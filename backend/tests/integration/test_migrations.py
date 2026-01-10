"""Integration tests for fresh database migrations.

This module tests that all Alembic migrations apply cleanly to a fresh database,
ensuring no migration failures occur during initial deployment or database recreation.

Test Coverage:
1. All migrations apply to a fresh (empty schema) database without errors
2. Expected tables exist after migrations complete
3. Migrations can be rolled back cleanly
4. Migration state tracking (alembic_version) works correctly

Note: These tests create isolated databases and run migrations, which can take
longer than the default timeout. Tests are marked with appropriate timeouts.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse, urlunparse

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from alembic import command

if TYPE_CHECKING:
    from collections.abc import Generator

# Path to backend directory where alembic.ini lives
BACKEND_PATH = Path(__file__).resolve().parent.parent.parent

# Marker for tests that require longer timeout due to database operations
pytestmark = [pytest.mark.timeout(60)]  # 60 second timeout for migration tests


def get_sync_db_url() -> str | None:
    """Get a synchronous database URL for migration testing.

    Returns:
        Sync PostgreSQL URL (without asyncpg driver), or None if unavailable.
    """
    # Check for test database URL from environment
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        # Use default dev URL
        url = "postgresql://security:security_dev_password@localhost:5432/security"  # pragma: allowlist secret

    # Convert async URL to sync (remove +asyncpg)
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "")

    return url


def _create_test_migration_db(base_url: str, db_name: str) -> str:
    """Create an isolated test database for migration testing.

    Args:
        base_url: The base PostgreSQL URL (e.g., to 'security' database)
        db_name: The name of the new test database to create

    Returns:
        Connection URL to the newly created database
    """
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    parsed = urlparse(base_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    user = parsed.username or "postgres"
    password = parsed.password or "postgres"

    # Connect to 'postgres' database to create the test database
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
            # First terminate any connections to the database if it exists
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (db_name,),
            )
            # Drop if exists (clean state)
            cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
            # Create fresh database
            cur.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        conn.close()

    # Return URL pointing to the new database
    new_parsed = parsed._replace(path=f"/{db_name}")
    return urlunparse(new_parsed)


def _drop_test_migration_db(base_url: str, db_name: str) -> None:
    """Drop the test migration database during cleanup.

    Args:
        base_url: The base PostgreSQL URL
        db_name: The name of the database to drop
    """
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    parsed = urlparse(base_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    user = parsed.username or "postgres"
    password = parsed.password or "postgres"

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
                cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        finally:
            conn.close()
    except Exception:  # best-effort cleanup, ok to ignore errors
        pass


def _reset_schema(db_url: str) -> None:
    """Reset the public schema to empty state (fresh database simulation).

    Args:
        db_url: Database connection URL
    """
    engine = create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        conn.commit()
    engine.dispose()


class TestFreshDatabaseMigrations:
    """Tests for applying migrations to a fresh database."""

    @pytest.fixture
    def fresh_db(self) -> Generator[str]:
        """Create a fresh test database for migration testing.

        This fixture:
        1. Creates a new empty database
        2. Temporarily unsets DATABASE_URL to use our test URL
        3. Yields the connection URL
        4. Restores DATABASE_URL and drops the database after the test
        """
        base_url = get_sync_db_url()
        if not base_url:
            pytest.skip("No database URL available")

        # Create unique database name to avoid conflicts with parallel tests
        import uuid

        db_name = f"migration_test_{uuid.uuid4().hex[:8]}"

        # Save original DATABASE_URL
        original_db_url = os.environ.get("DATABASE_URL")

        try:
            db_url = _create_test_migration_db(base_url, db_name)
            # Unset DATABASE_URL so alembic env.py uses the sqlalchemy.url config
            if "DATABASE_URL" in os.environ:
                del os.environ["DATABASE_URL"]
            yield db_url
        finally:
            # Restore original DATABASE_URL
            if original_db_url is not None:
                os.environ["DATABASE_URL"] = original_db_url
            _drop_test_migration_db(base_url, db_name)

    @pytest.fixture
    def alembic_config(self, fresh_db: str) -> Config:
        """Create an Alembic config pointing to the fresh test database."""
        alembic_ini = BACKEND_PATH / "alembic.ini"
        config = Config(str(alembic_ini))
        config.set_main_option("sqlalchemy.url", fresh_db)
        return config

    def test_all_migrations_apply_cleanly(self, fresh_db: str, alembic_config: Config) -> None:
        """All migrations should apply to a fresh database without errors.

        This test verifies that:
        1. Starting from an empty schema, all migrations can be applied
        2. No SQL errors occur during migration
        3. The database reaches the 'head' revision
        """
        # Apply all migrations to head
        # This should not raise any exceptions
        command.upgrade(alembic_config, "head")

        # Verify we reached the expected head revision
        script = ScriptDirectory.from_config(alembic_config)
        expected_head = script.get_current_head()

        engine = create_engine(fresh_db)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            current_version = result.scalar()

        engine.dispose()

        assert current_version == expected_head, (
            f"Expected migration head {expected_head}, got {current_version}"
        )

    def test_expected_tables_exist_after_migration(
        self, fresh_db: str, alembic_config: Config
    ) -> None:
        """Verify that expected tables exist after all migrations complete.

        This ensures migrations create the core tables required by the application.
        """
        # Apply all migrations
        command.upgrade(alembic_config, "head")

        # Query for existing tables
        engine = create_engine(fresh_db)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
            tables = {row[0] for row in result}

        engine.dispose()

        # Core tables that must exist (from initial schema and key migrations)
        expected_tables = {
            # Initial schema tables
            "cameras",
            "events",
            "detections",
            "gpu_stats",
            "logs",
            "api_keys",
            # Added by subsequent migrations
            "zones",
            "alert_rules",
            "alerts",
            "audit_logs",
            "activity_baselines",
            "class_baselines",
            "scene_changes",
            "event_audits",
            "prompt_configs",
            "prompt_versions",
            "event_detections",
            "notification_preferences",
            "quiet_hours_periods",
            "camera_notification_settings",
            "event_feedback",
            "user_calibrations",
            # Alembic tracking table
            "alembic_version",
        }

        missing_tables = expected_tables - tables
        assert not missing_tables, (
            f"Missing tables after migration: {missing_tables}. Found tables: {sorted(tables)}"
        )

    def test_migration_creates_expected_indexes(
        self, fresh_db: str, alembic_config: Config
    ) -> None:
        """Verify that migrations create essential indexes for query performance."""
        # Apply all migrations
        command.upgrade(alembic_config, "head")

        engine = create_engine(fresh_db)
        with engine.connect() as conn:
            # Get all indexes in public schema
            result = conn.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                    """
                )
            )
            indexes = {row[0] for row in result}

        engine.dispose()

        # Key indexes that should exist for performance
        # (subset of most critical indexes)
        expected_index_patterns = [
            "idx_events_started_at",
            "idx_detections_camera_id",
            "idx_detections_detected_at",
            "idx_gpu_stats_recorded_at",
        ]

        for pattern in expected_index_patterns:
            matching = [idx for idx in indexes if pattern in idx.lower()]
            assert len(matching) >= 1, (
                f"No index matching '{pattern}' found. Available indexes: {sorted(indexes)}"
            )

    def test_migration_downgrade_to_base(self, fresh_db: str, alembic_config: Config) -> None:
        """Migrations should downgrade cleanly to base (empty state).

        This tests the rollback path, ensuring downgrades don't leave orphaned
        objects or fail due to dependency issues.
        """
        # First upgrade to head
        command.upgrade(alembic_config, "head")

        # Verify tables exist
        engine = create_engine(fresh_db)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'")
            )
            table_count_before = result.scalar()

        assert table_count_before > 1, "Tables should exist after upgrade"

        # Now downgrade to base
        command.downgrade(alembic_config, "base")

        # Verify tables are dropped (only alembic_version may remain)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
            remaining_tables = {row[0] for row in result}

        engine.dispose()

        # Only alembic_version should remain after downgrade
        app_tables = remaining_tables - {"alembic_version"}
        assert len(app_tables) == 0, f"Tables remain after downgrade to base: {app_tables}"

    def test_migration_upgrade_downgrade_upgrade_idempotency(
        self, fresh_db: str, alembic_config: Config
    ) -> None:
        """Test that upgrade -> downgrade -> upgrade produces consistent state.

        This verifies migration idempotency and that the upgrade path works
        correctly after a rollback scenario.
        """
        # First upgrade
        command.upgrade(alembic_config, "head")

        # Get initial table state
        engine = create_engine(fresh_db)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
            tables_after_first_upgrade = {row[0] for row in result}

        # Downgrade to base
        command.downgrade(alembic_config, "base")

        # Upgrade again
        command.upgrade(alembic_config, "head")

        # Get final table state
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
            tables_after_second_upgrade = {row[0] for row in result}

        engine.dispose()

        # Tables should match
        assert tables_after_first_upgrade == tables_after_second_upgrade, (
            f"Tables differ between upgrades.\n"
            f"First: {sorted(tables_after_first_upgrade)}\n"
            f"Second: {sorted(tables_after_second_upgrade)}"
        )

    def test_migration_stepwise_upgrade(self, fresh_db: str, alembic_config: Config) -> None:
        """Test upgrading one migration at a time to catch inter-migration issues.

        Some migration bugs only manifest when applying migrations sequentially
        rather than all at once.
        """
        script = ScriptDirectory.from_config(alembic_config)

        # Get all revisions in order (base to head)
        revisions = list(script.walk_revisions("base", "head"))
        # Reverse to get base-first order
        revisions.reverse()

        engine = create_engine(fresh_db)

        # Apply each migration one at a time
        for rev in revisions:
            try:
                command.upgrade(alembic_config, rev.revision)
            except Exception as e:
                pytest.fail(f"Migration {rev.revision} ({rev.doc}) failed: {e}")

        # Verify final state matches head
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            current = result.scalar()

        engine.dispose()

        expected_head = script.get_current_head()
        assert current == expected_head, (
            f"Stepwise upgrade didn't reach head. Got {current}, expected {expected_head}"
        )


class TestMigrationRollback:
    """Tests for migration rollback scenarios."""

    @pytest.fixture
    def fresh_db(self) -> Generator[str]:
        """Create a fresh test database for rollback testing."""
        base_url = get_sync_db_url()
        if not base_url:
            pytest.skip("No database URL available")

        import uuid

        db_name = f"rollback_test_{uuid.uuid4().hex[:8]}"

        # Save original DATABASE_URL
        original_db_url = os.environ.get("DATABASE_URL")

        try:
            db_url = _create_test_migration_db(base_url, db_name)
            # Unset DATABASE_URL so alembic env.py uses the sqlalchemy.url config
            if "DATABASE_URL" in os.environ:
                del os.environ["DATABASE_URL"]
            yield db_url
        finally:
            # Restore original DATABASE_URL
            if original_db_url is not None:
                os.environ["DATABASE_URL"] = original_db_url
            _drop_test_migration_db(base_url, db_name)

    @pytest.fixture
    def alembic_config(self, fresh_db: str) -> Config:
        """Create an Alembic config pointing to the fresh test database."""
        alembic_ini = BACKEND_PATH / "alembic.ini"
        config = Config(str(alembic_ini))
        config.set_main_option("sqlalchemy.url", fresh_db)
        return config

    def test_partial_rollback_to_specific_revision(
        self, fresh_db: str, alembic_config: Config
    ) -> None:
        """Test rolling back to a specific revision (not base).

        This tests the common scenario of rolling back a problematic migration
        while keeping earlier migrations intact.
        """
        # Upgrade to head first
        command.upgrade(alembic_config, "head")

        # Get the initial schema revision (first migration)
        initial_rev = "968b0dff6a9b"  # Initial schema revision

        # Downgrade to initial schema
        command.downgrade(alembic_config, initial_rev)

        # Verify current revision
        engine = create_engine(fresh_db)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            current = result.scalar()

        engine.dispose()

        assert current == initial_rev, f"Expected revision {initial_rev}, got {current}"

    def test_downgrade_preserves_alembic_version_table(
        self, fresh_db: str, alembic_config: Config
    ) -> None:
        """Verify alembic_version table persists across downgrades.

        The alembic_version table must survive downgrades to track migration state.
        """
        command.upgrade(alembic_config, "head")
        command.downgrade(alembic_config, "base")

        engine = create_engine(fresh_db)
        with engine.connect() as conn:
            # Check alembic_version table exists
            result = conn.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT FROM pg_tables
                        WHERE schemaname = 'public'
                        AND tablename = 'alembic_version'
                    )
                    """
                )
            )
            exists = result.scalar()

        engine.dispose()

        assert exists, "alembic_version table should exist after downgrade to base"


class TestMigrationIntegrity:
    """Tests for migration script integrity and consistency."""

    @pytest.fixture
    def alembic_config(self) -> Config:
        """Create an Alembic config for script analysis."""
        alembic_ini = BACKEND_PATH / "alembic.ini"
        return Config(str(alembic_ini))

    def test_no_multiple_heads(self, alembic_config: Config) -> None:
        """Verify there's only one migration head (no unmerged branches).

        Multiple heads indicate unmerged migration branches which can cause
        deployment issues.
        """
        script = ScriptDirectory.from_config(alembic_config)
        heads = script.get_heads()

        assert len(heads) == 1, (
            f"Multiple migration heads detected: {heads}. "
            f"Merge branches with 'alembic merge heads -m \"merge message\"'"
        )

    def test_all_revisions_have_upgrade_and_downgrade(self, alembic_config: Config) -> None:
        """Verify all migration scripts have both upgrade and downgrade functions.

        Migrations without downgrade functions cannot be rolled back, which is
        problematic for production deployments.
        """
        script = ScriptDirectory.from_config(alembic_config)

        for rev in script.walk_revisions():
            module = rev.module
            assert hasattr(module, "upgrade"), f"Migration {rev.revision} missing upgrade function"
            assert hasattr(module, "downgrade"), (
                f"Migration {rev.revision} missing downgrade function"
            )

    def test_migration_chain_is_complete(self, alembic_config: Config) -> None:
        """Verify the migration chain from base to head is unbroken.

        A broken chain indicates missing or corrupted migration files.
        """
        script = ScriptDirectory.from_config(alembic_config)

        # Walk from base to head should succeed without gaps
        try:
            revisions = list(script.walk_revisions("base", "heads"))
            assert len(revisions) > 0, "No migrations found in the chain"
        except Exception as e:
            pytest.fail(f"Migration chain is broken: {e}")

    def test_no_duplicate_revision_ids(self, alembic_config: Config) -> None:
        """Verify no duplicate revision IDs exist.

        Duplicate IDs cause Alembic to fail or behave unpredictably.
        """
        script = ScriptDirectory.from_config(alembic_config)

        revision_ids: list[str] = []
        for rev in script.walk_revisions():
            if rev.revision in revision_ids:
                pytest.fail(f"Duplicate revision ID found: {rev.revision}")
            revision_ids.append(rev.revision)
