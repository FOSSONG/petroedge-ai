import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from app.schemas import WellLogSample
from app.services.analytics import analyze_sample
from app.services.las_parser import parse_las


async def replay_las(path: str, interval_ms: int, max_records: int) -> AsyncIterator[dict]:
    for row in parse_las(path, max_records=max_records):
        sample = WellLogSample(**row, timestamp=datetime.now(timezone.utc))
        result = analyze_sample(sample)
        yield result.model_dump(mode="json")
        await asyncio.sleep(interval_ms / 1000)

