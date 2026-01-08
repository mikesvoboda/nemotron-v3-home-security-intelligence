"""Tests for the consolidated exception hierarchy.

Tests the domain-specific exception hierarchy per NEM-1598:
- SecurityIntelligenceError (base)
- ServiceError -> AIServiceError -> DetectorUnavailableError, AnalyzerUnavailableError, EnrichmentUnavailableError
- DataError -> DetectionNotFoundError, EventNotFoundError, CameraNotFoundError
- ConfigurationError
- ResourceExhaustedError
"""

from backend.core.exceptions import (
    AIServiceError,
    AnalyzerUnavailableError,
    CameraNotFoundError,
    CircuitBreakerOpenError,
    ConfigurationError,
    DatabaseError,
    DetectionNotFoundError,
    DetectorUnavailableError,
    EnrichmentUnavailableError,
    EventNotFoundError,
    ExternalServiceError,
    InternalError,
    NotFoundError,
    RateLimitError,
    ResourceExhaustedError,
    SecurityIntelligenceError,
    ValidationError,
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
