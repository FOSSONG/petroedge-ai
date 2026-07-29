# PetroEdge AI Workflow Engine

The workflow engine executes validated directed acyclic graphs of reusable processing nodes.

## Built-in templates

- `well_log_interpretation`
- `production_forecast`
- `historical_replay`

## Built-in node types

- `input.payload`
- `qc.basic`
- `features.summary`
- `petrophysics.basic`
- `ai.model`
- `report.summary`
- `storage.passthrough`

## API

- `GET /api/v1/workflows`
- `GET /api/v1/workflows/templates`
- `GET /api/v1/workflows/nodes`
- `POST /api/v1/workflows`
- `GET /api/v1/workflows/{workflow_id}`
- `POST /api/v1/workflows/{workflow_id}/run`
- `GET /api/v1/workflows/{workflow_id}/status`
- `GET /api/v1/workflows/runs/{run_id}`

The first implementation deliberately separates model capability resolution from trained-model inference. This prevents the platform from claiming predictions when no trained artefact or executable model adapter is available.