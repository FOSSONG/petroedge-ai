from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status

router = APIRouter()


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
