# Edge ONNX model artefacts

Place compatible trained models here:

- `gru_live.onnx` for causal/live GRU inference
- `bigru_replay.onnx` for BiGRU historical/replay inference

The Docker Compose volume mounts `backend/model_store` at `/app/model_store`, and Release 2.1 resolves these files from `/app/model_store/edge`.

Without a compatible file, the application continues to run the progressive simulator but labels results as `deterministic-demo-fallback`. This is deliberate and prevents simulated scores from being presented as trained model predictions.
