from app.schemas import WellLogSample
from app.services.petrophysics import effective_porosity, shale_volume, water_saturation


LITHOLOGY_RULES = [
    ("shale", lambda s: s.gamma_ray_api >= 95),
    ("limestone", lambda s: s.density_gcc >= 2.55 and s.neutron_porosity_vv < 0.12),
    ("dolomite", lambda s: s.density_gcc >= 2.68),
    ("sandstone", lambda s: s.gamma_ray_api < 75 and s.density_gcc < 2.55),
]


def hydrocarbon_probability(sample: WellLogSample) -> float:
    phi = effective_porosity(sample)
    sw = water_saturation(sample)
    vsh = shale_volume(sample.gamma_ray_api)
    resistivity_signal = min(sample.resistivity_ohmm / 80.0, 1.0)
    score = 0.42 * (1 - sw) + 0.28 * phi / 0.35 + 0.2 * resistivity_signal + 0.1 * (1 - vsh)
    return round(max(0.0, min(1.0, score)), 4)


def classify_lithology(sample: WellLogSample) -> str:
    for lithology, predicate in LITHOLOGY_RULES:
        if predicate(sample):
            return lithology
    return "siltstone"


def predict_facies(sample: WellLogSample) -> str:
    hc = hydrocarbon_probability(sample)
    lithology = classify_lithology(sample)
    if lithology == "sandstone" and hc > 0.62:
        return "hydrocarbon-bearing clean sand"
    if lithology == "sandstone":
        return "water-bearing sand"
    if lithology == "shale":
        return "marine shale"
    if lithology in {"limestone", "dolomite"}:
        return "carbonate platform"
    return "heterolithic interval"


def anomaly_score(sample: WellLogSample) -> float:
    score = 0.0
    if sample.gamma_ray_api > 180:
        score += 0.25
    if sample.resistivity_ohmm > 500 or sample.resistivity_ohmm < 0.2:
        score += 0.25
    if sample.density_gcc < 1.9 or sample.density_gcc > 2.9:
        score += 0.2
    if sample.caliper_in > 12:
        score += 0.2
    if sample.sonic_usft > 180:
        score += 0.1
    return round(min(1.0, score), 4)

