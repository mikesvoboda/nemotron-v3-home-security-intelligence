"""Partition management service for PostgreSQL time-series tables.

This service manages PostgreSQL native partitioning for high-volume tables
(detections, events, logs, gpu_stats) to improve query performance and
enable efficient data retention management.

Features:
    - Automatic partition creation for current and future months
    - Configurable partition intervals (monthly, weekly)
    - Automatic cleanup of old partitions beyond retention period
    - Partition statistics and monitoring
    - Idempotent partition creation (safe to run multiple times)

Usage:
    manager = PartitionManager()
    await manager.ensure_partitions()  # Create missing partitions
    await manager.cleanup_old_partitions()  # Remove expired partitions
    stats = await manager.get_partition_stats()  # Get partition info

Partition Naming Convention:
    - Monthly: {table}_y{year}m{month:02d}  (e.g., detections_y2026m01)
    - Weekly: {table}_y{year}w{week:02d}   (e.g., gpu_stats_y2026w01)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from backend.core.database import get_session
from backend.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


@dataclass(slots=True)
class PartitionConfig:
    """Configuration for a partitioned table.

    Attributes:
        table_name: Name of the partitioned table
        partition_column: Column used for partitioning (must be timestamp)
        partition_interval: Partition interval ('monthly' or 'weekly')
        retention_months: Number of months to retain partitions
    """

    table_name: str
    partition_column: str
    partition_interval: str = "monthly"
    retention_months: int = 12


@dataclass(slots=True)
class PartitionInfo:
    """Information about an existing partition.

    Attributes:
        name: Partition table name
        table_name: Parent table name
        start_date: Start of partition range (inclusive)
        end_date: End of partition range (exclusive)
        row_count: Number of rows in partition
    """

    name: str
    table_name: str
    start_date: datetime
    end_date: datetime
    row_count: int = 0

    def is_expired(self, retention_months: int) -> bool:
        """Check if partition is beyond retention period.

        Args:
            retention_months: Number of months to retain

        Returns:
            True if partition should be dropped
        """
        cutoff = datetime.now(UTC) - timedelta(days=retention_months * 30)
        return self.end_date < cutoff


# Default configurations for high-volume tables
DEFAULT_PARTITION_CONFIGS: list[PartitionConfig] = [
    PartitionConfig(
        table_name="detections",
        partition_column="detected_at",
        partition_interval="monthly",
        retention_months=12,
    ),
    PartitionConfig(
        table_name="events",
        partition_column="started_at",
        partition_interval="monthly",
        retention_months=12,
    ),
    PartitionConfig(
        table_name="logs",
        partition_column="timestamp",
        partition_interval="monthly",
        retention_months=6,
    ),
    PartitionConfig(
        table_name="gpu_stats",
        partition_column="recorded_at",
        partition_interval="weekly",
        retention_months=3,
    ),
    PartitionConfig(
        table_name="audit_logs",
        partition_column="timestamp",
        partition_interval="monthly",
        retention_months=12,  # Keep audit logs longer for compliance
    ),
]


class PartitionManager:
    """Service for managing PostgreSQL table partitions.

    This service handles automatic creation and cleanup of partitions
    for time-series tables. It ensures partitions exist for current
    and future data while removing expired partitions.
    """

    def __init__(
        self,
        configs: list[PartitionConfig] | None = None,
        months_ahead: int = 2,
    ) -> None:
        """Initialize partition manager.

        Args:
            configs: List of partition configurations. If None, uses defaults.
            months_ahead: Number of months ahead to create partitions for.
        """
        self.configs = configs or DEFAULT_PARTITION_CONFIGS
        self.months_ahead = months_ahead

        logger.info(
            "PartitionManager initialized",
            extra={
                "tables": [c.table_name for c in self.configs],
                "months_ahead": months_ahead,
            },
        )

    def _sanitize_table_name(self, name: str) -> str:
        """Sanitize table name to prevent SQL injection.

        Args:
            name: Raw table name

        Returns:
            Sanitized name containing only lowercase alphanumeric and underscore

        Raises:
            ValueError: If the sanitized name would be empty
        """
        # Remove all non-alphanumeric/underscore characters and convert to lowercase
        # This is sufficient to prevent SQL injection since we only allow safe characters
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "", name).lower()

        # Ensure the name is not empty after sanitization
        if not sanitized:
            sanitized = "unknown"

        return sanitized

    def _generate_partition_name(self, config: PartitionConfig, date: datetime) -> str:
        """Generate partition name for a given date.

        Args:
            config: Partition configuration
            date: Date to generate name for

        Returns:
            Partition name (e.g., 'detections_y2026m01')
        """
        table = self._sanitize_table_name(config.table_name)

        if config.partition_interval == "weekly":
            # ISO week number
            week = date.isocalendar()[1]
            return f"{table}_y{date.year}w{week:02d}"
        # Monthly interval (default)
        return f"{table}_y{date.year}m{date.month:02d}"

    def _calculate_partition_bounds(
        self, config: PartitionConfig, date: datetime
    ) -> tuple[datetime, datetime]:
        """Calculate partition start and end dates.

        Args:
            config: Partition configuration
            date: Date within the partition

        Returns:
            Tuple of (start_date, end_date)
        """
        if config.partition_interval == "weekly":
            # Calculate week start (Monday) and end (next Monday)
            days_since_monday = date.weekday()
            start = datetime(date.year, date.month, date.day, 0, 0, 0, tzinfo=UTC) - timedelta(
                days=days_since_monday
            )
            end = start + timedelta(days=7)
            return start, end

        # Monthly interval (default)
        start = datetime(date.year, date.month, 1, 0, 0, 0, tzinfo=UTC)
        if date.month == 12:
            end = datetime(date.year + 1, 1, 1, 0, 0, 0, tzinfo=UTC)
        else:
            end = datetime(date.year, date.month + 1, 1, 0, 0, 0, tzinfo=UTC)

        return start, end

    def _get_partitions_to_create(
        self, config: PartitionConfig, months_ahead: int = 2
    ) -> list[tuple[str, datetime, datetime]]:
        """Determine which partitions need to be created.

        Args:
            config: Partition configuration
            months_ahead: Number of months ahead to create

        Returns:
            List of (name, start_date, end_date) tuples
        """
        partitions = []
        now = datetime.now(UTC)

        if config.partition_interval == "weekly":
            # Generate weekly partitions
            current_date = now
            for _ in range(months_ahead * 4 + 4):  # ~4 weeks per month + buffer
                name = self._generate_partition_name(config, current_date)
                start, end = self._calculate_partition_bounds(config, current_date)
                partitions.append((name, start, end))
                current_date = end
        else:
            # Generate monthly partitions
            current_date = now
            for _ in range(months_ahead + 1):  # Current + months_ahead
                name = self._generate_partition_name(config, current_date)
                start, end = self._calculate_partition_bounds(config, current_date)
                partitions.append((name, start, end))
                # Move to next month
                if current_date.month == 12:
                    current_date = datetime(current_date.year + 1, 1, 1, tzinfo=UTC)
                else:
                    current_date = datetime(
                        current_date.year, current_date.month + 1, 1, tzinfo=UTC
                    )

        return partitions

    async def _check_partition_exists(self, session: AsyncSession, partition_name: str) -> bool:
        """Check if a partition table exists.

        Args:
            session: Database session
            partition_name: Name of partition to check

        Returns:
            True if partition exists
        """
        result = await session.execute(
            text(
                """
                SELECT relname FROM pg_class
                WHERE relname = :name
                AND relkind = 'r'
                """
            ),
            {"name": partition_name},
        )
        return result.scalar_one_or_none() is not None

    async def _check_table_is_partitioned(self, session: AsyncSession, table_name: str) -> bool:
        """Check if a table exists and is partitioned.

        Args:
            session: Database session
            table_name: Name of table to check

        Returns:
            True if table is partitioned
        """
        result = await session.execute(
            text(
                """
                SELECT relkind FROM pg_class
                WHERE relname = :name
                """
            ),
            {"name": table_name},
        )
        row = result.scalar_one_or_none()
        # 'p' indicates a partitioned table
        # Handle both bytes and string returns from PostgreSQL
        if row is None:
            return False
        if isinstance(row, bytes):
            return row == b"p"
        return bool(row == "p")

    async def _create_partition(
        self,
        session: AsyncSession,
        config: PartitionConfig,
        partition_name: str,
        start_date: datetime,
        end_date: datetime,
    ) -> None:
        """Create a new partition.

        Args:
            session: Database session
            config: Partition configuration
            partition_name: Name for new partition
            start_date: Start of partition range (inclusive)
            end_date: End of partition range (exclusive)
        """
        # Sanitize names to prevent SQL injection
        table_name = self._sanitize_table_name(config.table_name)
        safe_partition_name = self._sanitize_table_name(partition_name)

        # Format dates for SQL
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # DDL for partition creation requires dynamic SQL - table names are sanitized, not user input
        sql = f"""
            CREATE TABLE IF NOT EXISTS {safe_partition_name}
            PARTITION OF {table_name}
            FOR VALUES FROM ('{start_str}') TO ('{end_str}')
        """

        await session.execute(text(sql))  # nosemgrep: avoid-sqlalchemy-text

        logger.info(
            f"Created partition {safe_partition_name}",
            extra={
                "table": table_name,
                "partition": safe_partition_name,
                "start": start_str,
                "end": end_str,
            },
        )

    async def _drop_partition(self, session: AsyncSession, partition_name: str) -> None:
        """Drop a partition table.

        Args:
            session: Database session
            partition_name: Name of partition to drop
        """
        safe_name = self._sanitize_table_name(partition_name)
        # DDL for partition drop requires dynamic SQL - table name is sanitized, not user input
        sql = f"DROP TABLE IF EXISTS {safe_name}"

        await session.execute(text(sql))  # nosemgrep: avoid-sqlalchemy-text

        logger.info(f"Dropped partition {safe_name}")

    async def _list_partitions(
        self, session: AsyncSession, config: PartitionConfig
    ) -> list[PartitionInfo]:
        """List existing partitions for a table.

        Args:
            session: Database session
            config: Partition configuration

        Returns:
            List of partition info objects
        """
        table_name = self._sanitize_table_name(config.table_name)

        # Query partition info from pg_catalog
        result = await session.execute(
            text(
                """
                SELECT
                    c.relname AS partition_name,
                    pg_catalog.pg_get_expr(c.relpartbound, c.oid) AS bounds,
                    (SELECT reltuples FROM pg_class WHERE relname = c.relname) AS row_count
                FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_inherits i ON c.oid = i.inhrelid
                JOIN pg_catalog.pg_class p ON i.inhparent = p.oid
                WHERE p.relname = :table_name
                AND c.relkind = 'r'
                ORDER BY c.relname
                """
            ),
            {"table_name": table_name},
        )

        partitions = []
        for row in result.fetchall():
            partition_name = row[0]
            bounds = row[1]  # e.g., "FOR VALUES FROM ('2026-01-01') TO ('2026-02-01')"
            row_count = int(row[2]) if row[2] else 0

            # Parse bounds
            start_date, end_date = self._parse_partition_bounds(bounds)

            if start_date and end_date:
                partitions.append(
                    PartitionInfo(
                        name=partition_name,
                        table_name=table_name,
                        start_date=start_date,
                        end_date=end_date,
                        row_count=row_count,
                    )
                )

        return partitions

    def _parse_partition_bounds(self, bounds: str) -> tuple[datetime | None, datetime | None]:
        """Parse partition bounds from PostgreSQL expression.

        Args:
            bounds: PostgreSQL bounds expression

        Returns:
            Tuple of (start_date, end_date) or (None, None) if parsing fails
        """
        try:
            # Extract dates from bounds like "FOR VALUES FROM ('2026-01-01') TO ('2026-02-01')"
            from_match = re.search(r"FROM \('([^']+)'\)", bounds)
            to_match = re.search(r"TO \('([^']+)'\)", bounds)

            if from_match and to_match:
                from_str = from_match.group(1)
                to_str = to_match.group(1)

                # Parse date strings (handle both date and datetime formats)
                if "T" in from_str or " " in from_str:
                    # Datetime format
                    start = datetime.fromisoformat(from_str.replace(" ", "T"))
                else:
                    # Date format
                    start = datetime.strptime(from_str, "%Y-%m-%d").replace(tzinfo=UTC)

                if "T" in to_str or " " in to_str:
                    end = datetime.fromisoformat(to_str.replace(" ", "T"))
                else:
                    end = datetime.strptime(to_str, "%Y-%m-%d").replace(tzinfo=UTC)

                # Ensure timezone awareness
                if start.tzinfo is None:
                    start = start.replace(tzinfo=UTC)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=UTC)

                return start, end
        except Exception:
            logger.warning(f"Failed to parse partition bounds: {bounds}", exc_info=True)

        return None, None

    async def ensure_partitions(self) -> list[str]:
        """Ensure all required partitions exist.

        Creates partitions for current and future months if they don't exist.

        Returns:
            List of newly created partition names
        """
        created = []

        async with get_session() as session:
            for config in self.configs:
                # Check if parent table is partitioned
                if not await self._check_table_is_partitioned(session, config.table_name):
                    logger.warning(f"Table {config.table_name} is not partitioned, skipping")
                    continue

                # Get partitions to create
                partitions = self._get_partitions_to_create(config, self.months_ahead)

                for name, start, end in partitions:
                    # Check if partition exists
                    if await self._check_partition_exists(session, name):
                        continue

                    # Create partition
                    try:
                        await self._create_partition(session, config, name, start, end)
                        created.append(name)
                    except Exception as e:
                        logger.error(
                            f"Failed to create partition {name}: {e}",
                            exc_info=True,
                        )

            await session.commit()

        if created:
            logger.info(
                f"Created {len(created)} partitions",
                extra={"partitions": created},
            )

        return created

    async def cleanup_old_partitions(self) -> list[str]:
        """Remove partitions beyond retention period.

        Returns:
            List of dropped partition names
        """
        dropped = []

        async with get_session() as session:
            for config in self.configs:
                # Get existing partitions
                partitions = await self._list_partitions(session, config)

                for partition in partitions:
                    if partition.is_expired(config.retention_months):
                        try:
                            await self._drop_partition(session, partition.name)
                            dropped.append(partition.name)
                        except Exception as e:
                            logger.error(
                                f"Failed to drop partition {partition.name}: {e}",
                                exc_info=True,
                            )

            await session.commit()

        if dropped:
            logger.info(
                f"Dropped {len(dropped)} old partitions",
                extra={"partitions": dropped},
            )

        return dropped

    async def get_partition_stats(self) -> dict[str, list[dict[str, Any]]]:
        """Get statistics for all partitions.

        Returns:
            Dictionary mapping table names to lists of partition stats
        """
        stats: dict[str, list[dict[str, Any]]] = {}

        async with get_session() as session:
            for config in self.configs:
                partitions = await self._list_partitions(session, config)

                stats[config.table_name] = [
                    {
                        "name": p.name,
                        "start_date": p.start_date.isoformat(),
                        "end_date": p.end_date.isoformat(),
                        "row_count": p.row_count,
                        "is_expired": p.is_expired(config.retention_months),
                    }
                    for p in partitions
                ]

        return stats

    async def run_maintenance(self) -> dict[str, Any]:
        """Run full partition maintenance.

        Creates missing partitions and cleans up old ones.

        Returns:
            Dictionary with maintenance results
        """
        logger.info("Starting partition maintenance")

        created = await self.ensure_partitions()
        dropped = await self.cleanup_old_partitions()
        stats = await self.get_partition_stats()

        result = {
            "created": created,
            "dropped": dropped,
            "total_created": len(created),
            "total_dropped": len(dropped),
            "partition_counts": {table: len(partitions) for table, partitions in stats.items()},
        }

        logger.info(
            "Partition maintenance completed",
            extra=result,
        )

        return result
