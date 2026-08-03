from __future__ import annotations

import pytest

from app.ml_platform.registry import get_model_registry
from app.ml_platform.schemas import InferenceRequest, ModelTask
from app.ml_platform.service import get_model_service


FEATURES = {
    "gamma_ray_api": 45.0,
    "resistivity_ohmm": 35.0,
    "density_gcc": 2.25,
    "neutron_porosity_vv": 0.18,
    "sonic_usft": 82.0,
    "caliper_in": 8.5,
}


def test_seed_models_are_discoverable():
    registry = get_model_registry()
    ids = {model.model_id for model in registry.list()}
    assert "hydrocarbon-xgb-v1" in ids
    assert "lithology-rf-v1" in ids


def test_default_models_match_tasks():
    registry = get_model_registry()
    assert registry.default_for(ModelTask.hydrocarbon_classification) == "hydrocarbon-xgb-v1"
    assert registry.default_for(ModelTask.lithology_classification) == "lithology-rf-v1"


def test_hydrocarbon_inference():
    output = get_model_service().infer(InferenceRequest(
        task=ModelTask.hydrocarbon_classification,
        records=[FEATURES],
    ))
    assert output.record_count == 1
    assert len(output.predictions) == 1


def test_feature_validation_rejects_missing_columns():
    with pytest.raises(ValueError, match="Missing required model features"):
        get_model_service().infer(InferenceRequest(
            task=ModelTask.hydrocarbon_classification,
            records=[{"gamma_ray_api": 50.0}],
        ))