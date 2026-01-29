#!/usr/bin/env python3
"""Initialize database schema directly from SQLAlchemy models.

This script creates all tables without using Alembic migrations.
Run with: python -m backend.scripts.init_schema
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.config import get_settings
from backend.models import Base
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def init_schema() -> None:
    """Create all tables from SQLAlchemy models."""
    settings = get_settings()

    print("Connecting to database...")
    engine = create_async_engine(settings.database_url, echo=False)

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
    asyncio.run(init_schema())
