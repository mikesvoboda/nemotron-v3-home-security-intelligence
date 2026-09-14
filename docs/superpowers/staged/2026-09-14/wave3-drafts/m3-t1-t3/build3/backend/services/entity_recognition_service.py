"""Entity recognition summary service.

This module provides aggregation of face detection and vehicle plate data
for the dashboard entity recognition summary feature.

Features:
- Person recognition stats (known vs unknown faces)
- Vehicle recognition stats (matching plates against household vehicles)
- Time-windowed aggregation for summary display

Implements NEM-5394: Entity Recognition Summary - Backend Service
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from backend.core.logging import get_logger
from backend.models.face_identity import FaceDetectionEvent
from backend.models.household import RegisteredVehicle
from backend.models.plate_read import PlateRead

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


@dataclass(slots=True)
class PersonStats:
    """Statistics for detected persons.

    Attributes:
        known: Count of faces matched to known persons
        unknown: Count of faces that did not match any known person
    """

    known: int
    unknown: int

    @property
    def total_persons(self) -> int:
        """Total count of detected persons."""
        return self.known + self.unknown

    @property
    def breakdown_text(self) -> str:
        """Human-readable breakdown string for display.

        Returns:
            String like "3 known, 2 unknown" or "No persons detected"
        """
        if self.known == 0 and self.unknown == 0:
            return "No persons detected"
        parts = []
        if self.known > 0:
            parts.append(f"{self.known} known")
        if self.unknown > 0:
            parts.append(f"{self.unknown} unknown")
        return ", ".join(parts)


@dataclass(slots=True)
class VehicleStats:
    """Statistics for detected vehicles.

    Attributes:
        known: Count of plates matched to registered household vehicles
        unknown: Count of plates that did not match any registered vehicle
    """

    known: int
    unknown: int

    @property
    def total_vehicles(self) -> int:
        """Total count of detected vehicles with plates."""
        return self.known + self.unknown

    @property
    def breakdown_text(self) -> str:
        """Human-readable breakdown string for display.

        Returns:
            String like "2 known, 3 unknown" or "No vehicles detected"
        """
        if self.known == 0 and self.unknown == 0:
            return "No vehicles detected"
        parts = []
        if self.known > 0:
            parts.append(f"{self.known} known")
        if self.unknown > 0:
            parts.append(f"{self.unknown} unknown")
        return ", ".join(parts)


@dataclass(slots=True)
class EntityRecognitionStats:
    """Combined entity recognition statistics.

    Attributes:
        persons: Statistics for detected persons
        vehicles: Statistics for detected vehicles
        window_start: Start of the aggregation time window
        window_end: End of the aggregation time window
    """

    persons: PersonStats
    vehicles: VehicleStats
    window_start: datetime
    window_end: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response.

        Returns:
            Dictionary with persons, vehicles, and time window data.
        """
        return {
            "persons": {
                "known": self.persons.known,
                "unknown": self.persons.unknown,
                "total": self.persons.total_persons,
                "breakdown": self.persons.breakdown_text,
            },
            "vehicles": {
                "known": self.vehicles.known,
                "unknown": self.vehicles.unknown,
                "total": self.vehicles.total_vehicles,
                "breakdown": self.vehicles.breakdown_text,
            },
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
        }


class EntityRecognitionService:
    """Service for aggregating entity recognition data.

    This service provides methods to aggregate face detection and vehicle
    plate recognition data for dashboard summary display.

    Usage:
        service = EntityRecognitionService()
        stats = await service.get_hourly_stats(session)
        print(f"Persons: {stats.persons.breakdown_text}")
        print(f"Vehicles: {stats.vehicles.breakdown_text}")
    """

    async def get_face_stats(
        self,
        session: AsyncSession,
        window_start: datetime,
        window_end: datetime,
    ) -> PersonStats:
        """Get face detection statistics for a time window.

        Aggregates FaceDetectionEvent records by is_unknown flag to count
        known vs unknown persons detected within the time window.

        Args:
            session: Database session
            window_start: Start of the time window
            window_end: End of the time window

        Returns:
            PersonStats with known and unknown counts
        """
        # Query FaceDetectionEvent grouped by is_unknown
        stmt = (
            select(FaceDetectionEvent.is_unknown, func.count(FaceDetectionEvent.id))
            .where(FaceDetectionEvent.timestamp >= window_start)
            .where(FaceDetectionEvent.timestamp < window_end)
            .group_by(FaceDetectionEvent.is_unknown)
        )

        result = await session.execute(stmt)
        rows = result.all()

        # Parse results
        known = 0
        unknown = 0
        for is_unknown, count in rows:
            if is_unknown:
                unknown = count
            else:
                known = count

        logger.debug(
            "Face stats for window %s to %s: known=%d, unknown=%d",
            window_start,
            window_end,
            known,
            unknown,
        )

        return PersonStats(known=known, unknown=unknown)

    async def get_vehicle_stats(
        self,
        session: AsyncSession,
        window_start: datetime,
        window_end: datetime,
    ) -> VehicleStats:
        """Get vehicle plate recognition statistics for a time window.

        Matches detected license plates against registered household vehicles
        to count known vs unknown vehicles.

        Args:
            session: Database session
            window_start: Start of the time window
            window_end: End of the time window

        Returns:
            VehicleStats with known and unknown counts
        """
        # Get all household vehicle plates (normalized to uppercase)
        household_stmt = select(RegisteredVehicle.license_plate).where(
            RegisteredVehicle.license_plate.isnot(None),
            RegisteredVehicle.trusted.is_(True),
        )
        household_result = await session.execute(household_stmt)
        household_plates = {plate.upper() for plate in household_result.scalars().all() if plate}

        # Get all detected plates in time window
        plates_stmt = (
            select(PlateRead.plate_text)
            .where(PlateRead.timestamp >= window_start)
            .where(PlateRead.timestamp < window_end)
        )
        plates_result = await session.execute(plates_stmt)
        detected_plates = plates_result.scalars().all()

        # Deduplicate detected plates (case-insensitive)
        unique_detected: set[str] = set()
        for plate in detected_plates:
            if plate:
                unique_detected.add(plate.upper())

        # Count matches
        known_plates = unique_detected & household_plates
        unknown_plates = unique_detected - household_plates

        logger.debug(
            "Vehicle stats for window %s to %s: known=%d, unknown=%d",
            window_start,
            window_end,
            len(known_plates),
            len(unknown_plates),
        )

        return VehicleStats(known=len(known_plates), unknown=len(unknown_plates))

    async def get_summary_stats(
        self,
        session: AsyncSession,
        window_start: datetime,
        window_end: datetime,
    ) -> EntityRecognitionStats:
        """Get combined entity recognition statistics for a time window.

        Args:
            session: Database session
            window_start: Start of the time window
            window_end: End of the time window

        Returns:
            EntityRecognitionStats with persons, vehicles, and time window
        """
        persons = await self.get_face_stats(session, window_start, window_end)
        vehicles = await self.get_vehicle_stats(session, window_start, window_end)

        return EntityRecognitionStats(
            persons=persons,
            vehicles=vehicles,
            window_start=window_start,
            window_end=window_end,
        )

    async def get_hourly_stats(self, session: AsyncSession) -> EntityRecognitionStats:
        """Get entity recognition statistics for the past hour.

        Convenience method that calculates the time window automatically.

        Args:
            session: Database session

        Returns:
            EntityRecognitionStats for the past hour
        """
        window_end = datetime.now(UTC)
        window_start = window_end - timedelta(hours=1)

        return await self.get_summary_stats(session, window_start, window_end)


# =============================================================================
# Global Service Instance (Singleton Pattern)
# =============================================================================

_entity_recognition_service: EntityRecognitionService | None = None


def get_entity_recognition_service() -> EntityRecognitionService:
    """Get or create the global EntityRecognitionService instance.

    Returns:
        Global EntityRecognitionService instance
    """
    global _entity_recognition_service  # noqa: PLW0603
    if _entity_recognition_service is None:
        _entity_recognition_service = EntityRecognitionService()
    return _entity_recognition_service


def reset_entity_recognition_service() -> None:
    """Reset the global EntityRecognitionService instance (for testing)."""
    global _entity_recognition_service  # noqa: PLW0603
    _entity_recognition_service = None
