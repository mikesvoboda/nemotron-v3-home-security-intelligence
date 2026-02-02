"""Depth calibration service for converting normalized depth to real-world distances.

This module provides calibration-based conversion from relative depth values (0-1)
to real-world distances in feet. Calibration data is stored per-camera and can be
used to provide more meaningful context to Nemotron for risk analysis.

NEM-5283: Phase 2 - Depth Distance Conversion
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


__all__ = [
    "CalibrationData",
    "CalibrationPoint",
    "DepthCalibrationService",
    "InvalidCalibrationError",
    "depth_to_feet",
    "format_distance_context",
    "get_depth_calibration_service",
    "reset_depth_calibration_service",
    "validate_calibration_data",
]


# =============================================================================
# Exceptions
# =============================================================================


class InvalidCalibrationError(Exception):
    """Raised when calibration data is invalid."""


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(slots=True)
class CalibrationPoint:
    """A single calibration point mapping depth value to real-world distance.

    Attributes:
        depth_value: Normalized depth value (0-1) at calibration location
        distance_feet: Real-world distance in feet at this depth
        reference_name: Optional name for the reference point (e.g., "front_door")
    """

    depth_value: float
    distance_feet: float
    reference_name: str | None = None


@dataclass(slots=True)
class CalibrationData:
    """Calibration data for a camera's depth-to-distance conversion.

    Attributes:
        camera_id: Camera identifier
        calibration_points: List of CalibrationPoint objects
        created_at: When calibration was created
        image_width: Width of calibration image (optional)
        image_height: Height of calibration image (optional)
    """

    camera_id: str
    calibration_points: list[CalibrationPoint]
    created_at: datetime | None = field(default=None)
    image_width: int | None = None
    image_height: int | None = None


# =============================================================================
# Validation Functions
# =============================================================================


def validate_calibration_data(data: CalibrationData) -> None:
    """Validate calibration data for correctness.

    Args:
        data: CalibrationData to validate

    Raises:
        InvalidCalibrationError: If validation fails

    Warns:
        UserWarning: If depth-distance relationship is non-monotonic
    """
    # Check for empty calibration points
    if not data.calibration_points:
        raise InvalidCalibrationError("Calibration data must have at least one calibration point")

    # Check each calibration point
    depth_values_seen: set[float] = set()

    for point in data.calibration_points:
        if point.distance_feet < 0:
            raise InvalidCalibrationError(
                f"Calibration point has negative distance: {point.distance_feet} feet"
            )
        if point.distance_feet == 0:
            raise InvalidCalibrationError(
                "Calibration point has zero distance - distance must be positive"
            )

        if point.depth_value < 0 or point.depth_value > 1:
            raise InvalidCalibrationError(
                f"Calibration point has depth value {point.depth_value} out of range [0, 1]"
            )

        # Check for duplicate depth values
        if point.depth_value in depth_values_seen:
            raise InvalidCalibrationError(
                f"Calibration data has duplicate depth value: {point.depth_value}"
            )
        depth_values_seen.add(point.depth_value)

    # Check for non-monotonic depth-distance relationship
    # Sort points by depth value
    sorted_points = sorted(data.calibration_points, key=lambda p: p.depth_value)

    for i in range(1, len(sorted_points)):
        prev_distance = sorted_points[i - 1].distance_feet
        curr_distance = sorted_points[i].distance_feet

        if curr_distance < prev_distance:
            warnings.warn(
                f"Calibration data has non-monotonic depth-distance relationship: "
                f"depth {sorted_points[i].depth_value} maps to {curr_distance} feet, "
                f"but previous point at depth {sorted_points[i - 1].depth_value} "
                f"maps to {prev_distance} feet",
                UserWarning,
                stacklevel=2,
            )
            break


# =============================================================================
# Conversion Functions
# =============================================================================


def depth_to_feet(depth: float, calibration: CalibrationData | None) -> float | None:
    """Convert normalized depth value to distance in feet.

    Uses linear interpolation/extrapolation between calibration points.
    For a single calibration point, uses linear scaling through origin.

    Args:
        depth: Normalized depth value (0-1)
        calibration: CalibrationData with calibration points, or None

    Returns:
        Distance in feet, or None if no calibration data provided
    """
    if calibration is None or not calibration.calibration_points:
        return None

    points = sorted(calibration.calibration_points, key=lambda p: p.depth_value)

    # Single point calibration - linear scaling through origin
    if len(points) == 1:
        point = points[0]
        if point.depth_value == 0:
            return point.distance_feet
        return depth * (point.distance_feet / point.depth_value)

    # Find bracketing points for interpolation/extrapolation
    lower_point: CalibrationPoint | None = None
    upper_point: CalibrationPoint | None = None

    for point in points:
        if point.depth_value <= depth:
            lower_point = point
        if point.depth_value >= depth and upper_point is None:
            upper_point = point

    # Extrapolate from edge points if depth is outside calibration range
    if lower_point is None:
        lower_point, upper_point = points[0], points[1]
    elif upper_point is None:
        lower_point, upper_point = points[-2], points[-1]

    depth_range = upper_point.depth_value - lower_point.depth_value
    if depth_range == 0:
        return lower_point.distance_feet

    factor = (depth - lower_point.depth_value) / depth_range
    distance_range = upper_point.distance_feet - lower_point.distance_feet
    result = lower_point.distance_feet + factor * distance_range

    return max(0.1, result)


# =============================================================================
# Formatting Functions
# =============================================================================


def format_distance_context(
    class_name: str,
    distance_feet: float | None,
    location_name: str = "camera",
    proximity_label: str | None = None,
) -> str:
    """Format distance information for LLM context.

    Creates human-readable description like:
    "Person is approximately 10 feet from front door"

    Args:
        class_name: Object class name (e.g., "person", "car")
        distance_feet: Distance in feet, or None if uncalibrated
        location_name: Name of the location/camera (e.g., "front door")
        proximity_label: Fallback proximity label when distance is None

    Returns:
        Formatted context string
    """
    display_name = class_name.replace("_", " ").capitalize()

    if distance_feet is not None:
        return f"{display_name} is approximately {round(distance_feet)} feet from {location_name}"

    if proximity_label is not None:
        return f"{display_name} is {proximity_label} to {location_name}"

    return f"{display_name} detected near {location_name}"


# =============================================================================
# Service Class
# =============================================================================


class DepthCalibrationService:
    """Service for managing depth calibration and depth-to-distance conversion.

    Provides calibration registration, caching, and conversion functionality.
    Supports loading calibration data from database when not cached.

    Attributes:
        _calibration_cache: In-memory cache of calibration data by camera_id
        _session: Optional database session for loading calibration from Camera model
    """

    def __init__(self, session: AsyncSession | None = None) -> None:
        """Initialize the DepthCalibrationService.

        Args:
            session: Optional SQLAlchemy async session for database operations
        """
        self._calibration_cache: dict[str, CalibrationData] = {}
        self._session: AsyncSession | None = session

    def register_calibration(self, data: CalibrationData) -> None:
        """Register calibration data for a camera.

        Validates the calibration data and stores it in the cache.

        Args:
            data: CalibrationData to register

        Raises:
            InvalidCalibrationError: If calibration data is invalid
        """
        validate_calibration_data(data)
        self._calibration_cache[data.camera_id] = data
        logger.info(
            f"Registered calibration for camera {data.camera_id} "
            f"with {len(data.calibration_points)} points"
        )

    def unregister_calibration(self, camera_id: str) -> None:
        """Remove calibration data for a camera.

        Args:
            camera_id: Camera identifier to remove calibration for
        """
        if camera_id in self._calibration_cache:
            del self._calibration_cache[camera_id]
            logger.info(f"Unregistered calibration for camera {camera_id}")

    def is_calibrated(self, camera_id: str) -> bool:
        """Check if a camera has calibration data registered.

        Args:
            camera_id: Camera identifier to check

        Returns:
            True if calibration data is registered
        """
        return camera_id in self._calibration_cache

    def get_calibration(self, camera_id: str) -> CalibrationData | None:
        """Get calibration data for a camera.

        Args:
            camera_id: Camera identifier

        Returns:
            CalibrationData if registered, None otherwise
        """
        return self._calibration_cache.get(camera_id)

    async def convert_depth_to_feet(
        self,
        camera_id: str,
        depth_value: float,
    ) -> float | None:
        """Convert depth value to feet for a specific camera.

        Attempts to use cached calibration data first. If not cached and a
        database session is available, loads from the Camera model.

        Args:
            camera_id: Camera identifier
            depth_value: Normalized depth value (0-1)

        Returns:
            Distance in feet, or None if camera is uncalibrated
        """
        # Check cache first
        calibration = self._calibration_cache.get(camera_id)

        # Try loading from database if not cached and session available
        if calibration is None and self._session is not None:
            calibration = await self._load_calibration_from_db(camera_id)
            if calibration is not None:
                # Cache for future use
                self._calibration_cache[camera_id] = calibration

        return depth_to_feet(depth_value, calibration)

    async def _load_calibration_from_db(self, camera_id: str) -> CalibrationData | None:
        """Load calibration data from database.

        Args:
            camera_id: Camera identifier

        Returns:
            CalibrationData if found and valid, None otherwise
        """
        try:
            from sqlalchemy import select

            from backend.models.camera import Camera

            if self._session is None:
                return None

            result = await self._session.execute(select(Camera).where(Camera.id == camera_id))
            camera = result.scalar_one_or_none()

            if camera is None or camera.calibration_data is None:
                return None

            return self._parse_calibration_dict(camera_id, camera.calibration_data)

        except Exception as e:
            logger.warning(f"Failed to load calibration from database for camera {camera_id}: {e}")
            return None

    def _parse_calibration_dict(
        self, camera_id: str, data: dict[str, Any]
    ) -> CalibrationData | None:
        """Parse calibration data from dictionary format.

        Args:
            camera_id: Camera identifier
            data: Dictionary with calibration data

        Returns:
            CalibrationData if valid, None otherwise
        """
        try:
            calibration_points_data = data.get("calibration_points", [])
            if not calibration_points_data:
                return None

            calibration_points = [
                CalibrationPoint(
                    depth_value=p["depth_value"],
                    distance_feet=p["distance_feet"],
                    reference_name=p.get("reference_name"),
                )
                for p in calibration_points_data
            ]

            return CalibrationData(
                camera_id=camera_id,
                calibration_points=calibration_points,
                image_width=data.get("image_width"),
                image_height=data.get("image_height"),
            )

        except (KeyError, TypeError) as e:
            logger.warning(f"Failed to parse calibration data for camera {camera_id}: {e}")
            return None


# =============================================================================
# Singleton Pattern
# =============================================================================

# Module-level singleton container (avoids PLW0603 global statement warnings)
_singleton: dict[str, DepthCalibrationService | None] = {"instance": None}


def get_depth_calibration_service() -> DepthCalibrationService:
    """Get the global DepthCalibrationService singleton instance.

    Creates the instance on first call.

    Returns:
        The global DepthCalibrationService instance
    """
    instance = _singleton["instance"]
    if instance is None:
        instance = DepthCalibrationService()
        _singleton["instance"] = instance
        logger.info("Initialized global DepthCalibrationService")
    return instance


def reset_depth_calibration_service() -> None:
    """Reset the global DepthCalibrationService singleton (for testing)."""
    _singleton["instance"] = None
    logger.debug("Reset global DepthCalibrationService")
