import asyncio
import random


async def replay_las(
    las_path: str,
    interval_ms: int = 500,
    max_records: int = 100,
):

    for i in range(max_records):

        yield {
            "depth": 1000 + i,
            "gamma_ray": round(
                random.uniform(20, 120),
                2,
            ),
            "resistivity": round(
                random.uniform(1, 200),
                2,
            ),
        }

        await asyncio.sleep(
            interval_ms / 1000
        )