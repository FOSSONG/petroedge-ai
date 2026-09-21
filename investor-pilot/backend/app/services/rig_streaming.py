from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable

from app.services.edge_buffer import DurableEdgeBuffer
from app.streaming.schemas import EdgeStreamSample


class ConnectorState(str, Enum):
    STOPPED = "STOPPED"
    CONNECTING = "CONNECTING"
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE_BUFFERING = "OFFLINE_BUFFERING"
    ERROR = "ERROR"


class RigStreamManager:
    """Durable connector manager.

    B3 provides a production-safe queue and a replay/JSON-WebSocket bridge.
    It intentionally does not claim Energistics ETP protocol conformance:
    a certified ETP 1.2 protocol adapter must be validated against the target rig server.
    """

    def __init__(self, buffer: DurableEdgeBuffer | None = None) -> None:
        self.buffer = buffer or DurableEdgeBuffer()
        self.state = ConnectorState.STOPPED
        self.connector_type = "none"
        self.endpoint: str | None = None
        self.last_message_at: str | None = None
        self.last_delivery_at: str | None = None
        self.last_error: str | None = None
        self.messages_received = 0
        self.messages_delivered = 0
        self.reconnect_count = 0
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._deliver: Callable[[EdgeStreamSample], Awaitable[dict[str, object]]] | None = None

    def bind_delivery(self, delivery: Callable[[EdgeStreamSample], Awaitable[dict[str, object]]]) -> None:
        self._deliver = delivery

    def status(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "connector_type": self.connector_type,
            "endpoint": self.endpoint,
            "last_message_at": self.last_message_at,
            "last_delivery_at": self.last_delivery_at,
            "last_error": self.last_error,
            "messages_received": self.messages_received,
            "messages_delivered": self.messages_delivered,
            "reconnect_count": self.reconnect_count,
            "buffer": self.buffer.stats(),
            "etp_conformance": "NOT_CERTIFIED",
            "transport_note": "B3 websocket mode expects PetroEdge canonical JSON from an ETP/WITSML gateway.",
        }

    async def accept(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.messages_received += 1
        self.last_message_at = datetime.now(timezone.utc).isoformat()
        queued = self.buffer.enqueue(payload)
        await self.flush(limit=250)
        return {"accepted": True, **queued, "status": self.status()}

    async def flush(self, limit: int = 250) -> dict[str, int]:
        if self._deliver is None:
            return {"delivered": 0, "remaining": self.buffer.stats()["depth"]}
        delivered = 0
        for record in self.buffer.peek(limit):
            try:
                sample = EdgeStreamSample.model_validate(record["payload"])
                await self._deliver(sample)
                self.buffer.acknowledge(record["id"])
                delivered += 1
                self.messages_delivered += 1
                self.last_delivery_at = datetime.now(timezone.utc).isoformat()
                self.last_error = None
            except Exception as exc:
                self.buffer.fail(record["id"], f"{type(exc).__name__}: {exc}")
                self.last_error = f"{type(exc).__name__}: {exc}"
                self.state = ConnectorState.DEGRADED
                break
        return {"delivered": delivered, "remaining": self.buffer.stats()["depth"]}

    async def start_websocket_bridge(self, endpoint: str, headers: dict[str, str] | None = None) -> None:
        if self._task and not self._task.done():
            raise RuntimeError("a rig connector is already running")
        if not endpoint.startswith(("ws://", "wss://")):
            raise ValueError("endpoint must use ws:// or wss://")
        self.connector_type = "websocket-json-bridge"
        self.endpoint = endpoint
        self._stop.clear()
        self._task = asyncio.create_task(self._websocket_loop(endpoint, headers or {}))

    async def _websocket_loop(self, endpoint: str, headers: dict[str, str]) -> None:
        import websockets
        delay = 1.0
        while not self._stop.is_set():
            self.state = ConnectorState.CONNECTING
            try:
                async with websockets.connect(
                    endpoint,
                    additional_headers=headers or None,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_queue=256,
                    open_timeout=15,
                ) as ws:
                    self.state = ConnectorState.ONLINE
                    delay = 1.0
                    await self.flush()
                    async for message in ws:
                        if self._stop.is_set():
                            break
                        payload = json.loads(message)
                        if not isinstance(payload, dict):
                            raise ValueError("bridge message must be a JSON object")
                        await self.accept(payload)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                self.state = ConnectorState.OFFLINE_BUFFERING
                self.reconnect_count += 1
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
                delay = min(delay * 2.0, 30.0)
        self.state = ConnectorState.STOPPED

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self.state = ConnectorState.STOPPED


rig_stream_manager = RigStreamManager()
