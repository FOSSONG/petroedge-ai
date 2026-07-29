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

$BackendRoot = Join-Path $ProjectRoot "backend"
$AppRoot = Join-Path $BackendRoot "app"

if (-not (Test-Path (Join-Path $AppRoot "main.py"))) {
    throw "PetroEdge backend not found. Run this script from the PetroEdge-AI-v1-demo project root."
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $ProjectRoot "backups\multi-agent-$Timestamp"
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

$BackupFiles = @(
    "backend\app\main.py",
    "backend\app\workflows\nodes\core.py",
    "backend\app\workflows\templates.py",
    "backend\app\api\routes\agents.py"
)

foreach ($RelativePath in $BackupFiles) {
    $Source = Join-Path $ProjectRoot $RelativePath
    if (Test-Path $Source) {
        $Destination = Join-Path $BackupRoot $RelativePath
        New-Item -ItemType Directory -Force -Path (Split-Path $Destination) | Out-Null
        Copy-Item $Source $Destination -Force
    }
}

$Directories = @(
    "backend\app\agents",
    "backend\app\api\routes",
    "backend\tests",
    "docs"
)

foreach ($Directory in $Directories) {
    New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot $Directory) | Out-Null
}

Write-Utf8File "backend\app\agents\schemas.py" @'
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
'@

Write-Utf8File "backend\app\agents\base.py" @'
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.agents.schemas import AgentDomain, AgentResult


class BaseAgent(ABC):
    key: str
    name: str
    domain: AgentDomain

    @abstractmethod
    async def analyse(
        self,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        raise NotImplementedError

    @staticmethod
    def rows_from_inputs(inputs: dict[str, Any]) -> list[dict[str, Any]]:
        rows = inputs.get("rows")
        if isinstance(rows, list) and all(isinstance(item, dict) for item in rows):
            return rows
        return []

    @staticmethod
    def numeric_values(rows: list[dict[str, Any]], column: str) -> list[float]:
        values: list[float] = []
        for row in rows:
            value = row.get(column)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(float(value))
        return values
'@

Write-Utf8File "backend\app\agents\registry.py" @'
from __future__ import annotations

import threading

from app.agents.base import BaseAgent


class AgentRegistryError(RuntimeError):
    pass


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._lock = threading.RLock()

    def register(self, agent: BaseAgent, *, replace: bool = False) -> None:
        with self._lock:
            if agent.key in self._agents and not replace:
                raise AgentRegistryError(f"Agent already registered: {agent.key}")
            self._agents[agent.key] = agent

    def get(self, key: str) -> BaseAgent:
        try:
            return self._agents[key]
        except KeyError as exc:
            raise AgentRegistryError(f"Unknown agent: {key}") from exc

    def list(self) -> list[BaseAgent]:
        return sorted(self._agents.values(), key=lambda item: item.name.lower())

    def keys(self) -> list[str]:
        return sorted(self._agents)


agent_registry = AgentRegistry()
'@

Write-Utf8File "backend\app\agents\domain_agents.py" @'
from __future__ import annotations

from statistics import mean
from typing import Any

from app.agents.base import BaseAgent
from app.agents.schemas import AgentDomain, AgentFinding, AgentResult, Severity


def _average(agent: BaseAgent, rows: list[dict[str, Any]], *columns: str) -> tuple[str | None, float | None]:
    for column in columns:
        values = agent.numeric_values(rows, column)
        if values:
            return column, mean(values)
    return None, None


class GeologistAgent(BaseAgent):
    key = "geologist"
    name = "Geologist Agent"
    domain = AgentDomain.geology

    async def analyse(self, inputs: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        rows = self.rows_from_inputs(inputs)
        gr_column, gr_mean = _average(self, rows, "GR", "GR_COMP.GAPI")
        findings = []
        confidence = 0.45

        if gr_mean is not None:
            confidence = 0.80
            if gr_mean < 60:
                statement = "The interval is predominantly clean and sand-prone."
                recommendation = "Prioritise the interval for reservoir-quality screening."
            elif gr_mean < 90:
                statement = "The interval is moderately shaly and may represent shaly sand."
                recommendation = "Integrate density-neutron and resistivity evidence before net-pay classification."
            else:
                statement = "The interval is shale-prone."
                recommendation = "Treat reservoir potential cautiously unless supported by core or image-log evidence."
            findings.append(
                AgentFinding(
                    title="Lithology screening",
                    statement=statement,
                    confidence=confidence,
                    evidence=[f"Mean {gr_column} = {gr_mean:.2f}"],
                    recommendations=[recommendation],
                    metrics={"mean_gamma_ray": gr_mean},
                )
            )

        if not findings:
            findings.append(
                AgentFinding(
                    title="Insufficient geological evidence",
                    statement="No recognised gamma-ray curve was available for lithology screening.",
                    confidence=0.30,
                    severity=Severity.medium,
                    recommendations=["Provide GR and depth-indexed log data."],
                )
            )

        return AgentResult(
            agent_key=self.key,
            agent_name=self.name,
            domain=self.domain,
            confidence=confidence,
            findings=findings,
            summary=findings[0].statement,
            limitations=[] if gr_mean is not None else ["Gamma-ray data unavailable."],
        )


class PetrophysicistAgent(BaseAgent):
    key = "petrophysicist"
    name = "Petrophysicist Agent"
    domain = AgentDomain.petrophysics

    async def analyse(self, inputs: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        rows = self.rows_from_inputs(inputs)
        phi_column, phi_mean = _average(self, rows, "PHI_D", "PHI", "POROSITY")
        sw_column, sw_mean = _average(self, rows, "SW_ARCHIE", "SW", "WATER_SATURATION")
        findings = []
        evidence = []
        confidence = 0.40

        if phi_mean is not None:
            evidence.append(f"Mean {phi_column} = {phi_mean:.3f}")
        if sw_mean is not None:
            evidence.append(f"Mean {sw_column} = {sw_mean:.3f}")

        if phi_mean is not None or sw_mean is not None:
            confidence = 0.88 if phi_mean is not None and sw_mean is not None else 0.72
            quality = "uncertain"
            if phi_mean is not None and sw_mean is not None:
                if phi_mean >= 0.18 and sw_mean <= 0.45:
                    quality = "favourable"
                elif phi_mean < 0.10 or sw_mean > 0.70:
                    quality = "poor"
                else:
                    quality = "moderate"

            findings.append(
                AgentFinding(
                    title="Reservoir quality",
                    statement=f"Petrophysical reservoir quality is {quality}.",
                    confidence=confidence,
                    evidence=evidence,
                    recommendations=[
                        "Validate cut-offs against core-calibrated porosity, saturation and permeability."
                    ],
                    metrics={
                        "mean_porosity": phi_mean,
                        "mean_water_saturation": sw_mean,
                    },
                )
            )
        else:
            findings.append(
                AgentFinding(
                    title="Insufficient petrophysical evidence",
                    statement="No recognised porosity or water-saturation curves were available.",
                    confidence=0.30,
                    severity=Severity.medium,
                    recommendations=["Run the petrophysical workflow before multi-agent interpretation."],
                )
            )

        return AgentResult(
            agent_key=self.key,
            agent_name=self.name,
            domain=self.domain,
            confidence=confidence,
            findings=findings,
            summary=findings[0].statement,
            limitations=[] if evidence else ["Porosity and saturation evidence unavailable."],
        )


class ReservoirEngineerAgent(BaseAgent):
    key = "reservoir_engineer"
    name = "Reservoir Engineer Agent"
    domain = AgentDomain.reservoir_engineering

    async def analyse(self, inputs: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        rows = self.rows_from_inputs(inputs)
        pressure_column, pressure_mean = _average(self, rows, "PRESSURE", "Pressure", "pressure")
        perm_column, perm_mean = _average(self, rows, "PERM", "PERMEABILITY", "k")
        evidence = []
        if pressure_mean is not None:
            evidence.append(f"Mean {pressure_column} = {pressure_mean:.2f}")
        if perm_mean is not None:
            evidence.append(f"Mean {perm_column} = {perm_mean:.2f}")

        if evidence:
            confidence = 0.70
            statement = "Reservoir deliverability can be screened, but connectivity requires spatial or pressure-transient evidence."
            limitations = ["Connectivity cannot be confirmed from scalar averages alone."]
        else:
            confidence = 0.28
            statement = "Reservoir-engineering evidence is insufficient for connectivity or recovery assessment."
            limitations = ["Pressure and permeability evidence unavailable."]

        finding = AgentFinding(
            title="Reservoir engineering screen",
            statement=statement,
            confidence=confidence,
            evidence=evidence,
            recommendations=[
                "Integrate pressure, production, PVT, completion and spatial data for dynamic assessment."
            ],
            metrics={"mean_pressure": pressure_mean, "mean_permeability": perm_mean},
        )
        return AgentResult(
            agent_key=self.key,
            agent_name=self.name,
            domain=self.domain,
            confidence=confidence,
            findings=[finding],
            summary=statement,
            limitations=limitations,
        )


class ProductionEngineerAgent(BaseAgent):
    key = "production_engineer"
    name = "Production Engineer Agent"
    domain = AgentDomain.production_engineering

    async def analyse(self, inputs: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        rows = self.rows_from_inputs(inputs)
        oil_column, oil_mean = _average(self, rows, "Qoil STB/d", "oil_rate", "QOIL")
        water_column, water_mean = _average(self, rows, "Qwat STB/d", "water_rate", "QWAT")
        evidence = []
        if oil_mean is not None:
            evidence.append(f"Mean {oil_column} = {oil_mean:.2f}")
        if water_mean is not None:
            evidence.append(f"Mean {water_column} = {water_mean:.2f}")

        if oil_mean is not None:
            confidence = 0.72
            statement = "Production performance is measurable from the supplied rate data."
            recommendations = ["Add ordered dates and cumulative production for decline and breakthrough analysis."]
            limitations = []
        else:
            confidence = 0.25
            statement = "Production performance cannot be evaluated because no recognised oil-rate curve was supplied."
            recommendations = ["Provide date-indexed oil, gas and water production histories."]
            limitations = ["Production-rate evidence unavailable."]

        finding = AgentFinding(
            title="Production performance",
            statement=statement,
            confidence=confidence,
            evidence=evidence,
            recommendations=recommendations,
            metrics={"mean_oil_rate": oil_mean, "mean_water_rate": water_mean},
        )
        return AgentResult(
            agent_key=self.key,
            agent_name=self.name,
            domain=self.domain,
            confidence=confidence,
            findings=[finding],
            summary=statement,
            limitations=limitations,
        )


class DrillingEngineerAgent(BaseAgent):
    key = "drilling_engineer"
    name = "Drilling Engineer Agent"
    domain = AgentDomain.drilling_engineering

    async def analyse(self, inputs: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        rows = self.rows_from_inputs(inputs)
        rop_column, rop_mean = _average(self, rows, "ROP", "rate_of_penetration")
        caliper_column, caliper_mean = _average(self, rows, "CALI", "CALIPER")
        evidence = []
        if rop_mean is not None:
            evidence.append(f"Mean {rop_column} = {rop_mean:.2f}")
        if caliper_mean is not None:
            evidence.append(f"Mean {caliper_column} = {caliper_mean:.2f}")

        confidence = 0.68 if evidence else 0.22
        statement = (
            "Available drilling measurements support a preliminary operational screen."
            if evidence
            else "Drilling hazards cannot be assessed from the supplied dataset."
        )
        finding = AgentFinding(
            title="Drilling risk screen",
            statement=statement,
            confidence=confidence,
            evidence=evidence,
            recommendations=[
                "Integrate mud weight, ECD, torque, drag, caliper, ROP and loss-event data."
            ],
            metrics={"mean_rop": rop_mean, "mean_caliper": caliper_mean},
        )
        return AgentResult(
            agent_key=self.key,
            agent_name=self.name,
            domain=self.domain,
            confidence=confidence,
            findings=[finding],
            summary=statement,
            limitations=[] if evidence else ["Drilling measurements unavailable."],
        )


class CCUSAgent(BaseAgent):
    key = "ccus"
    name = "CCUS Agent"
    domain = AgentDomain.ccus

    async def analyse(self, inputs: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        rows = self.rows_from_inputs(inputs)
        phi_column, phi_mean = _average(self, rows, "PHI_D", "PHI", "POROSITY")
        perm_column, perm_mean = _average(self, rows, "PERM", "PERMEABILITY", "k")
        evidence = []
        if phi_mean is not None:
            evidence.append(f"Mean {phi_column} = {phi_mean:.3f}")
        if perm_mean is not None:
            evidence.append(f"Mean {perm_column} = {perm_mean:.2f}")

        confidence = 0.62 if evidence else 0.20
        statement = (
            "The interval has preliminary storage-characterisation evidence, but seal integrity and injectivity remain unverified."
            if evidence
            else "CCUS suitability cannot be assessed from the supplied evidence."
        )
        finding = AgentFinding(
            title="CCUS suitability screen",
            statement=statement,
            confidence=confidence,
            evidence=evidence,
            recommendations=[
                "Add caprock, pressure, fault, geomechanical, fluid and dynamic injectivity evidence."
            ],
            metrics={"mean_porosity": phi_mean, "mean_permeability": perm_mean},
        )
        return AgentResult(
            agent_key=self.key,
            agent_name=self.name,
            domain=self.domain,
            confidence=confidence,
            findings=[finding],
            summary=statement,
            limitations=["This is a screening result, not a storage certification."],
        )
'@

Write-Utf8File "backend\app\agents\consensus.py" @'
from __future__ import annotations

from collections import Counter

from app.agents.schemas import AgentResult, ConsensusResult


class ConsensusEngine:
    def build(self, results: list[AgentResult]) -> ConsensusResult:
        if not results:
            return ConsensusResult(
                overall_confidence=0.0,
                summary="No agent results were produced.",
                missing_evidence=["No agents executed."],
            )

        confidence = sum(result.confidence for result in results) / len(results)
        recommendations = []
        missing_evidence = []
        summaries = []

        for result in results:
            summaries.append(f"{result.agent_name}: {result.summary}")
            missing_evidence.extend(result.limitations)
            for finding in result.findings:
                recommendations.extend(finding.recommendations)

        recommendation_counts = Counter(recommendations)
        deduplicated_recommendations = [
            recommendation
            for recommendation, _ in recommendation_counts.most_common()
        ]

        strong_agents = [
            result.agent_name
            for result in results
            if result.confidence >= 0.70
        ]
        agreements = []
        if len(strong_agents) >= 2:
            agreements.append(
                "Multiple domain agents produced findings with confidence of at least 0.70."
            )

        summary = " ".join(summaries)

        return ConsensusResult(
            overall_confidence=round(confidence, 4),
            summary=summary,
            recommendations=deduplicated_recommendations,
            agreements=agreements,
            disagreements=[],
            missing_evidence=sorted(set(missing_evidence)),
        )
'@

Write-Utf8File "backend\app\agents\orchestrator.py" @'
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from app.agents.consensus import ConsensusEngine
from app.agents.registry import agent_registry
from app.agents.schemas import AgentPanelResponse, AgentRequest
from app.agents.domain_agents import (
    CCUSAgent,
    DrillingEngineerAgent,
    GeologistAgent,
    PetrophysicistAgent,
    ProductionEngineerAgent,
    ReservoirEngineerAgent,
)


def register_builtin_agents() -> None:
    agents = (
        GeologistAgent(),
        PetrophysicistAgent(),
        ReservoirEngineerAgent(),
        ProductionEngineerAgent(),
        DrillingEngineerAgent(),
        CCUSAgent(),
    )
    for agent in agents:
        agent_registry.register(agent, replace=True)


class AgentOrchestrator:
    def __init__(self) -> None:
        register_builtin_agents()
        self.consensus_engine = ConsensusEngine()

    async def execute(self, request: AgentRequest) -> AgentPanelResponse:
        keys = request.agent_keys or agent_registry.keys()
        agents = [agent_registry.get(key) for key in keys]

        results = await asyncio.gather(
            *[
                agent.analyse(request.inputs, request.context)
                for agent in agents
            ]
        )
        consensus = self.consensus_engine.build(results)
        return AgentPanelResponse(
            panel_id=uuid.uuid4().hex,
            agents=results,
            consensus=consensus,
            metadata={
                "agent_count": len(results),
                "agent_keys": keys,
                "execution": "deterministic_domain_rules",
            },
        )


agent_orchestrator = AgentOrchestrator()
'@

Write-Utf8File "backend\app\agents\__init__.py" @'
from app.agents.orchestrator import AgentOrchestrator, agent_orchestrator
from app.agents.registry import AgentRegistry, AgentRegistryError, agent_registry
from app.agents.schemas import (
    AgentDomain,
    AgentFinding,
    AgentPanelResponse,
    AgentRequest,
    AgentResult,
    ConsensusResult,
)

__all__ = [
    "AgentDomain",
    "AgentFinding",
    "AgentOrchestrator",
    "AgentPanelResponse",
    "AgentRegistry",
    "AgentRegistryError",
    "AgentRequest",
    "AgentResult",
    "ConsensusResult",
    "agent_orchestrator",
    "agent_registry",
]
'@

Write-Utf8File "backend\app\api\routes\agents.py" @'
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents import AgentRequest, agent_orchestrator, agent_registry
from app.agents.registry import AgentRegistryError
from app.core.rbac import require_roles

router = APIRouter()

READ_ROLES = ("admin", "geoscientist", "engineer", "viewer")
WRITE_ROLES = ("admin", "geoscientist", "engineer")


@router.get("")
async def list_agents(
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    agents = agent_registry.list()
    return {
        "count": len(agents),
        "agents": [
            {
                "key": agent.key,
                "name": agent.name,
                "domain": agent.domain.value,
            }
            for agent in agents
        ],
    }


@router.get("/{agent_key}")
async def get_agent(
    agent_key: str,
    _: dict[str, Any] = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    try:
        agent = agent_registry.get(agent_key)
    except AgentRegistryError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return {
        "key": agent.key,
        "name": agent.name,
        "domain": agent.domain.value,
    }


@router.post("/panel/run")
async def run_agent_panel(
    request: AgentRequest,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    try:
        result = await agent_orchestrator.execute(request)
    except AgentRegistryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return result.model_dump(mode="json")


@router.post("/{agent_key}/run")
async def run_agent(
    agent_key: str,
    request: AgentRequest,
    _: dict[str, Any] = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    request.agent_keys = [agent_key]
    try:
        result = await agent_orchestrator.execute(request)
    except AgentRegistryError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return result.model_dump(mode="json")
'@

# Patch workflow node core.py
$CorePath = Join-Path $ProjectRoot "backend\app\workflows\nodes\core.py"
$CoreContent = Get-Content $CorePath -Raw

if ($CoreContent -notmatch "from app\.agents import AgentRequest, agent_orchestrator") {
    $CoreContent = $CoreContent -replace `
        "from app\.ai\.registry import registry as model_registry", `
        "from app.ai.registry import registry as model_registry`r`nfrom app.agents import AgentRequest, agent_orchestrator"
}

if ($CoreContent -notmatch "async def multi_agent_analysis") {
    $InsertFunction = @'

async def multi_agent_analysis(node: NodeSpec, context: WorkflowContext) -> dict[str, Any]:
    dependencies = context.dependency_payload(node.depends_on)
    rows: list[dict[str, Any]] = []

    for dependency in dependencies.values():
        candidate = dependency.get("rows")
        if isinstance(candidate, list) and all(isinstance(item, dict) for item in candidate):
            rows = candidate
            break

    agent_keys = node.parameters.get("agents")
    request = AgentRequest(
        inputs={"rows": rows},
        context={
            "workflow_id": context.workflow_id,
            "run_id": context.run_id,
            "dependencies": dependencies,
        },
        agent_keys=agent_keys if isinstance(agent_keys, list) else None,
    )
    result = await agent_orchestrator.execute(request)
    return result.model_dump(mode="json")

'@
    $CoreContent = $CoreContent -replace `
        "async def report_summary", `
        ($InsertFunction + "async def report_summary")
}

if ($CoreContent -notmatch '"agents\.panel": multi_agent_analysis') {
    $CoreContent = $CoreContent -replace `
        '"ai\.model": model_capability,', `
        '"ai.model": model_capability,`r`n        "agents.panel": multi_agent_analysis,'
}

[System.IO.File]::WriteAllText(
    $CorePath,
    $CoreContent,
    [System.Text.UTF8Encoding]::new($false)
)

# Patch workflow template
$TemplatesPath = Join-Path $ProjectRoot "backend\app\workflows\templates.py"
$TemplatesContent = Get-Content $TemplatesPath -Raw

if ($TemplatesContent -notmatch 'id="multi_agent_interpretation"') {
    $Marker = "`r`n)"
    $NewTemplate = @'
    WorkflowDefinition(
        id="multi_agent_interpretation",
        name="Multi-Agent Reservoir Interpretation",
        description="Petrophysical processing followed by coordinated domain-agent analysis.",
        tags=["multi-agent", "petrophysics", "reservoir"],
        nodes=[
            NodeSpec(id="input", type="input.payload", parameters={"key": "rows"}),
            NodeSpec(id="qc", type="qc.basic", depends_on=["input"]),
            NodeSpec(id="features", type="features.summary", depends_on=["qc"]),
            NodeSpec(id="petrophysics", type="petrophysics.basic", depends_on=["features"]),
            NodeSpec(
                id="agents",
                type="agents.panel",
                parameters={
                    "agents": [
                        "geologist",
                        "petrophysicist",
                        "reservoir_engineer",
                        "production_engineer",
                        "drilling_engineer",
                        "ccus",
                    ]
                },
                depends_on=["petrophysics"],
            ),
            NodeSpec(
                id="report",
                type="report.summary",
                parameters={"title": "Multi-Agent Reservoir Interpretation"},
                depends_on=["agents"],
            ),
        ],
    ),
'@
    $LastClose = $TemplatesContent.LastIndexOf(")")
    if ($LastClose -lt 0) {
        throw "Could not patch backend\app\workflows\templates.py"
    }
    $TemplatesContent = $TemplatesContent.Insert($LastClose, $NewTemplate)
    [System.IO.File]::WriteAllText(
        $TemplatesPath,
        $TemplatesContent,
        [System.Text.UTF8Encoding]::new($false)
    )
}

# Register route in main.py
$MainPath = Join-Path $ProjectRoot "backend\app\main.py"
$MainContent = Get-Content $MainPath -Raw

if ($MainContent -notmatch '\("agents",\s*"/agents"') {
    $Pattern = '\("workflows",\s*"/workflows",\s*\("Workflow Engine",\),\s*True\),'
    if ($MainContent -match $Pattern) {
        $Replacement = '("workflows", "/workflows", ("Workflow Engine",), True),' + "`r`n    " +
            '("agents", "/agents", ("Multi-Agent AI",), True),'
        $MainContent = [regex]::Replace($MainContent, $Pattern, $Replacement, 1)
    } else {
        $Pattern = '\("models",\s*"/models",\s*\("Models",\),\s*True\),'
        $Replacement = '("models", "/models", ("Models",), True),' + "`r`n    " +
            '("agents", "/agents", ("Multi-Agent AI",), True),'
        $MainContent = [regex]::Replace($MainContent, $Pattern, $Replacement, 1)
    }

    [System.IO.File]::WriteAllText(
        $MainPath,
        $MainContent,
        [System.Text.UTF8Encoding]::new($false)
    )
}

Write-Utf8File "backend\tests\test_agents.py" @'
import pytest

from app.agents import AgentRequest, agent_orchestrator, agent_registry


def test_builtin_agents_are_registered() -> None:
    assert {
        "geologist",
        "petrophysicist",
        "reservoir_engineer",
        "production_engineer",
        "drilling_engineer",
        "ccus",
    }.issubset(set(agent_registry.keys()))


@pytest.mark.asyncio
async def test_agent_panel_executes() -> None:
    result = await agent_orchestrator.execute(
        AgentRequest(
            inputs={
                "rows": [
                    {
                        "DEPTH": 1000.0,
                        "GR": 45.0,
                        "PHI_D": 0.24,
                        "SW_ARCHIE": 0.30,
                        "PERM": 250.0,
                        "Qoil STB/d": 1000.0,
                    }
                ]
            },
            agent_keys=["geologist", "petrophysicist", "reservoir_engineer"],
        )
    )

    assert len(result.agents) == 3
    assert result.consensus.overall_confidence > 0
    assert result.metadata["agent_count"] == 3


@pytest.mark.asyncio
async def test_petrophysicist_recognises_favourable_interval() -> None:
    result = await agent_orchestrator.execute(
        AgentRequest(
            inputs={
                "rows": [
                    {"PHI_D": 0.25, "SW_ARCHIE": 0.25},
                    {"PHI_D": 0.23, "SW_ARCHIE": 0.30},
                ]
            },
            agent_keys=["petrophysicist"],
        )
    )

    assert "favourable" in result.agents[0].summary.lower()
'@

Write-Utf8File "backend\tests\test_agents_api.py" @'
from fastapi.testclient import TestClient

from app.main import app


def test_agent_routes_are_present_in_openapi() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]
        assert "/api/v1/agents" in paths
        assert "/api/v1/agents/panel/run" in paths
        assert "/api/v1/agents/{agent_key}" in paths
        assert "/api/v1/agents/{agent_key}/run" in paths
'@

Write-Utf8File "backend\tests\test_agents_workflow.py" @'
import pytest

from app.workflows.engine import WorkflowEngine
from app.workflows.schemas import RunStatus, WorkflowRunRequest


@pytest.mark.asyncio
async def test_multi_agent_workflow_runs() -> None:
    engine = WorkflowEngine()
    run = await engine.run(
        "multi_agent_interpretation",
        WorkflowRunRequest(
            inputs={
                "rows": [
                    {"DEPTH": 1000.0, "GR": 45.0, "RHOB": 2.30, "RT": 10.0},
                    {"DEPTH": 1000.5, "GR": 50.0, "RHOB": 2.28, "RT": 12.0},
                ]
            }
        ),
    )

    assert run.status == RunStatus.succeeded
    assert "agents" in run.outputs
    assert len(run.outputs["agents"]["agents"]) == 6
    assert "consensus" in run.outputs["agents"]
'@

Write-Utf8File "docs\multi-agent-ai.md" @'
# PetroEdge Multi-Agent AI

This milestone adds a deterministic, auditable domain-agent layer.

## Built-in agents

- Geologist
- Petrophysicist
- Reservoir Engineer
- Production Engineer
- Drilling Engineer
- CCUS

## API

- `GET /api/v1/agents`
- `GET /api/v1/agents/{agent_key}`
- `POST /api/v1/agents/{agent_key}/run`
- `POST /api/v1/agents/panel/run`

## Workflow integration

The node type `agents.panel` is available to the Workflow Engine.

The built-in workflow template is:

- `multi_agent_interpretation`

## Important implementation boundary

The current agents use deterministic domain rules and supplied evidence. They do not call an external large language model and do not claim unsupported geological or engineering conclusions. Future LLM-backed reasoning can be introduced behind the same agent interface after governance, prompt versioning, evaluation and audit controls are implemented.
'@

Write-Host ""
Write-Host "PetroEdge Multi-Agent AI installed." -ForegroundColor Green
Write-Host "Backup created at: $BackupRoot" -ForegroundColor Cyan
Write-Host ""
Write-Host "Run next:" -ForegroundColor Yellow
Write-Host "  python -m pytest .\backend\tests\test_agents.py -q"
Write-Host "  python -m pytest .\backend\tests\test_agents_api.py -q"
Write-Host "  python -m pytest .\backend\tests\test_agents_workflow.py -q"
Write-Host "  python -m pytest .\backend\tests\test_workflow_engine.py -q"
Write-Host "  python -m pytest .\backend\tests\test_workflows_api.py -q"
Write-Host "  python -m uvicorn app.main:app --reload --app-dir backend"
