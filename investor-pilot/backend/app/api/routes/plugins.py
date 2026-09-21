from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.core.rbac import require_roles
from app.plugins import module_catalogue

router = APIRouter()


@router.get("/modules")
async def list_builtin_modules(
    _: dict[str, Any] = Depends(
        require_roles(
            "admin", "administrator", "operator", "petrophysicist",
            "geoscientist", "engineer", "viewer",
        )
    ),
) -> dict[str, Any]:
    modules = module_catalogue()
    return {
        "architecture": "level-1-built-in-lazy-modules",
        "module_count": len(modules),
        "modules": modules,
    }
