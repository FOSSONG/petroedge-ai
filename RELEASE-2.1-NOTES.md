# Release 2.1: Real-Time Edge Replay Correction

Corrections:

- replaces the single blocking replay request with a progressive replay job;
- updates the UI approximately every 400 ms;
- displays prediction count, progress, latest score, confidence and latency while replay is running;
- resolves GRU/BiGRU ONNX artefacts from `backend/model_store/edge`;
- retains an explicitly labelled deterministic fallback when no trained ONNX model is installed;
- includes Alembic files in the backend Docker image.

Expected model filenames:

- `backend/model_store/edge/gru_live.onnx`
- `backend/model_store/edge/bigru_replay.onnx`
