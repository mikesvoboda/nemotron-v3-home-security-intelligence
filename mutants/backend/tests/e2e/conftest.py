"""E2E test fixtures.

This module provides E2E-specific fixtures. The shared fixtures (integration_db,
mock_redis, client, etc.) are inherited from backend/tests/conftest.py.

No duplicate fixture definitions - all common fixtures are centralized in the
root conftest.py file.
"""

# E2E tests use the shared fixtures from backend/tests/conftest.py:
# - integration_db: PostgreSQL test database via testcontainers
# - mock_redis: Mock Redis client
# - client: httpx AsyncClient for API testing
