"""Test factories using factory_boy for generating test data.

This module provides factory classes for creating test instances of database models.
Factories reduce boilerplate in tests and ensure consistent test data creation.

Usage:
    from backend.tests.factories import CameraFactory, DetectionFactory, EventFactory

    # Create a camera with default values
    camera = CameraFactory()

    # Create a camera with specific values
    camera = CameraFactory(id="custom_id", name="Custom Camera")

    # Create multiple cameras
    cameras = CameraFactory.create_batch(5)

    # Build without saving (useful for unit tests)
    camera = CameraFactory.build()

Note:
    These factories create plain model instances without database persistence.
    For database tests, use with the appropriate database fixtures.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import factory
from factory import LazyAttribute, LazyFunction, Sequence, SubFactory

from backend.models.alert import Alert, AlertRule, AlertSeverity, AlertStatus
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.zone import Zone, ZoneShape, ZoneType


class CameraFactory(factory.Factory):
    """Factory for creating Camera model instances.

    Examples:
        # Create a camera with default values
        camera = CameraFactory()

        # Create a camera with custom values
        camera = CameraFactory(id="front_door", name="Front Door")

        # Create multiple cameras
        cameras = CameraFactory.create_batch(3)
    """

    class Meta:
        model = Camera

    id: str = Sequence(lambda n: f"camera_{n}")
    name: str = Sequence(lambda n: f"Camera {n}")
    folder_path: str = LazyAttribute(lambda o: f"/export/foscam/{o.name.replace(' ', '_').lower()}")
    status: str = "online"
    created_at: datetime = LazyFunction(lambda: datetime.now(UTC))
    last_seen_at: datetime | None = None

    class Params:
        """Traits for common camera configurations."""

        offline = factory.Trait(status="offline")
        with_last_seen = factory.Trait(last_seen_at=LazyFunction(lambda: datetime.now(UTC)))


class DetectionFactory(factory.Factory):
    """Factory for creating Detection model instances.

    Examples:
        # Create a detection with default values
        detection = DetectionFactory()

        # Create a person detection
        detection = DetectionFactory(object_type="person", confidence=0.95)

        # Create a video detection
        detection = DetectionFactory(video=True, duration=30.5)
    """

    class Meta:
        model = Detection

    id: int = Sequence(lambda n: n + 1)
    camera_id: str = Sequence(lambda n: f"camera_{n}")
    file_path: str = LazyAttribute(lambda o: f"/export/foscam/{o.camera_id}/image_{o.id:04d}.jpg")
    file_type: str = "image/jpeg"
    detected_at: datetime = LazyFunction(lambda: datetime.now(UTC))
    object_type: str = "person"
    confidence: float = 0.90
    bbox_x: int = 100
    bbox_y: int = 200
    bbox_width: int = 150
    bbox_height: int = 300
    thumbnail_path: str | None = None
    media_type: str = "image"
    duration: float | None = None
    video_codec: str | None = None
    video_width: int | None = None
    video_height: int | None = None
    enrichment_data: dict[str, Any] | None = None

    class Params:
        """Traits for common detection configurations."""

        # Video detection trait
        video = factory.Trait(
            media_type="video",
            file_type="video/mp4",
            file_path=LazyAttribute(lambda o: f"/export/foscam/{o.camera_id}/video_{o.id:04d}.mp4"),
            duration=30.0,
            video_codec="h264",
            video_width=1920,
            video_height=1080,
        )

        # High confidence detection
        high_confidence = factory.Trait(confidence=0.98)

        # Low confidence detection
        low_confidence = factory.Trait(confidence=0.45)

        # Vehicle detection
        vehicle = factory.Trait(object_type="vehicle")

        # Animal detection
        animal = factory.Trait(object_type="animal")


class EventFactory(factory.Factory):
    """Factory for creating Event model instances.

    Examples:
        # Create an event with default values
        event = EventFactory()

        # Create a high-risk event
        event = EventFactory(high_risk=True)

        # Create a reviewed event
        event = EventFactory(reviewed=True, notes="False positive")
    """

    class Meta:
        model = Event

    id: int = Sequence(lambda n: n + 1)
    batch_id: str = Sequence(lambda n: f"batch_{n:08d}")
    camera_id: str = Sequence(lambda n: f"camera_{n}")
    started_at: datetime = LazyFunction(lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    risk_score: int = 50
    risk_level: str = "medium"
    summary: str = LazyAttribute(lambda o: f"Event detected on {o.camera_id}")
    reasoning: str = "Standard detection analysis"
    llm_prompt: str | None = None
    detection_ids: str = "1,2,3"
    reviewed: bool = False
    notes: str | None = None
    is_fast_path: bool = False
    object_types: str = "person"
    clip_path: str | None = None
    search_vector = None

    class Params:
        """Traits for common event configurations."""

        # Low risk event
        low_risk = factory.Trait(
            risk_score=15,
            risk_level="low",
        )

        # High risk event
        high_risk = factory.Trait(
            risk_score=85,
            risk_level="high",
            summary="High risk activity detected",
            reasoning="Suspicious behavior at entry point during night hours",
        )

        # Critical risk event
        critical = factory.Trait(
            risk_score=95,
            risk_level="critical",
            summary="Critical security event",
            reasoning="Immediate attention required - unauthorized access attempt",
        )

        # Reviewed event
        reviewed_event = factory.Trait(
            reviewed=True,
            notes="Reviewed and confirmed",
        )

        # Fast path event
        fast_path = factory.Trait(
            is_fast_path=True,
            risk_score=90,
            risk_level="high",
        )

        # With clip
        with_clip = factory.Trait(clip_path=LazyAttribute(lambda o: f"/clips/event_{o.id}.mp4"))


class ZoneFactory(factory.Factory):
    """Factory for creating Zone model instances.

    Examples:
        # Create a zone with default values
        zone = ZoneFactory()

        # Create a driveway zone
        zone = ZoneFactory(driveway=True)

        # Create a disabled zone
        zone = ZoneFactory(enabled=False)
    """

    class Meta:
        model = Zone

    id: str = Sequence(lambda n: f"zone_{n}")
    camera_id: str = Sequence(lambda n: f"camera_{n}")
    name: str = Sequence(lambda n: f"Zone {n}")
    zone_type: ZoneType = ZoneType.OTHER
    coordinates: list = factory.LazyFunction(
        lambda: [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]]
    )
    shape: ZoneShape = ZoneShape.RECTANGLE
    color: str = "#3B82F6"
    enabled: bool = True
    priority: int = 0
    created_at: datetime = LazyFunction(lambda: datetime.now(UTC))
    updated_at: datetime = LazyFunction(lambda: datetime.now(UTC))

    class Params:
        """Traits for common zone configurations."""

        # Entry point zone
        entry_point = factory.Trait(
            zone_type=ZoneType.ENTRY_POINT,
            name="Entry Point",
            color="#EF4444",  # Red
            priority=10,
        )

        # Driveway zone
        driveway = factory.Trait(
            zone_type=ZoneType.DRIVEWAY,
            name="Driveway",
            color="#F59E0B",  # Orange
            priority=5,
        )

        # Sidewalk zone
        sidewalk = factory.Trait(
            zone_type=ZoneType.SIDEWALK,
            name="Sidewalk",
            color="#10B981",  # Green
            priority=1,
        )

        # Yard zone
        yard = factory.Trait(
            zone_type=ZoneType.YARD,
            name="Yard",
            color="#3B82F6",  # Blue
            priority=2,
        )

        # Polygon zone
        polygon = factory.Trait(
            shape=ZoneShape.POLYGON,
            coordinates=[
                [0.2, 0.1],
                [0.5, 0.1],
                [0.6, 0.5],
                [0.4, 0.9],
                [0.1, 0.6],
            ],
        )

        # Disabled zone
        disabled = factory.Trait(enabled=False)


class AlertFactory(factory.Factory):
    """Factory for creating Alert model instances.

    Examples:
        # Create an alert with default values
        alert = AlertFactory()

        # Create a high severity alert
        alert = AlertFactory(high_severity=True)

        # Create a delivered alert
        alert = AlertFactory(delivered=True)
    """

    class Meta:
        model = Alert

    id: str = Sequence(lambda n: f"alert_{n:06d}")
    event_id: int = Sequence(lambda n: n + 1)
    rule_id: str | None = Sequence(lambda n: f"rule_{n:03d}")
    severity: AlertSeverity = AlertSeverity.MEDIUM
    status: AlertStatus = AlertStatus.PENDING
    dedup_key: str = LazyAttribute(lambda o: f"camera_{o.event_id}:{o.rule_id}")
    channels: list[str] = factory.LazyFunction(lambda: ["push"])
    alert_metadata: dict[str, Any] | None = None
    created_at: datetime = LazyFunction(lambda: datetime.now(UTC))
    delivered_at: datetime | None = None

    class Params:
        """Traits for common alert configurations."""

        # Low severity alert
        low_severity = factory.Trait(severity=AlertSeverity.LOW)

        # High severity alert
        high_severity = factory.Trait(severity=AlertSeverity.HIGH)

        # Critical severity alert
        critical = factory.Trait(severity=AlertSeverity.CRITICAL)

        # Delivered alert
        delivered = factory.Trait(
            status=AlertStatus.DELIVERED,
            delivered_at=LazyFunction(lambda: datetime.now(UTC)),
        )

        # Acknowledged alert
        acknowledged = factory.Trait(status=AlertStatus.ACKNOWLEDGED)

        # Dismissed alert
        dismissed = factory.Trait(status=AlertStatus.DISMISSED)


class AlertRuleFactory(factory.Factory):
    """Factory for creating AlertRule model instances.

    Examples:
        # Create an alert rule with default values
        rule = AlertRuleFactory()

        # Create a disabled rule
        rule = AlertRuleFactory(enabled=False)

        # Create a high severity rule
        rule = AlertRuleFactory(high_severity=True)
    """

    class Meta:
        model = AlertRule

    id: str = Sequence(lambda n: f"rule_{n:03d}")
    name: str = Sequence(lambda n: f"Alert Rule {n}")
    enabled: bool = True
    severity: AlertSeverity = AlertSeverity.MEDIUM
    risk_threshold: int | None = 70
    camera_ids: list[str] | None = None
    object_types: list[str] | None = None
    min_confidence: float | None = 0.8
    cooldown_seconds: int = 300
    channels: list[str] = factory.LazyFunction(lambda: ["push"])
    schedule: dict[str, Any] | None = None
    dedup_key_template: str | None = "{camera_id}:{rule_id}"
    created_at: datetime = LazyFunction(lambda: datetime.now(UTC))
    updated_at: datetime = LazyFunction(lambda: datetime.now(UTC))

    class Params:
        """Traits for common alert rule configurations."""

        # Low severity rule
        low_severity = factory.Trait(
            severity=AlertSeverity.LOW,
            risk_threshold=30,
        )

        # High severity rule
        high_severity = factory.Trait(
            severity=AlertSeverity.HIGH,
            risk_threshold=80,
        )

        # Critical severity rule
        critical = factory.Trait(
            severity=AlertSeverity.CRITICAL,
            risk_threshold=90,
        )

        # Disabled rule
        disabled = factory.Trait(enabled=False)

        # Person detection rule
        person_detection = factory.Trait(
            name="Person Detection",
            object_types=["person"],
            min_confidence=0.85,
        )


# =============================================================================
# Related Model Factories
# =============================================================================


class CameraWithDetectionsFactory(CameraFactory):
    """Factory for creating a Camera with related Detection instances.

    This factory creates a Camera and can optionally build associated detections.

    Examples:
        # Create camera with 3 detections
        camera = CameraWithDetectionsFactory.create(num_detections=3)
    """

    @classmethod
    def _create(cls, model_class: type, *args: Any, **kwargs: Any) -> Camera:
        """Override create to optionally add detections."""
        num_detections = kwargs.pop("num_detections", 0)
        camera = super()._create(model_class, *args, **kwargs)

        if num_detections > 0:
            # Create detections for this camera
            for _ in range(num_detections):
                DetectionFactory(camera_id=camera.id)

        return camera


class EventWithCameraFactory(EventFactory):
    """Factory for creating an Event with a related Camera.

    This factory ensures the event's camera_id matches an actual Camera.

    Examples:
        # Create event with associated camera
        event = EventWithCameraFactory.create()
        # event.camera_id will match a CameraFactory-generated camera
    """

    camera: Camera = SubFactory(CameraFactory)
    camera_id: str = LazyAttribute(lambda o: o.camera.id)


# =============================================================================
# Batch Creation Helpers
# =============================================================================


def create_camera_with_events(
    camera_kwargs: dict[str, Any] | None = None,
    num_events: int = 3,
    event_kwargs: dict[str, Any] | None = None,
) -> tuple[Camera, list[Event]]:
    """Create a camera with multiple associated events.

    Args:
        camera_kwargs: Optional kwargs to pass to CameraFactory
        num_events: Number of events to create
        event_kwargs: Optional kwargs to pass to EventFactory

    Returns:
        Tuple of (camera, list of events)

    Example:
        camera, events = create_camera_with_events(
            camera_kwargs={"name": "Front Door"},
            num_events=5,
            event_kwargs={"risk_score": 75}
        )
    """
    camera_kwargs = camera_kwargs or {}
    event_kwargs = event_kwargs or {}

    camera = CameraFactory(**camera_kwargs)
    events = EventFactory.create_batch(
        num_events,
        camera_id=camera.id,
        **event_kwargs,
    )

    return camera, events


def create_detection_batch_for_camera(
    camera_id: str,
    count: int = 5,
    **detection_kwargs: Any,
) -> list[Detection]:
    """Create multiple detections for a specific camera.

    Args:
        camera_id: The camera ID for all detections
        count: Number of detections to create
        **detection_kwargs: Additional kwargs for DetectionFactory

    Returns:
        List of Detection instances

    Example:
        detections = create_detection_batch_for_camera(
            "front_door",
            count=10,
            object_type="person",
            confidence=0.85,
        )
    """
    return DetectionFactory.create_batch(
        count,
        camera_id=camera_id,
        **detection_kwargs,
    )
