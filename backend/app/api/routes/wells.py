from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import DBSession, WellRepo
from app.core.rbac import require_roles
from app.realtime.events import EventType, get_event_bus
from app.schemas import WellCreate, WellLogSample, WellSummary
from app.services.alert_engine import AlertEngine
from app.services.domain_services import WellService
from app.services.synthetic import generate_samples

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
    await get_event_bus().emit(
        EventType.WELL_CREATED,
        serialized,
        channel="wells",
        correlation_id=well.well_id,
        actor_id=_actor_id(user),
    )
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

    if not records:
        demo = wells.get_or_create(
            "PETROEDGE-DEMO-01",
            field_name="Niger Delta Demo Field",
        )
        demo.metadata_json = {"source": "synthetic", "kb_m": 42.3}
        demo.total_depth_m = 3560.0
        wells.commit()
        records = [demo]

        await get_event_bus().emit(
            EventType.WELL_CREATED,
            service.serialize(demo),
            channel="wells",
            correlation_id=demo.well_id,
            actor_id=_actor_id(user),
        )

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
    await get_event_bus().emit(
        EventType.WELL_UPDATED,
        {**serialized, "deleted": True},
        channel="wells",
        correlation_id=well_id,
        actor_id=_actor_id(user),
    )
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


@router.get("/{well_id}/logs")
async def get_well_logs(
    well_id: str,
    db: DBSession,
    wells: WellRepo,
    rows: int = Query(default=250, ge=1, le=2000),
    emit_alerts: bool = Query(default=True),
    user: dict[str, Any] = Depends(
        require_roles("admin", "geoscientist", "engineer", "viewer")
    ),
) -> list[dict[str, Any]]:
    bus = get_event_bus()
    actor_id = _actor_id(user)
    well = wells.get_by_well_id(well_id)
    created = well is None

    if well is None:
        well = wells.get_or_create(well_id)
        await bus.emit(
            EventType.WELL_CREATED,
            WellService.serialize(well),
            channel="wells",
            correlation_id=well_id,
            actor_id=actor_id,
        )

    try:
        from app.services.analytics import analyze_sample
        samples = generate_samples(rows=rows, well_id=well_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate well-log samples: {exc}",
        ) from exc

    enriched: list[dict[str, Any]] = []
    emitted_alert_count = 0
    alert_engine = AlertEngine(db)

    for sample in samples:
        result = analyze_sample(WellLogSample(**sample)).model_dump()
        record = {
            **sample,
            "lithology": result["lithology"],
            "hydrocarbon_probability": result["hydrocarbon_probability"],
            "facies": result["facies"],
            "porosity": result["porosity"],
            "water_saturation": result["water_saturation"],
            "permeability_md": result["permeability_md"],
            "qc_score": result["qc_score"],
            "anomaly_score": result["anomaly_score"],
            "is_anomaly": result["is_anomaly"],
        }
        enriched.append(record)

        if emit_alerts:
            emitted = alert_engine.evaluate_record(
                record,
                source_type="well-log",
                source_id=well_id,
            )
            emitted_alert_count += len(emitted)
            for alert in emitted:
                item = alert.to_dict()
                await bus.emit(
                    EventType.ALERT_CREATED,
                    item,
                    channel="alerts",
                    correlation_id=item.get("alert_id"),
                    actor_id=actor_id,
                )

    well.metadata_json = {
        **(well.metadata_json or {}),
        "sample_count": rows,
    }
    wells.commit()

    await bus.emit(
        EventType.WELL_LOGS_LOADED,
        {
            "well_id": well_id,
            "rows": rows,
            "alert_count": emitted_alert_count,
            "created": created,
        },
        channel="wells",
        correlation_id=well_id,
        actor_id=actor_id,
    )

    await bus.emit(
        EventType.WELL_UPDATED,
        WellService.serialize(well),
        channel="wells",
        correlation_id=well_id,
        actor_id=actor_id,
    )

    return enriched


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