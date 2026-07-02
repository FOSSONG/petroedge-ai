from app.schemas import AnalyticsResult, WellLogSample
from app.services.ai_models import (
    anomaly_score,
    classify_lithology,
    hydrocarbon_probability,
    predict_facies,
)
from app.services.explainability import explain_prediction
from app.services.petrophysics import effective_porosity, net_to_gross, permeability, shale_volume, water_saturation
from app.services.qc import quality_score


def analyze_sample(sample: WellLogSample) -> AnalyticsResult:
    anomaly = anomaly_score(sample)
    return AnalyticsResult(
        input=sample,
        qc_score=quality_score(sample),
        hydrocarbon_probability=hydrocarbon_probability(sample),
        lithology=classify_lithology(sample),
        facies=predict_facies(sample),
        anomaly_score=anomaly,
        is_anomaly=anomaly >= 0.5,
        porosity=effective_porosity(sample),
        water_saturation=water_saturation(sample),
        shale_volume=round(shale_volume(sample.gamma_ray_api), 4),
        net_to_gross=net_to_gross(sample),
        permeability_md=permeability(sample),
        explanation=explain_prediction(sample),
    )

