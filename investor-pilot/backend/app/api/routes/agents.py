from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from app.core.rbac import require_roles
from app.platform_v1.datasets import get_dataset
from pydantic import BaseModel, Field

router = APIRouter(dependencies=[Depends(require_roles("viewer"))])

AGENTS = [
    {"key": "geologist", "name": "Geologist Agent", "domain": "Lithology, stratigraphy and depositional interpretation", "status": "measured_evidence"},
    {"key": "petrophysicist", "name": "Petrophysicist Agent", "domain": "Porosity, saturation, permeability and pay screening", "status": "measured_evidence"},
    {"key": "reservoir", "name": "Reservoir Agent", "domain": "Reservoir quality, connectivity and development implications", "status": "measured_evidence"},
    {"key": "drilling", "name": "Drilling Agent", "domain": "Operational risk and real-time decision support", "status": "measured_evidence"},
    {"key": "qa", "name": "Quality Assurance Agent", "domain": "Data quality, plausibility and evidence checks", "status": "measured_evidence"},
]

class AgentRunRequest(BaseModel):
    dataset_id: str | None = None
    well_id: str | None = None
    top_depth: float | None = None
    bottom_depth: float | None = None
    objective: str = Field(default="Evaluate the selected interval", min_length=3, max_length=1000)
    context: dict[str, Any] = Field(default_factory=dict)


def _validate_sources(request: AgentRunRequest) -> None:
    if request.dataset_id is not None:
        try:
            get_dataset(request.dataset_id)
        except KeyError as exc:
            raise HTTPException(404, "Dataset not found.") from exc
    if request.well_id is not None:
        raise HTTPException(status_code=422, detail="Well evidence is not connected to this guidance panel yet.")
    if request.top_depth is not None and request.bottom_depth is not None and request.top_depth > request.bottom_depth:
        raise HTTPException(status_code=422, detail="Top depth must not exceed bottom depth.")


def _result(agent: dict[str, str], request: AgentRunRequest, measured=None) -> dict[str, Any]:
    interval = "entire dataset"
    if request.top_depth is not None or request.bottom_depth is not None:
        interval = f"{request.top_depth if request.top_depth is not None else 'minimum'} to {request.bottom_depth if request.bottom_depth is not None else 'maximum'}"
    if request.dataset_id and measured is None:
        from app.services.measured_evidence import snapshot
        try:
            from app.platform_v1.datasets import get_dataset_path
            if get_dataset_path(request.dataset_id).suffix.lower()==".pdf":
                if request.top_depth is not None or request.bottom_depth is not None: raise ValueError("PDF evidence cannot use a depth filter.")
                from app.services.document_evidence import retrieve
                measured=retrieve(request.dataset_id,request.objective)
            else: measured = snapshot(request.dataset_id,request.top_depth,request.bottom_depth)
        except (ValueError,OSError) as exc: raise HTTPException(422,str(exc)) from exc
    findings = {
        "geologist": ["Evaluate GR, density-neutron and sonic responses before assigning lithology.", "Preserve depth continuity and flag abrupt curve changes."],
        "petrophysicist": ["Use resistivity with porosity to screen hydrocarbon-bearing intervals.", "Validate saturation assumptions before operational use."],
        "reservoir": ["Rank intervals using net reservoir, porosity and fluid evidence.", "Treat isolated high-quality samples as uncertain until continuity is confirmed."],
        "drilling": ["Escalate anomalous log responses for human review.", "No qualified live alarm model is installed; use historical replay for demonstration."],
        "qa": ["Check missing curves, units, null codes and depth ordering.", "Do not report high confidence when essential measurements are absent."],
    }
    evidence=[]
    if measured and measured.get("mode")=="extractive_pdf_retrieval":
        findings[agent["key"]]=[measured["answer"]]
        evidence=measured["evidence"]
    elif measured:
        selected={"geologist":["gamma_ray_api","sonic_usft"],"petrophysicist":["density_gcc","neutron_porosity_vv","resistivity_ohmm"],"reservoir":["depth_m","resistivity_ohmm"],"drilling":["caliper_in"],"qa":list(measured["curves"])}[agent["key"]]
        findings[agent["key"]]=[f"{key}: {measured['curves'][key]['valid']} valid rows; median {measured['curves'][key]['median']}; range {measured['curves'][key]['minimum']} to {measured['curves'][key]['maximum']} (canonical units)." for key in selected if key in measured["curves"]]
        findings[agent["key"]]+=measured["issues"]
        if not findings[agent["key"]]:findings[agent["key"]]=["No qualified measured curves for this specialty in the selected dataset."]
        evidence=[f"Dataset {measured['dataset_id']}; {measured['rows']} inspected rows",f"SHA256 {measured['sha256']}"]
    return {
        "agent_key": agent["key"],
        "agent_name": agent["name"],
        "status": "measured_evidence" if measured else "guidance_only",
        "analysis_performed": bool(measured),
        "limitations": ["Deterministic measured-data review; no calibrated confidence, trained specialist model or autonomous operational action. Objective/context is not executed as instructions."],
        "objective": request.objective,
        "dataset_id": request.dataset_id,
        "well_id": request.well_id,
        "interval": interval,
        "confidence": None,
        "findings": findings[agent["key"]],
        "recommendation": "Review the evidence with a geoscientist before changing an operational or reservoir decision.",
        "evidence": evidence,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

@router.get("")
async def list_agents() -> list[dict[str, str]]:
    return AGENTS

@router.post("/panel/run")
async def run_panel(payload: AgentRunRequest) -> dict[str, Any]:
    _validate_sources(payload)
    measured = None
    if payload.dataset_id:
        from app.platform_v1.datasets import get_dataset_path
        from app.services.measured_evidence import snapshot
        from app.services.document_evidence import retrieve
        try:
            if get_dataset_path(payload.dataset_id).suffix.lower()==".pdf":
                if payload.top_depth is not None or payload.bottom_depth is not None: raise ValueError("PDF evidence cannot use a depth filter.")
                measured=retrieve(payload.dataset_id,payload.objective)
            else: measured = snapshot(payload.dataset_id, payload.top_depth, payload.bottom_depth)
        except (ValueError, OSError) as exc: raise HTTPException(422, str(exc)) from exc
    results = [_result(agent, payload, measured) for agent in AGENTS]
    return {
        "status": "measured_evidence" if payload.dataset_id else "guidance_only",
        "analysis_performed": bool(payload.dataset_id),
        "limitations": ["Measured statistics only; no specialist model or calibrated confidence."],
        "consensus": "The selected interval should be ranked using data quality, lithology continuity, porosity and resistivity evidence before operational use.",
        "confidence": None,
        "agreement_percent": None,
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
    _validate_sources(payload)
    return _result(agent, payload)
