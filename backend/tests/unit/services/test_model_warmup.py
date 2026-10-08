"""Unit tests for AI model cold start detection and warm-up strategy.

These tests cover the model readiness probing, warm-up logic, and cold start
tracking for the DetectorClient service, plus the Prometheus warmup metrics
and the health-monitor/system-API warming-state surface.

The NemotronAnalyzer half of this suite retired with R8 (2026-09-29): the
module is gone, so the analyzer-side probe/warm/cold pins went with it. The
VLM path has no warmup surface (``VlmAnalyzer`` defines neither
``model_readiness_probe`` nor ``warmup``/``is_cold``), so there is nothing to
repoint those pins to.

NEM-1670: Add AI Model Cold Start Detection and Warm-up Strategy
"""

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


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
        # pydantic v2 field names are not in dir(Settings), so a spec'd mock only
        # exposes what is pinned explicitly — the list below is exactly what
        # DetectorClient's __init__ reads (detector_client.py:287-351). The
        # P0.3 constrained-decoding flags, nemotron_model_id and
        # nemotron_verification_engine assignments this fixture used to carry
        # went with the NemotronAnalyzer half of the file: DetectorClient reads
        # no AI-LLM setting (surviving or deleted), so nothing here replaces them.
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
        mock.detection_class_thresholds = {}
        return mock

    @pytest.fixture
    async def detector_client(self, mock_settings):
        """Create DetectorClient instance with mocked settings."""
        with patch(
            "backend.services.detector_client.get_settings",
            return_value=mock_settings,
            autospec=True,
        ):
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
        """Test recording warmup duration in histogram.

        Labels are the live ones: "yolo26" (detector_client.py:577) and "ai-vlm"
        — the retired "nemotron" label went with the analyzer, and the VLM path
        stamps the breaker name (vlm_client.BREAKER_NAME == "ai-vlm").
        """
        from backend.core.metrics import observe_model_warmup_duration

        # Should not raise
        observe_model_warmup_duration("ai-vlm", 2.5)
        observe_model_warmup_duration("yolo26", 1.2)

    def test_record_cold_start(self):
        """Test recording cold start in counter (same live labels as above;
        vlm_client.py:973 records the cold start under "ai-vlm")."""
        from backend.core.metrics import record_model_cold_start

        # Should not raise
        record_model_cold_start("ai-vlm")
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
        # The "ai-nemotron" row re-homed to the shipped AI-service label: R8 S2
        # deleted the nemotron container's ServiceConfig row and relabelled the
        # health surface "ai-vlm" (routes/system.py:1061 — the two AI services
        # the health endpoint reports are "yolo26" and "ai-vlm").
        registry.register(
            ManagedService(
                name="ai-vlm",
                display_name="AI VLM",
                container_id="def456",
                image="ai-vlm:latest",
                port=8098,
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
        mock_registry.update_warmth_state("ai-vlm", "cold")

        warmth_states = mock_registry.get_ai_warmth_states()

        assert warmth_states["ai-yolo26"] == "warm"
        assert warmth_states["ai-vlm"] == "cold"


# ==============================================================================
# System API Warming State Tests
# ==============================================================================


class TestSystemAPIWarmingState:
    """Tests for warming state exposure via system API."""

    @pytest.mark.asyncio
    async def test_health_response_includes_warming_state(self):
        """Test that health response includes AI model warming states."""
        from backend.api.schemas.system import HealthCheckServiceStatus

        # Verify schema supports warming state in AI details. The detail keys are
        # the two AI services the health endpoint actually reports
        # (routes/system.py:1060-1061): "yolo26" and "ai-vlm".
        ai_status = HealthCheckServiceStatus(
            status="healthy",
            message="AI services operational",
            details={
                "yolo26": "healthy",
                "ai-vlm": "healthy",
                "yolo26_warmth": "warm",
                "ai-vlm_warmth": "cold",
            },
        )

        assert ai_status.details["yolo26_warmth"] == "warm"
        assert ai_status.details["ai-vlm_warmth"] == "cold"

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
                # The retired analyzer's model key re-homed to the deployed VLM
                # service label (same rename as the ai-vlm health row above).
                "ai-vlm": "warm",
            },
            # B1.4 made verdict_engine required (the route always populates it);
            # this test is about warmth, so it carries the honest empty state.
            verdict_engine={
                "state": "unknown",
                "since": datetime.now(UTC),
                "reason": "not probed yet",
            },
        )

        assert response.ready is True
        assert response.ai_warmth_status["yolo26"] == "warming"
