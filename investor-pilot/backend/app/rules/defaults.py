from app.rules.engine import rule_engine
from app.rules.schemas import EventRule, RuleAction, RuleCondition


DEFAULT_RULES = [
    EventRule(
        rule_id="pressure-low",
        name="Low reservoir pressure",
        event_type="telemetry.pressure",
        conditions=[
            RuleCondition(path="payload.value", operator="lt", value=2500.0),
        ],
        actions=[
            RuleAction(
                title="Low reservoir pressure",
                message="Reservoir pressure is below the configured operational threshold.",
                severity="critical",
                recommended_action="Validate the pressure measurement and review drawdown strategy.",
            )
        ],
    ),
    EventRule(
        rule_id="water-cut-high",
        name="High water cut",
        event_type="telemetry.production",
        conditions=[
            RuleCondition(path="payload.water_cut", operator="gt", value=0.70),
        ],
        actions=[
            RuleAction(
                title="High water cut",
                message="Water cut exceeds 70 percent.",
                severity="warning",
                recommended_action="Investigate water breakthrough, coning and completion integrity.",
            )
        ],
    ),
]


def register_default_rules() -> None:
    for rule in DEFAULT_RULES:
        rule_engine.register(rule, replace=True)