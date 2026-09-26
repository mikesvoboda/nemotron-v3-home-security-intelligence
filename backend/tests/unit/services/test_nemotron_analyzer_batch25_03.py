"""Batch-25 kill battery — chunk "NemotronAnalyzer.analyze_batch#chunk4" (130 keys).

Every key in this chunk is a survivor of
backend/services/nemotron_analyzer.py::NemotronAnalyzer.analyze_batch
(shipped lines 2341-3140). The chunk covers the SESSION-2 (WRITE) region and
the post-session telemetry/log/broadcast/cache tail:

  * junction-table pg_insert(...).on_conflict_do_nothing(index_elements=[...])
  * create_partial_audit(...) + session.add(audit) + "Created audit ..." debug
  * _enqueue_for_evaluation(event.id, event.risk_score or 50)
  * _build_enrichment_snapshot / _build_context_sources / LLMInteraction(...)
  * household_matches comprehensions + the "persons"/"vehicles" payload keys
  * LLMInteraction-failure logger.warning("LLMInteraction creation failed", extra=...)
  * add_span_event("database_write.complete"/"batch_analysis.complete", {...})
  * total_duration_ms/seconds arithmetic + observe_stage_duration + record_event_by_camera
  * the completion log_context(batch_id=..., camera_id=...) + "Batch analysis completed"
  * _broadcast_event(event) and the event-stats cache invalidation (both paths)

Each test drives the SHIPPED analyze_batch end-to-end through an in-memory
harness (mocked session / facade / LLM, REAL Camera+Detection+Event model
objects, deterministic time.time ladder, kwargs-blind log_context copy that
keeps the ContextVar machinery) and pins the shipped observable contract: the
statements handed to session.execute, the request signatures handed to
collaborators, the persisted ids, exact log messages / extras / stamped
log_context fields, and exact span-event + metrics arguments.

Identity pins matter: a NULLed ``enrichment_result=`` or ``detection_ids=``
kwarg is INVISIBLE to value-only comparisons when the pipeline ran without
enrichment (shipped None == None), so every run carries an enrichment SENTINEL
and the kwargs are then asserted by identity.

This file lives OUTSIDE the repo tree, so the repo conftest.py does not apply:
the minimum env vars the repo conftest sets are mirrored below and
pytestmark = pytest.mark.unit is declared. asyncio_mode=auto is not picked up
either, so every async test carries an explicit @pytest.mark.asyncio.
Every mock patch call site carries autospec=True (CI ratchet).
"""

from __future__ import annotations

import contextlib
import datetime as dt
import logging
import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("OTEL_ENABLED", "false")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

import backend.services.nemotron_analyzer as NA
from backend.core.config import Settings
from backend.core.constants import CacheInvalidationReason
from backend.core.logging import _log_context
from backend.core.redis import RedisClient
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.batch_coalescer import Priority

BATCH_ID = "batch-b25-03"
SIBLING_ID = "batch-sib-03"  # coalesced-in sibling batch (coalesce scenario)
CAM_ID = "cam-9"
CAM_NAME = "Front Porch Cam"
EVENT_ID = 4242
AUDIT_ID = 5555
LLMI_ID = 991
DET_IDS = [1, 2]

# Deterministic time.time() ladder consumed by analyze_batch (the module
# attribute `time` is replaced wholesale, so every duration in the tested
# region is exact and therefore mutant-comparable):
#   1 analysis_start          = 1000.0
#   2 llm_start               = 1010.0
#   3 -> llm_duration_ms      = int(2.0  * 1000) = 2000
#   4 -> llm_duration_seconds = 1012.5 - 1010.0  = 2.5   (exact in binary)
#   5 -> total_duration_ms    = int(13.0 * 1000) = 13000
#   6 -> total_duration_seconds = 1013.5 - 1000.0 = 13.5 (exact in binary)
TIMES = [1000.0, 1010.0, 1012.0, 1012.5, 1013.0, 1013.5]
LLM_SECONDS = 2.5
TOTAL_MS = 13000
TOTAL_SECONDS = 13.5

RISK_OK = {
    "risk_score": 75,
    "risk_level": "high",
    "summary": "Suspicious activity at the porch",
    "reasoning": "person loitering",
}  # NO "raw_response" key -> shipped .get("raw_response", "") == ""
RISK_RAW = {**RISK_OK, "raw_response": "RAW-XYZ"}
RISK_ZERO = {**RISK_OK, "risk_score": 0}  # exercises the `or 50` / `or 0` fallbacks

SETTINGS_PATHS = (
    "backend.services.nemotron_analyzer.get_settings",
    "backend.services.severity.get_settings",
    "backend.services.token_counter.get_settings",
    "backend.core.config.get_settings",
    "backend.services.inference_semaphore.get_settings",
)

_COMPLETION_KEYS = ("event_id", "risk_score", "risk_level", "duration_ms", "detection_count")

# (the enrichment sentinel is built after the _Enrich class below)


class _Clock:
    """time-module stand-in replaying a fixed ladder, then 1e9 (far future)."""

    def __init__(self) -> None:
        self._values = list(TIMES)

    def time(self) -> float:
        if self._values:
            return self._values.pop(0)
        return 1e9


class _Audit:
    """duck-typed object returned by create_partial_audit (id stamped on add)."""

    def __init__(self) -> None:
        self.id = None


class _Dumping:
    """household match WITH a model_dump() method (pydantic-style)."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def model_dump(self) -> dict:
        return dict(self.payload)


class _Plain:
    """household match WITHOUT model_dump() — the else-branch of the ternary."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload


class _Enrich:
    """duck-typed EnrichmentResult covering everything analyze_batch touches."""

    license_plates: list = []
    faces: list = []
    weather_classification = None
    pose_results = None
    action_results = None
    smoke_fire_detection = None
    person_reid_matches = None
    vehicle_reid_matches = None

    def __init__(self, person_household_matches=None, vehicle_household_matches=None) -> None:
        self.person_household_matches = person_household_matches
        self.vehicle_household_matches = vehicle_household_matches

    def to_storage_dict(self, det_id):  # falsy -> enrichment_data_map stays empty
        return None


# Single enrichment sentinel: a plain object whose identity every NULLed
# enrichment_result kwarg must fail (shipped sends this object, mutants send
# None). Its inline attribute reads (to_storage_dict, household matches,
# smoke_fire_detection) are all inert.
_sentinel = _Enrich()


class LogCapture:
    """caplog-shaped capture usable under pytest and from the out-of-repo driver."""

    def __init__(self) -> None:
        self.records: list[logging.LogRecord] = []
        self._handler: logging.Handler | None = None
        self._logger: logging.Logger | None = None

    def set_level(self, level: int, logger: str | None = None) -> None:
        self._logger = logging.getLogger(logger)
        self._logger.setLevel(level)

    def attach(self) -> None:
        outer = self

        class _H(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                outer.records.append(record)

        self._handler = _H()
        assert self._logger is not None
        self._logger.addHandler(self._handler)
        self._logger.setLevel(logging.DEBUG)

    def detach(self) -> None:
        if self._handler is not None and self._logger is not None:
            self._logger.removeHandler(self._handler)
            self._handler = None


def _make_settings() -> MagicMock:
    settings = MagicMock(spec=Settings)
    # P0.3 flags (#6678): pydantic v2 field names are not in
    # dir(Settings), so a spec'd mock must pin them explicitly.
    settings.nemotron_constrained_decoding_enabled = False
    settings.nemotron_constrained_fail_closed = True
    settings.nemotron_constrained_probe_enabled = True
    settings.nemotron_constrained_probe_required_build = None
    settings.nemotron_verification_engine = "llama.cpp"
    settings.nemotron_model_id = "Nemotron-3-Nano-30B-A3B-Q4_K_M"
    settings.nemotron_url = "http://localhost:8091"
    settings.nemotron_api_key = None
    settings.ai_connect_timeout = 10.0
    settings.nemotron_read_timeout = 120.0
    settings.ai_health_timeout = 5.0
    settings.nemotron_max_retries = 1
    settings.severity_low_max = 29
    settings.severity_medium_max = 59
    settings.severity_high_max = 84
    settings.nemotron_context_window = 4096
    settings.nemotron_max_output_tokens = 1536
    settings.context_utilization_warning_threshold = 0.80
    settings.context_truncation_enabled = True
    settings.llm_tokenizer_encoding = "cl100k_base"
    settings.image_quality_enabled = False
    settings.ai_warmup_enabled = False
    settings.ai_cold_start_threshold_seconds = 300.0
    settings.nemotron_warmup_prompt = "Test warmup prompt"
    settings.scene_change_resize_width = 640
    settings.use_enrichment_service = False
    settings.ai_max_concurrent_inferences = 4
    settings.nemotron_use_guided_json = False
    settings.nemotron_guided_json_fallback = True
    settings.batch_coalescing_enabled = False
    settings.batch_coalescing_max_size = 10
    settings.batch_coalescing_time_window = 5.0
    settings.priority_queue_enabled = False
    settings.priority_high_labels = ["weapon", "intruder", "fire"]
    settings.priority_medium_labels = ["person", "unknown"]
    return settings


def _reset_singletons() -> None:
    from backend.services.analyzer_facade import reset_analyzer_facade
    from backend.services.inference_semaphore import reset_inference_semaphore
    from backend.services.severity import reset_severity_service
    from backend.services.token_counter import reset_token_counter

    reset_severity_service()
    reset_token_counter()
    reset_analyzer_facade()
    reset_inference_semaphore()


def _camera() -> Camera:
    return Camera(id=CAM_ID, name=CAM_NAME, folder_path="/export/foscam/cam-9", status="online")


def _detections() -> list[Detection]:
    base = dt.datetime(2025, 12, 23, 14, 30, 0, tzinfo=dt.UTC)
    return [
        Detection(
            id=1,
            camera_id=CAM_ID,
            file_path="/export/foscam/cam-9/img1.jpg",
            detected_at=base,
            object_type="person",
            confidence=0.95,
        ),
        Detection(
            id=2,
            camera_id=CAM_ID,
            file_path="/export/foscam/cam-9/img2.jpg",
            detected_at=base + dt.timedelta(seconds=15),
            object_type="car",
            confidence=0.88,
        ),
    ]


@contextlib.contextmanager
def _passthru_log_context(**kwargs):
    """Shipped log_context MINUS the inheritance merge (ContextVar kept).

    backend/core/logging.py:304-315 merges kwargs INTO the current context, so
    an outer context leaks batch_id/camera_id onto every inner record and a
    dropped kwarg at one call site is invisible. This copy keeps the set/reset
    (records are stamped, or left absent, per shipped ContextFilter semantics
    at backend/core/logging.py:592-597) but starts the context FRESH from the
    call's own kwargs: a batch_id=/camera_id= argument dropped, added, or
    NULLed at the completion call site therefore shows up as a MISSING/None
    stamped attribute on that one record.
    """
    token = _log_context.set(dict(kwargs))
    try:
        yield
    finally:
        _log_context.reset(token)


def new_facts() -> dict:
    return {
        "session2_stmts": [],
        "audit_calls": [],
        "audit_added_ids": [],
        "audit_warnings": [],
        "eval_calls": [],
        "snapshot_calls": [],
        "ctxsrc_calls": [],
        "llmi_calls": [],
        "llmi_warnings": [],
        "span_events": [],
        "stage_calls": [],
        "camera_calls": [],
        "ai_dur_calls": [],
        "broadcast_args": [],
        "cache_calls": [],
        "cache_warnings": [],
        "audit_debugs": [],
        "llmi_debugs": [],
        "completion": [],
        "noop1": [],
        "noop2": [],
        "noop3": [],
        "redis_set": [],
        "event": None,
        "raised": None,
    }


async def drive(
    target, call, cap, *, enrich, risk, llmi_raises=None, cache_raises=None, coalesce=False
):
    """Run ``call(analyzer)`` against the code in ``target`` inside the harness.

    target: module whose globals the analyzed function resolves against — the
            shipped module in tests, a variant namespace module in red-checks.
    call:   callable(analyzer) -> awaitable.
    cap:    pytest caplog or a LogCapture.
    enrich: enrichment sentinel object, or False for "no enrichment data".
    coalesce: True enables batch coalescing (sibling batch merged into this one).
    """
    facts = new_facts()
    risk = dict(risk)
    state = {"execs": 0}
    enrich_obj = None if enrich is False else enrich
    before = len(cap.records)

    with contextlib.ExitStack() as st:
        settings = _make_settings()
        settings.batch_coalescing_enabled = coalesce
        for path in SETTINGS_PATHS:
            st.enter_context(patch(path, return_value=settings, autospec=True))
        redis = MagicMock(spec=RedisClient)
        redis.get = AsyncMock(return_value=None)  # idempotency miss on every key
        redis.set = AsyncMock(side_effect=lambda *a, **k: facts["redis_set"].append((a, k)) or True)
        redis.delete = AsyncMock(return_value=1)
        redis.publish = AsyncMock(return_value=1)
        _reset_singletons()
        st.callback(_reset_singletons)
        an = NA.NemotronAnalyzer(redis_client=redis)

        # ---- deterministic clock (module-global rebinding: no signature) ---
        clock = _Clock()
        _saved_time = target.time
        target.time = clock
        st.callback(setattr, target, "time", _saved_time)

        # ---- metrics / telemetry recorders (autospec'd module functions) ---
        def _rec(key):
            def _f(*a, **k):
                facts[key].append((a, k))

            return _f

        def _arec(key, raises=None):
            async def _f(*a, **k):
                if raises is None:
                    facts[key].append((a, k))
                else:
                    raise raises

            return _f

        def _span(name, attributes=None, **kw):
            facts["span_events"].append((name, attributes))

        st.enter_context(patch.object(target, "add_span_event", autospec=True, side_effect=_span))
        for name, key in (
            ("observe_stage_duration", "stage_calls"),
            ("record_event_by_camera", "camera_calls"),
            ("observe_ai_request_duration", "ai_dur_calls"),
            ("record_event_created", "noop1"),
            ("record_pipeline_error", "noop2"),
            ("record_batch_coalesce_llm_calls_saved", "noop3"),
        ):
            st.enter_context(patch.object(target, name, autospec=True, side_effect=_rec(key)))
        st.enter_context(
            patch.object(target, "log_context", autospec=True, side_effect=_passthru_log_context)
        )

        def _ctor(**kwargs):
            facts["llmi_calls"].append(dict(kwargs))
            if llmi_raises is not None:
                raise llmi_raises
            row = MagicMock(name="llm_interaction_row")
            row.id = LLMI_ID
            return row

        st.enter_context(patch.object(target, "LLMInteraction", autospec=True, side_effect=_ctor))

        # ---- session (session 1 + session 2 share one mock session) --------
        camera_obj = _camera()

        async def _execute(stmt):
            state["execs"] += 1
            if state["execs"] == 1:  # session 1: camera select
                res = MagicMock(name="camera_result")
                res.scalar_one_or_none.return_value = camera_obj
                return res
            facts["session2_stmts"].append(stmt)
            return MagicMock(name="exec_result")

        def _add(obj):
            if isinstance(obj, Event):
                obj.id = EVENT_ID
            elif isinstance(obj, _Audit):
                obj.id = AUDIT_ID
                facts["audit_added_ids"].append(AUDIT_ID)

        session = MagicMock(name="session")
        session.execute = AsyncMock(side_effect=_execute)
        session.add = MagicMock(side_effect=_add)
        session.flush = AsyncMock()
        session.commit = AsyncMock()

        sess_ctx = AsyncMock()
        sess_ctx.__aenter__.return_value = session
        sess_ctx.__aexit__.return_value = None
        gs = st.enter_context(patch.object(target, "get_session", autospec=True))
        gs.return_value = sess_ctx

        # ---- facade + audit service -----------------------------------------
        cache = MagicMock(name="cache_service")
        cache.invalidate_event_stats = AsyncMock(side_effect=_arec("cache_calls", cache_raises))
        facade = MagicMock(name="facade")
        if coalesce:
            # session 1 returns the batch detections; the coalesce re-fetch
            # (new detection ids only) returns none — enough for the shipped
            # marker loop over coalesced_batch_ids to run
            facade.fetch_detections = AsyncMock(side_effect=[_detections(), []])
        else:
            facade.fetch_detections = AsyncMock(return_value=_detections())
        tuner = MagicMock(name="tuner")
        tuner.get_tuning_context = AsyncMock(return_value="")
        facade.get_prompt_auto_tuner = MagicMock(return_value=tuner)
        facade.get_cache_service = AsyncMock(return_value=cache)
        an._facade = facade

        audit_service = MagicMock(name="audit_service")

        def _mk_audit(*args, **kwargs):
            facts["audit_calls"].append((args, kwargs))
            return _Audit()

        audit_service.create_partial_audit = MagicMock(side_effect=_mk_audit)
        st.enter_context(
            patch(
                "backend.services.pipeline_quality_audit_service.get_audit_service",
                autospec=True,
                return_value=audit_service,
            )
        )

        # ---- analyzer-internal seams (side_effect keeps autospec binding) --
        tracking = MagicMock(name="tracking")
        tracking.has_data = enrich_obj is not None
        tracking.data = enrich_obj

        for name, kwargs in (
            ("_call_llm", {"return_value": risk}),
            ("_get_enriched_context", {"return_value": None}),
            ("_get_recent_scene_changes", {"return_value": []}),
            ("_get_enrichment_result_from_data", {"return_value": tracking}),
            ("_get_household_context", {"return_value": ""}),
            ("_enrich_with_trajectory_analysis", {"return_value": None}),
            ("_trigger_event_created_webhook", {}),
            ("_enqueue_for_evaluation", {"side_effect": _arec("eval_calls")}),
            ("_broadcast_event", {"side_effect": _arec("broadcast_args")}),
        ):
            st.enter_context(patch.object(an, name, autospec=True, side_effect=AsyncMock(**kwargs)))
        # shipped-sync seams: side_effect must return the value, not a coroutine
        for name, kwargs in (
            ("calculate_batch_priority", {"return_value": Priority.P2_NORMAL}),
            ("_format_detections", {"return_value": "formatted-detections"}),
        ):
            st.enter_context(patch.object(an, name, autospec=True, side_effect=MagicMock(**kwargs)))

        if coalesce:
            # shipped coalescing path: this batch merges a sibling batch whose
            # extra detection joins the analysis; coalesced_batch_ids then
            # carries an id OTHER than batch_id, which is what makes the
            # `if coalesced_id != batch_id` marker loop observable.
            st.enter_context(
                patch.object(
                    an,
                    "register_coalesce_candidate",
                    autospec=True,
                    side_effect=AsyncMock(return_value=MagicMock(name="candidate")),
                )
            )
            st.enter_context(
                patch.object(
                    an,
                    "try_coalesce_batch",
                    autospec=True,
                    side_effect=AsyncMock(return_value=([*DET_IDS, 3], [BATCH_ID, SIBLING_ID])),
                )
            )

        # instance-level autospec patches bind self, so side_effects see only
        # the call's own args/kwargs (no leading self).
        def _snapshot(*a, **kw):
            assert not a, f"snapshot call gained positionals: {a}"
            facts["snapshot_calls"].append(((), dict(kw)))
            return {"snapshot": True}

        def _ctxsrc(*a, **kw):
            assert not a, f"context-sources call gained positionals: {a}"
            facts["ctxsrc_calls"].append(((), dict(kw)))
            return {"context_available": False}

        st.enter_context(
            patch.object(an, "_build_enrichment_snapshot", autospec=True, side_effect=_snapshot)
        )
        st.enter_context(
            patch.object(an, "_build_context_sources", autospec=True, side_effect=_ctxsrc)
        )

        # ---- run ------------------------------------------------------------
        cap.set_level(logging.DEBUG, logger="backend.services.nemotron_analyzer")
        if isinstance(cap, LogCapture):
            cap.attach()
        try:
            try:
                facts["event"] = await call(an)
            except Exception as exc:  # recorded, asserted where relevant
                facts["raised"] = exc
        finally:
            if isinstance(cap, LogCapture):
                cap.detach()

        for rec in cap.records[before:]:
            msg = rec.getMessage()
            if msg.startswith("Created audit "):
                facts["audit_debugs"].append((msg, rec.levelno))
            elif msg.startswith("Created LLMInteraction "):
                facts["llmi_debugs"].append((msg, rec.levelno))
            elif msg.startswith("Audit log write failed"):
                facts["audit_warnings"].append((msg, rec.levelno))
            elif msg.startswith("LLMInteraction creation failed"):
                facts["llmi_warnings"].append(
                    (
                        msg,
                        rec.levelno,
                        {
                            k: getattr(rec, k, "<MISSING>")
                            for k in (
                                "action",
                                "resource_id",
                                "resource_type",
                                "error_type",
                                "error_message",
                            )
                        },
                    )
                )
            elif msg.startswith("Failed to invalidate event stats cache"):
                facts["cache_warnings"].append(
                    (msg, rec.levelno, getattr(rec, "error", "<MISSING>"))
                )
            elif msg.startswith("Batch analysis completed"):
                facts["completion"].append(
                    (
                        msg,
                        rec.levelno,
                        {k: getattr(rec, k, "<MISSING>") for k in _COMPLETION_KEYS},
                        getattr(rec, "batch_id", "<MISSING>"),
                        getattr(rec, "camera_id", "<MISSING>"),
                    )
                )
    return facts


# ---------------------------------------------------------------------------
# assertion helpers — shared verbatim by the tests and the out-of-repo driver
# ---------------------------------------------------------------------------


def check_T1(f):
    """session 2 hands a real compiled statement (never None) to execute()."""
    assert f["raised"] is None, f"analyze_batch raised {f['raised']!r}"
    assert f["event"] is not None and f["event"].batch_id == BATCH_ID
    assert f["session2_stmts"], "session 2 must execute the junction upsert"
    assert all(s is not None for s in f["session2_stmts"]), (
        f"session.execute() must keep its statement argument: {f['session2_stmts']}"
    )
    assert any(getattr(s, "_post_values_clause", None) is not None for s in f["session2_stmts"]), (
        f"junction upsert lost its ON CONFLICT clause: "
        f"{[type(s).__name__ for s in f['session2_stmts']]}"
    )


def check_T2(f):
    """on_conflict_do_nothing keeps the exact composite conflict target."""
    targets = [
        s._post_values_clause.inferred_target_elements
        for s in f["session2_stmts"]
        if getattr(s, "_post_values_clause", None) is not None
    ]
    assert targets == [["event_id", "detection_id"]], f"ON CONFLICT target mutated: {targets}"


def check_T3(f):
    """create_partial_audit keeps its shipped 4-kwarg request signature."""
    assert f["audit_warnings"] == [], f"audit path diverted into the handler: {f['audit_warnings']}"
    assert len(f["audit_calls"]) == 1, f"expected one audit call, got {f['audit_calls']}"
    args, kwargs = f["audit_calls"][0]
    assert args == (), f"unexpected positional args: {args}"
    assert set(kwargs) == {"event_id", "llm_prompt", "enriched_context", "enrichment_result"}, (
        f"request kwargs mutated: {sorted(kwargs)}"
    )
    assert kwargs["event_id"] == EVENT_ID, f"event_id kwarg mutated: {kwargs['event_id']!r}"
    assert kwargs["llm_prompt"] is None
    assert kwargs["enriched_context"] is None
    assert kwargs["enrichment_result"] is f["_enrich"], (
        f"enrichment_result kwarg mutated: {kwargs['enrichment_result']!r}"
    )


def check_T4(f):
    """the audit row is added, and the shipped debug line names both ids."""
    assert f["audit_added_ids"] == [AUDIT_ID], f"audit add mutated: {f['audit_added_ids']}"
    assert f["audit_debugs"] == [
        (f"Created audit {AUDIT_ID} for event {EVENT_ID}", logging.DEBUG)
    ], f"audit debug record mutated: {f['audit_debugs']}"


def check_T5(f, expected_second):
    """_enqueue_for_evaluation(event.id, event.risk_score if not None else
    P03_UNVERIFIED_PRIORITY) contract (#6678 P0.3 replaced the `or 50`)."""
    assert len(f["eval_calls"]) == 1, f"expected one enqueue call, got {f['eval_calls']}"
    args = f["eval_calls"][0][0]
    assert len(args) >= 2, f"call lost an argument: {args}"
    assert args[-2] == EVENT_ID, f"event_id argument mutated: {args[-2]!r}"
    assert args[-1] == expected_second, f"risk-score argument mutated: {args[-1]!r}"


def check_T6(f):
    """snapshot / context-source / LLMInteraction request signatures."""
    assert f["llmi_warnings"] == [], f"LLMInteraction path diverted: {f['llmi_warnings']}"
    assert len(f["snapshot_calls"]) == 1 and len(f["ctxsrc_calls"]) == 1
    skw = f["snapshot_calls"][0][1]
    assert set(skw) == {"detection_ids", "enrichment_result", "enriched_context"}, (
        f"snapshot kwargs mutated: {sorted(skw)}"
    )
    assert skw["detection_ids"] == DET_IDS, f"detection_ids kwarg mutated: {skw['detection_ids']!r}"
    assert skw["enrichment_result"] is f["_enrich"], (
        f"snapshot enrichment_result mutated: {skw['enrichment_result']!r}"
    )
    ckw = f["ctxsrc_calls"][0][1]
    assert set(ckw) == {"enrichment_result", "enriched_context"}, f"ctx-src kwargs: {sorted(ckw)}"
    assert ckw["enrichment_result"] is f["_enrich"], (
        f"context-sources enrichment_result mutated: {ckw['enrichment_result']!r}"
    )

    assert len(f["llmi_calls"]) == 1, f"LLMInteraction attempts: {f['llmi_calls']}"
    kw = f["llmi_calls"][0]
    assert set(kw) == {
        "event_id",
        "raw_response",
        "enrichment_snapshot",
        "household_matches",
        "context_sources",
    }, f"LLMInteraction kwargs mutated: {sorted(kw)}"
    assert kw["event_id"] == EVENT_ID, f"LLMInteraction event_id mutated: {kw['event_id']!r}"
    assert kw["raw_response"] == f["_raw_expected"], (
        f"raw_response default mutated: {kw['raw_response']!r}"
    )
    assert kw["household_matches"] == f["_household_expected"], (
        f"household_matches default mutated: {kw['household_matches']!r}"
    )
    assert f["llmi_debugs"] == [
        (f"Created LLMInteraction {LLMI_ID} for event {EVENT_ID}", logging.DEBUG)
    ], f"success-path debug record mutated: {f['llmi_debugs']}"


def check_T7(f):
    """household payload keeps both keys and both branches of the dump ternary."""
    assert len(f["llmi_calls"]) == 1, f"LLMInteraction attempts: {f['llmi_calls']}"
    assert "household_matches" in f["llmi_calls"][0], "household_matches kwarg dropped"
    hh = f["llmi_calls"][0]["household_matches"]
    assert isinstance(hh, dict) and set(hh) == {"persons", "vehicles"}, (
        f"household payload keys mutated: {hh!r}"
    )
    assert len(hh["persons"]) == 2 and len(hh["vehicles"]) == 1, (
        f"household payload lengths mutated: {hh!r}"
    )
    assert hh["persons"][0] == {"det": 1, "score": 0.9}, (
        f"dumped person mutated: {hh['persons'][0]!r}"
    )
    assert hh["persons"][1] is f["_plain_obj"], (
        f"else-branch person must pass through unchanged: {hh['persons'][1]!r}"
    )
    assert hh["vehicles"] == [{"vid": 7}], f"vehicles payload mutated: {hh['vehicles']}"
    assert f["_dump_calls"] == 1, f"model_dump() call count mutated: {f['_dump_calls']}"


def check_T8(f):
    """LLMInteraction-failure warning keeps message + all five extra fields."""
    assert len(f["llmi_calls"]) == 1, f"LLMInteraction attempts: {f['llmi_calls']}"
    assert set(f["llmi_calls"][0]) == {
        "event_id",
        "raw_response",
        "enrichment_snapshot",
        "household_matches",
        "context_sources",
    }, f"LLMInteraction kwargs mutated: {sorted(f['llmi_calls'][0])}"
    assert f["llmi_calls"][0]["event_id"] == EVENT_ID
    assert f["event"] is not None, "analysis must complete past the failure"
    assert f["llmi_warnings"] == [
        (
            "LLMInteraction creation failed",
            logging.WARNING,
            {
                "action": "create_llm_interaction",
                "resource_id": str(EVENT_ID),
                "resource_type": "llm_interaction",
                "error_type": "RuntimeError",
                "error_message": "kaboom-88",
            },
        )
    ], f"warning contract mutated: {f['llmi_warnings']}"


def check_T9(f):
    """database_write.complete span event keeps name + exact attributes."""
    events = dict(f["span_events"])
    assert "database_write.complete" in events, f"span lost: {sorted(events)}"
    assert events["database_write.complete"] == {
        "batch.id": BATCH_ID,
        "event.id": EVENT_ID,
        "detection.count": len(DET_IDS),
        "enrichment_data.count": 0,
    }, f"span attributes mutated: {events['database_write.complete']}"


def check_T10(f):
    """duration arithmetic + stage-duration + per-camera metric arguments."""
    assert ("nemotron", LLM_SECONDS) in [a for a, _k in f["ai_dur_calls"]], (
        f"llm duration mutated: {f['ai_dur_calls']}"
    )
    assert ("analyze", TOTAL_SECONDS) in [a for a, _k in f["stage_calls"]], (
        f"observe_stage_duration mutated: {f['stage_calls']}"
    )
    assert (CAM_ID, CAM_NAME) in [a for a, _k in f["camera_calls"]], (
        f"record_event_by_camera mutated: {f['camera_calls']}"
    )
    assert f["completion"], "completion record missing"
    assert f["completion"][0][2]["duration_ms"] == TOTAL_MS, (
        f"total_duration_ms mutated: {f['completion'][0][2]}"
    )
    events = dict(f["span_events"])
    assert "batch_analysis.complete" in events, f"span lost: {sorted(events)}"
    assert events["batch_analysis.complete"]["total.duration_ms"] == TOTAL_MS


def check_T11(f):
    """completion INFO: message, extra contract, live log_context fields."""
    assert len(f["completion"]) == 1, f"completion records: {f['completion']}"
    msg, level, extra, b_id, c_id = f["completion"][0]
    assert msg == "Batch analysis completed", f"message mutated: {msg!r}"
    assert level == logging.INFO
    assert extra == {
        "event_id": EVENT_ID,
        "risk_score": f["_risk_expected"],
        "risk_level": "high",
        "duration_ms": TOTAL_MS,
        "detection_count": len(DET_IDS),
    }, f"completion extra mutated: {extra}"
    assert b_id == BATCH_ID, f"log_context batch_id field: {b_id!r}"
    assert c_id == CAM_ID, f"log_context camera_id field: {c_id!r}"


def check_T12(f):
    """_broadcast_event is awaited with the created Event instance itself."""
    assert len(f["broadcast_args"]) == 1, f"broadcast calls: {f['broadcast_args']}"
    args = f["broadcast_args"][0][0]
    assert args[-1] is f["event"], f"broadcast argument mutated: {args[-1]!r}"


def check_T13(f, expect_failure):
    """event-stats cache invalidation request / failure-warning contract."""
    if not expect_failure:
        assert f["cache_calls"] == [((), {"reason": CacheInvalidationReason.EVENT_CREATED})], (
            f"invalidation call mutated: {f['cache_calls']}"
        )
        assert f["cache_warnings"] == [], f"unexpected cache warning: {f['cache_warnings']}"
    else:
        assert f["cache_calls"] == [], f"failure run must not reach the cache: {f['cache_calls']}"
        assert f["cache_warnings"] == [
            ("Failed to invalidate event stats cache", logging.WARNING, "boom-77")
        ], f"cache failure contract mutated: {f['cache_warnings']}"


def check_T14(f):
    """batch_analysis.complete span event keeps every shipped attribute."""
    events = dict(f["span_events"])
    assert "batch_analysis.complete" in events, f"span lost: {sorted(events)}"
    assert events["batch_analysis.complete"] == {
        "batch.id": BATCH_ID,
        "event.id": EVENT_ID,
        "camera.id": CAM_ID,
        "risk.score": f["_risk_expected"] or 0,
        "risk.level": "high",
        "detection.count": len(DET_IDS),
        "total.duration_ms": TOTAL_MS,
    }, f"span attributes mutated: {events['batch_analysis.complete']}"


def check_T15(f):
    """every COALESCED sibling batch gets its own idempotency marker.

    Shipped writes batch_event:<id> for batch_id AND — inside the shipped
    ``if coalesced_id != batch_id`` loop (NEM-5464) — for each merged sibling.
    Inverting that comparison to == skips the sibling marker.
    """
    assert f["raised"] is None, f"analyze_batch raised {f['raised']!r}"
    keys_written = {a[0] for a, _k in f["redis_set"]}
    assert f"batch_event:{BATCH_ID}" in keys_written, (
        f"own idempotency marker missing: {sorted(keys_written)}"
    )
    assert f"batch_event:{SIBLING_ID}" in keys_written, (
        f"coalesced sibling marker missing: {sorted(keys_written)}"
    )


# ---------------------------------------------------------------------------
# the battery — 13 tests covering all 130 chunk keys
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session2_execute_keeps_compiled_statement(caplog):
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_526.

    Shipped builds the pg_insert(...).on_conflict_do_nothing(...) statement and
    hands THAT object to session.execute(); the mutant passes None. The pinned
    shipped contract is that every post-flush execute() argument in session 2
    is a real statement still carrying its ON CONFLICT clause.
    """
    f = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_OK,
    )
    check_T1(f)


@pytest.mark.asyncio
async def test_junction_upsert_conflict_target_columns(caplog):
    """Pins on_conflict_do_nothing(index_elements=["event_id", "detection_id"]).

    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_519
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_522
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_523
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_524
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_525
    The conflict target is read off the captured statement's ON CONFLICT clause:
    dropping index_elements (None => inferred target) or renaming/XX-wrapping
    either column changes the recorded elements.
    """
    f = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_OK,
    )
    check_T2(f)


@pytest.mark.asyncio
async def test_create_partial_audit_request_signature(caplog):
    """Pins the shipped 4-kwarg call handed to audit_service.create_partial_audit.

    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_532
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_533
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_534
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_537
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_538
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_541
    The run carries an enrichment SENTINEL, so a NULLed enrichment_result kwarg
    is caught by IDENTITY — with no enrichment shipped also sends None, which
    is the value-only-comparison trap this pin defeats.
    """
    f = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_OK,
    )
    f["_enrich"] = _sentinel
    check_T3(f)


@pytest.mark.asyncio
async def test_audit_row_added_and_debug_line_names_ids(caplog):
    """Kills analyze_batch__mutmut_545 and __mutmut_546.

    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_545
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_546
    session.add() must receive the audit object (id stamped by the harness) and
    the shipped DEBUG line must read "Created audit 5555 for event 4242";
    add(None) stamps nothing and logger.debug(None) emits "None".
    """
    f = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_OK,
    )
    check_T4(f)


@pytest.mark.asyncio
async def test_audit_enqueues_evaluation_with_event_id_and_risk(caplog):
    """Pins _enqueue_for_evaluation(event.id, event.risk_score unless None).

    P0.3 drift re-pin (#6678): the shipped `or 50` became
    `risk_score if risk_score is not None else P03_UNVERIFIED_PRIORITY`
    (=0), so a genuine 0 score now passes through as 0, never 50.

    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_547
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_548
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_549
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_550
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_551
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_552
    Both branches of the shipped ``or 50`` fallback are pinned: risk 75 passes
    through unchanged, risk 0 must become 50 — exactly what separates `or 50`
    from `and 50` and from `or 51`.
    """
    f = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_OK,
    )
    check_T5(f, 75)
    f0 = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_ZERO,
    )
    check_T5(f0, 0)  # P0.3: 0 passes through; None would take P03 (also 0)


@pytest.mark.asyncio
async def test_llminteraction_request_signatures_and_defaults(caplog):
    """Pins snapshot / context-source / LLMInteraction kwargs and shipped defaults.

    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_554
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_555
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_561
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_565
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_586
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_591
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_597
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_599
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_602
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_604
    Run A carries the enrichment sentinel (NULLed enrichment_result /
    detection_ids kwargs then differ by identity) and a risk dict WITHOUT
    raw_response, so the shipped default "" is the observable value; run B runs
    with enrichment False (household_matches must stay None — never the string
    produced by the mutant "" initializer) and a present raw_response. The
    success-path DEBUG line "Created LLMInteraction 991 for event 4242" is
    pinned here as well (its message argument is a single string literal the
    mutator can NULL outright).
    """
    fA = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_OK,
    )
    fA["_enrich"] = _sentinel
    fA["_raw_expected"] = ""
    fA["_household_expected"] = None
    check_T6(fA)

    fB = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=False,
        risk=RISK_RAW,
    )
    fB["_enrich"] = None
    fB["_raw_expected"] = "RAW-XYZ"
    fB["_household_expected"] = None
    check_T6(fB)


@pytest.mark.asyncio
async def test_household_matches_payload_and_dump_branch(caplog):
    """Pins the persons/vehicles household payload handed to LLMInteraction.

    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_568
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_573
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_574
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_575
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_579
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_580
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_581
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_582
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_583
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_584
    The person list mixes an object WITH model_dump() and one WITHOUT, so
    shipped takes both branches of the ternary; the vehicle list carries a
    dumping object, so NULLing vehicle_matches empties "vehicles". The dumping
    object counts its model_dump() invocations, catching the `and False` /
    `or True` inversions and the renamed hasattr targets even where the
    resulting dict compares equal.
    """
    dump_obj = _Dumping({"det": 1, "score": 0.9})
    calls = {"n": 0}
    real_dump = dump_obj.model_dump

    def counted():
        calls["n"] += 1
        return real_dump()

    dump_obj.model_dump = counted
    plain_obj = _Plain({"plain": 2})
    enrich = _Enrich(
        person_household_matches=[dump_obj, plain_obj],
        vehicle_household_matches=[_Dumping({"vid": 7})],
    )
    f = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=enrich,
        risk=RISK_OK,
    )
    f["_dump_calls"] = calls["n"]
    f["_plain_obj"] = plain_obj
    check_T7(f)


@pytest.mark.asyncio
async def test_llminteraction_failure_warning_contract(caplog):
    """Pins the whole LLMInteraction-failure logger.warning payload.

    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_605
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_606
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_608
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_609
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_610
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_611
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_612
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_613
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_614
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_615
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_616
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_617
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_618
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_619
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_620
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_621
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_622
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_623
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_624
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_625
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_626
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_627
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_628
    Constructing LLMInteraction raises RuntimeError("kaboom-88"); the shipped
    handler logs exactly "LLMInteraction creation failed" at WARNING with the
    five-field extra dict (action / resource_id / resource_type / error_type /
    error_message) verbatim, and the analysis still completes.
    """
    f = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_OK,
        llmi_raises=RuntimeError("kaboom-88"),
    )
    check_T8(f)


@pytest.mark.asyncio
async def test_database_write_complete_span_event(caplog):
    """Pins add_span_event("database_write.complete", {...}) name + attributes.

    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_629
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_630
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_631
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_632
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_633
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_634
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_637
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_638
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_641
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_642
    """
    f = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_OK,
    )
    check_T9(f)


@pytest.mark.asyncio
async def test_duration_math_stage_and_camera_metrics(caplog):
    """Pins total_duration arithmetic and its consumers on a fake clock.

    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_643
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_645
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_646
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_647
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_649
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_650
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_654
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_655
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_656
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_657
    time.time is replayed from a fixed ladder (LLM window 2.4 s, total window
    13.0 s for the ms value / 13.5 s for the seconds value), so
    observe_stage_duration("analyze", 13.5) and
    record_event_by_camera("cam-9", "Front Porch Cam") must arrive with exactly
    the shipped arguments, and total_duration_ms is asserted at both shipped
    sinks (completion extra + batch_analysis.complete span).
    """
    f = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_OK,
    )
    check_T10(f)


@pytest.mark.asyncio
async def test_completion_log_context_and_extra(caplog):
    """Pins the completion INFO record: message, extra, stamped context fields.

    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_660
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_661
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_662
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_663
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_664
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_665
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_667
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_668
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_669
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_670
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_671
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_672
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_673
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_674
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_675
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_676
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_677
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_678
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_679
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_680
    The harness installs a kwargs-blind copy of log_context that keeps the
    ContextVar machinery, so a dropped or NULLed batch_id=/camera_id= argument
    at the completion call site removes the stamped record attribute instead of
    being masked by the outer context — the shipped record carries both.
    """
    f = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_OK,
    )
    f["_risk_expected"] = 75
    check_T11(f)


@pytest.mark.asyncio
async def test_broadcast_receives_created_event(caplog):
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_681.

    _broadcast_event must be awaited with the created Event instance itself.
    """
    f = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_OK,
    )
    check_T12(f)


@pytest.mark.asyncio
async def test_cache_invalidation_success_and_failure_contract(caplog):
    """Pins the event-stats cache invalidation call and its failure warning.

    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_682
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_683
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_684
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_686
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_687
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_688
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_689
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_690
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_691
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_692
    Success run: invalidate_event_stats(reason=EVENT_CREATED) is awaited and no
    warning is emitted (which is what catches cache = None, since that diverts
    into the exception handler). Failure run: the cache raises
    RuntimeError("boom-77") and the shipped WARNING reads exactly
    "Failed to invalidate event stats cache" with extra={"error": "boom-77"}.
    """
    f = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_OK,
    )
    check_T13(f, expect_failure=False)
    f2 = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_OK,
        cache_raises=RuntimeError("boom-77"),
    )
    check_T13(f2, expect_failure=True)


@pytest.mark.asyncio
async def test_batch_analysis_complete_span_event(caplog):
    """Pins add_span_event("batch_analysis.complete", {...}) name + attributes.

    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_694
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_695
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_696
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_697
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_698
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_699
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_702
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_703
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_706
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_707
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_708
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_709
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_710
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_711
    kills: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_712
    The risk.score ``or 0`` and risk.level ``or "unknown"`` fallbacks are pinned
    on both Event states: score 75 (where `and 0` collapses to 0) and score 0
    (where shipped yields 0 but `or 1` yields 1).
    """
    f = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_OK,
    )
    f["_risk_expected"] = 75
    check_T14(f)
    f0 = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_ZERO,
    )
    f0["_risk_expected"] = 0
    check_T14(f0)


@pytest.mark.asyncio
async def test_coalesced_sibling_gets_idempotency_marker(caplog):
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_531.

    With batch coalescing enabled and one sibling batch merged, shipped marks
    BOTH batch_id and the sibling (``if coalesced_id != batch_id``, NEM-5464)
    in Redis; the ``==`` inversion skips the sibling marker entirely.
    """
    f = await drive(
        NA,
        lambda an: an.analyze_batch(BATCH_ID, CAM_ID, DET_IDS),
        caplog,
        enrich=_sentinel,
        risk=RISK_OK,
        coalesce=True,
    )
    check_T15(f)
