from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.alerts import (
    AlertNotFoundError,
    AlertSeverity,
    AlertStatus,
    AlertUpdate,
    alert_manager,
)
from app.core.rbac import require_roles

router = APIRouter()

READ_ROLES = ("admin", "geoscientist", "engineer", "viewer")
WRITE_ROLES = ("admin", "geoscientist", "engineer")


@router.get("")
async def list_alerts(
    status: AlertStatus | None = None,
    severity: AlertSeverity | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    alerts = alert_manager.list(status=status, severity=severity, limit=limit)
    return {
        "count": len(alerts),
        "alerts": [item.model_dump(mode="json") for item in alerts],
    }


@router.get("/{alert_id}")
async def get_alert(
    alert_id: str,
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    try:
        alert = alert_manager.get(alert_id)
    except AlertNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Alert not found.") from exc
    return alert.model_dump(mode="json")


@router.patch("/{alert_id}")
async def update_alert(
    alert_id: str,
    request: AlertUpdate,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    try:
        alert = alert_manager.update(alert_id, request)
    except AlertNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Alert not found.") from exc
    return alert.model_dump(mode="json")