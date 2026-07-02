import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def token() -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin@petroedge.ai", "password": "petroedge123", "mfa_code": "123456"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_analyze_sample():
    response = client.post(
        "/api/v1/analytics/sample",
        headers={"Authorization": f"Bearer {token()}"},
        json={
            "well_id": "TEST-01",
            "depth_m": 3000,
            "gamma_ray_api": 45,
            "resistivity_ohmm": 90,
            "density_gcc": 2.28,
            "neutron_porosity_vv": 0.21,
            "sonic_usft": 82,
            "caliper_in": 8.5,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["hydrocarbon_probability"] > 0.5
    assert body["porosity"] > 0
