"""API routes for ONVIF camera management.

NEM-4207: Endpoints for ONVIF device discovery, capabilities, PTZ control,
and preset navigation.

Endpoints:
- POST /api/cameras/onvif/discover - Discover ONVIF devices on the network
- GET /api/cameras/{camera_id}/onvif/capabilities - Get device capabilities
- POST /api/cameras/{camera_id}/onvif/ptz - Execute PTZ command
- GET /api/cameras/{camera_id}/onvif/presets - List PTZ presets
- POST /api/cameras/{camera_id}/onvif/presets/{preset_token} - Go to preset
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from backend.core.logging import get_logger

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
    onvif_service: Any,
    timeout: int = 10,
) -> dict[str, Any]:
    """Discover ONVIF devices on the network.

    Args:
        subnet: Network subnet in CIDR notation (e.g., '192.168.1.0/24').
        onvif_service: ONVIF service instance (injected).
        timeout: Discovery timeout in seconds (default: 10).

    Returns:
        Dictionary with discovered devices and count.

    Raises:
        HTTPException: 500 if discovery fails.
    """
    try:
        devices = await onvif_service.discover_devices(subnet=subnet, timeout=timeout)
        return {"devices": devices, "count": len(devices)}
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
    onvif_service: Any,
    camera_service: Any,
) -> dict[str, Any]:
    """Get ONVIF device capabilities for a camera.

    Args:
        camera_id: Camera ID to get capabilities for.
        onvif_service: ONVIF service instance (injected).
        camera_service: Camera service instance (injected).

    Returns:
        Dictionary with device capabilities.

    Raises:
        HTTPException: 404 if camera not found, 409 if not ONVIF, 503 if unreachable.
    """
    await _verify_camera_exists(camera_id, camera_service)

    try:
        capabilities = await onvif_service.get_capabilities(camera_id=camera_id)
        return dict(capabilities)  # type: ignore[arg-type]
    except ValueError as e:
        raise _handle_onvif_value_error(e) from e
    except Exception as e:
        raise _handle_onvif_error(e, camera_id, "get ONVIF capabilities") from e


async def execute_ptz_command(
    camera_id: str,
    command: str,
    value: float,
    speed: float,
    onvif_service: Any,
    camera_service: Any,
) -> dict[str, Any]:
    """Execute a PTZ command on the camera.

    Args:
        camera_id: Camera ID to control.
        command: PTZ command type (pan, tilt, zoom, stop).
        value: Movement value (-1.0 to 1.0).
        speed: Movement speed (0.0 to 1.0).
        onvif_service: ONVIF service instance (injected).
        camera_service: Camera service instance (injected).

    Returns:
        Dictionary with success status and command info.

    Raises:
        HTTPException: 400 if invalid, 404 if not found, 409 if not ONVIF, 503 if unreachable.
    """
    await _verify_camera_exists(camera_id, camera_service)

    try:
        result = await onvif_service.execute_ptz_command(
            camera_id=camera_id, command=command, value=value, speed=speed
        )
        return {"success": result, "command": command, "value": value, "speed": speed}
    except ValueError as e:
        raise _handle_onvif_value_error(e) from e
    except Exception as e:
        raise _handle_onvif_error(e, camera_id, "execute PTZ command") from e


async def get_ptz_presets(
    camera_id: str,
    onvif_service: Any,
    camera_service: Any,
) -> dict[str, Any]:
    """Get available PTZ presets for a camera.

    Args:
        camera_id: Camera ID to get presets for.
        onvif_service: ONVIF service instance (injected).
        camera_service: Camera service instance (injected).

    Returns:
        Dictionary with presets list and count.

    Raises:
        HTTPException: 404 if not found, 409 if not ONVIF, 503 if unreachable.
    """
    await _verify_camera_exists(camera_id, camera_service)

    try:
        presets = await onvif_service.get_presets(camera_id=camera_id)
        return {"presets": presets, "count": len(presets)}
    except ValueError as e:
        raise _handle_onvif_value_error(e) from e
    except Exception as e:
        raise _handle_onvif_error(e, camera_id, "get PTZ presets") from e


async def goto_ptz_preset(
    camera_id: str,
    preset_token: str,
    onvif_service: Any,
    camera_service: Any,
) -> dict[str, Any]:
    """Navigate camera to a PTZ preset position.

    Args:
        camera_id: Camera ID to control.
        preset_token: Preset token to navigate to.
        onvif_service: ONVIF service instance (injected).
        camera_service: Camera service instance (injected).

    Returns:
        Dictionary with success status and preset info.

    Raises:
        HTTPException: 400 if invalid, 404 if not found, 409 if not ONVIF, 503 if unreachable.
    """
    await _verify_camera_exists(camera_id, camera_service)

    try:
        result = await onvif_service.goto_preset(camera_id=camera_id, preset_token=preset_token)
        return {"success": result, "preset_token": preset_token}
    except ValueError as e:
        raise _handle_onvif_value_error(e) from e
    except Exception as e:
        raise _handle_onvif_error(e, camera_id, "go to PTZ preset") from e
