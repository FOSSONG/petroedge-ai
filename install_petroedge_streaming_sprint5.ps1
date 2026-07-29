param(
    [string]$ProjectRoot = (Get-Location).Path
)

$ErrorActionPreference = "Stop"

function Write-Utf8File {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$Content
    )
    $Target = Join-Path $ProjectRoot $RelativePath
    New-Item -ItemType Directory -Force -Path (Split-Path $Target) | Out-Null
    [System.IO.File]::WriteAllText(
        $Target,
        $Content,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Backup-File {
    param([string]$RelativePath, [string]$BackupRoot)
    $Source = Join-Path $ProjectRoot $RelativePath
    if (Test-Path $Source) {
        $Destination = Join-Path $BackupRoot $RelativePath
        New-Item -ItemType Directory -Force -Path (Split-Path $Destination) | Out-Null
        Copy-Item $Source $Destination -Force
    }
}

$BackendRoot = Join-Path $ProjectRoot "backend"
$AppRoot = Join-Path $BackendRoot "app"

if (-not (Test-Path (Join-Path $AppRoot "main.py"))) {
    throw "PetroEdge backend not found. Run this script from the PetroEdge-AI-v1-demo project root."
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $ProjectRoot "backups\streaming-$Timestamp"
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

@(
    "backend\app\main.py",
    "backend\app\api\routes\streaming.py",
    "backend\app\api\routes\events.py",
    "backend\app\api\routes\alerts.py"
) | ForEach-Object { Backup-File $_ $BackupRoot }

Write-Utf8File "backend\app\events\schemas.py" @'
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventSeverity(str, Enum):
    info = "info"
    advisory = "advisory"
    warning = "warning"
    critical = "critical"


class EventSource(str, Enum):
    api = "api"
    websocket = "websocket"
    replay = "replay"
    workflow = "workflow"
    model = "model"
    agent = "agent"
    sensor = "sensor"
    system = "system"


class Event(BaseModel):
    model_config = ConfigDict(extra="allow")

    event_id: str
    event_type: str
    source: EventSource = EventSource.api
    asset_id: str | None = None
    reservoir_id: str | None = None
    well_id: str | None = None
    severity: EventSeverity = EventSeverity.info
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=utc_now)
    received_at: datetime = Field(default_factory=utc_now)
    correlation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventCreate(BaseModel):
    event_type: str
    source: EventSource = EventSource.api
    asset_id: str | None = None
    reservoir_id: str | None = None
    well_id: str | None = None
    severity: EventSeverity = EventSeverity.info
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventDelivery(BaseModel):
    event: Event
    matched_rules: list[str] = Field(default_factory=list)
    alert_ids: list[str] = Field(default_factory=list)
    twin_updated: bool = False
    delivered_at: datetime = Field(default_factory=utc_now)
'@

Write-Utf8File "backend\app\events\bus.py" @'
from __future__ import annotations

import asyncio
import copy
import threading
from collections.abc import Awaitable, Callable

from app.events.schemas import Event

EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    def __init__(self, history_limit: int = 5000) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}
        self._wildcard_handlers: list[EventHandler] = []
        self._queues: set[asyncio.Queue[Event]] = set()
        self._history: list[Event] = []
        self._history_limit = history_limit
        self._lock = threading.RLock()

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        with self._lock:
            if event_type == "*":
                self._wildcard_handlers.append(handler)
            else:
                self._handlers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        with self._lock:
            handlers = self._wildcard_handlers if event_type == "*" else self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

    def create_queue(self, maxsize: int = 100) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)
        with self._lock:
            self._queues.add(queue)
        return queue

    def remove_queue(self, queue: asyncio.Queue[Event]) -> None:
        with self._lock:
            self._queues.discard(queue)

    async def publish(self, event: Event) -> None:
        with self._lock:
            self._history.append(copy.deepcopy(event))
            if len(self._history) > self._history_limit:
                self._history = self._history[-self._history_limit :]
            handlers = list(self._handlers.get(event.event_type, []))
            handlers.extend(self._wildcard_handlers)
            queues = list(self._queues)

        for queue in queues:
            try:
                queue.put_nowait(copy.deepcopy(event))
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(copy.deepcopy(event))
                except asyncio.QueueFull:
                    pass

        if handlers:
            await asyncio.gather(
                *(handler(copy.deepcopy(event)) for handler in handlers),
                return_exceptions=True,
            )

    def history(
        self,
        *,
        event_type: str | None = None,
        asset_id: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        with self._lock:
            items = list(self._history)

        if event_type:
            items = [item for item in items if item.event_type == event_type]
        if asset_id:
            items = [item for item in items if item.asset_id == asset_id]
        return copy.deepcopy(items[-max(1, min(limit, 1000)) :])

    def clear(self) -> None:
        with self._lock:
            self._history.clear()
            self._handlers.clear()
            self._wildcard_handlers.clear()
            self._queues.clear()


event_bus = EventBus()
'@

Write-Utf8File "backend\app\events\__init__.py" @'
from app.events.bus import EventBus, event_bus
from app.events.schemas import (
    Event,
    EventCreate,
    EventDelivery,
    EventSeverity,
    EventSource,
)

__all__ = [
    "Event",
    "EventBus",
    "EventCreate",
    "EventDelivery",
    "EventSeverity",
    "EventSource",
    "event_bus",
]
'@

Write-Utf8File "backend\app\alerts\schemas.py" @'
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AlertSeverity(str, Enum):
    information = "information"
    advisory = "advisory"
    warning = "warning"
    critical = "critical"


class AlertStatus(str, Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"


class Alert(BaseModel):
    alert_id: str
    title: str
    message: str
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.open
    source_event_id: str | None = None
    rule_id: str | None = None
    asset_id: str | None = None
    reservoir_id: str | None = None
    well_id: str | None = None
    recommended_action: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    acknowledged_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AlertUpdate(BaseModel):
    status: AlertStatus
    actor: str | None = None
    note: str | None = None
'@

Write-Utf8File "backend\app\alerts\manager.py" @'
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
'@

Write-Utf8File "backend\app\alerts\__init__.py" @'
from app.alerts.manager import AlertManager, AlertNotFoundError, alert_manager
from app.alerts.schemas import (
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertUpdate,
)

__all__ = [
    "Alert",
    "AlertManager",
    "AlertNotFoundError",
    "AlertSeverity",
    "AlertStatus",
    "AlertUpdate",
    "alert_manager",
]
'@

Write-Utf8File "backend\app\rules\schemas.py" @'
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.alerts.schemas import AlertSeverity


class RuleOperator(str, Enum):
    eq = "eq"
    ne = "ne"
    gt = "gt"
    gte = "gte"
    lt = "lt"
    lte = "lte"
    contains = "contains"
    in_ = "in"
    exists = "exists"


class RuleCondition(BaseModel):
    path: str
    operator: RuleOperator
    value: Any = None


class RuleAction(BaseModel):
    action_type: str = "alert"
    title: str
    message: str
    severity: AlertSeverity = AlertSeverity.warning
    recommended_action: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventRule(BaseModel):
    rule_id: str
    name: str
    event_type: str = "*"
    enabled: bool = True
    match_all: bool = True
    conditions: list[RuleCondition] = Field(default_factory=list)
    actions: list[RuleAction] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuleCreate(EventRule):
    pass
'@

Write-Utf8File "backend\app\rules\engine.py" @'
from __future__ import annotations

import copy
import threading
from typing import Any

from app.alerts import alert_manager
from app.events.schemas import Event
from app.rules.schemas import EventRule, RuleCondition, RuleOperator


class RuleEngine:
    def __init__(self) -> None:
        self._rules: dict[str, EventRule] = {}
        self._lock = threading.RLock()

    def register(self, rule: EventRule, *, replace: bool = False) -> EventRule:
        with self._lock:
            if rule.rule_id in self._rules and not replace:
                raise ValueError(f"Rule already exists: {rule.rule_id}")
            self._rules[rule.rule_id] = copy.deepcopy(rule)
        return copy.deepcopy(rule)

    def get(self, rule_id: str) -> EventRule:
        with self._lock:
            if rule_id not in self._rules:
                raise KeyError(rule_id)
            return copy.deepcopy(self._rules[rule_id])

    def list(self) -> list[EventRule]:
        with self._lock:
            return [copy.deepcopy(self._rules[key]) for key in sorted(self._rules)]

    def delete(self, rule_id: str) -> None:
        with self._lock:
            if rule_id not in self._rules:
                raise KeyError(rule_id)
            del self._rules[rule_id]

    def evaluate(self, event: Event) -> tuple[list[str], list[str]]:
        matched_rules: list[str] = []
        alert_ids: list[str] = []

        for rule in self.list():
            if not rule.enabled:
                continue
            if rule.event_type not in {"*", event.event_type}:
                continue

            results = [self._matches(event, condition) for condition in rule.conditions]
            matched = all(results) if rule.match_all else any(results)
            if not rule.conditions:
                matched = True
            if not matched:
                continue

            matched_rules.append(rule.rule_id)
            for action in rule.actions:
                if action.action_type != "alert":
                    continue
                alert = alert_manager.create(
                    event=event,
                    title=action.title,
                    message=action.message,
                    severity=action.severity,
                    rule_id=rule.rule_id,
                    recommended_action=action.recommended_action,
                    metadata=action.metadata,
                )
                alert_ids.append(alert.alert_id)

        return matched_rules, alert_ids

    def _matches(self, event: Event, condition: RuleCondition) -> bool:
        value = self._resolve(event, condition.path)
        expected = condition.value
        operator = condition.operator

        if operator == RuleOperator.exists:
            return value is not None
        if operator == RuleOperator.eq:
            return value == expected
        if operator == RuleOperator.ne:
            return value != expected
        if operator == RuleOperator.gt:
            return self._numeric(value, expected, lambda a, b: a > b)
        if operator == RuleOperator.gte:
            return self._numeric(value, expected, lambda a, b: a >= b)
        if operator == RuleOperator.lt:
            return self._numeric(value, expected, lambda a, b: a < b)
        if operator == RuleOperator.lte:
            return self._numeric(value, expected, lambda a, b: a <= b)
        if operator == RuleOperator.contains:
            try:
                return expected in value
            except TypeError:
                return False
        if operator == RuleOperator.in_:
            try:
                return value in expected
            except TypeError:
                return False
        return False

    @staticmethod
    def _numeric(value: Any, expected: Any, predicate) -> bool:
        if isinstance(value, bool) or isinstance(expected, bool):
            return False
        if not isinstance(value, (int, float)) or not isinstance(expected, (int, float)):
            return False
        return bool(predicate(float(value), float(expected)))

    @staticmethod
    def _resolve(event: Event, path: str) -> Any:
        current: Any = event.model_dump(mode="python")
        for segment in path.split("."):
            if isinstance(current, dict):
                current = current.get(segment)
            else:
                return None
        return current

    def clear(self) -> None:
        with self._lock:
            self._rules.clear()


rule_engine = RuleEngine()
'@

Write-Utf8File "backend\app\rules\defaults.py" @'
from app.rules.engine import rule_engine
from app.rules.schemas import EventRule, RuleAction, RuleCondition


DEFAULT_RULES = [
    EventRule(
        rule_id="pressure-low",
        name="Low reservoir pressure",
        event_type="telemetry.pressure",
        conditions=[
            RuleCondition(path="payload.value", operator="lt", value=2500.0),
        ],
        actions=[
            RuleAction(
                title="Low reservoir pressure",
                message="Reservoir pressure is below the configured operational threshold.",
                severity="critical",
                recommended_action="Validate the pressure measurement and review drawdown strategy.",
            )
        ],
    ),
    EventRule(
        rule_id="water-cut-high",
        name="High water cut",
        event_type="telemetry.production",
        conditions=[
            RuleCondition(path="payload.water_cut", operator="gt", value=0.70),
        ],
        actions=[
            RuleAction(
                title="High water cut",
                message="Water cut exceeds 70 percent.",
                severity="warning",
                recommended_action="Investigate water breakthrough, coning and completion integrity.",
            )
        ],
    ),
]


def register_default_rules() -> None:
    for rule in DEFAULT_RULES:
        rule_engine.register(rule, replace=True)
'@

Write-Utf8File "backend\app\rules\__init__.py" @'
from app.rules.defaults import DEFAULT_RULES, register_default_rules
from app.rules.engine import RuleEngine, rule_engine
from app.rules.schemas import (
    EventRule,
    RuleAction,
    RuleCondition,
    RuleCreate,
    RuleOperator,
)

__all__ = [
    "DEFAULT_RULES",
    "EventRule",
    "RuleAction",
    "RuleCondition",
    "RuleCreate",
    "RuleEngine",
    "RuleOperator",
    "register_default_rules",
    "rule_engine",
]
'@

Write-Utf8File "backend\app\streaming\schemas.py" @'
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.events.schemas import EventCreate


class TelemetryBatch(BaseModel):
    reservoir_id: str
    well_id: str | None = None
    rows: list[dict[str, Any]]
    event_type: str = "telemetry.batch"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReplayRequest(BaseModel):
    events: list[EventCreate]
    speed: float = Field(default=1.0, gt=0.0, le=100.0)
    interval_seconds: float = Field(default=1.0, ge=0.0, le=60.0)
'@

Write-Utf8File "backend\app\streaming\service.py" @'
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from app.digital_twin import digital_twin_orchestrator
from app.events import Event, EventCreate, EventDelivery, event_bus
from app.rules import register_default_rules, rule_engine
from app.streaming.schemas import ReplayRequest, TelemetryBatch


class StreamingService:
    def __init__(self) -> None:
        register_default_rules()

    async def ingest(self, request: EventCreate) -> EventDelivery:
        event = Event(
            event_id=uuid.uuid4().hex,
            event_type=request.event_type,
            source=request.source,
            asset_id=request.asset_id,
            reservoir_id=request.reservoir_id,
            well_id=request.well_id,
            severity=request.severity,
            payload=request.payload,
            occurred_at=request.occurred_at or datetime.now(timezone.utc),
            correlation_id=request.correlation_id,
            metadata=request.metadata,
        )

        twin_updated = False
        rows = request.payload.get("rows")
        if request.reservoir_id and isinstance(rows, list):
            valid_rows = [item for item in rows if isinstance(item, dict)]
            digital_twin_orchestrator.ingest_rows(
                reservoir_id=request.reservoir_id,
                rows=valid_rows,
                source_reference=f"event:{event.event_id}",
            )
            twin_updated = True

        matched_rules, alert_ids = rule_engine.evaluate(event)
        await event_bus.publish(event)

        return EventDelivery(
            event=event,
            matched_rules=matched_rules,
            alert_ids=alert_ids,
            twin_updated=twin_updated,
        )

    async def ingest_telemetry(self, request: TelemetryBatch) -> EventDelivery:
        rows = []
        for row in request.rows:
            enriched = dict(row)
            if request.well_id and not any(
                key in enriched for key in ("Well_ID", "Well_id", "well_id")
            ):
                enriched["Well_ID"] = request.well_id
            rows.append(enriched)

        return await self.ingest(
            EventCreate(
                event_type=request.event_type,
                source="api",
                reservoir_id=request.reservoir_id,
                well_id=request.well_id,
                asset_id=request.well_id or request.reservoir_id,
                payload={"rows": rows},
                metadata=request.metadata,
            )
        )

    async def replay(self, request: ReplayRequest) -> list[EventDelivery]:
        deliveries: list[EventDelivery] = []
        delay = request.interval_seconds / request.speed
        for index, event in enumerate(request.events):
            if index and delay > 0:
                await asyncio.sleep(delay)
            replay_event = event.model_copy(update={"source": "replay"})
            deliveries.append(await self.ingest(replay_event))
        return deliveries


streaming_service = StreamingService()
'@

Write-Utf8File "backend\app\streaming\__init__.py" @'
from app.streaming.schemas import ReplayRequest, TelemetryBatch
from app.streaming.service import StreamingService, streaming_service

__all__ = [
    "ReplayRequest",
    "StreamingService",
    "TelemetryBatch",
    "streaming_service",
]
'@

Write-Utf8File "backend\app\api\routes\streaming.py" @'
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.core.rbac import require_roles
from app.events import EventCreate, event_bus
from app.streaming import ReplayRequest, TelemetryBatch, streaming_service

router = APIRouter()

READ_ROLES = ("admin", "geoscientist", "engineer", "viewer")
WRITE_ROLES = ("admin", "geoscientist", "engineer")


@router.post("/events")
async def ingest_event(
    request: EventCreate,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    delivery = await streaming_service.ingest(request)
    return delivery.model_dump(mode="json")


@router.post("/telemetry")
async def ingest_telemetry(
    request: TelemetryBatch,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    delivery = await streaming_service.ingest_telemetry(request)
    return delivery.model_dump(mode="json")


@router.post("/replay")
async def replay_events(
    request: ReplayRequest,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    deliveries = await streaming_service.replay(request)
    return {
        "count": len(deliveries),
        "deliveries": [item.model_dump(mode="json") for item in deliveries],
    }


@router.websocket("/ws")
async def stream_events(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = event_bus.create_queue()
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.remove_queue(queue)
'@

Write-Utf8File "backend\app\api\routes\events.py" @'
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.rbac import require_roles
from app.events import event_bus

router = APIRouter()

READ_ROLES = ("admin", "geoscientist", "engineer", "viewer")


@router.get("")
async def list_events(
    event_type: str | None = None,
    asset_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    events = event_bus.history(
        event_type=event_type,
        asset_id=asset_id,
        limit=limit,
    )
    return {
        "count": len(events),
        "events": [item.model_dump(mode="json") for item in events],
    }
'@

Write-Utf8File "backend\app\api\routes\alerts.py" @'
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.alerts import (
    AlertNotFoundError,
    AlertSeverity,
    AlertStatus,
    AlertUpdate,
    alert_manager,
)
from app.core.rbac import require_roles

router = APIRouter()

READ_ROLES = ("admin", "geoscientist", "engineer", "viewer")
WRITE_ROLES = ("admin", "geoscientist", "engineer")


@router.get("")
async def list_alerts(
    status: AlertStatus | None = None,
    severity: AlertSeverity | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    alerts = alert_manager.list(status=status, severity=severity, limit=limit)
    return {
        "count": len(alerts),
        "alerts": [item.model_dump(mode="json") for item in alerts],
    }


@router.get("/{alert_id}")
async def get_alert(
    alert_id: str,
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    try:
        alert = alert_manager.get(alert_id)
    except AlertNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Alert not found.") from exc
    return alert.model_dump(mode="json")


@router.patch("/{alert_id}")
async def update_alert(
    alert_id: str,
    request: AlertUpdate,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    try:
        alert = alert_manager.update(alert_id, request)
    except AlertNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Alert not found.") from exc
    return alert.model_dump(mode="json")
'@

Write-Utf8File "backend\app\api\routes\rules.py" @'
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.rbac import require_roles
from app.rules import RuleCreate, rule_engine

router = APIRouter()

READ_ROLES = ("admin", "geoscientist", "engineer", "viewer")
WRITE_ROLES = ("admin", "geoscientist", "engineer")


@router.get("")
async def list_rules(
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    rules = rule_engine.list()
    return {
        "count": len(rules),
        "rules": [item.model_dump(mode="json") for item in rules],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_rule(
    request: RuleCreate,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    try:
        rule = rule_engine.register(request, replace=False)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return rule.model_dump(mode="json")


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: str,
    _: dict[str, Any] = Depends(require_roles("admin")),
) -> Response:
    try:
        rule_engine.delete(rule_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Rule not found.") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
'@

# Register API routes in main.py.
$MainPath = Join-Path $ProjectRoot "backend\app\main.py"
$MainContent = Get-Content $MainPath -Raw

$Routes = @(
    '    ("streaming", "/streaming", ("Real-Time Streaming",), True),',
    '    ("events", "/events", ("Event Bus",), True),',
    '    ("alerts", "/alerts", ("Operational Alerts",), True),',
    '    ("rules", "/rules", ("Event Rules",), True),'
)

foreach ($Route in $Routes) {
    $ModuleName = [regex]::Match($Route, '\("([^"]+)"').Groups[1].Value
    if ($MainContent -notmatch "\(`"$ModuleName`",") {
        $Anchor = '    ("twins", "/twins", ("Reservoir Digital Twin",), True),'
        if ($MainContent.Contains($Anchor)) {
            $MainContent = $MainContent.Replace(
                $Anchor,
                $Anchor + [Environment]::NewLine + $Route
            )
        } else {
            throw "Could not find twins route registration in main.py."
        }
    }
}

[System.IO.File]::WriteAllText(
    $MainPath,
    $MainContent,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Utf8File "backend\tests\test_streaming.py" @'
import pytest

from app.alerts import alert_manager
from app.digital_twin import twin_history, twin_registry
from app.events import EventCreate, event_bus
from app.rules import register_default_rules, rule_engine
from app.streaming import ReplayRequest, TelemetryBatch, streaming_service


@pytest.fixture(autouse=True)
def reset_state() -> None:
    event_bus.clear()
    alert_manager.clear()
    rule_engine.clear()
    twin_registry.clear()
    twin_history.clear()
    register_default_rules()


@pytest.mark.asyncio
async def test_event_creates_alert() -> None:
    delivery = await streaming_service.ingest(
        EventCreate(
            event_type="telemetry.pressure",
            reservoir_id="GABO",
            well_id="GABO-18",
            payload={"value": 2400.0},
        )
    )

    assert delivery.matched_rules == ["pressure-low"]
    assert len(delivery.alert_ids) == 1
    assert len(alert_manager.list()) == 1
    assert len(event_bus.history()) == 1


@pytest.mark.asyncio
async def test_telemetry_updates_digital_twin() -> None:
    delivery = await streaming_service.ingest_telemetry(
        TelemetryBatch(
            reservoir_id="GABO",
            well_id="GABO-18",
            rows=[
                {
                    "PHI_D": 0.24,
                    "SW_ARCHIE": 0.30,
                    "PRESSURE": 4000.0,
                }
            ],
        )
    )

    assert delivery.twin_updated is True
    state = twin_registry.get("GABO")
    assert state.wells["GABO-18"].porosity == pytest.approx(0.24)
    assert state.wells["GABO-18"].pressure == pytest.approx(4000.0)


@pytest.mark.asyncio
async def test_replay_processes_all_events() -> None:
    result = await streaming_service.replay(
        ReplayRequest(
            speed=100.0,
            interval_seconds=0.0,
            events=[
                EventCreate(event_type="test.one", payload={"value": 1}),
                EventCreate(event_type="test.two", payload={"value": 2}),
            ],
        )
    )

    assert len(result) == 2
    assert len(event_bus.history()) == 2
'@

Write-Utf8File "backend\tests\test_rules.py" @'
from app.alerts import alert_manager
from app.events import Event
from app.rules import EventRule, RuleAction, RuleCondition, rule_engine


def test_rule_engine_matches_nested_payload() -> None:
    rule_engine.clear()
    alert_manager.clear()
    rule_engine.register(
        EventRule(
            rule_id="water-cut-test",
            name="Water cut test",
            event_type="telemetry.production",
            conditions=[
                RuleCondition(
                    path="payload.water_cut",
                    operator="gt",
                    value=0.70,
                )
            ],
            actions=[
                RuleAction(
                    title="High water cut",
                    message="Water cut exceeded.",
                    severity="warning",
                )
            ],
        )
    )

    matched, alerts = rule_engine.evaluate(
        Event(
            event_id="evt-1",
            event_type="telemetry.production",
            payload={"water_cut": 0.85},
        )
    )

    assert matched == ["water-cut-test"]
    assert len(alerts) == 1
'@

Write-Utf8File "backend\tests\test_streaming_api.py" @'
from fastapi.testclient import TestClient

from app.main import app


def test_streaming_routes_are_present_in_openapi() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]

    assert "/api/v1/streaming/events" in paths
    assert "/api/v1/streaming/telemetry" in paths
    assert "/api/v1/streaming/replay" in paths
    assert "/api/v1/events" in paths
    assert "/api/v1/alerts" in paths
    assert "/api/v1/rules" in paths
'@

Write-Utf8File "docs\real-time-streaming.md" @'
# PetroEdge Real-Time Streaming and Event Processing

## Scope

Sprint 5 introduces an event-driven operational layer for PetroEdge.

## Components

- Asynchronous in-process event bus
- REST event ingestion
- Telemetry batch ingestion
- WebSocket event broadcasting
- Configurable rule engine
- Operational alert lifecycle
- Digital Twin updates from telemetry
- Historical replay

## Endpoints

- `POST /api/v1/streaming/events`
- `POST /api/v1/streaming/telemetry`
- `POST /api/v1/streaming/replay`
- `WS /api/v1/streaming/ws`
- `GET /api/v1/events`
- `GET /api/v1/alerts`
- `PATCH /api/v1/alerts/{alert_id}`
- `GET /api/v1/rules`
- `POST /api/v1/rules`
- `DELETE /api/v1/rules/{rule_id}`

## Production boundary

This sprint validates the event contracts and processing model with an in-process bus. Kafka, MQTT, Redis Streams or another durable broker can be introduced behind the same service interfaces in the infrastructure hardening milestone.
'@

Write-Host ""
Write-Host "Running syntax validation..." -ForegroundColor Yellow

$PythonFiles = @(
    "backend\app\events\schemas.py",
    "backend\app\events\bus.py",
    "backend\app\events\__init__.py",
    "backend\app\alerts\schemas.py",
    "backend\app\alerts\manager.py",
    "backend\app\alerts\__init__.py",
    "backend\app\rules\schemas.py",
    "backend\app\rules\engine.py",
    "backend\app\rules\defaults.py",
    "backend\app\rules\__init__.py",
    "backend\app\streaming\schemas.py",
    "backend\app\streaming\service.py",
    "backend\app\streaming\__init__.py",
    "backend\app\api\routes\streaming.py",
    "backend\app\api\routes\events.py",
    "backend\app\api\routes\alerts.py",
    "backend\app\api\routes\rules.py",
    "backend\app\main.py"
)

foreach ($File in $PythonFiles) {
    python -m py_compile $File
    if ($LASTEXITCODE -ne 0) {
        throw "Syntax validation failed: $File"
    }
}

Write-Host "Syntax validation passed." -ForegroundColor Green
Write-Host ""
Write-Host "Sprint 5 installed." -ForegroundColor Green
Write-Host "Backup: $BackupRoot" -ForegroundColor Cyan
Write-Host ""
Write-Host "Run:" -ForegroundColor Yellow
Write-Host "  python -m pytest .\backend\tests\test_streaming.py -q"
Write-Host "  python -m pytest .\backend\tests\test_rules.py -q"
Write-Host "  python -m pytest .\backend\tests\test_streaming_api.py -q"
Write-Host "  python -m pytest .\backend\tests -q"
Write-Host ""
Write-Host "Then start:" -ForegroundColor Yellow
Write-Host "  python -m uvicorn app.main:app --reload --app-dir backend"
