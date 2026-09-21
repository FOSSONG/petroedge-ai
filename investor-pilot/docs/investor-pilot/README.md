# Investor pilot 045
Read FEATURE_GUIDE.md for capabilities and scientific limits, CLOUD_RUN.md for hosting constraints, and VALIDATION.md for verification.

## Local development
Use Python 3.12 and Node 22.12+.
From backend: create a virtual environment and run pip install -e ".[dev]".
Copy backend/.env.example to backend/.env and replace all placeholders privately.
For local first-account setup leave PILOT_OWNER_EMAIL unset. Start uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 from backend.
From frontend: npm ci; copy .env.example to .env; npm run dev.
Complete first-account setup locally. Before external use configure PILOT_OWNER_EMAIL to disable public bootstrap.
The deployment start_backend.py initializes an empty database using the explicitly configured owner and never replaces an existing account. No default password is distributed.

Prepared training tables and the raw collection are not published. Reattach a local prepared catalog with PETROEDGE_PREPARED_CATALOG.
Model artifacts remain research-only. Presence in Git does not imply production qualification.
