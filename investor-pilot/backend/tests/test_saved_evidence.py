import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.routes import analytics, reports
from app.core.security import get_current_user
from app.core.ownership import OwnershipContextMiddleware
from app.services import analysis_records, report_service
from test_asset_ownership import ALICE, BOB, acting

@pytest.fixture
def evidence_client(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    out=tmp_path/"reports";out.mkdir()
    monkeypatch.setattr(report_service,"REPORT_ROOT",out)
    monkeypatch.setattr(reports,"REPORT_ROOT",out)
    monkeypatch.setattr(report_service,"_report_service",None)
    with acting(ALICE):
        record=analysis_records.save({"input":{"well_id":"W1","depth_m":100},"porosity":0.2,"lithology":"Sandstone","explanation":{"hydrocarbon_fallback_used":True},"provenance":{"well_id":"W1","dataset_id":"ds-source","source_row":2,"persisted":False}})
    app=FastAPI();app.add_middleware(OwnershipContextMiddleware)
    app.include_router(analytics.router,prefix="/analytics");app.include_router(reports.router,prefix="/reports")
    user={"value":ALICE};app.dependency_overrides[get_current_user]=lambda:user["value"]
    return TestClient(app),user,record["analysis_id"]

def test_saved_answer_cites_values_and_refuses_unsupported(evidence_client):
    c,user,key=evidence_client
    r=c.post(f"/analytics/saved/{key}/assistant",json={"question":"Summarise this result"})
    assert r.status_code==200
    data=r.json();assert data["facts"]["porosity"]["value"]==0.2
    assert "heuristic" in data["facts"]["porosity"]["method"]
    assert any(x["path"]=="porosity" and x["analysis_id"]==key for x in data["citations"])
    r=c.post(f"/analytics/saved/{key}/assistant",json={"question":"What are the field reserves?"})
    assert r.json()["facts"]=={}
    user["value"]=BOB
    assert c.post(f"/analytics/saved/{key}/assistant",json={"question":"summary"}).status_code==404

def test_report_preserves_source_and_blocks_other_owner(evidence_client):
    c,user,key=evidence_client
    payload={"source_type":"saved_analysis","source_id":key,"formats":["json"],"metadata":{"saved_analysis":{"provenance":{"well_id":"spoof"}}},"well_id":"spoof"}
    r=c.post("/reports/generate",json=payload)
    assert r.status_code in (200,201),r.text
    result=r.json();assert result["well_id"]=="W1"
    assert result["analysis"]["reservoir_intervals"]==[]
    assert result["metadata"]["saved_analysis"]["provenance"]["dataset_id"]=="ds-source"
    user["value"]=BOB
    assert c.post("/reports/generate",json=payload).status_code==404
