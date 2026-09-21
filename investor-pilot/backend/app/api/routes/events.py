from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.rbac import require_roles
from app.events import event_bus

router = APIRouter()

READ_ROLES = ("admin", "geoscientist", "engineer", "viewer")


@router.get("")
async def list_events(
    event_type: str | None = None,
    asset_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    events = event_bus.history(
        event_type=event_type,
        asset_id=asset_id,
        limit=limit,
    )
    return {
        "count": len(events),
        "events": [item.model_dump(mode="json") for item in events],
    }