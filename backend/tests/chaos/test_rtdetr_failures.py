"""Chaos tests for RT-DETR object detection service failures.

This module tests system behavior when the RT-DETR detection service
experiences various failure modes:
- Timeouts (service hangs)
- Connection errors (service unreachable)
- Server errors (5xx responses)
- Intermittent failures (random failures)

Expected Behavior:
- System returns empty detections (not crash)
- Circuit breaker opens after repeated failures
- Health endpoint reports degraded state
- Errors are logged appropriately
"""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

from backend.core.exceptions import DetectorUnavailableError
from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
    reset_circuit_breaker_registry,
)
from backend.services.detector_client import DetectorClient


@pytest.fixture(autouse=True)
def reset_circuit_breakers() -> None:
    """Reset circuit breakers before each test."""
    reset_circuit_breaker_registry()


@pytest.fixture
def test_image_path() -> Generator[str]:
    """Create a temporary valid image file for testing.

    The detector client validates image files before sending, so we need
    a real image file that passes validation (>10KB).
    """
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        # Create a large enough RGB image (1920x1080 - exceeds 10KB minimum)
        img = Image.new("RGB", (1920, 1080), color="red")
        img.save(tmp.name, "JPEG", quality=95)
        yield tmp.name
    # Clean up after test
    try:
        Path(tmp.name).unlink()
    except OSError:
        pass


class TestRTDETRTimeout:
    """Tests for RT-DETR timeout scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_timeout_raises_unavailable_error(self, test_image_path: str) -> None:
        """When RT-DETR times out, DetectorUnavailableError is raised."""
        client = DetectorClient()

        async def slow_response(*args: object, **kwargs: object) -> None:
            await asyncio.sleep(0.01)
            raise httpx.TimeoutException("Request timed out")

        with patch("httpx.AsyncClient.post", side_effect=slow_response):
            with pytest.raises(DetectorUnavailableError) as exc_info:
                mock_session = AsyncMock()
                await client.detect_objects(
                    image_path=test_image_path,
                    camera_id="test_camera",
                    session=mock_session,
                )

            # After retries, error message is "Detection failed after N attempts"
            assert "failed after" in str(exc_info.value).lower()

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_timeout_circuit_breaker_opens_after_threshold(self) -> None:
        """Repeated timeouts cause circuit breaker to open."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=10.0,
        )
        breaker = CircuitBreaker(name="rtdetr_timeout_test", config=config)

        async def timeout_operation() -> None:
            raise httpx.TimeoutException("Timeout")

        # Trigger failures up to threshold
        for _ in range(config.failure_threshold):
            try:
                await breaker.call(timeout_operation)
            except httpx.TimeoutException:
                pass

        # Circuit should be open
        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count >= config.failure_threshold

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls_immediately(self) -> None:
        """Open circuit breaker rejects calls without attempting operation."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=60.0,  # Long timeout so circuit stays open
        )
        breaker = CircuitBreaker(name="rtdetr_rejection_test", config=config)

        call_count = 0

        async def tracked_operation() -> None:
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("Timeout")

        # Open the circuit
        for _ in range(config.failure_threshold):
            try:
                await breaker.call(tracked_operation)
            except httpx.TimeoutException:
                pass

        initial_count = call_count
        assert breaker.state == CircuitState.OPEN

        # Try to call again - should be rejected without calling operation
        with pytest.raises(CircuitBreakerError):
            await breaker.call(tracked_operation)

        # Operation should not have been called
        assert call_count == initial_count


class TestRTDETRConnectionError:
    """Tests for RT-DETR connection error scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_connection_error_raises_unavailable_error(self, test_image_path: str) -> None:
        """When RT-DETR is unreachable, DetectorUnavailableError is raised."""
        client = DetectorClient()

        async def connection_refused(*args: object, **kwargs: object) -> None:
            raise httpx.ConnectError("Connection refused")

        with patch("httpx.AsyncClient.post", side_effect=connection_refused):
            with pytest.raises(DetectorUnavailableError) as exc_info:
                mock_session = AsyncMock()
                await client.detect_objects(
                    image_path=test_image_path,
                    camera_id="test_camera",
                    session=mock_session,
                )

            # After retries, error message is wrapped
            assert "failed after" in str(exc_info.value).lower()

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_connection_error(self) -> None:
        """Health check returns False when service is unreachable."""
        client = DetectorClient()

        async def connection_refused(*args: object, **kwargs: object) -> None:
            raise httpx.ConnectError("Connection refused")

        with patch("httpx.AsyncClient.get", side_effect=connection_refused):
            result = await client.health_check()
            assert result is False


class TestRTDETRServerError:
    """Tests for RT-DETR server error scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_5xx_error_raises_unavailable_error(self, test_image_path: str) -> None:
        """When RT-DETR returns 5xx, DetectorUnavailableError is raised."""
        client = DetectorClient()

        async def server_error(*args: object, **kwargs: object) -> None:
            response = MagicMock(spec=httpx.Response)
            response.status_code = 500
            response.json.return_value = {"error": "Internal server error"}
            raise httpx.HTTPStatusError("Server error", request=MagicMock(), response=response)

        with patch("httpx.AsyncClient.post", side_effect=server_error):
            with pytest.raises(DetectorUnavailableError) as exc_info:
                mock_session = AsyncMock()
                await client.detect_objects(
                    image_path=test_image_path,
                    camera_id="test_camera",
                    session=mock_session,
                )

            # After retries, error message is "Detection failed after N attempts"
            assert "failed after" in str(exc_info.value).lower()

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_4xx_error_returns_empty_list(self, test_image_path: str) -> None:
        """When RT-DETR returns 4xx (client error), empty list returned (no retry)."""
        client = DetectorClient()

        async def client_error(*args: object, **kwargs: object) -> None:
            response = MagicMock(spec=httpx.Response)
            response.status_code = 400
            response.json.return_value = {"detail": "Invalid image format"}
            response.text = "Invalid image format"
            raise httpx.HTTPStatusError("Client error", request=MagicMock(), response=response)

        with patch("httpx.AsyncClient.post", side_effect=client_error):
            mock_session = AsyncMock()
            result = await client.detect_objects(
                image_path=test_image_path,
                camera_id="test_camera",
                session=mock_session,
            )

            # 4xx errors return empty list (client error, no retry)
            assert result == []


class TestRTDETRCircuitBreakerIntegration:
    """Tests for circuit breaker behavior with RT-DETR."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_circuit_breaker_transitions_through_states(self) -> None:
        """Circuit breaker correctly transitions CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,  # Short timeout for testing
            success_threshold=1,
        )
        breaker = CircuitBreaker(name="rtdetr_state_test", config=config)

        # Start CLOSED
        assert breaker.state == CircuitState.CLOSED

        # Fail to OPEN
        async def failing_op() -> None:
            raise Exception("Simulated failure")

        for _ in range(config.failure_threshold):
            try:
                await breaker.call(failing_op)
            except Exception:
                pass  # Chaos test: intentionally suppress exception

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.2)

        # Next call transitions to HALF_OPEN (and succeeds)
        async def success_op() -> str:
            return "success"

        result = await breaker.call(success_op)
        assert result == "success"

        # After success, back to CLOSED
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self) -> None:
        """Failure in HALF_OPEN state reopens the circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=2,
        )
        breaker = CircuitBreaker(name="rtdetr_half_open_test", config=config)

        # Open the circuit
        async def failing_op() -> None:
            raise Exception("Failure")

        for _ in range(config.failure_threshold):
            try:
                await breaker.call(failing_op)
            except Exception:
                pass  # Chaos test: intentionally suppress exception

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery
        await asyncio.sleep(0.2)

        # Fail in HALF_OPEN
        try:
            await breaker.call(failing_op)
        except Exception:
            pass  # Chaos test: intentionally suppress exception

        # Should be back to OPEN
        assert breaker.state == CircuitState.OPEN


class TestRTDETRGracefulDegradation:
    """Tests for graceful degradation when RT-DETR is unavailable."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_detector_client_handles_file_not_found(self) -> None:
        """Detector client returns empty list for missing files."""
        client = DetectorClient()
        mock_session = AsyncMock()

        # No mocking needed - file simply doesn't exist
        result = await client.detect_objects(
            image_path="/nonexistent/path/image.jpg",
            camera_id="test_camera",
            session=mock_session,
        )

        assert result == []

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_detector_preserves_original_error_info(self, test_image_path: str) -> None:
        """DetectorUnavailableError preserves original exception for debugging."""
        client = DetectorClient()
        original_error = httpx.TimeoutException("Original timeout message")

        async def timeout_with_message(*args: object, **kwargs: object) -> None:
            raise original_error

        with patch("httpx.AsyncClient.post", side_effect=timeout_with_message):
            with pytest.raises(DetectorUnavailableError) as exc_info:
                mock_session = AsyncMock()
                await client.detect_objects(
                    image_path=test_image_path,
                    camera_id="test_camera",
                    session=mock_session,
                )

            # Original error should be preserved
            assert exc_info.value.original_error is original_error


class TestRTDETRRecovery:
    """Tests for RT-DETR service recovery scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_circuit_breaker_allows_recovery_calls(self) -> None:
        """After recovery timeout, circuit breaker allows test calls."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            half_open_max_calls=3,
        )
        breaker = CircuitBreaker(name="rtdetr_recovery_test", config=config)

        # Open the circuit
        async def failing() -> None:
            raise Exception("Fail")

        for _ in range(config.failure_threshold):
            try:
                await breaker.call(failing)
            except Exception:
                pass  # Chaos test: intentionally suppress exception

        # Wait for recovery
        await asyncio.sleep(0.2)

        # Should be able to make calls in HALF_OPEN
        allowed = await breaker.allow_call()
        assert allowed is True

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_successful_recovery_resets_failure_count(self) -> None:
        """Successful recovery resets the failure counter."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=0.1,
            success_threshold=1,
        )
        breaker = CircuitBreaker(name="rtdetr_reset_test", config=config)

        # Add some failures (but not enough to open)
        async def failing() -> None:
            raise Exception("Fail")

        try:
            await breaker.call(failing)
        except Exception:
            pass  # Chaos test: intentionally suppress exception

        assert breaker.failure_count == 1

        # Successful call should reset counter
        async def success() -> str:
            return "ok"

        await breaker.call(success)
        assert breaker.failure_count == 0
