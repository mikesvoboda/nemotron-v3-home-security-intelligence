"""Face recognition service for managing known persons and face matching.

This module provides the FaceRecognitionService class for:
- Managing known persons and their face embeddings
- Matching detected faces against known persons
- Recording face detection events
- Tracking unknown strangers for alerts

Implements NEM-3716: Face detection with InsightFace
Implements NEM-3717: Face quality assessment for recognition
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.core.logging import get_logger
from backend.models.face_identity import (
    FaceDetectionEvent,
    FaceEmbedding,
    KnownPerson,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# Default similarity threshold for face matching
DEFAULT_MATCH_THRESHOLD = 0.68


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


class FaceRecognitionService:
    """Service for face recognition and person management.

    This service provides methods to:
    - Create and manage known persons
    - Store and retrieve face embeddings
    - Match faces against known persons
    - Record face detection events
    - Track unknown strangers

    Usage:
        service = FaceRecognitionService()

        # Add a known person
        person = await service.create_known_person(session, "John Doe", True)

        # Add face embedding
        embedding = await service.add_face_embedding(
            session, person.id, embedding_vector, quality_score
        )

        # Match a detected face
        match = await service.match_face(session, detected_embedding)
        if match["matched"]:
            print(f"Matched: {match['person_name']}")

    Attributes:
        similarity_threshold: Default threshold for face matching
    """

    def __init__(self, similarity_threshold: float = DEFAULT_MATCH_THRESHOLD) -> None:
        """Initialize the face recognition service.

        Args:
            similarity_threshold: Default similarity threshold for matching.
        """
        self._similarity_threshold = similarity_threshold
        logger.info(
            "FaceRecognitionService initialized with threshold=%.2f",
            self._similarity_threshold,
        )

    @property
    def similarity_threshold(self) -> float:
        """Get the default similarity threshold."""
        return self._similarity_threshold

    # =========================================================================
    # Known Person Management
    # =========================================================================

    async def create_known_person(
        self,
        session: AsyncSession,
        name: str,
        is_household_member: bool = False,
        notes: str | None = None,
    ) -> KnownPerson:
        """Create a new known person.

        Args:
            session: Database session
            name: Display name of the person
            is_household_member: Whether person is a trusted household member
            notes: Optional notes about the person

        Returns:
            Created KnownPerson instance
        """
        person = KnownPerson(
            name=name,
            is_household_member=is_household_member,
            notes=notes,
        )
        session.add(person)
        await session.commit()
        await session.refresh(person)

        logger.info(
            "Created known person: %s (id=%d, household=%s)",
            name,
            person.id,
            is_household_member,
        )
        return person

    async def get_known_person(
        self,
        session: AsyncSession,
        person_id: int,
    ) -> KnownPerson | None:
        """Get a known person by ID.

        Args:
            session: Database session
            person_id: ID of the person

        Returns:
            KnownPerson instance or None if not found
        """
        stmt = (
            select(KnownPerson)
            .where(KnownPerson.id == person_id)
            .options(selectinload(KnownPerson.embeddings))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_known_persons(
        self,
        session: AsyncSession,
        household_only: bool = False,
    ) -> list[KnownPerson]:
        """List all known persons.

        Args:
            session: Database session
            household_only: If True, only return household members

        Returns:
            List of KnownPerson instances
        """
        stmt = select(KnownPerson).options(selectinload(KnownPerson.embeddings))

        if household_only:
            stmt = stmt.where(KnownPerson.is_household_member.is_(True))

        stmt = stmt.order_by(KnownPerson.name)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def update_known_person(
        self,
        session: AsyncSession,
        person_id: int,
        name: str | None = None,
        is_household_member: bool | None = None,
        notes: str | None = None,
    ) -> KnownPerson | None:
        """Update a known person.

        Args:
            session: Database session
            person_id: ID of the person to update
            name: New name (optional)
            is_household_member: New household status (optional)
            notes: New notes (optional)

        Returns:
            Updated KnownPerson instance or None if not found
        """
        person = await self.get_known_person(session, person_id)
        if person is None:
            return None

        if name is not None:
            person.name = name
        if is_household_member is not None:
            person.is_household_member = is_household_member
        if notes is not None:
            person.notes = notes

        await session.commit()
        await session.refresh(person)

        logger.info("Updated known person: %s (id=%d)", person.name, person.id)
        return person

    async def delete_known_person(
        self,
        session: AsyncSession,
        person_id: int,
    ) -> bool:
        """Delete a known person and all associated embeddings.

        Args:
            session: Database session
            person_id: ID of the person to delete

        Returns:
            True if deleted, False if not found
        """
        person = await self.get_known_person(session, person_id)
        if person is None:
            return False

        await session.delete(person)
        await session.commit()

        logger.info("Deleted known person: %s (id=%d)", person.name, person_id)
        return True

    # =========================================================================
    # Face Embedding Management
    # =========================================================================

    async def add_face_embedding(
        self,
        session: AsyncSession,
        person_id: int,
        embedding: list[float] | np.ndarray,
        quality_score: float = 1.0,
        source_image_path: str | None = None,
    ) -> FaceEmbedding | None:
        """Add a face embedding for a known person.

        Args:
            session: Database session
            person_id: ID of the person
            embedding: 512-dimensional embedding vector
            quality_score: Face quality score (0-1)
            source_image_path: Path to source image (optional)

        Returns:
            Created FaceEmbedding instance or None if person not found
        """
        # Verify person exists
        person = await self.get_known_person(session, person_id)
        if person is None:
            logger.warning("Cannot add embedding: person %d not found", person_id)
            return None

        # Convert to numpy array and serialize
        if isinstance(embedding, list):
            embedding_array = np.array(embedding, dtype=np.float32)
        else:
            embedding_array = embedding.astype(np.float32)

        # Normalize the embedding
        norm = np.linalg.norm(embedding_array)
        if norm > 0:
            embedding_array = embedding_array / norm

        # Serialize to bytes
        embedding_bytes = embedding_array.tobytes()

        face_embedding = FaceEmbedding(
            person_id=person_id,
            embedding=embedding_bytes,
            quality_score=quality_score,
            source_image_path=source_image_path,
        )
        session.add(face_embedding)
        await session.commit()
        await session.refresh(face_embedding)

        logger.info(
            "Added face embedding for person %s (id=%d, quality=%.2f)",
            person.name,
            person_id,
            quality_score,
        )
        return face_embedding

    async def get_person_embeddings(
        self,
        session: AsyncSession,
        person_id: int,
    ) -> list[FaceEmbedding]:
        """Get all embeddings for a person.

        Args:
            session: Database session
            person_id: ID of the person

        Returns:
            List of FaceEmbedding instances
        """
        stmt = (
            select(FaceEmbedding)
            .where(FaceEmbedding.person_id == person_id)
            .order_by(FaceEmbedding.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def delete_face_embedding(
        self,
        session: AsyncSession,
        embedding_id: int,
    ) -> bool:
        """Delete a face embedding.

        Args:
            session: Database session
            embedding_id: ID of the embedding to delete

        Returns:
            True if deleted, False if not found
        """
        stmt = select(FaceEmbedding).where(FaceEmbedding.id == embedding_id)
        result = await session.execute(stmt)
        embedding = result.scalar_one_or_none()

        if embedding is None:
            return False

        await session.delete(embedding)
        await session.commit()

        logger.info("Deleted face embedding %d", embedding_id)
        return True

    # =========================================================================
    # Face Matching
    # =========================================================================

    async def _get_all_embeddings(
        self,
        session: AsyncSession,
    ) -> list[tuple[int, str, bool, np.ndarray]]:
        """Get all embeddings with person info.

        Returns:
            List of (person_id, person_name, is_household, embedding_array)
        """
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        embeddings = result.scalars().all()

        results = []
        for emb in embeddings:
            if emb.person is None:
                continue

            try:
                embedding_array = np.frombuffer(emb.embedding, dtype=np.float32)
                results.append(
                    (
                        emb.person.id,
                        emb.person.name,
                        emb.person.is_household_member,
                        embedding_array,
                    )
                )
            except Exception as e:
                logger.warning(
                    "Failed to deserialize embedding %d: %s",
                    emb.id,
                    str(e),
                )

        return results

    async def match_face(
        self,
        session: AsyncSession,
        embedding: list[float] | np.ndarray,
        threshold: float | None = None,
    ) -> dict:
        """Match a face embedding against known persons.

        Args:
            session: Database session
            embedding: 512-dimensional embedding to match
            threshold: Minimum similarity for a match (uses default if None)

        Returns:
            Dict with match results:
            - matched: bool
            - person_id: int | None
            - person_name: str | None
            - similarity: float
            - is_unknown: bool
            - is_household_member: bool | None
        """
        if threshold is None:
            threshold = self._similarity_threshold

        # Convert to numpy array
        if isinstance(embedding, list):
            query_embedding = np.array(embedding, dtype=np.float32)
        else:
            query_embedding = embedding.astype(np.float32)

        # Normalize
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        # Get all known embeddings
        known_embeddings = await self._get_all_embeddings(session)

        if not known_embeddings:
            logger.debug("No known embeddings in database")
            return {
                "matched": False,
                "person_id": None,
                "person_name": None,
                "similarity": 0.0,
                "is_unknown": True,
                "is_household_member": None,
            }

        best_match: dict | None = None
        best_similarity = -1.0

        for person_id, person_name, is_household, known_emb in known_embeddings:
            similarity = cosine_similarity(query_embedding, known_emb)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = {
                    "person_id": person_id,
                    "person_name": person_name,
                    "is_household_member": is_household,
                }

        if best_similarity >= threshold and best_match is not None:
            logger.debug(
                "Face matched to %s (id=%d) with similarity %.3f",
                best_match["person_name"],
                best_match["person_id"],
                best_similarity,
            )
            return {
                "matched": True,
                "person_id": best_match["person_id"],
                "person_name": best_match["person_name"],
                "similarity": best_similarity,
                "is_unknown": False,
                "is_household_member": best_match["is_household_member"],
            }
        else:
            logger.debug(
                "No match found (best similarity: %.3f, threshold: %.2f)",
                best_similarity,
                threshold,
            )
            return {
                "matched": False,
                "person_id": None,
                "person_name": None,
                "similarity": best_similarity,
                "is_unknown": True,
                "is_household_member": None,
            }

    # =========================================================================
    # Face Detection Event Recording
    # =========================================================================

    async def record_face_detection(
        self,
        session: AsyncSession,
        camera_id: str,
        timestamp: datetime,
        bbox: list[float],
        embedding: list[float] | np.ndarray,
        quality_score: float,
        age_estimate: int | None = None,
        gender_estimate: str | None = None,
        auto_match: bool = True,
    ) -> FaceDetectionEvent:
        """Record a face detection event.

        Args:
            session: Database session
            camera_id: ID of the camera
            timestamp: When the face was detected
            bbox: Bounding box [x1, y1, x2, y2]
            embedding: 512-dimensional embedding
            quality_score: Face quality score
            age_estimate: Estimated age (optional)
            gender_estimate: Estimated gender 'M' or 'F' (optional)
            auto_match: Whether to automatically match against known persons

        Returns:
            Created FaceDetectionEvent instance
        """
        # Convert embedding to bytes
        if isinstance(embedding, list):
            embedding_array = np.array(embedding, dtype=np.float32)
        else:
            embedding_array = embedding.astype(np.float32)

        # Normalize
        norm = np.linalg.norm(embedding_array)
        if norm > 0:
            embedding_array = embedding_array / norm

        embedding_bytes = embedding_array.tobytes()

        # Initialize match fields
        matched_person_id = None
        match_confidence = None
        is_unknown = True

        # Auto-match if enabled
        if auto_match:
            match_result = await self.match_face(session, embedding_array)
            if match_result["matched"]:
                matched_person_id = match_result["person_id"]
                match_confidence = match_result["similarity"]
                is_unknown = False

        event = FaceDetectionEvent(
            camera_id=camera_id,
            timestamp=timestamp,
            bbox={"coordinates": bbox},
            embedding=embedding_bytes,
            matched_person_id=matched_person_id,
            match_confidence=match_confidence,
            is_unknown=is_unknown,
            quality_score=quality_score,
            age_estimate=age_estimate,
            gender_estimate=gender_estimate,
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)

        if is_unknown:
            logger.info(
                "Recorded unknown face detection on camera %s (quality=%.2f)",
                camera_id,
                quality_score,
            )
        else:
            logger.info(
                "Recorded face detection on camera %s, matched person_id=%d",
                camera_id,
                matched_person_id,
            )

        return event

    async def list_face_events(
        self,
        session: AsyncSession,
        camera_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        unknown_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[FaceDetectionEvent], int]:
        """List face detection events with optional filters.

        Args:
            session: Database session
            camera_id: Filter by camera ID (optional)
            start_time: Filter events after this time (optional)
            end_time: Filter events before this time (optional)
            unknown_only: If True, only return unknown faces
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            Tuple of (list of events, total count)
        """
        stmt = select(FaceDetectionEvent).options(selectinload(FaceDetectionEvent.matched_person))

        if camera_id is not None:
            stmt = stmt.where(FaceDetectionEvent.camera_id == camera_id)
        if start_time is not None:
            stmt = stmt.where(FaceDetectionEvent.timestamp >= start_time)
        if end_time is not None:
            stmt = stmt.where(FaceDetectionEvent.timestamp <= end_time)
        if unknown_only:
            stmt = stmt.where(FaceDetectionEvent.is_unknown.is_(True))

        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Get paginated results
        stmt = stmt.order_by(FaceDetectionEvent.timestamp.desc())
        stmt = stmt.limit(limit).offset(offset)
        result = await session.execute(stmt)
        events = list(result.scalars().all())

        return events, total

    async def get_unknown_strangers(
        self,
        session: AsyncSession,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        min_quality: float = 0.3,
        limit: int = 100,
    ) -> list[FaceDetectionEvent]:
        """Get unknown stranger detections for alerts.

        Args:
            session: Database session
            start_time: Filter events after this time (optional)
            end_time: Filter events before this time (optional)
            min_quality: Minimum quality score for reliable detections
            limit: Maximum number of events to return

        Returns:
            List of unknown face detection events
        """
        stmt = (
            select(FaceDetectionEvent)
            .where(FaceDetectionEvent.is_unknown.is_(True))
            .where(FaceDetectionEvent.quality_score >= min_quality)
        )

        if start_time is not None:
            stmt = stmt.where(FaceDetectionEvent.timestamp >= start_time)
        if end_time is not None:
            stmt = stmt.where(FaceDetectionEvent.timestamp <= end_time)

        stmt = stmt.order_by(FaceDetectionEvent.timestamp.desc()).limit(limit)
        result = await session.execute(stmt)

        return list(result.scalars().all())


# =============================================================================
# Global Service Instance (Singleton Pattern)
# =============================================================================

_face_recognition_service: FaceRecognitionService | None = None


def get_face_recognition_service() -> FaceRecognitionService:
    """Get or create the global FaceRecognitionService instance.

    Returns:
        Global FaceRecognitionService instance
    """
    global _face_recognition_service  # noqa: PLW0603
    if _face_recognition_service is None:
        _face_recognition_service = FaceRecognitionService()
    return _face_recognition_service


def reset_face_recognition_service() -> None:
    """Reset the global FaceRecognitionService instance (for testing)."""
    global _face_recognition_service  # noqa: PLW0603
    _face_recognition_service = None
