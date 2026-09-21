from __future__ import annotations

import pandas as pd

from app.ml_platform.registry import get_model_registry
from app.ml_platform.service import get_model_service
from app.ml_platform.schemas import ModelTask


def explain(features_df: pd.DataFrame, model_id: str | None = None) -> dict:
    selected_model = model_id or get_model_registry().default_for(ModelTask.hydrocarbon_classification)
    if not selected_model:
        return {"status": "unavailable", "reason": "No hydrocarbon model configured"}
    service = get_model_service()
    with service._lock:
        adapter = service._adapter(selected_model)
        explanations = adapter.explain(features_df)
        result = dict(explanations[0]) if explanations else {"status": "unavailable"}
        result["explanation_model_provenance"] = {"model_id": selected_model, "artifact_sha256": adapter.artifact_sha256, "manifest": adapter.manifest.model_dump(mode="json")}
        return result
