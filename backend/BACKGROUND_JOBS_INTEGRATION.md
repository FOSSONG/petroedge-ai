# PetroEdge Background Jobs Integration

This integration adds a persistent asynchronous job queue for work that should not block an HTTP request, such as LAS preprocessing, batch inference, report generation, and future model training.

## Current built-in tasks

- `system.echo`: verifies submission, execution, persistence and result retrieval.
- `system.delay`: verifies progress reporting, cancellation state and worker behaviour.

Domain handlers can be registered with `get_job_manager().register(task_name, handler)` without changing the API contract.

## Endpoints

- `POST /api/v1/jobs`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/health`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/cancel`

## Deployment note

The included manager is designed for development and single-instance deployment. It stores job state in SQL, recovers interrupted jobs at startup, supports retries, and keeps the frontend contract stable. When PetroEdge is deployed with several API replicas, replace the in-process queue with Celery, Dramatiq or RQ backed by Redis/RabbitMQ while retaining the `background_jobs` table and REST endpoints.
