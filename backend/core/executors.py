"""Executor management for CPU-bound parallel tasks.

This module provides utilities for obtaining the best available executor
for CPU-bound work. On Python 3.14+, it uses InterpreterPoolExecutor from
PEP 734, which provides process-like isolation via per-interpreter GILs
with lower memory overhead than multiprocessing (shared address space).

For older Python versions, it falls back to ThreadPoolExecutor.

References:
- PEP 734: Multiple Interpreters in the Stdlib
- https://docs.python.org/3.14/library/concurrent.futures.html#interpreterexecutor

Example:
    >>> from backend.core.executors import get_cpu_executor, get_executor_type
    >>> with get_cpu_executor(max_workers=4) as executor:
    ...     results = list(executor.map(cpu_heavy_work, items))
    >>> print(f"Using: {get_executor_type()}")
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from concurrent.futures import Executor

# Try to import InterpreterPoolExecutor (Python 3.14+)
# This executor uses sub-interpreters, each with its own GIL, providing
# true parallelism for CPU-bound tasks without the overhead of IPC.
try:
    from concurrent.futures import InterpreterPoolExecutor

    HAS_INTERPRETER_POOL = True
except ImportError:
    HAS_INTERPRETER_POOL = False
    InterpreterPoolExecutor = None  # type: ignore[misc, assignment]


def is_free_threaded() -> bool:
    """Check if running in free-threaded Python mode (GIL disabled).

    Free-threaded mode is available in Python 3.13+ builds compiled with
    --disable-gil and running with PYTHON_GIL=0 environment variable.

    Returns:
        True if the GIL is disabled, False otherwise.

    Example:
        >>> if is_free_threaded():
        ...     print("Running without GIL - true thread parallelism available")
    """
    if hasattr(sys, "_is_gil_enabled"):
        return not sys._is_gil_enabled()
    return False


def get_cpu_executor(max_workers: int | None = None) -> Executor:
    """Get the best executor for CPU-bound tasks.

    Returns InterpreterPoolExecutor if available (Python 3.14+),
    otherwise falls back to ThreadPoolExecutor.

    InterpreterPoolExecutor benefits:
    - Each interpreter has its own GIL (process-like isolation)
    - Lower memory overhead than multiprocessing (shared address space)
    - Faster communication than IPC (no pickling needed for simple types)

    Args:
        max_workers: Maximum worker count. Defaults to CPU count.

    Returns:
        Executor instance for CPU-bound work.

    Example:
        >>> with get_cpu_executor(max_workers=4) as executor:
        ...     futures = [executor.submit(compute, x) for x in data]
        ...     results = [f.result() for f in futures]
    """
    workers = max_workers or os.cpu_count() or 4

    if HAS_INTERPRETER_POOL and InterpreterPoolExecutor is not None:
        return InterpreterPoolExecutor(max_workers=workers)

    # Fallback for older Python versions
    return ThreadPoolExecutor(max_workers=workers)


def get_executor_type() -> str:
    """Get the type of executor that will be used by get_cpu_executor().

    This is useful for logging at startup to indicate which executor
    backend is active.

    Returns:
        String name of the executor class that will be used.

    Example:
        >>> logger.info(f"Using executor: {get_executor_type()}")
        Using executor: InterpreterPoolExecutor
    """
    if HAS_INTERPRETER_POOL:
        return "InterpreterPoolExecutor"
    return "ThreadPoolExecutor"


def get_executor_info() -> dict[str, object]:
    """Get detailed information about the executor configuration.

    This provides comprehensive information about the executor backend,
    Python version, and threading capabilities for diagnostics.

    Returns:
        Dictionary containing executor configuration details.

    Example:
        >>> info = get_executor_info()
        >>> print(json.dumps(info, indent=2))
    """
    return {
        "executor_type": get_executor_type(),
        "has_interpreter_pool": HAS_INTERPRETER_POOL,
        "is_free_threaded": is_free_threaded(),
        "python_version": sys.version_info[:3],
        "cpu_count": os.cpu_count(),
    }
