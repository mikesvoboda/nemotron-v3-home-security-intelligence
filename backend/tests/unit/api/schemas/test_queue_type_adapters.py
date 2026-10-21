"""Unit tests for module-level TypeAdapter instances in queue and LLM schemas.

This module tests that the TypeAdapter optimization (NEM-3395) works correctly
and provides the expected behavior. TypeAdapters are created once at module
load time to eliminate per-call construction overhead.

Test Strategy:
- Verify TypeAdapter instances exist at module level
- Verify validation functions use TypeAdapters correctly
- Verify TypeAdapters produce identical results to Model.model_validate()
- Verify TypeAdapters handle validation errors correctly
"""

import pytest

from backend.api.schemas.queue import (
    AnalysisQueuePayload,
    AnalysisQueuePayloadStrict,
    DetectionQueuePayload,
    DetectionQueuePayloadStrict,
    _analysis_payload_adapter,
    _analysis_payload_strict_adapter,
    _detection_payload_adapter,
    _detection_payload_strict_adapter,
    validate_analysis_payload,
    validate_analysis_payload_strict,
    validate_detection_payload,
    validate_detection_payload_strict,
)


class TestTypeAdapterInstancesExist:
    """Tests verifying TypeAdapter instances are created at module level."""

    def test_detection_payload_adapter_exists(self):
        """Test that _detection_payload_adapter is a TypeAdapter instance."""
        from pydantic import TypeAdapter

        assert isinstance(_detection_payload_adapter, TypeAdapter)

    def test_analysis_payload_adapter_exists(self):
        """Test that _analysis_payload_adapter is a TypeAdapter instance."""
        from pydantic import TypeAdapter

        assert isinstance(_analysis_payload_adapter, TypeAdapter)

    def test_detection_payload_strict_adapter_exists(self):
        """Test that _detection_payload_strict_adapter is a TypeAdapter instance."""
        from pydantic import TypeAdapter

        assert isinstance(_detection_payload_strict_adapter, TypeAdapter)

    def test_analysis_payload_strict_adapter_exists(self):
        """Test that _analysis_payload_strict_adapter is a TypeAdapter instance."""
        from pydantic import TypeAdapter

        assert isinstance(_analysis_payload_strict_adapter, TypeAdapter)


class TestTypeAdapterValidation:
    """Tests verifying TypeAdapter validation works correctly."""

    def test_detection_adapter_validates_valid_data(self):
        """Test TypeAdapter validates detection payload correctly."""
        valid_data = {
            "camera_id": "front_door",
            "file_path": "/export/foscam/front_door/image.jpg",
            "timestamp": "2025-12-23T10:30:00.000000",
            "media_type": "image",
        }
        result = _detection_payload_adapter.validate_python(valid_data)
        assert isinstance(result, DetectionQueuePayload)
        assert result.camera_id == "front_door"
        assert result.file_path == "/export/foscam/front_door/image.jpg"

    def test_analysis_adapter_validates_valid_data(self):
        """Test TypeAdapter validates analysis payload correctly."""
        valid_data = {
            "batch_id": "batch-123",
            "camera_id": "front_door",
            "detection_ids": [1, 2, 3],
        }
        result = _analysis_payload_adapter.validate_python(valid_data)
        assert isinstance(result, AnalysisQueuePayload)
        assert result.batch_id == "batch-123"
        assert result.detection_ids == [1, 2, 3]

    def test_detection_strict_adapter_validates_valid_data(self):
        """Test strict TypeAdapter validates detection payload correctly."""
        valid_data = {
            "camera_id": "front_door",
            "file_path": "/export/foscam/front_door/image.jpg",
            "timestamp": "2025-12-23T10:30:00.000000",
        }
        result = _detection_payload_strict_adapter.validate_python(valid_data)
        assert isinstance(result, DetectionQueuePayloadStrict)
        assert result.camera_id == "front_door"

    def test_analysis_strict_adapter_validates_valid_data(self):
        """Test strict TypeAdapter validates analysis payload correctly."""
        valid_data = {
            "batch_id": "batch-123",
            "detection_ids": [1, 2, 3],
        }
        result = _analysis_payload_strict_adapter.validate_python(valid_data)
        assert isinstance(result, AnalysisQueuePayloadStrict)
        assert result.batch_id == "batch-123"


class TestTypeAdapterEquivalenceToModelValidate:
    """Tests verifying TypeAdapter produces same results as Model.model_validate()."""

    def test_detection_adapter_matches_model_validate(self):
        """Test TypeAdapter and model_validate produce identical results."""
        valid_data = {
            "camera_id": "front_door",
            "file_path": "/export/foscam/front_door/image.jpg",
            "timestamp": "2025-12-23T10:30:00.000000",
            "media_type": "video",
            "file_hash": "abc123",
        }
        adapter_result = _detection_payload_adapter.validate_python(valid_data)
        model_result = DetectionQueuePayload.model_validate(valid_data)

        assert adapter_result.camera_id == model_result.camera_id
        assert adapter_result.file_path == model_result.file_path
        assert adapter_result.timestamp == model_result.timestamp
        assert adapter_result.media_type == model_result.media_type
        assert adapter_result.file_hash == model_result.file_hash

    def test_analysis_adapter_matches_model_validate(self):
        """Test TypeAdapter and model_validate produce identical results."""
        valid_data = {
            "batch_id": "batch-abc123",
            "camera_id": "side_camera",
            "detection_ids": [10, 20, 30],
            "pipeline_start_time": "2025-12-23T10:29:55.000000",
        }
        adapter_result = _analysis_payload_adapter.validate_python(valid_data)
        model_result = AnalysisQueuePayload.model_validate(valid_data)

        assert adapter_result.batch_id == model_result.batch_id
        assert adapter_result.camera_id == model_result.camera_id
        assert adapter_result.detection_ids == model_result.detection_ids
        assert adapter_result.pipeline_start_time == model_result.pipeline_start_time


class TestValidationFunctionsUseTypeAdapters:
    """Tests verifying validation functions correctly use TypeAdapters."""

    def test_validate_detection_payload_uses_adapter(self):
        """Test validate_detection_payload returns correct type via adapter."""
        valid_data = {
            "camera_id": "front_door",
            "file_path": "/export/foscam/front_door/image.jpg",
            "timestamp": "2025-12-23T10:30:00.000000",
        }
        result = validate_detection_payload(valid_data)
        assert isinstance(result, DetectionQueuePayload)

    def test_validate_analysis_payload_uses_adapter(self):
        """Test validate_analysis_payload returns correct type via adapter."""
        valid_data = {
            "batch_id": "batch-123",
        }
        result = validate_analysis_payload(valid_data)
        assert isinstance(result, AnalysisQueuePayload)

    def test_validate_detection_payload_strict_uses_adapter(self):
        """Test validate_detection_payload_strict returns correct type via adapter."""
        valid_data = {
            "camera_id": "front_door",
            "file_path": "/export/foscam/front_door/image.jpg",
            "timestamp": "2025-12-23T10:30:00.000000",
        }
        result = validate_detection_payload_strict(valid_data)
        assert isinstance(result, DetectionQueuePayloadStrict)

    def test_validate_analysis_payload_strict_uses_adapter(self):
        """Test validate_analysis_payload_strict returns correct type via adapter."""
        valid_data = {
            "batch_id": "batch-123",
            "detection_ids": [1, 2, 3],
        }
        result = validate_analysis_payload_strict(valid_data)
        assert isinstance(result, AnalysisQueuePayloadStrict)


class TestTypeAdapterErrorHandling:
    """Tests verifying TypeAdapters handle validation errors correctly."""

    def test_detection_adapter_raises_on_invalid_path(self):
        """Test TypeAdapter raises ValidationError for path traversal."""
        from pydantic import ValidationError

        invalid_data = {
            "camera_id": "front_door",
            "file_path": "../../../etc/passwd",  # Path traversal attack
            "timestamp": "2025-12-23T10:30:00.000000",
        }
        with pytest.raises(ValidationError):
            _detection_payload_adapter.validate_python(invalid_data)

    def test_validate_function_wraps_error_as_valueerror(self):
        """Test validate functions convert errors to ValueError."""
        invalid_data = {
            "camera_id": "front_door",
            "file_path": "../../../etc/passwd",  # Path traversal attack
            "timestamp": "2025-12-23T10:30:00.000000",
        }
        with pytest.raises(ValueError) as exc_info:
            validate_detection_payload(invalid_data)
        assert "Invalid detection queue payload" in str(exc_info.value)

    def test_strict_adapter_rejects_wrong_type(self):
        """Test strict TypeAdapter rejects type mismatches."""
        from pydantic import ValidationError

        invalid_data = {
            "batch_id": 12345,  # Should be string, not int
            "detection_ids": [1, 2, 3],
        }
        with pytest.raises(ValidationError):
            _analysis_payload_strict_adapter.validate_python(invalid_data)

    def test_strict_validate_function_wraps_type_error(self):
        """Test strict validate function converts type errors to ValueError."""
        invalid_data = {
            "batch_id": 12345,  # Should be string, not int
            "detection_ids": [1, 2, 3],
        }
        with pytest.raises(ValueError) as exc_info:
            validate_analysis_payload_strict(invalid_data)
        assert "Invalid analysis queue payload (strict)" in str(exc_info.value)


class TestTypeAdapterSerialization:
    """Tests verifying TypeAdapter JSON serialization capabilities."""

    def test_detection_adapter_dump_json(self):
        """Test TypeAdapter can serialize to JSON."""
        valid_data = {
            "camera_id": "front_door",
            "file_path": "/export/foscam/front_door/image.jpg",
            "timestamp": "2025-12-23T10:30:00.000000",
            "media_type": "image",
        }
        validated = _detection_payload_adapter.validate_python(valid_data)
        json_bytes = _detection_payload_adapter.dump_json(validated)
        assert b'"camera_id":"front_door"' in json_bytes
        assert b'"file_path":"/export/foscam/front_door/image.jpg"' in json_bytes

    def test_detection_adapter_validate_json(self):
        """Test TypeAdapter can validate JSON directly."""
        json_data = b'{"camera_id":"front_door","file_path":"/export/test/img.jpg","timestamp":"2025-12-23T10:30:00"}'
        result = _detection_payload_adapter.validate_json(json_data)
        assert isinstance(result, DetectionQueuePayload)
        assert result.camera_id == "front_door"

    def test_analysis_adapter_validate_json(self):
        """Test TypeAdapter can validate JSON directly for analysis payload."""
        json_data = b'{"batch_id":"batch-test","detection_ids":[1,2,3]}'
        result = _analysis_payload_adapter.validate_json(json_data)
        assert isinstance(result, AnalysisQueuePayload)
        assert result.batch_id == "batch-test"
        assert result.detection_ids == [1, 2, 3]
