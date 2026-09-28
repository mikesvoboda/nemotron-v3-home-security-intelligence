r"""S2 batch-28 lane L10 - ``detector_client`` group dc13 kill battery (74 keys).

Source: ``backend/services/detector_client.py``, md5 ``294c938abe9e37cd0f979f9357982753``
(the provenance blob ``83632911:backend/services/detector_client.py`` is byte-identical to
the workspace file, so every bank line below is also a CURRENT line).  Manifest group
``dc13-detect-persist-metrics-summary-logs`` - 74 KILLABLE keys,
``manifest_groups/dc13-detect-persist-metrics-summary-logs.keys`` (identical content to
``group_12.keys``).  Splice report: 37 clean / 36 twin / 1 unparseable (m472).  The
current ``replay_lib`` measures 70 single-position keys, 4 twin keys and 96 candidate mutants,
and it splices m472 itself; the hand-splice probe below is kept as an INDEPENDENT proof of that
key (including a line-count-neutral splice, so the kill cannot be a line-number artifact).

What the group owns
===================
``DetectorClient.detect_objects`` from the ``Detection`` construction to the ``return``:
the persist + telemetry tail (L1311-L1334), the camera bookkeeping (L1336-L1344), the
baseline updates (L1346-L1368) and the duration + summary logs (L1370-L1395).  Shipped
behaviour, pinned at those lines:

* one ``session.add`` per stored detection, carrying the real ``Detection`` (L1311);
* ``record_detection_by_class(object_class)`` (L1316) and
  ``observe_detection_confidence(confidence)`` (L1317) - the SECOND
  ``object_class = detection_data.get("class", "unknown")`` read (L1315) feeds only the
  class counter, which is what separates the L1187/L1315 occurrence twins;
* the per-detection DEBUG at L1319 with the shipped two-part f-string and NO extras;
* the ``except (ValueError, TypeError, KeyError)`` arm (L1324-L1334): ONE ERROR at L1328
  whose sentence, sanitized ``error`` extra and real traceback are all asserted, then
  ``record_pipeline_error("detection_processing_error")`` once and the loop CONTINUES;
* ``camera.last_seen_at = detected_at`` (L1340) plus its DEBUG at L1341; the baseline block
  (L1347-L1368) - one ``update_baseline`` await per unique non-None ``object_type``, with
  the FIRST detection's timestamp and this session - then ``await session.flush()`` and
  exactly one ``await session.commit()``;
* ``duration_ms = int((time.time() - start_time) * 1000)`` (L1372), carried by the INFO
  "Stored detections" (L1386, five fields) or by the no-detections DEBUG (L1388, three).

Candidate-twin table (ALL candidates must redden; each is pinned by its record line)
===================================================================================
``Logger.findCaller`` reports the FIRST line of the emitting call, so a single-line call's
record line IS the shipped statement and a multi-line call is pinned by its ``logger.<level>(``
line.  ``replay_lib.candidates()`` measures 96 candidate mutants over the 74 keys: 70 keys are
single-position and 4 carry twins; every candidate below is reddened by a leg that asserts that
record's OWNED FIELDS, so a mutant at any candidate position - not merely at the bank-cited one -
changes a named assertion.

key(s)                          candidate splice lines                 pinned by
m408                            1311                    the ``session.add`` payload
m410-m418                       1187, 1315              the class-less item: its stored
                                                        ``object_type`` is None and its DEBUG
                                                        prints ``None`` while the class counter
                                                        still receives "unknown"
m419, m420                      1316, 1317              the two metric spy argument tuples
m421                            1320                    the per-detection DEBUG's raw msg
m422, m428-m430                 1329                    the ERROR's sentence
m423, m426, m431-m433           448 <-> 1330            the two ``extra={"error":
m424, m427, m434                433, 440, 449, 716,     sanitize_error(e)},`` sites and the
                                747, 781, 816, 875,     eleven ``exc_info=True,`` lines - each
                                908, 1331, 1438         pinned by asserting the record carries
                                                        a populated exc_info triple (and the
                                                        two shipped exc_info-free calls by
                                                        asserting its ABSENCE)
m435-m437                       1333                    ``record_pipeline_error`` argument
m438                            1201, 1209, 1221, 1240, the seven ``continue`` statements, each
                                1262, 1278, 1334        exercised with a FOLLOWING item that a
                                                        ``break`` mutant would drop
m445-m452                       1342, 1343              the camera DEBUG's msg and its two keys
m455, m456                      1355, 1358              the baseline predicate and timestamp
m458, m462                      643, 1133, 1282, 1361   the four ``camera_id=camera_id,`` lines:
                                                        the trace_span keyword set, the
                                                        circuit-breaker call keywords, the
                                                        ``Detection`` field and the
                                                        ``update_baseline`` keyword
m459-m465                       1362, 1363, 1364        the other three baseline keywords
m466-m470                       1372, 1404, 1428        the three identical ``duration_ms =``
                                                        reads, each pinned by the arm that
                                                        reports it (INFO / breaker WARNING /
                                                        ERROR)
m472                            1378                    the INFO payload dict (also proven by a
                                                        hand-splice probe - see below)
m473, m474, m492, m493          1379, 1391              the INFO's and the DEBUG's ``camera_id``
m475, m476, m494, m495          1380, 1392              the same pair's ``file_path``
m477, m478                      1381                    ``detection_count``
m479, m480, m496, m497          1382, 1393              the two ``"duration_ms":`` fields
m481-m487                       1386                    the INFO call and its sentence
m488-m491                       1389, 1390              the no-detections DEBUG's msg/extra

Cross-module twins: the L696/L711/L727/L742/L760/L776/L796/L811/L834/L856/L871/L888/L903
(``"camera_id": camera_id,``) and L697/L712/.../L904 (``"file_path": image_path,``) members of
m473-m495 - plus L947/L948, L967, L974, L1049, L1062, L1073/L1074, L1104, L1410/L1411, L1434 -
are inside the harness's provenance-line disambiguation for this group, but each of those
record lines is ALSO pinned field-by-field by its own leg (the seven ``_send_detection_request``
exhaustion legs, the three validation legs, the missing-file, request-debug, breaker-reject,
buffered-frame, breaker-trip and read-failure legs), so no candidate relies on the
disambiguation alone.

Discipline
==========
Only shipped text and shipped structure are asserted, read off this source.  Every mock is
``autospec=True`` or ``new=`` (WP4.2).  No import-time global spy and no session-scope clock:
``M.time`` is replaced per-leg by ``new=`` over a real-clock stand-in whose ``offset`` flips
inside the shipped window (``time.monotonic``/``time.perf_counter`` are never touched), and
the shipped ``await asyncio.sleep(...)`` is pinned ``new=`` to a counter.  Each caplog window
opens with ``set_level``/``at_level`` and is drained, so no foreign record - including the
once-per-process class-semaphore DEBUG at L221 - can reach an assertion.

Style source: ``test_detector_client.py`` (shipped) and the proven sibling
``test_detector_client_batch28_06.py``; the clock stand-in follows the proven sibling
``test_detector_client_batch28_09.py``.  m472 (``log_extra: dict[str, Any] = None``) cannot
be spliced by the harness - the bank reprints that six-line block at the wrong indent - so it
is proven by the hand-splice probe recorded in ``/tmp/dc13-probe/manual_472.py``.
"""

from __future__ import annotations

import ast
import asyncio
import logging
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import backend.services.detector_client as M

pytestmark = pytest.mark.unit

# --- world-aware shipped-lineno re-anchor (abort-family seventh member) ----------
# The shipped lineno pins in this file hold in the pristine world and in the raw-
# copy replay world, but the bank runs the INSTRUMENTED tree under mutants/,
# where every mutated function is duplicated (backend/services/detector_client.py
# ships 1,443 lines against ~380k instrumented), so every shipped call ALSO fires
# from its per-mutant copies at shifted linenos.  Map every physical lineno of the
# loaded module back onto its pristine statement by matching the full shipped call
# block text; a copy whose block is mutated no longer matches, so its records
# normalize raw and fall OUTSIDE the pin sets -- exactly the red a log-surface
# mutation must produce.  Same strength in the pristine world (identity map).
_PRISTINE = Path(M.__file__)
_parts = _PRISTINE.parts
if "mutants" in _parts:
    _i = len(_parts) - 1 - _parts[::-1].index("mutants")
    _PRISTINE = Path(*_parts[:_i], *_parts[_i + 1 :])


def _logger_call_blocks(text: str) -> dict[int, tuple[str, ...]]:
    """Every shipped ``logger.<level>(...)`` statement: head lineno -> stripped block."""
    tree = ast.parse(text)
    lines = [ln.strip() for ln in text.splitlines()]
    out: dict[int, tuple[str, ...]] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "logger"
        ):
            out[node.lineno] = tuple(lines[node.lineno - 1 : node.end_lineno])
    assert len(set(out.values())) == len(out), (
        "two shipped logger calls share block text; the re-anchor map needs "
        "distinct blocks — disambiguate by extending the matched sequence"
    )
    return out


_SHIPPED_BLOCKS = _logger_call_blocks(_PRISTINE.read_text())
_live_src = Path(M.__file__).read_text()  # nosemgrep: path-traversal-open
_live_lines = [ln.strip() for ln in _live_src.splitlines()]
_by_head: dict[str, list[tuple[int, tuple[str, ...]]]] = {}
for _pl, _blk in _SHIPPED_BLOCKS.items():
    _by_head.setdefault(_blk[0], []).append((_pl, _blk))
_LIVE_TO_PRISTINE: dict[int, int] = {}
for _idx, _line in enumerate(_live_lines):
    for _pl, _blk in _by_head.get(_line, ()):
        if tuple(_live_lines[_idx : _idx + len(_blk)]) == _blk:
            assert _LIVE_TO_PRISTINE.setdefault(_idx + 1, _pl) == _pl, (
                f"physical line {_idx + 1} of {M.__file__} holds two shipped blocks"
            )
            break


def _anchor(rec: logging.LogRecord) -> int:
    """The record's shipped (pristine) statement line, in every world."""
    return _LIVE_TO_PRISTINE.get(rec.lineno, rec.lineno)


MIN_SIZE = M.MIN_DETECTION_IMAGE_SIZE
_IMAGE_PATH = "/export/yard/cam07/snap-0412.jpg"
_CAM = "cam-7"
_BYTES = b"jpeg-payload-bytes"

# Every record line a dc13 candidate can mutate or shift.  L221 (the lazily built class
# semaphore's DEBUG, emitted at most once per process) is NOT a dc13 candidate, so it is
# deliberately absent - an ordered fingerprint must not depend on another leg's leftovers.
# The record lines this group's candidates can produce or remove.  ``Logger.findCaller``
# reports the FIRST line of the emitting call, so every multi-line call here is pinned by its
# ``logger.<level>(`` line (692, 1060, 1319, 1328, 1341, ...) - the same convention the proven
# sibling ``test_detector_client_batch28_06.py`` pins.  L221/L357 (the once-per-process class
# semaphore DEBUG and the ``__init__`` INFO) are not dc13 candidates and are dropped by
# :func:`mine`, so an ordered fingerprint never depends on another leg's leftovers.
_ARM = frozenset(
    {
        430,
        437,
        446,
        692,
        707,
        723,
        738,
        755,
        771,
        792,
        807,
        830,
        851,
        866,
        884,
        899,
        944,
        965,
        972,
        1047,
        1060,
        1069,
        1101,
        1195,
        1208,
        1220,
        1234,
        1257,
        1266,
        1274,
        1319,
        1328,
        1341,
        1386,
        1388,
        1406,
        1430,
    }
)
_IGNORED = frozenset({221, 222, 357})


_NOISE = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "asctime",
    "message",
    "request_id",
    "correlation_id",
    "trace_id",
    "span_id",
    "connection_id",
    "task_id",
    "job_id",
    "hostname",
    "container_id",
    "app_version",
    "environment",
}


# --- caplog helpers -----------------------------------------------------------


async def win(caplog, coro_factory, level: int = logging.DEBUG):
    """Run one coroutine inside an isolated logging window on the MODULE's own logger.

    The window is opened on ``detector_client``'s own logger name, so a mutant sitting on a
    twin line anywhere in the module - inside ``detect_objects`` or inside
    ``_send_detection_request``/``health_check`` - lands in the same window and reddens the
    leg's fingerprint.
    """
    caplog.set_level(level, logger=M.logger.name)
    for rec in list(caplog.records):
        caplog.records.remove(rec)
    caplog.handler.clear()
    with caplog.at_level(level, logger=M.logger.name):
        before = tuple(caplog.records)
        try:
            value = await coro_factory()
            error: BaseException | None = None
        except Exception as exc:  # the leg asserts the shipped exception itself
            value, error = None, exc
    records = mine(caplog, before)
    in_arm(records)
    return value, error, records


def mine(caplog, before):
    """Every NEW record from this module's own logger, minus the two that no dc13 candidate
    can touch (:data:`_IGNORED`).  ALL of the rest are kept - not only the ones on a known
    line - so a mutant that moves a call to a different line still shows up in the
    fingerprint (and is caught by :func:`in_arm`)."""
    return tuple(
        r
        for r in caplog.records
        if r not in before and r.name == M.logger.name and _anchor(r) not in _IGNORED
    )


def sent(records) -> list[tuple[int, int]]:
    """The ordered fingerprint: (levelno, emitting line) of every owned record."""
    return [(r.levelno, _anchor(r)) for r in records]


def in_arm(records) -> None:
    """No record may arrive from outside the lines this group's candidates can touch."""
    stray = [ln for _, ln in sent(records) if ln not in _ARM]
    assert not stray, f"records from unexpected lines: {stray} ({sent(records)})"


def fields(rec) -> dict:
    return {k: v for k, v in rec.__dict__.items() if k not in _NOISE}


def at(records, line: int, level=None):
    return [r for r in records if _anchor(r) == line and (level is None or r.levelno == level)]


def one(records, line: int, level: int | None = None):
    hit = at(records, line, level)
    assert len(hit) == 1, f"expected exactly one record at L{line}: {sent(records)}"
    return hit[0]


def has_traceback(rec) -> bool:
    """True when the emitter was handed a real exception triple (None/False/dropped all
    render "no traceback", so triple presence is the only observable)."""
    exc_info = rec.exc_info
    return isinstance(exc_info, tuple) and len(exc_info) == 3 and exc_info[1] is not None


def body(dets, *, width=1280, height=720) -> dict:
    """The detector's JSON response (L1142/L1153/L1169-L1170/L1184)."""
    payload = {"detections": list(dets)}
    if width is not None:
        payload["image_width"] = width
    if height is not None:
        payload["image_height"] = height
    return payload


def det(confidence, klass, bbox) -> dict:
    """One entry of ``result["detections"]``.  ``klass=None`` omits the ``"class"`` key
    entirely - the shipped ``detection_data.get("class")`` (L1286) then yields None while
    ``detection_data.get("class", "unknown")`` (L1187/L1315) yields "unknown"."""
    item = {"confidence": confidence, "bbox": list(bbox)}
    if klass is not None:
        item["class"] = klass
    return item


# Shipped response used by the happy-path legs: two stored items of DIFFERENT classes (so the
# baseline set has two members and its iteration order cannot hide a kwarg mutant) plus one
# item below the 0.5 threshold that must be filtered out before any of that runs.
_BODY_PERSISTS = body(
    [
        det(0.95, "person", [100, 150, 200, 300]),
        det(0.88, "car", [50, 60, 70, 80]),
        det(0.45, "dog", [1, 2, 3, 4]),
    ]
)
_BODY_UNKNOWN = body([det(0.9, None, [2, 3, 4, 5])])
_BODY_CLASSLESS_TWO = body([det(0.9, None, [2, 3, 4, 5]), det(0.8, None, [6, 7, 8, 9])])
_BODY_NONE_CLASS_ONE = body([det(0.9, None, [2, 3, 4, 5]), det(0.7, "car", [9, 9, 9, 9])])
_BODY_RAISES_FIRST = body(
    [
        {"confidence": {"deep": "nested"}, "class": "ghost", "bbox": [1, 1, 1, 1]},
        det(0.9, "person", [10, 10, 10, 10]),
    ]
)
_BODY_NO_DIMS = body(
    [det(0.9, "person", [4, 5, -3, 6]), det(0.8, "car", [1, 2, 3, 4])],
    width=None,
    height=None,
)
_BODY_ONLY_FILTERED = body([det(0.4, "moth", [10, 10, 10, 10]), det(0.3, None, [5, 5, 5, 5])])
_BODY_RAISES_ONLY = body(
    [{"confidence": {"deep": "nested"}, "class": "ghost", "bbox": [1, 1, 1, 1]}]
)
_BODY_TWO_BAD_BBOX = body(
    [
        # a dict bbox without the four names -> L1208 WARNING + L1209 continue
        {"confidence": 0.9, "class": "ghost", "bbox": {"x": 1, "y": 2}},
        # a list bbox of the wrong length -> L1220 WARNING + L1221 continue
        {"confidence": 0.9, "class": "ghost", "bbox": ["n", "o", "t", "a", "box"]},
        det(0.9, "person", [10, 10, 10, 10]),
    ]
)
_BODY_OUTSIDE = body([det(0.9, "person", [900, 900, 20, 20]), det(0.8, "car", [1, 2, 3, 4])])
_BODY_TOO_SMALL = body([det(0.9, "person", [100, 20, -50, 40]), det(0.8, "car", [1, 2, 3, 4])])
_BODY_CLAMPED = body([det(0.9, "person", [20, 30, 1400, 900])])


def responds(payload):
    """A ``POST /detect`` side effect that succeeds with ``payload`` (L667-L686)."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.raise_for_status.return_value = None
    response.json.return_value = payload

    def _side_effect(*args, **kwargs):
        return response

    return _side_effect


def posted_responds(sink, payload):
    """A ``POST /detect`` side effect that NOTES the call and then succeeds."""
    side = responds(payload)

    def _side_effect(*args, **kwargs):
        sink.append(1)
        return side(*args, **kwargs)

    return _side_effect


def failing(error):
    """A ``POST /detect`` side effect that always raises ``error``."""

    def _side_effect(*args, **kwargs):
        raise error

    return _side_effect


def _status_error(message, status, body=None):
    """A real ``httpx.HTTPStatusError`` carrying a response with ``status_code``/``json()``."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status
    if body is not None:
        response.json.return_value = body
    return httpx.HTTPStatusError(
        message,
        request=httpx.Request("POST", "http://detector.invalid:8000/detect"),
        response=response,
    )


async def run(client, session, *, video_path=None, video_metadata=None):
    return await client.detect_objects(
        _IMAGE_PATH, _CAM, session, video_path=video_path, video_metadata=video_metadata
    )


class TimeStandIn:
    """``detector_client.time`` for one leg (``new=`` form), narrowed to ``time()``.

    ``time()`` hands out the values the leg scripted (a real reading once the script runs
    out) and records every read, so the shipped
    ``duration_ms = int((time.time() - start_time) * 1000)`` (L1372/L1404/L1428) becomes an
    elapsed value the leg chose EXACTLY - the first script entry is the run's ``start_time``
    (L1032) and the last one is the read inside the shipped duration statement.
    ``time.monotonic``/``time.perf_counter`` are never patched, and the stand-in lives only
    inside the one test that asked for it.
    """

    def __init__(self):
        self.script = []
        self.reads = []

    def time(self):
        value = self.script.pop(0) if self.script else time.time()
        self.reads.append(value)
        return value

    def __getattr__(self, name):
        """Anything but ``time()`` (``monotonic``, ``perf_counter``, ...) forwards to the
        REAL module, so the legs never bend a clock they do not own."""
        return getattr(time, name)


@pytest.fixture
def clock():
    stand_in = TimeStandIn()
    with patch.object(M, "time", new=stand_in):
        yield stand_in


@pytest.fixture(autouse=True)
def baseline_service():
    """The shipped suite's autouse mock of ``get_baseline_service`` (reached at L1351)."""
    service = MagicMock()
    service.update_baseline = AsyncMock()
    with patch("backend.services.detector_client.get_baseline_service", autospec=True) as factory:
        factory.return_value = service
        yield service


@pytest.fixture(autouse=True)
def envelope():
    """Correlation headers, the shared inference semaphore, the trace helpers and the OTel
    attribute setters the route consumes - all pinned at the shipped import sites so no leg
    depends on ambient settings or on another test's semaphore.  ``trace_span`` is left
    REAL: it is a generator context manager and the ``camera_id=camera_id`` keyword at L643
    is an occurrence twin of this group, so the real call must run."""
    span = MagicMock()
    trace_id = "0" * 32
    with (
        patch.object(
            M, "get_correlation_headers", autospec=True, return_value={"traceparent": "00-t"}
        ),
        patch.object(
            M, "get_inference_semaphore", autospec=True, return_value=asyncio.Semaphore(4)
        ),
        patch.object(M, "get_trace_id", autospec=True, return_value=trace_id),
        patch.object(M, "add_span_event", autospec=True),
        patch.object(M, "AIModelAttributes", autospec=True) as model_attrs,
        patch.object(M, "trace_span", autospec=True) as trace_span,
        # The two OTel result-attribute helpers are NOT part of what this group asserts (no
        # dc13 key lives in backend.core.telemetry_ai_conventions), and the shipped one sums
        # the raw response confidences - which the malformed-confidence leg feeds a dict to.
        patch.object(M, "set_detection_attributes", autospec=True),
        patch.object(M, "set_inference_result_attributes", autospec=True),
    ):
        trace_span.return_value.__enter__ = MagicMock(return_value=span)
        trace_span.return_value.__exit__ = MagicMock(return_value=False)
        model_attrs.set_on_span = MagicMock()
        yield {"span": span, "trace_id": trace_id, "trace_span": trace_span}


@pytest.fixture
def settings():
    """``get_settings`` pinned to the values this route reads (real floats so a REAL
    ``DetectorClient`` computes its explicit timeout)."""
    st = MagicMock()
    st.ai_gateway_url = None
    st.use_ai_gateway = False
    st.yolo26_url = "http://detector.invalid:8000"
    st.yolo26_api_key = None
    st.yolo26_read_timeout = 60.0
    st.ai_connect_timeout = 5.0
    st.ai_health_timeout = 5.0
    st.detector_max_retries = 2
    st.ai_max_concurrent_inferences = 4
    st.detection_confidence_threshold = 0.5
    st.detection_class_thresholds = {}
    st.ai_warmup_enabled = False
    st.ai_cold_start_threshold_seconds = 60.0
    with patch("backend.services.detector_client.get_settings", autospec=True) as factory:
        factory.return_value = st
        yield st


@pytest.fixture
def metrics():
    """Spies on the five telemetry call sites this group's keys mutate (L76-L83 imports the
    symbols by name, so the shipped call sites are calls of these module globals)."""
    with (
        patch.object(M, "record_pipeline_error", autospec=True) as pipeline_error,
        patch.object(M, "record_detection_processed", autospec=True) as processed,
        patch.object(M, "record_detection_by_class", autospec=True) as by_class,
        patch.object(M, "record_detection_filtered", autospec=True) as filtered,
        patch.object(M, "observe_detection_confidence", autospec=True) as observe,
        patch.object(M, "observe_ai_request_duration", autospec=True) as ai_duration,
    ):
        yield {
            "record_pipeline_error": pipeline_error,
            "record_detection_processed": processed,
            "record_detection_by_class": by_class,
            "record_detection_filtered": filtered,
            "observe_detection_confidence": observe,
            "observe_ai_request_duration": ai_duration,
        }


class _Frame:
    """The shipped frame-buffer branch (L1098-L1108) with the counts it reports."""

    def __init__(self, count=2):
        self.added = []
        self._count = count

    async def add_frame(self, camera_id, data, timestamp):
        self.added.append((camera_id, len(data)))

    def frame_count(self, camera_id):
        return self._count


class _ToThreadInline:
    """``asyncio.to_thread`` that runs the callable inline (``new=`` form) so the shipped
    ``image_file.read_bytes`` (L1084) hits the ``Path`` double below."""

    async def __call__(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)


class _IntactImage:
    """The PIL context manager ``Image.open`` returns in the validation helper (L957)."""

    def load(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _passes_timeout(seconds):
    """``asyncio.timeout(seconds)`` that never trips (``new=`` form)."""

    class _Timeout:
        def __init__(self, value):
            self.deadline = value

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

    return _Timeout(seconds)


class Surface(ExitStack):
    """The filesystem + offload surface the route reads, pinned for ONE leg.

    ``exists`` (L1046), ``read_bytes`` (L1084), ``asyncio.to_thread`` (L1084),
    ``asyncio.timeout`` (L665) and the module's ``time`` stand-in are all opened in one
    ``with`` statement and unwound on exit, so nothing leaks into another leg.  ``post``
    replaces ``httpx.AsyncClient.post`` - the shipped request call inside
    ``_send_detection_request`` - with a counter-backed side effect.
    """

    def __init__(
        self,
        *,
        exists=True,
        read_bytes=_BYTES,
        post=None,
        read_error=None,
        size=MIN_SIZE + 1,
        validate=False,
        image_error=None,
    ):
        super().__init__()
        self.posted = []
        stat = MagicMock()
        stat.st_size = size
        self.enter_context(patch.object(M.Path, "exists", autospec=True, return_value=exists))
        self.enter_context(patch.object(M.Path, "stat", autospec=True, return_value=stat))
        self.enter_context(
            patch.object(
                M.Path, "read_bytes", autospec=True, side_effect=read_error, return_value=read_bytes
            )
        )
        if validate:
            # the shipped validation helper (L921-L976) really runs when a leg asks for it:
            # PIL's open is pinned so the leg controls intact vs corrupt.
            self.enter_context(
                patch.object(
                    M.Image,
                    "open",
                    autospec=True,
                    side_effect=image_error,
                    return_value=None if image_error is not None else _IntactImage(),
                )
            )
        self.enter_context(patch.object(M.asyncio, "to_thread", new=_ToThreadInline()))
        self.enter_context(patch.object(M.asyncio, "timeout", new=_passes_timeout))
        self.enter_context(patch("asyncio.sleep", new=self._sleep))
        if post is not None:
            self.enter_context(
                patch.object(M.httpx.AsyncClient, "post", autospec=True, side_effect=post)
            )
        self.sleeps = []

    async def _sleep(self, seconds):
        self.sleeps.append(seconds)


def session_double(*, camera=True, commit_error=None):
    """An ``AsyncSession`` double: ``add`` records the objects it was given, ``get`` answers
    the camera lookup (L1338), ``commit``/``flush`` are awaitable spies."""
    session = MagicMock(spec=M.AsyncSession)
    session.added = []
    session.add = MagicMock(side_effect=lambda obj: session.added.append(obj))
    session.camera = None if camera is False else MagicMock()
    session.get = AsyncMock(return_value=session.camera)
    session.commit = AsyncMock() if commit_error is None else AsyncMock(side_effect=commit_error)
    session.flush = AsyncMock()
    return session


@pytest.fixture
def client(settings):
    """A REAL ``DetectorClient(max_retries=2)`` - the shipped ``__init__`` runs, so the retry
    loop, the threshold table and the explicit timeout under test are production code."""
    instance = M.DetectorClient(max_retries=2)
    assert instance._max_retries == 2
    assert instance._detector_type == "yolo26"
    assert instance._confidence_threshold == 0.5
    return instance


@pytest.fixture(autouse=True)
def breaker(client):
    """The client's circuit breaker replaced (``new=``) by a pass-through double.

    Shipped behaviour kept for the legs of THIS group: ``allow_call`` says yes and ``call``
    invokes the callable with the shipped keyword arguments (L1129-L1135), which is what lets
    a leg pin those keywords - the ``camera_id=camera_id`` keyword there is an occurrence twin
    of this group's keys.  ``state.value`` answers the two places that report it.
    """
    double = MagicMock()
    double.state = MagicMock()
    double.state.value = "closed"
    double.allow_call = AsyncMock(return_value=True)

    async def _call(fn, *args, **kwargs):
        return await fn(*args, **kwargs)

    double.call = AsyncMock(side_effect=_call)
    with patch.object(client, "_circuit_breaker", new=double):
        yield double


def exact(rec, **expected) -> None:
    """The record carries EXACTLY the shipped extra fields, with the shipped values."""
    assert fields(rec) == expected, (rec.lineno, fields(rec), expected)


# --------------------------------------------------------------------------- legs
# The persist + telemetry tail: L1311-L1334


async def test_every_stored_detection_is_added_counted_and_logged(
    client, caplog, clock, metrics, envelope
):
    """L1311-L1322 + L1374-L1386 (m408, m410-m421, m435-
    m437 twins, m458, m462, m466-m470, m472-m487): the two items above the threshold each
    become ONE ``session.add`` of the shipped ``Detection`` with the shipped fields, are
    counted once by class and once for confidence, and log the shipped per-detection DEBUG -
    and the run's whole record sequence is the shipped six."""
    clock.script = [1000.0, 1000.0, 1000.0, 1001.5]
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_PERSISTS)):
        _, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None

    assert [type(r).__name__ for r in ses.added] == ["Detection", "Detection"]
    stored = ses.added[0]
    assert (stored.camera_id, stored.file_path, stored.object_type) == (_CAM, _IMAGE_PATH, "person")
    assert stored.confidence == 0.95
    assert (stored.bbox_x, stored.bbox_y, stored.bbox_width, stored.bbox_height) == (
        100,
        150,
        200,
        300,
    )
    assert stored.media_type == "image"
    assert stored.detected_at is ses.added[1].detected_at
    assert ses.added[1].object_type == "car"
    assert [c.args for c in metrics["record_detection_by_class"].call_args_list] == [
        ("person",),
        ("car",),
    ]
    assert [c.args for c in metrics["observe_detection_confidence"].call_args_list] == [
        (0.95,),
        (0.88,),
    ]
    assert metrics["record_detection_processed"].call_args.kwargs == {"count": 2}
    assert metrics["record_pipeline_error"].call_args_list == []

    assert sent(recs) == [
        (logging.DEBUG, 1060),
        (logging.DEBUG, 1319),
        (logging.DEBUG, 1319),
        (logging.DEBUG, 1195),
        (logging.DEBUG, 1341),
        (logging.INFO, 1386),
    ]
    assert [r.getMessage() for r in at(recs, 1319, logging.DEBUG)] == [
        "Created detection: person (confidence: 0.95, bbox: [100, 150, 200, 300])",
        "Created detection: car (confidence: 0.88, bbox: [50, 60, 70, 80])",
    ]
    for rec in at(recs, 1319, logging.DEBUG):
        assert fields(rec) == {}, (rec.lineno, fields(rec))
    info = one(recs, 1386, logging.INFO)
    assert info.msg == "Stored detections"
    exact(
        info,
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        detection_count=2,
        duration_ms=1500,
    )
    assert info.trace_id == envelope["trace_id"]
    assert has_traceback(info) is False
    # L641-L646: the request span is opened with EXACTLY the shipped keyword set - the
    # ``camera_id=camera_id`` keyword there is an occurrence twin of m458/m462.
    span_call = envelope["trace_span"].call_args
    assert span_call.args == ("yolo26_detection_request",)
    assert span_call.kwargs == {
        "camera_id": _CAM,
        "image_path": _IMAGE_PATH,
        "image_size_bytes": len(_BYTES),
    }


async def test_the_class_less_item_is_counted_as_unknown_but_stored_as_none(
    client, caplog, clock, metrics
):
    """L1315 twins vs L1187/L1286 (m410-m418, m419, m486-
    m495 twins): an item with NO ``"class"`` key is counted as ``"unknown"`` by the class
    counter while the stored row's ``object_type`` is None - and the per-detection DEBUG
    prints that None."""
    clock.script = [1000.0, 1000.0, 1000.0, 1001.25]
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_UNKNOWN)):
        _, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None
    assert len(ses.added) == 1
    assert ses.added[0].object_type is None
    assert [c.args for c in metrics["record_detection_by_class"].call_args_list] == [("unknown",)]
    assert [c.args for c in metrics["observe_detection_confidence"].call_args_list] == [(0.9,)]
    assert sent(recs) == [
        (logging.DEBUG, 1060),
        (logging.DEBUG, 1319),
        (logging.DEBUG, 1341),
        (logging.INFO, 1386),
    ]
    assert recs[1].getMessage() == "Created detection: None (confidence: 0.90, bbox: [2, 3, 4, 5])"
    assert one(recs, 1386, logging.INFO).msg == "Stored detections"


async def test_a_detection_that_raises_is_dropped_counted_once_and_the_loop_continues(
    client, caplog, clock, metrics
):
    """L1324-L1334 (m422-m438 plus the L448<->L1330 and L1331<->L1438 twins): an item whose
    confidence is a dict makes L1194 raise TypeError; the shipped arm logs ONE ERROR carrying
    the shipped sentence, the sanitized error and a REAL traceback, reports the pipeline error
    once and CONTINUES - so the next item is still stored and counted."""
    raised = TypeError("'<' not supported between instances of 'dict' and 'float'")
    clock.script = [1000.0, 1000.0, 1000.0, 1001.5]
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_RAISES_FIRST)):
        _, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None
    assert [d.object_type for d in ses.added] == ["person"]

    error = one(recs, 1328, logging.ERROR)
    assert error.msg == "Error processing detection data"
    assert fields(error) == {"error": M.sanitize_error(raised)}
    assert has_traceback(error)
    assert error.exc_info[1].args == raised.args
    assert [c.args for c in metrics["record_pipeline_error"].call_args_list] == [
        ("detection_processing_error",)
    ]
    assert sent(recs) == [
        (logging.DEBUG, 1060),
        (logging.ERROR, 1328),
        (logging.DEBUG, 1319),
        (logging.DEBUG, 1341),
        (logging.INFO, 1386),
    ]
    assert [c.args for c in metrics["record_detection_by_class"].call_args_list] == [("person",)]


async def test_the_broken_item_alone_still_produces_the_no_detections_debug(
    client, caplog, clock, metrics
):
    """L1388-L1395 (m488-m497 and their cross-module twins): with NOTHING stored the run
    logs the shipped no-detections DEBUG with EXACTLY three fields and no traceback; the
    stored-detections INFO never runs."""
    clock.script = [1000.0, 1000.0, 1000.0, 1000.5]
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_RAISES_ONLY)):
        value, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None and value == []
    assert ses.added == []
    assert sent(recs) == [
        (logging.DEBUG, 1060),
        (logging.ERROR, 1328),
        (logging.DEBUG, 1341),
        (logging.DEBUG, 1388),
    ]
    debug = one(recs, 1388, logging.DEBUG)
    assert debug.getMessage() == f"No detections above threshold for {_IMAGE_PATH}"
    exact(debug, camera_id=_CAM, file_path=_IMAGE_PATH, duration_ms=500)
    assert has_traceback(debug) is False
    assert metrics["record_detection_processed"].call_args_list == []
    assert [c.args for c in metrics["record_pipeline_error"].call_args_list] == [
        ("detection_processing_error",)
    ]


async def test_the_only_sub_threshold_run_logs_the_filtered_debug_and_no_summary_info(
    client, caplog, clock, metrics
):
    """L1194-L1201 (m438's first continue twin) + L1388: the filtered item's DEBUG names the
    class and both numbers, ``record_detection_filtered`` runs once, ``continue`` skips the
    whole persist block - nothing is added, no baseline, no class counter - and the run ends
    on the no-detections DEBUG."""
    clock.script = [1000.0, 1000.0, 1000.0, 1000.25]
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_ONLY_FILTERED)):
        value, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None and value == []
    assert ses.added == []
    assert len(metrics["record_detection_filtered"].call_args_list) == 2
    assert metrics["record_detection_by_class"].call_args_list == []
    assert metrics["observe_detection_confidence"].call_args_list == []
    assert sent(recs) == [
        (logging.DEBUG, 1060),
        (logging.DEBUG, 1195),
        (logging.DEBUG, 1195),
        (logging.DEBUG, 1341),
        (logging.DEBUG, 1388),
    ]
    assert [r.getMessage() for r in at(recs, 1195, logging.DEBUG)] == [
        "Filtering out detection with low confidence: moth (0.40 < 0.50)",
        "Filtering out detection with low confidence: unknown (0.30 < 0.50)",
    ]
    exact(
        one(recs, 1388, logging.DEBUG),
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        duration_ms=250,
    )
    assert metrics["record_pipeline_error"].call_args_list == []
    assert metrics["record_detection_processed"].call_args_list == []


# The camera bookkeeping + baseline block: L1336-L1368


async def test_the_camera_debug_names_the_run_timestamp_and_its_two_fields(
    client, caplog, clock, baseline_service
):
    """L1338-L1344 (m445-m452 plus every L1343 twin): the camera row's ``last_seen_at``
    becomes the run's timestamp and the DEBUG prints it twice - in the message and in the
    ISO field - with EXACTLY two extra fields."""
    clock.script = [1000.0, 1000.0, 1000.0, 1001.0]
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_PERSISTS)):
        _, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None
    stamp = ses.added[0].detected_at
    assert ses.added[1].detected_at is stamp
    assert ses.camera.last_seen_at is stamp
    debug = one(recs, 1341, logging.DEBUG)
    assert debug.getMessage() == f"Updated camera {_CAM} last_seen_at to {stamp}"
    exact(debug, camera_id=_CAM, last_seen_at=stamp.isoformat())
    assert has_traceback(debug) is False


async def test_a_missing_camera_row_stores_the_detections_without_the_camera_debug(
    client, caplog, clock
):
    """L1339 (the ``if camera:`` guard, twin of the L1342/L1343 records): with no camera row
    the detections are still stored and committed and the camera DEBUG never runs - the
    summary INFO is the only tail record."""
    clock.script = [1000.0, 1000.0, 1000.0, 1001.0]
    ses = session_double(camera=False)
    with Surface(validate=True, post=responds(_BODY_PERSISTS)):
        _, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None and len(ses.added) == 2
    assert sent(recs) == [
        (logging.DEBUG, 1060),
        (logging.DEBUG, 1319),
        (logging.DEBUG, 1319),
        (logging.DEBUG, 1195),
        (logging.INFO, 1386),
    ]
    assert ses.commit.await_count == 1
    assert ses.flush.await_count == 2


async def test_the_baseline_runs_once_per_class_with_the_shipped_four_keywords(
    client, caplog, clock, baseline_service
):
    """L1347-L1368 (m455-m465, m458/m462's four L643/L1133/L1282/L1361 twins): two classes
    mean two ``update_baseline`` awaits, each with the shipped camera, class, the FIRST
    detection's timestamp and this session, one flush after them and exactly one commit."""
    clock.script = [1000.0, 1000.0, 1000.0, 1001.0]
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_PERSISTS)):
        await win(caplog, lambda: run(client, ses))
    awaited = baseline_service.update_baseline.await_args_list
    assert {c.kwargs["detection_class"] for c in awaited} == {"person", "car"}
    for call in awaited:
        assert call.kwargs["camera_id"] == _CAM
        assert call.kwargs["timestamp"] is ses.added[0].detected_at
        assert call.kwargs["session"] is ses
        assert call.kwargs["detection_class"] in {"person", "car"}
    assert ses.flush.await_count == 2
    assert ses.commit.await_count == 1


async def test_a_class_less_item_never_reaches_the_baseline_update(
    client, caplog, clock, baseline_service
):
    """L1355 (m455 ``is not None`` -> ``is None``): the ONLY non-None class is "car", so
    exactly one baseline await happens - with ``detection_class="car"``.  The inverted
    predicate would instead pass the class-less item's None and drop "car"."""
    clock.script = [1000.0, 1000.0, 1000.0, 1001.0]
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_NONE_CLASS_ONE)):
        await win(caplog, lambda: run(client, ses))
    assert [d.object_type for d in ses.added] == [None, "car"]
    awaited = baseline_service.update_baseline.await_args_list
    assert [c.kwargs["detection_class"] for c in awaited] == ["car"]
    assert awaited[0].kwargs["camera_id"] == _CAM
    assert awaited[0].kwargs["session"] is ses


async def test_two_class_less_items_update_the_baseline_exactly_once(
    client, caplog, clock, baseline_service
):
    """L1352-L1356 (the set comprehension that m455's inverted predicate would turn into
    ``{None}`` -> one call with ``detection_class=None``): two class-less items are ONE
    unique non-None class set, so the shipped code performs NO baseline update at all."""
    clock.script = [1000.0, 1000.0, 1000.0, 1001.0]
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_CLASSLESS_TWO)):
        await win(caplog, lambda: run(client, ses))
    assert [d.object_type for d in ses.added] == [None, None]
    assert baseline_service.update_baseline.await_args_list == []
    assert ses.flush.await_count == 0
    assert ses.commit.await_count == 1


async def test_the_baseline_timestamp_is_the_first_detection_s(
    client, caplog, clock, baseline_service
):
    """L1358 (m456): both baseline awaits carry ``detections[0].detected_at`` - the FIRST
    stored row's timestamp - even for the class that arrived second."""
    clock.script = [1000.0, 1000.0, 1000.0, 1001.0]
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_PERSISTS)):
        await win(caplog, lambda: run(client, ses))
    awaited = baseline_service.update_baseline.await_args_list
    assert len(awaited) == 2
    car_call = next(c for c in awaited if c.kwargs["detection_class"] == "car")
    assert car_call.kwargs["timestamp"] is ses.added[0].detected_at


# The seven ``continue`` statements of m438 + the bbox branch: L1203-L1278


async def test_the_two_malformed_bboxes_are_rejected_back_to_back(client, caplog, clock, metrics):
    """L1208-L1209 and L1220-L1221 (m438's second and third continue twins, plus the shipped
    sentences): a dict bbox WITHOUT the four names and a bbox that is neither dict nor a
    4-item list are each rejected with their OWN warning, and the loop still stores the item
    that follows - so a ``break`` at either line drops the other warning and the store."""
    clock.script = [1000.0, 1000.0, 1000.0, 1001.0]
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_TWO_BAD_BBOX)):
        _, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None
    assert [d.object_type for d in ses.added] == ["person"]
    assert sent(recs) == [
        (logging.DEBUG, 1060),
        (logging.WARNING, 1208),
        (logging.WARNING, 1220),
        (logging.DEBUG, 1319),
        (logging.DEBUG, 1341),
        (logging.INFO, 1386),
    ]
    assert (
        one(recs, 1208, logging.WARNING).getMessage()
        == "Invalid bbox dict format: {'x': 1, 'y': 2}"
    )
    assert one(recs, 1220, logging.WARNING).getMessage() == (
        "Invalid bbox format: ['n', 'o', 't', 'a', 'box']"
    )
    for rec in (one(recs, 1208, logging.WARNING), one(recs, 1220, logging.WARNING)):
        assert fields(rec) == {}
    assert metrics["record_detection_filtered"].call_args_list == []


async def test_a_bbox_outside_the_image_is_skipped_before_clamping(client, caplog, clock):
    """L1226-L1240 (m438's fourth continue twin): a bbox past the right/bottom edge is
    skipped with the shipped four-part sentence naming the image size and class, and the run
    continues to the next item."""
    clock.script = [1000.0, 1000.0, 1000.0, 1001.0]
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_OUTSIDE)):
        _, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None
    assert [d.object_type for d in ses.added] == ["car"]
    assert sent(recs) == [
        (logging.DEBUG, 1060),
        (logging.WARNING, 1234),
        (logging.DEBUG, 1319),
        (logging.DEBUG, 1341),
        (logging.INFO, 1386),
    ]
    assert one(recs, 1234, logging.WARNING).getMessage() == (
        "Skipping detection with bbox completely outside image: "
        "bbox=(900, 900, 20, 20), image=(1280x720), class=person"
    )


async def test_a_bbox_that_collapses_under_clamping_is_skipped(client, caplog, clock):
    """L1256-L1262 (m438's fifth continue twin): a box whose clamped width becomes 0 is
    dropped with the shipped original/clamped/image/class sentence."""
    clock.script = [1000.0, 1000.0, 1000.0, 1001.0]
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_TOO_SMALL)):
        _, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None
    assert [d.object_type for d in ses.added] == ["car"]
    assert sent(recs) == [
        (logging.DEBUG, 1060),
        (logging.WARNING, 1257),
        (logging.DEBUG, 1319),
        (logging.DEBUG, 1341),
        (logging.INFO, 1386),
    ]
    assert one(recs, 1257, logging.WARNING).getMessage() == (
        "Skipping detection with bbox too small after clamping: "
        "original=(100, 20, -50, 40), clamped=(100, 20, -50, 40), "
        "image=(1280x720), class=person"
    )


async def test_a_clamped_bbox_is_reported_once_and_still_stored(client, caplog, clock):
    """L1264-L1271 (the clamped WARNING, a neighbour of the m438 twins): coordinates past the
    right/bottom edge are clamped to the image, reported once with the shipped sentence, and
    the clamped box is what lands on the stored row."""
    clock.script = [1000.0, 1000.0, 1000.0, 1001.0]
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_CLAMPED)):
        _, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None
    stored = ses.added[0]
    assert (stored.bbox_x, stored.bbox_y, stored.bbox_width, stored.bbox_height) == (
        20,
        30,
        1260,
        690,
    )
    assert [d.object_type for d in ses.added] == ["person"]
    assert sent(recs) == [
        (logging.DEBUG, 1060),
        (logging.WARNING, 1266),
        (logging.DEBUG, 1319),
        (logging.DEBUG, 1341),
        (logging.INFO, 1386),
    ]
    assert one(recs, 1266, logging.WARNING).getMessage() == (
        "Clamped invalid bbox coordinates: original=(20, 30, 1400, 900), "
        "clamped=(20, 30, 1260, 690), image=(1280x720), class=person"
    )
    assert one(recs, 1319, logging.DEBUG).getMessage() == (
        "Created detection: person (confidence: 0.90, bbox: [20, 30, 1400, 900])"
    )


async def test_a_non_positive_bbox_without_dimensions_is_skipped(client, caplog, clock):
    """L1272-L1278 (m438's sixth continue twin): with NO image dimensions the clamp branch is
    skipped entirely and a negative width is rejected with the shipped sentence."""
    clock.script = [1000.0, 1000.0, 1000.0, 1001.0]
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_NO_DIMS)):
        _, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None
    assert [d.object_type for d in ses.added] == ["car"]
    assert ses.added[0].video_width is None
    assert sent(recs) == [
        (logging.DEBUG, 1060),
        (logging.WARNING, 1274),
        (logging.DEBUG, 1319),
        (logging.DEBUG, 1341),
        (logging.INFO, 1386),
    ]
    assert one(recs, 1274, logging.WARNING).getMessage() == (
        "Skipping detection with non-positive bbox dimensions: bbox=(4, 5, -3, 6), class=person"
    )


# The outer arms of detect_objects that still carry dc13 twins: L1045-L1108, L1398-L1443


async def test_a_missing_image_file_reports_the_camera_and_file_path(client, caplog, metrics):
    """L1045-L1052 (the L1049 twin of m473/m474/m492/m493): the ERROR names the camera and
    the path and nothing else, the pipeline error is reported once, and NO record from the
    request path follows."""
    ses = session_double()
    with Surface(validate=True, exists=False):
        value, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None and value == []
    assert sent(recs) == [(logging.ERROR, 1047)]
    error = one(recs, 1047, logging.ERROR)
    assert error.msg == "Image file not found"
    exact(error, camera_id=_CAM, file_path=_IMAGE_PATH)
    assert [c.args for c in metrics["record_pipeline_error"].call_args_list] == [
        ("file_not_found",)
    ]


async def test_the_request_debug_is_the_first_record_and_names_the_camera(client, caplog, clock):
    """L1060-L1063 (the L1062 twin): exactly two records for a run that stores nothing - the
    pre-request DEBUG and the summary DEBUG - and the first carries the two shipped fields."""
    clock.script = [1000.0, 1000.0, 1000.0, 1000.0]
    ses = session_double()
    with Surface(validate=True, post=responds(body([]))):
        value, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None and value == []
    assert sent(recs) == [
        (logging.DEBUG, 1060),
        (logging.DEBUG, 1341),
        (logging.DEBUG, 1388),
    ]
    debug = one(recs, 1060, logging.DEBUG)
    assert debug.getMessage() == f"Sending detection request for {_IMAGE_PATH}"
    exact(debug, camera_id=_CAM, file_path=_IMAGE_PATH)
    exact(
        one(recs, 1388, logging.DEBUG),
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        duration_ms=0,
    )


async def test_the_circuit_breaker_call_is_given_the_shipped_frame(client, caplog, clock, breaker):
    """L1129-L1135 (the L1133 twin of m458/m462): the breaker's ``call`` receives the shipped
    callable plus the four shipped keyword arguments - the frame bytes, the file NAME, the
    camera and the full path - and the response is still persisted."""
    clock.script = [1000.0, 1000.0, 1000.0, 1000.0]
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_UNKNOWN)):
        await win(caplog, lambda: run(client, ses))
    called = breaker.call.await_args
    assert called.args[0].__name__ == "_send_detection_request"
    assert called.args[1:] == ()
    assert called.kwargs["camera_id"] == _CAM
    assert called.kwargs["image_path"] == _IMAGE_PATH
    assert called.kwargs["image_name"] == "snap-0412.jpg"
    assert called.kwargs["image_data"] == _BYTES
    assert len(ses.added) == 1


async def test_an_open_breaker_rejects_before_the_request_is_made(client, caplog, breaker, metrics):
    """L1068-L1081 (the L1073/L1074 twins): when ``allow_call`` says no, the shipped WARNING
    carries the detector type, camera, path and state, the pipeline error is reported and the
    call is never attempted."""
    breaker.allow_call = AsyncMock(return_value=False)
    posted = []
    ses = session_double()
    with Surface(validate=True, post=posted_responds(posted, _BODY_PERSISTS)):
        value, err, recs = await win(caplog, lambda: run(client, ses))
    assert posted == []
    assert isinstance(err, M.DetectorUnavailableError) and value is None
    assert sent(recs) == [(logging.DEBUG, 1060), (logging.WARNING, 1069)]
    warning = one(recs, 1069, logging.WARNING)
    assert warning.getMessage() == ("Circuit breaker open for yolo26, rejecting detection request")
    exact(
        warning,
        detector_type="yolo26",
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        circuit_state="closed",
    )
    assert [c.args for c in metrics["record_pipeline_error"].call_args_list] == [
        ("circuit_breaker_open",)
    ]


async def test_a_buffered_frame_reports_the_camera_bytes_and_count(client, caplog, clock):
    """L1098-L1108 (the L1104 twin of m473/m474/m492/m493): with a frame buffer installed the
    shipped DEBUG carries EXACTLY the three shipped fields - camera, byte count, buffer
    count - and the frame really was handed to the buffer."""
    clock.script = [1000.0, 1000.0, 1000.0, 1000.0]
    frame_buffer = _Frame(count=7)
    instance = M.DetectorClient(max_retries=2, frame_buffer=frame_buffer)
    double = MagicMock()
    double.state = MagicMock()
    double.state.value = "closed"
    double.allow_call = AsyncMock(return_value=True)

    async def _call(fn, *args, **kwargs):
        return await fn(*args, **kwargs)

    double.call = AsyncMock(side_effect=_call)
    ses = session_double()
    with (
        patch.object(instance, "_circuit_breaker", new=double),
        Surface(validate=True, post=responds(body([]))),
    ):
        _, err, recs = await win(caplog, lambda: run(instance, ses))
    assert err is None
    assert frame_buffer.added == [(_CAM, len(_BYTES))]
    assert sent(recs) == [
        (logging.DEBUG, 1060),
        (logging.DEBUG, 1101),
        (logging.DEBUG, 1341),
        (logging.DEBUG, 1388),
    ]
    debug = one(recs, 1101, logging.DEBUG)
    assert debug.getMessage() == f"Buffered frame for camera {_CAM}"
    exact(debug, camera_id=_CAM, frame_size_bytes=len(_BYTES), buffer_count=7)


# The request-arm twins: L692-L908 (reached through detect_objects, so the L643 twin of
# m458/m462 is exercised in the same window)


async def _exhaust(caplog, client, ses, error):
    """One ``detect_objects`` run whose detector POST always raises ``error``."""
    with Surface(validate=True, post=failing(error)):
        return await win(caplog, lambda: run(client, ses))


async def test_a_connection_error_retries_once_then_reports_the_camera_and_path(
    client, caplog, clock, metrics
):
    """L688-L717 (the L696/L697 and L711/L712 twins + the L716 exc_info twin): the retry
    WARNING and the exhaustion ERROR are the only records, their fields are exactly the
    shipped ones, the backoff is the shipped 2**attempt, and only the final record carries a
    traceback.  The span opened for the request is the shipped keyword set (L641-L646)."""
    clock.script = [1000.0, 1000.0, 1000.0, 1000.0]
    ses = session_double()
    _, err, recs = await _exhaust(caplog, client, ses, httpx.ConnectError("connection refused"))
    assert (
        isinstance(err, M.DetectorUnavailableError)
        and err.original_error.args[0] == "connection refused"
    )
    assert sent(recs) == [(logging.DEBUG, 1060), (logging.WARNING, 692), (logging.ERROR, 707)]
    warning = one(recs, 692, logging.WARNING)
    assert warning.msg == "Detector connection error, retrying"
    exact(
        warning,
        detector_type="yolo26",
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        attempt=1,
        max_retries=2,
        retry_delay=1,
        error="connection refused",
    )
    assert has_traceback(warning) is False
    error = one(recs, 707, logging.ERROR)
    assert error.msg == "Detector connection error after all attempts"
    exact(
        error,
        detector_type="yolo26",
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        attempts=2,
        error="connection refused",
    )
    assert has_traceback(error)
    assert [c.args for c in metrics["record_pipeline_error"].call_args_list] == [
        ("yolo26_connection_error",)
    ]


async def test_a_timeout_error_is_retried_and_reported(client, caplog, clock):
    """L719-L748 (the L727/L728 and L742/L743 twins + L747 exc_info)."""
    clock.script = [1000.0, 1000.0, 1000.0, 1000.0]
    ses = session_double()
    _, err, recs = await _exhaust(
        caplog, client, ses, httpx.TimeoutException("read deadline exceeded")
    )
    assert isinstance(err, M.DetectorUnavailableError)
    assert sent(recs) == [(logging.DEBUG, 1060), (logging.WARNING, 723), (logging.ERROR, 738)]
    warning = one(recs, 723, logging.WARNING)
    assert warning.msg == "Detector timeout, retrying"
    exact(
        warning,
        detector_type="yolo26",
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        attempt=1,
        max_retries=2,
        retry_delay=1,
        error="read deadline exceeded",
    )
    error = one(recs, 738, logging.ERROR)
    assert error.msg == "Detector timeout after all attempts"
    exact(
        error,
        detector_type="yolo26",
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        attempts=2,
        error="read deadline exceeded",
    )
    assert has_traceback(error)


async def test_an_asyncio_timeout_reports_the_explicit_window_twice(client, caplog, clock):
    """L750-L782 (the L760/L761 and L776/L777 twins + L781 exc_info): both sentences name the
    shipped explicit timeout - the read timeout plus the connect timeout - and its field."""
    clock.script = [1000.0, 1000.0, 1000.0, 1000.0]
    ses = session_double()
    _, err, recs = await _exhaust(caplog, client, ses, TimeoutError("tripped"))
    assert isinstance(err, M.DetectorUnavailableError)
    assert sent(recs) == [(logging.DEBUG, 1060), (logging.WARNING, 755), (logging.ERROR, 771)]
    warning = one(recs, 755, logging.WARNING)
    assert warning.getMessage() == (
        "Detector asyncio timeout (attempt 1/2), retrying in 1s: request timed out after 65.0s"
    )
    exact(
        warning,
        detector_type="yolo26",
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        attempt=1,
        max_retries=2,
        retry_delay=1,
        explicit_timeout=65.0,
    )
    error = one(recs, 771, logging.ERROR)
    assert error.getMessage() == (
        "Detector asyncio timeout after 2 attempts: request timed out after 65.0s"
    )
    exact(
        error,
        detector_type="yolo26",
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        attempts=2,
        explicit_timeout=65.0,
    )
    assert has_traceback(error)


async def test_a_server_error_is_retried_and_reported_with_its_status(client, caplog, clock):
    """L784-L817 (the L796/L797 and L811/L812 twins + L816 exc_info)."""
    clock.script = [1000.0, 1000.0, 1000.0, 1000.0]
    ses = session_double()
    _, err, recs = await _exhaust(caplog, client, ses, _status_error("detector blew up", 502))
    assert isinstance(err, M.DetectorUnavailableError)
    assert sent(recs) == [(logging.DEBUG, 1060), (logging.WARNING, 792), (logging.ERROR, 807)]
    warning = one(recs, 792, logging.WARNING)
    assert warning.msg == "Detector server error, retrying"
    exact(
        warning,
        detector_type="yolo26",
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        status_code=502,
        attempt=1,
        max_retries=2,
        retry_delay=1,
    )
    error = one(recs, 807, logging.ERROR)
    assert error.msg == "Detector server error after all attempts"
    exact(
        error,
        detector_type="yolo26",
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        status_code=502,
        attempts=2,
    )
    assert has_traceback(error)


async def test_a_client_error_is_logged_once_without_traceback_and_returns_empty(
    client, caplog, clock, metrics
):
    """L818-L843 (the L834/L835 twins): a 4xx is NOT retried - one ERROR carrying the
    rejected detail and NO traceback - and the ValueError it raises is swallowed by L1399, so
    the run returns an empty list with no summary record at all."""
    clock.script = [1000.0, 1000.0, 1000.0, 1000.0]
    ses = session_double()
    _, err, recs = await _exhaust(
        caplog,
        client,
        ses,
        _status_error("rejected", 400, body={"detail": "payload rejected"}),
    )
    assert err is None and ses.added == []
    assert sent(recs) == [(logging.DEBUG, 1060), (logging.ERROR, 830)]
    error = one(recs, 830, logging.ERROR)
    assert error.msg == "Detector client error"
    exact(
        error,
        detector_type="yolo26",
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        status_code=400,
        error_detail="payload rejected",
    )
    assert has_traceback(error) is False
    assert [c.args for c in metrics["record_pipeline_error"].call_args_list] == [
        ("yolo26_client_error",)
    ]


async def test_an_unparseable_response_is_retried_and_reported(client, caplog, clock):
    """L845-L876 (the L856/L857 and L871/L872 twins + L875 exc_info): both sentences carry the
    SANITIZED decode error."""
    clock.script = [1000.0, 1000.0, 1000.0, 1000.0]
    raised = ValueError("Expecting value: line 1 column 1 (char 0)")
    ses = session_double()
    _, err, recs = await _exhaust(caplog, client, ses, raised)
    assert isinstance(err, M.DetectorUnavailableError)
    assert sent(recs) == [(logging.DEBUG, 1060), (logging.WARNING, 851), (logging.ERROR, 866)]
    sanitized = M.sanitize_error(raised)
    warning = one(recs, 851, logging.WARNING)
    assert warning.getMessage() == (
        f"Detector JSON/value error (attempt 1/2), retrying in 1s: {sanitized}"
    )
    exact(
        warning,
        detector_type="yolo26",
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        attempt=1,
        max_retries=2,
        retry_delay=1,
    )
    error = one(recs, 866, logging.ERROR)
    assert error.getMessage() == f"Detector JSON/value error after 2 attempts: {sanitized}"
    exact(
        error,
        detector_type="yolo26",
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        attempts=2,
    )
    assert has_traceback(error)


async def test_an_unexpected_error_is_retried_and_reported(client, caplog, clock):
    """L878-L909 (the L888/L889 and L903/L904 twins + L908 exc_info)."""
    clock.script = [1000.0, 1000.0, 1000.0, 1000.0]
    raised = RuntimeError("client is closed")
    ses = session_double()
    _, err, recs = await _exhaust(caplog, client, ses, raised)
    assert isinstance(err, M.DetectorUnavailableError)
    assert sent(recs) == [(logging.DEBUG, 1060), (logging.WARNING, 884), (logging.ERROR, 899)]
    sanitized = M.sanitize_error(raised)
    warning = one(recs, 884, logging.WARNING)
    assert warning.msg == "Unexpected detector error, retrying"
    exact(
        warning,
        detector_type="yolo26",
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        attempt=1,
        max_retries=2,
        retry_delay=1,
        error=sanitized,
    )
    error = one(recs, 899, logging.ERROR)
    assert error.msg == "Unexpected detector error after all attempts"
    exact(
        error,
        detector_type="yolo26",
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        attempts=2,
        error=sanitized,
    )
    assert has_traceback(error)


# The two outer arms that still carry dc13 twins: L1402-L1420 and L1424-L1443


async def test_a_tripped_breaker_error_is_reported_with_its_duration(
    client, caplog, clock, breaker, metrics
):
    """L1402-L1420 (the L1410/L1411 twins, the L1412 twin of m479/m480/m496/m497 and the
    L1404 twin of m466-m470): the breaker raising CircuitBreakerError produces ONE WARNING
    carrying the shipped five-plus-one fields with the run's duration, the pipeline error, and
    a DetectorUnavailableError out of the call."""
    clock.script = [1000.0, 1000.0, 1001.0]
    tripped = M.CircuitBreakerError("yolo26", "open")
    breaker.call = AsyncMock(side_effect=tripped)
    ses = session_double()
    with Surface(validate=True, post=responds(_BODY_PERSISTS)):
        value, err, recs = await win(caplog, lambda: run(client, ses))
    assert value is None and isinstance(err, M.DetectorUnavailableError)
    assert ses.added == []
    assert sent(recs) == [(logging.DEBUG, 1060), (logging.WARNING, 1406)]
    warning = one(recs, 1406, logging.WARNING)
    assert warning.getMessage() == "Circuit breaker open for yolo26"
    exact(
        warning,
        detector_type="yolo26",
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        duration_ms=1000,
        circuit_state="closed",
        error=str(tripped),
    )
    assert has_traceback(warning) is False
    assert [c.args for c in metrics["record_pipeline_error"].call_args_list] == [
        ("circuit_breaker_open",)
    ]


async def test_a_read_failure_becomes_the_object_detection_error(client, caplog, clock, metrics):
    """L1424-L1443 (the L1434 twin of m473/m492, the L1435 twin of m479/m496, the L1428 twin
    of m466-m470 and the L1438 exc_info twin): an OSError off the frame read produces ONE
    ERROR with the shipped four fields and a traceback, the typed pipeline error, and a
    DetectorUnavailableError carrying the original."""
    clock.script = [1000.0, 1001.0]
    raised = OSError("disk read failed")
    ses = session_double()
    with Surface(validate=True, read_error=raised):
        value, err, recs = await win(caplog, lambda: run(client, ses))
    assert value is None and isinstance(err, M.DetectorUnavailableError)
    assert err.original_error is raised
    assert sent(recs) == [(logging.DEBUG, 1060), (logging.ERROR, 1430)]
    error = one(recs, 1430, logging.ERROR)
    assert error.msg == "Unexpected error during object detection"
    exact(
        error,
        detector_type="yolo26",
        camera_id=_CAM,
        duration_ms=1000,
        error=M.sanitize_error(raised),
    )
    assert has_traceback(error)
    assert [c.args for c in metrics["record_pipeline_error"].call_args_list] == [
        ("yolo26_unexpected_error",)
    ]


# ``health_check`` twins: L430-L451 (the L433/L440/L449 exc_info members and the L448 twin of
# m423/m426/m431-m433 run here, where a dropped ``extra=`` or a mutated field is observable)


def _health(client, error):
    client._health_http_client = MagicMock()
    client._health_http_client.get = AsyncMock(side_effect=error if error is not None else None)


async def test_a_health_connect_failure_reports_the_stringified_error(client, caplog):
    """L429-L435: the WARNING carries ONLY the stringified failure (the file-path twin family
    never touches this call) and it does carry a traceback."""
    _health(client, httpx.ConnectError("no route to host"))
    value, err, recs = await win(caplog, lambda: client.health_check())
    assert err is None and value is False
    assert sent(recs) == [(logging.WARNING, 430)]
    warning = one(recs, 430, logging.WARNING)
    assert warning.msg == "Detector health check failed"
    exact(warning, error="no route to host")
    assert has_traceback(warning)


async def test_a_health_status_failure_reports_the_stringified_error(client, caplog):
    """L436-L442: the shipped sentence, the stringified status error and a traceback."""
    _health(client, _status_error("health endpoint unhappy", 503))
    value, err, recs = await win(caplog, lambda: client.health_check())
    assert err is None and value is False
    assert sent(recs) == [(logging.WARNING, 437)]
    warning = one(recs, 437, logging.WARNING)
    assert warning.msg == "Detector health check returned error status"
    exact(warning, error="health endpoint unhappy")
    assert has_traceback(warning)


async def test_an_unexpected_health_failure_reports_the_sanitized_error(client, caplog):
    """L443-L451 (m423/m426/m431-m433's L448 twin and the L449 exc_info twin): the extra key
    is exactly ``"error"``, its value is the SANITIZED message of the real exception, and a
    traceback is attached - the three candidates of this family live on this line, so this is
    where a dropped ``extra=`` (a TypeError swallowed by the arm, losing the record) and a
    renamed key are both caught."""
    raised = ValueError("bad payload at /var/lib/detector/state.json")
    _health(client, raised)
    value, err, recs = await win(caplog, lambda: client.health_check())
    assert err is None and value is False
    assert sent(recs) == [(logging.ERROR, 446)]
    error = one(recs, 446, logging.ERROR)
    assert error.msg == "Unexpected error during detector health check"
    assert fields(error) == {"error": M.sanitize_error(raised)}
    assert error.exc_info[1] is raised
    assert has_traceback(error)


async def test_a_truncated_image_is_rejected_before_the_request(client, caplog, metrics):
    """L943-L953 (the L947/L948 twins of m473-m476/m492-m495) + L1056-L1058: a file below
    ``MIN_DETECTION_IMAGE_SIZE`` is rejected with the shipped four fields, ``invalid_image``
    is reported once, and NO request is ever made - so this WARNING is the run's only record."""
    posted = []
    ses = session_double()
    with Surface(
        validate=True,
        size=MIN_SIZE - 1,
        post=posted_responds(posted, _BODY_PERSISTS),
    ):
        value, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None and value == [] and posted == []
    assert sent(recs) == [(logging.WARNING, 944)]
    warning = one(recs, 944, logging.WARNING)
    assert warning.msg == "Image too small for detection"
    exact(
        warning,
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        file_size=MIN_SIZE - 1,
        min_size=MIN_SIZE,
    )
    assert [c.args for c in metrics["record_pipeline_error"].call_args_list] == [("invalid_image",)]


async def test_a_corrupt_image_is_reported_with_the_camera_and_path(client, caplog, metrics):
    """L963-L969 (the L967 twins): PIL raising OSError produces the shipped corrupt/truncated
    WARNING with exactly the three shipped fields - the raw ``str(e)`` - and the run stops."""
    ses = session_double()
    with Surface(validate=True, image_error=OSError("image file is truncated")):
        value, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None and value == []
    assert sent(recs) == [(logging.WARNING, 965)]
    warning = one(recs, 965, logging.WARNING)
    assert warning.msg == "Image validation failed (corrupt/truncated)"
    exact(
        warning,
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        error="image file is truncated",
    )
    assert has_traceback(warning) is False
    assert [c.args for c in metrics["record_pipeline_error"].call_args_list] == [("invalid_image",)]


async def test_an_unreadable_image_format_is_reported_with_the_sanitized_error(
    client, caplog, metrics
):
    """L970-L976 (the L974 twins): the ValueError arm prints the SANITIZED message, not the
    raw one, and carries no traceback."""
    raised = ValueError("cannot identify image file /export/yard/cam07/snap-0412.jpg")
    ses = session_double()
    with Surface(validate=True, image_error=raised):
        value, err, recs = await win(caplog, lambda: run(client, ses))
    assert err is None and value == []
    assert sent(recs) == [(logging.WARNING, 972)]
    warning = one(recs, 972, logging.WARNING)
    assert warning.msg == "Image validation failed"
    exact(
        warning,
        camera_id=_CAM,
        file_path=_IMAGE_PATH,
        error=M.sanitize_error(raised),
    )
    assert [c.args for c in metrics["record_pipeline_error"].call_args_list] == [("invalid_image",)]
