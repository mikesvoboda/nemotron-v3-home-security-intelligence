"""Pytest configuration for repository integration tests.

Repository tests require serial execution because they share database state
and cannot be safely parallelized with pytest-xdist. The test_db fixture
does not provide per-worker database isolation like integration tests do.

To run these tests:
    pytest backend/tests/integration/repositories/ -n0  # Force serial execution

NOTE: The pytest_collection_modifyitems hook has been consolidated into the main
backend/tests/conftest.py to avoid multiple iterations over test items.
The xdist_group and serial markers for repository tests are now applied there.
"""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest for repository tests - warn if xdist is enabled."""
    import warnings

    # Check if we're running repository tests with xdist enabled
    args = config.args
    is_repository_tests = any("repositories" in str(arg) for arg in args)
    has_xdist = config.getoption("numprocesses", default=None)

    if is_repository_tests and has_xdist:
        warnings.warn(
            "Repository integration tests detected. These tests share database state and "
            "may experience deadlocks when run with pytest-xdist. "
            "Run with -n0 to force serial execution: "
            "pytest backend/tests/integration/repositories/ -n0",
            UserWarning,
            stacklevel=2,
        )


# NOTE: pytest_collection_modifyitems has been removed from this file.
# All marker logic is now consolidated in backend/tests/conftest.py
# for O(n) instead of O(4n) complexity when processing test items.
