from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.alerts.schemas import AlertSeverity


class RuleOperator(str, Enum):
    eq = "eq"
    ne = "ne"
    gt = "gt"
    gte = "gte"
    lt = "lt"
    lte = "lte"
    contains = "contains"
    in_ = "in"
    exists = "exists"


class RuleCondition(BaseModel):
    path: str
    operator: RuleOperator
    value: Any = None


class RuleAction(BaseModel):
    action_type: str = "alert"
    title: str
    message: str
    severity: AlertSeverity = AlertSeverity.warning
    recommended_action: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventRule(BaseModel):
    rule_id: str
    name: str
    event_type: str = "*"
    enabled: bool = True
    match_all: bool = True
    conditions: list[RuleCondition] = Field(default_factory=list)
    actions: list[RuleAction] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuleCreate(EventRule):
    pass