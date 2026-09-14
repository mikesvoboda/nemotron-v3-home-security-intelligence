"""Integration tests for system API endpoints.

This module re-exports tests from test_system_api.py to satisfy the
naming convention check. The actual tests are in test_system_api.py
which contains comprehensive coverage for all system endpoints.
"""

# Re-export all tests from test_system_api.py
from backend.tests.integration.test_system_api import *  # noqa: F403
