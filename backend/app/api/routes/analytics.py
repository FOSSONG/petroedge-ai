from fastapi import APIRouter, Depends

from app.core.rbac import require_roles
from app.schemas import AnalyticsResult, WellLogSample
from app.services.analytics import analyze_sample
from app.services.petrophysics import reservoir_quality_index

router = APIRouter()


@router.post("/sample", response_model=AnalyticsResult)
async def analyze(
    sample: WellLogSample,
    _: dict = Depends(require_roles("admin", "geoscientist", "engineer")),
) -> AnalyticsResult:
    return analyze_sample(sample)


@router.post("/petrophysics")
async def petrophysics(
    sample: WellLogSample,
    _: dict = Depends(require_roles("admin", "geoscientist", "engineer")),
) -> dict:
    result = analyze_sample(sample)
    return {
        "porosity": result.porosity,
        "water_saturation": result.water_saturation,
        "shale_volume": result.shale_volume,
        "net_to_gross": result.net_to_gross,
        "permeability_md": result.permeability_md,
        "reservoir_quality_index": reservoir_quality_index(sample),
    }

