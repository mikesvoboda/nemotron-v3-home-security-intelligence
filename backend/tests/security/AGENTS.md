# Security Tests Directory

## Purpose

This directory contains security-focused tests that verify the application's resistance to common web security vulnerabilities. These tests complement static analysis tools (Semgrep, Bandit) and dynamic scanners (OWASP ZAP) with targeted API-level security validation.

## Directory Structure

```
backend/tests/security/
├── AGENTS.md              # This file
├── __init__.py            # Package initialization
├── conftest.py            # Security test fixtures
├── test_api_security.py   # SQL injection, XSS, path traversal, rate limiting, CORS
├── test_auth_security.py  # API key auth, admin endpoints, authorization bypass
└── test_input_validation.py  # Boundary values, type confusion, Unicode, encoding attacks
```

## Running Security Tests

```bash
# Run all security tests
uv run pytest backend/tests/security/ -v

# Run specific test file
uv run pytest backend/tests/security/test_api_security.py -v

# Run specific test class
uv run pytest backend/tests/security/test_api_security.py::TestSQLInjection -v

# Run with coverage
uv run pytest backend/tests/security/ -v --cov=backend --cov-report=term-missing
```

## Test Categories

### API Security Tests (`test_api_security.py`)

| Test Class                 | Coverage                                                  |
| -------------------------- | --------------------------------------------------------- |
| `TestSQLInjection`         | SQL injection in query params, path params, JSON bodies   |
| `TestXSSPrevention`        | XSS payloads in query params and JSON bodies              |
| `TestPathTraversal`        | Path traversal in camera IDs and media endpoints          |
| `TestRateLimiting`         | Rate limit header presence and excessive request handling |
| `TestCORSConfiguration`    | CORS preflight and credentials handling                   |
| `TestSecurityHeaders`      | Content-Type, server version disclosure, cache control    |
| `TestErrorMessageSecurity` | Stack trace exposure, internal path disclosure            |

### Auth Security Tests (`test_auth_security.py`)

| Test Class                  | Coverage                                                   |
| --------------------------- | ---------------------------------------------------------- |
| `TestAPIKeySecurity`        | Invalid keys, missing keys, timing attacks, malicious keys |
| `TestAdminEndpointSecurity` | DEBUG mode protection, admin operation logging             |
| `TestSessionSecurity`       | Cookie flags, session fixation                             |
| `TestAuthorizationBypass`   | Method override, case sensitivity, URL encoding bypasses   |
| `TestPrivilegeEscalation`   | Data modification, ID manipulation, mass assignment        |

### Input Validation Tests (`test_input_validation.py`)

| Test Class                     | Coverage                                             |
| ------------------------------ | ---------------------------------------------------- |
| `TestBoundaryValues`           | Integer boundaries, empty strings, very long strings |
| `TestTypeConfusion`            | Type mismatches, nested objects, arrays              |
| `TestUnicodeHandling`          | Special Unicode, normalization, homoglyphs           |
| `TestContentTypeValidation`    | JSON Content-Type requirements, multipart handling   |
| `TestRequestSizeLimits`        | Large JSON bodies, many query params/headers         |
| `TestSpecialCharacterHandling` | Control characters, null bytes                       |
| `TestJSONParsingSecurity`      | Duplicate keys, comments, trailing commas            |
| `TestEncodingAttacks`          | Mixed encoding, overlong UTF-8                       |

## Security Testing Strategy

### Defense in Depth

Security tests are part of a layered security approach:

1. **Pre-commit** - Semgrep static analysis, detect-secrets
2. **CI** - Bandit, Gitleaks, Trivy container scanning, npm audit
3. **Integration tests** - This security test suite
4. **Weekly** - OWASP ZAP dynamic scanning

### Test Design Principles

1. **Negative testing** - Focus on what should be rejected
2. **Parameterized attacks** - Test multiple attack variants
3. **Safe assertions** - Verify handling without exposing system to risk
4. **Informative failures** - Clear messages indicating vulnerability type

### OWASP Top 10 Coverage

| OWASP 2021                    | Test Coverage                                    |
| ----------------------------- | ------------------------------------------------ |
| A01 Broken Access Control     | TestAuthorizationBypass, TestPrivilegeEscalation |
| A02 Cryptographic Failures    | (handled by infrastructure, not API tests)       |
| A03 Injection                 | TestSQLInjection, TestXSSPrevention              |
| A04 Insecure Design           | TestMassAssignment, TestTypeConfusion            |
| A05 Security Misconfiguration | TestSecurityHeaders, TestCORSConfiguration       |
| A06 Vulnerable Components     | (handled by Trivy, npm audit)                    |
| A07 Auth Failures             | TestAPIKeySecurity, TestSessionSecurity          |
| A08 Software/Data Integrity   | (handled by SAST tools)                          |
| A09 Logging Failures          | TestErrorMessageSecurity                         |
| A10 SSRF                      | TestPathTraversal (partial)                      |

## Adding New Security Tests

When adding new security tests:

1. **Identify the vulnerability class** - Reference OWASP, CWE, etc.
2. **Create parameterized tests** - Test multiple attack variants
3. **Use descriptive names** - Test name should indicate what's being tested
4. **Document scenarios** - Include docstrings explaining the attack
5. **Safe assertions** - Assert on status codes, not response content leaking info

Example pattern:

```python
@pytest.mark.parametrize(
    "payload,description",
    [
        ("attack1", "description of attack variant 1"),
        ("attack2", "description of attack variant 2"),
    ],
)
@pytest.mark.asyncio
async def test_vulnerability_class_blocked(
    self, security_client: AsyncClient, payload: str, description: str
):
    """Test that {vulnerability_class} attacks are blocked.

    Scenario: {description}
    """
    response = await security_client.get(f"/api/endpoint/{payload}")
    assert response.status_code != 500, f"Server error indicates vulnerability: {description}"
    assert response.status_code in [400, 403, 404], f"Attack may have succeeded: {description}"
```

## Related Documentation

- `/CLAUDE.md` - Project instructions including security testing requirements
- `/.pre-commit-config.yaml` - Pre-commit security hooks (detect-secrets, Semgrep)
- `/.github/workflows/sast.yml` - Static analysis CI workflow
- `/.github/workflows/gitleaks.yml` - Secret detection CI workflow
- `/.github/workflows/trivy.yml` - Container vulnerability scanning
- `/.github/workflows/zap-scan.yml` - OWASP ZAP dynamic scanning
- `/.zap/rules.tsv` - ZAP scan rule configuration
- `/.secrets.baseline` - Known false positives for detect-secrets
- `/.gitleaks.toml` - Gitleaks configuration
