import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.config import settings
from app.core.security import create_access_token, get_current_user
from app.core.pilot_access import PilotBoundaryMiddleware
from app.db import session as db_module
from app.db.session import Base, get_db
from app.db.models import User
from app.api.routes import pilot


@pytest.fixture
def pilot_client(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings,"pilot_owner_email","owner@example.test")
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False)
    monkeypatch.setattr(db_module,"SessionLocal",sessions)
    with sessions() as db:
        for key,email,role in [("owner","owner@example.test","admin"),("customer","customer@example.test","viewer"),("other","other@example.test","admin")]:
            db.add(User(id=key,email=email,full_name=key,role=role,hashed_password="unused",is_active=True))
        db.commit()
    app=FastAPI();app.add_middleware(PilotBoundaryMiddleware);app.include_router(pilot.router,prefix="/api/v1/pilot")
    def session():
        with sessions() as db:yield db
    app.dependency_overrides[get_db]=session
    @app.get("/api/v1/private")
    def protected(user=Depends(get_current_user)):return user
    @app.get("/api/v1/legacy")
    def legacy():return {"protected_by_boundary":True}
    @app.websocket("/api/v1/legacy-ws")
    async def websocket(ws: __import__("fastapi").WebSocket):
        await ws.accept(subprotocol="petroedge")
        while True:
            await ws.receive_text()
            await ws.send_text("private event")
    with TestClient(app) as client:
        yield client,sessions
    engine.dispose()


def headers(key,role="viewer"):
    return {"Authorization":"Bearer "+create_access_token(f"{key}@example.test",[role],user_id=key)}


def test_pause_and_disable_revoke_existing_tokens(pilot_client):
    client,sessions=pilot_client;owner=headers("owner","admin");customer=headers("customer")
    assert client.get("/api/v1/private",headers=customer).status_code==200
    assert client.put("/api/v1/pilot/access",headers=customer,json={"paused":True}).status_code==403
    assert client.put("/api/v1/pilot/access",headers=owner,json={"paused":True}).status_code==200
    assert client.get("/api/v1/private",headers=customer).status_code==403
    assert client.get("/api/v1/private",headers=owner).status_code==200
    assert client.put("/api/v1/pilot/access",headers=owner,json={"paused":False}).status_code==200
    assert client.put("/api/v1/pilot/customers/customer/active",headers=owner,json={"is_active":False}).status_code==200
    assert client.get("/api/v1/private",headers=customer).status_code==401
    assert client.put("/api/v1/pilot/customers/owner/active",headers=owner,json={"is_active":False}).status_code==409


def test_sole_owner_and_legacy_boundary(pilot_client):
    client,_=pilot_client
    assert client.get("/api/v1/legacy").status_code==401
    assert client.get("/api/v1/private",headers=headers("other","admin")).status_code==403
    # Signed stale claims cannot elevate the current database role.
    response=client.get("/api/v1/private",headers=headers("customer","admin"))
    assert response.status_code==200
    assert response.json()["roles"]==["viewer"]
    assert client.post("/api/v1/pilot/customers",headers=headers("owner","admin"),json={"email":"new@example.test","full_name":"New user","password":"long-enough-test-password","role":"admin"}).status_code==422


def test_unscoped_websockets_are_owner_only(pilot_client):
    from starlette.websockets import WebSocketDisconnect
    client,_=pilot_client
    for protocols in [[],["petroedge",headers("customer")["Authorization"][7:]]]:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/api/v1/legacy-ws",subprotocols=protocols):pass
