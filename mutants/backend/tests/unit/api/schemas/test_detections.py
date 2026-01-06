"""Unit tests for detection enrichment schemas (NEM-1067).

Tests for the typed enrichment_data schemas in DetectionResponse.
Following TDD: Tests written FIRST before implementation.
"""

from backend.api.routes.detections import validate_enrichment_data
from backend.api.schemas.detections import (
    EnrichmentDataSchema,
    PersonEnrichmentData,
    PetEnrichmentData,
    VehicleEnrichmentData,
)


class TestVehicleEnrichmentData:
    """Tests for VehicleEnrichmentData schema."""

    def test_valid_vehicle_enrichment_all_fields(self):
        """Test creating a valid vehicle enrichment with all fields."""
        vehicle = VehicleEnrichmentData(
            vehicle_type="sedan",
            vehicle_color="blue",
            has_damage=True,
            is_commercial=False,
        )
        assert vehicle.vehicle_type == "sedan"
        assert vehicle.vehicle_color == "blue"
        assert vehicle.has_damage is True
        assert vehicle.is_commercial is False

    def test_vehicle_enrichment_defaults(self):
        """Test vehicle enrichment with default values."""
        vehicle = VehicleEnrichmentData()
        assert vehicle.vehicle_type is None
        assert vehicle.vehicle_color is None
        assert vehicle.has_damage is False
        assert vehicle.is_commercial is False

    def test_vehicle_enrichment_partial_fields(self):
        """Test vehicle enrichment with only some fields."""
        vehicle = VehicleEnrichmentData(vehicle_type="truck")
        assert vehicle.vehicle_type == "truck"
        assert vehicle.vehicle_color is None
        assert vehicle.has_damage is False

    def test_vehicle_enrichment_serialization(self):
        """Test vehicle enrichment serializes correctly."""
        vehicle = VehicleEnrichmentData(
            vehicle_type="suv",
            vehicle_color="red",
            has_damage=False,
            is_commercial=True,
        )
        data = vehicle.model_dump()
        assert data == {
            "vehicle_type": "suv",
            "vehicle_color": "red",
            "has_damage": False,
            "is_commercial": True,
        }

    def test_vehicle_enrichment_from_dict(self):
        """Test creating vehicle enrichment from dict."""
        data = {
            "vehicle_type": "van",
            "vehicle_color": "white",
            "has_damage": True,
            "is_commercial": True,
        }
        vehicle = VehicleEnrichmentData.model_validate(data)
        assert vehicle.vehicle_type == "van"
        assert vehicle.is_commercial is True


class TestPersonEnrichmentData:
    """Tests for PersonEnrichmentData schema."""

    def test_valid_person_enrichment_all_fields(self):
        """Test creating a valid person enrichment with all fields."""
        person = PersonEnrichmentData(
            clothing_description="dark jacket, blue jeans",
            action="walking",
            carrying=["backpack", "phone"],
            is_suspicious=False,
        )
        assert person.clothing_description == "dark jacket, blue jeans"
        assert person.action == "walking"
        assert person.carrying == ["backpack", "phone"]
        assert person.is_suspicious is False

    def test_person_enrichment_defaults(self):
        """Test person enrichment with default values."""
        person = PersonEnrichmentData()
        assert person.clothing_description is None
        assert person.action is None
        assert person.carrying == []
        assert person.is_suspicious is False

    def test_person_enrichment_empty_carrying_list(self):
        """Test person enrichment with explicit empty carrying list."""
        person = PersonEnrichmentData(
            clothing_description="red shirt",
            carrying=[],
        )
        assert person.carrying == []

    def test_person_enrichment_suspicious(self):
        """Test person enrichment with suspicious flag."""
        person = PersonEnrichmentData(
            clothing_description="hoodie, mask",
            is_suspicious=True,
        )
        assert person.is_suspicious is True

    def test_person_enrichment_serialization(self):
        """Test person enrichment serializes correctly."""
        person = PersonEnrichmentData(
            clothing_description="business suit",
            action="standing",
            carrying=["briefcase"],
            is_suspicious=False,
        )
        data = person.model_dump()
        assert data == {
            "clothing_description": "business suit",
            "action": "standing",
            "carrying": ["briefcase"],
            "is_suspicious": False,
        }


class TestPetEnrichmentData:
    """Tests for PetEnrichmentData schema."""

    def test_valid_pet_enrichment_all_fields(self):
        """Test creating a valid pet enrichment with all fields."""
        pet = PetEnrichmentData(
            pet_type="dog",
            breed="golden retriever",
        )
        assert pet.pet_type == "dog"
        assert pet.breed == "golden retriever"

    def test_pet_enrichment_defaults(self):
        """Test pet enrichment with default values."""
        pet = PetEnrichmentData()
        assert pet.pet_type is None
        assert pet.breed is None

    def test_pet_enrichment_type_only(self):
        """Test pet enrichment with only type."""
        pet = PetEnrichmentData(pet_type="cat")
        assert pet.pet_type == "cat"
        assert pet.breed is None

    def test_pet_enrichment_serialization(self):
        """Test pet enrichment serializes correctly."""
        pet = PetEnrichmentData(
            pet_type="dog",
            breed="labrador",
        )
        data = pet.model_dump()
        assert data == {
            "pet_type": "dog",
            "breed": "labrador",
        }


class TestEnrichmentDataSchema:
    """Tests for EnrichmentDataSchema (composite schema)."""

    def test_valid_enrichment_data_all_fields(self):
        """Test creating enrichment data with all fields populated."""
        enrichment = EnrichmentDataSchema(
            vehicle=VehicleEnrichmentData(vehicle_type="sedan", vehicle_color="blue"),
            person=PersonEnrichmentData(clothing_description="jacket", action="walking"),
            pet=PetEnrichmentData(pet_type="dog"),
            weather="sunny",
            errors=[],
        )
        assert enrichment.vehicle is not None
        assert enrichment.vehicle.vehicle_type == "sedan"
        assert enrichment.person is not None
        assert enrichment.person.action == "walking"
        assert enrichment.pet is not None
        assert enrichment.pet.pet_type == "dog"
        assert enrichment.weather == "sunny"
        assert enrichment.errors == []

    def test_enrichment_data_defaults(self):
        """Test enrichment data with default values."""
        enrichment = EnrichmentDataSchema()
        assert enrichment.vehicle is None
        assert enrichment.person is None
        assert enrichment.pet is None
        assert enrichment.weather is None
        assert enrichment.errors == []

    def test_enrichment_data_vehicle_only(self):
        """Test enrichment data with only vehicle data."""
        enrichment = EnrichmentDataSchema(
            vehicle=VehicleEnrichmentData(vehicle_type="truck", is_commercial=True)
        )
        assert enrichment.vehicle is not None
        assert enrichment.vehicle.vehicle_type == "truck"
        assert enrichment.vehicle.is_commercial is True
        assert enrichment.person is None
        assert enrichment.pet is None

    def test_enrichment_data_person_only(self):
        """Test enrichment data with only person data."""
        enrichment = EnrichmentDataSchema(
            person=PersonEnrichmentData(
                clothing_description="red hoodie",
                carrying=["umbrella"],
            )
        )
        assert enrichment.person is not None
        assert enrichment.person.clothing_description == "red hoodie"
        assert enrichment.person.carrying == ["umbrella"]
        assert enrichment.vehicle is None

    def test_enrichment_data_with_errors(self):
        """Test enrichment data with processing errors."""
        enrichment = EnrichmentDataSchema(
            errors=["License plate detection failed", "Face detection timeout"],
        )
        assert len(enrichment.errors) == 2
        assert "License plate detection failed" in enrichment.errors

    def test_enrichment_data_serialization(self):
        """Test enrichment data serializes correctly."""
        enrichment = EnrichmentDataSchema(
            vehicle=VehicleEnrichmentData(vehicle_type="suv"),
            weather="cloudy",
            errors=["test error"],
        )
        data = enrichment.model_dump()
        assert data["vehicle"]["vehicle_type"] == "suv"
        assert data["weather"] == "cloudy"
        assert data["errors"] == ["test error"]
        assert data["person"] is None
        assert data["pet"] is None

    def test_enrichment_data_from_dict(self):
        """Test creating enrichment data from dict (backward compatibility)."""
        data = {
            "vehicle": {
                "vehicle_type": "sedan",
                "vehicle_color": "black",
                "has_damage": False,
                "is_commercial": False,
            },
            "person": {
                "clothing_description": "casual wear",
                "action": "running",
                "carrying": [],
                "is_suspicious": False,
            },
            "pet": None,
            "weather": "rainy",
            "errors": [],
        }
        enrichment = EnrichmentDataSchema.model_validate(data)
        assert enrichment.vehicle is not None
        assert enrichment.vehicle.vehicle_type == "sedan"
        assert enrichment.person is not None
        assert enrichment.person.action == "running"
        assert enrichment.weather == "rainy"

    def test_enrichment_data_from_dict_nested_models(self):
        """Test creating enrichment data with nested model dicts."""
        data = {
            "vehicle": {"vehicle_type": "van"},
            "person": {"clothing_description": "uniform"},
        }
        enrichment = EnrichmentDataSchema.model_validate(data)
        assert enrichment.vehicle is not None
        assert enrichment.person is not None

    def test_enrichment_data_exclude_none_serialization(self):
        """Test enrichment data serializes with exclude_none option."""
        enrichment = EnrichmentDataSchema(
            vehicle=VehicleEnrichmentData(vehicle_type="car"),
        )
        data = enrichment.model_dump(exclude_none=True)
        assert "person" not in data
        assert "pet" not in data
        assert "vehicle" in data

    def test_enrichment_data_partial_vehicle_data(self):
        """Test enrichment data handles partial vehicle data from dict."""
        data = {
            "vehicle": {"vehicle_type": "motorcycle"},  # Missing other fields
        }
        enrichment = EnrichmentDataSchema.model_validate(data)
        assert enrichment.vehicle is not None
        assert enrichment.vehicle.vehicle_type == "motorcycle"
        assert enrichment.vehicle.has_damage is False  # Default

    def test_enrichment_data_extra_fields_ignored(self):
        """Test that extra fields in dict are ignored (not raise error)."""
        data = {
            "vehicle": {
                "vehicle_type": "bus",
                "unknown_field": "should be ignored",
            },
            "extra_top_level": "also ignored",
        }
        # Should not raise, extra fields ignored
        enrichment = EnrichmentDataSchema.model_validate(data)
        assert enrichment.vehicle is not None
        assert enrichment.vehicle.vehicle_type == "bus"


class TestValidateEnrichmentData:
    """Tests for validate_enrichment_data function that converts raw DB data."""

    def test_validate_enrichment_data_none(self):
        """Test that None input returns None."""
        result = validate_enrichment_data(None)
        assert result is None

    def test_validate_enrichment_data_empty_dict(self):
        """Test that empty dict returns schema with defaults."""
        result = validate_enrichment_data({})
        assert result is not None
        assert result.vehicle is None
        assert result.person is None
        assert result.pet is None
        assert result.weather is None
        assert result.errors == []

    def test_validate_enrichment_data_with_vehicle_classifications(self):
        """Test extraction of vehicle data from raw DB format."""
        raw_data = {
            "vehicle_classifications": {
                "det_1": {
                    "vehicle_type": "sedan",
                    "is_commercial": False,
                    "confidence": 0.92,
                }
            },
            "vehicle_damage": {
                "det_1": {
                    "has_damage": True,
                    "damage_types": ["scratch"],
                }
            },
        }
        result = validate_enrichment_data(raw_data)
        assert result is not None
        assert result.vehicle is not None
        assert result.vehicle.vehicle_type == "sedan"
        assert result.vehicle.has_damage is True
        assert result.vehicle.is_commercial is False

    def test_validate_enrichment_data_with_clothing_classifications(self):
        """Test extraction of person data from raw DB format."""
        raw_data = {
            "clothing_classifications": {
                "det_1": {
                    "raw_description": "dark jacket, blue jeans",
                    "is_suspicious": False,
                    "carrying": "backpack",
                }
            },
        }
        result = validate_enrichment_data(raw_data)
        assert result is not None
        assert result.person is not None
        assert result.person.clothing_description == "dark jacket, blue jeans"
        assert result.person.carrying == ["backpack"]
        assert result.person.is_suspicious is False

    def test_validate_enrichment_data_with_pet_classifications(self):
        """Test extraction of pet data from raw DB format."""
        raw_data = {
            "pet_classifications": {
                "det_1": {
                    "animal_type": "dog",
                    "is_household_pet": True,
                    "confidence": 0.95,
                }
            },
        }
        result = validate_enrichment_data(raw_data)
        assert result is not None
        assert result.pet is not None
        assert result.pet.pet_type == "dog"

    def test_validate_enrichment_data_with_errors(self):
        """Test that errors are sanitized and included."""
        raw_data = {
            "errors": [
                "License plate detection failed: /internal/path/error",
                "Face detection timeout",
            ],
        }
        result = validate_enrichment_data(raw_data)
        assert result is not None
        assert len(result.errors) == 2
        # Errors should be sanitized (no internal paths)
        assert "License Plate Detection failed" in result.errors
        assert "Face Detection failed" in result.errors

    def test_validate_enrichment_data_complete(self):
        """Test extraction with all data types present."""
        raw_data = {
            "vehicle_classifications": {
                "det_1": {
                    "vehicle_type": "truck",
                    "is_commercial": True,
                }
            },
            "clothing_classifications": {
                "det_2": {
                    "raw_description": "uniform",
                    "is_suspicious": False,
                }
            },
            "pet_classifications": {
                "det_3": {
                    "animal_type": "cat",
                }
            },
            "errors": [],
        }
        result = validate_enrichment_data(raw_data)
        assert result is not None
        assert result.vehicle is not None
        assert result.vehicle.vehicle_type == "truck"
        assert result.person is not None
        assert result.person.clothing_description == "uniform"
        assert result.pet is not None
        assert result.pet.pet_type == "cat"
        assert result.errors == []

    def test_validate_enrichment_data_returns_typed_model(self):
        """Test that the result is a proper EnrichmentDataSchema instance."""
        raw_data = {"vehicle_classifications": {"det_1": {"vehicle_type": "van"}}}
        result = validate_enrichment_data(raw_data)
        assert isinstance(result, EnrichmentDataSchema)
        assert isinstance(result.vehicle, VehicleEnrichmentData)

    def test_validate_enrichment_data_empty_carrying(self):
        """Test person data with no carrying field."""
        raw_data = {
            "clothing_classifications": {
                "det_1": {
                    "raw_description": "casual",
                    "is_suspicious": False,
                    "carrying": "",  # Empty string
                }
            },
        }
        result = validate_enrichment_data(raw_data)
        assert result is not None
        assert result.person is not None
        assert result.person.carrying == []  # Should be empty list
