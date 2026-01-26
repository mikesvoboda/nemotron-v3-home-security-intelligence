"""Unit tests for ExportJob model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- ExportJobStatus and ExportType enums
- Property-based tests for field values
- Compliance fields (NEM-3669): retention_days, legal_hold, compliance_metadata

Tests use direct model instantiation (not database) to verify model structure.
"""

from datetime import timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.core.time_utils import utc_now
from backend.models.export_job import (
    DEFAULT_EXPORT_RETENTION_DAYS,
    ExportJob,
    ExportJobStatus,
    ExportType,
)

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for export statuses
export_statuses = st.sampled_from(list(ExportJobStatus))

# Strategy for export types
export_types = st.sampled_from(list(ExportType))

# Strategy for progress percentages (0-100)
progress_values = st.integers(min_value=0, max_value=100)

# Strategy for processed items (non-negative)
item_counts = st.integers(min_value=0, max_value=1000000)

# Strategy for retention days (positive)
retention_days_values = st.integers(min_value=1, max_value=365)

# Strategy for compliance metadata
compliance_metadata_strategy = st.fixed_dictionaries(
    {
        "requestor": st.emails(),
        "reason": st.text(min_size=1, max_size=200),
    },
    optional={"authorization": st.text(min_size=1, max_size=100)},
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_export_job():
    """Create a sample export job for testing with explicit defaults."""
    return ExportJob(
        export_type=ExportType.EVENTS,
        export_format="csv",
        status=ExportJobStatus.PENDING,
        progress_percent=0,
        processed_items=0,
        download_count=0,
        sensitivity_acknowledged=False,
        legal_hold=False,
    )


@pytest.fixture
def completed_export_job():
    """Create a completed export job."""
    now = utc_now()
    return ExportJob(
        export_type=ExportType.EVENTS,
        export_format="csv",
        status=ExportJobStatus.COMPLETED,
        total_items=100,
        processed_items=100,
        progress_percent=100,
        started_at=now - timedelta(minutes=5),
        completed_at=now,
        output_path="/exports/events_20250125.csv",
        output_size_bytes=12345,
    )


@pytest.fixture
def compliance_export_job():
    """Create an export job with compliance fields (NEM-3669)."""
    return ExportJob(
        export_type=ExportType.FULL_BACKUP,
        export_format="zip",
        retention_days=90,
        legal_hold=True,
        compliance_metadata={
            "requestor": "admin@example.com",
            "reason": "Annual audit compliance",
            "authorization": "AUTH-2025-001",
        },
    )


# =============================================================================
# ExportJobStatus Enum Tests
# =============================================================================


class TestExportJobStatusEnum:
    """Tests for the ExportJobStatus enum."""

    def test_status_values(self):
        """Test that all expected status values exist."""
        assert ExportJobStatus.PENDING.value == "pending"
        assert ExportJobStatus.RUNNING.value == "running"
        assert ExportJobStatus.COMPLETED.value == "completed"
        assert ExportJobStatus.FAILED.value == "failed"

    def test_status_count(self):
        """Test that there are exactly 4 status values."""
        assert len(ExportJobStatus) == 4

    def test_status_from_string(self):
        """Test creating status from string value."""
        assert ExportJobStatus("pending") == ExportJobStatus.PENDING
        assert ExportJobStatus("running") == ExportJobStatus.RUNNING
        assert ExportJobStatus("completed") == ExportJobStatus.COMPLETED
        assert ExportJobStatus("failed") == ExportJobStatus.FAILED


# =============================================================================
# ExportType Enum Tests
# =============================================================================


class TestExportTypeEnum:
    """Tests for the ExportType enum."""

    def test_type_values(self):
        """Test that all expected type values exist."""
        assert ExportType.EVENTS == "events"
        assert ExportType.ALERTS == "alerts"
        assert ExportType.FULL_BACKUP == "full_backup"

    def test_type_count(self):
        """Test that there are exactly 3 type values."""
        assert len(ExportType) == 3


# =============================================================================
# ExportJob Model Tests
# =============================================================================


class TestExportJobModel:
    """Tests for the ExportJob model."""

    def test_create_export_job_with_all_fields(self):
        """Test creating an export job with all fields explicitly set.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        Tests validate field assignments, not column defaults.
        """
        job = ExportJob(
            export_type=ExportType.EVENTS,
            export_format="csv",
            status=ExportJobStatus.PENDING,
            progress_percent=0,
            processed_items=0,
            download_count=0,
            sensitivity_acknowledged=False,
            legal_hold=False,
        )

        assert job.export_type == ExportType.EVENTS
        assert job.export_format == "csv"
        assert job.status == ExportJobStatus.PENDING
        assert job.progress_percent == 0
        assert job.processed_items == 0
        assert job.total_items is None
        assert job.download_count == 0
        assert job.sensitivity_acknowledged is False
        assert job.legal_hold is False

    def test_status_can_be_set(self, sample_export_job):
        """Test that status is correctly set."""
        assert sample_export_job.status == ExportJobStatus.PENDING

    def test_progress_can_be_set(self, sample_export_job):
        """Test that progress fields are correctly set."""
        assert sample_export_job.progress_percent == 0
        assert sample_export_job.processed_items == 0

    def test_download_count_can_be_set(self, sample_export_job):
        """Test that download count is correctly set."""
        assert sample_export_job.download_count == 0

    def test_sensitivity_acknowledged_can_be_set(self, sample_export_job):
        """Test that sensitivity_acknowledged is correctly set."""
        assert sample_export_job.sensitivity_acknowledged is False

    def test_export_formats(self):
        """Test various export formats."""
        for fmt in ["csv", "json", "zip", "excel"]:
            job = ExportJob(export_type=ExportType.EVENTS, export_format=fmt)
            assert job.export_format == fmt


# =============================================================================
# Compliance Fields Tests (NEM-3669)
# =============================================================================


class TestComplianceFields:
    """Tests for the compliance fields added in NEM-3669."""

    def test_retention_days_not_set_is_none(self, sample_export_job):
        """Test that retention_days is None when not explicitly set."""
        assert sample_export_job.retention_days is None

    def test_legal_hold_can_be_set_false(self, sample_export_job):
        """Test that legal_hold can be explicitly set to False."""
        assert sample_export_job.legal_hold is False

    def test_compliance_metadata_not_set_is_none(self, sample_export_job):
        """Test that compliance_metadata is None when not explicitly set."""
        assert sample_export_job.compliance_metadata is None

    def test_retention_days_can_be_set(self):
        """Test that retention_days can be set."""
        job = ExportJob(
            export_type=ExportType.EVENTS,
            export_format="csv",
            retention_days=30,
        )
        assert job.retention_days == 30

    def test_legal_hold_can_be_set_true(self):
        """Test that legal_hold can be set to True."""
        job = ExportJob(
            export_type=ExportType.EVENTS,
            export_format="csv",
            legal_hold=True,
        )
        assert job.legal_hold is True

    def test_compliance_metadata_can_be_set(self, compliance_export_job):
        """Test that compliance_metadata can be set with a dict."""
        assert compliance_export_job.compliance_metadata is not None
        assert compliance_export_job.compliance_metadata["requestor"] == "admin@example.com"
        assert compliance_export_job.compliance_metadata["reason"] == "Annual audit compliance"
        assert compliance_export_job.compliance_metadata["authorization"] == "AUTH-2025-001"

    def test_compliance_fields_combination(self, compliance_export_job):
        """Test that all compliance fields work together."""
        assert compliance_export_job.retention_days == 90
        assert compliance_export_job.legal_hold is True
        assert compliance_export_job.compliance_metadata is not None

    @given(days=retention_days_values)
    @settings(max_examples=25)
    def test_retention_days_positive_values(self, days):
        """Property test: retention_days accepts positive values."""
        job = ExportJob(
            export_type=ExportType.EVENTS,
            export_format="csv",
            retention_days=days,
        )
        assert job.retention_days == days
        assert job.retention_days > 0


# =============================================================================
# Property Tests (is_complete, is_running, duration_seconds)
# =============================================================================


class TestExportJobProperties:
    """Tests for ExportJob properties."""

    def test_is_complete_when_completed(self, completed_export_job):
        """Test is_complete returns True for COMPLETED status."""
        assert completed_export_job.is_complete is True

    def test_is_complete_when_failed(self):
        """Test is_complete returns True for FAILED status."""
        job = ExportJob(
            export_type=ExportType.EVENTS,
            export_format="csv",
            status=ExportJobStatus.FAILED,
            error_message="Test error",
        )
        assert job.is_complete is True

    def test_is_complete_when_pending(self, sample_export_job):
        """Test is_complete returns False for PENDING status."""
        assert sample_export_job.is_complete is False

    def test_is_complete_when_running(self):
        """Test is_complete returns False for RUNNING status."""
        job = ExportJob(
            export_type=ExportType.EVENTS,
            export_format="csv",
            status=ExportJobStatus.RUNNING,
        )
        assert job.is_complete is False

    def test_is_running_when_running(self):
        """Test is_running returns True for RUNNING status."""
        job = ExportJob(
            export_type=ExportType.EVENTS,
            export_format="csv",
            status=ExportJobStatus.RUNNING,
        )
        assert job.is_running is True

    def test_is_running_when_pending(self, sample_export_job):
        """Test is_running returns False for PENDING status."""
        assert sample_export_job.is_running is False

    def test_duration_seconds_when_not_started(self, sample_export_job):
        """Test duration_seconds returns None when job hasn't started."""
        assert sample_export_job.duration_seconds is None

    def test_duration_seconds_when_completed(self, completed_export_job):
        """Test duration_seconds returns correct value for completed job."""
        duration = completed_export_job.duration_seconds
        assert duration is not None
        # Should be approximately 5 minutes (300 seconds)
        assert 290 <= duration <= 310


# =============================================================================
# String Representation Tests
# =============================================================================


class TestExportJobRepr:
    """Tests for ExportJob __repr__ method."""

    def test_repr_format(self):
        """Test that __repr__ returns expected format."""
        job = ExportJob(
            export_type=ExportType.EVENTS,
            export_format="csv",
            status=ExportJobStatus.PENDING,
            progress_percent=0,
        )
        job.id = "test-job-id"
        repr_str = repr(job)

        assert "ExportJob" in repr_str
        assert "test-job-id" in repr_str
        assert "pending" in repr_str
        assert "events" in repr_str
        assert "progress=0%" in repr_str

    def test_repr_with_progress(self):
        """Test repr shows progress percentage."""
        job = ExportJob(
            export_type=ExportType.EVENTS,
            export_format="csv",
            status=ExportJobStatus.RUNNING,
            progress_percent=50,
        )
        job.id = "running-job"
        repr_str = repr(job)

        assert "progress=50%" in repr_str


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestExportJobPropertyBased:
    """Property-based tests for ExportJob model."""

    @given(status=export_statuses)
    @settings(max_examples=10)
    def test_any_status_is_valid(self, status):
        """Property test: any ExportJobStatus is valid for the model."""
        job = ExportJob(
            export_type=ExportType.EVENTS,
            export_format="csv",
            status=status,
        )
        assert job.status == status

    @given(export_type=export_types)
    @settings(max_examples=10)
    def test_any_export_type_is_valid(self, export_type):
        """Property test: any ExportType is valid for the model."""
        job = ExportJob(
            export_type=export_type,
            export_format="csv",
        )
        assert job.export_type == export_type

    @given(progress=progress_values)
    @settings(max_examples=25)
    def test_progress_in_valid_range(self, progress):
        """Property test: progress_percent accepts values 0-100."""
        job = ExportJob(
            export_type=ExportType.EVENTS,
            export_format="csv",
            progress_percent=progress,
        )
        assert job.progress_percent == progress
        assert 0 <= job.progress_percent <= 100

    @given(items=item_counts)
    @settings(max_examples=25)
    def test_processed_items_non_negative(self, items):
        """Property test: processed_items accepts non-negative values."""
        job = ExportJob(
            export_type=ExportType.EVENTS,
            export_format="csv",
            processed_items=items,
        )
        assert job.processed_items == items
        assert job.processed_items >= 0


# =============================================================================
# Default Retention Days Constant Test
# =============================================================================


class TestDefaultRetentionDays:
    """Tests for the DEFAULT_EXPORT_RETENTION_DAYS constant."""

    def test_default_export_retention_days_value(self):
        """Test that DEFAULT_EXPORT_RETENTION_DAYS is 7."""
        assert DEFAULT_EXPORT_RETENTION_DAYS == 7
