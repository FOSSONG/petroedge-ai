from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.dependencies import DBSession
from app.core.rbac import require_roles
from app.realtime.events import EventType, get_event_bus
from app.schemas import AnalyticsResult, WellLogSample
from app.services.alert_engine import AlertEngine
from app.services.domain_services import AnalyticsPersistenceService

router = APIRouter()


def _actor_id(user: dict[str, Any]) -> str | None:
    value = user.get("user_id") or user.get("uid") or user.get("sub")
    return str(value) if value else None


@router.post("/sample", response_model=AnalyticsResult)
async def sample_analysis(
    sample: WellLogSample,
    db: DBSession,
    emit_alerts: bool = True,
    user: dict[str, Any] = Depends(
        require_roles("admin", "geoscientist", "engineer", "viewer")
    ),
) -> AnalyticsResult:
    from app.services.analytics import analyze_sample

    bus = get_event_bus()
    actor_id = _actor_id(user)
    correlation_id = f"{sample.well_id}:{sample.depth_m}"

    await bus.emit(
        EventType.ANALYSIS_STARTED,
        {
            "well_id": sample.well_id,
            "depth_m": sample.depth_m,
        },
        channel="analytics",
        correlation_id=correlation_id,
        actor_id=actor_id,
    )

    try:
        result = analyze_sample(sample)
        payload = result.model_dump()
        AnalyticsPersistenceService(db).persist_sample_result(payload)

        emitted_alerts = []
        if emit_alerts:
            emitted_alerts = AlertEngine(db).evaluate_record(
                {**sample.model_dump(), **payload},
                source_type="analytics",
                source_id=sample.well_id,
            )

        for alert in emitted_alerts:
            item = alert.to_dict()
            await bus.emit(
                EventType.ALERT_CREATED,
                item,
                channel="alerts",
                correlation_id=item.get("alert_id"),
                actor_id=actor_id,
            )

        await bus.emit(
            EventType.PREDICTION_COMPLETED,
            {
                "well_id": sample.well_id,
                "depth_m": sample.depth_m,
                "lithology": payload.get("lithology"),
                "hydrocarbon_probability": payload.get(
                    "hydrocarbon_probability"
                ),
                "porosity": payload.get("porosity"),
                "water_saturation": payload.get("water_saturation"),
                "permeability_md": payload.get("permeability_md"),
                "qc_score": payload.get("qc_score"),
                "alert_count": len(emitted_alerts),
            },
            channel="analytics",
            correlation_id=correlation_id,
            actor_id=actor_id,
        )

        await bus.emit(
            EventType.ANALYSIS_COMPLETED,
            {
                "well_id": sample.well_id,
                "depth_m": sample.depth_m,
                "status": "completed",
            },
            channel="analytics",
            correlation_id=correlation_id,
            actor_id=actor_id,
        )

        return result
    except Exception as exc:
        await bus.emit(
            EventType.ANALYSIS_FAILED,
            {
                "well_id": sample.well_id,
                "depth_m": sample.depth_m,
                "error": f"{type(exc).__name__}: {exc}",
            },
            channel="analytics",
            correlation_id=correlation_id,
            actor_id=actor_id,
        )
        raise


@router.get("/predict")
def prediction_example(
    _: dict[str, Any] = Depends(
        require_roles("admin", "geoscientist", "engineer", "viewer")
    ),
) -> dict[str, Any]:
    return {
        "detail": "Use POST /api/v1/analytics/sample with a validated well-log sample.",
        "status": "ready",
    }