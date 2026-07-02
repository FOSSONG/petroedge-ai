# PetroEdge AI

PetroEdge AI is a real-time well logging analytics platform for hydrocarbon detection, lithology classification, anomaly detection, and reservoir characterization.

This repository is organized as a production-ready monorepo:

- `backend/` - FastAPI service, analytics pipelines, simulators, auth, tests
- `frontend/` - React, TypeScript, Tailwind CSS, Material UI dashboard
- `infra/` - PostgreSQL/TimescaleDB schema and Kubernetes manifests
- `data/` - sample LAS and CSV datasets
- `scripts/` - synthetic data generation and LAS replay helpers
- `docs/` - deployment, API, architecture, and model documentation

## Quick Start

```powershell
cp .env.example .env
docker compose up --build
```

Open:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs
- MLflow: http://localhost:5000

Demo login:

- Username: `admin@petroedge.ai`
- Password: `petroedge123`
- MFA code: `123456`

## Capabilities

- LAS, DLIS placeholder, CSV, ASCII, and WITSML ingestion interfaces
- Real-time replay simulator for LAS files over REST/Kafka-ready services
- Well log QC checks and quality scoring
- Hydrocarbon probability model
- Lithology and facies classification
- Anomaly detection
- Petrophysical calculations for porosity, water saturation, shale volume, net-to-gross, and permeability
- Real-time dashboard with tracks, crossplots, alerts, KPIs, and correlation panels
- JWT authentication, RBAC, and MFA verification hook
- Model monitoring and explainable AI endpoint
- Docker Compose, Kubernetes manifests, CI/CD, database schema, sample datasets, and automated tests

## Local Development

If Docker Desktop or WSL is unavailable, use:

- [Native Windows Development](docs/native-windows-dev.md)
- [GitHub Codespaces Development](docs/github-codespaces.md)

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Generate data:

```powershell
python scripts/generate_synthetic_data.py --rows 1000 --out data/generated_well_logs.csv
python scripts/replay_las.py --file data/sample_well.las --api http://localhost:8000
```

## Documentation

- [Architecture](docs/architecture.md)
- [API](docs/api.md)
- [Deployment](docs/deployment.md)
- [Models](docs/models.md)
- [Operations](docs/operations.md)
