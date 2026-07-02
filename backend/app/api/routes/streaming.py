import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.rbac import require_roles
from app.schemas import ReplayRequest
from app.services.simulator import replay_las

router = APIRouter()


@router.post("/replay")
async def replay(
    request: ReplayRequest,
    _: dict = Depends(require_roles("admin", "geoscientist", "engineer", "viewer")),
) -> StreamingResponse:
    async def event_stream():
        async for result in replay_las(request.las_path, request.interval_ms, request.max_records):
            yield f"data: {json.dumps(result)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

