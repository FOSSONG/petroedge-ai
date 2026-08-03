from __future__ import annotations

import json
import logging
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = BACKEND_ROOT / "data"
DATASET_ROOT = DATA_ROOT / "datasets"
PREDICTION_ROOT = DATA_ROOT / "predictions"
STREAM_ROOT = DATA_ROOT / "streams"
ALERT_ROOT = DATA_ROOT / "alerts"
REPORT_ROOT = DATA_ROOT / "reports"

DEFAULT_RECENT_LIMIT = 10
MAX_RECENT_LIMIT = 100


@dataclass(frozen=True)
class MetricCard:
    key: str
    label: str
    value: Any
    unit: str | None = None
    status: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DashboardSnapshot:
    generated_at: str
    overview: dict[str, Any]
    operational: dict[str, Any]
    data_quality: dict[str, Any]
    model_performance: dict[str, Any]
    reservoir_insights: dict[str, Any]
    alert_metrics: dict[str, Any]
    reporting_metrics: dict[str, Any]
    recent_activity: list[dict[str, Any]]
    cards: list[MetricCard]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "overview": self.overview,
            "operational": self.operational,
            "data_quality": self.data_quality,
            "model_performance": self.model_performance,
            "reservoir_insights": self.reservoir_insights,
            "alert_metrics": self.alert_metrics,
            "reporting_metrics": self.reporting_metrics,
            "recent_activity": self.recent_activity,
            "cards": [card.to_dict() for card in self.cards],
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def _round(value: Any, digits: int = 3) -> float | None:
    number = _safe_float(value)
    if number is None:
        return None
    return round(number, digits)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Could not read JSON file %s", path)
        return {}

    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []

    try:
        with path.open("r", encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if isinstance(payload, dict):
                    records.append(payload)
    except Exception:
        logger.exception("Could not read JSONL file %s", path)

    return records


def _iter_metadata(root: Path) -> Iterable[dict[str, Any]]:
    if not root.exists():
        return

    for directory in root.iterdir():
        if not directory.is_dir():
            continue

        metadata = _read_json(directory / "metadata.json")
        if metadata:
            metadata.setdefault("_directory", str(directory))
            metadata.setdefault("_id", directory.name)
            yield metadata


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None

    try:
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        return timestamp.to_pydatetime()
    except Exception:
        return None


def _latest_timestamp(metadata: Mapping[str, Any]) -> datetime | None:
    candidates = (
        metadata.get("created_at"),
        metadata.get("updated_at"),
        metadata.get("generated_at"),
        metadata.get("started_at"),
        metadata.get("completed_at"),
        metadata.get("timestamp"),
    )

    parsed = [
        value
        for item in candidates
        if (value := _parse_timestamp(item)) is not None
    ]

    return max(parsed) if parsed else None


def _mean(values: Sequence[float]) -> float | None:
    clean = [value for value in values if value is not None]
    return float(np.mean(clean)) if clean else None


class DashboardMetricsService:
    def __init__(self) -> None:
        self.dataset_root = DATASET_ROOT
        self.prediction_root = PREDICTION_ROOT
        self.stream_root = STREAM_ROOT
        self.alert_root = ALERT_ROOT
        self.report_root = REPORT_ROOT

    def build_snapshot(
        self,
        *,
        recent_limit: int = DEFAULT_RECENT_LIMIT,
    ) -> DashboardSnapshot:
        recent_limit = max(
            1,
            min(int(recent_limit), MAX_RECENT_LIMIT),
        )

        datasets = list(_iter_metadata(self.dataset_root))
        predictions = list(_iter_metadata(self.prediction_root))
        streams = list(_iter_metadata(self.stream_root))
        reports = list(_iter_metadata(self.report_root))
        alerts = _read_jsonl(self.alert_root / "alerts.jsonl")

        overview = self._overview(
            datasets=datasets,
            predictions=predictions,
            streams=streams,
            reports=reports,
            alerts=alerts,
        )

        operational = self._operational_metrics(streams)
        data_quality = self._data_quality_metrics(datasets)
        model_performance = self._model_metrics(predictions)
        reservoir_insights = self._reservoir_metrics(predictions)
        alert_metrics = self._alert_metrics(alerts)
        reporting_metrics = self._report_metrics(reports)
        recent_activity = self._recent_activity(
            datasets=datasets,
            predictions=predictions,
            streams=streams,
            reports=reports,
            alerts=alerts,
            limit=recent_limit,
        )

        cards = self._cards(
            overview=overview,
            operational=operational,
            data_quality=data_quality,
            reservoir=reservoir_insights,
            alerts=alert_metrics,
            reports=reporting_metrics,
        )

        return DashboardSnapshot(
            generated_at=_utc_now(),
            overview=overview,
            operational=operational,
            data_quality=data_quality,
            model_performance=model_performance,
            reservoir_insights=reservoir_insights,
            alert_metrics=alert_metrics,
            reporting_metrics=reporting_metrics,
            recent_activity=recent_activity,
            cards=cards,
        )

    def _overview(
        self,
        *,
        datasets: Sequence[Mapping[str, Any]],
        predictions: Sequence[Mapping[str, Any]],
        streams: Sequence[Mapping[str, Any]],
        reports: Sequence[Mapping[str, Any]],
        alerts: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        active_streams = sum(
            1
            for stream in streams
            if str(stream.get("status", "")).lower()
            in {"active", "running", "resumed"}
        )

        critical_open = sum(
            1
            for alert in alerts
            if str(alert.get("severity", "")).lower() == "critical"
            and str(alert.get("status", "open")).lower() == "open"
        )

        unique_wells = {
            str(value)
            for collection in (datasets, predictions, streams, reports)
            for item in collection
            for key in ("well_id", "Well_ID", "well_name")
            if (value := item.get(key)) not in (None, "")
        }

        return {
            "datasets_total": len(datasets),
            "predictions_total": len(predictions),
            "streams_total": len(streams),
            "active_streams": active_streams,
            "reports_total": len(reports),
            "alerts_total": len(alerts),
            "critical_open_alerts": critical_open,
            "unique_wells": len(unique_wells),
        }

    def _operational_metrics(
        self,
        streams: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        statuses = Counter(
            str(item.get("status", "unknown")).lower()
            for item in streams
        )

        latencies: list[float] = []
        throughputs: list[float] = []
        record_counts: list[float] = []

        for stream in streams:
            for key in (
                "average_latency_ms",
                "avg_latency_ms",
                "latency_ms",
            ):
                value = _safe_float(stream.get(key))
                if value is not None:
                    latencies.append(value)
                    break

            for key in (
                "throughput_records_per_second",
                "records_per_second",
                "throughput",
            ):
                value = _safe_float(stream.get(key))
                if value is not None:
                    throughputs.append(value)
                    break

            for key in (
                "records_received",
                "records_processed",
                "record_count",
            ):
                value = _safe_float(stream.get(key))
                if value is not None:
                    record_counts.append(value)
                    break

        return {
            "status_distribution": dict(statuses),
            "average_latency_ms": _round(_mean(latencies), 2),
            "average_throughput_records_per_second": _round(
                _mean(throughputs),
                2,
            ),
            "records_processed_total": int(sum(record_counts)),
            "active_session_ratio": _round(
                (
                    statuses.get("active", 0)
                    + statuses.get("running", 0)
                    + statuses.get("resumed", 0)
                )
                / len(streams)
                if streams
                else 0.0,
                3,
            ),
        }

    def _data_quality_metrics(
        self,
        datasets: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        qc_scores: list[float] = []
        readiness_scores: list[float] = []
        ai_ready_count = 0
        warning_count = 0
        missing_curves: Counter[str] = Counter()

        for item in datasets:
            qc_score = (
                item.get("qc_score")
                or item.get("quality_score")
            )
            numeric = _safe_float(qc_score)
            if numeric is not None:
                qc_scores.append(numeric)

            readiness = (
                item.get("ai_readiness_score")
                or item.get("readiness_score")
            )
            numeric = _safe_float(readiness)
            if numeric is not None:
                readiness_scores.append(numeric)

            if item.get("ai_ready") is True:
                ai_ready_count += 1

            warnings = item.get("warnings", [])
            if isinstance(warnings, list):
                warning_count += len(warnings)

            missing = item.get("missing_curves", [])
            if isinstance(missing, list):
                missing_curves.update(str(value) for value in missing)

        return {
            "average_qc_score": _round(_mean(qc_scores), 2),
            "average_ai_readiness_score": _round(
                _mean(readiness_scores),
                2,
            ),
            "ai_ready_datasets": ai_ready_count,
            "ai_ready_ratio": _round(
                ai_ready_count / len(datasets)
                if datasets
                else 0.0,
                3,
            ),
            "total_quality_warnings": warning_count,
            "most_frequently_missing_curves": dict(
                missing_curves.most_common(10)
            ),
        }

    def _model_metrics(
        self,
        predictions: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        runtimes: list[float] = []
        confidence_values: list[float] = []
        framework_counter: Counter[str] = Counter()
        fallback_counter: Counter[str] = Counter()
        version_counter: Counter[str] = Counter()

        for item in predictions:
            runtime = (
                item.get("runtime_seconds")
                or item.get("prediction_runtime_seconds")
            )
            numeric = _safe_float(runtime)
            if numeric is not None:
                runtimes.append(numeric)

            confidence = (
                item.get("average_confidence")
                or item.get("mean_confidence")
            )
            numeric = _safe_float(confidence)
            if numeric is not None:
                confidence_values.append(numeric)

            framework = item.get("framework")
            if framework:
                framework_counter[str(framework)] += 1

            version = item.get("model_version")
            if version:
                version_counter[str(version)] += 1

            fallbacks = item.get("fallbacks_used", [])
            if isinstance(fallbacks, list):
                fallback_counter.update(
                    str(value)
                    for value in fallbacks
                )

        return {
            "average_runtime_seconds": _round(_mean(runtimes), 3),
            "average_confidence": _round(
                _mean(confidence_values),
                3,
            ),
            "framework_distribution": dict(framework_counter),
            "model_version_distribution": dict(version_counter),
            "fallback_usage": dict(fallback_counter),
            "predictions_with_fallbacks": sum(
                1
                for item in predictions
                if item.get("fallbacks_used")
            ),
        }

    def _reservoir_metrics(
        self,
        predictions: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        porosity_means: list[float] = []
        sw_means: list[float] = []
        permeability_means: list[float] = []
        hydrocarbon_means: list[float] = []
        lithology_counter: Counter[str] = Counter()
        quality_counter: Counter[str] = Counter()
        interval_count = 0

        for item in predictions:
            summary = item.get("summary", {})
            if not isinstance(summary, Mapping):
                summary = {}

            for target, collection in (
                ("predicted_porosity", porosity_means),
                ("predicted_water_saturation", sw_means),
                ("predicted_permeability_md", permeability_means),
                ("hydrocarbon_probability", hydrocarbon_means),
            ):
                section = summary.get(target, {})
                if isinstance(section, Mapping):
                    value = _safe_float(section.get("mean"))
                    if value is not None:
                        collection.append(value)

            lithology = summary.get("lithology_distribution", {})
            if isinstance(lithology, Mapping):
                lithology_counter.update(
                    {
                        str(key): int(value)
                        for key, value in lithology.items()
                    }
                )

            quality = summary.get("reservoir_quality_distribution", {})
            if isinstance(quality, Mapping):
                quality_counter.update(
                    {
                        str(key): int(value)
                        for key, value in quality.items()
                    }
                )

            intervals = summary.get("reservoir_intervals", [])
            if isinstance(intervals, list):
                interval_count += len(intervals)

        return {
            "average_predicted_porosity": _round(
                _mean(porosity_means),
                4,
            ),
            "average_water_saturation": _round(
                _mean(sw_means),
                4,
            ),
            "average_permeability_md": _round(
                _mean(permeability_means),
                3,
            ),
            "average_hydrocarbon_probability": _round(
                _mean(hydrocarbon_means),
                4,
            ),
            "lithology_distribution": dict(lithology_counter),
            "reservoir_quality_distribution": dict(quality_counter),
            "identified_intervals_total": interval_count,
        }

    def _alert_metrics(
        self,
        alerts: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        severity = Counter(
            str(item.get("severity", "info")).lower()
            for item in alerts
        )
        statuses = Counter(
            str(item.get("status", "open")).lower()
            for item in alerts
        )
        types = Counter(
            str(item.get("alert_type", "unknown"))
            for item in alerts
        )

        open_alerts = statuses.get("open", 0)
        resolved = statuses.get("resolved", 0)

        return {
            "severity_distribution": dict(severity),
            "status_distribution": dict(statuses),
            "type_distribution": dict(types),
            "open_alerts": open_alerts,
            "critical_open_alerts": sum(
                1
                for item in alerts
                if str(item.get("severity", "")).lower() == "critical"
                and str(item.get("status", "open")).lower() == "open"
            ),
            "resolution_ratio": _round(
                resolved / len(alerts)
                if alerts
                else 0.0,
                3,
            ),
        }

    def _report_metrics(
        self,
        reports: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        format_counter: Counter[str] = Counter()
        source_counter: Counter[str] = Counter()

        for report in reports:
            source_counter[
                str(report.get("source_type", "unknown"))
            ] += 1

            files = report.get("generated_files", {})
            if isinstance(files, Mapping):
                format_counter.update(
                    key
                    for key in files.keys()
                    if key != "metadata"
                )

        return {
            "reports_total": len(reports),
            "format_distribution": dict(format_counter),
            "source_distribution": dict(source_counter),
        }

    def _recent_activity(
        self,
        *,
        datasets: Sequence[Mapping[str, Any]],
        predictions: Sequence[Mapping[str, Any]],
        streams: Sequence[Mapping[str, Any]],
        reports: Sequence[Mapping[str, Any]],
        alerts: Sequence[Mapping[str, Any]],
        limit: int,
    ) -> list[dict[str, Any]]:
        activity: list[dict[str, Any]] = []

        def append_items(
            collection: Sequence[Mapping[str, Any]],
            activity_type: str,
        ) -> None:
            for item in collection:
                timestamp = _latest_timestamp(item)
                activity.append(
                    {
                        "type": activity_type,
                        "id": (
                            item.get("_id")
                            or item.get(f"{activity_type}_id")
                            or item.get("source_id")
                        ),
                        "timestamp": (
                            timestamp.isoformat()
                            if timestamp
                            else None
                        ),
                        "well_id": item.get("well_id"),
                        "status": item.get("status"),
                        "title": item.get("title"),
                    }
                )

        append_items(datasets, "dataset")
        append_items(predictions, "prediction")
        append_items(streams, "stream")
        append_items(reports, "report")

        for alert in alerts:
            timestamp = _parse_timestamp(
                alert.get("triggered_at")
            )
            activity.append(
                {
                    "type": "alert",
                    "id": alert.get("alert_id"),
                    "timestamp": (
                        timestamp.isoformat()
                        if timestamp
                        else None
                    ),
                    "well_id": alert.get("well_id"),
                    "status": alert.get("status"),
                    "title": alert.get("rule_name"),
                    "severity": alert.get("severity"),
                }
            )

        activity.sort(
            key=lambda item: item.get("timestamp") or "",
            reverse=True,
        )
        return activity[:limit]

    def _cards(
        self,
        *,
        overview: Mapping[str, Any],
        operational: Mapping[str, Any],
        data_quality: Mapping[str, Any],
        reservoir: Mapping[str, Any],
        alerts: Mapping[str, Any],
        reports: Mapping[str, Any],
    ) -> list[MetricCard]:
        return [
            MetricCard(
                key="datasets_total",
                label="Datasets",
                value=overview.get("datasets_total", 0),
                description="Processed datasets available",
            ),
            MetricCard(
                key="active_streams",
                label="Active Streams",
                value=overview.get("active_streams", 0),
                status=(
                    "healthy"
                    if overview.get("active_streams", 0) > 0
                    else "idle"
                ),
            ),
            MetricCard(
                key="average_qc_score",
                label="Average QC Score",
                value=data_quality.get("average_qc_score"),
                unit="%",
                status=self._score_status(
                    data_quality.get("average_qc_score")
                ),
            ),
            MetricCard(
                key="critical_open_alerts",
                label="Critical Open Alerts",
                value=alerts.get("critical_open_alerts", 0),
                status=(
                    "critical"
                    if alerts.get("critical_open_alerts", 0) > 0
                    else "healthy"
                ),
            ),
            MetricCard(
                key="average_hydrocarbon_probability",
                label="Average HC Probability",
                value=reservoir.get(
                    "average_hydrocarbon_probability"
                ),
                unit="fraction",
            ),
            MetricCard(
                key="average_latency_ms",
                label="Average Stream Latency",
                value=operational.get("average_latency_ms"),
                unit="ms",
            ),
            MetricCard(
                key="reports_total",
                label="Generated Reports",
                value=reports.get("reports_total", 0),
            ),
            MetricCard(
                key="unique_wells",
                label="Wells",
                value=overview.get("unique_wells", 0),
            ),
        ]

    @staticmethod
    def _score_status(value: Any) -> str:
        number = _safe_float(value)
        if number is None:
            return "unknown"
        if number >= 80:
            return "healthy"
        if number >= 60:
            return "warning"
        return "critical"


_dashboard_service: DashboardMetricsService | None = None


def get_dashboard_metrics_service() -> DashboardMetricsService:
    global _dashboard_service

    if _dashboard_service is None:
        _dashboard_service = DashboardMetricsService()

    return _dashboard_service


def build_dashboard_snapshot(
    *,
    recent_limit: int = DEFAULT_RECENT_LIMIT,
) -> DashboardSnapshot:
    return get_dashboard_metrics_service().build_snapshot(
        recent_limit=recent_limit
    )


__all__ = [
    "DashboardMetricsService",
    "DashboardSnapshot",
    "MetricCard",
    "build_dashboard_snapshot",
    "get_dashboard_metrics_service",
]
