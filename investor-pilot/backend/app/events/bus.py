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