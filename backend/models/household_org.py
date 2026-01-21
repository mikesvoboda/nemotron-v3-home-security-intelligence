"""Household organization model for multi-property household management.

The Household model serves as the top-level organizational unit in the system,
grouping together household members, registered vehicles, and properties (locations).

This enables families with multiple homes (e.g., main house + beach house) to manage
all their security monitoring under a single household identity.

Hierarchy:
    Household (org unit, e.g., "Svoboda Family")
    ├── Members (people)
    ├── Vehicles (cars)
    └── Properties (locations)
          ├── "Main House"
          └── "Beach House"

Implements NEM-3128: Phase 5.1 - Create Household organization model.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .camera import Base

if TYPE_CHECKING:
    from .household import HouseholdMember, RegisteredVehicle
    from .property import Property


class Household(Base):
    """Top-level organizational unit representing a household.

    A Household is the root entity that groups together all members, vehicles,
    and properties for a family or organization. This enables multi-property
    management where a single household can have monitoring across multiple
    physical locations.

    Attributes:
        id: Unique identifier for the household
        name: Display name for the household (e.g., "Svoboda Family")
        created_at: When the household record was created
        members: Related HouseholdMember records
        vehicles: Related RegisteredVehicle records

    Example:
        household = Household(name="Svoboda Family")
        # Members and vehicles can be linked via household_id foreign key
        # Properties can be linked to represent multiple locations
    """

    __tablename__ = "households"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    members: Mapped[list[HouseholdMember]] = relationship(
        "HouseholdMember",
        back_populates="household",
    )
    vehicles: Mapped[list[RegisteredVehicle]] = relationship(
        "RegisteredVehicle",
        back_populates="household",
    )
    properties: Mapped[list[Property]] = relationship(
        "Property",
        back_populates="household",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Household(id={self.id}, name={self.name!r})>"
