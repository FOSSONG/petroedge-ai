# PetroEdge AI Phase 2 Backend Refactor

This package coordinates SQLAlchemy repositories, FastAPI dependency injection, service-layer business logic, ORM-backed alerts, persistent ingestion registration, and persisted sample analytics.

## Key changes

- `app/api/dependencies.py`: typed FastAPI providers for the database and repositories.
- `app/db/repositories/domain.py`: query and state-change operations for users, wells, datasets, models, predictions, and alerts.
- `app/services/domain_services.py`: authentication, well serialization, ingestion persistence, and analytics persistence.
- `app/services/alert_engine.py`: replaces JSONL alert persistence with the `alerts` ORM table.
- `auth.py`: authenticates through `UserRepository` and records last login.
- `wells.py`: uses ORM wells and ORM-backed alerts.
- `alerts.py`: adds database filtering and alert status updates.
- `analytics.py`: persists each sample result and evaluates alerts.
- `ingestion.py`: stores the source file and creates a dataset record.
- `monitoring.py`: reads alert metrics from the database repository.
- `las_parser.py` and `upload.py`: load LAS support lazily and return a clear error if `lasio` is missing.

## Install and verify

```powershell
cd "C:\Users\GUILIANNO FOSSONG\Documents\NCDMB PROJECT 2026\backend"
.\.venv\Scripts\Activate.ps1
pip install -r requirements-windows-dev.txt
python -m compileall app alembic
alembic upgrade head
python -c "from app.main import app; print(len(app.routes)); print(app.state.route_modules)"
uvicorn app.main:app --reload
```

The backend import was verified with all configured route modules loaded.
