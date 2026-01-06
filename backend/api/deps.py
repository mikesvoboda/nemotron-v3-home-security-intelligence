"""FastAPI dependencies for dependency injection.

This module provides dependency functions that can be used with FastAPI's
Depends() mechanism to inject common services and resources into route handlers.

Example:
    from fastapi import Depends
    from backend.api.deps import get_orchestrator

    @router.get("/services")
    async def list_services(
        orchestrator: ContainerOrchestrator = Depends(get_orchestrator),
    ):
        return orchestrator.get_all_services()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import HTTPException, Request

if TYPE_CHECKING:
    from backend.services.container_orchestrator import ContainerOrchestrator


async def get_orchestrator(request: Request) -> ContainerOrchestrator:
    """Get the container orchestrator from app state.

    This dependency retrieves the ContainerOrchestrator instance that was
    initialized during application startup and stored in app.state.

    Args:
        request: FastAPI Request object containing app state

    Returns:
        ContainerOrchestrator instance

    Raises:
        HTTPException: 503 Service Unavailable if orchestrator is not available
    """
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="Container orchestrator not available",
        )
    # Import at runtime to avoid circular imports

    return cast("ContainerOrchestrator", orchestrator)
