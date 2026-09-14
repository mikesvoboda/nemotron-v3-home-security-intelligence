"""Camera model for home security system."""

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .enums import CameraStatus, IngestionMode

if TYPE_CHECKING:
    from .action_event import ActionEvent
    from .analytics_zone import LineZone, PolygonZone
    from .area import Area
    from .baseline import ActivityBaseline, ClassBaseline
    from .camera_zone import CameraZone
    from .detection import Detection
    from .dwell_time import DwellTimeRecord
    from .event import Event
    from .notification_preferences import CameraNotificationSetting
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

    normalized = folder_name.strip().lower()
    normalized = re.sub(r"[\s\-]+", "_", normalized)  # spaces/hyphens -> underscore
    normalized = re.sub(r"[^\w]", "", normalized)  # remove non-word chars
    normalized = re.sub(r"_+", "_", normalized)  # collapse multiple underscores
    return normalized.strip("_")


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
        # CHECK constraint for ingestion_mode enum-like values (NEM-4191)
        CheckConstraint(
            "ingestion_mode IN ('ftp', 'rtsp', 'onvif')",
            name="ck_cameras_ingestion_mode",
        ),
        # CHECK constraint for stream_profile enum-like values (NEM-4191)
        CheckConstraint(
            "stream_profile IS NULL OR stream_profile IN ('main', 'sub', 'both')",
            name="ck_cameras_stream_profile",
        ),
        # CHECK constraint for motion_sensitivity range (NEM-4191)
        CheckConstraint(
            "motion_sensitivity >= 0.0 AND motion_sensitivity <= 1.0",
            name="ck_cameras_motion_sensitivity",
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

    # RTSP/ONVIF streaming fields (NEM-4191)
    # Note: These fields have Python-level defaults set in __init__ to ensure
    # defaults are available at object construction time (not just at DB insert)
    ingestion_mode: Mapped[str] = mapped_column(
        String, default=IngestionMode.FTP.value, nullable=False
    )
    rtsp_url: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    rtsp_username: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    rtsp_password: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    stream_profile: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    motion_sensitivity: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)

    # Depth calibration data for depth-to-distance conversion (NEM-5283)
    calibration_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)

    def __init__(
        self,
        *,
        id: str,
        name: str,
        folder_path: str,
        status: str | None = None,
        created_at: datetime | None = None,
        last_seen_at: datetime | None = None,
        deleted_at: datetime | None = None,
        property_id: int | None = None,
        ingestion_mode: str | None = None,
        rtsp_url: str | None = None,
        rtsp_username: str | None = None,
        rtsp_password: str | None = None,
        stream_profile: str | None = None,
        motion_sensitivity: float | None = None,
        calibration_data: dict | None = None,
    ):
        """Initialize a Camera instance with Python-level defaults.

        SQLAlchemy's mapped_column defaults only apply at database insert time.
        This __init__ ensures defaults are available at Python object construction.
        """
        super().__init__()
        self.id = id
        self.name = name
        self.folder_path = folder_path
        self.status = status or CameraStatus.ONLINE.value
        self.created_at = created_at or datetime.now(UTC)
        self.last_seen_at = last_seen_at
        self.deleted_at = deleted_at
        self.property_id = property_id
        self.ingestion_mode = ingestion_mode or IngestionMode.FTP.value
        self.rtsp_url = rtsp_url
        self.rtsp_username = rtsp_username
        self.rtsp_password = rtsp_password
        self.stream_profile = stream_profile
        self.motion_sensitivity = motion_sensitivity if motion_sensitivity is not None else 0.5
        self.calibration_data = calibration_data

    # Relationships
    detections: Mapped[list[Detection]] = relationship(
        "Detection", back_populates="camera", cascade="all, delete-orphan", passive_deletes=True
    )
    events: Mapped[list[Event]] = relationship(
        "Event", back_populates="camera", cascade="all, delete-orphan", passive_deletes=True
    )
    camera_zones: Mapped[list[CameraZone]] = relationship(
        "CameraZone", back_populates="camera", cascade="all, delete-orphan", passive_deletes=True
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
        "Track", back_populates="camera", cascade="all, delete-orphan", passive_deletes=True
    )
    line_zones: Mapped[list[LineZone]] = relationship(
        "LineZone", back_populates="camera", cascade="all, delete-orphan", passive_deletes=True
    )
    polygon_zones: Mapped[list[PolygonZone]] = relationship(
        "PolygonZone", back_populates="camera", cascade="all, delete-orphan", passive_deletes=True
    )
    dwell_time_records: Mapped[list[DwellTimeRecord]] = relationship(
        "DwellTimeRecord",
        back_populates="camera",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    action_events: Mapped[list[ActionEvent]] = relationship(
        "ActionEvent", back_populates="camera", cascade="all, delete-orphan", passive_deletes=True
    )
    plate_reads: Mapped[list[PlateRead]] = relationship(
        "PlateRead", back_populates="camera", cascade="all, delete-orphan", passive_deletes=True
    )
    notification_setting: Mapped[CameraNotificationSetting | None] = relationship(
        "CameraNotificationSetting", back_populates="camera", uselist=False
    )

    @property
    def is_deleted(self) -> bool:
        """Check if this camera is soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Soft delete this camera by setting deleted_at timestamp."""
        self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restore a soft-deleted camera by clearing deleted_at timestamp."""
        self.deleted_at = None

    async def hard_delete(self, session: object) -> None:
        """Permanently remove this camera from the database."""
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
