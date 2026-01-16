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
