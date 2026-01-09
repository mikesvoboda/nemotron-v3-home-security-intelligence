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

from backend.core.exceptions import (
    AIServiceError,
    AlertCreationError,
    AnalyzerUnavailableError,
    BaselineNotFoundError,
    BoundingBoxOutOfBoundsError,
    BoundingBoxValidationError,
    CameraNotFoundError,
    CertificateNotFoundError,
    CertificateValidationError,
    CircuitBreakerOpenError,
    ClipGenerationError,
    CLIPUnavailableError,
    ConfigurationError,
    DatabaseError,
    DetectionNotFoundError,
    DetectorUnavailableError,
    EnrichmentUnavailableError,
    EventNotFoundError,
    ExternalServiceError,
    FlorenceUnavailableError,
    InternalError,
    InvalidBoundingBoxError,
    InvalidEmbeddingError,
    LLMResponseParseError,
    NotFoundError,
    ProcessingError,
    PromptVersionConflictError,
    RateLimitError,
    ResourceExhaustedError,
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
        assert exc.service_name == "rtdetr"

    def test_database_error(self) -> None:
        exc = DatabaseError()
        assert exc.status_code == 503
        assert exc.error_code == "DATABASE_ERROR"

    def test_circuit_breaker_open_error(self) -> None:
        exc = CircuitBreakerOpenError(service_name="rtdetr", recovery_timeout=30.0)
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
        assert exc.service_name == "rtdetr"
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
        exc = ConfigurationError("Missing required setting: RTDETR_URL")
        assert exc.message == "Missing required setting: RTDETR_URL"


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
        exc = DetectorUnavailableError("RT-DETR timeout")
        result = exc.to_dict()
        assert result["code"] == "DETECTOR_UNAVAILABLE"
        assert result["message"] == "RT-DETR timeout"

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
            service_name="rtdetr",
            endpoint="/detect",
            method="POST",
            duration_ms=150.5,
            attempt_number=1,
            max_attempts=3,
        )
        assert context.service_name == "rtdetr"
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
            service_name="rtdetr",
            endpoint="/detect",
            method="POST",
            duration_ms=60500.0,
            attempt_number=3,
            max_attempts=3,
            circuit_state="open",
        )
        original = TimeoutError("Request timed out")
        exc = DetectorUnavailableError(
            "RT-DETR detection failed after 3 attempts",
            original_error=original,
            context=context,
        )
        assert exc.context is context
        assert exc.original_error is original
        assert exc.service_name == "rtdetr"

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
            service_name="rtdetr",
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
        assert log_dict["service_name"] == "rtdetr"
        assert log_dict["status_code"] == 503

        # Check context info
        assert log_dict["context"]["service_name"] == "rtdetr"
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
        assert log_dict["service_name"] == "rtdetr"
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
