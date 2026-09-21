from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class CurveAliasResult:
    """
    Result returned after canonical curve mapping.

    Attributes
    ----------
    dataframe:
        DataFrame with recognised log curves renamed to PetroEdge canonical
        names.

    mapping:
        Mapping of original column names to canonical names.

    unmatched_columns:
        Columns that were retained without canonical mapping.

    duplicate_candidates:
        Alternative source columns that matched a canonical curve already
        assigned to another column.
    """

    dataframe: pd.DataFrame
    mapping: dict[str, str]
    unmatched_columns: list[str]
    duplicate_candidates: dict[str, list[str]]


# ---------------------------------------------------------------------------
# PetroEdge canonical curve aliases
# ---------------------------------------------------------------------------

CURVE_ALIASES: dict[str, tuple[str, ...]] = {
    "depth_m": (
        "DEPTH",
        "DEPT",
        "TDEP",
        "MD",
        "MD_M",
        "TVD",
        "TVD_M",
        "TVDSS",
        "TVDSS_M",
        "DPT",
        "DEP",
        "DEPTH_M",
        "MEASURED_DEPTH",
        "BOREHOLE_DEPTH",
        "BOREHOLEDEPTH",
        "TRUE_VERTICAL_DEPTH",
    ),
    "gamma_ray_api": (
        "GR",
        "GR_COMP",
        "GR_CORR",
        "GR_EDTC", "GR_EDTC_R", "GRD", "GRC",
        "CGR",
        "SGR",
        "GAM",
        "GAMMA",
        "GAMMA_RAY",
        "GAMMARAY",
        "GAMMA_RAY_API",
        "GAPI",
        "HGR",
        "ECGR",
    ),
    "resistivity_ohmm": (
        "RT",
        "RT_COMP",
        "ILD",
        "LLD",
        "RDEP",
        "RDEEP",
        "RDEEP_COMP",
        "RES",
        "RESD",
        "RESDEEP",
        "RES_DEEP",
        "DEEP_RESISTIVITY",
        "AT90",
        "AIT90",
        "HDRS",
        "HLLD",
        "IDPH",
        "RLA5",
    ),
    "medium_resistivity_ohmm": (
        "RM",
        "ILM",
        "LLM",
        "RMED",
        "RMEDIUM",
        "RES_MEDIUM",
        "MEDIUM_RESISTIVITY",
        "AT30",
        "AIT30",
        "RLA3",
    ),
    "shallow_resistivity_ohmm": (
        "RS",
        "LLS",
        "RSHAL",
        "RSHALLOW",
        "RES_SHALLOW",
        "SHALLOW_RESISTIVITY",
        "MSFL",
        "SFLU",
        "AT10",
        "AIT10",
        "RLA1",
    ),
    "micro_resistivity_ohmm": (
        "RXO",
        "RXO_COMP",
        "RXOZ",
        "RFOC",
        "MICRO_RESISTIVITY",
        "INVASION_RESISTIVITY",
    ),
    "density_gcc": (
        "RHOB",
        "RHOB_COMP",
        "RHOB_CORR",
        "DEN",
        "DENS",
        "DENSITY",
        "DENSITY_GCC",
        "ZDEN",
        "RHOZ", "RHO8",
        "BD",
        "BULK_DENSITY",
        "BULKDENSITY",
    ),
    "density_correction_gcc": (
        "DRHO",
        "DRHO_COMP",
        "DELTA_RHO",
        "DENSITY_CORRECTION",
        "RHOB_CORRECTION",
    ),
    "neutron_porosity_vv": (
        "NPHI",
        "NPHI_COMP",
        "NPHI_CORR",
        "TNPH",
        "CNL",
        "NEUT",
        "NEUTRON",
        "NEUTRON_POROSITY",
        "NPOR",
        "PHIN",
        "NPHI_LS",
    ),
    "sonic_usft": (
        "DT",
        "DTC",
        "DT_COMP",
        "DTCO",
        "AC",
        "SONIC",
        "SONIC_COMP",
        "COMPRESSIONAL_SONIC",
        "DTP",
        "ITT",
    ),
    "shear_sonic_usft": (
        "DTS",
        "DTSM",
        "DTS_COMP",
        "SHEAR_SONIC",
        "SHEAR_SLOWNESS",
    ),
    "caliper_in": (
        "CALI",
        "CALI_COMP",
        "CAL",
        "CALIPER",
        "CALIPER_IN",
        "HCAL",
        "DCAL",
        "C1",
        "C2",
    ),
    "bit_size_in": (
        "BS",
        "BS_COMP",
        "BIT",
        "BITSIZE",
        "BIT_SIZE",
        "BIT_SIZE_IN",
    ),
    "sp_mv": (
        "SP",
        "SP_COMP",
        "SPONT",
        "SPONTANEOUS_POTENTIAL",
        "SP_MV",
    ),
    "photoelectric_factor": (
        "PE",
        "PEF",
        "PEFZ",
        "PEF_COMP",
        "PHOTOELECTRIC_FACTOR",
    ),
    "thorium_ppm": (
        "TH",
        "THOR",
        "THORIUM",
        "THORIUM_PPM",
    ),
    "uranium_ppm": (
        "U",
        "URAN",
        "URANIUM",
        "URANIUM_PPM",
    ),
    "potassium_pct": (
        "K",
        "POTA",
        "POTASSIUM",
        "POTASSIUM_PCT",
    ),
    "rop_mph": (
        "ROP",
        "ROP_MPH",
        "RATE_OF_PENETRATION",
        "PENETRATION_RATE",
    ),
    "mud_weight_ppg": (
        "MW",
        "MUDWT",
        "MUD_WEIGHT",
        "MUD_WEIGHT_PPG",
    ),
    "mud_resistivity_ohmm": (
        "RMUD",
        "RM",
        "MUD_RESISTIVITY",
    ),
    "mud_temperature_c": (
        "MTEMP",
        "MUD_TEMP",
        "MUD_TEMPERATURE",
        "MUD_TEMPERATURE_C",
    ),
    "temperature_c": (
        "TEMP",
        "TEMP_C",
        "TEMPERATURE",
        "TEMPERATURE_C",
        "BHT",
    ),
    "pressure_psi": (
        "PRES",
        "PRESSURE",
        "PRESSURE_PSI",
        "FORMATION_PRESSURE",
    ),
    "well_id": (
        "WELL",
        "WELL_ID",
        "WELLID",
        "WELL_NAME",
        "UWI",
        "API_NUMBER",
    ),
    "date": (
        "DATE",
        "DATETIME",
        "TIME",
        "TIMESTAMP",
        "LOG_DATE",
    ),
}


CANONICAL_UNITS: dict[str, str | None] = {
    "depth_m": "m",
    "gamma_ray_api": "API",
    "resistivity_ohmm": "ohm.m",
    "medium_resistivity_ohmm": "ohm.m",
    "shallow_resistivity_ohmm": "ohm.m",
    "micro_resistivity_ohmm": "ohm.m",
    "density_gcc": "g/cm3",
    "density_correction_gcc": "g/cm3",
    "neutron_porosity_vv": "v/v",
    "sonic_usft": "us/ft",
    "shear_sonic_usft": "us/ft",
    "caliper_in": "in",
    "bit_size_in": "in",
    "sp_mv": "mV",
    "photoelectric_factor": "barn/e",
    "thorium_ppm": "ppm",
    "uranium_ppm": "ppm",
    "potassium_pct": "%",
    "rop_mph": "m/h",
    "mud_weight_ppg": "ppg",
    "mud_resistivity_ohmm": "ohm.m",
    "mud_temperature_c": "degC",
    "temperature_c": "degC",
    "pressure_psi": "psi",
    "well_id": None,
    "date": None,
}


AI_REQUIRED_CURVES: tuple[str, ...] = (
    "gamma_ray_api",
    "resistivity_ohmm",
    "density_gcc",
    "neutron_porosity_vv",
    "sonic_usft",
)


AI_OPTIONAL_CURVES: tuple[str, ...] = (
    "caliper_in",
    "bit_size_in",
    "photoelectric_factor",
    "sp_mv",
    "medium_resistivity_ohmm",
    "shallow_resistivity_ohmm",
)


def normalise_curve_name(value: str) -> str:
    """
    Convert curve names to a stable uppercase comparison form.

    Examples
    --------
    ``RHOB.COMP`` becomes ``RHOB_COMP``.
    ``gamma ray`` becomes ``GAMMA_RAY``.
    """

    text = str(value).strip().upper()
    text = re.sub(r"[^A-Z0-9]+", "_", text)
    return text.strip("_")


def normalise_unit(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value)).strip().upper()
    text = text.replace("\u039c", "U").replace("\u00b5", "U").replace("\u03a9", "OHM")
    return text.replace(" ", "").replace("^3", "3").replace("\u00b7", ".").replace("\u22c5", ".")

def header_parts(value: str) -> tuple[str, str]:
    """Only split explicitly delimited, recognised units; never guess from values."""
    raw = str(value).strip()
    if raw.lower() in CURVE_ALIASES:
        return raw, ""
    known = {"M", "FT", "API", "GAPI", "OHMM", "OHM.M", "OHM-M", "OHM*M", "G/C3", "G/CC", "G/CM3", "KG/M3", "V/V", "FRAC", "%", "PU", "US/FT", "US/F", "US/M", "IN", "INCHES", "CM", "MM", "MV"}
    bracket = re.match(r"^(.*?)\s*[\[(]([^\])]+)[\])]$", raw)
    pairs = [(bracket[1], bracket[2])] if bracket else []
    pairs += [(raw[:i], raw[i+1:]) for i,c in enumerate(raw) if c in ". _"]
    for name, unit in pairs:
        unit = normalise_unit(unit)
        if name and unit in known:
            return name.strip(), unit
    return raw, ""


def curve_match(column_name: str) -> dict[str, object]:
    """Conservative alias matching. Ambiguous mnemonics require user selection.

    Punctuation/case variations and LAS duplicate suffixes are recognised;
    arbitrary prefixes, suffixes and fuzzy spelling are never guessed. A match
    identifies a physical quantity, not its units or depth reference.
    """
    raw = str(column_name).strip()
    base, header_unit = header_parts(raw)
    normalised = normalise_curve_name(base)
    canonical = [key for key in CURVE_ALIASES if normalise_curve_name(key) == normalised]
    candidates = canonical or [key for key, aliases in CURVE_ALIASES.items()
                               if any(normalise_curve_name(alias) == normalised for alias in aliases)]
    method = "canonical" if canonical else "alias"
    if not candidates and re.search(r":\d+$", raw):
        base = curve_match(re.sub(r":\d+$", "", raw))
        candidates = list(base["candidates"])
        method = "LAS duplicate suffix"
    return {"canonical": candidates[0] if len(candidates) == 1 else None,
            "candidates": candidates,
            "status": "matched" if len(candidates) == 1 else "ambiguous" if candidates else "unmatched",
            "method": (method + " with explicit header unit" if header_unit else method) if candidates else "manual mapping required", "header_unit": header_unit}


def canonical_name_for(column_name: str) -> str | None:
    return curve_match(column_name)["canonical"]


def aliases_for(canonical_name: str) -> tuple[str, ...]:
    """
    Return all recognised aliases for a canonical curve.
    """

    return CURVE_ALIASES.get(canonical_name, ())


def canonical_unit_for(canonical_name: str) -> str | None:
    """
    Return the expected unit for a canonical curve.
    """

    return CANONICAL_UNITS.get(canonical_name)


def map_curve_columns(
    dataframe: pd.DataFrame,
    *,
    preserve_unmatched: bool = True,
    prefer_existing_canonical: bool = True,
) -> CurveAliasResult:
    """
    Rename recognised DataFrame columns to PetroEdge canonical names.

    Duplicate aliases are not allowed to silently overwrite one another.
    The first selected source column is mapped, while other matching columns
    are reported under ``duplicate_candidates``.

    Parameters
    ----------
    dataframe:
        Input DataFrame.

    preserve_unmatched:
        Keep columns that do not match known aliases.

    prefer_existing_canonical:
        When both a canonical column and an alias are present, prefer the
        existing canonical column.
    """

    source = dataframe.copy()

    original_columns = [str(column) for column in source.columns]

    selected: dict[str, str] = {}
    duplicate_candidates: dict[str, list[str]] = {}
    unmatched_columns: list[str] = []

    canonical_columns_present = {
        str(column)
        for column in source.columns
        if str(column) in CURVE_ALIASES
    }

    ordered_columns = original_columns

    if prefer_existing_canonical:
        ordered_columns = sorted(
            original_columns,
            key=lambda column: (
                0 if column in canonical_columns_present else 1,
                original_columns.index(column),
            ),
        )

    for column in ordered_columns:
        canonical_name = canonical_name_for(column)

        if canonical_name is None:
            unmatched_columns.append(column)
            continue

        if canonical_name in selected:
            duplicate_candidates.setdefault(
                canonical_name,
                [],
            ).append(column)
            continue

        selected[canonical_name] = column

    rename_mapping = {
        original_name: canonical_name
        for canonical_name, original_name in selected.items()
        if original_name != canonical_name
    }

    mapped = source.rename(columns=rename_mapping)

    if not preserve_unmatched:
        retained_columns = [
            canonical_name
            for canonical_name in selected
            if canonical_name in mapped.columns
        ]

        mapped = mapped.loc[:, retained_columns]

    return CurveAliasResult(
        dataframe=mapped,
        mapping=rename_mapping,
        unmatched_columns=unmatched_columns,
        duplicate_candidates=duplicate_candidates,
    )


def find_available_curves(
    columns: Iterable[str],
) -> list[str]:
    """
    Return recognised canonical curves available in a column collection.
    """

    available: list[str] = []

    for column in columns:
        canonical_name = canonical_name_for(str(column))

        if (
            canonical_name is not None
            and canonical_name not in available
        ):
            available.append(canonical_name)

    return available


def missing_ai_curves(
    columns: Iterable[str],
) -> list[str]:
    """
    Return required AI curves missing from a dataset.
    """

    canonical_columns = {
        canonical_name_for(str(column)) or str(column)
        for column in columns
    }

    return [
        curve
        for curve in AI_REQUIRED_CURVES
        if curve not in canonical_columns
    ]


def ai_readiness(
    columns: Iterable[str],
) -> dict[str, object]:
    """
    Summarise whether a dataset contains the curves required by current models.
    """

    canonical_columns = {
        canonical_name_for(str(column)) or str(column)
        for column in columns
    }

    required_missing = [
        curve
        for curve in AI_REQUIRED_CURVES
        if curve not in canonical_columns
    ]

    required_available = [
        curve
        for curve in AI_REQUIRED_CURVES
        if curve in canonical_columns
    ]

    optional_available = [
        curve
        for curve in AI_OPTIONAL_CURVES
        if curve in canonical_columns
    ]

    return {
        "ready": len(required_missing) == 0,
        "required_available": required_available,
        "required_missing": required_missing,
        "optional_available": optional_available,
        "required_curve_count": len(AI_REQUIRED_CURVES),
        "available_required_count": len(required_available),
    }