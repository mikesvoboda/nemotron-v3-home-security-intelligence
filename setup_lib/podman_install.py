"""Podman installation utilities for setup.py.

Provides cross-platform Podman detection, installation, and initialization.
Supports Fedora (dnf), Debian/Ubuntu (apt), Arch (pacman), and Windows (winget).

Usage:
    from setup_lib.podman_install import prompt_and_install_podman

    # Interactive installation with user prompt
    success = prompt_and_install_podman()

    # Auto-install without prompting
    success = prompt_and_install_podman(config={"auto_install": True})
"""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any

from setup_lib.platform_detect import PlatformInfo, get_platform_info


def is_podman_installed() -> bool:
    """Check if Podman is installed and available in PATH.

    Returns:
        True if podman executable is found in PATH, False otherwise.
    """
    return shutil.which("podman") is not None


def get_podman_version() -> str | None:
    """Get the installed Podman version.

    Runs 'podman --version' and parses the output to extract the version string.

    Returns:
        Version string (e.g., '5.3.1') or None if podman is not installed
        or version cannot be determined.
    """
    try:
        result = subprocess.run(
            ["podman", "--version"],  # noqa: S607 - known podman command
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None

        # Parse output like "podman version 5.3.1" or "podman version 5.3.1-dev"
        match = re.search(r"podman version\s+(\S+)", result.stdout)
        if match:
            return match.group(1)
        return None
    except FileNotFoundError:
        return None
    except OSError:
        return None


def get_install_command(platform_info: PlatformInfo) -> list[str] | None:
    """Get the platform-specific Podman installation command.

    Args:
        platform_info: Platform information from get_platform_info().

    Returns:
        List of command arguments for installation, or None if unsupported.
    """
    package_manager = platform_info.get("package_manager")

    if package_manager is None:
        return None

    if package_manager == "dnf":
        return ["sudo", "dnf", "install", "-y", "podman"]
    if package_manager == "apt":
        return ["sudo", "apt", "install", "-y", "podman"]
    if package_manager == "pacman":
        return ["sudo", "pacman", "-S", "--noconfirm", "podman"]
    if package_manager == "winget":
        return ["winget", "install", "-e", "--id", "RedHat.Podman"]

    # Unsupported package manager
    return None


def install_podman(platform_info: PlatformInfo) -> bool:
    """Install Podman using the system package manager.

    Args:
        platform_info: Platform information from get_platform_info().

    Returns:
        True if installation succeeded, False otherwise.
    """
    command = get_install_command(platform_info)
    if command is None:
        return False

    try:
        result = subprocess.run(command, check=False)  # noqa: S603 - command from get_install_command
        return result.returncode == 0
    except OSError:
        return False


def init_podman_machine() -> bool:
    """Initialize and start Podman machine (required on Windows).

    On Windows, Podman runs inside a virtual machine that must be initialized
    and started before containers can be run.

    Returns:
        True if machine was successfully initialized and started, False otherwise.
    """
    try:
        # Initialize the machine
        init_result = subprocess.run(
            ["podman", "machine", "init"],  # noqa: S607 - known podman command
            check=False,
        )

        # If init fails and it's not because machine already exists, try start anyway
        # Exit code 125 typically means machine already exists

        # Start the machine
        start_result = subprocess.run(
            ["podman", "machine", "start"],  # noqa: S607 - known podman command
            check=False,
        )

        # Return True only if start succeeded (machine may already be initialized)
        if start_result.returncode == 0:
            return True

        # If init failed for reasons other than "already exists", return False
        if init_result.returncode not in {0, 125}:
            return False

        return False
    except FileNotFoundError:
        return False
    except OSError:
        return False


def _do_install_podman(
    platform_info: PlatformInfo,
    config: dict[str, Any] | None,
) -> bool:
    """Execute Podman installation after validation.

    Internal helper that handles the actual installation process.

    Args:
        platform_info: Validated platform information.
        config: Optional configuration dict.

    Returns:
        True if installation succeeded, False otherwise.
    """
    command = get_install_command(platform_info)
    if command is None:
        print("! No supported package manager found for Podman installation")
        return False

    # Check if auto-install is enabled
    auto_install = bool(config and config.get("auto_install"))

    # Prompt user unless auto-install is enabled
    if not auto_install:
        response = input("Podman is not installed. Would you like to install it? [y/N]: ")
        if response.lower() not in ("y", "yes"):
            return False

    print(f"Installing Podman using: {' '.join(command)}")

    # Run installation
    if not install_podman(platform_info):
        print("! Podman installation failed")
        return False

    print("Podman installed successfully")

    # On Windows, initialize the Podman machine
    if platform_info.get("platform") == "windows":
        print("Initializing Podman machine...")
        if not init_podman_machine():
            print("! Failed to initialize Podman machine")
            return False
        print("Podman machine initialized and started")

    return True


def prompt_and_install_podman(config: dict[str, Any] | None = None) -> bool:
    """Prompt user to install Podman if not already installed.

    Checks if Podman is installed, and if not, prompts the user for
    confirmation before installing. On Windows, also initializes the
    Podman machine after installation.

    Args:
        config: Optional configuration dict. If config['auto_install'] is True,
                skips the user prompt and installs automatically.

    Returns:
        True if Podman is installed (or was installed successfully),
        False otherwise.
    """
    # Check if already installed
    if is_podman_installed():
        return True

    # Get platform information
    platform_info = get_platform_info()
    if platform_info is None:
        print("! Unsupported platform for Podman installation")
        return False

    return _do_install_podman(platform_info, config)
