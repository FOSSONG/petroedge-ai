from __future__ import annotations

import copy
import threading
import uuid

from app.digital_twin.schemas import ReservoirState, TwinSnapshot, UpdateSource


class TwinHistory:
    def __init__(self) -> None:
        self._snapshots: dict[str, list[TwinSnapshot]] = {}
        self._lock = threading.RLock()

    def append(
        self,
        state: ReservoirState,
        source: UpdateSource,
        source_reference: str | None = None,
        metadata: dict | None = None,
    ) -> TwinSnapshot:
        with self._lock:
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
            history.append(snapshot)
            return copy.deepcopy(snapshot)

    def list(self, reservoir_id: str) -> list[TwinSnapshot]:
        with self._lock:
            return copy.deepcopy(self._snapshots.get(reservoir_id, []))

    def get_version(self, reservoir_id: str, version: int) -> TwinSnapshot:
        with self._lock:
            for snapshot in self._snapshots.get(reservoir_id, []):
                if snapshot.version == version:
                    return copy.deepcopy(snapshot)
        raise KeyError(f"Snapshot version not found: {reservoir_id}@{version}")

    def clear(self) -> None:
        with self._lock:
            self._snapshots.clear()


twin_history = TwinHistory()