import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.synthetic import write_csv  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic PetroEdge well log data.")
    parser.add_argument("--rows", type=int, default=500)
    parser.add_argument("--out", default="data/generated_well_logs.csv")
    args = parser.parse_args()

    output = write_csv(args.out, rows=args.rows)
    print(f"Wrote {args.rows} rows to {output}")


if __name__ == "__main__":
    main()

