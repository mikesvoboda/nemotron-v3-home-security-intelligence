# WP4.4 triage dossier — backend/services/nemotron_streaming.py
Date: 2026-09-18 · Source: mutants/backend/services/nemotron_streaming.py.meta (exit_code 0)
Mutants in meta: 533 keys · 172 killed · 90 unchecked (in-flight) · **271 survivors**
Only `x_analyze_batch_streaming` survived (call_llm_streaming fully killed). Diffs extracted by
block-diffing each `x_analyze_batch_streaming__mutmut_N` copy against `__mutmut_orig` in the mutant
module (mutmut show not needed). UNVERIFIED throughout — nothing was executed.

## Covering test file
- backend/tests/unit/services/test_nemotron_streaming.py — TestAnalyzeBatchStreaming L628-1320
  (mutmut-stats tests_by_mangled_function_name: x_analyze_batch_streaming -> 14 tests in that class;
   nemotron_analyzer.py delegation test in test_nemotron_analyzer.py::test_analyze_batch_streaming_delegates_to_streaming_module)
- Source: backend/services/nemotron_streaming.py analyze_batch_streaming L120-450.

## Why so many survive
The 14 existing tests assert error_code / event_type / event_id / a couple of progress contents and
2 kwargs (enriched_context, enrichment_result) on the mocked call_llm_streaming. Everything else —
kwargs piped to collaborators (analyzer is a MagicMock), DB-row columns on the constructed Event,
the LLMInteraction record, the junction INSERT, accumulated_text, and the `recoverable` flag — is
executed but never asserted. The mock-everything harness also means arg mutations to collaborators
survive silently.

## Clusters (sum = 271)

| # | Cluster (pattern × concern) | N | Class | Example keys (…nemotron_streaming.x_analyze_batch_streaming__mutmut_) |
|---|---|---|---|---|
| C1 | Progress event accumulated_text: init `""`→`"XXXX"`, `+= chunk`→`= chunk`, kwarg dropped (L283,300-304) | 3 | TEST-GAP | 218, 242, 247 |
| C2 | Fatal error yields marked recoverable=True: `recoverable=False` flipped to True or deleted (default True) on no-redis/batch-not-found/no-detections×2/invalid-ids (L127-195) | 10 | TEST-GAP | 7, 64, 85 |
| C3 | Retryable LLM handlers recoverable: True→False flip (3, real) or True deleted (3, EQUIVALENT — schema default=True, backend/api/schemas/streaming.py:80) (L307-328) | 6 | TEST-GAP | 261, 268, 283 |
| C4 | Idempotency-hit complete event fallbacks: `or 50`→`and 50`/`or 51`, `or "medium"`→`and`/`"MEDIUM"`/casing, summary/reasoning fallback text (L139-145); test builds all-populated existing Event so fallback branch never runs | 13 | TEST-GAP | 27, 28, 31 |
| C5 | Event row construction: `batch_id=`/`camera_id=`/`started_at=`/`ended_at=`→None or deleted, `reviewed=` flips (True/None/deleted), `risk_*.get` default tweaks (L341-355) | 29 | TEST-GAP | 307, 315, 335 |
| C6 | LLMInteraction record + observability builders: snapshot/sources/household args →None/deleted, `if enrichment_result is not None` inverted, LLMInteraction kwargs (L376-432); failures are try/except-swallowed and no test inspects session.add | 29 | TEST-GAP | 388, 393, 403 |
| C7 | Context kwargs piped to call_llm_streaming at analyze's call site: camera_name/start_time/end_time/detections_list/camera_health_context/detection_dicts/auto_tuning_context/household_context →None or deleted (L287-299) | 13 | TEST-GAP | 220, 227, 238 |
| C8 | Camera lookup: select(None)/where-flip/scalar→None, `camera.name if camera else camera_id` clobbered; camera_name then flows only into mocked collaborator (L174-176) | 7 | TEST-GAP | 69, 73, 75 |
| C9 | detections_for_household list-of-dicts: per-key string clobbers (`"XXconfidenceXX"`, UPPER), whole list→None, `if d.bbox_x is not None` flips (L239-271) | 31 | TEST-GAP | 168, 178, 192 |
| C10 | detection_dicts build: class_name key/default clobbers, `if d.confidence is not None` inverted, whole list→None (L273-281) | 6 | TEST-GAP | 211, 214, 216 |
| C11 | Junction-table INSERT: values dict keys clobbered, on_conflict index_elements clobbered, stmt→None/execute(None); session.execute fully mocked (L357-374) | 11 | TEST-GAP | 362, 370, 374 |
| C12 | Idempotency/broadcast collaborator args: `_check_idempotency(None)`, `_get_existing_event(None)`, `_set_idempotency(None, id)`/positional-swap, `_broadcast_event(None)` (L135-136,434,439) | 7 | TEST-GAP | 13, 404, 419 |
| C13 | Enrichment fetch call args: `_get_enriched_context`/`_get_enrichment_result` positional/kwargs →None/dropped (L202-210) | 15 | TEST-GAP | 107, 116, 122 |
| C14 | Context-fetch internals: `_get_recent_scene_changes`/`get_tuning_context` args →None/dropped (L212-237) | 11 | TEST-GAP | 128, 147, 149 |
| C15 | Context seed values `""`→None/`"XXXX"` (camera_health/auto_tuning/household) (L215,226,240) | 7 | TEST-GAP | 126, 145, 165 |
| C16 | `if detections_data else []` → `if (detections_data) or True else []` — would json.loads(None) crash; no test reaches that corner (L158-160) | 1 | TEST-GAP | 56 |
| C17 | batch_fetch_detections / _format_detections args →None (L188,200) | 4 | TEST-GAP | 87, 88, 104 |
| C18 | logger `extra={...}` dict: key clobbers, extra→None/deleted (3 warning blocks, L220-271) | 21 | EQUIVALENT | 134, 140, 143 |
| C19 | Logger message text: warning/info message strings cased/clobbered/None (L221,235,269,171,442) — pure log text | 14 | EQUIVALENT | 67, 133, 200 |
| C20 | Parse-fallback dict key clobbers `"risk_score"/"risk_level"` → renamed/UPPER: fallback still yields 50/"medium" via .get defaults — semantically identical (L334-339) | 4 | EQUIVALENT | 289, 290, 293 |
| C21 | Final complete-event `or`-fallback tweaks (`or 50`→51, `"medium"` casing): unreachable — Event fields always populated from risk_data which always carries all 4 keys (L444-450) | 9 | EQUIVALENT | 432, 437, 439 |
| C22 | `logger.error(..., exc_info=True)` →False/None/deleted (L322) — traceback capture only | 4 | LOW-VALUE | 269, 270, 273 |
| C23 | Prometheus call args: observe_ai_request_duration/observe_stage_duration label clobbers, duration→None/`+start` sign flip, record_event_by_camera args (L306,435-437) | 12 | LOW-VALUE | 252, 413, 416 |
| C24 | SSE error_message user-facing text clobbers ("Redis client not initialized", "LLM inference failed") — tests only substring-assert "Redis" (L130,325) | 4 | LOW-VALUE | 8, 280, 282 |

Class totals: TEST-GAP 203 · EQUIVALENT 48 · LOW-VALUE 20 (sum 271).
TEST-GAP headline: 194 of 203 sit in 8 "plumbing/row/persistence" clusters (C5, C6, C7, C8, C9,
C13, C14 + C15) that one strengthened success-flow test can mostly absorb; C1-C4, C11 are
individually sharp gaps.

## Drafted tests (6) — UNVERIFIED, not yet run red/green
Target file for all: backend/tests/unit/services/test_nemotron_streaming.py (reuse module fixtures
`mock_analyzer`, `sample_detections`; append classes). TDD procedure for each: run against the
mutant copy (or apply the one-line change) → assertion fails; run against original → passes.

### T1 → C1 (+ some C7) — accumulated_text must accumulate
```python
class TestProgressAccumulation:
    @pytest.mark.asyncio
    async def test_progress_events_accumulate_text(self, mock_analyzer, sample_detections):
        """StreamingProgressEvent.accumulated_text must grow across chunks."""
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        from backend.models.camera import Camera
        mock_camera = Camera(id="test_camera", name="Test Camera", folder_path="/test/path")
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none = MagicMock(return_value=mock_camera)
        mock_session.execute = AsyncMock(return_value=mock_camera_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        async def mock_refresh(obj):
            from backend.models.event import Event
            if isinstance(obj, Event):
                obj.id = 456

        mock_session.refresh = AsyncMock(side_effect=mock_refresh)

        async def mock_llm_stream(*args, **kwargs):
            yield "Alpha"
            yield " Beta"
            yield " Gamma"

        with (
            patch("backend.services.nemotron_streaming.get_session", return_value=mock_session, autospec=True),
            patch("backend.services.nemotron_streaming.batch_fetch_detections", return_value=sample_detections, autospec=True),
            patch("backend.services.nemotron_streaming.call_llm_streaming", side_effect=mock_llm_stream, autospec=True),
            patch("backend.services.nemotron_streaming.observe_ai_request_duration", autospec=True),
            patch("backend.services.nemotron_streaming.observe_stage_duration", autospec=True),
            patch("backend.services.nemotron_streaming.record_event_created", autospec=True),
            patch("backend.services.nemotron_streaming.record_event_by_camera", autospec=True),
        ):
            events = []
            async for event in analyze_batch_streaming(
                analyzer=mock_analyzer, batch_id="test_batch", camera_id="test_camera", detection_ids=[1, 2]
            ):
                events.append(event)

        progress = [e for e in events if e["event_type"] == "progress"]
        assert [p["content"] for p in progress] == ["Alpha", " Beta", " Gamma"]
        assert progress[0]["accumulated_text"] == "Alpha"
        assert progress[1]["accumulated_text"] == "Alpha Beta"
        assert progress[2]["accumulated_text"] == "Alpha Beta Gamma"
```
Kills `+= chunk`→`= chunk` (progress[1] == " Beta"), init "XXXX" (progress[0] == "XXXXAlpha"),
dropped accumulated_text kwarg (None != "Alpha").

### T2 → C2 + C3 — recoverable flag per error class
```python
class TestErrorRecoverability:
    @pytest.mark.asyncio
    async def test_fatal_errors_are_not_recoverable(self, mock_analyzer):
        """Config/data errors must mark recoverable=False (schema default is True)."""
        mock_analyzer._redis = None
        events = [e async for e in analyze_batch_streaming(analyzer=mock_analyzer, batch_id="b")]
        assert events[0]["recoverable"] is False

    @pytest.mark.asyncio
    async def test_retryable_llm_errors_are_recoverable(self, mock_analyzer, sample_detections):
        """Timeout/connect/server LLM failures must mark recoverable=True."""
        for exc in (httpx.TimeoutException("t"), httpx.ConnectError("c"), RuntimeError("s")):
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
            with (
                patch("backend.services.nemotron_streaming.get_session", return_value=mock_session, autospec=True),
                patch("backend.services.nemotron_streaming.batch_fetch_detections", return_value=sample_detections, autospec=True),
                patch("backend.services.nemotron_streaming.call_llm_streaming", side_effect=exc, autospec=True),
            ):
                events = [e async for e in analyze_batch_streaming(
                    analyzer=mock_analyzer, batch_id="test_batch", camera_id="test_camera", detection_ids=[1, 2]
                )]
            assert events[0]["event_type"] == "error"
            assert events[0]["recoverable"] is True
```
Kills the 10 False→True/deleted fatal mutants and the 3 True→False retryable flips.

### T3 → C4 — idempotency-hit fallbacks on sparse existing event
```python
class TestIdempotencyHitFallbacks:
    @pytest.mark.asyncio
    async def test_sparse_existing_event_uses_fallbacks(self, mock_analyzer):
        """Idempotency hit on an Event with NULL risk fields must emit documented fallbacks."""
        mock_analyzer._check_idempotency = AsyncMock(return_value=123)
        sparse = Event(id=123, batch_id="test_batch", camera_id="test_camera",
                       risk_score=None, risk_level=None, summary=None, reasoning=None)
        mock_analyzer._get_existing_event = AsyncMock(return_value=sparse)

        events = [e async for e in analyze_batch_streaming(analyzer=mock_analyzer, batch_id="test_batch")]
        assert len(events) == 1
        assert events[0]["event_type"] == "complete"
        assert events[0]["risk_score"] == 50
        assert events[0]["risk_level"] == "medium"
        assert events[0]["summary"] == "No summary available"
        assert events[0]["reasoning"] == "No reasoning available"
```
Kills or→and (and yields None/False), or 50→51, casing/clobbered fallbacks. Note: needs
`Event(...)` with nullable columns to be accepted by the model; if risk_score is NOT NULL, build
with `risk_score=0` — then `0 or 50`→`0 and 50` and `or 51` both still die. (UNVERIFIED which.)

### T4 → C5 + C12 (+ C6 partly) — persisted Event row + idempotency/broadcast call args
```python
class TestPersistedEventRow:
    @pytest.mark.asyncio
    async def test_event_row_and_side_effects_populated(self, mock_analyzer, sample_detections):
        """Event columns and idempotency/broadcast args must reflect the batch inputs."""
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        from backend.models.camera import Camera
        mock_camera = Camera(id="test_camera", name="Test Camera", folder_path="/test/path")
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_camera)))
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        async def mock_refresh(obj):
            from backend.models.event import Event
            if isinstance(obj, Event):
                obj.id = 456

        mock_session.refresh = AsyncMock(side_effect=mock_refresh)

        async def mock_llm_stream(*args, **kwargs):
            yield "ok"

        from backend.models.event import Event as EventModel
        with (
            patch("backend.services.nemotron_streaming.get_session", return_value=mock_session, autospec=True),
            patch("backend.services.nemotron_streaming.batch_fetch_detections", return_value=sample_detections, autospec=True),
            patch("backend.services.nemotron_streaming.call_llm_streaming", side_effect=mock_llm_stream, autospec=True),
            patch("backend.services.nemotron_streaming.observe_ai_request_duration", autospec=True),
            patch("backend.services.nemotron_streaming.observe_stage_duration", autospec=True),
            patch("backend.services.nemotron_streaming.record_event_created", autospec=True),
            patch("backend.services.nemotron_streaming.record_event_by_camera", autospec=True),
        ):
            events = [e async for e in analyze_batch_streaming(
                analyzer=mock_analyzer, batch_id="test_batch", camera_id="test_camera", detection_ids=[1, 2]
            )]

        added = [c.args[0] for c in mock_session.add.call_args_list]
        event = next(a for a in added if isinstance(a, EventModel))
        assert event.batch_id == "test_batch"
        assert event.camera_id == "test_camera"
        assert event.started_at == sample_detections[0].detected_at
        assert event.ended_at == sample_detections[1].detected_at
        assert event.reviewed is False
        assert events[-1]["event_type"] == "complete"
        mock_analyzer._check_idempotency.assert_awaited_once_with("test_batch")
        mock_analyzer._set_idempotency.assert_awaited_once_with("test_batch", 456)
        mock_analyzer._broadcast_event.assert_awaited_once_with(event)
```
Kills batch_id/camera_id/started_at/ended_at→None/deleted, reviewed True/None/deleted, and the
7 C12 arg mutants. (started_at/ended_at equality holds since analyze passes detection min/max
through; if isoformat round-trip in the mocked flow loses tz, compare `.isoformat()` strings.)

### T5 → C6 — LLMInteraction record content
```python
class TestLLMInteractionRecord:
    @pytest.mark.asyncio
    async def test_llm_interaction_captured_with_full_response(self, mock_analyzer, sample_detections):
        """An LLMInteraction mirroring prompt outputs must be added even though failures are swallowed."""
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        from backend.models.camera import Camera
        mock_camera = Camera(id="test_camera", name="Test Camera", folder_path="/test/path")
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_camera)))
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        async def mock_refresh(obj):
            from backend.models.event import Event
            if isinstance(obj, Event):
                obj.id = 456

        mock_session.refresh = AsyncMock(side_effect=mock_refresh)
        sentinel_snap = {"snap": True}
        sentinel_src = {"sources": True}
        mock_analyzer._build_enrichment_snapshot = MagicMock(return_value=sentinel_snap)
        mock_analyzer._build_context_sources = MagicMock(return_value=sentinel_src)

        async def mock_llm_stream(*args, **kwargs):
            yield "Hello"
            yield " world"

        with (
            patch("backend.services.nemotron_streaming.get_session", return_value=mock_session, autospec=True),
            patch("backend.services.nemotron_streaming.batch_fetch_detections", return_value=sample_detections, autospec=True),
            patch("backend.services.nemotron_streaming.call_llm_streaming", side_effect=mock_llm_stream, autospec=True),
            patch("backend.services.nemotron_streaming.observe_ai_request_duration", autospec=True),
            patch("backend.services.nemotron_streaming.observe_stage_duration", autospec=True),
            patch("backend.services.nemotron_streaming.record_event_created", autospec=True),
            patch("backend.services.nemotron_streaming.record_event_by_camera", autospec=True),
        ):
            async for _ in analyze_batch_streaming(
                analyzer=mock_analyzer, batch_id="test_batch", camera_id="test_camera", detection_ids=[1, 2]
            ):
                pass

        from backend.models.llm_interaction import LLMInteraction
        added = [c.args[0] for c in mock_session.add.call_args_list]
        lli = next(a for a in added if isinstance(a, LLMInteraction))
        assert lli.event_id == 456
        assert lli.raw_response == "Hello world"
        assert lli.enrichment_snapshot == sentinel_snap
        assert lli.context_sources == sentinel_src
        assert lli.household_matches is None
```
Kills `raw_response=None`/dropped (survivors 400s range), enrichment_snapshot/context_sources→None,
`event_id=event.id`→None/deleted, `if enrichment_result is not None` inversion (no-op here;
pair with the enrichment variant by re-running with an EnrichmentTrackingResult whose
person_household_matches is non-empty and asserting household_matches["persons"]).

### T6 → C7 + C8 + C10 (+ C15) — full kwargs contract into call_llm_streaming
```python
class TestLLMCallContextPlumbing:
    @pytest.mark.asyncio
    async def test_llm_call_receives_built_context(self, mock_analyzer, sample_detections):
        """Every context the analyzer builds must reach call_llm_streaming unchanged."""
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        from backend.models.camera import Camera
        mock_camera = Camera(id="test_camera", name="Front Door", folder_path="/test/path")
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_camera)))
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        async def mock_refresh(obj):
            from backend.models.event import Event
            if isinstance(obj, Event):
                obj.id = 456

        mock_session.refresh = AsyncMock(side_effect=mock_refresh)

        health_fmt = "HEALTH-CTX"
        mock_analyzer._get_recent_scene_changes = AsyncMock(return_value=["sc"])
        tuner = MagicMock()
        tuner.get_tuning_context = AsyncMock(return_value="TUNING-CTX")
        facade = MagicMock()
        facade.get_prompt_auto_tuner = MagicMock(return_value=tuner)
        mock_analyzer._get_facade = MagicMock(return_value=facade)
        mock_analyzer._get_household_context = AsyncMock(return_value="HOUSE-CTX")
        mock_analyzer._get_enriched_context = AsyncMock(return_value={"prev": 1})

        captured = {}

        async def mock_llm_stream(*args, **kwargs):
            captured.update(kwargs)
            yield "ok"

        import backend.services.nemotron_streaming as ns
        with (
            patch("backend.services.nemotron_streaming.get_session", return_value=mock_session, autospec=True),
            patch("backend.services.nemotron_streaming.batch_fetch_detections", return_value=sample_detections, autospec=True),
            patch.object(ns, "call_llm_streaming", side_effect=mock_llm_stream, autospec=True),
            patch("backend.services.prompts.format_camera_health_context", return_value=health_fmt),
            patch("backend.services.nemotron_streaming.observe_ai_request_duration", autospec=True),
            patch("backend.services.nemotron_streaming.observe_stage_duration", autospec=True),
            patch("backend.services.nemotron_streaming.record_event_created", autospec=True),
            patch("backend.services.nemotron_streaming.record_event_by_camera", autospec=True),
        ):
            async for _ in analyze_batch_streaming(
                analyzer=mock_analyzer, batch_id="test_batch", camera_id="test_camera", detection_ids=[1, 2]
            ):
                pass

        assert captured["camera_name"] == "Front Door"                      # kills C8 camera=None
        assert captured["start_time"] == sample_detections[0].detected_at.isoformat()
        assert captured["end_time"] == sample_detections[1].detected_at.isoformat()
        assert captured["detections_list"] == mock_analyzer._format_detections.return_value
        assert captured["enriched_context"] == {"prev": 1}
        assert captured["camera_health_context"] == health_fmt              # kills C7/C15 None/clobber
        assert captured["auto_tuning_context"] == "TUNING-CTX"
        assert captured["household_context"] == "HOUSE-CTX"
        assert captured["detection_dicts"] == [
            {"confidence": 0.95, "class_name": "person"},
            {"confidence": 0.88, "class_name": "car"},
        ]                                                                    # kills C10 confidence-filter inversion & dicts→None
```
Note: format_camera_health_context is imported inside the function, so patch at its defining
module path (`backend.services.prompts.format_camera_health_context`) — matches NEM-3012 import
style at L213. Sanitizer passthrough: `_build_prompt`/sanitize are mocked or identity in the
analyzer mock; `mock_analyzer._format_detections` returns a fixed string that must appear as
detections_list (kills `detections_list = None`).

## Notes for WP4.4
- C18/C19/C20/C21 (48) are EQUIVALENT: log text/extra dicts, fallback values identical to .get
  defaults, unreachable fallbacks. No test worth writing.
- C22/C23/C24 (20) LOW-VALUE: exc_info, Prometheus labels/durations, message casing. Optionally
  add a metrics-label assertion later; not worth mutant pressure now.
- The 90 `null` (unchecked) keys in the meta may shift totals when the live run finishes;
  re-fold counts before consuming this feed.
- Drafted tests assume `Event` model accepts risk=None on construction (T3). If the column is
  NOT NULL at model level, adjust as noted inline. UNVERIFIED — not executed per run constraints.
