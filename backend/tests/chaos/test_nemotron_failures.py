"""Chaos tests for LLM-service failure modes at the circuit breaker.

R8 (2026-09-29) retired ``backend.services.nemotron_analyzer``, and with it the
suite that drove these scenarios through ``NemotronAnalyzer`` directly: the
``health_check()`` pins, the ``_parse_llm_response`` / ``_validate_risk_data``
pins, and the "fallback risk assessment structure" pin (which asserted the
shape of a literal dict). Those subjects no longer exist, so they went —
the analyzer's parse/validate/fallback behaviour now lives on the VLM path and
is pinned in backend/tests/unit/services/test_vlm_analyzer.py and
test_vlm_client.py.

What survives here is the failure-mode half: the LLM service going down is
still an httpx timeout / connection error / 5xx / 429, and the product's
response to that is the circuit breaker (``backend.services.circuit_breaker``),
which the shipped ``VlmClient`` guards itself with (BREAKER_NAME "ai-vlm",
vlm_client.py:247). These are the chaos-shaped versions of that contract:
repeated failures open the breaker, recovery closes it, a half-open failure
reopens it.

Expected Behavior:
- Repeated LLM timeouts / connection errors open the circuit breaker
- A rate-limit (429) counts as a failure
- The breaker recovers once the service answers again
- A failure in HALF_OPEN reopens the circuit
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    reset_circuit_breaker_registry,
)


@pytest.fixture(autouse=True)
def reset_state() -> None:
    """Reset global state before each test."""
    reset_circuit_breaker_registry()


class TestLlmTimeout:
    """Tests for LLM timeout scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_timeout_circuit_breaker_opens(self) -> None:
        """Repeated LLM timeouts cause circuit breaker to open."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=10.0,
        )
        breaker = CircuitBreaker(name="vlm_timeout_test", config=config)

        async def timeout_operation() -> None:
            raise httpx.TimeoutException("VLM timeout")

        # Trigger failures
        for _ in range(config.failure_threshold):
            try:
                await breaker.call(timeout_operation)
            except httpx.TimeoutException:
                pass

        assert breaker.state == CircuitState.OPEN


class TestLlmConnectionError:
    """Tests for LLM connection error scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_connection_failures(self) -> None:
        """Repeated connection failures open the circuit breaker."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
        )
        breaker = CircuitBreaker(name="vlm_connection_test", config=config)

        async def connection_error() -> None:
            raise httpx.ConnectError("VLM unreachable")

        # Trigger failures
        for _ in range(config.failure_threshold):
            try:
                await breaker.call(connection_error)
            except httpx.ConnectError:
                pass

        assert breaker.state == CircuitState.OPEN


class TestLlmRateLimiting:
    """Tests for LLM rate limiting scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_429_response_handled(self) -> None:
        """HTTP 429 (rate limit) responses are handled gracefully."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
        )
        breaker = CircuitBreaker(name="vlm_rate_limit_test", config=config)

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


class TestLlmCircuitBreakerIntegration:
    """Tests for circuit breaker integration with the LLM service."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery_with_llm(self) -> None:
        """Circuit breaker allows recovery after the LLM comes back online."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=1,
        )
        breaker = CircuitBreaker(name="vlm_recovery_test", config=config)

        # Open the circuit
        async def failing() -> None:
            raise httpx.ConnectError("VLM down")

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
        breaker = CircuitBreaker(name="vlm_half_open_test", config=config)

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
