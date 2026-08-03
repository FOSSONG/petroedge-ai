# PetroEdge AI Release 2: Edge Computing

Release 2 extends the working Release 1 baseline without replacing its navigation, theme, authentication, WebSocket stack, AI Workflows or CCUS modules.

## Implemented

- Persistent edge-device registry stored in `backend/data/edge_runtime.json`.
- Device capability profiles and heartbeat endpoint.
- Versioned GRU/BiGRU model assignment to devices.
- Dataset-driven rig-site replay using sliding temporal windows.
- Real inference-service execution with optional ONNX Runtime.
- Explicit `fallback` and `runtime` fields when no ONNX artefact is installed.
- Offline result queue and manual synchronisation.
- Persistent run history, latency metrics, inference counts and deployment history.
- Release 2 Edge Computing dashboard with device, deployment, replay and history views.

## Important scientific-status rule

A run with `fallback: true` uses the deterministic baseline implemented for deployment validation. It must not be represented as a trained GRU/BiGRU scientific model result. Install a compatible ONNX model artefact to obtain real neural-network inference.

## Build and start

```powershell
Set-Location "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-2-Edge-Computing"
docker compose up -d --build
docker compose ps
```
