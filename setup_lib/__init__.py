"""Setup package for Home Security Intelligence.

This package provides reusable utilities for the setup script including
port checking, password generation, and other configuration helpers.
"""

from setup_lib.core import (
    WEAK_PASSWORDS,
    check_port_available,
    find_available_port,
    generate_password,
    is_weak_password,
)

__all__ = [
    "WEAK_PASSWORDS",
    "check_port_available",
    "find_available_port",
    "generate_password",
    "is_weak_password",
]
