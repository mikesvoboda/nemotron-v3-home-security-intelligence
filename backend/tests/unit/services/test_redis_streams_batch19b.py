"""Batch-19b mutation-kill battery: redis_streams raise-message + log shapes.

Target: the 217 rs18 survivors (``/tmp/redcheck-rs18.log``, rc=0, 156 KILLED
of the 373-key survivor feed). Triage census (``/tmp/rs19-shapes.tsv``,
grouped by feed shape): ~40 raise-message string mutants (None / XX-wrap /
lower / UPPER on the exact error texts) and ~88 log-message + EXTRA-KEY
mutants (message None/XX/case flips, extra=None, extra-kwarg removal, KEY
case renames, value→str(None)). Both are GAP classes — proven killable by
exact-text pins this campaign already ships in 13b/15b — NOT equivalents:
- raise pins: ``str(exc)`` is the shipped contract text; every mutant
  changes it (batch-12b vehicle).
- log pins: message arg EXACT + ``dict(kwargs["extra"])`` EXACT, plus
  NO-CALL assertions where shipped stays silent (trim removed==0, ack
  result==0) and the ``extra``-kwarg-presence pin (analysis BUSYGROUP debug
  ships WITHOUT extra — MEASURED kwargs_keys == []).

Boundary kills by construction (MEASURED shipped vs each mutant):
- trim ``removed > 0``: shipped removed==0 logs NOTHING; ``>= 0`` mutant
  logs at removed==0 (info_calls pin).
- claim ``data is None → continue``: shipped with None-data FIRST + valid
  SECOND returns [5-1]; a ``break`` mutant returns [] — count pin.
- ``entry[:2]``: a 3-tuple entry parses fine under shipped; ``[:3]``
  raises ValueError on unpack → the same test kills it (measured n==1).
- ``analysis_stream_parse_error`` metric label (consume_batches fail path)
  is already pinned by batch-18; this file covers the detection parse-fail
  WARNING text/extra which the feed survivor set contains.

Every expected value MEASURED this session against shipped production via
``/tmp/b19-harness.py`` (→ ``/tmp/b19-probes.json``). Production NOT bent to
any mutant. No kill tallies claimed here — those come only from the rs19b
lane red-check.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis import RedisClient
from backend.services import redis_streams as RS
from backend.services.redis_streams import (
    AnalysisStreamMessage,
    AnalysisStreamService,
    DetectionStreamMessage,
    DetectionStreamService,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def mk(svc_cls=DetectionStreamService, **kw):
    c = MagicMock(spec=RedisClient)
    c._client = AsyncMock()
    return svc_cls(redis_client=c, **kw), c


class TestNotConnectedMessages:
    """MEASURED str(exc) == "Redis client not connected" on all 10 guard sites;
    None/XX/lower/UPPER mutants all change the text."""

    async def test_all_ten_guard_sites_exact_text(self):
        d, c = mk()
        c._client = None
        sites = {
            "_ensure_consumer_group": d._ensure_consumer_group(),
            "add_detection": d.add_detection("cam", 1, "/p"),
            "consume_detections": d.consume_detections("w"),
            "acknowledge": d.acknowledge("1-1"),
            "claim_stale_messages": d.claim_stale_messages("w"),
            "get_stream_info": d.get_stream_info(),
            "get_consumer_group_info": d.get_consumer_group_info(),
            "get_pending_count": d.get_pending_count(),
            "trim_stream": d.trim_stream(),
        }
        for where, coro in sites.items():
            with pytest.raises(RuntimeError) as ei:
                await coro
            assert str(ei.value) == "Redis client not connected", where

    async def test_move_to_dlq_not_connected_exact(self):
        d, c = mk()
        c._client = None
        msg = DetectionStreamMessage(id="1-1", camera_id="c", detection_id=1, file_path="/p")
        with pytest.raises(RuntimeError) as ei:
            await d.move_to_dlq(msg)
        assert str(ei.value) == "Redis client not connected"

    async def test_analysis_not_connected_exact(self):
        a, c = mk(AnalysisStreamService)
        c._client = None
        am = AnalysisStreamMessage(id="1-1", batch_id="b", camera_id="c", detection_ids=[])
        for coro in (
            a._ensure_consumer_group(),
            a.add_batch("b", "c", [1]),
            a.consume_batches("w"),
            a.acknowledge("1-1"),
            a.claim_stale_messages("w"),
            a.move_to_dlq(am),
        ):
            with pytest.raises(RuntimeError) as ei:
                await coro
            assert str(ei.value) == "Redis client not connected"


class TestRequiredFieldMessages:
    """add_detection MEASURED texts; None/XX/UPPER mutants change str(exc)."""

    async def test_three_required_field_texts(self):
        d, _ = mk()
        with pytest.raises(ValueError) as ei:
            await d.add_detection("", 1, "/p")
        assert str(ei.value) == "camera_id is required"
        with pytest.raises(ValueError) as ei:
            await d.add_detection("c", None, "/p")
        assert str(ei.value) == "detection_id is required"
        with pytest.raises(ValueError) as ei:
            await d.add_detection("c", 1, "")
        assert str(ei.value) == "file_path is required"


class TestLogShapesExact:
    """message arg EXACT + extra dict EXACT (keys AND values); shipped silent
    paths pinned by call-count == 0."""

    async def test_ensure_created_info_exact(self):
        d, _ = mk()
        with patch.object(RS.logger, "info", autospec=True) as li:
            await d._ensure_consumer_group()
        assert li.call_args.args[0] == "Created consumer group"
        assert dict(li.call_args.kwargs["extra"]) == {
            "stream_key": "detections:stream",
            "consumer_group": "detection-workers",
        }

    async def test_ensure_busygroup_debug_exact(self):
        d, c = mk()
        c._client.xgroup_create.side_effect = Exception("BUSYGROUP Consumer Group exists")
        with patch.object(RS.logger, "debug", autospec=True) as ld:
            await d._ensure_consumer_group()
        assert ld.call_args.args[0] == "Consumer group already exists"
        assert dict(ld.call_args.kwargs["extra"]) == {
            "stream_key": "detections:stream",
            "consumer_group": "detection-workers",
        }

    async def test_analysis_created_info_exact(self):
        a, _ = mk(AnalysisStreamService)
        with patch.object(RS.logger, "info", autospec=True) as li:
            await a._ensure_consumer_group()
        assert li.call_args.args[0] == "Created analysis consumer group"
        assert dict(li.call_args.kwargs["extra"]) == {
            "stream_key": "analysis:stream",
            "consumer_group": "analysis-workers",
        }

    async def test_analysis_busygroup_debug_no_extra_kwarg(self):
        # MEASURED kwargs_keys == []: shipped debug call has NO extra at all —
        # an extra-adding mutant is a contract change the pin rejects.
        a, c = mk(AnalysisStreamService)
        c._client.xgroup_create.side_effect = Exception("BUSYGROUP boom")
        with patch.object(RS.logger, "debug", autospec=True) as ld:
            await a._ensure_consumer_group()
        assert ld.call_args.args[0] == "Analysis consumer group already exists"
        assert sorted(ld.call_args.kwargs) == []

    async def test_add_detection_debug_exact(self):
        d, c = mk()
        c._client.xadd.return_value = "11-1"
        with patch.object(RS.logger, "debug", autospec=True) as ld:
            await d.add_detection("cam1", 42, "/img/a.jpg", timestamp=100.0)
        assert ld.call_args.args[0] == "Added detection to stream"
        assert dict(ld.call_args.kwargs["extra"]) == {
            "stream_key": "detections:stream",
            "message_id": "11-1",
            "camera_id": "cam1",
            "detection_id": 42,
        }

    async def test_add_batch_debug_exact(self):
        a, c = mk(AnalysisStreamService)
        c._client.xadd.return_value = "22-2"
        with patch.object(RS.logger, "debug", autospec=True) as ld:
            await a.add_batch("b1", "cam2", [3, 4])
        assert ld.call_args.args[0] == "Added batch to analysis stream"
        assert dict(ld.call_args.kwargs["extra"]) == {
            "stream_key": "analysis:stream",
            "message_id": "22-2",
            "batch_id": "b1",
            "detection_count": 2,
        }

    async def test_ack_true_debug_exact_and_false_silent(self):
        d, c = mk()
        c._client.xack.return_value = 1
        with patch.object(RS.logger, "debug", autospec=True) as ld:
            assert await d.acknowledge("9-9") is True
        assert ld.call_args.args[0] == "Acknowledged stream message"
        assert dict(ld.call_args.kwargs["extra"]) == {
            "stream_key": "detections:stream",
            "message_id": "9-9",
        }
        d, c = mk()
        c._client.xack.return_value = 0
        with patch.object(RS.logger, "debug", autospec=True) as ld:
            assert await d.acknowledge("9-9") is False
        assert ld.call_count == 0  # removed>0-style boundary: shipped silent

    async def test_detection_dlq_warning_exact(self):
        d, c = mk()
        c._client.xadd.return_value = "dlq-7"
        c._client.xack.return_value = 1
        msg = DetectionStreamMessage(
            id="3-1",
            camera_id="c",
            detection_id=9,
            file_path="/p",
            raw_data={"q": 1},
            delivery_count=3,
        )
        with (
            patch.object(RS.logger, "warning", autospec=True) as lw,
            patch.object(RS, "record_pipeline_error", autospec=True) as rp,
        ):
            assert await d.move_to_dlq(msg, reason="too_many") == "dlq-7"
        assert lw.call_args.args[0] == "Moved message to DLQ"
        ex = dict(lw.call_args.kwargs["extra"])
        assert ex["original_message_id"] == "3-1"
        assert ex["dlq_message_id"] == "dlq-7"
        assert ex["reason"] == "too_many"
        assert ex["delivery_count"] == 3
        assert rp.call_args.args[0] == "stream_dlq_move"

    async def test_analysis_dlq_warning_exact(self):
        a, c = mk(AnalysisStreamService)
        c._client.xadd.return_value = "adlq-7"
        c._client.xack.return_value = 1
        am = AnalysisStreamMessage(
            id="4-1", batch_id="b9", camera_id="c", detection_ids=[], delivery_count=2
        )
        with (
            patch.object(RS.logger, "warning", autospec=True) as lw,
            patch.object(RS, "record_pipeline_error", autospec=True) as rp,
        ):
            assert await a.move_to_dlq(am) == "adlq-7"
        assert lw.call_args.args[0] == "Moved analysis message to DLQ"
        ex = dict(lw.call_args.kwargs["extra"])
        assert ex["original_message_id"] == "4-1"
        assert ex["dlq_message_id"] == "adlq-7"
        assert ex["batch_id"] == "b9"
        assert rp.call_args.args[0] == "analysis_stream_dlq_move"

    async def test_detection_consume_error_exact_and_reraise(self):
        d, c = mk()
        c._client.xreadgroup.side_effect = ConnectionError("down")
        with patch.object(RS.logger, "error", autospec=True) as le:
            with pytest.raises(ConnectionError):
                await d.consume_detections("w1")
        assert le.call_args.args[0] == "Error consuming from stream"
        assert dict(le.call_args.kwargs["extra"]) == {
            "stream_key": "detections:stream",
            "consumer_group": "detection-workers",
            "consumer_name": "w1",
            "error": "down",
        }

    async def test_detection_claim_error_exact_and_reraise(self):
        d, c = mk()
        c._client.xautoclaim.side_effect = ConnectionError("down2")
        with patch.object(RS.logger, "error", autospec=True) as le:
            with pytest.raises(ConnectionError):
                await d.claim_stale_messages("w2")
        assert le.call_args.args[0] == "Error claiming stale messages"
        assert dict(le.call_args.kwargs["extra"]) == {
            "stream_key": "detections:stream",
            "consumer_name": "w2",
            "error": "down2",
        }

    async def test_detection_claim_info_exact(self):
        d, c = mk()
        ok = ("5-1", {"camera_id": "c", "detection_id": "7", "file_path": "/p"})
        c._client.xautoclaim.return_value = ["0-0", [ok], []]
        c._client.xpending_range.return_value = [{"times_delivered": 2}]
        with patch.object(RS.logger, "info", autospec=True) as li:
            out = await d.claim_stale_messages("w")
        assert [m.id for m in out] == ["5-1"]
        assert li.call_args.args[0] == "Claimed stale messages"
        assert dict(li.call_args.kwargs["extra"]) == {
            "stream_key": "detections:stream",
            "consumer_name": "w",
            "claimed_count": 1,
        }

    async def test_analysis_claim_info_exact(self):
        a, c = mk(AnalysisStreamService)
        ok = ("7-7", {"batch_id": "b", "camera_id": "c", "detection_ids": "[1]"})
        c._client.xautoclaim.return_value = ["0-0", [ok], []]
        c._client.xpending_range.return_value = [{"times_delivered": 4}]
        with patch.object(RS.logger, "info", autospec=True) as li:
            out = await a.claim_stale_messages("w")
        assert [(m.id, m.delivery_count) for m in out] == [("7-7", 4)]
        assert li.call_args.args[0] == "Claimed stale analysis messages"
        # MEASURED: analysis claim info extra has NO stream_key (unlike detection)
        assert dict(li.call_args.kwargs["extra"]) == {"consumer_name": "w", "claimed_count": 1}

    async def test_trim_info_exact_and_removed_zero_silent(self):
        d, c = mk()
        c._client.xinfo_stream.side_effect = [{"length": 10}, {"length": 4}]
        with patch.object(RS.logger, "info", autospec=True) as li:
            assert await d.trim_stream() == 6
        assert li.call_args.args[0] == "Trimmed stream"
        assert dict(li.call_args.kwargs["extra"]) == {
            "stream_key": "detections:stream",
            "removed_count": 6,
            "new_length": 4,
        }
        d, c = mk()
        c._client.xinfo_stream.side_effect = [{"length": 5}, {"length": 5}]
        with patch.object(RS.logger, "info", autospec=True) as li:
            assert await d.trim_stream() == 0
            assert li.call_count == 0  # `>= 0` mutant logs here — kills the boundary

    async def test_parse_fail_warning_exact(self):
        # detection parse-fail warning text + extra (message_id str, error str
        # of int('abc')); MEASURED error text verbatim.
        d, c = mk()
        c._client.xreadgroup.return_value = [
            [
                "detections:stream",
                [
                    ("9-1", {"camera_id": "c", "detection_id": "abc", "file_path": "/p"}),
                    ("9-2", {"camera_id": "c", "detection_id": "3", "file_path": "/p"}),
                ],
            ]
        ]
        with (
            patch.object(RS.logger, "warning", autospec=True) as lw,
            patch.object(RS, "record_pipeline_error", autospec=True) as rp,
        ):
            out = await d.consume_detections("w")
        assert len(out) == 1
        assert lw.call_args.args[0] == "Failed to parse stream message"
        assert dict(lw.call_args.kwargs["extra"]) == {
            "message_id": "9-1",
            "error": "invalid literal for int() with base 10: 'abc'",
        }
        assert rp.call_args.args[0] == "stream_parse_error"


class TestClaimLoopShapes:
    """continue-vs-break and entry[:2]-vs-[:3] boundary shapes (MEASURED)."""

    async def test_none_data_first_continues_not_breaks(self):
        d, c = mk()
        ok = ("5-1", {"camera_id": "c", "detection_id": "7", "file_path": "/p"})
        c._client.xautoclaim.return_value = ["0-0", [(None, None), ok], []]
        c._client.xpending_range.return_value = [{"times_delivered": 2}]
        with patch.object(RS.logger, "info", autospec=True) as li:
            out = await d.claim_stale_messages("w")
        # MEASURED shipped: the None entry is skipped, the valid one CLAIMED
        # (a break mutant returns [] -> count pin kills it).
        assert [m.id for m in out] == ["5-1"]
        assert dict(li.call_args.kwargs["extra"])["claimed_count"] == 1

    async def test_three_element_entry_unpacks_first_two(self):
        # MEASURED: shipped entry[:2] parses a 3-tuple; the [:3] mutant raises
        # ValueError on unpack (not caught) -> this test kills it.
        d, c = mk()
        c._client.xautoclaim.return_value = [
            "0-0",
            [("6-1", {"camera_id": "c", "detection_id": "8", "file_path": "/p"}, "X3")],
            [],
        ]
        c._client.xpending_range.return_value = [{"times_delivered": 1}]
        out = await d.claim_stale_messages("w")
        assert [m.id for m in out] == ["6-1"]
        assert [m.delivery_count for m in out] == [1]
