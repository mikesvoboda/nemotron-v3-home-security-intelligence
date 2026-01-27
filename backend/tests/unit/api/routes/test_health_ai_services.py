"""Unit tests for the AI services health endpoint (NEM-3143).

Tests coverage for backend/api/routes/health_ai_services.py focusing on:
- Individual AI service health checks
- Circuit breaker state integration
- Queue depth retrieval
- Overall status calculation
- HTTP response status codes
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.routes.health_ai_services import (
    AI_SERVICES_CONFIG,
    _calculate_error_rate,
    _calculate_overall_status,
    _check_ai_service_health,
    _get_circuit_breaker_metrics,
    _get_circuit_breaker_state,
    _get_queue_depths,
    router,
)
from backend.api.schemas.ai_services_health import (
    AIServiceCircuitState,
    AIServiceHealthDetail,
    AIServiceOverallStatus,
    AIServiceStatus,
)
from backend.core.redis import get_redis_optional

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def test_app() -> FastAPI:
    """Create test FastAPI app with health router."""
    app = FastAPI()
    app.include_router(router)

    # Mock Redis dependency
    mock_redis = AsyncMock()
    mock_redis.get_queue_length.return_value = 0

    async def mock_get_redis_optional():
        yield mock_redis

    app.dependency_overrides[get_redis_optional] = mock_get_redis_optional
    return app


@pytest.fixture
async def async_client(test_app: FastAPI) -> AsyncClient:
    """Create async HTTP client for testing."""
    transport = ASGITransport(app=test_app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def create_mock_settings(
    yolo26_url: str = "http://ai-yolo26:8095",
    nemotron_url: str = "http://llm-analyzer:8080",
    florence_url: str = "http://florence-service:8091",
    clip_url: str = "http://clip-service:8092",
    enrichment_url: str = "http://enrichment-service:8093",
) -> MagicMock:
    """Create mock settings with AI service URLs.

    Args:
        yolo26_url: URL for YOLO26 service (empty string for unconfigured)
        nemotron_url: URL for Nemotron service
        florence_url: URL for Florence service
        clip_url: URL for CLIP service
        enrichment_url: URL for Enrichment service

    Returns:
        MagicMock configured with the specified URLs
    """
    mock = MagicMock()
    # Handle empty strings as None for "unconfigured" behavior
    mock.yolo26_url = yolo26_url if yolo26_url else None
    mock.nemotron_url = nemotron_url if nemotron_url else None
    mock.florence_url = florence_url if florence_url else None
    mock.clip_url = clip_url if clip_url else None
    mock.enrichment_url = enrichment_url if enrichment_url else None
    return mock


# =============================================================================
# Circuit Breaker State Tests
# =============================================================================


class TestCircuitBreakerState:
    """Tests for circuit breaker state retrieval."""

    def test_get_circuit_breaker_state_closed(self) -> None:
        """Test closed state when breaker is functioning normally."""
        with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_registry.return_value.get.return_value = mock_breaker

            state = _get_circuit_breaker_state("yolo26")
            assert state == AIServiceCircuitState.CLOSED

    def test_get_circuit_breaker_state_open(self) -> None:
        """Test open state when breaker is tripped."""
        with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "open"
            mock_registry.return_value.get.return_value = mock_breaker

            state = _get_circuit_breaker_state("yolo26")
            assert state == AIServiceCircuitState.OPEN

    def test_get_circuit_breaker_state_half_open(self) -> None:
        """Test half-open state during recovery."""
        with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "half_open"
            mock_registry.return_value.get.return_value = mock_breaker

            state = _get_circuit_breaker_state("yolo26")
            assert state == AIServiceCircuitState.HALF_OPEN

    def test_get_circuit_breaker_state_not_registered(self) -> None:
        """Test default closed state when breaker not registered."""
        with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
            mock_registry.return_value.get.return_value = None

            state = _get_circuit_breaker_state("unknown_service")
            assert state == AIServiceCircuitState.CLOSED


class TestCircuitBreakerMetrics:
    """Tests for circuit breaker metrics retrieval."""

    def test_get_circuit_breaker_metrics_exists(self) -> None:
        """Test metrics retrieval for registered breaker."""
        with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.get_status.return_value = {
                "failure_count": 2,
                "total_calls": 100,
                "rejected_calls": 5,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            metrics = _get_circuit_breaker_metrics("yolo26")
            assert metrics["failure_count"] == 2
            assert metrics["total_calls"] == 100
            assert metrics["rejected_calls"] == 5

    def test_get_circuit_breaker_metrics_not_registered(self) -> None:
        """Test default metrics when breaker not registered."""
        with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
            mock_registry.return_value.get.return_value = None

            metrics = _get_circuit_breaker_metrics("unknown_service")
            assert metrics["failure_count"] == 0
            assert metrics["total_calls"] == 0
            assert metrics["rejected_calls"] == 0


# =============================================================================
# Error Rate Calculation Tests
# =============================================================================


class TestErrorRateCalculation:
    """Tests for error rate calculation."""

    def test_calculate_error_rate_no_calls(self) -> None:
        """Test error rate is None when no calls recorded."""
        metrics = {"total_calls": 0, "failure_count": 0, "rejected_calls": 0}
        assert _calculate_error_rate(metrics) is None

    def test_calculate_error_rate_no_errors(self) -> None:
        """Test error rate is 0 when no errors."""
        metrics = {"total_calls": 100, "failure_count": 0, "rejected_calls": 0}
        assert _calculate_error_rate(metrics) == 0.0

    def test_calculate_error_rate_with_failures(self) -> None:
        """Test error rate calculation with failures."""
        metrics = {"total_calls": 100, "failure_count": 5, "rejected_calls": 0}
        assert _calculate_error_rate(metrics) == 0.05

    def test_calculate_error_rate_with_rejections(self) -> None:
        """Test error rate includes rejected calls."""
        metrics = {"total_calls": 100, "failure_count": 2, "rejected_calls": 3}
        assert _calculate_error_rate(metrics) == 0.05

    def test_calculate_error_rate_capped_at_one(self) -> None:
        """Test error rate is capped at 1.0."""
        metrics = {"total_calls": 10, "failure_count": 15, "rejected_calls": 5}
        assert _calculate_error_rate(metrics) == 1.0

    def test_calculate_error_rate_missing_fields(self) -> None:
        """Test error rate with missing fields defaults to zero."""
        metrics: dict[str, int] = {}
        assert _calculate_error_rate(metrics) is None

    def test_calculate_error_rate_rounds_to_four_decimals(self) -> None:
        """Test error rate is rounded to 4 decimal places."""
        metrics = {"total_calls": 7, "failure_count": 1, "rejected_calls": 0}
        result = _calculate_error_rate(metrics)
        assert result == 0.1429  # 1/7 rounded to 4 decimals


# =============================================================================
# AI Service Health Check Tests
# =============================================================================


class TestAIServiceHealthCheck:
    """Tests for individual AI service health checks."""

    @pytest.mark.asyncio
    async def test_service_url_not_configured(self) -> None:
        """Test health check when service URL is not configured."""
        config = AI_SERVICES_CONFIG[0]  # yolo26
        settings = create_mock_settings(yolo26_url="")

        with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
            mock_registry.return_value.get.return_value = None

            result = await _check_ai_service_health(config, settings)

            assert result.status == AIServiceStatus.UNKNOWN
            assert result.error == "Service URL not configured"
            assert result.url is None

    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self) -> None:
        """Test health check when circuit breaker is open."""
        config = AI_SERVICES_CONFIG[0]  # yolo26
        settings = create_mock_settings()

        with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "open"
            mock_breaker.get_status.return_value = {
                "failure_count": 10,
                "total_calls": 100,
                "rejected_calls": 5,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            result = await _check_ai_service_health(config, settings)

            assert result.status == AIServiceStatus.UNHEALTHY
            assert result.circuit_state == AIServiceCircuitState.OPEN
            assert "Circuit breaker is open" in result.error

    @pytest.mark.asyncio
    async def test_healthy_service(self) -> None:
        """Test health check for healthy service."""
        config = AI_SERVICES_CONFIG[0]  # yolo26
        settings = create_mock_settings()

        with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_breaker.get_status.return_value = {
                "failure_count": 0,
                "total_calls": 100,
                "rejected_calls": 0,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response

                result = await _check_ai_service_health(config, settings)

                assert result.status == AIServiceStatus.HEALTHY
                assert result.circuit_state == AIServiceCircuitState.CLOSED
                assert result.error is None
                assert result.latency_p99_ms is not None

    @pytest.mark.asyncio
    async def test_unhealthy_service_http_error(self) -> None:
        """Test health check when service returns HTTP error."""
        config = AI_SERVICES_CONFIG[0]  # yolo26
        settings = create_mock_settings()

        with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_breaker.get_status.return_value = {
                "failure_count": 5,
                "total_calls": 100,
                "rejected_calls": 0,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 500
                mock_get.return_value = mock_response

                result = await _check_ai_service_health(config, settings)

                assert result.status == AIServiceStatus.UNHEALTHY
                assert "HTTP 500" in result.error

    @pytest.mark.asyncio
    async def test_connection_refused(self) -> None:
        """Test health check when connection is refused."""
        config = AI_SERVICES_CONFIG[0]  # yolo26
        settings = create_mock_settings()

        with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_breaker.get_status.return_value = {
                "failure_count": 5,
                "total_calls": 10,
                "rejected_calls": 0,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_get.side_effect = httpx.ConnectError("Connection refused")

                result = await _check_ai_service_health(config, settings)

                assert result.status == AIServiceStatus.UNHEALTHY
                assert result.error == "Connection refused"

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        """Test health check when request times out."""
        config = AI_SERVICES_CONFIG[0]  # yolo26
        settings = create_mock_settings()

        with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_breaker.get_status.return_value = {
                "failure_count": 3,
                "total_calls": 10,
                "rejected_calls": 0,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_get.side_effect = httpx.TimeoutException("Request timed out")

                result = await _check_ai_service_health(config, settings, timeout=5.0)

                assert result.status == AIServiceStatus.UNHEALTHY
                assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_generic_exception_handling(self) -> None:
        """Test health check handles generic exceptions."""
        config = AI_SERVICES_CONFIG[0]  # yolo26
        settings = create_mock_settings()

        with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_breaker.get_status.return_value = {
                "failure_count": 0,
                "total_calls": 10,
                "rejected_calls": 0,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_get.side_effect = ValueError("Unexpected error")

                result = await _check_ai_service_health(config, settings)

                assert result.status == AIServiceStatus.UNHEALTHY
                assert "Unexpected error" in result.error

    @pytest.mark.asyncio
    async def test_custom_timeout_parameter(self) -> None:
        """Test health check respects custom timeout parameter."""
        config = AI_SERVICES_CONFIG[0]  # yolo26
        settings = create_mock_settings()

        with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
            mock_registry.return_value.get.return_value = None

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_context = AsyncMock()
                mock_client = AsyncMock()
                mock_context.__aenter__.return_value = mock_client
                mock_client_class.return_value = mock_context

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_client.get.return_value = mock_response

                custom_timeout = 10.0
                await _check_ai_service_health(config, settings, timeout=custom_timeout)

                # Verify timeout was passed to AsyncClient constructor
                mock_client_class.assert_called_once_with(timeout=custom_timeout)

    @pytest.mark.asyncio
    async def test_http_404_error(self) -> None:
        """Test health check when service returns 404."""
        config = AI_SERVICES_CONFIG[0]  # yolo26
        settings = create_mock_settings()

        with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
            mock_registry.return_value.get.return_value = None

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 404
                mock_get.return_value = mock_response

                result = await _check_ai_service_health(config, settings)

                assert result.status == AIServiceStatus.UNHEALTHY
                assert result.error == "HTTP 404"

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open(self) -> None:
        """Test health check when circuit breaker is half-open."""
        config = AI_SERVICES_CONFIG[1]  # nemotron
        settings = create_mock_settings()

        with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "half_open"
            mock_breaker.get_status.return_value = {
                "failure_count": 3,
                "total_calls": 20,
                "rejected_calls": 2,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response

                result = await _check_ai_service_health(config, settings)

                assert result.status == AIServiceStatus.HEALTHY
                assert result.circuit_state == AIServiceCircuitState.HALF_OPEN


# =============================================================================
# Queue Depth Tests
# =============================================================================


class TestQueueDepths:
    """Tests for queue depth retrieval."""

    @pytest.mark.asyncio
    async def test_get_queue_depths_success(self) -> None:
        """Test successful queue depth retrieval."""
        mock_redis = AsyncMock()
        mock_redis.get_queue_length.side_effect = [5, 2, 0, 1]

        result = await _get_queue_depths(mock_redis)

        assert result["detection_queue"].depth == 5
        assert result["detection_queue"].dlq_depth == 0
        assert result["analysis_queue"].depth == 2
        assert result["analysis_queue"].dlq_depth == 1

    @pytest.mark.asyncio
    async def test_get_queue_depths_redis_none(self) -> None:
        """Test queue depths when Redis is unavailable."""
        result = await _get_queue_depths(None)

        assert result["detection_queue"].depth == 0
        assert result["detection_queue"].dlq_depth == 0
        assert result["analysis_queue"].depth == 0
        assert result["analysis_queue"].dlq_depth == 0

    @pytest.mark.asyncio
    async def test_get_queue_depths_redis_error(self) -> None:
        """Test queue depths when Redis raises error."""
        mock_redis = AsyncMock()
        mock_redis.get_queue_length.side_effect = Exception("Redis connection error")

        result = await _get_queue_depths(mock_redis)

        # Should return zeros on error
        assert result["detection_queue"].depth == 0
        assert result["analysis_queue"].depth == 0

    @pytest.mark.asyncio
    async def test_get_queue_depths_partial_failure(self) -> None:
        """Test queue depths when some queries fail."""
        mock_redis = AsyncMock()
        # First call succeeds, rest fail
        mock_redis.get_queue_length.side_effect = [
            5,
            RuntimeError("Connection lost"),
            RuntimeError("Connection lost"),
            RuntimeError("Connection lost"),
        ]

        result = await _get_queue_depths(mock_redis)

        # Should handle partial failures gracefully
        assert result["detection_queue"].depth == 5
        assert result["detection_queue"].dlq_depth == 0
        assert result["analysis_queue"].depth == 0
        assert result["analysis_queue"].dlq_depth == 0

    @pytest.mark.asyncio
    async def test_get_queue_depths_none_values(self) -> None:
        """Test queue depths when Redis returns None."""
        mock_redis = AsyncMock()
        mock_redis.get_queue_length.side_effect = [None, None, None, None]

        result = await _get_queue_depths(mock_redis)

        # None should be converted to 0
        assert result["detection_queue"].depth == 0
        assert result["detection_queue"].dlq_depth == 0
        assert result["analysis_queue"].depth == 0
        assert result["analysis_queue"].dlq_depth == 0


# =============================================================================
# Overall Status Calculation Tests
# =============================================================================


class TestOverallStatusCalculation:
    """Tests for overall status calculation."""

    def test_all_healthy(self) -> None:
        """Test overall status is healthy when all services are healthy."""
        services = {
            "yolo26": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "nemotron": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "florence": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "clip": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "enrichment": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
        }

        assert _calculate_overall_status(services) == AIServiceOverallStatus.HEALTHY

    def test_critical_service_unhealthy(self) -> None:
        """Test overall status is critical when critical service is unhealthy."""
        services = {
            "yolo26": AIServiceHealthDetail(status=AIServiceStatus.UNHEALTHY),
            "nemotron": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "florence": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "clip": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "enrichment": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
        }

        assert _calculate_overall_status(services) == AIServiceOverallStatus.CRITICAL

    def test_critical_service_unknown(self) -> None:
        """Test overall status is critical when critical service is unknown."""
        services = {
            "yolo26": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "nemotron": AIServiceHealthDetail(status=AIServiceStatus.UNKNOWN),
            "florence": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "clip": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "enrichment": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
        }

        assert _calculate_overall_status(services) == AIServiceOverallStatus.CRITICAL

    def test_non_critical_service_unhealthy(self) -> None:
        """Test overall status is degraded when non-critical service is unhealthy."""
        services = {
            "yolo26": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "nemotron": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "florence": AIServiceHealthDetail(status=AIServiceStatus.UNHEALTHY),
            "clip": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "enrichment": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
        }

        assert _calculate_overall_status(services) == AIServiceOverallStatus.DEGRADED

    def test_non_critical_service_degraded(self) -> None:
        """Test overall status is degraded when non-critical service is degraded."""
        services = {
            "yolo26": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "nemotron": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "florence": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "clip": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "enrichment": AIServiceHealthDetail(status=AIServiceStatus.DEGRADED),
        }

        assert _calculate_overall_status(services) == AIServiceOverallStatus.DEGRADED

    def test_multiple_critical_services_unhealthy(self) -> None:
        """Test overall status is critical when multiple critical services are unhealthy."""
        services = {
            "yolo26": AIServiceHealthDetail(status=AIServiceStatus.UNHEALTHY),
            "nemotron": AIServiceHealthDetail(status=AIServiceStatus.UNHEALTHY),
            "florence": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "clip": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
            "enrichment": AIServiceHealthDetail(status=AIServiceStatus.HEALTHY),
        }

        assert _calculate_overall_status(services) == AIServiceOverallStatus.CRITICAL

    def test_all_services_unhealthy(self) -> None:
        """Test overall status is critical when all services are unhealthy."""
        services = {
            "yolo26": AIServiceHealthDetail(status=AIServiceStatus.UNHEALTHY),
            "nemotron": AIServiceHealthDetail(status=AIServiceStatus.UNHEALTHY),
            "florence": AIServiceHealthDetail(status=AIServiceStatus.UNHEALTHY),
            "clip": AIServiceHealthDetail(status=AIServiceStatus.UNHEALTHY),
            "enrichment": AIServiceHealthDetail(status=AIServiceStatus.UNHEALTHY),
        }

        assert _calculate_overall_status(services) == AIServiceOverallStatus.CRITICAL

    def test_empty_services_dict(self) -> None:
        """Test overall status is healthy when no services are defined."""
        services: dict[str, AIServiceHealthDetail] = {}
        assert _calculate_overall_status(services) == AIServiceOverallStatus.HEALTHY


# =============================================================================
# API Endpoint Tests
# =============================================================================


class TestAIServicesHealthEndpoint:
    """Tests for the /api/health/ai-services endpoint."""

    @pytest.mark.asyncio
    async def test_endpoint_returns_200_when_healthy(self, async_client: AsyncClient) -> None:
        """Test endpoint returns 200 when all services are healthy."""
        mock_settings = create_mock_settings()
        with patch("backend.api.routes.health_ai_services.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
                mock_breaker = MagicMock()
                mock_breaker.state.value = "closed"
                mock_breaker.get_status.return_value = {
                    "failure_count": 0,
                    "total_calls": 100,
                    "rejected_calls": 0,
                }
                mock_registry.return_value.get.return_value = mock_breaker

                with patch(
                    "backend.api.routes.health_ai_services.httpx.AsyncClient"
                ) as mock_client:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_context = AsyncMock()
                    mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                    mock_client.return_value = mock_context

                    response = await async_client.get("/api/health/ai-services")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["overall_status"] == "healthy"
                    assert "services" in data
                    assert "queues" in data
                    assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_endpoint_returns_503_when_critical(self, async_client: AsyncClient) -> None:
        """Test endpoint returns 503 when critical services are unhealthy."""
        mock_settings = create_mock_settings(
            florence_url="",
            clip_url="",
            enrichment_url="",
        )
        with patch("backend.api.routes.health_ai_services.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
                mock_breaker = MagicMock()
                mock_breaker.state.value = "open"
                mock_breaker.get_status.return_value = {
                    "failure_count": 50,
                    "total_calls": 100,
                    "rejected_calls": 10,
                }
                mock_registry.return_value.get.return_value = mock_breaker

                response = await async_client.get("/api/health/ai-services")

                assert response.status_code == 503
                data = response.json()
                assert data["overall_status"] == "critical"

    @pytest.mark.asyncio
    async def test_endpoint_includes_all_services(self, async_client: AsyncClient) -> None:
        """Test endpoint includes all 5 AI services."""
        mock_settings = create_mock_settings()
        with patch("backend.api.routes.health_ai_services.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
                mock_breaker = MagicMock()
                mock_breaker.state.value = "closed"
                mock_breaker.get_status.return_value = {
                    "failure_count": 0,
                    "total_calls": 0,
                    "rejected_calls": 0,
                }
                mock_registry.return_value.get.return_value = mock_breaker

                with patch(
                    "backend.api.routes.health_ai_services.httpx.AsyncClient"
                ) as mock_client:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_context = AsyncMock()
                    mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                    mock_client.return_value = mock_context

                    response = await async_client.get("/api/health/ai-services")

                    assert response.status_code == 200
                    data = response.json()
                    services = data["services"]
                    assert "yolo26" in services
                    assert "nemotron" in services
                    assert "florence" in services
                    assert "clip" in services
                    assert "enrichment" in services

    @pytest.mark.asyncio
    async def test_endpoint_includes_queue_info(self, async_client: AsyncClient) -> None:
        """Test endpoint includes queue depth information."""
        mock_settings = create_mock_settings(
            yolo26_url="",
            nemotron_url="",
            florence_url="",
            clip_url="",
            enrichment_url="",
        )
        with patch("backend.api.routes.health_ai_services.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
                mock_registry.return_value.get.return_value = None

                response = await async_client.get("/api/health/ai-services")

                data = response.json()
                queues = data["queues"]
                assert "detection_queue" in queues
                assert "analysis_queue" in queues
                assert "depth" in queues["detection_queue"]
                assert "dlq_depth" in queues["detection_queue"]

    @pytest.mark.asyncio
    async def test_endpoint_degraded_non_critical_service(self, async_client: AsyncClient) -> None:
        """Test endpoint returns 200 with degraded status when non-critical service fails."""
        mock_settings = create_mock_settings()
        with patch("backend.api.routes.health_ai_services.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch("backend.services.circuit_breaker._get_registry") as mock_registry:
                mock_breaker = MagicMock()
                mock_breaker.state.value = "closed"
                mock_breaker.get_status.return_value = {
                    "failure_count": 0,
                    "total_calls": 10,
                    "rejected_calls": 0,
                }
                mock_registry.return_value.get.return_value = mock_breaker

                with patch(
                    "backend.api.routes.health_ai_services.httpx.AsyncClient"
                ) as mock_client:
                    mock_context = AsyncMock()

                    # Make florence fail (non-critical)
                    async def mock_get(url: str, *args, **kwargs):
                        mock_response = MagicMock()
                        if "florence" in url:
                            mock_response.status_code = 500
                        else:
                            mock_response.status_code = 200
                        return mock_response

                    mock_context.__aenter__.return_value.get = mock_get
                    mock_client.return_value = mock_context

                    response = await async_client.get("/api/health/ai-services")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["overall_status"] == "degraded"


# =============================================================================
# AI Services Config Tests
# =============================================================================


class TestAIServicesConfig:
    """Tests for AI_SERVICES_CONFIG structure."""

    def test_config_has_all_required_fields(self) -> None:
        """Test that all service configs have required fields."""
        required_fields = ["name", "display_name", "url_attr", "circuit_breaker_name", "critical"]

        for config in AI_SERVICES_CONFIG:
            for field in required_fields:
                assert field in config

    def test_config_has_correct_critical_services(self) -> None:
        """Test that yolo26 and nemotron are marked as critical."""
        critical_services = {cfg["name"] for cfg in AI_SERVICES_CONFIG if cfg["critical"]}
        assert "yolo26" in critical_services
        assert "nemotron" in critical_services

    def test_config_has_correct_non_critical_services(self) -> None:
        """Test that florence, clip, and enrichment are not critical."""
        non_critical = {cfg["name"] for cfg in AI_SERVICES_CONFIG if not cfg["critical"]}
        assert "florence" in non_critical
        assert "clip" in non_critical
        assert "enrichment" in non_critical

    def test_config_count(self) -> None:
        """Test that there are exactly 5 AI services configured."""
        assert len(AI_SERVICES_CONFIG) == 5
