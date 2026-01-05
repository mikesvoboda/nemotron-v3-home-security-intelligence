"""Unit tests for Linear migration script retry logic (NEM-1087).

Tests cover:
- Retry logic with exponential backoff for API calls
- Respecting Retry-After header from rate limiting
- Configuration for max retries
- Logging of retry attempts
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

# Import the module under test
# Note: The migration script is standalone, so we'll test the retry logic patterns
# that should be implemented


class TestLinearClientRetryLogic:
    """Tests for LinearClient retry logic."""

    def test_successful_request_no_retry(self) -> None:
        """Test that successful requests don't trigger retries."""
        from scripts.migrate_beads_to_linear import LinearClient

        with patch.object(httpx.Client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"team": {"labels": {"nodes": []}}}}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            client = LinearClient("test_api_key")
            result = client.get_labels("test_team_id")

            # Should only call once
            assert mock_post.call_count == 1
            assert result == {}

    def test_retry_on_connection_error(self) -> None:
        """Test that connection errors trigger retry."""
        from scripts.migrate_beads_to_linear import LinearClient

        with patch.object(httpx.Client, "post") as mock_post:
            # First call fails, second succeeds
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"team": {"labels": {"nodes": []}}}}
            mock_response.raise_for_status = MagicMock()

            mock_post.side_effect = [
                httpx.ConnectError("Connection failed"),
                mock_response,
            ]

            client = LinearClient("test_api_key")
            result = client.get_labels("test_team_id")

            # Should have retried
            assert mock_post.call_count == 2
            assert result == {}

    def test_retry_on_rate_limit_429(self) -> None:
        """Test that 429 rate limit responses trigger retry."""
        from scripts.migrate_beads_to_linear import LinearClient

        with patch.object(httpx.Client, "post") as mock_post:
            # First call returns 429, second succeeds
            mock_429_response = MagicMock()
            mock_429_response.status_code = 429
            mock_429_response.headers = {"Retry-After": "1"}
            mock_429_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Too Many Requests",
                request=MagicMock(),
                response=mock_429_response,
            )

            mock_ok_response = MagicMock()
            mock_ok_response.status_code = 200
            mock_ok_response.json.return_value = {"data": {"team": {"labels": {"nodes": []}}}}
            mock_ok_response.raise_for_status = MagicMock()

            mock_post.side_effect = [mock_429_response, mock_ok_response]

            client = LinearClient("test_api_key")
            result = client.get_labels("test_team_id")

            # Should have retried after 429
            assert mock_post.call_count == 2
            assert result == {}

    def test_retry_respects_retry_after_header(self) -> None:
        """Test that retry respects Retry-After header from rate limit response."""
        from scripts.migrate_beads_to_linear import LinearClient

        with (
            patch.object(httpx.Client, "post") as mock_post,
            patch("time.sleep") as mock_sleep,
        ):
            # First call returns 429 with Retry-After
            mock_429_response = MagicMock()
            mock_429_response.status_code = 429
            mock_429_response.headers = {"Retry-After": "3"}
            mock_429_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Too Many Requests",
                request=MagicMock(),
                response=mock_429_response,
            )

            mock_ok_response = MagicMock()
            mock_ok_response.status_code = 200
            mock_ok_response.json.return_value = {"data": {"team": {"labels": {"nodes": []}}}}
            mock_ok_response.raise_for_status = MagicMock()

            mock_post.side_effect = [mock_429_response, mock_ok_response]

            client = LinearClient("test_api_key")
            client.get_labels("test_team_id")

            # Should have slept for the Retry-After duration
            mock_sleep.assert_called()
            # The sleep should be at least the Retry-After value
            sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert any(s >= 3 for s in sleep_calls)

    def test_retry_exhausted_raises_error(self) -> None:
        """Test that error is raised when all retries are exhausted."""
        from scripts.migrate_beads_to_linear import LinearClient

        with patch.object(httpx.Client, "post") as mock_post:
            # All calls fail
            mock_post.side_effect = httpx.ConnectError("Persistent failure")

            client = LinearClient("test_api_key")

            with pytest.raises(httpx.ConnectError):
                client.get_labels("test_team_id")

            # Should have tried max_retries times (default 3)
            assert mock_post.call_count == 3

    def test_exponential_backoff_timing(self) -> None:
        """Test that retry uses exponential backoff."""
        from scripts.migrate_beads_to_linear import LinearClient

        call_times: list[float] = []

        def tracking_post(*args, **kwargs):
            call_times.append(time.monotonic())
            raise httpx.ConnectError("Connection failed")

        with (
            patch.object(httpx.Client, "post", side_effect=tracking_post),
            patch("time.sleep") as mock_sleep,
        ):
            mock_sleep.side_effect = lambda _: None  # Don't actually sleep

            client = LinearClient("test_api_key")

            try:
                client.get_labels("test_team_id")
            except httpx.ConnectError:
                pass  # Expected - all retries exhausted

            # Check that sleep was called with increasing delays
            sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
            # Should be exponential: 1, 2, 4... or similar
            if len(sleep_calls) >= 2:
                assert sleep_calls[1] >= sleep_calls[0]

    def test_no_retry_on_graphql_error(self) -> None:
        """Test that GraphQL errors are not retried (they're application errors)."""
        from scripts.migrate_beads_to_linear import LinearClient

        with patch.object(httpx.Client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"errors": [{"message": "Invalid query"}]}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            client = LinearClient("test_api_key")

            # Using match parameter to avoid S110 lint error
            with pytest.raises(Exception, match="GraphQL errors"):
                client.get_labels("test_team_id")

            # Should only call once - GraphQL errors are not retryable
            assert mock_post.call_count == 1

    def test_retry_on_server_error_500(self) -> None:
        """Test that 500 server errors trigger retry."""
        from scripts.migrate_beads_to_linear import LinearClient

        with patch.object(httpx.Client, "post") as mock_post:
            # First call returns 500, second succeeds
            mock_500_response = MagicMock()
            mock_500_response.status_code = 500
            mock_500_response.headers = {}
            mock_500_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=mock_500_response,
            )

            mock_ok_response = MagicMock()
            mock_ok_response.status_code = 200
            mock_ok_response.json.return_value = {"data": {"team": {"labels": {"nodes": []}}}}
            mock_ok_response.raise_for_status = MagicMock()

            mock_post.side_effect = [mock_500_response, mock_ok_response]

            client = LinearClient("test_api_key")
            result = client.get_labels("test_team_id")

            # Should have retried after 500
            assert mock_post.call_count == 2
            assert result == {}


class TestLinearClientRetryConfiguration:
    """Tests for retry configuration in LinearClient."""

    def test_default_max_retries(self) -> None:
        """Test that default max retries is 3."""
        from scripts.migrate_beads_to_linear import LinearClient

        client = LinearClient("test_api_key")
        assert hasattr(client, "max_retries")
        assert client.max_retries == 3

    def test_custom_max_retries(self) -> None:
        """Test that max_retries can be customized."""
        from scripts.migrate_beads_to_linear import LinearClient

        client = LinearClient("test_api_key", max_retries=5)
        assert client.max_retries == 5

    def test_default_base_delay(self) -> None:
        """Test that default base delay is 1 second."""
        from scripts.migrate_beads_to_linear import LinearClient

        client = LinearClient("test_api_key")
        assert hasattr(client, "retry_base_delay")
        assert client.retry_base_delay == 1.0


class TestLinearClientRetryLogging:
    """Tests for retry logging behavior."""

    def test_retry_logs_warning(self) -> None:
        """Test that retry attempts are logged."""
        from scripts.migrate_beads_to_linear import LinearClient

        with (
            patch.object(httpx.Client, "post") as mock_post,
            patch("builtins.print") as mock_print,
        ):
            # First call fails, second succeeds
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"team": {"labels": {"nodes": []}}}}
            mock_response.raise_for_status = MagicMock()

            mock_post.side_effect = [
                httpx.ConnectError("Connection failed"),
                mock_response,
            ]

            client = LinearClient("test_api_key")
            client.get_labels("test_team_id")

            # Should have printed a retry message
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any("retry" in call.lower() for call in print_calls)
