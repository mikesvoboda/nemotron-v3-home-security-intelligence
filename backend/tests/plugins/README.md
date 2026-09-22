# Test plugins (opt-in)

Nothing in this directory loads automatically. Attach explicitly:

```bash
PYTHONPATH=backend/tests/plugins DURATIONS_DIR=/tmp/durations \
  uv run pytest backend/tests/integration -p durations_plugin
```

(`DURATIONS_DIR` unset defaults to gitignored `.pytest_cache/durations` — deliberately
not `/tmp`, which has wiped mid-analysis before.)

- `durations_plugin.py` — per-phase (setup/call/teardown) duration recorder;
  each xdist worker appends `$DURATIONS_DIR/<worker>.tsv` rows immediately
  (`nodeid  when  dur  outcome  slow  timeout_mark`), so a mid-run worker
  crash only loses the in-flight test. Promoted from
  `docs/superpowers/staged/2026-09-14/dur/` (M3 T4; that gitignored staging
  directory has since been cleaned up — this file is the surviving copy. The
  owner ruling that un-armed `timeout_func_only` was decided on the staged
  plugin's measurement output).

Note: with xdist the plugin records every report twice — once in the worker
(`gwN.tsv`) and once as the controller receives it (`main.tsv`), identical
durations. Sum/average analysis must count gw-rows only (main.tsv is a
mirror); percentiles are duplicate-invariant.
