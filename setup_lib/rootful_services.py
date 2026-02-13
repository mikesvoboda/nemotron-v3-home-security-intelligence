"""Rootful Podman service management for setup.py.

Manages system-level services that require host-level root access
and cannot run under rootless Podman. Currently handles:

- DCGM Exporter: NVIDIA GPU hardware metrics (requires root for nv-hostengine)

Usage:
    from setup_lib.rootful_services import (
        install_dcgm_exporter_service,
        is_dcgm_service_installed,
        prompt_and_install_dcgm_service,
        uninstall_dcgm_exporter_service,
    )
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# Systemd system-level service directory
_SYSTEMD_SYSTEM_DIR = Path("/etc/systemd/system")

# Service name constant
DCGM_SERVICE_NAME = "dcgm-exporter.service"

# Template placeholder for project root path
_PROJECT_ROOT_PLACEHOLDER = "__PROJECT_ROOT__"


def _run_sudo(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a command with sudo.

    Args:
        args: Command arguments (sudo is prepended automatically).
        check: Whether to raise on non-zero exit code.

    Returns:
        CompletedProcess result.
    """
    return subprocess.run(
        ["sudo", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=check,
    )


def _get_service_template_path(project_root: str | Path) -> Path:
    """Get path to the DCGM exporter service template.

    Args:
        project_root: Root directory of the project.

    Returns:
        Path to the service template file.
    """
    return Path(project_root) / "monitoring" / "dcgm" / "dcgm-exporter.service"


def is_dcgm_service_installed() -> bool:
    """Check if the DCGM exporter systemd service is installed and enabled.

    Returns:
        True if the service file exists in systemd and is enabled.
    """
    service_path = _SYSTEMD_SYSTEM_DIR / DCGM_SERVICE_NAME
    if not service_path.exists():
        return False

    # Check if enabled
    result = subprocess.run(
        ["systemctl", "is-enabled", DCGM_SERVICE_NAME],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def is_dcgm_service_running() -> bool:
    """Check if the DCGM exporter systemd service is currently running.

    Returns:
        True if the service is active (running).
    """
    result = subprocess.run(
        ["systemctl", "is-active", DCGM_SERVICE_NAME],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def install_dcgm_exporter_service(project_root: str | Path) -> bool:
    """Install the DCGM exporter as a system-level systemd service.

    Copies the service template to /etc/systemd/system/, substitutes
    the project root path, reloads systemd, and enables the service.

    Requires sudo access.

    Args:
        project_root: Root directory of the project (for custom-counters.csv path).

    Returns:
        True if installation succeeded, False otherwise.
    """
    project_root = Path(project_root).resolve()
    template_path = _get_service_template_path(project_root)

    if not template_path.exists():
        print(f"  Error: Service template not found: {template_path}")
        return False

    # Read template and substitute project root
    template_content = template_path.read_text()
    service_content = template_content.replace(_PROJECT_ROOT_PLACEHOLDER, str(project_root))

    # Write to a temporary file, then sudo cp to systemd directory
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".service", delete=False) as tmp:
        tmp.write(service_content)
        tmp_path = tmp.name

    try:
        dest = str(_SYSTEMD_SYSTEM_DIR / DCGM_SERVICE_NAME)

        # Copy service file to systemd directory
        result = _run_sudo(["cp", tmp_path, dest], check=False)
        if result.returncode != 0:
            print(f"  Error copying service file: {result.stderr.strip()}")
            return False

        # Set proper permissions (644 for systemd service files)
        _run_sudo(["chmod", "644", dest], check=False)

        # Reload systemd daemon
        result = _run_sudo(["systemctl", "daemon-reload"], check=False)
        if result.returncode != 0:
            print(f"  Error reloading systemd: {result.stderr.strip()}")
            return False

        # Enable the service (starts on boot)
        result = _run_sudo(["systemctl", "enable", DCGM_SERVICE_NAME], check=False)
        if result.returncode != 0:
            print(f"  Error enabling service: {result.stderr.strip()}")
            return False

        # Start the service now
        result = _run_sudo(["systemctl", "start", DCGM_SERVICE_NAME], check=False)
        if result.returncode != 0:
            print(f"  Warning: Service failed to start: {result.stderr.strip()}")
            print("  The service will attempt to start on next boot.")
            # Don't return False — installation succeeded even if start failed

        return True
    finally:
        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)


def uninstall_dcgm_exporter_service() -> bool:
    """Uninstall the DCGM exporter systemd service.

    Stops the service, disables it, removes the service file, and reloads systemd.

    Requires sudo access.

    Returns:
        True if uninstallation succeeded, False otherwise.
    """
    if not is_dcgm_service_installed():
        print("  DCGM exporter service is not installed.")
        return True

    # Stop the service
    _run_sudo(["systemctl", "stop", DCGM_SERVICE_NAME], check=False)

    # Disable the service
    _run_sudo(["systemctl", "disable", DCGM_SERVICE_NAME], check=False)

    # Remove the service file
    dest = str(_SYSTEMD_SYSTEM_DIR / DCGM_SERVICE_NAME)
    _run_sudo(["rm", "-f", dest], check=False)

    # Reload systemd daemon
    _run_sudo(["systemctl", "daemon-reload"], check=False)

    print("  DCGM exporter service uninstalled.")
    return True


def prompt_and_install_dcgm_service(project_root: str | Path, auto_install: bool = False) -> bool:
    """Interactive prompt to install the DCGM exporter systemd service.

    Checks for NVIDIA GPU presence, then offers to install the service.
    Skips if no GPU is detected or if already installed.

    Args:
        project_root: Root directory of the project.
        auto_install: If True, install automatically without prompting.

    Returns:
        True if service is installed (or was already installed), False if skipped.
    """
    # Check if NVIDIA GPU is available
    if not shutil.which("nvidia-smi"):
        return False

    # Check if systemd is available
    if not shutil.which("systemctl"):
        return False

    # Check if already installed and running
    if is_dcgm_service_installed():
        if is_dcgm_service_running():
            print("  DCGM exporter service: already installed and running")
        else:
            print("  DCGM exporter service: installed but not running, starting...")
            _run_sudo(["systemctl", "start", DCGM_SERVICE_NAME], check=False)
        return True

    print()
    print("=" * 60)
    print("GPU Hardware Metrics (DCGM Exporter)")
    print("=" * 60)
    print()
    print("NVIDIA DCGM Exporter provides detailed GPU hardware metrics:")
    print("  - SM/memory utilization, temperature, power consumption")
    print("  - PCIe throughput, ECC errors, clock frequencies")
    print("  - Exposed at :9400/metrics for Prometheus/Grafana")
    print()
    print("DCGM requires host-level root access (rootful Podman).")
    print("This will install a system-level systemd service.")
    print()

    # Auto-install if requested
    if auto_install:
        answer = "y"
        print("Auto-installing DCGM exporter service...")
    else:
        try:
            answer = input("Install DCGM exporter service? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False

    if answer in ("n", "no"):
        print("  Skipped. You can install later with:")
        print("    sudo cp monitoring/dcgm/dcgm-exporter.service /etc/systemd/system/")
        print("    sudo systemctl daemon-reload && sudo systemctl enable --now dcgm-exporter")
        return False

    print("  Installing DCGM exporter service (requires sudo)...")
    success = install_dcgm_exporter_service(project_root)

    if success:
        print("  DCGM exporter service installed and enabled.")
        # Verify it's running
        if is_dcgm_service_running():
            print("  Status: running (metrics at http://localhost:9400/metrics)")
        else:
            print("  Status: installed (will start on next boot)")
    else:
        print("  Failed to install DCGM exporter service.")
        print("  You can install manually:")
        print("    sudo cp monitoring/dcgm/dcgm-exporter.service /etc/systemd/system/")
        print("    sudo systemctl daemon-reload && sudo systemctl enable --now dcgm-exporter")

    return success
