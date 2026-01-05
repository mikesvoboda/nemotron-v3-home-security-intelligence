"""Database model for AI model prompt configurations.

This module provides persistent storage for AI model prompt configurations,
allowing users to save and retrieve custom prompts, temperature, and token settings.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .camera import Base


class PromptConfig(Base):
    """Prompt configuration for AI models.

    Stores the current configuration for each AI model including system prompt,
    temperature, and max_tokens settings. Each update increments the version
    to track changes over time.

    Attributes:
        id: Primary key
        model: Model name (nemotron, florence-2, yolo-world, x-clip, fashion-clip)
        system_prompt: Full system prompt text for the model
        temperature: LLM temperature setting (0-2)
        max_tokens: Maximum tokens in response (100-8192)
        version: Auto-incrementing version number
        created_at: When the config was first created
        updated_at: When the config was last updated
    """

    __tablename__ = "prompt_configs"
    __table_args__ = (
        Index("idx_prompt_configs_model", "model", unique=True),
        Index("idx_prompt_configs_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=2048)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<PromptConfig(model={self.model!r}, version={self.version})>"
