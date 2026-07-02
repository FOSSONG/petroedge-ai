from fastapi import APIRouter, Depends

from app.core.rbac import require_roles
from app.schemas import WellLogSample
from app.services.analytics import analyze_sample
from app.services.model_monitor import summarize_predictions
from app.services.synthetic import generate_samples

router = APIRouter()


@router.get("/models")
async def model_status(_: dict = Depends(require_roles("admin", "geoscientist", "engineer", "viewer"))) -> dict:
    samples = generate_samples(rows=120)
    results = [analyze_sample(WellLogSample(**sample)).model_dump() for sample in samples]
    return {
        "registered_models": [
            "hydrocarbon-detector-v1",
            "lithology-classifier-v1",
            "facies-predictor-v1",
            "anomaly-detector-v1",
        ],
        "metrics": summarize_predictions(results),
        "mlflow_tracking": "enabled",
    }
