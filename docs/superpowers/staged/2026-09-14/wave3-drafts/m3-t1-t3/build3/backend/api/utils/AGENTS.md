# API Utils - Agent Guide

## Purpose

This directory contains utility functions and helpers for API request/response processing. These utilities are shared across route handlers to reduce duplication and ensure consistent behavior.

## Files Overview

```
backend/api/utils/
|-- __init__.py           # Module exports
|-- field_filter.py       # Sparse fieldsets for response filtering (NEM-1434)
```

## `field_filter.py` - Sparse Fieldsets (NEM-1434)

Provides utilities for field selection in API responses, allowing clients to request only specific fields to reduce payload size and bandwidth.

**Usage:**

```
GET /api/events?fields=id,camera_id,risk_level,summary,reviewed
```

### Classes

| Class              | Purpose                                            |
| ------------------ | -------------------------------------------------- |
| `FieldFilterError` | Exception raised when invalid fields are requested |

### Functions

| Function             | Purpose                                       |
| -------------------- | --------------------------------------------- |
| `parse_fields_param` | Parse comma-separated fields param to set     |
| `validate_fields`    | Validate requested fields against allowed set |
| `filter_fields`      | Filter dict to include only specified fields  |

### Example

```python
from backend.api.utils.field_filter import (
    parse_fields_param,
    validate_fields,
    filter_fields,
    FieldFilterError,
)

# Define valid fields for the endpoint
VALID_EVENT_FIELDS = {"id", "camera_id", "risk_level", "summary", "reviewed", "started_at"}

# Parse the fields query parameter
requested_fields = parse_fields_param(fields_param)
# Returns: {'id', 'camera_id', 'risk_level'} or None

# Validate against allowed fields
try:
    validated_fields = validate_fields(requested_fields, VALID_EVENT_FIELDS)
except FieldFilterError as e:
    # e.invalid_fields contains the bad field names
    # e.valid_fields contains the allowed field names
    raise HTTPException(400, str(e))

# Filter each item in the response
filtered_events = [filter_fields(event.model_dump(), validated_fields) for event in events]
```

### Behavior Notes

- `parse_fields_param(None)` returns `None` (no filtering)
- `parse_fields_param("")` returns `None` (no filtering)
- Field names are normalized to lowercase
- Whitespace around field names is trimmed
- `filter_fields(data, None)` returns a shallow copy of the original dict
- Preserves key order from the original dictionary

## Related Documentation

- `/backend/api/AGENTS.md` - API package overview
- `/backend/api/schemas/openapi_docs.py` - OpenAPI documentation helpers
- `/backend/api/routes/AGENTS.md` - Route handlers using these utilities
