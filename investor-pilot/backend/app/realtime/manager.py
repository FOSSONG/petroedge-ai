from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.realtime.events import EventEnvelope, EventBus, get_event_bus

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ClientConnection:
    client_id: str
    websocket: WebSocket
    channels: set[str] = field(default_factory=lambda: {"global"})
    connected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    user_id: str | None = None


class ConnectionManager:
    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._clients: dict[str, ClientConnection] = {}
        self._lock = asyncio.Lock()
        self._event_bus = event_bus or get_event_bus()
        self._started = False

    @property
    def connection_count(self) -> int:
        return len(self._clients)

    async def start(self) -> None:
        if self._started:
            return
        await self._event_bus.subscribe("*", self.broadcast_event)
        self._started = True

    async def stop(self) -> None:
        if not self._started:
            return
        await self._event_bus.unsubscribe("*", self.broadcast_event)
        async with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            try:
                await client.websocket.close(code=1001, reason="Server shutdown")
            except Exception:
                pass
        self._started = False

    async def connect(
        self,
        websocket: WebSocket,
        *,
        user_id: str | None = None,
        initial_channels: set[str] | None = None,
    ) -> ClientConnection:
        await websocket.accept(subprotocol="petroedge")
        client = ClientConnection(
            client_id=str(uuid.uuid4()),
            websocket=websocket,
            channels=initial_channels or {"global"},
            user_id=user_id,
        )
        async with self._lock:
            self._clients[client.client_id] = client
        await self.send_json(
            client.client_id,
            {
                "event_type": "connection.ready",
                "channel": "system",
                "payload": {
                    "client_id": client.client_id,
                    "channels": sorted(client.channels),
                    "connected_at": client.connected_at,
                },
            },
        )
        return client

    async def disconnect(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)

    async def subscribe(self, client_id: str, channels: set[str]) -> set[str]:
        clean = {channel.strip() for channel in channels if channel.strip()}
        async with self._lock:
            client = self._clients.get(client_id)
            if client is None:
                raise LookupError("WebSocket client is not connected.")
            client.channels.update(clean)
            return set(client.channels)

    async def unsubscribe(self, client_id: str, channels: set[str]) -> set[str]:
        async with self._lock:
            client = self._clients.get(client_id)
            if client is None:
                raise LookupError("WebSocket client is not connected.")
            client.channels.difference_update(channels)
            client.channels.add("global")
            return set(client.channels)

    async def send_json(self, client_id: str, message: dict[str, Any]) -> bool:
        async with self._lock:
            client = self._clients.get(client_id)
        if client is None:
            return False
        try:
            if client.websocket.application_state == WebSocketState.CONNECTED:
                await client.websocket.send_json(message)
                return True
        except Exception:
            logger.debug("WebSocket send failed for %s", client_id, exc_info=True)
        await self.disconnect(client_id)
        return False

    async def broadcast_event(self, event: EventEnvelope) -> None:
        message = event.to_dict()
        async with self._lock:
            recipients = [
                client
                for client in self._clients.values()
                if event.channel in client.channels or "*" in client.channels
            ]
        if not recipients:
            return
        results = await asyncio.gather(
            *(self.send_json(client.client_id, message) for client in recipients),
            return_exceptions=True,
        )
        failures = sum(1 for result in results if result is False or isinstance(result, Exception))
        if failures:
            logger.debug("WebSocket event %s had %s failed deliveries", event.event_id, failures)

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            clients = list(self._clients.values())
        channel_counts: dict[str, int] = {}
        for client in clients:
            for channel in client.channels:
                channel_counts[channel] = channel_counts.get(channel, 0) + 1
        return {
            "status": "healthy" if self._started else "stopped",
            "started": self._started,
            "connections": len(clients),
            "channels": channel_counts,
        }


_connection_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    return _connection_manager
