from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
def test_monitoring_does_not_import_model_route():
    source = (BACKEND_ROOT / "app/api/routes/monitoring.py").read_text(encoding="utf-8")
    assert "app.api.routes.models" not in source
    assert "discover_model_statuses" in source


def test_runtime_services_do_not_load_models_directly():
    runtime_files = [
        (BACKEND_ROOT / "app/services/analytics.py"),
        (BACKEND_ROOT / "app/services/ml_inference.py"),
        (BACKEND_ROOT / "app/services/shap_service.py"),
    ]
    for path in runtime_files:
        source = path.read_text(encoding="utf-8")
        assert "joblib.load" not in source


def test_platform_route_tuple_is_well_formed():
    from app.main import ROUTE_MODULES

    assert all(len(item) == 4 for item in ROUTE_MODULES)
    names = [item[0] for item in ROUTE_MODULES]
    assert "monitoring" in names
    assert "platform" in names
