"""go2rtc client for RTSP to WebRTC conversion.

NEM-4400, NEM-4401: Client service for go2rtc integration.
Provides live video preview via WebRTC for RTSP cameras.
"""

from __future__ import annotations

import logging
import re
import secrets
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Session expiry time in seconds (5 minutes per design doc)
SESSION_EXPIRY_SECONDS = 300


class Go2RTCUnavailableError(Exception):
    """Raised when go2rtc service is unavailable."""

    pass


class StreamRegistrationError(Exception):
    """Raised when stream registration fails."""

    pass


class Go2RTCClient:
    """Client for interacting with go2rtc service.

    Provides RTSP to WebRTC conversion for low-latency video streaming.
    Session management with 5-minute expiry.
    Health monitoring for graceful degradation.
    """

    VALID_SCHEMES = ("rtsp", "rtsps")

    def __init__(
        self,
        api_url: str,
        webrtc_url: str,
        timeout: float = 5.0,
    ) -> None:
        """Initialize go2rtc client.

        Args:
            api_url: Base URL for go2rtc API (e.g., http://localhost:1984)
            webrtc_url: Base URL for WebRTC connections (e.g., http://localhost:8555)
            timeout: Request timeout in seconds
        """
        self.api_url = api_url.rstrip("/")
        self.webrtc_url = webrtc_url.rstrip("/")
        self.timeout = timeout

    async def health_check(self) -> bool:
        """Check if go2rtc service is available.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/api/",
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return True
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
            return False

    async def register_stream(
        self,
        camera_id: str,
        rtsp_url: str,
        username: str | None = None,
        password: str | None = None,
    ) -> dict:
        """Register an RTSP stream with go2rtc for WebRTC conversion.

        Args:
            camera_id: Unique camera identifier
            rtsp_url: RTSP URL for the camera stream
            username: Optional username for authentication
            password: Optional password for authentication

        Returns:
            Dict with stream_id, webrtc_url, and expires_in

        Raises:
            StreamRegistrationError: If URL is invalid or registration fails
            Go2RTCUnavailableError: If go2rtc service is unavailable
        """
        # Validate RTSP URL format
        validation_error = self._validate_rtsp_url(rtsp_url)
        if validation_error:
            raise StreamRegistrationError(
                f"Invalid RTSP URL for camera {camera_id}: {validation_error}"
            )

        # Build authenticated URL if credentials provided
        source_url = rtsp_url
        if username and password:
            parsed = urlparse(rtsp_url)
            source_url = f"{parsed.scheme}://{username}:{password}@{parsed.netloc}{parsed.path}"
            if parsed.query:
                source_url += f"?{parsed.query}"

        # Generate unique stream ID
        unique_suffix = secrets.token_hex(6)
        stream_id = f"camera_{camera_id}_{unique_suffix}"

        # Log without exposing password
        logger.debug(
            "Registering stream for camera %s with stream_id %s",
            camera_id,
            stream_id,
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/api/streams",
                    json={"name": stream_id, "source": source_url},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

                return {
                    "stream_id": data.get("stream_id", stream_id),
                    "webrtc_url": data.get("url", f"{self.webrtc_url}/api/ws?src={stream_id}"),
                    "expires_in": SESSION_EXPIRY_SECONDS,
                }

        except httpx.ConnectError as e:
            raise Go2RTCUnavailableError(
                f"go2rtc service unavailable - cannot register stream for camera {camera_id}"
            ) from e
        except httpx.TimeoutException as e:
            raise Go2RTCUnavailableError(
                f"go2rtc service timeout - cannot register stream for camera {camera_id}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise StreamRegistrationError(
                f"Failed to register stream for camera {camera_id}: {e}"
            ) from e

    async def unregister_stream(self, stream_id: str) -> None:
        """Remove a stream from go2rtc (best-effort cleanup).

        Args:
            stream_id: The stream ID to remove

        Note:
            This is a best-effort operation and will not raise exceptions.
            Errors are logged but not propagated.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.api_url}/api/streams/{stream_id}",
                    timeout=self.timeout,
                )
                # 404 is acceptable (stream already removed)
                if response.status_code not in (200, 204, 404):
                    logger.warning(
                        "Failed to unregister stream %s: HTTP %d",
                        stream_id,
                        response.status_code,
                    )
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning("Failed to unregister stream %s: %s", stream_id, e)

    def _validate_rtsp_url(self, rtsp_url: str) -> str | None:
        """Validate RTSP URL format.

        Returns error message if invalid, None if valid.
        """
        # Check for invalid characters (spaces, etc.)
        if re.search(r"\s", rtsp_url):
            return "URL contains spaces or invalid characters"

        try:
            parsed = urlparse(rtsp_url)
        except Exception:
            return "Could not parse URL"

        if not parsed.scheme:
            return "Missing protocol (expected rtsp:// or rtsps://)"

        if parsed.scheme.lower() not in self.VALID_SCHEMES:
            return f"Unsupported protocol '{parsed.scheme}' (expected rtsp:// or rtsps://)"

        if not parsed.netloc or not parsed.hostname:
            return "Missing host"

        return None
