from app.main import create_app


def test_streaming_routes_are_present_in_openapi() -> None:
    application = create_app()
    paths = application.openapi()["paths"]

    assert "/api/v1/streaming/events" in paths
    assert "/api/v1/streaming/telemetry" in paths
    assert "/api/v1/streaming/replay" in paths
    assert "/api/v1/events" in paths
    assert "/api/v1/alerts" in paths
    assert "/api/v1/rules" in paths