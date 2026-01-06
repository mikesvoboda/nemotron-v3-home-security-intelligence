"""Scene change model for camera tampering alerts.

Scene changes represent detected visual changes to camera views that may indicate
tampering, angle changes, or blocked/obscured views. These are detected by the
SceneChangeDetector service using SSIM (Structural Similarity Index) comparison.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.time_utils import utc_now

from .camera import Base

if TYPE_CHECKING:
    from .camera import Camera


class SceneChangeType(str, enum.Enum):
    """Type of scene change detected."""

    VIEW_BLOCKED = "view_blocked"
    ANGLE_CHANGED = "angle_changed"
    VIEW_TAMPERED = "view_tampered"
    UNKNOWN = "unknown"


class SceneChange(Base):
    """Scene change model representing detected camera view changes.

    Scene changes are detected when the current camera view significantly differs
    from the stored baseline image. This can indicate tampering, camera movement,
    or obstruction.

    Attributes:
        id: Unique auto-incrementing identifier
        camera_id: Foreign key to the source camera
        detected_at: When the scene change was detected
        change_type: Type of change (view_blocked, angle_changed, view_tampered, unknown)
        similarity_score: SSIM score between 0 and 1 (1 = identical, lower = more different)
        acknowledged: Whether the scene change has been acknowledged by a user
        acknowledged_at: When the scene change was acknowledged
        file_path: Path to the image that triggered the scene change detection
    """

    __tablename__ = "scene_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(
        String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    change_type: Mapped[SceneChangeType] = mapped_column(
        Enum(SceneChangeType, name="scene_change_type_enum"),
        default=SceneChangeType.UNKNOWN,
        nullable=False,
    )
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    camera: Mapped[Camera] = relationship("Camera", back_populates="scene_changes")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_scene_changes_camera_id", "camera_id"),
        Index("idx_scene_changes_detected_at", "detected_at"),
        Index("idx_scene_changes_acknowledged", "acknowledged"),
        Index("idx_scene_changes_camera_acknowledged", "camera_id", "acknowledged"),
        # BRIN index for time-series queries on detected_at (append-only chronological data)
        # Much smaller than B-tree (~1000x) and ideal for range queries on ordered timestamps
        Index(
            "ix_scene_changes_detected_at_brin",
            "detected_at",
            postgresql_using="brin",
        ),
        # CHECK constraint for business rules
        CheckConstraint(
            "similarity_score >= 0.0 AND similarity_score <= 1.0",
            name="ck_scene_changes_similarity_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SceneChange(id={self.id!r}, camera_id={self.camera_id!r}, "
            f"change_type={self.change_type!r}, similarity_score={self.similarity_score:.2f})>"
        )
