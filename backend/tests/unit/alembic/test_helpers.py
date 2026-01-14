"""Unit tests for Alembic migration helper utilities.

Tests the helper functions and classes in backend/alembic/helpers.py:
- Pre-flight check functions (table_exists, column_exists, etc.)
- Safe operation functions (safe_table_rename, safe_column_add, etc.)
- Verification functions
- MigrationContext context manager
- Transaction helpers

Related Linear issue: NEM-2610
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.alembic.helpers import (
    MigrationContext,
    MigrationError,
    PreflightCheckError,
    RollbackError,
    VerificationError,
    column_exists,
    constraint_exists,
    ensure_transaction_savepoint,
    get_foreign_key_references,
    get_table_row_count,
    index_exists,
    is_partitioned_table,
    logged_operation,
    release_savepoint,
    rollback_to_savepoint,
    safe_column_add,
    safe_column_drop,
    safe_index_create,
    safe_index_drop,
    safe_table_drop,
    safe_table_rename,
    table_exists,
    verify_column_exists,
    verify_index_exists,
    verify_table_exists,
    verify_table_schema,
)


class TestExceptionClasses:
    """Test custom exception classes."""

    def test_migration_error(self) -> None:
        exc = MigrationError("Something failed")
        assert str(exc) == "Something failed"

    def test_preflight_check_error(self) -> None:
        exc = PreflightCheckError("Table not found")
        assert isinstance(exc, MigrationError)
        assert str(exc) == "Table not found"

    def test_verification_error(self) -> None:
        exc = VerificationError("Verification failed")
        assert isinstance(exc, MigrationError)
        assert str(exc) == "Verification failed"

    def test_rollback_error(self) -> None:
        exc = RollbackError("Rollback failed")
        assert isinstance(exc, MigrationError)
        assert str(exc) == "Rollback failed"


class TestTableExists:
    """Test table_exists function."""

    def test_table_exists_returns_true(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_conn.execute.return_value = mock_result

        result = table_exists(mock_conn, "users")

        assert result is True
        mock_conn.execute.assert_called_once()

    def test_table_exists_returns_false(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_conn.execute.return_value = mock_result

        result = table_exists(mock_conn, "nonexistent")

        assert result is False


class TestColumnExists:
    """Test column_exists function."""

    def test_column_exists_returns_true(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_conn.execute.return_value = mock_result

        result = column_exists(mock_conn, "users", "email")

        assert result is True

    def test_column_exists_returns_false(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_conn.execute.return_value = mock_result

        result = column_exists(mock_conn, "users", "nonexistent")

        assert result is False


class TestIndexExists:
    """Test index_exists function."""

    def test_index_exists_returns_true(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_conn.execute.return_value = mock_result

        result = index_exists(mock_conn, "idx_users_email")

        assert result is True

    def test_index_exists_returns_false(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_conn.execute.return_value = mock_result

        result = index_exists(mock_conn, "idx_nonexistent")

        assert result is False


class TestConstraintExists:
    """Test constraint_exists function."""

    def test_constraint_exists_returns_true(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_conn.execute.return_value = mock_result

        result = constraint_exists(mock_conn, "pk_users")

        assert result is True

    def test_constraint_exists_returns_false(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_conn.execute.return_value = mock_result

        result = constraint_exists(mock_conn, "pk_nonexistent")

        assert result is False


class TestIsPartitionedTable:
    """Test is_partitioned_table function."""

    def test_is_partitioned_returns_true(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = "p"
        mock_conn.execute.return_value = mock_result

        result = is_partitioned_table(mock_conn, "events")

        assert result is True

    def test_is_partitioned_returns_false_for_regular_table(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = "r"
        mock_conn.execute.return_value = mock_result

        result = is_partitioned_table(mock_conn, "users")

        assert result is False

    def test_is_partitioned_returns_false_for_none(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_conn.execute.return_value = mock_result

        result = is_partitioned_table(mock_conn, "nonexistent")

        assert result is False


class TestGetTableRowCount:
    """Test get_table_row_count function."""

    def test_get_table_row_count_positive(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1000
        mock_conn.execute.return_value = mock_result

        result = get_table_row_count(mock_conn, "users")

        assert result == 1000

    def test_get_table_row_count_zero(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_conn.execute.return_value = mock_result

        result = get_table_row_count(mock_conn, "empty_table")

        assert result == 0

    def test_get_table_row_count_negative_returns_zero(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = -1
        mock_conn.execute.return_value = mock_result

        result = get_table_row_count(mock_conn, "table")

        assert result == 0

    def test_get_table_row_count_none_returns_zero(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_conn.execute.return_value = mock_result

        result = get_table_row_count(mock_conn, "table")

        assert result == 0


class TestGetForeignKeyReferences:
    """Test get_foreign_key_references function."""

    def test_get_foreign_key_references_returns_refs(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("detections", "camera_id", "fk_detections_camera"),
            ("events", "camera_id", "fk_events_camera"),
        ]
        mock_conn.execute.return_value = mock_result

        result = get_foreign_key_references(mock_conn, "cameras")

        assert len(result) == 2
        assert result[0]["referencing_table"] == "detections"
        assert result[0]["referencing_column"] == "camera_id"
        assert result[0]["constraint_name"] == "fk_detections_camera"

    def test_get_foreign_key_references_empty(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result

        result = get_foreign_key_references(mock_conn, "standalone_table")

        assert result == []


class TestSafeTableRename:
    """Test safe_table_rename function."""

    def test_safe_table_rename_success(self) -> None:
        mock_conn = MagicMock()
        # Setup mock for table_exists checks
        mock_result_source = MagicMock()
        mock_result_source.scalar.return_value = True
        mock_result_target = MagicMock()
        mock_result_target.scalar.return_value = False
        mock_result_fk = MagicMock()
        mock_result_fk.fetchall.return_value = []
        mock_result_verify = MagicMock()
        mock_result_verify.scalar.return_value = True

        mock_conn.execute.side_effect = [
            mock_result_source,  # source exists
            mock_result_target,  # target doesn't exist
            mock_result_fk,  # no FK references
            MagicMock(),  # rename execution
            mock_result_verify,  # verification
        ]

        safe_table_rename(mock_conn, "old_table", "new_table")

        assert mock_conn.execute.call_count == 5

    def test_safe_table_rename_source_not_exists(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_conn.execute.return_value = mock_result

        with pytest.raises(PreflightCheckError, match="does not exist"):
            safe_table_rename(mock_conn, "nonexistent", "new_table")

    def test_safe_table_rename_target_exists(self) -> None:
        mock_conn = MagicMock()
        mock_result_source = MagicMock()
        mock_result_source.scalar.return_value = True
        mock_result_target = MagicMock()
        mock_result_target.scalar.return_value = True

        mock_conn.execute.side_effect = [
            mock_result_source,  # source exists
            mock_result_target,  # target exists
        ]

        with pytest.raises(PreflightCheckError, match="already exists"):
            safe_table_rename(mock_conn, "old_table", "existing_table")


class TestSafeColumnAdd:
    """Test safe_column_add function."""

    def test_safe_column_add_success(self) -> None:
        mock_conn = MagicMock()
        mock_table_exists = MagicMock()
        mock_table_exists.scalar.return_value = True
        mock_col_not_exists = MagicMock()
        mock_col_not_exists.scalar.return_value = False
        mock_col_exists = MagicMock()
        mock_col_exists.scalar.return_value = True

        mock_conn.execute.side_effect = [
            mock_table_exists,  # table exists
            mock_col_not_exists,  # column doesn't exist
            MagicMock(),  # add column
            mock_col_exists,  # verification
        ]

        safe_column_add(mock_conn, "users", "email", "VARCHAR(255)")

        assert mock_conn.execute.call_count == 4

    def test_safe_column_add_with_not_null_and_default(self) -> None:
        mock_conn = MagicMock()
        mock_table_exists = MagicMock()
        mock_table_exists.scalar.return_value = True
        mock_col_not_exists = MagicMock()
        mock_col_not_exists.scalar.return_value = False
        mock_col_exists = MagicMock()
        mock_col_exists.scalar.return_value = True

        mock_conn.execute.side_effect = [
            mock_table_exists,
            mock_col_not_exists,
            MagicMock(),
            mock_col_exists,
        ]

        safe_column_add(
            mock_conn, "users", "status", "VARCHAR(20)", nullable=False, default="'active'"
        )

        assert mock_conn.execute.call_count == 4

    def test_safe_column_add_table_not_exists(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_conn.execute.return_value = mock_result

        with pytest.raises(PreflightCheckError, match="does not exist"):
            safe_column_add(mock_conn, "nonexistent", "col", "VARCHAR(255)")

    def test_safe_column_add_column_already_exists(self) -> None:
        mock_conn = MagicMock()
        mock_table_exists = MagicMock()
        mock_table_exists.scalar.return_value = True
        mock_col_exists = MagicMock()
        mock_col_exists.scalar.return_value = True

        mock_conn.execute.side_effect = [mock_table_exists, mock_col_exists]

        # Should skip without error
        safe_column_add(mock_conn, "users", "email", "VARCHAR(255)")

        # Only 2 calls - table check and column check (skipped add)
        assert mock_conn.execute.call_count == 2


class TestSafeColumnDrop:
    """Test safe_column_drop function."""

    def test_safe_column_drop_success(self) -> None:
        mock_conn = MagicMock()
        mock_table_exists = MagicMock()
        mock_table_exists.scalar.return_value = True
        mock_col_exists = MagicMock()
        mock_col_exists.scalar.return_value = True
        mock_col_gone = MagicMock()
        mock_col_gone.scalar.return_value = False

        mock_conn.execute.side_effect = [
            mock_table_exists,  # table exists
            mock_col_exists,  # column exists
            MagicMock(),  # drop column
            mock_col_gone,  # verification
        ]

        safe_column_drop(mock_conn, "users", "email")

        assert mock_conn.execute.call_count == 4

    def test_safe_column_drop_table_not_exists(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_conn.execute.return_value = mock_result

        with pytest.raises(PreflightCheckError, match="does not exist"):
            safe_column_drop(mock_conn, "nonexistent", "col")

    def test_safe_column_drop_column_not_exists(self) -> None:
        mock_conn = MagicMock()
        mock_table_exists = MagicMock()
        mock_table_exists.scalar.return_value = True
        mock_col_not_exists = MagicMock()
        mock_col_not_exists.scalar.return_value = False

        mock_conn.execute.side_effect = [mock_table_exists, mock_col_not_exists]

        # Should skip without error
        safe_column_drop(mock_conn, "users", "nonexistent")

        assert mock_conn.execute.call_count == 2


class TestSafeIndexCreate:
    """Test safe_index_create function."""

    def test_safe_index_create_success(self) -> None:
        mock_conn = MagicMock()
        mock_table_exists = MagicMock()
        mock_table_exists.scalar.return_value = True
        mock_idx_not_exists = MagicMock()
        mock_idx_not_exists.scalar.return_value = False
        mock_idx_exists = MagicMock()
        mock_idx_exists.scalar.return_value = True

        mock_conn.execute.side_effect = [
            mock_table_exists,  # table exists
            mock_idx_not_exists,  # index doesn't exist
            MagicMock(),  # create index
            mock_idx_exists,  # verification
        ]

        safe_index_create(mock_conn, "idx_users_email", "users", ["email"])

        assert mock_conn.execute.call_count == 4

    def test_safe_index_create_with_options(self) -> None:
        mock_conn = MagicMock()
        mock_table_exists = MagicMock()
        mock_table_exists.scalar.return_value = True
        mock_idx_not_exists = MagicMock()
        mock_idx_not_exists.scalar.return_value = False
        mock_idx_exists = MagicMock()
        mock_idx_exists.scalar.return_value = True

        mock_conn.execute.side_effect = [
            mock_table_exists,
            mock_idx_not_exists,
            MagicMock(),
            mock_idx_exists,
        ]

        safe_index_create(
            mock_conn,
            "idx_users_active",
            "users",
            ["id"],
            unique=True,
            where_clause="deleted_at IS NULL",
            using="btree",
        )

        assert mock_conn.execute.call_count == 4

    def test_safe_index_create_table_not_exists(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_conn.execute.return_value = mock_result

        with pytest.raises(PreflightCheckError, match="does not exist"):
            safe_index_create(mock_conn, "idx_test", "nonexistent", ["col"])

    def test_safe_index_create_already_exists(self) -> None:
        mock_conn = MagicMock()
        mock_table_exists = MagicMock()
        mock_table_exists.scalar.return_value = True
        mock_idx_exists = MagicMock()
        mock_idx_exists.scalar.return_value = True

        mock_conn.execute.side_effect = [mock_table_exists, mock_idx_exists]

        # Should skip without error
        safe_index_create(mock_conn, "idx_test", "users", ["email"])

        assert mock_conn.execute.call_count == 2


class TestSafeIndexDrop:
    """Test safe_index_drop function."""

    def test_safe_index_drop_success(self) -> None:
        mock_conn = MagicMock()
        mock_idx_exists = MagicMock()
        mock_idx_exists.scalar.return_value = True
        mock_idx_gone = MagicMock()
        mock_idx_gone.scalar.return_value = False

        mock_conn.execute.side_effect = [
            mock_idx_exists,  # index exists
            MagicMock(),  # drop index
            mock_idx_gone,  # verification
        ]

        safe_index_drop(mock_conn, "idx_test")

        assert mock_conn.execute.call_count == 3

    def test_safe_index_drop_not_exists(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_conn.execute.return_value = mock_result

        # Should skip without error
        safe_index_drop(mock_conn, "nonexistent_idx")

        mock_conn.execute.assert_called_once()


class TestSafeTableDrop:
    """Test safe_table_drop function."""

    def test_safe_table_drop_success(self) -> None:
        mock_conn = MagicMock()
        mock_table_exists = MagicMock()
        mock_table_exists.scalar.return_value = True
        mock_fk_refs = MagicMock()
        mock_fk_refs.fetchall.return_value = []
        mock_table_gone = MagicMock()
        mock_table_gone.scalar.return_value = False

        mock_conn.execute.side_effect = [
            mock_table_exists,  # table exists
            mock_fk_refs,  # no FK references
            MagicMock(),  # drop table
            mock_table_gone,  # verification
        ]

        safe_table_drop(mock_conn, "test_table")

        assert mock_conn.execute.call_count == 4

    def test_safe_table_drop_with_cascade(self) -> None:
        mock_conn = MagicMock()
        mock_table_exists = MagicMock()
        mock_table_exists.scalar.return_value = True
        mock_table_gone = MagicMock()
        mock_table_gone.scalar.return_value = False

        mock_conn.execute.side_effect = [
            mock_table_exists,  # table exists
            MagicMock(),  # drop table with cascade
            mock_table_gone,  # verification
        ]

        safe_table_drop(mock_conn, "test_table", cascade=True)

        assert mock_conn.execute.call_count == 3

    def test_safe_table_drop_not_exists(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_conn.execute.return_value = mock_result

        # Should skip without error
        safe_table_drop(mock_conn, "nonexistent")

        mock_conn.execute.assert_called_once()

    def test_safe_table_drop_has_fk_references(self) -> None:
        mock_conn = MagicMock()
        mock_table_exists = MagicMock()
        mock_table_exists.scalar.return_value = True
        mock_fk_refs = MagicMock()
        mock_fk_refs.fetchall.return_value = [
            ("detections", "camera_id", "fk_det_camera"),
        ]

        mock_conn.execute.side_effect = [mock_table_exists, mock_fk_refs]

        with pytest.raises(PreflightCheckError, match="referenced by foreign keys"):
            safe_table_drop(mock_conn, "cameras")


class TestVerifyFunctions:
    """Test verification functions."""

    def test_verify_table_exists_passes(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_conn.execute.return_value = mock_result

        verify_table_exists(mock_conn, "users")  # Should not raise

    def test_verify_table_exists_fails(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_conn.execute.return_value = mock_result

        with pytest.raises(VerificationError, match="does not exist"):
            verify_table_exists(mock_conn, "nonexistent")

    def test_verify_column_exists_passes(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_conn.execute.return_value = mock_result

        verify_column_exists(mock_conn, "users", "email")  # Should not raise

    def test_verify_column_exists_fails(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_conn.execute.return_value = mock_result

        with pytest.raises(VerificationError, match="does not exist"):
            verify_column_exists(mock_conn, "users", "nonexistent")

    def test_verify_index_exists_passes(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_conn.execute.return_value = mock_result

        verify_index_exists(mock_conn, "idx_users_email")  # Should not raise

    def test_verify_index_exists_fails(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_conn.execute.return_value = mock_result

        with pytest.raises(VerificationError, match="does not exist"):
            verify_index_exists(mock_conn, "nonexistent_idx")

    def test_verify_table_schema_passes(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_conn.execute.return_value = mock_result

        verify_table_schema(mock_conn, "users", ["id", "email", "name"])

    def test_verify_table_schema_fails(self) -> None:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.side_effect = [True, True, False]  # id, email exist, name missing
        mock_conn.execute.return_value = mock_result

        with pytest.raises(VerificationError, match="missing columns"):
            verify_table_schema(mock_conn, "users", ["id", "email", "name"])


class TestMigrationContext:
    """Test MigrationContext context manager."""

    @patch("backend.alembic.helpers.op")
    def test_context_manager_basic(self, mock_op: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_op.get_bind.return_value = mock_conn

        with MigrationContext("test_migration") as ctx:
            assert ctx.connection is mock_conn
            assert ctx.migration_name == "test_migration"
            assert ctx.operations == []

    @patch("backend.alembic.helpers.op")
    def test_context_manager_records_operations(self, mock_op: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_op.get_bind.return_value = mock_conn

        # Setup mocks for table_exists
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_conn.execute.return_value = mock_result

        with MigrationContext("test_migration") as ctx:
            ctx.verify_table_exists("users")
            assert len(ctx.operations) == 1
            assert "verify_table" in ctx.operations[0]

    @patch("backend.alembic.helpers.op")
    def test_context_manager_logs_on_error(self, mock_op: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_op.get_bind.return_value = mock_conn

        # Setup mock to raise error
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_conn.execute.return_value = mock_result

        with pytest.raises(VerificationError):
            with MigrationContext("test_migration") as ctx:
                ctx.verify_table_exists("nonexistent")

    def test_context_manager_requires_with_statement(self) -> None:
        ctx = MigrationContext("test_migration")

        with pytest.raises(RuntimeError, match="context manager"):
            ctx._ensure_connection()

    @patch("backend.alembic.helpers.op")
    def test_context_manager_table_exists(self, mock_op: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_op.get_bind.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_conn.execute.return_value = mock_result

        with MigrationContext("test_migration") as ctx:
            result = ctx.table_exists("users")
            assert result is True

    @patch("backend.alembic.helpers.op")
    def test_context_manager_column_exists(self, mock_op: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_op.get_bind.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_conn.execute.return_value = mock_result

        with MigrationContext("test_migration") as ctx:
            result = ctx.column_exists("users", "email")
            assert result is True

    @patch("backend.alembic.helpers.op")
    def test_context_manager_index_exists(self, mock_op: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_op.get_bind.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_conn.execute.return_value = mock_result

        with MigrationContext("test_migration") as ctx:
            result = ctx.index_exists("idx_users_email")
            assert result is True

    @patch("backend.alembic.helpers.op")
    def test_context_manager_is_partitioned(self, mock_op: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_op.get_bind.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.scalar.return_value = "p"
        mock_conn.execute.return_value = mock_result

        with MigrationContext("test_migration") as ctx:
            result = ctx.is_partitioned_table("events")
            assert result is True

    @patch("backend.alembic.helpers.op")
    def test_context_manager_get_row_count(self, mock_op: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_op.get_bind.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.scalar.return_value = 1000
        mock_conn.execute.return_value = mock_result

        with MigrationContext("test_migration") as ctx:
            result = ctx.get_table_row_count("users")
            assert result == 1000

    @patch("backend.alembic.helpers.op")
    def test_context_manager_execute(self, mock_op: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_op.get_bind.return_value = mock_conn

        mock_result = MagicMock()
        mock_conn.execute.return_value = mock_result

        with MigrationContext("test_migration") as ctx:
            result = ctx.execute("SELECT 1")
            assert result is mock_result
            assert "execute_sql" in ctx.operations[0]


class TestLoggedOperation:
    """Test logged_operation context manager."""

    def test_logged_operation_success(self) -> None:
        with logged_operation("test_operation"):
            pass  # Operation succeeds

    def test_logged_operation_with_hint(self) -> None:
        with logged_operation("test_operation", rollback_hint="Run alembic downgrade"):
            pass  # Operation succeeds

    def test_logged_operation_integrity_error(self) -> None:
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(MigrationError, match="failed"):
            with logged_operation("test_operation"):
                raise IntegrityError("statement", {}, Exception())

    def test_logged_operation_operational_error(self) -> None:
        from sqlalchemy.exc import OperationalError

        with pytest.raises(MigrationError, match="failed"):
            with logged_operation("test_operation"):
                raise OperationalError("statement", {}, Exception())

    def test_logged_operation_programming_error(self) -> None:
        from sqlalchemy.exc import ProgrammingError

        with pytest.raises(MigrationError, match="failed"):
            with logged_operation("test_operation"):
                raise ProgrammingError("statement", {}, Exception())

    def test_logged_operation_sqlalchemy_error(self) -> None:
        from sqlalchemy.exc import SQLAlchemyError

        with pytest.raises(MigrationError, match="Database error"):
            with logged_operation("test_operation"):
                raise SQLAlchemyError()


class TestSavepointHelpers:
    """Test savepoint helper functions."""

    def test_ensure_transaction_savepoint(self) -> None:
        mock_conn = MagicMock()

        ensure_transaction_savepoint(mock_conn, "sp1")

        mock_conn.execute.assert_called_once()
        # Check that the text clause was passed (the actual SQL is in the TextClause)
        call_args = mock_conn.execute.call_args
        text_clause = call_args[0][0]
        assert "SAVEPOINT sp1" in str(text_clause.text)

    def test_rollback_to_savepoint(self) -> None:
        mock_conn = MagicMock()

        rollback_to_savepoint(mock_conn, "sp1")

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        text_clause = call_args[0][0]
        assert "ROLLBACK TO SAVEPOINT sp1" in str(text_clause.text)

    def test_release_savepoint(self) -> None:
        mock_conn = MagicMock()

        release_savepoint(mock_conn, "sp1")

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        text_clause = call_args[0][0]
        assert "RELEASE SAVEPOINT sp1" in str(text_clause.text)


class TestVerificationErrors:
    """Test verification error scenarios."""

    def test_safe_table_rename_verification_fails(self) -> None:
        mock_conn = MagicMock()
        mock_result_source_exists = MagicMock()
        mock_result_source_exists.scalar.return_value = True
        mock_result_target_not_exists = MagicMock()
        mock_result_target_not_exists.scalar.return_value = False
        mock_result_fk = MagicMock()
        mock_result_fk.fetchall.return_value = []
        mock_result_verify_fails = MagicMock()
        mock_result_verify_fails.scalar.return_value = False

        mock_conn.execute.side_effect = [
            mock_result_source_exists,  # source exists
            mock_result_target_not_exists,  # target doesn't exist
            mock_result_fk,  # no FK references
            MagicMock(),  # rename execution
            mock_result_verify_fails,  # verification fails
        ]

        with pytest.raises(VerificationError, match="verification failed"):
            safe_table_rename(mock_conn, "old_table", "new_table")

    def test_safe_column_add_verification_fails(self) -> None:
        mock_conn = MagicMock()
        mock_table_exists = MagicMock()
        mock_table_exists.scalar.return_value = True
        mock_col_not_exists = MagicMock()
        mock_col_not_exists.scalar.return_value = False
        mock_verify_fails = MagicMock()
        mock_verify_fails.scalar.return_value = False

        mock_conn.execute.side_effect = [
            mock_table_exists,  # table exists
            mock_col_not_exists,  # column doesn't exist
            MagicMock(),  # add column
            mock_verify_fails,  # verification fails
        ]

        with pytest.raises(VerificationError, match="verification failed"):
            safe_column_add(mock_conn, "users", "email", "VARCHAR(255)")

    def test_safe_column_drop_verification_fails(self) -> None:
        mock_conn = MagicMock()
        mock_table_exists = MagicMock()
        mock_table_exists.scalar.return_value = True
        mock_col_exists = MagicMock()
        mock_col_exists.scalar.return_value = True
        mock_verify_fails = MagicMock()
        mock_verify_fails.scalar.return_value = True  # Column still exists!

        mock_conn.execute.side_effect = [
            mock_table_exists,  # table exists
            mock_col_exists,  # column exists
            MagicMock(),  # drop column
            mock_verify_fails,  # verification fails - column still there
        ]

        with pytest.raises(VerificationError, match="verification failed"):
            safe_column_drop(mock_conn, "users", "email")

    def test_safe_index_drop_verification_fails(self) -> None:
        mock_conn = MagicMock()
        mock_idx_exists = MagicMock()
        mock_idx_exists.scalar.return_value = True
        mock_verify_fails = MagicMock()
        mock_verify_fails.scalar.return_value = True  # Index still exists!

        mock_conn.execute.side_effect = [
            mock_idx_exists,  # index exists
            MagicMock(),  # drop index
            mock_verify_fails,  # verification fails - index still there
        ]

        with pytest.raises(VerificationError, match="verification failed"):
            safe_index_drop(mock_conn, "idx_test")

    def test_safe_table_drop_verification_fails(self) -> None:
        mock_conn = MagicMock()
        mock_table_exists = MagicMock()
        mock_table_exists.scalar.return_value = True
        mock_fk_refs = MagicMock()
        mock_fk_refs.fetchall.return_value = []
        mock_verify_fails = MagicMock()
        mock_verify_fails.scalar.return_value = True  # Table still exists!

        mock_conn.execute.side_effect = [
            mock_table_exists,  # table exists
            mock_fk_refs,  # no FK references
            MagicMock(),  # drop table
            mock_verify_fails,  # verification fails - table still there
        ]

        with pytest.raises(VerificationError, match="verification failed"):
            safe_table_drop(mock_conn, "test_table")
