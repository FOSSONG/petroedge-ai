# Release 2.3 Validation Report

## Passed
- Python source compilation (`python -m compileall app`).
- SQLite forward migration: 27 dataset fields present, including version, type, checksum, units, metadata and processing fields.
- Dataset lineage table creation.
- Plotly regression check: exactly one `PlotlyModule` import, one `PlotlyRuntime`, one local `Plot` component, and zero `react-plotly.js` wrapper references in Edge Computing.
- `package.json` and `package-lock.json` JSON integrity.
- Existing Docker persistence mounts retained for data, dataset, model and experiment stores.

## Environment-limited checks
- npm dependency installation could not complete because the execution environment's private npm mirror returned 404 for `yocto-queue@0.1.0`.
- Full FastAPI import and pytest execution could not run because the execution environment lacks installed project dependencies, beginning with `python-jose`.

These are dependency availability limitations in the packaging sandbox. Docker installs dependencies from `pyproject.toml`; ReportLab and openpyxl are now mandatory dependencies so report routes load in the deployed backend.
