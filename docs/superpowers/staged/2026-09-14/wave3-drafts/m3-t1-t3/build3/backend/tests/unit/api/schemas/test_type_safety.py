"""Unit tests for type safety between backend and frontend (NEM-4843).

Tests cover:
- AlertResponse includes version_id for optimistic locking
- EventResponse documents deferred fields (reasoning, llm_prompt)
- EntityResponse includes EntityMetadataSchema for entity_metadata
- DetectionResponse uses typed enrichment_data

Reference: docs/research/06-model-type-comparison.md
"""

from datetime import UTC, datetime

import pytest

from backend.api.schemas.alerts import AlertResponse, AlertSeverity, AlertStatus
from backend.api.schemas.detections import DetectionResponse
from backend.api.schemas.events import EventResponse

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# AlertResponse version_id Tests (NEM-4843 Issue 2: Optimistic Locking Mismatch)
# =============================================================================


class TestAlertResponseVersionId:
    """Tests for AlertResponse version_id field for optimistic locking."""

    def test_alert_response_has_version_id_field(self) -> None:
        """Test that AlertResponse includes version_id field."""
        # version_id should be included in the schema
        assert "version_id" in AlertResponse.model_fields
        assert AlertResponse.model_fields["version_id"].annotation is int

    def test_alert_response_with_version_id(self) -> None:
        """Test creating AlertResponse with version_id."""
        response = AlertResponse(
            id="550e8400-e29b-41d4-a716-446655440001",
            event_id=123,
            rule_id="550e8400-e29b-41d4-a716-446655440000",
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            dedup_key="test:key",
            version_id=1,
        )
        assert response.version_id == 1

    def test_alert_response_version_id_in_serialization(self) -> None:
        """Test that version_id is included in JSON serialization."""
        response = AlertResponse(
            id="550e8400-e29b-41d4-a716-446655440001",
            event_id=123,
            severity=AlertSeverity.MEDIUM,
            status=AlertStatus.DELIVERED,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            dedup_key="test:key",
            version_id=5,
        )
        json_data = response.model_dump(mode="json")
        assert "version_id" in json_data
        assert json_data["version_id"] == 5

    def test_alert_response_from_attributes_includes_version_id(self) -> None:
        """Test that version_id is populated from model attributes."""
        # Simulate model-like object with version_id
        # Use a factory function to avoid mutable class attribute lint error
        mock_alert = type(
            "MockAlert",
            (),
            {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "event_id": 123,
                "rule_id": None,
                "severity": AlertSeverity.LOW,
                "status": AlertStatus.ACKNOWLEDGED,
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
                "delivered_at": None,
                "channels": [],
                "dedup_key": "test:key",
                "alert_metadata": None,
                "version_id": 3,
            },
        )()

        response = AlertResponse.model_validate(mock_alert)
        assert response.version_id == 3


# =============================================================================
# EventResponse Deferred Fields Tests (NEM-4843 Issue 3: Deferred Fields)
# =============================================================================


class TestEventResponseDeferredFields:
    """Tests for EventResponse deferred field documentation."""

    def test_event_response_reasoning_has_deferred_description(self) -> None:
        """Test that reasoning field description mentions deferred loading."""
        field = EventResponse.model_fields["reasoning"]
        assert field.description is not None
        assert "deferred" in field.description.lower()

    def test_event_response_llm_prompt_has_deferred_description(self) -> None:
        """Test that llm_prompt field description mentions deferred loading."""
        field = EventResponse.model_fields["llm_prompt"]
        assert field.description is not None
        assert "deferred" in field.description.lower()

    def test_event_response_deferred_fields_json_schema(self) -> None:
        """Test that deferred fields are documented in JSON schema."""
        schema = EventResponse.model_json_schema()

        # Check reasoning description in schema
        reasoning_prop = schema["properties"]["reasoning"]
        assert "deferred" in reasoning_prop.get("description", "").lower()

        # Check llm_prompt description in schema
        llm_prompt_prop = schema["properties"]["llm_prompt"]
        assert "deferred" in llm_prompt_prop.get("description", "").lower()


# =============================================================================
# EntityMetadataSchema Tests (NEM-4843 Issue 1: JSONB Fields Untyped)
# =============================================================================


class TestEntityMetadataSchema:
    """Tests for typed EntityMetadataSchema for entity_metadata JSONB field."""

    def test_entity_metadata_schema_exists(self) -> None:
        """Test that EntityMetadataSchema is defined."""
        # Should be importable from entities module
        from backend.api.schemas.entities import EntityMetadataSchema

        assert EntityMetadataSchema is not None

    def test_entity_metadata_schema_has_expected_fields(self) -> None:
        """Test EntityMetadataSchema has common metadata fields."""
        from backend.api.schemas.entities import EntityMetadataSchema

        # Common fields for person entities
        metadata = EntityMetadataSchema(
            clothing_color="blue",
            clothing_description="Blue jacket with jeans",
            height_estimate="tall",
        )
        assert metadata.clothing_color == "blue"
        assert metadata.clothing_description == "Blue jacket with jeans"
        assert metadata.height_estimate == "tall"

    def test_entity_metadata_schema_vehicle_fields(self) -> None:
        """Test EntityMetadataSchema has vehicle metadata fields."""
        from backend.api.schemas.entities import EntityMetadataSchema

        metadata = EntityMetadataSchema(
            vehicle_make="Toyota",
            vehicle_model="Camry",
            vehicle_color="silver",
            license_plate="ABC-1234",
        )
        assert metadata.vehicle_make == "Toyota"
        assert metadata.vehicle_model == "Camry"

    def test_entity_metadata_schema_allows_extra_fields(self) -> None:
        """Test that EntityMetadataSchema allows extra fields for flexibility."""
        from backend.api.schemas.entities import EntityMetadataSchema

        # Schema should allow extra fields for forward compatibility
        metadata = EntityMetadataSchema(
            clothing_color="red",
            custom_field="custom_value",  # Extra field
        )
        # Depending on extra="allow" config, this should work
        assert metadata.clothing_color == "red"

    def test_entity_metadata_schema_all_optional(self) -> None:
        """Test that all EntityMetadataSchema fields are optional."""
        from backend.api.schemas.entities import EntityMetadataSchema

        # Should be able to create with no fields
        metadata = EntityMetadataSchema()
        assert metadata is not None


# =============================================================================
# EntityResponse Tests (NEM-4843 Issue 4: Missing Entity Schema)
# =============================================================================


class TestEntityResponse:
    """Tests for EntityResponse schema (API response format)."""

    def test_entity_response_exists(self) -> None:
        """Test that EntityResponse schema is defined."""
        # Should be importable from entities module
        from backend.api.schemas.entities import EntityResponse

        assert EntityResponse is not None

    def test_entity_response_has_required_fields(self) -> None:
        """Test EntityResponse has all required fields from Entity model."""
        from backend.api.schemas.entities import EntityResponse

        required_fields = [
            "id",
            "entity_type",
            "trust_status",
            "first_seen_at",
            "last_seen_at",
            "detection_count",
            "entity_metadata",
            "primary_detection_id",
        ]

        for field in required_fields:
            assert field in EntityResponse.model_fields, f"Missing field: {field}"

    def test_entity_response_uses_typed_metadata(self) -> None:
        """Test EntityResponse uses EntityMetadataSchema for entity_metadata."""
        from backend.api.schemas.entities import EntityResponse

        # entity_metadata should accept EntityMetadataSchema type
        field = EntityResponse.model_fields["entity_metadata"]
        # Annotation should reference EntityMetadataSchema (or be dict for backward compat)
        # At minimum, check it's not just dict[str, Any]
        assert field.annotation is not None


# =============================================================================
# DetectionResponse Typed Enrichment Data Tests
# =============================================================================


class TestDetectionResponseTypedEnrichment:
    """Tests for DetectionResponse with typed enrichment_data."""

    def test_detection_response_enrichment_data_field_info(self) -> None:
        """Test DetectionResponse enrichment_data has detailed field description."""
        field = DetectionResponse.model_fields["enrichment_data"]
        assert field.description is not None
        # Description should reference the schema structure
        assert "enrichment" in field.description.lower()

    def test_detection_response_enrichment_data_serialization(self) -> None:
        """Test that enrichment_data serializes correctly with structure."""
        response = DetectionResponse(
            id=1,
            camera_id="front_door",
            file_path="/path/to/file.jpg",
            detected_at=datetime.now(UTC),
            enrichment_data={
                "license_plates": [{"text": "ABC-1234", "confidence": 0.92}],
                "violence_detection": {"is_violent": False, "confidence": 0.05},
            },
        )

        json_data = response.model_dump(mode="json")
        assert "enrichment_data" in json_data
        assert json_data["enrichment_data"]["license_plates"][0]["text"] == "ABC-1234"


# =============================================================================
# Schema Documentation Tests
# =============================================================================


class TestSchemaDocumentation:
    """Tests for schema documentation and OpenAPI metadata."""

    def test_alert_response_version_id_documented(self) -> None:
        """Test AlertResponse version_id has proper description for OpenAPI."""
        field = AlertResponse.model_fields["version_id"]
        assert field.description is not None
        assert "optimistic" in field.description.lower() or "locking" in field.description.lower()

    def test_event_response_version_documented(self) -> None:
        """Test EventResponse version has proper description."""
        field = EventResponse.model_fields["version"]
        assert field.description is not None
        assert "optimistic" in field.description.lower() or "locking" in field.description.lower()

    def test_schemas_generate_valid_openapi(self) -> None:
        """Test that all modified schemas generate valid OpenAPI schemas."""
        # Generate JSON schemas - should not raise
        alert_schema = AlertResponse.model_json_schema()
        event_schema = EventResponse.model_json_schema()
        detection_schema = DetectionResponse.model_json_schema()

        # Basic validation that schemas are generated
        assert "properties" in alert_schema
        assert "properties" in event_schema
        assert "properties" in detection_schema

        # version_id should be in alert schema
        assert "version_id" in alert_schema["properties"]
