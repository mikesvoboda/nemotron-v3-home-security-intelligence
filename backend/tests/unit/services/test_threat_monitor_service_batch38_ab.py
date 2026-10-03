# TARGET-MODULE: backend.services.threat_monitor_service
"""Battery AB — campaign #26 batch-38 killers for threat_monitor_service.

Campaign #26 (ladder to 85%): the 244 survivor keys live in five methods
(process_multiple_threat_detections 71, process_threat_detection 54,
_broadcast_alert_created 52, _trigger_webhooks 43, _check_cooldown 24).
The module is DATA-MAPPING-shaped: the shipped suite exercises behavior
(alert created / not created) but never pins the emitted payloads, log
messages, call-site arguments or query text — every dict-key XX/UPPER
flip, message None/XX swap, call-argument drop/None-swap and
query-clause flip survives. This battery pins:

  * the FULL published WebSocket payload (json.loads of the exact payload
    string, whole-dict equality including the {"type", "data"} wrapper)
    and the publish CHANNEL string;
  * the webhook call as one whole tuple (db object IDENTITY, event_type,
    whole data dict, event_id kwarg) against a fake whose signature PINS
    all four parameters (required slots turn positional deletions into
    TypeErrors; the keyword-only event_id stays a real keyword);
  * a call-site SPY around _check_cooldown recording the exact
    (dedup_key, cooldown_seconds, rule) tuple, so the rule-cooldown
    ternaries and the cooldown arg mutations are observable at the call
    site (the spy wraps the BOUND method, so the trampoline still flips
    the real body per key);
  * the rendered cooldown SQL (str(stmt): entity columns, "dedup_key = :",
    ">=" cutoff clause, "LIMIT" clause) plus the compiled PARAM VALUES
    (cutoff tz-awareness + freshness, limit integer equality) — the
    select(None) tell is '"SELECT NULL" not in sql' (a None projection
    still renders FROM/WHERE);
  * log records on the FULL msgs() sequence (msg-equality, never
    substring) plus the extra= attributes merged on the record;
  * every created Alert's mapped attributes AND its full alert_metadata
    dict (equality, including the per-threat dicts in the multi path).

Style notes for the b30 sweep (module-level sync test_* only, zero args):
async paths run under asyncio.run; fakes live at TEST level; plain _Obj
attribute bags stand in for models — a Mock would manufacture attributes
and fake away the hasattr-guard lines in _check_cooldown; the real Alert
class is imported for the isinstance-guard polarity; the unflushed
Alert's instrumented created_at/updated_at read None (exactly what the
service's fallback ternaries were written for), so the no-id / no-stamps
rounds make those fallback branches LIVE rather than raising.

Honesty ledger (EQUIV candidates REGISTERED BY CONSTRUCTION; the sweep
verdict + the per-key probes in the campaign notes are the evidence - a
construction claim is not a verdict claim). Authoring sweep over the 244
survivor keys: RED=240 GREEN=4, no killer round was needed - those 4
GREENs are EXACTLY the EQUIV ledger below (measured 2026-10-03,
b38-c26-sweep-authoring.txt, batched 20-key wrapper, 0 HANG).

  Not equivalent, KILLABLE - the arms this battery supplies:
  - _broadcast m7/m8 (id or->and, str(None)): the no-id round makes the
    fallback LIVE - `and` yields None, str(None) yields "None"; the
    payload pins id to a real uuid-shaped string, never None/"None".
  - _broadcast m2/m3 (now_iso None / datetime.now(None)): the no-stamps
    round makes the fallback LIVE; the payload pins created_at/updated_at
    to end with "+00:00" (naive isoformat never carries the offset).
  - _broadcast m21/m25 (ternaries forced to the fallback): the
    stamps-SET round pins the EXACT isoformat of the known datetimes.
  - _check_cooldown m19-m33 family (mock-guard hasattr lines): plain
    rows with exact attribute polarities - (id only), (created_at only),
    (none) + the real-Alert row; key-case/None/1-arg hasattr variants die
    on the both-attrs row (a plain object WITHOUT the literal "id"/
    "created_at" attributes gets filtered while the orig keeps it).
  - _check_cooldown m2/m3 (cutoff +timedelta / now(None)): compiled
    cutoff param must be tz-aware AND in the recent past.
  - _check_cooldown m5/m7/m8/m9/m10/m11/m14 (stmt None, where(None) x2,
    select(None), == -> !=, >= -> >): SQL text tells - "SELECT NULL"
    absence, alerts.dedup_key/alerts.created_at presence, "!=" absence,
    ">=" presence.
  - _check_cooldown m6/m12 (limit(None) / limit(2)): "LIMIT" presence +
    the compiled limit param VALUE == 1.
  - process_multiple m3 (>= -> >): a threat at confidence EXACTLY the
    threshold must still create.
  - process_multiple m6/m11 (severity None / get(None, 0)): a
    [bat, gun] list pins the winner = gun (key-collapse to 0 makes max
    return the FIRST entry, bat).
  - process_multiple m8/m10/m23/m25/m52/m54 (severity-HINT drops): the
    hint round [knife(hint None), unknown-x(hint "critical")] - the hint
    makes unknown-x (priority 3) beat knife (2); dropping it TIES at 2
    and max() returns the FIRST entry (knife).
  - the rule families (ptd m28/m31/m33/m36/m38/m41/m53/m60/m66,
    pmd m29/m32/m34/m37/m39/m42/m59/m66/m72): rule round with a LIVE
    dedup_key_template + cooldown_seconds=42 pins the formatted key,
    alert.rule_id, and the (key, 42, rule) spy tuple; _build_dedup_key
    gets direct-call rounds (None rule, template None, KeyError
    template, live template).
  - call-arg None + trailing-comma DELETIONS (ptd m36/m38/m41, pmd
    m36/m37/m39/m42/m106/m107/m112, wh m1/m28-m35, bc m43-m47): spy
    tuples with REQUIRED slots, the session object IDENTITY in the db
    slot, and the publish/webhook call COUNTS - an event=None flip dies
    INSIDE the callee reading event.camera_id -> warning path -> count
    0 -> the count and payload pins both fire.
  - Alert-kwarg families (ptd m53/m57/m60/m64/m66, pmd m58-m70/m72-m90):
    whole-alert attribute equality (rule_id, status, dedup_key,
    channels == [], event_id) + whole alert_metadata dict equality.
  - Log families everywhere (msg -> None/XX + extra -> None/deleted/
    key-case): FULL msgs() sequence equality per path + record
    attribute equality on every extra key.
  - _trigger_webhooks m17 (`alert.channels or []` -> `and []`):
    discriminating polarity needs a NON-EMPTY channels alert - the
    process_ paths always construct channels=[], so this battery calls
    _trigger_webhooks DIRECTLY with a crafted channels=["sms"] alert.

  EQUIV candidates REGISTERED (construction, not verdict):
  - _check_cooldown m16 (`and` -> `or` in `existing_alert is not None
    and not isinstance(existing_alert, Alert)`): the polarities where
    the shapes disagree are (None, not-Alert) -> orig skips the guard
    returns None, mutant enters, hasattr(None,"id") False -> returns
    None; and (real Alert) -> orig enters? no: not-Alert False -> orig
    False, mutant True -> enters guard, real Alert HAS both instrumented
    attrs (they exist at None) -> falls through -> same alert. Every
    reachable input returns identically.
  - process_multiple m12/m14/m15 (SEVERITY_PRIORITY.get default -> None
    / deleted / -> 1): the default is read only when the key is absent;
    get_threat_severity returns ONLY AlertSeverity members and every
    member is in SEVERITY_PRIORITY - the default slot is unreachable.
    The sweep confirms: all three default arms GREEN alongside m16.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from backend.api.schemas.outbound_webhook import WebhookEventType
from backend.models import Alert, AlertSeverity, AlertStatus
from backend.services import threat_monitor_service as tm

# ---------------------------------------------------------------------------
# capture / patch helpers (no fixtures - the sweep calls plain functions)
# ---------------------------------------------------------------------------


class RecordList(logging.Handler):
    """Captures EVERY record emitted through tm.logger while active."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def one(self, msg: str) -> logging.LogRecord:
        hits = [r for r in self.records if r.getMessage() == msg]
        assert len(hits) == 1, (msg, [r.getMessage() for r in self.records])
        return hits[0]

    def msgs(self) -> list[str]:
        return [r.getMessage() for r in self.records]


@contextmanager
def logcap():
    cap = RecordList()
    old_level = tm.logger.level
    tm.logger.addHandler(cap)
    tm.logger.setLevel(logging.DEBUG)
    try:
        yield cap
    finally:
        tm.logger.removeHandler(cap)
        tm.logger.setLevel(old_level)


@contextmanager
def patched(obj: Any, attr: str, value: Any):
    old = getattr(obj, attr)
    setattr(obj, attr, value)
    try:
        yield value
    finally:
        setattr(obj, attr, old)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# model stand-ins (plain objects, NOT Mock - the hasattr guards in
# _check_cooldown need real attribute polarities)
# ---------------------------------------------------------------------------

CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)
UPDATED_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


class _Obj:
    """Attribute bag; unknown attributes raise AttributeError (a Mock would
    silently manufacture them and fake away the guard-line mutants)."""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


def make_event(*, eid: int = 77, camera_id: str = "cam-1", risk_score: int | None = 55) -> Any:
    return _Obj(id=eid, camera_id=camera_id, risk_score=risk_score)


def make_td(
    *,
    tid: int = 900,
    threat_type: str = "knife",
    confidence: float = 0.9,
    severity: str | None = None,
) -> Any:
    return _Obj(id=tid, threat_type=threat_type, confidence=confidence, severity=severity)


def make_rule(
    *, rid: str = "rule-1", template: str | None = None, cooldown_seconds: int = 42
) -> Any:
    return _Obj(id=rid, dedup_key_template=template, cooldown_seconds=cooldown_seconds)


def make_alert(
    *,
    aid: str | None = "alert-1",
    event_id: int = 77,
    rule_id: str | None = None,
    severity: AlertSeverity = AlertSeverity.HIGH,
    status: AlertStatus = AlertStatus.PENDING,
    dedup_key: str = "cam-1:knife:threat",
    channels: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: datetime | None = CREATED_AT,
    updated_at: datetime | None = UPDATED_AT,
) -> Alert:
    alert = Alert(
        event_id=event_id,
        rule_id=rule_id,
        severity=severity,
        status=status,
        dedup_key=dedup_key,
        channels=channels,
        alert_metadata=metadata if metadata is not None else {"k": "v"},
    )
    alert.id = aid
    alert.created_at = created_at
    alert.updated_at = updated_at
    return alert


# ---------------------------------------------------------------------------
# dependency fakes
# ---------------------------------------------------------------------------


class FakeResult:
    """scalar_one_or_none pops the scripted row (exhausted -> None)."""

    def __init__(self, script: list[Any] | None = None) -> None:
        self._script = list(script or [])

    def scalar_one_or_none(self) -> Any:
        return self._script.pop(0) if self._script else None


class FakeSession:
    """add/flush/refresh recorder; execute records (str(stmt), compiled
    params) — and survives the stmt=None mutants by recording "None".

    refresh() policy mirrors DB population: with_id/with_stamps True set
    real values; False sets None EXPLICITLY (the instrumented attribute
    exists reading None on an unflushed Alert — that is exactly the
    polarity that makes the broadcast fallback branches live instead of
    raising)."""

    def __init__(
        self,
        results: list[Any] | None = None,
        *,
        with_id: bool = True,
        with_stamps: bool = True,
        fixed_id: str = "alert-1",
    ) -> None:
        self._results = list(results or [])
        self._with_id = with_id
        self._with_stamps = with_stamps
        self._fixed_id = fixed_id
        self.added: list[Any] = []
        self.flushes = 0
        self.refreshed: list[Any] = []
        self.sqls: list[str] = []
        self.params: list[dict[str, Any]] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushes += 1

    async def refresh(self, obj: Any) -> None:
        self.refreshed.append(obj)
        obj.id = self._fixed_id if self._with_id else None
        obj.created_at = CREATED_AT if self._with_stamps else None
        obj.updated_at = UPDATED_AT if self._with_stamps else None

    async def execute(self, stmt: Any) -> Any:
        if stmt is not None:
            self.sqls.append(str(stmt))
            self.params.append(dict(stmt.compile().params))
        else:
            self.sqls.append("None")
            self.params.append({})
        return FakeResult(self._results)


class FakeRedis:
    """publish(channel, payload) with BOTH parameters required - the
    arg-deletion/trailing-comma mutants surface as TypeErrors."""

    def __init__(self, raises: Exception | None = None) -> None:
        self.published: list[tuple[Any, Any]] = []
        self.raises = raises

    async def publish(self, channel: Any, payload: Any) -> int:
        self.published.append((channel, payload))
        if self.raises is not None:
            raise self.raises
        return 1


class FakeWebhook:
    """trigger_webhooks_for_event(db, event_type, event_data, event_id)
    with ALL FOUR slots pinned (keyword-only event_id stays a keyword)."""

    def __init__(self, raises: Exception | None = None) -> None:
        self.calls: list[tuple[Any, Any, Any, Any]] = []
        self.raises = raises

    async def trigger_webhooks_for_event(
        self, db: Any, event_type: Any, event_data: Any, *, event_id: Any
    ) -> list[Any]:
        self.calls.append((db, event_type, event_data, event_id))
        if self.raises is not None:
            raise self.raises
        return []


def cooldown_spy(mgr: Any) -> list[tuple[Any, Any, Any]]:
    """Install a call-site spy over the manager's _check_cooldown,
    recording (dedup_key, cooldown_seconds, rule) and delegating to the
    bound method (the trampoline consults env at CALL time, so the real
    body still flips per key)."""
    rec: list[tuple[Any, Any, Any]] = []
    original = mgr._check_cooldown

    async def spy(dedup_key: Any, cooldown_seconds: Any, rule: Any = None) -> Any:
        rec.append((dedup_key, cooldown_seconds, rule))
        return await original(dedup_key, cooldown_seconds, rule)

    mgr._check_cooldown = spy  # type: ignore[method-assign]
    return rec


def make_mgr(
    *,
    session: Any = None,
    redis: Any = None,
    threshold: float = 0.7,
    cooldown_seconds: int = 300,
) -> Any:
    return tm.ThreatMonitorService(
        session if session is not None else FakeSession(),
        redis_client=redis,
        confidence_threshold=threshold,
        cooldown_seconds=cooldown_seconds,
    )


# ---------------------------------------------------------------------------
# _check_cooldown — query shape, params, rule filter, mock-guard polarities
# ---------------------------------------------------------------------------


def test_cooldown_query_shape_and_params_exact() -> None:
    """Rendered SQL + compiled params pin select(Alert), the == dedup
    comparison, the >= cutoff clause with a tz-aware RECENT cutoff, and
    LIMIT with param value 1 (m2/m3/m5/m6/m8/m9/m10/m11/m12/m14)."""
    row = make_alert()
    sess = FakeSession(results=[row])
    mgr = make_mgr(session=sess)
    found = run(mgr._check_cooldown("dedup-9", 3600))
    assert found is row
    assert len(sess.sqls) == 1
    sql, params = sess.sqls[0], sess.params[0]
    assert "SELECT NULL" not in sql
    assert "alerts.dedup_key = :" in sql.replace("dedup_key_1", "")
    assert "alerts.created_at >= :" in sql.replace("created_at_1", "")
    assert "!=" not in sql
    assert "LIMIT :" in sql.replace("param_1", "")
    assert params["dedup_key_1"] == "dedup-9"
    cutoff = params["created_at_1"]
    assert cutoff.tzinfo is not None and cutoff.utcoffset() == timedelta(0)
    # cutoff = now - 3600s: a +/-minute window is microsecond-safe; the
    # +timedelta mutant (cutoff ~ now + 1h) and the now(None) naive
    # mutant both fall out of this window.
    assert (
        datetime.now(UTC) - timedelta(hours=2) < cutoff < datetime.now(UTC) - timedelta(minutes=59)
    )
    assert params["param_1"] == 1


def test_cooldown_rule_filter_both_polarities() -> None:
    """No-rule query has no rule_id predicate; the rule round adds
    rule_id = :param with the rule's id as the VALUE (rule-arg drop /
    None-swap arms at the call sites are spied separately)."""
    sess1 = FakeSession()
    mgr1 = make_mgr(session=sess1)
    assert run(mgr1._check_cooldown("k1", 300)) is None
    assert "rule_id = :" not in sess1.sqls[0].replace("rule_id_1", "")

    rule = make_rule(rid="rule-7")
    sess2 = FakeSession()
    mgr2 = make_mgr(session=sess2)
    assert run(mgr2._check_cooldown("k2", 300, rule)) is None
    assert "rule_id = :" in sess2.sqls[0].replace("rule_id_1", "")
    assert sess2.params[0]["rule_id_1"] == "rule-7"


def test_cooldown_none_when_no_row_and_silent() -> None:
    """Empty result -> None, no log records (m16 EQUIV evidence: the
    None-input polarity returns identically under the or-flip)."""
    sess = FakeSession(results=[])
    mgr = make_mgr(session=sess)
    with logcap() as cap:
        assert run(mgr._check_cooldown("k3", 300)) is None
    assert cap.msgs() == []


def test_cooldown_guard_keeps_row_with_both_attrs() -> None:
    """A PLAIN row carrying exactly the literal attrs id+created_at is
    KEPT (key-case XXidXX/ID/XXcreated_atXX/CREATED_AT, None attr name
    and the 1-arg/trailing-comma hasattr calls all filter or TypeError
    this row out — m25/m26/m28/m29/m30/m31/m32/m33)."""
    row = _Obj(id="plain-1", created_at=CREATED_AT)
    sess = FakeSession(results=[row])
    mgr = make_mgr(session=sess)
    assert run(mgr._check_cooldown("k4", 300)) is row


def test_cooldown_guard_filters_row_missing_created_at() -> None:
    """id-only row is FILTERED (m19's and-flip keeps it; m27's or-flip
    with the second hasattr inverted keeps it — both die here)."""
    row = _Obj(id="plain-1")
    sess = FakeSession(results=[row])
    mgr = make_mgr(session=sess)
    assert run(mgr._check_cooldown("k5", 300)) is None


def test_cooldown_guard_filters_row_missing_id() -> None:
    """created_at-only row is FILTERED (m20's first-not->has flip keeps
    it: hasattr(id) False or not-attr False -> not filtered)."""
    row = _Obj(created_at=CREATED_AT)
    sess = FakeSession(results=[row])
    mgr = make_mgr(session=sess)
    assert run(mgr._check_cooldown("k6", 300)) is None


def test_cooldown_guard_filters_bare_row() -> None:
    """Attribute-less row is FILTERED -> None (every inversion of the
    hasattr pair must still filter it: pins the guard's floor)."""
    row = _Obj()
    sess = FakeSession(results=[row])
    mgr = make_mgr(session=sess)
    assert run(mgr._check_cooldown("k7", 300)) is None


def test_cooldown_guard_passes_real_alert_through() -> None:
    """A REAL Alert row passes the guard untouched (its instrumented
    id/created_at exist reading None); m16's or-flip enters the guard
    here and STILL returns the alert — m16 EQUIV construction evidence."""
    row = make_alert(aid="real-1")
    sess = FakeSession(results=[row])
    mgr = make_mgr(session=sess)
    assert run(mgr._check_cooldown("k8", 300)) is row


# ---------------------------------------------------------------------------
# _broadcast_alert_created — channel, exact payload, fallback polarity,
# exception path
# ---------------------------------------------------------------------------


def test_broadcast_no_redis_is_silent_noop() -> None:
    """redis_client None -> immediate return, no log, no crash (the
    gate's falsy branch; a flip to `if self.redis_client:` would crash
    on None.publish and log a warning instead)."""
    alert = make_alert()
    mgr = make_mgr(redis=None)
    with logcap() as cap:
        run(mgr._broadcast_alert_created(alert, make_event(), make_td()))
    assert cap.msgs() == []


def test_broadcast_happy_channel_and_full_payload_exact() -> None:
    """The published CHANNEL string and the WHOLE payload dict (top-level
    {"type","data"} wrapper + all 11 alert_data keys with exact names and
    values) — the dict-key XX/UPPER flips, type/value swaps, message
    None/XX and every key-name mutation die on this equality."""
    alert = make_alert(
        aid="alert-9",
        event_id=77,
        rule_id="rule-3",
        severity=AlertSeverity.CRITICAL,
        status=AlertStatus.PENDING,
        dedup_key="cam-1:gun:threat",
    )
    redis = FakeRedis()
    mgr = make_mgr(redis=redis)
    event = make_event(eid=77, camera_id="cam-1")
    td = make_td(threat_type="gun", confidence=0.83)
    with logcap() as cap:
        run(mgr._broadcast_alert_created(alert, event, td))

    assert len(redis.published) == 1
    channel, payload = redis.published[0]
    assert channel == "websocket:events"
    assert isinstance(payload, str)
    msg = json.loads(payload)
    assert msg == {
        "type": "alert.created",
        "data": {
            "id": "alert-9",
            "event_id": 77,
            "rule_id": "rule-3",
            "severity": "critical",
            "status": "pending",
            "dedup_key": "cam-1:gun:threat",
            "created_at": CREATED_AT.isoformat(),
            "updated_at": UPDATED_AT.isoformat(),
            "camera_id": "cam-1",
            "threat_type": "gun",
            "threat_confidence": 0.83,
        },
    }
    assert cap.msgs() == [f"Broadcast alert.created for threat alert {alert.id}"]
    rec = cap.records[0]
    assert rec.levelno == logging.DEBUG
    assert rec.alert_id == "alert-9"
    assert rec.threat_type == "gun"


def test_broadcast_no_id_no_stamps_fallbacks_live() -> None:
    """alert.id None + timestamps None make the fallback branches LIVE:
    id becomes a real uuid4 STRING (m7 `or`->`and` -> None; m8 str(None)
    -> "None"), and both timestamps become tz-aware isoformats ending in
    the UTC offset (m2 now_iso None; m3 datetime.now(None) is NAIVE and
    carries no offset)."""
    alert = make_alert(aid=None, created_at=None, updated_at=None)
    redis = FakeRedis()
    mgr = make_mgr(redis=redis)
    run(mgr._broadcast_alert_created(alert, make_event(), make_td()))
    data = json.loads(redis.published[0][1])["data"]
    assert data["id"] is not None and data["id"] != "None"
    assert len(data["id"]) == 36 and data["id"].count("-") == 4
    for key in ("created_at", "updated_at"):
        assert isinstance(data[key], str) and data[key].endswith("+00:00")
        assert datetime.fromisoformat(data[key]).tzinfo is not None


def test_broadcast_no_id_keeps_real_timestamps() -> None:
    """Fallback polarity, other half: with id None but REAL timestamps
    the ternaries must keep the alert's own isoformat values (a mutant
    forcing the fallback for created_at/updated_at — m21/m25 — replaces
    these exact strings with a fresh now())."""
    alert = make_alert(aid=None, created_at=CREATED_AT, updated_at=UPDATED_AT)
    redis = FakeRedis()
    mgr = make_mgr(redis=redis)
    run(mgr._broadcast_alert_created(alert, make_event(), make_td()))
    data = json.loads(redis.published[0][1])["data"]
    assert data["created_at"] == CREATED_AT.isoformat()
    assert data["updated_at"] == UPDATED_AT.isoformat()


def test_broadcast_publish_failure_warns_and_swallowed() -> None:
    """publish raising -> the warning path with the exact message and the
    alert_id/error extras; the exception NEVER propagates (m48/m49 and
    the extra-key family die on the record pins; m44/m47 die on the
    payload shape reaching publish before the raise)."""
    boom = RuntimeError("redis down")
    alert = make_alert(aid="alert-5")
    redis = FakeRedis(raises=boom)
    mgr = make_mgr(redis=redis)
    with logcap() as cap:
        run(mgr._broadcast_alert_created(alert, make_event(), make_td()))
    assert len(redis.published) == 1
    assert cap.msgs() == [f"Failed to broadcast threat alert: {boom}"]
    rec = cap.records[0]
    assert rec.levelno == logging.WARNING
    assert rec.alert_id == "alert-5"
    assert rec.error == "redis down"


def test_broadcast_payload_from_multi_shape_metadata() -> None:
    """Second payload shape (rule_id None passthrough + a non-default
    severity/status pair) so a rule_id/severity/status VALUE swap cannot
    hide behind the first round's coincidences."""
    alert = make_alert(
        aid="alert-6",
        rule_id=None,
        severity=AlertSeverity.MEDIUM,
        status=AlertStatus.ACKNOWLEDGED,
        dedup_key="cam-2:bat:threat",
    )
    redis = FakeRedis()
    mgr = make_mgr(redis=redis)
    run(
        mgr._broadcast_alert_created(
            alert, make_event(eid=88, camera_id="cam-2"), make_td(threat_type="bat", confidence=0.5)
        )
    )
    assert json.loads(redis.published[0][1]) == {
        "type": "alert.created",
        "data": {
            "id": "alert-6",
            "event_id": 77,
            "rule_id": None,
            "severity": "medium",
            "status": "acknowledged",
            "dedup_key": "cam-2:bat:threat",
            "created_at": CREATED_AT.isoformat(),
            "updated_at": UPDATED_AT.isoformat(),
            "camera_id": "cam-2",
            "threat_type": "bat",
            "threat_confidence": 0.5,
        },
    }


# ---------------------------------------------------------------------------
# _trigger_webhooks — call tuple pins (session identity, event type, full
# data dict, event_id kwarg), non-empty channels polarity, failure path
# ---------------------------------------------------------------------------


def test_webhook_call_tuple_exact_with_empty_channels() -> None:
    """The whole call as ONE tuple: (session identity, ALERT_FIRED, full
    webhook_data dict, event_id=alert.id). Required fake slots turn the
    positional DELETION mutants (wh m32-m35) into TypeErrors; the None
    swaps (m28-m31) die on the identity/dict/equality pins; m1 (service
    None) dies on the AttributeError -> warning path -> calls == 0."""
    alert = make_alert(aid="alert-2", event_id=77, rule_id=None, channels=[])
    sess = FakeSession()
    wh = FakeWebhook()
    mgr = make_mgr(session=sess)
    with patched(tm, "get_webhook_service", lambda: wh):
        run(mgr._trigger_webhooks(alert, make_event(eid=77, camera_id="cam-9", risk_score=12)))
    assert wh.calls == [
        (
            sess,
            WebhookEventType.ALERT_FIRED,
            {
                "alert_id": "alert-2",
                "event_id": 77,
                "rule_id": None,
                "severity": "high",
                "status": "pending",
                "dedup_key": "cam-1:knife:threat",
                "channels": [],
                "matched_conditions": ["threat_detected"],
                "camera_id": "cam-9",
                "risk_score": 12,
                "threat_metadata": {"k": "v"},
            },
            "alert-2",
        )
    ]


def test_webhook_nonempty_channels_kills_the_and_flip() -> None:
    """channels=["sms"]: `or []` keeps the list, `and []` (m17) replaces
    it with [] — the process_ paths always pass channels=[], so ONLY a
    crafted non-empty-channels direct call discriminates this flip."""
    alert = make_alert(aid="alert-3", channels=["sms"])
    sess = FakeSession()
    wh = FakeWebhook()
    mgr = make_mgr(session=sess)
    with patched(tm, "get_webhook_service", lambda: wh):
        run(mgr._trigger_webhooks(alert, make_event()))
    (db, etype, data, eid) = wh.calls[0]
    assert data["channels"] == ["sms"]


def test_webhook_service_failure_warns_and_swallowed() -> None:
    """get_webhook_service raising -> warning with the exact message and
    both extras; never propagates. The service itself is never called."""
    boom = RuntimeError("no webhooks")
    wh = FakeWebhook()

    def raiser() -> Any:
        raise boom

    alert = make_alert(aid="alert-4")
    mgr = make_mgr(session=FakeSession())
    with patched(tm, "get_webhook_service", raiser), logcap() as cap:
        run(mgr._trigger_webhooks(alert, make_event()))
    assert wh.calls == []
    assert cap.msgs() == [f"Failed to trigger webhooks for threat alert: {boom}"]
    rec = cap.records[0]
    assert rec.levelno == logging.WARNING
    assert rec.alert_id == "alert-4"
    assert rec.error == "no webhooks"


def test_webhook_delivery_failure_warns_with_delivery_error() -> None:
    """The webhook service RAISING at call time takes the same except
    arm; pinning the second str(e) value ("down") proves the error text
    is the CAUGHT exception (m44 str(None) writes "None" verbatim)."""
    boom = ValueError("down")
    wh = FakeWebhook(raises=boom)
    alert = make_alert(aid="alert-7")
    mgr = make_mgr(session=FakeSession())
    with patched(tm, "get_webhook_service", lambda: wh), logcap() as cap:
        run(mgr._trigger_webhooks(alert, make_event()))
    assert len(wh.calls) == 1
    assert cap.msgs() == [f"Failed to trigger webhooks for threat alert: {boom}"]
    rec = cap.records[0]
    assert rec.alert_id == "alert-7"
    assert rec.error == "down"


# ---------------------------------------------------------------------------
# _build_dedup_key — direct-call polarities (all four branches)
# ---------------------------------------------------------------------------


def test_dedup_key_default_shape() -> None:
    """No rule -> the f-string default "camera:type:threat"."""
    mgr = make_mgr()
    key = mgr._build_dedup_key(make_event(camera_id="cam-5"), make_td(threat_type="rifle"))
    assert key == "cam-5:rifle:threat"


def test_dedup_key_rule_without_template() -> None:
    """rule present but template None -> default shape (a truthiness flip
    on `rule and rule.dedup_key_template` alone can't change the KEY; the
    None-format mutant chain still yields the template's literal value —
    see the template round pinning the FORMATTED string)."""
    mgr = make_mgr()
    key = mgr._build_dedup_key(
        make_event(camera_id="cam-5"), make_td(threat_type="rifle"), make_rule(template=None)
    )
    assert key == "cam-5:rifle:threat"


def test_dedup_key_template_formats_all_three_fields() -> None:
    """Live template: every placeholder is replaced with its VALUE (the
    format-kwarg None/XX/swap arms change the rendered key)."""
    mgr = make_mgr()
    rule = make_rule(rid="r-42", template="{rule_id}|{camera_id}|{threat_type}")
    key = mgr._build_dedup_key(make_event(camera_id="cam-7"), make_td(threat_type="pistol"), rule)
    assert key == "r-42|cam-7|pistol"


def test_dedup_key_bad_template_falls_back_to_default() -> None:
    """Unknown placeholder -> KeyError -> default (the `pass` swallow;
    removing it would propagate and this call fails loud)."""
    mgr = make_mgr()
    rule = make_rule(template="{nonexistent_field}")
    key = mgr._build_dedup_key(make_event(camera_id="cam-8"), make_td(threat_type="sword"), rule)
    assert key == "cam-8:sword:threat"


# ---------------------------------------------------------------------------
# process_threat_detection — validation, threshold, cooldown, full happy
# ---------------------------------------------------------------------------


def test_ptd_requires_both_inputs() -> None:
    """The two ValueError guards with EXACT messages (m3/m7 XX-case and
    swap arms die on the message equality; a gate drop lands on a later
    AttributeError instead of the pinned message)."""
    mgr = make_mgr()
    with pytest.raises(ValueError, match=r"^threat_detection is required$"):
        run(mgr.process_threat_detection(None, make_event()))
    with pytest.raises(ValueError, match=r"^event is required$"):
        run(mgr.process_threat_detection(make_td(), None))


def test_ptd_below_threshold_skips_with_exact_debug() -> None:
    """confidence strictly below -> None + the exact debug msg AND the
    full extra set (threat_type, confidence, threshold as record attrs)."""
    sess = FakeSession()
    mgr = make_mgr(session=sess, threshold=0.7)
    td = make_td(threat_type="knife", confidence=0.69, tid=901)
    with logcap() as cap:
        assert run(mgr.process_threat_detection(td, make_event())) is None
    assert cap.msgs() == ["Skipping threat alert: confidence 0.69 below threshold 0.7"]
    rec = cap.records[0]
    assert rec.threat_type == "knife"
    assert rec.confidence == 0.69
    assert rec.threshold == 0.7
    assert sess.added == []


def test_ptd_boundary_confidence_equal_threshold_creates() -> None:
    """The process_one threshold polarity (m105 family in pmd has the
    list-comprehension twin; here the `<` gate) — confidence EXACTLY at
    the threshold is NOT skipped (a `>=` flip skips it)."""
    sess = FakeSession(results=[])
    wh = FakeWebhook()
    mgr = make_mgr(session=sess, threshold=0.7)
    td = make_td(threat_type="knife", confidence=0.7)
    with patched(tm, "get_webhook_service", lambda: wh):
        alert = run(mgr.process_threat_detection(td, make_event()))
    assert alert is not None
    assert alert.severity is AlertSeverity.HIGH
    assert wh.calls[0][3] == "alert-1"


def test_ptd_in_cooldown_skips_with_exact_debug() -> None:
    """The cooldown skip path with the cooldown SPY tuple and the exact
    debug message/extra — pins the (dedup_key, 300, None) call shape."""
    existing = make_alert()
    sess = FakeSession(results=[existing])
    mgr = make_mgr(session=sess)
    spy = cooldown_spy(mgr)
    td = make_td(threat_type="knife")
    with logcap() as cap:
        assert run(mgr.process_threat_detection(td, make_event(camera_id="cam-1"))) is None
    assert spy == [("cam-1:knife:threat", 300, None)]
    assert cap.msgs() == ["Skipping threat alert: in cooldown (dedup_key=cam-1:knife:threat)"]
    rec = cap.records[0]
    assert rec.threat_type == "knife"
    assert rec.dedup_key == "cam-1:knife:threat"
    assert sess.added == []


def test_ptd_happy_full_single_flow() -> None:
    """The whole happy path: alert kwargs (event_id, rule_id None,
    severity from the type map, PENDING, default dedup key, channels []
    — not None), the FULL alert_metadata dict, session add/flush/refresh
    ORDER, the info log msg + all five extras, the exact broadcast
    payload for the created alert, and the exact webhook call tuple."""
    sess = FakeSession()
    redis = FakeRedis()
    wh = FakeWebhook()
    mgr = make_mgr(session=sess, redis=redis)
    spy = cooldown_spy(mgr)
    td = make_td(tid=955, threat_type="gun", confidence=0.95)
    event = make_event(eid=77, camera_id="cam-1", risk_score=61)
    with patched(tm, "get_webhook_service", lambda: wh), logcap() as cap:
        alert = run(mgr.process_threat_detection(td, event))

    assert alert is not None
    assert alert.event_id == 77
    assert alert.rule_id is None
    assert alert.severity is AlertSeverity.CRITICAL
    assert alert.status is AlertStatus.PENDING
    assert alert.dedup_key == "cam-1:gun:threat"
    assert alert.channels == []
    assert alert.alert_metadata == {
        "threat_type": "gun",
        "threat_confidence": 0.95,
        "threat_detection_id": 955,
        "auto_generated": True,
        "source": "threat_monitor_service",
    }
    assert sess.added == [alert]
    assert sess.flushes == 1 and sess.refreshed == [alert]
    assert spy == [("cam-1:gun:threat", 300, None)]
    assert cap.msgs() == [
        "Created threat alert: critical for gun",
        "Broadcast alert.created for threat alert alert-1",
    ]
    rec = cap.records[0]
    assert rec.levelno == logging.INFO
    assert rec.alert_id == "alert-1"
    assert rec.event_id == 77
    assert rec.threat_type == "gun"
    assert rec.severity == "critical"
    assert rec.confidence == 0.95

    assert len(redis.published) == 1
    channel, payload = redis.published[0]
    assert channel == "websocket:events"
    assert json.loads(payload) == {
        "type": "alert.created",
        "data": {
            "id": "alert-1",
            "event_id": 77,
            "rule_id": None,
            "severity": "critical",
            "status": "pending",
            "dedup_key": "cam-1:gun:threat",
            "created_at": CREATED_AT.isoformat(),
            "updated_at": UPDATED_AT.isoformat(),
            "camera_id": "cam-1",
            "threat_type": "gun",
            "threat_confidence": 0.95,
        },
    }
    assert wh.calls == [
        (
            sess,
            WebhookEventType.ALERT_FIRED,
            {
                "alert_id": "alert-1",
                "event_id": 77,
                "rule_id": None,
                "severity": "critical",
                "status": "pending",
                "dedup_key": "cam-1:gun:threat",
                "channels": [],
                "matched_conditions": ["threat_detected"],
                "camera_id": "cam-1",
                "risk_score": 61,
                "threat_metadata": {
                    "threat_type": "gun",
                    "threat_confidence": 0.95,
                    "threat_detection_id": 955,
                    "auto_generated": True,
                    "source": "threat_monitor_service",
                },
            },
            "alert-1",
        )
    ]


def test_ptd_with_rule_full_polarity() -> None:
    """Rule round: live dedup_key_template + cooldown_seconds 42 —
    the FORMATTED key reaches the cooldown call (spy tuple third slot is
    the rule OBJECT identity), the rule's cooldown value (not 300) is
    passed, alert.rule_id is the rule's id, and the severity comes from
    the KNIFE type map (the severity arg is the detection's own hint
    "critical" but the mapped knife severity HIGH must win — a
    get_threat_severity arg mutation lands elsewhere)."""
    sess = FakeSession(results=[])
    mgr = make_mgr(session=sess)
    spy = cooldown_spy(mgr)
    rule = make_rule(
        rid="r-9", template="R:{rule_id}@{camera_id}/{threat_type}", cooldown_seconds=42
    )
    td = make_td(tid=960, threat_type="knife", confidence=0.9, severity="critical")
    wh = FakeWebhook()
    with patched(tm, "get_webhook_service", lambda: wh):
        alert = run(mgr.process_threat_detection(td, make_event(camera_id="cam-3"), rule))
    assert alert is not None
    assert wh.calls[0][3] == "alert-1"
    assert alert.dedup_key == "R:r-9@cam-3/knife"
    assert alert.rule_id == "r-9"
    assert alert.severity is AlertSeverity.HIGH
    assert spy == [("R:r-9@cam-3/knife", 42, rule)]


# ---------------------------------------------------------------------------
# process_multiple_threat_detections — filter, winner, hint, metadata,
# cooldown, full downstream pins
# ---------------------------------------------------------------------------


def test_pmd_empty_list_returns_none_silently() -> None:
    """Empty threat list -> None with NO log and NO session traffic."""
    sess = FakeSession()
    mgr = make_mgr(session=sess)
    with logcap() as cap:
        assert run(mgr.process_multiple_threat_detections([], make_event())) is None
    assert cap.msgs() == []
    assert sess.added == []


def test_pmd_all_below_threshold_skips_with_exact_debug() -> None:
    """All-below -> None + the count+threshold debug message (exact
    integers; the len(...) and threshold values in the f-string)."""
    sess = FakeSession()
    mgr = make_mgr(session=sess, threshold=0.7)
    tds = [
        make_td(tid=1, threat_type="knife", confidence=0.3),
        make_td(tid=2, threat_type="gun", confidence=0.6),
    ]
    with logcap() as cap:
        assert run(mgr.process_multiple_threat_detections(tds, make_event())) is None
    assert cap.msgs() == ["Skipping multi-threat alert: all 2 detections below threshold 0.7"]
    assert sess.added == []


def test_pmd_boundary_confidence_survives_the_filter() -> None:
    """m3 (>= -> >): a threat at confidence EXACTLY the threshold must be
    VALID — the alert must exist with total_threats 1 (a > flip takes the
    all-below skip instead)."""
    sess = FakeSession(results=[])
    mgr = make_mgr(session=sess, threshold=0.7)
    wh = FakeWebhook()
    with patched(tm, "get_webhook_service", lambda: wh):
        alert = run(
            mgr.process_multiple_threat_detections(
                [make_td(threat_type="knife", confidence=0.7)], make_event()
            )
        )
    assert alert is not None
    assert alert.alert_metadata["total_threats"] == 1
    assert wh.calls[0][3] == "alert-1"


def test_pmd_severity_winner_and_full_metadata() -> None:
    """[bat(MEDIUM), gun(CRITICAL), below-threshold knife] with a FIXED
    creation-order list: the CRITICAL gun wins the max (key-collapse m6
    -> None crash / m11 get(None,0) all make the FIRST valid entry win);
    detected_threats holds ONLY the two valid threats in input order
    with exact per-threat dicts (m47-m56 key/value flips die),
    total_threats 2, and the headline keys come from the WINNER."""
    sess = FakeSession(results=[])
    redis = FakeRedis()
    wh = FakeWebhook()
    mgr = make_mgr(session=sess, redis=redis)
    spy = cooldown_spy(mgr)
    bat = make_td(tid=101, threat_type="bat", confidence=0.8, severity=None)
    gun = make_td(tid=102, threat_type="gun", confidence=0.85, severity=None)
    weak = make_td(tid=103, threat_type="knife", confidence=0.1, severity=None)
    event = make_event(eid=77, camera_id="cam-1", risk_score=70)
    with patched(tm, "get_webhook_service", lambda: wh), logcap() as cap:
        alert = run(mgr.process_multiple_threat_detections([bat, gun, weak], event))

    assert alert is not None
    assert alert.event_id == 77
    assert alert.severity is AlertSeverity.CRITICAL
    assert alert.dedup_key == "cam-1:gun:threat"
    assert sess.added == [alert]
    assert alert.alert_metadata == {
        "threat_type": "gun",
        "threat_confidence": 0.85,
        "threat_detection_id": 102,
        "detected_threats": [
            {"type": "bat", "confidence": 0.8, "severity": "medium", "detection_id": 101},
            {"type": "gun", "confidence": 0.85, "severity": "critical", "detection_id": 102},
        ],
        "total_threats": 2,
        "auto_generated": True,
        "source": "threat_monitor_service",
    }
    assert spy == [("cam-1:gun:threat", 300, None)]
    assert cap.msgs() == [
        "Created multi-threat alert: critical with 2 threats",
        "Broadcast alert.created for threat alert alert-1",
    ]
    rec = cap.records[0]
    assert rec.levelno == logging.INFO
    assert rec.alert_id == "alert-1"
    assert rec.event_id == 77
    assert rec.threat_count == 2
    assert rec.severity == "critical"

    assert json.loads(redis.published[0][1])["data"]["threat_type"] == "gun"
    assert wh.calls[0][2]["camera_id"] == "cam-1"
    assert wh.calls[0][3] == "alert-1"


def test_pmd_severity_hint_breaks_the_tie() -> None:
    """m8/m10/m23/m25/m52/m54 (severity-HINT drops): [knife, mystery
    (hint "critical")] — WITH the hint, mystery maps CRITICAL (priority
    3) and wins; dropping the hint makes both HIGH (2) and max() returns
    the FIRST entry (knife). The winner name is the discriminator."""
    sess = FakeSession(results=[])
    mgr = make_mgr(session=sess)
    knife = make_td(tid=201, threat_type="knife", confidence=0.9, severity=None)
    mystery = make_td(tid=202, threat_type="mystery", confidence=0.9, severity="critical")
    wh = FakeWebhook()
    with patched(tm, "get_webhook_service", lambda: wh):
        alert = run(
            mgr.process_multiple_threat_detections([knife, mystery], make_event(camera_id="cam-h"))
        )
    assert alert is not None
    assert wh.calls[0][2]["threat_metadata"]["detected_threats"][1]["severity"] == "critical"
    assert alert.alert_metadata["threat_type"] == "mystery"
    assert alert.severity is AlertSeverity.CRITICAL
    assert alert.dedup_key == "cam-h:mystery:threat"
    # per-threat severities use the hint too: mystery -> "critical"
    assert alert.alert_metadata["detected_threats"][1]["severity"] == "critical"


def test_pmd_in_cooldown_skips_with_exact_debug() -> None:
    """Cooldown skip path: debug message with the winner's key, spy
    tuple with the RULE passed through, no session traffic."""
    existing = make_alert()
    sess = FakeSession(results=[existing])
    mgr = make_mgr(session=sess)
    spy = cooldown_spy(mgr)
    rule = make_rule(rid="r-5", template=None, cooldown_seconds=90)
    tds = [make_td(tid=301, threat_type="rifle", confidence=0.95)]
    with logcap() as cap:
        result = run(
            mgr.process_multiple_threat_detections(tds, make_event(camera_id="cam-c"), rule)
        )
    assert result is None
    assert spy == [("cam-c:rifle:threat", 90, rule)]
    assert cap.msgs() == ["Skipping multi-threat alert: in cooldown (dedup_key=cam-c:rifle:threat)"]
    assert sess.added == []


def test_pmd_with_rule_full_polarity() -> None:
    """Rule round end-to-end: template-formatted key, rule_id on the
    alert, cooldown 42 in the spy tuple, channels [] (not None)."""
    sess = FakeSession(results=[])
    mgr = make_mgr(session=sess)
    spy = cooldown_spy(mgr)
    rule = make_rule(
        rid="r-8", template="M/{rule_id}/{camera_id}/{threat_type}", cooldown_seconds=42
    )
    wh = FakeWebhook()
    with patched(tm, "get_webhook_service", lambda: wh):
        alert = run(
            mgr.process_multiple_threat_detections(
                [make_td(tid=401, threat_type="crowbar", confidence=0.75)],
                make_event(camera_id="cam-r"),
                rule,
            )
        )
    assert alert is not None
    assert alert.dedup_key == "M/r-8/cam-r/crowbar"
    assert alert.rule_id == "r-8"
    assert alert.channels == []
    assert alert.severity is AlertSeverity.MEDIUM
    assert spy == [("M/r-8/cam-r/crowbar", 42, rule)]
