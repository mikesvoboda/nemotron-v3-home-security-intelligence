"""ONVIF device management and PTZ control service.

NEM-4207: Service for ONVIF device discovery, capability retrieval,
RTSP URL extraction, and PTZ control operations.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from backend.core.logging import get_logger
from backend.models.camera import Camera

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.core.redis import RedisClient

logger = get_logger(__name__)


# These are module-level references that get patched by tests
# Using this pattern allows the test patches to work correctly
try:
    from wsdiscovery import WSDiscovery
except ImportError:
    WSDiscovery = None  # type: ignore[misc, assignment]

try:
    from onvif import ONVIFCamera
except ImportError:
    ONVIFCamera = None  # type: ignore[misc, assignment]


class OnvifService:
    """ONVIF device management and PTZ control service.

    NEM-4207: Provides functionality for:
    - Device discovery via WS-Discovery
    - Capability retrieval
    - RTSP URL extraction
    - PTZ command execution
    - Preset navigation

    Example:
        async with get_session() as session:
            service = OnvifService(session, redis)
            devices = await service.discover_devices(
                subnet="192.168.1.0/24",
                timeout=5
            )
    """

    def __init__(
        self,
        session: AsyncSession,
        redis: RedisClient | None = None,
    ) -> None:
        """Initialize the ONVIF service.

        Args:
            session: Database session for camera lookups.
            redis: Optional Redis client for caching.
        """
        self.session = session
        self.redis = redis

    async def discover_devices(
        self,
        subnet: str,
        timeout: int = 10,
    ) -> list[dict[str, Any]]:
        """Discover ONVIF devices on the network using WS-Discovery.

        Args:
            subnet: Network subnet in CIDR notation (e.g., '192.168.1.0/24').
            timeout: Discovery timeout in seconds.

        Returns:
            List of discovered devices with their information.

        Raises:
            Exception: If discovery fails.
        """
        # Use module-level WSDiscovery (allows test patching)
        _WSDiscovery = WSDiscovery
        if _WSDiscovery is None:
            raise ImportError(
                "WSDiscovery library not installed. Install with: pip install wsdiscovery"
            )

        logger.info(
            "Starting ONVIF device discovery",
            extra={"subnet": subnet, "timeout": timeout},
        )

        wsd = _WSDiscovery()
        wsd.start()

        try:
            # Search for services (ONVIF devices)
            services = wsd.searchServices(timeout=timeout)

            devices = []
            for service in services:
                # Get service address (XAddrs)
                xaddrs = getattr(service, "xaddrs", None) or getattr(service, "XAddrs", "")
                if isinstance(xaddrs, list):
                    xaddrs = xaddrs[0] if xaddrs else ""

                # Filter for ONVIF devices (device service URL)
                if not xaddrs or "onvif" not in xaddrs.lower():
                    continue

                # Extract basic device info
                device_info: dict[str, Any] = {
                    "device_url": xaddrs,
                    "manufacturer": "Unknown",
                    "model": "Unknown",
                    "firmware_version": None,
                    "serial_number": None,
                    "hardware_id": None,
                }

                # Try to get additional info from service scopes
                scopes = getattr(service, "scopes", []) or []
                for scope in scopes:
                    scope_str = str(scope)
                    if "manufacturer" in scope_str.lower():
                        parts = scope_str.split("/")
                        if parts:
                            device_info["manufacturer"] = parts[-1]
                    elif "model" in scope_str.lower():
                        parts = scope_str.split("/")
                        if parts:
                            device_info["model"] = parts[-1]

                devices.append(device_info)

            logger.info(
                "ONVIF discovery completed",
                extra={"subnet": subnet, "devices_found": len(devices)},
            )

            return devices

        finally:
            wsd.stop()

    async def get_capabilities(
        self,
        camera_id: str,
    ) -> dict[str, Any]:
        """Get ONVIF device capabilities for a camera.

        Args:
            camera_id: Camera ID to get capabilities for.

        Returns:
            Dictionary with device capabilities.

        Raises:
            ValueError: If camera not found or not an ONVIF camera.
            Exception: If connection fails.
        """
        # Look up camera in database first (before checking library import)
        camera = await self._get_camera(camera_id)

        # Use module-level ONVIFCamera (allows test patching)
        _ONVIFCamera = ONVIFCamera
        if _ONVIFCamera is None:
            raise ImportError(
                "onvif-zeep library not installed. Install with: pip install onvif-zeep"
            )

        # Parse device URL from camera folder_path (assumes ONVIF URL stored)
        device_url = camera.folder_path
        if not device_url.startswith("http"):
            raise ValueError(f"Camera {camera_id} is not an ONVIF camera")

        # Connect to ONVIF device
        # Note: In production, credentials would be stored securely
        onvif_camera = _ONVIFCamera(device_url)

        # Get device information
        device_info = onvif_camera.devicemgmt.GetDeviceInformation()

        # Get capabilities
        capabilities = onvif_camera.devicemgmt.GetCapabilities()

        return {
            "manufacturer": getattr(device_info, "Manufacturer", "Unknown"),
            "model": getattr(device_info, "Model", "Unknown"),
            "firmware_version": getattr(device_info, "FirmwareVersion", None),
            "serial_number": getattr(device_info, "SerialNumber", None),
            "hardware_id": getattr(device_info, "HardwareId", None),
            "ptz_supported": hasattr(capabilities, "PTZ") and capabilities.PTZ is not None,
            "media_supported": hasattr(capabilities, "Media") and capabilities.Media is not None,
            "analytics_supported": hasattr(capabilities, "Analytics")
            and capabilities.Analytics is not None,
        }

    async def execute_ptz_command(
        self,
        camera_id: str,
        command: str,
        value: float,
        speed: float,
    ) -> bool:
        """Execute a PTZ command on the camera.

        Args:
            camera_id: Camera ID to control.
            command: PTZ command type (pan, tilt, zoom, stop).
            value: Movement value (-1.0 to 1.0).
            speed: Movement speed (0.0 to 1.0).

        Returns:
            True if command executed successfully.

        Raises:
            ValueError: If camera not found, invalid command, or value out of range.
            Exception: If connection fails.
        """
        # Validate command first
        valid_commands = {"pan", "tilt", "zoom", "stop"}
        if command not in valid_commands:
            raise ValueError(f"Invalid PTZ command: {command}")

        # Validate value range
        if not -1.0 <= value <= 1.0:
            raise ValueError("PTZ value must be between -1.0 and 1.0")

        # Look up camera (before checking library import)
        camera = await self._get_camera(camera_id)

        # Use module-level ONVIFCamera (allows test patching)
        _ONVIFCamera = ONVIFCamera
        if _ONVIFCamera is None:
            raise ImportError(
                "onvif-zeep library not installed. Install with: pip install onvif-zeep"
            )

        # Parse device URL
        device_url = camera.folder_path
        if not device_url.startswith("http"):
            raise ValueError(f"Camera {camera_id} is not an ONVIF camera")

        # Connect to ONVIF device
        onvif_camera = _ONVIFCamera(device_url)

        if command == "stop":
            # Stop all PTZ movement
            onvif_camera.ptz.Stop()
        else:
            # Build velocity vector based on command type
            velocity = {
                "PanTilt": {"x": 0.0, "y": 0.0},
                "Zoom": {"x": 0.0},
            }

            if command == "pan":
                velocity["PanTilt"]["x"] = value * speed
            elif command == "tilt":
                velocity["PanTilt"]["y"] = value * speed
            elif command == "zoom":
                velocity["Zoom"]["x"] = value * speed

            # Execute continuous move
            onvif_camera.ptz.ContinuousMove(velocity)

        logger.info(
            "PTZ command executed",
            extra={
                "camera_id": camera_id,
                "command": command,
                "value": value,
                "speed": speed,
            },
        )

        return True

    async def get_rtsp_url_from_device(
        self,
        device_url: str,
        username: str,
        password: str,
    ) -> str:
        """Extract RTSP URL from an ONVIF device.

        Args:
            device_url: ONVIF device service URL.
            username: Device username.
            password: Device password.

        Returns:
            RTSP stream URL.

        Raises:
            ValueError: If no media profiles found.
            Exception: If connection fails.
        """
        # Use module-level ONVIFCamera (allows test patching)
        _ONVIFCamera = ONVIFCamera
        if _ONVIFCamera is None:
            raise ImportError(
                "onvif-zeep library not installed. Install with: pip install onvif-zeep"
            )

        # Connect to ONVIF device with credentials
        onvif_camera = _ONVIFCamera(device_url, username, password)

        # Get media profiles
        profiles = onvif_camera.media.GetProfiles()

        if not profiles:
            raise ValueError("No media profiles found on device")

        # Use first profile
        profile = profiles[0]

        # Get stream URI
        stream_uri = onvif_camera.media.GetStreamUri(
            ProfileToken=profile.token,
            StreamSetup={"Stream": "RTP-Unicast", "Transport": {"Protocol": "RTSP"}},
        )

        return str(stream_uri.Uri)

    async def get_presets(
        self,
        camera_id: str,
    ) -> list[dict[str, Any]]:
        """Get available PTZ presets for a camera.

        Args:
            camera_id: Camera ID to get presets for.

        Returns:
            List of preset dictionaries with token and name.

        Raises:
            ValueError: If camera not found.
            Exception: If connection fails.
        """
        # Look up camera first (before checking library import)
        camera = await self._get_camera(camera_id)

        # Use module-level ONVIFCamera (allows test patching)
        _ONVIFCamera = ONVIFCamera
        if _ONVIFCamera is None:
            raise ImportError(
                "onvif-zeep library not installed. Install with: pip install onvif-zeep"
            )

        # Parse device URL
        device_url = camera.folder_path
        if not device_url.startswith("http"):
            raise ValueError(f"Camera {camera_id} is not an ONVIF camera")

        # Connect to ONVIF device
        onvif_camera = _ONVIFCamera(device_url)

        # Get presets
        presets = onvif_camera.ptz.GetPresets()

        return [
            {
                "token": preset.token,
                "name": getattr(preset, "Name", None),
            }
            for preset in presets
        ]

    async def goto_preset(
        self,
        camera_id: str,
        preset_token: str,
    ) -> bool:
        """Navigate camera to a PTZ preset position.

        Args:
            camera_id: Camera ID to control.
            preset_token: Preset token to navigate to.

        Returns:
            True if navigation started successfully.

        Raises:
            ValueError: If camera not found.
            Exception: If connection fails or preset invalid.
        """
        # Look up camera first (before checking library import)
        camera = await self._get_camera(camera_id)

        # Use module-level ONVIFCamera (allows test patching)
        _ONVIFCamera = ONVIFCamera
        if _ONVIFCamera is None:
            raise ImportError(
                "onvif-zeep library not installed. Install with: pip install onvif-zeep"
            )

        # Parse device URL
        device_url = camera.folder_path
        if not device_url.startswith("http"):
            raise ValueError(f"Camera {camera_id} is not an ONVIF camera")

        # Connect to ONVIF device
        onvif_camera = _ONVIFCamera(device_url)

        # Go to preset
        onvif_camera.ptz.GotoPreset(PresetToken=preset_token)

        logger.info(
            "PTZ preset navigation started",
            extra={
                "camera_id": camera_id,
                "preset_token": preset_token,
            },
        )

        return True

    async def _get_camera(self, camera_id: str) -> Camera:
        """Look up a camera by ID.

        Args:
            camera_id: Camera ID to look up.

        Returns:
            Camera model instance.

        Raises:
            ValueError: If camera not found.
        """
        # Execute the query - handle both sync mocks and async session
        execute_result = self.session.execute(select(Camera).where(Camera.id == camera_id))

        # If the result is a coroutine (real async session), await it
        if inspect.iscoroutine(execute_result):
            result = await execute_result
        else:
            result = execute_result

        camera: Camera | None = result.scalar_one_or_none()

        if camera is None:
            raise ValueError(f"Camera {camera_id} not found")

        return camera
