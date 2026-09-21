from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.ml_platform.schemas import ModelManifest, ModelStage, ModelTask

BACKEND_ROOT = Path(__file__).resolve().parents[2]
MODEL_STORE = BACKEND_ROOT / "model_store"
REGISTRY_PATH = MODEL_STORE / "registry.json"
DEFAULTS_PATH = MODEL_STORE / "defaults.json"


class ModelRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        MODEL_STORE.mkdir(parents=True, exist_ok=True)
        self._ensure_seed_registry()

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.is_file():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default

    def _write_json(self, path: Path, payload: Any) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    def _ensure_seed_registry(self) -> None:
        existing = self._read_json(REGISTRY_PATH, {})

        required_model_ids = {
            "hydrocarbon-xgb-v1",
            "lithology-rf-v1",
        }

        # Keep an existing registry only when all required seed models
        # are already registered.
        if (
            isinstance(existing, dict)
            and required_model_ids.issubset(existing.keys())
        ):
            return
        features = [
            "gamma_ray_api",
            "resistivity_ohmm",
            "density_gcc",
            "neutron_porosity_vv",
            "sonic_usft",
            "caliper_in",
        ]
        seeds: dict[str, dict[str, Any]] = {}
        hydrocarbon = BACKEND_ROOT / "models" / "hydrocarbon_xgb.pkl"
        lithology = BACKEND_ROOT / "models" / "lithology_rf.pkl"
        if hydrocarbon.is_file():
            seeds["hydrocarbon-xgb-v1"] = ModelManifest(
                model_id="hydrocarbon-xgb-v1",
                display_name="Hydrocarbon XGBoost",
                task=ModelTask.hydrocarbon_classification,
                algorithm="XGBClassifier",
                framework="xgboost",
                version="1.0.0",
                stage=ModelStage.production,
                artifact_path="models/hydrocarbon_xgb.pkl",
                feature_schema=features,
                class_labels=["non_hydrocarbon", "hydrocarbon"],
                explainability="shap",
                resource_profile="small",
            ).model_dump(mode="json")
        if lithology.is_file():
            seeds["lithology-rf-v1"] = ModelManifest(
                model_id="lithology-rf-v1",
                display_name="Lithology Random Forest",
                task=ModelTask.lithology_classification,
                algorithm="RandomForestClassifier",
                framework="scikit-learn/joblib",
                version="1.0.0",
                stage=ModelStage.production,
                artifact_path="models/lithology_rf.pkl",
                feature_schema=features,
                explainability="feature_importance",
                resource_profile="large",
            ).model_dump(mode="json")
        self._write_json(REGISTRY_PATH, seeds)
        defaults: dict[str, str] = {}
        if "hydrocarbon-xgb-v1" in seeds:
            defaults[ModelTask.hydrocarbon_classification.value] = "hydrocarbon-xgb-v1"
        if "lithology-rf-v1" in seeds:
            defaults[ModelTask.lithology_classification.value] = "lithology-rf-v1"
        self._write_json(DEFAULTS_PATH, defaults)

    def list(self, task: ModelTask | None = None, include_disabled: bool = False) -> list[ModelManifest]:
        with self._lock:
            payload = self._read_json(REGISTRY_PATH, {})
        manifests = [ModelManifest.model_validate(value) for value in payload.values()]
        if task is not None:
            manifests = [model for model in manifests if model.task == task]
        if not include_disabled:
            manifests = [model for model in manifests if model.enabled]
        return sorted(manifests, key=lambda model: (model.task.value, model.display_name, model.version))

    def get(self, model_id: str) -> ModelManifest:
        with self._lock:
            payload = self._read_json(REGISTRY_PATH, {})
        if model_id not in payload:
            raise KeyError(model_id)
        return ModelManifest.model_validate(payload[model_id])

    def register(self, manifest: ModelManifest, overwrite: bool = False) -> ModelManifest:
        with self._lock:
            payload = self._read_json(REGISTRY_PATH, {})
            if manifest.model_id in payload and not overwrite:
                raise ValueError(f"Model already registered: {manifest.model_id}")
            now = datetime.now(timezone.utc).isoformat()
            if manifest.created_at is None:
                manifest.created_at = now
            manifest.updated_at = now
            payload[manifest.model_id] = manifest.model_dump(mode="json")
            self._write_json(REGISTRY_PATH, payload)
        return manifest

    def set_stage(self, model_id: str, stage: ModelStage) -> ModelManifest:
        manifest = self.get(model_id)
        manifest.stage = stage
        return self.register(manifest, overwrite=True)

    def default_for(self, task: ModelTask) -> str | None:
        with self._lock:
            defaults = self._read_json(DEFAULTS_PATH, {})
        return defaults.get(task.value)

    def set_default(self, task: ModelTask, model_id: str) -> None:
        manifest = self.get(model_id)
        if manifest.task != task:
            raise ValueError(f"Model {model_id} belongs to {manifest.task.value}, not {task.value}")
        if manifest.stage not in {ModelStage.validated, ModelStage.staging, ModelStage.production}:
            raise ValueError("Only validated, staging, or production models can be defaults")
        with self._lock:
            defaults = self._read_json(DEFAULTS_PATH, {})
            defaults[task.value] = model_id
            self._write_json(DEFAULTS_PATH, defaults)

    def artifact_path(self, manifest: ModelManifest) -> Path:
        path = (BACKEND_ROOT / manifest.artifact_path).resolve()
        if BACKEND_ROOT not in path.parents and path != BACKEND_ROOT:
            raise ValueError("Model artifact path escapes the backend directory")
        return path


_registry: ModelRegistry | None = None


def get_model_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry