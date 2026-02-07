# NEM-5021 Implementation Summary: Snapshot Testing with Syrupy

## Overview

Successfully implemented comprehensive snapshot testing for API schema validation using syrupy. This provides structure-only schema validation that detects breaking changes while ignoring dynamic data like timestamps and IDs.

## Files Created

### 1. Test Files (658 lines)

**backend/tests/integration/api/test_calibration_routes_snapshots.py** (269 lines)

- 11 snapshot tests covering all calibration endpoints
- Tests for GET, PUT, PATCH, POST endpoints
- Error response schema validation
- Cross-endpoint schema consistency tests

**backend/tests/integration/api/test_feedback_routes_snapshots.py** (389 lines)

- 17 snapshot tests covering all feedback endpoints
- Tests for CREATE, READ, LIST, STATS, DELETE operations
- Error response schema validation (404, 422)
- Pagination metadata validation
- Cross-endpoint schema consistency tests

### 2. Documentation (219 lines)

**backend/tests/integration/api/README_SNAPSHOTS.md** (219 lines)

- Complete guide to snapshot testing
- Examples of writing and updating tests
- Troubleshooting guide
- CI/CD integration documentation

## Files Modified

### 1. Core Test Infrastructure

**backend/tests/conftest.py**

- Added `extract_schema()` utility function for structure-only schema extraction
- Recursively converts response data to type names
- Supports nested objects, lists, and primitives
- Includes `preserve_lengths` parameter for list validation

### 2. Testing Documentation

**docs/development/testing.md**

- Added "Snapshot Testing with Syrupy" section (150+ lines)
- Usage examples and best practices
- Schema extraction utility documentation
- Snapshot update workflow
- CI/CD integration guidelines

## Key Features Implemented

### 1. Schema Extraction Utility

```python
def extract_schema(data: object, *, preserve_lengths: bool = False) -> object:
    """Extract structure-only schema from API response data."""
    # Converts: {"id": 123, "name": "test"}
    # To: {"id": "int", "name": "str"}
```

**Benefits:**

- Ignores dynamic data (timestamps, IDs, counts)
- Validates structure without false positives
- Supports nested objects and lists
- Preserves list lengths optionally

### 2. Comprehensive Test Coverage

**Calibration API (11 tests):**

- GET /api/calibration - Auto-creation schema
- PUT /api/calibration - Full/partial update schema
- PATCH /api/calibration - Partial update schema
- POST /api/calibration/reset - Reset response schema
- GET /api/calibration/defaults - Defaults schema
- Error responses (422 validation errors)
- Cross-endpoint consistency validation

**Feedback API (17 tests):**

- POST /api/feedback - Create with/without notes
- GET /api/feedback/{id} - Single item schema
- GET /api/feedback/event/{id} - Event feedback schema
- GET /api/feedback - List with pagination
- GET /api/feedback/stats - Statistics schema
- Error responses (404, 422)
- Empty collection schema
- Cross-endpoint consistency validation

### 3. Error Schema Validation

All tests include error response validation:

- 404 Not Found schemas
- 422 Validation Error schemas
- Consistent error structure across endpoints

### 4. Test Patterns

**Structure-only snapshots:**

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_endpoint_schema(client, snapshot):
    response = await client.get("/api/resource")
    assert response.status_code == 200
    schema = extract_schema(response.json())
    assert schema == snapshot
```

**Cross-endpoint consistency:**

```python
async def test_schema_consistency(client, snapshot):
    create_schema = extract_schema(create_response.json())
    get_schema = extract_schema(get_response.json())
    assert create_schema == get_schema == snapshot
```

## Testing the Implementation

### Run Snapshot Tests

```bash
# Generate initial snapshots (first run)
uv run pytest backend/tests/integration/api/test_calibration_routes_snapshots.py -n0 --snapshot-update

# Run all snapshot tests
uv run pytest backend/tests/integration/api/test_*_snapshots.py -n0

# View snapshot diffs
uv run pytest backend/tests/integration/api/test_calibration_routes_snapshots.py -n0 -v
```

### Validate Code Quality

```bash
# Ruff check (formatting)
uv run ruff check backend/tests/integration/api/test_*_snapshots.py
# ✅ All checks passed!

# MyPy check (type hints)
uv run mypy backend/tests/integration/api/test_*_snapshots.py
# ✅ Success: no issues found

# Test extract_schema utility
uv run python -c "from backend.tests.conftest import extract_schema; print(extract_schema({'id': 1, 'name': 'test'}))"
# ✅ {'id': 'int', 'name': 'str'}
```

## Benefits

### 1. Schema Change Detection

- Automatically detects breaking API changes
- Catches unintended field additions/removals
- Validates nested object structures

### 2. CI/CD Integration

- Snapshot tests run in CI automatically
- Failing tests indicate schema changes
- Updated snapshots must be committed with code

### 3. Low Maintenance

- No hardcoded assertions to update
- Self-documenting API contracts
- Easy to update when schemas change intentionally

### 4. Comprehensive Coverage

- 28 snapshot tests covering critical endpoints
- Error response validation
- Pagination metadata validation
- Cross-endpoint consistency checks

## Usage Examples

### Updating Snapshots After Schema Changes

```bash
# 1. Make API schema change
# 2. Run tests to see diff
pytest backend/tests/integration/api/test_*_snapshots.py -n0 -v

# 3. Review diff carefully
# 4. Update snapshots if change is intentional
pytest backend/tests/integration/api/test_*_snapshots.py -n0 --snapshot-update

# 5. Commit updated snapshots
git add backend/tests/integration/api/__snapshots__/
git commit -m "Update API snapshots for schema change"
```

### Adding Snapshot Tests for New Endpoints

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_new_endpoint_schema(client, snapshot):
    """Test new endpoint response schema."""
    response = await client.get("/api/new-resource")
    assert response.status_code == 200
    schema = extract_schema(response.json())
    assert schema == snapshot
```

## Next Steps

### Recommended Additional Coverage

1. **Cameras API** (`/api/cameras`)

   - List cameras with sparse fieldsets
   - Create/update camera schemas
   - Camera snapshot refresh response

2. **Events API** (`/api/events`)

   - Event list with pagination
   - Event details with detections
   - Timeline buckets response

3. **Zones API** (`/api/zones`)

   - Zone CRUD operations
   - Zone analytics responses
   - Household configuration schemas

4. **Analytics API** (`/api/analytics/*`)
   - Heatmap data structure
   - Zone analytics response
   - Cost analytics schema

### Integration with CI

Add to `.github/workflows/ci.yml`:

```yaml
- name: Run Snapshot Tests
  run: |
    uv run pytest backend/tests/integration/api/test_*_snapshots.py -n0 -v
```

## References

- **Issue:** NEM-5021 - Increase snapshot testing usage with syrupy for API schema validation
- **Syrupy Documentation:** https://github.com/tophat/syrupy
- **Testing Guide:** docs/development/testing.md
- **Test Patterns:** backend/tests/integration/api/README_SNAPSHOTS.md

## Success Metrics

- ✅ 28 snapshot tests created (11 calibration + 17 feedback)
- ✅ Schema extraction utility implemented and tested
- ✅ Documentation updated with comprehensive guide
- ✅ All code passes ruff and mypy validation
- ✅ README with examples and troubleshooting guide
- ✅ Error response schemas validated
- ✅ Cross-endpoint consistency tests added
