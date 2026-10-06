# TARGET-MODULE: backend.services.context_enricher
"""Battery AJ - campaign #34 kill battery for backend/services/context_enricher.py.

Covers the 153 keys the CURRENT shipped suite (test_context_enricher.py, 76 tests)
still leaves GREEN out of the 216 the bank records as survivors; the other 63 bank
"survivors" are already killed by today's suite (stale-era verdicts) and are NOT
re-authored here.

Killing machinery, by family:
  * a statement-signature session fake - every execute() is pinned by its compiled
    Postgres text, so all 48 SQL-shape mutants (select(None), where(None, x),
    dropped clause, == <-> !=, True <-> False, order_by(None)) change the signature.
  * exact-value rows for the deviation arithmetic (ratio/clamp/threshold/boost).
  * positional + kwarg-exact spies for the is_anomalous / format_class_anomaly /
    _get_* delegate call shapes.
  * non-empty-fixture drop-vs-None rows for the dataclass kwargs.
  * exact-string equality for every format_* literal, join and offset threshold.

HONESTY LEDGER (registered equivalents - each PROVEN by construction probe, see
/home/agent/runs/b38-c34-equiv-probe.py, not inferred from diff shape):
  * enrich__mutmut_15                      detections = [] -> None: the falsy branch
        returns immediately and never reads the value.
  * enrich__mutmut_70                      dropping recent_events=[] falls back to the
        dataclass default_factory which is also [] (value-equal).
  * _get_baseline_context__mutmut_19/34/35 total_expected is write-only (AST over the
        function: two Stores, zero Loads) - its value is never observed.
  * _get_baseline_context__mutmut_68       `ratio > 1` -> `ratio >= 1` differs only at
        ratio == 1 where both branches evaluate to 0.0.
  * _get_baseline_context__mutmut_84       clamp min(1.0 -> 2.0): the reachable
        pre-clamp range is (0, 1) for every ratio > 0, so the bound never binds.
  * _get_cross_camera_activity__mutmut_48  `if time_offsets` -> `if time_offsets or
        True`: the empty case is sum([])/len(dets) = 0.0, identical to the 0.0 fallback.
  * format_cross_camera_summary__mutmut_20/21  direction polarity flips only differ for
        -1 < offset <= 0, and the enclosing `abs(offset) > 60` guard excludes those.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.dialects import postgresql

from backend.models.camera_zone import CameraZoneType
from backend.services.context_enricher import (
    BaselineContext,
    ContextEnricher,
    CrossCameraActivity,
    ZoneContext,
)
from backend.services.context_enricher import logger as _MODULE_LOGGER
from backend.services.prompts import ClassAnomalyResult

MOD = "backend.services.context_enricher"
CAM = "cam-a"
T0 = datetime(2025, 6, 2, 10, 0, tzinfo=UTC)  # Monday, hour 10, weekday 0


def run(coro):
    return asyncio.run(coro)


def sig(stmt):
    """Compiled Postgres text, whitespace-normalised, operators spaced."""
    s = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    s = "".join(s.split())
    for a, b in [
        ("(", " ( "),
        (")", " ) "),
        ("<", " < "),
        (">", " > "),
        ("=", " = "),
        ("!", " ! "),
    ]:
        s = s.replace(a, b)
    return " ".join(s.split())


# --------------------------------------------------------------------------- fixtures
class Res:
    """One execute() result: scalars().all() and scalar_one_or_none() both served."""

    def __init__(self, rows=None, one=None):
        self._rows = rows or []
        self._one = one

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def scalar_one_or_none(self):
        return self._one


class Session:
    """Recording session fake: pins the statement signature of every execute()."""

    def __init__(self, results):
        self.results = list(results)
        self.sigs = []

    async def execute(self, stmt):
        self.sigs.append(sig(stmt))
        if self.results:
            return self.results.pop(0)
        return Res()


class OffMap:
    """A zone_type that is NOT a key of ZONE_RISK_WEIGHTS, so the .get default runs."""

    value = "rooftop"


NO_TIME = object()  # explicit sentinel: det(..., at=NO_TIME) means detected_at=None


def det(i, obj="person", at=T0, x=100, y=100, w=100, h=100, cam=CAM):
    return SimpleNamespace(
        id=i,
        object_type=obj,
        detected_at=None if at is NO_TIME else at,
        bbox_x=x,
        bbox_y=y,
        bbox_width=w,
        bbox_height=h,
        camera_id=cam,
    )


def zone(
    zid,
    name="Z",
    ztype=None,
    enabled=True,
    coords=((0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)),
    priority=1,
):
    return SimpleNamespace(
        id=zid,
        name=name,
        zone_type=ztype if ztype is not None else OffMap(),
        enabled=enabled,
        coordinates=list(coords),
        priority=priority,
    )


class Spy:
    """Async recorder standing in for BaselineService.is_anomalous."""

    def __init__(self, result=(False, 0.0)):
        self.result = result
        self.calls = []

    async def is_anomalous(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


def enricher(result=(False, 0.0)):
    """ContextEnricher whose baseline-service dependency is a recorder."""
    with patch(f"{MOD}.get_baseline_service", lambda: SimpleNamespace()):
        e = ContextEnricher(cross_camera_window=300, image_width=1920, image_height=1080)
    e._baseline_service = Spy(result)
    return e


class LogRec(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


class caplogger:
    """Swaps a fresh logger into the module and captures every message."""

    def __enter__(self):
        self.log = logging.Logger("aj-probe")
        self.log.setLevel(logging.DEBUG)
        self.log.propagate = False
        self.h = LogRec()
        self.log.addHandler(self.h)
        self.saved = _MODULE_LOGGER
        import backend.services.context_enricher as m

        self.mod = m
        m.logger = self.log
        return self.h

    def __exit__(self, *_exc):
        self.mod.logger = self.saved
        return False


# ------------------------------------------------------------------ SQL statement shape
# Every mutant that rewrites one of these five statements -- select(<cls>) -> select(None)
# (SELECT NULL AS anon_1), where(<clause>) -> where(None) (WHERE NULL), a dropped clause,
# == <-> !=, == True <-> == False, order_by(<col>) -> order_by(None) -- changes the
# compiled text, so these six pins kill the whole 48-key SQL family plus the two
# cross-camera window-direction mutants (they shift the literal timestamps).
SIG_CAM = (
    "SELECTcameras.id,cameras.name,cameras.folder_path,cameras.status,cameras.created_at,"
    "cameras.last_seen_at,cameras.deleted_at,cameras.property_id,cameras.ingestion_mode,"
    "cameras.rtsp_url,cameras.rtsp_username,cameras.rtsp_password,cameras.stream_profile,"
    "cameras.motion_sensitivity,cameras.calibration_dataFROMcamerasWHEREcameras.id = 'cam-a'"
)
SIG_ZONE = (
    "SELECTcamera_zones.id,camera_zones.camera_id,camera_zones.name,camera_zones.zone_type,"
    "camera_zones.coordinates,camera_zones.shape,camera_zones.color,camera_zones.enabled,"
    "camera_zones.priority,camera_zones.created_at,camera_zones.updated_atFROMcamera_zones"
    "WHEREcamera_zones.camera_id = 'cam-a'ANDcamera_zones.enabled = true"
    "ORDERBYcamera_zones.priorityDESC"
)
SIG_CB = (
    "SELECTclass_baselines.id,class_baselines.camera_id,class_baselines.detection_class,"
    "class_baselines.hour,class_baselines.frequency,class_baselines.sample_count,"
    "class_baselines.last_updatedFROMclass_baselinesWHEREclass_baselines.camera_id = 'cam-a'"
    "ANDclass_baselines.hour = 10"
)
SIG_AB = (
    "SELECTactivity_baselines.id,activity_baselines.camera_id,activity_baselines.hour,"
    "activity_baselines.day_of_week,activity_baselines.avg_count,activity_baselines"
    ".sample_count,activity_baselines.last_updatedFROMactivity_baselines"
    "WHEREactivity_baselines.camera_id = 'cam-a'ANDactivity_baselines.hour = 10"
    "ANDactivity_baselines.day_of_week = 0"
)
SIG_XD = (
    "SELECTdetections.id,detections.camera_id,detections.file_path,detections.file_type,"
    "detections.detected_at,detections.object_type,detections.confidence,detections.bbox_x,"
    "detections.bbox_y,detections.bbox_width,detections.bbox_height,detections"
    ".thumbnail_path,detections.media_type,detections.duration,detections.video_codec,"
    "detections.video_width,detections.video_height,detections.track_id,"
    "detections.track_confidence,detections.search_vector,detections.labelsFROMdetections"
    "WHEREdetections.camera_id ! = 'cam-a'ANDdetections.detected_at > = "
    "'2025-06-0209:55:00+00:00'ANDdetections.detected_at < = '2025-06-0210:15:00+00:00'"
    "ORDERBYdetections.detected_at"
)
SIG_IN = SIG_CAM.replace("WHEREcameras.id = 'cam-a'", "WHEREcameras.idIN ( 'cam-b' )")


def test_enrich_camera_query_shape():
    """enrich m2/m3/m4/m5 (select(None), where(None), class->None, == -> !=)."""
    e = enricher()
    s = Session([Res(one=SimpleNamespace(name="Front Door")), Res(rows=[])])
    run(e.enrich("b1", CAM, [], session=s))
    assert s.sigs[0] == SIG_CAM


def test_zone_query_shape():
    """_get_zone_context m2-m11 (10 keys: whole stmt, order_by, both clauses, ==/!=, True/False)."""
    e = enricher()
    s = Session([Res(rows=[])])
    run(e._get_zone_context(CAM, [], s))
    assert s.sigs == [SIG_ZONE]


def test_class_baseline_query_shape():
    """_get_baseline_context m23-m30 (8 keys)."""
    e = enricher()
    s = Session([Res(rows=[]), Res()])
    run(e._get_baseline_context(CAM, [], T0, s))
    assert s.sigs[0] == SIG_CB


def test_activity_baseline_query_shape():
    """_get_baseline_context m37-m47 (11 keys)."""
    e = enricher()
    s = Session([Res(rows=[]), Res()])
    run(e._get_baseline_context(CAM, [], T0, s))
    assert s.sigs[1] == SIG_AB


def test_cross_camera_detection_query_shape():
    """_get_cross_camera_activity m8-m19 (12 keys) + window m2/m5 via the literals."""
    e = enricher()
    s = Session([Res(rows=[])])
    run(e._get_cross_camera_activity(CAM, T0, T0 + timedelta(minutes=10), s))
    assert s.sigs == [SIG_XD]


def test_cross_camera_name_query_shape():
    """_get_cross_camera_activity m30/m31/m32 (select(None), in_(None) raises, cls->None)."""
    e = enricher()
    other = det(9, cam="cam-b", at=T0 + timedelta(seconds=120))
    s = Session([Res(rows=[other]), Res(rows=[SimpleNamespace(id="cam-b", name="Back")])])
    run(e._get_cross_camera_activity(CAM, T0, T0 + timedelta(minutes=10), s))
    assert s.sigs[1] == SIG_IN


# -------------------------------------------------------------------- baseline deviation
def deviation(dets, avg=None, samples=10, classes=None, result=(False, 0.0)):
    """Drives _get_baseline_context; returns the BaselineContext."""
    e = enricher(result)
    ab = SimpleNamespace(avg_count=avg, sample_count=samples) if avg is not None else None
    cb_rows = classes or []
    s = Session([Res(rows=list(cb_rows)), Res(one=ab)])
    return run(e._get_baseline_context(CAM, dets, T0, s))


def people(n):
    return [det(i) for i in range(n)]


def test_deviation_ratio_above_expected():
    """ratio 3.0 -> 0.667: kills m60 (mul), m64/m65 (expr), m79 (clamp), m85/m87 (flag), m54/m55 (gate)."""
    b = deviation(people(12), avg=4.0)
    assert abs(b.deviation_score - 0.6666666666666667) < 1e-9
    assert b.is_anomalous is True


def test_deviation_ratio_mildly_above_expected():
    """ratio 1.5 -> 0.333 (kills m69 `ratio > 2`, which falls to the other branch)."""
    b = deviation(people(6), avg=4.0)
    assert abs(b.deviation_score - 0.3333333333333333) < 1e-9
    assert b.is_anomalous is False


def test_deviation_ratio_below_expected():
    """ratio 0.5 -> 0.25 (kills m63 `or True`, m70, m71, m72, m73)."""
    b = deviation(people(2), avg=4.0)
    assert abs(b.deviation_score - 0.25) < 1e-9
    assert b.is_anomalous is False


def test_deviation_ratio_exactly_expected():
    """ratio 1.0 -> 0.0, the m68 branch-merge point (registered equivalent)."""
    b = deviation(people(4), avg=4.0)
    assert b.deviation_score == 0.0
    assert b.is_anomalous is False


def test_deviation_zero_current_hits_threshold_boundary():
    """dev exactly 0.5 and NOT anomalous (kills m86 `>` -> `>=`)."""
    b = deviation([], avg=4.0)
    assert b.deviation_score == 0.5
    assert b.is_anomalous is False


def test_deviation_fractional_expected_enters_ratio_branch():
    """avg 0.5 with class baselines present: gate is `expected > 0`, not `> 1` (kills m58)."""
    cls = SimpleNamespace(
        camera_id=CAM, hour=10, detection_class="person", frequency=2.0, sample_count=0
    )
    b = deviation([], avg=0.5, classes=[cls])
    assert b.deviation_score == 0.5


def test_class_anomaly_boost_scales_by_eighty_percent():
    """max(dev, score * 0.8): 0.5 vs 0.8*0.8 = 0.64 (kills m107 `/`, m108 `*1.8`)."""
    b = deviation(people(1), avg=None, result=(True, 0.8))
    assert abs(b.deviation_score - 0.64) < 1e-9
    assert b.is_anomalous is True


def test_is_anomalous_called_with_exact_positional_and_kwarg():
    """kills m92-m99: every argument to _baseline_service.is_anomalous, incl. session=."""
    e = enricher()
    s = Session([Res(rows=[]), Res()])
    run(e._get_baseline_context(CAM, people(1), T0, s))
    assert e._baseline_service.calls == [((CAM, "person", T0), {"session": s})]


def test_format_class_anomaly_context_called_with_exact_kwargs():
    """kills m111/m112: camera_id and current_hour passed to format_class_anomaly_context."""
    seen = []

    def fake(**kw):
        seen.append(kw)
        return "", []

    e = enricher()
    s = Session([Res(rows=[]), Res()])
    with patch(f"{MOD}.format_class_anomaly_context", fake):
        run(e._get_baseline_context(CAM, people(1), T0, s))
    assert seen == [
        {"camera_id": CAM, "current_hour": 10, "detections": {"person": 1}, "baselines": {}}
    ]


def test_baseline_context_carries_anomalies_and_context():
    """kills m126/m127/m134/m135: class_anomalies + class_anomaly_context drop-vs-None."""
    anomaly = ClassAnomalyResult(class_name="person", message="rare", severity="high")

    def fake(**kw):
        return "CTX-STRING", [anomaly]

    e = enricher()
    s = Session([Res(rows=[]), Res()])
    with patch(f"{MOD}.format_class_anomaly_context", fake):
        b = run(e._get_baseline_context(CAM, people(1), T0, s))
    assert b.class_anomalies == [anomaly]
    assert b.class_anomaly_context == "CTX-STRING"
    assert isinstance(b.class_anomalies, list)
    assert abs(b.deviation_score - 0.65) < 1e-9  # 0.5 + risk_modifier 15/100
    # the anomaly block must SET the flag, not merely leave it alone
    assert b.is_anomalous is True


def test_class_anomaly_risk_boost_is_capped_at_ninety_five():
    """pre-boost 0.9 + 15/100 = 1.05 -> 0.95; a raised cap leaks 1.05."""
    anomaly = ClassAnomalyResult(class_name="person", message="rare", severity="high")

    def fake(**kw):
        return "CTX", [anomaly]

    e = enricher()
    s = Session([Res(rows=[]), Res(one=SimpleNamespace(avg_count=4.0, sample_count=10))])
    with patch(f"{MOD}.format_class_anomaly_context", fake):
        b = run(e._get_baseline_context(CAM, people(40), T0, s))  # ratio 10 -> 0.9
    assert abs(b.deviation_score - 0.95) < 1e-9
    assert b.is_anomalous is True


# ----------------------------------------------------------------------- zone context
def test_bbox_none_guards_skip_exactly_one_missing_component():
    """kills m18/m19/m20: each `or` -> `and` collapse lets a half-broken bbox reach bbox_center."""
    e = enricher()
    zg = zone("z-ok")
    for bad in (
        det(1, x=None),
        det(2, y=None),
        det(3, w=None),
        det(4, h=None),
    ):
        s = Session([Res(rows=[zg])])
        assert run(e._get_zone_context(CAM, [bad], s)) == [], bad.id
    s = Session([Res(rows=[zg])])
    assert [z.detection_count for z in run(e._get_zone_context(CAM, [det(5)], s))] == [1]


def test_bbox_value_error_continues_to_the_next_detection():
    """kills the two continue -> break mutants: the FIRST bad detection must not stop the loop."""
    e = enricher()
    zg = zone("z-ok")
    bad_value_error = det(1, w=0)  # bbox_center raises ValueError
    s = Session([Res(rows=[zg])])
    out = run(e._get_zone_context(CAM, [bad_value_error, det(2)], s))
    assert [z.detection_count for z in out] == [1]
    bad_bbox = det(3, y=None)
    s = Session([Res(rows=[zg])])
    out = run(e._get_zone_context(CAM, [bad_bbox, det(4)], s))
    assert [z.detection_count for z in out] == [1]


def test_zone_sort_is_descending_by_detection_count():
    """kills m74-m79: key=None / key dropped / reverse None or False all change the order."""
    e = enricher()
    z1 = zone("many", priority=2)
    z2 = zone(
        "few",
        coords=((0.5, 0.5), (1.0, 0.5), (1.0, 1.0), (0.5, 1.0)),
        priority=1,
    )
    dets = [det(1), det(2), det(3), det(4, x=1000, y=900)]
    s = Session([Res(rows=[z1, z2])])
    out = run(e._get_zone_context(CAM, dets, s))
    assert [(z.zone_id, z.detection_count) for z in out] == [("many", 3), ("few", 1)]


def test_off_map_zone_type_gets_the_low_risk_weight_default():
    """kills m58/m60/m61/m62: default None, dropped default, XXlowXX, LOW."""
    e = enricher()
    s = Session([Res(rows=[zone("z1")])])
    out = run(e._get_zone_context(CAM, [det(1)], s))
    assert [z.risk_weight for z in out] == ["low"]


def test_zone_context_fields_are_exact():
    """zone id/name/type/count projected exactly (guards the ZoneContext kwargs family)."""
    e = enricher()
    z = zone("z1", name="Front Door", ztype=CameraZoneType.ENTRY_POINT)
    s = Session([Res(rows=[z])])
    out = run(e._get_zone_context(CAM, [det(1)], s))
    assert out == [ZoneContext("z1", "Front Door", "entry_point", "high", 1)]


# ------------------------------------------------------------------- cross-camera math
def cross(dets, names=None, start=None, end=None):
    e = enricher()
    s = Session([Res(rows=list(dets)), Res(rows=names or [])])
    st = start or T0
    return run(e._get_cross_camera_activity(CAM, st, end or st + timedelta(minutes=10), s))


def test_reference_time_is_the_window_midpoint():
    """kills m37/m38/m40: the reference is start + (end-start)/2 = T0+300s, so a
    detection at T0+120s sits -180s from it (m37 gives +420, m38 -1080, m40 -80)."""
    other = det(9, cam="cam-b", at=T0 + timedelta(seconds=120))
    out = cross([other], names=[SimpleNamespace(id="cam-b", name="Back")])
    assert len(out) == 1
    assert abs(out[0].time_offset_seconds + 180.0) < 1e-9


def test_average_offset_divides_by_detection_count():
    """kills m43 (time_offsets None), m47 (`and False`), m49 (`*len`), m62 (kwarg drop)."""
    d1 = det(9, cam="cam-b", at=T0 + timedelta(seconds=120))
    d2 = det(10, cam="cam-b", at=T0 + timedelta(seconds=60))
    out = cross([d1, d2], names=[SimpleNamespace(id="cam-b", name="Back")])
    assert abs(out[0].time_offset_seconds + 210.0) < 1e-9
    assert out[0].camera_name == "Back"
    assert out[0].detection_count == 2


def test_cross_camera_name_falls_back_to_the_id():
    """cameras.get(cam_id, cam_id) when the camera row is missing."""
    out = cross([det(9, cam="cam-b", at=T0)], names=[])
    assert out[0].camera_name == "cam-b"


# ---------------------------------------------------------------------- enrich plumbing
def test_enrich_delegates_with_exact_arguments():
    """kills m34/m35/m41/m49/m50: the three _get_* call sites, args and the await itself."""
    e = enricher()
    seen = {}

    async def zones(camera_id, detections, sess):
        seen["zones"] = (camera_id, detections, sess)
        return []

    async def baselines(camera_id, detections, reference_time, sess):
        seen["baselines"] = (camera_id, detections, reference_time, sess)

    async def crosscam(camera_id, start_time, end_time, sess):
        seen["cross"] = (camera_id, start_time, end_time, sess)
        return []

    e._get_zone_context = zones
    e._get_baseline_context = baselines
    e._get_cross_camera_activity = crosscam
    d = det(1, at=T0)
    s = Session([Res(one=SimpleNamespace(name="Front Door")), Res(rows=[d])])
    with patch(f"{MOD}.batch_fetch_detections", fetcher([d])):
        ctx = run(e.enrich("b1", CAM, [1], session=s))
    assert seen["zones"] == (CAM, [d], s)
    assert seen["baselines"] == (CAM, [d], T0, s)
    assert seen["cross"] == (CAM, T0, T0, s)
    assert ctx.camera_name == "Front Door"


def fetcher(rows):
    """Stand-in for batch_fetch_detections (a bare lambda trips ruff ARG005)."""

    async def _fetch(*_args, **_kwargs):
        return list(rows)

    return _fetch


def test_enrich_full_context_shape_is_exact():
    """kills m60/m62/m63/m68/m71 and m27/m32 (tz-aware fallback window)."""
    e = enricher()

    async def zones(camera_id, detections, sess):
        return [ZoneContext("z1", "Front", "entry_point", "high", 2)]

    async def baselines(camera_id, detections, reference_time, sess):
        return BaselineContext(hour_of_day=10, day_of_week="Monday")

    async def crosscam(camera_id, start_time, end_time, sess):
        return [CrossCameraActivity("cam-b", "Back", 1)]

    e._get_zone_context = zones
    e._get_baseline_context = baselines
    e._get_cross_camera_activity = crosscam
    d = det(1, at=T0 + timedelta(seconds=5))
    s = Session([Res(one=SimpleNamespace(name="Front Door")), Res(rows=[d])])
    with patch(f"{MOD}.batch_fetch_detections", fetcher([d])):
        ctx = run(e.enrich("b1", CAM, [1], session=s))
    assert ctx.zones and ctx.zones[0].zone_id == "z1"
    assert ctx.cross_camera and ctx.cross_camera[0].camera_id == "cam-b"
    assert ctx.recent_events == []
    assert ctx.start_time == T0 + timedelta(seconds=5)
    assert ctx.start_time.tzinfo is not None
    assert ctx.end_time.tzinfo is not None


def test_enrich_fallback_window_is_timezone_aware():
    """m27/m32: with every detected_at missing, `datetime.now(UTC)` -> `now(None)` is naive."""
    e = enricher()

    async def nope(*_args, **_kwargs):
        return []

    e._get_zone_context = nope
    e._get_baseline_context = nope
    e._get_cross_camera_activity = nope
    d = det(1, at=NO_TIME)
    s = Session([Res(one=SimpleNamespace(name="Front Door")), Res(rows=[d])])
    with patch(f"{MOD}.batch_fetch_detections", fetcher([d])):
        ctx = run(e.enrich("b1", CAM, [1], session=s))
    assert ctx.start_time is not None and ctx.start_time.tzinfo is not None
    assert ctx.end_time.tzinfo is not None
    assert ctx.start_time.utcoffset() == timedelta(0)


# ------------------------------------------------------------------------- log shapes
def test_init_logs_the_configured_window():
    """__init__ m5: logger.info(None) loses the message."""
    with caplogger() as h:
        with patch(f"{MOD}.get_baseline_service", lambda: SimpleNamespace()):
            ContextEnricher(cross_camera_window=420)
    assert "ContextEnricher initialized: cross_camera_window=420s" in h.records


def test_no_zones_debug_message_is_exact():
    """_get_zone_context m15: logger.debug(None)."""
    e = enricher()
    with caplogger() as h:
        run(e._get_zone_context(CAM, [], Session([Res(rows=[])])))
    assert "No zones defined for camera cam-a" in h.records


def test_zone_mapping_debug_message_is_exact():
    """_get_zone_context m80: logger.debug(None)."""
    e = enricher()
    with caplogger() as h:
        run(e._get_zone_context(CAM, [det(1)], Session([Res(rows=[zone("z1")])])))
    assert "Zone mapping for camera cam-a: 1 zones with detections" in h.records


def test_baseline_debug_message_is_exact():
    """_get_baseline_context m119: logger.debug(None)."""
    e = enricher()
    with caplogger() as h:
        run(e._get_baseline_context(CAM, people(2), T0, Session([Res(rows=[]), Res()])))
    want = (
        "Baseline context for camera cam-a at 10:00 Monday: deviation=0.50, "
        "anomalous=False, class_anomalies=0"
    )
    assert want in h.records


def test_cross_camera_debug_message_is_exact():
    """_get_cross_camera_activity m73: logger.debug(None)."""
    e = enricher()
    d = det(9, cam="cam-b", at=T0)
    with caplogger() as h:
        run(
            e._get_cross_camera_activity(
                CAM,
                T0,
                T0 + timedelta(minutes=10),
                Session([Res(rows=[d]), Res(rows=[SimpleNamespace(id="cam-b", name="Back")])]),
            )
        )
    assert "Cross-camera activity: 1 cameras with 1 total detections" in h.records


def test_no_detections_warning_message_is_exact():
    """enrich m17: logger.warning(None)."""
    e = enricher()
    with caplogger() as h:
        run(e.enrich("b42", CAM, [], session=Session([Res(one=None)])))
    assert "No detections found for batch b42, returning minimal context" in h.records


# --------------------------------------------------------------------------- formatters
def test_format_zone_analysis_exact_for_known_and_off_map_types():
    """kills m8-m14 and m17 of format_zone_analysis (labels, key, default, join)."""
    e = enricher()
    zones = [
        ZoneContext("z1", "Front Door", "entry_point", "high", 3),
        ZoneContext("z2", "Roof", "rooftop", "low", 1),
    ]
    assert e.format_zone_analysis(zones) == (
        "- Front Door (entry_point - high sensitivity - direct access to home): "
        "3 detection(s), risk weight: high\n"
        "- Roof (rooftop - low sensitivity - general area): "
        "1 detection(s), risk weight: low"
    )
    assert e.format_zone_analysis([]) == "No zone data available."


def test_format_baseline_comparison_exact_strings():
    """kills m7/m13/m17/m24 of format_baseline_comparison (headers, fallback, join)."""
    e = enricher()
    assert e.format_baseline_comparison(None) == "No baseline data available."
    full = BaselineContext(
        hour_of_day=10,
        day_of_week="Monday",
        expected_detections={"person": 2.5},
        current_detections={"person": 4},
        deviation_score=0.75,
        is_anomalous=True,
    )
    assert e.format_baseline_comparison(full) == (
        "Expected activity:\n  - person: ~2.5 per hour\n"
        "Current activity:\n  - person: 4\n"
        "NOTICE: Activity is unusual for this time (deviation: 0.75)"
    )
    empty_expected = BaselineContext(
        hour_of_day=10,
        day_of_week="Monday",
        current_detections={"car": 1},
    )
    assert e.format_baseline_comparison(empty_expected) == (
        "No historical baseline for this time slot.\nCurrent activity:\n  - car: 1"
    )


def test_format_cross_camera_summary_exact_strings():
    """kills m2/m6/m7/m31/m32/m36 of format_cross_camera_summary."""
    e = enricher()
    assert e.format_cross_camera_summary([]) == "No activity detected on other cameras."
    lines = e.format_cross_camera_summary(
        [
            CrossCameraActivity("c1", "Back Door", 2, ["person", "vehicle"], 30.0),
            CrossCameraActivity("c2", "Gate", 1, [], -600.0),
        ]
    )
    assert lines == (
        "- Back Door: 2 detection(s) [person, vehicle]\n"
        "- Gate: 1 detection(s) [unknown] (10 min before)"
    )


def test_format_cross_camera_offset_threshold_and_minutes():
    """kills m9 (>60 vs >=60), m10 (>60 vs >61), m14 (/60 vs /61)."""
    e = enricher()
    at60 = e.format_cross_camera_summary([CrossCameraActivity("c", "C", 1, ["x"], 60.0)])
    assert at60 == "- C: 1 detection(s) [x]"
    at61 = e.format_cross_camera_summary([CrossCameraActivity("c", "C", 1, ["x"], 61.0)])
    assert at61 == "- C: 1 detection(s) [x] (1 min after)"
    at90 = e.format_cross_camera_summary([CrossCameraActivity("c", "C", 1, ["x"], 90.0)])
    assert at90 == "- C: 1 detection(s) [x] (2 min after)"
    neg = e.format_cross_camera_summary([CrossCameraActivity("c", "C", 1, ["x"], -90.0)])
    assert neg == "- C: 1 detection(s) [x] (2 min before)"
