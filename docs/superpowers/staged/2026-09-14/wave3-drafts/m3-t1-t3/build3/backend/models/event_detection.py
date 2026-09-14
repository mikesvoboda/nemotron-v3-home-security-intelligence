"""EventDetection junction table for Event-Detection many-to-many relationship.

This module defines the junction/association table that normalizes the relationship
between Events and Detections. Previously, detection IDs were stored as a JSON array
or comma-separated string in the events.detection_ids column.

This normalized structure provides:
- Better query performance with proper indexes
- Referential integrity via foreign keys
- Efficient joins for fetching related detections
- Support for additional metadata on the relationship (e.g., created_at)
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base

if TYPE_CHECKING:
    from .detection import Detection
    from .event import Event


# Association table for SQLAlchemy's secondary relationship
# This is used by Event.detections and Detection.events relationships
event_detections = Table(
    "event_detections",
    Base.metadata,
    Column("event_id", Integer, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "detection_id", Integer, ForeignKey("detections.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "created_at", DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    ),
    Index("idx_event_detections_event_id", "event_id"),
    Index("idx_event_detections_detection_id", "detection_id"),
    Index("idx_event_detections_created_at", "created_at"),
)


class EventDetection(Base):
    """EventDetection model representing the junction between Events and Detections.

    This is an ORM model for the event_detections junction table, providing
    a class-based interface for queries and relationship management.

    The table uses a composite primary key (event_id, detection_id) to ensure
    each detection can only be associated with an event once.

    Attributes:
        event_id: Foreign key to events.id
        detection_id: Foreign key to detections.id
        created_at: Timestamp when the association was created

    Relationships:
        event: The associated Event
        detection: The associated Detection
    """

    __tablename__ = "event_detections"

    # Composite primary key columns
    event_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True,
    )
    detection_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("detections.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Timestamp for when the association was created
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    event: Mapped[Event] = relationship("Event", back_populates="detection_records")
    detection: Mapped[Detection] = relationship("Detection", back_populates="event_records")

    # Indexes are defined in the event_detections Table above
    # and in the migration add_event_detections_junction_table.py
    # Using extend_existing to share schema with the Table definition
    __table_args__ = ({"extend_existing": True},)

    def __repr__(self) -> str:
        return f"<EventDetection(event_id={self.event_id}, detection_id={self.detection_id})>"
