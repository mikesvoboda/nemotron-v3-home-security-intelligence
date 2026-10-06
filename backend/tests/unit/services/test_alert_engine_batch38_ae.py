# TARGET-MODULE: backend.services.alert_engine
"""Battery AE - campaign #29 backend/services/alert_engine.py (241 survivors).

Kill surfaces (each proven by construction against the pristine module):
  * SQL statement families: FakeSession routes on the EXACT compiled
    statement text plus the bound param dict, so select(None)/where(None)/
    is_(True|False|None)/== vs !=/limit flips either render different text,
    bind different params, or blow up before the route.
  * The webhook payload is pinned as a whole 11-key dict (plus strict str
    types for severity/status) on a raw-args spy installed by swapping the
    ae.get_webhook_service module global, so key renames, enum-vs-str
    polarity, and call-arg deletions (positional shift, missing event_id
    kwarg) all bite (CAPTURE #7 shape).
  * Scheduling boundaries run at exactly-equal operands (start == now,
    overnight edges) because the <= -> < twins only differ there.
  * Non-table severity strings ("bogus") are the lever that makes every
    SEVERITY_PRIORITY / THREAT_SEVERITY_PRIORITY .get-default arm
    observable: those defaults only fire for severities outside the table.

Honesty ledger (registered EQUIVALENTS - value-identical by construction):
  _check_cooldown m8/m18: skip_locked True -> None/False renders identical
    text under the default compiler (FOR UPDATE only) and lock semantics
    are invisible to a fake session.
  _check_dwell_time m15/m41: calculate_dwell_time prefers exit_time over
    its argument and falls back to utc_now() when passed None - both None
    sites render identical dwell seconds for settled records and only
    clock-jitter for open ones.
  _check_threat_detected m21: `if rule.threat_min_severity` -> `or True`:
    the true branch then evaluates .get(rule.threat_min_severity, 0) which
    is 0 for every falsy min_severity - identical to the else arm.
  _check_schedule m30: `len(days) > 0` -> `>= 0` - gated by `days and ...`
    so any surviving list is non-empty; both branches agree.
  _build_dedup_key m4: the "{CAMERA_ID}:{RULE_ID}" default raises KeyError
    inside format() and the handler returns f"{camera_id}:{rule_id}" - the
    exact same string and warning.
  test_rule_against_events m8/m10 and _batch_load_detections_for_events
    m30/m32: .get(event.id, []) default is unreachable - both maps are
    pre-seeded from exactly the same event list.
(Original ledger also carried _load_event_detections m1/m2 - run-1
adjudication DEMOTED them to killable: they only look equivalent when the
try fast path is never exercised; the _ProbeEvent fast-path test kills
them along with the m6/m7/m8 return-line births.)
"""

import ast
import asyncio
import inspect as pyinspect
import logging
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

import backend.services.alert_engine as ae
from backend.api.schemas.outbound_webhook import WebhookEventType
from backend.core.time_utils import utc_now_naive
from backend.models import AlertSeverity, AlertStatus, Event
from backend.models.enums import TrustStatus
from backend.services.alert_engine import (
    AlertRuleEngine,
    EvaluationResult,
    TriggeredRule,
)

_SRC = pyinspect.getsource(ae)


def n(s):
    return " ".join(str(s).split())


# EXACT compiled statement texts of the module's 12 query families,
# compiled pristine (whitespace-normalized) and transcribed here as static
# literals - never re-derived from the module source at runtime: under the
# trampoline tree the source text also contains every MUTANT body, so a
# runtime extraction could compile a mutant's statement as the "expected"
# text. FakeSession routes on these; a statement rewrite either mismatches
# (AssertionError -> killed) or rebinds params.
_SQL_RULES = "SELECT alert_rules.id, alert_rules.name, alert_rules.description, alert_rules.enabled, alert_rules.severity, alert_rules.risk_threshold, alert_rules.object_types, alert_rules.camera_ids, alert_rules.zone_ids, alert_rules.min_confidence, alert_rules.schedule, alert_rules.dwell_time_enabled, alert_rules.conditions, alert_rules.dwell_threshold_seconds, alert_rules.exclude_household_members, alert_rules.pose_types, alert_rules.pose_confidence_threshold, alert_rules.action_types, alert_rules.action_confidence_threshold, alert_rules.threat_detection_enabled, alert_rules.threat_types, alert_rules.threat_min_severity, alert_rules.threat_confidence_threshold, alert_rules.smoke_fire_detection_enabled, alert_rules.smoke_fire_consecutive_required, alert_rules.smoke_fire_confidence_threshold, alert_rules.dedup_key_template, alert_rules.cooldown_seconds, alert_rules.channels, alert_rules.created_at, alert_rules.updated_at FROM alert_rules WHERE alert_rules.enabled IS true"
_SQL_TRUST = "SELECT DISTINCT entities.trust_status FROM entities WHERE entities.primary_detection_id IN (__[POSTCOMPILE_primary_detection_id_1])"
_SQL_EVDET = "SELECT event_detections.detection_id FROM event_detections WHERE event_detections.event_id = :event_id_1"
_SQL_JUNC = "SELECT event_detections.event_id, event_detections.detection_id FROM event_detections WHERE event_detections.event_id IN (__[POSTCOMPILE_event_id_1])"
_SQL_DZONES = "SELECT DISTINCT dwell_time_records.zone_id FROM dwell_time_records WHERE dwell_time_records.camera_id = :camera_id_1 AND dwell_time_records.exit_time IS NULL"
_SQL_ZONES = "SELECT polygon_zones.id, polygon_zones.camera_id, polygon_zones.name, polygon_zones.polygon, polygon_zones.zone_type, polygon_zones.alert_threshold, polygon_zones.target_classes, polygon_zones.is_active, polygon_zones.color, polygon_zones.current_count, polygon_zones.loitering_threshold_seconds, polygon_zones.loitering_alert_enabled, polygon_zones.created_at FROM polygon_zones WHERE polygon_zones.id IN (__[POSTCOMPILE_id_1]) AND polygon_zones.loitering_alert_enabled IS true"
_SQL_DWELL = "SELECT dwell_time_records.id, dwell_time_records.zone_id, dwell_time_records.track_id, dwell_time_records.camera_id, dwell_time_records.object_class, dwell_time_records.entry_time, dwell_time_records.exit_time, dwell_time_records.total_seconds, dwell_time_records.triggered_alert FROM dwell_time_records WHERE dwell_time_records.zone_id = :zone_id_1 AND dwell_time_records.exit_time IS NULL"
_SQL_POSE = "SELECT pose_results.id, pose_results.detection_id, pose_results.keypoints, pose_results.pose_class, pose_results.confidence, pose_results.is_suspicious, pose_results.created_at FROM pose_results WHERE pose_results.detection_id IN (__[POSTCOMPILE_detection_id_1])"
_SQL_ACTION = "SELECT action_results.id, action_results.detection_id, action_results.action, action_results.confidence, action_results.is_suspicious, action_results.all_scores, action_results.created_at FROM action_results WHERE action_results.detection_id IN (__[POSTCOMPILE_detection_id_1])"
_SQL_THREAT = "SELECT threat_detections.id, threat_detections.detection_id, threat_detections.threat_type, threat_detections.confidence, threat_detections.severity, threat_detections.bbox, threat_detections.created_at FROM threat_detections WHERE threat_detections.detection_id IN (__[POSTCOMPILE_detection_id_1])"
_SQL_SMOKE = "SELECT detections.id, detections.camera_id, detections.file_path, detections.file_type, detections.detected_at, detections.object_type, detections.confidence, detections.bbox_x, detections.bbox_y, detections.bbox_width, detections.bbox_height, detections.thumbnail_path, detections.media_type, detections.duration, detections.video_codec, detections.video_width, detections.video_height, detections.track_id, detections.track_confidence, detections.search_vector, detections.labels FROM detections WHERE detections.id IN (__[POSTCOMPILE_id_1])"
_SQL_COOLDOWN = "SELECT alerts.id, alerts.event_id, alerts.rule_id, alerts.severity, alerts.status, alerts.created_at, alerts.updated_at, alerts.delivered_at, alerts.channels, alerts.dedup_key, alerts.metadata, alerts.version_id, alerts.is_high_priority FROM alerts WHERE alerts.dedup_key = :dedup_key_1 AND alerts.rule_id = :rule_id_1 AND alerts.created_at >= :created_at_1 LIMIT :param_1 FOR UPDATE"


class _Res:
    def __init__(self, rows):
        self._rows = list(rows)

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class FakeSession:
    """Routes on EXACT compiled statement text; records bound params."""

    def __init__(self, routes=None):
        self.routes = dict(routes or {})
        self.calls = []
        self.added = []
        self.flushes = 0

    async def execute(self, stmt):
        if stmt is None:
            raise AssertionError("session.execute(None)")
        text = n(stmt)
        params = dict(stmt.compile().params)
        self.calls.append((text, params))
        if text not in self.routes:
            raise AssertionError(f"unrouted statement: {text}")
        rows = self.routes[text]
        return _Res(rows(params) if callable(rows) else rows)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushes += 1


def rule(**kw):
    base = {
        "id": 1,
        "name": "r1",
        "severity": AlertSeverity.LOW,
        "risk_threshold": None,
        "camera_ids": None,
        "object_types": None,
        "min_confidence": None,
        "zone_ids": None,
        "schedule": None,
        "dwell_time_enabled": False,
        "pose_types": None,
        "pose_confidence_threshold": None,
        "action_types": None,
        "action_confidence_threshold": None,
        "threat_detection_enabled": False,
        "threat_types": None,
        "threat_min_severity": None,
        "threat_confidence_threshold": None,
        "smoke_fire_detection_enabled": False,
        "smoke_fire_confidence_threshold": None,
        "smoke_fire_consecutive_required": None,
        "dedup_key_template": None,
        "cooldown_seconds": None,
        "channels": None,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def det(id=1, object_type="person", confidence=0.9):
    return SimpleNamespace(id=id, object_type=object_type, confidence=confidence)


def ev(id=7, camera_id="cam-1", risk_score=8.5, started_at=None, **kw):
    return Event(id=id, camera_id=camera_id, risk_score=risk_score, started_at=started_at, **kw)


def vrow(created_at, id, verdict):
    return SimpleNamespace(created_at=created_at, id=id, verdict=verdict)


class SlotsEvent:
    """No __dict__: probes the getattr(event, '__dict__', <default>) guard."""

    __slots__ = ("camera_id", "id", "risk_score")

    def __init__(self):
        self.id = 77
        self.camera_id = "cam-1"
        self.risk_score = 8.5


class _ProbeBase(DeclarativeBase):
    pass


class _ProbeEvent(_ProbeBase):
    """Instrumented instance whose ATTRIBUTE access cannot see its own
    state.dict entry: the class-level property (a data descriptor) wins
    over the __dict__ key, so inside _load_event_detections the try fast
    path (reads state.dict["detections"]) and the except attribute probe
    (reads event.detections -> None) return DIFFERENT values - the only
    shape that observes the fast-path return line at all."""

    __tablename__ = "battery_ae_probe"

    id: Mapped[int] = mapped_column(primary_key=True)

    @property
    def detections(self):
        return None


class BatchSpy:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return list(self.rows)


class WebhookSpy:
    def __init__(self, raises=None):
        self.calls = []
        self.raises = raises

    async def trigger_webhooks_for_event(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.raises:
            raise self.raises


class WeirdEq:
    """Not a str, yet == "smoke" - kills the isinstance-and -> or flip."""

    def __eq__(self, other):
        return other in ("smoke", "fire")

    def __hash__(self):
        return 0


class _RecHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def caplogs(fn):
    """Capture the module logger at DEBUG, passing the record list in.

    A DECORATOR with a zero-arg wrapper, not a pytest fixture: the b30
    sweep invokes every battery test with NO arguments, so a fixture
    parameter would fail the shipped-green control. No functools.wraps
    either - it would publish the wrapped (1-arg) signature via
    __wrapped__ and make pytest hunt for a fixture again.
    """

    def wrapper():
        handler = _RecHandler()
        lg = ae.logger
        prev_propagate, prev_level = lg.propagate, lg.level
        lg.addHandler(handler)
        lg.propagate = False
        lg.setLevel(logging.DEBUG)
        try:
            return fn(handler.records)
        finally:
            lg.removeHandler(handler)
            lg.propagate = prev_propagate
            lg.setLevel(prev_level)

    wrapper.__name__ = fn.__name__
    wrapper.__qualname__ = fn.__qualname__
    wrapper.__doc__ = fn.__doc__
    return wrapper


def patched(fn):
    """Restore the swapped module globals after the test (zero-arg wrapper)."""

    def wrapper():
        saved_gws, saved_bfd = ae.get_webhook_service, ae.batch_fetch_detections
        try:
            return fn()
        finally:
            ae.get_webhook_service = saved_gws
            ae.batch_fetch_detections = saved_bfd

    wrapper.__name__ = fn.__name__
    wrapper.__qualname__ = fn.__qualname__
    wrapper.__doc__ = fn.__doc__
    return wrapper


run = asyncio.run


def _rec_msgs(records, level):
    return [r.getMessage() for r in records if r.levelno == level]


CT = datetime(2026, 10, 3, 10, 0)  # a Saturday


def _base_routes():
    return {_SQL_TRUST: [], _SQL_RULES: [], _SQL_COOLDOWN: []}


# ---------------------------------------------------------------- trust + rules


def test_get_enabled_rules_statement_family():
    # m1/m7 (None stmt/execute), m2 (clause dropped), m3 (select(NULL)),
    # m4/m5 (IS NULL / IS false) - every flip mismatches the pinned text.
    assert "WHERE alert_rules.enabled IS true" in _SQL_RULES
    s = FakeSession({_SQL_RULES: [rule(id=9, name="x")]})
    out = run(AlertRuleEngine(s)._get_enabled_rules())
    assert [r.id for r in out] == [9]
    assert s.calls == [(_SQL_RULES, {})]


@caplogs
def test_trusted_entity_skips_all_alerts(logs):
    # evaluate_event m13 (debug message -> None); trust statement family.
    s = FakeSession({_SQL_TRUST: [TrustStatus.TRUSTED.value]})
    result = run(AlertRuleEngine(s).evaluate_event(ev(), [det()], CT))
    assert isinstance(result, EvaluationResult)
    assert result.triggered_rules == []
    assert result.skipped_rules == []
    assert result.highest_severity is None
    assert result.entity_trust_status == TrustStatus.TRUSTED
    assert result.trusted_entity_skipped is True
    assert not result.has_triggers
    assert _rec_msgs(logs, logging.DEBUG) == [
        "Skipping alert generation for event 7 - trusted entity detected in detections"
    ]
    # the trusted short-circuit precedes _get_enabled_rules
    assert [t for t, _ in s.calls] == [_SQL_TRUST]


def test_trust_status_priority_and_statement():
    engine = AlertRuleEngine(FakeSession({_SQL_TRUST: []}))
    assert run(engine._get_aggregate_entity_trust_status([])) is None
    assert run(engine._get_aggregate_entity_trust_status([det(id=None)])) is None
    assert engine.session.calls == []  # both early returns run no query
    assert run(engine._get_aggregate_entity_trust_status([det(id=1)])) is None
    assert engine.session.calls[-1] == (_SQL_TRUST, {"primary_detection_id_1": [1]})
    for statuses, expected in (
        (
            [TrustStatus.TRUSTED.value, TrustStatus.UNTRUSTED.value, TrustStatus.UNKNOWN.value],
            TrustStatus.TRUSTED,
        ),
        ([TrustStatus.UNKNOWN.value, TrustStatus.UNTRUSTED.value], TrustStatus.UNTRUSTED),
        ([TrustStatus.UNKNOWN.value], TrustStatus.UNKNOWN),
        (["bogus-status"], TrustStatus.UNKNOWN),
    ):
        sx = FakeSession({_SQL_TRUST: statuses})
        assert run(AlertRuleEngine(sx)._get_aggregate_entity_trust_status([det(id=1)])) == expected


# ---------------------------------------------------------------- evaluate_event


def test_cooldown_round_statement_params_and_break_polarity():
    # cooldown m3/m5 (cutoff params), m7-m20 (pinned text + LIMIT param),
    # evaluate_event m26-m37 (dedup key flows to cooldown), m45 (break).
    s = FakeSession(_base_routes())
    r1 = rule(id=11, cooldown_seconds=300)
    r2 = rule(id=12, dedup_key_template="{camera_id}:{rule_id}:{object_type}")
    r3 = rule(id=13, cooldown_seconds=3600, dedup_key_template="{camera_id}")
    s.routes[_SQL_RULES] = [r1, r2, r3]
    result = run(AlertRuleEngine(s).evaluate_event(ev(), [det()], CT))
    cd = [p for t, p in s.calls if t == _SQL_COOLDOWN]
    assert len(cd) == 3
    assert cd[0]["dedup_key_1"] == "cam-1:11"
    assert cd[0]["rule_id_1"] == 11
    assert cd[0]["created_at_1"] == datetime(2026, 10, 3, 9, 55)
    assert cd[0]["param_1"] == 1
    assert "LIMIT :param_1" in _SQL_COOLDOWN and "FOR UPDATE" in _SQL_COOLDOWN
    assert cd[1]["created_at_1"] == datetime(2026, 10, 3, 9, 55)  # None or 300
    assert cd[1]["dedup_key_1"] == "cam-1:12:person"
    assert cd[2]["dedup_key_1"] == "cam-1"
    assert cd[2]["created_at_1"] == datetime(2026, 10, 3, 9, 0)
    assert result.skipped_rules == []
    assert [t.rule.id for t in result.triggered_rules] == [11, 12, 13]
    # m45 continue->break: with every cooldown hit, ALL rules get evaluated
    s2 = FakeSession(_base_routes())
    s2.routes[_SQL_RULES] = [r1, r2, r3]
    s2.routes[_SQL_COOLDOWN] = [SimpleNamespace(id=99)]
    res2 = run(AlertRuleEngine(s2).evaluate_event(ev(), [det()], CT))
    assert res2.triggered_rules == []
    assert [id(r) for r, _ in res2.skipped_rules] == [id(r1), id(r2), id(r3)]
    assert [reason for _, reason in res2.skipped_rules] == ["in_cooldown"] * 3


def test_untrusted_escalation_round():
    # m54-m56 (.get default on a non-table severity), m61-m74 (fields),
    # m79/m81 (compared-side defaults), sort order with a bogus severity.
    s = FakeSession(_base_routes())
    a = rule(id=1, name="A", severity=AlertSeverity.MEDIUM, cooldown_seconds=60)
    b = rule(id=2, name="B", severity=AlertSeverity.LOW, cooldown_seconds=60)
    c = rule(id=3, name="C", severity=AlertSeverity.HIGH, cooldown_seconds=60)
    d = rule(id=4, name="D", severity="bogus", cooldown_seconds=60)
    s.routes[_SQL_RULES] = [a, b, c, d]
    s.routes[_SQL_TRUST] = [TrustStatus.UNTRUSTED.value]
    result = run(AlertRuleEngine(s).evaluate_event(ev(), [det()], CT))
    assert result.skipped_rules == []  # m54/m55/m56 crash on the bogus rule
    by_id = {t.rule.id: t for t in result.triggered_rules}
    assert by_id[1].severity == AlertSeverity.HIGH
    assert by_id[1].original_severity == AlertSeverity.MEDIUM
    assert by_id[1].trust_adjusted is True
    assert by_id[1].matched_conditions == [
        "no_conditions (always matches)",
        "severity_escalated_untrusted_entity (medium -> high)",
    ]
    assert by_id[2].matched_conditions[-1] == "severity_escalated_untrusted_entity (low -> medium)"
    assert by_id[3].severity == AlertSeverity.CRITICAL
    assert (
        by_id[3].matched_conditions[-1] == "severity_escalated_untrusted_entity (high -> critical)"
    )
    assert by_id[4].severity == "bogus"  # the escalation table's default value
    assert by_id[4].original_severity == "bogus"
    assert by_id[4].trust_adjusted is False
    assert by_id[4].matched_conditions == ["no_conditions (always matches)"]
    assert result.highest_severity == AlertSeverity.CRITICAL
    # sort: CRITICAL (rule 3) leads, then HIGH (1), MEDIUM (2), bogus (0)
    assert [t.rule.id for t in result.triggered_rules] == [3, 1, 2, 4]
    assert result.entity_trust_status == TrustStatus.UNTRUSTED
    assert result.trusted_entity_skipped is False
    assert result.has_triggers
    assert by_id[1].dedup_key == "cam-1:1"
    for t in result.triggered_rules:
        assert t.dwell_time_match is None  # m67/m74 deleted-kwarg shape


def test_highest_severity_bogus_first():
    # m85/m87/m88 (result-side .get default) + m83 (>= re-assigns the
    # highest at an equal-priority tie between two bogus severities).
    s = FakeSession(_base_routes())
    d = rule(id=4, name="D", severity="bogus", cooldown_seconds=60)
    e = rule(id=5, name="E", severity="alsobogus", cooldown_seconds=60)
    s.routes[_SQL_RULES] = [d, e]
    s.routes[_SQL_TRUST] = [TrustStatus.UNTRUSTED.value]
    result = run(AlertRuleEngine(s).evaluate_event(ev(), [det()], CT))
    assert result.skipped_rules == []  # m85/m87 TypeError; m83 keeps equal
    assert result.highest_severity == "bogus"  # 0 > 0 is False, m83: assigns
    assert [t.rule.id for t in result.triggered_rules] == [4, 5]

    s2 = FakeSession(_base_routes())
    b = rule(id=2, name="B", severity=AlertSeverity.LOW, cooldown_seconds=60)
    s2.routes[_SQL_RULES] = [d, e, b]
    s2.routes[_SQL_TRUST] = [TrustStatus.UNTRUSTED.value]
    res2 = run(AlertRuleEngine(s2).evaluate_event(ev(), [det()], CT))
    assert res2.skipped_rules == []  # m85/m87: LOW(1) > None raises
    assert res2.highest_severity == AlertSeverity.MEDIUM  # 1 > 0; m88: 1 > 1 F
    assert [t.rule.id for t in res2.triggered_rules] == [2, 4, 5]


def test_highest_severity_lowest_first_sort_tie():
    # m82 (compared-side default 1), m105 (sort-key default 1): the LOW rule
    # goes first so the bogus rule sits BEHIND it (tie keeps insertion order).
    s = FakeSession(_base_routes())
    b = rule(id=2, name="B", severity=AlertSeverity.LOW, cooldown_seconds=60)
    d = rule(id=4, name="D", severity="bogus", cooldown_seconds=60)
    s.routes[_SQL_RULES] = [b, d]
    result = run(AlertRuleEngine(s).evaluate_event(ev(), [det()], CT))
    assert result.skipped_rules == []
    assert result.highest_severity == AlertSeverity.LOW  # bogus 0 never wins
    assert [t.rule.id for t in result.triggered_rules] == [2, 4]  # m105: [4, 2]
    assert [t.severity for t in result.triggered_rules] == [AlertSeverity.LOW, "bogus"]


@caplogs
def test_rule_error_round_and_dedup_fallback(logs):
    # evaluate_event m90-m94 (error msg + exc_info), _build_dedup_key m33.
    s = FakeSession(_base_routes())
    s.routes[_SQL_RULES] = [rule(id=21, name="bad", camera_ids=["cam-1"])]
    bare_event = SimpleNamespace(id=77)  # no camera_id -> AttributeError
    result = run(AlertRuleEngine(s).evaluate_event(bare_event, [], CT))
    assert result.triggered_rules == []
    assert len(result.skipped_rules) == 1
    skipped_rule, reason = result.skipped_rules[0]
    assert skipped_rule.id == 21
    assert reason.startswith("evaluation_error: ")
    assert "camera_id" in reason
    errs = [r for r in logs if r.levelno == logging.ERROR]
    assert len(errs) == 1
    assert errs[0].getMessage() == "Error evaluating rule 21: " + reason.split(": ", 1)[1]
    assert errs[0].exc_info is not None  # m91/m93/m94 (None/deleted/False)
    assert errs[0].exc_info[0] is AttributeError

    # dedup template with an unknown variable -> warning + camera:rule key
    logs.clear()
    s2 = FakeSession(_base_routes())
    s2.routes[_SQL_RULES] = [rule(id=22, name="tmpl", dedup_key_template="{bogus}")]
    res2 = run(AlertRuleEngine(s2).evaluate_event(ev(), [det()], CT))
    assert res2.triggered_rules[0].dedup_key == "cam-1:22"
    assert _rec_msgs(logs, logging.WARNING) == ["Invalid dedup_key_template variable: 'bogus'"]


def test_slots_event_triggers_pristine():
    # _evaluate_rule m8/m11: an event without __dict__ passes the gate
    # untouched (the None/deleted defaults raise TypeError -> skipped).
    s = FakeSession(_base_routes())
    s.routes[_SQL_RULES] = [rule(id=23, name="slots")]
    result = run(AlertRuleEngine(s).evaluate_event(SlotsEvent(), [], CT))
    assert result.skipped_rules == []
    assert result.triggered_rules[0].dedup_key == "cam-1:23"


# ---------------------------------------------------------------- _evaluate_rule


def test_verification_gate_rounds():
    # m18/m20/m21 (max key), m8/m11 (__dict__ probe defaults).
    engine = AlertRuleEngine(FakeSession())

    def evaluate(event):
        return run(engine._evaluate_rule(rule(), event, [], CT))

    e = ev()
    e.__dict__["verifications"] = [vrow(1, 1, "ok"), vrow(2, 2, "rejected")]
    assert evaluate(e) == (False, [], None)
    e2 = ev()
    e2.__dict__["verifications"] = [vrow(3, 5, "ok"), vrow(1, 9, "rejected")]
    assert evaluate(e2)[0] is True  # newest by (created_at, id) is the ok row
    e3 = ev()
    e3.__dict__["verifications"] = [vrow(1, 1, "rejected"), vrow(2, 2, "ok")]
    assert evaluate(e3)[0] is True  # m20: max(rows) w/o key compares rows -> raise
    e4 = ev()
    e4.__dict__["verifications"] = []
    assert evaluate(e4)[0] is True
    assert evaluate(SlotsEvent())[0] is True


@patched
def test_threat_and_smoke_condition_labels_through_evaluate_rule():
    # _evaluate_rule m92/m102: the "threat_detected"/"smoke_fire_detected"
    # labels appended AFTER the sub-checks pass - the direct _check_* rounds
    # above never observe these appends.
    ae.batch_fetch_detections = BatchSpy([])
    engine = AlertRuleEngine(
        FakeSession({_SQL_THREAT: [_thr()], _SQL_SMOKE: [smokerow(consecutive=5)]})
    )
    _, conds_t, _ = run(
        engine._evaluate_rule(rule(threat_detection_enabled=True), ev(), [det()], CT)
    )
    assert conds_t == ["threat_detected"]
    _, conds_s, _ = run(
        engine._evaluate_rule(rule(smoke_fire_detection_enabled=True), ev(), [det()], CT)
    )
    assert conds_s == ["smoke_fire_detected"]
    _, conds_b, _ = run(
        engine._evaluate_rule(
            rule(threat_detection_enabled=True, smoke_fire_detection_enabled=True),
            ev(),
            [det()],
            CT,
        )
    )
    assert conds_b == ["threat_detected", "smoke_fire_detected"]


@caplogs
def test_conditions_strings_and_zone_debug(logs):
    # m50 (zone debug None) + every matched-condition string + boundaries.
    engine = AlertRuleEngine(FakeSession())
    r = rule(
        id=4,
        risk_threshold=7.5,
        camera_ids=["cam-1", "cam-2"],
        object_types=["Person"],
        min_confidence=0.9,
        zone_ids=[3],
        schedule={"days": ["saturday"]},
    )
    matches, conds, dwell = run(engine._evaluate_rule(r, ev(), [det()], CT))
    assert matches is True and dwell is None
    assert conds == [
        "risk_score >= 7.5",
        "camera_id in ['cam-1', 'cam-2']",
        "object_type in ['Person']",
        "confidence >= 0.9",
        "within_schedule",
    ]
    assert _rec_msgs(logs, logging.DEBUG) == [
        "Zone condition in rule 4 - zone matching not yet implemented"
    ]
    assert run(engine._evaluate_rule(rule(risk_threshold=8.5), ev(), [], CT))[0] is True
    assert run(engine._evaluate_rule(rule(risk_threshold=8.6), ev(), [], CT)) == (False, [], None)
    assert run(engine._evaluate_rule(rule(risk_threshold=7.0), ev(risk_score=None), [], CT)) == (
        False,
        [],
        None,
    )
    assert (
        run(engine._evaluate_rule(rule(min_confidence=0.9), ev(), [det(confidence=0.9)], CT))[0]
        is True
    )
    assert run(
        engine._evaluate_rule(rule(min_confidence=0.91), ev(), [det(confidence=None)], CT)
    ) == (
        False,
        [],
        None,
    )
    assert (
        run(
            engine._evaluate_rule(
                rule(object_types=["PERSON"]), ev(), [det(object_type="person")], CT
            )
        )[0]
        is True
    )
    assert run(
        engine._evaluate_rule(rule(object_types=["car"]), ev(), [det(object_type=None)], CT)
    ) == (
        False,
        [],
        None,
    )
    assert run(engine._evaluate_rule(rule(object_types=["car"]), ev(), [], CT)) == (False, [], None)
    assert run(engine._evaluate_rule(rule(camera_ids=["other"]), ev(), [], CT)) == (False, [], None)


# ---------------------------------------------------------------- dwell time


def zone(id_, name="Z", thr=60):
    return SimpleNamespace(id=id_, name=name, loitering_threshold_seconds=thr)


def dwellrec(zone_id=9, track_id=42, entry=None, exit_=None):
    entry = datetime(2026, 10, 3, 9, 0) if entry is None else entry
    exit_ = datetime(2026, 10, 3, 9, 1) if exit_ is None else exit_  # exactly 60s

    def calc(current_time):
        end = exit_ or current_time or utc_now_naive()
        return (end - entry).total_seconds()

    return SimpleNamespace(zone_id=zone_id, track_id=track_id, calculate_dwell_time=calc)


@caplogs
def test_dwell_time_statement_family_and_match(logs):
    # m4-m8/m10 (camera query + params), m16-m26 (zones polarity),
    # m32-m38 (records query), m42 (>= vs > at the exact 60s tie), m52.
    s = FakeSession({_SQL_DZONES: [9], _SQL_ZONES: [zone(9)], _SQL_DWELL: [dwellrec()]})
    matched, details, match = run(
        AlertRuleEngine(s)._check_dwell_time(rule(id=1, dwell_time_enabled=True), ev())
    )
    assert matched is True
    assert details == ["loitering_in_zone:Z:60s(threshold:60s)"]
    assert (match.zone_id, match.track_id) == (9, 42)
    assert [t for t, _ in s.calls] == [_SQL_DZONES, _SQL_ZONES, _SQL_DWELL]
    assert s.calls[0][1] == {"camera_id_1": "cam-1"}
    assert s.calls[1][1] == {"id_1": [9]}
    assert s.calls[2][1] == {"zone_id_1": 9}
    assert "loitering_alert_enabled IS true" in _SQL_ZONES
    assert "exit_time IS NULL" in _SQL_DZONES and "exit_time IS NULL" in _SQL_DWELL
    assert _rec_msgs(logs, logging.DEBUG) == [
        "Loitering detected for rule 1: track 42 in zone Z for 60.0s (threshold: 60s)"
    ]
    # no zones from the camera query -> early return, no further queries
    s3 = FakeSession({_SQL_DZONES: [], _SQL_ZONES: [], _SQL_DWELL: []})
    assert run(AlertRuleEngine(s3)._check_dwell_time(rule(dwell_time_enabled=True), ev())) == (
        False,
        [],
        None,
    )
    assert [t for t, _ in s3.calls] == [_SQL_DZONES]
    # rule.zone_ids set -> the camera query is skipped entirely
    s4 = FakeSession({_SQL_ZONES: [zone(5)], _SQL_DWELL: []})
    matched4, _, _ = run(
        AlertRuleEngine(s4)._check_dwell_time(rule(dwell_time_enabled=True, zone_ids=[5]), ev())
    )
    assert matched4 is False
    assert [t for t, _ in s4.calls] == [_SQL_ZONES, _SQL_DWELL]
    # empty zones after the enabled filter -> no dwell query
    s5 = FakeSession({_SQL_DZONES: [9], _SQL_ZONES: []})
    assert run(AlertRuleEngine(s5)._check_dwell_time(rule(dwell_time_enabled=True), ev())) == (
        False,
        [],
        None,
    )
    assert [t for t, _ in s5.calls] == [_SQL_DZONES, _SQL_ZONES]


def test_dwell_end_to_end_through_evaluate_event():
    # evaluate_event m26-m34/m67/m74 + evaluate_rule m2/m62.
    s = FakeSession(
        {
            _SQL_RULES: [
                rule(
                    id=4,
                    dwell_time_enabled=True,
                    cooldown_seconds=60,
                    dedup_key_template="{camera_id}:{rule_id}:{zone_id}:{track_id}",
                )
            ],
            _SQL_DZONES: [9],
            _SQL_ZONES: [zone(9)],
            _SQL_DWELL: [dwellrec()],
            _SQL_COOLDOWN: [],
        }
    )
    result = run(AlertRuleEngine(s).evaluate_event(ev(), [], CT))
    t = result.triggered_rules[0]
    assert t.dedup_key == "cam-1:4:9:42"  # m2: "" init -> "" in details slot
    assert t.dwell_time_match is not None  # m67/m74
    assert (t.dwell_time_match.zone_id, t.dwell_time_match.track_id) == (9, 42)
    assert t.matched_conditions == ["loitering_in_zone:Z:60s(threshold:60s)"]
    assert [p for txt, p in s.calls if txt == _SQL_DZONES] == [{"camera_id_1": "cam-1"}]


# ---------------------------------------------------------------- pose / action


def test_pose_rounds():
    # m1 (guard flip -> query on the pose_types=None round), m7-m9/m12, m25.
    s = FakeSession({_SQL_POSE: [SimpleNamespace(pose_class="Sit", confidence=0.7)]})
    r = rule(pose_types=["SIT"], pose_confidence_threshold=0.7)
    assert run(AlertRuleEngine(s)._check_pose_type(r, [det()])) is True
    assert s.calls[-1] == (_SQL_POSE, {"detection_id_1": [1]})
    # m25: confidence EXACTLY at the threshold only passes under >=
    s2 = FakeSession({_SQL_POSE: [SimpleNamespace(pose_class="sit", confidence=0.7)]})
    assert run(AlertRuleEngine(s2)._check_pose_type(r, [det()])) is True
    s3 = FakeSession({_SQL_POSE: [SimpleNamespace(pose_class="SIT", confidence=None)]})
    assert run(AlertRuleEngine(s3)._check_pose_type(r, [det()])) is True
    s4 = FakeSession({_SQL_POSE: [SimpleNamespace(pose_class="stand", confidence=1.0)]})
    assert run(AlertRuleEngine(s4)._check_pose_type(r, [det()])) is False
    s5 = FakeSession({_SQL_POSE: [SimpleNamespace(pose_class=None, confidence=1.0)]})
    assert run(AlertRuleEngine(s5)._check_pose_type(r, [det()])) is False
    s6 = FakeSession({_SQL_POSE: [SimpleNamespace(pose_class="sit", confidence=0.69)]})
    assert run(AlertRuleEngine(s6)._check_pose_type(r, [det()])) is False
    # guards: the and-flip would run the query on the pose_types=None round
    s7 = FakeSession()
    assert run(AlertRuleEngine(s7)._check_pose_type(rule(pose_types=None), [det()])) is False
    assert run(AlertRuleEngine(s7)._check_pose_type(rule(pose_types=["sit"]), [])) is False
    assert s7.calls == []


def test_action_rounds():
    # m1 guard flip, m7-m9/m12, m20 (`and`->`or` crashes on a None action),
    # m25 threshold tie.
    s = FakeSession({_SQL_ACTION: [SimpleNamespace(action="run", confidence=0.7)]})
    r = rule(action_types=["RUN"], action_confidence_threshold=0.7)
    assert run(AlertRuleEngine(s)._check_action_type(r, [det()])) is True
    assert s.calls[-1] == (_SQL_ACTION, {"detection_id_1": [1]})
    s2 = FakeSession(
        {
            _SQL_ACTION: [
                SimpleNamespace(action=None, confidence=1.0),
                SimpleNamespace(action="run", confidence=1.0),
            ]
        }
    )
    assert run(AlertRuleEngine(s2)._check_action_type(r, [det()])) is True  # m20 raises
    s3 = FakeSession({_SQL_ACTION: [SimpleNamespace(action="walk", confidence=1.0)]})
    assert run(AlertRuleEngine(s3)._check_action_type(r, [det()])) is False
    s4 = FakeSession({_SQL_ACTION: [SimpleNamespace(action="RUN", confidence=0.7)]})
    assert run(AlertRuleEngine(s4)._check_action_type(r, [det()])) is True  # m25 tie
    s5 = FakeSession()
    assert run(AlertRuleEngine(s5)._check_action_type(rule(action_types=None), [det()])) is False
    assert run(AlertRuleEngine(s5)._check_action_type(rule(action_types=["run"]), [])) is False
    assert s5.calls == []


# ---------------------------------------------------------------- threat


def _thr(severity="critical", confidence=0.9, threat_type="weapon"):
    return SimpleNamespace(severity=severity, confidence=confidence, threat_type=threat_type)


def test_threat_rounds():
    # m1 guard, m7-m9/m12, m23-m27 (min-priority defaults via bogus
    # severity), m30-m34 (row priority), m35/m37 (< ties), m36/m38 (breaks).
    s = FakeSession({_SQL_THREAT: [_thr()]})
    assert (
        run(AlertRuleEngine(s)._check_threat_detected(rule(threat_detection_enabled=True), [det()]))
        is True
    )
    assert s.calls[-1] == (_SQL_THREAT, {"detection_id_1": [1]})

    def check(rows, **rule_kw):
        sx = FakeSession({_SQL_THREAT: rows})
        return run(
            AlertRuleEngine(sx)._check_threat_detected(
                rule(threat_detection_enabled=True, **rule_kw), [det()]
            )
        )

    assert (
        check([_thr(severity="low"), _thr(severity="critical")], threat_min_severity="high") is True
    )  # m36
    assert check([_thr(severity="high")], threat_min_severity="high") is True  # m35 tie
    assert (
        check([_thr(severity="critical", confidence=0.9)], threat_confidence_threshold=0.9) is True
    )  # m37 tie
    assert (
        check([_thr(confidence=0.1), _thr(confidence=0.95)], threat_confidence_threshold=0.5)
        is True
    )  # m38
    assert check([], threat_min_severity="high") is False
    # m23/m25/m26: an unknown MIN_SEVERITY consults the first .get default
    assert check([_thr(severity="low")], threat_min_severity="bogus") is True
    # m27: falsy min_severity takes the else-branch 0
    assert check([_thr(severity="low")], threat_min_severity=None) is True
    assert check([_thr(severity="low")], threat_min_severity="") is True
    # m30: the row severity feeds the priority table (critical >= high)
    assert check([_thr(severity="critical")], threat_min_severity="high") is True
    # m31/m33/m34: an unknown ROW severity consults the second .get default
    assert check([_thr(severity="bogus")], threat_min_severity="medium") is False
    assert check([_thr(severity="bogus")], threat_min_severity=None) is True
    # threat-type filter keeps its continue semantics
    assert (
        check([_thr(threat_type="x"), _thr(threat_type="weapon")], threat_types=["weapon"]) is True
    )
    assert check([_thr(threat_type="x")], threat_types=["weapon"]) is False
    s6 = FakeSession()
    assert (
        run(
            AlertRuleEngine(s6)._check_threat_detected(
                rule(threat_detection_enabled=False), [det()]
            )
        )
        is False
    )
    assert (
        run(AlertRuleEngine(s6)._check_threat_detected(rule(threat_detection_enabled=True), []))
        is False
    )
    assert s6.calls == []


# ---------------------------------------------------------------- smoke / fire


def smokerow(confidence=0.9, consecutive=None, detection_type=None):
    kw = {"confidence": confidence}
    if consecutive is not None:
        kw["consecutive_count"] = consecutive
    if detection_type is not None:
        kw["detection_type"] = detection_type
    return SimpleNamespace(**kw)


def test_smoke_rounds():
    # m11/m12 (consecutive default), m13-m15/m18 stmt, m23/m24, m26/m27,
    # m29 (and->or via a non-str equal member), m33/m34 (tuple strings).
    s = FakeSession({_SQL_SMOKE: [smokerow(consecutive=5)]})
    assert (
        run(AlertRuleEngine(s)._check_smoke_fire(rule(smoke_fire_detection_enabled=True), [det()]))
        is True
    )
    # the smoke/fire probe queries Detection.id, so the bind is id_1
    assert s.calls[-1] == (_SQL_SMOKE, {"id_1": [1]})

    def check(rows, **rule_kw):
        sx = FakeSession({_SQL_SMOKE: rows})
        return run(
            AlertRuleEngine(sx)._check_smoke_fire(
                rule(smoke_fire_detection_enabled=True, **rule_kw), [det()]
            )
        )

    # m12: the DEFAULT is 2 (not 3) - both rows are 2 so the mutant exhausts
    assert check([smokerow(consecutive=2), smokerow(consecutive=2)]) is True
    # m11: explicit 3 stays 3 (the `and 2` mutant would accept 2)
    assert check([smokerow(consecutive=2)], smoke_fire_consecutive_required=3) is False
    # m23/m24: below-or-at-threshold rows must continue, not break
    assert (
        check(
            [smokerow(confidence=0.5, detection_type="smoke")], smoke_fire_confidence_threshold=0.5
        )
        is True
    )
    assert (
        check(
            [smokerow(confidence=0.4), smokerow(confidence=0.9, detection_type="smoke")],
            smoke_fire_confidence_threshold=0.5,
        )
        is True
    )
    # m26: consecutive EXACTLY at the required count passes under <
    assert check([smokerow(consecutive=2)], smoke_fire_consecutive_required=2) is True
    # m27: the under-count row continues to the fire row
    assert check([smokerow(consecutive=1), smokerow(detection_type="fire")]) is True
    assert check([smokerow(detection_type="smoke")]) is True
    assert check([smokerow(detection_type="fire")]) is True  # kills m33
    assert check([smokerow(detection_type="FIRE")]) is False  # kills m34
    assert check([smokerow(detection_type=None)]) is False
    assert check([smokerow(detection_type=7)]) is False
    # m29: a non-str equal member must NOT pass the isinstance-gated `and`
    assert check([smokerow(detection_type=WeirdEq())]) is False
    assert check([]) is False
    s6 = FakeSession()
    assert (
        run(
            AlertRuleEngine(s6)._check_smoke_fire(rule(smoke_fire_detection_enabled=False), [det()])
        )
        is False
    )
    assert (
        run(AlertRuleEngine(s6)._check_smoke_fire(rule(smoke_fire_detection_enabled=True), []))
        is False
    )
    assert s6.calls == []


# ---------------------------------------------------------------- schedule


@caplogs
def test_schedule_boundaries(logs):
    # m31 (single-day list), m45 (`or` would parse the missing bound),
    # m53/m54 and m58/m59 at exactly-equal times, timezone conversion.
    engine = AlertRuleEngine(FakeSession())
    monday9 = datetime(2026, 10, 5, 9, 0)
    sched = {"days": ["monday"], "start_time": "09:00", "end_time": "17:00"}
    assert engine._check_schedule(sched, monday9) is True  # m53: start edge
    assert engine._check_schedule(sched, datetime(2026, 10, 5, 17, 0)) is True  # m54: end edge
    assert engine._check_schedule(sched, datetime(2026, 10, 5, 8, 59)) is False
    assert engine._check_schedule(sched, datetime(2026, 10, 5, 17, 1)) is False
    assert engine._check_schedule({"days": ["friday"]}, monday9) is False  # m31
    assert engine._check_schedule({"days": ["Monday"]}, monday9) is True
    assert engine._check_schedule({"days": []}, monday9) is True
    overnight = {"start_time": "22:00", "end_time": "06:00"}
    assert engine._check_schedule(overnight, datetime(2026, 10, 5, 22, 0)) is True  # m58 edge
    assert engine._check_schedule(overnight, datetime(2026, 10, 5, 6, 0)) is True  # m59 edge
    assert engine._check_schedule(overnight, datetime(2026, 10, 5, 21, 59)) is False
    assert engine._check_schedule(overnight, datetime(2026, 10, 5, 6, 1)) is False
    assert engine._check_schedule(overnight, datetime(2026, 10, 5, 2, 0)) is True
    assert engine._check_schedule({}, monday9) is True
    before = len(logs)
    assert engine._check_schedule({"start_time": "09:00"}, monday9) is True
    assert len(logs) == before  # m45 `or` would parse None and warn
    assert engine._check_schedule({"days": ["sunday"]}, monday9) is False  # default UTC
    assert len(logs) == before  # m10/m11: unknown/default tz names would warn
    # 20:00 UTC Sunday == 05:00 Monday in Tokyo
    assert (
        engine._check_schedule(
            {"days": ["monday"], "timezone": "Asia/Tokyo"}, datetime(2026, 10, 4, 20, 0)
        )
        is True
    )
    assert (
        engine._check_schedule(
            {"days": ["sunday"], "timezone": "Asia/Tokyo"}, datetime(2026, 10, 4, 20, 0)
        )
        is False
    )


@caplogs
def test_schedule_invalid_timezone_warns(logs):
    # m10/m11/m14: an unknown zone warns with the tz name, then falls back.
    engine = AlertRuleEngine(FakeSession())
    assert engine._check_schedule({"timezone": "Mars/Olympus"}, datetime(2026, 10, 5, 9, 0)) is True
    assert _rec_msgs(logs, logging.WARNING) == [
        "Invalid timezone Mars/Olympus, using UTC: 'No time zone found with key Mars/Olympus'"
    ]
    logs.clear()
    assert (
        engine._check_schedule(
            {"start_time": "90:00", "end_time": "17:00"}, datetime(2026, 10, 5, 9, 0)
        )
        is True
    )
    warns = _rec_msgs(logs, logging.WARNING)
    assert len(warns) == 1
    assert warns[0].startswith("Error parsing schedule time: ")


# ---------------------------------------------------------------- detections loading


@patched
def test_load_event_detections_fast_path_state_dict():
    # The try fast path reads state.dict["detections"] while the except
    # probe reads event.detections - on a REAL instrumented event both see
    # the same relationship, so no ordinary event distinguishes the two
    # returns. _ProbeEvent's class-level property hides its own state.dict
    # entry (descriptor beats __dict__), forcing the two paths to DIFFERENT
    # values: only a correct fast-path return yields [d1] with zero queries.
    # Kills m1/m2 (state=None / inspect(None) -> except -> attribute None ->
    # junction query) and the same-run birth family on the return line
    # (list(None), dict["XXdetectionsXX"], dict["DETECTIONS"]).
    d1, d2 = det(id=1), det(id=2)
    s = FakeSession({_SQL_EVDET: [2]})
    spy = BatchSpy([d2])
    ae.batch_fetch_detections = spy
    engine = AlertRuleEngine(s)
    p = _ProbeEvent(id=5)
    p.__dict__["detections"] = [d1]  # bypasses the property's no-setter
    assert run(engine._load_event_detections(p)) == [d1]
    assert s.calls == [] and spy.calls == []


@patched
def test_load_event_detections_rounds():
    # m11-m16 (junction stmt), m20-m23 (batch_fetch call shape); m1/m2 die
    # in the fast-path test above.
    d1 = det(id=1)
    s = FakeSession({_SQL_EVDET: [1, 2]})
    spy = BatchSpy([d1])
    ae.batch_fetch_detections = spy
    engine = AlertRuleEngine(s)

    # inspect-raises event (mock-shaped) with populated detections
    assert run(engine._load_event_detections(SimpleNamespace(id=7, detections=[d1]))) == [d1]
    assert spy.calls == [] and s.calls == []

    # transient real event, unloaded relationship -> junction query + fetch
    assert run(engine._load_event_detections(ev(id=7))) == [d1]
    assert s.calls[-1] == (_SQL_EVDET, {"event_id_1": 7})
    assert spy.calls == [((s, [1, 2]), {})]

    # junction empty -> [] with no fetch
    s2 = FakeSession({_SQL_EVDET: []})
    spy2 = BatchSpy([d1])
    ae.batch_fetch_detections = spy2
    assert run(AlertRuleEngine(s2)._load_event_detections(ev(id=8))) == []
    assert spy2.calls == []

    # real event with a loaded relationship short-circuits the query
    s3 = FakeSession()
    spy3 = BatchSpy([])
    ae.batch_fetch_detections = spy3
    e3 = Event(id=9, camera_id="c", risk_score=1.0, detections=[d1])
    assert run(AlertRuleEngine(s3)._load_event_detections(e3)) == [d1]
    assert spy3.calls == [] and s3.calls == []


@patched
def test_batch_load_detections_rounds():
    # m3-m8/m11 (junction stmt), m16 (collected ids), m19-m25 (fetch call
    # shape incl. order_by_time=False), m30/m32 (registered map-get).
    e1 = ev(id=7)
    e2 = ev(id=8)
    d1, d2 = det(id=1), det(id=2, object_type="car")
    s = FakeSession({_SQL_JUNC: [(7, 1), (7, 2)]})
    spy = BatchSpy([d1, d2])
    ae.batch_fetch_detections = spy
    engine = AlertRuleEngine(s)
    assert run(engine._batch_load_detections_for_events([e1, e2])) == {7: [d1, d2], 8: []}
    assert s.calls[-1] == (_SQL_JUNC, {"event_id_1": [7, 8]})
    assert spy.calls == [((s, [1, 2]), {"order_by_time": False})]
    before = len(s.calls)
    assert run(engine._batch_load_detections_for_events([])) == {}
    assert len(s.calls) == before  # empty input runs no query

    s2 = FakeSession({_SQL_JUNC: []})
    spy2 = BatchSpy([])
    ae.batch_fetch_detections = spy2
    assert run(AlertRuleEngine(s2)._batch_load_detections_for_events([e1])) == {7: []}
    assert spy2.calls == []

    # ids missing from the fetched rows are dropped from the mapping
    s3 = FakeSession({_SQL_JUNC: [(7, 1), (7, 99)]})
    spy3 = BatchSpy([d1])
    ae.batch_fetch_detections = spy3
    assert run(AlertRuleEngine(s3)._batch_load_detections_for_events([e1])) == {7: [d1]}
    assert spy3.calls == [((s3, [1, 99]), {"order_by_time": False})]


# ---------------------------------------------------------------- create + webhook


def alert_obj(**kw):
    base = {
        "id": 5,
        "event_id": 7,
        "rule_id": 3,
        "severity": AlertSeverity.CRITICAL,
        "status": AlertStatus.PENDING,
        "dedup_key": "dk",
        "channels": ["email"],
        "alert_metadata": {"matched_conditions": ["risk_score >= 1"], "rule_name": "n"},
    }
    base.update(kw)
    return SimpleNamespace(**base)


@patched
def test_webhook_payload_enum_round():
    # m2-m62: whole-dict payload pin, strict str types, exact call args.
    s = FakeSession()
    spy = WebhookSpy()
    ae.get_webhook_service = lambda: spy
    run(AlertRuleEngine(s)._trigger_alert_webhook(alert_obj(), ev()))
    assert len(spy.calls) == 1
    args, kwargs = spy.calls[0]
    assert len(args) == 3  # m61: dropping webhook_data shifts the call
    assert args[0] is s  # m55
    assert args[1] == WebhookEventType.ALERT_FIRED
    assert isinstance(args[2], dict)  # m57
    assert kwargs == {"event_id": 5}  # m58/m62
    data = args[2]
    assert type(data["severity"]) is str  # m11/m13/m17/m18: raw enum member
    assert type(data["status"]) is str  # m21/m23/m27/m28
    assert data == {
        "alert_id": 5,
        "event_id": 7,
        "rule_id": 3,
        "severity": "critical",
        "status": "pending",
        "dedup_key": "dk",
        "channels": ["email"],
        "matched_conditions": ["risk_score >= 1"],
        "rule_name": "n",
        "camera_id": "cam-1",
        "risk_score": 8.5,
    }


@patched
def test_webhook_str_and_absent_metadata_rounds():
    # m12/m22 (`or True`: .value on a plain str raises), m33 (channels),
    # m36-m43/m46-m50 (alert_metadata branches).
    spy = WebhookSpy()
    engine = AlertRuleEngine(FakeSession())
    ae.get_webhook_service = lambda: spy
    run(engine._trigger_alert_webhook(alert_obj(severity="high", status="pending"), ev()))
    data = spy.calls[0][0][2]
    assert data["severity"] == "high" and data["status"] == "pending"

    spy.calls.clear()
    run(engine._trigger_alert_webhook(alert_obj(alert_metadata={"rule_name": "r"}), ev()))
    data = spy.calls[0][0][2]
    assert data["matched_conditions"] == []
    assert data["rule_name"] == "r"

    # sentinel values under XX/CASE keys must NOT leak into the payload
    spy.calls.clear()
    run(
        engine._trigger_alert_webhook(
            alert_obj(alert_metadata={"XXmatched_conditionsXX": ["sentinel"], "RULE_NAME": "x"}),
            ev(),
        )
    )
    data = spy.calls[0][0][2]
    assert data["matched_conditions"] == []
    assert data["rule_name"] is None

    spy.calls.clear()
    run(engine._trigger_alert_webhook(alert_obj(alert_metadata=None), ev()))
    data = spy.calls[0][0][2]
    assert data["matched_conditions"] == []
    assert data["rule_name"] is None

    spy.calls.clear()
    run(engine._trigger_alert_webhook(alert_obj(channels=[]), ev()))
    assert spy.calls[0][0][2]["channels"] == []
    spy.calls.clear()
    run(engine._trigger_alert_webhook(alert_obj(channels=["slack", "email"]), ev()))
    assert spy.calls[0][0][2]["channels"] == ["slack", "email"]  # m33 -> []


@patched
@caplogs
def test_webhook_failure_log_round(logs):
    # m63-m70: the warning message and the extra={} alert_id/event_id attrs.
    spy = WebhookSpy(raises=RuntimeError("boom"))
    ae.get_webhook_service = lambda: spy
    run(AlertRuleEngine(FakeSession())._trigger_alert_webhook(alert_obj(), ev()))
    warns = [r for r in logs if r.levelno == logging.WARNING]
    assert len(warns) == 1
    assert warns[0].getMessage() == "Failed to trigger ALERT_FIRED webhooks: boom"
    assert warns[0].alert_id == 5 and warns[0].event_id == 7


@patched
def test_create_alerts_rounds():
    # create_alerts_for_event m22 (session.add(None)) + Alert shape +
    # one webhook per alert.
    from backend.models import Alert

    s = FakeSession()
    spy = WebhookSpy()
    ae.get_webhook_service = lambda: spy
    engine = AlertRuleEngine(s)
    r_a = rule(id=3, name="Ra", channels=["sms"])
    r_b = rule(id=4, name="Rb", channels=None)
    trigs = [
        TriggeredRule(
            rule=r_a, severity=AlertSeverity.HIGH, matched_conditions=["c1"], dedup_key="k1"
        ),
        TriggeredRule(
            rule=r_b, severity=AlertSeverity.LOW, matched_conditions=["c2"], dedup_key="k2"
        ),
    ]
    alerts = run(engine.create_alerts_for_event(ev(), trigs))
    assert len(s.added) == 2 and s.flushes == 1
    assert all(isinstance(a, Alert) and a is not None for a in s.added)  # m22
    a0, a1 = s.added
    assert (a0.event_id, a0.rule_id) == (7, 3)
    assert a0.severity == AlertSeverity.HIGH
    assert a0.status == AlertStatus.PENDING
    assert a0.dedup_key == "k1"
    assert a0.channels == ["sms"]
    assert a0.alert_metadata == {"matched_conditions": ["c1"], "rule_name": "Ra"}
    assert a1.channels == []  # rule channels None -> []
    assert (a1.rule_id, a1.dedup_key) == (4, "k2")
    assert alerts == [a0, a1]
    assert len(spy.calls) == 2
    assert [c[0][2]["rule_id"] for c in spy.calls] == [3, 4]
    assert [c[0][2]["dedup_key"] for c in spy.calls] == ["k1", "k2"]
    assert [c[0][2]["matched_conditions"] for c in spy.calls] == [["c1"], ["c2"]]
    assert [c[0][2]["rule_name"] for c in spy.calls] == ["Ra", "Rb"]


# ---------------------------------------------------------------- test_rule_against_events


@patched
def test_test_rule_against_events_rounds():
    # m2 (default clock reaches _check_schedule), m14 (detections reach
    # _evaluate_rule), m33-m36 (started_at key names + polarity).
    e1 = ev(id=7, started_at=datetime(2026, 10, 1, 12, 30, 45))
    e2 = ev(id=8, camera_id="cam-2", risk_score=2.0, started_at=None)
    d1 = det(id=1, object_type="car")
    s = FakeSession({_SQL_JUNC: [(7, 1)]})
    ae.batch_fetch_detections = BatchSpy([d1])
    engine = AlertRuleEngine(s)
    out = run(engine.test_rule_against_events(rule(id=5, object_types=["car"]), [e1, e2]))
    assert out == [
        {
            "event_id": 7,
            "camera_id": "cam-1",
            "risk_score": 8.5,
            "object_types": ["car"],
            "matches": True,
            "matched_conditions": ["object_type in ['car']"],
            "started_at": "2026-10-01T12:30:45",
        },
        {
            "event_id": 8,
            "camera_id": "cam-2",
            "risk_score": 2.0,
            "object_types": [],
            "matches": False,
            "matched_conditions": [],
            "started_at": None,
        },
    ]
    out2 = run(
        engine.test_rule_against_events(
            rule(id=6, schedule={"start_time": "00:00", "end_time": "23:59"}), [e1]
        )
    )
    assert out2[0]["matches"] is True  # m2: current_time=None crashes inside


# ---------------------------------------------------------------- source-shape self-check


def test_battery_targets_the_expected_functions():
    tree = ast.parse(_SRC)
    cls = next(
        nd for nd in tree.body if isinstance(nd, ast.ClassDef) and nd.name == "AlertRuleEngine"
    )
    have = {nd.name for nd in cls.body if isinstance(nd, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert {
        "evaluate_event",
        "_get_enabled_rules",
        "_get_aggregate_entity_trust_status",
        "_load_event_detections",
        "_batch_load_detections_for_events",
        "_evaluate_rule",
        "_check_dwell_time",
        "_check_pose_type",
        "_check_action_type",
        "_check_threat_detected",
        "_check_smoke_fire",
        "_check_schedule",
        "_build_dedup_key",
        "_check_cooldown",
        "create_alerts_for_event",
        "_trigger_alert_webhook",
        "test_rule_against_events",
    } <= have
    for text in (_SQL_TRUST, _SQL_JUNC, _SQL_DZONES, _SQL_ZONES, _SQL_DWELL, _SQL_COOLDOWN):
        assert "SELECT" in text and "\n" not in text
