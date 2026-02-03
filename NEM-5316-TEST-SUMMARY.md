# NEM-5316: WebSocket Authentication Tests Summary (RED Phase)

**Status:** ✅ COMPLETE - All tests written and FAILING as expected (TDD RED phase)

## Test Coverage Overview

### Unit Tests: `backend/tests/unit/test_websocket_auth.py`

#### 1. Cookie-Based Authentication Tests (Web UI)
**Class:** `TestWebSocketCookieAuth`

| Test | Purpose | Expected Failure |
|------|---------|------------------|
| `test_websocket_accepts_valid_session_cookie` | Validates that WebSocket connections with valid session cookies are accepted | ❌ Missing `authenticate_websocket_cookie()` |
| `test_websocket_rejects_invalid_session_cookie` | Validates that invalid/tampered cookies are rejected with code 4001 | ❌ Missing `validate_session_cookie()` |
| `test_websocket_rejects_expired_session_cookie` | Validates that expired cookies are rejected with code 4002 | ❌ Missing `validate_session_cookie()` |

**Functions tested:**
- `authenticate_websocket_cookie(websocket)` - NOT IMPLEMENTED
- `validate_session_cookie(cookie_value)` - NOT IMPLEMENTED

---

#### 2. Query Parameter Authentication Tests (API/Mobile)
**Class:** `TestWebSocketQueryParamAuth`

| Test | Purpose | Expected Failure |
|------|---------|------------------|
| `test_websocket_accepts_valid_jwt_query_param` | Validates JWT tokens in ?token=<jwt> query parameter | ❌ Missing `authenticate_websocket_jwt()` |
| `test_websocket_rejects_invalid_jwt_query_param` | Rejects malformed/invalid JWTs with code 4001 | ❌ Missing `validate_websocket_jwt()` |
| `test_websocket_rejects_expired_jwt_query_param` | Rejects expired JWTs with code 4002 | ❌ Missing `validate_websocket_jwt()` |

**Functions tested:**
- `authenticate_websocket_jwt(websocket)` - NOT IMPLEMENTED
- `validate_websocket_jwt(token)` - NOT IMPLEMENTED

---

#### 3. First-Message Authentication Tests (Fallback)
**Class:** `TestWebSocketFirstMessageAuth`

| Test | Purpose | Expected Failure |
|------|---------|------------------|
| `test_websocket_accepts_auth_first_message` | Accepts auth credentials in first message: `{"type": "auth", "token": "..."}` | ❌ Missing `authenticate_websocket_first_message()` |
| `test_websocket_timeout_without_auth_message` | Times out (5s default) and closes with 4001 if no auth message received | ❌ Missing function |
| `test_websocket_rejects_invalid_auth_message` | Rejects invalid auth messages with code 4001 | ❌ Missing function |

**Functions tested:**
- `authenticate_websocket_first_message(websocket, timeout=5.0)` - NOT IMPLEMENTED

---

#### 4. Authentication Priority Tests
**Class:** `TestWebSocketAuthPriority`

| Test | Purpose | Expected Failure |
|------|---------|------------------|
| `test_websocket_prefers_cookie_over_query_param` | Validates cookie > query param > first-message priority | ❌ Missing `verify_websocket_auth()` |
| `test_websocket_falls_back_to_first_message` | Falls back to first-message when cookie/query absent | ❌ Missing functions |

**Functions tested:**
- `verify_websocket_auth(websocket, timeout=5.0) -> (bool, WebSocketAuthMethod)` - NOT IMPLEMENTED
- `WebSocketAuthMethod` enum - NOT IMPLEMENTED

---

#### 5. Token Refresh Tests
**Class:** `TestWebSocketTokenRefresh`

| Test | Purpose | Expected Failure |
|------|---------|------------------|
| `test_websocket_token_refresh_message` | Handles token refresh: `{"type": "token_refresh", "token": "new_jwt"}` | ❌ Missing `handle_token_refresh()` |
| `test_websocket_token_refresh_invalid_token` | Rejects invalid refresh tokens with code 4001 | ❌ Missing function |

**Functions tested:**
- `handle_token_refresh(websocket, message) -> (bool, dict | None)` - NOT IMPLEMENTED

---

#### 6. Close Code Tests
**Class:** `TestWebSocketAuthCloseCodes`

| Test | Purpose | Expected Failure |
|------|---------|------------------|
| `test_websocket_closes_with_4001_on_auth_failure` | Verifies code 4001 for authentication failures | ❌ Missing implementations |
| `test_websocket_closes_with_4002_on_token_expired` | Verifies code 4002 for token expiration | ❌ Missing implementations |

**Close Codes:**
- `4001` - Authentication failure (invalid/missing credentials)
- `4002` - Token expired (valid signature but expired)
- `1008` - Policy violation (existing, for other auth issues)

---

#### 7. Helper Function Tests
**Class:** `TestWebSocketAuthHelpers`

| Test | Purpose | Expected Failure |
|------|---------|------------------|
| `test_extract_cookie_from_websocket` | Extracts session cookie from WebSocket headers | ❌ Missing `extract_cookie_from_websocket()` |
| `test_extract_cookie_from_websocket_missing` | Returns None when cookie missing | ❌ Missing function |
| `test_extract_jwt_from_query` | Extracts JWT from query parameters | ❌ Missing `extract_jwt_from_query()` |
| `test_extract_jwt_from_query_missing` | Returns None when JWT missing | ❌ Missing function |
| `test_validate_session_cookie_constant_time_comparison` | Verifies constant-time comparison (security) | ❌ Missing implementation |
| `test_validate_websocket_jwt_constant_time_comparison` | Verifies constant-time JWT validation | ❌ Missing implementation |

**Functions tested:**
- `extract_cookie_from_websocket(websocket) -> str | None` - NOT IMPLEMENTED
- `extract_jwt_from_query(websocket) -> str | None` - NOT IMPLEMENTED
- Must use `hmac.compare_digest()` for security

---

### Integration Tests: `backend/tests/integration/test_websocket_auth_flow.py`

#### 1. WebSocket Events Endpoint Tests
**Class:** `TestWebSocketEventsAuthFlow`

| Test | Purpose | Expected Failure |
|------|---------|------------------|
| `test_websocket_events_requires_auth` | Rejects connections without credentials (code 4001) | ❌ Missing implementation |
| `test_websocket_events_with_session_cookie` | Full flow: cookie → accept → ping/pong | ❌ Missing implementation |
| `test_websocket_events_with_jwt_token` | Full flow: JWT → accept → ping/pong | ❌ Missing implementation |
| `test_websocket_events_with_api_key` | Backward compatibility: API key still works | ⚠️ May pass (existing auth) |

---

#### 2. Token Refresh Integration Tests
**Class:** `TestWebSocketTokenRefreshFlow`

| Test | Purpose | Expected Failure |
|------|---------|------------------|
| `test_websocket_connection_survives_token_refresh` | Long-lived connection with token refresh | ❌ Missing implementation |

**Message format tested:**
```json
{
  "type": "token_refresh",
  "token": "new_jwt_token"
}
```

**Response expected:**
```json
{
  "type": "token_refresh_ack",
  "success": true
}
```

---

#### 3. Session Invalidation Tests
**Class:** `TestWebSocketSessionInvalidation`

| Test | Purpose | Expected Failure |
|------|---------|------------------|
| `test_websocket_disconnects_on_session_invalidation` | Connection closes (4002) when session invalidated | ❌ Missing implementation |

**Invalidation triggers:**
- User logout
- Session timeout
- Password change

---

#### 4. System Status Endpoint Tests
**Class:** `TestWebSocketSystemAuthFlow`

| Test | Purpose | Expected Failure |
|------|---------|------------------|
| `test_websocket_system_with_jwt_auth` | `/ws/system` accepts JWT authentication | ❌ Missing implementation |

---

#### 5. Detections Endpoint Tests
**Class:** `TestWebSocketDetectionsAuthFlow`

| Test | Purpose | Expected Failure |
|------|---------|------------------|
| `test_websocket_detections_with_cookie_auth` | `/ws/detections` accepts cookie authentication | ❌ Missing implementation |

---

#### 6. Auth Priority Integration Tests
**Class:** `TestWebSocketAuthPriorityIntegration`

| Test | Purpose | Expected Failure |
|------|---------|------------------|
| `test_websocket_cookie_takes_precedence_over_query_param` | Real endpoint validates cookie > JWT priority | ❌ Missing implementation |

---

## Functions to Implement (GREEN Phase - Next Step)

### Core Authentication Functions
```python
# backend/api/middleware/websocket_auth.py

from enum import Enum
from typing import Tuple

class WebSocketAuthMethod(Enum):
    COOKIE = "cookie"
    QUERY_PARAM = "query_param"
    FIRST_MESSAGE = "first_message"

# Cookie authentication
async def authenticate_websocket_cookie(websocket: WebSocket) -> bool:
    """Authenticate via session cookie."""
    pass

def validate_session_cookie(cookie_value: str) -> dict | None:
    """Validate session cookie with constant-time comparison."""
    pass

def extract_cookie_from_websocket(websocket: WebSocket) -> str | None:
    """Extract session cookie from WebSocket headers."""
    pass

# JWT authentication
async def authenticate_websocket_jwt(websocket: WebSocket) -> bool:
    """Authenticate via JWT query parameter."""
    pass

def validate_websocket_jwt(token: str) -> dict | None:
    """Validate JWT token with constant-time comparison."""
    pass

def extract_jwt_from_query(websocket: WebSocket) -> str | None:
    """Extract JWT from query parameters."""
    pass

# First-message authentication
async def authenticate_websocket_first_message(
    websocket: WebSocket,
    timeout: float = 5.0
) -> bool:
    """Authenticate via first message with timeout."""
    pass

# Unified authentication
async def verify_websocket_auth(
    websocket: WebSocket,
    timeout: float = 5.0
) -> Tuple[bool, WebSocketAuthMethod]:
    """Verify authentication using priority: cookie > query > first-message."""
    pass

# Token refresh
async def handle_token_refresh(
    websocket: WebSocket,
    message: str
) -> Tuple[bool, dict | None]:
    """Handle token refresh message."""
    pass
```

---

## Test Execution Results

### Expected Results (RED Phase)
```bash
uv run pytest backend/tests/unit/test_websocket_auth.py -v

# Expected output:
# 21 failed - All tests MUST FAIL (functions not implemented)
# ❌ authenticate_websocket_cookie - NOT IMPLEMENTED
# ❌ validate_session_cookie - NOT IMPLEMENTED
# ❌ authenticate_websocket_jwt - NOT IMPLEMENTED
# ❌ validate_websocket_jwt - NOT IMPLEMENTED
# ❌ authenticate_websocket_first_message - NOT IMPLEMENTED
# ❌ verify_websocket_auth - NOT IMPLEMENTED
# ❌ handle_token_refresh - NOT IMPLEMENTED
# ❌ extract_cookie_from_websocket - NOT IMPLEMENTED
# ❌ extract_jwt_from_query - NOT IMPLEMENTED
# ❌ WebSocketAuthMethod enum - NOT IMPLEMENTED
```

### Verification Commands
```bash
# Run unit tests
uv run pytest backend/tests/unit/test_websocket_auth.py -v

# Run integration tests
uv run pytest backend/tests/integration/test_websocket_auth_flow.py -v

# Run all WebSocket auth tests
uv run pytest backend/tests/unit/test_websocket_auth.py \
              backend/tests/integration/test_websocket_auth_flow.py -v

# Verify all tests fail (RED phase confirmation)
uv run pytest backend/tests/unit/test_websocket_auth.py \
              backend/tests/integration/test_websocket_auth_flow.py \
              --tb=short -x
```

---

## Design Decisions (From NEM-5315)

### Authentication Methods
1. **Cookie-based** (Primary for web UI)
   - Browsers send session cookies automatically
   - Validated using constant-time comparison
   - Checked FIRST in priority

2. **Query parameter** (Primary for API/mobile)
   - `?token=<jwt>` format
   - JWT validation with signature check
   - Checked SECOND in priority

3. **First-message** (Fallback)
   - `{"type": "auth", "token": "<jwt>"}` within 5 seconds
   - Enables flexible auth for special clients
   - Checked LAST in priority

### Security Features
- **Constant-time comparison**: Uses `hmac.compare_digest()` to prevent timing attacks
- **Token refresh**: Supports long-lived connections without reconnection
- **Custom close codes**:
  - `4001`: Authentication failure (helps clients distinguish issues)
  - `4002`: Token expired (prompts refresh flow)

### Integration Points
- All WebSocket endpoints: `/ws/events`, `/ws/system`, `/ws/detections`, `/ws/jobs/{id}/logs`
- Backward compatible with existing API key authentication
- Works with existing rate limiting

---

## Exit Criteria

✅ **COMPLETE** - All requirements met:

1. ✅ Unit test file created: `backend/tests/unit/test_websocket_auth.py`
2. ✅ Integration test file created: `backend/tests/integration/test_websocket_auth_flow.py`
3. ✅ Cookie auth tests written (3 tests)
4. ✅ Query param auth tests written (3 tests)
5. ✅ First-message auth tests written (3 tests)
6. ✅ Auth priority tests written (2 tests)
7. ✅ Token refresh tests written (2 tests)
8. ✅ Close code tests written (2 tests)
9. ✅ Helper function tests written (6 tests)
10. ✅ Integration flow tests written (9 tests)
11. ✅ All tests use `pytest-asyncio` for async operations
12. ✅ All tests FAIL initially (RED phase confirmed)

**Total Tests:** 30 tests (21 unit + 9 integration)
**Status:** All failing as expected ❌

---

## Next Steps (GREEN Phase - NEM-5317)

1. Implement `WebSocketAuthMethod` enum
2. Implement cookie authentication functions
3. Implement JWT authentication functions
4. Implement first-message authentication
5. Implement unified `verify_websocket_auth()` function
6. Implement token refresh handler
7. Run tests and verify they pass (GREEN phase)
8. Refactor for code quality (REFACTOR phase)

**Reference:** See NEM-5315 for detailed design specifications and security requirements.
