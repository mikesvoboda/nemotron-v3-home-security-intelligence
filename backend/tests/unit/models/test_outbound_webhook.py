"""Unit tests for the OutboundWebhook / WebhookDelivery models.

Anchored on the B4.2 / ruling-310 column: ``on_local_network`` is the
per-webhook allowance the destination policy reads (private and unique-local
targets admitted when set; metadata and link-local addresses stay blocked for
every webhook regardless). Also pins the shapes the webhook service and the
delivery worker rely on: defaults, FK cascade, retry fields, event-type and
status enums.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect as sa_inspect

from backend.models.outbound_webhook import (
    OutboundWebhook,
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookEventType,
)

pytestmark = pytest.mark.unit


class TestOutboundWebhookColumns:
    def test_on_local_network_defaults_off_and_is_not_nullable(self) -> None:
        """Ruling 310: the SQL-level contract the destination policy reads.

        Asserted on the mapped column (nullable + default), not on instances —
        ``mapped_column`` defaults apply at flush, not construction, so the
        column object is the honest witness.
        """
        col = sa_inspect(OutboundWebhook).columns["on_local_network"]
        assert col.nullable is False
        assert col.default is not None and col.default.arg is False

    def test_on_local_network_is_a_boolean_column(self) -> None:
        col = sa_inspect(OutboundWebhook).columns["on_local_network"]
        assert col.type.__class__.__name__ == "BOOLEAN" or "BOOLEAN" in str(col.type).upper()

    def test_url_is_required_and_long(self) -> None:
        col = sa_inspect(OutboundWebhook).columns["url"]
        assert col.nullable is False
        assert col.type.length == 2048

    def test_event_types_column_is_array(self) -> None:
        col = sa_inspect(OutboundWebhook).columns["event_types"]
        assert "ARRAY" in str(col.type).upper() or col.type.__class__.__name__ == "ARRAY"

    def test_retry_fields_are_check_constrained(self) -> None:
        names = {c.name for c in OutboundWebhook.__table__.constraints}
        assert "ck_webhook_max_retries" in names
        assert "ck_webhook_retry_delay" in names
        # Defaults live on the columns (max 10 retries, >=1s spacing).
        retries = sa_inspect(OutboundWebhook).columns["max_retries"]
        assert retries.default is not None and retries.default.arg == 4


class TestWebhookDeliveryColumns:
    def test_status_enum_lifecycle(self) -> None:
        assert {s.value for s in WebhookDeliveryStatus} >= {
            "pending",
            "success",
            "failed",
            "retrying",
        }

    def test_delivery_links_to_webhook_with_cascade(self) -> None:
        fk = next(fk for fk in sa_inspect(WebhookDelivery).columns["webhook_id"].foreign_keys)
        assert fk.column.table.name == "outbound_webhooks"
        assert "CASCADE" in (fk.ondelete or "")

    def test_event_type_values_include_alert_fired(self) -> None:
        assert {e.value for e in WebhookEventType} >= {
            "alert_fired",
            "alert_dismissed",
            "alert_acknowledged",
        }
