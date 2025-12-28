"""Unit tests for SQLite to PostgreSQL data migration script.

Tests cover:
- get_sqlite_url(): Environment variable handling and async URL stripping
- get_postgres_url(): Required env var validation and async URL stripping
- migrate_table(): Data migration between mock database sessions
- verify_counts(): Row count verification between databases
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Import the migration script module using importlib since it has hyphens in the name
script_path = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "scripts"
    / "migrate-sqlite-to-postgres.py"
)
spec = importlib.util.spec_from_file_location("migrate_sqlite_to_postgres", script_path)
migrate_module = importlib.util.module_from_spec(spec)
sys.modules["migrate_sqlite_to_postgres"] = migrate_module
spec.loader.exec_module(migrate_module)

# Import functions from the loaded module
get_sqlite_url = migrate_module.get_sqlite_url
get_postgres_url = migrate_module.get_postgres_url
migrate_table = migrate_module.migrate_table
verify_counts = migrate_module.verify_counts


class TestGetSqliteUrl:
    """Tests for get_sqlite_url() function."""

    def test_returns_default_url_when_env_var_not_set(self, monkeypatch):
        """Returns default URL when SQLITE_URL env var is not set."""
        monkeypatch.delenv("SQLITE_URL", raising=False)

        result = get_sqlite_url()

        assert result == "sqlite:///./backend/data/security.db"

    def test_strips_aiosqlite_from_async_urls(self, monkeypatch):
        """Strips +aiosqlite from async SQLite URLs."""
        monkeypatch.setenv("SQLITE_URL", "sqlite+aiosqlite:///./data/test.db")

        result = get_sqlite_url()

        assert result == "sqlite:///./data/test.db"
        assert "+aiosqlite" not in result

    def test_returns_env_var_value_when_set(self, monkeypatch):
        """Returns the SQLITE_URL env var value when set."""
        expected_url = "sqlite:///./custom/path/database.db"
        monkeypatch.setenv("SQLITE_URL", expected_url)

        result = get_sqlite_url()

        assert result == expected_url

    def test_handles_sync_url_without_modification(self, monkeypatch):
        """Does not modify sync SQLite URLs."""
        sync_url = "sqlite:///./data/sync.db"
        monkeypatch.setenv("SQLITE_URL", sync_url)

        result = get_sqlite_url()

        assert result == sync_url


class TestGetPostgresUrl:
    """Tests for get_postgres_url() function."""

    def test_exits_with_error_when_env_var_not_set(self, monkeypatch):
        """Exits with error when POSTGRES_URL env var is not set."""
        monkeypatch.delenv("POSTGRES_URL", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            get_postgres_url()

        assert exc_info.value.code == 1

    def test_strips_asyncpg_from_async_urls(self, monkeypatch):
        """Strips +asyncpg from async PostgreSQL URLs."""
        monkeypatch.setenv("POSTGRES_URL", "postgresql+asyncpg://user:pass@localhost:5432/dbname")

        result = get_postgres_url()

        assert result == "postgresql://user:pass@localhost:5432/dbname"
        assert "+asyncpg" not in result

    def test_returns_env_var_value_when_set(self, monkeypatch):
        """Returns the POSTGRES_URL env var value when set."""
        expected_url = "postgresql://user:pass@localhost:5432/testdb"
        monkeypatch.setenv("POSTGRES_URL", expected_url)

        result = get_postgres_url()

        assert result == expected_url

    def test_handles_sync_url_without_modification(self, monkeypatch):
        """Does not modify sync PostgreSQL URLs."""
        sync_url = "postgresql://user:pass@localhost/db"
        monkeypatch.setenv("POSTGRES_URL", sync_url)

        result = get_postgres_url()

        assert result == sync_url


class TestMigrateTable:
    """Tests for migrate_table() function."""

    def test_successfully_migrates_data_between_mock_sessions(self):
        """Successfully migrates data from SQLite to PostgreSQL sessions."""
        # Mock data to migrate
        mock_rows = [
            (1, "camera1", "/path/to/camera1"),
            (2, "camera2", "/path/to/camera2"),
            (3, "camera3", "/path/to/camera3"),
        ]
        columns = ["id", "name", "folder_path"]

        # Create mock SQLite session
        mock_sqlite_result = MagicMock()
        mock_sqlite_result.fetchall.return_value = mock_rows

        mock_sqlite_conn = MagicMock()
        mock_sqlite_conn.execute.return_value = mock_sqlite_result

        mock_sqlite_session = MagicMock(return_value=mock_sqlite_conn)

        # Create mock PostgreSQL session
        mock_postgres_conn = MagicMock()
        mock_postgres_session = MagicMock(return_value=mock_postgres_conn)

        # Execute migration
        result = migrate_table(
            mock_sqlite_session,
            mock_postgres_session,
            "cameras",
            columns,
        )

        # Verify SQLite was read
        mock_sqlite_conn.execute.assert_called_once()
        mock_sqlite_conn.close.assert_called_once()

        # Verify PostgreSQL was written to
        mock_postgres_conn.execute.assert_called_once()
        mock_postgres_conn.commit.assert_called_once()
        mock_postgres_conn.close.assert_called_once()

        # Verify return value
        assert result == 3

    def test_handles_empty_tables_correctly(self):
        """Handles empty tables without errors and returns 0."""
        columns = ["id", "name", "value"]

        # Mock empty result from SQLite
        mock_sqlite_result = MagicMock()
        mock_sqlite_result.fetchall.return_value = []

        mock_sqlite_conn = MagicMock()
        mock_sqlite_conn.execute.return_value = mock_sqlite_result

        mock_sqlite_session = MagicMock(return_value=mock_sqlite_conn)

        # PostgreSQL session should not be called for empty tables
        mock_postgres_session = MagicMock()

        # Execute migration
        result = migrate_table(
            mock_sqlite_session,
            mock_postgres_session,
            "empty_table",
            columns,
        )

        # Verify SQLite was read
        mock_sqlite_conn.execute.assert_called_once()
        mock_sqlite_conn.close.assert_called_once()

        # Verify PostgreSQL was NOT called (no data to insert)
        mock_postgres_session.assert_not_called()

        # Verify return value is 0
        assert result == 0

    def test_batches_large_datasets(self):
        """Batches large datasets into chunks of 1000 rows."""
        # Create 2500 rows to test batching (should result in 3 batches: 1000, 1000, 500)
        mock_rows = [(i, f"item_{i}") for i in range(2500)]
        columns = ["id", "name"]

        # Mock SQLite session
        mock_sqlite_result = MagicMock()
        mock_sqlite_result.fetchall.return_value = mock_rows

        mock_sqlite_conn = MagicMock()
        mock_sqlite_conn.execute.return_value = mock_sqlite_result

        mock_sqlite_session = MagicMock(return_value=mock_sqlite_conn)

        # Mock PostgreSQL session
        mock_postgres_conn = MagicMock()
        mock_postgres_session = MagicMock(return_value=mock_postgres_conn)

        # Execute migration
        result = migrate_table(
            mock_sqlite_session,
            mock_postgres_session,
            "large_table",
            columns,
        )

        # Verify PostgreSQL execute was called 3 times (for 3 batches)
        assert mock_postgres_conn.execute.call_count == 3

        # Verify commit was called once
        mock_postgres_conn.commit.assert_called_once()

        # Verify return value
        assert result == 2500

    def test_converts_rows_to_dicts_correctly(self):
        """Verifies rows are converted to dictionaries with correct column names."""
        mock_rows = [(1, "test_name", 100)]
        columns = ["id", "name", "value"]

        # Mock SQLite session
        mock_sqlite_result = MagicMock()
        mock_sqlite_result.fetchall.return_value = mock_rows

        mock_sqlite_conn = MagicMock()
        mock_sqlite_conn.execute.return_value = mock_sqlite_result

        mock_sqlite_session = MagicMock(return_value=mock_sqlite_conn)

        # Mock PostgreSQL session to capture the data
        mock_postgres_conn = MagicMock()
        mock_postgres_session = MagicMock(return_value=mock_postgres_conn)

        # Execute migration
        migrate_table(
            mock_sqlite_session,
            mock_postgres_session,
            "test_table",
            columns,
        )

        # Get the call arguments for the PostgreSQL execute
        call_args = mock_postgres_conn.execute.call_args
        # Second argument is the list of row dictionaries
        row_dicts = call_args[0][1]

        # Verify the dictionary has correct keys and values
        assert len(row_dicts) == 1
        assert row_dicts[0] == {"id": 1, "name": "test_name", "value": 100}


class TestVerifyCounts:
    """Tests for verify_counts() function."""

    def test_returns_true_when_counts_match(self):
        """Returns True when row counts match between databases."""
        # Mock SQLite session
        mock_sqlite_result = MagicMock()
        mock_sqlite_result.scalar.return_value = 100

        mock_sqlite_conn = MagicMock()
        mock_sqlite_conn.execute.return_value = mock_sqlite_result

        mock_sqlite_session = MagicMock(return_value=mock_sqlite_conn)

        # Mock PostgreSQL session with matching count
        mock_postgres_result = MagicMock()
        mock_postgres_result.scalar.return_value = 100

        mock_postgres_conn = MagicMock()
        mock_postgres_conn.execute.return_value = mock_postgres_result

        mock_postgres_session = MagicMock(return_value=mock_postgres_conn)

        # Execute verification
        result = verify_counts(
            mock_sqlite_session,
            mock_postgres_session,
            "test_table",
        )

        # Verify result is True
        assert result is True

        # Verify both sessions were queried
        mock_sqlite_conn.execute.assert_called_once()
        mock_postgres_conn.execute.assert_called_once()

    def test_returns_false_when_counts_differ(self):
        """Returns False when row counts differ between databases."""
        # Mock SQLite session with 100 rows
        mock_sqlite_result = MagicMock()
        mock_sqlite_result.scalar.return_value = 100

        mock_sqlite_conn = MagicMock()
        mock_sqlite_conn.execute.return_value = mock_sqlite_result

        mock_sqlite_session = MagicMock(return_value=mock_sqlite_conn)

        # Mock PostgreSQL session with 50 rows (mismatch)
        mock_postgres_result = MagicMock()
        mock_postgres_result.scalar.return_value = 50

        mock_postgres_conn = MagicMock()
        mock_postgres_conn.execute.return_value = mock_postgres_result

        mock_postgres_session = MagicMock(return_value=mock_postgres_conn)

        # Execute verification
        result = verify_counts(
            mock_sqlite_session,
            mock_postgres_session,
            "test_table",
        )

        # Verify result is False
        assert result is False

    def test_handles_zero_counts(self):
        """Handles zero counts correctly (both empty tables should match)."""
        # Mock SQLite session with 0 rows
        mock_sqlite_result = MagicMock()
        mock_sqlite_result.scalar.return_value = 0

        mock_sqlite_conn = MagicMock()
        mock_sqlite_conn.execute.return_value = mock_sqlite_result

        mock_sqlite_session = MagicMock(return_value=mock_sqlite_conn)

        # Mock PostgreSQL session with 0 rows
        mock_postgres_result = MagicMock()
        mock_postgres_result.scalar.return_value = 0

        mock_postgres_conn = MagicMock()
        mock_postgres_conn.execute.return_value = mock_postgres_result

        mock_postgres_session = MagicMock(return_value=mock_postgres_conn)

        # Execute verification
        result = verify_counts(
            mock_sqlite_session,
            mock_postgres_session,
            "empty_table",
        )

        # Verify result is True (both have 0 rows)
        assert result is True

    def test_closes_connections_after_query(self):
        """Verifies that connections are properly closed after querying."""
        # Mock SQLite session
        mock_sqlite_result = MagicMock()
        mock_sqlite_result.scalar.return_value = 10

        mock_sqlite_conn = MagicMock()
        mock_sqlite_conn.execute.return_value = mock_sqlite_result

        mock_sqlite_session = MagicMock(return_value=mock_sqlite_conn)

        # Mock PostgreSQL session
        mock_postgres_result = MagicMock()
        mock_postgres_result.scalar.return_value = 10

        mock_postgres_conn = MagicMock()
        mock_postgres_conn.execute.return_value = mock_postgres_result

        mock_postgres_session = MagicMock(return_value=mock_postgres_conn)

        # Execute verification
        verify_counts(
            mock_sqlite_session,
            mock_postgres_session,
            "test_table",
        )

        # Verify both connections were closed
        mock_sqlite_conn.close.assert_called_once()
        mock_postgres_conn.close.assert_called_once()
