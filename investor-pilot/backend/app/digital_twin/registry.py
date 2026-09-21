from __future__ import annotations

import copy
import threading
from app.digital_twin.persistence import load,save

from app.digital_twin.schemas import ReservoirState
from app.core.ownership import owner_id, require_owner, visible


class TwinRegistryError(RuntimeError):
    pass


class TwinRegistry:
    def __init__(self) -> None:
        self._states: dict[str, ReservoirState] = {k:ReservoirState.model_validate(v) for k,v in load("registry").items()}
        self._lock = threading.RLock()

    def create(self, state: ReservoirState) -> ReservoirState:
        with self._lock:
            if state.reservoir_id in self._states:
                raise TwinRegistryError(f"Twin already exists: {state.reservoir_id}")
            state = copy.deepcopy(state)
            existing = self._states.get(state.reservoir_id)
            if existing is not None:
                require_owner(existing.owner_id)
                state.owner_id = existing.owner_id
            else:
                state.owner_id = owner_id()
            save("registry",{**{k:v.model_dump(mode="json") for k,v in self._states.items()},state.reservoir_id:state.model_dump(mode="json")})
            self._states[state.reservoir_id] = copy.deepcopy(state)
            return copy.deepcopy(state)

    def upsert(self, state: ReservoirState) -> ReservoirState:
        with self._lock:
            state = copy.deepcopy(state)
            existing = self._states.get(state.reservoir_id)
            if existing is not None:
                require_owner(existing.owner_id)
                state.owner_id = existing.owner_id
            else:
                state.owner_id = owner_id()
            save("registry",{**{k:v.model_dump(mode="json") for k,v in self._states.items()},state.reservoir_id:state.model_dump(mode="json")})
            self._states[state.reservoir_id] = copy.deepcopy(state)
            return copy.deepcopy(state)

    def get(self, reservoir_id: str) -> ReservoirState:
        with self._lock:
            try:
                require_owner(self._states[reservoir_id].owner_id)
                return copy.deepcopy(self._states[reservoir_id])
            except KeyError as exc:
                raise TwinRegistryError(f"Unknown twin: {reservoir_id}") from exc

    def list(self) -> list[ReservoirState]:
        with self._lock:
            return [
                copy.deepcopy(self._states[key])
                for key in sorted(self._states)
                if visible(self._states[key].owner_id)
            ]

    def delete(self, reservoir_id: str) -> None:
        with self._lock:
            if reservoir_id not in self._states:
                raise TwinRegistryError(f"Unknown twin: {reservoir_id}")
            require_owner(self._states[reservoir_id].owner_id)
            save("registry",{k:v.model_dump(mode="json") for k,v in self._states.items() if k!=reservoir_id})
            del self._states[reservoir_id]

    def clear(self) -> None:
        with self._lock:
            save("registry",{})
            self._states.clear()


twin_registry = TwinRegistry()