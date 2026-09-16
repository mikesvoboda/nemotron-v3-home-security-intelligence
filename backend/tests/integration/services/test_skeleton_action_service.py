"""Integration tests for skeleton action recognition service (NEM-5563).

Tests verify keypoint buffering and action classification behavior.

Aligned to the SHIPPED contract (ledger R-T9-SKELETON):
- SkeletonActionService.__init__ requires model_dict (the loaded ST-GCN++
  checkpoint dict from load_stgcn_model) — there is no zero-arg
  constructor (skeleton_action_service.py:76).
- The per-person buffer attribute is ``_buffers`` (a defaultdict of
  deques), not ``_keypoint_buffers`` (skeleton_action_service.py:100).
- There is no ``classify_actions(camera_id=...)`` method; the entry point
  is ``await add_keypoints(person_id=..., keypoints=...)`` which returns
  None (falling back to the cached last result) when inference has not run.
"""

import numpy as np
import pytest


def _stub_model_dict() -> dict:
    """Minimal stand-in for the loaded ST-GCN++ model dict.

    The service stores model_dict and only touches it inside
    classify_skeleton_action once min_frames/inference_interval are met —
    these tests never reach inference, so an opaque stub is sufficient.
    """
    return {"state": "stub"}


@pytest.mark.integration
class TestSkeletonActionServiceIntegration:
    """Integration tests for SkeletonActionService."""

    @pytest.mark.asyncio
    async def test_service_initialization(self) -> None:
        """Test SkeletonActionService initializes with default config."""
        from backend.services.skeleton_action_service import SkeletonActionService

        service = SkeletonActionService(_stub_model_dict())
        assert service is not None
        status = service.get_buffer_status()
        assert status["active_persons"] == 0
        assert status["total_frames_buffered"] == 0

    @pytest.mark.asyncio
    async def test_buffer_keypoints_accumulates(self) -> None:
        """Test that keypoints are buffered per person across frames."""
        from backend.services.skeleton_action_service import SkeletonActionService

        service = SkeletonActionService(_stub_model_dict(), inference_interval=10**6)
        # Verify buffer starts empty
        assert len(service._buffers) == 0

        # Feed two frames for one person — below inference_interval, so no
        # classification is attempted and the buffer accumulates.
        frame = np.zeros((17, 3), dtype=np.float32)
        assert await service.add_keypoints("p1", frame) is None
        assert await service.add_keypoints("p1", frame) is None

        status = service.get_buffer_status()
        assert status["active_persons"] == 1
        assert status["total_frames_buffered"] == 2

    @pytest.mark.asyncio
    async def test_classify_returns_none_without_enough_frames(self) -> None:
        """Test graceful degradation before the min-frames threshold.

        The shipped service has no classify_actions(); add_keypoints
        returns None until min_frames have accumulated, and never
        dereferences the model below that threshold.
        """
        from backend.services.skeleton_action_service import SkeletonActionService

        service = SkeletonActionService(_stub_model_dict())
        frame = np.zeros((17, 3), dtype=np.float32)
        result = await service.add_keypoints(person_id="p1", keypoints=frame)
        assert result is None
        assert service.get_last_result("p1") is None
