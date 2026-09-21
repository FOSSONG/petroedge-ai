from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str = Field(min_length=8, max_length=256)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    roles: list[str]
    user: dict[str, Any] | None = None


class CurrentUser(BaseModel):
    username: str
    roles: list[str] = Field(default_factory=list)
    full_name: str | None = None
    user_id: str | None = None


class WellLogSample(BaseModel):
    model_config = ConfigDict(extra="ignore")

    well_id: str = Field(min_length=1, max_length=150)
    depth_m: float = Field(ge=0)
    gamma_ray_api: float = Field(ge=0)
    resistivity_ohmm: float = Field(gt=0)
    density_gcc: float = Field(gt=0)
    neutron_porosity_vv: float = Field(ge=-0.15, le=1.0)
    sonic_usft: float = Field(gt=0)
    caliper_in: float = Field(gt=0)


class AnalyticsResult(BaseModel):
    input: dict[str, Any]
    qc_score: float
    hydrocarbon_probability: float
    lithology: str
    facies: str
    anomaly_score: float
    is_anomaly: bool
    porosity: float
    water_saturation: float
    shale_volume: float
    net_to_gross: float
    permeability_md: float
    explanation: dict[str, Any]


class Alert(BaseModel):
    id: str
    severity: str
    well_id: str
    message: str
    created_at: datetime
    status: str = "open"
    rule_name: str | None = None
    depth_m: float | None = None


class SourceType(str, Enum):
    las = "las"
    csv = "csv"
    ascii = "ascii"
    dlis = "dlis"
    witsml = "witsml"


class IngestionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_type: SourceType
    records_ingested: int = Field(ge=0)
    well_id: str
    preview: list[dict[str, Any]] = Field(default_factory=list)
    dataset_id: str | None = None
    message: str | None = None


class ReplayRequest(BaseModel):
    las_path: str = Field(min_length=1)
    interval_ms: int = Field(default=500, ge=10, le=60_000)
    max_records: int = Field(default=100, ge=1, le=100_000)




class WellCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    well_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    field: str = Field(min_length=1, max_length=200)
    status: Literal["active", "inactive", "suspended", "abandoned"] = "active"
    kb_m: float | None = Field(default=None, ge=0)
    total_depth_m: float | None = Field(default=None, gt=0)
    operator: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

class WellSummary(BaseModel):
    well_id: str
    field: str | None = None
    status: str = "available"
    kb_m: float | None = None
    total_depth_m: float | None = None
    sample_count: int | None = None
    source: str = "synthetic"


class ModelStatus(BaseModel):
    name: str
    version: str | None = None
    framework: str | None = None
    status: Literal["ready", "missing", "error", "unknown"] = "unknown"
    path: str | None = None
    size_bytes: int | None = None
    modified_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    service: str
    version: str
    timestamp: datetime
    checks: dict[str, Any] = Field(default_factory=dict)


class Pagination(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class AlertStatusUpdate(BaseModel):
    status: Literal["open", "acknowledged", "resolved", "dismissed"]
    note: str | None = Field(default=None, max_length=1000)


class RoleName(str, Enum):
    admin = "admin"
    geoscientist = "geoscientist"
    engineer = "engineer"
    viewer = "viewer"


class UserCreate(BaseModel):
    email: str
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=12, max_length=256)
    roles: list[RoleName] = Field(default_factory=lambda: [RoleName.viewer])

    @field_validator("roles")
    @classmethod
    def unique_roles(cls, values: list[RoleName]) -> list[RoleName]:
        return list(dict.fromkeys(values))
