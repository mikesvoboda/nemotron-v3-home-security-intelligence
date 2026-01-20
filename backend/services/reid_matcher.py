"""Person re-identification matching service.

This module provides the ReIDMatcher service for matching person re-ID embeddings
across detections and time, enabling tracking of individuals across cameras.

The service uses cosine similarity to compare embeddings stored in the Detection
model's enrichment_data field under the 'reid_embedding' key.

Related to NEM-3043: Implement Re-ID Matching Service.

Example:
    from backend.services.reid_matcher import ReIDMatcher

    async with get_session() as session:
        matcher = ReIDMatcher(session, similarity_threshold=0.7)

        # Find matches for a new detection
        matches = await matcher.find_matches(
            embedding=[0.1, 0.2, ...],
            time_window_hours=24,
            max_results=10,
        )

        # Check if this is a known person
        is_known, best_match = await matcher.is_known_person(
            embedding=[0.1, 0.2, ...],
            time_window_hours=24,
        )
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import and_, desc, select

from backend.core.logging import get_logger
from backend.models import Detection

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# Default similarity threshold for considering a match
DEFAULT_SIMILARITY_THRESHOLD = 0.7

# Default time window for searching matches (hours)
DEFAULT_TIME_WINDOW_HOURS = 24

# Default embedding dimension for ReID models (OSNet-x0.25 produces 512-dim embeddings)
DEFAULT_EMBEDDING_DIMENSION = 512


@dataclass
class ReIDMatch:
    """Represents a re-identification match result.

    Attributes:
        detection_id: ID of the matching detection
        similarity: Cosine similarity score (0.0 to 1.0)
        timestamp: When the matching detection was recorded
        camera_id: ID of the camera that captured the detection
    """

    detection_id: int
    similarity: float
    timestamp: datetime
    camera_id: str | None = None


class ReIDMatcher:
    """Service for matching person re-ID embeddings across detections.

    Uses cosine similarity to find matching persons from recent detections.
    Embeddings are stored in the Detection model's enrichment_data field
    under the 'reid_embedding' key.

    Attributes:
        session: SQLAlchemy async session for database operations
        threshold: Minimum similarity score to consider a match (0-1)

    Example:
        matcher = ReIDMatcher(session, similarity_threshold=0.7)

        # Find matches for an embedding
        matches = await matcher.find_matches(
            embedding=[0.1, 0.2, ...],
            time_window_hours=24,
            max_results=10,
        )

        for match in matches:
            print(f"Detection {match.detection_id}: {match.similarity:.2f}")
    """

    def __init__(
        self,
        session: AsyncSession,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> None:
        """Initialize the ReIDMatcher.

        Args:
            session: SQLAlchemy async session for database operations.
            similarity_threshold: Minimum similarity score (0-1) to consider
                a detection as matching. Higher values require more similar
                embeddings for a match. Default: 0.7
        """
        self.session = session
        self.threshold = similarity_threshold

        logger.debug(
            "ReIDMatcher initialized with threshold=%s",
            similarity_threshold,
        )

    async def find_matches(
        self,
        embedding: list[float],
        time_window_hours: int = DEFAULT_TIME_WINDOW_HOURS,
        max_results: int = 10,
        exclude_detection_id: int | None = None,
    ) -> list[ReIDMatch]:
        """Find matching persons from recent detections.

        Searches detections within the time window that have ReID embeddings
        and computes cosine similarity with the query embedding.

        Args:
            embedding: Query embedding vector (typically 512-dim from OSNet)
            time_window_hours: How far back to search for matches (default: 24)
            max_results: Maximum number of matches to return (default: 10)
            exclude_detection_id: Optional detection ID to exclude from results
                (useful when checking if a new detection matches existing ones)

        Returns:
            List of ReIDMatch objects sorted by similarity (highest first),
            containing only matches above the configured threshold.

        Example:
            matches = await matcher.find_matches(
                embedding=[0.1, 0.2, ...],
                time_window_hours=48,
                max_results=5,
                exclude_detection_id=123,
            )
        """
        if not embedding:
            logger.warning("Empty embedding provided to find_matches")
            return []

        # Calculate time cutoff
        cutoff = datetime.now(UTC) - timedelta(hours=time_window_hours)

        # Build query for recent detections with reid embeddings
        # Filter for person detections that have reid_embedding in enrichment_data
        stmt = (
            select(Detection)
            .where(
                and_(
                    Detection.detected_at >= cutoff,
                    Detection.enrichment_data.isnot(None),
                    # Check if reid_embedding key exists in JSONB
                    Detection.enrichment_data.op("?")("reid_embedding"),
                )
            )
            .order_by(desc(Detection.detected_at))
        )

        if exclude_detection_id is not None:
            stmt = stmt.where(Detection.id != exclude_detection_id)

        result = await self.session.execute(stmt)
        recent_detections = result.scalars().all()

        if not recent_detections:
            logger.debug("No recent detections with ReID embeddings found")
            return []

        # Compute similarity for each detection
        matches: list[ReIDMatch] = []

        for detection in recent_detections:
            stored_embedding = self._get_reid_embedding(detection)
            if stored_embedding is None:
                continue

            similarity = self._cosine_similarity(embedding, stored_embedding)

            if similarity >= self.threshold:
                matches.append(
                    ReIDMatch(
                        detection_id=detection.id,
                        similarity=similarity,
                        timestamp=detection.detected_at,
                        camera_id=detection.camera_id,
                    )
                )

        # Sort by similarity (highest first) and limit results
        matches.sort(key=lambda x: x.similarity, reverse=True)

        logger.debug(
            "Found %d matches above threshold %.2f (searched %d detections)",
            len(matches[:max_results]),
            self.threshold,
            len(recent_detections),
        )

        return matches[:max_results]

    def _get_reid_embedding(self, detection: Detection) -> list[float] | None:
        """Extract ReID embedding from a detection's enrichment data.

        Args:
            detection: Detection model instance

        Returns:
            The ReID embedding vector if present, None otherwise
        """
        if detection.enrichment_data is None:
            return None

        reid_data = detection.enrichment_data.get("reid_embedding")
        if reid_data is None:
            return None

        # Handle both direct embedding list and dict with "vector" key
        if isinstance(reid_data, list):
            return list(reid_data)
        if isinstance(reid_data, dict) and "vector" in reid_data:
            vector = reid_data["vector"]
            return list(vector) if vector is not None else None

        return None

    @staticmethod
    def _cosine_similarity(vec1: Sequence[float], vec2: Sequence[float]) -> float:
        """Compute cosine similarity between two embedding vectors.

        Args:
            vec1: First embedding vector
            vec2: Second embedding vector

        Returns:
            Cosine similarity score between 0 and 1.
            Returns 0.0 if vectors have different dimensions or either is empty.
        """
        if len(vec1) != len(vec2) or len(vec1) == 0:
            return 0.0

        # Compute dot product and magnitudes
        dot_product: float = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        magnitude1: float = sum(a * a for a in vec1) ** 0.5
        magnitude2: float = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return float(dot_product / (magnitude1 * magnitude2))

    async def store_embedding(
        self,
        detection_id: int,
        embedding: list[float],
    ) -> bool:
        """Store a ReID embedding for a detection.

        Updates the detection's enrichment_data field to include the
        ReID embedding with metadata.

        Args:
            detection_id: ID of the detection to update
            embedding: ReID embedding vector to store

        Returns:
            True if the embedding was stored successfully, False if the
            detection was not found.

        Example:
            success = await matcher.store_embedding(
                detection_id=123,
                embedding=[0.1, 0.2, ...],
            )
        """
        # Get the detection
        stmt = select(Detection).where(Detection.id == detection_id)
        result = await self.session.execute(stmt)
        detection = result.scalar_one_or_none()

        if detection is None:
            logger.warning("Detection %d not found for storing ReID embedding", detection_id)
            return False

        # Create embedding hash for quick lookup
        embedding_hash = self._compute_embedding_hash(embedding)

        # Initialize enrichment_data if None
        if detection.enrichment_data is None:
            detection.enrichment_data = {}

        # Store embedding with metadata
        detection.enrichment_data = {
            **detection.enrichment_data,
            "reid_embedding": {
                "vector": embedding,
                "dimension": len(embedding),
                "hash": embedding_hash,
                "model": "osnet_x0_25",  # Default model name
                "stored_at": datetime.now(UTC).isoformat(),
            },
        }

        await self.session.flush()

        logger.debug(
            "Stored ReID embedding for detection %d (dim=%d, hash=%s)",
            detection_id,
            len(embedding),
            embedding_hash[:8],
        )

        return True

    @staticmethod
    def _compute_embedding_hash(embedding: list[float]) -> str:
        """Compute a hash of the embedding for quick lookup.

        Args:
            embedding: The embedding vector

        Returns:
            SHA-256 hash string (first 16 characters)
        """
        # Convert to bytes for hashing
        embedding_bytes = bytes(str(embedding), "utf-8")
        return hashlib.sha256(embedding_bytes).hexdigest()[:16]

    async def is_known_person(
        self,
        embedding: list[float],
        time_window_hours: int = DEFAULT_TIME_WINDOW_HOURS,
    ) -> tuple[bool, ReIDMatch | None]:
        """Check if this person has been seen before.

        Convenience method that searches for any match above the threshold.

        Args:
            embedding: Query embedding vector
            time_window_hours: How far back to search (default: 24)

        Returns:
            Tuple of (is_known, best_match) where:
            - is_known: True if at least one match was found
            - best_match: The highest-similarity match, or None if not found

        Example:
            is_known, best_match = await matcher.is_known_person(
                embedding=[0.1, 0.2, ...],
                time_window_hours=48,
            )
            if is_known:
                print(f"Known person! Best match: {best_match.detection_id}")
        """
        matches = await self.find_matches(
            embedding,
            time_window_hours=time_window_hours,
            max_results=1,
        )

        if matches:
            return True, matches[0]
        return False, None

    async def get_person_history(
        self,
        embedding: list[float],
        time_window_hours: int = 72,
    ) -> list[ReIDMatch]:
        """Get full history of when this person was seen.

        Searches for all matches within a longer time window to build
        a history of sightings for the given person.

        Args:
            embedding: Query embedding vector for the person
            time_window_hours: How far back to search (default: 72 hours)

        Returns:
            List of ReIDMatch objects representing historical sightings,
            sorted by similarity (highest first).

        Example:
            history = await matcher.get_person_history(
                embedding=[0.1, 0.2, ...],
                time_window_hours=168,  # 1 week
            )
            for sighting in history:
                print(f"Seen on camera {sighting.camera_id} at {sighting.timestamp}")
        """
        return await self.find_matches(
            embedding,
            time_window_hours=time_window_hours,
            max_results=100,  # Get more history
        )

    async def get_sightings_by_camera(
        self,
        embedding: list[float],
        time_window_hours: int = DEFAULT_TIME_WINDOW_HOURS,
    ) -> dict[str, list[ReIDMatch]]:
        """Get sightings of a person grouped by camera.

        Useful for understanding movement patterns across cameras.

        Args:
            embedding: Query embedding vector for the person
            time_window_hours: How far back to search (default: 24)

        Returns:
            Dictionary mapping camera_id to list of sightings on that camera

        Example:
            by_camera = await matcher.get_sightings_by_camera(
                embedding=[0.1, 0.2, ...],
                time_window_hours=24,
            )
            for camera_id, sightings in by_camera.items():
                print(f"Camera {camera_id}: {len(sightings)} sightings")
        """
        matches = await self.find_matches(
            embedding,
            time_window_hours=time_window_hours,
            max_results=100,
        )

        # Group by camera
        by_camera: dict[str, list[ReIDMatch]] = {}
        for match in matches:
            camera_id = match.camera_id or "unknown"
            if camera_id not in by_camera:
                by_camera[camera_id] = []
            by_camera[camera_id].append(match)

        return by_camera


# =============================================================================
# Factory Functions
# =============================================================================


def get_reid_matcher(
    session: AsyncSession,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> ReIDMatcher:
    """Create a ReIDMatcher instance.

    Factory function for creating ReIDMatcher with the provided session.
    Creates a new service instance each time because the service depends
    on a request-scoped session.

    Args:
        session: SQLAlchemy async session for database operations
        similarity_threshold: Minimum similarity for matching (default: 0.7)

    Returns:
        ReIDMatcher instance

    Example:
        async with get_session() as session:
            matcher = get_reid_matcher(session, similarity_threshold=0.75)
            matches = await matcher.find_matches(embedding)
    """
    return ReIDMatcher(
        session=session,
        similarity_threshold=similarity_threshold,
    )
