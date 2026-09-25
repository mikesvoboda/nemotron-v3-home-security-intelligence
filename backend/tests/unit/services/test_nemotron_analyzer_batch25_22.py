"""Batch-25 part 22 — chunk "tail:NemotronAnalyzer.__init__+5more#chunk1" (98 keys).

Chunk file: /tmp/wp-batch25/chunks/chunk-22.json. Six shipped functions:

  NemotronAnalyzer.__init__                              47 keys (:301-421)
  NemotronAnalyzer._run_enrichment_pipeline_from_data     17 keys (:2209-2313)
  NemotronAnalyzer._build_ondemand_enrichment_context     20 keys (:3744-3810)
  NemotronAnalyzer.calculate_batch_priority               8 keys (:647-690)
  NemotronAnalyzer.get_warmth_state                       5 keys (:1395-1422)
  NemotronAnalyzer.set_experiment_config                  1 key   (:889-908)

Everything below was probed against the SHIPPED module first (probes:
/tmp/wp-batch25/probes/c22/) and asserts shipped behavior, not intent.

HOW THE CONSTRUCTOR IS OBSERVED (the only reason its 47 survivors exist):
`constructed(fn)` builds a throwaway subclass whose __init__ is the function
under test and reads back the state it wrote — attribute identity, the two
httpx.Timeout objects, and the two live connection pools via
`client._transport._pool` (the repo's own precedent for pool assertions,
backend/tests/unit/services/test_http_connection_pooling.py:68-69,188-189) —
plus the debug record it logs.

OCCURRENCE TWEINS CARRIED IN FULL. The `limits=httpx.Limits(max_connections=
10, max_keepalive_connections=5)` shape occurs TWICE in __init__ (:406
inference client, :410 health client), so every limits shape group has two keys
and one test kills both — keys 60/71 (limits argument dropped), 61/72
(max_connections -> None), 62/73 (max_keepalive_connections -> None), 63/74
(max_connections= dropped), 64/75 (max_keepalive_connections= dropped), 65/76
(10 -> 11), 66/77 (5 -> 6). test_init_pools pins BOTH pools for all fourteen.

THE ONLY EQUIVALENTS IN THIS CHUNK ARE THE TWO UNREAD-OPERAND SHAPES on the
priority-label frozenset that NO CODE EVER READS: __init__ 53
(`self._priority_medium_labels = frozenset(...)` -> `= None`) and 55
(`label.lower()` -> `label.upper()` inside that same comprehension). Proof of
unreadness: `_priority_medium_labels` is written at
backend/services/nemotron_analyzer.py:398 and read NOWHERE — repo-wide
`grep -rn "_priority_medium_labels" backend/` returns exactly that one
assignment (plus its instrumented copies), no dynamic `getattr(self, ...)`
exists in the module, no test/API/scheduler touches it, and the medium tier is
implemented inside BatchCoalescer.calculate_priority
(backend/services/batch_coalescer.py:334-382) from that module's own
WEAPON_TYPES / CRITICAL_TYPES / VEHICLE_TYPES constants, never from the
analyzer's frozenset. The analyzer's only frozenset read is :677
`types_lower & self._priority_high_labels`, and the frozensets appear in NO log
record (:412-418 interpolates only max_retries / read timeout / guided_json /
coalescing / priority_queue). A value written to an attribute no code path ever
reads has no observable effect, so writing None or an upper-cased set instead
is behavior-preserving; no test — mine or the repo's — can distinguish them,
which is exactly why they are survivors. KEY 53 IS *NOT* THE TWIN OF KEY 52:
the shipped `label.lower()` at :396 is the FIRST of the two identical lower()
occurrences and belongs to the 52-group (minus names priority_high_labels,
whose set IS read at :677 — so 52 IS killed, by
test_init_priority_high_labels_are_lowercased_for_matching below), while 55 is
the second occurrence (the medium comprehension) — the group minus strings
differ, and only the medium-group keys (53/55) are equivalent.

NO KEY IN THIS CHUNK IS killed_by_draft. The draft battery
(/tmp/wp-batch25/test_nemotron_analyzer_batch25.py) drives only
_parse_llm_response / _validate_risk_data / _extract_json_objects. Repo overlap
was checked per function:
  * get_warmth_state — all five keys sit on the post-`_last_inference_time`
    tail (:1418-1421). The three repo warm-state tests
    (backend/tests/unit/services/test_nemotron_analyzer.py:3724-3746 and
    test_model_warmup.py:184-208) DO reach that tail, but each is itself a
    mutmut survivor for these keys: their fixture leaves
    `_last_inference_time` non-None with a 30-60s gap while
    `_cold_start_threshold` is 300.0, so every one of them lands on the "warm"
    branch — a "cold" -> "XXcoldXX"/"COLD" mutation (22/23) is invisible there,
    20's always-warm mutation agrees with their warm assertion, and 16/17
    change nothing at their inputs. Zero overlap; all five are killed here (the
    boundary is driven with a mocked time.monotonic and the "cold" literal is
    pinned on a branch no mutant can route around).
  * calculate_batch_priority — `grep -rn calculate_batch_priority backend/tests`
    returns nothing: the method has no test at all, which is why all eight of
    its shapes survived.
  * __init__ / _build_ondemand_enrichment_context /
    _run_enrichment_pipeline_from_data — the repo touches them only as a
    fixture side effect (NemotronAnalyzer(redis_client=...) construction) or
    behind an AsyncMock pipeline; nothing asserts the timeout/pool
    construction, the frozensets, the init record, the on-demand section
    assembly, or the DetectionInput/image mapping.
  * set_experiment_config — test_prompt_experiment_integration.py calls it and
    asserts behavior downstream of `self._experiment_config = config`; the
    config-shape INFO f-string (:904-908) is asserted nowhere.

GREEN-CHECK: cd /agents/agent-veranda3/workspace && .venv/bin/python -m pytest \
    /tmp/wp-batch25/parts/test_batch25_22.py -p no:cacheprovider -o addopts= -q
"""

from __future__ import annotations

import logging
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import httpx
import pytest

pytestmark = pytest.mark.unit

# This file lives outside the repo tree, so backend/tests/conftest.py does NOT
# apply. Mirror the minimum env that conftest sets before importing backend
# (values copied verbatim from backend/tests/conftest.py, not invented).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")

from backend.config.prompt_experiment import PromptExperimentConfig
from backend.core.config import Settings
from backend.services import nemotron_analyzer as nem
from backend.services.batch_coalescer import (
    BatchCoalescer,
    Priority,
)
from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentPipeline,
    EnrichmentResult,
)

LOGGER = "backend.services.nemotron_analyzer"

# --------------------------------------------------------------------------
# settings stub — every value distinct from BOTH the pydantic default and the
# sibling setting it could be swapped with (with defaults-equal stub values the
# connect/pool/read/health swaps are unobservable).
# --------------------------------------------------------------------------
LLM_URL = "http://nemotron.test:8091/v1"
CONNECT_T = 11.0
READ_T = 121.0
HEALTH_T = 5.5
RETRIES_FROM_SETTINGS = 3
WARMUP_PROMPT = "WARMUP-PROMPT-TEXT"
GUIDED_JSON = False
COALESCING_ENABLED = False
COALESCING_MAX = 7
COALESCING_WINDOW = 4.5
PRIORITY_QUEUE = True
HIGH_LABELS = ["Weapon", "INTRUDER", "fire"]
MEDIUM_LABELS = ["Person", "unknown"]

# shipped limits (NEM-5538): max_connections=10, max_keepalive_connections=5,
# keepalive_expiry left at httpx's 5.0 default. httpx 0.28.1 resolves a None
# limit to the pool's own defaults (max_connections -> INFINITY,
# max_keepalive_connections -> min(max/2, 10)) — a distinct signature per
# mutant, so one triple assertion covers all seven shapes on both clients.
POOL_SHIPPED = (10, 5, 5.0)

MSG_INIT = (
    f"NemotronAnalyzer initialized with max_retries={RETRIES_FROM_SETTINGS}, "
    f"timeout={READ_T}s, "
    f"guided_json={GUIDED_JSON}, "
    f"coalescing_enabled={COALESCING_ENABLED}, "
    f"priority_queue_enabled={PRIORITY_QUEUE}"
)
MSG_EXPERIMENT = "Experiment config set: shadow_mode=True, treatment=30.0%, experiment=my-exp"


def settings_stub() -> MagicMock:
    s = MagicMock(spec=Settings)
    # P0.3 flags (#6678): pydantic v2 field names are not in
    # dir(Settings), so a spec'd mock must pin them explicitly.
    s.nemotron_constrained_decoding_enabled = False
    s.nemotron_constrained_fail_closed = True
    s.nemotron_constrained_probe_enabled = True
    s.nemotron_constrained_probe_required_build = None
    s.nemotron_verification_engine = "llama.cpp"
    s.nemotron_model_id = "Nemotron-3-Nano-30B-A3B-Q4_K_M"
    s.nemotron_url = LLM_URL
    s.nemotron_api_key = None
    s.ai_connect_timeout = CONNECT_T
    s.nemotron_read_timeout = READ_T
    s.ai_health_timeout = HEALTH_T
    s.nemotron_max_retries = RETRIES_FROM_SETTINGS
    s.ai_warmup_enabled = True
    s.ai_cold_start_threshold_seconds = 300.0
    s.nemotron_warmup_prompt = WARMUP_PROMPT
    s.nemotron_use_guided_json = GUIDED_JSON
    s.nemotron_guided_json_fallback = True
    s.batch_coalescing_enabled = COALESCING_ENABLED
    s.batch_coalescing_max_size = COALESCING_MAX
    s.batch_coalescing_time_window = COALESCING_WINDOW
    s.priority_queue_enabled = PRIORITY_QUEUE
    s.priority_high_labels = list(HIGH_LABELS)
    s.priority_medium_labels = list(MEDIUM_LABELS)
    return s


class _Recorder(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def pool(client: httpx.AsyncClient) -> tuple:
    """The live connection pool's limit triple (repo precedent, see header)."""
    p = client._transport._pool
    return (p._max_connections, p._max_keepalive_connections, p._keepalive_expiry)


def capture_logs():
    """Attach a DEBUG capture handler to the module logger."""
    recorder = _Recorder()
    logger = logging.getLogger(LOGGER)
    previous = logger.level
    logger.addHandler(recorder)
    logger.setLevel(logging.DEBUG)
    return recorder, logger, previous


def stop_capture(recorder, logger, previous) -> list[str]:
    logger.setLevel(previous)
    logger.removeHandler(recorder)
    return [r.getMessage() for r in recorder.records]


# ==========================================================================
# NemotronAnalyzer.__init__  (47 keys)
# ==========================================================================

# Every construction below passes these two kwargs explicitly:
#   use_enriched_context=False — so the `= None` mutants of the attribute store
#     and of the constructor default are both visible;
#   max_retries=3 — equal to the settings fallback, so the init record stays
#     identical while the `max_retries is not None` guard is probed.
INIT_KWARGS = {"use_enriched_context": False, "max_retries": RETRIES_FROM_SETTINGS}


def constructed(init_fn=None, **kwargs):
    """Build with `init_fn` (default: the shipped __init__) and capture logs.

    A throwaway subclass carries the function under test, so the shipped class
    is never patched and the call goes through normal bound-method semantics.
    """
    merged = {**INIT_KWARGS, **kwargs}
    recorder, logger, previous = capture_logs()
    try:
        with patch(
            "backend.services.nemotron_analyzer.get_settings",
            autospec=True,
            return_value=settings_stub(),
        ):
            if init_fn is None:
                analyzer = nem.NemotronAnalyzer(redis_client=None, **merged)
            else:
                # The reconstructed variant is a plain function object (the
                # instrumented copy's module-level name), so it is assigned to a
                # subclass rather than unwrapped.
                class Built(nem.NemotronAnalyzer):
                    pass

                Built.__init__ = init_fn
                analyzer = Built(redis_client=None, **merged)
        return analyzer, stop_capture(recorder, logger, previous)
    except BaseException:
        stop_capture(recorder, logger, previous)
        raise


def test_init_stores_settings_and_injected_dependencies():
    """Kills __init__ mutmut_3, mutmut_23, mutmut_25, mutmut_26, mutmut_27,
    mutmut_45.

    Pins the constructor's dependency wiring AS SHIPPED: _llm_url comes from
    settings.nemotron_url and the five injected objects are stored by identity.
    _3 stores None for the LLM base URL, which every downstream request
    interpolates (model_readiness_probe posts f"{self._llm_url}/v1/completions"
    at :1437, _check_guided_json_support posts f"{self._llm_url}/completion" at
    :465) — a None URL breaks the whole inference path. Each `= None` mutant of
    an injected dependency nulls an object the shipped class then hands out:
    _25/_26 feed _get_context_enricher/_get_enrichment_pipeline (:1359-1367,
    which only skips its facade lookup when the attribute is not None), _27
    forces _get_facade() back onto the global singleton (undoing NEM-3150's
    single-mock-target test seam), _45 makes _get_batch_coalescer() (:642-646)
    return the global coalescer instead of the injected one, and _23 turns the
    documented opt-out `use_enriched_context=False` into None.
    """
    enricher = object()
    pipeline = object()
    facade = object()
    coalescer = object()
    a, _logs = constructed(
        context_enricher=enricher,
        enrichment_pipeline=pipeline,
        service_facade=facade,
        batch_coalescer=coalescer,
    )
    assert a._llm_url == LLM_URL
    assert a._use_enriched_context is False
    assert a._context_enricher is enricher
    assert a._enrichment_pipeline is pipeline
    assert a._facade is facade
    assert a._batch_coalescer is coalescer
    # the other flag keeps its True default (settings are never consulted)
    assert a._use_enrichment_pipeline is True


def test_init_max_retries_falls_back_to_settings_only_when_none():
    """Kills __init__ mutmut_29.

    `max_retries if max_retries is not None else settings.nemotron_max_retries`
    -> `max_retries if (max_retries is not None) and False else ...` discards a
    caller-supplied retry budget and silently reinstates the cluster default, so
    an operator narrowing retries for a latency-bound camera gets the settings
    value instead. Both arms are pinned: explicit 3 wins here (the stub carries
    the same 3 so the init record is identical either way) and explicit 7 below
    is the arm the mutant can never satisfy.
    """
    a, logs = constructed()
    assert a._max_retries == RETRIES_FROM_SETTINGS
    assert logs.count(MSG_INIT) == 1
    b, _ = constructed(max_retries=7)
    assert b._max_retries == 7


def test_init_builds_inference_timeout_from_settings_and_shares_it():
    """Kills __init__ mutmut_5, mutmut_6, mutmut_7, mutmut_8, mutmut_9,
    mutmut_57, mutmut_59.

    The inference timeout is a four-field httpx.Timeout built from
    ai_connect_timeout (connect/pool) and nemotron_read_timeout (read/write),
    and the persistent client must receive it as `timeout=self._timeout`.
    httpx.Timeout has no __eq__ and AsyncClient COPIES the timeout it is given
    (probe: `client.timeout is not the passed object`), so both sides are pinned
    through as_dict(). The `timeout=None` mutant (_57) yields
    {connect/read/write/pool: None} — a client with NO read deadline, the exact
    hazard NEM-5538's timeout wiring exists to remove — and dropping the
    keyword (_59) silently substitutes httpx's uniform 5.0 s default, far below
    a 121 s LLM read. The per-field dicts kill the four `field=None` shapes
    (_6-_9: a None connect/pool survives httpx normalization and shows up in
    as_dict, probe) and the whole-object store (_5: _timeout becomes None and
    as_dict() raises).
    """
    a, _logs = constructed()
    expected = {
        "connect": CONNECT_T,
        "read": READ_T,
        "write": READ_T,
        "pool": CONNECT_T,
    }
    assert a._timeout.as_dict() == expected
    assert a._http_client.timeout.as_dict() == expected


def test_init_builds_health_timeout_and_shares_it_with_health_client():
    """Kills __init__ mutmut_14, mutmut_15, mutmut_16, mutmut_17, mutmut_18,
    mutmut_68, mutmut_70.

    The health client gets its OWN uniform timeout built from
    ai_health_timeout on all four fields — deliberately not the 121 s inference
    read timeout, because a health probe that hangs for two minutes defeats
    readiness checks and warmup (:1428+). Same as_dict pin as the inference
    client; _68 removes the health deadline (as_dict -> all None), _70
    substitutes httpx's uniform 5.0 s default, _14-_18 break the timeout object
    itself (a None field shows up in the copied as_dict, probe).
    """
    a, _logs = constructed()
    expected = dict.fromkeys(("connect", "read", "write", "pool"), HEALTH_T)
    assert a._health_timeout.as_dict() == expected
    assert a._health_http_client.timeout.as_dict() == expected


def test_init_pools_are_bounded_to_ten_connections_five_keepalives():
    """Kills __init__ mutmut_60, 61, 62, 63, 64, 65, 66 AND their occurrence
    twins mutmut_71, 72, 73, 74, 75, 76, 77 — fourteen keys, because the
    `limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)`
    shape occurs twice (:406 inference client, :410 health client) and both
    pools are pinned here.

    Shipped limit is 10 connections / 5 keepalive on BOTH clients. Every
    mutation has a distinct resolved-pool signature (probe, httpx 0.28.1):
    dropping the limits argument (_60/_71) falls back to httpx's own
    (100, 20) limits — a ten-fold connection surge against a single NIM
    endpoint; passing or dropping a keyword inflates one side to INFINITY or to
    min(max/2, 10) = 10; the numeric bumps read (11, 5) and (10, 6). Pinning
    the whole (max_connections, max_keepalive_connections, keepalive_expiry)
    triple for both clients kills all fourteen and nothing else satisfies it.
    """
    a, _logs = constructed()
    assert pool(a._http_client) == POOL_SHIPPED
    assert pool(a._health_http_client) == POOL_SHIPPED


def test_init_logs_configuration_summary_with_interpolated_values():
    """Kills __init__ mutmut_78.

    The initialization DEBUG record at :412-418 is the only record of the
    effective retry / timeout / guided-json / coalescing / priority-queue
    configuration for a started analyzer; the mutant replaces the whole
    f-string with None, logging the literal "None". Asserted as the exact
    shipped interpolation of the stubbed settings (probe: the timeout renders
    as `121.0s`, the flags as False/True).
    """
    _a, logs = constructed()
    assert logs.count(MSG_INIT) == 1, logs


def test_init_priority_high_labels_are_lowercased_for_matching():
    """Kills __init__ mutmut_52 ONLY — deliberately NOT the sibling keys 53/55,
    which this file proves equivalent (module header): `_priority_medium_labels`
    has no reader, so nothing is asserted about it here and its two mutants are
    unkillable by construction.

    `label.lower()` -> `label.upper()` on the FIRST lower() occurrence (:396)
    makes the configured high-priority set {"WEAPON","INTRUDER","FIRE"} while
    calculate_batch_priority lower-cases the detections (:675), so the P0
    short-circuit at :677 — the one read of this frozenset — can never fire and
    a reported weapon degrades from P0_CRITICAL to whatever the coalescer's own
    table says.
    """
    a, _logs = constructed()
    assert a._priority_high_labels == frozenset({"weapon", "intruder", "fire"})


def test_init_coalescing_and_priority_settings_are_stored():
    """Kills __init__ mutmut_46, mutmut_47, mutmut_48, mutmut_49.

    The four NEM-5464 Phase-5 knobs are read straight off settings and stored.
    Two of them are interpolated into the init record pinned above
    (`coalescing_enabled=False`, `priority_queue_enabled=True`), so their `=
    None` mutants change that record; _47/_48 null the coalescer's batch-size
    and window limits that register_coalesce_candidate's batching compares.
    """
    a, logs = constructed()
    assert a._coalescing_enabled is COALESCING_ENABLED
    assert a._coalescing_max_size == COALESCING_MAX
    assert a._coalescing_time_window == COALESCING_WINDOW
    assert a._priority_queue_enabled is PRIORITY_QUEUE
    assert logs.count(MSG_INIT) == 1, logs


def test_init_warmup_and_ab_rollout_slots_start_as_shipped():
    """Kills __init__ mutmut_33, mutmut_37, mutmut_39, mutmut_41.

    `_is_warming` must be the boolean False, not None: get_warmth_state (:1403)
    and warmup() branch on `if self._is_warming:` for the "warming" report that
    load balancers read. `_warmup_prompt` is the literal body of the readiness
    probe request (:1440 `"prompt": self._warmup_prompt`), so a None prompt
    sends `{"prompt": null}` and misreports model readiness. `_ab_config` and
    `_rollout_manager` must start as None — not the empty string the mutants
    write — because get_ab_config()/get_rollout_manager() test them with
    `is not None` before delegating to the global singleton.
    """
    a, _logs = constructed()
    assert a._is_warming is False
    assert a._warmup_prompt == WARMUP_PROMPT
    assert a._ab_config is None
    assert a._rollout_manager is None


# ==========================================================================
# NemotronAnalyzer.calculate_batch_priority  (8 keys)
# ==========================================================================


def _priority_analyzer(high_labels=("weapon", "intruder", "fire")) -> tuple:
    """__new__-built analyzer carrying only the two attributes the method reads."""
    a = nem.NemotronAnalyzer.__new__(nem.NemotronAnalyzer)
    a._priority_high_labels = frozenset(high_labels)
    coalescer = create_autospec(BatchCoalescer, instance=True)
    coalescer.calculate_priority.return_value = Priority.P2_NORMAL
    a._batch_coalescer = coalescer
    return a, coalescer


def test_batch_priority_known_face_short_circuits_before_any_label_logic():
    """No key in this chunk sits on this guard (:670-671) — this is the
    counterfactual that keeps the delegation-arm assertions in the other two
    tests meaningful: shipped returns P3_LOW for a household face BEFORE
    lower-casing labels or consulting the coalescer, which is NEM-5464's
    "household members never queue ahead of strangers" rule.
    """
    a, coalescer = _priority_analyzer()
    got = a.calculate_batch_priority(["person"], time_of_day="night", is_known_face=True)
    assert got is Priority.P3_LOW
    coalescer.calculate_priority.assert_not_called()


def test_batch_priority_configured_high_label_wins_over_coalescer():
    """Kills calculate_batch_priority mutmut_2 and mutmut_3.

    _2 (`t.lower()` -> `t.upper()` at :675): the configured label set is
    lower-cased, so upper-casing the detections empties the intersection and a
    reported WEAPON falls through to the coalescer's P2 default.
    _3 (`types_lower & self._priority_high_labels` -> `types_lower | ...` at
    :677): a non-empty union is always truthy, so EVERY batch — a known
    delivery van included — claims P0_CRITICAL and the priority queue
    degenerates to FIFO. Both arms pinned: matching label -> P0 without
    touching the coalescer; non-matching label -> delegation.
    """
    a, coalescer = _priority_analyzer()
    assert a.calculate_batch_priority(["WEAPON"]) is Priority.P0_CRITICAL
    coalescer.calculate_priority.assert_not_called()
    assert a.calculate_batch_priority(["package"]) is Priority.P2_NORMAL
    assert coalescer.calculate_priority.call_count == 1


def test_batch_priority_delegates_confidence_and_context_to_coalescer():
    """Kills calculate_batch_priority mutmut_6, mutmut_7, mutmut_8, mutmut_11,
    mutmut_12, mutmut_13.

    The delegation contract is the full four-kwarg call
    `calculate_priority(object_types=..., confidence=0.5, time_of_day=...,
    is_known_face=...)` (:683-688) against the shipped signature
    `calculate_priority(self, object_types, confidence, time_of_day="day",
    is_known_face=False)` (backend/services/batch_coalescer.py:334-340) — so a
    dropped keyword silently re-reads as a default instead of raising: _6
    confidence=None and _13 confidence=1.5 (the reserved confidence slot fed a
    non-float / an out-of-domain score), _7/_11 time_of_day=None or dropped
    (the coalescer's night rule keys off `time_of_day == "night"`, so a night
    intrusion is demoted to daytime handling) and _8/_12 is_known_face=None or
    dropped (None is falsy, so the coalescer's own P3_LOW guard at :359 stops
    firing). The autospec coalescer's recorded kwargs are the only channel these
    six shapes have, so they are asserted exactly.
    """
    a, coalescer = _priority_analyzer(high_labels=())
    got = a.calculate_batch_priority(["package"], time_of_day="night", is_known_face=False)
    assert got is Priority.P2_NORMAL
    coalescer.calculate_priority.assert_called_once_with(
        object_types=["package"],
        confidence=0.5,
        time_of_day="night",
        is_known_face=False,
    )


# ==========================================================================
# NemotronAnalyzer._build_ondemand_enrichment_context  (20 keys)
# ==========================================================================

AGE_EMPTY = "Age estimation: No persons analyzed"
GENDER_EMPTY = "Gender estimation: No persons analyzed"
AGE_RICH = "Age estimation (1 persons):\n  Person 1: adult (80%)"
GENDER_RICH = "Gender estimation (1 persons):\n  Person 1: male (80%)"
OCR_RICH = '{"scene_text": [{"value": "FEDEX"}]}'
SF_RICH = "Smoke detected near the loading dock"
SF_NONE_TEXT = "No smoke or fire detected"


def ondemand(**overrides) -> str:
    """Call the shipped staticmethod against a real EnrichmentResult.

    Every enrichment data field keeps its real default; only what a test names
    is overridden, so a mutant that reaches an untested branch still runs the
    shipped code against real types.
    """
    result = EnrichmentResult()
    for name, value in overrides.items():
        setattr(result, name, value)
    return nem.NemotronAnalyzer._build_ondemand_enrichment_context(result)


@pytest.fixture
def spies():
    """Autospec-patch the four context formatters and expose call spies.

    The recorded call ARGS are the point: they separate "formatter replaced by
    None" from "formatter called with None" from "formatter called correctly".
    The shipped return values are restored verbatim through the spies so branch
    control stays shipped; `spies.reset()` restores the no-data defaults between
    the two counterfactual runs inside one test.
    """
    age = MagicMock(name="format_age_classification_context")
    gender = MagicMock(name="format_gender_classification_context")
    ocr = MagicMock(name="format_scene_ocr_context")
    smoke = MagicMock(name="format_smoke_fire_context")
    defaults = {age: AGE_EMPTY, gender: GENDER_EMPTY, ocr: "", smoke: SF_NONE_TEXT}

    def reset():
        for mock in (age, gender, ocr, smoke):
            mock.reset_mock()
            mock.return_value = defaults[mock]

    reset()
    bundle = SimpleNamespace(age=age, gender=gender, ocr=ocr, smoke=smoke, reset=reset)
    with (
        patch(
            "backend.services.nemotron_analyzer.format_age_classification_context",
            autospec=True,
            side_effect=age,
        ),
        patch(
            "backend.services.nemotron_analyzer.format_gender_classification_context",
            autospec=True,
            side_effect=gender,
        ),
        patch(
            "backend.services.nemotron_analyzer.format_scene_ocr_context",
            autospec=True,
            side_effect=ocr,
        ),
        patch(
            "backend.services.smoke_fire_loader.format_smoke_fire_context",
            autospec=True,
            side_effect=smoke,
        ),
    ):
        yield bundle


def test_ondemand_context_empty_result_returns_empty_string(spies):
    """Kills _build_ondemand_enrichment_context mutmut_1 and mutmut_19.

    With a default EnrichmentResult (no smoke/fire, no persons, no OCR) shipped
    returns "": `sections` starts as [] (:3765), every branch is skipped and
    `"\n\n".join([])` is "". _1 (`sections = None`) blows up the moment any
    branch appends and, on this input, at the join; _19 (`join(None)`) raises
    TypeError at the return even with no sections at all. The return value is
    prompt-bearing — the caller interpolates it into the Nemotron prompt
    (:4712) — so a raised TypeError fails the whole analysis path. The spy
    asserts additionally pin the shipped unconditional formatter calls.
    """
    assert ondemand() == ""
    spies.age.assert_called_once_with({})
    spies.gender.assert_called_once_with({})
    spies.ocr.assert_called_once_with(None)
    spies.smoke.assert_not_called()


def test_ondemand_context_sections_join_with_double_newline(spies):
    """Kills _build_ondemand_enrichment_context mutmut_20.

    The section separator is exactly "\n\n" (:3809); the "XX\n\nXX" mutant
    injects literal X characters into the assembled prompt context. Three
    sections are assembled so both join seams are exercised, and the shipped
    section ORDER (age, gender, then OCR) is part of the pinned string.
    """
    spies.age.return_value = AGE_RICH
    spies.gender.return_value = GENDER_RICH
    spies.ocr.return_value = OCR_RICH
    assert ondemand() == (
        f"### Age Estimation\n{AGE_RICH}\n\n"
        f"### Gender Estimation\n{GENDER_RICH}\n\n"
        f"### Scene Text (OCR)\n{OCR_RICH}"
    )


def test_ondemand_context_age_section_gated_on_the_no_persons_sentinel(spies):
    """Kills _build_ondemand_enrichment_context mutmut_3, 4, 5, 6, 7, 8, 9.

    The age block is appended only when the formatter produced real content:
    `if age_text and age_text != "Age estimation: No persons analyzed"`
    (:3777-3778). _3 replaces the call with None (content case loses its
    section), _4 calls the formatter with None instead of
    enrichment_result.age_classifications (pinned by the spy args), _5's `or`
    admits the empty/placeholder string, _6's `==` inverts the gate, and
    _7/_8/_9 mutate the sentinel literal (XX-wrapped / lowercase / uppercase)
    so it stops matching the formatter's real no-op string. Both directions are
    pinned: real content -> exactly the age section; the shipped placeholder ->
    empty string. In the second run _5/_6/_7/_8/_9 all append the boilerplate,
    which would tell the LLM "no persons analyzed" as if it were evidence.
    """
    spies.age.return_value = AGE_RICH
    assert ondemand() == f"### Age Estimation\n{AGE_RICH}"
    spies.age.assert_called_once_with({})
    spies.reset()
    spies.age.return_value = AGE_EMPTY
    assert ondemand() == ""
    spies.age.assert_called_once_with({})


def test_ondemand_context_gender_section_gated_on_the_no_persons_sentinel(spies):
    """Kills _build_ondemand_enrichment_context mutmut_10, 11, 12, 13, 14,
    15, 16.

    Gender mirrors the age gate (:3826-3827): `if gender_text and gender_text !=
    "Gender estimation: No persons analyzed"`. _10 replaces the call with None,
    _11 passes None instead of enrichment_result.gender_classifications (spy
    args), _12's `or` admits the placeholder, _13's `==` inverts the gate, and
    _14/_15/_16 break the sentinel literal. Same two-directional pin as age.
    """
    spies.gender.return_value = GENDER_RICH
    assert ondemand() == f"### Gender Estimation\n{GENDER_RICH}"
    spies.gender.assert_called_once_with({})
    spies.reset()
    spies.gender.return_value = GENDER_EMPTY
    assert ondemand() == ""
    spies.gender.assert_called_once_with({})


def test_ondemand_context_smoke_fire_first_and_ocr_last(spies):
    """Kills _build_ondemand_enrichment_context mutmut_2, mutmut_17,
    mutmut_18.

    _2 inverts `if enrichment_result.smoke_fire_detection is not None:`
    (:3768): with a real smoke/fire result the guard skips the SAFETY-CRITICAL
    block (a fire vanishes from the prompt) and with none present it calls the
    loader with None. _17 replaces the OCR formatter call with None — the
    `if ocr_text:` guard is then falsy and the OCR section silently disappears
    — and _18 calls format_scene_ocr_context(None) instead of
    enrichment_result.scene_ocr. The shipped section text, the smoke-fire-first
    ordering and both spy call-argument lists are pinned.
    """
    smoke = {"detections": [{"type": "smoke", "confidence": 0.9}]}
    ocr_result = object()
    spies.smoke.return_value = SF_RICH
    spies.ocr.return_value = OCR_RICH
    assert ondemand(smoke_fire_detection=smoke, scene_ocr=ocr_result) == (
        f"### Smoke/Fire Detection\n{SF_RICH}\n\n### Scene Text (OCR)\n{OCR_RICH}"
    )
    spies.smoke.assert_called_once_with(smoke, time_of_day=None)
    spies.ocr.assert_called_once_with(ocr_result)


# ==========================================================================
# NemotronAnalyzer._run_enrichment_pipeline_from_data  (17 keys)
# ==========================================================================

TRACKING = object()
DET_FULL = {
    "id": 7,
    "object_type": "person",
    "bounding_box": {"x": 10.0, "y": 20.0, "width": 30.0, "height": 40.0},
    "confidence": 0.9,
    "video_width": 1920,
    "video_height": 1080,
    "image_path": "/img/7.jpg",
}
# A detection with a well-formed bounding box but NO object_type: it passes the
# bbox type checks below, so a guard mutation lets it reach DetectionInput
# (which accepts class_name=None — probe) instead of skipping it.
DET_NO_TYPE = {"id": 9, "bounding_box": [0.0, 0.0, 5.0, 5.0]}
EXPECTED_INPUTS = [
    DetectionInput(
        id=7,
        class_name="person",
        confidence=0.9,
        bbox=BoundingBox(x1=10.0, y1=20.0, x2=40.0, y2=60.0),
        video_width=1920,
        video_height=1080,
    )
]
EXPECTED_IMAGES = {7: "/img/7.jpg", None: "/img/7.jpg"}


async def run_pipeline(detections):
    """Drive the shipped coroutine against an autospec pipeline stand-in."""
    analyzer = nem.NemotronAnalyzer.__new__(nem.NemotronAnalyzer)
    pipeline = create_autospec(EnrichmentPipeline, instance=True)
    pipeline.enrich_batch_with_tracking = AsyncMock(return_value=TRACKING)
    with patch.object(analyzer, "_get_enrichment_pipeline", autospec=True, return_value=pipeline):
        result = await analyzer._run_enrichment_pipeline_from_data(detections, camera_id="cam-7")
    return result, pipeline


@pytest.mark.asyncio
async def test_run_enrichment_from_data_empty_input_short_circuits():
    """Kills no key directly — the counterfactual that pins WHERE the pipeline
    call may never happen; mutmut_1's observable difference lives on the
    non-empty path and is claimed by
    test_run_enrichment_from_data_maps_detections_and_images.

    `if not detections_data: return None` (:2228-2229) is the documented no-op
    ("or None if no enrichment was needed"). Under _1 the empty batch still
    returns None here (via the second guard), so the mutant is invisible to
    this input — which is exactly why the happy-path test drives a real batch
    and pins the delegation.
    """
    result, pipeline = await run_pipeline([])
    assert result is None
    assert pipeline.enrich_batch_with_tracking.await_count == 0


@pytest.mark.asyncio
async def test_run_enrichment_from_data_maps_detections_and_images():
    """Kills _run_enrichment_pipeline_from_data mutmut_1, 2, 3, 4, 5, 6, 7, 8,
    9, 10, 11, 12, 17.

    _1 (`if not detections_data:` -> `if detections_data:`) is only visible on
    NON-empty input: the inverted guard returns None immediately for a real
    batch, so this happy path fails its TRACKING assert while the empty-input
    test above passes (the two together pin the guard's exact truth table).

    One happy-path run pins the whole mapping: `pipeline =
    self._get_enrichment_pipeline()` (_2 -> None dies at the await), the two
    accumulators `detection_inputs = []` / `images = {}` (_3/_4 -> None explode
    on the first append / subscript assignment), and all four `.get()` key
    shapes on the two required fields — `bbox = det_data.get("bounding_box")`
    (_5 None, _6 None-key, _7 "XXbounding_boxXX", _8 "BOUNDING_BOX") and
    `object_type = det_data.get("object_type")` (_9-_12 likewise) — each of
    which reads None and therefore skips the only valid detection, collapsing
    the result to None. _17 (`if detection_inputs:` -> return None) drops the
    result of the very call below. The autospec pipeline's recorded arguments
    are shipped-exact: one DetectionInput whose x2/y2 corners are bbox origin +
    width/height (pinning the field-by-field dict extraction), the per-detection
    image plus the None-keyed full-frame image, and camera_id="cam-7".
    """
    result, pipeline = await run_pipeline([DET_FULL])
    assert result is TRACKING
    call = pipeline.enrich_batch_with_tracking.await_args
    assert call.args[0] == EXPECTED_INPUTS
    assert call.args[1] == EXPECTED_IMAGES
    assert call.kwargs == {"camera_id": "cam-7"}


@pytest.mark.asyncio
async def test_run_enrichment_from_data_skips_incomplete_detection_and_continues():
    """Kills _run_enrichment_pipeline_from_data mutmut_13, mutmut_14,
    mutmut_15, mutmut_16.

    `if bbox is None or object_type is None: continue` (:2244-2245) skips a
    detection that cannot be enriched and keeps scanning. _13 (`and`) stops
    skipping a type-less entry whose bbox is well-formed, so it reaches
    DetectionInput with class_name=None and pollutes the batch (2 inputs where
    shipped produces 1); _14 (`bbox is not None or ...`) skips essentially
    everything, including the valid detection; _15 (`... or object_type is not
    None`) keeps the unusable entry and drops the valid one; _16 (`continue` ->
    `break`) abandons the scan at the first incomplete entry and loses every
    valid detection after it. All four land on a batch that is either empty
    (result None) or wrongly composed — both asserted against the shipped
    single-input call.
    """
    result, pipeline = await run_pipeline([DET_NO_TYPE, DET_FULL])
    assert result is TRACKING
    call = pipeline.enrich_batch_with_tracking.await_args
    assert call.args[0] == EXPECTED_INPUTS
    # shipped: images[None] is only set from detections_data[0]'s image, and
    # the (skipped) first entry has none — so only the per-detection entry
    # exists. A mutant that keeps DET_NO_TYPE changes args[0] above anyway.
    assert call.args[1] == {7: "/img/7.jpg"}


@pytest.mark.asyncio
async def test_run_enrichment_from_data_all_incomplete_returns_none():
    """No exclusive key claim — this is the second-side counterfactual of
    mutmut_17/_13/_15, whose kills are owned by
    test_run_enrichment_from_data_maps_detections_and_images (_17) and
    test_run_enrichment_from_data_skips_incomplete_detection_and_continues
    (_13/_15).

    A batch whose only entry lacks object_type yields no inputs, and shipped
    returns None WITHOUT touching the pipeline (:2308-2309): _17's inverted
    guard hands the empty list to enrich_batch_with_tracking here, and
    _13/_15's un-skipped entry reaches the pipeline as a class_name=None input.
    """
    result, pipeline = await run_pipeline([DET_NO_TYPE])
    assert result is None
    assert pipeline.enrich_batch_with_tracking.await_count == 0


# ==========================================================================
# NemotronAnalyzer.set_experiment_config  (1 key)
# ==========================================================================


def test_set_experiment_config_logs_the_exact_config_summary():
    """Kills set_experiment_config mutmut_3.

    The INFO record (:904-908) is the audit trail for every prompt-experiment
    rollout — which experiment went live, in shadow mode or not, at what
    treatment split — and the mutant logs the literal "None". Pinned as the
    shipped interpolation of a real PromptExperimentConfig (treatment renders
    through `:.1%` as 30.0%), with the assignment the record documents.
    """
    analyzer = nem.NemotronAnalyzer.__new__(nem.NemotronAnalyzer)
    config = PromptExperimentConfig(
        shadow_mode=True, treatment_percentage=0.3, experiment_name="my-exp"
    )
    recorder, logger, previous = capture_logs()
    try:
        analyzer.set_experiment_config(config)
    finally:
        messages = stop_capture(recorder, logger, previous)
    assert messages.count(MSG_EXPERIMENT) == 1, messages
    assert analyzer._experiment_config is config


# ==========================================================================
# NemotronAnalyzer.get_warmth_state  (5 keys)
# ==========================================================================


def warmth_at(seconds_ago: float, threshold: float = 10.0) -> dict:
    """Report warmth for a last-inference exactly `seconds_ago` in the past."""
    a = nem.NemotronAnalyzer.__new__(nem.NemotronAnalyzer)
    a._is_warming = False
    a._cold_start_threshold = threshold
    a._last_inference_time = 1000.0
    with patch("backend.services.nemotron_analyzer.time.monotonic", autospec=True) as clock:
        clock.return_value = 1000.0 + seconds_ago
        return a.get_warmth_state()


def test_warmth_state_is_cold_only_strictly_past_the_threshold():
    """Kills get_warmth_state mutmut_16, mutmut_17, mutmut_20, mutmut_22,
    mutmut_23.

    The idle branch computes `is_cold = seconds_ago > self._cold_start_threshold`
    (:1418) and returns `{"state": "cold" if is_cold else "warm", ...}` (:1420).
    _17 (`>=`) reports a model idle for exactly the threshold as cold, so the
    boundary is pinned on both sides (threshold-epsilon warm, exactly the
    threshold warm, threshold+epsilon cold). _16 (`is_cold = None`) and _20
    (`(is_cold) and False`) both make every idle model report "warm" — killed by
    the cold assertion below, whose string is read straight out of the returned
    dict; _22 ("XXcoldXX") and _23 ("COLD") mutate that very literal, so the
    same assertion is an exact-string check on it. The whole-dict equality also
    pins `last_inference_seconds_ago` as `time.monotonic() -
    self._last_inference_time`.
    """
    assert warmth_at(5.0, threshold=10.0) == {
        "state": "warm",
        "last_inference_seconds_ago": 5.0,
    }
    assert warmth_at(10.0, threshold=10.0) == {
        "state": "warm",
        "last_inference_seconds_ago": 10.0,
    }
    assert warmth_at(30.0, threshold=10.0) == {
        "state": "cold",
        "last_inference_seconds_ago": 30.0,
    }
