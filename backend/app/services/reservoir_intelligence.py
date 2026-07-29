from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ml_platform.registry import get_model_registry
from app.ml_platform.schemas import InferenceRequest, ModelTask
from app.ml_platform.service import get_model_service

FluidLabel = Literal["water", "oil", "gas", "oil_and_gas", "uncertain"]


class ReservoirIntelligenceRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    well_id: str = Field(min_length=1, max_length=150)
    depth_m: float = Field(ge=0)
    gamma_ray_api: float = Field(ge=0)
    resistivity_ohmm: float = Field(gt=0)
    density_gcc: float = Field(gt=0)
    neutron_porosity_vv: float = Field(ge=-0.15, le=1.0)
    sonic_usft: float = Field(gt=0)
    caliper_in: float = Field(gt=0)
    porosity: float | None = Field(default=None, ge=0, le=1)
    water_saturation: float | None = Field(default=None, ge=0, le=1)
    shale_volume: float | None = Field(default=None, ge=0, le=1)
    permeability_md: float | None = Field(default=None, ge=0)
    hydrocarbon_model_id: str | None = None
    fluid_model_id: str | None = None


class ReservoirIntelligenceResponse(BaseModel):
    well_id: str
    depth_m: float
    primary_fluid: FluidLabel
    fluid_probabilities: dict[str, float]
    fluid_confidence: float
    fluid_method: Literal["registered_ai_model", "physics_informed_fallback"]
    fluid_model_id: str | None = None
    hydrocarbon_probability: float
    hydrocarbon_model_id: str | None = None
    reservoir_quality: Literal["excellent", "good", "moderate", "poor"]
    pay_zone: Literal["net_pay", "transition_zone", "water_zone", "tight_reservoir", "non_pay", "uncertain"]
    evidence: list[str]
    advisory_actions: list[str]
    limitations: list[str]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _softmax(scores: dict[str, float]) -> dict[str, float]:
    maximum = max(scores.values())
    values = {key: math.exp(value - maximum) for key, value in scores.items()}
    total = sum(values.values()) or 1.0
    return {key: value / total for key, value in values.items()}


def _normalise_label(value: Any) -> str:
    label = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "brine": "water",
        "formation_water": "water",
        "hydrocarbon_oil": "oil",
        "hydrocarbon_gas": "gas",
        "oil_gas": "oil_and_gas",
        "gas_oil": "oil_and_gas",
        "mixed": "oil_and_gas",
    }
    return aliases.get(label, label)


def _hydrocarbon_probability(record: dict[str, Any], model_id: str | None) -> tuple[float, str | None]:
    try:
        response = get_model_service().infer(
            InferenceRequest(task=ModelTask.hydrocarbon_classification, model_id=model_id, records=[record])
        )
        raw = response.probabilities[0] if response.probabilities else None
        if isinstance(raw, list) and raw:
            return _clamp(float(raw[-1])), response.model_id
        label = _normalise_label(response.predictions[0])
        return (1.0 if label in {"1", "true", "hydrocarbon"} else 0.0), response.model_id
    except Exception:
        resistivity = max(float(record["resistivity_ohmm"]), 0.001)
        gamma_ray = float(record["gamma_ray_api"])
        rt_score = _clamp((math.log10(resistivity) - math.log10(1.0)) / (math.log10(100.0) - math.log10(1.0)))
        clean_score = _clamp(1.0 - ((gamma_ray - 20.0) / 100.0))
        return _clamp((0.70 * rt_score) + (0.30 * clean_score)), None


def _registered_fluid_prediction(record: dict[str, Any], model_id: str | None):
    registry = get_model_registry()
    selected = model_id or registry.default_for(ModelTask.fluid_type_classification)
    if not selected:
        return None
    response = get_model_service().infer(
        InferenceRequest(task=ModelTask.fluid_type_classification, model_id=selected, records=[record])
    )
    manifest = registry.get(response.model_id)
    label = _normalise_label(response.predictions[0])
    class_labels = [_normalise_label(item) for item in manifest.class_labels]
    raw = response.probabilities[0] if response.probabilities else None
    probabilities: dict[str, float] = {}
    if isinstance(raw, list) and class_labels and len(raw) == len(class_labels):
        probabilities = {name: _clamp(float(probability)) for name, probability in zip(class_labels, raw)}
    for name in ("water", "oil", "gas", "oil_and_gas"):
        probabilities.setdefault(name, 0.0)
    return label, probabilities, max(probabilities.values(), default=1.0), response.model_id


def _fallback_fluid_probabilities(record: dict[str, Any], hydrocarbon_probability: float) -> dict[str, float]:
    resistivity = max(float(record["resistivity_ohmm"]), 0.001)
    density = float(record["density_gcc"])
    neutron = float(record["neutron_porosity_vv"])
    sonic = float(record["sonic_usft"])
    gamma_ray = float(record["gamma_ray_api"])
    sw = record.get("water_saturation")
    if sw is None:
        rt_signal = _clamp((math.log10(resistivity) - math.log10(1.0)) / (math.log10(100.0) - math.log10(1.0)))
        sw = 1.0 - rt_signal
    sw = _clamp(float(sw))
    vsh = record.get("shale_volume")
    vsh = _clamp((gamma_ray - 20.0) / 100.0) if vsh is None else _clamp(float(vsh))
    density_porosity_proxy = _clamp((2.65 - density) / 1.65, -0.15, 0.65)
    gas_crossover = _clamp((density_porosity_proxy - neutron) / 0.30)
    low_density = _clamp((2.45 - density) / 0.45)
    sonic_gas_signal = _clamp((sonic - 75.0) / 65.0)
    clean = 1.0 - vsh
    hc = _clamp(hydrocarbon_probability)
    return _softmax({
        "water": (2.8 * sw) + (1.0 * (1.0 - hc)) + (0.4 * vsh),
        "oil": (2.4 * hc) + (0.9 * clean) + (0.6 * (1.0 - gas_crossover)),
        "gas": (2.1 * hc) + (1.7 * gas_crossover) + (0.8 * low_density) + (0.4 * sonic_gas_signal),
        "oil_and_gas": (1.4 * hc) + (0.9 * gas_crossover) + (0.5 * (1.0 - abs(sw - 0.45))),
    })


def _reservoir_quality(record: dict[str, Any], hc: float) -> str:
    phi = record.get("porosity")
    sw = record.get("water_saturation")
    vsh = record.get("shale_volume")
    permeability = record.get("permeability_md")
    phi_score = _clamp((float(phi) - 0.05) / 0.25) if phi is not None else 0.5
    sw_score = 1.0 - _clamp(float(sw)) if sw is not None else hc
    vsh_score = 1.0 - _clamp(float(vsh)) if vsh is not None else _clamp(1.0 - ((float(record["gamma_ray_api"]) - 20.0) / 100.0))
    perm_score = _clamp(math.log10(max(float(permeability), 0.1) + 1.0) / 3.0) if permeability is not None else 0.5
    score = (0.30 * phi_score) + (0.25 * sw_score) + (0.20 * vsh_score) + (0.15 * perm_score) + (0.10 * hc)
    if score >= 0.78:
        return "excellent"
    if score >= 0.60:
        return "good"
    if score >= 0.42:
        return "moderate"
    return "poor"


def _pay_zone(fluid: str, confidence: float, quality: str, record: dict[str, Any], hc: float) -> str:
    sw = record.get("water_saturation")
    permeability = record.get("permeability_md")
    if confidence < 0.40:
        return "uncertain"
    if fluid == "water" or (sw is not None and float(sw) >= 0.75):
        return "water_zone"
    if permeability is not None and float(permeability) < 1.0:
        return "tight_reservoir"
    if fluid in {"oil", "gas", "oil_and_gas"} and hc >= 0.65:
        return "net_pay" if quality in {"excellent", "good"} else "transition_zone"
    if hc < 0.35:
        return "non_pay"
    return "transition_zone"


def analyse_reservoir_interval(request: ReservoirIntelligenceRequest) -> ReservoirIntelligenceResponse:
    record = request.model_dump(exclude={"hydrocarbon_model_id", "fluid_model_id"})
    hc, hc_model_id = _hydrocarbon_probability(record, request.hydrocarbon_model_id)
    try:
        ai_result = _registered_fluid_prediction(record, request.fluid_model_id)
    except Exception:
        ai_result = None
    limitations = [
        "This output is decision support and must be reviewed by a qualified geoscientist or petrophysicist.",
        "Fluid typing should be reconciled with pressure gradients, mud-gas, PVT, core and formation-test data when available.",
    ]
    if ai_result is not None:
        fluid, probabilities, confidence, fluid_model_id = ai_result
        method = "registered_ai_model"
    else:
        probabilities = _fallback_fluid_probabilities(record, hc)
        fluid = max(probabilities, key=probabilities.get)
        confidence = probabilities[fluid]
        fluid_model_id = None
        method = "physics_informed_fallback"
        limitations.append("No validated oil/gas/water AI model is registered; the fluid type is a transparent screening fallback.")
    if confidence < 0.40:
        fluid = "uncertain"
    quality = _reservoir_quality(record, hc)
    pay_zone = _pay_zone(fluid, confidence, quality, record, hc)
    evidence = [
        f"Hydrocarbon probability is {hc:.1%}.",
        f"Fluid confidence is {confidence:.1%}.",
        f"Gamma ray is {request.gamma_ray_api:.1f} API.",
        f"Resistivity is {request.resistivity_ohmm:.2f} ohm-m.",
    ]
    if request.water_saturation is not None:
        evidence.append(f"Water saturation is {request.water_saturation:.1%}.")
    if request.porosity is not None:
        evidence.append(f"Porosity is {request.porosity:.1%}.")
    actions: list[str] = []
    if pay_zone == "net_pay":
        actions.extend(["Review the interval for pressure testing and representative fluid sampling.", "Prioritise the interval for formation evaluation and completion-design review."])
    elif fluid == "gas":
        actions.append("Confirm the gas indication with pressure-gradient, mud-gas and formation-test evidence.")
    elif fluid == "oil":
        actions.append("Confirm the oil indication with pressure-gradient and fluid-sampling evidence.")
    elif fluid == "water":
        actions.append("Evaluate the interval as a possible water-bearing or transition zone before testing.")
    if quality == "poor":
        actions.append("Poor reservoir quality may limit commercial deliverability even where hydrocarbons are indicated.")
    return ReservoirIntelligenceResponse(
        well_id=request.well_id,
        depth_m=request.depth_m,
        primary_fluid=fluid,
        fluid_probabilities={key: round(float(value), 6) for key, value in probabilities.items()},
        fluid_confidence=round(float(confidence), 6),
        fluid_method=method,
        fluid_model_id=fluid_model_id,
        hydrocarbon_probability=round(float(hc), 6),
        hydrocarbon_model_id=hc_model_id,
        reservoir_quality=quality,
        pay_zone=pay_zone,
        evidence=evidence,
        advisory_actions=actions,
        limitations=limitations,
    )