from app.core.rbac import effective_roles, require_roles
from app.main import app


def test_platform_route_registered_once_at_canonical_path():
    paths = set(app.openapi().get("paths", {}))
    assert "/api/v1/platform/overview" in paths
    assert "/api/v1/platform/platform/overview" not in paths


def test_extended_roles_are_valid():
    require_roles("administrator", "operator", "petrophysicist")
    assert "admin" in effective_roles({"administrator"})
    assert "viewer" in effective_roles({"operator"})
    assert "geoscientist" in effective_roles({"petrophysicist"})


