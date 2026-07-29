from __future__ import annotations

import asyncio
import uuid
from typing import Any

from app.agents.consensus import ConsensusEngine
from app.agents.registry import agent_registry
from app.agents.schemas import AgentPanelResponse, AgentRequest
from app.agents.domain_agents import (
    CCUSAgent,
    DrillingEngineerAgent,
    GeologistAgent,
    PetrophysicistAgent,
    ProductionEngineerAgent,
    ReservoirEngineerAgent,
)


def register_builtin_agents() -> None:
    agents = (
        GeologistAgent(),
        PetrophysicistAgent(),
        ReservoirEngineerAgent(),
        ProductionEngineerAgent(),
        DrillingEngineerAgent(),
        CCUSAgent(),
    )
    for agent in agents:
        agent_registry.register(agent, replace=True)


class AgentOrchestrator:
    def __init__(self) -> None:
        register_builtin_agents()
        self.consensus_engine = ConsensusEngine()

    async def execute(self, request: AgentRequest) -> AgentPanelResponse:
        keys = request.agent_keys or agent_registry.keys()
        agents = [agent_registry.get(key) for key in keys]

        results = await asyncio.gather(
            *[
                agent.analyse(request.inputs, request.context)
                for agent in agents
            ]
        )
        consensus = self.consensus_engine.build(results)
        return AgentPanelResponse(
            panel_id=uuid.uuid4().hex,
            agents=results,
            consensus=consensus,
            metadata={
                "agent_count": len(results),
                "agent_keys": keys,
                "execution": "deterministic_domain_rules",
            },
        )


agent_orchestrator = AgentOrchestrator()