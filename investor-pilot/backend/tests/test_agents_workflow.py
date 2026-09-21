import pytest

from app.workflows.engine import WorkflowEngine
from app.workflows.schemas import RunStatus, WorkflowRunRequest


@pytest.mark.asyncio
async def test_multi_agent_workflow_runs() -> None:
    engine = WorkflowEngine()
    run = await engine.run(
        "multi_agent_interpretation",
        WorkflowRunRequest(
            inputs={
                "rows": [
                    {"DEPTH": 1000.0, "GR": 45.0, "RHOB": 2.30, "RT": 10.0},
                    {"DEPTH": 1000.5, "GR": 50.0, "RHOB": 2.28, "RT": 12.0},
                ]
            }
        ),
    )

    assert run.status == RunStatus.succeeded
    assert "agents" in run.outputs
    assert len(run.outputs["agents"]["agents"]) == 6
    assert "consensus" in run.outputs["agents"]