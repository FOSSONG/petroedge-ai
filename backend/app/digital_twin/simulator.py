from __future__ import annotations

import copy
import uuid

from app.digital_twin.health import health_engine
from app.digital_twin.orchestrator import digital_twin_orchestrator
from app.digital_twin.registry import twin_registry
from app.digital_twin.schemas import (
    ReservoirState,
    SimulationRequest,
    SimulationResult,
    TwinUpdate,
)


class SimulationError(RuntimeError):
    pass


def _coerce_path_segment(segment: str) -> str:
    return segment.strip()


class TwinSimulator:
    def simulate(
        self,
        reservoir_id: str,
        request: SimulationRequest,
    ) -> SimulationResult:
        baseline = twin_registry.get(reservoir_id)
        simulated = copy.deepcopy(baseline)

        for change in request.changes:
            self._apply(simulated, change.path, change.operation, change.value)

        simulated = digital_twin_orchestrator._recalculate(simulated)
        baseline_health = health_engine.evaluate(baseline)
        simulated_health = health_engine.evaluate(simulated)

        if request.persist:
            digital_twin_orchestrator.update(
                reservoir_id,
                TwinUpdate(
                    source="simulation",
                    source_reference=request.name,
                    reservoir={
                        key: value
                        for key, value in simulated.model_dump(mode="python").items()
                        if key not in {"reservoir_id", "wells"}
                    },
                    wells=list(simulated.wells.values()),
                    metadata={"simulation": request.name, **request.metadata},
                ),
            )

        return SimulationResult(
            simulation_id=uuid.uuid4().hex,
            reservoir_id=reservoir_id,
            name=request.name,
            baseline_health=baseline_health,
            simulated_health=simulated_health,
            state=simulated,
            persisted=request.persist,
            metadata=request.metadata,
        )

    def _apply(
        self,
        state: ReservoirState,
        path: str,
        operation: str,
        value,
    ) -> None:
        segments = [_coerce_path_segment(item) for item in path.split(".") if item.strip()]
        if not segments:
            raise SimulationError("Simulation path cannot be empty.")

        target = state
        for segment in segments[:-1]:
            if isinstance(target, dict):
                if segment not in target:
                    raise SimulationError(f"Unknown simulation path: {path}")
                target = target[segment]
            else:
                if not hasattr(target, segment):
                    raise SimulationError(f"Unknown simulation path: {path}")
                target = getattr(target, segment)

        leaf = segments[-1]
        current = target.get(leaf) if isinstance(target, dict) else getattr(target, leaf, None)

        if operation == "set":
            updated = value
        elif operation == "increase":
            if not isinstance(current, (int, float)) or not isinstance(value, (int, float)):
                raise SimulationError(f"Increase requires numeric values: {path}")
            updated = current + value
        elif operation == "decrease":
            if not isinstance(current, (int, float)) or not isinstance(value, (int, float)):
                raise SimulationError(f"Decrease requires numeric values: {path}")
            updated = current - value
        elif operation == "multiply":
            if not isinstance(current, (int, float)) or not isinstance(value, (int, float)):
                raise SimulationError(f"Multiply requires numeric values: {path}")
            updated = current * value
        else:
            raise SimulationError(f"Unsupported simulation operation: {operation}")

        if isinstance(target, dict):
            target[leaf] = updated
        elif hasattr(target, leaf):
            setattr(target, leaf, updated)
        else:
            raise SimulationError(f"Unknown simulation path: {path}")


twin_simulator = TwinSimulator()