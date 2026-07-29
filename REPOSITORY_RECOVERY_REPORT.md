# PetroEdge AI Repository Recovery Report

## Canonical source selected

- Backend: original `backend2/`
- Frontend: original `frontend2/`

These trees contain the most complete integrated platform, including authentication, RBAC, real-time events, background jobs, model platform, reservoir intelligence, plugin registry and the current frontend module hub.

## Removed from the active release

- duplicated `backend/backend2` and `frontend/frontend2` trees;
- sprint patch folders and dated backup folders;
- in-source `.bak` files;
- Python caches and test caches;
- generated reports and transient runtime model/experiment output.

The original uploaded archive remains unchanged and is the recovery source for historical material.

## Consolidated target layout

- `backend/`
- `frontend/`
- `demo_data/`
- `docs/`
- `deployment/`
- `infra/`
- `scripts/`

## New implementation added

- first-class edge API route;
- GRU causal live-inference contract;
- BiGRU replay/batch/historical contract;
- optional ONNX Runtime execution;
- deterministic demonstration fallback with explicit disclosure;
- GRU/BiGRU tests and technical documentation.

## Known environment issue

The uploaded backend declares Python 3.11 to 3.12. Running it under Python 3.13 is unsupported. The project must use a Python 3.11 virtual environment and install the backend dependencies, including `python-jose[cryptography]`, before the full test suite can run.
