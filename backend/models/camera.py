"""Camera model for home security system."""

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .enums import CameraStatus

if TYPE_CHECKING:
    from .action_event import ActionEvent
    from .analytics_zone import LineZone, PolygonZone
    from .area import Area
    from .baseline import ActivityBaseline, ClassBaseline
    from .camera_zone import CameraZone
    from .detection import Detection
    from .dwell_time import DwellTimeRecord
    from .event import Event
    from .plate_read import PlateRead
    from .property import Property
    from .scene_change import SceneChange
    from .track import Track


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
    __table_args__ = (
        Index("idx_cameras_name_unique", "name", unique=True),
        Index("idx_cameras_folder_path_unique", "folder_path", unique=True),
        Index("idx_cameras_property_id", "property_id"),
        # CHECK constraint for status enum-like values
        CheckConstraint(
            "status IN ('online', 'offline', 'error', 'unknown')",
            name="ck_cameras_status",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    folder_path: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default=CameraStatus.ONLINE.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    property_id: Mapped[int | None] = mapped_column(
        ForeignKey("properties.id"), nullable=True, default=None
    )

    # Relationships
    detections: Mapped[list[Detection]] = relationship(
        "Detection", back_populates="camera", cascade="all, delete-orphan"
    )
    events: Mapped[list[Event]] = relationship(
        "Event", back_populates="camera", cascade="all, delete-orphan"
    )
    camera_zones: Mapped[list[CameraZone]] = relationship(
        "CameraZone", back_populates="camera", cascade="all, delete-orphan"
    )
    activity_baselines: Mapped[list[ActivityBaseline]] = relationship(
        "ActivityBaseline",
        back_populates="camera",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    class_baselines: Mapped[list[ClassBaseline]] = relationship(
        "ClassBaseline", back_populates="camera", cascade="all, delete-orphan", passive_deletes=True
    )
    scene_changes: Mapped[list[SceneChange]] = relationship(
        "SceneChange", back_populates="camera", cascade="all, delete-orphan", passive_deletes=True
    )
    # Note: Named 'property_ref' to avoid shadowing Python's built-in @property decorator
    property_ref: Mapped[Property | None] = relationship(
        "Property",
        back_populates="cameras",
    )
    areas: Mapped[list[Area]] = relationship(
        "Area",
        secondary="camera_areas",
        back_populates="cameras",
    )
    tracks: Mapped[list[Track]] = relationship(
        "Track", back_populates="camera", cascade="all, delete-orphan"
    )
    line_zones: Mapped[list[LineZone]] = relationship(
        "LineZone", back_populates="camera", cascade="all, delete-orphan"
    )
    polygon_zones: Mapped[list[PolygonZone]] = relationship(
        "PolygonZone", back_populates="camera", cascade="all, delete-orphan"
    )
    dwell_time_records: Mapped[list[DwellTimeRecord]] = relationship(
        "DwellTimeRecord", back_populates="camera", cascade="all, delete-orphan"
    )
    action_events: Mapped[list[ActionEvent]] = relationship(
        "ActionEvent", back_populates="camera", cascade="all, delete-orphan"
    )
    plate_reads: Mapped[list[PlateRead]] = relationship(
        "PlateRead", back_populates="camera", cascade="all, delete-orphan"
    )

    @property
    def is_deleted(self) -> bool:
        """Check if this camera is soft-deleted.

        Returns:
            True if deleted_at is set, False otherwise
        """
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Soft delete this camera by setting deleted_at timestamp.

        This marks the camera as deleted without removing it from the database,
        preserving referential integrity with related records.
        """
        self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restore a soft-deleted camera by clearing deleted_at timestamp."""
        self.deleted_at = None

    async def hard_delete(self, session: object) -> None:
        """Hard delete this camera, permanently removing it from the database.

        Args:
            session: SQLAlchemy async session to use for deletion
        """
        await session.delete(self)  # type: ignore[attr-defined]

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
            status=CameraStatus.ONLINE.value,
        )

    def __repr__(self) -> str:
        return f"<Camera(id={self.id!r}, name={self.name!r}, status={self.status!r})>"
