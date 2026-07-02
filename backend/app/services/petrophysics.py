import math

from app.schemas import WellLogSample


def shale_volume(gamma_ray_api: float, clean_sand_gr: float = 25.0, shale_gr: float = 125.0) -> float:
    igr = (gamma_ray_api - clean_sand_gr) / max(shale_gr - clean_sand_gr, 1e-6)
    return max(0.0, min(1.0, igr))


def density_porosity(density_gcc: float, matrix_density: float = 2.65, fluid_density: float = 1.0) -> float:
    porosity = (matrix_density - density_gcc) / max(matrix_density - fluid_density, 1e-6)
    return max(0.0, min(0.45, porosity))


def effective_porosity(sample: WellLogSample) -> float:
    density_phi = density_porosity(sample.density_gcc)
    neutron_phi = max(0.0, min(0.45, sample.neutron_porosity_vv))
    return round((density_phi + neutron_phi) / 2.0, 4)


def water_saturation(sample: WellLogSample, rw: float = 0.08, a: float = 1.0, m: float = 2.0, n: float = 2.0) -> float:
    phi = max(effective_porosity(sample), 0.03)
    rt = max(sample.resistivity_ohmm, 0.1)
    sw = ((a * rw) / (rt * (phi**m))) ** (1.0 / n)
    return round(max(0.0, min(1.0, sw)), 4)


def net_to_gross(sample: WellLogSample) -> float:
    vsh = shale_volume(sample.gamma_ray_api)
    phi = effective_porosity(sample)
    sw = water_saturation(sample)
    is_net = vsh < 0.45 and phi > 0.08 and sw < 0.65
    return 1.0 if is_net else 0.0


def permeability(sample: WellLogSample) -> float:
    phi = max(effective_porosity(sample), 0.01)
    swirr = max(water_saturation(sample), 0.05)
    k = 250.0 * (phi**3) / (swirr**2)
    return round(max(0.01, min(10000.0, k)), 3)


def reservoir_quality_index(sample: WellLogSample) -> float:
    phi = effective_porosity(sample)
    k = permeability(sample)
    return round(0.0314 * math.sqrt(k / max(phi, 0.01)), 4)

