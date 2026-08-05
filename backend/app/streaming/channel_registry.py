from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ChannelDefinition:
    canonical_name: str
    aliases: tuple[str, ...]
    canonical_unit: str
    quantity: str
    minimum: float | None = None
    maximum: float | None = None
    required_for_live_inference: bool = False


CHANNELS: Final[tuple[ChannelDefinition, ...]] = (
    ChannelDefinition("depth_m", ("DEPTH", "DEPT", "MD", "MDEPTH", "MEASURED_DEPTH"), "m", "length", 0.0, 15000.0, True),
    ChannelDefinition("gamma_ray_api", ("GR", "GR_COMP", "GAMMA", "GAMMA_RAY"), "API", "gamma_ray", 0.0, 300.0, True),
    ChannelDefinition("resistivity_ohmm", ("RT", "RT_COMP", "ILD", "LLD", "RES", "RESISTIVITY"), "ohm.m", "resistivity", 0.001, 100000.0, True),
    ChannelDefinition("density_gcc", ("RHOB", "RHOB_COMP", "DEN", "DENSITY"), "g/cm3", "density", 1.0, 4.0, False),
    ChannelDefinition("neutron_porosity_vv", ("NPHI", "NPHI_COMP", "NEUTRON"), "v/v", "porosity", -0.2, 1.0, False),
    ChannelDefinition("sonic_usft", ("DT", "DTC", "SONIC"), "us/ft", "slowness", 20.0, 400.0, False),
    ChannelDefinition("caliper_in", ("CALI", "CALIPER"), "in", "diameter", 3.0, 36.0, False),
    ChannelDefinition("standpipe_pressure_psi", ("SPP", "STANDPIPE_PRESSURE"), "psi", "pressure", 0.0, 20000.0, False),
    ChannelDefinition("annular_pressure_psi", ("ANNP", "ANNULAR_PRESSURE"), "psi", "pressure", 0.0, 20000.0, False),
    ChannelDefinition("mud_temperature_c", ("MUD_TEMP", "MUD_TEMPERATURE", "TEMP"), "degC", "temperature", -20.0, 250.0, False),
    ChannelDefinition("flow_in_gpm", ("FLOW_IN", "FLOWIN", "QIN"), "gpm", "flow", 0.0, 5000.0, False),
    ChannelDefinition("flow_out_gpm", ("FLOW_OUT", "FLOWOUT", "QOUT"), "gpm", "flow", 0.0, 5000.0, False),
    ChannelDefinition("pit_volume_bbl", ("PIT_VOLUME", "PIT_VOL", "PVT"), "bbl", "volume", 0.0, 100000.0, False),
    ChannelDefinition("rop_mph", ("ROP", "RATE_OF_PENETRATION"), "m/h", "rate", 0.0, 1000.0, False),
    ChannelDefinition("wob_klbf", ("WOB", "WEIGHT_ON_BIT"), "klbf", "force", 0.0, 500.0, False),
    ChannelDefinition("rpm", ("RPM", "ROTARY_SPEED"), "rpm", "rotation", 0.0, 500.0, False),
    ChannelDefinition("torque_klbf_ft", ("TORQUE", "TQ"), "klbf.ft", "torque", 0.0, 200.0, False),
)


def _key(value: str) -> str:
    return "".join(ch for ch in str(value).upper() if ch.isalnum())


_BY_NAME: dict[str, ChannelDefinition] = {}
for definition in CHANNELS:
    _BY_NAME[_key(definition.canonical_name)] = definition
    for alias in definition.aliases:
        _BY_NAME[_key(alias)] = definition


def resolve_channel(name: str) -> ChannelDefinition | None:
    return _BY_NAME.get(_key(name))


def registry_payload() -> list[dict[str, object]]:
    return [
        {
            "canonical_name": item.canonical_name,
            "aliases": list(item.aliases),
            "canonical_unit": item.canonical_unit,
            "quantity": item.quantity,
            "minimum": item.minimum,
            "maximum": item.maximum,
            "required_for_live_inference": item.required_for_live_inference,
        }
        for item in CHANNELS
    ]
