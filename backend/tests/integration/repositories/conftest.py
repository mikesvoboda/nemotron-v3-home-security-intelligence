"""Pytest configuration for repository unit tests.

Repository tests require serial execution because they share database state
and cannot be safely parallelized with pytest-xdist. The test_db fixture
does not provide per-worker database isolation like integration tests do.

To run these tests:
    pytest backend/tests/unit/repositories/ -n0  # Force serial execution
"""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest for repository tests - disable xdist if in this directory."""
    import warnings

    # Check if we're running repository tests with xdist enabled
    args = config.args
    is_repository_tests = any("repositories" in str(arg) for arg in args)
    has_xdist = config.getoption("numprocesses", default=None)

    if is_repository_tests and has_xdist:
        warnings.warn(
            "Repository unit tests detected. These tests share database state and "
            "may experience deadlocks when run with pytest-xdist. "
            "Run with -n0 to force serial execution: "
            "pytest backend/tests/unit/repositories/ -n0",
            UserWarning,
            stacklevel=2,
        )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Force repository tests to run serially by grouping them to a single worker.

    All tests in this directory are marked with xdist_group to ensure they run
    on the same worker, reducing (but not eliminating) database contention.
    """
    for item in items:
        # Add xdist_group marker to force all repo tests onto one worker
        if not item.get_closest_marker("xdist_group"):
            item.add_marker(pytest.mark.xdist_group(name="repository_tests_serial"))
        if not item.get_closest_marker("serial"):
            item.add_marker(pytest.mark.serial)
