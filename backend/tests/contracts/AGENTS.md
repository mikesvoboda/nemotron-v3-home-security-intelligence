# Contract Tests

## Purpose

This directory contains consumer-driven contract tests that verify API schema compliance using Schemathesis. These tests ensure frontend and backend API compatibility by validating that responses conform to the OpenAPI schema.

## Why Contract Testing?

Contract tests solve the problem of schema drift between frontend and backend:

- **Frontend assumes response shapes** - TypeScript types expect specific fields
- **Backend can change responses** - Field additions, renames, or type changes
- **Integration tests miss this** - They verify backend behavior, not frontend expectations
- **Contract tests catch drift early** - Before it becomes a runtime error in production

## Files

### `__init__.py`

Package initialization for the contracts test module.

### `conftest.py`

Pytest fixtures for contract testing:

| Fixture               | Scope  | Description                                    |
| --------------------- | ------ | ---------------------------------------------- |
| `app_with_db`         | module | FastAPI app with initialized database          |
| `async_client`        | module | httpx AsyncClient for testing                  |
| `openapi_schema`      | module | OpenAPI schema dict from FastAPI               |
| `schemathesis_schema` | module | Schemathesis schema for property-based testing |

### `test_api_contracts.py`

Contract tests for critical API endpoints:

| Test Class                    | Endpoints Tested                              |
| ----------------------------- | --------------------------------------------- |
| `TestEventsAPIContract`       | GET /api/events, GET /api/events/{id}         |
| `TestCamerasAPIContract`      | GET /api/cameras, GET /api/cameras/{id}       |
| `TestSystemAPIContract`       | GET /api/system/health, GET /api/system/gpu   |
| `TestDetectionsAPIContract`   | GET /api/detections, GET /api/detections/{id} |
| `TestAIAuditAPIContract`      | GET /api/ai-audit/stats                       |
| `TestSchemathesisGenerated`   | Schema-based fuzz testing of endpoints        |
| `TestOpenAPISchemaValidation` | Schema structure validation                   |

## Running Contract Tests

```bash
# Run all contract tests
uv run pytest backend/tests/contracts/ -v

# Run with verbose output
uv run pytest backend/tests/contracts/ -v --tb=short

# Run specific test class
uv run pytest backend/tests/contracts/test_api_contracts.py::TestEventsAPIContract -v

# Run with coverage
uv run pytest backend/tests/contracts/ --cov=backend --cov-report=term-missing
```

## Critical Endpoints

These endpoints are considered critical for frontend functionality:

1. **GET /api/events** - Event listing with filters (main dashboard)
2. **GET /api/events/{id}** - Event detail modal
3. **GET /api/cameras** - Camera listing (sidebar, grid)
4. **GET /api/system/health** - Health check (status indicator)
5. **GET /api/detections/{id}** - Detection detail
6. **GET /api/system/gpu** - GPU metrics (performance panel)
7. **GET /api/ai-audit/stats** - AI audit statistics

## Adding New Contract Tests

When adding a new API endpoint:

1. **Add schema validation test** - Verify response structure matches schema
2. **Add error case tests** - Test 404, 400, etc. responses
3. **Add to critical endpoints list** - If frontend depends on it
4. **Add Schemathesis fuzzing** - For comprehensive schema coverage

Example:

```python
class TestNewEndpointContract:
    """Contract tests for new endpoint."""

    @pytest.mark.asyncio
    async def test_endpoint_schema_compliance(self, async_client: AsyncClient) -> None:
        """Test that GET /api/new-endpoint returns schema-compliant response."""
        response = await async_client.get("/api/new-endpoint")

        assert response.status_code == 200
        data = response.json()

        # Verify required fields exist
        assert "required_field" in data
        assert isinstance(data["required_field"], expected_type)
```

## Schemathesis Integration

Schemathesis provides property-based testing from OpenAPI schemas:

```python
@pytest.mark.asyncio
@CONTRACT_TEST_SETTINGS
async def test_endpoint_fuzzing(self, schemathesis_schema) -> None:
    """Fuzz test endpoint with schema-generated inputs."""

    @schemathesis_schema.parametrize(endpoint="/api/endpoint", method="GET")
    @CONTRACT_TEST_SETTINGS
    def inner(case: schemathesis.Case) -> None:
        response = case.call_and_validate()

    inner()
```

## CI Integration

Contract tests run in CI as part of the integration test suite:

- Triggered on every PR
- Runs after backend starts
- Fails on schema violations
- Reports violations with detailed error messages

## Troubleshooting

### "Database not initialized"

Ensure the `app_with_db` fixture is being used and DATABASE_URL is set.

### Schemathesis validation failures

Check that:

1. Response schema is defined in the endpoint decorator
2. Response model matches actual response
3. Optional fields are properly typed

### Test timeout

Contract tests have 5-second deadline per example. Increase if needed:

```python
@settings(deadline=10000)  # 10 seconds
```

## Related Documentation

- `../AGENTS.md` - Test infrastructure overview
- `/backend/api/routes/AGENTS.md` - API endpoint documentation
- `/docs/AGENTS.md` - Project documentation
