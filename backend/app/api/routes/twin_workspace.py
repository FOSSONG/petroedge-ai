from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.core.rbac import require_roles
from app.digital_twin import TwinRegistryError, health_engine, twin_history, twin_registry

router = APIRouter()
READ = require_roles("admin", "administrator", "operator", "engineer", "geoscientist", "petrophysicist", "viewer")
WRITE = require_roles("admin", "administrator", "operator", "engineer", "geoscientist", "petrophysicist")


class ScenarioAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=300)
    operation: Literal["set", "increase", "decrease", "multiply"]
    value: float


class WorkspaceScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=200)
    adjustments: list[ScenarioAdjustment] = Field(min_length=1, max_length=25)


def _get_parent(document: dict[str, Any], path: str) -> tuple[dict[str, Any], str]:
    parts = [part for part in path.split(".") if part]
    if not parts:
        raise ValueError("Scenario path cannot be empty.")
    current: Any = document
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"Unknown scenario path: {path}")
        current = current[part]
    if not isinstance(current, dict):
        raise ValueError(f"Scenario path is not editable: {path}")
    return current, parts[-1]


def _apply(document: dict[str, Any], item: ScenarioAdjustment) -> dict[str, Any]:
    parent, key = _get_parent(document, item.path)
    if key not in parent:
        raise ValueError(f"Unknown scenario path: {item.path}")
    before = parent[key]
    if item.operation == "set":
        after: Any = item.value
    else:
        if not isinstance(before, (int, float)):
            raise ValueError(f"{item.operation.title()} requires a numeric value: {item.path}")
        if item.operation == "increase":
            after = float(before) + item.value
        elif item.operation == "decrease":
            after = float(before) - item.value
        else:
            after = float(before) * item.value
    parent[key] = after
    return {"path": item.path, "operation": item.operation, "before": before, "after": after}


@router.get("/{reservoir_id}/summary")
def summary(reservoir_id: str, _: dict[str, Any] = Depends(READ)) -> dict[str, Any]:
    try:
        twin = twin_registry.get(reservoir_id)
        health = health_engine.evaluate(twin)
    except TwinRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    history = twin_history.list(reservoir_id)
    return {
        "twin": twin.model_dump(mode="json"),
        "health": health.model_dump(mode="json"),
        "history_count": len(history),
        "latest_version": history[-1].version if history else None,
        "methodology": {
            "classification": "operational digital-twin state management",
            "scenario_mode": "non-persistent transparent state perturbation",
            "limitations": [
                "Not a full-physics reservoir simulator",
                "No automatic history matching",
                "No calibrated production forecast unless supplied by a validated model",
            ],
        },
    }


@router.post("/{reservoir_id}/scenario")
def scenario(
    reservoir_id: str,
    request: WorkspaceScenarioRequest,
    _: dict[str, Any] = Depends(WRITE),
) -> dict[str, Any]:
    try:
        twin = twin_registry.get(reservoir_id)
    except TwinRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    baseline = twin.model_dump(mode="json")
    scenario_state = deepcopy(baseline)
    changes: list[dict[str, Any]] = []
    try:
        for adjustment in request.adjustments:
            changes.append(_apply(scenario_state, adjustment))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "reservoir_id": reservoir_id,
        "scenario_name": request.name,
        "persisted": False,
        "baseline": baseline,
        "scenario": scenario_state,
        "changes": changes,
        "warning": "Scenario comparison changes state values only. It is not a full-physics flow simulation.",
    }