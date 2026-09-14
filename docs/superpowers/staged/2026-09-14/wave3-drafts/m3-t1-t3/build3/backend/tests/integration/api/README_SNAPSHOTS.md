# API Snapshot Testing (NEM-5021)

This directory contains snapshot tests for API schema validation using syrupy.

## Purpose

Snapshot tests validate that API response schemas remain consistent over time. They:

- **Detect breaking changes** in API responses
- **Validate schema structure** without hardcoding expectations
- **Catch unintended field additions/removals**
- **Ignore dynamic data** like timestamps, IDs, and counts

## Test Files

- `test_calibration_routes_snapshots.py` - Calibration API schema validation
- `test_feedback_routes_snapshots.py` - Feedback API schema validation
- `__snapshots__/*.ambr` - Generated snapshot files (auto-created on first run)

## Running Snapshot Tests

```bash
# Run all snapshot tests
uv run pytest backend/tests/integration/api/test_*_snapshots.py -n0

# Run specific test file
uv run pytest backend/tests/integration/api/test_calibration_routes_snapshots.py -n0

# Generate/update snapshots (first time or after schema changes)
uv run pytest backend/tests/integration/api/test_calibration_routes_snapshots.py -n0 --snapshot-update

# View snapshot diffs
uv run pytest backend/tests/integration/api/test_calibration_routes_snapshots.py -n0 -v
```

**Note:** Use `-n0` to disable parallel execution for integration tests.

## Schema Extraction

The `extract_schema()` utility (defined in `backend/tests/conftest.py`) converts response data to structure-only schemas:

### Example

**Input:**

```python
{
    "id": 123,
    "name": "Test Camera",
    "active": True,
    "tags": ["indoor", "front"],
    "metadata": {
        "location": "front_door",
        "floor": 1
    }
}
```

**Schema (snapshot):**

```python
{
    "id": "int",
    "name": "str",
    "active": "bool",
    "tags": ["str"],
    "metadata": {
        "location": "str",
        "floor": "int"
    }
}
```

## Writing Snapshot Tests

### Basic Pattern

```python
import pytest
from syrupy.assertion import SnapshotAssertion
from backend.tests.conftest import extract_schema


@pytest.mark.integration
@pytest.mark.asyncio
async def test_endpoint_response_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test endpoint response schema with snapshot."""
    response = await client.get("/api/resource")
    assert response.status_code == 200

    # Extract structure-only schema
    schema = extract_schema(response.json())
    assert schema == snapshot
```

### Coverage Guidelines

For each endpoint, create snapshot tests for:

1. **Success responses** (200, 201, 204)
2. **Error responses** (400, 404, 422, 500)
3. **Empty collections** (empty arrays/objects)
4. **Pagination metadata** (list endpoints)
5. **Cross-endpoint consistency** (same resource from different endpoints)

### Example: Complete Endpoint Coverage

```python
# Success response
async def test_create_resource_schema(client, snapshot):
    response = await client.post("/api/resource", json=data)
    assert response.status_code == 201
    assert extract_schema(response.json()) == snapshot

# Error response
async def test_resource_not_found_schema(client, snapshot):
    response = await client.get("/api/resource/999999")
    assert response.status_code == 404
    assert extract_schema(response.json()) == snapshot

# Empty collection
async def test_list_empty_resources_schema(client, snapshot):
    response = await client.get("/api/resource")
    assert response.status_code == 200
    assert extract_schema(response.json()) == snapshot

# Cross-endpoint consistency
async def test_resource_schema_consistency(client, snapshot):
    # Create
    create_response = await client.post("/api/resource", json=data)
    create_schema = extract_schema(create_response.json())

    # Get by ID
    resource_id = create_response.json()["id"]
    get_response = await client.get(f"/api/resource/{resource_id}")
    get_schema = extract_schema(get_response.json())

    # Should match
    assert create_schema == get_schema == snapshot
```

## Updating Snapshots

When API schemas change intentionally:

1. **Review the change** - Ensure it's intentional
2. **Run tests** to see the diff:
   ```bash
   pytest backend/tests/integration/api/test_*_snapshots.py -n0 -v
   ```
3. **Update snapshots** if change is correct:
   ```bash
   pytest backend/tests/integration/api/test_*_snapshots.py -n0 --snapshot-update
   ```
4. **Commit the changes**:
   ```bash
   git add backend/tests/integration/api/__snapshots__/
   git commit -m "Update API snapshots for schema change"
   ```

## CI/CD Integration

- Snapshot tests run automatically in CI
- Failing snapshots indicate schema changes that need review
- Updated snapshots must be committed with code changes
- PR reviewers should verify snapshot diffs are intentional

## Best Practices

1. **Test all endpoints** - Don't skip error cases
2. **Use descriptive test names** - Include endpoint and scenario
3. **Group related tests** - Organize by endpoint or feature
4. **Document intentional changes** - Explain why schema changed
5. **Review diffs carefully** - Snapshots are contracts with API consumers

## Troubleshooting

### Snapshot mismatch on first run

This is expected! Run with `--snapshot-update` to generate initial snapshots:

```bash
pytest backend/tests/integration/api/test_calibration_routes_snapshots.py -n0 --snapshot-update
```

### Test fails with "snapshot does not exist"

The snapshot file hasn't been generated yet. Use `--snapshot-update`:

```bash
pytest path/to/test.py --snapshot-update
```

### Snapshot diff shows unexpected changes

1. Review the diff carefully
2. Check if the API change was intentional
3. If unintentional, fix the API
4. If intentional, update the snapshot and document the change

### Database connection errors

Integration tests require a PostgreSQL database:

```bash
# Start containers
podman-compose -f docker-compose.prod.yml up -d postgres redis

# Or use testcontainers (automatic)
pytest backend/tests/integration/api/test_*_snapshots.py -n0
```

## References

- [Syrupy Documentation](https://github.com/tophat/syrupy)
- [Testing Guide](../../../docs/development/testing.md)
- [Test Patterns](../../../docs/developer/patterns/)
