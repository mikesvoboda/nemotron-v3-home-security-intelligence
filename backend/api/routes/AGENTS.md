# Backend API Routes - Agent Guide

## Purpose

`backend/api/routes/` holds the FastAPI router modules — 56 files, one
resource family each (cameras, events, detections, media, websocket,
system, …). Routes are thin: take dependencies, validate through
`backend/api/schemas/`, call a service or repository, return a schema.
Business logic belongs in `backend/services/`; a route module that grows
branching logic is a refactor signal, not a pattern to extend.

## Entry Points

| File           | Role                                                                                       |
| -------------- | ------------------------------------------------------------------------------------------ |
| `__init__.py`  | Re-exports the routers `backend/main.py` registers (`app.include_router(...)` — 60 calls)  |
| `cameras.py`   | Camera CRUD, snapshots (`FileResponse` + path-traversal check), baseline config (NEM-4921) |
| `events.py`    | Event search/export/streaming; the optimistic-locking 409 contract                         |
| `system.py`    | System status + the worker registration `register_workers()` main.py calls at boot         |
| `websocket.py` | The live WS endpoint: rate-limit then `authenticate_websocket` BEFORE accept               |
| `media.py`     | File serving with its own traversal protection                                             |

## The Rules (do not regress)

- **Register in `backend/main.py`, in its include block.** The import
  block (`from backend.api.routes import (...)`) and the `include_router`
  calls are the registration record; a router file added without both is
  dead surface. 55 of the 56 modules declare `prefix="/api/..."` — the
  prefix lives on the `APIRouter(...)`, and the OpenAPI snapshot +
  compatibility gate see the result.
- **Auth is two layers, and the route layer never replaces the gate.**
  `AuthMiddleware` (OD-12) refuses every uncredentialled request under
  `EXPOSE_LAN=true` except `OPEN_PATHS` (the health/auth set in
  `backend/api/middleware/auth.py`, pinned by
  `backend/tests/unit/api/middleware/test_auth.py::test_open_paths_are_the_documented_allowlist`).
  Per-route guards (`verify_api_key`, `require_admin_access`,
  `get_current_admin_user`) still run after it. The inbound-webhook key
  check (`require_api_key`, B1.3) is ALWAYS on — it does not honour
  `api_key_enabled` (fail-closed; D3). Websockets authenticate before
  accept; a failed handshake closes with code 4001, and the accept echoes
  an offered `api-key.*` subprotocol verbatim (B-1) so the browser sees a
  terminal close, not a retried 1006.
- **Optimistic-locking conflicts surface as 409.** `StaleDataError`
  handlers re-fetch and return HTTP 409 with the current version
  (`backend/api/routes/events.py`, NEM-3625) — a write route over a
  version_id model must repeat that contract, not swallow the error.
- **Errors return RFC 7807 Problem Details or `HTTPException` — never
  ad-hoc JSON.** The handlers in `backend/api/exception_handlers.py` map
  raised exceptions to `application/problem+json`.
- **Cache invalidation goes to `BackgroundTasks`** (NEM-3744): the
  response commits first, `_invalidate_events_cache_background`-style
  tasks run after — do not invalidate inline ahead of the commit.
- **Rate limiting is a per-route dependency**: `_rate_limit: None =
Depends(RateLimiter(tier=RateLimitTier.DEFAULT))`. Media/export/search
  endpoints take their tier (`MEDIA`, `EXPORT`, …) from
  `backend/api/middleware/rate_limit.py`.

## Patterns

- **Annotated aliases for dependencies** (`backend/api/dependencies.py`):
  `db: DbSession`, `cache: CacheDep`, `orchestrator: OrchestratorDep` —
  import the alias, not the raw `get_*` function, so the wiring stays in
  one place. Lookups use the shared `get_camera_or_404` /
  `get_event_or_404` helpers.
- **Pagination takes `cursor`** (`backend/api/pagination.py`); combining
  `offset` with `cursor` raises. New endpoints declare `cursor` only.
- **Field selection**: several list endpoints honour a field-selection
  query parameter to trim payloads (pinned per module in
  `backend/tests/unit/api/routes/test_*_field_selection.py`).

## Traps

- **The endpoint inventory is gone on purpose** (W1.3 banner → W3.2):
  the old file's per-file endpoint tables drifted as routes moved; the
  code and `app.openapi()` are the source of truth now. Do not
  re-introduce per-file endpoint tables here.
- **The materialized-view admin surface is retired (R-T9-MVSOURCE)** —
  `app.openapi()` must not expose `/api/admin/materialized-views*` and
  the five modules must stay unimportable
  (`backend/tests/unit/api/test_materialized_views_retired.py` locks both
  angles; restoring the feature means rewriting the lock, not deleting
  it).
- **Snapshot serving is exempt from API-key auth deliberately** — the
  camera snapshot route serves static images to `<img>` tags and carries
  its own controls (traversal check, file-type allowlist, its own rate
  limiter). Exemptions live in `OPEN_PATHS` / the route's own guard, not
  in middleware flags.
- Retired names sit under fall-only ratchet baselines
  (`.agents-md-validator.yml`); new prose mentions of the retired stack
  fail the AGENTS.md validator — the name list lives in
  `backend/AGENTS.md`.

## How to Test

```bash
uv run pytest backend/tests/unit/api/routes/ -n auto --dist=worksteal --timeout=60
```

102 test files mirror the modules (one or more per route file, plus the
field-selection and pagination slices). Route tests drive the app or
router directly; middleware behaviour lives under
`backend/tests/unit/api/middleware/`.

## Related

| Path                            | What it holds                                              |
| ------------------------------- | ---------------------------------------------------------- |
| `backend/api/AGENTS.md`         | the API layer: middleware stack, error contract, snapshots |
| `backend/api/schemas/AGENTS.md` | the request/response schemas routes declare                |
| `backend/api/dependencies.py`   | the `Annotated` alias table routes import from             |
| `backend/services/AGENTS.md`    | the services routes delegate to                            |
| `backend/AGENTS.md`             | the lane root: lane-wide rules, the AI tier, how to test   |
