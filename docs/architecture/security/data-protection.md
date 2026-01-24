# Data Protection

> Sensitive data handling, image storage security, and log sanitization

## Key Files

- `backend/api/routes/media.py:42-124` - Secure media serving with path validation
- `backend/core/sanitization.py:133-230` - Error message sanitization
- `backend/core/config.py:1090-1098` - API key configuration (hashed storage)
- `backend/api/middleware/auth.py` - API key hashing implementation
- `backend/api/middleware/request_recorder.py` - Request body redaction
- `backend/core/logging.py` - Structured logging with sensitive data filtering

## Overview

The Home Security Intelligence system handles sensitive data including camera images, video footage, and detection records. This document covers the protection mechanisms for:

1. **Image and Video Storage** - Secure serving with path traversal prevention
2. **Credential Protection** - API key hashing and secure storage
3. **Log Sanitization** - Preventing sensitive data leakage in logs
4. **Error Message Filtering** - Removing internal paths and credentials from responses

## Image and Video Storage Security

### Path Traversal Protection

All media endpoints validate paths to prevent directory traversal attacks:

```python
# From backend/api/routes/media.py:42-124
def _validate_and_resolve_path(base_path: Path, requested_path: str) -> Path:
    """Validate and resolve a file path securely."""

    # Check path length to prevent buffer overflow attacks
    if len(requested_path) > MAX_PATH_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_414_URI_TOO_LONG,
            detail=MediaErrorResponse(
                error=f"Path too long. Maximum length is {MAX_PATH_LENGTH} characters.",
                path=requested_path[:100] + "...",
            ).model_dump(),
        )

    # Check for path traversal attempts
    if ".." in requested_path or requested_path.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MediaErrorResponse(
                error="Path traversal detected",
                path=requested_path,
            ).model_dump(),
        )

    # Resolve the full path
    full_path = (base_path / requested_path).resolve()

    # Ensure the resolved path is within the base directory
    try:
        full_path.relative_to(base_path.resolve())
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MediaErrorResponse(
                error="Access denied - path outside allowed directory",
                path=requested_path,
            ).model_dump(),
        ) from err

    return full_path
```

**Security Checks Performed:**

| Check             | Purpose                       | Response Code    |
| ----------------- | ----------------------------- | ---------------- |
| Path length limit | Prevent buffer overflow       | 414 URI Too Long |
| `..` traversal    | Block parent directory access | 403 Forbidden    |
| Absolute path     | Block direct path injection   | 403 Forbidden    |
| `relative_to()`   | Verify path is within base    | 403 Forbidden    |
| File extension    | Allowlist media types         | 403 Forbidden    |

### Allowed File Types

Only specific media types are served:

```python
# From backend/api/routes/media.py:31-39
ALLOWED_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".mp4": "video/mp4",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
}
```

### Storage Organization

Camera images are stored in a structured hierarchy:

```
/cameras/
  ├── front_door/
  │   ├── 2024/
  │   │   └── 01/
  │   │       └── 15/
  │   │           └── image_001.jpg
  ├── backyard/
  │   └── ...
```

**Security Properties:**

- Camera ID validation prevents accessing other cameras' data
- Date-based organization limits enumeration surface
- No direct database file storage (file paths only)

## Credential Protection

### API Key Hashing

When API key authentication is enabled, keys are hashed using SHA-256:

```python
# From backend/api/middleware/auth.py (conceptual)
import hashlib

def hash_api_key(api_key: str) -> str:
    """Hash an API key using SHA-256."""
    return hashlib.sha256(api_key.encode()).hexdigest()

def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """Verify an API key against its stored hash."""
    return hash_api_key(provided_key) == stored_hash
```

### Configuration Security

API keys are configured via environment variables and hashed on startup:

```python
# From backend/core/config.py:1090-1098
api_key_enabled: bool = Field(
    default=False,
    description="Enable API key authentication (default: False for development)",
)
api_keys: list[str] = Field(
    default=[],
    description="List of valid API keys (plain text, hashed on startup)",
)
```

**Best Practices:**

| Practice               | Implementation                     |
| ---------------------- | ---------------------------------- |
| Never log API keys     | Keys redacted in request logs      |
| Environment variables  | Keys passed via `API_KEYS` env var |
| Timing-safe comparison | Constant-time string comparison    |
| No plaintext storage   | Keys hashed immediately on load    |

## Log Sanitization

### Error Message Sanitization

The `sanitize_error_for_response()` function removes sensitive data:

```python
# From backend/core/sanitization.py:133-230
def sanitize_error_for_response(error: Exception, context: str = "") -> str:
    """Sanitize an exception for safe inclusion in API responses.

    Removes potentially sensitive information like:
    - Full file paths (keeps only filename)
    - Stack traces
    - Internal module names
    - Database connection details
    - URL credentials (user:password@host)
    - JSON password values
    - Windows paths
    """
```

**Sensitive Patterns Redacted:**

```python
# From backend/core/sanitization.py:200-217
sensitive_patterns = [
    # JSON-style password values
    (re.compile(r'(["\'])password\1\s*:\s*["\'][^"\']*["\']', re.IGNORECASE),
     '"password": "[REDACTED]"'),
    # Key-value password patterns
    (re.compile(r"password[=:]\s*\S+", re.IGNORECASE), "password=[REDACTED]"),
    # Bearer tokens
    (re.compile(r"Bearer\s+\S+", re.IGNORECASE), "Bearer [REDACTED]"),
    # API keys
    (re.compile(r"api[_-]?key[=:]\s*\S+", re.IGNORECASE), "api_key=[REDACTED]"),
    # Secret/token values
    (re.compile(r"secret[=:]\s*\S+", re.IGNORECASE), "secret=[REDACTED]"),
    (re.compile(r"token[=:]\s*\S+", re.IGNORECASE), "token=[REDACTED]"),
    # IPv4 addresses
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[IP_REDACTED]"),
]
```

### Path Sanitization for Logs

File paths in error messages are reduced to filenames only:

```python
# From backend/core/sanitization.py:103-130
def sanitize_path_for_error(path: str) -> str:
    """Sanitize a file path for safe inclusion in error messages.

    Removes the directory path and returns only the filename.
    """
    if not path:
        return "[unknown]"

    # Extract just the filename
    parts = path.replace("\\", "/").rsplit("/", 1)
    filename = parts[1] if len(parts) == 2 else parts[0]

    # Limit length
    if len(filename) > 100:
        filename = filename[:97] + "..."

    return filename
```

**Example Transformations:**

| Input                                      | Output        |
| ------------------------------------------ | ------------- |
| `/var/app/data/cameras/front_door/img.jpg` | `img.jpg`     |
| `C:\Users\admin\secret\config.json`        | `config.json` |
| `/etc/passwd`                              | `passwd`      |

### Request Body Redaction

Debug request recording redacts sensitive fields:

```python
# From backend/api/middleware/request_recorder.py
def redact_request_body(body: dict) -> dict:
    """Redact sensitive fields from request body for logging."""
    sensitive_keys = {"password", "api_key", "secret", "token", "authorization"}
    redacted = {}
    for key, value in body.items():
        if key.lower() in sensitive_keys:
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = redact_request_body(value)
        else:
            redacted[key] = value
    return redacted
```

## Data Retention

### Configurable Retention Period

Detection and event data is retained for a configurable period:

```python
# From backend/core/config.py:618-623
retention_days: int = Field(
    default=30,
    gt=0,
    description="Number of days to retain events and detections",
)
```

### Automated Cleanup

The cleanup service removes old data:

```python
# Cleanup removes:
# - Detection records older than retention_days
# - Event records older than retention_days
# - Orphaned media files
# - Expired Redis keys
```

## Container Name Sanitization

Container names are validated to prevent command injection:

```python
# From backend/core/sanitization.py:38-77
def sanitize_container_name(name: str) -> str:
    """Sanitize a container name to prevent command injection.

    Only allows alphanumeric characters, hyphens, and underscores.
    Names must start with an alphanumeric character.
    """
    if not name:
        raise ValueError("Container name cannot be empty")

    if len(name) > CONTAINER_NAME_MAX_LENGTH:
        raise ValueError(f"Container name exceeds maximum length of {CONTAINER_NAME_MAX_LENGTH}")

    if not CONTAINER_NAME_PATTERN.match(name):
        raise ValueError("Container name contains invalid characters")

    return name
```

## Database Security

### Connection String Protection

Database connection strings are not logged:

```python
# Environment variable: DATABASE_URL
# Format: postgresql+asyncpg://user:password@host:port/database  # pragma: allowlist secret
# Password portion is never included in logs
```

### Query Parameterization

All database queries use SQLAlchemy's parameterized queries:

```python
# Safe - SQLAlchemy parameterizes all values
result = await session.execute(
    select(Detection).where(Detection.camera_id == camera_id)
)
```

## Related Documentation

- [Input Validation](./input-validation.md) - Request validation patterns
- [Network Security](./network-security.md) - CORS and network boundaries
- [Observability](../observability/README.md) - Logging configuration

---

_Last updated: 2026-01-24 - Data protection documentation for NEM-3464_
