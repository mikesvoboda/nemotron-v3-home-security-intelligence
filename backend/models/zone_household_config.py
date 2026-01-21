"""ZoneHouseholdConfig model for zone-household linkage.

This model enables linking camera zones to household members and vehicles,
enabling zone-based access control and trust management. Each zone can have:
- An owner (household member)
- A list of allowed household members
- A list of allowed vehicles
- Access schedules for time-based permissions

Implements NEM-3190: Backend Zone-Household Linkage API.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.models.camera import Base

if TYPE_CHECKING:
    from backend.models.camera_zone import CameraZone
    from backend.models.household import HouseholdMember


class ZoneHouseholdConfig(Base):
    """Configuration linking a camera zone to household members and vehicles.

    This model enables zone-based access control by associating zones with:
    - An owner who has full trust in the zone
    - Allowed members who have partial/configurable trust
    - Allowed vehicles that are trusted in the zone
    - Time-based access schedules

    Example access_schedules format:
    [
        {
            "member_ids": [1, 2],
            "cron_expression": "0 9-17 * * 1-5",  # Weekdays 9am-5pm
            "description": "Service workers during business hours"
        },
        {
            "member_ids": [3],
            "cron_expression": "0 18-22 * * *",  # Every day 6pm-10pm
            "description": "Evening visitor access"
        }
    ]

    Attributes:
        id: Primary key (integer, auto-increment)
        zone_id: Foreign key to camera_zones (string, unique per config)
        owner_id: Optional foreign key to the zone owner (household member)
        allowed_member_ids: Array of household member IDs with zone access
        allowed_vehicle_ids: Array of registered vehicle IDs with zone access
        access_schedules: JSON array of schedule configurations
        created_at: Timestamp when config was created
        updated_at: Timestamp when config was last updated
    """

    __tablename__ = "zone_household_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    zone_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("camera_zones.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL"),
        nullable=True,
    )
    allowed_member_ids: Mapped[list[int]] = mapped_column(
        ARRAY(Integer),  # Integer array
        default=list,
        nullable=False,
    )
    allowed_vehicle_ids: Mapped[list[int]] = mapped_column(
        ARRAY(Integer),  # Integer array
        default=list,
        nullable=False,
    )
    access_schedules: Mapped[list[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    zone: Mapped[CameraZone] = relationship(
        "CameraZone",
        back_populates="household_config",
        lazy="joined",
    )
    owner: Mapped[HouseholdMember | None] = relationship(
        "HouseholdMember",
        lazy="joined",
    )

    __table_args__ = (
        # Index for querying by owner
        Index("idx_zone_household_configs_owner_id", "owner_id"),
        # GIN index for array containment queries
        Index(
            "idx_zone_household_configs_allowed_member_ids",
            "allowed_member_ids",
            postgresql_using="gin",
        ),
        Index(
            "idx_zone_household_configs_allowed_vehicle_ids",
            "allowed_vehicle_ids",
            postgresql_using="gin",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ZoneHouseholdConfig(id={self.id}, zone_id={self.zone_id!r}, "
            f"owner_id={self.owner_id})>"
        )
