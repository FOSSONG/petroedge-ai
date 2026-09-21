from __future__ import annotations

import hashlib
import json
import math
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from app.streaming.channel_registry import resolve_channel


class QualityState(str, Enum):
    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"
    STALE = "STALE"
    CORRECTED = "CORRECTED"
    QUARANTINED = "QUARANTINED"


@dataclass(slots=True)
class StreamState:
    last_sequence: int | None = None
    last_source_timestamp: datetime | None = None


_UNIT_FACTORS: dict[tuple[str, str], tuple[float, float]] = {
    ("ft", "m"): (0.3048, 0.0),
    ("m", "m"): (1.0, 0.0),
    ("ohmm", "ohm.m"): (1.0, 0.0),
    ("ohm.m", "ohm.m"): (1.0, 0.0),
    ("api", "API"): (1.0, 0.0),
    ("g/cc", "g/cm3"): (1.0, 0.0),
    ("g/cm3", "g/cm3"): (1.0, 0.0),
    ("v/v", "v/v"): (1.0, 0.0),
    ("%", "v/v"): (0.01, 0.0),
    ("us/ft", "us/ft"): (1.0, 0.0),
    ("in", "in"): (1.0, 0.0),
    ("psi", "psi"): (1.0, 0.0),
    ("degc", "degC"): (1.0, 0.0),
    ("c", "degC"): (1.0, 0.0),
    ("degf", "degC"): (5.0 / 9.0, -32.0 * 5.0 / 9.0),
    ("f", "degC"): (5.0 / 9.0, -32.0 * 5.0 / 9.0),
    ("gpm", "gpm"): (1.0, 0.0),
    ("bbl", "bbl"): (1.0, 0.0),
    ("ft/h", "m/h"): (0.3048, 0.0),
    ("m/h", "m/h"): (1.0, 0.0),
    ("klbf", "klbf"): (1.0, 0.0),
    ("rpm", "rpm"): (1.0, 0.0),
    ("klbf.ft", "klbf.ft"): (1.0, 0.0),
}


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _normalise_unit(unit: str) -> str:
    return str(unit).strip().lower().replace("°", "deg").replace(" ", "")


def convert_value(value: float, source_unit: str | None, canonical_unit: str) -> tuple[float, bool]:
    if not source_unit:
        return value, False
    source = _normalise_unit(source_unit)
    target = canonical_unit
    factor_offset = _UNIT_FACTORS.get((source, target))
    if factor_offset is None:
        if source == _normalise_unit(target):
            return value, False
        raise ValueError(f"unsupported unit conversion {source_unit!r} -> {canonical_unit!r}")
    factor, offset = factor_offset
    converted = value * factor + offset
    return converted, source != _normalise_unit(target)


class EdgeStreamPipeline:
    def __init__(self, raw_path: Path | None = None) -> None:
        self.raw_path = raw_path or Path("data/streaming/raw_stream.jsonl")
        self.raw_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._state: dict[str, StreamState] = {}

    def _append_raw(self, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        record = {"sha256": digest, "record": payload}
        with self._lock:
            with self.raw_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, separators=(",", ":"), default=str) + "\n")
        return digest

    def process(
        self,
        *,
        stream_id: str,
        sequence: int,
        source_timestamp: datetime,
        channels: dict[str, Any],
        units: dict[str, str] | None = None,
        received_at: datetime | None = None,
        operational_state: str = "drilling",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        received = _utc(received_at)
        source = _utc(source_timestamp)
        units = units or {}
        metadata = metadata or {}

        raw = {
            "stream_id": stream_id,
            "sequence": sequence,
            "source_timestamp": source.isoformat(),
            "received_at": received.isoformat(),
            "channels": channels,
            "units": units,
            "operational_state": operational_state,
            "metadata": metadata,
        }
        digest = self._append_raw(raw)

        flags: list[str] = []
        quality = QualityState.GOOD
        state = self._state.setdefault(stream_id, StreamState())

        if state.last_sequence is not None:
            if sequence == state.last_sequence:
                quality = QualityState.QUARANTINED
                flags.append("duplicate_sequence")
            elif sequence < state.last_sequence:
                quality = QualityState.QUARANTINED
                flags.append("out_of_order_sequence")
            elif sequence > state.last_sequence + 1:
                quality = QualityState.UNCERTAIN
                flags.append("sequence_gap")

        if state.last_source_timestamp and source < state.last_source_timestamp:
            quality = QualityState.QUARANTINED
            flags.append("out_of_order_timestamp")

        latency_seconds = max(0.0, (received - source).total_seconds())
        if latency_seconds > 30.0 and quality != QualityState.QUARANTINED:
            quality = QualityState.STALE
            flags.append("stale_source_timestamp")
        elif latency_seconds > 5.0 and quality == QualityState.GOOD:
            quality = QualityState.UNCERTAIN
            flags.append("delayed_sample")

        normalised: dict[str, float] = {}
        unknown: list[str] = []
        corrected = False

        for incoming_name, incoming_value in channels.items():
            definition = resolve_channel(incoming_name)
            if definition is None:
                unknown.append(incoming_name)
                continue
            try:
                value = float(incoming_value)
                if not math.isfinite(value):
                    raise ValueError("non-finite")
                value, changed = convert_value(
                    value,
                    units.get(incoming_name) or units.get(definition.canonical_name),
                    definition.canonical_unit,
                )
                corrected = corrected or changed
            except (TypeError, ValueError) as exc:
                quality = QualityState.BAD if quality != QualityState.QUARANTINED else quality
                flags.append(f"invalid:{incoming_name}:{exc}")
                continue

            if definition.minimum is not None and value < definition.minimum:
                quality = QualityState.BAD if quality != QualityState.QUARANTINED else quality
                flags.append(f"below_range:{definition.canonical_name}")
            if definition.maximum is not None and value > definition.maximum:
                quality = QualityState.BAD if quality != QualityState.QUARANTINED else quality
                flags.append(f"above_range:{definition.canonical_name}")
            normalised[definition.canonical_name] = value

        if corrected and quality == QualityState.GOOD:
            quality = QualityState.CORRECTED
            flags.append("unit_normalised")

        required = {"depth_m", "gamma_ray_api", "resistivity_ohmm"}
        missing = sorted(required.difference(normalised))
        if missing:
            flags.append("missing_required:" + ",".join(missing))

        inference_ready = (
            quality in {QualityState.GOOD, QualityState.CORRECTED}
            and not missing
            and operational_state.lower() not in {"offline", "connection_lost", "unknown"}
        )

        if quality != QualityState.QUARANTINED:
            state.last_sequence = sequence
            state.last_source_timestamp = source

        return {
            "stream_id": stream_id,
            "sequence": sequence,
            "source_timestamp": source.isoformat(),
            "received_at": received.isoformat(),
            "latency_seconds": round(latency_seconds, 3),
            "quality_state": quality.value,
            "quality_flags": flags,
            "inference_ready": inference_ready,
            "canonical_channels": normalised,
            "unknown_channels": unknown,
            "operational_state": operational_state,
            "raw_record_sha256": digest,
        }


edge_stream_pipeline = EdgeStreamPipeline()
