from __future__ import annotations
import json, math, os, sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.core.rbac import require_roles
from app.platform_v1.datasets import get_dataset

router=APIRouter()
READ=require_roles("admin","administrator","operator","engineer","geoscientist","petrophysicist","viewer")
WRITE=require_roles("admin","administrator","operator","engineer","geoscientist","petrophysicist")
ROOT=Path(__file__).resolve().parents[3]
DB=Path(os.getenv("PETROEDGE_DATA_DIR",str(ROOT/"data"))).resolve()/"ccus_runs.db"

def now(): return datetime.now(timezone.utc).isoformat()
def connect():
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(str(DB),timeout=30); c.row_factory=sqlite3.Row; c.execute("PRAGMA journal_mode=WAL"); return c
def initialise():
    with closing(connect()) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS ccus_runs(
        run_id TEXT PRIMARY KEY,project_name TEXT NOT NULL,dataset_id TEXT,dataset_name TEXT,
        field_name TEXT,well_name TEXT,reservoir_name TEXT,storage_type TEXT NOT NULL,
        capacity_mt REAL NOT NULL,pore_volume_m3 REAL NOT NULL,suitability_score REAL NOT NULL,
        suitability_class TEXT NOT NULL,injectivity_score REAL NOT NULL,containment_score REAL NOT NULL,
        data_quality_score REAL NOT NULL,pressure_margin_mpa REAL NOT NULL,risk_flags_json TEXT NOT NULL,
        recommendations_json TEXT NOT NULL,inputs_json TEXT NOT NULL,methodology_json TEXT NOT NULL,
        created_at TEXT NOT NULL)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_ccus_runs_created ON ccus_runs(created_at DESC)")
        c.commit()
initialise()

class Screen(BaseModel):
    model_config=ConfigDict(extra="forbid")
    dataset_id:str|None=Field(default=None,max_length=200)
    project_name:str=Field(min_length=2,max_length=200)
    storage_type:Literal["saline_aquifer","depleted_reservoir"]="saline_aquifer"
    area_km2:float=Field(gt=0,le=100000)
    net_thickness_m:float=Field(gt=0,le=5000)
    porosity_fraction:float=Field(gt=0,le=.60)
    co2_density_kg_m3:float=Field(ge=100,le=1200)
    storage_efficiency_fraction:float=Field(gt=0,le=.40)
    permeability_md:float=Field(ge=0,le=1000000)
    depth_m:float=Field(gt=0,le=15000)
    initial_pressure_mpa:float=Field(ge=0,le=200)
    fracture_pressure_mpa:float=Field(gt=0,le=300)
    caprock_thickness_m:float|None=Field(default=None,ge=0,le=5000)
    fault_risk:Literal["low","medium","high","unknown"]="unknown"
    pressure_data_available:bool=False
    seal_data_available:bool=False
    fault_data_available:bool=False
    geomechanics_available:bool=False
    notes:str|None=Field(default=None,max_length=2000)
    @field_validator("project_name")
    @classmethod
    def clean(cls,v):
        v=v.strip()
        if not v: raise ValueError("Project name cannot be blank.")
        return v

def clamp(v,a=0,b=100): return max(a,min(b,float(v)))
def classify(v): return "high-potential" if v>=75 else "conditional" if v>=55 else "low-confidence" if v>=35 else "unsuitable"
def calculate(p:Screen):
    area=p.area_km2*1_000_000
    pore=area*p.net_thickness_m*p.porosity_fraction
    capacity=pore*p.storage_efficiency_fraction*p.co2_density_kg_m3/1_000_000_000
    perm=clamp((math.log10(max(p.permeability_md,.01))+2)/6,0,1)
    inj=round(100*(.72*perm+.28*clamp(p.net_thickness_m/100,0,1)),2)
    cont=35+(min(p.caprock_thickness_m/2,25) if p.caprock_thickness_m is not None else 0)
    cont+=15 if p.seal_data_available else 0
    cont+=10 if p.fault_data_available else 0
    cont+=10 if p.geomechanics_available else 0
    cont+=dict(low=5,medium=-8,high=-25,unknown=-12)[p.fault_risk]
    cont=round(clamp(cont),2)
    dq=round(20*sum([p.pressure_data_available,p.seal_data_available,p.fault_data_available,p.geomechanics_available,bool(p.dataset_id)]),2)
    margin=p.fracture_pressure_mpa-p.initial_pressure_mpa
    score=round(.22*clamp(p.porosity_fraction/.25*100)+.20*inj+.25*cont+.13*dq+.10*clamp((p.depth_m-600)/14)+.10*clamp(margin/10*100),2)
    flags=[]
    if margin<=0: flags.append("Initial pressure is at or above the entered fracture-pressure limit.")
    elif margin<3: flags.append("Pressure margin is narrow and requires geomechanical verification.")
    if p.permeability_md<10: flags.append("Low permeability may materially constrain injectivity.")
    elif p.permeability_md<50: flags.append("Moderate-to-low permeability requires dynamic injection testing.")
    if p.caprock_thickness_m is None: flags.append("Caprock thickness has not been provided.")
    elif p.caprock_thickness_m<20: flags.append("Entered caprock thickness is below the screening preference of 20 m.")
    if p.fault_risk=="high": flags.append("High fault risk requires structural and geomechanical review.")
    elif p.fault_risk=="unknown": flags.append("Fault risk is unknown.")
    if not p.pressure_data_available: flags.append("Measured pressure data are unavailable.")
    if not p.seal_data_available: flags.append("Seal-characterisation evidence is unavailable.")
    if not p.fault_data_available: flags.append("Fault-framework evidence is unavailable.")
    if not p.geomechanics_available: flags.append("Geomechanical evidence is unavailable.")
    rec=["Advance to site-specific modelling and dynamic simulation." if score>=75 else "Retain as a candidate and close evidence gaps before ranking." if score>=55 else "Do not progress beyond screening until major uncertainties are reduced."]
    if not p.pressure_data_available: rec.append("Acquire formation-pressure and pressure-gradient data.")
    if not p.seal_data_available: rec.append("Characterise caprock continuity and entry pressure.")
    if not p.fault_data_available: rec.append("Map faults and evaluate reactivation and leakage pathways.")
    if not p.geomechanics_available or margin<3: rec.append("Perform geomechanical fracture-pressure and fault-reactivation analysis.")
    if p.permeability_md<50: rec.append("Run pressure-transient or injection testing.")
    rec.append("Treat capacity as a volumetric screening estimate, not a bankable reserve.")
    return dict(capacity_mt=round(capacity,4),pore_volume_m3=round(pore,2),suitability_score=score,
      suitability_class=classify(score),injectivity_score=inj,containment_score=cont,
      data_quality_score=dq,pressure_margin_mpa=round(margin,3),risk_flags=flags,recommendations=rec,
      methodology={"capacity_equation":"M_CO2 = A Ã— h_net Ã— phi Ã— E_storage Ã— rho_CO2",
      "limitations":["No plume simulation","No geomechanical forecast","No regulatory resource classification"]})

def serial(row):
    d=dict(row)
    for k in ("risk_flags_json","recommendations_json","inputs_json","methodology_json"):
        d[k.replace("_json","")]=json.loads(d.pop(k))
    return d

@router.get("/capabilities")
def capabilities(_:dict[str,Any]=Depends(READ)):
    return {"status":"operational","version":"1.0-screening","capabilities":["volumetric_storage_capacity","reservoir_suitability_scoring","injectivity_proxy","containment_scoring","persistent_runs"],"limitations":["No plume simulation","No geomechanical forecast"]}

@router.post("/screen",status_code=201)
def screen(p:Screen,_:dict[str,Any]=Depends(WRITE)):
    meta={"dataset_name":None,"field_name":None,"well_name":None,"reservoir_name":None}
    if p.dataset_id:
        try:
            ds=get_dataset(p.dataset_id)
        except KeyError as e:
            raise HTTPException(404,"Selected dataset was not found.") from e
        meta={"dataset_name":ds.name,"field_name":ds.field_name,"well_name":ds.well_name,"reservoir_name":ds.reservoir_name}
    r=calculate(p); rid=f"ccus-{uuid4().hex[:14]}"; created=now()
    vals=(rid,p.project_name,p.dataset_id,meta["dataset_name"],meta["field_name"],meta["well_name"],meta["reservoir_name"],p.storage_type,
    r["capacity_mt"],r["pore_volume_m3"],r["suitability_score"],r["suitability_class"],r["injectivity_score"],r["containment_score"],
    r["data_quality_score"],r["pressure_margin_mpa"],json.dumps(r["risk_flags"]),json.dumps(r["recommendations"]),json.dumps(p.model_dump()),json.dumps(r["methodology"]),created)
    with closing(connect()) as c:
        c.execute("INSERT INTO ccus_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",vals); c.commit()
        row=c.execute("SELECT * FROM ccus_runs WHERE run_id=?",(rid,)).fetchone()
    return serial(row)

@router.get("/runs")
def runs(limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0),_:dict[str,Any]=Depends(READ)):
    with closing(connect()) as c: rows=c.execute("SELECT * FROM ccus_runs ORDER BY created_at DESC LIMIT ? OFFSET ?",(limit,offset)).fetchall()
    return [serial(x) for x in rows]

@router.get("/runs/{run_id}")
def run(run_id:str,_:dict[str,Any]=Depends(READ)):
    with closing(connect()) as c: row=c.execute("SELECT * FROM ccus_runs WHERE run_id=?",(run_id,)).fetchone()
    if row is None: raise HTTPException(404,"CCUS screening run not found.")
    return serial(row)

@router.delete("/runs/{run_id}",status_code=204)
def remove(run_id:str,_:dict[str,Any]=Depends(WRITE)):
    with closing(connect()) as c: cur=c.execute("DELETE FROM ccus_runs WHERE run_id=?",(run_id,)); c.commit()
    if cur.rowcount==0: raise HTTPException(404,"CCUS screening run not found.")