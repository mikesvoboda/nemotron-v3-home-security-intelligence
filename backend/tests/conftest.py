"""Pytest configuration and shared fixtures.

This module provides shared test fixtures for all backend tests.

FIXTURE HIERARCHY AND ORGANIZATION:
====================================

Root Fixtures (backend/tests/conftest.py - THIS FILE):
    Database Fixtures:
        - isolated_db: Function-scoped isolated database for unit tests (PostgreSQL)
        - test_db: Callable session factory for unit tests
        - session: Transaction-based isolation with savepoint rollback

    Mock Fixtures (Consolidated - NEM-3152):
        - mock_db_session: Comprehensive database session mock
        - mock_db_session_context: Async context manager wrapper for mock_db_session
        - mock_redis_client: Full-featured Redis client mock
        - mock_redis: Simplified Redis mock for basic operations
        - mock_http_client: HTTP client mock with all methods
        - mock_http_response: HTTP response mock
        - mock_detector_client: RT-DETR detector service mock
        - mock_nemotron_client: Nemotron LLM service mock
        - mock_baseline_service: Baseline service mock
        - mock_settings: Application settings mock

    Factory Fixtures:
        - camera_factory: Camera model factory
        - detection_factory: Detection model factory
        - event_factory: Event model factory
        - zone_factory: Zone model factory

    Utility Fixtures:
        - unique_id: Generate unique IDs for test data isolation
        - reset_settings_cache: Auto-reset settings between tests

Domain-Specific Fixtures (in subdirectories):
    Integration Tests (backend/tests/integration/conftest.py):
        - postgres_container, redis_container: Session-scoped test services
        - worker_db_url, worker_redis_url: Worker-isolated resources for pytest-xdist
        - integration_db, db_session, isolated_db_session: Integration test DB access
        - session: Override of root session for worker isolation
        - client: FastAPI test client with full app lifecycle

    Chaos Tests (backend/tests/chaos/conftest.py):
        - fault_injector: Core fault injection framework
        - rtdetr_*, redis_*, database_*, nemotron_*: Service-specific fault fixtures
        - high_latency, packet_loss: Network condition simulation
        - all_ai_services_down, cache_and_ai_down: Compound fault scenarios

    Contract Tests (backend/tests/contracts/conftest.py):
        - test_app: FastAPI app with mocked dependencies
        - async_client: HTTP client for contract testing
        - patch_database_dependency, patch_redis_dependency: Dependency injection patches
        NOTE: Uses mock_db_session and mock_redis_client from root conftest.py

    Security Tests (backend/tests/security/conftest.py):
        - security_client: Synchronous test client for security testing

    Unit Tests (backend/tests/unit/conftest.py):
        - mock_transformers_for_speed: Speed optimization for transformers import

    Unit Model Tests (backend/tests/unit/models/conftest.py):
        - _soft_delete_serial_lock: Cross-process lock for soft delete tests

CONSOLIDATION (NEM-3152):
==========================
Mock fixtures have been consolidated in this root conftest.py to eliminate duplication.
Previously, mock_db_session and mock_redis_client were duplicated in:
- backend/tests/conftest.py (comprehensive versions)
- backend/tests/contracts/conftest.py (basic versions - REMOVED)

Shared utility functions have been extracted to backend/tests/test_utils.py:
- check_tcp_connection
- wait_for_postgres_container
- wait_for_redis_container
- get_table_deletion_order

ENVIRONMENT CONFIGURATION:
==========================
Tests use PostgreSQL and Redis via testcontainers or local instances.
Configure TEST_DATABASE_URL/TEST_REDIS_URL environment variables for overrides.

Hypothesis Configuration:
- default: 100 examples, reasonable timeouts for local development
- ci: 200 examples, extended deadline for slower CI environments
- fast: 10 examples for quick smoke tests during development
- debug: 10 examples with verbose output for debugging failures

Flaky Test Detection:
- Tests marked with @pytest.mark.flaky are quarantined (failures don't fail CI)
- Test outcomes are tracked in FLAKY_TEST_RESULTS_FILE for analysis
- Use pytest-rerunfailures with --reruns flag for automatic retry

See backend/tests/AGENTS.md for full documentation on test conventions.
"""

from __future__ import annotations

# CRITICAL: Set ENVIRONMENT before any imports that might instantiate Settings.
# The password validation in config.py rejects weak passwords in production/staging.
# Tests use weak passwords by design, so we must run in development/test mode.
import os as _os

_os.environ.setdefault("ENVIRONMENT", "test")

import logging
import os
import socket
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import HealthCheck, Phase, Verbosity
from hypothesis import settings as hypothesis_settings

# NEM-1061: Logger for test cleanup handlers
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator


# Add backend to path for imports
backend_path = Path(__file__).parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# =============================================================================
# Hypothesis Settings Profiles
# =============================================================================
# Configure different profiles for various testing scenarios.
# Use with: pytest --hypothesis-profile=ci

# Default profile for local development
hypothesis_settings.register_profile(
    "default",
    max_examples=100,
    deadline=1000,  # 1 second per example
    suppress_health_check=[HealthCheck.too_slow],
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.shrink],
)

# CI profile with more examples and extended deadline
hypothesis_settings.register_profile(
    "ci",
    max_examples=200,
    deadline=5000,  # 5 seconds per example (CI is slower)
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.shrink],
    derandomize=False,  # Keep randomization for better coverage
)

# Fast profile for quick smoke tests during development
hypothesis_settings.register_profile(
    "fast",
    max_examples=10,
    deadline=500,  # 500ms per example
    suppress_health_check=[HealthCheck.too_slow],
    phases=[Phase.explicit, Phase.generate],  # Skip shrinking for speed
)

# Debug profile for investigating failures
hypothesis_settings.register_profile(
    "debug",
    max_examples=10,
    deadline=None,  # No deadline when debugging
    verbosity=Verbosity.verbose,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.shrink],
    report_multiple_bugs=True,
)

# Load profile from environment or use default
_hypothesis_profile = os.environ.get("HYPOTHESIS_PROFILE", "default")
hypothesis_settings.load_profile(_hypothesis_profile)


# =============================================================================
# Flaky Test Detection and Quarantine System
# =============================================================================
# Tracks test outcomes for flakiness analysis and handles quarantined tests.
# Results are written to a JSON file for aggregation across CI runs.

# File to store flaky test tracking data (set via FLAKY_TEST_RESULTS_FILE env var)
FLAKY_TEST_RESULTS_FILE = os.environ.get("FLAKY_TEST_RESULTS_FILE", "")

# Track test outcomes during this run (nodeid -> list of outcomes)
# Outcome format: {"outcome": "passed"|"failed"|"skipped", "rerun": bool, "duration": float}
_test_outcomes: dict[str, list[dict]] = {}


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest before test collection.

    Sets environment variables needed before any test modules are imported.
    """
    # Force pure-Python protobuf implementation for Python 3.14+ compatibility.
    # The C++ extension fails with "Metaclasses with custom tp_new are not supported."
    # See: https://bugzilla.redhat.com/show_bug.cgi?id=2356165
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

    # Set default DATABASE_URL for test collection (required by pydantic Settings)
    # This is needed because some modules import settings at module level
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
    )

    # Register custom markers to prevent warnings
    config.addinivalue_line(
        "markers",
        "flaky: mark test as flaky (known to fail intermittently, quarantined)",
    )
    config.addinivalue_line(
        "markers",
        "chaos: mark test as chaos engineering test (fault injection)",
    )


# Default development PostgreSQL URL (matches docker-compose.yml)
DEFAULT_DEV_POSTGRES_URL = "postgresql+asyncpg://security:security_dev_password@localhost:5432/security"  # pragma: allowlist secret

# Default development Redis URL (matches docker-compose.yml, using DB 15 for test isolation)
DEFAULT_DEV_REDIS_URL = "redis://localhost:6379/15"


def _check_tcp_connection(host: str = "localhost", port: int = 5432) -> bool:
    """Check if a TCP service is reachable on the given host/port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        # NEM-1061: Log suppressed exception for debugging
        logger.debug(
            "TCP connection check failed",
            extra={"host": host, "port": port, "error": str(e)},
        )
        return False


def _check_postgres_connection(host: str = "localhost", port: int = 5432) -> bool:
    """Check if PostgreSQL is reachable on the given host/port."""
    return _check_tcp_connection(host, port)


def _check_redis_connection(host: str = "localhost", port: int = 6379) -> bool:
    """Check if Redis is reachable on the given host/port."""
    return _check_tcp_connection(host, port)


def _apply_timeout_marker(item: pytest.Item, fspath_str: str) -> None:
    """Apply appropriate timeout marker to a test item.

    Helper function extracted from pytest_collection_modifyitems to reduce
    branch complexity in the main hook.

    Timeout hierarchy:
    1. Explicit @pytest.mark.timeout(N) on test - unchanged
    2. @pytest.mark.slow marker - 30 seconds
    3. Integration tests (in integration/ directory) - 5 seconds
    4. Default from pyproject.toml - 1 second (no marker needed)
    """
    # Skip if test has explicit timeout marker
    if item.get_closest_marker("timeout"):
        return

    # Slow-marked tests get 30s
    if item.get_closest_marker("slow"):
        item.add_marker(pytest.mark.timeout(30))
        return

    # Integration tests get 5s
    if "/integration/" in fspath_str:
        item.add_marker(pytest.mark.timeout(5))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-apply markers and timeouts based on test location in a single pass.

    This hook consolidates ALL marker application logic to avoid multiple iterations
    over the test items list. Previously, separate conftest.py files at different
    levels each iterated over all items, resulting in O(4n) complexity. This
    consolidated approach achieves O(n) complexity.

    Marker application (in order of checks):
    1. Unit tests (/unit/ directory):
       - Applies 'unit' marker
       - Skips tests marked with 'integration' (they require a real database)
    2. Integration tests (/integration/ directory):
       - Applies 'integration' marker
       - Repository tests (/integration/repositories/) get xdist_group + serial markers
    3. Soft delete tests (test_soft_delete.py in /unit/models/):
       - Gets xdist_group marker to force serial execution (prevents DB deadlocks)

    Timeout hierarchy (highest priority first):
    1. CLI --timeout=0 disables all timeouts (for CI)
    2. Explicit @pytest.mark.timeout(N) on test - unchanged
    3. @pytest.mark.slow marker - 30 seconds
    4. Integration tests (in integration/ directory) - 5 seconds
    5. Default from pyproject.toml - 1 second
    """
    # Check if timeouts are disabled via CLI (--timeout=0)
    # This is used in CI where environment is slower
    cli_timeout = config.getoption("timeout", default=None)
    timeouts_disabled = cli_timeout == 0

    # Pre-create markers to avoid repeated marker creation in loop
    skip_integration = pytest.mark.skip(
        reason="Integration test requires database - skipped in unit test run"
    )
    xdist_soft_delete = pytest.mark.xdist_group(name="soft_delete_serial")
    xdist_repository = pytest.mark.xdist_group(name="repository_tests_serial")
    serial_marker = pytest.mark.serial

    for item in items:
        fspath_str = str(item.fspath)
        nodeid = item.nodeid
        is_unit = "/unit/" in fspath_str
        is_integration = "/integration/" in fspath_str

        # === UNIT TEST HANDLING ===
        if is_unit:
            # Apply unit marker
            if not item.get_closest_marker("unit"):
                item.add_marker(pytest.mark.unit)

            # Skip integration-marked tests in unit runs
            # (They require a real database connection)
            if "integration" in item.keywords:
                item.add_marker(skip_integration)

            # Soft delete tests need xdist_group for serial execution
            # to avoid database deadlocks when modifying schema
            if "test_soft_delete.py" in nodeid and not item.get_closest_marker("xdist_group"):
                item.add_marker(xdist_soft_delete)

        # === INTEGRATION TEST HANDLING ===
        elif is_integration:
            # Apply integration marker
            if not item.get_closest_marker("integration"):
                item.add_marker(pytest.mark.integration)

            # Repository tests need serial execution due to shared database state
            if "/repositories/" in fspath_str:
                if not item.get_closest_marker("xdist_group"):
                    item.add_marker(xdist_repository)
                if not item.get_closest_marker("serial"):
                    item.add_marker(serial_marker)

        # === TIMEOUT HANDLING ===
        if not timeouts_disabled:
            _apply_timeout_marker(item, fspath_str)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Generator[None]:
    """Track test outcomes for flakiness analysis.

    This hook captures test outcomes (pass/fail/skip) and tracks reruns
    for tests using pytest-rerunfailures. Results are aggregated for
    flakiness scoring.

    Flaky tests (marked with @pytest.mark.flaky) have their failures
    recorded but don't fail CI - they are quarantined.
    """
    outcome = yield
    report = outcome.get_result()

    # Only track call phase (not setup/teardown)
    if call.when != "call":
        return

    nodeid = item.nodeid
    is_flaky = item.get_closest_marker("flaky") is not None

    # Detect if this is a rerun from pytest-rerunfailures
    is_rerun = hasattr(item, "execution_count") and item.execution_count > 1

    # Build outcome record
    outcome_record = {
        "outcome": report.outcome,
        "duration": report.duration,
        "rerun": is_rerun,
        "flaky_marked": is_flaky,
    }

    # Track this outcome
    if nodeid not in _test_outcomes:
        _test_outcomes[nodeid] = []
    _test_outcomes[nodeid].append(outcome_record)

    # For flaky-marked tests, convert failures to xfail (expected failure)
    # This makes them non-blocking in CI while still reporting them
    if is_flaky and report.outcome == "failed":
        # Log the quarantined failure
        logger.info(
            "Quarantined flaky test failure",
            extra={
                "test": nodeid,
                "duration": report.duration,
                "is_rerun": is_rerun,
            },
        )
        # Mark as xfail (expected failure) - doesn't fail CI
        report.outcome = "skipped"
        report.wasxfail = "Quarantined flaky test"


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Write flaky test tracking data at end of test session.

    Outputs a JSON file with test outcomes for aggregation across CI runs.
    This data is used by scripts/analyze-flaky-tests.py to detect flaky tests.
    """
    import json
    from datetime import UTC, datetime

    if not FLAKY_TEST_RESULTS_FILE:
        return

    # Build results summary
    results = {
        "timestamp": datetime.now(UTC).isoformat(),
        "exit_status": exitstatus,
        "tests": {},
    }

    for nodeid, outcomes in _test_outcomes.items():
        # Calculate pass rate
        total = len(outcomes)
        passed = sum(1 for o in outcomes if o["outcome"] == "passed")
        failed = sum(1 for o in outcomes if o["outcome"] == "failed")
        reruns = sum(1 for o in outcomes if o.get("rerun", False))

        results["tests"][nodeid] = {
            "outcomes": outcomes,
            "total_runs": total,
            "passed": passed,
            "failed": failed,
            "reruns": reruns,
            "pass_rate": passed / total if total > 0 else 0,
            "flaky_marked": any(o.get("flaky_marked", False) for o in outcomes),
        }

    # Write results file (append-friendly JSON lines format)
    try:
        results_path = Path(FLAKY_TEST_RESULTS_FILE)
        results_path.parent.mkdir(parents=True, exist_ok=True)
        with results_path.open("a") as f:
            f.write(json.dumps(results) + "\n")
        logger.info(
            "Wrote flaky test tracking data",
            extra={"file": str(results_path), "test_count": len(results["tests"])},
        )
    except Exception as e:
        logger.warning(
            "Failed to write flaky test tracking data",
            extra={"error": str(e), "file": FLAKY_TEST_RESULTS_FILE},
        )


def get_test_db_url() -> str:
    """Get the PostgreSQL test database URL for unit tests.

    Priority order:
    1. TEST_DATABASE_URL environment variable (explicit override)
    2. Local PostgreSQL on port 5432 (development with Podman/Docker)

    For integration tests, use the module-scoped containers in
    backend/tests/integration/conftest.py instead.

    Returns:
        str: PostgreSQL connection URL with asyncpg driver

    Raises:
        RuntimeError: If no PostgreSQL instance is available
    """
    # 1. Check for explicit environment variable override (CI sets both)
    env_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if env_url:
        # Ensure asyncpg driver
        if "postgresql://" in env_url and "asyncpg" not in env_url:
            env_url = env_url.replace("postgresql://", "postgresql+asyncpg://")
        return env_url

    # 2. Check for local PostgreSQL (development environment with Podman/Docker)
    if _check_postgres_connection():
        return DEFAULT_DEV_POSTGRES_URL

    raise RuntimeError(
        "PostgreSQL not available for unit testing. Options:\n"
        "1. Start PostgreSQL via 'podman-compose up -d postgres' (development)\n"
        "2. Set TEST_DATABASE_URL environment variable\n"
        "Note: Integration tests use module-scoped testcontainers."
    )


def get_test_redis_url() -> str:
    """Get the Redis test URL for unit tests.

    Priority order:
    1. TEST_REDIS_URL environment variable (explicit override)
    2. Local Redis on port 6379 (development with Podman/Docker)

    For integration tests, use the module-scoped containers in
    backend/tests/integration/conftest.py instead.

    Returns:
        str: Redis connection URL with database 15 for test isolation

    Raises:
        RuntimeError: If no Redis instance is available
    """
    # 1. Check for explicit environment variable override
    env_url = os.environ.get("TEST_REDIS_URL")
    if env_url:
        return env_url

    # 2. Check for local Redis (development environment with Podman/Docker)
    if _check_redis_connection():
        return DEFAULT_DEV_REDIS_URL

    raise RuntimeError(
        "Redis not available for unit testing. Options:\n"
        "1. Start Redis via 'podman-compose up -d redis' (development)\n"
        "2. Set TEST_REDIS_URL environment variable\n"
        "Note: Integration tests use module-scoped testcontainers."
    )


# Track if schema has been reset this worker process to avoid redundant operations
_schema_reset_done: bool = False


async def _ensure_clean_db() -> None:
    """Ensure database has tables and is ready for tests.

    This function creates tables if they don't exist.

    Test isolation is achieved through:
    1. Savepoint/rollback in the session fixture (transaction isolation)
    2. Using unique_id() for test data (prevents cross-test conflicts)

    Note: Integration tests use module-scoped containers which provide
    full isolation without needing advisory locks.
    """
    await _reset_db_schema()


async def _reset_db_schema() -> None:
    """Create all tables and add any missing columns to match current models.

    This is called once per database to ensure the database schema matches
    the current SQLAlchemy models. Uses create_all for new tables and
    explicit ALTER TABLE for missing columns.

    Uses a PostgreSQL advisory lock to prevent deadlocks when multiple pytest-xdist
    workers attempt to modify schema concurrently. The lock key is different from
    the one used in init_db to avoid conflicts.
    """
    global _schema_reset_done  # noqa: PLW0603

    if _schema_reset_done:
        return

    import hashlib

    from sqlalchemy import text

    from backend.core.database import get_engine

    # Import all models to ensure they're registered with Base.metadata
    from backend.models import Camera, Detection, Event, GPUStats, JobTransition  # noqa: F401
    from backend.models.camera import Base as ModelsBase
    from backend.models.event_feedback import EventFeedback  # noqa: F401
    from backend.models.user_calibration import UserCalibration  # noqa: F401

    engine = get_engine()
    if engine is None:
        return

    # Mark as done FIRST to prevent re-entry from concurrent coroutines
    _schema_reset_done = True

    # Advisory lock key for test schema reset (different from init_db lock key)
    # This prevents concurrent DDL operations that could cause deadlocks
    _TEST_SCHEMA_LOCK_NAMESPACE = "home_security_intelligence.test_schema_reset"
    _TEST_SCHEMA_LOCK_KEY = int(
        hashlib.sha256(_TEST_SCHEMA_LOCK_NAMESPACE.encode()).hexdigest()[:15], 16
    )

    async with engine.begin() as conn:
        # Acquire advisory lock to serialize DDL operations across pytest-xdist workers
        # Using pg_advisory_lock (blocking) to ensure all workers wait rather than skip
        lock_sql = text(f"SELECT pg_advisory_lock({_TEST_SCHEMA_LOCK_KEY})")  # nosemgrep
        await conn.execute(lock_sql)

        try:
            # Create tables if they don't exist
            await conn.run_sync(ModelsBase.metadata.create_all)

            # Add any missing columns that create_all doesn't handle
            # This handles schema drift without dropping data
            # Using IF NOT EXISTS makes this idempotent and safe to run in parallel
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
            # NEM-2363: Add snooze_until column for event snoozing
            await conn.execute(
                text(
                    "ALTER TABLE events ADD COLUMN IF NOT EXISTS snooze_until TIMESTAMP WITH TIME ZONE"
                )
            )
            # Add search_vector columns for full-text search
            await conn.execute(
                text("ALTER TABLE events ADD COLUMN IF NOT EXISTS search_vector TSVECTOR")
            )
            await conn.execute(
                text("ALTER TABLE detections ADD COLUMN IF NOT EXISTS search_vector TSVECTOR")
            )
            # Add labels column for detections
            await conn.execute(text("ALTER TABLE detections ADD COLUMN IF NOT EXISTS labels JSONB"))

            # NEM-2348: Add 4 feedback types columns for user_calibration
            await conn.execute(
                text(
                    "ALTER TABLE user_calibration ADD COLUMN IF NOT EXISTS correct_count INTEGER DEFAULT 0"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE user_calibration ADD COLUMN IF NOT EXISTS missed_threat_count INTEGER DEFAULT 0"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE user_calibration ADD COLUMN IF NOT EXISTS severity_wrong_count INTEGER DEFAULT 0"
                )
            )

            # NEM-2348: Add expected_severity column for event_feedback
            await conn.execute(
                text(
                    "ALTER TABLE event_feedback ADD COLUMN IF NOT EXISTS expected_severity VARCHAR"
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
            # Always release the advisory lock
            unlock_sql = text(f"SELECT pg_advisory_unlock({_TEST_SCHEMA_LOCK_KEY})")  # nosemgrep
            await conn.execute(unlock_sql)


def _get_table_deletion_order(metadata: object) -> list[str]:
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
    from collections import defaultdict

    # Build a dependency graph: table -> set of tables it references
    # A table "depends on" another if it has a FK pointing to it
    dependencies: dict[str, set[str]] = defaultdict(set)
    all_tables: set[str] = set()

    for table in metadata.tables.values():  # type: ignore[attr-defined]
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

    # Start with tables that have dependents but no dependencies (parent tables)
    # and tables with no relationships at all
    # We'll process in reverse order to get children first

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


async def _cleanup_test_cameras() -> None:
    """Delete all test camera data created by tests using isolated_db.

    This helper function cleans up all camera-related data in correct order
    (respecting foreign key constraints) to prevent orphaned entries from
    accumulating in the database.

    Uses automatic FK ordering based on SQLAlchemy metadata to determine
    the correct deletion order. Tables with foreign key references are
    deleted before the tables they reference.

    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine, get_session
    from backend.models.camera import Base as ModelsBase

    try:
        engine = get_engine()
        if engine is None:
            return

        # Get the correct deletion order from FK relationships
        deletion_order = _get_table_deletion_order(ModelsBase.metadata)

        async with get_session() as session:
            # Delete all test-related data in correct order (respecting FK constraints)
            # Order is automatically determined from foreign key relationships
            for table_name in deletion_order:
                # Safe: table_name comes from SQLAlchemy metadata, not user input
                await session.execute(text(f"DELETE FROM {table_name}"))  # noqa: S608 nosemgrep

            await session.commit()
    except Exception as e:
        # NEM-1061: Log suppressed exception for debugging
        logger.debug(
            "Test cleanup failed during table deletion",
            extra={"error": str(e), "error_type": type(e).__name__},
        )


@pytest.fixture(scope="function")
async def isolated_db() -> AsyncGenerator[None]:
    """Create an isolated test database for each test.

    This fixture:
    - Uses the shared PostgreSQL testcontainer or local PostgreSQL
    - Sets the DATABASE_URL environment variable
    - Clears the settings cache
    - Ensures tables exist (created once per worker, coordinated via advisory lock)
    - Yields control to the test
    - Cleans up test data and restores the original state

    Note: For true isolation in parallel tests, use the `session` fixture
    which provides transaction-based rollback isolation. Tests should use
    unique IDs (via unique_id() helper) to avoid conflicts with parallel tests.
    """
    from backend.core.config import get_settings
    from backend.core.database import close_db, init_db

    # Save original state
    original_db_url = os.environ.get("DATABASE_URL")

    # Clear the settings cache to force reload
    get_settings.cache_clear()

    # Get base PostgreSQL URL from testcontainer or local PostgreSQL
    test_db_url = get_test_db_url()

    # Set test database URL
    os.environ["DATABASE_URL"] = test_db_url

    # Clear cache again after setting env var
    get_settings.cache_clear()

    # Ensure database is closed before initializing
    await close_db()

    # Initialize database (creates engine and tables)
    await init_db()

    # Ensure schema exists and is ready for tests
    # This is coordinated across workers via advisory lock
    await _ensure_clean_db()

    yield

    # Clean up test data before closing database
    await _cleanup_test_cameras()

    # Close database connection
    await close_db()

    # Restore original state
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url
    else:
        os.environ.pop("DATABASE_URL", None)

    # Clear cache one more time to ensure clean state
    get_settings.cache_clear()


@pytest.fixture
async def session(isolated_db: None) -> AsyncGenerator[None]:
    """Create an isolated database session with transaction rollback for each test.

    This fixture provides true isolation in parallel test execution by:
    1. Starting a savepoint before each test
    2. Rolling back to the savepoint after each test

    All data created during the test is automatically rolled back, ensuring
    parallel tests don't see each other's data.

    Usage:
        @pytest.mark.asyncio
        async def test_something(session):
            camera = Camera(id="test", name="Test")
            session.add(camera)
            await session.flush()
            # Test assertions...
            # Data is automatically rolled back after test
    """
    from sqlalchemy import text

    from backend.core.database import get_session

    async with get_session() as sess:
        # Start a savepoint that we'll roll back to after the test
        # This ensures test isolation without needing TRUNCATE
        await sess.execute(text("SAVEPOINT test_savepoint"))

        try:
            yield sess
        finally:
            # Roll back to savepoint to undo all changes from this test
            await sess.execute(text("ROLLBACK TO SAVEPOINT test_savepoint"))


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Generator[None]:
    """Automatically reset settings cache and ensure required env vars before each test.

    This ensures:
    1. No global state leaks between tests
    2. Required environment variables (DATABASE_URL, REDIS_URL) have valid defaults
       so unit tests that instantiate classes calling get_settings() don't fail

    Note: We don't auto-close database here since some tests
    explicitly test the behavior when database is not initialized.
    """
    from backend.core.config import get_settings

    # Save original env vars to restore after test
    original_db_url = os.environ.get("DATABASE_URL")
    original_redis_url = os.environ.get("REDIS_URL")

    # Set default test values if not already set
    # This prevents Settings validation errors in unit tests that don't need a real DB
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = DEFAULT_DEV_POSTGRES_URL
    if not os.environ.get("REDIS_URL"):
        os.environ["REDIS_URL"] = DEFAULT_DEV_REDIS_URL

    # Clear settings cache before test
    get_settings.cache_clear()

    yield

    # Restore original env vars (or remove if they weren't set)
    if original_db_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = original_db_url

    if original_redis_url is None:
        os.environ.pop("REDIS_URL", None)
    else:
        os.environ["REDIS_URL"] = original_redis_url

    # Clear settings cache after test
    get_settings.cache_clear()


@pytest.fixture
async def test_db() -> AsyncGenerator[None]:
    """Create test database session factory for unit tests.

    This fixture provides a callable that returns a context manager for database sessions.
    It sets up a PostgreSQL test database with fresh schema and ensures cleanup.

    Usage:
        async with test_db() as session:
            # Use session for database operations
            ...
    """

    from backend.core.config import get_settings
    from backend.core.database import close_db, get_session, init_db

    # Save original state
    original_db_url = os.environ.get("DATABASE_URL")

    # Clear the settings cache to force reload
    get_settings.cache_clear()

    # Get PostgreSQL URL from testcontainer or local PostgreSQL
    test_db_url = get_test_db_url()

    # Set test database URL
    os.environ["DATABASE_URL"] = test_db_url

    # Clear cache again after setting env var
    get_settings.cache_clear()

    # Ensure database is closed before initializing
    await close_db()

    # Initialize database (creates engine)
    await init_db()

    # Reset schema to ensure it matches current models
    await _reset_db_schema()

    # Return the get_session function as a callable
    yield get_session

    # Clean up test data before closing database
    await _cleanup_test_cameras()

    # Close database connection
    await close_db()

    # Restore original state
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url
    else:
        os.environ.pop("DATABASE_URL", None)

    # Clear cache one more time to ensure clean state
    get_settings.cache_clear()


# =============================================================================
# Shared Utility Fixtures
# =============================================================================
# These fixtures are available to all tests (unit and integration).
# Integration tests use module-scoped fixtures from backend/tests/integration/conftest.py


@pytest.fixture
async def mock_redis() -> AsyncGenerator[AsyncMock]:
    """Mock Redis operations for tests that don't need real Redis.

    This fixture provides a mock Redis client with common operations pre-configured:
    - health_check: Returns healthy status

    The mock is patched into backend.core.redis module.

    Use this for unit tests that need to mock Redis behavior.
    Integration tests should use the mock_redis or real_redis fixtures
    from backend/tests/integration/conftest.py instead.
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


def unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts in parallel execution.

    Args:
        prefix: Optional prefix for the ID (default: "test")

    Returns:
        A unique string ID like "test_abc12345"
    """
    import uuid

    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# =============================================================================
# Consolidated Mock Fixtures (NEM-1448)
# =============================================================================
# These fixtures consolidate common mock patterns to reduce duplication across tests.
# See backend/tests/mock_utils.py for factory functions that can be used directly.


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session with all common operations configured.

    This fixture provides a mock AsyncSession with the following pre-configured:
    - add: MagicMock (synchronous)
    - commit: AsyncMock
    - refresh: AsyncMock
    - flush: AsyncMock
    - rollback: AsyncMock
    - execute: AsyncMock (returns empty result by default)
    - close: AsyncMock
    - delete: AsyncMock
    - get: AsyncMock (returns None by default)
    - scalar: AsyncMock (returns None by default)
    - scalars: MagicMock (returns empty list by default)
    - begin_nested: AsyncMock context manager

    Usage:
        @pytest.mark.asyncio
        async def test_something(mock_db_session):
            # Configure specific return values
            mock_db_session.execute.return_value.scalars.return_value.all.return_value = [camera]

            # Use in test
            service = MyService(session=mock_db_session)
            await service.do_something()

            # Verify interactions
            mock_db_session.commit.assert_called_once()
    """
    from unittest.mock import MagicMock

    session = AsyncMock()

    # Synchronous operations
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.expunge = MagicMock()
    session.expunge_all = MagicMock()

    # Async operations
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.delete = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.scalar = AsyncMock(return_value=None)
    session.execute = AsyncMock()

    # Configure execute to return a result object with common patterns
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_scalars.first.return_value = None
    mock_scalars.one_or_none.return_value = None
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one_or_none.return_value = None
    mock_result.first.return_value = None
    mock_result.all.return_value = []
    mock_result.fetchone.return_value = None
    mock_result.fetchall.return_value = []
    session.execute.return_value = mock_result

    # Configure begin_nested for savepoint support
    mock_nested = AsyncMock()
    mock_nested.__aenter__ = AsyncMock(return_value=mock_nested)
    mock_nested.__aexit__ = AsyncMock(return_value=None)
    session.begin_nested = MagicMock(return_value=mock_nested)

    return session


@pytest.fixture
def mock_db_session_context(mock_db_session: AsyncMock) -> AsyncMock:
    """Create a mock database context manager that yields mock_db_session.

    This fixture wraps mock_db_session in an async context manager for use
    with `async with get_session() as session:` patterns.

    Usage:
        @pytest.mark.asyncio
        async def test_something(mock_db_session, mock_db_session_context):
            with patch("backend.core.database.get_session", return_value=mock_db_session_context):
                # Code that uses async with get_session() as session:
                await my_function()
                mock_db_session.commit.assert_called()
    """
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    return mock_context


@pytest.fixture
def mock_http_response() -> MagicMock:
    """Create a mock HTTP response object with common attributes.

    Returns a MagicMock configured as httpx.Response with:
    - status_code: 200
    - json(): Returns empty dict
    - text: Empty string
    - content: Empty bytes
    - raise_for_status(): No-op by default

    Usage:
        def test_http_call(mock_http_response):
            mock_http_response.status_code = 200
            mock_http_response.json.return_value = {"status": "healthy"}

            with patch("httpx.AsyncClient.get", return_value=mock_http_response):
                result = await client.get("/health")
    """
    from unittest.mock import MagicMock

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {}
    response.text = ""
    response.content = b""
    response.headers = {}
    response.raise_for_status = MagicMock()
    response.is_success = True
    response.is_error = False
    return response


@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Create a mock httpx.AsyncClient with common HTTP methods.

    Returns an AsyncMock configured as httpx.AsyncClient with:
    - get: AsyncMock
    - post: AsyncMock
    - put: AsyncMock
    - delete: AsyncMock
    - patch: AsyncMock
    - Async context manager support (__aenter__/__aexit__)

    Usage:
        @pytest.mark.asyncio
        async def test_api_call(mock_http_client, mock_http_response):
            mock_http_response.json.return_value = {"detections": []}
            mock_http_client.post.return_value = mock_http_response

            with patch("httpx.AsyncClient", return_value=mock_http_client):
                result = await detector.detect(image_path)
                mock_http_client.post.assert_called_once()
    """
    client = AsyncMock()

    # Configure async context manager support
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    # All HTTP methods are already AsyncMock by default
    # but we ensure they're properly typed
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.delete = AsyncMock()
    client.patch = AsyncMock()
    client.head = AsyncMock()
    client.options = AsyncMock()

    # Common httpx.AsyncClient properties
    client.is_closed = False

    return client


@pytest.fixture
def mock_detector_client() -> AsyncMock:
    """Create a mock RT-DETR detector client.

    Returns an AsyncMock configured as DetectorClient with:
    - detect_objects: Returns empty list by default
    - health_check: Returns True
    - check_health: Returns {"status": "healthy"}

    Usage:
        @pytest.mark.asyncio
        async def test_detection(mock_detector_client, mock_db_session):
            mock_detector_client.detect_objects.return_value = [
                Detection(object_type="person", confidence=0.95, ...)
            ]

            with patch("backend.services.detector_client.DetectorClient", return_value=mock_detector_client):
                detections = await process_image(image_path, mock_db_session)
    """
    client = AsyncMock()
    client.detect_objects = AsyncMock(return_value=[])
    client.health_check = AsyncMock(return_value=True)
    client.check_health = AsyncMock(return_value={"status": "healthy"})
    client._validate_image_for_detection_async = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_nemotron_client() -> AsyncMock:
    """Create a mock Nemotron LLM client.

    Returns an AsyncMock configured as NemotronAnalyzer with:
    - analyze: Returns default risk assessment
    - health_check: Returns True
    - check_health: Returns {"status": "healthy"}

    Usage:
        @pytest.mark.asyncio
        async def test_risk_analysis(mock_nemotron_client):
            mock_nemotron_client.analyze.return_value = {
                "risk_score": 75,
                "risk_level": "high",
                "summary": "Person detected at entry point",
                "reasoning": "High risk due to proximity to entry",
            }

            with patch("backend.services.nemotron_analyzer.NemotronAnalyzer", return_value=mock_nemotron_client):
                result = await analyze_detections(detections)
    """
    client = AsyncMock()
    client.analyze = AsyncMock(
        return_value={
            "risk_score": 25,
            "risk_level": "low",
            "summary": "Normal activity detected",
            "reasoning": "No concerning patterns observed",
        }
    )
    client.health_check = AsyncMock(return_value=True)
    client.check_health = AsyncMock(return_value={"status": "healthy"})
    return client


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    """Create a comprehensive mock Redis client.

    Returns an AsyncMock configured with all common Redis operations:
    - get/set/delete: Basic key-value operations
    - publish: Pub/sub support
    - lpush/rpush/lpop/rpop: List operations
    - sadd/smembers: Set operations
    - hget/hset/hgetall: Hash operations
    - expire/ttl: Key expiration
    - health_check: Returns healthy status
    - add_to_queue_safe: Queue with backpressure support

    Usage:
        @pytest.mark.asyncio
        async def test_caching(mock_redis_client):
            mock_redis_client.get.return_value = '{"cached": "data"}'

            service = CacheService(redis=mock_redis_client)
            result = await service.get_cached("key")

            mock_redis_client.get.assert_called_with("key")
    """
    from backend.core.redis import QueueAddResult

    client = AsyncMock()

    # Basic operations
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.exists = AsyncMock(return_value=0)
    client.keys = AsyncMock(return_value=[])

    # Pub/sub
    client.publish = AsyncMock(return_value=1)
    client.subscribe = AsyncMock()
    client.unsubscribe = AsyncMock()

    # List operations
    client.lpush = AsyncMock(return_value=1)
    client.rpush = AsyncMock(return_value=1)
    client.lpop = AsyncMock(return_value=None)
    client.rpop = AsyncMock(return_value=None)
    client.llen = AsyncMock(return_value=0)
    client.lrange = AsyncMock(return_value=[])

    # Set operations
    client.sadd = AsyncMock(return_value=1)
    client.smembers = AsyncMock(return_value=set())
    client.sismember = AsyncMock(return_value=False)
    client.srem = AsyncMock(return_value=1)

    # Hash operations
    client.hget = AsyncMock(return_value=None)
    client.hset = AsyncMock(return_value=1)
    client.hgetall = AsyncMock(return_value={})
    client.hdel = AsyncMock(return_value=1)

    # Expiration
    client.expire = AsyncMock(return_value=True)
    client.ttl = AsyncMock(return_value=-2)  # Key doesn't exist
    client.setex = AsyncMock(return_value=True)

    # Health check
    client.health_check = AsyncMock(
        return_value={
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }
    )

    # Queue operations with backpressure
    client.add_to_queue_safe = AsyncMock(return_value=QueueAddResult(success=True, queue_length=1))

    # Ping for health checks
    client.ping = AsyncMock(return_value=True)

    # Pipeline support
    mock_pipeline = AsyncMock()
    mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
    mock_pipeline.__aexit__ = AsyncMock(return_value=None)
    mock_pipeline.execute = AsyncMock(return_value=[])
    client.pipeline = MagicMock(return_value=mock_pipeline)

    return client


@pytest.fixture
def mock_settings():
    """Create a mock Settings object with common defaults.

    Returns a MagicMock configured with typical application settings:
    - database_url: Test PostgreSQL URL
    - redis_url: Test Redis URL
    - ai_host: localhost
    - detector_port: 8001
    - nemotron_port: 8002
    - camera_root: /export/foscam

    Usage:
        def test_with_settings(mock_settings):
            mock_settings.detector_port = 9000  # Override specific setting

            with patch("backend.core.config.get_settings", return_value=mock_settings):
                client = DetectorClient()
                # client uses mock_settings.detector_port
    """
    from unittest.mock import MagicMock

    settings = MagicMock()

    # Database settings
    settings.database_url = "postgresql+asyncpg://security:test@localhost:5432/security_test"  # pragma: allowlist secret
    settings.database_pool_size = 5
    settings.database_max_overflow = 10

    # Redis settings
    settings.redis_url = "redis://localhost:6379/15"

    # AI service settings
    settings.ai_host = "localhost"
    settings.detector_port = 8001
    settings.detector_url = "http://localhost:8001"
    settings.nemotron_port = 8002
    settings.nemotron_url = "http://localhost:8002"
    settings.florence_port = 8003
    settings.florence_url = "http://localhost:8003"

    # Camera settings
    settings.camera_root = "/export/foscam"

    # Detection settings
    settings.confidence_threshold = 0.5
    settings.batch_timeout_seconds = 90
    settings.batch_idle_timeout_seconds = 30

    # Application settings
    settings.debug = False
    settings.environment = "test"
    settings.log_level = "INFO"

    # API settings
    settings.api_host = "0.0.0.0"  # noqa: S104
    settings.api_port = 8000

    return settings


@pytest.fixture
def mock_baseline_service() -> AsyncMock:
    """Create a mock BaselineService for tests.

    Returns an AsyncMock with update_baseline configured.
    This is commonly needed to avoid database interactions in unit tests.

    Usage:
        @pytest.fixture(autouse=True)
        def patch_baseline(mock_baseline_service):
            with patch("backend.services.detector_client.get_baseline_service", return_value=mock_baseline_service):
                yield
    """
    from unittest.mock import MagicMock

    service = MagicMock()
    service.update_baseline = AsyncMock()
    service.get_baseline = AsyncMock(return_value=None)
    service.check_anomaly = AsyncMock(return_value=False)
    return service


# =============================================================================
# Factory Fixtures (using factory_boy)
# =============================================================================
# These fixtures provide access to factory classes for creating test data.
# See backend/tests/factories.py for factory implementations.


@pytest.fixture
def camera_factory():
    """Provide CameraFactory for creating Camera instances.

    Usage:
        def test_something(camera_factory):
            camera = camera_factory(id="test_cam", name="Test Camera")
            # or use traits
            camera = camera_factory(offline=True)
    """
    from backend.tests.factories import CameraFactory

    return CameraFactory


@pytest.fixture
def detection_factory():
    """Provide DetectionFactory for creating Detection instances.

    Usage:
        def test_something(detection_factory):
            detection = detection_factory(object_type="person", confidence=0.95)
            # or use traits
            detection = detection_factory(video=True)
            detection = detection_factory(high_confidence=True)
    """
    from backend.tests.factories import DetectionFactory

    return DetectionFactory


@pytest.fixture
def event_factory():
    """Provide EventFactory for creating Event instances.

    Usage:
        def test_something(event_factory):
            event = event_factory(risk_score=75)
            # or use traits
            event = event_factory(high_risk=True)
            event = event_factory(fast_path=True)
    """
    from backend.tests.factories import EventFactory

    return EventFactory


@pytest.fixture
def zone_factory():
    """Provide ZoneFactory for creating Zone instances.

    Usage:
        def test_something(zone_factory):
            zone = zone_factory(name="Driveway")
            # or use traits
            zone = zone_factory(entry_point=True)
            zone = zone_factory(polygon=True, disabled=True)
    """
    from backend.tests.factories import ZoneFactory

    return ZoneFactory


# =============================================================================
# NeMo Data Designer Synthetic Scenarios (NEM-3230)
# =============================================================================
# These fixtures provide access to pre-generated synthetic scenarios for
# prompt evaluation and testing.

SYNTHETIC_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"


@pytest.fixture(scope="session")
def synthetic_scenarios() -> Generator:
    """Load pre-generated NeMo Data Designer scenarios.

    Returns a pandas DataFrame with synthetic security scenarios for testing.
    Skips if scenarios file doesn't exist or pandas is not installed.

    Usage:
        def test_with_scenarios(synthetic_scenarios):
            assert len(synthetic_scenarios) > 0
            assert "scenario_type" in synthetic_scenarios.columns
    """
    # Check if pandas is available
    try:
        import pandas as pd
    except ImportError:
        pytest.skip("pandas not installed (required for synthetic scenarios)")

    parquet_path = SYNTHETIC_FIXTURES_DIR / "scenarios.parquet"
    if not parquet_path.exists():
        pytest.skip(
            "Synthetic scenarios not generated yet. Run tools/nemo_data_designer/generate_scenarios.py"
        )

    yield pd.read_parquet(parquet_path)


@pytest.fixture(scope="session")
def scenario_by_type(synthetic_scenarios):
    """Group scenarios by type for targeted testing.

    Returns a dictionary mapping scenario types to DataFrames filtered by that type.
    Skips if synthetic_scenarios is not available.

    Usage:
        def test_threat_scenarios(scenario_by_type):
            threat_scenarios = scenario_by_type["threat"]
            for scenario in threat_scenarios.itertuples():
                assert scenario.ground_truth_range[0] >= 70  # Threats score high
    """
    if synthetic_scenarios is None:
        pytest.skip("Synthetic scenarios not available")

    return {
        "normal": synthetic_scenarios[synthetic_scenarios["scenario_type"] == "normal"],
        "suspicious": synthetic_scenarios[synthetic_scenarios["scenario_type"] == "suspicious"],
        "threat": synthetic_scenarios[synthetic_scenarios["scenario_type"] == "threat"],
        "edge_case": synthetic_scenarios[synthetic_scenarios["scenario_type"] == "edge_case"],
    }
