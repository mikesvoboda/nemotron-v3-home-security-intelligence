"""Core utility functions for setup script.

This module contains reusable utilities for port checking, password generation,
and other setup-related operations. These functions are extracted from the
main setup.py to enable better testing and reusability.
"""

import secrets
import socket

# Known weak/default passwords to warn about
WEAK_PASSWORDS = {
    "security_dev_password",
    "password",
    "postgres",
    "admin",
    "root",
    "123456",
    "changeme",
    "secret",
}


def check_port_available(port: int) -> bool:
    """Check if a port is available for binding.

    Checks both IPv4 and IPv6 localhost to detect processes bound to either.

    Args:
        port: Port number to check

    Returns:
        True if port is available on both IPv4 and IPv6, False if in use
    """
    # Check IPv4
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", port)) == 0:
            return False
    # Check IPv6
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            if s.connect_ex(("::1", port)) == 0:
                return False
    except OSError:
        pass  # IPv6 not available
    return True


def find_available_port(start: int, exclude: set[int] | None = None) -> int:
    """Find the next available port starting from a given port.

    Args:
        start: Starting port number
        exclude: Set of ports to skip (already assigned to other services)

    Returns:
        First available port >= start that is not in exclude set

    Raises:
        RuntimeError: If no available ports found up to 65535
    """
    if exclude is None:
        exclude = set()
    port = start
    while not check_port_available(port) or port in exclude:
        port += 1
        if port > 65535:
            raise RuntimeError(f"No available ports found starting from {start}")
    return port


def generate_password(length: int = 32) -> str:
    """Generate a secure random password.

    Args:
        length: Desired password length (default: 32 for security)

    Returns:
        URL-safe random string of specified length
    """
    return secrets.token_urlsafe(length)[:length]


def derive_frontend_bind_address(expose_lan: str) -> str:
    """Map an EXPOSE_LAN value to the frontend's published-port bind address.

    O1.6 (D10; OD-12): compose has no conditionals, so the switch lives here —
    setup.py derives FRONTEND_BIND_ADDRESS from EXPOSE_LAN and writes both into
    the .env it generates, and docker-compose.prod.yml references the bind var.

    One flag, one vocabulary (O1.6 review follow-up): the truthy set matches
    what pydantic parses for Settings.expose_lan from a string — case-
    insensitive {"true", "t", "yes", "y", "on", "1"} (probed against
    TypeAdapter(bool) on pydantic 2.13), so a value like EXPOSE_LAN=yes can
    never arm the auth gate here while the bind stayed loopback there.
    Everything else — unset, "false"/"no"/"off", a typo — yields loopback
    "127.0.0.1" (fail-safe). The words pydantic REJECTS outright (e.g. "banana")
    can't split the readers either: Settings construction raises before any
    render happens. The second fail-safe layer is compose's own
    ${FRONTEND_BIND_ADDRESS:-127.0.0.1} default, which covers a hand-edited
    .env that sets EXPOSE_LAN=true without re-running setup.py.

    Args:
        expose_lan: raw EXPOSE_LAN value (from a prompt answer or an env read)

    Returns:
        "0.0.0.0" when the UI is deliberately LAN-exposed, else "127.0.0.1"
    """
    return (
        "0.0.0.0"  # noqa: S104
        if expose_lan.strip().lower() in ("true", "t", "yes", "y", "on", "1")
        else "127.0.0.1"
    )


def is_weak_password(password: str) -> bool:
    """Check if a password is considered weak.

    Args:
        password: Password to check

    Returns:
        True if password is weak, False otherwise
    """
    if len(password) < 16:
        return True
    return password.lower() in WEAK_PASSWORDS
