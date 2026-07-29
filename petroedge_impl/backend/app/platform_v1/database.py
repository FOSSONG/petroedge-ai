from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def database_path() -> Path:
    path = Path.cwd() / "data" / "petroedge_v1.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(database_path(), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def initialise() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                source_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                row_count INTEGER,
                column_count INTEGER,
                columns_json TEXT NOT NULL DEFAULT '[]',
                missing_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'ready',
                owner_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                task TEXT NOT NULL,
                dataset_id TEXT,
                algorithm TEXT NOT NULL,
                model_id TEXT,
                status TEXT NOT NULL,
                parameters_json TEXT NOT NULL DEFAULT '{}',
                metrics_json TEXT NOT NULL DEFAULT '{}',
                training_seconds REAL,
                model_size_bytes INTEGER,
                validation_strategy TEXT,
                progress_percent INTEGER NOT NULL DEFAULT 0,
                current_stage TEXT,
                error_message TEXT,
                owner_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                actor_id TEXT,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            """
        )
        # Lightweight forward-compatible migrations for existing MVP databases.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(experiments)").fetchall()}
        for name, ddl in (
            ("progress_percent", "INTEGER NOT NULL DEFAULT 0"),
            ("current_stage", "TEXT"),
            ("error_message", "TEXT"),
        ):
            if name not in columns:
                conn.execute(f"ALTER TABLE experiments ADD COLUMN {name} {ddl}")


def audit(event_type: str, entity_type: str, entity_id: str | None, actor_id: str | None, details: dict[str, Any] | None = None) -> None:
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO audit_log(event_type, entity_type, entity_id, actor_id, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_type, entity_type, entity_id, actor_id, json.dumps(details or {}, default=str), utcnow()),
        )