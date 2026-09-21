from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import DBSession, WellRepo
from app.core.rbac import require_roles
from app.realtime.events import EventType, get_event_bus
from app.schemas import WellCreate, WellLogSample, WellSummary
from app.services.alert_engine import AlertEngine
from app.services.domain_services import WellService
from app.platform_v1 import datasets
from pydantic import BaseModel, ConfigDict, Field
import json
import hashlib
from datetime import datetime, timezone
from app.services.well_curve_mapping import CurveMapping, UNITS, validate_mapping, mapped_records

router = APIRouter()


def _actor_id(user: dict[str, Any]) -> str | None:
    value = user.get("user_id") or user.get("uid") or user.get("sub")
    return str(value) if value else None


@router.post("", response_model=WellSummary, status_code=status.HTTP_201_CREATED)
async def create_well(
    payload: WellCreate,
    wells: WellRepo,
    user: dict[str, Any] = Depends(
        require_roles("admin", "geoscientist", "engineer")
    ),
) -> WellSummary:
    if wells.get_by_well_id(payload.well_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Well '{payload.well_id}' already exists.",
        )

    well = wells.get_or_create(
        payload.well_id,
        field_name=payload.field,
        status=payload.status,
    )
    well.total_depth_m = payload.total_depth_m
    well.operator_name = payload.operator
    well.country = payload.country
    well.latitude = payload.latitude
    well.longitude = payload.longitude
    well.metadata_json = {
        **(well.metadata_json or {}),
        "source": "manual-registration",
        "kb_m": payload.kb_m,
    }
    wells.commit()

    serialized = WellService.serialize(well)

    return WellSummary(**serialized)


@router.get("", response_model=list[WellSummary])
async def list_wells(
    wells: WellRepo,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: dict[str, Any] = Depends(
        require_roles("admin", "geoscientist", "engineer", "viewer")
    ),
) -> list[WellSummary]:
    service = WellService(wells)
    records = wells.list_ordered(offset=offset, limit=limit)

    return [WellSummary(**service.serialize(record)) for record in records]


@router.delete("/{well_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_well(
    well_id: str,
    wells: WellRepo,
    user: dict[str, Any] = Depends(require_roles("admin", "geoscientist", "engineer")),
) -> None:
    well = wells.get_by_well_id(well_id)
    if well is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Well not found.")
    serialized = WellService.serialize(well)
    try:
        wells.delete(well)
        wells.commit()
    except Exception as exc:
        wells.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The well cannot be deleted because related governed records still reference it.",
        ) from exc

    return None


@router.get("/{well_id}", response_model=WellSummary)
def get_well(
    well_id: str,
    wells: WellRepo,
    _: dict[str, Any] = Depends(
        require_roles("admin", "geoscientist", "engineer", "viewer")
    ),
) -> WellSummary:
    well = wells.get_by_well_id(well_id)
    if well is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Well not found.",
        )
    return WellSummary(**WellService.serialize(well))


class WellDatasetBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str
    mapping: CurveMapping | None = None


def _bound_source(well, dataset_id: str):
    try:
        dataset = datasets.get_dataset(dataset_id)
        path = datasets.get_dataset_path(dataset_id)
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(404, "Dataset not found.") from exc
    if dataset.dataset_type not in {"well_log", "processed_well_log"}:
        raise HTTPException(422, "Only well-log datasets can be bound here.")
    if dataset.well_name != well.well_id:
        raise HTTPException(422, "Dataset well name must exactly match the registered well ID. Prepare a single-well dataset first.")
    if datasets._checksum(path) != dataset.checksum_sha256:
        raise HTTPException(409, "Dataset contents changed; register a new dataset version.")
    return dataset, path


@router.put("/{well_id}/log-dataset")
def bind_log_dataset(well_id: str, payload: WellDatasetBinding, wells: WellRepo,
                     _: dict[str, Any] = Depends(require_roles("admin", "engineer", "geoscientist"))):
    well = wells.get_by_well_id(well_id)
    if well is None:
        raise HTTPException(404, "Well not found.")
    dataset, path = _bound_source(well, payload.dataset_id)
    frame = datasets._frame(path)
    for column in frame.columns:
        if str(column).strip().lower() in {"well", "well_id", "well_name", "wellid"}:
            if not frame[column].notna().all() or not frame[column].astype(str).eq(well_id).all():
                raise HTTPException(422, "Dataset contains missing or different well identifiers; prepare a single-well dataset first.")
    if payload.mapping is not None:
        try:
            validate_mapping(payload.mapping, frame.columns)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    binding = {"mapping": payload.mapping.model_dump() if payload.mapping else None, "dataset_id": dataset.dataset_id, "version_id": dataset.version_id,
               "checksum_sha256": dataset.checksum_sha256}
    well.metadata_json = {**(well.metadata_json or {}), "log_dataset": binding}
    wells.commit()
    return {"well_id": well_id, **binding}


@router.get("/{well_id}/logs")
def get_well_logs(well_id: str, wells: WellRepo,
                  rows: int = Query(default=250, ge=1, le=2000),
                  offset: int = Query(default=0, ge=0),
                  emit_alerts: bool = Query(default=False),
                  mapped: bool = Query(default=False),
                  _: dict[str, Any] = Depends(require_roles("viewer"))) -> list[dict[str, Any]]:
    well = wells.get_by_well_id(well_id)
    if well is None:
        raise HTTPException(404, "Well not found.")
    if emit_alerts:
        raise HTTPException(422, "Log retrieval does not generate alerts. Run a validated analysis separately.")
    binding = (well.metadata_json or {}).get("log_dataset")
    if not binding:
        raise HTTPException(409, "No uploaded log dataset is bound to this well.")
    dataset, path = _bound_source(well, binding["dataset_id"])
    if dataset.version_id != binding["version_id"] or dataset.checksum_sha256 != binding["checksum_sha256"]:
        raise HTTPException(409, "Dataset version changed; rebind the well explicitly.")
    frame = datasets._frame(path, limit=offset + rows).iloc[offset:offset + rows]
    if mapped:
        if not binding.get("mapping"):
            raise HTTPException(409, "Configure explicit curve and unit mapping before viewing mapped logs.")
        try:
            records = mapped_records(frame, CurveMapping.model_validate(binding["mapping"]), well_id)
            for index, record in enumerate(records, start=offset):
                record["source_row"] = index
                record["binding_sha256"] = _binding_digest(binding)
            return records
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    return json.loads(frame.to_json(orient="records", date_format="iso"))


@router.get("/{well_id}/alerts")
def get_well_alerts(
    well_id: str,
    db: DBSession,
    wells: WellRepo,
    limit: int = Query(default=50, ge=1, le=500),
    _: dict[str, Any] = Depends(
        require_roles("admin", "geoscientist", "engineer", "viewer")
    ),
) -> dict[str, Any]:
    well = wells.get_by_well_id(well_id)
    if well is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Well not found.",
        )
    records = AlertEngine(db).alerts.filtered(
        well_db_id=well.id,
        limit=limit,
    )
    alerts = [
        AlertEngine.serialize_model(item, well_id)
        for item in records
    ]
    return {
        "well_id": well_id,
        "total": len(alerts),
        "alerts": alerts,
    }

@router.get("/{well_id}/log-dataset")
def get_log_binding(well_id: str, wells: WellRepo,
                    _: dict[str, Any] = Depends(require_roles("viewer"))):
    well = wells.get_by_well_id(well_id)
    if well is None:
        raise HTTPException(404, "Well not found.")
    binding = (well.metadata_json or {}).get("log_dataset")
    if binding:
        _bound_source(well, binding["dataset_id"])
    return {"binding": binding, "supported_units": UNITS}


def _binding_digest(binding: dict) -> str:
    return hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


class BoundRowAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_row: int = Field(ge=0, le=10000000)
    binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


@router.post("/{well_id}/analyze-row")
def analyze_bound_row(well_id: str, request: BoundRowAnalysis, wells: WellRepo,
                      _: dict[str, Any] = Depends(require_roles("viewer"))):
    well = wells.get_by_well_id(well_id)
    if well is None:
        raise HTTPException(404, "Well not found.")
    binding = (well.metadata_json or {}).get("log_dataset")
    if not binding or not binding.get("mapping"):
        raise HTTPException(409, "An explicit dataset and curve mapping is required.")
    digest = _binding_digest(binding)
    if digest != request.binding_sha256:
        raise HTTPException(409, "The well binding changed. Refresh the log rows before analysis.")
    dataset, path = _bound_source(well, binding["dataset_id"])
    if dataset.version_id != binding["version_id"] or dataset.checksum_sha256 != binding["checksum_sha256"]:
        raise HTTPException(409, "Dataset version changed. Rebind and refresh before analysis.")
    frame = datasets._frame(path, limit=request.source_row + 1).iloc[request.source_row:request.source_row + 1]
    if frame.empty:
        raise HTTPException(404, "Source row not found.")
    try:
        record = mapped_records(frame, CurveMapping.model_validate(binding["mapping"]), well_id)[0]
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not record["analysis_ready"]:
        raise HTTPException(422, "Source row lacks valid required curves or measured depth.")
    # Recheck after parsing; do not analyze a file modified during loading.
    if datasets._checksum(path) != binding["checksum_sha256"]:
        raise HTTPException(409, "Dataset changed while loading. Retry with an immutable version.")
    sample = WellLogSample.model_validate(record)
    from app.services.analytics import analyze_sample
    result = analyze_sample(sample).model_dump()
    result["provenance"] = {
        "well_id": well_id, "dataset_id": dataset.dataset_id,
        "version_id": dataset.version_id, "checksum_sha256": dataset.checksum_sha256,
        "source_row": request.source_row, "row_index_basis": "zero-based parsed data row, excluding header",
        "binding_sha256": digest, "mapping": binding["mapping"],
        "input_sha256": hashlib.sha256(json.dumps(sample.model_dump(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest(),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "analysis_engine": "sample analytics; model identities and fallbacks are recorded in explanation",
        "persisted": False,
    }
    from app.services.analysis_records import save
    return save(result)
