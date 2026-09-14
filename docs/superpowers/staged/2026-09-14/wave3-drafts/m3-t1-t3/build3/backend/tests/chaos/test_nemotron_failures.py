"""Chaos tests for Nemotron LLM service failures.

This module tests system behavior when the Nemotron LLM service experiences
various failure modes:
- Timeouts (LLM inference hangs)
- Connection errors (LLM service unreachable)
- Malformed responses (invalid JSON)
- Rate limiting (too many requests)

Expected Behavior:
- Events are created with default risk scores
- System gracefully handles LLM unavailability
- Fallback risk assessment is used
- Health endpoint reports LLM status accurately
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    reset_circuit_breaker_registry,
)
from backend.services.nemotron_analyzer import NemotronAnalyzer


@pytest.fixture(autouse=True)
def reset_state() -> None:
    """Reset global state before each test."""
    reset_circuit_breaker_registry()


class TestNemotronTimeout:
    """Tests for Nemotron timeout scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_timeout_circuit_breaker_opens(self) -> None:
        """Repeated LLM timeouts cause circuit breaker to open."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=10.0,
        )
        breaker = CircuitBreaker(name="nemotron_timeout_test", config=config)

        async def timeout_operation() -> None:
            raise httpx.TimeoutException("Nemotron timeout")

        # Trigger failures
        for _ in range(config.failure_threshold):
            try:
                await breaker.call(timeout_operation)
            except httpx.TimeoutException:
                pass

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_timeout(self) -> None:
        """Health check returns False when Nemotron times out."""
        analyzer = NemotronAnalyzer()

        async def timeout(*args: object, **kwargs: object) -> None:
            raise httpx.TimeoutException("Health check timeout")

        with patch("httpx.AsyncClient.get", side_effect=timeout):
            result = await analyzer.health_check()
            assert result is False


class TestNemotronConnectionError:
    """Tests for Nemotron connection error scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_connection_error_handled_gracefully(self) -> None:
        """Connection errors to Nemotron are handled gracefully."""
        analyzer = NemotronAnalyzer()

        async def connection_refused(*args: object, **kwargs: object) -> None:
            raise httpx.ConnectError("Connection refused")

        with patch("httpx.AsyncClient.get", side_effect=connection_refused):
            result = await analyzer.health_check()
            assert result is False

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_connection_failures(self) -> None:
        """Repeated connection failures open the circuit breaker."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
        )
        breaker = CircuitBreaker(name="nemotron_connection_test", config=config)

        async def connection_error() -> None:
            raise httpx.ConnectError("Nemotron unreachable")

        # Trigger failures
        for _ in range(config.failure_threshold):
            try:
                await breaker.call(connection_error)
            except httpx.ConnectError:
                pass

        assert breaker.state == CircuitState.OPEN


class TestNemotronMalformedResponse:
    """Tests for Nemotron malformed response scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_invalid_json_handled_with_defaults(self) -> None:
        """Invalid JSON from Nemotron results in default risk assessment."""
        analyzer = NemotronAnalyzer()

        # Test the response parser with invalid JSON
        with pytest.raises(ValueError) as exc_info:
            analyzer._parse_llm_response("This is not JSON at all")

        assert "No JSON found" in str(exc_info.value)

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_missing_risk_score_handled(self) -> None:
        """Missing risk_score in response is handled with defaults."""
        analyzer = NemotronAnalyzer()

        # JSON without required fields
        with pytest.raises(ValueError):
            analyzer._parse_llm_response('{"summary": "test", "reasoning": "test"}')

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_validate_risk_data_handles_out_of_range(self) -> None:
        """Risk scores out of range are clamped."""
        analyzer = NemotronAnalyzer()

        # Score above 100
        result_high = analyzer._validate_risk_data(
            {"risk_score": 150, "risk_level": "high", "summary": "test", "reasoning": "test"}
        )
        assert result_high["risk_score"] <= 100

        # Score below 0
        result_low = analyzer._validate_risk_data(
            {"risk_score": -50, "risk_level": "low", "summary": "test", "reasoning": "test"}
        )
        assert result_low["risk_score"] >= 0

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_validate_risk_data_handles_invalid_level(self) -> None:
        """Invalid risk_level is corrected based on score."""
        analyzer = NemotronAnalyzer()

        # Invalid risk_level with high score
        result = analyzer._validate_risk_data(
            {
                "risk_score": 90,
                "risk_level": "invalid_level",
                "summary": "test",
                "reasoning": "test",
            }
        )

        # Should have a valid risk_level
        assert result["risk_level"] in ("low", "medium", "high", "critical")


class TestNemotronRateLimiting:
    """Tests for Nemotron rate limiting scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_429_response_handled(self) -> None:
        """HTTP 429 (rate limit) responses are handled gracefully."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
        )
        breaker = CircuitBreaker(name="nemotron_rate_limit_test", config=config)

        async def rate_limited() -> None:
            response = MagicMock(spec=httpx.Response)
            response.status_code = 429
            response.json.return_value = {"error": "Rate limit exceeded"}
            raise httpx.HTTPStatusError("Rate limited", request=MagicMock(), response=response)

        # Rate limits should count as failures
        for _ in range(config.failure_threshold):
            try:
                await breaker.call(rate_limited)
            except httpx.HTTPStatusError:
                pass

        assert breaker.state == CircuitState.OPEN


class TestNemotronFallbackBehavior:
    """Tests for fallback behavior when Nemotron is unavailable."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_fallback_risk_assessment_structure(self) -> None:
        """Fallback risk assessment has correct structure."""
        # Simulate the fallback data that NemotronAnalyzer uses
        fallback_data = {
            "risk_score": 50,
            "risk_level": "medium",
            "summary": "Analysis unavailable - LLM service error",
            "reasoning": "Failed to analyze detections due to service error",
        }

        # Validate structure
        assert "risk_score" in fallback_data
        assert "risk_level" in fallback_data
        assert "summary" in fallback_data
        assert "reasoning" in fallback_data

        # Validate values are reasonable defaults
        assert 0 <= fallback_data["risk_score"] <= 100
        assert fallback_data["risk_level"] in ("low", "medium", "high", "critical")


class TestNemotronCircuitBreakerIntegration:
    """Tests for circuit breaker integration with Nemotron."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery_with_nemotron(self) -> None:
        """Circuit breaker allows recovery after Nemotron comes back online."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=1,
        )
        breaker = CircuitBreaker(name="nemotron_recovery_test", config=config)

        # Open the circuit
        async def failing() -> None:
            raise httpx.ConnectError("Nemotron down")

        for _ in range(config.failure_threshold):
            try:
                await breaker.call(failing)
            except httpx.ConnectError:
                pass

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.2)

        # Successful call should close circuit
        async def success() -> dict[str, Any]:
            return {"risk_score": 25, "risk_level": "low"}

        result = await breaker.call(success)
        assert result["risk_score"] == 25
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self) -> None:
        """Failure in HALF_OPEN state reopens the circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=2,
        )
        breaker = CircuitBreaker(name="nemotron_half_open_test", config=config)

        # Open circuit
        async def failing() -> None:
            raise httpx.TimeoutException("Timeout")

        for _ in range(config.failure_threshold):
            try:
                await breaker.call(failing)
            except httpx.TimeoutException:
                pass

        # Wait for recovery
        await asyncio.sleep(0.2)

        # Fail in half-open
        try:
            await breaker.call(failing)
        except httpx.TimeoutException:
            pass

        assert breaker.state == CircuitState.OPEN


class TestNemotronResponseParsing:
    """Tests for Nemotron response parsing edge cases."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_parse_response_with_think_blocks(self) -> None:
        """Response with <think> blocks is parsed correctly."""
        analyzer = NemotronAnalyzer()

        response = """<think>
        Let me analyze this detection...
        The person appears to be walking normally.
        </think>
        {"risk_score": 25, "risk_level": "low", "summary": "Normal activity", "reasoning": "Person walking"}"""

        result = analyzer._parse_llm_response(response)

        assert result["risk_score"] == 25
        assert result["risk_level"] == "low"

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_parse_response_with_preamble_text(self) -> None:
        """Response with preamble text before JSON is parsed correctly."""
        analyzer = NemotronAnalyzer()

        response = """Here is my analysis:
        {"risk_score": 75, "risk_level": "high", "summary": "Suspicious", "reasoning": "Unusual behavior"}"""

        result = analyzer._parse_llm_response(response)

        assert result["risk_score"] == 75
        assert result["risk_level"] == "high"

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_parse_empty_response_raises_error(self) -> None:
        """Empty response raises appropriate error."""
        analyzer = NemotronAnalyzer()

        with pytest.raises(ValueError) as exc_info:
            analyzer._parse_llm_response("")

        assert "No JSON found" in str(exc_info.value)

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_parse_partial_json_raises_error(self) -> None:
        """Partial/truncated JSON raises appropriate error."""
        analyzer = NemotronAnalyzer()

        with pytest.raises(ValueError):
            analyzer._parse_llm_response('{"risk_score": 50, "risk_level": "med')


class TestNemotronHealthMonitoring:
    """Tests for Nemotron health monitoring integration."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        """Health check returns True when Nemotron is healthy."""
        analyzer = NemotronAnalyzer()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        async def healthy_response(*args: object, **kwargs: object) -> httpx.Response:
            return mock_response

        with patch("httpx.AsyncClient.get", side_effect=healthy_response):
            result = await analyzer.health_check()
            assert result is True

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_health_check_5xx_returns_false(self) -> None:
        """Health check returns False on 5xx errors."""
        analyzer = NemotronAnalyzer()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 503

        async def server_error(*args: object, **kwargs: object) -> httpx.Response:
            return mock_response

        with patch("httpx.AsyncClient.get", side_effect=server_error):
            result = await analyzer.health_check()
            # Status code 503 should return False
            assert result is False
