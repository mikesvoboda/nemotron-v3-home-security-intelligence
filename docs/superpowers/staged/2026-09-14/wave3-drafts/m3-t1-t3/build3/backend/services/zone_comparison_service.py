"""Service for comparing metrics across zones.

This module provides the ZoneComparisonService for comparing zone metrics
such as crossings, dwell time, anomalies, and occupancy across multiple zones.

Example:
    async with get_session() as session:
        service = ZoneComparisonService(session)
        results = await service.compare_zones(
            zone_ids=[1, 2, 3],
            metric="crossings",
            start_time=now - timedelta(days=1),
            end_time=now,
        )
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, func, select

from backend.api.schemas.zone_comparison import ComparisonMetric
from backend.core.logging import get_logger
from backend.models.analytics_zone import LineZone, PolygonZone
from backend.models.dwell_time import DwellTimeRecord
from backend.models.zone_anomaly import ZoneAnomaly

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class ZoneComparisonService:
    """Service for comparing metrics across multiple zones.

    This service aggregates zone data and calculates comparison metrics
    including crossings, dwell time averages, anomaly counts, and
    current occupancy.

    Attributes:
        db: The async database session for operations.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the zone comparison service.

        Args:
            db: An async SQLAlchemy session for database operations.
        """
        self.db = db

    async def compare_zones(
        self,
        zone_ids: list[int],
        metric: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict]:
        """Compare specified metric across zones.

        Args:
            zone_ids: List of zone IDs to compare.
            metric: The metric to compare (crossings, dwell_time, anomalies, occupancy).
            start_time: Start of the comparison time window.
            end_time: End of the comparison time window.

        Returns:
            List of dictionaries containing zone comparison data.
        """
        results: list[dict] = []

        for zone_id in zone_ids:
            try:
                # Get zone info first
                zone_info = await self._get_zone_info(zone_id)
                if zone_info is None:
                    logger.warning(f"Zone {zone_id} not found, skipping")
                    continue

                # Get metric value based on type
                if metric == ComparisonMetric.CROSSINGS:
                    value = await self._get_crossing_count(zone_id)
                elif metric == ComparisonMetric.DWELL_TIME:
                    value = await self._get_avg_dwell_time(zone_id, start_time, end_time)
                elif metric == ComparisonMetric.ANOMALIES:
                    value = await self._get_anomaly_count(zone_id, start_time, end_time)
                elif metric == ComparisonMetric.OCCUPANCY:
                    value = await self._get_current_occupancy(zone_id)
                else:
                    logger.warning(f"Unknown metric '{metric}', defaulting to 0")
                    value = 0.0

                # Calculate trend by comparing to previous period
                trend_percent = await self._calculate_trend(
                    zone_id=zone_id,
                    metric=metric,
                    start_time=start_time,
                    end_time=end_time,
                )

                results.append(
                    {
                        "zone_id": zone_id,
                        "zone_name": zone_info["name"],
                        "zone_type": zone_info["type"],
                        "camera_id": zone_info["camera_id"],
                        "value": value,
                        "trend_percent": trend_percent,
                    }
                )

            except Exception as e:
                logger.warning(
                    f"Failed to get metric '{metric}' for zone {zone_id}: {e}",
                    extra={"zone_id": zone_id, "metric": metric, "error": str(e)},
                )

        return results

    async def _get_zone_info(self, zone_id: int) -> dict | None:
        """Get basic zone information.

        Attempts to find the zone as either a polygon zone or line zone.

        Args:
            zone_id: The zone ID to look up.

        Returns:
            Dictionary with name, type, and camera_id, or None if not found.
        """
        # Try polygon zone first
        stmt = select(PolygonZone).where(PolygonZone.id == zone_id)
        result = await self.db.execute(stmt)
        polygon_zone = result.scalar_one_or_none()

        if polygon_zone is not None:
            return {
                "name": polygon_zone.name,
                "type": polygon_zone.zone_type,
                "camera_id": polygon_zone.camera_id,
            }

        # Try line zone
        line_stmt = select(LineZone).where(LineZone.id == zone_id)
        line_result = await self.db.execute(line_stmt)
        line_zone = line_result.scalar_one_or_none()

        if line_zone is not None:
            return {
                "name": line_zone.name,
                "type": "line",
                "camera_id": line_zone.camera_id,
            }

        return None

    async def _get_crossing_count(self, zone_id: int) -> float:
        """Get total crossing count for a line zone.

        For polygon zones, returns 0 since they don't track crossings.

        Args:
            zone_id: The zone ID.

        Returns:
            Total crossings (in + out) as float.
        """
        stmt = select(LineZone).where(LineZone.id == zone_id)
        result = await self.db.execute(stmt)
        zone = result.scalar_one_or_none()

        if zone is None:
            return 0.0

        return float(zone.in_count + zone.out_count)

    async def _get_avg_dwell_time(
        self,
        zone_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> float:
        """Get average dwell time for a zone in the time window.

        Args:
            zone_id: The zone ID.
            start_time: Start of time window.
            end_time: End of time window.

        Returns:
            Average dwell time in seconds.
        """
        stmt = select(func.avg(DwellTimeRecord.total_seconds)).where(
            and_(
                DwellTimeRecord.zone_id == zone_id,
                DwellTimeRecord.entry_time >= start_time,
                DwellTimeRecord.entry_time <= end_time,
                DwellTimeRecord.exit_time.isnot(None),  # Only completed records
            )
        )
        result = await self.db.execute(stmt)
        avg = result.scalar_one_or_none()

        return float(avg) if avg is not None else 0.0

    async def _get_anomaly_count(
        self,
        zone_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> float:
        """Get count of anomalies for a zone in the time window.

        Args:
            zone_id: The zone ID.
            start_time: Start of time window.
            end_time: End of time window.

        Returns:
            Count of anomalies as float.
        """
        stmt = select(func.count(ZoneAnomaly.id)).where(
            and_(
                ZoneAnomaly.zone_id == str(zone_id),
                ZoneAnomaly.timestamp >= start_time,
                ZoneAnomaly.timestamp <= end_time,
            )
        )
        result = await self.db.execute(stmt)
        count = result.scalar_one_or_none()

        return float(count) if count is not None else 0.0

    async def _get_current_occupancy(self, zone_id: int) -> float:
        """Get current occupancy (count) for a polygon zone.

        For line zones, returns 0 since they don't track occupancy.

        Args:
            zone_id: The zone ID.

        Returns:
            Current occupancy count as float.
        """
        stmt = select(PolygonZone).where(PolygonZone.id == zone_id)
        result = await self.db.execute(stmt)
        zone = result.scalar_one_or_none()

        if zone is None:
            return 0.0

        return float(zone.current_count)

    async def _calculate_trend(
        self,
        zone_id: int,
        metric: str,
        start_time: datetime,
        end_time: datetime,
    ) -> float | None:
        """Calculate trend percentage compared to previous period.

        Args:
            zone_id: The zone ID.
            metric: The metric being compared.
            start_time: Start of current period.
            end_time: End of current period.

        Returns:
            Percentage change from previous period, or None if unable to calculate.
        """
        # Calculate previous period bounds
        period_duration = end_time - start_time
        prev_start = start_time - period_duration
        prev_end = start_time

        # Get values for both periods based on metric
        if metric == ComparisonMetric.DWELL_TIME:
            current_value = await self._get_avg_dwell_time(zone_id, start_time, end_time)
            prev_value = await self._get_avg_dwell_time(zone_id, prev_start, prev_end)
        elif metric == ComparisonMetric.ANOMALIES:
            current_value = await self._get_anomaly_count(zone_id, start_time, end_time)
            prev_value = await self._get_anomaly_count(zone_id, prev_start, prev_end)
        else:
            # For crossings and occupancy, we don't have historical data
            # to compare, so return None
            return None

        # Calculate percentage change
        if prev_value == 0.0:
            if current_value == 0.0:
                return 0.0
            # Avoid division by zero - treat as 100% increase if we had nothing before
            return 100.0

        return round(((current_value - prev_value) / prev_value) * 100.0, 1)


def get_zone_comparison_service(db: AsyncSession) -> ZoneComparisonService:
    """Get a ZoneComparisonService instance for the given session.

    This creates a new ZoneComparisonService bound to the provided session.
    Each request/transaction should use its own session and service.

    Args:
        db: An async SQLAlchemy session for database operations.

    Returns:
        A ZoneComparisonService instance bound to the session.

    Example:
        async with get_session() as session:
            service = get_zone_comparison_service(session)
            results = await service.compare_zones(
                zone_ids=[1, 2],
                metric="crossings",
                start_time=now - timedelta(days=1),
                end_time=now,
            )
    """
    return ZoneComparisonService(db)
