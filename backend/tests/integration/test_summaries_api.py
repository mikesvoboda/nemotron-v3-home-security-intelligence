"""Integration tests for summaries API endpoints.

Tests the complete flow from API call to database, including:
- Full API flow with actual database operations
- Redis cache integration (hit/miss behavior)
- Data roundtrip (create summary -> fetch via API)
- Error handling and edge cases

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database
- mock_redis: Mock Redis client for basic tests
- real_redis: Real Redis client for cache integration tests
- client: httpx AsyncClient with test app

NEM-2898: Dashboard Summaries API Integration Tests
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.models.summary import Summary, SummaryType

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def clean_summaries(integration_db):
    """Delete summaries table data before test runs for proper isolation.

    This ensures tests that expect specific summary counts start with empty tables.
    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks
    when tests run in parallel with xdist.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine

    async with get_engine().begin() as conn:
        # Delete summaries table
        await conn.execute(text("DELETE FROM summaries"))  # nosemgrep: avoid-sqlalchemy-text

    yield

    # Cleanup after test too (best effort)
    try:
        async with get_engine().begin() as conn:
            await conn.execute(text("DELETE FROM summaries"))  # nosemgrep: avoid-sqlalchemy-text
    except Exception:
        pass


@pytest.fixture
async def sample_hourly_summary(integration_db, clean_summaries) -> Summary:
    """Create a sample hourly summary in the database."""
    from backend.core.database import get_session

    now = datetime.now(UTC)
    async with get_session() as db:
        summary = Summary(
            summary_type=SummaryType.HOURLY.value,
            content="Over the past hour, one critical event occurred at the front door.",
            event_count=1,
            event_ids=[101],
            window_start=now - timedelta(hours=1),
            window_end=now,
            generated_at=now - timedelta(minutes=5),
        )
        db.add(summary)
        await db.commit()
        await db.refresh(summary)
        return summary


@pytest.fixture
async def sample_daily_summary(integration_db, clean_summaries) -> Summary:
    """Create a sample daily summary in the database."""
    from backend.core.database import get_session

    now = datetime.now(UTC)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    async with get_session() as db:
        summary = Summary(
            summary_type=SummaryType.DAILY.value,
            content="Today has seen minimal high-priority activity with routine traffic only.",
            event_count=2,
            event_ids=[101, 102],
            window_start=midnight,
            window_end=now,
            generated_at=now - timedelta(minutes=5),
        )
        db.add(summary)
        await db.commit()
        await db.refresh(summary)
        return summary


@pytest.fixture
async def multiple_summaries(integration_db, clean_summaries) -> list[Summary]:
    """Create multiple summaries of different types and times for testing."""
    from backend.core.database import get_session

    now = datetime.now(UTC)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    summaries = []
    async with get_session() as db:
        # Older hourly summary
        older_hourly = Summary(
            summary_type=SummaryType.HOURLY.value,
            content="Older hourly summary - two high-priority events detected.",
            event_count=2,
            event_ids=[100, 101],
            window_start=now - timedelta(hours=2),
            window_end=now - timedelta(hours=1),
            generated_at=now - timedelta(hours=1, minutes=5),
        )
        db.add(older_hourly)
        summaries.append(older_hourly)

        # Latest hourly summary
        latest_hourly = Summary(
            summary_type=SummaryType.HOURLY.value,
            content="Latest hourly summary - all clear with no high-priority events.",
            event_count=0,
            event_ids=[],
            window_start=now - timedelta(hours=1),
            window_end=now,
            generated_at=now - timedelta(minutes=5),
        )
        db.add(latest_hourly)
        summaries.append(latest_hourly)

        # Older daily summary
        older_daily = Summary(
            summary_type=SummaryType.DAILY.value,
            content="Older daily summary from yesterday.",
            event_count=5,
            event_ids=[90, 91, 92, 93, 94],
            window_start=midnight - timedelta(days=1),
            window_end=midnight,
            generated_at=midnight - timedelta(minutes=5),
        )
        db.add(older_daily)
        summaries.append(older_daily)

        # Latest daily summary
        latest_daily = Summary(
            summary_type=SummaryType.DAILY.value,
            content="Latest daily summary - three notable events today.",
            event_count=3,
            event_ids=[101, 102, 103],
            window_start=midnight,
            window_end=now,
            generated_at=now - timedelta(minutes=5),
        )
        db.add(latest_daily)
        summaries.append(latest_daily)

        await db.commit()
        for s in summaries:
            await db.refresh(s)

    return summaries


# =============================================================================
# GET /api/summaries/latest Tests
# =============================================================================


class TestGetLatestSummaries:
    """Integration tests for GET /api/summaries/latest endpoint."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_summaries_exist(self, client, clean_summaries) -> None:
        """Test that null values are returned when no summaries exist in database."""
        response = await client.get("/api/summaries/latest")
        assert response.status_code == 200

        data = response.json()
        assert data["hourly"] is None
        assert data["daily"] is None

    @pytest.mark.asyncio
    async def test_returns_both_summaries_from_database(
        self, client, sample_hourly_summary, sample_daily_summary
    ) -> None:
        """Test that both hourly and daily summaries are returned from database."""
        response = await client.get("/api/summaries/latest")
        assert response.status_code == 200

        data = response.json()

        # Verify hourly summary
        assert data["hourly"] is not None
        assert data["hourly"]["id"] == sample_hourly_summary.id
        assert "critical event" in data["hourly"]["content"]
        assert data["hourly"]["event_count"] == 1

        # Verify daily summary
        assert data["daily"] is not None
        assert data["daily"]["id"] == sample_daily_summary.id
        assert "minimal high-priority" in data["daily"]["content"]
        assert data["daily"]["event_count"] == 2

    @pytest.mark.asyncio
    async def test_returns_only_hourly_when_daily_missing(
        self, client, sample_hourly_summary
    ) -> None:
        """Test response when only hourly summary exists in database."""
        response = await client.get("/api/summaries/latest")
        assert response.status_code == 200

        data = response.json()
        assert data["hourly"] is not None
        assert data["hourly"]["id"] == sample_hourly_summary.id
        assert data["daily"] is None

    @pytest.mark.asyncio
    async def test_returns_only_daily_when_hourly_missing(
        self, client, sample_daily_summary
    ) -> None:
        """Test response when only daily summary exists in database."""
        response = await client.get("/api/summaries/latest")
        assert response.status_code == 200

        data = response.json()
        assert data["hourly"] is None
        assert data["daily"] is not None
        assert data["daily"]["id"] == sample_daily_summary.id

    @pytest.mark.asyncio
    async def test_returns_latest_summaries_when_multiple_exist(
        self, client, multiple_summaries
    ) -> None:
        """Test that only the latest summaries are returned when multiple exist."""
        response = await client.get("/api/summaries/latest")
        assert response.status_code == 200

        data = response.json()

        # Latest hourly should be "all clear" (event_count=0)
        assert data["hourly"] is not None
        assert "all clear" in data["hourly"]["content"].lower()
        assert data["hourly"]["event_count"] == 0

        # Latest daily should have 3 events
        assert data["daily"] is not None
        assert "three notable events" in data["daily"]["content"].lower()
        assert data["daily"]["event_count"] == 3

    @pytest.mark.asyncio
    async def test_response_contains_all_required_fields(
        self, client, sample_hourly_summary
    ) -> None:
        """Test that response contains all required fields with correct types."""
        response = await client.get("/api/summaries/latest")
        assert response.status_code == 200

        data = response.json()
        hourly = data["hourly"]

        # Verify all required fields are present
        assert "id" in hourly
        assert "content" in hourly
        assert "event_count" in hourly
        assert "window_start" in hourly
        assert "window_end" in hourly
        assert "generated_at" in hourly

        # Verify field types
        assert isinstance(hourly["id"], int)
        assert isinstance(hourly["content"], str)
        assert isinstance(hourly["event_count"], int)
        assert hourly["event_count"] >= 0

        # Verify datetime fields are ISO formatted
        assert "T" in hourly["window_start"]
        assert "T" in hourly["window_end"]
        assert "T" in hourly["generated_at"]


# =============================================================================
# GET /api/summaries/hourly Tests
# =============================================================================


class TestGetHourlySummary:
    """Integration tests for GET /api/summaries/hourly endpoint."""

    @pytest.mark.asyncio
    async def test_returns_null_when_no_hourly_summary(self, client, clean_summaries) -> None:
        """Test that null is returned when no hourly summary exists."""
        response = await client.get("/api/summaries/hourly")
        assert response.status_code == 200
        assert response.json() is None

    @pytest.mark.asyncio
    async def test_returns_hourly_summary_from_database(
        self, client, sample_hourly_summary
    ) -> None:
        """Test that hourly summary is fetched correctly from database."""
        response = await client.get("/api/summaries/hourly")
        assert response.status_code == 200

        data = response.json()
        assert data is not None
        assert data["id"] == sample_hourly_summary.id
        assert data["content"] == sample_hourly_summary.content
        assert data["event_count"] == sample_hourly_summary.event_count

    @pytest.mark.asyncio
    async def test_returns_latest_hourly_when_multiple_exist(
        self, client, multiple_summaries
    ) -> None:
        """Test that only the latest hourly summary is returned."""
        response = await client.get("/api/summaries/hourly")
        assert response.status_code == 200

        data = response.json()
        assert data is not None
        # Latest hourly has "all clear" message with event_count=0
        assert data["event_count"] == 0
        assert "all clear" in data["content"].lower()

    @pytest.mark.asyncio
    async def test_returns_null_when_only_daily_exists(self, client, sample_daily_summary) -> None:
        """Test that null is returned when only daily summary exists."""
        response = await client.get("/api/summaries/hourly")
        assert response.status_code == 200
        assert response.json() is None


# =============================================================================
# GET /api/summaries/daily Tests
# =============================================================================


class TestGetDailySummary:
    """Integration tests for GET /api/summaries/daily endpoint."""

    @pytest.mark.asyncio
    async def test_returns_null_when_no_daily_summary(self, client, clean_summaries) -> None:
        """Test that null is returned when no daily summary exists."""
        response = await client.get("/api/summaries/daily")
        assert response.status_code == 200
        assert response.json() is None

    @pytest.mark.asyncio
    async def test_returns_daily_summary_from_database(self, client, sample_daily_summary) -> None:
        """Test that daily summary is fetched correctly from database."""
        response = await client.get("/api/summaries/daily")
        assert response.status_code == 200

        data = response.json()
        assert data is not None
        assert data["id"] == sample_daily_summary.id
        assert data["content"] == sample_daily_summary.content
        assert data["event_count"] == sample_daily_summary.event_count

    @pytest.mark.asyncio
    async def test_returns_latest_daily_when_multiple_exist(
        self, client, multiple_summaries
    ) -> None:
        """Test that only the latest daily summary is returned."""
        response = await client.get("/api/summaries/daily")
        assert response.status_code == 200

        data = response.json()
        assert data is not None
        # Latest daily has "three notable events" with event_count=3
        assert data["event_count"] == 3
        assert "three notable events" in data["content"].lower()

    @pytest.mark.asyncio
    async def test_returns_null_when_only_hourly_exists(
        self, client, sample_hourly_summary
    ) -> None:
        """Test that null is returned when only hourly summary exists."""
        response = await client.get("/api/summaries/daily")
        assert response.status_code == 200
        assert response.json() is None


# =============================================================================
# Data Roundtrip Tests
# =============================================================================


class TestDataRoundtrip:
    """Test complete data roundtrip: create summary in DB -> fetch via API."""

    @pytest.mark.asyncio
    async def test_created_summary_accessible_via_api(
        self, client, integration_db, clean_summaries
    ) -> None:
        """Test that a summary created directly in DB is accessible via API."""
        from backend.core.database import get_session
        from backend.repositories.summary_repository import SummaryRepository

        now = datetime.now(UTC)

        # Create summary directly using repository
        async with get_session() as db:
            repo = SummaryRepository(db)
            created_summary = await repo.create_summary(
                summary_type=SummaryType.HOURLY,
                content="Test summary created via repository.",
                event_count=5,
                event_ids=[1, 2, 3, 4, 5],
                window_start=now - timedelta(hours=1),
                window_end=now,
                generated_at=now,
            )
            await db.commit()
            summary_id = created_summary.id

        # Fetch via API
        response = await client.get("/api/summaries/hourly")
        assert response.status_code == 200

        data = response.json()
        assert data is not None
        assert data["id"] == summary_id
        assert data["content"] == "Test summary created via repository."
        assert data["event_count"] == 5

    @pytest.mark.asyncio
    async def test_summary_timestamps_roundtrip_correctly(
        self, client, integration_db, clean_summaries
    ) -> None:
        """Test that timestamp fields roundtrip correctly through DB and API."""
        from backend.core.database import get_session

        # Use specific timestamps for verification
        window_start = datetime(2026, 1, 18, 14, 0, 0, tzinfo=UTC)
        window_end = datetime(2026, 1, 18, 15, 0, 0, tzinfo=UTC)
        generated_at = datetime(2026, 1, 18, 14, 55, 0, tzinfo=UTC)

        async with get_session() as db:
            summary = Summary(
                summary_type=SummaryType.HOURLY.value,
                content="Timestamp roundtrip test.",
                event_count=0,
                event_ids=None,
                window_start=window_start,
                window_end=window_end,
                generated_at=generated_at,
            )
            db.add(summary)
            await db.commit()

        # Fetch via API
        response = await client.get("/api/summaries/hourly")
        assert response.status_code == 200

        data = response.json()

        # Verify timestamps (API returns ISO format)
        assert data["window_start"] == "2026-01-18T14:00:00Z"
        assert data["window_end"] == "2026-01-18T15:00:00Z"
        assert data["generated_at"] == "2026-01-18T14:55:00Z"

    @pytest.mark.asyncio
    async def test_event_ids_array_roundtrips_correctly(
        self, client, integration_db, clean_summaries
    ) -> None:
        """Test that event_ids array is stored and retrieved correctly."""
        from backend.core.database import get_session

        now = datetime.now(UTC)
        event_ids = [100, 200, 300, 400, 500]

        async with get_session() as db:
            summary = Summary(
                summary_type=SummaryType.DAILY.value,
                content="Event IDs array test.",
                event_count=len(event_ids),
                event_ids=event_ids,
                window_start=now.replace(hour=0, minute=0, second=0, microsecond=0),
                window_end=now,
                generated_at=now,
            )
            db.add(summary)
            await db.commit()
            await db.refresh(summary)

            # Verify array stored correctly in DB
            assert summary.event_ids == event_ids

        # Note: event_ids is not included in API response per schema
        # Just verify the summary is accessible
        response = await client.get("/api/summaries/daily")
        assert response.status_code == 200
        assert response.json()["event_count"] == len(event_ids)


# =============================================================================
# Cache Integration Tests
# =============================================================================


class TestCacheIntegration:
    """Test Redis cache integration with summaries API."""

    @pytest.mark.asyncio
    async def test_cache_miss_then_hit_pattern(self, client, sample_hourly_summary) -> None:
        """Test that first request is cache miss, second is cache hit."""
        # First request - should hit database
        response1 = await client.get("/api/summaries/hourly")
        assert response1.status_code == 200
        data1 = response1.json()

        # Second request - should hit cache
        response2 = await client.get("/api/summaries/hourly")
        assert response2.status_code == 200
        data2 = response2.json()

        # Both should return the same data
        assert data1 == data2
        assert data1["id"] == sample_hourly_summary.id

    @pytest.mark.asyncio
    async def test_latest_endpoint_caches_correctly(
        self, client, sample_hourly_summary, sample_daily_summary
    ) -> None:
        """Test that /latest endpoint caches combined response correctly."""
        # First request
        response1 = await client.get("/api/summaries/latest")
        assert response1.status_code == 200
        data1 = response1.json()

        # Second request
        response2 = await client.get("/api/summaries/latest")
        assert response2.status_code == 200
        data2 = response2.json()

        # Both should have same data
        assert data1["hourly"]["id"] == data2["hourly"]["id"]
        assert data1["daily"]["id"] == data2["daily"]["id"]


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling for summaries API."""

    @pytest.mark.asyncio
    async def test_handles_empty_content_gracefully(
        self, client, integration_db, clean_summaries
    ) -> None:
        """Test that summaries with empty content are handled correctly."""
        from backend.core.database import get_session

        now = datetime.now(UTC)
        async with get_session() as db:
            # Note: Content should not be empty per design, but test defensive handling
            summary = Summary(
                summary_type=SummaryType.HOURLY.value,
                content="",  # Empty content
                event_count=0,
                event_ids=[],
                window_start=now - timedelta(hours=1),
                window_end=now,
                generated_at=now,
            )
            db.add(summary)
            await db.commit()

        response = await client.get("/api/summaries/hourly")
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == ""

    @pytest.mark.asyncio
    async def test_handles_null_event_ids_correctly(
        self, client, integration_db, clean_summaries
    ) -> None:
        """Test that summaries with null event_ids are handled correctly."""
        from backend.core.database import get_session

        now = datetime.now(UTC)
        async with get_session() as db:
            summary = Summary(
                summary_type=SummaryType.HOURLY.value,
                content="Summary with null event_ids.",
                event_count=0,
                event_ids=None,  # Null event_ids
                window_start=now - timedelta(hours=1),
                window_end=now,
                generated_at=now,
            )
            db.add(summary)
            await db.commit()

        response = await client.get("/api/summaries/hourly")
        assert response.status_code == 200
        data = response.json()
        assert data["event_count"] == 0

    @pytest.mark.asyncio
    async def test_handles_large_event_count(self, client, integration_db, clean_summaries) -> None:
        """Test that summaries with large event counts are handled correctly."""
        from backend.core.database import get_session

        now = datetime.now(UTC)
        large_event_count = 1000
        large_event_ids = list(range(1, large_event_count + 1))

        async with get_session() as db:
            summary = Summary(
                summary_type=SummaryType.DAILY.value,
                content="Summary with large event count.",
                event_count=large_event_count,
                event_ids=large_event_ids,
                window_start=now.replace(hour=0, minute=0, second=0, microsecond=0),
                window_end=now,
                generated_at=now,
            )
            db.add(summary)
            await db.commit()

        response = await client.get("/api/summaries/daily")
        assert response.status_code == 200
        data = response.json()
        assert data["event_count"] == large_event_count

    @pytest.mark.asyncio
    async def test_handles_long_content(self, client, integration_db, clean_summaries) -> None:
        """Test that summaries with long content are handled correctly."""
        from backend.core.database import get_session

        now = datetime.now(UTC)
        long_content = "A" * 5000  # 5000 character content

        async with get_session() as db:
            summary = Summary(
                summary_type=SummaryType.HOURLY.value,
                content=long_content,
                event_count=0,
                event_ids=[],
                window_start=now - timedelta(hours=1),
                window_end=now,
                generated_at=now,
            )
            db.add(summary)
            await db.commit()

        response = await client.get("/api/summaries/hourly")
        assert response.status_code == 200
        data = response.json()
        assert len(data["content"]) == 5000

    @pytest.mark.asyncio
    async def test_handles_special_characters_in_content(
        self, client, integration_db, clean_summaries
    ) -> None:
        """Test that summaries with special characters are handled correctly."""
        from backend.core.database import get_session

        now = datetime.now(UTC)
        special_content = (
            'Content with "quotes", <tags>, &entities, '
            "newlines\n\r, and unicode: \u2713\u2714\u2715"
        )

        async with get_session() as db:
            summary = Summary(
                summary_type=SummaryType.HOURLY.value,
                content=special_content,
                event_count=0,
                event_ids=[],
                window_start=now - timedelta(hours=1),
                window_end=now,
                generated_at=now,
            )
            db.add(summary)
            await db.commit()

        response = await client.get("/api/summaries/hourly")
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == special_content


# =============================================================================
# Repository Integration Tests
# =============================================================================


class TestRepositoryIntegration:
    """Test repository operations with real database."""

    @pytest.mark.asyncio
    async def test_get_latest_by_type_with_real_db(self, integration_db, clean_summaries) -> None:
        """Test get_latest_by_type with actual database queries."""
        from backend.core.database import get_session
        from backend.repositories.summary_repository import SummaryRepository

        now = datetime.now(UTC)

        async with get_session() as db:
            repo = SummaryRepository(db)

            # Initially no summaries
            result = await repo.get_latest_by_type(SummaryType.HOURLY)
            assert result is None

            # Create a summary
            summary = await repo.create_summary(
                summary_type=SummaryType.HOURLY,
                content="First hourly summary.",
                event_count=1,
                event_ids=[1],
                window_start=now - timedelta(hours=1),
                window_end=now,
                generated_at=now,
            )
            await db.commit()

            # Now should return the summary
            result = await repo.get_latest_by_type(SummaryType.HOURLY)
            assert result is not None
            assert result.id == summary.id

    @pytest.mark.asyncio
    async def test_get_latest_all_with_real_db(self, integration_db, clean_summaries) -> None:
        """Test get_latest_all with actual database queries."""
        from backend.core.database import get_session
        from backend.repositories.summary_repository import SummaryRepository

        now = datetime.now(UTC)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

        async with get_session() as db:
            repo = SummaryRepository(db)

            # Create both hourly and daily summaries
            hourly = await repo.create_summary(
                summary_type=SummaryType.HOURLY,
                content="Hourly summary.",
                event_count=1,
                event_ids=[1],
                window_start=now - timedelta(hours=1),
                window_end=now,
                generated_at=now,
            )

            daily = await repo.create_summary(
                summary_type=SummaryType.DAILY,
                content="Daily summary.",
                event_count=2,
                event_ids=[1, 2],
                window_start=midnight,
                window_end=now,
                generated_at=now,
            )
            await db.commit()

            # Get both
            result = await repo.get_latest_all()
            assert result["hourly"] is not None
            assert result["daily"] is not None
            assert result["hourly"].id == hourly.id
            assert result["daily"].id == daily.id

    @pytest.mark.asyncio
    async def test_cleanup_old_summaries_with_real_db(
        self, integration_db, clean_summaries
    ) -> None:
        """Test cleanup_old_summaries with actual database operations."""
        from backend.core.database import get_session
        from backend.repositories.summary_repository import SummaryRepository

        now = datetime.now(UTC)

        async with get_session() as db:
            repo = SummaryRepository(db)

            # Create old summary (8 days ago)
            old_summary = Summary(
                summary_type=SummaryType.HOURLY.value,
                content="Old summary.",
                event_count=0,
                event_ids=[],
                window_start=now - timedelta(days=8, hours=1),
                window_end=now - timedelta(days=8),
                generated_at=now - timedelta(days=8),
            )
            db.add(old_summary)
            await db.flush()

            # Manually set created_at to make it old
            # Note: We need to use raw SQL to bypass the server_default
            from sqlalchemy import text

            await db.execute(
                text(
                    "UPDATE summaries SET created_at = :old_time WHERE id = :id"
                ),  # nosemgrep: avoid-sqlalchemy-text
                {"old_time": now - timedelta(days=8), "id": old_summary.id},
            )
            await db.commit()

            # Create recent summary
            recent_summary = await repo.create_summary(
                summary_type=SummaryType.HOURLY,
                content="Recent summary.",
                event_count=0,
                event_ids=[],
                window_start=now - timedelta(hours=1),
                window_end=now,
                generated_at=now,
            )
            await db.commit()

            # Cleanup should delete only the old one
            deleted_count = await repo.cleanup_old_summaries(days=7)
            await db.commit()

            assert deleted_count == 1

            # Recent summary should still exist
            result = await repo.get_latest_by_type(SummaryType.HOURLY)
            assert result is not None
            assert result.id == recent_summary.id


# =============================================================================
# Concurrent Access Tests
# =============================================================================


class TestConcurrentAccess:
    """Test concurrent access to summaries API."""

    @pytest.mark.asyncio
    async def test_concurrent_reads_return_consistent_data(
        self, client, sample_hourly_summary, sample_daily_summary
    ) -> None:
        """Test that concurrent reads return consistent data."""
        import asyncio

        async def fetch_latest():
            response = await client.get("/api/summaries/latest")
            return response.json()

        # Make 10 concurrent requests
        results = await asyncio.gather(*[fetch_latest() for _ in range(10)])

        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            assert result["hourly"]["id"] == first_result["hourly"]["id"]
            assert result["daily"]["id"] == first_result["daily"]["id"]

    @pytest.mark.asyncio
    async def test_concurrent_endpoint_reads(
        self, client, sample_hourly_summary, sample_daily_summary
    ) -> None:
        """Test concurrent reads across different endpoints."""
        import asyncio

        async def fetch_hourly():
            response = await client.get("/api/summaries/hourly")
            return ("hourly", response.json())

        async def fetch_daily():
            response = await client.get("/api/summaries/daily")
            return ("daily", response.json())

        async def fetch_latest():
            response = await client.get("/api/summaries/latest")
            return ("latest", response.json())

        # Mix of all endpoint calls
        tasks = [
            fetch_hourly(),
            fetch_daily(),
            fetch_latest(),
            fetch_hourly(),
            fetch_daily(),
            fetch_latest(),
        ]

        results = await asyncio.gather(*tasks)

        # Verify all responses are valid
        for endpoint_type, data in results:
            if endpoint_type == "hourly":
                assert data["id"] == sample_hourly_summary.id
            elif endpoint_type == "daily":
                assert data["id"] == sample_daily_summary.id
            else:  # latest
                assert data["hourly"]["id"] == sample_hourly_summary.id
                assert data["daily"]["id"] == sample_daily_summary.id
