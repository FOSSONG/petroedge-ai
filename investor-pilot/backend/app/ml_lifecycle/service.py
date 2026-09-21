from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.ml_lifecycle.schemas import (
    Algorithm,
    ModelStage,
    TaskType,
    TrainingConfig,
    TrainingResult,
    ValidationStrategy,
)
from app.core.ownership import owner_id as request_owner, require_owner, visible
from app.platform_v1.datasets import get_dataset_path
from app.ml_lifecycle.prepared import load_prepared, locked_partitions

BACKEND_ROOT = Path(__file__).resolve().parents[2]
STORE_ROOT = BACKEND_ROOT / "model_store" / "lifecycle"
REGISTRY_PATH = STORE_ROOT / "registry.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_registry() -> dict[str, Any]:
    STORE_ROOT.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_PATH.is_file():
        return {}
    try:
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_registry(payload: dict[str, Any]) -> None:
    STORE_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(REGISTRY_PATH)


def _load_dataset(dataset_id: str) -> pd.DataFrame:
    path = get_dataset_path(dataset_id)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".las":
        import lasio
        return lasio.read(path).df().reset_index()
    raise ValueError(f"Unsupported training dataset type: {suffix}")


def algorithm_catalog() -> list[dict[str, Any]]:
    try:
        import xgboost
        xgb_available = True
        xgb_version = xgboost.__version__
    except Exception as exc:
        xgb_available = False
        xgb_version = None
        xgb_error = str(exc)
    return [
        {
            "algorithm": "random_forest",
            "display_name": "Random Forest",
            "available": True,
            "engine": "scikit-learn",
            "cpu_ready": True,
            "supports": ["regression", "classification"],
        },
        {
            "algorithm": "xgboost",
            "display_name": "XGBoost",
            "available": xgb_available,
            "engine": "xgboost",
            "engine_version": xgb_version,
            "cpu_ready": True,
            "supports": ["regression", "classification"],
            "unavailable_reason": None if xgb_available else f"XGBoost failed to load: {xgb_error}",
        },
        {
            "algorithm": "ann",
            "display_name": "Artificial Neural Network",
            "available": True,
            "engine": "scikit-learn MLP",
            "cpu_ready": True,
            "supports": ["regression", "classification"],
        },
    ]


def _build_estimator(config: TrainingConfig):
    params = dict(config.hyperparameters)
    classification = config.task_type == TaskType.classification

    if config.algorithm == Algorithm.random_forest:
        params.setdefault("n_estimators", 240)
        params.setdefault("max_depth", 18)
        params.setdefault("min_samples_leaf", 2)
        params.setdefault("n_jobs", -1)
        params.setdefault("random_state", config.random_seed)
        return RandomForestClassifier(**params) if classification else RandomForestRegressor(**params)

    if config.algorithm == Algorithm.xgboost:
        try:
            from xgboost import XGBClassifier, XGBRegressor
        except ImportError as exc:
            raise RuntimeError("XGBoost is unavailable. Install xgboost in the backend image.") from exc
        params.setdefault("n_estimators", 350)
        params.setdefault("max_depth", 6)
        params.setdefault("learning_rate", 0.05)
        params.setdefault("subsample", 0.9)
        params.setdefault("colsample_bytree", 0.9)
        params.setdefault("tree_method", "hist")
        params.setdefault("n_jobs", max(1, (os.cpu_count() or 2) - 1))
        params.setdefault("random_state", config.random_seed)
        if classification:
            params.setdefault("eval_metric", "logloss")
            return XGBClassifier(**params)
        params.setdefault("objective", "reg:squarederror")
        return XGBRegressor(**params)

    if config.algorithm == Algorithm.ann:
        params.setdefault("hidden_layer_sizes", (64, 32))
        params.setdefault("activation", "relu")
        params.setdefault("solver", "adam")
        params.setdefault("early_stopping", False)
        if params["early_stopping"] and config.validation_strategy != ValidationStrategy.random:
            raise ValueError("ANN random early stopping is incompatible with grouped or temporal validation.")
        params.setdefault("validation_fraction", 0.15)
        params.setdefault("max_iter", 600)
        params.setdefault("random_state", config.random_seed)
        return MLPClassifier(**params) if classification else MLPRegressor(**params)

    raise ValueError(f"Unsupported algorithm: {config.algorithm}")


def _split(frame: pd.DataFrame, config: TrainingConfig):
    if config.validation_strategy == ValidationStrategy.grouped:
        if config.group_column not in frame:
            raise ValueError(f"Grouped validation column not found: {config.group_column}")
        groups = frame[config.group_column]
        if groups.nunique(dropna=True) < 2:
            raise ValueError("Grouped validation requires at least two distinct groups.")
        splitter = GroupShuffleSplit(
            n_splits=1,
            test_size=config.test_size,
            random_state=config.random_seed,
        )
        train_idx, test_idx = next(splitter.split(frame, groups=groups))
        return frame.iloc[train_idx], frame.iloc[test_idx]

    if config.validation_strategy == ValidationStrategy.temporal:
        if config.time_column not in frame:
            raise ValueError(f"Temporal validation column not found: {config.time_column}")
        ordered = frame.sort_values(config.time_column, kind="stable")
        cut = max(2, min(len(ordered) - 2, int(len(ordered) * (1 - config.test_size))))
        # Purge a small boundary window so immediately adjacent depth/time samples
        # cannot appear on opposite sides of the validation boundary.
        purge = max(1, min(100, int(len(ordered) * 0.01)))
        train_end = max(1, cut - purge)
        validation_start = min(len(ordered) - 1, cut + purge)
        train_part = ordered.iloc[:train_end]
        validation_part = ordered.iloc[validation_start:]
        if len(train_part) < 10 or len(validation_part) < 5:
            raise ValueError("Temporal validation has too few rows after applying the leakage purge gap.")
        return train_part, validation_part

    stratify = None
    if config.task_type == TaskType.classification:
        counts = frame[config.target_column].value_counts()
        if len(counts) > 1 and counts.min() >= 2:
            stratify = frame[config.target_column]
    return train_test_split(
        frame,
        test_size=config.test_size,
        random_state=config.random_seed,
        stratify=stratify,
    )


def _metrics(y_true, predictions, task_type: TaskType) -> dict[str, float]:
    if task_type == TaskType.classification:
        return {
            "accuracy": float(accuracy_score(y_true, predictions)),
            "precision_weighted": float(precision_score(y_true, predictions, average="weighted", zero_division=0)),
            "recall_weighted": float(recall_score(y_true, predictions, average="weighted", zero_division=0)),
            "f1_weighted": float(f1_score(y_true, predictions, average="weighted", zero_division=0)),
        }
    return {
        "mae": float(mean_absolute_error(y_true, predictions)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, predictions))),
        "r2": float(r2_score(y_true, predictions)) if len(y_true) > 1 else 0.0,
    }


def _configuration_hash(config: TrainingConfig) -> str:
    serialised = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def _next_version(display_name: str) -> int:
    matches = [
        int(item.get("version", 0))
        for item in _read_registry().values()
        if item.get("display_name") == display_name and visible(item.get("owner_id"))
    ]
    return max(matches, default=0) + 1


def train_and_register(config: TrainingConfig) -> TrainingResult:
    owner = request_owner()
    if config.parent_model_id:
        get_model(config.parent_model_id)
    frame = load_prepared(config) if config.dataset_id.startswith("prepared:") else _load_dataset(config.dataset_id)
    contract = frame.attrs.get("prepared_contract")
    if "split_group_id" in frame and not contract:
        raise ValueError("Qualified parent-well datasets require a server-approved prepared contract and locked split.")
    # Prepared contracts already contain qualified finite values. Applying legacy
    # sentinels here would make training differ from independent evaluation.
    if not contract:
        frame = frame.replace([-999.25, -999.0, -9999.0, -99999.0, 999.25, 9999.0, np.inf, -np.inf], np.nan)

    if len(set(config.feature_columns)) != len(config.feature_columns):
        raise ValueError("Feature columns must be unique.")
    if config.target_column in config.feature_columns:
        raise ValueError("Data leakage blocked: the target column cannot also be a feature.")
    if config.group_column and config.group_column in config.feature_columns:
        raise ValueError("Data leakage blocked: the grouping identifier cannot be used as a predictor.")
    if config.time_column and config.time_column in config.feature_columns:
        raise ValueError("Data leakage blocked: the temporal ordering column cannot be used as a predictor in this workflow.")

    # Multi-well petrophysical rows are strongly autocorrelated. A random row split
    # would place samples from the same well in both train and validation sets.
    normalised = {re.sub(r"[^A-Z0-9]", "", str(c).upper()): c for c in frame.columns}
    identity_aliases = {"WELL", "WELLID", "WELLNAME", "UWI", "API", "BOREHOLE", "BOREHOLEID"}
    detected_identity = next((normalised[key] for key in identity_aliases if key in normalised), None)
    if config.validation_strategy == ValidationStrategy.random and detected_identity:
        distinct = frame[detected_identity].nunique(dropna=True)
        if distinct > 1:
            raise ValueError(
                f"Unsafe random row validation blocked: dataset contains {distinct} wells in '{detected_identity}'. "
                "Use grouped validation with that column to prevent same-well leakage."
            )

    required = list(dict.fromkeys([*config.feature_columns, config.target_column]))
    for optional in [config.group_column, config.time_column]:
        if optional:
            required.append(optional)
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Dataset columns missing: {', '.join(missing)}")

    frame = frame.replace([np.inf, -np.inf], np.nan)
    frame = frame.dropna(subset=[config.target_column]).copy()
    if len(frame) < 20:
        raise ValueError("At least 20 rows with a valid target are required.")

    test_frame = None
    if contract:
        # Never silently drop qualified target rows or use test values for preprocessing.
        if len(frame) != contract["rows"]:
            raise ValueError("Prepared target rows changed after cleaning; requalify the dataset.")
        train_frame, validation_frame, test_frame = locked_partitions(frame, contract["assignments"])
        if len(train_frame) < 10 or len(validation_frame) < 5 or len(test_frame) < 5:
            raise ValueError("Locked split requires at least 10 training, 5 validation and 5 test rows.")
    else:
        train_frame, validation_frame = _split(frame, config)
    numeric_features = list(config.feature_columns)
    pipeline_steps = [
        ("imputer", SimpleImputer(strategy="median")),
    ]
    if config.algorithm == Algorithm.ann:
        pipeline_steps.append(("scaler", StandardScaler()))
    pipeline_steps.append(("estimator", _build_estimator(config)))
    pipeline = Pipeline(pipeline_steps)

    non_numeric = [column for column in numeric_features if not pd.api.types.is_numeric_dtype(frame[column])]
    if non_numeric:
        raise ValueError(
            "Only numeric predictor columns are supported in this Release 3 workflow: "
            + ", ".join(non_numeric)
        )

    pipeline.fit(train_frame[numeric_features], train_frame[config.target_column])
    train_predictions = pipeline.predict(train_frame[numeric_features])
    predictions = pipeline.predict(validation_frame[numeric_features])
    train_metrics = _metrics(train_frame[config.target_column], train_predictions, config.task_type)
    validation_metrics = _metrics(validation_frame[config.target_column], predictions, config.task_type)
    metrics = {f"train_{key}": value for key, value in train_metrics.items()}
    metrics.update({f"validation_{key}": value for key, value in validation_metrics.items()})
    if config.task_type == TaskType.regression:
        metrics["generalisation_gap"] = float(train_metrics["r2"] - validation_metrics["r2"])
    else:
        metrics["generalisation_gap"] = float(train_metrics["accuracy"] - validation_metrics["accuracy"])
    metrics["overfitting_warning"] = float(metrics["generalisation_gap"] > 0.15)

    version = _next_version(config.display_name)
    slug = re.sub(r"[^a-z0-9]+", "-", config.display_name.lower()).strip("-") or "model"
    model_id = f"{slug}-v{version}-{uuid4().hex[:8]}"
    model_dir = STORE_ROOT / model_id
    model_dir.mkdir(parents=True, exist_ok=False)
    artefact = model_dir / "model.joblib"
    manifest_file = model_dir / "manifest.json"
    config_file = model_dir / "training-config.json"

    joblib.dump(pipeline, artefact, compress=3)
    config_file.write_text(
        json.dumps(config.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    config_hash = _configuration_hash(config)
    manifest = {
        "model_id": model_id,
        "owner_id": owner,
        "display_name": config.display_name,
        "version": version,
        "stage": ModelStage.candidate.value,
        "algorithm": config.algorithm.value,
        "task_type": config.task_type.value,
        "dataset_id": config.dataset_id,
        "target_column": config.target_column,
        "feature_columns": config.feature_columns,
        "validation_strategy": config.validation_strategy.value,
        "group_column": config.group_column,
        "time_column": config.time_column,
        "test_size": config.test_size,
        "random_seed": config.random_seed,
        "hyperparameters": config.hyperparameters,
        "metrics": metrics,
        "rows_used": len(frame),
        "independent_test_rows": len(test_frame) if test_frame is not None else 0,
        "independent_test_status": "reserved_not_evaluated" if contract else "not_reserved",
        "prepared_contract": contract,
        "training_rows": len(train_frame),
        "validation_rows": len(validation_frame),
        "artefact_path": str(artefact.relative_to(BACKEND_ROOT)).replace("\\", "/"),
        "manifest_path": str(manifest_file.relative_to(BACKEND_ROOT)).replace("\\", "/"),
        "configuration_path": str(config_file.relative_to(BACKEND_ROOT)).replace("\\", "/"),
        "configuration_hash": config_hash,
        "artefact_sha256": hashlib.sha256(artefact.read_bytes()).hexdigest(),
        "artefact_size_bytes": artefact.stat().st_size,
        "parent_model_id": config.parent_model_id,
        "retrained_at": _utcnow() if config.parent_model_id else None,
        "validated_at": None,
        "deployed_at": None,
        "software": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "scikit_learn": sklearn.__version__,
        },
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
    }
    manifest_file.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    registry = _read_registry()
    registry[model_id] = manifest
    _write_registry(registry)

    return TrainingResult(
        model_id=model_id,
        version=version,
        stage=ModelStage.candidate,
        metrics=metrics,
        artefact_path=manifest["artefact_path"],
        manifest_path=manifest["manifest_path"],
        configuration_hash=config_hash,
        rows_used=len(frame),
        training_rows=len(train_frame),
        validation_rows=len(validation_frame),
    )


def list_models() -> list[dict[str, Any]]:
    values = [item for item in _read_registry().values() if visible(item.get("owner_id"))]
    return sorted(values, key=lambda item: item.get("created_at", ""), reverse=True)


def get_model(model_id: str) -> dict[str, Any]:
    registry = _read_registry()
    if model_id not in registry:
        raise KeyError(model_id)
    require_owner(registry[model_id].get("owner_id"))
    return registry[model_id]


def delete_model(model_id: str) -> dict[str, Any]:
    registry = _read_registry()
    if model_id not in registry:
        raise KeyError(model_id)

    manifest = registry[model_id]
    require_owner(manifest.get("owner_id"))
    model_dir = (STORE_ROOT / model_id).resolve()
    store_root = STORE_ROOT.resolve()
    if model_dir.parent != store_root:
        raise RuntimeError("Refusing to delete a model outside the lifecycle model store.")

    # Update the registry first through its atomic writer. If artefact deletion fails,
    # restore the entry so registry state and disk state cannot silently diverge.
    del registry[model_id]
    _write_registry(registry)
    try:
        if model_dir.exists():
            shutil.rmtree(model_dir)
    except OSError:
        registry[model_id] = manifest
        _write_registry(registry)
        raise

    return {
        "model_id": model_id,
        "display_name": manifest.get("display_name", model_id),
        "version": manifest.get("version"),
        "deleted": True,
    }


def update_stage(model_id: str, stage: ModelStage) -> dict[str, Any]:
    registry = _read_registry()
    if model_id not in registry:
        raise KeyError(model_id)

    require_owner(registry[model_id].get("owner_id"))
    if registry[model_id].get("prepared_contract") and stage in {ModelStage.validated, ModelStage.staging, ModelStage.production}:
        if stage != ModelStage.validated:
            raise ValueError("Prepared model production/staging promotion requires operational approval, which is not implemented.")
        from app.ml_lifecycle.evaluation import require_passed_evaluation
        require_passed_evaluation(model_id)
    timestamp = _utcnow()
    if stage == ModelStage.production:
        task = registry[model_id]["task_type"]
        target = registry[model_id]["target_column"]
        for item in registry.values():
            if (
                item["model_id"] != model_id
                and item.get("owner_id") == registry[model_id].get("owner_id")
                and item.get("stage") == ModelStage.production.value
                and item.get("task_type") == task
                and item.get("target_column") == target
            ):
                item["stage"] = ModelStage.staging.value
                item["updated_at"] = timestamp
        registry[model_id]["deployed_at"] = timestamp

    if stage == ModelStage.validated:
        registry[model_id]["validated_at"] = timestamp

    registry[model_id]["stage"] = stage.value
    registry[model_id]["updated_at"] = timestamp
    _write_registry(registry)

    manifest_path = BACKEND_ROOT / registry[model_id]["manifest_path"]
    if manifest_path.is_file():
        manifest_path.write_text(
            json.dumps(registry[model_id], indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return registry[model_id]


def _prediction_inputs(manifest, frame):
    features = manifest["feature_columns"]
    missing = [c for c in features if c not in frame.columns]
    numeric = frame.reindex(columns=features).apply(pd.to_numeric, errors="coerce")
    numeric = numeric.replace([-999.25, -999.0, -9999.0, -99999.0, 999.25, 9999.0, np.inf, -np.inf], np.nan)
    invalid = {c: int(numeric[c].isna().sum()) for c in features}
    absent = [c for c in features if len(numeric) and numeric[c].isna().all() and c not in missing]
    complete = int(numeric.notna().all(axis=1).sum())
    ready = bool(len(frame)) and not missing and complete == len(frame)
    messages = []
    if missing: messages.append("Missing required columns: " + ", ".join(missing) + ". Resolve aliases/units in LAS Wizard or select a separately evaluated reduced-input model.")
    if absent: messages.append("No usable measurements in: " + ", ".join(absent) + ". An entirely missing curve is not supported.")
    if complete < len(frame): messages.append(f"{len(frame)-complete} rows have missing, non-numeric or null-marker inputs. Prepare a reviewed copy before prediction; automatic imputation is not approved by this check.")
    if not len(frame): messages.append("The dataset has no rows.")
    return numeric, {"ready": ready, "required_features": features, "missing_columns": missing, "empty_columns": absent, "invalid_counts": invalid, "total_rows": len(frame), "complete_rows": complete, "messages": messages, "policy": "Exact trained column names and complete numeric inputs required. No automatic model substitution or imputation. This check does not certify units, physical validity or model performance."}


def prediction_compatibility(model_id: str, dataset_id: str):
    manifest = get_model(model_id)
    _, report = _prediction_inputs(manifest, _load_dataset(dataset_id))
    return {"model_id": model_id, "dataset_id": dataset_id, **report}


def predict_dataset(model_id: str, dataset_id: str, output_column: str | None = None) -> dict[str, Any]:
    manifest = get_model(model_id)
    frame = _load_dataset(dataset_id)
    frame = frame.replace([-999.25, -999.0, -9999.0, -99999.0, 999.25, 9999.0, np.inf, -np.inf], np.nan)
    features = manifest["feature_columns"]
    numeric, compatibility = _prediction_inputs(manifest, frame)
    if not compatibility["ready"]:
        raise ValueError(" ".join(compatibility["messages"]))
    artefact = (BACKEND_ROOT / manifest["artefact_path"]).resolve()
    if not artefact.is_file():
        raise FileNotFoundError(f"Model artefact missing: {artefact}")
    model = joblib.load(artefact)
    predictions = model.predict(numeric[features])
    column = output_column or f"prediction_{manifest['target_column']}"
    result = frame.copy()
    result[column] = predictions
    prediction_dir = BACKEND_ROOT / "prediction_store"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    output_path = prediction_dir / f"{dataset_id}-{model_id}-{uuid4().hex[:8]}.csv"
    result.to_csv(output_path, index=False)
    output_path.with_suffix(".owner.json").write_text(json.dumps({"owner_id":request_owner(),"model_id":model_id,"dataset_id":dataset_id}),encoding="utf-8")
    preview = result[[*features, column]].head(100).replace({np.nan: None}).to_dict(orient="records")
    return {
        "model_id": model_id,
        "dataset_id": dataset_id,
        "output_column": column,
        "row_count": len(result),
        "output_path": str(output_path.relative_to(BACKEND_ROOT)).replace("\\", "/"),
        "preview": preview,
    }


def retrain(
    model_id: str,
    dataset_id: str | None,
    display_name: str | None,
    hyperparameters: dict[str, Any] | None,
    deploy_after_train: bool = True,
):
    manifest = get_model(model_id)
    config_path = BACKEND_ROOT / manifest["configuration_path"]
    config_payload = json.loads(config_path.read_text(encoding="utf-8"))
    config_payload["dataset_id"] = dataset_id or config_payload["dataset_id"]
    config_payload["display_name"] = display_name or manifest["display_name"]
    config_payload["parent_model_id"] = model_id
    if hyperparameters is not None:
        config_payload["hyperparameters"] = hyperparameters

    result = train_and_register(TrainingConfig.model_validate(config_payload))
    if not deploy_after_train:
        return result

    update_stage(result.model_id, ModelStage.production)
    return TrainingResult(
        model_id=result.model_id,
        version=result.version,
        stage=ModelStage.production,
        metrics=result.metrics,
        artefact_path=result.artefact_path,
        manifest_path=result.manifest_path,
        configuration_hash=result.configuration_hash,
        rows_used=result.rows_used,
        training_rows=result.training_rows,
        validation_rows=result.validation_rows,
    )


def prediction_output_path(output_name: str) -> Path:
    safe = Path(output_name).name
    if safe != output_name or not safe.lower().endswith(".csv"):
        raise ValueError("Invalid prediction output name.")
    root = BACKEND_ROOT / "prediction_store"
    path = (root / safe).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise FileNotFoundError("Prediction output not found.")
    sidecar=path.with_suffix(".owner.json")
    metadata=json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.is_file() else {}
    require_owner(metadata.get("owner_id"))
    return path
