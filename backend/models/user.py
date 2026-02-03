"""User model for authentication.

This module defines the User model for storing user authentication data.
Passwords are NEVER stored in plaintext - only argon2 hashes are persisted.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base

if TYPE_CHECKING:
    from .api_key import APIKey


class User(Base):
    """User model for authentication.

    Stores user credentials and profile information. Passwords are stored
    as argon2 hashes - plaintext passwords are NEVER persisted.

    Attributes:
        id: Unique user identifier (string primary key).
        username: Unique username for login.
        email: Unique email address.
        password_hash: Argon2 hash of the user's password.
        created_at: Timestamp when user was created.
        updated_at: Timestamp when user was last updated.
        last_login_at: Timestamp of last successful login (nullable).
        is_active: Whether the user account is active.
        api_keys: List of API keys belonging to this user.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    api_keys: Mapped[list[APIKey]] = relationship(
        "APIKey",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __init__(
        self,
        *,
        id: str,
        username: str,
        email: str,
        password_hash: str,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        last_login_at: datetime | None = None,
        is_active: bool = True,
        is_admin: bool = False,
    ) -> None:
        """Initialize a User instance.

        Args:
            id: Unique user identifier.
            username: Unique username for login.
            email: Unique email address.
            password_hash: Argon2 hash of the password (never plaintext).
            created_at: When user was created (defaults to now).
            updated_at: When user was last updated (defaults to now).
            last_login_at: Last login timestamp (optional).
            is_active: Whether account is active (defaults to True).
            is_admin: Whether user has admin privileges (defaults to False).
        """
        super().__init__()
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.created_at = created_at or datetime.now(UTC)
        self.updated_at = updated_at or datetime.now(UTC)
        self.last_login_at = last_login_at
        self.is_active = is_active
        self.is_admin = is_admin

    def __repr__(self) -> str:
        """Return string representation of User."""
        return f"<User(id={self.id!r}, username={self.username!r}, email={self.email!r})>"
