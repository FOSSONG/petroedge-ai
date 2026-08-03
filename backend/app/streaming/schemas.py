from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.events.schemas import EventCreate


class TelemetryBatch(BaseModel):
    reservoir_id: str
    well_id: str | None = None
    rows: list[dict[str, Any]]
    event_type: str = "telemetry.batch"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReplayRequest(BaseModel):
    events: list[EventCreate]
    speed: float = Field(default=1.0, gt=0.0, le=100.0)
    interval_seconds: float = Field(default=1.0, ge=0.0, le=60.0)