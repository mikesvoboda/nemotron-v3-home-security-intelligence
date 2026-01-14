"""Pytest configuration for unit model tests.

This conftest forces soft delete tests to run serially to avoid database deadlocks.

The soft delete tests create database schema modifications (adding/removing rows)
that cause deadlocks when run in parallel via pytest-xdist. The xdist_group marker
should ideally prevent this, but in practice deadlocks still occur intermittently.

This conftest uses filelock to create a cross-process lock that ensures only one
soft delete test runs at a time across all pytest-xdist workers.

NOTE: The pytest_collection_modifyitems hook has been consolidated into the main
backend/tests/conftest.py to avoid multiple iterations over test items.
The xdist_group marker for soft_delete_serial is now applied there.
"""

import tempfile
from pathlib import Path

import pytest
from filelock import FileLock

# Path to the lock file (shared across all workers)
_LOCK_FILE = Path(tempfile.gettempdir()) / "pytest_soft_delete.lock"


# NOTE: pytest_collection_modifyitems has been removed from this file.
# All marker logic is now consolidated in backend/tests/conftest.py
# for O(n) instead of O(4n) complexity when processing test items.


@pytest.fixture(autouse=True, scope="function")
def _soft_delete_serial_lock(request: pytest.FixtureRequest):
    """Automatically acquire cross-process lock for soft delete tests.

    This fixture is automatically used by all tests in this directory.
    It acquires a filelock before running soft delete tests to prevent deadlocks
    across all pytest-xdist workers (which run in separate processes).
    """
    # Only lock for test_soft_delete.py tests
    if "test_soft_delete.py" not in request.node.nodeid:
        yield
        return

    # For soft delete tests, acquire the cross-process file lock
    lock = FileLock(_LOCK_FILE, timeout=60)
    with lock:
        yield
