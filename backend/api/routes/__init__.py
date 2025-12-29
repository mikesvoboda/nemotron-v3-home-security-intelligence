"""API route handlers."""

from .alerts import router as alerts_router
from .audit import router as audit_router
from .logs import router as logs_router
from .zones import router as zones_router

__all__ = ["alerts_router", "audit_router", "logs_router", "zones_router"]
