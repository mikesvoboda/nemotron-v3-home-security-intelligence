"""Unit tests for EmbeddingsData schema validation.

Tests validate that the EmbeddingsData schema correctly validates and stores
cached embeddings for reuse across household matching and entity clustering.

TDD: These tests drive the implementation of embedding caching (Phase 3).
Related to NEM-4234: AI Pipeline Accuracy Improvements.
"""

from typing import Any

import pytest

from backend.api.schemas.enrichment_data import (
    EmbeddingsData,
    EnrichmentDataSchema,
    coerce_enrichment_data,
    validate_enrichment_data,
)


class TestEmbeddingsDataSchema:
    """Tests for EmbeddingsData schema validation."""

    def test_embeddings_data_with_person_reid(self) -> None:
        """Test validation of person re-ID embedding (512-dim OSNet)."""
        # Create a 512-dimensional embedding vector
        embedding = [0.1 * i for i in range(512)]
        data = {"person_reid": embedding}

        result = EmbeddingsData.model_validate(data)

        assert result.person_reid is not None
        assert len(result.person_reid) == 512
        assert result.person_reid[0] == 0.0
        assert result.person_reid[1] == pytest.approx(0.1)

    def test_embeddings_data_with_face_clip(self) -> None:
        """Test validation of face CLIP embedding (768-dim)."""
        # Create a 768-dimensional embedding vector
        embedding = [0.01 * i for i in range(768)]
        data = {"face_clip": embedding}

        result = EmbeddingsData.model_validate(data)

        assert result.face_clip is not None
        assert len(result.face_clip) == 768

    def test_embeddings_data_with_vehicle_visual(self) -> None:
        """Test validation of vehicle visual embedding (768-dim CLIP)."""
        # Create a 768-dimensional embedding vector
        embedding = [-0.5 + 0.001 * i for i in range(768)]
        data = {"vehicle_visual": embedding}

        result = EmbeddingsData.model_validate(data)

        assert result.vehicle_visual is not None
        assert len(result.vehicle_visual) == 768
        assert result.vehicle_visual[0] == pytest.approx(-0.5)

    def test_embeddings_data_all_fields(self) -> None:
        """Test validation with all embedding types present."""
        data = {
            "person_reid": [0.1] * 512,
            "face_clip": [0.2] * 768,
            "vehicle_visual": [0.3] * 768,
        }

        result = EmbeddingsData.model_validate(data)

        assert result.person_reid is not None
        assert result.face_clip is not None
        assert result.vehicle_visual is not None
        assert len(result.person_reid) == 512
        assert len(result.face_clip) == 768
        assert len(result.vehicle_visual) == 768

    def test_embeddings_data_all_none(self) -> None:
        """Test validation with all fields as None (empty embeddings)."""
        data: dict[str, Any] = {}

        result = EmbeddingsData.model_validate(data)

        assert result.person_reid is None
        assert result.face_clip is None
        assert result.vehicle_visual is None

    def test_embeddings_data_partial_fields(self) -> None:
        """Test validation with only some embedding types present."""
        data = {
            "person_reid": [0.1] * 512,
            # face_clip and vehicle_visual not provided
        }

        result = EmbeddingsData.model_validate(data)

        assert result.person_reid is not None
        assert result.face_clip is None
        assert result.vehicle_visual is None

    def test_embeddings_data_allows_extra_fields(self) -> None:
        """Test that extra fields are preserved for forward compatibility."""
        data = {
            "person_reid": [0.1] * 512,
            "future_embedding_type": [0.5] * 256,
        }

        # Should not raise due to model_config extra="allow"
        result = EmbeddingsData.model_validate(data)
        assert result.person_reid is not None

    def test_embeddings_data_empty_list(self) -> None:
        """Test validation with empty embedding lists."""
        data = {
            "person_reid": [],
            "face_clip": [],
        }

        result = EmbeddingsData.model_validate(data)

        # Empty lists are valid (no embedding available)
        assert result.person_reid == []
        assert result.face_clip == []


class TestEnrichmentDataWithEmbeddings:
    """Tests for EnrichmentDataSchema with embeddings field."""

    def test_enrichment_data_with_embeddings(self) -> None:
        """Test that EnrichmentDataSchema accepts embeddings field."""
        data = {
            "license_plates": [{"text": "ABC-123", "confidence": 0.9}],
            "embeddings": {
                "person_reid": [0.1] * 512,
                "face_clip": [0.2] * 768,
            },
        }

        schema = EnrichmentDataSchema.model_validate(data)

        assert schema.license_plates is not None
        assert len(schema.license_plates) == 1
        assert schema.embeddings is not None
        assert schema.embeddings.person_reid is not None
        assert len(schema.embeddings.person_reid) == 512

    def test_enrichment_data_without_embeddings(self) -> None:
        """Test that EnrichmentDataSchema works without embeddings (backward compat)."""
        data = {
            "license_plates": [{"text": "XYZ-789", "confidence": 0.85}],
            "processing_time_ms": 100.0,
        }

        schema = EnrichmentDataSchema.model_validate(data)

        assert schema.license_plates is not None
        assert schema.embeddings is None

    def test_enrichment_data_embeddings_none(self) -> None:
        """Test that embeddings can be explicitly set to None."""
        data = {
            "embeddings": None,
            "processing_time_ms": 50.0,
        }

        schema = EnrichmentDataSchema.model_validate(data)

        assert schema.embeddings is None

    def test_enrichment_data_empty_embeddings(self) -> None:
        """Test that empty embeddings object is valid."""
        data = {
            "embeddings": {},
        }

        schema = EnrichmentDataSchema.model_validate(data)

        assert schema.embeddings is not None
        assert schema.embeddings.person_reid is None
        assert schema.embeddings.face_clip is None
        assert schema.embeddings.vehicle_visual is None


class TestValidateEnrichmentDataWithEmbeddings:
    """Tests for validate_enrichment_data with embeddings."""

    def test_validate_embeddings_in_enrichment_data(self) -> None:
        """Test validation of enrichment data containing embeddings."""
        data = {
            "embeddings": {
                "person_reid": [0.5] * 512,
            },
            "processing_time_ms": 75.0,
        }

        result = validate_enrichment_data(data)

        assert result.is_valid is True
        assert result.data is not None
        assert "embeddings" in result.data
        assert result.data["embeddings"]["person_reid"] is not None

    def test_validate_preserves_embeddings(self) -> None:
        """Test that validation preserves embedding values."""
        embedding_values = [0.123, -0.456, 0.789, -0.012, 0.345]
        data = {
            "embeddings": {
                "person_reid": embedding_values + [0.0] * (512 - 5),
            }
        }

        result = validate_enrichment_data(data)

        assert result.is_valid is True
        assert result.data is not None
        person_reid = result.data["embeddings"]["person_reid"]
        assert person_reid[0] == pytest.approx(0.123)
        assert person_reid[1] == pytest.approx(-0.456)
        assert person_reid[2] == pytest.approx(0.789)


class TestCoerceEnrichmentDataWithEmbeddings:
    """Tests for coerce_enrichment_data with embeddings."""

    def test_coerce_preserves_embeddings(self) -> None:
        """Test that coercion preserves embedding data."""
        data = {
            "embeddings": {
                "vehicle_visual": [0.1] * 768,
            },
            "license_plates": [{"confidence": 1.5}],  # Out of range, will be clamped
        }

        result = coerce_enrichment_data(data)

        assert result is not None
        assert "embeddings" in result
        assert result["embeddings"]["vehicle_visual"] is not None
        assert len(result["embeddings"]["vehicle_visual"]) == 768
        # Confidence should be clamped
        assert result["license_plates"][0]["confidence"] == 1.0


class TestEmbeddingsDataIntegration:
    """Integration tests for embeddings in the enrichment pipeline flow."""

    def test_full_enrichment_data_with_embeddings(self) -> None:
        """Test complete enrichment data structure with all fields including embeddings."""
        data = {
            "license_plates": [
                {"bbox": [100.0, 200.0, 300.0, 250.0], "text": "ABC-1234", "confidence": 0.92}
            ],
            "faces": [{"bbox": [150.0, 50.0, 200.0, 120.0], "confidence": 0.95}],
            "vehicle_classifications": {"1": {"vehicle_type": "sedan", "confidence": 0.91}},
            "embeddings": {
                "person_reid": [0.1] * 512,
                "face_clip": [0.2] * 768,
                "vehicle_visual": [0.3] * 768,
            },
            "processing_time_ms": 150.0,
        }

        schema = EnrichmentDataSchema.model_validate(data)

        # Verify all fields are present
        assert len(schema.license_plates) == 1
        assert len(schema.faces) == 1
        assert "1" in schema.vehicle_classifications
        assert schema.embeddings is not None
        assert schema.embeddings.person_reid is not None
        assert schema.embeddings.face_clip is not None
        assert schema.embeddings.vehicle_visual is not None
        assert schema.processing_time_ms == 150.0

    def test_embeddings_data_serialization(self) -> None:
        """Test that embeddings can be serialized to dict (for JSON storage)."""
        embeddings = EmbeddingsData(
            person_reid=[0.1] * 512,
            face_clip=[0.2] * 768,
        )

        # Serialize to dict
        data = embeddings.model_dump()

        assert "person_reid" in data
        assert "face_clip" in data
        assert "vehicle_visual" in data  # Should be None
        assert len(data["person_reid"]) == 512
        assert len(data["face_clip"]) == 768
        assert data["vehicle_visual"] is None

    def test_enrichment_schema_model_dump_with_embeddings(self) -> None:
        """Test that EnrichmentDataSchema serializes embeddings correctly."""
        data = {
            "embeddings": {
                "person_reid": [0.5] * 512,
            }
        }

        schema = EnrichmentDataSchema.model_validate(data)
        dumped = schema.model_dump()

        assert "embeddings" in dumped
        assert dumped["embeddings"]["person_reid"] is not None
        assert len(dumped["embeddings"]["person_reid"]) == 512
