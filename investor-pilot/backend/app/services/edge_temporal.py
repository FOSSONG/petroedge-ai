from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from time import perf_counter
from typing import Any, Sequence

import numpy as np


class TemporalModelKind(StrEnum):
    GRU = "gru"
    BIGRU = "bigru"


class TemporalWorkflow(StrEnum):
    LITHOLOGY = "lithology_sequence"
    HYDROCARBON = "hydrocarbon_zone"
    ANOMALY = "well_log_anomaly"
    MISSING_LOG = "missing_log_reconstruction"
    DRILLING = "drilling_forecast"
    PRODUCTION = "production_forecast"
    INJECTION = "co2_injection_forecast"
    EMISSIONS = "emissions_forecast"
    DIGITAL_TWIN = "digital_twin_state"


@dataclass(frozen=True)
class TemporalModelManifest:
    model_id: str
    version: str
    kind: TemporalModelKind
    workflow: TemporalWorkflow
    causal: bool
    runtime: str
    model_path: str | None = None
    window_size: int = 32
    feature_names: tuple[str, ...] = ()


class EdgeTemporalInferenceService:
    """Edge-safe temporal inference with optional ONNX execution.

    GRU manifests are causal and suitable for live streams. BiGRU manifests are
    intentionally restricted to historical, replay, or batch workflows because
    bidirectional inference requires future context.
    """

    def __init__(self, model_root: Path | None = None) -> None:
        self.model_root = model_root or Path("model_store/edge")
        self._sessions: dict[str, Any] = {}

    @staticmethod
    def _validate_window(values: Sequence[Sequence[float]], window_size: int) -> np.ndarray:
        array = np.asarray(values, dtype=np.float32)
        if array.ndim != 2:
            raise ValueError("values must be a two-dimensional sequence [time, features]")
        if array.shape[0] < window_size:
            raise ValueError(f"at least {window_size} time steps are required")
        if not np.isfinite(array).all():
            raise ValueError("values contain NaN or infinite entries")
        return array[-window_size:]

    def _load_onnx_session(self, manifest: TemporalModelManifest):
        if not manifest.model_path:
            return None
        path = Path(manifest.model_path)
        if not path.is_absolute():
            path = self.model_root / path
        if not path.is_file():
            return None
        cache_key = f"{manifest.model_id}:{manifest.version}:{path}"
        if cache_key in self._sessions:
            return self._sessions[cache_key]
        try:
            import onnxruntime as ort
        except ImportError:
            return None
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        available = set(ort.get_available_providers())
        selected = [provider for provider in providers if provider in available]
        session = ort.InferenceSession(str(path), providers=selected or ["CPUExecutionProvider"])
        self._sessions[cache_key] = session
        return session

    @staticmethod
    def _demo_temporal_score(window: np.ndarray, kind: TemporalModelKind) -> float:
        """Deterministic fallback for demonstrations when no model artefact is installed."""
        scaled = (window - window.mean(axis=0, keepdims=True)) / (
            window.std(axis=0, keepdims=True) + 1e-6
        )
        forward = np.tanh(scaled).mean(axis=1)
        signal = float(forward[-8:].mean())
        if kind == TemporalModelKind.BIGRU:
            backward = np.tanh(scaled[::-1]).mean(axis=1)
            signal = 0.5 * (signal + float(backward[-8:].mean()))
        return float(1.0 / (1.0 + np.exp(-signal)))

    def predict(
        self,
        manifest: TemporalModelManifest,
        values: Sequence[Sequence[float]],
        *,
        execution_mode: str,
        allow_demo_fallback: bool = True,
    ) -> dict[str, Any]:
        mode = execution_mode.strip().lower()
        if manifest.kind == TemporalModelKind.BIGRU and mode not in {"batch", "replay", "historical"}:
            raise ValueError("BiGRU is not allowed for causal live inference; use GRU or replay mode")

        window = self._validate_window(values, manifest.window_size)
        started = perf_counter()
        session = self._load_onnx_session(manifest)

        if session is not None:
            input_name = session.get_inputs()[0].name
            outputs = session.run(None, {input_name: window[np.newaxis, :, :]})
            raw = np.asarray(outputs[0]).reshape(-1)
            score = float(raw[-1])
            runtime = "onnxruntime"
            fallback = False
        else:
            if not allow_demo_fallback:
                raise RuntimeError(
                    f"trained model artefact unavailable for {manifest.model_id}; "
                    "demo fallback is disabled for live operational inference"
                )
            score = self._demo_temporal_score(window, manifest.kind)
            runtime = "deterministic-demo-fallback"
            fallback = True

        latency_ms = (perf_counter() - started) * 1000.0
        return {
            "model_id": manifest.model_id,
            "model_version": manifest.version,
            "model_kind": manifest.kind.value,
            "workflow": manifest.workflow.value,
            "causal": manifest.causal,
            "execution_mode": mode,
            "runtime": runtime,
            "fallback": fallback,
            "score": score,
            "confidence": abs(score - 0.5) * 2.0,
            "window_size": manifest.window_size,
            "feature_count": int(window.shape[1]),
            "latency_ms": round(latency_ms, 3),
        }


def default_manifests() -> list[TemporalModelManifest]:
    return [
        TemporalModelManifest(
            model_id="petroedge-gru-live-v1",
            version="1.0.0",
            kind=TemporalModelKind.GRU,
            workflow=TemporalWorkflow.DIGITAL_TWIN,
            causal=True,
            runtime="onnxruntime",
            model_path="gru_live.onnx",
        ),
        TemporalModelManifest(
            model_id="petroedge-bigru-replay-v1",
            version="1.0.0",
            kind=TemporalModelKind.BIGRU,
            workflow=TemporalWorkflow.LITHOLOGY,
            causal=False,
            runtime="onnxruntime",
            model_path="bigru_replay.onnx",
        ),
    ]
