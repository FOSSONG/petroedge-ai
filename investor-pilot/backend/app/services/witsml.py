from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def normalize_witsml_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """Normalize a gateway-produced WITSML/ETP sample to PetroEdge's canonical envelope.

    This is an adapter boundary, not a complete WITSML XML or ETP protocol implementation.
    """
    channels = sample.get("channels") or sample.get("data") or {}
    units = sample.get("units") or {}
    if not isinstance(channels, dict):
        raise ValueError("channels must be an object")
    return {
        "stream_id": str(sample.get("stream_id") or sample.get("well_id") or "WITSML-STREAM"),
        "sequence": int(sample.get("sequence", 0)),
        "source_timestamp": sample.get("source_timestamp") or datetime.now(timezone.utc).isoformat(),
        "reservoir_id": sample.get("reservoir_id"),
        "well_id": sample.get("well_id") or "WITSML-DEMO",
        "channels": channels,
        "units": units,
        "operational_state": sample.get("operational_state", "drilling"),
        "metadata": {
            **(sample.get("metadata") or {}),
            "source_protocol": sample.get("source_protocol", "WITSML/ETP-gateway"),
        },
    }
