"""Append-only owner-protected analysis records, with content-integrity checks."""
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError
from fastapi import HTTPException
from app.core.ownership import owner_id, require_owner, visible


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _engine_identity():
    app = Path(__file__).resolve().parents[1]
    files = ["services/analytics.py", "services/well_curve_mapping.py", "services/shap_service.py", "ml_platform/service.py", "ml_platform/adapters.py", "schemas.py"]
    packages = {}
    for name in ["numpy", "pandas", "scikit-learn", "joblib", "shap", "onnxruntime"]:
        try: packages[name] = version(name)
        except PackageNotFoundError: packages[name] = None
    return {"code_sha256": {name: hashlib.sha256((app / name).read_bytes()).hexdigest() for name in files}, "packages": packages}

ENGINE_IDENTITY = _engine_identity()


def _connect():
    root = Path.cwd() / "analysis_store"
    root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(root / "analyses.sqlite3")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS analyses (analysis_id TEXT PRIMARY KEY, owner_id TEXT, payload TEXT NOT NULL, sha256 TEXT NOT NULL)")
    return conn


def save(result):
    # JSON round-trip prevents the caller mutating the persisted snapshot.
    payload = json.loads(_json(result))
    key = "analysis-" + uuid.uuid4().hex
    payload["analysis_id"] = key
    payload["provenance"]["persisted"] = True
    payload["provenance"]["engine"] = ENGINE_IDENTITY
    encoded = _json(payload)
    conn = _connect()
    try:
        with conn:
            conn.execute("INSERT INTO analyses VALUES (?,?,?,?)", (key, owner_id(), encoded, hashlib.sha256(encoded.encode()).hexdigest()))
    finally: conn.close()
    return payload


def _decode(row):
    require_owner(row["owner_id"])
    if hashlib.sha256(row["payload"].encode()).hexdigest() != row["sha256"]:
        raise HTTPException(409, "Saved analysis integrity check failed.")
    return json.loads(row["payload"])


def get(analysis_id):
    conn = _connect()
    try: row = conn.execute("SELECT * FROM analyses WHERE analysis_id=?", (analysis_id,)).fetchone()
    finally: conn.close()
    if row is None: raise HTTPException(404, "Analysis not found.")
    return _decode(row)


def list_records(limit=100):
    conn = _connect()
    try: rows = conn.execute("SELECT * FROM analyses ORDER BY rowid DESC").fetchall()
    finally: conn.close()
    output = []
    for row in rows:
        if not visible(row["owner_id"]): continue
        payload = _decode(row)
        output.append({"analysis_id": payload["analysis_id"], "provenance": payload["provenance"]})
        if len(output) >= limit: break
    return output
