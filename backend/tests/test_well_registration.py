from fastapi.testclient import TestClient

from app.main import create_app


def test_well_registration_route_is_present() -> None:
    paths = create_app().openapi()["paths"]
    assert "post" in paths["/api/v1/wells"]
    schema = paths["/api/v1/wells"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("/WellCreate")
