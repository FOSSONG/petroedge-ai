from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents import AgentRequest, agent_orchestrator, agent_registry
from app.agents.registry import AgentRegistryError
from app.core.rbac import require_roles

router = APIRouter()

READ_ROLES = ("admin", "geoscientist", "engineer", "viewer")
WRITE_ROLES = ("admin", "geoscientist", "engineer")


@router.get("")
async def list_agents(
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    agents = agent_registry.list()
    return {
        "count": len(agents),
        "agents": [
            {
                "key": agent.key,
                "name": agent.name,
                "domain": agent.domain.value,
            }
            for agent in agents
        ],
    }


@router.get("/{agent_key}")
async def get_agent(
    agent_key: str,
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    try:
        agent = agent_registry.get(agent_key)
    except AgentRegistryError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return {
        "key": agent.key,
        "name": agent.name,
        "domain": agent.domain.value,
    }


@router.post("/panel/run")
async def run_agent_panel(
    request: AgentRequest,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    try:
        result = await agent_orchestrator.execute(request)
    except AgentRegistryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return result.model_dump(mode="json")


@router.post("/{agent_key}/run")
async def run_agent(
    agent_key: str,
    request: AgentRequest,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    request.agent_keys = [agent_key]
    try:
        result = await agent_orchestrator.execute(request)
    except AgentRegistryError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return result.model_dump(mode="json")