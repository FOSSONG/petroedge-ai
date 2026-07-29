from __future__ import annotations

from typing import Any

from fastapi import (
    Depends,
APIRouter,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)

from app.core.security import decode_access_token, get_current_user
from app.realtime.events import get_event_bus
from app.realtime.manager import ClientConnection, get_connection_manager

router = APIRouter()


KNOWN_CHANNELS = frozenset(
    {
        "global",
        "alerts",
        "jobs",
        "models",
        "wells",
        "analytics",
        "streaming",
        "system",
    }
)


ROLE_CHANNELS: dict[str, frozenset[str]] = {
    "admin": KNOWN_CHANNELS | {"*"},
    "administrator": KNOWN_CHANNELS | {"*"},
    "operator": frozenset(
        {"global", "alerts", "jobs", "models", "wells", "analytics", "streaming"}
    ),
    "engineer": frozenset(
        {"global", "alerts", "jobs", "models", "wells", "analytics", "streaming"}
    ),
    "geoscientist": frozenset(
        {"global", "alerts", "models", "wells", "analytics", "streaming"}
    ),
    "analyst": frozenset(
        {"global", "alerts", "models", "wells", "analytics"}
    ),
    "viewer": frozenset({"global", "alerts", "models", "wells"}),
}


def _extract_websocket_token(websocket: WebSocket) -> str | None:
    raw_protocols = websocket.headers.get("sec-websocket-protocol", "")
    protocols = [item.strip() for item in raw_protocols.split(",") if item.strip()]

    if len(protocols) < 2 or protocols[0] != "petroedge":
        return None

    return protocols[1]


def _normalise_roles(claims: dict[str, Any]) -> set[str]:
    raw_roles = claims.get("roles", [])

    if not isinstance(raw_roles, list):
        return set()

    return {
        str(role).strip().lower()
        for role in raw_roles
        if str(role).strip()
    }


def _authorised_channels(
    requested_channels: set[str],
    roles: set[str],
) -> set[str]:
    allowed = {"global"}

    for role in roles:
        allowed.update(ROLE_CHANNELS.get(role, frozenset()))

    clean_requested = {
        channel.strip().lower()
        for channel in requested_channels
        if channel and channel.strip()
    }

    if "*" in allowed:
        return clean_requested or {"global"}

    return (clean_requested & allowed) or {"global"}


async def _reject_socket(
    websocket: WebSocket,
    *,
    code: int,
    reason: str,
) -> None:
    await websocket.accept(subprotocol="petroedge")
    await websocket.close(code=code, reason=reason)


@router.get("/health")
async def realtime_health() -> dict[str, Any]:
    return await get_connection_manager().snapshot()


@router.post("/test-event")
async def publish_test_event(
    message: str = Query(default="PetroEdge real-time channel is operational"),
    channel: str = Query(default="global"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    roles = _normalise_roles(current_user)

    allowed_roles = {
        "admin",
        "administrator",
        "operator",
        "engineer",
    }

    if not roles.intersection(allowed_roles):
        raise HTTPException(
            status_code=403,
            detail="You are not authorised to publish realtime test events.",
        )

    requested_channel = channel.strip().lower() or "global"
    authorised = _authorised_channels({requested_channel}, roles)

    if requested_channel not in authorised:
        raise HTTPException(
            status_code=403,
            detail=f"You are not authorised to publish to channel: {requested_channel}",
        )

    actor_id = str(
        current_user.get("uid")
        or current_user.get("id")
        or current_user.get("sub")
        or "unknown"
    )

    event = await get_event_bus().emit(
        "system.test",
        {"message": message},
        channel=requested_channel,
        actor_id=actor_id,
    )

    return event.to_dict()


@router.websocket("/ws")
async def realtime_socket(websocket: WebSocket) -> None:
    token = _extract_websocket_token(websocket)

    if not token:
        await _reject_socket(
            websocket,
            code=4401,
            reason="Missing access token.",
        )
        return

    try:
        claims = decode_access_token(token)
    except HTTPException as exc:
        await _reject_socket(
            websocket,
            code=4401,
            reason=str(exc.detail),
        )
        return

    username = str(claims["sub"])
    user_id = str(claims.get("uid") or username)
    roles = _normalise_roles(claims)

    raw_channels = websocket.query_params.get("channels", "global")
    requested_channels = {
        item.strip().lower()
        for item in raw_channels.split(",")
        if item.strip()
    }
    initial_channels = _authorised_channels(requested_channels, roles)

    manager = get_connection_manager()
    client: ClientConnection | None = None

    try:
        client = await manager.connect(
            websocket,
            user_id=user_id,
            initial_channels=initial_channels,
        )

        while True:
            message = await websocket.receive_json()

            try:
                decode_access_token(token)
            except HTTPException:
                await websocket.close(
                    code=4401,
                    reason="Access token has expired or is invalid.",
                )
                return

            action = str(message.get("action", "ping")).strip().lower()

            if action == "ping":
                await manager.send_json(
                    client.client_id,
                    {
                        "event_type": "connection.pong",
                        "channel": "system",
                        "payload": {
                            "client_id": client.client_id,
                            "authenticated": True,
                            "user_id": user_id,
                        },
                    },
                )
                continue

            if action in {"subscribe", "unsubscribe"}:
                raw_requested = message.get("channels", [])

                if not isinstance(raw_requested, list):
                    raw_requested = []

                requested = {
                    str(item).strip().lower()
                    for item in raw_requested
                    if str(item).strip()
                }
                authorised = _authorised_channels(requested, roles)
                denied = sorted(requested - authorised)

                if denied:
                    await manager.send_json(
                        client.client_id,
                        {
                            "event_type": "connection.error",
                            "channel": "system",
                            "payload": {
                                "message": "One or more channels are not authorised.",
                                "denied_channels": denied,
                            },
                        },
                    )

                if action == "subscribe":
                    active = await manager.subscribe(
                        client.client_id,
                        authorised,
                    )
                else:
                    active = await manager.unsubscribe(
                        client.client_id,
                        authorised,
                    )

                await manager.send_json(
                    client.client_id,
                    {
                        "event_type": "connection.channels_updated",
                        "channel": "system",
                        "payload": {"channels": sorted(active)},
                    },
                )
                continue

            await manager.send_json(
                client.client_id,
                {
                    "event_type": "connection.error",
                    "channel": "system",
                    "payload": {"message": f"Unsupported action: {action}"},
                },
            )

    except WebSocketDisconnect:
        pass
    finally:
        if client is not None:
            await manager.disconnect(client.client_id)