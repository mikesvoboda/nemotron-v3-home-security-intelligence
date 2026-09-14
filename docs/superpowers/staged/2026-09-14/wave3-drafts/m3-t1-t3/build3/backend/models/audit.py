"""Audit log model for tracking security-sensitive operations."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .camera import Base


class AuditAction(str, Enum):
    """Enumeration of auditable actions."""

    # Event actions
    EVENT_REVIEWED = "event_reviewed"
    EVENT_DISMISSED = "event_dismissed"

    # Settings actions
    SETTINGS_CHANGED = "settings_changed"
    CONFIG_UPDATED = "config_updated"

    # AI pipeline actions
    AI_REEVALUATED = "ai_reevaluated"

    # Media actions
    MEDIA_EXPORTED = "media_exported"

    # Alert rule actions
    RULE_CREATED = "rule_created"
    RULE_UPDATED = "rule_updated"
    RULE_DELETED = "rule_deleted"

    # Camera actions
    CAMERA_CREATED = "camera_created"
    CAMERA_UPDATED = "camera_updated"
    CAMERA_DELETED = "camera_deleted"

    # Authentication actions
    LOGIN = "login"
    LOGOUT = "logout"

    # API key actions
    API_KEY_CREATED = "api_key_created"  # pragma: allowlist secret
    API_KEY_REVOKED = "api_key_revoked"  # pragma: allowlist secret

    # Notification actions
    NOTIFICATION_TEST = "notification_test"

    # Admin actions
    DATA_CLEARED = "data_cleared"
    DATA_SEEDED = "data_seeded"
    CACHE_CLEARED = "cache_cleared"
    QUEUE_RESET = "queue_reset"

    # Security actions (NEM-1616)
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SECURITY_ALERT = "security_alert"
    CONTENT_TYPE_REJECTED = "content_type_rejected"
    FILE_MAGIC_REJECTED = "file_magic_rejected"

    # Bulk operations
    BULK_EXPORT_COMPLETED = "bulk_export_completed"

    # Cleanup operations
    CLEANUP_EXECUTED = "cleanup_executed"

    # Zone actions
    ZONE_CREATED = "zone_created"
    ZONE_UPDATED = "zone_updated"
    ZONE_DELETED = "zone_deleted"

    # Export compliance actions (NEM-3572)
    EXPORT_CREATED = "export_created"
    EXPORT_DOWNLOADED = "export_downloaded"
    EXPORT_EXPIRED = "export_expired"
    EXPORT_CANCELLED = "export_cancelled"


class AuditStatus(str, Enum):
    """Enumeration of audit log statuses."""

    SUCCESS = "success"
    FAILURE = "failure"


class AuditLog(Base):
    """Audit log model for tracking security-sensitive operations.

    Records detailed information about actions performed on the system,
    including who performed the action, when, and from where.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_audit_logs_timestamp", "timestamp"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_resource_type", "resource_type"),
        Index("idx_audit_logs_actor", "actor"),
        Index("idx_audit_logs_status", "status"),
        # Composite index for filtering by resource
        Index("idx_audit_logs_resource", "resource_type", "resource_id"),
        # BRIN index for time-series queries on timestamp (append-only chronological data)
        # Much smaller than B-tree (~1000x) and ideal for range queries on ordered timestamps
        Index(
            "ix_audit_logs_timestamp_brin",
            "timestamp",
            postgresql_using="brin",
        ),
        # CHECK constraint for status enum-like values
        CheckConstraint(
            "status IN ('success', 'failure')",
            name="ck_audit_logs_status",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, action={self.action!r}, "
            f"resource_type={self.resource_type!r}, actor={self.actor!r})>"
        )
