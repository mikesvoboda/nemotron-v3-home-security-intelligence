"""Integration tests for OSNet loader.

These tests are implemented in test_model_loaders.py as TestOSNetLoaderIntegration.
This file exists to satisfy the pre-commit hook check-integration-tests.py.
"""

# Import all tests and fixtures from the main test file
from backend.tests.integration.services.test_model_loaders import (  # noqa: F401
    TestOSNetLoaderIntegration,
    mock_transformers,
    reset_singletons,
)
