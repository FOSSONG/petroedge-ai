# Native Windows Development

This path runs PetroEdge AI without Docker, WSL, PostgreSQL, Redis, Kafka, or TimescaleDB. It is the best way to keep developing while WSL is broken.

## 1. Install Required Tools

Install:

- Python 3.11 from https://www.python.org/downloads/
- Node.js LTS from https://nodejs.org/
- Git for Windows from https://git-scm.com/download/win

Restart PowerShell after installation.

Verify:

```powershell
python --version
py -3.11 --version
node --version
npm --version
git --version
```

## 2. Open The Project

```powershell
cd "C:\Users\GUILIANNO FOSSONG\Documents\NCDMB PROJECT 2026"
```

Create the environment file if it does not exist:

```powershell
Copy-Item .env.example .env -ErrorAction SilentlyContinue
```

## 3. Start The Backend

Use the helper script:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\start-backend-windows.ps1
```

Keep this PowerShell window open.

Backend URLs:

- API: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## 4. Start The Frontend

Open a second PowerShell window:

```powershell
cd "C:\Users\GUILIANNO FOSSONG\Documents\NCDMB PROJECT 2026"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\start-frontend-windows.ps1
```

Open:

```text
http://127.0.0.1:5173
```

Demo login:

- Email: `admin@petroedge.ai`
- Password: `petroedge123`
- MFA code: `123456`

## 5. Run Tests

```powershell
cd "C:\Users\GUILIANNO FOSSONG\Documents\NCDMB PROJECT 2026\backend"
.\.venv\Scripts\python.exe -m pytest
```

## 6. Generate Synthetic Data

```powershell
cd "C:\Users\GUILIANNO FOSSONG\Documents\NCDMB PROJECT 2026"
.\backend\.venv\Scripts\python.exe scripts\generate_synthetic_data.py --rows 1000 --out data\generated_well_logs.csv
```

## 7. Replay LAS Data Locally

```powershell
cd "C:\Users\GUILIANNO FOSSONG\Documents\NCDMB PROJECT 2026"
.\backend\.venv\Scripts\python.exe scripts\replay_las.py --file data\sample_well.las --max-records 20
```

## 8. Production Gap

Native Windows development uses the demo in-memory services. For production parity, run Docker, Kubernetes, or cloud-managed services later:

- PostgreSQL/TimescaleDB for durable time-series storage
- Redis for cache and streaming coordination
- Kafka for real-time event transport
- MLflow for model registry and experiment tracking

