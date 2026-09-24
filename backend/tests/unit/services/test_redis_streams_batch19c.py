"""Batch-19c mutation-kill battery: redis_streams structural survivors.

Companion to 19b (raise/log shapes). Completes the rs18 217-survivor triage:
the KILLABLE structural residue the 19b classes don't reach, plus the
per-mutant EQUIVALENCE dispositions the census proved. All expected values
MEASURED via /tmp/b19-harness.py (→ /tmp/b19-probes.json); the kill designs
reason from the FEED SHAPES (/tmp/rs19-shapes.tsv) and were validated against
shipped behavior before being asserted. Production NOT bent to any mutant.

KILLABLE (asserted below):
- trim_stream ``info.get("length", 0)`` → ``None``/no-default on EITHER read
  (mutmut_12/14 current_length line, mutmut_?? new_length line): shipped
  defaults 0 and computes removed from the other read; both mutants raise
  TypeError inside ``max()`` → swallowed by the except → ret 0 + silence.
  Separating inputs use a mock-only NEGATIVE length (never occurs in real
  replies) — the only input class where the 0-default matters downstream.
- trim_stream except-branch ``current_length = 0`` → ``None`` (mutmut_18):
  only reachable when the FIRST xinfo raises; shipped then computes
  max(0, 0 - (-5)) = 5 from the negative mock length; the None mutant
  TypeErrors → ret 0.
- trim_stream ``if removed > 0`` → ``> 1`` (mutmut_48): shipped logs at
  removed == 1 (MEASURED 5→4); the mutant is silent there. (``>= 0`` is
  killed by 19b's removed==0 silence pin.)
- AnalysisStreamMessage.from_stream_entry ``replace("Z", "+00:00")`` →
  ``replace("z", "+00:00")`` (mutmut_25): MEASURED on 3.14 —
  ``fromisoformat("2024-01-02T03:04:05z")`` raises ValueError, so shipped
  (which only upper-cases the Z) returns pipeline_start_time None for the
  lowercase-z input, while the mutant parses it to 1704164645.0. Pin None.

EQUIVALENT (per-mutant, no input distinguishes — justified, not skipped):
- DetectionStreamMessage.from_stream_entry mutmut_3/5:
  ``data.get("timestamp", "")`` → None / no-default. Both falsy; the
  ``if raw_ts:`` guard sends both to the same ``ts = time.time()`` branch
  (MEASURED: absent-timestamp and ""-timestamp both → now-like float).
- AnalysisStreamMessage.from_stream_entry mutmut_3/5:
  ``data.get("detection_ids", "[]")`` → None / no-default. json.loads(None)
  raises TypeError, caught by the same except as the shipped "[]" path →
  both MEASURED ``detection_ids == []``.
- trim_stream except-branch ``new_length = 0`` → None/1 (mutmut_45/46): the
  except branch also pins ``removed = 0``, and new_length is read ONLY by
  the ``if removed > 0`` log — unreachable in that branch. Never observable.
- get_stream_info ``info.get("first-entry", [""])[0]`` → None/no-default
  (mutmut_58/60): the ``[0]`` subscript is guarded by
  ``if info.get("first-entry") else ""`` — the default is only read when
  the guard already chose the other side. Never observable.
- consume_* ``from_stream_entry(..., delivery_count=1)`` kwarg REMOVAL
  (DetectionStreamServiceǁconsume_detections mutmut_30,
  AnalysisStreamServiceǁconsume_batches mutmut_26): the parameter default IS
  1, so the call binds identically. (The None/=2 siblings are killed by the
  19b delivery_count pins.)
- add_detection ``str(value) if not isinstance(value, str) else value`` →
  ``... or True ...`` (mutmut_41): truthy-and is identity for the condition;
  and ``str(v) is v`` for str values — both branches bind the same object on
  every input (MEASURED identity probe add_same_str_identity).
- analysis claim ``_text(None)`` siblings where the id is passed through the
  valid-identity pin: the 19b analysis claim test pins msg.id == "7-7" from a
  valid entry, killing any _text-argument mutant; entries whose id is
  genuinely None are unrepresentable in the real XAUTOCLAIM reply shape.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis import RedisClient
from backend.services import redis_streams as RS
from backend.services.redis_streams import AnalysisStreamMessage, DetectionStreamService

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def mk(**kw):
    c = MagicMock(spec=RedisClient)
    c._client = AsyncMock()
    return DetectionStreamService(redis_client=c, **kw), c


class TestTrimDefaultShapes:
    async def test_second_read_missing_length_counts_removed(self):
        # new_length-line default mutants: first {"length": 10}, second {}
        # (no key) → shipped new_length default 0 → removed 10 + log;
        # None/no-default mutants TypeError inside max() → except → ret 0.
        d, c = mk()
        c._client.xinfo_stream.side_effect = [{"length": 10}, {}]
        with patch.object(RS.logger, "info", autospec=True) as li:
            assert await d.trim_stream() == 10
        assert li.call_args.args[0] == "Trimmed stream"
        assert dict(li.call_args.kwargs["extra"])["new_length"] == 0

    async def test_first_read_missing_length_counts_removed(self):
        # current_length-LINE default mutants (feed keys 12/14): first {} (no
        # key) → shipped baseline 0; second {"length": -5} (mock-only negative
        # — the sole separating input) → shipped max(0, 0-(-5)) = 5; the
        # None/no-default mutants TypeError inside max() → except → ret 0.
        d, c = mk()
        c._client.xinfo_stream.side_effect = [{}, {"length": -5}]
        with patch.object(RS.logger, "info", autospec=True) as li:
            assert await d.trim_stream() == 5
        assert dict(li.call_args.kwargs["extra"])["removed_count"] == 5

    async def test_first_read_raises_uses_zero_baseline(self):
        # except-branch `current_length = 0` → None mutant (feed key 18):
        # first xinfo RAISES → shipped baseline 0 → max(0, 0-(-5)) = 5;
        # the None mutant TypeErrors there → ret 0 silent.
        d, c = mk()
        c._client.xinfo_stream.side_effect = [Exception("boom"), {"length": -5}]
        with patch.object(RS.logger, "info", autospec=True) as li:
            assert await d.trim_stream() == 5
        assert dict(li.call_args.kwargs["extra"])["removed_count"] == 5

    async def test_removed_one_logs(self):
        # `removed > 1` mutant (feed key 48): shipped logs at removed == 1
        # (MEASURED shape 5→4); the mutant is silent there.
        d, c = mk()
        c._client.xinfo_stream.side_effect = [{"length": 5}, {"length": 4}]
        with patch.object(RS.logger, "info", autospec=True) as li:
            assert await d.trim_stream() == 1
        assert li.call_args.args[0] == "Trimmed stream"
        assert dict(li.call_args.kwargs["extra"]) == {
            "stream_key": "detections:stream",
            "removed_count": 1,
            "new_length": 4,
        }


class TestIsoZReplacement:
    def test_lowercase_z_input_stays_unparsed(self):
        # MEASURED on 3.14: fromisoformat rejects lowercase 'z'; shipped
        # replaces only "Z" → lowercase-z ISO input yields None, while the
        # replace("z", …) mutant parses it to 1704164645.0.
        m = AnalysisStreamMessage.from_stream_entry(
            "2-2", {"pipeline_start_time": "2024-01-02T03:04:05z"}
        )
        assert m.pipeline_start_time is None

    def test_uppercase_z_input_parses(self):
        # belt-and-braces on the same line: shipped DOES parse the Z form
        # (MEASURED 1704164645.0) — kills mutants that break the working path.
        m = AnalysisStreamMessage.from_stream_entry(
            "2-2", {"pipeline_start_time": "2024-01-02T03:04:05Z"}
        )
        assert m.pipeline_start_time == 1704164645.0
