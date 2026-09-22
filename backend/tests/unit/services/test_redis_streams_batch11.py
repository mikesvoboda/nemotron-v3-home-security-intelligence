"""Batch-11 mutation-kill battery: redis_streams argument-forwarding clusters.

Target: dossier ``redis_streams.md`` TEST-GAP clusters 1-8, 10-26 (238 of the
429 survivors). The dossier's stated shared weakness: the suites mock redis-py
and assert happy-path MESSAGE CONTENTS but almost never assert the ARGUMENTS
FORWARDED to redis commands (``call_args``) and never capture logs — hence
this battery asserts full call signatures, complete reply-mapping dicts, and
constructor-stored state, in BOTH service classes (Detection + Analysis),
plus the dataclass-default paths the entry tests never exercise.

All expected values were MEASURED from shipped
``backend/services/redis_streams.py`` at this commit (source cited per test),
not guessed. Log-text clusters (C-LOW-LOGKEY/MSG/DROP, 167 mutants) are
deliberately NOT asserted: log text is observability, per the batch-7
precedent; their disposition lives in the dossier LOW-VALUE rows.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis import RedisClient
from backend.services.redis_streams import (
    ANALYSIS_CONSUMER_GROUP,
    ANALYSIS_STREAM_KEY,
    DEFAULT_BLOCK_MS,
    DEFAULT_CLAIM_MIN_IDLE_MS,
    DEFAULT_MAX_DELIVERY_COUNT,
    DEFAULT_STREAM_APPROXIMATE,
    DEFAULT_STREAM_MAXLEN,
    DETECTION_CONSUMER_GROUP,
    DETECTION_STREAM_KEY,
    AnalysisStreamMessage,
    AnalysisStreamService,
    DetectionStreamMessage,
    DetectionStreamService,
    _text,
    get_analysis_stream_service,
    get_detection_stream_service,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.fixture
def mock_redis_client():
    mock = MagicMock(spec=RedisClient)
    mock._client = AsyncMock()
    return mock


@pytest.fixture
def det_service(mock_redis_client):
    return DetectionStreamService(
        redis_client=mock_redis_client,
        stream_key=DETECTION_STREAM_KEY,
        consumer_group=DETECTION_CONSUMER_GROUP,
    )


@pytest.fixture
def ana_service(mock_redis_client):
    return AnalysisStreamService(
        redis_client=mock_redis_client,
        stream_key=ANALYSIS_STREAM_KEY,
        consumer_group=ANALYSIS_CONSUMER_GROUP,
    )


def _claim_reply(mid: str, fields: dict[str, str]):
    """(next_id, [(id, fields)], deleted_ids) — redis-py xautoclaim shape."""
    return ("0-0", [(mid, fields)], [])


def _readgroup_reply(stream_key: str, entries: list[tuple]):
    return [[stream_key, entries]]


class TestClaimForwardsFullArgs:
    """Clusters 1 (XAUUTOCLAIM args), 4 (XPENDING args), 19 (TEXT id)."""

    async def test_detection_claim_forwards_exact_xautoclaim_args(
        self, det_service, mock_redis_client
    ):
        c = mock_redis_client._client
        c.xautoclaim = AsyncMock(return_value=_claim_reply("1234567890123-0", {"camera_id": "cam"}))
        c.xpending_range = AsyncMock(return_value=[("1234567890123-0", "w1", 120000, 3)])

        messages = await det_service.claim_stale_messages("worker-2", count=5)

        c.xautoclaim.assert_awaited_once_with(
            DETECTION_STREAM_KEY,
            DETECTION_CONSUMER_GROUP,
            "worker-2",
            DEFAULT_CLAIM_MIN_IDLE_MS,
            start_id="0-0",
            count=5,
        )
        c.xpending_range.assert_awaited_once_with(
            DETECTION_STREAM_KEY,
            DETECTION_CONSUMER_GROUP,
            min="1234567890123-0",
            max="1234567890123-0",
            count=1,
        )
        assert len(messages) == 1
        # cluster 19: id forwarded through _text; delivery count from pending row
        assert messages[0].id == "1234567890123-0"
        assert messages[0].delivery_count == 3

    async def test_analysis_claim_forwards_exact_args(self, ana_service, mock_redis_client):
        c = mock_redis_client._client
        c.xautoclaim = AsyncMock(return_value=_claim_reply("7-0", {"batch_id": "b"}))
        c.xpending_range = AsyncMock(return_value=[("7-0", "w1", 61000, 2)])

        messages = await ana_service.claim_stale_messages("worker-9", count=4)

        c.xautoclaim.assert_awaited_once_with(
            ANALYSIS_STREAM_KEY,
            ANALYSIS_CONSUMER_GROUP,
            "worker-9",
            DEFAULT_CLAIM_MIN_IDLE_MS,
            start_id="0-0",
            count=4,
        )
        c.xpending_range.assert_awaited_once_with(
            ANALYSIS_STREAM_KEY,
            ANALYSIS_CONSUMER_GROUP,
            min="7-0",
            max="7-0",
            count=1,
        )
        assert messages[0].delivery_count == 2

    async def test_claim_decodes_bytes_ids_via_text(self, det_service, mock_redis_client):
        # cluster 19 + 24: bytes reply entries flow through _text — shipped
        # decodes (b"9-0" -> "9-0"); _text->None yields None, _text(None)
        # yields "None"
        c = mock_redis_client._client
        c.xautoclaim = AsyncMock(return_value=("0-0", [(b"9-0", {b"camera_id": b"cam"})], []))
        c.xpending_range = AsyncMock(return_value=[(b"9-0", b"w", 1, 1)])

        (msg,) = await det_service.claim_stale_messages("w")
        assert msg.id == "9-0"
        assert msg.camera_id == "cam"

    async def test_claim_dict_row_reads_times_delivered(self, det_service, mock_redis_client):
        # _pending_delivery_count dict branch (:132-133): redis-py >=5 keys
        # the row by name — positional read would IndexError -> skip path
        c = mock_redis_client._client
        c.xautoclaim = AsyncMock(return_value=_claim_reply("1-0", {"camera_id": "c"}))
        c.xpending_range = AsyncMock(return_value=[{"times_delivered": 7}])

        (msg,) = await det_service.claim_stale_messages("w")
        assert msg.delivery_count == 7


class TestGroupAndReadArgs:
    """Clusters 5 (xgroup_create args), 6/18 (xreadgroup args/block), 14 (once)."""

    async def test_ensure_group_forwards_create_args_detection(
        self, det_service, mock_redis_client
    ):
        await det_service._ensure_consumer_group()
        mock_redis_client._client.xgroup_create.assert_awaited_once_with(
            DETECTION_STREAM_KEY, DETECTION_CONSUMER_GROUP, id="0", mkstream=True
        )

    async def test_ensure_group_forwards_create_args_analysis(self, ana_service, mock_redis_client):
        await ana_service._ensure_consumer_group()
        mock_redis_client._client.xgroup_create.assert_awaited_once_with(
            ANALYSIS_STREAM_KEY, ANALYSIS_CONSUMER_GROUP, id="0", mkstream=True
        )

    async def test_analysis_ensure_group_creates_once(self, ana_service, mock_redis_client):
        # cluster 14: _group_created True->None re-creates EVERY call;
        # False->True never creates
        await ana_service._ensure_consumer_group()
        await ana_service._ensure_consumer_group()
        assert mock_redis_client._client.xgroup_create.await_count == 1

    async def test_consume_detections_forwards_full_xreadgroup_args(
        self, det_service, mock_redis_client
    ):
        c = mock_redis_client._client
        c.xreadgroup = AsyncMock(return_value=[])
        await det_service.consume_detections("w1", count=3)
        c.xreadgroup.assert_awaited_once_with(
            DETECTION_CONSUMER_GROUP,
            "w1",
            {DETECTION_STREAM_KEY: ">"},
            count=3,
            block=DEFAULT_BLOCK_MS,
        )

    async def test_consume_detections_nonblocking_sends_block_none(
        self, det_service, mock_redis_client
    ):
        c = mock_redis_client._client
        c.xreadgroup = AsyncMock(return_value=[])
        await det_service.consume_detections("w1", count=2, block=False)
        assert c.xreadgroup.await_args.kwargs["block"] is None

    async def test_consume_batches_block_matrix(self, ana_service, mock_redis_client):
        # cluster 18: consume_batches had NO blocking/non-blocking assert —
        # block_ms = self._block_ms if block else None (:1081)
        c = mock_redis_client._client
        c.xreadgroup = AsyncMock(return_value=[])
        await ana_service.consume_batches("w2", count=1, block=True)
        assert c.xreadgroup.await_args.kwargs["block"] == DEFAULT_BLOCK_MS
        await ana_service.consume_batches("w2", count=1, block=False)
        assert c.xreadgroup.await_args.kwargs["block"] is None
        c.xreadgroup.assert_awaited_with(
            ANALYSIS_CONSUMER_GROUP, "w2", {ANALYSIS_STREAM_KEY: ">"}, count=1, block=None
        )

    async def test_consume_carries_delivery_count_and_survives_wide_entries(
        self, det_service, mock_redis_client
    ):
        # cluster 12 (delivery_count=1 kwarg observable) + 16 (entry[:3]
        # mutant ValueError-swallows the message — shipped reads [:2] fine)
        c = mock_redis_client._client
        c.xreadgroup = AsyncMock(
            return_value=_readgroup_reply(
                DETECTION_STREAM_KEY, [("1-0", {"camera_id": "cam", "detection_id": "4"}, "x")]
            )
        )
        (msg,) = await det_service.consume_detections("w")
        assert msg.delivery_count == 1
        assert msg.id == "1-0"


class TestReplyMappingCompleteness:
    """Clusters 2/3 (get_stream_info keys), 10 (cginfo), 11 (pending), 17 (xinfo args)."""

    async def test_get_stream_info_maps_every_key(self, det_service, mock_redis_client):
        det_service._redis._client.xinfo_stream = AsyncMock(
            return_value={
                "length": 42,
                "radix-tree-keys": 7,
                "radix-tree-nodes": 9,
                "groups": 2,
                "last-generated-id": "5-1",
                "first-entry": ["1-0", {"camera_id": "a"}],
            }
        )
        info = await det_service.get_stream_info()
        assert info == {
            "length": 42,
            "radix_tree_keys": 7,
            "radix_tree_nodes": 9,
            "groups": 2,
            "last_entry_id": "5-1",
            "first_entry_id": "1-0",
        }
        det_service._redis._client.xinfo_stream.assert_awaited_once_with(DETECTION_STREAM_KEY)

    async def test_get_stream_info_no_such_key_fallback_is_complete(
        self, det_service, mock_redis_client
    ):
        det_service._redis._client.xinfo_stream = AsyncMock(
            side_effect=Exception("ERR no such key")
        )
        assert await det_service.get_stream_info() == {
            "length": 0,
            "radix_tree_keys": 0,
            "radix_tree_nodes": 0,
            "groups": 0,
            "last_entry_id": "",
            "first_entry_id": "",
        }

    async def test_get_stream_info_first_entry_absent_maps_empty(
        self, det_service, mock_redis_client
    ):
        # `if info.get("first-entry")` guard :714-716 — dict WITHOUT the key
        det_service._redis._client.xinfo_stream = AsyncMock(
            return_value={"length": 1, "last-generated-id": "1-0"}
        )
        info = await det_service.get_stream_info()
        assert info["first_entry_id"] == ""
        assert info["radix_tree_keys"] == 0 and info["radix_tree_nodes"] == 0

    async def test_get_consumer_group_info_happy_path(self, det_service, mock_redis_client):
        # cluster 10: NO test covered the group-found path before this
        c = mock_redis_client._client
        c.xinfo_groups = AsyncMock(
            return_value=[
                {"name": "other", "consumers": 9, "pending": 9, "last-delivered-id": "X"},
                {
                    "name": DETECTION_CONSUMER_GROUP,
                    "consumers": 3,
                    "pending": 5,
                    "last-delivered-id": "123-0",
                },
            ]
        )
        info = await det_service.get_consumer_group_info()
        assert info == {
            "name": DETECTION_CONSUMER_GROUP,
            "consumers": 3,
            "pending": 5,
            "last_delivered_id": "123-0",
        }
        c.xinfo_groups.assert_awaited_once_with(DETECTION_STREAM_KEY)

    async def test_get_consumer_group_info_no_match_defaults(self, det_service, mock_redis_client):
        c = mock_redis_client._client
        c.xinfo_groups = AsyncMock(return_value=[{"name": "other"}])
        assert await det_service.get_consumer_group_info() == {
            "name": DETECTION_CONSUMER_GROUP,
            "consumers": 0,
            "pending": 0,
            "last_delivered_id": "",
        }

    async def test_get_pending_count_forwards_args_and_defaults(
        self, det_service, mock_redis_client
    ):
        # cluster 11: args + `.get` fallbacks never surfaced by complete-dict tests
        c = mock_redis_client._client
        c.xpending = AsyncMock(return_value={"pending": 7, "consumers": []})
        assert await det_service.get_pending_count() == 7
        c.xpending.assert_awaited_once_with(DETECTION_STREAM_KEY, DETECTION_CONSUMER_GROUP)

    async def test_get_pending_count_per_consumer_missing_pending_key(
        self, det_service, mock_redis_client
    ):
        c = mock_redis_client._client
        c.xpending = AsyncMock(
            return_value={"pending": 7, "consumers": [{"name": "w1"}]}  # no "pending" key
        )
        assert await det_service.get_pending_count("w1") == 0

    async def test_get_pending_count_consumers_key_absent(self, det_service, mock_redis_client):
        c = mock_redis_client._client
        c.xpending = AsyncMock(return_value={"pending": 3})  # no "consumers" key
        assert await det_service.get_pending_count("nope") == 0


class TestEntryDefaults:
    """Clusters 7 (from_stream_entry defaults), 12-observable, 25-adjacent."""

    def test_detection_missing_fields_defaults(self):
        # measured shipped output at :205-214 — every default on one object
        msg = DetectionStreamMessage.from_stream_entry("9-0", {})
        assert (msg.id, msg.camera_id, msg.detection_id, msg.file_path) == ("9-0", "", 0, "")
        assert (msg.confidence, msg.object_type, msg.delivery_count) == (None, None, 1)
        assert msg.raw_data == {}
        assert abs(msg.timestamp - time.time()) < 60  # default_factory=time.time

    def test_analysis_missing_fields_defaults(self):
        msg = AnalysisStreamMessage.from_stream_entry("9-0", {})
        assert (msg.id, msg.batch_id, msg.camera_id) == ("9-0", "", "")
        assert msg.detection_ids == []
        assert msg.pipeline_start_time is None
        assert msg.delivery_count == 1
        assert msg.raw_data == {}

    def test_detection_confidence_falsy_gate_measured(self):
        # `if data.get("confidence")` truthiness gate :209 — MEASURED shipped:
        # non-empty "0" is a TRUTHY string -> float("0") == 0.0; the falsy
        # members are "" and the missing key -> None. A gate dropped to
        # `if "confidence" in data` float()-crashes on ""; gate inverted to
        # `if not ...` swaps the two arms.
        assert (
            DetectionStreamMessage.from_stream_entry("1-0", {"confidence": "0"}).confidence == 0.0
        )
        assert (
            DetectionStreamMessage.from_stream_entry("1-0", {"confidence": "0.5"}).confidence == 0.5
        )
        assert (
            DetectionStreamMessage.from_stream_entry("1-0", {"confidence": ""}).confidence is None
        )
        assert DetectionStreamMessage.from_stream_entry("1-0", {}).confidence is None

    def test_iso_z_timestamp_parses(self):
        # _parse_timestamp Z-replacement :151: fromisoformat handles 'Z'
        # natively (3.11+, PEP-758 era) — the replaced value must equal the
        # same instant parsed the shipped way
        m = DetectionStreamMessage.from_stream_entry("1-0", {"timestamp": "2026-09-22T12:00:00Z"})
        assert (
            m.timestamp
            == __import__("datetime").datetime.fromisoformat("2026-09-22T12:00:00Z").timestamp()
        )


class TestWritePathsForwardKwargs:
    """Clusters 8 (xadd kwargs), 20 (extra coercion), 21/26 (DLQ), 22/9 (trim)."""

    async def test_add_detection_forwards_maxlen_approximate_and_coerces_extra(
        self, det_service, mock_redis_client
    ):
        c = mock_redis_client._client
        c.xadd = AsyncMock(return_value="1-0")
        await det_service.add_detection(
            "cam",
            42,
            "/p.jpg",
            confidence=0.5,
            object_type="person",
            extra_fields={"count": 5, "tag": "x"},
        )
        (stream, fields), kwargs = c.xadd.await_args.args, c.xadd.await_args.kwargs
        assert stream == DETECTION_STREAM_KEY
        assert kwargs == {
            "maxlen": DEFAULT_STREAM_MAXLEN,
            "approximate": DEFAULT_STREAM_APPROXIMATE,
        }
        # cluster 20: non-str coerced, str untouched (str(s)==s identity twin)
        assert fields["count"] == "5"
        assert fields["tag"] == "x"
        assert fields["confidence"] == "0.5"

    async def test_add_batch_forwards_maxlen_approximate(self, ana_service, mock_redis_client):
        c = mock_redis_client._client
        c.xadd = AsyncMock(return_value="1-0")
        await ana_service.add_batch("b1", "cam", [1, 2], pipeline_start_time=111.5)
        (stream, fields), kwargs = c.xadd.await_args.args, c.xadd.await_args.kwargs
        assert stream == ANALYSIS_STREAM_KEY
        assert kwargs == {
            "maxlen": DEFAULT_STREAM_MAXLEN,
            "approximate": DEFAULT_STREAM_APPROXIMATE,
        }
        assert fields["detection_ids"] == "[1, 2]"
        assert fields["pipeline_start_time"] == "111.5"
        assert "timestamp" in fields

    async def test_move_to_dlq_fields_and_ack_args(self, det_service, mock_redis_client):
        # clusters 21 + 26: raw_data passthrough values, dlq_timestamp, and
        # the acknowledge arg forwarding
        c = mock_redis_client._client
        c.xadd = AsyncMock(return_value="d-0")
        c.xack = AsyncMock(return_value=1)
        msg = DetectionStreamMessage(
            id="1-0",
            camera_id="front_door",
            detection_id=7,
            file_path="/p",
            raw_data={"camera_id": "front_door", "detection_id": "7"},
            delivery_count=4,
        )
        await det_service.move_to_dlq(msg, reason="poison")
        (stream, fields), _ = c.xadd.await_args.args, c.xadd.await_args.kwargs
        assert stream == f"{DETECTION_STREAM_KEY}:dlq"
        assert fields["camera_id"] == "front_door"  # not "None"-ified
        assert fields["original_message_id"] == "1-0"
        assert fields["dlq_reason"] == "poison"
        assert fields["delivery_count"] == "4"
        assert "dlq_timestamp" in fields
        c.xack.assert_awaited_once_with(DETECTION_STREAM_KEY, DETECTION_CONSUMER_GROUP, "1-0")

    async def test_trim_stream_forwards_args_and_reports_removal(
        self, det_service, mock_redis_client
    ):
        # cluster 22 full args + cluster 9 healthy math
        c = mock_redis_client._client
        c.xinfo_stream = AsyncMock(side_effect=[{"length": 12}, {"length": 7}])
        c.xtrim = AsyncMock(return_value=5)
        assert await det_service.trim_stream(maxlen=7) == 5  # max(0, 12-7)
        c.xtrim.assert_awaited_once_with(
            DETECTION_STREAM_KEY, maxlen=7, approximate=DEFAULT_STREAM_APPROXIMATE
        )

    async def test_trim_stream_equal_lengths_removes_zero(self, det_service, mock_redis_client):
        # max(0, ...) -> max(1, ...) mutant reports 1 here; also the
        # default-0 paths (info missing "length")
        c = mock_redis_client._client
        c.xinfo_stream = AsyncMock(side_effect=[{"length": 5}, {"length": 5}])
        c.xtrim = AsyncMock(return_value=0)
        assert await det_service.trim_stream() == 0

    async def test_trim_stream_info_failure_defaults_to_zero(self, det_service, mock_redis_client):
        # both xinfo calls raise -> current=0, new=0, removed=max(0,0-0)=0;
        # the default-0 vs default-1 mutants differ here
        c = mock_redis_client._client
        c.xinfo_stream = AsyncMock(side_effect=Exception("boom"))
        c.xtrim = AsyncMock(return_value=0)
        assert await det_service.trim_stream() == 0


class TestFactoryAndInitState:
    """Clusters 13 (factory-constructed values), 15 (svc attrs), 25 (dlq key)."""

    async def test_factory_constructs_with_settings_maxlen(self, mock_redis_client):
        import backend.services.redis_streams as module

        module._detection_stream_service = None
        module._analysis_stream_service = None
        try:
            with patch("backend.services.redis_streams.get_settings", autospec=True) as gs:
                gs.return_value.queue_max_size = 1234
                det = await get_detection_stream_service(mock_redis_client)
                ana = await get_analysis_stream_service(mock_redis_client)
            assert det._maxlen == 1234 and ana._maxlen == 1234
            assert det._redis is mock_redis_client and ana._redis is mock_redis_client
            # idempotent singleton: same instance second call
            assert await get_detection_stream_service(mock_redis_client) is det
        finally:
            module._detection_stream_service = None
            module._analysis_stream_service = None

    def test_analysis_service_stores_all_defaults(self, mock_redis_client):
        svc = AnalysisStreamService(redis_client=mock_redis_client)
        assert svc._dlq_key == f"{ANALYSIS_STREAM_KEY}:dlq"  # cluster 25
        assert svc._block_ms == DEFAULT_BLOCK_MS
        assert svc._claim_min_idle_ms == DEFAULT_CLAIM_MIN_IDLE_MS
        assert svc._max_delivery_count == DEFAULT_MAX_DELIVERY_COUNT
        assert svc._maxlen == DEFAULT_STREAM_MAXLEN
        assert svc._group_created is False

    def test_detection_init_maxlen_zero_falls_back_via_or(self, mock_redis_client):
        # `maxlen or DEFAULT` — a 0 maxlen stores DEFAULT (the `and`-fold
        # stores 0/None and changes xadd kwargs downstream)
        assert (
            DetectionStreamService(redis_client=mock_redis_client, maxlen=0)._maxlen
            == DEFAULT_STREAM_MAXLEN
        )
        assert DetectionStreamService(redis_client=mock_redis_client, maxlen=55)._maxlen == 55


class TestAckBoundary:
    """Cluster 23 (analysis ack 0 -> >= 0 reports success) + 24 (_text bytes)."""

    async def test_analysis_acknowledge_zero_is_false(self, ana_service, mock_redis_client):
        ana_service._redis._client.xack = AsyncMock(return_value=0)
        assert await ana_service.acknowledge("nope-0") is False

    async def test_detection_acknowledge_one_is_true(self, det_service, mock_redis_client):
        det_service._redis._client.xack = AsyncMock(return_value=1)
        assert await det_service.acknowledge("1-0") is True

    def test_text_decodes_bytes(self):
        assert _text(b"abc") == "abc"
        assert _text("s") == "s"
        assert _text(12) == "12"
