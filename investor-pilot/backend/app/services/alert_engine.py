from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

from sqlalchemy.orm import Session

from app.db.models import AlertRecord as AlertModel
from app.db.repositories.domain import AlertRepository, WellRepository


@dataclass(frozen=True)
class EmittedAlert:
    id: str
    severity: str
    well_id: str
    message: str
    created_at: datetime
    status: str
    rule_name: str | None
    depth_m: float | None
    source_type: str | None
    source_id: str | None
    value: float | None
    threshold: float | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "alert_id": self.id,
            "severity": self.severity,
            "well_id": self.well_id,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "rule_name": self.rule_name,
            "depth_m": self.depth_m,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "value": self.value,
            "threshold": self.threshold,
            "metadata": self.metadata,
        }


class AlertEngine:
    """Evaluate analytical records and persist alerts through SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.alerts = AlertRepository(session)
        self.wells = WellRepository(session)

    def evaluate_record(
        self,
        record: Mapping[str, Any],
        *,
        source_type: str = "analytics",
        source_id: str | None = None,
    ) -> list[EmittedAlert]:
        well_public_id = str(record.get("well_id") or "UNKNOWN")
        well = self.wells.get_or_create(well_public_id)
        depth = self._number(record.get("depth_m"))
        hydrocarbon = self._number(
            record.get(
                "hydrocarbon_probability",
                record.get("predicted_hydrocarbon_probability"),
            )
        )
        anomaly = bool(record.get("is_anomaly", False))
        qc_score = self._number(record.get("qc_score"))
        water_saturation = self._number(
            record.get(
                "water_saturation",
                record.get("predicted_water_saturation"),
            )
        )

        rules: list[dict[str, Any]] = []
        if hydrocarbon is not None and hydrocarbon >= 0.72:
            rules.append({
                "severity": "high",
                "rule_name": "High Hydrocarbon Probability",
                "message": f"Hydrocarbon probability reached {hydrocarbon:.3f}.",
                "value": hydrocarbon,
                "threshold": 0.72,
            })
        if anomaly:
            rules.append({
                "severity": "medium",
                "rule_name": "Anomalous Log Response",
                "message": "Anomalous log response detected.",
                "value": None,
                "threshold": None,
            })
        if qc_score is not None and qc_score < 0.60:
            rules.append({
                "severity": "medium",
                "rule_name": "Low Data Quality",
                "message": f"QC score fell to {qc_score:.3f}.",
                "value": qc_score,
                "threshold": 0.60,
            })
        if water_saturation is not None and water_saturation >= 0.90:
            rules.append({
                "severity": "low",
                "rule_name": "High Water Saturation",
                "message": f"Water saturation reached {water_saturation:.3f}.",
                "value": water_saturation,
                "threshold": 0.90,
            })

        emitted: list[EmittedAlert] = []
        for rule in rules:
            details = {
                "rule_name": rule["rule_name"],
                "depth_m": depth,
                "source_id": source_id,
                "value": rule["value"],
                "threshold": rule["threshold"],
            }
            model = AlertModel(
                well_id=well.id,
                alert_type=str(rule["rule_name"]),
                severity=str(rule["severity"]),
                title=str(rule["rule_name"]),
                message=str(rule["message"]),
                source=source_type,
                details_json=details,
            )
            self.alerts.add(model)
            emitted.append(self._serialize(model, well_public_id))
        return emitted

    def evaluate_records(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        source_type: str = "analytics",
        source_id: str | None = None,
    ) -> list[EmittedAlert]:
        emitted: list[EmittedAlert] = []
        for record in records:
            emitted.extend(
                self.evaluate_record(
                    record,
                    source_type=source_type,
                    source_id=source_id,
                )
            )
        return emitted

    @staticmethod
    def serialize_model(model: AlertModel, well_public_id: str | None = None) -> dict[str, Any]:
        details = model.details_json or {}
        return {
            "id": model.id,
            "alert_id": model.id,
            "severity": model.severity,
            "well_id": well_public_id,
            "message": model.message,
            "created_at": model.created_at.isoformat(),
            "status": model.status,
            "rule_name": details.get("rule_name") or model.alert_type,
            "depth_m": details.get("depth_m"),
            "source_type": model.source,
            "source_id": details.get("source_id"),
            "value": details.get("value"),
            "threshold": details.get("threshold"),
            "metadata": details,
        }

    def _serialize(self, model: AlertModel, well_public_id: str) -> EmittedAlert:
        details = model.details_json or {}
        return EmittedAlert(
            id=model.id,
            severity=model.severity,
            well_id=well_public_id,
            message=model.message,
            created_at=model.created_at,
            status=model.status,
            rule_name=details.get("rule_name") or model.alert_type,
            depth_m=details.get("depth_m"),
            source_type=model.source,
            source_id=details.get("source_id"),
            value=details.get("value"),
            threshold=details.get("threshold"),
            metadata=details,
        )

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None


def get_alert_engine(session: Session) -> AlertEngine:
    return AlertEngine(session)


def evaluate_alerts(
    session: Session,
    records: Iterable[Mapping[str, Any]],
    *,
    source_type: str = "analytics",
    source_id: str | None = None,
) -> list[dict[str, Any]]:
    return [
        item.to_dict()
        for item in AlertEngine(session).evaluate_records(
            records,
            source_type=source_type,
            source_id=source_id,
        )
    ]
