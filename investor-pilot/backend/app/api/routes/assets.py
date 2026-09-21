from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.rbac import require_roles


router = APIRouter()

READ_ROLES = require_roles(
    "admin",
    "administrator",
    "operator",
    "engineer",
    "geoscientist",
    "petrophysicist",
    "viewer",
)
WRITE_ROLES = require_roles(
    "admin",
    "administrator",
    "operator",
    "engineer",
    "geoscientist",
    "petrophysicist",
)

BACKEND_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = Path(
    os.getenv("PETROEDGE_DATA_DIR", str(BACKEND_ROOT / "data"))
).resolve()
ASSET_DB_PATH = DATA_ROOT / "assets.db"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AssetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=200)
    well: str = Field(min_length=1, max_length=200)
    dataset_id: str | None = Field(default=None, max_length=200)

    @field_validator("field", "well")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value cannot be blank.")
        return cleaned

    @field_validator("dataset_id")
    @classmethod
    def normalise_dataset_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class AssetSummary(BaseModel):
    asset_id: str
    field: str
    well: str
    dataset_id: str | None = None
    status: str = "active"
    created_at: str
    updated_at: str


def _connect(db_path: Path = ASSET_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialise(db_path: Path = ASSET_DB_PATH) -> None:
    with closing(_connect(db_path)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY,
                field TEXT NOT NULL,
                well TEXT NOT NULL,
                dataset_id TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(field, well)
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_assets_field_well
            ON assets(field, well)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_assets_dataset_id
            ON assets(dataset_id)
            """
        )
        connection.commit()


def _serialize(row: sqlite3.Row) -> AssetSummary:
    return AssetSummary(
        asset_id=str(row["asset_id"]),
        field=str(row["field"]),
        well=str(row["well"]),
        dataset_id=(
            str(row["dataset_id"])
            if row["dataset_id"] is not None
            else None
        ),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def list_asset_records(
    *,
    limit: int = 250,
    offset: int = 0,
    db_path: Path = ASSET_DB_PATH,
) -> list[AssetSummary]:
    initialise(db_path)

    with closing(_connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT asset_id, field, well, dataset_id, status,
                   created_at, updated_at
            FROM assets
            ORDER BY field COLLATE NOCASE, well COLLATE NOCASE
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

    return [_serialize(row) for row in rows]


def save_asset_record(
    payload: AssetCreate,
    *,
    db_path: Path = ASSET_DB_PATH,
) -> tuple[AssetSummary, bool]:
    initialise(db_path)
    timestamp = utcnow_iso()

    with closing(_connect(db_path)) as connection:
        existing = connection.execute(
            """
            SELECT asset_id, created_at
            FROM assets
            WHERE field = ? COLLATE NOCASE
              AND well = ? COLLATE NOCASE
            """,
            (payload.field, payload.well),
        ).fetchone()

        created = existing is None

        if created:
            asset_id = f"asset-{uuid4().hex[:12]}"
            created_at = timestamp
            connection.execute(
                """
                INSERT INTO assets (
                    asset_id, field, well, dataset_id, status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    asset_id,
                    payload.field,
                    payload.well,
                    payload.dataset_id,
                    created_at,
                    timestamp,
                ),
            )
        else:
            asset_id = str(existing["asset_id"])
            connection.execute(
                """
                UPDATE assets
                SET field = ?,
                    well = ?,
                    dataset_id = ?,
                    status = 'active',
                    updated_at = ?
                WHERE asset_id = ?
                """,
                (
                    payload.field,
                    payload.well,
                    payload.dataset_id,
                    timestamp,
                    asset_id,
                ),
            )

        connection.commit()

        row = connection.execute(
            """
            SELECT asset_id, field, well, dataset_id, status,
                   created_at, updated_at
            FROM assets
            WHERE asset_id = ?
            """,
            (asset_id,),
        ).fetchone()

    if row is None:
        raise RuntimeError("Asset persistence failed.")

    return _serialize(row), created


def delete_asset_record(
    asset_id: str,
    *,
    db_path: Path = ASSET_DB_PATH,
) -> bool:
    initialise(db_path)

    with closing(_connect(db_path)) as connection:
        cursor = connection.execute(
            "DELETE FROM assets WHERE asset_id = ?",
            (asset_id,),
        )
        connection.commit()
        return cursor.rowcount > 0


initialise()


@router.get("", response_model=list[AssetSummary])
def list_assets(
    limit: int = Query(default=250, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: dict[str, Any] = Depends(READ_ROLES),
) -> list[AssetSummary]:
    return list_asset_records(limit=limit, offset=offset)


@router.post("", response_model=AssetSummary)
def save_asset(
    payload: AssetCreate,
    _: dict[str, Any] = Depends(WRITE_ROLES),
) -> AssetSummary:
    asset, created = save_asset_record(payload)

    if created:
        return asset

    return asset


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_asset(
    asset_id: str,
    _: dict[str, Any] = Depends(WRITE_ROLES),
) -> None:
    if not delete_asset_record(asset_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found.",
        )

    return None


@router.get("/health")
def assets_health(
    _: dict[str, Any] = Depends(READ_ROLES),
) -> dict[str, Any]:
    initialise()
    return {
        "status": "healthy",
        "database": str(ASSET_DB_PATH),
        "asset_count": len(list_asset_records(limit=1000)),
    }