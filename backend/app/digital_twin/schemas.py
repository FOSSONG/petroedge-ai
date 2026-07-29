from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TwinStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"
    abandoned = "abandoned"


class HealthBand(str, Enum):
    excellent = "excellent"
    good = "good"
    watch = "watch"
    poor = "poor"
    critical = "critical"


class UpdateSource(str, Enum):
    user = "user"
    workflow = "workflow"
    model = "model"
    agent = "agent"
    streaming = "streaming"
    simulation = "simulation"


class WellState(BaseModel):
    model_config = ConfigDict(extra="allow")

    well_id: str
    status: TwinStatus = TwinStatus.active
    formation: str | None = None
    depth: float | None = None
    porosity: float | None = Field(default=None, ge=0.0, le=1.0)
    permeability: float | None = Field(default=None, ge=0.0)
    water_saturation: float | None = Field(default=None, ge=0.0, le=1.0)
    oil_rate: float | None = Field(default=None, ge=0.0)
    gas_rate: float | None = Field(default=None, ge=0.0)
    water_rate: float | None = Field(default=None, ge=0.0)
    pressure: float | None = Field(default=None, ge=0.0)
    temperature: float | None = None
    lithology: str | None = None
    ai_prediction: dict[str, Any] = Field(default_factory=dict)
    agent_consensus: dict[str, Any] = Field(default_factory=dict)
    health_score: float | None = Field(default=None, ge=0.0, le=100.0)
    risk_score: float | None = Field(default=None, ge=0.0, le=100.0)
    last_updated: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReservoirState(BaseModel):
    model_config = ConfigDict(extra="allow")

    reservoir_id: str
    name: str
    field: str | None = None
    status: TwinStatus = TwinStatus.active
    wells: dict[str, WellState] = Field(default_factory=dict)
    ooip: float | None = Field(default=None, ge=0.0)
    recovery_factor: float | None = Field(default=None, ge=0.0, le=1.0)
    average_pressure: float | None = Field(default=None, ge=0.0)
    average_porosity: float | None = Field(default=None, ge=0.0, le=1.0)
    average_water_saturation: float | None = Field(default=None, ge=0.0, le=1.0)
    average_permeability: float | None = Field(default=None, ge=0.0)
    active_wells: int = Field(default=0, ge=0)
    inactive_wells: int = Field(default=0, ge=0)
    health_score: float | None = Field(default=None, ge=0.0, le=100.0)
    risk_score: float | None = Field(default=None, ge=0.0, le=100.0)
    ccus_suitability: float | None = Field(default=None, ge=0.0, le=100.0)
    forecast: dict[str, Any] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TwinCreate(BaseModel):
    reservoir_id: str
    name: str
    field: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TwinUpdate(BaseModel):
    source: UpdateSource = UpdateSource.user
    source_reference: str | None = None
    reservoir: dict[str, Any] = Field(default_factory=dict)
    wells: list[WellState] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TwinSnapshot(BaseModel):
    snapshot_id: str
    reservoir_id: str
    version: int
    source: UpdateSource
    source_reference: str | None = None
    state: ReservoirState
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthMetric(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=100.0)
    weight: float = Field(ge=0.0)
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class HealthReport(BaseModel):
    reservoir_id: str
    overall_score: float = Field(ge=0.0, le=100.0)
    risk_score: float = Field(ge=0.0, le=100.0)
    band: HealthBand
    metrics: list[HealthMetric] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class SimulationChange(BaseModel):
    path: str
    operation: str = "set"
    value: float | int | str | bool | None


class SimulationRequest(BaseModel):
    name: str = "What-if scenario"
    changes: list[SimulationChange]
    persist: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationResult(BaseModel):
    simulation_id: str
    reservoir_id: str
    name: str
    baseline_health: HealthReport
    simulated_health: HealthReport
    state: ReservoirState
    persisted: bool
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)