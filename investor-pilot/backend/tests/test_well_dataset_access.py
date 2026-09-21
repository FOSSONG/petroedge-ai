import io
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db.session import Base, get_db
from app.core.security import get_current_user
from app.core.ownership import OwnershipContextMiddleware
from app.api.routes import wells
from app.platform_v1 import database, datasets
from test_asset_ownership import ALICE, BOB, ADMIN, acting

@pytest.fixture
def well_client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path); database.initialise()
    engine=create_engine("sqlite://", connect_args={"check_same_thread":False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    app=FastAPI();app.add_middleware(OwnershipContextMiddleware);app.include_router(wells.router,prefix="/wells")
    def session():
        with Session(engine) as db: yield db
    user={"value":ALICE}
    app.dependency_overrides[get_db]=session
    app.dependency_overrides[get_current_user]=lambda:user["value"]
    with acting(ALICE):
        data=datasets.register_upload("Logs",None,"logs.csv",io.BytesIO(b"DEPTH,GR,well_id\n100,42,W1\n101,43,W1\n"),None,well_name="W1")
    with TestClient(app) as client:
        assert client.get("/wells").json()==[]
        assert client.post("/wells",json={"well_id":"W1","field":"Field"}).status_code==201
        yield client,user,data
    engine.dispose()

def test_real_logs_and_no_read_side_effects(well_client):
    c,user,data=well_client
    assert c.get("/wells/missing/logs").status_code==404
    assert len(c.get("/wells").json())==1
    assert c.get("/wells/W1/logs").status_code==409
    assert c.put("/wells/W1/log-dataset",json={"dataset_id":data.dataset_id}).status_code==200
    assert c.get("/wells/W1/logs?offset=1&rows=1").json()==[{"DEPTH":101,"GR":43,"well_id":"W1"}]
    assert c.get("/wells/W1/logs?emit_alerts=true").status_code==422

@pytest.mark.parametrize("suffix",["","/logs","/alerts"])
def test_private_well_reads(well_client,suffix):
    c,user,data=well_client;user["value"]=BOB
    assert c.get("/wells/W1"+suffix).status_code==404
    assert c.get("/wells").json()==[]
    assert c.delete("/wells/W1").status_code==404
    assert c.put("/wells/W1/log-dataset",json={"dataset_id":data.dataset_id}).status_code==404

def test_binding_checks_source_and_rechecks_access(well_client):
    c,user,data=well_client
    assert c.put("/wells/W1/log-dataset",json={"dataset_id":"missing"}).status_code==404
    with acting(BOB):
        other=datasets.register_upload("Other",None,"other.csv",io.BytesIO(b"DEPTH,GR\n1,2\n"),None,well_name="W1")
    assert c.put("/wells/W1/log-dataset",json={"dataset_id":other.dataset_id}).status_code==404
    with acting(ALICE):
        mixed=datasets.register_upload("Mixed",None,"mixed.csv",io.BytesIO(b"DEPTH,well_id\n1,W1\n2,W2\n"),None,well_name="W1")
    assert c.put("/wells/W1/log-dataset",json={"dataset_id":mixed.dataset_id}).status_code==422
    assert c.put("/wells/W1/log-dataset",json={"dataset_id":data.dataset_id}).status_code==200
    with database.connection() as conn:
        conn.execute("UPDATE datasets SET owner_id=? WHERE dataset_id=?",("bob-id",data.dataset_id))
    assert c.get("/wells/W1/logs").status_code==404

def test_modified_source_is_rejected(well_client):
    c,user,data=well_client
    assert c.put("/wells/W1/log-dataset",json={"dataset_id":data.dataset_id}).status_code==200
    with acting(ALICE): path=datasets.get_dataset_path(data.dataset_id)
    path.write_text("DEPTH,GR\n1,999\n",encoding="utf-8")
    assert c.get("/wells/W1/logs").status_code==409
