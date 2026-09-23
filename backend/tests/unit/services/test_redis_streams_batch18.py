"""Batch-18 mutation-kill battery: redis_streams BATTERY-ONLY survivors.

Target: the 373 survivors of the rs11b red-check (batch-11 battery, 481/854
KILLED, log at ``/tmp/redcheck-rs11b.log``) that neither the shipped suites
(``test_redis_streams*.py``) nor batch-11 already kill. Mechanical literal
coverage analysis (``/tmp/rs18-gaps.tsv``): 76 literal-bearing gaps — of which
73 are the batch-7-precedent log-text/extra-key cluster (NOT asserted here) and
3 are the ``record_pipeline_error`` METRIC LABELS (asserted: labels are
consumed by alerting, not observability) — plus the literal-less call-arg /
state / default-value mutants enumerated below.

EVERY expected value below was MEASURED this session against shipped
production via ``/tmp/b18-harness.py`` (dumps ``/tmp/b18-probes.json``; extra
edge probes ``/tmp/b18-extra.py`` → ``/tmp/b18-extra.json``). Production was
NOT bent to any mutant. No kill tallies claimed here — those come only from
the rs18 lane red-check.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis import RedisClient
from backend.services.redis_streams import (
    ANALYSIS_STREAM_KEY,
    DEFAULT_BLOCK_MS,
    DEFAULT_CLAIM_MIN_IDLE_MS,
    DEFAULT_MAX_DELIVERY_COUNT,
    DEFAULT_STREAM_MAXLEN,
    DETECTION_CONSUMER_GROUP,
    DETECTION_STREAM_KEY,
    AnalysisStreamMessage,
    AnalysisStreamService,
    DetectionStreamMessage,
    DetectionStreamService,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def mk(svc_cls=DetectionStreamService, **kw):
    """MEASURED carrier (b18-harness.mk): spec'd RedisClient, AsyncMock _client."""
    c = MagicMock(spec=RedisClient)
    c._client = AsyncMock()
    return svc_cls(redis_client=c, **kw), c


class TestInitState:
    """__init__ mutants 9/10: stored state, verbatim MEASURED values."""

    def test_detection_stored_state(self):
        s, _ = mk()
        assert s._stream_key == "detections:stream"
        assert s._dlq_key == "detections:stream:dlq"  # f-string:dlq suffix
        assert s._consumer_group == "detection-workers"
        assert s._maxlen == DEFAULT_STREAM_MAXLEN == 10000
        assert s._block_ms == DEFAULT_BLOCK_MS == 5000
        assert s._claim_min_idle_ms == DEFAULT_CLAIM_MIN_IDLE_MS == 60000
        assert s._max_delivery_count == DEFAULT_MAX_DELIVERY_COUNT == 3
        assert s._group_created is False  # mutmut_10 None

    def test_analysis_stored_state(self):
        a, _ = mk(AnalysisStreamService)
        assert a._stream_key == "analysis:stream"
        assert a._dlq_key == "analysis:stream:dlq"
        assert a._consumer_group == "analysis-workers"
        assert a._max_delivery_count == 3


class TestEnsureConsumerGroup:
    """_ensure_consumer_group: xgroup_create call shape + flag + BUSYGROUP."""

    async def test_create_call_shape_and_flag(self):
        s, c = mk()
        await s._ensure_consumer_group()
        call = c._client.xgroup_create.call_args
        assert call.args == ("detections:stream", "detection-workers")
        assert call.kwargs == {"id": "0", "mkstream": True}
        assert s._group_created is True
        # second call: guarded by flag, NO redis round-trip
        await s._ensure_consumer_group()
        assert c._client.xgroup_create.await_count == 1

    async def test_custom_keys_forwarded(self):
        s, c = mk(DetectionStreamService, stream_key="k9", consumer_group="g9")
        await s._ensure_consumer_group()
        assert c._client.xgroup_create.call_args.args == ("k9", "g9")

    async def test_busygroup_swallowed_flag_set(self):
        s, c = mk()
        c._client.xgroup_create.side_effect = Exception(
            "BUSYGROUP Consumer Group name already exists"
        )
        await s._ensure_consumer_group()  # MEASURED: does NOT raise
        assert s._group_created is True

    async def test_other_error_raises_and_flag_unset(self):
        s, c = mk()
        c._client.xgroup_create.side_effect = ConnectionError("boom")
        with pytest.raises(ConnectionError):
            await s._ensure_consumer_group()
        assert s._group_created is False

    async def test_analysis_side_group_created(self):
        # MEASURED parallel path; analysis service sets its own flag
        a, c = mk(AnalysisStreamService)
        await a._ensure_consumer_group()
        assert c._client.xgroup_create.call_args.args == ("analysis:stream", "analysis-workers")
        assert a._group_created is True


class TestShouldMoveToDlqBoundary:
    """delivery_count >= max: False at 2, True AT 3 (==), True at 4."""

    async def test_boundary(self):
        s, _ = mk(max_delivery_count=3)

        def msg(dc):
            return DetectionStreamMessage(
                id="1-0", camera_id="c", detection_id=1, file_path="/f", delivery_count=dc
            )

        assert await s.should_move_to_dlq(msg(2)) is False
        assert await s.should_move_to_dlq(msg(3)) is True
        assert await s.should_move_to_dlq(msg(4)) is True


class TestAddDetectionFields:
    """add_detection: complete xadd fields dict + clock use."""

    async def test_full_fields_with_patched_clock(self):
        with patch("backend.services.redis_streams.time.time", autospec=True) as tt:
            tt.return_value = 1234.5
            s, c = mk()
            c._client.xadd.return_value = "11-0"
            rid = await s.add_detection(
                camera_id="cam1",
                detection_id=42,
                file_path="/p/img.jpg",
                confidence=0.75,
                object_type="person",
                extra_fields={"n": 5, "s": "abc"},
            )
            call = c._client.xadd.call_args
            assert rid == "11-0"
            assert call.args[0] == "detections:stream"
            # MEASURED: EXACT dict — every key, every str() cast, order-insensitive
            assert call.args[1] == {
                "camera_id": "cam1",
                "detection_id": "42",
                "file_path": "/p/img.jpg",
                "timestamp": "1234.5",  # str(time.time()) fallback
                "confidence": "0.75",
                "object_type": "person",
                "n": "5",  # extra_fields non-str cast
                "s": "abc",  # extra_fields str passthrough
            }
            assert call.kwargs == {"maxlen": DEFAULT_STREAM_MAXLEN, "approximate": True}

    async def test_explicit_timestamp_no_clock(self):
        s, c = mk()
        c._client.xadd.return_value = "x"
        await s.add_detection(camera_id="cam1", detection_id=42, file_path="/p", timestamp=99.0)
        fields = c._client.xadd.call_args.args[1]
        assert fields["timestamp"] == "99.0"
        assert sorted(fields) == ["camera_id", "detection_id", "file_path", "timestamp"]

    async def test_guard_message_verbatim(self):
        s, c = mk()
        c._client = None
        with pytest.raises(RuntimeError, match=r"^Redis client not connected$"):
            await s.add_detection(camera_id="c", detection_id=1, file_path="/f")


class TestMoveToDlq:
    """move_to_dlq: DLQ xadd fields/kwargs, ack args, METRIC LABELS."""

    async def test_detection_dlq_full(self):
        with patch("backend.services.redis_streams.time.time", autospec=True) as tt:
            tt.return_value = 1234.5
            with patch(
                "backend.services.redis_streams.record_pipeline_error", autospec=True
            ) as rpe:
                s, c = mk(DetectionStreamService, maxlen=100)
                c._client.xadd.return_value = "99-0"
                c._client.xack.return_value = 1
                msg = DetectionStreamMessage(
                    id="7-0",
                    camera_id="c",
                    detection_id=42,
                    file_path="/f",
                    timestamp=1.5,
                    delivery_count=3,
                    raw_data={"camera_id": "c", "detection_id": "42"},
                )
                res = await s.move_to_dlq(msg, reason="poison")
                assert res == "99-0"
                call = c._client.xadd.call_args
                assert call.args[0] == "detections:stream:dlq"
                assert call.args[1] == {
                    "camera_id": "c",  # raw_data spread, str()-cast
                    "detection_id": "42",
                    "original_message_id": "7-0",
                    "dlq_reason": "poison",
                    "dlq_timestamp": "1234.5",
                    "delivery_count": "3",
                }
                assert call.kwargs == {"maxlen": 100, "approximate": True}
                # original acked on the MAIN stream with the group
                assert c._client.xack.call_args.args == (
                    "detections:stream",
                    "detection-workers",
                    "7-0",
                )
                # METRIC LABEL (not log text): alerting key, killable
                assert [x.args for x in rpe.call_args_list] == [("stream_dlq_move",)]

    async def test_analysis_dlq_full_and_label(self):
        with patch("backend.services.redis_streams.time.time", autospec=True) as tt:
            tt.return_value = 1234.5
            with patch(
                "backend.services.redis_streams.record_pipeline_error", autospec=True
            ) as rpe:
                a, ac = mk(AnalysisStreamService)
                ac._client.xadd.return_value = "a9-0"
                ac._client.xack.return_value = 1
                am = AnalysisStreamMessage(
                    id="5-0",
                    batch_id="b",
                    camera_id="c",
                    detection_ids=[1],
                    delivery_count=2,
                    raw_data={"batch_id": "b"},
                )
                res = await a.move_to_dlq(am)
                assert res == "a9-0"
                call = ac._client.xadd.call_args
                assert call.args[0] == "analysis:stream:dlq"
                assert call.args[1] == {
                    "batch_id": "b",
                    "original_message_id": "5-0",
                    "dlq_reason": "max_delivery_exceeded",  # shipped default
                    "dlq_timestamp": "1234.5",
                    "delivery_count": "2",
                }
                assert [x.args for x in rpe.call_args_list] == [("analysis_stream_dlq_move",)]


class TestTrimStream:
    """trim_stream: removed-count arithmetic + xtrim kwargs (all MEASURED)."""

    async def test_custom_maxlen_removes(self):
        s, c = mk(DetectionStreamService, maxlen=500)
        c._client.xinfo_stream.side_effect = [{"length": 10}, {"length": 4}]
        assert await s.trim_stream(maxlen=7) == 6
        call = c._client.xtrim.call_args
        assert call.args == ("detections:stream",)
        assert call.kwargs == {"maxlen": 7, "approximate": True}
        assert [x.args for x in c._client.xinfo_stream.call_args_list] == [
            ("detections:stream",),
            ("detections:stream",),
        ]

    async def test_default_maxlen_used_when_none(self):
        s, c = mk(DetectionStreamService, maxlen=500)
        c._client.xinfo_stream.side_effect = [{"length": 10}, {"length": 4}]
        assert await s.trim_stream() == 6
        assert c._client.xtrim.call_args.kwargs["maxlen"] == 500  # _maxlen, not DEFAULT

    async def test_grew_returns_zero(self):
        s, _ = mk()
        c = s._redis._client
        c.xinfo_stream.side_effect = [{"length": 5}, {"length": 8}]
        assert await s.trim_stream() == 0  # max(0, neg)

    async def test_first_info_fails_zero(self):
        s, c = mk()
        c._client.xinfo_stream.side_effect = [Exception("gone"), {"length": 2}]
        assert await s.trim_stream() == 0

    async def test_second_info_fails_zero(self):
        s, c = mk()
        c._client.xinfo_stream.side_effect = [{"length": 9}, Exception("gone2")]
        assert await s.trim_stream() == 0

    async def test_missing_length_defaults(self):
        s, c = mk()
        c._client.xinfo_stream.side_effect = [{}, {"length": 0}]
        assert await s.trim_stream() == 0  # both lengths default 0 (MEASURED)
        s, c = mk()
        c._client.xinfo_stream.side_effect = [{"length": 10}, {}]
        assert await s.trim_stream() == 10  # new_length defaults 0 (MEASURED)

    async def test_first_exception_with_second_zero(self):
        s, c = mk()
        c._client.xinfo_stream.side_effect = [Exception("boom"), {"length": 0}]
        assert await s.trim_stream() == 0


class TestGetStreamInfo:
    """Mapping keys + .get defaults + no-such-key fallback (case-folded)."""

    async def test_full_mapping(self):
        s, c = mk()
        c._client.xinfo_stream.return_value = {
            "length": 12,
            "radix-tree-keys": 3,
            "radix-tree-nodes": 9,
            "groups": 2,
            "last-generated-id": "16-0",
            "first-entry": ["1-0", {}],
        }
        assert await s.get_stream_info() == {
            "length": 12,
            "radix_tree_keys": 3,
            "radix_tree_nodes": 9,
            "groups": 2,
            "last_entry_id": "16-0",
            "first_entry_id": "1-0",
        }

    async def test_empty_reply_defaults(self):
        s, c = mk()
        c._client.xinfo_stream.return_value = {}
        assert await s.get_stream_info() == {
            "length": 0,
            "radix_tree_keys": 0,
            "radix_tree_nodes": 0,
            "groups": 0,
            "last_entry_id": "",
            "first_entry_id": "",
        }

    async def test_empty_first_entry_falsy(self):
        s, c = mk()
        c._client.xinfo_stream.return_value = {"length": 1, "first-entry": []}
        info = await s.get_stream_info()
        assert info["first_entry_id"] == ""  # falsy branch, NOT ["" ]-indexed

    async def test_no_such_key_fallback_both_cases(self):
        s, c = mk()
        c._client.xinfo_stream.side_effect = Exception(
            "ERR The XREAD GROUP subcommand is not an integer: no such key"
        )
        assert (await s.get_stream_info())["length"] == 0
        s, c = mk()
        c._client.xinfo_stream.side_effect = Exception("NO SUCH KEY")  # .lower() fold MEASURED
        assert await s.get_stream_info() == {
            "length": 0,
            "radix_tree_keys": 0,
            "radix_tree_nodes": 0,
            "groups": 0,
            "last_entry_id": "",
            "first_entry_id": "",
        }

    async def test_other_error_propagates(self):
        s, c = mk()
        c._client.xinfo_stream.side_effect = Exception("WRONGTYPE")
        with pytest.raises(Exception, match="WRONGTYPE"):
            await s.get_stream_info()


class TestGetConsumerGroupInfo:
    async def test_match_returns_group(self):
        s, c = mk()
        c._client.xinfo_groups.return_value = [
            {
                "name": DETECTION_CONSUMER_GROUP,
                "consumers": 2,
                "pending": 7,
                "last-delivered-id": "5-0",
            }
        ]
        assert await s.get_consumer_group_info() == {
            "name": "detection-workers",
            "consumers": 2,
            "pending": 7,
            "last_delivered_id": "5-0",
        }

    async def test_nomatch_returns_zeroed_group(self):
        s, c = mk()
        c._client.xinfo_groups.return_value = [
            {"name": "other", "consumers": 9, "pending": 9, "last-delivered-id": "9"}
        ]
        assert await s.get_consumer_group_info() == {
            "name": "detection-workers",
            "consumers": 0,
            "pending": 0,
            "last_delivered_id": "",
        }

    async def test_missing_keys_default(self):
        s, c = mk()
        c._client.xinfo_groups.return_value = [{"name": DETECTION_CONSUMER_GROUP}]
        assert await s.get_consumer_group_info() == {
            "name": "detection-workers",
            "consumers": 0,
            "pending": 0,
            "last_delivered_id": "",
        }

    async def test_no_such_key_fallback(self):
        s, c = mk()
        c._client.xinfo_groups.side_effect = Exception("no such key")
        assert (await s.get_consumer_group_info())["consumers"] == 0


class TestGetPendingCount:
    async def test_total_and_per_consumer(self):
        s, c = mk()
        c._client.xpending.return_value = {
            "pending": 5,
            "consumers": [{"name": "c1", "pending": 2}, {"name": "c2", "pending": 3}],
        }
        assert await s.get_pending_count() == 5
        assert await s.get_pending_count("c1") == 2
        assert await s.get_pending_count("c2") == 3
        assert await s.get_pending_count("zz") == 0  # miss -> 0

    async def test_none_reply_zero(self):
        s, c = mk()
        c._client.xpending.return_value = None
        assert await s.get_pending_count() == 0

    async def test_partial_rows(self):
        s, c = mk()
        c._client.xpending.return_value = {"consumers": [{"name": "c1"}]}
        assert await s.get_pending_count("c1") == 0  # consumer pending default
        assert await s.get_pending_count() == 0  # top-level pending default

    async def test_no_such_key_zero(self):
        s, c = mk()
        c._client.xpending.side_effect = Exception("no such key")
        assert await s.get_pending_count() == 0


class TestClaimStaleDetection:
    """claim_stale_messages: xautoclaim/pending_range call shape + rows."""

    def _data(self):
        return {
            "camera_id": "cam1",
            "detection_id": "42",
            "file_path": "/f",
            "timestamp": "100.5",
            "object_type": "person",
        }

    async def test_full_args_and_dict_row(self):
        s, c = mk(DetectionStreamService, claim_min_idle_ms=4321)
        c._client.xautoclaim.return_value = ("0-0", [("3-0", self._data())], [])
        c._client.xpending_range.return_value = [
            {
                "message_id": "3-0",
                "consumer": "old",
                "time_since_delivered": 1000,
                "times_delivered": 4,
            }
        ]
        msgs = await s.claim_stale_messages("worker-9", count=7)
        call = c._client.xautoclaim.call_args
        assert call.args == ("detections:stream", "detection-workers", "worker-9", 4321)
        assert call.kwargs == {"start_id": "0-0", "count": 7}
        assert c._client.xpending_range.call_args.kwargs == {"min": "3-0", "max": "3-0", "count": 1}
        assert len(msgs) == 1
        assert msgs[0].id == "3-0"
        assert msgs[0].delivery_count == 4  # from dict row times_delivered
        assert msgs[0].camera_id == "cam1"
        assert msgs[0].timestamp == 100.5

    async def test_positional_row_and_default_count_and_none_skip(self):
        s, c = mk()
        c._client.xautoclaim.return_value = ("0-0", [("3-0", self._data()), ("4-0", None)], [])
        c._client.xpending_range.return_value = [["3-0", "old", 1000, 6]]
        msgs = await s.claim_stale_messages("w")
        assert len(msgs) == 1  # (4-0, None) deleted-entry skipped
        assert msgs[0].delivery_count == 6  # positional row[3] fallback
        assert c._client.xautoclaim.call_args.kwargs == {"start_id": "0-0", "count": 10}

    async def test_empty_and_short_replies(self):
        s, c = mk()
        c._client.xautoclaim.return_value = ("0-0", [], ["del"])
        assert await s.claim_stale_messages("w") == []
        s, c = mk()
        c._client.xautoclaim.return_value = ("0-0",)
        assert await s.claim_stale_messages("w") == []  # len(result) <= 1 -> no entries

    async def test_error_propagates(self):
        s, c = mk()
        c._client.xautoclaim.side_effect = ConnectionError("down")
        with pytest.raises(ConnectionError):
            await s.claim_stale_messages("w")


class TestAcknowledge:
    """xack truthiness boundary (rc=0 False, 1 True, 2 True) + ANALYSIS xack args."""

    async def test_detection_rc(self):
        for rc, expect in ((0, False), (1, True), (2, True)):
            s, c = mk()
            c._client.xack.return_value = rc
            assert await s.acknowledge("3-0") is expect

    async def test_analysis_rc_and_args(self):
        for rc, expect in ((0, False), (1, True), (2, True)):
            a, c = mk(AnalysisStreamService)
            c._client.xack.return_value = rc
            assert await a.acknowledge("3-0") is expect
        a, c = mk(AnalysisStreamService)
        c._client.xack.return_value = 1
        await a.acknowledge("3-0")
        assert c._client.xack.call_args.args == ("analysis:stream", "analysis-workers", "3-0")


class TestAddBatch:
    async def test_fields_and_kwargs(self):
        with patch("backend.services.redis_streams.time.time", autospec=True) as tt:
            tt.return_value = 1234.5
            a, c = mk(AnalysisStreamService, maxlen=250)
            c._client.xadd.return_value = "21-0"
            res = await a.add_batch("b-1", "cam1", [1, 2, 3])
            assert res == "21-0"
            call = c._client.xadd.call_args
            assert call.args[0] == "analysis:stream"
            assert call.args[1] == {
                "batch_id": "b-1",
                "camera_id": "cam1",
                "detection_ids": "[1, 2, 3]",  # json.dumps
                "timestamp": "1234.5",
            }
            assert call.kwargs == {"maxlen": 250, "approximate": True}

    async def test_pst_and_empty_ids(self):
        with patch("backend.services.redis_streams.time.time", autospec=True) as tt:
            tt.return_value = 1234.5
            a, c = mk(AnalysisStreamService)
            c._client.xadd.return_value = "22-0"
            await a.add_batch("b-2", "cam1", [9], pipeline_start_time=1700.0)
            assert c._client.xadd.call_args.args[1] == {
                "batch_id": "b-2",
                "camera_id": "cam1",
                "detection_ids": "[9]",
                "timestamp": "1234.5",
                "pipeline_start_time": "1700.0",
            }
            a, c = mk(AnalysisStreamService)
            c._client.xadd.return_value = "x"
            await a.add_batch("b", "c", [])
            assert c._client.xadd.call_args.args[1]["detection_ids"] == "[]"


class TestAnalysisMessageFromStreamEntry:
    def test_float_ids_and_pst(self):
        data = {
            "batch_id": "b-7",
            "camera_id": "cam7",
            "detection_ids": "[1, 2, 3]",
            "pipeline_start_time": "1700000000.0",
        }
        m = AnalysisStreamMessage.from_stream_entry("1-0", data)
        assert m.id == "1-0"
        assert (m.batch_id, m.camera_id) == ("b-7", "cam7")
        assert m.detection_ids == [1, 2, 3]
        assert m.pipeline_start_time == 1700000000.0
        assert m.delivery_count == 1
        assert m.raw_data is data
        assert m.to_queue_dict() == {
            "batch_id": "b-7",
            "camera_id": "cam7",
            "detection_ids": [1, 2, 3],
            "pipeline_start_time": "2023-11-14T22:13:20+00:00",  # ISO for worker
        }

    def test_iso_pst(self):
        m = AnalysisStreamMessage.from_stream_entry(
            "2-0", {"batch_id": "b", "pipeline_start_time": "2026-01-02T03:04:05Z"}
        )
        assert m.pipeline_start_time == 1767323045.0  # Z -> +00:00 replace MEASURED

    def test_empty_defaults(self):
        m = AnalysisStreamMessage.from_stream_entry("3-0", {})
        assert m.batch_id == ""
        assert m.camera_id == ""
        assert m.detection_ids == []
        assert m.pipeline_start_time is None
        assert m.delivery_count == 1
        assert sorted(m.to_queue_dict()) == ["batch_id", "camera_id", "detection_ids"]

    def test_bad_ids_fallbacks(self):
        assert (
            AnalysisStreamMessage.from_stream_entry(
                "4-0", {"detection_ids": "notjson"}
            ).detection_ids
            == []
        )
        assert (
            AnalysisStreamMessage.from_stream_entry("5-0", {"detection_ids": None}).detection_ids
            == []
        )

    def test_bad_pst_none(self):
        assert (
            AnalysisStreamMessage.from_stream_entry(
                "6-0", {"pipeline_start_time": "garbage"}
            ).pipeline_start_time
            is None
        )

    def test_delivery_count_forwarded(self):
        m = AnalysisStreamMessage.from_stream_entry(
            "7-0", {"detection_ids": "[4, 5]"}, delivery_count=3
        )
        assert (m.delivery_count, m.detection_ids) == (3, [4, 5])


class TestDetectionMessageFromStreamEntry:
    @staticmethod
    def _full():
        return {
            "camera_id": "cam1",
            "detection_id": "42",
            "file_path": "/f",
            "timestamp": "100.5",
            "confidence": "0.9",
            "object_type": "car",
        }

    def test_full(self):
        dm = DetectionStreamMessage.from_stream_entry("1-0", dict(self._full()))
        assert dm.id == "1-0"
        assert (dm.camera_id, dm.detection_id, dm.file_path) == ("cam1", 42, "/f")
        assert dm.confidence == 0.9
        assert dm.object_type == "car"
        assert dm.timestamp == 100.5
        assert dm.delivery_count == 1

    def test_empty_defaults_patched_clock(self):
        with patch("backend.services.redis_streams.time.time", autospec=True) as tt:
            tt.return_value = 555.5
            dm = DetectionStreamMessage.from_stream_entry("2-0", {})
        assert (dm.camera_id, dm.detection_id, dm.file_path) == ("", 0, "")
        assert dm.confidence is None
        assert dm.object_type is None
        assert dm.timestamp == 555.5  # time.time() fallback

    def test_bad_ts_falls_back_to_clock(self):
        with patch("backend.services.redis_streams.time.time", autospec=True) as tt:
            tt.return_value = 555.5
            dm = DetectionStreamMessage.from_stream_entry("3-0", {"timestamp": "garbage-ts"})
        assert dm.timestamp == 555.5

    def test_iso_ts(self):
        dm = DetectionStreamMessage.from_stream_entry(
            "4-0", dict(self._full(), timestamp="2026-01-02T03:04:05Z")
        )
        assert dm.timestamp == 1767323045.0

    def test_empty_confidence_none(self):
        dm = DetectionStreamMessage.from_stream_entry("5-0", dict(self._full(), confidence=""))
        assert dm.confidence is None

    def test_raw_data_identity(self):
        data = dict(self._full())
        assert DetectionStreamMessage.from_stream_entry("6-0", data).raw_data is data


class TestConsumeParseSkip:
    """bad-entry skip + METRIC labels + xreadgroup args + first-delivery dc=1."""

    async def test_detection_parse_skip_metric(self):
        with patch("backend.services.redis_streams.record_pipeline_error", autospec=True) as rpe:
            s, c = mk(DetectionStreamService, block_ms=2500)
            good = {"camera_id": "c", "detection_id": "1", "file_path": "/f", "timestamp": "1"}
            bad = {"camera_id": "c", "detection_id": "abc", "file_path": "/f", "timestamp": "1"}
            c._client.xreadgroup.return_value = [
                [DETECTION_STREAM_KEY, [("1-0", good), ("2-0", bad)]]
            ]
            msgs = await s.consume_detections("w1", count=4)
            assert [m.id for m in msgs] == ["1-0"]
            assert msgs[0].delivery_count == 1  # first-delivery constant
            call = c._client.xreadgroup.call_args
            assert call.args == ("detection-workers", "w1", {DETECTION_STREAM_KEY: ">"})
            assert call.kwargs == {"count": 4, "block": 2500}
            assert [x.args for x in rpe.call_args_list] == [("stream_parse_error",)]

    async def test_block_false_forwards_none(self):
        s, c = mk()
        c._client.xreadgroup.return_value = None
        await s.consume_detections("w1", block=False)
        assert c._client.xreadgroup.call_args.kwargs == {"count": 1, "block": None}

    async def test_analysis_parse_skip_metric(self):
        with patch("backend.services.redis_streams.record_pipeline_error", autospec=True) as rpe:
            a, ac = mk(AnalysisStreamService)
            ac._client.xreadgroup.return_value = [
                [ANALYSIS_STREAM_KEY, [("1-0", {"detection_ids": '{"a": 1}'})]]
            ]
            assert await a.consume_batches("w2") == []  # int(dict) -> TypeError -> skip
            assert [x.args for x in rpe.call_args_list] == [("analysis_stream_parse_error",)]

    async def test_analysis_valid_entry_kept(self):
        a, ac = mk(AnalysisStreamService)
        ac._client.xreadgroup.return_value = [
            [ANALYSIS_STREAM_KEY, [("1-0", {"detection_ids": "[1]"})]]
        ]
        msgs = await a.consume_batches("w2")
        assert len(msgs) == 1 and msgs[0].detection_ids == [1]

    async def test_empty_reply(self):
        a, ac = mk(AnalysisStreamService)
        ac._client.xreadgroup.return_value = None
        assert await a.consume_batches("w2") == []


class TestClaimStaleAnalysis:
    async def test_full_args_and_ids(self):
        a, c = mk(AnalysisStreamService, claim_min_idle_ms=999)
        adata = {"batch_id": "b", "camera_id": "c", "detection_ids": "[7]"}
        c._client.xautoclaim.return_value = ("0-0", [("8-0", adata)], [])
        c._client.xpending_range.return_value = [{"times_delivered": 2}]
        msgs = await a.claim_stale_messages("aw", count=5)
        call = c._client.xautoclaim.call_args
        assert call.args == ("analysis:stream", "analysis-workers", "aw", 999)
        assert call.kwargs == {"start_id": "0-0", "count": 5}
        assert len(msgs) == 1
        assert msgs[0].delivery_count == 2
        assert msgs[0].detection_ids == [7]
