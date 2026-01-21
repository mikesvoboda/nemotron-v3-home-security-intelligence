"""Free-threaded Python verification module.

This module provides utilities for verifying that Python is running with
free-threading support (GIL disabled). This is required for optimal
concurrent performance in the backend when running on Python 3.13+.

Free-threading support requires:
1. Python built with --disable-gil (Python 3.13t/3.14t builds)
2. PYTHON_GIL=0 environment variable set before Python starts

References:
- PEP 703: Making the Global Interpreter Lock Optional in CPython
- https://docs.python.org/3.14/whatsnew/3.13.html#free-threaded-cpython
"""

from __future__ import annotations

import sys
import sysconfig
from dataclasses import dataclass


@dataclass(frozen=True)
class FreeThreadingStatus:
    """Status of free-threading support in the current Python runtime.

    Attributes:
        build_supports_free_threading: Whether Python was built with free-threading support.
        gil_disabled: Whether the GIL is actually disabled at runtime.
        is_free_threaded: True if both build support and runtime GIL disable are active.
        python_version: Current Python version string.
        build_info: Build configuration information.
    """

    build_supports_free_threading: bool
    gil_disabled: bool
    is_free_threaded: bool
    python_version: str
    build_info: str


def check_free_threading_support() -> FreeThreadingStatus:
    """Check if Python has free-threading support and whether it's active.

    This function performs two checks:
    1. Build support: Was Python compiled with --disable-gil?
    2. Runtime status: Is the GIL actually disabled?

    Returns:
        FreeThreadingStatus with detailed information about the current state.

    Example:
        >>> status = check_free_threading_support()
        >>> if status.is_free_threaded:
        ...     print("Running with free-threading enabled!")
        ... else:
        ...     print(f"Free-threading not active: {status}")
    """
    # Check if Python was built with free-threading support
    # Py_GIL_DISABLED is 1 when Python was built with --disable-gil
    py_gil_disabled = sysconfig.get_config_var("Py_GIL_DISABLED")
    build_supports = py_gil_disabled == 1

    # Check if GIL is actually disabled at runtime
    # sys._is_gil_enabled() was added in Python 3.13 for free-threaded builds
    gil_disabled = not sys._is_gil_enabled() if hasattr(sys, "_is_gil_enabled") else False

    # Gather build information
    python_version = sys.version
    build_info = f"Py_GIL_DISABLED={py_gil_disabled}"

    return FreeThreadingStatus(
        build_supports_free_threading=build_supports,
        gil_disabled=gil_disabled,
        is_free_threaded=build_supports and gil_disabled,
        python_version=python_version,
        build_info=build_info,
    )


def verify_free_threading(*, raise_on_failure: bool = True) -> bool:
    """Verify that free-threaded Python is active.

    This function should be called during application startup to ensure
    the backend is running with optimal concurrent performance.

    Args:
        raise_on_failure: If True, raise RuntimeError when free-threading
            is not active. If False, return False instead.

    Returns:
        True if free-threaded Python is active.

    Raises:
        RuntimeError: If free-threading is not active and raise_on_failure is True.
            The error message includes details about what's missing:
            - "Python not built with free-threading support" if Py_GIL_DISABLED != 1
            - "GIL is enabled. Set PYTHON_GIL=0" if the build supports it but GIL is on

    Example:
        # Strict mode (default) - raises on failure
        >>> verify_free_threading()
        True

        # Non-strict mode - returns False on failure
        >>> if not verify_free_threading(raise_on_failure=False):
        ...     logger.warning("Free-threading not available, using GIL")
    """
    status = check_free_threading_support()

    if status.is_free_threaded:
        return True

    if not raise_on_failure:
        return False

    # Provide specific error message based on what's missing
    if not status.build_supports_free_threading:
        raise RuntimeError(
            "Python not built with free-threading support. "
            "Use Python 3.14t (free-threaded build) or build from source with --disable-gil. "
            f"Current Python: {status.python_version}"
        )

    if not status.gil_disabled:
        raise RuntimeError(
            "GIL is enabled. Set PYTHON_GIL=0 environment variable before starting Python. "
            f"Build info: {status.build_info}"
        )

    # Should not reach here, but handle edge case
    raise RuntimeError(f"Free-threading verification failed. Status: {status}")


def get_threading_mode() -> str:
    """Get a human-readable description of the current threading mode.

    Returns:
        A string describing the threading mode, suitable for logging.

    Example:
        >>> print(f"Running with {get_threading_mode()}")
        Running with free-threaded Python (GIL disabled)
    """
    status = check_free_threading_support()

    if status.is_free_threaded:
        return "free-threaded Python (GIL disabled)"
    elif status.build_supports_free_threading:
        return "GIL-enabled Python (free-threading build available but GIL active)"
    else:
        return "standard Python (GIL enabled, no free-threading support)"
