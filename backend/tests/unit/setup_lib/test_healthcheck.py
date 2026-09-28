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

        with patch(
            "setup_lib.healthcheck.urllib.request.urlopen",
            return_value=mock_response,
            autospec=True,
        ):
            result = poll_endpoint("http://localhost:8000/health", timeout=5)

            assert result is True

    def test_returns_false_on_timeout(self) -> None:
        """Should return False when endpoint never responds within timeout."""
        from setup_lib.healthcheck import poll_endpoint

        with (
            patch(
                "setup_lib.healthcheck.urllib.request.urlopen",
                side_effect=urllib.error.URLError("Connection refused"),
                autospec=True,
            ),
            patch("time.sleep", autospec=True),
            patch("time.monotonic", autospec=True) as mock_time,
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
                autospec=True,
            ),
            patch("time.sleep", autospec=True),
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

        with patch(
            "setup_lib.healthcheck.urllib.request.urlopen",
            return_value=mock_response,
            autospec=True,
        ):
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
            autospec=True,
        ):
            result = check_service_health("Backend", "http://localhost:8000/health")

            assert result["name"] == "Backend"
            assert result["status"] == "unhealthy"
            assert result["error"] is not None
            assert result["data"] is None
            assert isinstance(result["response_time_ms"], int)


class TestFileWatcherWarning:
    """file_watcher_warning() reads GET /api/system/pipeline's file_watcher
    block: watch_mode "polling-fallback" means the backend's native inotify
    watch on the camera root was REFUSED at startup (on an SELinux host,
    EACCES from a usr_t root - the A5500 bug), whatever the compose file."""

    @staticmethod
    def _status(mode: str | None, reason: str | None = None) -> dict:
        return {
            "file_watcher": {
                "running": True,
                "camera_root": "/cameras",
                "pending_tasks": 0,
                "observer_type": "polling",
                "watch_mode": mode,
                "watch_fallback_reason": reason,
            }
        }

    def test_polling_fallback_warns_with_the_reason_and_the_fix(self) -> None:
        from setup_lib.healthcheck import file_watcher_warning

        warning = file_watcher_warning(self._status("polling-fallback", "EACCES"), "/srv/cams")

        assert warning is not None
        assert "polling-fallback" in warning
        assert "EACCES" in warning
        assert ":z" in warning
        assert "sudo semanage fcontext -a -t container_file_t '/srv/cams(/.*)?'" in warning
        assert "sudo restorecon -R /srv/cams" in warning
        assert "fs.inotify.max_user_watches" in warning

    def test_a_missing_reason_still_warns(self) -> None:
        from setup_lib.healthcheck import file_watcher_warning

        warning = file_watcher_warning(self._status("polling-fallback"), "/export/foscam")

        assert warning is not None
        assert "watch_fallback_reason=unknown" in warning

    def test_native_and_configured_polling_are_not_warnings(self) -> None:
        from setup_lib.healthcheck import file_watcher_warning

        assert file_watcher_warning(self._status("native"), "/export/foscam") is None
        assert file_watcher_warning(self._status("polling"), "/export/foscam") is None

    def test_an_unreadable_or_older_status_is_not_a_warning(self) -> None:
        from setup_lib.healthcheck import file_watcher_warning

        assert file_watcher_warning(None, "/export/foscam") is None
        assert file_watcher_warning({}, "/export/foscam") is None
        assert file_watcher_warning({"file_watcher": None}, "/export/foscam") is None
        assert file_watcher_warning(self._status(None), "/export/foscam") is None
