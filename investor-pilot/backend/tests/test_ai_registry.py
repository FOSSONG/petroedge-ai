from pathlib import Path
import pytest
from app.ai.registry import ModelNotFoundError,ModelRegistry
def test_required_models(tmp_path:Path):
    keys={m.key for m in ModelRegistry(tmp_path).list_capabilities()}
    assert {'random_forest','xgboost','lightgbm','catboost','ann','cnn','lstm','gru','bigru','voting_ensemble','stacked_ensemble'}.issubset(keys)
def test_gru_bigru_semantics(tmp_path:Path):
    registry=ModelRegistry(tmp_path); gru=registry.get_capability('gru'); bigru=registry.get_capability('bigru')
    assert gru.supports_streaming and gru.causal and gru.edge_ready
    assert not bigru.supports_streaming and not bigru.causal
def test_unknown_model(tmp_path:Path):
    with pytest.raises(ModelNotFoundError): ModelRegistry(tmp_path).get_capability('missing')