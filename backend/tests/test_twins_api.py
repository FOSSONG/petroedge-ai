from fastapi.testclient import TestClient

from app.main import create_app


def test_twin_routes_are_present_in_openapi() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]

    assert "/api/v1/twins" in paths
    assert "/api/v1/twins/{reservoir_id}" in paths
    assert "/api/v1/twins/{reservoir_id}/health" in paths
    assert "/api/v1/twins/{reservoir_id}/history" in paths
    assert "/api/v1/twins/{reservoir_id}/simulate" in paths