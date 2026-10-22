"""Browser channel adapter (B4.2).

Browser rows are NOT sent by the worker on first pass: the pipeline publishes
the alert to connected WebSocket clients right after commit. The worker's job
for browser rows is the REPUBLISH ladder — a browser delivery still ``pending``
after 15 s is re-broadcast (the notification tag dedups client-side), and one
still ``pending`` after 5 minutes expires.

``send`` therefore performs one re-broadcast: it returns success when the
broadcast reached at least one connected client.
"""

from __future__ import annotations

from typing import Any, Protocol

from backend.models.alert_delivery import DeliveryChannelKind
from backend.services.alerting.channels.base import Channel, DeliveryTask, SendResult


class AlertBroadcaster(Protocol):
    """The slice of EventBroadcaster the adapter needs."""

    async def broadcast_alert(self, alert_data: dict[str, Any], event_type: str) -> int:
        """Broadcast an alert payload; returns the number of clients reached."""
        ...


class BrowserChannel(Channel):
    """Re-publish an alert to connected dashboard clients."""

    kind = DeliveryChannelKind.BROWSER

    def __init__(self, broadcaster: AlertBroadcaster) -> None:
        self._broadcaster = broadcaster

    async def send(self, task: DeliveryTask) -> SendResult:
        reached = await self._broadcaster.broadcast_alert(
            dict(task.payload), "alert_created"
        )
        if reached <= 0:
            # Nobody is listening — the row stays pending and the ladder retries.
            return SendResult(success=False, error="no_connected_clients")
        return SendResult(success=True, meta={"reached": reached})


__all__ = ["AlertBroadcaster", "BrowserChannel"]
