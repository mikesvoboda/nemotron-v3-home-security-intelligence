"""LLMInteraction model for AI pipeline observability.

Captures what Nemotron received (enrichment snapshot) and responded (raw_response)
for debugging accuracy issues in the AI pipeline. See NEM-4234 for context.

Key fields:
- raw_response: Full LLM output including <think> blocks for reasoning transparency
- enrichment_snapshot: Frozen copy of enrichment_data at analysis time for audit trail
- household_matches: Person/vehicle matches with similarity scores
- truncation_log: What context sections were dropped due to token limits
- context_sources: Which enrichment fields were populated vs empty
- validation_result: Expected vs actual comparison (for synthetic data testing)
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.orm_utils import get_relationship_lazy_mode

from .camera import Base

if TYPE_CHECKING:
    from .event import Event


class LLMInteraction(Base):
    """LLMInteraction model for storing Nemotron analysis observability data.

    Each record captures the full context of an LLM analysis call:
    - What data was sent (enrichment_snapshot, household_matches)
    - What was received (raw_response)
    - What was truncated (truncation_log)
    - Validation results for synthetic data testing

    This enables debugging misattribution issues where the LLM's reasoning
    references incorrect attributes from enrichment models.

    Relationships:
        - event: One-to-one relationship with Event (back_populates="llm_interaction")

    Indexes:
        - idx_llm_interactions_event_id: Fast lookup by event
        - idx_llm_interactions_created_at: Time-based queries for recent interactions
    """

    __tablename__ = "llm_interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )

    # Full LLM output including <think> blocks for reasoning transparency
    raw_response: Mapped[str] = mapped_column(Text, nullable=False)

    # Frozen copy of enrichment_data at analysis time for audit trail
    enrichment_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Person/vehicle matches with similarity scores (optional)
    household_matches: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # What context sections were dropped due to token limits (optional)
    truncation_log: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Which enrichment fields were populated vs empty (optional)
    context_sources: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Expected vs actual comparison for synthetic data testing (optional)
    validation_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # When analysis occurred
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship to Event (one-to-one)
    event: Mapped[Event] = relationship(
        "Event",
        back_populates="llm_interaction",
        lazy=get_relationship_lazy_mode(),
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_llm_interactions_event_id", "event_id"),
        Index("idx_llm_interactions_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<LLMInteraction(id={self.id}, event_id={self.event_id})>"
