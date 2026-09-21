import io
from types import SimpleNamespace
import pytest
from app.platform_v1 import datasets
from test_well_dataset_access import well_client
from test_asset_ownership import acting, ALICE, BOB

@pytest.fixture
def bound(well_client, monkeypatch):
    c,user,_=well_client
    with acting(ALICE):
        data=datasets.register_upload("Complete",None,"full.csv",io.BytesIO(b"D,G,R,B,N,S,C\n100,40,20,2.5,0.2,60,10\n101,50,30,2.6,0.3,70,11\n"),None,well_name="W1")
    names=["depth_m","gamma_ray_api","resistivity_ohmm","density_gcc","neutron_porosity_vv","sonic_usft","caliper_in"]
    units=["m","API","ohm.m","g/cm3","v/v","us/ft","in"]
    payload={"dataset_id":data.dataset_id,"mapping":{"depth_reference":"MD","curves":{n:{"source":s,"unit":u} for n,s,u in zip(names,"DGRBNSC",units)}}}
    assert c.put("/wells/W1/log-dataset",json=payload).status_code==200
    rows=c.get("/wells/W1/logs?mapped=true&offset=1&rows=1").json()
    calls=[]
    def analyze(sample):
        calls.append(sample.model_dump())
        return SimpleNamespace(model_dump=lambda:{"input":sample.model_dump(),"lithology":"test"})
    monkeypatch.setattr("app.services.analytics.analyze_sample",analyze)
    return c,user,data,payload,rows[0],calls

def request(row):
    return {"source_row":row["source_row"],"binding_sha256":row["binding_sha256"]}

def test_server_input_and_provenance(bound):
    c,user,data,payload,row,calls=bound
    assert row["source_row"]==1
    r=c.post("/wells/W1/analyze-row",json=request(row))
    assert r.status_code==200
    assert calls[0]["gamma_ray_api"]==50 and calls[0]["depth_m"]==101
    p=r.json()["provenance"]
    assert p["dataset_id"]==data.dataset_id and p["version_id"]==data.version_id
    assert p["checksum_sha256"]==data.checksum_sha256
    assert p["mapping"]["depth_reference"]=="MD" and p["source_row"]==1
    assert len(p["input_sha256"])==64 and p["persisted"] is True

def test_client_measurements_rejected(bound):
    c,_,_,_,row,calls=bound
    assert c.post("/wells/W1/analyze-row",json={**request(row),"gamma_ray_api":999}).status_code==422
    assert calls==[]

def test_stale_binding_and_invalid_row(bound):
    c,_,_,payload,row,calls=bound
    assert c.post("/wells/W1/analyze-row",json={**request(row),"source_row":99}).status_code==404
    payload["mapping"]["depth_reference"]="TVD"
    assert c.put("/wells/W1/log-dataset",json=payload).status_code==200
    assert c.post("/wells/W1/analyze-row",json=request(row)).status_code==409
    current=c.get("/wells/W1/logs?mapped=true").json()[0]
    assert c.post("/wells/W1/analyze-row",json=request(current)).status_code==422
    assert calls==[]

def test_ownership_and_source_change_checked_before_inference(bound):
    c,user,data,_,row,calls=bound
    user["value"]=BOB
    assert c.post("/wells/W1/analyze-row",json=request(row)).status_code==404
    user["value"]=ALICE
    with acting(ALICE): path=datasets.get_dataset_path(data.dataset_id)
    path.write_text("D,G\n1,2\n",encoding="utf-8")
    assert c.post("/wells/W1/analyze-row",json=request(row)).status_code==409
    assert calls==[]
