"""Process memory monitoring service (NEM-3890).

This service provides memory monitoring for the backend process:

1. RSS (Resident Set Size) - actual physical memory used
2. VMS (Virtual Memory Size) - total virtual memory allocated
3. Memory percentage of system RAM
4. Container memory limit detection (cgroup v1/v2)
5. Container memory usage percentage

Memory thresholds:
- Warning: 80% of container limit (or system RAM if no limit)
- Critical: 90% of container limit (or system RAM if no limit)

When memory usage exceeds these thresholds, alerts are generated
and logged to help diagnose memory pressure issues before OOM kills.

Example usage:
    service = ProcessMemoryService()
    info = service.get_memory_info()
    print(f"Memory: {info.rss_mb:.1f} MB ({info.container_usage_percent:.1f}%)")

    if service.is_memory_critical():
        logger.critical("Memory critical - risk of OOM")
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import psutil

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Default memory thresholds
DEFAULT_WARNING_THRESHOLD_PERCENT: Final[float] = 80.0
DEFAULT_CRITICAL_THRESHOLD_PERCENT: Final[float] = 90.0

# cgroup paths for container memory limits
CGROUP_V2_MEMORY_MAX: Final[Path] = Path("/sys/fs/cgroup/memory.max")
CGROUP_V1_MEMORY_LIMIT: Final[Path] = Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")


@dataclass(slots=True, frozen=True)
class ProcessMemoryInfo:
    """Memory information for the current process.

    Attributes:
        rss_bytes: Resident Set Size in bytes (physical memory)
        rss_mb: RSS in megabytes
        vms_bytes: Virtual Memory Size in bytes
        vms_mb: VMS in megabytes
        percent: Memory usage as percentage of system RAM
        container_limit_mb: Container memory limit in MB (None if not in container)
        container_usage_percent: RSS as percentage of container limit (None if no limit)
    """

    rss_bytes: int
    rss_mb: float
    vms_bytes: int
    vms_mb: float
    percent: float
    container_limit_mb: float | None
    container_usage_percent: float | None


class ProcessMemoryService:
    """Service for monitoring process memory usage.

    Tracks memory usage of the current Python process and provides
    threshold-based alerting for memory pressure situations.

    Works both in containerized environments (Docker/Podman with cgroups)
    and on bare metal systems.
    """

    def __init__(
        self,
        warning_threshold_percent: float = DEFAULT_WARNING_THRESHOLD_PERCENT,
        critical_threshold_percent: float = DEFAULT_CRITICAL_THRESHOLD_PERCENT,
    ) -> None:
        """Initialize the memory service.

        Args:
            warning_threshold_percent: Memory usage percentage to trigger warning
            critical_threshold_percent: Memory usage percentage to trigger critical alert
        """
        self._process = psutil.Process()
        self._warning_threshold = warning_threshold_percent
        self._critical_threshold = critical_threshold_percent
        self._cached_container_limit: float | None | bool = False  # False = not checked yet

    def get_memory_info(self) -> ProcessMemoryInfo:
        """Get current process memory information.

        Returns:
            ProcessMemoryInfo with current memory usage details
        """
        mem_info = self._process.memory_info()
        mem_percent = self._process.memory_percent()

        rss_bytes = mem_info.rss
        vms_bytes = mem_info.vms
        rss_mb = rss_bytes / (1024 * 1024)
        vms_mb = vms_bytes / (1024 * 1024)

        # Get container memory limit (cached)
        container_limit_mb = self._get_container_memory_limit()

        # Calculate container usage percentage if limit is known
        container_usage_percent: float | None = None
        if container_limit_mb is not None and container_limit_mb > 0:
            container_usage_percent = (rss_mb / container_limit_mb) * 100

        return ProcessMemoryInfo(
            rss_bytes=rss_bytes,
            rss_mb=rss_mb,
            vms_bytes=vms_bytes,
            vms_mb=vms_mb,
            percent=mem_percent,
            container_limit_mb=container_limit_mb,
            container_usage_percent=container_usage_percent,
        )

    def _read_cgroup_file(self, path: Path) -> str | None:
        """Read content from a cgroup file.

        Args:
            path: Path to the cgroup file

        Returns:
            File content stripped of whitespace, or None if file doesn't exist
        """
        try:
            return path.read_text().strip()
        except (FileNotFoundError, ValueError, PermissionError):
            return None

    def _get_container_memory_limit(self) -> float | None:
        """Get container memory limit from cgroups.

        Checks both cgroup v2 and v1 paths for memory limits.

        Returns:
            Memory limit in MB, or None if not in a container or no limit set
        """
        # Return cached value if already checked
        if self._cached_container_limit is not False:
            return self._cached_container_limit  # type: ignore[return-value]

        limit_bytes: int | None = None

        # Try cgroup v2 first (modern systems)
        content = self._read_cgroup_file(CGROUP_V2_MEMORY_MAX)
        if content is not None and content != "max":
            try:
                limit_bytes = int(content)
            except ValueError:
                pass

        # Fall back to cgroup v1
        if limit_bytes is None:
            content = self._read_cgroup_file(CGROUP_V1_MEMORY_LIMIT)
            if content is not None:
                try:
                    # Very large values indicate no limit (usually 2^63 or similar)
                    value = int(content)
                    if value < 2**62:  # Reasonable limit threshold
                        limit_bytes = value
                except ValueError:
                    pass

        # Convert to MB and cache
        if limit_bytes is not None:
            self._cached_container_limit = limit_bytes / (1024 * 1024)
        else:
            self._cached_container_limit = None

        return self._cached_container_limit

    def is_memory_warning(self) -> bool:
        """Check if memory usage is above warning threshold.

        Uses container usage percentage if available, otherwise system percentage.

        Returns:
            True if memory usage exceeds warning threshold
        """
        info = self.get_memory_info()
        usage = (
            info.container_usage_percent
            if info.container_usage_percent is not None
            else info.percent
        )
        return usage >= self._warning_threshold

    def is_memory_critical(self) -> bool:
        """Check if memory usage is above critical threshold.

        Uses container usage percentage if available, otherwise system percentage.

        Returns:
            True if memory usage exceeds critical threshold
        """
        info = self.get_memory_info()
        usage = (
            info.container_usage_percent
            if info.container_usage_percent is not None
            else info.percent
        )
        return usage >= self._critical_threshold

    def get_status(self) -> str:
        """Get memory status as a string.

        Returns:
            "critical", "warning", or "healthy"
        """
        if self.is_memory_critical():
            return "critical"
        if self.is_memory_warning():
            return "warning"
        return "healthy"


# Singleton instance
_process_memory_service: ProcessMemoryService | None = None


def get_process_memory_service() -> ProcessMemoryService:
    """Get or create the singleton ProcessMemoryService instance.

    Returns:
        ProcessMemoryService singleton
    """
    global _process_memory_service  # noqa: PLW0603
    if _process_memory_service is None:
        _process_memory_service = ProcessMemoryService()
    return _process_memory_service


def get_process_memory_info() -> ProcessMemoryInfo:
    """Convenience function to get process memory info.

    Returns:
        ProcessMemoryInfo with current memory usage details
    """
    return get_process_memory_service().get_memory_info()


def reset_process_memory_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _process_memory_service  # noqa: PLW0603
    _process_memory_service = None
