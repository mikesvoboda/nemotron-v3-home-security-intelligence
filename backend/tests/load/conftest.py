"""Pytest configuration for load tests.

This module provides load test-specific fixtures and configuration.
Load tests focus on performance validation under realistic workloads.

Implements NEM-3340: Load Testing for New Features (Phase 7.4).
"""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Mark all tests in the load directory appropriately.

    Load tests are automatically marked with:
    - 'load': Identifies as load/performance test
    - Longer timeout by default
    """
    for item in items:
        fspath_str = str(item.fspath)

        if "/load/" in fspath_str:
            # Mark all load tests
            if not item.get_closest_marker("load"):
                item.add_marker(pytest.mark.load)

            # Apply longer timeout for load tests unless already set
            if not item.get_closest_marker("timeout") and not item.get_closest_marker("slow"):
                # Default 30 second timeout for load tests
                item.add_marker(pytest.mark.timeout(30))
