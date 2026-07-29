# PetroEdge real-time events integration

This integration adds an in-process event bus and a central WebSocket connection manager.

## Endpoint

`ws://127.0.0.1:8000/api/v1/realtime/ws?channels=global`

Multiple channels can be supplied as a comma-separated list, for example:

`ws://127.0.0.1:8000/api/v1/realtime/ws?channels=global,job:JOB_ID,well:GABO-18`

## Client messages

```json
{"action": "ping"}
```

```json
{"action": "subscribe", "channels": ["job:JOB_ID", "well:GABO-18"]}
```

```json
{"action": "unsubscribe", "channels": ["job:JOB_ID"]}
```

## HTTP checks

- `GET /api/v1/realtime/health`
- `POST /api/v1/realtime/test-event`

## Events currently broadcast

- `system.ready`
- `system.shutdown`
- `job.queued`
- `job.started`
- `job.progress`
- `job.completed`
- `job.failed`
- `alert.created`
- `alert.updated`

The database remains the source of truth. WebSocket events provide immediate UI updates and do not replace persistent records.
