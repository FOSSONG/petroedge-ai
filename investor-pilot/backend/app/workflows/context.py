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