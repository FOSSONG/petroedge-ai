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