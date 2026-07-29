from __future__ import annotations

from datetime import datetime, timezone

from app.ml_platform.registry import ModelRegistry, get_model_registry
from app.schemas import ModelStatus


def discover_model_statuses(
    registry: ModelRegistry | None = None,
) -> list[ModelStatus]:
    """Return deployment status for every registered model artifact.

    This compatibility view is intentionally located in the model platform,
    rather than an API route, so monitoring and other services do not depend
    on route modules.
    """
    selected_registry = registry or get_model_registry()
    statuses: list[ModelStatus] = []

    for manifest in selected_registry.list(include_disabled=True):
        artifact = selected_registry.artifact_path(manifest)
        exists = artifact.is_file()
        modified_at = (
            datetime.fromtimestamp(artifact.stat().st_mtime, tz=timezone.utc)
            if exists
            else None
        )

        if not manifest.enabled:
            deployment_status = "unknown"
        elif exists:
            deployment_status = "ready"
        else:
            deployment_status = "missing"

        statuses.append(
            ModelStatus(
                name=manifest.model_id,
                version=manifest.version,
                framework=manifest.framework,
                status=deployment_status,
                path=manifest.artifact_path,
                size_bytes=artifact.stat().st_size if exists else None,
                modified_at=modified_at,
                metadata=manifest.model_dump(mode="json"),
            )
        )

    return statuses
