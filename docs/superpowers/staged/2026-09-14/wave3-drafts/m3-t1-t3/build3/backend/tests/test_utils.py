"""Shared test utilities and helper functions.

This module provides common utility functions used across different test types
(unit, integration, chaos, etc.) to avoid duplication.

Functions:
    - check_tcp_connection: Check if a TCP service is reachable
    - get_table_deletion_order: Compute FK-safe deletion order for tables
    - wait_for_postgres_container: Poll for PostgreSQL readiness
    - wait_for_redis_container: Poll for Redis readiness
"""

from __future__ import annotations

import logging
import random
import socket
import time
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy import MetaData
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

logger = logging.getLogger(__name__)


# =============================================================================
# Network/Service Connection Helpers
# =============================================================================


def check_tcp_connection(host: str = "localhost", port: int = 5432) -> bool:
    """Check if a TCP service is reachable on the given host/port.

    Args:
        host: Hostname or IP address to check
        port: Port number to check

    Returns:
        True if connection succeeds, False otherwise
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        logger.debug(
            "TCP connection check failed",
            extra={"host": host, "port": port, "error": str(e)},
        )
        return False


# =============================================================================
# Container Readiness Checks
# =============================================================================


def wait_for_postgres_container(
    container: PostgresContainer,
    timeout: float = 30.0,
    initial_delay: float = 0.1,
    max_delay: float = 2.0,
    fast_mode: bool = False,
) -> None:
    """Wait for PostgreSQL container to be ready using polling with exponential backoff.

    Args:
        container: PostgresContainer instance
        timeout: Maximum time to wait in seconds
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        fast_mode: If True, use faster polling for unit tests (0.01s initial, 0.05s max)

    Raises:
        TimeoutError: If PostgreSQL is not ready within timeout
    """
    # Override delays for fast mode (unit tests)
    if fast_mode:
        initial_delay = 0.01
        max_delay = 0.05
    import psycopg2

    start = time.monotonic()
    host = container.get_container_host_ip()
    port = int(container.get_exposed_port(5432))
    delay = initial_delay
    attempt = 0

    while time.monotonic() - start < timeout:
        attempt += 1
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user="postgres",
                password="postgres",  # pragma: allowlist secret
                dbname="security_test",
                connect_timeout=2,
            )
            conn.close()
            if attempt > 1:
                logger.info(f"PostgreSQL ready after {attempt} attempts")
            return
        except Exception as e:
            elapsed = time.monotonic() - start
            remaining = timeout - elapsed
            if remaining <= 0:
                break
            # Exponential backoff with jitter
            jitter = random.uniform(0, delay * 0.1)  # noqa: S311
            sleep_time = min(delay + jitter, remaining, max_delay)
            logger.debug(
                f"PostgreSQL not ready (attempt {attempt}): {e}, retrying in {sleep_time:.2f}s"
            )
            time.sleep(sleep_time)
            delay = min(delay * 2, max_delay)

    raise TimeoutError(f"PostgreSQL not ready after {timeout} seconds ({attempt} attempts)")


def wait_for_redis_container(
    container: RedisContainer,
    timeout: float = 30.0,
    initial_delay: float = 0.1,
    max_delay: float = 2.0,
    fast_mode: bool = False,
) -> None:
    """Wait for Redis container to be ready using polling with exponential backoff.

    Args:
        container: RedisContainer instance
        timeout: Maximum time to wait in seconds
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        fast_mode: If True, use faster polling for unit tests (0.01s initial, 0.05s max)

    Raises:
        TimeoutError: If Redis is not ready within timeout
    """
    # Override delays for fast mode (unit tests)
    if fast_mode:
        initial_delay = 0.01
        max_delay = 0.05
    import redis

    start = time.monotonic()
    host = container.get_container_host_ip()
    port = int(container.get_exposed_port(6379))
    delay = initial_delay
    attempt = 0

    while time.monotonic() - start < timeout:
        attempt += 1
        try:
            client = redis.Redis(host=host, port=port, socket_timeout=2)
            client.ping()
            client.close()
            if attempt > 1:
                logger.info(f"Redis ready after {attempt} attempts")
            return
        except Exception as e:
            elapsed = time.monotonic() - start
            remaining = timeout - elapsed
            if remaining <= 0:
                break
            # Exponential backoff with jitter
            jitter = random.uniform(0, delay * 0.1)  # noqa: S311
            sleep_time = min(delay + jitter, remaining, max_delay)
            logger.debug(f"Redis not ready (attempt {attempt}): {e}, retrying in {sleep_time:.2f}s")
            time.sleep(sleep_time)
            delay = min(delay * 2, max_delay)

    raise TimeoutError(f"Redis not ready after {timeout} seconds ({attempt} attempts)")


# =============================================================================
# Database Table Ordering
# =============================================================================


def get_table_deletion_order(metadata: MetaData) -> list[str]:
    """Compute the correct table deletion order based on foreign key relationships.

    Uses a topological sort to determine the order in which tables should be deleted
    to respect foreign key constraints. Tables that reference other tables must be
    deleted before the tables they reference.

    Args:
        metadata: SQLAlchemy MetaData object containing table definitions

    Returns:
        List of table names in the order they should be deleted (leaf tables first,
        parent tables last)
    """
    # Build a dependency graph: table -> set of tables it references
    # A table "depends on" another if it has a FK pointing to it
    dependencies: dict[str, set[str]] = defaultdict(set)
    all_tables: set[str] = set()

    for table in metadata.tables.values():
        table_name = table.name
        all_tables.add(table_name)
        for fk in table.foreign_keys:
            # fk.column.table.name is the table being referenced
            referenced_table = fk.column.table.name
            dependencies[table_name].add(referenced_table)
            all_tables.add(referenced_table)

    # Topological sort using Kahn's algorithm
    # We want tables with dependencies to come FIRST (delete children before parents)
    # So we invert the typical topological sort order

    # Build reverse dependency graph: table -> tables that depend on it
    dependents: dict[str, set[str]] = defaultdict(set)
    for table, deps in dependencies.items():
        for dep in deps:
            dependents[dep].add(table)

    # Count how many tables each table references (in-degree in dependency graph)
    in_degree: dict[str, int] = {table: len(dependencies[table]) for table in all_tables}

    # Tables with no dependencies can be processed first in normal topo sort
    # But we want children first, so we'll collect all and reverse
    result: list[str] = []
    queue: list[str] = [table for table in all_tables if in_degree[table] == 0]

    while queue:
        # Process a table with no remaining dependencies
        table = queue.pop(0)
        result.append(table)

        # Remove this table from dependencies of other tables
        for dependent in dependents[table]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    # Reverse to get deletion order (children/leaf tables first, parents last)
    result.reverse()

    # Handle any remaining tables (circular dependencies - shouldn't happen with proper schema)
    remaining = all_tables - set(result)
    if remaining:
        logger.warning(
            "Circular dependencies detected in schema",
            extra={"remaining_tables": sorted(remaining)},
        )
        result.extend(sorted(remaining))

    return result
