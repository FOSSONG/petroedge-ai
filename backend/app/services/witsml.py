from datetime import datetime, timezone


def normalize_witsml_sample(payload: dict) -> dict:
    """Normalize a minimal WITSML-like channel payload into PetroEdge curve names."""
    channels = payload.get("channels", payload)
    return {
        "well_id": payload.get("well_id", payload.get("wellUid", "WITSML-WELL")),
        "timestamp": payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "depth_m": float(channels.get("depth_m", channels.get("DEPT", 0.0))),
        "gamma_ray_api": float(channels.get("gamma_ray_api", channels.get("GR", 0.0))),
        "resistivity_ohmm": float(channels.get("resistivity_ohmm", channels.get("RT", 1.0))),
        "density_gcc": float(channels.get("density_gcc", channels.get("RHOB", 2.35))),
        "neutron_porosity_vv": float(channels.get("neutron_porosity_vv", channels.get("NPHI", 0.2))),
        "sonic_usft": float(channels.get("sonic_usft", channels.get("DT", 85.0))),
        "caliper_in": float(channels.get("caliper_in", channels.get("CALI", 8.5))),
    }

