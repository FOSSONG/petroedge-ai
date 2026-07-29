# PetroEdge Model Platform

## MVP capabilities

- Task-based model registry with version, lifecycle stage, metrics and feature schema.
- User-selectable inference through `POST /api/v1/models/infer`.
- Default model per analytical task with authorised promotion and rollback.
- Lazy model loading with bounded in-memory cache.
- Scikit-learn, XGBoost/joblib and ONNX adapter interfaces.
- CSV and Parquet training datasets contained inside `dataset_store`.
- Random, grouped-by-well and temporal validation.
- Model comparison, health checks and optional SHAP explanations.
- Local-first deployment with no paid service requirement.

## Deployment principles

1. Keep data and models portable. Do not couple the application to one cloud provider.
2. Use open formats: CSV, Parquet, JSON, joblib and ONNX.
3. Prefer grouped-by-well or temporal validation over random row splits for geoscience data.
4. Separate model artefacts, dataset artefacts and experiment metadata.
5. Permit production inference only from validated, staging or production models.
6. Preserve a default fallback model for every critical task.

## Scale path

- Small: pandas, scikit-learn and local workers.
- Medium: Parquet, Polars, chunked inference and XGBoost histogram training.
- Large: optional Dask, Ray or Spark workers and object storage.
- Streaming: Kafka/WITSML ingestion, micro-batches and online monitoring.

The distributed and deep-learning dependency groups are intentionally optional so the MVP remains portable and affordable.