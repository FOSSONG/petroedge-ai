from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.db.session import engine
from app.jobs.manager import get_job_manager
from app.realtime.manager import get_connection_manager

router = APIRouter()

def _route_integrity(request: Request) -> dict[str, Any]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    duplicates: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []

    for route in request.app.routes:
        path = getattr(route, "path", None)
        methods = tuple(sorted(getattr(route, "methods", set()) or set()))
        name = getattr(route, "name", None)
        if not path:
            continue
        key = (path, methods)
        if key in seen:
            duplicates.append(
                {
                    "path": path,
                    "methods": list(methods),
                    "name": name,
                }
            )
        else:
            seen.add(key)
        routes.append(
            {
                "path": path,
                "methods": list(methods),
                "name": name,
            }
        )

    return {
        "status": "ok" if not duplicates else "warning",
        "route_count": len(routes),
        "duplicate_count": len(duplicates),
        "duplicates": duplicates,
    }


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
        "startup": {
            "started_at": getattr(request.app.state, "startup_started_at", None),
            "ready_at": getattr(request.app.state, "ready_at", None),
            "duration_ms": getattr(request.app.state, "startup_duration_ms", None),
        },
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
        "route_integrity": _route_integrity(request),
        "routes": {
            "loaded": sum(
                1 for details in route_modules.values()
                if details.get("status") == "loaded"
            ),
            "failed": failed_routes,
        },
    }

@router.get("/route-audit")
async def route_audit(request: Request) -> dict[str, Any]:
    return _route_integrity(request)