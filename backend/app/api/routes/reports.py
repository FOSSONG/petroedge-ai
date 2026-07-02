from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.core.rbac import require_roles
from app.services.synthetic import generate_samples

router = APIRouter()


@router.get("/{well_id}/summary")
async def summary_report(
    well_id: str,
    _: dict = Depends(require_roles("admin", "geoscientist", "engineer", "viewer")),
) -> dict:
    rows = generate_samples(rows=100, well_id=well_id)
    return {
        "well_id": well_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": "Reservoir Characterization Summary",
        "sections": [
            "Data quality and curve availability",
            "Hydrocarbon probability intervals",
            "Lithology and facies distribution",
            "Petrophysical cutoffs and net pay",
            "Model monitoring and explainability notes",
        ],
        "sample_count": len(rows),
    }

