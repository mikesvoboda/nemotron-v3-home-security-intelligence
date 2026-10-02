# TARGET-MODULE: backend.services.zone_anomaly_service
"""Battery S - campaign #17 of the ladder (batch-38): kill-real coverage for
``backend/services/zone_anomaly_service.py`` (290 survivors at 44.97% entering).

Harness-compatible by design (batch-30 single-process sweep): every test is a
module-level sync ``test_*()`` with no fixtures and no parametrize; coroutines
run through ``asyncio.run`` inside. The file is also collected by normal
pytest in the repo tree, so every seam swap restores in ``finally``.

Why the shipped battery leaves 290 survivors: it asserts "an anomaly was
returned" and a couple of attributes. Almost every mutation here lives in the
EXACT SHAPE of the constructed ZoneAnomaly (a dropped kwarg leaves the mapped
attribute UNSET == None, never absent, so only a per-field equality assert
sees it), in the getattr DEFAULT family (needs the key-ABSENT polarity; the
name family needs the key-PRESENT polarity - both, per getattr), in the
trailing-comma ARG-DELETION family (killable only where the callee raises on
a missing attr - getattr 1-arg raises, so the attr-absent polarity works), and
in the boundary arithmetic (``<`` vs ``<=`` needs a value EXACTLY on the
boundary). Every field of every returned anomaly is therefore asserted by
equality against a literal expected dict.

Honesty ledger - dispositions registered EQUIVALENT (the sweep must show
GREEN on exactly these unless the sweep proves otherwise; anything else GREEN
is a test gap). Each is a BODY proof, not a diff shape:

* _check_unusual_time__mutmut_41  EQUIVALENT - hourly_std default
*   [1.0]*24 -> [1.0]*25: the ONLY consumer is ``if len(hourly_std) < 24:
*   hourly_std = [1.0]*24`` (25 passes, identical) and the index
*   ``hourly_std[hour]`` with hour = timestamp.hour in 0..23 < 24 - every
*   element is 1.0 either way, so every input behaves identically.
* _check_unusual_time__mutmut_57  EQUIVALENT - ``elif std > 0`` -> ``elif std
*   >= 0``: std is ``hourly_std[hour] if hourly_std[hour] > 0 else 0.1`` - it
*   is either a value STRICTLY greater than 0 or the literal 0.1, so std is
*   never 0 and ``> 0`` / ``>= 0`` agree for every reachable value (the else
*   branch dev=0.0 is unreachable by construction).
* _check_unusual_frequency__mutmut_22/m23/m25/m29/m30/m31  EQUIVALENT (one
*   family) - the ``detection_id = getattr(detection, "id", id(detection))``
*   BINDING line with its value mutated (None / getattr(None,...) / default
*   None / XX-name / UPPER-name / id(None)): the bound value is WRITE-ONLY -
*   it is stored into the tracker tuple's ``did`` slot, which the pruning
*   comprehension reads ONLY ``ts`` (``if ts > cutoff``), the rate is
*   ``len(...)``, and the emitted anomaly's detection_id RE-READS the
*   attribute through its own getattr line (killed separately) - so no input
*   can observe any of the six values. (m28, the same line's 1-arg
*   arg-deletion, is NOT equivalent: with the ``id`` attribute absent the
*   1-arg getattr RAISES - killed by the no-id frequency polarity.)
* check_detection__mutmut_54  EQUIVALENT - INFO: 2 -> 3: the ordering among
*   {CRITICAL 0, WARNING 1, INFO 3} is identical to {0, 1, 2} and the sort
*   default 99 is unreachable (every severity IS a key) - a purely
*   order-preserving key shift.
* check_detection__mutmut_58/m60/m61  EQUIVALENT (one family) -
*   ``severity_order.get(a.severity, 99)`` -> default None / default deleted
*   (99 gone) / default 100: every element of ``anomalies`` came from one of
*   the three check methods, which build severity EXCLUSIVELY from
*   ``self._deviation_to_severity(...).value`` in {critical, warning, info} -
*   all three are dict keys, so the default arm is UNREACHABLE and all three
*   defaults are unobservable (sorting never sees it).

All other 278 survivor keys have an explicit kill polarity in this battery;
sweep result target: RED=278 GREEN=12 of 290 == this ledger exactly. If a
later sweep GREENs anything else, it is a gap - close it (or register the
EQUIV with a body proof) before the run. Delta-birth audit after run 1 is
MANDATORY per the c15 protocol: archive the module meta BEFORE launch;
delta = cur meta keys - archived keys; every birth key must be swept,
killed, or registered before run 2.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.dialects import postgresql

from backend.services.zone_anomaly_service import (
    ZoneAnomalyService,
    get_zone_anomaly_service,
    reset_zone_anomaly_service,
)

_MISSING = object()
_HOURLY_ZERO = [0.0] * 24
_HOURLY_ONE = [1.0] * 24


class _Det:
    """Detection stand-in: attributes exist ONLY when passed (a getattr
    DEFAULT family is invisible to a MagicMock, which answers everything)."""

    def __init__(self, **attrs):
        self.__dict__.update(attrs)


class _Zone:
    def __init__(self, **attrs):
        self.__dict__.update(attrs)


class _Base:
    """Baseline stand-in, same no-default-answer rule as _Det."""

    def __init__(self, **attrs):
        self.__dict__.update(attrs)


def _fields(anomaly, expected):
    """Assert EVERY expected field by equality; a dropped constructor kwarg
    leaves the mapped attribute UNSET (None), so equality is the discriminator."""
    for name, want in expected.items():
        got = getattr(anomaly, name, _MISSING)
        assert got is not _MISSING, f"field {name} missing from the model"
        assert got == want, f"{name}: got {got!r}, want {want!r}"


def _assert_uuid_string(value):
    assert isinstance(value, str), f"id must be a str uuid, got {value!r}"
    uuid.UUID(value)  # m61 (None) and m62 (str(None)) both die here


# ---------------------------------------------------------------------------
# _check_unusual_time (63 keys)
# ---------------------------------------------------------------------------


def _time_service():
    return ZoneAnomalyService()


def test_unusual_time_full_anomaly_detected_at_only():
    """expected=0.0, std=0.5 -> deviation 2.0 == threshold -> CRITICAL-free
    INFO anomaly with EVERY field pinned. Detection carries detected_at and NO
    timestamp attribute: that polarity kills the whole first-getattr family
    (name mutations answer None -> early return; the object mutations too)."""
    svc = _time_service()
    ts = datetime(2026, 1, 21, 3, 15, 0, tzinfo=UTC)
    det = _Det(detected_at=ts, id=7712, thumbnail_path="/thumb/7712.jpg")
    zone = _Zone(id="zone-abc", camera_id="cam-front", name="Front Porch")
    pattern = list(_HOURLY_ZERO)
    pattern[3] = 0.0
    base = _Base(hourly_pattern=pattern, hourly_std=[0.5] * 24)
    a = svc._check_unusual_time(det, zone, base, 2.0)
    assert a is not None, "deviation 2.0 must meet the 2.0 threshold"
    _assert_uuid_string(a.id)
    _fields(
        a,
        {
            "zone_id": "zone-abc",
            "camera_id": "cam-front",
            "anomaly_type": "unusual_time",
            "severity": "info",
            "title": "Unusual activity at 03:15",
            "description": (
                "Activity detected in Front Porch at 03:15 when typical activity is 0.0."
            ),
            "expected_value": 0.0,
            "actual_value": 1.0,
            "deviation": 2.0,
            "detection_id": 7712,
            "thumbnail_url": "/thumb/7712.jpg",
            "timestamp": ts,
        },
    )
    assert a.description.count("03:15") == 1, "strftime format must render exactly once"


def test_unusual_time_timestamp_fallback_no_detected_at():
    """detected_at ABSENT, timestamp present: the OR-fallback must be used
    (kills the 1-arg-getattr arg-deletion m7 and the second-getattr family)."""
    svc = _time_service()
    ts = datetime(2026, 5, 4, 22, 5, 0, tzinfo=UTC)
    det = _Det(timestamp=ts, id=99, thumbnail_path="/t/99")
    zone = _Zone(id="z2", camera_id="c2", name="Drive")
    base = _Base(hourly_pattern=list(_HOURLY_ZERO), hourly_std=[0.5] * 24)
    a = svc._check_unusual_time(det, zone, base, 2.0)
    assert a is not None
    _fields(
        a,
        {
            "title": "Unusual activity at 22:05",
            "description": "Activity detected in Drive at 22:05 when typical activity is 0.0.",
            "timestamp": ts,
            "detection_id": 99,
            "thumbnail_url": "/t/99",
            "deviation": 2.0,
        },
    )


def test_unusual_time_no_timestamps_returns_none_cleanly():
    """Neither timestamp attribute: orig returns None (guard arm) while every
    arg-deleted second getattr raises; also pins id/thumbnail defaults."""
    svc = _time_service()
    det = _Det()
    zone = _Zone(id="z3", camera_id="c3", name="Yard")
    base = _Base(hourly_pattern=list(_HOURLY_ZERO), hourly_std=[0.5] * 24)
    assert svc._check_unusual_time(det, zone, base, 2.0) is None


def test_unusual_time_missing_detection_id_and_thumbnail_default_none():
    """id/thumbnail_path ABSENT -> the getattr(None) defaults must be used:
    kills the getattr(None-object) family (m101/m108 answer None too - so the
    PRESENT polarity in test 1 is what kills those - while XX/UPPER name
    mutations die on the PRESENT polarity as well)."""
    svc = _time_service()
    ts = datetime(2026, 1, 21, 4, 0, 0, tzinfo=UTC)
    det = _Det(detected_at=ts)
    zone = _Zone(id="z4", camera_id="c4", name="Gate")
    base = _Base(hourly_pattern=list(_HOURLY_ZERO), hourly_std=[0.5] * 24)
    a = svc._check_unusual_time(det, zone, base, 2.0)
    assert a is not None
    _fields(a, {"detection_id": None, "thumbnail_url": None, "zone_id": "z4", "camera_id": "c4"})


def test_unusual_time_expected_activity_one_returns_none():
    """expected_activity EXACTLY 1.0 with threshold 0.0: the >= 1.0 normal-hour
    guard fires (m50's strict > would fall through and build an anomaly)."""
    svc = _time_service()
    ts = datetime(2026, 1, 21, 10, 0, 0, tzinfo=UTC)
    det = _Det(detected_at=ts, id=1)
    zone = _Zone(id="z5", camera_id="c5", name="Kitchen")
    pattern = list(_HOURLY_ONE)
    base = _Base(hourly_pattern=pattern, hourly_std=[1.0] * 24)
    assert svc._check_unusual_time(det, zone, base, 0.0) is None


def test_unusual_time_expected_above_one_short_circuits():
    """expected_activity 1.5 with threshold -5.0: the >= 1.0 guard is what
    returns None (m51's >= 2.0 would proceed to build an anomaly)."""
    svc = _time_service()
    ts = datetime(2026, 1, 21, 11, 30, 0, tzinfo=UTC)
    det = _Det(detected_at=ts, id=2)
    zone = _Zone(id="z6", camera_id="c6", name="Den")
    pattern = [1.5] * 24
    base = _Base(hourly_pattern=pattern, hourly_std=[1.0] * 24)
    assert svc._check_unusual_time(det, zone, base, -5.0) is None


def test_unusual_time_boundary_deviation_equality_and_std_branches():
    """expected=0.0, std=0.5, threshold 2.0 -> deviation EXACTLY 2.0.
    Kills m63 (dev <= threshold would drop the anomaly), m48 (std>1 would
    substitute 0.1 -> deviation 4.0) and m56 (std<1.1 would take the 4.0 arm)."""
    svc = _time_service()
    ts = datetime(2026, 1, 21, 2, 0, 0, tzinfo=UTC)
    det = _Det(detected_at=ts, id=3)
    zone = _Zone(id="z7", camera_id="c7", name="Patio")
    base = _Base(hourly_pattern=list(_HOURLY_ZERO), hourly_std=[0.5] * 24)
    a = svc._check_unusual_time(det, zone, base, 2.0)
    assert a is not None
    _fields(a, {"deviation": 2.0, "expected_value": 0.0, "actual_value": 1.0, "severity": "info"})


def test_unusual_time_std_and_expected_boundary_pairs():
    """Four boundary pairs for m53/m54/m55 and the deviation-numerator mutants
    m61/m62, each asserted by the EXACT deviation it must produce."""
    svc = _time_service()
    ts = datetime(2026, 1, 21, 1, 0, 0, tzinfo=UTC)
    det = _Det(detected_at=ts, id=4)
    zone = _Zone(id="z8", camera_id="c8", name="Back")

    def run(expected, std, threshold):
        pattern = [0.0] * 24
        pattern[1] = expected
        base = _Base(hourly_pattern=pattern, hourly_std=[std] * 24)
        return svc._check_unusual_time(det, zone, base, threshold)

    # expected EXACTLY 0.1 with std 0.05: NOT the (exp<0.1 and std<0.1) arm ->
    # dev = (1-0.1)/0.05 = 18.0 (m53's <= would take the 4.0 arm).
    _fields(run(0.1, 0.05, 2.0), {"deviation": 18.0, "expected_value": 0.1, "severity": "critical"})
    # expected 0.5 with std 0.05: m54's (exp<1.1) would take the 4.0 arm; orig
    # dev = (1-0.5)/0.05 = 10.0.
    _fields(run(0.5, 0.05, 2.0), {"deviation": 10.0, "expected_value": 0.5, "severity": "critical"})
    # std EXACTLY 0.1 with expected 0.0: m55's (std<=0.1) would take the 4.0
    # arm; orig dev = 1.0/0.1 = 10.0.
    _fields(run(0.0, 0.1, 2.0), {"deviation": 10.0, "expected_value": 0.0, "severity": "critical"})
    # numerator: expected 0.5, std 0.5, threshold 0.5 -> dev EXACTLY 1.0
    # (m61 would say (1+0.5)/0.5 = 3.0, m62 (2-0.5)/0.5 = 3.0).
    _fields(run(0.5, 0.5, 0.5), {"deviation": 1.0, "expected_value": 0.5, "severity": "info"})
    # the very-low pair: expected 0.05, std 0.05 -> dev PINNED at 4.0.
    _fields(run(0.05, 0.05, 2.0), {"deviation": 4.0, "severity": "critical"})


def test_unusual_time_short_pattern_or_missing_hourly_std():
    """hourly_pattern shorter than 24 -> guard returns None (kills the
    XX-name/UPPER hasattr mutations, which make the guard fire on a GOOD
    baseline too - see the next test for the complementary polarity)."""
    svc = _time_service()
    ts = datetime(2026, 1, 21, 3, 15, 0, tzinfo=UTC)
    det = _Det(detected_at=ts, id=5)
    zone = _Zone(id="z9", camera_id="c9", name="Short")
    base = _Base(hourly_pattern=[0.0] * 23, hourly_std=[0.5] * 24)
    assert svc._check_unusual_time(det, zone, base, 2.0) is None


def test_unusual_time_hourly_std_default_family():
    """Baseline carries hourly_pattern but NO hourly_std: the default
    [1.0]*24 must be used (dev = (1-0)/1 = 1.0 with threshold 0.5). m33/m36
    (default None / deleted) raise on len(None)/1-arg getattr; m40's [2.0]*24
    would give deviation 0.5; m24/m25's hasattr name mutations short-circuit
    the guard to None."""
    svc = _time_service()
    ts = datetime(2026, 1, 21, 3, 15, 0, tzinfo=UTC)
    det = _Det(detected_at=ts, id=6)
    zone = _Zone(id="z10", camera_id="c10", name="NoStd")
    base = _Base(hourly_pattern=list(_HOURLY_ZERO))
    a = svc._check_unusual_time(det, zone, base, 0.5)
    assert a is not None, "m24/m25 make the pattern guard fire on a valid baseline"
    _fields(a, {"deviation": 1.0, "severity": "info", "expected_value": 0.0})


# ---------------------------------------------------------------------------
# _check_unusual_frequency (62 keys)
# ---------------------------------------------------------------------------


def _freq_fill(svc, zone_id, count, now_ts, spacing_min=5):
    """Pre-load the in-memory tracker with exactly ``count`` events inside the
    last hour for the UUID-normalised zone key (the tested call appends 1 more
    only where the caller does NOT clear it first)."""
    uid = uuid.UUID(zone_id) if isinstance(zone_id, str) else zone_id
    svc._frequency_tracker[uid] = [
        (now_ts - timedelta(minutes=spacing_min * (i + 1)), 1) for i in range(count)
    ]


def test_unusual_frequency_full_anomaly_present_attrs():
    """typical 10.0/0.5 PRESENT, 12 events in the hour -> deviation 4.0
    CRITICAL with EVERY field pinned; detected_at present and NO timestamp
    attribute (kills the or->and and first-getattr family), id/thumbnail
    present (kills the getattr-object and XX/UPPER name mutants)."""
    svc = ZoneAnomalyService()
    ts = datetime(2026, 3, 9, 12, 0, 0, tzinfo=UTC)
    zone = _Zone(id=str(uuid.uuid4()), camera_id="cam-driveway", name="Driveway")
    det = _Det(detected_at=ts, id=5150, thumbnail_path="/t/f")
    # NON-default typical values: the getattr(baseline -> None, ...) object
    # mutants otherwise answer the very defaults the baseline carries.
    base = _Base(typical_crossing_rate=5.0, typical_crossing_std=0.5)
    _freq_fill(svc, zone.id, 11, ts)  # the tested call makes 12
    a = asyncio.run(svc._check_unusual_frequency(det, zone, base, 2.0))
    assert a is not None, "12 events against typical 5.0/std 0.5 is 14 sigma"
    _assert_uuid_string(a.id)
    _fields(
        a,
        {
            "zone_id": zone.id,
            "camera_id": "cam-driveway",
            "anomaly_type": "unusual_frequency",
            "severity": "critical",
            "title": "High activity frequency in Driveway",
            "description": ("Detected 12 crossings in the last hour, typical is 5.0 (std: 0.5)."),
            "expected_value": 5.0,
            "actual_value": 12.0,
            "deviation": 14.0,
            "detection_id": 5150,
            "thumbnail_url": "/t/f",
            "timestamp": ts,
        },
    )


def test_unusual_frequency_defaults_fire_at_twenty():
    """Baseline carries NO typical_* attrs: defaults 10.0/5.0 must be used.
    At EXACTLY 20 events the deviation is exactly 2.0 -> anomaly (kills the
    11.0/6.0 default mutants m49/m59 and the <= m65); the m41/m43/m46 and
    m51/m53/m56 default mutants raise on None arithmetic. This detection also
    carries NO id and NO thumbnail_path, so the trailing-comma arg-deleted
    getattrs m101/m108 RAISE (orig falls back to the None defaults)."""
    svc = ZoneAnomalyService()
    ts = datetime(2026, 3, 9, 15, 30, 0, tzinfo=UTC)
    zone = _Zone(id=str(uuid.uuid4()), camera_id="cam-back", name="Back Yard")
    det = _Det(detected_at=ts)
    base = _Base()
    _freq_fill(svc, zone.id, 19, ts, spacing_min=2)  # the tested call makes 20
    a = asyncio.run(svc._check_unusual_frequency(det, zone, base, 2.0))
    assert a is not None, "exactly 20 events must hit deviation 2.0"
    _fields(
        a,
        {
            "anomaly_type": "unusual_frequency",
            "severity": "info",
            "description": ("Detected 20 crossings in the last hour, typical is 10.0 (std: 5.0)."),
            "expected_value": 10.0,
            "actual_value": 20.0,
            "deviation": 2.0,
            "detection_id": None,
            "thumbnail_url": None,
            "timestamp": ts,
        },
    )


def test_unusual_frequency_timestamp_polarities():
    """(a) detected_at ABSENT, timestamp PRESENT -> fallback must supply the
    anomaly timestamp; a MISSING timestamp in a no-timestamps detection still
    builds the anomaly with timestamp None (no early guard here) while the
    1-arg-getattr arg-deletions raise."""
    svc = ZoneAnomalyService()
    ts = datetime(2026, 3, 9, 18, 45, 0, tzinfo=UTC)
    zone = _Zone(id=str(uuid.uuid4()), camera_id="c", name="Sidewalk")
    base = _Base(typical_crossing_rate=10.0, typical_crossing_std=0.5)
    det = _Det(timestamp=ts, id=1, thumbnail_path="/x")
    _freq_fill(svc, zone.id, 12, ts)
    a = asyncio.run(svc._check_unusual_frequency(det, zone, base, 2.0))
    assert a is not None
    _fields(a, {"timestamp": ts, "title": "High activity frequency in Sidewalk"})

    svc2 = ZoneAnomalyService()
    det2 = _Det(id=2)
    got = asyncio.run(svc2._check_unusual_frequency(det2, zone, base, 2.0))
    assert got is None, "no timestamps at all must short-circuit before the tracker"


def test_unusual_frequency_zone_uuid_normalisation():
    """zone.id as a uuid.UUID OBJECT: orig keeps it as-is; m20's ``or True``
    forces uuid.UUID(UUID-object) -> TypeError."""
    svc = ZoneAnomalyService()
    ts = datetime(2026, 3, 9, 20, 0, 0, tzinfo=UTC)
    zone = _Zone(id=uuid.uuid4(), camera_id="c", name="Object Id")
    det = _Det(detected_at=ts)
    base = _Base(typical_crossing_rate=10.0, typical_crossing_std=1.0)
    assert asyncio.run(svc._check_unusual_frequency(det, zone, base, 1.0)) is None
    # and the UUID-keyed tracker must have been populated under the object key
    assert len(svc._frequency_tracker[zone.id]) == 1


def test_unusual_frequency_cutoff_window():
    """Three cutoff polarities: events OLDER than 1h are pruned (m35 keeps
    them), a NEW hour of events survives (m33's +1h prunes everything), and
    an event EXACTLY on the cutoff boundary is dropped (m37's >= keeps it)."""
    ts = datetime(2026, 3, 9, 21, 0, 0, tzinfo=UTC)
    base = _Base(typical_crossing_rate=10.0, typical_crossing_std=1.0)

    # m33: 11 fresh events (tested call makes 12) -> orig deviation 2.0 fires;
    # +1h prunes all -> None.
    svc = ZoneAnomalyService()
    zone = _Zone(id=str(uuid.uuid4()), camera_id="c", name="Fresh")
    _freq_fill(svc, zone.id, 11, ts)
    a = asyncio.run(svc._check_unusual_frequency(_Det(detected_at=ts), zone, base, 1.0))
    assert a is not None and a.deviation == 2.0

    # m35: 3 fresh + 10 events 90 minutes old -> orig prunes the old ones
    # (rate 4, deviation -6) and returns None; the 2h window keeps 14 -> fires.
    svc2 = ZoneAnomalyService()
    zone2 = _Zone(id=str(uuid.uuid4()), camera_id="c", name="Stale")
    uid2 = uuid.UUID(zone2.id)
    svc2._frequency_tracker[uid2] = [
        (ts - timedelta(minutes=20 * (i + 1)), 1) for i in range(3)
    ] + [(ts - timedelta(minutes=90 + i), 1) for i in range(10)]
    assert (
        asyncio.run(svc2._check_unusual_frequency(_Det(detected_at=ts), zone2, base, 1.0)) is None
    )

    # m37: 9 fresh + 1 event EXACTLY at the cutoff (ts - 1h): orig drops the
    # boundary event (rate 10, deviation 0.0 -> None); >= keeps it (rate 11,
    # deviation 1.0 -> fires at threshold 1.0).
    svc3 = ZoneAnomalyService()
    zone3 = _Zone(id=str(uuid.uuid4()), camera_id="c", name="Boundary")
    uid3 = uuid.UUID(zone3.id)
    svc3._frequency_tracker[uid3] = [(ts - timedelta(minutes=3 * (i + 1)), 1) for i in range(9)] + [
        (ts - timedelta(hours=1), 1)
    ]
    assert (
        asyncio.run(svc3._check_unusual_frequency(_Det(detected_at=ts), zone3, base, 1.0)) is None
    )


def test_unusual_frequency_second_call_survives_append():
    """m38 appends None instead of the (timestamp, id) tuple: it only shows
    up when a SECOND call unpacks the tracker list during pruning."""
    svc = ZoneAnomalyService()
    ts = datetime(2026, 3, 9, 22, 0, 0, tzinfo=UTC)
    zone = _Zone(id=str(uuid.uuid4()), camera_id="c", name="Twice")
    base = _Base(typical_crossing_rate=10.0, typical_crossing_std=1.0)
    assert asyncio.run(svc._check_unusual_frequency(_Det(detected_at=ts), zone, base, 1.0)) is None
    assert (
        asyncio.run(
            svc._check_unusual_frequency(
                _Det(detected_at=ts + timedelta(minutes=1)), zone, base, 1.0
            )
        )
        is None
    )
    assert len(svc._frequency_tracker[uuid.UUID(zone.id)]) == 2


def test_unusual_frequency_std_clamp_boundaries():
    """typical_crossing_std EXACTLY 0.0 -> clamp to 1.0 keeps deviation 2.0
    (m60's < 0 divides by zero); std 0.5 stays 0.5 -> deviation 4.0 (m61's
    <= 1 clamps it to 1.0 -> deviation 2.0)."""
    ts = datetime(2026, 3, 9, 23, 0, 0, tzinfo=UTC)

    svc = ZoneAnomalyService()
    zone = _Zone(id=str(uuid.uuid4()), camera_id="c", name="ZeroStd")
    _freq_fill(svc, zone.id, 11, ts)  # the tested call makes 12
    base0 = _Base(typical_crossing_rate=10.0, typical_crossing_std=0.0)
    a = asyncio.run(svc._check_unusual_frequency(_Det(detected_at=ts), zone, base0, 2.0))
    assert a is not None, "std 0.0 must clamp to 1.0, not divide by zero"
    _fields(
        a,
        {
            "deviation": 2.0,
            "severity": "info",
            "description": ("Detected 12 crossings in the last hour, typical is 10.0 (std: 1.0)."),
        },
    )

    svc2 = ZoneAnomalyService()
    zone2 = _Zone(id=str(uuid.uuid4()), camera_id="c", name="HalfStd")
    _freq_fill(svc2, zone2.id, 11, ts)  # the tested call makes 12
    base5 = _Base(typical_crossing_rate=10.0, typical_crossing_std=0.5)
    b = asyncio.run(svc2._check_unusual_frequency(_Det(detected_at=ts), zone2, base5, 2.0))
    assert b is not None
    _fields(b, {"deviation": 4.0, "severity": "critical"})


# ---------------------------------------------------------------------------
# _check_unusual_dwell (58 keys)
# ---------------------------------------------------------------------------


def test_unusual_dwell_full_anomaly_present_attrs():
    """typical_dwell/std PRESENT non-default, enrichment dict with dwell_time,
    detected_at present: EVERY field pinned (kills the constructor None/remove
    families, the getattr-object mutants of every line, and the name mutants
    of every PRESENT attribute)."""
    svc = ZoneAnomalyService()
    ts = datetime(2026, 4, 2, 9, 45, 0, tzinfo=UTC)
    det = _Det(enrichment_data={"dwell_time": 90.0}, detected_at=ts, id=8801, thumbnail_path="/t/d")
    zone = _Zone(id="zone-d", camera_id="cam-d", name="Patio")
    # NON-default typicals: the getattr(baseline -> None, ...) object mutants
    # otherwise answer the very defaults the baseline carries (30.0/10.0).
    base = _Base(typical_dwell_time=20.0, typical_dwell_std=5.0)
    a = asyncio.run(svc._check_unusual_dwell(det, zone, base, 2.0))
    assert a is not None, "deviation 14.0 must fire"
    _assert_uuid_string(a.id)
    _fields(
        a,
        {
            "zone_id": "zone-d",
            "camera_id": "cam-d",
            "anomaly_type": "unusual_dwell",
            "severity": "critical",
            "title": "Extended presence in Patio",
            "description": "Entity lingered for 90s, typical is 20s (std: 5.0s).",
            "expected_value": 20.0,
            "actual_value": 90.0,
            "deviation": 14.0,
            "detection_id": 8801,
            "thumbnail_url": "/t/d",
            "timestamp": ts,
        },
    )


def test_unusual_dwell_defaults_and_no_timestamps():
    """Baseline carries NO typical_* attrs (defaults 30.0/10.0 must be used).
    Dwell has NO timestamp guard, so with NEITHER timestamp attribute the orig
    still builds the anomaly (timestamp None) - while the 1-arg arg-deleted
    getattrs m23 (detected_at) / m30 (timestamp) RAISE on the absent attrs.
    The XX/UPPER name mutants (m24/m25/m31/m32) fall through to the same None
    default and stay GREEN on this polarity - they are killed by the PRESENT
    detected_at timestamp pin in test_unusual_dwell_full_anomaly_present_attrs."""
    svc = ZoneAnomalyService()
    det = _Det(enrichment_data={"dwell_time": 50.0})
    zone = _Zone(id="zone-e", camera_id="cam-e", name="Lobby")
    base = _Base()
    a0 = asyncio.run(svc._check_unusual_dwell(det, zone, base, 2.0))
    assert a0 is not None and a0.timestamp is None, "no timestamp guard in dwell"
    _fields(a0, {"expected_value": 30.0, "deviation": 2.0, "severity": "info"})

    # the DEFAULTS consumed with the detection carrying only a timestamp attr:
    # pins expected 30.0 / deviation 2.0 (kills the 31.0/11.0 default mutants
    # and the deleted/None-default ones m36/m39/m46/m49).
    ts = datetime(2026, 4, 2, 10, 0, 0, tzinfo=UTC)
    det2 = _Det(enrichment_data={"dwell_time": 50.0}, timestamp=ts)
    a = asyncio.run(svc._check_unusual_dwell(det2, zone, base, 2.0))
    assert a is not None
    _fields(
        a,
        {
            "expected_value": 30.0,
            "deviation": 2.0,
            "severity": "info",
            "description": "Entity lingered for 50s, typical is 30s (std: 10.0s).",
            "timestamp": ts,
            "detection_id": None,
            "thumbnail_url": None,
        },
    )


def test_unusual_dwell_enrichment_polarities():
    """(a) enrichment present but NOT a dict (kills m9's and->or: the orig
    guard returns None); (b) dwell_time ABSENT from the dict (m24's name
    mutants die on the PRESENT polarity of the same key); (c) no enrichment
    attribute at all."""
    svc = ZoneAnomalyService()
    zone = _Zone(id="zone-f", camera_id="cam-f", name="Dock")
    base = _Base(typical_dwell_time=30.0, typical_dwell_std=10.0)

    assert (
        asyncio.run(svc._check_unusual_dwell(_Det(enrichment_data="nope"), zone, base, 2.0)) is None
    )
    assert asyncio.run(svc._check_unusual_dwell(_Det(enrichment_data={}), zone, base, 2.0)) is None
    assert asyncio.run(svc._check_unusual_dwell(_Det(), zone, base, 2.0)) is None

    ts = datetime(2026, 4, 2, 11, 0, 0, tzinfo=UTC)
    a = asyncio.run(
        svc._check_unusual_dwell(
            _Det(enrichment_data={"dwell_time": 70.0}, detected_at=ts), zone, base, 2.0
        )
    )
    assert a is not None
    _fields(a, {"deviation": 4.0, "actual_value": 70.0, "severity": "critical"})


def test_unusual_dwell_std_and_threshold_boundaries():
    """std EXACTLY 0.0 clamps to 1.0 (m53's < 0 divides by zero); std EXACTLY
    1.0 must NOT clamp (m54's <= 1 clamps -> deviation 2.0); deviation EXACTLY
    2.0 fires (m56's * -> 0.5, m58's <= would drop it)."""
    ts = datetime(2026, 4, 2, 12, 0, 0, tzinfo=UTC)
    zone = _Zone(id="zone-g", camera_id="cam-g", name="Steps")

    svc = ZoneAnomalyService()
    det0 = _Det(enrichment_data={"dwell_time": 32.0}, detected_at=ts)
    a = asyncio.run(
        svc._check_unusual_dwell(
            det0, zone, _Base(typical_dwell_time=30.0, typical_dwell_std=0.0), 2.0
        )
    )
    assert a is not None, "std 0.0 must clamp to 1.0"
    _fields(
        a,
        {
            "deviation": 2.0,
            "expected_value": 30.0,
            "actual_value": 32.0,
            "description": "Entity lingered for 32s, typical is 30s (std: 1.0s).",
        },
    )

    svc2 = ZoneAnomalyService()
    det1 = _Det(enrichment_data={"dwell_time": 32.0}, detected_at=ts)
    b = asyncio.run(
        svc2._check_unusual_dwell(
            det1, zone, _Base(typical_dwell_time=30.0, typical_dwell_std=1.0), 2.0
        )
    )
    assert b is not None, "std 1.0 is a real std, not a clamp trigger"
    _fields(b, {"deviation": 2.0})

    svc3 = ZoneAnomalyService()
    detH = _Det(enrichment_data={"dwell_time": 31.0}, detected_at=ts)
    c = asyncio.run(
        svc3._check_unusual_dwell(
            detH, zone, _Base(typical_dwell_time=30.0, typical_dwell_std=0.5), 2.0
        )
    )
    assert c is not None, "deviation EXACTLY 2.0 must fire (orig uses <)"
    _fields(
        c, {"deviation": 2.0, "description": "Entity lingered for 31s, typical is 30s (std: 0.5s)."}
    )


# ---------------------------------------------------------------------------
# _emit_websocket_event (31 keys) + _persist_and_emit (1 key)
# ---------------------------------------------------------------------------


def _globals_of(fn):
    f = fn
    while hasattr(f, "__wrapped__"):
        f = f.__wrapped__
    return f.__globals__


_G = _globals_of(ZoneAnomalyService.check_detection)


class _PubSpy:
    def __init__(self, raise_msg=None):
        self.published = []
        self._raise = raise_msg

    async def publish(self, channel, message):
        if self._raise is not None:
            raise RuntimeError(self._raise)
        self.published.append((channel, message))
        return 1


class _LogCap:
    """Records (level, msg) pairs; installed as the module logger."""

    def __init__(self):
        self.calls = []

    def _rec(self, level):
        def _f(msg, *args, **kwargs):
            self.calls.append((level, msg))

        return _f

    def __getattr__(self, name):
        return self._rec(name)

    def names(self):
        return list(self.calls)


def _swap(key, value):
    old = _G[key]

    def restore():
        _G[key] = old

    _G[key] = value
    return restore


class _EmitAnomaly:
    """Stand-in carrying every field the payload reads."""

    def __init__(self, **attrs):
        self.__dict__.update(attrs)


def _full_emit_anomaly():
    return _EmitAnomaly(
        id="8b1a2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
        zone_id="z-emit",
        camera_id="cam-emit",
        anomaly_type="unusual_time",
        severity="warning",
        title="Emit Title",
        description="Emit Description",
        expected_value=1.5,
        actual_value=2.5,
        deviation=3.5,
        detection_id=42,
        thumbnail_url="/thumbnail/x",
        timestamp=datetime(2026, 6, 1, 8, 30, 0, tzinfo=UTC),
    )


def _full_emit_payload(anomaly):
    return {
        "type": "zone.anomaly",
        "data": {
            "id": anomaly.id,
            "zone_id": anomaly.zone_id,
            "camera_id": anomaly.camera_id,
            "anomaly_type": anomaly.anomaly_type,
            "severity": anomaly.severity,
            "title": anomaly.title,
            "description": anomaly.description,
            "expected_value": anomaly.expected_value,
            "actual_value": anomaly.actual_value,
            "deviation": anomaly.deviation,
            "detection_id": anomaly.detection_id,
            "thumbnail_url": anomaly.thumbnail_url,
            "timestamp": (anomaly.timestamp.isoformat() if anomaly.timestamp else None),
        },
    }


def test_emit_event_full_payload_custom_channel():
    """Redis set + settings WITH redis_event_channel: the exact payload dict
    and channel are pinned (kills every payload KEY mutation - a renamed key
    makes the dict unequal - the str(None) value mutants m26/m29, and the
    channel name mutants via the PRESENT-attribute polarity)."""
    svc = ZoneAnomalyService(redis_client=_PubSpy())
    anomaly = _full_emit_anomaly()
    restores = [_swap("get_settings", lambda: _Zone(redis_event_channel="custom:chan"))]
    try:
        asyncio.run(svc._emit_websocket_event(anomaly))
    finally:
        for r in restores:
            r()
    assert svc._redis.published == [("custom:chan", _full_emit_payload(anomaly))]


def test_emit_event_default_channel_via_get_redis():
    """_redis None -> the anext(get_redis()) path must supply the client;
    settings WITHOUT the channel attr -> the "hsi:events" default is used
    (kills the deleted/None defaults m12/m9 and the XX/UPPER channel
    mutants; the getattr-object mutant is killed by the custom-channel test
    where reading None would fall to the default "hsi:events")."""
    fake_redis = _PubSpy()

    async def _fake_get_redis():
        yield fake_redis

    anomaly = _full_emit_anomaly()
    restores = [
        _swap("get_redis", _fake_get_redis),
        _swap("get_settings", lambda: _Zone()),
    ]
    try:
        asyncio.run(ZoneAnomalyService()._emit_websocket_event(anomaly))
    finally:
        for r in restores:
            r()
    assert fake_redis.published == [("hsi:events", _full_emit_payload(anomaly))]


def test_emit_event_publish_failure_logs_exact_warning():
    """publish raises -> the EXACT warning record is pinned, m59-style
    (logger.warning(None) breaks the message equality) and nothing published."""
    svc = ZoneAnomalyService(redis_client=_PubSpy(raise_msg="kaboom"))
    cap = _LogCap()
    restores = [
        _swap("logger", cap),
        _swap("get_settings", lambda: _Zone(redis_event_channel="chan-w")),
    ]
    try:
        asyncio.run(svc._emit_websocket_event(_full_emit_anomaly()))
    finally:
        for r in restores:
            r()
    assert svc._redis.published == []
    assert cap.names() == [("warning", "Failed to emit WebSocket event for anomaly: kaboom")]


def test_emit_event_none_timestamp_payload_and_andor():
    """anomaly.timestamp None: the payload carries timestamp None (m53's
    ``or True`` would call None.isoformat() -> AttributeError -> the except
    swallows it and NOTHING is published - the pin below fails); m52's
    ``and False`` always takes the None arm - killed by the PRESENT-timestamp
    pin in the custom-channel test."""
    svc = ZoneAnomalyService(redis_client=_PubSpy())
    anomaly = _full_emit_anomaly()
    anomaly.timestamp = None
    restores = [_swap("get_settings", lambda: _Zone(redis_event_channel="chan-t"))]
    try:
        asyncio.run(svc._emit_websocket_event(anomaly))
    finally:
        for r in restores:
            r()
    expected = _full_emit_payload(anomaly)
    expected["data"]["timestamp"] = None
    assert svc._redis.published == [("chan-t", expected)]


class _AddSpy:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


def test_persist_and_emit_forwards_the_anomaly():
    """session given -> session.add + EXACT emit forward (m4's None-arg
    breaks identity); session None -> the get_session() context path adds and
    commits (the module-global seam is swapped, never the real DB)."""
    anomaly = _EmitAnomaly(id="pa-1")
    seen = []

    async def _emit_spy(a):
        seen.append(a)

    async def _emit_spy2(a):
        seen.append(a)

    svc = ZoneAnomalyService()
    orig_emit = svc._emit_websocket_event
    svc._emit_websocket_event = _emit_spy
    session = _AddSpy()
    try:
        asyncio.run(svc._persist_and_emit(anomaly, session=session))
    finally:
        svc._emit_websocket_event = orig_emit
    assert session.added == [anomaly] and session.commits == 0
    assert seen == [anomaly], "_persist_and_emit must forward the anomaly itself"

    class _Ctx:
        def __init__(self, sess):
            self.sess = sess

        async def __aenter__(self):
            return self.sess

        async def __aexit__(self, *exc):
            return False

    fresh = _AddSpy()
    svc2 = ZoneAnomalyService()
    orig_emit2 = svc2._emit_websocket_event
    svc2._emit_websocket_event = _emit_spy2
    restores = [_swap("get_session", lambda: _Ctx(fresh))]
    try:
        asyncio.run(svc2._persist_and_emit(anomaly))
    finally:
        svc2._emit_websocket_event = orig_emit2
        for r in restores:
            r()
    assert fresh.added == [anomaly] and fresh.commits == 1
    assert seen == [anomaly, anomaly]


# ---------------------------------------------------------------------------
# check_detection (39 keys) — orchestration, guards, severity ordering
# ---------------------------------------------------------------------------


class _BaseSvcSpy:
    """Stands in for svc._baseline_service; PINS both call-site args (the
    get_baseline(None, ...) / session-dropping mutants fail the pin)."""

    def __init__(self, baseline, want_zone_id, want_session):
        self.baseline = baseline
        self.want_zone_id = want_zone_id
        self.want_session = want_session

    async def get_baseline(self, zone_id, session=None):
        assert zone_id == self.want_zone_id, f"zone_id {zone_id!r} was forwarded"
        assert session is self.want_session, f"session {session!r} was forwarded"
        return self.baseline


class _SevAnom:
    def __init__(self, severity, tag):
        self.severity = severity
        self.tag = tag


class _CheckSpy:
    """Pins the exact positional args of a _check_unusual_* call site."""

    def __init__(self, ret, want_args):
        self.ret = ret
        self.want_args = want_args

    def _pin(self, args):
        assert args == self.want_args, f"args {args!r} != {self.want_args!r}"
        return self.ret

    def sync_call(self, *args):
        return self._pin(args)

    async def async_call(self, *args):
        return self._pin(args)


class _PersistSpy:
    def __init__(self):
        self.calls = []

    async def __call__(self, anomaly, session=None):
        self.calls.append((anomaly, session))


def _orchestrated(svc, det, zone, base, sess, threshold, t_ret, f_ret, d_ret):
    """Install arg-pinned spies over the three checks + persist; return
    (persist-spy, time-spy, freq-spy, dwell-spy)."""
    svc._baseline_service = _BaseSvcSpy(base, zone.id, sess)
    st = _CheckSpy(t_ret, (det, zone, base, threshold))
    sf = _CheckSpy(f_ret, (det, zone, base, threshold))
    sd = _CheckSpy(d_ret, (det, zone, base, threshold))
    svc._check_unusual_time = st.sync_call
    svc._check_unusual_frequency = sf.async_call
    svc._check_unusual_dwell = sd.async_call
    ps = _PersistSpy()
    svc._persist_and_emit = ps
    return ps


def test_check_detection_single_time_anomaly():
    """Only the time check fires: it must be returned AND persisted with the
    exact session kwarg. The three spies pin (detection, zone, baseline,
    threshold=5.0) - a positional shift, an arg None-out, or the threshold
    drop fails them; m21 (time call removed) returns None."""
    svc = ZoneAnomalyService()
    det = _Det()
    zone = _Zone(id="zc", camera_id="cc", name="C")
    sess = object()
    base = _Base(sample_count=7)
    T = _SevAnom("info", "T")
    ps = _orchestrated(svc, det, zone, base, sess, 5.0, T, None, None)
    out = asyncio.run(svc.check_detection(det, zone, session=sess, threshold=5.0))
    assert out is T, f"time anomaly must be the result, got {out!r}"
    assert ps.calls == [(T, sess)]


def test_check_detection_single_freq_and_dwell_anomalies():
    """Mirror of the time-only test for the two async call sites: m31/m40
    (call removed) make the result None; their arg mutants fail the pins."""
    svc = ZoneAnomalyService()
    det = _Det()
    zone = _Zone(id="zf", camera_id="cf", name="F")
    sess = object()
    base = _Base(sample_count=7)
    F = _SevAnom("warning", "F")
    ps = _orchestrated(svc, det, zone, base, sess, 5.0, None, F, None)
    out = asyncio.run(svc.check_detection(det, zone, session=sess, threshold=5.0))
    assert out is F, f"freq anomaly must be the result, got {out!r}"
    assert ps.calls == [(F, sess)]

    svc2 = ZoneAnomalyService()
    D = _SevAnom("critical", "D")
    ps2 = _orchestrated(svc2, det, zone, base, sess, 5.0, None, None, D)
    out2 = asyncio.run(svc2.check_detection(det, zone, session=sess, threshold=5.0))
    assert out2 is D, f"dwell anomaly must be the result, got {out2!r}"
    assert ps2.calls == [(D, sess)]


def test_check_detection_severity_ordering():
    """Two pairs of anomalies decide the severity_order dict:
    (a) WARNING(time) + CRITICAL(dwell) -> dwell wins: m52 (CRITICAL 0->1)
        ties the keys and stable sort keeps insertion order; m57 (key None ->
        every element 99) and m63 (anomalies[1]) also return the time one.
    (b) INFO(time) + WARNING(dwell) -> dwell wins: under m57 every element
        keys to 99 and stable sort keeps the time anomaly first; m63 again
        picks the wrong element. (m54 INFO 2->3 is the ledger EQUIV - an
        order-preserving shift these pairs cannot separate.)"""
    sess = object()
    det = _Det()
    zone = _Zone(id="zs", camera_id="cs", name="S")
    base = _Base(sample_count=7)

    svc = ZoneAnomalyService()
    T = _SevAnom("warning", "T")
    D = _SevAnom("critical", "D")
    ps = _orchestrated(svc, det, zone, base, sess, 5.0, T, None, D)
    out = asyncio.run(svc.check_detection(det, zone, session=sess, threshold=5.0))
    assert out is D, "CRITICAL must outrank WARNING"
    assert ps.calls == [(D, sess)]

    svc2 = ZoneAnomalyService()
    T2 = _SevAnom("info", "T2")
    D2 = _SevAnom("warning", "D2")
    ps2 = _orchestrated(svc2, det, zone, base, sess, 5.0, T2, None, D2)
    out2 = asyncio.run(svc2.check_detection(det, zone, session=sess, threshold=5.0))
    assert out2 is D2, "WARNING must outrank INFO"
    assert ps2.calls == [(D2, sess)]


def test_check_detection_baseline_guards():
    """baseline None -> None; a baseline WITHOUT sample_count must be treated
    as 0 and short-circuit (m11's None-default and m17's 1-default proceed to
    a full anomaly; m14's 1-arg getattr raises). Spies would return T if the
    guard is skipped."""
    sess = object()
    det = _Det()
    zone = _Zone(id="zg", camera_id="cg", name="G")
    T = _SevAnom("info", "T")

    svc = ZoneAnomalyService()
    ps = _orchestrated(svc, det, zone, None, sess, 3.0, T, None, None)
    assert asyncio.run(svc.check_detection(det, zone, session=sess, threshold=3.0)) is None
    assert ps.calls == []

    base = _Base()  # NO sample_count attribute
    svc2 = ZoneAnomalyService()
    ps2 = _orchestrated(svc2, det, zone, base, sess, 3.0, T, None, None)
    out = asyncio.run(svc2.check_detection(det, zone, session=sess, threshold=3.0))
    assert out is None, "missing sample_count means 0 samples - no anomaly"
    assert ps2.calls == []

    base0 = _Base(sample_count=0)
    svc3 = ZoneAnomalyService()
    ps3 = _orchestrated(svc3, det, zone, base0, sess, 3.0, T, None, None)
    assert asyncio.run(svc3.check_detection(det, zone, session=sess, threshold=3.0)) is None
    assert ps3.calls == []


# ---------------------------------------------------------------------------
# SQL query families: get_anomalies_for_zone (12) / acknowledge_anomaly (6) /
# get_anomaly_counts_by_zone (17)
# ---------------------------------------------------------------------------


def _sql(query):
    return str(query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


class _Result:
    def __init__(self, rows=None, one=_MISSING):
        self._rows = rows or []
        self._one = one

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def scalar_one_or_none(self):
        return None if self._one is _MISSING else self._one


class _Sess:
    def __init__(self, result):
        self.executed = []
        self.commits = 0
        self._result = result

    async def execute(self, query):
        self.executed.append(query)
        return self._result

    async def commit(self):
        self.commits += 1


class _Ack:
    def __init__(self):
        self.calls = []

    def acknowledge(self, acknowledged_by=None):
        self.calls.append(acknowledged_by)


def test_get_anomalies_for_zone_exact_sql():
    """All four clauses pinned in the compiled postgres text: the == 'z-1'
    (no !=), timestamp >= '<literal>', acknowledged = false (not true, not
    !=), and ORDER BY ... DESC. query/order_by/execute-None mutants blow up
    the compile; order_by(None) (a SQLA clause RESET idiom) drops the clause."""
    svc = ZoneAnomalyService()
    since = datetime(2026, 5, 5, tzinfo=UTC)
    row_a, row_b = object(), object()
    sess = _Sess(_Result(rows=[row_a, row_b]))
    out = asyncio.run(
        svc.get_anomalies_for_zone("z-1", since=since, unacknowledged_only=True, session=sess)
    )
    assert out == [row_a, row_b]
    assert len(sess.executed) == 1
    s = _sql(sess.executed[0])
    # m3's select(None) keeps the WHERE clause but renders "SELECT NULL AS
    # anon_1" - the entity column list is what proves select(ZoneAnomaly).
    assert "SELECT zone_anomalies.id, zone_anomalies.zone_id," in s, s
    assert "SELECT NULL" not in s, s
    assert "WHERE zone_anomalies.zone_id = 'z-1'" in s, s
    assert "!=" not in s, s
    assert "zone_anomalies.timestamp >= '" in s, s
    assert "zone_anomalies.acknowledged = false" in s, s
    assert "zone_anomalies.acknowledged = true" not in s, s
    assert "ORDER BY zone_anomalies.timestamp DESC" in s, s


def test_acknowledge_anomaly_exact_sql_and_flow():
    """Found path: WHERE id = '9' (no !=, not 'None'), anomaly.acknowledge
    receives the user, exactly one commit, the anomaly is returned."""
    svc = ZoneAnomalyService()
    acked = _Ack()
    sess = _Sess(_Result(one=acked))
    out = asyncio.run(svc.acknowledge_anomaly(9, "user-7", session=sess))
    assert out is acked
    assert acked.calls == ["user-7"]
    assert sess.commits == 1
    s = _sql(sess.executed[0])
    # m4's select(None) keeps the WHERE but loses the entity column list.
    assert "SELECT zone_anomalies.id, zone_anomalies.zone_id," in s, s
    assert "SELECT NULL" not in s, s
    assert "WHERE zone_anomalies.id = '9'" in s, s
    assert "!=" not in s, s


def test_acknowledge_anomaly_not_found_returns_none():
    """scalar_one_or_none -> None: no acknowledge, no commit, None back (the
    guard arm; keeps the found-path pins honest)."""
    svc = ZoneAnomalyService()
    sess = _Sess(_Result())
    assert asyncio.run(svc.acknowledge_anomaly("abc", session=sess)) is None
    assert sess.commits == 0


def test_get_anomaly_counts_by_zone_exact_sql():
    """SELECT zone_anomalies.zone_id, count(zone_anomalies.id) AS count ...
    GROUP BY zone_anomalies.zone_id and the {str: int} mapping."""
    svc = ZoneAnomalyService()
    sess = _Sess(_Result(rows=[("z-a", 3), ("z-b", 4)]))
    out = asyncio.run(svc.get_anomaly_counts_by_zone(session=sess))
    assert out == {"z-a": 3, "z-b": 4}
    s = _sql(sess.executed[0])
    assert "SELECT zone_anomalies.zone_id" in s, s
    assert "SELECT NULL" not in s, s  # m2's select(None, ...)
    assert "count(zone_anomalies.id)" in s, s
    # label(None) renders the anonymous "count_1"; "AS count" is a substring
    # of it, so the ABSENCE of the anonymous name is the exact-label proof.
    assert "AS count" in s, s
    assert "count_1" not in s, s
    assert "GROUP BY zone_anomalies.zone_id" in s, s


def test_get_anomaly_counts_filters_and_raise():
    """Filter polarity (since >=, acknowledged = false) and the EXACT
    ValueError message when session is None (m22's XX-wrapped message
    contains the old one, so assert EQUALITY)."""
    svc = ZoneAnomalyService()
    since = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)
    sess = _Sess(_Result(rows=[]))
    assert (
        asyncio.run(
            svc.get_anomaly_counts_by_zone(since=since, unacknowledged_only=True, session=sess)
        )
        == {}
    )
    s = _sql(sess.executed[0])
    assert "zone_anomalies.timestamp >= '" in s, s
    assert "zone_anomalies.acknowledged = false" in s, s
    assert "!=" not in s, s

    try:
        asyncio.run(svc.get_anomaly_counts_by_zone())
    except ValueError as exc:
        assert str(exc) == "session is required", f"got {str(exc)!r}"
    else:
        raise AssertionError("ValueError expected when session is None")


# ---------------------------------------------------------------------------
# module singleton
# ---------------------------------------------------------------------------


def test_reset_singleton_creates_fresh_instance():
    """reset assigns "" (m1) instead of None: get_zone_anomaly_service() then
    returns the "" falsy-but-not-None global instead of building a service."""
    reset_zone_anomaly_service()
    first = get_zone_anomaly_service()
    assert isinstance(first, ZoneAnomalyService)
    assert get_zone_anomaly_service() is first, "singleton must be stable"
    reset_zone_anomaly_service()
    after = get_zone_anomaly_service()
    assert isinstance(after, ZoneAnomalyService), "reset must clear the global to None"
    assert after is not first
    reset_zone_anomaly_service()
