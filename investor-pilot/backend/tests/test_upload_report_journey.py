from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db.session import Base,get_db
from app.core.security import get_current_user
from app.core.ownership import OwnershipContextMiddleware
from app.api.routes import platform,wells,analytics,reports
from app.platform_v1 import database
from app.services import report_service
from test_asset_ownership import ALICE,BOB,ADMIN

def test_upload_to_download_with_roles_and_stale_binding(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path);database.initialise()
    report_root=tmp_path/"reports";report_root.mkdir()
    monkeypatch.setattr(report_service,"REPORT_ROOT",report_root);monkeypatch.setattr(reports,"REPORT_ROOT",report_root);monkeypatch.setattr(report_service,"_report_service",None)
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    def db():
        with Session(engine) as session:yield session
    app=FastAPI();app.add_middleware(OwnershipContextMiddleware)
    for router,prefix in [(platform.router,""),(wells.router,"/wells"),(analytics.router,"/analytics"),(reports.router,"/reports")]:app.include_router(router,prefix=prefix)
    user={"value":ALICE};app.dependency_overrides[get_current_user]=lambda:user["value"];app.dependency_overrides[get_db]=db
    with TestClient(app) as c:
        r=c.post("/platform/datasets",data={"name":"Journey logs","well_name":"J1","dataset_type":"well_log"},files={"file":("journey.csv",b"D,G,R,B,N,S,C\n100,40,20,2.5,0.2,60,10\n101,50,30,2.6,0.3,70,11\n","text/csv")})
        assert r.status_code==201,r.text
        dataset=r.json();assert dataset["owner_id"]=="alice-id"
        assert c.post("/wells",json={"well_id":"J1","field":"Test field"}).status_code==201
        names=["depth_m","gamma_ray_api","resistivity_ohmm","density_gcc","neutron_porosity_vv","sonic_usft","caliper_in"]
        units=["m","API","ohm.m","g/cm3","v/v","us/ft","in"]
        binding={"dataset_id":dataset["dataset_id"],"mapping":{"depth_reference":"MD","curves":{k:{"source":col,"unit":unit} for k,col,unit in zip(names,"DGRBNSC",units)}}}
        assert c.put("/wells/J1/log-dataset",json=binding).status_code==200
        row=c.get("/wells/J1/logs?mapped=true&offset=1&rows=1").json()[0]
        request={"source_row":row["source_row"],"binding_sha256":row["binding_sha256"]}
        r=c.post("/wells/J1/analyze-row",json=request);assert r.status_code==200,r.text
        result=r.json();key=result["analysis_id"]
        assert result["input"]["depth_m"]==101
        assert result["provenance"]["dataset_id"]==dataset["dataset_id"]
        assert result["provenance"]["checksum_sha256"]==dataset["checksum_sha256"]
        assert "methodology" in result["explanation"]
        assert c.get(f"/analytics/saved/{key}").json()==result
        answer=c.post(f"/analytics/saved/{key}/assistant",json={"question":"Summarise this result"}).json()
        assert answer["facts"]["porosity"]["value"]==result["porosity"]
        payload={"source_type":"saved_analysis","source_id":key,"formats":["json","html"],"include_raw_records":True}
        r=c.post("/reports/generate",json=payload);assert r.status_code in (200,201),r.text
        report=r.json();rid=report["report_id"]
        download=c.get(f"/reports/{rid}/download?format=json");assert download.status_code==200
        assert download.json()["metadata"]["saved_analysis"]["analysis_id"]==key
        html=c.get(f"/reports/{rid}/download?format=html");assert html.status_code==200
        assert key in html.text and "heuristic" in html.text
        binding["mapping"]["depth_reference"]="TVD"
        assert c.put("/wells/J1/log-dataset",json=binding).status_code==200
        assert c.post("/wells/J1/analyze-row",json=request).status_code==409
        assert c.get(f"/analytics/saved/{key}").json()==result
        user["value"]={**ALICE,"roles":["viewer"]}
        assert c.get(f"/analytics/saved/{key}").status_code==200
        assert c.post("/reports/generate",json=payload).status_code==403
        assert c.put("/wells/J1/log-dataset",json=binding).status_code==403
        user["value"]=BOB
        for url in [f"/platform/datasets/{dataset['dataset_id']}","/wells/J1",f"/analytics/saved/{key}",f"/reports/{rid}/download?format=html"]:
            assert c.get(url).status_code==404,url
        assert c.get("/analytics/saved").json()==[]
        user["value"]=ADMIN
        assert c.get(f"/analytics/saved/{key}").status_code==200
        assert c.get(f"/reports/{rid}/download?format=json").status_code==200
    engine.dispose()
