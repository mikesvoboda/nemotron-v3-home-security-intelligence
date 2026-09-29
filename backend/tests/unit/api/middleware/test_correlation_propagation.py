"""Unit tests for correlation ID propagation in AI service clients.

NEM-1729: Test that correlation IDs are properly propagated through HTTP
requests to the AI service that still takes them client-side — the YOLO26
detector client — plus the shared correlation helpers themselves.

R8 S2 retired the Nemotron analyzer, and with it its httpx call surface
(NemotronAnalyzer._call_llm / .health_check). The VLM client that replaced
it sends no per-request auth/correlation headers at all, so the analyzer
half of this suite had no surviving subject and went with the module.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestCorrelationHeaderPropagation:
    """Test that correlation headers are propagated to AI services."""

    @pytest.fixture(autouse=True)
    def setup_correlation_context(self):
        """Set up correlation ID context for tests."""
        # Import after setting up mocks to avoid side effects
        from backend.api.middleware.request_id import set_correlation_id
        from backend.core.logging import set_request_id

        # Set correlation ID and request ID in context
        test_correlation_id = "test-correlation-id-12345"
        test_request_id = "test-req"

        set_correlation_id(test_correlation_id)
        set_request_id(test_request_id)

        yield {
            "correlation_id": test_correlation_id,
            "request_id": test_request_id,
        }

        # Clean up context
        set_correlation_id(None)
        set_request_id(None)

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        from sqlalchemy.ext.asyncio import AsyncSession

        session = AsyncMock(spec=AsyncSession)
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def mock_baseline_service(self):
        """Mock baseline service."""
        mock_service = MagicMock()
        mock_service.update_baseline = AsyncMock()
        return mock_service


class TestDetectorClientCorrelation(TestCorrelationHeaderPropagation):
    """Test correlation ID propagation in DetectorClient."""

    @pytest.fixture
    def detector_client(self):
        """Create detector client instance."""
        from backend.services.detector_client import DetectorClient

        return DetectorClient(max_retries=1)

    @pytest.mark.asyncio
    async def test_send_detection_request_includes_correlation_headers(
        self, detector_client, mock_session, setup_correlation_context, mock_baseline_service
    ):
        """Test that _send_detection_request includes X-Correlation-ID header."""
        mock_image_data = b"fake_image_data"
        captured_headers = {}

        async def capture_post(*args, **kwargs):
            """Capture the headers passed to httpx.post."""
            nonlocal captured_headers
            captured_headers = kwargs.get("headers", {})
            # Return successful response
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.json.return_value = {"detections": []}
            return mock_response

        with (
            patch("httpx.AsyncClient.post", side_effect=capture_post, autospec=True),
            patch(
                "backend.services.detector_client.get_baseline_service",
                return_value=mock_baseline_service,
                autospec=True,
            ),
        ):
            await detector_client._send_detection_request(
                image_data=mock_image_data,
                image_name="test.jpg",
                camera_id="test_camera",
                image_path="/test/path/test.jpg",
            )

        # Verify X-Correlation-ID header is present
        assert "X-Correlation-ID" in captured_headers
        assert captured_headers["X-Correlation-ID"] == setup_correlation_context["correlation_id"]

        # Verify X-Request-ID header is also present
        assert "X-Request-ID" in captured_headers
        assert captured_headers["X-Request-ID"] == setup_correlation_context["request_id"]

    @pytest.mark.asyncio
    async def test_detect_objects_propagates_correlation_headers(
        self, detector_client, mock_session, setup_correlation_context, mock_baseline_service
    ):
        """Test that detect_objects propagates correlation headers to detector."""
        image_path = "/export/foscam/front_door/test.jpg"
        camera_id = "front_door"
        mock_image_data = b"fake_image_data"

        captured_headers = {}

        async def capture_post(*args, **kwargs):
            nonlocal captured_headers
            captured_headers = kwargs.get("headers", {})
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "detections": [
                    {
                        "class": "person",
                        "confidence": 0.95,
                        "bbox": [100, 150, 300, 400],
                    }
                ]
            }
            return mock_response

        with (
            patch("pathlib.Path.exists", return_value=True, autospec=True),
            patch("pathlib.Path.read_bytes", return_value=mock_image_data, autospec=True),
            patch("httpx.AsyncClient.post", side_effect=capture_post, autospec=True),
            patch.object(
                detector_client,
                "_validate_image_for_detection_async",
                return_value=True,
                autospec=True,
            ),
            patch(
                "backend.services.detector_client.get_baseline_service",
                return_value=mock_baseline_service,
                autospec=True,
            ),
        ):
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Verify correlation headers were passed
        assert "X-Correlation-ID" in captured_headers
        assert captured_headers["X-Correlation-ID"] == setup_correlation_context["correlation_id"]

    @pytest.mark.asyncio
    async def test_health_check_includes_correlation_headers(
        self, detector_client, setup_correlation_context
    ):
        """Test that health_check includes correlation headers."""
        captured_headers = {}

        async def capture_get(*args, **kwargs):
            nonlocal captured_headers
            captured_headers = kwargs.get("headers", {})
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            return mock_response

        with patch("httpx.AsyncClient.get", side_effect=capture_get, autospec=True):
            await detector_client.health_check()

        # Verify correlation headers are included in health check
        assert "X-Correlation-ID" in captured_headers
        assert captured_headers["X-Correlation-ID"] == setup_correlation_context["correlation_id"]

    @pytest.mark.asyncio
    async def test_correlation_headers_merged_with_auth_headers(
        self, setup_correlation_context, mock_session, mock_baseline_service
    ):
        """Test that correlation headers are merged with API key auth headers."""
        from backend.services.detector_client import DetectorClient

        # Create client with mocked API key setting
        with patch("backend.services.detector_client.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.yolo26_url = "http://test:9001"
            mock_settings.return_value.detection_confidence_threshold = 0.5
            mock_settings.return_value.yolo26_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.return_value.ai_connect_timeout = 10.0
            mock_settings.return_value.yolo26_read_timeout = 60.0
            mock_settings.return_value.ai_health_timeout = 5.0
            mock_settings.return_value.detector_max_retries = 1
            mock_settings.return_value.ai_max_concurrent_inferences = 4

            client = DetectorClient(max_retries=1)

        captured_headers = {}

        async def capture_post(*args, **kwargs):
            nonlocal captured_headers
            captured_headers = kwargs.get("headers", {})
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.json.return_value = {"detections": []}
            return mock_response

        with (
            patch("httpx.AsyncClient.post", side_effect=capture_post, autospec=True),
            patch(
                "backend.services.detector_client.get_baseline_service",
                return_value=mock_baseline_service,
                autospec=True,
            ),
        ):
            await client._send_detection_request(
                image_data=b"test",
                image_name="test.jpg",
                camera_id="test",
                image_path="/test/test.jpg",
            )

        # Verify both auth and correlation headers are present
        assert "X-API-Key" in captured_headers
        assert captured_headers["X-API-Key"] == "test-api-key"
        assert "X-Correlation-ID" in captured_headers
        assert captured_headers["X-Correlation-ID"] == setup_correlation_context["correlation_id"]


class TestGetCorrelationHeadersFunction:
    """Test the get_correlation_headers() helper function."""

    def test_get_correlation_headers_returns_both_ids(self):
        """Test that get_correlation_headers returns both correlation and request IDs."""
        from backend.api.middleware.correlation import get_correlation_headers
        from backend.api.middleware.request_id import set_correlation_id
        from backend.core.logging import set_request_id

        # Set both IDs in context
        set_correlation_id("corr-123")
        set_request_id("req-456")

        try:
            headers = get_correlation_headers()

            assert "X-Correlation-ID" in headers
            assert headers["X-Correlation-ID"] == "corr-123"
            assert "X-Request-ID" in headers
            assert headers["X-Request-ID"] == "req-456"
        finally:
            set_correlation_id(None)
            set_request_id(None)

    def test_get_correlation_headers_empty_when_not_set(self):
        """Test that get_correlation_headers returns empty dict when IDs not set."""
        from backend.api.middleware.correlation import get_correlation_headers
        from backend.api.middleware.request_id import set_correlation_id
        from backend.core.logging import set_request_id

        # Ensure IDs are not set
        set_correlation_id(None)
        set_request_id(None)

        headers = get_correlation_headers()

        assert headers == {}

    def test_get_correlation_headers_partial_when_only_correlation_set(self):
        """Test headers when only correlation ID is set."""
        from backend.api.middleware.correlation import get_correlation_headers
        from backend.api.middleware.request_id import set_correlation_id
        from backend.core.logging import set_request_id

        set_correlation_id("corr-only")
        set_request_id(None)

        try:
            headers = get_correlation_headers()

            assert "X-Correlation-ID" in headers
            assert headers["X-Correlation-ID"] == "corr-only"
            assert "X-Request-ID" not in headers
        finally:
            set_correlation_id(None)


class TestMergeHeadersWithCorrelation:
    """Test the merge_headers_with_correlation() helper function."""

    def test_merge_headers_adds_correlation_to_existing(self):
        """Test merging correlation headers with existing headers."""
        from backend.api.middleware.correlation import merge_headers_with_correlation
        from backend.api.middleware.request_id import set_correlation_id
        from backend.core.logging import set_request_id

        set_correlation_id("merge-corr-id")
        set_request_id("merge-req-id")

        try:
            existing = {"Content-Type": "application/json", "X-Custom": "value"}
            merged = merge_headers_with_correlation(existing)

            # Original headers preserved
            assert merged["Content-Type"] == "application/json"
            assert merged["X-Custom"] == "value"
            # Correlation headers added
            assert merged["X-Correlation-ID"] == "merge-corr-id"
            assert merged["X-Request-ID"] == "merge-req-id"
            # Original dict not modified
            assert "X-Correlation-ID" not in existing
        finally:
            set_correlation_id(None)
            set_request_id(None)

    def test_merge_headers_creates_new_dict_when_none(self):
        """Test merge creates new dict when existing is None."""
        from backend.api.middleware.correlation import merge_headers_with_correlation
        from backend.api.middleware.request_id import set_correlation_id

        set_correlation_id("new-dict-corr")

        try:
            merged = merge_headers_with_correlation(None)

            assert "X-Correlation-ID" in merged
            assert merged["X-Correlation-ID"] == "new-dict-corr"
        finally:
            set_correlation_id(None)
