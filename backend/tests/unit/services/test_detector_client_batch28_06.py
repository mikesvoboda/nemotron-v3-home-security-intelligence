r"""S2 batch-28 lane L5 - ``detector_client`` group dc07 kill battery (90 keys).

Source: ``backend/services/detector_client.py``, md5 ``294c938abe9e37cd0f979f9357982753``.
Manifest: ``/tmp/wp-pw/detector_client/manifest.json`` group
``dc07-send-connection-timeout-retry-logs`` (90 KILLABLE keys; keys file
``manifest_groups/dc07-send-connection-timeout-retry-logs.keys``, content identical to
``group_06.keys``).  Splice report ``splice-dc07-send-connection-timeout-retry-logs.json``:
72 twin / 18 clean / **0 bad** - nothing in this group needs a hand-splice probe.  Candidate
counts below were recomputed with the harness's own matcher (``replay_lib.candidates``)
against this exact source and agree with that report key for key (792 candidate pytest runs).

What the group owns
===================
``DetectorClient._send_detection_request`` (def L596, last statement L919): the
``httpx.ConnectError`` arm (L688-L717, backoff cap L691) and the ``httpx.TimeoutException``
arm (L719-L748, cap L722).  Shipped behaviour, pinned at those lines:

* a NON-final attempt logs ONE WARNING (L692-L703 / L723-L734: message plus a seven-field
  ``extra=``) then ``await asyncio.sleep(min(2**attempt, 30))`` (L691/L722 + L704/L735);
* the FINAL attempt takes the ``else`` branch: NO sleep, ONE
  ``record_pipeline_error("<type>_connection_error")`` /
  ``record_pipeline_error("<type>_timeout")`` and ONE ERROR with a five-field ``extra=`` and
  ``exc_info=True`` (L705-L717 / L736-L748) - so a 7-attempt run sleeps SIX times
  (1, 2, 4, 8, 16, 30) and emits six WARNINGs plus one ERROR;
* the exhausted loop raises ``DetectorUnavailableError(error_msg, original_error=e) from e``
  (L911-L918).

How every occurrence twin is reddened
=====================================
The harness reddens EVERY text-matching candidate of a key, so a key whose ``before`` text
also sits in an arm this file does not own needs those arms exercised too.  The candidate line
sets, computed with the harness's own matcher against this exact source:

=================================================== ===== ====================================================
``before`` text                                        n  candidate lines (dc07 keys in brackets)
=================================================== ===== ====================================================
``delay = min(2**attempt, 30)``                        6  [691 m96] [722 m155] 754 791 850 883
``"detector_type": self._detector_type,``             17  360 [695] [710] [726] [741] 759 775 795 810 833
                                                          855 870 887 902 1072 1409 1433
``"camera_id": camera_id,``                           25  696 711 727 742 760 776 796 811 834 856 871 888
                                                          903 947 967 974 1049 1062 1073 1104 1343 1379
                                                          1391 1410 1434
``"file_path": image_path,``                          20  697 712 728 743 761 777 797 812 835 857 872 889
                                                          904 948 967 974 1074 1380 1392 1411
``"attempt": attempt + 1,``                            6  [698] [729] 762 799 858 890
``"max_retries": self._max_retries,``                  7  365 [699] [730] 763 800 859 891
``"retry_delay": delay,``                              6  [700] [731] 764 801 860 892
``"attempts": self._max_retries,``                     6  [713] [744] 778 814 873 905
``"error": str(e),``                                   5  [701 m120] [714 m142] [732 m179] [745 m201] 1414
``exc_info=True`` (and the ``arg_drop`` two-line form) 11  433 440 449 [716 m125/128/143] 747 781 816
                                                          875 908 1331 1438
``extra={...seven fields...},``                        2  (694, 725) - both dc07's own
``extra={...five fields...},``                         2  (709, 740) - both dc07's own
=================================================== =====

Every non-bracketed line above is reached by a leg below, and every leg pins the ORDERED
``(levelname, statement lineno)`` fingerprint of its own shipped call sites plus the raw
``record.msg`` and the named ``extra`` attributes of each record it owns, so no occurrence can
sit in while a sibling pretends to be it:

* cap (L754/L791/L850/L883) - ``test_asyncio_timeout_arm`` / ``test_server_error_arm`` /
  ``test_json_value_arm`` / ``test_unexpected_error_arm``, each a 7-attempt run that reads the
  six observed delays (the cap binds on attempts 5 and 6);
* L759/L762/L763/L764/L775/L778/L781 - ``test_asyncio_timeout_arm``; L795/L799-L801/L810/
  L814/L816 - ``test_server_error_arm``; L855/L858-L860/L870/L873/L875 -
  ``test_json_value_arm``; L887/L890-L892/L902/L905/L908 - ``test_unexpected_error_arm``;
* L833/L834/L835 - ``test_client_error_is_logged_once_and_returns_empty``;
* L360/L365 - ``test_init_info_record_carries_the_shipped_extras`` (a REAL client is built
  inside the capture window);
* L947/L948 - ``test_truncated_image_is_rejected_before_the_request``; L967 -
  ``test_unreadable_image_uses_the_oserror_arm``; L974 -
  ``test_unreadable_image_uses_the_valueerror_arm``; L1049 -
  ``test_missing_image_is_reported_once``; L1062 - ``test_request_debug_record_names_the_image``;
  L1072-L1074 - ``test_open_circuit_rejects_before_the_request``; L1104 -
  ``test_buffered_frame_debug_record_carries_the_camera``; L1343/L1379/L1380 -
  ``test_stored_detections_info_and_camera_debug_records``; L1391/L1392 -
  ``test_no_detections_debug_record``; L1409/L1410/L1411/L1414 -
  ``test_a_tripped_circuit_breaker_error_is_reported_and_reraised``; L1433/L1434/L1438 -
  ``test_a_commit_failure_becomes_the_object_detection_error``;
* the ``exc_info`` twins at L433/L440/L449 - the three ``health_check`` legs, and at L1331 -
  ``test_corrupted_detection_item_is_reported_with_its_traceback``.

The eleven-way ``exc_info`` twins (m125/m128/m143/m184/m187/m202) are the one place where the
shipped ``exc_info=None``/``exc_info=False`` mutants do NOT change the emitted record - both
render "no traceback" - so every leg that owns one of those eleven lines asserts the PRESENCE
of a populated 3-tuple (which is exactly what ``exc_info=True`` does), and the legs whose
shipped call carries NO ``exc_info`` (the 4xx arm, the validation WARNINGs, the route DEBUGs)
assert its ABSENCE.  A dropped ``extra=`` (a keyword-only ``logger.warning(extra=...)`` ->
``TypeError`` swallowed by the shipped ``except``) shows up as a MISSING record, which the
fingerprint assert catches.

Key -> test map (``mNN`` = ``..._send_detection_request__mutmut_NN``)
=====================================================================
* ConnectError retry WARNING (L692-L704) - ``test_connection_retry_warning`` (L725 twin via
  the TimeoutException legs): m97, m98, m100, m101, m102, m103, m104, m105, m106, m107, m108,
  m109, m110, m111, m112 (``attempt - 1``), m113 (``attempt + 2``), m114, m115, m116, m117,
  m118, m119, m120 (``str(None)``).
* ConnectError final (L705-L717) - ``test_connection_final_error``: m122 (label ``None``),
  m123, m124, m125, m127, m128, m129, m130, m131, m132, m133, m134, m135, m136, m137, m138,
  m139, m140, m141, m142, m143 (``exc_info=False``).
* TimeoutException retry WARNING (L719-L735) - ``test_timeout_retry_warning``: m156, m157,
  m159, m160, m161, m162, m163, m164, m165, m166, m167, m168, m169, m170, m171, m172, m173,
  m174, m175, m176, m177, m178, m179.
* TimeoutException final (L736-L748) - ``test_timeout_final_error``: m181, m182, m183, m184,
  m186, m187, m188, m189, m190, m191, m192, m193, m194, m195, m196, m197, m198, m199, m200,
  m201, m202.
* the 30 s cap - ``test_connection_backoff_caps_at_thirty`` (m96 @L691),
  ``test_timeout_backoff_caps_at_thirty`` (m155 @L722) and the four sibling-arm legs for
  @L754/L791/L850/L883.

Discipline
----------
* production never bends: the shipped ``_send_detection_request`` / ``detect_objects`` /
  ``health_check`` run on a REAL ``DetectorClient`` (the construction idiom of the shipped
  ``test_detector_client.py`` suite), so the shipped semaphore (L218-L223), circuit breaker
  (L336-L344, L1068, L1129) and retry loop are the code under test.  Patched collaborators are
  the HTTP transport, ``asyncio.sleep``, ``get_settings``, ``record_pipeline_error``,
  ``get_inference_semaphore``, the filesystem/PIL doubles, the thread offloads, the W3C header
  helper and the baseline service - every one of them ``autospec=True`` or ``new=`` (WP4.2
  ratchet).  There is no import-time global spy and no logger/handler mutation: only
  ``caplog``'s own handler sees the records.
* ``caplog``'s handler is process-wide and production has lazily-logged sites outside every
  leg's ownership - the class-level semaphore DEBUG (L221) fires on the FIRST
  ``_send_detection_request`` of the process and therefore lands in whichever leg happens to
  run first - so each leg asserts on the statement lines it owns (``mine_where``/``sent`` with
  its ``_ARM_*`` frozenset).  Every one of those lines is a candidate of at least one key in
  this group (table above), so the restriction can hide nothing this group must prove.
* no clock is patched: ``time.monotonic``/``time.perf_counter``/``datetime`` are untouched and
  every backoff delay is observed through the patched ``asyncio.sleep`` double, so the 30 s cap
  legs spend no wall-clock time.
"""

import ast
import asyncio
import json
import logging
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


# Every ``logger.<level>(`` statement line a leg below can legitimately produce, per arm.
# ``record.lineno`` IS the statement line (``Logger.findCaller`` skips this module's frames),
# so these frozensets are what the legs pin.  Values read straight off the source above.
_ARM_INIT = frozenset({357})
_ARM_CONNECT = frozenset({692, 707})
_ARM_TIMEOUT = frozenset({723, 738})
_ARM_ASYNCIO = frozenset({755, 771})
_ARM_SERVER = frozenset({792, 807})
_ARM_JSON = frozenset({851, 866})
_ARM_UNEXPECTED = frozenset({884, 899})
_ARM_CLIENT = frozenset({830, 1060})
_ARM_HEALTH_CONNECT = frozenset({430})
_ARM_HEALTH_STATUS = frozenset({437})
_ARM_HEALTH_UNEXPECTED = frozenset({446})
_ARM_VALIDATE_SMALL = frozenset({944})
_ARM_VALIDATE_OSERROR = frozenset({965})
_ARM_VALIDATE_VALUE = frozenset({972})
_ARM_MISSING = frozenset({1047})
_ARM_REQUEST_DEBUG = frozenset({1060})
_ARM_BREAKER_REJECT = frozenset({1060, 1069})
_ARM_BUFFERED = frozenset({1060, 1101, 1388})
_ARM_STORED = frozenset({1060, 1319, 1341, 1386})
_ARM_NO_DETECT = frozenset({1060, 1388})
_ARM_CORRUPTED = frozenset({1060, 1328, 1341, 1388})
_ARM_BREAKER_RAISED = frozenset({1060, 1406})
_ARM_COMMIT_FAILED = frozenset({1060, 1319, 1341, 1430})

# LogRecord's own attributes plus everything backend.core.logging's ContextFilter injects
# (probe-verified on this tree): what is left is the call's own ``extra=`` payload.
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
_CAMERA_ID = "cam-9"
_BYTES = b"image-bytes-here"
# shipped read timeout (L111: 60.0) + the ai_connect_timeout the settings fixture pins
# (5.0) -> the defense-in-depth explicit_timeout of L637 is 65.0.
_TIMEOUT = 65.0
# the delays of the NON-final attempts of a 7-attempt run: 2**0..2**5 capped at 30 (the final
# attempt takes the else branch: metrics + ERROR, no sleep) -> six sleeps and six WARNINGs,
# and the cap binds on the last two.
_BACKOFF = [1, 2, 4, 8, 16, 30]
_RETRIED = [(n, 7) for n in range(1, 7)]
_REQUEST = httpx.Request("POST", "http://detector.invalid:8000/detect")


# --------------------------------------------------------------------------- observation


def win(caplog):
    """Open a capture window on the shipped module logger (set_level + clear)."""
    caplog.set_level(logging.DEBUG, logger=M.logger.name)
    caplog.clear()


def mine(caplog):
    """Captured records from this module's own logger (provenance filtered)."""
    return [r for r in caplog.records if r.name == M.logger.name]


def mine_where(caplog, where):
    """This module's captured records restricted to the leg's own shipped call sites.

    See the module docstring: ``caplog`` is process-wide, production has lazily-logged sites
    (the class-level semaphore DEBUG at L221) outside every leg's ownership, and every line a
    leg owns is a candidate of at least one key in this group.
    """
    return [r for r in mine(caplog) if _anchor(r) in where]


def surface(caplog, where=None):
    """Every captured record as ``LEVEL lineno | msg | sorted(extras)``.

    The call site comes off the record, so a mutant that moves or swallows a log call is as
    visible as one that renames a field.
    """
    pool = mine(caplog) if where is None else mine_where(caplog, where)
    return sorted(f"{r.levelname} {_anchor(r)} | {r.msg} | {sorted(fields(r))}" for r in pool)


def sent(caplog, where):
    """``(levelname, caller lineno)`` of every record the leg owns, IN EMISSION ORDER.

    ``Logger.findCaller`` skips this module's own frames, so the lineno is the CALL SITE of
    ``logger.<level>(...)`` - the physical line the shipped call sits on.  Under an
    occurrence-twin mutant one sibling call dies (its kwargs stop matching the mutated
    signature) and the next same-level sibling takes its place at ITS OWN line, so a pure
    level-count collation could stay green; this ordered fingerprint is what no occurrence can
    fake, and it is the primary surface pin of every leg.
    """
    return [(r.levelname, _anchor(r)) for r in mine_where(caplog, where)]


def fields(rec):
    """The record's own ``extra=`` fields (LogRecord + ContextFilter noise removed)."""
    return {k: v for k, v in rec.__dict__.items() if k not in _NOISE}


def shipped_fields(rec, keys):
    """``{key: value}`` for shipped ``extra=`` names, asserting each is PRESENT and that
    neither its ``XX<name>XX`` nor its ``NAME`` variant sits on the record."""
    have = fields(rec)
    for key in keys:
        assert key in have, f"missing extra {key!r} on {rec.levelname} {rec.msg!r}: {sorted(have)}"
        assert f"XX{key}XX" not in have, f"renamed extra XX{key}XX on {rec.msg!r}"
        assert key.upper() not in have, f"renamed extra {key.upper()} on {rec.msg!r}"
    return {key: have[key] for key in keys}


def records_at(caplog, where, level, lineno):
    """The leg's records at ``level`` whose call site is exactly ``lineno``.

    The call site is pinned by ``sent``; this narrows to one shipped statement so the field
    asserts below read the record that statement produced - a sibling arm's record can never
    satisfy them.
    """
    return [r for r in mine_where(caplog, where) if r.levelname == level and _anchor(r) == lineno]


def one_at(caplog, where, level, lineno):
    """The single record of ``level`` at shipped statement ``lineno``."""
    hits = records_at(caplog, where, level, lineno)
    assert len(hits) == 1, f"expected exactly one {level} at L{lineno}: {surface(caplog, where)}"
    return hits[0]


def warned(caplog, where, lineno):
    """The retry WARNINGs emitted by one arm's retry statement."""
    return records_at(caplog, where, "WARNING", lineno)


def delays(records):
    """Each record's shipped ``retry_delay`` extra, read by name."""
    return [shipped_fields(r, ["retry_delay"])["retry_delay"] for r in records]


def retried(records):
    """``(attempt, max_retries)`` of the passed WARNINGs, in shipped order."""
    return [tuple(shipped_fields(r, ["attempt", "max_retries"]).values()) for r in records]


def tracebacks(record):
    """A populated ``exc_info`` 3-tuple is present (the shipped ``exc_info=True``)."""
    assert isinstance(record.exc_info, tuple), f"no exc_info tuple on {record.msg!r}"
    assert len(record.exc_info) == 3, record.exc_info
    assert record.exc_info[1] is not None, "the shipped exc_info=True carries the exception"
    return record.exc_info


# --------------------------------------------------------------------------- doubles


def status_error(message, status, body=None):
    """A shipped-shaped ``httpx.HTTPStatusError`` (real Request, response double).

    ``body`` backs ``e.response.json()``: the shipped 400 arm (L821-L827) reads the detail out
    of the ERROR response, so the double has to answer like a real response.
    """
    response = MagicMock(spec=httpx.Response)
    response.status_code = status
    if body is not None:
        response.json.return_value = body
    return httpx.HTTPStatusError(message, request=_REQUEST, response=response)


_ERR_400 = status_error(
    "Detector service rejected this image", 400, body={"detail": "payload rejected"}
)
_ERR_503 = status_error("Detector service is unavailable", 503)


async def _to_thread_inline(fn, *args, **kwargs):
    """Runs the offloaded callable on the current loop and awaits, like ``to_thread`` does.

    The shipped route offloads BOTH validation legs (L991) and the image read (L1084) through
    ``asyncio.to_thread``; patched to run inline, the real validation body executes on the
    ``Path`` doubles below instead of in a worker thread.  ``new=`` form (WP4.2 ratchet).
    """
    return fn(*args, **kwargs)


class _DecodedImage:
    """The PIL context manager ``Image.open`` returns (L957-L959): ``load()`` is the shipped
    decompression call that catches truncated uploads, so a no-op stand-in means "this image
    is intact"."""

    def load(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class fs(ExitStack):
    """Pins the filesystem the route reads - ``exists`` (L1046), ``stat().st_size`` (L942)
    and ``read_bytes`` (L1084) - plus the PIL open of the validation leg (L957), and runs the
    two ``asyncio.to_thread`` offloads inline on those doubles, so no leg touches a real file.
    An ExitStack, so ``with fs(), post() as posted:`` opens everything in one statement and
    unwinds it on exit.  ``image_error`` makes PIL's open raise, which is how the two corrupt-
    image legs reach their WARNING arms (L963-L976)."""

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


@pytest.fixture(autouse=True)
def baseline_service():
    """The shipped suite's autouse mock of ``get_baseline_service`` (the route reaches it
    whenever a detection is stored, L1351)."""
    service = MagicMock()
    service.update_baseline = AsyncMock()
    with patch("backend.services.detector_client.get_baseline_service", autospec=True) as factory:
        factory.return_value = service
        yield service


@pytest.fixture(autouse=True)
def request_envelope():
    """The correlation headers and the shared inference semaphore the route consumes
    (L399-L411, L1115).  Both are pinned autospec at the shipped import site so no leg
    depends on ambient settings or on another test's semaphore."""
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
    reads.  The timeout values are real floats so a REAL ``DetectorClient`` can be built."""
    st = MagicMock()
    st.ai_gateway_url = None
    st.use_ai_gateway = False
    st.yolo26_url = "http://detector.invalid:8000"
    st.yolo26_api_key = None
    st.yolo26_read_timeout = 60.0
    st.ai_connect_timeout = 5.0
    st.ai_health_timeout = 5.0
    st.detector_max_retries = 3
    st.ai_max_concurrent_inferences = 4
    st.detection_confidence_threshold = 0.5
    st.detection_class_thresholds = {}
    st.ai_warmup_enabled = False
    st.ai_cold_start_threshold_seconds = 60.0
    with patch("backend.services.detector_client.get_settings", autospec=True) as factory:
        factory.return_value = st
        yield factory


@pytest.fixture
def metrics():
    """Spy on the shipped metrics reporter: ``detector_client`` imports the symbol by name
    (L76-L83), so the shipped call site is a call of that module global with the real
    argument signature."""
    with patch.object(M, "record_pipeline_error", autospec=True) as spy:
        yield spy


class _PassThroughTimeout:
    """``asyncio.timeout(seconds)`` stand-in that never trips."""

    def __init__(self, seconds):
        self.seconds = seconds

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


def _pass_through_timeout(seconds):
    return _PassThroughTimeout(seconds)


@pytest.fixture
def sleep():
    """Spy on ``asyncio.sleep`` so backoff delays are observed and no wall clock is spent.

    ``asyncio.timeout`` (L665) is a CONTEXT MANAGER, so this fixture also patches it with a
    pass-through stand-in: a bare ``AsyncMock`` there would hand the shipped body an awaitable
    instead of an async context manager and every happy leg would take the ``TimeoutError``
    arm.  The asyncio leg replaces both entries for its own ``TimeoutError``-tripping probe.
    """
    with (
        patch("asyncio.sleep", new_callable=AsyncMock) as sleeper,
        patch.object(asyncio, "timeout", new=_pass_through_timeout),
    ):
        yield sleeper


@pytest.fixture
def client(settings):
    """A REAL ``DetectorClient(max_retries=2)`` - the shipped ``__init__`` runs, so the
    semaphore, circuit breaker and retry loop under test are production code."""
    instance = DetectorClient(max_retries=2)
    assert instance._max_retries == 2  # the ctor argument wins over settings (L313-L315)
    assert instance._detector_type == "yolo26"
    assert instance._read_timeout == 60.0
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


def post(**kwargs):
    """Patch the persistent HTTP client's ``post`` (autospec, as the shipped suite does)."""
    return patch.object(httpx.AsyncClient, "post", autospec=True, **kwargs)


def get(**kwargs):
    """Patch the health client's ``get``."""
    return patch.object(httpx.AsyncClient, "get", autospec=True, **kwargs)


def session_double(*, camera=None, commit_error=None):
    """A DB session double: ``get`` answers with ``camera``, ``add``/``commit``/``flush``
    are spies (``commit`` can be made to fail)."""
    ses = AsyncMock()
    ses.get = AsyncMock(return_value=camera)
    ses.add = MagicMock()
    if commit_error is not None:
        ses.commit = AsyncMock(side_effect=commit_error)
    else:
        ses.commit = AsyncMock()
    ses.flush = AsyncMock()
    return ses


async def run_request(client, *, retries=None, data=_BYTES):
    """Drive the shipped ``_send_detection_request`` the way L1129-L1135 does."""
    if retries is not None:
        client._max_retries = retries
    return await client._send_detection_request(data, "frame-0007.jpg", _CAMERA_ID, _IMAGE_PATH)


async def run_detect(client, ses=None):
    """Drive the shipped ``detect_objects`` for the sibling log sites."""
    return await client.detect_objects(_IMAGE_PATH, _CAMERA_ID, ses or session_double())


def one_body(**over):
    """A detector body carrying exactly ONE shipped-shaped detection (plus dimensions)."""
    body = {
        "detections": [{"class": "person", "confidence": 0.9, "bbox": [1, 2, 3, 4]}],
        "image_width": 100,
        "image_height": 60,
    }
    body.update(over)
    return body


# --------------------------------------------------------------------------- tests
# --------------------------------------------------------------------------- tests


@pytest.mark.asyncio
async def test_init_info_record_carries_the_shipped_extras(caplog, settings):
    """TWIN COVERAGE for L360 (and the ``__init__`` INFO as shipped behaviour): a real
    client built from the pinned settings emits exactly ONE record - the INFO at L357 -
    whose extras are exactly the shipped nine keys with the shipped values."""
    win(caplog)
    instance = DetectorClient(max_retries=4)

    assert sent(caplog, _ARM_INIT) == [("INFO", 357)], surface(caplog, _ARM_INIT)
    info = one_at(caplog, _ARM_INIT, "INFO", 357)
    assert info.msg == "DetectorClient initialized"
    assert shipped_fields(
        info,
        [
            "detector_type",
            "detector_url",
            "free_threading",
            "max_concurrent_inferences",
            "preprocess_workers",
            "max_retries",
            "timeout_seconds",
            "circuit_breaker_failure_threshold",
            "circuit_breaker_recovery_timeout",
        ],
    ) == {
        "detector_type": "yolo26",
        "detector_url": "http://detector.invalid:8000",
        "free_threading": M._is_free_threaded(),
        "max_concurrent_inferences": 4,
        "preprocess_workers": M._get_preprocess_worker_count(),
        "max_retries": 4,
        "timeout_seconds": 60.0,
        "circuit_breaker_failure_threshold": 5,
        "circuit_breaker_recovery_timeout": 60.0,
    }
    assert instance._max_retries == 4


@pytest.mark.asyncio
async def test_connection_retry_warning(caplog, client, sleep, metrics, settings):
    """L688-L704 with ``max_retries=2``: attempt 0 is non-final, so the shipped WARNING
    (raw msg + seven ``extra=`` fields) fires once and exactly ``asyncio.sleep(1)`` follows
    it.  The leg also carries the shipped consequence of the second attempt - the final ERROR
    and its metrics label - because that is what a 2-attempt exhaustion does."""
    exc = httpx.ConnectError("refused")
    win(caplog)
    with post(side_effect=exc):
        with pytest.raises(M.DetectorUnavailableError) as raised:
            await run_request(client)

    assert type(raised.value.original_error) is httpx.ConnectError
    assert sent(caplog, _ARM_CONNECT) == [("WARNING", 692), ("ERROR", 707)], surface(
        caplog, _ARM_CONNECT
    )
    assert [c.args[0] for c in sleep.call_args_list] == [1]
    assert [c.args for c in metrics.call_args_list] == [("yolo26_connection_error",)]
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
        "error": "refused",
    }
    assert warning.exc_info is None


@pytest.mark.asyncio
async def test_connection_final_error(caplog, client, sleep, metrics, settings):
    """L705-L717: on the final attempt the shipped label is reported, then ONE ERROR with
    the shipped msg, five extras and a real ``exc_info`` 3-tuple whose exception is the
    shipped ``raise ... from e`` cause (L916-L918)."""
    exc = httpx.ConnectError("refused")
    win(caplog)
    with post(side_effect=exc):
        with pytest.raises(M.DetectorUnavailableError) as raised:
            await run_request(client)

    assert sent(caplog, _ARM_CONNECT) == [("WARNING", 692), ("ERROR", 707)], surface(
        caplog, _ARM_CONNECT
    )
    assert [c.args for c in metrics.call_args_list] == [("yolo26_connection_error",)]
    assert [c.args[0] for c in sleep.call_args_list] == [1]
    error = one_at(caplog, _ARM_CONNECT, "ERROR", 707)
    assert error.msg == "Detector connection error after all attempts"
    assert shipped_fields(error, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(error, ["attempts", "error"]) == {"attempts": 2, "error": "refused"}
    assert tracebacks(error)[1] is exc
    assert raised.value.__cause__ is exc
    assert raised.value.original_error is exc


@pytest.mark.asyncio
async def test_timeout_retry_warning(caplog, client, sleep, metrics, settings):
    """L719-L735: the TimeoutException arm's own shipped WARNING msg and seven extras, at
    its own statement lines (L723 then the final ERROR at L738)."""
    exc = httpx.TimeoutException("slow")
    win(caplog)
    with post(side_effect=exc):
        with pytest.raises(M.DetectorUnavailableError) as raised:
            await run_request(client)

    assert type(raised.value.original_error) is httpx.TimeoutException
    assert sent(caplog, _ARM_TIMEOUT) == [("WARNING", 723), ("ERROR", 738)], surface(
        caplog, _ARM_TIMEOUT
    )
    assert [c.args[0] for c in sleep.call_args_list] == [1]
    assert [c.args for c in metrics.call_args_list] == [("yolo26_timeout",)]
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
        "error": "slow",
    }
    assert warning.exc_info is None


@pytest.mark.asyncio
async def test_timeout_final_error(caplog, client, sleep, metrics, settings):
    """L736-L748: ``record_pipeline_error("yolo26_timeout")`` then the shipped final ERROR
    msg, five extras and ``exc_info`` chain identity."""
    exc = httpx.TimeoutException("slow")
    win(caplog)
    with post(side_effect=exc):
        with pytest.raises(M.DetectorUnavailableError) as raised:
            await run_request(client)

    assert sent(caplog, _ARM_TIMEOUT) == [("WARNING", 723), ("ERROR", 738)], surface(
        caplog, _ARM_TIMEOUT
    )
    assert [c.args for c in metrics.call_args_list] == [("yolo26_timeout",)]
    assert [c.args[0] for c in sleep.call_args_list] == [1]
    error = one_at(caplog, _ARM_TIMEOUT, "ERROR", 738)
    assert error.msg == "Detector timeout after all attempts"
    assert shipped_fields(error, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(error, ["attempts", "error"]) == {"attempts": 2, "error": "slow"}
    assert tracebacks(error)[1] is exc
    assert raised.value.__cause__ is exc


@pytest.mark.asyncio
async def test_connection_backoff_caps_at_thirty(caplog, client, sleep, metrics, settings):
    """L691: seven ConnectError attempts sleep 1,2,4,8,16,30 - the final attempt logs the
    ERROR instead of sleeping - and every retry WARNING's ``retry_delay`` repeats the delay
    that was slept, so the shipped cap is 30 and not 31."""
    win(caplog)
    with post(side_effect=httpx.ConnectError("refused")):
        with pytest.raises(M.DetectorUnavailableError):
            await run_request(client, retries=7)

    assert sent(caplog, _ARM_CONNECT) == [("WARNING", 692)] * 6 + [("ERROR", 707)], surface(
        caplog, _ARM_CONNECT
    )
    assert [c.args[0] for c in sleep.call_args_list] == _BACKOFF
    warnings = warned(caplog, _ARM_CONNECT, 692)
    assert delays(warnings) == _BACKOFF
    assert retried(warnings) == _RETRIED
    assert [c.args for c in metrics.call_args_list] == [("yolo26_connection_error",)]


@pytest.mark.asyncio
async def test_timeout_backoff_caps_at_thirty(caplog, client, sleep, metrics, settings):
    """L722: the same capped sequence on the TimeoutException arm."""
    win(caplog)
    with post(side_effect=httpx.TimeoutException("slow")):
        with pytest.raises(M.DetectorUnavailableError):
            await run_request(client, retries=7)

    assert sent(caplog, _ARM_TIMEOUT) == [("WARNING", 723)] * 6 + [("ERROR", 738)], surface(
        caplog, _ARM_TIMEOUT
    )
    assert [c.args[0] for c in sleep.call_args_list] == _BACKOFF
    warnings = warned(caplog, _ARM_TIMEOUT, 723)
    assert delays(warnings) == _BACKOFF
    assert retried(warnings) == _RETRIED
    assert [c.args for c in metrics.call_args_list] == [("yolo26_timeout",)]


class _TrippingTimeout:
    """Stand-in for the shipped ``asyncio.timeout`` gate (L665) that always trips.

    ``asyncio.timeout`` is patched ``new=`` for the leg only: the shipped
    ``except TimeoutError`` arm (L750-L782) then runs for real, which is the only way to
    reach the L754/L762-L764/L778/L781 twins this group's texts collide with.
    """

    def __init__(self, seconds, raises):
        self.seconds = seconds
        self.raises = raises

    async def __aenter__(self):
        raise self.raises

    async def __aexit__(self, *exc_info):
        return False


@pytest.mark.asyncio
async def test_asyncio_timeout_arm(caplog, client, sleep, metrics, settings):
    """TWIN COVERAGE for L754/L762/L763/L764/L778/L781: the ``asyncio.timeout`` arm reaches
    the same cap, and its f-string msgs and extras are as shipped."""
    trip = TimeoutError("gate tripped")
    win(caplog)
    with (
        patch.object(asyncio, "timeout", new=lambda seconds: _TrippingTimeout(seconds, trip)),
        post(),
        pytest.raises(M.DetectorUnavailableError) as raised,
    ):
        await run_request(client, retries=7)

    assert type(raised.value.original_error) is TimeoutError
    assert sent(caplog, _ARM_ASYNCIO) == [("WARNING", 755)] * 6 + [("ERROR", 771)], surface(
        caplog, _ARM_ASYNCIO
    )
    assert [c.args[0] for c in sleep.call_args_list] == _BACKOFF
    assert [c.args for c in metrics.call_args_list] == [("yolo26_asyncio_timeout",)]
    warnings = warned(caplog, _ARM_ASYNCIO, 755)
    assert delays(warnings) == _BACKOFF
    assert retried(warnings) == _RETRIED
    assert [shipped_fields(r, ["explicit_timeout"])["explicit_timeout"] for r in warnings] == [
        _TIMEOUT
    ] * 6
    assert [r.msg for r in warnings] == [
        f"Detector asyncio timeout (attempt {n}/7), retrying in {d}s: "
        f"request timed out after {_TIMEOUT}s"
        for n, d in enumerate(_BACKOFF, start=1)
    ]
    # The retry WARNING (L755) carries the SAME detector_type/camera_id/file_path names and
    # values as this arm's final ERROR (L771), which the next block pins to the shipped
    # literals - so the WARNING's three field names are pinned here too, via identity with
    # the record whose values are asserted directly.  If any of the six shipped lines
    # (L759-L761 vs L775-L777) were renamed, the field reads below stop matching by name
    # and this leg fails - reddening every detector_type/camera_id/file_path occurrence on
    # the WARNING's extras, not just the ERROR's.
    error = one_at(caplog, _ARM_ASYNCIO, "ERROR", 771)
    warning_fields = [
        shipped_fields(r, ["detector_type", "camera_id", "file_path"]) for r in warnings
    ]
    error_fields = shipped_fields(error, ["detector_type", "camera_id", "file_path"])
    assert warning_fields == [error_fields] * 6
    assert error.msg == (
        f"Detector asyncio timeout after 7 attempts: request timed out after {_TIMEOUT}s"
    )
    assert shipped_fields(error, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(error, ["attempts", "explicit_timeout"]) == {
        "attempts": 7,
        "explicit_timeout": _TIMEOUT,
    }
    assert tracebacks(error)[1] is trip


@pytest.mark.asyncio
async def test_server_error_arm(caplog, client, sleep, metrics, settings):
    """TWIN COVERAGE for L791/L799/L800/L801/L814/L816: a 503 is retried with the capped
    sequence and the shipped ``status_code``-bearing extras."""
    win(caplog)
    resp = response(status=503, status_error=_ERR_503)
    with post(return_value=resp), pytest.raises(M.DetectorUnavailableError):
        await run_request(client, retries=7)

    assert sent(caplog, _ARM_SERVER) == [("WARNING", 792)] * 6 + [("ERROR", 807)], surface(
        caplog, _ARM_SERVER
    )
    assert [c.args[0] for c in sleep.call_args_list] == _BACKOFF
    assert [c.args for c in metrics.call_args_list] == [("yolo26_server_error",)]
    warnings = warned(caplog, _ARM_SERVER, 792)
    assert delays(warnings) == _BACKOFF
    assert retried(warnings) == _RETRIED
    assert [r.msg for r in warnings] == ["Detector server error, retrying"] * 6
    assert [shipped_fields(r, ["status_code"])["status_code"] for r in warnings] == [503] * 6
    error = one_at(caplog, _ARM_SERVER, "ERROR", 807)
    warning_fields = [
        shipped_fields(r, ["detector_type", "camera_id", "file_path"]) for r in warnings
    ]
    error_fields = shipped_fields(error, ["detector_type", "camera_id", "file_path"])
    assert warning_fields == [error_fields] * 6  # pins L795/L796/L797 against L810-L812
    assert error.msg == "Detector server error after all attempts"
    assert shipped_fields(error, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(error, ["status_code", "attempts"]) == {
        "status_code": 503,
        "attempts": 7,
    }
    assert tracebacks(error)[1] is _ERR_503


@pytest.mark.asyncio
async def test_json_value_arm(caplog, client, sleep, metrics, settings):
    """TWIN COVERAGE for L850/L858/L859/L860/L873/L875: a malformed JSON body is retried
    with the capped sequence; its msg is the shipped f-string carrying ``str(e)`` - the full
    ``JSONDecodeError`` sentence, not just its first words."""
    body_error = json.JSONDecodeError("Expecting value", "not-json", 0)
    detail = str(body_error)
    win(caplog)
    resp = response(json_error=body_error)
    with post(return_value=resp), pytest.raises(M.DetectorUnavailableError) as raised:
        await run_request(client, retries=7)

    assert type(raised.value.original_error) is json.JSONDecodeError
    assert sent(caplog, _ARM_JSON) == [("WARNING", 851)] * 6 + [("ERROR", 866)], surface(
        caplog, _ARM_JSON
    )
    assert [c.args[0] for c in sleep.call_args_list] == _BACKOFF
    assert [c.args for c in metrics.call_args_list] == [("yolo26_json_error",)]
    warnings = warned(caplog, _ARM_JSON, 851)
    assert delays(warnings) == _BACKOFF
    assert retried(warnings) == _RETRIED
    assert [r.msg for r in warnings] == [
        f"Detector JSON/value error (attempt {n}/7), retrying in {d}s: {detail}"
        for n, d in enumerate(_BACKOFF, start=1)
    ]
    error = one_at(caplog, _ARM_JSON, "ERROR", 866)
    warning_fields = [
        shipped_fields(r, ["detector_type", "camera_id", "file_path"]) for r in warnings
    ]
    error_fields = shipped_fields(error, ["detector_type", "camera_id", "file_path"])
    assert warning_fields == [error_fields] * 6  # pins L855/L856/L857 against L870-L872
    assert error.msg == f"Detector JSON/value error after 7 attempts: {detail}"
    assert shipped_fields(error, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(error, ["attempts"]) == {"attempts": 7}
    assert tracebacks(error)[1] is body_error


@pytest.mark.asyncio
async def test_unexpected_error_arm(caplog, client, sleep, metrics, settings):
    """TWIN COVERAGE for L883/L890/L891/L892/L905/L908: an ``OSError`` is retried with the
    capped sequence and the ``sanitize_error`` text in the ``error`` extra."""
    boom = OSError("disk went away")
    win(caplog)
    with post(side_effect=boom), pytest.raises(M.DetectorUnavailableError) as raised:
        await run_request(client, retries=7)

    assert type(raised.value.original_error) is OSError
    assert sent(caplog, _ARM_UNEXPECTED) == [
        ("WARNING", 884),
    ] * 6 + [("ERROR", 899)], surface(caplog, _ARM_UNEXPECTED)
    assert [c.args[0] for c in sleep.call_args_list] == _BACKOFF
    assert [c.args for c in metrics.call_args_list] == [("yolo26_unexpected_error",)]
    warnings = warned(caplog, _ARM_UNEXPECTED, 884)
    assert delays(warnings) == _BACKOFF
    assert retried(warnings) == _RETRIED
    assert [r.msg for r in warnings] == ["Unexpected detector error, retrying"] * 6
    assert [shipped_fields(r, ["error"])["error"] for r in warnings] == ["disk went away"] * 6
    error = one_at(caplog, _ARM_UNEXPECTED, "ERROR", 899)
    warning_fields = [
        shipped_fields(r, ["detector_type", "camera_id", "file_path"]) for r in warnings
    ]
    error_fields = shipped_fields(error, ["detector_type", "camera_id", "file_path"])
    assert warning_fields == [error_fields] * 6  # pins L887/L888/L889 against L902-L904
    assert error.msg == "Unexpected detector error after all attempts"
    assert shipped_fields(error, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(error, ["attempts", "error"]) == {
        "attempts": 7,
        "error": "disk went away",
    }
    assert tracebacks(error)[1] is boom


@pytest.mark.asyncio
async def test_client_error_is_logged_once_and_returns_empty(caplog, client, metrics, settings):
    """TWIN COVERAGE for L833/L834/L835 (plus this group's own behaviour): a 400 is NOT
    retried - one ``Detector client error`` ERROR with the shipped five extras and no
    traceback, then ``detect_objects`` swallows the ``ValueError`` (L1399-L1401) and returns
    nothing (so the "No detections" DEBUG at L1388 never fires)."""
    win(caplog)
    resp = response(status=400, status_error=_ERR_400, body={"detail": "payload rejected"})
    with fs(), post(return_value=resp) as posted:
        assert await run_detect(client) == []

    assert posted.await_count == 1
    assert metrics.call_args_list == [call("yolo26_client_error")]
    assert sent(caplog, _ARM_CLIENT) == [("DEBUG", 1060), ("ERROR", 830)], surface(
        caplog, _ARM_CLIENT
    )
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
    assert error.exc_info is None, "the 4xx arm is logged without a traceback"


@pytest.mark.asyncio
async def test_health_check_connection_arm_keeps_its_traceback(caplog, client):
    """TWIN COVERAGE for L433: the ``ConnectError``/``TimeoutException`` arm of
    ``health_check`` logs its shipped sentence at L430 with the ``error`` extra and a
    traceback - once per exception type, and nothing else."""
    for exc in (httpx.ConnectError("health refused"), httpx.TimeoutException("health slow")):
        win(caplog)
        with get(side_effect=exc):
            assert await client.health_check() is False
        assert sent(caplog, _ARM_HEALTH_CONNECT) == [("WARNING", 430)], surface(
            caplog, _ARM_HEALTH_CONNECT
        )
        warning = one_at(caplog, _ARM_HEALTH_CONNECT, "WARNING", 430)
        assert warning.msg == "Detector health check failed"
        assert shipped_fields(warning, ["error"]) == {"error": str(exc)}
        assert tracebacks(warning)[1] is exc


@pytest.mark.asyncio
async def test_health_check_status_arm_keeps_its_traceback(caplog, client):
    """TWIN COVERAGE for L440: the ``HTTPStatusError`` arm logs its own shipped sentence at
    L437."""
    win(caplog)
    resp = response(status=503, status_error=_ERR_503)
    with get(return_value=resp):
        assert await client.health_check() is False
    assert sent(caplog, _ARM_HEALTH_STATUS) == [("WARNING", 437)], surface(
        caplog, _ARM_HEALTH_STATUS
    )
    warning = one_at(caplog, _ARM_HEALTH_STATUS, "WARNING", 437)
    assert warning.msg == "Detector health check returned error status"
    assert shipped_fields(warning, ["error"]) == {"error": str(_ERR_503)}
    assert tracebacks(warning)[1] is _ERR_503


@pytest.mark.asyncio
async def test_health_check_unexpected_arm_keeps_its_traceback(caplog, client):
    """TWIN COVERAGE for L449: the ``OSError``/``RuntimeError``/``ValueError`` arm is the
    module's ``logger.error`` at L446 with ``exc_info=True`` and the sanitized error."""
    boom = RuntimeError("health exploded")
    win(caplog)
    with get(side_effect=boom):
        assert await client.health_check() is False
    assert sent(caplog, _ARM_HEALTH_UNEXPECTED) == [("ERROR", 446)], surface(
        caplog, _ARM_HEALTH_UNEXPECTED
    )
    error = one_at(caplog, _ARM_HEALTH_UNEXPECTED, "ERROR", 446)
    assert error.msg == "Unexpected error during detector health check"
    assert shipped_fields(error, ["error"]) == {"error": "health exploded"}
    assert tracebacks(error)[1] is boom


@pytest.mark.asyncio
async def test_truncated_image_is_rejected_before_the_request(caplog, client, metrics):
    """TWIN COVERAGE for L947/L948: a file below ``MIN_DETECTION_IMAGE_SIZE`` never reaches
    the detector - one WARNING at L944 naming camera, path, size and floor."""
    win(caplog)
    with fs(size=MIN_DETECTION_IMAGE_SIZE - 1), post() as posted:
        assert await run_detect(client) == []

    assert sent(caplog, _ARM_VALIDATE_SMALL) == [("WARNING", 944)], surface(
        caplog, _ARM_VALIDATE_SMALL
    )
    warning = one_at(caplog, _ARM_VALIDATE_SMALL, "WARNING", 944)
    assert warning.msg == "Image too small for detection"
    assert shipped_fields(warning, ["camera_id", "file_path"]) == {
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(warning, ["file_size", "min_size"]) == {
        "file_size": MIN_DETECTION_IMAGE_SIZE - 1,
        "min_size": MIN_DETECTION_IMAGE_SIZE,
    }
    posted.assert_not_awaited()
    assert metrics.call_args_list == [call("invalid_image")]


@pytest.mark.asyncio
async def test_unreadable_image_uses_the_oserror_arm(caplog, client, metrics):
    """TWIN COVERAGE for L967: an ``OSError`` out of PIL's open logs the shipped
    corrupt/truncated WARNING at L965 (camera_id, file_path, error) and skips detection."""
    win(caplog)
    with fs(image_error=OSError("truncated upload")), post() as posted:
        assert await run_detect(client) == []

    assert sent(caplog, _ARM_VALIDATE_OSERROR) == [("WARNING", 965)], surface(
        caplog, _ARM_VALIDATE_OSERROR
    )
    warning = one_at(caplog, _ARM_VALIDATE_OSERROR, "WARNING", 965)
    assert warning.msg == "Image validation failed (corrupt/truncated)"
    assert shipped_fields(warning, ["camera_id", "file_path", "error"]) == {
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
        "error": "truncated upload",
    }
    posted.assert_not_awaited()
    assert metrics.call_args_list == [call("invalid_image")]


@pytest.mark.asyncio
async def test_unreadable_image_uses_the_valueerror_arm(caplog, client, metrics):
    """TWIN COVERAGE for L974: the ``ValueError``/``RuntimeError`` arm logs the shorter
    shipped sentence at L972 with the sanitized error."""
    win(caplog)
    with fs(image_error=ValueError("bad image format")), post() as posted:
        assert await run_detect(client) == []

    assert sent(caplog, _ARM_VALIDATE_VALUE) == [("WARNING", 972)], surface(
        caplog, _ARM_VALIDATE_VALUE
    )
    warning = one_at(caplog, _ARM_VALIDATE_VALUE, "WARNING", 972)
    assert warning.msg == "Image validation failed"
    assert shipped_fields(warning, ["camera_id", "file_path", "error"]) == {
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
        "error": "bad image format",
    }
    posted.assert_not_awaited()
    assert metrics.call_args_list == [call("invalid_image")]


@pytest.mark.asyncio
async def test_missing_image_is_reported_once(caplog, client, metrics):
    """TWIN COVERAGE for L1049: a missing file logs ONE ERROR at L1047 naming camera and
    path, reports ``file_not_found`` and never opens the detector."""
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
async def test_request_debug_record_names_the_image(caplog, client):
    """TWIN COVERAGE for L1062: the pre-request DEBUG (L1060) names the camera and the path,
    and is followed by the empty-result DEBUG at L1388 - the shipped pair for a clean,
    detection-free run."""
    win(caplog)
    with fs(), post(return_value=response()):
        assert await run_detect(client) == []

    assert sent(caplog, _ARM_NO_DETECT) == [("DEBUG", 1060), ("DEBUG", 1388)], surface(
        caplog, _ARM_NO_DETECT
    )
    debug = one_at(caplog, _ARM_REQUEST_DEBUG, "DEBUG", 1060)
    assert debug.msg == f"Sending detection request for {_IMAGE_PATH}"
    assert shipped_fields(debug, ["camera_id", "file_path"]) == {
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }


@pytest.mark.asyncio
async def test_open_circuit_rejects_before_the_request(caplog, client, metrics):
    """TWIN COVERAGE for L1072/L1073/L1074: with the shipped breaker reporting an open
    circuit, ``detect_objects`` logs the shipped rejection WARNING at L1069 (detector,
    camera, path, state), reports ``circuit_breaker_open`` and raises without touching the
    transport."""
    client._circuit_breaker.force_open()
    win(caplog)
    with fs(), post() as posted:
        with pytest.raises(M.DetectorUnavailableError) as raised:
            await run_detect(client)

    assert sent(caplog, _ARM_BREAKER_REJECT) == [("DEBUG", 1060), ("WARNING", 1069)], surface(
        caplog, _ARM_BREAKER_REJECT
    )
    warning = one_at(caplog, _ARM_BREAKER_REJECT, "WARNING", 1069)
    assert warning.msg == "Circuit breaker open for yolo26, rejecting detection request"
    assert shipped_fields(warning, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    state = shipped_fields(warning, ["circuit_state"])["circuit_state"]
    assert state == client._circuit_breaker.state.value
    assert "circuit breaker open" in str(raised.value)
    assert metrics.call_args_list == [call("circuit_breaker_open")]
    posted.assert_not_awaited()


@pytest.mark.asyncio
async def test_buffered_frame_debug_record_carries_the_camera(caplog, client):
    """TWIN COVERAGE for L1104: with a frame buffer attached, the buffered-frame DEBUG
    (L1101) names camera_id, frame_size_bytes and buffer_count, between the pre-request
    DEBUG and the empty-result DEBUG."""
    buffer = MagicMock()
    buffer.add_frame = AsyncMock()
    buffer.frame_count = MagicMock(return_value=3)
    client._frame_buffer = buffer
    win(caplog)
    with fs(), post(return_value=response(body={"detections": []})):
        assert await run_detect(client) == []

    buffer.add_frame.assert_awaited_once()
    assert sent(caplog, _ARM_BUFFERED) == [
        ("DEBUG", 1060),
        ("DEBUG", 1101),
        ("DEBUG", 1388),
    ], surface(caplog, _ARM_BUFFERED)
    debug = [r for r in mine_where(caplog, _ARM_BUFFERED) if _anchor(r) == 1101]
    assert len(debug) == 1, surface(caplog, _ARM_BUFFERED)
    assert debug[0].msg == f"Buffered frame for camera {_CAMERA_ID}"
    assert shipped_fields(debug[0], ["camera_id", "frame_size_bytes", "buffer_count"]) == {
        "camera_id": _CAMERA_ID,
        "frame_size_bytes": len(_BYTES),
        "buffer_count": 3,
    }


@pytest.mark.asyncio
async def test_stored_detections_info_and_camera_debug_records(caplog, client):
    """TWIN COVERAGE for L1343/L1379/L1380 (plus the shipped INFO contract): a stored
    detection logs the per-detection DEBUG (L1319), the camera ``last_seen_at`` DEBUG
    (L1341) and the ``Stored detections`` INFO (L1386) naming camera_id, file_path and
    detection_count."""
    camera = MagicMock()
    ses = session_double(camera=camera)
    win(caplog)
    with fs(), post(return_value=response(body=one_body())):
        detections = await run_detect(client, ses)

    assert len(detections) == 1
    ses.add.assert_called_once()
    ses.commit.assert_awaited_once()
    assert camera.last_seen_at is not None
    assert sent(caplog, _ARM_STORED) == [
        ("DEBUG", 1060),
        ("DEBUG", 1319),
        ("DEBUG", 1341),
        ("INFO", 1386),
    ], surface(caplog, _ARM_STORED)
    info = one_at(caplog, _ARM_STORED, "INFO", 1386)
    assert info.msg == "Stored detections"
    assert shipped_fields(info, ["camera_id", "file_path", "detection_count"]) == {
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
        "detection_count": 1,
    }
    debug = [r for r in mine_where(caplog, _ARM_STORED) if _anchor(r) == 1341]
    assert len(debug) == 1, surface(caplog, _ARM_STORED)
    assert debug[0].msg.startswith(f"Updated camera {_CAMERA_ID} last_seen_at to ")
    assert shipped_fields(debug[0], ["camera_id"]) == {"camera_id": _CAMERA_ID}
    assert "last_seen_at" in fields(debug[0])


@pytest.mark.asyncio
async def test_no_detections_debug_record(caplog, client):
    """TWIN COVERAGE for L1391/L1392: an empty result logs the shipped DEBUG at L1388 naming
    the path, camera and duration."""
    win(caplog)
    with fs(), post(return_value=response(body={"detections": []})):
        assert await run_detect(client) == []

    assert sent(caplog, _ARM_NO_DETECT) == [("DEBUG", 1060), ("DEBUG", 1388)], surface(
        caplog, _ARM_NO_DETECT
    )
    debug = [r for r in mine_where(caplog, _ARM_NO_DETECT) if _anchor(r) == 1388]
    assert len(debug) == 1, surface(caplog, _ARM_NO_DETECT)
    assert debug[0].msg == f"No detections above threshold for {_IMAGE_PATH}"
    assert shipped_fields(debug[0], ["camera_id", "file_path"]) == {
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert isinstance(shipped_fields(debug[0], ["duration_ms"])["duration_ms"], int)


@pytest.mark.asyncio
async def test_corrupted_detection_item_is_reported_with_its_traceback(caplog, client, metrics):
    """TWIN COVERAGE for L1331: a detection item whose bbox cannot become an ``int`` raises
    ``ValueError`` inside the shipped ``try`` and is logged as the ``Error processing
    detection data`` ERROR at L1328 with the sanitized error and a traceback; the item is
    dropped, so the run still updates the camera and reports nothing stored."""
    body = {
        "detections": [{"class": "person", "confidence": 0.9, "bbox": ["x", 2, 3, 4]}],
        "image_width": 10,
        "image_height": 10,
    }
    ses = session_double(camera=MagicMock())
    win(caplog)
    with fs(), post(return_value=response(body=body)):
        assert await run_detect(client, ses) == []

    assert sent(caplog, _ARM_CORRUPTED) == [
        ("DEBUG", 1060),
        ("ERROR", 1328),
        ("DEBUG", 1341),
        ("DEBUG", 1388),
    ], surface(caplog, _ARM_CORRUPTED)
    error = one_at(caplog, _ARM_CORRUPTED, "ERROR", 1328)
    assert error.msg == "Error processing detection data"
    assert shipped_fields(error, ["error"]) == {
        "error": "invalid literal for int() with base 10: 'x'"
    }
    assert tracebacks(error)[1] is not None
    assert metrics.call_args_list == [call("detection_processing_error")]


@pytest.mark.asyncio
async def test_a_tripped_circuit_breaker_error_is_reported_and_reraised(caplog, client, metrics):
    """TWIN COVERAGE for L1409/L1410/L1411/L1414: when the shipped breaker raises
    ``CircuitBreakerError`` around the call (the call-phase trip, past ``allow_call``),
    ``detect_objects`` logs the shipped WARNING at L1406 with the six shipped extras
    (including ``"error": str(e)``) and re-raises as ``DetectorUnavailableError``."""
    win(caplog)
    trip = M.CircuitBreakerError("detector_yolo26", "open", recovery_timeout=60.0)
    breaker = MagicMock()
    breaker.allow_call = AsyncMock(return_value=True)
    breaker.call = AsyncMock(side_effect=trip)
    breaker.state = trip.state
    client._circuit_breaker = breaker
    with fs(), post(return_value=response(body=one_body())):
        with pytest.raises(M.DetectorUnavailableError) as raised:
            await run_detect(client)

    assert sent(caplog, _ARM_BREAKER_RAISED) == [("DEBUG", 1060), ("WARNING", 1406)], surface(
        caplog, _ARM_BREAKER_RAISED
    )
    assert raised.value.original_error is trip
    assert metrics.call_args_list == [call("circuit_breaker_open")]
    warning = one_at(caplog, _ARM_BREAKER_RAISED, "WARNING", 1406)
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


@pytest.mark.asyncio
async def test_a_commit_failure_becomes_the_object_detection_error(caplog, client, metrics):
    """TWIN COVERAGE for L1433/L1434/L1438: a ``RuntimeError`` from the commit is logged as
    the shipped ``Unexpected error during object detection`` ERROR at L1430 (detector,
    camera, sanitized error, ``exc_info=True``) and re-raised."""
    boom = RuntimeError("session pool gone")
    win(caplog)
    ses = session_double(camera=MagicMock(), commit_error=boom)
    with fs(), post(return_value=response(body=one_body())):
        with pytest.raises(M.DetectorUnavailableError) as raised:
            await run_detect(client, ses)

    assert sent(caplog, _ARM_COMMIT_FAILED) == [
        ("DEBUG", 1060),
        ("DEBUG", 1319),
        ("DEBUG", 1341),
        ("ERROR", 1430),
    ], surface(caplog, _ARM_COMMIT_FAILED)
    assert raised.value.original_error is boom
    assert metrics.call_args_list == [call("yolo26_unexpected_error")]
    error = one_at(caplog, _ARM_COMMIT_FAILED, "ERROR", 1430)
    assert error.msg == "Unexpected error during object detection"
    assert shipped_fields(error, ["detector_type", "camera_id", "error"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "error": "session pool gone",
    }
    assert isinstance(shipped_fields(error, ["duration_ms"])["duration_ms"], int)
    assert tracebacks(error)[1] is boom
