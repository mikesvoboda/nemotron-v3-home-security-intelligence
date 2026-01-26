"""Polygon zone processor for intrusion detection using supervision.

This module provides the PolygonZoneProcessor class for real-time detection
of objects entering, exiting, or dwelling within defined polygon areas.
It wraps the supervision library's PolygonZone for efficient zone checking.

The processor maintains registered zones and checks detection bounding boxes
against all zones in a single pass, returning results that indicate which
detections are in each zone and whether alert thresholds are exceeded.

Example:
    from ai.enrichment.polygon_zone_processor import PolygonZoneProcessor

    # Create processor and register zones
    processor = PolygonZoneProcessor()
    processor.register_zone(
        zone_id=1,
        polygon=[[100, 100], [400, 100], [400, 300], [100, 300]],
        name="Restricted Area",
        threshold=1,
    )

    # Process detections
    results = processor.process_detections(detections)
    for result in results:
        if result.alert_triggered:
            print(f"Alert: {result.current_count} objects in {result.zone_name}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import numpy as np

if TYPE_CHECKING:
    import supervision as sv

logger = logging.getLogger(__name__)


@dataclass
class ZoneCheckResult:
    """Result of checking detections against a polygon zone.

    This dataclass holds the results of processing detections through
    a registered polygon zone, including which detections are in the zone
    and whether the alert threshold has been exceeded.

    Attributes:
        zone_id: The unique identifier of the zone.
        zone_name: Human-readable name of the zone.
        in_zone_mask: Boolean numpy array indicating which detections
            are inside the zone. Shape matches the number of detections.
        current_count: The number of detections currently in the zone.
        alert_triggered: True if current_count exceeds the zone's threshold,
            or if threshold is 0 and any detection is present.
        detection_indices: List of indices of detections inside the zone.

    Example:
        result = ZoneCheckResult(
            zone_id=1,
            zone_name="Restricted Area",
            in_zone_mask=np.array([True, False, True]),
            current_count=2,
            alert_triggered=True,
            detection_indices=[0, 2],
        )
    """

    zone_id: int
    zone_name: str
    in_zone_mask: np.ndarray
    current_count: int
    alert_triggered: bool
    detection_indices: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Compute detection indices from mask if not provided."""
        if not self.detection_indices and self.in_zone_mask is not None:
            self.detection_indices = list(np.where(self.in_zone_mask)[0])


@dataclass
class ZoneConfig:
    """Configuration for a registered polygon zone.

    Attributes:
        zone: The supervision PolygonZone instance.
        name: Human-readable name of the zone.
        threshold: Alert threshold (0 = any entry triggers alert).
        target_classes: List of object classes to monitor (optional).
    """

    zone: Any  # sv.PolygonZone - typed as Any for lazy import
    name: str
    threshold: int
    target_classes: list[str] = field(default_factory=list)


class PolygonZoneProcessor:
    """Processor for checking detections against registered polygon zones.

    This class manages a collection of polygon zones and provides efficient
    detection checking against all registered zones. It uses the supervision
    library's PolygonZone for spatial containment testing.

    The processor is designed to be:
    - Stateless between frames (zones can be dynamically registered/removed)
    - Thread-safe for read operations
    - Efficient for checking many detections against multiple zones

    Attributes:
        zones: Dictionary mapping zone IDs to their configurations.

    Example:
        processor = PolygonZoneProcessor()

        # Register zones from database
        for zone in db_zones:
            processor.register_zone(
                zone_id=zone.id,
                polygon=zone.polygon,
                name=zone.name,
                threshold=zone.alert_threshold,
                target_classes=zone.target_classes,
            )

        # Process frame detections
        results = processor.process_detections(detections)

        # Handle alerts
        for result in results:
            if result.alert_triggered:
                await send_alert(result)
    """

    def __init__(self) -> None:
        """Initialize the polygon zone processor."""
        self.zones: dict[int, ZoneConfig] = {}
        self._sv: Any = None  # Lazy import of supervision

    def _get_supervision(self) -> Any:
        """Lazily import supervision library.

        Returns:
            The supervision module.

        Raises:
            ImportError: If supervision is not installed.
        """
        if self._sv is None:
            try:
                import supervision as sv

                self._sv = sv
            except ImportError as e:
                logger.error("supervision library not installed")
                raise ImportError(
                    "supervision library required for polygon zone processing. "
                    "Install with: pip install supervision"
                ) from e
        return self._sv

    def register_zone(
        self,
        zone_id: int,
        polygon: list[list[int]],
        name: str,
        threshold: int = 0,
        target_classes: list[str] | None = None,
    ) -> None:
        """Register a polygon zone for processing.

        Creates a supervision PolygonZone from the polygon coordinates
        and stores it with the associated configuration.

        Args:
            zone_id: Unique identifier for the zone.
            polygon: List of [x, y] coordinate pairs defining the polygon
                vertices. Must have at least 3 points.
            name: Human-readable name for the zone.
            threshold: Alert threshold - alerts trigger when count exceeds
                this value. Use 0 to alert on any entry.
            target_classes: Optional list of object classes to monitor
                (e.g., ["person", "car"]). If None, all classes are monitored.

        Raises:
            ValueError: If polygon has fewer than 3 points.

        Example:
            processor.register_zone(
                zone_id=1,
                polygon=[[100, 100], [400, 100], [400, 300], [100, 300]],
                name="Pool Area",
                threshold=1,
                target_classes=["person"],
            )
        """
        if len(polygon) < 3:
            raise ValueError(f"Polygon must have at least 3 points, got {len(polygon)}")

        sv = self._get_supervision()

        # Convert to numpy array
        polygon_np = np.array(polygon, dtype=np.int32)

        # Create supervision PolygonZone
        # Using BOTTOM_CENTER as the triggering anchor - detects when the bottom
        # center of a bounding box enters the zone (good for standing people)
        zone = sv.PolygonZone(
            polygon=polygon_np,
            triggering_anchors=[sv.Position.BOTTOM_CENTER],
        )

        self.zones[zone_id] = ZoneConfig(
            zone=zone,
            name=name,
            threshold=threshold,
            target_classes=target_classes or [],
        )

        logger.debug(
            f"Registered polygon zone {zone_id} '{name}' with {len(polygon)} vertices",
            extra={
                "zone_id": zone_id,
                "zone_name": name,
                "threshold": threshold,
                "vertex_count": len(polygon),
            },
        )

    def unregister_zone(self, zone_id: int) -> bool:
        """Remove a registered zone.

        Args:
            zone_id: The ID of the zone to remove.

        Returns:
            True if the zone was removed, False if not found.
        """
        if zone_id in self.zones:
            del self.zones[zone_id]
            logger.debug(f"Unregistered polygon zone {zone_id}")
            return True
        return False

    def clear_zones(self) -> None:
        """Remove all registered zones."""
        self.zones.clear()
        logger.debug("Cleared all polygon zones")

    def process_detections(
        self,
        detections: sv.Detections,
        class_filter: list[str] | None = None,
    ) -> list[ZoneCheckResult]:
        """Check detections against all registered zones.

        Processes the given detections through each registered zone and
        returns results indicating which detections are in each zone.

        Args:
            detections: A supervision Detections object containing bounding
                boxes and optional class information.
            class_filter: Optional list of class names to filter detections
                before zone checking. If None, all detections are checked.

        Returns:
            List of ZoneCheckResult for each registered zone, containing
            the in-zone mask, count, and alert status.

        Example:
            # Process detections from a detector
            detections = detector.detect(frame)
            results = processor.process_detections(detections)

            for result in results:
                print(f"{result.zone_name}: {result.current_count} objects")
                if result.alert_triggered:
                    print(f"  ALERT triggered!")
        """
        if not self.zones:
            return []

        results: list[ZoneCheckResult] = []

        for zone_id, zone_config in self.zones.items():
            # Apply class filter if specified
            filtered_detections = detections
            if class_filter or zone_config.target_classes:
                filtered_detections = self._filter_by_class(
                    detections,
                    class_filter or zone_config.target_classes,
                )

            # Check detections against zone
            in_zone_mask = zone_config.zone.trigger(filtered_detections)
            current_count = int(zone_config.zone.current_count)

            # Determine if alert should be triggered
            # threshold=0 means alert on any entry
            # threshold>0 means alert when count exceeds threshold
            if zone_config.threshold == 0:
                alert_triggered = current_count > 0
            else:
                alert_triggered = current_count > zone_config.threshold

            results.append(
                ZoneCheckResult(
                    zone_id=zone_id,
                    zone_name=zone_config.name,
                    in_zone_mask=in_zone_mask,
                    current_count=current_count,
                    alert_triggered=alert_triggered,
                )
            )

        return results

    def _filter_by_class(
        self,
        detections: sv.Detections,
        target_classes: list[str],
    ) -> sv.Detections:
        """Filter detections to only include specified classes.

        Args:
            detections: Original detections object.
            target_classes: List of class names to keep.

        Returns:
            Filtered detections containing only the target classes.
        """
        if not target_classes:
            return detections

        # Get class names from detections if available
        if not hasattr(detections, "data") or "class_name" not in detections.data:
            # No class information, return all detections
            return detections

        class_names = detections.data["class_name"]
        mask = np.isin(class_names, target_classes)
        # Supervision's __getitem__ with bool array always returns Detections
        return cast("sv.Detections", detections[mask])

    def get_zone_polygon(self, zone_id: int) -> np.ndarray | None:
        """Get the polygon coordinates for a zone.

        Args:
            zone_id: The zone ID.

        Returns:
            Numpy array of polygon vertices, or None if zone not found.
        """
        if zone_id not in self.zones:
            return None
        polygon: np.ndarray = self.zones[zone_id].zone.polygon
        return polygon

    def get_zone_count(self, zone_id: int) -> int | None:
        """Get the current count for a specific zone.

        This returns the count from the last trigger() call.

        Args:
            zone_id: The zone ID.

        Returns:
            The current count, or None if zone not found.
        """
        if zone_id not in self.zones:
            return None
        return int(self.zones[zone_id].zone.current_count)

    @property
    def zone_count(self) -> int:
        """Get the number of registered zones."""
        return len(self.zones)

    def __len__(self) -> int:
        """Return the number of registered zones."""
        return len(self.zones)

    def __contains__(self, zone_id: int) -> bool:
        """Check if a zone is registered."""
        return zone_id in self.zones
