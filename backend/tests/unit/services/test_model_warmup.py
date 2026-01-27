"""Unit tests for AI model cold start detection and warm-up strategy.

These tests cover the model readiness probing, warm-up logic, and cold start
tracking for both NemotronAnalyzer and DetectorClient services.

NEM-1670: Add AI Model Cold Start Detection and Warm-up Strategy
"""

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# ==============================================================================
# NemotronAnalyzer Cold Start / Warmup Tests
# ==============================================================================


class TestNemotronAnalyzerWarmup:
    """Tests for NemotronAnalyzer model warmup and cold start detection."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for NemotronAnalyzer."""
        from backend.core.config import Settings

        mock = MagicMock(spec=Settings)
        mock.nemotron_url = "http://localhost:8091"
        mock.nemotron_api_key = None
        mock.ai_connect_timeout = 10.0
        mock.nemotron_read_timeout = 120.0
        mock.ai_health_timeout = 5.0
        mock.nemotron_max_retries = 1
        mock.severity_low_max = 29
        mock.severity_medium_max = 59
        mock.severity_high_max = 84
        mock.nemotron_context_window = 4096
        mock.nemotron_max_output_tokens = 1536
        mock.context_utilization_warning_threshold = 0.80
        mock.context_truncation_enabled = True
        mock.llm_tokenizer_encoding = "cl100k_base"
        mock.image_quality_enabled = False
        # Guided JSON settings (NEM-3726)
        mock.nemotron_use_guided_json = False
        mock.nemotron_guided_json_fallback = True
        # Warmup-specific settings (NEM-1670)
        mock.ai_warmup_enabled = True
        mock.ai_cold_start_threshold_seconds = 300.0  # 5 minutes
        mock.nemotron_warmup_prompt = "Hello, please respond with 'ready'."
        return mock

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client."""
        from backend.core.redis import RedisClient

        mock_client = MagicMock(spec=RedisClient)
        mock_client.get = AsyncMock(return_value=None)
        mock_client.set = AsyncMock(return_value=True)
        mock_client.delete = AsyncMock(return_value=1)
        mock_client.publish = AsyncMock(return_value=1)
        return mock_client

    @pytest.fixture
    def analyzer(self, mock_redis_client, mock_settings):
        """Create NemotronAnalyzer instance with mocked dependencies."""
        with (
            patch("backend.services.nemotron_analyzer.get_settings", return_value=mock_settings),
            patch("backend.services.severity.get_settings", return_value=mock_settings),
            patch("backend.services.token_counter.get_settings", return_value=mock_settings),
            patch("backend.core.config.get_settings", return_value=mock_settings),
        ):
            from backend.services.nemotron_analyzer import NemotronAnalyzer
            from backend.services.severity import reset_severity_service
            from backend.services.token_counter import reset_token_counter

            reset_severity_service()
            reset_token_counter()
            yield NemotronAnalyzer(redis_client=mock_redis_client)
            reset_severity_service()
            reset_token_counter()

    @pytest.mark.asyncio
    async def test_model_readiness_probe_success(self, analyzer):
        """Test that model_readiness_probe returns True when inference succeeds."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.json.return_value = {"content": "ready"}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await analyzer.model_readiness_probe()

        assert result is True

    @pytest.mark.asyncio
    async def test_model_readiness_probe_failure_connection_error(self, analyzer):
        """Test that model_readiness_probe returns False on connection error."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")

            result = await analyzer.model_readiness_probe()

        assert result is False

    @pytest.mark.asyncio
    async def test_model_readiness_probe_failure_timeout(self, analyzer):
        """Test that model_readiness_probe returns False on timeout."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Request timeout")

            result = await analyzer.model_readiness_probe()

        assert result is False

    @pytest.mark.asyncio
    async def test_warmup_on_startup_success(self, analyzer):
        """Test that warmup sends a test prompt and records warmup duration."""
        with patch.object(analyzer, "model_readiness_probe", new_callable=AsyncMock) as mock_probe:
            mock_probe.return_value = True

            result = await analyzer.warmup()

        assert result is True
        mock_probe.assert_called_once()
        # Should track the warmup completion time
        assert analyzer._last_inference_time is not None

    @pytest.mark.asyncio
    async def test_warmup_on_startup_failure(self, analyzer):
        """Test that warmup returns False when model is not ready."""
        with patch.object(analyzer, "model_readiness_probe", new_callable=AsyncMock) as mock_probe:
            mock_probe.return_value = False

            result = await analyzer.warmup()

        assert result is False

    def test_is_cold_when_never_used(self, analyzer):
        """Test that model is considered cold when never used."""
        # Ensure _last_inference_time is None (never used)
        analyzer._last_inference_time = None

        assert analyzer.is_cold() is True

    def test_is_cold_after_threshold_exceeded(self, analyzer, mock_settings):
        """Test that model is cold after cold_start_threshold_seconds."""
        # Set last inference time to 10 minutes ago (threshold is 5 minutes)
        analyzer._last_inference_time = time.monotonic() - 600

        assert analyzer.is_cold() is True

    def test_is_warm_within_threshold(self, analyzer):
        """Test that model is warm within cold_start_threshold_seconds."""
        # Set last inference time to 1 minute ago
        analyzer._last_inference_time = time.monotonic() - 60

        assert analyzer.is_cold() is False

    def test_get_warmth_state_cold(self, analyzer):
        """Test get_warmth_state returns 'cold' when model is cold."""
        analyzer._last_inference_time = None

        state = analyzer.get_warmth_state()

        assert state["state"] == "cold"
        assert state["last_inference_seconds_ago"] is None

    def test_get_warmth_state_warm(self, analyzer):
        """Test get_warmth_state returns 'warm' when model is warm."""
        analyzer._last_inference_time = time.monotonic() - 30

        state = analyzer.get_warmth_state()

        assert state["state"] == "warm"
        assert state["last_inference_seconds_ago"] is not None
        assert state["last_inference_seconds_ago"] < 60

    def test_get_warmth_state_warming(self, analyzer):
        """Test get_warmth_state returns 'warming' during warmup."""
        analyzer._is_warming = True
        analyzer._last_inference_time = None

        state = analyzer.get_warmth_state()

        assert state["state"] == "warming"

    def test_track_inference_updates_last_inference_time(self, analyzer):
        """Test that _track_inference updates the last inference timestamp."""
        assert analyzer._last_inference_time is None

        analyzer._track_inference()

        assert analyzer._last_inference_time is not None


# ==============================================================================
# DetectorClient Cold Start / Warmup Tests
# ==============================================================================


class TestDetectorClientWarmup:
    """Tests for DetectorClient (YOLO26) model warmup and cold start detection."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for DetectorClient."""
        from backend.core.config import Settings

        mock = MagicMock(spec=Settings)
        mock.yolo26_url = "http://localhost:8090"
        mock.yolo26_api_key = None
        mock.ai_connect_timeout = 10.0
        mock.yolo26_read_timeout = 60.0
        mock.ai_health_timeout = 5.0
        mock.detector_max_retries = 1
        mock.detection_confidence_threshold = 0.5
        mock.ai_max_concurrent_inferences = 4
        # Detector type selection (default to yolo26)
        mock.detector_type = "yolo26"
        # YOLO26 settings (needed even when using yolo26 to avoid attribute errors)
        mock.yolo26_url = "http://localhost:8095"
        mock.yolo26_api_key = None
        mock.yolo26_read_timeout = 30.0
        # Warmup-specific settings (NEM-1670)
        mock.ai_warmup_enabled = True
        mock.ai_cold_start_threshold_seconds = 300.0  # 5 minutes
        return mock

    @pytest.fixture
    async def detector_client(self, mock_settings):
        """Create DetectorClient instance with mocked settings."""
        with patch("backend.services.detector_client.get_settings", return_value=mock_settings):
            from backend.services.detector_client import DetectorClient

            client = DetectorClient()
            yield client
            # Cleanup: close HTTP clients
            await client.close()

    @pytest.mark.asyncio
    async def test_model_readiness_probe_success(self, detector_client):
        """Test that model_readiness_probe returns True when detection succeeds."""
        with patch.object(
            detector_client, "_send_detection_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = {"detections": []}

            result = await detector_client.model_readiness_probe()

        assert result is True

    @pytest.mark.asyncio
    async def test_model_readiness_probe_failure(self, detector_client):
        """Test that model_readiness_probe returns False on error."""
        from backend.services.detector_client import DetectorUnavailableError

        with patch.object(
            detector_client, "_send_detection_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.side_effect = DetectorUnavailableError("Service unavailable")

            result = await detector_client.model_readiness_probe()

        assert result is False

    @pytest.mark.asyncio
    async def test_warmup_with_test_image_success(self, detector_client):
        """Test warmup sends a test image and records completion."""
        with patch.object(
            detector_client, "model_readiness_probe", new_callable=AsyncMock
        ) as mock_probe:
            mock_probe.return_value = True

            result = await detector_client.warmup()

        assert result is True
        mock_probe.assert_called_once()
        assert detector_client._last_inference_time is not None

    @pytest.mark.asyncio
    async def test_warmup_failure(self, detector_client):
        """Test warmup returns False when model is not ready."""
        with patch.object(
            detector_client, "model_readiness_probe", new_callable=AsyncMock
        ) as mock_probe:
            mock_probe.return_value = False

            result = await detector_client.warmup()

        assert result is False

    def test_is_cold_when_never_used(self, detector_client):
        """Test detector is cold when never used."""
        detector_client._last_inference_time = None

        assert detector_client.is_cold() is True

    def test_is_cold_after_threshold_exceeded(self, detector_client):
        """Test detector is cold after cold_start_threshold_seconds."""
        detector_client._last_inference_time = time.monotonic() - 600

        assert detector_client.is_cold() is True

    def test_is_warm_within_threshold(self, detector_client):
        """Test detector is warm within cold_start_threshold_seconds."""
        detector_client._last_inference_time = time.monotonic() - 60

        assert detector_client.is_cold() is False

    def test_get_warmth_state_returns_correct_structure(self, detector_client):
        """Test get_warmth_state returns proper state structure."""
        detector_client._last_inference_time = time.monotonic() - 30

        state = detector_client.get_warmth_state()

        assert "state" in state
        assert "last_inference_seconds_ago" in state
        assert state["state"] in ("cold", "warm", "warming")


# ==============================================================================
# Prometheus Metrics Tests
# ==============================================================================


class TestWarmupMetrics:
    """Tests for cold start and warmup duration Prometheus metrics."""

    def test_warmup_duration_metric_exists(self):
        """Test that warmup duration histogram metric is defined."""
        from backend.core.metrics import MODEL_WARMUP_DURATION

        assert MODEL_WARMUP_DURATION is not None
        assert MODEL_WARMUP_DURATION._name == "hsi_model_warmup_duration_seconds"

    def test_cold_start_counter_metric_exists(self):
        """Test that cold start counter metric is defined."""
        from backend.core.metrics import MODEL_COLD_START_TOTAL

        assert MODEL_COLD_START_TOTAL is not None
        # prometheus_client internally stores name without _total suffix
        assert MODEL_COLD_START_TOTAL._name == "hsi_model_cold_start"

    def test_record_warmup_duration(self):
        """Test recording warmup duration in histogram."""
        from backend.core.metrics import observe_model_warmup_duration

        # Should not raise
        observe_model_warmup_duration("nemotron", 2.5)
        observe_model_warmup_duration("yolo26", 1.2)

    def test_record_cold_start(self):
        """Test recording cold start in counter."""
        from backend.core.metrics import record_model_cold_start

        # Should not raise
        record_model_cold_start("nemotron")
        record_model_cold_start("yolo26")


# ==============================================================================
# Health Monitor Orchestrator Warming State Tests
# ==============================================================================


class TestHealthMonitorOrchestratorWarmingState:
    """Tests for warming state tracking in health monitor orchestrator."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock service registry."""
        from backend.api.schemas.services import ServiceCategory
        from backend.services.health_monitor_orchestrator import ManagedService, ServiceRegistry

        registry = ServiceRegistry()
        # Add AI services
        registry.register(
            ManagedService(
                name="ai-yolo26",
                display_name="AI Detector",
                container_id="abc123",
                image="yolo26:latest",
                port=8095,
                category=ServiceCategory.AI,
                health_endpoint="/health",
            )
        )
        registry.register(
            ManagedService(
                name="ai-nemotron",
                display_name="AI Nemotron",
                container_id="def456",
                image="nemotron:latest",
                port=8091,
                category=ServiceCategory.AI,
                health_endpoint="/health",
            )
        )
        return registry

    def test_managed_service_has_warmth_state_field(self):
        """Test ManagedService has warmth_state attribute."""
        from backend.api.schemas.services import ServiceCategory
        from backend.services.health_monitor_orchestrator import ManagedService

        service = ManagedService(
            name="ai-yolo26",
            display_name="AI Detector",
            container_id="abc123",
            image="yolo26:latest",
            port=8095,
            category=ServiceCategory.AI,
        )

        assert hasattr(service, "warmth_state")
        assert service.warmth_state in ("cold", "warm", "warming", "unknown")

    def test_registry_update_warmth_state(self, mock_registry):
        """Test updating warmth state in registry."""
        mock_registry.update_warmth_state("ai-yolo26", "warming")

        service = mock_registry.get("ai-yolo26")
        assert service.warmth_state == "warming"

    def test_registry_get_ai_services_warmth(self, mock_registry):
        """Test getting warmth state for all AI services."""
        mock_registry.update_warmth_state("ai-yolo26", "warm")
        mock_registry.update_warmth_state("ai-nemotron", "cold")

        warmth_states = mock_registry.get_ai_warmth_states()

        assert warmth_states["ai-yolo26"] == "warm"
        assert warmth_states["ai-nemotron"] == "cold"


# ==============================================================================
# System API Warming State Tests
# ==============================================================================


class TestSystemAPIWarmingState:
    """Tests for warming state exposure via system API."""

    @pytest.mark.asyncio
    async def test_health_response_includes_warming_state(self):
        """Test that health response includes AI model warming states."""
        from backend.api.schemas.system import HealthCheckServiceStatus

        # Verify schema supports warming state in AI details
        ai_status = HealthCheckServiceStatus(
            status="healthy",
            message="AI services operational",
            details={
                "yolo26": "healthy",
                "nemotron": "healthy",
                "yolo26_warmth": "warm",
                "nemotron_warmth": "cold",
            },
        )

        assert ai_status.details["yolo26_warmth"] == "warm"
        assert ai_status.details["nemotron_warmth"] == "cold"

    @pytest.mark.asyncio
    async def test_readiness_response_considers_warming_state(self):
        """Test that readiness probe considers warming state for AI services."""
        from backend.api.schemas.system import ReadinessResponse

        # A system with warming AI services should still report ready=True
        # (warming is acceptable, only cold on first request is problematic)
        response = ReadinessResponse(
            ready=True,
            status="ready",
            services={},
            workers=[],
            timestamp=datetime.now(UTC),
            ai_warmth_status={
                "yolo26": "warming",
                "nemotron": "warm",
            },
        )

        assert response.ready is True
        assert response.ai_warmth_status["yolo26"] == "warming"
