"""Integration test fixtures with pytest-xdist worker-scoped database isolation.

This module provides integration-specific fixtures that enable PARALLEL execution
of integration tests using pytest-xdist. Each xdist worker gets its own isolated
database to prevent race conditions.

Key fixtures:
- postgres_container: Session-scoped PostgreSQL container (or local service)
- redis_container: Session-scoped Redis container (or local service)
- worker_db_url: Worker-specific database URL (each xdist worker gets own DB)
- integration_db: Initialize database with fresh schema per worker
- db_session: Per-test database session
- client: HTTP client for API testing
- mock_redis: Mock Redis client for tests that don't need real Redis
- real_redis: Real Redis client for tests that need real Redis behavior

Parallel Execution Strategy:
1. pytest-xdist spawns multiple workers (gw0, gw1, gw2, etc.)
2. Each worker creates its own database (security_test_gw0, security_test_gw1, etc.)
3. Tests are distributed across workers using the worksteal scheduler
4. Each worker cleans up its database at session end

In development environments (with local Podman containers), the fixtures
use the local services for faster test execution. In CI/headless environments,
testcontainers are used for full isolation.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import xdist
from sqlalchemy import inspect

from backend.tests.test_utils import (
    check_tcp_connection,
    wait_for_postgres_container,
    wait_for_redis_container,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Table Dependency Detection
# =============================================================================


# Fallback hardcoded table order in case reflection fails
# NOTE: Only include tables that actually exist in the schema.
# New tables should be added here when their migrations are created.
HARDCODED_TABLE_DELETION_ORDER = [
    # First: Delete tables with foreign key references (leaf tables)
    "alerts",
    "event_audits",
    "detections",
    "activity_baselines",
    "class_baselines",
    "events",
    "scene_changes",
    "camera_notification_settings",  # FK to cameras
    "zones",  # FK to cameras - must be deleted before cameras
    # Second: Delete tables without FK references (standalone)
    "alert_rules",
    "audit_logs",
    "gpu_stats",
    "logs",
    "prompt_configs",
    "quiet_hours_periods",
    "notification_preferences",
    "job_transitions",  # Job transition history
    "job_logs",  # Job execution logs
    "job_attempts",  # Job attempt records
    "jobs",  # Job tracking
    # Last: Delete parent tables
    "cameras",
]


def _build_dependency_graph(inspector, tables: set[str]) -> dict[str, set[str]]:
    """Build a dependency graph from foreign key relationships.

    Args:
        inspector: SQLAlchemy inspector instance
        tables: Set of table names to process

    Returns:
        Dictionary mapping each table to the set of tables it references via FK
    """
    dependencies: dict[str, set[str]] = defaultdict(set)
    for table in tables:
        try:
            fks = inspector.get_foreign_keys(table)
            for fk in fks:
                referred_table = fk.get("referred_table")
                if referred_table and referred_table in tables:
                    # table depends on referred_table
                    dependencies[table].add(referred_table)
        except Exception as e:
            logger.warning(f"Failed to get foreign keys for {table}: {e}")

    # Ensure all tables are in the dependencies dict (even those with no FKs)
    for table in tables:
        if table not in dependencies:
            dependencies[table] = set()

    return dependencies


def _topological_sort(tables: set[str], dependencies: dict[str, set[str]]) -> list[str] | None:
    """Perform topological sort using Kahn's algorithm.

    Args:
        tables: Set of all table names
        dependencies: Dictionary mapping each table to tables it references

    Returns:
        Sorted list of table names, or None if a cycle is detected
    """
    # Count incoming edges (tables that depend on each table)
    in_degree: dict[str, int] = dict.fromkeys(tables, 0)
    for table, deps in dependencies.items():
        for dep in deps:
            in_degree[dep] = in_degree.get(dep, 0) + 1

    # Start with tables that have no incoming edges (nothing depends on them)
    # These are the leaf tables that should be deleted first
    queue = [table for table, degree in in_degree.items() if degree == 0]
    sorted_tables: list[str] = []

    while queue:
        # Sort for deterministic ordering
        queue.sort()
        table = queue.pop(0)
        sorted_tables.append(table)

        # Remove this table's edges
        for dep in dependencies.get(table, set()):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    # Check for cycles
    if len(sorted_tables) != len(tables):
        return None

    return sorted_tables


def get_table_deletion_order(engine) -> list[str]:
    """Get tables in FK-safe deletion order using topological sort.

    Uses SQLAlchemy's inspector to dynamically discover all tables and their
    foreign key relationships, then performs a topological sort to determine
    the safe deletion order. Tables that reference other tables (via FK) must
    be deleted first.

    Args:
        engine: SQLAlchemy engine (sync or async)

    Returns:
        List of table names in safe deletion order (dependent tables first,
        parent tables last).
    """
    try:
        # For async engines, we need to get the sync engine
        sync_engine = getattr(engine, "sync_engine", engine)
        inspector = inspect(sync_engine)
        tables = set(inspector.get_table_names())

        if not tables:
            logger.warning("No tables found via reflection, using hardcoded order")
            return HARDCODED_TABLE_DELETION_ORDER

        # Build dependency graph from foreign key relationships
        dependencies = _build_dependency_graph(inspector, tables)

        # Perform topological sort
        sorted_tables = _topological_sort(tables, dependencies)

        if sorted_tables is None:
            remaining = tables - set(sorted_tables or [])
            logger.error(f"Circular dependency detected among tables: {remaining}")
            logger.warning("Falling back to hardcoded table order")
            return HARDCODED_TABLE_DELETION_ORDER

        logger.debug(f"Computed table deletion order: {sorted_tables}")
        return sorted_tables

    except Exception as e:
        logger.warning(f"Failed to compute table deletion order: {e}")
        logger.warning("Falling back to hardcoded table order")
        return HARDCODED_TABLE_DELETION_ORDER


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    from backend.core.redis import RedisClient

# Logger for test infrastructure
logger = logging.getLogger(__name__)


# =============================================================================
# Service Detection
# =============================================================================

# Default development PostgreSQL URL (matches docker-compose.yml)
DEFAULT_DEV_POSTGRES_URL = "postgresql+asyncpg://security:security_dev_password@localhost:5432/security"  # pragma: allowlist secret

# Default development Redis URL (matches docker-compose.yml, using DB 15 for test isolation)
DEFAULT_DEV_REDIS_URL = "redis://localhost:6379/15"


def _check_local_postgres() -> bool:
    """Check if local PostgreSQL is running on port 5432.

    Uses shared check_tcp_connection from backend.tests.test_utils.
    """
    return check_tcp_connection("localhost", 5432)


def _check_local_redis() -> bool:
    """Check if local Redis is running on port 6379.

    Uses shared check_tcp_connection from backend.tests.test_utils.
    """
    return check_tcp_connection("localhost", 6379)


# =============================================================================
# Worker ID Utilities for pytest-xdist
# =============================================================================


def get_worker_id(request: pytest.FixtureRequest) -> str:
    """Get the pytest-xdist worker ID ('gw0', 'gw1', etc.) or 'master'.

    When running without xdist (-n0 or no -n flag), returns 'master'.
    """
    return xdist.get_xdist_worker_id(request)


def get_worker_db_name(worker_id: str) -> str:
    """Generate a unique database name for the xdist worker.

    Args:
        worker_id: The xdist worker ID ('gw0', 'gw1', 'master')

    Returns:
        Database name like 'security_test_gw0' or 'security_test' for master
    """
    if worker_id == "master":
        return "security_test"
    return f"security_test_{worker_id}"


# =============================================================================
# Session-Scoped Service Fixtures (shared across all tests in worker session)
# =============================================================================


# Wrapper class for local services to provide consistent interface
class LocalPostgresService:
    """Wrapper for local PostgreSQL service to mimic testcontainer interface."""

    def get_container_host_ip(self) -> str:
        return "localhost"

    def get_exposed_port(self, port: int) -> int:
        return 5432

    def get_connection_url(self) -> str:
        """Get PostgreSQL connection URL, preferring CI environment variables.

        Priority order:
        1. TEST_DATABASE_URL (explicit CI override)
        2. DATABASE_URL (also set in CI)
        3. DEFAULT_DEV_POSTGRES_URL (local development fallback)
        """
        # Check CI environment variables first
        env_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
        if env_url:
            # Ensure asyncpg driver
            if "postgresql://" in env_url and "asyncpg" not in env_url:
                env_url = env_url.replace("postgresql://", "postgresql+asyncpg://")
            return env_url
        return DEFAULT_DEV_POSTGRES_URL


class LocalRedisService:
    """Wrapper for local Redis service to mimic testcontainer interface."""

    def get_container_host_ip(self) -> str:
        return "localhost"

    def get_exposed_port(self, port: int) -> int:
        return 6379


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer | LocalPostgresService]:
    """Provide a session-scoped PostgreSQL service for all integration tests.

    Uses local PostgreSQL if available (development with Podman),
    otherwise starts a testcontainer for full isolation.

    Note: This fixture provides the PostgreSQL server. Each xdist worker
    creates its own database within this server via the worker_db_url fixture.
    """
    # Check for explicit environment variable override
    if os.environ.get("TEST_DATABASE_URL"):
        yield LocalPostgresService()
        return

    # Check for local PostgreSQL (development environment with Podman/Docker)
    if _check_local_postgres():
        yield LocalPostgresService()
        return

    # Fall back to testcontainer
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer(
        "postgres:16-alpine",
        username="postgres",
        password="postgres",  # pragma: allowlist secret
        dbname="security_test",
        driver="asyncpg",
    )
    container.start()

    try:
        wait_for_postgres_container(container)
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def redis_container() -> Generator[RedisContainer | LocalRedisService]:
    """Provide a session-scoped Redis service for all integration tests.

    Uses local Redis if available (development with Podman),
    otherwise starts a testcontainer for full isolation.

    Note: Each xdist worker uses a different Redis database number (0-15)
    for isolation via the worker_redis_url fixture.
    """
    # Check for explicit environment variable override
    if os.environ.get("TEST_REDIS_URL"):
        yield LocalRedisService()
        return

    # Check for local Redis (development environment with Podman/Docker)
    if _check_local_redis():
        yield LocalRedisService()
        return

    # Fall back to testcontainer
    from testcontainers.redis import RedisContainer

    container = RedisContainer("redis:7-alpine")
    container.start()

    try:
        wait_for_redis_container(container)
        yield container
    finally:
        container.stop()


def _get_postgres_url(container: PostgresContainer | LocalPostgresService) -> str:
    """Get PostgreSQL URL from container or local service."""
    if isinstance(container, LocalPostgresService):
        # Check for explicit environment variable override (e.g., CI environment)
        env_url = os.environ.get("TEST_DATABASE_URL")
        if env_url:
            # Ensure asyncpg driver
            if "postgresql://" in env_url and "asyncpg" not in env_url:
                env_url = env_url.replace("postgresql://", "postgresql+asyncpg://")
            return env_url
        return DEFAULT_DEV_POSTGRES_URL

    url = container.get_connection_url()
    # Replace psycopg2 driver with asyncpg
    return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")


def _get_redis_url(container: RedisContainer | LocalRedisService) -> str:
    """Get Redis URL from container or local service."""
    if isinstance(container, LocalRedisService):
        # Check for explicit environment variable override (e.g., CI environment)
        env_url = os.environ.get("TEST_REDIS_URL")
        if env_url:
            return env_url
        return DEFAULT_DEV_REDIS_URL

    host = container.get_container_host_ip()
    port = container.get_exposed_port(6379)
    # Use database 15 for test isolation
    return f"redis://{host}:{port}/15"


def _get_worker_redis_db(worker_id: str) -> int:
    """Get Redis database number for the xdist worker.

    Workers gw0-gw14 use databases 0-14, master uses 15.
    This provides isolation between parallel workers.

    Args:
        worker_id: The xdist worker ID ('gw0', 'gw1', 'master')

    Returns:
        Redis database number (0-15)
    """
    if worker_id == "master":
        return 15
    # Extract number from 'gw0', 'gw1', etc.
    try:
        worker_num = int(worker_id.replace("gw", ""))
        # Keep within valid Redis DB range (0-15)
        return min(worker_num, 14)
    except ValueError:
        return 15


def _create_worker_database(base_url: str, db_name: str) -> str:
    """Create a worker-specific database and return its URL.

    This function connects to the PostgreSQL server and creates a new database
    for the worker if it doesn't exist. It uses psycopg2 in synchronous mode
    since this runs during fixture setup.

    Args:
        base_url: The base PostgreSQL URL (pointing to the main database)
        db_name: The name of the database to create

    Returns:
        The full PostgreSQL URL pointing to the worker's database
    """
    from urllib.parse import urlparse, urlunparse

    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    # Parse the base URL to get connection details
    parsed = urlparse(base_url.replace("+asyncpg", ""))
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    user = parsed.username or "postgres"
    password = parsed.password or "postgres"
    base_db = parsed.path.lstrip("/") or "postgres"

    # Connect to the base database to create the worker database
    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=base_db,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

    try:
        with conn.cursor() as cur:
            # Check if database exists
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (db_name,),
            )
            if not cur.fetchone():
                # Create the database (safe: db_name is generated internally)
                cur.execute(f'CREATE DATABASE "{db_name}"')
                logger.info(f"Created worker database: {db_name}")
    finally:
        conn.close()

    # Build the URL for the worker database
    # Replace the database name in the path
    new_parsed = parsed._replace(path=f"/{db_name}")
    worker_url = urlunparse(new_parsed)

    # Add asyncpg driver back
    worker_url = worker_url.replace("postgresql://", "postgresql+asyncpg://")

    return worker_url


def _drop_worker_database(base_url: str, db_name: str) -> None:
    """Drop a worker-specific database during cleanup.

    Args:
        base_url: The base PostgreSQL URL (pointing to the main database)
        db_name: The name of the database to drop
    """
    from urllib.parse import urlparse

    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    # Don't drop the main database
    if db_name in ("security", "security_test", "postgres"):
        return

    # Parse the base URL to get connection details
    parsed = urlparse(base_url.replace("+asyncpg", ""))
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    user = parsed.username or "postgres"
    password = parsed.password or "postgres"

    # Connect to postgres database (not the one we're dropping)
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname="postgres",
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        try:
            with conn.cursor() as cur:
                # Terminate connections to the database
                cur.execute(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = %s AND pid <> pg_backend_pid()
                    """,
                    (db_name,),
                )
                # Drop the database (safe: db_name is generated internally)
                cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
                logger.info(f"Dropped worker database: {db_name}")
        finally:
            conn.close()
    except Exception as e:
        # Log but don't fail - cleanup errors shouldn't fail tests
        logger.warning(f"Failed to drop worker database {db_name}: {e}")


# =============================================================================
# Worker-Scoped Database Fixtures (for pytest-xdist parallel execution)
# =============================================================================


@pytest.fixture(scope="session")
def worker_db_url(
    request: pytest.FixtureRequest,
    postgres_container: PostgresContainer | LocalPostgresService,
) -> Generator[str]:
    """Create and provide a worker-specific database URL for parallel test execution.

    Each pytest-xdist worker gets its own database to prevent interference:
    - gw0 -> security_test_gw0
    - gw1 -> security_test_gw1
    - master (serial) -> security_test

    The database is created at session start and dropped at session end.

    Returns:
        PostgreSQL connection URL for the worker's database
    """
    worker_id = get_worker_id(request)
    db_name = get_worker_db_name(worker_id)
    base_url = _get_postgres_url(postgres_container)

    # Create the worker database
    worker_url = _create_worker_database(base_url, db_name)

    logger.info(f"Worker {worker_id} using database: {db_name}")

    try:
        yield worker_url
    finally:
        # Clean up the worker database at session end
        _drop_worker_database(base_url, db_name)


@pytest.fixture(scope="session")
def worker_redis_url(
    request: pytest.FixtureRequest,
    redis_container: RedisContainer | LocalRedisService,
) -> str:
    """Get a worker-specific Redis URL for parallel test execution.

    Each pytest-xdist worker uses a different Redis database number:
    - gw0 -> database 0
    - gw1 -> database 1
    - master -> database 15

    Returns:
        Redis connection URL with worker-specific database number
    """
    worker_id = get_worker_id(request)
    redis_db = _get_worker_redis_db(worker_id)

    if isinstance(redis_container, LocalRedisService):
        # For local Redis, use the worker-specific database
        return f"redis://localhost:6379/{redis_db}"

    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    return f"redis://{host}:{port}/{redis_db}"


# =============================================================================
# Environment and Database Fixtures
# =============================================================================


@pytest.fixture
def integration_env(
    worker_db_url: str,
    worker_redis_url: str,
) -> Generator[str]:
    """Set DATABASE_URL/REDIS_URL for integration tests using worker-specific URLs.

    This fixture sets environment variables pointing to the worker's isolated
    PostgreSQL database and Redis database for parallel test execution.
    """
    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")
    original_redis_url = os.environ.get("REDIS_URL")
    original_runtime_env_path = os.environ.get("HSI_RUNTIME_ENV_PATH")

    # Create temporary directory for runtime env
    tmpdir = tempfile.mkdtemp()
    runtime_env_path = str(Path(tmpdir) / "runtime.env")

    # Use worker-specific URLs for parallel isolation
    os.environ["DATABASE_URL"] = worker_db_url
    os.environ["REDIS_URL"] = worker_redis_url
    os.environ["HSI_RUNTIME_ENV_PATH"] = runtime_env_path

    # Configure pool sizes for integration tests to prevent "too many clients" errors.
    # In CI environments, we use larger pools for better parallelism.
    # In local development, we use smaller pools to prevent exhausting connections.
    if os.environ.get("CI"):
        # CI: Larger pools for better parallelism with GitHub Actions runners
        os.environ["DATABASE_POOL_SIZE"] = "10"
        os.environ["DATABASE_POOL_OVERFLOW"] = "5"
        logger.debug("CI environment detected: using larger database pool (10+5)")
    else:
        # Local: Smaller pools to prevent "too many clients" errors.
        # Even serial test execution (-n0) can hit PostgreSQL's max_connections
        # limit (typically 100) because each test creates its own engine pool.
        # With default settings (pool_size=20, max_overflow=30), just 2-3 tests
        # can exhaust the connection limit. Use pool_size=5, max_overflow=2.
        os.environ["DATABASE_POOL_SIZE"] = "5"
        os.environ["DATABASE_POOL_OVERFLOW"] = "2"

    get_settings.cache_clear()

    try:
        yield worker_db_url
    finally:
        # Restore env
        if original_db_url is not None:
            os.environ["DATABASE_URL"] = original_db_url
        else:
            os.environ.pop("DATABASE_URL", None)

        if original_redis_url is not None:
            os.environ["REDIS_URL"] = original_redis_url
        else:
            os.environ.pop("REDIS_URL", None)

        if original_runtime_env_path is not None:
            os.environ["HSI_RUNTIME_ENV_PATH"] = original_runtime_env_path
        else:
            os.environ.pop("HSI_RUNTIME_ENV_PATH", None)

        get_settings.cache_clear()

        # Cleanup temp directory
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
async def integration_db(integration_env: str) -> AsyncGenerator[str]:
    """Initialize a PostgreSQL test database for integration tests.

    This fixture:
    - Depends on integration_env for environment setup
    - Initializes the database with fresh schema
    - Yields the database URL
    - Cleans up after the test

    Note: This is function-scoped because pytest-asyncio doesn't support
    module-scoped async fixtures well. When local services are used
    (development), tests share the database but use unique IDs to avoid
    conflicts. When testcontainers are used (CI), each module gets isolated
    containers.

    Uses a PostgreSQL advisory lock to prevent deadlocks when multiple
    pytest-xdist workers attempt to modify schema concurrently.
    """
    import hashlib

    from sqlalchemy import text

    from backend.core.config import get_settings
    from backend.core.database import close_db, get_engine, init_db

    # Import all models to ensure they're registered with Base.metadata
    from backend.models import Camera, Detection, Event, GPUStats  # noqa: F401
    from backend.models.camera import Base as ModelsBase

    # Ensure clean state
    get_settings.cache_clear()
    await close_db()

    # Initialize database (creates engine)
    await init_db()

    # Advisory lock key for integration test schema initialization
    # This prevents concurrent DDL operations that could cause deadlocks
    _INTEGRATION_SCHEMA_LOCK_NAMESPACE = "home_security_intelligence.integration_test_schema"
    _INTEGRATION_SCHEMA_LOCK_KEY = int(
        hashlib.sha256(_INTEGRATION_SCHEMA_LOCK_NAMESPACE.encode()).hexdigest()[:15], 16
    )

    # Create all tables with advisory lock to prevent deadlock on concurrent DDL
    engine = get_engine()
    async with engine.begin() as conn:
        # Acquire advisory lock to serialize DDL operations across pytest-xdist workers
        # Using pg_try_advisory_lock with retry to prevent hanging if lock is held by dead worker
        # Set a statement timeout to prevent indefinite blocking
        await conn.execute(text("SET statement_timeout = '20s'"))

        lock_acquired = False
        max_attempts = 30  # 30 attempts * 1s = 30s max wait
        for attempt in range(max_attempts):
            result = await conn.execute(
                text(f"SELECT pg_try_advisory_lock({_INTEGRATION_SCHEMA_LOCK_KEY})")  # nosemgrep
            )
            lock_acquired = result.scalar()
            if lock_acquired:
                break
            # Wait before retry (use asyncio.sleep for async context)
            await asyncio.sleep(1.0)

        if not lock_acquired:
            logger.warning(
                f"Failed to acquire advisory lock after {max_attempts} attempts, proceeding anyway"
            )

        try:
            # Create all tables
            await conn.run_sync(ModelsBase.metadata.create_all)

            # Add any missing columns (using IF NOT EXISTS for idempotency)
            await conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS llm_prompt TEXT"))
            await conn.execute(
                text("ALTER TABLE detections ADD COLUMN IF NOT EXISTS enrichment_data JSONB")
            )
            # NEM-1652: Add soft delete columns
            await conn.execute(
                text(
                    "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE events ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE"
                )
            )

            # Add unique indexes for cameras table (migration adds these for production)
            # First, clean up any duplicate cameras that might prevent index creation

            # Delete duplicate cameras by name (keep oldest)
            await conn.execute(
                text(
                    """
                    DELETE FROM cameras
                    WHERE id IN (
                        SELECT id FROM (
                            SELECT id,
                                   ROW_NUMBER() OVER (
                                       PARTITION BY name
                                       ORDER BY created_at ASC, id ASC
                                   ) as rn
                            FROM cameras
                        ) ranked
                        WHERE rn > 1
                    )
                    """
                )
            )

            # Delete duplicate cameras by folder_path (keep oldest)
            await conn.execute(
                text(
                    """
                    DELETE FROM cameras
                    WHERE id IN (
                        SELECT id FROM (
                            SELECT id,
                                   ROW_NUMBER() OVER (
                                       PARTITION BY folder_path
                                       ORDER BY created_at ASC, id ASC
                                   ) as rn
                            FROM cameras
                        ) ranked
                        WHERE rn > 1
                    )
                    """
                )
            )

            # Now create unique indexes (using IF NOT EXISTS for idempotency)
            await conn.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS idx_cameras_name_unique ON cameras (name)")
            )
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_cameras_folder_path_unique ON cameras (folder_path)"
                )
            )
        finally:
            # Release the advisory lock only if we acquired it
            if lock_acquired:
                # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text, sqlalchemy-raw-text-injection
                unlock_sql = text(f"SELECT pg_advisory_unlock({_INTEGRATION_SCHEMA_LOCK_KEY})")
                await conn.execute(unlock_sql)
            # Reset statement timeout
            await conn.execute(text("RESET statement_timeout"))

    try:
        yield integration_env
    finally:
        # Clean up test cameras before closing the database
        await _cleanup_test_cameras()
        await close_db()
        get_settings.cache_clear()


# =============================================================================
# Per-Test Fixtures
# =============================================================================


@pytest.fixture
async def clean_tables(integration_db: str) -> AsyncGenerator[None]:
    """Delete all data from tables before and after test for proper isolation.

    This fixture should be used by tests that need a clean database state.
    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks
    when tests run in parallel.

    The table deletion order is automatically determined using SQLAlchemy's
    reflection API to inspect foreign key relationships.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine, get_session

    async def delete_all() -> None:
        engine = get_engine()
        if engine is None:
            return

        # Get tables in FK-safe deletion order
        deletion_order = get_table_deletion_order(engine)

        async with get_session() as session:
            # Delete data in order (respecting foreign key constraints)
            for table_name in deletion_order:
                try:
                    # Safe: table_name comes from SQLAlchemy inspector (trusted source), not user input
                    await session.execute(text(f"DELETE FROM {table_name}"))  # noqa: S608 nosemgrep
                except Exception as e:
                    # Skip tables that don't exist
                    logger.debug(f"Skipping table {table_name}: {e}")
            await session.commit()

    # Delete before test
    await delete_all()

    yield

    # Delete after test (cleanup)
    await delete_all()


@pytest.fixture
async def db_session(integration_db: str):
    """Yield a live AsyncSession bound to the integration test database.

    This fixture provides a database session for each test. When used with
    the `client` fixture (API tests), the `client` fixture handles cleanup
    via DELETE statements before and after each test.

    When used standalone (without `client`), use `isolated_db_session`
    for automatic savepoint-based rollback.

    Note: The session uses autocommit=False, so you must call
    `await session.commit()` to persist changes.
    """
    from backend.core.database import get_session

    async with get_session() as session:
        yield session


@pytest.fixture
async def isolated_db_session(integration_db: str):
    """Yield an isolated AsyncSession with transaction rollback for each test.

    This fixture provides a database session for each test with automatic
    transaction rollback after the test completes. This ensures:
    - Test data doesn't persist after test completion
    - Tests can run repeatedly without data accumulation
    - Test failures still trigger proper cleanup via rollback

    Implementation uses PostgreSQL savepoints:
    1. Start a transaction and create a savepoint before the test
    2. Yield the session to the test
    3. Rollback to the savepoint after the test (success or failure)

    IMPORTANT: Do NOT use this fixture with `client` fixture - use `db_session` instead.
    The `client` fixture handles cleanup via DELETE statements.
    """
    from sqlalchemy import text

    from backend.core.database import get_session_factory

    # Get a raw session (not the auto-commit context manager)
    factory = get_session_factory()
    session = factory()

    try:
        # Start a savepoint that we'll roll back to after the test
        await session.execute(text("SAVEPOINT test_savepoint"))

        yield session
    finally:
        # Roll back to savepoint to undo all changes from this test
        # This works whether the test passed, failed, or raised an exception
        try:
            await session.execute(text("ROLLBACK TO SAVEPOINT test_savepoint"))
        except Exception:
            # If rollback fails, just rollback the entire transaction
            await session.rollback()
        finally:
            await session.close()


@pytest.fixture
async def session(isolated_db_session):
    """Alias for isolated_db_session to maintain compatibility with tests using 'session'.

    This overrides the root conftest.py 'session' fixture for integration tests,
    providing worker-isolated database access for parallel execution.

    Tests in backend/tests/integration/ that use the 'session' fixture will
    automatically use the worker-specific database.
    """
    # isolated_db_session is the actual AsyncSession object, not None
    # Just yield it directly for tests to use
    return isolated_db_session


@pytest.fixture
async def mock_redis() -> AsyncGenerator[AsyncMock]:
    """Mock Redis operations so tests don't require actual Redis operations.

    This fixture provides a mock Redis client with common operations pre-configured.
    Use this for tests that need to mock Redis behavior.
    """
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    # Set _client to None by default - tests that need _client behavior
    # should configure it explicitly
    mock_redis_client._client = None

    # Patch the shared singleton, initializer, and closer.
    with (
        patch("backend.core.redis._redis_client", mock_redis_client),
        patch("backend.core.redis.init_redis", return_value=mock_redis_client),
        patch("backend.core.redis.close_redis", return_value=None),
    ):
        yield mock_redis_client


@pytest.fixture
async def real_redis(
    worker_redis_url: str,
) -> AsyncGenerator[RedisClient]:
    """Provide a real Redis client connected to the worker's isolated Redis database.

    This fixture provides a real RedisClient instance for integration tests that
    need to test actual Redis behavior (e.g., queue operations, pub/sub, etc.).

    Each xdist worker uses a different Redis database number for isolation.

    Note: This fixture does NOT call flushdb() to allow parallel test execution.
    Tests should use unique key prefixes (via test_prefix fixture) and cleanup_keys
    fixture for proper isolation. This prevents one test's teardown from deleting
    another parallel test's keys.
    """
    from backend.core.redis import RedisClient

    # Use worker-specific Redis URL for parallel isolation
    client = RedisClient(redis_url=worker_redis_url)
    await client.connect()

    try:
        yield client
    finally:
        # Disconnect without flushing to avoid affecting parallel tests
        await client.disconnect()


async def _cleanup_test_data(max_retries: int = 3) -> None:
    """Delete all test data created by integration tests with retry logic.

    This helper function cleans up all tables in correct order (respecting
    foreign key constraints) to prevent orphaned entries from accumulating
    in the database.

    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks.
    Implements retry logic with exponential backoff for transient failures.

    The table deletion order is automatically determined using SQLAlchemy's
    reflection API to inspect foreign key relationships, with a fallback to
    a hardcoded list if reflection fails.

    Args:
        max_retries: Maximum number of retry attempts (default 3)
    """
    from sqlalchemy import text

    from backend.core.database import get_engine, get_session

    for attempt in range(max_retries):
        try:
            engine = get_engine()
            if engine is None:
                return

            # Get tables in FK-safe deletion order (dependent tables first)
            deletion_order = get_table_deletion_order(engine)

            async with get_session() as session:
                # Delete all test-related data in FK-safe order
                # The order is automatically computed from foreign key relationships
                for tbl in deletion_order:
                    try:
                        # Use SAVEPOINT so failures don't abort the transaction
                        # This handles missing tables (not yet migrated) gracefully
                        await session.execute(text(f"SAVEPOINT sp_{tbl}"))  # nosemgrep
                        # Safe: tbl comes from SQLAlchemy inspector (trusted source), not user input
                        await session.execute(text(f"DELETE FROM {tbl}"))  # noqa: S608 nosemgrep
                        await session.execute(text(f"RELEASE SAVEPOINT sp_{tbl}"))  # nosemgrep
                    except Exception as e:
                        # Rollback to savepoint and continue - table may not exist yet
                        try:
                            await session.execute(
                                text(f"ROLLBACK TO SAVEPOINT sp_{tbl}")
                            )  # nosemgrep
                        except Exception as rb_err:
                            logger.debug(f"Savepoint rollback failed for {tbl}: {rb_err}")
                        logger.debug(f"Skipping table {tbl}: {e}")

                await session.commit()
            # Success - exit retry loop
            return

        except Exception as e:
            if attempt < max_retries - 1:
                # Exponential backoff: 0.1s, 0.2s, 0.4s, ...
                delay = 0.1 * (2**attempt)
                logger.warning(
                    f"Database cleanup attempt {attempt + 1}/{max_retries} failed: {e}, "
                    f"retrying in {delay:.2f}s"
                )
                await asyncio.sleep(delay)
            else:
                # Final attempt failed - log warning but don't raise
                # Allow tests to continue even if cleanup fails
                logger.warning(
                    f"Database cleanup failed after {max_retries} attempts: {e}",
                    exc_info=True,
                )


# Keep the old name as an alias for backward compatibility
_cleanup_test_cameras = _cleanup_test_data


@pytest.fixture
async def client(integration_db: str, mock_redis: AsyncMock):
    """Async HTTP client bound to the FastAPI app (no network, no server startup).

    Notes:
    - The DB is pre-initialized by `integration_db`.
    - We patch app lifespan DB init/close to avoid double initialization.
    - We patch Redis init/close so lifespan does not connect.
    - All background services are mocked to avoid slow startup and cleanup issues.
    - Test data is cleaned up BEFORE and AFTER each test to ensure isolation
      and prevent data leakage between tests.

    Use this fixture for testing API endpoints.

    Database Isolation Strategy:
    - Pre-test cleanup: DELETE all test data to start fresh
    - Post-test cleanup: DELETE all test data to prevent leakage
    - This ensures tests can run repeatedly without data accumulation
    """
    # Clean up any existing test data BEFORE the test runs
    await _cleanup_test_data()
    from httpx import ASGITransport, AsyncClient

    # Import the app only after env is set up.
    from backend.main import app

    # Mock all background services to avoid slow startup/cleanup
    mock_system_broadcaster = MagicMock()
    mock_system_broadcaster.start_broadcasting = AsyncMock()
    mock_system_broadcaster.stop_broadcasting = AsyncMock()

    mock_gpu_monitor = MagicMock()
    mock_gpu_monitor.start = AsyncMock()
    mock_gpu_monitor.stop = AsyncMock()

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.start = AsyncMock()
    mock_cleanup_service.stop = AsyncMock()
    mock_cleanup_service.running = False
    mock_cleanup_service.get_cleanup_stats.return_value = {
        "running": False,
        "retention_days": 30,
        "cleanup_time": "03:00",
        "delete_images": False,
        "next_cleanup": None,
    }

    mock_file_watcher = MagicMock()
    mock_file_watcher.start = AsyncMock()
    mock_file_watcher.stop = AsyncMock()
    mock_file_watcher.configure_mock(
        running=False,
        camera_root="/mock/foscam",
        _use_polling=False,
        _pending_tasks={},
    )

    mock_file_watcher_class = MagicMock(return_value=mock_file_watcher)

    mock_file_watcher_for_routes = MagicMock()
    mock_file_watcher_for_routes.configure_mock(
        running=False,
        camera_root="/mock/foscam",
        _use_polling=False,
        _pending_tasks={},
    )

    mock_pipeline_manager = MagicMock()
    mock_pipeline_manager.start = AsyncMock()
    mock_pipeline_manager.stop = AsyncMock()

    mock_event_broadcaster = MagicMock()
    mock_event_broadcaster.start = AsyncMock()
    mock_event_broadcaster.stop = AsyncMock()
    mock_event_broadcaster.channel_name = "security_events"

    mock_service_health_monitor = MagicMock()
    mock_service_health_monitor.start = AsyncMock()
    mock_service_health_monitor.stop = AsyncMock()

    with (
        patch("backend.main.init_db", AsyncMock(return_value=None)),
        patch("backend.main.close_db", AsyncMock(return_value=None)),
        patch("backend.main.init_redis", AsyncMock(return_value=mock_redis)),
        patch("backend.main.close_redis", AsyncMock(return_value=None)),
        patch("backend.main.get_system_broadcaster", return_value=mock_system_broadcaster),
        patch("backend.main.GPUMonitor", return_value=mock_gpu_monitor),
        patch("backend.main.CleanupService", return_value=mock_cleanup_service),
        patch("backend.main.FileWatcher", mock_file_watcher_class),
        patch("backend.main.get_pipeline_manager", AsyncMock(return_value=mock_pipeline_manager)),
        patch("backend.main.stop_pipeline_manager", AsyncMock()),
        patch("backend.main.get_broadcaster", AsyncMock(return_value=mock_event_broadcaster)),
        patch("backend.main.stop_broadcaster", AsyncMock()),
        patch("backend.main.ServiceHealthMonitor", return_value=mock_service_health_monitor),
        patch("backend.api.routes.system._file_watcher", mock_file_watcher_for_routes),
        patch("backend.api.routes.system._cleanup_service", mock_cleanup_service),
    ):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                yield ac
        finally:
            # Clean up test data AFTER the test (even on failure)
            # This ensures no data leakage between tests
            # Use timeout protection to prevent hanging on cleanup
            try:
                await asyncio.wait_for(_cleanup_test_data(), timeout=10.0)
            except TimeoutError:
                logger.warning("Client fixture cleanup timed out after 10s, continuing anyway")


# =============================================================================
# Utility Functions (re-exported from root conftest)
# =============================================================================


def unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts.

    Re-exported from backend.tests.conftest for convenience.

    Args:
        prefix: Optional prefix for the ID (default: "test")

    Returns:
        A unique string ID like "test_abc12345"
    """
    import uuid

    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _unique_prefix() -> str:
    """Generate a unique prefix for Redis keys to prevent collisions across parallel tests."""
    import uuid

    return f"test:{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def test_prefix() -> str:
    """Generate a unique prefix for this test to avoid key collisions in Redis.

    This fixture is used by tests that interact with Redis to ensure that
    parallel test execution doesn't cause key collisions. Each test gets
    a unique prefix like "test:abc12345".
    """
    return _unique_prefix()


@pytest.fixture
async def cleanup_keys(real_redis: RedisClient, test_prefix: str):
    """Clean up test keys after test completion.

    This fixture ensures that Redis keys created during a test are cleaned up
    after the test completes, preventing key accumulation and ensuring isolation.
    """
    yield

    # Cleanup after test - delete all keys with this test's prefix
    try:
        keys = []
        async for key in real_redis._client.scan_iter(match=f"{test_prefix}:*"):
            keys.append(key)

        if keys:
            await real_redis._client.delete(*keys)
            logger.debug(f"Cleaned up {len(keys)} Redis keys with prefix {test_prefix}")
    except Exception as e:
        logger.warning(f"Failed to clean up Redis keys: {e}")
