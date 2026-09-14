"""PackageEvent model for tracking package delivery and removal events.

This module provides SQLAlchemy models for package event tracking as part of
the package detection feature (NEM-5293). It tracks when packages are delivered,
removed, and whether removals are suspicious (potential theft).

The model supports:
- Package delivery tracking with timestamps
- Removal detection and timing
- Theft suspicion flagging based on household member presence
- Zone and camera associations
- Duration calculation for package dwell time

Usage:
    from backend.models.package_event import PackageEvent, PackageEventType

    # Create a delivery event
    event = PackageEvent(
        camera_id="front_door",
        event_type=PackageEventType.DELIVERED,
        detected_at=datetime.now(UTC),
        confidence=0.85,
    )

    # Check if theft is suspected
    if event.is_theft_suspected:
        send_alert()
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.time_utils import utc_now

from .camera import Base

if TYPE_CHECKING:
    from .analytics_zone import PolygonZone
    from .camera import Camera


class PackageEventType(StrEnum):
    """Enumeration of package event types.

    Attributes:
        DELIVERED: Package was detected as delivered to the location
        REMOVED: Package was removed from the location
        THEFT_SUSPECTED: Package was removed without household member present
        RETRIEVED_BY_OWNER: Package was retrieved by a recognized household member
    """

    DELIVERED = "delivered"
    REMOVED = "removed"
    THEFT_SUSPECTED = "theft_suspected"
    RETRIEVED_BY_OWNER = "retrieved_by_owner"


class PackageEvent(Base):
    """Package event model for tracking package delivery and removal events.

    This model tracks the lifecycle of packages detected by the security system,
    from delivery through removal. It includes confidence scores from detection,
    zone associations, and flags for suspicious activity.

    Attributes:
        id: Primary key for the package event
        camera_id: Foreign key to the camera that detected the package
        zone_id: Optional foreign key to the zone where package was detected
        event_type: Type of event (delivered, removed, theft_suspected, retrieved_by_owner)
        detected_at: Timestamp when the event was detected
        delivery_timestamp: Timestamp when the package was first delivered
        removal_timestamp: Timestamp when the package was removed
        confidence: Detection confidence score (0.0-1.0)
        bbox: Bounding box coordinates as JSONB {x1, y1, x2, y2}
        package_class: YOLO-World detected class name (e.g., "Amazon box")
        household_member_present: Whether a household member was present during removal
        delivery_person_present: Whether a delivery person was present
        notes: Optional notes about the event
        created_at: Timestamp when the record was created
        deleted_at: Soft delete timestamp

    Relationships:
        camera: The Camera that detected this package event
        zone: The PolygonZone where the package was detected (optional)

    Example:
        # Query for suspicious removals in the last 24 hours
        suspicious_events = session.query(PackageEvent).filter(
            PackageEvent.event_type == PackageEventType.THEFT_SUSPECTED,
            PackageEvent.detected_at >= datetime.now(UTC) - timedelta(days=1),
            PackageEvent.deleted_at.is_(None),
        ).all()
    """

    __tablename__ = "package_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(
        String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    zone_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("polygon_zones.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivery_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    removal_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    package_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    household_member_present: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    delivery_person_present: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Relationships
    camera: Mapped[Camera] = relationship("Camera")
    zone: Mapped[PolygonZone | None] = relationship("PolygonZone")

    # Table arguments (indexes for common queries)
    __table_args__ = (
        Index("idx_package_events_camera_id", "camera_id"),
        Index("idx_package_events_detected_at", "detected_at"),
        Index("idx_package_events_event_type", "event_type"),
        Index("idx_package_events_zone_id", "zone_id"),
    )

    @property
    def duration(self) -> timedelta | None:
        """Calculate the duration between delivery and removal.

        Returns the time difference between delivery_timestamp and removal_timestamp.
        Returns None if either timestamp is not set.

        Returns:
            timedelta representing the duration, or None if not applicable
        """
        if self.delivery_timestamp is None or self.removal_timestamp is None:
            return None
        return self.removal_timestamp - self.delivery_timestamp

    @property
    def is_theft_suspected(self) -> bool:
        """Check if this event indicates suspected theft.

        Returns:
            True if event_type is THEFT_SUSPECTED, False otherwise
        """
        return self.event_type == PackageEventType.THEFT_SUSPECTED

    @property
    def is_deleted(self) -> bool:
        """Check if this event is soft-deleted.

        Returns:
            True if deleted_at is set, False otherwise
        """
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Soft delete this event by setting deleted_at timestamp."""
        self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restore a soft-deleted event by clearing deleted_at timestamp."""
        self.deleted_at = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event to a dictionary for API responses.

        Returns:
            Dictionary representation of the event with all fields
        """
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "zone_id": self.zone_id,
            "event_type": self.event_type,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "delivery_timestamp": (
                self.delivery_timestamp.isoformat() if self.delivery_timestamp else None
            ),
            "removal_timestamp": (
                self.removal_timestamp.isoformat() if self.removal_timestamp else None
            ),
            "confidence": self.confidence,
            "bbox": self.bbox,
            "package_class": self.package_class,
            "household_member_present": self.household_member_present,
            "delivery_person_present": self.delivery_person_present,
            "notes": self.notes,
            "duration_seconds": self.duration.total_seconds() if self.duration else None,
            "is_theft_suspected": self.is_theft_suspected,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"<PackageEvent(id={self.id}, camera_id={self.camera_id!r}, "
            f"event_type={self.event_type!r})>"
        )
