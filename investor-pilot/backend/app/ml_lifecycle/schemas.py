from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, model_validator


class Algorithm(str, Enum):
    random_forest = "random_forest"
    xgboost = "xgboost"
    ann = "ann"


class TaskType(str, Enum):
    regression = "regression"
    classification = "classification"


class ValidationStrategy(str, Enum):
    random = "random"
    grouped = "grouped"
    temporal = "temporal"


class ModelStage(str, Enum):
    candidate = "candidate"
    validated = "validated"
    staging = "staging"
    production = "production"
    archived = "archived"


class TrainingConfig(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    dataset_id: str = Field(min_length=1)
    algorithm: Algorithm
    task_type: TaskType
    target_column: str = Field(min_length=1)
    feature_columns: list[str] = Field(min_length=1)
    validation_strategy: ValidationStrategy = ValidationStrategy.random
    group_column: str | None = None
    time_column: str | None = None
    test_size: float = Field(default=0.2, gt=0.05, lt=0.5)
    random_seed: int = 42
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    parent_model_id: str | None = None

    @model_validator(mode="after")
    def validate_strategy_columns(self):
        if self.validation_strategy == ValidationStrategy.grouped and not self.group_column:
            raise ValueError("group_column is required for grouped validation")
        if self.validation_strategy == ValidationStrategy.temporal and not self.time_column:
            raise ValueError("time_column is required for temporal validation")
        return self


class TrainingResult(BaseModel):
    model_id: str
    version: int
    stage: ModelStage
    metrics: dict[str, Any]
    artefact_path: str
    manifest_path: str
    configuration_hash: str
    rows_used: int
    training_rows: int
    validation_rows: int


class PredictionRequest(BaseModel):
    dataset_id: str
    model_id: str
    output_column: str | None = None


class BuiltinPredictionRequest(BaseModel):
    dataset_id: str
    algorithm: Algorithm
    task_type: TaskType
    target_column: str
    feature_columns: list[str]
    validation_strategy: ValidationStrategy = ValidationStrategy.random
    group_column: str | None = None
    time_column: str | None = None
    test_size: float = Field(default=0.2, gt=0.05, lt=0.5)
    random_seed: int = 42
    hyperparameters: dict[str, Any] = Field(default_factory=dict)


class StageUpdate(BaseModel):
    stage: ModelStage


class RetrainRequest(BaseModel):
    dataset_id: str | None = None
    display_name: str | None = None
    hyperparameters: dict[str, Any] | None = None
    deploy_after_train: bool = True
