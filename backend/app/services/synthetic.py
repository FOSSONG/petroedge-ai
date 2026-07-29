from datetime import datetime, timezone

import random


def generate_samples(
    rows: int = 100,
    well_id: str = "PETROEDGE-DEMO-01",
):

    samples = []

    for i in range(rows):

        samples.append(
    {
        "well_id": well_id,

        "depth_m": 1000 + i,

        "gamma_ray_api": round(
            random.uniform(20, 120),
            2,
        ),

        "resistivity_ohmm": round(
            random.uniform(1, 200),
            2,
        ),

        "density_gcc": round(
            random.uniform(2.0, 2.8),
            2,
        ),

        "neutron_porosity_vv": round(
            random.uniform(0.05, 0.35),
            3,
        ),

        "sonic_usft": round(
            random.uniform(40, 120),
            2,
        ),

        "caliper_in": round(
            random.uniform(8.0, 12.0),
            2,
        ),

        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }
)

    return samples