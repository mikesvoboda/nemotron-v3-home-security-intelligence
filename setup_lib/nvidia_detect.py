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

import os
import shutil
import subprocess
from pathlib import Path
from typing import TypedDict

# Prevent apt/dpkg from prompting (causes hang in non-interactive setup).
# Use env to set DEBIAN_FRONTEND before sudo; sudo strips env by default.
_APT_ENV = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
_SUDO = ["env", "DEBIAN_FRONTEND=noninteractive", "sudo", "-E"]

# Minimum driver version for CUDA 13.1 compatibility
# CUDA 13.x requires driver 580+ (ai-llm container uses CUDA 13.1.1)
MINIMUM_DRIVER_VERSION = 580


def fix_broken_apt_if_needed() -> bool:
    """Fix broken apt state (e.g. from failed nvidia installs) before any package installs.

    Run this at the start of setup so podman and other installs can succeed.
    Purges nvidia packages FIRST so apt --fix-broken does not "fix" by installing
    nvidia-driver-565 (we want 580+ for CUDA 13.1). Returns True.
    """
    if not shutil.which("apt"):
        return True

    apt_cmd = _SUDO + [
        "apt", "--fix-broken", "install", "-y",
        "-o", "Dpkg::Options::=--force-confdef",
        "-o", "Dpkg::Options::=--force-confold",
    ]

    # Only purge nvidia packages when driver is insufficient (< 580) or missing.
    # If we already have 580+, keep it — don't remove a working driver.
    print("  [apt] Checking for nvidia packages in dpkg...", flush=True)
    nvidia_pkgs = _get_nvidia_packages_from_dpkg()
    print(f"  [apt] Found {len(nvidia_pkgs)} nvidia packages", flush=True)
    if nvidia_pkgs:
        driver_version = get_driver_version()
        if is_driver_version_sufficient(driver_version):
            print(f"  [apt] Driver {driver_version or '?'} >= {MINIMUM_DRIVER_VERSION} — skipping purge", flush=True)
        else:
            _purge_broken_nvidia_packages()

    # Now fix-broken (no nvidia to "fix" with 565; just cleans orphans etc.)
    print("  [apt] Running: apt --fix-broken install -y (streaming output, timeout 300s)...", flush=True)
    r = subprocess.run(
        apt_cmd,  # noqa: S603, S607
        capture_output=False,
        check=False,
        timeout=300,
        env=_APT_ENV,
    )
    print(f"  [apt] apt --fix-broken done (rc={r.returncode})", flush=True)
    print("  [apt] fix_broken_apt_if_needed complete", flush=True)
    return True


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

    Tries nvidia-smi first. If not available (e.g. driver purged), falls back to lspci.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=gpu_name", "--format=csv,noheader"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0:
            return True
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired):
        pass

    # Fallback: lspci when nvidia-smi unavailable (e.g. after driver purge)
    try:
        result = subprocess.run(
            ["lspci"],  # noqa: S603, S607
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and "NVIDIA" in result.stdout:
            return True
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired):
        pass
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


def _ensure_ubuntu_repos_enabled() -> None:
    """Enable restricted, universe, multiverse (libnvidia-* packages are in restricted)."""
    if not shutil.which("add-apt-repository"):
        subprocess.run(
            ["sudo", "apt", "install", "-y", "software-properties-common"],  # noqa: S603, S607
            capture_output=True,
            check=False,
            timeout=120,
        )
    for component in ["restricted", "universe", "multiverse"]:
        subprocess.run(
            ["sudo", "add-apt-repository", "-y", component],  # noqa: S603, S607
            capture_output=True,
            check=False,
            timeout=30,
        )
    subprocess.run(
        ["sudo", "apt", "update"],  # noqa: S603, S607
        capture_output=True,
        check=False,
        timeout=120,
    )


def _get_nvidia_packages_from_dpkg() -> list[str]:
    """Get all nvidia/cuda-driver packages from dpkg -l.

    Includes nvidia, libnvidia, xserver-xorg-video-nvidia, and cuda-drivers-*
    (cuda-drivers-565, cuda-drivers-fabricmanager-565) which pull in nvidia-565.
    Includes any status (ii, rc, iF, iU, etc.) to catch half-installed or broken.
    """
    result = subprocess.run(
        ["dpkg", "-l"],  # noqa: S603, S607
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if result.returncode != 0:
        return []

    pkgs = []
    for line in result.stdout.splitlines():
        if len(line) < 10:
            continue
        # Exclude packages not on system (status xx where x[1]='n' = not installed)
        if len(line) >= 2 and line[1] == "n":
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        pkg = parts[1]
        if (
            pkg.startswith("nvidia-")
            or pkg.startswith("libnvidia-")
            or pkg.startswith("xserver-xorg-video-nvidia-")
            or pkg.startswith("cuda-drivers-")
        ):
            pkgs.append(pkg)
    # Purge cuda-drivers-* first (meta-packages), then nvidia (dependencies)
    return sorted(pkgs, key=lambda p: (0 if p.startswith("cuda-drivers-") else 1, p))


def _purge_broken_nvidia_packages() -> bool:
    """Remove installed nvidia/libnvidia packages to resolve conflicts.

    Uses dpkg --purge --force when apt purge fails. Runs multiple passes until
    no packages remain (dpkg may need several passes for dependency order).
    Returns True if purge was attempted.
    """
    purged_any = False
    for pass_num in range(5):  # Max 5 passes
        nvidia_pkgs = _get_nvidia_packages_from_dpkg()
        if not nvidia_pkgs:
            break

        if pass_num == 0:
            print("  [purge] Purging conflicting nvidia packages for clean install...", flush=True)

        # Unhold
        print(f"  [purge] Unholding {len(nvidia_pkgs)} packages...", flush=True)
        for pkg in nvidia_pkgs:
            subprocess.run(
                _SUDO + ["apt-mark", "unhold", pkg],  # noqa: S603, S607
                capture_output=True,
                check=False,
                timeout=5,
                env=_APT_ENV,
            )

        # Try apt purge first (only on first pass)
        if pass_num == 0:
            print("  [purge] Trying apt purge...", flush=True)
            purge_result = subprocess.run(
                _SUDO + ["apt", "purge", "-y", "--allow-change-held-packages"] + nvidia_pkgs,  # noqa: S603, S607
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
                env=_APT_ENV,
            )
            if purge_result.returncode == 0:
                print("  [purge] apt purge succeeded", flush=True)
                purged_any = True
                print("  [purge] Running apt --fix-broken after purge...", flush=True)
                subprocess.run(
                    _SUDO + ["apt", "--fix-broken", "install", "-y"],  # noqa: S603, S607
                    capture_output=True,
                    check=False,
                    timeout=120,
                    env=_APT_ENV,
                )
                continue
            print("  [purge] apt purge failed, using dpkg force-purge...", flush=True)

        # Force-purge with dpkg (--force-breaks allows breaking dependents)
        if pass_num > 0:
            print("  Additional pass to remove remaining packages...")
        for pkg in nvidia_pkgs:
            print(f"    Purging {pkg}...", flush=True)
            r = subprocess.run(
                _SUDO
                + [
                    "dpkg",
                    "--purge",
                    "--force-remove-reinstreq",
                    "--force-depends",
                    "--force-breaks",
                    "--no-triggers",
                    pkg,
                ],  # noqa: S603, S607
                capture_output=True,
                check=False,
                timeout=60,
                env=_APT_ENV,
            )
            if r.returncode == 0:
                purged_any = True

        # Fix broken state between passes
        subprocess.run(
            _SUDO + ["apt", "--fix-broken", "install", "-y"],  # noqa: S603, S607
            capture_output=True,
            check=False,
            timeout=120,
            env=_APT_ENV,
        )

    # Run pending triggers (skipped by --no-triggers during purge)
    print("  [purge] Running dpkg --configure -a...", flush=True)
    subprocess.run(
        _SUDO + ["dpkg", "--configure", "-a", "--force-confold"],
        capture_output=True,
        check=False,
        timeout=180,
        env=_APT_ENV,
    )
    print("  [purge] Running apt --fix-broken...", flush=True)
    subprocess.run(
        _SUDO + ["apt", "--fix-broken", "install", "-y"],  # noqa: S603, S607
        capture_output=True,
        check=False,
        timeout=120,
        env=_APT_ENV,
    )
    print("  [purge] Running apt autoremove...", flush=True)
    subprocess.run(
        _SUDO + ["apt", "autoremove", "-y"],  # noqa: S603, S607
        capture_output=True,
        check=False,
        timeout=60,
        env=_APT_ENV,
    )
    print("  [purge] Running apt update...", flush=True)
    subprocess.run(
        _SUDO + ["apt", "update"],  # noqa: S603, S607
        capture_output=True,
        check=False,
        timeout=120,
        env=_APT_ENV,
    )
    print("  [purge] Purge complete", flush=True)
    return purged_any


def _warn_driver_upgrade_failed(version: str | None) -> None:
    """Print warning when driver upgrade did not meet requirements."""
    print(
        f"  WARNING: Driver version still {version or 'unknown'} "
        f"(>= {MINIMUM_DRIVER_VERSION} required). Reboot may be needed, or use CUDA 12.x in ai-llm."
    )


def _run_grub_update() -> None:
    """Regenerate GRUB menu after driver/kernel install."""
    if shutil.which("update-grub"):
        print("  Regenerating GRUB menu (new kernel installed)...")
        subprocess.run(["sudo", "update-grub"], check=False, timeout=60)  # noqa: S603, S607
    elif shutil.which("grub2-mkconfig"):
        print("  Regenerating GRUB menu (new kernel installed)...")
        grub_cfg = "/boot/efi/EFI/fedora/grub.cfg" if Path("/sys/firmware/efi").is_dir() else "/boot/grub2/grub.cfg"
        subprocess.run(["sudo", "grub2-mkconfig", "-o", grub_cfg], check=False, timeout=60)  # noqa: S603, S607


def _run_apt_nvidia_driver() -> bool:
    """Fallback: install nvidia-driver via apt (Ubuntu/Debian).

    Handles broken apt state, repo enablement, and conflicts by trying:
    1. apt --fix-broken install
    2. Enable restricted/universe/multiverse (libnvidia-* in restricted)
    3. nvidia-driver meta-package and versioned packages
    4. Purge conflicting nvidia packages and retry (clean install)
    5. Add graphics-drivers PPA and retry
    """
    # Fix broken apt state first
    print("  Fixing broken apt dependencies (if any)...")
    subprocess.run(
        ["sudo", "apt", "--fix-broken", "install", "-y"],  # noqa: S603, S607
        capture_output=True,
        check=False,
        timeout=300,
    )

    def _try_packages(pkgs: list[str], no_install_recommends: bool = False) -> bool:
        extra = ["--no-install-recommends"] if no_install_recommends else []
        for pkg in pkgs:
            print(f"  Running: sudo apt install -y {' '.join(extra)} {pkg}")
            result = subprocess.run(
                ["sudo", "apt", "install", "-y"] + extra + [pkg],  # noqa: S603, S607
                check=False,
                timeout=600,
            )
            if result.returncode == 0:
                _run_grub_update()
                return True
        return False

    packages = [
        "nvidia-driver",
        "nvidia-driver-580",
        "nvidia-driver-550",
        "nvidia-driver-535",
    ]

    # Enable restricted/universe/multiverse (libnvidia-* packages live in restricted)
    print("  Ensuring restricted/universe/multiverse repos are enabled...")
    _ensure_ubuntu_repos_enabled()

    # Purge conflicting nvidia packages first (resolves "not installable" / Conflicts / held)
    # Do this before install attempts to avoid dependency cycles
    if _purge_broken_nvidia_packages():
        subprocess.run(["sudo", "apt", "update"], capture_output=True, check=False, timeout=120)  # noqa: S603, S607

    if _try_packages(packages):
        return True

    # Retry without recommends (skips i386 libs that may be "not installable" on cloud images)
    print("  Retrying with --no-install-recommends (skip i386 libs)...")
    if _try_packages(packages, no_install_recommends=True):
        return True

    # Add NVIDIA graphics-drivers PPA for newer drivers (580+ for CUDA 13.1)
    if shutil.which("add-apt-repository"):
        print("  Adding graphics-drivers PPA (newer drivers for CUDA 13.1)...")
        ppa_result = subprocess.run(
            ["sudo", "add-apt-repository", "-y", "ppa:graphics-drivers/ppa"],  # noqa: S603, S607
            check=False,
            timeout=60,
        )
        if ppa_result.returncode == 0:
            print("  Running: sudo apt update")
            subprocess.run(
                ["sudo", "apt", "update"],  # noqa: S603, S607
                check=False,
                timeout=120,
            )
            ppa_packages = ["nvidia-driver-580", "nvidia-driver", "nvidia-driver-550", "nvidia-driver-535"]
            if _try_packages(ppa_packages):
                return True
            if _try_packages(ppa_packages, no_install_recommends=True):
                return True

    return False


def _run_driver_upgrade(distro_family: str, *, is_ubuntu: bool = False) -> bool:
    """Run the NVIDIA driver upgrade command for the current platform.

    Args:
        distro_family: Distribution family ('fedora', 'debian', 'arch').
        is_ubuntu: Whether the system is specifically Ubuntu.

    Returns:
        True if upgrade succeeded, False otherwise.
    """
    if distro_family == "debian" and is_ubuntu:
        # Fix broken apt state and ensure repos (restricted has libnvidia-*)
        subprocess.run(
            ["sudo", "apt", "--fix-broken", "install", "-y"],  # noqa: S603, S607
            capture_output=True,
            check=False,
            timeout=300,
        )
        _ensure_ubuntu_repos_enabled()
        # ubuntu-drivers is provided by ubuntu-drivers-common; not installed on minimal/cloud images
        if not shutil.which("ubuntu-drivers"):
            print("  Installing ubuntu-drivers-common (provides ubuntu-drivers)...")
            install_common = subprocess.run(
                ["sudo", "apt", "install", "-y", "ubuntu-drivers-common"],  # noqa: S603, S607
                check=False,
                timeout=120,
            )
            if install_common.returncode != 0:
                print("  WARNING: ubuntu-drivers-common install failed — falling back to nvidia-driver")
                return _run_apt_nvidia_driver()
        print("  Running: sudo ubuntu-drivers install")
        result = subprocess.run(
            ["sudo", "ubuntu-drivers", "install"],  # noqa: S603, S607
            check=False,
            timeout=600,
        )
    else:
        cmd = get_driver_install_command(distro_family, is_ubuntu=is_ubuntu)
        if not cmd:
            print(f"  No driver install command available for '{distro_family}'")
            return False

        print(f"  Running: {cmd}")
        result = subprocess.run(
            cmd.split(),  # noqa: S603
            check=False,
            timeout=600,
        )

    if result.returncode != 0:
        if distro_family == "debian" and is_ubuntu:
            return _run_apt_nvidia_driver()
        return False

    _run_grub_update()
    return True


def _add_nvidia_container_toolkit_repo() -> bool:
    """Add NVIDIA Container Toolkit repo (package not in default Ubuntu repos)."""
    try:
        key_result = subprocess.run(
            [
                "curl",
                "-fsSL",
                "https://nvidia.github.io/libnvidia-container/gpgkey",
            ],  # noqa: S603, S607
            capture_output=True,
            check=False,
            timeout=30,
        )
        if key_result.returncode != 0:
            return False
        # Remove existing keyring to avoid "Overwrite? (y/N)" prompt
        subprocess.run(
            ["sudo", "rm", "-f", "/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg"],  # noqa: S603, S607
            capture_output=True,
            check=False,
        )
        gpg_result = subprocess.run(
            [
                "sudo",
                "gpg",
                "--batch",
                "--dearmor",
                "-o",
                "/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg",
            ],  # noqa: S603, S607
            input=key_result.stdout,
            capture_output=True,
            check=False,
            timeout=10,
        )
        if gpg_result.returncode != 0:
            return False
        list_result = subprocess.run(
            [
                "curl",
                "-sL",
                "https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list",
            ],  # noqa: S603, S607
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if list_result.returncode != 0:
            return False
        # Add signed-by and expand $(ARCH) for Ubuntu 24.04
        arch = subprocess.run(
            ["dpkg", "--print-architecture"],  # noqa: S603, S607
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        arch_str = arch.stdout.strip() if arch.returncode == 0 else "amd64"
        repo_content = list_result.stdout.replace(
            "deb https://",
            "deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://",
        ).replace("$(ARCH)", arch_str)
        proc = subprocess.run(
            ["sudo", "tee", "/etc/apt/sources.list.d/nvidia-container-toolkit.list"],
            input=repo_content.encode(),
            capture_output=True,
            check=False,
            timeout=5,
        )
        if proc.returncode != 0:
            return False
        subprocess.run(
            ["sudo", "apt", "update"],
            capture_output=True,
            check=False,
            timeout=120,
        )
        return True
    except Exception:
        return False


def _run_toolkit_install(distro_family: str) -> bool:
    """Run the NVIDIA Container Toolkit installation.

    Args:
        distro_family: Distribution family ('fedora', 'debian', 'arch').

    Returns:
        True if installation succeeded, False otherwise.
    """
    cmd = get_toolkit_install_command(distro_family)
    if not cmd:
        print(f"  No toolkit install command available for '{distro_family}'")
        return False

    # Debian/Ubuntu: add NVIDIA repo first (package not in default repos)
    if distro_family == "debian":
        print("  Adding NVIDIA Container Toolkit repo...")
        if not _add_nvidia_container_toolkit_repo():
            print("  WARNING: Failed to add NVIDIA Container Toolkit repo")
            return False

    print(f"  Running: {cmd}")
    result = subprocess.run(
        cmd.split(),  # noqa: S603
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    if result.returncode == 0:
        _run_toolkit_post_install()
        return True

    stderr = result.stderr or ""
    # Debian: if unmet dependencies, fix-broken and retry (e.g. after failed podman 5 upgrade)
    if distro_family == "debian" and (
        "Unmet dependencies" in stderr or "fix-broken" in stderr.lower()
    ):
        print("  Fixing broken apt state before retry...")
        subprocess.run(
            _SUDO + ["apt", "--fix-broken", "install", "-y"],
            capture_output=True,
            check=False,
            timeout=300,
            env=_APT_ENV,
        )
        print(f"  Retrying: {cmd}")
        result = subprocess.run(
            cmd.split(),  # noqa: S603
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        if result.returncode == 0:
            _run_toolkit_post_install()
            return True

    # Log failure for debugging
    if result.stderr:
        for line in result.stderr.strip().splitlines()[-5:]:
            print(f"    {line}", flush=True)
    return False


def _run_toolkit_post_install() -> None:
    """Regenerate CDI spec after toolkit install.

    May fail when no NVIDIA driver is installed (libnvidia-ml not found).
    CDI spec will be generated after driver install; non-fatal here.
    """
    r = subprocess.run(
        ["sudo", "nvidia-ctk", "cdi", "generate", "--output=/etc/cdi/nvidia.yaml"],  # noqa: S603, S607
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if r.returncode != 0 and "libnvidia-ml" in (r.stderr or ""):
        print("  (CDI spec deferred until driver is installed)")


def prompt_and_check_nvidia(config: dict[str, object]) -> bool:
    """Check NVIDIA GPU, driver version, and container toolkit.

    Detects GPU, driver version, and container toolkit. When auto_install
    is set in config, automatically upgrades the driver and installs the
    container toolkit if needed.

    Args:
        config: Configuration dictionary to update with detection results.
            If config['auto_install'] is True, performs upgrades automatically.

    Returns:
        True if GPU is detected (regardless of driver status), False otherwise.
    """
    from setup_lib.platform_detect import (
        detect_linux_distro,
        get_distro_family,
    )

    print("\n[NVIDIA GPU Detection]")

    if not is_nvidia_gpu_present():
        print("  No NVIDIA GPU detected (nvidia-smi not available)")
        config["gpu_detected"] = False
        return False

    config["gpu_detected"] = True
    auto_install = bool(config.get("auto_install"))

    # Detect platform for install commands
    distro = detect_linux_distro()
    distro_family = get_distro_family(distro)
    is_ubuntu = (distro or {}).get("id", "") == "ubuntu"

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

            if auto_install:
                print("  Upgrading NVIDIA driver...")
                upgraded = _run_driver_upgrade(distro_family, is_ubuntu=is_ubuntu)
                # Verify driver actually upgraded (ubuntu-drivers can return 0 despite apt errors)
                new_version = get_driver_version()
                if is_driver_version_sufficient(new_version):
                    print("  Driver upgrade complete")
                    config["driver_version"] = new_version
                    config["driver_needs_upgrade"] = False
                    config["driver_upgraded"] = True
                elif upgraded and distro_family == "debian" and is_ubuntu:
                    # ubuntu-drivers reported success but version unchanged — try PPA fallback
                    print("  ubuntu-drivers did not upgrade — trying graphics-drivers PPA...")
                    if _run_apt_nvidia_driver():
                        new_version = get_driver_version()
                        if is_driver_version_sufficient(new_version):
                            print("  Driver upgrade complete")
                            config["driver_version"] = new_version
                            config["driver_needs_upgrade"] = False
                            config["driver_upgraded"] = True
                        else:
                            _warn_driver_upgrade_failed(new_version)
                    else:
                        _warn_driver_upgrade_failed(new_version)
                elif upgraded:
                    _warn_driver_upgrade_failed(new_version)
                else:
                    print("  WARNING: Driver upgrade failed — GPU containers may not start")
            else:
                cmd = get_driver_install_command(distro_family, is_ubuntu=is_ubuntu)
                if cmd:
                    print(f"  To upgrade manually: {cmd}")
    else:
        config["driver_needs_upgrade"] = True
        print("  Driver Version: Unknown")

        if auto_install:
            print("  Installing NVIDIA driver...")
            upgraded = _run_driver_upgrade(distro_family, is_ubuntu=is_ubuntu)
            new_version = get_driver_version()
            if is_driver_version_sufficient(new_version):
                print("  Driver installed")
                config["driver_version"] = new_version
                config["driver_needs_upgrade"] = False
                config["driver_upgraded"] = True
                if is_container_toolkit_installed():
                    _run_toolkit_post_install()
            elif upgraded:
                print("  Driver packages installed — reboot required to load kernel module")
                config["driver_upgraded"] = True
                if is_container_toolkit_installed():
                    _run_toolkit_post_install()
            elif distro_family == "debian" and is_ubuntu:
                print("  ubuntu-drivers did not install — trying graphics-drivers PPA...")
                if _run_apt_nvidia_driver():
                    new_version = get_driver_version()
                    if is_driver_version_sufficient(new_version):
                        print("  Driver installed")
                        config["driver_version"] = new_version
                        config["driver_needs_upgrade"] = False
                        config["driver_upgraded"] = True
                        if is_container_toolkit_installed():
                            _run_toolkit_post_install()
                    else:
                        print("  Driver packages installed — reboot required to load kernel module")
                        config["driver_upgraded"] = True
                        if is_container_toolkit_installed():
                            _run_toolkit_post_install()
                else:
                    print("  WARNING: Driver install failed — GPU containers may not start")
            else:
                print("  WARNING: Driver install failed — GPU containers may not start")
        else:
            cmd = get_driver_install_command(distro_family, is_ubuntu=is_ubuntu)
            if cmd:
                print(f"  To install manually: {cmd}")

    # Check container toolkit
    toolkit_installed = is_container_toolkit_installed()
    config["toolkit_installed"] = toolkit_installed

    if toolkit_installed:
        print("  Container Toolkit: Installed")
    else:
        print("  Container Toolkit: NOT INSTALLED")

        if auto_install:
            print("  Installing NVIDIA Container Toolkit...")
            if _run_toolkit_install(distro_family):
                print("  Container Toolkit installed")
                config["toolkit_installed"] = True
            else:
                print("  WARNING: Container Toolkit install failed — GPU passthrough may not work")
        else:
            cmd = get_toolkit_install_command(distro_family)
            if cmd:
                print(f"  To install manually: {cmd}")

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
