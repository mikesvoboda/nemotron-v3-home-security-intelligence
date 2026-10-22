"""REST API endpoints for container orchestrator service management.

Provides endpoints for listing managed services and performing manual actions
like restart, enable, disable, and start.
"""

import inspect
import logging
from datetime import UTC, datetime
from typing import Any, Protocol

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.routes.auth import get_current_admin_user
from backend.api.schemas.services import (
    CategorySummary,
    ContainerServiceStatus,
    ServiceActionResponse,
    ServiceCategory,
    ServiceInfo,
    ServicesResponse,
)
from backend.core.database import get_session_factory
from backend.models.audit import AuditAction, AuditLog, AuditStatus
from backend.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system/services", tags=["services"])

# B4.11 (4n-status.md §Shape -> Service controls): only these four services may be restarted.
RESTARTABLE_SERVICES: frozenset[str] = frozenset({"ai-gateway", "ai-vlm", "redis", "postgres"})


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
        raise HTTPException(503, "Container orchestrator not available (engine not available)")
    return orchestrator


async def get_admin_orchestrator(
    request: Request,
    _admin: User = Depends(get_current_admin_user),
) -> Any:
    """Resolve `get_current_admin_user` FIRST, then `get_orchestrator` (4n-status.md)."""
    override = request.app.dependency_overrides.get(get_orchestrator)
    if override is not None:
        res = override()
        return await res if inspect.isawaitable(res) else res
    return await get_orchestrator(request)


async def _resolve_orchestrator(request: Request | None, explicit: Any = None) -> Any:
    """Resolve the orchestrator AFTER `get_current_admin_user` has succeeded."""
    if (
        explicit is not None
        and not isinstance(explicit, Request)
        and not hasattr(explicit, "dependency")
    ):
        return explicit
    if request is None:
        raise HTTPException(503, "Container orchestrator not available (engine not available)")
    override = request.app.dependency_overrides.get(get_orchestrator)
    if override is not None:
        res = override()
        return await res if inspect.isawaitable(res) else res
    return await get_orchestrator(request)


async def _record_service_audit(
    *,
    actor: str,
    service_name: str,
    step: str,
    status_val: str = AuditStatus.SUCCESS.value,
    extra_details: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    """Commit one AuditLog row in its own short-lived database session (4n-status.md)."""
    try:
        factory = get_session_factory()
    except RuntimeError:
        return

    ip_address = None
    user_agent = None
    if request is not None:
        if request.client is not None:
            ip_address = request.client.host
        user_agent = request.headers.get("user-agent")

    details: dict[str, Any] = {
        "step": step,
        "service": service_name,
        "username": actor,
    }
    if extra_details:
        details.update(extra_details)

    try:
        async with factory() as session:
            row = AuditLog(
                timestamp=datetime.now(UTC),
                action=AuditAction.SERVICE_RESTART.value,
                resource_type="service",
                resource_id=service_name,
                actor=actor,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details,
                status=status_val,
            )
            session.add(row)
            await session.commit()
    except Exception as exc:
        logger.warning(f"Failed to write service audit row ({step}) for {service_name}: {exc}")


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
        401: {"description": "Not authenticated"},
        403: {"description": "Admin session required"},
        404: {"description": "Service not found"},
        503: {"description": "Container orchestrator not available"},
        500: {"description": "Internal server error"},
    },
)
async def restart_service(
    name: str,
    request: Request = None,  # type: ignore[assignment]
    current_user: User = Depends(get_current_admin_user),
    orchestrator: Any = Depends(get_admin_orchestrator),
) -> ServiceActionResponse:
    """Manually restart an allowed service (`ai-gateway`, `ai-vlm`, `redis`, `postgres`).

    Requires an admin session (`get_current_admin_user`); API keys are refused with 403.
    Commits a 'restart requested' audit row before calling the engine, and records the
    outcome in a fresh session afterward (B4.11 / 4n-status.md).
    """
    actor = getattr(current_user, "username", None) or "admin"
    orch = await _resolve_orchestrator(request, orchestrator)

    if name not in RESTARTABLE_SERVICES:
        raise HTTPException(404, f"Service '{name}' not found")

    service = orch.get_service(name)
    if not service:
        raise HTTPException(404, f"Service '{name}' not found")

    # Step 1 audit: commit "restart requested" BEFORE calling the container engine
    await _record_service_audit(
        actor=actor,
        service_name=name,
        step="restart requested",
        status_val=AuditStatus.SUCCESS.value,
        request=request,
    )

    try:
        success = await orch.restart_service(name, reset_failures=True)
    except Exception as exc:
        await _record_service_audit(
            actor=actor,
            service_name=name,
            step="restart failed",
            status_val=AuditStatus.FAILURE.value,
            extra_details={"error": str(exc)},
            request=request,
        )
        raise

    # Step 2 audit: record the outcome in a fresh session
    await _record_service_audit(
        actor=actor,
        service_name=name,
        step="restart completed" if success else "restart failed",
        status_val=AuditStatus.SUCCESS.value if success else AuditStatus.FAILURE.value,
        extra_details={"success": bool(success)},
        request=request,
    )

    updated_service = orch.get_service(name)
    return ServiceActionResponse(
        success=success,
        message=f"Service '{name}' restart initiated" if success else f"Failed to restart '{name}'",
        service=_to_service_info(updated_service),
    )


@router.post(
    "/{name}/enable",
    response_model=ServiceActionResponse,
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Admin session required"},
        404: {"description": "Service not found"},
        503: {"description": "Container orchestrator not available"},
        500: {"description": "Internal server error"},
    },
)
async def enable_service(
    name: str,
    request: Request = None,  # type: ignore[assignment]
    _current_user: User = Depends(get_current_admin_user),
    orchestrator: Any = Depends(get_admin_orchestrator),
) -> ServiceActionResponse:
    """Re-enable a disabled service (guarded by `get_current_admin_user` until F4.8 retires it)."""
    orch = await _resolve_orchestrator(request, orchestrator)
    service = orch.get_service(name)
    if not service:
        raise HTTPException(404, f"Service '{name}' not found")

    success = await orch.enable_service(name)

    updated_service = orch.get_service(name)
    return ServiceActionResponse(
        success=success,
        message=f"Service '{name}' enabled" if success else f"Failed to enable '{name}'",
        service=_to_service_info(updated_service),
    )


@router.post(
    "/{name}/disable",
    response_model=ServiceActionResponse,
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Admin session required"},
        404: {"description": "Service not found"},
        503: {"description": "Container orchestrator not available"},
        500: {"description": "Internal server error"},
    },
)
async def disable_service(
    name: str,
    request: Request = None,  # type: ignore[assignment]
    _current_user: User = Depends(get_current_admin_user),
    orchestrator: Any = Depends(get_admin_orchestrator),
) -> ServiceActionResponse:
    """Manually disable a service (guarded by `get_current_admin_user` until F4.8 retires it)."""
    orch = await _resolve_orchestrator(request, orchestrator)
    service = orch.get_service(name)
    if not service:
        raise HTTPException(404, f"Service '{name}' not found")

    success = await orch.disable_service(name)

    updated_service = orch.get_service(name)
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
        401: {"description": "Not authenticated"},
        403: {"description": "Admin session required"},
        404: {"description": "Service not found"},
        503: {"description": "Container orchestrator not available"},
        500: {"description": "Internal server error"},
    },
)
async def start_service(
    name: str,
    request: Request = None,  # type: ignore[assignment]
    _current_user: User = Depends(get_current_admin_user),
    orchestrator: Any = Depends(get_admin_orchestrator),
) -> ServiceActionResponse:
    """Start a stopped service container (guarded by `get_current_admin_user` until F4.8 retires it)."""
    orch = await _resolve_orchestrator(request, orchestrator)
    service = orch.get_service(name)
    if not service:
        raise HTTPException(404, f"Service '{name}' not found")

    if service.status == ContainerServiceStatus.RUNNING:
        raise HTTPException(400, f"Service '{name}' is already running")

    if service.status == ContainerServiceStatus.DISABLED:
        raise HTTPException(400, f"Service '{name}' is disabled. Enable it first.")

    success = await orch.start_service(name)

    updated_service = orch.get_service(name)
    return ServiceActionResponse(
        success=success,
        message=f"Service '{name}' start initiated" if success else f"Failed to start '{name}'",
        service=_to_service_info(updated_service),
    )
