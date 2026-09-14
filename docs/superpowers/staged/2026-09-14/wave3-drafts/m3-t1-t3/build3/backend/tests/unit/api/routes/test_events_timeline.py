"""Unit tests for timeline summary endpoint (NEM-2932).

Tests the /events/timeline-summary endpoint which provides bucketed
event data for the timeline scrubber visualization.
"""

from datetime import UTC, datetime, timedelta

import pytest

from backend.api.schemas.events import (
    TimelineBucketResponse,
    TimelineSummaryResponse,
)


class TestTimelineBucketResponseSchema:
    """Tests for TimelineBucketResponse schema validation."""

    def test_valid_bucket_response(self):
        """Test creating a valid bucket response."""
        bucket = TimelineBucketResponse(
            timestamp=datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC),
            event_count=5,
            max_risk_score=75,
        )
        assert bucket.timestamp == datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        assert bucket.event_count == 5
        assert bucket.max_risk_score == 75

    def test_bucket_with_zero_events(self):
        """Test bucket with zero events is valid."""
        bucket = TimelineBucketResponse(
            timestamp=datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC),
            event_count=0,
            max_risk_score=0,
        )
        assert bucket.event_count == 0
        assert bucket.max_risk_score == 0

    def test_bucket_event_count_must_be_non_negative(self):
        """Test that event_count must be >= 0."""
        with pytest.raises(ValueError):
            TimelineBucketResponse(
                timestamp=datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC),
                event_count=-1,
                max_risk_score=50,
            )

    def test_bucket_risk_score_must_be_in_range(self):
        """Test that max_risk_score must be 0-100."""
        # Test above max
        with pytest.raises(ValueError):
            TimelineBucketResponse(
                timestamp=datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC),
                event_count=5,
                max_risk_score=101,
            )

        # Test below min
        with pytest.raises(ValueError):
            TimelineBucketResponse(
                timestamp=datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC),
                event_count=5,
                max_risk_score=-1,
            )

    def test_bucket_defaults_risk_score_to_zero(self):
        """Test that max_risk_score defaults to 0."""
        bucket = TimelineBucketResponse(
            timestamp=datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC),
            event_count=5,
        )
        assert bucket.max_risk_score == 0


class TestTimelineSummaryResponseSchema:
    """Tests for TimelineSummaryResponse schema validation."""

    def test_valid_summary_response(self):
        """Test creating a valid summary response."""
        now = datetime.now(UTC)
        summary = TimelineSummaryResponse(
            buckets=[
                TimelineBucketResponse(
                    timestamp=now,
                    event_count=5,
                    max_risk_score=75,
                ),
                TimelineBucketResponse(
                    timestamp=now + timedelta(hours=1),
                    event_count=3,
                    max_risk_score=45,
                ),
            ],
            total_events=8,
            start_date=now,
            end_date=now + timedelta(hours=2),
        )
        assert len(summary.buckets) == 2
        assert summary.total_events == 8

    def test_summary_with_empty_buckets(self):
        """Test summary with no buckets is valid."""
        now = datetime.now(UTC)
        summary = TimelineSummaryResponse(
            buckets=[],
            total_events=0,
            start_date=now,
            end_date=now + timedelta(hours=1),
        )
        assert summary.buckets == []
        assert summary.total_events == 0

    def test_summary_total_events_must_be_non_negative(self):
        """Test that total_events must be >= 0."""
        now = datetime.now(UTC)
        with pytest.raises(ValueError):
            TimelineSummaryResponse(
                buckets=[],
                total_events=-1,
                start_date=now,
                end_date=now + timedelta(hours=1),
            )


class TestBucketSizeConstants:
    """Tests for bucket size configuration."""

    def test_bucket_sizes_exist(self):
        """Test that bucket size constants are defined in the routes module."""
        from backend.api.routes.events import BUCKET_SIZES

        assert "hour" in BUCKET_SIZES
        assert "day" in BUCKET_SIZES
        assert "week" in BUCKET_SIZES

    def test_hour_bucket_is_5_minutes(self):
        """Test hour zoom has 5-minute buckets."""
        from backend.api.routes.events import BUCKET_SIZES

        assert BUCKET_SIZES["hour"] == 5 * 60  # 5 minutes in seconds

    def test_day_bucket_is_1_hour(self):
        """Test day zoom has 1-hour buckets."""
        from backend.api.routes.events import BUCKET_SIZES

        assert BUCKET_SIZES["day"] == 60 * 60  # 1 hour in seconds

    def test_week_bucket_is_1_day(self):
        """Test week zoom has 1-day buckets."""
        from backend.api.routes.events import BUCKET_SIZES

        assert BUCKET_SIZES["week"] == 24 * 60 * 60  # 1 day in seconds


class TestDefaultRangeConstants:
    """Tests for default time range configuration."""

    def test_default_ranges_exist(self):
        """Test that default range constants are defined."""
        from backend.api.routes.events import DEFAULT_RANGES

        assert "hour" in DEFAULT_RANGES
        assert "day" in DEFAULT_RANGES
        assert "week" in DEFAULT_RANGES

    def test_hour_default_is_1_hour(self):
        """Test hour zoom defaults to 1 hour range."""
        from backend.api.routes.events import DEFAULT_RANGES

        assert DEFAULT_RANGES["hour"] == 60 * 60  # 1 hour

    def test_day_default_is_24_hours(self):
        """Test day zoom defaults to 24 hours range."""
        from backend.api.routes.events import DEFAULT_RANGES

        assert DEFAULT_RANGES["day"] == 24 * 60 * 60  # 24 hours

    def test_week_default_is_7_days(self):
        """Test week zoom defaults to 7 days range."""
        from backend.api.routes.events import DEFAULT_RANGES

        assert DEFAULT_RANGES["week"] == 7 * 24 * 60 * 60  # 7 days


class TestBucketCalculation:
    """Tests for bucket calculation logic."""

    def test_calculate_bucket_index(self):
        """Test bucket index calculation from timestamp."""
        # Given an event at 12:07 with 5-minute buckets starting at 12:00
        start_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        event_time = datetime(2026, 1, 15, 12, 7, 0, tzinfo=UTC)
        bucket_seconds = 5 * 60  # 5 minutes

        time_since_start = (event_time - start_time).total_seconds()
        bucket_index = int(time_since_start // bucket_seconds)

        # 7 minutes = 420 seconds, 420 // 300 = 1
        assert bucket_index == 1

    def test_calculate_bucket_time(self):
        """Test bucket start time calculation from event timestamp."""
        start_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        bucket_seconds = 60 * 60  # 1 hour buckets

        bucket_index = 2
        bucket_time = start_time + timedelta(seconds=bucket_index * bucket_seconds)

        assert bucket_time == datetime(2026, 1, 15, 14, 0, 0, tzinfo=UTC)

    def test_event_falls_into_correct_bucket(self):
        """Test that an event falls into the expected bucket."""
        start_time = datetime(2026, 1, 15, 0, 0, 0, tzinfo=UTC)
        bucket_seconds = 60 * 60  # 1 hour

        # Event at 2:30 AM should be in bucket 2 (covering 2:00-3:00)
        event_time = datetime(2026, 1, 15, 2, 30, 0, tzinfo=UTC)
        time_since_start = (event_time - start_time).total_seconds()
        bucket_index = int(time_since_start // bucket_seconds)

        assert bucket_index == 2

    def test_edge_case_event_at_bucket_boundary(self):
        """Test event exactly at bucket boundary."""
        start_time = datetime(2026, 1, 15, 0, 0, 0, tzinfo=UTC)
        bucket_seconds = 60 * 60  # 1 hour

        # Event exactly at 2:00 should be in bucket 2
        event_time = datetime(2026, 1, 15, 2, 0, 0, tzinfo=UTC)
        time_since_start = (event_time - start_time).total_seconds()
        bucket_index = int(time_since_start // bucket_seconds)

        assert bucket_index == 2

    def test_edge_case_event_at_start_time(self):
        """Test event at the very start of the range."""
        start_time = datetime(2026, 1, 15, 0, 0, 0, tzinfo=UTC)
        bucket_seconds = 60 * 60  # 1 hour

        event_time = start_time
        time_since_start = (event_time - start_time).total_seconds()
        bucket_index = int(time_since_start // bucket_seconds)

        assert bucket_index == 0
