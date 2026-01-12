"""Unit tests for partition management service.

Tests for the PartitionManager service that handles PostgreSQL time-series
table partitioning for high-volume tables (detections, events, logs, gpu_stats).

Following TDD approach - tests written first before implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# PartitionConfig Tests
# =============================================================================


class TestPartitionConfig:
    """Tests for partition configuration dataclass."""

    def test_partition_config_creation(self) -> None:
        """Test creating a partition configuration."""
        from backend.services.partition_manager import PartitionConfig

        config = PartitionConfig(
            table_name="detections",
            partition_column="detected_at",
            partition_interval="monthly",
            retention_months=12,
        )

        assert config.table_name == "detections"
        assert config.partition_column == "detected_at"
        assert config.partition_interval == "monthly"
        assert config.retention_months == 12

    def test_partition_config_defaults(self) -> None:
        """Test partition configuration default values."""
        from backend.services.partition_manager import PartitionConfig

        config = PartitionConfig(
            table_name="events",
            partition_column="started_at",
        )

        assert config.partition_interval == "monthly"
        assert config.retention_months == 12

    def test_partition_config_weekly_interval(self) -> None:
        """Test partition configuration with weekly interval."""
        from backend.services.partition_manager import PartitionConfig

        config = PartitionConfig(
            table_name="gpu_stats",
            partition_column="recorded_at",
            partition_interval="weekly",
            retention_months=3,
        )

        assert config.partition_interval == "weekly"
        assert config.retention_months == 3


# =============================================================================
# PartitionInfo Tests
# =============================================================================


class TestPartitionInfo:
    """Tests for partition information dataclass."""

    def test_partition_info_creation(self) -> None:
        """Test creating partition info."""
        from backend.services.partition_manager import PartitionInfo

        info = PartitionInfo(
            name="detections_y2026m01",
            table_name="detections",
            start_date=datetime(2026, 1, 1, tzinfo=UTC),
            end_date=datetime(2026, 2, 1, tzinfo=UTC),
            row_count=1000,
        )

        assert info.name == "detections_y2026m01"
        assert info.table_name == "detections"
        assert info.start_date == datetime(2026, 1, 1, tzinfo=UTC)
        assert info.end_date == datetime(2026, 2, 1, tzinfo=UTC)
        assert info.row_count == 1000

    def test_partition_info_is_expired(self) -> None:
        """Test checking if a partition is expired."""
        from backend.services.partition_manager import PartitionInfo

        # Create a partition that's 13 months old
        old_start = datetime.now(UTC) - timedelta(days=400)
        old_end = old_start + timedelta(days=31)

        info = PartitionInfo(
            name="detections_old",
            table_name="detections",
            start_date=old_start,
            end_date=old_end,
            row_count=500,
        )

        # Should be expired with 12 month retention
        assert info.is_expired(retention_months=12)

        # Should not be expired with 24 month retention
        assert not info.is_expired(retention_months=24)

    def test_partition_info_is_not_expired_recent(self) -> None:
        """Test that recent partitions are not expired."""
        from backend.services.partition_manager import PartitionInfo

        # Create a partition for current month
        now = datetime.now(UTC)
        start = datetime(now.year, now.month, 1, tzinfo=UTC)
        if now.month == 12:
            end = datetime(now.year + 1, 1, 1, tzinfo=UTC)
        else:
            end = datetime(now.year, now.month + 1, 1, tzinfo=UTC)

        info = PartitionInfo(
            name="detections_current",
            table_name="detections",
            start_date=start,
            end_date=end,
            row_count=100,
        )

        assert not info.is_expired(retention_months=12)


# =============================================================================
# PartitionManager Tests
# =============================================================================


class TestPartitionManager:
    """Tests for the partition manager service."""

    def test_partition_manager_initialization(self) -> None:
        """Test partition manager initialization."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        configs = [
            PartitionConfig("detections", "detected_at"),
            PartitionConfig("events", "started_at"),
        ]

        manager = PartitionManager(configs=configs)

        assert len(manager.configs) == 2
        assert manager.configs[0].table_name == "detections"
        assert manager.configs[1].table_name == "events"

    def test_partition_manager_default_configs(self) -> None:
        """Test partition manager with default configurations."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        # Should have default configs for high-volume tables
        table_names = [c.table_name for c in manager.configs]
        assert "detections" in table_names
        assert "events" in table_names
        assert "logs" in table_names
        assert "gpu_stats" in table_names
        assert "audit_logs" in table_names

    def test_generate_partition_name_monthly(self) -> None:
        """Test generating partition names for monthly intervals."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("detections", "detected_at", "monthly")

        date = datetime(2026, 1, 15, tzinfo=UTC)
        name = manager._generate_partition_name(config, date)

        assert name == "detections_y2026m01"

    def test_generate_partition_name_weekly(self) -> None:
        """Test generating partition names for weekly intervals."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("gpu_stats", "recorded_at", "weekly")

        # Week 1 of 2026
        date = datetime(2026, 1, 5, tzinfo=UTC)
        name = manager._generate_partition_name(config, date)

        assert name.startswith("gpu_stats_y2026w")

    def test_calculate_partition_bounds_monthly(self) -> None:
        """Test calculating partition bounds for monthly intervals."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("detections", "detected_at", "monthly")

        date = datetime(2026, 1, 15, 12, 30, 0, tzinfo=UTC)
        start, end = manager._calculate_partition_bounds(config, date)

        assert start == datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert end == datetime(2026, 2, 1, 0, 0, 0, tzinfo=UTC)

    def test_calculate_partition_bounds_monthly_december(self) -> None:
        """Test calculating partition bounds for December (year rollover)."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("detections", "detected_at", "monthly")

        date = datetime(2026, 12, 25, tzinfo=UTC)
        start, end = manager._calculate_partition_bounds(config, date)

        assert start == datetime(2026, 12, 1, 0, 0, 0, tzinfo=UTC)
        assert end == datetime(2027, 1, 1, 0, 0, 0, tzinfo=UTC)

    def test_calculate_partition_bounds_weekly(self) -> None:
        """Test calculating partition bounds for weekly intervals."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("gpu_stats", "recorded_at", "weekly")

        # Monday, January 5, 2026
        date = datetime(2026, 1, 5, tzinfo=UTC)
        start, end = manager._calculate_partition_bounds(config, date)

        # Should be a 7-day range starting on Monday
        assert (end - start).days == 7
        # Start should be on or before the given date
        assert start <= date
        # End should be after the given date
        assert end > date

    def test_get_partitions_to_create(self) -> None:
        """Test determining which partitions need to be created."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("detections", "detected_at", "monthly")

        # Get partitions to create (current month + 2 future months)
        partitions = manager._get_partitions_to_create(config, months_ahead=2)

        assert len(partitions) >= 3  # Current + 2 ahead
        # All partitions should have valid bounds
        for name, start, end in partitions:
            assert name.startswith("detections_y")
            assert start < end

    def test_get_partitions_to_create_december_rollover(self) -> None:
        """Test partition creation that crosses December into next year."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("detections", "detected_at", "monthly")

        # Mock datetime to be in December
        with patch("backend.services.partition_manager.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 12, 15, tzinfo=UTC)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            partitions = manager._get_partitions_to_create(config, months_ahead=2)

            # Should create partitions including January of next year
            assert len(partitions) >= 3
            partition_names = [name for name, _, _ in partitions]
            # Should have December 2026 and January 2027
            assert any("y2026m12" in name for name in partition_names)
            assert any("y2027m01" in name for name in partition_names)

    @pytest.mark.asyncio
    async def test_check_partition_exists_when_exists(self) -> None:
        """Test checking if a partition exists when it does."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        # Mock the database session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "detections_y2026m01"
        mock_session.execute.return_value = mock_result

        exists = await manager._check_partition_exists(mock_session, "detections_y2026m01")
        assert exists is True

    @pytest.mark.asyncio
    async def test_check_partition_exists_when_not_exists(self) -> None:
        """Test checking if a partition exists when it doesn't."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        # Mock the database session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        exists = await manager._check_partition_exists(mock_session, "detections_nonexistent")
        assert exists is False

    @pytest.mark.asyncio
    async def test_create_partition(self) -> None:
        """Test creating a new partition."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("detections", "detected_at", "monthly")

        mock_session = AsyncMock()

        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 2, 1, tzinfo=UTC)

        await manager._create_partition(mock_session, config, "detections_y2026m01", start, end)

        # Should have executed SQL to create partition
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "CREATE TABLE" in sql_text or "PARTITION" in sql_text

    @pytest.mark.asyncio
    async def test_drop_partition(self) -> None:
        """Test dropping an old partition."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        mock_session = AsyncMock()

        await manager._drop_partition(mock_session, "detections_y2024m01")

        # Should have executed SQL to drop partition
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "DROP TABLE" in sql_text or "detections_y2024m01" in sql_text

    @pytest.mark.asyncio
    async def test_ensure_partitions_creates_missing(self) -> None:
        """Test that ensure_partitions creates missing partitions."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        config = PartitionConfig("detections", "detected_at", "monthly")
        manager = PartitionManager(configs=[config])

        mock_session = AsyncMock()

        # Mock partition existence check to return False (partition doesn't exist)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Mock the async context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None

        with (
            patch.object(manager, "_check_table_is_partitioned", return_value=True),
            patch.object(manager, "_check_partition_exists", return_value=False) as mock_check,
            patch.object(manager, "_create_partition") as mock_create,
            patch(
                "backend.services.partition_manager.get_session",
                return_value=mock_context,
            ),
        ):
            result = await manager.ensure_partitions()

            # Should have checked for existing partitions
            assert mock_check.call_count >= 1
            # Should have created partitions
            assert mock_create.call_count >= 1
            # Should return list of created partitions
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_ensure_partitions_skips_existing(self) -> None:
        """Test that ensure_partitions skips existing partitions."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        config = PartitionConfig("detections", "detected_at", "monthly")
        manager = PartitionManager(configs=[config])

        mock_session = AsyncMock()

        # Mock the async context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None

        with (
            patch.object(manager, "_check_table_is_partitioned", return_value=True),
            patch.object(manager, "_check_partition_exists", return_value=True) as mock_check,
            patch.object(manager, "_create_partition") as mock_create,
            patch(
                "backend.services.partition_manager.get_session",
                return_value=mock_context,
            ),
        ):
            await manager.ensure_partitions()

            # Should have checked for existing partitions
            assert mock_check.call_count >= 1
            # Should NOT have created partitions (they exist)
            assert mock_create.call_count == 0

    @pytest.mark.asyncio
    async def test_cleanup_old_partitions(self) -> None:
        """Test cleaning up old partitions beyond retention period."""
        from backend.services.partition_manager import (
            PartitionConfig,
            PartitionInfo,
            PartitionManager,
        )

        config = PartitionConfig("detections", "detected_at", "monthly", retention_months=12)
        manager = PartitionManager(configs=[config])

        # Create mock old partition info
        old_start = datetime.now(UTC) - timedelta(days=400)
        old_partition = PartitionInfo(
            name="detections_y2024m01",
            table_name="detections",
            start_date=old_start,
            end_date=old_start + timedelta(days=31),
            row_count=1000,
        )

        mock_session = AsyncMock()

        with (
            patch.object(manager, "_list_partitions", return_value=[old_partition]) as mock_list,
            patch.object(manager, "_drop_partition") as mock_drop,
            patch("backend.services.partition_manager.get_session") as mock_get_session,
        ):
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await manager.cleanup_old_partitions()

            # Should have listed partitions
            mock_list.assert_called()
            # Should have dropped old partition
            mock_drop.assert_called_with(mock_session, "detections_y2024m01")
            # Should return list of dropped partitions
            assert "detections_y2024m01" in result

    @pytest.mark.asyncio
    async def test_cleanup_old_partitions_keeps_recent(self) -> None:
        """Test that cleanup keeps recent partitions."""
        from backend.services.partition_manager import (
            PartitionConfig,
            PartitionInfo,
            PartitionManager,
        )

        config = PartitionConfig("detections", "detected_at", "monthly", retention_months=12)
        manager = PartitionManager(configs=[config])

        # Create mock recent partition info
        now = datetime.now(UTC)
        recent_start = datetime(now.year, now.month, 1, tzinfo=UTC)
        recent_partition = PartitionInfo(
            name="detections_y2026m01",
            table_name="detections",
            start_date=recent_start,
            end_date=recent_start + timedelta(days=31),
            row_count=1000,
        )

        mock_session = AsyncMock()

        with (
            patch.object(manager, "_list_partitions", return_value=[recent_partition]),
            patch.object(manager, "_drop_partition") as mock_drop,
            patch("backend.services.partition_manager.get_session") as mock_get_session,
        ):
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await manager.cleanup_old_partitions()

            # Should NOT have dropped recent partition
            mock_drop.assert_not_called()
            # Should return empty list
            assert result == []

    @pytest.mark.asyncio
    async def test_get_partition_stats(self) -> None:
        """Test getting partition statistics."""
        from backend.services.partition_manager import (
            PartitionConfig,
            PartitionInfo,
            PartitionManager,
        )

        config = PartitionConfig("detections", "detected_at", "monthly")
        manager = PartitionManager(configs=[config])

        now = datetime.now(UTC)
        partition = PartitionInfo(
            name="detections_y2026m01",
            table_name="detections",
            start_date=datetime(now.year, 1, 1, tzinfo=UTC),
            end_date=datetime(now.year, 2, 1, tzinfo=UTC),
            row_count=5000,
        )

        mock_session = AsyncMock()

        with (
            patch.object(manager, "_list_partitions", return_value=[partition]),
            patch("backend.services.partition_manager.get_session") as mock_get_session,
        ):
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            stats = await manager.get_partition_stats()

            assert "detections" in stats
            assert len(stats["detections"]) == 1
            assert stats["detections"][0]["name"] == "detections_y2026m01"
            assert stats["detections"][0]["row_count"] == 5000


# =============================================================================
# Partition Name Generation Tests
# =============================================================================


class TestAuditLogsPartitioning:
    """Tests specific to audit_logs partitioning."""

    def test_audit_logs_config_in_defaults(self) -> None:
        """Test that audit_logs is included in default configurations."""
        from backend.services.partition_manager import DEFAULT_PARTITION_CONFIGS

        table_names = [c.table_name for c in DEFAULT_PARTITION_CONFIGS]
        assert "audit_logs" in table_names

    def test_audit_logs_config_properties(self) -> None:
        """Test audit_logs partition configuration properties."""
        from backend.services.partition_manager import DEFAULT_PARTITION_CONFIGS

        audit_config = None
        for config in DEFAULT_PARTITION_CONFIGS:
            if config.table_name == "audit_logs":
                audit_config = config
                break

        assert audit_config is not None
        assert audit_config.partition_column == "timestamp"
        assert audit_config.partition_interval == "monthly"
        assert audit_config.retention_months == 12  # Longer retention for compliance

    def test_audit_logs_partition_name_generation(self) -> None:
        """Test partition name generation for audit_logs."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("audit_logs", "timestamp", "monthly")

        date = datetime(2026, 1, 15, tzinfo=UTC)
        name = manager._generate_partition_name(config, date)

        assert name == "audit_logs_y2026m01"

    def test_audit_logs_partition_bounds(self) -> None:
        """Test partition bounds calculation for audit_logs."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("audit_logs", "timestamp", "monthly")

        date = datetime(2026, 3, 15, tzinfo=UTC)
        start, end = manager._calculate_partition_bounds(config, date)

        assert start == datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC)
        assert end == datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)


class TestPartitionNameGeneration:
    """Tests for partition name generation edge cases."""

    def test_generate_name_january(self) -> None:
        """Test name generation for January."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("events", "started_at", "monthly")

        date = datetime(2026, 1, 15, tzinfo=UTC)
        name = manager._generate_partition_name(config, date)

        assert name == "events_y2026m01"

    def test_generate_name_december(self) -> None:
        """Test name generation for December."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("events", "started_at", "monthly")

        date = datetime(2026, 12, 15, tzinfo=UTC)
        name = manager._generate_partition_name(config, date)

        assert name == "events_y2026m12"

    def test_generate_name_different_tables(self) -> None:
        """Test name generation for different tables."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        date = datetime(2026, 6, 15, tzinfo=UTC)

        tables = ["detections", "events", "logs", "gpu_stats", "audit_logs"]
        for table in tables:
            config = PartitionConfig(table, "timestamp", "monthly")
            name = manager._generate_partition_name(config, date)
            assert name == f"{table}_y2026m06"


# =============================================================================
# Integration with Database Tests
# =============================================================================


class TestPartitionManagerDatabaseIntegration:
    """Tests for partition manager database integration.

    These tests verify SQL generation and execution patterns.
    """

    @pytest.mark.asyncio
    async def test_sql_generation_for_create_partition(self) -> None:
        """Test that correct SQL is generated for creating partitions."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("detections", "detected_at", "monthly")

        mock_session = AsyncMock()

        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 2, 1, tzinfo=UTC)

        await manager._create_partition(mock_session, config, "detections_y2026m01", start, end)

        # Verify SQL was executed
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        sql = str(call_args[0][0])

        # Should contain CREATE TABLE with PARTITION OF
        assert "detections_y2026m01" in sql
        # Should contain date range
        assert "2026-01-01" in sql or "2026-02-01" in sql

    @pytest.mark.asyncio
    async def test_sql_generation_for_drop_partition(self) -> None:
        """Test that correct SQL is generated for dropping partitions."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        mock_session = AsyncMock()

        await manager._drop_partition(mock_session, "detections_y2024m01")

        # Verify SQL was executed
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        sql = str(call_args[0][0])

        # Should contain DROP TABLE
        assert "DROP TABLE" in sql.upper()
        assert "detections_y2024m01" in sql

    @pytest.mark.asyncio
    async def test_sql_injection_prevention_in_partition_name(self) -> None:
        """Test that SQL injection is prevented in partition names."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()

        # Attempt SQL injection via table name
        malicious_config = PartitionConfig(
            "detections; DROP TABLE users; --", "detected_at", "monthly"
        )

        # The manager should sanitize table names
        date = datetime(2026, 1, 15, tzinfo=UTC)
        name = manager._generate_partition_name(malicious_config, date)

        # Name should be sanitized (only alphanumeric and underscore)
        assert ";" not in name
        assert "--" not in name
        # Special characters that enable SQL injection should be removed
        # The sanitized name will be "detectionsdroptableusers_y2026m01"
        # Note: "drop" and "table" remain as part of the sanitized string,
        # but they're harmless without special characters to execute SQL
        assert name == "detectionsdroptableusers_y2026m01"
        # Verify no spaces (spaces would allow command separation)
        assert " " not in name
        # Name should end with the date suffix
        assert name.endswith("_y2026m01")


# =============================================================================
# Sanitization and Edge Case Tests
# =============================================================================


class TestSanitization:
    """Tests for name sanitization and edge cases."""

    def test_sanitize_table_name_empty_string(self) -> None:
        """Test sanitization of completely invalid table name."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        # Completely invalid name with only special characters
        result = manager._sanitize_table_name("!@#$%^&*()")

        # Should return 'unknown' as fallback
        assert result == "unknown"

    def test_sanitize_table_name_valid(self) -> None:
        """Test sanitization of valid table name."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        result = manager._sanitize_table_name("valid_table_123")
        assert result == "valid_table_123"

    def test_sanitize_table_name_mixed_case(self) -> None:
        """Test sanitization converts to lowercase."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        result = manager._sanitize_table_name("MyTable123")
        assert result == "mytable123"


# =============================================================================
# Weekly Partition Generation Tests
# =============================================================================


class TestWeeklyPartitionGeneration:
    """Tests for weekly partition generation logic."""

    def test_get_partitions_to_create_weekly(self) -> None:
        """Test generating weekly partitions."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("gpu_stats", "recorded_at", "weekly", retention_months=3)

        # Get weekly partitions for 2 months ahead
        partitions = manager._get_partitions_to_create(config, months_ahead=2)

        # Should generate multiple weeks (at least 8-10 weeks for 2 months)
        assert len(partitions) >= 8
        # All partition names should contain week indicator
        for name, start, end in partitions:
            assert "gpu_stats_y" in name
            assert "w" in name
            # Verify bounds are 7 days apart
            assert (end - start).days == 7


# =============================================================================
# Table Check Tests
# =============================================================================


class TestTableChecks:
    """Tests for table existence and partitioning checks."""

    @pytest.mark.asyncio
    async def test_check_table_is_partitioned_true(self) -> None:
        """Test checking if a table is partitioned when it is."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()
        mock_session = AsyncMock()

        # Mock result returning 'p' for partitioned table
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "p"
        mock_session.execute.return_value = mock_result

        result = await manager._check_table_is_partitioned(mock_session, "detections")
        assert result is True

    @pytest.mark.asyncio
    async def test_check_table_is_partitioned_bytes(self) -> None:
        """Test checking partitioned table when result is bytes."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()
        mock_session = AsyncMock()

        # Mock result returning bytes b'p' for partitioned table
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = b"p"
        mock_session.execute.return_value = mock_result

        result = await manager._check_table_is_partitioned(mock_session, "detections")
        assert result is True

    @pytest.mark.asyncio
    async def test_check_table_is_partitioned_false(self) -> None:
        """Test checking if a table is partitioned when it's not."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()
        mock_session = AsyncMock()

        # Mock result returning 'r' for regular table (not partitioned)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "r"
        mock_session.execute.return_value = mock_result

        result = await manager._check_table_is_partitioned(mock_session, "users")
        assert result is False

    @pytest.mark.asyncio
    async def test_check_table_is_partitioned_not_exists(self) -> None:
        """Test checking if a table is partitioned when it doesn't exist."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()
        mock_session = AsyncMock()

        # Mock result returning None for non-existent table
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await manager._check_table_is_partitioned(mock_session, "nonexistent")
        assert result is False


# =============================================================================
# List Partitions Tests
# =============================================================================


class TestListPartitions:
    """Tests for listing existing partitions."""

    @pytest.mark.asyncio
    async def test_list_partitions_success(self) -> None:
        """Test listing partitions successfully."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("detections", "detected_at", "monthly")

        mock_session = AsyncMock()
        mock_result = MagicMock()

        # Mock database rows
        mock_rows = [
            ("detections_y2026m01", "FOR VALUES FROM ('2026-01-01') TO ('2026-02-01')", 1000),
            ("detections_y2026m02", "FOR VALUES FROM ('2026-02-01') TO ('2026-03-01')", 2000),
        ]
        mock_result.fetchall.return_value = mock_rows
        mock_session.execute.return_value = mock_result

        partitions = await manager._list_partitions(mock_session, config)

        assert len(partitions) == 2
        assert partitions[0].name == "detections_y2026m01"
        assert partitions[0].row_count == 1000
        assert partitions[1].name == "detections_y2026m02"
        assert partitions[1].row_count == 2000

    @pytest.mark.asyncio
    async def test_list_partitions_with_null_row_count(self) -> None:
        """Test listing partitions with NULL row count."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("detections", "detected_at", "monthly")

        mock_session = AsyncMock()
        mock_result = MagicMock()

        # Mock database rows with None row count
        mock_rows = [
            ("detections_y2026m01", "FOR VALUES FROM ('2026-01-01') TO ('2026-02-01')", None),
        ]
        mock_result.fetchall.return_value = mock_rows
        mock_session.execute.return_value = mock_result

        partitions = await manager._list_partitions(mock_session, config)

        assert len(partitions) == 1
        assert partitions[0].row_count == 0  # Should default to 0

    @pytest.mark.asyncio
    async def test_list_partitions_skips_invalid_bounds(self) -> None:
        """Test listing partitions skips entries with unparseable bounds."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("detections", "detected_at", "monthly")

        mock_session = AsyncMock()
        mock_result = MagicMock()

        # Mock database rows with one valid and one invalid bounds
        mock_rows = [
            ("detections_y2026m01", "FOR VALUES FROM ('2026-01-01') TO ('2026-02-01')", 1000),
            ("detections_invalid", "INVALID BOUNDS", 500),  # Should be skipped
        ]
        mock_result.fetchall.return_value = mock_rows
        mock_session.execute.return_value = mock_result

        partitions = await manager._list_partitions(mock_session, config)

        # Should only include the valid partition
        assert len(partitions) == 1
        assert partitions[0].name == "detections_y2026m01"


# =============================================================================
# Parse Partition Bounds Tests
# =============================================================================


class TestParsePartitionBounds:
    """Tests for parsing partition bounds from PostgreSQL."""

    def test_parse_partition_bounds_success(self) -> None:
        """Test parsing valid partition bounds."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        bounds = "FOR VALUES FROM ('2026-01-01') TO ('2026-02-01')"
        start, end = manager._parse_partition_bounds(bounds)

        assert start == datetime(2026, 1, 1, tzinfo=UTC)
        assert end == datetime(2026, 2, 1, tzinfo=UTC)

    def test_parse_partition_bounds_with_datetime(self) -> None:
        """Test parsing bounds with datetime format (including time)."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        bounds = "FOR VALUES FROM ('2026-01-01T00:00:00') TO ('2026-02-01T00:00:00')"
        start, end = manager._parse_partition_bounds(bounds)

        assert start is not None
        assert end is not None
        assert start < end

    def test_parse_partition_bounds_with_spaces(self) -> None:
        """Test parsing bounds with space-separated datetime."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        bounds = "FOR VALUES FROM ('2026-01-01 00:00:00') TO ('2026-02-01 00:00:00')"
        start, end = manager._parse_partition_bounds(bounds)

        assert start is not None
        assert end is not None

    def test_parse_partition_bounds_invalid_format(self) -> None:
        """Test parsing invalid bounds returns None."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        bounds = "INVALID BOUNDS STRING"
        start, end = manager._parse_partition_bounds(bounds)

        assert start is None
        assert end is None

    def test_parse_partition_bounds_missing_from(self) -> None:
        """Test parsing bounds with missing FROM."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        bounds = "TO ('2026-02-01')"
        start, end = manager._parse_partition_bounds(bounds)

        assert start is None
        assert end is None

    def test_parse_partition_bounds_missing_to(self) -> None:
        """Test parsing bounds with missing TO."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        bounds = "FOR VALUES FROM ('2026-01-01')"
        start, end = manager._parse_partition_bounds(bounds)

        assert start is None
        assert end is None

    def test_parse_partition_bounds_invalid_date_format(self) -> None:
        """Test parsing bounds with invalid date format triggers exception."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        # This will match the regex but fail to parse the date
        bounds = "FOR VALUES FROM ('not-a-date') TO ('also-not-a-date')"
        start, end = manager._parse_partition_bounds(bounds)

        # Should handle exception and return None, None
        assert start is None
        assert end is None


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in partition operations."""

    @pytest.mark.asyncio
    async def test_ensure_partitions_skips_non_partitioned_table(self) -> None:
        """Test that ensure_partitions skips non-partitioned tables."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        config = PartitionConfig("regular_table", "timestamp", "monthly")
        manager = PartitionManager(configs=[config])

        mock_session = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None

        with (
            patch.object(manager, "_check_table_is_partitioned", return_value=False),
            patch.object(manager, "_create_partition") as mock_create,
            patch(
                "backend.services.partition_manager.get_session",
                return_value=mock_context,
            ),
        ):
            result = await manager.ensure_partitions()

            # Should not create any partitions
            mock_create.assert_not_called()
            assert result == []

    @pytest.mark.asyncio
    async def test_ensure_partitions_handles_create_error(self) -> None:
        """Test that ensure_partitions handles partition creation errors."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        config = PartitionConfig("detections", "detected_at", "monthly")
        manager = PartitionManager(configs=[config])

        mock_session = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None

        with (
            patch.object(manager, "_check_table_is_partitioned", return_value=True),
            patch.object(manager, "_check_partition_exists", return_value=False),
            patch.object(
                manager,
                "_create_partition",
                side_effect=Exception("Database error"),
            ) as mock_create,
            patch(
                "backend.services.partition_manager.get_session",
                return_value=mock_context,
            ),
        ):
            result = await manager.ensure_partitions()

            # Should attempt to create partitions but handle errors
            assert mock_create.call_count >= 1
            # Should return empty list since all creations failed
            assert result == []

    @pytest.mark.asyncio
    async def test_cleanup_old_partitions_handles_drop_error(self) -> None:
        """Test that cleanup handles partition drop errors."""
        from backend.services.partition_manager import (
            PartitionConfig,
            PartitionInfo,
            PartitionManager,
        )

        config = PartitionConfig("detections", "detected_at", "monthly", retention_months=12)
        manager = PartitionManager(configs=[config])

        # Create mock old partition
        old_start = datetime.now(UTC) - timedelta(days=400)
        old_partition = PartitionInfo(
            name="detections_old",
            table_name="detections",
            start_date=old_start,
            end_date=old_start + timedelta(days=31),
            row_count=1000,
        )

        mock_session = AsyncMock()

        with (
            patch.object(manager, "_list_partitions", return_value=[old_partition]),
            patch.object(
                manager,
                "_drop_partition",
                side_effect=Exception("Cannot drop partition"),
            ) as mock_drop,
            patch("backend.services.partition_manager.get_session") as mock_get_session,
        ):
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await manager.cleanup_old_partitions()

            # Should attempt to drop but handle error
            mock_drop.assert_called_once()
            # Should return empty list since drop failed
            assert result == []


# =============================================================================
# Run Maintenance Tests
# =============================================================================


class TestRunMaintenance:
    """Tests for the run_maintenance method."""

    @pytest.mark.asyncio
    async def test_run_maintenance_full_cycle(self) -> None:
        """Test running full maintenance cycle."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        config = PartitionConfig("detections", "detected_at", "monthly")
        manager = PartitionManager(configs=[config])

        created_partitions = ["detections_y2026m03", "detections_y2026m04"]
        dropped_partitions = ["detections_y2024m01"]
        stats = {
            "detections": [
                {
                    "name": "detections_y2026m01",
                    "start_date": "2026-01-01T00:00:00+00:00",
                    "end_date": "2026-02-01T00:00:00+00:00",
                    "row_count": 1000,
                    "is_expired": False,
                }
            ]
        }

        with (
            patch.object(manager, "ensure_partitions", return_value=created_partitions),
            patch.object(manager, "cleanup_old_partitions", return_value=dropped_partitions),
            patch.object(manager, "get_partition_stats", return_value=stats),
        ):
            result = await manager.run_maintenance()

            assert result["created"] == created_partitions
            assert result["dropped"] == dropped_partitions
            assert result["total_created"] == 2
            assert result["total_dropped"] == 1
            assert result["partition_counts"]["detections"] == 1

    @pytest.mark.asyncio
    async def test_run_maintenance_no_changes(self) -> None:
        """Test running maintenance when no changes are needed."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        config = PartitionConfig("detections", "detected_at", "monthly")
        manager = PartitionManager(configs=[config])

        with (
            patch.object(manager, "ensure_partitions", return_value=[]),
            patch.object(manager, "cleanup_old_partitions", return_value=[]),
            patch.object(manager, "get_partition_stats", return_value={"detections": []}),
        ):
            result = await manager.run_maintenance()

            assert result["created"] == []
            assert result["dropped"] == []
            assert result["total_created"] == 0
            assert result["total_dropped"] == 0
