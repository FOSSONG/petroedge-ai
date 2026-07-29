param(
    [string]$ProjectRoot = (Get-Location).Path
)

$ErrorActionPreference = "Stop"

function Write-Utf8File {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$Content
    )
    $Target = Join-Path $ProjectRoot $RelativePath
    New-Item -ItemType Directory -Force -Path (Split-Path $Target) | Out-Null
    [System.IO.File]::WriteAllText(
        $Target,
        $Content,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Backup-File {
    param([string]$RelativePath, [string]$BackupRoot)
    $Source = Join-Path $ProjectRoot $RelativePath
    if (Test-Path $Source) {
        $Destination = Join-Path $BackupRoot $RelativePath
        New-Item -ItemType Directory -Force -Path (Split-Path $Destination) | Out-Null
        Copy-Item $Source $Destination -Force
    }
}

$BackendRoot = Join-Path $ProjectRoot "backend"
$AppRoot = Join-Path $BackendRoot "app"

if (-not (Test-Path (Join-Path $AppRoot "main.py"))) {
    throw "PetroEdge backend not found. Run this script from the PetroEdge-AI-v1-demo project root."
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $ProjectRoot "backups\digital-twin-$Timestamp"
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

@(
    "backend\app\main.py",
    "backend\app\workflows\nodes\core.py",
    "backend\app\workflows\templates.py",
    "backend\app\api\routes\twins.py"
) | ForEach-Object { Backup-File $_ $BackupRoot }

Write-Utf8File "backend\app\digital_twin\schemas.py" @'
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TwinStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"
    abandoned = "abandoned"


class HealthBand(str, Enum):
    excellent = "excellent"
    good = "good"
    watch = "watch"
    poor = "poor"
    critical = "critical"


class UpdateSource(str, Enum):
    user = "user"
    workflow = "workflow"
    model = "model"
    agent = "agent"
    streaming = "streaming"
    simulation = "simulation"


class WellState(BaseModel):
    model_config = ConfigDict(extra="allow")

    well_id: str
    status: TwinStatus = TwinStatus.active
    formation: str | None = None
    depth: float | None = None
    porosity: float | None = Field(default=None, ge=0.0, le=1.0)
    permeability: float | None = Field(default=None, ge=0.0)
    water_saturation: float | None = Field(default=None, ge=0.0, le=1.0)
    oil_rate: float | None = Field(default=None, ge=0.0)
    gas_rate: float | None = Field(default=None, ge=0.0)
    water_rate: float | None = Field(default=None, ge=0.0)
    pressure: float | None = Field(default=None, ge=0.0)
    temperature: float | None = None
    lithology: str | None = None
    ai_prediction: dict[str, Any] = Field(default_factory=dict)
    agent_consensus: dict[str, Any] = Field(default_factory=dict)
    health_score: float | None = Field(default=None, ge=0.0, le=100.0)
    risk_score: float | None = Field(default=None, ge=0.0, le=100.0)
    last_updated: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReservoirState(BaseModel):
    model_config = ConfigDict(extra="allow")

    reservoir_id: str
    name: str
    field: str | None = None
    status: TwinStatus = TwinStatus.active
    wells: dict[str, WellState] = Field(default_factory=dict)
    ooip: float | None = Field(default=None, ge=0.0)
    recovery_factor: float | None = Field(default=None, ge=0.0, le=1.0)
    average_pressure: float | None = Field(default=None, ge=0.0)
    average_porosity: float | None = Field(default=None, ge=0.0, le=1.0)
    average_water_saturation: float | None = Field(default=None, ge=0.0, le=1.0)
    average_permeability: float | None = Field(default=None, ge=0.0)
    active_wells: int = Field(default=0, ge=0)
    inactive_wells: int = Field(default=0, ge=0)
    health_score: float | None = Field(default=None, ge=0.0, le=100.0)
    risk_score: float | None = Field(default=None, ge=0.0, le=100.0)
    ccus_suitability: float | None = Field(default=None, ge=0.0, le=100.0)
    forecast: dict[str, Any] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TwinCreate(BaseModel):
    reservoir_id: str
    name: str
    field: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TwinUpdate(BaseModel):
    source: UpdateSource = UpdateSource.user
    source_reference: str | None = None
    reservoir: dict[str, Any] = Field(default_factory=dict)
    wells: list[WellState] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TwinSnapshot(BaseModel):
    snapshot_id: str
    reservoir_id: str
    version: int
    source: UpdateSource
    source_reference: str | None = None
    state: ReservoirState
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthMetric(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=100.0)
    weight: float = Field(ge=0.0)
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class HealthReport(BaseModel):
    reservoir_id: str
    overall_score: float = Field(ge=0.0, le=100.0)
    risk_score: float = Field(ge=0.0, le=100.0)
    band: HealthBand
    metrics: list[HealthMetric] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class SimulationChange(BaseModel):
    path: str
    operation: str = "set"
    value: float | int | str | bool | None


class SimulationRequest(BaseModel):
    name: str = "What-if scenario"
    changes: list[SimulationChange]
    persist: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationResult(BaseModel):
    simulation_id: str
    reservoir_id: str
    name: str
    baseline_health: HealthReport
    simulated_health: HealthReport
    state: ReservoirState
    persisted: bool
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)
'@

Write-Utf8File "backend\app\digital_twin\health.py" @'
from __future__ import annotations

from statistics import mean

from app.digital_twin.schemas import (
    HealthBand,
    HealthMetric,
    HealthReport,
    ReservoirState,
    TwinStatus,
)


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


class HealthEngine:
    def evaluate(self, state: ReservoirState) -> HealthReport:
        metrics: list[HealthMetric] = []
        recommendations: list[str] = []

        pressure_values = [
            well.pressure
            for well in state.wells.values()
            if well.pressure is not None
        ]
        water_cuts = []
        for well in state.wells.values():
            total_liquid = (well.oil_rate or 0.0) + (well.water_rate or 0.0)
            if total_liquid > 0:
                water_cuts.append((well.water_rate or 0.0) / total_liquid)

        pressure_score = 75.0
        if pressure_values:
            spread = max(pressure_values) - min(pressure_values)
            reference = max(mean(pressure_values), 1.0)
            pressure_score = _clamp(100.0 - (spread / reference) * 200.0)
        else:
            recommendations.append("Provide pressure data for depletion and connectivity monitoring.")

        metrics.append(
            HealthMetric(
                name="pressure_stability",
                score=pressure_score,
                weight=0.30,
                message="Pressure stability across available wells.",
                evidence={"well_count": len(pressure_values)},
            )
        )

        water_score = 80.0
        if water_cuts:
            average_water_cut = mean(water_cuts)
            water_score = _clamp(100.0 - average_water_cut * 100.0)
            if average_water_cut >= 0.60:
                recommendations.append("Investigate water breakthrough and coning risk.")
        else:
            recommendations.append("Provide oil and water rates for water-cut monitoring.")

        metrics.append(
            HealthMetric(
                name="water_management",
                score=water_score,
                weight=0.25,
                message="Water-cut and breakthrough screening.",
                evidence={"average_water_cut": mean(water_cuts) if water_cuts else None},
            )
        )

        active = sum(
            well.status == TwinStatus.active
            for well in state.wells.values()
        )
        total = len(state.wells)
        availability_score = 100.0 if total == 0 else _clamp((active / total) * 100.0)
        if total and active < total:
            recommendations.append("Review inactive or suspended wells and associated production loss.")

        metrics.append(
            HealthMetric(
                name="well_availability",
                score=availability_score,
                weight=0.20,
                message="Share of wells currently active.",
                evidence={"active_wells": active, "total_wells": total},
            )
        )

        porosity_values = [
            well.porosity
            for well in state.wells.values()
            if well.porosity is not None
        ]
        saturation_values = [
            well.water_saturation
            for well in state.wells.values()
            if well.water_saturation is not None
        ]

        reservoir_quality_score = 65.0
        if porosity_values or saturation_values:
            phi_component = (
                _clamp(mean(porosity_values) / 0.25 * 100.0)
                if porosity_values
                else 60.0
            )
            sw_component = (
                _clamp((1.0 - mean(saturation_values)) * 100.0)
                if saturation_values
                else 60.0
            )
            reservoir_quality_score = 0.55 * phi_component + 0.45 * sw_component
        else:
            recommendations.append("Provide porosity and saturation data for reservoir-quality scoring.")

        metrics.append(
            HealthMetric(
                name="reservoir_quality",
                score=_clamp(reservoir_quality_score),
                weight=0.25,
                message="Reservoir quality from porosity and water saturation.",
                evidence={
                    "average_porosity": mean(porosity_values) if porosity_values else None,
                    "average_water_saturation": (
                        mean(saturation_values) if saturation_values else None
                    ),
                },
            )
        )

        weighted_sum = sum(metric.score * metric.weight for metric in metrics)
        total_weight = sum(metric.weight for metric in metrics)
        overall = _clamp(weighted_sum / total_weight if total_weight else 0.0)
        risk = _clamp(100.0 - overall)

        if overall >= 85:
            band = HealthBand.excellent
        elif overall >= 70:
            band = HealthBand.good
        elif overall >= 55:
            band = HealthBand.watch
        elif overall >= 35:
            band = HealthBand.poor
        else:
            band = HealthBand.critical

        return HealthReport(
            reservoir_id=state.reservoir_id,
            overall_score=round(overall, 3),
            risk_score=round(risk, 3),
            band=band,
            metrics=metrics,
            recommendations=sorted(set(recommendations)),
        )


health_engine = HealthEngine()
'@

Write-Utf8File "backend\app\digital_twin\registry.py" @'
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
'@

Write-Utf8File "backend\app\digital_twin\history.py" @'
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
'@

Write-Utf8File "backend\app\digital_twin\orchestrator.py" @'
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
'@

Write-Utf8File "backend\app\digital_twin\simulator.py" @'
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
'@

Write-Utf8File "backend\app\digital_twin\__init__.py" @'
from app.digital_twin.health import HealthEngine, health_engine
from app.digital_twin.history import TwinHistory, twin_history
from app.digital_twin.orchestrator import (
    DigitalTwinOrchestrator,
    digital_twin_orchestrator,
)
from app.digital_twin.registry import (
    TwinRegistry,
    TwinRegistryError,
    twin_registry,
)
from app.digital_twin.schemas import (
    HealthReport,
    ReservoirState,
    SimulationRequest,
    SimulationResult,
    TwinCreate,
    TwinSnapshot,
    TwinUpdate,
    WellState,
)
from app.digital_twin.simulator import SimulationError, TwinSimulator, twin_simulator

__all__ = [
    "DigitalTwinOrchestrator",
    "HealthEngine",
    "HealthReport",
    "ReservoirState",
    "SimulationError",
    "SimulationRequest",
    "SimulationResult",
    "TwinCreate",
    "TwinHistory",
    "TwinRegistry",
    "TwinRegistryError",
    "TwinSimulator",
    "TwinSnapshot",
    "TwinUpdate",
    "WellState",
    "digital_twin_orchestrator",
    "health_engine",
    "twin_history",
    "twin_registry",
    "twin_simulator",
]
'@

Write-Utf8File "backend\app\api\routes\twins.py" @'
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.rbac import require_roles
from app.digital_twin import (
    SimulationError,
    SimulationRequest,
    TwinCreate,
    TwinRegistryError,
    TwinUpdate,
    digital_twin_orchestrator,
    health_engine,
    twin_history,
    twin_registry,
    twin_simulator,
)

router = APIRouter()

READ_ROLES = ("admin", "geoscientist", "engineer", "viewer")
WRITE_ROLES = ("admin", "geoscientist", "engineer")


@router.get("")
async def list_twins(
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    twins = twin_registry.list()
    return {
        "count": len(twins),
        "twins": [item.model_dump(mode="json") for item in twins],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_twin(
    request: TwinCreate,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    try:
        twin = digital_twin_orchestrator.create(request)
    except TwinRegistryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return twin.model_dump(mode="json")


@router.get("/{reservoir_id}")
async def get_twin(
    reservoir_id: str,
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    try:
        twin = twin_registry.get(reservoir_id)
    except TwinRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return twin.model_dump(mode="json")


@router.patch("/{reservoir_id}")
async def update_twin(
    reservoir_id: str,
    request: TwinUpdate,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    try:
        twin = digital_twin_orchestrator.update(reservoir_id, request)
    except TwinRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return twin.model_dump(mode="json")


@router.delete("/{reservoir_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_twin(
    reservoir_id: str,
    _: dict[str, Any] = Depends(require_roles("admin")),
) -> Response:
    try:
        twin_registry.delete(reservoir_id)
    except TwinRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{reservoir_id}/health")
async def get_health(
    reservoir_id: str,
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    try:
        report = health_engine.evaluate(twin_registry.get(reservoir_id))
    except TwinRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return report.model_dump(mode="json")


@router.get("/{reservoir_id}/history")
async def get_history(
    reservoir_id: str,
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    try:
        twin_registry.get(reservoir_id)
    except TwinRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    history = twin_history.list(reservoir_id)
    return {
        "reservoir_id": reservoir_id,
        "count": len(history),
        "snapshots": [item.model_dump(mode="json") for item in history],
    }


@router.post("/{reservoir_id}/restore/{version}")
async def restore_version(
    reservoir_id: str,
    version: int,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    try:
        twin = digital_twin_orchestrator.restore(reservoir_id, version)
    except (TwinRegistryError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return twin.model_dump(mode="json")


@router.post("/{reservoir_id}/simulate")
async def simulate(
    reservoir_id: str,
    request: SimulationRequest,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    try:
        result = twin_simulator.simulate(reservoir_id, request)
    except TwinRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SimulationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.model_dump(mode="json")
'@

# Patch core.py with import, node function, and handler using exact replacements.
$CorePath = Join-Path $ProjectRoot "backend\app\workflows\nodes\core.py"
$CoreContent = Get-Content $CorePath -Raw

if ($CoreContent -notmatch "from app\.digital_twin import digital_twin_orchestrator") {
    $Anchor = "from app.agents import AgentRequest, agent_orchestrator"
    if ($CoreContent.Contains($Anchor)) {
        $CoreContent = $CoreContent.Replace(
            $Anchor,
            $Anchor + [Environment]::NewLine + "from app.digital_twin import digital_twin_orchestrator"
        )
    } else {
        throw "Could not find the agents import anchor in core.py."
    }
}

if ($CoreContent -notmatch "async def digital_twin_update") {
    $Function = @'

async def digital_twin_update(node: NodeSpec, context: WorkflowContext) -> dict[str, Any]:
    dependencies = context.dependency_payload(node.depends_on)
    rows: list[dict[str, Any]] = []

    for dependency in dependencies.values():
        candidate = dependency.get("rows")
        if isinstance(candidate, list) and all(isinstance(item, dict) for item in candidate):
            rows = candidate
            break

    reservoir_id = str(
        node.parameters.get("reservoir_id")
        or context.inputs.get("reservoir_id")
        or "PETROEDGE-DEMO"
    )

    state = digital_twin_orchestrator.ingest_rows(
        reservoir_id=reservoir_id,
        rows=rows,
        source_reference=f"{context.workflow_id}:{context.run_id}",
    )
    return {
        "reservoir_id": reservoir_id,
        "state": state.model_dump(mode="json"),
        "row_count": len(rows),
        "status": "updated",
    }

'@
    $Anchor = "async def report_summary"
    if ($CoreContent.Contains($Anchor)) {
        $CoreContent = $CoreContent.Replace($Anchor, $Function + $Anchor)
    } else {
        throw "Could not find report_summary in core.py."
    }
}

if ($CoreContent -notmatch '"digital_twin\.update": digital_twin_update') {
    $Anchor = '        "agents.panel": multi_agent_analysis,'
    if ($CoreContent.Contains($Anchor)) {
        $CoreContent = $CoreContent.Replace(
            $Anchor,
            $Anchor + [Environment]::NewLine + '        "digital_twin.update": digital_twin_update,'
        )
    } else {
        throw "Could not find agents.panel handler in core.py."
    }
}

[System.IO.File]::WriteAllText(
    $CorePath,
    $CoreContent,
    [System.Text.UTF8Encoding]::new($false)
)

# Register API route.
$MainPath = Join-Path $ProjectRoot "backend\app\main.py"
$MainContent = Get-Content $MainPath -Raw

if ($MainContent -notmatch '\("twins",\s*"/twins"') {
    $Anchor = '    ("agents", "/agents", ("Multi-Agent AI",), True),'
    if ($MainContent.Contains($Anchor)) {
        $MainContent = $MainContent.Replace(
            $Anchor,
            $Anchor + [Environment]::NewLine + '    ("twins", "/twins", ("Reservoir Digital Twin",), True),'
        )
    } else {
        throw "Could not find agents route registration in main.py."
    }
}

[System.IO.File]::WriteAllText(
    $MainPath,
    $MainContent,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Utf8File "backend\tests\test_digital_twin.py" @'
import pytest

from app.digital_twin import (
    SimulationRequest,
    TwinCreate,
    TwinUpdate,
    WellState,
    digital_twin_orchestrator,
    twin_history,
    twin_registry,
    twin_simulator,
)


@pytest.fixture(autouse=True)
def reset_state() -> None:
    twin_registry.clear()
    twin_history.clear()


def test_create_and_update_twin() -> None:
    created = digital_twin_orchestrator.create(
        TwinCreate(reservoir_id="GABO", name="Gabo Reservoir")
    )
    assert created.reservoir_id == "GABO"

    updated = digital_twin_orchestrator.update(
        "GABO",
        TwinUpdate(
            wells=[
                WellState(
                    well_id="GABO-18",
                    porosity=0.22,
                    water_saturation=0.32,
                    pressure=4000.0,
                    oil_rate=1000.0,
                    water_rate=100.0,
                )
            ]
        ),
    )

    assert updated.active_wells == 1
    assert updated.average_porosity == pytest.approx(0.22)
    assert updated.health_score is not None
    assert len(twin_history.list("GABO")) == 2


def test_simulation_does_not_persist_by_default() -> None:
    digital_twin_orchestrator.create(
        TwinCreate(reservoir_id="GABO", name="Gabo Reservoir")
    )
    digital_twin_orchestrator.update(
        "GABO",
        TwinUpdate(
            wells=[
                WellState(
                    well_id="GABO-18",
                    oil_rate=1000.0,
                    water_rate=100.0,
                    pressure=4000.0,
                )
            ]
        ),
    )

    result = twin_simulator.simulate(
        "GABO",
        SimulationRequest(
            changes=[
                {
                    "path": "wells.GABO-18.water_rate",
                    "operation": "increase",
                    "value": 2000.0,
                }
            ]
        ),
    )

    assert result.persisted is False
    assert result.state.wells["GABO-18"].water_rate == pytest.approx(2100.0)
    assert twin_registry.get("GABO").wells["GABO-18"].water_rate == pytest.approx(100.0)


def test_ingest_rows_creates_well_state() -> None:
    state = digital_twin_orchestrator.ingest_rows(
        "GABO",
        [
            {
                "Well_ID": "GABO-18",
                "PHI_D": 0.20,
                "SW_ARCHIE": 0.35,
                "PRESSURE": 3900.0,
            },
            {
                "Well_ID": "GABO-18",
                "PHI_D": 0.24,
                "SW_ARCHIE": 0.25,
                "PRESSURE": 4100.0,
            },
        ],
        source_reference="test",
    )

    assert state.wells["GABO-18"].porosity == pytest.approx(0.22)
    assert state.wells["GABO-18"].pressure == pytest.approx(4000.0)
'@

Write-Utf8File "backend\tests\test_twins_api.py" @'
from fastapi.testclient import TestClient

from app.main import app


def test_twin_routes_are_present_in_openapi() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]

    assert "/api/v1/twins" in paths
    assert "/api/v1/twins/{reservoir_id}" in paths
    assert "/api/v1/twins/{reservoir_id}/health" in paths
    assert "/api/v1/twins/{reservoir_id}/history" in paths
    assert "/api/v1/twins/{reservoir_id}/simulate" in paths
'@

Write-Utf8File "backend\tests\test_digital_twin_workflow.py" @'
import pytest

from app.digital_twin import twin_history, twin_registry
from app.workflows.engine import WorkflowEngine
from app.workflows.schemas import NodeSpec, RunStatus, WorkflowDefinition, WorkflowRunRequest


@pytest.fixture(autouse=True)
def reset_state() -> None:
    twin_registry.clear()
    twin_history.clear()


@pytest.mark.asyncio
async def test_digital_twin_workflow_node() -> None:
    engine = WorkflowEngine()
    definition = WorkflowDefinition(
        id="digital_twin_test",
        name="Digital Twin Test",
        description="Test workflow",
        tags=["test"],
        nodes=[
            NodeSpec(id="input", type="input.payload", parameters={"key": "rows"}),
            NodeSpec(id="twin", type="digital_twin.update", depends_on=["input"]),
        ],
    )
    engine.register(definition, replace=True)

    run = await engine.run(
        "digital_twin_test",
        WorkflowRunRequest(
            inputs={
                "reservoir_id": "GABO",
                "rows": [
                    {
                        "Well_ID": "GABO-18",
                        "PHI_D": 0.24,
                        "SW_ARCHIE": 0.30,
                        "PRESSURE": 4000.0,
                    }
                ],
            }
        ),
    )

    assert run.status == RunStatus.succeeded
    assert run.outputs["twin"]["reservoir_id"] == "GABO"
    assert twin_registry.get("GABO").wells["GABO-18"].porosity == pytest.approx(0.24)
'@

Write-Utf8File "docs\reservoir-digital-twin.md" @'
# PetroEdge Reservoir Digital Twin

## Scope

The Digital Twin maintains an auditable in-memory reservoir and well state that can be updated by users, workflows, models, agents and future streaming integrations.

## Core capabilities

- Reservoir and well state management
- Health and risk scoring
- Versioned snapshots
- Historical restore
- What-if simulations
- Workflow ingestion through `digital_twin.update`
- REST API under `/api/v1/twins`

## API endpoints

- `GET /api/v1/twins`
- `POST /api/v1/twins`
- `GET /api/v1/twins/{reservoir_id}`
- `PATCH /api/v1/twins/{reservoir_id}`
- `DELETE /api/v1/twins/{reservoir_id}`
- `GET /api/v1/twins/{reservoir_id}/health`
- `GET /api/v1/twins/{reservoir_id}/history`
- `POST /api/v1/twins/{reservoir_id}/restore/{version}`
- `POST /api/v1/twins/{reservoir_id}/simulate`

## Persistence boundary

This sprint uses an in-memory registry and history store to validate the domain model and API contract. Production persistence should be implemented with the existing database layer in the next hardening sprint.
'@

Write-Host ""
Write-Host "Running syntax validation..." -ForegroundColor Yellow

$PythonFiles = @(
    "backend\app\digital_twin\schemas.py",
    "backend\app\digital_twin\health.py",
    "backend\app\digital_twin\registry.py",
    "backend\app\digital_twin\history.py",
    "backend\app\digital_twin\orchestrator.py",
    "backend\app\digital_twin\simulator.py",
    "backend\app\digital_twin\__init__.py",
    "backend\app\api\routes\twins.py",
    "backend\app\workflows\nodes\core.py"
)

foreach ($File in $PythonFiles) {
    python -m py_compile $File
    if ($LASTEXITCODE -ne 0) {
        throw "Syntax validation failed: $File"
    }
}

Write-Host "Syntax validation passed." -ForegroundColor Green
Write-Host ""
Write-Host "Digital Twin implementation installed." -ForegroundColor Green
Write-Host "Backup: $BackupRoot" -ForegroundColor Cyan
Write-Host ""
Write-Host "Run:" -ForegroundColor Yellow
Write-Host "  python -m pytest .\backend\tests\test_digital_twin.py -q"
Write-Host "  python -m pytest .\backend\tests\test_twins_api.py -q"
Write-Host "  python -m pytest .\backend\tests\test_digital_twin_workflow.py -q"
Write-Host "  python -m pytest .\backend\tests\test_agents.py -q"
Write-Host "  python -m pytest .\backend\tests\test_agents_api.py -q"
Write-Host "  python -m pytest .\backend\tests\test_agents_workflow.py -q"
Write-Host "  python -m pytest .\backend\tests\test_workflow_engine.py -q"
Write-Host "  python -m pytest .\backend\tests\test_workflows_api.py -q"
Write-Host ""
Write-Host "Then start:" -ForegroundColor Yellow
Write-Host "  python -m uvicorn app.main:app --reload --app-dir backend"
