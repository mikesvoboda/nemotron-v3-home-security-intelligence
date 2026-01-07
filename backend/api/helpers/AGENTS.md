# API Helpers

## Purpose

The `backend/api/helpers/` directory contains helper modules for API data transformations and processing. These modules provide reusable utilities that transform complex database structures into structured API response formats.

## Files

### `__init__.py`

Package initialization with a simple docstring: "API helper modules."

### `enrichment_transformers.py`

Enrichment data transformation helpers for converting raw JSONB enrichment data from the database into structured API response format.

**Purpose:**

Transforms the complex `enrichment_data` JSONB field from detections into a structured, type-safe format for API responses. Uses an extractor pattern to handle different enrichment types (license plates, faces, vehicles, clothing, violence, image quality, pets).

**Key Classes:**

| Class                     | Purpose                                          |
| ------------------------- | ------------------------------------------------ |
| `EnrichmentTransformer`   | Main transformer orchestrating all extractors    |
| `BaseEnrichmentExtractor` | Abstract base class for enrichment extractors    |
| `LicensePlateExtractor`   | Extract license plate data                       |
| `FaceExtractor`           | Extract face detection data                      |
| `ViolenceExtractor`       | Extract violence detection data                  |
| `VehicleExtractor`        | Extract vehicle classification and damage data   |
| `ClothingExtractor`       | Extract clothing classification and segmentation |
| `ImageQualityExtractor`   | Extract image quality assessment data            |
| `PetExtractor`            | Extract pet classification data                  |

**Key Functions:**

| Function                     | Purpose                                          |
| ---------------------------- | ------------------------------------------------ |
| `transform_enrichment_data`  | Main entry point for enrichment transformation   |
| `get_enrichment_transformer` | Get the default transformer singleton            |
| `sanitize_errors`            | Sanitize error messages to remove sensitive data |

**Design Patterns:**

1. **Extractor Pattern** - Each enrichment type has a dedicated extractor class
2. **Template Method** - Base class defines common extraction interface
3. **Singleton** - Reuses transformer instance to avoid repeated initialization
4. **Validation First** - Validates enrichment data schema before transformation

**Security Features:**

- **Error Sanitization:** Removes file paths, IP addresses, and stack traces from error messages
- **Schema Validation:** Validates enrichment data before transformation (NEM-1351)
- **Known Error Categories:** Only preserves known error categories in sanitized output

**Usage:**

```python
from backend.api.helpers.enrichment_transformers import transform_enrichment_data

# Transform enrichment data for API response
enrichment_response = transform_enrichment_data(
    detection_id=detection.id,
    enrichment_data=detection.enrichment_data,
    detected_at=detection.detected_at,
)
```

**Extractor Base Class:**

All extractors inherit from `BaseEnrichmentExtractor` and implement:

- `enrichment_key` - The key in enrichment_data to look for
- `default_value` - Default value when no data is found
- `extract(enrichment_data)` - Transform the enrichment data

**Transformer Features:**

- **Schema Validation (NEM-1351):** Validates enrichment data before transformation
- **Reduced Duplication (NEM-1349):** Shared base class for all extractors
- **Focused Helpers (NEM-1307):** Each extractor handles one enrichment type
- **Graceful Degradation:** Returns empty response when data is missing or invalid
- **Error Sanitization:** Removes sensitive details from error messages

**Enrichment Types Handled:**

| Enrichment Type | Extractor Class         | Key in enrichment_data     |
| --------------- | ----------------------- | -------------------------- |
| License Plates  | `LicensePlateExtractor` | `license_plates`           |
| Faces           | `FaceExtractor`         | `faces`                    |
| Violence        | `ViolenceExtractor`     | `violence_detection`       |
| Vehicles        | `VehicleExtractor`      | `vehicle_classifications`  |
| Clothing        | `ClothingExtractor`     | `clothing_classifications` |
| Image Quality   | `ImageQualityExtractor` | `image_quality`            |
| Pets            | `PetExtractor`          | `pet_classifications`      |

**Response Structure:**

```python
{
    "detection_id": 123,
    "enriched_at": "2025-01-07T10:30:00Z",
    "license_plate": {"detected": True, "text": "ABC123", ...},
    "face": {"detected": True, "count": 2, ...},
    "vehicle": {"type": "sedan", "confidence": 0.95, ...},
    "clothing": {"upper": "jacket", "lower": "jeans", ...},
    "violence": {"detected": False, "score": 0.0, ...},
    "weather": None,  # Placeholder
    "pose": None,     # Placeholder for future ViTPose
    "depth": None,    # Placeholder for future Depth Anything V2
    "image_quality": {"score": 0.85, "is_blurry": False, ...},
    "pet": {"detected": True, "type": "dog", ...},
    "processing_time_ms": 42,
    "errors": ["License plate detection failed"]  # Sanitized
}
```

## Common Patterns

### Extractor Pattern

All extractors follow the same pattern:

```python
class MyExtractor(BaseEnrichmentExtractor):
    @property
    def enrichment_key(self) -> str:
        return "my_enrichment_key"

    @property
    def default_value(self) -> dict[str, Any]:
        return {"detected": False}

    def extract(self, enrichment_data: dict[str, Any]) -> dict[str, Any]:
        data = enrichment_data.get(self.enrichment_key)
        if not data:
            return self.default_value

        # Transform data to API format
        return {"detected": True, ...}
```

### Error Sanitization

Error messages are sanitized to remove sensitive details:

```python
# Input: "License plate detection failed: /path/to/image.jpg not found"
# Output: "License Plate Detection Failed"

sanitized = sanitize_errors(raw_errors)
```

### Validation Before Transformation

Enrichment data is validated before transformation (optional):

```python
transformer = EnrichmentTransformer(validate_schema=True)
result = transformer.transform(detection_id, enrichment_data, detected_at)
```

## Integration Points

### Used By

- `backend/api/routes/detections.py` - Detections API endpoints
- `backend/api/routes/enrichment.py` - Enrichment API endpoints (if exists)

### Dependencies

- `backend/api/schemas/enrichment_data.py` - Schema validation
- `backend/core/logging` - Logging for warnings and errors

## Testing Considerations

When testing enrichment transformers:

1. Test each extractor independently
2. Test with missing enrichment data (should return defaults)
3. Test with invalid enrichment data (should validate and coerce)
4. Test error sanitization (should remove sensitive details)
5. Test all enrichment types
6. Test validation warnings and errors
7. Test graceful degradation

## Future Enhancements

Potential improvements:

1. **Caching** - Cache transformer instances per request
2. **Performance** - Skip validation for trusted data sources
3. **Extensibility** - Plugin system for new enrichment types
4. **Telemetry** - Track transformation performance and failures
5. **Placeholder Support** - Add extractors for weather, pose, depth when models are integrated
