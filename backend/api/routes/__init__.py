"""API route handlers."""

from .alerts import alerts_instance_router
from .alerts import router as alerts_router
from .audit import router as audit_router
from .calibration import router as calibration_router
from .entities import router as entities_router
from .exports import router as exports_router
from .feedback import router as feedback_router
from .jobs import router as jobs_router
from .logs import router as logs_router
from .notification_preferences import router as notification_preferences_router
from .rum import router as rum_router
from .services import router as services_router
from .summaries import router as summaries_router
from .zones import router as zones_router

__all__ = [
    "alerts_instance_router",
    "alerts_router",
    "audit_router",
    "calibration_router",
    "entities_router",
    "exports_router",
    "feedback_router",
    "jobs_router",
    "logs_router",
    "notification_preferences_router",
    "rum_router",
    "services_router",
    "summaries_router",
    "zones_router",
]
