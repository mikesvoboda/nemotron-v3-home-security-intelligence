# AI Provider Contract Tests - Agent Guide

## Purpose

The conformance tier for the AI-tier contract (`backend/ai_contract/`): the registry, the provider interface, the deterministic FakeProvider, the golden wire snapshots, and the real backend clients - so provider and consumer can no longer stay independently green. Plan P WP7.1-WP8.5 (plan: `docs/superpowers/plans/2026-09-19-swap-readiness-72h.md`).

## Key Files

| File                                | Purpose                                                                                          |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `test_ai_contract_registry.py`      | Registry completeness + the "no `ai.*` import at runtime" rule, asserted on the real module graph   |
| `test_ai_provider.py`               | Declared `AIProvider` interface: omitting a declared operation fails AT IMPORT, naming it          |
| `test_fake_provider.py`             | FakeProvider: all 37 ops, byte-determinism, AST mirror tests for class vocabularies                |
| `test_schema_snapshots.py`          | WP7.2: renaming a key in a contract model reddens CI naming the key (not a blob diff)              |
| `test_client_conformance.py`        | WP8.4: drives the six real backend AI clients through the FakeProvider (client parse methods)      |
| `test_conformance_ops.py`           | WP8.3 op-specific targets + the availability-matrix spine (absent / NOT-WIRED / wired states)     |
| `test_conformance_{geometry,numeric,semantics,vocabulary,dbvocabulary}.py` | WP8.3/8.5 per-property clusters |
| `golden/`                           | GENERATED (do not hand-edit) - see below                                                           |

## Generated `golden/` Directory

Both subdirs are emitted by `scripts/gen-ai-contract.py` from `backend/ai_contract/schemas/` (43 files each):

- `golden/snapshots/` - one shape digest per operation side (key to type token, required list, `$defs` names); a key rename produces a named diff.
- `golden/payloads/` - one contract-valid wire instance per operation side, imported verbatim by the fake and consumer tests INSTEAD of hand-written dicts.

Regenerate with `uv run python scripts/gen-ai-contract.py`; the `api-types-check` CI job runs `--check` and fails naming any drifted or stale file.

## Patterns and Gotchas

- **No xfail / skip / importorskip anywhere in this tier** (goal rule); a RULING-blocked finding is pinned as a characterization test, never left red. This is also why per-op absence is a GREEN GUARD, not a skip.
- **Never respx:** the fake is a real ASGI app - every hop is `httpx.ASGITransport` (`backend/ai_contract/fake/app.py`).
- Headers still carrying `DRAFT` / `UNVERIFIED` status notes are historical drafting context from the 72h plan; the in-tree pytest run is the arbiter.
- The tier inherits `ENVIRONMENT=test` and autouse settings-cache reset from `backend/tests/conftest.py`; there is no local conftest here.

## Related

- `../../../ai_contract/AGENTS.md` - the package under contract
- `../AGENTS.md` - contracts tier overview
