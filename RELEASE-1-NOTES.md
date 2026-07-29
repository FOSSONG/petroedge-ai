# PetroEdge AI Release 1

## Implemented

- Preserved the deployed Nginx `/api/v1` reverse-proxy architecture.
- Preserved relative WebSocket URL construction for localhost and Cloudflare `ws`/`wss` operation.
- Reordered the scientific navigation as requested.
- Added **AI Workflows** as the first workspace.
- Connected AI Workflows to the existing FastAPI workflow engine and dataset previews.
- Added a deployment-safe **CCUS** workspace boundary without fabricated scientific outputs.
- Grouped Operations, Models, Alerts, Jobs and Live Events under one dropdown tab.
- Added PowerShell backup and validation scripts.

## Intentionally unchanged

Release 1 does not alter:

- reservoir petrophysical calculations;
- training estimators;
- model registry behaviour;
- AI Agent reasoning;
- edge inference algorithms;
- database schema;
- authentication;
- persistent data volumes.

These remain scheduled for subsequent controlled releases.

## PowerShell deployment

Run from the project root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\backup-working-mvp.ps1 -ExportDockerImages
docker compose config
docker compose build
docker compose up -d --force-recreate
docker compose ps
```

After confirming the interface, run:

```powershell
.\scripts\validate-release1.ps1
```

Cloudflare should continue to expose only:

```text
http://localhost:5173
```
