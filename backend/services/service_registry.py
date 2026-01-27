"""Service Registry with Redis persistence for Container Orchestrator.

This module re-exports the ServiceRegistry, ManagedService, and related utilities
from the shared orchestrator module. The canonical implementations now live in
backend.services.orchestrator.

For new code, import directly from the orchestrator module:
    from backend.services.orchestrator import (
        ManagedService,
        ServiceRegistry,
        get_service_registry,
        reset_service_registry,
        REDIS_KEY_PREFIX,
    )

This module is maintained for backward compatibility with existing imports:
    from backend.services.service_registry import (
        ManagedService,
        ServiceRegistry,
        get_service_registry,
        reset_service_registry,
        REDIS_KEY_PREFIX,
    )

Example usage:
    from backend.services.service_registry import get_service_registry, ManagedService
    from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory

    registry = await get_service_registry()

    # Register a service
    service = ManagedService(
        name="ai-yolo26",
        display_name="YOLO26v2",
        container_id="abc123",
        image="ghcr.io/.../yolo26:latest",
        port=8095,
        health_endpoint="/health",
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.RUNNING,
    )
    registry.register(service)

    # Update status
    registry.update_status("ai-yolo26", ContainerServiceStatus.UNHEALTHY)

    # Persist to Redis
    await registry.persist_state("ai-yolo26")

    # Load from Redis on restart
    await registry.load_all_state()
"""

# Re-export everything from the canonical orchestrator module
from backend.services.orchestrator import (
    REDIS_KEY_PREFIX,
    ManagedService,
    ServiceRegistry,
    get_service_registry,
    reset_service_registry,
)

__all__ = [
    "REDIS_KEY_PREFIX",
    "ManagedService",
    "ServiceRegistry",
    "get_service_registry",
    "reset_service_registry",
]
