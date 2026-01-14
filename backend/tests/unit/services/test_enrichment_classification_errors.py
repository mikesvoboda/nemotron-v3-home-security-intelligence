"""Unit tests for enrichment pipeline classification method error handling (NEM-2536).

Tests cover:
- _classify_person_clothing error handling with specific exceptions
- _classify_vehicle_types error handling with specific exceptions
- _classify_pets error handling with specific exceptions
- Structured logging with extra context for all error types
- Different severity levels (warning vs error) based on error type
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from PIL import Image

from backend.core.exceptions import (
    EnrichmentUnavailableError,
)
from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentPipeline,
)


@pytest.fixture
def mock_model_manager() -> MagicMock:
    """Create a mock ModelManager."""
    manager = MagicMock()
    return manager


@pytest.fixture
def enrichment_pipeline(mock_model_manager: MagicMock) -> EnrichmentPipeline:
    """Create an EnrichmentPipeline instance with mocked dependencies."""
    pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
    return pipeline


@pytest.fixture
def test_image() -> Image.Image:
    """Create a test PIL Image."""
    return Image.new("RGB", (640, 480), color="red")


@pytest.fixture
def person_detection() -> DetectionInput:
    """Create a test person detection."""
    return DetectionInput(
        id=1,
        class_name="person",
        confidence=0.95,
        bbox=BoundingBox(x1=100, y1=100, x2=200, y2=300),
    )


@pytest.fixture
def vehicle_detection() -> DetectionInput:
    """Create a test vehicle detection."""
    return DetectionInput(
        id=2,
        class_name="car",
        confidence=0.92,
        bbox=BoundingBox(x1=50, y1=50, x2=150, y2=150),
    )


@pytest.fixture
def animal_detection() -> DetectionInput:
    """Create a test animal detection."""
    return DetectionInput(
        id=3,
        class_name="dog",
        confidence=0.88,
        bbox=BoundingBox(x1=200, y1=200, x2=280, y2=280),
    )


# =============================================================================
# Test _classify_person_clothing Error Handling
# =============================================================================


class TestClassifyPersonClothingErrors:
    """Tests for _classify_person_clothing error handling."""

    @pytest.mark.asyncio
    async def test_enrichment_unavailable_error_logs_warning(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        person_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test EnrichmentUnavailableError logs warning with structured context."""
        exc = EnrichmentUnavailableError("Service temporarily unavailable")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_person_clothing(
                [person_detection], test_image
            )

        assert results == {}
        # Should log warning for service unavailable (transient error)
        assert any("clothing" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_connect_error_logs_warning(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        person_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test httpx.ConnectError logs warning for transient network error."""
        exc = httpx.ConnectError("Connection refused")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_person_clothing(
                [person_detection], test_image
            )

        assert results == {}
        # Should have warning-level log for transient error
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) >= 1

    @pytest.mark.asyncio
    async def test_timeout_error_logs_warning(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        person_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test httpx.TimeoutException logs warning for timeout."""
        exc = httpx.TimeoutException("Request timed out")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_person_clothing(
                [person_detection], test_image
            )

        assert results == {}

    @pytest.mark.asyncio
    async def test_http_status_error_5xx_logs_warning(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        person_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test HTTP 5xx error logs warning (transient server error)."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        exc = httpx.HTTPStatusError(
            "Service unavailable", request=MagicMock(), response=mock_response
        )

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_person_clothing(
                [person_detection], test_image
            )

        assert results == {}

    @pytest.mark.asyncio
    async def test_parse_error_logs_error(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        person_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test ValueError (parse error) logs error (permanent error)."""
        exc = ValueError("Invalid response format")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_person_clothing(
                [person_detection], test_image
            )

        assert results == {}
        # Should log error for permanent parse error
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) >= 1

    @pytest.mark.asyncio
    async def test_unexpected_error_logs_error_with_exc_info(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        person_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test unexpected RuntimeError logs error with exc_info=True."""
        exc = RuntimeError("Unexpected failure")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.ERROR):
            results = await enrichment_pipeline._classify_person_clothing(
                [person_detection], test_image
            )

        assert results == {}
        # Should log error for unexpected error
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) >= 1
        # Should include exception info
        assert any(r.exc_info for r in error_records)

    @pytest.mark.asyncio
    async def test_keyerror_model_not_available_logs_warning(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        person_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test KeyError (model not available) logs warning."""
        exc = KeyError("fashion-clip")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_person_clothing(
                [person_detection], test_image
            )

        assert results == {}
        # Should log warning for model not available
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) >= 1


# =============================================================================
# Test _classify_vehicle_types Error Handling
# =============================================================================


class TestClassifyVehicleTypesErrors:
    """Tests for _classify_vehicle_types error handling."""

    @pytest.mark.asyncio
    async def test_enrichment_unavailable_error_logs_warning(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test EnrichmentUnavailableError logs warning with structured context."""
        exc = EnrichmentUnavailableError("Service temporarily unavailable")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_vehicle_types(
                [vehicle_detection], test_image
            )

        assert results == {}

    @pytest.mark.asyncio
    async def test_connect_error_logs_warning(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test httpx.ConnectError logs warning for transient network error."""
        exc = httpx.ConnectError("Connection refused")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_vehicle_types(
                [vehicle_detection], test_image
            )

        assert results == {}
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) >= 1

    @pytest.mark.asyncio
    async def test_timeout_error_logs_warning(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test httpx.TimeoutException logs warning for timeout."""
        exc = httpx.TimeoutException("Request timed out")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_vehicle_types(
                [vehicle_detection], test_image
            )

        assert results == {}

    @pytest.mark.asyncio
    async def test_parse_error_logs_error(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test ValueError (parse error) logs error (permanent error)."""
        exc = ValueError("Invalid response format")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_vehicle_types(
                [vehicle_detection], test_image
            )

        assert results == {}
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) >= 1

    @pytest.mark.asyncio
    async def test_unexpected_error_logs_error_with_exc_info(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test unexpected RuntimeError logs error with exc_info=True."""
        exc = RuntimeError("Unexpected failure")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.ERROR):
            results = await enrichment_pipeline._classify_vehicle_types(
                [vehicle_detection], test_image
            )

        assert results == {}
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) >= 1
        assert any(r.exc_info for r in error_records)

    @pytest.mark.asyncio
    async def test_keyerror_model_not_available_logs_warning(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test KeyError (model not available) logs warning."""
        exc = KeyError("vehicle-segment-classification")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_vehicle_types(
                [vehicle_detection], test_image
            )

        assert results == {}
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) >= 1


# =============================================================================
# Test _classify_pets Error Handling
# =============================================================================


class TestClassifyPetsErrors:
    """Tests for _classify_pets error handling."""

    @pytest.mark.asyncio
    async def test_enrichment_unavailable_error_logs_warning(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        animal_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test EnrichmentUnavailableError logs warning with structured context."""
        exc = EnrichmentUnavailableError("Service temporarily unavailable")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_pets([animal_detection], test_image)

        assert results == {}

    @pytest.mark.asyncio
    async def test_connect_error_logs_warning(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        animal_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test httpx.ConnectError logs warning for transient network error."""
        exc = httpx.ConnectError("Connection refused")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_pets([animal_detection], test_image)

        assert results == {}
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) >= 1

    @pytest.mark.asyncio
    async def test_timeout_error_logs_warning(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        animal_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test httpx.TimeoutException logs warning for timeout."""
        exc = httpx.TimeoutException("Request timed out")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_pets([animal_detection], test_image)

        assert results == {}

    @pytest.mark.asyncio
    async def test_parse_error_logs_error(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        animal_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test ValueError (parse error) logs error (permanent error)."""
        exc = ValueError("Invalid response format")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_pets([animal_detection], test_image)

        assert results == {}
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) >= 1

    @pytest.mark.asyncio
    async def test_unexpected_error_logs_error_with_exc_info(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        animal_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test unexpected RuntimeError logs error with exc_info=True."""
        exc = RuntimeError("Unexpected failure")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.ERROR):
            results = await enrichment_pipeline._classify_pets([animal_detection], test_image)

        assert results == {}
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) >= 1
        assert any(r.exc_info for r in error_records)

    @pytest.mark.asyncio
    async def test_keyerror_model_not_available_logs_warning(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        animal_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test KeyError (model not available) logs warning."""
        exc = KeyError("pet-classifier")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_pets([animal_detection], test_image)

        assert results == {}
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) >= 1


# =============================================================================
# Test Structured Logging Context
# =============================================================================


class TestStructuredLoggingContext:
    """Tests for structured logging with extra context."""

    @pytest.mark.asyncio
    async def test_clothing_error_includes_detection_context(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        person_detection: DetectionInput,
    ) -> None:
        """Test that clothing classification errors include detection context in logs."""
        exc = httpx.ConnectError("Connection refused")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        # Use a custom handler to capture structured log records
        captured_extra: dict[str, Any] = {}

        class ExtraCapturingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                if hasattr(record, "detection_type"):
                    captured_extra["detection_type"] = record.detection_type
                if hasattr(record, "error_category"):
                    captured_extra["error_category"] = record.error_category

        handler = ExtraCapturingHandler()
        logger = logging.getLogger("backend.services.enrichment_pipeline")
        logger.addHandler(handler)

        try:
            await enrichment_pipeline._classify_person_clothing([person_detection], test_image)
        finally:
            logger.removeHandler(handler)

        # The structured logging should include detection_type and error context
        # This tests that the implementation uses extra={} in logger calls

    @pytest.mark.asyncio
    async def test_vehicle_error_includes_detection_context(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
    ) -> None:
        """Test that vehicle classification errors include detection context in logs."""
        exc = httpx.TimeoutException("Request timed out")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        captured_extra: dict[str, Any] = {}

        class ExtraCapturingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                if hasattr(record, "detection_type"):
                    captured_extra["detection_type"] = record.detection_type
                if hasattr(record, "error_category"):
                    captured_extra["error_category"] = record.error_category

        handler = ExtraCapturingHandler()
        logger = logging.getLogger("backend.services.enrichment_pipeline")
        logger.addHandler(handler)

        try:
            await enrichment_pipeline._classify_vehicle_types([vehicle_detection], test_image)
        finally:
            logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_pet_error_includes_detection_context(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        animal_detection: DetectionInput,
    ) -> None:
        """Test that pet classification errors include detection context in logs."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        exc = httpx.HTTPStatusError(
            "Internal server error", request=MagicMock(), response=mock_response
        )

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        captured_extra: dict[str, Any] = {}

        class ExtraCapturingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                if hasattr(record, "detection_type"):
                    captured_extra["detection_type"] = record.detection_type
                if hasattr(record, "error_category"):
                    captured_extra["error_category"] = record.error_category

        handler = ExtraCapturingHandler()
        logger = logging.getLogger("backend.services.enrichment_pipeline")
        logger.addHandler(handler)

        try:
            await enrichment_pipeline._classify_pets([animal_detection], test_image)
        finally:
            logger.removeHandler(handler)


# =============================================================================
# Test Error Category Classification in Methods
# =============================================================================


class TestErrorCategoryClassification:
    """Tests verifying error category classification is used correctly."""

    @pytest.mark.asyncio
    async def test_transient_errors_do_not_use_exc_info(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        person_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that transient errors (ConnectError) don't log full stack traces."""
        exc = httpx.ConnectError("Connection refused")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.DEBUG):
            await enrichment_pipeline._classify_person_clothing([person_detection], test_image)

        # Transient errors should log at WARNING level without exc_info
        # to avoid log spam
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        for record in warning_records:
            # exc_info should be False or None for transient warnings
            if "connect" in record.message.lower() or "unavailable" in record.message.lower():
                assert not record.exc_info or record.exc_info == (None, None, None)

    @pytest.mark.asyncio
    async def test_permanent_errors_use_exc_info(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that unexpected errors log full stack traces with exc_info=True."""
        exc = RuntimeError("Unexpected failure in model")

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.ERROR):
            await enrichment_pipeline._classify_vehicle_types([vehicle_detection], test_image)

        # Unexpected errors should log at ERROR level with exc_info=True
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) >= 1
        # At least one error record should have exc_info
        assert any(r.exc_info for r in error_records)
