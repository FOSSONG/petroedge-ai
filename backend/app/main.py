from __future__ import annotations

import asyncio
import importlib
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.jobs.manager import get_job_manager
from app.realtime.events import EventType, get_event_bus
from app.realtime.manager import get_connection_manager

logger = logging.getLogger(__name__)
API_PREFIX = "/api/v1"
APP_VERSION = "4.1.1"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI_PATH = BACKEND_ROOT / "alembic.ini"
ALEMBIC_SCRIPT_PATH = BACKEND_ROOT / "alembic"

ROUTE_MODULES: tuple[tuple[str, str, tuple[str, ...], bool], ...] = (
    ("auth", "/auth", ("Authentication",), True),
    ("dashboard", "/dashboard", ("Dashboard",), True),
    ("wells", "/wells", ("Wells",), True),
    ("assets", "/assets", ("Asset Management",), True),
    ("ccus", "/ccus", ("CCUS Screening",), True),
    ("models", "/models", ("Models",), True),
    ("workflows", "/workflows", ("Workflow Engine",), True),
    ("agents", "/agents", ("Multi-Agent AI",), True),
    ("twins", "/twins", ("Reservoir Digital Twin",), True),
    ("twin_workspace", "/twin-workspace", ("Digital Twin Workspace",), True),
    ("rules", "/rules", ("Event Rules",), True),
    ("events", "/events", ("Event Bus",), True),
    ("monitoring", "/monitoring", ("Monitoring",), True),
    ("platform", "", ("Platform",), True),
    ("plugins", "/plugins", ("Built-in Modules",), True),
    ("reservoir_v1", "", ("Reservoir Intelligence V1",), True),
    ("jobs", "/jobs", ("Background Jobs",), True),
    ("realtime", "/realtime", ("Real-time Events",), True),
    ("edge", "/edge", ("Edge Computing",), True),
    ("training_lifecycle", "/training-lifecycle", ("Model Training and Lifecycle",), True),
    ("alerts", "/alerts", ("Alerts",), False),
    ("analytics", "/analytics", ("Analytics",), False),
    ("ingestion", "/ingestion", ("Ingestion",), False),
    ("reports", "/reports", ("Reports",), False),
    ("streaming", "/streaming", ("Streaming",), False),
    ("stream", "", ("Stream",), False),
    ("upload", "", ("Upload",), False),
)


def _parse_boolean(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalised = value.strip().lower()
    if normalised in {"1", "true", "yes", "on"}:
        return True
    if normalised in {"0", "false", "no", "off"}:
        return False
    logger.warning("Invalid Boolean value %r; using default=%s.", value, default)
    return default


def _is_production() -> bool:
    return str(settings.environment).strip().lower() in {"production", "prod"}


def _should_run_migrations() -> bool:
    return _parse_boolean(
        os.getenv("PETROEDGE_RUN_MIGRATIONS"),
        default=not _is_production(),
    )


def _build_alembic_config() -> Config:
    if not ALEMBIC_INI_PATH.is_file():
        raise FileNotFoundError(f"Alembic configuration not found: {ALEMBIC_INI_PATH}")
    if not ALEMBIC_SCRIPT_PATH.is_dir():
        raise FileNotFoundError(f"Alembic directory not found: {ALEMBIC_SCRIPT_PATH}")
    config = Config(str(ALEMBIC_INI_PATH))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPT_PATH))
    return config


def _run_database_migrations() -> None:
    command.upgrade(_build_alembic_config(), "head")


def _check_database_connection() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def _register_routes(application: FastAPI) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    registered_router_ids: set[int] = set()

    for route_spec in ROUTE_MODULES:
        if len(route_spec) == 4:
            module_name, prefix, tags, required = route_spec
        elif len(route_spec) == 3:
            # Backward compatibility for legacy route declarations.
            module_name, prefix, tags = route_spec
            required = False
        else:
            raise ValueError(
                "Invalid ROUTE_MODULES entry. Expected "
                f"(module_name, prefix, tags[, required]), got: {route_spec!r}"
            )
        try:
            module = importlib.import_module(f"app.api.routes.{module_name}")
            router = getattr(module, "router", None)
            if router is None:
                raise AttributeError(f"{module_name!r} does not expose a router object")
            if id(router) in registered_router_ids:
                state[module_name] = {
                    "status": "skipped",
                    "required": required,
                    "detail": "Router already registered.",
                }
                continue
            full_prefix = f"{API_PREFIX}{prefix}"
            application.include_router(router, prefix=full_prefix, tags=list(tags))
            registered_router_ids.add(id(router))
            state[module_name] = {
                "status": "loaded",
                "required": required,
                "prefix": full_prefix,
            }
        except Exception as exc:
            state[module_name] = {
                "status": "failed",
                "required": required,
                "detail": f"{type(exc).__name__}: {exc}",
            }
            logger.exception("Could not load route module %s.", module_name)
            if required:
                raise RuntimeError(
                    f"Required route module failed to load: {module_name}"
                ) from exc
    return state


@asynccontextmanager
async def lifespan(application: FastAPI):
    run_migrations = _should_run_migrations()
    application.state.migration_status = {
        "enabled": run_migrations,
        "status": "not_started",
    }

    if run_migrations:
        try:
            await asyncio.to_thread(_run_database_migrations)
            application.state.migration_status = {
                "enabled": True,
                "status": "completed",
                "revision": "head",
            }
        except Exception as exc:
            application.state.migration_status = {
                "enabled": True,
                "status": "failed",
                "detail": f"{type(exc).__name__}: {exc}",
            }
            logger.exception("Database migration failed.")
            raise RuntimeError("Database migration failed; startup aborted.") from exc
    else:
        application.state.migration_status = {
            "enabled": False,
            "status": "skipped",
            "detail": "Run 'alembic upgrade head' before production startup.",
        }

    await asyncio.to_thread(_check_database_connection)

    realtime_manager = get_connection_manager()
    await realtime_manager.start()
    application.state.realtime_manager = realtime_manager

    job_manager = get_job_manager()
    await job_manager.start()
    application.state.job_manager = job_manager

    await get_event_bus().emit(
        EventType.SYSTEM_READY,
        {"service": settings.app_name, "version": APP_VERSION},
        channel="global",
    )

    try:
        yield
    finally:
        await get_event_bus().emit(
            EventType.SYSTEM_SHUTDOWN,
            {"service": settings.app_name},
            channel="global",
        )
        await job_manager.stop()
        await realtime_manager.stop()
        engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(
        title="PetroEdge AI API",
        version=APP_VERSION,
        description="Real-time well logging analytics and reservoir intelligence API.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    application.add_middleware(GZipMiddleware, minimum_size=1000)
    application.state.route_modules = _register_routes(application)

    @application.get("/", tags=["System"])
    async def root() -> dict[str, Any]:
        return {
            "application": settings.app_name,
            "version": APP_VERSION,
            "environment": settings.environment,
            "docs": "/docs",
            "health": "/health",
            "api_prefix": API_PREFIX,
        }

    @application.get("/health", tags=["System"])
    async def health() -> dict[str, Any]:
        database_status = "healthy"
        try:
            await asyncio.to_thread(_check_database_connection)
        except Exception as exc:
            database_status = f"unhealthy: {type(exc).__name__}: {exc}"

        failed_routes = {
            name: details
            for name, details in application.state.route_modules.items()
            if details.get("status") == "failed"
        }
        migration_status = getattr(
            application.state,
            "migration_status",
            {"enabled": False, "status": "not_started"},
        )
        unhealthy = database_status != "healthy" or migration_status.get("status") == "failed"
        overall = "unhealthy" if unhealthy else ("degraded" if failed_routes else "ok")
        return {
            "status": overall,
            "service": settings.app_name,
            "version": APP_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": database_status,
            "migrations": migration_status,
            "routes": application.state.route_modules,
            "background_jobs": {
                "running": get_job_manager().is_running,
                "worker_count": get_job_manager().worker_count,
                "queue_size": get_job_manager().queue_size,
            },
            "realtime": await get_connection_manager().snapshot(),
        }

    return application


app = create_app()



