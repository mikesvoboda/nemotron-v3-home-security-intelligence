"""S2 batch-28 lane L4 - ``detector_client`` group dc06 kill battery (64 keys).

Module: ``backend/services/detector_client.py`` (md5
``294c938abe9e37cd0f979f9357982753``, re-verified before this file was written).
Admitted manifest: ``/tmp/wp-pw/detector_client/manifest.json`` group
``dc06-send-happy-path-telemetry`` - 64 KILLABLE / 0 EQUIVALENT / 0
NEEDS_INVESTIGATION; keys file ``manifest_groups/dc06-send-happy-path-telemetry.keys``
(content-identical to ``group_05.keys``); splice report
``splice-dc06-send-happy-path-telemetry.json``: 60 clean / 4 twin / **0 bad**, so
no key in this group needs a hand-splice probe.

Every key sits inside the ONE def ``DetectorClient._send_detection_request``: the
timeout-budget line (L637), the span + AI-model telemetry block (L641-655), the
``retry_attempt`` attribute (L658), the POST and its payload handling (L666-677)
and the two result helpers (L678-685).  Production never bends: every literal
below is transcribed from the shipped line quoted in the leg that asserts it.

Settings are INJECTED (``settings`` fixture) rather than inherited, which is what
makes ``m5`` (``Add -> Subtract`` on L637) observable: the two legs the budget is
built from are asymmetric (``yolo26_read_timeout=20.0``,
``ai_connect_timeout=30.0``), so the shipped sum is ``50.0`` while the mutant's
difference is ``-10.0`` - a negative ``asyncio.timeout`` budget fires
``TimeoutError`` BEFORE the request body runs, which is a completely different
observable outcome from the shipped timeout (the shipped arm emits a WARNING
first, the negative-budget arm emits none at all).  Because the values are
fixture-owned, every budget figure quoted below is computed by the LEG
(``BUDGET = READ_TIMEOUT + CONNECT_TIMEOUT``), never hardcoded.

Observation strategy
====================
The four telemetry collaborators are replaced per test, inside the module's own
name resolution (``trace_span`` at L85; ``AIModelAttributes`` at L86-90,
``set_detection_attributes`` / ``set_inference_result_attributes`` at L87/L89),
so the code under test stays shipped while BOTH surfaces are readable:

* ``trace_span`` -> ``MagicMock(new=...)`` whose ``side_effect`` is a generator
  helper yielding ONE shared ``RecorderSpan``.  A truthy ``side_effect`` return
  value replaces the mock's return value, so the object the shipped
  ``with ... as span`` binds IS that recorder.
* ``AIModelAttributes.set_on_span`` and the two result helpers ->
  ``autospec=True, wraps=<the shipped callable>``: the SHIPPED helper still runs
  and writes the recorder span (so a ``None``-ed or dropped keyword is a MISSING
  attribute - the shipped helpers guard every leg with ``is not None``), while
  the spy records the call the shipped line made (so a renamed literal and a
  dropped-but-defaulted keyword - which the real helper cannot distinguish - are
  both visible too).  Both surfaces are asserted for every key in L648-685.
* ``httpx.AsyncClient.post`` -> ``autospec=True`` (the shipped persistent client
  of L321 IS a real ``AsyncClient``, so the binding matches).  Autospec hands the
  recorded call the bound client first, so ``call_args.args[1]`` is the shipped
  URL, and an exception-valued ``side_effect`` is raised INSIDE the shipped
  ``async with`` body - which is what lets the budget legs drive the shipped
  ``except`` arms.

Attribute NAMES are the shipped constants imported from
``backend.core/telemetry_ai_conventions.py``; their string values stay literal in
the expectations, and the ``retry_attempt`` key of L658 is quoted rather than
imported so a rename of that shipped literal is visible on its own.

Clock discipline
================
No test patches ``time.monotonic``/``perf_counter`` (the event loop's own basis)
and no test patches ``asyncio.timeout``.  The exact-millisecond legs swap only
the MODULE's own ``time`` name (``patch.object(M, "time", new=clock)``) for a
stand-in whose ``monotonic`` returns a REAL ``time.monotonic()`` reading plus a
constant offset the leg sets from INSIDE the shipped request window (the POST
hook, which runs between the L664 and L674 reads): the shipped
``(time.monotonic() - start_time) * 1000`` is then pinned to the elapsed count
the leg computes itself, so ``* 1001`` (0.1 % off), ``/ 1000`` (1e6x too small),
``(monotonic + start_time) * 1000`` (absurdly large) and ``-> None`` all fall
outside it while the shipped expression cannot.  The budget legs inject the
shipped pair with a ``0.005 + 0.005 == 0.01`` s budget against a ``0.04`` s POST,
so the lapsing ones cost tens of real milliseconds and ``asyncio.sleep`` is never
patched anywhere - the retry leg pays the shipped 1 s backoff for real.

Occurrence twins (``m7``/``m8``/``m11``/``m12``)
===============================================
The bank's before-text ``camera_id=camera_id,`` also sits at L1133 (the
``_send_detection_request`` forward inside ``detect_objects``), L1282 (the
``Detection`` constructor) and L1361 (``update_baseline``), and
``image_path=image_path,`` at L1134 and L1361.  The harness splices EVERY
candidate, so the ``detect_objects`` path runs for real here (autospec'd session,
shipped mime/threshold/bbox/clamp logic, no DB) and is read by
``test_a_healthy_detection_forwards_camera_id_to_every_shipped_call`` and
``test_a_healthy_detection_forwards_image_path_to_every_shipped_call``.  The
forward at L1129-1135 goes through the SHIPPED ``CircuitBreaker.call``, which
invokes its ``operation`` argument directly (``circuit_breaker.py:482``), and the
``_send_detection_request`` ATTRIBUTE is patched with
``autospec=True, wraps=<the shipped bound method>`` - so the forward's four
keywords are recorded (``image_data`` / ``image_name`` / ``camera_id`` /
``image_path``, the exact surface of the L1133/L1134 twins) and the shipped route
still executes.

Test -> mutant-key map (``mN`` == ``_send_detection_request__mutmut_N``)
=======================================================================
Budget (L637 with L665)
* ``m4`` (``explicit_timeout = None`` - guard disabled), ``m5`` (``Add ->
  Subtract`` - budget becomes ``-10.0``), ``m46`` (``asyncio.timeout(None)`` -
  budget computed, guard disabled) -> the three legs of
  ``test_the_request_is_cancelled_once_the_real_budget_lapses`` (parametrisation
  ``shipped`` / ``lapsed``: the shipped ``20.0 + 30.0`` pair completes inside its
  budget with no WARNING/ERROR at all, while the ``0.005 + 0.005`` pair produces
  EXACTLY the shipped timeout conversation whose text carries
  ``request timed out after {budget}s``) and
  ``test_the_budget_is_the_sum_recorded_in_the_retry_warning`` (attempt 1 of 2
  plus the full seven-field extra, then the exhausted attempt 2 of 2).

Span creation (L641-646)
* ``m6`` (name -> ``None``) -> ``test_the_span_name_is_derived_from_the_detector_type``
* ``m7``/``m11`` (``camera_id`` None/dropped) -> L643 leg of
  ``test_the_span_kwargs_are_exactly_the_three_caller_arguments`` + the L1133 /
  L1282 / L1361 twins in the ``camera_id`` storage leg
* ``m8``/``m12`` (``image_path`` None/dropped) -> same span leg + the L1134 /
  L1361 twins in the ``image_path`` storage leg
* ``m9``/``m13`` (``image_size_bytes`` None/dropped) -> that span leg (the byte
  count of the IMAGE, 27, not of the path) and
  ``test_the_storage_path_attributes_the_inference_to_this_camera``
  (``camera.id`` / ``frame.size_bytes``).

AI model attributes (L648-655)
* ``m15``/``m21`` (``model_name``), ``m16``/``m22`` (``model_version``),
  ``m17``/``m23`` (``model_provider``), ``m18``/``m24`` (``device``),
  ``m19``/``m25`` (``batch_size``), ``m35``/``m36`` (``"cuda:0"`` XX/upper),
  ``m37`` (``batch_size=2``) ->
  ``test_the_five_ai_model_attributes_land_on_the_span_with_their_shipped_values``
  (spy kwargs EXACTLY the five, then the recorder reads: None/drop is a MISSING
  key, a renamed literal a wrong value) and
  ``test_the_span_attribute_multiset_is_exactly_the_shipped_success_path``.
* the conditional's own variants ``m26`` (``and False``), ``m27`` (``or True``),
  ``m28``/``m29`` (``"huggingface"`` XX/upper), ``m30`` (``Equal -> NotEqual``),
  ``m31``/``m32`` (``"yolo26"`` XX/upper), ``m33``/``m34`` (``"ultralytics"``
  XX/upper) ->
  ``test_the_provider_follows_the_detector_type_in_both_shipped_arms``: the
  yolo26 leg reddens the ``"huggingface"``/``"yolo26"`` renames and the
  ``and False`` / ``!=`` variants, and a client whose ``_detector_type`` was
  overwritten BEFORE the call runs the shipped else-arm and reddens ``or True``
  and the ``"ultralytics"`` renames.

Retry attribute (L658)
* ``m39`` (key -> ``None``), ``m40`` (value -> ``None``), ``m43``/``m44``
  (``"retry_attempt"`` XX/upper) ->
  ``test_the_retry_attempt_attribute_names_the_attempt_number`` (the multiset
  keyed by ``repr`` - an unexpected key such as ``None`` /
  ``XXretry_attemptXX`` / ``RETRY_ATTEMPT`` is itself the failure),
  ``test_the_span_attribute_multiset_is_exactly_the_shipped_success_path`` and
  ``test_the_exhausted_retry_path_attributes_the_failure`` (``[0, 1, 2]``).

POST payload (L666-671)
* ``m47`` (``files = None``), ``m48``/``m49`` (field name XX/upper), ``m50``/``m51``
  (content type XX/upper), ``m53`` (url -> ``None``), ``m54`` (``files=None``),
  ``m57`` (``files=`` dropped) ->
  ``test_the_upload_reaches_post_as_the_shipped_multipart_triple`` (URL, the
  whole dict, the exact keyword list and the call-list identity), with
  ``test_the_post_carries_the_shipped_auth_and_correlation_headers`` as the
  header arm.

Inference duration (L673-674)
* ``m60`` (``-> None``), ``m61`` (``Multiply -> Divide``), ``m62`` (``Subtract
  -> Add``), ``m63`` (``* 1001``) ->
  ``test_the_inference_duration_is_the_elapsed_milliseconds_of_the_request_window``
  (exactly two clock reads, both helpers holding the same object, that object
  equal to the window the leg measured, and that window under 45 ms) and
  ``test_the_inference_duration_is_a_realistic_millisecond_count``.

Detections extraction (L677)
* ``m64`` (``-> None``) -> the identity pins in
  ``test_the_two_result_helpers_run_once_with_the_shipped_arguments`` (the list
  the helper receives IS ``result['detections']``) and
  ``test_the_span_detection_count_and_confidence_stats_come_from_the_payload``.
* ``m65`` (key -> ``None``), ``m66`` (default -> ``None``), ``m68`` (default
  dropped), ``m69``/``m70`` (``"detections"`` XX/upper) ->
  ``test_a_payload_without_a_detections_key_still_attributes_count_zero``: the
  key is ABSENT, so only the shipped two-argument ``.get`` yields ``[]``; each of
  those five yields ``None``, after which the shipped helper writes NO
  ``detection.count`` and the spy records ``detections=None`` - both pins redden.
* ``m72``/``m75`` (``detections``), ``m73``/``m76`` (``inference_time_ms``),
  ``m78``/``m81`` (``duration_ms``), ``m79``/``m82`` (``status``), ``m83``/``m84``
  (``"success"`` XX/upper) ->
  ``test_the_two_result_helpers_run_once_with_the_shipped_arguments`` (exact
  keyword lists + value identities),
  ``test_the_recorder_span_holds_the_duration_written_by_both_helpers``,
  ``test_the_span_attribute_multiset_is_exactly_the_shipped_success_path`` and
  ``test_the_success_path_writes_no_error_attributes``.

Controls stating the surrounding shipped contract (so no killing leg can be
satisfied by an accidental fall-through):
``test_a_successful_request_returns_the_parsed_payload_object``,
``test_the_span_is_closed_cleanly_and_the_success_path_sets_no_error``,
``test_an_empty_detections_list_is_still_reported_as_count_zero``,
``test_the_storage_path_attributes_the_inference_to_this_camera``.

L632 ``last_exception: Exception | None = None`` is dispositioned EQUIVALENT by
the manifest (``eq-lastexception-falsy-init``) and carries no key here.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import backend.services.detector_client as M
from backend.core.telemetry_ai_conventions import (
    AI_INFERENCE_BATCH_SIZE,
    AI_INFERENCE_DEVICE,
    AI_INFERENCE_DURATION_MS,
    AI_INFERENCE_STATUS,
    AI_MODEL_NAME,
    AI_MODEL_PROVIDER,
    AI_MODEL_VERSION,
    DETECTION_CLASSES,
    DETECTION_CONFIDENCE_AVG,
    DETECTION_CONFIDENCE_MAX,
    DETECTION_CONFIDENCE_MIN,
    DETECTION_COUNT,
    AIModelAttributes,
    set_detection_attributes,
    set_inference_result_attributes,
)

pytestmark = [pytest.mark.unit]

LOG_NAME = "backend.services.detector_client"
# L658's key, quoted (not imported) so a rename of the shipped literal is visible.
RETRY_ATTEMPT = "retry_attempt"

# ---- values INJECTED by this file (never shipped values) --------------------
READ_TIMEOUT = 20.0  # settings.yolo26_read_timeout
CONNECT_TIMEOUT = 30.0  # settings.ai_connect_timeout
# L637 is `self._read_timeout + settings.ai_connect_timeout`; this leg-computed
# sum is the shipped budget, while `Add -> Subtract` reads READ_TIMEOUT -
# CONNECT_TIMEOUT == -10.0 and cancels before the request body even runs.
BUDGET = READ_TIMEOUT + CONNECT_TIMEOUT
DETECTOR_URL = "http://detector.invalid:8000"
API_KEY = "sk-batch28-dc06"  # pragma: allowlist secret  # nosemgrep: hardcoded-password
IMAGE_DATA = b"fake-image-bytes-0123456789"  # len 27 - the span's image_size_bytes
IMAGE_NAME = "front-door-0001.jpg"
IMAGE_PATH = "/export/foscam/front_door/front-door-0001.jpg"
CAMERA_ID = "front_door"
FILE_TYPE = "image/jpeg"  # L1180 via get_mime_type_with_default(".jpg")
# L674: the whole request window (semaphore entry to the shipped arithmetic) is
# tens of microseconds; 45 ms leaves a slow CI two orders of magnitude of slack
# while still excluding every arithmetic mutant.
MAX_WINDOW_MS = 45.0
# L674 clock stand-in: an OFFSET added to the SECOND read only, which turns the
# shipped subtraction into ``OFFSET + real window`` seconds.  One second of offset
# is 1000 s of uptime-equivalent, so a ``+``-instead-of-``-`` mutant doubles the
# real uptime and a ``* 1001`` mutant is 1e5 ms off - both hopeless to confuse.
OFFSET = 1_000.0
# Exactness tolerance for the leg that measures the window on the real clock:
# the shipped ``json()`` read and the shipped L674 read are one statement apart.
TOLERANCE_MS = 5.0
# The budget legs: a lapSING pair is injected so the shipped guard is 10 ms and
# the POST double yields for 4x that, so the cancel is never a coin flip even on
# a starved loop.  The shipped pair (20.0 + 30.0) leaves the same POST far inside
# the guard, and the 'Add -> Subtract' budget (0.0 / -10.0) cancels BEFORE the
# POST body runs at all - a third, distinct conversation.
LAPSE_READ = 0.005
LAPSE_CONNECT = 0.005
POST_SLEEP = 0.04
# L688/L719/L763/L856: the backoff every retried arm awaits, patched out so the
# retry legs cost nothing.
BACKOFF_S = 1


# =============================================================================
# Payload + record observation
# =============================================================================


def one_detection() -> dict[str, Any]:
    """The shipped-shape payload: one confident person in a 10x10 image."""
    return {
        "detections": [{"class": "person", "confidence": 0.9, "bbox": [1, 2, 3, 4]}],
        "image_width": 10,
        "image_height": 10,
    }


def _baseline_attrs() -> frozenset[str]:
    """Attribute names that are NOT part of a shipped ``extra=`` payload.

    The union of the fields ``logging.LogRecord.__init__`` always sets and the
    fields this module's ``ContextFilter`` injects (the filter is idempotent, so
    running it once over a fresh record adds exactly the injected names).
    ``message`` is excluded - the formatter sets it.
    """
    probe = logging.LogRecord("baseline.probe", logging.DEBUG, "f", 1, "probe", (), None)
    core = set(probe.__dict__)
    injected = set(M.logger.filter(probe).__dict__) - core
    return frozenset(core | injected | {"message"})


BASELINE_ATTRS = _baseline_attrs()


def shipped_extra(record: logging.LogRecord) -> dict[str, Any]:
    """The ``extra=`` dict the shipped call passed, as the record shows it.

    ``Logger.makeRecord`` copies ``extra`` into the record verbatim, so removing
    the baseline leaves precisely the shipped payload - which is how a renamed or
    dropped KEY becomes visible.
    """
    return {k: v for k, v in record.__dict__.items() if k not in BASELINE_ATTRS}


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer."""
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def one(caplog: pytest.LogCaptureFixture, level: int, msg: str) -> logging.LogRecord:
    """Exactly one record at ``level`` from this logger, carrying this RAW text."""
    recs = at(caplog, level)
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in recs]}"
    )
    assert recs[0].msg == msg, f"log text mutated: {recs[0].msg!r} != {msg!r}"
    assert tuple(recs[0].args or ()) == (), f"unexpected lazy args: {recs[0].args!r}"
    return recs[0]


# =============================================================================
# Module clock stand-in (the real time module is never touched)
# =============================================================================


class OffsetClock:
    """The module's ``time`` name, narrowed to what L664/L674 read.

    ``monotonic`` returns a REAL ``time.monotonic()`` reading plus ``offset``, so
    the shipped subtraction stays exact and a leg that sets ``offset`` from
    inside the shipped request window turns ``(time.monotonic() - start_time) *
    1000`` into a number the leg measures itself.  ``monotonic_offset`` is the
    shipped module's other name in this class's namespace that ``_send_detection
    _request`` never reads; it exists so the stand-in cannot silently shadow a
    second read.  ``monotonic`` appears at L462, L476, L499, L572, L576, L664 and
    L674 of the shipped file and only the last two run on this path.
    """

    def __init__(self) -> None:
        self.offset = 0.0
        self.readings: list[float] = []

    def monotonic(self) -> float:
        value = time.monotonic() + self.offset
        self.readings.append(value)
        return value


@pytest.fixture
def clock() -> Any:
    """``M.time`` replaced by :class:`OffsetClock` for ONE test (``new=`` form)."""
    fake = OffsetClock()
    with patch.object(M, "time", new=fake):
        yield fake


# =============================================================================
# Settings + client construction (the shipped suite's idiom)
# =============================================================================


@pytest.fixture
def settings() -> Any:
    """``get_settings`` pinned to the values this route reads.

    The two legs L637 adds are deliberately asymmetric (``20.0`` and ``30.0``) so
    the shipped ``+`` and the ``-`` mutant give different budgets, and
    ``ai_max_concurrent_inferences`` is a value no neighbouring module uses, so
    the class-level semaphore of ``_get_semaphore()`` is always (re)built to this
    file's own limit instead of inheriting another module's.
    """
    st = MagicMock()
    st.ai_gateway_url = None
    st.use_ai_gateway = False
    st.yolo26_url = DETECTOR_URL
    st.yolo26_api_key = None
    st.yolo26_read_timeout = READ_TIMEOUT
    st.ai_connect_timeout = CONNECT_TIMEOUT
    st.ai_health_timeout = 2.0
    st.detector_max_retries = 3
    st.ai_max_concurrent_inferences = 11
    st.detection_confidence_threshold = 0.5
    st.detection_class_thresholds = {}
    st.ai_warmup_enabled = False
    st.ai_cold_start_threshold_seconds = 60.0
    with patch("backend.services.detector_client.get_settings", autospec=True) as factory:
        factory.return_value = st
        yield st


@pytest.fixture(autouse=True)
def baseline_service() -> Any:
    """The shipped suite's autouse mock of ``get_baseline_service`` (L1351)."""
    service = MagicMock()
    service.update_baseline = AsyncMock()
    with patch("backend.services.detector_client.get_baseline_service", autospec=True) as factory:
        factory.return_value = service
        yield service


@pytest.fixture
def mock_session() -> Any:
    """DB session double in the shipped suite's shape (L1335 / L1369 / L1373)."""
    session = AsyncMock(spec=AsyncSession)
    session.get = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def client(settings: Any) -> Any:
    """A REAL ``DetectorClient``: the shipped ``__init__`` runs, so the semaphore,
    persistent clients, timeout object, circuit breaker and retry loop under test
    are production code - only settings and the socket are stand-ins."""
    instance = M.DetectorClient(max_retries=1)
    assert instance._max_retries == 1  # the ctor argument wins over settings (L313)
    assert instance._read_timeout == READ_TIMEOUT
    assert instance._timeout.read == READ_TIMEOUT
    assert instance._timeout.connect == CONNECT_TIMEOUT
    yield instance


# =============================================================================
# Span recorder + telemetry spies (shipped helpers kept, wrapped)
# =============================================================================


class RecorderSpan:
    """The shipped ``SpanProtocol`` surface this code path actually writes.

    ``set_attribute`` is the only writer on the happy path (L658 directly,
    everything else through the three telemetry helpers), so reading the span
    back is what makes a dropped / ``None``-ed / renamed argument observable as a
    MISSING attribute.  ``keys``/``items``/``get``/``__getitem__``/
    ``__contains__``/``__len__`` are a read-only view for the assertions, never a
    second store.
    """

    def __init__(self) -> None:
        self.attrs: dict[str, Any] = {}
        self.setattr_calls: list[tuple[str, Any]] = []
        self.end_calls: list[dict[str, Any]] = []
        self.event_calls: list[tuple[str, Any]] = []
        self.status_calls: list[Any] = []
        self.exception_calls: list[Any] = []

    # --- shipped span surface -------------------------------------------------
    def set_attribute(self, key: str, value: Any) -> None:
        self.setattr_calls.append((key, value))
        self.attrs[key] = value

    def add_event(self, name: str, attributes: Any = None, **kwargs: Any) -> None:
        self.event_calls.append((name, attributes if attributes is not None else kwargs))

    def record_exception(self, exception: BaseException, **kwargs: Any) -> None:
        self.exception_calls.append((exception, kwargs))

    def set_status(self, status: Any = None, **kwargs: Any) -> None:
        self.status_calls.append((status, kwargs))

    def is_recording(self) -> bool:
        return True

    def end(self, **kwargs: Any) -> None:
        self.end_calls.append(dict(kwargs))

    # --- read-only view for assertions ----------------------------------------
    def keys(self) -> list[str]:
        return list(self.attrs)

    def items(self) -> list[tuple[str, Any]]:
        return list(self.attrs.items())

    def get(self, key: str, default: Any = None) -> Any:
        return self.attrs.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.attrs[key]

    def __contains__(self, key: object) -> bool:
        return key in self.attrs

    def __len__(self) -> int:
        return len(self.attrs)


@contextlib.contextmanager
def _yields(recorder: RecorderSpan) -> Any:
    """``trace_span``'s fake body: the shipped ``as span`` binds ``recorder``."""
    yield recorder


class Telemetry:
    """The four module-level telemetry collaborators, spied by name inside ``M``.

    The three helpers are autospec'd with ``wraps=`` pointing at the SHIPPED
    callables, so the real writer runs against the recorder AND the spy keeps the
    shipped call's exact keyword list; ``trace_span`` is a mock so the ``with``
    binds our recorder as the span.
    """

    def __init__(self) -> None:
        self.span = RecorderSpan()
        self.trace_span = MagicMock(name="trace_span", side_effect=self._open_recorder_span)
        self.model: Any = None
        self.detections: Any = None
        self.result: Any = None

    def _open_recorder_span(self, *_args: Any, **_kwargs: Any) -> Any:
        """The ``trace_span`` double's side effect: hand back the recorder as a CM.

        A bound method rather than a lambda, so the two ignored parameters cost
        nothing to the lint gate (ARG002 is ignored in tests, ARG005 is not).
        """
        return _yields(self.span)

    def attach(self, stack: contextlib.ExitStack) -> None:
        stack.enter_context(patch.object(M, "trace_span", new=self.trace_span))
        self.model = stack.enter_context(
            patch.object(
                M.AIModelAttributes,
                "set_on_span",
                autospec=True,
                wraps=AIModelAttributes.set_on_span,
            )
        )
        self.detections = stack.enter_context(
            patch.object(
                M, "set_detection_attributes", autospec=True, wraps=set_detection_attributes
            )
        )
        self.result = stack.enter_context(
            patch.object(
                M,
                "set_inference_result_attributes",
                autospec=True,
                wraps=set_inference_result_attributes,
            )
        )

    @property
    def span_call(self) -> Any:
        assert self.trace_span.call_count == 1, (
            f"expected exactly one span open, got {self.trace_span.call_count}"
        )
        return self.trace_span.call_args

    def attr_values(self, key: str) -> list[Any]:
        return [value for name, value in self.span.setattr_calls if name == key]

    def multiset(self) -> dict[str, list[Any]]:
        out: dict[str, list[Any]] = {}
        for name, value in self.span.setattr_calls:
            out.setdefault(repr(name), []).append(value)
        return out


@pytest.fixture
def telemetry() -> Any:
    """Shipped telemetry collaborators replaced by in-module name-spies."""
    tele = Telemetry()
    with contextlib.ExitStack() as stack:
        tele.attach(stack)
        yield tele


# =============================================================================
# Transport stand-ins
# =============================================================================


def response(body: dict[str, Any], *, mark: Any = None) -> Any:
    """A 200 response: ``raise_for_status()`` passes, ``json()`` returns ``body``."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    if mark is None:
        resp.json.return_value = body
    else:

        def _json(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            mark(time.monotonic())
            return body

        resp.json.side_effect = _json
    return resp


def posted(**kwargs: Any) -> Any:
    """Autospec'd ``httpx.AsyncClient.post`` (the shipped persistent client's type).

    Autospec records the bound client first, so ``call_args.args[1]`` is the
    shipped URL.  Pass ``side_effect=responder(...)`` (a coroutine FUNCTION, which
    the mock protocol awaits before the shipped ``await`` receives it) or
    ``side_effect=<exception>`` (which the mock raises INSIDE the shipped
    ``async with`` body, straight into the shipped ``except`` arms).
    """
    return patch.object(M.httpx.AsyncClient, "post", autospec=True, **kwargs)


def responder(
    body: dict[str, Any],
    *,
    sleep_s: float = 0.0,
    hook: Any = None,
    mark: Any = None,
    boom: Any = None,
) -> Any:
    """A POST double as a coroutine function: hook, yield, then the response - or the error.

    Handing the mock an ``async def`` (rather than a lambda that builds a
    coroutine) is what makes the shipped ``await`` receive the RESPONSE instead of
    an un-awaited coroutine object.  ``hook`` runs inside the shipped request
    window, before the POST; ``mark`` is wired into the response double's
    ``json()``, so it runs at the shipped L673 - one statement before the L674
    clock read - and gives the leg a real-clock stamp of the window's END.
    """

    async def _post(*_args: Any, **_kwargs: Any) -> Any:
        if hook is not None:
            hook()
        if sleep_s:
            await asyncio.sleep(sleep_s)
        if boom is not None:
            raise boom
        return response(body, mark=mark)

    return _post


# =============================================================================
# Happy path: the returned payload, the transport call, the span lifecycle
# =============================================================================


@pytest.mark.asyncio
async def test_a_successful_request_returns_the_parsed_payload_object(
    client: Any, telemetry: Telemetry
) -> None:
    """L673/L686: the parsed JSON object is handed straight back, after ONE post."""
    body = one_detection()
    with posted(side_effect=responder(body)) as mock_post:
        result = await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    assert result is body
    assert mock_post.call_count == 1, "the success path posts once - no retry"
    assert telemetry.span.exception_calls == []
    assert telemetry.span.event_calls == []
    assert telemetry.span.status_calls == []


@pytest.mark.asyncio
async def test_the_upload_reaches_post_as_the_shipped_multipart_triple(
    client: Any, telemetry: Telemetry
) -> None:
    """L666-671: ``{"file": (image_name, image_data, "image/jpeg")}`` at ``<url>/detect``.

    The ``files`` dict is pinned whole (a renamed field or content type is a
    different dict, not merely a different key) and so is the shipped keyword
    list, which is what makes a dropped ``files=`` visible.
    """
    with posted(side_effect=responder(one_detection())) as mock_post:
        await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    args, kwargs = mock_post.call_args
    assert len(args) == 2, f"the shipped call is (client, url): {args!r}"
    assert args[1] == f"{DETECTOR_URL}/detect"
    assert kwargs["files"] == {"file": (IMAGE_NAME, IMAGE_DATA, "image/jpeg")}
    assert list(kwargs) == ["files", "headers"]
    assert next(iter(mock_post.call_args_list)) is mock_post.call_args


@pytest.mark.asyncio
async def test_the_post_carries_the_shipped_auth_and_correlation_headers(
    settings: Any, telemetry: Telemetry
) -> None:
    """L670: the header dict IS the shipped ``_get_auth_headers()`` (correlation + key).

    The key is injected BEFORE construction because L288/L405-413 read it once in
    ``__init__`` and then only from the instance.
    """
    settings.yolo26_api_key = API_KEY
    keyed = M.DetectorClient(max_retries=1)
    assert keyed._get_auth_headers() == {"X-API-Key": API_KEY}
    with (
        patch.object(
            M, "get_correlation_headers", autospec=True, return_value={"traceparent": "00-t"}
        ),
        posted(side_effect=responder(one_detection())) as mock_post,
    ):
        await keyed._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)
        assert keyed._get_auth_headers() == {"traceparent": "00-t", "X-API-Key": API_KEY}

    assert mock_post.call_args.kwargs["headers"] == {"traceparent": "00-t", "X-API-Key": API_KEY}


@pytest.mark.asyncio
async def test_the_span_is_closed_cleanly_and_the_success_path_sets_no_error(
    client: Any, telemetry: Telemetry
) -> None:
    """L641-686: the span exits without status/exception; the error teardown is retry-only."""
    with posted(side_effect=responder(one_detection())):
        await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    assert telemetry.span.end_calls == []
    assert telemetry.span.status_calls == []
    assert telemetry.span.exception_calls == []
    assert "error" not in telemetry.span
    assert "error.message" not in telemetry.span


# =============================================================================
# L641-646: span name + the three initial attributes
# =============================================================================


@pytest.mark.asyncio
async def test_the_span_kwargs_are_exactly_the_three_caller_arguments(
    client: Any, telemetry: Telemetry
) -> None:
    """L643-645: ``camera_id``, ``image_path`` and ``len(image_data)`` open the span.

    ``image_size_bytes`` is the byte count of the IMAGE (27), not of the path
    string, and those three keywords are the shipped set: no extra, none missing.
    """
    with posted(side_effect=responder(one_detection())):
        await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    _args, kwargs = telemetry.span_call
    assert kwargs == {
        "camera_id": CAMERA_ID,
        "image_path": IMAGE_PATH,
        "image_size_bytes": len(IMAGE_DATA),
    }
    assert kwargs["image_size_bytes"] == 27
    # The shipped write order: the AI-model block (L648) precedes the retry loop
    # (L657), so the very first attribute the span is handed is the model name.
    assert telemetry.span.setattr_calls[0] == (AI_MODEL_NAME, "yolo26")
    assert RETRY_ATTEMPT in telemetry.span


@pytest.mark.asyncio
async def test_the_span_name_is_derived_from_the_detector_type(
    client: Any, telemetry: Telemetry
) -> None:
    """L642: ``f"{self._detector_type}_detection_request"`` - the positional span name."""
    with posted(side_effect=responder(one_detection())):
        await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)
    assert telemetry.trace_span.call_args_list[0].args == ("yolo26_detection_request",)

    renamed = M.DetectorClient(max_retries=1)
    renamed._detector_type = "other"
    assert renamed._detector_type == "other"
    with posted(side_effect=responder(one_detection())):
        await renamed._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)
    # L642 interpolates the attribute: whatever it holds now IS the span name.
    assert telemetry.trace_span.call_args_list[1].args == (
        f"{renamed._detector_type}_detection_request",
    )
    assert telemetry.trace_span.call_count == 2


# =============================================================================
# L648-655: AI model semantic attributes
# =============================================================================


@pytest.mark.asyncio
async def test_the_five_ai_model_attributes_land_on_the_span_with_their_shipped_values(
    client: Any, telemetry: Telemetry
) -> None:
    """L648-655: five keywords, each landing on the span under its shipped key.

    Both surfaces are read: the spy's keyword list (so a dropped keyword is an
    ABSENT key, never a silently-defaulted one) and the recorder the shipped
    helper wrote (so a ``None`` or dropped value is a MISSING attribute and a
    renamed literal is a wrong value).  ``model_name``/``model_version`` are
    re-derived from the live attributes - the shipped line passes those
    attributes, so a renamed ``"yolo26"`` COMPARATOR (m31/m32) is a name mutation
    at L650 too and only a live read keeps this leg exact for that twin.
    """
    with posted(side_effect=responder(one_detection())):
        await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    assert telemetry.model.call_count == 1
    call = telemetry.model.call_args
    assert call.args == (telemetry.span,)
    assert list(call.kwargs) == [
        "model_name",
        "model_version",
        "model_provider",
        "device",
        "batch_size",
    ]
    assert call.kwargs["model_name"] == client._detector_type
    assert call.kwargs["model_version"] == client._model_version
    assert call.kwargs["model_provider"] == "huggingface"
    assert call.kwargs["device"] == "cuda:0"
    assert call.kwargs["batch_size"] == 1
    assert telemetry.span[AI_MODEL_NAME] == client._detector_type
    assert telemetry.span[AI_MODEL_VERSION] == client._model_version
    assert telemetry.span[AI_MODEL_PROVIDER] == "huggingface"
    assert telemetry.span[AI_INFERENCE_DEVICE] == "cuda:0"
    assert telemetry.span[AI_INFERENCE_BATCH_SIZE] == 1


@pytest.mark.asyncio
async def test_the_provider_follows_the_detector_type_in_both_shipped_arms(
    client: Any, telemetry: Telemetry
) -> None:
    """L652: ``"huggingface" if self._detector_type == "yolo26" else "ultralytics"``.

    Neither arm alone pins the conditional.  The yolo26 arm reddens ``and False``,
    ``!=``, the renamed comparator and the renamed ``"huggingface"``; a client
    whose ``_detector_type`` was overwritten BEFORE the call runs the shipped
    else-arm and reddens ``or True`` and the renamed ``"ultralytics"``.  The
    expected provider is re-derived with the shipped comparator on the live
    attribute, so a comparator rename cannot fake a pass.
    """
    with posted(side_effect=responder(one_detection())):
        await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)
    assert client._detector_type == "yolo26"
    assert telemetry.span[AI_MODEL_PROVIDER] == "huggingface"

    renamed = M.DetectorClient(max_retries=1)
    renamed._detector_type = "other"
    assert renamed._detector_type == "other"
    with posted(side_effect=responder(one_detection())):
        await renamed._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)
    expected = "huggingface" if renamed._detector_type == "yolo26" else "ultralytics"
    assert expected == "ultralytics"
    assert telemetry.model.call_args.kwargs["model_provider"] == expected
    assert telemetry.span[AI_MODEL_PROVIDER] == expected


# =============================================================================
# L657-658: the retry_attempt attribute
# =============================================================================


@pytest.mark.asyncio
async def test_the_retry_attempt_attribute_names_the_attempt_number(
    client: Any, telemetry: Telemetry
) -> None:
    """L658: ``set_attribute("retry_attempt", attempt)`` - key AND value, together.

    The multiset is keyed by ``repr`` of the written key, so the ``None``-key
    mutant, the ``XXretry_attemptXX`` rename and the ``RETRY_ATTEMPT`` upper all
    surface as an UNEXPECTED key next to a missing shipped one.
    """
    with posted(side_effect=responder(one_detection())):
        await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    assert telemetry.attr_values(RETRY_ATTEMPT) == [0]
    assert telemetry.multiset()["'retry_attempt'"] == [0]
    assert "'None'" not in telemetry.multiset()


@pytest.mark.asyncio
async def test_the_exhausted_retry_path_attributes_the_failure(
    client: Any, telemetry: Telemetry, caplog: pytest.LogCaptureFixture
) -> None:
    """L657-658 across three attempts, then the shipped retry-exhaustion teardown.

    ``_max_retries`` is overridden on the instance BEFORE the call (the ctor arm at
    L313 stays pinned by the ``client`` fixture), so the shipped
    ``range(self._max_retries)`` still governs; the backoff sleeps are autospec'd
    out and every attempt posts.
    """
    client._max_retries = 3
    assert client._max_retries == 3
    win(caplog)
    with (
        posted(
            side_effect=responder(one_detection(), boom=httpx.TimeoutException("boom"))
        ) as mock_post,
        patch.object(M.asyncio, "sleep", autospec=True, return_value=None) as slept,
    ):
        with pytest.raises(M.DetectorUnavailableError) as excinfo:
            await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    assert mock_post.call_count == 3
    assert [s.args[0] for s in slept.call_args_list] == [BACKOFF_S, BACKOFF_S * 2]
    assert telemetry.attr_values(RETRY_ATTEMPT) == [0, 1, 2]
    assert isinstance(excinfo.value.original_error, httpx.TimeoutException)
    assert telemetry.span["error"] is True
    assert telemetry.span["error.message"] == "Detection failed after 3 attempts"
    assert telemetry.attr_values(AI_INFERENCE_STATUS) == []
    assert [r.msg for r in at(caplog, logging.WARNING)] == [
        "Detector timeout, retrying",
        "Detector timeout, retrying",
    ]
    error = one(caplog, logging.ERROR, "Detector timeout after all attempts")
    assert shipped_extra(error) == {
        "detector_type": "yolo26",
        "camera_id": CAMERA_ID,
        "file_path": IMAGE_PATH,
        "attempts": 3,
        "error": "boom",
    }


# =============================================================================
# L673-674: the inference duration
# =============================================================================


@pytest.mark.asyncio
async def test_the_inference_duration_is_the_elapsed_milliseconds_of_the_request_window(
    client: Any, telemetry: Telemetry, clock: OffsetClock
) -> None:
    """L664 + L674 on a real clock plus the leg's own offset: exactly ``elapsed_ms``.

    ``clock.offset`` is set from INSIDE the shipped window (the POST hook, which
    runs between the L664 and L674 reads), so the subtraction carries a known
    ``OFFSET`` seconds on top of the real window and every arithmetic mutant is
    pushed far outside an exact tolerance: ``* 1001`` lands ``0.1 %`` of ``1e9 ms``
    away (1e5 ms), ``(monotonic + start_time) * 1000`` lands near ``2e9``, ``/ 1000``
    lands near ``1.0`` and ``-> None`` writes nothing at all.  The independent
    estimate of the window's END is taken by the response double itself at the
    L673 ``json()`` call - one shipped statement before the L674 read - on the
    REAL clock, while ``readings[0]`` is the shipped L664 read itself.
    """
    marks: list[float] = []

    def hook() -> None:
        clock.offset = OFFSET

    body = one_detection()
    with posted(side_effect=responder(body, hook=hook, mark=marks.append)):
        await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    assert len(clock.readings) == 2, f"L664 then L674: {clock.readings!r}"
    assert len(marks) == 1, f"the shipped json() read runs once: {marks!r}"
    window_ms = (marks[0] - clock.readings[0] + OFFSET) * 1000
    durations = telemetry.attr_values(AI_INFERENCE_DURATION_MS)
    assert len(durations) == 2
    assert durations[0] is durations[1]
    assert durations[0] == pytest.approx(window_ms, abs=TOLERANCE_MS)
    assert OFFSET * 1000 < durations[0] <= OFFSET * 1000 + MAX_WINDOW_MS, (
        f"the window beyond the shipped offset must stay under {MAX_WINDOW_MS} ms"
    )


@pytest.mark.asyncio
async def test_the_inference_duration_is_a_realistic_millisecond_count(
    client: Any, telemetry: Telemetry
) -> None:
    """Real-clock control: a positive millisecond count, never a raw seconds delta."""
    with posted(side_effect=responder(one_detection(), sleep_s=0.005)):
        await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    durations = telemetry.attr_values(AI_INFERENCE_DURATION_MS)
    assert len(durations) == 2
    assert durations[0] is durations[1]
    assert isinstance(durations[0], float)
    assert 0.05 < durations[0] <= MAX_WINDOW_MS, (
        f"a 5 ms request must read as single-digit milliseconds: {durations[0]}"
    )


# =============================================================================
# L677-685: the two result helpers
# =============================================================================


@pytest.mark.asyncio
async def test_the_two_result_helpers_run_once_with_the_shipped_arguments(
    client: Any, telemetry: Telemetry
) -> None:
    """L677-685: what the shipped helpers receive, by identity and by keyword list.

    ``result`` is the parsed object (L673), so ``detections`` IS the list the
    payload carries (L677/L678) and ``inference_time_ms`` / ``duration_ms`` are
    the same object as each other (L674/L681/L684).  The keyword LIST is pinned
    because the shipped helpers default every parameter: a dropped keyword leaves
    the written attributes looking identical, and only the recorded call shows
    the difference.
    """
    body = one_detection()
    with posted(side_effect=responder(body)):
        out = await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    assert out is body
    assert telemetry.detections.call_count == 1
    assert telemetry.result.call_count == 1
    det = telemetry.detections.call_args
    res = telemetry.result.call_args
    assert det.args == (telemetry.span,)
    assert list(det.kwargs) == ["detections", "inference_time_ms"]
    assert det.kwargs["detections"] is body["detections"]
    assert det.kwargs["inference_time_ms"] is not None
    assert res.args == (telemetry.span,)
    assert list(res.kwargs) == ["duration_ms", "status"]
    assert res.kwargs["duration_ms"] is det.kwargs["inference_time_ms"]
    assert res.kwargs["status"] == "success"


@pytest.mark.asyncio
async def test_the_span_detection_count_and_confidence_stats_come_from_the_payload(
    client: Any, telemetry: Telemetry
) -> None:
    """L677-681: the shipped helper derives five values from the extracted list.

    ``detections`` is never written as an attribute, so those five values exist
    only while L677 hands the helper the payload's list.
    """
    with posted(side_effect=responder(one_detection())):
        await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    assert telemetry.span[DETECTION_COUNT] == 1
    assert telemetry.span[DETECTION_CONFIDENCE_AVG] == 0.9
    assert telemetry.span[DETECTION_CONFIDENCE_MIN] == 0.9
    assert telemetry.span[DETECTION_CONFIDENCE_MAX] == 0.9
    assert telemetry.span[DETECTION_CLASSES] == "person"
    assert "detections" not in telemetry.span


@pytest.mark.asyncio
async def test_a_payload_without_a_detections_key_still_attributes_count_zero(
    client: Any, telemetry: Telemetry
) -> None:
    """L677 default arm: the key is ABSENT, so only the shipped two-argument ``.get`` gives [].

    ``result.get(None, [])`` / ``.get("detections", None)`` / ``.get("detections")``
    / the two renamed keys all yield ``None``; the spy then records
    ``detections=None`` and the shipped helper writes NO ``detection.count`` - both
    pins redden.
    """
    body: dict[str, Any] = {"image_width": 10, "image_height": 10}
    with posted(side_effect=responder(body)):
        out = await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    assert out is body
    assert telemetry.detections.call_args.kwargs["detections"] == []
    assert telemetry.attr_values(DETECTION_COUNT) == [0]
    assert telemetry.span[DETECTION_COUNT] == 0
    assert telemetry.attr_values(DETECTION_CONFIDENCE_AVG) == []
    assert telemetry.attr_values(DETECTION_CLASSES) == []
    assert telemetry.result.call_count == 1


@pytest.mark.asyncio
async def test_an_empty_detections_list_is_still_reported_as_count_zero(
    client: Any, telemetry: Telemetry
) -> None:
    """The shipped empty-list arm: ``detection.count`` 0 and no confidence statistics."""
    body = {"detections": [], "image_width": 10, "image_height": 10}
    with posted(side_effect=responder(body)):
        out = await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    assert out is body
    assert telemetry.detections.call_args.kwargs["detections"] is body["detections"]
    assert telemetry.span[DETECTION_COUNT] == 0
    assert telemetry.attr_values(DETECTION_CONFIDENCE_AVG) == []


@pytest.mark.asyncio
async def test_the_recorder_span_holds_the_duration_written_by_both_helpers(
    client: Any, telemetry: Telemetry
) -> None:
    """L681 + L684 both write ``ai.inference.duration_ms``: two calls, one value, never ``None``."""
    with posted(side_effect=responder(one_detection())):
        await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    durations = telemetry.attr_values(AI_INFERENCE_DURATION_MS)
    assert len(durations) == 2, f"both result helpers must write it: {durations}"
    assert durations[0] is durations[1]
    assert durations[0] is not None
    assert telemetry.attr_values(AI_INFERENCE_STATUS) == ["success"]


@pytest.mark.asyncio
async def test_the_span_attribute_multiset_is_exactly_the_shipped_success_path(
    client: Any, telemetry: Telemetry
) -> None:
    """The complete key/value multiset of one success: nothing extra, nothing missing.

    Keys are compared as ``repr`` of what the span was handed, so a renamed or
    ``None``-ed key is an UNEXPECTED entry as well as a missing shipped one.  The
    two duration entries are read back from the recorder (their exact value is
    pinned against an independent measurement elsewhere); what this leg owns is
    that the success path writes EXACTLY these thirteen keys in EXACTLY this
    multiplicity.
    """
    with posted(side_effect=responder(one_detection(), sleep_s=0.002)):
        await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    durations = telemetry.attr_values(AI_INFERENCE_DURATION_MS)
    assert len(durations) == 2 and durations[0] is durations[1]
    assert telemetry.multiset() == {
        "'retry_attempt'": [0],
        f"'{AI_MODEL_NAME}'": ["yolo26"],
        f"'{AI_MODEL_VERSION}'": ["yolo26m"],
        f"'{AI_MODEL_PROVIDER}'": ["huggingface"],
        f"'{AI_INFERENCE_DEVICE}'": ["cuda:0"],
        f"'{AI_INFERENCE_BATCH_SIZE}'": [1],
        f"'{AI_INFERENCE_DURATION_MS}'": durations,
        f"'{DETECTION_COUNT}'": [1],
        f"'{DETECTION_CONFIDENCE_AVG}'": [0.9],
        f"'{DETECTION_CONFIDENCE_MIN}'": [0.9],
        f"'{DETECTION_CONFIDENCE_MAX}'": [0.9],
        f"'{DETECTION_CLASSES}'": ["person"],
        f"'{AI_INFERENCE_STATUS}'": ["success"],
    }
    assert len(telemetry.span.setattr_calls) == 14


@pytest.mark.asyncio
async def test_the_success_path_writes_no_error_attributes(
    client: Any, telemetry: Telemetry
) -> None:
    """Status is the literal ``"success"`` and no retry-exhaustion key appears on a 200."""
    with posted(side_effect=responder(one_detection())):
        await client._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    assert telemetry.span[AI_INFERENCE_STATUS] == "success"
    assert "error" not in telemetry.span
    assert "error.message" not in telemetry.span
    assert len(telemetry.span) == 13


# =============================================================================
# L637 / L665: the explicit asyncio.timeout budget (m4, m5, m46)
# =============================================================================


@pytest.mark.parametrize("which", ["shipped", "lapsed"])
@pytest.mark.asyncio
async def test_the_request_is_cancelled_once_the_real_budget_lapses(
    settings: Any, telemetry: Telemetry, caplog: pytest.LogCaptureFixture, which: str
) -> None:
    """L637 + L665: the guard is ``read_timeout + ai_connect_timeout``, and its text says so.

    Two legs over the INJECTED settings pair, so the budget is never a shipped
    default.  Shipped (``20.0 + 30.0 = 50.0``) the 40 ms POST finishes long before
    the guard and the route logs no warning and no error at all.  Lapsed
    (``0.005 + 0.005 = 0.01``) the same POST is cancelled at 10 ms and lands in the
    shipped ``except TimeoutError`` arm (L748-783), whose text embeds the budget.

    That pair separates all three budget mutants by OBSERVATION SHAPE, not by
    arithmetic luck: ``explicit_timeout = None`` (m4) and ``asyncio.timeout(None)``
    (m46) disable the guard, so the lapsed leg returns the payload with no records
    (the ``pytest.raises`` reddens); ``Add -> Subtract`` (m5) reads ``0.0`` in the
    lapsed leg and ``-10.0`` in the shipped one, so it either fires with the text
    ``timed out after 0.0s`` or fires at all where shipped must not - both break
    the pins below.
    """
    if which == "lapsed":
        settings.yolo26_read_timeout = LAPSE_READ
        settings.ai_connect_timeout = LAPSE_CONNECT
    budget = settings.yolo26_read_timeout + settings.ai_connect_timeout
    instance = M.DetectorClient(max_retries=1)
    assert instance._read_timeout == settings.yolo26_read_timeout
    body = one_detection()
    win(caplog)
    with posted(side_effect=responder(body, sleep_s=POST_SLEEP)) as mock_post:
        if which == "shipped":
            assert budget == BUDGET
            out = await instance._send_detection_request(
                IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH
            )
            assert out is body
            assert mock_post.call_count == 1
            assert at(caplog, logging.WARNING) == []
            assert at(caplog, logging.ERROR) == []
            assert telemetry.attr_values(AI_INFERENCE_STATUS) == ["success"]
            return

        assert budget == LAPSE_READ + LAPSE_CONNECT
        with pytest.raises(M.DetectorUnavailableError) as excinfo:
            await instance._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    assert mock_post.call_count == 1
    assert isinstance(excinfo.value.original_error, TimeoutError)
    assert telemetry.attr_values(RETRY_ATTEMPT) == [0]
    assert telemetry.attr_values(AI_INFERENCE_DURATION_MS) == []
    assert telemetry.attr_values(AI_INFERENCE_STATUS) == []
    assert telemetry.span["error"] is True
    assert telemetry.span["error.message"] == "Detection failed after 1 attempts"
    error = one(
        caplog,
        logging.ERROR,
        f"Detector asyncio timeout after 1 attempts: request timed out after {budget}s",
    )
    assert shipped_extra(error) == {
        "detector_type": "yolo26",
        "camera_id": CAMERA_ID,
        "file_path": IMAGE_PATH,
        "attempts": 1,
        "explicit_timeout": budget,
    }


@pytest.mark.asyncio
async def test_the_budget_is_the_sum_recorded_in_the_retry_warning(
    settings: Any, telemetry: Telemetry, caplog: pytest.LogCaptureFixture
) -> None:
    """L755-767 on a retried attempt: the WARNING names the same budget, and the loop continues.

    ``_max_retries`` is overridden on the instance (the ctor arm at L313 stays
    pinned by the ``client`` fixture) and BOTH attempts lapse inside the 10 ms
    budget, so the leg sees attempt 1 of 2 followed by attempt 2 of 2.  The
    shipped ``await asyncio.sleep(delay)`` at L767 is NOT patched - the leg pays
    its real ``2**0 == 1`` second once, because patching the event loop's own
    sleep would also silence the delay the POST double depends on.
    """
    settings.yolo26_read_timeout = LAPSE_READ
    settings.ai_connect_timeout = LAPSE_CONNECT
    budget = settings.yolo26_read_timeout + settings.ai_connect_timeout
    instance = M.DetectorClient(max_retries=1)
    instance._max_retries = 2
    assert instance._max_retries == 2
    win(caplog)
    with posted(side_effect=responder(one_detection(), sleep_s=POST_SLEEP)) as mock_post:
        with pytest.raises(M.DetectorUnavailableError):
            await instance._send_detection_request(IMAGE_DATA, IMAGE_NAME, CAMERA_ID, IMAGE_PATH)

    assert mock_post.call_count == 2
    warning = one(
        caplog,
        logging.WARNING,
        f"Detector asyncio timeout (attempt 1/2), retrying in {BACKOFF_S}s: "
        f"request timed out after {budget}s",
    )
    assert shipped_extra(warning) == {
        "detector_type": "yolo26",
        "camera_id": CAMERA_ID,
        "file_path": IMAGE_PATH,
        "attempt": 1,
        "max_retries": 2,
        "retry_delay": BACKOFF_S,
        "explicit_timeout": budget,
    }
    assert telemetry.attr_values(RETRY_ATTEMPT) == [0, 1]
    assert telemetry.attr_values(AI_INFERENCE_STATUS) == []
    error = one(
        caplog,
        logging.ERROR,
        f"Detector asyncio timeout after 2 attempts: request timed out after {budget}s",
    )
    assert shipped_extra(error) == {
        "detector_type": "yolo26",
        "camera_id": CAMERA_ID,
        "file_path": IMAGE_PATH,
        "attempts": 2,
        "explicit_timeout": budget,
    }


# =============================================================================
# Storage-path twins of L643/L644 (the other occurrences of m7/m8/m11/m12)
# =============================================================================


def _inline_offload(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Run an ``asyncio.to_thread`` offload on the current loop (L1083)."""
    return fn(*args, **kwargs)


@pytest.fixture
def storage_route(settings: Any) -> Any:
    """The shipped ``detect_objects`` route with only I/O, the socket and the DB stubbed.

    ``_send_detection_request`` stays SHIPPED and reachable: the forward at
    L1129-1135 goes through the shipped ``CircuitBreaker.call``, which invokes its
    ``operation`` argument directly (``circuit_breaker.py:482``), so the autospec'd ``wraps`` spy on the
    INSTANCE attribute records exactly the four keyword arguments the shipped
    forward passed - ``autospec`` of a BOUND method takes ``self`` out of the
    signature, so the record is ``call(image_data=..., image_name=...,
    camera_id=..., image_path=...)``, which is precisely the surface L1133/L1134
    mutate - while the shipped method still runs (against a 200 double) and
    returns the payload.
    """
    instance = M.DetectorClient(max_retries=1)
    assert instance._confidence_threshold == 0.5
    body = one_detection()
    with (
        patch.object(M.Path, "exists", autospec=True, return_value=True),
        patch.object(M.Path, "read_bytes", autospec=True, return_value=IMAGE_DATA),
        patch.object(
            instance, "_validate_image_for_detection_async", autospec=True, return_value=True
        ),
        patch.object(M.asyncio, "to_thread", autospec=True, side_effect=_inline_offload),
        patch.object(
            M, "get_inference_semaphore", autospec=True, return_value=asyncio.Semaphore(4)
        ),
        patch.object(M, "get_correlation_headers", autospec=True, return_value={}),
        patch.object(
            instance,
            "_send_detection_request",
            autospec=True,
            wraps=instance._send_detection_request,
        ),
        posted(side_effect=responder(body)),
    ):
        yield instance


@pytest.mark.asyncio
async def test_a_healthy_detection_forwards_camera_id_to_every_shipped_call(
    storage_route: Any, mock_session: Any, baseline_service: Any
) -> None:
    """L1133 / L1282 / L1361: the three OTHER homes of ``camera_id=camera_id,``.

    The bank's before-text for ``m7``/``m11`` matches all four sites and the
    harness splices each, so all of them are read: the forwarded call's keyword
    map, the ``Detection.camera_id`` the shipped constructor stores and the
    ``update_baseline`` keyword.
    """
    stored = await storage_route.detect_objects(IMAGE_PATH, CAMERA_ID, mock_session)

    fwd = storage_route._send_detection_request.call_args
    assert fwd.args == ()
    assert fwd.kwargs == {
        "image_data": IMAGE_DATA,
        "image_name": IMAGE_NAME,
        "camera_id": CAMERA_ID,
        "image_path": IMAGE_PATH,
    }
    assert list(fwd.kwargs) == ["image_data", "image_name", "camera_id", "image_path"]

    assert len(stored) == 1
    assert stored[0].camera_id == CAMERA_ID
    assert stored[0].object_type == "person"
    assert stored[0].file_path == IMAGE_PATH
    assert stored[0].file_type == FILE_TYPE
    assert mock_session.add.call_count == 1
    assert mock_session.add.call_args.args == (stored[0],)

    assert baseline_service.update_baseline.call_count == 1
    assert baseline_service.update_baseline.call_args.kwargs["camera_id"] == CAMERA_ID


@pytest.mark.asyncio
async def test_a_healthy_detection_forwards_image_path_to_every_shipped_call(
    storage_route: Any, mock_session: Any, baseline_service: Any
) -> None:
    """L1134 / L1361: the two other homes of ``image_path=image_path,`` (m8 / m12)."""
    stored = await storage_route.detect_objects(IMAGE_PATH, CAMERA_ID, mock_session)

    assert storage_route._send_detection_request.call_args.kwargs["image_path"] == IMAGE_PATH
    assert len(stored) == 1
    assert stored[0].file_path == IMAGE_PATH
    baseline_kwargs = baseline_service.update_baseline.call_args.kwargs
    assert list(baseline_kwargs) == ["camera_id", "detection_class", "timestamp", "session"]
    assert baseline_kwargs["camera_id"] == CAMERA_ID


@pytest.mark.asyncio
async def test_the_storage_path_attributes_the_inference_to_this_camera(
    storage_route: Any, mock_session: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L1113-1150 (control): the span events around the request name this camera.

    ``camera.id`` / ``file.path`` / ``frame.size_bytes`` are built from the same
    caller arguments L643-645 forwards into the request span, so a mis-wired
    forward shows up here as well as in the request-span legs.
    """
    win(caplog)
    stored = await storage_route.detect_objects(IMAGE_PATH, CAMERA_ID, mock_session)

    assert len(stored) == 1
    assert stored[0].video_width == 10
    assert stored[0].confidence == 0.9
    assert at(caplog, logging.WARNING) == []
    assert at(caplog, logging.ERROR) == []
    final = one(caplog, logging.INFO, "Stored detections")
    extra = shipped_extra(final)
    assert extra["camera_id"] == CAMERA_ID
    assert extra["file_path"] == IMAGE_PATH
    assert extra["detection_count"] == 1
    assert isinstance(extra["duration_ms"], int)
    assert math.isfinite(extra["duration_ms"])
