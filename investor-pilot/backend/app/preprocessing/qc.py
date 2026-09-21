from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

import numpy as np
import pandas as pd

from app.preprocessing.curve_aliases import (
    AI_REQUIRED_CURVES,
    ai_readiness,
    canonical_unit_for,
)

PHYSICAL_RANGES: dict[str, tuple[float | None, float | None]] = {
    "depth_m": (0.0, 15000.0),
    "gamma_ray_api": (-10.0, 500.0),
    "resistivity_ohmm": (0.0001, 200000.0),
    "medium_resistivity_ohmm": (0.0001, 200000.0),
    "shallow_resistivity_ohmm": (0.0001, 200000.0),
    "micro_resistivity_ohmm": (0.0001, 200000.0),
    "density_gcc": (1.0, 3.5),
    "density_correction_gcc": (-1.0, 1.0),
    "neutron_porosity_vv": (-0.20, 1.00),
    "sonic_usft": (20.0, 300.0),
    "shear_sonic_usft": (30.0, 700.0),
    "caliper_in": (2.0, 40.0),
    "bit_size_in": (2.0, 40.0),
    "sp_mv": (-500.0, 500.0),
    "photoelectric_factor": (0.0, 30.0),
    "thorium_ppm": (0.0, 1000.0),
    "uranium_ppm": (0.0, 1000.0),
    "potassium_pct": (0.0, 25.0),
    "rop_mph": (0.0, 500.0),
    "mud_weight_ppg": (5.0, 30.0),
    "mud_resistivity_ohmm": (0.0001, 1000.0),
    "mud_temperature_c": (-10.0, 300.0),
    "temperature_c": (-10.0, 350.0),
    "pressure_psi": (0.0, 50000.0),
}

DEFAULT_QC_WEIGHTS: dict[str, float] = {
    "completeness": 0.30,
    "physical_validity": 0.25,
    "depth_quality": 0.20,
    "signal_quality": 0.15,
    "ai_readiness": 0.10,
}


@dataclass(frozen=True)
class CurveQCResult:
    curve: str
    unit: str | None
    row_count: int
    valid_count: int
    missing_count: int
    null_fraction: float
    minimum: float | None
    maximum: float | None
    mean: float | None
    median: float | None
    standard_deviation: float | None
    out_of_range_count: int
    out_of_range_fraction: float
    flatline_count: int
    flatline_fraction: float
    spike_count: int
    spike_fraction: float
    constant_curve: bool
    qc_score: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DepthQCResult:
    depth_column: str
    row_count: int
    valid_depth_count: int
    missing_depth_count: int
    duplicate_depth_count: int
    non_monotonic_count: int
    is_monotonic_increasing: bool
    minimum_depth: float | None
    maximum_depth: float | None
    median_step: float | None
    irregular_step_fraction: float
    qc_score: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class WashoutQCResult:
    available: bool
    assessed_count: int
    washout_count: int
    washout_fraction: float
    threshold_in: float
    severe_washout_count: int
    qc_score: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DatasetQCResult:
    qc_score: float
    quality_class: str
    row_count: int
    column_count: int
    numeric_curve_count: int
    completeness_score: float
    physical_validity_score: float
    depth_quality_score: float
    signal_quality_score: float
    ai_readiness_score: float
    ai_ready: bool
    missing_ai_curves: tuple[str, ...]
    duplicate_depth_count: int
    interpolatable_null_count: int
    total_null_count: int
    total_out_of_range_count: int
    total_spike_count: int
    total_flatline_count: int
    depth: DepthQCResult
    washout: WashoutQCResult
    curves: tuple[CurveQCResult, ...]
    warnings: tuple[str, ...] = ()
    provenance: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if np.isfinite(numeric) else None


def _score_to_quality_class(score: float) -> str:
    if score >= 90.0:
        return "excellent"
    if score >= 80.0:
        return "very_good"
    if score >= 70.0:
        return "good"
    if score >= 60.0:
        return "fair"
    if score >= 40.0:
        return "poor"
    return "critical"


def _normalise_weights(weights: dict[str, float] | None) -> dict[str, float]:
    selected = dict(DEFAULT_QC_WEIGHTS)
    if weights:
        for key, value in weights.items():
            if key in selected:
                selected[key] = max(0.0, float(value))
    total = sum(selected.values())
    if total <= 0.0:
        return dict(DEFAULT_QC_WEIGHTS)
    return {key: value / total for key, value in selected.items()}


def _numeric_series(dataframe: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(dataframe[column], errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    )


def _detect_spikes(
    series: pd.Series,
    *,
    window: int = 9,
    threshold: float = 4.0,
) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").astype(float)
    if len(numeric) < 5:
        return pd.Series(False, index=numeric.index)
    window = max(5, int(window))
    if window % 2 == 0:
        window += 1
    rolling_median = numeric.rolling(
        window=window,
        center=True,
        min_periods=max(3, window // 3),
    ).median()
    absolute_deviation = (numeric - rolling_median).abs()
    rolling_mad = absolute_deviation.rolling(
        window=window,
        center=True,
        min_periods=max(3, window // 3),
    ).median()
    robust_sigma = 1.4826 * rolling_mad
    global_scale = float(np.nanmedian(robust_sigma.to_numpy()))
    if not np.isfinite(global_scale) or global_scale <= 0.0:
        global_scale = float(np.nanstd(numeric.to_numpy()))
    if not np.isfinite(global_scale) or global_scale <= 0.0:
        return pd.Series(False, index=numeric.index)
    robust_sigma = robust_sigma.fillna(global_scale).clip(lower=global_scale * 0.05)
    return (absolute_deviation > threshold * robust_sigma).fillna(False)


def _detect_flatlines(
    series: pd.Series,
    *,
    tolerance: float = 1e-8,
    minimum_run: int = 8,
) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").astype(float)
    valid = numeric.notna()
    unchanged = (
        numeric.diff().abs().le(tolerance)
        & valid
        & valid.shift(1, fill_value=False)
    )
    groups = unchanged.ne(unchanged.shift(fill_value=False)).cumsum()
    run_lengths = unchanged.groupby(groups).transform("sum")
    mask = unchanged & run_lengths.ge(max(2, minimum_run - 1))
    return (mask | mask.shift(-1, fill_value=False)).fillna(False)


def _irregular_step_fraction(
    depth: pd.Series,
    *,
    tolerance_fraction: float = 0.25,
) -> tuple[float, float | None]:
    valid_depth = depth.dropna().astype(float)
    if len(valid_depth) < 3:
        return 0.0, None
    differences = valid_depth.diff().dropna()
    positive = differences[differences > 0]
    if positive.empty:
        return 1.0, None
    median_step = float(positive.median())
    if median_step <= 0.0:
        return 1.0, median_step
    lower = median_step * (1.0 - tolerance_fraction)
    upper = median_step * (1.0 + tolerance_fraction)
    irregular = (positive < lower) | (positive > upper)
    return float(irregular.mean()), median_step


def assess_depth_quality(
    dataframe: pd.DataFrame,
    *,
    depth_column: str = "depth_m",
) -> DepthQCResult:
    if depth_column not in dataframe.columns:
        return DepthQCResult(
            depth_column=depth_column,
            row_count=int(len(dataframe)),
            valid_depth_count=0,
            missing_depth_count=int(len(dataframe)),
            duplicate_depth_count=0,
            non_monotonic_count=0,
            is_monotonic_increasing=False,
            minimum_depth=None,
            maximum_depth=None,
            median_step=None,
            irregular_step_fraction=1.0,
            qc_score=0.0,
            warnings=("Depth column is missing.",),
        )

    depth = _numeric_series(dataframe, depth_column)
    valid_depth = depth.dropna()
    missing_count = int(depth.isna().sum())
    duplicate_count = int(valid_depth.duplicated().sum())
    differences = valid_depth.diff()
    non_monotonic_count = int((differences < 0).sum())
    irregular_fraction, median_step = _irregular_step_fraction(depth)

    completeness_score = 100.0 * (1.0 - missing_count / max(len(depth), 1))
    duplicate_penalty = min(40.0, 100.0 * duplicate_count / max(len(valid_depth), 1))
    monotonic_penalty = min(40.0, 100.0 * non_monotonic_count / max(len(valid_depth), 1))
    irregular_penalty = min(20.0, 20.0 * irregular_fraction)
    score = max(
        0.0,
        completeness_score - duplicate_penalty - monotonic_penalty - irregular_penalty,
    )

    warnings: list[str] = []
    if missing_count:
        warnings.append(f"{missing_count} depth values are missing or invalid.")
    if duplicate_count:
        warnings.append(f"{duplicate_count} duplicate depth values were detected.")
    if non_monotonic_count:
        warnings.append(f"{non_monotonic_count} negative depth increments were detected.")
    if irregular_fraction > 0.20:
        warnings.append("Depth sampling is substantially irregular.")

    return DepthQCResult(
        depth_column=depth_column,
        row_count=int(len(dataframe)),
        valid_depth_count=int(valid_depth.size),
        missing_depth_count=missing_count,
        duplicate_depth_count=duplicate_count,
        non_monotonic_count=non_monotonic_count,
        is_monotonic_increasing=bool(valid_depth.is_monotonic_increasing),
        minimum_depth=_safe_float(valid_depth.min()) if not valid_depth.empty else None,
        maximum_depth=_safe_float(valid_depth.max()) if not valid_depth.empty else None,
        median_step=median_step,
        irregular_step_fraction=round(irregular_fraction, 6),
        qc_score=round(score, 2),
        warnings=tuple(warnings),
    )


def assess_curve_quality(
    dataframe: pd.DataFrame,
    curve: str,
    *,
    physical_ranges: dict[str, tuple[float | None, float | None]] | None = None,
    spike_window: int = 9,
    spike_threshold: float = 4.0,
    flatline_minimum_run: int = 8,
) -> CurveQCResult:
    if curve not in dataframe.columns:
        raise KeyError(f"Curve '{curve}' does not exist in the dataframe.")

    ranges = physical_ranges or PHYSICAL_RANGES
    series = _numeric_series(dataframe, curve)
    row_count = int(len(series))
    valid = series.dropna()
    valid_count = int(valid.size)
    missing_count = int(series.isna().sum())
    null_fraction = missing_count / max(row_count, 1)

    lower, upper = ranges.get(curve, (None, None))
    out_of_range_mask = pd.Series(False, index=series.index)
    if lower is not None:
        out_of_range_mask |= series < lower
    if upper is not None:
        out_of_range_mask |= series > upper
    out_of_range_mask &= series.notna()

    spike_mask = _detect_spikes(series, window=spike_window, threshold=spike_threshold)
    flatline_mask = _detect_flatlines(series, minimum_run=flatline_minimum_run)

    out_of_range_count = int(out_of_range_mask.sum())
    spike_count = int(spike_mask.sum())
    flatline_count = int(flatline_mask.sum())
    out_of_range_fraction = out_of_range_count / max(valid_count, 1)
    spike_fraction = spike_count / max(valid_count, 1)
    flatline_fraction = flatline_count / max(valid_count, 1)
    constant_curve = bool(valid_count > 1 and valid.nunique(dropna=True) <= 1)

    completeness_component = 100.0 * (1.0 - null_fraction)
    range_component = 100.0 * (1.0 - min(out_of_range_fraction, 1.0))
    spike_component = 100.0 * (1.0 - min(spike_fraction * 2.0, 1.0))
    flatline_component = 100.0 * (1.0 - min(flatline_fraction * 2.0, 1.0))
    score = (
        0.40 * completeness_component
        + 0.30 * range_component
        + 0.15 * spike_component
        + 0.15 * flatline_component
    )
    if constant_curve:
        score = min(score, 20.0)

    warnings: list[str] = []
    if null_fraction > 0.20:
        warnings.append(f"{null_fraction:.1%} of values are missing.")
    if out_of_range_fraction > 0.01:
        warnings.append(
            f"{out_of_range_fraction:.1%} of valid values are outside the expected physical range."
        )
    if spike_fraction > 0.01:
        warnings.append(f"{spike_fraction:.1%} of valid values were flagged as spikes.")
    if flatline_fraction > 0.05:
        warnings.append(
            f"{flatline_fraction:.1%} of valid values are part of flat-line runs."
        )
    if constant_curve:
        warnings.append("The curve is constant across all valid samples.")

    return CurveQCResult(
        curve=curve,
        unit=canonical_unit_for(curve),
        row_count=row_count,
        valid_count=valid_count,
        missing_count=missing_count,
        null_fraction=round(null_fraction, 6),
        minimum=_safe_float(valid.min()) if not valid.empty else None,
        maximum=_safe_float(valid.max()) if not valid.empty else None,
        mean=_safe_float(valid.mean()) if not valid.empty else None,
        median=_safe_float(valid.median()) if not valid.empty else None,
        standard_deviation=_safe_float(valid.std(ddof=0)) if not valid.empty else None,
        out_of_range_count=out_of_range_count,
        out_of_range_fraction=round(out_of_range_fraction, 6),
        flatline_count=flatline_count,
        flatline_fraction=round(flatline_fraction, 6),
        spike_count=spike_count,
        spike_fraction=round(spike_fraction, 6),
        constant_curve=constant_curve,
        qc_score=round(max(0.0, min(100.0, score)), 2),
        warnings=tuple(warnings),
    )


def assess_washout(
    dataframe: pd.DataFrame,
    *,
    caliper_column: str = "caliper_in",
    bit_size_column: str = "bit_size_in",
    nominal_bit_size_in: float = 8.5,
    threshold_in: float = 1.0,
    severe_threshold_in: float = 2.5,
) -> WashoutQCResult:
    if caliper_column not in dataframe.columns:
        return WashoutQCResult(
            available=False,
            assessed_count=0,
            washout_count=0,
            washout_fraction=0.0,
            threshold_in=float(threshold_in),
            severe_washout_count=0,
            qc_score=100.0,
            warnings=("Caliper curve is unavailable; washout was not assessed.",),
        )

    caliper = _numeric_series(dataframe, caliper_column)
    if bit_size_column in dataframe.columns:
        bit_size = _numeric_series(dataframe, bit_size_column)
    else:
        bit_size = pd.Series(float(nominal_bit_size_in), index=dataframe.index, dtype=float)

    valid_mask = caliper.notna() & bit_size.notna()
    difference = caliper - bit_size
    washout_mask = valid_mask & (difference > threshold_in)
    severe_mask = valid_mask & (difference > severe_threshold_in)

    assessed_count = int(valid_mask.sum())
    washout_count = int(washout_mask.sum())
    severe_count = int(severe_mask.sum())
    washout_fraction = washout_count / max(assessed_count, 1)
    score = max(
        0.0,
        100.0
        - 70.0 * washout_fraction
        - 30.0 * severe_count / max(assessed_count, 1),
    )

    warnings: list[str] = []
    if bit_size_column not in dataframe.columns:
        warnings.append(
            f"Bit size was unavailable; a nominal {nominal_bit_size_in:.1f}-inch hole size was used."
        )
    if washout_fraction > 0.10:
        warnings.append(
            f"Possible washout affects {washout_fraction:.1%} of assessed samples."
        )
    if severe_count:
        warnings.append(f"{severe_count} samples exceed the severe washout threshold.")

    return WashoutQCResult(
        available=True,
        assessed_count=assessed_count,
        washout_count=washout_count,
        washout_fraction=round(washout_fraction, 6),
        threshold_in=float(threshold_in),
        severe_washout_count=severe_count,
        qc_score=round(score, 2),
        warnings=tuple(warnings),
    )


def estimate_interpolatable_nulls(
    dataframe: pd.DataFrame,
    *,
    maximum_gap: int = 3,
    excluded_columns: Iterable[str] = ("well_id", "date"),
) -> int:
    excluded = set(excluded_columns)
    total = 0
    for column in dataframe.columns:
        if column in excluded:
            continue
        numeric = _numeric_series(dataframe, column)
        missing = numeric.isna()
        if not missing.any():
            continue
        groups = missing.ne(missing.shift(fill_value=False)).cumsum()
        for _, indices in missing.groupby(groups).groups.items():
            index_list = list(indices)
            if not index_list or not bool(missing.loc[index_list[0]]):
                continue
            if len(index_list) > maximum_gap:
                continue
            first_position = numeric.index.get_loc(index_list[0])
            last_position = numeric.index.get_loc(index_list[-1])
            bounded_left = first_position > 0 and pd.notna(numeric.iloc[first_position - 1])
            bounded_right = last_position < len(numeric) - 1 and pd.notna(
                numeric.iloc[last_position + 1]
            )
            if bounded_left and bounded_right:
                total += len(index_list)
    return int(total)


def assess_dataset_quality(
    dataframe: pd.DataFrame,
    *,
    depth_column: str = "depth_m",
    physical_ranges: dict[str, tuple[float | None, float | None]] | None = None,
    weights: dict[str, float] | None = None,
    metadata: dict[str, Any] | None = None,
    provenance: Iterable[dict[str, Any]] | None = None,
) -> DatasetQCResult:
    if dataframe.empty:
        empty_depth = assess_depth_quality(dataframe, depth_column=depth_column)
        empty_washout = assess_washout(dataframe)
        return DatasetQCResult(
            qc_score=0.0,
            quality_class="critical",
            row_count=0,
            column_count=int(len(dataframe.columns)),
            numeric_curve_count=0,
            completeness_score=0.0,
            physical_validity_score=0.0,
            depth_quality_score=0.0,
            signal_quality_score=0.0,
            ai_readiness_score=0.0,
            ai_ready=False,
            missing_ai_curves=tuple(AI_REQUIRED_CURVES),
            duplicate_depth_count=0,
            interpolatable_null_count=0,
            total_null_count=0,
            total_out_of_range_count=0,
            total_spike_count=0,
            total_flatline_count=0,
            depth=empty_depth,
            washout=empty_washout,
            curves=(),
            warnings=("The dataset is empty.",),
            provenance=tuple(provenance or ()),
            metadata=dict(metadata or {}),
        )

    ranges = physical_ranges or PHYSICAL_RANGES
    normalised_weights = _normalise_weights(weights)
    numeric_columns: list[str] = []
    for column in dataframe.columns:
        if column in {"well_id", "date"}:
            continue
        converted = pd.to_numeric(dataframe[column], errors="coerce")
        if converted.notna().any():
            numeric_columns.append(str(column))

    curve_results = tuple(
        assess_curve_quality(dataframe, curve, physical_ranges=ranges)
        for curve in numeric_columns
        if curve != depth_column
    )
    depth_result = assess_depth_quality(dataframe, depth_column=depth_column)
    washout_result = assess_washout(dataframe)

    readiness = ai_readiness(dataframe.columns)
    missing_curves = tuple(str(curve) for curve in readiness["required_missing"])
    ai_ready = bool(readiness["ready"])
    ai_readiness_score = (
        100.0
        * int(readiness["available_required_count"])
        / max(int(readiness["required_curve_count"]), 1)
    )

    total_cells = max(int(dataframe.shape[0] * max(len(numeric_columns), 1)), 1)
    total_null_count = int(
        sum(_numeric_series(dataframe, column).isna().sum() for column in numeric_columns)
    )
    completeness_score = max(0.0, 100.0 * (1.0 - total_null_count / total_cells))

    total_valid_curve_values = sum(result.valid_count for result in curve_results)
    total_out_of_range_count = sum(result.out_of_range_count for result in curve_results)
    total_spike_count = sum(result.spike_count for result in curve_results)
    total_flatline_count = sum(result.flatline_count for result in curve_results)

    physical_validity_score = max(
        0.0,
        100.0 * (1.0 - total_out_of_range_count / max(total_valid_curve_values, 1)),
    )

    if curve_results:
        curve_signal_scores = [
            max(0.0, 100.0 * (1.0 - result.spike_fraction - result.flatline_fraction))
            for result in curve_results
        ]
        signal_quality_score = float(np.mean(curve_signal_scores))
    else:
        signal_quality_score = 0.0

    weighted_score = (
        normalised_weights["completeness"] * completeness_score
        + normalised_weights["physical_validity"] * physical_validity_score
        + normalised_weights["depth_quality"] * depth_result.qc_score
        + normalised_weights["signal_quality"] * signal_quality_score
        + normalised_weights["ai_readiness"] * ai_readiness_score
    )
    if washout_result.available:
        weighted_score -= min(10.0, 10.0 * washout_result.washout_fraction)
    weighted_score = max(0.0, min(100.0, weighted_score))

    warnings: list[str] = []
    warnings.extend(depth_result.warnings)
    warnings.extend(washout_result.warnings)
    for result in curve_results:
        for warning in result.warnings:
            warnings.append(f"{result.curve}: {warning}")
    if missing_curves:
        warnings.append(
            "AI inference is not ready. Missing required curves: "
            + ", ".join(missing_curves)
            + "."
        )
    low_quality_curves = [result.curve for result in curve_results if result.qc_score < 60.0]
    if low_quality_curves:
        warnings.append(
            "Low-quality curves requiring review: " + ", ".join(low_quality_curves) + "."
        )

    return DatasetQCResult(
        qc_score=round(weighted_score, 2),
        quality_class=_score_to_quality_class(weighted_score),
        row_count=int(len(dataframe)),
        column_count=int(len(dataframe.columns)),
        numeric_curve_count=len(numeric_columns),
        completeness_score=round(completeness_score, 2),
        physical_validity_score=round(physical_validity_score, 2),
        depth_quality_score=round(depth_result.qc_score, 2),
        signal_quality_score=round(signal_quality_score, 2),
        ai_readiness_score=round(ai_readiness_score, 2),
        ai_ready=ai_ready,
        missing_ai_curves=missing_curves,
        duplicate_depth_count=depth_result.duplicate_depth_count,
        interpolatable_null_count=estimate_interpolatable_nulls(dataframe),
        total_null_count=total_null_count,
        total_out_of_range_count=total_out_of_range_count,
        total_spike_count=total_spike_count,
        total_flatline_count=total_flatline_count,
        depth=depth_result,
        washout=washout_result,
        curves=curve_results,
        warnings=tuple(dict.fromkeys(warnings)),
        provenance=tuple(provenance or ()),
        metadata=dict(metadata or {}),
    )


def qc_summary(dataframe: pd.DataFrame, **kwargs: Any) -> dict[str, Any]:
    return assess_dataset_quality(dataframe, **kwargs).to_dict()
