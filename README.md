# PetroEdge AI MVP

PetroEdge AI MVP is a CPU-first petroleum intelligence platform for well-log ingestion, petrophysical interpretation, water/oil/gas screening, model evaluation, multi-agent workflows and report generation.

## MVP capabilities

- Reservoir Intelligence with interactive synchronized depth plots
- Explicit water, oil, gas and residual-hydrocarbon screening
- Interactive logs and PDF report export
- Dataset, asset and operations integration
- Model Evaluation Centre with crash-safe metric handling
- Persistent light and dark modes
- FastAPI backend, React frontend and Docker deployment

## Local installation on Windows

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\APPLY_FINAL_MVP.ps1
```

Start the backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Start the frontend in a second PowerShell window:

```powershell
cd frontend
npm run dev
```

## Docker

```powershell
docker compose up --build
```

Frontend: `http://localhost:5173`  
API documentation: `http://localhost:8000/docs`

## Engineering limitation

Fluid typing is decision support. Oil and gas interpretations should be confirmed with pressure gradients, formation testing, mud-gas, PVT, fluid samples or production evidence.
