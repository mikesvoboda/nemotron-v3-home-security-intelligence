"""Tests for the Exports API routes (NEM-2385)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# Import route module for coverage tracking
import backend.api.routes.exports  # noqa: F401
from backend.api.routes.exports import (
    _get_export_job,
    _model_to_response,
    cancel_export,
    download_export,
    get_download_info,
    get_export_status,
    list_exports,
    run_export_job_with_db,
    start_export,
)
from backend.api.schemas.export import (
    ExportFormatEnum,
    ExportJobCreate,
    ExportJobStatusEnum,
    ExportTypeEnum,
)
from backend.models.export_job import ExportJob, ExportJobStatus
from backend.services.export_service import ExportService
from backend.services.job_tracker import JobTracker


@pytest.fixture
def mock_job_tracker() -> MagicMock:
    """Create a mock job tracker."""
    tracker = MagicMock(spec=JobTracker)
    tracker.create_job = MagicMock()
    tracker.start_job = MagicMock()
    tracker.complete_job = MagicMock()
    tracker.fail_job = MagicMock()
    tracker.cancel_job = MagicMock()
    return tracker


@pytest.fixture
def mock_export_service() -> MagicMock:
    """Create a mock export service."""
    service = MagicMock(spec=ExportService)
    service.export_events_with_progress = AsyncMock(
        return_value={
            "file_path": "/api/exports/test.csv",
            "file_size": 12345,
            "event_count": 100,
        }
    )
    return service


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def sample_export_job() -> ExportJob:
    """Create a sample export job for testing."""
    job = ExportJob(
        id=str(uuid4()),
        status=ExportJobStatus.PENDING,
        export_type="events",
        export_format="csv",
        total_items=None,
        processed_items=0,
        progress_percent=0,
        current_step=None,
        created_at=datetime.now(UTC),
        started_at=None,
        completed_at=None,
        estimated_completion=None,
        output_path=None,
        output_size_bytes=None,
        error_message=None,
        filter_params=None,
    )
    return job


@pytest.fixture
def completed_export_job() -> ExportJob:
    """Create a completed export job for testing."""
    job = ExportJob(
        id=str(uuid4()),
        status=ExportJobStatus.COMPLETED,
        export_type="events",
        export_format="csv",
        total_items=100,
        processed_items=100,
        progress_percent=100,
        current_step="Complete",
        created_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        estimated_completion=None,
        output_path="/api/exports/events_export_20250112.csv",
        output_size_bytes=12345,
        error_message=None,
        filter_params=None,
    )
    return job


class TestModelToResponse:
    """Tests for _model_to_response helper function."""

    def test_model_to_response_pending_job(self, sample_export_job: ExportJob) -> None:
        """Should convert pending job to response."""
        # Already imported

        response = _model_to_response(sample_export_job)

        assert response.id == sample_export_job.id
        assert response.status == ExportJobStatusEnum.PENDING
        assert response.export_type == "events"
        assert response.export_format == "csv"
        assert response.progress.total_items is None
        assert response.progress.processed_items == 0
        assert response.result is None
        assert response.error_message is None

    def test_model_to_response_completed_job(self, completed_export_job: ExportJob) -> None:
        """Should convert completed job with result to response."""
        # Already imported

        response = _model_to_response(completed_export_job)

        assert response.id == completed_export_job.id
        assert response.status == ExportJobStatusEnum.COMPLETED
        assert response.progress.progress_percent == 100
        assert response.result is not None
        assert response.result.output_path == "/api/exports/events_export_20250112.csv"
        assert response.result.output_size_bytes == 12345
        assert response.result.event_count == 100

    def test_model_to_response_with_progress(self) -> None:
        """Should include progress information."""
        # Already imported

        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.RUNNING,
            export_type="events",
            export_format="json",
            total_items=1000,
            processed_items=500,
            progress_percent=50,
            current_step="Processing events...",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=None,
            estimated_completion=datetime(2025, 1, 12, 14, 30, tzinfo=UTC),
            output_path=None,
            output_size_bytes=None,
            error_message=None,
            filter_params=None,
        )

        response = _model_to_response(job)

        assert response.status == ExportJobStatusEnum.RUNNING
        assert response.progress.total_items == 1000
        assert response.progress.processed_items == 500
        assert response.progress.progress_percent == 50
        assert response.progress.current_step == "Processing events..."
        assert response.progress.estimated_completion is not None


class TestGetExportJob:
    """Tests for _get_export_job helper function."""

    @pytest.mark.asyncio
    async def test_get_export_job_found(
        self,
        mock_db: AsyncMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Should return job when found."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute.return_value = mock_result

        result = await _get_export_job(sample_export_job.id, mock_db)

        assert result.id == sample_export_job.id
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_export_job_not_found(self, mock_db: AsyncMock) -> None:
        """Should raise 404 when job not found."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await _get_export_job("nonexistent-id", mock_db)

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()


class TestRunExportJobWithDb:
    """Tests for run_export_job_with_db background task function."""

    @pytest.mark.asyncio
    async def test_run_export_job_success(
        self,
        mock_db: AsyncMock,
        mock_export_service: MagicMock,
        mock_job_tracker: MagicMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Should successfully run export job and update database."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute.return_value = mock_result

        await run_export_job_with_db(
            job_id=sample_export_job.id,
            export_format="csv",
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            export_service=mock_export_service,
            job_tracker=mock_job_tracker,
            db=mock_db,
        )

        # Verify status updates
        assert sample_export_job.status == ExportJobStatus.COMPLETED
        assert sample_export_job.progress_percent == 100
        assert sample_export_job.output_path == "/api/exports/test.csv"
        assert sample_export_job.output_size_bytes == 12345
        assert sample_export_job.processed_items == 100

        # Verify tracker calls
        mock_job_tracker.start_job.assert_called_once()
        mock_job_tracker.complete_job.assert_called_once()
        mock_export_service.export_events_with_progress.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_export_job_with_filters(
        self,
        mock_db: AsyncMock,
        mock_export_service: MagicMock,
        mock_job_tracker: MagicMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Should pass filters to export service."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute.return_value = mock_result

        await run_export_job_with_db(
            job_id=sample_export_job.id,
            export_format="csv",
            camera_id="front_door",
            risk_level="high",
            start_date="2025-01-01T00:00:00Z",
            end_date="2025-01-12T23:59:59Z",
            reviewed=True,
            export_service=mock_export_service,
            job_tracker=mock_job_tracker,
            db=mock_db,
        )

        # Verify export_events_with_progress called with filters
        call_args = mock_export_service.export_events_with_progress.call_args
        assert call_args[1]["camera_id"] == "front_door"
        assert call_args[1]["risk_level"] == "high"
        assert call_args[1]["start_date"] == "2025-01-01T00:00:00Z"
        assert call_args[1]["end_date"] == "2025-01-12T23:59:59Z"
        assert call_args[1]["reviewed"] is True

    @pytest.mark.asyncio
    async def test_run_export_job_not_found(
        self,
        mock_db: AsyncMock,
        mock_export_service: MagicMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Should handle job not found gracefully."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Should not raise, just log error
        await run_export_job_with_db(
            job_id="nonexistent",
            export_format="csv",
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            export_service=mock_export_service,
            job_tracker=mock_job_tracker,
            db=mock_db,
        )

        # Export should not be called
        mock_export_service.export_events_with_progress.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_export_job_failure(
        self,
        mock_db: AsyncMock,
        mock_export_service: MagicMock,
        mock_job_tracker: MagicMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Should handle export failure and update status."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute.return_value = mock_result

        # Make export fail
        mock_export_service.export_events_with_progress.side_effect = Exception("Export error")

        await run_export_job_with_db(
            job_id=sample_export_job.id,
            export_format="csv",
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            export_service=mock_export_service,
            job_tracker=mock_job_tracker,
            db=mock_db,
        )

        # Verify failure status
        assert sample_export_job.status == ExportJobStatus.FAILED
        assert "Export error" in sample_export_job.error_message
        mock_job_tracker.fail_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_export_job_failure_db_update_fails(
        self,
        mock_db: AsyncMock,
        mock_export_service: MagicMock,
        mock_job_tracker: MagicMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Should handle case where failure status update also fails."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute.return_value = mock_result

        # Make export fail
        mock_export_service.export_events_with_progress.side_effect = Exception("Export error")

        # Make db.refresh fail
        mock_db.refresh.side_effect = Exception("DB error")

        # Should not raise, just log
        await run_export_job_with_db(
            job_id=sample_export_job.id,
            export_format="csv",
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            export_service=mock_export_service,
            job_tracker=mock_job_tracker,
            db=mock_db,
        )

        mock_job_tracker.fail_job.assert_called_once()


class TestStartExport:
    """Tests for POST /api/exports."""

    @pytest.mark.asyncio
    async def test_start_export_creates_job(
        self,
        mock_job_tracker: MagicMock,
        mock_export_service: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Should create an export job and return 202."""
        # Already imported

        request = ExportJobCreate(
            export_type=ExportTypeEnum.EVENTS,
            export_format=ExportFormatEnum.CSV,
        )

        background_tasks = BackgroundTasks()

        result = await start_export(
            request=request,
            background_tasks=background_tasks,
            db=mock_db,
            export_service=mock_export_service,
            job_tracker=mock_job_tracker,
        )

        assert result.status == ExportJobStatusEnum.PENDING
        assert "GET /api/exports/" in result.message
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_job_tracker.create_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_export_with_all_filters(
        self,
        mock_job_tracker: MagicMock,
        mock_export_service: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Should accept all filter parameters."""
        # Already imported

        request = ExportJobCreate(
            export_type=ExportTypeEnum.EVENTS,
            export_format=ExportFormatEnum.CSV,
            camera_id="front_door",
            risk_level="high",
            start_date=datetime(2025, 1, 1, tzinfo=UTC),
            end_date=datetime(2025, 1, 12, tzinfo=UTC),
            reviewed=True,
        )

        background_tasks = BackgroundTasks()

        result = await start_export(
            request=request,
            background_tasks=background_tasks,
            db=mock_db,
            export_service=mock_export_service,
            job_tracker=mock_job_tracker,
        )

        assert result.status == ExportJobStatusEnum.PENDING
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_export_json_format(
        self,
        mock_job_tracker: MagicMock,
        mock_export_service: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Should accept JSON export format."""
        # Already imported

        request = ExportJobCreate(
            export_type=ExportTypeEnum.EVENTS,
            export_format=ExportFormatEnum.JSON,
        )

        background_tasks = BackgroundTasks()

        result = await start_export(
            request=request,
            background_tasks=background_tasks,
            db=mock_db,
            export_service=mock_export_service,
            job_tracker=mock_job_tracker,
        )

        assert result.status == ExportJobStatusEnum.PENDING

    @pytest.mark.asyncio
    async def test_start_export_zip_format(
        self,
        mock_job_tracker: MagicMock,
        mock_export_service: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Should accept ZIP export format."""
        # Already imported

        request = ExportJobCreate(
            export_type=ExportTypeEnum.EVENTS,
            export_format=ExportFormatEnum.ZIP,
        )

        background_tasks = BackgroundTasks()

        result = await start_export(
            request=request,
            background_tasks=background_tasks,
            db=mock_db,
            export_service=mock_export_service,
            job_tracker=mock_job_tracker,
        )

        assert result.status == ExportJobStatusEnum.PENDING

    @pytest.mark.asyncio
    async def test_start_export_excel_format(
        self,
        mock_job_tracker: MagicMock,
        mock_export_service: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Should accept EXCEL export format."""
        # Already imported

        request = ExportJobCreate(
            export_type=ExportTypeEnum.EVENTS,
            export_format=ExportFormatEnum.EXCEL,
        )

        background_tasks = BackgroundTasks()

        result = await start_export(
            request=request,
            background_tasks=background_tasks,
            db=mock_db,
            export_service=mock_export_service,
            job_tracker=mock_job_tracker,
        )

        assert result.status == ExportJobStatusEnum.PENDING


class TestListExports:
    """Tests for GET /api/exports."""

    @pytest.mark.asyncio
    async def test_list_exports_empty(self, mock_db: AsyncMock) -> None:
        """Should return empty list when no jobs exist."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await list_exports(status_filter=None, limit=50, offset=0, db=mock_db)

        assert result.pagination.total == 0
        assert len(result.items) == 0

    @pytest.mark.asyncio
    async def test_list_exports_with_jobs(
        self,
        mock_db: AsyncMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Should return list of export jobs."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_export_job]
        mock_db.execute.return_value = mock_result

        result = await list_exports(status_filter=None, limit=50, offset=0, db=mock_db)

        assert result.pagination.total == 1
        assert len(result.items) == 1
        assert result.items[0].id == sample_export_job.id

    @pytest.mark.asyncio
    async def test_list_exports_with_status_filter(
        self,
        mock_db: AsyncMock,
        completed_export_job: ExportJob,
    ) -> None:
        """Should filter by status."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [completed_export_job]
        mock_db.execute.return_value = mock_result

        result = await list_exports(
            status_filter=ExportJobStatusEnum.COMPLETED,
            limit=50,
            offset=0,
            db=mock_db,
        )

        assert result.pagination.total == 1
        assert result.items[0].status == ExportJobStatusEnum.COMPLETED

    @pytest.mark.asyncio
    async def test_list_exports_pagination(self, mock_db: AsyncMock) -> None:
        """Should support pagination with limit and offset."""
        # Already imported

        jobs = [
            ExportJob(
                id=str(uuid4()),
                status=ExportJobStatus.PENDING,
                export_type="events",
                export_format="csv",
                total_items=None,
                processed_items=0,
                progress_percent=0,
                current_step=None,
                created_at=datetime.now(UTC),
                started_at=None,
                completed_at=None,
                estimated_completion=None,
                output_path=None,
                output_size_bytes=None,
                error_message=None,
                filter_params=None,
            )
            for _ in range(5)
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = jobs[:2]  # Return 2 of 5
        mock_db.execute.return_value = mock_result

        # First call returns all jobs for count
        count_result = MagicMock()
        count_result.scalars.return_value.all.return_value = jobs
        mock_db.execute.side_effect = [count_result, mock_result]

        result = await list_exports(status_filter=None, limit=2, offset=0, db=mock_db)

        assert result.pagination.total == 5
        assert result.pagination.limit == 2
        assert result.pagination.offset == 0
        assert len(result.items) == 2


class TestGetExportStatus:
    """Tests for GET /api/exports/{job_id}."""

    @pytest.mark.asyncio
    async def test_get_export_status_found(
        self,
        mock_db: AsyncMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Should return export job status when found."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute.return_value = mock_result

        result = await get_export_status(job_id=sample_export_job.id, db=mock_db)

        assert result.id == sample_export_job.id
        assert result.status == ExportJobStatusEnum.PENDING

    @pytest.mark.asyncio
    async def test_get_export_status_not_found(self, mock_db: AsyncMock) -> None:
        """Should raise 404 when job not found."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_export_status(job_id="nonexistent-id", db=mock_db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_export_status_completed(
        self,
        mock_db: AsyncMock,
        completed_export_job: ExportJob,
    ) -> None:
        """Should return result for completed job."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = completed_export_job
        mock_db.execute.return_value = mock_result

        result = await get_export_status(job_id=completed_export_job.id, db=mock_db)

        assert result.status == ExportJobStatusEnum.COMPLETED
        assert result.result is not None
        assert result.result.output_path is not None


class TestCancelExport:
    """Tests for DELETE /api/exports/{job_id}."""

    @pytest.mark.asyncio
    async def test_cancel_export_success(
        self,
        mock_db: AsyncMock,
        mock_job_tracker: MagicMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Should cancel a pending export job."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute.return_value = mock_result

        result = await cancel_export(
            job_id=sample_export_job.id,
            db=mock_db,
            job_tracker=mock_job_tracker,
        )

        assert result.job_id == sample_export_job.id
        assert result.status == ExportJobStatusEnum.FAILED
        assert result.cancelled is True
        assert sample_export_job.status == ExportJobStatus.FAILED
        assert "Cancelled by user" in sample_export_job.error_message
        mock_job_tracker.cancel_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_export_running(
        self,
        mock_db: AsyncMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Should cancel a running export job."""
        # Already imported

        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.RUNNING,
            export_type="events",
            export_format="csv",
            total_items=1000,
            processed_items=500,
            progress_percent=50,
            current_step="Processing...",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=None,
            estimated_completion=None,
            output_path=None,
            output_size_bytes=None,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute.return_value = mock_result

        result = await cancel_export(job_id=job.id, db=mock_db, job_tracker=mock_job_tracker)

        assert result.cancelled is True

    @pytest.mark.asyncio
    async def test_cancel_export_not_found(
        self,
        mock_db: AsyncMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Should return 404 when job not found."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await cancel_export(
                job_id="nonexistent-id",
                db=mock_db,
                job_tracker=mock_job_tracker,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_export_already_completed(
        self,
        mock_db: AsyncMock,
        mock_job_tracker: MagicMock,
        completed_export_job: ExportJob,
    ) -> None:
        """Should return 409 when job already completed."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = completed_export_job
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await cancel_export(
                job_id=completed_export_job.id,
                db=mock_db,
                job_tracker=mock_job_tracker,
            )

        assert exc_info.value.status_code == 409
        assert "cannot be cancelled" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_cancel_export_already_failed(
        self,
        mock_db: AsyncMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Should return 409 when job already failed."""
        # Already imported

        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.FAILED,
            export_type="events",
            export_format="csv",
            total_items=1000,
            processed_items=500,
            progress_percent=50,
            current_step="Failed",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            estimated_completion=None,
            output_path=None,
            output_size_bytes=None,
            error_message="Connection error",
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await cancel_export(job_id=job.id, db=mock_db, job_tracker=mock_job_tracker)

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_cancel_export_tracker_key_error(
        self,
        mock_db: AsyncMock,
        mock_job_tracker: MagicMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Should handle KeyError from job tracker gracefully."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute.return_value = mock_result

        # Make cancel_job raise KeyError
        mock_job_tracker.cancel_job.side_effect = KeyError("Job not in tracker")

        # Should not raise, just continue
        result = await cancel_export(
            job_id=sample_export_job.id,
            db=mock_db,
            job_tracker=mock_job_tracker,
        )

        assert result.cancelled is True


class TestDownloadExport:
    """Tests for GET /api/exports/{job_id}/download."""

    @pytest.mark.asyncio
    async def test_download_export_not_found(self, mock_db: AsyncMock) -> None:
        """Should return 404 when job not found."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await download_export(job_id="nonexistent-id", db=mock_db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_download_export_not_complete(
        self,
        mock_db: AsyncMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Should return 400 when job not complete."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await download_export(job_id=sample_export_job.id, db=mock_db)

        assert exc_info.value.status_code == 400
        assert "not complete" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_download_export_no_output_path(
        self,
        mock_db: AsyncMock,
    ) -> None:
        """Should return 404 when output_path is None."""
        # Already imported

        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.COMPLETED,
            export_type="events",
            export_format="csv",
            total_items=100,
            processed_items=100,
            progress_percent=100,
            current_step="Complete",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            estimated_completion=None,
            output_path=None,  # No output path
            output_size_bytes=None,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await download_export(job_id=job.id, db=mock_db)

        assert exc_info.value.status_code == 404
        assert "path not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_download_export_file_not_on_disk(
        self,
        mock_db: AsyncMock,
        completed_export_job: ExportJob,
    ) -> None:
        """Should return 404 when file doesn't exist on disk."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = completed_export_job
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.exports.EXPORT_DIR") as mock_export_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_export_dir.__truediv__.return_value = mock_path

            with pytest.raises(HTTPException) as exc_info:
                await download_export(job_id=completed_export_job.id, db=mock_db)

            assert exc_info.value.status_code == 404
            assert "not found on disk" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_download_export_success_csv(
        self,
        mock_db: AsyncMock,
        completed_export_job: ExportJob,
    ) -> None:
        """Should return FileResponse for CSV export."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = completed_export_job
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.exports.EXPORT_DIR") as mock_export_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_export_dir.__truediv__.return_value = mock_path

            result = await download_export(job_id=completed_export_job.id, db=mock_db)

            assert result.media_type == "text/csv"
            assert "events_export_20250112.csv" in result.filename

    @pytest.mark.asyncio
    async def test_download_export_success_json(
        self,
        mock_db: AsyncMock,
    ) -> None:
        """Should return FileResponse for JSON export."""
        # Already imported

        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.COMPLETED,
            export_type="events",
            export_format="json",
            total_items=100,
            processed_items=100,
            progress_percent=100,
            current_step="Complete",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            estimated_completion=None,
            output_path="/api/exports/events_export_20250112.json",
            output_size_bytes=12345,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.exports.EXPORT_DIR") as mock_export_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_export_dir.__truediv__.return_value = mock_path

            result = await download_export(job_id=job.id, db=mock_db)

            assert result.media_type == "application/json"

    @pytest.mark.asyncio
    async def test_download_export_success_zip(
        self,
        mock_db: AsyncMock,
    ) -> None:
        """Should return FileResponse for ZIP export."""
        # Already imported

        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.COMPLETED,
            export_type="events",
            export_format="zip",
            total_items=100,
            processed_items=100,
            progress_percent=100,
            current_step="Complete",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            estimated_completion=None,
            output_path="/api/exports/events_export_20250112.zip",
            output_size_bytes=12345,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.exports.EXPORT_DIR") as mock_export_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_export_dir.__truediv__.return_value = mock_path

            result = await download_export(job_id=job.id, db=mock_db)

            assert result.media_type == "application/zip"

    @pytest.mark.asyncio
    async def test_download_export_success_excel(
        self,
        mock_db: AsyncMock,
    ) -> None:
        """Should return FileResponse for Excel export."""
        # Already imported

        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.COMPLETED,
            export_type="events",
            export_format="excel",
            total_items=100,
            processed_items=100,
            progress_percent=100,
            current_step="Complete",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            estimated_completion=None,
            output_path="/api/exports/events_export_20250112.xlsx",
            output_size_bytes=12345,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.exports.EXPORT_DIR") as mock_export_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_export_dir.__truediv__.return_value = mock_path

            result = await download_export(job_id=job.id, db=mock_db)

            assert (
                result.media_type
                == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    @pytest.mark.asyncio
    async def test_download_export_unknown_format(
        self,
        mock_db: AsyncMock,
    ) -> None:
        """Should use octet-stream for unknown formats."""
        # Already imported

        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.COMPLETED,
            export_type="events",
            export_format="unknown",
            total_items=100,
            processed_items=100,
            progress_percent=100,
            current_step="Complete",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            estimated_completion=None,
            output_path="/api/exports/events_export_20250112.dat",
            output_size_bytes=12345,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.exports.EXPORT_DIR") as mock_export_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_export_dir.__truediv__.return_value = mock_path

            result = await download_export(job_id=job.id, db=mock_db)

            assert result.media_type == "application/octet-stream"


class TestGetDownloadInfo:
    """Tests for GET /api/exports/{job_id}/download/info."""

    @pytest.mark.asyncio
    async def test_get_download_info_not_found(self, mock_db: AsyncMock) -> None:
        """Should raise 404 when job not found."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_download_info(job_id="nonexistent-id", db=mock_db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_download_info_not_ready_pending(
        self,
        mock_db: AsyncMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Should return not ready for pending job."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute.return_value = mock_result

        result = await get_download_info(job_id=sample_export_job.id, db=mock_db)

        assert result.ready is False
        assert result.filename is None
        assert result.content_type is None
        assert result.size_bytes is None
        assert result.download_url is None

    @pytest.mark.asyncio
    async def test_get_download_info_not_ready_no_path(
        self,
        mock_db: AsyncMock,
    ) -> None:
        """Should return not ready when completed but no output_path."""
        # Already imported

        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.COMPLETED,
            export_type="events",
            export_format="csv",
            total_items=100,
            processed_items=100,
            progress_percent=100,
            current_step="Complete",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            estimated_completion=None,
            output_path=None,  # No path
            output_size_bytes=None,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute.return_value = mock_result

        result = await get_download_info(job_id=job.id, db=mock_db)

        assert result.ready is False

    @pytest.mark.asyncio
    async def test_get_download_info_not_ready_file_missing(
        self,
        mock_db: AsyncMock,
        completed_export_job: ExportJob,
    ) -> None:
        """Should return not ready when file doesn't exist on disk."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = completed_export_job
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.exports.EXPORT_DIR") as mock_export_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_export_dir.__truediv__.return_value = mock_path

            result = await get_download_info(job_id=completed_export_job.id, db=mock_db)

            assert result.ready is False

    @pytest.mark.asyncio
    async def test_get_download_info_ready_csv(
        self,
        mock_db: AsyncMock,
        completed_export_job: ExportJob,
    ) -> None:
        """Should return download info when ready (CSV)."""
        # Already imported

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = completed_export_job
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.exports.EXPORT_DIR") as mock_export_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_export_dir.__truediv__.return_value = mock_path

            result = await get_download_info(job_id=completed_export_job.id, db=mock_db)

            assert result.ready is True
            assert result.filename == "events_export_20250112.csv"
            assert result.content_type == "text/csv"
            assert result.size_bytes == 12345
            assert result.download_url == f"/api/exports/{completed_export_job.id}/download"

    @pytest.mark.asyncio
    async def test_get_download_info_ready_json(
        self,
        mock_db: AsyncMock,
    ) -> None:
        """Should return download info for JSON export."""
        # Already imported

        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.COMPLETED,
            export_type="events",
            export_format="json",
            total_items=100,
            processed_items=100,
            progress_percent=100,
            current_step="Complete",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            estimated_completion=None,
            output_path="/api/exports/events_export_20250112.json",
            output_size_bytes=54321,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.exports.EXPORT_DIR") as mock_export_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_export_dir.__truediv__.return_value = mock_path

            result = await get_download_info(job_id=job.id, db=mock_db)

            assert result.ready is True
            assert result.content_type == "application/json"
            assert result.size_bytes == 54321

    @pytest.mark.asyncio
    async def test_get_download_info_ready_zip(
        self,
        mock_db: AsyncMock,
    ) -> None:
        """Should return download info for ZIP export."""
        # Already imported

        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.COMPLETED,
            export_type="events",
            export_format="zip",
            total_items=100,
            processed_items=100,
            progress_percent=100,
            current_step="Complete",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            estimated_completion=None,
            output_path="/api/exports/events_export_20250112.zip",
            output_size_bytes=99999,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.exports.EXPORT_DIR") as mock_export_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_export_dir.__truediv__.return_value = mock_path

            result = await get_download_info(job_id=job.id, db=mock_db)

            assert result.ready is True
            assert result.content_type == "application/zip"

    @pytest.mark.asyncio
    async def test_get_download_info_ready_excel(
        self,
        mock_db: AsyncMock,
    ) -> None:
        """Should return download info for Excel export."""
        # Already imported

        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.COMPLETED,
            export_type="events",
            export_format="excel",
            total_items=100,
            processed_items=100,
            progress_percent=100,
            current_step="Complete",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            estimated_completion=None,
            output_path="/api/exports/events_export_20250112.xlsx",
            output_size_bytes=88888,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.exports.EXPORT_DIR") as mock_export_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_export_dir.__truediv__.return_value = mock_path

            result = await get_download_info(job_id=job.id, db=mock_db)

            assert result.ready is True
            assert (
                result.content_type
                == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    @pytest.mark.asyncio
    async def test_get_download_info_ready_unknown_format(
        self,
        mock_db: AsyncMock,
    ) -> None:
        """Should use octet-stream for unknown formats."""
        # Already imported

        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.COMPLETED,
            export_type="events",
            export_format="unknown",
            total_items=100,
            processed_items=100,
            progress_percent=100,
            current_step="Complete",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            estimated_completion=None,
            output_path="/api/exports/events_export_20250112.dat",
            output_size_bytes=11111,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.exports.EXPORT_DIR") as mock_export_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_export_dir.__truediv__.return_value = mock_path

            result = await get_download_info(job_id=job.id, db=mock_db)

            assert result.ready is True
            assert result.content_type == "application/octet-stream"
