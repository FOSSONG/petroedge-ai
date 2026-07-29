from fastapi import APIRouter, WebSocket
import asyncio
import json
import random

router = APIRouter()

@router.websocket("/stream")
async def stream_logs(websocket: WebSocket):

    await websocket.accept()

    while True:

        payload = {
            "depth_m": round(random.uniform(2000, 3500), 2),
            "gamma_ray_api": round(random.uniform(15, 150), 2),
            "resistivity_ohmm": round(random.uniform(0.5, 200), 2),
            "density_gcc": round(random.uniform(2.0, 2.8), 2),
            "neutron_porosity_vv": round(random.uniform(0.05, 0.35), 3),
        }

        await websocket.send_text(
            json.dumps(payload)
        )

        await asyncio.sleep(2)