from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

JobHandler = Callable[[dict[str, Any], Callable[[float], Awaitable[None]]], Awaitable[dict[str, Any]]]


async def echo_handler(
    payload: dict[str, Any],
    report_progress: Callable[[float], Awaitable[None]],
) -> dict[str, Any]:
    await report_progress(25.0)
    await asyncio.sleep(0)
    await report_progress(100.0)
    return {"echo": payload}


async def delay_handler(
    payload: dict[str, Any],
    report_progress: Callable[[float], Awaitable[None]],
) -> dict[str, Any]:
    seconds = float(payload.get("seconds", 1.0))
    seconds = min(max(seconds, 0.0), 300.0)
    steps = max(1, min(int(seconds * 4) or 1, 100))
    for step in range(steps):
        await asyncio.sleep(seconds / steps if seconds else 0)
        await report_progress(((step + 1) / steps) * 100.0)
    return {"slept_seconds": seconds}


DEFAULT_HANDLERS: dict[str, JobHandler] = {
    "system.echo": echo_handler,
    "system.delay": delay_handler,
}
