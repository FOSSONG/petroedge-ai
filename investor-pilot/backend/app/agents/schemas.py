from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentDomain(str, Enum):
    geology = "geology"
    petrophysics = "petrophysics"
    reservoir_engineering = "reservoir_engineering"
    production_engineering = "production_engineering"
    drilling_engineering = "drilling_engineering"
    ccus = "ccus"


class Severity(str, Enum):
    information = "information"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AgentFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    statement: str
    confidence: float = Field(ge=0.0, le=1.0)
    severity: Severity = Severity.information
    evidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    metrics: dict[str, float | int | str | None] = Field(default_factory=dict)


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inputs: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    agent_keys: list[str] | None = None


class AgentResult(BaseModel):
    agent_key: str
    agent_name: str
    domain: AgentDomain
    confidence: float = Field(ge=0.0, le=1.0)
    findings: list[AgentFinding] = Field(default_factory=list)
    summary: str
    limitations: list[str] = Field(default_factory=list)


class Disagreement(BaseModel):
    topic: str
    agents: list[str]
    explanation: str
    severity: Severity = Severity.medium


class ConsensusResult(BaseModel):
    overall_confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    recommendations: list[str] = Field(default_factory=list)
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[Disagreement] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class AgentPanelResponse(BaseModel):
    panel_id: str
    agents: list[AgentResult]
    consensus: ConsensusResult
    metadata: dict[str, Any] = Field(default_factory=dict)