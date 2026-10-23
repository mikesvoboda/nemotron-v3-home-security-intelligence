# Backend Lane - Agent Guide

## Purpose

The backend is the FastAPI server of the home-security system: it receives camera
media, runs the detection/analysis pipeline against the AI containers, stores the
results in PostgreSQL, serves them over REST + WebSocket, and raises alerts. The
lane's boundary directories carry their own `AGENTS.md` files (see _Related_);
this file is the map and the cross-package rules only.

## Entry Points

| File                           | Role                                                                                                  |
| ------------------------------ | ----------------------------------------------------------------------------------------------------- |
| `main.py`                      | The application: lifespan startup/shutdown, middleware stack, `include_router` for every route module |
| `core/config.py`               | `Settings` (Pydantic BaseSettings) — every env var is declared here, read by `.env.example`'s ratchet |
| `core/container.py`            | `wire_services()` — the DI registrations the whole server runs on                                     |
| `services/pipeline_factory.py` | The ONE construction point for the per-event analyzer                                                 |
| `ai_contract/`                 | The generated operation registry the AI tier must satisfy                                             |

## The Rules (do not regress)

- **One analyzer construction point.** Every production path that needs the
  per-event analyzer asks `services/pipeline_factory.build_pipeline_analyzer()` —
  the analysis-queue worker, the API dependency, the DI container, the batch
  aggregator's fast path. Before the seam existed each site spelled the analyzer
  by hand and flipping the mode meant finding every site; the source-scan pin is
  `backend/tests/unit/services/test_pipeline_factory.py`. `PIPELINE_MODE` accepts
  one value and raises on the retired spelling (R8 removed the legacy branch).
- **The DI registry name is `vlm_analyzer`.** `core/container.wire_services()`
  registers the analyzer under that string; the startup gate and
  `core/dependencies.py` resolve by it. Renaming a load-bearing wiring string is
  its own slice — the guard is
  `backend/tests/unit/test_r8_s2b_nemotron_deletion.py::TestDiNameIsDeliberate`.
- **`AuthMiddleware` is the EXPOSE_LAN gate and is added LAST**, so it runs
  before every other middleware — nothing, not even an idempotent replay,
  answers an unchecked request (`main.py` comments it; guard
  `backend/tests/unit/api/middleware/test_auth.py`). With `EXPOSE_LAN` unset it
  passes everything; the shipped default binds the published ports to 127.0.0.1
  and that binding is the boundary (test
  `backend/tests/unit/core/test_frontend_expose_lan_bind.py`).
- **Webhook dependencies validate fail-closed.** The inbound-webhook key check
  does NOT honour `api_key_enabled` — with no keys configured every request is
  refused. The two older copies in `backend/api/routes/dlq.py` and
  `backend/api/routes/system.py` DO return early when the flag is off; giving
  the webhook dependency the same branch is the hole D3 records.
- **Schema changes ship with a recorded upgrade.** `core/database.py`'s
  `create_all` creates missing tables and never alters an existing one; column
  and type changes ride the ordered upgrades in `backend/migrations/` (SQL text
  in `docs/api/migrations/*.sql`, order in `migrations/registry.py`, runner runs
  inside `init_db`'s advisory lock under savepoints). Tests:
  `backend/tests/unit/migrations/` and
  `backend/tests/integration/test_alembic_migrations.py`.
- **Every `Settings` field is read outside `config.py` or allowlisted with a
  reason** (B3.3 ratchet,
  `backend/tests/unit/core/test_settings_orphan_ratchet.py`), and every
  `.env.example` variable is read by `config.py`, compose or `setup.py` (O3.3
  ratchet, `backend/tests/unit/core/test_env_example_ratchet.py`). Declaring a
  setting nobody reads fails the unit run naming the field.

## The AI Tier Is Two Containers

- **ai-gateway** (`AI_GATEWAY_URL`, default `http://ai-gateway:8090`) serves
  ONLY `/yolo26` (detection) and `/enrich-lt` (the kept threat + re-ID
  specialists). The heavier routers were pruned (R8 S3): `florence_url`,
  `clip_url` and `enrichment_url` are DELETED from `Settings`, and their compose
  routers are unbootable.
- **ai-vlm** (`AI_VLM_URL`, default `http://ai-vlm:8098`) is the shipped LLM
  engine — llama.cpp serving `vlm_assess`; it owns the analysis stage.
- In gateway mode (`USE_AI_GATEWAY=true`) clients build `{ai_gateway_url}/
{router}` themselves; `enrichment_light_url` is the fallback direct route.
- The llama.cpp context budget is DERIVED, not declared:
  `nemotron_context_window` (validation alias `CTX_SIZE`) is the total pool and
  `_derive_slot_context_window` divides it by `llama_slot_count` (alias
  `PARALLEL`) — a per-request budget is the per-slot figure. Declare the
  per-slot number and the default gets divided twice.

## Patterns

- **Dependency injection.** Routes take `Annotated` aliases from
  `backend/api/dependencies.py` (`DbSession`, `RedisDep`, `CacheDep`, …);
  services outside the request cycle use `backend.core` context managers
  (`get_session()`, `init_redis()`) or the container. Legacy
  `Depends(get_db)` still works but is not the pattern to copy.
- **Singleton reset for tests.** Most services expose `reset_*()` functions;
  the Model Zoo additionally needs `reset_model_zoo()` + `reset_model_manager()`
  before a test builds one. The list is in `backend/services/AGENTS.md`.
- **Coverage gate.** Unit tier: 85% PR-diff baseline via `pyproject.toml`
  `fail_under`; the executed absolute floor is `scripts/validate.sh
--fail-under=80` over unit + integration combined (owner ruling A7.1).

## How to Test

```bash
uv run pytest backend/tests/unit/ -n auto --dist=worksteal --timeout=60
uv run pytest backend/tests/integration/ --timeout=30
./scripts/validate.sh                               # pre-PR validation (both tiers + coverage)
```

Unit tests run under `pytest-xdist` (`-n auto --dist=worksteal`) in CI — a test
that touches a wall clock, a shared singleton, or an order-dependent module must
script its inputs; the webhook response-time test pinned a live
`datetime.now()` pair and flaked under xdist load until #7384 scripted its clock.
Structure mirrors source: `backend/tests/unit/{api,core,models,services}`,
integration in `backend/tests/integration/` (sharded), contracts in
`backend/tests/contracts/`, goldens in `backend/tests/golden/`.

## Traps

- `pytest-randomly` draws a fresh shuffle seed per process; the four CI unit
  shards each shuffled before `pytest-split` sliced, so slices overlapped and
  the merged run undercounts coverage (mechanism + pin in
  `docs/developer/testing.md`, `scripts/test_coverage_denominator.py`).
- `core/dependencies.py` has no `get_enrichment_pipeline_dependency` or
  `get_yolo_world_service_dependency` — those services are gone (R8). The DI
  container's `wire_services()` registers exactly: `health_service_registry`,
  `health_event_emitter`, `redis_client`, `context_enricher`, `vlm_analyzer`,
  `detector_client`, `face_detector_service`, `plate_detector_service`,
  `ocr_service`.
- A worker that loses the `init_db` advisory lock starts serving without
  waiting for the winner; the window is a boot-order race, not a missed
  upgrade — the runner is idempotent and re-runs on every boot. Making losers
  wait would wedge every worker behind a wedged winner (deliberate, commented
  in `core/database.py`).
- `admin_api_key` is declared + redacted but NOT enforced — no code path reads
  it. Admin endpoints gate on `admin_enabled` alone; the network boundary is
  the real protection. `debug` is not consulted for admin.
- The retired names (the five keys of `.agents-md-validator.yml`'s
  `retired_name_baseline` — the W3.1-retired stack) sit under fall-only
  ratchet baselines; new mentions fail the AGENTS.md validator.
  Whole-word case-insensitive: `ENRICHMENT_LIGHT_URL`
  does NOT count (underscore is a `\w` edge) but `enrichment-light` DOES
  (hyphen is not).

## Related

| Path                            | What it holds                                                    |
| ------------------------------- | ---------------------------------------------------------------- |
| `backend/ai_contract/AGENTS.md` | the generated AI-tier operation registry + deterministic fake    |
| `backend/api/AGENTS.md`         | the API layer: middleware, routes, schemas, error contract       |
| `backend/core/AGENTS.md`        | config, database, redis, logging, resilience, DI container       |
| `backend/models/AGENTS.md`      | the SQLAlchemy models and their cascade/relationship rules       |
| `backend/services/AGENTS.md`    | the pipeline services, the VLM path, workers, testing reset list |
| `docs/developer/testing.md`     | the coverage gates, shard mechanics, test commands               |
| `docs/api/migrations/README.md` | how upgrades are recorded and applied                            |
| `/AGENTS.md`                    | project-wide instructions                                        |

Directories without an `AGENTS.md` on purpose: `backend/repositories/`,
`backend/evaluation/`, `backend/jobs/`, `backend/scripts/`,
`backend/data/` (runtime), `backend/tests/` (tests index themselves).
