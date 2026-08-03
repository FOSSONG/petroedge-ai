from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class DatasetSummary(BaseModel):
    dataset_id: str
    version_id: str
    version_number: int = 1
    parent_dataset_id: str | None = None
    root_dataset_id: str
    dataset_type: str
    name: str
    description: str | None = None
    source_type: str
    file_name: str
    file_size_bytes: int
    checksum_sha256: str
    row_count: int | None = None
    column_count: int | None = None
    columns: list[str] = Field(default_factory=list)
    missing_values: dict[str, int] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    processing: dict[str, Any] = Field(default_factory=dict)
    field_name: str | None = None
    well_name: str | None = None
    reservoir_name: str | None = None
    status: str
    owner_id: str | None = None
    created_at: str
    updated_at: str


class DatasetLineageNode(BaseModel):
    dataset: DatasetSummary
    parents: list[str] = Field(default_factory=list)
    children: list[str] = Field(default_factory=list)
    operations: list[dict[str, Any]] = Field(default_factory=list)


class LasProcessRequest(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    null_values: list[float] = Field(default_factory=lambda: [-999.25, -999.0, -9999.0])
    interpolate_limit: int = Field(default=3, ge=0, le=50)
    normalise_mnemonics: bool = True
    harmonise_units: bool = True


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    task: str = Field(min_length=2, max_length=100)
    dataset_id: str | None = None
    algorithm: str = Field(min_length=2, max_length=100)
    model_id: str | None = None
    status: Literal["queued", "running", "completed", "failed", "cancelled"] = "queued"
    parameters: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    training_seconds: float | None = Field(default=None, ge=0)
    model_size_bytes: int | None = Field(default=None, ge=0)
    validation_strategy: str | None = None
    progress_percent: int = Field(default=0, ge=0, le=100)
    current_stage: str | None = None
    error_message: str | None = None


class ExperimentSummary(ExperimentCreate):
    experiment_id: str
    owner_id: str | None = None
    created_at: str
    updated_at: str


class PlatformOverview(BaseModel):
    version: str
    datasets: int
    experiments: int
    completed_experiments: int
    registered_models: int
    production_models: int
    capabilities: list[str]

class DatasetPreview(BaseModel):
    dataset_id: str
    columns: list[str]
    rows: list[dict[str, Any]]
    total_rows: int


class DatasetPreparationRequest(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    null_values: list[float] = Field(default_factory=lambda: [-999.25, -999.0, -9999.0, -99999.0])
    zero_as_null_columns: list[str] = Field(default_factory=list)
    depth_column: str | None = None
    interpolate_limit: int = Field(default=3, ge=0, le=50)
    despike: bool = True
    smooth: bool = False
    clip_physical_ranges: bool = False
    scaling: Literal["none", "standard", "minmax", "robust"] = "none"
    scaling_columns: list[str] = Field(default_factory=list)

class DatasetEditRequest(BaseModel):
    operations: list[dict[str, Any]] = Field(default_factory=list)
    name: str | None = Field(default=None, max_length=160)

class DatasetQualityReport(BaseModel):
    dataset_id: str
    blocking_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unit_warnings: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    column_quality: list[dict[str, Any]] = Field(default_factory=list)
    ready_for_training: bool = True
