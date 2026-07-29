from __future__ import annotations

import copy
import threading

from app.digital_twin.schemas import ReservoirState


class TwinRegistryError(RuntimeError):
    pass


class TwinRegistry:
    def __init__(self) -> None:
        self._states: dict[str, ReservoirState] = {}
        self._lock = threading.RLock()

    def create(self, state: ReservoirState) -> ReservoirState:
        with self._lock:
            if state.reservoir_id in self._states:
                raise TwinRegistryError(f"Twin already exists: {state.reservoir_id}")
            self._states[state.reservoir_id] = copy.deepcopy(state)
            return copy.deepcopy(state)

    def upsert(self, state: ReservoirState) -> ReservoirState:
        with self._lock:
            self._states[state.reservoir_id] = copy.deepcopy(state)
            return copy.deepcopy(state)

    def get(self, reservoir_id: str) -> ReservoirState:
        with self._lock:
            try:
                return copy.deepcopy(self._states[reservoir_id])
            except KeyError as exc:
                raise TwinRegistryError(f"Unknown twin: {reservoir_id}") from exc

    def list(self) -> list[ReservoirState]:
        with self._lock:
            return [
                copy.deepcopy(self._states[key])
                for key in sorted(self._states)
            ]

    def delete(self, reservoir_id: str) -> None:
        with self._lock:
            if reservoir_id not in self._states:
                raise TwinRegistryError(f"Unknown twin: {reservoir_id}")
            del self._states[reservoir_id]

    def clear(self) -> None:
        with self._lock:
            self._states.clear()


twin_registry = TwinRegistry()