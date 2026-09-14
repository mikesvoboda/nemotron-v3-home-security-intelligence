# API Helpers Unit Tests

## Purpose

Unit tests for API helper functions, specifically enrichment data transformation utilities that convert raw AI enrichment data into structured formats for the API.

## Directory Structure

```
backend/tests/unit/api/helpers/
├── AGENTS.md                         # This file
├── __init__.py                       # Package initialization
└── test_enrichment_transformers.py   # Enrichment data transformation tests (25KB)
```

## Running Tests

```bash
# All API helper tests
pytest backend/tests/unit/api/helpers/ -v

# Specific test file
pytest backend/tests/unit/api/helpers/test_enrichment_transformers.py -v

# With coverage
pytest backend/tests/unit/api/helpers/ -v --cov=backend.api.helpers --cov-report=html
```

## Test Files (1 total)

### `test_enrichment_transformers.py`

Tests for enrichment data transformation helpers (NEM-1349, NEM-1351, NEM-1307):

**Test Classes:**

| Test Class                     | Coverage                             |
| ------------------------------ | ------------------------------------ |
| `TestBaseEnrichmentExtractor`  | Base extractor class functionality   |
| `TestLicensePlateExtractor`    | License plate data extraction        |
| `TestFaceExtractor`            | Face detection data extraction       |
| `TestVehicleExtractor`         | Vehicle data extraction              |
| `TestPetExtractor`             | Pet detection data extraction        |
| `TestClothingExtractor`        | Clothing attribute extraction        |
| `TestViolenceExtractor`        | Violence detection extraction        |
| `TestImageQualityExtractor`    | Image quality metrics extraction     |
| `TestEnrichmentTransformer`    | Main transformer orchestration       |
| `TestTransformEnrichmentData`  | Transform function integration       |
| `TestGetEnrichmentTransformer` | Transformer factory function         |
| `TestSanitizeErrors`           | Error sanitization for API responses |

**Key Test Coverage:**

- Schema validation before transformation
- Bounding box normalization
- Confidence score handling
- Error handling and sanitization
- Code duplication reduction through base class
- Individual extractor classes work correctly
- Integration of all extractors

**Test Patterns:**

```python
@pytest.fixture
def sample_enrichment_data() -> dict[str, Any]:
    """Sample enrichment data as stored in the database."""
    return {
        "license_plates": [...],
        "faces": [...],
        "vehicles": [...],
        # ... other enrichment types
    }

def test_license_plate_extractor(sample_enrichment_data):
    """Test license plate data extraction."""
    extractor = LicensePlateExtractor()
    result = extractor.extract(sample_enrichment_data)

    assert "license_plates" in result
    assert len(result["license_plates"]) > 0
    assert result["license_plates"][0]["text"] == "ABC-1234"
```

## Related Documentation

- `/backend/api/helpers/AGENTS.md` - API helper implementations
- `/backend/api/helpers/enrichment_transformers.py` - Transformation logic
- `/backend/tests/unit/api/AGENTS.md` - API unit tests overview
- `/backend/tests/AGENTS.md` - Test infrastructure overview
