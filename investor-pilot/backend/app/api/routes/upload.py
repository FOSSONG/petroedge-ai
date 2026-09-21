from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status, Depends
from app.core.rbac import require_roles

router = APIRouter(dependencies=[Depends(require_roles("admin", "geoscientist", "engineer"))])


@router.post("/upload-las")
async def upload_las(file: UploadFile = File(...)) -> dict[str, object]:
    try:
        import lasio
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LAS support requires the optional dependency 'lasio'.",
        ) from exc

    try:
        las = lasio.read(file.file)
        frame = las.df()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse LAS file: {exc}",
        ) from exc

    return {"rows": len(frame), "columns": list(frame.columns)}
