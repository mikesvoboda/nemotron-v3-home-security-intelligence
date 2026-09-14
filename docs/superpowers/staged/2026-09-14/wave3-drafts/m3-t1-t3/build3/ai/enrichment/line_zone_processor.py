"""Line zone processor for virtual tripwire detection using Supervision.

This module provides the LineZoneProcessor class for detecting objects
crossing line zones (virtual tripwires) using the Supervision library.
It tracks crossings and reports direction (in/out) for each event.

The processor maintains state for each registered line zone and detects
when tracked objects cross from one side to the other.

Example:
    processor = LineZoneProcessor()
    processor.register_zone(
        zone_id=1,
        start=(100, 400),
        end=(500, 400),
        name="Driveway Entrance"
    )

    # Process detections from tracker
    crossings = processor.process_detections(detections)
    for crossing in crossings:
        print(f"Track {crossing.track_id} crossed '{crossing.zone_name}' {crossing.direction}")

Reference: https://supervision.roboflow.com/latest/detection/tools/line_zone/
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

try:
    import supervision as sv

    SUPERVISION_AVAILABLE = True
except ImportError:
    SUPERVISION_AVAILABLE = False
    sv = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


@dataclass
class LineCrossing:
    """A single line crossing event.

    Represents when an object crosses a line zone boundary.

    Attributes:
        zone_id: The database ID of the line zone that was crossed.
        zone_name: Human-readable name of the line zone.
        track_id: The tracker-assigned ID of the object that crossed.
                  May be -1 if track correlation is not available.
        direction: The direction of crossing, either "in" or "out".
                   Direction is determined by the line zone's normal vector.
    """

    zone_id: int
    zone_name: str
    track_id: int
    direction: str  # 'in' or 'out'

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "track_id": self.track_id,
            "direction": self.direction,
        }


@dataclass
class LineZoneState:
    """Internal state for a registered line zone.

    Attributes:
        zone: The Supervision LineZone instance for crossing detection.
        name: Human-readable name of the zone.
        previous_in_count: Last recorded in_count from the zone.
        previous_out_count: Last recorded out_count from the zone.
    """

    zone: Any  # sv.LineZone when supervision is available
    name: str
    previous_in_count: int = 0
    previous_out_count: int = 0


class LineZoneProcessor:
    """Processor for detecting line crossings using Supervision.

    This class wraps Supervision's LineZone functionality to detect when
    tracked objects cross virtual tripwire lines. It maintains state for
    multiple line zones and reports crossing events with direction.

    The processor tracks cumulative in/out counts for each zone and detects
    new crossings by comparing against previous counts. This allows it to
    report individual crossing events even when processing batched detections.

    Attributes:
        zones: Dictionary mapping zone IDs to LineZoneState objects.

    Example:
        # Initialize processor
        processor = LineZoneProcessor()

        # Register zones from database
        for zone in db_zones:
            processor.register_zone(
                zone_id=zone.id,
                start=(zone.start_x, zone.start_y),
                end=(zone.end_x, zone.end_y),
                name=zone.name
            )

        # Process detections each frame
        detections = tracker.update(frame, raw_detections)
        crossings = processor.process_detections(detections)

        # Handle crossings
        for crossing in crossings:
            await line_zone_service.increment_count(
                crossing.zone_id,
                crossing.direction
            )
    """

    def __init__(self) -> None:
        """Initialize the line zone processor.

        Raises:
            ImportError: If supervision library is not installed.
        """
        if not SUPERVISION_AVAILABLE:
            raise ImportError(
                "supervision library is required for LineZoneProcessor. "
                "Install with: pip install supervision"
            )

        self.zones: dict[int, LineZoneState] = {}
        logger.info("LineZoneProcessor initialized")

    def register_zone(
        self,
        zone_id: int,
        start: tuple[int, int],
        end: tuple[int, int],
        name: str,
        triggering_anchors: list[str] | None = None,
    ) -> None:
        """Register a line zone for crossing detection.

        Creates a Supervision LineZone with the specified coordinates and
        adds it to the processor's internal tracking.

        Args:
            zone_id: Unique database ID for the zone.
            start: Starting point coordinates (x, y) in pixels.
            end: Ending point coordinates (x, y) in pixels.
            name: Human-readable name for the zone.
            triggering_anchors: List of anchor points to use for triggering.
                                Defaults to ["BOTTOM_CENTER"] for person tracking.
                                Options: "CENTER", "BOTTOM_CENTER", "TOP_CENTER", etc.

        Example:
            processor.register_zone(
                zone_id=1,
                start=(100, 400),
                end=(500, 400),
                name="Driveway Entrance",
                triggering_anchors=["BOTTOM_CENTER"]
            )
        """
        if triggering_anchors is None:
            triggering_anchors = ["BOTTOM_CENTER"]

        # Convert string anchors to sv.Position enum values
        anchors = []
        for anchor in triggering_anchors:
            try:
                anchors.append(getattr(sv.Position, anchor.upper()))
            except AttributeError:
                logger.warning(f"Unknown anchor position: {anchor}, using CENTER")
                anchors.append(sv.Position.CENTER)

        # Create the LineZone with supervision
        line_zone = sv.LineZone(
            start=sv.Point(start[0], start[1]),
            end=sv.Point(end[0], end[1]),
            triggering_anchors=anchors,
        )

        self.zones[zone_id] = LineZoneState(
            zone=line_zone,
            name=name,
            previous_in_count=0,
            previous_out_count=0,
        )

        logger.debug(
            f"Registered line zone {zone_id}: '{name}' from {start} to {end}",
            extra={
                "zone_id": zone_id,
                "name": name,
                "start": start,
                "end": end,
            },
        )

    def unregister_zone(self, zone_id: int) -> bool:
        """Unregister a line zone.

        Args:
            zone_id: The ID of the zone to unregister.

        Returns:
            True if the zone was removed, False if not found.
        """
        if zone_id in self.zones:
            del self.zones[zone_id]
            logger.debug(f"Unregistered line zone {zone_id}")
            return True
        return False

    def process_detections(self, detections: sv.Detections) -> list[LineCrossing]:
        """Process detections and detect any new line crossings.

        Triggers all registered line zones with the provided detections
        and returns a list of any new crossing events that occurred.

        The method compares current cumulative counts against previous
        counts to detect new crossings. This allows accurate detection
        even when multiple crossings occur in a single frame.

        Args:
            detections: Supervision Detections object containing tracked
                        objects with bounding boxes and optional tracker IDs.

        Returns:
            List of LineCrossing events for any detected crossings.

        Example:
            # Process a frame's detections
            crossings = processor.process_detections(detections)

            # Log any crossings
            for crossing in crossings:
                logger.info(
                    f"Object {crossing.track_id} crossed "
                    f"'{crossing.zone_name}' going {crossing.direction}"
                )
        """
        crossings: list[LineCrossing] = []

        for zone_id, zone_state in self.zones.items():
            line_zone = zone_state.zone

            # Trigger the zone with detections
            # This updates in_count and out_count internally
            line_zone.trigger(detections)

            # Compare against previous counts to find new crossings
            new_in = line_zone.in_count - zone_state.previous_in_count
            new_out = line_zone.out_count - zone_state.previous_out_count

            # Generate crossing events for new IN crossings
            if new_in > 0:
                # Try to correlate with tracker IDs if available
                track_ids = self._get_crossing_track_ids(detections, new_in)
                for i in range(new_in):
                    track_id = track_ids[i] if i < len(track_ids) else -1
                    crossings.append(
                        LineCrossing(
                            zone_id=zone_id,
                            zone_name=zone_state.name,
                            track_id=track_id,
                            direction="in",
                        )
                    )

            # Generate crossing events for new OUT crossings
            if new_out > 0:
                track_ids = self._get_crossing_track_ids(detections, new_out)
                for i in range(new_out):
                    track_id = track_ids[i] if i < len(track_ids) else -1
                    crossings.append(
                        LineCrossing(
                            zone_id=zone_id,
                            zone_name=zone_state.name,
                            track_id=track_id,
                            direction="out",
                        )
                    )

            # Update previous counts
            zone_state.previous_in_count = line_zone.in_count
            zone_state.previous_out_count = line_zone.out_count

        if crossings:
            logger.debug(
                f"Detected {len(crossings)} line crossing(s)",
                extra={"crossings": [c.to_dict() for c in crossings]},
            )

        return crossings

    def _get_crossing_track_ids(self, detections: sv.Detections, count: int) -> list[int]:
        """Extract tracker IDs from detections for correlation.

        Note: This is a best-effort correlation. The Supervision LineZone
        does not directly report which specific tracks crossed, so we
        return available tracker IDs from the detections.

        Args:
            detections: The detections that triggered the crossing.
            count: Number of crossing events to correlate.

        Returns:
            List of tracker IDs (may be fewer than count if not available).
        """
        if detections.tracker_id is None:
            return []

        # Return unique tracker IDs up to the count
        track_ids = [int(tid) for tid in detections.tracker_id if tid is not None]
        return track_ids[:count]

    def get_zone_counts(self, zone_id: int) -> tuple[int, int] | None:
        """Get the current in/out counts for a zone.

        Args:
            zone_id: The ID of the zone.

        Returns:
            Tuple of (in_count, out_count) or None if zone not found.
        """
        if zone_id not in self.zones:
            return None

        zone_state = self.zones[zone_id]
        return (zone_state.zone.in_count, zone_state.zone.out_count)

    def reset_zone_counts(self, zone_id: int) -> bool:
        """Reset the in/out counts for a zone to zero.

        Note: This only resets the processor's internal tracking.
        The database counts should be reset separately via LineZoneService.

        Args:
            zone_id: The ID of the zone to reset.

        Returns:
            True if the zone was reset, False if not found.
        """
        if zone_id not in self.zones:
            return False

        zone_state = self.zones[zone_id]

        # Re-create the LineZone to reset counts
        # (Supervision LineZone doesn't expose a reset method)
        start = zone_state.zone.vector.start
        end = zone_state.zone.vector.end
        anchors = zone_state.zone.triggering_anchors

        zone_state.zone = sv.LineZone(
            start=sv.Point(int(start.x), int(start.y)),
            end=sv.Point(int(end.x), int(end.y)),
            triggering_anchors=anchors,
        )
        zone_state.previous_in_count = 0
        zone_state.previous_out_count = 0

        logger.debug(f"Reset counts for line zone {zone_id}")
        return True

    def reset_all_counts(self) -> None:
        """Reset the in/out counts for all registered zones."""
        for zone_id in list(self.zones.keys()):
            self.reset_zone_counts(zone_id)
        logger.info(f"Reset counts for all {len(self.zones)} line zones")

    def get_registered_zone_ids(self) -> list[int]:
        """Get list of all registered zone IDs.

        Returns:
            List of zone IDs currently registered with the processor.
        """
        return list(self.zones.keys())

    def is_zone_registered(self, zone_id: int) -> bool:
        """Check if a zone is registered.

        Args:
            zone_id: The ID of the zone to check.

        Returns:
            True if the zone is registered, False otherwise.
        """
        return zone_id in self.zones


@dataclass
class LineZoneProcessorConfig:
    """Configuration for LineZoneProcessor.

    Attributes:
        default_triggering_anchors: Default anchor points for triggering.
    """

    default_triggering_anchors: list[str] = field(default_factory=lambda: ["BOTTOM_CENTER"])


def create_line_zone_processor(
    _config: LineZoneProcessorConfig | None = None,
) -> LineZoneProcessor:
    """Factory function for creating a LineZoneProcessor.

    Args:
        _config: Optional configuration for the processor (reserved for future use).

    Returns:
        A new LineZoneProcessor instance.

    Raises:
        ImportError: If supervision library is not installed.
    """
    # Config is reserved for future configuration options
    return LineZoneProcessor()
