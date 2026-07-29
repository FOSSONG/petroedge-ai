# Edge GRU and BiGRU Integration

PetroEdge AI treats GRU and BiGRU as temporal model families with different operating constraints.

## GRU

GRU is the default model for live edge inference because it is causal. It can process a sliding window containing the current and preceding samples without requiring future measurements.

Initial workflows:

- live well-log anomaly detection;
- digital-twin state estimation;
- drilling parameter forecasting;
- production and injection forecasting;
- emissions forecasting.

## BiGRU

BiGRU uses forward and backward temporal context. It is therefore restricted to uploaded data, historical analysis, batch processing and replay. The API rejects BiGRU requests in `live` mode.

Initial workflows:

- lithology sequence classification;
- electrofacies interpretation;
- retrospective hydrocarbon-zone detection;
- missing-log reconstruction;
- historical anomaly analysis;
- offline model recalibration.

## Model packaging

The edge service expects ONNX model artefacts under `backend/models/edge`. Each production artefact must be accompanied by a manifest containing the model ID, version, workflow, input feature schema, window size, checksum and runtime requirements.

When no ONNX artefact is installed, the demonstration release uses a deterministic fallback. This allows the workflow and API to be demonstrated, but it is not a trained geological model and must not be represented as one.

## API

- `GET /api/v1/edge/capabilities`
- `POST /api/v1/edge/temporal/predict`

The response includes model provenance, execution mode, runtime, fallback status, score, confidence and latency.
