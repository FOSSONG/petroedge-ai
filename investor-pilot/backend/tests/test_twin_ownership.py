import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.ownership import OwnershipContextMiddleware
from app.core.security import get_current_user
from app.digital_twin.registry import twin_registry
from app.digital_twin.history import twin_history
from app.api.routes import twins, twin_workspace
from test_asset_ownership import ALICE, BOB, ADMIN

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(twin_registry, "_states", {})
    monkeypatch.setattr(twin_history, "_snapshots", {})
    app = FastAPI()
    app.add_middleware(OwnershipContextMiddleware)
    app.include_router(twins.router, prefix="/twins")
    app.include_router(twin_workspace.router, prefix="/workspace")
    user = {"value": ALICE}
    app.dependency_overrides[get_current_user] = lambda: user["value"]
    with TestClient(app) as c:
        r = c.post("/twins", json={"reservoir_id":"private-ownership-test", "name":"Private", "metadata":{"owner_id":"bob-id"}})
        assert r.status_code == 201
        assert r.json()["owner_id"] == "alice-id"
        yield c, user

@pytest.mark.parametrize("suffix", ["", "/health", "/history"])
def test_other_user_cannot_read(client, suffix):
    c, user = client
    user["value"] = BOB
    assert c.get("/twins/private-ownership-test" + suffix).status_code == 404
    assert c.get("/twins").json()["twins"] == []
    assert c.get("/workspace/private-ownership-test/summary").status_code == 404

@pytest.mark.parametrize("action", ["update", "restore", "simulate"])
def test_other_user_cannot_mutate(client, action):
    c, user = client
    user["value"] = BOB
    path = "/twins/private-ownership-test"
    if action == "update": r = c.patch(path, json={"reservoir":{"name":"Stolen"}})
    elif action == "restore": r = c.post(path + "/restore/1")
    else: r = c.post(path + "/simulate", json={"changes":[], "persist":True})
    assert r.status_code == 404
    user["value"] = ALICE
    assert c.get(path).json()["name"] == "Private"

def test_owner_immutable_and_admin_access(client):
    c, user = client
    path = "/twins/private-ownership-test"
    r = c.patch(path, json={"reservoir":{"owner_id":"bob-id", "name":"Updated"}})
    assert r.status_code == 200 and r.json()["owner_id"] == "alice-id"
    r = c.post(path + "/simulate", json={"changes":[{"path":"owner_id", "value":"bob-id"}], "persist":True})
    assert r.status_code == 422
    assert c.post(path + "/restore/1").status_code == 200
    user["value"] = ADMIN
    assert c.get(path).status_code == 200
    assert c.delete(path).status_code == 204
    assert c.post(path + "/restore/1").status_code == 404

def test_reused_id_does_not_expose_previous_history(client):
    c, user = client
    path = "/twins/private-ownership-test"
    user["value"] = ADMIN
    assert c.delete(path).status_code == 204
    user["value"] = BOB
    assert c.post("/twins", json={"reservoir_id":"private-ownership-test", "name":"New"}).status_code == 201
    snapshots = c.get(path + "/history").json()["snapshots"]
    assert len(snapshots) == 1 and snapshots[0]["state"]["owner_id"] == "bob-id"
    assert c.post(path + "/restore/1").status_code == 404
