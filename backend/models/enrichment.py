"""Enrichment result models for on-demand AI model outputs.

This module contains SQLAlchemy models for storing enrichment results from
the on-demand model loading system. These models store outputs from:
- Pose estimation (YOLOv8n-pose)
- Threat detection (Threat-Detection-YOLOv8n)
- Action recognition (X-CLIP)

RETIRED (R8 S4, owner ruling 2026-09-30): `DemographicsResult`
(`demographics_results`) and `ReIDEmbedding` (`reid_embeddings`) — zero live
readers and zero shipped writers (the sole writer was `enrichment_pipeline.py`,
deleted in S2b; the surviving reference is `scripts/seed-events.py`, which
shipped code never invokes). The dated DROP SQL is
`docs/api/migrations/2026-09-30-retire-demographics-reid-tables.sql`.
`pose_results`/`action_results` STAY: unlike the retired pair they are READ on
the shipped alert-test path, the same reachability class as `threat_detections`
(kept). `PoseResult`/`ThreatDetection`/`ActionResult` stay below; guard:
`backend/tests/unit/models/test_r8_s4_demographics_reid_retirement.py`.
The name-trap twin `household.PersonEmbedding` (`person_embeddings`, the LIVE
VLM re-ID gallery) and the JSONB key `detections.enrichment_data["reid_embedding"]`
are NOT this module's business and stay exactly as they are.

See: docs/plans/2026-01-19-model-zoo-prompt-improvements-design.md Section 6
Related Linear issue: NEM-3042
"""

from datetime import UTC, datetime
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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base

if TYPE_CHECKING:
    from .detection import Detection


class PoseResult(Base):
    """Stores pose estimation results from YOLOv8n-pose model.

    Each pose result is associated with a detection and contains:
    - 17 keypoints in COCO format as a JSON array
    - Classified pose (standing, crouching, bending_over, arms_raised)
    - Confidence score
    - Suspicious flag for concerning postures (crouching near doors, etc.)
    """

    __tablename__ = "pose_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detection_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("detections.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    keypoints: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, comment="17 COCO keypoints as [[x, y, conf], ...]"
    )
    pose_class: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Classified pose: standing, crouching, etc."
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    detection: Mapped[Detection] = relationship("Detection", back_populates="pose_result")

    __table_args__ = (
        Index("idx_pose_results_detection_id", "detection_id"),
        Index("idx_pose_results_created_at", "created_at"),
        Index("idx_pose_results_is_suspicious", "is_suspicious"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_pose_results_confidence_range",
        ),
        CheckConstraint(
            "pose_class IS NULL OR pose_class IN ('standing', 'crouching', 'bending_over', "
            "'arms_raised', 'sitting', 'lying_down', 'unknown')",
            name="ck_pose_results_pose_class",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PoseResult(id={self.id}, detection_id={self.detection_id}, "
            f"pose_class={self.pose_class!r}, is_suspicious={self.is_suspicious})>"
        )


class ThreatDetection(Base):
    """Stores threat detection results from Threat-Detection-YOLOv8n model.

    Each threat detection is associated with a detection and contains:
    - Threat type (gun, knife, grenade, explosive)
    - Confidence score
    - Severity classification (critical, high, medium)
    - Bounding box of the detected threat object
    """

    __tablename__ = "threat_detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detection_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("detections.id", ondelete="CASCADE"), nullable=False
    )
    threat_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Type of threat: gun, knife, etc."
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Severity: critical, high, medium"
    )
    bbox: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, comment="Bounding box as [x1, y1, x2, y2]"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    detection: Mapped[Detection] = relationship("Detection", back_populates="threat_detections")

    __table_args__ = (
        Index("idx_threat_detections_detection_id", "detection_id"),
        Index("idx_threat_detections_created_at", "created_at"),
        Index("idx_threat_detections_threat_type", "threat_type"),
        Index("idx_threat_detections_severity", "severity"),
        # Composite index for queries like "find all critical gun threats"
        Index("idx_threat_detections_type_severity", "threat_type", "severity"),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_threat_detections_confidence_range",
        ),
        CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low')",
            name="ck_threat_detections_severity",
        ),
        CheckConstraint(
            "threat_type IN ('gun', 'knife', 'grenade', 'explosive', 'weapon', 'other')",
            name="ck_threat_detections_threat_type",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ThreatDetection(id={self.id}, detection_id={self.detection_id}, "
            f"threat_type={self.threat_type!r}, severity={self.severity!r})>"
        )


class ActionResult(Base):
    """Stores action recognition results from X-CLIP model.

    Each action result is associated with a detection and contains:
    - Recognized action (walking, running, climbing, etc.)
    - Confidence score
    - Suspicious flag for concerning actions
    - All action scores for transparency
    """

    __tablename__ = "action_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detection_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("detections.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    action: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Recognized action: walking, running, etc."
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    all_scores: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Dict of action -> score for all candidates"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    detection: Mapped[Detection] = relationship("Detection", back_populates="action_result")

    __table_args__ = (
        Index("idx_action_results_detection_id", "detection_id"),
        Index("idx_action_results_created_at", "created_at"),
        Index("idx_action_results_action", "action"),
        Index("idx_action_results_is_suspicious", "is_suspicious"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_action_results_confidence_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ActionResult(id={self.id}, detection_id={self.detection_id}, "
            f"action={self.action!r}, is_suspicious={self.is_suspicious})>"
        )
