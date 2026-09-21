from __future__ import annotations

import copy
import threading
import uuid
from app.digital_twin.persistence import load,save

from app.digital_twin.schemas import ReservoirState, TwinSnapshot, UpdateSource
from app.core.ownership import require_owner, visible


class TwinHistory:
    def __init__(self) -> None:
        self._snapshots: dict[str, list[TwinSnapshot]] = {k:[TwinSnapshot.model_validate(x) for x in v] for k,v in load("history").items()}
        self._lock = threading.RLock()

    def append(
        self,
        state: ReservoirState,
        source: UpdateSource,
        source_reference: str | None = None,
        metadata: dict | None = None,
    ) -> TwinSnapshot:
        with self._lock:
            require_owner(state.owner_id)
            history = self._snapshots.setdefault(state.reservoir_id, [])
            snapshot = TwinSnapshot(
                snapshot_id=uuid.uuid4().hex,
                reservoir_id=state.reservoir_id,
                version=len(history) + 1,
                source=source,
                source_reference=source_reference,
                state=copy.deepcopy(state),
                metadata=metadata or {},
            )
            save("history",{**{k:[x.model_dump(mode="json") for x in v] for k,v in self._snapshots.items()},state.reservoir_id:[x.model_dump(mode="json") for x in [*history,snapshot]]})
            history.append(snapshot)
            return copy.deepcopy(snapshot)

    def list(self, reservoir_id: str) -> list[TwinSnapshot]:
        with self._lock:
            return copy.deepcopy([s for s in self._snapshots.get(reservoir_id, []) if visible(s.state.owner_id)])

    def get_version(self, reservoir_id: str, version: int) -> TwinSnapshot:
        with self._lock:
            for snapshot in self._snapshots.get(reservoir_id, []):
                if snapshot.version == version:
                    require_owner(snapshot.state.owner_id)
                    return copy.deepcopy(snapshot)
        raise KeyError(f"Snapshot version not found: {reservoir_id}@{version}")

    def clear(self) -> None:
        with self._lock:
            save("history",{})
            self._snapshots.clear()


twin_history = TwinHistory()