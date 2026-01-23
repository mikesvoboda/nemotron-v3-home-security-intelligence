"""Unit tests for strict mode queue payload schemas.

This module tests the strict mode variants of queue payload schemas used
for internal communication (Redis queues, background tasks, inter-service).

Strict mode provides 15-25% faster validation by skipping type coercion,
which is safe for trusted internal data where types are already correct.

Test Strategy:
- Verify strict schemas reject coercible values (e.g., "123" for int)
- Verify strict schemas accept correctly-typed values
- Verify strict schemas inherit base security validations
- Compare validation behavior between strict and non-strict variants
"""

import pytest
from pydantic import ValidationError

from backend.api.schemas.queue import (
    AnalysisQueuePayload,
    AnalysisQueuePayloadStrict,
    DetectionQueuePayload,
    DetectionQueuePayloadStrict,
)


class TestDetectionQueuePayloadStrict:
    """Tests for DetectionQueuePayloadStrict schema."""

    def test_strict_accepts_correct_types(self):
        """Test strict schema accepts correctly-typed values."""
        payload = DetectionQueuePayloadStrict(
            camera_id="front_door",
            file_path="/export/foscam/front_door/image_001.jpg",
            timestamp="2025-12-23T10:30:00.000000",
            media_type="image",
        )
        assert payload.camera_id == "front_door"
        assert payload.file_path == "/export/foscam/front_door/image_001.jpg"
        assert payload.media_type == "image"

    def test_strict_accepts_optional_fields(self):
        """Test strict schema accepts optional fields with correct types."""
        payload = DetectionQueuePayloadStrict(
            camera_id="front_door",
            file_path="/export/foscam/front_door/image_001.jpg",
            timestamp="2025-12-23T10:30:00.000000",
            media_type="image",
            file_hash="abc123def456",  # pragma: allowlist secret
            pipeline_start_time="2025-12-23T10:29:55.000000",
        )
        assert payload.file_hash == "abc123def456"  # pragma: allowlist secret
        assert payload.pipeline_start_time == "2025-12-23T10:29:55.000000"

    def test_strict_rejects_coercible_int_for_string(self):
        """Test strict schema rejects integer where string expected."""
        # Non-strict would coerce 123 to "123", but strict should reject
        with pytest.raises(ValidationError) as exc_info:
            DetectionQueuePayloadStrict(
                camera_id=123,  # Should be string
                file_path="/export/foscam/front_door/image.jpg",
                timestamp="2025-12-23T10:30:00.000000",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("camera_id",) for e in errors)

    def test_strict_rejects_float_for_string(self):
        """Test strict schema rejects float where string expected."""
        with pytest.raises(ValidationError) as exc_info:
            DetectionQueuePayloadStrict(
                camera_id="front_door",
                file_path="/export/foscam/front_door/image.jpg",
                timestamp=1735123456.789,  # Should be string
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("timestamp",) for e in errors)

    def test_strict_inherits_path_traversal_validation(self):
        """Test strict schema still validates path traversal attacks."""
        with pytest.raises(ValidationError) as exc_info:
            DetectionQueuePayloadStrict(
                camera_id="front_door",
                file_path="../../../etc/passwd",  # Path traversal
                timestamp="2025-12-23T10:30:00.000000",
            )
        assert "file_path" in str(exc_info.value)

    def test_strict_inherits_absolute_path_validation(self):
        """Test strict schema still validates absolute path requirement."""
        with pytest.raises(ValidationError) as exc_info:
            DetectionQueuePayloadStrict(
                camera_id="front_door",
                file_path="relative/path/image.jpg",  # Not absolute
                timestamp="2025-12-23T10:30:00.000000",
            )
        assert "file_path" in str(exc_info.value)

    def test_strict_inherits_timestamp_validation(self):
        """Test strict schema still validates ISO timestamp format."""
        with pytest.raises(ValidationError) as exc_info:
            DetectionQueuePayloadStrict(
                camera_id="front_door",
                file_path="/export/foscam/front_door/image.jpg",
                timestamp="not-a-timestamp",  # Invalid format
            )
        assert "timestamp" in str(exc_info.value)

    def test_strict_inherits_camera_id_pattern_validation(self):
        """Test strict schema still validates camera_id pattern."""
        with pytest.raises(ValidationError) as exc_info:
            DetectionQueuePayloadStrict(
                camera_id="front door!@#",  # Invalid chars
                file_path="/export/foscam/front_door/image.jpg",
                timestamp="2025-12-23T10:30:00.000000",
            )
        assert "camera_id" in str(exc_info.value)

    def test_strict_model_config_is_strict(self):
        """Test that strict variant has strict=True in config."""
        config = DetectionQueuePayloadStrict.model_config
        assert config.get("strict") is True


class TestAnalysisQueuePayloadStrict:
    """Tests for AnalysisQueuePayloadStrict schema."""

    def test_strict_accepts_correct_types(self):
        """Test strict schema accepts correctly-typed values."""
        payload = AnalysisQueuePayloadStrict(
            batch_id="550e8400-e29b-41d4-a716-446655440000",
            camera_id="front_door",
            detection_ids=[1, 2, 3, 4, 5],
        )
        assert payload.batch_id == "550e8400-e29b-41d4-a716-446655440000"
        assert payload.camera_id == "front_door"
        assert payload.detection_ids == [1, 2, 3, 4, 5]

    def test_strict_accepts_optional_fields(self):
        """Test strict schema accepts optional fields with correct types."""
        payload = AnalysisQueuePayloadStrict(
            batch_id="batch-123",
            pipeline_start_time="2025-12-23T10:29:55.000000",
        )
        assert payload.pipeline_start_time == "2025-12-23T10:29:55.000000"

    def test_strict_rejects_coercible_int_for_string_batch_id(self):
        """Test strict schema rejects integer for batch_id."""
        with pytest.raises(ValidationError) as exc_info:
            AnalysisQueuePayloadStrict(
                batch_id=12345,  # Should be string
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("batch_id",) for e in errors)

    def test_strict_rejects_string_detection_ids(self):
        """Test strict schema rejects string detection IDs in list.

        The non-strict variant allows ["1", "2", "3"] and validates/converts them.
        The strict variant should reject non-integer detection_ids.
        """
        with pytest.raises(ValidationError) as exc_info:
            AnalysisQueuePayloadStrict(
                batch_id="batch-123",
                detection_ids=["1", "2", "3"],  # Should be ints
            )
        errors = exc_info.value.errors()
        # Should fail on detection_ids containing strings
        assert any("detection_ids" in str(e["loc"]) for e in errors)

    def test_strict_inherits_batch_id_validation(self):
        """Test strict schema still validates batch_id security."""
        with pytest.raises(ValidationError) as exc_info:
            AnalysisQueuePayloadStrict(
                batch_id="batch\x00null",  # Null byte injection
            )
        assert "batch_id" in str(exc_info.value)

    def test_strict_inherits_batch_id_newline_validation(self):
        """Test strict schema still validates batch_id newline injection."""
        with pytest.raises(ValidationError) as exc_info:
            AnalysisQueuePayloadStrict(
                batch_id="batch\ninjection",  # Newline injection
            )
        assert "batch_id" in str(exc_info.value)

    def test_strict_inherits_detection_ids_positive_validation(self):
        """Test strict schema still validates detection_ids are positive."""
        with pytest.raises(ValidationError) as exc_info:
            AnalysisQueuePayloadStrict(
                batch_id="batch-123",
                detection_ids=[1, 2, -1, 4],  # Negative ID
            )
        assert "detection_ids" in str(exc_info.value)

    def test_strict_inherits_detection_ids_max_size_validation(self):
        """Test strict schema still validates detection_ids max size."""
        large_list = list(range(1, 10002))  # 10001 items, > max 10000
        with pytest.raises(ValidationError) as exc_info:
            AnalysisQueuePayloadStrict(
                batch_id="batch-123",
                detection_ids=large_list,
            )
        assert "detection_ids" in str(exc_info.value)

    def test_strict_model_config_is_strict(self):
        """Test that strict variant has strict=True in config."""
        config = AnalysisQueuePayloadStrict.model_config
        assert config.get("strict") is True


class TestStrictVsNonStrictComparison:
    """Tests comparing behavior between strict and non-strict schemas."""

    def test_non_strict_detection_rejects_int_camera_id(self):
        """Test non-strict DetectionQueuePayload rejects int camera_id.

        Note: The pattern constraint on camera_id requires a string, so even
        non-strict mode rejects integers. This is Pydantic's expected behavior
        when pattern validation is used.
        """
        # Pattern validation requires string, so int is rejected even in non-strict
        with pytest.raises(ValidationError):
            DetectionQueuePayload(
                camera_id=123,  # Rejected: pattern requires string
                file_path="/export/foscam/front_door/image.jpg",
                timestamp="2025-12-23T10:30:00.000000",
            )

    def test_strict_detection_rejects_int_camera_id(self):
        """Test strict DetectionQueuePayloadStrict rejects int."""
        with pytest.raises(ValidationError):
            DetectionQueuePayloadStrict(
                camera_id=123,  # Should reject
                file_path="/export/foscam/front_door/image.jpg",
                timestamp="2025-12-23T10:30:00.000000",
            )

    def test_non_strict_analysis_allows_string_detection_ids(self):
        """Test non-strict AnalysisQueuePayload handles string detection IDs."""
        # Non-strict should validate and accept (the validator converts)
        payload = AnalysisQueuePayload(
            batch_id="batch-123",
            detection_ids=["1", "2", "3"],  # Strings are valid per validator
        )
        # The validator accepts int|str, so this should pass
        assert payload.detection_ids == ["1", "2", "3"]

    def test_strict_analysis_rejects_string_detection_ids(self):
        """Test strict AnalysisQueuePayloadStrict rejects string detection IDs."""
        with pytest.raises(ValidationError):
            AnalysisQueuePayloadStrict(
                batch_id="batch-123",
                detection_ids=["1", "2", "3"],  # Should reject strings
            )

    def test_both_accept_valid_data(self):
        """Test both variants accept properly typed data."""
        valid_detection_data = {
            "camera_id": "front_door",
            "file_path": "/export/foscam/front_door/image.jpg",
            "timestamp": "2025-12-23T10:30:00.000000",
            "media_type": "image",
        }
        valid_analysis_data = {
            "batch_id": "batch-123",
            "camera_id": "front_door",
            "detection_ids": [1, 2, 3],
        }

        # Non-strict
        d1 = DetectionQueuePayload(**valid_detection_data)
        a1 = AnalysisQueuePayload(**valid_analysis_data)

        # Strict
        d2 = DetectionQueuePayloadStrict(**valid_detection_data)
        a2 = AnalysisQueuePayloadStrict(**valid_analysis_data)

        # Both should produce same results
        assert d1.camera_id == d2.camera_id
        assert a1.batch_id == a2.batch_id
        assert a1.detection_ids == a2.detection_ids


class TestStrictSchemaModelDump:
    """Tests for model serialization compatibility."""

    def test_strict_detection_model_dump(self):
        """Test strict DetectionQueuePayloadStrict serializes correctly."""
        payload = DetectionQueuePayloadStrict(
            camera_id="front_door",
            file_path="/export/foscam/front_door/image.jpg",
            timestamp="2025-12-23T10:30:00.000000",
            media_type="image",
        )
        data = payload.model_dump()
        assert data["camera_id"] == "front_door"
        assert data["file_path"] == "/export/foscam/front_door/image.jpg"
        assert data["media_type"] == "image"

    def test_strict_analysis_model_dump(self):
        """Test strict AnalysisQueuePayloadStrict serializes correctly."""
        payload = AnalysisQueuePayloadStrict(
            batch_id="batch-123",
            camera_id="front_door",
            detection_ids=[1, 2, 3],
        )
        data = payload.model_dump()
        assert data["batch_id"] == "batch-123"
        assert data["camera_id"] == "front_door"
        assert data["detection_ids"] == [1, 2, 3]

    def test_strict_model_dump_json(self):
        """Test strict schemas serialize to JSON correctly."""
        payload = DetectionQueuePayloadStrict(
            camera_id="front_door",
            file_path="/export/foscam/front_door/image.jpg",
            timestamp="2025-12-23T10:30:00.000000",
        )
        json_str = payload.model_dump_json()
        assert '"camera_id":"front_door"' in json_str
        assert '"file_path":"/export/foscam/front_door/image.jpg"' in json_str
