import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.routes import agents
from test_asset_ownership import assets, ALICE, BOB

@pytest.mark.parametrize("endpoint", ["/agents/geologist/run", "/agents/panel/run"])
def test_sources_authorized_and_scores_not_fabricated(assets, endpoint):
    a, b, legacy, client, user = assets
    client.app.include_router(agents.router, prefix="/agents")
    for dataset in (b, legacy):
        assert client.post(endpoint, json={"dataset_id":dataset.dataset_id}).status_code == 404
    result = client.post(endpoint, json={"dataset_id":a.dataset_id}).json()
    assert result["status"] == "measured_evidence"
    assert result["analysis_performed"] is True
    assert result["confidence"] is None
    if "agents" in result:
        assert result["agreement_percent"] is None
        assert all(len(r["evidence"]) == 2 and r["confidence"] is None for r in result["agents"])
    else:
        assert len(result["evidence"]) == 2
    assert client.post(endpoint, json={"well_id":"unverified"}).status_code == 422
    assert client.post(endpoint, json={"top_depth":100, "bottom_depth":50}).status_code == 422

@pytest.mark.parametrize("method,path", [("get","/agents"),("get","/agents/geologist"),("post","/agents/geologist/run"),("post","/agents/panel/run")])
def test_authentication_required(method,path):
    app=FastAPI();app.include_router(agents.router,prefix="/agents")
    with TestClient(app) as client:
        response=client.request(method,path,**({"json":{}} if method=="post" else {}))
        assert response.status_code in (401,403)
