# golden/ - GENERATED, do not hand-edit

Both directories here are emitted by `scripts/gen-ai-contract.py` (plan P
WP7.2) from `backend/ai_contract/schemas/`:

- `snapshots/` - one shape digest per operation side (key to type token,
  required list, `$defs` names). A key rename in a contract model reddens
  `backend/tests/contracts/ai_providers/test_schema_snapshots.py` naming the
  key - a named diff, not a payload blob diff. Each snapshot also carries a
  `generated_by` field in-file.
- `payloads/` - one contract-valid wire instance per operation side, verbatim
  (no wrapper keys): both sides of the AI boundary import these instead of
  hand-written dicts (WP8.2 FakeProvider; consumer tests migrate per WP7.4).

Regenerate with `uv run python scripts/gen-ai-contract.py`; the api-types-check
CI job runs `--check`, which fails naming any drifted or stale file here.
