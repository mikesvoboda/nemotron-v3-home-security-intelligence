"""Batch-19d mutation-kill battery: redis_streams residue the 19b battery left.

Target: the 31 rs19b survivors' GAP subset (rs19b: 186 KILLED / 31 SURVIVED,
`/tmp/redcheck-rs19b.log`, rc=0, source clean — battery vs the 217-key rs18
survivor feed). rs19c's structural pins handle the trim/ISO keys; THIS file
covers the ten shapes neither 19b nor 19c reaches, all MEASURED against
shipped via /tmp/b19d-harness.py -> /tmp/b19d-probes.json:

- add_detection XADD FIELDS dict (feed add_detection__mutmut_65/66: the
  "camera_id" KEY -> "XXcamera_idXX"/"CAMERA_ID"): the shipped stream-field
  dict is the wire contract consumed by from_stream_entry — pinned EXACT
  (keys + values: {"camera_id","detection_id","file_path","timestamp"} with
  detection_id str-cast and the passed timestamp str-cast), plus stream key
  "detections:stream" positional and the {approximate, maxlen} kwargs names.
  19b only pinned the DEBUG log extra, never the xadd call.
- add_batch XADD FIELDS dict (add_batch__mutmut_39 "batch_id" rename): same
  pin on "analysis:stream"; detection_ids is MEASURED json.dumps ->
  "[3, 4]"; shipped fills timestamp=str(time.time()) (dynamic) — pinned
  structurally (float() parses > 0), names pinned exactly.
- consume_batches success (consume_batches__mutmut_21 message_id -> None,
  _23 delivery_count -> None, _27 delivery_count -> 2): MEASURED ids
  ["7-1"] / delivery_counts [1] — all three diverge from that pin.
- analysis claim entry[:3] (claim_stale_messages__mutmut_21): a 3-element
  entry parses under shipped entry[:2] (MEASURED n 1, ids ["9-1"]); the
  [:3] mutant unpacks 3 into 2 -> ValueError -> parse-fail path -> n 0.
- detection claim parse-fail WARNING (claim_stale_messages__mutmut_77/78/79
  "error" key rename / str(None)): MEASURED message "Failed to parse
  claimed message" (NOT consume's "Failed to parse stream message" —
  distinct text, why the 19b consume pin missed this) + extra EXACT
  {"message_id": "4-1", "error": "invalid literal for int() with base 10:
  'abc'"} + the "Claimed stale messages" info NOT firing at zero parsed
  (MEASURED: only info call is "Created consumer group", call_count 1).

CORRECTIONS to batch-19c's equivalence list (each MEASURED this session —
right verdicts, wrong or over-broad reasoning):
- DetectionStreamMessage.from_stream_entry__mutmut_8 ("timestamp","") ->
  ("timestamp","XXXX"): NOT a falsy-same-branch story (the mutant default
  is TRUTHY) but EQUIVALENT anyway: MEASURED _parse_timestamp("XXXX")
  raises ValueError, caught by the same ``except`` -> ts = time.time(),
  identical to the shipped falsy branch. Default value unobservable.
- AnalysisStreamMessage.from_stream_entry__mutmut_8 ("detection_ids",
  "[]") -> "XX[]XX": EQUIVALENT — json.loads("XX[]XX") raises, the SAME
  except yields [] exactly like shipped's "[]" parse. (19c's None/no-
  default row for this site stays correct.)
- from_stream_entry__mutmut_24 replace("Z",…) -> replace("XXZXX",…):
  EQUIVALENT — the XX pattern never matches, so the raw "…Z" reaches
  fromisoformat, which on 3.14 ACCEPTS trailing Z directly (MEASURED
  datetime.fromisoformat("2024-01-02T03:04:05Z").timestamp() ==
  1704164645.0 == the shipped replace-then-parse value); non-Z inputs
  untouched by either. No input separates them.
- consume_batches delivery_count=1 REMOVAL (_26): default IS 1 (signature
  `delivery_count: int = 1`) — binding identity, EQUIVALENT. The 19c note
  said the "19b delivery_count pins" kill the None/=2 siblings — 19b had
  no analysis-CONSUME dc pin (rs19b proves it: 21/23/27 survived); they
  are real gaps and are killed HERE.
- consume_detections delivery_count=1 REMOVAL (consume_detections__mutmut_
  30): same default-identity EQUIVALENT.
- add_detection str-cast `or True` (_41), get_stream_info first-entry
  default mutants (_58/_60), trim except-branch new_length (_45/_46),
  timestamp/detection_ids None-defaults: dispositions UNCHANGED from 19c
  (identity / guard-suppressed / unreachable reads).

Every expected value MEASURED against shipped production this session;
production NOT bent to any mutant. No kill tallies claimed here — those
come only from the rs19d lane red-check.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis import RedisClient
from backend.services import redis_streams as RS
from backend.services.redis_streams import (
    AnalysisStreamService,
    DetectionStreamService,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def mk(svc_cls=DetectionStreamService, **kw):
    c = MagicMock(spec=RedisClient)
    c._client = AsyncMock()
    return svc_cls(redis_client=c, **kw), c


class TestXaddFieldsContract:
    """Wire-format pins the log-extra pins never saw."""

    async def test_add_detection_xadd_fields_exact(self):
        # kills add_detection__65/66 (camera_id KEY rename/CASE in the FIELDS
        # dict) — MEASURED dict verbatim.
        d, c = mk()
        c._client.xadd.return_value = "11-1"
        await d.add_detection("cam1", 42, "/img/a.jpg", timestamp=100.0)
        call = c._client.xadd.call_args
        assert call.args[0] == "detections:stream"
        assert call.args[1] == {
            "camera_id": "cam1",
            "detection_id": "42",
            "file_path": "/img/a.jpg",
            "timestamp": "100.0",
        }
        assert sorted(call.kwargs) == ["approximate", "maxlen"]

    async def test_add_batch_xadd_fields_exact(self):
        # kills add_batch__39 ("batch_id" -> "XXbatch_idXX" in FIELDS);
        # shipped timestamp is time.time()-derived -> structural pin.
        a, ca = mk(AnalysisStreamService)
        ca._client.xadd.return_value = "22-2"
        await a.add_batch("b1", "cam2", [3, 4])
        call = ca._client.xadd.call_args
        assert call.args[0] == "analysis:stream"
        fields = call.args[1]
        assert sorted(fields) == ["batch_id", "camera_id", "detection_ids", "timestamp"]
        assert fields["batch_id"] == "b1"
        assert fields["camera_id"] == "cam2"
        assert fields["detection_ids"] == "[3, 4]"  # MEASURED json.dumps shape
        assert float(fields["timestamp"]) > 0


class TestAnalysisConsumeClaimShapes:
    async def test_consume_batches_success_id_and_dc(self):
        # kills consume_batches__21 (message_id None), __23 (dc None),
        # __27 (dc 2): MEASURED ids ["7-1"] dcs [1].
        a, ca = mk(AnalysisStreamService)
        ca._client.xreadgroup.return_value = [
            [
                "analysis:stream",
                [("7-1", {"batch_id": "b", "camera_id": "c", "detection_ids": "[1,2]"})],
            ]
        ]
        msgs = await a.consume_batches("w")
        assert [(m.id, m.delivery_count) for m in msgs] == [("7-1", 1)]

    async def test_analysis_claim_three_element_entry(self):
        # kills claim_stale_messages__21 (entry[:3] -> unpack ValueError ->
        # parse-fail path): shipped [:2] claims it. MEASURED n 1 id "9-1".
        a, ca = mk(AnalysisStreamService)
        ca._client.xautoclaim.return_value = [
            "0-0",
            [("9-1", {"batch_id": "b", "camera_id": "c", "detection_ids": "[5]"}, "X3")],
            [],
        ]
        ca._client.xpending_range.return_value = [{"times_delivered": 2}]
        msgs = await a.claim_stale_messages("w")
        assert [m.id for m in msgs] == ["9-1"]


class TestDetectionClaimParseFail:
    async def test_claim_parse_fail_warning_exact(self):
        # kills claim_stale_messages__77/78 (error KEY rename/CASE) and
        # __79 (str(None)): distinct text from the consume parse-fail pin
        # ("claimed"), extra pinned EXACT incl. the int() error text.
        d, c = mk()
        c._client.xautoclaim.return_value = [
            "0-0",
            [("4-1", {"camera_id": "c", "detection_id": "abc", "file_path": "/p"})],
            [],
        ]
        c._client.xpending_range.return_value = [{"times_delivered": 2}]
        with (
            patch.object(RS.logger, "warning", autospec=True) as lw,
            patch.object(RS.logger, "info", autospec=True) as li,
        ):
            out = await d.claim_stale_messages("w")
        assert out == []
        assert lw.call_args.args[0] == "Failed to parse claimed message"
        assert dict(lw.call_args.kwargs["extra"]) == {
            "message_id": "4-1",
            "error": "invalid literal for int() with base 10: 'abc'",
        }
        # MEASURED: the ONLY info call on this path is the consumer-group
        # ensure — the "Claimed stale messages" info does NOT fire when
        # zero messages parsed (an always-log mutant -> call_count 2 dies).
        assert li.call_count == 1
        assert li.call_args.args[0] == "Created consumer group"
