"""Context enrichment service for Nemotron prompt enhancement.

This service enriches detection batches with contextual information
including zone mapping, baseline deviation analysis, and cross-camera
correlation to provide more informed risk assessments.

Usage:
    from backend.services.context_enricher import ContextEnricher, get_context_enricher

    enricher = get_context_enricher()
    context = await enricher.enrich(batch_id, camera_id, detection_ids)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_session
from backend.core.logging import get_logger
from backend.models.baseline import ActivityBaseline, ClassBaseline
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.zone import Zone, ZoneType
from backend.services.baseline import get_baseline_service
from backend.services.batch_fetch import batch_fetch_detections
from backend.services.prompt_sanitizer import sanitize_camera_name, sanitize_zone_name
from backend.services.zone_service import bbox_center, point_in_zone

logger = get_logger(__name__)

# Global singleton
_context_enricher: ContextEnricher | None = None

# Default image dimensions for zone calculations
DEFAULT_IMAGE_WIDTH = 1920
DEFAULT_IMAGE_HEIGHT = 1080

# Cross-camera correlation window (5 minutes)
CROSS_CAMERA_WINDOW_SECONDS = 300


@dataclass(slots=True)
class ZoneContext:
    """Zone information for a detection.

    Attributes:
        zone_id: Unique identifier for the zone
        zone_name: Human-readable zone name
        zone_type: Type of zone (entry_point, driveway, etc.)
        risk_weight: Risk weight for this zone type (high, medium, low)
        detection_count: Number of detections in this zone
    """

    zone_id: str
    zone_name: str
    zone_type: str
    risk_weight: str
    detection_count: int = 1


@dataclass(slots=True)
class BaselineContext:
    """Baseline deviation information for current activity.

    Attributes:
        hour_of_day: Current hour (0-23)
        day_of_week: Current day name (e.g., "Monday")
        expected_detections: Expected count per class based on historical data
        current_detections: Actual count per class in current batch
        deviation_score: How unusual this activity is (0=normal, 1=highly unusual)
        is_anomalous: Whether activity is considered anomalous
    """

    hour_of_day: int
    day_of_week: str
    expected_detections: dict[str, float] = field(default_factory=dict)
    current_detections: dict[str, int] = field(default_factory=dict)
    deviation_score: float = 0.0
    is_anomalous: bool = False


@dataclass(slots=True)
class RecentEvent:
    """Recent event for context.

    Attributes:
        event_id: Event identifier
        risk_score: Risk score of the event
        risk_level: Risk level (low/medium/high/critical)
        summary: Brief summary of the event
        occurred_at: When the event occurred
    """

    event_id: int
    risk_score: int
    risk_level: str
    summary: str
    occurred_at: datetime


@dataclass(slots=True)
class CrossCameraActivity:
    """Activity from other cameras within the time window.

    Attributes:
        camera_id: Camera identifier
        camera_name: Human-readable camera name
        detection_count: Number of detections on this camera
        object_types: List of object types detected
        time_offset_seconds: How many seconds before/after the current batch
    """

    camera_id: str
    camera_name: str
    detection_count: int
    object_types: list[str] = field(default_factory=list)
    time_offset_seconds: float = 0.0


@dataclass(slots=True)
class EnrichedContext:
    """Complete enriched context for a detection batch.

    Attributes:
        camera_name: Name of the camera
        camera_id: Camera identifier
        zones: Zone context for detections
        baselines: Baseline deviation information
        recent_events: Recent events from this camera
        cross_camera: Activity from other cameras
        start_time: Start of detection window
        end_time: End of detection window
    """

    camera_name: str
    camera_id: str
    zones: list[ZoneContext] = field(default_factory=list)
    baselines: BaselineContext | None = None
    recent_events: list[RecentEvent] = field(default_factory=list)
    cross_camera: list[CrossCameraActivity] = field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None


# Zone type to risk weight mapping
ZONE_RISK_WEIGHTS: dict[ZoneType, str] = {
    ZoneType.ENTRY_POINT: "high",
    ZoneType.DRIVEWAY: "medium",
    ZoneType.SIDEWALK: "low",
    ZoneType.YARD: "medium",
    ZoneType.OTHER: "low",
}

# Day of week names
DAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


class ContextEnricher:
    """Service for enriching detection batches with contextual information.

    This service aggregates zone information, baseline deviations, recent events,
    and cross-camera activity to provide comprehensive context for risk analysis.

    Attributes:
        cross_camera_window: Time window in seconds for cross-camera correlation
        image_width: Default image width for zone calculations
        image_height: Default image height for zone calculations
    """

    def __init__(
        self,
        cross_camera_window: int = CROSS_CAMERA_WINDOW_SECONDS,
        image_width: int = DEFAULT_IMAGE_WIDTH,
        image_height: int = DEFAULT_IMAGE_HEIGHT,
    ) -> None:
        """Initialize the context enricher.

        Args:
            cross_camera_window: Time window for cross-camera correlation (seconds)
            image_width: Default image width for zone calculations (pixels)
            image_height: Default image height for zone calculations (pixels)
        """
        self.cross_camera_window = cross_camera_window
        self.image_width = image_width
        self.image_height = image_height
        self._baseline_service = get_baseline_service()

        logger.info(f"ContextEnricher initialized: cross_camera_window={cross_camera_window}s")

    async def enrich(
        self,
        batch_id: str,
        camera_id: str,
        detection_ids: list[int],
        *,
        session: AsyncSession | None = None,
    ) -> EnrichedContext:
        """Enrich a detection batch with contextual information.

        Aggregates zone information, baseline deviations, and cross-camera
        activity for the given detection batch.

        Args:
            batch_id: Batch identifier
            camera_id: Camera identifier
            detection_ids: List of detection IDs in the batch
            session: Optional database session (creates new one if not provided)

        Returns:
            EnrichedContext with all contextual information
        """

        async def _do_enrich(sess: AsyncSession) -> EnrichedContext:
            # Get camera info
            camera_result = await sess.execute(select(Camera).where(Camera.id == camera_id))
            camera = camera_result.scalar_one_or_none()
            camera_name = camera.name if camera else camera_id

            # Get detections using batch fetching to handle large detection lists
            if detection_ids:
                detections = await batch_fetch_detections(sess, detection_ids)
            else:
                detections = []

            if not detections:
                logger.warning(
                    f"No detections found for batch {batch_id}, returning minimal context"
                )
                return EnrichedContext(
                    camera_name=camera_name,
                    camera_id=camera_id,
                )

            # Determine time window
            detection_times = [d.detected_at for d in detections if d.detected_at]
            start_time = min(detection_times) if detection_times else datetime.now(UTC)
            end_time = max(detection_times) if detection_times else datetime.now(UTC)

            # Gather all context in parallel-ish manner (sequential for now)
            zones = await self._get_zone_context(camera_id, detections, sess)
            baselines = await self._get_baseline_context(camera_id, detections, start_time, sess)
            cross_camera = await self._get_cross_camera_activity(
                camera_id, start_time, end_time, sess
            )

            return EnrichedContext(
                camera_name=camera_name,
                camera_id=camera_id,
                zones=zones,
                baselines=baselines,
                recent_events=[],  # Could add recent events from database
                cross_camera=cross_camera,
                start_time=start_time,
                end_time=end_time,
            )

        if session is not None:
            return await _do_enrich(session)
        else:
            async with get_session() as sess:
                return await _do_enrich(sess)

    async def _get_zone_context(
        self,
        camera_id: str,
        detections: list[Detection],
        session: AsyncSession,
    ) -> list[ZoneContext]:
        """Map detections to zones and aggregate zone context.

        Args:
            camera_id: Camera identifier
            detections: List of detections to map
            session: Database session

        Returns:
            List of ZoneContext with detection counts per zone
        """
        # Query all enabled zones for this camera
        zones_result = await session.execute(
            select(Zone)
            .where(Zone.camera_id == camera_id, Zone.enabled == True)  # noqa: E712
            .order_by(Zone.priority.desc())
        )
        zones = list(zones_result.scalars().all())

        if not zones:
            logger.debug(f"No zones defined for camera {camera_id}")
            return []

        # Map each detection to zones
        zone_counts: dict[str, int] = {}
        zone_map: dict[str, Zone] = {z.id: z for z in zones}

        for detection in detections:
            if (
                detection.bbox_x is None
                or detection.bbox_y is None
                or detection.bbox_width is None
                or detection.bbox_height is None
            ):
                continue

            # Calculate normalized center point
            try:
                center_x, center_y = bbox_center(
                    detection.bbox_x,
                    detection.bbox_y,
                    detection.bbox_width,
                    detection.bbox_height,
                    self.image_width,
                    self.image_height,
                )
            except ValueError:
                continue

            # Check which zones contain this detection
            for zone in zones:
                if point_in_zone(center_x, center_y, zone):
                    zone_counts[zone.id] = zone_counts.get(zone.id, 0) + 1

        # Build ZoneContext list
        zone_contexts = []
        for zone_id, count in zone_counts.items():
            zone = zone_map[zone_id]
            risk_weight = ZONE_RISK_WEIGHTS.get(zone.zone_type, "low")
            zone_contexts.append(
                ZoneContext(
                    zone_id=zone_id,
                    zone_name=zone.name,
                    zone_type=zone.zone_type.value,
                    risk_weight=risk_weight,
                    detection_count=count,
                )
            )

        # Sort by detection count (highest first)
        zone_contexts.sort(key=lambda z: z.detection_count, reverse=True)

        logger.debug(
            f"Zone mapping for camera {camera_id}: {len(zone_contexts)} zones with detections"
        )

        return zone_contexts

    async def _get_baseline_context(
        self,
        camera_id: str,
        detections: list[Detection],
        reference_time: datetime,
        session: AsyncSession,
    ) -> BaselineContext:
        """Calculate baseline deviation for current activity.

        Compares current detection counts to historical baselines for this
        camera at this time slot.

        Args:
            camera_id: Camera identifier
            detections: List of detections in the batch
            reference_time: Reference time for baseline lookup
            session: Database session

        Returns:
            BaselineContext with deviation information
        """
        hour = reference_time.hour
        day_of_week = reference_time.weekday()
        day_name = DAY_NAMES[day_of_week]

        # Count current detections by class
        current_counts: dict[str, int] = {}
        for detection in detections:
            obj_type = detection.object_type or "unknown"
            current_counts[obj_type] = current_counts.get(obj_type, 0) + 1

        # Get baseline expectations from database
        expected_counts: dict[str, float] = {}
        total_expected = 0.0
        total_current = sum(current_counts.values())

        # Query class baselines for this camera and hour
        class_baselines_result = await session.execute(
            select(ClassBaseline).where(
                ClassBaseline.camera_id == camera_id,
                ClassBaseline.hour == hour,
            )
        )
        class_baselines = list(class_baselines_result.scalars().all())

        for baseline in class_baselines:
            expected_counts[baseline.detection_class] = baseline.frequency
            total_expected += baseline.frequency

        # Query activity baseline for this time slot
        activity_result = await session.execute(
            select(ActivityBaseline).where(
                ActivityBaseline.camera_id == camera_id,
                ActivityBaseline.hour == hour,
                ActivityBaseline.day_of_week == day_of_week,
            )
        )
        activity_baseline = activity_result.scalar_one_or_none()

        # Calculate deviation score
        deviation_score = 0.0
        is_anomalous = False

        if activity_baseline and activity_baseline.sample_count >= 10:
            # Compare current activity to expected
            expected_activity = activity_baseline.avg_count
            if expected_activity > 0:
                # Deviation based on ratio of current to expected
                ratio = total_current / expected_activity
                # Score increases with deviation from 1.0
                # ratio of 2.0 (double expected) gives deviation of 0.5
                # ratio of 4.0 (4x expected) gives deviation of 0.75
                # Less than expected is also unusual but less concerning
                deviation_score = 1.0 - 1.0 / ratio if ratio > 1 else (1.0 - ratio) * 0.5

                deviation_score = max(0.0, min(1.0, deviation_score))

                # Flag as anomalous if deviation > 0.5
                is_anomalous = deviation_score > 0.5
        elif not class_baselines:
            # No baseline data - neutral score
            deviation_score = 0.5

        # Check for anomalous individual classes
        for obj_type, _count in current_counts.items():
            is_class_anomalous, anomaly_score = await self._baseline_service.is_anomalous(
                camera_id, obj_type, reference_time, session=session
            )
            if is_class_anomalous:
                is_anomalous = True
                # Boost deviation score for anomalous classes
                deviation_score = max(deviation_score, anomaly_score * 0.8)

        logger.debug(
            f"Baseline context for camera {camera_id} at {hour}:00 {day_name}: "
            f"deviation={deviation_score:.2f}, anomalous={is_anomalous}"
        )

        return BaselineContext(
            hour_of_day=hour,
            day_of_week=day_name,
            expected_detections=expected_counts,
            current_detections=current_counts,
            deviation_score=deviation_score,
            is_anomalous=is_anomalous,
        )

    async def _get_cross_camera_activity(
        self,
        camera_id: str,
        start_time: datetime,
        end_time: datetime,
        session: AsyncSession,
    ) -> list[CrossCameraActivity]:
        """Query recent detections from other cameras within time window.

        Finds activity on other cameras that may be correlated with the
        current batch (e.g., same person moving between cameras).

        Args:
            camera_id: Current camera identifier (excluded from results)
            start_time: Start of detection window
            end_time: End of detection window
            session: Database session

        Returns:
            List of CrossCameraActivity for other cameras
        """
        # Expand time window for cross-camera correlation
        window_start = start_time - timedelta(seconds=self.cross_camera_window)
        window_end = end_time + timedelta(seconds=self.cross_camera_window)

        # Query detections from other cameras in the window
        other_detections_result = await session.execute(
            select(Detection)
            .where(
                Detection.camera_id != camera_id,
                Detection.detected_at >= window_start,
                Detection.detected_at <= window_end,
            )
            .order_by(Detection.detected_at)
        )
        other_detections = list(other_detections_result.scalars().all())

        if not other_detections:
            return []

        # Group by camera
        camera_activities: dict[str, list[Detection]] = {}
        for detection in other_detections:
            if detection.camera_id not in camera_activities:
                camera_activities[detection.camera_id] = []
            camera_activities[detection.camera_id].append(detection)

        # Get camera names
        camera_ids = list(camera_activities.keys())
        cameras_result = await session.execute(select(Camera).where(Camera.id.in_(camera_ids)))
        cameras = {c.id: c.name for c in cameras_result.scalars().all()}

        # Build CrossCameraActivity list
        cross_camera = []
        reference_time = start_time + (end_time - start_time) / 2

        for cam_id, dets in camera_activities.items():
            # Collect unique object types
            object_types = list({d.object_type for d in dets if d.object_type})

            # Calculate average time offset from reference
            if dets:
                time_offsets = [
                    float((d.detected_at - reference_time).total_seconds())
                    for d in dets
                    if d.detected_at
                ]
                avg_time = sum(time_offsets) / len(dets) if time_offsets else 0.0
            else:
                avg_time = 0.0

            cross_camera.append(
                CrossCameraActivity(
                    camera_id=cam_id,
                    camera_name=cameras.get(cam_id, cam_id),
                    detection_count=len(dets),
                    object_types=object_types,
                    time_offset_seconds=avg_time,
                )
            )

        # Sort by detection count (highest first)
        cross_camera.sort(key=lambda c: c.detection_count, reverse=True)

        logger.debug(
            f"Cross-camera activity: {len(cross_camera)} cameras with "
            f"{sum(c.detection_count for c in cross_camera)} total detections"
        )

        return cross_camera

    def format_zone_analysis(self, zones: list[ZoneContext]) -> str:
        """Format zone context for prompt inclusion.

        Args:
            zones: List of zone contexts

        Returns:
            Formatted string for prompt

        Security:
            Sanitizes zone_name to prevent prompt injection via zone names.
            See NEM-1722 and backend/services/prompt_sanitizer.py for details.
        """
        if not zones:
            return "No zone data available."

        lines = []
        for zone in zones:
            # Sanitize zone_name to prevent prompt injection (NEM-1722)
            safe_zone_name = sanitize_zone_name(zone.zone_name)
            lines.append(
                f"- {safe_zone_name} ({zone.zone_type}): "
                f"{zone.detection_count} detection(s), risk weight: {zone.risk_weight}"
            )

        return "\n".join(lines)

    def format_baseline_comparison(self, baseline: BaselineContext | None) -> str:
        """Format baseline context for prompt inclusion.

        Args:
            baseline: Baseline context

        Returns:
            Formatted string for prompt
        """
        if baseline is None:
            return "No baseline data available."

        lines = []

        if baseline.expected_detections:
            lines.append("Expected activity:")
            for cls, count in sorted(baseline.expected_detections.items()):
                lines.append(f"  - {cls}: ~{count:.1f} per hour")
        else:
            lines.append("No historical baseline for this time slot.")

        if baseline.current_detections:
            lines.append("Current activity:")
            for cls, count in sorted(baseline.current_detections.items()):
                lines.append(f"  - {cls}: {count}")

        if baseline.is_anomalous:
            lines.append(
                f"NOTICE: Activity is unusual for this time (deviation: {baseline.deviation_score:.2f})"
            )

        return "\n".join(lines)

    def format_cross_camera_summary(self, cross_camera: list[CrossCameraActivity]) -> str:
        """Format cross-camera activity for prompt inclusion.

        Args:
            cross_camera: List of cross-camera activities

        Returns:
            Formatted string for prompt

        Security:
            Sanitizes camera_name to prevent prompt injection via camera names.
            See NEM-1722 and backend/services/prompt_sanitizer.py for details.
        """
        if not cross_camera:
            return "No activity detected on other cameras."

        lines = []
        for activity in cross_camera:
            offset_desc = ""
            if abs(activity.time_offset_seconds) > 60:
                minutes = abs(activity.time_offset_seconds) / 60
                direction = "before" if activity.time_offset_seconds < 0 else "after"
                offset_desc = f" ({minutes:.0f} min {direction})"

            # Sanitize camera_name to prevent prompt injection (NEM-1722)
            safe_camera_name = sanitize_camera_name(activity.camera_name)
            types_str = ", ".join(activity.object_types) if activity.object_types else "unknown"
            lines.append(
                f"- {safe_camera_name}: {activity.detection_count} detection(s) "
                f"[{types_str}]{offset_desc}"
            )

        return "\n".join(lines)


def get_context_enricher() -> ContextEnricher:
    """Get or create the global context enricher singleton.

    Returns:
        The global ContextEnricher instance.
    """
    global _context_enricher  # noqa: PLW0603
    if _context_enricher is None:
        _context_enricher = ContextEnricher()
    return _context_enricher


def reset_context_enricher() -> None:
    """Reset the global context enricher singleton.

    Useful for testing to ensure a clean state.
    """
    global _context_enricher  # noqa: PLW0603
    _context_enricher = None
