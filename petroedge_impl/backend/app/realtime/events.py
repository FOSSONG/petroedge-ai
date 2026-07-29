from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class EventType(StrEnum):
    SYSTEM_READY = "system.ready"
    SYSTEM_SHUTDOWN = "system.shutdown"
    ANALYSIS_STARTED = "analysis.started"
    ANALYSIS_COMPLETED = "analysis.completed"
    ANALYSIS_FAILED = "analysis.failed"
    WELL_CREATED = "well.created"
    WELL_UPDATED = "well.updated"
    WELL_LOGS_LOADED = "well.logs_loaded"
    STREAM_STARTED = "stream.started"
    STREAM_COMPLETED = "stream.completed"
    STREAM_FAILED = "stream.failed"
    JOB_QUEUED = "job.queued"
    JOB_STARTED = "job.started"
    JOB_PROGRESS = "job.progress"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"
    ALERT_CREATED = "alert.created"
    ALERT_UPDATED = "alert.updated"
    STREAM_SAMPLE = "stream.sample"
    PREDICTION_COMPLETED = "prediction.completed"
    DATASET_INGESTED = "dataset.ingested"
    REPORT_COMPLETED = "report.completed"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    event_type: str
    payload: dict[str, Any]
    channel: str = "global"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: str = field(default_factory=utcnow_iso)
    correlation_id: str | None = None
    actor_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


EventSubscriber = Callable[[EventEnvelope], Awaitable[None]]


class EventBus:
    """Small in-process async event bus.

    It decouples background jobs, alerts, streaming and WebSocket delivery.
    The interface can later be backed by Redis without changing publishers.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, set[EventSubscriber]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, topic: str, subscriber: EventSubscriber) -> None:
        async with self._lock:
            self._subscribers[topic].add(subscriber)

    async def unsubscribe(self, topic: str, subscriber: EventSubscriber) -> None:
        async with self._lock:
            subscribers = self._subscribers.get(topic)
            if not subscribers:
                return
            subscribers.discard(subscriber)
            if not subscribers:
                self._subscribers.pop(topic, None)

    async def publish(self, event: EventEnvelope) -> None:
        async with self._lock:
            subscribers = set(self._subscribers.get(event.event_type, set()))
            subscribers.update(self._subscribers.get("*", set()))

        if not subscribers:
            return

        results = await asyncio.gather(
            *(subscriber(event) for subscriber in subscribers),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.error("Event subscriber failed for %s: %s", event.event_type, result)

    async def emit(
        self,
        event_type: EventType | str,
        payload: dict[str, Any],
        *,
        channel: str = "global",
        correlation_id: str | None = None,
        actor_id: str | None = None,
    ) -> EventEnvelope:
        event = EventEnvelope(
            event_type=str(event_type),
            payload=payload,
            channel=channel,
            correlation_id=correlation_id,
            actor_id=actor_id,
        )
        await self.publish(event)
        return event


_event_bus = EventBus()


def get_event_bus() -> EventBus:
    return _event_bus
