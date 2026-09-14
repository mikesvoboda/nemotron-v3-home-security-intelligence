"""PrometheusAlert model for storing Alertmanager alerts.

This model stores alerts received from Prometheus Alertmanager for history
tracking. Alerts are stored when received via the webhook endpoint and
also broadcast via WebSocket for real-time frontend updates.

NEM-3122: Phase 3.1 - Alertmanager webhook receiver for Prometheus alerts.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.time_utils import utc_now

from .camera import Base


class PrometheusAlertStatus(str, enum.Enum):
    """Status of a Prometheus alert."""

    FIRING = "firing"
    RESOLVED = "resolved"


class PrometheusAlert(Base):
    """Prometheus alert model for storing Alertmanager webhook alerts.

    Alerts are stored with their original fingerprint for deduplication,
    labels for filtering, and annotations for display purposes.

    Attributes:
        id: Unique auto-incrementing identifier
        fingerprint: Alertmanager fingerprint for deduplication
        status: Alert status (firing or resolved)
        labels: JSON dict of alert labels (alertname, severity, instance, etc.)
        annotations: JSON dict of alert annotations (summary, description)
        starts_at: When the alert started firing (from Alertmanager)
        ends_at: When the alert was resolved (from Alertmanager, null if still firing)
        received_at: When the alert was received by the backend
    """

    __tablename__ = "prometheus_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[PrometheusAlertStatus] = mapped_column(
        Enum(
            PrometheusAlertStatus,
            name="prometheus_alert_status_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    labels: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    annotations: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Indexes for common queries
    __table_args__ = (
        # Index for filtering by status
        Index("idx_prometheus_alerts_status", "status"),
        # Index for time-based queries
        Index("idx_prometheus_alerts_starts_at", "starts_at"),
        Index("idx_prometheus_alerts_received_at", "received_at"),
        # BRIN index for time-series queries on received_at (append-only chronological data)
        Index(
            "ix_prometheus_alerts_received_at_brin",
            "received_at",
            postgresql_using="brin",
        ),
        # Partial index for firing alerts (dashboard queries)
        Index(
            "idx_prometheus_alerts_firing",
            "status",
            postgresql_where=text("status = 'firing'"),
        ),
        # GIN index on labels for JSON queries (filter by alertname, severity, etc.)
        Index(
            "idx_prometheus_alerts_labels_gin",
            "labels",
            postgresql_using="gin",
        ),
    )

    def __repr__(self) -> str:
        alertname = self.labels.get("alertname", "unknown")
        return (
            f"<PrometheusAlert(id={self.id!r}, fingerprint={self.fingerprint!r}, "
            f"alertname={alertname!r}, status={self.status!r})>"
        )

    @property
    def alertname(self) -> str:
        """Get the alertname from labels."""
        return self.labels.get("alertname", "unknown")

    @property
    def severity(self) -> str:
        """Get the severity from labels."""
        return self.labels.get("severity", "info")

    @property
    def summary(self) -> str:
        """Get the summary from annotations."""
        return self.annotations.get("summary", "")

    @property
    def description(self) -> str:
        """Get the description from annotations."""
        return self.annotations.get("description", "")
