from __future__ import annotations

from typing import Any

from app.ml_platform.schemas import InferenceRequest, ModelTask
from app.ml_platform.service import get_model_service
from app.schemas import AnalyticsResult, WellLogSample
from app.services.shap_service import explain


def _extract_positive_probability(
    probabilities: list[Any] | None,
    prediction: Any,
) -> float:
    if probabilities:
        first = probabilities[0]

        if isinstance(first, list):
            if len(first) >= 2:
                return float(first[-1])

            if len(first) == 1:
                return float(first[0])

        if isinstance(first, (int, float)):
            return float(first)

    if isinstance(prediction, bool):
        return 1.0 if prediction else 0.0

    if isinstance(prediction, (int, float)):
        value = float(prediction)

        if 0.0 <= value <= 1.0:
            return value

        return 1.0 if value > 0 else 0.0

    label = str(prediction).strip().lower()

    return (
        1.0
        if label in {
            "1",
            "true",
            "hydrocarbon",
            "pay",
            "oil",
            "gas",
        }
        else 0.0
    )


def _heuristic_hydrocarbon_probability(
    sample: WellLogSample,
) -> float:
    """
    Deterministic operational fallback used only when a registered model
    is unavailable. It preserves service availability while making the
    fallback explicit in the explanation payload.
    """
    resistivity_score = min(
        max(sample.resistivity_ohmm / 100.0, 0.0),
        1.0,
    )

    clean_sand_score = min(
        max(
            1.0 - sample.gamma_ray_api / 150.0,
            0.0,
        ),
        1.0,
    )

    porosity_score = min(
        max(sample.neutron_porosity_vv / 0.30, 0.0),
        1.0,
    )

    probability = (
        0.50 * resistivity_score
        + 0.30 * clean_sand_score
        + 0.20 * porosity_score
    )

    return round(
        min(max(probability, 0.0), 1.0),
        4,
    )


def analyze_sample(
    sample: WellLogSample,
) -> AnalyticsResult:
    feature_record = {
        "gamma_ray_api": sample.gamma_ray_api,
        "resistivity_ohmm": sample.resistivity_ohmm,
        "density_gcc": sample.density_gcc,
        "neutron_porosity_vv": sample.neutron_porosity_vv,
        "sonic_usft": sample.sonic_usft,
        "caliper_in": sample.caliper_in,
    }

    model_service = get_model_service()
    fallback_details: dict[str, Any] = {}

    try:
        hydrocarbon_output = model_service.infer(
            InferenceRequest(
                task=ModelTask.hydrocarbon_classification,
                records=[feature_record],
                explain=False,
            )
        )

        hydrocarbon_prediction = (
            hydrocarbon_output.predictions[0]
        )

        model_probability = _extract_positive_probability(
            hydrocarbon_output.probabilities,
            hydrocarbon_prediction,
        )
        heuristic_probability = _heuristic_hydrocarbon_probability(sample)
        # Blend the model with a transparent petrophysical prior. This prevents
        # a weak or poorly calibrated development model from contradicting a
        # clean, porous, high-resistivity interval while preserving the model
        # as the primary source of the prediction.
        hydrocarbon_probability = round(
            min(max((0.55 * model_probability) + (0.45 * heuristic_probability), 0.0), 1.0),
            4,
        )

        fallback_details["hydrocarbon_model_id"] = (
            hydrocarbon_output.model_id
        )
        fallback_details["hydrocarbon_fallback_used"] = (
            hydrocarbon_output.fallback_used
        )
    except Exception as exc:
        hydrocarbon_probability = (
            _heuristic_hydrocarbon_probability(sample)
        )

        fallback_details.update(
            {
                "hydrocarbon_model_id": None,
                "hydrocarbon_fallback_used": True,
                "hydrocarbon_fallback_reason": (
                    f"{type(exc).__name__}: {exc}"
                ),
            }
        )

    try:
        lithology_output = model_service.infer(
            InferenceRequest(
                task=ModelTask.lithology_classification,
                records=[feature_record],
                explain=False,
            )
        )

        lithology_prediction = str(
            lithology_output.predictions[0]
        )

        fallback_details["lithology_model_id"] = (
            lithology_output.model_id
        )
        fallback_details["lithology_fallback_used"] = (
            lithology_output.fallback_used
        )
    except Exception as exc:
        lithology_prediction = (
            "Sandstone"
            if sample.gamma_ray_api < 75
            else "Shale"
        )

        fallback_details.update(
            {
                "lithology_model_id": None,
                "lithology_fallback_used": True,
                "lithology_fallback_reason": (
                    f"{type(exc).__name__}: {exc}"
                ),
            }
        )

    try:
        explanation = explain(
            __import__("pandas").DataFrame(
                [feature_record]
            )
        )
    except Exception as exc:
        explanation = {
            "status": "unavailable",
            "reason": f"{type(exc).__name__}: {exc}",
        }

    explanation = {
        **explanation,
        **fallback_details,
    }

    porosity = round(
        min(
            max(sample.neutron_porosity_vv, 0.0),
            0.6,
        ),
        3,
    )

    water_saturation = round(
        max(
            0.1,
            min(
                (
                    20.0
                    / max(sample.resistivity_ohmm, 0.1)
                )
                ** 0.5,
                1.0,
            ),
        ),
        3,
    )

    permeability_md = round(
        max(
            porosity
            * sample.resistivity_ohmm
            * 10.0,
            0.0,
        ),
        1,
    )

    qc_score = round(
        max(
            0.5,
            1.0
            - abs(sample.caliper_in - 8.5)
            / 10.0,
        ),
        2,
    )

    shale_volume = round(
        min(
            max(sample.gamma_ray_api / 150.0, 0.0),
            1.0,
        ),
        3,
    )

    net_to_gross = round(
        min(
            max(
                1.0
                - sample.gamma_ray_api / 200.0,
                0.0,
            ),
            1.0,
        ),
        3,
    )

    return AnalyticsResult(
        input=sample.model_dump(),
        qc_score=qc_score,
        hydrocarbon_probability=round(
            min(
                max(hydrocarbon_probability, 0.0),
                1.0,
            ),
            4,
        ),
        lithology=lithology_prediction,
        facies=(
            "Channel Sand"
            if sample.gamma_ray_api < 75
            else "Shale-Dominated Facies"
        ),
        anomaly_score=round(
            1.0 - hydrocarbon_probability,
            3,
        ),
        is_anomaly=hydrocarbon_probability > 0.80,
        porosity=porosity,
        water_saturation=water_saturation,
        shale_volume=shale_volume,
        net_to_gross=net_to_gross,
        permeability_md=permeability_md,
        explanation=explanation,
    )
