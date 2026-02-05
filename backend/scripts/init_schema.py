#!/usr/bin/env python3
"""Initialize database schema directly from SQLAlchemy models.

This script creates all tables without using Alembic migrations.
Run with: python -m backend.scripts.init_schema

NEM-4482: Production safeguards added to prevent accidental data loss.
This script will refuse to run in production environments unless
explicitly confirmed with --force flag.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.config import get_settings
from backend.models import Base
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def is_production_environment() -> bool:
    """Check if we're running in a production environment.

    Returns:
        True if environment appears to be production, False otherwise.
    """
    # Check common production environment indicators
    env = os.environ.get("ENVIRONMENT", "").lower()
    if env in ("production", "prod"):
        return True

    # Check for production-like database URLs
    db_url = os.environ.get("DATABASE_URL", "")
    production_indicators = [
        "rds.amazonaws.com",  # AWS RDS
        "postgres.database.azure.com",  # Azure PostgreSQL
        "cloudsql.google.com",  # Google Cloud SQL
        ".neon.tech",  # Neon DB
        ".supabase.co",  # Supabase
        "prod",  # Generic production indicator
    ]
    for indicator in production_indicators:
        if indicator in db_url.lower():
            return True

    # Check NODE_ENV (common in containerized environments)
    node_env = os.environ.get("NODE_ENV", "").lower()
    if node_env == "production":
        return True

    # Check for CI/CD pipeline indicators (safer to prevent in CI too)
    return bool(os.environ.get("CI"))


async def init_schema(force: bool = False) -> None:
    """Create all tables from SQLAlchemy models.

    NEM-4482: This function includes production safeguards to prevent
    accidental data loss in production environments.

    Args:
        force: If True, skip production safeguards (use with extreme caution)
    """
    settings = get_settings()

    # NEM-4482: Production safeguards
    if is_production_environment() and not force:
        print("ERROR: Refusing to run init_schema in production environment!")
        print("")
        print("This script will DROP ALL TABLES and recreate the schema,")
        print("resulting in PERMANENT DATA LOSS.")
        print("")
        print("If you really want to proceed, use one of these options:")
        print("  1. Run with --force flag: python -m backend.scripts.init_schema --force")
        print("  2. Set ENVIRONMENT=development in your environment")
        print("")
        print("For production deployments, let the backend initialize the schema:")
        print("  init_db() is called automatically during backend startup")
        sys.exit(1)

    print("Connecting to database...")
    engine = create_async_engine(settings.database_url, echo=False)

    # Additional confirmation for non-localhost databases
    db_url = settings.database_url
    if "localhost" not in db_url and "127.0.0.1" not in db_url and not force:
        print(f"WARNING: Database URL does not appear to be local: {db_url[:50]}...")
        response = input("Are you sure you want to DROP ALL TABLES? (type 'yes' to confirm): ")
        if response.lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    async with engine.begin() as conn:
        print("Dropping all existing tables...")
        await conn.run_sync(Base.metadata.drop_all)

        print("Creating all tables from models...")
        await conn.run_sync(Base.metadata.create_all)

        # Verify tables were created
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
        )
        tables = [row[0] for row in result.fetchall()]
        print(f"\nCreated {len(tables)} tables:")
        for table in tables:
            print(f"  - {table}")

    await engine.dispose()
    print("\nSchema initialization complete!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Initialize database schema from SQLAlchemy models",
        epilog="WARNING: This script drops all tables! Schema is auto-initialized during backend startup.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force execution even in production environment (DANGEROUS)",
    )
    args = parser.parse_args()

    asyncio.run(init_schema(force=args.force))
