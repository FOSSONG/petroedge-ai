from app.schemas import WellLogSample
from app.services.petrophysics import effective_porosity, shale_volume, water_saturation


def explain_prediction(sample: WellLogSample) -> dict[str, float | str]:
    phi = effective_porosity(sample)
    sw = water_saturation(sample)
    vsh = shale_volume(sample.gamma_ray_api)
    driver = "resistivity and low water saturation" if sample.resistivity_ohmm > 30 and sw < 0.55 else "lithology and porosity"
    return {
        "primary_driver": driver,
        "porosity_contribution": round(phi / 0.35, 4),
        "water_saturation_contribution": round(1 - sw, 4),
        "shale_volume_contribution": round(1 - vsh, 4),
        "resistivity_contribution": round(min(sample.resistivity_ohmm / 80.0, 1.0), 4),
    }

