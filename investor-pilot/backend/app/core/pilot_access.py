"""Persistent pilot access switch. Only the configured owner administers it."""
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from fastapi import HTTPException
from app.core.config import settings


def access_state(paused=None, actor=None):
    path = Path.cwd() / "data" / "pilot_access.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=30) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS access_state (id INTEGER PRIMARY KEY CHECK(id=1), paused INTEGER NOT NULL, updated_at TEXT, actor TEXT)")
        conn.execute("INSERT OR IGNORE INTO access_state VALUES (1,0,NULL,NULL)")
        if paused is not None:
            conn.execute("UPDATE access_state SET paused=?, updated_at=?, actor=? WHERE id=1", (int(paused),datetime.now(timezone.utc).isoformat(),actor))
        row=conn.execute("SELECT paused,updated_at,actor FROM access_state WHERE id=1").fetchone()
    return {"paused":bool(row[0]),"updated_at":row[1],"actor":row[2],"owner_configured":bool(settings.pilot_owner_email)}


def enforce_pilot(user):
    owner = (settings.pilot_owner_email or "").strip().lower()
    if not owner:
        return
    if user["username"].lower() == owner:
        if not set(user["roles"]) & {"admin", "administrator"}:
            raise HTTPException(403,"Configured pilot owner must hold the administrator role.")
        return
    if set(user["roles"]) & {"admin", "administrator"}:
        raise HTTPException(403,"Only the configured pilot owner may administer this deployment.")
    if access_state()["paused"]:
        raise HTTPException(403,"The owner has paused pilot access.")


def require_pilot_owner(user):
    if not settings.pilot_owner_email or user["username"].lower() != settings.pilot_owner_email.strip().lower():
        raise HTTPException(403,"Only the configured pilot owner can manage customer access.")
    if not set(user["roles"]) & {"admin","administrator"}:
        raise HTTPException(403,"Administrator role required.")


class PilotBoundaryMiddleware:
    """Enforce the pilot boundary even on legacy routes without dependencies.

    Unscoped global event feeds are owner-only until tenant filtering exists.
    Every outbound WebSocket event rechecks account and pause state.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if not settings.pilot_owner_email or scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        if scope["type"] == "http" and (scope.get("method") == "OPTIONS" or path in {"/health", "/api/v1/auth/login", "/api/v1/auth/status", "/api/v1/auth/duo/callback", "/api/v1/auth/duo/complete"}):
            return await self.app(scope, receive, send)
        if scope["type"] == "http" and not path.startswith(("/api/", "/docs", "/redoc", "/openapi")):
            return await self.app(scope, receive, send)
        from starlette.responses import JSONResponse
        from app.core.security import decode_access_token, resolve_current_user
        from app.db.session import SessionLocal
        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode()
        token = auth[7:] if auth.lower().startswith("bearer ") else None
        if scope["type"] == "websocket":
            protocols = scope.get("subprotocols", [])
            token = protocols[1] if len(protocols)>1 and protocols[0]=="petroedge" else None

        def check():
            if not token: raise HTTPException(401,"Authentication required.")
            with SessionLocal() as db:
                user = resolve_current_user(decode_access_token(token), db)
            if scope["type"] == "websocket":
                require_pilot_owner(user)
            return user

        try: check()
        except HTTPException as exc:
            if scope["type"] == "websocket":
                await send({"type":"websocket.close","code":4403})
            else:
                await JSONResponse({"detail":exc.detail},status_code=exc.status_code)(scope,receive,send)
            return
        closed = False
        async def checked_send(message):
            nonlocal closed
            if closed: return
            if scope["type"] == "websocket" and message["type"] in {"websocket.accept", "websocket.send"}:
                try: check()
                except HTTPException:
                    closed = True
                    await send({"type":"websocket.close","code":4403})
                    from starlette.websockets import WebSocketDisconnect
                    raise WebSocketDisconnect(4403)
            await send(message)
        await self.app(scope,receive,checked_send)
