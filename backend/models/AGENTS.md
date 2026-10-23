# Backend Models - Agent Guide

## Purpose

`backend/models/` is the SQLAlchemy 2.0 ORM layer: one class per table, all
sharing the `Base` that `backend/models/camera.py` declares and every other module
imports from there (`from .camera import Base`). `init_db()` runs
`create_all` on exactly that class's metadata (`backend/core/database.py`
imports `camera.Base as ModelsBase`), so a model defined on a different
Base is invisible to table creation. This directory holds schema and
relationship rules only — query behaviour lives in
`backend/repositories/` and the services above it.

## Entry Points

| File        | Role                                                                                                                         |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `camera.py` | `Camera` + THE `Base` (all other modules import it from here) — `init_db` creates tables from its metadata                   |
| `event.py`  | `Event` — the central record: detections, verification, notify decision, soft delete, optimistic locking, full-text search   |
| `alert.py`  | `Alert` + delivery FKs (`alert_delivery.py`); `ondelete="SET NULL"` for the rule link                                        |
| `arming.py` | The B4.7 arming-core tables (`ArmingState`, `ArmingModeExclusion`, `ArmingScheduleEntry`, `ArmingChange`) — migration `0014` |
| `enums.py`  | Shared enum types (guard: `backend/tests/unit/models/test_enums.py`)                                                         |

## The Rules (do not regress)

- **Provenance is required on every embedding write (F11).** `set_embedding`
  raises `ValueError` without the model id — there is no default to inherit
  ("the belt flows from the PRODUCER, never from a module default",
  `backend/models/entity.py`). Vector columns carry `model_id` (`role@weights@sha`
  grammar from `backend/core/vector_provenance.py`); the
  `LEGACY_MODEL_ID` sentinel means untrusted-by-default and never joins a
  score. A vector without provenance is a schema bug, not a missing field.
- **Every new model: `version_id` + `__mapper_args__ = {"version_id_col":
...}`.** Optimistic locking is the concurrency model (NEM-3408 pattern in
  `event.py` and `alert.py`); a writable table without a version column
  loses conflict detection.
- **DB-level FK cascades, ORM mirror.** Relationships declare both:
  `ondelete="CASCADE"` on the ForeignKey AND `cascade="all, delete-orphan"`
  with `passive_deletes=True` on the relationship — "so a session.delete()
  never leaves an orphan" (`event.py` comments it). The AlertRule → Alert
  link is the deliberate exception: `ondelete="SET NULL"`.
- **CHECK constraints for enum-like columns.** `risk_level IN
('low','medium','high','critical')`, `risk_score 0..100`,
  `ended_at >= started_at` are named `ck_*` constraints (guard:
  `backend/tests/unit/models/test_check_constraints.py` asserts the
  expression, not just presence). Add the constraint with the column.
- **Soft delete = `deleted_at IS NULL`, partial-indexed.** `Camera` and
  `Event` carry `deleted_at` plus a partial index on the active set
  (`postgresql_where="deleted_at IS NULL"`); `is_deleted` is a property,
  not a column. Guard: `backend/tests/unit/models/test_soft_delete.py`.
- **IDs are UUIDv7 strings** (`default=lambda: str(uuid7())` from
  `backend/models/alert.py` et al.) — time-ordered so B-tree inserts stay
  local (property-tested in `backend/tests/unit/models/test_uuid7.py`).
- **Schema changes ship with a recorded upgrade.** `create_all` never
  alters an existing table; column/type changes ride `backend/migrations/`
  (see `backend/core/AGENTS.md` for the registry/runner mechanics).

## Patterns

- **Relationships: `TYPE_CHECKING` import, typed `Mapped[...]`, named
  string target, `back_populates` both sides.** Lazy mode goes through
  `get_relationship_lazy_mode()` (`backend/core/orm_utils.py`): production
  `select`, development/test `raise_on_sql` — a lazy load that fires in a
  dev/test session raises instead of hiding an N+1. Read-eager pairs
  (`detections`, `verifications`) declare `lazy="selectin"` explicitly so
  the API can read them with every event.
- **One-to-one children are UNIQUE FKs, not uselist=False.**
  `EventNotifyDecision` (ISS-001) is one row per decided event or none —
  absence means "no decision was made", never False; `UNIQUE(event_id)`
  backs the rule at the database level.
- **JSONB for structured payloads** (`entities`, `flags`,
  `confidence_factors` on `Event`) with GIN indexes; full-text search rides
  the `search_vector` TSVECTOR + GIN index, populated by the Postgres
  trigger the recorded migration adds (services build
  `to_tsvector` expressions against it — `backend/services/search.py`).
- **Time-series indexes**: B-tree for lookup columns, BRIN for append-only
  chronology (`ix_events_started_at_brin` — ~1000x smaller than B-tree on
  ordered timestamps).
- **Legacy-event semantics live in absence, not flags**: an `Event` with no
  `EventVerification` row is a legacy event (the REST/WS `verification`
  field branches on row presence); the same doctrine for
  `notify_decision`.

## Traps

- **Importing `Base` from `backend.core.database` gives you a DIFFERENT,
  unused `DeclarativeBase`** — the one `create_all` runs is
  `backend.models.camera.Base`. Defining a model on the wrong Base
  silently never creates its table.
- **`passive_deletes=True` means the DB does the deleting** — an ORM-level
  cascade without the matching DB-level `ondelete` will raise on bulk
  deletes, and a DB-level cascade without the ORM mirror orphans rows on
  `session.delete()`. Ship both halves.
- **`EventVerification` is async-expunged once its session closes** — the
  WS payload that carries it is built INSIDE session 2 and published after
  (`vlm_analyzer.py` session doctrine). Reading the relationship after the
  session raises `DetachedInstanceError`.
- **The retired R8 S4 child-table classes are gone** (demographic and
  REID attributes); a source-scan test
  (`backend/tests/unit/models/test_r8_s4_demographics_reid_retirement.py`)
  reads live forms — re-introducing the class by hand fails it.
- **`postgres_where` indexes live in `__table_args__` of the model AND in
  the recorded SQL** — drift between the two is caught only by the
  migrations tests; when adding an index, add both halves in the same PR.

## How to Test

```bash
uv run pytest backend/tests/unit/models/ -n auto --dist=worksteal --timeout=60
uv run pytest backend/tests/unit/models/test_check_constraints.py --timeout=60
uv run pytest backend/tests/unit/models/test_models_hypothesis.py --timeout=60
```

53 test files, one per module plus cross-cutting suites: the
Hypothesis-based property tests (`test_models_hypothesis.py`), the CHECK
constraint expressions, and the retirement scans. Real-database behaviour
( cascades, partial indexes, triggers) is covered by
`backend/tests/integration/test_database.py`.

## Related

| Path                                            | What it holds                                              |
| ----------------------------------------------- | ---------------------------------------------------------- |
| `backend/AGENTS.md`                             | the lane root: lane-wide rules, the AI tier, how to test   |
| `backend/core/AGENTS.md`                        | the migration runner, `create_all` semantics, `orm_utils`  |
| `backend/services/AGENTS.md`                    | the services that write these tables                       |
| `backend/repositories/`                         | the query layer over these models (no AGENTS.md by design) |
| `docs/api/migrations/README.md`                 | how upgrades are recorded and applied                      |
| `backend/tests/unit/models/test_soft_delete.py` | the soft-delete pin                                        |
