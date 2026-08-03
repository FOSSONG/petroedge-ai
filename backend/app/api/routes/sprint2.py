from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.rbac import require_roles
from app.jobs.manager import get_job_manager
from app.ml_platform.registry import get_model_registry
from app.platform_v1.datasets import list_datasets
from app.platform_v1.experiments import list_experiments
from app.realtime.manager import get_connection_manager
from app.api.routes.reservoir_v1 import _interpret

router = APIRouter(prefix="/sprint2", tags=["Sprint 2 Platform"])
READ_ROLES = require_roles("admin", "administrator", "operator", "engineer", "geoscientist", "petrophysicist", "viewer")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workflow_for_dataset(dataset: Any) -> list[dict[str, Any]]:
    columns = {str(item).lower() for item in (dataset.columns or [])}
    recognised = any(token in " ".join(columns) for token in ("gr", "gamma", "rhob", "nphi", "res", "ild", "depth"))
    stages = [
        ("Upload", True, "Dataset registered"),
        ("Curve recognition", recognised, "Well-log aliases mapped" if recognised else "Awaiting recognised log curves"),
        ("Quality control", dataset.status == "ready", "Profile and missing-value checks complete"),
        ("Feature engineering", dataset.status == "ready" and recognised, "Petrophysical features available"),
        ("Lithology", dataset.status == "ready" and recognised, "Interpretation ready"),
        ("Petrophysics", dataset.status == "ready" and recognised, "Porosity, saturation and permeability ready"),
        ("Hydrocarbon detection", dataset.status == "ready" and recognised, "Screening model ready"),
        ("Pay detection", dataset.status == "ready" and recognised, "Intervals can be evaluated"),
        ("Report", False, "Generated on demand"),
        ("Knowledge base", False, "Requires expert validation"),
    ]
    return [
        {"name": name, "status": "completed" if done else "pending", "message": message, "order": index + 1}
        for index, (name, done, message) in enumerate(stages)
    ]


@router.get("/operations")
async def operations(_: dict[str, Any] = Depends(READ_ROLES)) -> dict[str, Any]:
    datasets = list_datasets()
    experiments = list_experiments()
    models = get_model_registry().list(include_disabled=True)
    realtime = await get_connection_manager().snapshot()
    jobs = get_job_manager()
    active_experiments = [item for item in experiments if item.status in {"queued", "running"}]
    failed_experiments = [item for item in experiments if item.status == "failed"]
    current = datasets[0] if datasets else None
    return {
        "generated_at": _now(),
        "summary": {
            "datasets": len(datasets),
            "active_wells": len({item.name for item in datasets}),
            "running_jobs": len(active_experiments) + jobs.queue_size,
            "registered_models": len(models),
            "failed_jobs": len(failed_experiments),
            "realtime_clients": int(realtime.get("connections", realtime.get("connection_count", 0)) or 0),
        },
        "current_dataset": current.model_dump() if current else None,
        "processing_queue": [
            {
                "id": item.experiment_id,
                "name": item.name,
                "task": item.task,
                "status": item.status,
                "progress": item.progress_percent,
                "stage": item.current_stage,
                "dataset_id": item.dataset_id,
            }
            for item in active_experiments[:10]
        ],
        "services": [
            {"name": "FastAPI", "status": "online", "detail": "API responding"},
            {"name": "Background jobs", "status": "online" if jobs.is_running else "offline", "detail": f"{jobs.worker_count} worker(s), queue {jobs.queue_size}"},
            {"name": "Realtime events", "status": "online", "detail": f"{len(realtime.get('channels', []))} channel(s)"},
            {"name": "Model registry", "status": "online", "detail": f"{len(models)} registered model(s)"},
        ],
        "workflow": _workflow_for_dataset(current) if current else [],
    }


@router.get("/calibration")
def calibration(_: dict[str, Any] = Depends(READ_ROLES)) -> dict[str, Any]:
    datasets = list_datasets()
    samples = sum(int(item.row_count or 0) for item in datasets)
    validated = sum(1 for item in datasets if item.status == "ready")
    return {
        "region": "Niger Delta",
        "calibration_name": "Niger Delta screening calibration",
        "status": "active" if datasets else "baseline",
        "formations": ["Benin Formation", "Agbada Formation", "Akata Formation"],
        "datasets": len(datasets),
        "validated_datasets": validated,
        "training_samples": samples,
        "supported_curves": ["DEPTH", "GR", "RT/ILD", "RHOB", "NPHI", "DT", "CALI"],
        "governance": "Expert validation required before knowledge-base admission",
        "last_updated": _now(),
    }


@router.get("/learning")
def continual_learning(_: dict[str, Any] = Depends(READ_ROLES)) -> dict[str, Any]:
    datasets = list_datasets()
    experiments = list_experiments()
    candidates = [item for item in experiments if item.status == "completed" and item.model_id]
    return {
        "knowledge_base": {"eligible_datasets": sum(1 for item in datasets if item.status == "ready"), "admitted_datasets": 0},
        "retraining_queue": [
            {"dataset_id": item.dataset_id, "name": item.name, "status": "awaiting_expert_validation"}
            for item in datasets[:10]
        ],
        "model_candidates": [
            {"experiment_id": item.experiment_id, "model_id": item.model_id, "task": item.task, "metrics": item.metrics, "status": "validation_required"}
            for item in candidates[:10]
        ],
        "controls": ["data leakage check", "cross-validation", "hold-out validation", "expert sign-off", "rollback-ready deployment"],
    }


class ExplainRequest(BaseModel):
    question: str = Field(default="Explain the hydrocarbon and pay interpretation", min_length=2, max_length=1000)


@router.post("/datasets/{dataset_id}/explain")
def explain(dataset_id: str, payload: ExplainRequest, _: dict[str, Any] = Depends(READ_ROLES)) -> dict[str, Any]:
    try:
        result = _interpret(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    samples = result["samples"]
    best = max(samples, key=lambda row: float(row["hydrocarbon_probability"]))
    drivers = [
        {"feature": "Resistivity", "direction": "supports hydrocarbon" if float(best["rt"]) >= 10 else "weak support", "value": best["rt"], "unit": "ohm·m"},
        {"feature": "Gamma ray", "direction": "supports clean reservoir" if float(best["gr"]) <= 75 else "indicates shale influence", "value": best["gr"], "unit": "API"},
        {"feature": "Porosity", "direction": "supports reservoir quality" if float(best["porosity"]) >= .15 else "limited reservoir quality", "value": best["porosity"], "unit": "v/v"},
        {"feature": "Water saturation", "direction": "supports pay" if float(best["water_saturation"]) <= .60 else "water risk", "value": best["water_saturation"], "unit": "v/v"},
        {"feature": "Shale volume", "direction": "supports reservoir" if float(best["shale_volume"]) <= .45 else "shale risk", "value": best["shale_volume"], "unit": "v/v"},
    ]
    intervals = [
        {**interval, "gross_thickness": round(abs(float(interval["base_depth"]) - float(interval["top_depth"])), 3)}
        for interval in result["intervals"]
    ]
    return {
        "question": payload.question,
        "dataset_id": dataset_id,
        "prediction": best["pay_flag"],
        "confidence": best["hydrocarbon_probability"],
        "best_depth": best["depth"],
        "lithology": best["lithology"],
        "drivers": drivers,
        "pay_intervals": intervals,
        "method": "Physics-informed Niger Delta screening explanation",
        "limitations": ["Screening result only", "Validate with core, pressure, fluid and production evidence"],
    }
