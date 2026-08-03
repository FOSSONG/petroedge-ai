from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any

import pandas as pd

from app.ml_platform.adapters import ModelAdapter, build_adapter
from app.ml_platform.registry import ModelRegistry, get_model_registry
from app.ml_platform.schemas import InferenceRequest, InferenceResponse, ModelStage, ModelTask


class ModelService:
    def __init__(self, registry: ModelRegistry | None = None, max_loaded_models: int = 3):
        self.registry = registry or get_model_registry()
        self.max_loaded_models = max(1, max_loaded_models)
        self._adapters: OrderedDict[str, ModelAdapter] = OrderedDict()
        self._lock = threading.RLock()

    def _adapter(self, model_id: str) -> ModelAdapter:
        with self._lock:
            if model_id in self._adapters:
                adapter = self._adapters.pop(model_id)
                self._adapters[model_id] = adapter
                return adapter
            manifest = self.registry.get(model_id)
            adapter = build_adapter(manifest, self.registry.artifact_path(manifest))
            self._adapters[model_id] = adapter
            while len(self._adapters) > self.max_loaded_models:
                _, evicted = self._adapters.popitem(last=False)
                evicted.unload()
            return adapter

    def unload(self, model_id: str | None = None) -> None:
        with self._lock:
            if model_id is None:
                for adapter in self._adapters.values():
                    adapter.unload()
                self._adapters.clear()
                return
            adapter = self._adapters.pop(model_id, None)
            if adapter:
                adapter.unload()

    def resolve_model(self, task: ModelTask, requested_model_id: str | None) -> tuple[str, bool]:
        fallback_used = False
        model_id = requested_model_id or self.registry.default_for(task)
        if not model_id:
            raise ValueError(f"No default model configured for task {task.value}")
        try:
            manifest = self.registry.get(model_id)
            if manifest.task != task:
                raise ValueError(f"Model {model_id} does not support task {task.value}")
            if not manifest.enabled or manifest.stage in {ModelStage.failed, ModelStage.archived, ModelStage.deprecated}:
                raise ValueError(f"Model {model_id} is not available for inference")
            if not self.registry.artifact_path(manifest).is_file():
                raise FileNotFoundError(f"Artifact missing for model {model_id}")
        except Exception:
            default_id = self.registry.default_for(task)
            if requested_model_id and default_id and default_id != requested_model_id:
                model_id = default_id
                fallback_used = True
            else:
                raise
        return model_id, fallback_used

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        model_id, fallback_used = self.resolve_model(request.task, request.model_id)
        manifest = self.registry.get(model_id)
        adapter = self._adapter(model_id)
        frame = pd.DataFrame.from_records(request.records)
        started = time.perf_counter()
        predictions = adapter.predict(frame)
        probabilities = adapter.predict_proba(frame)
        explanations = adapter.explain(frame) if request.explain else None
        latency_ms = (time.perf_counter() - started) * 1000.0
        return InferenceResponse(
            task=request.task,
            model_id=model_id,
            model_version=manifest.version,
            predictions=predictions,
            probabilities=probabilities,
            explanations=explanations,
            record_count=len(frame),
            latency_ms=round(latency_ms, 3),
            fallback_used=fallback_used,
        )

    def health(self, model_id: str) -> dict[str, Any]:
        manifest = self.registry.get(model_id)
        adapter = self._adapter(model_id)
        state = adapter.health_check()
        state.update({
            "model_id": model_id,
            "task": manifest.task.value,
            "stage": manifest.stage.value,
            "framework": manifest.framework,
            "version": manifest.version,
        })
        return state

    def loaded_models(self) -> list[str]:
        with self._lock:
            return list(self._adapters.keys())


_service: ModelService | None = None


def get_model_service() -> ModelService:
    global _service
    if _service is None:
        _service = ModelService()
    return _service