"""Shared domain models for container orchestration.

This package provides the canonical definitions for dataclasses, enums, and
the service registry used across all container orchestration modules.

Instead of duplicating definitions in each module, import from here:

    from backend.services.orchestrator import (
        # Enums
        ServiceCategory,
        ContainerServiceStatus,
        # Models
        ManagedService,
        ServiceConfig,
        # Registry
        ServiceRegistry,
        get_service_registry,
        reset_service_registry,
    )

Modules in this package:
    enums: Re-exports ServiceCategory and ContainerServiceStatus from API schemas
    models: ManagedService and ServiceConfig dataclasses
    registry: ServiceRegistry with Redis persistence
"""

from backend.services.orchestrator.enums import ContainerServiceStatus, ServiceCategory
from backend.services.orchestrator.models import ManagedService, ServiceConfig
from backend.services.orchestrator.registry import (
    REDIS_KEY_PREFIX,
    ServiceRegistry,
    get_service_registry,
    reset_service_registry,
)

__all__ = [
    "REDIS_KEY_PREFIX",
    "ContainerServiceStatus",
    "ManagedService",
    "ServiceCategory",
    "ServiceConfig",
    "ServiceRegistry",
    "get_service_registry",
    "reset_service_registry",
]
