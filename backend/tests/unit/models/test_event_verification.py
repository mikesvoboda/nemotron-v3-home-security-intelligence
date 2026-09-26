"""P0.4 (spec §4): the `event_verifications` table model.

One row per vlm-mode event answers "what did the verifier see and say?" -
verdict, scene description, criteria, the key frames it reviewed, and the
engine/model/latency provenance. Legacy events have NO row (§4: "Legacy
events have no verification row"), which is why every consumer-side rule
(REST/WS `verification` field, the notification-filter pin) keys on row
presence, never on a defaulted verdict.

Retention doctrine (spec §4 + cleanup_service): production hard-deletes
events; the verification row follows the event (FK CASCADE, the same pattern
as event_audits/llm_interactions), so an event delete can never orphan-500.
Evaluation data does NOT live here - eval items are self-contained in the
eval store precisely because retention deletes production rows (D7).

Migration doctrine: this repo has NO alembic (removed in #4465; schema is
`create_all`-only, backend/core/database.py). `create_all` creates NEW
tables on an existing database and never alters existing ones - so a new
model is the entire "migration", and the create-new-tables-on-existing-DB
behavior itself is pinned by the integration tier
(tests/integration/test_p04_event_verifications.py).
"""

from __future__ import annotations

import pytest
from sqlalchemy import CheckConstraint, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.schema import CreateTable

from backend.models.camera import Base as ModelsBase
from backend.models.event import Event
from backend.models.event_verification import EventVerification

pytestmark = pytest.mark.unit


# =============================================================================
# Table shape (spec §4 column list, verbatim)
# =============================================================================


class TestTableShape:
    def test_table_registered_on_base(self):
        """The model joins Base.metadata - that IS the migration story here
        (create_all-only repo; no alembic chain to append)."""
        assert "event_verifications" in ModelsBase.metadata.tables

    def test_spec_columns_present(self):
        table = ModelsBase.metadata.tables["event_verifications"]
        expected = {
            "id",
            "event_id",
            "verdict",
            "scene_description",
            "criteria",
            "key_frame_detection_ids",
            "engine",
            "model_id",
            "latency_ms",
            "created_at",
        }
        columns = set(table.columns.keys())
        assert expected <= columns, sorted(expected ^ columns)

    def test_event_id_is_cascade_fk_to_events(self):
        """FK(event_id -> events.id) ON DELETE CASCADE: cleanup_service
        hard-deletes events (cleanup_service.py:294 area); the row must follow
        the event at the DB level so a delete never leaves an orphan and never
        500s the cleanup job."""
        table = ModelsBase.metadata.tables["event_verifications"]
        fks = [fk for fk in table.foreign_keys if fk.column.table.name == "events"]
        assert len(fks) == 1
        assert fks[0].ondelete == "CASCADE"

    def test_jsonb_columns(self):
        """criteria + key_frame_detection_ids are JSONB per spec §4."""
        table = ModelsBase.metadata.tables["event_verifications"]
        assert isinstance(table.columns["criteria"].type, JSONB)
        assert isinstance(table.columns["key_frame_detection_ids"].type, JSONB)

    def test_latency_ms_nullable_int(self):
        """NULL = the engine reported nothing (e.g. transport failure before
        any timed call) - spec §4 carries the column, §6 makes NULL honest."""
        table = ModelsBase.metadata.tables["event_verifications"]
        col = table.columns["latency_ms"]
        assert col.nullable is True

    def test_verdict_check_constraint(self):
        """verdict ∈ {confirmed, rejected, uncertain, verification_failed}
        (spec §4) - enforced at the DB, mirroring events' ck_events_risk_level
        style for enum-ish string columns."""
        table = ModelsBase.metadata.tables["event_verifications"]
        checks = [c.sqltext.text for c in table.constraints if isinstance(c, CheckConstraint)]
        joined = " ".join(checks)
        for value in ("confirmed", "rejected", "uncertain", "verification_failed"):
            assert value in joined

    def test_event_id_indexed(self):
        """Every API/WS serialization path looks a row up by event_id."""
        table = ModelsBase.metadata.tables["event_verifications"]
        indexed_cols = {c.name for idx in table.indexes for c in idx.columns}
        assert "event_id" in indexed_cols

    def test_dialect_ddl_compiles(self):
        """Sanity: the table compiles for postgres (JSONB) - the tier that
        actually runs it."""
        from sqlalchemy.dialects import postgresql

        table = ModelsBase.metadata.tables["event_verifications"]
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert "event_verifications" in ddl
        assert "JSONB" in ddl.upper()


# =============================================================================
# Row construction (in-Python; DB behavior is the integration tier)
# =============================================================================


class TestRowConstruction:
    def test_minimal_row(self):
        row = EventVerification(
            event_id=7,
            verdict="verification_failed",
            engine="llama.cpp",
            model_id="qwen3-vl-4b",
        )
        assert row.verdict == "verification_failed"
        assert row.criteria is None
        assert row.key_frame_detection_ids is None
        assert row.latency_ms is None

    def test_full_row(self):
        row = EventVerification(
            event_id=7,
            verdict="confirmed",
            scene_description="Person at front door carrying a parcel",
            criteria=[{"name": "person_present", "passed": True, "evidence": "front porch"}],
            key_frame_detection_ids=[11, 12],
            engine="llama.cpp",
            model_id="qwen3-vl-4b",
            latency_ms=1400,
        )
        assert row.criteria[0]["passed"] is True
        assert row.key_frame_detection_ids == [11, 12]
        assert row.latency_ms == 1400

    def test_event_relationship_backref(self):
        """Event.verifications exists (uselist=True, delete-orphan cascade
        mirroring the DB-level CASCADE) so the ORM path agrees with SQL."""
        assert hasattr(Event, "verifications")
        rel = Event.verifications.property
        assert rel.uselist is True
        assert "delete-orphan" in str(rel.cascade)

    def test_repr_is_informative(self):
        row = EventVerification(event_id=3, verdict="rejected", engine="llama.cpp", model_id="m")
        assert "event_id=3" in repr(row)
        assert "rejected" in repr(row)


# =============================================================================
# 1.6: the FILTER vocabulary and its SQL condition. Both the list and the
# search route build `?verdict=` from this one module, so the vocabulary and
# the EXISTS shape are pinned here rather than in either route's tests.
# =============================================================================


class TestVerdictFilterVocabulary:
    def test_filter_values_are_the_four_verdicts_plus_none(self) -> None:
        """`none` is a pseudo-value meaning "no verification row" — the one
        question a verdict column cannot answer, and the first thing an
        operator asks in a fresh vlm deployment."""
        from backend.models.event_verification import (
            VERDICT_FILTER_VALUES,
            VERDICT_VALUES,
        )

        assert VERDICT_VALUES == ("confirmed", "rejected", "uncertain", "verification_failed")
        assert set(VERDICT_FILTER_VALUES) == set(VERDICT_VALUES) | {"none"}

    def test_the_check_constraint_is_narrower_than_the_filter(self) -> None:
        """Deliberate asymmetry: 'none' filters on row ABSENCE, so a stored
        row may never carry it. If these two lists ever become equal, the
        CHECK has silently widened to accept a non-verdict."""
        from backend.models.event_verification import VERDICT_FILTER_VALUES

        table = ModelsBase.metadata.tables["event_verifications"]
        checks = [c.sqltext.text for c in table.constraints if isinstance(c, CheckConstraint)]
        joined = " ".join(checks)
        assert "none" not in joined.split()
        assert "none" in VERDICT_FILTER_VALUES

    def test_condition_compiles_for_postgres(self) -> None:
        """The real shape is EXISTS on the relationship (the verdict has no
        column on Event), and 'none' is its negation — both must compile,
        and each names the verification table exactly once."""
        from sqlalchemy.dialects import postgresql

        from backend.models.event import Event
        from backend.models.event_verification import verdict_filter_condition

        real = str(
            select(Event.id)
            .where(verdict_filter_condition("rejected"))
            .compile(dialect=postgresql.dialect())
        )
        none = str(
            select(Event.id)
            .where(verdict_filter_condition("none"))
            .compile(dialect=postgresql.dialect())
        )
        assert "event_verifications" in real and "event_verifications" in none
        # SQLAlchemy renders the negation as `NOT (EXISTS ...)`
        assert "EXISTS" in real and "NOT" not in real
        assert "NOT (EXISTS" in none

    def test_none_is_the_only_negated_form(self) -> None:
        """A real verdict filter must NOT be negated - a silent inversion
        would make ?verdict=rejected return everything BUT rejected."""
        from sqlalchemy.dialects import postgresql

        from backend.models.event import Event
        from backend.models.event_verification import VERDICT_VALUES, verdict_filter_condition

        for verdict in VERDICT_VALUES:
            sql = str(
                select(Event.id)
                .where(verdict_filter_condition(verdict))
                .compile(dialect=postgresql.dialect())
            )
            assert "NOT (EXISTS" not in sql
            assert "verdict =" in sql
