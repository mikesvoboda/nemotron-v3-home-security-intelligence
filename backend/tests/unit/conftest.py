"""Unit test configuration and fixtures.

This module provides fixtures specific to unit tests in backend/tests/unit/.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


def pytest_collection_modifyitems(config, items):
    """Skip tests marked with 'integration' in unit test runs.

    Tests marked with @pytest.mark.integration require a real database
    connection and should not run during unit test execution.
    """
    skip_integration = pytest.mark.skip(
        reason="Integration test requires database - skipped in unit test run"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture(autouse=True)
def mock_transformers_for_speed(monkeypatch):
    """Mock transformers to speed up unit tests.

    The transformers package import takes ~0.54s. Since unit tests
    mock the actual model loading anyway, we mock the import to
    avoid this overhead on every test.

    Tests that need real transformers should use integration tests
    or explicitly unmock in the test.
    """
    # Only mock if not already imported (avoid breaking other tests)
    if "transformers" not in sys.modules:
        mock_transformers = MagicMock()
        # Configure from_pretrained to raise OSError for nonexistent paths
        # (matching real HuggingFace behavior)
        mock_transformers.AutoImageProcessor.from_pretrained.side_effect = OSError(
            "Can't load tokenizer for 'nonexistent'. Make sure that model path exists."
        )
        mock_transformers.AutoModelForImageClassification.from_pretrained.side_effect = OSError(
            "Can't load model for 'nonexistent'. Make sure that model path exists."
        )
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)
