from app.schemas import WellLogSample


RANGES = {
    "gamma_ray_api": (0.0, 250.0),
    "resistivity_ohmm": (0.05, 2000.0),
    "density_gcc": (1.75, 3.1),
    "neutron_porosity_vv": (-0.15, 0.65),
    "sonic_usft": (35.0, 220.0),
    "caliper_in": (5.5, 18.0),
}


def quality_score(sample: WellLogSample) -> float:
    passed = 0
    for field, (lower, upper) in RANGES.items():
        value = getattr(sample, field)
        if lower <= value <= upper:
            passed += 1
    borehole_penalty = 0.1 if sample.caliper_in > 10.5 else 0.0
    return round(max(0.0, passed / len(RANGES) - borehole_penalty), 3)


def qc_flags(sample: WellLogSample) -> list[str]:
    flags: list[str] = []
    for field, (lower, upper) in RANGES.items():
        value = getattr(sample, field)
        if value < lower or value > upper:
            flags.append(f"{field} outside expected range")
    if sample.caliper_in > 10.5:
        flags.append("possible washout from elevated caliper")
    return flags

