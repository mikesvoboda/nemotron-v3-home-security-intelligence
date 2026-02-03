"""NVIDIA Container Toolkit installation and configuration for setup.py.

Provides detection, installation, and runtime configuration of NVIDIA Container
Toolkit for Docker and Podman. Enables GPU passthrough to containers for
AI workloads.

Usage:
    from setup_lib.nvidia_toolkit import (
        is_toolkit_installed,
        get_toolkit_version,
        setup_nvidia_container_toolkit,
    )

    if not is_toolkit_installed():
        setup_nvidia_container_toolkit(auto_install=True)
"""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any, TypedDict


class ToolkitInstallationSummary(TypedDict):
    """Complete NVIDIA Container Toolkit installation summary."""

    toolkit_installed: bool
    toolkit_version: str | None
    docker_available: bool
    podman_available: bool
    docker_configured: bool
    podman_configured: bool


# Package installation commands by distribution family
_TOOLKIT_INSTALL_COMMANDS: dict[str, list[str]] = {
    "fedora": ["sudo", "dnf", "install", "-y", "nvidia-container-toolkit"],
    "debian": ["sudo", "apt", "install", "-y", "nvidia-container-toolkit"],
    "arch": ["sudo", "pacman", "-S", "--noconfirm", "nvidia-container-toolkit"],
}


def is_toolkit_installed() -> bool:
    """Check if NVIDIA Container Toolkit is installed.

    Checks for the presence of nvidia-ctk binary in PATH.

    Returns:
        True if nvidia-ctk is found, False otherwise.
    """
    return shutil.which("nvidia-ctk") is not None


def get_toolkit_version() -> str | None:
    """Get the installed NVIDIA Container Toolkit version.

    Runs 'nvidia-ctk --version' and parses the output to extract
    the version string.

    Returns:
        Version string (e.g., '1.14.3') or None if not installed
        or version cannot be determined.
    """
    try:
        result = subprocess.run(
            ["nvidia-ctk", "--version"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            return None

        # Parse output like "NVIDIA Container Toolkit CLI version 1.14.3"
        # or "nvidia-ctk version 1.14.3"
        output = result.stdout + result.stderr
        match = re.search(r"version\s+(\d+\.\d+(?:\.\d+)?)", output, re.IGNORECASE)
        if match:
            return match.group(1)
        return None
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError):
        return None


def is_docker_installed() -> bool:
    """Check if Docker is installed and available.

    Returns:
        True if docker executable is found in PATH, False otherwise.
    """
    return shutil.which("docker") is not None


def is_podman_installed() -> bool:
    """Check if Podman is installed and available.

    Returns:
        True if podman executable is found in PATH, False otherwise.
    """
    return shutil.which("podman") is not None


def get_detected_runtimes() -> list[str]:
    """Get list of available container runtimes.

    Detects which container runtimes (Docker, Podman) are installed
    and available on the system.

    Returns:
        List of runtime names that are available (e.g., ['docker', 'podman']).
    """
    runtimes: list[str] = []
    if is_docker_installed():
        runtimes.append("docker")
    if is_podman_installed():
        runtimes.append("podman")
    return runtimes


def get_toolkit_installation_summary() -> ToolkitInstallationSummary:
    """Get a complete summary of NVIDIA Container Toolkit status.

    Returns:
        ToolkitInstallationSummary with all installation and configuration status.
    """
    toolkit_installed = is_toolkit_installed()
    toolkit_version = get_toolkit_version() if toolkit_installed else None
    docker_available = is_docker_installed()
    podman_available = is_podman_installed()

    return ToolkitInstallationSummary(
        toolkit_installed=toolkit_installed,
        toolkit_version=toolkit_version,
        docker_available=docker_available,
        podman_available=podman_available,
        docker_configured=False,  # Would need runtime check
        podman_configured=False,  # Would need runtime check
    )


def get_install_command(distro_family: str) -> list[str] | None:
    """Get the NVIDIA Container Toolkit installation command.

    Args:
        distro_family: Distribution family ('fedora', 'debian', 'arch').

    Returns:
        List of command arguments for installation, or None for unknown distributions.
    """
    return _TOOLKIT_INSTALL_COMMANDS.get(distro_family)


def install_toolkit(distro_family: str) -> bool:
    """Install NVIDIA Container Toolkit using the system package manager.

    Args:
        distro_family: Distribution family ('fedora', 'debian', 'arch').

    Returns:
        True if installation succeeded, False otherwise.
    """
    command = get_install_command(distro_family)
    if command is None:
        return False

    try:
        result = subprocess.run(command, check=False)
        return result.returncode == 0
    except OSError:
        return False


def configure_docker_runtime() -> bool:
    """Configure Docker to use the NVIDIA runtime.

    Uses nvidia-ctk to configure the Docker daemon for GPU support.
    This adds the nvidia runtime to Docker's daemon.json.

    Returns:
        True if configuration succeeded, False otherwise.
    """
    if not is_toolkit_installed():
        return False

    try:
        result = subprocess.run(
            ["sudo", "nvidia-ctk", "runtime", "configure", "--runtime=docker"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError):
        return False


def configure_podman_runtime() -> bool:
    """Configure Podman to use the NVIDIA runtime via CDI.

    Uses nvidia-ctk to generate CDI (Container Device Interface) specs
    for Podman GPU support.

    Returns:
        True if configuration succeeded, False otherwise.
    """
    if not is_toolkit_installed():
        return False

    try:
        result = subprocess.run(
            ["sudo", "nvidia-ctk", "cdi", "generate", "--output=/etc/cdi/nvidia.yaml"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError):
        return False


def configure_runtimes() -> dict[str, bool]:
    """Configure all detected container runtimes for GPU support.

    Detects available runtimes (Docker, Podman) and configures each
    for NVIDIA GPU passthrough.

    Returns:
        Dict mapping runtime names to configuration success status.
    """
    results: dict[str, bool] = {}
    runtimes = get_detected_runtimes()

    if "docker" in runtimes:
        results["docker"] = configure_docker_runtime()

    if "podman" in runtimes:
        results["podman"] = configure_podman_runtime()

    return results


def restart_docker_daemon() -> bool:
    """Restart Docker daemon to apply configuration changes.

    Uses systemctl to restart the Docker service.

    Returns:
        True if restart succeeded, False otherwise.
    """
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "restart", "docker"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError):
        return False


def verify_gpu_passthrough(runtime: str = "docker") -> bool:
    """Verify GPU passthrough works in containers.

    Runs a test container with GPU access to verify the configuration.

    Args:
        runtime: Container runtime to test ('docker' or 'podman').

    Returns:
        True if GPU is accessible in containers, False otherwise.
    """
    if runtime not in ("docker", "podman"):
        return False

    try:
        if runtime == "docker":
            cmd = [
                "docker",
                "run",
                "--rm",
                "--gpus",
                "all",
                "nvidia/cuda:12.1.0-base-ubuntu22.04",
                "nvidia-smi",
            ]
        else:
            # Podman uses CDI for GPU access
            cmd = [
                "podman",
                "run",
                "--rm",
                "--device",
                "nvidia.com/gpu=all",
                "nvidia/cuda:12.1.0-base-ubuntu22.04",
                "nvidia-smi",
            ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError):
        return False


def prompt_and_install_toolkit(config: dict[str, Any] | None = None) -> bool:
    """Interactive prompt to install NVIDIA Container Toolkit.

    Checks if toolkit is installed, and if not, prompts the user for
    confirmation before installing.

    Args:
        config: Optional configuration dict. If config['auto_install'] is True,
                skips the user prompt and installs automatically.
                Requires config['distro_family'] for the distribution family.

    Returns:
        True if toolkit is installed (or was installed successfully),
        False otherwise.
    """
    if is_toolkit_installed():
        return True

    # Get distro family from config
    distro_family = config.get("distro_family") if config else None
    if not distro_family:
        print("! Cannot determine distribution family for toolkit installation")
        return False

    command = get_install_command(distro_family)
    if command is None:
        print(f"! Unsupported distribution family: {distro_family}")
        return False

    # Check if auto-install is enabled
    auto_install = bool(config and config.get("auto_install"))

    if not auto_install:
        response = input("NVIDIA Container Toolkit is not installed. Install it? [y/N]: ")
        if response.lower() not in ("y", "yes"):
            return False

    print(f"Installing NVIDIA Container Toolkit: {' '.join(command)}")

    if not install_toolkit(distro_family):
        print("! NVIDIA Container Toolkit installation failed")
        return False

    print("NVIDIA Container Toolkit installed successfully")
    return True


def prompt_and_configure_runtimes(config: dict[str, Any] | None = None) -> bool:
    """Interactive prompt to configure container runtimes for GPU support.

    Detects available runtimes and prompts to configure each one.

    Args:
        config: Optional configuration dict. If config['auto_install'] is True,
                skips the user prompt and configures automatically.

    Returns:
        True if at least one runtime was configured successfully,
        False otherwise.
    """
    if not is_toolkit_installed():
        print("! NVIDIA Container Toolkit must be installed before configuring runtimes")
        return False

    runtimes = get_detected_runtimes()
    if not runtimes:
        print("! No container runtimes detected (Docker or Podman)")
        return False

    auto_install = bool(config and config.get("auto_install"))

    if not auto_install:
        runtime_list = ", ".join(runtimes)
        response = input(f"Configure GPU support for {runtime_list}? [y/N]: ")
        if response.lower() not in ("y", "yes"):
            return False

    print(f"Configuring container runtimes: {', '.join(runtimes)}")
    results = configure_runtimes()

    any_success = False
    for runtime, success in results.items():
        if success:
            print(f"  {runtime}: configured successfully")
            any_success = True
        else:
            print(f"  {runtime}: configuration failed")

    # Restart Docker if it was configured
    if results.get("docker"):
        print("Restarting Docker daemon...")
        if restart_docker_daemon():
            print("  Docker daemon restarted")
        else:
            print("  ! Failed to restart Docker daemon")

    return any_success


def setup_nvidia_container_toolkit(auto_install: bool = False) -> bool:
    """Full setup orchestration for NVIDIA Container Toolkit.

    Performs complete setup including installation and runtime configuration.

    Args:
        auto_install: If True, skips user prompts and installs/configures
                     automatically.

    Returns:
        True if setup completed successfully, False otherwise.
    """
    from setup_lib.platform_detect import get_distro_family, get_platform_info

    print("\n[NVIDIA Container Toolkit Setup]")

    # Get platform info
    platform_info = get_platform_info()
    if platform_info is None:
        print("! Unsupported platform")
        return False

    if platform_info["platform"] != "linux":
        print("! NVIDIA Container Toolkit is only supported on Linux")
        return False

    distro = platform_info.get("distro")
    distro_family = get_distro_family(distro)

    if distro_family == "unknown":
        print("! Unknown distribution family")
        return False

    config: dict[str, Any] = {
        "auto_install": auto_install,
        "distro_family": distro_family,
    }

    # Check if already installed
    if is_toolkit_installed():
        version = get_toolkit_version()
        print(f"  NVIDIA Container Toolkit: installed (version {version or 'unknown'})")
    else:
        print("  NVIDIA Container Toolkit: not installed")
        if not prompt_and_install_toolkit(config):
            return False

    # Configure runtimes
    runtimes = get_detected_runtimes()
    if runtimes:
        print(f"  Detected runtimes: {', '.join(runtimes)}")
        if not prompt_and_configure_runtimes(config):
            print("! Runtime configuration failed or declined")
            # Not a fatal error if toolkit is installed
    else:
        print("  No container runtimes detected")

    print("  NVIDIA Container Toolkit setup complete")
    return True


def print_toolkit_info() -> None:
    """Print NVIDIA Container Toolkit information for debugging."""
    summary = get_toolkit_installation_summary()

    print("NVIDIA Container Toolkit Status:")
    print(f"  Installed: {summary['toolkit_installed']}")

    if summary["toolkit_installed"]:
        print(f"  Version: {summary['toolkit_version'] or 'unknown'}")

    print(f"  Docker Available: {summary['docker_available']}")
    print(f"  Podman Available: {summary['podman_available']}")

    runtimes = get_detected_runtimes()
    if runtimes:
        print(f"  Detected Runtimes: {', '.join(runtimes)}")


if __name__ == "__main__":
    print_toolkit_info()
