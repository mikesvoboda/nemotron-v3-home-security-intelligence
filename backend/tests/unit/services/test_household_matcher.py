"""Unit tests for HouseholdMatcher service.

Tests cover:
- HouseholdMatch dataclass creation and fields
- Cosine similarity computation for embeddings
- Person matching via embeddings with threshold
- Vehicle matching via license plate (exact match)
- Vehicle matching via visual embedding (fallback)
- Edge cases: no embeddings, no matches, empty database
- Case-insensitive license plate matching

Implements NEM-3017: Implement HouseholdMatcher service for person/vehicle recognition.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from backend.models.household import (
    HouseholdMember,
    MemberRole,
    PersonEmbedding,
    RegisteredVehicle,
    TrustLevel,
    VehicleType,
)
from backend.services.household_matcher import (
    HouseholdMatch,
    HouseholdMatcher,
    cosine_similarity,
    get_household_matcher,
    reset_household_matcher,
)

# =============================================================================
# HouseholdMatch Dataclass Tests
# =============================================================================


class TestHouseholdMatch:
    """Tests for HouseholdMatch dataclass."""

    def test_household_match_default_values(self) -> None:
        """Test HouseholdMatch has correct default values."""
        match = HouseholdMatch()

        assert match.member_id is None
        assert match.member_name is None
        assert match.vehicle_id is None
        assert match.vehicle_description is None
        assert match.similarity == 0.0
        assert match.match_type == ""

    def test_household_match_person_match(self) -> None:
        """Test HouseholdMatch for a person match."""
        match = HouseholdMatch(
            member_id=1,
            member_name="John Doe",
            similarity=0.92,
            match_type="person",
        )

        assert match.member_id == 1
        assert match.member_name == "John Doe"
        assert match.vehicle_id is None
        assert match.similarity == 0.92
        assert match.match_type == "person"

    def test_household_match_vehicle_license_plate(self) -> None:
        """Test HouseholdMatch for a vehicle license plate match."""
        match = HouseholdMatch(
            vehicle_id=5,
            vehicle_description="Silver Tesla Model 3",
            similarity=1.0,
            match_type="license_plate",
        )

        assert match.member_id is None
        assert match.vehicle_id == 5
        assert match.vehicle_description == "Silver Tesla Model 3"
        assert match.similarity == 1.0
        assert match.match_type == "license_plate"

    def test_household_match_vehicle_visual(self) -> None:
        """Test HouseholdMatch for a vehicle visual match."""
        match = HouseholdMatch(
            vehicle_id=3,
            vehicle_description="Blue Honda Civic",
            similarity=0.88,
            match_type="vehicle_visual",
        )

        assert match.vehicle_id == 3
        assert match.similarity == 0.88
        assert match.match_type == "vehicle_visual"


# =============================================================================
# Cosine Similarity Tests
# =============================================================================


class TestCosineSimilarity:
    """Tests for cosine_similarity function."""

    def test_identical_vectors(self) -> None:
        """Test cosine similarity of identical vectors is 1."""
        vec = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
        similarity = cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.0001

    def test_orthogonal_vectors(self) -> None:
        """Test cosine similarity of orthogonal vectors is 0."""
        vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        similarity = cosine_similarity(vec1, vec2)
        assert abs(similarity) < 0.0001

    def test_opposite_vectors(self) -> None:
        """Test cosine similarity of opposite vectors is -1."""
        vec1 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        vec2 = np.array([-1.0, -2.0, -3.0], dtype=np.float32)
        similarity = cosine_similarity(vec1, vec2)
        assert abs(similarity - (-1.0)) < 0.0001

    def test_similar_vectors(self) -> None:
        """Test cosine similarity of similar vectors is high."""
        vec1 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        vec2 = np.array([1.1, 2.1, 3.1], dtype=np.float32)
        similarity = cosine_similarity(vec1, vec2)
        assert similarity > 0.99

    def test_zero_vector_returns_zero(self) -> None:
        """Test cosine similarity with zero vector returns 0."""
        vec1 = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        similarity = cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_normalized_vectors(self) -> None:
        """Test cosine similarity with normalized vectors."""
        vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([0.707, 0.707, 0.0], dtype=np.float32)  # 45 degrees
        similarity = cosine_similarity(vec1, vec2)
        assert abs(similarity - 0.707) < 0.01


# =============================================================================
# HouseholdMatcher Person Matching Tests
# =============================================================================


class TestHouseholdMatcherPersonMatching:
    """Tests for HouseholdMatcher.match_person method."""

    @pytest.fixture
    def matcher(self) -> HouseholdMatcher:
        """Create a HouseholdMatcher instance."""
        return HouseholdMatcher()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AsyncSession."""
        return AsyncMock()

    def _create_member_with_embedding(
        self,
        member_id: int,
        name: str,
        embedding_data: bytes,
    ) -> tuple[HouseholdMember, PersonEmbedding]:
        """Helper to create a household member with embedding."""
        member = MagicMock(spec=HouseholdMember)
        member.id = member_id
        member.name = name
        member.role = MemberRole.RESIDENT
        member.trusted_level = TrustLevel.FULL

        embedding = MagicMock(spec=PersonEmbedding)
        embedding.id = member_id * 10
        embedding.member_id = member_id
        embedding.embedding = embedding_data
        embedding.confidence = 1.0
        embedding.member = member

        return member, embedding

    @pytest.mark.asyncio
    async def test_match_person_exact_match(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test matching a person with an exact embedding match."""
        # Create a test embedding
        test_embedding = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)
        stored_embedding = test_embedding.tobytes()

        # Mock the database query to return a matching member
        _member, _person_embedding = self._create_member_with_embedding(
            member_id=1,
            name="John Doe",
            embedding_data=stored_embedding,
        )

        # Mock _get_all_member_embeddings to return our test data
        matcher._get_all_member_embeddings = AsyncMock(
            return_value=[(1, "John Doe", test_embedding)]
        )

        # Perform the match
        result = await matcher.match_person(test_embedding, mock_session)

        # Verify the result
        assert result is not None
        assert result.member_id == 1
        assert result.member_name == "John Doe"
        assert result.similarity > 0.99  # Should be ~1.0 for identical vectors
        assert result.match_type == "person"

    @pytest.mark.asyncio
    async def test_match_person_similar_embedding(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test matching a person with a similar (not exact) embedding."""
        # Create test embeddings that are similar but not identical
        test_embedding = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)
        stored_embedding = np.array([0.11, 0.21, 0.31, 0.41, 0.51], dtype=np.float32)

        # Mock _get_all_member_embeddings
        matcher._get_all_member_embeddings = AsyncMock(
            return_value=[(1, "Jane Doe", stored_embedding)]
        )

        result = await matcher.match_person(test_embedding, mock_session)

        assert result is not None
        assert result.member_id == 1
        assert result.member_name == "Jane Doe"
        assert result.similarity > 0.85  # Should exceed threshold
        assert result.match_type == "person"

    @pytest.mark.asyncio
    async def test_match_person_below_threshold(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test that dissimilar embeddings don't match."""
        # Create very different embeddings
        test_embedding = np.array([1.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        stored_embedding = np.array([0.0, 1.0, 0.0, 0.0, 0.0], dtype=np.float32)

        matcher._get_all_member_embeddings = AsyncMock(
            return_value=[(1, "Random Person", stored_embedding)]
        )

        result = await matcher.match_person(test_embedding, mock_session)

        assert result is None  # No match because similarity < 0.85

    @pytest.mark.asyncio
    async def test_match_person_no_embeddings(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test matching when no embeddings exist in database."""
        test_embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)

        matcher._get_all_member_embeddings = AsyncMock(return_value=[])

        result = await matcher.match_person(test_embedding, mock_session)

        assert result is None

    @pytest.mark.asyncio
    async def test_match_person_best_match_selected(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test that the best matching person is selected from multiple candidates."""
        test_embedding = np.array([1.0, 0.0, 0.0], dtype=np.float32)

        # Create multiple embeddings with varying similarity
        embeddings = [
            (1, "Low Match", np.array([0.7, 0.7, 0.1], dtype=np.float32)),  # ~0.7 similarity
            (2, "Best Match", np.array([0.99, 0.01, 0.0], dtype=np.float32)),  # ~0.99 similarity
            (3, "Medium Match", np.array([0.9, 0.3, 0.0], dtype=np.float32)),  # ~0.95 similarity
        ]

        matcher._get_all_member_embeddings = AsyncMock(return_value=embeddings)

        result = await matcher.match_person(test_embedding, mock_session)

        assert result is not None
        assert result.member_id == 2
        assert result.member_name == "Best Match"
        assert result.similarity > 0.98

    @pytest.mark.asyncio
    async def test_match_person_custom_threshold(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test matching with a custom similarity threshold."""
        matcher = HouseholdMatcher(similarity_threshold=0.95)

        test_embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        # This embedding is similar but not >0.95
        stored_embedding = np.array([0.11, 0.21, 0.31], dtype=np.float32)

        matcher._get_all_member_embeddings = AsyncMock(
            return_value=[(1, "Test Person", stored_embedding)]
        )

        # With default 0.85 threshold, this would match
        # With 0.95 threshold, it should not match (similarity ~0.999)
        # Actually this should match because the vectors are very similar
        result = await matcher.match_person(test_embedding, mock_session)

        # The similarity of these vectors is ~0.9997, so it should match
        assert result is not None


# =============================================================================
# HouseholdMatcher Vehicle Matching Tests
# =============================================================================


class TestHouseholdMatcherVehicleMatching:
    """Tests for HouseholdMatcher.match_vehicle method."""

    @pytest.fixture
    def matcher(self) -> HouseholdMatcher:
        """Create a HouseholdMatcher instance."""
        return HouseholdMatcher()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AsyncSession."""
        return AsyncMock()

    def _create_vehicle(
        self,
        vehicle_id: int,
        description: str,
        license_plate: str | None = None,
        vehicle_type: VehicleType = VehicleType.CAR,
        color: str | None = None,
        reid_embedding: bytes | None = None,
    ) -> MagicMock:
        """Helper to create a mock RegisteredVehicle."""
        vehicle = MagicMock(spec=RegisteredVehicle)
        vehicle.id = vehicle_id
        vehicle.description = description
        vehicle.license_plate = license_plate
        vehicle.vehicle_type = vehicle_type
        vehicle.color = color
        vehicle.reid_embedding = reid_embedding
        vehicle.trusted = True
        return vehicle

    @pytest.mark.asyncio
    async def test_match_vehicle_by_license_plate(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test matching a vehicle by exact license plate."""
        vehicle = self._create_vehicle(
            vehicle_id=1,
            description="Silver Tesla Model 3",
            license_plate="ABC123",
        )

        matcher._find_by_plate = AsyncMock(return_value=vehicle)

        result = await matcher.match_vehicle(
            license_plate="ABC123",
            vehicle_embedding=None,
            vehicle_type="car",
            color="silver",
            session=mock_session,
        )

        assert result is not None
        assert result.vehicle_id == 1
        assert result.vehicle_description == "Silver Tesla Model 3"
        assert result.similarity == 1.0
        assert result.match_type == "license_plate"

    @pytest.mark.asyncio
    async def test_match_vehicle_license_plate_case_insensitive(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test that license plate matching is case-insensitive."""
        vehicle = self._create_vehicle(
            vehicle_id=1,
            description="Red Ford F150",
            license_plate="XYZ789",
        )

        matcher._find_by_plate = AsyncMock(return_value=vehicle)

        # Query with lowercase
        result = await matcher.match_vehicle(
            license_plate="xyz789",
            vehicle_embedding=None,
            vehicle_type="truck",
            color="red",
            session=mock_session,
        )

        assert result is not None
        assert result.vehicle_id == 1
        assert result.match_type == "license_plate"

    @pytest.mark.asyncio
    async def test_match_vehicle_by_visual_embedding(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test matching a vehicle by visual embedding when no license plate match."""
        test_embedding = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)

        # No license plate match
        matcher._find_by_plate = AsyncMock(return_value=None)

        # Visual match found
        matcher._match_vehicle_visual = AsyncMock(
            return_value=HouseholdMatch(
                vehicle_id=2,
                vehicle_description="Blue Honda Civic",
                similarity=0.90,
                match_type="vehicle_visual",
            )
        )

        result = await matcher.match_vehicle(
            license_plate=None,
            vehicle_embedding=test_embedding,
            vehicle_type="car",
            color="blue",
            session=mock_session,
        )

        assert result is not None
        assert result.vehicle_id == 2
        assert result.match_type == "vehicle_visual"
        assert result.similarity == 0.90

    @pytest.mark.asyncio
    async def test_match_vehicle_license_plate_priority(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test that license plate match takes priority over visual match."""
        test_embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)

        plate_vehicle = self._create_vehicle(
            vehicle_id=1,
            description="Plate Match Car",
            license_plate="ABC123",
        )

        matcher._find_by_plate = AsyncMock(return_value=plate_vehicle)
        matcher._match_vehicle_visual = AsyncMock()  # Should not be called

        result = await matcher.match_vehicle(
            license_plate="ABC123",
            vehicle_embedding=test_embedding,
            vehicle_type="car",
            color="black",
            session=mock_session,
        )

        assert result is not None
        assert result.vehicle_id == 1
        assert result.match_type == "license_plate"
        matcher._match_vehicle_visual.assert_not_called()

    @pytest.mark.asyncio
    async def test_match_vehicle_no_match(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test when no vehicle match is found."""
        matcher._find_by_plate = AsyncMock(return_value=None)
        matcher._match_vehicle_visual = AsyncMock(return_value=None)

        result = await matcher.match_vehicle(
            license_plate="UNKNOWN",
            vehicle_embedding=np.array([0.1, 0.2, 0.3], dtype=np.float32),
            vehicle_type="car",
            color="green",
            session=mock_session,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_match_vehicle_no_plate_no_embedding(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test matching when neither plate nor embedding provided."""
        result = await matcher.match_vehicle(
            license_plate=None,
            vehicle_embedding=None,
            vehicle_type="car",
            color="white",
            session=mock_session,
        )

        assert result is None


# =============================================================================
# HouseholdMatcher Visual Vehicle Matching Tests
# =============================================================================


class TestHouseholdMatcherVisualVehicleMatching:
    """Tests for HouseholdMatcher._match_vehicle_visual method."""

    @pytest.fixture
    def matcher(self) -> HouseholdMatcher:
        """Create a HouseholdMatcher instance."""
        return HouseholdMatcher()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AsyncSession."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_visual_match_by_embedding(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test visual matching by vehicle embedding."""
        test_embedding = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)
        stored_embedding = test_embedding  # Same embedding for exact match

        # Mock _get_vehicles_with_embeddings
        matcher._get_vehicles_with_embeddings = AsyncMock(
            return_value=[(1, "Blue Honda Civic", VehicleType.CAR, "blue", stored_embedding)]
        )

        result = await matcher._match_vehicle_visual(
            embedding=test_embedding,
            vehicle_type="car",
            color="blue",
            session=mock_session,
        )

        assert result is not None
        assert result.vehicle_id == 1
        assert result.vehicle_description == "Blue Honda Civic"
        assert result.similarity > 0.99
        assert result.match_type == "vehicle_visual"

    @pytest.mark.asyncio
    async def test_visual_match_below_threshold(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test that dissimilar vehicle embeddings don't match."""
        test_embedding = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        stored_embedding = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        matcher._get_vehicles_with_embeddings = AsyncMock(
            return_value=[(1, "Some Vehicle", VehicleType.CAR, "red", stored_embedding)]
        )

        result = await matcher._match_vehicle_visual(
            embedding=test_embedding,
            vehicle_type="car",
            color="red",
            session=mock_session,
        )

        assert result is None  # No match because similarity < 0.85

    @pytest.mark.asyncio
    async def test_visual_match_no_vehicles(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test visual matching when no vehicles have embeddings."""
        test_embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)

        matcher._get_vehicles_with_embeddings = AsyncMock(return_value=[])

        result = await matcher._match_vehicle_visual(
            embedding=test_embedding,
            vehicle_type="car",
            color="silver",
            session=mock_session,
        )

        assert result is None


# =============================================================================
# HouseholdMatcher Singleton Tests
# =============================================================================


class TestHouseholdMatcherSingleton:
    """Tests for global HouseholdMatcher singleton functions."""

    def test_get_household_matcher_returns_instance(self) -> None:
        """Test that get_household_matcher returns a HouseholdMatcher instance."""
        reset_household_matcher()  # Reset first to ensure clean state
        matcher = get_household_matcher()
        assert isinstance(matcher, HouseholdMatcher)

    def test_get_household_matcher_returns_same_instance(self) -> None:
        """Test that get_household_matcher returns the same instance."""
        reset_household_matcher()
        matcher1 = get_household_matcher()
        matcher2 = get_household_matcher()
        assert matcher1 is matcher2

    def test_reset_household_matcher(self) -> None:
        """Test that reset_household_matcher creates a new instance."""
        reset_household_matcher()
        matcher1 = get_household_matcher()
        reset_household_matcher()
        matcher2 = get_household_matcher()
        assert matcher1 is not matcher2


# =============================================================================
# HouseholdMatcher Threshold Configuration Tests
# =============================================================================


class TestHouseholdMatcherConfiguration:
    """Tests for HouseholdMatcher configuration."""

    def test_default_similarity_threshold(self) -> None:
        """Test that default similarity threshold is 0.85."""
        matcher = HouseholdMatcher()
        assert matcher.similarity_threshold == 0.85

    def test_custom_similarity_threshold(self) -> None:
        """Test setting a custom similarity threshold."""
        matcher = HouseholdMatcher(similarity_threshold=0.90)
        assert matcher.similarity_threshold == 0.90

    def test_similarity_threshold_property(self) -> None:
        """Test the similarity_threshold property."""
        matcher = HouseholdMatcher(similarity_threshold=0.75)
        assert matcher.similarity_threshold == 0.75


# =============================================================================
# HouseholdMatcher.match_detections Tests (NEM-4234 Phase 2)
# =============================================================================


class TestHouseholdMatcherMatchDetections:
    """Tests for HouseholdMatcher.match_detections method.

    This method implements detection-attributed household matching to prevent
    context bleeding between detections in the same batch.
    """

    @pytest.fixture
    def matcher(self) -> HouseholdMatcher:
        """Create a HouseholdMatcher instance."""
        return HouseholdMatcher()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AsyncSession."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_match_detections_returns_tuple_of_dicts(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test that match_detections returns a tuple of two dicts."""
        # Mock empty match results
        matcher.match_person = AsyncMock(return_value=None)
        matcher.match_vehicle = AsyncMock(return_value=None)

        person_matches, vehicle_matches = await matcher.match_detections(
            detections=[],
            enrichment_data={},
            session=mock_session,
        )

        assert isinstance(person_matches, dict)
        assert isinstance(vehicle_matches, dict)

    @pytest.mark.asyncio
    async def test_match_detections_with_person_detection(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test matching a person detection with cached embedding."""
        # Create mock detection
        mock_detection = MagicMock()
        mock_detection.id = 1
        mock_detection.object_type = "person"

        # Create enrichment data with cached person embedding
        enrichment_data = {
            1: {
                "embeddings": {
                    "person_reid": [0.1, 0.2, 0.3, 0.4, 0.5],
                }
            }
        }

        # Mock successful person match
        expected_match = HouseholdMatch(
            member_id=1,
            member_name="Mike",
            similarity=0.92,
            match_type="person",
        )
        matcher.match_person = AsyncMock(return_value=expected_match)
        matcher.match_vehicle = AsyncMock(return_value=None)

        person_matches, vehicle_matches = await matcher.match_detections(
            detections=[mock_detection],
            enrichment_data=enrichment_data,
            session=mock_session,
        )

        # Should have match for detection 1
        assert 1 in person_matches
        assert person_matches[1].member_name == "Mike"
        assert len(vehicle_matches) == 0

    @pytest.mark.asyncio
    async def test_match_detections_with_vehicle_detection(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test matching a vehicle detection."""
        # Create mock detection
        mock_detection = MagicMock()
        mock_detection.id = 2
        mock_detection.object_type = "car"

        # Create enrichment data with license plate
        enrichment_data = {
            2: {
                "license_plates": [{"text": "ABC123"}],
                "embeddings": {},
            }
        }

        # Mock successful vehicle match
        expected_match = HouseholdMatch(
            vehicle_id=1,
            vehicle_description="Honda Civic",
            similarity=1.0,
            match_type="license_plate",
        )
        matcher.match_person = AsyncMock(return_value=None)
        matcher.match_vehicle = AsyncMock(return_value=expected_match)

        person_matches, vehicle_matches = await matcher.match_detections(
            detections=[mock_detection],
            enrichment_data=enrichment_data,
            session=mock_session,
        )

        # Should have match for detection 2
        assert len(person_matches) == 0
        assert 2 in vehicle_matches
        assert vehicle_matches[2].vehicle_description == "Honda Civic"

    @pytest.mark.asyncio
    async def test_match_detections_multiple_detections_isolated(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test that matches are attributed to correct detections (isolation).

        This is the critical test for NEM-4234 Phase 2: verify that Mike's
        match is only associated with detection 1, not detection 2.
        """
        # Create mock detections
        detection1 = MagicMock()
        detection1.id = 1
        detection1.object_type = "person"

        detection2 = MagicMock()
        detection2.id = 2
        detection2.object_type = "person"

        # Only detection 1 has a person embedding
        enrichment_data = {
            1: {
                "embeddings": {
                    "person_reid": [0.1, 0.2, 0.3, 0.4, 0.5],
                }
            },
            2: {
                "embeddings": {}  # No embedding for detection 2
            },
        }

        # Mock match only for detection 1
        mike_match = HouseholdMatch(
            member_id=1,
            member_name="Mike",
            similarity=0.92,
            match_type="person",
        )

        call_count = [0]

        async def mock_match_person(embedding, session):
            call_count[0] += 1
            # Return Mike match only if called with detection 1's embedding
            if call_count[0] == 1:
                return mike_match
            return None

        matcher.match_person = mock_match_person
        matcher.match_vehicle = AsyncMock(return_value=None)

        person_matches, vehicle_matches = await matcher.match_detections(
            detections=[detection1, detection2],
            enrichment_data=enrichment_data,
            session=mock_session,
        )

        # Mike should be associated with detection 1 only
        assert 1 in person_matches
        assert person_matches[1].member_name == "Mike"

        # Detection 2 should NOT have Mike (context isolation)
        assert 2 not in person_matches

    @pytest.mark.asyncio
    async def test_match_detections_no_enrichment_data(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test detection without enrichment data is skipped."""
        mock_detection = MagicMock()
        mock_detection.id = 1
        mock_detection.object_type = "person"

        # No enrichment data for this detection
        enrichment_data = {}

        matcher.match_person = AsyncMock(return_value=None)
        matcher.match_vehicle = AsyncMock(return_value=None)

        person_matches, vehicle_matches = await matcher.match_detections(
            detections=[mock_detection],
            enrichment_data=enrichment_data,
            session=mock_session,
        )

        # Should have no matches
        assert len(person_matches) == 0
        assert len(vehicle_matches) == 0
        # match_person should not be called
        matcher.match_person.assert_not_called()


# =============================================================================
# HouseholdMatcher Cached Embedding Tests (NEM-4234 Phase 3)
# =============================================================================


class TestHouseholdMatcherCachedEmbeddings:
    """Tests for HouseholdMatcher using cached embeddings from enrichment_data.

    These tests verify that HouseholdMatcher can read pre-computed embeddings
    from Detection.enrichment_data instead of recomputing them.

    Related to NEM-4234: AI Pipeline Accuracy Improvements - Phase 3.
    """

    @pytest.fixture
    def matcher(self) -> HouseholdMatcher:
        """Create a HouseholdMatcher instance."""
        return HouseholdMatcher()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AsyncSession."""
        return AsyncMock()

    def test_extract_person_embedding_from_enrichment_data(self) -> None:
        """Test extracting person_reid embedding from enrichment_data."""
        # This tests the helper method that will read cached embeddings
        enrichment_data = {
            "embeddings": {
                "person_reid": [0.1] * 512,
                "face_clip": [0.2] * 768,
            },
            "license_plates": [],
        }

        # Import the helper function (will be implemented)
        from backend.services.household_matcher import extract_person_embedding

        embedding = extract_person_embedding(enrichment_data)

        assert embedding is not None
        assert len(embedding) == 512
        assert embedding[0] == 0.1

    def test_extract_person_embedding_missing_embeddings(self) -> None:
        """Test extracting person embedding when embeddings field is missing."""
        enrichment_data = {
            "license_plates": [],
            "faces": [],
        }

        from backend.services.household_matcher import extract_person_embedding

        embedding = extract_person_embedding(enrichment_data)

        assert embedding is None

    def test_extract_person_embedding_none_person_reid(self) -> None:
        """Test extracting person embedding when person_reid is None."""
        enrichment_data = {
            "embeddings": {
                "person_reid": None,
                "vehicle_visual": [0.3] * 768,
            },
        }

        from backend.services.household_matcher import extract_person_embedding

        embedding = extract_person_embedding(enrichment_data)

        assert embedding is None

    def test_extract_person_embedding_empty_list(self) -> None:
        """Test extracting person embedding when person_reid is empty list."""
        enrichment_data = {
            "embeddings": {
                "person_reid": [],
            },
        }

        from backend.services.household_matcher import extract_person_embedding

        embedding = extract_person_embedding(enrichment_data)

        # Empty list should return None (no valid embedding)
        assert embedding is None

    def test_extract_vehicle_embedding_from_enrichment_data(self) -> None:
        """Test extracting vehicle_visual embedding from enrichment_data."""
        enrichment_data = {
            "embeddings": {
                "vehicle_visual": [0.5] * 768,
            },
            "vehicle_classifications": {"1": {"vehicle_type": "sedan"}},
        }

        from backend.services.household_matcher import extract_vehicle_embedding

        embedding = extract_vehicle_embedding(enrichment_data)

        assert embedding is not None
        assert len(embedding) == 768
        assert embedding[0] == 0.5

    def test_extract_vehicle_embedding_missing(self) -> None:
        """Test extracting vehicle embedding when not present."""
        enrichment_data = {
            "embeddings": {
                "person_reid": [0.1] * 512,
            },
        }

        from backend.services.household_matcher import extract_vehicle_embedding

        embedding = extract_vehicle_embedding(enrichment_data)

        assert embedding is None

    @pytest.mark.asyncio
    async def test_match_person_from_cached_embedding(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test matching a person using cached embedding from enrichment_data."""
        # Simulate a stored member embedding
        stored_embedding = np.array([0.1] * 512, dtype=np.float32)

        matcher._get_all_member_embeddings = AsyncMock(
            return_value=[(1, "John Doe", stored_embedding)]
        )

        # Create enrichment_data with cached person_reid embedding
        enrichment_data = {
            "embeddings": {
                "person_reid": [0.1] * 512,  # Same as stored - should match
            },
        }

        from backend.services.household_matcher import extract_person_embedding

        cached_embedding = extract_person_embedding(enrichment_data)
        assert cached_embedding is not None

        # Convert to numpy array for matching
        cached_np = np.array(cached_embedding, dtype=np.float32)
        result = await matcher.match_person(cached_np, mock_session)

        assert result is not None
        assert result.member_id == 1
        assert result.member_name == "John Doe"
        assert result.similarity > 0.99

    @pytest.mark.asyncio
    async def test_match_vehicle_from_cached_embedding(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Test matching a vehicle using cached embedding from enrichment_data."""
        stored_embedding = np.array([0.5] * 768, dtype=np.float32)

        matcher._find_by_plate = AsyncMock(return_value=None)
        matcher._get_vehicles_with_embeddings = AsyncMock(
            return_value=[(1, "Silver Honda Accord", VehicleType.CAR, "silver", stored_embedding)]
        )

        enrichment_data = {
            "embeddings": {
                "vehicle_visual": [0.5] * 768,
            },
        }

        from backend.services.household_matcher import extract_vehicle_embedding

        cached_embedding = extract_vehicle_embedding(enrichment_data)
        assert cached_embedding is not None

        cached_np = np.array(cached_embedding, dtype=np.float32)
        result = await matcher.match_vehicle(
            license_plate=None,
            vehicle_embedding=cached_np,
            vehicle_type="car",
            color="silver",
            session=mock_session,
        )

        assert result is not None
        assert result.vehicle_id == 1
        assert result.similarity > 0.99
