### Authentication Model

The system uses a **single-user local deployment** model:

1. **SetupGuardMiddleware** returns 503 on all API requests until the first admin user is registered
2. **First-time registration** via `POST /api/auth/register` creates the admin account
3. **After registration**, API endpoints are open for the local network — no per-request login required
4. **Network binding** to `127.0.0.1` is the primary security boundary
5. **Per-route protections** (`verify_api_key`, `require_admin_access`) guard admin/destructive operations
6. **API key auth** is optionally available via `API_KEY_ENABLED=true`
