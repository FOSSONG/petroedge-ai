from __future__ import annotations

from typing import Any

import pandas as pd

from app.ml_platform.schemas import InferenceRequest, ModelTask
from app.ml_platform.service import get_model_service


def predict_las_dataframe(
    df: pd.DataFrame,
    hydrocarbon_model_id: str | None = None,
    lithology_model_id: str | None = None,
) -> list[dict[str, Any]]:
    records = df.to_dict(orient="records")
    hydrocarbon = get_model_service().infer(InferenceRequest(
        task=ModelTask.hydrocarbon_classification,
        model_id=hydrocarbon_model_id,
        records=records,
    ))
    lithology = get_model_service().infer(InferenceRequest(
        task=ModelTask.lithology_classification,
        model_id=lithology_model_id,
        records=records,
    ))
    results: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        probabilities = hydrocarbon.probabilities[index] if hydrocarbon.probabilities else None
        hydrocarbon_probability = probabilities[-1] if isinstance(probabilities, list) else None
        results.append({
            "depth_m": float(record.get("depth_m", index)),
            "hydrocarbon_probability": round(float(hydrocarbon_probability or 0.0), 4),
            "lithology": str(lithology.predictions[index]),
            "hydrocarbon_model_id": hydrocarbon.model_id,
            "lithology_model_id": lithology.model_id,
        })
    return results