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