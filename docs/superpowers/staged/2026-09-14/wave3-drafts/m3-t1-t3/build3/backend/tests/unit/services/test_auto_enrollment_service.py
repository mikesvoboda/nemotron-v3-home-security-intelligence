"""Unit tests for face auto-enrollment service.

Tests the auto-enrollment functionality for high-confidence face detections:
- Quality threshold validation
- Duplicate detection prevention
- Enrollment queue management
- Automatic vs manual enrollment modes

Implements NEM-4941: Face Auto-Enrollment from High-Confidence Detections
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from backend.models.face_identity import (
    EnrollmentCandidate,
    EnrollmentStatus,
    FaceDetectionEvent,
    FaceEmbedding,
    KnownPerson,
)
from backend.services.auto_enrollment_service import (
    AutoEnrollmentService,
    get_auto_enrollment_service,
    reset_auto_enrollment_service,
)


class TestAutoEnrollmentService:
    """Tests for AutoEnrollmentService."""

    @pytest.fixture
    def service(self) -> AutoEnrollmentService:
        """Create an AutoEnrollmentService instance with test thresholds."""
        return AutoEnrollmentService(
            confidence_threshold=0.95,
            quality_threshold=0.8,
            similarity_threshold=0.85,
            auto_approve=False,  # Default to queue mode
        )

    @pytest.fixture
    def service_auto_approve(self) -> AutoEnrollmentService:
        """Create an AutoEnrollmentService instance with auto-approve enabled."""
        return AutoEnrollmentService(
            confidence_threshold=0.95,
            quality_threshold=0.8,
            similarity_threshold=0.85,
            auto_approve=True,
        )

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def high_quality_event(self) -> MagicMock:
        """Create a mock high-quality face detection event."""
        event = MagicMock(spec=FaceDetectionEvent)
        event.id = 1
        event.camera_id = "front_door"
        event.timestamp = datetime.now(UTC)
        event.quality_score = 0.92
        event.is_unknown = True
        event.matched_person_id = None
        # Create a normalized embedding
        embedding = np.random.rand(512).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        event.embedding = embedding.tobytes()
        return event

    @pytest.fixture
    def low_quality_event(self) -> MagicMock:
        """Create a mock low-quality face detection event."""
        event = MagicMock(spec=FaceDetectionEvent)
        event.id = 2
        event.camera_id = "front_door"
        event.timestamp = datetime.now(UTC)
        event.quality_score = 0.5  # Below threshold
        event.is_unknown = True
        event.matched_person_id = None
        embedding = np.random.rand(512).astype(np.float32)
        event.embedding = embedding.tobytes()
        return event

    # =========================================================================
    # Test: Quality Threshold Validation
    # =========================================================================

    @pytest.mark.asyncio
    async def test_should_auto_enroll_returns_true_for_high_quality(
        self, service: AutoEnrollmentService, high_quality_event: MagicMock
    ) -> None:
        """High quality unknown faces should be candidates for auto-enrollment."""
        result = service.should_auto_enroll(
            quality_score=high_quality_event.quality_score,
            is_unknown=high_quality_event.is_unknown,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_should_auto_enroll_returns_false_for_low_quality(
        self, service: AutoEnrollmentService, low_quality_event: MagicMock
    ) -> None:
        """Low quality faces should not be auto-enrolled."""
        result = service.should_auto_enroll(
            quality_score=low_quality_event.quality_score,
            is_unknown=low_quality_event.is_unknown,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_should_auto_enroll_returns_false_for_known_faces(
        self, service: AutoEnrollmentService
    ) -> None:
        """Already matched faces should not be auto-enrolled."""
        result = service.should_auto_enroll(
            quality_score=0.95,  # High quality
            is_unknown=False,  # Already matched
        )
        assert result is False

    # =========================================================================
    # Test: Duplicate Detection
    # =========================================================================

    @pytest.mark.asyncio
    async def test_is_duplicate_returns_true_for_similar_embedding(
        self, service: AutoEnrollmentService, mock_session: AsyncMock
    ) -> None:
        """Should detect duplicate when similar embedding exists."""
        # Create a reference embedding
        ref_embedding = np.random.rand(512).astype(np.float32)
        ref_embedding = ref_embedding / np.linalg.norm(ref_embedding)

        # Create a very similar embedding (above similarity threshold)
        similar_embedding = ref_embedding + np.random.rand(512).astype(np.float32) * 0.01
        similar_embedding = similar_embedding / np.linalg.norm(similar_embedding)

        # Mock existing embeddings in database
        mock_existing = MagicMock(spec=FaceEmbedding)
        mock_existing.embedding = ref_embedding.tobytes()
        mock_existing.person = MagicMock(spec=KnownPerson)
        mock_existing.person.id = 1
        mock_existing.person.name = "Existing Person"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_existing]
        mock_session.execute = AsyncMock(return_value=mock_result)

        is_dup, matched_person_id = await service.is_duplicate(
            mock_session, similar_embedding.tobytes()
        )

        assert is_dup is True
        assert matched_person_id == 1

    @pytest.mark.asyncio
    async def test_is_duplicate_returns_false_for_different_embedding(
        self, service: AutoEnrollmentService, mock_session: AsyncMock
    ) -> None:
        """Should not detect duplicate for very different embedding."""
        # Create two very different embeddings
        embedding1 = np.random.rand(512).astype(np.float32)
        embedding1 = embedding1 / np.linalg.norm(embedding1)

        embedding2 = np.random.rand(512).astype(np.float32)
        embedding2 = embedding2 / np.linalg.norm(embedding2)

        # Mock existing embeddings
        mock_existing = MagicMock(spec=FaceEmbedding)
        mock_existing.embedding = embedding2.tobytes()
        mock_existing.person = MagicMock(spec=KnownPerson)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_existing]
        mock_session.execute = AsyncMock(return_value=mock_result)

        is_dup, matched_person_id = await service.is_duplicate(mock_session, embedding1.tobytes())

        assert is_dup is False
        assert matched_person_id is None

    @pytest.mark.asyncio
    async def test_is_duplicate_returns_false_when_no_existing_embeddings(
        self, service: AutoEnrollmentService, mock_session: AsyncMock
    ) -> None:
        """Should return False when no embeddings exist in database."""
        embedding = np.random.rand(512).astype(np.float32)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        is_dup, matched_person_id = await service.is_duplicate(mock_session, embedding.tobytes())

        assert is_dup is False
        assert matched_person_id is None

    # =========================================================================
    # Test: Enrollment Queue Management
    # =========================================================================

    @pytest.mark.asyncio
    async def test_add_to_queue_creates_enrollment_candidate(
        self,
        service: AutoEnrollmentService,
        mock_session: AsyncMock,
        high_quality_event: MagicMock,
    ) -> None:
        """Should create EnrollmentCandidate when adding to queue."""
        # Mock no duplicate found
        with patch.object(service, "is_duplicate", new_callable=AsyncMock) as mock_is_dup:
            mock_is_dup.return_value = (False, None)

            # Mock session.add and commit
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            mock_session.refresh = AsyncMock()

            candidate = await service.add_to_queue(mock_session, high_quality_event)

            assert candidate is not None
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_to_queue_skips_duplicate(
        self,
        service: AutoEnrollmentService,
        mock_session: AsyncMock,
        high_quality_event: MagicMock,
    ) -> None:
        """Should not create candidate when duplicate detected."""
        # Mock duplicate found
        with patch.object(service, "is_duplicate", new_callable=AsyncMock) as mock_is_dup:
            mock_is_dup.return_value = (True, 1)

            candidate = await service.add_to_queue(mock_session, high_quality_event)

            assert candidate is None
            mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_pending_candidates_returns_pending_only(
        self, service: AutoEnrollmentService, mock_session: AsyncMock
    ) -> None:
        """Should only return candidates with pending status."""
        # Create mock candidates
        pending_candidate = MagicMock(spec=EnrollmentCandidate)
        pending_candidate.status = EnrollmentStatus.PENDING
        pending_candidate.created_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pending_candidate]
        mock_session.execute = AsyncMock(return_value=mock_result)

        candidates = await service.list_pending_candidates(mock_session)

        assert len(candidates) == 1
        assert candidates[0].status == EnrollmentStatus.PENDING

    # =========================================================================
    # Test: Auto-Approve Mode
    # =========================================================================

    @pytest.mark.asyncio
    async def test_process_event_auto_enrolls_when_auto_approve_enabled(
        self,
        service_auto_approve: AutoEnrollmentService,
        mock_session: AsyncMock,
        high_quality_event: MagicMock,
    ) -> None:
        """Should auto-enroll immediately when auto_approve is True."""
        # Mock no duplicate
        with patch.object(
            service_auto_approve, "is_duplicate", new_callable=AsyncMock
        ) as mock_is_dup:
            mock_is_dup.return_value = (False, None)

            # Mock auto_enroll
            with patch.object(
                service_auto_approve, "auto_enroll", new_callable=AsyncMock
            ) as mock_auto_enroll:
                mock_person = MagicMock(spec=KnownPerson)
                mock_person.id = 1
                mock_person.name = "Auto Person 1"
                mock_auto_enroll.return_value = mock_person

                result = await service_auto_approve.process_event(mock_session, high_quality_event)

                assert result is not None
                assert result["action"] == "enrolled"
                assert result["person_id"] == 1
                mock_auto_enroll.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_event_adds_to_queue_when_auto_approve_disabled(
        self,
        service: AutoEnrollmentService,
        mock_session: AsyncMock,
        high_quality_event: MagicMock,
    ) -> None:
        """Should add to queue when auto_approve is False."""
        # Mock no duplicate
        with patch.object(service, "is_duplicate", new_callable=AsyncMock) as mock_is_dup:
            mock_is_dup.return_value = (False, None)

            # Mock add_to_queue
            with patch.object(service, "add_to_queue", new_callable=AsyncMock) as mock_add_queue:
                mock_candidate = MagicMock(spec=EnrollmentCandidate)
                mock_candidate.id = 1
                mock_add_queue.return_value = mock_candidate

                result = await service.process_event(mock_session, high_quality_event)

                assert result is not None
                assert result["action"] == "queued"
                assert result["candidate_id"] == 1
                mock_add_queue.assert_called_once()

    # =========================================================================
    # Test: Approve/Reject Candidates
    # =========================================================================

    @pytest.mark.asyncio
    async def test_approve_candidate_creates_person_and_embedding(
        self, service: AutoEnrollmentService, mock_session: AsyncMock
    ) -> None:
        """Approving a candidate should create KnownPerson and FaceEmbedding."""
        # Create mock candidate
        embedding = np.random.rand(512).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)

        mock_candidate = MagicMock(spec=EnrollmentCandidate)
        mock_candidate.id = 1
        mock_candidate.face_event_id = 100
        mock_candidate.embedding = embedding.tobytes()
        mock_candidate.quality_score = 0.92
        mock_candidate.status = EnrollmentStatus.PENDING

        # Mock face event
        mock_event = MagicMock(spec=FaceDetectionEvent)
        mock_event.id = 100
        mock_event.camera_id = "front_door"
        mock_event.timestamp = datetime.now(UTC)

        # Mock get candidate query
        mock_candidate_result = MagicMock()
        mock_candidate_result.scalar_one_or_none.return_value = mock_candidate

        # Mock get event query
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_session.execute = AsyncMock(side_effect=[mock_candidate_result, mock_event_result])
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await service.approve_candidate(mock_session, candidate_id=1, name="New Person")

        assert result is not None
        assert result["success"] is True
        # Should have added KnownPerson and FaceEmbedding
        assert mock_session.add.call_count >= 2
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_approve_candidate_links_to_existing_person(
        self, service: AutoEnrollmentService, mock_session: AsyncMock
    ) -> None:
        """Approving with existing person_id should link embedding to that person."""
        embedding = np.random.rand(512).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)

        # Create real-like mock objects that can have attributes set
        mock_candidate = MagicMock()
        mock_candidate.id = 1
        mock_candidate.face_event_id = 100
        mock_candidate.embedding = embedding.tobytes()
        mock_candidate.quality_score = 0.92
        mock_candidate.status = EnrollmentStatus.PENDING.value

        mock_event = MagicMock()
        mock_event.id = 100
        mock_event.matched_person_id = None
        mock_event.is_unknown = True

        # For person, we need to return something that the service
        # can use to set person_id on the embedding
        mock_person = MagicMock()
        mock_person.id = 5
        mock_person.name = "Existing Person"

        # Mock queries - note we need to handle candidate.status assignment
        mock_candidate_result = MagicMock()
        mock_candidate_result.scalar_one_or_none.return_value = mock_candidate

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_person_result = MagicMock()
        mock_person_result.scalar_one_or_none.return_value = mock_person

        mock_session.execute = AsyncMock(
            side_effect=[mock_candidate_result, mock_event_result, mock_person_result]
        )
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Use patch to avoid SQLAlchemy relationship issues
        with patch("backend.services.auto_enrollment_service.FaceEmbedding") as mock_embedding_cls:
            mock_embedding_instance = MagicMock()
            mock_embedding_cls.return_value = mock_embedding_instance

            result = await service.approve_candidate(mock_session, candidate_id=1, person_id=5)

        assert result is not None
        assert result["success"] is True
        assert result["person_id"] == 5

    @pytest.mark.asyncio
    async def test_reject_candidate_updates_status(
        self, service: AutoEnrollmentService, mock_session: AsyncMock
    ) -> None:
        """Rejecting a candidate should update its status to REJECTED."""
        mock_candidate = MagicMock(spec=EnrollmentCandidate)
        mock_candidate.id = 1
        mock_candidate.status = EnrollmentStatus.PENDING

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_candidate
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        result = await service.reject_candidate(
            mock_session, candidate_id=1, reason="Not a household member"
        )

        assert result is True
        assert mock_candidate.status == EnrollmentStatus.REJECTED
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_reject_candidate_returns_false_for_nonexistent(
        self, service: AutoEnrollmentService, mock_session: AsyncMock
    ) -> None:
        """Should return False when candidate doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service.reject_candidate(mock_session, candidate_id=999)

        assert result is False

    # =========================================================================
    # Test: Auto-Enroll (creates new person automatically)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_auto_enroll_creates_person_with_generated_name(
        self,
        service: AutoEnrollmentService,
        mock_session: AsyncMock,
        high_quality_event: MagicMock,
    ) -> None:
        """Auto-enroll should create a KnownPerson with a generated name."""
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Mock the count of existing auto-enrolled persons for naming
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5  # 5 existing auto-enrolled
        mock_session.execute = AsyncMock(return_value=mock_count_result)

        person = await service.auto_enroll(mock_session, high_quality_event)

        assert person is not None
        # Should have added both KnownPerson and FaceEmbedding
        assert mock_session.add.call_count == 2
        mock_session.commit.assert_called()


class TestAutoEnrollmentServiceSingleton:
    """Tests for singleton pattern of AutoEnrollmentService."""

    def teardown_method(self) -> None:
        """Reset singleton after each test."""
        reset_auto_enrollment_service()

    def test_get_auto_enrollment_service_returns_same_instance(self) -> None:
        """Should return the same instance on multiple calls."""
        service1 = get_auto_enrollment_service()
        service2 = get_auto_enrollment_service()
        assert service1 is service2

    def test_reset_auto_enrollment_service_clears_instance(self) -> None:
        """Reset should clear the singleton instance."""
        service1 = get_auto_enrollment_service()
        reset_auto_enrollment_service()
        service2 = get_auto_enrollment_service()
        assert service1 is not service2


class TestEnrollmentCandidateModel:
    """Tests for EnrollmentCandidate model."""

    def test_enrollment_status_enum_values(self) -> None:
        """Verify EnrollmentStatus enum values."""
        assert EnrollmentStatus.PENDING.value == "pending"
        assert EnrollmentStatus.APPROVED.value == "approved"
        assert EnrollmentStatus.REJECTED.value == "rejected"
        assert EnrollmentStatus.AUTO_ENROLLED.value == "auto_enrolled"

    def test_enrollment_candidate_repr(self) -> None:
        """Test string representation of EnrollmentCandidate."""
        candidate = EnrollmentCandidate(
            id=1,
            face_event_id=100,
            status=EnrollmentStatus.PENDING.value,
            quality_score=0.85,
            embedding=b"test_embedding",
        )
        repr_str = repr(candidate)
        assert "EnrollmentCandidate" in repr_str
        assert "id=1" in repr_str
        assert "face_event_id=100" in repr_str
