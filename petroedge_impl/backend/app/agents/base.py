from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.agents.schemas import AgentDomain, AgentResult


class BaseAgent(ABC):
    key: str
    name: str
    domain: AgentDomain

    @abstractmethod
    async def analyse(
        self,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        raise NotImplementedError

    @staticmethod
    def rows_from_inputs(inputs: dict[str, Any]) -> list[dict[str, Any]]:
        rows = inputs.get("rows")
        if isinstance(rows, list) and all(isinstance(item, dict) for item in rows):
            return rows
        return []

    @staticmethod
    def numeric_values(rows: list[dict[str, Any]], column: str) -> list[float]:
        values: list[float] = []
        for row in rows:
            value = row.get(column)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(float(value))
        return values