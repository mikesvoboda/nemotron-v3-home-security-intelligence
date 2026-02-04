"""API routes for ONVIF camera management.

NEM-4207: Endpoints for ONVIF device discovery, capabilities, PTZ control,
and preset navigation.

NEM-4885 Phase 3: Wire PTZ HTTP endpoints to expose the PTZ helper functions
as proper FastAPI routes that the frontend can call.

Endpoints:
- POST /api/cameras/onvif/discover - Discover ONVIF devices on the network
- GET /api/cameras/{camera_id}/onvif/capabilities - Get device capabilities
- POST /api/cameras/{camera_id}/onvif/ptz - Execute PTZ command
- POST /api/cameras/{camera_id}/onvif/ptz/stop - Stop PTZ movement
- GET /api/cameras/{camera_id}/onvif/presets - List PTZ presets
- POST /api/cameras/{camera_id}/onvif/presets/{preset_token} - Go to preset
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, status

from backend.api.dependencies import DbSession, OnvifServiceDep, get_camera_or_404
from backend.api.schemas.onvif import (
    OnvifCapabilitiesResponse,
    OnvifDiscoveryResponse,
    PTZCommand,
    PTZCommandResponse,
    PTZGotoPresetResponse,
    PTZPresetsResponse,
    PTZStopResponse,
)
from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.services.onvif_service import OnvifService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/cameras", tags=["onvif"])


async def _verify_camera_exists(camera_id: str, camera_service: Any) -> None:
    """Verify camera exists, raising HTTPException 404 if not found."""
    try:
        await camera_service.get_camera(camera_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


def _handle_onvif_value_error(e: ValueError) -> HTTPException:
    """Map ValueError to appropriate HTTPException based on error message."""
    error_msg = str(e)
    error_lower = error_msg.lower()

    if "invalid ptz command" in error_lower or "ptz value" in error_lower:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid PTZ command: {error_msg}",
        )
    if "invalid preset" in error_lower:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid preset token: {error_msg}",
        )
    if "not an onvif" in error_lower:
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Camera is not an ONVIF device: {error_msg}",
        )
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)


def _handle_onvif_error(e: Exception, camera_id: str, operation: str) -> HTTPException:
    """Handle general ONVIF errors, logging and returning 503."""
    error_msg = str(e)

    # Check for invalid preset token in general exceptions
    if "invalid preset token" in error_msg.lower():
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid preset token: {error_msg}",
        )

    logger.error(
        f"Failed to {operation}",
        extra={"camera_id": camera_id, "error": error_msg},
        exc_info=True,
    )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Device unreachable: {e}",
    )


async def discover_onvif_devices(
    subnet: str,
    onvif_service: OnvifService,
    timeout: int = 10,
) -> OnvifDiscoveryResponse:
    """Discover ONVIF devices on the network.

    Args:
        subnet: Network subnet in CIDR notation (e.g., '192.168.1.0/24').
        onvif_service: ONVIF service instance (injected).
        timeout: Discovery timeout in seconds (default: 10).

    Returns:
        OnvifDiscoveryResponse with discovered devices and count.

    Raises:
        HTTPException: 500 if discovery fails.
    """
    try:
        devices = await onvif_service.discover_devices(subnet=subnet, timeout=timeout)
        return OnvifDiscoveryResponse(devices=devices, count=len(devices))
    except Exception as e:
        logger.error(
            "ONVIF device discovery failed",
            extra={"subnet": subnet, "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Discovery failed: {e}",
        ) from e


async def get_device_capabilities(
    camera_id: str,
    onvif_service: OnvifService,
    camera_service: Any,
) -> OnvifCapabilitiesResponse:
    """Get ONVIF device capabilities for a camera.

    Args:
        camera_id: Camera ID to get capabilities for.
        onvif_service: ONVIF service instance (injected).
        camera_service: Camera service instance (injected).

    Returns:
        OnvifCapabilitiesResponse with device capabilities.

    Raises:
        HTTPException: 404 if camera not found, 409 if not ONVIF, 503 if unreachable.
    """
    await _verify_camera_exists(camera_id, camera_service)

    try:
        capabilities = await onvif_service.get_capabilities(camera_id=camera_id)
        return OnvifCapabilitiesResponse.model_validate(dict(capabilities))
    except ValueError as e:
        raise _handle_onvif_value_error(e) from e
    except Exception as e:
        raise _handle_onvif_error(e, camera_id, "get ONVIF capabilities") from e


async def execute_ptz_command(
    camera_id: str,
    command: str,
    value: float,
    speed: float,
    onvif_service: OnvifService,
    camera_service: Any,
) -> PTZCommandResponse:
    """Execute a PTZ command on the camera.

    Args:
        camera_id: Camera ID to control.
        command: PTZ command type (pan, tilt, zoom, stop).
        value: Movement value (-1.0 to 1.0).
        speed: Movement speed (0.0 to 1.0).
        onvif_service: ONVIF service instance (injected).
        camera_service: Camera service instance (injected).

    Returns:
        PTZCommandResponse with success status and command info.

    Raises:
        HTTPException: 400 if invalid, 404 if not found, 409 if not ONVIF, 503 if unreachable.
    """
    await _verify_camera_exists(camera_id, camera_service)

    try:
        result = await onvif_service.execute_ptz_command(
            camera_id=camera_id, command=command, value=value, speed=speed
        )
        return PTZCommandResponse(success=result, command=command, value=value, speed=speed)
    except ValueError as e:
        raise _handle_onvif_value_error(e) from e
    except Exception as e:
        raise _handle_onvif_error(e, camera_id, "execute PTZ command") from e


async def get_ptz_presets(
    camera_id: str,
    onvif_service: OnvifService,
    camera_service: Any,
) -> PTZPresetsResponse:
    """Get available PTZ presets for a camera.

    Args:
        camera_id: Camera ID to get presets for.
        onvif_service: ONVIF service instance (injected).
        camera_service: Camera service instance (injected).

    Returns:
        PTZPresetsResponse with presets list and count.

    Raises:
        HTTPException: 404 if not found, 409 if not ONVIF, 503 if unreachable.
    """
    await _verify_camera_exists(camera_id, camera_service)

    try:
        presets = await onvif_service.get_presets(camera_id=camera_id)
        return PTZPresetsResponse(presets=presets, count=len(presets))
    except ValueError as e:
        raise _handle_onvif_value_error(e) from e
    except Exception as e:
        raise _handle_onvif_error(e, camera_id, "get PTZ presets") from e


async def goto_ptz_preset(
    camera_id: str,
    preset_token: str,
    onvif_service: OnvifService,
    camera_service: Any,
) -> PTZGotoPresetResponse:
    """Navigate camera to a PTZ preset position.

    Args:
        camera_id: Camera ID to control.
        preset_token: Preset token to navigate to.
        onvif_service: ONVIF service instance (injected).
        camera_service: Camera service instance (injected).

    Returns:
        PTZGotoPresetResponse with success status and preset info.

    Raises:
        HTTPException: 400 if invalid, 404 if not found, 409 if not ONVIF, 503 if unreachable.
    """
    await _verify_camera_exists(camera_id, camera_service)

    try:
        result = await onvif_service.goto_preset(camera_id=camera_id, preset_token=preset_token)
        return PTZGotoPresetResponse(success=result, preset_token=preset_token)
    except ValueError as e:
        raise _handle_onvif_value_error(e) from e
    except Exception as e:
        raise _handle_onvif_error(e, camera_id, "go to PTZ preset") from e


# =============================================================================
# HTTP Route Handlers (NEM-4885 Phase 3)
# =============================================================================
# These routes expose the PTZ helper functions as HTTP endpoints that match
# what the frontend expects in ptzApi.ts.
# =============================================================================


@router.post(
    "/{camera_id}/onvif/ptz",
    summary="Execute PTZ command",
    response_model=PTZCommandResponse,
    responses={
        200: {"description": "PTZ command executed successfully"},
        400: {"description": "Invalid PTZ command or value"},
        404: {"description": "Camera not found"},
        409: {"description": "Camera is not an ONVIF device"},
        503: {"description": "Device unreachable"},
    },
)
async def ptz_command_endpoint(
    camera_id: str,
    command: PTZCommand,
    db: DbSession,
    onvif_service: OnvifServiceDep,
) -> PTZCommandResponse:
    """Execute a PTZ command (pan, tilt, zoom, stop) on a camera.

    This endpoint controls PTZ cameras via ONVIF protocol. The frontend uses
    this for the PTZ control D-pad and zoom buttons.

    Args:
        camera_id: ID of the camera to control
        command: PTZ command with type, value, and speed
        db: Database session for camera lookup
        onvif_service: ONVIF service for PTZ control

    Returns:
        PTZCommandResponse with success status and executed command details

    Raises:
        HTTPException: 400 if invalid command/value, 404 if camera not found,
                      409 if not ONVIF device, 503 if device unreachable
    """
    # Verify camera exists using the database directly
    await get_camera_or_404(camera_id, db)

    try:
        result = await onvif_service.execute_ptz_command(
            camera_id=camera_id,
            command=command.command,
            value=command.value,
            speed=command.speed,
        )
        return PTZCommandResponse(
            success=result,
            command=command.command,
            value=command.value,
            speed=command.speed,
        )
    except ValueError as e:
        raise _handle_onvif_value_error(e) from e
    except Exception as e:
        raise _handle_onvif_error(e, camera_id, "execute PTZ command") from e


@router.post(
    "/{camera_id}/onvif/ptz/stop",
    summary="Stop PTZ movement",
    response_model=PTZStopResponse,
    responses={
        200: {"description": "PTZ movement stopped"},
        404: {"description": "Camera not found"},
        409: {"description": "Camera is not an ONVIF device"},
        503: {"description": "Device unreachable"},
    },
)
async def ptz_stop_endpoint(
    camera_id: str,
    db: DbSession,
    onvif_service: OnvifServiceDep,
) -> PTZStopResponse:
    """Stop all PTZ movement on a camera.

    Convenience endpoint that sends a stop command without requiring
    a request body. The frontend calls this when the user releases
    the PTZ controls.

    Args:
        camera_id: ID of the camera to stop
        db: Database session for camera lookup
        onvif_service: ONVIF service for PTZ control

    Returns:
        PTZStopResponse with success status

    Raises:
        HTTPException: 404 if camera not found, 409 if not ONVIF device,
                      503 if device unreachable
    """
    await get_camera_or_404(camera_id, db)

    try:
        result = await onvif_service.execute_ptz_command(
            camera_id=camera_id,
            command="stop",
            value=0.0,
            speed=0.0,
        )
        return PTZStopResponse(success=result)
    except ValueError as e:
        raise _handle_onvif_value_error(e) from e
    except Exception as e:
        raise _handle_onvif_error(e, camera_id, "stop PTZ movement") from e


@router.get(
    "/{camera_id}/onvif/presets",
    summary="Get PTZ presets",
    response_model=PTZPresetsResponse,
    responses={
        200: {"description": "List of PTZ presets"},
        404: {"description": "Camera not found"},
        409: {"description": "Camera is not an ONVIF device"},
        503: {"description": "Device unreachable"},
    },
)
async def get_presets_endpoint(
    camera_id: str,
    db: DbSession,
    onvif_service: OnvifServiceDep,
) -> PTZPresetsResponse:
    """Get available PTZ presets for a camera.

    Retrieves the list of saved PTZ positions (presets) configured on
    the camera. Each preset has a token and optional name.

    Args:
        camera_id: ID of the camera to get presets for
        db: Database session for camera lookup
        onvif_service: ONVIF service for preset retrieval

    Returns:
        PTZPresetsResponse with presets list and count

    Raises:
        HTTPException: 404 if camera not found, 409 if not ONVIF device,
                      503 if device unreachable
    """
    await get_camera_or_404(camera_id, db)

    try:
        presets = await onvif_service.get_presets(camera_id=camera_id)
        return PTZPresetsResponse(presets=presets, count=len(presets))
    except ValueError as e:
        raise _handle_onvif_value_error(e) from e
    except Exception as e:
        raise _handle_onvif_error(e, camera_id, "get PTZ presets") from e


@router.post(
    "/{camera_id}/onvif/presets/{preset_token}",
    summary="Go to PTZ preset",
    response_model=PTZGotoPresetResponse,
    responses={
        200: {"description": "Camera moving to preset position"},
        400: {"description": "Invalid preset token"},
        404: {"description": "Camera not found"},
        409: {"description": "Camera is not an ONVIF device"},
        503: {"description": "Device unreachable"},
    },
)
async def goto_preset_endpoint(
    camera_id: str,
    preset_token: str,
    db: DbSession,
    onvif_service: OnvifServiceDep,
) -> PTZGotoPresetResponse:
    """Navigate camera to a saved PTZ preset position.

    Moves the camera to a previously saved preset position. The preset_token
    is obtained from the GET /presets endpoint.

    Args:
        camera_id: ID of the camera to control
        preset_token: Token identifying the preset position
        db: Database session for camera lookup
        onvif_service: ONVIF service for PTZ control

    Returns:
        PTZGotoPresetResponse with success status and preset token

    Raises:
        HTTPException: 400 if invalid preset token, 404 if camera not found,
                      409 if not ONVIF device, 503 if device unreachable
    """
    await get_camera_or_404(camera_id, db)

    try:
        result = await onvif_service.goto_preset(
            camera_id=camera_id,
            preset_token=preset_token,
        )
        return PTZGotoPresetResponse(success=result, preset_token=preset_token)
    except ValueError as e:
        raise _handle_onvif_value_error(e) from e
    except Exception as e:
        raise _handle_onvif_error(e, camera_id, "go to PTZ preset") from e


@router.get(
    "/{camera_id}/onvif/capabilities",
    summary="Get ONVIF device capabilities",
    response_model=OnvifCapabilitiesResponse,
    responses={
        200: {"description": "Device capabilities"},
        404: {"description": "Camera not found"},
        409: {"description": "Camera is not an ONVIF device"},
        503: {"description": "Device unreachable"},
    },
)
async def get_capabilities_endpoint(
    camera_id: str,
    db: DbSession,
    onvif_service: OnvifServiceDep,
) -> OnvifCapabilitiesResponse:
    """Get ONVIF device capabilities for a camera.

    Retrieves device information and capability flags including:
    - Manufacturer, model, firmware version
    - PTZ support
    - Media support
    - Analytics support

    Args:
        camera_id: ID of the camera to get capabilities for
        db: Database session for camera lookup
        onvif_service: ONVIF service for capability retrieval

    Returns:
        OnvifCapabilitiesResponse with device info and capability flags

    Raises:
        HTTPException: 404 if camera not found, 409 if not ONVIF device,
                      503 if device unreachable
    """
    await get_camera_or_404(camera_id, db)

    try:
        capabilities = await onvif_service.get_capabilities(camera_id=camera_id)
        return OnvifCapabilitiesResponse.model_validate(dict(capabilities))
    except ValueError as e:
        raise _handle_onvif_value_error(e) from e
    except Exception as e:
        raise _handle_onvif_error(e, camera_id, "get ONVIF capabilities") from e
