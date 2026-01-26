"""Analytics zone models for line crossing and polygon intrusion detection.

These models support the supervision-based analytics pipeline with:
- LineZone: Virtual tripwire for counting and detecting line crossings
- PolygonZone: Region-based intrusion detection and object counting

The zones are camera-specific and can be configured per camera to define
areas of interest for automated analytics.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.time_utils import utc_now

from .camera import Base

if TYPE_CHECKING:
    from .camera import Camera
    from .dwell_time import DwellTimeRecord


class LineZone(Base):
    """Line zone for virtual tripwire detection.

    A LineZone defines a virtual line on a camera view that can detect
    and count objects crossing from one side to the other. The line is
    defined by start and end coordinates (in pixels).

    Attributes:
        id: Unique identifier for the line zone
        camera_id: Foreign key to the associated camera
        name: Human-readable name for the line zone
        start_x: X coordinate of the line start point (pixels)
        start_y: Y coordinate of the line start point (pixels)
        end_x: X coordinate of the line end point (pixels)
        end_y: Y coordinate of the line end point (pixels)
        in_count: Cumulative count of objects crossing in the "in" direction
        out_count: Cumulative count of objects crossing in the "out" direction
        alert_on_cross: Whether to generate alerts when objects cross the line
        target_classes: List of object classes to track (e.g., ["person", "car"])
        created_at: Timestamp when the line zone was created

    Example:
        A driveway entrance line at y=400 spanning x=100 to x=500:
        LineZone(
            camera_id="front_door",
            name="Driveway Entrance",
            start_x=100, start_y=400,
            end_x=500, end_y=400,
            target_classes=["person", "car"]
        )
    """

    __tablename__ = "line_zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(
        String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_x: Mapped[int] = mapped_column(Integer, nullable=False)
    start_y: Mapped[int] = mapped_column(Integer, nullable=False)
    end_x: Mapped[int] = mapped_column(Integer, nullable=False)
    end_y: Mapped[int] = mapped_column(Integer, nullable=False)
    in_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    out_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    alert_on_cross: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    target_classes: Mapped[list] = mapped_column(JSONB, default=["person"], nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationship
    camera: Mapped[Camera] = relationship("Camera", back_populates="line_zones")

    __table_args__ = (
        Index("idx_line_zones_camera", "camera_id"),
        # Ensure coordinates are non-negative (pixel coordinates)
        CheckConstraint("start_x >= 0", name="ck_line_zones_start_x_non_negative"),
        CheckConstraint("start_y >= 0", name="ck_line_zones_start_y_non_negative"),
        CheckConstraint("end_x >= 0", name="ck_line_zones_end_x_non_negative"),
        CheckConstraint("end_y >= 0", name="ck_line_zones_end_y_non_negative"),
        # Ensure counts are non-negative
        CheckConstraint("in_count >= 0", name="ck_line_zones_in_count_non_negative"),
        CheckConstraint("out_count >= 0", name="ck_line_zones_out_count_non_negative"),
    )

    def __repr__(self) -> str:
        return (
            f"<LineZone(id={self.id!r}, camera_id={self.camera_id!r}, "
            f"name={self.name!r}, in_count={self.in_count}, out_count={self.out_count})>"
        )


class PolygonZone(Base):
    """Polygon zone for intrusion detection and object counting.

    A PolygonZone defines a polygonal region on a camera view that can
    detect objects entering, exiting, or dwelling within the area. The
    polygon is defined as a list of [x, y] coordinate pairs (in pixels).

    Attributes:
        id: Unique identifier for the polygon zone
        camera_id: Foreign key to the associated camera
        name: Human-readable name for the polygon zone
        polygon: List of [x, y] coordinate pairs defining the polygon vertices
        zone_type: Type of zone (monitored, excluded, restricted)
        alert_threshold: Minimum object count to trigger an alert (0 = any entry)
        target_classes: List of object classes to track (e.g., ["person"])
        is_active: Whether the zone is currently being monitored
        color: Hex color code for visualization (e.g., "#FF0000")
        current_count: Current count of objects within the zone
        created_at: Timestamp when the polygon zone was created

    Example:
        A restricted backyard area:
        PolygonZone(
            camera_id="backyard",
            name="Pool Area",
            polygon=[[100, 200], [400, 200], [400, 500], [100, 500]],
            zone_type="restricted",
            alert_threshold=1,
            target_classes=["person"]
        )
    """

    __tablename__ = "polygon_zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(
        String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    polygon: Mapped[list] = mapped_column(JSONB, nullable=False)  # [[x1,y1], [x2,y2], ...]
    zone_type: Mapped[str] = mapped_column(String(50), default="monitored", nullable=False)
    alert_threshold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_classes: Mapped[list] = mapped_column(JSONB, default=["person"], nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#FF0000", nullable=False)
    current_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    camera: Mapped[Camera] = relationship("Camera", back_populates="polygon_zones")
    dwell_time_records: Mapped[list[DwellTimeRecord]] = relationship(
        "DwellTimeRecord", back_populates="zone", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_polygon_zones_camera", "camera_id"),
        Index("idx_polygon_zones_type", "zone_type"),
        Index("idx_polygon_zones_active", "is_active"),
        # Ensure threshold and count are non-negative
        CheckConstraint("alert_threshold >= 0", name="ck_polygon_zones_threshold_non_negative"),
        CheckConstraint("current_count >= 0", name="ck_polygon_zones_count_non_negative"),
        # Validate hex color format
        CheckConstraint("color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_polygon_zones_color_hex"),
        # Validate zone_type enum-like values
        CheckConstraint(
            "zone_type IN ('monitored', 'excluded', 'restricted')",
            name="ck_polygon_zones_type_valid",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PolygonZone(id={self.id!r}, camera_id={self.camera_id!r}, "
            f"name={self.name!r}, zone_type={self.zone_type!r}, current_count={self.current_count})>"
        )
