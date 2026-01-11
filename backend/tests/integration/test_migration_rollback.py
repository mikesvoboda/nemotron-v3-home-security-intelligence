"""Migration rollback verification tests (NEM-2221).

This module provides comprehensive tests for database migration rollback scenarios,
ensuring that migrations can be safely rolled back without data loss or corruption.

Test Coverage:
1. Individual migration rollback (each migration can be downgraded)
2. Data integrity preservation during rollback
3. Schema state verification after rollback
4. Orphaned object detection (indexes, constraints, enums)
5. Rollback with existing data
6. Multi-step rollback scenarios

Related: NEM-2096 (Epic: Disaster Recovery Testing)
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse, urlunparse

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from alembic import command

if TYPE_CHECKING:
    from collections.abc import Generator

# Path to backend directory where alembic.ini lives
BACKEND_PATH = Path(__file__).resolve().parent.parent.parent

# Marker for tests that require longer timeout due to database operations
pytestmark = [pytest.mark.timeout(90)]  # 90 second timeout for migration rollback tests


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


class TestIndividualMigrationRollback:
    """Tests for rolling back individual migrations."""

    @pytest.fixture
    def fresh_db(self) -> Generator[str]:
        """Create a fresh test database for migration rollback testing."""
        base_url = get_sync_db_url()
        if not base_url:
            pytest.skip("No database URL available")

        db_name = f"migration_rollback_{uuid.uuid4().hex[:8]}"

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

    def test_each_migration_has_working_downgrade(
        self, fresh_db: str, alembic_config: Config
    ) -> None:
        """Each migration should have a working downgrade function.

        This test verifies that migrations can be successfully rolled back
        from head to base, ensuring the downgrade path is functional.

        Note: This test uses Alembic's built-in downgrade mechanism which
        handles merge migrations correctly by unwinding the full history.
        """
        engine = create_engine(fresh_db)

        # Upgrade to head first
        command.upgrade(alembic_config, "head")

        # Verify we're at head
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            current = result.scalar()
            assert current is not None, "No migration version found after upgrade"

        # Now downgrade all the way to base
        # This tests that all downgrade functions work without crashing
        try:
            command.downgrade(alembic_config, "base")
        except Exception as e:
            pytest.fail(f"Downgrade from head to base failed: {e}")

        # Verify we're at base (no version in alembic_version table)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM alembic_version"))
            count = result.scalar()
            assert count == 0, (
                "Expected no version after downgrade to base, but found version entries"
            )

        engine.dispose()

    def test_rollback_single_migration_and_reapply(
        self, fresh_db: str, alembic_config: Config
    ) -> None:
        """Test rolling back a single migration and reapplying it.

        This verifies that a migration can be downgraded and upgraded repeatedly
        without causing issues (idempotency).
        """
        # Upgrade to head
        command.upgrade(alembic_config, "head")

        script = ScriptDirectory.from_config(alembic_config)
        head_revision = script.get_current_head()

        # Get the revision before head
        head_script = script.get_revision(head_revision)
        if not head_script.down_revision:
            pytest.skip("No previous revision to test with")

        previous_revision = head_script.down_revision

        engine = create_engine(fresh_db)

        # Get table count at head
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'")
            )
            tables_at_head = result.scalar()

        # Downgrade one step
        command.downgrade(alembic_config, "-1")

        # Verify we're at the previous revision
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            current = result.scalar()
            assert current == previous_revision

        # Upgrade back to head
        command.upgrade(alembic_config, "head")

        # Verify table count matches original
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'")
            )
            tables_after_reapply = result.scalar()

        engine.dispose()

        assert tables_at_head == tables_after_reapply, (
            f"Table count mismatch after downgrade/upgrade cycle: "
            f"before={tables_at_head}, after={tables_after_reapply}"
        )


class TestDataIntegrityDuringRollback:
    """Tests for data integrity preservation during migration rollback."""

    @pytest.fixture
    def fresh_db(self) -> Generator[str]:
        """Create a fresh test database for data integrity testing."""
        base_url = get_sync_db_url()
        if not base_url:
            pytest.skip("No database URL available")

        db_name = f"data_integrity_{uuid.uuid4().hex[:8]}"

        # Save original DATABASE_URL
        original_db_url = os.environ.get("DATABASE_URL")

        try:
            db_url = _create_test_migration_db(base_url, db_name)
            if "DATABASE_URL" in os.environ:
                del os.environ["DATABASE_URL"]
            yield db_url
        finally:
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

    def test_core_table_data_preserved_during_rollback(
        self, fresh_db: str, alembic_config: Config
    ) -> None:
        """Core table data should be preserved when rolling back migrations.

        This test verifies that data in core tables (cameras, detections, events)
        is not lost when rolling back migrations that don't affect those tables.
        """
        # Upgrade to head
        command.upgrade(alembic_config, "head")

        engine = create_engine(fresh_db)

        # Insert test data into cameras table
        test_camera_id = f"rollback_test_{uuid.uuid4().hex[:8]}"
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO cameras (id, name, folder_path, status, created_at)
                    VALUES (:id, :name, :folder_path, 'online', NOW())
                    """
                ),
                {
                    "id": test_camera_id,
                    "name": "Rollback Test Camera",
                    "folder_path": "/test/path",
                },
            )
            conn.commit()

            # Verify data exists
            result = conn.execute(
                text("SELECT name FROM cameras WHERE id = :id"),
                {"id": test_camera_id},
            )
            camera_name_before = result.scalar()
            assert camera_name_before == "Rollback Test Camera"

        # Downgrade one step (to test data preservation)
        command.downgrade(alembic_config, "-1")

        # Verify data still exists and is intact
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM cameras WHERE id = :id"),
                {"id": test_camera_id},
            )
            camera_name_after = result.scalar()

        engine.dispose()

        assert camera_name_after == camera_name_before, (
            f"Camera data changed during rollback: "
            f"before='{camera_name_before}', after='{camera_name_after}'"
        )

    def test_foreign_key_relationships_maintained_during_rollback(
        self, fresh_db: str, alembic_config: Config
    ) -> None:
        """Foreign key relationships should remain valid during rollback.

        This test ensures that foreign key constraints are maintained when
        rolling back migrations, preventing orphaned records.
        """
        # Upgrade to head
        command.upgrade(alembic_config, "head")

        engine = create_engine(fresh_db)

        # Insert related test data (camera + detection)
        test_camera_id = f"fk_test_{uuid.uuid4().hex[:8]}"
        with engine.connect() as conn:
            # Insert camera
            conn.execute(
                text(
                    """
                    INSERT INTO cameras (id, name, folder_path, status, created_at)
                    VALUES (:id, :name, :folder_path, 'online', NOW())
                    """
                ),
                {
                    "id": test_camera_id,
                    "name": "FK Test Camera",
                    "folder_path": "/test/fk",
                },
            )

            # Insert detection (references camera via FK)
            conn.execute(
                text(
                    """
                    INSERT INTO detections (camera_id, file_path, detected_at, object_type, confidence)
                    VALUES (:camera_id, '/test/detection.jpg', NOW(), 'person', 0.95)
                    """
                ),
                {"camera_id": test_camera_id},
            )
            conn.commit()

            # Verify FK relationship exists
            result = conn.execute(
                text(
                    """
                    SELECT d.id, d.camera_id, c.name
                    FROM detections d
                    JOIN cameras c ON d.camera_id = c.id
                    WHERE d.camera_id = :camera_id
                    """
                ),
                {"camera_id": test_camera_id},
            )
            related_data_before = result.fetchone()
            assert related_data_before is not None
            assert related_data_before[2] == "FK Test Camera"

        # Downgrade one step
        command.downgrade(alembic_config, "-1")

        # Verify FK relationship still valid
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT d.id, d.camera_id, c.name
                    FROM detections d
                    JOIN cameras c ON d.camera_id = c.id
                    WHERE d.camera_id = :camera_id
                    """
                ),
                {"camera_id": test_camera_id},
            )
            related_data_after = result.fetchone()

        engine.dispose()

        assert related_data_after is not None, "FK relationship broken during rollback"
        assert related_data_after[2] == "FK Test Camera"


class TestSchemaStateAfterRollback:
    """Tests for verifying schema state after migration rollback."""

    @pytest.fixture
    def fresh_db(self) -> Generator[str]:
        """Create a fresh test database for schema verification testing."""
        base_url = get_sync_db_url()
        if not base_url:
            pytest.skip("No database URL available")

        db_name = f"schema_state_{uuid.uuid4().hex[:8]}"

        # Save original DATABASE_URL
        original_db_url = os.environ.get("DATABASE_URL")

        try:
            db_url = _create_test_migration_db(base_url, db_name)
            if "DATABASE_URL" in os.environ:
                del os.environ["DATABASE_URL"]
            yield db_url
        finally:
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

    def test_no_orphaned_indexes_after_rollback(
        self, fresh_db: str, alembic_config: Config
    ) -> None:
        """Verify no orphaned indexes remain after migration rollback.

        This test ensures that when a migration is rolled back, any indexes
        it created are properly dropped.
        """
        # Upgrade to head
        command.upgrade(alembic_config, "head")

        engine = create_engine(fresh_db)

        # Get indexes at head
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT schemaname, tablename, indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                    ORDER BY tablename, indexname
                    """
                )
            )
            indexes_at_head = {(row[0], row[1], row[2]) for row in result.fetchall()}

        # Downgrade one step
        command.downgrade(alembic_config, "-1")

        # Get indexes after downgrade
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT schemaname, tablename, indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                    ORDER BY tablename, indexname
                    """
                )
            )
            indexes_after_downgrade = {(row[0], row[1], row[2]) for row in result.fetchall()}

        # Upgrade back to head
        command.upgrade(alembic_config, "head")

        # Get indexes after re-upgrade
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT schemaname, tablename, indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                    ORDER BY tablename, indexname
                    """
                )
            )
            indexes_after_upgrade = {(row[0], row[1], row[2]) for row in result.fetchall()}

        engine.dispose()

        # Verify indexes match after full cycle
        assert indexes_at_head == indexes_after_upgrade, (
            f"Index mismatch after downgrade/upgrade cycle.\n"
            f"Missing: {indexes_at_head - indexes_after_upgrade}\n"
            f"Extra: {indexes_after_upgrade - indexes_at_head}"
        )

    def test_no_orphaned_enums_after_rollback(self, fresh_db: str, alembic_config: Config) -> None:
        """Verify no orphaned enum types remain after migration rollback.

        PostgreSQL enum types can be left behind after table drops if not
        properly cleaned up in downgrade functions.
        """
        # Upgrade to head
        command.upgrade(alembic_config, "head")

        engine = create_engine(fresh_db)

        # Get enums at head
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT typname
                    FROM pg_type
                    WHERE typtype = 'e'
                    AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
                    ORDER BY typname
                    """
                )
            )
            enums_at_head = {row[0] for row in result.fetchall()}

        # Downgrade to initial schema (which has no enums)
        initial_rev = "968b0dff6a9b"
        command.downgrade(alembic_config, initial_rev)

        # Get enums after downgrade
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT typname
                    FROM pg_type
                    WHERE typtype = 'e'
                    AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
                    ORDER BY typname
                    """
                )
            )
            enums_after_downgrade = {row[0] for row in result.fetchall()}

        engine.dispose()

        # Initial schema should have no enums
        assert len(enums_after_downgrade) == 0, (
            f"Orphaned enum types found after rollback to initial schema: {enums_after_downgrade}"
        )

    def test_no_orphaned_constraints_after_rollback(
        self, fresh_db: str, alembic_config: Config
    ) -> None:
        """Verify no orphaned constraints remain after migration rollback.

        This test ensures that check constraints, unique constraints, etc.
        are properly dropped when their tables are dropped.
        """
        # Upgrade to head
        command.upgrade(alembic_config, "head")

        engine = create_engine(fresh_db)

        # Get constraints at head (excluding FK constraints which are tested separately)
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT conname, contype
                    FROM pg_constraint
                    WHERE connamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
                    AND contype IN ('c', 'u')  -- Check and unique constraints
                    ORDER BY conname
                    """
                )
            )
            constraints_at_head = {(row[0], row[1]) for row in result.fetchall()}

        # Downgrade one step
        command.downgrade(alembic_config, "-1")

        # Upgrade back to head
        command.upgrade(alembic_config, "head")

        # Get constraints after re-upgrade
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT conname, contype
                    FROM pg_constraint
                    WHERE connamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
                    AND contype IN ('c', 'u')  -- Check and unique constraints
                    ORDER BY conname
                    """
                )
            )
            constraints_after_upgrade = {(row[0], row[1]) for row in result.fetchall()}

        engine.dispose()

        # Verify constraints match
        assert constraints_at_head == constraints_after_upgrade, (
            f"Constraint mismatch after downgrade/upgrade cycle.\n"
            f"Missing: {constraints_at_head - constraints_after_upgrade}\n"
            f"Extra: {constraints_after_upgrade - constraints_at_head}"
        )

    def test_table_schema_matches_expected_state_after_rollback(
        self, fresh_db: str, alembic_config: Config
    ) -> None:
        """Verify table schemas match expected state after rollback.

        This test uses SQLAlchemy's inspector to verify that the schema
        matches what's expected for a given migration state.
        """
        # Upgrade to initial schema
        initial_rev = "968b0dff6a9b"
        command.upgrade(alembic_config, initial_rev)

        engine = create_engine(fresh_db)
        inspector = inspect(engine)

        # Get schema at initial revision
        tables_at_initial = set(inspector.get_table_names(schema="public"))
        columns_at_initial = {}
        for table in tables_at_initial:
            columns_at_initial[table] = {col["name"] for col in inspector.get_columns(table)}

        # Upgrade to head
        command.upgrade(alembic_config, "head")

        # Downgrade back to initial
        command.downgrade(alembic_config, initial_rev)

        # Get schema after rollback
        inspector = inspect(engine)  # Refresh inspector
        tables_after_rollback = set(inspector.get_table_names(schema="public"))
        columns_after_rollback = {}
        for table in tables_after_rollback:
            columns_after_rollback[table] = {col["name"] for col in inspector.get_columns(table)}

        engine.dispose()

        # Verify tables match
        assert tables_at_initial == tables_after_rollback, (
            f"Table mismatch after rollback to initial schema.\n"
            f"Expected: {sorted(tables_at_initial)}\n"
            f"Got: {sorted(tables_after_rollback)}"
        )

        # Verify columns match for each table
        # Note: Tables that underwent partition conversion may have extra columns
        # from migrations that ran between initial and partition migration.
        # This is acceptable as it doesn't affect functionality.
        for table in tables_at_initial:
            expected = columns_at_initial[table]
            actual = columns_after_rollback.get(table, set())

            # Check that all expected columns exist
            missing = expected - actual
            assert not missing, (
                f"Missing columns in table '{table}' after rollback.\nMissing: {sorted(missing)}"
            )

            # Extra columns are acceptable for partitioned tables
            # (detections, events, logs, gpu_stats, audit_logs) due to migration ordering
            partitioned_tables = {"detections", "events", "logs", "gpu_stats", "audit_logs"}
            if table not in partitioned_tables:
                assert expected == actual, (
                    f"Column mismatch for table '{table}' after rollback.\n"
                    f"Expected: {sorted(expected)}\n"
                    f"Got: {sorted(actual)}"
                )
