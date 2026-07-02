from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends

from app.core.rbac import require_roles
from app.schemas import Alert, WellLogSample
from app.services.analytics import analyze_sample

router = APIRouter()

ALERTS: list[Alert] = [
    Alert(
        id="ALT-001",
        severity="high",
        well_id="PETROEDGE-DEMO-01",
        message="Hydrocarbon probability exceeded 0.72 in clean sand interval",
        created_at=datetime.now(timezone.utc),
    )
]


@router.get("", response_model=list[Alert])
async def list_alerts(_: dict = Depends(require_roles("admin", "geoscientist", "engineer", "viewer"))) -> list[Alert]:
    return ALERTS


@router.post("/evaluate", response_model=list[Alert])
async def evaluate_alerts(
    sample: WellLogSample,
    _: dict = Depends(require_roles("admin", "geoscientist", "engineer")),
) -> list[Alert]:
    result = analyze_sample(sample)
    emitted: list[Alert] = []
    if result.hydrocarbon_probability >= 0.72:
        emitted.append(
            Alert(
                id=f"ALT-{uuid4().hex[:8].upper()}",
                severity="high",
                well_id=sample.well_id,
                message="Hydrocarbon probability threshold exceeded",
                created_at=datetime.now(timezone.utc),
            )
        )
    if result.is_anomaly:
        emitted.append(
            Alert(
                id=f"ALT-{uuid4().hex[:8].upper()}",
                severity="medium",
                well_id=sample.well_id,
                message="Anomalous log response detected",
                created_at=datetime.now(timezone.utc),
            )
        )
    ALERTS.extend(emitted)
    return emitted

