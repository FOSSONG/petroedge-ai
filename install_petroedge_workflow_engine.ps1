param(
    [string]$ProjectRoot = (Get-Location).Path
)

$ErrorActionPreference = "Stop"

$BackendRoot = Join-Path $ProjectRoot "backend"
$AppRoot = Join-Path $BackendRoot "app"

if (-not (Test-Path (Join-Path $AppRoot "main.py"))) {
    throw "PetroEdge backend not found. Run this script from the PetroEdge-AI-v1-demo project root."
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $ProjectRoot "backups\workflow-engine-$Timestamp"
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

$FilesToBackup = @(
    "backend\app\main.py",
    "backend\app\api\routes\workflows.py"
)

foreach ($RelativePath in $FilesToBackup) {
    $Source = Join-Path $ProjectRoot $RelativePath
    if (Test-Path $Source) {
        $Destination = Join-Path $BackupRoot $RelativePath
        New-Item -ItemType Directory -Force -Path (Split-Path $Destination) | Out-Null
        Copy-Item $Source $Destination -Force
    }
}

$Directories = @(
    "backend\app\workflows",
    "backend\app\workflows\nodes",
    "backend\tests"
)

foreach ($Directory in $Directories) {
    New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot $Directory) | Out-Null
}

function Write-Utf8File {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$Content
    )
    $Target = Join-Path $ProjectRoot $RelativePath
    New-Item -ItemType Directory -Force -Path (Split-Path $Target) | Out-Null
    [System.IO.File]::WriteAllText(
        $Target,
        $Content,
        [System.Text.UTF8Encoding]::new($false)
    )
}

Write-Utf8File "backend\app\workflows\schemas.py" @'
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class NodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    type: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    name: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    enabled: bool = True


class WorkflowDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    name: str
    description: str = ""
    version: str = "1.0.0"
    tags: list[str] = Field(default_factory=list)
    nodes: list[NodeSpec]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph(self) -> "WorkflowDefinition":
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Workflow node IDs must be unique.")

        known = set(node_ids)
        for node in self.nodes:
            missing = set(node.depends_on) - known
            if missing:
                raise ValueError(
                    f"Node {node.id!r} depends on unknown nodes: {sorted(missing)}"
                )
            if node.id in node.depends_on:
                raise ValueError(f"Node {node.id!r} cannot depend on itself.")
        return self


class WorkflowRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inputs: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)


class NodeRunResult(BaseModel):
    node_id: str
    node_type: str
    status: RunStatus
    started_at: str
    finished_at: str | None = None
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class WorkflowRun(BaseModel):
    run_id: str
    workflow_id: str
    status: RunStatus
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    node_results: list[NodeRunResult] = Field(default_factory=list)
    error: str | None = None
'@

Write-Utf8File "backend\app\workflows\context.py" @'
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WorkflowContext:
    workflow_id: str
    run_id: str
    inputs: dict[str, Any]
    parameters: dict[str, Any] = field(default_factory=dict)
    node_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)

    def dependency_payload(self, dependency_ids: list[str]) -> dict[str, Any]:
        return {
            dependency_id: self.node_outputs[dependency_id]
            for dependency_id in dependency_ids
            if dependency_id in self.node_outputs
        }
'@

Write-Utf8File "backend\app\workflows\registry.py" @'
from __future__ import annotations

import threading
from collections.abc import Awaitable, Callable
from typing import Any

from app.workflows.context import WorkflowContext
from app.workflows.schemas import NodeSpec

NodeHandler = Callable[[NodeSpec, WorkflowContext], Awaitable[dict[str, Any]]]


class NodeRegistryError(RuntimeError):
    pass


class NodeRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, NodeHandler] = {}
        self._lock = threading.RLock()

    def register(
        self,
        node_type: str,
        handler: NodeHandler,
        *,
        replace: bool = False,
    ) -> None:
        with self._lock:
            if node_type in self._handlers and not replace:
                raise NodeRegistryError(f"Node type already registered: {node_type}")
            self._handlers[node_type] = handler

    def handler(self, node_type: str) -> NodeHandler:
        try:
            return self._handlers[node_type]
        except KeyError as exc:
            raise NodeRegistryError(f"Unknown workflow node type: {node_type}") from exc

    def list_types(self) -> list[str]:
        return sorted(self._handlers)


node_registry = NodeRegistry()
'@

Write-Utf8File "backend\app\workflows\nodes\core.py" @'
from __future__ import annotations

from statistics import mean
from typing import Any

from app.ai.registry import registry as model_registry
from app.workflows.context import WorkflowContext
from app.workflows.registry import node_registry
from app.workflows.schemas import NodeSpec


def _as_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    return []


async def input_payload(node: NodeSpec, context: WorkflowContext) -> dict[str, Any]:
    key = node.parameters.get("key")
    if key:
        return {"value": context.inputs.get(str(key))}
    return {"inputs": context.inputs}


async def quality_control(node: NodeSpec, context: WorkflowContext) -> dict[str, Any]:
    source = node.parameters.get("source")
    rows = _as_rows(context.inputs.get(str(source))) if source else []
    if not rows:
        for dependency in context.dependency_payload(node.depends_on).values():
            rows = _as_rows(dependency.get("rows"))
            if rows:
                break

    columns = sorted({key for row in rows for key in row})
    missing_by_column = {
        column: sum(row.get(column) in (None, "") for row in rows)
        for column in columns
    }
    return {
        "rows": rows,
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": columns,
        "missing_by_column": missing_by_column,
    }


async def feature_engineering(node: NodeSpec, context: WorkflowContext) -> dict[str, Any]:
    dependencies = context.dependency_payload(node.depends_on)
    rows: list[dict[str, Any]] = []
    for dependency in dependencies.values():
        rows = _as_rows(dependency.get("rows"))
        if rows:
            break

    numeric_columns = sorted(
        {
            key
            for row in rows
            for key, value in row.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
    )
    summary = {}
    for column in numeric_columns:
        values = [
            float(row[column])
            for row in rows
            if isinstance(row.get(column), (int, float))
            and not isinstance(row.get(column), bool)
        ]
        if values:
            summary[column] = {
                "count": len(values),
                "mean": mean(values),
                "min": min(values),
                "max": max(values),
            }
    return {"rows": rows, "numeric_summary": summary}


async def petrophysics(node: NodeSpec, context: WorkflowContext) -> dict[str, Any]:
    dependencies = context.dependency_payload(node.depends_on)
    rows: list[dict[str, Any]] = []
    for dependency in dependencies.values():
        rows = _as_rows(dependency.get("rows"))
        if rows:
            break

    rho_matrix = float(node.parameters.get("rho_matrix", 2.65))
    rho_fluid = float(node.parameters.get("rho_fluid", 1.0))
    rhob_column = str(node.parameters.get("rhob_column", "RHOB"))
    gr_column = str(node.parameters.get("gr_column", "GR"))
    rt_column = str(node.parameters.get("rt_column", "RT"))
    rw = float(node.parameters.get("rw", 0.1))
    a = float(node.parameters.get("archie_a", 1.0))
    m = float(node.parameters.get("archie_m", 2.0))
    n = float(node.parameters.get("archie_n", 2.0))

    enriched: list[dict[str, Any]] = []
    for row in rows:
        output = dict(row)
        rhob = row.get(rhob_column)
        gr = row.get(gr_column)
        rt = row.get(rt_column)

        if isinstance(rhob, (int, float)) and rho_matrix != rho_fluid:
            phi = (rho_matrix - float(rhob)) / (rho_matrix - rho_fluid)
            output["PHI_D"] = max(0.0, min(0.6, phi))

        if isinstance(gr, (int, float)):
            output["VSH_LINEAR"] = max(0.0, min(1.0, (float(gr) - 20.0) / 100.0))

        phi = output.get("PHI_D")
        if (
            isinstance(phi, (int, float))
            and phi > 0
            and isinstance(rt, (int, float))
            and float(rt) > 0
        ):
            sw = ((a * rw) / (float(rt) * (float(phi) ** m))) ** (1.0 / n)
            output["SW_ARCHIE"] = max(0.0, min(1.0, sw))

        enriched.append(output)

    return {"rows": enriched, "calculated_curves": ["PHI_D", "VSH_LINEAR", "SW_ARCHIE"]}


async def model_capability(node: NodeSpec, context: WorkflowContext) -> dict[str, Any]:
    model_key = str(node.parameters.get("model", "random_forest"))
    capability = model_registry.get_capability(model_key)
    dependencies = context.dependency_payload(node.depends_on)
    return {
        "model": capability.model_dump(mode="json"),
        "execution": "capability_resolved",
        "dependencies": dependencies,
        "message": (
            "The model capability was resolved successfully. "
            "Executable prediction requires a trained artefact and registered adapter."
        ),
    }


async def report_summary(node: NodeSpec, context: WorkflowContext) -> dict[str, Any]:
    dependencies = context.dependency_payload(node.depends_on)
    return {
        "title": str(node.parameters.get("title", "PetroEdge Workflow Report")),
        "workflow_id": context.workflow_id,
        "run_id": context.run_id,
        "sections": [
            {
                "node_id": dependency_id,
                "keys": sorted(payload.keys()),
            }
            for dependency_id, payload in dependencies.items()
        ],
        "status": "generated",
    }


async def passthrough(node: NodeSpec, context: WorkflowContext) -> dict[str, Any]:
    return {
        "parameters": node.parameters,
        "dependencies": context.dependency_payload(node.depends_on),
    }


def register_builtin_nodes() -> None:
    handlers = {
        "input.payload": input_payload,
        "qc.basic": quality_control,
        "features.summary": feature_engineering,
        "petrophysics.basic": petrophysics,
        "ai.model": model_capability,
        "report.summary": report_summary,
        "storage.passthrough": passthrough,
    }
    for node_type, handler in handlers.items():
        node_registry.register(node_type, handler, replace=True)
'@

Write-Utf8File "backend\app\workflows\nodes\__init__.py" @'
from app.workflows.nodes.core import register_builtin_nodes

__all__ = ["register_builtin_nodes"]
'@

Write-Utf8File "backend\app\workflows\templates.py" @'
from __future__ import annotations

from app.workflows.schemas import NodeSpec, WorkflowDefinition


BUILTIN_TEMPLATES: tuple[WorkflowDefinition, ...] = (
    WorkflowDefinition(
        id="well_log_interpretation",
        name="Well-log Interpretation",
        description="QC, feature summary, basic petrophysics, model selection and report.",
        tags=["well-logs", "petrophysics", "ai"],
        nodes=[
            NodeSpec(id="input", type="input.payload", parameters={"key": "rows"}),
            NodeSpec(id="qc", type="qc.basic", depends_on=["input"]),
            NodeSpec(id="features", type="features.summary", depends_on=["qc"]),
            NodeSpec(id="petrophysics", type="petrophysics.basic", depends_on=["features"]),
            NodeSpec(
                id="model",
                type="ai.model",
                parameters={"model": "random_forest"},
                depends_on=["petrophysics"],
            ),
            NodeSpec(
                id="report",
                type="report.summary",
                parameters={"title": "Well-log Interpretation Report"},
                depends_on=["qc", "petrophysics", "model"],
            ),
        ],
    ),
    WorkflowDefinition(
        id="production_forecast",
        name="Production Forecast",
        description="Production QC, feature summary and causal GRU capability resolution.",
        tags=["production", "forecasting", "gru"],
        nodes=[
            NodeSpec(id="input", type="input.payload", parameters={"key": "rows"}),
            NodeSpec(id="qc", type="qc.basic", depends_on=["input"]),
            NodeSpec(id="features", type="features.summary", depends_on=["qc"]),
            NodeSpec(
                id="model",
                type="ai.model",
                parameters={"model": "gru"},
                depends_on=["features"],
            ),
            NodeSpec(
                id="report",
                type="report.summary",
                parameters={"title": "Production Forecast Report"},
                depends_on=["model"],
            ),
        ],
    ),
    WorkflowDefinition(
        id="historical_replay",
        name="Historical Replay",
        description="Historical contextual analysis using the BiGRU capability.",
        tags=["replay", "bigru", "sequence"],
        nodes=[
            NodeSpec(id="input", type="input.payload", parameters={"key": "rows"}),
            NodeSpec(id="qc", type="qc.basic", depends_on=["input"]),
            NodeSpec(
                id="model",
                type="ai.model",
                parameters={"model": "bigru"},
                depends_on=["qc"],
            ),
            NodeSpec(
                id="report",
                type="report.summary",
                parameters={"title": "Historical Replay Report"},
                depends_on=["model"],
            ),
        ],
    ),
)
'@

Write-Utf8File "backend\app\workflows\engine.py" @'
from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from app.workflows.context import WorkflowContext
from app.workflows.nodes import register_builtin_nodes
from app.workflows.registry import NodeRegistry, node_registry
from app.workflows.schemas import (
    NodeRunResult,
    RunStatus,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunRequest,
)
from app.workflows.templates import BUILTIN_TEMPLATES


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class WorkflowError(RuntimeError):
    pass


class WorkflowNotFoundError(WorkflowError):
    pass


class WorkflowEngine:
    def __init__(self, registry: NodeRegistry = node_registry) -> None:
        self.registry = registry
        self._workflows: dict[str, WorkflowDefinition] = {}
        self._runs: dict[str, WorkflowRun] = {}
        self._lock = threading.RLock()
        register_builtin_nodes()
        for template in BUILTIN_TEMPLATES:
            self.register_workflow(template, replace=True)

    def register_workflow(
        self,
        definition: WorkflowDefinition,
        *,
        replace: bool = False,
    ) -> WorkflowDefinition:
        self._validate_acyclic(definition)
        for node in definition.nodes:
            if node.enabled:
                self.registry.handler(node.type)

        with self._lock:
            if definition.id in self._workflows and not replace:
                raise WorkflowError(f"Workflow already exists: {definition.id}")
            self._workflows[definition.id] = definition
        return definition

    def list_workflows(self) -> list[WorkflowDefinition]:
        return sorted(self._workflows.values(), key=lambda item: item.name.lower())

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition:
        try:
            return self._workflows[workflow_id]
        except KeyError as exc:
            raise WorkflowNotFoundError(f"Workflow not found: {workflow_id}") from exc

    def get_run(self, run_id: str) -> WorkflowRun:
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise WorkflowNotFoundError(f"Workflow run not found: {run_id}") from exc

    async def run(
        self,
        workflow_id: str,
        request: WorkflowRunRequest,
    ) -> WorkflowRun:
        definition = self.get_workflow(workflow_id)
        run_id = uuid.uuid4().hex
        run = WorkflowRun(
            run_id=run_id,
            workflow_id=workflow_id,
            status=RunStatus.queued,
            created_at=utc_now(),
            inputs=request.inputs,
        )
        self._runs[run_id] = run

        context = WorkflowContext(
            workflow_id=workflow_id,
            run_id=run_id,
            inputs=request.inputs,
            parameters=request.parameters,
        )

        run.status = RunStatus.running
        run.started_at = utc_now()

        try:
            for node in self._topological_order(definition):
                if not node.enabled:
                    continue

                result = NodeRunResult(
                    node_id=node.id,
                    node_type=node.type,
                    status=RunStatus.running,
                    started_at=utc_now(),
                )
                run.node_results.append(result)

                try:
                    handler = self.registry.handler(node.type)
                    output = await handler(node, context)
                    context.node_outputs[node.id] = output
                    result.output = output
                    result.status = RunStatus.succeeded
                    result.finished_at = utc_now()
                except Exception as exc:
                    result.status = RunStatus.failed
                    result.error = f"{type(exc).__name__}: {exc}"
                    result.finished_at = utc_now()
                    raise

            run.outputs = context.node_outputs
            run.status = RunStatus.succeeded
            run.finished_at = utc_now()
        except Exception as exc:
            run.status = RunStatus.failed
            run.error = f"{type(exc).__name__}: {exc}"
            run.finished_at = utc_now()

        return run

    async def run_background(
        self,
        workflow_id: str,
        request: WorkflowRunRequest,
    ) -> str:
        definition = self.get_workflow(workflow_id)
        run_id = uuid.uuid4().hex
        self._runs[run_id] = WorkflowRun(
            run_id=run_id,
            workflow_id=definition.id,
            status=RunStatus.queued,
            created_at=utc_now(),
            inputs=request.inputs,
        )

        async def runner() -> None:
            provisional_id = run_id
            completed = await self.run(workflow_id, request)
            completed.run_id = provisional_id
            self._runs[provisional_id] = completed

        asyncio.create_task(runner())
        return run_id

    @staticmethod
    def _validate_acyclic(definition: WorkflowDefinition) -> None:
        WorkflowEngine._topological_order(definition)

    @staticmethod
    def _topological_order(definition: WorkflowDefinition):
        enabled_nodes = {node.id: node for node in definition.nodes if node.enabled}
        remaining = {
            node_id: {dependency for dependency in node.depends_on if dependency in enabled_nodes}
            for node_id, node in enabled_nodes.items()
        }
        ordered = []

        while remaining:
            ready = sorted(node_id for node_id, dependencies in remaining.items() if not dependencies)
            if not ready:
                cycle_nodes = sorted(remaining)
                raise WorkflowError(f"Workflow contains a dependency cycle: {cycle_nodes}")

            for node_id in ready:
                ordered.append(enabled_nodes[node_id])
                remaining.pop(node_id)
                for dependencies in remaining.values():
                    dependencies.discard(node_id)

        return ordered


workflow_engine = WorkflowEngine()
'@

Write-Utf8File "backend\app\workflows\__init__.py" @'
from app.workflows.engine import (
    WorkflowEngine,
    WorkflowError,
    WorkflowNotFoundError,
    workflow_engine,
)
from app.workflows.schemas import (
    NodeSpec,
    RunStatus,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunRequest,
)

__all__ = [
    "NodeSpec",
    "RunStatus",
    "WorkflowDefinition",
    "WorkflowEngine",
    "WorkflowError",
    "WorkflowNotFoundError",
    "WorkflowRun",
    "WorkflowRunRequest",
    "workflow_engine",
]
'@

Write-Utf8File "backend\app\api\routes\workflows.py" @'
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
'@

Write-Utf8File "backend\tests\test_workflow_engine.py" @'
import pytest

from app.workflows.engine import WorkflowEngine, WorkflowError
from app.workflows.schemas import NodeSpec, RunStatus, WorkflowDefinition, WorkflowRunRequest


@pytest.mark.asyncio
async def test_builtin_well_log_workflow_runs() -> None:
    engine = WorkflowEngine()
    request = WorkflowRunRequest(
        inputs={
            "rows": [
                {"DEPTH": 1000.0, "GR": 45.0, "RHOB": 2.30, "RT": 10.0},
                {"DEPTH": 1000.5, "GR": 85.0, "RHOB": 2.45, "RT": 4.0},
            ]
        }
    )
    run = await engine.run("well_log_interpretation", request)

    assert run.status == RunStatus.succeeded
    assert "petrophysics" in run.outputs
    rows = run.outputs["petrophysics"]["rows"]
    assert "PHI_D" in rows[0]
    assert "VSH_LINEAR" in rows[0]
    assert "SW_ARCHIE" in rows[0]


@pytest.mark.asyncio
async def test_production_forecast_resolves_gru() -> None:
    engine = WorkflowEngine()
    run = await engine.run(
        "production_forecast",
        WorkflowRunRequest(
            inputs={
                "rows": [
                    {"month": 1, "oil_rate": 1000.0},
                    {"month": 2, "oil_rate": 980.0},
                ]
            }
        ),
    )
    assert run.status == RunStatus.succeeded
    assert run.outputs["model"]["model"]["key"] == "gru"
    assert run.outputs["model"]["model"]["causal"] is True


def test_cycle_is_rejected() -> None:
    engine = WorkflowEngine()
    with pytest.raises(WorkflowError):
        engine.register_workflow(
            WorkflowDefinition(
                id="cyclic",
                name="Cyclic",
                nodes=[
                    NodeSpec(id="a", type="storage.passthrough", depends_on=["b"]),
                    NodeSpec(id="b", type="storage.passthrough", depends_on=["a"]),
                ],
            )
        )
'@

Write-Utf8File "backend\tests\test_workflows_api.py" @'
from fastapi.testclient import TestClient

from app.main import app


def test_workflow_routes_are_present_in_openapi() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]
        assert "/api/v1/workflows" in paths
        assert "/api/v1/workflows/templates" in paths
        assert "/api/v1/workflows/nodes" in paths
        assert "/api/v1/workflows/{workflow_id}/run" in paths
        assert "/api/v1/workflows/runs/{run_id}" in paths
'@

Write-Utf8File "docs\workflow-engine.md" @'
# PetroEdge AI Workflow Engine

The workflow engine executes validated directed acyclic graphs of reusable processing nodes.

## Built-in templates

- `well_log_interpretation`
- `production_forecast`
- `historical_replay`

## Built-in node types

- `input.payload`
- `qc.basic`
- `features.summary`
- `petrophysics.basic`
- `ai.model`
- `report.summary`
- `storage.passthrough`

## API

- `GET /api/v1/workflows`
- `GET /api/v1/workflows/templates`
- `GET /api/v1/workflows/nodes`
- `POST /api/v1/workflows`
- `GET /api/v1/workflows/{workflow_id}`
- `POST /api/v1/workflows/{workflow_id}/run`
- `GET /api/v1/workflows/{workflow_id}/status`
- `GET /api/v1/workflows/runs/{run_id}`

The first implementation deliberately separates model capability resolution from trained-model inference. This prevents the platform from claiming predictions when no trained artefact or executable model adapter is available.
'@

# Ensure main.py registers workflows when it uses a static route module list.
$MainPath = Join-Path $AppRoot "main.py"
$MainContent = Get-Content $MainPath -Raw

if ($MainContent -notmatch '"workflows"' -and $MainContent -notmatch "'workflows'") {
    $Patterns = @(
        '(?s)(ROUTE_MODULES\s*=\s*\[)(.*?)(\])',
        '(?s)(route_modules\s*=\s*\[)(.*?)(\])',
        '(?s)(modules\s*=\s*\[)(.*?)(\])'
    )

    $Patched = $false
    foreach ($Pattern in $Patterns) {
        if ($MainContent -match $Pattern) {
            $MainContent = [regex]::Replace(
                $MainContent,
                $Pattern,
                {
                    param($match)
                    $body = $match.Groups[2].Value.TrimEnd()
                    $separator = if ($body.Trim().Length -eq 0 -or $body.TrimEnd().EndsWith(",")) { "" } else { "," }
                    return $match.Groups[1].Value + $body + $separator + "`n    `"workflows`"," + "`n" + $match.Groups[3].Value
                },
                1
            )
            $Patched = $true
            break
        }
    }

    if (-not $Patched) {
        Write-Warning "Could not automatically identify the static route list in main.py."
        Write-Warning "If /api/v1/workflows does not appear, add `"workflows`" to the route module list."
    } else {
        [System.IO.File]::WriteAllText(
            $MainPath,
            $MainContent,
            [System.Text.UTF8Encoding]::new($false)
        )
    }
}

Write-Host ""
Write-Host "PetroEdge Workflow Engine installed." -ForegroundColor Green
Write-Host "Backup created at: $BackupRoot" -ForegroundColor Cyan
Write-Host ""
Write-Host "Run next:" -ForegroundColor Yellow
Write-Host "  python -m pytest backend\tests\test_workflow_engine.py -q"
Write-Host "  python -m pytest backend\tests\test_workflows_api.py -q"
Write-Host "  python -m uvicorn app.main:app --reload --app-dir backend"
