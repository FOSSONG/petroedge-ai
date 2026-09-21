from __future__ import annotations

import math
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from app.services.edge_temporal import (
    EdgeTemporalInferenceService,
    TemporalModelKind,
    TemporalModelManifest,
    TemporalWorkflow,
)


def _clip(value: float, low: float, high: float) -> float:
    return float(min(high, max(low, value)))


@dataclass(slots=True)
class StreamCalibration:
    gr: deque[float]
    log_rt: deque[float]


class RealTimeInterpretationService:
    """Causal physics + trained-ML orchestration for B1-approved stream samples.

    Physics is always available for inference-ready samples. ML is used only
    when a real causal GRU ONNX artefact is installed. Demo fallback is never
    presented as trained AI in this live path.
    """

    FEATURE_ORDER = (
        "depth_m",
        "gamma_ray_api",
        "resistivity_ohmm",
        "density_gcc",
        "neutron_porosity_vv",
        "sonic_usft",
    )

    def __init__(self, model_root: Path | None = None, history_size: int = 128) -> None:
        self.model_root = model_root or Path("model_store/edge")
        self.temporal = EdgeTemporalInferenceService(self.model_root)
        self.history_size = history_size
        self._lock = threading.RLock()
        self._calibration: dict[str, StreamCalibration] = defaultdict(
            lambda: StreamCalibration(deque(maxlen=history_size), deque(maxlen=history_size))
        )
        self._features: dict[str, deque[list[float]]] = defaultdict(
            lambda: deque(maxlen=history_size)
        )

    def _physics(self, stream_id: str, channels: dict[str, float]) -> dict[str, Any]:
        started = perf_counter()
        depth = float(channels["depth_m"])
        gr = float(channels["gamma_ray_api"])
        rt = max(float(channels["resistivity_ohmm"]), 1e-4)
        rhob = channels.get("density_gcc")
        nphi = channels.get("neutron_porosity_vv")

        with self._lock:
            calibration = self._calibration[stream_id]
            calibration.gr.append(gr)
            calibration.log_rt.append(math.log10(rt))
            gr_values = np.asarray(calibration.gr, dtype=float)
            rt_values = np.asarray(calibration.log_rt, dtype=float)

        if len(gr_values) >= 20:
            gr_min, gr_max = np.quantile(gr_values, [0.05, 0.95])
        else:
            gr_min, gr_max = 20.0, 150.0
        if gr_max <= gr_min:
            gr_max = gr_min + 1.0

        vsh = _clip((gr - float(gr_min)) / (float(gr_max) - float(gr_min)), 0.0, 1.0)
        phi_density = _clip((2.65 - float(rhob)) / 1.65, 0.0, 0.45) if rhob is not None else None
        phi_neutron = _clip(float(nphi), 0.0, 0.45) if nphi is not None else None

        if phi_density is not None and phi_neutron is not None:
            porosity = _clip(0.5 * (phi_density + phi_neutron), 0.0, 0.45)
        elif phi_density is not None:
            porosity = phi_density
        elif phi_neutron is not None:
            porosity = phi_neutron
        else:
            porosity = _clip(0.32 * (1.0 - vsh), 0.03, 0.32)

        effective_porosity = _clip(porosity * (1.0 - 0.55 * vsh), 0.001, 0.45)

        # Current platform defaults. These are deterministic engineering assumptions,
        # not formation-specific calibrated constants.
        rw, a, m, n = 0.10, 1.0, 2.0, 2.0
        sw = _clip(
            ((a * rw) / (rt * max(effective_porosity, 1e-3) ** m)) ** (1.0 / n),
            0.0,
            1.0,
        )
        sh = 1.0 - sw
        permeability_md = _clip(
            1000.0 * effective_porosity ** 4.4 / max(sw, 0.08) ** 2.0,
            0.001,
            20000.0,
        )

        reservoir_probability = _clip(
            (1.0 - vsh) * 0.55
            + min(math.log10(rt + 1.0) / 3.0, 1.0) * 0.25
            + min(effective_porosity / 0.30, 1.0) * 0.20,
            0.0,
            1.0,
        )
        hydrocarbon_probability = _clip(reservoir_probability * sh, 0.0, 1.0)
        water_probability = _clip(sw * (0.75 + 0.25 * vsh), 0.0, 1.0)

        gas_indicator = 0.0
        if phi_density is not None and phi_neutron is not None:
            gas_indicator = _clip((phi_density - phi_neutron) / 0.18, 0.0, 1.0)
        gas_probability = _clip(hydrocarbon_probability * gas_indicator, 0.0, 1.0)
        oil_probability = _clip(hydrocarbon_probability - gas_probability, 0.0, 1.0)

        total = water_probability + oil_probability + gas_probability
        if total > 0:
            water_probability /= total
            oil_probability /= total
            gas_probability /= total

        gr_mean = float(gr_values.mean())
        gr_std = max(float(gr_values.std()), 1e-6)
        rt_mean = float(rt_values.mean())
        rt_std = max(float(rt_values.std()), 1e-6)
        anomaly_score = _clip(
            max(abs((gr - gr_mean) / gr_std), abs((math.log10(rt) - rt_mean) / rt_std)) / 5.0,
            0.0,
            1.0,
        ) if len(gr_values) >= 8 else 0.0

        pay_zone = bool(vsh <= 0.35 and effective_porosity >= 0.08 and sw <= 0.55 and rt >= 5.0)
        reservoir_class = "Reservoir" if reservoir_probability >= 0.55 else "Non-reservoir"
        fluid_class = max(
            {"Water": water_probability, "Oil": oil_probability, "Gas": gas_probability},
            key={"Water": water_probability, "Oil": oil_probability, "Gas": gas_probability}.get,
        )

        return {
            "depth_m": round(depth, 3),
            "vsh": round(vsh, 4),
            "porosity": round(porosity, 4),
            "effective_porosity": round(effective_porosity, 4),
            "permeability_md": round(permeability_md, 3),
            "water_saturation": round(sw, 4),
            "hydrocarbon_saturation": round(sh, 4),
            "reservoir_probability": round(reservoir_probability, 4),
            "hydrocarbon_probability": round(hydrocarbon_probability, 4),
            "water_probability": round(water_probability, 4),
            "oil_probability": round(oil_probability, 4),
            "gas_probability": round(gas_probability, 4),
            "reservoir_class": reservoir_class,
            "fluid_class": fluid_class,
            "pay_zone": pay_zone,
            "well_log_anomaly_score": round(anomaly_score, 4),
            "well_log_anomaly": anomaly_score >= 0.65,
            "assumptions": {"rw_ohm_m": rw, "archie_a": a, "archie_m": m, "archie_n": n},
            "calibration_samples": len(gr_values),
            "runtime": "deterministic-petrophysics",
            "latency_ms": round((perf_counter() - started) * 1000.0, 3),
        }

    def _feature_vector(self, channels: dict[str, float]) -> list[float]:
        values: list[float] = []
        for name in self.FEATURE_ORDER:
            value = channels.get(name)
            values.append(float(value) if value is not None else 0.0)
        return values

    def _trained_gru(self, stream_id: str, channels: dict[str, float]) -> dict[str, Any]:
        with self._lock:
            history = self._features[stream_id]
            history.append(self._feature_vector(channels))
            values = list(history)

        manifest = TemporalModelManifest(
            model_id="petroedge-gru-live-v1",
            version="1.0.0",
            kind=TemporalModelKind.GRU,
            workflow=TemporalWorkflow.HYDROCARBON,
            causal=True,
            runtime="onnxruntime",
            model_path="gru_live.onnx",
            window_size=32,
            feature_names=self.FEATURE_ORDER,
        )
        model_path = self.model_root / "gru_live.onnx"
        if not model_path.is_file():
            return {
                "status": "PHYSICS_ONLY",
                "reason": "trained causal GRU artefact is not installed",
                "model_id": manifest.model_id,
                "model_path": str(model_path),
                "fallback_used": False,
                "history_samples": len(values),
            }
        if len(values) < manifest.window_size:
            return {
                "status": "INFERENCE_BLOCKED",
                "reason": f"GRU warm-up requires {manifest.window_size} causal samples",
                "model_id": manifest.model_id,
                "fallback_used": False,
                "history_samples": len(values),
            }

        result = self.temporal.predict(
            manifest,
            values,
            execution_mode="live",
            allow_demo_fallback=False,
        )
        return {
            "status": "TRAINED_MODEL",
            "fallback_used": False,
            **result,
        }

    def interpret(self, stream: dict[str, Any]) -> dict[str, Any]:
        started = perf_counter()
        if not stream.get("inference_ready"):
            return {
                "status": "INFERENCE_BLOCKED",
                "reason": "B1 quality/inference-readiness gate rejected the sample",
                "quality_state": stream.get("quality_state"),
                "physics": None,
                "ml": {"status": "INFERENCE_BLOCKED", "fallback_used": False},
                "fusion": None,
            }

        channels = stream["canonical_channels"]
        physics = self._physics(str(stream["stream_id"]), channels)
        ml = self._trained_gru(str(stream["stream_id"]), channels)

        physics_hc = float(physics["hydrocarbon_probability"])
        if ml["status"] == "TRAINED_MODEL":
            ml_score = _clip(float(ml["score"]), 0.0, 1.0)
            fused_hc = 0.65 * physics_hc + 0.35 * ml_score
            fusion_mode = "PHYSICS_PLUS_TRAINED_GRU"
            confidence = 0.65 * abs(physics_hc - 0.5) * 2.0 + 0.35 * float(ml["confidence"])
        else:
            fused_hc = physics_hc
            fusion_mode = "PHYSICS_ONLY"
            confidence = abs(physics_hc - 0.5) * 2.0

        return {
            "status": "INTERPRETED",
            "physics": physics,
            "ml": ml,
            "fusion": {
                "mode": fusion_mode,
                "hydrocarbon_probability": round(_clip(fused_hc, 0.0, 1.0), 4),
                "confidence": round(_clip(confidence, 0.0, 1.0), 4),
                "reservoir_class": physics["reservoir_class"],
                "fluid_class": physics["fluid_class"],
                "pay_zone": physics["pay_zone"],
            },
            "provenance": {
                "quality_gate": "B1",
                "physics_engine": "petroedge-deterministic-petrophysics",
                "ml_status": ml["status"],
                "demo_fallback_used": False,
            },
            "latency_ms": round((perf_counter() - started) * 1000.0, 3),
        }


real_time_interpretation_service = RealTimeInterpretationService()
