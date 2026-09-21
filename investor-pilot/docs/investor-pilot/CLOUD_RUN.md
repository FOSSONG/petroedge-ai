# Cloud Run assessment: not deployed
Oracle is excluded. Duo is optional/off. No billable resources were created.

Cloud Shell can build without local Docker/WSL, as the attached plan suggests. The CLI is signed in but has no selected project. No existing project was assumed to be the intended PetroEdge project.

## Cost and access
Request-based Cloud Run currently includes 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests per billing account per month. Builds, images, storage, secrets, networking and databases have separate billing.
Minimum instances 0 permits on-demand wake-up with cold starts. Minimum instances 1 can incur idle costs. Maximum instances 1 limits scale, not spend. Budget alerts are not spending caps.
Guaranteed zero cost, unlimited external use and always-warm availability cannot all be promised.

## Before deploying
1. Select the owner's project; verify billing, free allowances and region.
2. Migrate persistent state: SQLAlchemy accounts plus separate SQLite registries and file stores. Changing DATABASE_URL alone is insufficient.
3. Use transactional durable storage for registries and object storage for files. Do not assume SQLite locking works safely on an object bucket mount.
4. Build the frontend with relative /api/v1 and use one HTTPS origin for frontend/API.
5. Bind to 0.0.0.0 and Cloud Run's PORT. Keep one backend worker until state concurrency is redesigned.
6. Move background training/replay to resumable jobs; request-based CPU and instance termination can interrupt in-process work.
7. Configure owner secrets privately with Secret Manager and restricted service-account permissions.
8. Test restart/scale-to-zero persistence, cross-account access, account revocation and pilot pause.
9. Deploy a limited pilot only after those checks; measure actual resources and configure alerts/quotas.

The current Compose deployment expects a persistent-volume host. It is not directly Cloud Run compatible. No generic deploy command is offered that would silently discard user work.

Sources checked:
https://cloud.google.com/run/pricing
https://cloud.google.com/run/docs/container-contract
https://cloud.google.com/run/docs/deploying-source-code
