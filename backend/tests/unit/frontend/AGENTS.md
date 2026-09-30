# Unit Tests - Frontend Source Guards

## Purpose

Python tests that read `frontend/src` as TEXT and pin facts about it. They do
not import or execute any TypeScript; they assert file presence/absence, import
specifiers, JSX element usage and `data-testid` attributes, so a retirement can
be guarded without a JS runtime in the backend tier. The sibling R8 guards in
`backend/tests/unit/` use the same idiom against Python source.

## Directory Structure

```
backend/tests/unit/frontend/
├── AGENTS.md                                  # This file
├── __init__.py                                # Package marker, as in every sibling test dir
└── test_r8_s5_frontend_panel_retirement.py    # S5: five enrichment panels deleted, tombstone too
```

## Why pins, not greps

Every "X is gone" check reads source text for LIVE forms only — import
specifiers, JSX elements, `data-testid` attributes — with comments stripped, so
a docblock that names a retired component cannot fail the file. Prose is
allowed to name the dead. Every scan carries its own non-vacuity witness (the
tree-wide import-resolution pin asserts it resolved >2000 specifiers, not zero).

## Running

```bash
uv run pytest backend/tests/unit/frontend/ -v --no-cov
```

These are fast (<10s) and CPU-only; nothing here is `-m gpu` or integration.

## Related Documentation

- `frontend/src/components/events/AGENTS.md` - the retired panels' tombstone
- `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md` - the R8 ledger records this slice
