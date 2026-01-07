"""Unit tests for health check schemas.

Tests for the consolidated health check response schemas defined in
backend/api/schemas/health.py. These schemas ensure consistent response
formats across all health endpoints.
"""

import pytest
from pydantic import ValidationError

from backend.api.schemas.health import (
    CheckResult,
    LivenessResponse,
    ReadinessResponse,
    SimpleReadinessResponse,
)


class TestLivenessResponse:
    """Tests for LivenessResponse schema."""

    def test_liveness_response_default_status(self) -> None:
        """LivenessResponse should have default status 'alive'."""
        response = LivenessResponse()
        assert response.status == "alive"

    def test_liveness_response_explicit_alive(self) -> None:
        """LivenessResponse should accept explicit 'alive' status."""
        response = LivenessResponse(status="alive")
        assert response.status == "alive"

    def test_liveness_response_rejects_invalid_status(self) -> None:
        """LivenessResponse should reject status values other than 'alive'."""
        with pytest.raises(ValidationError):
            LivenessResponse(status="dead")  # type: ignore[arg-type]

    def test_liveness_response_rejects_healthy(self) -> None:
        """LivenessResponse should reject 'healthy' as status (use 'alive')."""
        with pytest.raises(ValidationError):
            LivenessResponse(status="healthy")  # type: ignore[arg-type]

    def test_liveness_response_serialization(self) -> None:
        """LivenessResponse should serialize to expected JSON format."""
        response = LivenessResponse()
        data = response.model_dump()
        assert data == {"status": "alive"}

    def test_liveness_response_json_schema_example(self) -> None:
        """LivenessResponse should have a valid JSON schema example."""
        schema = LivenessResponse.model_json_schema()
        assert "example" in schema
        assert schema["example"]["status"] == "alive"


class TestCheckResult:
    """Tests for CheckResult schema."""

    def test_check_result_healthy(self) -> None:
        """CheckResult should accept healthy status."""
        result = CheckResult(status="healthy")
        assert result.status == "healthy"
        assert result.latency_ms is None
        assert result.error is None

    def test_check_result_unhealthy_with_error(self) -> None:
        """CheckResult should accept unhealthy status with error message."""
        result = CheckResult(
            status="unhealthy",
            error="Connection refused",
        )
        assert result.status == "unhealthy"
        assert result.error == "Connection refused"

    def test_check_result_degraded(self) -> None:
        """CheckResult should accept degraded status."""
        result = CheckResult(status="degraded", latency_ms=500.0)
        assert result.status == "degraded"
        assert result.latency_ms == 500.0

    def test_check_result_with_latency(self) -> None:
        """CheckResult should accept latency_ms measurement."""
        result = CheckResult(status="healthy", latency_ms=5.2)
        assert result.latency_ms == 5.2

    def test_check_result_rejects_negative_latency(self) -> None:
        """CheckResult should reject negative latency values."""
        with pytest.raises(ValidationError):
            CheckResult(status="healthy", latency_ms=-1.0)

    def test_check_result_rejects_invalid_status(self) -> None:
        """CheckResult should reject invalid status values."""
        with pytest.raises(ValidationError):
            CheckResult(status="unknown")  # type: ignore[arg-type]

    def test_check_result_serialization(self) -> None:
        """CheckResult should serialize to expected JSON format."""
        result = CheckResult(status="healthy", latency_ms=2.5, error=None)
        data = result.model_dump()
        assert data == {
            "status": "healthy",
            "latency_ms": 2.5,
            "error": None,
        }

    def test_check_result_json_schema_example(self) -> None:
        """CheckResult should have a valid JSON schema example."""
        schema = CheckResult.model_json_schema()
        assert "example" in schema
        assert schema["example"]["status"] == "healthy"


class TestReadinessResponse:
    """Tests for ReadinessResponse schema."""

    def test_readiness_response_ready(self) -> None:
        """ReadinessResponse should accept ready state with healthy checks."""
        response = ReadinessResponse(
            ready=True,
            checks={
                "database": CheckResult(status="healthy", latency_ms=2.5),
                "redis": CheckResult(status="healthy", latency_ms=1.2),
            },
        )
        assert response.ready is True
        assert len(response.checks) == 2
        assert response.checks["database"].status == "healthy"
        assert response.checks["redis"].status == "healthy"

    def test_readiness_response_not_ready(self) -> None:
        """ReadinessResponse should accept not ready state with unhealthy checks."""
        response = ReadinessResponse(
            ready=False,
            checks={
                "database": CheckResult(status="unhealthy", error="Connection refused"),
                "redis": CheckResult(status="healthy", latency_ms=1.0),
            },
        )
        assert response.ready is False
        assert response.checks["database"].status == "unhealthy"
        assert response.checks["database"].error == "Connection refused"

    def test_readiness_response_empty_checks(self) -> None:
        """ReadinessResponse should accept empty checks dict."""
        response = ReadinessResponse(ready=True, checks={})
        assert response.ready is True
        assert response.checks == {}

    def test_readiness_response_requires_ready_field(self) -> None:
        """ReadinessResponse should require the ready field."""
        with pytest.raises(ValidationError):
            ReadinessResponse(checks={})  # type: ignore[call-arg]

    def test_readiness_response_requires_checks_field(self) -> None:
        """ReadinessResponse should require the checks field."""
        with pytest.raises(ValidationError):
            ReadinessResponse(ready=True)  # type: ignore[call-arg]

    def test_readiness_response_serialization(self) -> None:
        """ReadinessResponse should serialize to expected JSON format."""
        response = ReadinessResponse(
            ready=True,
            checks={
                "database": CheckResult(status="healthy", latency_ms=2.5),
            },
        )
        data = response.model_dump()
        assert data["ready"] is True
        assert "checks" in data
        assert data["checks"]["database"]["status"] == "healthy"
        assert data["checks"]["database"]["latency_ms"] == 2.5

    def test_readiness_response_json_schema_example(self) -> None:
        """ReadinessResponse should have a valid JSON schema example."""
        schema = ReadinessResponse.model_json_schema()
        assert "example" in schema
        assert schema["example"]["ready"] is True
        assert "checks" in schema["example"]
        assert "database" in schema["example"]["checks"]

    def test_readiness_response_degraded_check(self) -> None:
        """ReadinessResponse should handle degraded service checks."""
        response = ReadinessResponse(
            ready=True,
            checks={
                "database": CheckResult(status="healthy"),
                "redis": CheckResult(status="degraded", latency_ms=500.0),
            },
        )
        assert response.checks["redis"].status == "degraded"


class TestSimpleReadinessResponse:
    """Tests for SimpleReadinessResponse schema."""

    def test_simple_readiness_ready(self) -> None:
        """SimpleReadinessResponse should accept ready state."""
        response = SimpleReadinessResponse(ready=True, status="ready")
        assert response.ready is True
        assert response.status == "ready"

    def test_simple_readiness_not_ready(self) -> None:
        """SimpleReadinessResponse should accept not_ready state."""
        response = SimpleReadinessResponse(ready=False, status="not_ready")
        assert response.ready is False
        assert response.status == "not_ready"

    def test_simple_readiness_rejects_invalid_status(self) -> None:
        """SimpleReadinessResponse should reject invalid status values."""
        with pytest.raises(ValidationError):
            SimpleReadinessResponse(ready=True, status="healthy")  # type: ignore[arg-type]

    def test_simple_readiness_requires_both_fields(self) -> None:
        """SimpleReadinessResponse should require both ready and status fields."""
        with pytest.raises(ValidationError):
            SimpleReadinessResponse(ready=True)  # type: ignore[call-arg]

        with pytest.raises(ValidationError):
            SimpleReadinessResponse(status="ready")  # type: ignore[call-arg]

    def test_simple_readiness_serialization(self) -> None:
        """SimpleReadinessResponse should serialize to expected JSON format."""
        response = SimpleReadinessResponse(ready=True, status="ready")
        data = response.model_dump()
        assert data == {"ready": True, "status": "ready"}

    def test_simple_readiness_json_schema_example(self) -> None:
        """SimpleReadinessResponse should have a valid JSON schema example."""
        schema = SimpleReadinessResponse.model_json_schema()
        assert "example" in schema
        assert schema["example"]["ready"] is True
        assert schema["example"]["status"] == "ready"


class TestHealthSchemaConsistency:
    """Tests for consistency across health schemas."""

    def test_liveness_is_minimal(self) -> None:
        """LivenessResponse should have minimal fields (only status)."""
        fields = set(LivenessResponse.model_fields.keys())
        assert fields == {"status"}

    def test_check_result_has_standard_fields(self) -> None:
        """CheckResult should have standard health check fields."""
        fields = set(CheckResult.model_fields.keys())
        assert fields == {"status", "latency_ms", "error"}

    def test_readiness_has_required_structure(self) -> None:
        """ReadinessResponse should have ready bool and checks dict."""
        response = ReadinessResponse(ready=True, checks={})
        assert isinstance(response.ready, bool)
        assert isinstance(response.checks, dict)

    def test_simple_readiness_is_subset_of_full(self) -> None:
        """SimpleReadinessResponse fields should be a subset of response needs."""
        simple_fields = set(SimpleReadinessResponse.model_fields.keys())
        # Simple response should have exactly ready and status
        assert simple_fields == {"ready", "status"}
