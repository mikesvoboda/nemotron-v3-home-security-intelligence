"""Household matcher service functions for alert engine integration.

This module provides simple service functions that wrap the HouseholdMatcher class
for use in the alert engine. These functions are designed to be easily mockable
in tests.

Related to NEM-5085: Alert Rule Condition Types
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


async def check_household_match(
    session: AsyncSession,  # noqa: ARG001 - reserved for future DB queries
    track_id: int,
    camera_id: str,
) -> bool:
    """Check if a track belongs to a household member.

    This function is used by the alert engine to determine if a dwell time
    record should be excluded from alerts due to being a household member.

    Args:
        session: Database session for queries
        track_id: The track ID to check
        camera_id: The camera ID where the track was detected

    Returns:
        True if the track belongs to a household member, False otherwise.

    Note:
        Currently this is a placeholder implementation. The full implementation
        would query the Track model to get the associated embedding and then
        use the HouseholdMatcher to check for a match.
    """
    # TODO: Implement full track-to-household matching
    # For now, this always returns False (no household match)
    # Full implementation would:
    # 1. Query Track table by track_id and camera_id
    # 2. Get the associated person embedding from the track's detections
    # 3. Use HouseholdMatcher.match_person() to check for a match
    # 4. Return True if similarity exceeds threshold

    logger.debug(
        "Checking household match for track_id=%d, camera_id=%s",
        track_id,
        camera_id,
    )

    # Placeholder: Always return False (not a household member)
    # This ensures alerts still fire during development
    return False
