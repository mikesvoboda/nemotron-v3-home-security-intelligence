"""NVIDIA GPU detection and driver management for setup.py.

Provides detection of NVIDIA GPUs, driver version checking, and installation
command generation for various Linux distributions. Supports CUDA 13.1+
compatibility checking (requires driver 580+).

Usage:
    from setup_lib.nvidia_detect import (
        is_nvidia_gpu_present,
        get_gpu_info,
        get_driver_version,
        is_driver_version_sufficient,
        prompt_and_check_nvidia,
    )

    if is_nvidia_gpu_present():
        gpu_info = get_gpu_info()
        version = get_driver_version()
        if not is_driver_version_sufficient(version):
            print("Driver upgrade required")
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TypedDict

# Minimum driver version for CUDA 13.1 compatibility
# CUDA 13.x requires driver 580+ (ai-llm container uses CUDA 13.1.1)
MINIMUM_DRIVER_VERSION = 580


class GpuInfo(TypedDict):
    """GPU information from nvidia-smi."""

    name: str
    vram_mb: int
    compute_cap: str  # Compute capability (e.g., "8.9")


class NvidiaDetectionSummary(TypedDict):
    """Complete NVIDIA detection summary."""

    gpu_present: bool
    gpus: list[GpuInfo] | None
    driver_version: str | None
    driver_sufficient: bool
    toolkit_installed: bool


def _parse_driver_version(version: str) -> tuple[int, int, int] | None:
    """Parse driver version string into tuple of (major, minor, patch).

    Args:
        version: Version string like "560.35.03" or "535.183.01"

    Returns:
        Tuple of (major, minor, patch) or None if parsing fails.
    """
    if not version or not version.strip():
        return None

    parts = version.strip().split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except (ValueError, IndexError):
        return None


def is_nvidia_gpu_present() -> bool:
    """Check if an NVIDIA GPU is present and accessible.

    Attempts to run nvidia-smi to detect NVIDIA GPU presence.

    Returns:
        True if nvidia-smi runs successfully, False otherwise.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=gpu_name", "--format=csv,noheader"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired):
        return False


def get_gpu_info() -> list[GpuInfo] | None:
    """Get information about all detected NVIDIA GPUs.

    Queries nvidia-smi for GPU names, VRAM sizes, and compute capability.

    Returns:
        List of GpuInfo dicts with name, vram_mb, and compute_cap, or None if detection fails.
    """
    try:
        # Get GPU names
        name_result = subprocess.run(
            ["nvidia-smi", "--query-gpu=gpu_name", "--format=csv,noheader"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if name_result.returncode != 0:
            return None

        # Get VRAM sizes (in MiB)
        memory_result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if memory_result.returncode != 0:
            return None

        # Get compute capability
        compute_result = subprocess.run(
            ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        names = [n.strip() for n in name_result.stdout.strip().split("\n") if n.strip()]
        memories = [m.strip() for m in memory_result.stdout.strip().split("\n") if m.strip()]
        compute_caps = (
            [c.strip() for c in compute_result.stdout.strip().split("\n") if c.strip()]
            if compute_result.returncode == 0
            else []
        )

        gpus: list[GpuInfo] = []
        for i, name in enumerate(names):
            vram_mb = int(memories[i]) if i < len(memories) else 0
            compute_cap = compute_caps[i] if i < len(compute_caps) else "unknown"
            gpus.append(GpuInfo(name=name, vram_mb=vram_mb, compute_cap=compute_cap))

        return gpus if gpus else None

    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, ValueError):
        return None


def get_driver_version() -> str | None:
    """Get the NVIDIA driver version from nvidia-smi.

    Returns:
        Driver version string (e.g., "560.35.03") or None if detection fails.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            return None

        # Take first line in case of multiple GPUs (all should have same driver)
        version = result.stdout.strip().split("\n")[0].strip()
        return version if version else None

    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired):
        return None


def is_driver_version_sufficient(
    version: str | None,
    minimum_major: int = MINIMUM_DRIVER_VERSION,
) -> bool:
    """Check if driver version meets minimum requirements.

    Args:
        version: Driver version string from get_driver_version().
        minimum_major: Minimum major version required (default: 535 for CUDA 12.1).

    Returns:
        True if version >= minimum, False otherwise.
    """
    if not version:
        return False

    parsed = _parse_driver_version(version)
    if not parsed:
        return False

    major, _, _ = parsed
    return major >= minimum_major


def get_driver_install_command(distro_family: str, *, is_ubuntu: bool = False) -> str | None:
    """Get the appropriate driver installation command for the distribution.

    Args:
        distro_family: Distribution family ('fedora', 'debian', 'arch').
        is_ubuntu: Whether the system is specifically Ubuntu (for ubuntu-drivers).

    Returns:
        Installation command string or None for unknown distributions.
    """
    if not distro_family:
        return None

    if distro_family == "fedora":
        return "sudo dnf install -y akmod-nvidia"
    elif distro_family == "debian":
        if is_ubuntu:
            return "sudo ubuntu-drivers install"
        return "sudo apt install -y nvidia-driver"
    elif distro_family == "arch":
        return "sudo pacman -S --noconfirm nvidia"

    return None


def is_container_toolkit_installed() -> bool:
    """Check if NVIDIA Container Toolkit is installed.

    Checks for the presence of nvidia-ctk binary.

    Returns:
        True if nvidia-ctk is found, False otherwise.
    """
    return shutil.which("nvidia-ctk") is not None


_TOOLKIT_INSTALL_COMMANDS: dict[str, str] = {
    "fedora": "sudo dnf install -y nvidia-container-toolkit",
    "debian": "sudo apt install -y nvidia-container-toolkit",
    "arch": "sudo pacman -S --noconfirm nvidia-container-toolkit",
}


def get_toolkit_install_command(distro_family: str) -> str | None:
    """Get the NVIDIA Container Toolkit installation command.

    Args:
        distro_family: Distribution family ('fedora', 'debian', 'arch').

    Returns:
        Installation command string or None for unknown distributions.
    """
    return _TOOLKIT_INSTALL_COMMANDS.get(distro_family)


def get_nvidia_detection_summary() -> NvidiaDetectionSummary:
    """Get a complete summary of NVIDIA GPU detection status.

    Returns:
        NvidiaDetectionSummary with all detection results.
    """
    gpu_present = is_nvidia_gpu_present()

    if not gpu_present:
        return NvidiaDetectionSummary(
            gpu_present=False,
            gpus=None,
            driver_version=None,
            driver_sufficient=False,
            toolkit_installed=False,
        )

    gpus = get_gpu_info()
    driver_version = get_driver_version()
    driver_sufficient = is_driver_version_sufficient(driver_version)
    toolkit_installed = is_container_toolkit_installed()

    return NvidiaDetectionSummary(
        gpu_present=True,
        gpus=gpus,
        driver_version=driver_version,
        driver_sufficient=driver_sufficient,
        toolkit_installed=toolkit_installed,
    )


def prompt_and_check_nvidia(config: dict[str, object]) -> bool:
    """Interactive prompt to check NVIDIA GPU and update configuration.

    Detects GPU, driver version, and container toolkit. Updates config dict
    with detection results for use by setup.py.

    Args:
        config: Configuration dictionary to update with detection results.

    Returns:
        True if GPU is detected (regardless of driver status), False otherwise.
    """
    print("\n[NVIDIA GPU Detection]")

    if not is_nvidia_gpu_present():
        print("  No NVIDIA GPU detected (nvidia-smi not available)")
        config["gpu_detected"] = False
        return False

    config["gpu_detected"] = True

    # Get GPU info
    gpus = get_gpu_info()
    if gpus:
        gpu = gpus[0]  # Primary GPU
        config["gpu_name"] = gpu["name"]
        config["gpu_vram_mb"] = gpu["vram_mb"]
        print(f"  GPU: {gpu['name']}")
        print(f"  VRAM: {gpu['vram_mb']} MB")

        if len(gpus) > 1:
            print(f"  Additional GPUs: {len(gpus) - 1}")

    # Check driver version
    driver_version = get_driver_version()
    config["driver_version"] = driver_version

    if driver_version:
        print(f"  Driver Version: {driver_version}")

        if is_driver_version_sufficient(driver_version):
            config["driver_needs_upgrade"] = False
            print(f"  Driver Status: OK (>= {MINIMUM_DRIVER_VERSION} required for CUDA 13.1)")
        else:
            config["driver_needs_upgrade"] = True
            print(f"  Driver Status: UPGRADE NEEDED (>= {MINIMUM_DRIVER_VERSION} required)")
    else:
        config["driver_needs_upgrade"] = True
        print("  Driver Version: Unknown")

    # Check container toolkit
    toolkit_installed = is_container_toolkit_installed()
    config["toolkit_installed"] = toolkit_installed

    if toolkit_installed:
        print("  Container Toolkit: Installed")
    else:
        print("  Container Toolkit: NOT INSTALLED")

    return True


def print_nvidia_info() -> None:
    """Print detected NVIDIA GPU information for debugging."""
    summary = get_nvidia_detection_summary()

    if not summary["gpu_present"]:
        print("No NVIDIA GPU detected")
        return

    print("NVIDIA GPU Detection Summary:")
    print(f"  GPU Present: {summary['gpu_present']}")

    if summary["gpus"]:
        for i, gpu in enumerate(summary["gpus"]):
            print(f"  GPU {i}: {gpu['name']} ({gpu['vram_mb']} MB)")

    print(f"  Driver Version: {summary['driver_version'] or 'Unknown'}")
    print(f"  Driver Sufficient: {summary['driver_sufficient']}")
    print(
        f"  Container Toolkit: {'Installed' if summary['toolkit_installed'] else 'Not installed'}"
    )


if __name__ == "__main__":
    print_nvidia_info()
