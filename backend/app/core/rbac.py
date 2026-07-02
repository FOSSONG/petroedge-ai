from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user


def require_roles(*allowed_roles: str) -> Callable:
    async def dependency(user: dict = Depends(get_current_user)) -> dict:
        user_roles = set(user.get("roles", []))
        if not user_roles.intersection(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {', '.join(allowed_roles)}",
            )
        return user

    return dependency

