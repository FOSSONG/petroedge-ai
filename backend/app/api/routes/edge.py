from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.edge_temporal import (
    EdgeTemporalInferenceService,
    TemporalModelKind,
    TemporalModelManifest,
    TemporalWorkflow,
    default_manifests,
)

router = APIRouter()
service = EdgeTemporalInferenceService()


class TemporalInferenceRequest(BaseModel):
    model_kind: TemporalModelKind = TemporalModelKind.GRU
    workflow: TemporalWorkflow = TemporalWorkflow.DIGITAL_TWIN
    execution_mode: Literal["live", "batch", "replay", "historical"] = "live"
    values: list[list[float]] = Field(min_length=4)
    window_size: int = Field(default=4, ge=4, le=512)


@router.get("/capabilities")
async def edge_capabilities() -> dict[str, Any]:
    return {
        "edge_ready": True,
        "architectures": ["linux/amd64", "linux/arm64"],
        "accelerators": ["CPU", "CUDA", "NVIDIA Jetson/TensorRT profile"],
        "connectors": ["file-replay", "TCP", "UDP", "WebSocket", "MQTT", "REST"],
        "temporal_models": ["GRU", "BiGRU"],
        "policy": {
            "GRU": "causal live, replay, historical and batch inference",
            "BiGRU": "historical, replay and batch inference only",
        },
        "workflows": [workflow.value for workflow in TemporalWorkflow],
        "installed_manifests": [manifest.__dict__ for manifest in default_manifests()],
    }


@router.post("/temporal/predict")
async def temporal_predict(payload: TemporalInferenceRequest) -> dict[str, Any]:
    manifest = TemporalModelManifest(
        model_id=f"petroedge-{payload.model_kind.value}-{payload.workflow.value}-demo",
        version="1.0.0-demo",
        kind=payload.model_kind,
        workflow=payload.workflow,
        causal=payload.model_kind == TemporalModelKind.GRU,
        runtime="onnxruntime",
        window_size=payload.window_size,
    )
    try:
        return service.predict(manifest, payload.values, execution_mode=payload.execution_mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
