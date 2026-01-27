"""PlateRead model for storing license plate detection records.

This module provides the PlateRead SQLAlchemy model for persisting
license plate recognition results from the ALPR (Automatic License
Plate Recognition) service.

Each PlateRead represents a single plate detection event with:
- Recognized text and confidence scores
- Bounding box location
- Image quality metrics
- Camera and timestamp information
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base

if TYPE_CHECKING:
    from .camera import Camera


class PlateRead(Base):
    """Model for storing license plate detection records.

    A PlateRead represents a single license plate recognition event,
    storing the detected plate text along with confidence metrics
    and image quality assessment.

    Attributes:
        id: Primary key (auto-incremented)
        camera_id: Foreign key to the camera that captured the plate
        timestamp: When the plate was detected
        plate_text: Recognized plate text (filtered to alphanumeric)
        raw_text: Original OCR output before filtering
        detection_confidence: Confidence of plate detection/localization (0-1)
        ocr_confidence: Confidence of text recognition (0-1)
        bbox: Bounding box coordinates as [x1, y1, x2, y2]
        image_quality_score: Quality assessment score (0-1)
        is_enhanced: Whether low-light enhancement was applied
        is_blurry: Whether motion blur was detected
        created_at: Record creation timestamp
    """

    __tablename__ = "plate_reads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(
        String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    plate_text: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(String(50), nullable=False)
    detection_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    ocr_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    # Bounding box: [x1, y1, x2, y2] in pixel coordinates
    bbox: Mapped[list] = mapped_column(JSONB, nullable=False)
    image_quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_enhanced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_blurry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    # Relationships
    camera: Mapped[Camera] = relationship("Camera", back_populates="plate_reads")

    # Indexes for efficient querying
    __table_args__ = (
        # Composite index for camera and time range queries
        Index("idx_plate_reads_camera_timestamp", "camera_id", "timestamp"),
        # Index for plate text searches (partial match via LIKE)
        Index("idx_plate_reads_plate_text", "plate_text"),
        # Index for confidence-based filtering
        Index("idx_plate_reads_ocr_confidence", "ocr_confidence"),
        # BRIN index for time-series queries
        Index("idx_plate_reads_timestamp_brin", "timestamp", postgresql_using="brin"),
    )

    def __repr__(self) -> str:
        return (
            f"<PlateRead(id={self.id}, plate_text={self.plate_text!r}, "
            f"camera_id={self.camera_id!r}, timestamp={self.timestamp})>"
        )
