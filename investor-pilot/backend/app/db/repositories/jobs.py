from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import BackgroundJob, JobStatus
from app.db.repositories.base import Repository


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BackgroundJobRepository(Repository[BackgroundJob]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, BackgroundJob)

    def create_job(
        self,
        *,
        task_name: str,
        payload: dict,
        priority: int,
        max_attempts: int,
        requested_by: str | None = None,
    ) -> BackgroundJob:
        job = BackgroundJob(
            task_name=task_name,
            payload_json=payload,
            priority=priority,
            max_attempts=max_attempts,
            requested_by=requested_by,
            queued_at=utcnow(),
        )
        return self.add(job)

    def list_filtered(
        self,
        *,
        status: str | None,
        task_name: str | None,
        offset: int,
        limit: int,
    ) -> Sequence[BackgroundJob]:
        statement = select(BackgroundJob)
        if status:
            statement = statement.where(BackgroundJob.status == status)
        if task_name:
            statement = statement.where(BackgroundJob.task_name == task_name)
        statement = statement.order_by(BackgroundJob.created_at.desc()).offset(offset).limit(limit)
        return self.session.scalars(statement).all()

    def count_filtered(self, *, status: str | None, task_name: str | None) -> int:
        statement = select(func.count()).select_from(BackgroundJob)
        if status:
            statement = statement.where(BackgroundJob.status == status)
        if task_name:
            statement = statement.where(BackgroundJob.task_name == task_name)
        return int(self.session.scalar(statement) or 0)

    def cancel(self, job_id: str) -> BackgroundJob:
        job = self.require(job_id)
        if job.status in {JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value}:
            return job
        job.status = JobStatus.CANCELLED.value
        job.cancelled_at = utcnow()
        self.session.commit()
        self.session.refresh(job)
        return job
