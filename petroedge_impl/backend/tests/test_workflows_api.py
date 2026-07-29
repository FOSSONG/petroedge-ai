from fastapi.testclient import TestClient

from app.main import create_app


def test_workflow_routes_are_present_in_openapi() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]
        assert "/api/v1/workflows" in paths
        assert "/api/v1/workflows/templates" in paths
        assert "/api/v1/workflows/nodes" in paths
        assert "/api/v1/workflows/{workflow_id}/run" in paths
        assert "/api/v1/workflows/runs/{run_id}" in paths