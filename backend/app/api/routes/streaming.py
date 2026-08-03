from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.core.rbac import require_roles
from app.events import EventCreate, event_bus
from app.streaming import ReplayRequest, TelemetryBatch, streaming_service

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