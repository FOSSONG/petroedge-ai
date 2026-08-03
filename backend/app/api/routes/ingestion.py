from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.dependencies import DBSession
from app.core.rbac import require_roles
from app.core.security import get_current_user
from app.schemas import IngestionResponse, SourceType
from app.services.domain_services import IngestionPersistenceService
from app.services.las_parser import parse_las
from app.services.witsml import normalize_witsml_sample

router = APIRouter()
BACKEND_ROOT = Path(__file__).resolve().parents[3]
UPLOAD_ROOT = BACKEND_ROOT / "data" / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


@router.post("/upload", response_model=IngestionResponse)
async def upload_log_file(
    source_type: SourceType,
    db: DBSession,
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
    _: dict[str, Any] = Depends(require_roles("admin", "geoscientist", "engineer")),
) -> IngestionResponse:
    original_name = Path(file.filename or "upload").name
    suffix = Path(original_name).suffix.lower()
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    stored_name = f"{uuid4().hex}{suffix}"
    stored_path = UPLOAD_ROOT / stored_name
    stored_path.write_bytes(content)

    rows: list[dict[str, Any]] = []
    try:
        if source_type == SourceType.las:
            rows = parse_las(stored_path, max_records=500)
        elif source_type in {SourceType.csv, SourceType.ascii}:
            with stored_path.open("r", encoding="utf-8-sig", newline="") as source:
                rows = list(csv.DictReader(source))[:500]
        elif source_type == SourceType.dlis:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="DLIS ingestion is not enabled in this build.",
            )
        else:
            rows = [normalize_witsml_sample({"well_id": "WITSML-STREAM", "channels": {}})]
    except HTTPException:
        stored_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    well_id = str(rows[0].get("well_id", "UNKNOWN")) if rows else "UNKNOWN"
    checksum = hashlib.sha256(content).hexdigest()
    dataset = IngestionPersistenceService(db).persist_dataset(
        well_public_id=well_id,
        source_type=source_type.value,
        filename=original_name,
        storage_path=str(stored_path.relative_to(BACKEND_ROOT)),
        row_count=len(rows),
        owner_id=user.get("user_id") if user.get("user_id") != "development-admin" else None,
        metadata={
            "checksum_sha256": checksum,
            "preview_count": min(len(rows), 10),
            "content_type": file.content_type,
        },
    )
    dataset.checksum_sha256 = checksum
    db.commit()

    return IngestionResponse(
        source_type=source_type,
        records_ingested=len(rows),
        well_id=well_id,
        dataset_id=dataset.id,
        preview=rows[:10],
        message="File ingested and registered successfully.",
    )
