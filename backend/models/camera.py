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
    """Normalize a folder name to a valid camera ID.

    Converts folder names like "Front Door" to "front_door" for use as camera IDs.
    This ensures consistent mapping between upload directory names and camera IDs.

    Contract:
        - camera_id == normalize_camera_id(folder_name)
        - folder_path should end with folder_name (the directory being watched)

    Args:
        folder_name: The upload directory name (e.g., "Front Door", "back-yard", "Garage")

    Returns:
        Normalized camera ID (lowercase, spaces/hyphens replaced with underscores)
    """
    if not folder_name:
        return ""

    # Strip whitespace
    normalized = folder_name.strip()
    # Convert to lowercase
    normalized = normalized.lower()
    # Replace spaces and hyphens with underscores
    normalized = re.sub(r"[\s\-]+", "_", normalized)
    # Remove any characters that aren't alphanumeric or underscore
    normalized = re.sub(r"[^\w]", "", normalized)
    # Collapse multiple underscores
    normalized = re.sub(r"_+", "_", normalized)
    # Remove leading/trailing underscores
    normalized = normalized.strip("_")

    return normalized


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class Camera(Base):
    """Camera model representing a security camera.

    Tracks camera metadata, status, and file system path for image uploads.

    Camera ID Contract:
        The camera.id MUST match the normalized form of the upload directory name.
        Use normalize_camera_id(folder_name) to generate consistent IDs.

        Example:
            Upload path: /export/foscam/Front Door/image.jpg
            folder_name: "Front Door"
            camera.id: "front_door" (via normalize_camera_id)
            camera.folder_path: "/export/foscam/Front Door"

        This ensures the file_watcher can correctly map uploaded files to cameras
        without requiring database lookups for every file.
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

    @classmethod
    def from_folder_name(cls, folder_name: str, folder_path: str) -> Camera:
        """Create a Camera instance from an upload folder name.

        This factory method ensures the camera ID matches the normalized folder name,
        maintaining the contract between upload directories and camera records.

        Args:
            folder_name: The upload directory name (e.g., "Front Door")
            folder_path: Full path to the upload directory

        Returns:
            Camera instance with correctly normalized ID
        """
        camera_id = normalize_camera_id(folder_name)
        # Use folder name as display name (preserves original casing/spacing)
        return cls(
            id=camera_id,
            name=folder_name,
            folder_path=folder_path,
            status="online",
        )

    def __repr__(self) -> str:
        return f"<Camera(id={self.id!r}, name={self.name!r}, status={self.status!r})>"
