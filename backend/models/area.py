"""Area model for logical zones within a property.

The Area model represents a logical zone within a property (e.g., "Front Yard",
"Garage", "Pool Area"). Areas have a many-to-many relationship with cameras,
allowing a camera to cover multiple areas and an area to be covered by multiple
cameras.

Hierarchy:
    Property (location)
    └── Areas (logical zones)
          ├── "Front Yard" <-> Cameras (many-to-many via camera_areas)
          ├── "Garage"
          └── "Pool Area"

Implements NEM-3129: Phase 5.2 - Create Property and Area models.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .camera import Base

if TYPE_CHECKING:
    from .camera import Camera
    from .property import Property

# Association table for Camera <-> Area many-to-many relationship
camera_areas = Table(
    "camera_areas",
    Base.metadata,
    Column("camera_id", String, ForeignKey("cameras.id", ondelete="CASCADE"), primary_key=True),
    Column("area_id", Integer, ForeignKey("areas.id", ondelete="CASCADE"), primary_key=True),
)


class Area(Base):
    """Logical zone within a property.

    An Area represents a named region within a property that may be covered
    by one or more cameras. Examples include "Front Yard", "Driveway",
    "Pool Area", etc.

    The many-to-many relationship with cameras via the camera_areas table
    allows flexible mapping where:
    - A single camera can cover multiple areas (e.g., a corner camera
      covering both the driveway and front yard)
    - An area can be covered by multiple cameras (e.g., the front yard
      covered by both the porch camera and the garage camera)

    Attributes:
        id: Unique identifier for the area
        property_id: FK to the parent property
        name: Display name for the area (e.g., "Front Yard")
        description: Optional longer description
        color: Hex color code for UI display (default "#76B900" - NVIDIA green)
        created_at: When the area record was created
        property: Related Property record
        cameras: Related Camera records (via camera_areas association)

    Example:
        area = Area(
            property_id=1,
            name="Front Yard",
            description="Main entrance and lawn area",
            color="#10B981",
        )
    """

    __tablename__ = "areas"
    __table_args__ = (
        Index("idx_areas_property_id", "property_id"),
        Index("idx_areas_name", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(7), default="#76B900", nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    property: Mapped[Property] = relationship(
        "Property",
        back_populates="areas",
    )
    cameras: Mapped[list[Camera]] = relationship(
        "Camera",
        secondary=camera_areas,
        back_populates="areas",
    )

    def __repr__(self) -> str:
        return f"<Area(id={self.id}, name={self.name!r}, property_id={self.property_id})>"
