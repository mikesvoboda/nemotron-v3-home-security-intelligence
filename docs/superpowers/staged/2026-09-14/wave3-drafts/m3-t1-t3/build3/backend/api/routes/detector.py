"""API routes for detector management.

Endpoints for listing, switching, and checking health of object detectors
at runtime (NEM-3692).

Endpoints:
    GET  /api/system/detectors           - List all registered detectors
    GET  /api/system/detectors/active    - Get currently active detector
    PUT  /api/system/detectors/active    - Switch active detector
    GET  /api/system/detectors/{type}    - Get specific detector config
    GET  /api/system/detectors/{type}/health - Check detector health
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.api.schemas.detector import (
    DetectorHealthResponse,
    DetectorInfoResponse,
    DetectorListResponse,
    SwitchDetectorRequest,
    SwitchDetectorResponse,
)
from backend.core.logging import get_logger
from backend.services.detector_registry import get_detector_registry

logger = get_logger(__name__)

router = APIRouter(prefix="/system/detectors", tags=["detectors"])


@router.get(
    "",
    response_model=DetectorListResponse,
    summary="List all registered detectors",
    description="Returns a list of all registered object detectors with their "
    "configuration and status. Optionally includes health status for each detector.",
)
async def list_detectors(
    include_health: bool = Query(
        False,
        description="Include health status for each detector (slower)",
    ),
) -> DetectorListResponse:
    """List all registered object detectors.

    Args:
        include_health: If True, perform health checks on all detectors

    Returns:
        DetectorListResponse with all registered detectors
    """
    registry = get_detector_registry()
    detector_infos = registry.list_detectors()

    # Convert to response models
    detectors = [
        DetectorInfoResponse(
            detector_type=info.detector_type,
            display_name=info.display_name,
            url=info.url,
            enabled=info.enabled,
            is_active=info.is_active,
            model_version=info.model_version,
            description=info.description,
        )
        for info in detector_infos
    ]

    response = DetectorListResponse(
        detectors=detectors,
        active_detector=registry.active_detector,
        health_checked=False,
    )

    # Optionally include health status
    if include_health:
        # Check health of all detectors (results logged internally)
        await registry.check_all_health()

        # Mark that health was checked
        response.health_checked = True

        logger.debug(
            "Listed detectors with health check",
            extra={
                "detector_count": len(detectors),
                "health_checked": True,
            },
        )

    return response


@router.get(
    "/active",
    response_model=DetectorInfoResponse,
    summary="Get active detector",
    description="Returns the configuration of the currently active object detector.",
)
async def get_active_detector() -> DetectorInfoResponse:
    """Get the currently active detector configuration.

    Returns:
        DetectorInfoResponse for the active detector

    Raises:
        HTTPException 500: If no detector is configured as active
    """
    registry = get_detector_registry()

    try:
        config = registry.get_active_config()
    except ValueError as e:
        logger.error(f"No active detector configured: {e}")
        raise HTTPException(
            status_code=500,
            detail="No active detector configured. This is a configuration error.",
        ) from e

    return DetectorInfoResponse(
        detector_type=config.detector_type,
        display_name=config.display_name,
        url=config.url,
        enabled=config.enabled,
        is_active=True,
        model_version=config.model_version,
        description=config.description,
    )


@router.put(
    "/active",
    response_model=SwitchDetectorResponse,
    summary="Switch active detector",
    description="Switch to a different object detector. By default, validates that "
    "the target detector is healthy before switching. Use force=True to skip health check.",
)
async def switch_detector(
    request: SwitchDetectorRequest,
) -> SwitchDetectorResponse:
    """Switch to a different active detector.

    Args:
        request: SwitchDetectorRequest with target detector type

    Returns:
        SwitchDetectorResponse with status of the switch operation

    Raises:
        HTTPException 400: If detector type is invalid, disabled, or unhealthy
    """
    registry = get_detector_registry()

    try:
        status = await registry.switch_detector(
            request.detector_type,
            force=request.force,
        )
    except ValueError as e:
        logger.warning(
            f"Failed to switch detector: {e}",
            extra={
                "target_detector": request.detector_type,
                "force": request.force,
            },
        )
        raise HTTPException(status_code=400, detail=str(e)) from e

    config = registry.get_active_config()

    logger.info(
        f"Switched to detector: {request.detector_type}",
        extra={
            "detector_type": request.detector_type,
            "forced": request.force,
        },
    )

    return SwitchDetectorResponse(
        detector_type=config.detector_type,
        display_name=config.display_name,
        message=f"Successfully switched to {config.display_name}",
        healthy=status.healthy,
    )


@router.get(
    "/{detector_type}",
    response_model=DetectorInfoResponse,
    summary="Get detector configuration",
    description="Returns the configuration for a specific detector type.",
)
async def get_detector_config(detector_type: str) -> DetectorInfoResponse:
    """Get configuration for a specific detector.

    Args:
        detector_type: Type identifier of the detector

    Returns:
        DetectorInfoResponse for the requested detector

    Raises:
        HTTPException 404: If detector type is not found
    """
    registry = get_detector_registry()

    try:
        config = registry.get_config(detector_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return DetectorInfoResponse(
        detector_type=config.detector_type,
        display_name=config.display_name,
        url=config.url,
        enabled=config.enabled,
        is_active=(detector_type == registry.active_detector),
        model_version=config.model_version,
        description=config.description,
    )


@router.get(
    "/{detector_type}/health",
    response_model=DetectorHealthResponse,
    summary="Check detector health",
    description="Performs a health check on a specific detector and returns the status.",
)
async def check_detector_health(detector_type: str) -> DetectorHealthResponse:
    """Check health status of a specific detector.

    Args:
        detector_type: Type identifier of the detector

    Returns:
        DetectorHealthResponse with health status

    Raises:
        HTTPException 404: If detector type is not found
    """
    registry = get_detector_registry()

    # First verify the detector exists
    try:
        registry.get_config(detector_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    status = await registry.check_health(detector_type)

    return DetectorHealthResponse(
        detector_type=status.detector_type,
        healthy=status.healthy,
        model_loaded=status.model_loaded,
        latency_ms=status.latency_ms,
        error_message=status.error_message,
    )
