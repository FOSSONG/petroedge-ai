# Architecture

PetroEdge AI uses a modular platform architecture:

1. Ingestion accepts LAS, CSV, ASCII, DLIS placeholders, and WITSML stream registrations.
2. Streaming services replay samples from LAS files and are designed to publish to Kafka topics.
3. FastAPI exposes analytics, wells, alerts, reporting, and model monitoring APIs.
4. PostgreSQL with TimescaleDB stores time-series log samples and model outputs.
5. Redis is reserved for low-latency cache, stream checkpoints, and alert fan-out.
6. MLflow tracks trained PyTorch, TensorFlow, and Scikit-learn model versions.
7. React renders operational dashboards for log tracks, crossplots, correlation, alerts, KPIs, and explainability.

The initial implementation includes deterministic model baselines so the product works locally immediately. Those baselines are isolated under `backend/app/services`, making them straightforward to replace with trained model artifacts loaded from MLflow.

