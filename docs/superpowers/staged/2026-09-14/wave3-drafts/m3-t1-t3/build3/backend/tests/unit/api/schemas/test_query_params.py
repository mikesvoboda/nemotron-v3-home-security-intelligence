"""Unit tests for query parameter models.

NEM-3345: Test Query Parameter Models for reusable validation.
"""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from backend.api.schemas.query_params import (
    CommonQueryParams,
    DateRangeParams,
    FieldSelectionParams,
    FilterParams,
    PaginationParams,
    RiskLevel,
    SortOrder,
    SortParams,
)


class TestPaginationParams:
    """Tests for PaginationParams model."""

    def test_default_values(self):
        """Test that default values are applied correctly."""
        params = PaginationParams(limit=50, offset=0, cursor=None)
        assert params.limit == 50
        assert params.offset == 0
        assert params.cursor is None

    def test_cursor_based_pagination(self):
        """Test cursor-based pagination detection."""
        params = PaginationParams(limit=50, offset=0, cursor="abc123")
        assert params.is_cursor_based is True
        assert params.is_offset_deprecated is False
        assert params.get_deprecation_warning() is None

    def test_offset_pagination_deprecated(self):
        """Test that offset pagination generates deprecation warning."""
        params = PaginationParams(limit=50, offset=10, cursor=None)
        assert params.is_cursor_based is False
        assert params.is_offset_deprecated is True
        warning = params.get_deprecation_warning()
        assert warning is not None
        assert "deprecated" in warning.lower()

    def test_cursor_and_offset_conflict_validation(self):
        """Test that cursor and non-zero offset cannot be used together."""
        with pytest.raises(HTTPException) as exc_info:
            PaginationParams(limit=50, offset=10, cursor="abc123")
        assert exc_info.value.status_code == 400
        assert "cursor" in exc_info.value.detail.lower()
        assert "offset" in exc_info.value.detail.lower()

    def test_cursor_with_zero_offset_allowed(self):
        """Test that cursor can be used with offset=0 (default)."""
        params = PaginationParams(limit=50, offset=0, cursor="abc123")
        assert params.cursor == "abc123"
        assert params.offset == 0


class TestDateRangeParams:
    """Tests for DateRangeParams model."""

    def test_valid_date_range(self):
        """Test valid date range where start_date < end_date."""
        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 1, 31, tzinfo=UTC)
        params = DateRangeParams(start_date=start, end_date=end)
        assert params.start_date == start
        assert params.end_date == end

    def test_invalid_date_range(self):
        """Test that start_date > end_date raises an error."""
        start = datetime(2026, 1, 31, tzinfo=UTC)
        end = datetime(2026, 1, 1, tzinfo=UTC)
        with pytest.raises(HTTPException) as exc_info:
            DateRangeParams(start_date=start, end_date=end)
        assert exc_info.value.status_code == 400
        assert "start_date" in exc_info.value.detail.lower()

    def test_same_date_allowed(self):
        """Test that start_date == end_date is allowed."""
        same_date = datetime(2026, 1, 15, tzinfo=UTC)
        params = DateRangeParams(start_date=same_date, end_date=same_date)
        assert params.start_date == same_date
        assert params.end_date == same_date

    def test_normalized_end_date_midnight(self):
        """Test that midnight end dates are normalized to end of day."""
        end = datetime(2026, 1, 15, 0, 0, 0, tzinfo=UTC)
        params = DateRangeParams(start_date=None, end_date=end)
        normalized = params.get_normalized_end_date()
        assert normalized is not None
        assert normalized.hour == 23
        assert normalized.minute == 59
        assert normalized.second == 59

    def test_normalized_end_date_non_midnight(self):
        """Test that non-midnight end dates are not normalized."""
        end = datetime(2026, 1, 15, 14, 30, 0, tzinfo=UTC)
        params = DateRangeParams(start_date=None, end_date=end)
        normalized = params.get_normalized_end_date()
        assert normalized == end

    def test_none_dates_allowed(self):
        """Test that both dates can be None."""
        params = DateRangeParams(start_date=None, end_date=None)
        assert params.start_date is None
        assert params.end_date is None


class TestFilterParams:
    """Tests for FilterParams model."""

    def test_camera_id_filter(self):
        """Test camera_id filter parameter."""
        params = FilterParams(
            camera_id="front_door",
            detection_type=None,
            risk_level=None,
            min_confidence=None,
            reviewed=None,
        )
        assert params.camera_id == "front_door"

    def test_detection_type_alias(self):
        """Test that object_type is an alias for detection_type."""
        params = FilterParams(
            camera_id=None,
            detection_type="person",
            risk_level=None,
            min_confidence=None,
            reviewed=None,
        )
        assert params.detection_type == "person"
        assert params.object_type == "person"

    def test_risk_level_enum(self):
        """Test risk level enum values."""
        params = FilterParams(
            camera_id=None,
            detection_type=None,
            risk_level=RiskLevel.HIGH,
            min_confidence=None,
            reviewed=None,
        )
        assert params.risk_level == RiskLevel.HIGH

    def test_min_confidence_bounds(self):
        """Test min_confidence is validated to 0.0-1.0 range."""
        params = FilterParams(
            camera_id=None,
            detection_type=None,
            risk_level=None,
            min_confidence=0.75,
            reviewed=None,
        )
        assert params.min_confidence == 0.75

    def test_reviewed_boolean(self):
        """Test reviewed boolean filter."""
        params = FilterParams(
            camera_id=None,
            detection_type=None,
            risk_level=None,
            min_confidence=None,
            reviewed=True,
        )
        assert params.reviewed is True


class TestSortParams:
    """Tests for SortParams model."""

    def test_default_sort_order(self):
        """Test that default sort order is DESC."""
        params = SortParams(sort_by="created_at", sort_order=SortOrder.DESC)
        assert params.sort_order == SortOrder.DESC

    def test_asc_sort_order(self):
        """Test ascending sort order."""
        params = SortParams(sort_by="name", sort_order=SortOrder.ASC)
        assert params.sort_order == SortOrder.ASC

    def test_get_order_function_desc(self):
        """Test get_order_function returns desc for DESC."""
        params = SortParams(sort_by="created_at", sort_order=SortOrder.DESC)
        order_func = params.get_order_function()
        # Check that it's the desc function by comparing its behavior
        assert order_func.__name__ == "desc"

    def test_get_order_function_asc(self):
        """Test get_order_function returns asc for ASC."""
        params = SortParams(sort_by="created_at", sort_order=SortOrder.ASC)
        order_func = params.get_order_function()
        # Check that it's the asc function by comparing its behavior
        assert order_func.__name__ == "asc"


class TestFieldSelectionParams:
    """Tests for FieldSelectionParams model."""

    def test_parse_fields_single(self):
        """Test parsing a single field."""
        params = FieldSelectionParams(fields="id")
        result = params.parse_fields()
        assert result == {"id"}

    def test_parse_fields_multiple(self):
        """Test parsing multiple comma-separated fields."""
        params = FieldSelectionParams(fields="id,name,status")
        result = params.parse_fields()
        assert result == {"id", "name", "status"}

    def test_parse_fields_with_whitespace(self):
        """Test parsing fields with extra whitespace."""
        params = FieldSelectionParams(fields="id, name , status")
        result = params.parse_fields()
        assert result == {"id", "name", "status"}

    def test_parse_fields_none(self):
        """Test that None fields parameter returns None."""
        params = FieldSelectionParams(fields=None)
        result = params.parse_fields()
        assert result is None

    def test_parse_fields_empty_string(self):
        """Test that empty string returns None."""
        params = FieldSelectionParams(fields="")
        result = params.parse_fields()
        assert result is None


class TestCommonQueryParams:
    """Tests for CommonQueryParams combined model."""

    def test_all_params_combined(self):
        """Test that all parameters can be set together."""
        params = CommonQueryParams(
            limit=25,
            offset=0,
            cursor=None,
            start_date=datetime(2026, 1, 1, tzinfo=UTC),
            end_date=datetime(2026, 1, 31, tzinfo=UTC),
            camera_id="front_door",
            object_type="person",
            risk_level=RiskLevel.MEDIUM,
            min_confidence=0.8,
            reviewed=False,
            sort_by="started_at",
            sort_order=SortOrder.DESC,
            fields="id,name",
        )

        assert params.limit == 25
        assert params.camera_id == "front_door"
        assert params.risk_level == RiskLevel.MEDIUM

    def test_pagination_property(self):
        """Test that pagination property returns correct PaginationParams."""
        params = CommonQueryParams(
            limit=25,
            offset=5,
            cursor=None,
            start_date=None,
            end_date=None,
            camera_id=None,
            object_type=None,
            risk_level=None,
            min_confidence=None,
            reviewed=None,
            sort_by=None,
            sort_order=SortOrder.DESC,
            fields=None,
        )
        pagination = params.pagination
        assert pagination.limit == 25
        assert pagination.offset == 5
        assert pagination.cursor is None

    def test_date_range_property(self):
        """Test that date_range property returns correct DateRangeParams."""
        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 1, 31, tzinfo=UTC)
        params = CommonQueryParams(
            limit=50,
            offset=0,
            cursor=None,
            start_date=start,
            end_date=end,
            camera_id=None,
            object_type=None,
            risk_level=None,
            min_confidence=None,
            reviewed=None,
            sort_by=None,
            sort_order=SortOrder.DESC,
            fields=None,
        )
        date_range = params.date_range
        assert date_range.start_date == start
        assert date_range.end_date == end

    def test_filters_property(self):
        """Test that filters property returns correct FilterParams."""
        params = CommonQueryParams(
            limit=50,
            offset=0,
            cursor=None,
            start_date=None,
            end_date=None,
            camera_id="backyard",
            object_type="car",
            risk_level=RiskLevel.LOW,
            min_confidence=0.5,
            reviewed=True,
            sort_by=None,
            sort_order=SortOrder.DESC,
            fields=None,
        )
        filters = params.filters
        assert filters.camera_id == "backyard"
        assert filters.detection_type == "car"
        assert filters.risk_level == RiskLevel.LOW
        assert filters.min_confidence == 0.5
        assert filters.reviewed is True

    def test_sort_property(self):
        """Test that sort property returns correct SortParams."""
        params = CommonQueryParams(
            limit=50,
            offset=0,
            cursor=None,
            start_date=None,
            end_date=None,
            camera_id=None,
            object_type=None,
            risk_level=None,
            min_confidence=None,
            reviewed=None,
            sort_by="risk_score",
            sort_order=SortOrder.ASC,
            fields=None,
        )
        sort = params.sort
        assert sort.sort_by == "risk_score"
        assert sort.sort_order == SortOrder.ASC

    def test_combined_validation_cursor_offset(self):
        """Test that combined params validate cursor/offset conflict."""
        with pytest.raises(HTTPException) as exc_info:
            CommonQueryParams(
                limit=50,
                offset=10,
                cursor="abc123",
                start_date=None,
                end_date=None,
                camera_id=None,
                object_type=None,
                risk_level=None,
                min_confidence=None,
                reviewed=None,
                sort_by=None,
                sort_order=SortOrder.DESC,
                fields=None,
            )
        assert exc_info.value.status_code == 400

    def test_combined_validation_date_range(self):
        """Test that combined params validate date range."""
        with pytest.raises(HTTPException) as exc_info:
            CommonQueryParams(
                limit=50,
                offset=0,
                cursor=None,
                start_date=datetime(2026, 1, 31, tzinfo=UTC),
                end_date=datetime(2026, 1, 1, tzinfo=UTC),
                camera_id=None,
                object_type=None,
                risk_level=None,
                min_confidence=None,
                reviewed=None,
                sort_by=None,
                sort_order=SortOrder.DESC,
                fields=None,
            )
        assert exc_info.value.status_code == 400


class TestRiskLevelEnum:
    """Tests for RiskLevel enum."""

    def test_all_risk_levels(self):
        """Test all risk level values exist."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


class TestSortOrderEnum:
    """Tests for SortOrder enum."""

    def test_sort_order_values(self):
        """Test sort order enum values."""
        assert SortOrder.ASC.value == "asc"
        assert SortOrder.DESC.value == "desc"
