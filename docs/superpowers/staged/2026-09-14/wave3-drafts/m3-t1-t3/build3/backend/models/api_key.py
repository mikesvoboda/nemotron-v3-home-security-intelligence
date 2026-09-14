"""APIKey model for API authentication.

This module defines the APIKey model for storing API key metadata.
API keys are NEVER stored in plaintext - only SHA256 hashes are persisted.
The key prefix is stored for identification purposes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base

if TYPE_CHECKING:
    from .user import User


class APIKey(Base):
    """API Key model for programmatic authentication.

    Stores API key metadata. The actual key is NEVER stored - only
    a SHA256 hash is persisted. The prefix (first ~12 chars) is stored
    for identification/display purposes.

    Attributes:
        id: Unique API key identifier.
        user_id: Foreign key to the owning user.
        prefix: Visible prefix for identification (e.g., "nemo_k1_abc").
        key_hash: SHA256 hash of the full API key.
        name: Human-readable name for the key.
        created_at: Timestamp when key was created.
        last_used_at: Timestamp when key was last used (nullable).
        expires_at: Optional expiration timestamp (nullable for permanent keys).
        is_active: Whether the key is active.
        user: Relationship to the owning User.
    """

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="api_keys")

    def __init__(
        self,
        *,
        id: str,
        user_id: str,
        prefix: str,
        key_hash: str,
        name: str,
        created_at: datetime | None = None,
        last_used_at: datetime | None = None,
        expires_at: datetime | None = None,
        is_active: bool = True,
    ) -> None:
        """Initialize an APIKey instance.

        Args:
            id: Unique API key identifier.
            user_id: ID of the owning user.
            prefix: Visible prefix for identification.
            key_hash: SHA256 hash of the full API key.
            name: Human-readable name for the key.
            created_at: When key was created (defaults to now).
            last_used_at: Last usage timestamp (optional).
            expires_at: Expiration timestamp (optional, None = permanent).
            is_active: Whether key is active (defaults to True).
        """
        super().__init__()
        self.id = id
        self.user_id = user_id
        self.prefix = prefix
        self.key_hash = key_hash
        self.name = name
        self.created_at = created_at or datetime.now(UTC)
        self.last_used_at = last_used_at
        self.expires_at = expires_at
        self.is_active = is_active

    @property
    def is_expired(self) -> bool:
        """Check if the API key has expired.

        Returns:
            True if the key has an expiration date that has passed,
            False if permanent (no expires_at) or not yet expired.
        """
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    def __repr__(self) -> str:
        """Return string representation of APIKey."""
        return f"<APIKey(id={self.id!r}, prefix={self.prefix!r}, name={self.name!r})>"
