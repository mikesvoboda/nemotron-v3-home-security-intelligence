"""Unit tests for DLQ (dead-letter queue) API routes.

This test module provides comprehensive coverage for backend/api/routes/dlq.py
including all endpoints, authentication, error handling, and edge cases.

Endpoints tested:
- GET /api/dlq/stats - View DLQ statistics
- GET /api/dlq/jobs/{queue_name} - List jobs in a specific DLQ
- POST /api/dlq/requeue/{queue_name} - Requeue single job from DLQ
- POST /api/dlq/requeue-all/{queue_name} - Requeue all jobs from DLQ
- DELETE /api/dlq/{queue_name} - Clear all jobs from a DLQ

Test coverage:
- Happy paths (successful operations)
- API key authentication (enabled and disabled)
- Invalid API keys
- Empty queues
- Pagination
- Query parameter validation
- Error handling (Redis failures)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from backend.api.routes.dlq import DLQName, verify_api_key
from backend.services.retry_handler import DLQStats, JobFailure


class TestVerifyApiKey:
    """Tests for the verify_api_key dependency function."""

    @pytest.mark.asyncio
    async def test_verify_api_key_disabled_auth_allows_all_requests(self, mock_settings):
        """Test that when api_key_enabled is False, all requests pass without validation."""
        mock_settings.api_key_enabled = False

        with patch("backend.api.routes.dlq.get_settings", return_value=mock_settings):
            # Should not raise any exception
            result = await verify_api_key(x_api_key=None, api_key=None)
            assert result is None

    @pytest.mark.asyncio
    async def test_verify_api_key_enabled_requires_key(self, mock_settings):
        """Test that when api_key_enabled is True, missing key raises 401."""
        mock_settings.api_key_enabled = True
        mock_settings.api_keys = ["valid_key"]

        with patch("backend.api.routes.dlq.get_settings", return_value=mock_settings):
            with pytest.raises(Exception) as exc_info:
                await verify_api_key(x_api_key=None, api_key=None)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "API key required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_api_key_valid_header_passes(self, mock_settings):
        """Test that valid API key in header passes authentication."""
        valid_key = "test_api_key_12345"
        mock_settings.api_key_enabled = True
        mock_settings.api_keys = [valid_key]

        with patch("backend.api.routes.dlq.get_settings", return_value=mock_settings):
            result = await verify_api_key(x_api_key=valid_key, api_key=None)
            assert result is None

    @pytest.mark.asyncio
    async def test_verify_api_key_valid_query_param_passes(self, mock_settings):
        """Test that valid API key in query parameter passes authentication."""
        valid_key = "test_api_key_12345"
        mock_settings.api_key_enabled = True
        mock_settings.api_keys = [valid_key]

        with patch("backend.api.routes.dlq.get_settings", return_value=mock_settings):
            result = await verify_api_key(x_api_key=None, api_key=valid_key)
            assert result is None

    @pytest.mark.asyncio
    async def test_verify_api_key_header_preferred_over_query(self, mock_settings):
        """Test that header API key is used when both header and query param provided."""
        valid_key = "header_key"
        invalid_key = "query_key"
        mock_settings.api_key_enabled = True
        mock_settings.api_keys = [valid_key]

        with patch("backend.api.routes.dlq.get_settings", return_value=mock_settings):
            # Header key is valid, should pass
            result = await verify_api_key(x_api_key=valid_key, api_key=invalid_key)
            assert result is None

    @pytest.mark.asyncio
    async def test_verify_api_key_invalid_key_raises_401(self, mock_settings):
        """Test that invalid API key raises 401 Unauthorized."""
        mock_settings.api_key_enabled = True
        mock_settings.api_keys = ["valid_key"]

        with patch("backend.api.routes.dlq.get_settings", return_value=mock_settings):
            with pytest.raises(Exception) as exc_info:
                await verify_api_key(x_api_key="invalid_key", api_key=None)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid API key" in exc_info.value.detail  # pragma: allowlist secret

    @pytest.mark.asyncio
    async def test_verify_api_key_hashing_security(self, mock_settings):
        """Test that API key verification uses secure hashing."""
        valid_key = "secure_key_123"  # pragma: allowlist secret
        mock_settings.api_key_enabled = True
        mock_settings.api_keys = [valid_key]

        with patch("backend.api.routes.dlq.get_settings", return_value=mock_settings):
            # Valid key should work
            await verify_api_key(x_api_key=valid_key, api_key=None)

            # Slightly different key should fail
            with pytest.raises(Exception) as exc_info:
                await verify_api_key(x_api_key="secure_key_124", api_key=None)
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED  # pragma: allowlist secret

    @pytest.mark.asyncio
    async def test_verify_api_key_multiple_valid_keys(self, mock_settings):
        """Test that any of multiple valid keys pass authentication."""
        mock_settings.api_key_enabled = True
        mock_settings.api_keys = ["key1", "key2", "key3"]  # pragma: allowlist secret

        with patch("backend.api.routes.dlq.get_settings", return_value=mock_settings):
            # All valid keys should pass  # pragma: allowlist secret
            await verify_api_key(x_api_key="key1", api_key=None)  # pragma: allowlist secret
            await verify_api_key(x_api_key="key2", api_key=None)  # pragma: allowlist secret
            await verify_api_key(x_api_key="key3", api_key=None)  # pragma: allowlist secret


class TestDLQName:
    """Tests for DLQName enum."""

    def test_dlq_name_enum_values(self):
        """Test that DLQName enum has correct values."""
        assert DLQName.DETECTION.value == "dlq:detection_queue"
        assert DLQName.ANALYSIS.value == "dlq:analysis_queue"

    def test_dlq_name_target_queue_detection(self):
        """Test that DETECTION DLQ maps to correct target queue."""
        assert DLQName.DETECTION.target_queue == "detection_queue"

    def test_dlq_name_target_queue_analysis(self):
        """Test that ANALYSIS DLQ maps to correct target queue."""
        assert DLQName.ANALYSIS.target_queue == "analysis_queue"


class TestGetDLQStats:
    """Tests for GET /api/dlq/stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_dlq_stats_success(self, mock_redis_client):
        """Test successful retrieval of DLQ statistics."""
        from backend.api.routes.dlq import get_dlq_stats

        # Mock the retry handler
        mock_handler = MagicMock()
        mock_handler.get_dlq_stats = AsyncMock(
            return_value=DLQStats(
                detection_queue_count=5,
                analysis_queue_count=3,
                total_count=8,
            )
        )

        with patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler):
            result = await get_dlq_stats(redis=mock_redis_client)

            assert result.detection_queue_count == 5
            assert result.analysis_queue_count == 3
            assert result.total_count == 8
            mock_handler.get_dlq_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_dlq_stats_empty_queues(self, mock_redis_client):
        """Test DLQ stats when queues are empty."""
        from backend.api.routes.dlq import get_dlq_stats

        mock_handler = MagicMock()
        mock_handler.get_dlq_stats = AsyncMock(
            return_value=DLQStats(
                detection_queue_count=0,
                analysis_queue_count=0,
                total_count=0,
            )
        )

        with patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler):
            result = await get_dlq_stats(redis=mock_redis_client)

            assert result.detection_queue_count == 0
            assert result.analysis_queue_count == 0
            assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_get_dlq_stats_large_counts(self, mock_redis_client):
        """Test DLQ stats with large queue counts."""
        from backend.api.routes.dlq import get_dlq_stats

        mock_handler = MagicMock()
        mock_handler.get_dlq_stats = AsyncMock(
            return_value=DLQStats(
                detection_queue_count=10000,
                analysis_queue_count=5000,
                total_count=15000,
            )
        )

        with patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler):
            result = await get_dlq_stats(redis=mock_redis_client)

            assert result.detection_queue_count == 10000
            assert result.analysis_queue_count == 5000
            assert result.total_count == 15000


class TestGetDLQJobs:
    """Tests for GET /api/dlq/jobs/{queue_name} endpoint."""

    @pytest.mark.asyncio
    async def test_get_dlq_jobs_success(self, mock_redis_client):
        """Test successful retrieval of DLQ jobs."""
        from backend.api.routes.dlq import get_dlq_jobs

        # Create mock job failures
        mock_job = JobFailure(
            original_job={"camera_id": "front_door", "file_path": "/test.jpg"},
            error="Connection refused",
            attempt_count=3,
            first_failed_at="2025-01-21T10:00:00",
            last_failed_at="2025-01-21T10:05:00",
            queue_name="detection_queue",
            error_type="ConnectionRefusedError",
            stack_trace="Traceback...",
            http_status=None,
            response_body=None,
            retry_delays=[1.0, 2.0],
            context={"queue_depth": 150},
        )

        mock_handler = MagicMock()
        mock_handler.get_dlq_jobs = AsyncMock(return_value=[mock_job])
        mock_redis_client.get_queue_length = AsyncMock(return_value=1)

        with patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler):
            result = await get_dlq_jobs(
                queue_name=DLQName.DETECTION,
                start=0,
                limit=100,
                redis=mock_redis_client,
            )

            assert result.queue_name == "dlq:detection_queue"
            assert len(result.items) == 1
            # Items are returned as dict objects
            job = result.items[0]
            assert job.original_job["camera_id"] == "front_door"
            assert job.error == "Connection refused"
            assert job.attempt_count == 3
            assert job.error_type == "ConnectionRefusedError"
            assert result.pagination.total == 1
            assert result.pagination.limit == 100
            assert result.pagination.offset == 0

    @pytest.mark.asyncio
    async def test_get_dlq_jobs_empty_queue(self, mock_redis_client):
        """Test retrieving jobs from an empty DLQ."""
        from backend.api.routes.dlq import get_dlq_jobs

        mock_handler = MagicMock()
        mock_handler.get_dlq_jobs = AsyncMock(return_value=[])
        mock_redis_client.get_queue_length = AsyncMock(return_value=0)

        with patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler):
            result = await get_dlq_jobs(
                queue_name=DLQName.ANALYSIS,
                start=0,
                limit=100,
                redis=mock_redis_client,
            )

            assert result.queue_name == "dlq:analysis_queue"
            assert len(result.items) == 0
            assert result.pagination.total == 0

    @pytest.mark.asyncio
    async def test_get_dlq_jobs_with_pagination(self, mock_redis_client):
        """Test DLQ jobs retrieval with custom pagination parameters."""
        from backend.api.routes.dlq import get_dlq_jobs

        # Create 5 mock jobs
        mock_jobs = [
            JobFailure(
                original_job={"camera_id": f"camera_{i}", "file_path": f"/test_{i}.jpg"},
                error=f"Error {i}",
                attempt_count=i + 1,
                first_failed_at=f"2025-01-21T10:0{i}:00",
                last_failed_at=f"2025-01-21T10:0{i}:30",
                queue_name="detection_queue",
            )
            for i in range(5)
        ]

        mock_handler = MagicMock()
        mock_handler.get_dlq_jobs = AsyncMock(return_value=mock_jobs[:2])  # Return first 2
        mock_redis_client.get_queue_length = AsyncMock(return_value=5)

        with patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler):
            result = await get_dlq_jobs(
                queue_name=DLQName.DETECTION,
                start=0,
                limit=2,
                redis=mock_redis_client,
            )

            assert len(result.items) == 2
            assert result.pagination.total == 5
            assert result.pagination.limit == 2
            assert result.pagination.offset == 0
            mock_handler.get_dlq_jobs.assert_called_once_with("dlq:detection_queue", 0, 1)

    @pytest.mark.asyncio
    async def test_get_dlq_jobs_with_offset(self, mock_redis_client):
        """Test DLQ jobs retrieval with offset pagination."""
        from backend.api.routes.dlq import get_dlq_jobs

        mock_job = JobFailure(
            original_job={"camera_id": "test"},
            error="Test error",
            attempt_count=1,
            first_failed_at="2025-01-21T10:00:00",
            last_failed_at="2025-01-21T10:00:00",
            queue_name="analysis_queue",
        )

        mock_handler = MagicMock()
        mock_handler.get_dlq_jobs = AsyncMock(return_value=[mock_job])
        mock_redis_client.get_queue_length = AsyncMock(return_value=100)

        with patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler):
            result = await get_dlq_jobs(
                queue_name=DLQName.ANALYSIS,
                start=50,
                limit=10,
                redis=mock_redis_client,
            )

            assert result.pagination.offset == 50
            assert result.pagination.limit == 10
            mock_handler.get_dlq_jobs.assert_called_once_with("dlq:analysis_queue", 50, 59)

    @pytest.mark.asyncio
    async def test_get_dlq_jobs_max_limit(self, mock_redis_client):
        """Test DLQ jobs retrieval respects maximum limit of 1000."""
        from backend.api.routes.dlq import get_dlq_jobs

        mock_handler = MagicMock()
        mock_handler.get_dlq_jobs = AsyncMock(return_value=[])
        mock_redis_client.get_queue_length = AsyncMock(return_value=0)

        with patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler):
            # Limit is constrained to 1000 by FastAPI validation
            result = await get_dlq_jobs(
                queue_name=DLQName.DETECTION,
                start=0,
                limit=1000,
                redis=mock_redis_client,
            )

            assert result.pagination.limit == 1000
            mock_handler.get_dlq_jobs.assert_called_once_with("dlq:detection_queue", 0, 999)

    @pytest.mark.asyncio
    async def test_get_dlq_jobs_enriched_error_context(self, mock_redis_client):
        """Test that DLQ jobs include enriched error context (NEM-1474)."""
        from backend.api.routes.dlq import get_dlq_jobs

        mock_job = JobFailure(
            original_job={"camera_id": "front_door"},
            error="HTTP 500 Internal Server Error",
            attempt_count=3,
            first_failed_at="2025-01-21T10:00:00",
            last_failed_at="2025-01-21T10:05:00",
            queue_name="analysis_queue",
            error_type="HTTPStatusError",
            stack_trace="Traceback (most recent call last):\n  File...",
            http_status=500,
            response_body='{"error": "Internal error"}',
            retry_delays=[1.0, 2.0, 4.0],
            context={"analysis_queue_depth": 25, "circuit_breaker": "closed"},
        )

        mock_handler = MagicMock()
        mock_handler.get_dlq_jobs = AsyncMock(return_value=[mock_job])
        mock_redis_client.get_queue_length = AsyncMock(return_value=1)

        with patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler):
            result = await get_dlq_jobs(
                queue_name=DLQName.ANALYSIS,
                start=0,
                limit=100,
                redis=mock_redis_client,
            )

            job = result.items[0]
            assert job.error_type == "HTTPStatusError"
            assert "Traceback" in job.stack_trace
            assert job.http_status == 500
            assert job.response_body == '{"error": "Internal error"}'
            assert job.retry_delays == [1.0, 2.0, 4.0]
            assert job.context["circuit_breaker"] == "closed"


class TestRequeueDLQJob:
    """Tests for POST /api/dlq/requeue/{queue_name} endpoint."""

    @pytest.mark.asyncio
    async def test_requeue_dlq_job_success(self, mock_redis_client, mock_settings):
        """Test successful requeue of a single job from DLQ."""
        from backend.api.routes.dlq import requeue_dlq_job

        mock_settings.api_key_enabled = False

        mock_handler = MagicMock()
        mock_handler.move_dlq_job_to_queue = AsyncMock(return_value=True)

        with (
            patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler),
            patch("backend.api.routes.dlq.get_settings", return_value=mock_settings),
        ):
            result = await requeue_dlq_job(
                queue_name=DLQName.DETECTION,
                redis=mock_redis_client,
                _auth=None,
            )

            assert result.success is True
            assert "requeued" in result.message.lower()
            assert "detection_queue" in result.message
            mock_handler.move_dlq_job_to_queue.assert_called_once_with(
                "dlq:detection_queue", "detection_queue"
            )

    @pytest.mark.asyncio
    async def test_requeue_dlq_job_empty_queue(self, mock_redis_client, mock_settings):
        """Test requeue from empty DLQ returns appropriate message."""
        from backend.api.routes.dlq import requeue_dlq_job

        mock_settings.api_key_enabled = False

        mock_handler = MagicMock()
        mock_handler.move_dlq_job_to_queue = AsyncMock(return_value=False)

        with (
            patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler),
            patch("backend.api.routes.dlq.get_settings", return_value=mock_settings),
        ):
            result = await requeue_dlq_job(
                queue_name=DLQName.ANALYSIS,
                redis=mock_redis_client,
                _auth=None,
            )

            assert result.success is False
            assert "no jobs to requeue" in result.message.lower()
            assert result.job is None

    @pytest.mark.asyncio
    async def test_requeue_dlq_job_requires_auth_when_enabled(
        self, mock_redis_client, mock_settings
    ):
        """Test that requeue requires API key when authentication is enabled."""
        from backend.api.routes.dlq import verify_api_key

        mock_settings.api_key_enabled = True
        mock_settings.api_keys = ["valid_key"]

        # Test with no API key - should raise 401
        with patch("backend.api.routes.dlq.get_settings", return_value=mock_settings):
            with pytest.raises(Exception) as exc_info:
                # Manually call verify_api_key to test auth requirement
                await verify_api_key(x_api_key=None, api_key=None)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_requeue_dlq_job_analysis_queue(self, mock_redis_client, mock_settings):
        """Test requeue from analysis DLQ to analysis queue."""
        from backend.api.routes.dlq import requeue_dlq_job

        mock_settings.api_key_enabled = False

        mock_handler = MagicMock()
        mock_handler.move_dlq_job_to_queue = AsyncMock(return_value=True)

        with (
            patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler),
            patch("backend.api.routes.dlq.get_settings", return_value=mock_settings),
        ):
            result = await requeue_dlq_job(
                queue_name=DLQName.ANALYSIS,
                redis=mock_redis_client,
                _auth=None,
            )

            assert result.success is True
            assert "analysis_queue" in result.message
            mock_handler.move_dlq_job_to_queue.assert_called_once_with(
                "dlq:analysis_queue", "analysis_queue"
            )


class TestRequeueAllDLQJobs:
    """Tests for POST /api/dlq/requeue-all/{queue_name} endpoint."""

    @pytest.mark.asyncio
    async def test_requeue_all_dlq_jobs_success(self, mock_redis_client, mock_settings):
        """Test successful requeue of all jobs from DLQ."""
        from backend.api.routes.dlq import requeue_all_dlq_jobs

        mock_settings.api_key_enabled = False
        mock_settings.max_requeue_iterations = 10000

        # Mock queue has 5 jobs
        mock_redis_client.get_queue_length = AsyncMock(return_value=5)

        mock_handler = MagicMock()
        # Return True 5 times, then False
        mock_handler.move_dlq_job_to_queue = AsyncMock(
            side_effect=[True, True, True, True, True, False]
        )

        with (
            patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler),
            patch("backend.api.routes.dlq.get_settings", return_value=mock_settings),
        ):
            result = await requeue_all_dlq_jobs(
                queue_name=DLQName.DETECTION,
                redis=mock_redis_client,
                _auth=None,
            )

            assert result.success is True
            assert "5 jobs" in result.message
            assert "detection_queue" in result.message
            assert mock_handler.move_dlq_job_to_queue.call_count == 6  # 5 successful + 1 empty

    @pytest.mark.asyncio
    async def test_requeue_all_dlq_jobs_empty_queue(self, mock_redis_client, mock_settings):
        """Test requeue-all from empty DLQ returns early."""
        from backend.api.routes.dlq import requeue_all_dlq_jobs

        mock_settings.api_key_enabled = False
        mock_settings.max_requeue_iterations = 10000

        # Queue is empty
        mock_redis_client.get_queue_length = AsyncMock(return_value=0)

        mock_handler = MagicMock()
        mock_handler.move_dlq_job_to_queue = AsyncMock()

        with (
            patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler),
            patch("backend.api.routes.dlq.get_settings", return_value=mock_settings),
        ):
            result = await requeue_all_dlq_jobs(
                queue_name=DLQName.ANALYSIS,
                redis=mock_redis_client,
                _auth=None,
            )

            assert result.success is False
            assert "no jobs to requeue" in result.message.lower()
            # Should not attempt any moves
            mock_handler.move_dlq_job_to_queue.assert_not_called()

    @pytest.mark.asyncio
    async def test_requeue_all_dlq_jobs_hits_limit(self, mock_redis_client, mock_settings):
        """Test requeue-all stops at max_requeue_iterations limit."""
        from backend.api.routes.dlq import requeue_all_dlq_jobs

        mock_settings.api_key_enabled = False
        mock_settings.max_requeue_iterations = 100

        # Queue has more than 100 jobs
        mock_redis_client.get_queue_length = AsyncMock(return_value=150)

        mock_handler = MagicMock()
        # Always return True (queue never empties)
        mock_handler.move_dlq_job_to_queue = AsyncMock(return_value=True)

        with (
            patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler),
            patch("backend.api.routes.dlq.get_settings", return_value=mock_settings),
        ):
            result = await requeue_all_dlq_jobs(
                queue_name=DLQName.DETECTION,
                redis=mock_redis_client,
                _auth=None,
            )

            assert result.success is True
            assert "100 jobs" in result.message
            assert "hit limit of 100" in result.message
            assert mock_handler.move_dlq_job_to_queue.call_count == 100

    @pytest.mark.asyncio
    async def test_requeue_all_dlq_jobs_partial_success(self, mock_redis_client, mock_settings):
        """Test requeue-all with partial success (some jobs fail)."""
        from backend.api.routes.dlq import requeue_all_dlq_jobs

        mock_settings.api_key_enabled = False
        mock_settings.max_requeue_iterations = 10000

        # Queue has 3 jobs
        mock_redis_client.get_queue_length = AsyncMock(return_value=3)

        mock_handler = MagicMock()
        # First 2 succeed, then queue empties
        mock_handler.move_dlq_job_to_queue = AsyncMock(side_effect=[True, True, False])

        with (
            patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler),
            patch("backend.api.routes.dlq.get_settings", return_value=mock_settings),
        ):
            result = await requeue_all_dlq_jobs(
                queue_name=DLQName.DETECTION,
                redis=mock_redis_client,
                _auth=None,
            )

            assert result.success is True
            assert "2 jobs" in result.message

    @pytest.mark.asyncio
    async def test_requeue_all_dlq_jobs_requires_auth(self, mock_redis_client, mock_settings):
        """Test that requeue-all requires API key when authentication is enabled."""
        from backend.api.routes.dlq import verify_api_key

        mock_settings.api_key_enabled = True
        mock_settings.api_keys = ["valid_key"]

        # Test auth requirement
        with patch("backend.api.routes.dlq.get_settings", return_value=mock_settings):
            with pytest.raises(Exception) as exc_info:
                await verify_api_key(x_api_key=None, api_key=None)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


class TestClearDLQ:
    """Tests for DELETE /api/dlq/{queue_name} endpoint."""

    @pytest.mark.asyncio
    async def test_clear_dlq_success(self, mock_redis_client, mock_settings):
        """Test successful clearing of DLQ."""
        from backend.api.routes.dlq import clear_dlq

        mock_settings.api_key_enabled = False

        # Queue has 5 jobs
        mock_redis_client.get_queue_length = AsyncMock(return_value=5)

        mock_handler = MagicMock()
        mock_handler.clear_dlq = AsyncMock(return_value=True)

        with (
            patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler),
            patch("backend.api.routes.dlq.get_settings", return_value=mock_settings),
        ):
            result = await clear_dlq(
                queue_name=DLQName.DETECTION,
                redis=mock_redis_client,
                _auth=None,
            )

            assert result.success is True
            assert "cleared 5 jobs" in result.message.lower()
            assert result.queue_name == "dlq:detection_queue"
            mock_handler.clear_dlq.assert_called_once_with("dlq:detection_queue")

    @pytest.mark.asyncio
    async def test_clear_dlq_empty_queue(self, mock_redis_client, mock_settings):
        """Test clearing an empty DLQ."""
        from backend.api.routes.dlq import clear_dlq

        mock_settings.api_key_enabled = False

        # Queue is empty
        mock_redis_client.get_queue_length = AsyncMock(return_value=0)

        mock_handler = MagicMock()
        mock_handler.clear_dlq = AsyncMock(return_value=True)

        with (
            patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler),
            patch("backend.api.routes.dlq.get_settings", return_value=mock_settings),
        ):
            result = await clear_dlq(
                queue_name=DLQName.ANALYSIS,
                redis=mock_redis_client,
                _auth=None,
            )

            assert result.success is True
            assert "cleared 0 jobs" in result.message.lower()

    @pytest.mark.asyncio
    async def test_clear_dlq_failure(self, mock_redis_client, mock_settings):
        """Test clear DLQ when operation fails."""
        from backend.api.routes.dlq import clear_dlq

        mock_settings.api_key_enabled = False

        mock_redis_client.get_queue_length = AsyncMock(return_value=10)

        mock_handler = MagicMock()
        mock_handler.clear_dlq = AsyncMock(return_value=False)

        with (
            patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler),
            patch("backend.api.routes.dlq.get_settings", return_value=mock_settings),
        ):
            result = await clear_dlq(
                queue_name=DLQName.DETECTION,
                redis=mock_redis_client,
                _auth=None,
            )

            assert result.success is False
            assert "failed to clear" in result.message.lower()

    @pytest.mark.asyncio
    async def test_clear_dlq_requires_auth(self, mock_redis_client, mock_settings):
        """Test that clear DLQ requires API key when authentication is enabled."""
        from backend.api.routes.dlq import verify_api_key

        mock_settings.api_key_enabled = True
        mock_settings.api_keys = ["valid_key"]

        # Test auth requirement
        with patch("backend.api.routes.dlq.get_settings", return_value=mock_settings):
            with pytest.raises(Exception) as exc_info:
                await verify_api_key(x_api_key=None, api_key=None)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_clear_dlq_large_queue(self, mock_redis_client, mock_settings):
        """Test clearing a DLQ with large number of jobs."""
        from backend.api.routes.dlq import clear_dlq

        mock_settings.api_key_enabled = False

        # Queue has 10000 jobs
        mock_redis_client.get_queue_length = AsyncMock(return_value=10000)

        mock_handler = MagicMock()
        mock_handler.clear_dlq = AsyncMock(return_value=True)

        with (
            patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler),
            patch("backend.api.routes.dlq.get_settings", return_value=mock_settings),
        ):
            result = await clear_dlq(
                queue_name=DLQName.DETECTION,
                redis=mock_redis_client,
                _auth=None,
            )

            assert result.success is True
            assert "10000" in result.message


class TestEdgeCasesAndErrorHandling:
    """Tests for edge cases and error handling across all endpoints."""

    @pytest.mark.asyncio
    async def test_get_dlq_jobs_limit_boundary_values(self, mock_redis_client):
        """Test DLQ jobs with boundary limit values (1 and 1000)."""
        from backend.api.routes.dlq import get_dlq_jobs

        mock_handler = MagicMock()
        mock_handler.get_dlq_jobs = AsyncMock(return_value=[])
        mock_redis_client.get_queue_length = AsyncMock(return_value=0)

        with patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler):
            # Test minimum limit (1)
            result = await get_dlq_jobs(
                queue_name=DLQName.DETECTION,
                start=0,
                limit=1,
                redis=mock_redis_client,
            )
            assert result.pagination.limit == 1

            # Test maximum limit (1000)
            result = await get_dlq_jobs(
                queue_name=DLQName.DETECTION,
                start=0,
                limit=1000,
                redis=mock_redis_client,
            )
            assert result.pagination.limit == 1000

    @pytest.mark.asyncio
    async def test_verify_api_key_with_whitespace(self, mock_settings):
        """Test API key validation handles whitespace correctly."""
        from backend.api.routes.dlq import verify_api_key

        valid_key = "test_key_123"
        mock_settings.api_key_enabled = True
        mock_settings.api_keys = [valid_key]

        with patch("backend.api.routes.dlq.get_settings", return_value=mock_settings):
            # Key with whitespace should fail (exact match required)
            with pytest.raises(Exception) as exc_info:
                await verify_api_key(x_api_key=" test_key_123 ", api_key=None)
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_dlq_operations_with_none_error_context(self, mock_redis_client):
        """Test DLQ operations handle jobs with None error context fields."""
        from backend.api.routes.dlq import get_dlq_jobs

        # Job with minimal fields (no enriched error context)
        mock_job = JobFailure(
            original_job={"camera_id": "test"},
            error="Simple error",
            attempt_count=1,
            first_failed_at="2025-01-21T10:00:00",
            last_failed_at="2025-01-21T10:00:00",
            queue_name="detection_queue",
            error_type=None,
            stack_trace=None,
            http_status=None,
            response_body=None,
            retry_delays=None,
            context=None,
        )

        mock_handler = MagicMock()
        mock_handler.get_dlq_jobs = AsyncMock(return_value=[mock_job])
        mock_redis_client.get_queue_length = AsyncMock(return_value=1)

        with patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler):
            result = await get_dlq_jobs(
                queue_name=DLQName.DETECTION,
                start=0,
                limit=100,
                redis=mock_redis_client,
            )

            job = result.items[0]
            assert job.error_type is None
            assert job.stack_trace is None
            assert job.http_status is None
            assert job.response_body is None
            assert job.retry_delays is None
            assert job.context is None

    @pytest.mark.asyncio
    async def test_requeue_operations_with_special_characters_in_job_data(
        self, mock_redis_client, mock_settings
    ):
        """Test requeue operations handle special characters in job data."""
        from backend.api.routes.dlq import requeue_dlq_job

        mock_settings.api_key_enabled = False

        mock_handler = MagicMock()
        mock_handler.move_dlq_job_to_queue = AsyncMock(return_value=True)

        with (
            patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler),
            patch("backend.api.routes.dlq.get_settings", return_value=mock_settings),
        ):
            result = await requeue_dlq_job(
                queue_name=DLQName.DETECTION,
                redis=mock_redis_client,
                _auth=None,
            )

            # Should succeed regardless of job content
            assert result.success is True

    @pytest.mark.asyncio
    async def test_clear_dlq_analysis_queue(self, mock_redis_client, mock_settings):
        """Test clearing analysis DLQ specifically."""
        from backend.api.routes.dlq import clear_dlq

        mock_settings.api_key_enabled = False

        mock_redis_client.get_queue_length = AsyncMock(return_value=3)

        mock_handler = MagicMock()
        mock_handler.clear_dlq = AsyncMock(return_value=True)

        with (
            patch("backend.api.routes.dlq.get_retry_handler", return_value=mock_handler),
            patch("backend.api.routes.dlq.get_settings", return_value=mock_settings),
        ):
            result = await clear_dlq(
                queue_name=DLQName.ANALYSIS,
                redis=mock_redis_client,
                _auth=None,
            )

            assert result.success is True
            assert result.queue_name == "dlq:analysis_queue"
            mock_handler.clear_dlq.assert_called_once_with("dlq:analysis_queue")
