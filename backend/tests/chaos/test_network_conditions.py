"""Chaos tests for adverse network conditions.

This module tests system behavior under various network conditions:
- High latency (500ms+ added to all calls)
- Packet loss (random connection drops)
- Bandwidth limitations (slow data transfer)
- DNS failures (hostname resolution failures)

Expected Behavior:
- System continues to operate under high latency
- Retries handle intermittent packet loss
- Circuit breakers open under sustained issues
- Appropriate timeouts prevent hanging
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from backend.core.redis import RedisClient
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


class TestHighLatency:
    """Tests for high network latency scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_circuit_breaker_handles_slow_responses(self) -> None:
        """Circuit breaker correctly handles slow but successful responses."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=10.0,
        )
        breaker = CircuitBreaker(name="latency_test", config=config)

        async def slow_but_successful() -> str:
            await asyncio.sleep(0.1)  # Simulate latency
            return "success"

        # Slow responses should still be successful
        for _ in range(5):
            result = await breaker.call(slow_but_successful)
            assert result == "success"

        # Circuit should remain closed
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_high_latency_with_timeout_triggers_failure(self) -> None:
        """High latency that exceeds timeout triggers circuit breaker."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=10.0,
        )
        breaker = CircuitBreaker(name="latency_timeout_test", config=config)

        async def exceeds_timeout() -> None:
            await asyncio.sleep(0.1)
            raise TimeoutError("Operation timed out")

        # Timeouts should count as failures
        for _ in range(config.failure_threshold):
            try:
                await breaker.call(exceeds_timeout)
            except TimeoutError:
                pass

        assert breaker.state == CircuitState.OPEN


class TestPacketLoss:
    """Tests for packet loss / intermittent connection scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_intermittent_failures_with_retry_succeeds(self) -> None:
        """Operations succeed after retry when packet loss is intermittent."""
        from redis.exceptions import ConnectionError as RedisConnectionError

        call_count = 0

        async def intermittent_failure() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # Use Redis ConnectionError which with_retry handles
                raise RedisConnectionError("Connection reset")
            return "success"

        # Use Redis client's retry mechanism
        client = RedisClient()

        result = await client.with_retry(
            intermittent_failure, operation_name="test_op", max_retries=5
        )

        assert result == "success"
        assert call_count == 3  # Failed twice, succeeded on third

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_sustained_packet_loss_opens_circuit(self) -> None:
        """Sustained packet loss eventually opens the circuit breaker."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
        )
        breaker = CircuitBreaker(name="packet_loss_test", config=config)

        async def always_fails() -> None:
            raise httpx.ConnectError("Connection reset by peer")

        # Sustained failures should open circuit
        for _ in range(config.failure_threshold):
            try:
                await breaker.call(always_fails)
            except httpx.ConnectError:
                pass

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_random_failures_tracked_correctly(self) -> None:
        """Random intermittent failures are tracked correctly."""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=10.0,
        )
        breaker = CircuitBreaker(name="random_failure_test", config=config)

        call_count = 0
        failure_pattern = [True, False, True, False, False]  # Alternating

        async def random_failure() -> str:
            nonlocal call_count
            should_fail = failure_pattern[call_count % len(failure_pattern)]
            call_count += 1
            if should_fail:
                raise httpx.ConnectError("Random failure")
            return "success"

        # Make several calls
        successes = 0
        failures = 0
        for _ in range(5):
            try:
                await breaker.call(random_failure)
                successes += 1
            except httpx.ConnectError:
                failures += 1

        # Should have both successes and failures
        assert successes > 0
        assert failures > 0

        # Circuit should still be closed (successes reset counter)
        assert breaker.state == CircuitState.CLOSED


class TestDNSFailures:
    """Tests for DNS resolution failure scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_dns_failure_handled_as_connection_error(self) -> None:
        """DNS resolution failures are handled like connection errors."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=10.0,
        )
        breaker = CircuitBreaker(name="dns_failure_test", config=config)

        async def dns_failure() -> None:
            # DNS failures typically manifest as connection errors
            raise httpx.ConnectError("Name or service not known")

        for _ in range(config.failure_threshold):
            try:
                await breaker.call(dns_failure)
            except httpx.ConnectError:
                pass

        assert breaker.state == CircuitState.OPEN


class TestNetworkPartitions:
    """Tests for network partition scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_partial_partition_affects_some_services(self) -> None:
        """Network partition affecting some services is handled correctly."""
        # Create separate circuit breakers for different services
        yolo26_breaker = CircuitBreaker(
            name="yolo26_partition",
            config=CircuitBreakerConfig(failure_threshold=2),
        )
        nemotron_breaker = CircuitBreaker(
            name="nemotron_partition",
            config=CircuitBreakerConfig(failure_threshold=2),
        )

        async def yolo26_partitioned() -> None:
            raise httpx.ConnectError("Network unreachable")

        async def nemotron_ok() -> str:
            return "success"

        # YOLO26 is partitioned
        for _ in range(2):
            try:
                await yolo26_breaker.call(yolo26_partitioned)
            except httpx.ConnectError:
                pass

        # Nemotron is fine
        result = await nemotron_breaker.call(nemotron_ok)

        assert yolo26_breaker.state == CircuitState.OPEN
        assert nemotron_breaker.state == CircuitState.CLOSED
        assert result == "success"


class TestRetryWithBackoff:
    """Tests for retry with exponential backoff behavior."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_exponential_backoff_delays_increase(self) -> None:
        """Verify exponential backoff delays increase with each retry."""
        client = RedisClient()

        # Test the backoff calculation
        delay1 = client._calculate_backoff_delay(1)
        delay2 = client._calculate_backoff_delay(2)
        delay3 = client._calculate_backoff_delay(3)

        # Base delays should increase exponentially
        # Note: jitter adds randomness, so we check the trend
        assert delay2 > delay1 * 0.5  # Account for jitter
        assert delay3 > delay2 * 0.5

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_backoff_respects_max_delay(self) -> None:
        """Verify exponential backoff is capped at max delay."""
        client = RedisClient()

        # Even with many retries, delay should be capped
        max_delay = client._max_delay
        delay_10 = client._calculate_backoff_delay(10)

        # Should not exceed max_delay + jitter
        assert delay_10 <= max_delay * 1.5  # Account for jitter


class TestConnectionPoolExhaustion:
    """Tests for connection pool exhaustion under load."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_pool_exhaustion_handled_gracefully(self) -> None:
        """Connection pool exhaustion is handled without crashing."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=10.0,
        )
        breaker = CircuitBreaker(name="pool_exhaustion_test", config=config)

        async def pool_exhausted() -> None:
            raise httpx.PoolTimeout("Pool exhausted, no connections available")

        for _ in range(config.failure_threshold):
            try:
                await breaker.call(pool_exhausted)
            except httpx.PoolTimeout:
                pass

        # Pool exhaustion should be treated as a failure
        assert breaker.state == CircuitState.OPEN


class TestNetworkRecovery:
    """Tests for network recovery scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_circuit_recovers_after_network_heals(self) -> None:
        """Circuit breaker recovers after network issues resolve."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=1,
        )
        breaker = CircuitBreaker(name="network_recovery_test", config=config)

        # Fail the circuit
        async def network_down() -> None:
            raise httpx.ConnectError("Network down")

        for _ in range(config.failure_threshold):
            try:
                await breaker.call(network_down)
            except httpx.ConnectError:
                pass

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.2)

        # Network heals
        async def network_up() -> str:
            return "success"

        result = await breaker.call(network_up)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_flapping_network_keeps_circuit_open(self) -> None:
        """Flapping network (up/down/up/down) keeps circuit open."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=2,
        )
        breaker = CircuitBreaker(name="flapping_test", config=config)

        async def network_down() -> None:
            raise httpx.ConnectError("Network down")

        async def network_up() -> str:
            return "success"

        # Open the circuit
        for _ in range(config.failure_threshold):
            try:
                await breaker.call(network_down)
            except httpx.ConnectError:
                pass

        # Wait for recovery
        await asyncio.sleep(0.2)

        # One success in half-open
        await breaker.call(network_up)

        # Fail again - should reopen
        try:
            await breaker.call(network_down)
        except httpx.ConnectError:
            pass

        # Circuit should be back to open
        assert breaker.state == CircuitState.OPEN


class TestTimeoutHandling:
    """Tests for timeout handling under various conditions."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_read_timeout_handled(self) -> None:
        """Read timeout (data transfer too slow) is handled correctly."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker(name="read_timeout_test", config=config)

        async def read_timeout() -> None:
            raise httpx.ReadTimeout("Timed out reading response body")

        for _ in range(config.failure_threshold):
            try:
                await breaker.call(read_timeout)
            except httpx.ReadTimeout:
                pass

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_write_timeout_handled(self) -> None:
        """Write timeout (request upload too slow) is handled correctly."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker(name="write_timeout_test", config=config)

        async def write_timeout() -> None:
            raise httpx.WriteTimeout("Timed out writing request body")

        for _ in range(config.failure_threshold):
            try:
                await breaker.call(write_timeout)
            except httpx.WriteTimeout:
                pass

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_connect_timeout_handled(self) -> None:
        """Connect timeout is handled correctly."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker(name="connect_timeout_test", config=config)

        async def connect_timeout() -> None:
            raise httpx.ConnectTimeout("Timed out establishing connection")

        for _ in range(config.failure_threshold):
            try:
                await breaker.call(connect_timeout)
            except httpx.ConnectTimeout:
                pass

        assert breaker.state == CircuitState.OPEN
