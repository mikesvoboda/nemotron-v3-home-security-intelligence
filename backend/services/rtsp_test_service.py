"""RTSP connection testing service.

NEM-4382: Service for testing RTSP camera connections before adding them.
Provides connection validation, capability detection, and error reporting.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass
class RTSPCapabilities:
    """Detected capabilities of an RTSP stream."""

    video: bool = True
    audio: bool = False
    ptz: bool = False
    resolution: str | None = None
    codec: str = "H.264"
    fps: int | None = None


@dataclass
class RTSPTestResult:
    """Result of an RTSP connection test."""

    success: bool
    latency_ms: int | None = None
    capabilities: RTSPCapabilities | None = None
    error_message: str | None = None


class RTSPTestService:
    """Service for testing RTSP camera connections.

    Provides functionality to test RTSP URLs for connectivity,
    authentication, and capability detection.
    """

    CONNECTION_TIMEOUT = 5.0  # seconds

    async def test_connection(
        self,
        rtsp_url: str,
        username: str | None = None,
        password: str | None = None,
    ) -> RTSPTestResult:
        """Test an RTSP connection and detect stream capabilities.

        Args:
            rtsp_url: The RTSP URL to test
            username: Optional username for authentication
            password: Optional password for authentication

        Returns:
            RTSPTestResult with success status, latency, and capabilities
        """

        # Build authenticated URL if credentials provided
        if username and password:
            # Insert credentials into URL
            if "://" in rtsp_url:
                protocol, rest = rtsp_url.split("://", 1)
                rtsp_url = f"{protocol}://{username}:{password}@{rest}"

        start_time = time.monotonic()

        try:
            # Run capture in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self._test_capture, rtsp_url),
                timeout=self.CONNECTION_TIMEOUT,
            )

            latency_ms = int((time.monotonic() - start_time) * 1000)
            result.latency_ms = latency_ms
            return result

        except TimeoutError:
            return RTSPTestResult(
                success=False,
                error_message="Connection timeout - stream did not respond within 5 seconds",
            )
        except Exception as e:
            return RTSPTestResult(
                success=False,
                error_message=f"Connection failed: {e!s}",
            )

    def _test_capture(self, rtsp_url: str) -> RTSPTestResult:
        """Synchronous capture test (run in executor)."""
        import cv2

        cap = cv2.VideoCapture(rtsp_url)

        try:
            if not cap.isOpened():
                # Check if it's an auth failure
                if "401" in str(cap) or "Unauthorized" in str(cap):
                    return RTSPTestResult(
                        success=False,
                        error_message="Authentication failed - check username and password",
                    )
                return RTSPTestResult(
                    success=False,
                    error_message="Failed to connect to RTSP stream",
                )

            # Get stream properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))

            capabilities = RTSPCapabilities(
                video=True,
                audio=False,  # Would need separate audio detection
                ptz=False,  # Would need ONVIF query
                resolution=f"{width}x{height}" if width and height else None,
                codec="H.264",  # Default assumption
                fps=fps if fps > 0 else None,
            )

            return RTSPTestResult(
                success=True,
                capabilities=capabilities,
            )

        finally:
            cap.release()
