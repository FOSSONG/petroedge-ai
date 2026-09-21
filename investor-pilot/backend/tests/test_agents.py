import pytest

from app.agents import AgentRequest, agent_orchestrator, agent_registry


def test_builtin_agents_are_registered() -> None:
    assert {
        "geologist",
        "petrophysicist",
        "reservoir_engineer",
        "production_engineer",
        "drilling_engineer",
        "ccus",
    }.issubset(set(agent_registry.keys()))


@pytest.mark.asyncio
async def test_agent_panel_executes() -> None:
    result = await agent_orchestrator.execute(
        AgentRequest(
            inputs={
                "rows": [
                    {
                        "DEPTH": 1000.0,
                        "GR": 45.0,
                        "PHI_D": 0.24,
                        "SW_ARCHIE": 0.30,
                        "PERM": 250.0,
                        "Qoil STB/d": 1000.0,
                    }
                ]
            },
            agent_keys=["geologist", "petrophysicist", "reservoir_engineer"],
        )
    )

    assert len(result.agents) == 3
    assert result.consensus.overall_confidence > 0
    assert result.metadata["agent_count"] == 3


@pytest.mark.asyncio
async def test_petrophysicist_recognises_favourable_interval() -> None:
    result = await agent_orchestrator.execute(
        AgentRequest(
            inputs={
                "rows": [
                    {"PHI_D": 0.25, "SW_ARCHIE": 0.25},
                    {"PHI_D": 0.23, "SW_ARCHIE": 0.30},
                ]
            },
            agent_keys=["petrophysicist"],
        )
    )

    assert "favourable" in result.agents[0].summary.lower()