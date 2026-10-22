"""Channel adapter contract for alert delivery (B4.2).

A channel adapter turns a planned delivery + alert payload into an actual send.
Adapters never touch the database: the worker owns claim/lease/retry state and
hands each adapter the resolved signing secret (already decrypted) and the
redacted payload.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from backend.models.alert_delivery import DeliveryChannelKind


@dataclass(frozen=True)
class SendResult:
    """Outcome of one send attempt."""

    success: bool
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeliveryTask:
    """Everything an adapter needs to send one delivery.

    Built by the worker from the delivery row + alert + channel record.
    """

    delivery_id: str
    channel_id: str
    channel_kind: DeliveryChannelKind
    recipient_id: str
    idempotency_key: str
    payload: dict[str, Any]
    include_names: bool
    on_local_network: bool = False
    target: str = ""
    signing_secret: str | None = None  # plaintext, resolved at send time only
    push_subscription: dict[str, Any] | None = None


class Channel(ABC):
    """Base class for channel adapters."""

    kind: DeliveryChannelKind

    @abstractmethod
    async def send(self, task: DeliveryTask) -> SendResult:
        """Send one delivery. No DB access; returns the outcome for the worker to record."""

    def close(self) -> None:
        """Release resources (HTTP clients). Default: nothing to close."""


__all__ = ["Channel", "DeliveryTask", "SendResult"]
