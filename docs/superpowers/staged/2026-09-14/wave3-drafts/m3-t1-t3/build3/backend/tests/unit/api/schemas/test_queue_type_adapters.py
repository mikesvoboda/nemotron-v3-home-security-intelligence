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

from backend.api.schemas.llm import (
    LLMResponseParseError,
    LLMRiskResponse,
    _llm_risk_response_adapter,
    validate_llm_response,
)
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


# =============================================================================
# LLM Response TypeAdapter Tests (NEM-3395)
# =============================================================================


class TestLLMTypeAdapterInstanceExists:
    """Tests verifying LLM TypeAdapter instance is created at module level."""

    def test_llm_risk_response_adapter_exists(self):
        """Test that _llm_risk_response_adapter is a TypeAdapter instance."""
        from pydantic import TypeAdapter

        assert isinstance(_llm_risk_response_adapter, TypeAdapter)


class TestLLMTypeAdapterValidation:
    """Tests verifying LLM TypeAdapter validation works correctly."""

    def test_llm_adapter_validates_valid_data(self):
        """Test TypeAdapter validates LLM response correctly."""
        valid_data = {
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Suspicious activity detected",
            "reasoning": "Person detected at unusual time near entry point",
        }
        result = _llm_risk_response_adapter.validate_python(valid_data)
        assert isinstance(result, LLMRiskResponse)
        assert result.risk_score == 75
        assert result.risk_level.value == "high"
        assert result.summary == "Suspicious activity detected"

    def test_llm_adapter_coerces_risk_score(self):
        """Test TypeAdapter coerces float risk_score to int."""
        valid_data = {
            "risk_score": 75.5,  # Float should be coerced to int
            "risk_level": "high",
            "summary": "Test summary",
            "reasoning": "Test reasoning",
        }
        result = _llm_risk_response_adapter.validate_python(valid_data)
        assert result.risk_score == 75
        assert isinstance(result.risk_score, int)

    def test_llm_adapter_handles_case_insensitive_risk_level(self):
        """Test TypeAdapter handles uppercase risk levels."""
        valid_data = {
            "risk_score": 30,
            "risk_level": "MEDIUM",  # Uppercase
            "summary": "Test summary",
            "reasoning": "Test reasoning",
        }
        result = _llm_risk_response_adapter.validate_python(valid_data)
        assert result.risk_level.value == "medium"


class TestLLMTypeAdapterEquivalence:
    """Tests verifying LLM TypeAdapter matches Model.model_validate()."""

    def test_llm_adapter_matches_model_validate(self):
        """Test TypeAdapter and model_validate produce identical results."""
        valid_data = {
            "risk_score": 85,
            "risk_level": "critical",
            "summary": "Critical security event",
            "reasoning": "Multiple threats detected with high confidence",
        }
        adapter_result = _llm_risk_response_adapter.validate_python(valid_data)
        model_result = LLMRiskResponse.model_validate(valid_data)

        assert adapter_result.risk_score == model_result.risk_score
        assert adapter_result.risk_level == model_result.risk_level
        assert adapter_result.summary == model_result.summary
        assert adapter_result.reasoning == model_result.reasoning


class TestLLMValidateFunctionUsesAdapter:
    """Tests verifying validate_llm_response uses TypeAdapter."""

    def test_validate_llm_response_uses_adapter(self):
        """Test validate_llm_response returns correct type via adapter."""
        valid_data = {
            "risk_score": 50,
            "risk_level": "medium",
            "summary": "Routine activity",
            "reasoning": "Normal patterns observed",
        }
        result = validate_llm_response(valid_data)
        assert isinstance(result, LLMRiskResponse)

    def test_validate_llm_response_wraps_errors(self):
        """Test validate_llm_response wraps errors as LLMResponseParseError."""
        invalid_data = {
            "risk_score": "invalid",  # Invalid type
            "risk_level": "medium",
            "summary": "Test",
            "reasoning": "Test",
        }
        with pytest.raises(LLMResponseParseError) as exc_info:
            validate_llm_response(invalid_data)
        assert "Invalid LLM response" in str(exc_info.value)


class TestLLMTypeAdapterSerialization:
    """Tests verifying LLM TypeAdapter JSON capabilities."""

    def test_llm_adapter_dump_json(self):
        """Test TypeAdapter can serialize LLM response to JSON."""
        valid_data = {
            "risk_score": 60,
            "risk_level": "high",
            "summary": "Test summary",
            "reasoning": "Test reasoning",
        }
        validated = _llm_risk_response_adapter.validate_python(valid_data)
        json_bytes = _llm_risk_response_adapter.dump_json(validated)
        assert b'"risk_score":60' in json_bytes
        assert b'"risk_level":"high"' in json_bytes

    def test_llm_adapter_validate_json(self):
        """Test TypeAdapter can validate JSON directly for LLM response."""
        json_data = (
            b'{"risk_score":45,"risk_level":"medium","summary":"Test","reasoning":"Test reason"}'
        )
        result = _llm_risk_response_adapter.validate_json(json_data)
        assert isinstance(result, LLMRiskResponse)
        assert result.risk_score == 45
