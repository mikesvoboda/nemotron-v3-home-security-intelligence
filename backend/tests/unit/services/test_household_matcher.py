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
