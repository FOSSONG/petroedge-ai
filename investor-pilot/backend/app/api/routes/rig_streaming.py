from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.rbac import require_roles
from app.services.rig_streaming import rig_stream_manager
from app.services.witsml import normalize_witsml_sample
from app.streaming import streaming_service

router = APIRouter()
READ_ROLES = ("admin", "geoscientist", "engineer", "viewer")
WRITE_ROLES = ("admin", "geoscientist", "engineer")


class BridgeStartRequest(BaseModel):
    endpoint: str
    headers: dict[str, str] = Field(default_factory=dict)


class GatewaySampleRequest(BaseModel):
    sample: dict[str, Any]


@router.get("/status")
async def connector_status(_: dict[str, Any] = Depends(require_roles(*READ_ROLES))) -> dict[str, Any]:
    rig_stream_manager.bind_delivery(streaming_service.ingest_edge_sample)
    return rig_stream_manager.status()


@router.post("/gateway/sample")
async def gateway_sample(
    request: GatewaySampleRequest,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    rig_stream_manager.bind_delivery(streaming_service.ingest_edge_sample)
    return await rig_stream_manager.accept(normalize_witsml_sample(request.sample))


@router.post("/buffer/flush")
async def flush_buffer(_: dict[str, Any] = Depends(require_roles(*WRITE_ROLES))) -> dict[str, Any]:
    rig_stream_manager.bind_delivery(streaming_service.ingest_edge_sample)
    return await rig_stream_manager.flush()


@router.post("/bridge/start")
async def start_bridge(
    request: BridgeStartRequest,
    _: dict[str, Any] = Depends(require_roles("admin", "engineer")),
) -> dict[str, Any]:
    rig_stream_manager.bind_delivery(streaming_service.ingest_edge_sample)
    await rig_stream_manager.start_websocket_bridge(request.endpoint, request.headers)
    return rig_stream_manager.status()


@router.post("/bridge/stop")
async def stop_bridge(_: dict[str, Any] = Depends(require_roles("admin", "engineer"))) -> dict[str, Any]:
    await rig_stream_manager.stop()
    return rig_stream_manager.status()
