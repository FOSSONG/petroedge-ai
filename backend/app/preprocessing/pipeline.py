from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

import numpy as np
import pandas as pd

from app.preprocessing.curve_aliases import (
    AI_REQUIRED_CURVES,
    CurveAliasResult,
    ai_readiness,
    map_curve_columns,
)
from app.preprocessing.qc import (
    PHYSICAL_RANGES,
    DatasetQCResult,
    assess_dataset_quality,
)


STANDARD_NULL_VALUES: tuple[float, ...] = (
    -999.25,
    -999.0,
    -9999.0,
    -99999.0,
    -999999.0,
)


DEFAULT_INTERPOLATION_CURVES: tuple[str, ...] = (
    "gamma_ray_api",
    "resistivity_ohmm",
    "medium_resistivity_ohmm",
    "shallow_resistivity_ohmm",
    "micro_resistivity_ohmm",
    "density_gcc",
    "density_correction_gcc",
    "neutron_porosity_vv",
    "sonic_usft",
    "shear_sonic_usft",
    "caliper_in",
    "bit_size_in",
    "sp_mv",
    "photoelectric_factor",
    "thorium_ppm",
    "uranium_ppm",
    "potassium_pct",
    "rop_mph",
    "mud_weight_ppg",
    "mud_resistivity_ohmm",
    "mud_temperature_c",
    "temperature_c",
    "pressure_psi",
)


DEFAULT_SMOOTHING_CURVES: tuple[str, ...] = (
    "gamma_ray_api",
    "density_gcc",
    "neutron_porosity_vv",
    "sonic_usft",
    "caliper_in",
)


@dataclass(frozen=True)
class PipelineConfig:
    depth_column: str = "depth_m"
    preserve_unmatched_columns: bool = True
    replace_standard_nulls: bool = True
    sort_depth: bool = True
    remove_missing_depth: bool = True
    remove_duplicate_depths: bool = True
    duplicate_keep: str = "first"
    convert_numeric_columns: bool = True
    interpolate_short_gaps: bool = True
    interpolation_limit: int = 3
    interpolation_method: str = "linear"
    despike: bool = True
    hampel_window: int = 9
    hampel_threshold: float = 4.0
    replace_spikes_with_rolling_median: bool = True
    smooth: bool = False
    smoothing_window: int = 5
    clip_to_physical_ranges: bool = False
    add_default_caliper: bool = True
    default_caliper_in: float = 8.5
    add_default_bit_size: bool = False
    default_bit_size_in: float = 8.5
    interpolation_curves: tuple[str, ...] = DEFAULT_INTERPOLATION_CURVES
    smoothing_curves: tuple[str, ...] = DEFAULT_SMOOTHING_CURVES


@dataclass(frozen=True)
class PreprocessingResult:
    dataframe: pd.DataFrame
    qc_before: DatasetQCResult
    qc_after: DatasetQCResult
    provenance: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    curve_mapping: dict[str, str]
    duplicate_curve_candidates: dict[str, list[str]]
    unmatched_columns: tuple[str, ...]
    ai_readiness: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "rows": int(len(self.dataframe)),
            "columns": int(len(self.dataframe.columns)),
            "qc_before": self.qc_before.to_dict(),
            "qc_after": self.qc_after.to_dict(),
            "provenance": list(self.provenance),
            "warnings": list(self.warnings),
            "curve_mapping": dict(self.curve_mapping),
            "duplicate_curve_candidates": dict(
                self.duplicate_curve_candidates
            ),
            "unmatched_columns": list(self.unmatched_columns),
            "ai_readiness": dict(self.ai_readiness),
            "metadata": dict(self.metadata),
        }


def _record_step(
    provenance: list[dict[str, Any]],
    step: str,
    **details: Any,
) -> None:
    payload = {"step": step}
    payload.update(details)
    provenance.append(payload)


def _numeric_columns(
    dataframe: pd.DataFrame,
    *,
    excluded: Iterable[str] = ("well_id", "date"),
) -> list[str]:
    excluded_set = set(excluded)
    columns: list[str] = []

    for column in dataframe.columns:
        if column in excluded_set:
            continue

        converted = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

        if converted.notna().any():
            columns.append(str(column))

    return columns


def _replace_null_codes(
    dataframe: pd.DataFrame,
    *,
    standard_nulls: Iterable[float] = STANDARD_NULL_VALUES,
) -> tuple[pd.DataFrame, int]:
    cleaned = dataframe.copy()
    replaced_count = 0

    for column in _numeric_columns(cleaned):
        series = pd.to_numeric(
            cleaned[column],
            errors="coerce",
        ).astype(float)

        for null_value in standard_nulls:
            mask = np.isclose(
                series.to_numpy(dtype=float),
                float(null_value),
                rtol=0.0,
                atol=1e-8,
                equal_nan=False,
            )

            count = int(mask.sum())

            if count:
                series.loc[mask] = np.nan
                replaced_count += count

        non_finite_mask = ~np.isfinite(
            series.to_numpy(dtype=float)
        ) & series.notna().to_numpy()

        non_finite_count = int(non_finite_mask.sum())

        if non_finite_count:
            series.loc[non_finite_mask] = np.nan
            replaced_count += non_finite_count

        cleaned[column] = series

    return cleaned, replaced_count


def _coerce_numeric_columns(
    dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    converted = dataframe.copy()
    conversion_count = 0

    recognised_non_numeric = {"well_id", "date"}

    for column in converted.columns:
        if column in recognised_non_numeric:
            continue

        original_non_null = int(
            pd.Series(converted[column]).notna().sum()
        )

        numeric = pd.to_numeric(
            converted[column],
            errors="coerce",
        )

        numeric_non_null = int(numeric.notna().sum())

        if numeric_non_null > 0:
            converted[column] = numeric
            conversion_count += max(
                0,
                original_non_null - numeric_non_null,
            )

    return converted, conversion_count


def _sort_and_clean_depth(
    dataframe: pd.DataFrame,
    config: PipelineConfig,
) -> tuple[pd.DataFrame, dict[str, int | bool]]:
    cleaned = dataframe.copy()
    depth_column = config.depth_column

    details: dict[str, int | bool] = {
        "missing_depth_rows_removed": 0,
        "duplicate_depth_rows_removed": 0,
        "depth_sorted": False,
    }

    if depth_column not in cleaned.columns:
        return cleaned, details

    cleaned[depth_column] = pd.to_numeric(
        cleaned[depth_column],
        errors="coerce",
    )

    if config.remove_missing_depth:
        missing_count = int(
            cleaned[depth_column].isna().sum()
        )

        if missing_count:
            cleaned = cleaned.dropna(
                subset=[depth_column]
            )

        details["missing_depth_rows_removed"] = missing_count

    if config.remove_duplicate_depths:
        duplicate_count = int(
            cleaned[depth_column].duplicated().sum()
        )

        if duplicate_count:
            cleaned = cleaned.drop_duplicates(
                subset=[depth_column],
                keep=config.duplicate_keep,
            )

        details["duplicate_depth_rows_removed"] = duplicate_count

    if (
        config.sort_depth
        and not cleaned[depth_column].is_monotonic_increasing
    ):
        cleaned = cleaned.sort_values(
            depth_column,
            kind="mergesort",
        )
        details["depth_sorted"] = True

    return cleaned.reset_index(drop=True), details


def _interpolate_short_gaps(
    dataframe: pd.DataFrame,
    *,
    curves: Iterable[str],
    limit: int,
    method: str,
) -> tuple[pd.DataFrame, dict[str, int]]:
    interpolated = dataframe.copy()
    counts: dict[str, int] = {}

    for curve in curves:
        if curve not in interpolated.columns:
            continue

        series = pd.to_numeric(
            interpolated[curve],
            errors="coerce",
        ).astype(float)

        before = int(series.isna().sum())

        if before == 0:
            counts[curve] = 0
            continue

        filled = series.interpolate(
            method=method,
            limit=max(1, int(limit)),
            limit_direction="both",
            limit_area="inside",
        )

        after = int(filled.isna().sum())
        counts[curve] = before - after
        interpolated[curve] = filled

    return interpolated, counts


def _hampel_mask(
    series: pd.Series,
    *,
    window: int,
    threshold: float,
) -> tuple[pd.Series, pd.Series]:
    numeric = pd.to_numeric(
        series,
        errors="coerce",
    ).astype(float)

    if len(numeric) < 5:
        empty_mask = pd.Series(
            False,
            index=numeric.index,
        )
        return empty_mask, numeric.copy()

    window = max(5, int(window))

    if window % 2 == 0:
        window += 1

    rolling_median = numeric.rolling(
        window=window,
        center=True,
        min_periods=max(3, window // 3),
    ).median()

    absolute_deviation = (
        numeric - rolling_median
    ).abs()

    rolling_mad = absolute_deviation.rolling(
        window=window,
        center=True,
        min_periods=max(3, window // 3),
    ).median()

    robust_sigma = 1.4826 * rolling_mad

    global_scale = float(
        np.nanmedian(
            robust_sigma.to_numpy(dtype=float)
        )
    )

    if not np.isfinite(global_scale) or global_scale <= 0:
        global_scale = float(
            np.nanstd(
                numeric.to_numpy(dtype=float)
            )
        )

    if not np.isfinite(global_scale) or global_scale <= 0:
        mask = pd.Series(
            False,
            index=numeric.index,
        )
        return mask, rolling_median

    robust_sigma = robust_sigma.fillna(global_scale)
    robust_sigma = robust_sigma.clip(
        lower=max(global_scale * 0.05, 1e-12)
    )

    mask = (
        absolute_deviation
        > float(threshold) * robust_sigma
    ).fillna(False)

    return mask, rolling_median


def _despike_dataframe(
    dataframe: pd.DataFrame,
    *,
    curves: Iterable[str],
    window: int,
    threshold: float,
    replace_with_median: bool,
) -> tuple[pd.DataFrame, dict[str, int]]:
    cleaned = dataframe.copy()
    counts: dict[str, int] = {}

    for curve in curves:
        if curve not in cleaned.columns:
            continue

        series = pd.to_numeric(
            cleaned[curve],
            errors="coerce",
        ).astype(float)

        mask, rolling_median = _hampel_mask(
            series,
            window=window,
            threshold=threshold,
        )

        count = int(mask.sum())
        counts[curve] = count

        if count and replace_with_median:
            replacement = rolling_median.where(
                rolling_median.notna(),
                series,
            )
            series.loc[mask] = replacement.loc[mask]
            cleaned[curve] = series

    return cleaned, counts


def _rolling_median_smooth(
    dataframe: pd.DataFrame,
    *,
    curves: Iterable[str],
    window: int,
) -> tuple[pd.DataFrame, list[str]]:
    smoothed = dataframe.copy()
    applied: list[str] = []

    window = max(3, int(window))

    if window % 2 == 0:
        window += 1

    for curve in curves:
        if curve not in smoothed.columns:
            continue

        series = pd.to_numeric(
            smoothed[curve],
            errors="coerce",
        ).astype(float)

        if series.notna().sum() < window:
            continue

        rolling = series.rolling(
            window=window,
            center=True,
            min_periods=1,
        ).median()

        smoothed[curve] = rolling
        applied.append(curve)

    return smoothed, applied


def _clip_physical_ranges(
    dataframe: pd.DataFrame,
    *,
    physical_ranges: dict[str, tuple[float | None, float | None]],
) -> tuple[pd.DataFrame, dict[str, int]]:
    clipped = dataframe.copy()
    counts: dict[str, int] = {}

    for curve, (lower, upper) in physical_ranges.items():
        if curve not in clipped.columns:
            continue

        series = pd.to_numeric(
            clipped[curve],
            errors="coerce",
        ).astype(float)

        mask = pd.Series(
            False,
            index=series.index,
        )

        if lower is not None:
            mask |= series < lower

        if upper is not None:
            mask |= series > upper

        count = int(mask.sum())
        counts[curve] = count

        if lower is not None or upper is not None:
            clipped[curve] = series.clip(
                lower=lower,
                upper=upper,
            )

    return clipped, counts


def _add_default_curves(
    dataframe: pd.DataFrame,
    config: PipelineConfig,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    augmented = dataframe.copy()
    added: list[dict[str, Any]] = []

    if (
        config.add_default_caliper
        and "caliper_in" not in augmented.columns
    ):
        augmented["caliper_in"] = float(
            config.default_caliper_in
        )
        added.append(
            {
                "curve": "caliper_in",
                "value": float(
                    config.default_caliper_in
                ),
                "reason": "required by current inference interface",
            }
        )

    if (
        config.add_default_bit_size
        and "bit_size_in" not in augmented.columns
    ):
        augmented["bit_size_in"] = float(
            config.default_bit_size_in
        )
        added.append(
            {
                "curve": "bit_size_in",
                "value": float(
                    config.default_bit_size_in
                ),
                "reason": "configured nominal borehole size",
            }
        )

    return augmented, added


def run_preprocessing_pipeline(
    dataframe: pd.DataFrame,
    *,
    config: PipelineConfig | None = None,
    metadata: dict[str, Any] | None = None,
) -> PreprocessingResult:
    """
    Run the PetroEdge preprocessing and quality-control workflow.

    The function is deliberately deterministic. Every transformation is
    recorded in ``provenance`` so processed datasets remain auditable.
    """

    selected_config = config or PipelineConfig()
    working = dataframe.copy()

    provenance: list[dict[str, Any]] = []
    warnings: list[str] = []

    _record_step(
        provenance,
        "pipeline_started",
        input_rows=int(len(working)),
        input_columns=int(len(working.columns)),
    )

    alias_result: CurveAliasResult = map_curve_columns(
        working,
        preserve_unmatched=selected_config.preserve_unmatched_columns,
        prefer_existing_canonical=True,
    )

    working = alias_result.dataframe

    _record_step(
        provenance,
        "curve_alias_mapping",
        mapped_columns=dict(alias_result.mapping),
        unmatched_columns=list(alias_result.unmatched_columns),
        duplicate_candidates=dict(
            alias_result.duplicate_candidates
        ),
    )

    if alias_result.duplicate_candidates:
        warnings.append(
            "Multiple source columns matched the same canonical curve. "
            "The preferred column was retained and alternatives were recorded."
        )

    if selected_config.convert_numeric_columns:
        working, failed_conversion_count = _coerce_numeric_columns(
            working
        )

        _record_step(
            provenance,
            "numeric_conversion",
            invalid_values_converted_to_null=failed_conversion_count,
        )

    if selected_config.replace_standard_nulls:
        working, replaced_null_count = _replace_null_codes(
            working
        )

        _record_step(
            provenance,
            "standard_null_replacement",
            values_replaced=replaced_null_count,
            null_codes=list(STANDARD_NULL_VALUES),
        )

    qc_before = assess_dataset_quality(
        working,
        depth_column=selected_config.depth_column,
        metadata=metadata,
        provenance=provenance,
    )

    _record_step(
        provenance,
        "qc_before_cleaning",
        qc_score=qc_before.qc_score,
        quality_class=qc_before.quality_class,
    )

    if selected_config.depth_column not in working.columns:
        warnings.append(
            "The canonical depth column is missing. Depth cleaning could not "
            "be performed."
        )
    else:
        working, depth_details = _sort_and_clean_depth(
            working,
            selected_config,
        )

        _record_step(
            provenance,
            "depth_cleaning",
            **depth_details,
        )

    working, added_defaults = _add_default_curves(
        working,
        selected_config,
    )

    if added_defaults:
        _record_step(
            provenance,
            "default_curve_assignment",
            curves=added_defaults,
        )
        warnings.append(
            "One or more missing operational curves were assigned configured "
            "default values. Review provenance before production use."
        )

    if selected_config.interpolate_short_gaps:
        working, interpolation_counts = _interpolate_short_gaps(
            working,
            curves=selected_config.interpolation_curves,
            limit=selected_config.interpolation_limit,
            method=selected_config.interpolation_method,
        )

        total_interpolated = int(
            sum(interpolation_counts.values())
        )

        _record_step(
            provenance,
            "short_gap_interpolation",
            method=selected_config.interpolation_method,
            maximum_gap=selected_config.interpolation_limit,
            values_interpolated=total_interpolated,
            per_curve=interpolation_counts,
        )

    if selected_config.despike:
        despike_curves = [
            curve
            for curve in _numeric_columns(working)
            if curve != selected_config.depth_column
        ]

        working, spike_counts = _despike_dataframe(
            working,
            curves=despike_curves,
            window=selected_config.hampel_window,
            threshold=selected_config.hampel_threshold,
            replace_with_median=(
                selected_config.replace_spikes_with_rolling_median
            ),
        )

        _record_step(
            provenance,
            "hampel_despiking",
            window=selected_config.hampel_window,
            threshold=selected_config.hampel_threshold,
            spikes_detected=int(sum(spike_counts.values())),
            per_curve=spike_counts,
            values_replaced=bool(
                selected_config.replace_spikes_with_rolling_median
            ),
        )

    if selected_config.smooth:
        working, smoothed_curves = _rolling_median_smooth(
            working,
            curves=selected_config.smoothing_curves,
            window=selected_config.smoothing_window,
        )

        _record_step(
            provenance,
            "rolling_median_smoothing",
            window=selected_config.smoothing_window,
            curves=smoothed_curves,
        )

    if selected_config.clip_to_physical_ranges:
        working, clipping_counts = _clip_physical_ranges(
            working,
            physical_ranges=PHYSICAL_RANGES,
        )

        _record_step(
            provenance,
            "physical_range_clipping",
            values_clipped=int(sum(clipping_counts.values())),
            per_curve=clipping_counts,
        )
        warnings.append(
            "Physical-range clipping was enabled. Clipped values should be "
            "reviewed because extreme measurements may represent real geology."
        )

    working = working.reset_index(drop=True)

    qc_after = assess_dataset_quality(
        working,
        depth_column=selected_config.depth_column,
        metadata=metadata,
        provenance=provenance,
    )

    readiness = ai_readiness(working.columns)

    _record_step(
        provenance,
        "qc_after_cleaning",
        qc_score=qc_after.qc_score,
        quality_class=qc_after.quality_class,
        ai_ready=bool(readiness["ready"]),
        missing_ai_curves=list(
            readiness["required_missing"]
        ),
    )

    if not readiness["ready"]:
        warnings.append(
            "AI inference is not ready because required curves are missing: "
            + ", ".join(
                str(curve)
                for curve in readiness["required_missing"]
            )
            + "."
        )

    if qc_after.qc_score < qc_before.qc_score:
        warnings.append(
            "The post-processing QC score is lower than the pre-processing "
            "score. Review the provenance and configuration."
        )

    _record_step(
        provenance,
        "pipeline_completed",
        output_rows=int(len(working)),
        output_columns=int(len(working.columns)),
        qc_improvement=round(
            qc_after.qc_score - qc_before.qc_score,
            2,
        ),
    )

    return PreprocessingResult(
        dataframe=working,
        qc_before=qc_before,
        qc_after=qc_after,
        provenance=tuple(provenance),
        warnings=tuple(dict.fromkeys(warnings)),
        curve_mapping=dict(alias_result.mapping),
        duplicate_curve_candidates=dict(
            alias_result.duplicate_candidates
        ),
        unmatched_columns=tuple(
            alias_result.unmatched_columns
        ),
        ai_readiness=dict(readiness),
        metadata=dict(metadata or {}),
    )


def preprocess_dataframe(
    dataframe: pd.DataFrame,
    *,
    config: PipelineConfig | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Compatibility wrapper returning the cleaned dataframe and summary.
    """

    result = run_preprocessing_pipeline(
        dataframe,
        config=config,
        metadata=metadata,
    )

    return result.dataframe, result.summary()
