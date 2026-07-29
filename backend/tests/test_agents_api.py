from fastapi.testclient import TestClient

from app.main import create_app


def test_agent_routes_are_present_in_openapi() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]
        assert "/api/v1/agents" in paths
        assert "/api/v1/agents/panel/run" in paths
        assert "/api/v1/agents/{agent_key}" in paths
        assert "/api/v1/agents/{agent_key}/run" in paths