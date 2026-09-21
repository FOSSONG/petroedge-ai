import pytest

from app.alerts import alert_manager
from app.digital_twin import twin_history, twin_registry
from app.events import EventCreate, event_bus
from app.rules import register_default_rules, rule_engine
from app.streaming import ReplayRequest, TelemetryBatch, streaming_service


@pytest.fixture(autouse=True)
def reset_state() -> None:
    event_bus.clear()
    alert_manager.clear()
    rule_engine.clear()
    twin_registry.clear()
    twin_history.clear()
    register_default_rules()


@pytest.mark.asyncio
async def test_event_creates_alert() -> None:
    delivery = await streaming_service.ingest(
        EventCreate(
            event_type="telemetry.pressure",
            reservoir_id="GABO",
            well_id="GABO-18",
            payload={"value": 2400.0},
        )
    )

    assert delivery.matched_rules == ["pressure-low"]
    assert len(delivery.alert_ids) == 1
    assert len(alert_manager.list()) == 1
    assert len(event_bus.history()) == 1


@pytest.mark.asyncio
async def test_telemetry_updates_digital_twin() -> None:
    delivery = await streaming_service.ingest_telemetry(
        TelemetryBatch(
            reservoir_id="GABO",
            well_id="GABO-18",
            rows=[
                {
                    "PHI_D": 0.24,
                    "SW_ARCHIE": 0.30,
                    "PRESSURE": 4000.0,
                }
            ],
        )
    )

    assert delivery.twin_updated is True
    state = twin_registry.get("GABO")
    assert state.wells["GABO-18"].porosity == pytest.approx(0.24)
    assert state.wells["GABO-18"].pressure == pytest.approx(4000.0)


@pytest.mark.asyncio
async def test_replay_processes_all_events() -> None:
    result = await streaming_service.replay(
        ReplayRequest(
            speed=100.0,
            interval_seconds=0.0,
            events=[
                EventCreate(event_type="test.one", payload={"value": 1}),
                EventCreate(event_type="test.two", payload={"value": 2}),
            ],
        )
    )

    assert len(result) == 2
    assert len(event_bus.history()) == 2