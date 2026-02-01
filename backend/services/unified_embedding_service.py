"""Unified Embedding Service for Face and Person Re-ID Integration.

This module bridges the gap between the face recognition system (512-dim ArcFace)
and the person re-identification system (768-dim CLIP), enabling:

1. Face-to-Entity Mapping: Links detected faces to tracked entities
2. Household Member Resolution: Maps face matches to household context
3. Entity Trust Propagation: Updates entity trust status based on face recognition
4. Cross-Reference Queries: Find entities by face match or vice versa

Architecture Overview:
- Face Recognition: 512-dim ArcFace embeddings for facial identity
- Person Re-ID: 768-dim CLIP embeddings for whole-person matching
- Entity Clustering: 768-dim CLIP embeddings for canonical entity tracking

The service does NOT convert between embedding types (they serve different purposes),
but instead maintains associations that allow face recognition to inform entity
trust classification and vice versa.

Implements NEM-4942: Unify Face and Re-ID Embedding Systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.logging import get_logger
from backend.models.entity import Entity
from backend.models.enums import TrustStatus
from backend.models.face_identity import FaceDetectionEvent, KnownPerson
from backend.models.household import HouseholdMember

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


@dataclass(slots=True)
class FaceEntityAssociation:
    """Association between a face match and an entity.

    Represents the link between a detected face that matches a known person
    and an entity that has been tracked via re-identification.

    Attributes:
        face_event_id: ID of the FaceDetectionEvent
        entity_id: UUID of the associated Entity
        known_person_id: ID of the matched KnownPerson (if any)
        household_member_id: ID of the linked HouseholdMember (if any)
        face_confidence: Confidence of the face match
        association_type: How the association was established
        created_at: When the association was recorded
    """

    face_event_id: int
    entity_id: UUID
    known_person_id: int | None = None
    household_member_id: int | None = None
    face_confidence: float = 0.0
    association_type: str = "face_match"  # face_match, manual, spatial_temporal
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class UnifiedPersonContext:
    """Unified context combining face recognition and entity re-ID information.

    Provides a comprehensive view of a detected person by combining:
    - Face recognition match (KnownPerson identity)
    - Entity re-ID tracking (cross-camera appearances)
    - Household membership (trust level, schedule)

    Attributes:
        entity: The tracked Entity (if matched)
        known_person: The matched KnownPerson (if face recognized)
        household_member: The linked HouseholdMember (if any)
        face_confidence: Confidence of face match (0.0 if no face match)
        entity_similarity: Similarity score of entity match (0.0 if new entity)
        is_household: Whether person is a household member
        trust_status: Resolved trust status (from entity or household)
        cameras_seen: List of cameras where entity has been seen
        detection_count: Total number of detections for this entity
    """

    entity: Entity | None = None
    known_person: KnownPerson | None = None
    household_member: HouseholdMember | None = None
    face_confidence: float = 0.0
    entity_similarity: float = 0.0
    is_household: bool = False
    trust_status: str = TrustStatus.UNKNOWN.value
    cameras_seen: list[str] = field(default_factory=list)
    detection_count: int = 0


class UnifiedEmbeddingService:
    """Service for unifying face recognition and person re-identification.

    This service acts as a bridge between the face recognition system and the
    entity re-identification system, enabling:

    1. **Face-to-Entity Resolution**: When a face is recognized, find or create
       the corresponding entity and update its trust status.

    2. **Entity-to-Person Lookup**: Given an entity, find any associated face
       matches and household member information.

    3. **Trust Propagation**: Automatically update entity trust status when
       face recognition identifies a household member.

    4. **Unified Context Building**: Combine face recognition, entity tracking,
       and household membership into a single context object.

    Usage:
        service = UnifiedEmbeddingService()

        # Get unified context for a detection
        context = await service.get_unified_person_context(
            session=session,
            detection_id=123,
            entity_id=entity_uuid,
            face_event_id=456,
        )

        if context.is_household:
            print(f"Detected household member: {context.household_member.name}")

        # Propagate face match to entity trust
        await service.propagate_face_match_to_entity(
            session=session,
            face_event_id=456,
            entity_id=entity_uuid,
        )
    """

    def __init__(self) -> None:
        """Initialize the UnifiedEmbeddingService."""
        logger.info("UnifiedEmbeddingService initialized")

    async def get_unified_person_context(
        self,
        session: AsyncSession,
        detection_id: int | None = None,  # noqa: ARG002 - Reserved for future detection lookup
        entity_id: UUID | None = None,
        face_event_id: int | None = None,
    ) -> UnifiedPersonContext:
        """Build unified context combining face recognition and entity re-ID.

        Given any combination of detection_id, entity_id, or face_event_id,
        resolves all related information and builds a comprehensive context.

        Args:
            session: Database session
            detection_id: Optional detection ID to look up
            entity_id: Optional entity UUID to look up
            face_event_id: Optional face event ID to look up

        Returns:
            UnifiedPersonContext with all resolved information
        """
        context = UnifiedPersonContext()

        # Resolve entity if provided
        if entity_id is not None:
            entity = await self._get_entity_by_id(session, entity_id)
            if entity:
                context.entity = entity
                context.detection_count = entity.detection_count
                context.trust_status = entity.trust_status

                # Extract cameras_seen from entity_metadata
                if entity.entity_metadata and "cameras_seen" in entity.entity_metadata:
                    context.cameras_seen = entity.entity_metadata["cameras_seen"]

        # Resolve face event if provided
        if face_event_id is not None:
            face_event = await self._get_face_event_with_person(session, face_event_id)
            if face_event:
                context.face_confidence = face_event.match_confidence or 0.0

                if face_event.matched_person:
                    context.known_person = face_event.matched_person
                    context.is_household = face_event.matched_person.is_household_member

                    # Look up linked household member
                    household_member = await self._get_household_member_by_known_person(
                        session, face_event.matched_person.id
                    )
                    if household_member:
                        context.household_member = household_member
                        context.is_household = True

                        # Upgrade trust status based on household membership
                        if household_member.trusted_level.value == "full":
                            context.trust_status = TrustStatus.TRUSTED.value

        return context

    async def propagate_face_match_to_entity(
        self,
        session: AsyncSession,
        face_event_id: int,
        entity_id: UUID,
        update_trust: bool = True,
    ) -> FaceEntityAssociation | None:
        """Propagate face recognition match to entity trust status.

        When a face is recognized and matched to a known person who is a
        household member, this method updates the corresponding entity's
        trust status to reflect the identification.

        Args:
            session: Database session
            face_event_id: ID of the face detection event with a match
            entity_id: UUID of the entity to update
            update_trust: Whether to update entity trust status (default: True)

        Returns:
            FaceEntityAssociation if successful, None if face event not found
            or not matched to a known person
        """
        # Get the face event with matched person
        face_event = await self._get_face_event_with_person(session, face_event_id)
        if face_event is None or face_event.matched_person is None:
            logger.debug(
                "Cannot propagate face match: event %d not found or not matched",
                face_event_id,
            )
            return None

        known_person = face_event.matched_person
        known_person_id = known_person.id
        household_member_id: int | None = None

        # Look up linked household member
        household_member = await self._get_household_member_by_known_person(
            session, known_person_id
        )
        if household_member:
            household_member_id = household_member.id

        # Create association record
        association = FaceEntityAssociation(
            face_event_id=face_event_id,
            entity_id=entity_id,
            known_person_id=known_person_id,
            household_member_id=household_member_id,
            face_confidence=face_event.match_confidence or 0.0,
            association_type="face_match",
        )

        # Update entity trust status if requested and person is household member
        if update_trust and known_person.is_household_member:
            entity = await self._get_entity_by_id(session, entity_id)
            if entity:
                # Determine trust level from household member or default to trusted
                if household_member:
                    trust_level = household_member.trusted_level.value
                    if trust_level == "full":
                        entity.trust_status = TrustStatus.TRUSTED.value
                    elif trust_level == "monitor":
                        entity.trust_status = TrustStatus.UNKNOWN.value
                    # "partial" keeps current status
                else:
                    # Known person is household member but no HouseholdMember record
                    entity.trust_status = TrustStatus.TRUSTED.value

                # Add face match info to entity metadata
                if entity.entity_metadata is None:
                    entity.entity_metadata = {}
                entity.entity_metadata["face_match"] = {
                    "known_person_id": known_person_id,
                    "known_person_name": known_person.name,
                    "face_confidence": association.face_confidence,
                    "matched_at": association.created_at.isoformat(),
                }

                await session.flush()

                logger.info(
                    "Updated entity %s trust to %s based on face match to %s",
                    entity_id,
                    entity.trust_status,
                    known_person.name,
                )

        return association

    async def find_entity_by_face_match(
        self,
        session: AsyncSession,
        known_person_id: int,
        camera_id: str | None = None,
        since_hours: int = 24,  # noqa: ARG002 - Reserved for future time filtering
    ) -> list[Entity]:
        """Find entities that have been face-matched to a known person.

        Searches for entities that have face_match metadata containing
        the specified known_person_id.

        Args:
            session: Database session
            known_person_id: ID of the known person to search for
            camera_id: Optional camera ID to filter by
            since_hours: Look back window in hours (default: 24)

        Returns:
            List of Entity objects that have face-matched to this person
        """
        # Query entities with face_match metadata containing known_person_id
        stmt = select(Entity).where(
            Entity.entity_metadata.op("@>")({"face_match": {"known_person_id": known_person_id}})
        )

        if camera_id:
            stmt = stmt.where(Entity.entity_metadata.op("@>")({"camera_id": camera_id}))

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_person_sighting_history(
        self,
        session: AsyncSession,
        known_person_id: int,
        include_entities: bool = True,
        include_face_events: bool = True,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get combined sighting history for a known person.

        Combines face detection events and entity tracking data to provide
        a unified view of when and where a person has been seen.

        Args:
            session: Database session
            known_person_id: ID of the known person
            include_entities: Include entity sightings (default: True)
            include_face_events: Include face detection events (default: True)
            limit: Maximum number of sightings to return

        Returns:
            Dict containing:
            - known_person: KnownPerson details
            - household_member: HouseholdMember details (if linked)
            - face_events: List of face detection events
            - entities: List of entities matched to this person
            - total_sightings: Combined count
        """
        result: dict[str, Any] = {
            "known_person": None,
            "household_member": None,
            "face_events": [],
            "entities": [],
            "total_sightings": 0,
        }

        # Get the known person
        stmt = select(KnownPerson).where(KnownPerson.id == known_person_id)
        person_result = await session.execute(stmt)
        known_person = person_result.scalar_one_or_none()

        if known_person is None:
            return result

        result["known_person"] = {
            "id": known_person.id,
            "name": known_person.name,
            "is_household_member": known_person.is_household_member,
            "notes": known_person.notes,
        }

        # Get linked household member
        household_member = await self._get_household_member_by_known_person(
            session, known_person_id
        )
        if household_member:
            result["household_member"] = {
                "id": household_member.id,
                "name": household_member.name,
                "role": household_member.role.value,
                "trust_level": household_member.trusted_level.value,
            }

        # Get face detection events
        if include_face_events:
            face_stmt = (
                select(FaceDetectionEvent)
                .where(FaceDetectionEvent.matched_person_id == known_person_id)
                .order_by(FaceDetectionEvent.timestamp.desc())
                .limit(limit)
            )
            face_result = await session.execute(face_stmt)
            face_events = face_result.scalars().all()

            result["face_events"] = [
                {
                    "id": fe.id,
                    "camera_id": fe.camera_id,
                    "timestamp": fe.timestamp.isoformat(),
                    "confidence": fe.match_confidence,
                    "quality_score": fe.quality_score,
                }
                for fe in face_events
            ]

        # Get associated entities
        if include_entities:
            entities = await self.find_entity_by_face_match(session, known_person_id)
            result["entities"] = [
                {
                    "id": str(e.id),
                    "entity_type": e.entity_type,
                    "trust_status": e.trust_status,
                    "first_seen_at": e.first_seen_at.isoformat() if e.first_seen_at else None,
                    "last_seen_at": e.last_seen_at.isoformat() if e.last_seen_at else None,
                    "detection_count": e.detection_count,
                }
                for e in entities
            ]

        result["total_sightings"] = len(result["face_events"]) + sum(
            e["detection_count"] for e in result["entities"]
        )

        return result

    async def link_face_event_to_entity(
        self,
        session: AsyncSession,
        face_event_id: int,
        entity_id: UUID,
        association_type: str = "manual",
    ) -> FaceEntityAssociation | None:
        """Manually link a face detection event to an entity.

        Used when automatic association isn't possible (e.g., face detected
        but entity was tracked via different camera with only re-ID matching).

        Args:
            session: Database session
            face_event_id: ID of the face detection event
            entity_id: UUID of the entity to link
            association_type: Type of association (manual, spatial_temporal)

        Returns:
            FaceEntityAssociation if successful, None if face event not found
        """
        # Verify face event exists
        face_event = await self._get_face_event_with_person(session, face_event_id)
        if face_event is None:
            return None

        # Verify entity exists
        entity = await self._get_entity_by_id(session, entity_id)
        if entity is None:
            return None

        known_person_id = face_event.matched_person_id
        household_member_id: int | None = None

        if known_person_id:
            household_member = await self._get_household_member_by_known_person(
                session, known_person_id
            )
            if household_member:
                household_member_id = household_member.id

        association = FaceEntityAssociation(
            face_event_id=face_event_id,
            entity_id=entity_id,
            known_person_id=known_person_id,
            household_member_id=household_member_id,
            face_confidence=face_event.match_confidence or 0.0,
            association_type=association_type,
        )

        # Store association in entity metadata
        if entity.entity_metadata is None:
            entity.entity_metadata = {}

        face_associations = entity.entity_metadata.get("face_associations", [])
        face_associations.append(
            {
                "face_event_id": face_event_id,
                "known_person_id": known_person_id,
                "confidence": association.face_confidence,
                "type": association_type,
                "linked_at": association.created_at.isoformat(),
            }
        )
        entity.entity_metadata["face_associations"] = face_associations

        await session.flush()

        logger.info(
            "Linked face event %d to entity %s (type=%s)",
            face_event_id,
            entity_id,
            association_type,
        )

        return association

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    async def _get_entity_by_id(
        self,
        session: AsyncSession,
        entity_id: UUID,
    ) -> Entity | None:
        """Get an entity by ID with metadata."""
        stmt = select(Entity).where(Entity.id == entity_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_face_event_with_person(
        self,
        session: AsyncSession,
        face_event_id: int,
    ) -> FaceDetectionEvent | None:
        """Get a face event with matched_person eagerly loaded."""
        stmt = (
            select(FaceDetectionEvent)
            .options(selectinload(FaceDetectionEvent.matched_person))
            .where(FaceDetectionEvent.id == face_event_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_household_member_by_known_person(
        self,
        session: AsyncSession,
        known_person_id: int,
    ) -> HouseholdMember | None:
        """Find household member linked to a known person."""
        stmt = select(HouseholdMember).where(HouseholdMember.known_person_id == known_person_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


# =============================================================================
# Global Service Instance (Singleton Pattern)
# =============================================================================

_unified_embedding_service: UnifiedEmbeddingService | None = None


def get_unified_embedding_service() -> UnifiedEmbeddingService:
    """Get or create the global UnifiedEmbeddingService instance.

    Returns:
        Global UnifiedEmbeddingService instance
    """
    global _unified_embedding_service  # noqa: PLW0603
    if _unified_embedding_service is None:
        _unified_embedding_service = UnifiedEmbeddingService()
    return _unified_embedding_service


def reset_unified_embedding_service() -> None:
    """Reset the global UnifiedEmbeddingService instance (for testing)."""
    global _unified_embedding_service  # noqa: PLW0603
    _unified_embedding_service = None
