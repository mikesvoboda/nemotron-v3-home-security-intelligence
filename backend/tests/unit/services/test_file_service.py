"""Tests for FileService cascade file deletion.

Related Linear issue: NEM-1988
"""
# ruff: noqa: S108  # Test file uses /tmp paths which is acceptable for testing

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.file_service import (
    FILE_DELETION_QUEUE,
    FileDeletionJob,
    FileService,
    get_file_service,
    reset_file_service,
)


class TestFileDeletionJob:
    """Tests for FileDeletionJob dataclass."""

    def test_create_job_with_defaults(self) -> None:
        """Test creating a job with default values."""
        job = FileDeletionJob(file_paths=["/tmp/test.jpg"], event_id=123)

        assert job.file_paths == ["/tmp/test.jpg"]
        assert job.event_id == 123
        assert job.job_id  # Should have a UUID
        assert job.created_at > 0

    def test_create_job_with_custom_values(self) -> None:
        """Test creating a job with custom values."""
        job = FileDeletionJob(
            file_paths=["/tmp/a.jpg", "/tmp/b.jpg"],
            event_id=456,
            job_id="custom-id",
            created_at=1234567890.0,
        )

        assert job.file_paths == ["/tmp/a.jpg", "/tmp/b.jpg"]
        assert job.event_id == 456
        assert job.job_id == "custom-id"
        assert job.created_at == 1234567890.0

    def test_to_json(self) -> None:
        """Test serializing job to JSON."""
        job = FileDeletionJob(
            file_paths=["/tmp/test.jpg"],
            event_id=123,
            job_id="test-id",
            created_at=1234567890.0,
        )
        json_str = job.to_json()
        data = json.loads(json_str)

        assert data["file_paths"] == ["/tmp/test.jpg"]
        assert data["event_id"] == 123
        assert data["job_id"] == "test-id"
        assert data["created_at"] == 1234567890.0

    def test_from_json(self) -> None:
        """Test deserializing job from JSON."""
        json_str = json.dumps(
            {
                "file_paths": ["/tmp/test.jpg"],
                "event_id": 123,
                "job_id": "test-id",
                "created_at": 1234567890.0,
            }
        )
        job = FileDeletionJob.from_json(json_str)

        assert job.file_paths == ["/tmp/test.jpg"]
        assert job.event_id == 123
        assert job.job_id == "test-id"
        assert job.created_at == 1234567890.0

    def test_roundtrip_serialization(self) -> None:
        """Test that serialization and deserialization are inverse operations."""
        original = FileDeletionJob(
            file_paths=["/tmp/a.jpg", "/tmp/b.jpg"],
            event_id=789,
        )
        restored = FileDeletionJob.from_json(original.to_json())

        assert restored.file_paths == original.file_paths
        assert restored.event_id == original.event_id
        assert restored.job_id == original.job_id
        assert restored.created_at == original.created_at


class TestFileServiceScheduleDeletion:
    """Tests for FileService.schedule_deletion method."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.zadd = AsyncMock(return_value=1)
        redis.zrange = AsyncMock(return_value=[])
        redis.zrem = AsyncMock(return_value=1)
        redis.zcard = AsyncMock(return_value=0)
        redis.zrangebyscore = AsyncMock(return_value=[])
        return redis

    @pytest.mark.asyncio
    async def test_schedule_deletion_success(self, mock_redis: MagicMock) -> None:
        """Test successfully scheduling file deletion."""
        service = FileService(redis_client=mock_redis)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            job_id = await service.schedule_deletion(
                file_paths=[temp_path],
                event_id=123,
            )

            assert job_id is not None
            mock_redis.zadd.assert_called_once()

            # Verify the call arguments
            call_args = mock_redis.zadd.call_args
            assert call_args[0][0] == FILE_DELETION_QUEUE
            mapping = call_args[0][1]
            assert len(mapping) == 1

            # Verify the job data
            job_json = next(iter(mapping.keys()))
            job = FileDeletionJob.from_json(job_json)
            assert job.file_paths == [temp_path]
            assert job.event_id == 123
            assert job.job_id == job_id
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_schedule_deletion_with_custom_delay(self, mock_redis: MagicMock) -> None:
        """Test scheduling with custom delay."""
        service = FileService(redis_client=mock_redis)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            before = time.time()
            await service.schedule_deletion(
                file_paths=[temp_path],
                event_id=123,
                delay_seconds=600,  # 10 minutes
            )
            after = time.time()

            # Verify the score (deletion time) is approximately 10 minutes from now
            call_args = mock_redis.zadd.call_args
            mapping = call_args[0][1]
            score = next(iter(mapping.values()))

            assert score >= before + 600
            assert score <= after + 600
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_schedule_deletion_no_redis(self) -> None:
        """Test that schedule_deletion returns None when Redis unavailable."""
        service = FileService(redis_client=None)

        with patch("backend.services.file_service.get_redis_client_sync", return_value=None):
            job_id = await service.schedule_deletion(
                file_paths=["/tmp/test.jpg"],
                event_id=123,
            )

        assert job_id is None

    @pytest.mark.asyncio
    async def test_schedule_deletion_empty_paths(self, mock_redis: MagicMock) -> None:
        """Test that empty file paths returns None."""
        service = FileService(redis_client=mock_redis)

        job_id = await service.schedule_deletion(
            file_paths=[],
            event_id=123,
        )

        assert job_id is None
        mock_redis.zadd.assert_not_called()

    @pytest.mark.asyncio
    async def test_schedule_deletion_nonexistent_files(self, mock_redis: MagicMock) -> None:
        """Test that nonexistent files are filtered out."""
        service = FileService(redis_client=mock_redis)

        job_id = await service.schedule_deletion(
            file_paths=["/nonexistent/file.jpg"],
            event_id=123,
        )

        assert job_id is None
        mock_redis.zadd.assert_not_called()


class TestFileServiceCancelDeletion:
    """Tests for FileService cancellation methods."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.zadd = AsyncMock(return_value=1)
        redis.zrange = AsyncMock(return_value=[])
        redis.zrem = AsyncMock(return_value=1)
        redis.zcard = AsyncMock(return_value=0)
        redis.zrangebyscore = AsyncMock(return_value=[])
        return redis

    @pytest.mark.asyncio
    async def test_cancel_deletion_by_job_id_success(self, mock_redis: MagicMock) -> None:
        """Test cancelling a job by its ID."""
        job = FileDeletionJob(file_paths=["/tmp/test.jpg"], event_id=123, job_id="target-id")
        mock_redis.zrange.return_value = [job.to_json()]

        service = FileService(redis_client=mock_redis)
        result = await service.cancel_deletion("target-id")

        assert result is True
        mock_redis.zrem.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_deletion_by_job_id_not_found(self, mock_redis: MagicMock) -> None:
        """Test cancelling a non-existent job."""
        mock_redis.zrange.return_value = []

        service = FileService(redis_client=mock_redis)
        result = await service.cancel_deletion("nonexistent-id")

        assert result is False
        mock_redis.zrem.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancel_deletion_by_event_id_success(self, mock_redis: MagicMock) -> None:
        """Test cancelling all jobs for an event."""
        job1 = FileDeletionJob(file_paths=["/tmp/a.jpg"], event_id=123, job_id="job1")
        job2 = FileDeletionJob(file_paths=["/tmp/b.jpg"], event_id=123, job_id="job2")
        job3 = FileDeletionJob(file_paths=["/tmp/c.jpg"], event_id=456, job_id="job3")
        mock_redis.zrange.return_value = [job1.to_json(), job2.to_json(), job3.to_json()]

        service = FileService(redis_client=mock_redis)
        count = await service.cancel_deletion_by_event_id(123)

        assert count == 2
        assert mock_redis.zrem.call_count == 2

    @pytest.mark.asyncio
    async def test_cancel_deletion_by_event_id_none_found(self, mock_redis: MagicMock) -> None:
        """Test cancelling when no jobs exist for event."""
        job = FileDeletionJob(file_paths=["/tmp/test.jpg"], event_id=456, job_id="other-job")
        mock_redis.zrange.return_value = [job.to_json()]

        service = FileService(redis_client=mock_redis)
        count = await service.cancel_deletion_by_event_id(123)

        assert count == 0
        mock_redis.zrem.assert_not_called()


class TestFileServiceProcessQueue:
    """Tests for FileService.process_deletion_queue method."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.zadd = AsyncMock(return_value=1)
        redis.zrange = AsyncMock(return_value=[])
        redis.zrem = AsyncMock(return_value=1)
        redis.zcard = AsyncMock(return_value=0)
        redis.zrangebyscore = AsyncMock(return_value=[])
        return redis

    @pytest.mark.asyncio
    async def test_process_queue_empty(self, mock_redis: MagicMock) -> None:
        """Test processing an empty queue."""
        mock_redis.zrangebyscore.return_value = []

        service = FileService(redis_client=mock_redis)
        jobs_processed, files_deleted = await service.process_deletion_queue()

        assert jobs_processed == 0
        assert files_deleted == 0

    @pytest.mark.asyncio
    async def test_process_queue_with_due_jobs(self, mock_redis: MagicMock) -> None:
        """Test processing jobs that are due for deletion."""
        # Create temp files to delete
        with tempfile.NamedTemporaryFile(delete=False) as f1:
            temp1 = f1.name
        with tempfile.NamedTemporaryFile(delete=False) as f2:
            temp2 = f2.name

        try:
            job = FileDeletionJob(
                file_paths=[temp1, temp2],
                event_id=123,
                job_id="test-job",
            )
            mock_redis.zrangebyscore.return_value = [job.to_json()]

            service = FileService(redis_client=mock_redis)
            jobs_processed, files_deleted = await service.process_deletion_queue()

            assert jobs_processed == 1
            assert files_deleted == 2
            mock_redis.zrem.assert_called_once()

            # Verify files were deleted
            assert not Path(temp1).exists()
            assert not Path(temp2).exists()
        finally:
            Path(temp1).unlink(missing_ok=True)
            Path(temp2).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_process_queue_handles_missing_files(self, mock_redis: MagicMock) -> None:
        """Test that processing handles already-deleted files gracefully."""
        job = FileDeletionJob(
            file_paths=["/nonexistent/file.jpg"],
            event_id=123,
            job_id="test-job",
        )
        mock_redis.zrangebyscore.return_value = [job.to_json()]

        service = FileService(redis_client=mock_redis)
        jobs_processed, files_deleted = await service.process_deletion_queue()

        assert jobs_processed == 1
        assert files_deleted == 0  # File didn't exist
        mock_redis.zrem.assert_called_once()


class TestFileServiceDeleteFile:
    """Tests for FileService.delete_file method."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_delete_file_success(self, mock_redis: MagicMock) -> None:
        """Test successfully deleting a file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        assert Path(temp_path).exists()

        service = FileService(redis_client=mock_redis)
        result = await service.delete_file(temp_path)

        assert result is True
        assert not Path(temp_path).exists()

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, mock_redis: MagicMock) -> None:
        """Test deleting a non-existent file."""
        service = FileService(redis_client=mock_redis)
        result = await service.delete_file("/nonexistent/file.jpg")

        assert result is False


class TestFileServiceSingleton:
    """Tests for FileService singleton pattern."""

    def test_get_file_service_returns_same_instance(self) -> None:
        """Test that get_file_service returns the same instance."""
        reset_file_service()
        service1 = get_file_service()
        service2 = get_file_service()

        assert service1 is service2

    def test_reset_file_service_clears_instance(self) -> None:
        """Test that reset_file_service clears the singleton."""
        reset_file_service()
        service1 = get_file_service()
        reset_file_service()
        service2 = get_file_service()

        assert service1 is not service2


class TestFileServiceBackgroundWorker:
    """Tests for FileService background worker."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.zrangebyscore = AsyncMock(return_value=[])
        redis.zcard = AsyncMock(return_value=0)
        return redis

    @pytest.mark.asyncio
    async def test_start_stop_background_worker(self, mock_redis: MagicMock) -> None:
        """Test starting and stopping the background worker."""
        service = FileService(redis_client=mock_redis)

        await service.start()
        assert service._running is True
        assert service._task is not None

        await service.stop()
        assert service._running is False
        assert service._task is None

    @pytest.mark.asyncio
    async def test_start_twice_logs_warning(self, mock_redis: MagicMock) -> None:
        """Test that starting twice doesn't create multiple workers."""
        service = FileService(redis_client=mock_redis)

        await service.start()
        task1 = service._task

        await service.start()  # Should log warning
        task2 = service._task

        assert task1 is task2

        await service.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, mock_redis: MagicMock) -> None:
        """Test that stopping when not running is safe."""
        service = FileService(redis_client=mock_redis)

        # Should not raise
        await service.stop()


class TestFileServiceGetters:
    """Tests for FileService getter methods."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.zcard = AsyncMock(return_value=5)
        redis.zrange = AsyncMock(return_value=[])
        return redis

    @pytest.mark.asyncio
    async def test_get_queue_size(self, mock_redis: MagicMock) -> None:
        """Test getting the queue size."""
        mock_redis.zcard.return_value = 5

        service = FileService(redis_client=mock_redis)
        size = await service.get_queue_size()

        assert size == 5
        mock_redis.zcard.assert_called_once_with(FILE_DELETION_QUEUE)

    @pytest.mark.asyncio
    async def test_get_pending_jobs_for_event(self, mock_redis: MagicMock) -> None:
        """Test getting pending jobs for a specific event."""
        job1 = FileDeletionJob(file_paths=["/tmp/a.jpg"], event_id=123, job_id="job1")
        job2 = FileDeletionJob(file_paths=["/tmp/b.jpg"], event_id=456, job_id="job2")
        mock_redis.zrange.return_value = [job1.to_json(), job2.to_json()]

        service = FileService(redis_client=mock_redis)
        jobs = await service.get_pending_jobs_for_event(123)

        assert len(jobs) == 1
        assert jobs[0].event_id == 123
        assert jobs[0].job_id == "job1"
