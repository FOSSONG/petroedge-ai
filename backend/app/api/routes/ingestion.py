import csv
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.rbac import require_roles
from app.schemas import IngestionResponse, SourceType
from app.services.las_parser import parse_las
from app.services.witsml import normalize_witsml_sample

router = APIRouter()


@router.post("/upload", response_model=IngestionResponse)
async def upload_log_file(
    source_type: SourceType,
    file: UploadFile = File(...),
    _: dict = Depends(require_roles("admin", "geoscientist", "engineer")),
) -> IngestionResponse:
    suffix = Path(file.filename or "upload").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        if source_type == SourceType.las:
            rows = parse_las(tmp_path, max_records=500)
        elif source_type in {SourceType.csv, SourceType.ascii}:
            with tmp_path.open("r", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))[:500]
        elif source_type == SourceType.dlis:
            rows = [{"status": "DLIS adapter placeholder", "file": file.filename}]
        else:
            rows = [normalize_witsml_sample({"well_id": "WITSML-STREAM", "channels": {}})]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    well_id = str(rows[0].get("well_id", "UNKNOWN")) if rows else "UNKNOWN"
    return IngestionResponse(
        source_type=source_type,
        records_ingested=len(rows),
        well_id=well_id,
        preview=rows[:10],
    )
