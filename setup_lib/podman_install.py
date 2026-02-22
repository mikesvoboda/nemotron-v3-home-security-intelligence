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

import platform
import re
import shutil
import subprocess
from pathlib import Path
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


def _install_podman5_dependencies() -> None:
    """Install runtime dependencies required by Podman 5.x.

    Podman 5.x uses pasta (from passt) for rootless networking instead of
    slirp4netns. Without it, container builds and runs fail with:
      "could not find pasta, the network namespace can't be configured"

    Also migrates the container database from deprecated BoltDB to SQLite
    to avoid warnings and prepare for Podman 6.0.
    """
    # Install passt (provides the pasta binary for rootless networking)
    if not shutil.which("pasta"):
        print("  Installing passt (required for Podman 5.x rootless networking)...")
        result = subprocess.run(
            ["sudo", "apt-get", "install", "-y", "passt"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            print("  + passt installed")
        else:
            print(f"  ! Failed to install passt: {result.stderr.strip()}")
            print("    Container builds may fail without it")
    else:
        print("  + pasta already available")

    # Migrate BoltDB → SQLite (required before Podman 6.0 removes BoltDB)
    print("  Migrating Podman database to SQLite...")
    result = subprocess.run(
        ["podman", "system", "migrate", "--migrate-db"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        print("  + Podman database migrated to SQLite")
    # Non-zero is fine if already migrated — suppress noise


def upgrade_podman_to_4x(platform_info: PlatformInfo) -> bool:
    """Upgrade Podman to 5.x (or 4.x as fallback) using Kubic repository.

    Tries the Kubic testing repo (Podman 5.x) first, then falls back to
    unstable (Podman 4.x). Adds BuildKit cache mount support enabling
    5-10x faster rebuilds.

    Supports Ubuntu 20.04, 22.04, 24.04.

    Args:
        platform_info: Platform information from get_platform_info().

    Returns:
        True if upgrade succeeded, False otherwise.
    """
    # Only supported on Debian/Ubuntu systems with apt
    package_manager = str(platform_info.get("package_manager", ""))
    distro = platform_info.get("distro") or {}
    version = str(distro.get("version_id", ""))

    if package_manager != "apt":
        print("! Podman 5.x upgrade only supported on Debian/Ubuntu")
        return False

    # Map Ubuntu version to Kubic repository label
    repo_map = {
        "20.04": "xUbuntu_20.04",
        "22.04": "xUbuntu_22.04",
        "24.04": "xUbuntu_24.04",
    }

    repo_version = repo_map.get(version)
    if repo_version is None:
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

    # Ordered list of repos to try, targeting 5.x first.
    # Each entry: (label, base_url_template, sources_filename, gpg_filename)
    # {repo_version} is substituted with e.g. "xUbuntu_22.04"
    repo_candidates = [
        (
            "alvistack/podman-5",
            "https://download.opensuse.org/repositories/home:/alvistack/{repo_version}",
            "home:alvistack.list",
            "alvistack.gpg",
        ),
        (
            "Kubic testing",
            "https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/testing/{repo_version}",
            "devel:kubic:libcontainers:testing.list",
            "kubic-libcontainers-testing.gpg",
        ),
        (
            "Kubic unstable",
            "https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/unstable/{repo_version}",
            "devel:kubic:libcontainers:unstable.list",
            "kubic-libcontainers-unstable.gpg",
        ),
    ]

    def _remove_source(sources_file: str, gpg_file: str) -> None:
        """Remove apt source and GPG key files (best-effort cleanup)."""
        for path in (sources_file, gpg_file):
            subprocess.run(["sudo", "rm", "-f", path], capture_output=True, check=False)  # noqa: S607

    # Remove any stale sources files from previous failed attempts before starting
    for _, _, sf, gf in repo_candidates:
        sf_path = f"/etc/apt/sources.list.d/{sf}"
        gf_path = f"/etc/apt/trusted.gpg.d/{gf}"
        if Path(sf_path).exists() or Path(gf_path).exists():
            _remove_source(sf_path, gf_path)

    for label, url_template, sources_filename, gpg_filename in repo_candidates:
        base_url = url_template.format(repo_version=repo_version)
        repo_line = f"deb {base_url}/ /"
        sources_file = f"/etc/apt/sources.list.d/{sources_filename}"
        gpg_file = f"/etc/apt/trusted.gpg.d/{gpg_filename}"

        print(f"  [podman] Trying {label} repo ({repo_version})...", flush=True)

        try:
            # Fetch GPG key first — if this fails the repo doesn't exist for this OS
            key_result = subprocess.run(
                ["curl", "-fsSL", f"{base_url}/Release.key"],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if key_result.returncode != 0:
                print(f"  [podman] {label}: curl failed (rc={key_result.returncode}, 22=URL not found)", flush=True)
                _remove_source(sources_file, gpg_file)
                continue
            if not key_result.stdout:
                print(f"  [podman] {label}: empty GPG key, skipping", flush=True)
                continue

            # Write apt sources entry
            subprocess.run(
                ["sudo", "tee", sources_file],  # noqa: S607
                input=repo_line,
                text=True,
                check=True,
                capture_output=True,
            )

            # Import GPG key (--yes overwrites existing file)
            key_bytes = key_result.stdout.encode() if isinstance(key_result.stdout, str) else key_result.stdout
            subprocess.run(
                ["sudo", "gpg", "--yes", "--dearmor", "-o", gpg_file],  # noqa: S607
                input=key_bytes,
                check=True,
                capture_output=True,
            )

            # Update only the new source, then install
            update_result = subprocess.run(
                ["sudo", "apt-get", "update"],  # noqa: S607
                capture_output=True,
                check=False,
            )
            # apt-get update returns 100 if ANY repo fails — check the specific source
            if update_result.returncode != 0:
                stderr = update_result.stderr.decode(errors="replace")
                if sources_file.replace("/etc/apt/sources.list.d/", "") in stderr or base_url in stderr:
                    print(f"  {label}: repo update failed, skipping")
                    _remove_source(sources_file, gpg_file)
                    continue
                # Other repos failed (not our new one) — proceed anyway

            install_result = subprocess.run(
                ["sudo", "apt-get", "install", "-y", "podman"],  # noqa: S607
                check=False,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if install_result.returncode != 0:
                print(f"  [podman] {label}: apt-get install failed (rc={install_result.returncode})", flush=True)
                if install_result.stderr:
                    for line in install_result.stderr.strip().splitlines()[-2:]:
                        print(f"    {line}", flush=True)
                raise subprocess.CalledProcessError(install_result.returncode, ["apt-get", "install", "-y", "podman"])

            new_version = get_podman_version()
            if new_version and is_version_at_least(new_version, (4, 0, 0)):
                print(f"+ Podman upgraded to {new_version} (via {label})")
                _install_podman5_dependencies()
                return True

            print(f"  {label}: installed but version check failed ({new_version})")
            _remove_source(sources_file, gpg_file)

        except subprocess.CalledProcessError as e:
            print(f"  [podman] {label} failed: {e}", flush=True)
            _remove_source(sources_file, gpg_file)
        except OSError as e:
            print(f"  [podman] {label} failed: {e}", flush=True)
            _remove_source(sources_file, gpg_file)

    print("! Podman upgrade failed via all repositories (keeping 4.x from Ubuntu)", flush=True)
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
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"  [podman] apt install exited {result.returncode}", flush=True)
            if result.stderr:
                for line in result.stderr.strip().splitlines()[-3:]:
                    print(f"    {line}", flush=True)
        return result.returncode == 0
    except OSError as e:
        print(f"  [podman] install failed: {e}", flush=True)
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

    print(f"  [podman] Installing Podman using: {' '.join(command)}", flush=True)

    # Run installation
    if not install_podman(platform_info):
        print("  [podman] Standard apt install failed (rc!=0), trying Kubic/alvistack repos...", flush=True)
        if not upgrade_podman_to_4x(platform_info):
            print("! Podman installation failed via all methods", flush=True)
            return False

    if not is_podman_installed():
        print("! Podman not found after installation attempt (which podman returned nothing)", flush=True)
        return False

    print("  [podman] Podman installed successfully", flush=True)
    _verify_podman_operational()

    # On Windows, initialize the Podman machine
    if platform_info.get("platform") == "windows":
        print("Initializing Podman machine...")
        if not init_podman_machine():
            print("! Failed to initialize Podman machine")
            return False
        print("Podman machine initialized and started")

    return True


def _verify_podman_operational() -> None:
    """Verify podman is operational and print the compose command to use."""
    podman_path = shutil.which("podman")
    if not podman_path:
        print("! WARNING: podman not found in PATH after install", flush=True)
        return
    try:
        result = subprocess.run(
            ["podman", "--version"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            print(f"  [podman] Verified: {result.stdout.strip()} at {podman_path}", flush=True)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("! WARNING: podman --version failed", flush=True)
        return

    # Determine compose command for user (include ~/.local/bin for pip-installed podman-compose)
    compose_cmd = None
    local_compose = Path.home() / ".local" / "bin" / "podman-compose"
    if is_version_at_least(get_podman_version(), (5, 0, 0)):
        compose_cmd = "podman compose"
    elif shutil.which("podman-compose"):
        compose_cmd = "podman-compose"
    elif local_compose.exists():
        compose_cmd = "podman-compose"  # assume in PATH after profile reload, or use full path
        if not shutil.which("podman-compose"):
            compose_cmd = str(local_compose)

    if compose_cmd:
        print(f"  [podman] Start containers: {compose_cmd} -f docker-compose.prod.yml up -d", flush=True)
    else:
        print("  [podman] Install podman-compose: sudo apt install -y podman-compose", flush=True)


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
    """Install podman-compose.

    Tries in order:
      1. apt install podman-compose (Debian/Ubuntu)
      2. pipx install podman-compose
      3. pip3 install --user --break-system-packages podman-compose

    Returns:
        True if installation succeeded, False otherwise.
    """
    import os

    local_bin = str(Path.home() / ".local" / "bin")

    def _ensure_local_bin_in_path() -> None:
        if local_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = f"{local_bin}:{os.environ.get('PATH', '')}"

    def _verify_and_report() -> bool:
        _ensure_local_bin_in_path()
        if is_podman_compose_installed():
            print("+ podman-compose installed successfully")
            _add_to_shell_profile()
            return True
        print("! podman-compose installed but not in PATH")
        print('  Add to your ~/.bashrc: export PATH="$HOME/.local/bin:$PATH"')
        return True  # installed, just not in PATH yet

    # 1. Try system package manager (preferred — no pip/pipx needed)
    pkg_cmds: list[list[str]] = []
    if shutil.which("apt"):
        pkg_cmds.append(["sudo", "apt", "install", "-y", "podman-compose"])  # noqa: S607
    if shutil.which("dnf"):
        pkg_cmds.append(["sudo", "dnf", "install", "-y", "podman-compose"])  # noqa: S607
    if shutil.which("pacman"):
        pkg_cmds.append(["sudo", "pacman", "-S", "--noconfirm", "podman-compose"])  # noqa: S607

    for pkg_cmd in pkg_cmds:
        result = subprocess.run(pkg_cmd, check=False, capture_output=True, text=True)  # noqa: S607
        if result.returncode == 0 and is_podman_compose_installed():
            print(f"+ podman-compose installed via {pkg_cmd[1]}")
            return True

    # 2. Try pipx
    if shutil.which("pipx"):
        result = subprocess.run(
            ["pipx", "install", "podman-compose"],  # noqa: S607
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return _verify_and_report()

    # 3. Fall back to pip3 with --break-system-packages
    try:
        result = subprocess.run(
            ["pip3", "install", "--user", "--break-system-packages", "podman-compose"],  # noqa: S607
            check=False,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            # Last-ditch attempt without the flag (older pip)
            result = subprocess.run(
                ["pip3", "install", "--user", "podman-compose"],  # noqa: S607
                check=False,
                capture_output=True,
                text=True,
            )

        if result.returncode != 0:
            print(f"! pip install failed: {result.stderr}")
            return False

        return _verify_and_report()

    except FileNotFoundError:
        print("! pip3 not found")
        return False
    except OSError as e:
        print(f"! Installation failed: {e}")
        return False


def configure_rootless_cgroups() -> bool:  # noqa: PLR0911
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
            ["sudo", "mkdir", "-p", "/etc/systemd/system/user@.service.d/"],  # noqa: S607
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
            ["sudo", "tee", str(delegate_file)],  # noqa: S607
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
            ["sudo", "systemctl", "daemon-reload"],  # noqa: S607
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
                ["loginctl", "enable-linger", username],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            # Ignore errors - lingering is nice-to-have, not required

        # Reload user systemd session
        result = subprocess.run(
            ["systemctl", "--user", "daemon-reload"],  # noqa: S607
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
                    ["sysctl", "-n", sysctl],  # noqa: S607
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
                ["sudo", "sysctl", "-w", f"{sysctl}={value}"],  # noqa: S607
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
                    ["sudo", "tee", "-a", str(sysctl_file)],  # noqa: S607
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

        # Configure open files limit (required for frontend builds with Vite/Rollup)
        print("\nConfiguring open files limit...")
        print("  (Required for large Node.js builds in rootless containers)")

        limits_file = Path("/etc/security/limits.d/99-podman-nofile.conf")
        limits_config = "* soft nofile 65536\n* hard nofile 65536\n"

        # Check if already configured
        if limits_file.exists():
            try:
                content = limits_file.read_text()
                if "nofile 65536" in content:
                    print("  Open files limit already configured")
                    return True
            except (OSError, PermissionError):
                pass

        result = subprocess.run(
            ["sudo", "tee", str(limits_file)],  # noqa: S607
            input=limits_config,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            print("  Open files limit: 65536 (configured)")
            print(f"    Persisted to {limits_file}")
        else:
            print(f"! Warning: Failed to set open files limit: {result.stderr}")
            print("  Frontend builds may fail with 'EMFILE: too many open files'")

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
    print("  [podman] Detecting platform...", flush=True)
    platform_info = get_platform_info()
    if platform_info is None:
        print("! Unsupported platform for Podman installation", flush=True)
        return False
    print(f"  [podman] Platform: {platform_info.get('platform', '?')} / {platform_info.get('package_manager', '?')}", flush=True)

    # Check if already installed
    if is_podman_installed():
        print("  [podman] Podman already installed, checking version...", flush=True)
        # Check version (need 5.0+ for native podman compose support)
        current_version = get_podman_version()
        if current_version:
            print(f"  [podman] Podman {current_version} detected", flush=True)

            if not is_version_at_least(current_version, (5, 0, 0)):
                print("! Podman < 5.0 detected - upgrading for native compose and BuildKit support", flush=True)

                auto_install = bool(config and config.get("auto_install"))
                if auto_install:
                    print("  [podman] Upgrading to Podman 5.x...", flush=True)
                    upgrade_podman_to_4x(platform_info)
                else:
                    response = input("Upgrade to Podman 5.x? [y/N]: ")
                    if response.lower() in ("y", "yes"):
                        upgrade_podman_to_4x(platform_info)

        # Ensure Podman 5.x runtime dependencies are present
        if is_version_at_least(get_podman_version(), (5, 0, 0)):
            print("  [podman] Installing Podman 5.x dependencies (passt)...", flush=True)
            _install_podman5_dependencies()

        # Also check and install podman-compose
        if not is_podman_compose_installed():
            print("  [podman] podman-compose not found, installing...", flush=True)
            install_podman_compose()
        else:
            print("  [podman] podman-compose already installed", flush=True)

        # Configure rootless cgroups (Linux only, required for resource limits)
        print("  [podman] Configuring rootless cgroups...", flush=True)
        configure_rootless_cgroups()

        _verify_podman_operational()
        return True

    # Not installed - do fresh installation
    print("  [podman] Podman not installed, performing fresh install...", flush=True)
    success = _do_install_podman(platform_info, config)

    # If Podman was installed successfully, check version and upgrade if needed
    if success:
        current_version = get_podman_version()
        print(f"  [podman] Fresh install complete, version: {current_version or 'unknown'}", flush=True)
        if current_version and not is_version_at_least(current_version, (5, 0, 0)):
            print(f"  [podman] Podman {current_version} installed, but 5.0+ is recommended", flush=True)
            print("  [podman] Upgrading to Podman 5.x...", flush=True)
            upgrade_podman_to_4x(platform_info)

        # Install podman-compose
        if not is_podman_compose_installed():
            print("  [podman] Installing podman-compose...", flush=True)
            install_podman_compose()
        else:
            print("  [podman] podman-compose already installed", flush=True)

        # Configure rootless cgroups (Linux only, required for resource limits)
        print("  [podman] Configuring rootless cgroups...", flush=True)
        configure_rootless_cgroups()

        _verify_podman_operational()
    else:
        print("  [podman] Installation failed", flush=True)

    return success
