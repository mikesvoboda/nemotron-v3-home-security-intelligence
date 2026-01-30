"""ONVIF device management and PTZ control service.

NEM-4207: Service for ONVIF device discovery, capability retrieval,
RTSP URL extraction, and PTZ control operations.

Phase 2 enhancements (NEM-4388):
- RTSP URL extraction during discovery
- Manufacturer/model from ONVIF scopes
- IP/port parsing from device URL
- Capability detection (video, ptz, events)
- Partial success handling for timeouts
"""

from __future__ import annotations

import inspect
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

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


# ONVIF scope patterns for extracting manufacturer and model
ONVIF_SCOPE_NAME_PATTERN = re.compile(r"onvif://www\.onvif\.org/name/(.+)", re.IGNORECASE)
ONVIF_SCOPE_HARDWARE_PATTERN = re.compile(r"onvif://www\.onvif\.org/hardware/(.+)", re.IGNORECASE)


def _require_onvif_library() -> Any:
    """Return ONVIFCamera class or raise ImportError if not installed."""
    if ONVIFCamera is None:
        raise ImportError("onvif-zeep library not installed. Install with: pip install onvif-zeep")
    return ONVIFCamera


def _get_onvif_device_url(camera: Camera) -> str:
    """Extract and validate ONVIF device URL from camera.

    Raises:
        ValueError: If camera is not an ONVIF camera.
    """
    device_url = camera.folder_path
    if not device_url.startswith("http"):
        raise ValueError(f"Camera {camera.id} is not an ONVIF camera")
    return device_url


class OnvifService:
    """ONVIF device management and PTZ control service.

    Provides device discovery, capability retrieval, RTSP URL extraction,
    PTZ command execution, and preset navigation.

    Example:
        async with get_session() as session:
            service = OnvifService(session, redis)
            devices = await service.discover_devices(subnet="192.168.1.0/24")
    """

    def __init__(
        self,
        session: AsyncSession,
        redis: RedisClient | None = None,
    ) -> None:
        """Initialize the ONVIF service."""
        self.session = session
        self.redis = redis

    async def discover_devices(
        self,
        subnet: str,
        timeout: int = 10,
    ) -> list[dict[str, Any]]:
        """Discover ONVIF devices on the network using WS-Discovery.

        Phase 2 enhanced discovery includes:
        - RTSP URL extraction from media profiles
        - Manufacturer/model from ONVIF-standard scopes
        - IP address and port parsing
        - Capability detection (video, ptz, events)
        - Partial success handling for device timeouts

        Args:
            subnet: Network subnet in CIDR notation (e.g., '192.168.1.0/24').
            timeout: Discovery timeout in seconds.

        Returns:
            List of discovered devices with their information including
            rtsp_urls, capabilities, ip, and port.

        Raises:
            Exception: If discovery fails.
        """
        # Use module-level WSDiscovery (allows test patching)
        _WSDiscovery = WSDiscovery
        if _WSDiscovery is None:
            raise ImportError(
                "WSDiscovery library not installed. Install with: pip install wsdiscovery"
            )

        # Use module-level ONVIFCamera for detailed device info
        _ONVIFCamera = ONVIFCamera

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
            timeout_count = 0

            for service in services:
                # Get service address (XAddrs)
                xaddrs = getattr(service, "xaddrs", None) or getattr(service, "XAddrs", "")
                if isinstance(xaddrs, list):
                    xaddrs = xaddrs[0] if xaddrs else ""

                # Filter for ONVIF devices (device service URL)
                if not xaddrs or "onvif" not in xaddrs.lower():
                    continue

                # Parse IP and port from device URL
                parsed_url = urlparse(xaddrs)
                ip_address = parsed_url.hostname or ""
                port = parsed_url.port or 80  # Default ONVIF port

                # Extract basic device info
                device_info: dict[str, Any] = {
                    "device_url": xaddrs,
                    "ip": ip_address,
                    "port": port,
                    "manufacturer": "Unknown",
                    "model": "Unknown",
                    "firmware_version": None,
                    "serial_number": None,
                    "hardware_id": None,
                    "rtsp_urls": [],
                    "capabilities": {
                        "video": True,  # Assume video if ONVIF device
                        "ptz": False,
                        "events": False,
                    },
                }

                # Parse ONVIF-standard scopes for manufacturer and model
                scopes = getattr(service, "scopes", []) or []
                for scope in scopes:
                    scope_str = str(scope)
                    # Handle scope objects that have a .scope attribute
                    if hasattr(scope, "scope"):
                        scope_str = str(scope.scope)

                    # Extract manufacturer from /name/ scope (ONVIF standard)
                    name_match = ONVIF_SCOPE_NAME_PATTERN.match(scope_str)
                    if name_match:
                        device_info["manufacturer"] = name_match.group(1)
                        continue

                    # Extract model from /hardware/ scope (ONVIF standard)
                    hardware_match = ONVIF_SCOPE_HARDWARE_PATTERN.match(scope_str)
                    if hardware_match:
                        device_info["model"] = hardware_match.group(1)
                        continue

                # Try to get detailed info via ONVIF connection
                if _ONVIFCamera is not None:
                    try:
                        # Connect to device for RTSP URLs and capabilities
                        onvif_camera = _ONVIFCamera(xaddrs)

                        # Get media profiles and RTSP URLs
                        try:
                            profiles = onvif_camera.media.GetProfiles()
                            rtsp_urls = []
                            for profile in profiles:
                                try:
                                    stream_uri = onvif_camera.media.GetStreamUri(
                                        ProfileToken=profile.token,
                                        StreamSetup={
                                            "Stream": "RTP-Unicast",
                                            "Transport": {"Protocol": "RTSP"},
                                        },
                                    )
                                    rtsp_urls.append(
                                        {
                                            "profile": getattr(profile, "Name", profile.token),
                                            "url": str(stream_uri.Uri),
                                        }
                                    )
                                except Exception as e:
                                    # Skip profiles that fail to get stream URI
                                    logger.debug(
                                        "Failed to get stream URI for profile",
                                        extra={
                                            "device_url": xaddrs,
                                            "profile_token": profile.token,
                                            "error": str(e),
                                        },
                                    )
                            device_info["rtsp_urls"] = rtsp_urls
                        except TimeoutError:
                            timeout_count += 1
                            logger.warning(
                                "Timeout getting media profiles",
                                extra={"device_url": xaddrs},
                            )
                        except Exception as e:
                            logger.debug(
                                "Failed to get media profiles",
                                extra={"device_url": xaddrs, "error": str(e)},
                            )

                        # Get capabilities
                        try:
                            capabilities = onvif_camera.devicemgmt.GetCapabilities()
                            device_info["capabilities"] = {
                                "video": True,  # All ONVIF devices support video
                                "ptz": hasattr(capabilities, "PTZ")
                                and capabilities.PTZ is not None,
                                "events": hasattr(capabilities, "Events")
                                and capabilities.Events is not None,
                            }
                        except Exception as e:
                            logger.debug(
                                "Failed to get capabilities",
                                extra={"device_url": xaddrs, "error": str(e)},
                            )

                    except TimeoutError:
                        timeout_count += 1
                        logger.warning(
                            "Timeout connecting to ONVIF device",
                            extra={"device_url": xaddrs},
                        )
                    except Exception as e:
                        logger.debug(
                            "Failed to connect to ONVIF device for details",
                            extra={"device_url": xaddrs, "error": str(e)},
                        )

                devices.append(device_info)

            logger.info(
                "ONVIF discovery completed",
                extra={
                    "subnet": subnet,
                    "devices_found": len(devices),
                    "timeout_count": timeout_count,
                },
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
        camera = await self._get_camera(camera_id)
        _ONVIFCamera = _require_onvif_library()
        device_url = _get_onvif_device_url(camera)

        onvif_camera = _ONVIFCamera(device_url)
        device_info = onvif_camera.devicemgmt.GetDeviceInformation()
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
        valid_commands = {"pan", "tilt", "zoom", "stop"}
        if command not in valid_commands:
            raise ValueError(f"Invalid PTZ command: {command}")
        if not -1.0 <= value <= 1.0:
            raise ValueError("PTZ value must be between -1.0 and 1.0")

        camera = await self._get_camera(camera_id)
        _ONVIFCamera = _require_onvif_library()
        device_url = _get_onvif_device_url(camera)

        onvif_camera = _ONVIFCamera(device_url)

        if command == "stop":
            onvif_camera.ptz.Stop()
        else:
            velocity = {"PanTilt": {"x": 0.0, "y": 0.0}, "Zoom": {"x": 0.0}}
            if command == "pan":
                velocity["PanTilt"]["x"] = value * speed
            elif command == "tilt":
                velocity["PanTilt"]["y"] = value * speed
            elif command == "zoom":
                velocity["Zoom"]["x"] = value * speed
            onvif_camera.ptz.ContinuousMove(velocity)

        logger.info(
            "PTZ command executed",
            extra={"camera_id": camera_id, "command": command, "value": value, "speed": speed},
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
        _ONVIFCamera = _require_onvif_library()
        onvif_camera = _ONVIFCamera(device_url, username, password)

        profiles = onvif_camera.media.GetProfiles()
        if not profiles:
            raise ValueError("No media profiles found on device")

        stream_uri = onvif_camera.media.GetStreamUri(
            ProfileToken=profiles[0].token,
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
        camera = await self._get_camera(camera_id)
        _ONVIFCamera = _require_onvif_library()
        device_url = _get_onvif_device_url(camera)

        onvif_camera = _ONVIFCamera(device_url)
        presets = onvif_camera.ptz.GetPresets()

        return [{"token": p.token, "name": getattr(p, "Name", None)} for p in presets]

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
        camera = await self._get_camera(camera_id)
        _ONVIFCamera = _require_onvif_library()
        device_url = _get_onvif_device_url(camera)

        onvif_camera = _ONVIFCamera(device_url)
        onvif_camera.ptz.GotoPreset(PresetToken=preset_token)

        logger.info(
            "PTZ preset navigation started",
            extra={"camera_id": camera_id, "preset_token": preset_token},
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
