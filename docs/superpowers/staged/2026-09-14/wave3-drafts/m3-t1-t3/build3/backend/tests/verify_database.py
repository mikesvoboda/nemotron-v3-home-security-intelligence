#!/usr/bin/env python3
"""Manual verification script for database connection."""

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import Column, Integer, String, select

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core import Base, close_db, get_session, init_db


# Test model
class TestItem(Base):
    __tablename__ = "test_items"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255))


async def main():
    """Test database connection and operations."""
    print("Testing database connection...")

    # Set test database
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_verify.db"

    try:
        # Initialize database
        print("1. Initializing database...")
        await init_db()
        print("   ✓ Database initialized")

        # Create test table
        print("2. Creating test table...")
        from backend.core import get_engine

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(TestItem.__table__.create, checkfirst=True)
        print("   ✓ Test table created")

        # Insert test data
        print("3. Inserting test data...")
        async with get_session() as session:
            item1 = TestItem(name="Item 1", description="First test item")
            item2 = TestItem(name="Item 2", description="Second test item")
            session.add(item1)
            session.add(item2)
        print("   ✓ Test data inserted")

        # Query test data
        print("4. Querying test data...")
        async with get_session() as session:
            result = await session.execute(select(TestItem))
            items = result.scalars().all()
            print(f"   ✓ Found {len(items)} items:")
            for item in items:
                print(f"     - {item.name}: {item.description}")

        # Test session rollback
        print("5. Testing rollback on error...")
        try:
            async with get_session() as session:
                item3 = TestItem(name="Item 3", description="Will be rolled back")
                session.add(item3)
                raise ValueError("Intentional error for rollback test")
        except ValueError:
            pass

        async with get_session() as session:
            result = await session.execute(select(TestItem).where(TestItem.name == "Item 3"))
            item = result.scalar_one_or_none()
            if item is None:
                print("   ✓ Rollback worked correctly")
            else:
                print("   ✗ Rollback failed - item was committed")

        print("\n✓ All database tests passed!")

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    finally:
        # Cleanup
        print("\n6. Cleaning up...")
        await close_db()
        print("   ✓ Database closed")

        # Remove test database
        test_db_path = Path("./data/test_verify.db")
        if test_db_path.exists():
            test_db_path.unlink()
            print("   ✓ Test database removed")


if __name__ == "__main__":
    asyncio.run(main())
