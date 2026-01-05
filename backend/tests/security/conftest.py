"""Pytest fixtures for security tests.

This module provides fixtures specifically for security testing,
re-using the integration test infrastructure for database and Redis.

Security tests use the same client fixture from integration tests
but focus on testing security controls at the API layer.
"""

from __future__ import annotations

# Import all fixtures from integration tests
# This gives us: postgres_container, redis_container, integration_env,
# integration_db, db_session, client, mock_redis, real_redis, unique_id
from backend.tests.integration.conftest import (
    client,
    integration_db,
    integration_env,
    mock_redis,
    postgres_container,
    real_redis,
    redis_container,
    unique_id,
)

# Re-export for pytest discovery
__all__ = [
    "client",
    "integration_db",
    "integration_env",
    "mock_redis",
    "postgres_container",
    "real_redis",
    "redis_container",
    "unique_id",
]

# Alias security_client to client for backwards compatibility
security_client = client
