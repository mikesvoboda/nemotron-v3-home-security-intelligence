# Backend API - Agent Guide

## Purpose

`backend/api/` is the FastAPI layer: `main.py`'s middleware stack, the
route modules under `routes/`, the Pydantic request/response schemas under
`schemas/`, and the shared dependency aliases, pagination and error
contract. Routes are thin: they validate through schemas, take services
from `dependencies.py`'s `Annotated` aliases, and delegate to
`backend/services/`.

## Entry Points

| File                    | Role                                                                                                                                                      |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dependencies.py`       | The `Annotated` alias table (`DbSession`, `ReadDbSession`, `RedisDep`, `CacheDep`, `OrchestratorDep`, …) plus `get_*_or_404` lookups and the analyzer dep |
| `exception_handlers.py` | The RFC 7807 `application/problem+json` handlers registered on the app                                                                                    |
| `pagination.py`         | Cursor-based pagination (`encode_cursor`/`decode_cursor`), cursor-injection hardened (NEM-2602)                                                           |
| `validators.py`         | Date-range, camera-id and risk-score parameter validators                                                                                                 |
| `middleware/`           | 15 ASGI middleware modules; the stack order lives in `backend/main.py`                                                                                    |
| `routes/`, `schemas/`   | See their own `AGENTS.md` files                                                                                                                           |

## The Rules (do not regress)

- **`AuthMiddleware` is added LAST so it runs FIRST** — nothing, not even
  an idempotent replay, answers an unchecked request (`backend/main.py`
  comments it; the full middleware order is read bottom-up from the
  `add_middleware` calls there). With `EXPOSE_LAN` unset it passes
  everything; the published-ports binding is the boundary. Guard:
  `backend/tests/unit/api/middleware/test_auth.py` +
  `backend/tests/unit/api/test_expose_lan_routes.py` (the route-table
  enumeration and the every-route-refuses matrix).
- **Errors are RFC 7807 Problem Details** (`backend/api/schemas/problem_details.py`,
  media type `application/problem+json`). New error paths return
  `ProblemDetail` through the handlers in `exception_handlers.py`, not
  ad-hoc JSON.
- **Response schemas are snapshot-pinned** (NEM-3748):
  `backend/tests/unit/api/schemas/test_response_schema_snapshots.py`
  (syrupy) fails on any unintended schema change. Intentional changes run
  `pytest --snapshot-update backend/tests/unit/api/schemas/test_response_schema_snapshots.py`
  and commit the snapshot diff under
  `backend/tests/unit/api/schemas/__snapshots__/` in the same PR.
- **Breaking API changes fail CI**: the API Compatibility workflow diffs
  the OpenAPI schema against main (`scripts/check-api-compatibility.sh`,
  oasdiff — removed endpoints, required parameters, response-shape
  changes). Plan removals as deprecations or expect the red.
- **API-key scopes are enforced per path+method** (`API_KEY_SCOPES` in
  `backend/core/constants.py` declares the monitoring scope's route table;
  guard `backend/tests/unit/api/test_api_key_scopes.py` pins every
  scope-pair, refuses wrong-method serving and checks query strings do
  not escape the scope).
- **Pagination is cursor-based; offset is deprecated but tolerated.**
  List endpoints page by opaque cursor (`pagination.py` — `encode_cursor`
  /`decode_cursor`, cursor-injection hardened, NEM-2602). A request
  passing BOTH `offset` and `cursor` is refused when the `offset` is
  nonzero (`validate_pagination_params`); a nonzero `offset` alone still serves
  but carries a deprecation warning header (`get_deprecation_warning`) —
  new endpoints take `cursor` only, and do not copy offset back in.

## The Middleware Stack (bottom-up as registered)

`SetupGuardMiddleware` (503 until first admin exists, NEM-5312) →
`ContentTypeValidationMiddleware` → `RequestIDMiddleware` →
`BaggageMiddleware` (OTel context, NEM-3796) → `ProfilingMiddleware` →
`ObservabilityMiddleware` → `RequestRecorderMiddleware` (records ≥500 errors, a sampled % of
successes, or any request carrying the `X-Debug-Record` header —
NEM-1646 replay debugging) → `CORSMiddleware` (explicit header allowlist,
no wildcard with credentials) → `SecurityHeadersMiddleware` →
`BodySizeLimitMiddleware` (10 MB) → `GZipMiddleware` (>1 KB, level 5) →
`IdempotencyMiddleware` (Idempotency-Key response cache, opt-in) →
`AuthMiddleware` (added last = outermost). Rate limiting is NOT in the
stack: it is a per-route dependency, `Depends(RateLimiter(tier=...))`
(`middleware/rate_limit.py`, Redis sliding window over sorted sets;
tiers DEFAULT/MEDIA/SEARCH/EXPORT/AI_INFERENCE).

## Traps

- **`get_vlm_analyzer_dep` returns the shipped `VlmAnalyzer` through the
  pipeline factory** — the name is wiring, not a claim about a class
  (B3.3 renamed the dep after R8 S2 retired the legacy class; the docstring
  keeps the history). Build analyzer through
  `backend/services/pipeline_factory.py`, never inline.
- **The api/helpers dead-twin is GONE (WP3.4).** Nothing imports
  `api.helpers.enrichment_transformers`; the absence ratchet
  (`backend/tests/unit/api/test_enrichment_transformers_retired.py`)
  fails if it comes back. Do not "restore" it.
- **Middleware modules are not the ones the old inventory listed** —
  `accept_header`, `content_negotiation`, `deprecation`,
  `deprecation_logger`, `error_handler`, `etag`, `exception_handler` and
  `file_validator` no longer exist (the deprecation pair was removed when
  zero deprecated endpoints remained, NEM-5558). Add middleware only
  through `main.py`'s stack, in its order.
- **WebSocket auth is its own middleware** (`websocket_auth.py`):
  cookie → query `?token=` → first-message fallback, constant-time
  comparison, rejection before handshake completion. Guard:
  `backend/tests/unit/api/middleware/test_websocket_auth.py`.
- **Path traversal is checked at the media routes** (`backend/api/routes/media.py`
  rejects traversal attempts before reading files) — new file-serving
  routes must repeat that check, not assume the middleware layer does it.
- Retired names sit under fall-only ratchet baselines
  (`.agents-md-validator.yml`); new prose mentions of the retired stack
  fail the AGENTS.md validator — the name list lives in
  `backend/AGENTS.md`.

## How to Test

```bash
uv run pytest backend/tests/unit/api/ -n auto --dist=worksteal --timeout=60
uv run pytest backend/tests/unit/api/middleware/ -n auto --dist=worksteal --timeout=60
./scripts/check-api-compatibility.sh          # OpenAPI diff vs main (what CI runs)
```

Unit tests mirror the layer: `backend/tests/unit/api/middleware/` (per
middleware), `backend/tests/unit/api/routes/` (per route module), and
`backend/tests/unit/api/schemas/` (schemas + snapshots). Pure-ASGI
middleware is tested without an app (`test_pure_asgi_middleware.py`).

## Related

| Path                                 | What it holds                                            |
| ------------------------------------ | -------------------------------------------------------- |
| `backend/AGENTS.md`                  | the lane root: lane-wide rules, the AI tier, how to test |
| `backend/api/routes/AGENTS.md`       | the route modules and their patterns                     |
| `backend/api/schemas/AGENTS.md`      | the Pydantic schemas and validation conventions          |
| `backend/services/AGENTS.md`         | what the dependencies hand to routes                     |
| `backend/core/AGENTS.md`             | the container/DB/Redis layer beneath the dependencies    |
| `scripts/check-api-compatibility.sh` | the breaking-change gate CI runs                         |
