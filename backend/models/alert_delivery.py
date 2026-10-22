"""Recipient, RecipientChannel, and NotificationDelivery models for alert delivery.

This module defines the B4.2 delivery data model: who receives alert notifications
(recipients), through which channels (recipient channels), and the per-alert delivery
records (notification deliveries) that the delivery worker claims, sends, and retries.

Model notes:
    - The "Household" recipient owns the existing quiet_hours_periods rows; the
      recorded upgrade seeds it and points existing quiet-hours rows at it.
    - Webhook channel signing secrets are NOT stored in plaintext. The secret is
      generated at channel creation, returned to the caller once, and persisted
      Fernet-encrypted under the SECRETS_MASTER_KEY from settings.
    - NotificationDelivery rows are written in the same transaction as the alert
      that produced them ("the alert and its pending deliveries are written in one
      transaction").
"""

from datetime import datetime
from enum import StrEnum
from uuid import uuid7

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.time_utils import utc_now

from .camera import Base


class DeliveryChannelKind(StrEnum):
    """Channel kinds a recipient can receive alert notifications through."""

    BROWSER = "browser"
    EMAIL = "email"
    WEBHOOK = "webhook"
    WEBPUSH = "webpush"


class DeliveryStatus(StrEnum):
    """Lifecycle of a single delivery attempt record.

    pending -> sent (email/webhook) or broadcast (browser)
            -> retrying -> sent | failed (after max attempts)
            -> suppressed (quiet hours, recorded not sent)
            -> expired (browser row unclaimed past the expiry window)
    """

    PENDING = "pending"
    SENT = "sent"
    BROADCAST = "broadcast"
    RETRYING = "retrying"
    FAILED = "failed"
    SUPPRESSED = "suppressed"
    EXPIRED = "expired"


class Recipient(Base):
    """A person (or shared household identity) that receives alert notifications.

    The "Household" recipient is seeded by the recorded upgrade and owns the
    existing quiet_hours_periods rows. Per-person recipients opt out of alerts by
    being disabled rather than deleted, so delivery history stays referentially
    intact.

    Attributes:
        id: Unique identifier (UUID7).
        name: Human-readable recipient name (unique).
        enabled: Whether this recipient currently receives alerts.
        user_id: Optional link to an authenticated user (SET NULL on delete).
        critical_breaks_quiet: Whether critical-severity alerts bypass quiet hours
            for this recipient.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        channels: The delivery channels configured for this recipient.
    """

    __tablename__ = "recipients"
    __table_args__ = (
        UniqueConstraint("name", name="uq_recipients_name"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid7()),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    user_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    critical_breaks_quiet: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    channels: Mapped[list["RecipientChannel"]] = relationship(
        back_populates="recipient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class RecipientChannel(Base):
    """A delivery channel (browser/email/webhook/webpush) for one recipient.

    Attributes:
        id: Unique identifier (UUID7).
        recipient_id: Owning recipient (CASCADE on delete).
        kind: Channel kind (browser|email|webhook|webpush).
        target: Channel address — email address, webhook URL, or device id.
        push_subscription: WebPush subscription keys (endpoint/keys), webpush only.
        on_local_network: Webhook-only flag allowing private/unique-local targets;
            metadata and link-local addresses stay blocked for every channel.
        include_names: Whether gallery/identity names may appear in payloads
            (default off — payloads say "a known person").
        enabled: Whether this channel currently receives alerts.
        last_success_at: Timestamp of the last successful send.
        last_error: Last send error text (also used for fail-closed reasons).
        signing_secret_encrypted: Fernet-encrypted webhook signing secret; the
            plaintext is shown once at creation and never stored.
        signing_secret_hint: Short display hint for the stored secret (prefix).
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "recipient_channels"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('browser','email','webhook','webpush')",
            name="ck_recipient_channels_kind",
        ),
        Index("idx_recipient_channels_recipient", "recipient_id", "enabled"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid7()),
    )

    recipient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("recipients.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[DeliveryChannelKind] = mapped_column(
        Enum(
            DeliveryChannelKind,
            name="delivery_channel_kind",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    target: Mapped[str] = mapped_column(String(2048), nullable=False)
    push_subscription: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    on_local_network: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    include_names: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    signing_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    signing_secret_hint: Mapped[str | None] = mapped_column(String(16), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    recipient: Mapped["Recipient"] = relationship(back_populates="channels")


class NotificationDelivery(Base):
    """One planned delivery of one alert through one recipient channel.

    Written in the same transaction as the alert. The delivery worker claims
    pending/retrying rows past their next_attempt_at under a lease (SKIP LOCKED),
    sends outside any transaction, and records the outcome.

    Attributes:
        id: Unique identifier (UUID7).
        alert_id: The alert being delivered (CASCADE on alert delete).
        recipient_id: Target recipient.
        channel_id: Target channel.
        kind: Denormalised channel kind for history reads without a join.
        status: Delivery lifecycle state.
        attempts: Send attempts made so far.
        next_attempt_at: Lease/claim gate — worker only claims rows at or past it.
        last_error: Last failure text.
        idempotency_key: Unique per-send key (webhook header / email Message-ID).
        sent_at: Timestamp of the successful send.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','sent','broadcast','retrying','failed',"
            "'suppressed','expired')",
            name="ck_notification_deliveries_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_notification_deliveries_attempts"),
        Index(
            "idx_notification_deliveries_claim",
            "status",
            "next_attempt_at",
        ),
        Index("idx_notification_deliveries_alert", "alert_id"),
        Index("idx_notification_deliveries_recipient", "recipient_id", "created_at"),
        UniqueConstraint("idempotency_key", name="uq_notification_deliveries_idem"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid7()),
    )

    alert_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
    )
    recipient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("recipients.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("recipient_channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)

    status: Mapped[DeliveryStatus] = mapped_column(
        Enum(
            DeliveryStatus,
            name="delivery_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=DeliveryStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    alert: Mapped["Alert"] = relationship()
    recipient: Mapped["Recipient"] = relationship()
    channel: Mapped["RecipientChannel"] = relationship()
