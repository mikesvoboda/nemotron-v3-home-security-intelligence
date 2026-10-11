# Security: API Key Query Parameters

> **WARNING:** Passing API keys in URL query parameters exposes them to multiple security risks. This document explains the risks and recommended alternatives.

---

## Overview

This system supports API key authentication via two methods:

1. **HTTP Header (Recommended):** `X-API-Key: your-key`
2. **Query Parameter (Insecure):** `?api_key=your-key`

For WebSocket connections, there are also two methods:

1. **Sec-WebSocket-Protocol Header (Recommended):** `api-key.your-key`
2. **Query Parameter (Insecure):** `ws://host/ws/events?api_key=your-key`

**Always prefer header-based authentication over query parameters.**

Browsers use neither form: the session cookie from the login authenticates
the browser (ruling 44 — no API key may exist inside the served bundle), so
everything below describes **non-browser clients** (scripts, services, CLIs).

---

## Security Risks of Query Parameter API Keys

### 1. Server Access Logs

API keys in URLs are logged by web servers, load balancers, and reverse proxies:

```
# Nginx access log example
192.168.1.100 - - [03/Jan/2026:10:30:45 +0000] "GET /api/events?api_key=sk-secret-key-12345 HTTP/1.1" 200 1234
```

**Impact:**

- API keys persist in log files indefinitely
- Log aggregation systems (Splunk, ELK, CloudWatch) store the keys
- Log files may be backed up, increasing exposure surface
- System administrators with log access can see API keys

### 2. Browser History

URLs with query parameters are stored in browser history:

```
# Chrome History database (SQLite)
URL: https://security.local:8000/api/events?api_key=sk-secret-key-12345
Title: Security Events
Last Visit: 2026-01-03T10:30:45Z
```

**Impact:**

- Anyone with access to the device can view API keys
- Browser sync features may propagate keys to other devices
- History persists after logout/session end
- Browser profiles can be exported, exposing stored URLs

### 3. HTTP Referer Headers

When navigating from a page with query parameters to another site, the full URL (including query parameters) may be sent in the `Referer` header:

```http
GET /some-page HTTP/1.1
Host: external-site.com
Referer: https://security.local:8000/api/events?api_key=sk-secret-key-12345
```

**Impact:**

- External sites receive your API key
- Analytics services (Google Analytics, etc.) may log the referrer
- Third-party scripts embedded in pages can read `document.referrer`
- CDN and proxy logs on the external site capture the referrer

### 4. Shared Links and Screenshots

URLs are often shared via:

- Copy/paste to chat applications
- Screenshots of browser windows
- Browser developer tools (visible in Network tab)
- Email clients showing full URLs

**Impact:**

- Unintentional disclosure of API keys
- Keys visible in screen recordings or live streams
- Keys captured in bug reports and support tickets

### 5. Browser Extensions

Browser extensions may access and transmit URL data:

```javascript
// Malicious or compromised extension
chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    // details.url includes query parameters with API keys
    sendToAttacker(details.url);
  },
  { urls: ['<all_urls>'] }
);
```

**Impact:**

- Extensions can harvest API keys from URLs
- Legitimate extensions with data collection may inadvertently capture keys
- Browser sync features may expose extension data

### 6. Proxy and CDN Logging

Intermediate systems between client and server log URLs:

```
# Corporate proxy log
2026-01-03 10:30:45 GET https://security.local:8000/api/events?api_key=sk-secret-key-12345 200
```

**Impact:**

- Corporate networks log all HTTPS URLs (even with TLS, the URL path is visible before encryption)
- CDN providers (Cloudflare, AWS CloudFront) may log request URLs
- Security appliances (WAF, IDS) log URLs for analysis

### 7. Caching

URLs are used as cache keys:

```
# Browser cache
/api/events?api_key=sk-secret-key-12345 -> cached_response_hash
```

**Impact:**

- API keys persist in browser cache
- Shared caches (CDN, reverse proxy) may cache responses keyed by URL
- Cache inspection tools expose URLs with keys

---

## Where Query Parameters Are Currently Supported

### Backend Middleware (`backend/api/middleware/auth.py`)

The authentication middleware accepts API keys from both sources:

```python
# Extract API key from header or query parameter
api_key = request.headers.get("X-API-Key")
if not api_key:
    api_key = request.query_params.get("api_key")
```

**Order of precedence:** Header takes priority over query parameter.

### WebSocket Endpoints (`backend/api/routes/websocket.py`)

WebSocket connections accept API keys via:

1. Query parameter: `ws://host/ws/events?api_key=YOUR_KEY`
2. Sec-WebSocket-Protocol header: `api-key.YOUR_KEY`

```python
# WebSocket authentication
api_key = websocket.query_params.get("api_key")

# Fall back to Sec-WebSocket-Protocol header
if not api_key:
    protocols = websocket.headers.get("sec-websocket-protocol", "")
    for protocol in protocols.split(","):
        if protocol.strip().startswith("api-key."):
            api_key = protocol.strip()[8:]
            break
```

### Frontend API Client (`frontend/src/services/api.ts`)

The frontend's WebSocket builder mints no credential at all:

```typescript
// Ruling 44: Vite inlines VITE_* values into the served bundle, so no key may
// exist in frontend code to attach. The browser socket is authenticated by the
// session cookie the login endpoint sets.
export function buildWebSocketOptions(endpoint: string): { url: string } {
  // Returns { url } only — no protocols, no key.
}
```

---

## Recommended Practices

### For HTTP Requests

Always use the `X-API-Key` header:

```bash
# Correct: Header-based authentication
curl -H "X-API-Key: your-api-key" https://localhost:8000/api/events

# Avoid: Query parameter authentication
curl "https://localhost:8000/api/events?api_key=your-api-key"
```

### For WebSocket Connections (non-browser clients)

Use the Sec-WebSocket-Protocol header:

```javascript
// CORRECT: API key in protocol header
const ws = new WebSocket('ws://localhost:8000/ws/events', ['api-key.your-api-key']);

// AVOID: API key in URL query parameter
const ws = new WebSocket('ws://localhost:8000/ws/events?api_key=your-api-key');
```

In the browser there is nothing to attach — the cookie jar authenticates the
handshake:

```typescript
import { buildWebSocketOptions } from '../services/api';

// Returns { url: 'ws://localhost:8000/ws/events' } — no protocols (ruling 44).
const options = buildWebSocketOptions('/ws/events');
const ws = new WebSocket(options.url);
```

The `api-key.…` protocol form above is for scripted non-browser clients that
hold a key: they pass it explicitly, and the server echoes it back (the B-1
behaviour pinned by `backend/tests/integration/test_ws_subprotocol_echo_b1.py`).

### For Documentation and Examples

When documenting API usage:

```markdown
<!-- CORRECT: Show header authentication -->

curl -H "X-API-Key: \$API_KEY" https://localhost:8000/api/events

<!-- AVOID: Query parameter examples -->

curl "https://localhost:8000/api/events?api_key=\$API_KEY"
```

---

## Mitigations in This Codebase

### 1. Log Sanitization

The backend sanitizes sensitive data in logs (`backend/core/sanitization.py`):

```python
# API keys in log output are redacted
(re.compile(r"api[_-]?key[=:]\s*\S+", re.IGNORECASE), "api_key=[REDACTED]")
```

### 2. Browser Code Carries No Credential

The hooks that open sockets (e.g. `frontend/src/hooks/useEventStream.ts`) say
plainly that keys are for non-browser clients and the browser socket rides the
session cookie. `frontend/src/__tests__/no-browser-api-key.test.ts` fails CI if
browser code reads the key env var or mints the subprotocol form again.

### 3. The Query-Parameter Builder Is Deleted, Not Deprecated

`buildWebSocketUrl()` no longer exists in the frontend. It existed only to move
a baked-in key into a URL, so ruling 44 removed it outright — a deprecated
function is one refactor away from being called again.

### 4. Header Priority

When both header and query parameter are provided, the header takes precedence, allowing gradual migration away from query parameters.

---

## Configuration Recommendations

### Disable Query Parameter Authentication (Future)

Consider configuring your deployment to reject API keys in query parameters:

```bash
# Future enhancement: environment variable to disable query param auth
API_KEY_QUERY_PARAM_ENABLED=false
```

### Enable HTTPS/TLS

Always use TLS in production to encrypt API keys in transit:

```bash
TLS_MODE=provided
TLS_CERT_PATH=/path/to/cert.pem
TLS_KEY_PATH=/path/to/key.pem
```

### Rotate API Keys

Regularly rotate API keys to limit exposure window if a key is compromised:

```bash
# Generate new API key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Update environment and redeploy
API_KEYS=["new-key-here"]
```

---

## See Also

- [Security Guide](security.md) - Comprehensive security configuration
- [API Reference Overview](../../developer/api/README.md) - API authentication details
- [WebSocket API](../../developer/api/realtime.md) - WebSocket authentication methods
- [Configuration Reference](../../reference/config/env-reference.md) - Environment variable reference

---

## References

- [OWASP API Security - Broken Authentication](https://owasp.org/API-Security/editions/2023/en/0xa2-broken-authentication/)
- [RFC 6750 - Bearer Token Usage (OAuth 2.0)](https://datatracker.ietf.org/doc/html/rfc6750#section-2.3) - Recommends against query parameters
- [CWE-598: Use of GET Request Method With Sensitive Query Strings](https://cwe.mitre.org/data/definitions/598.html)
