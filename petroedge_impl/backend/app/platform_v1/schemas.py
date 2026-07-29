from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class DatasetSummary(BaseModel):
    dataset_id: str
    name: str
    description: str | None = None
    source_type: str
    file_name: str
    file_size_bytes: int
    row_count: int | None = None
    column_count: int | None = None
    columns: list[str] = Field(default_factory=list)
    missing_values: dict[str, int] = Field(default_factory=dict)
    status: str
    owner_id: str | None = None
    created_at: str
    updated_at: str


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

