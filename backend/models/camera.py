"""Camera model for home security system."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .detection import Detection
    from .event import Event
    from .zone import Zone


def normalize_camera_id(folder_name: str) -> str:
    """Normalize a folder name to a consistent camera ID.

    Converts folder names like "Front Door", "front-door", "Front_Door" to
    a consistent lowercase underscore format: "front_door".

    Args:
        folder_name: The folder name to normalize

    Returns:
        Normalized camera ID string
    """
    if not folder_name:
        return ""

    # Convert to lowercase
    normalized = folder_name.lower().strip()

    # Replace spaces and hyphens with underscores
    normalized = re.sub(r"[\s\-]+", "_", normalized)

    # Remove any non-alphanumeric characters except underscores
    normalized = re.sub(r"[^a-z0-9_]", "", normalized)

    # Collapse multiple underscores
    normalized = re.sub(r"_+", "_", normalized)

    # Strip leading/trailing underscores
    normalized = normalized.strip("_")

    return normalized


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    detections: Mapped[list[Detection]] = relationship(
        "Detection", back_populates="camera", cascade="all, delete-orphan"
    )
    events: Mapped[list[Event]] = relationship(
        "Event", back_populates="camera", cascade="all, delete-orphan"
    )
    zones: Mapped[list[Zone]] = relationship(
        "Zone", back_populates="camera", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Camera(id={self.id!r}, name={self.name!r}, status={self.status!r})>"

    @classmethod
    def from_folder_name(cls, folder_name: str, folder_path: str) -> Camera:
        """Create a Camera instance from a folder name.

        Factory method that normalizes the folder name to create a consistent
        camera ID and uses the folder name as the display name.

        Args:
            folder_name: The folder name (e.g., "Front Door")
            folder_path: The full path to the folder

        Returns:
            A new Camera instance
        """
        camera_id = normalize_camera_id(folder_name)
        return cls(
            id=camera_id,
            name=folder_name,
            folder_path=folder_path,
            status="online",
        )
