"""Unit tests for Household Matcher API routes.

Tests the API endpoints for Household Matcher service (NEM-4934).

The person endpoint is RETIRED (D-1, F11 re-ID full swap): after the swap
every stored vector names its model_id and a client-posted list of floats
carries none, so matching happens only where the server computes the
vector. Its pins are retirement pins now — the face client-vector
enrollment pair (test_face_enrollment_provenance.py) is the precedent.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.api.routes import household_matcher as hm
from backend.services.household_matcher import HouseholdMatch


class TestMatchPersonRetired:
    """POST /api/household-matcher/match-person answers 410 Gone, always."""

    @pytest.mark.asyncio
    async def test_endpoint_answers_gone(self) -> None:
        """A posted vector is refused before anything is compared — a
        client-claimed model_id is no trust anchor, so there is no
        threshold, no gallery read, no score."""
        from backend.api.schemas.household_matcher import PersonMatchRequest

        with pytest.raises(HTTPException) as exc_info:
            await hm.match_person(request=PersonMatchRequest(embedding=[0.1] * 512), db=AsyncMock())

        assert exc_info.value.status_code == 410

    def test_gone_detail_names_the_server_side_paths(self) -> None:
        """The refusal tells the caller where matching DOES happen."""
        source = "\n".join(hm.match_person.__doc__.split())
        assert "person_reid" in source
        assert "/api/household/members/{member_id}/embeddings" in source

    def test_route_registered_deprecated_with_410(self) -> None:
        """OpenAPI shows the retirement: deprecated + the 410 response."""
        route = next(
            r
            for r in hm.router.routes
            if getattr(r, "path", None) == "/api/household-matcher/match-person"
        )
        assert route.deprecated is True
        assert 410 in route.responses or "410" in route.responses


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
            "backend.api.routes.household_matcher.get_household_matcher", autospec=True
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
            "backend.api.routes.household_matcher.get_household_matcher", autospec=True
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
            "backend.api.routes.household_matcher.get_household_matcher", autospec=True
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
            "backend.api.routes.household_matcher.get_household_matcher", autospec=True
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
            "backend.api.routes.household_matcher.get_household_matcher", autospec=True
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
            "backend.api.routes.household_matcher.get_household_matcher", autospec=True
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
            "backend.api.routes.household_matcher.get_household_matcher", autospec=True
        ) as mock_get_matcher:
            mock_matcher = MagicMock()
            mock_matcher.similarity_threshold = 0.85
            mock_get_matcher.return_value = mock_matcher

            result = await get_matcher_config(db=mock_db)

        assert result.total_member_embeddings == 0
        assert result.total_registered_vehicles == 0
