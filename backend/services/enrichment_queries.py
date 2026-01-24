"""Service for querying enrichment data using PostgreSQL JSON functions.

This module provides utilities for:
1. Extracting license plate detections from enrichment_data
2. Extracting face detections from enrichment_data
3. Extracting vehicle classification data from enrichment_data
4. Getting enrichment summaries for detections
5. Aggregating enrichment statistics

These functions use PostgreSQL's jsonb_array_elements and jsonb_each functions
to efficiently query the enrichment_data JSONB column, replacing Python-side
JSON parsing for better performance.

Related Linear issue: NEM-3390: Use JSON_TABLE for complex enrichment queries.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging import get_logger

logger = get_logger(__name__)


class EnrichmentQueryService:
    """Service for querying enrichment data from the database.

    This service uses PostgreSQL functions to efficiently extract and aggregate
    data from the enrichment_data JSONB column in the detections table.
    """

    def __init__(self, session: AsyncSession):
        """Initialize the service with a database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_license_plate_detections(
        self,
        camera_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get license plate detections using the PostgreSQL function.

        Args:
            camera_id: Filter by camera ID
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            min_confidence: Minimum confidence threshold (default 0.0)
            limit: Maximum number of results to return

        Returns:
            List of license plate detection records
        """
        query = """
            SELECT * FROM get_license_plate_detections(
                :camera_id,
                :start_date,
                :end_date,
                :min_confidence
            )
            LIMIT :limit
        """

        result = await self.session.execute(
            text(query),
            {
                "camera_id": camera_id,
                "start_date": start_date,
                "end_date": end_date,
                "min_confidence": min_confidence,
                "limit": limit,
            },
        )
        rows = result.fetchall()

        return [
            {
                "detection_id": row.detection_id,
                "camera_id": row.camera_id,
                "detected_at": row.detected_at,
                "plate_text": row.plate_text,
                "plate_confidence": row.plate_confidence,
                "ocr_confidence": row.ocr_confidence,
                "bbox": row.bbox,
            }
            for row in rows
        ]

    async def get_face_detections(
        self,
        camera_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get face detections using the PostgreSQL function.

        Args:
            camera_id: Filter by camera ID
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            min_confidence: Minimum confidence threshold (default 0.0)
            limit: Maximum number of results to return

        Returns:
            List of face detection records
        """
        query = """
            SELECT * FROM get_face_detections(
                :camera_id,
                :start_date,
                :end_date,
                :min_confidence
            )
            LIMIT :limit
        """

        result = await self.session.execute(
            text(query),
            {
                "camera_id": camera_id,
                "start_date": start_date,
                "end_date": end_date,
                "min_confidence": min_confidence,
                "limit": limit,
            },
        )
        rows = result.fetchall()

        return [
            {
                "detection_id": row.detection_id,
                "camera_id": row.camera_id,
                "detected_at": row.detected_at,
                "face_confidence": row.face_confidence,
                "bbox": row.bbox,
            }
            for row in rows
        ]

    async def get_vehicle_data(
        self,
        camera_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get vehicle classification data using the PostgreSQL function.

        Args:
            camera_id: Filter by camera ID
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            limit: Maximum number of results to return

        Returns:
            List of vehicle classification records
        """
        query = """
            SELECT * FROM get_enrichment_vehicle_data(
                :camera_id,
                :start_date,
                :end_date
            )
            LIMIT :limit
        """

        result = await self.session.execute(
            text(query),
            {
                "camera_id": camera_id,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
            },
        )
        rows = result.fetchall()

        return [
            {
                "detection_id": row.detection_id,
                "camera_id": row.camera_id,
                "detected_at": row.detected_at,
                "source_detection_id": row.source_detection_id,
                "vehicle_type": row.vehicle_type,
                "classification_confidence": row.classification_confidence,
                "is_commercial": row.is_commercial,
                "has_damage": row.has_damage,
                "damage_confidence": row.damage_confidence,
            }
            for row in rows
        ]

    async def get_detection_enrichment_summary(self, detection_id: int) -> dict[str, Any] | None:
        """Get enrichment summary for a single detection.

        Args:
            detection_id: The detection ID to get summary for

        Returns:
            Enrichment summary dict or None if detection not found
        """
        query = """
            SELECT * FROM get_detection_enrichment_summary(:detection_id)
        """

        result = await self.session.execute(text(query), {"detection_id": detection_id})
        row = result.fetchone()

        if not row or row.detection_id is None:
            return None

        return {
            "detection_id": row.detection_id,
            "has_license_plates": row.has_license_plates,
            "license_plate_count": row.license_plate_count,
            "has_faces": row.has_faces,
            "face_count": row.face_count,
            "has_violence_detection": row.has_violence_detection,
            "is_violent": row.is_violent,
            "has_vehicle_classification": row.has_vehicle_classification,
            "vehicle_types": row.vehicle_types or [],
            "has_pet_classification": row.has_pet_classification,
            "has_image_quality": row.has_image_quality,
            "image_quality_score": row.image_quality_score,
            "processing_time_ms": row.processing_time_ms,
            "error_count": row.error_count,
        }

    async def get_enrichment_statistics(
        self,
        camera_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get aggregated enrichment statistics using the PostgreSQL function.

        Args:
            camera_id: Filter by camera ID
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)

        Returns:
            List of enrichment statistics by camera
        """
        query = """
            SELECT * FROM get_enrichment_statistics(
                :camera_id,
                :start_date,
                :end_date
            )
        """

        result = await self.session.execute(
            text(query),
            {
                "camera_id": camera_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        rows = result.fetchall()

        return [
            {
                "camera_id": row.camera_id,
                "total_detections": row.total_detections,
                "with_license_plates": row.with_license_plates,
                "with_faces": row.with_faces,
                "with_violence_detection": row.with_violence_detection,
                "violent_detections": row.violent_detections,
                "with_vehicle_classification": row.with_vehicle_classification,
                "with_pet_classification": row.with_pet_classification,
                "with_image_quality": row.with_image_quality,
                "avg_quality_score": row.avg_quality_score,
                "avg_processing_time_ms": row.avg_processing_time_ms,
                "with_errors": row.with_errors,
            }
            for row in rows
        ]

    async def search_license_plates(
        self,
        plate_text: str,
        camera_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search for license plates by text pattern.

        Uses SQL LIKE pattern matching for flexible searching.

        Args:
            plate_text: Plate text pattern to search for (supports % wildcards)
            camera_id: Filter by camera ID
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            limit: Maximum number of results

        Returns:
            List of matching license plate detection records
        """
        # Build dynamic query with pattern matching
        query = """
            SELECT
                d.id AS detection_id,
                d.camera_id,
                d.detected_at,
                (lp.value->>'text')::TEXT AS plate_text,
                (lp.value->>'confidence')::FLOAT AS plate_confidence,
                (lp.value->>'ocr_confidence')::FLOAT AS ocr_confidence,
                lp.value->'bbox' AS bbox
            FROM detections d
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(d.enrichment_data->'license_plates', '[]'::jsonb)
            ) AS lp(value)
            WHERE d.enrichment_data->'license_plates' IS NOT NULL
              AND jsonb_array_length(d.enrichment_data->'license_plates') > 0
              AND (lp.value->>'text') ILIKE :plate_pattern
        """
        params: dict[str, Any] = {"plate_pattern": f"%{plate_text}%"}

        if camera_id:
            query += " AND d.camera_id = :camera_id"
            params["camera_id"] = camera_id
        if start_date:
            query += " AND d.detected_at >= :start_date"
            params["start_date"] = start_date
        if end_date:
            query += " AND d.detected_at <= :end_date"
            params["end_date"] = end_date

        query += " ORDER BY d.detected_at DESC LIMIT :limit"
        params["limit"] = limit

        result = await self.session.execute(text(query), params)
        rows = result.fetchall()

        return [
            {
                "detection_id": row.detection_id,
                "camera_id": row.camera_id,
                "detected_at": row.detected_at,
                "plate_text": row.plate_text,
                "plate_confidence": row.plate_confidence,
                "ocr_confidence": row.ocr_confidence,
                "bbox": row.bbox,
            }
            for row in rows
        ]

    async def get_violent_detections(
        self,
        camera_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get detections flagged as violent.

        Args:
            camera_id: Filter by camera ID
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            limit: Maximum number of results

        Returns:
            List of violent detection records
        """
        query = """
            SELECT
                d.id AS detection_id,
                d.camera_id,
                d.detected_at,
                d.object_type,
                d.confidence,
                (d.enrichment_data->'violence_detection'->>'is_violent')::BOOLEAN AS is_violent,
                (d.enrichment_data->'violence_detection'->>'confidence')::FLOAT AS violence_confidence,
                d.enrichment_data->'violence_detection'->>'predicted_class' AS predicted_class
            FROM detections d
            WHERE d.enrichment_data->'violence_detection' IS NOT NULL
              AND (d.enrichment_data->'violence_detection'->>'is_violent')::BOOLEAN = TRUE
        """
        params: dict[str, Any] = {}

        if camera_id:
            query += " AND d.camera_id = :camera_id"
            params["camera_id"] = camera_id
        if start_date:
            query += " AND d.detected_at >= :start_date"
            params["start_date"] = start_date
        if end_date:
            query += " AND d.detected_at <= :end_date"
            params["end_date"] = end_date

        query += " ORDER BY d.detected_at DESC LIMIT :limit"
        params["limit"] = limit

        result = await self.session.execute(text(query), params)
        rows = result.fetchall()

        return [
            {
                "detection_id": row.detection_id,
                "camera_id": row.camera_id,
                "detected_at": row.detected_at,
                "object_type": row.object_type,
                "confidence": row.confidence,
                "is_violent": row.is_violent,
                "violence_confidence": row.violence_confidence,
                "predicted_class": row.predicted_class,
            }
            for row in rows
        ]

    async def get_low_quality_detections(
        self,
        camera_id: str | None = None,
        max_quality_score: float = 50.0,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get detections with low image quality scores.

        Args:
            camera_id: Filter by camera ID
            max_quality_score: Maximum quality score threshold (default 50.0)
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            limit: Maximum number of results

        Returns:
            List of low quality detection records
        """
        query = """
            SELECT
                d.id AS detection_id,
                d.camera_id,
                d.detected_at,
                d.object_type,
                (d.enrichment_data->'image_quality'->>'quality_score')::FLOAT AS quality_score,
                (d.enrichment_data->'image_quality'->>'is_blurry')::BOOLEAN AS is_blurry,
                (d.enrichment_data->'image_quality'->>'is_low_quality')::BOOLEAN AS is_low_quality,
                d.enrichment_data->'image_quality'->'quality_issues' AS quality_issues
            FROM detections d
            WHERE d.enrichment_data->'image_quality' IS NOT NULL
              AND (d.enrichment_data->'image_quality'->>'quality_score')::FLOAT <= :max_quality_score
        """
        params: dict[str, Any] = {"max_quality_score": max_quality_score}

        if camera_id:
            query += " AND d.camera_id = :camera_id"
            params["camera_id"] = camera_id
        if start_date:
            query += " AND d.detected_at >= :start_date"
            params["start_date"] = start_date
        if end_date:
            query += " AND d.detected_at <= :end_date"
            params["end_date"] = end_date

        query += " ORDER BY (d.enrichment_data->'image_quality'->>'quality_score')::FLOAT ASC LIMIT :limit"
        params["limit"] = limit

        result = await self.session.execute(text(query), params)
        rows = result.fetchall()

        return [
            {
                "detection_id": row.detection_id,
                "camera_id": row.camera_id,
                "detected_at": row.detected_at,
                "object_type": row.object_type,
                "quality_score": row.quality_score,
                "is_blurry": row.is_blurry,
                "is_low_quality": row.is_low_quality,
                "quality_issues": row.quality_issues,
            }
            for row in rows
        ]
