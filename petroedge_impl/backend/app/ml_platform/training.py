from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error, precision_score, r2_score, recall_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split

from app.ml_platform.registry import BACKEND_ROOT, get_model_registry
from app.ml_platform.schemas import ModelManifest, ModelStage, ModelTask, TrainingRequest, TrainingResult

DATASET_STORE = BACKEND_ROOT / "dataset_store"
MODEL_STORE = BACKEND_ROOT / "model_store"
EXPERIMENT_STORE = BACKEND_ROOT / "experiment_store"


def _safe_dataset_path(relative_path: str) -> Path:
    candidate = (DATASET_STORE / relative_path).resolve()
    if DATASET_STORE.resolve() not in candidate.parents:
        raise ValueError("dataset_path must point inside backend/dataset_store")
    if not candidate.is_file():
        raise FileNotFoundError(f"Dataset not found: {candidate}")
    if candidate.suffix.lower() not in {".csv", ".parquet"}:
        raise ValueError("Only CSV and Parquet datasets are supported in the MVP")
    return candidate


def _read_dataset(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)


def _classification_task(task: ModelTask) -> bool:
    return task in {
        ModelTask.hydrocarbon_classification,
        ModelTask.fluid_type_classification,
        ModelTask.reservoir_quality_classification,
        ModelTask.pay_zone_classification,
        ModelTask.lithology_classification,
        ModelTask.facies_classification,
        ModelTask.anomaly_detection,
    }


def _build_estimator(request: TrainingRequest, classification: bool):
    params = dict(request.hyperparameters)
    params.setdefault("random_state", request.random_state)
    params.setdefault("n_jobs", -1)
    if request.algorithm == "random_forest":
        cls = RandomForestClassifier if classification else RandomForestRegressor
        params.setdefault("n_estimators", 200)
        params.setdefault("max_depth", 16)
        return cls(**params)
    if request.algorithm == "extra_trees":
        cls = ExtraTreesClassifier if classification else ExtraTreesRegressor
        params.setdefault("n_estimators", 200)
        params.setdefault("max_depth", 16)
        return cls(**params)
    if request.algorithm == "hist_gradient_boosting":
        params.pop("n_jobs", None)
        cls = HistGradientBoostingClassifier if classification else HistGradientBoostingRegressor
        return cls(**params)
    if request.algorithm == "logistic_regression":
        if not classification:
            raise ValueError("logistic_regression is classification-only")
        params.setdefault("max_iter", 1000)
        return LogisticRegression(**params)
    if request.algorithm == "linear_regression":
        if classification:
            raise ValueError("linear_regression is regression-only")
        params.pop("random_state", None)
        return LinearRegression(**params)
    if request.algorithm == "xgboost":
        try:
            from xgboost import XGBClassifier, XGBRegressor
        except ImportError as exc:
            raise RuntimeError("Install the tree-model dependency group to train XGBoost") from exc
        cls = XGBClassifier if classification else XGBRegressor
        params.setdefault("n_estimators", 300)
        params.setdefault("max_depth", 6)
        params.setdefault("learning_rate", 0.05)
        params.setdefault("tree_method", "hist")
        return cls(**params)
    raise ValueError(f"Unsupported algorithm: {request.algorithm}")


def _split(frame: pd.DataFrame, request: TrainingRequest):
    if request.validation_strategy == "grouped_by_well":
        if request.group_column not in frame.columns:
            raise ValueError(f"Group column not found: {request.group_column}")
        splitter = GroupShuffleSplit(n_splits=1, test_size=request.test_size, random_state=request.random_state)
        train_idx, test_idx = next(splitter.split(frame, groups=frame[request.group_column]))
        return frame.iloc[train_idx], frame.iloc[test_idx]
    if request.validation_strategy == "temporal":
        if request.time_column not in frame.columns:
            raise ValueError(f"Time column not found: {request.time_column}")
        ordered = frame.sort_values(request.time_column)
        cut = int(len(ordered) * (1.0 - request.test_size))
        return ordered.iloc[:cut], ordered.iloc[cut:]
    train, test = train_test_split(frame, test_size=request.test_size, random_state=request.random_state)
    return train, test


def _metrics(y_true, predictions, probabilities, classification: bool) -> dict[str, float]:
    if classification:
        output = {
            "accuracy": float(accuracy_score(y_true, predictions)),
            "precision_weighted": float(precision_score(y_true, predictions, average="weighted", zero_division=0)),
            "recall_weighted": float(recall_score(y_true, predictions, average="weighted", zero_division=0)),
            "f1_weighted": float(f1_score(y_true, predictions, average="weighted", zero_division=0)),
        }
        if probabilities is not None:
            try:
                if probabilities.ndim == 2 and probabilities.shape[1] == 2:
                    output["roc_auc"] = float(roc_auc_score(y_true, probabilities[:, 1]))
                elif probabilities.ndim == 2:
                    output["roc_auc_ovr_weighted"] = float(roc_auc_score(y_true, probabilities, multi_class="ovr", average="weighted"))
            except ValueError:
                pass
        return output
    rmse = float(np.sqrt(mean_squared_error(y_true, predictions)))
    return {
        "mae": float(mean_absolute_error(y_true, predictions)),
        "rmse": rmse,
        "r2": float(r2_score(y_true, predictions)),
    }


def train_model(request: TrainingRequest) -> TrainingResult:
    path = _safe_dataset_path(request.dataset_path)
    frame = _read_dataset(path)
    required = list(dict.fromkeys([*request.feature_columns, request.target_column]))
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Dataset columns missing: {', '.join(missing)}")
    frame = frame.dropna(subset=required).copy()
    if len(frame) < 50:
        raise ValueError("At least 50 complete rows are required for training")
    train_frame, test_frame = _split(frame, request)
    classification = _classification_task(request.task)
    estimator = _build_estimator(request, classification)
    estimator.fit(train_frame[request.feature_columns], train_frame[request.target_column])
    predictions = estimator.predict(test_frame[request.feature_columns])
    probabilities = estimator.predict_proba(test_frame[request.feature_columns]) if hasattr(estimator, "predict_proba") else None
    metrics = _metrics(test_frame[request.target_column], predictions, probabilities, classification)

    suffix = uuid4().hex[:8]
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", request.display_name or f"{request.task.value}-{request.algorithm}").strip("-").lower()
    model_id = f"{stem}-{suffix}"
    task_dir = MODEL_STORE / request.task.value
    task_dir.mkdir(parents=True, exist_ok=True)
    artifact = task_dir / f"{model_id}.joblib"
    joblib.dump(estimator, artifact, compress=3)

    manifest = ModelManifest(
        model_id=model_id,
        display_name=request.display_name or f"{request.algorithm.replace('_', ' ').title()} for {request.task.value}",
        task=request.task,
        algorithm=request.algorithm,
        framework="xgboost" if request.algorithm == "xgboost" else "scikit-learn/joblib",
        version="1.0.0",
        stage=ModelStage.candidate,
        artifact_path=str(artifact.relative_to(BACKEND_ROOT)).replace("\\", "/"),
        feature_schema=request.feature_columns,
        target_name=request.target_column,
        metrics=metrics,
        dataset_id=path.name,
        explainability="shap" if request.algorithm in {"random_forest", "extra_trees", "xgboost"} else "none",
        resource_profile="small" if artifact.stat().st_size < 100_000_000 else "large",
        created_at=datetime.now(timezone.utc).isoformat(),
        metadata={
            "validation_strategy": request.validation_strategy,
            "rows_used": len(frame),
            "train_rows": len(train_frame),
            "test_rows": len(test_frame),
            "hyperparameters": request.hyperparameters,
        },
    )
    get_model_registry().register(manifest)
    experiment = EXPERIMENT_STORE / f"{model_id}.json"
    experiment.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2), encoding="utf-8")
    return TrainingResult(
        model_id=model_id,
        artifact_path=manifest.artifact_path,
        metrics=metrics,
        validation_strategy=request.validation_strategy,
        rows_used=len(frame),
        train_rows=len(train_frame),
        test_rows=len(test_frame),
    )