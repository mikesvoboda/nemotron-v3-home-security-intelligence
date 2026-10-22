"""Channel adapters for alert delivery (B4.2)."""

from backend.services.alerting.channels.base import Channel, DeliveryTask, SendResult
from backend.services.alerting.channels.browser import BrowserChannel
from backend.services.alerting.channels.email import EmailChannel
from backend.services.alerting.channels.webhook import WebhookChannel

__all__ = [
    "BrowserChannel",
    "Channel",
    "DeliveryTask",
    "EmailChannel",
    "SendResult",
    "WebhookChannel",
]
