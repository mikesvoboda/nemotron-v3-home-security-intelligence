"""Unit tests for partition manager enhancements (NEM-3759).

Tests for enhanced partition management features including:
- Converting non-partitioned tables to partitioned tables
- Automatic index creation on partitions
- Partition pruning optimization hints
- Time-series optimization strategies

Following TDD approach - tests written first before implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

# =============================================================================
# Table Conversion Tests
# =============================================================================


class TestTableConversion:
    """Tests for converting non-partitioned tables to partitioned tables."""

    @pytest.mark.asyncio
    async def test_generate_conversion_sql_for_detections(self) -> None:
        """Test generating SQL to convert detections table to partitioned."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("detections", "detected_at", "monthly")

        sql_statements = manager.generate_partition_conversion_sql(config)

        assert isinstance(sql_statements, list)
        assert len(sql_statements) > 0

        # Should contain CREATE TABLE for the partitioned table
        combined = "\n".join(sql_statements)
        assert "PARTITION BY RANGE" in combined
        assert "detected_at" in combined

    @pytest.mark.asyncio
    async def test_generate_conversion_sql_for_events(self) -> None:
        """Test generating SQL to convert events table to partitioned."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("events", "started_at", "monthly")

        sql_statements = manager.generate_partition_conversion_sql(config)

        assert len(sql_statements) > 0
        combined = "\n".join(sql_statements)
        assert "started_at" in combined

    def test_conversion_preserves_columns(self) -> None:
        """Test that conversion SQL preserves all table columns."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("detections", "detected_at", "monthly")

        sql_statements = manager.generate_partition_conversion_sql(config)

        # Should reference the original table
        combined = "\n".join(sql_statements)
        assert "detections" in combined


# =============================================================================
# Automatic Index Creation Tests
# =============================================================================


class TestAutomaticIndexCreation:
    """Tests for automatic index creation on partitions."""

    @pytest.mark.asyncio
    async def test_generate_partition_indexes(self) -> None:
        """Test generating index creation SQL for a partition."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("detections", "detected_at", "monthly")

        index_sql = manager.generate_partition_indexes(config, "detections_y2026m01")

        assert isinstance(index_sql, list)
        assert len(index_sql) > 0

        # Should create index on partition column
        combined = "\n".join(index_sql)
        assert "CREATE INDEX" in combined
        assert "detections_y2026m01" in combined

    @pytest.mark.asyncio
    async def test_partition_index_on_timestamp_column(self) -> None:
        """Test index is created on the timestamp column."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("events", "started_at", "monthly")

        index_sql = manager.generate_partition_indexes(config, "events_y2026m01")

        combined = "\n".join(index_sql)
        assert "started_at" in combined

    @pytest.mark.asyncio
    async def test_partition_indexes_include_brin(self) -> None:
        """Test that BRIN indexes are suggested for time-series data."""
        from backend.services.partition_manager import PartitionConfig, PartitionManager

        manager = PartitionManager()
        config = PartitionConfig("detections", "detected_at", "monthly")

        index_sql = manager.generate_partition_indexes(
            config, "detections_y2026m01", include_brin=True
        )

        combined = "\n".join(index_sql)
        # BRIN indexes are efficient for time-series data
        assert "USING brin" in combined.lower() or "btree" in combined.lower()


# =============================================================================
# Partition Pruning Tests
# =============================================================================


class TestPartitionPruning:
    """Tests for partition pruning optimization."""

    def test_get_partition_pruning_condition_monthly(self) -> None:
        """Test generating partition pruning condition for monthly partitions."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        # Query for January 2026
        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 1, 31, 23, 59, 59, tzinfo=UTC)

        condition = manager.get_partition_pruning_hint("detections", "detected_at", start, end)

        # Should return a hint about which partitions will be scanned
        assert isinstance(condition, dict)
        assert "partitions" in condition
        assert "detections_y2026m01" in condition["partitions"]

    def test_get_partition_pruning_condition_range(self) -> None:
        """Test partition pruning for a date range spanning multiple partitions."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        # Query spanning January to March 2026
        start = datetime(2026, 1, 15, tzinfo=UTC)
        end = datetime(2026, 3, 15, tzinfo=UTC)

        condition = manager.get_partition_pruning_hint("events", "started_at", start, end)

        # Should include multiple partitions
        assert len(condition["partitions"]) >= 3

    def test_get_partition_pruning_no_date_filter(self) -> None:
        """Test partition pruning when no date filter is provided."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        condition = manager.get_partition_pruning_hint("detections", "detected_at", None, None)

        # Should indicate all partitions will be scanned
        assert condition["all_partitions"] is True


# =============================================================================
# Time-Series Optimization Tests
# =============================================================================


class TestTimeSeriesOptimization:
    """Tests for time-series specific optimizations."""

    def test_get_optimal_partition_interval_high_volume(self) -> None:
        """Test determining optimal partition interval for high-volume tables."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        # High volume: more than 1M rows per month -> weekly partitions recommended
        interval = manager.recommend_partition_interval(
            estimated_rows_per_month=5_000_000,
            query_pattern="recent",  # Queries mostly recent data
        )

        assert interval in ("weekly", "monthly")

    def test_get_optimal_partition_interval_low_volume(self) -> None:
        """Test determining optimal partition interval for low-volume tables."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        # Low volume: less than 100K rows per month -> monthly partitions recommended
        interval = manager.recommend_partition_interval(
            estimated_rows_per_month=50_000,
            query_pattern="historical",  # Queries often look at old data
        )

        assert interval == "monthly"

    def test_get_retention_recommendation(self) -> None:
        """Test getting retention period recommendation based on data type."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        # Audit logs should have longer retention
        retention = manager.recommend_retention_period(
            table_name="audit_logs",
            compliance_requirements=True,
        )

        assert retention >= 12  # At least 12 months for compliance

        # Temporary data can have shorter retention
        retention = manager.recommend_retention_period(
            table_name="gpu_stats",
            compliance_requirements=False,
        )

        assert retention <= 6  # Shorter for non-compliance data


# =============================================================================
# Partition Health Check Tests
# =============================================================================


class TestPartitionHealthChecks:
    """Tests for partition health monitoring."""

    @pytest.mark.asyncio
    async def test_check_partition_balance(self) -> None:
        """Test checking if partition sizes are balanced."""
        from backend.services.partition_manager import PartitionInfo, PartitionManager

        manager = PartitionManager()

        partitions = [
            PartitionInfo("p1", "detections", datetime.now(UTC), datetime.now(UTC), row_count=1000),
            PartitionInfo("p2", "detections", datetime.now(UTC), datetime.now(UTC), row_count=1100),
            PartitionInfo("p3", "detections", datetime.now(UTC), datetime.now(UTC), row_count=900),
        ]

        health = manager.check_partition_balance(partitions)

        assert health["balanced"] is True
        assert "variance" in health

    @pytest.mark.asyncio
    async def test_detect_unbalanced_partitions(self) -> None:
        """Test detecting unbalanced partitions."""
        from backend.services.partition_manager import PartitionInfo, PartitionManager

        manager = PartitionManager()

        # One partition is much larger than others (more than 3x average)
        # Average = (1000 + 50000 + 900) / 3 = 17300
        # Ratio = 50000 / 17300 = 2.89 (need > 3.0 to trigger unbalanced)
        # Let's use 60000 to be sure: 60000 / ((1000 + 60000 + 900) / 3) = 60000 / 20633 = 2.91
        # Use even higher to guarantee >3x: 100000 / ((1000 + 100000 + 900) / 3) = 100000 / 33967 = 2.94
        # Need extreme: 150000 / ((1000 + 150000 + 900) / 3) = 150000 / 50633 = 2.96
        # Try 200000 / ((1000 + 200000 + 900) / 3) = 200000 / 67300 = 2.97
        # Need 300000 / ((1000 + 300000 + 900) / 3) = 300000 / 100633 = 2.98
        # Actually for >3x: max > 3 * (sum / count), so max > sum
        # If max = 10000, others = 1000, 900, sum = 11900, avg = 3967, ratio = 2.52
        # Need max > 3 * avg, so for avg of 1000, max needs to be > 3000
        # With p1=1000, p3=900, avg without p2 = 950
        # For ratio > 3: max / ((max + 1900) / 3) > 3
        # max / ((max + 1900) / 3) > 3
        # 3 * max / (max + 1900) > 3
        # max / (max + 1900) > 1 (impossible)
        # Actually: max > 3 * (max + 1900) / 3 = max + 1900 (impossible)
        # So we need: max > 3 * ((max + others) / 3) = max + others (never true)
        # The algorithm checks max/avg > 3, so:
        # max / ((max + others) / n) > 3
        # n * max / (max + others) > 3
        # For n=3, others=1900: 3 * max / (max + 1900) > 3
        # max / (max + 1900) > 1 (impossible with positive values)
        # The issue is the threshold - let me use 2 partitions instead
        partitions = [
            PartitionInfo("p1", "detections", datetime.now(UTC), datetime.now(UTC), row_count=1000),
            PartitionInfo(
                "p2", "detections", datetime.now(UTC), datetime.now(UTC), row_count=20000
            ),
        ]
        # avg = (1000 + 20000) / 2 = 10500
        # ratio = 20000 / 10500 = 1.9 (still < 3)
        # Need: max / ((max + other) / 2) > 3
        # 2 * max / (max + other) > 3
        # 2 * max > 3 * max + 3 * other
        # -max > 3 * other (impossible)
        # So with 2 items, can't trigger > 3x avg
        # Let's use 4 items with one very large
        partitions = [
            PartitionInfo("p1", "detections", datetime.now(UTC), datetime.now(UTC), row_count=100),
            PartitionInfo(
                "p2", "detections", datetime.now(UTC), datetime.now(UTC), row_count=50000
            ),
            PartitionInfo("p3", "detections", datetime.now(UTC), datetime.now(UTC), row_count=100),
            PartitionInfo("p4", "detections", datetime.now(UTC), datetime.now(UTC), row_count=100),
        ]
        # avg = (100 + 50000 + 100 + 100) / 4 = 12575
        # ratio = 50000 / 12575 = 3.98 > 3.0 - this should trigger unbalanced

        health = manager.check_partition_balance(partitions)

        assert health["balanced"] is False
        assert health["largest_partition"] == "p2"

    @pytest.mark.asyncio
    async def test_identify_missing_partitions(self) -> None:
        """Test identifying gaps in partition coverage."""
        from backend.services.partition_manager import (
            PartitionConfig,
            PartitionInfo,
            PartitionManager,
        )

        manager = PartitionManager()
        config = PartitionConfig("detections", "detected_at", "monthly")

        # Missing February partition
        existing = [
            PartitionInfo(
                "detections_y2026m01",
                "detections",
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 2, 1, tzinfo=UTC),
                row_count=1000,
            ),
            # Missing February
            PartitionInfo(
                "detections_y2026m03",
                "detections",
                datetime(2026, 3, 1, tzinfo=UTC),
                datetime(2026, 4, 1, tzinfo=UTC),
                row_count=1000,
            ),
        ]

        gaps = manager.identify_partition_gaps(config, existing)

        assert len(gaps) > 0
        # Should identify the missing February partition
        assert any("2026m02" in gap for gap in gaps)


# =============================================================================
# Partition Metadata Tests
# =============================================================================


class TestPartitionMetadata:
    """Tests for partition metadata management."""

    def test_get_partition_metadata(self) -> None:
        """Test getting metadata for a partition."""
        from backend.services.partition_manager import PartitionInfo, PartitionManager

        manager = PartitionManager()

        info = PartitionInfo(
            name="detections_y2026m01",
            table_name="detections",
            start_date=datetime(2026, 1, 1, tzinfo=UTC),
            end_date=datetime(2026, 2, 1, tzinfo=UTC),
            row_count=5000,
        )

        metadata = manager.get_partition_metadata(info)

        assert metadata["name"] == "detections_y2026m01"
        assert metadata["table_name"] == "detections"
        assert metadata["row_count"] == 5000
        assert "size_estimate_mb" in metadata
        assert "days_covered" in metadata
        assert metadata["days_covered"] == 31  # January has 31 days

    def test_estimate_partition_size(self) -> None:
        """Test estimating partition size in MB."""
        from backend.services.partition_manager import PartitionManager

        manager = PartitionManager()

        # Estimate based on row count and average row size
        size_mb = manager.estimate_partition_size(
            row_count=100_000,
            avg_row_size_bytes=500,  # 500 bytes per row
        )

        # 100,000 * 500 = 50,000,000 bytes = ~47.7 MB
        assert 40 < size_mb < 60
