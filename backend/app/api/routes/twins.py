from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.rbac import require_roles
from app.digital_twin import (
    SimulationError,
    SimulationRequest,
    TwinCreate,
    TwinRegistryError,
    TwinUpdate,
    digital_twin_orchestrator,
    health_engine,
    twin_history,
    twin_registry,
    twin_simulator,
)

router = APIRouter()

READ_ROLES = ("admin", "administrator", "operator", "engineer", "geoscientist", "petrophysicist", "viewer")
WRITE_ROLES = ("admin", "administrator", "operator", "engineer", "geoscientist", "petrophysicist")


@router.get("")
async def list_twins(
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    twins = twin_registry.list()
    return {
        "count": len(twins),
        "twins": [item.model_dump(mode="json") for item in twins],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_twin(
    request: TwinCreate,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    try:
        twin = digital_twin_orchestrator.create(request)
    except TwinRegistryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return twin.model_dump(mode="json")


@router.get("/{reservoir_id}")
async def get_twin(
    reservoir_id: str,
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    try:
        twin = twin_registry.get(reservoir_id)
    except TwinRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return twin.model_dump(mode="json")


@router.patch("/{reservoir_id}")
async def update_twin(
    reservoir_id: str,
    request: TwinUpdate,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    try:
        twin = digital_twin_orchestrator.update(reservoir_id, request)
    except TwinRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return twin.model_dump(mode="json")


@router.delete("/{reservoir_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_twin(
    reservoir_id: str,
    _: dict[str, Any] = Depends(require_roles("admin")),
) -> Response:
    try:
        twin_registry.delete(reservoir_id)
    except TwinRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{reservoir_id}/health")
async def get_health(
    reservoir_id: str,
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    try:
        report = health_engine.evaluate(twin_registry.get(reservoir_id))
    except TwinRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return report.model_dump(mode="json")


@router.get("/{reservoir_id}/history")
async def get_history(
    reservoir_id: str,
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    try:
        twin_registry.get(reservoir_id)
    except TwinRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    history = twin_history.list(reservoir_id)
    return {
        "reservoir_id": reservoir_id,
        "count": len(history),
        "snapshots": [item.model_dump(mode="json") for item in history],
    }


@router.post("/{reservoir_id}/restore/{version}")
async def restore_version(
    reservoir_id: str,
    version: int,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    try:
        twin = digital_twin_orchestrator.restore(reservoir_id, version)
    except (TwinRegistryError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return twin.model_dump(mode="json")


@router.post("/{reservoir_id}/simulate")
async def simulate(
    reservoir_id: str,
    request: SimulationRequest,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    try:
        result = twin_simulator.simulate(reservoir_id, request)
    except TwinRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SimulationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.model_dump(mode="json")