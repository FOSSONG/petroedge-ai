from __future__ import annotations

import pandas as pd

from app.ml_platform.registry import get_model_registry
from app.ml_platform.service import get_model_service
from app.ml_platform.schemas import ModelTask


def explain(features_df: pd.DataFrame, model_id: str | None = None) -> dict:
    selected_model = model_id or get_model_registry().default_for(ModelTask.hydrocarbon_classification)
    if not selected_model:
        return {"status": "unavailable", "reason": "No hydrocarbon model configured"}
    adapter = get_model_service()._adapter(selected_model)
    explanations = adapter.explain(features_df)
    return explanations[0] if explanations else {"status": "unavailable"}