from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.rbac import require_roles
from app.rules import RuleCreate, rule_engine

router = APIRouter()

READ_ROLES = ("admin", "geoscientist", "engineer", "viewer")
WRITE_ROLES = ("admin", "geoscientist", "engineer")


@router.get("")
async def list_rules(
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    rules = rule_engine.list()
    return {
        "count": len(rules),
        "rules": [item.model_dump(mode="json") for item in rules],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_rule(
    request: RuleCreate,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    try:
        rule = rule_engine.register(request, replace=False)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return rule.model_dump(mode="json")


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: str,
    _: dict[str, Any] = Depends(require_roles("admin")),
) -> Response:
    try:
        rule_engine.delete(rule_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Rule not found.") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)