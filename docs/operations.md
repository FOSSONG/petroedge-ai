# Operations

## Security

- JWT bearer tokens protect all operational APIs.
- RBAC roles are `admin`, `geoscientist`, `engineer`, and `viewer`.
- MFA is implemented as a verification hook. The demo accepts `123456`; production should connect this to TOTP or an identity provider.

## Observability

- `/health` is used by Docker and Kubernetes probes.
- Model monitoring is exposed by `/api/v1/monitoring/models`.
- MLflow is included for model experiment and artifact tracking.

## Data Retention

TimescaleDB hypertables are used for `log_samples` and `analytics_results`. Production deployments should add retention and compression policies according to regulatory and operational needs.

