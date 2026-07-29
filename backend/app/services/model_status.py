from __future__ import annotations

from datetime import datetime, timezone

from app.ml_platform.registry import get_model_registry
from app.schemas import ModelStatus


def discover_model_statuses() -> list[ModelStatus]:
    """
    Return model deployment status without importing an API router.

    Runtime services and monitoring routes must depend on the Model Platform
    registry rather than importing private functions from another route module.
    """
    registry = get_model_registry()
    statuses: list[ModelStatus] = []

    for manifest in registry.list(include_disabled=True):
        artifact = registry.artifact_path(manifest)
        exists = artifact.is_file()

        modified_at = (
            datetime.fromtimestamp(
                artifact.stat().st_mtime,
                tz=timezone.utc,
            )
            if exists
            else None
        )

        statuses.append(
            ModelStatus(
                name=manifest.model_id,
                version=manifest.version,
                framework=manifest.framework,
                status=(
                    "ready"
                    if exists and manifest.enabled
                    else "missing"
                ),
                path=manifest.artifact_path,
                size_bytes=(
                    artifact.stat().st_size
                    if exists
                    else None
                ),
                modified_at=modified_at,
                metadata=manifest.model_dump(mode="json"),
            )
        )

    return statuses
