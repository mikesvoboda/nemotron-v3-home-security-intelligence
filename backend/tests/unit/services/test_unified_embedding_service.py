"""Unit tests for UnifiedEmbeddingService.

Tests the integration layer between face recognition (512-dim ArcFace)
and person re-identification (768-dim CLIP) systems.

Implements NEM-4942: Unify Face and Re-ID Embedding Systems.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.entity import Entity
from backend.models.enums import TrustStatus
from backend.models.face_identity import FaceDetectionEvent, KnownPerson
from backend.models.household import HouseholdMember, MemberRole, TrustLevel
from backend.services.unified_embedding_service import (
    FaceEntityAssociation,
    UnifiedEmbeddingService,
    UnifiedPersonContext,
    get_unified_embedding_service,
    reset_unified_embedding_service,
)


class TestFaceEntityAssociation:
    """Tests for FaceEntityAssociation dataclass."""

    def test_default_values(self) -> None:
        """Test FaceEntityAssociation default values."""
        entity_id = uuid.uuid7()
        assoc = FaceEntityAssociation(
            face_event_id=1,
            entity_id=entity_id,
        )

        assert assoc.face_event_id == 1
        assert assoc.entity_id == entity_id
        assert assoc.known_person_id is None
        assert assoc.household_member_id is None
        assert assoc.face_confidence == 0.0
        assert assoc.association_type == "face_match"
        assert assoc.created_at is not None

    def test_full_values(self) -> None:
        """Test FaceEntityAssociation with all values provided."""
        entity_id = uuid.uuid7()
        created_at = datetime.now(UTC)

        assoc = FaceEntityAssociation(
            face_event_id=1,
            entity_id=entity_id,
            known_person_id=10,
            household_member_id=5,
            face_confidence=0.95,
            association_type="manual",
            created_at=created_at,
        )

        assert assoc.face_event_id == 1
        assert assoc.entity_id == entity_id
        assert assoc.known_person_id == 10
        assert assoc.household_member_id == 5
        assert assoc.face_confidence == 0.95
        assert assoc.association_type == "manual"
        assert assoc.created_at == created_at


class TestUnifiedPersonContext:
    """Tests for UnifiedPersonContext dataclass."""

    def test_default_values(self) -> None:
        """Test UnifiedPersonContext default values."""
        context = UnifiedPersonContext()

        assert context.entity is None
        assert context.known_person is None
        assert context.household_member is None
        assert context.face_confidence == 0.0
        assert context.entity_similarity == 0.0
        assert context.is_household is False
        assert context.trust_status == TrustStatus.UNKNOWN.value
        assert context.cameras_seen == []
        assert context.detection_count == 0


class TestUnifiedEmbeddingServiceInit:
    """Tests for UnifiedEmbeddingService initialization."""

    def test_init(self) -> None:
        """Test service initialization."""
        service = UnifiedEmbeddingService()
        assert service is not None


class TestGetUnifiedPersonContext:
    """Tests for get_unified_person_context method."""

    @pytest.fixture
    def service(self) -> UnifiedEmbeddingService:
        """Create service instance."""
        return UnifiedEmbeddingService()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_empty_context_no_ids(
        self,
        service: UnifiedEmbeddingService,
        mock_session: AsyncMock,
    ) -> None:
        """Test get_unified_person_context with no IDs returns empty context."""
        context = await service.get_unified_person_context(session=mock_session)

        assert context.entity is None
        assert context.known_person is None
        assert context.household_member is None
        assert context.face_confidence == 0.0
        assert context.is_household is False

    @pytest.mark.asyncio
    async def test_context_with_entity_id(
        self,
        service: UnifiedEmbeddingService,
        mock_session: AsyncMock,
    ) -> None:
        """Test get_unified_person_context with entity_id."""
        entity_id = uuid.uuid7()
        entity = MagicMock(spec=Entity)
        entity.id = entity_id
        entity.detection_count = 5
        entity.trust_status = TrustStatus.TRUSTED.value
        entity.entity_metadata = {"cameras_seen": ["front_door", "driveway"]}

        # Mock the execute result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = entity
        mock_session.execute = AsyncMock(return_value=mock_result)

        context = await service.get_unified_person_context(
            session=mock_session,
            entity_id=entity_id,
        )

        assert context.entity == entity
        assert context.detection_count == 5
        assert context.trust_status == TrustStatus.TRUSTED.value
        assert context.cameras_seen == ["front_door", "driveway"]

    @pytest.mark.asyncio
    async def test_context_with_face_event_matched_person(
        self,
        service: UnifiedEmbeddingService,
        mock_session: AsyncMock,
    ) -> None:
        """Test get_unified_person_context with face_event that has matched person."""
        # Create mock known person
        known_person = MagicMock(spec=KnownPerson)
        known_person.id = 10
        known_person.name = "John Doe"
        known_person.is_household_member = True

        # Create mock face event
        face_event = MagicMock(spec=FaceDetectionEvent)
        face_event.id = 1
        face_event.match_confidence = 0.92
        face_event.matched_person = known_person

        # Mock execute to return face event for first call, None for household member
        mock_result_face = MagicMock()
        mock_result_face.scalar_one_or_none.return_value = face_event

        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(side_effect=[mock_result_face, mock_result_member])

        context = await service.get_unified_person_context(
            session=mock_session,
            face_event_id=1,
        )

        assert context.known_person == known_person
        assert context.face_confidence == 0.92
        assert context.is_household is True

    @pytest.mark.asyncio
    async def test_context_with_household_member_linked(
        self,
        service: UnifiedEmbeddingService,
        mock_session: AsyncMock,
    ) -> None:
        """Test context when face is matched to household member."""
        # Create mock known person
        known_person = MagicMock(spec=KnownPerson)
        known_person.id = 10
        known_person.name = "John Doe"
        known_person.is_household_member = True

        # Create mock household member
        household_member = MagicMock(spec=HouseholdMember)
        household_member.id = 5
        household_member.name = "John Doe"
        household_member.trusted_level = TrustLevel.FULL

        # Create mock face event
        face_event = MagicMock(spec=FaceDetectionEvent)
        face_event.id = 1
        face_event.match_confidence = 0.95
        face_event.matched_person = known_person

        # Mock execute calls
        mock_result_face = MagicMock()
        mock_result_face.scalar_one_or_none.return_value = face_event

        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = household_member

        mock_session.execute = AsyncMock(side_effect=[mock_result_face, mock_result_member])

        context = await service.get_unified_person_context(
            session=mock_session,
            face_event_id=1,
        )

        assert context.known_person == known_person
        assert context.household_member == household_member
        assert context.is_household is True
        assert context.trust_status == TrustStatus.TRUSTED.value


class TestPropagateFaceMatchToEntity:
    """Tests for propagate_face_match_to_entity method."""

    @pytest.fixture
    def service(self) -> UnifiedEmbeddingService:
        """Create service instance."""
        return UnifiedEmbeddingService()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock database session."""
        session = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_face_event(
        self,
        service: UnifiedEmbeddingService,
        mock_session: AsyncMock,
    ) -> None:
        """Test returns None when face event not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service.propagate_face_match_to_entity(
            session=mock_session,
            face_event_id=999,
            entity_id=uuid.uuid7(),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_unmatched_face_event(
        self,
        service: UnifiedEmbeddingService,
        mock_session: AsyncMock,
    ) -> None:
        """Test returns None when face event has no matched person."""
        face_event = MagicMock(spec=FaceDetectionEvent)
        face_event.matched_person = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = face_event
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service.propagate_face_match_to_entity(
            session=mock_session,
            face_event_id=1,
            entity_id=uuid.uuid7(),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_creates_association_and_updates_entity_trust(
        self,
        service: UnifiedEmbeddingService,
        mock_session: AsyncMock,
    ) -> None:
        """Test creates association and updates entity trust for household member."""
        entity_id = uuid.uuid7()

        # Create mock known person (household member)
        known_person = MagicMock(spec=KnownPerson)
        known_person.id = 10
        known_person.name = "John Doe"
        known_person.is_household_member = True

        # Create mock face event
        face_event = MagicMock(spec=FaceDetectionEvent)
        face_event.id = 1
        face_event.match_confidence = 0.95
        face_event.matched_person = known_person
        face_event.matched_person_id = 10

        # Create mock entity
        entity = MagicMock(spec=Entity)
        entity.id = entity_id
        entity.entity_metadata = {}
        entity.trust_status = TrustStatus.UNKNOWN.value

        # Create mock household member with full trust
        household_member = MagicMock(spec=HouseholdMember)
        household_member.id = 5
        household_member.trusted_level = TrustLevel.FULL

        # Mock execute calls: face event, household member, entity
        mock_result_face = MagicMock()
        mock_result_face.scalar_one_or_none.return_value = face_event

        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = household_member

        mock_result_entity = MagicMock()
        mock_result_entity.scalar_one_or_none.return_value = entity

        mock_session.execute = AsyncMock(
            side_effect=[mock_result_face, mock_result_member, mock_result_entity]
        )

        result = await service.propagate_face_match_to_entity(
            session=mock_session,
            face_event_id=1,
            entity_id=entity_id,
        )

        assert result is not None
        assert result.face_event_id == 1
        assert result.entity_id == entity_id
        assert result.known_person_id == 10
        assert result.household_member_id == 5
        assert result.face_confidence == 0.95
        assert entity.trust_status == TrustStatus.TRUSTED.value
        assert "face_match" in entity.entity_metadata


class TestFindEntityByFaceMatch:
    """Tests for find_entity_by_face_match method."""

    @pytest.fixture
    def service(self) -> UnifiedEmbeddingService:
        """Create service instance."""
        return UnifiedEmbeddingService()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_finds_entities_with_face_match(
        self,
        service: UnifiedEmbeddingService,
        mock_session: AsyncMock,
    ) -> None:
        """Test finds entities that have been face-matched to a known person."""
        entity1 = MagicMock(spec=Entity)
        entity1.id = uuid.uuid7()
        entity2 = MagicMock(spec=Entity)
        entity2.id = uuid.uuid7()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [entity1, entity2]
        mock_session.execute = AsyncMock(return_value=mock_result)

        entities = await service.find_entity_by_face_match(
            session=mock_session,
            known_person_id=10,
        )

        assert len(entities) == 2
        assert entity1 in entities
        assert entity2 in entities

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_matches(
        self,
        service: UnifiedEmbeddingService,
        mock_session: AsyncMock,
    ) -> None:
        """Test returns empty list when no entities match."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        entities = await service.find_entity_by_face_match(
            session=mock_session,
            known_person_id=999,
        )

        assert len(entities) == 0


class TestGetPersonSightingHistory:
    """Tests for get_person_sighting_history method."""

    @pytest.fixture
    def service(self) -> UnifiedEmbeddingService:
        """Create service instance."""
        return UnifiedEmbeddingService()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_returns_empty_result_for_unknown_person(
        self,
        service: UnifiedEmbeddingService,
        mock_session: AsyncMock,
    ) -> None:
        """Test returns empty result when known person not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service.get_person_sighting_history(
            session=mock_session,
            known_person_id=999,
        )

        assert result["known_person"] is None
        assert result["face_events"] == []
        assert result["entities"] == []
        assert result["total_sightings"] == 0

    @pytest.mark.asyncio
    async def test_returns_full_history(
        self,
        service: UnifiedEmbeddingService,
        mock_session: AsyncMock,
    ) -> None:
        """Test returns full sighting history for known person."""
        # Create mock known person
        known_person = MagicMock(spec=KnownPerson)
        known_person.id = 10
        known_person.name = "John Doe"
        known_person.is_household_member = True
        known_person.notes = "Test person"

        # Create mock household member
        household_member = MagicMock(spec=HouseholdMember)
        household_member.id = 5
        household_member.name = "John Doe"
        household_member.role = MemberRole.RESIDENT
        household_member.trusted_level = TrustLevel.FULL

        # Create mock face event
        face_event = MagicMock(spec=FaceDetectionEvent)
        face_event.id = 1
        face_event.camera_id = "front_door"
        face_event.timestamp = datetime.now(UTC)
        face_event.match_confidence = 0.95
        face_event.quality_score = 0.8

        # Create mock entity
        entity = MagicMock(spec=Entity)
        entity.id = uuid.uuid7()
        entity.entity_type = "person"
        entity.trust_status = TrustStatus.TRUSTED.value
        entity.first_seen_at = datetime.now(UTC)
        entity.last_seen_at = datetime.now(UTC)
        entity.detection_count = 5

        # Mock execute calls in order:
        # 1. Known person lookup
        # 2. Household member lookup
        # 3. Face events query
        # 4. Entities query (via find_entity_by_face_match)
        mock_result_person = MagicMock()
        mock_result_person.scalar_one_or_none.return_value = known_person

        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = household_member

        mock_result_faces = MagicMock()
        mock_result_faces.scalars.return_value.all.return_value = [face_event]

        mock_result_entities = MagicMock()
        mock_result_entities.scalars.return_value.all.return_value = [entity]

        mock_session.execute = AsyncMock(
            side_effect=[
                mock_result_person,
                mock_result_member,
                mock_result_faces,
                mock_result_entities,
            ]
        )

        result = await service.get_person_sighting_history(
            session=mock_session,
            known_person_id=10,
        )

        assert result["known_person"]["id"] == 10
        assert result["known_person"]["name"] == "John Doe"
        assert result["household_member"]["id"] == 5
        assert result["household_member"]["trust_level"] == "full"
        assert len(result["face_events"]) == 1
        assert len(result["entities"]) == 1
        assert result["total_sightings"] == 6  # 1 face event + 5 detection count


class TestLinkFaceEventToEntity:
    """Tests for link_face_event_to_entity method."""

    @pytest.fixture
    def service(self) -> UnifiedEmbeddingService:
        """Create service instance."""
        return UnifiedEmbeddingService()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock database session."""
        session = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_face_event(
        self,
        service: UnifiedEmbeddingService,
        mock_session: AsyncMock,
    ) -> None:
        """Test returns None when face event not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service.link_face_event_to_entity(
            session=mock_session,
            face_event_id=999,
            entity_id=uuid.uuid7(),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_entity(
        self,
        service: UnifiedEmbeddingService,
        mock_session: AsyncMock,
    ) -> None:
        """Test returns None when entity not found."""
        face_event = MagicMock(spec=FaceDetectionEvent)
        face_event.id = 1

        mock_result_face = MagicMock()
        mock_result_face.scalar_one_or_none.return_value = face_event

        mock_result_entity = MagicMock()
        mock_result_entity.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(side_effect=[mock_result_face, mock_result_entity])

        result = await service.link_face_event_to_entity(
            session=mock_session,
            face_event_id=1,
            entity_id=uuid.uuid7(),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_creates_association_and_stores_in_metadata(
        self,
        service: UnifiedEmbeddingService,
        mock_session: AsyncMock,
    ) -> None:
        """Test creates association and stores in entity metadata."""
        entity_id = uuid.uuid7()

        # Create mock face event (no matched person)
        face_event = MagicMock(spec=FaceDetectionEvent)
        face_event.id = 1
        face_event.match_confidence = 0.0
        face_event.matched_person_id = None

        # Create mock entity
        entity = MagicMock(spec=Entity)
        entity.id = entity_id
        entity.entity_metadata = {}

        mock_result_face = MagicMock()
        mock_result_face.scalar_one_or_none.return_value = face_event

        mock_result_entity = MagicMock()
        mock_result_entity.scalar_one_or_none.return_value = entity

        mock_session.execute = AsyncMock(side_effect=[mock_result_face, mock_result_entity])

        result = await service.link_face_event_to_entity(
            session=mock_session,
            face_event_id=1,
            entity_id=entity_id,
            association_type="spatial_temporal",
        )

        assert result is not None
        assert result.face_event_id == 1
        assert result.entity_id == entity_id
        assert result.association_type == "spatial_temporal"
        assert "face_associations" in entity.entity_metadata
        assert len(entity.entity_metadata["face_associations"]) == 1


class TestGlobalServiceManagement:
    """Tests for global service instance management."""

    def setup_method(self) -> None:
        """Reset global service before each test."""
        reset_unified_embedding_service()

    def teardown_method(self) -> None:
        """Reset global service after each test."""
        reset_unified_embedding_service()

    def test_get_unified_embedding_service_creates_instance(self) -> None:
        """Test get_unified_embedding_service creates singleton instance."""
        service1 = get_unified_embedding_service()
        service2 = get_unified_embedding_service()

        assert service1 is not None
        assert service1 is service2  # Same instance

    def test_reset_unified_embedding_service(self) -> None:
        """Test reset_unified_embedding_service clears singleton."""
        service1 = get_unified_embedding_service()
        reset_unified_embedding_service()
        service2 = get_unified_embedding_service()

        assert service1 is not service2  # New instance after reset
