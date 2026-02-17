"""Rootful Podman service management and host configuration for setup.py.

Manages system-level services that require host-level root access
and cannot run under rootless Podman. Also configures host-level
security limits required by rootless containers.

Currently handles:

- DCGM Exporter: NVIDIA GPU hardware metrics (requires root for nv-hostengine)
- cAdvisor: Container metrics (requires privileged access to cgroups v2)
- Memlock limits: eBPF profiling in Grafana Alloy requires unlimited memlock

Usage:
    from setup_lib.rootful_services import (
        configure_memlock_limits,
        install_cadvisor_service,
        install_dcgm_exporter_service,
        is_dcgm_service_installed,
        prompt_and_install_dcgm_service,
        prompt_and_install_rootful_services,
        uninstall_dcgm_exporter_service,
    )
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# Systemd system-level service directory
_SYSTEMD_SYSTEM_DIR = Path("/etc/systemd/system")

# Service name constants
DCGM_SERVICE_NAME = "dcgm-exporter.service"
CADVISOR_SERVICE_NAME = "cadvisor.service"

# Template placeholder for project root path
_PROJECT_ROOT_PLACEHOLDER = "__PROJECT_ROOT__"

# Memlock limits configuration
_MEMLOCK_LIMITS_PATH = Path("/etc/security/limits.d/50-memlock.conf")


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


# ---------------------------------------------------------------------------
# Generic systemd service helpers
# ---------------------------------------------------------------------------


def _is_service_installed(service_name: str) -> bool:
    """Check if a systemd service is installed and enabled."""
    service_path = _SYSTEMD_SYSTEM_DIR / service_name
    if not service_path.exists():
        return False
    result = subprocess.run(
        ["systemctl", "is-enabled", service_name],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _is_service_running(service_name: str) -> bool:
    """Check if a systemd service is currently running."""
    result = subprocess.run(
        ["systemctl", "is-active", service_name],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _install_systemd_service(
    service_name: str,
    template_path: Path,
    *,
    project_root: Path | None = None,
) -> bool:
    """Install a systemd service from a template file.

    Args:
        service_name: Name of the systemd service (e.g. "cadvisor.service").
        template_path: Path to the service template file.
        project_root: If provided, replaces __PROJECT_ROOT__ placeholder.

    Returns:
        True if installation succeeded, False otherwise.
    """
    if not template_path.exists():
        print(f"  Error: Service template not found: {template_path}")
        return False

    template_content = template_path.read_text()
    if project_root:
        service_content = template_content.replace(
            _PROJECT_ROOT_PLACEHOLDER, str(project_root.resolve())
        )
    else:
        service_content = template_content

    with tempfile.NamedTemporaryFile(mode="w", suffix=".service", delete=False) as tmp:
        tmp.write(service_content)
        tmp_path = tmp.name

    try:
        dest = str(_SYSTEMD_SYSTEM_DIR / service_name)

        result = _run_sudo(["cp", tmp_path, dest], check=False)
        if result.returncode != 0:
            print(f"  Error copying service file: {result.stderr.strip()}")
            return False

        _run_sudo(["chmod", "644", dest], check=False)

        result = _run_sudo(["systemctl", "daemon-reload"], check=False)
        if result.returncode != 0:
            print(f"  Error reloading systemd: {result.stderr.strip()}")
            return False

        result = _run_sudo(["systemctl", "enable", service_name], check=False)
        if result.returncode != 0:
            print(f"  Error enabling service: {result.stderr.strip()}")
            return False

        result = _run_sudo(["systemctl", "start", service_name], check=False)
        if result.returncode != 0:
            print(f"  Warning: Service failed to start: {result.stderr.strip()}")
            print("  The service will attempt to start on next boot.")

        return True
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Memlock limits (required for Grafana Alloy eBPF profiling)
# ---------------------------------------------------------------------------


def is_memlock_configured() -> bool:
    """Check if memlock limits are configured for the current user.

    Returns:
        True if the memlock limits file exists with the correct content.
    """
    if not _MEMLOCK_LIMITS_PATH.exists():
        return False
    try:
        content = _MEMLOCK_LIMITS_PATH.read_text()
        username = os.environ.get("USER", "")
        return username in content and "memlock" in content
    except PermissionError:
        # File exists but we can't read it — assume it's configured
        return True


def configure_memlock_limits() -> bool:
    """Configure memlock limits for eBPF profiling.

    Creates /etc/security/limits.d/50-memlock.conf to allow the current
    user to lock unlimited memory, required by Grafana Alloy's eBPF
    profiler for native C/C++ profiling (llama.cpp, etc.).

    Requires sudo access. A re-login is needed for limits to take effect.

    Returns:
        True if configuration succeeded, False otherwise.
    """
    username = os.environ.get("USER", "")
    if not username:
        print("  Error: Could not determine current username")
        return False

    content = (
        "# Allow rootless Podman containers to lock memory for eBPF profiling (Grafana Alloy)\n"
        "# Required by pyroscope.ebpf component for native C/C++ profiling (llama.cpp, etc.)\n"
        "# Installed by setup.py — see monitoring/alloy/ for details\n"
        f"{username} soft memlock unlimited\n"
        f"{username} hard memlock unlimited\n"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        dest = str(_MEMLOCK_LIMITS_PATH)
        result = _run_sudo(["cp", tmp_path, dest], check=False)
        if result.returncode != 0:
            print(f"  Error writing limits file: {result.stderr.strip()}")
            return False

        _run_sudo(["chmod", "644", dest], check=False)
        return True
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# DCGM Exporter (existing functions, preserved for backward compatibility)
# ---------------------------------------------------------------------------


def is_dcgm_service_installed() -> bool:
    """Check if the DCGM exporter systemd service is installed and enabled."""
    return _is_service_installed(DCGM_SERVICE_NAME)


def is_dcgm_service_running() -> bool:
    """Check if the DCGM exporter systemd service is currently running."""
    return _is_service_running(DCGM_SERVICE_NAME)


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
    return _install_systemd_service(DCGM_SERVICE_NAME, template_path, project_root=project_root)


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


# ---------------------------------------------------------------------------
# cAdvisor (container metrics — rootful systemd service)
# ---------------------------------------------------------------------------


def is_cadvisor_service_installed() -> bool:
    """Check if the cAdvisor systemd service is installed and enabled."""
    return _is_service_installed(CADVISOR_SERVICE_NAME)


def is_cadvisor_service_running() -> bool:
    """Check if the cAdvisor systemd service is currently running."""
    return _is_service_running(CADVISOR_SERVICE_NAME)


def install_cadvisor_service(project_root: str | Path) -> bool:
    """Install cAdvisor as a system-level systemd service.

    Args:
        project_root: Root directory of the project.

    Returns:
        True if installation succeeded, False otherwise.
    """
    template_path = Path(project_root) / "monitoring" / "cadvisor" / "cadvisor.service"
    return _install_systemd_service(CADVISOR_SERVICE_NAME, template_path)


# ---------------------------------------------------------------------------
# Combined installer for all rootful services + host config
# ---------------------------------------------------------------------------


def prompt_and_install_rootful_services(
    project_root: str | Path, *, auto_install: bool = False
) -> None:
    """Install all rootful systemd services and host-level configuration.

    Handles:
    1. Memlock limits for eBPF profiling (Grafana Alloy)
    2. cAdvisor systemd service (container metrics)
    3. DCGM Exporter is handled separately (GPU-dependent)

    Args:
        project_root: Root directory of the project.
        auto_install: If True, install automatically without prompting.
    """
    if not shutil.which("systemctl"):
        return

    project_root = Path(project_root).resolve()

    # --- Memlock limits ---
    if is_memlock_configured():
        print("  Memlock limits: already configured")
    else:
        print()
        print("=" * 60)
        print("eBPF Profiling (Memlock Limits)")
        print("=" * 60)
        print()
        print("Grafana Alloy's eBPF profiler needs unlimited memlock to")
        print("profile native C/C++ services (llama.cpp, Triton, etc.).")
        print("This creates /etc/security/limits.d/50-memlock.conf")
        print()
        print("NOTE: A re-login is required for the new limits to take effect.")
        print()

        if auto_install:
            answer = "y"
            print("Auto-configuring memlock limits...")
        else:
            try:
                answer = input("Configure memlock limits? [Y/n] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                answer = "n"

        if answer not in ("n", "no"):
            print("  Configuring memlock limits (requires sudo)...")
            if configure_memlock_limits():
                print("  Memlock limits configured.")
                print("  NOTE: Re-login required for limits to take effect.")
            else:
                print("  Failed. Configure manually:")
                print("    sudo tee /etc/security/limits.d/50-memlock.conf <<< \\")
                print('      "$(whoami) soft memlock unlimited\\n$(whoami) hard memlock unlimited"')

    # --- cAdvisor ---
    if is_cadvisor_service_installed():
        if is_cadvisor_service_running():
            print("  cAdvisor service: already installed and running")
        else:
            print("  cAdvisor service: installed but not running, starting...")
            _run_sudo(["systemctl", "start", CADVISOR_SERVICE_NAME], check=False)
    else:
        print()
        print("=" * 60)
        print("Container Metrics (cAdvisor)")
        print("=" * 60)
        print()
        print("cAdvisor provides container resource usage metrics:")
        print("  - CPU, memory, disk, network per container")
        print("  - Exposed at :8088/metrics for Prometheus/Grafana")
        print()
        print("cAdvisor requires privileged host access (rootful Podman).")
        print("This will install a system-level systemd service.")
        print()

        if auto_install:
            answer = "y"
            print("Auto-installing cAdvisor service...")
        else:
            try:
                answer = input("Install cAdvisor service? [Y/n] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                answer = "n"

        if answer not in ("n", "no"):
            print("  Installing cAdvisor service (requires sudo)...")
            if install_cadvisor_service(project_root):
                print("  cAdvisor service installed and enabled.")
                if is_cadvisor_service_running():
                    print("  Status: running (metrics at http://localhost:8088/metrics)")
                else:
                    print("  Status: installed (will start on next boot)")
            else:
                print("  Failed. Install manually:")
                print("    sudo cp monitoring/cadvisor/cadvisor.service /etc/systemd/system/")
                print("    sudo systemctl daemon-reload && sudo systemctl enable --now cadvisor")
