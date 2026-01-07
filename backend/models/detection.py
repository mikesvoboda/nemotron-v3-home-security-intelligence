"""Detection model for object detection results."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.api.schemas.enrichment_data import validate_enrichment_data

from .camera import Base

if TYPE_CHECKING:
    from .camera import Camera
    from .event_detection import EventDetection


class Detection(Base):
    """Detection model representing an object detection result.

    Stores detection metadata including bounding box coordinates,
    confidence scores, and references to the source image or video file.

    For video files, additional metadata is stored:
    - media_type: "image" or "video"
    - duration: Video duration in seconds
    - video_codec: Video codec (e.g., "h264", "hevc")
    - video_width: Video resolution width
    - video_height: Video resolution height
    """

    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(
        String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_type: Mapped[str | None] = mapped_column(String, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    object_type: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String, nullable=True)

    # Video-specific metadata
    media_type: Mapped[str | None] = mapped_column(String, nullable=True, default="image")
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    video_codec: Mapped[str | None] = mapped_column(String, nullable=True)
    video_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Enrichment pipeline results (JSONB for structured vision model outputs)
    # Contains results from 18+ vision models: license plate, face, vehicle,
    # clothing, violence, weather, image quality, pet classification, etc.
    enrichment_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    camera: Mapped[Camera] = relationship("Camera", back_populates="detections")
    # Junction table relationship for normalized event associations
    # This provides access to EventDetection records for this detection
    event_records: Mapped[list[EventDetection]] = relationship(
        "EventDetection", back_populates="detection", cascade="all, delete-orphan"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_detections_camera_id", "camera_id"),
        Index("idx_detections_detected_at", "detected_at"),
        Index("idx_detections_camera_time", "camera_id", "detected_at"),
        Index("idx_detections_camera_object_type", "camera_id", "object_type"),
        # NEM-1591: Composite index for class-based analytics queries
        # Enables efficient queries like "show all person detections in the last hour"
        # Column order: object_type (equality filter) first, then detected_at (range/sort)
        Index("ix_detections_object_type_detected_at", "object_type", "detected_at"),
        # GIN index with jsonb_path_ops for containment queries (@>) on enrichment_data
        # Enables fast queries like: enrichment_data @> '{"license_plates": [{}]}'
        Index(
            "ix_detections_enrichment_data_gin",
            "enrichment_data",
            postgresql_using="gin",
            postgresql_ops={"enrichment_data": "jsonb_path_ops"},
        ),
        # BRIN index for time-series queries on detected_at (append-only chronological data)
        # Much smaller than B-tree (~1000x) and ideal for range queries on ordered timestamps
        Index(
            "ix_detections_detected_at_brin",
            "detected_at",
            postgresql_using="brin",
        ),
        # CHECK constraints for enum-like columns and business rules
        CheckConstraint(
            "media_type IS NULL OR media_type IN ('image', 'video')",
            name="ck_detections_media_type",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_detections_confidence_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Detection(id={self.id}, camera_id={self.camera_id!r}, "
            f"object_type={self.object_type!r}, confidence={self.confidence})>"
        )

    def validate_enrichment_data(self) -> tuple[bool, list[str]]:
        """Validate enrichment_data field using Pydantic schema.

        Returns:
            Tuple of (is_valid, messages) where messages contains warnings/errors
        """
        result = validate_enrichment_data(self.enrichment_data, strict=False)
        messages = result.warnings + result.errors
        return result.is_valid, messages

    def get_validated_enrichment_data(self) -> dict[str, Any] | None:
        """Get validated and coerced enrichment_data.

        Returns validated data with values coerced to proper types/ranges.
        Returns None if enrichment_data is None.
        """
        result = validate_enrichment_data(self.enrichment_data, strict=False)
        return result.data

    def set_enrichment_data_validated(
        self, data: dict[str, Any], strict: bool = False
    ) -> tuple[bool, list[str]]:
        """Set enrichment_data after validation.

        Args:
            data: The enrichment data to validate and set
            strict: If True, fail on validation errors. If False, set data with warnings.

        Returns:
            Tuple of (success, warnings) where warnings contains any validation messages
        """
        result = validate_enrichment_data(data, strict=strict)

        if result.is_valid:
            self.enrichment_data = result.data
            return True, result.warnings
        else:
            # In strict mode, validation failed - don't set data
            return False, result.errors
