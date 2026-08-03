from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.report_service import (
    DEFAULT_FORMATS,
    REPORT_ROOT,
    SUPPORTED_FORMATS,
    ReportRequest,
    get_report_service,
)


logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500

FORMAT_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "xlsx": (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
    "csv": "text/csv",
    "json": "application/json",
    "html": "text/html",
    "metadata": "application/json",
}

FORMAT_FILENAMES = {
    "pdf": "report.pdf",
    "xlsx": "report.xlsx",
    "csv": "report.csv",
    "json": "report.json",
    "html": "report.html",
    "metadata": "metadata.json",
}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ReportGenerationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str = Field(
        min_length=1,
        max_length=50,
    )
    source_id: str = Field(
        min_length=1,
        max_length=150,
    )
    title: str | None = Field(
        default=None,
        max_length=300,
    )
    well_id: str | None = Field(
        default=None,
        max_length=150,
    )
    formats: list[str] = Field(
        default_factory=lambda: list(
            DEFAULT_FORMATS
        ),
        min_length=1,
    )
    include_alerts: bool = True
    include_raw_records: bool = False
    include_recommendations: bool = True
    reservoir_porosity_cutoff: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
    )
    reservoir_sw_cutoff: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
    )
    hydrocarbon_probability_cutoff: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
    )
    minimum_interval_thickness: float = Field(
        default=0.5,
        gt=0.0,
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    @field_validator("source_type")
    @classmethod
    def validate_source_type(
        cls,
        value: str,
    ) -> str:
        normalised = value.strip().lower()
        allowed = {
            "dataset",
            "prediction",
            "stream",
        }

        if normalised not in allowed:
            raise ValueError(
                "source_type must be one of: "
                "dataset, prediction, stream"
            )

        return normalised

    @field_validator("formats")
    @classmethod
    def validate_formats(
        cls,
        values: list[str],
    ) -> list[str]:
        normalised = list(
            dict.fromkeys(
                str(value).strip().lower()
                for value in values
                if str(value).strip()
            )
        )

        if not normalised:
            raise ValueError(
                "At least one report format is required."
            )

        unsupported = [
            value
            for value in normalised
            if value not in SUPPORTED_FORMATS
        ]

        if unsupported:
            raise ValueError(
                "Unsupported report formats: "
                + ", ".join(unsupported)
            )

        return normalised


class SourceReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None,
        max_length=300,
    )
    well_id: str | None = Field(
        default=None,
        max_length=150,
    )
    formats: list[str] = Field(
        default_factory=lambda: list(
            DEFAULT_FORMATS
        ),
        min_length=1,
    )
    include_alerts: bool = True
    include_raw_records: bool = False
    include_recommendations: bool = True
    reservoir_porosity_cutoff: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
    )
    reservoir_sw_cutoff: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
    )
    hydrocarbon_probability_cutoff: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
    )
    minimum_interval_thickness: float = Field(
        default=0.5,
        gt=0.0,
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    @field_validator("formats")
    @classmethod
    def validate_formats(
        cls,
        values: list[str],
    ) -> list[str]:
        normalised = list(
            dict.fromkeys(
                str(value).strip().lower()
                for value in values
                if str(value).strip()
            )
        )

        unsupported = [
            value
            for value in normalised
            if value not in SUPPORTED_FORMATS
        ]

        if unsupported:
            raise ValueError(
                "Unsupported report formats: "
                + ", ".join(unsupported)
            )

        return normalised or list(
            DEFAULT_FORMATS
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_uuid(
    identifier: str,
    label: str,
) -> None:
    try:
        UUID(identifier)
    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=f"The {label} is invalid.",
        ) from exc


def _build_request(
    *,
    source_type: str,
    source_id: str,
    payload: SourceReportPayload,
) -> ReportRequest:
    return ReportRequest(
        source_type=source_type,
        source_id=source_id,
        title=payload.title,
        well_id=payload.well_id,
        formats=tuple(payload.formats),
        include_alerts=(
            payload.include_alerts
        ),
        include_raw_records=(
            payload.include_raw_records
        ),
        include_recommendations=(
            payload.include_recommendations
        ),
        reservoir_porosity_cutoff=(
            payload.reservoir_porosity_cutoff
        ),
        reservoir_sw_cutoff=(
            payload.reservoir_sw_cutoff
        ),
        hydrocarbon_probability_cutoff=(
            payload.hydrocarbon_probability_cutoff
        ),
        minimum_interval_thickness=(
            payload.minimum_interval_thickness
        ),
        metadata=payload.metadata,
    )


def _report_directory(
    report_id: str,
) -> Path:
    _validate_uuid(
        report_id,
        "report ID",
    )

    directory = REPORT_ROOT / report_id

    if not directory.exists():
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Report not found.",
        )

    return directory


def _load_report_metadata(
    report_id: str,
) -> dict[str, Any]:
    directory = _report_directory(
        report_id
    )
    metadata_path = (
        directory / "metadata.json"
    )

    if not metadata_path.exists():
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Report metadata was not found."
            ),
        )

    try:
        payload = json.loads(
            metadata_path.read_text(
                encoding="utf-8"
            )
        )
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Stored report metadata is invalid."
            ),
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Stored report metadata has an "
                "invalid structure."
            ),
        )

    return payload


def _resolve_report_file(
    report_id: str,
    format_name: str,
) -> Path:
    format_name = (
        format_name.strip().lower()
    )

    if format_name not in FORMAT_FILENAMES:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "format must be one of: "
                + ", ".join(
                    sorted(
                        FORMAT_FILENAMES
                    )
                )
            ),
        )

    directory = _report_directory(
        report_id
    )
    path = (
        directory
        / FORMAT_FILENAMES[
            format_name
        ]
    )

    if not path.exists():
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                f"The {format_name} report "
                "was not generated."
            ),
        )

    return path


async def _generate(
    request: ReportRequest,
) -> dict[str, Any]:
    service = get_report_service()

    try:
        result = await asyncio.to_thread(
            service.generate,
            request,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception(
            "Report generation failed."
        )
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Report generation failed. "
                "Review the server logs for details."
            ),
        ) from exc

    return result.to_dict()


# ---------------------------------------------------------------------------
# Report generation routes
# ---------------------------------------------------------------------------

@router.post(
    "/generate",
    status_code=status.HTTP_201_CREATED,
    summary="Generate a report from any supported source",
)
async def generate_report(
    payload: ReportGenerationPayload,
) -> dict[str, Any]:
    request = ReportRequest(
        source_type=payload.source_type,
        source_id=payload.source_id,
        title=payload.title,
        well_id=payload.well_id,
        formats=tuple(
            payload.formats
        ),
        include_alerts=(
            payload.include_alerts
        ),
        include_raw_records=(
            payload.include_raw_records
        ),
        include_recommendations=(
            payload.include_recommendations
        ),
        reservoir_porosity_cutoff=(
            payload.reservoir_porosity_cutoff
        ),
        reservoir_sw_cutoff=(
            payload.reservoir_sw_cutoff
        ),
        hydrocarbon_probability_cutoff=(
            payload.hydrocarbon_probability_cutoff
        ),
        minimum_interval_thickness=(
            payload.minimum_interval_thickness
        ),
        metadata=payload.metadata,
    )

    return await _generate(request)


@router.post(
    "/dataset/{dataset_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Generate a report for a processed dataset",
)
async def generate_dataset_report(
    dataset_id: str,
    payload: SourceReportPayload = Body(
        default_factory=SourceReportPayload
    ),
) -> dict[str, Any]:
    request = _build_request(
        source_type="dataset",
        source_id=dataset_id,
        payload=payload,
    )

    return await _generate(request)


@router.post(
    "/prediction/{prediction_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Generate a report for a saved prediction",
)
async def generate_prediction_report(
    prediction_id: str,
    payload: SourceReportPayload = Body(
        default_factory=SourceReportPayload
    ),
) -> dict[str, Any]:
    _validate_uuid(
        prediction_id,
        "prediction ID",
    )

    request = _build_request(
        source_type="prediction",
        source_id=prediction_id,
        payload=payload,
    )

    return await _generate(request)


@router.post(
    "/stream/{stream_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Generate a report for a stream session",
)
async def generate_stream_report(
    stream_id: str,
    payload: SourceReportPayload = Body(
        default_factory=SourceReportPayload
    ),
) -> dict[str, Any]:
    _validate_uuid(
        stream_id,
        "stream ID",
    )

    request = _build_request(
        source_type="stream",
        source_id=stream_id,
        payload=payload,
    )

    return await _generate(request)


# ---------------------------------------------------------------------------
# Report management routes
# ---------------------------------------------------------------------------

@router.get(
    "",
    summary="List generated reports",
)
async def list_reports(
    source_type: str | None = Query(
        default=None
    ),
    source_id: str | None = Query(
        default=None
    ),
    well_id: str | None = Query(
        default=None
    ),
    limit: int = Query(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
) -> dict[str, Any]:
    service = get_report_service()

    reports = await asyncio.to_thread(
        service.list_reports
    )

    if source_type:
        normalised = (
            source_type.strip().lower()
        )
        reports = [
            report
            for report in reports
            if str(
                report.get(
                    "source_type",
                    "",
                )
            ).lower()
            == normalised
        ]

    if source_id:
        reports = [
            report
            for report in reports
            if report.get("source_id")
            == source_id
        ]

    if well_id:
        reports = [
            report
            for report in reports
            if str(
                report.get(
                    "well_id",
                    "",
                )
            )
            == str(well_id)
        ]

    total = len(reports)
    page = reports[
        offset : offset + limit
    ]

    return {
        "items": page,
        "reports": page,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/formats",
    summary="List supported report formats",
)
async def list_report_formats() -> dict[str, Any]:
    return {
        "supported_formats": list(
            SUPPORTED_FORMATS
        ),
        "default_formats": list(
            DEFAULT_FORMATS
        ),
        "media_types": (
            FORMAT_MEDIA_TYPES
        ),
    }


@router.get(
    "/health/status",
    summary="Read reporting service health",
)
async def report_service_health() -> dict[str, Any]:
    service = get_report_service()

    reports = await asyncio.to_thread(
        service.list_reports
    )

    return {
        "status": "healthy",
        "report_root": str(
            REPORT_ROOT
        ),
        "report_count": len(reports),
        "supported_formats": list(
            SUPPORTED_FORMATS
        ),
    }


@router.get(
    "/{report_id}",
    summary="Read report metadata and analysis",
)
async def get_report(
    report_id: str,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _load_report_metadata,
        report_id,
    )


@router.get(
    "/{report_id}/files",
    summary="List files generated for a report",
)
async def list_report_files(
    report_id: str,
) -> dict[str, Any]:
    directory = _report_directory(
        report_id
    )

    files: list[dict[str, Any]] = []

    for path in sorted(
        directory.iterdir()
    ):
        if not path.is_file():
            continue

        format_name = next(
            (
                key
                for key, filename
                in FORMAT_FILENAMES.items()
                if filename == path.name
            ),
            path.suffix.lstrip("."),
        )

        files.append(
            {
                "name": path.name,
                "format": format_name,
                "size_bytes": (
                    path.stat().st_size
                ),
            }
        )

    return {
        "report_id": report_id,
        "files": files,
        "total": len(files),
    }


@router.get(
    "/{report_id}/download",
    response_class=FileResponse,
    summary="Download a generated report file",
)
async def download_report(
    report_id: str,
    format_name: str = Query(
        default="pdf",
        alias="format",
    ),
) -> FileResponse:
    path = _resolve_report_file(
        report_id,
        format_name,
    )
    normalised = (
        format_name.strip().lower()
    )

    return FileResponse(
        path=path,
        media_type=(
            FORMAT_MEDIA_TYPES.get(
                normalised,
                "application/octet-stream",
            )
        ),
        filename=path.name,
    )


@router.get(
    "/{report_id}/preview",
    response_class=FileResponse,
    summary="Preview the HTML report",
)
async def preview_report(
    report_id: str,
) -> FileResponse:
    path = _resolve_report_file(
        report_id,
        "html",
    )

    return FileResponse(
        path=path,
        media_type="text/html",
        filename=path.name,
    )


@router.delete(
    "/{report_id}",
    summary="Delete a generated report",
)
async def delete_report(
    report_id: str,
) -> dict[str, Any]:
    service = get_report_service()

    try:
        deleted = await asyncio.to_thread(
            service.delete_report,
            report_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        ) from exc

    if not deleted:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Report not found.",
        )

    return {
        "report_id": report_id,
        "status": "deleted",
    }
