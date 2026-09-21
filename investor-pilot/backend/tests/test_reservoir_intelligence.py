from app.api.routes.models import _discover_models
from app.services.reservoir_intelligence import ReservoirIntelligenceRequest, analyse_reservoir_interval


def request(**overrides):
    payload = {
        "well_id": "DEMO-01",
        "depth_m": 2500.0,
        "gamma_ray_api": 42.0,
        "resistivity_ohmm": 45.0,
        "density_gcc": 2.22,
        "neutron_porosity_vv": 0.12,
        "sonic_usft": 92.0,
        "caliper_in": 8.5,
        "porosity": 0.22,
        "water_saturation": 0.28,
        "shale_volume": 0.16,
        "permeability_md": 180.0,
    }
    payload.update(overrides)
    return ReservoirIntelligenceRequest(**payload)


def test_registry_compatibility():
    assert isinstance(_discover_models(), list)


def test_fluid_hierarchy():
    response = analyse_reservoir_interval(request())
    assert response.primary_fluid in {"water", "oil", "gas", "oil_and_gas", "uncertain"}
    assert set(response.fluid_probabilities) >= {"water", "oil", "gas", "oil_and_gas"}
    assert abs(sum(response.fluid_probabilities.values()) - 1.0) < 1e-4


def test_water_zone():
    response = analyse_reservoir_interval(request(resistivity_ohmm=1.4, water_saturation=0.92, density_gcc=2.48, neutron_porosity_vv=0.30))
    assert response.primary_fluid == "water"
    assert response.pay_zone == "water_zone"