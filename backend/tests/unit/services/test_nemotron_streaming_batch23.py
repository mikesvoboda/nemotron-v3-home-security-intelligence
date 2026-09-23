"""Batch-23 mutation-kill battery: nemotron_streaming analyzer identity,
Event id fields, progress accumulation, LLM payload stop-tokens.

Target: the 9 TRUE-GAP survivors of the batch-21 combined kill-check
(/tmp/redcheck-b21.log, rc=0 09:44:53Z, 102 KILLED / 19 SURVIVED over the
121-key ns16c-and-ns16b feed). The other 10 are per-mutant MEASURED
EQUIVALENTs, justified in the ledger: recoverable=True removal x3 (field
default MEASURED True), content ''->None x2 (falsy in `if content:`),
risk-fallback DICT-LITERAL renames x4 (A#289/290/292/293 - renaming the
literal key AND reading it back through .get with the SAME default is
value-identity, verified by construction), break->return at loop-end
(A#78 - MEASURED tail of call_llm_streaming after the loop is EMPTY).
NOTE: batch-21's docstring predicted 5 equivalents; the 19-survivor probe
drives MEASURED the full split as 10/9 - corrected by measurement.

Root causes of the 9 gaps:
- analyzer=analyzer (A#220): call_llm received the analyzer by KWARG and
  nobody asserted its IDENTITY, so analyzer=None sailed through.
- Event batch_id/camera_id (A#307/308/316): batch-21 pinned the Event's
  TIME and RISK fields but not its identity columns.
- accumulated_text=accumulated_text (A#247): progress events were never
  read - MEASURED shipped ships the CUMULATIVE string ("X" then "XY").
- stop-token list (L#42-45): the payload dict was never pinned whole, so
  every string mutation inside "stop" survived.

Every expected value MEASURED against shipped production this session
(inline enrich-lane probe drives; production NOT bent).
"""

from __future__ import annotations

import pytest

from backend.tests.unit.services.test_nemotron_streaming_batch16 import (
    SSE_OK,
    make_settings,
    run_analyze,
    run_llm,
)
from backend.tests.unit.services.test_nemotron_streaming_batch16c import (
    populated_analyzer,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


class TestIdentityPins:
    """analyzer kwarg IDENTITY and the Event identity columns were never
    asserted, so analyzer=None / batch_id=None / camera_id=None survived."""

    async def test_call_llm_receives_the_same_analyzer_object(self):
        a, _, _ = populated_analyzer()
        r = await run_analyze(a, chunks=("X",))
        # MEASURED: shipped forwards the analyzer ITSELF.
        assert r["captured"]["kwargs"]["analyzer"] is a

    async def test_event_identity_columns(self):
        a, _, _ = populated_analyzer()
        r = await run_analyze(a, chunks=("X",))
        ev = next(o for o in (c.args[0] for c in r["add_calls"]) if hasattr(o, "batch_id"))
        assert ev.batch_id == "test_batch"
        assert ev.camera_id == "test_camera"


class TestProgressAccumulation:
    """Progress events ship the CUMULATIVE text; the removal mutant ships
    the field-default '' (MEASURED via inspect.signature)."""

    async def test_progress_events_carry_running_total(self):
        a, _, _ = populated_analyzer()
        r = await run_analyze(a, chunks=("X", "Y"))
        prog = [e for e in r["events"] if e.get("event_type") == "progress"]
        assert [p["accumulated_text"] for p in prog] == ["X", "XY"]


class TestLlmPayloadDictExact:
    """The completion payload was never pinned whole, so the four
    stop-token string mutants (XX-wrapped / case-flipped) survived."""

    async def test_payload_exact(self):
        a, _, _ = populated_analyzer()
        r = await run_llm(a, SSE_OK, settings=make_settings(max_tokens=1536))
        payload = r["stream_call"].kwargs["json"]
        # MEASURED shipped dict, value by value.
        assert payload["prompt"] == "TRUNCATED_PROMPT"
        assert payload["temperature"] == 0.3
        assert payload["top_p"] == 0.95
        assert payload["max_tokens"] == 1536
        assert payload["stream"] is True
        # MEASURED EXACT list (order + case + angle-brackets): the four
        # L#42-45 string mutants (XX-wrap / case-flip per token) all die here.
        assert payload["stop"] == ["<|im_end|>", "<|im_start|>"]
