# PetroEdge Real-Time Streaming and Event Processing

## Scope

Sprint 5 introduces an event-driven operational layer for PetroEdge.

## Components

- Asynchronous in-process event bus
- REST event ingestion
- Telemetry batch ingestion
- WebSocket event broadcasting
- Configurable rule engine
- Operational alert lifecycle
- Digital Twin updates from telemetry
- Historical replay

## Endpoints

- `POST /api/v1/streaming/events`
- `POST /api/v1/streaming/telemetry`
- `POST /api/v1/streaming/replay`
- `WS /api/v1/streaming/ws`
- `GET /api/v1/events`
- `GET /api/v1/alerts`
- `PATCH /api/v1/alerts/{alert_id}`
- `GET /api/v1/rules`
- `POST /api/v1/rules`
- `DELETE /api/v1/rules/{rule_id}`

## Production boundary

This sprint validates the event contracts and processing model with an in-process bus. Kafka, MQTT, Redis Streams or another durable broker can be introduced behind the same service interfaces in the infrastructure hardening milestone.