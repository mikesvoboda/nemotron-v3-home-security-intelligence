"""Zone baseline service for managing zone activity baselines.

This module provides the ZoneBaselineService for computing and retrieving
zone activity baselines used by the anomaly detection system.

Note: This is a stub implementation that will be fully developed in
a separate task (NEM-3197).

Related: NEM-3197 (Backend Baseline Data Service)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.models.zone_baseline import ZoneActivityBaseline


class ZoneBaselineService:
    """Service for managing zone activity baselines.

    Provides methods for computing and retrieving zone baselines
    that are used for anomaly detection.
    """

    async def get_baseline(
        self, zone_id: str, session: AsyncSession | None = None
    ) -> ZoneActivityBaseline | None:
        """Get baseline for a zone.

        Args:
            zone_id: The zone ID.
            session: Optional database session.

        Returns:
            The zone baseline, or None if not found.
        """
        from backend.models.zone_baseline import ZoneActivityBaseline

        if session is None:
            return None

        query = select(ZoneActivityBaseline).where(ZoneActivityBaseline.zone_id == zone_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()


_zone_baseline_service: ZoneBaselineService | None = None


def get_zone_baseline_service() -> ZoneBaselineService:
    """Get or create the singleton zone baseline service.

    Returns:
        The ZoneBaselineService singleton.
    """
    global _zone_baseline_service  # noqa: PLW0603
    if _zone_baseline_service is None:
        _zone_baseline_service = ZoneBaselineService()
    return _zone_baseline_service


def reset_zone_baseline_service() -> None:
    """Reset the singleton zone baseline service.

    Useful for testing.
    """
    global _zone_baseline_service  # noqa: PLW0603
    _zone_baseline_service = None
