# API Migration Guides

This directory holds two kinds of file: prose migration guides for deprecated API endpoints, and
the SQL schema migrations applied at deployment time. They are named differently, so the index
below is what tells them apart.

## Naming Convention

Migration guides (markdown):

```
{resource}-v{old}-to-v{new}.md
```

Schema migrations (SQL) keep their own convention — a `YYYY-MM-DD-` date prefix followed by what
the migration changes:

```
2026-09-26-face-vector-provenance-model-id.sql
```

## Creating a New Migration Guide

Use the template in `../DEPRECATION_POLICY.md` under "Migration Guide Template".

## Index

### Migration guides

| Migration Guide          | Status | Removal Date |
| ------------------------ | ------ | ------------ |
| _No active deprecations_ | -      | -            |

As endpoints are deprecated, add their migration guides here.

### Schema migrations

| File                                               | What it changes                                           |
| -------------------------------------------------- | --------------------------------------------------------- |
| `2026-09-26-face-vector-provenance-model-id.sql`   | Adds `model_id` provenance to face embedding vectors      |
| `2026-09-26-person-vector-provenance-model-id.sql` | Adds `model_id` provenance to person embedding vectors    |
| `2026-09-30-retire-demographics-reid-tables.sql`   | Drops the demographics and re-ID tables                   |
| `NEM-5051-convert-alert-json-to-jsonb.sql`         | Converts `alerts` / `alert_rules` JSON columns to `jsonb` |

The `model_id` columns are what make the provenance rule enforceable: a row that never named
its weights defaults to the `legacy-unknown-provenance` sentinel, and the specialists answer
`unavailable (re-enroll)` for those rows instead of scoring them. See
[Face Recognition](../../guides/face-recognition.md).
