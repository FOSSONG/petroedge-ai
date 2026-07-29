from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.ml_platform.schemas import ModelManifest


class ModelAdapter(ABC):
    def __init__(self, manifest: ModelManifest, artifact_path: Path):
        self.manifest = manifest
        self.artifact_path = artifact_path
        self.model: Any | None = None

    @abstractmethod
    def load(self) -> None: ...

    def unload(self) -> None:
        self.model = None

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def validate_features(self, frame: pd.DataFrame) -> pd.DataFrame:
        missing = [name for name in self.manifest.feature_schema if name not in frame.columns]
        if missing:
            raise ValueError(f"Missing required model features: {', '.join(missing)}")
        selected = frame[self.manifest.feature_schema].copy()
        for column in selected.columns:
            selected[column] = pd.to_numeric(selected[column], errors="coerce")
        if selected.isna().any().any():
            invalid = selected.columns[selected.isna().any()].tolist()
            raise ValueError(f"Non-numeric or missing values in features: {', '.join(invalid)}")
        return selected

    @abstractmethod
    def predict(self, frame: pd.DataFrame) -> list[Any]: ...

    def predict_proba(self, frame: pd.DataFrame) -> list[Any] | None:
        return None

    def explain(self, frame: pd.DataFrame) -> list[dict[str, Any]] | None:
        if not self.loaded:
            self.load()
        if self.manifest.explainability == "none":
            return None
        try:
            import shap
        except ImportError:
            return [{"status": "unavailable", "reason": "SHAP is not installed"}] * len(frame)

        selected = self.validate_features(frame)
        try:
            explainer = shap.TreeExplainer(self.model)
            values = explainer.shap_values(selected)
            if isinstance(values, list):
                values = values[-1]
            values = np.asarray(values)
            if values.ndim == 3:
                values = values[:, :, -1]
            explanations: list[dict[str, Any]] = []
            for row_values in values:
                contributions = {
                    feature: float(value)
                    for feature, value in zip(self.manifest.feature_schema, row_values)
                }
                ranked = sorted(contributions.items(), key=lambda item: abs(item[1]), reverse=True)
                explanations.append({
                    "top_feature": ranked[0][0] if ranked else None,
                    "top_value": ranked[0][1] if ranked else None,
                    "all_features": contributions,
                })
            return explanations
        except Exception as exc:
            return [{"status": "failed", "reason": f"{type(exc).__name__}: {exc}"}] * len(frame)

    def health_check(self) -> dict[str, Any]:
        return {
            "loaded": self.loaded,
            "artifact_exists": self.artifact_path.is_file(),
            "artifact_path": str(self.artifact_path),
        }


class JoblibAdapter(ModelAdapter):
    def load(self) -> None:
        if not self.artifact_path.is_file():
            raise FileNotFoundError(f"Model artifact not found: {self.artifact_path}")
        self.model = joblib.load(self.artifact_path)

    def predict(self, frame: pd.DataFrame) -> list[Any]:
        if not self.loaded:
            self.load()
        selected = self.validate_features(frame)
        output = self.model.predict(selected)
        return [value.item() if hasattr(value, "item") else value for value in output]

    def predict_proba(self, frame: pd.DataFrame) -> list[Any] | None:
        if not self.loaded:
            self.load()
        if not hasattr(self.model, "predict_proba"):
            return None
        selected = self.validate_features(frame)
        output = self.model.predict_proba(selected)
        return np.asarray(output).tolist()


class OnnxAdapter(ModelAdapter):
    def load(self) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError("onnxruntime is not installed") from exc
        self.model = ort.InferenceSession(str(self.artifact_path), providers=["CPUExecutionProvider"])

    def predict(self, frame: pd.DataFrame) -> list[Any]:
        if not self.loaded:
            self.load()
        selected = self.validate_features(frame).to_numpy(dtype=np.float32)
        input_name = self.model.get_inputs()[0].name
        outputs = self.model.run(None, {input_name: selected})
        return np.asarray(outputs[0]).reshape(-1).tolist()


ADAPTERS: dict[str, type[ModelAdapter]] = {
    "scikit-learn": JoblibAdapter,
    "scikit-learn/joblib": JoblibAdapter,
    "xgboost": JoblibAdapter,
    "joblib": JoblibAdapter,
    "onnx": OnnxAdapter,
    "onnxruntime": OnnxAdapter,
}


def build_adapter(manifest: ModelManifest, artifact_path: Path) -> ModelAdapter:
    adapter_type = ADAPTERS.get(manifest.framework.lower())
    if adapter_type is None:
        raise ValueError(f"Unsupported model framework: {manifest.framework}")
    return adapter_type(manifest, artifact_path)