from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class DurableEdgeBuffer:
    """SQLite store-and-forward queue. Records are deleted only after successful ingestion."""

    def __init__(self, path: Path | str = Path("data/edge_stream_buffer.sqlite3"), max_records: int = 100000) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_records = max_records
        self._lock = threading.RLock()
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialise(self) -> None:
        with self._lock, self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS edge_buffer(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stream_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                source_timestamp TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                received_at TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                UNIQUE(stream_id, sequence)
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS ix_edge_buffer_order ON edge_buffer(stream_id, sequence, id)")

    def enqueue(self, payload: dict[str, Any]) -> dict[str, Any]:
        stream_id = str(payload["stream_id"])
        sequence = int(payload["sequence"])
        source_timestamp = str(payload["source_timestamp"])
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str)
        with self._lock, self._connect() as db:
            count = int(db.execute("SELECT COUNT(*) FROM edge_buffer").fetchone()[0])
            if count >= self.max_records:
                raise RuntimeError(f"edge buffer capacity reached ({self.max_records} records)")
            cursor = db.execute(
                """INSERT OR IGNORE INTO edge_buffer
                   (stream_id,sequence,source_timestamp,payload_json,received_at)
                   VALUES(?,?,?,?,?)""",
                (stream_id, sequence, source_timestamp, encoded, datetime.now(timezone.utc).isoformat()),
            )
            return {"queued": cursor.rowcount == 1, "duplicate_buffer_record": cursor.rowcount == 0}

    def peek(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT * FROM edge_buffer ORDER BY stream_id, sequence, id LIMIT ?", (int(limit),)
            ).fetchall()
        return [dict(row) | {"payload": json.loads(row["payload_json"])} for row in rows]

    def acknowledge(self, record_id: int) -> None:
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM edge_buffer WHERE id=?", (int(record_id),))

    def fail(self, record_id: int, error: str) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE edge_buffer SET attempts=attempts+1,last_error=? WHERE id=?",
                (str(error)[:2000], int(record_id)),
            )

    def stats(self) -> dict[str, Any]:
        with self._lock, self._connect() as db:
            row = db.execute(
                """SELECT COUNT(*) AS depth, MIN(received_at) AS oldest,
                          MAX(received_at) AS newest, COALESCE(SUM(attempts),0) AS attempts
                   FROM edge_buffer"""
            ).fetchone()
        return {
            "depth": int(row["depth"]),
            "oldest_received_at": row["oldest"],
            "newest_received_at": row["newest"],
            "failed_delivery_attempts": int(row["attempts"]),
            "capacity": self.max_records,
            "path": str(self.path),
        }
