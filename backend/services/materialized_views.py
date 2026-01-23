"""Service for managing and querying materialized views.

This module provides utilities for:
1. Refreshing dashboard materialized views
2. Querying pre-aggregated analytics data
3. Managing refresh schedules

Materialized views provide significant performance improvements for dashboard
analytics by pre-computing expensive aggregations.

Related Linear issues:
- NEM-3389: Create materialized views for dashboard aggregations
- NEM-3390: Use JSON_TABLE for complex enrichment queries
"""

from datetime import date
from typing import Any, ClassVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging import get_logger

logger = get_logger(__name__)


class MaterializedViewService:
    """Service for managing and querying materialized views.

    This service provides methods to:
    - Refresh all dashboard materialized views
    - Query pre-aggregated analytics data
    - Check view freshness
    """

    # List of materialized views managed by this service
    MANAGED_VIEWS: ClassVar[list[str]] = [
        "mv_daily_detection_counts",
        "mv_hourly_event_stats",
        "mv_detection_type_distribution",
        "mv_entity_tracking_summary",
        "mv_risk_score_aggregations",
        "mv_enrichment_summary",
    ]

    def __init__(self, session: AsyncSession):
        """Initialize the service with a database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def refresh_all_views(self, concurrently: bool = True) -> dict[str, bool]:
        """Refresh all dashboard materialized views.

        Args:
            concurrently: If True, use CONCURRENTLY option (allows reads during refresh).
                         Requires unique index on each view.

        Returns:
            Dictionary mapping view name to success status
        """
        results: dict[str, bool] = {}

        if concurrently:
            # Use the stored function for concurrent refresh
            try:
                await self.session.execute(text("SELECT refresh_dashboard_materialized_views()"))
                await self.session.commit()
                for view in self.MANAGED_VIEWS:
                    results[view] = True
                logger.info("Refreshed all materialized views concurrently")
            except Exception as e:
                logger.error(f"Failed to refresh materialized views: {e}")
                await self.session.rollback()
                for view in self.MANAGED_VIEWS:
                    results[view] = False
        else:
            # Refresh each view individually (blocks reads during refresh)
            for view in self.MANAGED_VIEWS:
                try:
                    await self.session.execute(text(f"REFRESH MATERIALIZED VIEW {view}"))
                    await self.session.commit()
                    results[view] = True
                    logger.info(f"Refreshed materialized view: {view}")
                except Exception as e:
                    logger.error(f"Failed to refresh {view}: {e}")
                    await self.session.rollback()
                    results[view] = False

        return results

    async def refresh_view(self, view_name: str, concurrently: bool = True) -> bool:
        """Refresh a specific materialized view.

        Args:
            view_name: Name of the materialized view to refresh
            concurrently: If True, use CONCURRENTLY option

        Returns:
            True if refresh succeeded, False otherwise
        """
        if view_name not in self.MANAGED_VIEWS:
            logger.warning(f"Unknown materialized view: {view_name}")
            return False

        concurrent_clause = "CONCURRENTLY" if concurrently else ""

        try:
            await self.session.execute(
                text(f"REFRESH MATERIALIZED VIEW {concurrent_clause} {view_name}")
            )
            await self.session.commit()
            logger.info(f"Refreshed materialized view: {view_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to refresh {view_name}: {e}")
            await self.session.rollback()
            return False

    async def get_daily_detection_counts(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        camera_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get daily detection counts from materialized view.

        Args:
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            camera_id: Filter by specific camera

        Returns:
            List of daily detection count records
        """
        query = """
            SELECT
                detection_date,
                camera_id,
                object_type,
                detection_count,
                avg_confidence,
                first_detection,
                last_detection
            FROM mv_daily_detection_counts
            WHERE 1=1
        """
        params: dict[str, Any] = {}

        if start_date:
            query += " AND detection_date >= :start_date"
            params["start_date"] = start_date
        if end_date:
            query += " AND detection_date <= :end_date"
            params["end_date"] = end_date
        if camera_id:
            query += " AND camera_id = :camera_id"
            params["camera_id"] = camera_id

        query += " ORDER BY detection_date DESC, camera_id, object_type"

        result = await self.session.execute(text(query), params)
        rows = result.fetchall()

        return [
            {
                "detection_date": row.detection_date,
                "camera_id": row.camera_id,
                "object_type": row.object_type,
                "detection_count": row.detection_count,
                "avg_confidence": float(row.avg_confidence) if row.avg_confidence else None,
                "first_detection": row.first_detection,
                "last_detection": row.last_detection,
            }
            for row in rows
        ]

    async def get_hourly_event_stats(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        camera_id: str | None = None,
        risk_level: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get hourly event statistics from materialized view.

        Args:
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            camera_id: Filter by specific camera
            risk_level: Filter by risk level (low, medium, high, critical)

        Returns:
            List of hourly event statistics records
        """
        query = """
            SELECT
                event_date,
                event_hour,
                camera_id,
                risk_level,
                event_count,
                avg_risk_score,
                reviewed_count,
                fast_path_count
            FROM mv_hourly_event_stats
            WHERE 1=1
        """
        params: dict[str, Any] = {}

        if start_date:
            query += " AND event_date >= :start_date"
            params["start_date"] = start_date
        if end_date:
            query += " AND event_date <= :end_date"
            params["end_date"] = end_date
        if camera_id:
            query += " AND camera_id = :camera_id"
            params["camera_id"] = camera_id
        if risk_level:
            query += " AND risk_level = :risk_level"
            params["risk_level"] = risk_level

        query += " ORDER BY event_date DESC, event_hour, camera_id"

        result = await self.session.execute(text(query), params)
        rows = result.fetchall()

        return [
            {
                "event_date": row.event_date,
                "event_hour": row.event_hour,
                "camera_id": row.camera_id,
                "risk_level": row.risk_level,
                "event_count": row.event_count,
                "avg_risk_score": float(row.avg_risk_score) if row.avg_risk_score else None,
                "reviewed_count": row.reviewed_count,
                "fast_path_count": row.fast_path_count,
            }
            for row in rows
        ]

    async def get_risk_score_aggregations(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        camera_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get risk score aggregations from materialized view.

        Args:
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            camera_id: Filter by specific camera

        Returns:
            List of risk score aggregation records
        """
        query = """
            SELECT
                camera_id,
                event_date,
                total_events,
                low_risk_count,
                medium_risk_count,
                high_risk_count,
                critical_risk_count,
                avg_risk_score,
                median_risk_score,
                p95_risk_score,
                max_risk_score
            FROM mv_risk_score_aggregations
            WHERE 1=1
        """
        params: dict[str, Any] = {}

        if start_date:
            query += " AND event_date >= :start_date"
            params["start_date"] = start_date
        if end_date:
            query += " AND event_date <= :end_date"
            params["end_date"] = end_date
        if camera_id:
            query += " AND camera_id = :camera_id"
            params["camera_id"] = camera_id

        query += " ORDER BY event_date DESC, camera_id"

        result = await self.session.execute(text(query), params)
        rows = result.fetchall()

        return [
            {
                "camera_id": row.camera_id,
                "event_date": row.event_date,
                "total_events": row.total_events,
                "low_risk_count": row.low_risk_count,
                "medium_risk_count": row.medium_risk_count,
                "high_risk_count": row.high_risk_count,
                "critical_risk_count": row.critical_risk_count,
                "avg_risk_score": float(row.avg_risk_score) if row.avg_risk_score else None,
                "median_risk_score": float(row.median_risk_score)
                if row.median_risk_score
                else None,
                "p95_risk_score": float(row.p95_risk_score) if row.p95_risk_score else None,
                "max_risk_score": row.max_risk_score,
            }
            for row in rows
        ]

    async def get_detection_type_distribution(
        self, camera_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Get detection type distribution from materialized view.

        Args:
            camera_id: Filter by specific camera

        Returns:
            List of detection type distribution records
        """
        query = """
            SELECT
                camera_id,
                object_type,
                total_count,
                last_24h_count,
                last_7d_count,
                last_30d_count,
                avg_confidence,
                first_seen,
                last_seen
            FROM mv_detection_type_distribution
            WHERE 1=1
        """
        params: dict[str, Any] = {}

        if camera_id:
            query += " AND camera_id = :camera_id"
            params["camera_id"] = camera_id

        query += " ORDER BY camera_id, total_count DESC"

        result = await self.session.execute(text(query), params)
        rows = result.fetchall()

        return [
            {
                "camera_id": row.camera_id,
                "object_type": row.object_type,
                "total_count": row.total_count,
                "last_24h_count": row.last_24h_count,
                "last_7d_count": row.last_7d_count,
                "last_30d_count": row.last_30d_count,
                "avg_confidence": float(row.avg_confidence) if row.avg_confidence else None,
                "first_seen": row.first_seen,
                "last_seen": row.last_seen,
            }
            for row in rows
        ]

    async def get_entity_tracking_summary(self) -> list[dict[str, Any]]:
        """Get entity tracking summary from materialized view.

        Returns:
            List of entity tracking summary records
        """
        query = """
            SELECT
                entity_type,
                trust_status,
                entity_count,
                total_detections,
                avg_detections_per_entity,
                earliest_first_seen,
                latest_last_seen,
                active_last_24h,
                active_last_7d
            FROM mv_entity_tracking_summary
            ORDER BY entity_type, trust_status
        """

        result = await self.session.execute(text(query))
        rows = result.fetchall()

        return [
            {
                "entity_type": row.entity_type,
                "trust_status": row.trust_status,
                "entity_count": row.entity_count,
                "total_detections": row.total_detections,
                "avg_detections_per_entity": (
                    float(row.avg_detections_per_entity) if row.avg_detections_per_entity else None
                ),
                "earliest_first_seen": row.earliest_first_seen,
                "latest_last_seen": row.latest_last_seen,
                "active_last_24h": row.active_last_24h,
                "active_last_7d": row.active_last_7d,
            }
            for row in rows
        ]

    async def get_enrichment_summary(self, camera_id: str | None = None) -> list[dict[str, Any]]:
        """Get enrichment summary from materialized view.

        Args:
            camera_id: Filter by specific camera

        Returns:
            List of enrichment summary records
        """
        query = """
            SELECT
                camera_id,
                total_detections,
                with_enrichment,
                with_license_plates,
                total_license_plates,
                with_faces,
                total_faces,
                violent_detections,
                with_vehicle_classification,
                with_pet_classification,
                avg_image_quality,
                avg_processing_time_ms
            FROM mv_enrichment_summary
            WHERE 1=1
        """
        params: dict[str, Any] = {}

        if camera_id:
            query += " AND camera_id = :camera_id"
            params["camera_id"] = camera_id

        query += " ORDER BY camera_id"

        result = await self.session.execute(text(query), params)
        rows = result.fetchall()

        return [
            {
                "camera_id": row.camera_id,
                "total_detections": row.total_detections,
                "with_enrichment": row.with_enrichment,
                "with_license_plates": row.with_license_plates,
                "total_license_plates": row.total_license_plates,
                "with_faces": row.with_faces,
                "total_faces": row.total_faces,
                "violent_detections": row.violent_detections,
                "with_vehicle_classification": row.with_vehicle_classification,
                "with_pet_classification": row.with_pet_classification,
                "avg_image_quality": (
                    float(row.avg_image_quality) if row.avg_image_quality else None
                ),
                "avg_processing_time_ms": (
                    float(row.avg_processing_time_ms) if row.avg_processing_time_ms else None
                ),
            }
            for row in rows
        ]

    async def check_view_exists(self, view_name: str) -> bool:
        """Check if a materialized view exists.

        Args:
            view_name: Name of the materialized view

        Returns:
            True if view exists, False otherwise
        """
        query = """
            SELECT EXISTS (
                SELECT 1
                FROM pg_matviews
                WHERE matviewname = :view_name
            )
        """
        result = await self.session.execute(text(query), {"view_name": view_name})
        row = result.fetchone()
        return bool(row and row[0])

    async def get_view_stats(self) -> list[dict[str, Any]]:
        """Get statistics for all managed materialized views.

        Returns:
            List of view statistics including size and last refresh info
        """
        stats = []

        for view_name in self.MANAGED_VIEWS:
            try:
                # Check if view exists
                exists = await self.check_view_exists(view_name)
                if not exists:
                    stats.append(
                        {
                            "view_name": view_name,
                            "exists": False,
                            "row_count": 0,
                            "size_bytes": 0,
                        }
                    )
                    continue

                # Get row count - view_name is from MANAGED_VIEWS constant, not user input
                count_result = await self.session.execute(
                    text(f"SELECT COUNT(*) FROM {view_name}")  # noqa: S608
                )
                row_count = count_result.scalar() or 0

                # Get size - view_name is from MANAGED_VIEWS constant, not user input
                size_result = await self.session.execute(
                    text(f"SELECT pg_relation_size('{view_name}')")
                )
                size_bytes = size_result.scalar() or 0

                stats.append(
                    {
                        "view_name": view_name,
                        "exists": True,
                        "row_count": row_count,
                        "size_bytes": size_bytes,
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to get stats for {view_name}: {e}")
                stats.append(
                    {
                        "view_name": view_name,
                        "exists": False,
                        "row_count": 0,
                        "size_bytes": 0,
                        "error": str(e),
                    }
                )

        return stats
