# API Middleware

## Middleware Chain

![API Middleware Chain](../../../docs/images/architecture/middleware-chain.png)

_HTTP request/response flow through the middleware chain showing execution order._

## Authentication Middleware

Basic API key authentication middleware for securing API endpoints.

### Configuration

Authentication is **disabled by default** for development convenience. Enable it using environment variables:

```bash
# Enable authentication
export API_KEY_ENABLED=true

# Set valid API keys (JSON array)
export API_KEYS='["your_secret_key_1", "your_secret_key_2"]'
```

Or in `.env`:

```env
API_KEY_ENABLED=true
API_KEYS=["your_secret_key_1", "your_secret_key_2"]
```

### Usage

#### With Header (Recommended)

```bash
curl -H "X-API-Key: your_secret_key_1" http://localhost:8000/api/cameras
```

#### With Query Parameter

```bash
curl http://localhost:8000/api/cameras?api_key=your_secret_key_1
```

### Exempt Endpoints

The following endpoints bypass authentication:

- `/` - Root endpoint
- `/health` - Health check
- `/api/system/health` - System health check
- `/docs` - API documentation (Swagger UI)
- `/redoc` - API documentation (ReDoc)
- `/openapi.json` - OpenAPI schema

### Security Notes

1. **Keys are hashed**: API keys are hashed using SHA-256 before validation
2. **Header priority**: `X-API-Key` header takes precedence over `api_key` query parameter
3. **No database storage**: Keys are configured via environment variables (stored hashes can be added to database in future)
4. **Development mode**: Authentication is disabled by default (`API_KEY_ENABLED=false`)

### Error Responses

#### Missing API Key

```json
HTTP 401 Unauthorized
{
  "detail": "API key required. Provide via X-API-Key header or api_key query parameter."
}
```

#### Invalid API Key

```json
HTTP 401 Unauthorized
{
  "detail": "Invalid API key"
}
```

### Testing

Run unit tests:

```bash
python -m pytest backend/tests/unit/test_auth_middleware.py -v
```

### Future Enhancements

- Database storage for API keys with metadata (name, created_at, is_active)
- Key rotation and expiration
- Rate limiting per API key
- Audit logging of API key usage
- Key permissions/scopes
