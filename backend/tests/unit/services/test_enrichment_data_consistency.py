"""TDD tests for enrichment data consistency (NEM-5488).

These tests are written FIRST (red phase) to verify that:
1. VehicleClassificationResult.to_dict() includes all fields (display_name, is_commercial, all_scores)
2. Storage dict matches prompt content (no data loss between runtime and storage paths)
3. New to_storage_dict() method uses to_dict() methods on result classes
4. get_enrichment_for_detection() raises DeprecationWarning
5. Missing to_dict() methods are added to HouseholdMatch, EntityMatch, LicensePlateResult, FaceResult, SceneChangeResult

Problem Summary:
- get_enrichment_for_detection() (lines 1555-1684) manually constructs dicts, losing fields
- VehicleClassificationResult loses: display_name, is_commercial, all_scores
- Runtime path (prompt generation) uses full objects with all fields
- Storage path uses simplified dict missing critical fields
- Result classes like HouseholdMatch, EntityMatch, LicensePlateResult lack to_dict() methods
"""

from __future__ import annotations

import warnings
from datetime import datetime

import pytest

from backend.services.enrichment_pipeline import (
    BoundingBox,
    EnrichmentResult,
    FaceResult,
    LicensePlateResult,
)
from backend.services.household_matcher import HouseholdMatch
from backend.services.pet_classifier_loader import PetClassificationResult
from backend.services.reid_service import EntityEmbedding, EntityMatch
from backend.services.scene_change_detector import SceneChangeResult
from backend.services.vehicle_classifier_loader import VehicleClassificationResult

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def vehicle_classification_result() -> VehicleClassificationResult:
    """Create a VehicleClassificationResult with all fields populated."""
    return VehicleClassificationResult(
        vehicle_type="bus",
        display_name="School Bus",
        confidence=0.92,
        is_commercial=True,
        all_scores={"bus": 0.92, "truck": 0.05, "car": 0.03},
    )


@pytest.fixture
def pet_classification_result() -> PetClassificationResult:
    """Create a PetClassificationResult with all fields populated.

    Note: PetClassificationResult from pet_classifier_loader uses animal_type,
    cat_score, dog_score (not breed/all_scores). The current storage method
    loses these scores and sets breed to None even though it could derive
    breed information from the classifier.
    """
    return PetClassificationResult(
        animal_type="dog",
        confidence=0.88,
        cat_score=0.12,
        dog_score=0.88,
        is_household_pet=True,
    )


@pytest.fixture
def license_plate_result() -> LicensePlateResult:
    """Create a LicensePlateResult with all fields populated."""
    return LicensePlateResult(
        bbox=BoundingBox(x1=100, y1=200, x2=200, y2=230),
        text="ABC1234",
        confidence=0.95,
        ocr_confidence=0.91,
        source_detection_id=1,
    )


@pytest.fixture
def face_result() -> FaceResult:
    """Create a FaceResult with all fields populated."""
    return FaceResult(
        bbox=BoundingBox(x1=50, y1=60, x2=120, y2=150),
        confidence=0.89,
        source_detection_id=2,
    )


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


@pytest.fixture
def enrichment_result_with_vehicle(
    vehicle_classification_result: VehicleClassificationResult,
) -> EnrichmentResult:
    """Create an EnrichmentResult with vehicle classification."""
    result = EnrichmentResult()
    result.vehicle_classifications["1"] = vehicle_classification_result
    return result


@pytest.fixture
def enrichment_result_with_pet(
    pet_classification_result: PetClassificationResult,
) -> EnrichmentResult:
    """Create an EnrichmentResult with pet classification."""
    result = EnrichmentResult()
    result.pet_classifications["3"] = pet_classification_result
    return result


@pytest.fixture
def enrichment_result_complete(
    vehicle_classification_result: VehicleClassificationResult,
    pet_classification_result: PetClassificationResult,
    license_plate_result: LicensePlateResult,
    face_result: FaceResult,
    household_match_person: HouseholdMatch,
    household_match_vehicle: HouseholdMatch,
) -> EnrichmentResult:
    """Create a fully populated EnrichmentResult."""
    result = EnrichmentResult()
    result.vehicle_classifications["1"] = vehicle_classification_result
    result.pet_classifications["3"] = pet_classification_result
    result.license_plates.append(license_plate_result)
    result.faces.append(face_result)
    # NEM-5512/5513/5514: Household matches are now dicts keyed by detection ID
    result.person_household_matches[1] = household_match_person
    result.vehicle_household_matches[2] = household_match_vehicle
    return result


# =============================================================================
# VehicleClassificationResult.to_dict() Tests
# =============================================================================


class TestVehicleClassificationToDict:
    """Tests for VehicleClassificationResult.to_dict() including all fields."""

    def test_to_dict_includes_display_name(
        self, vehicle_classification_result: VehicleClassificationResult
    ) -> None:
        """Verify to_dict() includes display_name field.

        The display_name provides human-readable vehicle type (e.g., "School Bus")
        which is used in prompts but currently lost in storage path.
        """
        d = vehicle_classification_result.to_dict()

        assert "display_name" in d, "display_name field must be included in to_dict()"
        assert d["display_name"] == "School Bus"

    def test_to_dict_includes_is_commercial(
        self, vehicle_classification_result: VehicleClassificationResult
    ) -> None:
        """Verify to_dict() includes is_commercial field.

        is_commercial flag identifies commercial/delivery vehicles which
        affects risk assessment but is currently lost in storage.
        """
        d = vehicle_classification_result.to_dict()

        assert "is_commercial" in d, "is_commercial field must be included in to_dict()"
        assert d["is_commercial"] is True

    def test_to_dict_includes_all_scores(
        self, vehicle_classification_result: VehicleClassificationResult
    ) -> None:
        """Verify to_dict() includes all_scores field.

        all_scores provides classification alternatives that help assess
        confidence and are used in detailed analysis but lost in storage.
        """
        d = vehicle_classification_result.to_dict()

        assert "all_scores" in d, "all_scores field must be included in to_dict()"
        assert d["all_scores"] == {"bus": 0.92, "truck": 0.05, "car": 0.03}

    def test_to_dict_includes_vehicle_type(
        self, vehicle_classification_result: VehicleClassificationResult
    ) -> None:
        """Verify to_dict() includes basic vehicle_type field."""
        d = vehicle_classification_result.to_dict()

        assert "vehicle_type" in d
        assert d["vehicle_type"] == "bus"

    def test_to_dict_includes_confidence(
        self, vehicle_classification_result: VehicleClassificationResult
    ) -> None:
        """Verify to_dict() includes confidence field."""
        d = vehicle_classification_result.to_dict()

        assert "confidence" in d
        assert d["confidence"] == 0.92


# =============================================================================
# Storage Dict vs Prompt Content Tests
# =============================================================================


class TestStorageDictMatchesPromptContent:
    """Tests verifying stored enrichment contains same data used in prompt."""

    def test_storage_dict_includes_vehicle_display_name(
        self, enrichment_result_with_vehicle: EnrichmentResult
    ) -> None:
        """Verify stored enrichment contains vehicle display_name.

        Currently get_enrichment_for_detection() loses display_name when
        creating the storage dict. This test will FAIL until fixed.
        """
        # Get storage dict using the new method (to be implemented)
        stored = enrichment_result_with_vehicle.to_storage_dict(detection_id=1)

        assert "vehicle" in stored
        assert "display_name" in stored["vehicle"], (
            "Storage dict must include display_name to match prompt content"
        )
        assert stored["vehicle"]["display_name"] == "School Bus"

    def test_storage_dict_includes_vehicle_is_commercial(
        self, enrichment_result_with_vehicle: EnrichmentResult
    ) -> None:
        """Verify stored enrichment contains vehicle is_commercial flag."""
        stored = enrichment_result_with_vehicle.to_storage_dict(detection_id=1)

        assert "vehicle" in stored
        assert "is_commercial" in stored["vehicle"], (
            "Storage dict must include is_commercial to match prompt content"
        )
        assert stored["vehicle"]["is_commercial"] is True

    def test_storage_dict_includes_vehicle_all_scores(
        self, enrichment_result_with_vehicle: EnrichmentResult
    ) -> None:
        """Verify stored enrichment contains vehicle all_scores."""
        stored = enrichment_result_with_vehicle.to_storage_dict(detection_id=1)

        assert "vehicle" in stored
        assert "all_scores" in stored["vehicle"], (
            "Storage dict must include all_scores to match prompt content"
        )

    def test_storage_dict_includes_pet_cat_dog_scores(
        self, enrichment_result_with_pet: EnrichmentResult
    ) -> None:
        """Verify stored enrichment contains pet cat_score and dog_score.

        get_enrichment_for_detection() currently loses cat_score/dog_score
        which are needed for confidence analysis and debugging.
        """
        stored = enrichment_result_with_pet.to_storage_dict(detection_id=3)

        assert "pet" in stored
        assert "cat_score" in stored["pet"], "Storage dict must include cat_score"
        assert "dog_score" in stored["pet"], "Storage dict must include dog_score"
        assert stored["pet"]["cat_score"] == 0.12
        assert stored["pet"]["dog_score"] == 0.88

    def test_storage_dict_includes_pet_is_household_pet(
        self, enrichment_result_with_pet: EnrichmentResult
    ) -> None:
        """Verify stored enrichment contains is_household_pet flag."""
        stored = enrichment_result_with_pet.to_storage_dict(detection_id=3)

        assert "pet" in stored
        assert "is_household_pet" in stored["pet"], "Storage dict must include is_household_pet"
        assert stored["pet"]["is_household_pet"] is True

    def test_old_method_returns_incomplete_vehicle_data(
        self, enrichment_result_with_vehicle: EnrichmentResult
    ) -> None:
        """Document that old get_enrichment_for_detection() loses data.

        This test documents the current broken behavior. It passes today
        but serves as documentation of the bug being fixed.
        """
        # Suppress the deprecation warning for this test
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            old_result = enrichment_result_with_vehicle.get_enrichment_for_detection(1)

        # Old method loses these fields - this documents the bug
        assert old_result is not None
        assert "vehicle" in old_result
        # These assertions document what the OLD method returns (incomplete)
        assert "display_name" not in old_result["vehicle"], (
            "Old method is known to lose display_name"
        )
        assert "is_commercial" not in old_result["vehicle"], (
            "Old method is known to lose is_commercial"
        )
        assert "all_scores" not in old_result["vehicle"], "Old method is known to lose all_scores"


# =============================================================================
# to_storage_dict() Method Tests
# =============================================================================


class TestToStorageDictUsesToDictMethods:
    """Tests verifying new to_storage_dict() properly uses to_dict() methods."""

    def test_to_storage_dict_method_exists(
        self, enrichment_result_with_vehicle: EnrichmentResult
    ) -> None:
        """Verify EnrichmentResult has to_storage_dict() method."""
        assert hasattr(enrichment_result_with_vehicle, "to_storage_dict"), (
            "EnrichmentResult must have to_storage_dict() method"
        )
        assert callable(enrichment_result_with_vehicle.to_storage_dict)

    def test_to_storage_dict_uses_vehicle_to_dict(
        self, enrichment_result_with_vehicle: EnrichmentResult
    ) -> None:
        """Verify to_storage_dict() delegates to VehicleClassificationResult.to_dict().

        The new method should call to_dict() on result objects rather than
        manually extracting fields, ensuring all fields are preserved.
        """
        # Mock the to_dict method to verify it's called
        original_vc = enrichment_result_with_vehicle.vehicle_classifications["1"]

        # Get storage dict
        stored = enrichment_result_with_vehicle.to_storage_dict(detection_id=1)

        # Verify vehicle data matches what to_dict() returns
        expected_vehicle = original_vc.to_dict()
        assert stored["vehicle"]["vehicle_type"] == expected_vehicle["vehicle_type"]
        assert stored["vehicle"]["display_name"] == expected_vehicle["display_name"]
        assert stored["vehicle"]["confidence"] == expected_vehicle["confidence"]
        assert stored["vehicle"]["is_commercial"] == expected_vehicle["is_commercial"]
        assert stored["vehicle"]["all_scores"] == expected_vehicle["all_scores"]

    def test_to_storage_dict_returns_none_when_empty(self) -> None:
        """Verify to_storage_dict() returns None when no enrichment data."""
        result = EnrichmentResult()
        stored = result.to_storage_dict(detection_id=999)

        assert stored is None, "Should return None when no enrichment data"


# =============================================================================
# Deprecation Warning Tests
# =============================================================================


class TestDeprecationWarning:
    """Tests for deprecation warning on old get_enrichment_for_detection()."""

    def test_get_enrichment_for_detection_raises_deprecation_warning(
        self, enrichment_result_with_vehicle: EnrichmentResult
    ) -> None:
        """Verify old method raises DeprecationWarning.

        Once to_storage_dict() is implemented, get_enrichment_for_detection()
        should warn users to migrate to the new method.
        """
        with pytest.warns(DeprecationWarning, match="use to_storage_dict"):
            enrichment_result_with_vehicle.get_enrichment_for_detection(1)

    def test_deprecation_warning_message_includes_migration_path(
        self, enrichment_result_with_vehicle: EnrichmentResult
    ) -> None:
        """Verify deprecation warning includes clear migration path."""
        with pytest.warns(DeprecationWarning) as warning_info:
            enrichment_result_with_vehicle.get_enrichment_for_detection(1)

        warning_message = str(warning_info[0].message)
        assert "to_storage_dict" in warning_message, "Warning must mention the replacement method"


# =============================================================================
# Missing to_dict() Method Tests
# =============================================================================


class TestHouseholdMatchToDict:
    """Tests for HouseholdMatch.to_dict() method (currently missing)."""

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
    """Tests for EntityMatch.to_dict() method (currently missing)."""

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


class TestLicensePlateResultToDict:
    """Tests for LicensePlateResult.to_dict() method (currently missing)."""

    def test_license_plate_result_has_to_dict_method(
        self, license_plate_result: LicensePlateResult
    ) -> None:
        """Verify LicensePlateResult has to_dict() method."""
        assert hasattr(license_plate_result, "to_dict"), (
            "LicensePlateResult must have to_dict() method for serialization"
        )
        assert callable(license_plate_result.to_dict)

    def test_license_plate_to_dict_includes_text(
        self, license_plate_result: LicensePlateResult
    ) -> None:
        """Verify to_dict() includes plate text."""
        d = license_plate_result.to_dict()
        assert "text" in d
        assert d["text"] == "ABC1234"

    def test_license_plate_to_dict_includes_confidence(
        self, license_plate_result: LicensePlateResult
    ) -> None:
        """Verify to_dict() includes detection confidence."""
        d = license_plate_result.to_dict()
        assert "confidence" in d
        assert d["confidence"] == 0.95

    def test_license_plate_to_dict_includes_ocr_confidence(
        self, license_plate_result: LicensePlateResult
    ) -> None:
        """Verify to_dict() includes OCR confidence."""
        d = license_plate_result.to_dict()
        assert "ocr_confidence" in d
        assert d["ocr_confidence"] == 0.91

    def test_license_plate_to_dict_includes_source_detection_id(
        self, license_plate_result: LicensePlateResult
    ) -> None:
        """Verify to_dict() includes source detection ID."""
        d = license_plate_result.to_dict()
        assert "source_detection_id" in d
        assert d["source_detection_id"] == 1

    def test_license_plate_to_dict_includes_bbox(
        self, license_plate_result: LicensePlateResult
    ) -> None:
        """Verify to_dict() includes bounding box."""
        d = license_plate_result.to_dict()
        assert "bbox" in d
        # BoundingBox should be serialized as dict
        assert d["bbox"]["x1"] == 100
        assert d["bbox"]["y1"] == 200
        assert d["bbox"]["x2"] == 200
        assert d["bbox"]["y2"] == 230


class TestFaceResultToDict:
    """Tests for FaceResult.to_dict() method (currently missing)."""

    def test_face_result_has_to_dict_method(self, face_result: FaceResult) -> None:
        """Verify FaceResult has to_dict() method."""
        assert hasattr(face_result, "to_dict"), (
            "FaceResult must have to_dict() method for serialization"
        )
        assert callable(face_result.to_dict)

    def test_face_result_to_dict_includes_confidence(self, face_result: FaceResult) -> None:
        """Verify to_dict() includes detection confidence."""
        d = face_result.to_dict()
        assert "confidence" in d
        assert d["confidence"] == 0.89

    def test_face_result_to_dict_includes_source_detection_id(
        self, face_result: FaceResult
    ) -> None:
        """Verify to_dict() includes source detection ID."""
        d = face_result.to_dict()
        assert "source_detection_id" in d
        assert d["source_detection_id"] == 2

    def test_face_result_to_dict_includes_bbox(self, face_result: FaceResult) -> None:
        """Verify to_dict() includes bounding box."""
        d = face_result.to_dict()
        assert "bbox" in d
        assert d["bbox"]["x1"] == 50
        assert d["bbox"]["y1"] == 60


class TestSceneChangeResultToDict:
    """Tests for SceneChangeResult.to_dict() method (currently missing)."""

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


# =============================================================================
# Integration-Style Tests for Data Round-Trip
# =============================================================================


class TestEnrichmentDataRoundTrip:
    """Tests for complete data round-trip through storage and retrieval."""

    def test_vehicle_classification_round_trip_preserves_all_fields(
        self,
        enrichment_result_with_vehicle: EnrichmentResult,
        vehicle_classification_result: VehicleClassificationResult,
    ) -> None:
        """Verify storing and retrieving vehicle classification preserves all fields.

        This test simulates the full flow:
        1. Create EnrichmentResult with VehicleClassificationResult
        2. Serialize to storage dict
        3. Verify all original fields are present
        """
        stored = enrichment_result_with_vehicle.to_storage_dict(detection_id=1)

        original = vehicle_classification_result
        assert stored["vehicle"]["vehicle_type"] == original.vehicle_type
        assert stored["vehicle"]["display_name"] == original.display_name
        assert stored["vehicle"]["confidence"] == original.confidence
        assert stored["vehicle"]["is_commercial"] == original.is_commercial
        assert stored["vehicle"]["all_scores"] == original.all_scores

    def test_complete_enrichment_round_trip(
        self, enrichment_result_complete: EnrichmentResult
    ) -> None:
        """Verify complete EnrichmentResult serializes all data correctly.

        Tests that a fully populated EnrichmentResult preserves all
        enrichment data through the storage path.
        """
        # Test vehicle detection (id=1)
        vehicle_stored = enrichment_result_complete.to_storage_dict(detection_id=1)
        assert vehicle_stored is not None
        assert "vehicle" in vehicle_stored
        assert vehicle_stored["vehicle"]["display_name"] == "School Bus"
        assert vehicle_stored["vehicle"]["is_commercial"] is True

        # Test person detection (id=2) - has face
        person_stored = enrichment_result_complete.to_storage_dict(detection_id=2)
        assert person_stored is not None
        assert person_stored.get("face_detected") is True

        # Test pet detection (id=3)
        pet_stored = enrichment_result_complete.to_storage_dict(detection_id=3)
        assert pet_stored is not None
        assert "pet" in pet_stored
        assert pet_stored["pet"]["animal_type"] == "dog"
        assert pet_stored["pet"]["cat_score"] == 0.12
        assert pet_stored["pet"]["dog_score"] == 0.88


class TestNemotronReceivesSameDataAsStorage:
    """Tests verifying prompt content matches stored data."""

    def test_vehicle_prompt_data_matches_storage(
        self,
        enrichment_result_with_vehicle: EnrichmentResult,
        vehicle_classification_result: VehicleClassificationResult,
    ) -> None:
        """Verify data used in Nemotron prompt matches what gets stored.

        The prompt generation uses to_context_string() which includes display_name
        and is_commercial, but storage currently loses these fields.
        """
        # What prompt sees (via to_context_string())
        prompt_context = vehicle_classification_result.to_context_string()

        # What storage sees
        stored = enrichment_result_with_vehicle.to_storage_dict(detection_id=1)

        # If display_name is "School Bus", it should appear in both
        assert "School Bus" in prompt_context, "Prompt context should include display_name"
        assert stored["vehicle"]["display_name"] == "School Bus", (
            "Storage should also include display_name"
        )

        # If is_commercial, it should appear in both
        assert "Commercial" in prompt_context, "Prompt context should indicate commercial vehicle"
        assert stored["vehicle"]["is_commercial"] is True, (
            "Storage should also indicate commercial vehicle"
        )


# =============================================================================
# BoundingBox.to_dict() Tests (may already exist, but needed for other to_dict)
# =============================================================================


class TestBoundingBoxToDict:
    """Tests for BoundingBox.to_dict() method needed by other to_dict() methods."""

    def test_bounding_box_has_to_dict_method(self) -> None:
        """Verify BoundingBox has to_dict() method."""
        bbox = BoundingBox(x1=10, y1=20, x2=100, y2=200)
        assert hasattr(bbox, "to_dict"), (
            "BoundingBox must have to_dict() method for nested serialization"
        )

    def test_bounding_box_to_dict_includes_all_coordinates(self) -> None:
        """Verify to_dict() includes all coordinate fields."""
        bbox = BoundingBox(x1=10.5, y1=20.5, x2=100.5, y2=200.5, confidence=0.95)
        d = bbox.to_dict()

        assert d["x1"] == 10.5
        assert d["y1"] == 20.5
        assert d["x2"] == 100.5
        assert d["y2"] == 200.5
        assert d["confidence"] == 0.95
