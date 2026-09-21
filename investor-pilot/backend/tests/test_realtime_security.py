from __future__ import annotations

from app.api.routes.realtime import _authorised_channels, _normalise_roles


def test_normalise_roles_accepts_jwt_claims() -> None:
    claims = {
        "sub": "admin@petroedge.ai",
        "roles": ["Admin", "Engineer"],
    }

    assert _normalise_roles(claims) == {"admin", "engineer"}


def test_admin_can_access_all_requested_channels() -> None:
    requested = {"global", "alerts", "jobs", "models", "wells"}

    assert _authorised_channels(requested, {"admin"}) == requested


def test_viewer_channels_are_restricted() -> None:
    requested = {"global", "alerts", "jobs", "models", "wells"}

    assert _authorised_channels(requested, {"viewer"}) == {
        "global",
        "alerts",
        "models",
        "wells",
    }


def test_unknown_role_falls_back_to_global() -> None:
    requested = {"alerts", "jobs"}

    assert _authorised_channels(requested, {"unknown"}) == {"global"}