# Security Tests Directory

## Purpose

Security tests validate the application's resilience against common web security vulnerabilities including SQL injection, XSS, path traversal, authentication bypass, and input validation issues. These tests ensure the application handles malicious inputs safely without exposing sensitive data or crashing.

## Directory Structure

```
backend/tests/security/
├── AGENTS.md                  # This file
├── __init__.py                # Package initialization
├── conftest.py                # Security test fixtures
├── test_api_security.py       # API security tests (SQL injection, XSS, path traversal, rate limiting, CORS)
├── test_auth_security.py      # Authentication security tests (API key validation, hashing, exempt paths)
└── test_input_validation.py   # Input validation tests (schema validation, query parameters, encoding)
```

## Running Tests

```bash
# All security tests
pytest backend/tests/security/ -v

# Specific test file
pytest backend/tests/security/test_api_security.py -v

# With coverage
pytest backend/tests/security/ -v --cov=backend.api --cov-report=html

# Run with verbose output
pytest backend/tests/security/ -vv -s
```

## Test Files (3 total)

### `test_api_security.py`

API security vulnerability testing:

| Test Class          | Coverage                                  |
| ------------------- | ----------------------------------------- |
| `TestSQLInjection`  | SQL injection protection on all endpoints |
| `TestXSSPrevention` | XSS prevention in API responses           |
| `TestPathTraversal` | Path traversal attacks on file endpoints  |
| `TestRateLimiting`  | Rate limiting enforcement                 |
| `TestCORSHeaders`   | CORS header validation                    |

**SQL Injection Test Payloads:**

- `'; DROP TABLE cameras; --` - DROP TABLE attempt
- `' OR '1'='1` - OR 1=1 bypass
- `' OR '1'='1' --` - OR 1=1 with comment
- `1; SELECT * FROM users --` - UNION SELECT attempt
- `' UNION SELECT NULL, NULL, NULL --` - UNION NULL injection
- `1 AND 1=1` - Tautology attack
- `1' AND SLEEP(5) --` - Time-based blind SQLi
- `1' AND (SELECT SUBSTRING(password,1,1) FROM users)='a' --` - Substring extraction
- `%27` - URL-encoded quote
- `admin'--` - Comment truncation
- `';EXEC xp_cmdshell('dir');--` - Command execution attempt

**XSS Test Payloads:**

- `<script>alert('XSS')</script>` - Basic XSS
- `<img src=x onerror=alert('XSS')>` - Image tag XSS
- `<svg onload=alert('XSS')>` - SVG XSS
- `javascript:alert('XSS')` - Javascript protocol
- `<iframe src=javascript:alert('XSS')>` - Iframe XSS

**Path Traversal Test Payloads:**

- `../../../etc/passwd` - Unix path traversal
- `..\\..\\..\\windows\\system32\\config\\sam` - Windows path traversal
- `....//....//etc/passwd` - Double encoding
- `%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd` - URL encoding

### `test_auth_security.py`

Authentication security testing:

| Test Class                      | Coverage                      |
| ------------------------------- | ----------------------------- |
| `TestHashKeyFunction`           | API key SHA-256 hashing       |
| `TestAuthMiddlewareExemptPaths` | Exempt path checking logic    |
| `TestAuthMiddlewareValidation`  | API key validation logic      |
| `TestAuthMiddlewareIntegration` | End-to-end auth flow          |
| `TestAPIKeyLeakagePrevention`   | Key leakage in logs/responses |

**Key Security Tests:**

- Valid API key acceptance
- Invalid API key rejection
- Missing API key handling
- API key in header vs query parameter
- Exempt endpoint handling (health checks, OpenAPI docs)
- Key hashing consistency
- Key leakage prevention in error messages

### `test_input_validation.py`

Input validation and sanitization testing:

| Test Class                     | Coverage                       |
| ------------------------------ | ------------------------------ |
| `TestSchemaValidation`         | Pydantic schema validation     |
| `TestQueryParameterValidation` | Query string validation        |
| `TestPathParameterValidation`  | URL path parameter validation  |
| `TestContentTypeValidation`    | Content-Type header validation |
| `TestCharacterEncoding`        | Unicode and encoding handling  |
| `TestJSONParsingSecurity`      | JSON parsing edge cases        |

**Validation Tests:**

- Invalid JSON body rejected
- Missing required fields rejected
- Extra/unexpected fields handled safely
- Prototype pollution attempts blocked
- Query parameter type validation
- Query parameter range validation
- Path parameter format validation
- Content-Type mismatch handling
- Unicode characters handled safely
- Large payloads rejected
- Deeply nested JSON rejected

## Fixtures

Security tests use these fixtures from `conftest.py`:

| Fixture           | Description                           |
| ----------------- | ------------------------------------- |
| `security_client` | TestClient with security middleware   |
| `valid_api_key`   | Valid API key for authenticated tests |
| `invalid_api_key` | Invalid API key for negative tests    |

## Expected Security Behaviors

### SQL Injection Protection

- **SQLAlchemy ORM**: Uses parameterized queries automatically
- **Raw SQL**: Not used; all queries go through ORM
- **Expected Response**: 400/404 for malformed input, never SQL errors

### XSS Prevention

- **API Responses**: JSON responses auto-escape by FastAPI
- **HTML Responses**: Not used in API
- **Expected Response**: XSS payloads returned as plain text, never executed

### Path Traversal Protection

- **File Serving**: Path normalization and validation
- **Allowed Paths**: Only serve files from configured directories
- **Expected Response**: 400/404 for traversal attempts, never expose system files

### Authentication

- **API Key**: SHA-256 hashed, stored in environment variable
- **Exempt Paths**: `/`, `/health`, `/ready`, `/docs`, `/openapi.json`
- **Expected Response**: 401 for missing/invalid keys, 200 for valid keys

### Input Validation

- **Pydantic Schemas**: Automatic validation on all request bodies
- **Type Coercion**: Strict type checking
- **Expected Response**: 422 for validation errors with detailed error messages

## Adding New Security Tests

1. Identify the vulnerability to test
2. Create test class in appropriate file
3. Use parametrized tests for multiple payloads
4. Test both positive (should block) and negative (should allow) cases
5. Verify proper HTTP status codes and error messages
6. Document expected behavior in test docstrings

## Related Documentation

- `/backend/api/middleware/auth.py` - Authentication middleware implementation
- `/backend/api/routes/AGENTS.md` - API route handlers
- `/backend/tests/AGENTS.md` - Test infrastructure overview
- `/CLAUDE.md` - Project security requirements
