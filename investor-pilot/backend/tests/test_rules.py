from app.alerts import alert_manager
from app.events import Event
from app.rules import EventRule, RuleAction, RuleCondition, rule_engine


def test_rule_engine_matches_nested_payload() -> None:
    rule_engine.clear()
    alert_manager.clear()
    rule_engine.register(
        EventRule(
            rule_id="water-cut-test",
            name="Water cut test",
            event_type="telemetry.production",
            conditions=[
                RuleCondition(
                    path="payload.water_cut",
                    operator="gt",
                    value=0.70,
                )
            ],
            actions=[
                RuleAction(
                    title="High water cut",
                    message="Water cut exceeded.",
                    severity="warning",
                )
            ],
        )
    )

    matched, alerts = rule_engine.evaluate(
        Event(
            event_id="evt-1",
            event_type="telemetry.production",
            payload={"water_cut": 0.85},
        )
    )

    assert matched == ["water-cut-test"]
    assert len(alerts) == 1