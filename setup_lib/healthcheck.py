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


def file_watcher_warning(pipeline_status: dict | None, camera_root: str) -> str | None:
    """Warning text if the backend's file watcher fell back to polling, else None.

    Reads the ``file_watcher`` block of ``GET /api/system/pipeline``:
    ``watch_mode == "polling-fallback"`` means the kernel REFUSED the native
    inotify watch on the camera root at startup (A5500 box, 2026-09-28: EACCES
    from SELinux on a usr_t root), so uploads are found by scanning. This
    closes the loop on any host, whatever the compose file. An unreadable or
    older status (no ``watch_mode``) is not a warning.

    Args:
        pipeline_status: The endpoint's JSON body, or None if unreadable.
        camera_root: The HOST camera root (FOSCAM_BASE_PATH), for the fix.
    """
    watcher = (pipeline_status or {}).get("file_watcher") or {}
    if watcher.get("watch_mode") != "polling-fallback":
        return None
    reason = watcher.get("watch_fallback_reason") or "unknown"
    return (
        "file watcher is in polling-fallback "
        f"(watch_fallback_reason={reason}): the backend's inotify watch on the "
        "camera root was refused at startup, so uploads are found by scanning, "
        "not watched. EACCES/EPERM on an SELinux host: add :z to the backend's "
        "/cameras mount, or relabel the root once: sudo semanage fcontext -a -t "
        f"container_file_t '{camera_root}(/.*)?' && sudo restorecon -R {camera_root}. "
        "ENOSPC/EMFILE: raise fs.inotify.max_user_watches / "
        "fs.inotify.max_user_instances. Then restart the backend."
    )
