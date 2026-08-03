# PetroEdge AI Frontend — Milestone 2

## Implemented

- AI Workspace landing page backed by `/api/v1/platform/overview`
- Dataset Registry with authenticated CSV, Parquet and LAS upload
- Dataset search, status, dimensions, file size and schema detail views
- Experiment Manager with dataset, task, algorithm and validation selection
- React Query caching and invalidation across platform resources
- Navigation integration for AI Workspace, Datasets and Experiments
- Existing Operations, Well Logs, Alerts, Models, Jobs and Live Events preserved

## Backend endpoints used

- `GET /api/v1/platform/overview`
- `GET /api/v1/platform/datasets`
- `POST /api/v1/platform/datasets`
- `GET /api/v1/platform/experiments`
- `POST /api/v1/platform/experiments`
- `GET /api/v1/models`

## Validation

TypeScript validation completed successfully with `tsc --noEmit`.
The Linux packaging environment could not execute the uploaded Windows `node_modules` Vite native binding. Run `npm install` and `npm run build` on the target Windows environment to generate the production bundle.
