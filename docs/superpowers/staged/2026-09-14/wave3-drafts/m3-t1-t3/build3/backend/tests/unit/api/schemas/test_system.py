"""Unit tests for system API schemas."""

from datetime import UTC, datetime

from backend.api.schemas.system import (
    ConfigResponse,
    HealthCheckServiceStatus,
    HealthResponse,
    ProcessMemoryResponse,
)


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


# ProcessMemoryResponse tests (NEM-3890)


def test_process_memory_response_with_container_limit():
    """Test ProcessMemoryResponse with container memory limit."""
    response = ProcessMemoryResponse(
        rss_mb=2048.5,
        vms_mb=4096.0,
        percent=25.5,
        container_limit_mb=6144.0,
        container_usage_percent=33.3,
        status="healthy",
    )
    assert response.rss_mb == 2048.5
    assert response.vms_mb == 4096.0
    assert response.percent == 25.5
    assert response.container_limit_mb == 6144.0
    assert response.container_usage_percent == 33.3
    assert response.status == "healthy"

    # Test serialization
    data = response.model_dump()
    assert "rss_mb" in data
    assert "container_limit_mb" in data
    assert data["container_limit_mb"] == 6144.0


def test_process_memory_response_without_container_limit():
    """Test ProcessMemoryResponse without container memory limit."""
    response = ProcessMemoryResponse(
        rss_mb=2048.5,
        vms_mb=4096.0,
        percent=25.5,
        container_limit_mb=None,
        container_usage_percent=None,
        status="healthy",
    )
    assert response.container_limit_mb is None
    assert response.container_usage_percent is None


def test_process_memory_response_warning_status():
    """Test ProcessMemoryResponse with warning status."""
    response = ProcessMemoryResponse(
        rss_mb=4915.2,
        vms_mb=6144.0,
        percent=80.5,
        container_limit_mb=6144.0,
        container_usage_percent=80.0,
        status="warning",
    )
    assert response.status == "warning"


def test_process_memory_response_critical_status():
    """Test ProcessMemoryResponse with critical status."""
    response = ProcessMemoryResponse(
        rss_mb=5529.6,
        vms_mb=6144.0,
        percent=90.5,
        container_limit_mb=6144.0,
        container_usage_percent=90.0,
        status="critical",
    )
    assert response.status == "critical"


def test_health_response_includes_memory():
    """Test HealthResponse includes memory field (NEM-3890)."""
    memory = ProcessMemoryResponse(
        rss_mb=2048.5,
        vms_mb=4096.0,
        percent=25.5,
        container_limit_mb=6144.0,
        container_usage_percent=33.3,
        status="healthy",
    )

    response = HealthResponse(
        status="healthy",
        services={
            "database": HealthCheckServiceStatus(status="healthy", message="OK"),
            "redis": HealthCheckServiceStatus(status="healthy", message="OK"),
        },
        timestamp=datetime.now(UTC),
        recent_events=[],
        memory=memory,
    )

    assert response.memory is not None
    assert response.memory.rss_mb == 2048.5
    assert response.memory.status == "healthy"

    # Test serialization includes memory
    data = response.model_dump()
    assert "memory" in data
    assert data["memory"]["rss_mb"] == 2048.5


def test_health_response_memory_optional():
    """Test HealthResponse works without memory field."""
    response = HealthResponse(
        status="healthy",
        services={
            "database": HealthCheckServiceStatus(status="healthy", message="OK"),
        },
        timestamp=datetime.now(UTC),
        recent_events=[],
    )

    assert response.memory is None

    # Test serialization
    data = response.model_dump()
    assert "memory" in data
    assert data["memory"] is None
