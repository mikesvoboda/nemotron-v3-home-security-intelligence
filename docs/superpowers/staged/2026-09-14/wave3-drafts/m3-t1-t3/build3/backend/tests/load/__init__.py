"""Load tests for performance validation of new features.

This package contains load tests to verify that:
- Household matching completes within 50ms p99 latency
- Frame buffer memory stays under 500MB per camera
- X-CLIP handles concurrent inference requests

Tests use realistic data sizes and concurrent access patterns
to validate production readiness of new features.

Implements NEM-3340: Load Testing for New Features (Phase 7.4).
"""
