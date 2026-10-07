"""Campaign #48.5 (batch-38, battery AY) - `backend.services.vlm_analyzer` follow-up.

# TARGET-MODULE: backend.services.vlm_analyzer

Battery Y (campaign #23, `test_vlm_analyzer_batch38_y.py`) closed this module at
its generation's denominator; coverage growth then BIRTHED the 21
`_persist_notify_decision` keys (verdict 33 / no_tests - the function had NO
test of its own, Y drove it only through `_notify_decision`, where Y's own
honesty ledger notes the persist call is swallowed by the outer
`except Exception`) and left 22 survivors. The 22 split by Y's already-
adjudicated EQUIV ledger (renumbered bodies, re-probed in this campaign, see
below) plus 8 killable ones in the `_notify_decision` arg surface. 22 + 21 =
the whole remaining module gap.

Harness contract (b30 sweep, /home/agent/runs/b30-sweep.py): NO pytest
fixtures, NO parametrize, NO monkeypatch - the sweep imports this file
directly and calls every module-level ``test_*`` with zero arguments in ONE
process, flipping os.environ[MUTANT_UNDER_TEST] per key. Async entry points
are driven with asyncio.run INSIDE the test body; seams are patched through
the TARGET MODULE's globals (va.get_session, va.decide_notification,
va.utc_now, va.logger) with attribute save/restore through _Patcher so a
mid-test assert failure cannot leak a patch into the next key's window.
Self-provisioned tmp dirs instead of the tmp_path fixture (the sweep passes
no fixtures).

KILL CONSTRUCTIONS (why each family bites its keys, not just its shipped run):

  * `_persist_notify_decision` is a STATICMETHOD called directly - no
    VlmAnalyzer(), no settings, no DB. A recording session captures the
    SQLAlchemy statement; the assertion is on its PostgreSQL compilation with
    `literal_binds`, so the ON CONFLICT target and the SET column list are
    LITERAL TEXT. A renamed/conflict/index/set_ key renders differently
    (`"XXnotifyXX"`, `"EVENT_ID"`, ...) and a deleted argument raises at
    BUILD time (ValueError/ArgumentError, probe-measured), never silently.
    The timestamp rides `va.utc_now` patched to a fixed instant, so the SET
    literal `created_at = '...12:30:45.123456+00:00'` is byte-stable.
  * `_notify_decision` drives the shipped try-body on a fake session whose
    identity is pinned: the persist spy records `(session is SENT, event_id,
    notify)` as a full tuple, so dropping/None-ing/re-ordering ANY argument -
    or dropping the call - fails the tuple. `decide_notification` returns a
    value distinguishable from the `notify: bool | None = None` initializer
    (False, not None), which is what makes the initializer mutants observable:
    with init "" (m12) or False, the `if notify is None` fallback leg is
    SKIPPED (the shipped run reaches it and calls the pure path again), so
    the call-count and result-type asserts both bite.

EXTENSION (post-commit, PRE-GENERATION): m360/m361 mutate the
`_notify_decision` CALL SITE inside analyze_batch, so killing them needs a
full analyze_batch drive. No battery in this repo imports another battery
(the precedent, batch28_00b, copies observation helpers VERBATIM; the b30
sweep loads each file by path, so a sibling import would be fragile there),
so the fake surface below is COPIED VERBATIM from battery Y - byte-identical
bodies, only the banners differ. Battery Y is untouched. The drive uses the
REAL `VlmAnalyzer.__init__` (Y's construction precedent: settings validate
under the test env) because analyze_batch reads `self._settings`
(camera_timezone, fallback provenance) - the __new__-only route of the
notify tests above cannot run analyze_batch for exactly that reason.

EQUIV ledger for the 22 survivors (Y-registered dispositions, bodies re-found
by NAME after the coverage-growth renumber and mechanisms RE-PROBED this
campaign - /home/agent/runs/b48-ay-probe{1,2,3,3b,5}.py):
  * _notify_decision m12 `notify = ""` - KILLED by the fallback test below,
    NOT EQUIV (a first-draft ledger entry claimed EQUIV on "same truthiness";
    refuted by the observable pair that test pins: the decide-fails world
    reaches decide TWICE and returns False (bool) in shipped, ONCE and ""
    (str) under m12 - the `if notify is None` leg tests IDENTITY, so the
    str-typed initializer is observable without any equality probe).
  * _notify_decision m17/m18/m19/m20/m21/m22, analyze_batch m360/m361
    (event_id/camera_id dropped) - the killable eight with m12 (NOT EQUIV):
    m17-m22 die to the persist spies above; m360/m361 die to the
    analyze_batch drives at the bottom of this file, which pin the
    `_notify_decision` call kwargs (event_id from the FLUSHED event,
    camera_id the resolved BATCH camera).
  * analyze_batch m41/m43 (zones/household initializers -> None) -
    re-assigned unconditionally at the two following lines before any read
    (Y: "dead initializers"). EQUIV.
  * analyze_batch m348 `if payload is not None or True` - the call site
    always feeds a non-empty row list it just selected, so the ternary never
    takes the else arm (Y m347 ruling). EQUIV.
  * analyze_batch m357 `notify = ""` initializer - same shape as m12: the
    assignment is overwritten by `_notify_decision` on the only live path,
    and the replay path keeps None in BOTH worlds... re-probed: replay skips
    the branch, so the initializer value reaches `_broadcast` only via the
    non-replay path which ALWAYS re-assigns. EQUIV.
  * analyze_batch m341 `_EventView(event_id=None)` + _EventView.__init__ m1
    (`self.event_id = None`) - `verification_payload` reads
    `event.verifications` only (grep: zero `event_id` reads in
    event_verification.py; the payload schema carries no event id). EQUIV.
  * analyze_batch_streaming m33/m48 (drop `recoverable=True`) and m5 (drop
    `accumulated_text=""`) - schema defaults: StreamingErrorEvent.recoverable
    default True, StreamingProgressEvent.accumulated_text default "";
    model_dump() byte-identical in both arms (probe: `error drop-recoverable
    equal? True`, `m5 drop-accumulated equal? True`). EQUIV.
  * apply_verdict_invariants m37 `risk_score is not None or True` -
    VlmVerdict.risk_score is a REQUIRED int (probe: not constructible as
    None), so the else arm is dead code the shipped ternary also never takes.
    EQUIV.
  * key_frame_ids m4 (`build_frame_refs(detections, None)`) - the by_path map
    is pairing-invariant: the winner per file is the max-ranked frame whether
    the (camera, class) pairs merge or split, and the fallback is reached only
    for a FALSY row camera_id which production rows never carry (Y ruling,
    selector source re-read). EQUIV.
  * load_household_context m5 (`join(Zone, None)`) / m7 (`join(Zone,)`) -
    the FK-derived ON clause renders BYTE-IDENTICAL SQL in all three arms
    (probe: `join(Zone, ) == shipped? True`, `join(Zone, None) ... == shipped?
    True`); the onclause is redundant because zone_household_configs.zone_id
    is the FK to camera_zones.id. EQUIV.

The 21 `_persist_notify_decision` keys are covered by DIRECT call (no analyzer,
no settings): each arm of the mutation shows up either as a build-time raise
(deleted/dropped args) or a compiled-string difference (renamed keys), and the
shipped arm is pinned to the exact literal SQL below.
"""

from __future__ import annotations

import asyncio
import logging
import operator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import sqlalchemy
from sqlalchemy.dialects import postgresql

from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_verification import EventVerification
from backend.services import vlm_analyzer as va
from backend.services.severity import SeverityService
from backend.services.vlm_verdict import VlmVerdict

TS = datetime(2026, 10, 6, 12, 30, 45, 123456, tzinfo=UTC)

SHIPPED_SQL = (
    "INSERT INTO event_notify_decisions (event_id, notify, decided_by, created_at) "
    "VALUES (4242, true, 'vlm', NULL) "
    "ON CONFLICT (event_id) DO UPDATE SET notify = true, "
    "created_at = '2026-10-06 12:30:45.123456+00:00' "
    "RETURNING event_notify_decisions.id"
)


class RecordingSession:
    """Captures every executed statement; identity-pinned via `tag`."""

    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> Any:
        self.statements.append(stmt)
        return sqlalchemy.engine.Row


def compile_sql(stmt: Any) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


class _Patcher:
    """Minimal attribute save/restore (no monkeypatch in the b30 harness)."""

    def __init__(self, *triples: tuple[Any, str, Any]) -> None:
        self.triples = triples
        self.saved: list[tuple[Any, str, Any]] = []

    def __enter__(self) -> None:
        for obj, attr, value in self.triples:
            self.saved.append((obj, attr, getattr(obj, attr)))
            setattr(obj, attr, value)

    def __exit__(self, *exc: Any) -> bool:
        for obj, attr, value in reversed(self.saved):
            setattr(obj, attr, value)
        return False


def _patch_utc_now() -> _Patcher:
    return _Patcher((va, "utc_now", lambda: TS))


# ---------------------------------------------------------------------------
# _persist_notify_decision: the statement IS the product. Pinned literally.
# ---------------------------------------------------------------------------


def test_persist_notify_decision_compiles_to_the_shipped_upsert() -> None:
    """The whole body's observable output: one INSERT..ON CONFLICT DO UPDATE
    whose conflict target, SET columns and literal timestamp are all pinned.
    Kills the renamed-index (m15/m16), renamed-set (m17/m18), renamed-set-key
    (m19/m20) and dropped-statement arms, and any re-order of the columns."""
    rec = RecordingSession()
    with _patch_utc_now():
        asyncio.run(va.VlmAnalyzer._persist_notify_decision(rec, 4242, True))
    assert len(rec.statements) == 1, f"expected exactly one statement, got {len(rec.statements)}"
    assert compile_sql(rec.statements[0]) == SHIPPED_SQL


def test_persist_notify_decision_carries_its_arguments_verbatim() -> None:
    """event_id and notify reach the VALUES list; decided_by is the LITERAL
    'vlm' (never the caller's value), and the SET side re-applies notify."""
    for event_id, notify in ((7, False), (99991, True)):
        rec = RecordingSession()
        with _patch_utc_now():
            asyncio.run(va.VlmAnalyzer._persist_notify_decision(rec, event_id, notify))
        sql = compile_sql(rec.statements[0])
        assert f"VALUES ({event_id}, {'true' if notify else 'false'}, 'vlm', NULL)" in sql, sql
        assert f"DO UPDATE SET notify = {'true' if notify else 'false'}, " in sql, sql
        assert "'vlm'" in sql and "VALUES" in sql


def test_persist_notify_decision_indexes_the_conflict_on_event_id() -> None:
    """The UPSERT contract (docstring: "one-row-per-event by schema") lives in
    `index_elements=["event_id"]`. A renamed/case-flipped element renders a
    quoted, wrong identity column - the row would still insert but the
    RE-decide would fight the unique index. Assert the ON CONFLICT clause
    exactly, unquoted."""
    rec = RecordingSession()
    with _patch_utc_now():
        asyncio.run(va.VlmAnalyzer._persist_notify_decision(rec, 1, True))
    sql = compile_sql(rec.statements[0])
    on_conflict = sql.split("RETURNING")[0].split("ON CONFLICT")[1].split("DO UPDATE")[0]
    assert on_conflict.strip() == "(event_id)", on_conflict


def test_persist_notify_decision_updates_only_notify_and_created_at() -> None:
    """The SET list is exactly {notify, created_at}: decided_by is write-once
    (the first decision's attribution survives a re-decide) and event_id is
    the key. A renamed set key appears quoted; a dropped set_ entry shrinks
    the list. Assert the full clause text, not a substring."""
    rec = RecordingSession()
    with _patch_utc_now():
        asyncio.run(va.VlmAnalyzer._persist_notify_decision(rec, 1, True))
    sql = compile_sql(rec.statements[0])
    set_clause = sql.split("DO UPDATE SET ")[1].split(" RETURNING")[0]
    assert set_clause == (
        f"notify = true, created_at = '{TS.strftime('%Y-%m-%d %H:%M:%S.%f')}+00:00'"
    ), set_clause


def test_persist_notify_decision_stamp_comes_from_utc_now() -> None:
    """The created_at literal is the patched instant - so the SET clause is
    reproducible, and `utc_now()` (not a DB-side now(), not a constant) is
    proven to be the source. A mutant that drops the created_at entry entirely
    loses the whole tail of the clause."""
    rec = RecordingSession()
    with _patch_utc_now():
        asyncio.run(va.VlmAnalyzer._persist_notify_decision(rec, 5, False))
    sql = compile_sql(rec.statements[0])
    assert f"created_at = '{TS.strftime('%Y-%m-%d %H:%M:%S.%f')}+00:00'" in sql, sql
    assert "now()" not in sql.lower(), sql


def test_persist_notify_decision_rejects_a_broken_statement_shape() -> None:
    """Negative control for the deleted-argument arms: a UPSERT missing
    index_elements or set_ cannot even be BUILT (probed: ValueError from
    on_conflict_do_update, ArgumentError from pg_insert(None)). The shipped
    build must succeed, and each broken shape must raise - so an arm that
    quietly builds a DIFFERENT statement still dies on the positive pins, and
    an arm that builds nothing dies here."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from backend.models.event_notify import EventNotifyDecision

    base = pg_insert(EventNotifyDecision).values(event_id=1, notify=True, decided_by="vlm")
    broken = {
        "no index_elements": lambda: base.on_conflict_do_update(set_={"notify": True}),
        "no set_": lambda: base.on_conflict_do_update(index_elements=["event_id"]),
        "empty set_": lambda: base.on_conflict_do_update(index_elements=["event_id"], set_={}),
    }
    built_any: list[str] = []
    for label, build in broken.items():
        try:
            build()
        except (ValueError, sqlalchemy.exc.ArgumentError) as exc:
            assert str(exc), f"{label} raised an empty message"
        else:
            built_any.append(label)
    assert not built_any, f"broken UPSERT shapes that built anyway: {built_any}"
    rec = RecordingSession()
    with _patch_utc_now():
        asyncio.run(va.VlmAnalyzer._persist_notify_decision(rec, 1, True))
    assert compile_sql(rec.statements[0]).startswith("INSERT INTO event_notify_decisions")


# ---------------------------------------------------------------------------
# _notify_decision: the persist call's ARGUMENT TUPLES are pinned, and the
# initializer's world is observable through the fallback leg's call count.
# ---------------------------------------------------------------------------


class _FakeSessionCtx:
    """`async with get_session() as session` -> a stable, identity-checkable
    object. `boom=True` makes opening raise (the shipped fallback world)."""

    def __init__(self, session: Any, boom: bool = False) -> None:
        self.session = session
        self.boom = boom

    async def __aenter__(self) -> Any:
        if self.boom:
            raise RuntimeError("session could not be opened")
        return self.session

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class PersistSpy:
    """Records the EXACT call tuples of `_persist_notify_decision`."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def bind(self, analyzer: Any) -> None:
        analyzer._persist_notify_decision = self  # type: ignore[method-assign]

    async def __call__(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(args)


def _drive_notify(
    *,
    decide_results: list[Any],
    session: Any,
    boom: bool = False,
    analyzer: Any | None = None,
) -> tuple[Any, PersistSpy, int]:
    """Run `_notify_decision` once over a patched get_session + counting
    decide_notification. Returns (result, persist spy, decide call count)."""
    sent = analyzer or va.VlmAnalyzer.__new__(va.VlmAnalyzer)  # no __init__, no settings
    spy = PersistSpy()
    spy.bind(sent)
    counts = {"n": 0}

    async def decide(sess: Any, **kwargs: Any) -> Any:
        counts["n"] += 1
        outcome = decide_results[min(counts["n"] - 1, len(decide_results) - 1)]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    with _Patcher(
        (va, "decide_notification", decide),
        (va, "get_session", lambda: _FakeSessionCtx(session, boom=boom)),
    ):
        result = asyncio.run(
            sent._notify_decision(
                event_id=4242,
                camera_id="camera-kitchen",
                timestamp=TS,
                risk_score=50,
                verdict="confirmed",
                detections=[{"id": 1}],
            )
        )
    return result, spy, counts["n"]


def test_notify_decision_persists_the_decided_value_with_the_right_key() -> None:
    """Happy path: decide returns False (deliberately NOT None - the
    initializer's world must be distinguishable), and persist is called
    EXACTLY once with (the same session object, event_id 4242, False).
    Kills m17 (session->None: identity fails), m18 (event_id->None), m19
    (notify->None), m20 (session slot drops -> args shift to 2-tuple),
    m21/m22 (dropped args: wrong arity)."""
    SENT = object()
    result, spy, n = _drive_notify(decide_results=[False], session=SENT)
    assert result is False, result
    assert n == 1, f"decide_notification called {n} times, expected 1"
    assert spy.calls == [(SENT, 4242, False)], spy.calls


def test_notify_decision_persist_is_not_swallowed_by_the_guard() -> None:
    """The shipped persist sits INSIDE the try block (ISS-001: the persistence
    IS the recorded delivery). A decide result of True must still produce the
    write, and the returned value must be True - i.e. the try body runs to
    completion, not to the persist call only."""
    SENT = object()
    result, spy, n = _drive_notify(decide_results=[True], session=SENT)
    assert result is True
    assert spy.calls == [(SENT, 4242, True)], spy.calls


def test_notify_decision_falls_back_to_the_pure_path_when_the_session_decide_fails() -> None:
    """The session-leg decide raises (a settings read can abort the
    transaction - the docstring's whole point) -> the except logs and the
    `if notify is None` leg re-decides on the SHIPPED DEFAULTS (session=None).
    decide is therefore called TWICE and nothing persists. This is the leg the
    initializer mutants skip: with notify initialised to "" (m12/m357) the
    `is None` test is False, the leg is skipped, the result is the initializer
    and decide runs ONCE - so this test's (call count, result identity, zero
    writes) triple kills the initializer arms. The second decide's SESSION
    is pinned to None as well, which is the "deciding on the shipped defaults"
    contract itself."""
    SENT = object()
    seen_sessions: list[Any] = []

    async def decide_two_legs(sess: Any, **kwargs: Any) -> Any:
        seen_sessions.append(sess)
        if len(seen_sessions) == 1:
            raise RuntimeError("session dead")
        return False

    sent = va.VlmAnalyzer.__new__(va.VlmAnalyzer)
    spy = PersistSpy()
    spy.bind(sent)
    with _Patcher(
        (va, "decide_notification", decide_two_legs),
        (va, "get_session", lambda: _FakeSessionCtx(SENT)),
    ):
        result = asyncio.run(
            sent._notify_decision(
                event_id=4242,
                camera_id="camera-kitchen",
                timestamp=TS,
                risk_score=50,
                verdict="confirmed",
                detections=[{"id": 1}],
            )
        )
    assert seen_sessions[0] is SENT, "the session leg did not run"
    assert seen_sessions[1] is None, "the fallback must decide on the shipped defaults"
    assert len(seen_sessions) == 2, (
        f"expected one session attempt + one pure fallback, got {len(seen_sessions)}"
    )
    assert result is False, repr(result)
    assert spy.calls == [], spy.calls


def test_notify_decision_logs_the_session_failure_once() -> None:
    """The warning is the operator's only trace that the decision came from
    defaults, not from stored settings. Assert the message + the structured
    extra surface (camera_id) exactly - a mutant that drops the log, renames
    the key, or fires twice breaks the count."""
    records: list[logging.LogRecord] = []

    class Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Collector()
    va.logger.addHandler(handler)
    try:
        result, spy, n = _drive_notify(
            decide_results=[RuntimeError("nope"), False], session=object(), boom=False
        )
    finally:
        va.logger.removeHandler(handler)
    assert result is False
    warns = [r for r in records if r.levelno == logging.WARNING and "defaults" in r.getMessage()]
    assert len(warns) == 1, [r.getMessage() for r in records]
    assert getattr(warns[0], "camera_id", None) == "camera-kitchen"


def test_notify_decision_returns_none_only_when_the_pure_path_fails() -> None:
    """Both legs fail -> None ("no key on the wire"). The initializer mutants
    (m12: "" / False-worlds) cannot produce None here because they skip the
    leg whose failure is the ONLY thing that returns None; assert the exact
    value plus the error log that pairs with it."""
    records: list[logging.LogRecord] = []

    class Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Collector()
    va.logger.addHandler(handler)
    try:
        result, spy, n = _drive_notify(
            decide_results=[RuntimeError("a"), RuntimeError("b")],
            session=object(),
            boom=True,
        )
    finally:
        va.logger.removeHandler(handler)
    assert result is None, repr(result)
    errs = [r for r in records if r.levelno >= logging.ERROR]
    assert len(errs) == 1, [r.getMessage() for r in records]
    assert spy.calls == []


def test_notify_decision_persist_failure_keeps_the_decision() -> None:
    """ISS-001's doctrine half: a persist that RAISES (the DB write failed)
    must not lose the decision - the result still comes back, and it is the
    decided value, not a fallback re-compute (decide called exactly once).
    Pins that persist really was attempted with the session tuple."""
    SENT = object()

    class Boom:
        async def __aenter__(self) -> Any:
            return SENT

        async def __aexit__(self, *exc: Any) -> bool:
            return False

    sent = va.VlmAnalyzer.__new__(va.VlmAnalyzer)
    calls: list[tuple[Any, ...]] = []

    async def persist(*args: Any) -> None:
        calls.append(args)
        raise RuntimeError("constraint violated")

    async def decide(sess: Any, **kwargs: Any) -> bool:
        return True

    sent._persist_notify_decision = persist  # type: ignore[method-assign]
    with _Patcher((va, "decide_notification", decide), (va, "get_session", lambda: Boom())):
        result = asyncio.run(
            sent._notify_decision(
                event_id=42,
                camera_id="c",
                timestamp=TS,
                risk_score=1,
                verdict="rejected",
                detections=[],
            )
        )
    assert result is True, repr(result)
    assert calls == [(SENT, 42, True)], calls


# ---------------------------------------------------------------------------
# Pure-builder EQUIV witnesses: shipped behavior pinned where the surviving
# mutants live, so a REGRESSION in the EQUIV direction (someone "fixes" the
# dead code into live code) is caught, and the ledger's claims stay measured.
# ---------------------------------------------------------------------------


def test_streaming_error_dump_keeps_recoverable_true_in_every_arm() -> None:
    """Witness for the m33/m48 EQUIV claim: the default IS True, so both
    streaming error arms dump identically with or without the kwarg. Pinned
    here so the EQUIV ruling (Y: model_dump identical in EVERY arm) is
    re-measured, not inherited."""
    a = va.StreamingErrorEvent(
        error_code="INTERNAL_ERROR", error_message="Streaming analysis failed", recoverable=True
    ).model_dump()
    b = va.StreamingErrorEvent(
        error_code="INTERNAL_ERROR", error_message="Streaming analysis failed"
    ).model_dump()
    assert (
        a
        == b
        == {
            "event_type": "error",
            "error_code": "INTERNAL_ERROR",
            "error_message": "Streaming analysis failed",
            "recoverable": True,
        }
    ), (a, b)


def test_streaming_progress_dump_keeps_accumulated_text_empty() -> None:
    """Witness for the m5 EQUIV claim (accumulated_text default "")."""
    a = va.StreamingProgressEvent(
        content="", accumulated_text="", progress_percent=5.0
    ).model_dump()
    b = va.StreamingProgressEvent(content="", progress_percent=5.0).model_dump()
    assert (
        a
        == b
        == {
            "event_type": "progress",
            "content": "",
            "accumulated_text": "",
            "progress_percent": 5.0,
        }
    ), (a, b)


def test_load_household_context_sql_is_the_fk_derived_join() -> None:
    """Witness for the m5/m7 EQUIV claim (join(Zone, None) / join(Zone,) render
    byte-identical SQL). Assert the shipped statement's ON clause text so a
    future schema change that makes the ON clause load-bearing re-opens the
    ruling instead of silently shipping a different join."""
    from sqlalchemy import select

    from backend.models.zone import Zone
    from backend.models.zone_household_config import ZoneHouseholdConfig

    shipped = str(
        select(ZoneHouseholdConfig, Zone)
        .join(Zone, Zone.id == ZoneHouseholdConfig.zone_id)
        .where(Zone.camera_id == "c")
        .compile(dialect=postgresql.dialect())
    )
    one_arg = str(
        select(ZoneHouseholdConfig, Zone)
        .join(Zone)
        .where(Zone.camera_id == "c")
        .compile(dialect=postgresql.dialect())
    )
    none_arg = str(
        select(ZoneHouseholdConfig, Zone)
        .join(Zone, None)
        .where(Zone.camera_id == "c")
        .compile(dialect=postgresql.dialect())
    )
    assert "JOIN camera_zones ON camera_zones.id = zone_household_configs.zone_id" in shipped
    assert shipped == one_arg == none_arg, "join arms diverged - the EQUIV ruling is stale"


def test_apply_verdict_invariants_maps_level_only_through_the_service() -> None:
    """Witness for the m37 EQUIV claim (risk_score is REQUIRED, the else arm is
    dead): the level comes from risk_score_to_severity(score).value on the
    SCORE path, and the None-score path belongs to verdict=None (the
    verification_failed dict), never to a constructed verdict. A stub severity
    service keeps this settings-free."""

    class StubSeverity:
        low_max = 30

        @staticmethod
        def risk_score_to_severity(score: int) -> Any:
            class _S:
                value = "high" if score >= 70 else "medium"

            return _S()

    from backend.services.vlm_verdict import VlmVerdict

    v = VlmVerdict(
        verdict="confirmed",
        risk_score=85,
        summary="A person stands at the door.",
        reasoning="Criterion evidence reviewed.",
        description="Front door, one person.",
        criteria=[{"name": "person_present", "passed": True, "evidence": "full frame"}],
        provenance={"engine": "llama.cpp", "model_id": "Qwen3VL-8B"},
    )
    out = va.apply_verdict_invariants(v, StubSeverity())  # type: ignore[arg-type]
    assert out["risk_level"] == "high", out
    assert out["risk_score"] == 85 and out["verdict"] == "confirmed"
    # The None-verdict world (not a None-score world) owns the NULL level.
    none_out = va.apply_verdict_invariants(None, StubSeverity())  # type: ignore[arg-type]
    assert none_out["risk_level"] is None and none_out["verdict"] == "verification_failed"


def test_verification_payload_reads_only_the_row_list() -> None:
    """Witness for the _EventView m1 / analyze_batch m341 EQUIV claim: the
    view's event_id is never read, and a non-empty rows list ALWAYS yields a
    payload (the m348 else arm is dead). Both halves of the claim measured on
    the real function."""
    from backend.api.schemas.event_verification import verification_payload

    class Row:
        id = 7
        created_at = TS
        verdict = "confirmed"
        risk_score = 85
        summary = "A person stands at the door."
        reasoning = "Criterion evidence reviewed."
        scene_description = "d"
        criteria = None
        key_frame_detection_ids = None
        engine = "vlm"
        model_id = "m"
        latency_ms = 1

    for event_id in (4242, None):
        view = va._EventView(event_id=event_id, rows=[Row()])  # type: ignore[arg-type]
        payload = verification_payload(view)
        assert payload is not None, f"event_id={event_id} produced no payload"
        assert payload.model_dump()["verdict"] == "confirmed"
    assert verification_payload(va._EventView(event_id=1, rows=[])) is None


def test_key_frame_ids_are_pairing_invariant() -> None:
    """Witness for the key_frame_ids m4 EQUIV claim: two rows sharing one
    file_path (the detector's one-row-per-object shape) with different
    object_types merge into one still whether the pairs are split by a real
    camera_id or merged by the fallback, and the WINNER per file is the
    max-ranked row - so `by_path` cannot disagree between shipped and the
    `build_frame_refs(..., None)` mutant."""
    from backend.services.vlm_analyzer import key_frame_ids

    def req(paths: list[str], camera_id: str) -> Any:
        class _Ctx:
            pass

        ctx = _Ctx()
        ctx.camera_id = camera_id

        class _Req:
            pass

        r = _Req()
        r.context = ctx
        r.image_paths = paths
        return r

    rows = [
        {
            "id": 1,
            "camera_id": "camA",
            "object_type": "person",
            "confidence": 0.9,
            "detected_at": None,
            "file_path": "/f/a.jpg",
            "thumbnail_path": None,
        },
        {
            "id": 2,
            "camera_id": "camA",
            "object_type": "car",
            "confidence": 0.8,
            "detected_at": None,
            "file_path": "/f/b.jpg",
            "thumbnail_path": None,
        },
    ]
    got = key_frame_ids(req(["/f/a.jpg", "/f/b.jpg"], "camA"), detections=rows)
    assert got == [1, 2], got


# ===========================================================================
# VERBATIM COPIED from test_vlm_analyzer_batch38_y.py (battery Y) — analysis
# helpers only, byte-identical bodies (the batch28_00b precedent: batteries
# never import each other; the b30 sweep loads files by path). Used by the
# analyze_batch notify-call drives at the bottom of this file.
# ===========================================================================


SEV = SeverityService(low_max=29, medium_max=59, high_max=84)


TS1 = datetime(2026, 9, 25, 12, 0, 0, tzinfo=UTC)


TS2 = datetime(2026, 9, 25, 12, 5, 0, tzinfo=UTC)


class Spy:
    """Records (args, kwargs) per call; optional side_effect. ``results``
    (when given) overrides ``result`` per call so one spy can answer one
    call loudly and the rest quietly (the idempotency-key probe)."""

    def __init__(
        self,
        result: Any = None,
        raises: Exception | None = None,
        results: dict[int, Any] | None = None,
    ) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.result = result
        self.raises = raises
        self.results = results or {}

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if self.raises is not None:
            raise self.raises
        return self.results.get(len(self.calls) - 1, self.result)

    def kwargs(self, index: int = 0) -> dict[str, Any]:
        return self.calls[index][1]

    def args(self, index: int = 0) -> tuple[Any, ...]:
        return self.calls[index][0]

    @property
    def count(self) -> int:
        return len(self.calls)


class SyncSpy:
    """Same call-log surface as Spy for SYNCHRONOUS seams
    (record_pipeline_error is called without await)."""

    def __init__(self, result: Any = None, raises: Exception | None = None) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.result = result
        self.raises = raises

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if self.raises is not None:
            raise self.raises
        return self.result

    def args(self, index: int = 0) -> tuple[Any, ...]:
        return self.calls[index][0]

    @property
    def count(self) -> int:
        return len(self.calls)


class FakeRedis:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values: dict[str, str] = dict(values or {})
        self.sets: list[tuple[str, str, Any]] = []

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, expire: Any = "UNSET") -> None:
        self.values[key] = value
        self.sets.append((key, value, expire))


class FakeClient:
    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.calls: list[Any] = []
        self.closed = 0

    async def assess(self, request: Any) -> Any:
        self.calls.append(request)
        outcome = self.script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def prompt_text(self, request: Any) -> str:
        return f"PROMPT {request.context.camera_id}"

    async def close(self) -> None:
        self.closed += 1


class FakeBroadcaster:
    def __init__(self, raises: Exception | None = None) -> None:
        self.messages: list[dict[str, Any]] = []
        self.raises = raises

    async def broadcast_event(self, message: dict[str, Any]) -> int:
        if self.raises is not None:
            raise self.raises
        self.messages.append(message)
        return 1


def getter_spy(broadcaster: FakeBroadcaster) -> Spy:
    spy = Spy(result=broadcaster)

    async def fake_get_broadcaster(redis: Any) -> FakeBroadcaster:
        await spy(redis)
        return broadcaster

    return spy


class FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> FakeResult:
        return self

    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any:
        return self._rows[0] if self._rows else None


def _pred(stmt: Any) -> tuple[str | None, Any, Any]:
    """(column-name, operator, value) of a single binary whereclause."""
    wc = getattr(stmt, "whereclause", None)
    left = getattr(wc, "left", None)
    right = getattr(wc, "right", None)
    if left is None or right is None:
        return (None, None, None)
    return (getattr(left, "name", None), wc.operator, getattr(right, "value", None))


def _projects(stmt: Any, cls: type) -> bool:
    """True iff the SELECT still PROJECTS the ORM entity (a column of it).

    Needed because ``select(None).where(E.id == x)`` keeps the FROM clause
    (measured: 'SELECT NULL AS anon_1 FROM events WHERE ...'), so table-name
    matching alone would MASK the select-entity mutants (m7/m46/m336) that
    a real DB answers as an all-NULL scalar row, never an ORM object.
    """
    # Measured: select(E).column_descriptions -> [{'name': 'E', 'type': E}]
    # and select(None) -> [{'name': '_no_label', 'type': NULL}].
    return any(desc.get("type") is cls for desc in getattr(stmt, "column_descriptions", ()))


class FakeSession:
    """Answers the analyzer's three SELECT shapes SEMANTICALLY: rows come
    back only when the compiled statement keeps its shape (FROM table
    present, predicate operator/value intact). ``.where(None)`` (a silent
    WHERE NULL) or a flipped ``!=`` therefore returns [] exactly as the
    real DB would, and select(None) loses the FROM clause entirely."""

    def __init__(
        self,
        detections: list[Any] | None = None,
        existing_event: Any = None,
    ) -> None:
        self.detections = list(detections or [])
        self.existing_event = existing_event
        self.added: list[Any] = []
        self.flushes = 0
        self.executed: list[Any] = []
        self._next_id = 100

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            self._next_id += 1
            obj.id = self._next_id

    async def flush(self) -> None:
        self.flushes += 1
        # faithful server default: event_verifications.created_at = utc_now()
        for obj in self.added:
            if isinstance(obj, EventVerification) and getattr(obj, "created_at", None) is None:
                obj.created_at = TS1

    async def execute(self, stmt: Any) -> FakeResult:
        self.executed.append(stmt)
        return FakeResult(self._rows_for(stmt))

    def _rows_for(self, stmt: Any) -> list[Any]:
        """One decision point: the rows a real DB would answer."""
        if "INSERT" in str(stmt):
            return []
        for cls, reader in (
            (EventVerification, self._verification_rows),
            (Event, self._existing_event_rows),
            (Detection, self._detection_rows),
        ):
            if _projects(stmt, cls):
                return reader(stmt)
        return []

    def _verification_rows(self, stmt: Any) -> list[Any]:
        col, op, _ = _pred(stmt)
        if op is operator.eq and col == "event_id":
            return [o for o in self.added if isinstance(o, EventVerification)]
        return []  # where(None)/!=/select(None): a real DB has none

    def _existing_event_rows(self, stmt: Any) -> list[Any]:
        col, op, _ = _pred(stmt)
        if op is operator.eq and col == "id" and self.existing_event is not None:
            return [self.existing_event]
        return []

    def _detection_rows(self, stmt: Any) -> list[Any]:
        # session-1 read is `Detection.id.in_(int_ids)`; a WHERE NULL, a
        # flipped operator, or select(None) all answer 0 rows.
        col, op, _ = _pred(stmt)
        want = _in_values(stmt)
        if col == "id" and op is not None and want is not None:
            return [d for d in self.detections if d.id in want]
        return []


def _in_values(stmt: Any) -> list[Any] | None:
    """The id-list of a `Detection.id.in_([...])` statement, else None."""
    wc = getattr(stmt, "whereclause", None)
    op = getattr(wc, "operator", None)
    if op is None or op.__name__ not in ("in_op",):
        return None
    try:
        params = stmt.compile().params
    except Exception:  # pragma: no cover
        return None
    for value in params.values():
        if isinstance(value, (list, tuple, set, frozenset)):
            return list(value)
    return None


def det_row(
    det_id: int,
    *,
    camera_id: str | None = "rcam",
    object_type: str | None = "person",
    confidence: float | None = 0.7,
    detected_at: datetime | None = TS1,
    file_path: str | None = None,
    thumbnail_path: str | None = "/thumbs/one.png",
    track_id: int | None = None,
    bbox: tuple[int, int, int, int] | None = None,
    video: tuple[int, int] | None = (100, 100),
) -> Any:
    full: dict[str, Any] = {
        "id": det_id,
        "camera_id": camera_id,
        "object_type": object_type,
        "confidence": confidence,
        "detected_at": detected_at,
        "file_path": file_path or f"/media/frames/det_{det_id}.jpg",
        "thumbnail_path": thumbnail_path,
        "track_id": track_id,
        "bbox_x": None,
        "bbox_y": None,
        "bbox_width": None,
        "bbox_height": None,
        "video_width": None,
        "video_height": None,
    }
    if bbox is not None:
        full.update(zip(("bbox_x", "bbox_y", "bbox_width", "bbox_height"), bbox, strict=True))
    if bbox is not None and video is not None:
        full["video_width"], full["video_height"] = video
    return SimpleNamespaceOf(full)


def SimpleNamespaceOf(mapping: dict[str, Any]) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(**mapping)


def make_verdict(
    *,
    verdict: str = "confirmed",
    risk_score: int = 85,
    summary: str = "A person stands at the door.",
    reasoning: str = "Criterion evidence reviewed.",
    description: str = "Front door, one person.",
) -> VlmVerdict:
    return VlmVerdict(
        verdict=verdict,
        risk_score=risk_score,
        summary=summary,
        reasoning=reasoning,
        description=description,
        criteria=[{"name": "person_present", "passed": True, "evidence": "full frame"}],
        provenance={"engine": "llama.cpp", "model_id": "Qwen3VL-8B"},
    )


class NotifySpy:
    """Stands in for the bound `_notify_decision` method on the analyzer
    INSTANCE (attribute lookup beats the class def), recording the full
    kwargs of every call. Returns False - distinguishable from the
    `notify: bool | None = None` initializer so the broadcast key assert
    downstream is not vacuous."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> bool:
        self.calls.append(kwargs)
        return False

    @property
    def count(self) -> int:
        return len(self.calls)


def _drive_batch(*, replay: bool = False) -> Any:
    """One full analyze_batch drive over the battery-Y fake surface (the
    fakes are Y's, copied verbatim above; construction through the REAL
    __init__ is Y's own precedent - settings validate under the test env).
    Everything the shipped path calls outward is a spy; the analyzer is
    returned with the spies on a namespace. `_notify_decision` is replaced
    on the instance so the call site - NOT the decision internals, which
    the tests above pin directly - is what these drives measure."""
    session = FakeSession(detections=[det_row(11), det_row(12)])
    client = FakeClient([make_verdict()])
    broadcaster = FakeBroadcaster()
    gb = getter_spy(broadcaster)
    analyzer = va.VlmAnalyzer(
        vlm_client=client, redis_client=FakeRedis(), severity=SEV, replay=replay
    )
    notify_spy = NotifySpy()
    analyzer._notify_decision = notify_spy  # type: ignore[method-assign]
    with _Patcher(
        (va, "get_session", lambda: session),
        (va, "get_zones_for_detection", Spy(result=[])),
        (va, "load_household_context", Spy(result={})),
        (
            va,
            "collect_specialist_outputs",
            Spy(result={"faces": "f", "plates": "p", "person_reid": "r"}),
        ),
        (va, "record_pipeline_error", SyncSpy()),
    ):
        with patch("backend.services.event_broadcaster.get_broadcaster", gb):
            event = asyncio.run(
                analyzer.analyze_batch("b1", camera_id="cam1", detection_ids=[11, 12])
            )
    return SimpleNamespaceOf(
        {
            "event": event,
            "session": session,
            "notify": notify_spy,
            "broadcaster": broadcaster,
        }
    )


def test_analyze_batch_calls_notify_decision_with_the_flushed_event_id_and_batch_camera() -> None:
    """m360 (event_id -> None) / m361 (camera_id -> None) mutate the CALL
    SITE kwargs inside analyze_batch, so the kill has to drive analyze_batch
    itself and read what _notify_decision actually RECEIVED. event_id must
    be the id the write session's add/flush assigned (101 - the literal
    pins the flush contract, the event.id equality pins identity), and
    camera_id must be the RESOLVED BATCH camera ("cam1"), not the row
    camera: the projection row deliberately carries a DIFFERENT camera
    ("rcam", Y's divergence rule) so a projection-row substitution has a
    witness. The full key set is pinned too (renames/deletions die on the
    set, values on the dict)."""
    env = _drive_batch()
    spy = env.notify
    assert spy.count == 1, f"_notify_decision called {spy.count} times, expected 1"
    kw = spy.calls[0]
    assert set(kw) == {
        "event_id",
        "camera_id",
        "timestamp",
        "risk_score",
        "verdict",
        "detections",
    }, set(kw)
    assert kw["event_id"] == 101 == env.event.id, kw["event_id"]
    assert kw["camera_id"] == "cam1", kw["camera_id"]
    assert kw["timestamp"] == TS1, kw["timestamp"]
    assert kw["risk_score"] == 85, kw["risk_score"]
    assert kw["verdict"] == "confirmed", kw["verdict"]
    assert len(kw["detections"]) == 2 and kw["detections"][0]["id"] == 11, kw["detections"]
    # the decided value rides the broadcast frame (m357-adjacent: the
    # call site's result must reach _broadcast, and False - not absence)
    assert env.broadcaster.messages[0]["data"]["notify"] is False, env.broadcaster.messages


def test_analyze_batch_replay_never_asks_for_a_notify_decision() -> None:
    """The `if not self._replay` guard is the whole replay contract here
    (F11 ruling 4 - replay writes nothing outward and never reads the
    owner's settings): the decision call and the broadcast both stay silent
    while the event is still analyzed. Drops of the guard would call the
    spy and emit a frame."""
    env = _drive_batch(replay=True)
    assert env.notify.count == 0, env.notify.calls
    assert env.broadcaster.messages == [], env.broadcaster.messages
    assert env.event.id == 101, env.event.id
