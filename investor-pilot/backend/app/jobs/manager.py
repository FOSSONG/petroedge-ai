from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import BackgroundJob, JobStatus
from app.db.session import SessionLocal
from app.jobs.handlers import DEFAULT_HANDLERS, JobHandler
from app.realtime.events import EventType, get_event_bus

logger = logging.getLogger(__name__)

QueueItem = tuple[int, float, str]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BackgroundJobManager:
    """In-process asynchronous worker pool with persistent SQL job state.

    The manager is restart-safe across repeated FastAPI lifespan executions,
    including multiple TestClient instances created during one pytest session.
    """

    def __init__(self, *, worker_count: int = 2) -> None:
        self.worker_count = max(1, int(worker_count))

        self._queue: asyncio.PriorityQueue[QueueItem] | None = None
        self._handlers: dict[str, JobHandler] = dict(DEFAULT_HANDLERS)
        self._workers: list[asyncio.Task[None]] = []

        self._running = False
        self._generation = 0
        self._owner_loop: asyncio.AbstractEventLoop | None = None

        self._event_bus = get_event_bus()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def registered_tasks(self) -> list[str]:
        return sorted(self._handlers)

    @property
    def queue_size(self) -> int:
        queue = self._queue
        return queue.qsize() if queue is not None else 0

    def register(self, task_name: str, handler: JobHandler) -> None:
        clean_name = task_name.strip()

        if not clean_name:
            raise ValueError("task_name cannot be empty")

        self._handlers[clean_name] = handler

    async def start(self) -> None:
        """Start a fresh worker pool for the current event loop."""

        current_loop = asyncio.get_running_loop()

        if (
            self._running
            and self._owner_loop is current_loop
            and any(not worker.done() for worker in self._workers)
        ):
            return

        await self._discard_existing_workers()

        self._generation += 1
        generation = self._generation

        queue: asyncio.PriorityQueue[QueueItem] = asyncio.PriorityQueue()

        self._queue = queue
        self._owner_loop = current_loop
        self._running = True

        try:
            recovered_jobs = await asyncio.to_thread(
                self._recover_interrupted_jobs
            )

            for item in recovered_jobs:
                queue.put_nowait(item)

            self._workers = [
                asyncio.create_task(
                    self._worker_loop(
                        worker_index=index,
                        queue=queue,
                        generation=generation,
                    ),
                    name=f"petroedge-job-worker-{index}",
                )
                for index in range(self.worker_count)
            ]

            logger.info(
                "Background job manager started with %s workers.",
                self.worker_count,
            )

        except BaseException:
            self._running = False
            self._generation += 1
            self._queue = None
            self._owner_loop = None
            self._workers.clear()
            raise

    async def stop(self) -> None:
        """Stop workers without retaining event-loop-bound objects."""

        self._running = False
        self._generation += 1

        workers = list(self._workers)
        self._workers.clear()

        current_loop = asyncio.get_running_loop()
        local_workers: list[asyncio.Task[None]] = []

        for worker in workers:
            if worker.done():
                continue

            try:
                worker_loop = worker.get_loop()
            except RuntimeError:
                continue

            if worker_loop is current_loop:
                worker.cancel()
                local_workers.append(worker)
                continue

            if not worker_loop.is_closed():
                try:
                    worker_loop.call_soon_threadsafe(worker.cancel)
                except RuntimeError:
                    logger.debug(
                        "Could not cancel worker attached to another loop.",
                        exc_info=True,
                    )

        if local_workers:
            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        *local_workers,
                        return_exceptions=True,
                    ),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Timed out while stopping background job workers."
                )

        self._queue = None
        self._owner_loop = None

        logger.info("Background job manager stopped.")

    async def _discard_existing_workers(self) -> None:
        """Remove stale workers before starting another lifecycle."""

        if not self._workers:
            self._running = False
            self._queue = None
            self._owner_loop = None
            return

        self._running = False
        self._generation += 1

        workers = list(self._workers)
        self._workers.clear()

        current_loop = asyncio.get_running_loop()
        local_workers: list[asyncio.Task[None]] = []

        for worker in workers:
            if worker.done():
                continue

            try:
                worker_loop = worker.get_loop()
            except RuntimeError:
                continue

            if worker_loop is current_loop:
                worker.cancel()
                local_workers.append(worker)
            elif not worker_loop.is_closed():
                try:
                    worker_loop.call_soon_threadsafe(worker.cancel)
                except RuntimeError:
                    logger.debug(
                        "Could not cancel stale worker.",
                        exc_info=True,
                    )

        if local_workers:
            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        *local_workers,
                        return_exceptions=True,
                    ),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Timed out while discarding stale job workers."
                )

        self._queue = None
        self._owner_loop = None

    async def enqueue(
        self,
        job_id: str,
        *,
        priority: int = 100,
        actor_id: str | None = None,
    ) -> None:
        del actor_id

        if not self._running or self._queue is None:
            raise RuntimeError(
                "Background job manager is not running."
            )

        queue = self._queue

        await queue.put(
            (
                int(priority),
                asyncio.get_running_loop().time(),
                job_id,
            )
        )

        await self._event_bus.emit(
            EventType.JOB_QUEUED,
            {
                "job_id": job_id,
                "priority": int(priority),
            },
            channel="jobs",
            correlation_id=job_id,
        )

    async def _worker_loop(
        self,
        *,
        worker_index: int,
        queue: asyncio.PriorityQueue[QueueItem],
        generation: int,
    ) -> None:
        while self._running and self._generation == generation:
            try:
                _, _, job_id = await queue.get()

                try:
                    if (
                        not self._running
                        or self._generation != generation
                    ):
                        return

                    await self._execute(job_id)

                finally:
                    queue.task_done()

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception(
                    "Background worker %s failed unexpectedly.",
                    worker_index,
                )

    async def _execute(self, job_id: str) -> None:
        job = await asyncio.to_thread(
            self._claim_job,
            job_id,
        )

        if job is None:
            return

        await self._event_bus.emit(
            EventType.JOB_STARTED,
            {
                "job_id": job_id,
                "task_name": job["task_name"],
            },
            channel="jobs",
            correlation_id=job_id,
        )

        handler = self._handlers.get(job["task_name"])

        if handler is None:
            message = (
                "No handler is registered for task "
                f"{job['task_name']!r}."
            )

            await asyncio.to_thread(
                self._fail_job,
                job_id,
                message,
            )

            await self._event_bus.emit(
                EventType.JOB_FAILED,
                {
                    "job_id": job_id,
                    "error": message,
                },
                channel="jobs",
                correlation_id=job_id,
            )

            return

        async def report_progress(value: float) -> None:
            normalised = min(
                max(float(value), 0.0),
                100.0,
            )

            await asyncio.to_thread(
                self._set_progress,
                job_id,
                normalised,
            )

            await self._event_bus.emit(
                EventType.JOB_PROGRESS,
                {
                    "job_id": job_id,
                    "progress_percent": normalised,
                },
                channel="jobs",
                correlation_id=job_id,
            )

        try:
            result = await handler(
                job["payload"],
                report_progress,
            )

            await asyncio.to_thread(
                self._complete_job,
                job_id,
                result,
            )

            await self._event_bus.emit(
                EventType.JOB_COMPLETED,
                {
                    "job_id": job_id,
                    "result": result,
                },
                channel="jobs",
                correlation_id=job_id,
            )

        except asyncio.CancelledError:
            await asyncio.to_thread(
                self._requeue_running_job,
                job_id,
            )
            raise

        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"

            should_retry, priority = await asyncio.to_thread(
                self._record_failure,
                job_id,
                error_message,
            )

            if should_retry:
                if self._running and self._queue is not None:
                    await self.enqueue(
                        job_id,
                        priority=priority,
                    )
                return

            await self._event_bus.emit(
                EventType.JOB_FAILED,
                {
                    "job_id": job_id,
                    "error": error_message,
                },
                channel="jobs",
                correlation_id=job_id,
            )

            logger.exception(
                "Background job %s failed permanently.",
                job_id,
            )

    def _recover_interrupted_jobs(self) -> list[QueueItem]:
        """Reset interrupted jobs and return queue entries.

        This method runs in a worker thread. It deliberately returns ordinary
        Python values rather than touching an asyncio queue from that thread.
        """

        with SessionLocal() as session:
            jobs = session.scalars(
                select(BackgroundJob).where(
                    BackgroundJob.status.in_(
                        [
                            JobStatus.PENDING.value,
                            JobStatus.RUNNING.value,
                        ]
                    )
                )
            ).all()

            now = utcnow()

            for job in jobs:
                job.status = JobStatus.PENDING.value
                job.started_at = None
                job.queued_at = now
                session.add(job)

            session.commit()

            recovered: list[QueueItem] = []

            for job in jobs:
                created_at = job.created_at or now

                recovered.append(
                    (
                        int(job.priority),
                        created_at.timestamp(),
                        str(job.id),
                    )
                )

            return recovered

    def _claim_job(
        self,
        job_id: str,
    ) -> dict[str, Any] | None:
        with SessionLocal() as session:
            job = session.get(
                BackgroundJob,
                job_id,
            )

            if (
                job is None
                or job.status != JobStatus.PENDING.value
            ):
                return None

            job.status = JobStatus.RUNNING.value
            job.started_at = utcnow()
            job.attempts += 1

            session.commit()

            return {
                "task_name": job.task_name,
                "payload": dict(job.payload_json or {}),
            }

    def _set_progress(
        self,
        job_id: str,
        value: float,
    ) -> None:
        with SessionLocal() as session:
            job = session.get(
                BackgroundJob,
                job_id,
            )

            if (
                job is not None
                and job.status == JobStatus.RUNNING.value
            ):
                job.progress_percent = min(
                    max(float(value), 0.0),
                    100.0,
                )
                session.commit()

    def _complete_job(
        self,
        job_id: str,
        result: dict[str, Any],
    ) -> None:
        with SessionLocal() as session:
            job = session.get(
                BackgroundJob,
                job_id,
            )

            if job is None:
                return

            job.status = JobStatus.COMPLETED.value
            job.progress_percent = 100.0
            job.result_json = result
            job.completed_at = utcnow()
            job.error_message = None

            session.commit()

    def _fail_job(
        self,
        job_id: str,
        message: str,
    ) -> None:
        with SessionLocal() as session:
            job = session.get(
                BackgroundJob,
                job_id,
            )

            if job is None:
                return

            job.status = JobStatus.FAILED.value
            job.error_message = message
            job.completed_at = utcnow()

            session.commit()

    def _record_failure(
        self,
        job_id: str,
        message: str,
    ) -> tuple[bool, int]:
        with SessionLocal() as session:
            job = session.get(
                BackgroundJob,
                job_id,
            )

            if job is None:
                return False, 100

            should_retry = (
                job.attempts < job.max_attempts
                and job.status != JobStatus.CANCELLED.value
            )

            job.error_message = message

            if should_retry:
                job.status = JobStatus.PENDING.value
                job.started_at = None
                job.queued_at = utcnow()
            else:
                job.status = JobStatus.FAILED.value
                job.completed_at = utcnow()

            priority = int(job.priority)

            session.commit()

            return should_retry, priority

    def _requeue_running_job(
        self,
        job_id: str,
    ) -> None:
        with SessionLocal() as session:
            job = session.get(
                BackgroundJob,
                job_id,
            )

            if (
                job is not None
                and job.status == JobStatus.RUNNING.value
            ):
                job.status = JobStatus.PENDING.value
                job.started_at = None
                job.queued_at = utcnow()

                session.commit()


_job_manager = BackgroundJobManager()


def get_job_manager() -> BackgroundJobManager:
    return _job_manager