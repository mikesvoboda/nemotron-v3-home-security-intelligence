"""Unit tests for system API schemas."""

from backend.api.schemas.system import ConfigResponse


def test_config_response_includes_grafana_url():
    """Test that ConfigResponse includes grafana_url field."""
    response = ConfigResponse(
        app_name="Test App",
        version="1.0.0",
        retention_days=30,
        log_retention_days=7,
        batch_window_seconds=90,
        batch_idle_timeout_seconds=30,
        detection_confidence_threshold=0.5,
        fast_path_confidence_threshold=0.9,
        grafana_url="http://localhost:3002",
        debug=False,
    )
    assert response.grafana_url == "http://localhost:3002"

    # Test serialization
    data = response.model_dump()
    assert "grafana_url" in data
    assert data["grafana_url"] == "http://localhost:3002"


def test_config_response_includes_debug():
    """Test that ConfigResponse includes debug field."""
    response = ConfigResponse(
        app_name="Test App",
        version="1.0.0",
        retention_days=30,
        log_retention_days=7,
        batch_window_seconds=90,
        batch_idle_timeout_seconds=30,
        detection_confidence_threshold=0.5,
        fast_path_confidence_threshold=0.9,
        grafana_url="http://localhost:3002",
        debug=True,
    )
    assert response.debug is True

    # Test serialization
    data = response.model_dump()
    assert "debug" in data
    assert data["debug"] is True


def test_config_response_includes_log_retention_days():
    """Test that ConfigResponse includes log_retention_days field."""
    response = ConfigResponse(
        app_name="Test App",
        version="1.0.0",
        retention_days=30,
        log_retention_days=14,
        batch_window_seconds=90,
        batch_idle_timeout_seconds=30,
        detection_confidence_threshold=0.5,
        fast_path_confidence_threshold=0.9,
        grafana_url="http://localhost:3002",
        debug=False,
    )
    assert response.log_retention_days == 14

    # Test serialization
    data = response.model_dump()
    assert "log_retention_days" in data
    assert data["log_retention_days"] == 14


def test_config_response_includes_fast_path_confidence_threshold():
    """Test that ConfigResponse includes fast_path_confidence_threshold field."""
    response = ConfigResponse(
        app_name="Test App",
        version="1.0.0",
        retention_days=30,
        log_retention_days=7,
        batch_window_seconds=90,
        batch_idle_timeout_seconds=30,
        detection_confidence_threshold=0.5,
        fast_path_confidence_threshold=0.85,
        grafana_url="http://localhost:3002",
        debug=False,
    )
    assert response.fast_path_confidence_threshold == 0.85

    # Test serialization
    data = response.model_dump()
    assert "fast_path_confidence_threshold" in data
    assert data["fast_path_confidence_threshold"] == 0.85
