from pathlib import Path

import numpy as np


def parse_las(
    path: str | Path,
    max_records: int = 500,
):

    try:
        import lasio
    except ImportError as exc:
        raise RuntimeError("LAS support requires the optional dependency 'lasio'.") from exc

    las = lasio.read(path)

    depth = las["DEPTH"]

    gamma_ray = las["GR_COMP"]

    resistivity = las["RDEEP_COMP"]

    density = las["RHOB_COMP"]

    neutron = las["NPHI_COMP"]

    sonic = las["DT_COMP"]

    rows = []

    limit = min(
        len(depth),
        max_records
    )

    for i in range(limit):

        rows.append(
            {
                "well_id": Path(path).stem,

                "depth_m": float(depth[i]),

                "gamma_ray_api": float(
                    np.nan_to_num(
                        gamma_ray[i]
                    )
                ),

                "resistivity_ohmm": float(
                    np.nan_to_num(
                        resistivity[i]
                    )
                ),

                "density_gcc": float(
                    np.nan_to_num(
                        density[i]
                    )
                ),

                "neutron_porosity_vv": float(
                    np.nan_to_num(
                        neutron[i]
                    )
                ),

                "sonic_usft": float(
                    np.nan_to_num(
                        sonic[i]
                    )
                ),

                "caliper_in": 8.5,
            }
        )

    return rows