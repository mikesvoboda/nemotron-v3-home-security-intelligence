"""Unit tests for backend.services.alerting.channels.browser (B4.2).

The browser channel is the republish leg of the ladder: a browser delivery
still pending after 15 s is re-broadcast, and one pending past 5 minutes
expires. ``send`` succeeds only when the broadcast reached a client.
"""

from __future__ import annotations

from typing import Any

from backend.models.alert_delivery import DeliveryChannelKind
from backend.services.alerting.channels.base import DeliveryTask
from backend.services.alerting.channels.browser import BrowserChannel


def _task() -> DeliveryTask:
    return DeliveryTask(
        delivery_id="d-1",
        channel_id="c-1",
        channel_kind=DeliveryChannelKind.BROWSER,
        recipient_id="r-1",
        idempotency_key="idem-1",
        payload={"title": "t", "severity": "high", "summary": "s"},
        include_names=False,
    )


class _Broadcaster:
    """Records broadcasts; returns a configured client count."""

    def __init__(self, reached: int) -> None:
        self.reached = reached
        self.calls: list[dict[str, Any]] = []

    async def broadcast_alert(self, alert_data: dict[str, Any], event_type: Any) -> int:
        self.calls.append({"alert_data": alert_data, "event_type": event_type})
        return self.reached


class TestBrowserChannel:
    async def test_send_succeeds_when_clients_reached(self) -> None:
        b = _Broadcaster(reached=2)
        result = await BrowserChannel(b).send(_task())
        assert result.success is True
        assert result.meta == {"reached": 2}
        # The republish is the "created" shape, as the WebSocketAlertEventType
        # member — a bare string would fail EventBroadcaster's per-type
        # payload validation.
        assert b.calls[0]["event_type"].value == "alert_created"
        assert b.calls[0]["alert_data"]["title"] == "t"

    async def test_send_fails_when_nobody_is_listening(self) -> None:
        b = _Broadcaster(reached=0)
        result = await BrowserChannel(b).send(_task())
        assert result.success is False
        assert result.error == "no_connected_clients"

    async def test_kind_is_browser(self) -> None:
        assert BrowserChannel.kind is DeliveryChannelKind.BROWSER
