from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.services.dashboard_metrics import (
    DEFAULT_RECENT_LIMIT,
    MAX_RECENT_LIMIT,
    build_dashboard_snapshot,
    get_dashboard_metrics_service,
)


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    summary="Get the complete PetroEdge dashboard snapshot",
)
async def get_dashboard(
    recent_limit: int = Query(
        default=DEFAULT_RECENT_LIMIT,
        ge=1,
        le=MAX_RECENT_LIMIT,
        description=(
            "Maximum number of recent platform activities "
            "to include in the response."
        ),
    ),
) -> dict[str, Any]:
    try:
        snapshot = await asyncio.to_thread(
            build_dashboard_snapshot,
            recent_limit=recent_limit,
        )
    except Exception as exc:
        logger.exception(
            "Dashboard snapshot generation failed."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Dashboard metrics could not be generated. "
                "Review the backend logs for details."
            ),
        ) from exc

    return snapshot.to_dict()


@router.get(
    "/overview",
    summary="Get high-level platform metrics",
)
async def get_dashboard_overview() -> dict[str, Any]:
    try:
        snapshot = await asyncio.to_thread(
            build_dashboard_snapshot,
            recent_limit=1,
        )
    except Exception as exc:
        logger.exception(
            "Dashboard overview generation failed."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dashboard overview could not be generated.",
        ) from exc

    return {
        "generated_at": snapshot.generated_at,
        "overview": snapshot.overview,
        "cards": [
            card.to_dict()
            for card in snapshot.cards
        ],
    }


@router.get(
    "/operations",
    summary="Get streaming and operational metrics",
)
async def get_operational_metrics() -> dict[str, Any]:
    try:
        snapshot = await asyncio.to_thread(
            build_dashboard_snapshot,
            recent_limit=1,
        )
    except Exception as exc:
        logger.exception(
            "Operational dashboard metrics failed."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Operational metrics could not be generated.",
        ) from exc

    return {
        "generated_at": snapshot.generated_at,
        "operational": snapshot.operational,
    }


@router.get(
    "/data-quality",
    summary="Get dataset QC and AI-readiness metrics",
)
async def get_data_quality_metrics() -> dict[str, Any]:
    try:
        snapshot = await asyncio.to_thread(
            build_dashboard_snapshot,
            recent_limit=1,
        )
    except Exception as exc:
        logger.exception(
            "Data-quality dashboard metrics failed."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Data-quality metrics could not be generated.",
        ) from exc

    return {
        "generated_at": snapshot.generated_at,
        "data_quality": snapshot.data_quality,
    }


@router.get(
    "/models",
    summary="Get model execution and inference metrics",
)
async def get_model_metrics() -> dict[str, Any]:
    try:
        snapshot = await asyncio.to_thread(
            build_dashboard_snapshot,
            recent_limit=1,
        )
    except Exception as exc:
        logger.exception(
            "Model dashboard metrics failed."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model metrics could not be generated.",
        ) from exc

    return {
        "generated_at": snapshot.generated_at,
        "model_performance": snapshot.model_performance,
    }


@router.get(
    "/reservoir",
    summary="Get reservoir interpretation metrics",
)
async def get_reservoir_metrics() -> dict[str, Any]:
    try:
        snapshot = await asyncio.to_thread(
            build_dashboard_snapshot,
            recent_limit=1,
        )
    except Exception as exc:
        logger.exception(
            "Reservoir dashboard metrics failed."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reservoir metrics could not be generated.",
        ) from exc

    return {
        "generated_at": snapshot.generated_at,
        "reservoir_insights": snapshot.reservoir_insights,
    }


@router.get(
    "/alerts",
    summary="Get alert statistics",
)
async def get_alert_metrics() -> dict[str, Any]:
    try:
        snapshot = await asyncio.to_thread(
            build_dashboard_snapshot,
            recent_limit=1,
        )
    except Exception as exc:
        logger.exception(
            "Alert dashboard metrics failed."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Alert metrics could not be generated.",
        ) from exc

    return {
        "generated_at": snapshot.generated_at,
        "alert_metrics": snapshot.alert_metrics,
    }


@router.get(
    "/reports",
    summary="Get report-generation metrics",
)
async def get_reporting_metrics() -> dict[str, Any]:
    try:
        snapshot = await asyncio.to_thread(
            build_dashboard_snapshot,
            recent_limit=1,
        )
    except Exception as exc:
        logger.exception(
            "Reporting dashboard metrics failed."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reporting metrics could not be generated.",
        ) from exc

    return {
        "generated_at": snapshot.generated_at,
        "reporting_metrics": snapshot.reporting_metrics,
    }


@router.get(
    "/activity",
    summary="Get recent platform activity",
)
async def get_recent_activity(
    limit: int = Query(
        default=DEFAULT_RECENT_LIMIT,
        ge=1,
        le=MAX_RECENT_LIMIT,
    ),
) -> dict[str, Any]:
    try:
        snapshot = await asyncio.to_thread(
            build_dashboard_snapshot,
            recent_limit=limit,
        )
    except Exception as exc:
        logger.exception(
            "Recent dashboard activity failed."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Recent activity could not be generated.",
        ) from exc

    return {
        "generated_at": snapshot.generated_at,
        "items": snapshot.recent_activity,
        "total": len(snapshot.recent_activity),
        "limit": limit,
    }


@router.get(
    "/health",
    summary="Get dashboard service health",
)
async def dashboard_health() -> dict[str, Any]:
    service = get_dashboard_metrics_service()

    try:
        snapshot = await asyncio.to_thread(
            service.build_snapshot,
            recent_limit=1,
        )
    except Exception as exc:
        logger.exception(
            "Dashboard service health check failed."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard metrics service is unavailable.",
        ) from exc

    return {
        "status": "healthy",
        "generated_at": snapshot.generated_at,
        "datasets_total": snapshot.overview.get(
            "datasets_total",
            0,
        ),
        "predictions_total": snapshot.overview.get(
            "predictions_total",
            0,
        ),
        "active_streams": snapshot.overview.get(
            "active_streams",
            0,
        ),
        "alerts_total": snapshot.overview.get(
            "alerts_total",
            0,
        ),
        "reports_total": snapshot.overview.get(
            "reports_total",
            0,
        ),
    }


__all__ = ["router"]
