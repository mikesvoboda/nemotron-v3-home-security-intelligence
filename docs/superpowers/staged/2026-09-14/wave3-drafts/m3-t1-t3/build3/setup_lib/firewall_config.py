"""Firewall auto-configuration for setup.py.

Provides cross-platform firewall detection and configuration for Linux
(firewalld, ufw) and Windows. Supports opening required ports for the
Home Security Intelligence application.

Usage:
    from setup_lib.firewall_config import prompt_and_configure_firewall
    prompt_and_configure_firewall(config)
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Literal

# Type alias for supported firewall types
FirewallType = Literal["firewalld", "ufw", "windows"]

# Default ports for Home Security Intelligence
DEFAULT_PORTS: list[int] = [
    8443,  # HTTPS dashboard
    8555,  # WebRTC streaming
    5432,  # PostgreSQL
    6379,  # Redis
]


def detect_firewall_type() -> FirewallType | None:
    """Detect the active firewall type on the system.

    Checks for firewalld (Fedora/RHEL), ufw (Ubuntu/Debian), or Windows
    firewall in that order.

    Returns:
        'firewalld', 'ufw', 'windows', or None if no firewall is active.
    """
    # Check firewalld first (Fedora, RHEL, CentOS)
    if shutil.which("firewall-cmd"):
        try:
            result = subprocess.run(
                ["firewall-cmd", "--state"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0 and "running" in result.stdout.lower():
                return "firewalld"
        except (subprocess.SubprocessError, OSError):
            pass

    # Check ufw (Ubuntu, Debian)
    if shutil.which("ufw"):
        try:
            result = subprocess.run(
                ["ufw", "status"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0 and "status: active" in result.stdout.lower():
                return "ufw"
        except (subprocess.SubprocessError, OSError):
            pass

    # Check Windows firewall
    if platform.system() == "Windows" and shutil.which("netsh"):
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles", "state"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                # Check if any profile has firewall ON
                lines = result.stdout.lower()
                if "state" in lines and "on" in lines:
                    return "windows"
        except (subprocess.SubprocessError, OSError):
            pass

    return None


def is_firewall_active() -> bool:
    """Check if any firewall is currently active.

    Returns:
        True if a firewall is active, False otherwise.
    """
    return detect_firewall_type() is not None


def _is_port_open_firewalld(port: int) -> bool:
    """Check if port is open in firewalld."""
    try:
        result = subprocess.run(  # noqa: S603
            ["firewall-cmd", "--query-port", f"{port}/tcp"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _is_port_open_ufw(port: int) -> bool:
    """Check if port is open in ufw."""
    try:
        result = subprocess.run(
            ["ufw", "status"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0:
            # Look for the port in the output
            return f"{port}/tcp" in result.stdout.lower()
    except (subprocess.SubprocessError, OSError):
        pass
    return False


def _is_port_open_windows(port: int) -> bool:
    """Check if port is open in Windows firewall."""
    try:
        result = subprocess.run(
            [  # noqa: S607
                "netsh",
                "advfirewall",
                "firewall",
                "show",
                "rule",
                "name=all",
                "dir=in",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            # Look for a rule with this port
            return f"localport:{port}" in result.stdout.lower().replace(" ", "")
    except (subprocess.SubprocessError, OSError):
        pass
    return False


def is_port_open(port: int) -> bool:
    """Check if a port is already allowed through the firewall.

    Args:
        port: Port number to check.

    Returns:
        True if port is open or no firewall is active, False if blocked.
    """
    firewall_type = detect_firewall_type()

    if firewall_type is None:
        # No firewall active, port is not blocked
        return True

    port_checkers = {
        "firewalld": _is_port_open_firewalld,
        "ufw": _is_port_open_ufw,
        "windows": _is_port_open_windows,
    }

    checker = port_checkers.get(firewall_type)
    if checker:
        return checker(port)

    return True


def get_open_port_commands(ports: list[int], firewall_type: FirewallType | None) -> list[str]:
    """Generate commands to open the specified ports.

    Args:
        ports: List of port numbers to open.
        firewall_type: Type of firewall to configure.

    Returns:
        List of command strings to execute.
    """
    if not ports or firewall_type is None:
        return []

    commands: list[str] = []

    if firewall_type == "firewalld":
        for port in ports:
            commands.append(f"firewall-cmd --permanent --add-port={port}/tcp")
        commands.append("firewall-cmd --reload")

    elif firewall_type == "ufw":
        for port in ports:
            commands.append(f"ufw allow {port}/tcp")

    elif firewall_type == "windows":
        for port in ports:
            rule_name = f"Home Security {port}"
            commands.append(
                f'netsh advfirewall firewall add rule name="{rule_name}" '
                f"dir=in action=allow protocol=tcp localport={port}"
            )

    return commands


def open_firewall_ports(ports: list[int], firewall_type: FirewallType | None) -> bool:
    """Execute commands to open firewall ports.

    Args:
        ports: List of port numbers to open.
        firewall_type: Type of firewall to configure.

    Returns:
        True if all commands succeeded, False otherwise.
    """
    if firewall_type is None:
        return True

    commands = get_open_port_commands(ports, firewall_type)
    if not commands:
        return True

    import shlex

    try:
        for cmd in commands:
            # Split command into arguments
            # Use shlex.split to handle quoted arguments (Windows rule names)
            args = shlex.split(cmd)

            result = subprocess.run(  # noqa: S603
                args,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            if result.returncode != 0:
                print(f"! Failed to execute: {cmd}")
                if result.stderr:
                    print(f"  Error: {result.stderr.strip()}")
                return False

        return True

    except subprocess.SubprocessError as e:
        print(f"! Subprocess error: {e}")
        return False


def get_ports_to_open(ports: list[int]) -> list[int]:
    """Filter ports to only those that need to be opened.

    Args:
        ports: List of port numbers to check.

    Returns:
        List of ports that are not currently open.
    """
    firewall_type = detect_firewall_type()

    if firewall_type is None:
        # No firewall active, nothing to open
        return []

    return [port for port in ports if not is_port_open(port)]


def prompt_and_configure_firewall(config: dict) -> None:
    """Prompt user and configure firewall if needed.

    Detects the active firewall, checks which ports need to be opened,
    and prompts the user before making changes.

    Args:
        config: Configuration dictionary. May contain 'firewall_ports' key
            with custom list of ports to configure.
    """
    print()
    print("=" * 60)
    print("Firewall Configuration")
    print("=" * 60)
    print()

    firewall_type = detect_firewall_type()

    if firewall_type is None:
        print("+ No active firewall detected")
        print("  Ports are not blocked by a host firewall")
        return

    print(f"Detected firewall: {firewall_type}")

    # Get ports to configure
    ports = config.get("firewall_ports", DEFAULT_PORTS)
    ports_to_open = get_ports_to_open(ports)

    if not ports_to_open:
        print("+ All required ports are already open")
        return

    print()
    print("The following ports need to be opened:")
    port_descriptions = {
        8443: "HTTPS dashboard",
        8555: "WebRTC streaming",
        5432: "PostgreSQL database",
        6379: "Redis cache",
    }

    for port in ports_to_open:
        description = port_descriptions.get(port, "Application")
        print(f"  - {port}/tcp ({description})")

    # Show commands that will be executed
    commands = get_open_port_commands(ports_to_open, firewall_type)
    print()
    print("Commands to execute:")
    for cmd in commands:
        print(f"  $ {cmd}")

    print()
    answer = input("Open these firewall ports? [y]: ").strip().lower()
    if answer and answer not in ("y", "yes"):
        print("  Skipping firewall configuration")
        print("  ! You may need to manually open these ports")
        return

    print()
    print("Configuring firewall...")

    if open_firewall_ports(ports_to_open, firewall_type):
        print("+ Firewall ports opened successfully")
    else:
        print("! Failed to configure firewall")
        print("  You may need to run with elevated privileges (sudo)")


if __name__ == "__main__":
    # Allow testing the module directly
    prompt_and_configure_firewall({})
