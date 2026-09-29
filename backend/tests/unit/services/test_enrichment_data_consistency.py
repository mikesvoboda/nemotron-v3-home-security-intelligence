"""Unit tests for the stored-serialization contract of the match/result dataclasses.

This file was the NEM-5488 "enrichment data consistency" suite: it pinned
that every enrichment result class carries a to_dict() whose fields match
what the storage path writes. R8 S2 deleted the enrichment tier, so the
half of the suite that drove EnrichmentResult.to_storage_dict(), the two
classifier-loader result classes (vehicle_classifier_loader,
pet_classifier_loader) and the enrichment_pipeline value objects
(BoundingBox / FaceResult / LicensePlateResult) lost their subjects and
went with the module — there is no storage dict left to be consistent with.

What remains is the part of that contract that outlived the tier: the three
dataclasses still shipped (HouseholdMatch, EntityMatch, SceneChangeResult),
whose to_dict() is what their owner modules document and no other suite pins.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from backend.services.household_matcher import HouseholdMatch
from backend.services.reid_service import EntityEmbedding, EntityMatch
from backend.services.scene_change_detector import SceneChangeResult

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def scene_change_result() -> SceneChangeResult:
    """Create a SceneChangeResult with all fields populated."""
    return SceneChangeResult(
        change_detected=True,
        similarity_score=0.75,
        is_first_frame=False,
    )


@pytest.fixture
def household_match_person() -> HouseholdMatch:
    """Create a HouseholdMatch for a person."""
    return HouseholdMatch(
        member_id=42,
        member_name="John Doe",
        vehicle_id=None,
        vehicle_description=None,
        similarity=0.87,
        match_type="person",
        member_role="resident",
        schedule_status=True,
    )


@pytest.fixture
def household_match_vehicle() -> HouseholdMatch:
    """Create a HouseholdMatch for a vehicle."""
    return HouseholdMatch(
        member_id=None,
        member_name=None,
        vehicle_id=101,
        vehicle_description="Silver Honda Accord",
        similarity=1.0,
        match_type="license_plate",
        member_role=None,
        schedule_status=None,
    )


@pytest.fixture
def entity_embedding() -> EntityEmbedding:
    """Create an EntityEmbedding for testing EntityMatch."""
    return EntityEmbedding(
        entity_type="person",
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
        camera_id="camera_01",
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        detection_id="det_123",
        attributes={"clothing_color": "blue"},
    )


@pytest.fixture
def entity_match(entity_embedding: EntityEmbedding) -> EntityMatch:
    """Create an EntityMatch with all fields populated."""
    return EntityMatch(
        entity=entity_embedding,
        similarity=0.92,
        time_gap_seconds=3600.0,
    )


# =============================================================================
# Surviving to_dict() Contracts
# =============================================================================


class TestHouseholdMatchToDict:
    """Tests for HouseholdMatch.to_dict() (household_matcher.py)."""

    def test_household_match_has_to_dict_method(
        self, household_match_person: HouseholdMatch
    ) -> None:
        """Verify HouseholdMatch has to_dict() method."""
        assert hasattr(household_match_person, "to_dict"), (
            "HouseholdMatch must have to_dict() method for serialization"
        )
        assert callable(household_match_person.to_dict)

    def test_household_match_to_dict_includes_member_id(
        self, household_match_person: HouseholdMatch
    ) -> None:
        """Verify to_dict() includes member_id."""
        d = household_match_person.to_dict()
        assert "member_id" in d
        assert d["member_id"] == 42

    def test_household_match_to_dict_includes_member_name(
        self, household_match_person: HouseholdMatch
    ) -> None:
        """Verify to_dict() includes member_name."""
        d = household_match_person.to_dict()
        assert "member_name" in d
        assert d["member_name"] == "John Doe"

    def test_household_match_to_dict_includes_similarity(
        self, household_match_person: HouseholdMatch
    ) -> None:
        """Verify to_dict() includes similarity."""
        d = household_match_person.to_dict()
        assert "similarity" in d
        assert d["similarity"] == 0.87

    def test_household_match_to_dict_includes_match_type(
        self, household_match_person: HouseholdMatch
    ) -> None:
        """Verify to_dict() includes match_type."""
        d = household_match_person.to_dict()
        assert "match_type" in d
        assert d["match_type"] == "person"

    def test_household_match_to_dict_includes_member_role(
        self, household_match_person: HouseholdMatch
    ) -> None:
        """Verify to_dict() includes member_role."""
        d = household_match_person.to_dict()
        assert "member_role" in d
        assert d["member_role"] == "resident"

    def test_household_match_to_dict_includes_schedule_status(
        self, household_match_person: HouseholdMatch
    ) -> None:
        """Verify to_dict() includes schedule_status."""
        d = household_match_person.to_dict()
        assert "schedule_status" in d
        assert d["schedule_status"] is True

    def test_household_match_vehicle_to_dict(self, household_match_vehicle: HouseholdMatch) -> None:
        """Verify vehicle HouseholdMatch serializes correctly."""
        d = household_match_vehicle.to_dict()

        assert d["vehicle_id"] == 101
        assert d["vehicle_description"] == "Silver Honda Accord"
        assert d["match_type"] == "license_plate"
        assert d["similarity"] == 1.0


class TestEntityMatchToDict:
    """Tests for EntityMatch.to_dict() (reid_service.py)."""

    def test_entity_match_has_to_dict_method(self, entity_match: EntityMatch) -> None:
        """Verify EntityMatch has to_dict() method."""
        assert hasattr(entity_match, "to_dict"), (
            "EntityMatch must have to_dict() method for serialization"
        )
        assert callable(entity_match.to_dict)

    def test_entity_match_to_dict_includes_similarity(self, entity_match: EntityMatch) -> None:
        """Verify to_dict() includes similarity score."""
        d = entity_match.to_dict()
        assert "similarity" in d
        assert d["similarity"] == 0.92

    def test_entity_match_to_dict_includes_time_gap(self, entity_match: EntityMatch) -> None:
        """Verify to_dict() includes time_gap_seconds."""
        d = entity_match.to_dict()
        assert "time_gap_seconds" in d
        assert d["time_gap_seconds"] == 3600.0

    def test_entity_match_to_dict_includes_entity_data(self, entity_match: EntityMatch) -> None:
        """Verify to_dict() includes nested entity data."""
        d = entity_match.to_dict()
        assert "entity" in d
        # Entity should use its own to_dict()
        assert "entity_type" in d["entity"]
        assert d["entity"]["entity_type"] == "person"
        assert "camera_id" in d["entity"]
        assert d["entity"]["camera_id"] == "camera_01"


class TestSceneChangeResultToDict:
    """Tests for SceneChangeResult.to_dict() (scene_change_detector.py)."""

    def test_scene_change_result_has_to_dict_method(
        self, scene_change_result: SceneChangeResult
    ) -> None:
        """Verify SceneChangeResult has to_dict() method."""
        assert hasattr(scene_change_result, "to_dict"), (
            "SceneChangeResult must have to_dict() method for serialization"
        )
        assert callable(scene_change_result.to_dict)

    def test_scene_change_to_dict_includes_change_detected(
        self, scene_change_result: SceneChangeResult
    ) -> None:
        """Verify to_dict() includes change_detected flag."""
        d = scene_change_result.to_dict()
        assert "change_detected" in d
        assert d["change_detected"] is True

    def test_scene_change_to_dict_includes_similarity_score(
        self, scene_change_result: SceneChangeResult
    ) -> None:
        """Verify to_dict() includes similarity_score."""
        d = scene_change_result.to_dict()
        assert "similarity_score" in d
        assert d["similarity_score"] == 0.75

    def test_scene_change_to_dict_includes_is_first_frame(
        self, scene_change_result: SceneChangeResult
    ) -> None:
        """Verify to_dict() includes is_first_frame flag."""
        d = scene_change_result.to_dict()
        assert "is_first_frame" in d
        assert d["is_first_frame"] is False
