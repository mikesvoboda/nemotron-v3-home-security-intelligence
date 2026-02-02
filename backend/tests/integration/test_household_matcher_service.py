"""Integration tests for household matcher service.

This module provides integration tests for the household_matcher_service module,
verifying behavior with real database sessions.

Related to NEM-5085: Alert Rule Condition Types
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.household_matcher_service import check_household_match


@pytest.mark.integration
class TestHouseholdMatcherServiceIntegration:
    """Integration tests for household matcher service functions."""

    @pytest.mark.asyncio
    async def test_check_household_match_returns_false_placeholder(self, db_session: AsyncSession):
        """Verify check_household_match returns False (placeholder implementation).

        The current implementation is a placeholder that always returns False.
        This test verifies the behavior with a real database session.
        """
        result = await check_household_match(
            session=db_session,
            track_id=123,
            camera_id="test_camera",
        )

        # Placeholder implementation always returns False
        assert result is False

    @pytest.mark.asyncio
    async def test_check_household_match_with_different_inputs(self, db_session: AsyncSession):
        """Verify check_household_match handles various input values.

        Tests that the function handles different track_id and camera_id values
        without errors, even though it currently returns False for all.
        """
        test_cases = [
            (1, "cam1"),
            (999999, "front_door"),
            (0, "back_yard"),
            (42, "garage"),
        ]

        for track_id, camera_id in test_cases:
            result = await check_household_match(
                session=db_session,
                track_id=track_id,
                camera_id=camera_id,
            )
            assert result is False, f"Failed for track_id={track_id}, camera_id={camera_id}"
