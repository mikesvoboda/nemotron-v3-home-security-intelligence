"""Unit tests for the job search service.

Tests filtering, aggregation, sorting, and pagination logic.
NEM-2392: Job search and filtering API.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from backend.services.job_search_service import (
    JobAggregations,
    JobSearchFilters,
    JobSearchResult,
    JobSearchService,
    JobSortField,
    SortOrder,
    _calculate_job_duration,
    _compute_aggregations,
    _filter_job,
    _get_sort_key,
    _matches_duration_filter,
    _matches_error_filter,
    _matches_status_filter,
    _matches_text_query,
    _matches_timestamp_filter,
    _matches_type_filter,
    _parse_datetime,
    search_jobs,
    search_jobs_with_aggregations,
)
from backend.services.job_tracker import JobInfo, JobStatus, JobTracker


@pytest.fixture
def mock_job_tracker() -> MagicMock:
    """Create a mock job tracker."""
    return MagicMock(spec=JobTracker)


@pytest.fixture
def sample_jobs() -> list[JobInfo]:
    """Create sample jobs for testing."""
    now = datetime.now(UTC)
    return [
        JobInfo(
            job_id="job-1",
            job_type="export",
            status=JobStatus.COMPLETED,
            progress=100,
            message="Export completed",
            created_at=(now - timedelta(hours=2)).isoformat(),
            started_at=(now - timedelta(hours=2, minutes=-1)).isoformat(),
            completed_at=(now - timedelta(hours=1, minutes=30)).isoformat(),
            result={"file_path": "/exports/data.csv"},
            error=None,
        ),
        JobInfo(
            job_id="job-2",
            job_type="cleanup",
            status=JobStatus.FAILED,
            progress=50,
            message="Cleanup failed",
            created_at=(now - timedelta(hours=1)).isoformat(),
            started_at=(now - timedelta(hours=1, minutes=-1)).isoformat(),
            completed_at=(now - timedelta(minutes=30)).isoformat(),
            result=None,
            error="Connection timeout",
        ),
        JobInfo(
            job_id="job-3",
            job_type="export",
            status=JobStatus.RUNNING,
            progress=75,
            message="Processing events",
            created_at=(now - timedelta(minutes=30)).isoformat(),
            started_at=(now - timedelta(minutes=29)).isoformat(),
            completed_at=None,
            result=None,
            error=None,
        ),
        JobInfo(
            job_id="job-4",
            job_type="backup",
            status=JobStatus.PENDING,
            progress=0,
            message=None,
            created_at=(now - timedelta(minutes=10)).isoformat(),
            started_at=None,
            completed_at=None,
            result=None,
            error=None,
        ),
    ]


class TestParseDatetime:
    """Tests for _parse_datetime helper."""

    def test_parse_iso_string(self) -> None:
        """Should parse ISO format datetime string."""
        result = _parse_datetime("2024-01-15T10:30:00+00:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_z_suffix(self) -> None:
        """Should handle Z suffix for UTC."""
        result = _parse_datetime("2024-01-15T10:30:00Z")
        assert result is not None
        assert result.year == 2024

    def test_parse_datetime_object(self) -> None:
        """Should return datetime objects as-is."""
        dt = datetime(2024, 1, 15, 10, 30, tzinfo=UTC)
        result = _parse_datetime(dt)
        assert result == dt

    def test_parse_none(self) -> None:
        """Should return None for None input."""
        result = _parse_datetime(None)
        assert result is None

    def test_parse_invalid_string(self) -> None:
        """Should return None for invalid string."""
        result = _parse_datetime("not-a-date")
        assert result is None


class TestCalculateJobDuration:
    """Tests for _calculate_job_duration helper."""

    def test_completed_job_duration(self, sample_jobs: list[JobInfo]) -> None:
        """Should calculate duration for completed jobs."""
        # Job 1 is completed
        duration = _calculate_job_duration(sample_jobs[0])
        assert duration is not None
        assert duration > 0

    def test_running_job_no_duration(self, sample_jobs: list[JobInfo]) -> None:
        """Should return None for running jobs (no completed_at)."""
        duration = _calculate_job_duration(sample_jobs[2])
        assert duration is None

    def test_pending_job_no_duration(self, sample_jobs: list[JobInfo]) -> None:
        """Should return None for pending jobs (no started_at)."""
        duration = _calculate_job_duration(sample_jobs[3])
        assert duration is None


class TestMatchesTextQuery:
    """Tests for _matches_text_query helper."""

    def test_matches_job_type(self, sample_jobs: list[JobInfo]) -> None:
        """Should match against job type."""
        assert _matches_text_query(sample_jobs[0], "export")
        assert not _matches_text_query(sample_jobs[0], "cleanup")

    def test_matches_error_message(self, sample_jobs: list[JobInfo]) -> None:
        """Should match against error message."""
        assert _matches_text_query(sample_jobs[1], "timeout")
        assert not _matches_text_query(sample_jobs[0], "timeout")

    def test_matches_status_message(self, sample_jobs: list[JobInfo]) -> None:
        """Should match against status message."""
        assert _matches_text_query(sample_jobs[2], "processing")

    def test_matches_result_dict(self, sample_jobs: list[JobInfo]) -> None:
        """Should match against result dictionary values."""
        assert _matches_text_query(sample_jobs[0], "csv")

    def test_case_insensitive(self, sample_jobs: list[JobInfo]) -> None:
        """Should be case insensitive."""
        assert _matches_text_query(sample_jobs[0], "EXPORT")
        assert _matches_text_query(sample_jobs[0], "Export")

    def test_empty_query_matches_all(self, sample_jobs: list[JobInfo]) -> None:
        """Empty query should match all jobs."""
        assert _matches_text_query(sample_jobs[0], "")
        assert _matches_text_query(sample_jobs[0], None)


class TestMatchesStatusFilter:
    """Tests for _matches_status_filter helper."""

    def test_matches_single_status(self, sample_jobs: list[JobInfo]) -> None:
        """Should match single status."""
        assert _matches_status_filter(sample_jobs[0], ["completed"])
        assert not _matches_status_filter(sample_jobs[0], ["running"])

    def test_matches_multiple_statuses(self, sample_jobs: list[JobInfo]) -> None:
        """Should match any of multiple statuses."""
        assert _matches_status_filter(sample_jobs[0], ["completed", "failed"])
        assert _matches_status_filter(sample_jobs[1], ["completed", "failed"])
        assert not _matches_status_filter(sample_jobs[2], ["completed", "failed"])

    def test_empty_list_matches_all(self, sample_jobs: list[JobInfo]) -> None:
        """Empty list should match all jobs."""
        assert _matches_status_filter(sample_jobs[0], [])


class TestMatchesTypeFilter:
    """Tests for _matches_type_filter helper."""

    def test_matches_single_type(self, sample_jobs: list[JobInfo]) -> None:
        """Should match single type."""
        assert _matches_type_filter(sample_jobs[0], ["export"])
        assert not _matches_type_filter(sample_jobs[0], ["cleanup"])

    def test_matches_multiple_types(self, sample_jobs: list[JobInfo]) -> None:
        """Should match any of multiple types."""
        assert _matches_type_filter(sample_jobs[0], ["export", "cleanup"])
        assert _matches_type_filter(sample_jobs[1], ["export", "cleanup"])
        assert not _matches_type_filter(sample_jobs[3], ["export", "cleanup"])

    def test_empty_list_matches_all(self, sample_jobs: list[JobInfo]) -> None:
        """Empty list should match all jobs."""
        assert _matches_type_filter(sample_jobs[0], [])


class TestMatchesTimestampFilter:
    """Tests for _matches_timestamp_filter helper."""

    def test_created_after_filter(self, sample_jobs: list[JobInfo]) -> None:
        """Should filter by created_at after timestamp."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=1, minutes=30)

        # Job 1 was created 2 hours ago, job 3 was created 30 minutes ago
        assert not _matches_timestamp_filter(sample_jobs[0], cutoff, None, None, None)
        assert _matches_timestamp_filter(sample_jobs[2], cutoff, None, None, None)

    def test_created_before_filter(self, sample_jobs: list[JobInfo]) -> None:
        """Should filter by created_at before timestamp."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=20)

        # Job 4 was created 10 minutes ago
        assert _matches_timestamp_filter(sample_jobs[0], None, cutoff, None, None)
        assert not _matches_timestamp_filter(sample_jobs[3], None, cutoff, None, None)

    def test_completed_after_filter(self, sample_jobs: list[JobInfo]) -> None:
        """Should filter by completed_at after timestamp."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=1)

        # Job 1 completed 1.5 hours ago, job 2 completed 30 minutes ago
        assert not _matches_timestamp_filter(sample_jobs[0], None, None, cutoff, None)
        assert _matches_timestamp_filter(sample_jobs[1], None, None, cutoff, None)

    def test_completed_filter_excludes_uncompleted(self, sample_jobs: list[JobInfo]) -> None:
        """Jobs without completed_at should not match completed filters."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=1)

        # Running and pending jobs have no completed_at
        assert not _matches_timestamp_filter(sample_jobs[2], None, None, cutoff, None)
        assert not _matches_timestamp_filter(sample_jobs[3], None, None, cutoff, None)


class TestMatchesErrorFilter:
    """Tests for _matches_error_filter helper."""

    def test_has_error_true(self, sample_jobs: list[JobInfo]) -> None:
        """Should filter jobs with errors when has_error=True."""
        assert not _matches_error_filter(sample_jobs[0], has_error=True)
        assert _matches_error_filter(sample_jobs[1], has_error=True)

    def test_has_error_false(self, sample_jobs: list[JobInfo]) -> None:
        """Should filter jobs without errors when has_error=False."""
        assert _matches_error_filter(sample_jobs[0], has_error=False)
        assert not _matches_error_filter(sample_jobs[1], has_error=False)

    def test_has_error_none(self, sample_jobs: list[JobInfo]) -> None:
        """Should match all when has_error=None."""
        assert _matches_error_filter(sample_jobs[0], has_error=None)
        assert _matches_error_filter(sample_jobs[1], has_error=None)


class TestMatchesDurationFilter:
    """Tests for _matches_duration_filter helper."""

    def test_min_duration_filter(self, sample_jobs: list[JobInfo]) -> None:
        """Should filter by minimum duration."""
        # Job 1 has a duration (completed job)
        # Assuming duration is around 30 minutes = 1800 seconds
        assert _matches_duration_filter(sample_jobs[0], min_duration=60, max_duration=None)
        assert not _matches_duration_filter(sample_jobs[0], min_duration=7200, max_duration=None)

    def test_max_duration_filter(self, sample_jobs: list[JobInfo]) -> None:
        """Should filter by maximum duration."""
        assert _matches_duration_filter(sample_jobs[0], min_duration=None, max_duration=7200)
        assert not _matches_duration_filter(sample_jobs[0], min_duration=None, max_duration=1)

    def test_duration_filter_excludes_uncompleted(self, sample_jobs: list[JobInfo]) -> None:
        """Jobs without duration should not match duration filters."""
        assert not _matches_duration_filter(sample_jobs[2], min_duration=0, max_duration=None)
        assert not _matches_duration_filter(sample_jobs[3], min_duration=0, max_duration=None)

    def test_no_filter_matches_all(self, sample_jobs: list[JobInfo]) -> None:
        """Should match all when no duration filter."""
        assert _matches_duration_filter(sample_jobs[0], min_duration=None, max_duration=None)
        assert _matches_duration_filter(sample_jobs[2], min_duration=None, max_duration=None)


class TestFilterJob:
    """Tests for _filter_job helper."""

    def test_filter_by_query(self, sample_jobs: list[JobInfo]) -> None:
        """Should filter by text query."""
        filters = JobSearchFilters(query="export")
        assert _filter_job(sample_jobs[0], filters)
        assert not _filter_job(sample_jobs[1], filters)

    def test_filter_by_status(self, sample_jobs: list[JobInfo]) -> None:
        """Should filter by status."""
        filters = JobSearchFilters(statuses=["completed"])
        assert _filter_job(sample_jobs[0], filters)
        assert not _filter_job(sample_jobs[1], filters)

    def test_filter_by_type(self, sample_jobs: list[JobInfo]) -> None:
        """Should filter by job type."""
        filters = JobSearchFilters(job_types=["export"])
        assert _filter_job(sample_jobs[0], filters)
        assert not _filter_job(sample_jobs[1], filters)

    def test_combined_filters(self, sample_jobs: list[JobInfo]) -> None:
        """Should apply all filters (AND logic)."""
        filters = JobSearchFilters(
            query="export",
            statuses=["completed"],
            job_types=["export"],
        )
        assert _filter_job(sample_jobs[0], filters)
        assert not _filter_job(sample_jobs[2], filters)  # Running export


class TestComputeAggregations:
    """Tests for _compute_aggregations helper."""

    def test_aggregates_by_status(self, sample_jobs: list[JobInfo]) -> None:
        """Should aggregate counts by status."""
        aggs = _compute_aggregations(sample_jobs)
        assert aggs.by_status["completed"] == 1
        assert aggs.by_status["failed"] == 1
        assert aggs.by_status["running"] == 1
        assert aggs.by_status["pending"] == 1

    def test_aggregates_by_type(self, sample_jobs: list[JobInfo]) -> None:
        """Should aggregate counts by type."""
        aggs = _compute_aggregations(sample_jobs)
        assert aggs.by_type["export"] == 2
        assert aggs.by_type["cleanup"] == 1
        assert aggs.by_type["backup"] == 1

    def test_empty_list(self) -> None:
        """Should handle empty list."""
        aggs = _compute_aggregations([])
        assert aggs.by_status == {}
        assert aggs.by_type == {}


class TestGetSortKey:
    """Tests for _get_sort_key helper."""

    def test_sort_by_created_at(self, sample_jobs: list[JobInfo]) -> None:
        """Should get created_at for sorting."""
        key = _get_sort_key(sample_jobs[0], JobSortField.CREATED_AT)
        assert key == sample_jobs[0]["created_at"]

    def test_sort_by_progress(self, sample_jobs: list[JobInfo]) -> None:
        """Should get progress for sorting."""
        key = _get_sort_key(sample_jobs[0], JobSortField.PROGRESS)
        assert key == 100

    def test_sort_by_job_type(self, sample_jobs: list[JobInfo]) -> None:
        """Should get job_type for sorting."""
        key = _get_sort_key(sample_jobs[0], JobSortField.JOB_TYPE)
        assert key == "export"

    def test_sort_by_started_at_none(self, sample_jobs: list[JobInfo]) -> None:
        """Should handle None started_at."""
        key = _get_sort_key(sample_jobs[3], JobSortField.STARTED_AT)
        assert key == ""


class TestSearchJobs:
    """Tests for search_jobs function."""

    @pytest.mark.anyio
    async def test_basic_search(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        """Should return jobs matching search criteria."""
        mock_job_tracker.get_all_jobs.return_value = sample_jobs

        jobs, total = await search_jobs(
            job_tracker=mock_job_tracker,
            statuses=["completed"],
        )

        assert total == 1
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "job-1"

    @pytest.mark.anyio
    async def test_pagination(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        """Should apply pagination."""
        mock_job_tracker.get_all_jobs.return_value = sample_jobs

        jobs, total = await search_jobs(
            job_tracker=mock_job_tracker,
            limit=2,
            offset=0,
        )

        assert total == 4
        assert len(jobs) == 2

    @pytest.mark.anyio
    async def test_sorting_desc(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        """Should sort descending by default."""
        mock_job_tracker.get_all_jobs.return_value = sample_jobs

        jobs, _ = await search_jobs(
            job_tracker=mock_job_tracker,
            sort_by="created_at",
            sort_order="desc",
        )

        # Most recent first (job-4 created 10 minutes ago)
        assert jobs[0]["job_id"] == "job-4"

    @pytest.mark.anyio
    async def test_sorting_asc(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        """Should sort ascending when specified."""
        mock_job_tracker.get_all_jobs.return_value = sample_jobs

        jobs, _ = await search_jobs(
            job_tracker=mock_job_tracker,
            sort_by="created_at",
            sort_order="asc",
        )

        # Oldest first (job-1 created 2 hours ago)
        assert jobs[0]["job_id"] == "job-1"


class TestSearchJobsWithAggregations:
    """Tests for search_jobs_with_aggregations function."""

    @pytest.mark.anyio
    async def test_returns_aggregations(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        """Should return aggregations along with jobs."""
        mock_job_tracker.get_all_jobs.return_value = sample_jobs

        result = await search_jobs_with_aggregations(
            job_tracker=mock_job_tracker,
        )

        assert isinstance(result, JobSearchResult)
        assert result.total == 4
        assert len(result.jobs) == 4
        assert result.aggregations.by_status["completed"] == 1
        assert result.aggregations.by_type["export"] == 2

    @pytest.mark.anyio
    async def test_aggregations_on_filtered_results(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        """Aggregations should be computed on filtered results."""
        mock_job_tracker.get_all_jobs.return_value = sample_jobs

        result = await search_jobs_with_aggregations(
            job_tracker=mock_job_tracker,
            job_types=["export"],
        )

        assert result.total == 2
        assert result.aggregations.by_type["export"] == 2
        # Only export jobs, so only their statuses appear
        assert "cleanup" not in result.aggregations.by_type


class TestJobSearchService:
    """Tests for JobSearchService class."""

    @pytest.mark.anyio
    async def test_search_method(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        """Should delegate to search_jobs_with_aggregations."""
        mock_job_tracker.get_all_jobs.return_value = sample_jobs

        service = JobSearchService(job_tracker=mock_job_tracker)
        result = await service.search(
            query="export",
            statuses=["completed", "running"],
        )

        assert isinstance(result, JobSearchResult)
        assert result.total == 2  # 2 export jobs


class TestJobSortField:
    """Tests for JobSortField enum."""

    def test_field_values(self) -> None:
        """Should have expected field values."""
        assert JobSortField.CREATED_AT == "created_at"
        assert JobSortField.STARTED_AT == "started_at"
        assert JobSortField.COMPLETED_AT == "completed_at"
        assert JobSortField.PROGRESS == "progress"
        assert JobSortField.JOB_TYPE == "job_type"
        assert JobSortField.STATUS == "status"


class TestSortOrder:
    """Tests for SortOrder enum."""

    def test_order_values(self) -> None:
        """Should have expected order values."""
        assert SortOrder.ASC == "asc"
        assert SortOrder.DESC == "desc"


class TestJobSearchFilters:
    """Tests for JobSearchFilters dataclass."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        filters = JobSearchFilters()
        assert filters.query is None
        assert filters.statuses == []
        assert filters.job_types == []
        assert filters.queue is None
        assert filters.created_after is None
        assert filters.created_before is None
        assert filters.completed_after is None
        assert filters.completed_before is None
        assert filters.has_error is None
        assert filters.min_duration is None
        assert filters.max_duration is None


class TestJobAggregations:
    """Tests for JobAggregations dataclass."""

    def test_to_dict(self) -> None:
        """Should serialize to dictionary."""
        aggs = JobAggregations(
            by_status={"completed": 10, "failed": 5},
            by_type={"export": 8, "cleanup": 7},
        )
        result = aggs.to_dict()
        assert result["by_status"] == {"completed": 10, "failed": 5}
        assert result["by_type"] == {"export": 8, "cleanup": 7}


class TestJobSearchResult:
    """Tests for JobSearchResult dataclass."""

    def test_to_dict(self, sample_jobs: list[JobInfo]) -> None:
        """Should serialize to dictionary."""
        result = JobSearchResult(
            jobs=sample_jobs[:2],
            total=2,
            aggregations=JobAggregations(
                by_status={"completed": 1, "failed": 1},
                by_type={"export": 1, "cleanup": 1},
            ),
        )
        data = result.to_dict()
        assert data["total"] == 2
        assert len(data["jobs"]) == 2
        assert data["aggregations"]["by_status"]["completed"] == 1
