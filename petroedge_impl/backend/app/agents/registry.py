from __future__ import annotations

import threading

from app.agents.base import BaseAgent


class AgentRegistryError(RuntimeError):
    pass


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._lock = threading.RLock()

    def register(self, agent: BaseAgent, *, replace: bool = False) -> None:
        with self._lock:
            if agent.key in self._agents and not replace:
                raise AgentRegistryError(f"Agent already registered: {agent.key}")
            self._agents[agent.key] = agent

    def get(self, key: str) -> BaseAgent:
        try:
            return self._agents[key]
        except KeyError as exc:
            raise AgentRegistryError(f"Unknown agent: {key}") from exc

    def list(self) -> list[BaseAgent]:
        return sorted(self._agents.values(), key=lambda item: item.name.lower())

    def keys(self) -> list[str]:
        return sorted(self._agents)


agent_registry = AgentRegistry()