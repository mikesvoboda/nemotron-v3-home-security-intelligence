# Backend Core - Agent Guide

## Purpose

`backend/core/` is the server's foundation layer: configuration, database and
Redis wiring, the DI container, logging/telemetry, security utilities and the
async helpers everything else builds on. It owns cross-cutting contracts —
where settings come from, how a session is obtained, how services are
registered — that every layer above depends on. Module-level code (a leaf
helper, an exception type) lives here; anything that talks to a camera, a
model or a pipeline lives in `backend/services/`.

## Entry Points

| File              | Role                                                                                                                                                                               |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `config.py`       | `Settings` (Pydantic) + `get_settings()` (module `@cache`d — one instance per process); `HSI_RUNTIME_ENV_PATH` (default `./data/runtime.env`) layers runtime overrides over `.env` |
| `database.py`     | Engine/session factory; `init_db()` (lifespan); `get_session()` context manager; migration runner call                                                                             |
| `redis.py`        | `RedisClient` (pools, TLS, Zstd compression with the `Z:` prefix, queues, HyperLogLog); `init_redis()` double-check-lock startup; Sentinel variants                                |
| `container.py`    | `Container` + `wire_services()` — the single registration site for the server's services                                                                                           |
| `dependencies.py` | FastAPI `get_*` dependencies over the container (`get_redis_dependency`, `get_vlm_analyzer_dependency`, …)                                                                         |
| `exceptions.py`   | The shared exception hierarchy rooted at `SecurityIntelligenceError`                                                                                                               |

## The Rules (do not regress)

- **Settings changes hit two ratchets.** Every `Settings` field must be read
  outside `config.py` or stay on the
  `ALLOWED_UNREAD_OUTSIDE_CONFIG` allowlist with a reason
  (`backend/tests/unit/core/test_settings_orphan_ratchet.py`, scanner
  `scripts/audit/settings_orphans.py` — the allowlist currently holds the four
  fields only the validator can see, e.g. `llama_slot_count`, which
  `_derive_slot_context_window` consumes via `info.data.get`). And every
  `.env.example` variable must be read by `config.py`, compose or `setup.py`
  (`backend/tests/unit/core/test_env_example_ratchet.py`, scanner
  `scripts/audit/env_dead_vars.py`). An orphaned field or dead env var fails
  the unit run naming it. The two derivation traps: a context-window field is
  declared as the TOTAL pool and a `mode="before"` validator divides it —
  `nemotron_context_window` (alias `CTX_SIZE`) by `llama_slot_count` (alias
  `PARALLEL`), `vlm_context_window` (alias `VLM_CTX_SIZE`) by
  `vlm_slot_count` (alias `VLM_PARALLEL`). Declaring the per-slot figure
  gets it divided twice.
- **Schema changes ship with a recorded upgrade.** `create_all` creates missing
  tables and never alters an existing one (`backend/core/database.py` comments this
  inline, citing ruling 203). Column and type changes ride the ordered
  upgrades in `backend/migrations/` (14 entries, `0001`…`0014-arming-core`):
  the ORDER lives in `backend/migrations/registry.py`'s `UPGRADES`, the SQL TEXT lives
  in `docs/api/migrations/*.sql` — `MIGRATION_DIR` points there, so the
  backend container `COPY`s that one docs directory even though `docs/` is
  otherwise dockerignored (`backend/Dockerfile` comments it: without the COPY
  the container boots a database owing an upgrade and fails loudly with
  `UpgradeError`). `init_db()` runs `apply_all(..., nested=True)` inside the
  same advisory lock and transaction as `create_all`, so a failing upgrade
  rolls back to before itself and the next boot retries from a clean shape.
  Guards: `backend/tests/unit/migrations/` (incl.
  `test_record_consistency.py` — a recorded upgrade missing from the registry
  is drift) and `backend/tests/integration/test_alembic_migrations.py`.
- **The DI registry name for the analyzer is `vlm_analyzer`**, and the
  dependency function name mirrors the container key (`backend/core/dependencies.py`
  comments it — load-bearing wiring). Renaming either string is its own
  slice; guard
  `backend/tests/unit/test_r8_s2b_nemotron_deletion.py::TestDiNameIsDeliberate`.
  `wire_services()` registers exactly nine services (two of them async
  singletons): `health_service_registry`, `health_event_emitter`,
  `redis_client`, `context_enricher`, `vlm_analyzer`, `detector_client`,
  `face_detector_service`, `plate_detector_service`, `ocr_service`
  (face-detector singleton behaviour is pinned by
  `backend/tests/unit/core/test_container_ai_services.py`).
- **`get_settings()` is `@cache`d.** Tests that mutate environment state must
  call `get_settings.cache_clear()` (the convention throughout
  `backend/tests/unit/core/test_config.py`) or the next construction reads
  the stale process cache. The `Settings` instance redacts itself in
  `repr`/`str`.
- **The Docker/Podman client never raises for container operations.**
  `backend/core/docker_client.py` catches `DockerException`/`APIError` per call and
  returns the sentinel (`False` from `test_connection`, `[]` from
  `list_containers`) with a warning log — `backend/services/health_monitor_orchestrator.py`
  is built on that contract. Only misuse (client closed before use) raises.
  Guard: `backend/tests/unit/core/test_docker_client.py`.
- **Secrets at rest are Fernet ciphertext.** `backend/core/secret_box.py` encrypts
  webhook signing secrets under `SECRETS_MASTER_KEY` (SHA-256 → 32-byte
  Fernet key); the plaintext is shown once at channel creation. An unset key
  or a non-decrypting ciphertext raises `SecretBoxUnavailableError` with the
  operator instruction. Guard: `backend/tests/unit/core/test_secret_box.py`.
- **PIPELINE_MODE accepts one value.** The legacy spelling raises at
  `Settings` construction (validator mode="before") —
  `backend/tests/unit/core/test_config_pipeline_mode_hard_raise.py` pins the
  raise, including the env-var spelling.

## Traps

- **Two env files, not one.** `_env_file=(".env", $HSI_RUNTIME_ENV_PATH)` —
  the runtime file is read at call time (deliberately, so tests can override
  it) and LATER values win. A variable set only in `runtime.env` is invisible
  to anything that greps `.env` alone.
- **`init_db` advisory-lock race is deliberate.** A worker that loses
  `pg_try_advisory_lock` starts serving without waiting for the winner; the
  runner is idempotent and re-runs every boot. Making losers wait would wedge
  the fleet behind a wedged winner (`backend/core/database.py` comment).
- **Lifespan degradation is by design**: if Redis init fails the whole
  Redis block is caught and the server keeps serving without queues and
  workers ("Continuing without Redis"); DB init is NOT in that try-block —
  a database failure aborts startup.
- **Retired services are gone, not commented out.** `get_enrichment_pipeline_dependency`
  and `get_yolo_world_service_dependency` do not exist; the prompt-enhancement
  role lives in `backend/services/context_enricher.py` (`ContextEnricher`), registered
  as `context_enricher` in the container (R8 S3).
- **Retired names sit under fall-only ratchet baselines**
  (`.agents-md-validator.yml` `retired_name_baseline`); new mentions fail
  the validator — the name list and the `\w` edge
  (`ENRICHMENT_LIGHT_URL` does not count, underscore is a word character;
  `enrichment-light` does, a hyphen is not) live in
  `backend/AGENTS.md`.
- **Free-threading is a 3.14t requirement, not a default.**
  `backend/core/free_threading.py` verifies `--disable-gil` builds; `executors.get_cpu_executor()`
  falls back to `ThreadPoolExecutor` when `InterpreterPoolExecutor` is absent
  (guard `backend/tests/unit/core/test_executors.py`).
- **SSRF validation is for outbound URLs** (`backend/core/url_validation.py` blocks
  private/link-local/suffix targets for webhook + monitoring URLs) — do not
  confuse it with `backend/core/sanitization.py`, which sanitizes error strings,
  container names, camera ids and metric labels.
- **Circuit breakers live in `backend/services/circuit_breaker.py`**, not core (the
  AI-provider resilience pattern moved there; `backend/core/websocket_circuit_breaker.py`
  is the WebSocket-connection-specific one).

## How to Test

```bash
uv run pytest backend/tests/unit/core/ -n auto --dist=worksteal --timeout=60
uv run pytest backend/tests/unit/migrations/ -n auto --dist=worksteal --timeout=60
uv run pytest backend/tests/integration/test_database.py --timeout=30   # real Postgres
```

Structure mirrors source: per-module `test_<module>.py` files in
`backend/tests/unit/core/`; the migrations suite is its own directory;
integration coverage in `backend/tests/integration/`. Singletons follow the
lane-wide reset convention (see `backend/services/AGENTS.md` for the list);
`reset_container()` clears registrations and overrides.

## Key Modules (one line each)

| Module                 | What it owns                                                                                                                                                    |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `async_context.py`     | ContextVars for connection/task/job ids across async boundaries                                                                                                 |
| `async_utils.py`       | `async_sleep`, `async_open_image`, `async_subprocess_run`, `bounded_gather`, `AsyncTaskGroup`                                                                   |
| `config_validation.py` | Startup validation + summary table (NEM-2026)                                                                                                                   |
| `constants.py`         | Queue/DLQ names, `API_KEY_SCOPES` (monitoring), cache-invalidation reasons                                                                                      |
| `logging.py`           | Structured logging, trace-context formatter, URL/value redaction                                                                                                |
| `metrics.py`           | `MetricsService`, pipeline stage/latency stats                                                                                                                  |
| `mime_types.py`        | Media extension↔MIME mapping (use this, not ad-hoc checks)                                                                                                      |
| `orm_utils.py`         | `created_at_column`/`updated_at_column`/`version_column` factories, lazy mode                                                                                   |
| `profiling.py`         | `ProfilingManager` + `profile_if_enabled` decorator                                                                                                             |
| `security.py`          | Path validation for models (`validate_model_path`, `is_safe_path_for_deletion`), checksums, ONNX source checks                                                  |
| `sanitization.py`      | Error-string/container-name/camera-id sanitization, URL validation for Grafana                                                                                  |
| `sampling.py`          | Priority-based OTel trace sampling (NEM-3793): errors/high-risk always sampled                                                                                  |
| `telemetry.py`         | `setup_telemetry`/`shutdown_telemetry`, tracer/span helpers                                                                                                     |
| `otel_metrics.py`      | OTel metrics for the circuit breakers                                                                                                                           |
| `tls.py`               | `TLSConfig`, `TLSMode`, certificate discovery                                                                                                                   |
| `url_validation.py`    | SSRF-blocked hosts/IP ranges for outbound URLs                                                                                                                  |
| `vector_provenance.py` | The one-embedding-space provenance vocabulary (F11): `role@weights@sha` ids; `LEGACY_MODEL_ID` sentinel is UNTRUSTED BY DEFAULT — never participates in a score |
| `face_provenance.py`   | Re-exports the face-path constant from `vector_provenance` (ONE sentinel for every vector store)                                                                |
| `websocket/`           | Event-type registry, payload schemas, subscription manager, compression, message buffer, sequence tracker                                                       |

## Related

| Path                                | What it holds                                            |
| ----------------------------------- | -------------------------------------------------------- |
| `backend/AGENTS.md`                 | the lane root: lane-wide rules, the AI tier, how to test |
| `backend/services/AGENTS.md`        | the services that consume this layer, incl. the analyzer |
| `backend/models/AGENTS.md`          | the SQLAlchemy models `orm_utils` columns feed           |
| `backend/ai_contract/AGENTS.md`     | the generated AI-tier operation registry                 |
| `docs/api/migrations/README.md`     | how upgrades are recorded and applied                    |
| `scripts/audit/settings_orphans.py` | the orphan-field census the ratchet test runs            |

The DI-name guard
(`backend/tests/unit/test_r8_s2b_nemotron_deletion.py::TestDiNameIsDeliberate`)
lives in `backend/tests/unit/`, beside the deletion tests it belongs with —
not under `backend/tests/unit/core/`.
