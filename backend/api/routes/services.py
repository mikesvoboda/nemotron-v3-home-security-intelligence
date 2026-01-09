"""REST API endpoints for container orchestrator service management.

Provides endpoints for listing managed services and performing manual actions
like restart, enable, disable, and start.
"""

from datetime import UTC, datetime
from typing import Any, Protocol

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.schemas.services import (
    CategorySummary,
    ContainerServiceStatus,
    ServiceActionResponse,
    ServiceCategory,
    ServiceInfo,
    ServicesResponse,
)

router = APIRouter(prefix="/api/system/services", tags=["services"])


class ManagedServiceProtocol(Protocol):
    """Protocol defining the interface for a managed service."""

    name: str
    display_name: str
    category: ServiceCategory
    status: ContainerServiceStatus
    enabled: bool
    container_id: str | None
    image: str | None
    port: int
    failure_count: int
    restart_count: int
    last_restart_at: datetime | None


async def get_orchestrator(request: Request) -> Any:
    """Get orchestrator from app state.

    Args:
        request: FastAPI request object containing app state

    Returns:
        Container orchestrator instance

    Raises:
        HTTPException: 503 if orchestrator is not available
    """
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise HTTPException(503, "Container orchestrator not available")
    return orchestrator


def _calculate_uptime(service: ManagedServiceProtocol) -> int | None:
    """Calculate uptime in seconds from last_restart_at.

    Args:
        service: ManagedService instance

    Returns:
        Uptime in seconds if running, None otherwise
    """
    if service.status != ContainerServiceStatus.RUNNING:
        return None
    if service.last_restart_at:
        return int((datetime.now(UTC) - service.last_restart_at).total_seconds())
    return None


def _to_service_info(service: ManagedServiceProtocol) -> ServiceInfo:
    """Convert ManagedService to ServiceInfo response model.

    Args:
        service: ManagedService instance from orchestrator

    Returns:
        ServiceInfo schema for API response
    """
    return ServiceInfo(
        name=service.name,
        display_name=service.display_name,
        category=service.category,
        status=service.status,
        enabled=service.enabled,
        container_id=service.container_id[:12] if service.container_id else None,
        image=service.image,
        port=service.port,
        failure_count=service.failure_count,
        restart_count=service.restart_count,
        last_restart_at=service.last_restart_at,
        uptime_seconds=_calculate_uptime(service),
    )


def _build_category_summaries(services: list[ManagedServiceProtocol]) -> dict[str, CategorySummary]:
    """Build category summaries from service list.

    Args:
        services: List of ManagedService instances

    Returns:
        Dictionary mapping category names to CategorySummary objects
    """
    summaries: dict[str, CategorySummary] = {}

    for category in list(ServiceCategory):
        cat_services = [s for s in services if s.category == category]
        healthy = sum(1 for s in cat_services if s.status == ContainerServiceStatus.RUNNING)
        unhealthy = len(cat_services) - healthy
        summaries[category.value] = CategorySummary(
            total=len(cat_services),
            healthy=healthy,
            unhealthy=unhealthy,
        )

    return summaries


@router.get(
    "",
    response_model=ServicesResponse,
    responses={
        503: {"description": "Container orchestrator not available"},
        500: {"description": "Internal server error"},
    },
)
async def list_services(
    category: ServiceCategory | None = None,
    orchestrator: Any = Depends(get_orchestrator),
) -> ServicesResponse:
    """Get status of all managed services.

    Args:
        category: Optional filter by category (infrastructure, ai, monitoring)
        orchestrator: Container orchestrator instance (injected)

    Returns:
        List of services with status and category summaries.
    """
    all_services = orchestrator.get_all_services()

    filtered = [s for s in all_services if s.category == category] if category else all_services

    return ServicesResponse(
        services=[_to_service_info(s) for s in filtered],
        by_category=_build_category_summaries(all_services),
        timestamp=datetime.now(UTC),
    )


@router.post(
    "/{name}/restart",
    response_model=ServiceActionResponse,
    responses={
        400: {"description": "Bad request - Service is disabled"},
        404: {"description": "Service not found"},
        503: {"description": "Container orchestrator not available"},
        500: {"description": "Internal server error"},
    },
)
async def restart_service(
    name: str,
    orchestrator: Any = Depends(get_orchestrator),
) -> ServiceActionResponse:
    """Manually restart a service.

    Resets failure count (manual restart is intentional).

    Args:
        name: Service name to restart
        orchestrator: Container orchestrator instance (injected)

    Returns:
        Action result with updated service information

    Raises:
        HTTPException: 404 if service not found, 400 if service is disabled
    """
    service = orchestrator.get_service(name)
    if not service:
        raise HTTPException(404, f"Service '{name}' not found")

    if service.status == ContainerServiceStatus.DISABLED:
        raise HTTPException(400, f"Service '{name}' is disabled. Enable it first.")

    success = await orchestrator.restart_service(name, reset_failures=True)

    updated_service = orchestrator.get_service(name)
    return ServiceActionResponse(
        success=success,
        message=f"Service '{name}' restart initiated" if success else f"Failed to restart '{name}'",
        service=_to_service_info(updated_service),
    )


@router.post(
    "/{name}/enable",
    response_model=ServiceActionResponse,
    responses={
        404: {"description": "Service not found"},
        503: {"description": "Container orchestrator not available"},
        500: {"description": "Internal server error"},
    },
)
async def enable_service(
    name: str,
    orchestrator: Any = Depends(get_orchestrator),
) -> ServiceActionResponse:
    """Re-enable a disabled service.

    Resets failure count and allows self-healing to resume.

    Args:
        name: Service name to enable
        orchestrator: Container orchestrator instance (injected)

    Returns:
        Action result with updated service information

    Raises:
        HTTPException: 404 if service not found
    """
    service = orchestrator.get_service(name)
    if not service:
        raise HTTPException(404, f"Service '{name}' not found")

    success = await orchestrator.enable_service(name)

    updated_service = orchestrator.get_service(name)
    return ServiceActionResponse(
        success=success,
        message=f"Service '{name}' enabled" if success else f"Failed to enable '{name}'",
        service=_to_service_info(updated_service),
    )


@router.post(
    "/{name}/disable",
    response_model=ServiceActionResponse,
    responses={
        404: {"description": "Service not found"},
        503: {"description": "Container orchestrator not available"},
        500: {"description": "Internal server error"},
    },
)
async def disable_service(
    name: str,
    orchestrator: Any = Depends(get_orchestrator),
) -> ServiceActionResponse:
    """Manually disable a service.

    Prevents self-healing restarts.

    Args:
        name: Service name to disable
        orchestrator: Container orchestrator instance (injected)

    Returns:
        Action result with updated service information

    Raises:
        HTTPException: 404 if service not found
    """
    service = orchestrator.get_service(name)
    if not service:
        raise HTTPException(404, f"Service '{name}' not found")

    success = await orchestrator.disable_service(name)

    updated_service = orchestrator.get_service(name)
    return ServiceActionResponse(
        success=success,
        message=f"Service '{name}' disabled" if success else f"Failed to disable '{name}'",
        service=_to_service_info(updated_service),
    )


@router.post(
    "/{name}/start",
    response_model=ServiceActionResponse,
    responses={
        400: {"description": "Bad request - Service already running or disabled"},
        404: {"description": "Service not found"},
        503: {"description": "Container orchestrator not available"},
        500: {"description": "Internal server error"},
    },
)
async def start_service(
    name: str,
    orchestrator: Any = Depends(get_orchestrator),
) -> ServiceActionResponse:
    """Start a stopped service container.

    Args:
        name: Service name to start
        orchestrator: Container orchestrator instance (injected)

    Returns:
        Action result with updated service information

    Raises:
        HTTPException: 404 if service not found,
                       400 if service is already running or disabled
    """
    service = orchestrator.get_service(name)
    if not service:
        raise HTTPException(404, f"Service '{name}' not found")

    if service.status == ContainerServiceStatus.RUNNING:
        raise HTTPException(400, f"Service '{name}' is already running")

    if service.status == ContainerServiceStatus.DISABLED:
        raise HTTPException(400, f"Service '{name}' is disabled. Enable it first.")

    success = await orchestrator.start_service(name)

    updated_service = orchestrator.get_service(name)
    return ServiceActionResponse(
        success=success,
        message=f"Service '{name}' start initiated" if success else f"Failed to start '{name}'",
        service=_to_service_info(updated_service),
    )
