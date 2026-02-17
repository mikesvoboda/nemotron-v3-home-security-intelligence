"""Unit tests for setup_lib.healthcheck module.

Tests HTTP health polling and service health check functions.
"""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch


class TestPollEndpoint:
    """Tests for poll_endpoint() function."""

    def test_returns_true_on_success(self) -> None:
        """Should return True when endpoint returns 200."""
        from setup_lib.healthcheck import poll_endpoint

        mock_response = MagicMock()
        mock_response.status = 200

        with patch("setup_lib.healthcheck.urllib.request.urlopen", return_value=mock_response):
            result = poll_endpoint("http://localhost:8000/health", timeout=5)

            assert result is True

    def test_returns_false_on_timeout(self) -> None:
        """Should return False when endpoint never responds within timeout."""
        from setup_lib.healthcheck import poll_endpoint

        with (
            patch(
                "setup_lib.healthcheck.urllib.request.urlopen",
                side_effect=urllib.error.URLError("Connection refused"),
            ),
            patch("time.sleep"),
            patch("time.monotonic") as mock_time,
        ):
            # Simulate time progression: start at 0, deadline check, then past deadline
            mock_time.side_effect = [0, 0.1, 0.2, 100]

            result = poll_endpoint("http://localhost:8000/health", timeout=5, interval=1)

            assert result is False

    def test_retries_on_failure(self) -> None:
        """Should retry after failure and return True when eventually succeeds."""
        from setup_lib.healthcheck import poll_endpoint

        mock_response = MagicMock()
        mock_response.status = 200

        call_count = 0

        def urlopen_side_effect(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise urllib.error.URLError("Connection refused")
            return mock_response

        with (
            patch(
                "setup_lib.healthcheck.urllib.request.urlopen",
                side_effect=urlopen_side_effect,
            ),
            patch("time.sleep"),
        ):
            result = poll_endpoint("http://localhost:8000/health", timeout=60, interval=1)

            assert result is True
            assert call_count == 3


class TestCheckServiceHealth:
    """Tests for check_service_health() function."""

    def test_healthy_response(self) -> None:
        """Should return healthy status with response data on success."""
        from setup_lib.healthcheck import check_service_health

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"status": "ok"}).encode()

        with patch("setup_lib.healthcheck.urllib.request.urlopen", return_value=mock_response):
            result = check_service_health("Backend", "http://localhost:8000/health")

            assert result["name"] == "Backend"
            assert result["status"] == "healthy"
            assert result["error"] is None
            assert result["data"] == {"status": "ok"}
            assert isinstance(result["response_time_ms"], int)

    def test_unhealthy_response(self) -> None:
        """Should return unhealthy status when request fails."""
        from setup_lib.healthcheck import check_service_health

        with patch(
            "setup_lib.healthcheck.urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            result = check_service_health("Backend", "http://localhost:8000/health")

            assert result["name"] == "Backend"
            assert result["status"] == "unhealthy"
            assert result["error"] is not None
            assert result["data"] is None
            assert isinstance(result["response_time_ms"], int)
