"""ORM utilities for SQLAlchemy models.

This module provides utilities for configuring SQLAlchemy ORM behavior,
including:
- Configurable lazy loading with raiseload for N+1 query prevention
- Server-side timestamp defaults
- Optimistic locking patterns

NEM-3405: raiseload configuration
NEM-3407: Server-side timestamp standardization
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Literal

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

# =============================================================================
# Environment-based Configuration (NEM-3405)
# =============================================================================


def is_development_mode() -> bool:
    """Check if the application is running in development mode.

    Returns True if ENVIRONMENT is 'development' or 'test', enabling
    stricter ORM validation like raiseload.

    Returns:
        True if in development/test mode, False otherwise
    """
    env = os.environ.get("ENVIRONMENT", "production").lower()
    return env in ("development", "test", "testing")


def get_relationship_lazy_mode(
    default: str = "select",
    development_mode: str = "raise_on_sql",
) -> Literal["select", "raise_on_sql", "selectin", "joined", "subquery", "noload"]:
    """Get the appropriate lazy loading mode based on environment.

    In development/test mode, returns 'raise_on_sql' to catch N+1 queries
    by raising an exception when a lazy load would trigger a SQL query.
    In production, returns the specified default (usually 'select').

    This allows catching N+1 query patterns during development while
    maintaining standard behavior in production.

    Args:
        default: Lazy mode for production (default: 'select')
        development_mode: Lazy mode for development (default: 'raise_on_sql')

    Returns:
        The appropriate lazy loading mode string

    Example:
        ```python
        from backend.core.orm_utils import get_relationship_lazy_mode

        class Event(Base):
            camera: Mapped[Camera] = relationship(
                "Camera",
                lazy=get_relationship_lazy_mode(default="select"),
            )
        ```

    Note:
        'raise_on_sql' differs from 'raise' in that it only raises when
        a SQL query would be emitted, allowing access to already-loaded
        objects from the identity map.
    """
    if is_development_mode():
        return development_mode  # type: ignore[return-value]
    return default  # type: ignore[return-value]


# =============================================================================
# Server-Side Timestamp Defaults (NEM-3407)
# =============================================================================


def created_at_column() -> Mapped[datetime]:
    """Create a created_at column with proper server-side default.

    Uses func.now() for the server_default to ensure timestamps are
    generated at the database level, providing consistency across
    all insertions (including bulk inserts and migrations).

    Returns:
        Mapped column configured with server_default=func.now()

    Example:
        ```python
        from backend.core.orm_utils import created_at_column

        class MyModel(Base):
            created_at: Mapped[datetime] = created_at_column()
        ```
    """
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


def updated_at_column(nullable: bool = False) -> Mapped[datetime | None] | Mapped[datetime]:
    """Create an updated_at column with proper server-side default and onupdate.

    Uses func.now() for both server_default and onupdate to ensure
    timestamps are generated at the database level.

    Args:
        nullable: If True, allows NULL values (default: False)

    Returns:
        Mapped column configured with server_default and onupdate

    Example:
        ```python
        from backend.core.orm_utils import updated_at_column

        class MyModel(Base):
            updated_at: Mapped[datetime] = updated_at_column()
        ```
    """
    return mapped_column(
        DateTime(timezone=True),
        nullable=nullable,
        server_default=func.now(),
        onupdate=func.now(),
    )


def timestamp_column(
    nullable: bool = True,
    use_server_default: bool = False,
) -> Mapped[datetime | None] | Mapped[datetime]:
    """Create a generic timestamp column with optional server default.

    For timestamps that don't follow the created_at/updated_at pattern,
    this provides a flexible column factory.

    Args:
        nullable: If True, allows NULL values (default: True)
        use_server_default: If True, uses func.now() as server_default

    Returns:
        Mapped column configured as specified

    Example:
        ```python
        from backend.core.orm_utils import timestamp_column

        class MyModel(Base):
            processed_at: Mapped[datetime | None] = timestamp_column()
            expires_at: Mapped[datetime] = timestamp_column(nullable=False)
        ```
    """
    if use_server_default:
        return mapped_column(
            DateTime(timezone=True),
            nullable=nullable,
            server_default=func.now(),
        )
    return mapped_column(
        DateTime(timezone=True),
        nullable=nullable,
    )


# =============================================================================
# Optimistic Locking Utilities (NEM-3408)
# =============================================================================


def version_column(start_value: int = 1) -> Mapped[int]:
    """Create a version column for optimistic locking.

    The version column is auto-incremented by SQLAlchemy on each UPDATE
    when configured with __mapper_args__['version_id_col'].

    Args:
        start_value: Initial version value for new rows (default: 1)

    Returns:
        Mapped column configured for optimistic locking

    Example:
        ```python
        from backend.core.orm_utils import version_column

        class MyModel(Base):
            version: Mapped[int] = version_column()

            @declared_attr
            def __mapper_args__(cls):
                return {"version_id_col": cls.__table__.c.version}
        ```

    Note:
        The version column alone doesn't enable optimistic locking.
        You must also configure __mapper_args__['version_id_col'] to
        point to the column.
    """
    return mapped_column(
        nullable=False,
        default=start_value,
        server_default=str(start_value),
    )
