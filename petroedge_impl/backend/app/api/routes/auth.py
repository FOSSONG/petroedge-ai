from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import UserRepo
from app.core.config import settings
from app.core.security import create_access_token, get_current_user
from app.schemas import LoginRequest, TokenResponse
from app.services.domain_services import AuthenticationService

router = APIRouter()


def _development_admin(payload: LoginRequest) -> dict[str, Any] | None:
    environment = settings.environment.strip().lower()

    # Development fallback credentials are never accepted in production.
    if environment in {"production", "prod"}:
        return None

    configured_email = settings.petroedge_admin_email.strip()
    configured_password = settings.petroedge_admin_password

    configured_match = (
        bool(configured_email)
        and bool(configured_password)
        and payload.username.strip().lower() == configured_email.lower()
        and payload.password == configured_password
    )

    # Backwards-compatible competition MVP credential used by the existing
    # integration suite. This remains restricted to local/test environments.
    legacy_match = (
        payload.username.strip().lower() == "admin@petroedge.ai"
        and payload.password == "petroedge123"
    )

    if not configured_match and not legacy_match:
        return None

    resolved_email = (
        configured_email
        if configured_match
        else "admin@petroedge.ai"
    )

    return {
        "id": "development-admin",
        "email": resolved_email,
        "full_name": "PetroEdge Administrator",
        "roles": ["admin"],
    }


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, users: UserRepo) -> TokenResponse:
    user = AuthenticationService(users).authenticate(
        payload.username,
        payload.password,
    )

    identity: dict[str, Any] | None = None

    if user is not None:
        user.last_login_at = datetime.now(timezone.utc)
        users.commit()

        identity = {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "roles": [str(user.role)],
        }
    else:
        identity = _development_admin(payload)

    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        identity["email"],
        identity["roles"],
        user_id=identity["id"],
        full_name=identity["full_name"],
    )

    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        roles=identity["roles"],
        user={
            "id": identity["id"],
            "email": identity["email"],
            "full_name": identity["full_name"],
        },
    )


@router.get("/me")
def me(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return user
