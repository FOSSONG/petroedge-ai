from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user


ROLE_HIERARCHY: dict[str, set[str]] = {
    # Full platform superuser.
    "admin": {
        "admin",
        "administrator",
        "operator",
        "petrophysicist",
        "geoscientist",
        "engineer",
        "viewer",
    },

    # Administrator is maintained as an enterprise-facing alias for admin.
    # Including "admin" preserves compatibility with existing admin-only
    # dependencies and the Milestone 1 regression contract.
    "administrator": {
        "admin",
        "administrator",
        "operator",
        "petrophysicist",
        "geoscientist",
        "engineer",
        "viewer",
    },

    # Operations personnel can access operational, technical and read views.
    "operator": {
        "operator",
        "petrophysicist",
        "geoscientist",
        "engineer",
        "viewer",
    },

    # Petrophysicists inherit geoscience and read-only capabilities.
    "petrophysicist": {
        "petrophysicist",
        "geoscientist",
        "viewer",
    },

    "geoscientist": {
        "geoscientist",
        "viewer",
    },

    "engineer": {
        "engineer",
        "viewer",
    },

    "viewer": {
        "viewer",
    },
}

VALID_ROLES = frozenset(ROLE_HIERARCHY)


def effective_roles(roles: list[str] | set[str]) -> set[str]:
    expanded: set[str] = set()

    for role in roles:
        normalised_role = str(role).strip().lower()
        if not normalised_role:
            continue

        expanded.update(
            ROLE_HIERARCHY.get(normalised_role, {normalised_role})
        )

    return expanded


def require_roles(*allowed_roles: str) -> Callable[..., Any]:
    requested = {
        role.strip().lower()
        for role in allowed_roles
        if role and role.strip()
    }

    if not requested:
        raise ValueError("At least one allowed role is required.")

    unknown = requested - VALID_ROLES
    if unknown:
        raise ValueError(
            f"Unknown role(s): {', '.join(sorted(unknown))}"
        )

    async def dependency(
        user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        raw_roles = user.get("roles", [])
        user_roles = effective_roles(set(raw_roles))

        if user_roles.isdisjoint(requested):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "Insufficient permissions.",
                    "required_roles": sorted(requested),
                    "effective_roles": sorted(user_roles),
                },
            )

        return user

    return dependency


def require_admin() -> Callable[..., Any]:
    return require_roles("admin")
