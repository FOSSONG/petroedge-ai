from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.rbac import require_roles
from app.workflows import (
    WorkflowDefinition,
    WorkflowError,
    WorkflowNotFoundError,
    WorkflowRunRequest,
    workflow_engine,
)
from app.workflows.registry import node_registry

router = APIRouter()

READ_ROLES = ("admin", "geoscientist", "engineer", "viewer")
WRITE_ROLES = ("admin", "geoscientist", "engineer")


@router.get("")
async def list_workflows(
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    workflows = workflow_engine.list_workflows()
    return {
        "count": len(workflows),
        "workflows": [workflow.model_dump(mode="json") for workflow in workflows],
    }


@router.get("/templates")
async def list_templates(
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    workflows = workflow_engine.list_workflows()
    return {
        "count": len(workflows),
        "templates": [workflow.model_dump(mode="json") for workflow in workflows],
    }


@router.get("/nodes")
async def list_node_types(
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    node_types = node_registry.list_types()
    return {"count": len(node_types), "node_types": node_types}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_workflow(
    definition: WorkflowDefinition,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    try:
        created = workflow_engine.register_workflow(definition)
    except WorkflowError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return created.model_dump(mode="json")


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    try:
        run = workflow_engine.get_run(run_id)
    except WorkflowNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return run.model_dump(mode="json")


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    try:
        workflow = workflow_engine.get_workflow(workflow_id)
    except WorkflowNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return workflow.model_dump(mode="json")


@router.post("/{workflow_id}/run")
async def run_workflow(
    workflow_id: str,
    request: WorkflowRunRequest,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    try:
        run = await workflow_engine.run(workflow_id, request)
    except WorkflowNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    response = run.model_dump(mode="json")
    if run.status.value == "failed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=response,
        )
    return response


@router.get("/{workflow_id}/status")
async def workflow_status(
    workflow_id: str,
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    try:
        workflow = workflow_engine.get_workflow(workflow_id)
    except WorkflowNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return {
        "workflow_id": workflow.id,
        "status": "available",
        "node_count": len(workflow.nodes),
    }