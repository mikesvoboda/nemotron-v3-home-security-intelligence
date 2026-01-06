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

import logging
import os
import socket
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import xdist

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
DEFAULT_DEV_POSTGRES_URL = (
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security"
)

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
                password="postgres",  # noqa: S106 - test password
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
        password="postgres",  # noqa: S106 - test password
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
    """
    from sqlalchemy import text

    from backend.core.database import get_session

    async def delete_all() -> None:
        async with get_session() as session:
            # Delete data in order (respecting foreign key constraints)
            await session.execute(text("DELETE FROM detections"))
            await session.execute(text("DELETE FROM events"))
            await session.execute(text("DELETE FROM gpu_stats"))
            await session.execute(text("DELETE FROM cameras"))
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
    worker_redis_url: str,
) -> AsyncGenerator[RedisClient]:
    """Provide a real Redis client connected to the worker's isolated Redis database.

    This fixture provides a real RedisClient instance for integration tests that
    need to test actual Redis behavior (e.g., queue operations, pub/sub, etc.).

    Each xdist worker uses a different Redis database number for isolation.
    """
    from backend.core.redis import RedisClient

    # Use worker-specific Redis URL for parallel isolation
    client = RedisClient(redis_url=worker_redis_url)
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
        except Exception:  # noqa: S110
            pass  # Ignore errors during cleanup
        await client.disconnect()


async def _cleanup_test_data() -> None:
    """Delete all test data created by integration tests.

    This helper function cleans up all tables in correct order (respecting
    foreign key constraints) to prevent orphaned entries from accumulating
    in the database.

    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine, get_session

    try:
        engine = get_engine()
        if engine is None:
            return

        async with get_session() as session:
            # Delete all test-related data in correct order (respecting FK constraints)
            # Tables with foreign keys must be deleted before their parent tables
            # Order: leaf tables first, parent tables last
            #
            # Dependency tree:
            # - alerts -> alert_rules, events
            # - audit_logs -> (standalone)
            # - activity_baselines -> cameras
            # - class_baselines -> cameras
            # - detections -> cameras, events
            # - events -> cameras
            # - event_audits -> events
            # - gpu_stats -> (standalone)
            # - logs -> (standalone)
            # - api_keys -> (standalone)
            # - zones -> (standalone)
            # - cameras -> (parent)

            # First: Delete tables with foreign key references
            await session.execute(text("DELETE FROM alerts"))
            await session.execute(text("DELETE FROM event_audits"))
            await session.execute(text("DELETE FROM detections"))
            await session.execute(text("DELETE FROM activity_baselines"))
            await session.execute(text("DELETE FROM class_baselines"))
            await session.execute(text("DELETE FROM events"))

            # Second: Delete tables without FK references (standalone)
            await session.execute(text("DELETE FROM alert_rules"))
            await session.execute(text("DELETE FROM audit_logs"))
            await session.execute(text("DELETE FROM gpu_stats"))
            await session.execute(text("DELETE FROM logs"))
            await session.execute(text("DELETE FROM api_keys"))
            await session.execute(text("DELETE FROM zones"))

            # Last: Delete parent tables
            await session.execute(text("DELETE FROM cameras"))

            await session.commit()
    except Exception:  # noqa: S110
        pass


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
