"""Unit tests for GET /api/system/health/full endpoint.

Tests for the comprehensive health check endpoint that aggregates status
from all services including AI services, infrastructure, and circuit breakers.

Implements NEM-1582: Service health check orchestration and circuit breaker integration.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import Result
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes import system as system_routes
from backend.api.routes.system import (
    AI_SERVICES_CONFIG,
    _check_ai_service_health,
    _check_postgres_health_full,
    _check_redis_health_full,
    _get_circuit_breaker_summary,
    _get_worker_status,
)
from backend.api.schemas.health import (
    CircuitState,
    ServiceHealthState,
)
from backend.core.config import Settings
from backend.core.redis import RedisClient

# =============================================================================
# Test _check_postgres_health_full
# =============================================================================


@pytest.mark.asyncio
async def test_check_postgres_health_full_healthy() -> None:
    """Test that PostgreSQL health returns healthy when query succeeds."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock(spec=Result)
    mock_result.scalar.return_value = datetime.now(UTC)
    mock_db.execute.return_value = mock_result

    result = await _check_postgres_health_full(mock_db)

    assert result.name == "postgres"
    assert result.status == ServiceHealthState.HEALTHY
    assert result.message == "Database operational"


@pytest.mark.asyncio
async def test_check_postgres_health_full_unhealthy() -> None:
    """Test that PostgreSQL health returns unhealthy when query fails."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute.side_effect = RuntimeError("Connection refused")

    result = await _check_postgres_health_full(mock_db)

    assert result.name == "postgres"
    assert result.status == ServiceHealthState.UNHEALTHY
    assert "Connection refused" in result.message


# =============================================================================
# Test _check_redis_health_full
# =============================================================================


@pytest.mark.asyncio
async def test_check_redis_health_full_healthy() -> None:
    """Test that Redis health returns healthy when health_check succeeds."""
    mock_redis = AsyncMock(spec=RedisClient)
    mock_redis.health_check.return_value = {
        "status": "healthy",
        "redis_version": "7.4.0",
    }

    result = await _check_redis_health_full(mock_redis)

    assert result.name == "redis"
    assert result.status == ServiceHealthState.HEALTHY
    assert result.message == "Redis connected"
    assert result.details == {"redis_version": "7.4.0"}


@pytest.mark.asyncio
async def test_check_redis_health_full_unhealthy_with_error() -> None:
    """Test that Redis health returns unhealthy when health_check returns error."""
    mock_redis = AsyncMock(spec=RedisClient)
    mock_redis.health_check.return_value = {
        "error": "Connection timeout",
    }

    result = await _check_redis_health_full(mock_redis)

    assert result.name == "redis"
    assert result.status == ServiceHealthState.UNHEALTHY
    assert "Connection timeout" in result.message


@pytest.mark.asyncio
async def test_check_redis_health_full_unhealthy_when_none() -> None:
    """Test that Redis health returns unhealthy when client is None."""
    result = await _check_redis_health_full(None)

    assert result.name == "redis"
    assert result.status == ServiceHealthState.UNHEALTHY
    assert "not available" in result.message.lower()


@pytest.mark.asyncio
async def test_check_redis_health_full_unhealthy_on_exception() -> None:
    """Test that Redis health returns unhealthy when exception is raised."""
    mock_redis = AsyncMock(spec=RedisClient)
    mock_redis.health_check.side_effect = ConnectionError("Network unreachable")

    result = await _check_redis_health_full(mock_redis)

    assert result.name == "redis"
    assert result.status == ServiceHealthState.UNHEALTHY
    assert "Network unreachable" in result.message


# =============================================================================
# Test _check_ai_service_health
# =============================================================================


@pytest.mark.asyncio
async def test_check_ai_service_health_healthy() -> None:
    """Test that AI service health returns healthy when endpoint responds 200."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.yolo26_url = "http://ai-detector:8090"

    service_config = {
        "name": "yolo26",
        "display_name": "RT-DETRv2 Object Detection",
        "url_attr": "yolo26_url",
        "circuit_breaker_name": "yolo26",
        "critical": True,
    }

    with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
        mock_registry.return_value.get.return_value = None  # No circuit breaker registered

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await _check_ai_service_health(service_config, mock_settings)

    assert result.name == "yolo26"
    assert result.display_name == "RT-DETRv2 Object Detection"
    assert result.status == ServiceHealthState.HEALTHY
    assert result.url == "http://ai-detector:8090"
    assert result.circuit_state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_check_ai_service_health_unhealthy_http_error() -> None:
    """Test that AI service health returns unhealthy on HTTP error."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.yolo26_url = "http://ai-detector:8090"

    service_config = {
        "name": "yolo26",
        "display_name": "RT-DETRv2 Object Detection",
        "url_attr": "yolo26_url",
        "circuit_breaker_name": "yolo26",
        "critical": True,
    }

    with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
        mock_registry.return_value.get.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await _check_ai_service_health(service_config, mock_settings)

    assert result.status == ServiceHealthState.UNHEALTHY
    assert result.error == "HTTP 500"


@pytest.mark.asyncio
async def test_check_ai_service_health_unhealthy_connection_refused() -> None:
    """Test that AI service health returns unhealthy on connection error."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.yolo26_url = "http://ai-detector:8090"

    service_config = {
        "name": "yolo26",
        "display_name": "RT-DETRv2 Object Detection",
        "url_attr": "yolo26_url",
        "circuit_breaker_name": "yolo26",
        "critical": True,
    }

    with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
        mock_registry.return_value.get.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )

            result = await _check_ai_service_health(service_config, mock_settings)

    assert result.status == ServiceHealthState.UNHEALTHY
    assert result.error == "Connection refused"


@pytest.mark.asyncio
async def test_check_ai_service_health_unhealthy_timeout() -> None:
    """Test that AI service health returns unhealthy on timeout."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.yolo26_url = "http://ai-detector:8090"

    service_config = {
        "name": "yolo26",
        "display_name": "RT-DETRv2 Object Detection",
        "url_attr": "yolo26_url",
        "circuit_breaker_name": "yolo26",
        "critical": True,
    }

    with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
        mock_registry.return_value.get.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Request timeout")
            )

            result = await _check_ai_service_health(service_config, mock_settings, timeout=5.0)

    assert result.status == ServiceHealthState.UNHEALTHY
    assert "Timeout" in result.error


@pytest.mark.asyncio
async def test_check_ai_service_health_unknown_when_url_not_configured() -> None:
    """Test that AI service health returns unknown when URL is not configured."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.yolo26_url = None  # Not configured

    service_config = {
        "name": "yolo26",
        "display_name": "RT-DETRv2 Object Detection",
        "url_attr": "yolo26_url",
        "circuit_breaker_name": "yolo26",
        "critical": True,
    }

    result = await _check_ai_service_health(service_config, mock_settings)

    assert result.status == ServiceHealthState.UNKNOWN
    assert "not configured" in result.error.lower()


@pytest.mark.asyncio
async def test_check_ai_service_health_skips_when_circuit_open() -> None:
    """Test that AI service health skips check when circuit breaker is open."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.yolo26_url = "http://ai-detector:8090"

    service_config = {
        "name": "yolo26",
        "display_name": "RT-DETRv2 Object Detection",
        "url_attr": "yolo26_url",
        "circuit_breaker_name": "yolo26",
        "critical": True,
    }

    with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
        mock_breaker = MagicMock()
        mock_breaker.state.value = "open"
        mock_registry.return_value.get.return_value = mock_breaker

        result = await _check_ai_service_health(service_config, mock_settings)

    assert result.status == ServiceHealthState.UNHEALTHY
    assert result.circuit_state == CircuitState.OPEN
    assert "Circuit breaker is open" in result.error


# =============================================================================
# Test _get_circuit_breaker_summary
# =============================================================================


def test_get_circuit_breaker_summary_all_closed() -> None:
    """Test circuit breaker summary when all circuits are closed."""
    with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
        mock_registry.return_value.get_all_status.return_value = {
            "yolo26": {"state": "closed", "failure_count": 0},
            "nemotron": {"state": "closed", "failure_count": 0},
            "florence": {"state": "closed", "failure_count": 0},
        }

        result = _get_circuit_breaker_summary()

    assert result.total == 3
    assert result.closed == 3
    assert result.open == 0
    assert result.half_open == 0
    assert result.breakers["yolo26"] == CircuitState.CLOSED


def test_get_circuit_breaker_summary_with_open() -> None:
    """Test circuit breaker summary with some circuits open."""
    with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
        mock_registry.return_value.get_all_status.return_value = {
            "yolo26": {"state": "open", "failure_count": 5},
            "nemotron": {"state": "closed", "failure_count": 0},
            "florence": {"state": "half_open", "failure_count": 2},
        }

        result = _get_circuit_breaker_summary()

    assert result.total == 3
    assert result.closed == 1
    assert result.open == 1
    assert result.half_open == 1
    assert result.breakers["yolo26"] == CircuitState.OPEN
    assert result.breakers["nemotron"] == CircuitState.CLOSED
    assert result.breakers["florence"] == CircuitState.HALF_OPEN


def test_get_circuit_breaker_summary_empty() -> None:
    """Test circuit breaker summary when no circuits are registered."""
    with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
        mock_registry.return_value.get_all_status.return_value = {}

        result = _get_circuit_breaker_summary()

    assert result.total == 0
    assert result.closed == 0
    assert result.open == 0
    assert result.half_open == 0


# =============================================================================
# Test _get_worker_status
# =============================================================================


def test_get_worker_status_returns_workers() -> None:
    """Test worker status returns list of workers."""
    with patch.object(system_routes, "_cleanup_service", None):
        result = _get_worker_status()

    # Should have file_watcher and cleanup_service
    assert len(result) == 2

    file_watcher = next((w for w in result if w.name == "file_watcher"), None)
    assert file_watcher is not None
    assert file_watcher.critical is True

    cleanup = next((w for w in result if w.name == "cleanup_service"), None)
    assert cleanup is not None
    assert cleanup.critical is False


def test_get_worker_status_cleanup_service_running() -> None:
    """Test worker status when cleanup service is running."""
    mock_cleanup = MagicMock()
    mock_cleanup.get_cleanup_stats.return_value = {"running": True}

    with patch.object(system_routes, "_cleanup_service", mock_cleanup):
        result = _get_worker_status()

    cleanup = next((w for w in result if w.name == "cleanup_service"), None)
    assert cleanup is not None
    assert cleanup.running is True
    assert cleanup.critical is False


# =============================================================================
# Test AI_SERVICES_CONFIG structure
# =============================================================================


def test_ai_services_config_structure() -> None:
    """Test that AI_SERVICES_CONFIG has required fields."""
    required_fields = ["name", "display_name", "url_attr", "circuit_breaker_name", "critical"]

    for config in AI_SERVICES_CONFIG:
        for field in required_fields:
            assert field in config, f"Missing field {field} in {config['name']}"


def test_ai_services_config_critical_services() -> None:
    """Test that critical services are correctly identified."""
    critical_services = [s for s in AI_SERVICES_CONFIG if s["critical"]]
    critical_names = [s["name"] for s in critical_services]

    assert "yolo26" in critical_names
    assert "nemotron" in critical_names

    # Non-critical should not be marked critical
    assert "florence" not in critical_names
    assert "clip" not in critical_names
    assert "enrichment" not in critical_names


def test_ai_services_config_all_services_present() -> None:
    """Test that all expected AI services are configured."""
    expected_services = ["yolo26", "nemotron", "florence", "clip", "enrichment"]
    actual_services = [s["name"] for s in AI_SERVICES_CONFIG]

    for service in expected_services:
        assert service in actual_services, f"Missing service: {service}"
