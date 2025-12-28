"""Detection model for object detection results."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base

if TYPE_CHECKING:
    from .camera import Camera


class Detection(Base):
    """Detection model representing an object detection result.

    Stores detection metadata including bounding box coordinates,
    confidence scores, and references to the source image file.
    """

    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(
        String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_type: Mapped[str | None] = mapped_column(String, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    object_type: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    camera: Mapped[Camera] = relationship("Camera", back_populates="detections")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_detections_camera_id", "camera_id"),
        Index("idx_detections_detected_at", "detected_at"),
        Index("idx_detections_camera_time", "camera_id", "detected_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Detection(id={self.id}, camera_id={self.camera_id!r}, "
            f"object_type={self.object_type!r}, confidence={self.confidence})>"
        )
