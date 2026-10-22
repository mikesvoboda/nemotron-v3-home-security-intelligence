"""Process-wide handle for the alert-delivery worker (B4.2).

The pipeline commits new delivery rows and should wake the worker immediately
(the poll interval is only the fallback). Importing the worker into the
pipeline module would invert the dependency (the worker imports channel
adapters, the pipeline must not know them), so main.py registers the running
worker here and the pipeline looks it up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.services.alerting.worker import NotificationDeliveryWorker

_worker: NotificationDeliveryWorker | None = None


def set_delivery_worker(worker: NotificationDeliveryWorker) -> None:
    """Register the running worker (main lifespan calls this once)."""
    global _worker
    _worker = worker


def get_delivery_worker() -> NotificationDeliveryWorker | None:
    """The registered worker, or None before startup (or in tests)."""
    return _worker


def wake_delivery_worker() -> None:
    """Wake the worker if one is registered; harmless when none is."""
    worker = _worker
    if worker is not None:
        worker.wake()


def reset_delivery_worker() -> None:
    """Clear the registration (shutdown / tests)."""
    global _worker
    _worker = None
