# Backend API Schemas - Agent Guide

## Purpose

`backend/api/schemas/` holds the Pydantic request/response models — 73
modules, re-exported through `__init__.py`, consumed by the route modules
and rendered into the OpenAPI document FastAPI serves. Schemas are the
API's contract surface: what a client may send, what it will see back,
and what the snapshot + compatibility gates pin.

## Entry Points

| File                                                   | Role                                                                                      |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| `__init__.py`                                          | The public exports (import schemas from here or their module)                             |
| `problem_details.py`                                   | `ProblemDetail`, the RFC 7807 error body + `get_status_phrase`                            |
| `camera.py`, `events.py`, `detections.py`, `alerts.py` | the highest-traffic resources (response models carry `version_id`, computed `risk_level`) |
| `websocket.py`                                         | WS message types: `Literal["type"]` discriminators, the NEM-3394 unions                   |
| `queue.py`                                             | Queue payload schemas + their strict-mode variants                                        |
| `hateoas.py`                                           | `build_camera_links` / `build_event_links` / … — the shared `_links` builders             |

## The Rules (do not regress)

- **Response schemas are snapshot-pinned (NEM-3748).**
  `backend/tests/unit/api/schemas/test_response_schema_snapshots.py`
  (syrupy) compares each response model's JSON schema against the
  committed snapshot under `backend/tests/unit/api/schemas/__snapshots__/`.
  Intentional changes: run
  `pytest --snapshot-update backend/tests/unit/api/schemas/test_response_schema_snapshots.py`
  and commit the diff in the same PR. Anything unintended reds here first.
- **Derived fields are `computed_field`, never stored twice (NEM-3398).**
  `risk_level` derives from `risk_score` via `SeverityService` bands
  (cached_property) — a schema that declares a writable `risk_level`
  reintroduces the inconsistency the pattern removed.
- **List/detail serialization modes (NEM-3432).** Large response models
  expose `model_dump_list()` (trims heavy fields for list views) and
  `model_dump_detail()` — the pattern for payload-heavy resources; today
  the methods exist on `EventResponse`/`DetectionResponse` and are
  pinned by `test_serialization_modes.py`, but no route calls them yet.
  A new heavy field should join both modes, or lists balloon.
- **Backend↔frontend type safety is pinned (NEM-4843)**:
  `backend/tests/unit/api/schemas/test_type_safety.py` asserts
  `AlertResponse.version_id` (optimistic locking), the documented deferred
  fields on `EventResponse`, and typed `enrichment_data` on
  `DetectionResponse` — a field removal breaks the frontend contract.
- **Field constraints are tested**: bounded strings/numbers carry
  `Field(...)` constraints, and
  `backend/tests/unit/api/schemas/test_field_constraints.py` exercises
  them — a `max_length` added silently is drift.
- **Strict queue schemas exist for a reason**: `queue.py`'s strict
  variants skip type coercion for trusted internal payloads (15–25%
  faster validation, per the module's own docstring). They must keep
  inheriting the base security validators — the strict test pins that.

## Patterns

- `model_config = ConfigDict(from_attributes=True, ...)` on ORM-backed
  responses; `populate_by_name=True` where aliases exist.
- **Discriminated unions over plain `Union`** (NEM-3394): WebSocket
  messages declare `type: Literal["..."]` on every variant and route by
  discriminator — O(1) validation, better error messages.
- **HATEOAS links come from `hateoas.py`'s builders**, not inline dicts —
  one place to change a link shape.
- Enums are `StrEnum` subclasses declared next to their schemas
  (`RiskLevel`, `WebSocketMessageType`, …); the same names re-declared in
  `backend/models/enums.py` are the DB-side truth — keep both honest.

## Traps

- **The per-file schema inventory is gone on purpose** (W1.3 banner →
  W3.2): the old file's per-module schema tables drifted; the models and
  `app.openapi()` are the source of truth now.
- **Snapshot updates are part of the change, not a follow-up**: a schema
  PR whose snapshot diff lands in a later PR breaks the compatibility
  gate in between.
- The snapshot file is `.ambr` (`__snapshots__/test_response_schema_snapshots.ambr`)
  — one file, diffed like any code artifact.
- `llm_response.py`'s `RiskLevel` is re-exported as `LLMRiskLevel` in
  `__init__.py` for the LLM-facing imports; the canonical risk vocabulary
  lives in `backend/services/vlm_verdict.py`
  (the `risk_level`-is-NOT-a-field rule there applies to its payloads).
- Retired names sit under fall-only ratchet baselines
  (`.agents-md-validator.yml`); new prose mentions of the retired stack
  fail the AGENTS.md validator — the name list lives in
  `backend/AGENTS.md`.

## How to Test

```bash
uv run pytest backend/tests/unit/api/schemas/ -n auto --dist=worksteal --timeout=60
uv run pytest backend/tests/unit/api/schemas/test_response_schema_snapshots.py --timeout=60
```

43 test files cover the modules and the cross-cutting contracts (type
safety, field constraints, serialization modes, computed fields, strict
queue schemas, pagination, HATEOAS, problem details).

## Related

| Path                              | What it holds                                                            |
| --------------------------------- | ------------------------------------------------------------------------ |
| `backend/api/AGENTS.md`           | the API layer: middleware stack, error contract, how the schemas serve   |
| `backend/api/routes/AGENTS.md`    | the routes that declare these schemas                                    |
| `backend/services/vlm_verdict.py` | the canonical `vlm_assess` verdict schema (pydantic-only import closure) |
| `backend/models/enums.py`         | the DB-side enums that mirror the schema enums                           |
| `backend/AGENTS.md`               | the lane root: lane-wide rules, the AI tier, how to test                 |
