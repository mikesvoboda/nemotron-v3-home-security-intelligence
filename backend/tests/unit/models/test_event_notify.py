"""Unit tests for the EventNotifyDecision model and its REST value helper.

The model is the record ISS-001's OD-31 closure names "(or recorded
delivery)": one row per decided event, so the notify answer a live WS
consumer read for one frame is still readable from GET /api/events
afterwards. The end-to-end wiring (row written by the analyzer, surfaced on
both REST surfaces) is pinned in
backend/tests/integration/test_notify_decision_wiring.py - a live-DB tier.
This file pins what a unit tier can see without a database:

  - the table shape that carries the contract: UNIQUE(event_id) is the
    one-decision-per-event rule (a re-analysis UPSERTS this row, unlike
    event_verifications, which may stack - the docstring says so; the
    constraint is the sentence), notify NOT NULL (a row IS a decision; a
    nullable boolean would let "no decision" creep in as a null row), and
    the CASCADE FK (the retention doctrine: cleanup hard-deletes events and
    the decision row goes with it - never an orphan, never a 500);
  - notify_decision_value's presence matrix - the helper is the single
    place an ORM row becomes the REST/WS `notify` value, and the whole
    asymmetry lives here: true and false are decisions (both render), no
    row means "no decision was made" (renders None, which exclude_if drops
    from the payload - absence is never False), and a mocked event must
    render None rather than a truthy MagicMock (the guard mirrors
    verification_payload's, for the same reason: unit tests carry mocks,
    production carries rows).
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Boolean, DateTime, Integer

from backend.models.event_notify import EventNotifyDecision, notify_decision_value

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def decision_row():
    """A constructed (never flushed) decision row - attribute-level only."""
    return EventNotifyDecision(
        id=1,
        event_id=42,
        notify=True,
        decided_by="vlm",
        created_at=datetime(2026, 10, 5, 12, 0, 0, tzinfo=UTC),
    )


# =============================================================================
# Table shape - the contract the docstring states
# =============================================================================


class TestTableShape:
    def test_tablename(self):
        assert EventNotifyDecision.__tablename__ == "event_notify_decisions"

    def test_event_id_is_unique_one_decision_per_event(self):
        """UNIQUE(event_id) is the upsert target and the per-event rule.

        The analyzer's persist path does an on_conflict_do_update against
        exactly this constraint; without it a re-analyzed batch would
        append a second row and the relationship would become ambiguous.
        """
        column = EventNotifyDecision.__table__.c.event_id
        assert column.unique is True

    def test_event_id_fk_cascades_on_delete(self):
        """Retention: an event delete takes the decision row with it."""
        column = EventNotifyDecision.__table__.c.event_id
        fk = next(fk for fk in column.foreign_keys)
        assert fk.target_fullname == "events.id"
        assert fk.ondelete == "CASCADE"

    def test_notify_is_not_null_false_is_data(self):
        """A row means a decision happened - `false` must survive storage.

        If this column ever becomes nullable, "no decision" gains a second
        encoding (a null row) and the REST absence contract forks. That is
        the fork this pin is here to catch.
        """
        column = EventNotifyDecision.__table__.c.notify
        assert column.nullable is False
        assert isinstance(column.type, Boolean)

    def test_decided_by_is_not_null(self):
        column = EventNotifyDecision.__table__.c.decided_by
        assert column.nullable is False

    def test_defaults_the_vlm_producer_and_the_clock(self):
        """decided_by is forensics ("vlm" today); created_at is server-side-ish.

        The defaults are read off the column objects, not an instance: a
        constructed-but-unflushed instance has not run them yet (SQLAlchemy
        applies column defaults at INSERT), which is precisely why the
        helper below does not rely on either.
        """
        assert EventNotifyDecision.__table__.c.decided_by.default.arg == "vlm"
        created = EventNotifyDecision.__table__.c.created_at
        assert isinstance(created.type, DateTime)
        assert created.type.timezone is True
        # utc_now is callable (a Python-side default), not a fixed value
        assert callable(created.default.arg)

    def test_event_id_is_integer_pk_is_separate(self):
        """The surrogate id exists so event_id can be the UNIQUE, not the PK."""
        assert isinstance(EventNotifyDecision.__table__.c.id.type, Integer)
        assert EventNotifyDecision.__table__.c.id.primary_key is True


class TestRelationshipShape:
    def test_back_populates_event(self):
        rel = EventNotifyDecision.__mapper__.relationships["event"]
        assert rel.back_populates == "notify_decision"
        assert rel.uselist is False


class TestRepr:
    def test_repr_names_the_fields_that_matter(self, decision_row):
        text = repr(decision_row)
        assert "EventNotifyDecision" in text
        assert "event_id=42" in text
        assert "notify=True" in text
        assert "'vlm'" in text


# =============================================================================
# notify_decision_value - the presence matrix
# =============================================================================


class TestNotifyDecisionValue:
    def test_true_decision_renders_true(self):
        event = MagicMock()
        event.notify_decision.notify = True
        assert notify_decision_value(event) is True

    def test_false_decision_renders_false_not_none(self):
        """The arm that makes 'why was I not paged?' answerable."""
        event = MagicMock()
        event.notify_decision.notify = False
        assert notify_decision_value(event) is False

    def test_no_row_renders_none_absence_is_not_false(self):
        event = MagicMock()
        event.notify_decision = None
        assert notify_decision_value(event) is None

    def test_none_event_renders_none(self):
        assert notify_decision_value(None) is None

    def test_magicmock_event_renders_none_not_a_truthy_mock(self):
        """The reason the isinstance guard exists.

        A bare MagicMock answers EVERY attribute, so `getattr(row, "notify")`
        is a truthy Mock, not a bool - a helper without the guard would put
        a Mock (or, serialized, garbage) where production puts a decision.
        Only a real bool - a loaded row - produces a value.
        """
        assert notify_decision_value(MagicMock()) is None

    def test_non_bool_stored_value_renders_none(self):
        """A row whose notify is not a bool (a hand-built stand-in, a test
        double that modeled it wrong) is not a decision either."""
        event = MagicMock()
        event.notify_decision.notify = "true"
        assert notify_decision_value(event) is None
        event.notify_decision.notify = 1
        assert notify_decision_value(event) is None

    def test_result_is_always_bool_or_none(self):
        """The declared return type, pinned at both decision arms: the
        exclude_if on the REST field fires on `is None` only, so anything
        other than bool/None here would ship as a truthy non-boolean."""
        for value in (True, False):
            event = MagicMock()
            event.notify_decision.notify = value
            assert isinstance(notify_decision_value(event), bool)
        assert notify_decision_value(MagicMock()) is None

    def test_row_without_notify_attribute_renders_none(self):
        row = object()  # no .notify at all
        event = MagicMock()
        event.notify_decision = row
        assert notify_decision_value(event) is None
