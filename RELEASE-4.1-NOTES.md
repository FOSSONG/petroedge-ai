# PetroEdge AI Release 4.1

## Integrated fixes

- Registered the existing `training_lifecycle` FastAPI router at `/api/v1/training-lifecycle`.
- Promoted the lifecycle route to a required startup module so a broken model lifecycle cannot fail silently.
- Added explicit React Query result types for datasets, algorithms, models, previews and predictions.
- Preserved the existing dark theme and first-class workspace navigation.
- Updated the visible release identifier and backend application version to 4.1.0.
- Removed obsolete patch, backup and diagnostic artefacts from the distributable package.

## Validation

Run `VALIDATE-RELEASE-4.1.ps1` from the repository root. It validates source syntax, builds the Docker images, starts the stack, checks backend health and confirms lifecycle route registration.
