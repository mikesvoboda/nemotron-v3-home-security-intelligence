"""Tests for the consolidated exception hierarchy.

Tests the domain-specific exception hierarchy per NEM-1598:
- SecurityIntelligenceError (base)
- ServiceError -> AIServiceError -> DetectorUnavailableError, AnalyzerUnavailableError, EnrichmentUnavailableError
- DataError -> DetectionNotFoundError, EventNotFoundError, CameraNotFoundError
- ConfigurationError
- ResourceExhaustedError

Tests for ServiceRequestContext per NEM-1446:
- ServiceRequestContext dataclass for operational context
- to_log_dict() method for structured logging
"""

import pytest

from backend.core.exceptions import (
    AIServiceError,
    AlertCreationError,
    AnalyzerUnavailableError,
    AuthenticationError,
    AuthorizationError,
    BaselineNotFoundError,
    BoundingBoxOutOfBoundsError,
    BoundingBoxValidationError,
    CacheError,
    CameraNotFoundError,
    CertificateNotFoundError,
    CertificateValidationError,
    CircuitBreakerOpenError,
    ClipGenerationError,
    CLIPUnavailableError,
    ConfigurationError,
    ConflictError,
    DatabaseError,
    DateRangeValidationError,
    DetectionNotFoundError,
    DetectorUnavailableError,
    DuplicateResourceError,
    EnrichmentUnavailableError,
    EventNotFoundError,
    ExternalServiceError,
    FlorenceUnavailableError,
    InternalError,
    InvalidBoundingBoxError,
    InvalidEmbeddingError,
    InvalidImageSizeError,
    InvalidInputError,
    InvalidStateTransition,
    LLMResponseParseError,
    MediaNotFoundError,
    NotFoundError,
    ProcessingError,
    PromptVersionConflictError,
    RateLimitError,
    ResourceExhaustedError,
    ResourceNotFoundError,
    SceneBaselineError,
    SecurityIntelligenceError,
    ServiceRequestContext,
    SSRFValidationError,
    TLSConfigurationError,
    TLSError,
    URLValidationError,
    ValidationError,
    VideoProcessingError,
    get_exception_error_code,
    get_exception_status_code,
    validate_bounding_box,
    validate_image_size,
)


class TestSecurityIntelligenceError:
    def test_default_values(self) -> None:
        exc = SecurityIntelligenceError()
        assert exc.message == "An unexpected error occurred"
        assert exc.error_code == "INTERNAL_ERROR"
        assert exc.status_code == 500
        assert exc.details == {}

    def test_custom_message(self) -> None:
        exc = SecurityIntelligenceError("Custom error message")
        assert exc.message == "Custom error message"
        assert str(exc) == "Custom error message"


class TestValidationErrors:
    def test_validation_error_defaults(self) -> None:
        exc = ValidationError()
        assert exc.status_code == 400
        assert exc.error_code == "VALIDATION_ERROR"


class TestNotFoundErrors:
    def test_camera_not_found_error(self) -> None:
        exc = CameraNotFoundError(camera_id="backyard")
        assert exc.status_code == 404
        assert exc.error_code == "CAMERA_NOT_FOUND"
        assert "backyard" in exc.message


class TestRateLimitError:
    def test_rate_limit_error_defaults(self) -> None:
        exc = RateLimitError()
        assert exc.status_code == 429
        assert exc.error_code == "RATE_LIMIT_EXCEEDED"


class TestExternalServiceErrors:
    def test_detector_unavailable_error(self) -> None:
        exc = DetectorUnavailableError()
        assert exc.error_code == "DETECTOR_UNAVAILABLE"
        assert exc.service_name == "yolo26"

    def test_database_error(self) -> None:
        exc = DatabaseError()
        assert exc.status_code == 503
        assert exc.error_code == "DATABASE_ERROR"

    def test_circuit_breaker_open_error(self) -> None:
        exc = CircuitBreakerOpenError(service_name="yolo26", recovery_timeout=30.0)
        assert exc.status_code == 503
        assert exc.error_code == "CIRCUIT_BREAKER_OPEN"
        assert exc.details["recovery_timeout_seconds"] == 30.0


class TestAIServiceErrors:
    """Test AI service error hierarchy per NEM-1598."""

    def test_ai_service_error_hierarchy(self) -> None:
        """AIServiceError extends ExternalServiceError."""
        exc = AIServiceError()
        assert isinstance(exc, ExternalServiceError)
        assert isinstance(exc, SecurityIntelligenceError)
        assert exc.status_code == 503
        assert exc.error_code == "AI_SERVICE_UNAVAILABLE"

    def test_detector_unavailable_error(self) -> None:
        exc = DetectorUnavailableError()
        assert exc.error_code == "DETECTOR_UNAVAILABLE"
        assert exc.service_name == "yolo26"
        assert isinstance(exc, AIServiceError)

    def test_detector_unavailable_error_with_original(self) -> None:
        """DetectorUnavailableError preserves original exception."""
        original = ConnectionError("Network failure")
        exc = DetectorUnavailableError("Detection failed", original_error=original)
        assert exc.original_error is original
        assert exc.message == "Detection failed"

    def test_analyzer_unavailable_error(self) -> None:
        """AnalyzerUnavailableError for Nemotron failures."""
        exc = AnalyzerUnavailableError()
        assert exc.error_code == "ANALYZER_UNAVAILABLE"
        assert exc.service_name == "nemotron"
        assert isinstance(exc, AIServiceError)
        assert exc.status_code == 503

    def test_analyzer_unavailable_error_with_original(self) -> None:
        """AnalyzerUnavailableError preserves original exception."""
        original = TimeoutError("LLM timeout")
        exc = AnalyzerUnavailableError("Analysis failed", original_error=original)
        assert exc.original_error is original
        assert exc.message == "Analysis failed"

    def test_enrichment_unavailable_error(self) -> None:
        """EnrichmentUnavailableError for enrichment service failures."""
        exc = EnrichmentUnavailableError()
        assert exc.error_code == "ENRICHMENT_UNAVAILABLE"
        assert exc.service_name == "enrichment"
        assert isinstance(exc, AIServiceError)
        assert exc.status_code == 503

    def test_enrichment_unavailable_error_with_original(self) -> None:
        """EnrichmentUnavailableError preserves original exception."""
        original = Exception("Service down")
        exc = EnrichmentUnavailableError("Enrichment failed", original_error=original)
        assert exc.original_error is original
        assert exc.message == "Enrichment failed"


class TestDataErrors:
    """Test data/resource not found errors per NEM-1598."""

    def test_not_found_error_base(self) -> None:
        """NotFoundError is base for all data errors."""
        exc = NotFoundError()
        assert exc.status_code == 404
        assert exc.error_code == "NOT_FOUND"
        assert isinstance(exc, SecurityIntelligenceError)

    def test_detection_not_found_error(self) -> None:
        exc = DetectionNotFoundError(detection_id=123)
        assert exc.status_code == 404
        assert exc.error_code == "DETECTION_NOT_FOUND"
        assert "123" in exc.message
        assert exc.details["detection_id"] == 123

    def test_event_not_found_error(self) -> None:
        exc = EventNotFoundError(event_id=456)
        assert exc.status_code == 404
        assert exc.error_code == "EVENT_NOT_FOUND"
        assert "456" in exc.message
        assert exc.details["event_id"] == 456

    def test_camera_not_found_error(self) -> None:
        exc = CameraNotFoundError(camera_id="backyard")
        assert exc.status_code == 404
        assert exc.error_code == "CAMERA_NOT_FOUND"
        assert "backyard" in exc.message


class TestConfigurationError:
    """Test configuration error per NEM-1598."""

    def test_configuration_error(self) -> None:
        exc = ConfigurationError()
        assert exc.status_code == 500
        assert exc.error_code == "CONFIGURATION_ERROR"
        assert isinstance(exc, InternalError)
        assert isinstance(exc, SecurityIntelligenceError)

    def test_configuration_error_custom_message(self) -> None:
        exc = ConfigurationError("Missing required setting: YOLO26_URL")
        assert exc.message == "Missing required setting: YOLO26_URL"


class TestResourceExhaustedError:
    """Test resource exhausted error per NEM-1598."""

    def test_resource_exhausted_error_defaults(self) -> None:
        exc = ResourceExhaustedError()
        assert exc.status_code == 503
        assert exc.error_code == "RESOURCE_EXHAUSTED"
        assert isinstance(exc, SecurityIntelligenceError)

    def test_resource_exhausted_error_with_details(self) -> None:
        exc = ResourceExhaustedError(
            "GPU memory exhausted",
            resource_type="gpu_memory",
            limit="24GB",
            current="24GB",
        )
        assert exc.message == "GPU memory exhausted"
        assert exc.details["resource_type"] == "gpu_memory"
        assert exc.details["limit"] == "24GB"
        assert exc.details["current"] == "24GB"


class TestUtilityFunctions:
    def test_get_exception_status_code_custom(self) -> None:
        exc = CameraNotFoundError(camera_id="test")
        assert get_exception_status_code(exc) == 404

    def test_get_exception_error_code_custom(self) -> None:
        exc = RateLimitError()
        assert get_exception_error_code(exc) == "RATE_LIMIT_EXCEEDED"

    def test_get_status_code_for_ai_errors(self) -> None:
        """AI service errors return 503."""
        assert get_exception_status_code(DetectorUnavailableError()) == 503
        assert get_exception_status_code(AnalyzerUnavailableError()) == 503
        assert get_exception_status_code(EnrichmentUnavailableError()) == 503

    def test_get_error_code_for_ai_errors(self) -> None:
        """AI service errors have distinct error codes."""
        assert get_exception_error_code(DetectorUnavailableError()) == "DETECTOR_UNAVAILABLE"
        assert get_exception_error_code(AnalyzerUnavailableError()) == "ANALYZER_UNAVAILABLE"
        assert get_exception_error_code(EnrichmentUnavailableError()) == "ENRICHMENT_UNAVAILABLE"


class TestExceptionHierarchy:
    """Test the complete exception hierarchy per NEM-1598."""

    def test_all_exceptions_inherit_from_base(self) -> None:
        """All custom exceptions inherit from SecurityIntelligenceError."""
        exceptions = [
            AIServiceError(),
            DetectorUnavailableError(),
            AnalyzerUnavailableError(),
            EnrichmentUnavailableError(),
            NotFoundError(),
            DetectionNotFoundError(detection_id=1),
            EventNotFoundError(event_id=1),
            CameraNotFoundError(camera_id="test"),
            ConfigurationError(),
            ResourceExhaustedError(),
            ValidationError(),
            RateLimitError(),
            DatabaseError(),
        ]
        for exc in exceptions:
            assert isinstance(exc, SecurityIntelligenceError), (
                f"{type(exc).__name__} does not inherit from base"
            )

    def test_ai_service_hierarchy(self) -> None:
        """AI service exceptions form a proper hierarchy."""
        detector_exc = DetectorUnavailableError()
        analyzer_exc = AnalyzerUnavailableError()
        enrichment_exc = EnrichmentUnavailableError()

        # All are AIServiceError
        assert isinstance(detector_exc, AIServiceError)
        assert isinstance(analyzer_exc, AIServiceError)
        assert isinstance(enrichment_exc, AIServiceError)

        # All are ExternalServiceError
        assert isinstance(detector_exc, ExternalServiceError)
        assert isinstance(analyzer_exc, ExternalServiceError)
        assert isinstance(enrichment_exc, ExternalServiceError)

    def test_to_dict_serialization(self) -> None:
        """Exceptions can be serialized to dict for API responses."""
        exc = DetectorUnavailableError("YOLO26 timeout")
        result = exc.to_dict()
        assert result["code"] == "DETECTOR_UNAVAILABLE"
        assert result["message"] == "YOLO26 timeout"

    def test_to_dict_with_details(self) -> None:
        """Exception details are included in serialization."""
        exc = ResourceExhaustedError(
            "GPU exhausted",
            resource_type="gpu",
            limit="24GB",
        )
        result = exc.to_dict()
        assert result["code"] == "RESOURCE_EXHAUSTED"
        assert result["details"]["resource_type"] == "gpu"
        assert result["details"]["limit"] == "24GB"


# =============================================================================
# NEM-1441 Consolidated Exception Tests
# =============================================================================


class TestBoundingBoxErrors:
    """Test bounding box validation errors (NEM-1441)."""

    def test_invalid_bounding_box_error_defaults(self) -> None:
        exc = InvalidBoundingBoxError()
        assert exc.status_code == 400
        assert exc.error_code == "INVALID_BOUNDING_BOX_FORMAT"
        assert isinstance(exc, BoundingBoxValidationError)
        assert isinstance(exc, ValidationError)

    def test_invalid_bounding_box_error_with_bbox(self) -> None:
        bbox = (10.0, 20.0, 100.0, 200.0)
        exc = InvalidBoundingBoxError("Bad bbox", bbox=bbox)
        assert exc.bbox == bbox
        assert exc.details["bbox"] == [10.0, 20.0, 100.0, 200.0]

    def test_bounding_box_out_of_bounds_error(self) -> None:
        bbox = (10.0, 20.0, 2000.0, 2000.0)
        image_size = (1920, 1080)
        exc = BoundingBoxOutOfBoundsError(bbox=bbox, image_size=image_size)
        assert exc.status_code == 400
        assert exc.error_code == "BOUNDING_BOX_OUT_OF_BOUNDS"
        assert exc.bbox == bbox
        assert exc.image_size == image_size
        assert exc.details["bbox"] == list(bbox)
        assert exc.details["image_size"] == list(image_size)


class TestURLValidationErrors:
    """Test URL validation errors (NEM-1441)."""

    def test_url_validation_error_defaults(self) -> None:
        exc = URLValidationError()
        assert exc.status_code == 400
        assert exc.error_code == "INVALID_URL"
        assert isinstance(exc, ValidationError)

    def test_url_validation_error_with_details(self) -> None:
        exc = URLValidationError("Invalid URL format", url="http://example", reason="missing TLD")
        assert exc.url == "http://example"
        assert exc.reason == "missing TLD"
        assert exc.details["url"] == "http://example"
        assert exc.details["reason"] == "missing TLD"

    def test_ssrf_validation_error(self) -> None:
        exc = SSRFValidationError(url="http://169.254.169.254/metadata")
        assert exc.status_code == 400
        assert exc.error_code == "SSRF_BLOCKED"
        assert isinstance(exc, URLValidationError)


class TestAdditionalAIServiceErrors:
    """Test additional AI service errors (NEM-1441)."""

    def test_florence_unavailable_error(self) -> None:
        exc = FlorenceUnavailableError()
        assert exc.status_code == 503
        assert exc.error_code == "FLORENCE_UNAVAILABLE"
        assert exc.service_name == "florence"
        assert isinstance(exc, AIServiceError)

    def test_florence_unavailable_error_with_original(self) -> None:
        original = TimeoutError("Connection timed out")
        exc = FlorenceUnavailableError("Florence service down", original_error=original)
        assert exc.original_error is original
        assert exc.message == "Florence service down"

    def test_clip_unavailable_error(self) -> None:
        exc = CLIPUnavailableError()
        assert exc.status_code == 503
        assert exc.error_code == "CLIP_UNAVAILABLE"
        assert exc.service_name == "clip"
        assert isinstance(exc, AIServiceError)

    def test_clip_unavailable_error_with_original(self) -> None:
        original = ConnectionError("Network error")
        exc = CLIPUnavailableError("CLIP service unavailable", original_error=original)
        assert exc.original_error is original


class TestTLSErrors:
    """Test TLS/certificate errors (NEM-1441)."""

    def test_tls_error_base(self) -> None:
        exc = TLSError()
        assert exc.status_code == 500
        assert exc.error_code == "TLS_ERROR"
        assert isinstance(exc, ConfigurationError)

    def test_tls_configuration_error(self) -> None:
        exc = TLSConfigurationError("Invalid TLS version")
        assert exc.status_code == 500
        assert exc.error_code == "TLS_CONFIGURATION_ERROR"
        assert isinstance(exc, TLSError)

    def test_certificate_not_found_error(self) -> None:
        exc = CertificateNotFoundError(cert_path="/etc/ssl/certs/missing.pem")
        assert exc.status_code == 500
        assert exc.error_code == "CERTIFICATE_NOT_FOUND"
        assert exc.cert_path == "/etc/ssl/certs/missing.pem"
        assert exc.details["cert_path"] == "/etc/ssl/certs/missing.pem"

    def test_certificate_validation_error(self) -> None:
        exc = CertificateValidationError(reason="Certificate expired")
        assert exc.status_code == 500
        assert exc.error_code == "CERTIFICATE_VALIDATION_ERROR"
        assert exc.reason == "Certificate expired"
        assert exc.details["reason"] == "Certificate expired"


class TestSceneBaselineErrors:
    """Test scene baseline errors (NEM-1441)."""

    def test_scene_baseline_error_base(self) -> None:
        exc = SceneBaselineError()
        assert exc.status_code == 500
        assert exc.error_code == "SCENE_BASELINE_ERROR"
        assert isinstance(exc, ProcessingError)

    def test_baseline_not_found_error(self) -> None:
        exc = BaselineNotFoundError(camera_id="front_door")
        assert exc.status_code == 500
        assert exc.error_code == "BASELINE_NOT_FOUND"
        assert exc.camera_id == "front_door"
        assert exc.details["camera_id"] == "front_door"

    def test_invalid_embedding_error(self) -> None:
        exc = InvalidEmbeddingError(expected_dim=512, actual_dim=256)
        assert exc.status_code == 500
        assert exc.error_code == "INVALID_EMBEDDING"
        assert exc.expected_dim == 512
        assert exc.actual_dim == 256
        assert exc.details["expected_dim"] == 512
        assert exc.details["actual_dim"] == 256


class TestMediaProcessingErrors:
    """Test media processing errors (NEM-1441)."""

    def test_video_processing_error(self) -> None:
        exc = VideoProcessingError(video_path="/videos/test.mp4")
        assert exc.status_code == 500
        assert exc.error_code == "VIDEO_PROCESSING_ERROR"
        assert exc.video_path == "/videos/test.mp4"
        assert exc.details["filename"] == "test.mp4"

    def test_clip_generation_error(self) -> None:
        exc = ClipGenerationError(event_id=123)
        assert exc.status_code == 500
        assert exc.error_code == "CLIP_GENERATION_ERROR"
        assert exc.event_id == 123
        assert exc.details["event_id"] == 123


class TestAlertErrors:
    """Test alert errors (NEM-1441)."""

    def test_alert_creation_error(self) -> None:
        exc = AlertCreationError(event_id=456, reason="Duplicate alert")
        assert exc.status_code == 500
        assert exc.error_code == "ALERT_CREATION_ERROR"
        assert exc.event_id == 456
        assert exc.reason == "Duplicate alert"
        assert exc.details["event_id"] == 456
        assert exc.details["reason"] == "Duplicate alert"


class TestLLMErrors:
    """Test LLM response errors (NEM-1441)."""

    def test_llm_response_parse_error(self) -> None:
        raw = '{"incomplete": true'
        exc = LLMResponseParseError("Failed to parse JSON", raw_response=raw)
        assert exc.status_code == 500
        assert exc.error_code == "LLM_RESPONSE_PARSE_ERROR"
        assert exc.raw_response == raw
        assert exc.details["raw_response_preview"] == raw

    def test_llm_response_parse_error_truncates_long_response(self) -> None:
        long_response = "x" * 1000
        exc = LLMResponseParseError(raw_response=long_response)
        assert len(exc.details["raw_response_preview"]) == 500


class TestPromptConflictErrors:
    """Test prompt conflict errors (NEM-1441)."""

    def test_prompt_version_conflict_error(self) -> None:
        exc = PromptVersionConflictError(expected_version=5, actual_version=3)
        assert exc.status_code == 409
        assert exc.error_code == "PROMPT_VERSION_CONFLICT"
        assert exc.expected_version == 5
        assert exc.actual_version == 3
        assert exc.details["expected_version"] == 5
        assert exc.details["actual_version"] == 3

    def test_prompt_version_conflict_error_defaults(self) -> None:
        """PromptVersionConflictError works with default message."""
        exc = PromptVersionConflictError()
        assert exc.status_code == 409
        assert exc.error_code == "PROMPT_VERSION_CONFLICT"
        assert exc.message == "Prompt version conflict"


class TestConsolidatedExceptionsHierarchy:
    """Test that all consolidated exceptions inherit properly (NEM-1441)."""

    def test_all_consolidated_exceptions_inherit_from_base(self) -> None:
        """All NEM-1441 exceptions inherit from SecurityIntelligenceError."""
        exceptions = [
            InvalidBoundingBoxError(),
            BoundingBoxOutOfBoundsError(),
            URLValidationError(),
            SSRFValidationError(),
            FlorenceUnavailableError(),
            CLIPUnavailableError(),
            TLSError(),
            TLSConfigurationError(),
            CertificateNotFoundError(),
            CertificateValidationError(),
            SceneBaselineError(),
            BaselineNotFoundError(),
            InvalidEmbeddingError(),
            VideoProcessingError(),
            ClipGenerationError(),
            AlertCreationError(),
            LLMResponseParseError(),
            PromptVersionConflictError(),
        ]
        for exc in exceptions:
            assert isinstance(exc, SecurityIntelligenceError), (
                f"{type(exc).__name__} does not inherit from SecurityIntelligenceError"
            )

    def test_ai_service_errors_hierarchy(self) -> None:
        """Florence and CLIP errors are part of AI service hierarchy."""
        florence = FlorenceUnavailableError()
        clip = CLIPUnavailableError()
        assert isinstance(florence, AIServiceError)
        assert isinstance(florence, ExternalServiceError)
        assert isinstance(clip, AIServiceError)
        assert isinstance(clip, ExternalServiceError)

    def test_tls_errors_hierarchy(self) -> None:
        """TLS errors are part of configuration error hierarchy."""
        tls = TLSError()
        tls_config = TLSConfigurationError()
        cert_not_found = CertificateNotFoundError()
        cert_validation = CertificateValidationError()
        assert isinstance(tls, ConfigurationError)
        assert isinstance(tls_config, TLSError)
        assert isinstance(cert_not_found, TLSError)
        assert isinstance(cert_validation, TLSError)

    def test_processing_errors_hierarchy(self) -> None:
        """Scene and media errors are part of processing error hierarchy."""
        scene = SceneBaselineError()
        baseline = BaselineNotFoundError()
        video = VideoProcessingError()
        clip = ClipGenerationError()
        alert = AlertCreationError()
        llm = LLMResponseParseError()
        assert isinstance(scene, ProcessingError)
        assert isinstance(baseline, SceneBaselineError)
        assert isinstance(video, ProcessingError)
        assert isinstance(clip, ProcessingError)
        assert isinstance(alert, ProcessingError)
        assert isinstance(llm, ProcessingError)


# =============================================================================
# NEM-1446 ServiceRequestContext Tests
# =============================================================================


class TestServiceRequestContext:
    """Test ServiceRequestContext dataclass per NEM-1446."""

    def test_basic_initialization(self) -> None:
        """ServiceRequestContext stores basic operational data."""
        context = ServiceRequestContext(
            service_name="yolo26",
            endpoint="/detect",
            method="POST",
            duration_ms=150.5,
            attempt_number=1,
            max_attempts=3,
        )
        assert context.service_name == "yolo26"
        assert context.endpoint == "/detect"
        assert context.method == "POST"
        assert context.duration_ms == 150.5
        assert context.attempt_number == 1
        assert context.max_attempts == 3
        assert context.circuit_state is None

    def test_with_circuit_state(self) -> None:
        """ServiceRequestContext includes circuit breaker state when provided."""
        context = ServiceRequestContext(
            service_name="nemotron",
            endpoint="/completion",
            method="POST",
            duration_ms=2500.0,
            attempt_number=3,
            max_attempts=3,
            circuit_state="half_open",
        )
        assert context.circuit_state == "half_open"

    def test_to_dict(self) -> None:
        """ServiceRequestContext serializes to dictionary."""
        context = ServiceRequestContext(
            service_name="enrichment",
            endpoint="/vehicle-classify",
            method="POST",
            duration_ms=45.2,
            attempt_number=2,
            max_attempts=3,
            circuit_state="closed",
        )
        result = context.to_dict()
        assert result["service_name"] == "enrichment"
        assert result["endpoint"] == "/vehicle-classify"
        assert result["method"] == "POST"
        assert result["duration_ms"] == 45.2
        assert result["attempt_number"] == 2
        assert result["max_attempts"] == 3
        assert result["circuit_state"] == "closed"


class TestServiceUnavailableErrorContext:
    """Test ServiceUnavailableError with context per NEM-1446."""

    def test_detector_unavailable_with_context(self) -> None:
        """DetectorUnavailableError includes request context."""
        context = ServiceRequestContext(
            service_name="yolo26",
            endpoint="/detect",
            method="POST",
            duration_ms=60500.0,
            attempt_number=3,
            max_attempts=3,
            circuit_state="open",
        )
        original = TimeoutError("Request timed out")
        exc = DetectorUnavailableError(
            "YOLO26 detection failed after 3 attempts",
            original_error=original,
            context=context,
        )
        assert exc.context is context
        assert exc.original_error is original
        assert exc.service_name == "yolo26"

    def test_analyzer_unavailable_with_context(self) -> None:
        """AnalyzerUnavailableError includes request context."""
        context = ServiceRequestContext(
            service_name="nemotron",
            endpoint="/completion",
            method="POST",
            duration_ms=120500.0,
            attempt_number=3,
            max_attempts=3,
        )
        exc = AnalyzerUnavailableError(
            "Nemotron analysis failed",
            context=context,
        )
        assert exc.context is context
        assert exc.service_name == "nemotron"

    def test_enrichment_unavailable_with_context(self) -> None:
        """EnrichmentUnavailableError includes request context."""
        context = ServiceRequestContext(
            service_name="enrichment",
            endpoint="/vehicle-classify",
            method="POST",
            duration_ms=30200.0,
            attempt_number=2,
            max_attempts=3,
            circuit_state="half_open",
        )
        exc = EnrichmentUnavailableError(
            "Enrichment service unavailable",
            original_error=ConnectionError("Connection refused"),
            context=context,
        )
        assert exc.context is context
        assert exc.service_name == "enrichment"

    def test_to_log_dict_with_context(self) -> None:
        """to_log_dict() includes all context for structured logging."""
        context = ServiceRequestContext(
            service_name="yolo26",
            endpoint="/detect",
            method="POST",
            duration_ms=45000.0,
            attempt_number=3,
            max_attempts=3,
            circuit_state="open",
        )
        original = TimeoutError("Request timed out after 45s")
        exc = DetectorUnavailableError(
            "Detection failed after retries",
            original_error=original,
            context=context,
        )
        log_dict = exc.to_log_dict()

        # Check exception info
        assert log_dict["error_code"] == "DETECTOR_UNAVAILABLE"
        assert log_dict["message"] == "Detection failed after retries"
        assert log_dict["service_name"] == "yolo26"
        assert log_dict["status_code"] == 503

        # Check context info
        assert log_dict["context"]["service_name"] == "yolo26"
        assert log_dict["context"]["endpoint"] == "/detect"
        assert log_dict["context"]["method"] == "POST"
        assert log_dict["context"]["duration_ms"] == 45000.0
        assert log_dict["context"]["attempt_number"] == 3
        assert log_dict["context"]["max_attempts"] == 3
        assert log_dict["context"]["circuit_state"] == "open"

        # Check original error info
        assert "original_error" in log_dict
        assert log_dict["original_error"]["type"] == "TimeoutError"
        assert "Request timed out" in log_dict["original_error"]["message"]

    def test_to_log_dict_without_context(self) -> None:
        """to_log_dict() works without context."""
        exc = DetectorUnavailableError("Service down")
        log_dict = exc.to_log_dict()

        assert log_dict["error_code"] == "DETECTOR_UNAVAILABLE"
        assert log_dict["message"] == "Service down"
        assert log_dict["service_name"] == "yolo26"
        assert log_dict["context"] is None
        assert log_dict["original_error"] is None

    def test_to_log_dict_with_only_original_error(self) -> None:
        """to_log_dict() includes original error without context."""
        original = ConnectionError("Connection refused")
        exc = AnalyzerUnavailableError(
            "Nemotron unreachable",
            original_error=original,
        )
        log_dict = exc.to_log_dict()

        assert log_dict["service_name"] == "nemotron"
        assert log_dict["context"] is None
        assert log_dict["original_error"]["type"] == "ConnectionError"
        assert "Connection refused" in log_dict["original_error"]["message"]

    def test_backward_compatibility(self) -> None:
        """Exceptions work without context parameter (backward compatibility)."""
        # DetectorUnavailableError
        exc1 = DetectorUnavailableError()
        assert exc1.context is None
        assert exc1.original_error is None

        exc2 = DetectorUnavailableError("Custom message", original_error=ValueError("test"))
        assert exc2.context is None
        assert isinstance(exc2.original_error, ValueError)

        # AnalyzerUnavailableError
        exc3 = AnalyzerUnavailableError()
        assert exc3.context is None

        # EnrichmentUnavailableError
        exc4 = EnrichmentUnavailableError()
        assert exc4.context is None


# =============================================================================
# Additional Coverage Tests for Missing Lines
# =============================================================================


class TestInvalidInputError:
    """Test InvalidInputError with all parameter combinations."""

    def test_invalid_input_error_defaults(self) -> None:
        exc = InvalidInputError()
        assert exc.status_code == 400
        assert exc.error_code == "INVALID_INPUT"
        assert exc.message == "Invalid input provided"

    def test_invalid_input_error_with_field(self) -> None:
        exc = InvalidInputError("Invalid email", field="email")
        assert exc.message == "Invalid email"
        assert exc.details["field"] == "email"

    def test_invalid_input_error_with_value(self) -> None:
        exc = InvalidInputError("Invalid value", field="age", value=200)
        assert exc.details["field"] == "age"
        assert exc.details["value"] == "200"

    def test_invalid_input_error_with_long_value(self) -> None:
        """Long values are truncated to 100 characters."""
        long_value = "x" * 150
        exc = InvalidInputError("Too long", field="description", value=long_value)
        assert len(exc.details["value"]) == 100

    def test_invalid_input_error_with_constraint(self) -> None:
        exc = InvalidInputError(
            "Value out of range",
            field="age",
            value=200,
            constraint="must be between 0 and 120",
        )
        assert exc.details["constraint"] == "must be between 0 and 120"

    def test_invalid_input_error_with_custom_details(self) -> None:
        """Custom details are merged with auto-generated details."""
        exc = InvalidInputError(
            "Invalid input",
            field="email",
            details={"custom_key": "custom_value"},
        )
        assert exc.details["field"] == "email"
        assert exc.details["custom_key"] == "custom_value"


class TestDateRangeValidationError:
    """Test DateRangeValidationError with date parameters."""

    def test_date_range_validation_error_defaults(self) -> None:
        exc = DateRangeValidationError()
        assert exc.status_code == 400
        assert exc.error_code == "INVALID_DATE_RANGE"
        assert "start_date must be before end_date" in exc.message

    def test_date_range_validation_error_with_dates(self) -> None:
        from datetime import datetime

        start = datetime(2025, 1, 15)
        end = datetime(2025, 1, 10)
        exc = DateRangeValidationError(
            "Invalid date range",
            start_date=start,
            end_date=end,
        )
        assert exc.details["start_date"] == str(start)
        assert exc.details["end_date"] == str(end)

    def test_date_range_validation_error_with_custom_details(self) -> None:
        """Custom details are merged properly."""
        exc = DateRangeValidationError(
            details={"custom": "value"},
            start_date="2025-01-15",
        )
        assert exc.details["start_date"] == "2025-01-15"
        assert exc.details["custom"] == "value"


class TestAuthErrors:
    """Test authentication and authorization errors."""

    def test_authentication_error(self) -> None:
        exc = AuthenticationError()
        assert exc.status_code == 401
        assert exc.error_code == "AUTHENTICATION_REQUIRED"
        assert exc.message == "Authentication required"

    def test_authentication_error_custom_message(self) -> None:
        exc = AuthenticationError("Invalid credentials")
        assert exc.message == "Invalid credentials"

    def test_authorization_error(self) -> None:
        exc = AuthorizationError()
        assert exc.status_code == 403
        assert exc.error_code == "ACCESS_DENIED"
        assert exc.message == "Access denied"

    def test_authorization_error_custom_message(self) -> None:
        exc = AuthorizationError("Insufficient permissions")
        assert exc.message == "Insufficient permissions"


class TestResourceNotFoundError:
    """Test ResourceNotFoundError with various resource types."""

    def test_resource_not_found_with_string_id(self) -> None:
        exc = ResourceNotFoundError("camera", "backyard")
        assert exc.status_code == 404
        assert "Camera" in exc.message
        assert "backyard" in exc.message
        assert exc.details["resource_type"] == "camera"
        assert exc.details["resource_id"] == "backyard"

    def test_resource_not_found_with_int_id(self) -> None:
        exc = ResourceNotFoundError("event", 123)
        assert "Event" in exc.message
        assert "123" in exc.message
        assert exc.details["resource_id"] == "123"

    def test_resource_not_found_with_custom_message(self) -> None:
        exc = ResourceNotFoundError("user", 456, message="User does not exist")
        assert exc.message == "User does not exist"
        assert exc.details["resource_type"] == "user"

    def test_resource_not_found_with_custom_details(self) -> None:
        exc = ResourceNotFoundError(
            "session",
            "abc123",
            details={"expired": True},
        )
        assert exc.details["resource_type"] == "session"
        assert exc.details["expired"] is True


class TestMediaNotFoundError:
    """Test MediaNotFoundError with file path handling."""

    def test_media_not_found_basic(self) -> None:
        exc = MediaNotFoundError("/path/to/image.jpg")
        assert exc.status_code == 404
        assert exc.error_code == "MEDIA_NOT_FOUND"
        assert exc.details["filename"] == "image.jpg"

    def test_media_not_found_with_media_type(self) -> None:
        exc = MediaNotFoundError("/path/to/video.mp4", media_type="video")
        assert "Video " in exc.message
        assert exc.details["media_type"] == "video"
        assert exc.details["filename"] == "video.mp4"

    def test_media_not_found_with_empty_path(self) -> None:
        """Empty path results in 'unknown' filename."""
        exc = MediaNotFoundError("")
        assert exc.details["filename"] == "unknown"

    def test_media_not_found_custom_message(self) -> None:
        exc = MediaNotFoundError(
            "/path/to/file.jpg",
            message="Custom not found message",
        )
        assert exc.message == "Custom not found message"


class TestConflictErrors:
    """Test conflict error hierarchy."""

    def test_conflict_error_base(self) -> None:
        exc = ConflictError()
        assert exc.status_code == 409
        assert exc.error_code == "CONFLICT"
        assert exc.message == "Request conflicts with current state"

    def test_conflict_error_custom(self) -> None:
        exc = ConflictError("Resource is locked")
        assert exc.message == "Resource is locked"


class TestDuplicateResourceError:
    """Test DuplicateResourceError with various parameter combinations."""

    def test_duplicate_resource_basic(self) -> None:
        exc = DuplicateResourceError("camera")
        assert exc.status_code == 409
        assert exc.error_code == "DUPLICATE_RESOURCE"
        assert "Camera already exists" in exc.message
        assert exc.details["resource_type"] == "camera"

    def test_duplicate_resource_with_field_and_value(self) -> None:
        exc = DuplicateResourceError("user", field="email", value="test@example.com")
        assert "User" in exc.message
        assert "email" in exc.message
        assert "test@example.com" in exc.message
        assert exc.details["field"] == "email"
        assert exc.details["value"] == "test@example.com"

    def test_duplicate_resource_with_existing_id(self) -> None:
        exc = DuplicateResourceError(
            "camera",
            field="name",
            value="backyard",
            existing_id="abc-123",
        )
        assert "(id: abc-123)" in exc.message
        assert exc.details["existing_id"] == "abc-123"

    def test_duplicate_resource_custom_message(self) -> None:
        exc = DuplicateResourceError(
            "resource",
            message="Custom duplicate message",
        )
        assert exc.message == "Custom duplicate message"


class TestRateLimitErrorDetails:
    """Test RateLimitError with all optional parameters."""

    def test_rate_limit_with_retry_after(self) -> None:
        exc = RateLimitError(retry_after=60)
        assert exc.details["retry_after"] == 60

    def test_rate_limit_with_limit(self) -> None:
        exc = RateLimitError(limit=100)
        assert exc.details["limit"] == 100

    def test_rate_limit_with_window(self) -> None:
        exc = RateLimitError(window_seconds=3600)
        assert exc.details["window_seconds"] == 3600

    def test_rate_limit_with_all_params(self) -> None:
        exc = RateLimitError(
            "Too many requests",
            retry_after=120,
            limit=50,
            window_seconds=60,
        )
        assert exc.message == "Too many requests"
        assert exc.details["retry_after"] == 120
        assert exc.details["limit"] == 50
        assert exc.details["window_seconds"] == 60


class TestExternalServiceErrorWithServiceName:
    """Test ExternalServiceError with service_name parameter."""

    def test_external_service_error_with_service_name(self) -> None:
        exc = ExternalServiceError(service_name="custom_service")
        assert exc.service_name == "custom_service"
        assert exc.details["service"] == "custom_service"

    def test_external_service_error_without_service_name(self) -> None:
        exc = ExternalServiceError()
        assert exc.service_name is None


class TestCacheError:
    """Test CacheError initialization."""

    def test_cache_error_defaults(self) -> None:
        exc = CacheError()
        assert exc.status_code == 503
        assert exc.error_code == "CACHE_ERROR"
        assert exc.service_name == "redis"

    def test_cache_error_custom_message(self) -> None:
        exc = CacheError("Redis connection failed")
        assert exc.message == "Redis connection failed"


class TestCircuitBreakerOpenErrorDetails:
    """Test CircuitBreakerOpenError message generation."""

    def test_circuit_breaker_default_message(self) -> None:
        exc = CircuitBreakerOpenError("test_service")
        assert "test_service" in exc.message
        assert "Circuit breaker" in exc.message
        assert exc.service_name == "test_service"

    def test_circuit_breaker_without_recovery_timeout(self) -> None:
        exc = CircuitBreakerOpenError("api_service")
        assert "recovery_timeout_seconds" not in exc.details


class TestProcessingErrorWithOperation:
    """Test ProcessingError with operation parameter."""

    def test_processing_error_with_operation(self) -> None:
        exc = ProcessingError("Processing failed", operation="image_resize")
        assert exc.details["operation"] == "image_resize"

    def test_processing_error_without_operation(self) -> None:
        exc = ProcessingError("Processing failed")
        assert "operation" not in exc.details


class TestInvalidStateTransition:
    """Test InvalidStateTransition error."""

    def test_invalid_state_transition_auto_message(self) -> None:
        exc = InvalidStateTransition(
            from_status="completed",
            to_status="running",
        )
        assert "Cannot transition from 'completed' to 'running'" in exc.message
        assert exc.from_status == "completed"
        assert exc.to_status == "running"
        assert exc.details["from_status"] == "completed"
        assert exc.details["to_status"] == "running"

    def test_invalid_state_transition_with_job_id(self) -> None:
        exc = InvalidStateTransition(
            from_status="pending",
            to_status="completed",
            job_id="job-123",
        )
        assert exc.job_id == "job-123"
        assert exc.details["job_id"] == "job-123"

    def test_invalid_state_transition_custom_message(self) -> None:
        exc = InvalidStateTransition(
            message="Custom transition error",
            from_status="a",
            to_status="b",
        )
        assert exc.message == "Custom transition error"

    def test_invalid_state_transition_defaults(self) -> None:
        exc = InvalidStateTransition()
        assert exc.status_code == 409
        assert exc.error_code == "INVALID_STATE_TRANSITION"


class TestURLValidationErrorTruncation:
    """Test URL validation error URL truncation."""

    def test_url_truncation_long_url(self) -> None:
        long_url = "http://example.com/" + "x" * 250
        exc = URLValidationError(url=long_url)
        assert len(exc.details["url"]) == 200

    def test_url_no_truncation_short_url(self) -> None:
        short_url = "http://example.com/short"
        exc = URLValidationError(url=short_url)
        assert exc.details["url"] == short_url


class TestUtilityFunctionsEdgeCases:
    """Test utility functions with non-SecurityIntelligenceError exceptions."""

    def test_get_exception_status_code_standard_exception(self) -> None:
        """Standard Python exceptions return 500."""
        exc = ValueError("Some error")
        assert get_exception_status_code(exc) == 500

    def test_get_exception_error_code_standard_exception(self) -> None:
        """Standard Python exceptions return INTERNAL_ERROR."""
        exc = RuntimeError("Some error")
        assert get_exception_error_code(exc) == "INTERNAL_ERROR"


class TestToDictWithoutDetails:
    """Test to_dict() method when details is empty."""

    def test_to_dict_empty_details(self) -> None:
        """Empty details dict is not included in to_dict() output."""
        exc = SecurityIntelligenceError("Error without details")
        result = exc.to_dict()
        assert "code" in result
        assert "message" in result
        assert "details" not in result


class TestEnrichmentUnavailableToLogDict:
    """Test EnrichmentUnavailableError.to_log_dict() method."""

    def test_enrichment_to_log_dict_with_context_and_error(self) -> None:
        context = ServiceRequestContext(
            service_name="enrichment",
            endpoint="/classify",
            method="POST",
            duration_ms=1500.0,
            attempt_number=2,
            max_attempts=3,
            circuit_state="half_open",
        )
        original = TimeoutError("Request timeout")
        exc = EnrichmentUnavailableError(
            "Enrichment failed",
            original_error=original,
            context=context,
        )
        log_dict = exc.to_log_dict()

        assert log_dict["error_code"] == "ENRICHMENT_UNAVAILABLE"
        assert log_dict["message"] == "Enrichment failed"
        assert log_dict["service_name"] == "enrichment"
        assert log_dict["context"]["endpoint"] == "/classify"
        assert log_dict["original_error"]["type"] == "TimeoutError"

    def test_enrichment_to_log_dict_without_context_or_error(self) -> None:
        exc = EnrichmentUnavailableError()
        log_dict = exc.to_log_dict()

        assert log_dict["error_code"] == "ENRICHMENT_UNAVAILABLE"
        assert log_dict["context"] is None
        assert log_dict["original_error"] is None


class TestAnalyzerUnavailableToLogDict:
    """Test AnalyzerUnavailableError.to_log_dict() method edge cases."""

    def test_analyzer_to_log_dict_with_only_context(self) -> None:
        context = ServiceRequestContext(
            service_name="nemotron",
            endpoint="/completion",
            method="POST",
            duration_ms=5000.0,
            attempt_number=1,
            max_attempts=3,
        )
        exc = AnalyzerUnavailableError(context=context)
        log_dict = exc.to_log_dict()

        assert log_dict["context"] is not None
        assert log_dict["original_error"] is None


class TestExceptionWithCustomErrorCodeAndStatus:
    """Test exceptions with custom error_code and status_code parameters."""

    def test_security_intelligence_error_with_custom_codes(self) -> None:
        exc = SecurityIntelligenceError(
            "Custom error",
            error_code="CUSTOM_CODE",
            status_code=418,
        )
        assert exc.error_code == "CUSTOM_CODE"
        assert exc.status_code == 418

    def test_security_intelligence_error_with_custom_details(self) -> None:
        details = {"key1": "value1", "key2": "value2"}
        exc = SecurityIntelligenceError("Error", details=details)
        assert exc.details == details


# =============================================================================
# NEM-2605 Bounding Box Edge Case Tests
# =============================================================================


class TestInvalidImageSizeError:
    """Test InvalidImageSizeError exception (NEM-2605)."""

    def test_invalid_image_size_error_defaults(self) -> None:
        exc = InvalidImageSizeError()
        assert exc.status_code == 400
        assert exc.error_code == "INVALID_IMAGE_SIZE"
        assert exc.message == "Invalid image size"
        assert isinstance(exc, ValidationError)

    def test_invalid_image_size_error_with_image_size(self) -> None:
        exc = InvalidImageSizeError("Width is zero", image_size=(0, 480))
        assert exc.image_size == (0, 480)
        assert exc.details["image_size"] == [0, 480]
        assert exc.message == "Width is zero"

    def test_invalid_image_size_error_with_reason(self) -> None:
        exc = InvalidImageSizeError(reason="non-positive width")
        assert exc.reason == "non-positive width"
        assert exc.details["reason"] == "non-positive width"

    def test_invalid_image_size_error_with_all_params(self) -> None:
        exc = InvalidImageSizeError(
            "Invalid dimensions",
            image_size=(-1, 100),
            reason="negative width",
        )
        assert exc.message == "Invalid dimensions"
        assert exc.image_size == (-1, 100)
        assert exc.reason == "negative width"
        assert exc.details["image_size"] == [-1, 100]
        assert exc.details["reason"] == "negative width"


class TestValidateBoundingBox:
    """Test validate_bounding_box function (NEM-2605)."""

    def test_valid_bbox_passes(self) -> None:
        """Valid bbox should not raise."""
        validate_bounding_box((10, 20, 100, 200))  # Should not raise

    def test_valid_bbox_with_floats_passes(self) -> None:
        """Valid bbox with float coordinates should not raise."""
        validate_bounding_box((10.5, 20.5, 100.5, 200.5))  # Should not raise

    def test_zero_width_raises(self) -> None:
        """Zero-width bbox (x1 == x2) should raise InvalidBoundingBoxError."""
        with pytest.raises(InvalidBoundingBoxError) as exc_info:
            validate_bounding_box((50, 0, 50, 100))
        assert "zero or negative width" in str(exc_info.value)
        assert exc_info.value.bbox == (50, 0, 50, 100)

    def test_zero_height_raises(self) -> None:
        """Zero-height bbox (y1 == y2) should raise InvalidBoundingBoxError."""
        with pytest.raises(InvalidBoundingBoxError) as exc_info:
            validate_bounding_box((0, 50, 100, 50))
        assert "zero or negative height" in str(exc_info.value)
        assert exc_info.value.bbox == (0, 50, 100, 50)

    def test_negative_width_raises(self) -> None:
        """Negative-width bbox (x2 < x1) should raise InvalidBoundingBoxError."""
        with pytest.raises(InvalidBoundingBoxError) as exc_info:
            validate_bounding_box((100, 0, 50, 100))
        assert "zero or negative width" in str(exc_info.value)

    def test_negative_height_raises(self) -> None:
        """Negative-height bbox (y2 < y1) should raise InvalidBoundingBoxError."""
        with pytest.raises(InvalidBoundingBoxError) as exc_info:
            validate_bounding_box((0, 100, 100, 50))
        assert "zero or negative height" in str(exc_info.value)

    def test_negative_coordinates_raises_by_default(self) -> None:
        """Negative coordinates should raise by default."""
        with pytest.raises(InvalidBoundingBoxError) as exc_info:
            validate_bounding_box((-10, 0, 100, 100))
        assert "negative coordinates" in str(exc_info.value)

    def test_negative_coordinates_allowed_when_enabled(self) -> None:
        """Negative coordinates should pass when allow_negative=True."""
        validate_bounding_box((-10, -10, 100, 100), allow_negative=True)

    def test_all_negative_coordinates_raises_by_default(self) -> None:
        """All negative coordinates should raise by default."""
        with pytest.raises(InvalidBoundingBoxError) as exc_info:
            validate_bounding_box((-100, -100, -10, -10))
        assert "negative coordinates" in str(exc_info.value)

    def test_all_negative_coordinates_allowed_when_enabled(self) -> None:
        """All negative coordinates pass when allow_negative=True."""
        validate_bounding_box((-100, -100, -10, -10), allow_negative=True)

    def test_with_valid_image_size(self) -> None:
        """Valid bbox with valid image_size should pass."""
        validate_bounding_box((10, 20, 100, 200), image_size=(640, 480))

    def test_with_zero_width_image_size_raises(self) -> None:
        """Zero-width image_size should raise InvalidImageSizeError."""
        with pytest.raises(InvalidImageSizeError) as exc_info:
            validate_bounding_box((10, 20, 100, 200), image_size=(0, 480))
        assert "positive" in str(exc_info.value)
        assert exc_info.value.image_size == (0, 480)

    def test_with_zero_height_image_size_raises(self) -> None:
        """Zero-height image_size should raise InvalidImageSizeError."""
        with pytest.raises(InvalidImageSizeError) as exc_info:
            validate_bounding_box((10, 20, 100, 200), image_size=(640, 0))
        assert "positive" in str(exc_info.value)

    def test_with_negative_width_image_size_raises(self) -> None:
        """Negative-width image_size should raise InvalidImageSizeError."""
        with pytest.raises(InvalidImageSizeError) as exc_info:
            validate_bounding_box((10, 20, 100, 200), image_size=(-1, 480))
        assert "positive" in str(exc_info.value)

    def test_with_negative_height_image_size_raises(self) -> None:
        """Negative-height image_size should raise InvalidImageSizeError."""
        with pytest.raises(InvalidImageSizeError) as exc_info:
            validate_bounding_box((10, 20, 100, 200), image_size=(640, -1))
        assert "positive" in str(exc_info.value)


class TestValidateImageSize:
    """Test validate_image_size function (NEM-2605)."""

    def test_valid_image_size_passes(self) -> None:
        """Valid image_size should not raise."""
        validate_image_size((640, 480))  # Should not raise

    def test_large_image_size_passes(self) -> None:
        """Large valid image_size should not raise."""
        validate_image_size((4096, 2160))  # Should not raise

    def test_none_image_size_raises(self) -> None:
        """None image_size should raise InvalidImageSizeError."""
        with pytest.raises(InvalidImageSizeError) as exc_info:
            validate_image_size(None)
        assert "cannot be None" in str(exc_info.value)
        assert exc_info.value.reason == "image_size is required"

    def test_zero_width_raises(self) -> None:
        """Zero width should raise InvalidImageSizeError."""
        with pytest.raises(InvalidImageSizeError) as exc_info:
            validate_image_size((0, 480))
        assert "positive" in str(exc_info.value)
        assert exc_info.value.reason == "non-positive width"
        assert exc_info.value.image_size == (0, 480)

    def test_zero_height_raises(self) -> None:
        """Zero height should raise InvalidImageSizeError."""
        with pytest.raises(InvalidImageSizeError) as exc_info:
            validate_image_size((640, 0))
        assert "positive" in str(exc_info.value)
        assert exc_info.value.reason == "non-positive height"
        assert exc_info.value.image_size == (640, 0)

    def test_negative_width_raises(self) -> None:
        """Negative width should raise InvalidImageSizeError."""
        with pytest.raises(InvalidImageSizeError) as exc_info:
            validate_image_size((-10, 480))
        assert "positive" in str(exc_info.value)
        assert exc_info.value.reason == "non-positive width"

    def test_negative_height_raises(self) -> None:
        """Negative height should raise InvalidImageSizeError."""
        with pytest.raises(InvalidImageSizeError) as exc_info:
            validate_image_size((640, -10))
        assert "positive" in str(exc_info.value)
        assert exc_info.value.reason == "non-positive height"

    def test_both_zero_raises(self) -> None:
        """Both dimensions zero should raise (width checked first)."""
        with pytest.raises(InvalidImageSizeError) as exc_info:
            validate_image_size((0, 0))
        assert "width" in str(exc_info.value)
        assert exc_info.value.reason == "non-positive width"

    def test_both_negative_raises(self) -> None:
        """Both dimensions negative should raise (width checked first)."""
        with pytest.raises(InvalidImageSizeError) as exc_info:
            validate_image_size((-1, -1))
        assert "width" in str(exc_info.value)

    def test_non_tuple_raises(self) -> None:
        """Non-tuple image_size should raise InvalidImageSizeError."""
        with pytest.raises(InvalidImageSizeError) as exc_info:
            validate_image_size(640)  # type: ignore[arg-type]
        assert "must be a 2-tuple" in str(exc_info.value)
        assert exc_info.value.reason == "not iterable"

    def test_wrong_length_tuple_raises(self) -> None:
        """Tuple with wrong length should raise InvalidImageSizeError."""
        with pytest.raises(InvalidImageSizeError) as exc_info:
            validate_image_size((640, 480, 3))  # type: ignore[arg-type]
        assert "2-tuple" in str(exc_info.value)
        assert "got 3 elements" in str(exc_info.value)
        assert exc_info.value.reason == "must be 2-tuple"

    def test_single_element_tuple_raises(self) -> None:
        """Single-element tuple should raise InvalidImageSizeError."""
        with pytest.raises(InvalidImageSizeError) as exc_info:
            validate_image_size((640,))  # type: ignore[arg-type]
        assert "got 1 elements" in str(exc_info.value)

    def test_empty_tuple_raises(self) -> None:
        """Empty tuple should raise InvalidImageSizeError."""
        with pytest.raises(InvalidImageSizeError) as exc_info:
            validate_image_size(())  # type: ignore[arg-type]
        assert "got 0 elements" in str(exc_info.value)


class TestBoundingBoxEdgeCasesNEM2605:
    """Integration tests for NEM-2605 edge cases."""

    def test_edge_case_zero_area_x1_equals_x2(self) -> None:
        """Edge case: x1 == x2 creates zero-area box."""
        with pytest.raises(InvalidBoundingBoxError):
            validate_bounding_box((100, 50, 100, 150))

    def test_edge_case_zero_area_y1_equals_y2(self) -> None:
        """Edge case: y1 == y2 creates zero-area box."""
        with pytest.raises(InvalidBoundingBoxError):
            validate_bounding_box((50, 100, 150, 100))

    def test_edge_case_inverted_bbox(self) -> None:
        """Edge case: inverted bbox (x2 < x1, y2 < y1)."""
        with pytest.raises(InvalidBoundingBoxError):
            validate_bounding_box((100, 100, 50, 50))

    def test_edge_case_image_size_one_pixel(self) -> None:
        """Edge case: 1x1 image size is valid."""
        validate_image_size((1, 1))  # Should not raise

    def test_edge_case_bbox_with_image_size_validation_order(self) -> None:
        """Edge case: bbox validation happens before image_size validation."""
        # Invalid bbox should raise before image_size is checked
        with pytest.raises(InvalidBoundingBoxError):
            validate_bounding_box((100, 100, 50, 50), image_size=(0, 0))

    def test_edge_case_valid_bbox_invalid_image_size(self) -> None:
        """Edge case: valid bbox with invalid image_size should raise InvalidImageSizeError."""
        with pytest.raises(InvalidImageSizeError):
            validate_bounding_box((10, 10, 50, 50), image_size=(0, 100))

    def test_error_messages_are_descriptive(self) -> None:
        """Error messages should contain useful information."""
        # Test bbox error message
        try:
            validate_bounding_box((50, 0, 50, 100))
        except InvalidBoundingBoxError as e:
            assert "x1=50" in str(e)
            assert "x2=50" in str(e)

        # Test image_size error message
        try:
            validate_image_size((0, 480))
        except InvalidImageSizeError as e:
            assert "0" in str(e) or "positive" in str(e)
