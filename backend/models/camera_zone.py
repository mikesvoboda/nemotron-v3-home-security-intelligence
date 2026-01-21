"""CameraZone model for camera zone definitions.

CameraZones define regions of interest on camera views for detection context.
Each zone has normalized coordinates (0-1 range) and can be used to
determine which detections fall within specific areas like driveways,
entry points, or sidewalks.

Note: This model was renamed from Zone to CameraZone in Phase 5.3 of NEM-3113
to distinguish detection polygons from logical Areas in the organizational hierarchy.
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.time_utils import utc_now

from .camera import Base, Camera


class CameraZoneType(str, enum.Enum):
    """Type of camera zone for semantic categorization."""

    ENTRY_POINT = "entry_point"
    DRIVEWAY = "driveway"
    SIDEWALK = "sidewalk"
    YARD = "yard"
    OTHER = "other"


class CameraZoneShape(str, enum.Enum):
    """Shape of the camera zone polygon."""

    RECTANGLE = "rectangle"
    POLYGON = "polygon"


# Aliases for backward compatibility during migration
ZoneType = CameraZoneType
ZoneShape = CameraZoneShape


class CameraZone(Base):
    """CameraZone model representing a defined region on a camera view.

    CameraZones allow users to define regions of interest on camera feeds.
    These zones provide context for detections - for example, a person
    detected in the "driveway" zone vs "sidewalk" zone may have different
    risk implications.

    Coordinates are normalized (0-1 range) relative to image dimensions,
    stored as JSON arrays of [x, y] points.

    Example coordinates for a rectangle:
        [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]]

    Note: This model was renamed from Zone to CameraZone in Phase 5.3 of NEM-3113
    to distinguish detection polygons from logical Areas in the organizational hierarchy.
    """

    __tablename__ = "camera_zones"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    camera_id: Mapped[str] = mapped_column(
        String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    zone_type: Mapped[CameraZoneType] = mapped_column(
        Enum(
            CameraZoneType,
            name="camera_zone_type_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=CameraZoneType.OTHER,
        nullable=False,
    )
    coordinates: Mapped[list] = mapped_column(JSONB, nullable=False)
    shape: Mapped[CameraZoneShape] = mapped_column(
        Enum(
            CameraZoneShape,
            name="camera_zone_shape_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=CameraZoneShape.RECTANGLE,
        nullable=False,
    )
    color: Mapped[str] = mapped_column(String(7), default="#3B82F6", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    camera: Mapped[Camera] = relationship("Camera", back_populates="camera_zones")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_camera_zones_camera_id", "camera_id"),
        Index("idx_camera_zones_enabled", "enabled"),
        Index("idx_camera_zones_camera_enabled", "camera_id", "enabled"),
        # CHECK constraints for business rules
        CheckConstraint("priority >= 0", name="ck_camera_zones_priority_non_negative"),
        CheckConstraint("color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_camera_zones_color_hex"),
    )

    def __repr__(self) -> str:
        return (
            f"<CameraZone(id={self.id!r}, camera_id={self.camera_id!r}, "
            f"name={self.name!r}, zone_type={self.zone_type!r})>"
        )


# Alias for backward compatibility during migration
Zone = CameraZone
