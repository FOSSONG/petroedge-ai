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