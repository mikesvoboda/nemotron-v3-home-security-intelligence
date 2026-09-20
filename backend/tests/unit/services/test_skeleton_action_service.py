"""WP3.1 first tests for backend.services.skeleton_action_service.

Mutation history listed this module as no_tests (never covered at all — its
mutants were unmeasurable, not surviving). The WP3.1 done-when is assertions
that fail against mutants, so every behavior gate gets its own test:

  * _keypoints_dict_to_array: (17,3) shape, COCO name->row ordering, missing
    joints stay zero, dict-with-attributes -> x/y/confidence placement
  * add_keypoints: buffer accumulates below min_frames with NO inference;
    inference runs only at (len(buf) >= min_frames AND count >= interval);
    result cached and returned from the cache on subsequent below-gate calls;
    bad shape returns None without buffering; classify failure falls back to
    the cached result (or None on first-ever frame)
  * circular buffer: maxlen evicts the oldest frame
  * cleanup_stale: only buffers whose LAST frame is older than max_age are
    removed, and removal clears counts + cached results (return count exact)
  * get_buffer_status: the three counters, and the global get/set/reset trio
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

import backend.services.skeleton_action_service as sas
from backend.services.skeleton_action_service import (
    SkeletonActionService,
    get_skeleton_action_service,
    reset_skeleton_action_service,
    set_skeleton_action_service,
)
from backend.services.stgcn_loader import COCO_KEYPOINT_NAMES, SkeletonActionResult


def _result(label: str = "stand", conf: float = 0.9) -> SkeletonActionResult:
    return SkeletonActionResult(
        action_label=label,
        action_index=0,
        confidence=conf,
        security_risk="none",
        is_security_relevant=False,
        top_actions=[(label, conf)],
    )


@pytest.fixture
def classify_spy(monkeypatch):
    """Patch the classify call the service awaits; records input shapes."""
    calls: list = []

    async def fake(model_dict, seq, top_k=5):
        calls.append({"model_dict": model_dict, "seq": seq, "top_k": top_k})
        return _result(f"call-{len(calls)}")

    monkeypatch.setattr(sas, "classify_skeleton_action", fake)
    return calls


def _kp_dict(x: float = 0.5) -> dict:
    return {name: SimpleNamespace(x=x, y=x + 0.1, confidence=0.8) for name in COCO_KEYPOINT_NAMES}


def _service(**kw) -> SkeletonActionService:
    return SkeletonActionService({"model": None}, **kw)


class TestKeypointsDictToArray:
    def test_shape_and_dtype(self) -> None:
        arr = _service()._keypoints_dict_to_array(_kp_dict())
        assert arr.shape == (17, 3)
        assert arr.dtype == np.float32

    def test_coco_name_ordering(self) -> None:
        d = {
            name: SimpleNamespace(x=float(i), y=0.0, confidence=1.0)
            for i, name in enumerate(COCO_KEYPOINT_NAMES)
        }
        arr = _service()._keypoints_dict_to_array(d)
        assert arr[:, 0].tolist() == [float(i) for i in range(17)]

    def test_missing_joints_stay_zero(self) -> None:
        d = {
            "nose": SimpleNamespace(x=1.0, y=2.0, confidence=0.5),
            "left_wrist": SimpleNamespace(x=3.0, y=4.0, confidence=0.25),
        }
        arr = _service()._keypoints_dict_to_array(d)
        nose = COCO_KEYPOINT_NAMES.index("nose")
        wrist = COCO_KEYPOINT_NAMES.index("left_wrist")
        assert arr[nose].tolist() == [1.0, 2.0, 0.5]
        assert arr[wrist].tolist() == [3.0, 4.0, 0.25]
        others = [i for i in range(17) if i not in (nose, wrist)]
        assert arr[others].sum() == 0.0


class TestAddKeypointsGating:
    @pytest.mark.asyncio
    async def test_below_min_frames_buffers_without_inference(self, classify_spy) -> None:
        svc = _service(min_frames=30, inference_interval=15)
        for i in range(29):
            assert await svc.add_keypoints("p", _kp_dict(), timestamp=1000.0 + i) is None
        assert classify_spy == []
        assert svc.get_buffer_status()["total_frames_buffered"] == 29

    @pytest.mark.asyncio
    async def test_inference_at_min_frames_and_interval(self, classify_spy) -> None:
        svc = _service(min_frames=5, inference_interval=5)
        out = None
        for i in range(5):
            out = await svc.add_keypoints("p", _kp_dict(), timestamp=100.0 + i)
        assert out is not None and out.action_label == "call-1"
        assert len(classify_spy) == 1
        # sequence shape: (1, T, 17, 3)
        assert classify_spy[0]["seq"].shape == (1, 5, 17, 3)
        assert classify_spy[0]["top_k"] == 5

    @pytest.mark.asyncio
    async def test_interval_restarts_after_inference(self, classify_spy) -> None:
        svc = _service(min_frames=3, inference_interval=3)
        for i in range(3):
            await svc.add_keypoints("p", _kp_dict(), timestamp=1.0 + i)
        assert len(classify_spy) == 1
        # frames 4-5: buffer long enough but only 1-2 frames since the reset ->
        # gated, and a gated call returns the CACHED result (call-1)
        assert (await svc.add_keypoints("p", _kp_dict(), timestamp=4.0)).action_label == "call-1"
        assert (await svc.add_keypoints("p", _kp_dict(), timestamp=5.0)).action_label == "call-1"
        assert len(classify_spy) == 1
        out = await svc.add_keypoints("p", _kp_dict(), timestamp=6.0)  # count hits 3 again
        assert out.action_label == "call-2"

    @pytest.mark.asyncio
    async def test_cached_result_returned_while_gated(self, classify_spy) -> None:
        svc = _service(min_frames=2, inference_interval=2)
        await svc.add_keypoints("p", _kp_dict(), timestamp=1.0)
        r = await svc.add_keypoints("p", _kp_dict(), timestamp=2.0)  # triggers call-1
        cached = await svc.add_keypoints("p", _kp_dict(), timestamp=3.0)  # gated -> cache
        assert cached is r
        assert svc.get_last_result("p") is r

    @pytest.mark.asyncio
    async def test_wrong_shape_returns_none_and_does_not_buffer(self, classify_spy) -> None:
        svc = _service(min_frames=2, inference_interval=1)
        assert (
            await svc.add_keypoints("p", np.zeros((16, 3), dtype=np.float32), timestamp=1.0) is None
        )
        assert svc.get_buffer_status() == {
            "active_persons": 0,
            "total_frames_buffered": 0,
            "persons_with_results": 0,
        }

    @pytest.mark.asyncio
    async def test_classify_failure_falls_back_to_cache_then_none(self, monkeypatch) -> None:
        svc = _service(min_frames=1, inference_interval=1)

        async def boom(model_dict, seq, top_k=5):
            raise RuntimeError("model exploded")

        monkeypatch.setattr(sas, "classify_skeleton_action", boom)
        assert await svc.add_keypoints("p", _kp_dict(), timestamp=1.0) is None  # no cache yet

        good = _result("walk")

        async def ok(model_dict, seq, top_k=5):
            return good

        monkeypatch.setattr(sas, "classify_skeleton_action", ok)
        assert await svc.add_keypoints("p", _kp_dict(), timestamp=2.0) is good
        monkeypatch.setattr(sas, "classify_skeleton_action", boom)
        assert await svc.add_keypoints("p", _kp_dict(), timestamp=3.0) is good  # cached

    @pytest.mark.asyncio
    async def test_circular_buffer_evicts_oldest(self, classify_spy) -> None:
        svc = _service(buffer_size=3, min_frames=2, inference_interval=1)
        for i in range(5):
            await svc.add_keypoints(
                "p", np.full((17, 3), float(i), dtype=np.float32), timestamp=float(i)
            )
        assert svc.get_buffer_status()["total_frames_buffered"] == 3
        last_seq = classify_spy[-1]["seq"]
        assert last_seq[0, :, 0, 0].tolist() == [2.0, 3.0, 4.0]

    @pytest.mark.asyncio
    async def test_persons_are_independent(self, classify_spy) -> None:
        svc = _service(min_frames=2, inference_interval=2)
        await svc.add_keypoints("a", _kp_dict(), timestamp=1.0)
        await svc.add_keypoints("b", _kp_dict(), timestamp=1.0)
        assert await svc.add_keypoints("a", _kp_dict(), timestamp=2.0) is not None
        assert classify_spy[-1]["seq"].shape == (1, 2, 17, 3)  # only a's frames
        assert svc.get_buffer_status()["active_persons"] == 2


class TestCleanupStale:
    @pytest.mark.asyncio
    async def test_only_stale_buffers_removed_and_state_cleared(self, classify_spy) -> None:
        import time as time_mod

        svc = _service(min_frames=999, max_age_seconds=60.0)
        now = time_mod.time()
        await svc.add_keypoints("old", _kp_dict(), timestamp=now - 120.0)
        await svc.add_keypoints("fresh", _kp_dict(), timestamp=now - 1.0)
        removed = await svc.cleanup_stale()
        assert removed == 1
        status = svc.get_buffer_status()
        assert status["active_persons"] == 1
        assert status["total_frames_buffered"] == 1

    @pytest.mark.asyncio
    async def test_removal_drops_cached_result_and_count(self, classify_spy) -> None:
        svc = _service(min_frames=1, inference_interval=1, max_age_seconds=60.0)
        r = await svc.add_keypoints("p", _kp_dict(), timestamp=1.0)
        assert r is not None
        assert await svc.cleanup_stale() == 1
        assert svc.get_last_result("p") is None
        # frame count reset too: one new frame re-triggers inference (interval 1)
        before = len(classify_spy)
        await svc.add_keypoints("p", _kp_dict(), timestamp=1e9)
        assert len(classify_spy) == before + 1

    @pytest.mark.asyncio
    async def test_exactly_at_max_age_is_not_stale(self, classify_spy, monkeypatch) -> None:
        # freeze the clock so the strict `>` boundary is exact, not a race
        monkeypatch.setattr(sas.time, "time", lambda: 1_000.0)
        svc = _service(min_frames=999, max_age_seconds=50.0)
        await svc.add_keypoints("edge", _kp_dict(), timestamp=950.0)  # age == max_age
        assert await svc.cleanup_stale() == 0  # not strictly older
        await svc.add_keypoints("edge", _kp_dict(), timestamp=949.0)  # age 51 > 50
        assert await svc.cleanup_stale() == 1


class TestBufferStatus:
    def test_empty_service(self) -> None:
        assert _service().get_buffer_status() == {
            "active_persons": 0,
            "total_frames_buffered": 0,
            "persons_with_results": 0,
        }


class TestGlobalRegistry:
    def test_get_set_reset(self) -> None:
        reset_skeleton_action_service()
        assert get_skeleton_action_service() is None
        svc = _service()
        set_skeleton_action_service(svc)
        assert get_skeleton_action_service() is svc
        reset_skeleton_action_service()
        assert get_skeleton_action_service() is None
