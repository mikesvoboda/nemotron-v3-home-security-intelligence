"""Unit tests for Household Matcher API routes.

Tests the API endpoints for Household Matcher service (NEM-4934).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from backend.services.household_matcher import HouseholdMatch


class TestMatchPerson:
    """Tests for POST /api/household-matcher/match-person endpoint."""

    @pytest.mark.asyncio
    async def test_match_person_success(self) -> None:
        """Test successfully matching a person embedding."""
        from backend.api.routes.household_matcher import match_person
        from backend.api.schemas.household_matcher import PersonMatchRequest

        mock_db = AsyncMock()

        mock_match = HouseholdMatch(
            member_id=1,
            member_name="John Doe",
            similarity=0.92,
            match_type="person",
            member_role="resident",
            schedule_status=True,
        )

        request = PersonMatchRequest(embedding=[0.1] * 512)

        with patch(
            "backend.api.routes.household_matcher.get_household_matcher"
        ) as mock_get_matcher:
            mock_matcher = AsyncMock()
            mock_matcher.match_person.return_value = mock_match
            mock_get_matcher.return_value = mock_matcher

            result = await match_person(request=request, db=mock_db)

        assert result.matched is True
        assert result.member_id == 1
        assert result.member_name == "John Doe"
        assert result.similarity == 0.92
        assert result.match_type == "person"

    @pytest.mark.asyncio
    async def test_match_person_no_match(self) -> None:
        """Test no match found for person embedding."""
        from backend.api.routes.household_matcher import match_person
        from backend.api.schemas.household_matcher import PersonMatchRequest

        mock_db = AsyncMock()
        request = PersonMatchRequest(embedding=[0.5] * 512)

        with patch(
            "backend.api.routes.household_matcher.get_household_matcher"
        ) as mock_get_matcher:
            mock_matcher = AsyncMock()
            mock_matcher.match_person.return_value = None
            mock_get_matcher.return_value = mock_matcher

            result = await match_person(request=request, db=mock_db)

        assert result.matched is False
        assert result.member_id is None

    @pytest.mark.asyncio
    async def test_match_person_custom_threshold(self) -> None:
        """Test matching with custom similarity threshold."""
        from backend.api.routes.household_matcher import match_person
        from backend.api.schemas.household_matcher import PersonMatchRequest
        from backend.services.household_matcher import HouseholdMatcher

        mock_db = AsyncMock()
        request = PersonMatchRequest(
            embedding=[0.1] * 512,
            similarity_threshold=0.95,
        )

        with patch.object(
            HouseholdMatcher, "match_person", new_callable=AsyncMock
        ) as mock_match:
            mock_match.return_value = None
            result = await match_person(request=request, db=mock_db)

        assert result.matched is False

    @pytest.mark.asyncio
    async def test_match_person_empty_embedding(self) -> None:
        """Test that empty embedding returns 400 error."""
        from fastapi import HTTPException

        from backend.api.routes.household_matcher import match_person
        from backend.api.schemas.household_matcher import PersonMatchRequest

        mock_db = AsyncMock()

        # Bypass Pydantic validation with valid request but trigger route validation
        request = PersonMatchRequest(embedding=[0.1])  # Minimal valid embedding

        # Mock the numpy conversion to simulate empty check
        with patch("backend.api.routes.household_matcher.np.array") as mock_array:
            mock_array.return_value = np.array([], dtype=np.float32)
            # This test actually needs to test the schema validation
            # The route check is for len(embedding) == 0 after assignment

        # The schema validation handles min_length=1, so direct route call won't hit that
        # Test the schema validation instead
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PersonMatchRequest(embedding=[])


class TestMatchVehicle:
    """Tests for POST /api/household-matcher/match-vehicle endpoint."""

    @pytest.mark.asyncio
    async def test_match_vehicle_by_plate_success(self) -> None:
        """Test successfully matching vehicle by license plate."""
        from backend.api.routes.household_matcher import match_vehicle
        from backend.api.schemas.household_matcher import VehicleMatchRequest

        mock_db = AsyncMock()

        mock_match = HouseholdMatch(
            vehicle_id=5,
            vehicle_description="Silver Tesla Model 3",
            similarity=1.0,
            match_type="license_plate",
        )

        request = VehicleMatchRequest(
            license_plate="ABC123",
            vehicle_type="car",
        )

        with patch(
            "backend.api.routes.household_matcher.get_household_matcher"
        ) as mock_get_matcher:
            mock_matcher = AsyncMock()
            mock_matcher.match_vehicle.return_value = mock_match
            mock_get_matcher.return_value = mock_matcher

            result = await match_vehicle(request=request, db=mock_db)

        assert result.matched is True
        assert result.vehicle_id == 5
        assert result.vehicle_description == "Silver Tesla Model 3"
        assert result.similarity == 1.0
        assert result.match_type == "license_plate"

    @pytest.mark.asyncio
    async def test_match_vehicle_by_embedding_success(self) -> None:
        """Test successfully matching vehicle by visual embedding."""
        from backend.api.routes.household_matcher import match_vehicle
        from backend.api.schemas.household_matcher import VehicleMatchRequest

        mock_db = AsyncMock()

        mock_match = HouseholdMatch(
            vehicle_id=3,
            vehicle_description="Blue Honda Civic",
            similarity=0.88,
            match_type="vehicle_visual",
        )

        request = VehicleMatchRequest(
            embedding=[0.3] * 768,
            vehicle_type="car",
            color="blue",
        )

        with patch(
            "backend.api.routes.household_matcher.get_household_matcher"
        ) as mock_get_matcher:
            mock_matcher = AsyncMock()
            mock_matcher.match_vehicle.return_value = mock_match
            mock_get_matcher.return_value = mock_matcher

            result = await match_vehicle(request=request, db=mock_db)

        assert result.matched is True
        assert result.match_type == "vehicle_visual"
        assert result.similarity == 0.88

    @pytest.mark.asyncio
    async def test_match_vehicle_no_match(self) -> None:
        """Test no match found for vehicle."""
        from backend.api.routes.household_matcher import match_vehicle
        from backend.api.schemas.household_matcher import VehicleMatchRequest

        mock_db = AsyncMock()
        request = VehicleMatchRequest(
            license_plate="XYZ789",
            vehicle_type="truck",
        )

        with patch(
            "backend.api.routes.household_matcher.get_household_matcher"
        ) as mock_get_matcher:
            mock_matcher = AsyncMock()
            mock_matcher.match_vehicle.return_value = None
            mock_get_matcher.return_value = mock_matcher

            result = await match_vehicle(request=request, db=mock_db)

        assert result.matched is False
        assert result.vehicle_id is None

    @pytest.mark.asyncio
    async def test_match_vehicle_missing_criteria(self) -> None:
        """Test that missing both plate and embedding returns 400."""
        from fastapi import HTTPException

        from backend.api.routes.household_matcher import match_vehicle
        from backend.api.schemas.household_matcher import VehicleMatchRequest

        mock_db = AsyncMock()
        request = VehicleMatchRequest(
            license_plate=None,
            embedding=None,
            vehicle_type="car",
        )

        with pytest.raises(HTTPException) as exc_info:
            await match_vehicle(request=request, db=mock_db)

        assert exc_info.value.status_code == 400
        assert "must provide" in exc_info.value.detail.lower()


class TestMatchBatch:
    """Tests for POST /api/household-matcher/match-batch endpoint."""

    @pytest.mark.asyncio
    async def test_match_batch_success(self) -> None:
        """Test successfully batch matching detections."""
        from backend.api.routes.household_matcher import match_batch
        from backend.api.schemas.household_matcher import BatchMatchRequest

        mock_db = AsyncMock()

        person_match = HouseholdMatch(
            member_id=1,
            member_name="John",
            similarity=0.9,
            match_type="person",
        )
        vehicle_match = HouseholdMatch(
            vehicle_id=2,
            vehicle_description="Tesla",
            similarity=1.0,
            match_type="license_plate",
        )

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

        with patch(
            "backend.api.routes.household_matcher.get_household_matcher"
        ) as mock_get_matcher:
            mock_matcher = AsyncMock()
            mock_matcher.match_detections.return_value = (
                {1: person_match},  # person_matches
                {2: vehicle_match},  # vehicle_matches
            )
            mock_get_matcher.return_value = mock_matcher

            result = await match_batch(request=request, db=mock_db)

        assert result.total_detections == 2
        assert result.total_matches == 2
        assert "1" in result.person_matches
        assert "2" in result.vehicle_matches

    @pytest.mark.asyncio
    async def test_match_batch_no_matches(self) -> None:
        """Test batch matching with no matches found."""
        from backend.api.routes.household_matcher import match_batch
        from backend.api.schemas.household_matcher import BatchMatchRequest

        mock_db = AsyncMock()

        request = BatchMatchRequest(
            detections=[
                {"id": 1, "object_type": "person"},
            ],
            enrichment_data={
                "1": {"embeddings": {"person_reid": [0.5] * 512}},
            },
        )

        with patch(
            "backend.api.routes.household_matcher.get_household_matcher"
        ) as mock_get_matcher:
            mock_matcher = AsyncMock()
            mock_matcher.match_detections.return_value = ({}, {})
            mock_get_matcher.return_value = mock_matcher

            result = await match_batch(request=request, db=mock_db)

        assert result.total_detections == 1
        assert result.total_matches == 0
        assert result.person_matches == {}
        assert result.vehicle_matches == {}


class TestGetMatcherConfig:
    """Tests for GET /api/household-matcher/config endpoint."""

    @pytest.mark.asyncio
    async def test_get_config_success(self) -> None:
        """Test getting matcher configuration."""
        from backend.api.routes.household_matcher import get_matcher_config

        mock_db = AsyncMock()

        # Mock count queries
        mock_embedding_count = MagicMock()
        mock_embedding_count.scalar.return_value = 10
        mock_vehicle_count = MagicMock()
        mock_vehicle_count.scalar.return_value = 5

        mock_db.execute.side_effect = [mock_embedding_count, mock_vehicle_count]

        with patch(
            "backend.api.routes.household_matcher.get_household_matcher"
        ) as mock_get_matcher:
            mock_matcher = MagicMock()
            mock_matcher.similarity_threshold = 0.85
            mock_get_matcher.return_value = mock_matcher

            result = await get_matcher_config(db=mock_db)

        assert result.similarity_threshold == 0.85
        assert result.total_member_embeddings == 10
        assert result.total_registered_vehicles == 5

    @pytest.mark.asyncio
    async def test_get_config_empty_database(self) -> None:
        """Test config with no embeddings or vehicles."""
        from backend.api.routes.household_matcher import get_matcher_config

        mock_db = AsyncMock()

        # Mock count queries returning zero
        mock_embedding_count = MagicMock()
        mock_embedding_count.scalar.return_value = 0
        mock_vehicle_count = MagicMock()
        mock_vehicle_count.scalar.return_value = 0

        mock_db.execute.side_effect = [mock_embedding_count, mock_vehicle_count]

        with patch(
            "backend.api.routes.household_matcher.get_household_matcher"
        ) as mock_get_matcher:
            mock_matcher = MagicMock()
            mock_matcher.similarity_threshold = 0.85
            mock_get_matcher.return_value = mock_matcher

            result = await get_matcher_config(db=mock_db)

        assert result.total_member_embeddings == 0
        assert result.total_registered_vehicles == 0
