from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    las = "LAS"
    dlis = "DLIS"
    csv = "CSV"
    ascii = "ASCII"
    witsml = "WITSML"


class LoginRequest(BaseModel):
    username: str
    password: str
    mfa_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    roles: list[str]


class WellLogSample(BaseModel):
    well_id: str = "PETROEDGE-DEMO-01"
    timestamp: datetime | None = None
    depth_m: float
    gamma_ray_api: float = Field(..., ge=0)
    resistivity_ohmm: float = Field(..., gt=0)
    density_gcc: float = Field(..., gt=0)
    neutron_porosity_vv: float = Field(..., ge=-0.15, le=0.8)
    sonic_usft: float = Field(..., gt=0)
    caliper_in: float = Field(8.5, gt=0)


class AnalyticsResult(BaseModel):
    input: WellLogSample
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
    explanation: dict[str, float | str]


class IngestionResponse(BaseModel):
    source_type: SourceType
    records_ingested: int
    well_id: str
    preview: list[dict[str, Any]]


class Alert(BaseModel):
    id: str
    severity: str
    well_id: str
    message: str
    created_at: datetime
    acknowledged: bool = False


class ReplayRequest(BaseModel):
    las_path: str = "data/sample_well.las"
    interval_ms: int = Field(250, ge=50, le=10000)
    max_records: int = Field(200, ge=1, le=10000)

