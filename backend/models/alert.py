"""Alert and AlertRule models for the alerting system.

This module defines the data models for managing security alerts and alert rules.
Alerts are generated based on events and can be sent through multiple notification
channels. Alert rules define the conditions under which alerts are triggered.

Condition Types:
    - risk_threshold: Alert when event risk_score >= threshold (e.g., 70)
    - object_types: Alert when specific objects detected (person, vehicle, animal)
    - camera_ids: Only apply rule to specific cameras (empty = all)
    - time_range: Only apply during certain hours (e.g., 22:00-06:00)
    - zone_ids: Only apply when detection is in specific zones (empty = any)
    - min_confidence: Minimum detection confidence threshold

Rule Evaluation:
    - All conditions in a rule must match (AND logic)
    - Multiple rules can trigger for same event
    - Higher severity rule takes precedence for same event
    - Check cooldown before triggering (use dedup_key)
"""

from datetime import datetime
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any
from uuid import uuid7

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
    Text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.time_utils import utc_now

from .camera import Base

if TYPE_CHECKING:
    from .event import Event


class AlertSeverityEnum(StrEnum):
    """Alert severity levels."""

    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


class AlertStatusEnum(StrEnum):
    """Alert status values."""

    PENDING = auto()
    DELIVERED = auto()
    ACKNOWLEDGED = auto()
    DISMISSED = auto()


# Backward compatibility aliases
AlertSeverity = AlertSeverityEnum
AlertStatus = AlertStatusEnum


class Alert(Base):
    """Alert model representing a notification generated from a security event.

    Alerts are created when events match alert rule conditions. They track
    delivery status across notification channels and support deduplication
    to prevent alert fatigue.

    Deduplication:
        Alerts with the same dedup_key within the cooldown window (from the
        associated rule) are considered duplicates. The dedup_key is typically
        constructed from: camera_id + object_type + zone (if available).
    """

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid7()),
    )
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("alert_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AlertSeverity.MEDIUM,
    )
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AlertStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channels: Mapped[list | None] = mapped_column(JSON, nullable=True)
    dedup_key: Mapped[str] = mapped_column(String(255), nullable=False)
    # Note: Named alert_metadata to avoid collision with SQLAlchemy's reserved 'metadata'
    alert_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Optimistic locking version column (NEM-2581)
    # Prevents race conditions during concurrent acknowledge/dismiss operations
    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Relationships
    event: Mapped[Event] = relationship("Event", back_populates="alerts")
    rule: Mapped[AlertRule | None] = relationship("AlertRule", back_populates="alerts")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_alerts_event_id", "event_id"),
        Index("idx_alerts_rule_id", "rule_id"),
        Index("idx_alerts_severity", "severity"),
        Index("idx_alerts_status", "status"),
        Index("idx_alerts_created_at", "created_at"),
        Index("idx_alerts_dedup_key", "dedup_key"),
        Index("idx_alerts_dedup_key_created_at", "dedup_key", "created_at"),
        # Deduplication performance indexes
        Index("idx_alerts_delivered_at", "delivered_at"),
        Index("idx_alerts_event_rule_delivered", "event_id", "rule_id", "delivered_at"),
    )

    # Enable optimistic locking - SQLAlchemy will automatically increment version_id
    # on updates and raise StaleDataError if version doesn't match (NEM-2581)
    # Note: SQLAlchemy mapper_args is a special class attribute that doesn't use ClassVar
    __mapper_args__ = {"version_id_col": version_id}  # noqa: RUF012  # type: ignore[misc]

    def __repr__(self) -> str:
        return (
            f"<Alert(id={self.id!r}, event_id={self.event_id}, "
            f"severity={self.severity.value!r}, status={self.status.value!r})>"
        )

    def to_dict(self, for_websocket: bool = False) -> dict[str, Any]:
        """Convert Alert model to a dictionary representation.

        Provides unified serialization for both API responses and WebSocket broadcasts,
        eliminating code duplication between these two use cases.

        Args:
            for_websocket: If True, formats timestamps as ISO strings and excludes
                fields not needed for WebSocket broadcasts (delivered_at, channels,
                alert_metadata). If False, includes all fields for API responses.

        Returns:
            Dictionary representation of the alert suitable for JSON serialization.

        Examples:
            # For API response (full data)
            alert_dict = alert.to_dict()

            # For WebSocket broadcast (minimal data, ISO timestamps)
            ws_data = alert.to_dict(for_websocket=True)
        """
        # Extract enum values safely (handle both enum and raw string values)
        severity_value = self.severity.value if hasattr(self.severity, "value") else self.severity
        status_value = self.status.value if hasattr(self.status, "value") else self.status

        if for_websocket:
            # WebSocket format: minimal fields with ISO timestamp strings
            return {
                "id": self.id,
                "event_id": self.event_id,
                "rule_id": self.rule_id,
                "severity": severity_value,
                "status": status_value,
                "dedup_key": self.dedup_key,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            }

        # API response format: all fields with datetime objects
        return {
            "id": self.id,
            "event_id": self.event_id,
            "rule_id": self.rule_id,
            "severity": severity_value,
            "status": status_value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "delivered_at": self.delivered_at,
            "channels": self.channels or [],
            "dedup_key": self.dedup_key,
            "alert_metadata": self.alert_metadata,
        }


class AlertRule(Base):
    """AlertRule model defining conditions for generating alerts.

    Alert rules specify conditions that must ALL match (AND logic) for alerts to trigger:
    - risk_threshold: Minimum risk score (0-100)
    - object_types: List of object types to match (JSON array)
    - camera_ids: List of camera IDs to match (JSON array, empty = all)
    - zone_ids: List of zone IDs to match (JSON array, empty = any)
    - min_confidence: Minimum detection confidence (0.0-1.0)
    - schedule: Time-based conditions (JSON object with days, start_time, end_time)

    Rules also specify:
    - Severity level for triggered alerts
    - Cooldown period to prevent duplicate alerts
    - Dedup key template for generating unique identifiers
    - Notification channels to deliver alerts through
    """

    __tablename__ = "alert_rules"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid7()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(
            AlertSeverity,
            name="alert_severity",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AlertSeverity.MEDIUM,
    )

    # Condition: Risk score threshold (alert when risk_score >= threshold)
    # None means no risk threshold condition
    risk_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Condition: Object types to match (JSON array, e.g., ["person", "vehicle"])
    # Empty or null means all object types
    object_types: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Condition: Camera IDs to apply to (JSON array)
    # Empty or null means all cameras
    camera_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Condition: Zone IDs to match (JSON array)
    # Empty or null means any zone
    zone_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Condition: Minimum detection confidence threshold (0.0-1.0)
    min_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Schedule: Time-based conditions (JSON object with days, start_time, end_time, timezone)
    # If start_time > end_time, schedule spans midnight. No schedule = always active.
    schedule: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Legacy conditions field (for backward compatibility)
    # New rules should use explicit fields above
    conditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Cooldown: Deduplication key template and cooldown period
    # Template variables: {camera_id}, {rule_id}, {object_type}
    # e.g., "{camera_id}:{rule_id}" or "{camera_id}:{object_type}:{rule_id}"
    dedup_key_template: Mapped[str] = mapped_column(
        String(255), default="{camera_id}:{rule_id}", nullable=False
    )
    # Cooldown period in seconds (default: 5 minutes)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)

    # Notification channels (JSON array)
    channels: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    alerts: Mapped[list[Alert]] = relationship(
        "Alert", back_populates="rule", cascade="all, delete-orphan"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_alert_rules_name", "name"),
        Index("idx_alert_rules_enabled", "enabled"),
        Index("idx_alert_rules_severity", "severity"),
        # CHECK constraints for business rules
        CheckConstraint(
            "risk_threshold IS NULL OR (risk_threshold >= 0 AND risk_threshold <= 100)",
            name="ck_alert_rules_risk_threshold_range",
        ),
        CheckConstraint(
            "min_confidence IS NULL OR (min_confidence >= 0.0 AND min_confidence <= 1.0)",
            name="ck_alert_rules_min_confidence_range",
        ),
        CheckConstraint(
            "cooldown_seconds >= 0",
            name="ck_alert_rules_cooldown_non_negative",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AlertRule(id={self.id!r}, name={self.name!r}, "
            f"enabled={self.enabled}, severity={self.severity.value!r})>"
        )
