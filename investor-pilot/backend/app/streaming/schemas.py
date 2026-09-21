from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.events.schemas import EventCreate


class TelemetryBatch(BaseModel):
    reservoir_id: str
    well_id: str | None = None
    rows: list[dict[str, Any]]
    event_type: str = "telemetry.batch"
    metadata: dict[str, Any] = Field(default_factory=dict)


class EdgeStreamSample(BaseModel):
    stream_id: str = Field(min_length=1, max_length=200)
    sequence: int = Field(ge=0)
    source_timestamp: datetime
    reservoir_id: str | None = None
    well_id: str | None = None
    channels: dict[str, Any] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    operational_state: str = "drilling"
    metadata: dict[str, Any] = Field(default_factory=dict)


class EdgeStreamBatch(BaseModel):
    samples: list[EdgeStreamSample] = Field(min_length=1, max_length=5000)


class ReplayRequest(BaseModel):
    events: list[EventCreate]
    speed: float = Field(default=1.0, gt=0.0, le=100.0)
    interval_seconds: float = Field(default=1.0, ge=0.0, le=60.0)
