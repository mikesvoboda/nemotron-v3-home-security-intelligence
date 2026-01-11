"""Entity model for re-identification tracking.

Entities represent unique tracked objects (people, vehicles, etc.) across
multiple detections. This enables re-identification by storing embedding
vectors and tracking appearance patterns over time.

Related Linear epic: NEM-1880
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum, auto
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.time_utils import utc_now

from .camera import Base


class EntityType(StrEnum):
    """Type of tracked entity for re-identification."""

    PERSON = auto()
    VEHICLE = auto()
    ANIMAL = auto()
    UNKNOWN = auto()


class Entity(Base):
    """Entity model representing a unique tracked object across detections.

    Entities enable re-identification by:
    - Storing embedding vectors for similarity matching
    - Tracking first/last seen timestamps and appearance count
    - Associating multiple detections with the same real-world entity
    - Storing metadata for entity attributes (clothing, vehicle type, etc.)

    Re-identification workflow:
    1. New detection generates embedding vector
    2. System searches for existing entities with similar embeddings
    3. If match found (similarity > threshold), link detection to entity
    4. If no match, create new entity with this detection
    5. Update entity's last_seen_at and appearance_count

    The embedding_vector stores a float array suitable for cosine similarity
    or Euclidean distance calculations. Vector dimension depends on the
    embedding model used (typically 128-512 dimensions).

    Example embedding models:
    - Person re-ID: OSNet (512d), FastReID (2048d), torchreid models
    - Vehicle re-ID: VeRi-Wild embeddings, vehicle make/model classifiers
    """

    __tablename__ = "entities"

    # Primary key - UUID for distributed ID generation
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Entity type categorization
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType, name="entity_type_enum"),
        nullable=False,
        default=EntityType.UNKNOWN,
    )

    # Display name for the entity (auto-generated or user-assigned)
    # e.g., "Person #42", "Blue Honda Civic", "Regular Visitor"
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Tracking timestamps
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Count of times this entity has been detected
    appearance_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Embedding vector for re-identification similarity matching
    # Stored as float array - dimension depends on model (typically 128-512)
    # Use pgvector extension for efficient similarity search in production
    embedding_vector: Mapped[list[float] | None] = mapped_column(
        ARRAY(Float),
        nullable=True,
    )

    # Embedding model identifier (for vector compatibility)
    # e.g., "osnet_x1_0", "fastreid_msmt17", "clip_vit_b32"
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Flexible metadata for entity attributes
    # Examples:
    # - Person: {"clothing_color": "blue", "height_estimate": "tall", "accessory": "backpack"}
    # - Vehicle: {"make": "Honda", "model": "Civic", "color": "blue", "license_plate": "ABC123"}
    # - Animal: {"species": "dog", "breed": "golden_retriever", "color": "golden"}
    # Note: Named entity_metadata to avoid collision with SQLAlchemy's reserved 'metadata'
    entity_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)

    # Optional notes for user annotations
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Soft delete support
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Timestamps for auditing
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Indexes for common queries
    __table_args__ = (
        # Type-based queries (e.g., "show all person entities")
        Index("idx_entities_entity_type", "entity_type"),
        # Time-range queries for entity activity
        Index("idx_entities_first_seen_at", "first_seen_at"),
        Index("idx_entities_last_seen_at", "last_seen_at"),
        # Soft delete filtering
        Index("idx_entities_deleted_at", "deleted_at"),
        # Composite index for active entities by type
        Index("idx_entities_type_last_seen", "entity_type", "last_seen_at"),
        # Partial index for active (non-deleted) entities
        Index(
            "idx_entities_active",
            "id",
            postgresql_where="deleted_at IS NULL",
        ),
        # GIN index for JSONB metadata queries
        Index(
            "idx_entities_metadata_gin",
            "metadata",
            postgresql_using="gin",
            postgresql_ops={"metadata": "jsonb_path_ops"},
        ),
        # CHECK constraints for business rules
        CheckConstraint(
            "appearance_count >= 0",
            name="ck_entities_appearance_count_non_negative",
        ),
        CheckConstraint(
            "first_seen_at <= last_seen_at",
            name="ck_entities_seen_timestamps_order",
        ),
    )

    @property
    def is_deleted(self) -> bool:
        """Check if this entity is soft-deleted.

        Returns:
            True if deleted_at is set, False otherwise
        """
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Soft delete this entity by setting deleted_at timestamp."""
        self.deleted_at = utc_now()

    def restore(self) -> None:
        """Restore a soft-deleted entity by clearing deleted_at timestamp."""
        self.deleted_at = None

    def update_seen(self) -> None:
        """Update the entity's last_seen_at timestamp and increment appearance count.

        Call this method when a new detection is associated with this entity.
        """
        self.last_seen_at = utc_now()
        self.appearance_count += 1

    def __repr__(self) -> str:
        return (
            f"<Entity(id={self.id!r}, entity_type={self.entity_type.value!r}, "
            f"appearance_count={self.appearance_count}, name={self.name!r})>"
        )
