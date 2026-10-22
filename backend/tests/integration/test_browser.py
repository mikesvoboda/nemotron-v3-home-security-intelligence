"""Integration tests for the browser republish channel (B4.2).

The browser adapter's job in the worker is the republish ladder: re-broadcast
the alert frame the pipeline already published on commit. This file drives the
adapter ↔ broadcast-fabric seam end-to-end: a real ``EventBroadcaster`` over a
Redis pub/sub fake, the payload shaped exactly like the pipeline's
``alert.to_dict(for_websocket=True)`` frame (the schema-validated shape), and
the two outcomes the ladder keys off — nobody listening (the row stays pending)
and at least one subscriber reached (success with the subscriber count).

The DB side of browser rows (pending → expired ladder) is pinned in the
worker's claim tests; the payload-vs-frame shape distinction is asserted here
because it is what makes the republish pass validation at all.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid7

import pytest

from backend.models.alert import Alert
from backend.models.alert_delivery import DeliveryChannelKind
from backend.services.alerting.channels.base import DeliveryTask
from backend.services.alerting.channels.browser import BrowserChannel
from backend.services.event_broadcaster import EventBroadcaster

# asyncio_mode=auto (pyproject) makes async tests run under pytest-asyncio.

CHANNEL = "home_security_alerts"


class FakeRedis:
    """The pub/sub surface EventBroadcaster consumes.

    Subscribers register inboxes; ``publish`` appends the wire message to each
    and returns how many received it — the number ``broadcast_alert`` reports
    and the ladder keys off.
    """

    def __init__(self, subscribers: int = 0) -> None:
        self.subscribers = subscribers
        self.published: list[str] = []

    async def publish(self, channel: str, message: Any) -> int:
        self.published.append(message if isinstance(message, str) else json.dumps(message))
        return self.subscribers


def _task(payload: dict[str, Any]) -> DeliveryTask:
    return DeliveryTask(
        delivery_id="d-browser-1",
        channel_id="ch-browser",
        channel_kind=DeliveryChannelKind.BROWSER,
        recipient_id="rec-1",
        idempotency_key="idem-browser-1",
        payload=payload,
        include_names=False,
    )


def _make_alert() -> Alert:
    # Construction-time defaults fill id (the repo's __init__ idiom) but NOT
    # created_at (that default applies at flush, and the websocket schema
    # requires the ISO string) — so the test supplies the timestamps.
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return Alert(
        id=str(uuid7()),
        event_id=990001,
        severity="medium",
        status="open",
        dedup_key="browser_test:dedup",
        created_at=now,
        updated_at=now,
    )


class TestBrowserRepublishSeam:
    async def test_frame_reaches_a_subscriber(self) -> None:
        """One subscriber → success; the frame carries the validated alert."""
        redis = FakeRedis(subscribers=1)
        broadcaster = EventBroadcaster(redis, channel_name=CHANNEL)
        alert = _make_alert()
        channel = BrowserChannel(broadcaster)
        result = await channel.send(_task(alert.to_dict(for_websocket=True)))
        assert result.success is True
        assert result.meta is not None and result.meta["reached"] == 1
        # What crossed the wire is the schema-validated message shape.
        assert len(redis.published) == 1
        frame = json.loads(redis.published[0])
        assert frame["type"] == "alert_created"
        assert frame["data"]["id"] == alert.id
        assert frame["data"]["severity"] == "medium"

    async def test_no_subscribers_returns_no_connected_clients(self) -> None:
        redis = FakeRedis(subscribers=0)
        broadcaster = EventBroadcaster(redis, channel_name=CHANNEL)
        channel = BrowserChannel(broadcaster)
        result = await channel.send(_task(_make_alert().to_dict(for_websocket=True)))
        assert result.success is False
        assert result.error == "no_connected_clients"

    async def test_republish_rejects_a_delivery_payload_shape(self) -> None:
        """The delivery payload shape is NOT a valid alert frame.

        The browser task builder must hand the adapter the pipeline's
        ``to_dict(for_websocket=True)`` shape; passing the delivery payload
        fails loudly (ValueError from schema validation), which is what keeps
        a mis-wired builder from silently broadcasting junk to clients.
        """
        redis = FakeRedis(subscribers=1)
        broadcaster = EventBroadcaster(redis, channel_name=CHANNEL)
        channel = BrowserChannel(broadcaster)
        with pytest.raises(ValueError):
            await channel.send(_task({"alert_id": "x", "title": "t", "summary": "s"}))
