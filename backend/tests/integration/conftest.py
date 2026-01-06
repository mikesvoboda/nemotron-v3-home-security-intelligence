"""Integration test fixtures with module-scoped testcontainers.

This module provides integration-specific fixtures with fully isolated containers
per test module. This eliminates race conditions that occur when tests share a
PostgreSQL container and need to coordinate schema creation.

Key fixtures:
- postgres_container: Module-scoped PostgreSQL container (or local service)
- redis_container: Module-scoped Redis container (or local service)
- integration_db: Initialize database with fresh schema per module
- db_session: Per-test database session
- client: HTTP client for API testing
- mock_redis: Mock Redis client for tests that don't need real Redis
- real_redis: Real Redis client for tests that need real Redis behavior

In development environments (with local Podman containers), the fixtures
use the local services for faster test execution. In CI/headless environments,
testcontainers are used for full isolation.
"""

from __future__ import annotations

import logging
import os
import socket
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import inspect

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
    # Second: Delete tables without FK references (standalone)
    "alert_rules",
    "audit_logs",
    "gpu_stats",
    "logs",
    "api_keys",
    "zones",
    "prompt_configs",
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


# =============================================================================
# Service Detection
# =============================================================================

# Default development PostgreSQL URL (matches docker-compose.yml)
DEFAULT_DEV_POSTGRES_URL = "postgresql+asyncpg://security:security_dev_password@localhost:5432/security"  # pragma: allowlist secret

# Default development Redis URL (matches docker-compose.yml, using DB 15 for test isolation)
DEFAULT_DEV_REDIS_URL = "redis://localhost:6379/15"


def _check_tcp_connection(host: str, port: int) -> bool:
    """Check if a TCP service is reachable on the given host/port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def _check_local_postgres() -> bool:
    """Check if local PostgreSQL is running on port 5432."""
    return _check_tcp_connection("localhost", 5432)


def _check_local_redis() -> bool:
    """Check if local Redis is running on port 6379."""
    return _check_tcp_connection("localhost", 6379)


# =============================================================================
# Deterministic Readiness Checks (polling-based)
# =============================================================================


def wait_for_postgres_container(container: PostgresContainer, timeout: float = 30.0) -> None:
    """Wait for PostgreSQL container to be ready using polling.

    Args:
        container: PostgresContainer instance
        timeout: Maximum time to wait in seconds

    Raises:
        TimeoutError: If PostgreSQL is not ready within timeout
    """
    import psycopg2

    start = time.monotonic()
    host = container.get_container_host_ip()
    port = int(container.get_exposed_port(5432))

    while time.monotonic() - start < timeout:
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user="postgres",
                password="postgres",  # noqa: S106  # pragma: allowlist secret
                dbname="security_test",
                connect_timeout=1,
            )
            conn.close()
            return
        except Exception:
            time.sleep(0.1)  # Brief poll interval

    raise TimeoutError(f"PostgreSQL not ready after {timeout} seconds")


def wait_for_redis_container(container: RedisContainer, timeout: float = 30.0) -> None:
    """Wait for Redis container to be ready using polling.

    Args:
        container: RedisContainer instance
        timeout: Maximum time to wait in seconds

    Raises:
        TimeoutError: If Redis is not ready within timeout
    """
    import redis

    start = time.monotonic()
    host = container.get_container_host_ip()
    port = int(container.get_exposed_port(6379))

    while time.monotonic() - start < timeout:
        try:
            client = redis.Redis(host=host, port=port, socket_timeout=1)
            client.ping()
            client.close()
            return
        except Exception:
            time.sleep(0.1)  # Brief poll interval

    raise TimeoutError(f"Redis not ready after {timeout} seconds")


# =============================================================================
# Module-Scoped Service Fixtures
# =============================================================================


# Wrapper class for local services to provide consistent interface
class LocalPostgresService:
    """Wrapper for local PostgreSQL service to mimic testcontainer interface."""

    def get_container_host_ip(self) -> str:
        return "localhost"

    def get_exposed_port(self, port: int) -> int:
        return 5432

    def get_connection_url(self) -> str:
        return DEFAULT_DEV_POSTGRES_URL


class LocalRedisService:
    """Wrapper for local Redis service to mimic testcontainer interface."""

    def get_container_host_ip(self) -> str:
        return "localhost"

    def get_exposed_port(self, port: int) -> int:
        return 6379


@pytest.fixture(scope="module")
def postgres_container() -> Generator[PostgresContainer | LocalPostgresService]:
    """Provide a module-scoped PostgreSQL service.

    Uses local PostgreSQL if available (development with Podman),
    otherwise starts a testcontainer for full isolation.
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
        password="postgres",  # noqa: S106  # pragma: allowlist secret
        dbname="security_test",
        driver="asyncpg",
    )
    container.start()

    try:
        wait_for_postgres_container(container)
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="module")
def redis_container() -> Generator[RedisContainer | LocalRedisService]:
    """Provide a module-scoped Redis service.

    Uses local Redis if available (development with Podman),
    otherwise starts a testcontainer for full isolation.
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


# =============================================================================
# Environment and Database Fixtures
# =============================================================================


@pytest.fixture
def integration_env(
    postgres_container: PostgresContainer | LocalPostgresService,
    redis_container: RedisContainer | LocalRedisService,
) -> Generator[str]:
    """Set DATABASE_URL/REDIS_URL for integration tests.

    This fixture sets environment variables pointing to the PostgreSQL
    and Redis services (either local or testcontainer).
    """
    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")
    original_redis_url = os.environ.get("REDIS_URL")
    original_runtime_env_path = os.environ.get("HSI_RUNTIME_ENV_PATH")

    # Create temporary directory for runtime env
    tmpdir = tempfile.mkdtemp()
    runtime_env_path = str(Path(tmpdir) / "runtime.env")

    # Get URLs from containers
    test_db_url = _get_postgres_url(postgres_container)
    test_redis_url = _get_redis_url(redis_container)

    os.environ["DATABASE_URL"] = test_db_url
    os.environ["REDIS_URL"] = test_redis_url
    os.environ["HSI_RUNTIME_ENV_PATH"] = runtime_env_path

    get_settings.cache_clear()

    try:
        yield test_db_url
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
    """
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

    # Create all tables (no advisory lock needed)
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(ModelsBase.metadata.create_all)
        # Add unique indexes for cameras table (migration adds these for production)
        # First, clean up any duplicate cameras that might prevent index creation
        from sqlalchemy import text

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
async def db_session(integration_db: str) -> AsyncGenerator[None]:
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
async def isolated_db_session(integration_db: str) -> AsyncGenerator[None]:
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

    # Patch the shared singleton, initializer, and closer.
    with (
        patch("backend.core.redis._redis_client", mock_redis_client),
        patch("backend.core.redis.init_redis", return_value=mock_redis_client),
        patch("backend.core.redis.close_redis", return_value=None),
    ):
        yield mock_redis_client


@pytest.fixture
async def real_redis(
    redis_container: RedisContainer | LocalRedisService,
) -> AsyncGenerator[RedisClient]:
    """Provide a real Redis client connected to the module-scoped container.

    This fixture provides a real RedisClient instance for integration tests that
    need to test actual Redis behavior (e.g., queue operations, pub/sub, etc.).
    """
    from backend.core.redis import RedisClient

    # Get Redis URL from container
    redis_url = _get_redis_url(redis_container)

    # Create and connect the client
    client = RedisClient(redis_url=redis_url)
    await client.connect()

    try:
        # Flush the test database for isolation
        redis_client = client._ensure_connected()
        await redis_client.flushdb()

        yield client
    finally:
        # Ensure clean state before disconnecting
        try:
            redis_client = client._ensure_connected()
            await redis_client.flushdb()
        except Exception as e:
            logger.warning(
                f"Redis cleanup failed: {e}",
                exc_info=True,
            )
            # Continue to allow tests to run even if cleanup fails
        await client.disconnect()


async def _cleanup_test_data() -> None:
    """Delete all test data created by integration tests.

    This helper function cleans up all tables in correct order (respecting
    foreign key constraints) to prevent orphaned entries from accumulating
    in the database.

    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks.

    The table deletion order is automatically determined using SQLAlchemy's
    reflection API to inspect foreign key relationships, with a fallback to
    a hardcoded list if reflection fails.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine, get_session

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
                        await session.execute(text(f"ROLLBACK TO SAVEPOINT sp_{tbl}"))  # nosemgrep
                    except Exception as rb_err:
                        logger.debug(f"Savepoint rollback failed for {tbl}: {rb_err}")
                    logger.debug(f"Skipping table {tbl}: {e}")

            await session.commit()
    except Exception as e:
        logger.warning(
            f"Database cleanup failed: {e}",
            exc_info=True,
        )
        # Continue to allow tests to run even if cleanup fails


# Keep the old name as an alias for backward compatibility
_cleanup_test_cameras = _cleanup_test_data


@pytest.fixture
async def client(integration_db: str, mock_redis: AsyncMock) -> AsyncGenerator[None]:
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
            await _cleanup_test_data()


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
