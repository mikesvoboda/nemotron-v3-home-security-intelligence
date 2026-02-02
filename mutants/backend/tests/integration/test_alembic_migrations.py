"""Integration tests for Alembic migrations with PostgreSQL support.

This module tests:
1. URL conversion from async to sync (asyncpg -> psycopg2)
2. Migration autogenerate (detects models)
3. Offline migration mode (generates SQL without connecting)

Note: This project only supports PostgreSQL. SQLite is not supported.
"""

from __future__ import annotations

import os
import sys
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from alembic import command

if TYPE_CHECKING:
    from collections.abc import Generator

    from testcontainers.postgres import PostgresContainer

# Add backend to path for imports
backend_path = Path(__file__).resolve().parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


def convert_async_url_to_sync(url: str | None) -> str | None:
    """Convert async database URLs to sync equivalents.

    This mirrors the logic in backend/alembic/env.py:get_database_url().
    We test this function directly instead of importing env.py which
    requires Alembic's runtime context.

    Note: Only PostgreSQL is supported. SQLite URLs are not handled.

    Args:
        url: Database URL that may use async drivers.

    Returns:
        Converted URL with sync drivers, or None if input was None.
    """
    if url is None:
        return None

    # asyncpg -> psycopg2 (or just postgresql)
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "")

    return url


class TestUrlConversion:
    """Tests for the URL conversion logic used in alembic env.py."""

    def test_converts_asyncpg_to_sync(self) -> None:
        """Test that postgresql+asyncpg:// is converted to postgresql://."""
        url = "postgresql+asyncpg://user:pass@localhost:5432/mydb"
        result = convert_async_url_to_sync(url)
        assert result == "postgresql://user:pass@localhost:5432/mydb"
        assert "+asyncpg" not in result

    def test_preserves_plain_postgresql_url(self) -> None:
        """Test that plain postgresql:// URLs are preserved."""
        url = "postgresql://user:pass@localhost:5432/mydb"
        result = convert_async_url_to_sync(url)
        assert result == "postgresql://user:pass@localhost:5432/mydb"

    def test_handles_none_input(self) -> None:
        """Test that None input returns None."""
        result = convert_async_url_to_sync(None)
        assert result is None

    def test_handles_url_with_query_params(self) -> None:
        """Test URL conversion preserves query parameters."""
        url = "postgresql+asyncpg://user:pass@localhost:5432/mydb?sslmode=require"
        result = convert_async_url_to_sync(url)
        assert result == "postgresql://user:pass@localhost:5432/mydb?sslmode=require"
        assert "+asyncpg" not in result

    def test_handles_url_with_special_characters_in_password(self) -> None:
        """Test URL conversion handles special characters in password."""
        url = "postgresql+asyncpg://user:p%40ss%3Aword@localhost:5432/mydb"
        result = convert_async_url_to_sync(url)
        assert result == "postgresql://user:p%40ss%3Aword@localhost:5432/mydb"
        assert "+asyncpg" not in result

    def test_handles_unix_socket_url(self) -> None:
        """Test URL conversion handles Unix socket connections."""
        url = "postgresql+asyncpg://user:pass@/mydb?host=/var/run/postgresql"
        result = convert_async_url_to_sync(url)
        assert result == "postgresql://user:pass@/mydb?host=/var/run/postgresql"
        assert "+asyncpg" not in result


class TestMigrationAutogenerate:
    """Tests for migration autogenerate functionality."""

    @pytest.fixture
    def alembic_config(self, tmp_path: Path) -> Config:
        """Create a test Alembic config for testing script metadata.

        Note: This fixture uses the default PostgreSQL URL from alembic.ini.
        Tests that don't require database connectivity work fine.
        Tests that need a live database connection are skipped (PostgreSQL-only).
        """
        # Find the alembic.ini file
        alembic_ini = backend_path / "alembic.ini"
        config = Config(str(alembic_ini))
        return config

    def test_script_directory_has_versions(self) -> None:
        """Test that the script directory contains migration versions."""
        alembic_ini = backend_path / "alembic.ini"
        config = Config(str(alembic_ini))

        script = ScriptDirectory.from_config(config)
        revisions = list(script.walk_revisions())

        # Should have at least the initial migration
        assert len(revisions) >= 1

    def test_target_metadata_contains_models(self) -> None:
        """Test that target_metadata includes our SQLAlchemy models.

        We verify this by checking the migration scripts themselves,
        which are generated from the metadata.
        """
        alembic_ini = backend_path / "alembic.ini"
        config = Config(str(alembic_ini))

        script = ScriptDirectory.from_config(config)

        # Get the head revision
        head = script.get_current_head()
        assert head is not None, "No migration head found"

        # Get the revision script and check it contains our tables
        rev = script.get_revision(head)
        assert rev is not None

        # Read the migration file content
        from backend.models.camera import Base

        # Check Base.metadata contains expected tables
        table_names = list(Base.metadata.tables.keys())

        expected_tables = {"cameras", "events", "detections", "gpu_stats"}
        for table in expected_tables:
            assert table in table_names, f"Table '{table}' not found in metadata"

    def test_initial_migration_exists(self) -> None:
        """Test that the initial migration script exists and has proper structure."""
        alembic_ini = backend_path / "alembic.ini"
        config = Config(str(alembic_ini))

        script = ScriptDirectory.from_config(config)

        # Get the head revision
        head = script.get_current_head()
        assert head is not None, "No migration head found"

        # Get the revision script
        rev = script.get_revision(head)
        assert rev is not None

        # Verify it has upgrade and downgrade functions
        module = rev.module
        assert hasattr(module, "upgrade"), "Migration missing upgrade function"
        assert hasattr(module, "downgrade"), "Migration missing downgrade function"


class TestOfflineMigrationMode:
    """Tests for offline migration mode (SQL generation without database connection).

    Uses PostgreSQL dialect for SQL generation to match production environment.
    """

    @pytest.fixture
    def alembic_config(self) -> Config:
        """Create a test Alembic config for offline mode with PostgreSQL."""
        alembic_ini = backend_path / "alembic.ini"
        config = Config(str(alembic_ini))

        # Set a PostgreSQL URL for offline testing (won't connect, just for dialect)
        config.set_main_option(
            "sqlalchemy.url", "postgresql://user:pass@localhost:5432/offline_test"
        )

        return config

    def test_offline_upgrade_generates_sql(self, alembic_config: Config) -> None:
        """Test that offline mode generates valid PostgreSQL SQL statements."""
        # Capture the SQL output
        sql_output = StringIO()
        alembic_config.output_buffer = sql_output

        # Run upgrade in offline mode (--sql flag equivalent)
        command.upgrade(alembic_config, "head", sql=True)

        # Get the generated SQL
        sql = sql_output.getvalue()

        # Verify SQL contains expected CREATE TABLE statements
        assert "CREATE TABLE" in sql.upper()
        assert "cameras" in sql.lower()
        assert "events" in sql.lower()
        assert "detections" in sql.lower()

    def test_offline_downgrade_generates_sql(self, alembic_config: Config) -> None:
        """Test that offline downgrade generates DROP TABLE statements."""
        # Get the head revision for the downgrade range
        script = ScriptDirectory.from_config(alembic_config)
        head = script.get_current_head()

        # Capture the SQL for downgrade
        sql_output = StringIO()
        alembic_config.output_buffer = sql_output

        # Run downgrade in offline mode from head to base
        # Offline mode requires explicit revision range
        command.downgrade(alembic_config, f"{head}:base", sql=True)

        # Get the generated SQL
        sql = sql_output.getvalue()

        # Verify SQL contains expected DROP TABLE statements
        assert "DROP TABLE" in sql.upper()

    def test_offline_mode_sql_contains_index_statements(self, alembic_config: Config) -> None:
        """Test that offline SQL includes index creation."""
        sql_output = StringIO()
        alembic_config.output_buffer = sql_output

        command.upgrade(alembic_config, "head", sql=True)

        sql = sql_output.getvalue()

        # Verify indexes are created
        assert "CREATE INDEX" in sql.upper()


@pytest.mark.integration
class TestMigrationUpgradeDowngrade:
    """Tests for migration upgrade/downgrade operations using PostgreSQL testcontainers.

    These tests verify that Alembic migrations work correctly with a real PostgreSQL database,
    matching the production environment.
    """

    @pytest.fixture(scope="class")
    def postgres_container(self) -> "Generator[PostgresContainer]":
        """Create a PostgreSQL testcontainer for migration testing."""
        from testcontainers.postgres import PostgresContainer

        with PostgresContainer("postgres:16", driver=None) as postgres:
            yield postgres

    @pytest.fixture
    def temp_db_config(self, postgres_container: "PostgresContainer") -> Config:
        """Create an Alembic config using the test PostgreSQL container."""
        alembic_ini = backend_path / "alembic.ini"
        config = Config(str(alembic_ini))

        # Get the connection URL from testcontainer
        # testcontainers returns psycopg2-compatible URL by default
        test_db_url = postgres_container.get_connection_url()
        config.set_main_option("sqlalchemy.url", test_db_url)

        return config

    def test_upgrade_to_head(self, temp_db_config: Config) -> None:
        """Test upgrading to the latest migration."""
        # Run upgrade to head
        command.upgrade(temp_db_config, "head")

        # Verify tables were created by checking the PostgreSQL database
        from sqlalchemy import create_engine, inspect

        engine = create_engine(temp_db_config.get_main_option("sqlalchemy.url"))
        inspector = inspect(engine)

        # Get list of tables
        tables = set(inspector.get_table_names())

        engine.dispose()

        # Check for expected tables
        expected_tables = {"cameras", "events", "detections", "gpu_stats", "alembic_version"}
        for table in expected_tables:
            assert table in tables, f"Table '{table}' not found after upgrade"

    def test_downgrade_to_base(self, temp_db_config: Config) -> None:
        """Test downgrading to base (empty database)."""
        # First upgrade to head
        command.upgrade(temp_db_config, "head")

        # Then downgrade to base
        command.downgrade(temp_db_config, "base")

        # Verify tables were dropped
        from sqlalchemy import create_engine, inspect

        engine = create_engine(temp_db_config.get_main_option("sqlalchemy.url"))
        inspector = inspect(engine)

        tables = set(inspector.get_table_names())

        engine.dispose()

        # Only alembic_version should remain
        app_tables = tables - {"alembic_version"}
        assert len(app_tables) == 0, f"Tables remain after downgrade: {app_tables}"

    def test_current_revision_after_upgrade(self, temp_db_config: Config) -> None:
        """Test that current revision is correctly tracked after upgrade."""
        # Upgrade to head
        command.upgrade(temp_db_config, "head")

        # Get the script directory
        script = ScriptDirectory.from_config(temp_db_config)
        head = script.get_current_head()

        # Verify the database has the correct revision
        from sqlalchemy import create_engine

        engine = create_engine(temp_db_config.get_main_option("sqlalchemy.url"))

        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()

        engine.dispose()

        assert current_rev == head, f"Expected revision {head}, got {current_rev}"

    def test_migration_creates_indexes(self, temp_db_config: Config) -> None:
        """Test that migrations create the expected indexes."""
        command.upgrade(temp_db_config, "head")

        from sqlalchemy import create_engine, inspect

        engine = create_engine(temp_db_config.get_main_option("sqlalchemy.url"))
        inspector = inspect(engine)

        # Get all indexes from all tables
        all_indexes = set()
        for table_name in inspector.get_table_names():
            for index in inspector.get_indexes(table_name):
                all_indexes.add(index["name"])

        engine.dispose()

        # Check for expected indexes (some examples)
        expected_index_patterns = [
            "idx_detections_camera_id",
            "idx_events_started_at",
            "idx_gpu_stats_recorded_at",
        ]

        for pattern in expected_index_patterns:
            matching = [idx for idx in all_indexes if pattern in idx.lower()]
            assert len(matching) >= 1, f"No index matching '{pattern}' found. Indexes: {all_indexes}"

    def test_stepwise_upgrade_downgrade(self, temp_db_config: Config) -> None:
        """Test each migration can be upgraded and downgraded individually."""
        script = ScriptDirectory.from_config(temp_db_config)

        # Get all revisions in order
        revisions = list(script.walk_revisions("base", "heads"))
        # Reverse to get chronological order (base -> head)
        revisions.reverse()

        # Test upgrading to each revision
        for revision in revisions:
            command.upgrade(temp_db_config, revision.revision)

            # Verify we're at the expected revision
            from sqlalchemy import create_engine
            engine = create_engine(temp_db_config.get_main_option("sqlalchemy.url"))
            with engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current_rev = context.get_current_revision()
            engine.dispose()

            assert current_rev == revision.revision, (
                f"Expected revision {revision.revision}, got {current_rev}"
            )

        # Now test downgrading step by step
        for revision in reversed(revisions):
            if revision.down_revision:
                command.downgrade(temp_db_config, revision.down_revision)

                # Verify we're at the expected revision
                from sqlalchemy import create_engine
                engine = create_engine(temp_db_config.get_main_option("sqlalchemy.url"))
                with engine.connect() as conn:
                    context = MigrationContext.configure(conn)
                    current_rev = context.get_current_revision()
                engine.dispose()

                assert current_rev == revision.down_revision, (
                    f"Expected revision {revision.down_revision}, got {current_rev}"
                )

    def test_migration_idempotency(self, temp_db_config: Config) -> None:
        """Test that running the same migration twice is safe (idempotent)."""
        # Upgrade to head
        command.upgrade(temp_db_config, "head")

        # Get initial state
        from sqlalchemy import create_engine, inspect
        engine = create_engine(temp_db_config.get_main_option("sqlalchemy.url"))
        inspector = inspect(engine)
        initial_tables = set(inspector.get_table_names())
        engine.dispose()

        # Run upgrade again (should be no-op)
        command.upgrade(temp_db_config, "head")

        # Verify state hasn't changed
        engine = create_engine(temp_db_config.get_main_option("sqlalchemy.url"))
        inspector = inspect(engine)
        final_tables = set(inspector.get_table_names())
        engine.dispose()

        assert initial_tables == final_tables, (
            "Tables changed after re-running migration"
        )


class TestMigrationWithEnvironmentVariable:
    """Tests for migration behavior with DATABASE_URL environment variable."""

    @pytest.fixture(autouse=True)
    def setup_env(self) -> Generator[None]:
        """Save and restore DATABASE_URL environment variable."""
        original_url = os.environ.get("DATABASE_URL")
        yield
        if original_url is not None:
            os.environ["DATABASE_URL"] = original_url
        else:
            os.environ.pop("DATABASE_URL", None)

    @pytest.mark.skip(reason="SQLite not supported - PostgreSQL-only project")
    def test_migration_uses_env_url_when_set(self, tmp_path: Path) -> None:
        """Test that migrations use DATABASE_URL when set."""
        db_path = tmp_path / "env_test.db"
        # Use sync URL since Alembic doesn't use async drivers
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

        alembic_ini = backend_path / "alembic.ini"
        config = Config(str(alembic_ini))

        # Run upgrade - it should use the env var URL
        command.upgrade(config, "head")

        # Verify the database was created at the env var path
        assert db_path.exists(), "Database not created at DATABASE_URL path"

    @pytest.mark.skip(reason="SQLite not supported - PostgreSQL-only project")
    def test_migration_with_async_url_in_env(self, tmp_path: Path) -> None:
        """Test that async URLs in DATABASE_URL are converted.

        Alembic's env.py converts async URLs to sync before using them.
        """
        db_path = tmp_path / "async_env_test.db"
        # Set async URL - env.py should convert it
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

        alembic_ini = backend_path / "alembic.ini"
        config = Config(str(alembic_ini))

        # Run upgrade - env.py should convert the async URL to sync
        command.upgrade(config, "head")

        # Verify the database was created
        assert db_path.exists(), "Database not created with async URL in DATABASE_URL"
