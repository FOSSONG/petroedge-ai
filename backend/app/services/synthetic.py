from __future__ import annotations

import csv
import math
import random
from pathlib import Path


def generate_samples(rows: int = 500, well_id: str = "PETROEDGE-DEMO-01") -> list[dict[str, float | str]]:
    samples: list[dict[str, float | str]] = []
    depth = 2500.0
    for i in range(rows):
        zone_signal = math.sin(i / 34.0)
        clean_sand = zone_signal > 0.35
        gamma = random.gauss(48 if clean_sand else 112, 12)
        resistivity = random.lognormvariate(3.5 if clean_sand else 1.2, 0.45)
        density = random.gauss(2.32 if clean_sand else 2.55, 0.06)
        neutron = random.gauss(0.22 if clean_sand else 0.31, 0.035)
        sonic = random.gauss(82 if clean_sand else 105, 7)
        samples.append(
            {
                "well_id": well_id,
                "depth_m": round(depth + i * 0.1524, 4),
                "gamma_ray_api": round(max(5, gamma), 3),
                "resistivity_ohmm": round(max(0.1, resistivity), 4),
                "density_gcc": round(density, 4),
                "neutron_porosity_vv": round(neutron, 4),
                "sonic_usft": round(sonic, 3),
                "caliper_in": round(random.gauss(8.6, 0.25), 3),
            }
        )
    return samples


def write_csv(path: str | Path, rows: int = 500) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    samples = generate_samples(rows)
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(samples[0].keys()))
        writer.writeheader()
        writer.writerows(samples)
    return output

