import pytest

from app.services.edge_temporal import (
    EdgeTemporalInferenceService,
    TemporalModelKind,
    TemporalModelManifest,
    TemporalWorkflow,
)


def _values(rows: int = 8):
    return [[float(i), float(i % 3), float(i) / 10.0] for i in range(rows)]


def test_gru_supports_live_causal_inference():
    service = EdgeTemporalInferenceService()
    manifest = TemporalModelManifest(
        model_id="gru-test",
        version="1",
        kind=TemporalModelKind.GRU,
        workflow=TemporalWorkflow.DIGITAL_TWIN,
        causal=True,
        runtime="demo",
        window_size=4,
    )
    result = service.predict(manifest, _values(), execution_mode="live")
    assert result["model_kind"] == "gru"
    assert result["causal"] is True
    assert 0 <= result["score"] <= 1


def test_bigru_rejects_live_mode():
    service = EdgeTemporalInferenceService()
    manifest = TemporalModelManifest(
        model_id="bigru-test",
        version="1",
        kind=TemporalModelKind.BIGRU,
        workflow=TemporalWorkflow.LITHOLOGY,
        causal=False,
        runtime="demo",
        window_size=4,
    )
    with pytest.raises(ValueError, match="not allowed"):
        service.predict(manifest, _values(), execution_mode="live")


def test_bigru_supports_replay_mode():
    service = EdgeTemporalInferenceService()
    manifest = TemporalModelManifest(
        model_id="bigru-test",
        version="1",
        kind=TemporalModelKind.BIGRU,
        workflow=TemporalWorkflow.LITHOLOGY,
        causal=False,
        runtime="demo",
        window_size=4,
    )
    result = service.predict(manifest, _values(), execution_mode="replay")
    assert result["model_kind"] == "bigru"
    assert result["execution_mode"] == "replay"
