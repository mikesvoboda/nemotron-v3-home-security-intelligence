#!/usr/bin/env python3
"""Migrate data from SQLite to PostgreSQL.

This script exports data from an existing SQLite database and imports it into
PostgreSQL while preserving IDs and relationships.

Usage:
    python scripts/migrate-sqlite-to-postgres.py

Environment variables:
    SQLITE_URL: SQLite database URL (default: sqlite:///./backend/data/security.db)
    POSTGRES_URL: PostgreSQL database URL (required)

Example:
    POSTGRES_URL=postgresql://security:password@localhost:5432/security \
        python scripts/migrate-sqlite-to-postgres.py
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def get_sqlite_url() -> str:
    """Get SQLite database URL."""
    url = os.getenv("SQLITE_URL", "sqlite:///./backend/data/security.db")
    # Remove async driver prefix if present
    if "+aiosqlite" in url:
        url = url.replace("+aiosqlite", "")
    return url


def get_postgres_url() -> str:
    """Get PostgreSQL database URL."""
    url = os.getenv("POSTGRES_URL")
    if not url:
        print("Error: POSTGRES_URL environment variable is required")
        print("Example: POSTGRES_URL=postgresql://user:pass@localhost:5432/dbname")
        sys.exit(1)
    # Remove async driver prefix if present
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "")
    return url


def migrate_table(
    sqlite_session: sessionmaker,
    postgres_session: sessionmaker,
    table_name: str,
    columns: list[str],
) -> int:
    """Migrate data from one table.

    Args:
        sqlite_session: SQLite session
        postgres_session: PostgreSQL session
        table_name: Name of the table to migrate
        columns: List of column names

    Returns:
        Number of rows migrated
    """
    # Read from SQLite
    sqlite_conn = sqlite_session()
    cols = ", ".join(columns)
    # nosemgrep: avoid-sqlalchemy-text - table/column names from hardcoded metadata, not user input
    result = sqlite_conn.execute(text(f"SELECT {cols} FROM {table_name}"))  # noqa: S608
    rows = result.fetchall()
    sqlite_conn.close()

    if not rows:
        print(f"  {table_name}: 0 rows (empty)")
        return 0

    # Insert into PostgreSQL
    postgres_conn = postgres_session()

    # Build insert statement with placeholders
    placeholders = ", ".join([f":{col}" for col in columns])
    # nosemgrep: avoid-sqlalchemy-text - table/column names from hardcoded metadata, not user input
    insert_sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"  # noqa: S608

    # Convert rows to dicts
    row_dicts = [dict(zip(columns, row, strict=False)) for row in rows]

    # Execute in batches
    batch_size = 1000
    for i in range(0, len(row_dicts), batch_size):
        batch = row_dicts[i : i + batch_size]
        # nosemgrep: avoid-sqlalchemy-text  # noqa: ERA001
        postgres_conn.execute(text(insert_sql), batch)

    postgres_conn.commit()
    postgres_conn.close()

    print(f"  {table_name}: {len(rows)} rows migrated")
    return len(rows)


def reset_sequence(postgres_session: sessionmaker, table_name: str, id_column: str = "id") -> None:
    """Reset PostgreSQL sequence to max ID value.

    This ensures new inserts get IDs after existing data.
    """
    conn = postgres_session()
    # Get max ID
    # nosemgrep: avoid-sqlalchemy-text - table/column names from function args, not user input
    result = conn.execute(text(f"SELECT COALESCE(MAX({id_column}), 0) FROM {table_name}"))  # noqa: S608
    max_id = result.scalar()

    if max_id and max_id > 0:
        # Reset sequence
        seq_name = f"{table_name}_{id_column}_seq"
        # nosemgrep: avoid-sqlalchemy-text - seq_name derived from table name, not user input
        conn.execute(text(f"SELECT setval('{seq_name}', {max_id})"))
        conn.commit()

    conn.close()


def verify_counts(
    sqlite_session: sessionmaker,
    postgres_session: sessionmaker,
    table_name: str,
) -> bool:
    """Verify row counts match between databases."""
    sqlite_conn = sqlite_session()
    # nosemgrep: avoid-sqlalchemy-text - table_name from hardcoded metadata, not user input
    result = sqlite_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))  # noqa: S608
    sqlite_count = result.scalar()
    sqlite_conn.close()

    postgres_conn = postgres_session()
    # nosemgrep: avoid-sqlalchemy-text - table_name from hardcoded metadata, not user input
    result = postgres_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))  # noqa: S608
    postgres_count = result.scalar()
    postgres_conn.close()

    match = sqlite_count == postgres_count
    status = "OK" if match else "MISMATCH"
    print(f"  {table_name}: SQLite={sqlite_count}, PostgreSQL={postgres_count} [{status}]")
    return match


def main() -> int:
    """Run the migration."""
    print("=" * 60)
    print("SQLite to PostgreSQL Data Migration")
    print("=" * 60)
    print()

    # Get database URLs
    sqlite_url = get_sqlite_url()
    postgres_url = get_postgres_url()

    print(f"Source (SQLite): {sqlite_url}")
    print(f"Target (PostgreSQL): {postgres_url.split('@')[0]}@***")
    print()

    # Create engines
    sqlite_engine = create_engine(sqlite_url)
    postgres_engine = create_engine(postgres_url)

    SQLiteSession = sessionmaker(bind=sqlite_engine)
    PostgresSession = sessionmaker(bind=postgres_engine)

    # Define tables and their columns (in dependency order)
    tables = {
        "cameras": [
            "id",
            "name",
            "folder_path",
            "status",
            "created_at",
            "last_seen_at",
        ],
        "gpu_stats": [
            "id",
            "recorded_at",
            "gpu_name",
            "gpu_utilization",
            "memory_used",
            "memory_total",
            "temperature",
            "power_usage",
            "inference_fps",
        ],
        "api_keys": [
            "id",
            "key_hash",
            "name",
            "created_at",
            "is_active",
        ],
        "logs": [
            "id",
            "timestamp",
            "level",
            "component",
            "message",
            "camera_id",
            "event_id",
            "request_id",
            "detection_id",
            "duration_ms",
            "extra",
            "source",
            "user_agent",
        ],
        "detections": [
            "id",
            "camera_id",
            "file_path",
            "file_type",
            "detected_at",
            "object_type",
            "confidence",
            "bbox_x",
            "bbox_y",
            "bbox_width",
            "bbox_height",
            "thumbnail_path",
        ],
        "events": [
            "id",
            "batch_id",
            "camera_id",
            "started_at",
            "ended_at",
            "risk_score",
            "risk_level",
            "summary",
            "reasoning",
            "detection_ids",
            "reviewed",
            "notes",
            "is_fast_path",
        ],
    }

    # Run migration
    print("Step 1: Migrating data...")
    print("-" * 40)
    start_time = datetime.now()
    total_rows = 0

    for table_name, columns in tables.items():
        try:
            rows = migrate_table(SQLiteSession, PostgresSession, table_name, columns)
            total_rows += rows
        except Exception as e:
            print(f"  {table_name}: ERROR - {e}")
            return 1

    elapsed = (datetime.now() - start_time).total_seconds()
    print()
    print(f"Total: {total_rows} rows migrated in {elapsed:.2f}s")
    print()

    # Reset sequences
    print("Step 2: Resetting sequences...")
    print("-" * 40)
    sequence_tables = ["gpu_stats", "api_keys", "logs", "detections", "events"]
    for table_name in sequence_tables:
        try:
            reset_sequence(PostgresSession, table_name)
            print(f"  {table_name}: sequence reset")
        except Exception as e:
            print(f"  {table_name}: WARNING - {e}")
    print()

    # Verify migration
    print("Step 3: Verifying migration...")
    print("-" * 40)
    all_match = True
    for table_name in tables:
        if not verify_counts(SQLiteSession, PostgresSession, table_name):
            all_match = False
    print()

    if all_match:
        print("Migration completed successfully!")
        return 0
    else:
        print("WARNING: Some row counts don't match. Please verify manually.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
