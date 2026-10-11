### Authentication Model

The system is a **single-user deployment** with two exposure modes (OD-12):

1. **SetupGuardMiddleware** returns 503 on all API requests until the first admin user is registered
2. **First-time registration** via `POST /api/auth/register` creates the admin account
3. **`EXPOSE_LAN` unset (the default):** no credential is required; the UI binds to `127.0.0.1` and that binding is the security boundary (`O1.6` landed — `setup.py` derives `FRONTEND_BIND_ADDRESS`, and compose's `:-127.0.0.1` default is the fail-safe)
4. **`EXPOSE_LAN=true`** (anything beyond this machine can reach the UI): `AuthMiddleware` refuses every request without the login session cookie from `POST /api/auth/login` or an `API_KEYS` key, except health probes, setup and login. Monitoring needs a credential too (UR-33, landed in `O1.11`): `setup.py` generates a `MONITORING_API_KEY`, mirrors it into `API_KEYS` as an entry scoped to `monitoring` (R60 — it can read exactly the monitoring paths, not the whole API), and Prometheus, Alertmanager, the json-exporter and Grafana's Backend-API datasource each present it, so scraping and alert delivery keep working with the gate on; `/grafana/` goes behind the app login (nginx `auth_request` + Grafana `auth.proxy` as Viewer). Logging in over a plain-`http` LAN address needs `SESSION_COOKIE_SECURE=false` (the cookie is `Secure` by default, and a browser drops a `Secure` cookie on an http origin, looping the login) — the full http/TLS/cookie trade-off and the startup warning are in **The login cookie over http and TLS** in the Environment Reference (R55 — the link lives in each host page, not here; see the maintainer note at the end of this file)
5. **Per-route protections** (`verify_api_key`, `require_admin_access`) still guard admin/destructive operations in both modes
6. **API key auth** on those per-route guards is optionally available via `API_KEY_ENABLED=true`

<!-- Maintainer note (R55): do not put a relative link in this file. pymdownx
snippets substitutes text in place, so a relative link resolves against each
HOST page's directory, and this snippet's hosts do not share a depth:
docs/architecture/overview.md is 1 directory under docs/, while
docs/architecture/security/README.md is 2. One shared relative path therefore
cannot serve both — the shallower host silently escapes docs/ and mkdocs emits
the unresolved href verbatim (a deployed 404). Site-root links are not a fix
either: site_url puts this site under a project path, so /reference/... 404s at
the root. Put host-specific links in the host pages instead, and keep this
file link-free. Verified with `mkdocs build` plus a grep of the built hosts. -->
