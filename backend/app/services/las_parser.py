from pathlib import Path


CURVE_MAP = {
    "DEPT": "depth_m",
    "DEPTH": "depth_m",
    "GR": "gamma_ray_api",
    "RT": "resistivity_ohmm",
    "ILD": "resistivity_ohmm",
    "RHOB": "density_gcc",
    "NPHI": "neutron_porosity_vv",
    "DT": "sonic_usft",
    "CALI": "caliper_in",
}


def parse_las(path: str | Path, max_records: int | None = None) -> list[dict[str, float | str]]:
    las_path = Path(path)
    if not las_path.exists():
        raise FileNotFoundError(f"LAS file not found: {las_path}")

    curves: list[str] = []
    data_started = False
    records: list[dict[str, float | str]] = []

    for raw_line in las_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        upper = line.upper()
        if upper.startswith("~CURVE"):
            data_started = False
            continue
        if upper.startswith("~ASCII"):
            data_started = True
            continue
        if upper.startswith("~"):
            data_started = False
            continue

        if not data_started and "." in line:
            mnemonic = line.split(".", 1)[0].strip().upper()
            if mnemonic in CURVE_MAP:
                curves.append(CURVE_MAP[mnemonic])
            continue

        if data_started:
            values = line.split()
            if not values:
                continue
            row: dict[str, float | str] = {"well_id": las_path.stem.upper()}
            for index, value in enumerate(values[: len(curves)]):
                try:
                    row[curves[index]] = float(value)
                except (ValueError, IndexError):
                    continue
            if "caliper_in" not in row:
                row["caliper_in"] = 8.5
            records.append(row)
            if max_records and len(records) >= max_records:
                break

    return records

