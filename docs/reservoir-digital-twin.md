# PetroEdge Reservoir Digital Twin

## Scope

The Digital Twin maintains an auditable in-memory reservoir and well state that can be updated by users, workflows, models, agents and future streaming integrations.

## Core capabilities

- Reservoir and well state management
- Health and risk scoring
- Versioned snapshots
- Historical restore
- What-if simulations
- Workflow ingestion through `digital_twin.update`
- REST API under `/api/v1/twins`

## API endpoints

- `GET /api/v1/twins`
- `POST /api/v1/twins`
- `GET /api/v1/twins/{reservoir_id}`
- `PATCH /api/v1/twins/{reservoir_id}`
- `DELETE /api/v1/twins/{reservoir_id}`
- `GET /api/v1/twins/{reservoir_id}/health`
- `GET /api/v1/twins/{reservoir_id}/history`
- `POST /api/v1/twins/{reservoir_id}/restore/{version}`
- `POST /api/v1/twins/{reservoir_id}/simulate`

## Persistence boundary

This sprint uses an in-memory registry and history store to validate the domain model and API contract. Production persistence should be implemented with the existing database layer in the next hardening sprint.