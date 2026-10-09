### Authentication Model

The system is a **single-user deployment** with two exposure modes (OD-12):

1. **SetupGuardMiddleware** returns 503 on all API requests until the first admin user is registered
2. **First-time registration** via `POST /api/auth/register` creates the admin account
3. **`EXPOSE_LAN` unset (the default):** no credential is required; the UI binds to `127.0.0.1` and that binding is the security boundary (`O1.6` landed — `setup.py` derives `FRONTEND_BIND_ADDRESS`, and compose's `:-127.0.0.1` default is the fail-safe)
4. **`EXPOSE_LAN=true`** (anything beyond this machine can reach the UI): `AuthMiddleware` refuses every request without the login session cookie from `POST /api/auth/login` or an `API_KEYS` key, except health probes, setup and login. Monitoring needs a credential too (UR-33, landed in `O1.11`): `setup.py` generates a `MONITORING_API_KEY`, mirrors it into `API_KEYS`, and Prometheus, Alertmanager, the json-exporter and Grafana's Backend-API datasource each present it, so scraping and alert delivery keep working with the gate on; `/grafana/` goes behind the app login (nginx `auth_request` + Grafana `auth.proxy` as Viewer). Logging in needs HTTPS in front, because the session cookie is `Secure`
5. **Per-route protections** (`verify_api_key`, `require_admin_access`) still guard admin/destructive operations in both modes
6. **API key auth** on those per-route guards is optionally available via `API_KEY_ENABLED=true`
