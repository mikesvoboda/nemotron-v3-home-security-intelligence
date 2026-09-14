"""Unit tests for SummaryRepository.

Tests follow TDD approach - these tests are written BEFORE the implementation.
Run with: uv run pytest backend/tests/unit/repositories/test_summary_repository.py -v

Related to NEM-2888: Create SummaryRepository for PostgreSQL CRUD operations.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.summary import Summary, SummaryType


class TestSummaryRepositoryBasicCRUD:
    """Test basic CRUD operations inherited from Repository base class."""

    @pytest.mark.asyncio
    async def test_create_summary(self, mock_db_session: AsyncMock):
        """Test creating a new summary."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)

        now = datetime.now(UTC)
        summary = Summary(
            summary_type=SummaryType.HOURLY.value,
            content="No high-priority events in the past hour.",
            event_count=0,
            event_ids=None,
            window_start=now - timedelta(hours=1),
            window_end=now,
            generated_at=now,
        )

        # Configure mock to return the summary on refresh
        mock_db_session.refresh = AsyncMock()

        created = await repo.create(summary)

        mock_db_session.add.assert_called_once_with(summary)
        mock_db_session.flush.assert_called_once()
        mock_db_session.refresh.assert_called_once_with(summary)
        assert created == summary

    @pytest.mark.asyncio
    async def test_create_hourly_summary_with_events(self, mock_db_session: AsyncMock):
        """Test creating an hourly summary with event IDs."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)

        now = datetime.now(UTC)
        summary = Summary(
            summary_type=SummaryType.HOURLY.value,
            content="One critical event at the front door.",
            event_count=1,
            event_ids=[101, 102],
            window_start=now - timedelta(hours=1),
            window_end=now,
            generated_at=now,
        )

        mock_db_session.refresh = AsyncMock()

        created = await repo.create(summary)

        assert created == summary
        assert created.summary_type == "hourly"
        assert created.event_count == 1
        assert created.event_ids == [101, 102]

    @pytest.mark.asyncio
    async def test_create_daily_summary(self, mock_db_session: AsyncMock):
        """Test creating a daily summary."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)

        now = datetime.now(UTC)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        summary = Summary(
            summary_type=SummaryType.DAILY.value,
            content="Today saw minimal high-priority activity.",
            event_count=2,
            event_ids=[101, 102],
            window_start=midnight,
            window_end=now,
            generated_at=now,
        )

        mock_db_session.refresh = AsyncMock()

        created = await repo.create(summary)

        assert created == summary
        assert created.summary_type == "daily"

    @pytest.mark.asyncio
    async def test_get_by_id_existing(self, mock_db_session: AsyncMock):
        """Test retrieving an existing summary by ID."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)
        summary_id = 1
        expected_summary = Summary(
            id=summary_id,
            summary_type=SummaryType.HOURLY.value,
            content="Test content",
            event_count=0,
            window_start=datetime.now(UTC),
            window_end=datetime.now(UTC),
            generated_at=datetime.now(UTC),
        )

        mock_db_session.get.return_value = expected_summary

        result = await repo.get_by_id(summary_id)

        mock_db_session.get.assert_called_once_with(Summary, summary_id)
        assert result == expected_summary

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_db_session: AsyncMock):
        """Test retrieving a non-existent summary returns None."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)
        mock_db_session.get.return_value = None

        result = await repo.get_by_id(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_summary(self, mock_db_session: AsyncMock):
        """Test deleting a summary."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)
        now = datetime.now(UTC)
        summary = Summary(
            id=1,
            summary_type=SummaryType.HOURLY.value,
            content="Test content",
            event_count=0,
            window_start=now,
            window_end=now,
            generated_at=now,
        )

        await repo.delete(summary)

        mock_db_session.delete.assert_called_once_with(summary)
        mock_db_session.flush.assert_called_once()


class TestSummaryRepositoryGetLatestByType:
    """Test get_latest_by_type method."""

    @pytest.mark.asyncio
    async def test_get_latest_hourly_summary(self, mock_db_session: AsyncMock):
        """Test getting latest hourly summary."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)

        now = datetime.now(UTC)
        latest_hourly = Summary(
            id=5,
            summary_type=SummaryType.HOURLY.value,
            content="Latest hourly summary",
            event_count=1,
            event_ids=[100],
            window_start=now - timedelta(hours=1),
            window_end=now,
            generated_at=now,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = latest_hourly
        mock_db_session.execute.return_value = mock_result

        result = await repo.get_latest_by_type(SummaryType.HOURLY)

        assert result == latest_hourly
        assert result.summary_type == "hourly"
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_latest_daily_summary(self, mock_db_session: AsyncMock):
        """Test getting latest daily summary."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)

        now = datetime.now(UTC)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        latest_daily = Summary(
            id=10,
            summary_type=SummaryType.DAILY.value,
            content="Latest daily summary",
            event_count=3,
            event_ids=[101, 102, 103],
            window_start=midnight,
            window_end=now,
            generated_at=now,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = latest_daily
        mock_db_session.execute.return_value = mock_result

        result = await repo.get_latest_by_type(SummaryType.DAILY)

        assert result == latest_daily
        assert result.summary_type == "daily"

    @pytest.mark.asyncio
    async def test_get_latest_by_type_string(self, mock_db_session: AsyncMock):
        """Test getting latest summary using string type."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)

        now = datetime.now(UTC)
        latest_hourly = Summary(
            id=5,
            summary_type=SummaryType.HOURLY.value,
            content="Latest hourly summary",
            event_count=0,
            window_start=now - timedelta(hours=1),
            window_end=now,
            generated_at=now,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = latest_hourly
        mock_db_session.execute.return_value = mock_result

        result = await repo.get_latest_by_type("hourly")

        assert result == latest_hourly

    @pytest.mark.asyncio
    async def test_get_latest_by_type_not_found(self, mock_db_session: AsyncMock):
        """Test get_latest_by_type returns None when no summaries exist."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await repo.get_latest_by_type(SummaryType.HOURLY)

        assert result is None


class TestSummaryRepositoryGetLatestAll:
    """Test get_latest_all method."""

    @pytest.mark.asyncio
    async def test_get_latest_all_both_exist(self, mock_db_session: AsyncMock):
        """Test getting both hourly and daily summaries."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)

        now = datetime.now(UTC)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

        hourly_summary = Summary(
            id=5,
            summary_type=SummaryType.HOURLY.value,
            content="Latest hourly summary",
            event_count=1,
            window_start=now - timedelta(hours=1),
            window_end=now,
            generated_at=now,
        )

        daily_summary = Summary(
            id=10,
            summary_type=SummaryType.DAILY.value,
            content="Latest daily summary",
            event_count=3,
            window_start=midnight,
            window_end=now,
            generated_at=now,
        )

        # Mock execute to return different results for each call
        mock_result_hourly = MagicMock()
        mock_result_hourly.scalar_one_or_none.return_value = hourly_summary

        mock_result_daily = MagicMock()
        mock_result_daily.scalar_one_or_none.return_value = daily_summary

        mock_db_session.execute.side_effect = [mock_result_hourly, mock_result_daily]

        result = await repo.get_latest_all()

        assert result["hourly"] == hourly_summary
        assert result["daily"] == daily_summary
        assert mock_db_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_get_latest_all_only_hourly_exists(self, mock_db_session: AsyncMock):
        """Test get_latest_all when only hourly summary exists."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)

        now = datetime.now(UTC)
        hourly_summary = Summary(
            id=5,
            summary_type=SummaryType.HOURLY.value,
            content="Latest hourly summary",
            event_count=0,
            window_start=now - timedelta(hours=1),
            window_end=now,
            generated_at=now,
        )

        mock_result_hourly = MagicMock()
        mock_result_hourly.scalar_one_or_none.return_value = hourly_summary

        mock_result_daily = MagicMock()
        mock_result_daily.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [mock_result_hourly, mock_result_daily]

        result = await repo.get_latest_all()

        assert result["hourly"] == hourly_summary
        assert result["daily"] is None

    @pytest.mark.asyncio
    async def test_get_latest_all_only_daily_exists(self, mock_db_session: AsyncMock):
        """Test get_latest_all when only daily summary exists."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)

        now = datetime.now(UTC)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        daily_summary = Summary(
            id=10,
            summary_type=SummaryType.DAILY.value,
            content="Latest daily summary",
            event_count=2,
            window_start=midnight,
            window_end=now,
            generated_at=now,
        )

        mock_result_hourly = MagicMock()
        mock_result_hourly.scalar_one_or_none.return_value = None

        mock_result_daily = MagicMock()
        mock_result_daily.scalar_one_or_none.return_value = daily_summary

        mock_db_session.execute.side_effect = [mock_result_hourly, mock_result_daily]

        result = await repo.get_latest_all()

        assert result["hourly"] is None
        assert result["daily"] == daily_summary

    @pytest.mark.asyncio
    async def test_get_latest_all_neither_exists(self, mock_db_session: AsyncMock):
        """Test get_latest_all when no summaries exist."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await repo.get_latest_all()

        assert result["hourly"] is None
        assert result["daily"] is None


class TestSummaryRepositoryCleanupOldSummaries:
    """Test cleanup_old_summaries method."""

    @pytest.mark.asyncio
    async def test_cleanup_old_summaries_default_retention(self, mock_db_session: AsyncMock):
        """Test cleanup with default 7-day retention."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_db_session.execute.return_value = mock_result

        deleted_count = await repo.cleanup_old_summaries()

        assert deleted_count == 5
        mock_db_session.execute.assert_called_once()
        mock_db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_summaries_custom_retention(self, mock_db_session: AsyncMock):
        """Test cleanup with custom retention period."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.rowcount = 10
        mock_db_session.execute.return_value = mock_result

        deleted_count = await repo.cleanup_old_summaries(days=3)

        assert deleted_count == 10
        mock_db_session.execute.assert_called_once()
        mock_db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_summaries_none_to_delete(self, mock_db_session: AsyncMock):
        """Test cleanup when no old summaries exist."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db_session.execute.return_value = mock_result

        deleted_count = await repo.cleanup_old_summaries()

        assert deleted_count == 0


class TestSummaryRepositoryCreate:
    """Test create method with full parameters."""

    @pytest.mark.asyncio
    async def test_create_with_all_parameters(self, mock_db_session: AsyncMock):
        """Test create_summary helper method with all parameters."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)

        now = datetime.now(UTC)
        window_start = now - timedelta(hours=1)
        window_end = now
        event_ids = [101, 102, 103]

        mock_db_session.refresh = AsyncMock()

        summary = await repo.create_summary(
            summary_type=SummaryType.HOURLY,
            content="Three high-priority events detected.",
            event_count=3,
            event_ids=event_ids,
            window_start=window_start,
            window_end=window_end,
            generated_at=now,
        )

        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()
        mock_db_session.refresh.assert_called_once()

        # Verify the summary object passed to add() has correct attributes
        added_summary = mock_db_session.add.call_args[0][0]
        assert added_summary.summary_type == SummaryType.HOURLY.value
        assert added_summary.content == "Three high-priority events detected."
        assert added_summary.event_count == 3
        assert added_summary.event_ids == event_ids
        assert added_summary.window_start == window_start
        assert added_summary.window_end == window_end
        assert added_summary.generated_at == now

    @pytest.mark.asyncio
    async def test_create_with_string_type(self, mock_db_session: AsyncMock):
        """Test create_summary with string type parameter."""
        from backend.repositories.summary_repository import SummaryRepository

        repo = SummaryRepository(mock_db_session)

        now = datetime.now(UTC)
        mock_db_session.refresh = AsyncMock()

        await repo.create_summary(
            summary_type="daily",
            content="All clear for today.",
            event_count=0,
            event_ids=None,
            window_start=now.replace(hour=0, minute=0, second=0, microsecond=0),
            window_end=now,
            generated_at=now,
        )

        # Verify the summary type was normalized to string
        added_summary = mock_db_session.add.call_args[0][0]
        assert added_summary.summary_type == "daily"
