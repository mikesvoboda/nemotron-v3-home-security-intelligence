"""Unit test configuration and fixtures.

This module provides fixtures specific to unit tests in backend/tests/unit/.

NOTE: Marker application logic (skipping integration tests, applying unit marker)
has been consolidated into the main backend/tests/conftest.py to avoid multiple
iterations over test items. See pytest_collection_modifyitems in conftest.py.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# NOTE: pytest_collection_modifyitems has been removed from this file.
# All marker logic is now consolidated in backend/tests/conftest.py
# for O(n) instead of O(4n) complexity when processing test items.


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


@pytest.fixture(autouse=True)
def set_test_environment(monkeypatch):
    """Set ENVIRONMENT=test to bypass production password validation.

    The Settings class defaults to environment='production', which triggers
    password strength validation. Unit tests use weak/test passwords, so
    setting ENVIRONMENT=test bypasses this validation.
    """
    monkeypatch.setenv("ENVIRONMENT", "test")
