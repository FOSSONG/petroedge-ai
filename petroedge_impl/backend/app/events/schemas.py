from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventSeverity(str, Enum):
    info = "info"
    advisory = "advisory"
    warning = "warning"
    critical = "critical"


class EventSource(str, Enum):
    api = "api"
    websocket = "websocket"
    replay = "replay"
    workflow = "workflow"
    model = "model"
    agent = "agent"
    sensor = "sensor"
    system = "system"


class Event(BaseModel):
    model_config = ConfigDict(extra="allow")

    event_id: str
    event_type: str
    source: EventSource = EventSource.api
    asset_id: str | None = None
    reservoir_id: str | None = None
    well_id: str | None = None
    severity: EventSeverity = EventSeverity.info
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=utc_now)
    received_at: datetime = Field(default_factory=utc_now)
    correlation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventCreate(BaseModel):
    event_type: str
    source: EventSource = EventSource.api
    asset_id: str | None = None
    reservoir_id: str | None = None
    well_id: str | None = None
    severity: EventSeverity = EventSeverity.info
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventDelivery(BaseModel):
    event: Event
    matched_rules: list[str] = Field(default_factory=list)
    alert_ids: list[str] = Field(default_factory=list)
    twin_updated: bool = False
    delivered_at: datetime = Field(default_factory=utc_now)