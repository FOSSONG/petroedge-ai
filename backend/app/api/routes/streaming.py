from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.core.rbac import require_roles
from app.events import EventCreate, event_bus
from app.streaming import EdgeStreamBatch, EdgeStreamSample, ReplayRequest, TelemetryBatch, streaming_service
from app.streaming.channel_registry import registry_payload
from app.services.realtime_inference import real_time_interpretation_service

router = APIRouter()

READ_ROLES = ("admin", "geoscientist", "engineer", "viewer")
WRITE_ROLES = ("admin", "geoscientist", "engineer")


@router.post("/events")
async def ingest_event(
    request: EventCreate,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    delivery = await streaming_service.ingest(request)
    return delivery.model_dump(mode="json")


@router.post("/telemetry")
async def ingest_telemetry(
    request: TelemetryBatch,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    delivery = await streaming_service.ingest_telemetry(request)
    return delivery.model_dump(mode="json")


@router.get("/edge/inference/status")
async def edge_inference_status(
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    model_path = real_time_interpretation_service.model_root / "gru_live.onnx"
    return {
        "physics_ready": True,
        "trained_gru_installed": model_path.is_file(),
        "trained_gru_path": str(model_path),
        "live_demo_fallback_allowed": False,
        "fusion_policy": "physics + trained causal GRU when installed; otherwise physics-only",
        "bigru_live_allowed": False,
    }


@router.get("/edge/channels")
async def edge_channel_registry(
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    channels = registry_payload()
    return {"count": len(channels), "channels": channels}


@router.post("/edge/sample")
async def ingest_edge_sample(
    request: EdgeStreamSample,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    return await streaming_service.ingest_edge_sample(request)


@router.post("/edge/batch")
async def ingest_edge_batch(
    request: EdgeStreamBatch,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    return await streaming_service.ingest_edge_batch(request)


@router.post("/replay")
async def replay_events(
    request: ReplayRequest,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    deliveries = await streaming_service.replay(request)
    return {
        "count": len(deliveries),
        "deliveries": [item.model_dump(mode="json") for item in deliveries],
    }


@router.websocket("/ws")
async def stream_events(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = event_bus.create_queue()
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.remove_queue(queue)