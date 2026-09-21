from __future__ import annotations

import math
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd

ALIASES = {
    "depth": ("DEPTH", "DEPT", "MD", "TVD", "TVDSS", "TVD_COMP", "TVDSS_COMP"),
    "gr": ("GR", "GR_COMP", "GAMMA", "GAMMA_RAY"),
    "rt": ("RT", "RT_COMP", "ILD", "LLD", "RES", "RESISTIVITY"),
    "rhob": ("RHOB", "RHOB_COMP", "DEN", "DENSITY"),
    "nphi": ("NPHI", "NPHI_COMP", "NEUTRON"),
}


def _normalise(name: str) -> str:
    return "".join(ch for ch in str(name).upper() if ch.isalnum() or ch == "_")


def identify_columns(columns: list[str]) -> dict[str, str | None]:
    normalised = {_normalise(column): column for column in columns}
    result: dict[str, str | None] = {}
    for canonical, aliases in ALIASES.items():
        result[canonical] = next((normalised.get(_normalise(alias)) for alias in aliases if _normalise(alias) in normalised), None)
    return result


def load_dataset(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path)
    elif suffix == ".parquet":
        frame = pd.read_parquet(path)
    elif suffix == ".las":
        import lasio
        las = lasio.read(path)
        frame = las.df().reset_index()
    else:
        raise ValueError(f"Unsupported dataset type: {suffix}")
    frame = frame.replace([-999.25, -999.0, -9999.0], np.nan)
    return frame


def _clip(value: float, low: float, high: float) -> float:
    return float(min(high, max(low, value)))


def _safe(value: Any) -> float | None:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


class EdgePetrophysicalInterpreter:
    """Depth-indexed deterministic petrophysics used when no trained multi-output ONNX model exists."""

    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.columns = identify_columns([str(column) for column in frame.columns])
        required = ["depth", "gr", "rt"]
        missing = [name.upper() for name in required if not self.columns[name]]
        if missing:
            raise ValueError(f"Dataset must contain depth, GR and RT curves. Missing: {', '.join(missing)}")

        gr = pd.to_numeric(frame[self.columns["gr"]], errors="coerce")
        self.gr_clean = gr
        self.gr_min = float(gr.quantile(0.05)) if gr.notna().any() else 20.0
        self.gr_max = float(gr.quantile(0.95)) if gr.notna().any() else 150.0
        if self.gr_max <= self.gr_min:
            self.gr_max = self.gr_min + 1.0
        self.gr_mean = float(gr.mean()) if gr.notna().any() else 0.0
        self.gr_std = max(float(gr.std()) if gr.notna().sum() > 1 else 1.0, 1e-6)

        rt = pd.to_numeric(frame[self.columns["rt"]], errors="coerce")
        log_rt = np.log10(rt.clip(lower=1e-4))
        self.rt_mean = float(log_rt.mean()) if log_rt.notna().any() else 0.0
        self.rt_std = max(float(log_rt.std()) if log_rt.notna().sum() > 1 else 1.0, 1e-6)

    def interpret_row(self, index: int) -> dict[str, Any]:
        started = perf_counter()
        row = self.frame.iloc[index]
        depth = _safe(row[self.columns["depth"]])
        gr = _safe(row[self.columns["gr"]])
        rt = _safe(row[self.columns["rt"]])
        rhob = _safe(row[self.columns["rhob"]]) if self.columns["rhob"] else None
        nphi = _safe(row[self.columns["nphi"]]) if self.columns["nphi"] else None
        if depth is None or gr is None or rt is None or rt <= 0:
            raise ValueError("Invalid depth, GR or RT value")

        vsh = _clip((gr - self.gr_min) / (self.gr_max - self.gr_min), 0.0, 1.0)
        phi_density = _clip((2.65 - rhob) / (2.65 - 1.0), 0.0, 0.45) if rhob is not None else None
        phi_neutron = _clip(nphi, 0.0, 0.45) if nphi is not None else None
        if phi_density is not None and phi_neutron is not None:
            porosity = _clip(0.5 * (phi_density + phi_neutron), 0.0, 0.45)
        elif phi_density is not None:
            porosity = phi_density
        elif phi_neutron is not None:
            porosity = phi_neutron
        else:
            porosity = _clip(0.32 * (1.0 - vsh), 0.03, 0.32)

        effective_porosity = _clip(porosity * (1.0 - 0.55 * vsh), 0.001, 0.45)
        rw, a, m, n = 0.10, 1.0, 2.0, 2.0
        sw = _clip(((a * rw) / (max(rt, 1e-4) * max(effective_porosity, 1e-3) ** m)) ** (1.0 / n), 0.0, 1.0)
        hydrocarbon_saturation = 1.0 - sw
        permeability_md = _clip(1000.0 * effective_porosity ** 4.4 / max(sw, 0.08) ** 2.0, 0.001, 20000.0)

        reservoir_probability = _clip((1.0 - vsh) * 0.55 + min(math.log10(rt + 1.0) / 3.0, 1.0) * 0.25 + min(effective_porosity / 0.30, 1.0) * 0.20, 0.0, 1.0)
        water_probability = _clip(sw * (0.75 + 0.25 * vsh), 0.0, 1.0)
        hydrocarbon_probability = _clip(reservoir_probability * hydrocarbon_saturation, 0.0, 1.0)
        gas_indicator = 0.0
        if nphi is not None and rhob is not None:
            gas_indicator = _clip((phi_density - phi_neutron) / 0.18, 0.0, 1.0)
        gas_probability = _clip(hydrocarbon_probability * gas_indicator, 0.0, 1.0)
        oil_probability = _clip(hydrocarbon_probability - gas_probability, 0.0, 1.0)
        total = water_probability + oil_probability + gas_probability
        if total > 0:
            water_probability, oil_probability, gas_probability = [value / total for value in (water_probability, oil_probability, gas_probability)]

        gr_z = abs((gr - self.gr_mean) / self.gr_std)
        rt_z = abs((math.log10(max(rt, 1e-4)) - self.rt_mean) / self.rt_std)
        anomaly_score = _clip(max(gr_z, rt_z) / 5.0, 0.0, 1.0)
        anomaly = anomaly_score >= 0.65
        pay_zone = bool(vsh <= 0.35 and effective_porosity >= 0.08 and sw <= 0.55 and rt >= 5.0)
        reservoir_class = "Reservoir" if reservoir_probability >= 0.55 else "Non-reservoir"
        fluid_class = max({"Water": water_probability, "Oil": oil_probability, "Gas": gas_probability}, key=lambda key: {"Water": water_probability, "Oil": oil_probability, "Gas": gas_probability}[key])

        return {
            "row_index": index,
            "depth": round(depth, 3),
            "gr": round(gr, 3),
            "rt": round(rt, 4),
            "rhob": round(rhob, 4) if rhob is not None else None,
            "nphi": round(nphi, 4) if nphi is not None else None,
            "vsh": round(vsh, 4),
            "porosity": round(porosity, 4),
            "effective_porosity": round(effective_porosity, 4),
            "permeability_md": round(permeability_md, 3),
            "water_saturation": round(sw, 4),
            "water_probability": round(water_probability, 4),
            "oil_probability": round(oil_probability, 4),
            "gas_probability": round(gas_probability, 4),
            "hydrocarbon_probability": round(hydrocarbon_probability, 4),
            "anomaly_score": round(anomaly_score, 4),
            "anomaly": anomaly,
            "pay_zone": pay_zone,
            "reservoir_class": reservoir_class,
            "fluid_class": fluid_class,
            "interpretation": f"{reservoir_class}; dominant fluid {fluid_class}; {'pay zone' if pay_zone else 'non-pay'}; {'log anomaly' if anomaly else 'logs within expected range'}.",
            "runtime": "industry-standard-deterministic-petrophysics",
            "latency_ms": round((perf_counter() - started) * 1000.0, 3),
        }
