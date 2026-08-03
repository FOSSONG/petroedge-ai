from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.db.session import engine
from app.jobs.manager import get_job_manager
from app.realtime.manager import get_connection_manager

router = APIRouter()


def _database_probe() -> dict[str, Any]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        return {
            "status": "not_ready",
            "detail": f"{type(exc).__name__}: {exc}",
        }


@router.get("/readiness")
async def readiness(request: Request) -> dict[str, Any]:
    database = _database_probe()
    migrations = getattr(
        request.app.state,
        "migration_status",
        {"status": "unknown"},
    )
    ready = database["status"] == "ready" and migrations.get("status") != "failed"
    return {
        "status": "ready" if ready else "not_ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": database,
        "migrations": migrations,
    }


@router.get("/diagnostics")
async def diagnostics(request: Request) -> dict[str, Any]:
    route_modules = getattr(request.app.state, "route_modules", {})
    failed_routes = {
        name: details
        for name, details in route_modules.items()
        if details.get("status") == "failed"
    }
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": _database_probe(),
        "migrations": getattr(
            request.app.state,
            "migration_status",
            {"status": "unknown"},
        ),
        "realtime": getattr(
            request.app.state,
            "realtime_status",
            await get_connection_manager().snapshot(),
        ),
        "background_jobs": {
            "status": getattr(
                request.app.state,
                "job_manager_status",
                {"status": "unknown"},
            ),
            "running": get_job_manager().is_running,
            "worker_count": get_job_manager().worker_count,
            "queue_size": get_job_manager().queue_size,
        },
        "routes": {
            "loaded": sum(
                1 for details in route_modules.values()
                if details.get("status") == "loaded"
            ),
            "failed": failed_routes,
        },
    }