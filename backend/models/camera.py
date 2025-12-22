"""Camera model for home security system."""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class Camera(Base):
    """Camera model representing a security camera.

    Tracks camera metadata, status, and file system path for image uploads.
    """

    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    folder_path: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="online", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    detections: Mapped[list["Detection"]] = relationship(
        "Detection", back_populates="camera", cascade="all, delete-orphan"  # noqa: F821
    )
    events: Mapped[list["Event"]] = relationship(
        "Event", back_populates="camera", cascade="all, delete-orphan"  # noqa: F821
    )

    def __repr__(self) -> str:
        return f"<Camera(id={self.id!r}, name={self.name!r}, status={self.status!r})>"
