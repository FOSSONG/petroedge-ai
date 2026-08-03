from __future__ import annotations

import copy
import threading
import uuid
from datetime import datetime, timezone

from app.alerts.schemas import Alert, AlertSeverity, AlertStatus, AlertUpdate
from app.events.schemas import Event


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AlertNotFoundError(KeyError):
    pass


class AlertManager:
    def __init__(self) -> None:
        self._alerts: dict[str, Alert] = {}
        self._lock = threading.RLock()

    def create(
        self,
        *,
        event: Event,
        title: str,
        message: str,
        severity: AlertSeverity,
        rule_id: str | None = None,
        recommended_action: str | None = None,
        metadata: dict | None = None,
    ) -> Alert:
        alert = Alert(
            alert_id=uuid.uuid4().hex,
            title=title,
            message=message,
            severity=severity,
            source_event_id=event.event_id,
            rule_id=rule_id,
            asset_id=event.asset_id,
            reservoir_id=event.reservoir_id,
            well_id=event.well_id,
            recommended_action=recommended_action,
            metadata=metadata or {},
        )
        with self._lock:
            self._alerts[alert.alert_id] = alert
        return copy.deepcopy(alert)

    def get(self, alert_id: str) -> Alert:
        with self._lock:
            try:
                return copy.deepcopy(self._alerts[alert_id])
            except KeyError as exc:
                raise AlertNotFoundError(alert_id) from exc

    def list(
        self,
        *,
        status: AlertStatus | None = None,
        severity: AlertSeverity | None = None,
        limit: int = 100,
    ) -> list[Alert]:
        with self._lock:
            alerts = list(self._alerts.values())
        if status:
            alerts = [item for item in alerts if item.status == status]
        if severity:
            alerts = [item for item in alerts if item.severity == severity]
        alerts.sort(key=lambda item: item.created_at, reverse=True)
        return copy.deepcopy(alerts[: max(1, min(limit, 1000))])

    def update(self, alert_id: str, request: AlertUpdate) -> Alert:
        with self._lock:
            if alert_id not in self._alerts:
                raise AlertNotFoundError(alert_id)
            alert = self._alerts[alert_id]
            alert.status = request.status
            if request.status == AlertStatus.acknowledged:
                alert.acknowledged_at = utc_now()
                alert.acknowledged_by = request.actor
            elif request.status == AlertStatus.resolved:
                alert.resolved_at = utc_now()
            if request.note:
                alert.metadata["status_note"] = request.note
            return copy.deepcopy(alert)

    def clear(self) -> None:
        with self._lock:
            self._alerts.clear()


alert_manager = AlertManager()