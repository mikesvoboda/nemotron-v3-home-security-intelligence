"""Unit tests for alerts API schemas.

Tests cover:
- AlertRuleSchedule validation (days, times, timezone)
- Time format validation
- Invalid day detection
- Edge cases for schedule validation

NEM-1295: Add ScheduleSelector validation for overlapping schedules and invalid time ranges
"""

import pytest
from pydantic import ValidationError

from backend.api.schemas.alerts import (
    VALID_DAYS,
    AlertRuleSchedule,
    validate_time_format,
)

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# validate_time_format Tests
# =============================================================================


class TestValidateTimeFormat:
    """Tests for validate_time_format function."""

    def test_valid_time_format_midnight(self):
        """Test valid time at midnight."""
        hours, minutes = validate_time_format("00:00")
        assert hours == 0
        assert minutes == 0

    def test_valid_time_format_end_of_day(self):
        """Test valid time at end of day."""
        hours, minutes = validate_time_format("23:59")
        assert hours == 23
        assert minutes == 59

    def test_valid_time_format_noon(self):
        """Test valid time at noon."""
        hours, minutes = validate_time_format("12:00")
        assert hours == 12
        assert minutes == 0

    def test_valid_time_format_morning(self):
        """Test valid morning time."""
        hours, minutes = validate_time_format("09:30")
        assert hours == 9
        assert minutes == 30

    def test_valid_time_format_evening(self):
        """Test valid evening time."""
        hours, minutes = validate_time_format("22:00")
        assert hours == 22
        assert minutes == 0

    def test_invalid_hours_24(self):
        """Test that 24:00 is invalid."""
        with pytest.raises(ValueError, match=r"Invalid hours '24'.*Hours must be 00-23"):
            validate_time_format("24:00")

    def test_invalid_hours_99(self):
        """Test that 99 hours is invalid."""
        with pytest.raises(ValueError, match=r"Invalid hours '99'.*Hours must be 00-23"):
            validate_time_format("99:00")

    def test_invalid_minutes_60(self):
        """Test that 60 minutes is invalid."""
        with pytest.raises(ValueError, match=r"Invalid minutes '60'.*Minutes must be 00-59"):
            validate_time_format("12:60")

    def test_invalid_minutes_99(self):
        """Test that 99 minutes is invalid."""
        with pytest.raises(ValueError, match=r"Invalid minutes '99'.*Minutes must be 00-59"):
            validate_time_format("12:99")

    def test_invalid_format_no_colon(self):
        """Test that time without colon is invalid."""
        with pytest.raises(ValueError, match=r"Invalid time format.*Expected HH:MM"):
            validate_time_format("1200")

    def test_invalid_format_single_digit_hours(self):
        """Test that single digit hours are invalid."""
        with pytest.raises(ValueError, match=r"Invalid time format.*Expected HH:MM"):
            validate_time_format("9:00")

    def test_invalid_format_single_digit_minutes(self):
        """Test that single digit minutes are invalid."""
        with pytest.raises(ValueError, match=r"Invalid time format.*Expected HH:MM"):
            validate_time_format("09:0")

    def test_invalid_format_non_numeric_hours(self):
        """Test that non-numeric hours are invalid."""
        with pytest.raises(ValueError, match="Hours and minutes must be numeric"):
            validate_time_format("ab:00")

    def test_invalid_format_non_numeric_minutes(self):
        """Test that non-numeric minutes are invalid."""
        with pytest.raises(ValueError, match="Hours and minutes must be numeric"):
            validate_time_format("12:cd")

    def test_invalid_format_empty_string(self):
        """Test that empty string is invalid."""
        with pytest.raises(ValueError, match="Invalid time format"):
            validate_time_format("")

    def test_invalid_format_too_long(self):
        """Test that time string too long is invalid."""
        with pytest.raises(ValueError, match="Invalid time format"):
            validate_time_format("12:00:00")


# =============================================================================
# AlertRuleSchedule Days Validation Tests
# =============================================================================


class TestAlertRuleScheduleDaysValidation:
    """Tests for AlertRuleSchedule days field validation."""

    def test_valid_single_day(self):
        """Test valid single day."""
        schedule = AlertRuleSchedule(days=["monday"])
        assert schedule.days == ["monday"]

    def test_valid_all_weekdays(self):
        """Test valid weekdays."""
        schedule = AlertRuleSchedule(days=["monday", "tuesday", "wednesday", "thursday", "friday"])
        assert len(schedule.days) == 5
        assert "monday" in schedule.days
        assert "friday" in schedule.days

    def test_valid_all_days(self):
        """Test valid all days of week."""
        schedule = AlertRuleSchedule(
            days=["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        )
        assert len(schedule.days) == 7

    def test_valid_weekend(self):
        """Test valid weekend days."""
        schedule = AlertRuleSchedule(days=["saturday", "sunday"])
        assert schedule.days == ["saturday", "sunday"]

    def test_days_none_means_all_days(self):
        """Test that None means all days."""
        schedule = AlertRuleSchedule(days=None)
        assert schedule.days is None

    def test_days_empty_list_allowed(self):
        """Test that empty list is allowed (means all days)."""
        schedule = AlertRuleSchedule(days=[])
        assert schedule.days == []

    def test_invalid_day_name(self):
        """Test invalid day name raises error."""
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleSchedule(days=["monday", "funday"])

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "Invalid day(s): funday" in str(errors[0]["msg"])

    def test_multiple_invalid_days(self):
        """Test multiple invalid day names."""
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleSchedule(days=["moonday", "sunnight"])

        errors = exc_info.value.errors()
        assert "Invalid day(s): moonday, sunnight" in str(errors[0]["msg"])

    def test_case_insensitive_days(self):
        """Test that days are case insensitive."""
        schedule = AlertRuleSchedule(days=["Monday", "TUESDAY", "Wednesday"])
        # Days should be normalized to lowercase
        assert schedule.days == ["monday", "tuesday", "wednesday"]

    def test_mixed_case_days(self):
        """Test mixed case days are normalized."""
        schedule = AlertRuleSchedule(days=["MoNdAy", "TuEsDaY"])
        assert schedule.days == ["monday", "tuesday"]


# =============================================================================
# AlertRuleSchedule Time Validation Tests
# =============================================================================


class TestAlertRuleScheduleTimeValidation:
    """Tests for AlertRuleSchedule time field validation."""

    def test_valid_daytime_schedule(self):
        """Test valid daytime schedule."""
        schedule = AlertRuleSchedule(start_time="09:00", end_time="17:00")
        assert schedule.start_time == "09:00"
        assert schedule.end_time == "17:00"

    def test_valid_overnight_schedule(self):
        """Test valid overnight schedule (start > end)."""
        schedule = AlertRuleSchedule(start_time="22:00", end_time="06:00")
        assert schedule.start_time == "22:00"
        assert schedule.end_time == "06:00"

    def test_valid_all_day_schedule(self):
        """Test valid all day schedule."""
        schedule = AlertRuleSchedule(start_time="00:00", end_time="23:59")
        assert schedule.start_time == "00:00"
        assert schedule.end_time == "23:59"

    def test_start_time_none_allowed(self):
        """Test that start_time None is allowed."""
        schedule = AlertRuleSchedule(start_time=None, end_time="17:00")
        assert schedule.start_time is None

    def test_end_time_none_allowed(self):
        """Test that end_time None is allowed."""
        schedule = AlertRuleSchedule(start_time="09:00", end_time=None)
        assert schedule.end_time is None

    def test_both_times_none_allowed(self):
        """Test that both times None is allowed (always active)."""
        schedule = AlertRuleSchedule(start_time=None, end_time=None)
        assert schedule.start_time is None
        assert schedule.end_time is None

    def test_invalid_start_time_hours(self):
        """Test invalid start time hours."""
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleSchedule(start_time="25:00", end_time="17:00")

        # Pattern validation may fire first, but the error should be caught
        errors = exc_info.value.errors()
        assert len(errors) >= 1

    def test_invalid_end_time_hours(self):
        """Test invalid end time hours."""
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleSchedule(start_time="09:00", end_time="24:00")

        errors = exc_info.value.errors()
        assert len(errors) >= 1

    def test_invalid_start_time_minutes(self):
        """Test invalid start time minutes."""
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleSchedule(start_time="09:60", end_time="17:00")

        errors = exc_info.value.errors()
        assert len(errors) >= 1

    def test_invalid_end_time_minutes(self):
        """Test invalid end time minutes."""
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleSchedule(start_time="09:00", end_time="17:60")

        errors = exc_info.value.errors()
        assert len(errors) >= 1

    def test_invalid_start_time_format(self):
        """Test invalid start time format."""
        with pytest.raises(ValidationError):
            AlertRuleSchedule(start_time="9:00", end_time="17:00")

    def test_invalid_end_time_format(self):
        """Test invalid end time format."""
        with pytest.raises(ValidationError):
            AlertRuleSchedule(start_time="09:00", end_time="5pm")


# =============================================================================
# AlertRuleSchedule Complete Validation Tests
# =============================================================================


class TestAlertRuleScheduleCompleteValidation:
    """Tests for complete AlertRuleSchedule validation."""

    def test_complete_valid_schedule(self):
        """Test complete valid schedule."""
        schedule = AlertRuleSchedule(
            days=["monday", "tuesday", "wednesday", "thursday", "friday"],
            start_time="22:00",
            end_time="06:00",
            timezone="America/New_York",
        )
        assert schedule.days == ["monday", "tuesday", "wednesday", "thursday", "friday"]
        assert schedule.start_time == "22:00"
        assert schedule.end_time == "06:00"
        assert schedule.timezone == "America/New_York"

    def test_minimal_schedule(self):
        """Test minimal schedule (all defaults)."""
        schedule = AlertRuleSchedule()
        assert schedule.days is None
        assert schedule.start_time is None
        assert schedule.end_time is None
        assert schedule.timezone == "UTC"

    def test_default_timezone(self):
        """Test default timezone is UTC."""
        schedule = AlertRuleSchedule()
        assert schedule.timezone == "UTC"

    def test_custom_timezone(self):
        """Test custom timezone."""
        schedule = AlertRuleSchedule(timezone="America/Los_Angeles")
        assert schedule.timezone == "America/Los_Angeles"

    def test_timezone_with_days_and_times(self):
        """Test complete schedule with timezone."""
        schedule = AlertRuleSchedule(
            days=["saturday", "sunday"],
            start_time="00:00",
            end_time="23:59",
            timezone="Europe/London",
        )
        assert schedule.days == ["saturday", "sunday"]
        assert schedule.timezone == "Europe/London"


# =============================================================================
# VALID_DAYS Constant Tests
# =============================================================================


class TestValidDaysConstant:
    """Tests for VALID_DAYS constant."""

    def test_valid_days_count(self):
        """Test VALID_DAYS has exactly 7 days."""
        assert len(VALID_DAYS) == 7

    def test_valid_days_contains_weekdays(self):
        """Test VALID_DAYS contains all weekdays."""
        weekdays = {"monday", "tuesday", "wednesday", "thursday", "friday"}
        assert weekdays.issubset(VALID_DAYS)

    def test_valid_days_contains_weekend(self):
        """Test VALID_DAYS contains weekend days."""
        weekend = {"saturday", "sunday"}
        assert weekend.issubset(VALID_DAYS)

    def test_valid_days_is_frozenset(self):
        """Test VALID_DAYS is immutable frozenset."""
        assert isinstance(VALID_DAYS, frozenset)
