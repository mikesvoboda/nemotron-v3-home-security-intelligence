"""Batch-21 mutation-kill battery: nemotron_streaming downstream kwargs/args
+ SSE flow + observability texts — the 57-key residual of the batch-16c
kill-check (/tmp/redcheck-ns16c16c.log, rc=0 09:16:20Z, 64 KILLED / 57
SURVIVED over the 121-key ns16c∩ns16b feed; shapes /tmp/s57-diffs.tsv).

Root cause of this residual class: the 16c battery pinned the ENRICHMENT
forwarding sites, but every OTHER downstream call site — Event row fields,
metrics args, the HTTP headers dict, and the SSE parse loop's
continue/break/default flows — still had zero exact-argument coverage, so
arg->None/removal and dict-key case mutants all sailed through.

Every expected value MEASURED against shipped production this session
(/tmp/b21-harness.py -> /tmp/b21-probes.json + inline probe v2; production
NOT bent):
- Event row: started_at=14:30:00Z / ended_at=14:30:15Z (min/max detection
  times), risk 75/'high'/'Parsed summary'/'Parsed reasoning', reviewed False.
- _get_recent_scene_changes ships POSITIONALS ('test_camera', session) with
  session IDENTITY; _get_household_context ships 2 positionals whose second
  IS the EnrichmentResult object.
- record_event_by_camera('test_camera', 'Test Camera'); with camera=None the
  if-camera-else fallback ships camera_id in BOTH slots (kills the
  or-True/ternary-flip family, which either crashes or leaks 'None').
- observe_ai_request_duration('nemotron', float), observe_stage_duration
  ('analyze', float), both durations in [0, 60) — kills None (TypeError on
  compare) and the time+start mutants (~3.6e9).
- texts: 'Streaming analysis for batch test_batch',
  'Failed to broadcast event: bcboom',
  'Streaming LLM error: genboom' + exc_info=True EXACT kwargs,
  'Malformed SSE data: ' + EXACTLY 100 x's (kills the [:101] off-by-one).
- headers dict EXACT {'Content-Type': 'application/json', 'X-Auth': ...} —
  kills all five case-rename mutants and headers=None at once.
- SSE flow: blank line mid-stream keeps streaming (kills continue->break),
  [DONE] stops it (kills break->continue via a poisoned post-DONE line),
  content-less JSON yields nothing.

NOT covered — 5 of the 57 are per-mutant MEASURED EQUIVALENTs (ledger):
recoverable=True removal x3 (MEASURED StreamingErrorEvent field default IS
True via inspect.signature) and content default ""->None x2 (falsiness
identity in `if content:`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.services.nemotron_streaming import StreamingErrorCode
from backend.tests.unit.services.test_nemotron_streaming_batch16 import (
    NSP,
    SSE_OK,
    make_session,
    make_settings,
    run_analyze,
    run_llm,
)
from backend.tests.unit.services.test_nemotron_streaming_batch16c import (
    populated_analyzer,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def add_events(r, attr: str):
    return [o for o in (c.args[0] for c in r["add_calls"]) if hasattr(o, attr)]


class TestEventRowFieldPins:
    """Event(...) kwargs were never pinned field-by-field; started_at/
    ended_at=None/removal and the risk_data.get key renames all survived
    because nothing read the row back off session.add."""

    async def test_started_ended_at_are_min_max_detection_times(self):
        a, _, _ = populated_analyzer()
        r = await run_analyze(a, chunks=("X",))
        ev = add_events(r, "started_at")[0]
        # MEASURED: min/max over sample_detections' detected_at
        assert ev.started_at == datetime(2025, 12, 23, 14, 30, tzinfo=UTC)
        assert ev.ended_at == datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC)

    async def test_risk_fields_from_parsed_response(self):
        # POPULATED parse (75/high) is the discriminator: every
        # risk_data.get key-rename mutant falls to 50/'medium' and dies here.
        a, _, _ = populated_analyzer()
        r = await run_analyze(a, chunks=("X",))
        ev = add_events(r, "risk_score")[0]
        assert (ev.risk_score, ev.risk_level) == (75, "high")
        assert (ev.summary, ev.reasoning) == ("Parsed summary", "Parsed reasoning")
        assert ev.reviewed is False

    async def test_parse_failure_falls_back_to_neutral_risk(self):
        # Pins the except-leg defaults so the rename family cannot hide by
        # making the POPULATED leg fall back: here shipped ships 50/medium.
        a, _, _ = populated_analyzer()
        a._parse_llm_response = MagicMock(side_effect=ValueError("nope"))
        r = await run_analyze(a, chunks=("X",))
        ev = add_events(r, "risk_score")[0]
        assert (ev.risk_score, ev.risk_level) == (50, "medium")
        assert ev.summary == "Analysis unavailable"


class TestDownstreamCallArguments:
    """The arg->None / arg-removal family across every downstream call site."""

    async def test_scene_changes_positionals(self):
        a, _, _ = populated_analyzer()
        r = await run_analyze(a, chunks=("X",))
        c = a._get_recent_scene_changes.call_args
        assert c.kwargs == {}  # MEASURED: strictly positional
        assert c.args[0] == "test_camera"
        assert c.args[1] is r["session"]

    async def test_household_context_positionals(self):
        a, er, _ = populated_analyzer()
        await run_analyze(a, chunks=("X",))
        c = a._get_household_context.call_args
        assert len(c.args) == 2
        assert len(c.args[0]) == 2  # per-detection dicts, one per detection
        assert c.args[0][0]["object_type"] == "person"  # MEASURED key
        assert c.args[1] is er

    async def test_record_event_by_camera_args(self):
        a, _, _ = populated_analyzer()
        r = await run_analyze(a, chunks=("X",))
        m = r["metrics"]["record_event_by_camera"]
        assert m.call_args.args == ("test_camera", "Test Camera")
        assert m.call_args.kwargs == {}

    async def test_cameraless_batch_reports_camera_id_in_both_slots(self):
        # if-camera-else fallback MEASURED: camera=None -> 'test_camera' for
        # BOTH the LLM kwargs and the metrics arg (or-True mutant crashes
        # None.name or leaks None).
        a, _, _ = populated_analyzer()
        sess = make_session(camera=None)
        r = await run_analyze(a, session=sess, chunks=("X",))
        assert r["captured"]["kwargs"]["camera_name"] == "test_camera"
        m = r["metrics"]["record_event_by_camera"]
        assert m.call_args.args == ("test_camera", "test_camera")

    async def test_duration_metrics_get_real_floats(self):
        a, _, _ = populated_analyzer()
        r = await run_analyze(a, chunks=("X",))
        ai = r["metrics"]["observe_ai_request_duration"].call_args
        st = r["metrics"]["observe_stage_duration"].call_args
        assert ai.args[0] == "nemotron"
        assert st.args[0] == "analyze"
        for call in (ai, st):  # None -> TypeError here; time+start -> ~3.6e9
            assert 0 <= call.args[1] < 60
            assert isinstance(call.args[1], float)


class TestObservabilityTexts:
    """Message-text and kwarg mutants (->None, case swaps, [:101])."""

    async def test_batch_info_log_message(self):
        a, _, _ = populated_analyzer()
        with patch(f"{NSP}.logger.info", autospec=True) as li:
            await run_analyze(a, chunks=("X",))
        msgs = [str(c.args) for c in li.call_args_list]
        assert str(("Streaming analysis for batch test_batch",)) in msgs

    async def test_broadcast_failure_warning_text(self):
        a, _, _ = populated_analyzer()
        a._broadcast_event = AsyncMock(side_effect=RuntimeError("bcboom"))
        with patch(f"{NSP}.logger.warning", autospec=True) as lw:
            await run_analyze(a, chunks=("X",))
        hits = [c for c in lw.call_args_list if "broadcast" in str(c.args)]
        assert len(hits) == 1
        assert hits[0].args == ("Failed to broadcast event: bcboom",)
        assert hits[0].kwargs == {}

    async def test_generic_llm_error_logs_with_exc_info_true(self):
        a, _, _ = populated_analyzer()

        async def boom(*args, **kwargs):
            raise ValueError("genboom")
            yield  # pragma: no cover

        with patch(f"{NSP}.logger.error", autospec=True) as le:
            r = await run_analyze(a, chunks=(), llm_side_effect=boom)
        assert le.call_count == 1
        assert le.call_args.args == ("Streaming LLM error: genboom",)
        # MEASURED kwargs EXACT {exc_info: True}: removal/False/None all die
        assert dict(le.call_args.kwargs) == {"exc_info": True}
        err = [e for e in r["events"] if e.get("error_code")]
        assert len(err) == 1
        assert err[0]["error_code"] is StreamingErrorCode.LLM_SERVER_ERROR
        assert err[0]["recoverable"] is True

    async def test_malformed_sse_warns_with_exact_100_char_prefix(self):
        a, _, _ = populated_analyzer()
        lines = [f"data: {'x' * 150}", 'data: {"content": "A"}', "data: [DONE]"]
        with patch(f"{NSP}.logger.warning", autospec=True) as lw:
            r = await run_llm(a, lines, settings=make_settings())
        assert r["chunks"] == ["A"]  # malformed line skipped, stream continues
        assert len(lw.call_args_list) == 1
        assert lw.call_args.args == (f"Malformed SSE data: {'x' * 100}",)


class TestErrorEventRecoverableLegs:
    """Timeout/connect legs ship recoverable=True + the right code (the
    False-flip mutants; removal mutants are default-True equivalents)."""

    async def _leg(self, exc):
        a, _, _ = populated_analyzer()

        async def boom(*args, **kwargs):
            raise exc
            yield  # pragma: no cover

        r = await run_analyze(a, chunks=(), llm_side_effect=boom)
        err = [e for e in r["events"] if e.get("error_code")]
        assert len(err) == 1
        return err[0]

    async def test_timeout_leg(self):
        e = await self._leg(httpx.TimeoutException("tboom"))
        assert e["error_code"] is StreamingErrorCode.LLM_TIMEOUT
        assert e["recoverable"] is True

    async def test_connect_leg(self):
        e = await self._leg(httpx.ConnectError("cboom"))
        assert e["error_code"] is StreamingErrorCode.LLM_CONNECTION_ERROR
        assert e["recoverable"] is True


class TestCallLlmHttpShape:
    """Headers dict and the detection_dicts flow through BOTH functions."""

    async def test_stream_headers_dict_exact(self):
        a, _, _ = populated_analyzer()
        r = await run_llm(a, SSE_OK, settings=make_settings())
        # MEASURED: base Content-Type + analyzer auth headers, merged EXACT —
        # kills every case-rename key/value mutant and headers=None together.
        assert r["stream_call"].kwargs["headers"] == {
            "Content-Type": "application/json",
            "X-Auth": "auth-token",
        }

    async def test_detection_dicts_flow_to_build_prompt(self):
        a, er, _ = populated_analyzer()
        dicts = [{"id": 1, "confidence": 0.5}]
        r = await run_llm(
            a,
            SSE_OK,
            settings=make_settings(),
            enriched_context="EC",
            enrichment_result=er,
            detection_dicts=dicts,
        )
        assert r["chunks"] == ["Based", " on", " the"]
        # call_llm forwards EXACTLY what it got (MEASURED; =None mutant dies)
        assert a._build_prompt.call_args.kwargs["detection_dicts"] == dicts

    async def test_analyze_builds_detection_dicts_from_confident_detections(self):
        a, _, _ = populated_analyzer()
        r = await run_analyze(a, chunks=("X",))
        # MEASURED shipped shape: confidence + class_name per confident det
        assert r["captured"]["kwargs"]["detection_dicts"] == [
            {"confidence": 0.95, "class_name": "person"},
            {"confidence": 0.88, "class_name": "car"},
        ]


class TestSseParseFlow:
    """continue/break/content-default flows in the SSE loop."""

    async def test_blank_line_continues_stream(self):
        # continue->break mutant yields [] here; shipped keeps streaming.
        a, _, _ = populated_analyzer()
        lines = ["", 'data: {"content": "A"}', "data: [DONE]"]
        r = await run_llm(a, lines, settings=make_settings())
        assert r["chunks"] == ["A"]

    async def test_done_breaks_and_poison_line_never_emits(self):
        # break->continue mutant emits "POISON" after [DONE].
        a, _, _ = populated_analyzer()
        lines = ['data: {"content": "A"}', "data: [DONE]", 'data: {"content": "POISON"}']
        r = await run_llm(a, lines, settings=make_settings())
        assert r["chunks"] == ["A"]

    async def test_contentless_chunk_yields_nothing(self):
        a, _, _ = populated_analyzer()
        lines = ['data: {"notcontent": 1}', "data: [DONE]"]
        r = await run_llm(a, lines, settings=make_settings())
        assert r["chunks"] == []
