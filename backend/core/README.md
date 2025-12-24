# Backend Core Module

This directory contains core infrastructure components for the Home Security Intelligence application.

## Modules

### config.py

Application configuration using Pydantic Settings. All configuration is loaded from environment variables with sensible defaults.

Key settings:

- `DATABASE_URL`: SQLAlchemy database connection string (default: sqlite+aiosqlite:///./data/security.db)
- `REDIS_URL`: Redis connection string
- `FOSCAM_BASE_PATH`: Base path for camera FTP uploads
- `RETENTION_DAYS`: Data retention period (default: 30 days)
- Batch processing configuration
- AI service endpoints

Usage:

```python
from backend.core import get_settings

settings = get_settings()
print(settings.database_url)
```

### database.py

Database connection and session management using SQLAlchemy 2.0 async patterns.

Features:

- Async SQLite database engine with proper connection pooling
- Session factory with automatic commit/rollback
- Base declarative class for models
- FastAPI dependency injection support
- Application lifecycle management

Usage:

#### Initialize database (in application startup):

```python
from backend.core import init_db, close_db

# Startup
await init_db()

# Shutdown
await close_db()
```

#### Using sessions in FastAPI endpoints:

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core import get_db

@app.get("/items")
async def get_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item))
    return result.scalars().all()
```

#### Using sessions in standalone code:

```python
from backend.core import get_session
from sqlalchemy import select

async with get_session() as session:
    result = await session.execute(select(Item))
    items = result.scalars().all()
    # Commit happens automatically on context exit
```

#### Creating models:

```python
from sqlalchemy import Column, Integer, String
from backend.core import Base

class MyModel(Base):
    __tablename__ = "my_models"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
```

## Testing

Unit tests are located in `backend/tests/unit/test_database.py`.

Run tests:

```bash
pytest backend/tests/unit/test_database.py -v
```

Verify database connection manually:

```bash
python backend/tests/verify_database.py
```

## Configuration

Create a `.env` file in the project root to override default settings:

```env
DATABASE_URL=sqlite+aiosqlite:///./data/security.db
REDIS_URL=redis://localhost:6379/0
DEBUG=false
RETENTION_DAYS=30
```

## Database Schema

The database schema is defined by SQLAlchemy models in `backend/models/`. The database is automatically created and migrated when the application starts.

Database file location: `./data/security.db` (configurable via DATABASE_URL)
