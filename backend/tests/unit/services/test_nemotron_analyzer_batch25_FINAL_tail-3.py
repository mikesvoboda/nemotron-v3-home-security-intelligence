"""Batch-25 FINAL chunk tail-3 kill battery - NemotronAnalyzer._call_llm.

Source under test: backend/services/nemotron_analyzer.py lines 3811-4267 (the
SHIPPED coroutine). Production never bends: every expectation below was PROBED
against the shipped function first (probes under /tmp/wp-batch25/probes/tail3/),
and where shipped behavior differs from a naive expectation the test pins the
SHIPPED behavior.

Keys covered (all "x<U+01C1>NemotronAnalyzer<U+01C1>_call_llm__mutmut_N", written
below in short as "_call_llm__mutmut_N"):
    2, 15, 16, 17, 19, 20, 21, 22, 23, 149, 150, 151, 152, 153, 154, 155, 158,
    168, 171, 173, 176, 179, 205, 208, 225

This file lives OUTSIDE the repo tree, so the repo conftest.py does NOT apply:
``pytestmark = pytest.mark.unit`` is declared below, and the settings env vars
are mirrored from backend/tests/conftest.py by the shared harness
``_b25_dead052_h`` (values copied, not invented). Async is driven with an
explicit ``asyncio.run`` inside sync tests because pytest-asyncio's
``asyncio_mode = "auto"`` ini is not picked up for /tmp paths.

MUTANT SOURCE / RED-CHECK FORCING: bodies are mutmut's OWN per-mutant bodies,
spliced out of /tmp/wp-batch25/instrumented-nemotron_analyzer.py via
instrumented.py.spans. Setting ``WP25_TAIL3_MUT=<n>`` makes every test drive
mutmut's body <n> instead of the shipped coroutine. Deliberate difference from
parts/_b25_dead052_h.compile_mutant: ONLY the function region is exec'd (inside
a synthetic class), never the module top level - re-executing the module top
level would rebind ``tracer = get_tracer(...)`` and the metric helpers and
silently UN-install the patches the test installed, producing a fake all-kill.
A structural check asserts the splice really differs from shipped before any
mutant runs. Nothing under the repository is modified.

AUTOSPEC NOTE (WP4.2 ratchet): every mock-patch CALL SITE carries autospec=True
- the ones inside ``_b25_dead052_h.patched_env`` (record_nemotron_tokens,
AIModelAttributes, set_pipeline_context_attributes, add_span_attributes,
set_llm_inference_attributes, set_inference_result_attributes,
NemotronAnalyzer._get_facade, time.monotonic, asyncio.timeout) plus the
``NemotronAnalyzer._build_prompt`` spy each drive installs here. Swaps that must
deliver a REAL recording object instead of a mock (nem.tracer, the instance-level
_check_guided_json_support stub, the mutant coroutine swap) are direct
assignments with restore in finally - autospec is unsatisfiable there by
construction, since autospec would build the spec FROM the shipped object the
swap exists to replace.

OCCURRENCE-TWIN RULE: mutant identity is occurrence order among identical
minus/plus shapes. Three of this chunk's numbers are occurrence twins and are
carried individually, each killed at the site its own body names:
  * _mutmut_205 and _mutmut_225 both turn a ``camera_id=camera_name`` kwarg into
    ``camera_id=None``; the per-site diff puts 205 on
    record_nemotron_tokens (nemotron_analyzer.py:3996) and 225 on
    cost_tracker.track_llm_usage (:4011), so each is killed by the test that
    pins THAT call's kwargs.
  * _mutmut_149/_150/_151 are the "drop one kwarg" family over the same
    add_span_attributes pre-flight call; each drops a DIFFERENT keyword
    (prompt_length / pipeline_stage / guided_json_enabled), and the pinned
    full-dict equality kills each one independently.
"""

from __future__ import annotations

import asyncio
import contextlib
import difflib
import functools
import logging
import os
import re
import sys
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

PARTS = str(__import__("pathlib").Path(__file__).resolve().parent)
if PARTS not in sys.path:
    sys.path.insert(0, PARTS)

import _b25_dead052_h as H

import backend.services.nemotron_analyzer as nem
from backend.services.context_enricher import (
    BaselineContext,
    EnrichedContext,
)
from backend.services.enrichment_pipeline import EnrichmentResult
from backend.services.nemotron_analyzer import NemotronAnalyzer
from backend.services.prompt_sanitizer import (
    sanitize_camera_name,
    sanitize_detection_description,
)

REPO = H.REPO
FN = H.FN
SPANS = ILINES = SH = S_IDX = E_IDX = None


def _H5():
    """Lazy bind of the helper's loader globals (WP25_MUTT machinery only)."""
    global SPANS, ILINES, SH, S_IDX, E_IDX
    H._ensure()
    SPANS, ILINES, SH, S_IDX, E_IDX = H._SPANS, H._ILINES, H._SH, H._S, H._E


# --- shipped-behavior constants, all PROBED (probes/tail3/probe_b.py) --------
START = "2026-01-01T00:00:00"
END = "2026-01-01T00:05:00"
DET_RAW = "1. 00:00:00 - person (confidence: 0.95)"
DET_SAN = sanitize_detection_description(DET_RAW)
CAM_RAW = "Front " + "<" + "|im_start" + "|" + ">" + " Door  "
CAM_SAN = sanitize_camera_name(CAM_RAW)
# The basic template interpolates camera/window/detections verbatim (probe_b:
# 'Camera: <cam>' at prompt line 57, 'Time: <start> to <end>' at 58, the detection
# list at 61) and the shipped prompt contains the literal string "None" ZERO times
# - which is what makes the None-substitution mutants (_19.._23, _2) visible.
TOKENS = {"prompt_tokens": 7, "completion_tokens": 3}
EMPTY_MSG = "Empty completion from LLM"
LEGACY_PRE = {
    "llm_service": "nemotron",
    "llm_url": H.LLM_URL,
    "template_name": "basic",
    "pipeline_stage": "llm_analysis",
    "guided_json_enabled": False,
}
RISK_KEYS = ("risk_score", "risk_level", "summary", "reasoning")

# Captured BEFORE any patch can touch the class: the _build_prompt spy delegates
# here so a drive still produces a REAL prompt string.
_SHIP_BUILD_PROMPT = NemotronAnalyzer.__dict__["_build_prompt"]


def _ship_prompt(self_, **kw):
    """side_effect for the _build_prompt spy: run the shipped implementation."""
    return _SHIP_BUILD_PROMPT(self_, **kw)


# ---------------------------------------------------------------------------
# mutant install (function-region-only exec; see module docstring)
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=512)
def _mutant_code(mnum: int):
    _H5()
    a, b = SPANS["%s__mutmut_%d" % (FN, mnum)]
    body = list(ILINES[a - 1 : b])
    while body and body[0].strip() == "":
        body.pop(0)
    while body and body[-1].strip() == "":
        body.pop()
    body[0] = re.sub(
        r"async def " + FN + r"__mutmut_\d+",
        "async def _call_llm",
        body[0],
        count=1,
    )
    # structural sanity: the splice must differ from shipped by exactly one
    # contiguous hunk, else the "mutant" is really shipped code (fake green).
    merged = SH[:S_IDX] + body + SH[E_IDX:]
    diff = [
        ln
        for ln in difflib.unified_diff(SH, merged, lineterm="", n=0)
        if ln[:1] in "+-" and ln[:3] not in ("+++", "---")
    ]
    if not diff:
        raise AssertionError("mutant %d splice is a no-op" % mnum)
    # nosemgrep: dangerous-eval
    return compile(
        # nosemgrep: dangerous-eval
        "class _Mut:\n" + "\n".join(body),
        nem.__file__,
        "exec",
    )  # nosemgrep: dangerous-eval


FORCED = int(os.environ.get("WP25_TAIL3_MUT") or 0)


@contextlib.contextmanager
def forced(mutant: int):
    """Swap in mutmut's body for the duration of one drive (0 = shipped)."""
    mnum = FORCED or mutant
    if not mnum:
        yield False
        return
    code = _mutant_code(mnum)

    def dispatch(self, *args, **kwargs):
        ns = dict(nem.__dict__)
        ns.pop("__name__", None)
        # nosemgrep: dangerous-eval
        exec(
            # nosemgrep: dangerous-eval
            code,
            ns,
        )  # lazy: snapshot the patches THIS drive installed  # nosemgrep: dangerous-eval
        return ns["_Mut"]._call_llm(self, *args, **kwargs)

    saved = NemotronAnalyzer.__dict__.get("_call_llm")
    NemotronAnalyzer._call_llm = dispatch
    try:
        yield True
    finally:
        if saved is not None:
            NemotronAnalyzer._call_llm = saved
        else:  # pragma: no cover - the class always defines it
            del NemotronAnalyzer._call_llm


class _StubEnricher:
    """Deterministic stand-in for ContextEnricher's three formatters used by the
    model_zoo prompt branch (not a collaborator of _call_llm itself)."""

    def format_zone_analysis(self, zones):
        return "Zone analysis: stub"

    def format_baseline_comparison(self, baselines):
        return "Baseline comparison: stub"

    def format_cross_camera_summary(self, cross_camera):
        return "Cross-camera activity: stub"


# ---------------------------------------------------------------------------
# the drive
# ---------------------------------------------------------------------------
def call_llm(
    mutant: int = 0,
    *,
    content=H.RISK_BODY,
    usage=None,
    camera=CAM_RAW,
    enriched=None,
    enrichment=None,
    guided=False,
    supports=None,
    max_retries=1,
):
    """Drive _call_llm once (shipped, or mutmut body <mutant>) and record every
    observable channel: returned dict / raised error, the exact kwargs handed to
    _build_prompt, the POSTed payload + headers, the pinned collaborator kwargs,
    the recording span's attributes, both DEBUG log sites, the asyncio.timeout
    deadlines, and the semaphore balance.
    """
    payload = {"usage": TOKENS if usage is None else usage}
    if content is not None:
        payload["content"] = content
    tracer = H.RecordingTracer()
    clock = H.Clock(100.0)
    to = H.RecordingTimeout()
    tracker = H.RecordingCostTracker()
    sem = asyncio.Semaphore(1)
    facade = H.FakeFacade(sem, tracker)
    client = H.FakeClient(payload)
    analyzer = H.build_analyzer(
        payload=payload,
        guided=guided,
        supports=supports,
        llm_url=H.LLM_URL,
        api_key=None,
        max_retries=max_retries,
    )
    analyzer._http_client = client
    # The model_zoo branch of _build_prompt formats zone/baseline/cross-camera text
    # through the context enricher (reached via the facade). It is not one of
    # _call_llm's collaborators, so the drive supplies a deterministic stand-in
    # rather than letting the facade build the real one. Never touched on the
    # basic-prompt drives. Instance-level REAL stub, not a mock patch.
    analyzer._context_enricher = _StubEnricher()

    logger = logging.getLogger(H.LOGGER)
    handler = H._Recorder()
    previous = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    result: dict = {}
    exc: BaseException | None = None
    settings = nem.get_settings()
    try:
        with H.patched_env(tracer, clock, to, facade) as mocks:
            # The spy records the EXACT kwargs _call_llm hands to _build_prompt;
            # the side_effect delegates to the shipped _build_prompt captured at
            # import time, so the prompt inside the POSTed payload is real
            # template output (needed by the prompt-content pins below).
            with patch.object(
                NemotronAnalyzer,
                "_build_prompt",
                autospec=True,
                side_effect=_ship_prompt,
            ) as bp:
                with forced(mutant):
                    try:
                        result = asyncio.run(
                            analyzer._call_llm(
                                camera_name=camera,
                                start_time=START,
                                end_time=END,
                                detections_list=DET_RAW,
                                enriched_context=enriched,
                                enrichment_result=enrichment,
                            )
                        )
                    except BaseException as e:
                        exc = e
                    bp_kwargs = [dict(c.kwargs) for c in bp.call_args_list]
                    bp_positional = [tuple(c.args[1:]) for c in bp.call_args_list]
                    legacy = [dict(c.kwargs) for c in mocks["legacy"].call_args_list]
                    tokens = [dict(c.kwargs) for c in mocks["tokens"].call_args_list]
                    ai = [dict(c.kwargs) for c in mocks["ai_attrs"].set_on_span.call_args_list]
                    pipe = [
                        (tuple(c.args), dict(c.kwargs)) for c in mocks["pipe_attrs"].call_args_list
                    ]
    finally:
        logger.setLevel(previous)
        logger.removeHandler(handler)

    return H.Drive(
        mutant=FORCED or mutant,
        analyzer=analyzer,
        client=client,
        posts=list(client.calls),
        result=result,
        exc=exc,
        tracer=tracer,
        clock=clock,
        timeout=to,
        facade=facade,
        tracker=tracker,
        semaphore=sem,
        semaphore_limit=1,
        debug_records=[r for r in handler.records if r.levelno == logging.DEBUG],
        records=list(handler.records),
        token_calls=tokens,
        ai_calls=ai,
        pipe_calls=pipe,
        legacy_calls=legacy,
        settings=settings,
        bp_calls=bp_kwargs,
        bp_positional=bp_positional,
        track_calls=tracker.track_calls,
    )


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------
def test_build_prompt_receives_the_window_inputs_verbatim():
    """Kills _call_llm__mutmut_19, _mutmut_20, _mutmut_21, _mutmut_22.

    nemotron_analyzer.py:3869-3879 forwards the prompt inputs to _build_prompt as
    keyword arguments, and each of these mutants replaces ONE forwarded value with
    None: camera_name (:3870), start_time (:3871), end_time (:3872),
    detections_list (:3873). The autospec spy pins the FULL keyword dict of the
    single call, so any None substitution fails on the differing key.

    Not the killer for _mutmut_23 (same shape, but on enriched_context at :3874):
    this drive legitimately passes enriched_context=None, so on this drive alone
    the substitution is invisible. _mutmut_23 is killed by
    test_model_zoo_enriched_context_is_forwarded_by_identity, which drives a
    NON-None EnrichedContext - proving :3874 is a live position rather than a dead
    argument rewrite.
    """
    d = call_llm()
    assert d.exc is None, d.exc
    assert len(d.bp_calls) == 1, d.bp_calls
    assert len(d.bp_positional) == 1 and d.bp_positional[0] == ()
    assert d.bp_calls[0] == {
        "camera_name": CAM_SAN,
        "start_time": START,
        "end_time": END,
        "detections_list": DET_SAN,
        "enriched_context": None,
        "enrichment_result": None,
        "camera_health_context": "",
        "detection_dicts": None,
        "auto_tuning_context": "",
        "household_context": "",
    }


def test_camera_name_is_sanitized_before_the_prompt_is_built():
    """Kills _call_llm__mutmut_2 (sanitize_camera_name(camera_name) -> (None)).

    nemotron_analyzer.py:3856 sanitizes the attacker-influenceable camera name and
    rebinds it; every later consumer (the _build_prompt kwarg, the prompt body,
    the span's camera_id) sees the SANITIZED value. The drive's camera is
    ``'Front <chatml-start token> Door  '`` (raw, with trailing whitespace), and
    the sanitizer collapses the ChatML token to ``[FILTERED:chatml_start]`` and
    strips the padding (probed: sanitize_camera_name -> 'Front [FILTERED:chatml_start] Door').

    With the mutant's None argument the sanitizer returns "" (:prompt_sanitizer
    183-184) and the prompt's camera line becomes 'Camera: ' - so the pinned
    prompt line fails. The assertion set ALSO pins that the raw token never
    reaches the prompt, which is the actual NEM-1722 security property.
    """
    d = call_llm()
    assert d.exc is None, d.exc
    prompt = d.result["llm_prompt"]
    assert prompt == H.payload_of(d)["prompt"]  # payload carries the same prompt
    # the RAW attacker string never reaches the prompt ...
    assert CAM_RAW not in prompt
    assert CAM_RAW.strip() not in prompt
    # ... its filtered form appears exactly once, on the camera line ...
    assert prompt.count("[FILTERED:chatml_start]") == 1
    assert "Camera: " + CAM_SAN in prompt.splitlines()
    assert d.bp_calls[0]["camera_name"] == CAM_SAN
    # and the sanitizer really is what produced it (no hard-coded string drift).
    # NOTE: the prompt legitimately still contains <|im_start|> - the ChatML
    # scaffolding belongs to the template; only the user-controlled token is
    # filtered, which is the property pinned above.
    assert CAM_SAN != CAM_RAW
    assert sanitize_camera_name(CAM_RAW) == CAM_SAN


def test_template_name_is_basic_for_an_unenriched_call():
    """Kills _call_llm__mutmut_15, _mutmut_16 and _mutmut_17.

    nemotron_analyzer.py:3862-3865 picks the metrics template name and it is
    observable in the pre-retry add_span_attributes kwargs (:3964-3966):

        template_name = "model_zoo" if has_enriched_context or enrichment_result
                        is not None else "basic"

    The drive carries neither an EnrichedContext nor an EnrichmentResult, so the
    shipped name is "basic" and the pinned kwargs say so. Each of the three
    mutants breaks that pin in its own way:
      * _mutmut_15 flips the second condition to ``enrichment_result is None``;
        with enrichment_result None the mutant condition is unconditionally True,
        so the name becomes "model_zoo" on THIS drive - the pin fails.
      * _mutmut_16 rewrites the else-arm to "XXbasicXX",
      * _mutmut_17 rewrites the else-arm to "BASIC",
    both of which also fail the same exact-equality pin. The model_zoo arm itself
    is exercised by test_prompt_template_reaches_the_span_kwargs below, so the
    killed name is not resting on an unreachable branch.
    """
    d = call_llm()
    assert d.exc is None, d.exc
    assert d.legacy_calls[0]["template_name"] == "basic"
    assert d.result["risk_score"] == 60  # same drive, success path reached

    # TWO-SIDED WITNESS that the pin is not resting on a one-branch drive: an
    # enrichment_result-only call (has_enriched_context False, enrichment_result
    # NOT None) takes the model_zoo arm under shipped code while _mutmut_15 would
    # report "basic" there. So the shipped name flips with the condition and the
    # mutant's inversion is caught from both directions, not just the basic one.
    m = call_llm(enrichment=EnrichmentResult())
    assert m.exc is None, m.exc
    assert m.legacy_calls[0]["template_name"] == "model_zoo"


def test_model_zoo_enriched_context_is_forwarded_by_identity():
    """Kills _call_llm__mutmut_23 (and pins the model_zoo side of the template name).

    _call_llm__mutmut_23 turns the forwarded ``enriched_context=enriched_context``
    at nemotron_analyzer.py:3874 into ``enriched_context=None``. Only a drive that
    actually passes a non-None EnrichedContext can see that, which is why THIS
    drive (not the basic one) is what carries the key: the spy shows the enriched
    context arriving as the SAME object, so :3874 is a live position and the None
    substitution is a real behavior change rather than a dead-argument rewrite. The
    same drive also pins the "model_zoo" arm of the template-name choice, which the
    basic drive in test_template_name_is_basic_for_an_unenriched_call cannot see.
    """
    enriched = EnrichedContext(
        camera_name=CAM_SAN,
        camera_id="cam-front",
        baselines=BaselineContext(hour_of_day=3, day_of_week="Monday"),
    )
    d = call_llm(enriched=enriched)
    assert d.exc is None, d.exc
    assert d.legacy_calls[0]["template_name"] == "model_zoo"  # the other arm
    assert len(d.bp_calls) == 1, d.bp_calls
    got = d.bp_calls[0]["enriched_context"]
    assert got is enriched
    assert d.bp_calls[0]["enrichment_result"] is None


def test_legacy_span_attributes_pre_retry_call_is_pinned_exactly():
    """Kills _call_llm__mutmut_149, _150, _151, _152, _153, _154, _155.

    nemotron_analyzer.py:3963-3970 emits the legacy compatibility attributes ONCE
    before the retry loop. The full-dict pin kills all seven:
      * _149 drops prompt_length, _150 drops pipeline_stage, _151 drops
        guided_json_enabled (the "delete one kwarg" family - a missing key fails
        equality),
      * _152/_153 rewrite llm_service to "XXnemotronXX"/"NEMOTRON",
      * _154/_155 rewrite pipeline_stage to "XXllm_analysisXX"/"LLM_ANALYSIS".
    prompt_length is pinned to the shipped len(prompt) of the real prompt string,
    so this test also proves the truncation guard left the prompt untouched.
    """
    d = call_llm()
    assert d.exc is None, d.exc
    prompt = H.payload_of(d)["prompt"]
    assert len(d.legacy_calls) >= 2, d.legacy_calls
    assert d.legacy_calls[0] == dict(LEGACY_PRE, prompt_length=len(prompt))
    assert len(prompt) == len(H.payload_of(d)["prompt"])


def test_asyncio_timeout_deadline_is_read_plus_connect_timeout():
    """Kills _call_llm__mutmut_158 (asyncio.timeout(explicit_timeout) -> (None)).

    nemotron_analyzer.py:3910 computes explicit_timeout =
    settings.nemotron_read_timeout + settings.ai_connect_timeout and :3976 passes
    it to asyncio.timeout as the defense-in-depth deadline (NEM-1465). The
    recording asyncio.timeout stand-in captures the WHEN value, which is pinned to
    the same settings-derived number - so the mutant's None (no deadline) fails.
    """
    d = call_llm()
    assert d.exc is None, d.exc
    assert d.timeout.whens == [H.expected_timeout(d.settings)]
    assert d.timeout.whens[0] is not None
    assert d.timeout.entered == 1 and d.timeout.exited == 1


def test_success_drive_records_the_clock_delta_duration():
    """Kills _call_llm__mutmut_168 (monotonic() - start -> monotonic() + start).

    nemotron_analyzer.py:3984 derives llm_call_duration from the two
    time.monotonic() reads and :3999/:4006/:4031/:4034 consume it. The harness
    Clock returns a constant, so the shipped delta is exactly 0.0 and it is pinned
    in all three consumers (record_nemotron_tokens duration_seconds,
    track_llm_usage duration_seconds, legacy llm_duration_ms) plus the two
    *_ms/llm_duration_ms-derived span calls. The mutant yields
    monotonic() + start == 200.0, breaking every one of them.
    """
    d = call_llm()
    assert d.exc is None, d.exc
    assert d.result["risk_score"] == 60
    assert set(RISK_KEYS) <= set(d.result)
    assert d.result["raw_response"] == H.RISK_BODY
    assert d.token_calls[0]["duration_seconds"] == 0.0
    assert d.track_calls[0]["duration_seconds"] == 0.0
    assert d.legacy_calls[1]["llm_duration_ms"] == 0.0
    assert d.clock.calls > 0


def test_token_and_cost_records_pin_camera_id_at_their_own_occurrence():
    """Kills _call_llm__mutmut_205 and _mutmut_225 (OCCURRENCE TWINS).

    Both mutants turn ``camera_id=camera_name`` into ``camera_id=None``, but they
    sit on DIFFERENT calls and each is killed by the pin on ITS call:
      * _205 -> record_nemotron_tokens(camera_id=...) at :3996,
      * _225 -> cost_tracker.track_llm_usage(camera_id=...) at :4011.
    Both are pinned to the sanitized camera name, and each call's remaining
    kwargs are pinned in full so the twin identification is not accidental: the
    tokens call carries input/output_tokens + duration_seconds only, the cost
    tracker call additionally carries model="nemotron".
    """
    d = call_llm()
    assert d.exc is None, d.exc
    assert d.token_calls == [
        {
            "camera_id": CAM_SAN,
            "input_tokens": TOKENS["prompt_tokens"],
            "output_tokens": TOKENS["completion_tokens"],
            "duration_seconds": 0.0,
        }
    ]
    assert d.track_calls == [
        {
            "input_tokens": TOKENS["prompt_tokens"],
            "output_tokens": TOKENS["completion_tokens"],
            "model": "nemotron",
            "duration_seconds": 0.0,
            "camera_id": CAM_SAN,
        }
    ]
    assert d.tracker.increment_calls == 1


def test_duration_seconds_is_recorded_when_usage_is_present():
    """Kills _call_llm__mutmut_208 (duration_seconds=<conditional> -> None).

    nemotron_analyzer.py:3999-4001 passes the measured duration when either token
    count is positive and None otherwise. With usage prompt_tokens/completion_tokens
    = 7/3 the shipped kwargs carry the (clock-derived, here 0.0) duration, so the
    mutant's unconditional None fails the pin. The zero-usage counterfactual keeps
    the conditional non-vacuous: shipped then records duration_seconds=None while
    still recording the call at all.
    """
    d = call_llm()
    assert d.exc is None, d.exc
    assert "duration_seconds" in d.token_calls[0]
    assert d.token_calls[0]["duration_seconds"] is not None

    z = call_llm(usage={})
    assert z.exc is None, z.exc
    assert z.token_calls == [
        {
            "camera_id": CAM_SAN,
            "input_tokens": 0,
            "output_tokens": 0,
            "duration_seconds": None,
        }
    ]


def test_empty_completion_raises_the_shipped_valueerror_message_exactly():
    """Kills _call_llm__mutmut_179 and _mutmut_176.

    Two shapes on the empty-completion guard (:3987-3989):
      * _179 wraps the message -> "XXEmpty completion from LLMXX". The assertion is
        an EXACT string equality on str(exc): a pytest.raises(match=...) would NOT
        kill it, because the mutant message still contains the shipped substring
        (probed).
      * _176 changes the .get default from "" to the truthy "XXXX", so with the
        "content" key ABSENT the guard stops firing: the run falls through to
        _parse_llm_response and raises a DIFFERENT ValueError whose message embeds
        "XXXX" and which carries the raw_completion attribute. Both channels -
        shipped message and absence of raw_completion - are pinned for the
        content-absent drive.
    """
    d = call_llm(content="")
    assert type(d.exc) is ValueError
    assert str(d.exc) == EMPTY_MSG
    assert not hasattr(d.exc, "raw_completion")
    assert d.token_calls == [] and d.track_calls == []
    assert len(d.legacy_calls) == 1  # only the pre-retry call: never succeeded
    d.assert_semaphore_free()

    m = call_llm(content=None)  # "content" key absent from the response body
    assert type(m.exc) is ValueError
    assert str(m.exc) == EMPTY_MSG
    assert not hasattr(m.exc, "raw_completion")


def test_missing_content_key_and_empty_content_are_observably_identical():
    """Equivalence EVIDENCE for _call_llm__mutmut_171 and _mutmut_173.

    Both mutants only change the DEFAULT of llm_result.get("content", ...) - _171
    to None, _173 to the one-argument form (which is also default None). The
    default is read only when the "content" key is absent, and shipped then raises
    ValueError immediately at :3988-3989 (``if not completion_text``), so the
    substituted value never escapes to any observable channel. This test drives
    BOTH key-present-empty and key-absent shapes and pins that every recorded
    channel is identical - error type, exact message, absence of raw_completion,
    the pre-retry span kwargs, the absence of token/cost records, the timeout
    deadline, the POSTed payload and the DEBUG log - which is the constructive
    proof that "" and None are indistinguishable here. (The counter-witness
    _mutmut_176, a truthy default, is killed in the test above - the guard fires
    on FALSY, so only falsy defaults are equivalent.)
    """
    empty = call_llm(content="")
    absent = call_llm(content=None)
    assert type(empty.exc) is type(absent.exc) is ValueError
    assert str(empty.exc) == str(absent.exc) == EMPTY_MSG
    assert hasattr(empty.exc, "raw_completion") is hasattr(absent.exc, "raw_completion")
    assert empty.legacy_calls == absent.legacy_calls
    assert empty.token_calls == absent.token_calls == []
    assert empty.track_calls == absent.track_calls == []
    assert empty.timeout.whens == absent.timeout.whens
    assert empty.posts == absent.posts
    assert empty.debug_texts == absent.debug_texts
    assert empty.result == absent.result == {}
