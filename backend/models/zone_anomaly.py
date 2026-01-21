"""Zone anomaly model for detecting activity anomalies in camera zones.

This module defines the SQLAlchemy model for storing zone anomalies detected
when real-time activity deviates from established baselines.

Features:
    - Multiple anomaly types: unusual time, frequency, dwell, entity
    - Severity levels based on deviation magnitude
    - Links to detections and zones for context
    - Acknowledgment workflow support
    - Thumbnail support for visual context

Related: NEM-3198 (Backend Anomaly Detection Service)
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.time_utils import utc_now

from .camera import Base

if TYPE_CHECKING:
    from .camera_zone import CameraZone
    from .detection import Detection


class AnomalyType(str, enum.Enum):
    """Types of zone anomalies that can be detected."""

    UNUSUAL_TIME = "unusual_time"
    UNUSUAL_FREQUENCY = "unusual_frequency"
    UNUSUAL_DWELL = "unusual_dwell"
    UNUSUAL_ENTITY = "unusual_entity"


class AnomalySeverity(str, enum.Enum):
    """Severity levels for detected anomalies."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ZoneAnomaly(Base):
    """Zone anomaly model for storing detected activity anomalies."""

    __tablename__ = "zone_anomalies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    zone_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("camera_zones.id", ondelete="CASCADE"),
        nullable=False,
    )
    camera_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Anomaly classification
    anomaly_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")

    # Human-readable details
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Quantitative details
    expected_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    deviation: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Related detection (optional)
    detection_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("detections.id", ondelete="SET NULL"),
        nullable=True,
    )
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Acknowledgment workflow
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    zone: Mapped[CameraZone] = relationship("CameraZone", back_populates="anomalies")
    detection: Mapped[Detection | None] = relationship("Detection")

    # Constraints and indexes
    __table_args__ = (
        Index("idx_zone_anomalies_zone_id", "zone_id"),
        Index("idx_zone_anomalies_camera_id", "camera_id"),
        Index("idx_zone_anomalies_timestamp", "timestamp"),
        Index("idx_zone_anomalies_severity", "severity"),
        Index("idx_zone_anomalies_acknowledged", "acknowledged"),
        Index("idx_zone_anomalies_zone_timestamp", "zone_id", "timestamp"),
        Index("idx_zone_anomalies_unacknowledged", "acknowledged", "severity", "timestamp"),
        CheckConstraint(
            "anomaly_type IN ('unusual_time', 'unusual_frequency', 'unusual_dwell', 'unusual_entity')",
            name="ck_zone_anomalies_anomaly_type",
        ),
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name="ck_zone_anomalies_severity",
        ),
        CheckConstraint(
            "deviation IS NULL OR deviation >= 0",
            name="ck_zone_anomalies_deviation_non_negative",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ZoneAnomaly(id={self.id!r}, zone_id={self.zone_id!r}, "
            f"anomaly_type={self.anomaly_type!r}, severity={self.severity!r}, "
            f"timestamp={self.timestamp!r})>"
        )

    def acknowledge(self, acknowledged_by: str | None = None) -> None:
        """Mark this anomaly as acknowledged."""
        self.acknowledged = True
        self.acknowledged_at = utc_now()
        self.acknowledged_by = acknowledged_by
