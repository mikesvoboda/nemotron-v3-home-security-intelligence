"""Migration helper utilities for safe database operations.

This module provides helper functions for Alembic migrations to ensure:
1. Pre-flight checks before destructive operations
2. Transaction management with proper rollback support
3. Verification steps after migration operations
4. Meaningful error logging throughout the process

Usage in migrations:
    from backend.alembic.helpers import (
        safe_table_rename,
        safe_column_add,
        verify_table_exists,
        MigrationContext,
    )

    def upgrade() -> None:
        with MigrationContext("my_migration") as ctx:
            if ctx.table_exists("old_table"):
                ctx.safe_table_rename("old_table", "new_table")
            ctx.verify_table_exists("new_table")

Related Linear issue: NEM-2610
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.exc import (
    IntegrityError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from sqlalchemy.engine import Connection

# Configure logging
logger = logging.getLogger("alembic.helpers")


class MigrationError(Exception):
    """Base exception for migration errors."""

    pass


class PreflightCheckError(MigrationError):
    """Raised when a pre-flight check fails."""

    pass


class VerificationError(MigrationError):
    """Raised when post-migration verification fails."""

    pass


class RollbackError(MigrationError):
    """Raised when a rollback operation fails."""

    pass


# =============================================================================
# Pre-flight Check Functions
# =============================================================================


def table_exists(connection: Connection, table_name: str) -> bool:
    """Check if a table exists in the database.

    Args:
        connection: SQLAlchemy connection object.
        table_name: Name of the table to check.

    Returns:
        True if table exists, False otherwise.
    """
    result = connection.execute(
        text(
            "SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = :name)"
        ),
        {"name": table_name},
    )
    return bool(result.scalar())


def column_exists(connection: Connection, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table.

    Args:
        connection: SQLAlchemy connection object.
        table_name: Name of the table.
        column_name: Name of the column to check.

    Returns:
        True if column exists, False otherwise.
    """
    result = connection.execute(
        text(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = :table_name
                AND column_name = :column_name
            )
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return bool(result.scalar())


def index_exists(connection: Connection, index_name: str) -> bool:
    """Check if an index exists in the database.

    Args:
        connection: SQLAlchemy connection object.
        index_name: Name of the index to check.

    Returns:
        True if index exists, False otherwise.
    """
    result = connection.execute(
        text(
            "SELECT EXISTS (SELECT FROM pg_indexes WHERE schemaname = 'public' AND indexname = :name)"
        ),
        {"name": index_name},
    )
    return bool(result.scalar())


def constraint_exists(connection: Connection, constraint_name: str) -> bool:
    """Check if a constraint exists in the database.

    Args:
        connection: SQLAlchemy connection object.
        constraint_name: Name of the constraint to check.

    Returns:
        True if constraint exists, False otherwise.
    """
    result = connection.execute(
        text(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.table_constraints
                WHERE constraint_schema = 'public'
                AND constraint_name = :name
            )
            """
        ),
        {"name": constraint_name},
    )
    return bool(result.scalar())


def is_partitioned_table(connection: Connection, table_name: str) -> bool:
    """Check if a table is partitioned.

    Args:
        connection: SQLAlchemy connection object.
        table_name: Name of the table to check.

    Returns:
        True if table is partitioned, False otherwise.
    """
    result = connection.execute(
        text("SELECT relkind FROM pg_class WHERE relname = :name"),
        {"name": table_name},
    )
    relkind = result.scalar()
    return relkind == "p"


def get_table_row_count(connection: Connection, table_name: str) -> int:
    """Get the approximate row count of a table.

    Uses pg_stat_user_tables for fast approximate count on large tables.

    Args:
        connection: SQLAlchemy connection object.
        table_name: Name of the table.

    Returns:
        Approximate number of rows in the table.
    """
    result = connection.execute(
        text(
            """
            SELECT reltuples::bigint AS estimate
            FROM pg_class
            WHERE relname = :name
            """
        ),
        {"name": table_name},
    )
    count = result.scalar()
    return int(count) if count and count > 0 else 0


def get_foreign_key_references(connection: Connection, table_name: str) -> list[dict[str, Any]]:
    """Get all foreign keys that reference a table.

    Args:
        connection: SQLAlchemy connection object.
        table_name: Name of the table to check references for.

    Returns:
        List of dicts with constraint info (table, column, constraint name).
    """
    result = connection.execute(
        text(
            """
            SELECT
                tc.table_name AS referencing_table,
                kcu.column_name AS referencing_column,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND ccu.table_name = :table_name
            AND tc.table_schema = 'public'
            """
        ),
        {"table_name": table_name},
    )
    return [
        {
            "referencing_table": row[0],
            "referencing_column": row[1],
            "constraint_name": row[2],
        }
        for row in result.fetchall()
    ]


# =============================================================================
# Safe Operation Functions
# =============================================================================


def safe_table_rename(connection: Connection, old_name: str, new_name: str) -> None:
    """Safely rename a table with existence checks.

    Args:
        connection: SQLAlchemy connection object.
        old_name: Current name of the table.
        new_name: New name for the table.

    Raises:
        PreflightCheckError: If source table doesn't exist or target exists.
    """
    logger.info(f"Attempting to rename table '{old_name}' to '{new_name}'")

    # Pre-flight check: source must exist
    if not table_exists(connection, old_name):
        raise PreflightCheckError(f"Source table '{old_name}' does not exist")

    # Pre-flight check: target must not exist
    if table_exists(connection, new_name):
        raise PreflightCheckError(f"Target table '{new_name}' already exists")

    # Check for foreign key references
    fk_refs = get_foreign_key_references(connection, old_name)
    if fk_refs:
        ref_tables = [ref["referencing_table"] for ref in fk_refs]
        logger.warning(f"Table '{old_name}' is referenced by foreign keys from: {ref_tables}")

    # Perform the rename (identifiers are validated above)
    connection.execute(text(f'ALTER TABLE "{old_name}" RENAME TO "{new_name}"'))

    # Verification
    if not table_exists(connection, new_name):
        raise VerificationError(f"Table rename verification failed: '{new_name}' not found")

    logger.info(f"Successfully renamed table '{old_name}' to '{new_name}'")


def safe_column_add(
    connection: Connection,
    table_name: str,
    column_name: str,
    column_type: str,
    nullable: bool = True,
    default: str | None = None,
) -> None:
    """Safely add a column with existence checks.

    Args:
        connection: SQLAlchemy connection object.
        table_name: Name of the table.
        column_name: Name of the column to add.
        column_type: SQL type for the column (e.g., 'VARCHAR(255)', 'INTEGER').
        nullable: Whether the column allows NULL values.
        default: Default value for the column (as SQL expression).

    Raises:
        PreflightCheckError: If table doesn't exist or column already exists.
    """
    logger.info(f"Attempting to add column '{column_name}' to table '{table_name}'")

    # Pre-flight check: table must exist
    if not table_exists(connection, table_name):
        raise PreflightCheckError(f"Table '{table_name}' does not exist")

    # Pre-flight check: column must not exist
    if column_exists(connection, table_name, column_name):
        logger.info(f"Column '{column_name}' already exists in '{table_name}', skipping")
        return

    # Build the ALTER TABLE statement
    null_constraint = "" if nullable else " NOT NULL"
    default_clause = f" DEFAULT {default}" if default else ""

    # Execute (identifiers validated above)
    connection.execute(
        text(
            f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" '
            f"{column_type}{null_constraint}{default_clause}"
        )
    )

    # Verification
    if not column_exists(connection, table_name, column_name):
        raise VerificationError(
            f"Column add verification failed: '{column_name}' not found in '{table_name}'"
        )

    logger.info(f"Successfully added column '{column_name}' to table '{table_name}'")


def safe_column_drop(connection: Connection, table_name: str, column_name: str) -> None:
    """Safely drop a column with existence checks.

    Args:
        connection: SQLAlchemy connection object.
        table_name: Name of the table.
        column_name: Name of the column to drop.

    Raises:
        PreflightCheckError: If table doesn't exist.
    """
    logger.info(f"Attempting to drop column '{column_name}' from table '{table_name}'")

    # Pre-flight check: table must exist
    if not table_exists(connection, table_name):
        raise PreflightCheckError(f"Table '{table_name}' does not exist")

    # If column doesn't exist, nothing to do
    if not column_exists(connection, table_name, column_name):
        logger.info(f"Column '{column_name}' doesn't exist in '{table_name}', skipping")
        return

    # Execute (identifiers validated above)
    connection.execute(text(f'ALTER TABLE "{table_name}" DROP COLUMN "{column_name}"'))

    # Verification
    if column_exists(connection, table_name, column_name):
        raise VerificationError(
            f"Column drop verification failed: '{column_name}' still exists in '{table_name}'"
        )

    logger.info(f"Successfully dropped column '{column_name}' from table '{table_name}'")


def safe_index_create(
    connection: Connection,
    index_name: str,
    table_name: str,
    columns: Sequence[str],
    unique: bool = False,
    where_clause: str | None = None,
    using: str | None = None,
    concurrently: bool = False,
) -> None:
    """Safely create an index with existence checks.

    Args:
        connection: SQLAlchemy connection object.
        index_name: Name for the index.
        table_name: Name of the table.
        columns: List of column names for the index.
        unique: Whether to create a unique index.
        where_clause: Optional WHERE clause for partial index.
        using: Index type (e.g., 'btree', 'gin', 'gist').
        concurrently: Whether to create index concurrently (non-blocking).

    Raises:
        PreflightCheckError: If table doesn't exist or index already exists.
    """
    logger.info(f"Attempting to create index '{index_name}' on '{table_name}'")

    # Pre-flight check: table must exist
    if not table_exists(connection, table_name):
        raise PreflightCheckError(f"Table '{table_name}' does not exist")

    # If index already exists, skip
    if index_exists(connection, index_name):
        logger.info(f"Index '{index_name}' already exists, skipping")
        return

    # Build the CREATE INDEX statement
    unique_clause = "UNIQUE " if unique else ""
    concurrent_clause = "CONCURRENTLY " if concurrently else ""
    using_clause = f" USING {using}" if using else ""
    column_list = ", ".join(f'"{col}"' for col in columns)
    where_part = f" WHERE {where_clause}" if where_clause else ""

    # Execute (identifiers validated above)
    connection.execute(
        text(
            f'CREATE {unique_clause}INDEX {concurrent_clause}"{index_name}" '
            f'ON "{table_name}"{using_clause} ({column_list}){where_part}'
        )
    )

    # For concurrent index creation, verify separately
    if not concurrently and not index_exists(connection, index_name):
        raise VerificationError(f"Index creation verification failed: '{index_name}' not found")

    logger.info(f"Successfully created index '{index_name}' on '{table_name}'")


def safe_index_drop(connection: Connection, index_name: str) -> None:
    """Safely drop an index with existence checks.

    Args:
        connection: SQLAlchemy connection object.
        index_name: Name of the index to drop.
    """
    logger.info(f"Attempting to drop index '{index_name}'")

    # If index doesn't exist, nothing to do
    if not index_exists(connection, index_name):
        logger.info(f"Index '{index_name}' doesn't exist, skipping")
        return

    # Execute (identifier validated above)
    connection.execute(text(f'DROP INDEX IF EXISTS "{index_name}"'))

    # Verification
    if index_exists(connection, index_name):
        raise VerificationError(f"Index drop verification failed: '{index_name}' still exists")

    logger.info(f"Successfully dropped index '{index_name}'")


def safe_table_drop(connection: Connection, table_name: str, cascade: bool = False) -> None:
    """Safely drop a table with existence checks.

    Args:
        connection: SQLAlchemy connection object.
        table_name: Name of the table to drop.
        cascade: Whether to cascade drop to dependent objects.

    Raises:
        PreflightCheckError: If table has foreign key references and cascade is False.
    """
    logger.info(f"Attempting to drop table '{table_name}'")

    # If table doesn't exist, nothing to do
    if not table_exists(connection, table_name):
        logger.info(f"Table '{table_name}' doesn't exist, skipping")
        return

    # Check for foreign key references
    if not cascade:
        fk_refs = get_foreign_key_references(connection, table_name)
        if fk_refs:
            ref_tables = [ref["referencing_table"] for ref in fk_refs]
            raise PreflightCheckError(
                f"Table '{table_name}' is referenced by foreign keys from: {ref_tables}. "
                f"Use cascade=True to drop anyway."
            )

    cascade_clause = " CASCADE" if cascade else ""

    # Execute (identifier validated above)
    connection.execute(text(f'DROP TABLE IF EXISTS "{table_name}"{cascade_clause}'))

    # Verification
    if table_exists(connection, table_name):
        raise VerificationError(f"Table drop verification failed: '{table_name}' still exists")

    logger.info(f"Successfully dropped table '{table_name}'")


# =============================================================================
# Verification Functions
# =============================================================================


def verify_table_exists(connection: Connection, table_name: str) -> None:
    """Verify that a table exists.

    Args:
        connection: SQLAlchemy connection object.
        table_name: Name of the table to verify.

    Raises:
        VerificationError: If table does not exist.
    """
    if not table_exists(connection, table_name):
        raise VerificationError(f"Verification failed: table '{table_name}' does not exist")


def verify_column_exists(connection: Connection, table_name: str, column_name: str) -> None:
    """Verify that a column exists in a table.

    Args:
        connection: SQLAlchemy connection object.
        table_name: Name of the table.
        column_name: Name of the column to verify.

    Raises:
        VerificationError: If column does not exist.
    """
    if not column_exists(connection, table_name, column_name):
        raise VerificationError(
            f"Verification failed: column '{column_name}' does not exist in '{table_name}'"
        )


def verify_index_exists(connection: Connection, index_name: str) -> None:
    """Verify that an index exists.

    Args:
        connection: SQLAlchemy connection object.
        index_name: Name of the index to verify.

    Raises:
        VerificationError: If index does not exist.
    """
    if not index_exists(connection, index_name):
        raise VerificationError(f"Verification failed: index '{index_name}' does not exist")


def verify_table_schema(
    connection: Connection,
    table_name: str,
    expected_columns: Sequence[str],
) -> None:
    """Verify that a table has the expected columns.

    Args:
        connection: SQLAlchemy connection object.
        table_name: Name of the table.
        expected_columns: List of column names that should exist.

    Raises:
        VerificationError: If any expected column is missing.
    """
    missing_columns = []
    for col in expected_columns:
        if not column_exists(connection, table_name, col):
            missing_columns.append(col)

    if missing_columns:
        raise VerificationError(
            f"Verification failed: table '{table_name}' is missing columns: {missing_columns}"
        )


# =============================================================================
# Migration Context Manager
# =============================================================================


class MigrationContext:
    """Context manager for safe migration operations with automatic rollback.

    This context manager provides:
    1. Automatic transaction management (if not in Alembic's transaction)
    2. Meaningful error logging
    3. Access to helper functions as methods
    4. Operation tracking for debugging

    Usage:
        def upgrade() -> None:
            with MigrationContext("add_user_email") as ctx:
                ctx.safe_column_add("users", "email", "VARCHAR(255)")
                ctx.verify_column_exists("users", "email")

    Attributes:
        migration_name: Name of the migration for logging.
        connection: SQLAlchemy connection object.
        operations: List of operations performed.
    """

    def __init__(self, migration_name: str) -> None:
        """Initialize the migration context.

        Args:
            migration_name: Name of the migration for logging purposes.
        """
        self.migration_name = migration_name
        self.connection: Connection | None = None
        self.operations: list[str] = []
        self._entered = False

    def __enter__(self) -> MigrationContext:
        """Enter the context and get the database connection.

        Returns:
            Self for method chaining.
        """
        self.connection = op.get_bind()
        self._entered = True
        logger.info(f"Starting migration: {self.migration_name}")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit the context, logging any errors.

        Args:
            exc_type: Exception type if an error occurred.
            exc_val: Exception value if an error occurred.
            exc_tb: Exception traceback if an error occurred.

        Note:
            Exceptions are not suppressed - Alembic handles rollback.
        """
        if exc_type is not None:
            logger.error(
                f"Migration '{self.migration_name}' failed: {exc_type.__name__}: {exc_val}"
            )
            logger.error(f"Operations completed before failure: {self.operations}")
            # Don't suppress the exception - let Alembic handle rollback
            return

        logger.info(f"Migration '{self.migration_name}' completed successfully")
        logger.info(f"Operations performed: {self.operations}")

    def _ensure_connection(self) -> Connection:
        """Ensure we have a valid connection.

        Returns:
            SQLAlchemy connection object.

        Raises:
            RuntimeError: If context was not entered properly.
        """
        if not self._entered or self.connection is None:
            raise RuntimeError(
                "MigrationContext must be used as a context manager (with statement)"
            )
        return self.connection

    def _record_operation(self, operation: str) -> None:
        """Record an operation for debugging.

        Args:
            operation: Description of the operation.
        """
        self.operations.append(operation)

    # Delegate methods to module-level functions
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        return table_exists(self._ensure_connection(), table_name)

    def column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists."""
        return column_exists(self._ensure_connection(), table_name, column_name)

    def index_exists(self, index_name: str) -> bool:
        """Check if an index exists."""
        return index_exists(self._ensure_connection(), index_name)

    def is_partitioned_table(self, table_name: str) -> bool:
        """Check if a table is partitioned."""
        return is_partitioned_table(self._ensure_connection(), table_name)

    def get_table_row_count(self, table_name: str) -> int:
        """Get approximate row count of a table."""
        return get_table_row_count(self._ensure_connection(), table_name)

    def safe_table_rename(self, old_name: str, new_name: str) -> None:
        """Safely rename a table."""
        safe_table_rename(self._ensure_connection(), old_name, new_name)
        self._record_operation(f"rename_table: {old_name} -> {new_name}")

    def safe_column_add(
        self,
        table_name: str,
        column_name: str,
        column_type: str,
        nullable: bool = True,
        default: str | None = None,
    ) -> None:
        """Safely add a column."""
        safe_column_add(
            self._ensure_connection(), table_name, column_name, column_type, nullable, default
        )
        self._record_operation(f"add_column: {table_name}.{column_name}")

    def safe_column_drop(self, table_name: str, column_name: str) -> None:
        """Safely drop a column."""
        safe_column_drop(self._ensure_connection(), table_name, column_name)
        self._record_operation(f"drop_column: {table_name}.{column_name}")

    def safe_index_create(
        self,
        index_name: str,
        table_name: str,
        columns: Sequence[str],
        unique: bool = False,
        where_clause: str | None = None,
        using: str | None = None,
    ) -> None:
        """Safely create an index."""
        safe_index_create(
            self._ensure_connection(),
            index_name,
            table_name,
            columns,
            unique,
            where_clause,
            using,
        )
        self._record_operation(f"create_index: {index_name} on {table_name}")

    def safe_index_drop(self, index_name: str) -> None:
        """Safely drop an index."""
        safe_index_drop(self._ensure_connection(), index_name)
        self._record_operation(f"drop_index: {index_name}")

    def safe_table_drop(self, table_name: str, cascade: bool = False) -> None:
        """Safely drop a table."""
        safe_table_drop(self._ensure_connection(), table_name, cascade)
        self._record_operation(f"drop_table: {table_name}")

    def verify_table_exists(self, table_name: str) -> None:
        """Verify a table exists."""
        verify_table_exists(self._ensure_connection(), table_name)
        self._record_operation(f"verify_table: {table_name}")

    def verify_column_exists(self, table_name: str, column_name: str) -> None:
        """Verify a column exists."""
        verify_column_exists(self._ensure_connection(), table_name, column_name)
        self._record_operation(f"verify_column: {table_name}.{column_name}")

    def verify_index_exists(self, index_name: str) -> None:
        """Verify an index exists."""
        verify_index_exists(self._ensure_connection(), index_name)
        self._record_operation(f"verify_index: {index_name}")

    def verify_table_schema(self, table_name: str, expected_columns: Sequence[str]) -> None:
        """Verify a table has expected columns."""
        verify_table_schema(self._ensure_connection(), table_name, expected_columns)
        self._record_operation(f"verify_schema: {table_name}")

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        """Execute raw SQL with logging.

        Args:
            sql: SQL statement to execute.
            params: Optional parameters for the SQL statement.

        Returns:
            Result of the SQL execution.
        """
        conn = self._ensure_connection()
        logger.debug(f"Executing SQL: {sql[:100]}...")
        result = conn.execute(text(sql), params or {})
        self._record_operation(f"execute_sql: {sql[:50]}...")
        return result


# =============================================================================
# Transaction Helpers
# =============================================================================


@contextmanager
def logged_operation(operation_name: str, rollback_hint: str | None = None) -> Generator[None]:
    """Context manager for logging migration operations.

    Args:
        operation_name: Name of the operation for logging.
        rollback_hint: Optional hint for how to rollback this operation.

    Yields:
        None - just provides logging around the operation.

    Raises:
        MigrationError: Re-raises any exception with additional context.
    """
    logger.info(f"Starting operation: {operation_name}")
    try:
        yield
        logger.info(f"Completed operation: {operation_name}")
    except (IntegrityError, OperationalError, ProgrammingError) as e:
        error_msg = f"Operation '{operation_name}' failed: {e}"
        if rollback_hint:
            error_msg += f"\nRollback hint: {rollback_hint}"
        logger.error(error_msg)
        raise MigrationError(error_msg) from e
    except SQLAlchemyError as e:
        error_msg = f"Database error in operation '{operation_name}': {e}"
        logger.error(error_msg)
        raise MigrationError(error_msg) from e


def ensure_transaction_savepoint(connection: Connection, name: str) -> None:
    """Create a savepoint for potential partial rollback.

    Note: PostgreSQL supports SAVEPOINT within transactions.
    This allows rolling back to a specific point without
    aborting the entire transaction.

    Args:
        connection: SQLAlchemy connection object.
        name: Name for the savepoint.
    """
    connection.execute(text(f"SAVEPOINT {name}"))
    logger.debug(f"Created savepoint: {name}")


def rollback_to_savepoint(connection: Connection, name: str) -> None:
    """Rollback to a previously created savepoint.

    Args:
        connection: SQLAlchemy connection object.
        name: Name of the savepoint to rollback to.
    """
    connection.execute(text(f"ROLLBACK TO SAVEPOINT {name}"))
    logger.info(f"Rolled back to savepoint: {name}")


def release_savepoint(connection: Connection, name: str) -> None:
    """Release a savepoint (commit the savepoint).

    Args:
        connection: SQLAlchemy connection object.
        name: Name of the savepoint to release.
    """
    connection.execute(text(f"RELEASE SAVEPOINT {name}"))
    logger.debug(f"Released savepoint: {name}")
