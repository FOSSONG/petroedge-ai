from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from app.digital_twin import digital_twin_orchestrator
from app.events import Event, EventCreate, EventDelivery, event_bus
from app.rules import register_default_rules, rule_engine
from app.streaming.schemas import ReplayRequest, TelemetryBatch


class StreamingService:
    def __init__(self) -> None:
        register_default_rules()

    async def ingest(self, request: EventCreate) -> EventDelivery:
        event = Event(
            event_id=uuid.uuid4().hex,
            event_type=request.event_type,
            source=request.source,
            asset_id=request.asset_id,
            reservoir_id=request.reservoir_id,
            well_id=request.well_id,
            severity=request.severity,
            payload=request.payload,
            occurred_at=request.occurred_at or datetime.now(timezone.utc),
            correlation_id=request.correlation_id,
            metadata=request.metadata,
        )

        twin_updated = False
        rows = request.payload.get("rows")
        if request.reservoir_id and isinstance(rows, list):
            valid_rows = [item for item in rows if isinstance(item, dict)]
            digital_twin_orchestrator.ingest_rows(
                reservoir_id=request.reservoir_id,
                rows=valid_rows,
                source_reference=f"event:{event.event_id}",
            )
            twin_updated = True

        matched_rules, alert_ids = rule_engine.evaluate(event)
        await event_bus.publish(event)

        return EventDelivery(
            event=event,
            matched_rules=matched_rules,
            alert_ids=alert_ids,
            twin_updated=twin_updated,
        )

    async def ingest_telemetry(self, request: TelemetryBatch) -> EventDelivery:
        rows = []
        for row in request.rows:
            enriched = dict(row)
            if request.well_id and not any(
                key in enriched for key in ("Well_ID", "Well_id", "well_id")
            ):
                enriched["Well_ID"] = request.well_id
            rows.append(enriched)

        return await self.ingest(
            EventCreate(
                event_type=request.event_type,
                source="api",
                reservoir_id=request.reservoir_id,
                well_id=request.well_id,
                asset_id=request.well_id or request.reservoir_id,
                payload={"rows": rows},
                metadata=request.metadata,
            )
        )

    async def replay(self, request: ReplayRequest) -> list[EventDelivery]:
        deliveries: list[EventDelivery] = []
        delay = request.interval_seconds / request.speed
        for index, event in enumerate(request.events):
            if index and delay > 0:
                await asyncio.sleep(delay)
            replay_event = event.model_copy(update={"source": "replay"})
            deliveries.append(await self.ingest(replay_event))
        return deliveries


streaming_service = StreamingService()