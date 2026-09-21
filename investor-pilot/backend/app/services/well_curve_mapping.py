"""Explicit, versioned well-view mapping; source datasets remain unchanged."""
import math
from typing import Literal
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from app.schemas import WellLogSample

# Factors convert source units to the unit encoded in the target name.
UNITS = {
    "depth_m": {"m": 1.0, "ft": 0.3048},
    "gamma_ray_api": {"API": 1.0},
    "resistivity_ohmm": {"ohm.m": 1.0},
    "density_gcc": {"g/cm3": 1.0, "kg/m3": 0.001},
    "neutron_porosity_vv": {"v/v": 1.0, "%": 0.01},
    "sonic_usft": {"us/ft": 1.0, "us/m": 0.3048},
    "caliper_in": {"in": 1.0, "cm": 1.0 / 2.54, "mm": 1.0 / 25.4},
}

class CurveSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    source: str = Field(min_length=1)
    unit: str
    null_values: list[float] = Field(default_factory=list, max_length=20)

class CurveMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    depth_reference: Literal["MD", "TVD", "TVDSS"]
    curves: dict[str, CurveSelection]


def validate_mapping(mapping: CurveMapping, columns) -> None:
    if "depth_m" not in mapping.curves:
        raise ValueError("Map a depth curve and declare its reference.")
    sources = []
    for target, choice in mapping.curves.items():
        if target not in UNITS or choice.unit not in UNITS[target]:
            raise ValueError(f"Unsupported target/unit: {target} / {choice.unit}")
        if choice.source not in columns:
            raise ValueError(f"Source column is missing: {choice.source}")
        sources.append(choice.source)
    if len(set(sources)) != len(sources):
        raise ValueError("A source column cannot represent multiple physical curves.")


def mapped_records(frame, mapping: CurveMapping, well_id: str):
    validate_mapping(mapping, frame.columns)
    output = []
    for _, row in frame.iterrows():
        record = {"well_id": well_id, "depth_reference": mapping.depth_reference}
        for target, choice in mapping.curves.items():
            value = pd.to_numeric(row[choice.source], errors="coerce")
            valid = pd.notna(value) and math.isfinite(float(value)) and value not in choice.null_values
            converted = float(value) * UNITS[target][choice.unit] if valid else None
            record[target] = converted if converted is not None and math.isfinite(converted) else None
        # Vertical depth cannot be silently passed to a measured-depth analysis.
        try:
            WellLogSample.model_validate(record)
            ready = mapping.depth_reference == "MD"
        except ValueError:
            ready = False
        record["analysis_ready"] = ready
        output.append(record)
    return output
