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