"""S2 batch-28 lane L4 - ``detector_client`` group dc04 kill battery (73 keys).

Module: ``backend/services/detector_client.py`` (md5
``294c938abe9e37cd0f979f9357982753``, re-verified before and after this file was
written - the source is never edited).  Admitted manifest:
``/tmp/wp-pw/detector_client/manifest.json`` group
``dc04-warmth-warmup-readiness-probe`` - 73 KILLABLE / 0 EQUIVALENT / 0
NEEDS_INVESTIGATION; keys file
``manifest_groups/dc04-warmth-warmup-readiness-probe.keys``; splice report
``splice-dc04-warmth-warmup-readiness-probe.json``: **73 clean / 0 bad**, so no
key in this group needs a hand-splice probe.

Every key sits in the warmth block, on THIS blob:

* ``DetectorClient.is_cold``               L464-477  (1 key:  L477)
* ``DetectorClient.get_warmth_state``      L479-504  (8 keys: L493, L499, L500 x2, L502 x4)
* ``DetectorClient.model_readiness_probe`` L506-541  (19 keys: L520 x3, L525, L528 x8,
                                                      L530/L531/L532 x2, L537)
* ``DetectorClient.warmup``                L543-594  (45 keys: L566-571 (1/2/6/4),
                                                      L576/L577 (1/3), L582-586 (3/6/3/4),
                                                      L590/L591/L594 (6/4/2))

Production never bends: every literal below is transcribed from the shipped line
quoted in the leg that asserts it.

Settings are INJECTED (``settings`` fixture) rather than inherited, so the
cold-start threshold the warmth arithmetic is judged against (25.0 s) is
fixture-owned and the boundary legs can be placed exactly ON it; the client is
built by the shipped ``__init__`` and the fixture asserts that the ctor argument
``max_retries=1`` beat ``settings.detector_max_retries=2``, so no leg can be
quietly satisfied by a settings value the client never read.

Observation strategy
====================
``warmup`` runs ``from backend.core.metrics import ...`` INSIDE the def
(L556-560), so the three collaborators resolve through ``backend.core.metrics``
on every call and that is the module the watchers patch -
``patch.object(METRICS, name, autospec=True, side_effect=<watcher>)`` where the
watcher records the call and then runs the SHIPPED callable.  That buys three
independent surfaces for the same shipped line:

1. the recorded ARGS - the exact surface every ``arg->None`` and string-rename
   mutant moves (the shipped ``None``-ed and dropped forms stay distinguishable,
   since an autospec'd spy records an absent keyword as absent);
2. the shipped Prometheus objects themselves - ``MODEL_WARMUP_DURATION`` sums the
   duration, ``MODEL_COLD_START_TOTAL`` increments, and ``MODEL_WARMTH_STATE``
   maps its label through the shipped dict ``{"cold": 0, "warming": 1, "warm":
   2}`` (``backend/core/metrics.py`` L3423), so a renamed label silently becomes
   ``0`` and a renamed model writes a different child;
3. the interleaving - every watcher records the world as it found it (how many
   observations existed, what ``_is_warming`` held, which INFO lines had been
   emitted), which is the only available channel for the ordering the shipped
   block encodes between L567, L568, L571, L577, L582 and L583/L590.

The readiness probe's transport is ``patch.object(client,
"_send_detection_request", new=AsyncMock(spec=...))`` - the shipped call at
L528-533 is an attribute lookup, so the record is exactly
``call(image_data=..., image_name=..., camera_id=..., image_path=...)``, which is
precisely the 16-key surface of L525/L528-532.  The image is also read back
through PIL: a leg decodes the captured bytes and asserts ``size == (32, 32)``,
``mode == "RGB"`` and ``getextrema() == ((0, 0), (0, 0), (0, 0))``.  Re-encoding
the shipped triple locally reproduces the captured bytes EXACTLY (probed), so
whole-object byte equality is available as a pin, and the three sibling triples
((33, 32), (32, 33) and the (0, 1, 0) colour) provably differ from it.

Clock discipline
================
``time.monotonic`` / ``time.perf_counter`` are NEVER patched, and the real
``time`` module is never replaced process-wide.  A leg that needs an arithmetic
boundary does ``patch.object(M, "time", new=WarmupClock(...))`` - a stand-in that
lives only inside that leg's ``with`` block, hands out exact scripted floats, and
forwards everything else to the real module.  Because every scripted value is
exact (``1000.0``, ``1025.0``, ``1025.001``, ``1017.5``) the shipped subtraction
is bit-exact, which is what lets the ``>``/``>=`` boundary at L477 and L500 sit ON
the threshold rather than near it, and makes ``Subtract -> Add`` on L576 read
``2027.75`` where shipped reads ``0.25``.  The one real-clock leg measures an
ELAPSED interval (never an absolute) and only bounds it, so no uptime value is
ever asserted.

Occurrence twins
================
No key in this group has a before-text occurring elsewhere in this blob, so no leg
must reach outside it: the four L528-532 keywords appear at their shipped literal
values only inside ``model_readiness_probe`` (the ``detect_objects`` forward at
L1129-1135 passes caller variables, not these literals), and the three
``set_model_warmth_state`` call sites differ in their second argument.  The two
neighbouring EQUIVALENT groups - ``eq-readiness-probe-image-bytes`` (6 keys on
L521-525 and the ``m21`` lowercase of L537) and ``eq-lastexception-falsy-init`` (1
key on L632) - carry no key here and are not exercised.

Honest gaps (stated, not papered over)
======================================
All 73 keys were killed on the first prove run (``replay_dc04.json``: 73/73, 73
occurrences, every one red with a NAMED failing test, 0 lookup errors, 0
multi-candidate occurrences - so no occurrence-twin leg was needed at all).  Three
pairs/triples are nonetheless covered by a SHARED leg rather than one each, because
they are indistinguishable at every observable boundary this code offers:

* ``probe m22`` (``image_data = None``, L525) and ``m23`` (``image_data=None``,
  L528) produce the SAME captured keyword map, and ``m27`` (``image_data=``
  dropped) is distinguishable from them only by the missing key.  Likewise
  ``m26`` (``image_path=None``) vs ``m30`` (``image_path=`` dropped).  The three
  legs ``test_the_readiness_probe_sends_exactly_the_four_shipped_keyword_arguments``,
  ``test_the_probe_image_is_the_shipped_32x32_black_jpeg`` and
  ``test_the_probe_builds_a_fresh_payload_on_every_call`` together name all of
  them; none of the four keys has a leg of its own.  (Probed: an ``AsyncMock``
  records a dropped keyword as an ABSENT key and does NOT raise, so the whole-map
  and ``list(kwargs)`` pins - not an exception - are what separate them.)
* ``warmup m39`` (``extra=None``) and ``m41`` (``extra=`` dropped) are visible
  only as the ABSENCE of ``duration``/``was_cold`` from the record: ``logging``
  keeps ``extra`` in its own signature slot, so the mutant's payload never reaches
  the record (probed).  ``BASELINE_ATTRS`` strips logging's own fields including
  that slot, which is exactly why the legs assert the two shipped keys are PRESENT
  rather than merely "not renamed".
* ``warmup m2`` (``was_cold = None``, L566) is invisible on the FAILURE arm: the
  shipped record interpolates the value, so ``None`` prints as ``None`` under
  either key name.  It is named only on the SUCCESS arm, where shipped puts
  literal ``True`` in ``extra["was_cold"]`` - leg
  ``test_the_completion_record_names_the_duration_and_the_cold_start``.

Test -> mutant-key map (``mN`` == ``<fn>__mutmut_N``)
====================================================
Transcribed from ``replay_dc04.json``, which records the failing tests the harness
actually named for each key - not from intent.  Legs are abbreviated below without
their ``test_`` prefix.  22 of the 26 legs name at least one key; the four that
name none are stated as controls at the end.

Warmth (9 keys)
* ``is_cold m5`` (``> -> >=``, L477) ->
  ``a_recently_used_client_is_warm_until_the_threshold_passes`` (exactly the
  threshold -> ``False``, one millisecond past -> ``True``).
* ``get_warmth_state m1`` (``is None -> is not None``, L493) -> five legs:
  ``the_warmth_snapshot_of_an_unused_model_is_cold_with_no_age`` (the shipped
  subtraction receives ``None``), ``..._names_a_recently_used_model_warm``,
  ``..._names_a_stale_model_cold_with_its_age``,
  ``..._reports_the_real_elapsed_age_of_the_model`` and
  ``a_failed_probe_leaves_the_model_cold_and_reports_failure`` (whose post-warmup
  snapshot call is where the flipped guard surfaces).
* ``m3`` (``Subtract -> Add``, L499) -> the warm, stale and real-age legs (the age
  becomes a nonsense sum, so the state reads ``"cold"``).
* ``m5`` (``>=``, L500) -> ``..._names_a_recently_used_model_warm`` only (the
  boundary is placed ON the threshold, so only the warm leg can see it).
* ``m4`` (``is_cold = None``), ``m8`` (``and False``), ``m10``/``m11`` (``"cold"``
  XX/upper) -> ``..._names_a_stale_model_cold_with_its_age`` only.
* ``m9`` (``or True``) -> the warm leg and the real-age leg (always-cold cannot
  survive a "warm" pin).

Readiness probe (19 keys)
* ``m10``/``m11`` (33-px width / height), ``m13`` (green pixel) ->
  ``the_probe_image_is_the_shipped_32x32_black_jpeg`` (PIL decode: size, extrema,
  whole-bytes equality, the three sibling triples),
  ``the_probe_builds_a_fresh_payload_on_every_call`` and
  ``the_probe_recovers_from_a_failure_and_still_succeeds``.
* ``m22`` (L525 payload ``None``), ``m23``/``m27`` (L528 ``image_data`` None /
  dropped) -> those three legs plus
  ``the_readiness_probe_sends_exactly_the_four_shipped_keyword_arguments``.
* ``m24`` (``image_name=None``), ``m31``/``m32`` (``"warmup_test.jpg"`` XX/upper),
  ``m35``/``m36`` (``"/dev/null"`` XX/upper) ->
  ``the_readiness_probe_sends_exactly_the_four_shipped_keyword_arguments`` only.
* ``m28`` (``image_name=`` dropped), ``m29`` (``camera_id=``) and ``m30``
  (``image_path=``) -> all three reddens
  ``the_readiness_probe_sends_exactly_the_four_shipped_keyword_arguments``,
  ``the_probe_succeeds_for_any_response_the_service_returns`` and
  ``the_probe_builds_a_fresh_payload_on_every_call`` (``m29`` also the recovery
  leg).  A dropped keyword does NOT raise at the double - probed: the mock accepts
  it and records three keywords - so what separates these from their ``None``-value
  siblings is the recorded KEY LIST and the whole-map equality, not an exception.
* ``m25``/``m26`` (``camera_id`` / ``image_path`` ``None``) -> the sends-exactly leg
  (and, for ``m25``, the recovery leg's per-call camera pin).
* ``m33``/``m34`` (``"warmup"`` XX/upper) -> the sends-exactly leg and
  ``the_probe_recovers_from_a_failure_and_still_succeeds``.
* ``m38`` (``logger.warning(None)``, L537) ->
  ``an_unavailable_detector_fails_the_probe_with_its_own_warning``.

Warmup (45 keys)
* ``m2`` (``was_cold = None``, L566) -> five legs, of which
  ``the_completion_record_names_the_duration_and_the_cold_start`` is the one that
  names the KEY (shipped puts literal ``True`` in ``extra["was_cold"]`` for a cold
  model; see HONEST GAPS).
* ``m3``/``m4`` (L567 ``= None``/``False``) and ``m60``/``m61`` (L594 ``= None``/
  ``True``) -> the four flag legs: ``a_cold_warmup_publishes_...``,
  ``a_warm_model_warms_up_...``, ``a_failed_probe_...`` and
  ``the_warming_flag_is_set_only_for_the_duration_of_the_probe`` (identity pins:
  ``is True`` DURING the probe, ``is False`` after, read from ``__dict__``).
* ``m5``/``m6``/``m9``-``m12`` (the six L568 warming-call keys) -> those same three
  warmup legs plus ``the_warmth_labels_are_the_shipped_gauge_vocabulary``, where a
  renamed label collapses to ``0`` through the shipped dict.
* ``m13``-``m16`` (the four L571 marker keys) ->
  ``the_starting_marker_precedes_the_request_and_the_warming_gauge``,
  ``the_completion_record_...``, ``a_warm_model_...`` and ``a_failed_probe_...``
  (whose INFO list must be exactly the marker).
* ``m20`` (L576 ``Subtract -> Add``) -> five legs, including the real histogram
  delta in ``the_duration_observation_lands_on_the_real_yolo26_warmup_histogram``.
* ``m21``/``m25``/``m26`` (L577) -> the three warmup legs and that same histogram
  leg (``m21``'s ``None`` model writes a different child).
* ``m27``/``m28``/``m29`` (L582) -> ``a_cold_warmup_publishes_...`` (recorded args)
  and ``the_cold_start_counter_really_increments_for_a_cold_model`` (the live
  counter's delta, which a renamed or ``None``-ed label leaves at zero).
* ``m30``/``m31``/``m34``-``m37`` (the six L583 warm-gauge keys) -> the cold leg,
  the warm leg and the gauge-vocabulary leg.
* ``m38`` (``logger.info(None)``, L585) -> the warm leg,
  ``the_completion_record_...`` and ``the_starting_marker_...``.
* ``m39``/``m41``/``m42``-``m45`` (the six L586 ``extra`` keys) ->
  ``the_completion_record_names_the_duration_and_the_cold_start`` and the warm leg.
* ``m47``/``m48``/``m51``-``m54`` (the six L590 cold-gauge keys) ->
  ``a_failed_probe_leaves_the_model_cold_and_reports_failure`` and the
  gauge-vocabulary leg.
* ``m55``-``m58`` (the four L591 warning keys) -> ``a_failed_probe_...`` only.

Controls that kill nothing (stated so they are not mistaken for killers):
``a_client_that_never_ran_inference_is_cold``,
``the_warming_flag_short_circuits_the_snapshot_to_warming``,
``a_disabled_warmup_reports_success_without_touching_any_wiring`` and
``a_generic_failure_fails_the_probe_with_the_plain_warning``.  They pin shipped
contract that a killing leg could otherwise fall through - the ``None``-time arm of
``is_cold``, the unmutated ``"warming"`` short-circuit, the L562 guard, and the
L539 arm's separation from L536 - and none of the 73 keys has an occurrence there.
"""

from __future__ import annotations

import contextlib
import io
import logging
import re
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

import backend.core.metrics as METRICS
import backend.services.detector_client as M

pytestmark = [pytest.mark.unit]

LOG_NAME = "backend.services.detector_client"

# ---- values INJECTED by this file (never shipped values) --------------------
DETECTOR_URL = "http://detector.invalid:8080"
READ_TIMEOUT = 17.0
CONNECT_TIMEOUT = 7.0
HEALTH_TIMEOUT = 3.0
RETRIES_FROM_SETTINGS = 2
MAX_RETRIES_ARG = 1
CONCURRENT = 7
# L351 stores `settings.ai_cold_start_threshold_seconds` - the value L477 and
# L500 compare against.  It and every scripted reading below are exact binary
# floats, so the boundary legs land ON the threshold rather than near it.
THRESHOLD = 25.0

# The scripted clock's zero.
TICK0 = 1000.0
# ``warmup`` reads the clock at L566 (inside ``is_cold``) and again at L572
# (``start_time``); one scripted value covers both and keeps L572 exact.
TICK_PAST = TICK0 + THRESHOLD + 0.001  # 1025.001 - past the threshold
TICK_WARM = TICK0 + 17.5  # 1017.5 - comfortably inside the threshold
TICK_ON = TICK0 + THRESHOLD  # 1025.0 exactly - the L477/L500 boundary

# L530-532: the shipped literals of the probe request, transcribed.
PROBE_IMAGE_NAME = "warmup_test.jpg"
PROBE_CAMERA_ID = "warmup"
PROBE_IMAGE_PATH = "/dev/null"
# L520: the shipped ``Image.new("RGB", (32, 32), color=(0, 0, 0))`` triple.
PROBE_WH = (32, 32)
PROBE_COLOR = (0, 0, 0)
PROBE_MAGIC = b"\xff\xd8\xff"
# L585: `f"YOLO26 warmup completed in {duration:.2f}s"`.
COMPLETED_SHAPE = re.compile(r"^YOLO26 warmup completed in \d+\.\d{2}s$")
# L537 / L540 are f-strings; only the literal prefix is shippable text and the
# interpolated tail is asserted next to it.
UNAVAILABLE_PREFIX = "YOLO26 readiness probe failed (unavailable): "
GENERIC_PREFIX = "YOLO26 readiness probe failed: "
# L563 / L571 / L591, verbatim.
DISABLED_MSG = "YOLO26 warmup disabled by configuration"
STARTING_MSG = "Starting YOLO26 model warmup..."
FAILED_MSG = "YOLO26 warmup failed - model not ready"
# L568 / L577 / L582 / L583 / L590: the model label and the three gauge labels.
MODEL = "yolo26"
LABEL_WARMING = "warming"
LABEL_WARM = "warm"
LABEL_COLD = "cold"
# metrics.py L3423 - the shipped label->value map ``set_model_warmth_state`` uses.
GAUGE_VALUES = {"cold": 0, "warming": 1, "warm": 2}
# The scripted duration the warmup legs expect: each leg's end reading is
# ``<its tick> + DURATION``, and all three ticks are exact binary values, so the
# shipped subtraction yields exactly 0.25.
DURATION = 0.25


# =============================================================================
# Module clock stand-in (the real time module is never touched)
# =============================================================================


class WarmupClock:
    """``detector_client.time`` for ONE leg (``new=`` form).

    ``monotonic`` hands out ``tick`` until the probe has run and ``tick_end``
    afterwards, so the shipped ``time.monotonic() - start_time`` (L576) is the
    exact difference the leg chose, and the shipped ``>`` at L477/L500 is placed
    on an exact boundary.  The real ``time.monotonic``/``time.perf_counter`` are
    never patched; the shipped module's own ``time`` NAME is replaced for one
    ``with`` block only, and anything besides ``monotonic`` forwards to the real
    module so the stand-in cannot bend a clock these paths do not read.
    """

    def __init__(self, tick: float, tick_end: float) -> None:
        self.tick = tick
        self.tick_end = tick_end
        self.started = False
        self.readings: list[float] = []

    def monotonic(self) -> float:
        value = self.tick_end if self.started else self.tick
        self.readings.append(value)
        return value

    def __getattr__(self, name: str) -> Any:
        return getattr(time, name)


# =============================================================================
# Log observation (only caplog's own handler sees the records)
# =============================================================================


def _baseline_attrs() -> frozenset[str]:
    """Attribute names that are NOT part of a shipped ``extra=`` payload.

    The union of the fields ``logging.LogRecord.__init__`` always sets (which
    includes its ``extra``/``extras`` PARAMETER slots - probed, so a dropped or
    ``None``-ed ``extra=`` never lands here) and the fields this module's
    ``ContextFilter`` injects (the filter is idempotent, so running it once over a
    fresh record adds exactly the injected names).  ``message`` is excluded - the
    formatter sets it.
    """
    probe = logging.LogRecord("baseline.probe", logging.DEBUG, "f", 1, "probe", (), None)
    core = set(probe.__dict__)
    injected = set(M.logger.filter(probe).__dict__) - core
    return frozenset(core | injected | {"message"})


BASELINE_ATTRS = _baseline_attrs()


def shipped_extra(record: logging.LogRecord) -> dict[str, Any]:
    """The shipped ``extra=`` payload, as the record shows it.

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


def texts(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    return [r.msg for r in at(caplog, level)]


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


def none_at(caplog: pytest.LogCaptureFixture, level: int) -> None:
    recs = at(caplog, level)
    assert recs == [], (
        f"unexpected {logging.getLevelName(level)} records: {[(r.levelno, r.msg) for r in recs]}"
    )


# =============================================================================
# JPEG helpers - the shipped L520-525 encoding, transcribed
# =============================================================================


def encode(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    """The shipped ``Image.new(...)`` + ``save(format="JPEG")`` pair, re-run here."""
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=color).save(buffer, format="JPEG")
    return buffer.getvalue()


def decode(data: bytes) -> tuple[Any, Any, Any]:
    """Decode captured probe bytes: ``(size, mode, extrema)`` of the real image."""
    image = Image.open(io.BytesIO(data))
    image.load()
    return image.size, image.mode, image.getextrema()


# =============================================================================
# Settings + client construction (the shipped suite's idiom)
# =============================================================================


@pytest.fixture
def settings() -> Any:
    """``get_settings`` pinned to the values these def's read.

    ``ai_cold_start_threshold_seconds`` is fixture-owned (25.0) so the warmth
    boundary legs land exactly on it, and ``detector_max_retries`` differs from
    the ctor argument the ``client`` fixture passes so the ctor arm at L313 is
    visibly the one in effect.
    """
    st = MagicMock()
    st.ai_gateway_url = None
    st.use_ai_gateway = False
    st.yolo26_url = DETECTOR_URL
    st.yolo26_api_key = None
    st.yolo26_read_timeout = READ_TIMEOUT
    st.ai_connect_timeout = CONNECT_TIMEOUT
    st.ai_health_timeout = HEALTH_TIMEOUT
    st.detector_max_retries = RETRIES_FROM_SETTINGS
    st.ai_max_concurrent_inferences = CONCURRENT
    st.detection_confidence_threshold = 0.5
    st.detection_class_thresholds = {}
    st.ai_warmup_enabled = True
    st.ai_cold_start_threshold_seconds = THRESHOLD
    with patch("backend.services.detector_client.get_settings", autospec=True) as factory:
        factory.return_value = st
        yield st


@pytest.fixture
def client(settings: Any) -> Any:
    """A REAL ``DetectorClient``: the shipped ``__init__`` runs, so the four
    warmth attributes stored at L348-351 are production state.  They are read
    through ``__dict__`` everywhere in this file so an inherited or re-bound
    attribute can never stand in for the one the shipped code wrote."""
    instance = M.DetectorClient(max_retries=MAX_RETRIES_ARG)
    assert instance._max_retries == MAX_RETRIES_ARG  # the ctor argument wins (L313)
    assert instance._warmup_enabled is True
    assert instance._cold_start_threshold == THRESHOLD
    assert instance.__dict__["_last_inference_time"] is None
    assert instance.__dict__["_is_warming"] is False
    yield instance


# =============================================================================
# Metrics watchers (the shipped helpers keep running) + the warmup driver
# =============================================================================

# The SHIPPED helpers, captured at import purely so a watcher can forward to
# them.  Nothing is installed anywhere: every patch is scoped to one leg.
REAL_SET_STATE = METRICS.set_model_warmth_state
REAL_OBSERVE = METRICS.observe_model_warmup_duration
REAL_COLD_START = METRICS.record_model_cold_start


class Warmup:
    """One scripted ``warmup()`` of a real client, observed from three sides.

    Each shipped metrics call is watched by an autospec'd spy whose side effect
    records ``(args, kwargs, world)`` and then runs the SHIPPED helper, so the
    real Prometheus registry still moves (two legs read it back) while the
    recorded call stays the exact surface the ``None``-ed / renamed mutants move.
    ``world`` is what the watcher found when it was called - the flag, how many
    observations and gauge writes already existed, and which INFO lines had been
    emitted - which is the only channel that can express the shipped ordering of
    L567 / L568 / L571 / L577 / L582 / L583 / L590.
    """

    def __init__(self, instance: Any, caplog: pytest.LogCaptureFixture) -> None:
        self.client = instance
        self.caplog = caplog
        self.clock: WarmupClock = WarmupClock(TICK0, TICK0)  # run() replaces it
        self.warmth_state: list[Any] = []
        self.warmup_duration: list[Any] = []
        self.cold_start: list[Any] = []
        self.flag_during: list[Any] = []
        self.infos_during: list[Any] = []
        self.durations_during: list[Any] = []
        self.probe: Any = None
        self.result: Any = None

    # --- the world as each watcher found it ----------------------------------
    def _world(self) -> dict[str, Any]:
        return {
            "flag": self.client.__dict__["_is_warming"],
            "durations": len(self.warmup_duration),
            "states": len(self.warmth_state),
            "cold_starts": len(self.cold_start),
            "infos": list(texts(self.caplog, logging.INFO)),
        }

    # --- watchers (record, then run the shipped helper) ---------------------
    def _watch_state(self, model: str, state: str) -> None:
        self.warmth_state.append(((model, state), {}, self._world()))
        REAL_SET_STATE(model, state)

    def _watch_duration(self, model: str, seconds: float) -> None:
        self.warmup_duration.append(((model, seconds), {}, self._world()))
        REAL_OBSERVE(model, seconds)

    def _watch_cold_start(self, model: str) -> None:
        self.cold_start.append(((model,), {}, self._world()))
        REAL_COLD_START(model)

    # --- the probe double ---------------------------------------------------
    def _run_probe(self) -> bool:
        self.flag_during.append(self.client.__dict__["_is_warming"])
        self.infos_during.append(list(texts(self.caplog, logging.INFO)))
        self.durations_during.append(len(self.warmup_duration))
        self.clock.started = True
        return self.result_outcome  # type: ignore[attr-defined]

    # --- drive one warmup ---------------------------------------------------
    def run(self, *, outcome: bool, tick: float) -> bool:
        self.clock = WarmupClock(tick, tick + DURATION)
        self.result_outcome = outcome
        self.probe = AsyncMock(spec=M.DetectorClient.model_readiness_probe)
        self.probe.side_effect = self._run_probe
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(M, "time", new=self.clock))
            stack.enter_context(patch.object(self.client, "model_readiness_probe", new=self.probe))
            stack.enter_context(
                patch.object(
                    METRICS,
                    "set_model_warmth_state",
                    autospec=True,
                    side_effect=self._watch_state,
                )
            )
            stack.enter_context(
                patch.object(
                    METRICS,
                    "observe_model_warmup_duration",
                    autospec=True,
                    side_effect=self._watch_duration,
                )
            )
            stack.enter_context(
                patch.object(
                    METRICS,
                    "record_model_cold_start",
                    autospec=True,
                    side_effect=self._watch_cold_start,
                )
            )
            self.result = asyncio_run(self.client.warmup())
        return self.result

    # --- readable surfaces --------------------------------------------------
    @property
    def states(self) -> list[Any]:
        """Every gauge write's ``(model, label)``, in call order."""
        return [entry[0] for entry in self.warmth_state]

    @property
    def state_labels(self) -> list[Any]:
        return [entry[0][1] for entry in self.warmth_state]


@pytest.fixture
def warmup(client: Any, caplog: pytest.LogCaptureFixture) -> Any:
    """The three-sided observation harness around the shipped ``warmup``."""
    win(caplog)
    return Warmup(client, caplog)


def gauge_value(model: str) -> int:
    """The live ``MODEL_WARMTH_STATE`` child value for ``model``."""
    return int(METRICS.MODEL_WARMTH_STATE.labels(model=model)._value.get())


def warmup_sum(model: str) -> float:
    """The live ``MODEL_WARMUP_DURATION`` running sum for ``model``."""
    return float(METRICS.MODEL_WARMUP_DURATION.labels(model=model)._sum.get())


def cold_starts(model: str) -> float:
    """The live ``MODEL_COLD_START_TOTAL`` value for ``model``."""
    return float(METRICS.MODEL_COLD_START_TOTAL.labels(model=model)._value.get())


def asyncio_run(coro: Any) -> Any:
    """Drive one coroutine to completion (the shipped suite's own idiom)."""
    import asyncio

    return asyncio.run(coro)


# =============================================================================
# L464-477 / L479-504: is_cold() and get_warmth_state()
# =============================================================================


def test_a_client_that_never_ran_inference_is_cold(client: Any) -> None:
    """L474-475: the ``_last_inference_time is None`` arm answers True, unpaid.

    No clock is patched, because this arm returns before L476 - which is also
    what the flipped ``is not None`` mutant at L493 (``get_warmth_state m1``, the
    same keyword one line down in the next def) would have broken here had this
    line been mutated the same way.
    """
    assert client.__dict__["_last_inference_time"] is None
    assert client.is_cold() is True


def test_a_recently_used_client_is_warm_until_the_threshold_passes(client: Any) -> None:
    """L476-477: the shipped comparator is ``>``, so exactly the threshold is WARM.

    ``is_cold m5`` rewrites that line as ``>=``.  Both readings are exact
    (``1025.0 - 1000.0 == 25.0`` against an injected threshold of ``25.0``), so
    the mutant flips the first leg while shipped cannot; one millisecond past the
    threshold the shipped line flips itself, which is what stops an always-False
    or ``<``-shaped variant from passing the other way.
    """
    client.__dict__["_last_inference_time"] = TICK0
    assert client._cold_start_threshold == THRESHOLD

    with patch.object(M, "time", new=WarmupClock(TICK_ON, TICK_ON)):
        assert client.is_cold() is False, (
            f"exactly {THRESHOLD}s since the last inference is not cold - the "
            "shipped comparator is `>`, so `m5`'s `>=` is the only way to fail this"
        )
    with patch.object(M, "time", new=WarmupClock(TICK_PAST, TICK_PAST)):
        assert client.is_cold() is True, "one millisecond past the threshold IS cold"


def test_the_warmth_snapshot_of_an_unused_model_is_cold_with_no_age(client: Any) -> None:
    """L493-497: never-inferred -> ``"cold"`` with a ``None`` age.

    ``get_warmth_state m1`` flips L493 to ``is not None``, so this state falls
    through to L499 where the shipped subtraction receives ``None`` - the leg
    ERRORS on the TypeError, and that error IS the red.
    """
    assert client.__dict__["_last_inference_time"] is None
    state = client.get_warmth_state()

    assert state == {"state": "cold", "last_inference_seconds_ago": None}
    assert state["last_inference_seconds_ago"] is None
    assert state["state"] != "warming"


def test_the_warmth_snapshot_names_a_recently_used_model_warm(client: Any) -> None:
    """L499-503 at exactly the threshold: ``"warm"`` and the exact age.

    Six mutants live in these two shipped lines.  ``m3`` (``Add`` for
    ``Subtract``) turns the age into ``2025.0`` and so the state into ``"cold"``;
    ``m5`` (``>=``) turns the state into ``"cold"`` on its own; ``m8`` (``and
    False``) can never say cold and ``m9`` (``or True``) can never say warm;
    ``m1`` hands back a ``None`` age; and the label renames ``m10``/``m11`` land
    on a state that is not in the shipped vocabulary.  The age is pinned both as
    the exact scripted delta and as a plausible number, so the nonsense sum cannot
    pass a shape check.
    """
    client.__dict__["_last_inference_time"] = TICK0
    clock = WarmupClock(TICK_ON, TICK_ON)
    with patch.object(M, "time", new=clock):
        state = client.get_warmth_state()

    assert clock.readings == [TICK_ON], f"L499 reads the clock exactly once: {clock.readings}"
    assert state == {"state": "warm", "last_inference_seconds_ago": THRESHOLD}
    assert state["state"] == "warm", f"L502 label mutated: {state['state']!r}"
    assert state["last_inference_seconds_ago"] == pytest.approx(THRESHOLD, abs=1e-9)
    assert state["last_inference_seconds_ago"] < 60.0, "L499 must subtract, not add"


def test_the_warmth_snapshot_names_a_stale_model_cold_with_its_age(client: Any) -> None:
    """L500-503 past the threshold: ``"cold"``, and an age that is a positive float.

    ``m4`` (``is_cold = None``) and ``m8`` (``and False``) both make the shipped
    conditional falsy and hand back ``"warm"``; ``m9`` (``or True``) would make
    the WARM leg cold instead, and is caught there.  ``m10``/``m11`` change the
    label itself.  The age must survive as a positive float - that is the only
    difference between this return block and the two above it, so an early-return
    mutant cannot satisfy the state pin and skip this one.
    """
    client.__dict__["_last_inference_time"] = TICK0
    with patch.object(M, "time", new=WarmupClock(TICK_PAST, TICK_PAST)):
        state = client.get_warmth_state()

    assert state["state"] == "cold", f"L502 label mutated: {state['state']!r}"
    assert state["state"] != "warm"
    assert state["state"] in ("cold", "warming", "warm"), "not a shipped state word"
    age = state["last_inference_seconds_ago"]
    assert age is not None, "a stale model reports its age, never None"
    assert isinstance(age, float) and not isinstance(age, bool), f"age is {age!r}"
    assert age > 0.0, f"the shipped delta must be positive: {age!r}"
    assert age == pytest.approx(THRESHOLD + 0.001, abs=1e-9)


def test_the_warming_flag_short_circuits_the_snapshot_to_warming(client: Any) -> None:
    """L487-491: while the flag is set the snapshot is ``warming`` with ``None`` age.

    A control leg - no key sits on those two lines - but it is what stops the
    legs above from being satisfied by an accidental always-``"warming"``, and it
    pins that the flag BEATS a perfectly good stored timestamp without spending a
    clock read.
    """
    client.__dict__["_last_inference_time"] = TICK0
    client.__dict__["_is_warming"] = True
    clock = WarmupClock(TICK_ON, TICK_ON)
    with patch.object(M, "time", new=clock):
        state = client.get_warmth_state()

    assert state == {"state": "warming", "last_inference_seconds_ago": None}
    assert clock.readings == [], "the warming arm returns before any clock read"


def test_the_warmth_snapshot_reports_the_real_elapsed_age_of_the_model(client: Any) -> None:
    """Real-clock control: the reported age IS the interval the leg measured.

    Nothing is patched but the module's own ``time`` name, and the value it is
    handed is a real reading taken between two real readings.  ``m3`` lands on a
    nonsense sum here and the label mutants on ``"cold"`` immediately, so both
    reddening at once is expected; what this leg owns on its own is that the age
    equals an independently measured elapsed interval, never an absolute uptime
    value.
    """
    before = time.monotonic()
    client.__dict__["_last_inference_time"] = before
    clock = WarmupClock(time.monotonic(), 0.0)
    with patch.object(M, "time", new=clock):
        state = client.get_warmth_state()

    age = state["last_inference_seconds_ago"]
    measured = clock.readings[0] - before
    assert isinstance(age, float) and not isinstance(age, bool)
    assert 0.0 <= age <= 1.0, f"a snapshot taken at once cannot read {age}s old"
    assert age == pytest.approx(measured, abs=1e-6), "the age is not the measured interval"
    assert state["state"] == "warm", f"{measured}s against a {THRESHOLD}s threshold"


# =============================================================================
# L506-541: model_readiness_probe
# =============================================================================


@pytest.fixture
def sender(client: Any) -> Any:
    """``client._send_detection_request`` replaced by a recording ``AsyncMock``.

    The shipped call at L528-533 is an attribute lookup, so the double sees it;
    ``spec=`` keeps the shipped signature, so the record is
    ``call(image_data=..., image_name=..., camera_id=..., image_path=...)`` -
    exactly the 16-key surface of L525/L528-532, with a dropped keyword showing
    as an ABSENT key rather than a defaulted one.
    """
    double = AsyncMock(spec=M.DetectorClient._send_detection_request)
    double.return_value = {"detections": []}
    with patch.object(client, "_send_detection_request", new=double):
        yield double


def test_the_readiness_probe_sends_exactly_the_four_shipped_keyword_arguments(
    client: Any, sender: Any
) -> None:
    """L528-533: four keywords, whole map, shipped order, real JPEG payload.

    All sixteen L525/L528-532 keys move this map: the four ``arg->None`` and four
    ``arg_drop`` pairs - an absent key is NOT a ``None`` value, which is why the
    whole-map equality is paired with an explicit ``is not None`` check and with
    the ordering leg below - and the six literal renames.  ``list(kwargs)`` pins
    the shipped order, which no permutation can slip past.
    """
    assert asyncio_run(client.model_readiness_probe()) is True

    assert sender.call_count == 1
    call = sender.call_args
    assert call.args == (), f"the shipped call is all-keyword: {call.args!r}"
    kwargs = call.kwargs
    assert list(kwargs) == ["image_data", "image_name", "camera_id", "image_path"]
    assert kwargs == {
        "image_data": kwargs["image_data"],
        "image_name": PROBE_IMAGE_NAME,
        "camera_id": PROBE_CAMERA_ID,
        "image_path": PROBE_IMAGE_PATH,
    }
    assert kwargs["image_name"] == PROBE_IMAGE_NAME, (
        f"L530 literal mutated: {kwargs['image_name']!r}"
    )
    assert kwargs["camera_id"] == PROBE_CAMERA_ID, f"L531 literal mutated: {kwargs['camera_id']!r}"
    assert kwargs["image_path"] == PROBE_IMAGE_PATH, (
        f"L532 literal mutated: {kwargs['image_path']!r}"
    )
    assert kwargs["image_data"] is not None, "the shipped payload cannot be None"
    assert kwargs["image_name"] is not None
    assert kwargs["camera_id"] is not None
    assert kwargs["image_path"] is not None
    assert PROBE_IMAGE_NAME == "warmup_test.jpg"


def test_the_probe_image_is_the_shipped_32x32_black_jpeg(client: Any, sender: Any) -> None:
    """L520-525: the captured bytes decode to a 32x32 RGB image of pure black.

    ``m10``/``m11`` change one output dimension (caught by ``size`` and by whole-
    bytes equality), ``m13`` sets the green channel (caught by the extrema), and
    ``m22``/``m23``/``m27`` take the payload away entirely - ``None`` cannot be
    decoded, so this leg is their red too.  Re-encoding the shipped triple
    reproduces the captured bytes EXACTLY (probed), and each of the three sibling
    triples provably differs from it, so those four pins together name the shipped
    dimensions and colour and nothing else.
    """
    assert asyncio_run(client.model_readiness_probe()) is True

    data = sender.call_args.kwargs["image_data"]
    assert isinstance(data, bytes), f"the probe payload is {type(data)} - nothing to decode"
    assert not isinstance(data, bool)
    assert data.startswith(PROBE_MAGIC), f"not a JPEG stream: {data[:4]!r}"
    assert len(data) > 100, f"a 32x32 JPEG is hundreds of bytes: {len(data)}"

    size, mode, extrema = decode(data)
    assert mode == "RGB", f"the shipped image mode is RGB: {mode!r}"
    assert size == PROBE_WH, f"L520 dimension mutated: {size} != {PROBE_WH}"
    assert size[0] == 32 and size[1] == 32
    assert extrema == ((0, 0), (0, 0), (0, 0)), f"L520 colour mutated: {extrema}"

    assert data == encode(32, 32, (0, 0, 0)), "the payload is not the shipped black 32x32"
    assert encode(33, 32, (0, 0, 0)) != data, "m10's (33, 32) is not the shipped image"
    assert encode(32, 33, (0, 0, 0)) != data, "m11's (32, 33) is not the shipped image"
    assert encode(32, 32, (0, 1, 0)) != data, "m13's green pixel is not the shipped colour"


def test_the_probe_builds_a_fresh_payload_on_every_call(client: Any, sender: Any) -> None:
    """L521-525 run inside the ``try``: every call re-encodes and sends the image.

    The image is built per call rather than hoisted or cached, and the bytes that
    reach L528 are exactly what L525's ``getvalue()`` returned - the full,
    decodable JPEG, twice.  This is also where the payload-vs-nothing split behind
    ``m22``/``m23``/``m27`` shows up as a second, independent red: a payload that
    is ``None`` cannot be decoded twice.  (The three of them that produce the same
    captured keyword map are value-equivalent at this boundary - see HONEST GAPS.)
    """
    assert asyncio_run(client.model_readiness_probe()) is True
    assert asyncio_run(client.model_readiness_probe()) is True

    assert sender.call_count == 2
    payloads = [c.kwargs["image_data"] for c in sender.call_args_list]
    for payload in payloads:
        assert isinstance(payload, bytes), f"payload is {type(payload)}"
        assert payload.startswith(PROBE_MAGIC), "each call sends a real JPEG stream"
        assert decode(payload)[:2] == ((32, 32), "RGB")
    assert payloads[0] == payloads[1] == encode(32, 32, (0, 0, 0))
    assert [list(c.kwargs) for c in sender.call_args_list] == [
        ["image_data", "image_name", "camera_id", "image_path"],
        ["image_data", "image_name", "camera_id", "image_path"],
    ]


@pytest.mark.parametrize("payload", [{"detections": []}, {"detections": [{"class": "person"}]}])
def test_the_probe_succeeds_for_any_response_the_service_returns(
    client: Any, sender: Any, payload: dict[str, Any]
) -> None:
    """L534-535: the response is DISCARDED - any completion at all means ready.

    The empty-detections payload is the leg that proves nothing is read out of the
    response (the shipped comment says so); a mutant that returned the payload, or
    its truthiness, instead of ``True`` fails here.  The populated payload is the
    same arm with content, and both pin the awaited result down.
    """
    sender.return_value = payload
    assert asyncio_run(client.model_readiness_probe()) is True
    assert sender.call_count == 1
    assert list(sender.call_args.kwargs) == [
        "image_data",
        "image_name",
        "camera_id",
        "image_path",
    ]
    assert set(payload) == {"detections"}


def test_an_unavailable_detector_fails_the_probe_with_its_own_warning(
    client: Any, sender: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L536-538: ``DetectorUnavailableError`` -> ``False`` + the qualified warning.

    ``m38`` replaces the warning's argument with ``None``, so the record's raw
    ``msg`` becomes ``None`` and this leg reddens on the text pin.  The
    parenthesised ``(unavailable)`` form is what tells the two arms apart, so both
    texts are pinned against each other and no other level may fire.
    """
    sender.side_effect = M.DetectorUnavailableError("x")
    win(caplog)

    assert asyncio_run(client.model_readiness_probe()) is False

    record = one(caplog, logging.WARNING, UNAVAILABLE_PREFIX + "x")
    assert record.msg.startswith(UNAVAILABLE_PREFIX)
    assert record.msg != GENERIC_PREFIX + "x", "the two probe arms must not share a text"
    assert "(unavailable)" in record.msg
    assert record.levelno == logging.WARNING
    none_at(caplog, logging.ERROR)
    none_at(caplog, logging.INFO)
    assert sender.call_count == 1


def test_a_generic_failure_fails_the_probe_with_the_plain_warning(
    client: Any, sender: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L539-541: any other exception -> ``False`` + the plain warning, no suffix.

    The shipped text is an f-string interpolating the error, so the tail is the
    message the leg raised.  The exception must not escape, and the L536 arm's
    ``(unavailable)`` text must not appear - which is what keeps this leg from
    passing if the two ``except`` arms were swapped or merged.
    """
    sender.side_effect = RuntimeError("kaboom")
    win(caplog)

    assert asyncio_run(client.model_readiness_probe()) is False

    record = one(caplog, logging.WARNING, GENERIC_PREFIX + "kaboom")
    assert "(unavailable)" not in record.msg
    assert record.msg.endswith("kaboom")
    none_at(caplog, logging.ERROR)
    none_at(caplog, logging.INFO)


def test_the_probe_recovers_from_a_failure_and_still_succeeds(
    client: Any, sender: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """Sequencing control: two calls, exactly one warning, and the second is ``True``.

    Nothing in L517-535 is stateful, so a single-call leg could accept a mutant
    that latched a flag or returned ``False`` unconditionally.  This leg cannot:
    it demands one failure, one success, one record, and the same shipped
    keywords both times.
    """
    sender.side_effect = [RuntimeError("transient"), {"detections": [{"class": "car"}]}]
    win(caplog)

    assert asyncio_run(client.model_readiness_probe()) is False
    assert asyncio_run(client.model_readiness_probe()) is True

    assert sender.call_count == 2
    assert texts(caplog, logging.WARNING) == [GENERIC_PREFIX + "transient"]
    assert [c.kwargs["camera_id"] for c in sender.call_args_list] == [
        PROBE_CAMERA_ID,
        PROBE_CAMERA_ID,
    ]
    assert next(iter(sender.call_args_list)).kwargs["image_data"] == encode(32, 32, (0, 0, 0))


# =============================================================================
# L543-594: warmup
# =============================================================================


def _boom(*_args: Any, **_kwargs: Any) -> None:
    """A probe double that must never be reached - reaching it IS the failure."""
    raise AssertionError("the readiness probe must not run while warmup is disabled")


def test_a_disabled_warmup_reports_success_without_touching_any_wiring(
    settings: Any, client: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L562-564: the guard returns ``True`` with one DEBUG line and NOTHING else.

    The guard's own value is injected False before construction, so L350 stores it
    and L562 reads it.  The probe double raises if called, all three metrics
    watchers must stay empty, the flag must never move, and no INFO/WARNING/ERROR
    may appear - so a mutant that fell past the guard cannot pass even though no
    clock is patched here.
    """
    settings.ai_warmup_enabled = False
    instance = M.DetectorClient(max_retries=MAX_RETRIES_ARG)
    assert instance._warmup_enabled is False
    win(caplog)
    calls: list[Any] = []

    with (
        patch.object(METRICS, "set_model_warmth_state", autospec=True, side_effect=calls.append),
        patch.object(
            METRICS, "observe_model_warmup_duration", autospec=True, side_effect=calls.append
        ),
        patch.object(METRICS, "record_model_cold_start", autospec=True, side_effect=calls.append),
        patch.object(instance, "model_readiness_probe", new=AsyncMock(side_effect=_boom)),
    ):
        assert asyncio_run(instance.warmup()) is True

    assert calls == [], f"the disabled guard must return before L566: {calls!r}"
    one(caplog, logging.DEBUG, DISABLED_MSG)
    none_at(caplog, logging.INFO)
    none_at(caplog, logging.WARNING)
    none_at(caplog, logging.ERROR)
    assert instance.__dict__["_is_warming"] is False
    assert instance.__dict__["_last_inference_time"] is None


def test_a_cold_warmup_publishes_warming_then_warm_and_records_the_cold_start(
    client: Any, warmup: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L566-588 on a cold client: ``warming`` -> ``warm``, one cold start, ``True``.

    This is the widest leg and the surface it reads is exactly what 22 keys move:
    the two gauge writes (L568 six keys, L583 six keys), the duration observation
    (L577 three), the cold-start counter (L582 three), the flag (L567/L594) and
    the return.  Every expectation is derived from the scripted clock, so
    ``Subtract -> Add`` on L576 reads ``2027.75`` where shipped reads ``0.25``, and
    the interleaved ``world`` records are what pin the shipped ORDER of the block
    rather than merely its set of calls.
    """
    assert warmup.run(outcome=True, tick=TICK_PAST) is True

    # L567 -> probe -> L594, read from the instance's own __dict__, by IDENTITY.
    assert warmup.flag_during == [True], (
        f"L567 must set the flag before the probe: {warmup.flag_during}"
    )
    assert warmup.flag_during[0] is True, "L567 `-> None` / `-> False` mutants"
    assert client.__dict__["_is_warming"] is False, "L594 (finally) must clear the flag"
    assert client.__dict__["_is_warming"] is not None, "L594 `assign:->None` mutant"

    # L566 -> L581/L582: the model was cold, so the counter fires once.
    assert [e[0] for e in warmup.cold_start] == [(MODEL,)], (
        f"a cold model records exactly one cold start: {[e[0] for e in warmup.cold_start]}"
    )

    # L568 / L583: two gauge writes, shipped order, shipped label.
    assert warmup.states == [(MODEL, LABEL_WARMING), (MODEL, LABEL_WARM)], (
        f"the warmth gauge sequence is mutated: {warmup.states!r}"
    )
    assert warmup.state_labels == ["warming", "warm"]
    assert warmup.warmth_state[0][1] == {}, "both gauge calls are positional"
    assert warmup.warmth_state[1][1] == {}

    # L570-577: the observation precedes the final state write.
    assert len(warmup.warmup_duration) == 1
    (args, kwargs, world) = warmup.warmup_duration[0]
    assert args == (MODEL, DURATION), f"L576/L577 mutated: {args!r}"
    assert args[1] == pytest.approx(DURATION, abs=1e-9)
    assert args[1] < 1.0, f"mutated duration: {args[1]}"
    assert kwargs == {}
    assert warmup.durations_during == [0], "L577 runs after the probe, not before"

    # L580: the inference is tracked with the clock value the leg scripted.
    assert client.__dict__["_last_inference_time"] == TICK_PAST + DURATION

    # The shipped ordering inside the success arm: L582 between L577 and L583.
    final = warmup.warmth_state[1][2]
    assert (final["durations"], final["cold_starts"], final["flag"]) == (1, 1, True), (
        f"L577 -> L582 -> L583 order broken, and the flag must still be set: {final}"
    )
    opening = warmup.warmth_state[0][2]
    assert (opening["durations"], opening["cold_starts"], opening["flag"]) == (0, 0, True)

    none_at(caplog, logging.WARNING)
    none_at(caplog, logging.ERROR)


def test_the_duration_observation_carries_the_scripted_duration(
    client: Any, warmup: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L572/L576: exactly the reads the shipped block makes, and their difference.

    A never-inferred client short-circuits L474, so it spends three clock reads -
    L572 ``start_time``, L576, then L580 in ``_track_inference``.  A client with a
    stored timestamp spends four, because L476 inside ``is_cold`` reads first.  The
    recorded duration is the difference between the first two distinct readings in
    both shapes, which is exactly ``DURATION``; ``m20`` (``Subtract -> Add``) reads
    ``2050.252`` here, and ``m4`` of ``get_warmth_state``-style ``-> None`` variants
    would leave nothing to compare.
    """
    assert warmup.run(outcome=True, tick=TICK_PAST) is True

    assert warmup.clock.readings == [TICK_PAST, TICK_PAST + DURATION, TICK_PAST + DURATION], (
        f"L572, L576, L580 - three reads for a never-inferred client: {warmup.clock.readings}"
    )
    args = warmup.warmup_duration[0][0]
    assert args[1] == warmup.clock.readings[-1] - warmup.clock.readings[0]
    assert args[1] == pytest.approx(DURATION, abs=1e-9)
    assert args[1] < 1.0, f"mutated duration: {args[1]}"
    assert client.__dict__["_last_inference_time"] == warmup.clock.readings[-1], (
        "L580 tracks the inference with the same clock the duration came from"
    )

    # The four-read shape: L476 inside is_cold is spent only when a time is stored.
    client.__dict__["_last_inference_time"] = TICK_WARM
    second = Warmup(client, caplog)
    assert second.run(outcome=True, tick=TICK_WARM) is True
    assert second.clock.readings == [
        TICK_WARM,
        TICK_WARM,
        TICK_WARM + DURATION,
        TICK_WARM + DURATION,
    ], f"L476 is spent once the client HAS a stored time: {second.clock.readings}"
    assert second.warmup_duration[0][0][1] == pytest.approx(DURATION, abs=1e-9)


def test_the_completion_record_names_the_duration_and_the_cold_start(
    client: Any, warmup: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L584-587: one INFO, shipped text shape, shipped two-key ``extra`` payload.

    Seven keys sit on these four lines.  ``m38`` (``logger.info(None)``) removes
    the text; ``m39``/``m41`` take the ``extra`` payload away, which logging keeps
    in its own signature slot - so what this leg sees is that the two shipped keys
    are GONE, and it asserts their presence, not merely the absence of a rename;
    ``m42``/``m43``/``m44``/``m45`` rename a key, which shows as an unexpected key
    next to a missing one.  This leg is also the ONLY place ``m2`` (``was_cold =
    None``) is named: shipped puts literal ``True`` in that slot for a cold model.
    """
    assert warmup.run(outcome=True, tick=TICK_PAST) is True

    # Two INFO lines ship on this path (L571 then L584), so the completion record
    # is addressed by position and its text pinned whole, not by a count.
    assert texts(caplog, logging.INFO) == [
        STARTING_MSG,
        f"YOLO26 warmup completed in {warmup.warmup_duration[0][0][1]:.2f}s",
    ]
    duration = warmup.warmup_duration[0][0][1]
    info = at(caplog, logging.INFO)[-1]
    assert COMPLETED_SHAPE.match(info.msg), f"L585 text mutated: {info.msg!r}"
    assert info.msg.endswith(".25s"), "the shipped format is `:.2f`, not raw or `:.1f`"
    assert info.levelno == logging.INFO
    assert info.msg != STARTING_MSG

    extra = shipped_extra(info)
    assert sorted(extra) == ["duration", "was_cold"], f"L586 extra mutated: {extra!r}"
    assert "duration" in extra and "was_cold" in extra, f"extra= payload lost: {extra!r}"
    assert extra["duration"] == duration
    assert extra["was_cold"] is True, f"L566/L586 was_cold: {extra!r}"
    assert isinstance(extra["duration"], float) and extra["duration"] >= 0.0
    assert shipped_extra(at(caplog, logging.INFO)[0]) == {}, "L571 logs bare"


def test_a_warm_model_warms_up_without_recording_a_cold_start(
    client: Any, warmup: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L581 else-arm: a model used 17.5 s ago reaches warm with NO cold start.

    The mirror of the cold leg, and the only place the shipped counter's ABSENCE is
    pinned - so a mutant that hoisted L582 out of the ``if`` reddens here.  ``m61``
    (L594 ``_is_warming = True``) is caught twice over: by the final identity pin
    and because a flag stuck at True makes the snapshot read ``"warming"``.
    ``m2`` prints ``False`` -> ``None`` -> falsy identically here, which is exactly
    why the cold leg is where it is named.
    """
    client.__dict__["_last_inference_time"] = TICK_WARM
    assert TICK_WARM - TICK0 == 17.5 < THRESHOLD

    assert warmup.run(outcome=True, tick=TICK_WARM) is True

    assert warmup.cold_start == [], (
        f"a warm model records no cold start: {[e[0] for e in warmup.cold_start]}"
    )
    assert warmup.states == [(MODEL, LABEL_WARMING), (MODEL, LABEL_WARM)]
    assert warmup.warmup_duration[0][0] == (MODEL, DURATION)
    assert warmup.flag_during == [True]
    assert client.__dict__["_is_warming"] is False
    assert client.get_warmth_state()["state"] != "warming", (
        "an unstuck flag is the only way this leaves the warm window"
    )

    duration = warmup.warmup_duration[0][0][1]
    assert texts(caplog, logging.INFO) == [
        STARTING_MSG,
        f"YOLO26 warmup completed in {duration:.2f}s",
    ]
    info = at(caplog, logging.INFO)[-1]
    assert COMPLETED_SHAPE.match(info.msg), f"L585 text mutated: {info.msg!r}"
    assert shipped_extra(info) == {"duration": duration, "was_cold": False}
    none_at(caplog, logging.WARNING)


def test_a_failed_probe_leaves_the_model_cold_and_reports_failure(
    client: Any, warmup: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L589-594: ``False``, the cold gauge, one WARNING, no tracking, no completion.

    Twelve keys land here: the six on the L590 cold-gauge call, the four on the
    L591 warning, and the two on the L594 clear.  The duration observation at L577
    runs BEFORE the outcome branch, so it must still have happened - which is what
    separates a mutant that skipped the branch from one that skipped the block.
    The ABSENCE of the L584 completion INFO is also pinned here, which is the
    success arm's ``m38``/``m41``/``m42``-``m45`` legs seen from the other side.
    """
    assert warmup.run(outcome=False, tick=TICK_PAST) is False

    assert warmup.flag_during == [True] and warmup.flag_during[0] is True
    assert client.__dict__["_is_warming"] is False, "L594 `-> None` / `-> True` mutants"
    assert client.__dict__["_is_warming"] is not None
    assert client.__dict__["_last_inference_time"] is None, (
        "a failed warmup must not record an inference (L580 is inside the else-arm)"
    )
    assert client.get_warmth_state()["state"] == "cold"

    assert warmup.states == [(MODEL, LABEL_WARMING), (MODEL, LABEL_COLD)], (
        f"the failed warmup must publish `cold`: {warmup.states!r}"
    )
    assert warmup.state_labels == ["warming", "cold"]
    assert len(warmup.warmup_duration) == 1, "L577 runs before the outcome branch"
    assert warmup.warmup_duration[0][0] == (MODEL, DURATION)
    assert warmup.cold_start == [], "a failed warmup records no cold start"

    one(caplog, logging.WARNING, FAILED_MSG)
    none_at(caplog, logging.ERROR)
    assert texts(caplog, logging.INFO) == [STARTING_MSG], (
        f"a failed warmup logs no completion record: {texts(caplog, logging.INFO)}"
    )
    final = warmup.warmth_state[1][2]
    assert (final["durations"], final["cold_starts"]) == (1, 0)


def test_the_starting_marker_precedes_the_request_and_the_warming_gauge(
    client: Any, warmup: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L568-571: the gauge write happens first, then the INFO marker, then the probe.

    ``m13``-``m16`` blank or case-shift the marker, which the record pin catches (a
    ``None`` argument leaves no usable text at all, and the XX/upper/lower variants
    change it).  The marker's position relative to the first gauge write and to the
    probe is read from the world the watcher and the probe double captured - the
    shipped block has no other ordering channel - and ``extra`` must stay empty,
    since L571 logs bare.
    """
    assert warmup.run(outcome=True, tick=TICK_PAST) is True

    opening = warmup.warmth_state[0][2]
    assert opening["infos"] == [], "L568 writes the gauge BEFORE the L571 marker is emitted"
    assert warmup.infos_during == [[STARTING_MSG]], (
        f"the marker must be emitted before the probe runs: {warmup.infos_during!r}"
    )
    assert texts(caplog, logging.INFO) == [
        STARTING_MSG,
        f"YOLO26 warmup completed in {warmup.warmup_duration[0][0][1]:.2f}s",
    ]
    assert shipped_extra(at(caplog, logging.INFO)[0]) == {}, "L571 logs bare - no extra payload"
    assert at(caplog, logging.INFO)[0].msg == "Starting YOLO26 model warmup..."
    assert warmup.result is True


def test_the_warming_flag_is_set_only_for_the_duration_of_the_probe(
    client: Any, warmup: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """L567 / L594 across BOTH arms: the flag is True exactly while the probe runs.

    Every one of the four flag mutants (L567 ``-> None`` / ``-> False``, L594
    ``-> None`` / ``-> True``) breaks at least one identity pin here, and the
    ``world`` each watcher saw is what proves the flag was ALREADY set when L568
    ran and still set when L577/L582/L583 ran - i.e. that the ``finally`` is the
    only thing that clears it.
    """
    assert warmup.run(outcome=True, tick=TICK_PAST) is True
    assert warmup.flag_during == [True]
    assert client.__dict__["_is_warming"] is False

    assert all(entry[2]["flag"] is True for entry in warmup.warmth_state), (
        f"the gauge writes happen inside the warm window: "
        f"{[e[2]['flag'] for e in warmup.warmth_state]}"
    )
    assert warmup.warmup_duration[0][2]["flag"] is True
    assert warmup.cold_start[0][2]["flag"] is True

    # And on the failure arm, where the finally is the ONLY exit left.
    failed = Warmup(client, caplog)
    assert failed.run(outcome=False, tick=TICK_PAST) is False
    assert failed.flag_during == [True]
    assert client.__dict__["_is_warming"] is False
    assert client.get_warmth_state()["state"] != "warming"


def test_the_warmth_labels_are_the_shipped_gauge_vocabulary(
    client: Any, warmup: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """Second surface: the shipped gauge really moved, for both arms.

    ``set_model_warmth_state`` maps its label through the shipped dict
    ``{"cold": 0, "warming": 1, "warm": 2}`` (``metrics.py`` L3423) with a
    ``.get(state, 0)`` fallback, so every renamed label - ``m11``/``m12``'s
    ``warming``, ``m36``/``m37``'s ``warm``, ``m53``/``m54``'s ``cold`` -
    collapses to ``0``.  Reading the LIVE child after each run therefore names the
    labels independently of the recorded args: success must leave ``2`` and the
    failure that follows must leave ``0``, so neither a mislabelled success nor a
    mislabelled failure can pass.  The registry is process-wide and the shipped
    call site names the model from the shipped literal, so the leg reads the
    shipped child and asserts transitions rather than absolute state.
    """
    assert warmup.run(outcome=True, tick=TICK_PAST) is True
    assert warmup.states == [(MODEL, LABEL_WARMING), (MODEL, LABEL_WARM)]
    assert gauge_value(MODEL) == GAUGE_VALUES["warm"] == 2, (
        "the live gauge must read warm after a successful warmup - a renamed label silently reads 0"
    )
    assert gauge_value(MODEL) != GAUGE_VALUES["warming"]

    failed = Warmup(client, caplog)
    assert failed.run(outcome=False, tick=TICK_PAST) is False
    assert failed.state_labels == ["warming", "cold"]
    assert gauge_value(MODEL) == GAUGE_VALUES["cold"] == 0, (
        f"L590's label is not reaching the shipped gauge: {gauge_value(MODEL)}"
    )
    # The two arms really did take different labels at the same shipped call site.
    assert warmup.states[1] == (MODEL, "warm") and failed.states[1] == (MODEL, "cold")
    assert warmup.states[1] != failed.states[1]


def test_the_duration_observation_lands_on_the_real_yolo26_warmup_histogram(
    client: Any, warmup: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """Second surface for L577: the shipped histogram really took the observation.

    The watchers forward to the shipped helpers, so ``MODEL_WARMUP_DURATION`` is
    live and process-wide; this leg measures a DELTA on the shipped child rather
    than an absolute (other legs in this process write the same child, and the
    shipped call site names the model from the shipped literal, so the child is
    shared and not resettable).  ``m20`` makes the delta 2027.75 and ``m21`` moves
    it to a different child entirely - both break the exact delta.
    """
    before_sum = warmup_sum(MODEL)
    assert warmup.run(outcome=True, tick=TICK_PAST) is True

    args = warmup.warmup_duration[0][0]
    assert args == (MODEL, pytest.approx(DURATION, abs=1e-9))
    delta = warmup_sum(MODEL) - before_sum
    assert delta == pytest.approx(DURATION, abs=1e-9), (
        f"the live histogram took {delta}s under model={MODEL!r}; the shipped line "
        "must add exactly the scripted duration"
    )
    assert 0.0 < delta < 1.0


def test_the_cold_start_counter_really_increments_for_a_cold_model(
    client: Any, warmup: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """Second surface for L582: the shipped counter moved, and L581 gated it.

    Same delta discipline as the histogram leg: a cold warmup must add exactly
    ``1`` to the shipped child, and the warm warmup that follows must add nothing.
    ``m27`` (``None``) moves the increment to another child, and ``m28``/``m29``
    rename it - both leave the shipped child's delta at ``0`` and redden here.
    """
    before = cold_starts(MODEL)
    assert warmup.run(outcome=True, tick=TICK_PAST) is True
    assert [e[0] for e in warmup.cold_start] == [(MODEL,)]
    assert cold_starts(MODEL) - before == 1.0, (
        f"the shipped counter did not move under model={MODEL!r}: {cold_starts(MODEL) - before}"
    )

    warm = Warmup(client, caplog)
    client.__dict__["_last_inference_time"] = TICK_WARM
    after = cold_starts(MODEL)
    assert warm.run(outcome=True, tick=TICK_WARM) is True
    assert cold_starts(MODEL) == after, "a warm model must not increment the cold-start counter"
    assert warm.cold_start == []
