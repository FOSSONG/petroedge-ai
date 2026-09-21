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