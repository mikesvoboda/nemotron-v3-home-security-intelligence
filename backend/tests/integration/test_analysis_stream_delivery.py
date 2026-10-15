"""Integration tests for Ruling 199 ([r199]): analysis stream disposition and
database-decided redelivery idempotency against a real Postgres and Redis.

Ruling 199 (6198662741) item 3 specifies four integration tests:
  (a) The write fails before the commit. The message stays pending, and a
      redelivery stores exactly one event.
  (b) The process stops after the commit, before the Redis key and the notify
      decision. The redelivery stores no second event, makes no VLM call, and
      writes the notify decision.
  (c) An invalid payload leaves one dead-letter entry and nothing pending.
  (d) A failure on all three deliveries leaves one dead-letter entry.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from backend.core.database import get_session
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_notify import EventNotifyDecision
from backend.services.event_broadcaster import reset_broadcaster_state
from backend.services.pipeline_workers import AnalysisQueueWorker
from backend.services.redis_streams import AnalysisStreamService
from backend.services.vlm_analyzer import VlmAnalyzer
from backend.services.vlm_verdict import VlmVerdict

pytestmark = pytest.mark.integration


class ScriptedVlmClient:
    """Deterministic VLM client stub that counts assess() calls without network or GPU."""

    def __init__(self, verdict: VlmVerdict | None = None) -> None:
        self._verdict = verdict or VlmVerdict.model_validate(
            {
                "verdict": "confirmed",
                "risk_score": 75,
                "summary": "A person stands at the front door.",
                "reasoning": "Criterion evidence reviewed.",
                "description": "Front door, one person.",
                "criteria": [{"name": "person_present", "passed": True, "evidence": "full frame"}],
                "provenance": {"engine": "llama.cpp", "model_id": "Qwen3VL-8B-Instruct-Q4_K_M"},
            }
        )
        self.assess_calls = 0

    def prompt_text(self, request: Any) -> str:
        return f"ASSESS camera={request.context.camera_id} PATHS {request.image_paths}"

    async def assess(self, _request: Any) -> VlmVerdict:
        self.assess_calls += 1
        return self._verdict

    async def close(self) -> None:
        return None


@pytest.fixture
async def seeded_batch(integration_db: str) -> tuple[Camera, list[int], str]:
    """Create a real Camera and two real Detection rows in Postgres."""
    suffix = uuid.uuid4().hex[:8]
    camera_id = f"r199-cam-{suffix}"
    batch_id = f"r199_batch_{suffix}"
    async with get_session() as session:
        cam = Camera(
            id=camera_id,
            name=f"R199 Camera {suffix}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(cam)
        await session.flush()

        det_ids: list[int] = []
        for idx in range(2):
            det = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/frame_{idx}.jpg",
                object_type="person",
                confidence=0.92,
                detected_at=datetime(2026, 10, 15, 12, idx, tzinfo=UTC),
            )
            session.add(det)
            await session.flush()
            det_ids.append(det.id)
    return cam, det_ids, batch_id


async def _drive_stream_pass(
    worker: AnalysisQueueWorker,
    stream_service: AnalysisStreamService,
    *,
    trigger_reclaim: bool = False,
) -> None:
    """Run exactly one iteration of AnalysisQueueWorker._run_loop against real Redis."""
    real_consume = stream_service.consume_batches
    calls = 0

    async def consume_once(consumer_name: str, count: int = 1, block: bool = True) -> list[Any]:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise asyncio.CancelledError
        return await real_consume(consumer_name, count=count, block=False)

    clock_values = [1000.0, 1000.0, 1035.0, 1035.0] if trigger_reclaim else [1000.0] * 6

    class _Clock:
        def time(self) -> float:
            return clock_values.pop(0) if len(clock_values) > 1 else clock_values[0]

    worker._running = True
    with (
        patch("backend.services.pipeline_workers.time_module", new=_Clock()),
        patch(
            "backend.services.pipeline_workers.get_analysis_stream_service",
            autospec=True,
            return_value=stream_service,
        ),
        patch.object(stream_service, "consume_batches", side_effect=consume_once),
    ):
        await worker._run_loop()


async def _pending_count(real_redis: Any, stream_service: AnalysisStreamService) -> int:
    assert real_redis._client is not None
    pending = await real_redis._client.xpending(
        stream_service._stream_key, stream_service._consumer_group
    )
    return int(pending.get("pending", 0)) if isinstance(pending, dict) else 0


async def _dlq_entries(real_redis: Any, dlq_key: str) -> list[tuple[str, dict[str, Any]]]:
    assert real_redis._client is not None
    raw = await real_redis._client.xrange(dlq_key, "-", "+")
    return [
        (str(entry_id), {str(k): str(v) for k, v in fields.items()}) for entry_id, fields in raw
    ]


class TestRuling199AnalysisStreamDelivery:
    """Ruling 199 item 3(a)-(d) against real Postgres and real Redis."""

    async def test_a_write_failure_before_commit_keeps_message_pending_and_redelivery_stores_one_event(
        self,
        seeded_batch: tuple[Camera, list[int], str],
        real_redis: Any,
    ) -> None:
        """(a) The write fails before the commit. The message stays pending, and a
        redelivery stores exactly one event."""
        reset_broadcaster_state()
        cam, det_ids, batch_id = seeded_batch
        stream_key = f"test:r199:a:{uuid.uuid4().hex[:8]}"
        stream_service = AnalysisStreamService(
            redis_client=real_redis,
            stream_key=stream_key,
            block_ms=10,
            claim_min_idle_ms=0,
            max_delivery_count=3,
        )
        vlm_client = ScriptedVlmClient()
        analyzer = VlmAnalyzer(vlm_client=vlm_client, redis_client=real_redis)
        worker = AnalysisQueueWorker(redis_client=real_redis, analyzer=analyzer)

        await stream_service.add_batch(
            batch_id=batch_id,
            camera_id=cam.id,
            detection_ids=det_ids,
        )

        fail_write = True

        @asynccontextmanager
        async def failing_write_session():
            async with get_session() as session:
                real_flush = session.flush

                async def flush_hook(*args: Any, **kwargs: Any) -> Any:
                    if fail_write and any(isinstance(obj, Event) for obj in session.new):
                        raise RuntimeError("simulated DB failure before commit")
                    return await real_flush(*args, **kwargs)

                session.flush = flush_hook  # type: ignore[method-assign]
                yield session

        try:
            # Delivery 1: DB write fails before commit -> disposition is "retry"
            with patch(
                "backend.services.vlm_analyzer.get_session", side_effect=failing_write_session
            ):
                await _drive_stream_pass(worker, stream_service, trigger_reclaim=False)

            assert await _pending_count(real_redis, stream_service) == 1
            assert await _dlq_entries(real_redis, stream_service._dlq_key) == []
            async with get_session() as check_session:
                count_after_first = await check_session.scalar(
                    select(func.count()).select_from(Event).where(Event.batch_id == batch_id)
                )
            assert count_after_first == 0

            # Delivery 2 (reclaim): write succeeds -> stores 1 event and acknowledges message
            fail_write = False
            await _drive_stream_pass(worker, stream_service, trigger_reclaim=True)

            assert await _pending_count(real_redis, stream_service) == 0
            assert await _dlq_entries(real_redis, stream_service._dlq_key) == []
            async with get_session() as check_session:
                events = (
                    (await check_session.execute(select(Event).where(Event.batch_id == batch_id)))
                    .scalars()
                    .all()
                )
            assert len(events) == 1
            assert events[0].camera_id == cam.id
        finally:
            reset_broadcaster_state()
            if real_redis._client:
                await real_redis._client.delete(stream_key, stream_service._dlq_key)

    async def test_b_stop_after_commit_before_redis_key_and_notify_redelivers_without_vlm_and_writes_notify(
        self,
        seeded_batch: tuple[Camera, list[int], str],
        real_redis: Any,
    ) -> None:
        """(b) The process stops after the commit, before the Redis key and the notify
        decision. The redelivery stores no second event, makes no VLM call, and writes
        the notify decision."""
        reset_broadcaster_state()
        cam, det_ids, batch_id = seeded_batch
        stream_key = f"test:r199:b:{uuid.uuid4().hex[:8]}"
        stream_service = AnalysisStreamService(
            redis_client=real_redis,
            stream_key=stream_key,
            block_ms=10,
            claim_min_idle_ms=0,
            max_delivery_count=3,
        )
        vlm_client = ScriptedVlmClient()
        analyzer = VlmAnalyzer(vlm_client=vlm_client, redis_client=real_redis)
        worker = AnalysisQueueWorker(redis_client=real_redis, analyzer=analyzer)

        await stream_service.add_batch(
            batch_id=batch_id,
            camera_id=cam.id,
            detection_ids=det_ids,
        )

        real_set_idempotency = analyzer._set_idempotency
        stop_after_commit = True

        async def stop_before_redis_key(b_id: str, ev_id: int) -> None:
            if stop_after_commit:
                raise RuntimeError("process stopped after commit before Redis key and notify")
            await real_set_idempotency(b_id, ev_id)

        try:
            # Delivery 1: commits Event, then stops before setting Redis key & notify decision
            with patch.object(analyzer, "_set_idempotency", side_effect=stop_before_redis_key):
                await _drive_stream_pass(worker, stream_service, trigger_reclaim=False)

            assert vlm_client.assess_calls == 1
            assert await _pending_count(real_redis, stream_service) == 1
            assert await real_redis.get(f"batch_event:{batch_id}") is None

            async with get_session() as check_session:
                committed_event = await check_session.scalar(
                    select(Event).where(Event.batch_id == batch_id)
                )
                assert committed_event is not None
                first_event_id = committed_event.id
                notify_before = await check_session.scalar(
                    select(EventNotifyDecision).where(
                        EventNotifyDecision.event_id == first_event_id
                    )
                )
            assert notify_before is None

            # Delivery 2 (reclaim): Redis key misses, DB lookup finds Event -> no VLM call,
            # no second Event, writes Redis key and notify decision, acknowledges message
            stop_after_commit = False
            await _drive_stream_pass(worker, stream_service, trigger_reclaim=True)

            assert vlm_client.assess_calls == 1, "redelivery must not call the VLM again"
            assert await _pending_count(real_redis, stream_service) == 0
            assert await real_redis.get(f"batch_event:{batch_id}") == str(first_event_id)

            async with get_session() as check_session:
                events = (
                    (await check_session.execute(select(Event).where(Event.batch_id == batch_id)))
                    .scalars()
                    .all()
                )
                notify_after = await check_session.scalar(
                    select(EventNotifyDecision).where(
                        EventNotifyDecision.event_id == first_event_id
                    )
                )
            assert len(events) == 1
            assert events[0].id == first_event_id
            assert notify_after is not None
            assert notify_after.notify is True
        finally:
            reset_broadcaster_state()
            if real_redis._client:
                await real_redis._client.delete(
                    stream_key, stream_service._dlq_key, f"batch_event:{batch_id}"
                )

    async def test_c_invalid_payload_leaves_one_dead_letter_entry_and_nothing_pending(
        self,
        integration_db: str,
        real_redis: Any,
    ) -> None:
        """(c) An invalid payload leaves one dead-letter entry and nothing pending."""
        reset_broadcaster_state()
        stream_key = f"test:r199:c:{uuid.uuid4().hex[:8]}"
        stream_service = AnalysisStreamService(
            redis_client=real_redis,
            stream_key=stream_key,
            block_ms=10,
            claim_min_idle_ms=0,
            max_delivery_count=3,
        )
        vlm_client = ScriptedVlmClient()
        analyzer = VlmAnalyzer(vlm_client=vlm_client, redis_client=real_redis)
        worker = AnalysisQueueWorker(redis_client=real_redis, analyzer=analyzer)

        assert real_redis._client is not None
        await real_redis._client.xadd(
            stream_key,
            {
                "batch_id": "",
                "camera_id": "../invalid-camera",
                "detection_ids": json.dumps([1, 2]),
            },
        )

        try:
            await _drive_stream_pass(worker, stream_service, trigger_reclaim=False)

            assert vlm_client.assess_calls == 0
            assert await _pending_count(real_redis, stream_service) == 0
            dlq = await _dlq_entries(real_redis, stream_service._dlq_key)
            assert len(dlq) == 1
            assert dlq[0][1]["camera_id"] == "../invalid-camera"
            assert "dlq_reason" in dlq[0][1] and dlq[0][1]["dlq_reason"]
        finally:
            reset_broadcaster_state()
            if real_redis._client:
                await real_redis._client.delete(stream_key, stream_service._dlq_key)

    async def test_d_failure_on_all_three_deliveries_leaves_one_dead_letter_entry(
        self,
        seeded_batch: tuple[Camera, list[int], str],
        real_redis: Any,
    ) -> None:
        """(d) A failure on all three deliveries leaves one dead-letter entry."""
        reset_broadcaster_state()
        cam, det_ids, batch_id = seeded_batch
        stream_key = f"test:r199:d:{uuid.uuid4().hex[:8]}"
        stream_service = AnalysisStreamService(
            redis_client=real_redis,
            stream_key=stream_key,
            block_ms=10,
            claim_min_idle_ms=0,
            max_delivery_count=3,
        )
        vlm_client = ScriptedVlmClient()
        analyzer = VlmAnalyzer(vlm_client=vlm_client, redis_client=real_redis)
        worker = AnalysisQueueWorker(redis_client=real_redis, analyzer=analyzer)

        await stream_service.add_batch(
            batch_id=batch_id,
            camera_id=cam.id,
            detection_ids=det_ids,
        )

        try:
            with patch.object(
                analyzer,
                "analyze_batch",
                autospec=True,
                side_effect=RuntimeError("persistent database outage across all deliveries"),
            ):
                # Delivery 1 (consume_batches, delivery_count=1): fails -> stays pending
                await _drive_stream_pass(worker, stream_service, trigger_reclaim=False)
                assert await _pending_count(real_redis, stream_service) == 1
                assert await _dlq_entries(real_redis, stream_service._dlq_key) == []

                # Delivery 2 (1st reclaim, delivery_count=2): fails -> stays pending
                await _drive_stream_pass(worker, stream_service, trigger_reclaim=True)
                assert await _pending_count(real_redis, stream_service) == 1
                assert await _dlq_entries(real_redis, stream_service._dlq_key) == []

                # Delivery 3 (2nd reclaim, delivery_count=3): moves to DLQ and acknowledges
                await _drive_stream_pass(worker, stream_service, trigger_reclaim=True)

            assert await _pending_count(real_redis, stream_service) == 0
            dlq = await _dlq_entries(real_redis, stream_service._dlq_key)
            assert len(dlq) == 1
            assert dlq[0][1]["batch_id"] == batch_id
            assert dlq[0][1]["dlq_reason"] == "max_delivery_exceeded"
            assert dlq[0][1]["delivery_count"] == "3"
        finally:
            reset_broadcaster_state()
            if real_redis._client:
                await real_redis._client.delete(stream_key, stream_service._dlq_key)
