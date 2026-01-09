"""API route handlers."""

from .alerts import alerts_instance_router
from .alerts import router as alerts_router
from .audit import router as audit_router
from .entities import router as entities_router
from .logs import router as logs_router
from .notification_preferences import router as notification_preferences_router
from .rum import router as rum_router
from .services import router as services_router
from .zones import router as zones_router

__all__ = [
    "alerts_instance_router",
    "alerts_router",
    "audit_router",
    "entities_router",
    "logs_router",
    "notification_preferences_router",
    "rum_router",
    "services_router",
    "zones_router",
]
