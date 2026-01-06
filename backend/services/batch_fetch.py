"""Batch fetching service for detections.

This module provides utilities to batch fetch detections by ID, avoiding N+1 query
problems when fetching large numbers of detections. The batch fetching approach:

1. Deduplicates input IDs
2. Splits IDs into configurable batch sizes
3. Executes batched queries with IN clauses
4. Aggregates results efficiently

Usage:
    from backend.services.batch_fetch import batch_fetch_detections

    async with get_session() as session:
        detections = await batch_fetch_detections(session, detection_ids)

For dictionary access by ID:
    detection_map = await batch_fetch_detections_by_ids(session, detection_ids)
    detection = detection_map.get(123)  # O(1) lookup
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.core.logging import get_logger
from backend.models.detection import Detection

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# Configuration constants for batch sizes
# These values are tuned for typical PostgreSQL IN clause performance
MIN_BATCH_SIZE: int = 1
DEFAULT_BATCH_SIZE: int = 250  # Balanced between query count and IN clause size
MAX_BATCH_SIZE: int = 1000  # PostgreSQL handles IN clauses well up to ~1000 items


def _clamp_batch_size(batch_size: int) -> int:
    """Clamp batch size to valid range.

    Args:
        batch_size: Requested batch size

    Returns:
        Batch size clamped to [MIN_BATCH_SIZE, MAX_BATCH_SIZE]
    """
    return max(MIN_BATCH_SIZE, min(batch_size, MAX_BATCH_SIZE))


async def batch_fetch_detections(
    session: AsyncSession,
    detection_ids: list[int],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    order_by_time: bool = True,
) -> list[Detection]:
    """Fetch detections by IDs using batched queries.

    This function efficiently fetches detections by splitting large ID lists
    into smaller batches, avoiding query timeout issues with very large IN
    clauses and preventing N+1 query patterns.

    Args:
        session: SQLAlchemy async session
        detection_ids: List of detection IDs to fetch
        batch_size: Maximum IDs per query (clamped to MIN/MAX_BATCH_SIZE)
        order_by_time: If True, order results by detected_at ascending

    Returns:
        List of Detection objects, ordered by detected_at if order_by_time=True

    Example:
        detections = await batch_fetch_detections(session, [1, 2, 3, 4, 5])
    """
    if not detection_ids:
        logger.debug("batch_fetch_detections called with empty ID list")
        return []

    # Deduplicate IDs
    unique_ids = list(set(detection_ids))

    # Clamp batch size to valid range
    effective_batch_size = _clamp_batch_size(batch_size)

    if len(unique_ids) != len(detection_ids):
        logger.debug(f"Deduplicated detection IDs: {len(detection_ids)} -> {len(unique_ids)}")

    # If all IDs fit in one batch, execute single query
    if len(unique_ids) <= effective_batch_size:
        query = select(Detection).where(Detection.id.in_(unique_ids))
        if order_by_time:
            query = query.order_by(Detection.detected_at.asc())
        result = await session.execute(query)
        detections = list(result.scalars().all())
        logger.debug(
            f"Fetched {len(detections)} detections in single query (requested: {len(unique_ids)})"
        )
        return detections

    # Split into batches
    all_detections: list[Detection] = []
    batch_count = 0

    for i in range(0, len(unique_ids), effective_batch_size):
        batch_ids = unique_ids[i : i + effective_batch_size]
        batch_count += 1

        query = select(Detection).where(Detection.id.in_(batch_ids))
        result = await session.execute(query)
        batch_detections = list(result.scalars().all())
        all_detections.extend(batch_detections)

    logger.debug(
        f"Fetched {len(all_detections)} detections in {batch_count} batches "
        f"(requested: {len(unique_ids)}, batch_size: {effective_batch_size})"
    )

    # Sort by detected_at if requested
    if order_by_time:
        all_detections.sort(key=lambda d: d.detected_at)

    return all_detections


async def batch_fetch_detections_by_ids(
    session: AsyncSession,
    detection_ids: list[int],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[int, Detection]:
    """Fetch detections by IDs and return as a dictionary keyed by ID.

    This is useful when you need O(1) lookup by detection ID after fetching.

    Args:
        session: SQLAlchemy async session
        detection_ids: List of detection IDs to fetch
        batch_size: Maximum IDs per query (clamped to MIN/MAX_BATCH_SIZE)

    Returns:
        Dictionary mapping detection ID to Detection object.
        Missing IDs will not be present in the result.

    Example:
        detection_map = await batch_fetch_detections_by_ids(session, [1, 2, 3])
        det = detection_map.get(1)  # Returns Detection or None
    """
    detections = await batch_fetch_detections(
        session, detection_ids, batch_size=batch_size, order_by_time=False
    )
    return {d.id: d for d in detections}


async def batch_fetch_file_paths(
    session: AsyncSession,
    detection_ids: list[int],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[str]:
    """Fetch only file paths for detections (optimized for file path access).

    This is more efficient than batch_fetch_detections when you only need
    file paths, as it only queries the file_path column.

    Args:
        session: SQLAlchemy async session
        detection_ids: List of detection IDs to fetch
        batch_size: Maximum IDs per query (clamped to MIN/MAX_BATCH_SIZE)

    Returns:
        List of file paths (as strings), filtered to remove None values

    Example:
        paths = await batch_fetch_file_paths(session, detection_ids)
    """
    if not detection_ids:
        return []

    # Deduplicate IDs
    unique_ids = list(set(detection_ids))
    effective_batch_size = _clamp_batch_size(batch_size)

    all_paths: list[str] = []

    for i in range(0, len(unique_ids), effective_batch_size):
        batch_ids = unique_ids[i : i + effective_batch_size]

        query = select(Detection.file_path).where(Detection.id.in_(batch_ids))
        result = await session.execute(query)
        batch_paths = [row[0] for row in result.all() if row[0] is not None]
        all_paths.extend(batch_paths)

    logger.debug(f"Fetched {len(all_paths)} file paths for {len(unique_ids)} detection IDs")
    return all_paths
