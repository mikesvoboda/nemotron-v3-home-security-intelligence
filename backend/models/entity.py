"""Entity model for person/object re-identification tracking.

This module provides the Entity model for tracking unique individuals
and objects across multiple cameras using embedding vectors for
re-identification.

IMPORTANT: No FK constraint on primary_detection_id
============================================
The primary_detection_id column does NOT have a foreign key constraint.
This is intentional because the detections table is partitioned by detected_at
with a composite primary key (id, detected_at). PostgreSQL does not support FK
constraints that reference only part of a composite key on partitioned tables.

Referential integrity is enforced at the application level via:
- validate_primary_detection_async() for async contexts (with Session)
- The relationship is optional and used primarily for display purposes

See docs/decisions/entity-detection-referential-integrity.md
for the full architectural decision record.

Related to NEM-1880 (Re-identification feature), NEM-2210 (Entity model), NEM-2431, NEM-2670.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base
from .enums import EntityType, TrustStatus

if TYPE_CHECKING:
    from .detection import Detection


class Entity(Base):
    """Entity model for tracking unique persons/objects across cameras.

    Entities represent unique individuals or objects that can be tracked
    across multiple cameras over time using re-identification techniques.
    Each entity stores an embedding vector for matching and maintains
    statistics about when and how often they have been seen.

    The embedding_vector is stored as JSONB to support flexible storage
    of feature vectors from various models (CLIP, ReID-specific models, etc.).
    For high-performance similarity search, consider using pgvector extension
    when available.

    Attributes:
        id: Unique entity identifier (UUID)
        entity_type: Type of entity (person, vehicle, animal, package, other)
        trust_status: Trust classification (trusted, untrusted, unknown)
        embedding_vector: Feature vector for re-identification (JSONB array)
        first_seen_at: Timestamp of first detection
        last_seen_at: Timestamp of most recent detection
        detection_count: Total number of detections linked to this entity
        entity_metadata: Flexible JSONB field for additional attributes
        primary_detection_id: Optional reference to the primary/best detection
    """

    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EntityType.PERSON.value
    )
    # Trust status for alert handling: trusted entities may skip/reduce alerts,
    # untrusted entities may increase alert severity, unknown entities process normally.
    trust_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TrustStatus.UNKNOWN.value
    )
    # Embedding vector stored as JSONB array for flexibility.
    # Contains keys: vector (list of floats), model (str), dimension (int).
    embedding_vector: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    detection_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Flexible metadata for attributes like clothing color, vehicle make/model, etc.
    # Named entity_metadata to avoid conflict with SQLAlchemy's reserved 'metadata' attribute
    entity_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Optional reference to the primary/best detection for this entity.
    # NOTE: No ForeignKey constraint because detections is a partitioned table
    # with composite PK (id, detected_at). PostgreSQL doesn't support FK references
    # to partial keys on partitioned tables. See module docstring for details.
    primary_detection_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,  # Index for efficient joins even without FK
    )

    # Relationships - uses primaryjoin without FK constraint for flexibility
    # with partitioned tables. The relationship still works for eager loading
    # but doesn't enforce referential integrity at the database level.
    primary_detection: Mapped[Detection | None] = relationship(
        "Detection",
        primaryjoin="Entity.primary_detection_id == Detection.id",
        foreign_keys=[primary_detection_id],
        lazy="selectin",
        viewonly=True,  # No cascade since there's no FK
    )

    # Indexes for common query patterns
    __table_args__ = (
        # Index on entity_type for filtering by type
        Index("idx_entities_entity_type", "entity_type"),
        # Index on trust_status for filtering by trust level
        Index("idx_entities_trust_status", "trust_status"),
        # Index on first_seen_at for time-range queries
        Index("idx_entities_first_seen_at", "first_seen_at"),
        # Index on last_seen_at for recent activity queries
        Index("idx_entities_last_seen_at", "last_seen_at"),
        # Composite index for type + time filtering
        Index("idx_entities_type_last_seen", "entity_type", "last_seen_at"),
        # GIN index on entity_metadata for flexible attribute queries
        Index(
            "ix_entities_entity_metadata_gin",
            "entity_metadata",
            postgresql_using="gin",
            postgresql_ops={"entity_metadata": "jsonb_path_ops"},
        ),
        # CHECK constraint for valid entity types
        CheckConstraint(
            "entity_type IN ('person', 'vehicle', 'animal', 'package', 'other')",
            name="ck_entities_entity_type",
        ),
        # CHECK constraint for valid trust status values
        CheckConstraint(
            "trust_status IN ('trusted', 'untrusted', 'unknown')",
            name="ck_entities_trust_status",
        ),
        # CHECK constraint for non-negative detection count
        CheckConstraint(
            "detection_count >= 0",
            name="ck_entities_detection_count",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Entity(id={self.id}, entity_type={self.entity_type!r}, "
            f"trust_status={self.trust_status!r}, "
            f"detection_count={self.detection_count}, last_seen_at={self.last_seen_at})>"
        )

    def get_trust_status(self) -> TrustStatus:
        """Get the trust status as an enum value.

        Returns:
            TrustStatus enum value (TRUSTED, UNTRUSTED, or UNKNOWN)
        """
        try:
            return TrustStatus(self.trust_status)
        except ValueError:
            return TrustStatus.UNKNOWN

    def is_trusted(self) -> bool:
        """Check if entity is trusted.

        Returns:
            True if entity trust_status is 'trusted', False otherwise
        """
        return self.trust_status == TrustStatus.TRUSTED.value

    def is_untrusted(self) -> bool:
        """Check if entity is explicitly untrusted.

        Returns:
            True if entity trust_status is 'untrusted', False otherwise
        """
        return self.trust_status == TrustStatus.UNTRUSTED.value

    def update_seen(self, timestamp: datetime | None = None) -> None:
        """Update the entity's last_seen_at timestamp and increment detection count.

        Args:
            timestamp: Optional timestamp to use. Defaults to current UTC time.
        """
        self.last_seen_at = timestamp or datetime.now(UTC)
        # Handle case where detection_count hasn't been initialized yet
        # (SQLAlchemy defaults are applied at database flush time)
        current_count = self.detection_count if self.detection_count is not None else 0
        self.detection_count = current_count + 1

    def set_embedding(
        self,
        vector: list[float],
        model: str = "clip",
        dimension: int | None = None,
    ) -> None:
        """Set the entity's embedding vector with metadata.

        Args:
            vector: The embedding vector as a list of floats
            model: The model used to generate the embedding (default: "clip")
            dimension: Optional dimension override (defaults to len(vector))
        """
        self.embedding_vector = {
            "vector": vector,
            "model": model,
            "dimension": dimension or len(vector),
        }

    def get_embedding_vector(self) -> list[float] | None:
        """Get the raw embedding vector if available.

        Returns:
            The embedding vector as a list of floats, or None if not set
        """
        if self.embedding_vector and "vector" in self.embedding_vector:
            vector = self.embedding_vector["vector"]
            return list(vector) if vector is not None else None
        return None

    def get_embedding_model(self) -> str | None:
        """Get the model name used for the embedding.

        Returns:
            The model name string, or None if embedding not set
        """
        if self.embedding_vector and "model" in self.embedding_vector:
            model = self.embedding_vector["model"]
            return str(model) if model is not None else None
        return None

    @classmethod
    def from_detection(
        cls,
        entity_type: EntityType | str,
        detection_id: int | None = None,
        embedding: list[float] | None = None,
        model: str = "clip",
        entity_metadata: dict[str, Any] | None = None,
        trust_status: TrustStatus | str = TrustStatus.UNKNOWN,
    ) -> Entity:
        """Create a new Entity from a detection.

        Factory method for creating entities linked to their first detection.

        Args:
            entity_type: The type of entity (person, vehicle, etc.)
            detection_id: Optional ID of the primary detection
            embedding: Optional embedding vector
            model: Model used for embedding (default: "clip")
            entity_metadata: Optional additional metadata
            trust_status: Trust classification (default: unknown)

        Returns:
            A new Entity instance
        """
        entity_type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type
        trust_status_str = (
            trust_status.value if isinstance(trust_status, TrustStatus) else trust_status
        )

        entity = cls(
            entity_type=entity_type_str,
            trust_status=trust_status_str,
            primary_detection_id=detection_id,
            detection_count=1,
            entity_metadata=entity_metadata,
        )

        if embedding:
            entity.set_embedding(embedding, model=model)

        return entity

    async def validate_primary_detection_async(
        self, session: AsyncSession
    ) -> tuple[bool, str | None]:
        """Validate that primary_detection_id references an existing detection.

        Since the detections table is partitioned and cannot have FK constraints
        referencing just the id column, we perform application-level validation.

        This method should be called before persisting an Entity with a
        primary_detection_id to ensure referential integrity.

        Args:
            session: SQLAlchemy async session for database queries

        Returns:
            A tuple of (is_valid, error_message) where:
            - is_valid: True if detection exists or primary_detection_id is None
            - error_message: Description of the error if validation fails, None otherwise

        Example:
            >>> entity = Entity(entity_type="person", primary_detection_id=123)
            >>> is_valid, error = await entity.validate_primary_detection_async(session)
            >>> if not is_valid:
            ...     raise ValueError(error)
        """
        if self.primary_detection_id is None:
            return True, None

        # Import here to avoid circular imports
        from .detection import Detection

        # Check if the detection exists
        result = await session.execute(
            select(Detection.id).where(Detection.id == self.primary_detection_id).limit(1)
        )
        detection_exists = result.scalar_one_or_none() is not None

        if not detection_exists:
            return False, (
                f"Detection with id={self.primary_detection_id} does not exist. "
                f"Cannot set as primary_detection_id for Entity."
            )

        return True, None

    async def set_primary_detection_validated(
        self,
        session: AsyncSession,
        detection_id: int | None,
    ) -> tuple[bool, str | None]:
        """Set primary_detection_id with validation.

        This is the recommended way to set primary_detection_id as it ensures
        the referenced detection exists before setting the value.

        Args:
            session: SQLAlchemy async session for database queries
            detection_id: The detection ID to set, or None to clear

        Returns:
            A tuple of (success, error_message) where:
            - success: True if the detection was set successfully
            - error_message: Description of the error if validation fails

        Example:
            >>> entity = Entity(entity_type="person")
            >>> success, error = await entity.set_primary_detection_validated(session, 123)
            >>> if not success:
            ...     raise ValueError(error)
        """
        if detection_id is None:
            self.primary_detection_id = None
            return True, None

        # Temporarily set to validate
        old_value = self.primary_detection_id
        self.primary_detection_id = detection_id

        is_valid, error = await self.validate_primary_detection_async(session)
        if not is_valid:
            # Restore old value on validation failure
            self.primary_detection_id = old_value
            return False, error

        return True, None
