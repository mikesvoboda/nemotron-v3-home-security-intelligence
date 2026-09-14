"""Unit tests for JobLogEmitter service (backend/services/job_log_emitter.py).

Tests cover:
- Log emission to Redis pub/sub
- Job lifecycle events (started, progress, completed, failed)
- Redis unavailability handling
- Singleton pattern and initialization
- Channel name generation
"""

from __future__ import annotations

import json
import os
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

# Set DATABASE_URL for tests before importing any backend modules
_TEST_DB_URL = "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret
os.environ.setdefault("DATABASE_URL", _TEST_DB_URL)

from backend.services.job_log_emitter import (  # noqa: E402
    JobLogEmitter,
    get_job_log_emitter,
    reset_emitter_state,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the singleton state before and after each test."""
    reset_emitter_state()
    yield
    reset_emitter_state()


@pytest.fixture
def mock_redis_client() -> MagicMock:
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.publish = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def emitter(mock_redis_client: MagicMock) -> JobLogEmitter:
    """Create a JobLogEmitter with a mock Redis client."""
    return JobLogEmitter(redis_client=mock_redis_client)


@pytest.fixture
def sample_job_id() -> str:
    """Sample job ID for tests."""
    return str(uuid.uuid4())


# =============================================================================
# Tests for JobLogEmitter
# =============================================================================


class TestJobLogEmitter:
    """Tests for JobLogEmitter class."""

    def test_init_with_redis_client(self, mock_redis_client: MagicMock) -> None:
        """Should initialize with Redis client."""
        emitter = JobLogEmitter(redis_client=mock_redis_client)

        assert emitter._redis_client is mock_redis_client
        assert emitter.emit_count == 0
        assert emitter.emit_errors == 0

    def test_init_without_redis_client(self) -> None:
        """Should initialize without Redis client."""
        emitter = JobLogEmitter()

        assert emitter._redis_client is None

    def test_set_redis_client(self, mock_redis_client: MagicMock) -> None:
        """Should allow setting Redis client after initialization."""
        emitter = JobLogEmitter()
        emitter.set_redis_client(mock_redis_client)

        assert emitter._redis_client is mock_redis_client

    def test_get_channel_name_with_string(self, emitter: JobLogEmitter) -> None:
        """Should generate correct channel name from string job ID."""
        job_id = "abc123"
        channel = emitter._get_channel_name(job_id)

        assert channel == "job:abc123:logs"

    def test_get_channel_name_with_uuid(self, emitter: JobLogEmitter) -> None:
        """Should generate correct channel name from UUID."""
        job_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        channel = emitter._get_channel_name(job_id)

        assert channel == "job:550e8400-e29b-41d4-a716-446655440000:logs"


class TestEmitLog:
    """Tests for emit_log method."""

    @pytest.mark.asyncio
    async def test_emit_log_publishes_to_redis(
        self,
        emitter: JobLogEmitter,
        mock_redis_client: MagicMock,
        sample_job_id: str,
    ) -> None:
        """Should publish log message to Redis channel."""
        result = await emitter.emit_log(
            job_id=sample_job_id,
            level="INFO",
            message="Test message",
            context={"key": "value"},
        )

        assert result is True
        mock_redis_client.publish.assert_called_once()

        # Verify channel name
        call_args = mock_redis_client.publish.call_args
        channel = call_args[0][0]
        assert channel == f"job:{sample_job_id}:logs"

        # Verify message structure
        message = call_args[0][1]
        parsed = json.loads(message)
        assert parsed["type"] == "log"
        assert parsed["data"]["level"] == "INFO"
        assert parsed["data"]["message"] == "Test message"
        assert parsed["data"]["context"] == {"key": "value"}
        assert "timestamp" in parsed["data"]

    @pytest.mark.asyncio
    async def test_emit_log_increments_count(
        self,
        emitter: JobLogEmitter,
        sample_job_id: str,
    ) -> None:
        """Should increment emit count on success."""
        await emitter.emit_log(sample_job_id, "INFO", "Test")
        await emitter.emit_log(sample_job_id, "INFO", "Test 2")

        assert emitter.emit_count == 2
        assert emitter.emit_errors == 0

    @pytest.mark.asyncio
    async def test_emit_log_without_redis_returns_false(
        self,
        sample_job_id: str,
    ) -> None:
        """Should return False when Redis client is not available."""
        emitter = JobLogEmitter()  # No Redis client

        result = await emitter.emit_log(sample_job_id, "INFO", "Test")

        assert result is False

    @pytest.mark.asyncio
    async def test_emit_log_handles_redis_error(
        self,
        emitter: JobLogEmitter,
        mock_redis_client: MagicMock,
        sample_job_id: str,
    ) -> None:
        """Should handle Redis publish errors gracefully."""
        mock_redis_client.publish = AsyncMock(side_effect=Exception("Redis error"))

        result = await emitter.emit_log(sample_job_id, "INFO", "Test")

        assert result is False
        assert emitter.emit_errors == 1

    @pytest.mark.asyncio
    async def test_emit_log_normalizes_level_to_uppercase(
        self,
        emitter: JobLogEmitter,
        mock_redis_client: MagicMock,
        sample_job_id: str,
    ) -> None:
        """Should normalize log level to uppercase."""
        await emitter.emit_log(sample_job_id, "info", "Test")

        call_args = mock_redis_client.publish.call_args
        message = json.loads(call_args[0][1])
        assert message["data"]["level"] == "INFO"


class TestJobLifecycleEvents:
    """Tests for job lifecycle event methods."""

    @pytest.mark.asyncio
    async def test_emit_job_started(
        self,
        emitter: JobLogEmitter,
        mock_redis_client: MagicMock,
        sample_job_id: str,
    ) -> None:
        """Should emit job started event."""
        result = await emitter.emit_job_started(
            job_id=sample_job_id,
            job_type="export",
            metadata={"format": "csv"},
        )

        assert result is True
        call_args = mock_redis_client.publish.call_args
        message = json.loads(call_args[0][1])
        assert "Job started: export" in message["data"]["message"]
        assert message["data"]["context"]["job_type"] == "export"

    @pytest.mark.asyncio
    async def test_emit_job_progress(
        self,
        emitter: JobLogEmitter,
        mock_redis_client: MagicMock,
        sample_job_id: str,
    ) -> None:
        """Should emit job progress event."""
        result = await emitter.emit_job_progress(
            job_id=sample_job_id,
            progress_percent=50,
            current_step="Processing",
            items_processed=500,
            items_total=1000,
        )

        assert result is True
        call_args = mock_redis_client.publish.call_args
        message = json.loads(call_args[0][1])
        assert "Processing: 50%" in message["data"]["message"]
        assert message["data"]["context"]["progress_percent"] == 50
        assert message["data"]["context"]["items_processed"] == 500
        assert message["data"]["context"]["items_total"] == 1000

    @pytest.mark.asyncio
    async def test_emit_job_progress_without_step(
        self,
        emitter: JobLogEmitter,
        mock_redis_client: MagicMock,
        sample_job_id: str,
    ) -> None:
        """Should emit progress without step description."""
        result = await emitter.emit_job_progress(
            job_id=sample_job_id,
            progress_percent=75,
        )

        assert result is True
        call_args = mock_redis_client.publish.call_args
        message = json.loads(call_args[0][1])
        assert "Progress: 75%" in message["data"]["message"]

    @pytest.mark.asyncio
    async def test_emit_job_completed(
        self,
        emitter: JobLogEmitter,
        mock_redis_client: MagicMock,
        sample_job_id: str,
    ) -> None:
        """Should emit job completed event."""
        result = await emitter.emit_job_completed(
            job_id=sample_job_id,
            result={"items_exported": 1000},
            duration_seconds=45.5,
        )

        assert result is True
        call_args = mock_redis_client.publish.call_args
        message = json.loads(call_args[0][1])
        assert "completed successfully" in message["data"]["message"]
        assert "45.5s" in message["data"]["message"]
        assert message["data"]["context"]["status"] == "completed"
        assert message["data"]["context"]["result"]["items_exported"] == 1000

    @pytest.mark.asyncio
    async def test_emit_job_failed(
        self,
        emitter: JobLogEmitter,
        mock_redis_client: MagicMock,
        sample_job_id: str,
    ) -> None:
        """Should emit job failed event."""
        result = await emitter.emit_job_failed(
            job_id=sample_job_id,
            error="Database connection failed",
            error_code="DB_ERROR",
            retryable=True,
        )

        assert result is True
        call_args = mock_redis_client.publish.call_args
        message = json.loads(call_args[0][1])
        assert message["data"]["level"] == "ERROR"
        assert "Job failed: Database connection failed" in message["data"]["message"]
        assert message["data"]["context"]["status"] == "failed"
        assert message["data"]["context"]["error_code"] == "DB_ERROR"
        assert message["data"]["context"]["retryable"] is True


class TestGetStats:
    """Tests for get_stats method."""

    @pytest.mark.asyncio
    async def test_get_stats_returns_correct_data(
        self,
        emitter: JobLogEmitter,
        sample_job_id: str,
    ) -> None:
        """Should return correct statistics."""
        # Emit some logs
        await emitter.emit_log(sample_job_id, "INFO", "Test 1")
        await emitter.emit_log(sample_job_id, "INFO", "Test 2")

        stats = emitter.get_stats()

        assert stats["emit_count"] == 2
        assert stats["emit_errors"] == 0
        assert stats["redis_client_available"] is True


# =============================================================================
# Tests for Singleton Pattern
# =============================================================================


class TestJobLogEmitterSingleton:
    """Tests for the singleton pattern."""

    @pytest.mark.asyncio
    async def test_get_job_log_emitter_creates_singleton(
        self,
        mock_redis_client: MagicMock,
    ) -> None:
        """Should create singleton instance."""
        emitter1 = await get_job_log_emitter(mock_redis_client)
        emitter2 = await get_job_log_emitter()

        assert emitter1 is emitter2

    @pytest.mark.asyncio
    async def test_get_job_log_emitter_updates_redis_client(
        self,
        mock_redis_client: MagicMock,
    ) -> None:
        """Should update Redis client on existing singleton."""
        emitter1 = await get_job_log_emitter()
        assert emitter1._redis_client is None

        emitter2 = await get_job_log_emitter(mock_redis_client)
        assert emitter2._redis_client is mock_redis_client
        assert emitter1 is emitter2

    @pytest.mark.asyncio
    async def test_reset_emitter_state_clears_singleton(
        self,
        mock_redis_client: MagicMock,
    ) -> None:
        """Should clear singleton on reset."""
        emitter1 = await get_job_log_emitter(mock_redis_client)
        reset_emitter_state()
        emitter2 = await get_job_log_emitter()

        assert emitter1 is not emitter2


# =============================================================================
# Tests for Integration with JobHistoryService
# =============================================================================


class TestJobHistoryServiceIntegration:
    """Tests for integration with JobHistoryService."""

    @pytest.mark.asyncio
    async def test_add_job_log_emits_to_websocket(
        self,
        mock_redis_client: MagicMock,
    ) -> None:
        """Should emit log to WebSocket when adding job log."""
        # Initialize the emitter with the mock Redis client
        await get_job_log_emitter(mock_redis_client)

        # Mock the session
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        from backend.services.job_history_service import JobHistoryService

        service = JobHistoryService(mock_session)
        job_id = str(uuid.uuid4())

        await service.add_job_log(
            job_id=job_id,
            level="INFO",
            message="Test log entry",
            context={"test": True},
        )

        # Verify Redis publish was called
        mock_redis_client.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_job_log_can_skip_websocket_emission(
        self,
        mock_redis_client: MagicMock,
    ) -> None:
        """Should skip WebSocket emission when emit_to_websocket=False."""
        await get_job_log_emitter(mock_redis_client)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        from backend.services.job_history_service import JobHistoryService

        service = JobHistoryService(mock_session)
        job_id = str(uuid.uuid4())

        await service.add_job_log(
            job_id=job_id,
            level="INFO",
            message="Test log entry",
            emit_to_websocket=False,
        )

        # Verify Redis publish was NOT called
        mock_redis_client.publish.assert_not_called()
