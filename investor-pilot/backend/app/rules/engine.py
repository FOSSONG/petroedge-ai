from __future__ import annotations

import copy
import threading
from typing import Any

from app.alerts import alert_manager
from app.events.schemas import Event
from app.rules.schemas import EventRule, RuleCondition, RuleOperator


class RuleEngine:
    def __init__(self) -> None:
        self._rules: dict[str, EventRule] = {}
        self._lock = threading.RLock()

    def register(self, rule: EventRule, *, replace: bool = False) -> EventRule:
        with self._lock:
            if rule.rule_id in self._rules and not replace:
                raise ValueError(f"Rule already exists: {rule.rule_id}")
            self._rules[rule.rule_id] = copy.deepcopy(rule)
        return copy.deepcopy(rule)

    def get(self, rule_id: str) -> EventRule:
        with self._lock:
            if rule_id not in self._rules:
                raise KeyError(rule_id)
            return copy.deepcopy(self._rules[rule_id])

    def list(self) -> list[EventRule]:
        with self._lock:
            return [copy.deepcopy(self._rules[key]) for key in sorted(self._rules)]

    def delete(self, rule_id: str) -> None:
        with self._lock:
            if rule_id not in self._rules:
                raise KeyError(rule_id)
            del self._rules[rule_id]

    def evaluate(self, event: Event) -> tuple[list[str], list[str]]:
        matched_rules: list[str] = []
        alert_ids: list[str] = []

        for rule in self.list():
            if not rule.enabled:
                continue
            if rule.event_type not in {"*", event.event_type}:
                continue

            results = [self._matches(event, condition) for condition in rule.conditions]
            matched = all(results) if rule.match_all else any(results)
            if not rule.conditions:
                matched = True
            if not matched:
                continue

            matched_rules.append(rule.rule_id)
            for action in rule.actions:
                if action.action_type != "alert":
                    continue
                alert = alert_manager.create(
                    event=event,
                    title=action.title,
                    message=action.message,
                    severity=action.severity,
                    rule_id=rule.rule_id,
                    recommended_action=action.recommended_action,
                    metadata=action.metadata,
                )
                alert_ids.append(alert.alert_id)

        return matched_rules, alert_ids

    def _matches(self, event: Event, condition: RuleCondition) -> bool:
        value = self._resolve(event, condition.path)
        expected = condition.value
        operator = condition.operator

        if operator == RuleOperator.exists:
            return value is not None
        if operator == RuleOperator.eq:
            return value == expected
        if operator == RuleOperator.ne:
            return value != expected
        if operator == RuleOperator.gt:
            return self._numeric(value, expected, lambda a, b: a > b)
        if operator == RuleOperator.gte:
            return self._numeric(value, expected, lambda a, b: a >= b)
        if operator == RuleOperator.lt:
            return self._numeric(value, expected, lambda a, b: a < b)
        if operator == RuleOperator.lte:
            return self._numeric(value, expected, lambda a, b: a <= b)
        if operator == RuleOperator.contains:
            try:
                return expected in value
            except TypeError:
                return False
        if operator == RuleOperator.in_:
            try:
                return value in expected
            except TypeError:
                return False
        return False

    @staticmethod
    def _numeric(value: Any, expected: Any, predicate) -> bool:
        if isinstance(value, bool) or isinstance(expected, bool):
            return False
        if not isinstance(value, (int, float)) or not isinstance(expected, (int, float)):
            return False
        return bool(predicate(float(value), float(expected)))

    @staticmethod
    def _resolve(event: Event, path: str) -> Any:
        current: Any = event.model_dump(mode="python")
        for segment in path.split("."):
            if isinstance(current, dict):
                current = current.get(segment)
            else:
                return None
        return current

    def clear(self) -> None:
        with self._lock:
            self._rules.clear()


rule_engine = RuleEngine()