import secrets
import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.models import User, UserRole
from app.db.session import Base, get_db
from app.main import create_app


@pytest.fixture
def api_fixture():
    # Use a disposable database and a real account; never rely on release credentials.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    password = secrets.token_urlsafe(24)
    email = "api-test@example.invalid"
    with sessions() as session:
        session.add(User(email=email, full_name="API Test", hashed_password=hash_password(password),
                         role=UserRole.ADMIN.value, is_active=True))
        session.commit()
    application = create_app()
    def test_db():
        with sessions() as session:
            yield session
    application.dependency_overrides[get_db] = test_db
    # Lifecycle startup has its own smoke test against migrated disposable storage.
    client = TestClient(application)
    try:
        yield client, email, password
    finally:
        client.close()
        application.dependency_overrides.clear()
        engine.dispose()


def token(api_fixture):
    client, email, password = api_fixture
    response = client.post("/api/v1/auth/login", json={"username": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_health(api_fixture):
    client, _, _ = api_fixture
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_login_rejects_wrong_password(api_fixture):
    client, email, _ = api_fixture
    response = client.post("/api/v1/auth/login", json={"username": email, "password": "incorrect-test-password"})
    assert response.status_code == 401


def test_analyze_sample(api_fixture):
    client, _, _ = api_fixture
    response = client.post(
        "/api/v1/analytics/sample",
        headers={"Authorization": f"Bearer {token(api_fixture)}"},
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

