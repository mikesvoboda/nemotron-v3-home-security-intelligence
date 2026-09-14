"""Loitering detector for zone-based dwell time tracking.

This module provides the LoiteringDetector class for real-time tracking of
object dwell time within polygon zones. It integrates with the polygon zone
processor to detect when objects exceed configured loitering thresholds.

The detector maintains in-memory state for active tracking sessions and
generates alerts when thresholds are exceeded. It is designed to be used
with the detection pipeline for frame-by-frame processing.

Example:
    from ai.enrichment.loitering_detector import LoiteringDetector

    # Create detector with 5-minute threshold
    detector = LoiteringDetector(default_threshold_seconds=300)

    # Register zones (can have different thresholds per zone)
    detector.register_zone(zone_id=1, threshold_seconds=300)
    detector.register_zone(zone_id=2, threshold_seconds=60)

    # Process detections from polygon zone processor
    alerts = detector.process_zone_results(zone_results, current_time)
    for alert in alerts:
        print(f"Loitering: {alert.object_class} in zone {alert.zone_id}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai.enrichment.polygon_zone_processor import ZoneCheckResult

logger = logging.getLogger(__name__)


@dataclass
class TrackedObject:
    """In-memory tracking state for an object in a zone.

    Attributes:
        track_id: The detection pipeline's tracking ID for the object.
        zone_id: The polygon zone the object is being tracked in.
        object_class: Classification of the object (e.g., "person").
        camera_id: The camera where the object was detected.
        entry_time: Timestamp when the object first entered the zone.
        last_seen: Timestamp when the object was last seen in the zone.
        alert_triggered: Whether a loitering alert has been generated.
    """

    track_id: int
    zone_id: int
    object_class: str
    camera_id: str
    entry_time: datetime
    last_seen: datetime
    alert_triggered: bool = False

    def get_dwell_seconds(self, current_time: datetime) -> float:
        """Calculate current dwell time in seconds.

        Args:
            current_time: The time to calculate dwell from.

        Returns:
            Dwell time in seconds from entry_time to current_time.
        """
        return (current_time - self.entry_time).total_seconds()


@dataclass
class LoiteringAlertData:
    """Data structure for a loitering alert event.

    Attributes:
        zone_id: The polygon zone where loitering was detected.
        track_id: The tracking ID of the loitering object.
        camera_id: The camera where detection occurred.
        object_class: Classification of the loitering object.
        entry_time: When the object entered the zone.
        dwell_seconds: Current dwell time in seconds.
        threshold_seconds: The threshold that was exceeded.
    """

    zone_id: int
    track_id: int
    camera_id: str
    object_class: str
    entry_time: datetime
    dwell_seconds: float
    threshold_seconds: float


@dataclass
class ZoneConfig:
    """Configuration for a monitored zone.

    Attributes:
        zone_id: The polygon zone ID.
        threshold_seconds: Dwell time threshold for loitering alerts.
        enabled: Whether loitering detection is enabled for this zone.
    """

    zone_id: int
    threshold_seconds: float
    enabled: bool = True


class LoiteringDetector:
    """Real-time loitering detection for polygon zones.

    This class tracks objects within polygon zones and generates alerts
    when objects exceed configured dwell time thresholds. It maintains
    in-memory state for efficient frame-by-frame processing.

    The detector is designed to work with the PolygonZoneProcessor's
    output, mapping zone check results to dwell time tracking.

    Key features:
    - Per-zone configurable thresholds
    - Efficient in-memory tracking
    - Automatic cleanup of stale tracks
    - Integration with polygon zone processor

    Attributes:
        default_threshold_seconds: Default threshold if zone not configured.
        stale_timeout_seconds: Time after which inactive tracks are cleaned up.
        zones: Dictionary of zone configurations.
        active_tracks: Nested dict of zone_id -> track_id -> TrackedObject.

    Example:
        detector = LoiteringDetector(
            default_threshold_seconds=300,
            stale_timeout_seconds=60,
        )

        # Process each frame
        for frame in frames:
            zone_results = zone_processor.process_detections(detections)
            alerts = detector.process_zone_results(
                zone_results,
                current_time=frame.timestamp,
            )
            for alert in alerts:
                await handle_loitering_alert(alert)
    """

    def __init__(
        self,
        default_threshold_seconds: float = 300.0,
        stale_timeout_seconds: float = 60.0,
    ) -> None:
        """Initialize the loitering detector.

        Args:
            default_threshold_seconds: Default loitering threshold in seconds.
                Used when a zone doesn't have a specific threshold configured.
            stale_timeout_seconds: Time in seconds after which inactive tracks
                are considered stale and cleaned up. This handles cases where
                exit events are missed.
        """
        self.default_threshold_seconds = default_threshold_seconds
        self.stale_timeout_seconds = stale_timeout_seconds
        self.zones: dict[int, ZoneConfig] = {}
        self.active_tracks: dict[int, dict[int, TrackedObject]] = {}

    def register_zone(
        self,
        zone_id: int,
        threshold_seconds: float | None = None,
        enabled: bool = True,
    ) -> None:
        """Register a zone for loitering detection.

        Args:
            zone_id: The polygon zone ID to monitor.
            threshold_seconds: Dwell time threshold in seconds.
                If None, uses default_threshold_seconds.
            enabled: Whether to enable loitering detection for this zone.

        Example:
            detector.register_zone(zone_id=1, threshold_seconds=300)
            detector.register_zone(zone_id=2, threshold_seconds=60)
        """
        self.zones[zone_id] = ZoneConfig(
            zone_id=zone_id,
            threshold_seconds=threshold_seconds or self.default_threshold_seconds,
            enabled=enabled,
        )
        if zone_id not in self.active_tracks:
            self.active_tracks[zone_id] = {}

        logger.debug(
            f"Registered zone {zone_id} for loitering detection "
            f"(threshold: {threshold_seconds}s, enabled: {enabled})",
            extra={
                "zone_id": zone_id,
                "threshold_seconds": threshold_seconds,
                "enabled": enabled,
            },
        )

    def unregister_zone(self, zone_id: int) -> bool:
        """Remove a zone from loitering detection.

        Args:
            zone_id: The zone ID to remove.

        Returns:
            True if the zone was removed, False if not found.
        """
        if zone_id in self.zones:
            del self.zones[zone_id]
            if zone_id in self.active_tracks:
                del self.active_tracks[zone_id]
            logger.debug(f"Unregistered zone {zone_id} from loitering detection")
            return True
        return False

    def clear(self) -> None:
        """Clear all zones and active tracks."""
        self.zones.clear()
        self.active_tracks.clear()
        logger.debug("Cleared all loitering detection state")

    def process_zone_results(
        self,
        zone_results: list[ZoneCheckResult],
        current_time: datetime | None = None,
        camera_id: str = "unknown",
        class_names: list[str] | None = None,
        track_ids: list[int] | None = None,
    ) -> list[LoiteringAlertData]:
        """Process zone check results and detect loitering.

        This method should be called once per frame with the results from
        PolygonZoneProcessor.process_detections(). It updates tracking state
        and returns any new loitering alerts.

        Args:
            zone_results: Results from polygon zone processor.
            current_time: Current timestamp. If None, uses UTC now.
            camera_id: Camera identifier for the frame.
            class_names: Object class names corresponding to detection indices.
                If None, uses "unknown" for all objects.
            track_ids: Tracking IDs corresponding to detection indices.
                If None, uses detection indices as track IDs.

        Returns:
            List of new loitering alerts (only alerts not previously triggered).

        Example:
            zone_results = zone_processor.process_detections(detections)
            alerts = detector.process_zone_results(
                zone_results,
                current_time=frame_time,
                camera_id="front_door",
                class_names=detections.data.get("class_name"),
                track_ids=detections.tracker_id,
            )
        """
        now = current_time or datetime.now(UTC)
        alerts: list[LoiteringAlertData] = []

        for result in zone_results:
            zone_id = result.zone_id

            # Skip if zone not registered or disabled
            zone_config = self.zones.get(zone_id)
            if zone_config is None or not zone_config.enabled:
                continue

            # Ensure zone has tracking dict
            if zone_id not in self.active_tracks:
                self.active_tracks[zone_id] = {}

            zone_tracks = self.active_tracks[zone_id]

            # Get current track IDs in zone
            current_track_ids_in_zone: set[int] = set()

            for detection_idx in result.detection_indices:
                # Get track ID (use index if not provided)
                track_id = track_ids[detection_idx] if track_ids is not None else detection_idx
                current_track_ids_in_zone.add(track_id)

                # Get object class
                object_class = (
                    class_names[detection_idx]
                    if class_names is not None and len(class_names) > detection_idx
                    else "unknown"
                )

                # Check if already tracking this object
                if track_id in zone_tracks:
                    # Update last seen
                    tracked = zone_tracks[track_id]
                    tracked.last_seen = now

                    # Check for loitering threshold
                    dwell_seconds = tracked.get_dwell_seconds(now)
                    if (
                        dwell_seconds >= zone_config.threshold_seconds
                        and not tracked.alert_triggered
                    ):
                        # Generate alert
                        tracked.alert_triggered = True
                        alerts.append(
                            LoiteringAlertData(
                                zone_id=zone_id,
                                track_id=track_id,
                                camera_id=tracked.camera_id,
                                object_class=tracked.object_class,
                                entry_time=tracked.entry_time,
                                dwell_seconds=dwell_seconds,
                                threshold_seconds=zone_config.threshold_seconds,
                            )
                        )
                        logger.warning(
                            f"Loitering detected: track {track_id} in zone {zone_id} "
                            f"for {dwell_seconds:.1f}s",
                            extra={
                                "zone_id": zone_id,
                                "track_id": track_id,
                                "dwell_seconds": dwell_seconds,
                                "threshold_seconds": zone_config.threshold_seconds,
                            },
                        )
                else:
                    # New object entering zone
                    zone_tracks[track_id] = TrackedObject(
                        track_id=track_id,
                        zone_id=zone_id,
                        object_class=object_class,
                        camera_id=camera_id,
                        entry_time=now,
                        last_seen=now,
                    )
                    logger.debug(
                        f"Track {track_id} entered zone {zone_id}",
                        extra={
                            "zone_id": zone_id,
                            "track_id": track_id,
                            "object_class": object_class,
                        },
                    )

            # Remove tracks that have left the zone
            exited_tracks = set(zone_tracks.keys()) - current_track_ids_in_zone
            for track_id in exited_tracks:
                tracked = zone_tracks.pop(track_id)
                dwell_seconds = tracked.get_dwell_seconds(now)
                logger.debug(
                    f"Track {track_id} exited zone {zone_id} after {dwell_seconds:.1f}s",
                    extra={
                        "zone_id": zone_id,
                        "track_id": track_id,
                        "dwell_seconds": dwell_seconds,
                    },
                )

        return alerts

    def cleanup_stale_tracks(
        self,
        current_time: datetime | None = None,
    ) -> int:
        """Remove stale tracks that haven't been seen recently.

        Tracks that haven't been updated within stale_timeout_seconds are
        considered to have left the zone (exit event was missed) and are
        removed from tracking.

        Args:
            current_time: Current timestamp. If None, uses UTC now.

        Returns:
            Number of tracks removed.
        """
        now = current_time or datetime.now(UTC)
        removed = 0

        for zone_id, zone_tracks in self.active_tracks.items():
            stale_track_ids = [
                track_id
                for track_id, tracked in zone_tracks.items()
                if (now - tracked.last_seen).total_seconds() > self.stale_timeout_seconds
            ]
            for track_id in stale_track_ids:
                tracked = zone_tracks.pop(track_id)
                removed += 1
                logger.debug(
                    f"Removed stale track {track_id} from zone {zone_id}",
                    extra={
                        "zone_id": zone_id,
                        "track_id": track_id,
                        "dwell_seconds": tracked.get_dwell_seconds(now),
                    },
                )

        return removed

    def get_active_dwellers(self, zone_id: int) -> list[TrackedObject]:
        """Get all objects currently tracked in a zone.

        Args:
            zone_id: The zone to query.

        Returns:
            List of TrackedObject instances for active dwellers.
        """
        return list(self.active_tracks.get(zone_id, {}).values())

    def get_zone_threshold(self, zone_id: int) -> float:
        """Get the loitering threshold for a zone.

        Args:
            zone_id: The zone to query.

        Returns:
            Threshold in seconds, or default if zone not configured.
        """
        config = self.zones.get(zone_id)
        return config.threshold_seconds if config else self.default_threshold_seconds

    def set_zone_threshold(self, zone_id: int, threshold_seconds: float) -> bool:
        """Update the loitering threshold for a zone.

        Args:
            zone_id: The zone to update.
            threshold_seconds: New threshold in seconds.

        Returns:
            True if zone was found and updated, False otherwise.
        """
        config = self.zones.get(zone_id)
        if config is None:
            return False
        config.threshold_seconds = threshold_seconds
        return True

    def set_zone_enabled(self, zone_id: int, enabled: bool) -> bool:
        """Enable or disable loitering detection for a zone.

        Args:
            zone_id: The zone to update.
            enabled: Whether to enable loitering detection.

        Returns:
            True if zone was found and updated, False otherwise.
        """
        config = self.zones.get(zone_id)
        if config is None:
            return False
        config.enabled = enabled
        return True

    @property
    def zone_count(self) -> int:
        """Get the number of registered zones."""
        return len(self.zones)

    @property
    def total_active_tracks(self) -> int:
        """Get total number of active tracks across all zones."""
        return sum(len(tracks) for tracks in self.active_tracks.values())


# Module-level singleton for shared state
_loitering_detector: LoiteringDetector | None = None


def get_loitering_detector(
    default_threshold_seconds: float = 300.0,
    stale_timeout_seconds: float = 60.0,
) -> LoiteringDetector:
    """Get the shared loitering detector instance.

    Creates a new instance if one doesn't exist, otherwise returns
    the existing singleton.

    Args:
        default_threshold_seconds: Default threshold for new instance.
        stale_timeout_seconds: Stale timeout for new instance.

    Returns:
        The shared LoiteringDetector instance.
    """
    global _loitering_detector
    if _loitering_detector is None:
        _loitering_detector = LoiteringDetector(
            default_threshold_seconds=default_threshold_seconds,
            stale_timeout_seconds=stale_timeout_seconds,
        )
    return _loitering_detector


def reset_loitering_detector() -> None:
    """Reset the shared loitering detector instance.

    Used primarily for testing to ensure clean state between tests.
    """
    global _loitering_detector
    _loitering_detector = None
