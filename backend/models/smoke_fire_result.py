"""SmokeFireResult model for storing smoke/fire detection results.

This module defines the database model for tracking smoke and fire detections,
including consecutive detection counts for reducing false positives.

Detection Strategy:
- Fire detection: Single high-confidence detection triggers alert (immediate danger)
- Smoke detection: Requires consecutive detections within time window (reduces false positives)
- Consecutive tracking helps differentiate smoke from steam/fog

Priority Levels:
- Fire: Always HIGH priority (immediate danger)
- Smoke: HIGH priority after consecutive threshold met, MEDIUM otherwise
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.time_utils import utc_now

from .camera import Base

if TYPE_CHECKING:
    from backend.services.smoke_fire_loader import SmokeFireDetection


class SmokeFireType(StrEnum):
    """Smoke/fire detection types."""

    SMOKE = "smoke"
    FIRE = "fire"


class SmokeFireResult(Base):
    """SmokeFireResult model for storing smoke/fire detection data.

    Tracks individual smoke/fire detections with metadata for:
    - Consecutive detection counting (reduces false positives)
    - Priority flagging (fire is always high priority)
    - Camera and zone association
    - Bounding box coordinates

    Attributes:
        id: Primary key
        detection_id: Foreign key to detections table
        camera_id: Camera identifier where detection occurred
        zone_id: Optional zone identifier for spatial context
        detection_type: Type of detection (smoke or fire)
        confidence: Detection confidence score (0.0-1.0)
        consecutive_count: Number of consecutive detections
        is_high_priority: Whether this is a high-priority detection
        bbox_x1, bbox_y1, bbox_x2, bbox_y2: Bounding box coordinates
        detection_timestamp: When the detection occurred
        created_at: When this record was created
    """

    __tablename__ = "smoke_fire_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detection_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("detections.id", ondelete="CASCADE"), nullable=False
    )
    camera_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zone_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detection_type: Mapped[SmokeFireType] = mapped_column(
        Enum(SmokeFireType, name="smoke_fire_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    consecutive_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    bbox_x1: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y1: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_x2: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y2: Mapped[float | None] = mapped_column(Float, nullable=True)
    detection_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=True
    )

    # Relationships
    detection: Mapped[Any] = relationship("Detection", backref="smoke_fire_results")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_smoke_fire_results_detection_id", "detection_id"),
        Index("idx_smoke_fire_results_camera_id", "camera_id"),
        Index("idx_smoke_fire_results_detection_type", "detection_type"),
        Index("idx_smoke_fire_results_created_at", "created_at"),
        Index("idx_smoke_fire_results_camera_type", "camera_id", "detection_type"),
        # CHECK constraints
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_smoke_fire_results_confidence_range",
        ),
        CheckConstraint(
            "consecutive_count >= 1",
            name="ck_smoke_fire_results_consecutive_positive",
        ),
    )

    def __init__(self, **kwargs: Any) -> None:
        """Initialize SmokeFireResult with computed is_high_priority.

        The is_high_priority field is automatically computed based on:
        - Fire detection: Always high priority
        - Smoke detection: High priority only with consecutive_count >= 2

        Args:
            **kwargs: Field values for the SmokeFireResult
        """
        # Set defaults
        kwargs.setdefault("consecutive_count", 1)

        # Call parent init first
        super().__init__(**kwargs)

    @property
    def is_high_priority(self) -> bool:
        """Compute whether this detection is high priority.

        Fire is always high priority.
        Smoke is high priority only with consecutive_count >= 2.
        Can be explicitly overridden via setter.

        Returns:
            True if high priority, False otherwise
        """
        # Check for explicit override first
        if hasattr(self, "_is_high_priority_override"):
            return self._is_high_priority_override

        if self.detection_type == SmokeFireType.FIRE:
            return True
        # Smoke with consecutive detections is high priority
        return self.consecutive_count >= 2

    @is_high_priority.setter
    def is_high_priority(self, value: bool) -> None:
        """Allow setting is_high_priority (used in tests).

        This setter allows explicit override of the computed property
        for testing purposes. In normal operation, is_high_priority
        is computed from detection_type and consecutive_count.
        """
        # Store in a private attribute for override
        self._is_high_priority_override = value

    def __repr__(self) -> str:
        return (
            f"<SmokeFireResult(id={self.id!r}, detection_type={self.detection_type.value!r}, "
            f"confidence={self.confidence:.2f}, consecutive_count={self.consecutive_count})>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the smoke/fire result
        """
        return {
            "id": self.id,
            "detection_id": self.detection_id,
            "camera_id": self.camera_id,
            "zone_id": self.zone_id,
            "detection_type": self.detection_type.value if self.detection_type else None,
            "confidence": self.confidence,
            "consecutive_count": self.consecutive_count,
            "is_high_priority": self.is_high_priority,
            "bbox": {
                "x1": self.bbox_x1,
                "y1": self.bbox_y1,
                "x2": self.bbox_x2,
                "y2": self.bbox_y2,
            }
            if any([self.bbox_x1, self.bbox_y1, self.bbox_x2, self.bbox_y2])
            else None,
            "detection_timestamp": (
                self.detection_timestamp.isoformat() if self.detection_timestamp else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_detection(
        cls,
        detection: SmokeFireDetection,
        detection_id: int,
        camera_id: str | None = None,
        zone_id: int | None = None,
        consecutive_count: int = 1,
        detection_timestamp: datetime | None = None,
    ) -> SmokeFireResult:
        """Create a SmokeFireResult from a SmokeFireDetection dataclass.

        Args:
            detection: SmokeFireDetection dataclass instance
            detection_id: Database detection ID to link to
            camera_id: Camera identifier
            zone_id: Optional zone identifier
            consecutive_count: Number of consecutive detections
            detection_timestamp: When the detection occurred

        Returns:
            New SmokeFireResult instance
        """
        # Extract bbox coordinates
        bbox = detection.bbox
        bbox_x1 = float(bbox[0]) if bbox else None
        bbox_y1 = float(bbox[1]) if bbox else None
        bbox_x2 = float(bbox[2]) if bbox else None
        bbox_y2 = float(bbox[3]) if bbox else None

        # Map detection_type string to enum
        detection_type_enum = SmokeFireType(detection.detection_type)

        return cls(
            detection_id=detection_id,
            camera_id=camera_id,
            zone_id=zone_id,
            detection_type=detection_type_enum,
            confidence=detection.confidence,
            consecutive_count=consecutive_count,
            bbox_x1=bbox_x1,
            bbox_y1=bbox_y1,
            bbox_x2=bbox_x2,
            bbox_y2=bbox_y2,
            detection_timestamp=detection_timestamp or utc_now(),
        )
