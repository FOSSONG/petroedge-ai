from fastapi import APIRouter, Depends

from app.core.rbac import require_roles
from app.services.synthetic import generate_samples

router = APIRouter()


@router.get("")
async def list_wells(_: dict = Depends(require_roles("admin", "geoscientist", "engineer", "viewer"))) -> list[dict]:
    return [
        {
            "well_id": "PETROEDGE-DEMO-01",
            "field": "Niger Delta Demo Field",
            "status": "streaming",
            "kb_m": 42.3,
            "total_depth_m": 3560.0,
        }
    ]


@router.get("/{well_id}/logs")
async def logs(
    well_id: str,
    rows: int = 250,
    _: dict = Depends(require_roles("admin", "geoscientist", "engineer", "viewer")),
) -> list[dict]:
    return generate_samples(rows=min(rows, 2000), well_id=well_id)

