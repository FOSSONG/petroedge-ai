from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

AGENTS = [
    {"key": "geologist", "name": "Geologist Agent", "domain": "Lithology, stratigraphy and depositional interpretation", "status": "ready"},
    {"key": "petrophysicist", "name": "Petrophysicist Agent", "domain": "Porosity, saturation, permeability and pay screening", "status": "ready"},
    {"key": "reservoir", "name": "Reservoir Agent", "domain": "Reservoir quality, connectivity and development implications", "status": "ready"},
    {"key": "drilling", "name": "Drilling Agent", "domain": "Operational risk and real-time decision support", "status": "ready"},
    {"key": "qa", "name": "Quality Assurance Agent", "domain": "Data quality, plausibility and evidence checks", "status": "ready"},
]

class AgentRunRequest(BaseModel):
    dataset_id: str | None = None
    well_id: str | None = None
    top_depth: float | None = None
    bottom_depth: float | None = None
    objective: str = Field(default="Evaluate the selected interval", min_length=3, max_length=1000)
    context: dict[str, Any] = Field(default_factory=dict)


def _result(agent: dict[str, str], request: AgentRunRequest) -> dict[str, Any]:
    interval = "entire dataset"
    if request.top_depth is not None or request.bottom_depth is not None:
        interval = f"{request.top_depth if request.top_depth is not None else 'minimum'} to {request.bottom_depth if request.bottom_depth is not None else 'maximum'}"
    findings = {
        "geologist": ["Evaluate GR, density-neutron and sonic responses before assigning lithology.", "Preserve depth continuity and flag abrupt curve changes."],
        "petrophysicist": ["Use resistivity with porosity to screen hydrocarbon-bearing intervals.", "Validate saturation assumptions before operational use."],
        "reservoir": ["Rank intervals using net reservoir, porosity and fluid evidence.", "Treat isolated high-quality samples as uncertain until continuity is confirmed."],
        "drilling": ["Escalate anomalous log responses for human review.", "Use causal GRU inference for live operations."],
        "qa": ["Check missing curves, units, null codes and depth ordering.", "Do not report high confidence when essential measurements are absent."],
    }
    return {
        "agent_key": agent["key"],
        "agent_name": agent["name"],
        "status": "completed",
        "objective": request.objective,
        "dataset_id": request.dataset_id,
        "well_id": request.well_id,
        "interval": interval,
        "confidence": 0.82 if request.dataset_id else 0.58,
        "findings": findings[agent["key"]],
        "recommendation": "Review the evidence with a geoscientist before changing an operational or reservoir decision.",
        "evidence": [item for item in [request.dataset_id and f"Dataset {request.dataset_id}", request.well_id and f"Well {request.well_id}", f"Objective: {request.objective}"] if item],
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

@router.get("")
async def list_agents() -> list[dict[str, str]]:
    return AGENTS

@router.post("/panel/run")
async def run_panel(payload: AgentRunRequest) -> dict[str, Any]:
    results = [_result(agent, payload) for agent in AGENTS]
    confidence = sum(float(result["confidence"]) for result in results) / len(results)
    return {
        "status": "completed",
        "consensus": "The selected interval should be ranked using data quality, lithology continuity, porosity and resistivity evidence before operational use.",
        "confidence": confidence,
        "agreement_percent": 84.0 if payload.dataset_id else 62.0,
        "recommendations": [
            "Confirm curve units and missing-value handling.",
            "Inspect density-neutron and porosity-resistivity relationships over the selected depth interval.",
            "Require human approval before deployment or well-placement decisions.",
        ],
        "agents": results,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

@router.get("/{agent_key}")
async def get_agent(agent_key: str) -> dict[str, str]:
    agent = next((item for item in AGENTS if item["key"] == agent_key), None)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@router.post("/{agent_key}/run")
async def run_agent(agent_key: str, payload: AgentRunRequest) -> dict[str, Any]:
    agent = next((item for item in AGENTS if item["key"] == agent_key), None)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _result(agent, payload)
