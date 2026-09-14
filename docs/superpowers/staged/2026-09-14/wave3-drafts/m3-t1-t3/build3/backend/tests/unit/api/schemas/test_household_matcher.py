"""Unit tests for Household Matcher API schemas.

Tests the Pydantic schemas for Household Matcher endpoints (NEM-4934).
"""

import pytest
from pydantic import ValidationError

from backend.api.schemas.household_matcher import (
    BatchMatchRequest,
    BatchMatchResponse,
    HouseholdMatchResponse,
    MatcherConfigResponse,
    PersonMatchRequest,
    VehicleMatchRequest,
)


class TestPersonMatchRequest:
    """Tests for PersonMatchRequest schema."""

    def test_valid_person_match_request(self) -> None:
        """Test creating a valid person match request."""
        embedding = [0.1] * 512  # 512-dim embedding
        request = PersonMatchRequest(embedding=embedding)
        assert len(request.embedding) == 512
        assert request.similarity_threshold is None

    def test_person_match_request_with_threshold(self) -> None:
        """Test person match request with custom threshold."""
        embedding = [0.5] * 256
        request = PersonMatchRequest(
            embedding=embedding,
            similarity_threshold=0.9,
        )
        assert request.similarity_threshold == 0.9

    def test_person_match_request_empty_embedding(self) -> None:
        """Test that empty embedding raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            PersonMatchRequest(embedding=[])
        # Pydantic 2.x uses "too_short" instead of "min_length"
        assert "too_short" in str(exc_info.value) or "at least 1" in str(exc_info.value)

    def test_person_match_request_invalid_threshold(self) -> None:
        """Test that invalid threshold values are rejected."""
        embedding = [0.1] * 10
        with pytest.raises(ValidationError):
            PersonMatchRequest(
                embedding=embedding,
                similarity_threshold=1.5,  # > 1.0
            )
        with pytest.raises(ValidationError):
            PersonMatchRequest(
                embedding=embedding,
                similarity_threshold=-0.1,  # < 0.0
            )


class TestVehicleMatchRequest:
    """Tests for VehicleMatchRequest schema."""

    def test_valid_vehicle_match_by_plate(self) -> None:
        """Test vehicle match request with license plate."""
        request = VehicleMatchRequest(
            license_plate="ABC123",
            vehicle_type="car",
        )
        assert request.license_plate == "ABC123"
        assert request.vehicle_type == "car"
        assert request.embedding is None
        assert request.color is None

    def test_valid_vehicle_match_by_embedding(self) -> None:
        """Test vehicle match request with embedding."""
        embedding = [0.3] * 768  # 768-dim CLIP embedding
        request = VehicleMatchRequest(
            embedding=embedding,
            vehicle_type="truck",
            color="blue",
        )
        assert len(request.embedding) == 768
        assert request.vehicle_type == "truck"
        assert request.color == "blue"

    def test_vehicle_match_request_all_fields(self) -> None:
        """Test vehicle match request with all fields."""
        request = VehicleMatchRequest(
            license_plate="XYZ789",
            embedding=[0.1] * 100,
            vehicle_type="van",
            color="white",
            similarity_threshold=0.8,
        )
        assert request.license_plate == "XYZ789"
        assert request.similarity_threshold == 0.8

    def test_vehicle_match_request_missing_vehicle_type(self) -> None:
        """Test that missing vehicle_type raises validation error."""
        with pytest.raises(ValidationError):
            VehicleMatchRequest(license_plate="ABC123")


class TestHouseholdMatchResponse:
    """Tests for HouseholdMatchResponse schema."""

    def test_no_match_response(self) -> None:
        """Test response for no match found."""
        response = HouseholdMatchResponse(matched=False)
        assert response.matched is False
        assert response.member_id is None
        assert response.vehicle_id is None
        assert response.similarity == 0.0
        assert response.match_type == ""

    def test_person_match_response(self) -> None:
        """Test response for person match."""
        response = HouseholdMatchResponse(
            matched=True,
            member_id=1,
            member_name="John Doe",
            similarity=0.92,
            match_type="person",
            member_role="resident",
            schedule_status=True,
        )
        assert response.matched is True
        assert response.member_id == 1
        assert response.member_name == "John Doe"
        assert response.similarity == 0.92
        assert response.match_type == "person"
        assert response.member_role == "resident"
        assert response.schedule_status is True

    def test_vehicle_plate_match_response(self) -> None:
        """Test response for license plate match."""
        response = HouseholdMatchResponse(
            matched=True,
            vehicle_id=5,
            vehicle_description="Silver Tesla Model 3",
            similarity=1.0,
            match_type="license_plate",
        )
        assert response.matched is True
        assert response.vehicle_id == 5
        assert response.similarity == 1.0
        assert response.match_type == "license_plate"

    def test_vehicle_visual_match_response(self) -> None:
        """Test response for visual vehicle match."""
        response = HouseholdMatchResponse(
            matched=True,
            vehicle_id=3,
            vehicle_description="Blue Honda Civic",
            similarity=0.88,
            match_type="vehicle_visual",
        )
        assert response.similarity == 0.88
        assert response.match_type == "vehicle_visual"

    def test_similarity_bounds(self) -> None:
        """Test that similarity values are validated."""
        # Valid bounds
        HouseholdMatchResponse(matched=True, similarity=0.0)
        HouseholdMatchResponse(matched=True, similarity=1.0)

        # Invalid bounds
        with pytest.raises(ValidationError):
            HouseholdMatchResponse(matched=True, similarity=-0.1)
        with pytest.raises(ValidationError):
            HouseholdMatchResponse(matched=True, similarity=1.1)


class TestBatchMatchRequest:
    """Tests for BatchMatchRequest schema."""

    def test_valid_batch_request(self) -> None:
        """Test valid batch match request."""
        request = BatchMatchRequest(
            detections=[
                {"id": 1, "object_type": "person"},
                {"id": 2, "object_type": "car"},
            ],
            enrichment_data={
                "1": {"embeddings": {"person_reid": [0.1] * 512}},
                "2": {"license_plates": [{"text": "ABC123"}]},
            },
        )
        assert len(request.detections) == 2
        assert "1" in request.enrichment_data
        assert "2" in request.enrichment_data

    def test_batch_request_empty_detections(self) -> None:
        """Test that empty detections list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            BatchMatchRequest(
                detections=[],
                enrichment_data={},
            )
        # Pydantic 2.x uses "too_short" instead of "min_length"
        assert "too_short" in str(exc_info.value) or "at least 1" in str(exc_info.value)


class TestBatchMatchResponse:
    """Tests for BatchMatchResponse schema."""

    def test_empty_batch_response(self) -> None:
        """Test batch response with no matches."""
        response = BatchMatchResponse(
            person_matches={},
            vehicle_matches={},
            total_detections=2,
            total_matches=0,
        )
        assert response.total_detections == 2
        assert response.total_matches == 0

    def test_batch_response_with_matches(self) -> None:
        """Test batch response with matches."""
        person_match = HouseholdMatchResponse(
            matched=True,
            member_id=1,
            member_name="John",
            similarity=0.9,
            match_type="person",
        )
        vehicle_match = HouseholdMatchResponse(
            matched=True,
            vehicle_id=2,
            vehicle_description="Tesla",
            similarity=1.0,
            match_type="license_plate",
        )
        response = BatchMatchResponse(
            person_matches={"1": person_match},
            vehicle_matches={"2": vehicle_match},
            total_detections=2,
            total_matches=2,
        )
        assert len(response.person_matches) == 1
        assert len(response.vehicle_matches) == 1
        assert response.total_matches == 2


class TestMatcherConfigResponse:
    """Tests for MatcherConfigResponse schema."""

    def test_config_response(self) -> None:
        """Test matcher config response."""
        response = MatcherConfigResponse(
            similarity_threshold=0.85,
            total_member_embeddings=10,
            total_registered_vehicles=5,
        )
        assert response.similarity_threshold == 0.85
        assert response.total_member_embeddings == 10
        assert response.total_registered_vehicles == 5

    def test_config_response_zero_counts(self) -> None:
        """Test config response with zero counts."""
        response = MatcherConfigResponse(
            similarity_threshold=0.9,
            total_member_embeddings=0,
            total_registered_vehicles=0,
        )
        assert response.total_member_embeddings == 0
        assert response.total_registered_vehicles == 0
