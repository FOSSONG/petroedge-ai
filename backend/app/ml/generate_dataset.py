import numpy as np
import pandas as pd

np.random.seed(42)

N = 100000

rows = []

for i in range(N):

    gamma_ray = np.random.uniform(15, 140)

    gamma_ray += np.random.normal(0, 10)

    resistivity = np.random.uniform(1, 150)

    resistivity += np.random.normal(0, 5)

    density = np.random.uniform(1.95, 2.85)

    neutron_porosity = np.random.uniform(
        0.05,
        0.35
    )

    neutron_porosity += np.random.normal(
    0,
    0.02
)

    sonic = np.random.uniform(
        45,
        140
    )

    caliper = np.random.uniform(
        8.0,
        10.0
    )

    depth = np.random.uniform(
        1000,
        4500
    )

    # -------------------------------------
    # Lithology
    # -------------------------------------

    if gamma_ray < 45:

        lithology = np.random.choice(
            ["Sandstone", "Silty Sand"],
            p=[0.85, 0.15]
        )

    elif gamma_ray < 85:

        lithology = np.random.choice(
            ["Silty Sand", "Shale"],
            p=[0.70, 0.30]
        )

    else:

        lithology = np.random.choice(
            ["Shale", "Silty Sand"],
            p=[0.90, 0.10]
        )

    # -------------------------------------
    # Hydrocarbon probability
    # -------------------------------------

    signal = (
        0.015 * resistivity
        - 0.020 * gamma_ray
        + 2.0 * neutron_porosity
        - 1.5
    )

    probability = (
        1 /
        (1 + np.exp(-signal))
    )

    hydrocarbon = (
        np.random.rand() < probability
    )

    rows.append(
        [
            depth,
            gamma_ray,
            resistivity,
            density,
            neutron_porosity,
            sonic,
            caliper,
            lithology,
            int(hydrocarbon)
        ]
    )

df = pd.DataFrame(
    rows,
    columns=[
        "depth_m",
        "gamma_ray_api",
        "resistivity_ohmm",
        "density_gcc",
        "neutron_porosity_vv",
        "sonic_usft",
        "caliper_in",
        "lithology",
        "hydrocarbon"
    ]
)

df.to_csv(
    "data/niger_delta_synthetic.csv",
    index=False
)

print(df.head())

print()
print("Saved 100000 rows.")