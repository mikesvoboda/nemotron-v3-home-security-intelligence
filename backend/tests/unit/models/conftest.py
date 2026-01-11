"""Pytest configuration for unit model tests.

This conftest forces soft delete tests to run serially to avoid database deadlocks.

The soft delete tests create database schema modifications (adding/removing rows)
that cause deadlocks when run in parallel via pytest-xdist. The xdist_group marker
should ideally prevent this, but in practice deadlocks still occur intermittently.

This conftest uses filelock to create a cross-process lock that ensures only one
soft delete test runs at a time across all pytest-xdist workers.
"""

import tempfile
from pathlib import Path

import pytest
from filelock import FileLock

# Path to the lock file (shared across all workers)
_LOCK_FILE = Path(tempfile.gettempdir()) / "pytest_soft_delete.lock"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Force soft delete tests to run serially by marking them with xdist_group.

    All test_soft_delete.py tests are marked with xdist_group to ensure they run
    on the same worker sequentially, reducing database contention.
    """
    for item in items:
        # Only apply to test_soft_delete.py tests
        # Add xdist_group marker to force all soft delete tests onto one worker
        if "test_soft_delete.py" in item.nodeid and not item.get_closest_marker("xdist_group"):
            item.add_marker(pytest.mark.xdist_group(name="soft_delete_serial"))


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
