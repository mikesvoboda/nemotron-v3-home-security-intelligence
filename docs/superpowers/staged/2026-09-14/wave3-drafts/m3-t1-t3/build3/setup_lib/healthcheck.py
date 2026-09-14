"""Health check utilities for deployment verification."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


def poll_endpoint(url: str, timeout: int = 60, interval: int = 5) -> bool:
    """Poll HTTP endpoint until 200 response or timeout.

    Args:
        url: HTTP URL to poll.
        timeout: Maximum seconds to wait.
        interval: Seconds between attempts.

    Returns:
        True on success, False on timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = urllib.request.urlopen(url, timeout=5)  # noqa: S310  # nosemgrep: ssrf-requests
            if resp.status == 200:
                return True
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(interval, remaining))
    return False


def check_service_health(name: str, url: str, timeout: int = 60) -> dict:
    """Check a service health endpoint.

    Args:
        name: Human-readable service name.
        url: Health endpoint URL.
        timeout: Request timeout in seconds.

    Returns:
        Dict with keys: name, status, response_time_ms, error, data.
    """
    start = time.monotonic()
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)  # noqa: S310  # nosemgrep: ssrf-requests
        elapsed_ms = int((time.monotonic() - start) * 1000)
        data = json.loads(resp.read().decode())
        return {
            "name": name,
            "status": "healthy",
            "response_time_ms": elapsed_ms,
            "error": None,
            "data": data,
        }
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "name": name,
            "status": "unhealthy",
            "response_time_ms": elapsed_ms,
            "error": str(e),
            "data": None,
        }
