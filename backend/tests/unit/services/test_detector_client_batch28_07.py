r"""S2 batch-28 lane L6 - ``detector_client`` group dc08 kill battery (74 keys).

Source: ``backend/services/detector_client.py``, md5 ``294c938abe9e37cd0f979f9357982753``.
Manifest: ``/tmp/wp-pw/detector_client/manifest.json`` group
``dc08-send-server-error-4xx-logs`` (74 KILLABLE keys; keys file
``manifest_groups/dc08-send-server-error-4xx-logs.keys``, content identical to
``group_07.keys``).  Splice report ``splice-dc08-send-server-error-4xx-logs.json``:
38 twin / 36 clean / **0 bad** - nothing in this group needs a hand-splice probe.  Candidate
counts below were recomputed with the harness's own matcher (``replay_lib.candidates``)
against this exact source and agree with that report key for key (527 candidate pytest runs,
every one of which compiles).

What the group owns
===================
``DetectorClient._send_detection_request`` (def L596, last statement L919) inside the
``except httpx.HTTPStatusError`` arm (L784-L843).  Shipped behaviour, pinned at those lines:

* ``status_code >= 500`` (L788) is a SERVER failure: a NON-final attempt logs ONE WARNING
  (L792-L803: raw msg ``"Detector server error, retrying"`` plus a seven-field ``extra=``)
  then ``await asyncio.sleep(min(2**attempt, 30))`` (L791 + L804); the FINAL attempt takes the
  ``else`` branch - NO sleep, ONE ``record_pipeline_error("<type>_server_error")`` and ONE
  ERROR ``"Detector server error after all attempts"`` with a five-field ``extra=`` and
  ``exc_info=True`` (L805-L817).  A 1-attempt client therefore logs ONLY that ERROR.
* anything else (L818) is a CLIENT error: NO retry, no sleep.  Only a 400 (L821) reads the
  response body - ``e.response.json().get("detail", str(e))`` (L823-L824), whose
  ``json.JSONDecodeError/ValueError/AttributeError`` handler (L825-L827) falls back to
  ``e.response.text[:500] if e.response.text else str(e)``; every other code keeps the
  ``error_detail = None`` of L820.  Then ONE ``record_pipeline_error("<type>_client_error")``
  (L829), ONE ERROR ``"Detector client error"`` with a five-field ``extra=`` and NO traceback
  (L830-L839) and ``raise ValueError(f"Detector client error {status_code}: {error_detail or e}")
  from e`` (L841-L843).

How every occurrence twin is reddened
=====================================
The harness reddens EVERY text-matching candidate of a key, so a key whose ``before`` text
also sits in an arm this file does not own needs those arms exercised too.  The candidate line
sets, computed with the harness's own matcher against this exact source:

=================================================== ===== ====================================================
``before`` text                                        n  candidate lines (dc08 keys in brackets)
=================================================== ===== ====================================================
``delay = min(2**attempt, 30)``                        6  691 722 [791 m217] 850 883 754
``"Detector server error, retrying",``                  1  [793 m218/222/223/224]
``extra={...seven fields...},``                         1  [794 m219 m221]
``extra={...five fields...},``                          1  [809 m244 m247]
``extra={...five fields (4xx)...},``                    1  [832 m277 m279]
``"detector_type": self._detector_type,``              17  360 695 710 726 741 759 775 [795 m225/226]
                                                          810 [m252/253] 833 [m283/284] 855 870 887 902
                                                          1072 1409 1433
``"camera_id": camera_id,``                            25  696 711 727 742 760 776 [796 m227/228]
                                                          811 [m254/255] 834 [m285/286] 856 871 888 903
                                                          947 967 974 1049 1062 1073 1104 1343 1379
                                                          1391 1410 1434
``"file_path": image_path,``                           20  697 712 728 743 761 777 [797 m229/230]
                                                          812 [m256/257] 835 [m287/288] 857 872 889 904
                                                          948 967 974 1074 1380 1392 1411
``"status_code": status_code,``                         3  [798 m231/232] [813 m258/259] [836 m289/290]
``"attempt": attempt + 1,``                             6  698 729 762 [799 m233-236] 858 890
``"max_retries": self._max_retries,``                   7  365 699 730 763 [800 m237/238] 859 891
``"retry_delay": delay,``                               6  700 731 764 [801 m239/240] 860 892
``"attempts": self._max_retries,``                      6  713 744 778 [814 m260/261] 873 905
``exc_info=True,`` (and the ``arg_drop`` two-line form) 11  433 440 449 716 747 781 [816 m245 m248 m262]
                                                          875 908 1331 1438
``record_pipeline_error("..._server_error")``           1  [806 m242]
``"Detector server error after all attempts",``         1  [808 m243/249/250/251]
``error_detail = None``                                 1  [820 m263]
``if status_code == 400:``                              1  [821 m264 m265]
``error_response = e.response.json()``                  1  [823 m266]
``error_detail = error_response.get("detail", str(e))`` 1  [824 m267-m274]
``record_pipeline_error("..._client_error")``           1  [829 m275]
``"Detector client error",``                            1  [831 m276/280/281/282]
``"error_detail": error_detail,``                       1  [837 m291/292]
``f"Detector client error {code}: {detail or e}"``      1  [842 m293 m294]
=================================================== =====

Every non-bracketed line above is reached by a leg below, and every leg pins the ORDERED
``(levelname, statement lineno)`` fingerprint of its own shipped call sites plus the raw
``record.msg`` and the named ``extra`` attributes of each record it owns, so no occurrence can
sit in while a sibling pretends to be it:

* the five ``delay = min(2**attempt, 30)`` siblings (691/722/754/850/883) -
  ``test_connection_arm_caps_the_delay_at_thirty`` / ``test_timeout_arm_caps_the_delay_at_thirty``
  / ``test_asyncio_timeout_arm_caps_the_delay_at_thirty`` /
  ``test_json_value_arm_caps_the_delay_at_thirty`` / ``test_unexpected_error_arm_caps_the_delay_at_thirty``,
  each a 7-attempt run that reads the six observed delays back out of the retry WARNINGs (the
  cap binds on attempts 5 and 6, so a 31 cap is visible in both the sleep and the record);
* L360/L365 - ``test_init_info_record_names_the_pinned_configuration`` (a REAL client is built
  inside the capture window); L433/L440/L449 - the three ``health_check`` legs; L947/L948 -
  ``test_truncated_image_is_rejected_before_the_request``; L967 -
  ``test_corrupt_image_uses_the_oserror_arm``; L974 - ``test_bad_format_image_uses_the_valueerror_arm``;
  L1049 - ``test_missing_image_is_reported_once``; L1062 - ``test_request_debug_record_names_the_image``;
  L1072/L1073/L1074 - ``test_open_circuit_rejects_before_the_request``; L1104 -
  ``test_buffered_frame_debug_record_carries_the_camera``; L1331 -
  ``test_corrupted_detection_item_is_reported_with_its_traceback``; L1343/L1379/L1380 -
  ``test_stored_detections_info_and_camera_debug_records``; L1391/L1392 -
  ``test_no_detections_debug_record``; L1409/L1410/L1411 -
  ``test_a_tripped_circuit_breaker_error_is_reported_and_reraised``; L1433/L1434/L1438 -
  ``test_a_commit_failure_becomes_the_object_detection_error``;
* L695-L701/L710/L713/L716 and L726-L731/L741/L744/L747 - ``test_connection_arm_six_retries``
  and ``test_timeout_arm_six_retries``; L759-L765/L775/L778/L781 - ``test_asyncio_timeout_arm``;
  L855-L860/L870/L873/L875 - ``test_json_value_arm``; L887-L893/L902/L905/L908 -
  ``test_unexpected_error_arm``;
* L795-L801/L810-L814/L816 - ``test_server_retry_warning_then_final_error`` (a 7-attempt 503,
  which is also the leg that owns m217's own occurrence at L791);
* L833-L837 - the three 4xx legs (``test_client_400_with_json_detail_is_reported_once``,
  ``test_client_400_with_an_unparseable_body_falls_back_to_the_raw_text``,
  ``test_client_400_with_no_detail_key_reports_the_status_error_text`` - the last two also pin
  the two lines of the L825-L827 handler, which only a body that cannot be parsed reaches).

The ``exc_info`` twins (m245/m248/m262) are the one place where the shipped
``exc_info=None``/``exc_info=False`` mutants do NOT change the emitted record - both render "no
traceback" - so the legs that own one of those eleven lines assert the PRESENCE of a populated
3-tuple (which is exactly what ``exc_info=True`` does) and that its exception IS the exception
the shipped ``raise ... from e`` chains, while the legs whose shipped call carries NO
``exc_info`` (the 4xx arm, the validation WARNINGs, the route DEBUGs) assert its ABSENCE.  A
dropped ``extra=`` (a keyword-only ``logger.error(extra=...)`` -> ``TypeError`` swallowed by
the shipped ``except``) shows up as a MISSING record, which the fingerprint assert catches.

Key -> test map (``mNN`` = ``..._send_detection_request__mutmut_NN``)
=====================================================================
* 5xx retry WARNING (L792-L804) - ``test_server_retry_warning_then_final_error`` (7 attempts:
  six WARNINGs + the final ERROR) plus ``test_single_attempt_server_error_never_sleeps_or_warns``:
  m217 (31 cap), m218, m219, m221, m222, m223, m224, m225, m226, m227, m228, m229, m230, m231,
  m232, m233, m234, m235 (``attempt - 1``), m236 (``attempt + 2``), m237, m238, m239, m240.
* 5xx final (L805-L817) - same two legs: m242 (label ``None``), m243, m244, m245, m247, m248,
  m249, m250, m251, m252, m253, m254, m255, m256, m257, m258, m259, m260, m261, m262
  (``exc_info=False``).
* 4xx gate + detail extraction (L818-L827) + report/raise (L829-L843) - the three 400 legs and
  ``test_client_404_keeps_the_detail_none``: m263 (``error_detail = ""``), m264 (``!=``),
  m265 (``== 401``), m266 (``error_response = None``), m267, m268, m269, m270, m271, m272,
  m273, m274, m275 (label ``None``), m276, m277, m279, m280, m281, m282, m283, m284, m285,
  m286, m287, m288, m289, m290, m291, m292, m293 (message ``None``), m294 (``or`` -> ``and``).
* the 30 s cap at L791 - ``test_server_error_arm_caps_the_delay_at_thirty`` (m217's own line)
  and the five sibling-arm legs listed above.

Discipline
----------
* production never bends: the shipped ``_send_detection_request`` / ``detect_objects`` /
  ``health_check`` run on a REAL ``DetectorClient`` (the construction idiom of the shipped
  ``test_detector_client.py`` suite), so the shipped semaphore (L214-L223), circuit breaker
  (L336-L344, L1068, L1129) and retry loop are the code under test.  Patched collaborators are
  the HTTP transport, ``asyncio.sleep``, ``get_settings``, ``record_pipeline_error``,
  ``get_inference_semaphore``, the filesystem/PIL doubles, the thread offloads, the W3C header
  helper and the baseline service - every one of them ``autospec=True`` or ``new=`` (WP4.2
  ratchet).  There is no import-time global spy and no logger/handler mutation: only
  ``caplog``'s own handler sees the records.
* the response doubles are REAL ``httpx.Response`` objects carrying their status, body and
  reason phrase, and the ``HTTPStatusError`` is the one ``raise_for_status()`` actually raises,
  so ``e.response.json()`` / ``e.response.text`` / ``str(e)`` behave like production instead of
  like a mock's default.
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
_ARM_CLIENT = frozenset({830, 944, 965, 972, 1047, 1060})
_ARM_JSON = frozenset({851, 866})
_ARM_UNEXPECTED = frozenset({884, 899})
_ARM_VALIDATE_SMALL = frozenset({944})
_ARM_VALIDATE_OSERROR = frozenset({965})
_ARM_VALIDATE_VALUE = frozenset({972})
_ARM_MISSING = frozenset({1047})
_ARM_REQUEST_DEBUG = frozenset({1060})
_ARM_BREAKER_REJECT = frozenset({1060, 1069})
_ARM_BUFFERED = frozenset({1060, 1101})
_ARM_CORRUPTED = frozenset({1060, 1328, 1341, 1388})
_ARM_STORED = frozenset({1060, 1341, 1386})
_ARM_NO_DETECT = frozenset({1060, 1388})
_ARM_BREAKER_RAISED = frozenset({1060, 1406})
_ARM_COMMIT_FAILED = frozenset({1060, 1341, 1430})
_ARM_HEALTH_CONNECT = frozenset({430})
_ARM_HEALTH_STATUS = frozenset({437})
_ARM_HEALTH_UNEXPECTED = frozenset({446})

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

_IMAGE_PATH = "/export/yard/corridor/frame-0431.jpg"
_CAMERA_ID = "cam-11"
_IMAGE_NAME = "frame-0431.jpg"
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


def traced(triplet, expected=None):
    """A populated ``exc_info`` 3-tuple is present (the shipped ``exc_info=True``), carrying
    ``expected`` as its exception when the leg knows which object that must be."""
    assert isinstance(triplet, tuple), f"no exc_info tuple: {triplet!r}"
    assert len(triplet) == 3, triplet
    assert triplet[1] is not None, "the shipped exc_info=True carries the exception"
    if expected is not None:
        assert triplet[1] is expected, f"traceback carries {triplet[1]!r}, not the shipped cause"
    return triplet


# --------------------------------------------------------------------------- doubles
def status_error(status, *, body=None, raw=None):
    """The shipped ``httpx.HTTPStatusError`` for one REAL ``httpx.Response``.

    ``httpx.Response.raise_for_status()`` raises exactly this object, its message being the
    status reason phrase, so ``str(e)`` is production text and ``e.response.json()`` /
    ``e.response.text`` behave like production - which is what the shipped 400 arm (L821-L827)
    reads.  ``body=`` sends a JSON body; ``raw=`` sends a NON-JSON body (so ``.json()`` raises
    ``JSONDecodeError`` out of the text and the shipped handler L825-L827 reads ``.text``);
    neither sends an empty body, which is the shipped falsy-text case.
    """
    response = (
        httpx.Response(status, json=body, request=_REQUEST)
        if body is not None
        else httpx.Response(status, text=raw if raw is not None else "", request=_REQUEST)
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as raised:
        return raised
    raise AssertionError(f"status {status} does not raise")


# the 5xx the retry arm consumes, and the four 400 body shapes the detail extractor walks
_ERR_503 = status_error(503, body={"detail": "GPU is busy"})
_ERR_400 = status_error(400, body={"detail": "image rejected by the validator"})
_ERR_400_NODETAIL = status_error(400, body={})
_ERR_400_BODY = status_error(400, raw="detectorsize-mismatch: image is 12x9")
_ERR_400_EMPTY = status_error(400)
# the 404 the shipped L821 gate keeps OUT of the json() attempt
_ERR_404 = status_error(404, raw="Detector service has no such route")


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
    (L404, L1115).  Both are pinned autospec at the shipped import site so no leg depends on
    ambient settings or on another test's semaphore."""
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
    assert instance._max_retries == 2  # the ctor argument wins over settings
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
    return await client._send_detection_request(data, _IMAGE_NAME, _CAMERA_ID, _IMAGE_PATH)


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
# --------------------------------------------------------------------------- 5xx arm (L784-L817)


@pytest.mark.asyncio
async def test_server_retry_warning_then_final_error(caplog, client, sleep, metrics, settings):
    """L788-L804 with seven 503 attempts: every non-final attempt logs the shipped WARNING
    (raw msg + the seven ``extra=`` fields) and sleeps ``min(2**attempt, 30)``, so the shipped
    sequence is 1,2,4,8,16,30 and the retry WARNING's ``retry_delay`` repeats the delay that
    was slept."""
    win(caplog)
    resp = response(status=503, status_error=_ERR_503)
    with post(return_value=resp), pytest.raises(M.DetectorUnavailableError) as raised:
        await run_request(client, retries=7)

    assert raised.value.original_error is _ERR_503
    assert raised.value.__cause__ is _ERR_503
    assert sent(caplog, _ARM_SERVER) == [("WARNING", 792)] * 6 + [("ERROR", 807)], surface(
        caplog, _ARM_SERVER
    )
    assert [c.args[0] for c in sleep.call_args_list] == _BACKOFF
    assert [c.args for c in metrics.call_args_list] == [("yolo26_server_error",)]
    warnings = warned(caplog, _ARM_SERVER, 792)
    assert [r.msg for r in warnings] == ["Detector server error, retrying"] * 6
    assert delays(warnings) == _BACKOFF
    assert retried(warnings) == _RETRIED
    assert [shipped_fields(r, ["status_code"])["status_code"] for r in warnings] == [503] * 6
    assert all(r.exc_info is None for r in warnings)


@pytest.mark.asyncio
async def test_server_final_error_names_the_status_and_keeps_its_traceback(
    caplog, client, sleep, metrics, settings
):
    """L805-L817: the FINAL attempt skips the sleep, reports ``yolo26_server_error`` and logs
    the shipped ERROR msg with its five extras and a real ``exc_info`` 3-tuple carrying the
    503 - and the retry WARNINGs' three shared names are pinned against the ERROR's, whose
    values are asserted straight off the shipped literals."""
    win(caplog)
    resp = response(status=503, status_error=_ERR_503)
    with post(return_value=resp), pytest.raises(M.DetectorUnavailableError):
        await run_request(client, retries=7)

    assert [c.args[0] for c in sleep.call_args_list] == _BACKOFF  # six sleeps, seven attempts
    assert [c.args for c in metrics.call_args_list] == [("yolo26_server_error",)]
    error = one_at(caplog, _ARM_SERVER, "ERROR", 807)
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
    traced(error.exc_info, _ERR_503)
    warnings = warned(caplog, _ARM_SERVER, 792)
    warning_fields = [
        shipped_fields(r, ["detector_type", "camera_id", "file_path", "status_code"])
        for r in warnings
    ]
    assert (
        warning_fields
        == [
            {
                "detector_type": "yolo26",
                "camera_id": _CAMERA_ID,
                "file_path": _IMAGE_PATH,
                "status_code": 503,
            }
        ]
        * 6
    )  # pins L795-L798 against L810-L813


@pytest.mark.asyncio
async def test_single_attempt_server_error_never_sleeps_or_warns(
    caplog, client, sleep, metrics, settings
):
    """``max_retries=1`` makes attempt 0 the FINAL one (L790 is false), so the shipped 503 run
    is ONE ERROR at L807 with ``attempts == 1`` and no WARNING at all - and the exhausted loop
    raises ``DetectorUnavailableError("Detection failed after 1 attempts") from the 503."""
    win(caplog)
    resp = response(status=503, status_error=_ERR_503)
    with post(return_value=resp), pytest.raises(M.DetectorUnavailableError) as raised:
        await run_request(client, retries=1)

    assert sent(caplog, _ARM_SERVER) == [("ERROR", 807)], surface(caplog, _ARM_SERVER)
    assert sleep.await_count == 0
    assert [c.args for c in metrics.call_args_list] == [("yolo26_server_error",)]
    error = one_at(caplog, _ARM_SERVER, "ERROR", 807)
    assert shipped_fields(error, ["attempts"]) == {"attempts": 1}
    assert str(raised.value) == "Detection failed after 1 attempts"
    assert raised.value.original_error is _ERR_503
    assert error.exc_info is not None


@pytest.mark.asyncio
async def test_server_error_arm_caps_the_delay_at_thirty(caplog, client, sleep, metrics, settings):
    """L791 is one of SIX identical ``delay = min(2**attempt, 30)`` statements: on the 503 arm
    the cap binds on attempts 5 and 6, so the slept - and logged - sequence is 1,2,4,8,16,30."""
    win(caplog)
    resp = response(status=503, status_error=_ERR_503)
    with post(return_value=resp), pytest.raises(M.DetectorUnavailableError):
        await run_request(client, retries=7)

    assert [c.args[0] for c in sleep.call_args_list] == _BACKOFF
    assert delays(warned(caplog, _ARM_SERVER, 792)) == _BACKOFF


# --------------------------------------------------------------------------- 4xx arm (L818-L843)


@pytest.mark.asyncio
async def test_client_400_with_json_detail_is_reported_once(
    caplog, client, sleep, metrics, settings
):
    """L821-L824 + L829-L843: a 400 whose body carries ``{"detail": ...}`` is NOT retried -
    one ``record_pipeline_error("yolo26_client_error")``, one ERROR with the shipped five
    extras and NO traceback, then a ``ValueError`` whose message is the shipped f-string built
    from the extracted detail, chained ``from`` the status error."""
    win(caplog)
    resp = response(status=400, status_error=_ERR_400)
    with post(return_value=resp) as posted, pytest.raises(ValueError) as raised:
        await run_request(client, retries=3)

    assert posted.await_count == 1
    assert sleep.await_count == 0
    assert metrics.call_args_list == [call("yolo26_client_error")]
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
        "error_detail": _ERR_400.response.json()["detail"],
    }
    assert error.exc_info is None, "the 4xx arm is logged without a traceback"
    assert str(raised.value) == f"Detector client error 400: {_ERR_400.response.json()['detail']}"
    assert raised.value.__cause__ is _ERR_400


@pytest.mark.asyncio
async def test_client_400_with_an_unparseable_body_falls_back_to_the_raw_text(
    caplog, client, sleep, metrics, settings
):
    """L825-L827: a 400 whose body is not JSON raises out of ``e.response.json()`` and the
    shipped handler reads ``e.response.text[:500]``, so the ERROR's ``error_detail`` IS the raw
    body text and the raised message carries it too."""
    raw = "detectorsize-mismatch: image is 12x9"
    win(caplog)
    resp = response(status=400, status_error=_ERR_400_BODY)
    with post(return_value=resp), pytest.raises(ValueError) as raised:
        await run_request(client, retries=3)

    assert sleep.await_count == 0
    assert metrics.call_args_list == [call("yolo26_client_error")]
    assert sent(caplog, _ARM_CLIENT) == [("ERROR", 830)], surface(caplog, _ARM_CLIENT)
    error = one_at(caplog, _ARM_CLIENT, "ERROR", 830)
    assert shipped_fields(error, ["error_detail"]) == {"error_detail": raw}
    assert str(raised.value) == f"Detector client error 400: {raw}"


@pytest.mark.asyncio
async def test_client_400_with_an_empty_body_falls_back_to_the_status_error_text(
    caplog, client, sleep, metrics, settings
):
    """The shipped falsy branch of L827: an empty body makes ``e.response.text`` falsy, so the
    handler's ``else`` arm contributes ``str(e)`` - the status error's own message - and the
    raised ``ValueError`` starts with the shipped prefix followed by exactly that text."""
    win(caplog)
    resp = response(status=400, status_error=_ERR_400_EMPTY)
    with post(return_value=resp), pytest.raises(ValueError) as raised:
        await run_request(client, retries=3)

    assert metrics.call_args_list == [call("yolo26_client_error")]
    assert sent(caplog, _ARM_CLIENT) == [("ERROR", 830)], surface(caplog, _ARM_CLIENT)
    assert shipped_fields(one_at(caplog, _ARM_CLIENT, "ERROR", 830), ["error_detail"]) == {
        "error_detail": str(_ERR_400_EMPTY)
    }
    assert str(raised.value).startswith("Detector client error 400: ")
    assert str(raised.value) == f"Detector client error 400: {_ERR_400_EMPTY!s}"


@pytest.mark.asyncio
async def test_client_400_with_no_detail_key_reports_the_status_error_text(
    caplog, client, sleep, metrics, settings
):
    """L824's default: a 400 whose JSON body has NO ``detail`` key keeps the
    ``.get("detail", str(e))`` fallback, so ``error_detail`` is exactly ``str(e)`` - which
    rules out the ``str(None)`` and ``None`` defaults and every renamed lookup key."""
    win(caplog)
    resp = response(status=400, status_error=_ERR_400_NODETAIL)
    with post(return_value=resp), pytest.raises(ValueError) as raised:
        await run_request(client, retries=3)

    assert metrics.call_args_list == [call("yolo26_client_error")]
    assert sent(caplog, _ARM_CLIENT) == [("ERROR", 830)], surface(caplog, _ARM_CLIENT)
    error = one_at(caplog, _ARM_CLIENT, "ERROR", 830)
    assert shipped_fields(error, ["error_detail", "status_code"]) == {
        "error_detail": str(_ERR_400_NODETAIL),
        "status_code": 400,
    }
    assert str(raised.value) == f"Detector client error 400: {_ERR_400_NODETAIL!s}"


@pytest.mark.asyncio
async def test_client_404_keeps_the_detail_none(caplog, client, sleep, metrics, settings):
    """L820-L821 with a 404: only a 400 reads the body, so ``error_detail`` stays ``None`` (the
    record carries the key with a ``None`` value) and the shipped ``{error_detail or e}``
    fallback puts the status error's text into the raised ``ValueError``."""
    win(caplog)
    resp = response(status=404, status_error=_ERR_404)
    with post(return_value=resp), pytest.raises(ValueError) as raised:
        await run_request(client, retries=3)

    assert sleep.await_count == 0
    assert metrics.call_args_list == [call("yolo26_client_error")]
    assert sent(caplog, _ARM_CLIENT) == [("ERROR", 830)], surface(caplog, _ARM_CLIENT)
    error = one_at(caplog, _ARM_CLIENT, "ERROR", 830)
    have = fields(error)
    assert have["error_detail"] is None
    assert shipped_fields(error, ["status_code"]) == {"status_code": 404}
    assert str(raised.value) == f"Detector client error 404: {_ERR_404!s}"


@pytest.mark.asyncio
async def test_detect_objects_swallows_the_client_error_and_reports_nothing(
    caplog, client, metrics, settings
):
    """The shipped consequence of the 4xx raise: ``detect_objects`` catches the ``ValueError``
    at L1399-L1401 and returns ``[]``, so the route logs the pre-request DEBUG (L1060) and the
    client ERROR (L830) only - the empty-result DEBUG at L1388 never fires - and the 400 is NOT
    counted as a transient failure."""
    win(caplog)
    resp = response(status=400, status_error=_ERR_400)
    with fs(), post(return_value=resp) as posted:
        assert await run_detect(client) == []

    assert posted.await_count == 1
    assert metrics.call_args_list == [call("yolo26_client_error")]
    assert sent(caplog, _ARM_CLIENT) == [
        ("DEBUG", 1060),
        ("ERROR", 830),
    ], surface(caplog, _ARM_CLIENT)


# --------------------------------------------------------------------------- cap twins (five siblings)


@pytest.mark.asyncio
async def test_connection_arm_caps_the_delay_at_thirty(caplog, client, sleep, metrics, settings):
    """TWIN COVERAGE for L691: seven ConnectError attempts sleep 1,2,4,8,16,30 and every retry
    WARNING's ``retry_delay`` repeats the delay that was slept."""
    win(caplog)
    with post(side_effect=httpx.ConnectError("refused")):
        with pytest.raises(M.DetectorUnavailableError):
            await run_request(client, retries=7)

    assert sent(caplog, _ARM_CONNECT) == [("WARNING", 692)] * 6 + [("ERROR", 707)], surface(
        caplog, _ARM_CONNECT
    )
    assert [c.args[0] for c in sleep.call_args_list] == _BACKOFF
    assert delays(warned(caplog, _ARM_CONNECT, 692)) == _BACKOFF
    assert [c.args for c in metrics.call_args_list] == [("yolo26_connection_error",)]


@pytest.mark.asyncio
async def test_timeout_arm_caps_the_delay_at_thirty(caplog, client, sleep, metrics, settings):
    """TWIN COVERAGE for L722: the same capped sequence on the TimeoutException arm."""
    win(caplog)
    with post(side_effect=httpx.TimeoutException("slow")):
        with pytest.raises(M.DetectorUnavailableError):
            await run_request(client, retries=7)

    assert sent(caplog, _ARM_TIMEOUT) == [("WARNING", 723)] * 6 + [("ERROR", 738)], surface(
        caplog, _ARM_TIMEOUT
    )
    assert [c.args[0] for c in sleep.call_args_list] == _BACKOFF
    assert delays(warned(caplog, _ARM_TIMEOUT, 723)) == _BACKOFF
    assert [c.args for c in metrics.call_args_list] == [("yolo26_timeout",)]


@pytest.mark.asyncio
async def test_json_value_arm_caps_the_delay_at_thirty(caplog, client, sleep, metrics, settings):
    """TWIN COVERAGE for L850: a malformed JSON body is retried with the capped sequence."""
    win(caplog)
    resp = response(json_error=json.JSONDecodeError("Expecting value", "not-json", 0))
    with post(return_value=resp), pytest.raises(M.DetectorUnavailableError):
        await run_request(client, retries=7)

    assert sent(caplog, _ARM_JSON) == [("WARNING", 851)] * 6 + [("ERROR", 866)], surface(
        caplog, _ARM_JSON
    )
    assert [c.args[0] for c in sleep.call_args_list] == _BACKOFF
    assert delays(warned(caplog, _ARM_JSON, 851)) == _BACKOFF
    assert [c.args for c in metrics.call_args_list] == [("yolo26_json_error",)]


@pytest.mark.asyncio
async def test_unexpected_error_arm_caps_the_delay_at_thirty(
    caplog, client, sleep, metrics, settings
):
    """TWIN COVERAGE for L883: an ``OSError`` out of the transport is retried with the capped
    sequence and its ``sanitize_error`` text in the ``error`` extra."""
    win(caplog)
    with post(side_effect=OSError("disk went away")):
        with pytest.raises(M.DetectorUnavailableError):
            await run_request(client, retries=7)

    assert sent(caplog, _ARM_UNEXPECTED) == [("WARNING", 884)] * 6 + [("ERROR", 899)], surface(
        caplog, _ARM_UNEXPECTED
    )
    assert [c.args[0] for c in sleep.call_args_list] == _BACKOFF
    assert delays(warned(caplog, _ARM_UNEXPECTED, 884)) == _BACKOFF
    assert [c.args for c in metrics.call_args_list] == [("yolo26_unexpected_error",)]


class _TrippingTimeout:
    """Stand-in for the shipped ``asyncio.timeout`` gate (L665) that always trips.

    ``asyncio.timeout`` is patched ``new=`` for the leg only: the shipped ``except TimeoutError``
    arm (L750-L782) then runs for real, which is the only way to reach the L754/L759-L765/
    L775/L778/L781 twins this group's texts collide with.
    """

    def __init__(self, seconds, raises):
        self.seconds = seconds
        self.raises = raises

    async def __aenter__(self):
        raise self.raises

    async def __aexit__(self, *exc_info):
        return False


@pytest.mark.asyncio
async def test_asyncio_timeout_arm_caps_the_delay_at_thirty(
    caplog, client, sleep, metrics, settings
):
    """TWIN COVERAGE for L754: with the shipped timeout gate tripping on every attempt the
    ``TimeoutError`` arm reaches the same cap."""
    win(caplog)
    with (
        patch.object(
            asyncio, "timeout", new=lambda seconds: _TrippingTimeout(seconds, TimeoutError("gate"))
        ),
        post(),
        pytest.raises(M.DetectorUnavailableError),
    ):
        await run_request(client, retries=7)

    assert sent(caplog, _ARM_ASYNCIO) == [("WARNING", 755)] * 6 + [("ERROR", 771)], surface(
        caplog, _ARM_ASYNCIO
    )
    assert [c.args[0] for c in sleep.call_args_list] == _BACKOFF
    assert delays(warned(caplog, _ARM_ASYNCIO, 755)) == _BACKOFF
    assert [c.args for c in metrics.call_args_list] == [("yolo26_asyncio_timeout",)]


# --------------------------------------------------------------------------- six-retry twins (ConnectError, Timeout)


@pytest.mark.asyncio
async def test_connection_arm_six_retries_pin_every_retry_field(
    caplog, client, sleep, metrics, settings
):
    """TWIN COVERAGE for L695-L701/L710/L713/L716: the ConnectError arm's six WARNINGs walk
    ``attempt`` 1..6 against ``max_retries`` 7 (so ``attempt + 1`` is pinned in both
    directions) and its final ERROR keeps a traceback carrying the transport error."""
    boom = httpx.ConnectError("refused")
    win(caplog)
    with post(side_effect=boom), pytest.raises(M.DetectorUnavailableError) as raised:
        await run_request(client, retries=7)

    assert raised.value.original_error is boom
    assert sent(caplog, _ARM_CONNECT) == [("WARNING", 692)] * 6 + [("ERROR", 707)], surface(
        caplog, _ARM_CONNECT
    )
    warnings = warned(caplog, _ARM_CONNECT, 692)
    assert [r.msg for r in warnings] == ["Detector connection error, retrying"] * 6
    assert retried(warnings) == _RETRIED
    assert delays(warnings) == _BACKOFF
    assert [shipped_fields(r, ["detector_type", "camera_id", "file_path"]) for r in warnings] == [
        {
            "detector_type": "yolo26",
            "camera_id": _CAMERA_ID,
            "file_path": _IMAGE_PATH,
        }
    ] * 6
    assert [shipped_fields(r, ["error"])["error"] for r in warnings] == ["refused"] * 6
    assert all(r.exc_info is None for r in warnings)
    error = one_at(caplog, _ARM_CONNECT, "ERROR", 707)
    assert error.msg == "Detector connection error after all attempts"
    assert shipped_fields(error, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(error, ["attempts", "error"]) == {"attempts": 7, "error": "refused"}
    traced(error.exc_info, boom)


@pytest.mark.asyncio
async def test_timeout_arm_six_retries_pin_every_retry_field(
    caplog, client, sleep, metrics, settings
):
    """TWIN COVERAGE for L726-L731/L741/L744/L747: the TimeoutException arm's mirror leg."""
    boom = httpx.TimeoutException("slow")
    win(caplog)
    with post(side_effect=boom), pytest.raises(M.DetectorUnavailableError) as raised:
        await run_request(client, retries=7)

    assert raised.value.original_error is boom
    assert sent(caplog, _ARM_TIMEOUT) == [("WARNING", 723)] * 6 + [("ERROR", 738)], surface(
        caplog, _ARM_TIMEOUT
    )
    warnings = warned(caplog, _ARM_TIMEOUT, 723)
    assert [r.msg for r in warnings] == ["Detector timeout, retrying"] * 6
    assert retried(warnings) == _RETRIED
    assert delays(warnings) == _BACKOFF
    assert [shipped_fields(r, ["detector_type", "camera_id", "file_path"]) for r in warnings] == [
        {
            "detector_type": "yolo26",
            "camera_id": _CAMERA_ID,
            "file_path": _IMAGE_PATH,
        }
    ] * 6
    assert [shipped_fields(r, ["error"])["error"] for r in warnings] == ["slow"] * 6
    error = one_at(caplog, _ARM_TIMEOUT, "ERROR", 738)
    assert error.msg == "Detector timeout after all attempts"
    assert shipped_fields(error, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(error, ["attempts", "error"]) == {"attempts": 7, "error": "slow"}
    traced(error.exc_info, boom)


@pytest.mark.asyncio
async def test_asyncio_timeout_arm_pins_its_f_string_and_extras(
    caplog, client, sleep, metrics, settings
):
    """TWIN COVERAGE for L759-L765/L775/L778/L781: the tripped-gate arm's f-string WARNINGs
    carry the attempt, the retry delay and the shipped ``explicit_timeout``, and its final
    ERROR keeps a traceback carrying the raised gate error."""
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
    warnings = warned(caplog, _ARM_ASYNCIO, 755)
    assert [r.msg for r in warnings] == [
        f"Detector asyncio timeout (attempt {n}/7), retrying in {d}s: "
        f"request timed out after {_TIMEOUT}s"
        for n, d in enumerate(_BACKOFF, start=1)
    ]
    assert delays(warnings) == _BACKOFF
    assert retried(warnings) == _RETRIED
    assert [shipped_fields(r, ["explicit_timeout"])["explicit_timeout"] for r in warnings] == [
        _TIMEOUT
    ] * 6
    error = one_at(caplog, _ARM_ASYNCIO, "ERROR", 771)
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
    traced(error.exc_info, trip)
    assert [shipped_fields(r, ["detector_type", "camera_id", "file_path"]) for r in warnings] == [
        {
            "detector_type": "yolo26",
            "camera_id": _CAMERA_ID,
            "file_path": _IMAGE_PATH,
        }
    ] * 6


@pytest.mark.asyncio
async def test_json_value_arm_pins_its_f_string_and_extras(
    caplog, client, sleep, metrics, settings
):
    """TWIN COVERAGE for L855-L860/L870/L873/L875: the malformed-JSON arm's msg is the shipped
    f-string carrying the full ``JSONDecodeError`` sentence, and its final ERROR keeps a
    traceback carrying that error."""
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
    warnings = warned(caplog, _ARM_JSON, 851)
    assert [r.msg for r in warnings] == [
        f"Detector JSON/value error (attempt {n}/7), retrying in {d}s: {detail}"
        for n, d in enumerate(_BACKOFF, start=1)
    ]
    assert delays(warnings) == _BACKOFF
    assert retried(warnings) == _RETRIED
    error = one_at(caplog, _ARM_JSON, "ERROR", 866)
    assert error.msg == f"Detector JSON/value error after 7 attempts: {detail}"
    assert shipped_fields(error, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(error, ["attempts"]) == {"attempts": 7}
    traced(error.exc_info, body_error)
    assert [shipped_fields(r, ["detector_type", "camera_id", "file_path"]) for r in warnings] == [
        {
            "detector_type": "yolo26",
            "camera_id": _CAMERA_ID,
            "file_path": _IMAGE_PATH,
        }
    ] * 6


@pytest.mark.asyncio
async def test_unexpected_error_arm_pins_its_fields_and_traceback(
    caplog, client, sleep, metrics, settings
):
    """TWIN COVERAGE for L887-L893/L902/L905/L908: the ``OSError`` arm's WARNINGs carry the
    sanitized error text alongside the shared names and its final ERROR keeps a traceback."""
    boom = OSError("disk went away")
    win(caplog)
    with post(side_effect=boom), pytest.raises(M.DetectorUnavailableError) as raised:
        await run_request(client, retries=7)

    assert raised.value.original_error is boom
    assert sent(caplog, _ARM_UNEXPECTED) == [("WARNING", 884)] * 6 + [("ERROR", 899)], surface(
        caplog, _ARM_UNEXPECTED
    )
    warnings = warned(caplog, _ARM_UNEXPECTED, 884)
    assert [r.msg for r in warnings] == ["Unexpected detector error, retrying"] * 6
    assert delays(warnings) == _BACKOFF
    assert retried(warnings) == _RETRIED
    assert [shipped_fields(r, ["error"])["error"] for r in warnings] == ["disk went away"] * 6
    error = one_at(caplog, _ARM_UNEXPECTED, "ERROR", 899)
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
    traced(error.exc_info, boom)
    assert [shipped_fields(r, ["detector_type", "camera_id", "file_path"]) for r in warnings] == [
        {
            "detector_type": "yolo26",
            "camera_id": _CAMERA_ID,
            "file_path": _IMAGE_PATH,
        }
    ] * 6


# --------------------------------------------------------------------------- other-site twins


@pytest.mark.asyncio
async def test_init_info_record_names_the_pinned_configuration(caplog, settings):
    """TWIN COVERAGE for L360/L365: a real client built from the pinned settings emits exactly
    ONE record - the INFO at L357 - whose ``detector_type`` and ``max_retries`` extras carry
    the shipped names and the pinned values."""
    win(caplog)
    instance = DetectorClient(max_retries=4)

    assert sent(caplog, _ARM_INIT) == [("INFO", 357)], surface(caplog, _ARM_INIT)
    info = one_at(caplog, _ARM_INIT, "INFO", 357)
    assert info.msg == "DetectorClient initialized"
    assert shipped_fields(info, ["detector_type", "max_retries"]) == {
        "detector_type": "yolo26",
        "max_retries": 4,
    }
    assert instance._max_retries == 4


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
        traced(warning.exc_info, exc)


@pytest.mark.asyncio
async def test_health_check_status_arm_keeps_its_traceback(caplog, client):
    """TWIN COVERAGE for L440: the ``HTTPStatusError`` arm logs its own shipped sentence at
    L437 and its traceback carries that status error."""
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
    traced(warning.exc_info, _ERR_503)


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
    traced(error.exc_info, boom)


@pytest.mark.asyncio
async def test_truncated_image_is_rejected_before_the_request(caplog, client, metrics):
    """TWIN COVERAGE for L947/L948: a file below ``MIN_DETECTION_IMAGE_SIZE`` never reaches the
    detector - one WARNING at L944 naming camera, path, size and floor."""
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
async def test_corrupt_image_uses_the_oserror_arm(caplog, client, metrics):
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
async def test_bad_format_image_uses_the_valueerror_arm(caplog, client, metrics):
    """TWIN COVERAGE for L974: the ``ValueError``/``RuntimeError`` arm logs the shorter shipped
    sentence at L972 with the sanitized error."""
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
    """TWIN COVERAGE for L1049: a missing file logs ONE ERROR at L1047 naming camera and path,
    reports ``file_not_found`` and never opens the detector."""
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
    """TWIN COVERAGE for L1062: the pre-request DEBUG (L1060) names the camera and the path and
    is the only owned record of a clean, detection-free run whose empty-result DEBUG sits
    outside this leg's ownership."""
    win(caplog)
    with fs(), post(return_value=response()):
        assert await run_detect(client) == []

    assert sent(caplog, _ARM_REQUEST_DEBUG) == [("DEBUG", 1060)], surface(
        caplog, _ARM_REQUEST_DEBUG
    )
    debug = one_at(caplog, _ARM_REQUEST_DEBUG, "DEBUG", 1060)
    assert debug.msg == f"Sending detection request for {_IMAGE_PATH}"
    assert shipped_fields(debug, ["camera_id", "file_path"]) == {
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }


@pytest.mark.asyncio
async def test_open_circuit_rejects_before_the_request(caplog, client, metrics):
    """TWIN COVERAGE for L1072/L1073/L1074: with the shipped breaker reporting an open circuit,
    ``detect_objects`` logs the shipped rejection WARNING at L1069 (detector, camera, path,
    state), reports ``circuit_breaker_open`` and raises without touching the transport."""
    client._circuit_breaker.force_open()
    win(caplog)
    with fs(), post() as posted:
        with pytest.raises(M.DetectorUnavailableError) as raised:
            await run_detect(client)

    assert sent(caplog, _ARM_BREAKER_REJECT) == [
        ("DEBUG", 1060),
        ("WARNING", 1069),
    ], surface(caplog, _ARM_BREAKER_REJECT)
    warning = one_at(caplog, _ARM_BREAKER_REJECT, "WARNING", 1069)
    assert warning.msg == "Circuit breaker open for yolo26, rejecting detection request"
    assert shipped_fields(warning, ["detector_type", "camera_id", "file_path"]) == {
        "detector_type": "yolo26",
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert shipped_fields(warning, ["circuit_state"])["circuit_state"] == (
        client._circuit_breaker.state.value
    )
    assert "circuit breaker open" in str(raised.value)
    assert metrics.call_args_list == [call("circuit_breaker_open")]
    posted.assert_not_awaited()


@pytest.mark.asyncio
async def test_buffered_frame_debug_record_carries_the_camera(caplog, client):
    """TWIN COVERAGE for L1104: with a frame buffer attached, the buffered-frame DEBUG (L1101)
    names camera_id, frame_size_bytes and buffer_count - the shipped record between the
    pre-request DEBUG and the empty-result DEBUG."""
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
    ], surface(caplog, _ARM_BUFFERED)
    debug = one_at(caplog, _ARM_BUFFERED, "DEBUG", 1101)
    assert debug.msg == f"Buffered frame for camera {_CAMERA_ID}"
    assert shipped_fields(debug, ["camera_id", "frame_size_bytes", "buffer_count"]) == {
        "camera_id": _CAMERA_ID,
        "frame_size_bytes": len(_BYTES),
        "buffer_count": 3,
    }


@pytest.mark.asyncio
async def test_corrupted_detection_item_is_reported_with_its_traceback(caplog, client, metrics):
    """TWIN COVERAGE for L1331: a detection item whose bbox cannot become an ``int`` raises
    ``ValueError`` inside the shipped ``try`` and is logged as the ``Error processing detection
    data`` ERROR at L1328 with the sanitized error and a traceback; the item is dropped."""
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
    traced(error.exc_info)
    assert metrics.call_args_list == [call("detection_processing_error")]


@pytest.mark.asyncio
async def test_stored_detections_info_and_camera_debug_records(caplog, client):
    """TWIN COVERAGE for L1343/L1379/L1380 (plus the shipped INFO contract): a stored detection
    logs the camera ``last_seen_at`` DEBUG (L1341) and the ``Stored detections`` INFO (L1386)
    naming camera_id, file_path and detection_count."""
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
    debug = one_at(caplog, _ARM_STORED, "DEBUG", 1341)
    assert debug.msg.startswith(f"Updated camera {_CAMERA_ID} last_seen_at to ")
    assert shipped_fields(debug, ["camera_id"]) == {"camera_id": _CAMERA_ID}
    assert "last_seen_at" in fields(debug)


@pytest.mark.asyncio
async def test_no_detections_debug_record(caplog, client):
    """TWIN COVERAGE for L1391/L1392: an empty result logs the shipped DEBUG at L1388 naming the
    path, camera and an integer duration."""
    win(caplog)
    with fs(), post(return_value=response(body={"detections": []})):
        assert await run_detect(client) == []

    assert sent(caplog, _ARM_NO_DETECT) == [
        ("DEBUG", 1060),
        ("DEBUG", 1388),
    ], surface(caplog, _ARM_NO_DETECT)
    debug = one_at(caplog, _ARM_NO_DETECT, "DEBUG", 1388)
    assert debug.msg == f"No detections above threshold for {_IMAGE_PATH}"
    assert shipped_fields(debug, ["camera_id", "file_path"]) == {
        "camera_id": _CAMERA_ID,
        "file_path": _IMAGE_PATH,
    }
    assert isinstance(shipped_fields(debug, ["duration_ms"])["duration_ms"], int)


@pytest.mark.asyncio
async def test_a_tripped_circuit_breaker_error_is_reported_and_reraised(caplog, client, metrics):
    """TWIN COVERAGE for L1409/L1410/L1411: when the shipped breaker raises
    ``CircuitBreakerError`` around the call (the call-phase trip, past ``allow_call``),
    ``detect_objects`` logs the shipped WARNING at L1406 with the six shipped extras and
    re-raises as ``DetectorUnavailableError`` - and its call carries NO ``exc_info``."""
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

    assert sent(caplog, _ARM_BREAKER_RAISED) == [
        ("DEBUG", 1060),
        ("WARNING", 1406),
    ], surface(caplog, _ARM_BREAKER_RAISED)
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
    assert warning.exc_info is None


@pytest.mark.asyncio
async def test_a_commit_failure_becomes_the_object_detection_error(caplog, client, metrics):
    """TWIN COVERAGE for L1433/L1434/L1438: a ``RuntimeError`` from the commit is logged as the
    shipped ``Unexpected error during object detection`` ERROR at L1430 (detector, camera,
    sanitized error, ``exc_info=True``) and re-raised with that error as its cause."""
    boom = RuntimeError("session pool gone")
    win(caplog)
    ses = session_double(camera=MagicMock(), commit_error=boom)
    with fs(), post(return_value=response(body=one_body())):
        with pytest.raises(M.DetectorUnavailableError) as raised:
            await run_detect(client, ses)

    assert sent(caplog, _ARM_COMMIT_FAILED) == [
        ("DEBUG", 1060),
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
    traced(error.exc_info, boom)
