"""PromptVersion model for AI prompt configuration version tracking."""

import json
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.json_utils import safe_json_loads
from backend.core.time_utils import utc_now

from .camera import Base


class AIModel(str, Enum):
    """AI models that have configurable prompts.

    B3.3 box 4 (R2a row 27): the four vision models retired with the R8 S2/S3 sweep;
    their ``prompt_versions`` rows are deleted and the column left the native enum by
    upgrade ``0011-retire-vision-model-prompts``. The stored column is now a plain
    varchar holding ``nemotron`` -- the only model a deployment boots.
    """

    NEMOTRON = "nemotron"


class PromptVersion(Base):
    """Version tracking for AI model prompt configurations.

    Stores historical versions of prompts/configs for all supported AI models.
    Each update creates a new version, enabling rollback and auditing.

    Uses optimistic locking via row_version column to prevent race conditions
    when multiple clients try to update the same prompt config concurrently.
    """

    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Plain varchar, not a native enum: 0011 converted the historical `aimodel` enum column
    # to varchar, and create_all must build the same shape (schema twins).
    model: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Configuration content (JSON for structured data, text for prompts)
    # For Nemotron: system_prompt text
    config_json: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional description of what changed
    change_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Is this the currently active version?
    is_active: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")

    # Optimistic locking version counter - incremented on each update
    # Used to detect concurrent modifications and prevent race conditions
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    # Indexes and constraints
    __table_args__ = (
        Index("idx_prompt_versions_model", "model"),
        Index("idx_prompt_versions_model_version", "model", "version"),
        Index("idx_prompt_versions_model_active", "model", "is_active"),
        Index("idx_prompt_versions_created_at", "created_at"),
        # Ensure each (model, version) combination is unique - prevents duplicate versions
        UniqueConstraint("model", "version", name="uq_prompt_version_model_version"),
    )

    @property
    def config(self) -> dict[str, Any]:
        """Parse config_json and return as dict."""
        result = safe_json_loads(
            self.config_json,
            default={},
            context=f"PromptVersion config (model={self.model}, version={self.version})",
        )
        return result if isinstance(result, dict) else {}

    def set_config(self, config: dict[str, Any]) -> None:
        """Set config from dict, serializing to JSON."""
        self.config_json = json.dumps(config, indent=2)

    def __repr__(self) -> str:
        return (
            f"<PromptVersion(id={self.id}, model={self.model}, "
            f"version={self.version}, active={self.is_active})>"
        )
