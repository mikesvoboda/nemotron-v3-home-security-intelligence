"""Integration test fixtures.

This module provides integration-specific fixtures. The shared fixtures
(integration_db, mock_redis, client, etc.) are inherited from backend/tests/conftest.py.

No duplicate fixture definitions - all common fixtures are centralized in the
root conftest.py file.
"""

# Integration tests use the shared fixtures from backend/tests/conftest.py:
# - integration_env: Environment setup only (no DB init)
# - integration_db: Isolated temporary SQLite database
# - mock_redis: Mock Redis client
# - db_session: Database session for direct DB access
# - client: httpx AsyncClient for API testing

# Add any integration-specific fixtures below as needed.
