"""Request-scoped private asset ownership; direct internal jobs remain explicit trusted callers."""
from contextvars import ContextVar
from fastapi import HTTPException

principal = ContextVar("asset_principal", default=None)


def identity(user):
    return str(user.get("user_id") or user.get("uid") or user.get("username") or user.get("sub") or "") or None


def set_principal(user):
    principal.set(dict(user))


def owner_id(fallback=None):
    user=principal.get()
    if user is None:
        return fallback
    value=identity(user)
    if not value:
        raise HTTPException(status_code=401,detail="Authenticated asset owner is required.")
    return value


def visible(owner):
    user=principal.get()
    if user is None:  # Internal scripts without an HTTP request.
        return True
    roles={str(r).lower() for r in user.get("roles",[])}
    if roles & {"admin","administrator"}:
        return True
    return bool(owner and identity(user) and str(owner)==identity(user))


def require_owner(owner):
    if not visible(owner):
        raise HTTPException(status_code=404,detail="Asset not found.")


class OwnershipContextMiddleware:
    def __init__(self,app): self.app=app
    async def __call__(self,scope,receive,send):
        if scope["type"] not in {"http","websocket"}:
            return await self.app(scope,receive,send)
        token=principal.set({})  # Unauthenticated requests fail closed.
        try: await self.app(scope,receive,send)
        finally: principal.reset(token)
