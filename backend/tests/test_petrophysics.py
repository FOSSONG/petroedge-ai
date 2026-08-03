from app.schemas import WellLogSample
from app.services.petrophysics import effective_porosity, permeability, water_saturation


def test_petrophysical_outputs_are_bounded():
    sample = WellLogSample(
        well_id="UNIT-01",
        depth_m=3000,
        gamma_ray_api=55,
        resistivity_ohmm=60,
        density_gcc=2.31,
        neutron_porosity_vv=0.22,
        sonic_usft=85,
        caliper_in=8.5,
    )
    assert 0 <= effective_porosity(sample) <= 0.45
    assert 0 <= water_saturation(sample) <= 1
    assert permeability(sample) > 0

