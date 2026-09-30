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


#: The settings field each shipped table row probes, read off the live table in
#: table order. R8 S3 deleted the florence/clip/enrichment rows and their
#: settings fields together (owner rulings 1 + 5), so "which url attrs does the
#: mock need" now has a one-word answer: whichever ones the table names.
_URL_ATTRS: list[str] = [cfg["url_attr"] for cfg in AI_SERVICES_CONFIG]


def create_mock_settings(
    yolo26_url: str = "http://ai-yolo26:8095",
    ai_vlm_url: str = "http://ai-vlm:8098",
    **extra_url_attrs: str,
) -> MagicMock:
    """Create mock settings with AI service URLs.

    One url attr per row of the shipped table, derived from
    ``AI_SERVICES_CONFIG`` above — there is no ``nemotron_url`` arg because
    R8 S2 deleted that setting along with the retired LLM's row, and no
    ``florence_url`` / ``clip_url`` / ``enrichment_url`` arg because R8 S3
    deleted those three settings along with their providers. Handing a real
    ``Settings`` one of those names is silently inert (``extra="ignore"``), so
    the honest mock is one that does not answer them at all.

    Args:
        yolo26_url: URL for YOLO26 service (empty string for unconfigured)
        ai_vlm_url: URL for the VLM verdict service (empty for unconfigured)
        **extra_url_attrs: override for a url_attr this signature has not
            caught up with yet; a name no shipped row reads is a loud TypeError

    Returns:
        MagicMock configured with the specified URLs
    """
    values = {"yolo26_url": yolo26_url, "ai_vlm_url": ai_vlm_url, **extra_url_attrs}
    unknown = set(values) - set(_URL_ATTRS)
    if unknown:
        raise TypeError(
            f"create_mock_settings: no shipped AI-services row reads {sorted(unknown)}; "
            f"the table reads {_URL_ATTRS}"
        )
    missing = [attr for attr in _URL_ATTRS if attr not in values]
    assert not missing, f"shipped AI-services row has no mock url attr: {missing}"
    mock = MagicMock()
    # Handle empty strings as None for "unconfigured" behavior
    for attr in _URL_ATTRS:
        setattr(mock, attr, values[attr] if values[attr] else None)
    # No `pipeline_mode` on the mock (R8 left one mode) and every url attr
    # spelled: the shipped table's rows read settings.<url_attr>, so a bare
    # MagicMock attr would leak a mock object into AIServiceHealthDetail.url.
    return mock


# =============================================================================
# Circuit Breaker State Tests
# =============================================================================


class TestCircuitBreakerState:
    """Tests for circuit breaker state retrieval."""

    def test_get_circuit_breaker_state_closed(self) -> None:
        """Test closed state when breaker is functioning normally."""
        with patch(
            "backend.services.circuit_breaker._get_registry", autospec=True
        ) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_registry.return_value.get.return_value = mock_breaker

            state = _get_circuit_breaker_state("yolo26")
            assert state == AIServiceCircuitState.CLOSED

    def test_get_circuit_breaker_state_open(self) -> None:
        """Test open state when breaker is tripped."""
        with patch(
            "backend.services.circuit_breaker._get_registry", autospec=True
        ) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "open"
            mock_registry.return_value.get.return_value = mock_breaker

            state = _get_circuit_breaker_state("yolo26")
            assert state == AIServiceCircuitState.OPEN

    def test_get_circuit_breaker_state_half_open(self) -> None:
        """Test half-open state during recovery."""
        with patch(
            "backend.services.circuit_breaker._get_registry", autospec=True
        ) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "half_open"
            mock_registry.return_value.get.return_value = mock_breaker

            state = _get_circuit_breaker_state("yolo26")
            assert state == AIServiceCircuitState.HALF_OPEN

    def test_get_circuit_breaker_state_not_registered(self) -> None:
        """Test default closed state when breaker not registered."""
        with patch(
            "backend.services.circuit_breaker._get_registry", autospec=True
        ) as mock_registry:
            mock_registry.return_value.get.return_value = None

            state = _get_circuit_breaker_state("unknown_service")
            assert state == AIServiceCircuitState.CLOSED


class TestCircuitBreakerMetrics:
    """Tests for circuit breaker metrics retrieval."""

    def test_get_circuit_breaker_metrics_exists(self) -> None:
        """Test metrics retrieval for registered breaker."""
        with patch(
            "backend.services.circuit_breaker._get_registry", autospec=True
        ) as mock_registry:
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
        with patch(
            "backend.services.circuit_breaker._get_registry", autospec=True
        ) as mock_registry:
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

        with patch(
            "backend.services.circuit_breaker._get_registry", autospec=True
        ) as mock_registry:
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

        with patch(
            "backend.services.circuit_breaker._get_registry", autospec=True
        ) as mock_registry:
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

        with patch(
            "backend.services.circuit_breaker._get_registry", autospec=True
        ) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_breaker.get_status.return_value = {
                "failure_count": 0,
                "total_calls": 100,
                "rejected_calls": 0,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get", autospec=True) as mock_get:
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

        with patch(
            "backend.services.circuit_breaker._get_registry", autospec=True
        ) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_breaker.get_status.return_value = {
                "failure_count": 5,
                "total_calls": 100,
                "rejected_calls": 0,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get", autospec=True) as mock_get:
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

        with patch(
            "backend.services.circuit_breaker._get_registry", autospec=True
        ) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_breaker.get_status.return_value = {
                "failure_count": 5,
                "total_calls": 10,
                "rejected_calls": 0,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get", autospec=True) as mock_get:
                mock_get.side_effect = httpx.ConnectError("Connection refused")

                result = await _check_ai_service_health(config, settings)

                assert result.status == AIServiceStatus.UNHEALTHY
                assert result.error == "Connection refused"

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        """Test health check when request times out."""
        config = AI_SERVICES_CONFIG[0]  # yolo26
        settings = create_mock_settings()

        with patch(
            "backend.services.circuit_breaker._get_registry", autospec=True
        ) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_breaker.get_status.return_value = {
                "failure_count": 3,
                "total_calls": 10,
                "rejected_calls": 0,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get", autospec=True) as mock_get:
                mock_get.side_effect = httpx.TimeoutException("Request timed out")

                result = await _check_ai_service_health(config, settings, timeout=5.0)

                assert result.status == AIServiceStatus.UNHEALTHY
                assert "Timeout" in result.error


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


# =============================================================================
# Overall Status Calculation Tests
# =============================================================================


class TestOverallStatusCalculation:
    """Tests for overall status calculation."""

    # Every case below builds its health map from the SHIPPED table: one entry
    # per row, all healthy, with named rows overridden. R8 S3 retired florence,
    # clip and enrichment (owner rulings 1 + 5), and because
    # ``_calculate_overall_status`` treats any key that is not a critical row as
    # non-critical, hand-typed keys for those three used to be what made the
    # DEGRADED cases fire — a table drift would have kept them green while
    # testing a topology that no longer ships. The critical/non-critical split
    # now comes from the live ``critical`` flags.
    @staticmethod
    def _health(overrides: dict[str, AIServiceStatus]) -> dict[str, AIServiceHealthDetail]:
        """A health entry for every shipped table row, HEALTHY by default."""
        names = {cfg["name"] for cfg in AI_SERVICES_CONFIG}
        assert names, "AI_SERVICES_CONFIG has no rows to build health for"
        unknown = set(overrides) - names
        assert not unknown, (
            f"override names a row the shipped table does not have: {sorted(unknown)}"
        )
        return {
            name: AIServiceHealthDetail(status=overrides.get(name, AIServiceStatus.HEALTHY))
            for name in names
        }

    def test_all_healthy(self) -> None:
        """Test overall status is healthy when all services are healthy."""
        assert _calculate_overall_status(self._health({})) == AIServiceOverallStatus.HEALTHY

    def test_critical_service_unhealthy(self) -> None:
        """Test overall status is critical when the critical service is unhealthy."""
        critical = {cfg["name"] for cfg in AI_SERVICES_CONFIG if cfg["critical"]}
        assert critical, "shipped table has no critical row: nothing could ever be CRITICAL"
        victim = sorted(critical)[0]
        services = self._health({victim: AIServiceStatus.UNHEALTHY})

        assert _calculate_overall_status(services) == AIServiceOverallStatus.CRITICAL

    def test_critical_service_unknown(self) -> None:
        """Test overall status is critical when the critical service is unknown."""
        victim = sorted({cfg["name"] for cfg in AI_SERVICES_CONFIG if cfg["critical"]})[0]
        services = self._health({victim: AIServiceStatus.UNKNOWN})

        assert _calculate_overall_status(services) == AIServiceOverallStatus.CRITICAL

    def test_non_critical_service_unhealthy(self) -> None:
        """Test overall status is degraded when a non-critical service is unhealthy."""
        non_critical = {cfg["name"] for cfg in AI_SERVICES_CONFIG if not cfg["critical"]}
        assert non_critical, "shipped table has no non-critical row: nothing could ever DEGRADE"
        victim = sorted(non_critical)[0]
        services = self._health({victim: AIServiceStatus.UNHEALTHY})

        assert _calculate_overall_status(services) == AIServiceOverallStatus.DEGRADED

    def test_ai_vlm_down_is_degraded_not_critical(self) -> None:
        """ai-vlm is the table's non-critical verdict-engine row: down alone
        costs a DEGRADED badge, never the 503 a critical row earns (R8 S2)."""
        services = self._health({"ai-vlm": AIServiceStatus.UNHEALTHY})

        assert _calculate_overall_status(services) == AIServiceOverallStatus.DEGRADED

    def test_non_critical_service_degraded(self) -> None:
        """Test overall status is degraded when a non-critical service is degraded."""
        non_critical = {cfg["name"] for cfg in AI_SERVICES_CONFIG if not cfg["critical"]}
        victim = sorted(non_critical)[0]
        services = self._health({victim: AIServiceStatus.DEGRADED})

        assert _calculate_overall_status(services) == AIServiceOverallStatus.DEGRADED


# =============================================================================
# API Endpoint Tests
# =============================================================================


class TestAIServicesHealthEndpoint:
    """Tests for the /api/health/ai-services endpoint."""

    @pytest.mark.asyncio
    async def test_endpoint_returns_200_when_healthy(self, async_client: AsyncClient) -> None:
        """Test endpoint returns 200 when all services are healthy."""
        mock_settings = create_mock_settings()
        with patch(
            "backend.api.routes.health_ai_services.get_settings", autospec=True
        ) as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "backend.services.circuit_breaker._get_registry", autospec=True
            ) as mock_registry:
                mock_breaker = MagicMock()
                mock_breaker.state.value = "closed"
                mock_breaker.get_status.return_value = {
                    "failure_count": 0,
                    "total_calls": 100,
                    "rejected_calls": 0,
                }
                mock_registry.return_value.get.return_value = mock_breaker

                with patch(
                    "backend.api.routes.health_ai_services.httpx.AsyncClient", autospec=True
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
        mock_settings = create_mock_settings()
        with patch(
            "backend.api.routes.health_ai_services.get_settings", autospec=True
        ) as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "backend.services.circuit_breaker._get_registry", autospec=True
            ) as mock_registry:
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
        """Test endpoint reports exactly the rows of the SHIPPED table.

        ai-vlm is a row of AI_SERVICES_CONFIG itself (R8 S2), so the key set is
        the live two rows; every retired name is asserted absent. The literal
        expected set is deliberate here -- pinning WHICH rows ship is the point,
        and it is non-vacuous because the table still has rows to report.
        """
        mock_settings = create_mock_settings()
        with patch(
            "backend.api.routes.health_ai_services.get_settings", autospec=True
        ) as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "backend.services.circuit_breaker._get_registry", autospec=True
            ) as mock_registry:
                mock_breaker = MagicMock()
                mock_breaker.state.value = "closed"
                mock_breaker.get_status.return_value = {
                    "failure_count": 0,
                    "total_calls": 0,
                    "rejected_calls": 0,
                }
                mock_registry.return_value.get.return_value = mock_breaker

                with patch(
                    "backend.api.routes.health_ai_services.httpx.AsyncClient", autospec=True
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
                    assert "ai-vlm" in services
                    # Absence, not presence, for every retired row: the endpoint
                    # reports AI_SERVICES_CONFIG, and R8 S3 (owner rulings 1 + 5)
                    # deleted the florence/clip/enrichment rows along with the LLM
                    # row S2b took. A row reappearing here means a service name
                    # came back without a ruling.
                    assert set(services) == {"yolo26", "ai-vlm"}, sorted(services)
                    for retired in ("nemotron", "florence", "clip", "enrichment"):
                        assert retired not in services

    @pytest.mark.asyncio
    async def test_endpoint_includes_queue_info(self, async_client: AsyncClient) -> None:
        """Test endpoint includes queue depth information."""
        mock_settings = create_mock_settings(
            yolo26_url="",
            ai_vlm_url="",
        )
        with patch(
            "backend.api.routes.health_ai_services.get_settings", autospec=True
        ) as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "backend.services.circuit_breaker._get_registry", autospec=True
            ) as mock_registry:
                mock_registry.return_value.get.return_value = None

                response = await async_client.get("/api/health/ai-services")

                data = response.json()
                queues = data["queues"]
                assert "detection_queue" in queues
                assert "analysis_queue" in queues
                assert "depth" in queues["detection_queue"]
                assert "dlq_depth" in queues["detection_queue"]
