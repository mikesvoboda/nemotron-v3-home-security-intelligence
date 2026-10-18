# backend/migrations — Recorded Schema Upgrades (B3.3)

## Purpose

`create_all` creates missing tables and never alters an existing one
(`backend/core/database.py`'s `init_db()`), so a database deployed last month keeps whatever
columns and types it was created with no matter what `backend/models/` says today. This package
is the other half: an ordered, **checked** upgrade path that records which upgrades a database
has had. `docs/uplevel/packages/backend.md` B3.3 box 5 and owner ruling 203 (record
`6198942052`) are the authority; ruling 254 (record on #6854, 2026-10-18) makes it the road the
retired model values leave `AIModel` by.

## Files

```
backend/migrations/
  registry.py   the ORDERED list (UPGRADES) + the SQL text handles: the statement lexer
                (`split_statements`), the text digest (`checksum_text`), drift handles
                (`missing_files`, `unlisted_files`). The upgrade TEXT lives in
                docs/api/migrations/*.sql; only the order lives here.
  checks.py     per-upgrade predicates answering "is this upgrade's effect ALREADY in this
                database?". Read them as catalog queries, not as SQL to run.
  runner.py     `plan()` / `apply_all()` / `upgrade_database()`. One transaction per upgrade
                covering check + action + record.
  errors.py     UpgradeError, UpgradeDriftError, UpgradeNotRegisteredError. Not AppException
                subclasses on purpose (error_handler.py maps those to HTTP; this has no HTTP).
  __main__.py   `python -m backend.migrations [--status|--dry-run|--apply]`
```

## Adding an upgrade (the only procedure that matters)

1. Write the SQL as `docs/api/migrations/YYYY-MM-DD-<what-it-changes>.sql`.
2. Add an `Upgrade(id, filename, source)` to `registry.UPGRADES`. **The id is permanent** — once
   a database records it, renaming it is `UpgradeDriftError`, not a renumber. Append; never
   reorder what shipped.
3. Add a predicate to `checks.CHECKS` when EITHER is true:
   - the file is **not safe to re-run** (changes a type, rewrites rows, drops something a running
     server reads) — then the check is the thing standing between a fresh boot and a rewrite; or
   - the file's effect is one `create_all` **already delivers** on a fresh database — then the
     check keeps a no-op from being _executed_ on every boot of every fresh install.

   "It changes nothing" is not "it costs nothing." An `IF NOT EXISTS` statement is safe to re-run
   but still takes a lock before it evaluates the `IF NOT EXISTS`: `ALTER TABLE` takes
   `ACCESS EXCLUSIVE` (blocks readers and writers), `CREATE INDEX` takes `SHARE` (blocks writers),
   and `ALTER COLUMN … TYPE` is the worst — `ACCESS EXCLUSIVE` _and_ a full rewrite. So a file
   whose effect `create_all` already built wants a check purely to skip that lock on a healthy
   boot, even though re-running it would be harmless.

   A file that is neither case is the only one where the runner's "assume not in place, run it"
   default is what you want: correct and self-healing for an idempotent file whose effect
   `create_all` cannot build. **0005 is the precedent for the second bullet**: twelve
   `ADD COLUMN IF NOT EXISTS` statements, safe to re-run, still given an
   `all_present(column_present(…))` check because a `create_all` database already has all twelve
   columns — proven by `test_upgrade_command_records_a_create_all_database_without_running_sql`,
   which asserts `verified` + zero statements for every upgrade on a fresh database. Do NOT strip
   that check because "the file is idempotent"; that reading of this list is what the second
   bullet exists to block.

4. `uv run python -m backend.migrations --dry-run` against a scratch database, then `--apply`
   twice: the second run must print `recorded, nothing to do` for every upgrade.

An `.sql` file in `docs/api/migrations/` that no `UPGRADES` entry names is reported by
`--status` as drift and is **never applied** — listing it is what makes it run.

## The two questions, which are not the same question

- _"Is this file idempotent?"_ is a property of the SQL text. It means re-running is harmless.
- _"Is the effect already in place?"_ is a property of **this database**. It means re-running is
  unnecessary — and for NEM-5051 that difference is the whole design: `ALTER COLUMN ... TYPE
jsonb` rewrites the column and takes `ACCESS EXCLUSIVE` on `alerts`/`alert_rules`, and a
  `create_all`-built database already has those columns as `jsonb`. Blind re-apply at startup
  would take that lock on every boot, and would fail outright the day a view depends on one of
  those columns. So the runner asks the second question, and when the answer is yes it records
  the upgrade with `executed = false` rather than running it.

## Contract rules

- **Never edit a shipped `.sql` file.** Its digest is recorded per database; an edit is
  `UpgradeDriftError` on every database that already applied it. Ship the correction as a NEW
  upgrade id.
- The record table `schema_migrations` is created here, not by a model. A model would mean it
  exists only on databases `create_all` built fresh — and the case this package exists for is a
  database `create_all` already built.
- Every statement runs as **driver SQL**, not `text()`: `text()` parses `:name` as a bind
  parameter even inside a string literal, so a file containing `'{"x":1}'` fails with "A value
  is required for bind parameter '1'". Upgrade files have no bind parameters by construction.
- `docs/` is dockerignored (`.dockerignore:70`), so `backend/Dockerfile` must
  `COPY docs/api/migrations` in every runtime stage or the startup upgrade silently no-ops.
  Both stages do (dev + prod), and `.dockerignore` carries `!docs/api/migrations/**` to re-include
  the directory through the `docs/` prune — verified empirically that the negation brings the
  directory _and its contents_ back and nothing else under `docs/`. `Upgrade.read_sql` fails loud
  naming that remedy if the COPY goes missing, and
  `backend/tests/unit/migrations/test_registry_lexing.py` pins the message.
- 0005's CHECK **derives its column list from the shipped file** (`checks._add_column_pairs`), so
  `import backend.migrations.checks` reads `docs/api/migrations/2026-10-18-*.sql` from disk. That
  moves the missing-file failure earlier: an image that lost its `COPY` now fails at package
  import — which is during `init_db()`, since the startup hook imports the runner — instead of when
  0005 runs. Same loud `UpgradeError` naming the COPY remedy, one step sooner, and "loud at boot" is
  the outcome this whole rule is about. New upgrades should follow the pattern: a hand-transcribed
  column list drifts silently, a derived one cannot.
- `init_db()` runs `apply_all` **inside the same advisory lock and transaction as `create_all`**,
  as savepoints (`nested=True`). That is what makes a restart upgrade a database, and it is why
  `plan`/`apply_all` take a `nested` flag: on an already-open transaction `conn.begin()` raises
  ("This connection has already initialized a SQLAlchemy Transaction()").
- `backend/scripts/init_schema.py` drops `schema_migrations` explicitly before rebuilding. It has
  to: the record table is deliberately outside `Base.metadata` (see the rule above), so
  `drop_all` cannot reach it, and a rebuild that left the history behind would tell the next boot
  that a database it just emptied had already been upgraded.

## Related

- `docs/api/migrations/README.md` — the directory's own index (prose guides + SQL).
- `backend/scripts/init_schema.py` — the destructive path (`drop_all` + `create_all`); never a
  substitute for an upgrade, and it refuses to run in production without `--force`.
- `backend/tests/integration/test_schema_upgrade_path.py` — box 6: a pre-upgrade schema **with
  rows**, upgraded, rows checked.
- `backend/tests/unit/migrations/test_registry_lexing.py` — the failure modes that no database can
  see: a lexer that splits inside a string literal, a checksum that normalizes a real edit away, a
  `checks.py` list that loses a column. It found the block-comment hang in `split_statements`,
  which the shipped files cannot trigger (they use only `--` comments).
