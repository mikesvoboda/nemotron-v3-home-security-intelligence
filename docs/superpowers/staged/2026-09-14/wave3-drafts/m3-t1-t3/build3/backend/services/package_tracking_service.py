"""Package tracking service for detecting and monitoring packages across frames.

This module provides a singleton service for tracking packages detected by YOLO-World
across multiple video frames. It manages package state transitions (delivered, present,
removed, suspicious_removal) and integrates with household member presence detection.

Key features:
- Track packages across frames using IoU (Intersection over Union) matching
- State machine: PRESENT -> DELIVERED (new) -> REMOVED or SUSPICIOUS_REMOVAL
- Integration with YOLO-World prompts for package detection
- Confidence threshold filtering (default 0.35)
- Automatic cleanup of old tracked packages

Usage:
    from backend.services.package_tracking_service import (
        get_package_tracking_service,
        PackageState,
    )

    service = get_package_tracking_service()

    # Process a detection from YOLO-World
    result = await service.process_detection(
        detection=detection_dict,
        camera_id="front_door",
        zone=zone_object,
        frame_timestamp=datetime.now(UTC),
    )

    # Check if removal is suspicious
    removal_result = await service.check_removal_context(
        camera_id="front_door",
        zone_id="delivery_zone_001",
        household_member_present=False,
        removal_timestamp=datetime.now(UTC),
    )
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# Default confidence threshold for package detection
PACKAGE_CONFIDENCE_THRESHOLD = 0.35

# IoU threshold for matching packages across frames
IOU_THRESHOLD = 0.5


class PackageState(StrEnum):
    """Enumeration of package tracking states.

    Attributes:
        PRESENT: Package is currently visible in frame
        DELIVERED: Package was newly detected (first appearance)
        REMOVED: Package was removed (no longer visible)
        SUSPICIOUS_REMOVAL: Package removed without household member present
    """

    PRESENT = "present"
    DELIVERED = "delivered"
    REMOVED = "removed"
    SUSPICIOUS_REMOVAL = "suspicious_removal"


@dataclass
class TrackedPackage:
    """Data class representing a tracked package.

    Attributes:
        id: Unique identifier for the tracked package
        bbox: Bounding box coordinates {x1, y1, x2, y2}
        confidence: Detection confidence score
        state: Current state of the package
        first_seen: Timestamp when package was first detected
        last_seen: Timestamp of most recent detection
        zone_id: ID of the zone where package is located (optional)
        camera_id: ID of the camera tracking this package
        removal_time: Timestamp when package was removed (optional)
        is_suspicious: Whether removal was flagged as suspicious
        class_name: YOLO-World detected class name
    """

    id: str
    bbox: dict[str, float]
    confidence: float
    state: PackageState
    first_seen: datetime
    last_seen: datetime
    zone_id: str | None
    camera_id: str
    removal_time: datetime | None = None
    is_suspicious: bool = False
    class_name: str = "package"

    def to_dict(self) -> dict[str, Any]:
        """Serialize the tracked package to a dictionary.

        Returns:
            Dictionary representation with all fields
        """
        return {
            "id": self.id,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "state": self.state.value,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "zone_id": self.zone_id,
            "camera_id": self.camera_id,
            "removal_time": self.removal_time.isoformat() if self.removal_time else None,
            "is_suspicious": self.is_suspicious,
            "class_name": self.class_name,
        }


@dataclass
class PackageDetectionResult:
    """Result from package detection operation.

    Attributes:
        detections: List of raw detection dictionaries from YOLO-World
        processing_time_ms: Time taken for detection in milliseconds
        has_packages: Whether any packages were detected
    """

    detections: list[dict[str, Any]]
    processing_time_ms: float = 0.0
    has_packages: bool = False

    def __post_init__(self) -> None:
        """Set has_packages based on detections."""
        self.has_packages = len(self.detections) > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result to a dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "detections": self.detections,
            "processing_time_ms": self.processing_time_ms,
            "has_packages": self.has_packages,
        }


def _calculate_iou(bbox1: dict[str, float], bbox2: dict[str, float]) -> float:
    """Calculate Intersection over Union (IoU) between two bounding boxes.

    Args:
        bbox1: First bounding box with x1, y1, x2, y2 keys
        bbox2: Second bounding box with x1, y1, x2, y2 keys

    Returns:
        IoU value between 0.0 and 1.0
    """
    x1_1, y1_1, x2_1, y2_1 = bbox1["x1"], bbox1["y1"], bbox1["x2"], bbox1["y2"]
    x1_2, y1_2, x2_2, y2_2 = bbox2["x1"], bbox2["y1"], bbox2["x2"], bbox2["y2"]

    # Calculate intersection
    x1_i = max(x1_1, x1_2)
    y1_i = max(y1_1, y1_2)
    x2_i = min(x2_1, x2_2)
    y2_i = min(y2_1, y2_2)

    if x2_i <= x1_i or y2_i <= y1_i:
        return 0.0

    intersection = (x2_i - x1_i) * (y2_i - y1_i)

    # Calculate union
    area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


class PackageTrackingService:
    """Singleton service for tracking packages across video frames.

    This service maintains state for all tracked packages across cameras,
    handles package state transitions, and integrates with YOLO-World for
    detection.

    The service uses IoU (Intersection over Union) matching to track the
    same package across multiple frames, even if it moves slightly.

    Example:
        service = PackageTrackingService()

        # Process detection from YOLO-World
        result = await service.process_detection(
            detection={"class_name": "Amazon box", "confidence": 0.72, "bbox": {...}},
            camera_id="front_door",
            zone=zone,
            frame_timestamp=datetime.now(UTC),
        )

        # Get all tracked packages for a camera
        packages = service.get_tracked_packages("front_door")
    """

    def __init__(self) -> None:
        """Initialize the PackageTrackingService."""
        # Track packages per camera: camera_id -> {package_id -> TrackedPackage}
        self._tracked_packages: dict[str, dict[str, TrackedPackage]] = {}
        self._confidence_threshold = PACKAGE_CONFIDENCE_THRESHOLD
        self._iou_threshold = IOU_THRESHOLD

    async def detect_packages(
        self,
        model: Any,
        image: Image.Image | Any,
    ) -> PackageDetectionResult:
        """Run YOLO-World package detection on an image.

        Args:
            model: YOLO-World model instance
            image: PIL Image or image path to process

        Returns:
            PackageDetectionResult containing detected packages
        """
        start_time = time.perf_counter()

        # Run detection through internal method
        detections = await self._run_yolo_world_detection(model, image)

        # Filter by confidence threshold
        filtered_detections = [
            d for d in detections if d.get("confidence", 0) >= self._confidence_threshold
        ]

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        return PackageDetectionResult(
            detections=filtered_detections,
            processing_time_ms=processing_time_ms,
        )

    async def _run_yolo_world_detection(
        self,
        model: Any,
        image: Image.Image | Any,
    ) -> list[dict[str, Any]]:
        """Internal method to run YOLO-World detection.

        This method is designed to be mocked in tests.

        Args:
            model: YOLO-World model instance
            image: Image to process

        Returns:
            List of detection dictionaries
        """
        from backend.services.yolo_world_loader import YOLO_WORLD_PROMPTS_V2, detect_with_prompts

        package_prompts = YOLO_WORLD_PROMPTS_V2["packages"]["prompts"]
        threshold = YOLO_WORLD_PROMPTS_V2["packages"]["threshold"]

        return await detect_with_prompts(
            model,
            image,
            prompts=package_prompts,
            confidence_threshold=threshold,
        )

    async def process_detection(
        self,
        detection: dict[str, Any],
        camera_id: str,
        zone: Any | None,
        frame_timestamp: datetime,
    ) -> TrackedPackage:
        """Process a single package detection and update tracking state.

        This method handles:
        - Creating new tracked packages for first-time detections
        - Updating existing packages via IoU matching
        - Managing state transitions (PRESENT -> DELIVERED, etc.)

        Args:
            detection: Detection dict with class_name, confidence, bbox
            camera_id: ID of the camera
            zone: Zone object (must have .id attribute) or None
            frame_timestamp: Timestamp of the frame

        Returns:
            TrackedPackage instance (new or updated)
        """
        bbox = detection.get("bbox", {})
        confidence = detection.get("confidence", 0.0)
        class_name = detection.get("class_name", "package")
        zone_id = zone.id if zone else None

        # Ensure camera has a tracking dict
        if camera_id not in self._tracked_packages:
            self._tracked_packages[camera_id] = {}

        # Try to match with existing package via IoU
        matched_package = self._find_matching_package(camera_id, bbox, zone_id)

        if matched_package:
            # Update existing package
            matched_package.bbox = bbox
            matched_package.confidence = confidence
            matched_package.last_seen = frame_timestamp
            # Keep state as DELIVERED or move to PRESENT if already tracked
            if matched_package.state not in (PackageState.DELIVERED, PackageState.PRESENT):
                matched_package.state = PackageState.PRESENT
            return matched_package
        else:
            # New package detected
            package_id = f"pkg_{uuid.uuid4().hex[:12]}"
            new_package = TrackedPackage(
                id=package_id,
                bbox=bbox,
                confidence=confidence,
                state=PackageState.DELIVERED,
                first_seen=frame_timestamp,
                last_seen=frame_timestamp,
                zone_id=zone_id,
                camera_id=camera_id,
                class_name=class_name,
            )
            self._tracked_packages[camera_id][package_id] = new_package
            logger.info(
                f"New package detected: {package_id} on camera {camera_id}",
                extra={"package_id": package_id, "camera_id": camera_id, "zone_id": zone_id},
            )
            return new_package

    def _find_matching_package(
        self,
        camera_id: str,
        bbox: dict[str, float],
        zone_id: str | None = None,  # noqa: ARG002 - zone_id reserved for future zone filtering
    ) -> TrackedPackage | None:
        """Find an existing tracked package that matches the given bbox.

        Uses IoU matching to find packages with overlapping bounding boxes.

        Args:
            camera_id: Camera ID to search
            bbox: Bounding box to match
            zone_id: Optional zone ID to filter by (reserved for future use)

        Returns:
            Matching TrackedPackage or None
        """
        if camera_id not in self._tracked_packages:
            return None

        best_match: TrackedPackage | None = None
        best_iou = 0.0

        for package in self._tracked_packages[camera_id].values():
            # Skip removed packages
            if package.state in (PackageState.REMOVED, PackageState.SUSPICIOUS_REMOVAL):
                continue

            iou = _calculate_iou(bbox, package.bbox)
            if iou >= self._iou_threshold and iou > best_iou:
                best_iou = iou
                best_match = package

        return best_match

    async def mark_package_removed(
        self,
        camera_id: str,
        zone_id: str,
        removal_timestamp: datetime,
    ) -> TrackedPackage | None:
        """Mark a package as removed from the zone.

        Args:
            camera_id: Camera ID
            zone_id: Zone ID where package was
            removal_timestamp: When the package was removed

        Returns:
            Updated TrackedPackage or None if no package found
        """
        if camera_id not in self._tracked_packages:
            return None

        # Find package in the specified zone
        for package in self._tracked_packages[camera_id].values():
            if package.zone_id == zone_id and package.state in (
                PackageState.DELIVERED,
                PackageState.PRESENT,
            ):
                package.state = PackageState.REMOVED
                package.removal_time = removal_timestamp
                logger.info(
                    f"Package removed: {package.id} from camera {camera_id}",
                    extra={"package_id": package.id, "camera_id": camera_id},
                )
                return package

        return None

    async def check_removal_context(
        self,
        camera_id: str,
        zone_id: str,
        household_member_present: bool,
        removal_timestamp: datetime,
        delivery_person_present: bool = False,
    ) -> TrackedPackage | None:
        """Check the context of a package removal to determine if suspicious.

        If no household member or delivery person is present during removal,
        the package is marked as SUSPICIOUS_REMOVAL.

        Args:
            camera_id: Camera ID
            zone_id: Zone ID where package was
            household_member_present: Whether a household member was detected
            removal_timestamp: When the package was removed
            delivery_person_present: Whether a delivery person was detected

        Returns:
            Updated TrackedPackage with is_suspicious flag set, or None
        """
        if camera_id not in self._tracked_packages:
            return None

        # Find package in the specified zone
        for package in self._tracked_packages[camera_id].values():
            if package.zone_id == zone_id and package.state in (
                PackageState.DELIVERED,
                PackageState.PRESENT,
            ):
                # Determine if removal is suspicious
                is_suspicious = not (household_member_present or delivery_person_present)

                if is_suspicious:
                    package.state = PackageState.SUSPICIOUS_REMOVAL
                    package.is_suspicious = True
                    logger.warning(
                        f"Suspicious package removal: {package.id}",
                        extra={
                            "package_id": package.id,
                            "camera_id": camera_id,
                            "household_member_present": household_member_present,
                            "delivery_person_present": delivery_person_present,
                        },
                    )
                else:
                    package.state = PackageState.REMOVED
                    package.is_suspicious = False

                package.removal_time = removal_timestamp
                return package

        return None

    def get_tracked_packages(
        self,
        camera_id: str,
        zone_id: str | None = None,
    ) -> list[TrackedPackage]:
        """Get all tracked packages for a camera.

        Args:
            camera_id: Camera ID
            zone_id: Optional zone ID to filter by

        Returns:
            List of TrackedPackage instances
        """
        if camera_id not in self._tracked_packages:
            return []

        packages = list(self._tracked_packages[camera_id].values())

        if zone_id is not None:
            packages = [p for p in packages if p.zone_id == zone_id]

        return packages

    async def cleanup_old_packages(
        self,
        retention_hours: int = 24,
    ) -> int:
        """Remove tracked packages older than retention period.

        Args:
            retention_hours: Maximum age in hours for tracked packages

        Returns:
            Number of packages cleaned up
        """
        cutoff_time = datetime.now(UTC) - timedelta(hours=retention_hours)
        removed_count = 0

        for camera_id in list(self._tracked_packages.keys()):
            packages_to_remove = []

            for package_id, package in self._tracked_packages[camera_id].items():
                if package.last_seen < cutoff_time:
                    packages_to_remove.append(package_id)

            for package_id in packages_to_remove:
                del self._tracked_packages[camera_id][package_id]
                removed_count += 1

            # Clean up empty camera entries
            if not self._tracked_packages[camera_id]:
                del self._tracked_packages[camera_id]

        if removed_count > 0:
            logger.info(
                f"Cleaned up {removed_count} old tracked packages",
                extra={"removed_count": removed_count, "retention_hours": retention_hours},
            )

        return removed_count

    def _should_include_detection(self, detection: dict[str, Any]) -> bool:
        """Check if a detection should be included based on confidence threshold.

        Args:
            detection: Detection dictionary with confidence key

        Returns:
            True if confidence >= threshold, False otherwise
        """
        confidence: float = detection.get("confidence", 0.0)
        return bool(confidence >= self._confidence_threshold)

    def _is_valid_bbox(self, bbox: dict[str, float]) -> bool:
        """Check if a bounding box has valid coordinates (0-1 range).

        Args:
            bbox: Dictionary with x1, y1, x2, y2 keys

        Returns:
            True if all coordinates are in valid range
        """
        try:
            for key in ["x1", "y1", "x2", "y2"]:
                value = bbox.get(key, -1)
                if not (0.0 <= value <= 1.0):
                    return False
            return True
        except (TypeError, ValueError):
            return False

    def reset(self) -> None:
        """Reset all tracked packages (useful for testing)."""
        self._tracked_packages.clear()


# Module-level singleton instance
_package_tracking_service: PackageTrackingService | None = None


def get_package_tracking_service() -> PackageTrackingService:
    """Get the singleton PackageTrackingService instance.

    Returns:
        The shared PackageTrackingService instance
    """
    global _package_tracking_service  # noqa: PLW0603 - singleton pattern requires global
    if _package_tracking_service is None:
        _package_tracking_service = PackageTrackingService()
    return _package_tracking_service


def reset_package_tracking_service() -> None:
    """Reset the singleton instance (primarily for testing)."""
    global _package_tracking_service  # noqa: PLW0603 - singleton pattern requires global
    _package_tracking_service = None
