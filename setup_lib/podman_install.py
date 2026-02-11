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


def parse_version(version_str: str) -> tuple[int, int, int] | None:
    """Parse a version string into (major, minor, patch) tuple.

    Args:
        version_str: Version string like "3.4.4" or "4.9.3-dev"

    Returns:
        Tuple of (major, minor, patch) integers, or None if parse fails.
    """
    try:
        # Remove any suffix like "-dev" or "-rhel"
        clean_version = version_str.split("-")[0]
        parts = clean_version.split(".")
        if len(parts) >= 3:
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        return None
    except (ValueError, IndexError):
        return None


def is_version_at_least(current: str | None, required: tuple[int, int, int]) -> bool:
    """Check if current version meets minimum requirement.

    Args:
        current: Current version string (e.g., "3.4.4")
        required: Required version as tuple (e.g., (4, 0, 0))

    Returns:
        True if current version >= required, False otherwise.
    """
    if current is None:
        return False
    
    parsed = parse_version(current)
    if parsed is None:
        return False
    
    return parsed >= required


def upgrade_podman_to_4x(platform_info: PlatformInfo) -> bool:
    """Upgrade Podman to 4.x or newer using Kubic repository.

    Adds the Kubic repository which provides newer Podman versions (4.9+/5.x)
    with BuildKit cache mount support. Cache mounts enable 5-10x faster rebuilds
    by persisting pip/uv/npm downloads and CUDA object files between builds.

    Supports Ubuntu 20.04, 22.04, 24.04 by detecting version and using
    appropriate repository.

    Args:
        platform_info: Platform information from get_platform_info().

    Returns:
        True if upgrade succeeded, False otherwise.
    """
    # Only supported on Debian/Ubuntu systems with apt
    package_manager = platform_info.get("package_manager")
    dist_id = platform_info.get("distribution_id", "").lower()
    version = platform_info.get("version", "")
    
    if package_manager != "apt":
        print("! Podman 4.x+ upgrade only supported on Debian/Ubuntu")
        return False
    
    # Map Ubuntu version to Kubic repository URL
    # Use exact match for Ubuntu, fallback for Debian
    repo_map = {
        "20.04": "xUbuntu_20.04",
        "22.04": "xUbuntu_22.04",
        "24.04": "xUbuntu_24.04",
    }
    
    repo_version = repo_map.get(version)
    if repo_version is None:
        # Try to infer for Debian or unknown Ubuntu versions
        if "20" in version:
            repo_version = "xUbuntu_20.04"
        elif "22" in version:
            repo_version = "xUbuntu_22.04"
        elif "24" in version:
            repo_version = "xUbuntu_24.04"
        else:
            print(f"! Unsupported Ubuntu/Debian version for Kubic repo: {version}")
            print("  Supported versions: 20.04, 22.04, 24.04")
            return False
    
    print(f"Upgrading Podman from Kubic repository ({repo_version})...")
    
    try:
        # Add Kubic repository for detected OS version
        base_url = f"https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/unstable/{repo_version}"
        repo_line = f"deb {base_url}/ /"
        
        subprocess.run(
            ["sudo", "tee", "/etc/apt/sources.list.d/devel:kubic:libcontainers:unstable.list"],
            input=repo_line,
            text=True,
            check=True,
            capture_output=True,
        )
        
        # Add GPG key (use detected OS version)
        key_url = f"{base_url}/Release.key"
        result = subprocess.run(
            ["curl", "-fsSL", key_url],
            capture_output=True,
            check=True,
        )
        
        subprocess.run(
            ["sudo", "gpg", "--dearmor", "-o", "/etc/apt/trusted.gpg.d/kubic-libcontainers-unstable.gpg"],
            input=result.stdout,
            check=True,
            capture_output=True,
        )
        
        # Update package list
        subprocess.run(
            ["sudo", "apt-get", "update"],
            check=True,
            capture_output=True,
        )
        
        # Upgrade podman
        subprocess.run(
            ["sudo", "apt-get", "install", "-y", "podman"],
            check=True,
            capture_output=True,
        )
        
        # Verify upgrade
        new_version = get_podman_version()
        if new_version and is_version_at_least(new_version, (4, 0, 0)):
            print(f"+ Podman upgraded to {new_version}")
            return True
        else:
            print(f"! Upgrade may have failed (version: {new_version})")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"! Upgrade failed: {e}")
        return False
    except OSError as e:
        print(f"! Upgrade failed: {e}")
        return False


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


def is_podman_compose_installed() -> bool:
    """Check if podman-compose is installed and available.

    Returns:
        True if podman-compose is in PATH, False otherwise.
    """
    return shutil.which("podman-compose") is not None


def _add_to_shell_profile() -> None:
    """Add ~/.local/bin to PATH in shell profile if not already present."""
    path_export = 'export PATH="$HOME/.local/bin:$PATH"'
    
    # Determine which shell profile to update
    shell_profiles = [
        Path.home() / ".bashrc",
        Path.home() / ".bash_profile",
        Path.home() / ".profile",
    ]
    
    for profile in shell_profiles:
        if profile.exists():
            try:
                content = profile.read_text()
                if ".local/bin" not in content:
                    # Append PATH export to profile
                    with profile.open("a") as f:
                        f.write(f"\n# Added by setup.py for podman-compose\n{path_export}\n")
                    print(f"  + Added ~/.local/bin to PATH in {profile.name}")
                    return
            except (OSError, PermissionError):
                pass
    
    # If no profile found, suggest manual addition
    print(f"  Note: Add to shell profile: {path_export}")


def install_podman_compose() -> bool:
    """Install podman-compose via pip.

    Returns:
        True if installation succeeded, False otherwise.
    """
    try:
        # Install via pip3 with user flag
        result = subprocess.run(
            ["pip3", "install", "--user", "podman-compose"],
            check=False,
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            print(f"! pip install failed: {result.stderr}")
            return False
        
        # Add ~/.local/bin to PATH for current session
        import os
        local_bin = str(Path.home() / ".local" / "bin")
        if local_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = f"{local_bin}:{os.environ.get('PATH', '')}"
        
        # Verify installation
        if is_podman_compose_installed():
            print("+ podman-compose installed successfully")
            
            # Add to shell profile for persistence
            _add_to_shell_profile()
            return True
        else:
            print("! podman-compose installed but not in PATH")
            print(f"  Add to your ~/.bashrc: export PATH=\"$HOME/.local/bin:$PATH\"")
            return True  # Still return True as it's installed
            
    except FileNotFoundError:
        print("! pip3 not found")
        return False
    except OSError as e:
        print(f"! Installation failed: {e}")
        return False


def configure_rootless_cgroups() -> bool:
    """Configure cgroup delegation for rootless Podman (Linux only).
    
    Rootless Podman requires cgroup delegation to enforce resource limits
    (CPU, memory) defined in docker-compose.yml. Without delegation, containers
    will fail to start with "cpu controller not available" errors.
    
    This function:
    1. Creates /etc/systemd/system/user@.service.d/delegate.conf
    2. Sets Delegate=yes to enable cgroup passthrough
    3. Reloads systemd daemon
    4. Enables lingering for current user
    
    Returns:
        True if configuration succeeded or is not needed (macOS/Windows),
        False if configuration failed.
    """
    # Only needed on Linux
    if platform.system() != "Linux":
        return True
    
    # Check if delegation is already configured
    delegate_file = Path("/etc/systemd/system/user@.service.d/delegate.conf")
    if delegate_file.exists():
        try:
            content = delegate_file.read_text()
            if "Delegate=yes" in content:
                print("+ Rootless cgroup delegation already configured")
                return True
        except (OSError, PermissionError):
            pass
    
    print("\nConfiguring cgroup delegation for rootless Podman...")
    print("  (Required for CPU/memory limits in compose files)")
    
    try:
        # Create systemd drop-in directory
        result = subprocess.run(
            ["sudo", "mkdir", "-p", "/etc/systemd/system/user@.service.d/"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            print(f"! Failed to create systemd directory: {result.stderr}")
            return False
        
        # Write delegation configuration
        delegate_config = "[Service]\nDelegate=yes\n"
        result = subprocess.run(
            ["sudo", "tee", str(delegate_file)],
            input=delegate_config,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            print(f"! Failed to write delegation config: {result.stderr}")
            return False
        
        # Reload systemd daemon
        result = subprocess.run(
            ["sudo", "systemctl", "daemon-reload"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            print(f"! Failed to reload systemd: {result.stderr}")
            return False
        
        # Enable lingering for current user (allows user services to run at boot)
        import os
        username = os.environ.get("USER")
        if username:
            result = subprocess.run(
                ["loginctl", "enable-linger", username],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            # Ignore errors - lingering is nice-to-have, not required
        
        # Reload user systemd session
        result = subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            print(f"! Warning: Failed to reload user systemd: {result.stderr}")
            print("  Delegation will take effect after logout/login")
        
        print("+ Cgroup delegation configured successfully")
        print("  CPU/memory limits will now work in rootless containers")
        
        # Configure Redis sysctls (required for rootless containers)
        print("\nConfiguring Redis sysctls...")
        sysctls_to_set = {
            "vm.overcommit_memory": "1",
            "net.core.somaxconn": "511",
        }
        
        for sysctl, value in sysctls_to_set.items():
            # Check current value
            try:
                current_result = subprocess.run(
                    ["sysctl", "-n", sysctl],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if current_result.returncode == 0:
                    current_value = current_result.stdout.strip()
                    if current_value == value:
                        print(f"  {sysctl}={value} already set")
                        continue
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                pass
            
            # Set sysctl
            result = subprocess.run(
                ["sudo", "sysctl", "-w", f"{sysctl}={value}"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode == 0:
                print(f"  {sysctl}={value} configured")
                
                # Make it persistent across reboots
                sysctl_file = Path("/etc/sysctl.d/99-podman-redis.conf")
                result = subprocess.run(
                    ["sudo", "tee", "-a", str(sysctl_file)],
                    input=f"{sysctl}={value}\n",
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if result.returncode == 0:
                    print(f"    Persisted to {sysctl_file}")
            else:
                print(f"! Warning: Failed to set {sysctl}: {result.stderr}")
        
        return True
        
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError) as e:
        print(f"! Failed to configure cgroup delegation: {e}")
        print("  Containers may fail with 'cpu controller not available' errors")
        return False


def prompt_and_install_podman(config: dict[str, Any] | None = None) -> bool:
    """Prompt user to install Podman if not already installed.

    Checks if Podman is installed, and if not, prompts the user for
    confirmation before installing. On Windows, also initializes the
    Podman machine after installation.

    Also checks Podman version and upgrades to 4.x if needed (for BuildKit support).
    Configures rootless cgroups for resource limit support (Linux only).

    Args:
        config: Optional configuration dict. If config['auto_install'] is True,
                skips the user prompt and installs automatically.

    Returns:
        True if Podman is installed (or was installed successfully),
        False otherwise.
    """
    # Get platform information early
    platform_info = get_platform_info()
    if platform_info is None:
        print("! Unsupported platform for Podman installation")
        return False
    
    # Check if already installed
    if is_podman_installed():
        # Check version (need 4.0+ for BuildKit cache mount support)
        current_version = get_podman_version()
        if current_version:
            print(f"Podman {current_version} detected")
            
            if not is_version_at_least(current_version, (4, 0, 0)):
                print("! Podman 3.x detected - need 4.0+ for BuildKit cache mounts")
                
                auto_install = bool(config and config.get("auto_install"))
                if auto_install:
                    print("Upgrading to Podman 4.x...")
                    upgrade_podman_to_4x(platform_info)
                else:
                    response = input("Upgrade to Podman 4.x for faster builds? [y/N]: ")
                    if response.lower() in ("y", "yes"):
                        upgrade_podman_to_4x(platform_info)
        
        # Also check and install podman-compose
        if not is_podman_compose_installed():
            print("Checking for podman-compose...")
            install_podman_compose()
        
        # Configure rootless cgroups (Linux only, required for resource limits)
        configure_rootless_cgroups()
        
        return True

    # Not installed - do fresh installation
    success = _do_install_podman(platform_info, config)
    
    # If Podman was installed successfully, check version and upgrade if needed
    if success:
        current_version = get_podman_version()
        if current_version and not is_version_at_least(current_version, (4, 0, 0)):
            print(f"\nPodman {current_version} installed, but 4.0+ is recommended")
            print("Upgrading to Podman 4.x for BuildKit support...")
            upgrade_podman_to_4x(platform_info)
        
        # Install podman-compose
        if not is_podman_compose_installed():
            print("\nInstalling podman-compose...")
            install_podman_compose()
        
        # Configure rootless cgroups (Linux only, required for resource limits)
        configure_rootless_cgroups()
    
    return success
