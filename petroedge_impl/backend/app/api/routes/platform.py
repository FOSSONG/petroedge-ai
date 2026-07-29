from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.rbac import require_roles
from app.ml_platform.registry import get_model_registry
from app.platform_v1.database import connection, initialise
from app.platform_v1.datasets import delete_dataset, get_dataset, list_datasets, preview_dataset, register_upload
from app.platform_v1.experiments import create_experiment, get_experiment, list_experiments
from app.platform_v1.schemas import DatasetPreview, DatasetSummary, ExperimentCreate, ExperimentSummary, PlatformOverview

router = APIRouter(prefix="/platform", tags=["Platform V1"])
READ_ROLES = require_roles("admin", "administrator", "operator", "engineer", "geoscientist", "petrophysicist", "viewer")
WRITE_ROLES = require_roles("admin", "administrator", "operator", "engineer", "geoscientist", "petrophysicist")
initialise()


def actor(user: dict[str, Any]) -> str | None:
    return str(user.get("uid") or user.get("sub") or "") or None


@router.get("/overview", response_model=PlatformOverview)
def overview(_: dict[str, Any] = Depends(READ_ROLES)) -> PlatformOverview:
    registry = get_model_registry()
    manifests = registry.list(include_disabled=True)
    with connection() as conn:
        datasets = conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]
        experiments = conn.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
        completed = conn.execute("SELECT COUNT(*) FROM experiments WHERE status = 'completed'").fetchone()[0]
    production = sum(1 for model in manifests if str(model.stage.value if hasattr(model.stage, "value") else model.stage) == "production")
    return PlatformOverview(
        version="1.0.0-mvp", datasets=int(datasets), experiments=int(experiments), completed_experiments=int(completed),
        registered_models=len(manifests), production_models=production,
        capabilities=["dataset_registry", "experiment_tracking", "model_registry", "model_comparison", "hierarchical_fluid_classification", "reservoir_intelligence", "realtime_events", "audit_logging", "portable_sqlite_storage", "docker_deployment"],
    )


@router.post("/datasets", response_model=DatasetSummary, status_code=status.HTTP_201_CREATED)
def upload_dataset(name: str = Form(...), description: str | None = Form(default=None), file: UploadFile = File(...), user: dict[str, Any] = Depends(WRITE_ROLES)) -> DatasetSummary:
    try:
        return register_upload(name, description, file.filename or "dataset", file.file, actor(user))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/datasets", response_model=list[DatasetSummary])
def datasets(_: dict[str, Any] = Depends(READ_ROLES)) -> list[DatasetSummary]:
    return list_datasets()


@router.get("/datasets/{dataset_id}", response_model=DatasetSummary)
def dataset(dataset_id: str, _: dict[str, Any] = Depends(READ_ROLES)) -> DatasetSummary:
    try:
        return get_dataset(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found.") from exc


@router.get("/datasets/{dataset_id}/preview", response_model=DatasetPreview)
def dataset_preview(dataset_id: str, limit: int = 500, _: dict[str, Any] = Depends(READ_ROLES)) -> DatasetPreview:
    try:
        return DatasetPreview(**preview_dataset(dataset_id, max(1, min(limit, 2000))))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found.") from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_dataset(dataset_id: str, user: dict[str, Any] = Depends(WRITE_ROLES)) -> None:
    try:
        delete_dataset(dataset_id, actor(user))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found.") from exc


@router.post("/experiments", response_model=ExperimentSummary, status_code=status.HTTP_201_CREATED)
def register_experiment(payload: ExperimentCreate, user: dict[str, Any] = Depends(WRITE_ROLES)) -> ExperimentSummary:
    return create_experiment(payload, actor(user))


@router.get("/experiments", response_model=list[ExperimentSummary])
def experiments(_: dict[str, Any] = Depends(READ_ROLES)) -> list[ExperimentSummary]:
    return list_experiments()


@router.get("/experiments/{experiment_id}", response_model=ExperimentSummary)
def experiment(experiment_id: str, _: dict[str, Any] = Depends(READ_ROLES)) -> ExperimentSummary:
    try:
        return get_experiment(experiment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Experiment not found.") from exc