"""Schemathesis-based contract tests (DEPRECATED - API incompatibility).

**DEPRECATED**: This file is kept for historical reference but is not functional
due to Schemathesis 4.x API changes. The `from_asgi()` method no longer exists
in Schemathesis 4.x, which uses a completely different API.

**USE INSTEAD**: `test_openapi_schema_validation.py`
- Provides OpenAPI schema validation without Schemathesis dependency
- Validates response structures against expected schemas
- Tests pagination, error formats, and critical endpoints
- More maintainable and doesn't require learning Schemathesis API

**Migration Notes**:
- Schemathesis 3.x used `schemathesis.from_asgi()` for ASGI app integration
- Schemathesis 4.x completely changed the API and removed this method
- Upgrading would require rewriting all tests with new API
- Decision: Use direct OpenAPI schema validation instead

**Historical Context (NEM-1408)**:
This file was created as part of contract testing implementation using
Schemathesis for property-based testing and OpenAPI validation. However,
the Schemathesis 4.x release introduced breaking API changes that made
this approach non-viable without significant refactoring.

**References**:
- Schemathesis 3.x docs: https://schemathesis.readthedocs.io/en/stable/
- Schemathesis 4.x migration: Breaking changes documented in release notes
- Alternative approach: test_openapi_schema_validation.py

If you need Schemathesis functionality:
1. Pin schemathesis<4.0 in pyproject.toml
2. OR rewrite tests using Schemathesis 4.x API
3. OR use the simpler direct validation approach (recommended)
"""

# This file intentionally left empty - see docstring above for migration path
