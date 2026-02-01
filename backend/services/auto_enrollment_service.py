"""Auto-enrollment service for high-confidence face detections.

This service automatically enrolls faces from high-confidence detections
into the known persons database, with options for:
- Queue-based review workflow (default)
- Fully automatic enrollment mode
- Duplicate detection to prevent re-enrolling known faces
- Linking to existing household members when possible

Implements NEM-4941: Face Auto-Enrollment from High-Confidence Detections
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.core.logging import get_logger
from backend.models.face_identity import (
    EnrollmentCandidate,
    EnrollmentStatus,
    FaceDetectionEvent,
    FaceEmbedding,
    KnownPerson,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# Default thresholds for auto-enrollment
DEFAULT_CONFIDENCE_THRESHOLD = 0.95  # Minimum detection confidence
DEFAULT_QUALITY_THRESHOLD = 0.8  # Minimum face quality score
DEFAULT_SIMILARITY_THRESHOLD = 0.85  # Threshold for duplicate detection


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


class AutoEnrollmentService:
    """Service for automatic face enrollment from high-confidence detections.

    This service provides methods to:
    - Evaluate faces for auto-enrollment eligibility
    - Detect duplicate faces to prevent re-enrollment
    - Add eligible faces to an enrollment queue for review
    - Automatically enroll faces when enabled
    - Approve or reject enrollment candidates

    Usage:
        service = AutoEnrollmentService()

        # Process a face detection event
        result = await service.process_event(session, face_event)
        if result["action"] == "queued":
            print(f"Added to queue: {result['candidate_id']}")
        elif result["action"] == "enrolled":
            print(f"Auto-enrolled as: {result['person_id']}")

    Attributes:
        confidence_threshold: Minimum detection confidence for eligibility
        quality_threshold: Minimum face quality score for eligibility
        similarity_threshold: Threshold for duplicate detection
        auto_approve: If True, skip queue and auto-enroll immediately
    """

    def __init__(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        auto_approve: bool = False,
    ) -> None:
        """Initialize the auto-enrollment service.

        Args:
            confidence_threshold: Minimum confidence for enrollment (0-1)
            quality_threshold: Minimum quality score for enrollment (0-1)
            similarity_threshold: Similarity threshold for duplicate detection (0-1)
            auto_approve: If True, automatically enroll without queue review
        """
        self._confidence_threshold = confidence_threshold
        self._quality_threshold = quality_threshold
        self._similarity_threshold = similarity_threshold
        self._auto_approve = auto_approve

        logger.info(
            "AutoEnrollmentService initialized: "
            f"confidence={self._confidence_threshold}, "
            f"quality={self._quality_threshold}, "
            f"similarity={self._similarity_threshold}, "
            f"auto_approve={self._auto_approve}"
        )

    @property
    def confidence_threshold(self) -> float:
        """Get the confidence threshold."""
        return self._confidence_threshold

    @property
    def quality_threshold(self) -> float:
        """Get the quality threshold."""
        return self._quality_threshold

    @property
    def similarity_threshold(self) -> float:
        """Get the similarity threshold for duplicate detection."""
        return self._similarity_threshold

    @property
    def auto_approve(self) -> bool:
        """Get the auto-approve setting."""
        return self._auto_approve

    # =========================================================================
    # Quality Threshold Validation
    # =========================================================================

    def should_auto_enroll(self, quality_score: float, is_unknown: bool) -> bool:
        """Check if a face detection should be auto-enrolled.

        Args:
            quality_score: Face quality score (0-1)
            is_unknown: Whether the face is currently unknown

        Returns:
            True if the face meets auto-enrollment criteria
        """
        if not is_unknown:
            # Already matched to a known person
            return False

        # Quality must meet threshold
        return quality_score >= self._quality_threshold

    # =========================================================================
    # Duplicate Detection
    # =========================================================================

    async def is_duplicate(
        self,
        session: AsyncSession,
        embedding_bytes: bytes,
    ) -> tuple[bool, int | None]:
        """Check if an embedding is a duplicate of existing known persons.

        Compares the embedding against all stored face embeddings using
        cosine similarity. Returns True if a match above the threshold
        is found.

        Args:
            session: Database session
            embedding_bytes: Serialized embedding to check

        Returns:
            Tuple of (is_duplicate, matched_person_id)
        """
        # Get all existing embeddings
        stmt = select(FaceEmbedding).options(selectinload(FaceEmbedding.person))
        result = await session.execute(stmt)
        existing_embeddings = result.scalars().all()

        if not existing_embeddings:
            return False, None

        # Deserialize the query embedding
        try:
            query_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Failed to deserialize query embedding: {e}")
            return False, None

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        best_similarity = -1.0
        best_person_id: int | None = None

        for emb in existing_embeddings:
            if emb.person is None:
                continue

            try:
                stored_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_person_id = emb.person.id

            except Exception as e:
                logger.warning(f"Failed to compare embedding {emb.id}: {e}")
                continue

        if best_similarity >= self._similarity_threshold:
            logger.debug(
                f"Duplicate detected: similarity={best_similarity:.3f} "
                f"to person_id={best_person_id}"
            )
            return True, best_person_id

        return False, None

    # =========================================================================
    # Enrollment Queue Management
    # =========================================================================

    async def add_to_queue(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> EnrollmentCandidate | None:
        """Add a face detection event to the enrollment queue.

        Creates an EnrollmentCandidate for review. First checks for
        duplicates to avoid queueing faces that are already known.

        Args:
            session: Database session
            face_event: The face detection event to queue

        Returns:
            Created EnrollmentCandidate or None if duplicate detected
        """
        # Check for duplicates first
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.info(
                f"Skipping duplicate face event {face_event.id}, "
                f"matches person_id={matched_person_id}"
            )
            return None

        # Create enrollment candidate
        candidate = EnrollmentCandidate(
            face_event_id=face_event.id,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
            status=EnrollmentStatus.PENDING.value,
        )

        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        logger.info(
            f"Added face event {face_event.id} to enrollment queue "
            f"(candidate_id={candidate.id}, quality={face_event.quality_score:.2f})"
        )

        return candidate

    async def list_pending_candidates(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EnrollmentCandidate]:
        """List pending enrollment candidates.

        Args:
            session: Database session
            limit: Maximum number of candidates to return
            offset: Number of candidates to skip

        Returns:
            List of pending EnrollmentCandidate objects
        """
        stmt = (
            select(EnrollmentCandidate)
            .where(EnrollmentCandidate.status == EnrollmentStatus.PENDING.value)
            .options(selectinload(EnrollmentCandidate.face_event))
            .order_by(EnrollmentCandidate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_candidate(
        self,
        session: AsyncSession,
        candidate_id: int,
    ) -> EnrollmentCandidate | None:
        """Get a specific enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate

        Returns:
            EnrollmentCandidate or None if not found
        """
        stmt = (
            select(EnrollmentCandidate)
            .where(EnrollmentCandidate.id == candidate_id)
            .options(selectinload(EnrollmentCandidate.face_event))
        )

        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    # =========================================================================
    # Auto-Enroll (creates new person automatically)
    # =========================================================================

    async def auto_enroll(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> KnownPerson:
        """Automatically enroll a face as a new known person.

        Creates a new KnownPerson with a generated name and adds
        the face embedding to their profile.

        Args:
            session: Database session
            face_event: The face detection event to enroll

        Returns:
            Created KnownPerson
        """
        # Generate a name for the new person
        # Count existing auto-enrolled persons for numbering
        count_stmt = select(func.count(KnownPerson.id)).where(
            KnownPerson.name.like("Unknown Person %")
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0

        person_name = f"Unknown Person {count + 1}"

        # Create the known person
        person = KnownPerson(
            name=person_name,
            is_household_member=False,  # Not trusted by default
            notes=f"Auto-enrolled from camera {face_event.camera_id} on {face_event.timestamp}",
        )
        session.add(person)

        # Create the face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=face_event.embedding,
            quality_score=face_event.quality_score,
        )
        session.add(embedding)

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Auto-enrolled person {person.id} ({person_name}) from face event {face_event.id}"
        )

        return person

    # =========================================================================
    # Process Event (main entry point)
    # =========================================================================

    async def process_event(
        self,
        session: AsyncSession,
        face_event: FaceDetectionEvent,
    ) -> dict | None:
        """Process a face detection event for potential auto-enrollment.

        This is the main entry point. It:
        1. Checks if the face meets enrollment criteria
        2. Checks for duplicates
        3. Either auto-enrolls or adds to queue based on settings

        Args:
            session: Database session
            face_event: The face detection event to process

        Returns:
            Dict with action result, or None if not eligible
        """
        # Check eligibility
        if not self.should_auto_enroll(
            quality_score=face_event.quality_score,
            is_unknown=face_event.is_unknown,
        ):
            logger.debug(
                f"Face event {face_event.id} not eligible for auto-enrollment "
                f"(quality={face_event.quality_score:.2f}, unknown={face_event.is_unknown})"
            )
            return None

        # Check for duplicates
        is_dup, matched_person_id = await self.is_duplicate(session, face_event.embedding)

        if is_dup:
            logger.debug(
                f"Face event {face_event.id} is duplicate of person_id={matched_person_id}"
            )
            return {
                "action": "duplicate",
                "person_id": matched_person_id,
            }

        # Either auto-enroll or add to queue
        if self._auto_approve:
            person = await self.auto_enroll(session, face_event)
            return {
                "action": "enrolled",
                "person_id": person.id,
                "person_name": person.name,
            }
        else:
            candidate = await self.add_to_queue(session, face_event)
            if candidate:
                return {
                    "action": "queued",
                    "candidate_id": candidate.id,
                }
            return None

    # =========================================================================
    # Approve/Reject Candidates
    # =========================================================================

    async def approve_candidate(
        self,
        session: AsyncSession,
        candidate_id: int,
        name: str | None = None,
        person_id: int | None = None,
        is_household_member: bool = False,
    ) -> dict | None:
        """Approve an enrollment candidate.

        Either creates a new KnownPerson or links to an existing one.

        Args:
            session: Database session
            candidate_id: ID of the candidate to approve
            name: Name for new person (required if person_id not provided)
            person_id: ID of existing person to link to (optional)
            is_household_member: Whether to mark as household member

        Returns:
            Dict with success status and person details, or None if not found
        """
        # Get the candidate
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return None

        if candidate.status != EnrollmentStatus.PENDING.value:
            logger.warning(f"Candidate {candidate_id} is not pending (status={candidate.status})")
            return {"success": False, "error": "Candidate is not pending"}

        # Get the face event for updating
        event_stmt = select(FaceDetectionEvent).where(
            FaceDetectionEvent.id == candidate.face_event_id
        )
        event_result = await session.execute(event_stmt)
        face_event = event_result.scalar_one_or_none()

        if face_event is None:
            logger.warning(f"Face event {candidate.face_event_id} not found")
            return {"success": False, "error": "Face event not found"}

        # Either link to existing person or create new one
        if person_id is not None:
            # Link to existing person
            person_stmt = select(KnownPerson).where(KnownPerson.id == person_id)
            person_result = await session.execute(person_stmt)
            person = person_result.scalar_one_or_none()

            if person is None:
                logger.warning(f"Person {person_id} not found")
                return {"success": False, "error": "Person not found"}
        else:
            # Create new person
            if not name:
                name = f"Person {candidate_id}"

            person = KnownPerson(
                name=name,
                is_household_member=is_household_member,
            )
            session.add(person)

        # Create face embedding
        embedding = FaceEmbedding(
            person=person,
            embedding=candidate.embedding,
            quality_score=candidate.quality_score,
        )
        session.add(embedding)

        # Update candidate status
        candidate.status = EnrollmentStatus.APPROVED.value
        candidate.enrolled_person_id = person.id if person_id else None
        candidate.reviewed_at = datetime.now(UTC)

        # Update face event to mark as matched
        face_event.matched_person_id = person.id
        face_event.is_unknown = False

        await session.commit()
        await session.refresh(person)

        logger.info(
            f"Approved candidate {candidate_id}, enrolled as person {person.id} ({person.name})"
        )

        return {
            "success": True,
            "person_id": person.id,
            "person_name": person.name,
        }

    async def reject_candidate(
        self,
        session: AsyncSession,
        candidate_id: int,
        reason: str | None = None,
    ) -> bool:
        """Reject an enrollment candidate.

        Args:
            session: Database session
            candidate_id: ID of the candidate to reject
            reason: Optional reason for rejection

        Returns:
            True if rejected, False if not found
        """
        candidate_stmt = select(EnrollmentCandidate).where(EnrollmentCandidate.id == candidate_id)
        candidate_result = await session.execute(candidate_stmt)
        candidate = candidate_result.scalar_one_or_none()

        if candidate is None:
            logger.warning(f"Enrollment candidate {candidate_id} not found")
            return False

        candidate.status = EnrollmentStatus.REJECTED.value
        candidate.rejection_reason = reason
        candidate.reviewed_at = datetime.now(UTC)

        await session.commit()

        logger.info(
            f"Rejected candidate {candidate_id}" + (f" (reason: {reason})" if reason else "")
        )

        return True


# =============================================================================
# Global Service Instance (Singleton Pattern)
# =============================================================================

_auto_enrollment_service: AutoEnrollmentService | None = None


def get_auto_enrollment_service() -> AutoEnrollmentService:
    """Get or create the global AutoEnrollmentService instance.

    Returns:
        Global AutoEnrollmentService instance
    """
    global _auto_enrollment_service  # noqa: PLW0603
    if _auto_enrollment_service is None:
        _auto_enrollment_service = AutoEnrollmentService()
    return _auto_enrollment_service


def reset_auto_enrollment_service() -> None:
    """Reset the global AutoEnrollmentService instance (for testing)."""
    global _auto_enrollment_service  # noqa: PLW0603
    _auto_enrollment_service = None
