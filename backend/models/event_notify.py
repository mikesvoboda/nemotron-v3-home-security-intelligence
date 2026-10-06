"""EventNotifyDecision model: the persisted notify decision per event (ISS-001).

The VLM analyzer already MAKES the notify decision after an event commits
(spec section 6 via ``NotificationFilterService.should_notify``) and already
puts it on the WebSocket frame (``data.notify``, the exclude_if key). But a
WS frame is a moment, not a record: an operator who opens the dashboard ten
minutes later — or whose tab was closed when the event landed — cannot see
whether the system decided this event was worth notifying. The REST surface
carried nothing, so the decision vanished with the frame.

One row per DECIDED event records the boolean the filter returned, so the
same key a live consumer reads is also readable from ``GET /api/events``:
the row's presence is the semantic - no row means "no decision" (legacy
events, replay runs, events from other emitters), and ``false`` is a real
decision that must never be conflated with absence. That asymmetry
(false-present vs absent) is the whole contract, mirroring the
``verification`` field's exclude_if rule (backend/api/schemas/
event_verification.py): absence is not False.

Retention: same doctrine as event_verifications - cleanup_service
hard-deletes events and the FK cascades (the event_audits/
llm_interactions pattern), so an event delete takes the decision row with
it: never an orphan, never a 500.

Migration: none exists to write - this repo is `create_all`-only (Alembic
was removed in #4465; backend/core/database.py). create_all creates NEW
tables on an existing database and never ALTERS existing ones, so shipping
this model IS the migration; new tables are the sanctioned pattern the
event_verification.py docstring documents. The behavior is pinned by
backend/tests/integration/test_notify_decision_wiring.py.

Ruled provenance: docs/vss-integration/17-action-plan.md - ISS-001's
closure, on the OD-31 narrow reading (the persisted decision is what
"(or recorded delivery)" means), per the owner rulings in the 2026-10-05
Intake log entries.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.orm_utils import get_relationship_lazy_mode
from backend.core.time_utils import utc_now

from .camera import Base

if TYPE_CHECKING:
    from .event import Event


class EventNotifyDecision(Base):
    """The persisted notify decision for one event (ISS-001).

    ``notify`` is the boolean ``should_notify`` returned for the stored
    verdict - never a re-derivation at read time (a post-hoc preference edit
    must not rewrite an event's history; the OD-1 follow-up ruling's
    eliminated alternative).

    Relationships:
        - event: many-to-one to Event (event.notify_decision back_populates)

    Indexes:
        - idx_event_notify_decisions_event_id: the API serialization lookup
        - idx_event_notify_decisions_created_at: recency queries
    """

    __tablename__ = "event_notify_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # UNIQUE: one decision per event - a re-analysis of a coalesced batch
    # upserts the same row (the decision belongs to the event, not to the
    # run), unlike event_verifications where a repair path may stack rows.
    event_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # The stored decision. NULL is impossible by construction: a row means a
    # decision happened, so the column is NOT NULL and `false` is data.
    notify: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Which code path decided, for forensics only ("vlm" today): cheap, and
    # it keeps a future second producer honest about which rule fired.
    decided_by: Mapped[str] = mapped_column(String, nullable=False, default="vlm")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    event: Mapped[Event] = relationship(
        "Event",
        back_populates="notify_decision",
        # repo N+1 guard (dev/test = raise_on_sql); the API path reads the
        # row via Event.notify_decision (eager selectin), never this direction.
        lazy=get_relationship_lazy_mode(),
    )

    __table_args__ = (
        Index("idx_event_notify_decisions_event_id", "event_id"),
        Index("idx_event_notify_decisions_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<EventNotifyDecision(id={self.id}, event_id={self.event_id}, "
            f"notify={self.notify}, decided_by={self.decided_by!r})>"
        )


def notify_decision_value(event: object | None) -> bool | None:
    """Render the REST/WS `notify` value from an Event ORM row.

    Returns the stored boolean when a decision row exists, and None when it
    does not - None is what both consumers' exclude_if keys drop from the
    payload, so "no decision" stays ABSENT rather than becoming False (the
    presence contract shared with `verification`).

    The isinstance guard is deliberate, mirroring verification_payload:
    mocked events in unit tests carry MagicMock attributes, which are truthy
    but not real rows - only a loaded relationship ever produces a value.
    """
    row = getattr(event, "notify_decision", None) if event is not None else None
    if row is None or not isinstance(getattr(row, "notify", None), bool):
        return None
    return row.notify


__all__ = ["EventNotifyDecision", "notify_decision_value"]
