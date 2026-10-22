"""Unit tests for the B4.2 alert-delivery models.

Tests cover:
- DeliveryChannelKind / DeliveryStatus enums (lifecycle spelling)
- Recipient / RecipientChannel / NotificationDelivery column shapes the
  worker and planner depend on (defaults, FKs, denormalised kind)
- The uniqueness + check constraints the upgrade relies on
- Recipient.quiet_periods viewonly relationship mapping
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect as sa_inspect

from backend.models.alert_delivery import (
    DeliveryChannelKind,
    DeliveryStatus,
    NotificationDelivery,
    Recipient,
    RecipientChannel,
)

pytestmark = pytest.mark.unit


class TestDeliveryEnums:
    def test_channel_kind_values(self) -> None:
        assert {k.value for k in DeliveryChannelKind} == {
            "browser",
            "email",
            "webhook",
            "webpush",
        }

    def test_status_lifecycle_values(self) -> None:
        assert {s.value for s in DeliveryStatus} == {
            "pending",
            "sent",
            "broadcast",
            "retrying",
            "failed",
            "suppressed",
            "expired",
        }


class TestRecipientColumns:
    def test_defaults_via_column_info(self) -> None:
        name = "seed-recipient"
        rec = Recipient(id="r-test", name=name)
        assert rec.enabled is True
        assert rec.critical_breaks_quiet is True

    def test_quiet_periods_relationship_is_mapped(self) -> None:
        mapper = sa_inspect(Recipient)
        assert "quiet_periods" in mapper.relationships
        assert "channels" in mapper.relationships

    def test_tablename(self) -> None:
        assert Recipient.__tablename__ == "recipients"


class TestRecipientChannelColumns:
    def test_defaults(self) -> None:
        ch = RecipientChannel(
            id="c-test",
            recipient_id="r-test",
            kind=DeliveryChannelKind.EMAIL,
            target="a@b.c",
        )
        assert ch.on_local_network is False
        assert ch.include_names is False
        assert ch.enabled is True
        assert ch.last_success_at is None
        assert ch.signing_secret_encrypted is None

    def test_check_constraint_names(self) -> None:
        names = {c.name for c in RecipientChannel.__table__.constraints}
        assert "ck_recipient_channels_kind" in names

    def test_tablename(self) -> None:
        assert RecipientChannel.__tablename__ == "recipient_channels"


class TestNotificationDeliveryColumns:
    def test_tablename_and_indexes(self) -> None:
        assert NotificationDelivery.__tablename__ == "notification_deliveries"
        idx_names = {i.name for i in NotificationDelivery.__table__.indexes}
        assert "idx_notification_deliveries_claim" in idx_names
        assert "idx_notification_deliveries_alert" in idx_names

    def test_unique_idempotency_key(self) -> None:
        names = {c.name for c in NotificationDelivery.__table__.constraints}
        assert "uq_notification_deliveries_idem" in names

    def test_check_constraints(self) -> None:
        names = {c.name for c in NotificationDelivery.__table__.constraints}
        assert "ck_notification_deliveries_status" in names
        assert "ck_notification_deliveries_attempts" in names

    def test_relationship_names(self) -> None:
        mapper = sa_inspect(NotificationDelivery)
        names = {rel.key for rel in mapper.relationships}
        assert {"alert", "recipient", "channel"} <= names
