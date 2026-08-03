# PetroEdge AI Release 4.1.1

## Changes

- Added permanent deletion of registered lifecycle models.
- Added a confirmation dialogue, including a production-stage warning.
- Deletes the registry entry and corresponding model artefact directory transactionally.
- Replaced JSON prediction previews with a scrollable tabular preview.
- Displays up to the first 100 prediction rows while retaining the complete CSV output.
- Increased the Nginx request-body limit to 1 GB for dataset uploads.

## Deployment

Run `docker compose build --no-cache` followed by `docker compose up -d`.
Existing datasets, model artefacts and experiment stores remain mounted from the project directories.
