"""Unit tests for Ruling 200 ([r200]): one owner for the running pipeline workers.

Verifies:
1. After startup, the process runs exactly the configured number of detection
   and analysis consumers, one batch-timeout worker and one metrics worker,
   and the supervisor supervises the manager's workers and reads their heartbeats.
2. A worker whose task dies is restarted by the supervisor, and the count does
   not grow.
3. Shutdown stops each worker once.
4. The legacy create_*_worker factories that built a second set of workers are
   deleted and backend/main.py no longer builds pipeline workers outside
   PipelineWorkerManager.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import backend.services.pipeline_workers as pw_module
from backend.core.redis import RedisClient
from backend.services.pipeline_workers import (
    AnalysisQueueWorker,
    BatchTimeoutWorker,
    DetectionQueueWorker,
    PipelineWorkerManager,
    QueueMetricsWorker,
)
from backend.services.worker_supervisor import (
    SupervisorConfig,
    WorkerStatus,
    WorkerSupervisor,
)


def _mock_redis() -> AsyncMock:
    redis = AsyncMock(spec=RedisClient)
    redis.get_from_queue = AsyncMock(return_value=None)
    redis.get_queue_length = AsyncMock(return_value=0)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


async def _idle_loop(worker: object) -> None:
    """Fast cooperative loop for testing worker task lifecycle without Redis I/O."""
    while getattr(worker, "_running", False):
        supervisor = getattr(worker, "_supervisor", None)
        worker_name = getattr(worker, "_worker_name", "")
        if supervisor is not None and worker_name:
            supervisor.record_heartbeat(worker_name)
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_startup_runs_exact_configured_worker_counts_and_reads_heartbeats() -> None:
    """After startup, the process runs exactly the configured number of detection
    and analysis consumers, one batch-timeout worker and one metrics worker, all
    supervised by WorkerSupervisor with heartbeat reporting."""
    for factory_name in (
        "create_detection_worker",
        "create_analysis_worker",
        "create_timeout_worker",
        "create_metrics_worker",
    ):
        assert not hasattr(pw_module, factory_name), (
            f"{factory_name} should be deleted so no second worker set can be built"
        )

    main_source = Path("backend/main.py").read_text(encoding="utf-8")
    for forbidden in (
        "create_detection_worker",
        "create_analysis_worker",
        "create_timeout_worker",
        "create_metrics_worker",
    ):
        assert forbidden not in main_source

    redis = _mock_redis()
    supervisor = WorkerSupervisor(
        config=SupervisorConfig(
            check_interval=0.05,
            default_max_restarts=3,
            default_backoff_base=0.01,
            default_backoff_max=0.05,
        )
    )

    with (
        patch.object(
            DetectionQueueWorker,
            "_run_loop",
            autospec=True,
            side_effect=_idle_loop,
        ),
        patch.object(
            AnalysisQueueWorker,
            "_run_loop",
            autospec=True,
            side_effect=_idle_loop,
        ),
        patch.object(
            BatchTimeoutWorker,
            "_run_loop",
            autospec=True,
            side_effect=_idle_loop,
        ),
        patch.object(
            QueueMetricsWorker,
            "_run_loop",
            autospec=True,
            side_effect=_idle_loop,
        ),
    ):
        manager = PipelineWorkerManager(
            redis_client=redis,
            detector_client=MagicMock(),
            analyzer=MagicMock(),
            detection_worker_count=2,
            analysis_worker_count=2,
            worker_stop_timeout=1.0,
        )
        try:
            await manager.start()
            await manager.register_workers_with_supervisor(supervisor, max_restarts=3)
            await supervisor.start()

            await asyncio.sleep(0.03)

            assert len(manager._detection_workers) == 2
            assert len(manager._analysis_workers) == 2
            assert manager._timeout_worker is not None
            assert manager._metrics_worker is not None

            for w in manager._detection_workers:
                assert w.running is True
                assert w._task is not None and not w._task.done()
                assert w._supervisor is supervisor
            for w in manager._analysis_workers:
                assert w.running is True
                assert w._task is not None and not w._task.done()
                assert w._supervisor is supervisor
            assert manager._timeout_worker.running is True
            assert (
                manager._timeout_worker._task is not None
                and not manager._timeout_worker._task.done()
            )
            assert manager._timeout_worker._supervisor is supervisor
            assert manager._metrics_worker.running is True
            assert (
                manager._metrics_worker._task is not None
                and not manager._metrics_worker._task.done()
            )
            assert manager._metrics_worker._supervisor is supervisor

            expected_names = {
                "detection-0",
                "detection-1",
                "analysis-0",
                "analysis-1",
                "batch_timeout",
                "metrics",
            }
            assert set(supervisor.get_all_workers().keys()) == expected_names
            assert supervisor.worker_count == 6

            for name in expected_names:
                info = supervisor.get_worker_info(name)
                assert info is not None
                assert info.status == WorkerStatus.RUNNING
                assert info.last_heartbeat_at is not None
        finally:
            await supervisor.stop()
            await manager.stop()


@pytest.mark.asyncio
async def test_worker_whose_task_dies_is_restarted_by_supervisor_and_count_does_not_grow() -> None:
    """A worker whose task dies is restarted by the supervisor, and the count does not grow."""
    redis = _mock_redis()
    supervisor = WorkerSupervisor(
        config=SupervisorConfig(
            check_interval=0.02,
            default_max_restarts=3,
            default_backoff_base=0.01,
            default_backoff_max=0.02,
        )
    )

    with (
        patch.object(
            DetectionQueueWorker,
            "_run_loop",
            autospec=True,
            side_effect=_idle_loop,
        ),
        patch.object(
            AnalysisQueueWorker,
            "_run_loop",
            autospec=True,
            side_effect=_idle_loop,
        ),
        patch.object(
            BatchTimeoutWorker,
            "_run_loop",
            autospec=True,
            side_effect=_idle_loop,
        ),
        patch.object(
            QueueMetricsWorker,
            "_run_loop",
            autospec=True,
            side_effect=_idle_loop,
        ),
    ):
        manager = PipelineWorkerManager(
            redis_client=redis,
            detector_client=MagicMock(),
            analyzer=MagicMock(),
            detection_worker_count=2,
            analysis_worker_count=2,
            worker_stop_timeout=1.0,
        )
        try:
            await manager.start()
            await manager.register_workers_with_supervisor(supervisor, max_restarts=3)
            await supervisor.start()

            target_worker = manager._detection_workers[0]
            original_task = target_worker._task
            assert original_task is not None and not original_task.done()

            # Simulate the worker's task dying unexpectedly
            original_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await original_task

            # Wait for supervisor monitor loop to detect the dead task and restart it
            for _ in range(30):
                await asyncio.sleep(0.02)
                info = supervisor.get_worker_info("detection-0")
                if (
                    info is not None
                    and info.restart_count >= 1
                    and info.status == WorkerStatus.RUNNING
                    and target_worker._task is not None
                    and target_worker._task is not original_task
                    and not target_worker._task.done()
                ):
                    break

            info = supervisor.get_worker_info("detection-0")
            assert info is not None
            assert info.restart_count == 1
            assert info.status == WorkerStatus.RUNNING
            assert target_worker.running is True
            assert target_worker._task is not None
            assert target_worker._task is not original_task
            assert not target_worker._task.done()

            # Count of workers in manager and supervisor did not grow
            assert len(manager._detection_workers) == 2
            assert len(manager._analysis_workers) == 2
            assert manager._detection_workers[0] is target_worker
            assert supervisor.worker_count == 6
        finally:
            await supervisor.stop()
            await manager.stop()


@pytest.mark.asyncio
async def test_shutdown_stops_each_worker_once() -> None:
    """Shutdown stops each worker once."""
    redis = _mock_redis()
    supervisor = WorkerSupervisor(
        config=SupervisorConfig(
            check_interval=0.05,
            default_max_restarts=3,
            default_backoff_base=0.01,
            default_backoff_max=0.05,
        )
    )

    with (
        patch.object(
            DetectionQueueWorker,
            "_run_loop",
            autospec=True,
            side_effect=_idle_loop,
        ),
        patch.object(
            AnalysisQueueWorker,
            "_run_loop",
            autospec=True,
            side_effect=_idle_loop,
        ),
        patch.object(
            BatchTimeoutWorker,
            "_run_loop",
            autospec=True,
            side_effect=_idle_loop,
        ),
        patch.object(
            QueueMetricsWorker,
            "_run_loop",
            autospec=True,
            side_effect=_idle_loop,
        ),
    ):
        manager = PipelineWorkerManager(
            redis_client=redis,
            detector_client=MagicMock(),
            analyzer=MagicMock(),
            detection_worker_count=2,
            analysis_worker_count=2,
            worker_stop_timeout=1.0,
        )
        await manager.start()
        await manager.register_workers_with_supervisor(supervisor, max_restarts=3)
        await supervisor.start()

        all_workers = [
            *manager._detection_workers,
            *manager._analysis_workers,
            manager._timeout_worker,
            manager._metrics_worker,
        ]
        stop_spies: list[AsyncMock] = []
        stack_patches = []
        for w in all_workers:
            assert w is not None
            spy = AsyncMock(wraps=w.stop)
            stop_spies.append(spy)
            p = patch.object(w, "stop", spy)
            p.start()
            stack_patches.append(p)

        try:
            # Stop via manager.stop() (which stops supervisor first if running, then stops each worker once)
            await manager.stop()

            assert supervisor.is_running is False
            assert manager.running is False
            for spy in stop_spies:
                assert spy.await_count == 1
        finally:
            for p in stack_patches:
                p.stop()
