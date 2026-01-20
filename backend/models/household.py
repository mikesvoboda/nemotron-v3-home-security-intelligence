"""Household models for known persons and vehicles.

These models enable tracking of known household members and vehicles to reduce
false positives in security monitoring. If Nemotron knows "this is Mike's car"
or "this is a family member", it can score lower risk.

Models:
- HouseholdMember: Known persons who should not trigger high-risk alerts
- PersonEmbedding: Re-ID embeddings for matching persons to household members
- RegisteredVehicle: Known vehicles that should not trigger alerts

Implements NEM-3016: Create HouseholdMember and RegisteredVehicle database models.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Index, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .camera import Base


class MemberRole(str, enum.Enum):
    """Role of a household member for access categorization."""

    RESIDENT = "resident"
    FAMILY = "family"
    SERVICE_WORKER = "service_worker"
    FREQUENT_VISITOR = "frequent_visitor"


class TrustLevel(str, enum.Enum):
    """Trust level for household members determining alert behavior.

    - FULL: Never trigger alerts for this person
    - PARTIAL: Reduced alert severity, still monitored
    - MONITOR: Log activity but don't suppress alerts
    """

    FULL = "full"
    PARTIAL = "partial"
    MONITOR = "monitor"


class VehicleType(str, enum.Enum):
    """Type of vehicle for categorization."""

    CAR = "car"
    TRUCK = "truck"
    MOTORCYCLE = "motorcycle"
    SUV = "suv"
    VAN = "van"
    OTHER = "other"


class HouseholdMember(Base):
    """Known persons who should not trigger high-risk alerts.

    Household members represent people who are expected to be seen by cameras
    and should not trigger high-risk security events. The trust_level determines
    how alerts are handled when this person is detected.

    The typical_schedule field allows defining expected presence times, which
    helps with anomaly detection (e.g., detecting the gardener outside normal hours).

    Attributes:
        id: Unique identifier for the household member
        name: Display name for the person
        role: Categorization of the person's relationship to the household
        trusted_level: Level of trust determining alert suppression
        typical_schedule: JSON object defining expected presence schedule
        notes: Free-form notes about the person
        created_at: When the member record was created
        updated_at: When the member record was last updated
        embeddings: Related PersonEmbedding records for person re-identification
    """

    __tablename__ = "household_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[MemberRole] = mapped_column(
        Enum(MemberRole, name="member_role_enum"),
        nullable=False,
    )
    trusted_level: Mapped[TrustLevel] = mapped_column(
        Enum(TrustLevel, name="trust_level_enum"),
        nullable=False,
    )
    typical_schedule: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Relationships
    embeddings: Mapped[list[PersonEmbedding]] = relationship(
        "PersonEmbedding",
        back_populates="member",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # Index for querying by role
        Index("idx_household_members_role", "role"),
        # Index for querying by trust level
        Index("idx_household_members_trusted_level", "trusted_level"),
        # Composite index for role + trust level queries
        Index("idx_household_members_role_trust", "role", "trusted_level"),
    )

    def __repr__(self) -> str:
        return (
            f"<HouseholdMember(id={self.id}, name={self.name!r}, "
            f"role={self.role.value!r}, trusted_level={self.trusted_level.value!r})>"
        )


class PersonEmbedding(Base):
    """Re-ID embeddings for matching persons to household members.

    Stores person re-identification embeddings that can be used to match
    detected persons against known household members. Multiple embeddings
    can be stored per member to improve recognition accuracy across different
    angles, lighting conditions, and clothing.

    The embedding is stored as a serialized numpy array in LargeBinary format.
    The confidence field indicates how reliable this embedding is for matching.

    Attributes:
        id: Unique identifier for the embedding
        member_id: Foreign key to the associated household member
        embedding: Serialized numpy array containing the re-ID embedding
        source_event_id: Optional reference to the event where this embedding was captured
        confidence: Reliability score for this embedding (0-1)
        created_at: When the embedding was created
        member: Relationship to the parent HouseholdMember
    """

    __tablename__ = "person_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("household_members.id", ondelete="CASCADE"),
        nullable=False,
    )
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    source_event_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    member: Mapped[HouseholdMember] = relationship(
        "HouseholdMember",
        back_populates="embeddings",
    )

    __table_args__ = (
        # Index for querying embeddings by member
        Index("idx_person_embeddings_member_id", "member_id"),
        # Index for looking up embeddings by source event
        Index("idx_person_embeddings_source_event_id", "source_event_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<PersonEmbedding(id={self.id}, member_id={self.member_id}, "
            f"confidence={self.confidence})>"
        )


class RegisteredVehicle(Base):
    """Known vehicles that should not trigger alerts.

    Registered vehicles represent cars, trucks, and other vehicles that
    belong to household members or are expected to be seen regularly.
    Detection of a registered vehicle can suppress or reduce alert severity.

    The reid_embedding field stores an optional vehicle re-identification
    embedding that can be used for visual matching beyond license plate.

    Attributes:
        id: Unique identifier for the vehicle
        description: Human-readable description (e.g., "Silver Tesla Model 3")
        license_plate: Optional license plate number
        vehicle_type: Type/category of the vehicle
        color: Optional color description
        owner_id: Optional foreign key to the vehicle owner (HouseholdMember)
        trusted: Whether this vehicle should suppress alerts
        reid_embedding: Optional serialized embedding for visual matching
        created_at: When the vehicle record was created
        owner: Relationship to the optional owner HouseholdMember
    """

    __tablename__ = "registered_vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    license_plate: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vehicle_type: Mapped[VehicleType] = mapped_column(
        Enum(VehicleType, name="vehicle_type_enum"),
        nullable=False,
    )
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    owner_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("household_members.id", ondelete="SET NULL"),
        nullable=True,
    )
    trusted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reid_embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    owner: Mapped[HouseholdMember | None] = relationship("HouseholdMember")

    __table_args__ = (
        # Index for querying by owner
        Index("idx_registered_vehicles_owner_id", "owner_id"),
        # Index for license plate lookups
        Index("idx_registered_vehicles_license_plate", "license_plate"),
        # Index for trusted vehicles (common query filter)
        Index("idx_registered_vehicles_trusted", "trusted"),
        # Index for vehicle type filtering
        Index("idx_registered_vehicles_vehicle_type", "vehicle_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<RegisteredVehicle(id={self.id}, description={self.description!r}, "
            f"vehicle_type={self.vehicle_type.value!r}, trusted={self.trusted})>"
        )
