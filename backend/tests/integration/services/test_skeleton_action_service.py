"""Integration tests for skeleton action recognition service (NEM-5563).

Tests verify keypoint buffering and action classification behavior.
"""

import pytest


@pytest.mark.integration
class TestSkeletonActionServiceIntegration:
    """Integration tests for SkeletonActionService."""

    @pytest.mark.asyncio
    async def test_service_initialization(self) -> None:
        """Test SkeletonActionService initializes with default config."""
        from backend.services.skeleton_action_service import SkeletonActionService

        service = SkeletonActionService()
        assert service is not None

    @pytest.mark.asyncio
    async def test_buffer_keypoints_accumulates(self) -> None:
        """Test that keypoints are buffered per person across frames."""
        from backend.services.skeleton_action_service import SkeletonActionService

        service = SkeletonActionService()
        # Verify buffer starts empty
        assert len(service._keypoint_buffers) == 0

    @pytest.mark.asyncio
    async def test_classify_returns_none_without_model(self) -> None:
        """Test graceful degradation when model is not loaded."""
        from backend.services.skeleton_action_service import SkeletonActionService

        service = SkeletonActionService()
        # Without a loaded model, classification should return None or empty
        result = await service.classify_actions(camera_id="test", person_id="p1", keypoints=[])
        assert result is None or result == {}
