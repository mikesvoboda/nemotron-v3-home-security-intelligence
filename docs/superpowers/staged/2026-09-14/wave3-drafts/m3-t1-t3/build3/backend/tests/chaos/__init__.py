"""Chaos testing module for resilience and fault injection testing.

This module provides a comprehensive framework for testing system behavior
under failure conditions. It helps verify that the system degrades gracefully
when dependencies become unavailable.

Components:
    - conftest.py: Fault injection fixtures and FaultInjector class
    - test_redis_failures.py: Redis cache/queue service failures
    - test_database_failures.py: PostgreSQL database failures
    - test_nemotron_failures.py: Nemotron LLM service failures
    - test_network_conditions.py: Network latency and reliability issues

Usage:
    pytest backend/tests/chaos/ -v -m chaos

The chaos tests verify:
    - Services return degraded but valid responses during outages
    - Circuit breakers open and close correctly
    - Health endpoints accurately report degraded state
    - Fallback mechanisms engage appropriately
    - No data is silently lost during failures
"""
