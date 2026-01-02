"""Unit tests for system API schemas."""

from backend.api.schemas.system import ConfigResponse


def test_config_response_includes_grafana_url():
    """Test that ConfigResponse includes grafana_url field."""
    response = ConfigResponse(
        app_name="Test App",
        version="1.0.0",
        retention_days=30,
        batch_window_seconds=90,
        batch_idle_timeout_seconds=30,
        detection_confidence_threshold=0.5,
        grafana_url="http://localhost:3002",
    )
    assert response.grafana_url == "http://localhost:3002"

    # Test serialization
    data = response.model_dump()
    assert "grafana_url" in data
    assert data["grafana_url"] == "http://localhost:3002"
