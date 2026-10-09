# scripts/audit — Committed Measurement Scripts (O1.7)

## Purpose

One committed scanner per count a later uplevel package measures its work
against. `docs/uplevel/00-audit.md` shipped its **[A]** figures from scans
nobody committed, which breaks contract rule 3 (reproducible evidence) and
leaves B3.3, W1.1, W3.3, O3.3, BB.1 and Phase 4 comparing against numbers no
one can re-derive. Each script here is the scan view that number must be
re-measured under; replace the audit's figure with the run's value tagged
**[C]**, never with a hand-typed count.

## Scripts

```
scripts/audit/
  retired_names.py        the five §O1.7 retired names (the list lives in
                          NAMES there — this file deliberately does not
                          restate it: count_retired_names counts whole-word
                          mentions in AGENTS.md files against a committed
                          ceiling, and a new guide that names the names it
                          measures is +3 violations on its first commit),
                          whole-word (the validator's
                          rule), bucketed agents / living docs / code, dated
                          record trees exempt.          → B3.3, W1.1, W3.3
  settings_orphans.py     settings fields in backend/core/config.py read
                          nowhere outside it (case-folded env spelling;
                          over-approximates READS, never orphans).
                                                            → B3.3
  env_dead_vars.py        .env.example variables read by neither config.py,
                          compose nor setup.py.         → O3.3
  battery_census.py       test_<module>_batchNN*.py files: lines, collected
                          test count, target module; non-literal parametrize
                          args flagged, never guessed.     → Phase 4
  literal_groups.py       groups of >=3 tests differing only in literals;
                          imports parametrize-guard.py's masked-body identity
                          and raises-match bucket — do not fork that logic.
                                                              → BB.1
  nav_coverage.py         docs pages in the mkdocs nav and which are not;
                          authority is a `mkdocs build` log passed via
                          --build-log (the YAML nav alone misreads titles and
                          cannot see awesome-pages injection). Classifies
                          disabled/record instead of dropping them.
                                                              → W3.3
```

## Conventions (every script here)

- Run: `uv run python scripts/audit/<name>.py [--root REPO]` — JSON on
  stdout, one human summary line on stderr beginning `O1.7 <name>:`.
- Test: `uv run python -m pytest scripts/audit/test_<name>.py -q`. These
  files sit outside pytest `testpaths` on purpose (no self-collection); CI
  runs them explicitly in ci.yml's "Run the anti-rot gates' own tests" step.
  A census with no CI leg is a census that rots.
- Fail loud: unreadable or unparseable input exits 1 naming the file. A
  silent skip turns a census into a fossil.
- Direction of approximation is deliberate per script and documented in its
  docstring: a census may over-count LIVE (safe — cleanup deletes against it
  next run) but must never report a live thing DEAD (O3.3 would ratchet-delete
  a working variable).
