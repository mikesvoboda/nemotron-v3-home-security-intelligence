from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import ProgrammingError

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.engine import Engine

# Add backend to path for imports
backend_path = Path(__file__).resolve().parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# Set up logging
logger = logging.getLogger(__name__)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="function")
def clean_db_config(integration_env: None) -> Generator[Config]:  # noqa: PLR0912
    """Create Alembic config with clean database state for each test.

    This fixture ensures that each test starts with a completely clean
    database (at base state) and restores it to head after the test completes.

    Args:
        integration_env: Fixture that sets TEST_DATABASE_URL environment variable.

    Yields:
        Alembic Config object configured for test database.
    """
    alembic_ini = backend_path / "alembic.ini"
    config = Config(str(alembic_ini))

    # Get database URL from environment and convert to sync
    db_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.fail("No database URL configured")

    # Convert async URL to sync for Alembic
    if "+asyncpg" in db_url:
        db_url = db_url.replace("+asyncpg", "")

    config.set_main_option("sqlalchemy.url", db_url)

    # Ensure we start from a clean state - downgrade to base before each test
    # The integration_db fixture already initializes the schema, so we need to
    # remove it completely before running migration tests
    db_url_str = config.get_main_option("sqlalchemy.url")
    if not db_url_str:
        pytest.fail("No database URL in config")

    temp_engine = create_engine(db_url_str)
    try:
        # Drop all tables manually to ensure clean state
        # This is necessary because integration_db creates tables directly
        inspector = inspect(temp_engine)
        tables = inspector.get_table_names()

        if tables:
            logger.debug(f"Dropping {len(tables)} existing tables for clean migration testing")
            with temp_engine.connect() as conn:
                # Drop all tables
                for table in tables:
                    try:
                        conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))  # nosemgrep
                    except Exception as e:
                        logger.warning(f"Failed to drop table {table}: {e}")
                conn.commit()

        # Drop alembic_version table if it exists
        with temp_engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
            conn.commit()

        # Drop all PostgreSQL ENUMs (custom types)
        with temp_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT t.typname
                FROM pg_type t
                JOIN pg_namespace n ON t.typnamespace = n.oid
                WHERE t.typtype = 'e' AND n.nspname = 'public'
                """
                )
            )
            enum_types = [row[0] for row in result]

            for enum_type in enum_types:
                try:
                    conn.execute(text(f"DROP TYPE IF EXISTS {enum_type} CASCADE"))  # nosemgrep
                except Exception as e:
                    logger.warning(f"Failed to drop enum {enum_type}: {e}")
            conn.commit()

        logger.debug("Database cleaned for migration testing (tables and enums dropped)")
    finally:
        temp_engine.dispose()

    yield config

    # Clean up after test - ensure database is at head for other integration tests
    try:
        # First downgrade to base to ensure clean state
        command.downgrade(config, "base")

        # Drop any remaining tables and enums
        temp_engine2 = create_engine(db_url_str)
        try:
            with temp_engine2.connect() as conn:
                # Drop remaining tables
                inspector2 = inspect(temp_engine2)
                tables2 = inspector2.get_table_names()
                for table in tables2:
                    try:
                        conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))  # nosemgrep
                    except Exception:
                        pass

                # Drop remaining enums
                result = conn.execute(
                    text(
                        """
                    SELECT t.typname
                    FROM pg_type t
                    JOIN pg_namespace n ON t.typnamespace = n.oid
                    WHERE t.typtype = 'e' AND n.nspname = 'public'
                    """
                    )
                )
                enum_types2 = [row[0] for row in result]
                for enum_type in enum_types2:
                    try:
                        conn.execute(text(f"DROP TYPE IF EXISTS {enum_type} CASCADE"))  # nosemgrep
                    except Exception:
                        pass

                conn.commit()
        finally:
            temp_engine2.dispose()

        # Now upgrade to head
        command.upgrade(config, "head")
        logger.debug("Database restored to head after migration testing")
    except Exception as e:
        logger.warning(f"Failed to restore database to head after test: {e}")


@pytest.fixture
def alembic_config(clean_db_config: Config) -> Config:
    """Alias for clean_db_config for backward compatibility.

    Args:
        clean_db_config: Clean database configuration fixture.

    Returns:
        Alembic Config object.
    """
    return clean_db_config


@pytest.fixture
def sync_engine(alembic_config: Config) -> Generator[Engine]:
    """Create a synchronous SQLAlchemy engine for direct database inspection.

    Args:
        alembic_config: Alembic configuration with database URL.

    Yields:
        SQLAlchemy Engine instance.
    """
    db_url = alembic_config.get_main_option("sqlalchemy.url")
    if not db_url:
        pytest.fail("No database URL in Alembic config")

    engine = create_engine(db_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def migration_context(sync_engine: Engine) -> MigrationContext:
    """Create a migration context for querying database revision state.

    Args:
        sync_engine: Synchronous SQLAlchemy engine.

    Returns:
        MigrationContext instance.
    """
    with sync_engine.connect() as conn:
        return MigrationContext.configure(conn)


def get_current_revision(sync_engine: Engine) -> str | None:
    """Get the current migration revision from the database.

    Args:
        sync_engine: Synchronous SQLAlchemy engine.

    Returns:
        Current revision ID or None if no migrations applied.
    """
    with sync_engine.connect() as conn:
        context = MigrationContext.configure(conn)
        return context.get_current_revision()


def get_table_names(sync_engine: Engine) -> set[str]:
    """Get all table names from the database.

    Args:
        sync_engine: Synchronous SQLAlchemy engine.

    Returns:
        Set of table names.
    """
    inspector = inspect(sync_engine)
    return set(inspector.get_table_names())


def get_index_names(sync_engine: Engine, table_name: str) -> set[str]:
    """Get all index names for a specific table.

    Args:
        sync_engine: Synchronous SQLAlchemy engine.
        table_name: Name of the table to inspect.

    Returns:
        Set of index names for the table.
    """
    inspector = inspect(sync_engine)
    try:
        indexes = inspector.get_indexes(table_name)
        return {idx["name"] for idx in indexes}
    except ProgrammingError:
        # Table doesn't exist
        return set()


def table_exists(sync_engine: Engine, table_name: str) -> bool:
    """Check if a table exists in the database.

    Args:
        sync_engine: Synchronous SQLAlchemy engine.
        table_name: Name of the table to check.

    Returns:
        True if table exists, False otherwise.
    """
    return table_name in get_table_names(sync_engine)


class TestMigrationForwardExecution:
    """Tests for forward migration execution (upgrade)."""

    @pytest.mark.asyncio
    async def test_upgrade_to_head_creates_all_tables(
        self, alembic_config: Config, sync_engine: Engine
    ) -> None:
        """Test that upgrading to head creates all expected tables."""
        # Start from clean slate
        command.downgrade(alembic_config, "base")

        # Upgrade to head
        command.upgrade(alembic_config, "head")

        # Verify core tables exist
        tables = get_table_names(sync_engine)
        expected_tables = {
            "cameras",
            "detections",
            "events",
            "gpu_stats",
            "logs",
            "alembic_version",
        }

        for table in expected_tables:
            assert table in tables, f"Table '{table}' not created by migrations"

    @pytest.mark.asyncio
    async def test_upgrade_sets_correct_revision(
        self, alembic_config: Config, sync_engine: Engine
    ) -> None:
        """Test that upgrade sets the correct revision in alembic_version."""
        # Get expected head revision
        script = ScriptDirectory.from_config(alembic_config)
        expected_head = script.get_current_head()

        # Upgrade to head
        command.upgrade(alembic_config, "head")

        # Verify current revision matches head
        current_rev = get_current_revision(sync_engine)
        assert current_rev == expected_head, f"Expected {expected_head}, got {current_rev}"

    @pytest.mark.asyncio
    async def test_upgrade_creates_indexes(
        self, alembic_config: Config, sync_engine: Engine
    ) -> None:
        """Test that upgrade creates expected indexes."""
        # Upgrade to head
        command.upgrade(alembic_config, "head")

        # Check for expected indexes on detections table
        detection_indexes = get_index_names(sync_engine, "detections")
        expected_patterns = ["idx_detections_camera_id", "idx_detections_camera_time"]

        for pattern in expected_patterns:
            matching = [idx for idx in detection_indexes if pattern in idx.lower()]
            assert len(matching) >= 1, f"No index matching '{pattern}' found"


class TestMigrationDowngrade:
    """Tests for migration rollback (downgrade) execution."""

    @pytest.mark.asyncio
    async def test_downgrade_to_base_removes_all_tables(
        self, alembic_config: Config, sync_engine: Engine
    ) -> None:
        """Test that downgrading to base removes all application tables."""
        # Ensure we start from head
        command.upgrade(alembic_config, "head")

        # Verify tables exist
        tables_before = get_table_names(sync_engine)
        assert "cameras" in tables_before

        # Downgrade to base
        command.downgrade(alembic_config, "base")

        # Verify application tables are removed
        tables_after = get_table_names(sync_engine)
        app_tables = tables_after - {"alembic_version"}

        assert len(app_tables) == 0, f"Tables remain after downgrade: {app_tables}"

    @pytest.mark.asyncio
    async def test_downgrade_updates_revision_tracking(
        self, alembic_config: Config, sync_engine: Engine
    ) -> None:
        """Test that downgrade correctly updates alembic_version table."""
        # Upgrade to head first
        command.upgrade(alembic_config, "head")

        # Get the script directory
        script = ScriptDirectory.from_config(alembic_config)

        # Get all revisions in order
        revisions = list(script.walk_revisions())
        if len(revisions) < 2:
            pytest.skip("Need at least 2 migrations for this test")

        # Downgrade by 1 step
        command.downgrade(alembic_config, "-1")

        # Verify revision was updated
        current_rev = get_current_revision(sync_engine)

        # Current revision should be the second-to-last migration
        # (since we downgraded from head by 1)
        expected_rev = revisions[1].revision
        assert current_rev == expected_rev, f"Expected {expected_rev}, got {current_rev}"

    @pytest.mark.asyncio
    async def test_downgrade_removes_indexes(
        self, alembic_config: Config, sync_engine: Engine
    ) -> None:
        """Test that downgrade properly removes indexes created in migrations."""
        # Upgrade to head
        command.upgrade(alembic_config, "head")

        # Verify indexes exist
        if table_exists(sync_engine, "detections"):
            detection_indexes_before = get_index_names(sync_engine, "detections")
            assert len(detection_indexes_before) > 0, "No indexes found on detections table"

        # Downgrade to base
        command.downgrade(alembic_config, "base")

        # Verify table and indexes are removed
        assert not table_exists(sync_engine, "detections"), (
            "detections table still exists after downgrade"
        )


class TestDataPreservationDuringRollback:
    """Tests for data preservation/handling during migration rollback."""

    @pytest.mark.asyncio
    async def test_downgrade_handles_data_dependent_operations(
        self, alembic_config: Config, sync_engine: Engine
    ) -> None:
        """Test that downgrade can handle tables with data.

        This test verifies that the downgrade logic properly handles:
        - Foreign key constraints during table drops
        - Cascade deletes where appropriate
        - Proper order of operations
        """
        # Upgrade to head
        command.upgrade(alembic_config, "head")

        # Insert test data to verify cascade behavior
        with sync_engine.connect() as conn:
            # Insert a camera
            conn.execute(
                text(
                    """
                INSERT INTO cameras (id, name, folder_path, status, created_at)
                VALUES ('test_cam', 'Test Camera', '/test/path', 'active', NOW())
                """
                )
            )

            # Insert a detection for the camera
            conn.execute(
                text(
                    """
                INSERT INTO detections (camera_id, file_path, detected_at, object_type, confidence)
                VALUES ('test_cam', '/test/image.jpg', NOW(), 'person', 0.95)
                """
                )
            )

            conn.commit()

        # Verify data exists
        with sync_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM cameras"))
            camera_count = result.scalar()
            assert camera_count == 1, "Camera not inserted"

            result = conn.execute(text("SELECT COUNT(*) FROM detections"))
            detection_count = result.scalar()
            assert detection_count == 1, "Detection not inserted"

        # Downgrade should succeed even with data present
        command.downgrade(alembic_config, "base")

        # Verify tables are removed
        assert not table_exists(sync_engine, "cameras")
        assert not table_exists(sync_engine, "detections")

    @pytest.mark.asyncio
    async def test_partial_downgrade_preserves_earlier_migration_data(
        self, alembic_config: Config, sync_engine: Engine
    ) -> None:
        """Test that partial downgrade preserves data from earlier migrations.

        This test verifies that when rolling back to a specific revision,
        data created by that revision is preserved.
        """
        # Get the script directory
        script = ScriptDirectory.from_config(alembic_config)
        revisions = list(script.walk_revisions())

        if len(revisions) < 2:
            pytest.skip("Need at least 2 migrations for this test")

        # Upgrade to head
        command.upgrade(alembic_config, "head")

        # Insert test data
        with sync_engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO cameras (id, name, folder_path, status, created_at)
                VALUES ('test_cam', 'Test Camera', '/test/path', 'active', NOW())
                """
                )
            )
            conn.commit()

        # Get the second-to-last revision (one before head)
        target_revision = revisions[1].revision

        # Downgrade to that revision
        command.downgrade(alembic_config, target_revision)

        # Verify we're at the target revision
        current_rev = get_current_revision(sync_engine)
        assert current_rev == target_revision

        # If the cameras table still exists at this revision, data should be preserved
        if table_exists(sync_engine, "cameras"):
            with sync_engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM cameras"))
                camera_count = result.scalar()
                assert camera_count == 1, "Data was lost during partial downgrade"


class TestSchemaStateVerification:
    """Tests for verifying schema state after migrations and rollbacks."""

    @pytest.mark.asyncio
    async def test_upgrade_then_downgrade_returns_to_base_state(
        self, alembic_config: Config, sync_engine: Engine
    ) -> None:
        """Test that upgrade followed by full downgrade returns to base state."""
        # Start from base
        command.downgrade(alembic_config, "base")

        # Get base state (should only have alembic_version)
        base_tables = get_table_names(sync_engine)
        assert base_tables <= {"alembic_version"}, "Unexpected tables in base state"

        # Upgrade to head
        command.upgrade(alembic_config, "head")

        # Verify tables were created
        head_tables = get_table_names(sync_engine)
        assert len(head_tables) > 1, "No tables created during upgrade"

        # Downgrade back to base
        command.downgrade(alembic_config, "base")

        # Verify we're back to base state
        final_tables = get_table_names(sync_engine)
        assert final_tables == base_tables, "State differs after round-trip migration"

    @pytest.mark.asyncio
    async def test_multiple_downgrade_steps_maintain_consistency(
        self, alembic_config: Config, sync_engine: Engine
    ) -> None:
        """Test that multiple downgrade steps maintain database consistency."""
        script = ScriptDirectory.from_config(alembic_config)
        revisions = list(script.walk_revisions())

        if len(revisions) < 3:
            pytest.skip("Need at least 3 migrations for this test")

        # Upgrade to head
        command.upgrade(alembic_config, "head")

        # Record the head revision
        head_revision = get_current_revision(sync_engine)

        # Downgrade step by step
        for i in range(min(3, len(revisions))):
            command.downgrade(alembic_config, "-1")

            # Verify revision tracking is correct
            current_rev = get_current_revision(sync_engine)

            # If we're not at base, verify revision is tracked
            if current_rev is not None:
                # Verify the revision exists in our script directory
                rev = script.get_revision(current_rev)
                assert rev is not None, f"Unknown revision: {current_rev}"

                # Verify revision is earlier than head
                assert current_rev != head_revision or i == 0

    @pytest.mark.asyncio
    async def test_downgrade_with_dependent_foreign_keys(
        self, alembic_config: Config, sync_engine: Engine
    ) -> None:
        """Test that downgrade handles foreign key dependencies correctly."""
        # Upgrade to head
        command.upgrade(alembic_config, "head")

        # Verify foreign key relationships exist
        inspector = inspect(sync_engine)

        # Check detections table has foreign key to cameras
        if table_exists(sync_engine, "detections"):
            fkeys = inspector.get_foreign_keys("detections")
            camera_fkeys = [fk for fk in fkeys if fk["referred_table"] == "cameras"]
            assert len(camera_fkeys) > 0, "No foreign key from detections to cameras"

        # Downgrade should handle foreign keys correctly (drop in proper order)
        command.downgrade(alembic_config, "base")

        # Verify both tables are removed
        assert not table_exists(sync_engine, "detections")
        assert not table_exists(sync_engine, "cameras")


class TestMultipleStepRollback:
    """Tests for multi-step rollback scenarios."""

    @pytest.mark.asyncio
    async def test_downgrade_multiple_steps_at_once(
        self, alembic_config: Config, sync_engine: Engine
    ) -> None:
        """Test downgrading multiple migrations in a single operation."""
        script = ScriptDirectory.from_config(alembic_config)
        revisions = list(script.walk_revisions())

        if len(revisions) < 3:
            pytest.skip("Need at least 3 migrations for this test")

        # Upgrade to head
        command.upgrade(alembic_config, "head")

        # Get the third-to-last revision
        target_revision = revisions[2].revision

        # Downgrade directly to target (skipping intermediate revisions)
        command.downgrade(alembic_config, target_revision)

        # Verify we ended up at the correct revision
        current_rev = get_current_revision(sync_engine)
        assert current_rev == target_revision

    @pytest.mark.asyncio
    async def test_downgrade_by_relative_number(
        self, alembic_config: Config, sync_engine: Engine
    ) -> None:
        """Test downgrading by a relative number of steps (e.g., -2)."""
        script = ScriptDirectory.from_config(alembic_config)
        revisions = list(script.walk_revisions())

        if len(revisions) < 3:
            pytest.skip("Need at least 3 migrations for this test")

        # Upgrade to head
        command.upgrade(alembic_config, "head")

        # Downgrade by 2 steps
        command.downgrade(alembic_config, "-2")

        # Verify we're at the correct revision
        current_rev = get_current_revision(sync_engine)
        expected_rev = revisions[2].revision

        assert current_rev == expected_rev, f"Expected {expected_rev}, got {current_rev}"

    @pytest.mark.asyncio
    async def test_upgrade_after_partial_downgrade(
        self, alembic_config: Config, sync_engine: Engine
    ) -> None:
        """Test that we can upgrade again after a partial downgrade."""
        script = ScriptDirectory.from_config(alembic_config)
        revisions = list(script.walk_revisions())

        if len(revisions) < 2:
            pytest.skip("Need at least 2 migrations for this test")

        # Upgrade to head
        command.upgrade(alembic_config, "head")
        head_revision = get_current_revision(sync_engine)

        # Downgrade by 1 step
        command.downgrade(alembic_config, "-1")
        intermediate_rev = get_current_revision(sync_engine)
        assert intermediate_rev != head_revision

        # Upgrade back to head
        command.upgrade(alembic_config, "head")
        final_rev = get_current_revision(sync_engine)

        assert final_rev == head_revision, "Failed to return to head after downgrade"


class TestMigrationErrorHandling:
    """Tests for error handling during migrations."""

    @pytest.mark.asyncio
    async def test_downgrade_from_base_is_noop(
        self, alembic_config: Config, sync_engine: Engine
    ) -> None:
        """Test that downgrading from base state doesn't cause errors."""
        # Start from base
        command.downgrade(alembic_config, "base")

        # Try to downgrade again (should be a no-op)
        command.downgrade(alembic_config, "base")

        # Verify we're still at base
        current_rev = get_current_revision(sync_engine)
        assert current_rev is None, "Revision tracking incorrect at base"

    @pytest.mark.asyncio
    async def test_upgrade_from_head_is_noop(
        self, alembic_config: Config, sync_engine: Engine
    ) -> None:
        """Test that upgrading from head doesn't cause errors."""
        # Upgrade to head
        command.upgrade(alembic_config, "head")
        head_rev = get_current_revision(sync_engine)

        # Try to upgrade again (should be a no-op)
        command.upgrade(alembic_config, "head")

        # Verify we're still at head
        current_rev = get_current_revision(sync_engine)
        assert current_rev == head_rev, "Revision changed during head upgrade"
