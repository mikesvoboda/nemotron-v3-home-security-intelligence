"""Entity model for person/object re-identification tracking.

This module provides the Entity model for tracking unique individuals
and objects across multiple cameras using embedding vectors for
re-identification.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base
from .enums import EntityType

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

    # Optional reference to the primary/best detection for this entity
    primary_detection_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("detections.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    primary_detection: Mapped[Detection | None] = relationship(
        "Detection",
        foreign_keys=[primary_detection_id],
        lazy="selectin",
    )

    # Indexes for common query patterns
    __table_args__ = (
        # Index on entity_type for filtering by type
        Index("idx_entities_entity_type", "entity_type"),
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
        # CHECK constraint for non-negative detection count
        CheckConstraint(
            "detection_count >= 0",
            name="ck_entities_detection_count",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Entity(id={self.id}, entity_type={self.entity_type!r}, "
            f"detection_count={self.detection_count}, last_seen_at={self.last_seen_at})>"
        )

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
    ) -> Entity:
        """Create a new Entity from a detection.

        Factory method for creating entities linked to their first detection.

        Args:
            entity_type: The type of entity (person, vehicle, etc.)
            detection_id: Optional ID of the primary detection
            embedding: Optional embedding vector
            model: Model used for embedding (default: "clip")
            entity_metadata: Optional additional metadata

        Returns:
            A new Entity instance
        """
        entity_type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type

        entity = cls(
            entity_type=entity_type_str,
            primary_detection_id=detection_id,
            detection_count=1,
            entity_metadata=entity_metadata,
        )

        if embedding:
            entity.set_embedding(embedding, model=model)

        return entity
