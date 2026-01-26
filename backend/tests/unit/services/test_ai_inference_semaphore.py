"""Unit tests for AI inference concurrency limits (NEM-1463).

These tests verify that asyncio.Semaphore properly limits concurrent
AI inference operations for both YOLO26 detection and Nemotron analysis.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestAIInferenceSemaphoreConfiguration:
    """Tests for AI inference semaphore configuration."""

    def test_default_max_concurrent_inferences_from_settings(self):
        """Test that default max concurrent inferences is read from settings."""
        with patch("backend.services.inference_semaphore.get_settings") as mock_settings:
            mock_settings.return_value.ai_max_concurrent_inferences = 4

            from backend.services.inference_semaphore import (
                get_inference_semaphore,
                reset_inference_semaphore,
            )

            # Reset to ensure fresh semaphore
            reset_inference_semaphore()

            semaphore = get_inference_semaphore()

            # Verify semaphore is created with correct limit
            assert semaphore._value == 4

    def test_custom_max_concurrent_inferences(self):
        """Test that custom max concurrent inferences can be configured."""
        with patch("backend.services.inference_semaphore.get_settings") as mock_settings:
            mock_settings.return_value.ai_max_concurrent_inferences = 8

            from backend.services.inference_semaphore import (
                get_inference_semaphore,
                reset_inference_semaphore,
            )

            # Reset to ensure fresh semaphore
            reset_inference_semaphore()

            semaphore = get_inference_semaphore()

            # Verify semaphore is created with custom limit
            assert semaphore._value == 8

    def test_settings_has_ai_max_concurrent_inferences_field(self):
        """Test that Settings class has ai_max_concurrent_inferences field."""
        from backend.core.config import Settings

        # Verify the field exists in the Settings class
        assert hasattr(Settings, "model_fields")
        assert "ai_max_concurrent_inferences" in Settings.model_fields


class TestDetectorClientConcurrencyLimits:
    """Tests for DetectorClient concurrency limiting."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings with semaphore config."""
        mock = MagicMock()
        mock.yolo26_url = "http://localhost:8090"
        mock.detection_confidence_threshold = 0.5
        mock.yolo26_api_key = None
        mock.ai_connect_timeout = 10.0
        mock.yolo26_read_timeout = 60.0
        mock.ai_health_timeout = 5.0
        mock.detector_max_retries = 1
        mock.ai_max_concurrent_inferences = 2  # Limit to 2 concurrent
        return mock

    @pytest.mark.asyncio
    async def test_detect_objects_respects_semaphore_limit(self, mock_settings):
        """Test that detect_objects respects the semaphore concurrency limit."""
        from backend.services.inference_semaphore import reset_inference_semaphore

        # Reset semaphore before test
        reset_inference_semaphore()

        with (
            patch("backend.services.detector_client.get_settings", return_value=mock_settings),
            patch("backend.services.inference_semaphore.get_settings", return_value=mock_settings),
        ):
            from backend.services.detector_client import DetectorClient
            from backend.services.inference_semaphore import get_inference_semaphore

            # Create clients
            client = DetectorClient(max_retries=1)
            # Ensure semaphore is initialized (no need to store reference)
            get_inference_semaphore()

            # Track concurrent requests
            concurrent_count = 0
            max_concurrent = 0
            lock = asyncio.Lock()

            async def mock_post(*args, **kwargs):
                nonlocal concurrent_count, max_concurrent
                async with lock:
                    concurrent_count += 1
                    max_concurrent = max(max_concurrent, concurrent_count)

                # Simulate AI processing time
                await asyncio.sleep(0.1)

                async with lock:
                    concurrent_count -= 1

                response = MagicMock(spec=httpx.Response)
                response.status_code = 200
                response.json.return_value = {
                    "detections": [
                        {"class": "person", "confidence": 0.95, "bbox": [0, 0, 100, 100]}
                    ]
                }
                return response

            mock_session = AsyncMock()
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            mock_session.flush = AsyncMock()
            mock_session.get = AsyncMock(return_value=None)

            mock_baseline = MagicMock()
            mock_baseline.update_baseline = AsyncMock()

            with (
                patch("pathlib.Path.exists", return_value=True),
                patch("pathlib.Path.read_bytes", return_value=b"fake_image_data"),
                patch("httpx.AsyncClient.post", side_effect=mock_post),
                patch.object(client, "_validate_image_for_detection", return_value=True),
                patch(
                    "backend.services.detector_client.get_baseline_service",
                    return_value=mock_baseline,
                ),
            ):
                # Launch 5 concurrent detection requests
                tasks = [
                    client.detect_objects(f"/img{i}.jpg", "camera1", mock_session) for i in range(5)
                ]

                await asyncio.gather(*tasks)

                # Verify max concurrent never exceeded the limit
                assert max_concurrent <= 2, (
                    f"Max concurrent requests ({max_concurrent}) exceeded limit (2)"
                )

    @pytest.mark.asyncio
    async def test_detect_objects_acquires_and_releases_semaphore(self, mock_settings):
        """Test that detect_objects properly acquires and releases semaphore."""
        from backend.services.inference_semaphore import reset_inference_semaphore

        # Reset semaphore before test
        reset_inference_semaphore()

        with (
            patch("backend.services.detector_client.get_settings", return_value=mock_settings),
            patch("backend.services.inference_semaphore.get_settings", return_value=mock_settings),
        ):
            from backend.services.detector_client import DetectorClient
            from backend.services.inference_semaphore import get_inference_semaphore

            client = DetectorClient(max_retries=1)
            semaphore = get_inference_semaphore()

            # Check initial semaphore value
            initial_value = semaphore._value

            mock_session = AsyncMock()
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            mock_session.flush = AsyncMock()
            mock_session.get = AsyncMock(return_value=None)

            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.json.return_value = {"detections": []}

            mock_baseline = MagicMock()
            mock_baseline.update_baseline = AsyncMock()

            with (
                patch("pathlib.Path.exists", return_value=True),
                patch("pathlib.Path.read_bytes", return_value=b"fake_image_data"),
                patch("httpx.AsyncClient.post", return_value=mock_response),
                patch.object(client, "_validate_image_for_detection", return_value=True),
                patch(
                    "backend.services.detector_client.get_baseline_service",
                    return_value=mock_baseline,
                ),
            ):
                await client.detect_objects("/img.jpg", "camera1", mock_session)

            # Verify semaphore is released (value restored)
            assert semaphore._value == initial_value

    @pytest.mark.asyncio
    async def test_detect_objects_releases_semaphore_on_error(self, mock_settings):
        """Test that detect_objects releases semaphore even when error occurs."""
        from backend.services.inference_semaphore import reset_inference_semaphore

        # Reset semaphore before test
        reset_inference_semaphore()

        with (
            patch("backend.services.detector_client.get_settings", return_value=mock_settings),
            patch("backend.services.inference_semaphore.get_settings", return_value=mock_settings),
        ):
            from backend.services.detector_client import DetectorClient, DetectorUnavailableError
            from backend.services.inference_semaphore import get_inference_semaphore

            client = DetectorClient(max_retries=1)
            semaphore = get_inference_semaphore()

            # Check initial semaphore value
            initial_value = semaphore._value

            mock_session = AsyncMock()
            mock_baseline = MagicMock()
            mock_baseline.update_baseline = AsyncMock()

            with (
                patch("pathlib.Path.exists", return_value=True),
                patch("pathlib.Path.read_bytes", return_value=b"fake_image_data"),
                patch(
                    "httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")
                ),
                patch.object(client, "_validate_image_for_detection", return_value=True),
                patch(
                    "backend.services.detector_client.get_baseline_service",
                    return_value=mock_baseline,
                ),
                pytest.raises(DetectorUnavailableError),
            ):
                await client.detect_objects("/img.jpg", "camera1", mock_session)

            # Verify semaphore is released despite error
            assert semaphore._value == initial_value


class TestNemotronAnalyzerConcurrencyLimits:
    """Tests for NemotronAnalyzer concurrency limiting."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings with semaphore config."""
        mock = MagicMock()
        mock.nemotron_url = "http://localhost:8091"
        mock.nemotron_api_key = None
        mock.ai_connect_timeout = 10.0
        mock.nemotron_read_timeout = 120.0
        mock.ai_health_timeout = 5.0
        mock.nemotron_max_retries = 1
        mock.ai_max_concurrent_inferences = 2  # Limit to 2 concurrent
        mock.severity_low_max = 29
        mock.severity_medium_max = 59
        mock.severity_high_max = 84
        mock.background_evaluation_enabled = False
        # LLM context window settings (NEM-1666)
        mock.nemotron_context_window = 4096
        mock.nemotron_max_output_tokens = 1536
        mock.context_utilization_warning_threshold = 0.80
        mock.context_truncation_enabled = True
        mock.llm_tokenizer_encoding = "cl100k_base"
        return mock

    @pytest.mark.asyncio
    async def test_call_llm_respects_semaphore_limit(self, mock_settings):
        """Test that _call_llm respects the semaphore concurrency limit."""
        from backend.services.analyzer_facade import reset_analyzer_facade
        from backend.services.inference_semaphore import reset_inference_semaphore
        from backend.services.severity import reset_severity_service
        from backend.services.token_counter import reset_token_counter

        # Reset services before test (facade caches semaphore, must reset both)
        reset_analyzer_facade()
        reset_inference_semaphore()
        reset_severity_service()
        reset_token_counter()

        with (
            patch("backend.services.nemotron_analyzer.get_settings", return_value=mock_settings),
            patch("backend.services.inference_semaphore.get_settings", return_value=mock_settings),
            patch("backend.services.severity.get_settings", return_value=mock_settings),
            patch("backend.services.token_counter.get_settings", return_value=mock_settings),
            patch("backend.core.config.get_settings", return_value=mock_settings),
        ):
            from backend.services.nemotron_analyzer import NemotronAnalyzer

            # Create analyzer with mocked Redis
            mock_redis = MagicMock()
            analyzer = NemotronAnalyzer(redis_client=mock_redis, max_retries=1)

            # Track concurrent requests
            concurrent_count = 0
            max_concurrent = 0
            lock = asyncio.Lock()

            async def mock_post(*args, **kwargs):
                nonlocal concurrent_count, max_concurrent
                async with lock:
                    concurrent_count += 1
                    max_concurrent = max(max_concurrent, concurrent_count)

                # Simulate LLM processing time
                await asyncio.sleep(0.1)

                async with lock:
                    concurrent_count -= 1

                response = MagicMock(spec=httpx.Response)
                response.status_code = 200
                response.json.return_value = {
                    "content": '{"risk_score": 50, "risk_level": "medium", "summary": "test", "reasoning": "test"}'
                }
                return response

            with patch("httpx.AsyncClient.post", side_effect=mock_post):
                # Launch 5 concurrent LLM calls
                tasks = [
                    analyzer._call_llm(
                        camera_name="test_camera",
                        start_time="2025-01-01T00:00:00",
                        end_time="2025-01-01T00:01:00",
                        detections_list="1. person",
                    )
                    for _ in range(5)
                ]

                await asyncio.gather(*tasks)

                # Verify max concurrent never exceeded the limit
                assert max_concurrent <= 2, (
                    f"Max concurrent requests ({max_concurrent}) exceeded limit (2)"
                )

    @pytest.mark.asyncio
    async def test_call_llm_releases_semaphore_on_error(self, mock_settings):
        """Test that _call_llm releases semaphore even when error occurs."""
        from backend.services.analyzer_facade import reset_analyzer_facade
        from backend.services.inference_semaphore import reset_inference_semaphore
        from backend.services.severity import reset_severity_service

        # Reset services before test (facade caches semaphore, must reset both)
        reset_analyzer_facade()
        reset_inference_semaphore()
        reset_severity_service()

        with (
            patch("backend.services.nemotron_analyzer.get_settings", return_value=mock_settings),
            patch("backend.services.inference_semaphore.get_settings", return_value=mock_settings),
            patch("backend.services.severity.get_settings", return_value=mock_settings),
        ):
            from backend.services.inference_semaphore import get_inference_semaphore
            from backend.services.nemotron_analyzer import NemotronAnalyzer

            # Create analyzer with mocked Redis
            mock_redis = MagicMock()
            analyzer = NemotronAnalyzer(redis_client=mock_redis, max_retries=1)
            semaphore = get_inference_semaphore()

            # Check initial semaphore value
            initial_value = semaphore._value

            from backend.core.exceptions import AnalyzerUnavailableError

            with (
                patch(
                    "httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")
                ),
                pytest.raises(AnalyzerUnavailableError),
            ):
                await analyzer._call_llm(
                    camera_name="test_camera",
                    start_time="2025-01-01T00:00:00",
                    end_time="2025-01-01T00:01:00",
                    detections_list="1. person",
                )

            # Verify semaphore is released despite error
            assert semaphore._value == initial_value


class TestInferenceSemaphoreModule:
    """Tests for the inference_semaphore module itself."""

    def test_get_inference_semaphore_returns_singleton(self):
        """Test that get_inference_semaphore returns the same instance."""
        with patch("backend.services.inference_semaphore.get_settings") as mock_settings:
            mock_settings.return_value.ai_max_concurrent_inferences = 4

            from backend.services.inference_semaphore import (
                get_inference_semaphore,
                reset_inference_semaphore,
            )

            # Reset to ensure fresh semaphore
            reset_inference_semaphore()

            sem1 = get_inference_semaphore()
            sem2 = get_inference_semaphore()

            assert sem1 is sem2

    def test_reset_inference_semaphore_clears_singleton(self):
        """Test that reset_inference_semaphore clears the singleton."""
        with patch("backend.services.inference_semaphore.get_settings") as mock_settings:
            mock_settings.return_value.ai_max_concurrent_inferences = 4

            from backend.services.inference_semaphore import (
                get_inference_semaphore,
                reset_inference_semaphore,
            )

            # Get initial semaphore
            sem1 = get_inference_semaphore()

            # Reset
            reset_inference_semaphore()

            # Get new semaphore
            sem2 = get_inference_semaphore()

            # Should be different instances
            assert sem1 is not sem2

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrent_operations(self):
        """Test that semaphore actually limits concurrent operations."""
        with patch("backend.services.inference_semaphore.get_settings") as mock_settings:
            mock_settings.return_value.ai_max_concurrent_inferences = 2

            from backend.services.inference_semaphore import (
                get_inference_semaphore,
                reset_inference_semaphore,
            )

            # Reset to ensure fresh semaphore
            reset_inference_semaphore()

            semaphore = get_inference_semaphore()

            # Track concurrent operations
            concurrent_count = 0
            max_concurrent = 0
            lock = asyncio.Lock()

            async def operation():
                nonlocal concurrent_count, max_concurrent
                async with semaphore:
                    async with lock:
                        concurrent_count += 1
                        max_concurrent = max(max_concurrent, concurrent_count)

                    await asyncio.sleep(0.05)

                    async with lock:
                        concurrent_count -= 1

            # Run 10 concurrent operations
            await asyncio.gather(*[operation() for _ in range(10)])

            # Should never exceed limit of 2
            assert max_concurrent == 2


class TestQueueingBehavior:
    """Tests for proper request queuing when limit is reached."""

    @pytest.mark.asyncio
    async def test_requests_queue_when_limit_reached(self):
        """Test that requests properly queue when semaphore limit is reached."""
        with patch("backend.services.inference_semaphore.get_settings") as mock_settings:
            mock_settings.return_value.ai_max_concurrent_inferences = 1  # Only 1 at a time

            from backend.services.inference_semaphore import (
                get_inference_semaphore,
                reset_inference_semaphore,
            )

            # Reset to ensure fresh semaphore
            reset_inference_semaphore()

            semaphore = get_inference_semaphore()

            # Track execution order
            execution_order = []
            lock = asyncio.Lock()

            async def operation(id):
                async with semaphore:
                    async with lock:
                        execution_order.append(f"start_{id}")

                    await asyncio.sleep(0.05)

                    async with lock:
                        execution_order.append(f"end_{id}")

            # Run 3 operations that should execute sequentially
            await asyncio.gather(operation(1), operation(2), operation(3))

            # Each operation should complete before the next starts
            # (within the constraints of asyncio scheduling)
            starts = [x for x in execution_order if x.startswith("start")]
            ends = [x for x in execution_order if x.startswith("end")]

            # Should have 3 starts and 3 ends
            assert len(starts) == 3
            assert len(ends) == 3

            # Verify sequential execution: each start_N should be followed by end_N
            # before the next start (due to semaphore limit of 1)
            for i in range(len(execution_order) - 1):
                item = execution_order[i]
                if item.startswith("start"):
                    # The very next item should be the corresponding end
                    # (with semaphore limit=1, operations are strictly sequential)
                    expected_end = f"end{item[5:]}"  # Extract the ID
                    assert execution_order[i + 1] == expected_end, (
                        f"Expected {expected_end} after {item}, got {execution_order[i + 1]}"
                    )
