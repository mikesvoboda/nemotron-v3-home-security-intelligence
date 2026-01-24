# Input Validation

> Pydantic validation patterns, SQL injection prevention, and request sanitization

## Key Files

- `backend/api/schemas/camera.py:36-137` - Camera input validation with path traversal prevention
- `backend/api/schemas/zone.py:115-156` - Polygon geometry validation
- `backend/api/schemas/events.py` - Event schema validation
- `backend/api/schemas/detections.py` - Detection schema validation
- `backend/core/sanitization.py` - Error and metric label sanitization
- `backend/api/middleware/body_limit.py` - Request body size limits
- `backend/api/middleware/content_type_validator.py` - Content-Type validation

## Overview

The Home Security Intelligence system uses a layered input validation approach:

1. **Pydantic Schemas** - Type validation, field constraints, and custom validators
2. **SQLAlchemy ORM** - Parameterized queries preventing SQL injection
3. **Middleware** - Request body limits and Content-Type validation
4. **Sanitization** - Error message and metric label sanitization

This follows OWASP guidelines for input validation: validate on the server side, use allowlists where possible, and sanitize output.

## Pydantic Schema Validation

### Field Constraints

Pydantic v2 provides declarative field constraints via the `Field()` function:

```python
# From backend/api/schemas/camera.py:114-121
name: str = Field(..., min_length=1, max_length=255, description="Camera name")
folder_path: str = Field(
    ..., min_length=1, max_length=500, description="File system path for camera uploads"
)
status: CameraStatus = Field(
    default=CameraStatus.ONLINE,
    description="Camera status (online, offline, error, unknown)",
)
```

**Key Constraints Used:**

| Constraint   | Purpose                  | Example                        |
| ------------ | ------------------------ | ------------------------------ |
| `min_length` | Prevent empty strings    | `min_length=1`                 |
| `max_length` | Prevent buffer overflow  | `max_length=500`               |
| `ge`/`le`    | Numeric range validation | `ge=0, le=100`                 |
| `pattern`    | Regex validation         | `pattern=r"^#[0-9A-Fa-f]{6}$"` |

### Custom Field Validators

For complex validation logic, Pydantic's `@field_validator` decorator is used:

```python
# From backend/api/schemas/camera.py:123-136
@field_validator("name")
@classmethod
def validate_name(cls, v: str) -> str:
    """Validate and sanitize camera name.

    NEM-2569: Rejects control characters, strips whitespace.
    """
    return _validate_camera_name(v)

@field_validator("folder_path")
@classmethod
def validate_folder_path(cls, v: str) -> str:
    """Validate folder_path for security."""
    return _validate_folder_path(v)
```

### Path Traversal Prevention

The camera schema explicitly blocks path traversal attempts:

```python
# From backend/api/schemas/camera.py:36-63
def _validate_folder_path(v: str) -> str:
    """Validate folder_path for security and correctness."""
    # Check for path traversal attempts
    if ".." in v:
        raise ValueError("Path traversal (..) not allowed in folder_path")

    # Check path length
    if not v or len(v) > 500:
        raise ValueError("folder_path must be between 1 and 500 characters")

    # Check for forbidden characters
    if _FORBIDDEN_PATH_CHARS.search(v):
        raise ValueError(
            'folder_path contains forbidden characters (< > : " | ? * or control characters)'
        )

    return v
```

**Forbidden Characters Pattern:**

```python
# From backend/api/schemas/camera.py:27-33
# Regex pattern for forbidden path characters
_FORBIDDEN_PATH_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')

# Regex pattern for forbidden name characters
_FORBIDDEN_NAME_CHARS = re.compile(r"[\x00-\x1f\x7f]")
```

### Control Character Rejection

Camera names are validated to reject control characters that could cause log injection or display issues:

```python
# From backend/api/schemas/camera.py:66-93
def _validate_camera_name(v: str) -> str:
    """Validate and sanitize camera name."""
    # Strip leading/trailing whitespace
    stripped = v.strip()

    # Check if name is effectively empty after stripping
    if not stripped:
        raise ValueError("Camera name cannot be empty or whitespace-only")

    # Check for forbidden control characters
    if _FORBIDDEN_NAME_CHARS.search(v):
        raise ValueError(
            "Camera name contains forbidden characters (control characters)"
        )

    return stripped
```

### Geometry Validation

Zone coordinates undergo comprehensive geometry validation:

```python
# From backend/api/schemas/zone.py:115-156
def _validate_polygon_geometry(coords: list[list[float]]) -> list[list[float]]:
    """Validate that coordinates form a valid polygon.

    Checks:
    1. Each point has exactly 2 values [x, y]
    2. All values are normalized (0-1 range)
    3. No duplicate consecutive points
    4. Polygon has positive area (not degenerate)
    5. Polygon does not self-intersect
    """
    # Check point format and normalization
    for point in coords:
        if len(point) != 2:
            raise ValueError("Each coordinate must have exactly 2 values [x, y]")
        x, y = point
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise ValueError("Coordinates must be normalized (0-1 range)")

    # Check for duplicate consecutive points
    if _has_duplicate_consecutive_points(coords):
        raise ValueError("Polygon has duplicate consecutive points")

    # Check polygon has positive area
    area = abs(_polygon_area(coords))
    if area < 1e-10:
        raise ValueError("Polygon has zero or near-zero area")

    # Check for self-intersection
    if _is_self_intersecting(coords):
        raise ValueError("Polygon edges must not intersect")

    return coords
```

## SQL Injection Prevention

### SQLAlchemy ORM Usage

The system uses SQLAlchemy ORM exclusively, which provides automatic parameterization:

```python
# Safe - SQLAlchemy handles parameterization
result = await session.execute(
    select(Camera).where(Camera.id == camera_id)
)

# Safe - all values are parameterized
result = await session.execute(
    select(Detection).where(
        Detection.camera_id == camera_id,
        Detection.detected_at >= start_date
    )
)
```

**Key Protections:**

1. **No raw SQL** - All queries use SQLAlchemy's query builder
2. **Automatic escaping** - User input is never concatenated into queries
3. **Type coercion** - SQLAlchemy validates types before query execution

### Async Session Pattern

Database sessions are managed via dependency injection with proper cleanup:

```python
# From backend/core/database.py
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session as FastAPI dependency."""
    async with get_session() as session:
        yield session
```

## Request Body Validation

### Body Size Limits

The `BodySizeLimitMiddleware` prevents denial-of-service via large payloads:

```python
# From backend/main.py:1059-1061
# Add body size limit middleware to prevent DoS attacks (NEM-1614)
# Default: 10MB limit for request bodies
app.add_middleware(BodySizeLimitMiddleware, max_body_size=10 * 1024 * 1024)
```

### Content-Type Validation

The `ContentTypeValidationMiddleware` ensures POST/PUT/PATCH requests have valid Content-Type headers:

```python
# From backend/main.py:1005-1007
# Add Content-Type validation middleware for request body validation (NEM-1617)
# Validates that POST/PUT/PATCH requests have acceptable Content-Type headers
app.add_middleware(ContentTypeValidationMiddleware)
```

## Error Message Sanitization

### Path Sanitization for Errors

Error messages are sanitized to prevent path disclosure:

```python
# From backend/core/sanitization.py:103-130
def sanitize_path_for_error(path: str) -> str:
    """Sanitize a file path for safe inclusion in error messages.

    Removes the directory path and returns only the filename to prevent
    information disclosure about internal file system structure.
    """
    if not path:
        return "[unknown]"

    # Extract just the filename
    parts = path.replace("\\", "/").rsplit("/", 1)
    filename = parts[1] if len(parts) == 2 else parts[0]

    # Limit length to prevent very long filenames in logs
    if len(filename) > 100:
        filename = filename[:97] + "..."

    return filename
```

### Credential Redaction

Sensitive data is redacted from error messages:

```python
# From backend/core/sanitization.py:159-169
# Pattern matches: protocol://user:pass@host
url_credentials_pattern = re.compile(
    r"([a-zA-Z][a-zA-Z0-9+.-]*://)?([^:@\s/]+):([^@\s/]+)@([^\s]+)", re.IGNORECASE  # pragma: allowlist secret
)

def replace_url_credentials(match: re.Match[str]) -> str:
    protocol = match.group(1) or ""
    host_and_rest = match.group(4)
    return f"{protocol}[CREDENTIALS_REDACTED]@{host_and_rest}"
```

**Sensitive Patterns Redacted:**

| Pattern           | Replacement           |
| ----------------- | --------------------- |
| `password=secret` | `password=[REDACTED]` |
| `Bearer token123` | `Bearer [REDACTED]`   |
| `api_key=abc123`  | `api_key=[REDACTED]`  |
| `192.168.1.100`   | `[IP_REDACTED]`       |

## Metric Label Sanitization

Prometheus metric labels are sanitized to prevent cardinality explosion:

```python
# From backend/core/sanitization.py:359-433
def sanitize_metric_label(
    value: str,
    label_name: str = "",
    allowlist: frozenset[str] | None = None,
    max_length: int = METRIC_LABEL_MAX_LENGTH,
) -> str:
    """Sanitize a value for use as a Prometheus metric label.

    Prevents cardinality explosion by:
    1. Limiting length
    2. Normalizing to lowercase
    3. Replacing special characters
    4. Using allowlist when available
    """
```

**Known Allowlists:**

| Label Type     | Allowlist                | Unknown Value |
| -------------- | ------------------------ | ------------- |
| `object_class` | COCO dataset classes     | `"other"`     |
| `error_type`   | Known error types        | `"other"`     |
| `risk_level`   | low/medium/high/critical | `"unknown"`   |

## Validation Error Responses

Pydantic validation errors are returned as structured JSON:

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "name"],
      "msg": "String should have at least 1 character",
      "input": "",
      "ctx": { "min_length": 1 }
    }
  ]
}
```

## Related Documentation

- [Security Headers](./security-headers.md) - HTTP response headers
- [Data Protection](./data-protection.md) - Sensitive data handling
- [API Reference](../api-reference/README.md) - Endpoint schemas

---

_Last updated: 2026-01-24 - Input validation documentation for NEM-3464_
