"""Repository for Summary entity database operations.

This module provides the SummaryRepository class which extends the generic
Repository base class with summary-specific query methods.

Example:
    async with get_session() as session:
        repo = SummaryRepository(session)
        latest_hourly = await repo.get_latest_by_type(SummaryType.HOURLY)
        all_latest = await repo.get_latest_all()
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, desc, select

from backend.models.summary import Summary, SummaryType
from backend.repositories.base import Repository


class SummaryRepository(Repository[Summary]):
    """Repository for Summary entity database operations.

    Provides CRUD operations inherited from Repository base class plus
    summary-specific query methods for retrieving latest summaries and
    cleanup of old summaries.

    Attributes:
        model_class: Set to Summary for type inference and query construction.

    Example:
        async with get_session() as session:
            repo = SummaryRepository(session)

            # Get latest hourly summary
            hourly = await repo.get_latest_by_type(SummaryType.HOURLY)

            # Get both latest summaries
            all_latest = await repo.get_latest_all()

            # Clean up old summaries (7 days retention)
            deleted = await repo.cleanup_old_summaries()
    """

    model_class = Summary

    async def get_latest_by_type(self, summary_type: SummaryType | str) -> Summary | None:
        """Get the latest summary of the specified type.

        Retrieves the most recently created summary of the given type,
        ordered by created_at descending.

        Args:
            summary_type: The type of summary to retrieve ('hourly' or 'daily').
                          Can be a SummaryType enum or a string.

        Returns:
            The latest Summary of the specified type, or None if no summaries
            exist for that type.

        Example:
            latest_hourly = await repo.get_latest_by_type(SummaryType.HOURLY)
            latest_daily = await repo.get_latest_by_type("daily")
        """
        # Normalize type to string value
        type_value = summary_type.value if isinstance(summary_type, SummaryType) else summary_type

        stmt = (
            select(Summary)
            .where(Summary.summary_type == type_value)
            .order_by(desc(Summary.created_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_all(self) -> dict[str, Summary | None]:
        """Get the latest hourly and daily summaries in one call.

        Retrieves both the latest hourly and daily summaries efficiently.
        This is optimized for the dashboard display which needs both summaries.

        Returns:
            A dictionary with keys 'hourly' and 'daily', each containing
            the latest Summary of that type or None if no summary exists.

        Example:
            summaries = await repo.get_latest_all()
            hourly = summaries["hourly"]  # Summary or None
            daily = summaries["daily"]    # Summary or None
        """
        hourly = await self.get_latest_by_type(SummaryType.HOURLY)
        daily = await self.get_latest_by_type(SummaryType.DAILY)

        return {
            "hourly": hourly,
            "daily": daily,
        }

    async def cleanup_old_summaries(self, days: int = 7) -> int:
        """Delete summaries older than the specified retention period.

        Removes summaries where created_at is older than (now - days).
        This is called by the cleanup service to maintain database hygiene.

        Args:
            days: Number of days to retain summaries. Default is 7 days
                  as specified in the design document.

        Returns:
            The number of summaries deleted.

        Example:
            # Delete summaries older than 7 days (default)
            deleted_count = await repo.cleanup_old_summaries()

            # Delete summaries older than 3 days
            deleted_count = await repo.cleanup_old_summaries(days=3)
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = delete(Summary).where(Summary.created_at < cutoff)
        result = await self.session.execute(stmt)
        await self.session.flush()

        deleted_count: int = result.rowcount or 0  # type: ignore[attr-defined]
        return deleted_count

    async def create_summary(
        self,
        summary_type: SummaryType | str,
        content: str,
        event_count: int,
        event_ids: list[int] | None,
        window_start: datetime,
        window_end: datetime,
        generated_at: datetime,
    ) -> Summary:
        """Create a new summary with the specified parameters.

        This is a convenience method that creates a Summary instance and
        persists it to the database. It handles type normalization and
        provides a cleaner API than constructing Summary objects directly.

        Args:
            summary_type: The type of summary ('hourly' or 'daily').
                          Can be a SummaryType enum or a string.
            content: The LLM-generated narrative text.
            event_count: Number of high/critical events included.
            event_ids: List of event IDs that were summarized, or None.
            window_start: Start of the time window covered.
            window_end: End of the time window covered.
            generated_at: Timestamp when the LLM produced this summary.

        Returns:
            The created Summary with database-generated values (id, created_at).

        Example:
            summary = await repo.create_summary(
                summary_type=SummaryType.HOURLY,
                content="One critical event detected at the front door.",
                event_count=1,
                event_ids=[101],
                window_start=datetime.now(UTC) - timedelta(hours=1),
                window_end=datetime.now(UTC),
                generated_at=datetime.now(UTC),
            )
        """
        # Normalize type to string value
        type_value = summary_type.value if isinstance(summary_type, SummaryType) else summary_type

        summary = Summary(
            summary_type=type_value,
            content=content,
            event_count=event_count,
            event_ids=event_ids,
            window_start=window_start,
            window_end=window_end,
            generated_at=generated_at,
        )

        return await self.create(summary)
