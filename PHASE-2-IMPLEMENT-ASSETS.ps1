$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $ProjectRoot "patch-backups\phase2-assets-$Timestamp"
$ResultPath = Join-Path $ProjectRoot "PHASE-2-ASSETS-RESULT.txt"

$MainFile = Join-Path $ProjectRoot "backend\app\main.py"
$AssetsRouteFile = Join-Path $ProjectRoot "backend\app\api\routes\assets.py"
$AssetsTestFile = Join-Path $ProjectRoot "backend\tests\test_assets_api.py"

function Assert-FileExists {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file not found: $Path"
    }
}

function Save-Backup {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$RelativeDestination
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        return
    }

    $Destination = Join-Path $BackupRoot $RelativeDestination
    $DestinationDirectory = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Path $DestinationDirectory -Force | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )

    $Directory = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null

    [System.IO.File]::WriteAllText(
        $Path,
        $Content,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

Assert-FileExists -Path $MainFile
New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null

Save-Backup -Source $MainFile -RelativeDestination "backend\app\main.py"
Save-Backup -Source $AssetsRouteFile -RelativeDestination "backend\app\api\routes\assets.py"
Save-Backup -Source $AssetsTestFile -RelativeDestination "backend\tests\test_assets_api.py"

$AssetsRoute = @'
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
'@

$AssetsTest = @'
from pathlib import Path

from app.api.routes.assets import (
    AssetCreate,
    delete_asset_record,
    list_asset_records,
    save_asset_record,
)
from app.main import create_app


def test_assets_routes_are_registered() -> None:
    paths = create_app().openapi()["paths"]

    assert "/api/v1/assets" in paths
    assert "get" in paths["/api/v1/assets"]
    assert "post" in paths["/api/v1/assets"]
    assert "/api/v1/assets/{asset_id}" in paths
    assert "/api/v1/assets/health" in paths


def test_asset_repository_create_update_list_delete(tmp_path: Path) -> None:
    db_path = tmp_path / "assets-test.db"

    created_asset, created = save_asset_record(
        AssetCreate(
            field="Niger Delta",
            well="GABO-18",
            dataset_id="ds-demo-001",
        ),
        db_path=db_path,
    )

    assert created is True
    assert created_asset.field == "Niger Delta"
    assert created_asset.well == "GABO-18"
    assert created_asset.dataset_id == "ds-demo-001"
    assert created_asset.status == "active"

    updated_asset, created_again = save_asset_record(
        AssetCreate(
            field="Niger Delta",
            well="GABO-18",
            dataset_id="ds-demo-002",
        ),
        db_path=db_path,
    )

    assert created_again is False
    assert updated_asset.asset_id == created_asset.asset_id
    assert updated_asset.dataset_id == "ds-demo-002"

    records = list_asset_records(db_path=db_path)

    assert len(records) == 1
    assert records[0].asset_id == created_asset.asset_id

    assert delete_asset_record(
        created_asset.asset_id,
        db_path=db_path,
    ) is True

    assert list_asset_records(db_path=db_path) == []
'@

Write-Host ""
Write-Host "[1/7] Writing Assets backend route..." -ForegroundColor Cyan
Write-Utf8NoBom -Path $AssetsRouteFile -Content $AssetsRoute

Write-Host "[2/7] Registering Assets router..." -ForegroundColor Cyan

$MainContent = [System.IO.File]::ReadAllText($MainFile)

if ($MainContent -notmatch '\("assets", "/assets"') {
    $Anchor = '    ("wells", "/wells", ("Wells",), True),'

    if (-not $MainContent.Contains($Anchor)) {
        throw "Could not find the Wells router registration anchor in backend\app\main.py"
    }

    $Replacement = $Anchor + [Environment]::NewLine +
        '    ("assets", "/assets", ("Asset Management",), True),'

    $MainContent = $MainContent.Replace($Anchor, $Replacement)

    [System.IO.File]::WriteAllText(
        $MainFile,
        $MainContent,
        (New-Object System.Text.UTF8Encoding($false))
    )
}
else {
    Write-Host "Assets router is already registered." -ForegroundColor Yellow
}

Write-Host "[3/7] Writing Assets regression tests..." -ForegroundColor Cyan
Write-Utf8NoBom -Path $AssetsTestFile -Content $AssetsTest

Set-Location $ProjectRoot

Write-Host "[4/7] Validating Docker Compose..." -ForegroundColor Cyan
docker compose config --quiet

if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose validation failed."
}

Write-Host "[5/7] Rebuilding backend and frontend..." -ForegroundColor Cyan
docker compose up -d --build --force-recreate --remove-orphans

if ($LASTEXITCODE -ne 0) {
    throw "Docker rebuild failed. Backups: $BackupRoot"
}

Write-Host "[6/7] Waiting for backend health..." -ForegroundColor Cyan

$Healthy = $false

for ($Attempt = 1; $Attempt -le 30; $Attempt++) {
    $BackendId = docker compose ps -q backend 2>$null

    if ($BackendId) {
        $Status = docker inspect $BackendId --format "{{.State.Status}}" 2>$null
        $Health = docker inspect $BackendId --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}" 2>$null

        Write-Host "Backend: status=$Status health=$Health"

        if ($Status -eq "running" -and ($Health -eq "healthy" -or $Health -eq "no-healthcheck")) {
            $Healthy = $true
            break
        }
    }

    Start-Sleep -Seconds 4
}

if (-not $Healthy) {
    docker compose ps -a
    docker compose logs backend --tail 250
    throw "Backend failed to become healthy. Backups: $BackupRoot"
}

Write-Host "[7/7] Running Assets tests and route verification..." -ForegroundColor Cyan

docker compose exec -T backend pytest -q tests/test_assets_api.py

if ($LASTEXITCODE -ne 0) {
    throw "Assets regression tests failed. Backups: $BackupRoot"
}

$OpenApi = Invoke-RestMethod `
    -Uri "http://localhost:8000/openapi.json" `
    -Method Get `
    -TimeoutSec 30

$Paths = @($OpenApi.paths.PSObject.Properties.Name)
$RequiredPaths = @(
    "/api/v1/assets",
    "/api/v1/assets/{asset_id}",
    "/api/v1/assets/health"
)

$Missing = @($RequiredPaths | Where-Object { $Paths -notcontains $_ })

$Result = New-Object System.Collections.Generic.List[string]
$Result.Add("PETROEDGE AI PHASE 2 ASSETS RESULT")
$Result.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')")
$Result.Add("Backup: $BackupRoot")
$Result.Add("")
$Result.Add("Required Assets paths missing: $($Missing.Count)")

foreach ($Path in $Missing) {
    $Result.Add("MISSING: $Path")
}

$Result.Add("")
$Result.Add("Persistent database:")
$Result.Add("backend\data\assets.db")
$Result.Add("")
$Result.Add("Docker state:")

$ComposeState = docker compose ps -a 2>&1

foreach ($Line in $ComposeState) {
    $Result.Add([string]$Line)
}

$Result | Set-Content -LiteralPath $ResultPath -Encoding utf8

if ($Missing.Count -gt 0) {
    throw "Assets routes are missing after rebuild. Review: $ResultPath"
}

Write-Host ""
Write-Host "PHASE 2 ASSETS IMPLEMENTATION COMPLETED" -ForegroundColor Green
Write-Host "Assets API: http://localhost:8000/api/v1/assets" -ForegroundColor Green
Write-Host "Assets UI: http://localhost:5173" -ForegroundColor Green
Write-Host "Result report: $ResultPath"
Write-Host "Backups: $BackupRoot"
Write-Host ""
Write-Host "Refresh the browser with Ctrl+F5, then open the Assets tab." -ForegroundColor Yellow
