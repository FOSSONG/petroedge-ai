from __future__ import annotations

import csv
import json
import uuid
from pathlib import Path
from typing import BinaryIO

from app.platform_v1.database import audit, connection, utcnow
from app.platform_v1.schemas import DatasetSummary
from app.preprocessing.curve_aliases import canonical_name_for

ALLOWED_EXTENSIONS = {".csv", ".parquet", ".las"}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024


def storage_root() -> Path:
    root = Path.cwd() / "dataset_store"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def profile_csv(path: Path):
    rows = 0
    columns: list[str] = []
    missing: dict[str, int] = {}
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        missing = {column: 0 for column in columns}
        for row in reader:
            rows += 1
            for column in columns:
                value = row.get(column)
                if value is None or not str(value).strip():
                    missing[column] += 1
    return rows, columns, missing


def profile_parquet(path: Path):
    import pandas as pd
    frame = pd.read_parquet(path)
    return int(len(frame)), [str(c) for c in frame.columns], {str(k): int(v) for k, v in frame.isna().sum().items()}


def profile_las(path: Path):
    import lasio
    las = lasio.read(path)
    columns = [str(curve.mnemonic) for curve in las.curves]
    return len(las.index), columns, {column: 0 for column in columns}


def register_upload(name: str, description: str | None, filename: str, stream: BinaryIO, owner_id: str | None) -> DatasetSummary:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported type {suffix}. Use CSV, Parquet or LAS.")

    dataset_id = f"ds-{uuid.uuid4().hex[:12]}"
    destination = storage_root() / f"{dataset_id}{suffix}"
    size = 0
    with destination.open("wb") as output:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                destination.unlink(missing_ok=True)
                raise ValueError("Dataset exceeds the 500 MB MVP limit.")
            output.write(chunk)

    try:
        if suffix == ".csv":
            rows, columns, missing = profile_csv(destination)
        elif suffix == ".parquet":
            rows, columns, missing = profile_parquet(destination)
        else:
            rows, columns, missing = profile_las(destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    now = utcnow()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO datasets(dataset_id, name, description, source_type, file_path, file_name, file_size_bytes, row_count, column_count, columns_json, missing_json, status, owner_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (dataset_id, name, description, suffix.lstrip("."), str(destination), filename, size, rows, len(columns), json.dumps(columns), json.dumps(missing), "ready", owner_id, now, now),
        )
    mapping = {column: canonical_name_for(column) for column in columns if canonical_name_for(column)}
    audit("dataset.registered", "dataset", dataset_id, owner_id, {"file_name": filename, "curve_mapping": mapping})
    return get_dataset(dataset_id)


def _row_to_model(row) -> DatasetSummary:
    return DatasetSummary(
        dataset_id=row["dataset_id"], name=row["name"], description=row["description"], source_type=row["source_type"],
        file_name=row["file_name"], file_size_bytes=row["file_size_bytes"], row_count=row["row_count"],
        column_count=row["column_count"], columns=json.loads(row["columns_json"]), missing_values=json.loads(row["missing_json"]),
        status=row["status"], owner_id=row["owner_id"], created_at=row["created_at"], updated_at=row["updated_at"]
    )


def list_datasets() -> list[DatasetSummary]:
    with connection() as conn:
        rows = conn.execute("SELECT * FROM datasets ORDER BY created_at DESC").fetchall()
    return [_row_to_model(row) for row in rows]


def get_dataset(dataset_id: str) -> DatasetSummary:
    with connection() as conn:
        row = conn.execute("SELECT * FROM datasets WHERE dataset_id = ?", (dataset_id,)).fetchone()
    if row is None:
        raise KeyError(dataset_id)
    return _row_to_model(row)

def get_dataset_path(dataset_id: str) -> Path:
    with connection() as conn:
        row = conn.execute("SELECT file_path FROM datasets WHERE dataset_id = ?", (dataset_id,)).fetchone()
    if row is None:
        raise KeyError(dataset_id)
    path = Path(row["file_path"])
    if not path.exists():
        raise FileNotFoundError(f"Dataset file is missing: {path}")
    return path


def preview_dataset(dataset_id: str, limit: int = 500):
    import pandas as pd
    path = get_dataset_path(dataset_id)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path, nrows=limit)
    elif suffix == ".parquet":
        frame = pd.read_parquet(path).head(limit)
    elif suffix == ".las":
        import lasio
        las = lasio.read(path)
        frame = las.df().reset_index().head(limit)
    else:
        raise ValueError("Unsupported dataset type.")
    frame = frame.replace({float("inf"): None, float("-inf"): None})
    frame = frame.where(frame.notna(), None)
    summary = get_dataset(dataset_id)
    return {
        "dataset_id": dataset_id,
        "columns": [str(c) for c in frame.columns],
        "rows": frame.to_dict(orient="records"),
        "total_rows": int(summary.row_count or len(frame)),
    }


def delete_dataset(dataset_id: str, actor_id: str | None = None) -> None:
    """Delete a dataset record and its stored file atomically enough for local MVP use."""
    with connection() as conn:
        row = conn.execute(
            "SELECT file_path, file_name FROM datasets WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchone()
        if row is None:
            raise KeyError(dataset_id)
        conn.execute("DELETE FROM experiments WHERE dataset_id = ?", (dataset_id,))
        conn.execute("DELETE FROM datasets WHERE dataset_id = ?", (dataset_id,))
    Path(row["file_path"]).unlink(missing_ok=True)
    audit("dataset.deleted", "dataset", dataset_id, actor_id, {"file_name": row["file_name"]})
