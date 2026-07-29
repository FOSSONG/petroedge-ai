# PetroEdge Version 1.0: Milestone 1

## Architecture consolidation completed

This backend revision stabilises application startup and establishes the model platform as the sole runtime model-loading path.

### Corrections

- Repaired the malformed `ROUTE_MODULES` entry in `app/main.py`.
- Registered the Version 1 platform router separately at `/api/v1/platform`.
- Removed the monitoring route's dependency on the models API route.
- Added `app/ml_platform/catalog.py` as the central model-status catalogue.
- Preserved `_discover_models()` as a backward-compatible wrapper only.
- Removed import-time `joblib.load()` calls from analytics.
- Routed hydrocarbon and lithology inference through `ModelService`.
- Added a public `ModelService.explain()` interface.
- Removed SHAP service access to the private `_adapter()` method.
- Refactored the offline SHAP importance utility to use the central model service.
- Added the missing public `permeability()` function required by the petrophysics tests.
- Strengthened requested-model fallback validation.
- Added XGBoost to core runtime dependencies because the bundled production model requires it.
- Added architecture regression tests.

### Runtime model-loading rule

Only `app/ml_platform/adapters.py` loads serialised model artefacts. API routes and domain services use `get_model_service()`.

### Validation performed

- All Python files passed AST parsing.
- The complete backend passed `compileall`.
- Route tuple structure was verified statically.
- Runtime services were checked for direct `joblib.load()` usage.

Full pytest execution could not be completed in the packaging environment because its Python installation does not contain the project's external dependencies and internet package installation is unavailable. The supplied Windows project environment should install `requirements-windows-dev.txt` before running the tests.

### Local verification

```powershell
cd "C:\Users\GUILIANNO FOSSONG\Documents\NCDMB PROJECT 2026\backend2"

.\.venv\Scripts\python.exe -m pip install -r requirements-windows-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Expected application checks:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`
- `GET /api/v1/monitoring/health`
- `GET /api/v1/models`
- `GET /api/v1/platform/overview`
