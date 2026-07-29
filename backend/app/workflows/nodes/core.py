from __future__ import annotations

from statistics import mean
from typing import Any

from app.ai.registry import registry as model_registry
from app.agents import AgentRequest, agent_orchestrator
from app.digital_twin import digital_twin_orchestrator
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
        data = context.inputs.get(str(key))

        if isinstance(data, list):
            return {"rows": data}

        return {str(key): data}

    return context.inputs


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



async def multi_agent_analysis(node: NodeSpec, context: WorkflowContext) -> dict[str, Any]:
    dependencies = context.dependency_payload(node.depends_on)
    rows: list[dict[str, Any]] = []

    for dependency in dependencies.values():
        candidate = dependency.get("rows")
        if isinstance(candidate, list) and all(isinstance(item, dict) for item in candidate):
            rows = candidate
            break

    agent_keys = node.parameters.get("agents")
    request = AgentRequest(
        inputs={"rows": rows},
        context={
            "workflow_id": context.workflow_id,
            "run_id": context.run_id,
            "dependencies": dependencies,
        },
        agent_keys=agent_keys if isinstance(agent_keys, list) else None,
    )
    result = await agent_orchestrator.execute(request)
    return result.model_dump(mode="json")

async def digital_twin_update(node: NodeSpec, context: WorkflowContext) -> dict[str, Any]:
    dependencies = context.dependency_payload(node.depends_on)
    rows: list[dict[str, Any]] = []

    for dependency in dependencies.values():
        candidate = dependency.get("rows")
        if isinstance(candidate, list) and all(isinstance(item, dict) for item in candidate):
            rows = candidate
            break

    reservoir_id = str(
        node.parameters.get("reservoir_id")
        or context.inputs.get("reservoir_id")
        or "PETROEDGE-DEMO"
    )

    state = digital_twin_orchestrator.ingest_rows(
        reservoir_id=reservoir_id,
        rows=rows,
        source_reference=f"{context.workflow_id}:{context.run_id}",
    )
    return {
        "reservoir_id": reservoir_id,
        "state": state.model_dump(mode="json"),
        "row_count": len(rows),
        "status": "updated",
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
        "agents.panel": multi_agent_analysis,
        "digital_twin.update": digital_twin_update,
        "report.summary": report_summary,
        "storage.passthrough": passthrough,
    }

    for node_type, handler in handlers.items():
        node_registry.register(node_type, handler, replace=True)
