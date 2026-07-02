import argparse
import json
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.schemas import WellLogSample  # noqa: E402
from app.services.analytics import analyze_sample  # noqa: E402
from app.services.las_parser import parse_las  # noqa: E402


def post_json(url: str, payload: dict, token: str | None) -> None:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=10) as response:
        response.read()


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a LAS file through the PetroEdge analytics API.")
    parser.add_argument("--file", default="data/sample_well.las")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--interval-ms", type=int, default=250)
    parser.add_argument("--max-records", type=int, default=100)
    parser.add_argument("--token", default=None)
    args = parser.parse_args()

    rows = parse_las(args.file, max_records=args.max_records)
    for row in rows:
        sample = WellLogSample(**row)
        result = analyze_sample(sample)
        print(json.dumps(result.model_dump(mode="json")))
        if args.token:
            post_json(f"{args.api}/api/v1/analytics/sample", sample.model_dump(mode="json"), args.token)
        time.sleep(args.interval_ms / 1000)


if __name__ == "__main__":
    main()

