"""Pytest configuration and shared fixtures.

This module provides shared test fixtures for all backend tests.

FIXTURE HIERARCHY AND ORGANIZATION:
====================================

Root Fixtures (backend/tests/conftest.py - THIS FILE):
    Database-per-Worker Isolation (pytest-xdist):
        - cleanup_stale_databases: Session-scoped autouse, removes leftover test databases

    Database Fixtures:
        - isolated_db: Function-scoped isolated database for unit tests (PostgreSQL)
        - test_db: Callable session factory for unit tests
        - session: Transaction-based isolation with savepoint rollback

    Mock Fixtures (Consolidated - NEM-3152):
        - mock_db_session: Comprehensive database session mock
        - mock_db_session_context: Async context manager wrapper for mock_db_session
        - mock_redis_client: Full-featured Redis client mock
        - mock_http_client: HTTP client mock with all methods
        - mock_http_response: HTTP response mock
        - mock_detector_client: YOLO26 detector service mock
        - mock_nemotron_client: Nemotron LLM service mock
        - mock_baseline_service: Baseline service mock
        - mock_websocket_client: Comprehensive WebSocket client mock
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

    Contract Tests (backend/tests/contracts/conftest.py):
        - test_app: FastAPI app with mocked dependencies
        - async_client: HTTP client for contract testing
        NOTE: Uses mock_db_session and mock_redis_client from root conftest.py

    Security Tests (backend/tests/security/conftest.py):
        - security_client: Synchronous test client for security testing

    Unit Tests (backend/tests/unit/conftest.py):
        - mock_transformers_for_speed: Speed optimization for transformers import


CONSOLIDATION (NEM-3152):
==========================
Mock fixtures have been consolidated in this root conftest.py to eliminate duplication.
Previously, mock_db_session and mock_redis_client were duplicated in:
- backend/tests/conftest.py (comprehensive versions)
- backend/tests/contracts/conftest.py (basic versions - REMOVED)

Shared utility functions have been extracted to backend/tests/testing_utils.py:
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

Domain-Specific Hypothesis Strategies:
- See backend/tests/hypothesis_strategies.py for comprehensive property-based testing strategies
- Includes strategies for: camera IDs, detection bboxes, risk scores, confidence values,
  timestamps, RTSP URLs, detection labels, polygon coordinates, and composite model instances
- Use with @given decorator from hypothesis for property-based tests

Flaky Test Detection:
- @pytest.mark.flaky is an allowlist-governed quarantine (WP0.8): collection
  fails if a marked test has no unexpired entry with a tracking ref in
  .github/flake-allowlist.yml. Registered marked tests have failures
  converted to skips; un-allowlisted failures fail once and stay failed.
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

# R-T7-CRASH: pyroscope-io's native sampling profiler (oncpu + gil_only=False)
# crashes pytest-xdist workers on aarch64/64k-page kernels whenever a test
# boots the FastAPI lifespan (main.py calls init_profiling()). Disabling it for
# the test session only — prod/compose keep the PYROSCOPE_ENABLED=true default
# (docker-compose.prod.yml), and an explicit env value still wins (setdefault).
_os.environ.setdefault("PYROSCOPE_ENABLED", "false")

import logging
import os
import re
import socket
import sys
import warnings
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlparse, urlunparse

import psycopg2
import pytest
from hypothesis import HealthCheck, Phase, Verbosity
from hypothesis import settings as hypothesis_settings
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# NEM-1061: Logger for test cleanup handlers
logger = logging.getLogger(__name__)


# Add backend to path for imports
backend_path = Path(__file__).parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# =============================================================================
# WP0.8: @pytest.mark.flaky is an allowlist-governed quarantine
# =============================================================================

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FLAKE_ENTRY_RE = re.compile(r"^\s*-\s+id:\s*(\S+)")
_FLAKE_FIELD_RE = re.compile(r"^\s+(tracking|expires):\s*(.+?)\s*$")


def _active_flake_allowlist_ids() -> tuple[list[str], Path]:
    """Ids in .github/flake-allowlist.yml whose expiry has not passed.

    Same 15-line flat-list parse as scripts/check-flake-allowlist.py and
    scripts/flake-k-filter.py (the zero-coupling convention those two already
    share deliberately). FLAKE_ALLOWLIST_FILE is the test seam. Expired ids are
    EXCLUDED — expiry is revocation; reviving a quarantine means re-registering,
    and check-flake-allowlist.py fails CI on the stale entry anyway.
    """
    path = Path(
        os.environ.get("FLAKE_ALLOWLIST_FILE") or _REPO_ROOT / ".github/flake-allowlist.yml"
    )
    if not path.is_file():
        return [], path
    import datetime as dt

    entries: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _FLAKE_ENTRY_RE.match(line)
        if m:
            entries.append({"id": m.group(1)})
            continue
        if entries:
            fm = _FLAKE_FIELD_RE.match(line)
            if fm:
                entries[-1][fm.group(1)] = fm.group(2).strip("'\"")
    today = dt.date.today()
    active = []
    for e in entries:
        try:
            if dt.date.fromisoformat(e.get("expires", "")) < today:
                continue
        except ValueError:
            continue
        active.append(e["id"])
    return active, path


def _enforce_flaky_registration(items: list[pytest.Item]) -> None:
    """Fail collection if any collected item carries @pytest.mark.flaky without
    a matching, unexpired entry in .github/flake-allowlist.yml (WP0.8).

    The marker feeds pytest_runtest_makereport's failure→skip conversion, so an
    unregistered mark means a permanent failure can hide as a skip with no
    owner, no expiry, no review — the exact state .github/flake-allowlist.yml
    exists to prevent (spec §5.2: un-allowlisted failures fail once and stay
    failed). Id matching follows the -k semantics flake-k-filter.py already
    ships: the id must appear in the item's nodeid.
    """
    active, path = _active_flake_allowlist_ids()
    violations = [
        item.nodeid
        for item in items
        if item.get_closest_marker("flaky") is not None
        and not any(flake_id in item.nodeid for flake_id in active)
    ]
    if violations:
        shown = "\n".join(f"  - {nodeid}" for nodeid in sorted(violations)[:20])
        more = f"\n  ... and {len(violations) - 20} more" if len(violations) > 20 else ""
        msg = (
            f"{len(violations)} @pytest.mark.flaky test(s) are NOT registered in "
            f"{path.relative_to(_REPO_ROOT)} (quarantine without a tracking ref and expiry "
            "is how WP0.2-class rot hides for months — a marked test's failures convert to "
            "skips): \n"
            f"{shown}{more}\n"
            "Fix: register each with a real Linear tracking ref + expiry in "
            ".github/flake-allowlist.yml, or remove the mark if the test is not actually flaky."
        )
        raise pytest.UsageError(msg)


# =============================================================================
# Schema Extraction Utilities for Snapshot Testing (NEM-5021)
# =============================================================================


def extract_schema(data: object, *, preserve_lengths: bool = False) -> object:
    """Extract structure-only schema from API response data for snapshot testing.

    This utility recursively traverses the response data and replaces actual
    values with type names, creating a structure-only snapshot. This allows
    us to validate API schema changes without false positives from dynamic
    data like timestamps, IDs, or counts.

    Args:
        data: The response data to extract schema from (dict, list, or primitive)
        preserve_lengths: If True, preserve list lengths instead of using [<type>]

    Returns:
        Schema representation with type names instead of actual values

    Examples:
        >>> extract_schema({"id": 123, "name": "test", "active": True})
        {'id': 'int', 'name': 'str', 'active': 'bool'}

        >>> extract_schema({"items": [{"id": 1}, {"id": 2}]})
        {'items': [{'id': 'int'}]}

        >>> extract_schema({"items": [{"id": 1}, {"id": 2}]}, preserve_lengths=True)
        {'items': [{'id': 'int'}, {'id': 'int'}]}

        >>> extract_schema(None)
        'NoneType'

        >>> extract_schema([1, 2, 3])
        ['int']
    """
    # Handle dict: recursively extract schema for all values
    if isinstance(data, dict):
        return {
            key: extract_schema(value, preserve_lengths=preserve_lengths)
            for key, value in data.items()
        }

    # Handle list: use first item as representative (or preserve all if requested)
    if isinstance(data, list):
        if not data:
            return []
        if preserve_lengths:
            return [extract_schema(item, preserve_lengths=preserve_lengths) for item in data]
        return [extract_schema(data[0], preserve_lengths=preserve_lengths)]

    # Handle primitives and None: return type name
    if data is None:
        return "NoneType"
    return type(data).__name__


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
    # Load .env file if it exists (for local development)
    # Only load if DATABASE_URL isn't already set (to avoid interfering with tests)
    if "DATABASE_URL" not in os.environ:
        from pathlib import Path

        from dotenv import load_dotenv

        env_file = Path(__file__).parents[2] / ".env"
        if env_file.exists():
            load_dotenv(env_file, override=False)

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

    # Disable OpenTelemetry tracing in the test process (R-T7-OTEL-OOM):
    # otel_enabled defaults True (config.py:1815), so every TestClient(app)
    # with a live lifespan runs setup_telemetry and arms an OTLP
    # BatchSpanProcessor pointed at the shipped default endpoint
    # (http://alloy:4317) — unreachable outside the compose network, and
    # every export 502s through the sandbox proxy. Failed exports retry
    # with the span held in memory; xdist workers running thousands of
    # span-generating tests (websocket auth flows, LLM analysis pipeline)
    # accumulated ~52GB anon RSS per worker until the host OOM-killed the
    # process (11 'node down' cascades in validate run 3; dmesg:
    # 'Out of memory: Killed process ... [pytest-xdist r] anon-rss:
    # 51844004kB'). Production keeps the default True; this only opts the
    # test process out, matching how the D21 memray marker is scoped.
    os.environ.setdefault("OTEL_ENABLED", "false")

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
# Use POSTGRES_PASSWORD from environment if set, otherwise fall back to default
_POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "security_dev_password")
DEFAULT_DEV_POSTGRES_URL = f"postgresql+asyncpg://security:{_POSTGRES_PASSWORD}@localhost:5432/security"  # pragma: allowlist secret

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


def _apply_timeout_marker(item: pytest.Item, fspath_str: str, cli_cap: float | None = None) -> None:
    """Apply appropriate timeout marker to a test item.

    Helper function extracted from pytest_collection_modifyitems to reduce
    branch complexity in the main hook.

    Timeout hierarchy (M3 T5: a CLI --timeout now GOVERNS — pytest-timeout's
    per-item markers override the CLI option, so validate.sh's --timeout=30
    integration stage silently ran at the 5s stamp; ruling packet
    docs/superpowers/rulings/2026-09-14-m3-t5-timeout-config-ruling-packet.md,
    owner-approved 2026-09-14):
    1. Explicit @pytest.mark.timeout(N) on test - always unchanged
    2. CLI --timeout=N (cli_cap) - governs slow/integration tiers
    3. @pytest.mark.slow marker - 30 seconds
    4. Integration tests (in integration/ directory) - 5 seconds
    5. Default from pyproject.toml - no marker needed
    """
    # Skip if test has explicit timeout marker
    if item.get_closest_marker("timeout"):
        return

    # CLI --timeout governs everything unmarked (M3 T5 honesty fix).
    if cli_cap:
        item.add_marker(pytest.mark.timeout(cli_cap))
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

    Timeout hierarchy (highest priority first; M3 T5 — CLI now governs):
    1. CLI --timeout=0 disables all timeouts (for CI)
    2. Explicit @pytest.mark.timeout(N) on test - unchanged
    3. CLI --timeout=N - governs every unmarked item (was: silently
       overridden by the stamps below; ruling packet owner-approved 2026-09-14)
    4. @pytest.mark.slow marker - 30 seconds
    5. Integration tests (in integration/ directory) - 5 seconds
    6. Default from pyproject.toml (timeout ini) for everything else
    """
    # Check if timeouts are disabled via CLI (--timeout=0)
    # This is used in CI where environment is slower
    cli_timeout = config.getoption("timeout", default=None)
    timeouts_disabled = cli_timeout == 0

    # Pre-create markers to avoid repeated marker creation in loop
    skip_integration = pytest.mark.skip(
        reason="Integration test requires database - skipped in unit test run"
    )

    for item in items:
        fspath_str = str(item.fspath)
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

        # === INTEGRATION TEST HANDLING ===
        elif is_integration:
            # Apply integration marker
            if not item.get_closest_marker("integration"):
                item.add_marker(pytest.mark.integration)

            # M3 T4d: the "repository tests share database state" premise
            # this block enforced is stale. test_db (the only DB fixture
            # repositories tests use) resolves through get_test_db_url ->
            # _memo_worker_database, which mints a PER-WORKER database
            # ('<base>_gwN') since the spec-3.1 cutover — the same isolation
            # every other integration test runs on. xdist_group forced all
            # ~201 repository items onto ONE worker for no reason; dropping
            # the markers lets worksteal balance them across the tier.

        # === TIMEOUT HANDLING ===
        if not timeouts_disabled:
            _apply_timeout_marker(item, fspath_str, cli_timeout)

    # WP0.8: every surviving @pytest.mark.flaky item must be registered in the
    # governed allowlist — an unregistered quarantine fails collection outright.
    _enforce_flaky_registration(items)


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


def pytest_sessionstart(session: pytest.Session) -> None:
    """Pre-clean crashed sessions' root-tier worker databases (spec 3.1 Task 7).

    Coordination (master) process only — every xdist worker sets
    PYTEST_XDIST_WORKER before its inner session starts (xdist/remote.py), so
    the same conftest loaded in a worker skips. Silent when Postgres or the
    test-DB env is absent: AI-tier / setup_lib sessions share this testpaths
    and must not gain a Postgres dependency from this hook.

    Deliberately a hook, not the plan's autouse session fixture: an autouse
    session fixture fires inside EVERY xdist worker (each worker = its own
    session), so a sweep written that way runs -n times and races itself;
    pytest_sessionstart is the only place the once-per-run semantics live.
    """
    if _coordination_worker_id() != "master":
        return
    base_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not base_url or os.environ.get("TEST_DB_NO_WORKER_SUFFIX"):
        return
    if not _check_postgres_connection():
        return
    try:
        _sweep_stale_worker_dbs(base_url)
    except Exception as exc:  # hygiene must never fail a session at startup
        logger.warning(f"worker-DB stale sweep failed: {exc}")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Write flaky test tracking data at end of test session.

    Outputs a JSON file with test outcomes for aggregation across CI runs.
    This data is used by scripts/analyze-flaky-tests.py to detect flaky tests.

    Then reclaims this process's worker databases (spec 3.1 Task 7). Placement
    note: conftest hooks run before pytest-runner's sessionfinish (LIFO), i.e.
    before session-scoped fixture finalizers — that is safe ONLY because
    _reclaim_worker_dbs is guard-first (any connection still on the database,
    ours or a foreign session's, defers the drop to the next session's sweep).
    """
    import json
    from datetime import UTC, datetime

    # NOTE: the flaky-data block below ends in `return` when
    # FLAKY_TEST_RESULTS_FILE is unset, so worker-DB reclamation must run
    # BEFORE it, not at the function tail.
    _reclaim_root_worker_dbs_at_session_end()

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
    0. TEST_DB_NO_WORKER_SUFFIX set -> verbatim env URL (documented emergency
       opt-out; the pre-spec-3.1 behavior, kept as the rollback lever)
    1. TEST_DATABASE_URL environment variable (explicit override)
    2. Local PostgreSQL on port 5432 (development with Podman/Docker)

    For integration tests, use the module-scoped containers in
    backend/tests/integration/conftest.py instead.

    Returns:
        str: PostgreSQL connection URL with asyncpg driver, pointed at a
        PER-WORKER database ('<base>_gwN' under xdist, '<base>_main' when
        serial), created idempotently on first call (spec 3.1; M1
        R-T7-DBRACE-FINAL proved the verbatim return serializes every worker
        on one schema-reset advisory lock).

    Raises:
        RuntimeError: If no PostgreSQL instance is available
    """
    # 0. Emergency opt-out (rollback lever named in spec 3.1's risk framing).
    if os.environ.get("TEST_DB_NO_WORKER_SUFFIX"):
        env_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
        if env_url:
            if "postgresql://" in env_url and "asyncpg" not in env_url:
                env_url = env_url.replace("postgresql://", "postgresql+asyncpg://")
            return env_url

    # 1. Check for explicit environment variable override (CI sets both).
    #    The returned URL is PER-WORKER: the base DB name gets the xdist worker
    #    id suffixed and the database is ensured to exist. Connection params
    #    (host/port/credentials) still come from the env.
    env_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if env_url:
        # Ensure asyncpg driver
        if "postgresql://" in env_url and "asyncpg" not in env_url:
            env_url = env_url.replace("postgresql://", "postgresql+asyncpg://")
        return _memo_worker_database(env_url)

    # 2. Check for local PostgreSQL (development environment with Podman/Docker)
    if _check_postgres_connection():
        return _memo_worker_database(DEFAULT_DEV_POSTGRES_URL)

    raise RuntimeError(
        "PostgreSQL not available for unit testing. Options:\n"
        "1. Start PostgreSQL via 'podman-compose up -d postgres' (development)\n"
        "2. Set TEST_DATABASE_URL environment variable\n"
        "Note: Integration tests use module-scoped testcontainers."
    )


# ── Per-worker test database isolation (fast-confidence-loop spec SS3.1) ─────
# Root-tier tests must not share one database across xdist workers: every
# test_db/isolated_db invocation would queue on _reset_db_schema's advisory
# lock (M1 R-T7-DBRACE-FINAL: load 8.1 on 72 cores, all of it queue). Pattern
# mirrors backend/tests/integration/conftest.py's proven worker machinery;
# duplication across conftests is deliberate (conftest-to-conftest imports are
# brittle under pytest's importer) and matches the existing _get_advisory_lock_key
# duplication. get_test_db_url now routes through these helpers (the spec 3.1
# cutover landed in e8619d80); session lifecycle (create-once memo, master-only
# stale sweep, collision-safe reclamation) lives above get_test_redis_url.


def worker_id() -> str:
    """Current xdist worker id ('gw0'…) or 'master' when running serially.

    Reads the env var xdist sets in each worker at startup
    (xdist/remote.py: os.environ['PYTEST_XDIST_WORKER'] = workerinput['workerid'])
    so it works inside plain functions without a fixture request.
    """
    return os.environ.get("PYTEST_XDIST_WORKER", "master")


def worker_db_name(base_url: str) -> str:
    """Per-worker database name derived from the base DB name.

    master -> '<base>_main', gwN -> '<base>_gwN'. Base name is sanitized to
    [a-z0-9_] and the total is capped at 63 chars (Postgres NAMEDATALEN).
    """
    base = urlparse(base_url.replace("+asyncpg", "")).path.lstrip("/") or "test"
    prefix = re.sub(r"[^a-z0-9_]", "_", base.lower()).strip("_") or "test"
    suffix = "main" if worker_id() == "master" else worker_id()
    name = f"{prefix}_{suffix}"
    return name[:63]


def _create_worker_database(base_url: str, db_name: str) -> str:
    """CREATE DATABASE (IF-MISSING) via psycopg2 autocommit; return worker URL.

    Idempotent: two workers (or a rerun after a crash) racing on the same name
    is safe — the pg_database existence check plus catching duplicate_database
    covers the race window.
    """
    parsed = urlparse(base_url.replace("+asyncpg", ""))
    conn = psycopg2.connect(
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        user=parsed.username or "postgres",
        password=parsed.password or "postgres",
        dbname=parsed.path.lstrip("/") or "postgres",
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            if not cur.fetchone():
                try:
                    # Use sql.Identifier for safe escaping (NEM-4452)
                    # nosemgrep: sql-injection-format-string - sql.Identifier() is safe parameterization
                    cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
                except psycopg2.errors.DuplicateDatabase:
                    pass  # lost the race to a sibling worker: the DB exists, that is all we wanted
    finally:
        conn.close()
    worker_url = urlunparse(parsed._replace(path=f"/{db_name}"))
    if "postgresql://" in worker_url and "asyncpg" not in worker_url:
        worker_url = worker_url.replace("postgresql://", "postgresql+asyncpg://")
    return worker_url


_PROTECTED_DB_NAMES = frozenset({"security", "security_test", "postgres", "template1", "template0"})


def _drop_worker_database(base_url: str, db_name: str, max_retries: int = 3) -> None:
    """Terminate connections then DROP DATABASE, advisory-locked, retrying.

    Refuses protected names (raises ValueError — these helpers run against the
    developer's live Postgres; a bug here must not be able to eat the dev DB).
    Final failure after retries logs a warning only: leaked fcl/test worker DBs
    are cleaned by the next session's pre-clean sweep, never by failing tests.
    """
    import time

    if db_name in _PROTECTED_DB_NAMES:
        raise ValueError(f"refusing to drop protected database: {db_name}")

    parsed = urlparse(base_url.replace("+asyncpg", ""))
    lock_key = _get_advisory_lock_key(f"fcl_drop:{db_name}")

    for attempt in range(max_retries):
        conn = None
        try:
            conn = psycopg2.connect(
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
                user=parsed.username or "postgres",
                password=parsed.password or "postgres",
                dbname="postgres",  # must connect elsewhere to DROP
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_lock(%s)", (lock_key,))
                cur.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()",
                    (db_name,),
                )
                # nosemgrep: sql-injection-format-string - sql.Identifier() is safe parameterization
                cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name)))
                cur.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))
            return
        except psycopg2.Error as exc:
            logger.warning(f"drop {db_name} attempt {attempt + 1} failed: {exc}")
            if attempt + 1 < max_retries:
                time.sleep(0.1 * (2**attempt))
        finally:
            if conn is not None:
                try:
                    conn.close()
                except psycopg2.Error:
                    pass
    logger.warning(
        f"could not drop worker database {db_name}; stale copy will be swept next session"
    )


# ── Worker-DB session lifecycle: create-once memo + sweep + reclaim ─────────
# Task 7 (spec 3.1). Create-per-call (Task 6) is idempotent but re-parses
# pg_database on every fixture invocation, and crashed sessions leak copies.
# The collision-safety rules gate run 9 demands (ledger: "worker-DB names
# COLLIDE by construction"):
#   - only names in THIS process's memo are ever drop candidates at teardown;
#   - a name with ANY live connection (ours, a sibling worker's, or another
#     pytest session's) is skipped, never fought over;
#   - the sweep's membership regex can never match the base DB, the
#     integration tier's 'security_test' / 'security_test_gwN' names, or
#     template_test/test_db_gw* (those stay with cleanup_stale_databases);
#   - nothing here ever runs a DROP during session setup except the
#     master-only sweep of exactly-matched stale names.

_worker_db_url_cache: dict[tuple[str, str], str] = {}
_worker_dbs_created: set[str] = set()


def _coordination_worker_id() -> str:
    """Master/worker id for session bookkeeping WITHOUT importing xdist.

    Reads the env var xdist sets in every worker before its inner session
    starts (xdist/remote.py: os.environ["PYTEST_XDIST_WORKER"]). Kept separate
    from worker_id() — same value, different contract: session hooks must not
    import xdist's helpers (a worker runs pytest_sessionstart before its
    plugins are configured) nor take a fixture ``request`` (hooks have none).
    """
    return os.environ.get("PYTEST_XDIST_WORKER", "master")


def _memo_worker_database(base_url: str) -> str:
    """Create-once: memoized per (worker, base URL) worker-database creation.

    Cache hit returns the URL without a psycopg2 round trip. The key includes
    worker_id() so an in-process env change (a test monkeypatching
    TEST_DATABASE_URL under a different PYTEST_XDIST_WORKER, as
    test_db_isolation does) re-derives instead of returning another worker's
    URL. Names created are bookkept for _reclaim_worker_dbs.
    """
    key = (worker_id(), base_url)
    url = _worker_db_url_cache.get(key)
    if url is None:
        name = worker_db_name(base_url)
        url = _create_worker_database(base_url, name)
        _worker_db_url_cache[key] = url
        _worker_dbs_created.add(name)
    return url


def _base_db_prefix(base_url: str) -> str:
    """Sanitized worker-DB name prefix for a base URL.

    Mirrors worker_db_name()'s sanitize/strip/cap logic exactly (minus the
    worker suffix) so sweep membership and name derivation cannot diverge.
    """
    base = urlparse(base_url.replace("+asyncpg", "")).path.lstrip("/") or "test"
    prefix = re.sub(r"[^a-z0-9_]", "_", base.lower()).strip("_") or "test"
    return prefix[:63]


def _list_databases_by_prefix(base_url: str, prefix: str) -> list[str]:
    """Existing database names starting with prefix (anchored, LIKE-escaped).

    Connects to the server's 'postgres' db. Connection errors propagate to the
    caller (the sweep treats them as "skip hygiene this session", never as
    "no databases" — fail-closed).
    """
    parsed = urlparse(base_url.replace("+asyncpg", ""))
    conn = psycopg2.connect(
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        user=parsed.username or "postgres",
        password=parsed.password or "postgres",
        dbname="postgres",
    )
    try:
        with conn.cursor() as cur:
            like_prefix = prefix.replace("\\", "\\\\").replace("_", "\\_")
            cur.execute(
                "SELECT datname FROM pg_database WHERE datname LIKE %s || '%' ORDER BY 1",
                (like_prefix,),
            )
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def _db_has_active_connections(base_url: str, db_name: str) -> bool:
    """True if any server process is currently connected to db_name.

    Fail-closed: psycopg2.Error propagates — an unreachable server must read
    as "do not drop", not as "nobody is home".
    """
    parsed = urlparse(base_url.replace("+asyncpg", ""))
    conn = psycopg2.connect(
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        user=parsed.username or "postgres",
        password=parsed.password or "postgres",
        dbname="postgres",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_stat_activity WHERE datname = %s LIMIT 1",
                (db_name,),
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


def _sweep_stale_worker_dbs(base_url: str) -> None:
    """Drop <prefix>_main / <prefix>_gw<N> leftovers from crashed sessions.

    Master-only (pytest_sessionstart). Membership is exactly the live
    root-tier naming: anchored fullmatch of prefix_main or prefix_gw<digits>
    — so 'security_test' / 'security_test_gw0' (integration tier, possibly a
    LIVE gate's right now), the bare base DB, and template_test / test_db_gw*
    (kept by cleanup_stale_databases) can never match. Anything still holding
    a connection is a live session's database (gate run 9: 'a concurrent
    -n auto run dropped the live gate's DBs') and is skipped, never stolen.
    """
    prefix = _base_db_prefix(base_url)
    try:
        candidates = [
            name
            for name in _list_databases_by_prefix(base_url, prefix)
            if name not in _PROTECTED_DB_NAMES
            and re.fullmatch(rf"^{prefix}_(?:gw[0-9]+|main)$", name)
        ]
    except psycopg2.Error as exc:
        logger.warning(f"worker-DB stale sweep skipped (server unreachable): {exc}")
        return
    for name in candidates:
        try:
            if _db_has_active_connections(base_url, name):
                logger.info(f"worker DB {name} is in active use (live session?) — sweep skips it")
                continue
        except psycopg2.Error as exc:
            logger.warning(f"worker DB {name} liveness check failed ({exc}) — sweep skips it")
            continue
        logger.info(f"Dropping stale root-tier worker database: {name}")
        _drop_worker_database(base_url, name)


def _reclaim_root_worker_dbs_at_session_end() -> None:
    """Gate the Task-7 reclamation: coordination process only, env only.

    xdist workers never drop anything: gate run 9 proved a session-end drop
    kills siblings mid-flight, and xdist can recycle a gwN id for a
    late-spawned replacement worker (worksteal reschedule) whose database a
    per-worker drop would then delete out from under it. Parallel runs' worker
    DBs therefore persist until the next session's sweep — the plan's own
    tolerance ("leaked fcl/test worker DBs are cleaned by the next session's
    pre-clean sweep, never by failing tests").
    """
    if _coordination_worker_id() != "master" or os.environ.get("TEST_DB_NO_WORKER_SUFFIX"):
        return
    base_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not base_url:
        return
    try:
        _reclaim_worker_dbs(base_url)
    except Exception as exc:  # cleanup errors never fail the session (NEM-4491 doctrine)
        logger.warning(f"worker-DB session teardown failed: {exc}")


def _reclaim_worker_dbs(base_url: str) -> None:
    """Drop databases THIS process created at session end, if provably unused.

    Master-only caller (_reclaim_root_worker_dbs_at_session_end). Memo-scoped
    ownership + zero-connection check are the two collision guards; leftovers
    are tolerated by design and picked up by the next session's sweep.
    """
    for name in sorted(_worker_dbs_created):
        try:
            if _db_has_active_connections(base_url, name):
                logger.info(
                    f"worker DB {name} still has connections; next session's sweep reclaims it"
                )
                continue
        except psycopg2.Error as exc:
            logger.warning(f"worker DB {name} liveness check failed ({exc}); leaving it in place")
            continue
        _drop_worker_database(base_url, name)


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


# =============================================================================
# Database-per-Worker Isolation for pytest-xdist
# =============================================================================
# These fixtures enable parallel integration test execution by giving each
# xdist worker its own database copy. Uses PostgreSQL's TEMPLATE feature for
# instant database copies.
#
# Architecture:
#   CI Runner starts
#       └── Postgres container (single instance)
#             ├── template_test (created once, schema applied)
#             ├── test_db_gw0 (copied from template)
#             ├── test_db_gw1 (copied from template)
#             └── test_db_gw{N} (copied from template)
#
# See docs/plans/2026-01-24-integration-test-parallelization-design.md


def _get_base_database_url() -> str:
    """Get the base PostgreSQL URL for creating template/worker databases.

    Returns the connection URL pointing to the 'postgres' system database,
    which is required for database creation operations.

    Returns:
        PostgreSQL connection URL pointing to postgres database
    """
    # Get the base URL from environment or default
    base_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not base_url:
        base_url = DEFAULT_DEV_POSTGRES_URL

    # Ensure we're using asyncpg driver
    if "postgresql://" in base_url and "asyncpg" not in base_url:
        base_url = base_url.replace("postgresql://", "postgresql+asyncpg://")

    return base_url


def _parse_database_url(url: str) -> dict:
    """Parse PostgreSQL URL into connection components.

    Args:
        url: PostgreSQL connection URL

    Returns:
        Dictionary with host, port, user, password, dbname keys
    """
    # Remove asyncpg driver for psycopg2 compatibility
    parsed = urlparse(url.replace("+asyncpg", ""))
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "user": parsed.username or "security",
        "password": parsed.password or "security_dev_password",
        "dbname": parsed.path.lstrip("/") or "security",
    }


def _build_database_url(base_url: str, db_name: str) -> str:
    """Build a database URL with a different database name.

    Args:
        base_url: Original PostgreSQL URL
        db_name: New database name to use

    Returns:
        PostgreSQL URL pointing to the new database
    """
    parsed = urlparse(base_url.replace("+asyncpg", ""))
    new_parsed = parsed._replace(path=f"/{db_name}")
    result = urlunparse(new_parsed)
    # Add asyncpg driver back
    return result.replace("postgresql://", "postgresql+asyncpg://")


def _get_advisory_lock_key(db_name: str) -> int:
    """Generate a consistent advisory lock key from database name.

    NEM-4491: Uses a hash-based approach to generate a lock key that's
    consistent across processes but unique per database name.

    Args:
        db_name: The database name to generate a lock key for

    Returns:
        Integer lock key for use with pg_advisory_lock
    """
    import hashlib

    # Use hash to generate consistent lock key from db_name
    hash_val = hashlib.sha256(f"test_db_cleanup:{db_name}".encode()).hexdigest()
    # PostgreSQL advisory locks use bigint, so we need to fit within int64
    return int(hash_val[:15], 16) % (2**31)


def _drop_database_with_lock(cur, db_name: str, max_retries: int = 3) -> bool:
    """Drop a database with advisory lock protection and retry logic.

    NEM-4491: Uses PostgreSQL advisory locks to prevent race conditions when
    multiple workers try to drop the same database concurrently.

    Args:
        cur: Database cursor
        db_name: Name of the database to drop
        max_retries: Maximum number of retry attempts

    Returns:
        True if database was dropped successfully, False otherwise
    """
    lock_key = _get_advisory_lock_key(db_name)

    for attempt in range(max_retries):
        try:
            # Try to acquire advisory lock (non-blocking)
            cur.execute("SELECT pg_try_advisory_lock(%s)", (lock_key,))
            lock_acquired = cur.fetchone()[0]

            if not lock_acquired:
                # Lock held by another process, wait briefly and retry
                import time

                delay = 0.1 * (2**attempt)  # Exponential backoff
                logger.debug(
                    f"Advisory lock for {db_name} held by another process, "
                    f"retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(delay)
                continue

            try:
                # Terminate connections to the database
                cur.execute(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = %s AND pid <> pg_backend_pid()
                    """,
                    (db_name,),
                )
                # Drop the database using sql.Identifier for safe escaping (NEM-4452)
                # nosemgrep: sql-injection-format-string - sql.Identifier() is safe parameterization
                cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name)))
                logger.info(f"Cleaned up stale test database: {db_name}")
                return True
            finally:
                # Always release the advisory lock
                cur.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))

        except Exception as e:
            if attempt < max_retries - 1:
                import time

                delay = 0.1 * (2**attempt)
                logger.debug(
                    f"Error dropping {db_name}: {e}, retrying in {delay:.2f}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(delay)
            else:
                logger.warning(
                    f"Failed to drop stale database {db_name} after {max_retries} attempts: {e}"
                )

    return False


@pytest.fixture(scope="session", autouse=True)
def cleanup_stale_databases(request: pytest.FixtureRequest) -> Generator[None]:
    """Remove leftover test databases from previous failed runs.

    This autouse fixture runs at the start of each test session to clean up
    any stale databases (test_db_gw*, template_test) that may have been left
    behind by crashed or interrupted test runs.

    Only runs on the master process (or when running without xdist) to avoid
    race conditions between workers.

    NEM-4491: Uses advisory locks and retry logic to prevent race conditions
    when multiple test sessions try to clean up databases concurrently.
    """
    # Only run cleanup on master process
    try:
        import xdist

        worker_id = xdist.get_xdist_worker_id(request)
    except ImportError, AttributeError:
        worker_id = "master"

    if worker_id != "master":
        yield
        return

    # Check if PostgreSQL is available
    if not _check_postgres_connection():
        logger.debug("PostgreSQL not available, skipping stale database cleanup")
        yield
        return

    try:
        base_url = _get_base_database_url()
        params = _parse_database_url(base_url)

        conn = psycopg2.connect(
            host=params["host"],
            port=params["port"],
            user=params["user"],
            password=params["password"],
            dbname="postgres",
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        try:
            with conn.cursor() as cur:
                # Find stale test databases
                # NEM-4491: Use stricter pattern matching to avoid accidental drops
                cur.execute(
                    """
                    SELECT datname FROM pg_database
                    WHERE (datname LIKE 'test_db_gw%%' AND datname ~ '^test_db_gw[0-9]+$')
                       OR datname = 'template_test'
                    """
                )
                stale_dbs = [row[0] for row in cur.fetchall()]

                for db_name in stale_dbs:
                    # NEM-4491: Use advisory lock protected drop with retries
                    _drop_database_with_lock(cur, db_name)
        finally:
            conn.close()
    except Exception as e:
        # Log but don't fail - cleanup errors shouldn't prevent tests from running
        logger.warning(f"Failed to clean up stale databases: {e}")

    yield


def _apply_schema_to_database(db_url: str) -> None:
    """Apply full schema to a database synchronously.

    This function creates all tables and adds any missing columns to ensure
    the database schema matches the current SQLAlchemy models.

    Args:
        db_url: PostgreSQL connection URL for the database
    """
    from sqlalchemy import create_engine, text

    # Import all models to ensure they're registered with Base.metadata
    from backend.models import Camera, Detection, Event, GPUStats, JobTransition  # noqa: F401
    from backend.models.camera import Base as ModelsBase
    from backend.models.event_feedback import EventFeedback  # noqa: F401
    from backend.models.user_calibration import UserCalibration  # noqa: F401

    # Create synchronous engine (without asyncpg)
    sync_url = db_url.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    try:
        with engine.begin() as conn:
            # Create all tables
            ModelsBase.metadata.create_all(conn)

            # Add any missing columns (using IF NOT EXISTS for idempotency)
            # These match the columns added in _reset_db_schema()
            conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS llm_prompt TEXT"))
            conn.execute(
                text("ALTER TABLE detections ADD COLUMN IF NOT EXISTS enrichment_data JSONB")
            )
            conn.execute(
                text(
                    "ALTER TABLE cameras "
                    "ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE events "
                    "ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE events "
                    "ADD COLUMN IF NOT EXISTS snooze_until TIMESTAMP WITH TIME ZONE"
                )
            )
            conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS search_vector TSVECTOR"))
            conn.execute(
                text("ALTER TABLE detections ADD COLUMN IF NOT EXISTS search_vector TSVECTOR")
            )
            conn.execute(text("ALTER TABLE detections ADD COLUMN IF NOT EXISTS labels JSONB"))
            conn.execute(
                text(
                    "ALTER TABLE user_calibration "
                    "ADD COLUMN IF NOT EXISTS correct_count INTEGER DEFAULT 0"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE user_calibration "
                    "ADD COLUMN IF NOT EXISTS missed_threat_count INTEGER DEFAULT 0"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE user_calibration "
                    "ADD COLUMN IF NOT EXISTS severity_wrong_count INTEGER DEFAULT 0"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE event_feedback ADD COLUMN IF NOT EXISTS expected_severity VARCHAR"
                )
            )

            # Create unique indexes for cameras table
            conn.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS idx_cameras_name_unique ON cameras (name)")
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "idx_cameras_folder_path_unique ON cameras (folder_path)"
                )
            )
    finally:
        engine.dispose()


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
    original_environment = os.environ.get("ENVIRONMENT")

    # Set default test values if not already set
    # This prevents Settings validation errors in unit tests that don't need a real DB
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = DEFAULT_DEV_POSTGRES_URL
    if not os.environ.get("REDIS_URL"):
        os.environ["REDIS_URL"] = DEFAULT_DEV_REDIS_URL
    # Always set ENVIRONMENT to development for tests to skip password validation
    if not os.environ.get("ENVIRONMENT"):
        os.environ["ENVIRONMENT"] = "development"

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

    if original_environment is None:
        os.environ.pop("ENVIRONMENT", None)
    else:
        os.environ["ENVIRONMENT"] = original_environment

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
# Consolidated Mock Fixtures (NEM-1448, NEM-3152)
# =============================================================================
# These fixtures consolidate common mock patterns to reduce duplication across tests.
# See backend/tests/mock_utils.py for factory functions that can be used directly.
# WebSocket utilities are available in backend/tests/websocket_utils.py.


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
    """Create a mock YOLO26 detector client.

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

    # Idempotency settings
    settings.idempotency_ttl_seconds = 86400  # 24 hours
    settings.idempotency_max_payload_size = 10485760  # 10MB
    settings.idempotency_chunk_size = 65536  # 64KB

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


@pytest.fixture
def mock_websocket_client() -> MagicMock:
    """Create a comprehensive mock WebSocket client for testing.

    Returns a MagicMock configured as a WebSocket with:
    - Connection state tracking (connected/disconnected)
    - Message tracking (sent messages captured)
    - Common operations: connect, disconnect, send, receive, subscribe, unsubscribe
    - Error injection support for testing error handling
    - Query params and headers support
    - Async context manager support

    Usage:
        def test_websocket_broadcast(mock_websocket_client):
            # Configure behavior
            mock_websocket_client.application_state.CONNECTED = WebSocketState.CONNECTED

            # Simulate sending message
            await mock_websocket_client.send_text('{"type": "event", "data": {...}}')

            # Verify message was sent
            assert mock_websocket_client.send_text.called
            assert len(mock_websocket_client.sent_messages) == 1

            # Simulate receiving message
            mock_websocket_client.receive_text.return_value = '{"action": "ping"}'
    """
    from fastapi.websockets import WebSocketState

    websocket = MagicMock()

    # Connection state tracking
    websocket.application_state = MagicMock()
    websocket.application_state.CONNECTED = WebSocketState.CONNECTED
    websocket.application_state.DISCONNECTED = WebSocketState.DISCONNECTED
    websocket.client_state = WebSocketState.DISCONNECTED

    # Track sent messages for verification
    websocket.sent_messages = []

    # Connection lifecycle methods
    async def mock_accept():
        websocket.client_state = WebSocketState.CONNECTED

    async def mock_close(code: int = 1000):
        websocket.client_state = WebSocketState.DISCONNECTED
        websocket.close_code = code

    websocket.accept = AsyncMock(side_effect=mock_accept)
    websocket.close = AsyncMock(side_effect=mock_close)
    websocket.close_code = None

    # Message sending methods
    async def mock_send_text(message: str):
        websocket.sent_messages.append({"type": "text", "data": message})

    async def mock_send_json(data: dict):
        websocket.sent_messages.append({"type": "json", "data": data})

    async def mock_send_bytes(data: bytes):
        websocket.sent_messages.append({"type": "bytes", "data": data})

    websocket.send_text = AsyncMock(side_effect=mock_send_text)
    websocket.send_json = AsyncMock(side_effect=mock_send_json)
    websocket.send_bytes = AsyncMock(side_effect=mock_send_bytes)

    # Message receiving methods (default to returning None)
    websocket.receive_text = AsyncMock(return_value=None)
    websocket.receive_json = AsyncMock(return_value=None)
    websocket.receive_bytes = AsyncMock(return_value=None)

    # Query parameters and headers
    websocket.query_params = {}
    websocket.headers = {}

    # Subscription tracking
    websocket.subscriptions = set()

    # Error injection support
    websocket.inject_error = None  # Set to exception to inject error on next operation

    # Async iteration support (for message streaming)
    async def mock_iter():
        # Empty async generator for default behavior
        for _ in []:
            yield

    websocket.__aiter__ = mock_iter

    return websocket


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


# ---------------------------------------------------------------------------
# freezegun + SIGALRM leak guard (M3 T11; gate-20 forensics 2026-09-15)
#
# Gate 20 attempt 2 lost 13 unit tests on two workers with `Failed: Timeout
# (>5.0s)` cascades. Root cause (proven from the poisoned gw's own tracebacks
# + a forced reproduction with --timeout 0.05): pytest-timeout's signal method
# fires SIGALRM on the MAIN thread at any bytecode boundary — including inside
# freeze_time.__enter__/start() (the gw3 traceback shows the alarm landing
# mid-start()) and inside async freeze bodies (abandoned coroutines never run
# __exit__). Either way stop() never executes: the worker keeps
# datetime=Fakedatetime / time.monotonic=fake_monotonic patched AND freezegun's
# asyncio escape hatch (EventLoopClass.time = real_monotonic, installed at the
# END of start()) never lands. Every later async test on that worker then
# hangs in asyncio.sleep until ITS 5s alarm fires, and sync tests compute
# against the frozen clock (attempt 2's dwell assert -63691200.0 ==
# detected_at(2026-01-21 14:30 UTC) - leaked-now(2024-01-15 10:30), exactly).
# One stray alarm poisons every remaining test on its worker.
#
# Two-layer guard, test infra only; a timed-out test still gets its own
# verdict — this only stops ONE timeout cascading into a dozen inherited ones:
#  1. start() made alarm-atomic: the running handler is swapped for a deferrer
#     during start(), so start() can never be interrupted mid-patch; a fired
#     alarm is re-delivered to the original handler AFTER the freeze window
#     fully opened (the test still fails as timed-out; its __enter__ raised
#     past start, and layer 2 unwinds the opened window below).
#  2. per-phase repair: any window still open when a test phase finished is a
#     leak (well-behaved freeze_time blocks close inside the test) — stopped
#     via the _freeze_time owner saved by the wrapper, whose stop() unwinds
#     exactly what start() patched, per-module attribute restorations
#     included.
# ---------------------------------------------------------------------------

_FREEZE_OWNERS: list = []  # _freeze_time instances paired with freezegun's factory stacks


def _install_freezegun_alarm_guard() -> None:
    """Wrap freezegun start/stop against mid-patch SIGALRM (idempotent)."""
    import signal

    import freezegun.api as fa

    if getattr(fa._freeze_time.start, "_alarm_guarded", False):
        return
    orig_start = fa._freeze_time.start
    orig_stop = fa._freeze_time.stop

    def guarded_start(self):  # mirrors freezegun's start() contract
        fired: list = []

        def _defer(sig, frame):  # never raises: start() must run atomically
            fired.append((sig, frame))

        prev = signal.signal(signal.SIGALRM, _defer)
        try:
            remaining = signal.setitimer(signal.ITIMER_REAL, 0)
        except Exception:  # pragma: no cover - non-POSIX fallback
            remaining = (0.0, 0.0)
        try:
            factory = orig_start(self)
        except BaseException:
            signal.signal(signal.SIGALRM, prev)
            raise
        _FREEZE_OWNERS.append(self)
        signal.signal(signal.SIGALRM, prev)
        if fired:
            # alarm expired inside the guarded window: re-deliver to the real
            # handler NOW (window fully open -> the handler's pytest.fail
            # unwinds the test; layer 2 unwinds the freeze window at report
            # time). No timer re-arm: pytest-timeout's one-shot is spent, and
            # prev may be SIG_DFL/None (not callable) — deliver only to handlers.
            if callable(prev):
                prev(*fired[0])
        elif remaining and remaining[0] > 0:
            # still-pending timer: restore it with its original remaining budget
            signal.setitimer(signal.ITIMER_REAL, remaining[0], remaining[1] or 0)
        return factory

    def guarded_stop(self):
        orig_stop(self)
        try:
            _FREEZE_OWNERS.remove(self)
        except ValueError:
            pass

    guarded_start._alarm_guarded = True  # type: ignore[attr-defined]
    fa._freeze_time.start = guarded_start  # type: ignore[method-assign]
    fa._freeze_time.stop = guarded_stop  # type: ignore[method-assign]


def _repair_freeze_leaks(when: str, nodeid: str) -> int:
    """Force-stop leaked freeze windows; returns the repaired count."""
    try:
        import freezegun.api as fa
    except ImportError:  # pragma: no cover - freezegun is a hard dev dep
        return 0
    repaired = 0
    while fa.freeze_factories:
        if _FREEZE_OWNERS:
            _FREEZE_OWNERS[-1].stop()  # unwinds start() fully (wrapped: pops ours too)
        else:  # pragma: no cover - only if the guard failed to pair
            fa.freeze_factories.pop()
            fa.ignore_lists.pop()
            fa.tick_flags.pop()
            fa.tz_offsets.pop()
            if not fa.freeze_factories:
                import copyreg
                import datetime as _dt
                import time as _time

                _dt.datetime = fa.real_datetime
                _dt.date = fa.real_date
                copyreg.dispatch_table.pop(fa.real_datetime, None)
                copyreg.dispatch_table.pop(fa.real_date, None)
                _time.time = fa.real_time
                _time.monotonic = fa.real_monotonic
                _time.perf_counter = fa.real_perf_counter
                _time.localtime = fa.real_localtime
                _time.gmtime = fa.real_gmtime
                _time.strftime = fa.real_strftime
        repaired += 1
    if repaired:
        warnings.warn(
            f"freezegun leak guard: force-stopped {repaired} leaked freeze window(s) "
            f"after {when} of {nodeid} (SIGALRM landed inside a freeze_time window)",
            RuntimeWarning,
            stacklevel=2,
        )
    return repaired


@pytest.hookimpl
def pytest_collection_finish(session: pytest.Session) -> None:
    # NOTE: this conftest already defines pytest_configure (:260); installing
    # here instead of shadowing it. Collection is complete, no test started.
    _install_freezegun_alarm_guard()
    _repair_freeze_leaks("collection", "<startup>")


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Repair leaked freezegun state after every test phase (see block above)."""
    _repair_freeze_leaks(report.when, report.nodeid)
