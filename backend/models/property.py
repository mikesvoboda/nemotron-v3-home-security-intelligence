"""Property model for multi-location household management.

The Property model represents a physical location owned by a household,
such as a main house, beach house, or vacation home. Properties contain
areas (logical zones like "Front Yard") and cameras.

Hierarchy:
    Household (org unit, e.g., "Svoboda Family")
    └── Properties (locations)
          ├── "Main House"
          │     ├── Areas ("Front Yard", "Garage")
          │     └── Cameras
          └── "Beach House"
                ├── Areas
                └── Cameras

Implements NEM-3129: Phase 5.2 - Create Property and Area models.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .camera import Base

if TYPE_CHECKING:
    from .area import Area
    from .camera import Camera
    from .household_org import Household


class Property(Base):
    """Physical location owned by a household.

    A Property represents a physical address/location where security monitoring
    takes place. Each property can have multiple areas (logical zones) and
    cameras assigned to it.

    Attributes:
        id: Unique identifier for the property
        household_id: FK to the owning household
        name: Display name for the property (e.g., "Main House", "Beach House")
        address: Optional street address
        timezone: Timezone for the property (default "UTC")
        created_at: When the property record was created
        household: Related Household record
        areas: Related Area records
        cameras: Related Camera records

    Example:
        property = Property(
            household_id=1,
            name="Main House",
            address="123 Main St, City, ST 12345",
            timezone="America/New_York",
        )
    """

    __tablename__ = "properties"
    __table_args__ = (
        Index("idx_properties_household_id", "household_id"),
        Index("idx_properties_name", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    household: Mapped[Household] = relationship(
        "Household",
        back_populates="properties",
    )
    areas: Mapped[list[Area]] = relationship(
        "Area",
        back_populates="property",
        cascade="all, delete-orphan",
    )
    cameras: Mapped[list[Camera]] = relationship(
        "Camera",
        back_populates="property_ref",
    )

    def __repr__(self) -> str:
        return f"<Property(id={self.id}, name={self.name!r}, household_id={self.household_id})>"
