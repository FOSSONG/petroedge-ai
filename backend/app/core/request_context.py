from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger("petroedge.requests")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Adds request IDs, latency headers and structured request logs."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "Unhandled request failure.",
                extra={
                    "event": "request_failed",
                    "component": "http",
                    "duration_ms": duration_ms,
                    "status": 500,
                },
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error.",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(duration_ms)

        logger.info(
            "%s %s -> %s",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "event": "request_completed",
                "component": "http",
                "duration_ms": duration_ms,
                "status": response.status_code,
            },
        )
        return response