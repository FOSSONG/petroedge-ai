from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ModelTask(str, Enum):
    hydrocarbon_classification = "hydrocarbon_classification"
    fluid_type_classification = "fluid_type_classification"
    reservoir_quality_classification = "reservoir_quality_classification"
    pay_zone_classification = "pay_zone_classification"
    lithology_classification = "lithology_classification"
    facies_classification = "facies_classification"
    porosity_regression = "porosity_regression"
    permeability_regression = "permeability_regression"
    water_saturation_regression = "water_saturation_regression"
    anomaly_detection = "anomaly_detection"
    sequence_interpretation = "sequence_interpretation"


class ModelStage(str, Enum):
    draft = "draft"
    training = "training"
    candidate = "candidate"
    validated = "validated"
    staging = "staging"
    production = "production"
    deprecated = "deprecated"
    failed = "failed"
    archived = "archived"


class ModelManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model_id: str = Field(min_length=3, max_length=160, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=2, max_length=200)
    task: ModelTask
    algorithm: str
    framework: str
    version: str = "1.0.0"
    stage: ModelStage = ModelStage.candidate
    artifact_path: str
    feature_schema: list[str] = Field(min_length=1)
    target_name: str | None = None
    class_labels: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    dataset_id: str | None = None
    supports_batch: bool = True
    supports_streaming: bool = True
    explainability: Literal["shap", "feature_importance", "none"] = "none"
    resource_profile: Literal["small", "medium", "large", "gpu"] = "small"
    enabled: bool = True
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InferenceRequest(BaseModel):
    task: ModelTask
    model_id: str | None = None
    records: list[dict[str, Any]] = Field(min_length=1, max_length=100_000)
    explain: bool = False
    execution_mode: Literal["auto", "single", "batch"] = "auto"


class InferenceResponse(BaseModel):
    task: ModelTask
    model_id: str
    model_version: str
    predictions: list[Any]
    probabilities: list[Any] | None = None
    explanations: list[dict[str, Any]] | None = None
    record_count: int
    latency_ms: float
    fallback_used: bool = False


class DefaultModelUpdate(BaseModel):
    task: ModelTask
    model_id: str


class PromotionRequest(BaseModel):
    stage: ModelStage


class TrainingRequest(BaseModel):
    task: ModelTask
    algorithm: Literal[
        "random_forest",
        "extra_trees",
        "hist_gradient_boosting",
        "logistic_regression",
        "linear_regression",
        "xgboost",
    ]
    dataset_path: str
    target_column: str
    feature_columns: list[str] = Field(min_length=1)
    validation_strategy: Literal["random", "grouped_by_well", "temporal"] = "grouped_by_well"
    group_column: str | None = "well_id"
    time_column: str | None = None
    test_size: float = Field(default=0.2, gt=0.05, lt=0.5)
    random_state: int = 42
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    display_name: str | None = None

    @model_validator(mode="after")
    def validate_split_columns(self) -> "TrainingRequest":
        if self.validation_strategy == "grouped_by_well" and not self.group_column:
            raise ValueError("group_column is required for grouped_by_well validation")
        if self.validation_strategy == "temporal" and not self.time_column:
            raise ValueError("time_column is required for temporal validation")
        return self


class TrainingResult(BaseModel):
    model_id: str
    artifact_path: str
    metrics: dict[str, float]
    validation_strategy: str
    rows_used: int
    train_rows: int
    test_rows: int


class ComparisonRequest(BaseModel):
    task: ModelTask
    model_ids: list[str] = Field(min_length=2, max_length=10)
    records: list[dict[str, Any]] = Field(min_length=1, max_length=25_000)