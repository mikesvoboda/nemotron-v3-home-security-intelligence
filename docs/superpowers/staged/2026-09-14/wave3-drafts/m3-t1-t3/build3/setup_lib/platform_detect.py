"""Platform detection for setup.py.

Provides cross-platform detection of operating system, Linux distribution,
package managers, and WSL environment. Used by setup.py to determine
appropriate installation commands.

Usage:
    from setup_lib.platform_detect import get_platform_info

    info = get_platform_info()
    if info:
        print(f"Platform: {info['platform']}")
        print(f"Package manager: {info['package_manager']}")
"""

from __future__ import annotations

import platform
import shutil
from pathlib import Path
from typing import TypedDict


class DistroInfo(TypedDict, total=False):
    """Linux distribution information from /etc/os-release."""

    id: str
    id_like: str
    name: str
    version_id: str
    pretty_name: str


class PlatformInfo(TypedDict):
    """Complete platform information."""

    platform: str
    distro: DistroInfo | None
    package_manager: str | None
    is_wsl: bool


def detect_platform() -> str | None:
    """Detect the current operating system.

    Returns:
        'linux', 'windows', or None for unsupported platforms (macOS).
    """
    system = platform.system()
    if system == "Linux":
        return "linux"
    if system == "Windows":
        return "windows"
    # macOS (Darwin) is not supported due to lack of NVIDIA CUDA
    return None


def detect_linux_distro() -> DistroInfo | None:
    """Detect Linux distribution from /etc/os-release.

    Parses the standard /etc/os-release file to identify the Linux
    distribution and its key attributes.

    Returns:
        DistroInfo dict with id, name, version_id, etc. or None if not found.
    """
    os_release_path = Path("/etc/os-release")

    if not os_release_path.exists():
        return None

    try:
        content = os_release_path.read_text()
    except OSError:
        return None

    distro: DistroInfo = {}

    for raw_line in content.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line or "=" not in stripped_line:
            continue

        key, _, value = stripped_line.partition("=")
        key = key.lower()

        # Remove quotes from value
        value = value.strip("\"'")

        if key == "id":
            distro["id"] = value
        elif key == "id_like":
            distro["id_like"] = value
        elif key == "name":
            distro["name"] = value
        elif key == "version_id":
            distro["version_id"] = value
        elif key == "pretty_name":
            distro["pretty_name"] = value

    return distro if distro else None


def detect_package_manager() -> str | None:
    """Detect available package manager.

    Checks for common package managers in order of preference:
    - dnf (Fedora, RHEL)
    - apt (Debian, Ubuntu)
    - pacman (Arch)
    - winget (Windows)

    Returns:
        Package manager name or None if not found.
    """
    # Order matters: check more specific first
    package_managers = ["dnf", "apt", "pacman", "winget"]

    for pm in package_managers:
        if shutil.which(pm):
            return pm

    return None


def is_wsl() -> bool:
    """Detect if running under Windows Subsystem for Linux.

    Checks /proc/version for Microsoft or WSL indicators.

    Returns:
        True if running in WSL, False otherwise.
    """
    proc_version = Path("/proc/version")

    if not proc_version.exists():
        return False

    try:
        content = proc_version.read_text().lower()
        return "microsoft" in content or "wsl" in content
    except OSError:
        return False


def get_distro_family(distro: DistroInfo | None) -> str:
    """Determine the distribution family for installation commands.

    Maps specific distributions to their family for determining
    which package manager commands to use.

    Args:
        distro: Distribution info from detect_linux_distro().

    Returns:
        'fedora', 'debian', 'arch', or 'unknown'.
    """
    if not distro:
        return "unknown"

    distro_id = distro.get("id", "")
    id_like = distro.get("id_like", "")

    # Map of family identifiers to family name
    families = {
        "fedora": ("fedora", "rhel", "centos", "rocky", "almalinux"),
        "debian": ("debian", "ubuntu", "linuxmint", "pop"),
        "arch": ("arch", "manjaro", "endeavouros"),
    }

    # Check direct ID first, then ID_LIKE
    for family, identifiers in families.items():
        if distro_id in identifiers:
            return family
        if any(
            ident in id_like for ident in identifiers[:2]
        ):  # Check first 2 identifiers in id_like
            return family

    return "unknown"


def get_platform_info() -> PlatformInfo | None:
    """Get complete platform information.

    Aggregates all platform detection into a single info structure.

    Returns:
        PlatformInfo dict or None for unsupported platforms.
    """
    plat = detect_platform()
    if plat is None:
        return None

    distro = None
    wsl = False

    if plat == "linux":
        distro = detect_linux_distro()
        wsl = is_wsl()

    return PlatformInfo(
        platform=plat,
        distro=distro,
        package_manager=detect_package_manager(),
        is_wsl=wsl,
    )


def print_platform_info() -> None:
    """Print detected platform information for debugging."""
    info = get_platform_info()

    if info is None:
        print("! Unsupported platform (only Linux and Windows are supported)")
        return

    print(f"Platform: {info['platform']}")

    if info["distro"]:
        distro = info["distro"]
        family = get_distro_family(distro)
        print(f"Distribution: {distro.get('pretty_name', distro.get('id', 'Unknown'))}")
        print(f"Distribution ID: {distro.get('id', 'Unknown')}")
        print(f"Distribution Family: {family}")
        if distro.get("version_id"):
            print(f"Version: {distro['version_id']}")

    if info["package_manager"]:
        print(f"Package Manager: {info['package_manager']}")
    else:
        print("Package Manager: Not detected")

    if info["is_wsl"]:
        print("WSL: Yes (Windows Subsystem for Linux)")


if __name__ == "__main__":
    print_platform_info()
