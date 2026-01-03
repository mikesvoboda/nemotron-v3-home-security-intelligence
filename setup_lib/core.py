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

    Args:
        port: Port number to check

    Returns:
        True if port is available, False if in use
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0


def find_available_port(start: int) -> int:
    """Find the next available port starting from a given port.

    Args:
        start: Starting port number

    Returns:
        First available port >= start

    Raises:
        RuntimeError: If no available ports found up to 65535
    """
    port = start
    while not check_port_available(port):
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
