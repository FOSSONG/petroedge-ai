from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any

from app.digital_twin.health import health_engine
from app.digital_twin.history import twin_history
from app.digital_twin.registry import TwinRegistryError, twin_registry
from app.digital_twin.schemas import (
    ReservoirState,
    TwinCreate,
    TwinSnapshot,
    TwinStatus,
    TwinUpdate,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DigitalTwinOrchestrator:
    def create(self, request: TwinCreate) -> ReservoirState:
        state = ReservoirState(
            reservoir_id=request.reservoir_id,
            name=request.name,
            field=request.field,
            metadata=request.metadata,
        )
        state = self._recalculate(state)
        twin_registry.create(state)
        twin_history.append(state, source="user")
        return state

    def update(self, reservoir_id: str, request: TwinUpdate) -> ReservoirState:
        state = twin_registry.get(reservoir_id)
        payload = state.model_dump(mode="python")

        for key, value in request.reservoir.items():
            if key in {"reservoir_id", "wells"}:
                continue
            payload[key] = value

        state = ReservoirState.model_validate(payload)
        for well in request.wells:
            state.wells[well.well_id] = well

        state.metadata.update(request.metadata)
        state.last_updated = _utc_now()
        state = self._recalculate(state)
        twin_registry.upsert(state)
        twin_history.append(
            state,
            source=request.source,
            source_reference=request.source_reference,
            metadata=request.metadata,
        )
        return state

    def restore(self, reservoir_id: str, version: int) -> ReservoirState:
        snapshot = twin_history.get_version(reservoir_id, version)
        state = self._recalculate(snapshot.state)
        twin_registry.upsert(state)
        twin_history.append(
            state,
            source="user",
            source_reference=f"restore:{version}",
        )
        return state

    def _recalculate(self, state: ReservoirState) -> ReservoirState:
        wells = list(state.wells.values())

        pressure = [well.pressure for well in wells if well.pressure is not None]
        porosity = [well.porosity for well in wells if well.porosity is not None]
        saturation = [
            well.water_saturation
            for well in wells
            if well.water_saturation is not None
        ]
        permeability = [
            well.permeability
            for well in wells
            if well.permeability is not None
        ]

        state.average_pressure = mean(pressure) if pressure else state.average_pressure
        state.average_porosity = mean(porosity) if porosity else state.average_porosity
        state.average_water_saturation = (
            mean(saturation) if saturation else state.average_water_saturation
        )
        state.average_permeability = (
            mean(permeability) if permeability else state.average_permeability
        )
        state.active_wells = sum(well.status == TwinStatus.active for well in wells)
        state.inactive_wells = len(wells) - state.active_wells

        report = health_engine.evaluate(state)
        state.health_score = report.overall_score
        state.risk_score = report.risk_score
        state.last_updated = _utc_now()
        return state

    def ingest_rows(
        self,
        reservoir_id: str,
        rows: list[dict[str, Any]],
        source_reference: str | None = None,
    ) -> ReservoirState:
        try:
            state = twin_registry.get(reservoir_id)
        except TwinRegistryError:
            state = self.create(
                TwinCreate(
                    reservoir_id=reservoir_id,
                    name=reservoir_id,
                )
            )

        well_map: dict[str, dict[str, list[float]]] = {}
        for row in rows:
            well_id = str(
                row.get("Well_ID")
                or row.get("Well_id")
                or row.get("well_id")
                or "UNKNOWN"
            )
            metrics = well_map.setdefault(well_id, {})
            aliases = {
                "porosity": ("PHI_D", "PHI", "POROSITY"),
                "water_saturation": ("SW_ARCHIE", "SW", "WATER_SATURATION"),
                "permeability": ("PERM", "PERMEABILITY", "k"),
                "pressure": ("PRESSURE", "Pressure", "pressure"),
                "oil_rate": ("Qoil STB/d", "oil_rate", "QOIL"),
                "gas_rate": ("Qgas MMScf/d", "gas_rate", "QGAS"),
                "water_rate": ("Qwat STB/d", "water_rate", "QWAT"),
                "depth": ("DEPTH", "Depth", "depth"),
            }
            for target, columns in aliases.items():
                for column in columns:
                    value = row.get(column)
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        metrics.setdefault(target, []).append(float(value))
                        break

        wells = []
        for well_id, metrics in well_map.items():
            existing = state.wells.get(well_id)
            base = existing.model_dump(mode="python") if existing else {"well_id": well_id}
            for key, values in metrics.items():
                if values:
                    base[key] = mean(values)
            from app.digital_twin.schemas import WellState
            wells.append(WellState.model_validate(base))

        return self.update(
            reservoir_id,
            TwinUpdate(
                source="workflow",
                source_reference=source_reference,
                wells=wells,
            ),
        )


digital_twin_orchestrator = DigitalTwinOrchestrator()