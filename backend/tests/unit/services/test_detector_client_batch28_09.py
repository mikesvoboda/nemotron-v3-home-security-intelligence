r"""S2 batch-28 lane L8 - ``detector_client`` group dc10 kill battery (60 keys).

Source: ``backend/services/detector_client.py``, md5 ``294c938abe9e37cd0f979f9357982753``.
Manifest: ``/tmp/wp-pw/detector_client/manifest.json`` group
``dc10-detect-preflight-framebuffer-metrics`` (60 KILLABLE keys; keys file
``manifest_groups/dc10-detect-preflight-framebuffer-metrics.keys``, content identical to
``group_09.keys``).  Splice report ``splice-dc10-detect-preflight-framebuffer-metrics.json``:
30 clean / 30 twin / **0 bad** - nothing in this group needs a hand-splice probe.  Candidate
counts below were recomputed with the harness's own matcher (``replay_lib.candidates``)
against this exact source and agree with that report key for key.

What the group owns
===================
The pre-flight, frame-buffering and measurement part of ``DetectorClient.detect_objects``
(def L993, last statement L1443):

* L1031 ``trace_id = get_trace_id()`` - the value reaches the ``Stored detections`` INFO only
  through L1384's ``if trace_id: log_extra["trace_id"] = trace_id`` (m1);
* L1035-L1042 ``add_span_event("frame_capture.start", ...)`` and its L1087 / L1118 / L1143
  siblings - four events, each with a pinned attribute dict (m13/m14/m109/m110/m137/m138);
* L1046-L1052 the missing-file arm: ERROR at L1047 (msg + ``camera_id``/``file_path``),
  ``record_pipeline_error("file_not_found")`` at L1051 and ``return []`` (m18-m31);
* L1056-L1057 the integrity gate: the camera is passed to
  ``_validate_image_for_detection_async`` and a ``False`` reports ``invalid_image`` (m34,
  m37-m39);
* L1060-L1063 the pre-request DEBUG (m40-m47);
* L1068-L1081 the circuit-breaker gate: the rejection WARNING at L1069 with four extras,
  ``circuit_breaker_open`` at L1078 and the raise at L1079-L1080 (m49-m64);
* L1099-L1108 frame buffering: ``add_frame(camera_id, image_data, datetime)`` plus the DEBUG
  at L1101 with ``camera_id`` / ``frame_size_bytes`` / ``buffer_count`` (the count comes from
  ``frame_count(camera_id)``, which m96 blinds) (m86-m96);
* L1111-L1149 the measurement window: ``ai_start_time`` / ``ai_duration`` /
  ``observe_ai_request_duration(detector_type, ai_duration)`` /
  ``int(ai_duration * 1000)`` inside ``inference.duration_ms`` (m123/m124/m144/m145).

Why this file has more legs than the group's line range
=======================================================
The harness reddens EVERY text-matching candidate of a key, so a key whose ``before`` text
also sits in a sibling arm has to have that arm exercised too.  The candidate line sets,
computed with the harness's own matcher against this exact source:

=================================================== ===== ====================================================
``before`` text                                        n  candidate lines (dc10 keys in brackets)
=================================================== ===== ====================================================
``"detector_type": self._detector_type,``             17  [360] 695 [710] 726 [741] 759 [775] 795 [810]
                                                          833 855 [870] 887 [902] [1072] 1409 1433
``"camera_id": camera_id,``                           25  696 [711] 727 [742] 760 [776] 796 [811] 834
                                                          856 [871] 888 [903] 947 967 974 [1049] [1062]
                                                          [1073] [1104] 1343 1379 1391 1410 1434
``"file_path": image_path,``                          20  697 [712] 728 [743] 761 [777] 797 [812] 835
                                                          857 [872] 889 [904] 948 967 974 [1074] 1380
                                                          1392 1411
``"detector.type": self._detector_type,``              3  [1040] [1122] [1147]
``extra={"camera_id": camera_id, "file_path": ...},``   2  [1049] [1062]
``"circuit_state": self._circuit_breaker.state.value``  2  [1075] 1413
``record_pipeline_error("circuit_breaker_open")``       2  [1078] 1405
``f"{self._detector_type} service temporarily ... "``   2  [1080] 1418
=================================================== =====

Every non-bracketed line above is reached by a leg below, and every leg pins the ORDERED
``(levelname, statement lineno)`` fingerprint of its own shipped call sites plus the raw
``record.msg`` and the named ``extra`` attributes of each record it owns, so no occurrence can
sit in while a sibling pretends to be it:

* L360 - ``test_the_client_construction_record_names_the_detector`` (a REAL client is built
  inside the capture window);
* L695/L696/L697 + L710/L711/L712 - ``test_the_connection_arm_retries_once_then_reports``;
* L726/L727/L728 + L741/L742/L743 - ``test_the_timeout_arm_retries_once_then_reports``;
* L759/L760/L761 + L775/L776/L777 - ``test_the_asyncio_timeout_arm_retries_then_reports``;
* L795/L796/L797 + L810/L811/L812 - ``test_the_server_error_arm_retries_then_reports``;
* L833/L834/L835 - ``test_a_client_error_is_reported_once_and_returns_empty``;
* L855/L856/L857 + L870/L871/L872 - ``test_the_json_error_arm_retries_then_reports``;
* L887/L888/L889 + L902/L903/L904 - ``test_the_unexpected_error_arm_retries_then_reports``;
* L947/L948 - ``test_a_truncated_image_is_reported_as_invalid``; L967 -
  ``test_an_unreadable_image_uses_the_oserror_arm``; L974 -
  ``test_an_unreadable_image_uses_the_decode_arm``;
* L1343/L1379/L1380 - ``test_a_stored_detection_logs_the_camera_and_the_stored_summary``;
  L1391/L1392 - ``test_the_empty_result_debug_names_the_camera_and_the_path``;
* L1409/L1410/L1411/L1413 (and the L1405 metric, the L1418 message) -
  ``test_a_call_phase_trip_is_reported_and_reraised``; L1433/L1434 -
  ``test_a_commit_failure_becomes_the_object_detection_error``.

Discipline
----------
* production never bends: the shipped ``detect_objects`` / ``_send_detection_request`` run on
  a REAL ``DetectorClient`` (the construction idiom of the shipped ``test_detector_client.py``
  suite), so the shipped circuit breaker (L336-L344, L1068, L1129), retry loop and
  record-building code are production code.  Patched collaborators are the HTTP transport,
  ``asyncio.sleep``/``asyncio.timeout``, ``get_settings``, ``get_inference_semaphore``,
  ``get_correlation_headers``, the metrics reporters, the telemetry helpers, the frame buffer,
  the session, the filesystem/PIL doubles, the thread offloads and the baseline service -
  every one of them ``autospec=True`` or ``new=`` (WP4.2 ratchet).  There is no import-time
  global spy and no logger/handler mutation: only ``caplog``'s own handler sees the records.
* ``caplog``'s handler is process-wide and production has lazily-logged sites outside every
  leg's ownership (the class-level semaphore DEBUG at L221 fires on the first client of the
  process), so each leg asserts on the statement lines it owns.
* clocks: ``time.monotonic`` and ``time.perf_counter`` are NEVER patched and no wall-clock
  duration is asserted.  The measurement leg replaces only the MODULE's own ``time`` name
  with a stand-in that forwards ``time()`` to the real clock plus a leg-controlled offset
  (``patch.object(M, "time", new=...)``), so the shipped subtraction is pinned exactly while
  every ``duration_ms`` field is still only type-checked.
"""

import ast
import asyncio
import json
import logging
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

import backend.services.detector_client as M
from backend.services.detector_client import MIN_DETECTION_IMAGE_SIZE, DetectorClient

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


# Statement lines owned by a leg (values read straight off the source).  ``record.lineno`` IS
# the statement line (``Logger.findCaller`` skips this module's frames).
_ARM_INIT = frozenset({357})
_ARM_MISSING = frozenset({1047})
_ARM_REQUEST_DEBUG = frozenset({1060})
_ARM_SMALL = frozenset({944})
_ARM_OSERROR = frozenset({965})
_ARM_DECODE = frozenset({972})
_ARM_REJECT = frozenset({1060, 1069})
_ARM_TRIP = frozenset({1060, 1406})
_ARM_BUFFERED = frozenset({1060, 1101, 1388})
_ARM_STORED = frozenset({1060, 1319, 1341, 1386})
_ARM_EMPTY = frozenset({1060, 1388})
_ARM_COMMIT = frozenset({1060, 1319, 1341, 1430})
_ARM_CONNECT = frozenset({692, 707})
_ARM_TIMEOUT = frozenset({723, 738})
_ARM_ASYNCIO = frozenset({755, 771})
_ARM_SERVER = frozenset({792, 807})
_ARM_CLIENT = frozenset({830})
_ARM_JSON = frozenset({851, 866})
_ARM_UNEXPECTED = frozenset({884, 899})

# LogRecord's own attributes plus everything backend.core.logging's ContextFilter injects:
# what is left is the call's own ``extra=`` payload.
_NOISE = frozenset(
    set(logging.LogRecord("n", 0, "p", 0, "m", None, None).__dict__)
    | {
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
)

_IMAGE_PATH = "/export/yard/driveway/frame-0007.jpg"
_IMAGE_NAME = "frame-0007.jpg"
_CAMERA_ID = "cam-9"
_BYTES = b"image-bytes-here"
_DETECTOR_URL = "http://detector.invalid:8000"
# The explicit request budget L637 builds from the pinned settings (60.0 read + 5.0 connect)
# - it appears in the asyncio-timeout arm's two messages.
_EXPLICIT_TIMEOUT = 65.0
_REQUEST = httpx.Request("POST", "http://detector.invalid:8000/detect")
# The measurement leg's stand-in offset: 1000 s of "inference time", which is 1_000_000 ms of
# reported duration.  The real window between the two reads is tens of microseconds, so
# +-500 ms of tolerance excludes both the `/ 1000` mutant (which reports 1) and the `* 1001`
# mutant (which reports 1_001_000) while accepting the shipped 1_000_000.
_OFFSET = 1000.0
_TOLERANCE_MS = 500


# --------------------------------------------------------------------------- observation
def win(caplog):
    """Open a capture window on the shipped module logger (set_level + clear)."""
    caplog.set_level(logging.DEBUG, logger=M.logger.name)
    caplog.clear()


def mine(caplog):
    """Captured records from this module's own logger (provenance filtered)."""
    return [r for r in caplog.records if r.name == M.logger.name]


def mine_where(caplog, where):
    """This module's captured records restricted to the leg's own shipped call sites."""
    return [r for r in mine(caplog) if _anchor(r) in where]


def surface(caplog, where=None):
    """Every captured record as ``LEVEL lineno | msg | sorted(extras)``."""
    pool = mine(caplog) if where is None else mine_where(caplog, where)
    return sorted(f"{r.levelname} {_anchor(r)} | {r.msg} | {sorted(fields(r))}" for r in pool)


def sent(caplog, where):
    """``(levelname, caller lineno)`` of every owned record, IN EMISSION ORDER.

    ``Logger.findCaller`` skips this module's own frames, so the lineno IS the call site: an
    occurrence-twin sibling that dies (its kwargs stop matching the mutated signature) leaves
    a HOLE here even when another same-level record survives.
    """
    return [(r.levelname, _anchor(r)) for r in mine_where(caplog, where)]


def fields(rec):
    """The record's own ``extra=`` fields (LogRecord + ContextFilter noise removed)."""
    return {k: v for k, v in rec.__dict__.items() if k not in _NOISE}


def shipped_fields(rec, keys):
    """The named subset of the record's own ``extra=`` fields."""
    got = fields(rec)
    assert set(keys) <= set(got), (sorted(got), keys)
    return {k: got[k] for k in keys}


def one_at(caplog, where, level, lineno):
    """The single owned record at (level, lineno)."""
    hits = [r for r in mine_where(caplog, where) if (r.levelname, _anchor(r)) == (level, lineno)]
    assert len(hits) == 1, surface(caplog, where)
    return hits[0]


# --------------------------------------------------------------------------- doubles
class _DecodedImage:
    """The PIL context manager ``Image.open`` returns; ``load()`` is the shipped
    decompression call, so a no-op stand-in means "this image is intact"."""

    def load(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


async def _to_thread_inline(fn, *args, **kwargs):
    """Runs the offloaded callable on the current loop (``new=`` form, WP4.2 ratchet)."""
    return fn(*args, **kwargs)


class _PassThroughTimeout:
    """``asyncio.timeout(seconds)`` stand-in that never trips."""

    def __init__(self, seconds):
        self.seconds = seconds

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class fs(ExitStack):
    """Pins the filesystem the route reads - ``exists`` (L1046), ``stat().st_size`` (L942)
    and ``read_bytes`` (L1084) - plus PIL's open of the validation leg, and runs the two
    ``asyncio.to_thread`` offloads inline plus the backoff sleep and the request timeout, so
    no leg touches a real file and no leg waits.  ``image_error`` makes PIL's open raise,
    which is how the two corrupt-image legs reach their WARNING arms."""

    def __init__(
        self,
        *,
        exists=True,
        read_bytes=_BYTES,
        size=MIN_DETECTION_IMAGE_SIZE + 1,
        image_error=None,
    ):
        super().__init__()
        stat = MagicMock()
        stat.st_size = size
        self.enter_context(patch.object(M.Path, "exists", autospec=True, return_value=exists))
        self.enter_context(patch.object(M.Path, "stat", autospec=True, return_value=stat))
        self.enter_context(
            patch.object(M.Path, "read_bytes", autospec=True, return_value=read_bytes)
        )
        self.enter_context(
            patch.object(
                M.Image,
                "open",
                autospec=True,
                side_effect=image_error,
                return_value=None if image_error is not None else _DecodedImage(),
            )
        )
        self.enter_context(patch.object(M.asyncio, "to_thread", new=_to_thread_inline))
        self.enter_context(patch("asyncio.sleep", new_callable=AsyncMock))
        self.enter_context(patch.object(asyncio, "timeout", new=_PassThroughTimeout))


class TimeStandIn:
    """The module's own ``time`` name, narrowed to the ``time()`` reads of the route.

    ``time()`` returns a REAL reading plus ``offset``, so the shipped
    ``ai_duration = time.time() - ai_start_time`` stays exact while a leg that flips
    ``offset`` from inside the shipped inference window turns that subtraction into a number
    the leg chose.  ``readings`` records every read, so the leg can also pin HOW MANY reads
    the route performs on this path and WHICH two are the inference window.
    """

    def __init__(self):
        self.offset = 0.0
        self.readings = []

    def time(self):
        value = time.time() + self.offset
        self.readings.append(value)
        return value


@pytest.fixture
def clock():
    """``M.time`` replaced by :class:`TimeStandIn` for ONE test (``new=`` form)."""
    stand_in = TimeStandIn()
    with patch.object(M, "time", new=stand_in):
        yield stand_in


@pytest.fixture(autouse=True)
def baseline_service():
    """The shipped suite's autouse mock of ``get_baseline_service`` (reached at L1351
    whenever a detection is stored)."""
    service = MagicMock()
    service.update_baseline = AsyncMock()
    with patch("backend.services.detector_client.get_baseline_service", autospec=True) as factory:
        factory.return_value = service
        yield service


@pytest.fixture(autouse=True)
def request_envelope():
    """The W3C correlation headers and the shared inference semaphore the route consumes -
    pinned autospec so no leg depends on ambient settings or on another test's semaphore."""
    with (
        patch.object(
            M, "get_correlation_headers", autospec=True, return_value={"traceparent": "00-t"}
        ),
        patch.object(
            M, "get_inference_semaphore", autospec=True, return_value=asyncio.Semaphore(4)
        ),
    ):
        yield


@pytest.fixture
def settings():
    """``get_settings`` as the shipped suite patches it, pinned to the values this route
    reads.  The timeouts are real floats so a REAL ``DetectorClient`` can be built; the
    concurrency limit is a value no neighbouring module uses."""
    st = MagicMock()
    st.ai_gateway_url = None
    st.use_ai_gateway = False
    st.yolo26_url = _DETECTOR_URL
    st.yolo26_api_key = None
    st.yolo26_read_timeout = 60.0
    st.ai_connect_timeout = 5.0
    st.ai_health_timeout = 5.0
    st.detector_max_retries = 3
    st.ai_max_concurrent_inferences = 13
    st.detection_confidence_threshold = 0.5
    st.detection_class_thresholds = {}
    st.ai_warmup_enabled = False
    st.ai_cold_start_threshold_seconds = 60.0
    with patch("backend.services.detector_client.get_settings", autospec=True) as factory:
        factory.return_value = st
        yield factory


@pytest.fixture
def metrics():
    """Spy on the shipped pipeline-error reporter (imported by name at L76-L82, so the
    shipped call site is a call of that module global)."""
    with patch.object(M, "record_pipeline_error", autospec=True) as spy:
        yield spy


@pytest.fixture
def spans():
    """Spy on ``add_span_event``: the route calls it four times with the shipped names and
    attribute dicts."""
    with patch.object(M, "add_span_event", autospec=True) as spy:
        yield spy


@pytest.fixture
def durations():
    """Spy on ``observe_ai_request_duration`` (the L1139 call)."""
    with patch.object(M, "observe_ai_request_duration", autospec=True) as spy:
        yield spy


@pytest.fixture
def client(settings):
    """A REAL ``DetectorClient(max_retries=2)`` - the shipped ``__init__`` runs, so the
    breaker and retry loop under test are production code (2 attempts: one retry, one final)."""
    instance = DetectorClient(max_retries=2)
    assert instance._max_retries == 2
    assert instance._detector_type == "yolo26"
    assert instance._detector_url == _DETECTOR_URL
    yield instance


def response(*, status=200, body=None, json_error=None, status_error=None):
    """An ``httpx.Response`` double in the shape the shipped call sites use."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    if status_error is not None:
        resp.raise_for_status.side_effect = status_error
    else:
        resp.raise_for_status.return_value = None
    if json_error is not None:
        resp.json.side_effect = json_error
    else:
        resp.json.return_value = {"detections": []} if body is None else body
    return resp


def status_error(message, status, body=None):
    """A shipped-shaped ``httpx.HTTPStatusError`` (real Request, response double).

    ``body`` backs ``e.response.json()``: the shipped 400 arm (L821-L827) reads the detail
    out of the ERROR response, so the double has to answer like a real response.
    """
    return httpx.HTTPStatusError(
        message,
        request=_REQUEST,
        response=response(status=status, body=body if body is not None else {"detections": []}),
    )


_ERR_503 = status_error("Detector service is unavailable", 503)
_ERR_400 = status_error(
    "Detector service rejected this image", 400, body={"detail": "payload rejected"}
)


def post(**kwargs):
    """Patch the persistent HTTP client's ``post`` (autospec, as the shipped suite does)."""
    return patch.object(httpx.AsyncClient, "post", autospec=True, **kwargs)


def session_double(*, camera=None, commit_error=None):
    """A DB session double: ``get`` answers with ``camera``, ``add``/``commit``/``flush``
    are spies (``commit`` can be made to fail)."""
    ses = AsyncMock()
    ses.get = AsyncMock(return_value=camera)
    ses.add = MagicMock()
    ses.commit = AsyncMock(side_effect=commit_error) if commit_error else AsyncMock()
    ses.flush = AsyncMock()
    return ses


async def run_detect(client, ses=None, **over):
    """Drive the shipped ``detect_objects`` on the pinned image/camera."""
    return await client.detect_objects(_IMAGE_PATH, _CAMERA_ID, ses or session_double(), **over)


def stub_transport(client, body):
    """Short-circuits ONLY the transport: ``_circuit_breaker.call`` answers with ``body``.
    ``autospec=True`` on the bound attribute (WP4.2 ratchet) and the shipped L1068
    ``allow_call()`` / L1129 kwargs still execute as production code."""

    async def _call(_fn, **kwargs):
        return body

    return patch.object(client._circuit_breaker, "call", autospec=True, side_effect=_call)


def _body(**over):
    payload = {"detections": []}
    payload.update(over)
    return payload


def _attrs(spy, index):
    """The attribute dict of the ``index``-th ``add_span_event`` call."""
    return spy.call_args_list[index].args[1]


def _names(spy):
    return [c.args[0] for c in spy.call_args_list]


# The route emits exactly four span events per run, so a second phase of the same leg reads
# its own ``detection_inference.complete`` at index 3 + 4.
FIRST_EVENTS = 4


# --------------------------------------------------------------------------- tests
# --------------------------------------------------------------------------- tests
# (A) the pre-flight gates: L1031-L1063  (m1, m13/m14, m18-m47)


@pytest.mark.asyncio
async def test_the_client_construction_record_names_the_detector(caplog, settings):
    """TWIN COVERAGE for L360: ``"detector_type": self._detector_type,`` is a 17-way
    occurrence and the client-construction INFO is one of them - a REAL client built inside
    the window proves that candidate."""
    win(caplog)
    built = DetectorClient(max_retries=3)

    assert sent(caplog, _ARM_INIT) == [("INFO", 357)], surface(caplog, _ARM_INIT)
    info = one_at(caplog, _ARM_INIT, "INFO", 357)
    assert info.msg == "DetectorClient initialized"
    assert shipped_fields(info, ["detector_type", "max_retries"]) == {
        "detector_type": built._detector_type,
        "max_retries": 3,
    }


@pytest.mark.asyncio
async def test_the_four_span_events_carry_the_shipped_attributes(caplog, client, spans, metrics):
    """L1035/L1087/L1118/L1143 in emission order with their EXACT attribute dicts: the
    ``detector.type`` key is a 3-way occurrence across three of these events (m13/m14/m137/
    m138 rename or upper-case it) and ``detector.url`` appears once at L1123 (m109/m110)."""
    win(caplog)
    with fs(), stub_transport(client, _body()):
        assert await run_detect(client) == []

    assert _names(spans) == [
        "frame_capture.start",
        "frame_capture.complete",
        "detection_inference.start",
        "detection_inference.complete",
    ], spans.call_args_list
    assert _attrs(spans, 0) == {
        "camera.id": _CAMERA_ID,
        "file.path": _IMAGE_PATH,
        "detector.type": "yolo26",
    }
    assert _attrs(spans, 1) == {"camera.id": _CAMERA_ID, "frame.size_bytes": len(_BYTES)}
    assert _attrs(spans, 2) == {
        "camera.id": _CAMERA_ID,
        "detector.type": "yolo26",
        "detector.url": client._detector_url,
    }
    done = _attrs(spans, 3)
    assert done["camera.id"] == _CAMERA_ID
    assert done["detector.type"] == "yolo26"
    assert done["detection.count"] == 0
    assert isinstance(done["inference.duration_ms"], int)
    assert 0 <= done["inference.duration_ms"] < 5000
    assert metrics.call_args_list == []


@pytest.mark.asyncio
async def test_a_missing_file_is_reported_once_and_stops(caplog, client, metrics):
    """TWIN COVERAGE for L1049: the missing-file arm logs ONE ERROR (L1047) naming the
    camera and the path, reports ``file_not_found`` (L1051) and never reaches the
    transport/span-events.  m18/m22/m23/m24 act on the message, m19/m21/m25-m28 on the
    ``extra`` - which is ALSO the L1062 sibling, proven by the pre-request DEBUG leg."""
    win(caplog)
    with fs(exists=False), post() as posted:
        assert await run_detect(client) == []

    assert sent(caplog, _ARM_MISSING) == [("ERROR", 1047)], surface(caplog, _ARM_MISSING)
    error = one_at(caplog, _ARM_MISSING, "ERROR", 1047)
    assert error.msg == "Image file not found"
    assert shipped_fields(error, ["camera_id", "file_path"]) == {
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert metrics.call_args_list == [call("file_not_found")]
    posted.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_pre_request_debug_names_the_image(caplog, client, metrics):
    """TWIN COVERAGE for L1062: the pre-request DEBUG (L1060) carries the shipped f-string
    text and the two-field ``extra`` (m40 blanks the message, m41/m43 drop the ``extra``,
    m44-m47 rename its keys).  Its ``extra`` text is the SAME occurrence family as L1049's,
    which the missing-file leg above pins."""
    win(caplog)
    with fs(), stub_transport(client, _body()):
        assert await run_detect(client) == []

    assert sent(caplog, _ARM_EMPTY) == [("DEBUG", 1060), ("DEBUG", 1388)], surface(
        caplog, _ARM_EMPTY
    )
    debug = one_at(caplog, _ARM_REQUEST_DEBUG, "DEBUG", 1060)
    assert debug.msg == f"Sending detection request for {_IMAGE_PATH}"
    assert shipped_fields(debug, ["camera_id", "file_path"]) == {
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }


@pytest.mark.asyncio
async def test_the_camera_is_handed_to_the_integrity_check(client):
    """L1056: the integrity gate is asked about THIS camera - ``m34`` blinds the second
    argument to ``None``, so the shipped two-positional-argument call is what this pins."""
    client._frame_buffer = None
    with (
        fs(),
        patch.object(
            client, "_validate_image_for_detection_async", autospec=True, return_value=True
        ) as gate,
        stub_transport(client, _body()),
    ):
        assert await run_detect(client) == []

    assert gate.await_count == 1
    assert gate.await_args.args == (_IMAGE_PATH, _CAMERA_ID), gate.await_args


@pytest.mark.asyncio
async def test_a_rejected_image_is_reported_as_invalid(caplog, client, metrics):
    """L1056-L1057: when the integrity gate says ``False`` the route reports
    ``invalid_image`` and returns before the pre-request DEBUG - so the ONLY owned record is
    gone and no metric label other than the shipped one exists (m37-m39)."""
    with (
        fs(),
        patch.object(
            client, "_validate_image_for_detection_async", autospec=True, return_value=False
        ),
        post() as posted,
    ):
        win(caplog)
        assert await run_detect(client) == []

    assert sent(caplog, _ARM_EMPTY) == [], surface(caplog, _ARM_EMPTY)
    assert metrics.call_args_list == [call("invalid_image")]
    posted.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_truncated_image_is_reported_as_invalid(caplog, client, metrics):
    """TWIN COVERAGE for L947/L948: a file below ``MIN_DETECTION_IMAGE_SIZE`` never reaches
    the detector - one WARNING at L944 naming camera, path, size and floor - and the route
    then reports ``invalid_image`` at L1057."""
    with fs(size=MIN_DETECTION_IMAGE_SIZE - 1), post() as posted:
        win(caplog)
        assert await run_detect(client) == []

    assert sent(caplog, _ARM_SMALL) == [("WARNING", 944)], surface(caplog, _ARM_SMALL)
    warning = one_at(caplog, _ARM_SMALL, "WARNING", 944)
    assert warning.msg == "Image too small for detection"
    assert shipped_fields(warning, ["camera_id", "file_path"]) == {
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(warning, ["file_size", "min_size"]) == {
        "file_size": MIN_DETECTION_IMAGE_SIZE - 1,
        "min_size": MIN_DETECTION_IMAGE_SIZE,
    }
    assert metrics.call_args_list == [call("invalid_image")]
    posted.assert_not_awaited()


@pytest.mark.asyncio
async def test_an_unreadable_image_uses_the_oserror_arm(caplog, client, metrics):
    """TWIN COVERAGE for L967: an ``OSError`` out of PIL's open logs the shipped corrupt/
    truncated WARNING at L965 with camera_id, file_path and the raw error."""
    with fs(image_error=OSError("truncated upload")), post() as posted:
        win(caplog)
        assert await run_detect(client) == []

    assert sent(caplog, _ARM_OSERROR) == [("WARNING", 965)], surface(caplog, _ARM_OSERROR)
    warning = one_at(caplog, _ARM_OSERROR, "WARNING", 965)
    assert warning.msg == "Image validation failed (corrupt/truncated)"
    assert shipped_fields(warning, ["camera_id", "file_path", "error"]) == {
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
        "error": "truncated upload",
    }
    assert metrics.call_args_list == [call("invalid_image")]
    posted.assert_not_awaited()


@pytest.mark.asyncio
async def test_an_unreadable_image_uses_the_decode_arm(caplog, client, metrics):
    """TWIN COVERAGE for L974: the ``ValueError``/``RuntimeError`` arm logs the shorter
    shipped sentence at L972 with the sanitized error."""
    with fs(image_error=ValueError("bad image format")), post() as posted:
        win(caplog)
        assert await run_detect(client) == []

    assert sent(caplog, _ARM_DECODE) == [("WARNING", 972)], surface(caplog, _ARM_DECODE)
    warning = one_at(caplog, _ARM_DECODE, "WARNING", 972)
    assert warning.msg == "Image validation failed"
    assert shipped_fields(warning, ["camera_id", "file_path", "error"]) == {
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
        "error": "bad image format",
    }
    assert metrics.call_args_list == [call("invalid_image")]
    posted.assert_not_awaited()


# --------------------------------------------------------------------------- (B) breaker gate
# --------------------------------------------------------------------------- (B) the circuit-breaker gate: L1068-L1081 and its L1402 twin
# --------------------------------------------------------------------------- (m49-m64)


@pytest.mark.asyncio
async def test_an_open_circuit_rejects_before_the_request(caplog, client, metrics):
    """TWIN COVERAGE for L1072/L1073/L1074/L1075 (plus the L1078 metric and the L1080
    message): with the shipped breaker reporting an open circuit, ``detect_objects`` logs ONE
    rejection WARNING at L1069 with the shipped f-string text and four extras, reports
    ``circuit_breaker_open`` and raises - without touching the transport."""
    client._circuit_breaker.force_open()
    win(caplog)
    with fs(), post() as posted:
        with pytest.raises(M.DetectorUnavailableError) as raised:
            await run_detect(client)

    assert sent(caplog, _ARM_REJECT) == [("DEBUG", 1060), ("WARNING", 1069)], surface(
        caplog, _ARM_REJECT
    )
    warning = one_at(caplog, _ARM_REJECT, "WARNING", 1069)
    assert warning.msg == "Circuit breaker open for yolo26, rejecting detection request"
    assert shipped_fields(warning, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(warning, ["circuit_state"])["circuit_state"] == (
        client._circuit_breaker.state.value
    )
    assert metrics.call_args_list == [call("circuit_breaker_open")]
    assert str(raised.value) == ("yolo26 service temporarily unavailable (circuit breaker open)")
    posted.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_call_phase_trip_is_reported_and_reraised(caplog, client, metrics):
    """TWIN COVERAGE for L1405/L1409/L1410/L1411/L1413/L1418: when the shipped breaker
    RAISES ``CircuitBreakerError`` around the call (the call-phase trip, past ``allow_call``),
    ``detect_objects`` reports ``circuit_breaker_open`` at L1405, logs the shipped WARNING at
    L1406 with the six shipped extras and re-raises with the shipped message."""
    trip = M.CircuitBreakerError("detector_yolo26", "open", recovery_timeout=60.0)
    breaker = MagicMock()
    breaker.allow_call = AsyncMock(return_value=True)
    breaker.call = AsyncMock(side_effect=trip)
    breaker.state = trip.state
    client._circuit_breaker = breaker
    win(caplog)
    with fs(), post():
        with pytest.raises(M.DetectorUnavailableError) as raised:
            await run_detect(client)

    assert sent(caplog, _ARM_TRIP) == [("DEBUG", 1060), ("WARNING", 1406)], surface(
        caplog, _ARM_TRIP
    )
    assert raised.value.original_error is trip
    assert str(raised.value) == ("yolo26 service temporarily unavailable (circuit breaker open)")
    assert metrics.call_args_list == [call("circuit_breaker_open")]
    warning = one_at(caplog, _ARM_TRIP, "WARNING", 1406)
    assert warning.msg == "Circuit breaker open for yolo26"
    assert shipped_fields(warning, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(warning, ["circuit_state", "error"]) == {
        "circuit_state": trip.state.value,
        "error": str(trip),
    }
    assert isinstance(shipped_fields(warning, ["duration_ms"])["duration_ms"], int)


# --------------------------------------------------------------------------- (C) frame buffer
# --------------------------------------------------------------------------- (C) frame buffering: L1099-L1108  (m86-m96)


@pytest.mark.asyncio
async def test_the_frame_buffer_receives_the_frame_and_logs_it(caplog, client, metrics):
    """L1100-L1108: the frame is handed to ``add_frame(camera_id, image_bytes, aware
    datetime)``, and the DEBUG at L1101 names ``camera_id``, ``frame_size_bytes`` (the byte
    count) and ``buffer_count`` - which the shipped code reads with ``frame_count(camera_id)``,
    so m96's blinded ``None`` is caught by the call argument while m86-m95 act on the record.
    """
    buffer = MagicMock()
    buffer.add_frame = AsyncMock()
    buffer.frame_count = MagicMock(return_value=3)
    client._frame_buffer = buffer
    win(caplog)
    with fs(), stub_transport(client, _body()):
        assert await run_detect(client) == []

    buffer.add_frame.assert_awaited_once()
    args = buffer.add_frame.await_args.args
    assert args[0] == _CAMERA_ID
    assert args[1] == _BYTES
    assert args[2].tzinfo is not None
    buffer.frame_count.assert_called_once_with(_CAMERA_ID)
    assert sent(caplog, _ARM_BUFFERED) == [
        ("DEBUG", 1060),
        ("DEBUG", 1101),
        ("DEBUG", 1388),
    ], surface(caplog, _ARM_BUFFERED)
    debug = one_at(caplog, _ARM_BUFFERED, "DEBUG", 1101)
    assert debug.msg == f"Buffered frame for camera {_CAMERA_ID}"
    assert shipped_fields(debug, ["camera_id", "frame_size_bytes", "buffer_count"]) == {
        "camera_id": _CAMERA_ID,
        "frame_size_bytes": len(_BYTES),
        "buffer_count": 3,
    }


# --------------------------------------------------------------------------- (D) measurement
# --------------------------------------------------------------------------- (D) the measurement window: L1111-L1149  (m123/m124/m144/m145)


@pytest.mark.asyncio
async def test_the_inference_window_is_a_subtraction_reported_in_ms(
    caplog, client, clock, durations, spans, metrics
):
    """Two phases of the SAME route, so the shipped arithmetic is pinned from both sides:

    * phase 1 - no offset: exactly FOUR ``time()`` reads happen on this path
      (L1032/L1111/L1138/L1372).  ``observe_ai_request_duration`` is then handed EXACTLY
      ``readings[2] - readings[1]`` and the span attribute EXACTLY
      ``int((readings[2] - readings[1]) * 1000)``, which is the shipped arithmetic with no
      slack at all: m123's ``+`` hands over ~2x the epoch (~3.6e9) and m124's ``None`` label
      is caught by the reporter's first argument;
    * phase 2 - ``offset`` flipped from inside the shipped request window (the transport
      stub's own side effect, which runs between the two reads): the window becomes
      ``OFFSET + (microseconds)``.  The shipped ``int(ai_duration * 1000)`` then reports
      ~1_000_000 ms, m144's ``/ 1000`` reports 1 and m145's ``* 1001`` reports ~1_001_000.
    """
    # ---- phase 1: the shipped subtraction, measured on a real clock
    win(caplog)
    with fs(), stub_transport(client, _body()):
        assert await run_detect(client) == []

    assert len(clock.readings) == 4, clock.readings
    window = clock.readings[2] - clock.readings[1]
    assert 0.0 <= window < 0.5, window
    durations.assert_called_once_with("yolo26", window)
    assert _attrs(spans, 3)["inference.duration_ms"] == int(window * 1000)

    # ---- phase 2: the same route with a 1000 s window
    async def _slow(_fn, **kwargs):
        clock.offset = _OFFSET
        return _body()

    clock.offset = 0.0
    durations.reset_mock()
    win(caplog)
    with (
        fs(),
        patch.object(
            client._circuit_breaker,
            "call",
            autospec=True,
            side_effect=_slow,
        ),
    ):
        assert await run_detect(client) == []

    assert len(clock.readings) == 8, clock.readings
    window = clock.readings[6] - clock.readings[5]
    assert _names(spans)[FIRST_EVENTS:] == [
        "frame_capture.start",
        "frame_capture.complete",
        "detection_inference.start",
        "detection_inference.complete",
    ], spans.call_args_list
    assert _attrs(spans, FIRST_EVENTS + 3)["inference.duration_ms"] == int(window * 1000)
    assert abs(window - _OFFSET) < 0.5, window
    durations.assert_called_once()
    assert durations.call_args.args[0] == "yolo26"
    assert abs(durations.call_args.args[1] - _OFFSET) < 0.5, durations.call_args
    reported = _attrs(spans, FIRST_EVENTS + 3)["inference.duration_ms"]
    assert abs(reported - _OFFSET * 1000) < _TOLERANCE_MS, reported


# --------------------------------------------------------------------------- (E) trace id
# --------------------------------------------------------------------------- (E) the trace_id contract: L1031 + L1384  (m1)


@pytest.mark.asyncio
async def test_the_trace_id_reaches_the_stored_detections_record(caplog, client, metrics):
    """L1031 -> L1384: a trace id read at the top of the route is published on the
    ``Stored detections`` INFO.  m1 pins ``trace_id = None`` at L1031, so the key never
    reaches ``extra`` and ``ContextFilter`` fills the attribute with its empty default -
    which is what this leg distinguishes."""
    ses = session_double(camera=MagicMock())
    body = {
        "detections": [{"class": "person", "confidence": 0.9, "bbox": [1, 2, 3, 4]}],
        "image_width": 100,
        "image_height": 60,
    }
    win(caplog)
    with (
        fs(),
        stub_transport(client, body),
        patch.object(M, "get_trace_id", autospec=True, return_value="TRACE-1") as trace,
    ):
        assert len(await run_detect(client, ses)) == 1

    trace.assert_called_once_with()
    info = one_at(caplog, _ARM_STORED, "INFO", 1386)
    assert info.msg == "Stored detections"
    assert info.trace_id == "TRACE-1"


# --------------------------------------------------------------------------- (F) stored/empty
# --------------------------------------------------------------------------- (F) the closing records: L1341-L1392  (1343/1379/1380/1391/1392)


@pytest.mark.asyncio
async def test_a_stored_detection_logs_the_camera_and_the_stored_summary(caplog, client, metrics):
    """TWIN COVERAGE for L1343/L1379/L1380: a stored detection produces the per-detection
    DEBUG (L1319), the camera ``last_seen_at`` DEBUG (L1341, naming camera_id) and the
    ``Stored detections`` INFO (L1386, naming camera_id, file_path and detection_count)."""
    camera = MagicMock()
    ses = session_double(camera=camera)
    body = {
        "detections": [{"class": "person", "confidence": 0.9, "bbox": [1, 2, 3, 4]}],
        "image_width": 100,
        "image_height": 60,
    }
    win(caplog)
    with fs(), stub_transport(client, body):
        assert len(await run_detect(client, ses)) == 1

    assert sent(caplog, _ARM_STORED) == [
        ("DEBUG", 1060),
        ("DEBUG", 1319),
        ("DEBUG", 1341),
        ("INFO", 1386),
    ], surface(caplog, _ARM_STORED)
    debug = one_at(caplog, _ARM_STORED, "DEBUG", 1341)
    assert debug.msg.startswith(f"Updated camera {_CAMERA_ID} last_seen_at to ")
    assert shipped_fields(debug, ["camera_id", "last_seen_at"]) == {
        "camera_id": _CAMERA_ID,
        "last_seen_at": camera.last_seen_at.isoformat(),
    }
    info = one_at(caplog, _ARM_STORED, "INFO", 1386)
    assert info.msg == "Stored detections"
    assert shipped_fields(info, ["camera_id", "file_path", "detection_count"]) == {
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
        "detection_count": 1,
    }
    assert isinstance(shipped_fields(info, ["duration_ms"])["duration_ms"], int)


@pytest.mark.asyncio
async def test_the_empty_result_debug_names_the_camera_and_the_path(caplog, client, metrics):
    """TWIN COVERAGE for L1391/L1392: an empty result logs the shipped DEBUG at L1388 naming
    the path, the camera and the duration."""
    win(caplog)
    with fs(), stub_transport(client, _body()):
        assert await run_detect(client) == []

    assert sent(caplog, _ARM_EMPTY) == [("DEBUG", 1060), ("DEBUG", 1388)], surface(
        caplog, _ARM_EMPTY
    )
    debug = one_at(caplog, _ARM_EMPTY, "DEBUG", 1388)
    assert debug.msg == f"No detections above threshold for {_IMAGE_PATH}"
    assert shipped_fields(debug, ["camera_id", "file_path"]) == {
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert isinstance(shipped_fields(debug, ["duration_ms"])["duration_ms"], int)


@pytest.mark.asyncio
async def test_a_commit_failure_becomes_the_object_detection_error(caplog, client, metrics):
    """TWIN COVERAGE for L1433/L1434: a ``RuntimeError`` out of the commit is logged as the
    shipped ``Unexpected error during object detection`` ERROR at L1430 (detector_type,
    camera_id, sanitized error, ``exc_info=True``) and re-raised."""
    boom = RuntimeError("session pool gone")
    ses = session_double(camera=MagicMock(), commit_error=boom)
    body = {
        "detections": [{"class": "person", "confidence": 0.9, "bbox": [1, 2, 3, 4]}],
        "image_width": 100,
        "image_height": 60,
    }
    win(caplog)
    with fs(), stub_transport(client, body):
        with pytest.raises(M.DetectorUnavailableError) as raised:
            await run_detect(client, ses)

    assert sent(caplog, _ARM_COMMIT) == [
        ("DEBUG", 1060),
        ("DEBUG", 1319),
        ("DEBUG", 1341),
        ("ERROR", 1430),
    ], surface(caplog, _ARM_COMMIT)
    assert raised.value.original_error is boom
    assert metrics.call_args_list == [call("yolo26_unexpected_error")]
    error = one_at(caplog, _ARM_COMMIT, "ERROR", 1430)
    assert error.msg == "Unexpected error during object detection"
    assert shipped_fields(error, ["detector_type", "camera_id", "error"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "error": "session pool gone",
    }
    assert error.exc_info is not None and error.exc_info[1] is boom


# --------------------------------------------------------------------------- (G) transport arms
# --------------------------------------------------------------------------- (G) the retry arms' extras (17/25/20-way occurrence twins)


def _retried(caplog, where, warning_lineno, error_lineno):
    """One WARNING at the arm's retry site and one ERROR at its final site, in order."""
    assert sent(caplog, where) == [("WARNING", warning_lineno), ("ERROR", error_lineno)], surface(
        caplog, where
    )


@pytest.mark.asyncio
async def test_the_connection_arm_retries_once_then_reports(caplog, client, metrics):
    """TWIN COVERAGE for L695/L696/L697 and L710/L711/L712: a ``ConnectError`` retries once
    (WARNING at L692 with the seven shipped extras) and then reports + logs the final ERROR
    (L707, five extras, ``exc_info=True``)."""
    win(caplog)
    with fs(), post(side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(M.DetectorUnavailableError):
            await run_detect(client)

    _retried(caplog, _ARM_CONNECT, 692, 707)
    warning = one_at(caplog, _ARM_CONNECT, "WARNING", 692)
    assert warning.msg == "Detector connection error, retrying"
    assert shipped_fields(warning, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(warning, ["attempt", "max_retries", "retry_delay", "error"]) == {
        "attempt": 1,
        "max_retries": 2,
        "retry_delay": 1,
        "error": "Connection refused",
    }
    error = one_at(caplog, _ARM_CONNECT, "ERROR", 707)
    assert error.msg == "Detector connection error after all attempts"
    assert shipped_fields(error, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(error, ["attempts", "error"]) == {
        "attempts": 2,
        "error": "Connection refused",
    }
    assert error.exc_info is not None
    assert metrics.call_args_list == [call("yolo26_connection_error")]


@pytest.mark.asyncio
async def test_the_timeout_arm_retries_once_then_reports(caplog, client, metrics):
    """TWIN COVERAGE for L726/L727/L728 and L741/L742/L743 - the ``TimeoutException`` arm."""
    win(caplog)
    with fs(), post(side_effect=httpx.TimeoutException("no answer")):
        with pytest.raises(M.DetectorUnavailableError):
            await run_detect(client)

    _retried(caplog, _ARM_TIMEOUT, 723, 738)
    warning = one_at(caplog, _ARM_TIMEOUT, "WARNING", 723)
    assert warning.msg == "Detector timeout, retrying"
    assert shipped_fields(warning, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(warning, ["attempt", "max_retries", "retry_delay", "error"]) == {
        "attempt": 1,
        "max_retries": 2,
        "retry_delay": 1,
        "error": "no answer",
    }
    error = one_at(caplog, _ARM_TIMEOUT, "ERROR", 738)
    assert error.msg == "Detector timeout after all attempts"
    assert shipped_fields(error, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(error, ["attempts", "error"]) == {"attempts": 2, "error": "no answer"}
    assert error.exc_info is not None
    assert metrics.call_args_list == [call("yolo26_timeout")]


@pytest.mark.asyncio
async def test_the_asyncio_timeout_arm_retries_then_reports(caplog, client, metrics):
    """TWIN COVERAGE for L759/L760/L761 and L775/L776/L777 - the ``TimeoutError`` arm, whose
    two messages interpolate the shipped request budget."""
    win(caplog)
    with fs(), post(side_effect=TimeoutError("watchdog")):
        with pytest.raises(M.DetectorUnavailableError):
            await run_detect(client)

    _retried(caplog, _ARM_ASYNCIO, 755, 771)
    warning = one_at(caplog, _ARM_ASYNCIO, "WARNING", 755)
    assert warning.msg == (
        f"Detector asyncio timeout (attempt 1/2), retrying in 1s: request timed out after "
        f"{_EXPLICIT_TIMEOUT}s"
    )
    assert shipped_fields(warning, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(
        warning, ["attempt", "max_retries", "retry_delay", "explicit_timeout"]
    ) == {
        "attempt": 1,
        "max_retries": 2,
        "retry_delay": 1,
        "explicit_timeout": _EXPLICIT_TIMEOUT,
    }
    error = one_at(caplog, _ARM_ASYNCIO, "ERROR", 771)
    assert error.msg == (
        f"Detector asyncio timeout after 2 attempts: request timed out after {_EXPLICIT_TIMEOUT}s"
    )
    assert shipped_fields(error, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(error, ["attempts", "explicit_timeout"]) == {
        "attempts": 2,
        "explicit_timeout": _EXPLICIT_TIMEOUT,
    }
    assert error.exc_info is not None
    assert metrics.call_args_list == [call("yolo26_asyncio_timeout")]


@pytest.mark.asyncio
async def test_the_server_error_arm_retries_then_reports(caplog, client, metrics):
    """TWIN COVERAGE for L795/L796/L797 and L810/L811/L812 - the HTTP 5xx arm (the retry
    WARNING has no ``error`` key; it carries ``status_code`` instead)."""
    win(caplog)
    with fs(), post(return_value=response(status=503, status_error=_ERR_503)):
        with pytest.raises(M.DetectorUnavailableError):
            await run_detect(client)

    _retried(caplog, _ARM_SERVER, 792, 807)
    warning = one_at(caplog, _ARM_SERVER, "WARNING", 792)
    assert warning.msg == "Detector server error, retrying"
    assert shipped_fields(warning, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(warning, ["status_code", "attempt", "max_retries", "retry_delay"]) == {
        "status_code": 503,
        "attempt": 1,
        "max_retries": 2,
        "retry_delay": 1,
    }
    error = one_at(caplog, _ARM_SERVER, "ERROR", 807)
    assert error.msg == "Detector server error after all attempts"
    assert shipped_fields(error, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(error, ["status_code", "attempts"]) == {
        "status_code": 503,
        "attempts": 2,
    }
    assert error.exc_info is not None
    assert metrics.call_args_list == [call("yolo26_server_error")]


@pytest.mark.asyncio
async def test_a_client_error_is_reported_once_and_returns_empty(caplog, client, metrics):
    """TWIN COVERAGE for L833/L834/L835: a 4xx is NOT retried - one ERROR (L830) with the
    five shipped extras, a ``yolo26_client_error`` report, and ``detect_objects`` swallows the
    resulting ``ValueError`` into an empty result (L1400-L1401)."""
    win(caplog)
    with fs(), post(return_value=response(status=400, status_error=_ERR_400)):
        assert await run_detect(client) == []

    assert sent(caplog, _ARM_CLIENT) == [("ERROR", 830)], surface(caplog, _ARM_CLIENT)
    error = one_at(caplog, _ARM_CLIENT, "ERROR", 830)
    assert error.msg == "Detector client error"
    assert shipped_fields(error, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(error, ["status_code", "error_detail"]) == {
        "status_code": 400,
        "error_detail": "payload rejected",
    }
    assert error.exc_info is None
    assert metrics.call_args_list == [call("yolo26_client_error")]


@pytest.mark.asyncio
async def test_the_json_error_arm_retries_then_reports(caplog, client, metrics):
    """TWIN COVERAGE for L855/L856/L857 and L870/L871/L872 - the malformed-JSON arm, whose
    messages interpolate the sanitized error."""
    boom = json.JSONDecodeError("Expecting value", "<html>", 0)
    win(caplog)
    with fs(), post(return_value=response(json_error=boom)):
        with pytest.raises(M.DetectorUnavailableError):
            await run_detect(client)

    _retried(caplog, _ARM_JSON, 851, 866)
    warning = one_at(caplog, _ARM_JSON, "WARNING", 851)
    assert warning.msg == (
        f"Detector JSON/value error (attempt 1/2), retrying in 1s: {M.sanitize_error(boom)}"
    )
    assert shipped_fields(warning, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(warning, ["attempt", "max_retries", "retry_delay"]) == {
        "attempt": 1,
        "max_retries": 2,
        "retry_delay": 1,
    }
    error = one_at(caplog, _ARM_JSON, "ERROR", 866)
    assert error.msg == (f"Detector JSON/value error after 2 attempts: {M.sanitize_error(boom)}")
    assert shipped_fields(error, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(error, ["attempts"]) == {"attempts": 2}
    assert error.exc_info is not None
    assert metrics.call_args_list == [call("yolo26_json_error")]


@pytest.mark.asyncio
async def test_the_unexpected_error_arm_retries_then_reports(caplog, client, metrics):
    """TWIN COVERAGE for L887/L888/L889 and L902/L903/L904 - the ``OSError``/``RuntimeError``
    arm inside the retry loop."""
    boom = RuntimeError("connection reset by peer")
    win(caplog)
    with fs(), post(side_effect=boom):
        with pytest.raises(M.DetectorUnavailableError):
            await run_detect(client)

    _retried(caplog, _ARM_UNEXPECTED, 884, 899)
    warning = one_at(caplog, _ARM_UNEXPECTED, "WARNING", 884)
    assert warning.msg == "Unexpected detector error, retrying"
    assert shipped_fields(warning, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(warning, ["attempt", "max_retries", "retry_delay", "error"]) == {
        "attempt": 1,
        "max_retries": 2,
        "retry_delay": 1,
        "error": "connection reset by peer",
    }
    error = one_at(caplog, _ARM_UNEXPECTED, "ERROR", 899)
    assert error.msg == "Unexpected detector error after all attempts"
    assert shipped_fields(error, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(error, ["attempts", "error"]) == {
        "attempts": 2,
        "error": "connection reset by peer",
    }
    assert error.exc_info is not None
    assert metrics.call_args_list == [call("yolo26_unexpected_error")]
