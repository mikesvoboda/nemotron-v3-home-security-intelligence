"""Enrichment result models for on-demand AI model outputs.

This module contains SQLAlchemy models for storing enrichment results from
the on-demand model loading system. These models store outputs from:
- Pose estimation (YOLOv8n-pose)
- Threat detection (Threat-Detection-YOLOv8n)
- Demographics (Age-Gender prediction)
- Re-identification embeddings (OSNet)
- Action recognition (X-CLIP)

See: docs/plans/2026-01-19-model-zoo-prompt-improvements-design.md Section 6
Related Linear issue: NEM-3042
"""

from __future__ import annotations

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


class DemographicsResult(Base):
    """Stores demographics prediction results from Age-Gender model.

    Each demographics result is associated with a detection and contains:
    - Estimated age range
    - Predicted gender
    - Confidence scores for each prediction
    """

    __tablename__ = "demographics_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detection_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("detections.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    age_range: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="Age range: 0-10, 11-20, etc."
    )
    age_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    gender: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="Gender: male, female, unknown"
    )
    gender_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    detection: Mapped[Detection] = relationship("Detection", back_populates="demographics_result")

    __table_args__ = (
        Index("idx_demographics_results_detection_id", "detection_id"),
        Index("idx_demographics_results_created_at", "created_at"),
        CheckConstraint(
            "age_confidence IS NULL OR (age_confidence >= 0.0 AND age_confidence <= 1.0)",
            name="ck_demographics_results_age_confidence_range",
        ),
        CheckConstraint(
            "gender_confidence IS NULL OR (gender_confidence >= 0.0 AND gender_confidence <= 1.0)",
            name="ck_demographics_results_gender_confidence_range",
        ),
        CheckConstraint(
            "gender IS NULL OR gender IN ('male', 'female', 'unknown')",
            name="ck_demographics_results_gender",
        ),
        CheckConstraint(
            "age_range IS NULL OR age_range IN ('0-10', '11-20', '21-30', '31-40', '41-50', "
            "'51-60', '61-70', '71-80', '81+', 'unknown')",
            name="ck_demographics_results_age_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DemographicsResult(id={self.id}, detection_id={self.detection_id}, "
            f"age_range={self.age_range!r}, gender={self.gender!r})>"
        )


class ReIDEmbedding(Base):
    """Stores person re-identification embeddings from OSNet model.

    Each embedding is associated with a detection and contains:
    - 512-dimensional feature vector as JSON array
    - Hash of the embedding for fast similarity lookups
    """

    __tablename__ = "reid_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detection_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("detections.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    embedding: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, comment="512-dim feature vector as JSON array"
    )
    embedding_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="SHA256 hash for quick lookup"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    detection: Mapped[Detection] = relationship("Detection", back_populates="reid_embedding")

    __table_args__ = (
        Index("idx_reid_embeddings_detection_id", "detection_id"),
        Index("idx_reid_embeddings_created_at", "created_at"),
        # embedding_hash is already indexed via index=True in column definition
    )

    def __repr__(self) -> str:
        embedding_preview = (
            f"[{self.embedding[0]:.4f}, ...]"
            if self.embedding and len(self.embedding) > 0
            else None
        )
        return (
            f"<ReIDEmbedding(id={self.id}, detection_id={self.detection_id}, "
            f"embedding={embedding_preview})>"
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
