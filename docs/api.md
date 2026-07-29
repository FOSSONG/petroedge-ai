# API Documentation

Interactive OpenAPI documentation is available at `/docs` when the backend is running.

Core endpoints:

- `POST /api/v1/auth/login` - JWT login with MFA code.
- `POST /api/v1/ingestion/upload` - upload LAS, CSV, ASCII, DLIS, or WITSML registration payloads.
- `POST /api/v1/streaming/replay` - stream analyzed LAS records as server-sent events.
- `POST /api/v1/analytics/sample` - run QC, AI predictions, petrophysics, and explainability for one sample.
- `POST /api/v1/analytics/petrophysics` - calculate reservoir properties.
- `GET /api/v1/wells` - list wells.
- `GET /api/v1/wells/{well_id}/logs` - return demo or synthetic well logs.
- `GET /api/v1/alerts` - list alert center events.
- `POST /api/v1/alerts/evaluate` - evaluate a sample against alert rules.
- `GET /api/v1/reports/{well_id}/summary` - generate report metadata.
- `GET /api/v1/monitoring/models` - model registry and drift metrics.

Authentication:

```json
{
  "username": "admin@petroedge.ai",
  "password": "petroedge123",
  "mfa_code": "123456"
}
```

