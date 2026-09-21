from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_job_repository
from app.core.rbac import require_roles
from app.db.models import BackgroundJob
from app.db.repositories.jobs import BackgroundJobRepository
from app.jobs.manager import BackgroundJobManager, get_job_manager
from app.jobs.schemas import JobCreate, JobHealthResponse, JobListResponse, JobResponse
from app.realtime.events import EventType, get_event_bus

router = APIRouter()
JobRepo = Annotated[
    BackgroundJobRepository,
    Depends(get_job_repository),
]
JobManager = Annotated[
    BackgroundJobManager,
    Depends(get_job_manager),
]


def _actor_id(user: dict[str, Any]) -> str | None:
    value = user.get("user_id") or user.get("uid") or user.get("sub")
    return str(value) if value else None


def _serialize(job: BackgroundJob) -> JobResponse:
    return JobResponse(
        id=job.id,
        task_name=job.task_name,
        status=job.status,
        priority=job.priority,
        progress_percent=job.progress_percent,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        payload=dict(job.payload_json or {}),
        result=dict(job.result_json or {}),
        error_message=job.error_message,
        created_at=job.created_at,
        queued_at=job.queued_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        cancelled_at=job.cancelled_at,
    )


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_job(
    request: JobCreate,
    repository: JobRepo,
    manager: JobManager,
    user: dict[str, Any] = Depends(
        require_roles("admin", "geoscientist", "engineer")
    ),
) -> JobResponse:
    if request.task_name not in manager.registered_tasks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Unknown background task.",
                "registered_tasks": manager.registered_tasks,
            },
        )

    job = repository.create_job(
        task_name=request.task_name,
        payload=request.payload,
        priority=request.priority,
        max_attempts=request.max_attempts,
    )

    await manager.enqueue(
        job.id,
        priority=job.priority,
        actor_id=_actor_id(user),
    )

    return _serialize(job)


@router.get("", response_model=JobListResponse)
def list_jobs(
    repository: JobRepo,
    status_filter: str | None = Query(default=None, alias="status"),
    task_name: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    _: dict[str, Any] = Depends(
        require_roles("admin", "geoscientist", "engineer", "viewer")
    ),
) -> JobListResponse:
    jobs = repository.list_filtered(
        status=status_filter,
        task_name=task_name,
        offset=offset,
        limit=limit,
    )
    total = repository.count_filtered(
        status=status_filter,
        task_name=task_name,
    )
    return JobListResponse(
        items=[_serialize(job) for job in jobs],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/health", response_model=JobHealthResponse)
def job_health(
    manager: JobManager,
    _: dict[str, Any] = Depends(
        require_roles("admin", "geoscientist", "engineer", "viewer")
    ),
) -> JobHealthResponse:
    return JobHealthResponse(
        status="healthy" if manager.is_running else "stopped",
        running=manager.is_running,
        worker_count=manager.worker_count,
        queue_size=manager.queue_size,
        registered_tasks=manager.registered_tasks,
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    repository: JobRepo,
    _: dict[str, Any] = Depends(
        require_roles("admin", "geoscientist", "engineer", "viewer")
    ),
) -> JobResponse:
    job = repository.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Background job not found.",
        )
    return _serialize(job)


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: str,
    repository: JobRepo,
    user: dict[str, Any] = Depends(
        require_roles("admin", "geoscientist", "engineer")
    ),
) -> JobResponse:
    try:
        job = repository.cancel(job_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    response = _serialize(job)

    await get_event_bus().emit(
        EventType.JOB_CANCELLED,
        response.model_dump(mode="json"),
        channel="jobs",
        correlation_id=job_id,
        actor_id=_actor_id(user),
    )

    return response