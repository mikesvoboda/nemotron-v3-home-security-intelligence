"""EventVerification model for VLM verification provenance (spec §4, P0.4).

One row per vlm-mode event records what the verifier concluded and saw:
the verdict, the scene description it generated, the criteria checklist, the
detection ids of the key frames it reviewed, and the engine/model/latency
provenance. Legacy events have NO row (spec §4: "Legacy events have no
verification row") - row presence is what the REST/WS `verification` field
branches on.

Production only: replay results live in the eval store (spec §5), not here.
Retention hard-deletes events (backend/services/cleanup_service.py); the FK
cascades (the event_audits/llm_interactions pattern), so an event delete
takes the verification row with it - never an orphan, never a 500. The plan
(ledger P0.4 decision) kept CASCADE over an FK-less provenance row because
the evaluation needs NOTHING from this table: eval items are self-contained
by D7, so there is no provenance to outlive the event.

Migration: none exists to write - this repo is `create_all`-only (Alembic
was removed in #4465; backend/core/database.py). create_all creates NEW
tables on an existing database and never ALTERS existing ones, so shipping
this model IS the migration; the behavior is pinned by
backend/tests/integration/test_p04_event_verifications.py.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Literal, get_args

from sqlalchemy import (
    CheckConstraint,
    ColumnElement,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.orm_utils import get_relationship_lazy_mode
from backend.core.time_utils import utc_now

from .camera import Base

if TYPE_CHECKING:
    from .event import Event

# spec §4: verdict ∈ {confirmed, rejected, uncertain, verification_failed}
VerdictLiteral = Literal["confirmed", "rejected", "uncertain", "verification_failed"]
VERDICT_VALUES: tuple[str, ...] = get_args(VerdictLiteral)

# 1.6: the API filter vocabulary is the four verdicts PLUS a pseudo-value.
# VERDICT_NONE = "show me what was never verified" — not expressible as any
# verdict, and in a fresh vlm deployment it is the first question an operator
# asks. The Literal (not a str) is what makes a typo a 422 instead of an
# empty list: the 1.5 no-silent-fallback rule, applied to a filter.
VERDICT_NONE = "none"
VerdictFilterLiteral = Literal["confirmed", "rejected", "uncertain", "verification_failed", "none"]
VERDICT_FILTER_VALUES: tuple[str, ...] = get_args(VerdictFilterLiteral)


def verdict_filter_condition(verdict: str) -> ColumnElement[bool]:
    """SQL condition for ``?verdict=<value>`` on the event list/search routes.

    The verdict lives ONLY on ``event_verifications`` — it is never
    denormalized onto Event — so filtering is EXISTS / NOT EXISTS on the
    relationship, not a column comparison. ``Event.verifications`` has no
    unique constraint (a repair path may stack rows), so a row whose ANY
    verification matches is a match; ``verification_payload`` independently
    renders the newest row for display.

    ``verdict`` arrives already validated at the route: the param is typed
    ``VerdictFilterLiteral``, so anything outside the vocabulary is a 422
    before this runs — the 1.5 no-silent-fallback rule, applied to a filter.
    """
    from .event import Event  # function-local: event.py names THIS module (TYPE_CHECKING)

    if verdict == VERDICT_NONE:
        return ~(
            select(EventVerification.id).where(EventVerification.event_id == Event.id).exists()
        )
    return (
        select(EventVerification.id)
        .where(
            EventVerification.event_id == Event.id,
            EventVerification.verdict == verdict,
        )
        .exists()
    )


class EventVerification(Base):
    """A VLM verification record for one event (spec §4).

    ``verdict`` answers "is the detected candidate real and correctly
    identified?"; it is independent of the event's risk score (spec §6).
    ``verdict='verification_failed'`` pairs with the event's NULL
    risk_score/risk_level (D11) and is written by the 0.3 fail-closed path.

    Relationships:
        - event: many-to-one to Event (event.verifications back_populates)

    Indexes:
        - idx_event_verifications_event_id: the API/WS serialization lookup
        - idx_event_verifications_created_at: recency queries
    """

    __tablename__ = "event_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )

    # verdict ∈ {confirmed, rejected, uncertain, verification_failed} (spec §4)
    verdict: Mapped[VerdictLiteral] = mapped_column(String, nullable=False)

    # The whole-scene description the VLM generated (§3 VlmVerdict.description)
    scene_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # criteria checklist: [{name, passed, evidence}, ...] (spec §6 post-validation
    # requires >= 1 criterion with evidence on a scored verdict)
    criteria: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    # detection ids of the 1-4 key frames the VLM actually reviewed; the UI
    # resolves them to existing thumbnails (spec §4 event detail)
    key_frame_detection_ids: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)

    # provenance: which engine + model produced the verdict, and how long it took
    engine: Mapped[str] = mapped_column(String, nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    # NULL = no timed call happened (e.g. transport failure before response);
    # honest absence, never a fabricated 0
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    event: Mapped[Event] = relationship(
        "Event",
        back_populates="verifications",
        # repo N+1 guard (dev/test = raise_on_sql); the API path reads rows via
        # Event.verifications (eager selectin), never this direction.
        lazy=get_relationship_lazy_mode(),
    )

    __table_args__ = (
        Index("idx_event_verifications_event_id", "event_id"),
        Index("idx_event_verifications_created_at", "created_at"),
        # The CHECK stays the four REAL verdicts: VERDICT_FILTER_VALUES is a
        # filter vocabulary and 'none' means "no row exists", so a row may
        # never carry it. The two lists are deliberately not the same set.
        CheckConstraint(
            "verdict IN ('confirmed', 'rejected', 'uncertain', 'verification_failed')",
            name="ck_event_verifications_verdict",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<EventVerification(id={self.id}, event_id={self.event_id}, "
            f"verdict={self.verdict!r}, engine={self.engine!r}, "
            f"model_id={self.model_id!r})>"
        )
