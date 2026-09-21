def hydrocarbon_probability(
    gamma_ray: float,
    resistivity: float
) -> float:

    score = (
        (150 - gamma_ray) / 150
    ) * (
        resistivity / 150
    )

    score = max(
        0,
        min(score, 1)
    )

    return round(score, 3)


def shale_volume(
    gamma_ray: float
) -> float:

    vsh = gamma_ray / 150

    return round(
        max(0, min(vsh, 1)),
        3,
    )


def effective_porosity(
    sample
) -> float:

    if hasattr(sample, "neutron_porosity_vv"):

        return round(
            float(sample.neutron_porosity_vv),
            3,
        )

    return 0.25


def water_saturation(
    sample
) -> float:

    rt = max(
        sample.resistivity_ohmm,
        0.1,
    )

    sw = (20 / rt) ** 0.5

    return round(
        max(0, min(sw, 1)),
        3,
    )

def permeability(sample) -> float:
    """Estimate permeability in millidarcies using a bounded Timur-style proxy."""
    phi = max(0.01, min(float(effective_porosity(sample)), 0.45))
    sw = max(0.05, min(float(water_saturation(sample)), 1.0))
    value = 1000.0 * (phi ** 4.4) / (sw ** 2.0)
    return round(max(0.0, min(value, 10000.0)), 3)
