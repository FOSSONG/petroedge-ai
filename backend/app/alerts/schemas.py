from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AlertSeverity(str, Enum):
    information = "information"
    advisory = "advisory"
    warning = "warning"
    critical = "critical"


class AlertStatus(str, Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"


class Alert(BaseModel):
    alert_id: str
    title: str
    message: str
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.open
    source_event_id: str | None = None
    rule_id: str | None = None
    asset_id: str | None = None
    reservoir_id: str | None = None
    well_id: str | None = None
    recommended_action: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    acknowledged_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AlertUpdate(BaseModel):
    status: AlertStatus
    actor: str | None = None
    note: str | None = None