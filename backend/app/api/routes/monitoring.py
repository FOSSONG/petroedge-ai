from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import AlertRepo
from app.core.rbac import require_roles
from app.db.session import get_db
from app.services.model_status import discover_model_statuses

router = APIRouter()
BACKEND_ROOT = Path(__file__).resolve().parents[3]


@router.get("/health")
async def service_health(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    checks: dict[str, Any] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"status": "healthy"}
    except Exception as exc:
        checks["database"] = {
            "status": "unhealthy",
            "detail": str(exc),
        }

    models = discover_model_statuses()
    model_count = sum(
        model.status == "ready"
        for model in models
    )

    checks["models"] = {
        "status": "healthy" if model_count else "degraded",
        "ready": model_count,
    }

    usage = shutil.disk_usage(BACKEND_ROOT)
    free_ratio = (
        usage.free / usage.total
        if usage.total
        else 0.0
    )

    checks["storage"] = {
        "status": (
            "healthy"
            if free_ratio >= 0.10
            else "degraded"
        ),
        "free_bytes": usage.free,
        "total_bytes": usage.total,
        "free_ratio": round(free_ratio, 4),
    }

    overall = "healthy"

    if any(
        item.get("status") == "unhealthy"
        for item in checks.values()
    ):
        overall = "unhealthy"
    elif any(
        item.get("status") == "degraded"
        for item in checks.values()
    ):
        overall = "degraded"

    return {
        "status": overall,
        "service": "PetroEdge AI",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


@router.get("/models")
async def model_status(
    _: dict[str, Any] = Depends(
        require_roles(
            "admin",
            "administrator",
            "operator",
            "petrophysicist",
            "geoscientist",
            "engineer",
            "viewer",
        )
    ),
) -> dict[str, Any]:
    models = discover_model_statuses()

    return {
        "registered_models": [
            model.model_dump()
            for model in models
        ],
        "ready": sum(
            model.status == "ready"
            for model in models
        ),
        "missing": sum(
            model.status == "missing"
            for model in models
        ),
        "checked_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }


@router.get("/alerts")
async def alert_status(
    alerts_repo: AlertRepo,
    limit: int = 100,
    _: dict[str, Any] = Depends(
        require_roles(
            "admin",
            "administrator",
            "operator",
            "petrophysicist",
            "geoscientist",
            "engineer",
            "viewer",
        )
    ),
) -> dict[str, Any]:
    records = alerts_repo.filtered(
        limit=max(1, min(limit, 500))
    )

    severity: dict[str, int] = {}
    recent: list[dict[str, Any]] = []

    for alert in records:
        key = str(
            alert.severity or "unknown"
        ).lower()

        severity[key] = severity.get(key, 0) + 1

        if len(recent) < 10:
            recent.append(
                {
                    "id": alert.id,
                    "severity": alert.severity,
                    "status": alert.status,
                    "title": alert.title,
                    "message": alert.message,
                    "created_at": (
                        alert.created_at.isoformat()
                    ),
                }
            )

    return {
        "total": len(records),
        "severity_distribution": severity,
        "recent": recent,
    }
