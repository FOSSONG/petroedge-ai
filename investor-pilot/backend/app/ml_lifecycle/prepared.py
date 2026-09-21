"""Server-owned prepared-data contracts and immutable group split assignments."""
from pathlib import Path
import hashlib
import json
import os
import pandas as pd

DEFAULT_CATALOG = Path(__file__).resolve().parents[4] / "data/prepared/platform_manifest_001.json"

def catalog():
    path = Path(os.environ.get("PETROEDGE_PREPARED_CATALOG", str(DEFAULT_CATALOG))).resolve()
    if not path.is_file():
        return path, {}, None
    raw = path.read_bytes()
    payload = json.loads(raw)
    return path, payload["datasets"], hashlib.sha256(raw).hexdigest()

def entries():
    _, items, _ = catalog()
    return [{"dataset_id": key, "name": value["name"], "rows": value["rows"],
             "target": value["target_definition"], "condition": value["condition"],
             "status": "approved_contract" if value.get("quality_approved") and value.get("assignments") else "blocked",
             "reason": value.get("blocked_reason", ""),
             "feature_columns": value["feature_columns"]} for key, value in items.items()]

def locked_partitions(frame, assignments):
    required = {"specimen_id", "split_group_id"}
    if not required.issubset(frame.columns):
        raise ValueError("Locked split requires specimen_id and split_group_id.")
    for column in required:
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise ValueError("Locked split identifiers cannot be missing or blank.")
    ids = frame["specimen_id"].astype(str)
    if ids.duplicated().any():
        raise ValueError("Each specimen must have one row per target contract.")
    if set(ids) != set(assignments):
        raise ValueError("Locked assignments must cover exactly the dataset specimens.")
    labels = ids.map(assignments)
    if set(labels) != {"train", "validation", "test"}:
        raise ValueError("Locked split requires nonempty train, validation and test partitions.")
    check = pd.DataFrame({"group": frame["split_group_id"].astype(str), "partition": labels})
    if check.groupby("group")["partition"].nunique().gt(1).any():
        raise ValueError("Parent-well leakage: a group crosses partition boundaries.")
    return tuple(frame.loc[labels.eq(part)].copy() for part in ("train", "validation", "test"))

def load_prepared(config):
    path, items, catalog_hash = catalog()
    item = items.get(config.dataset_id)
    if item is None:
        raise ValueError("Unknown prepared dataset identifier.")
    if not item.get("quality_approved") or not item.get("assignments"):
        raise ValueError("Prepared dataset blocked: " + item.get("blocked_reason", "Quality approval and locked split are required."))
    if config.target_column != item["target_column"] or config.feature_columns != item["feature_columns"]:
        raise ValueError("Prepared feature order and target must match the approved contract.")
    if config.task_type.value != item["task_type"]:
        raise ValueError("Task type differs from prepared target contract.")
    if config.validation_strategy.value != "grouped" or config.group_column != "split_group_id":
        raise ValueError("Prepared training requires grouped validation on split_group_id.")
    source = (path.parent / item["path"]).resolve()
    if not source.is_relative_to(path.parent) or source.suffix.lower() != ".csv":
        raise ValueError("Prepared dataset path is outside the catalog root or is not CSV.")
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != item["sha256"]:
        raise ValueError("Prepared dataset checksum mismatch.")
    from io import BytesIO
    frame = pd.read_csv(BytesIO(raw))
    if len(frame) != item["rows"]:
        raise ValueError("Prepared dataset row count mismatch.")
    for column, expected in item.get("constant_columns", {}).items():
        if column not in frame or frame[column].isna().any() or set(frame[column].astype(str)) != {str(expected)}:
            raise ValueError("Mixed or mismatched target conditions in prepared dataset.")
    columns = item["feature_columns"] + [item["target_column"]]
    if not set(columns).issubset(frame.columns):
        raise ValueError("Prepared feature or target columns are missing.")
    import numpy as np
    for column in columns:
        if not pd.api.types.is_numeric_dtype(frame[column]) or not np.isfinite(frame[column]).all():
            raise ValueError("Prepared numeric values must be finite; requalify the dataset.")
    locked_partitions(frame, item["assignments"])
    frame.attrs["prepared_contract"] = {**item, "catalog_sha256": catalog_hash}
    return frame
