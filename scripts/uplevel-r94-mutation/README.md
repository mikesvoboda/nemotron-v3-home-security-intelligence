# `[r94]` evidence harness

The harness behind `[r94]`'s evidence (PR #7038): `battery.py` scores mutants against
this package's own suite, and `sourcing_shapes.py` measures how bash reads a converted
`API_KEYS` line. Contract rule 3 of `docs/uplevel/rules.md` (UR-10) — "tools live in the
repo; work from `/tmp` or a home directory does not count as evidence" — so both live
here, not in `/tmp`. Precedent: `scripts/uplevel-f13-done-when/`, which cites
`scripts/uplevel-real-tier/`.

`setup.py` and `setup_lib/core.py` are **not** in mutmut's scored set (`pyproject.toml`
→ `[tool.mutmut] source_paths = ["backend/services", "backend/api/routes"]`), so the
template's scored-module table does not cover this package. This battery is the
substitute: hand-transcribed mutants scored against this package's own suite.

## What it does

For each of the 16 mutants in `battery.py`: rewrite the working tree, run
`backend/tests/unit/setup_lib/test_r94_env_preserving_reruns.py`, restore the file from
an in-memory snapshot and verify the restore by SHA-256. A mutant that produces **zero
reds is reported QUIET and the run exits 1** — that is a gap in the pins, and it is the
only outcome here that means CI would have shipped the defect.

Two properties make the output trustworthy rather than decorative:

- **Every mutant declares its expected occurrence count** and the harness refuses a
  pattern that does not match it. A mutant whose pattern silently stopped matching
  leaves the product code unmutated, which would then read as "quiet" — a false
  indictment of the suite. `setup.py` has two interactive modes, so a mutant like M4
  declares `2`; a pattern that matched only one mode would undercount the suite and let
  a weak pin look strong.
- **Every mutant is transcribed from a site that exists in the product code today**, not
  invented. An invented near-miss can score 16/16 quiet against a guard that works.

## Run

Run on a clean tree — it rewrites `setup.py` and `setup_lib/core.py` for a few seconds
at a time, always restoring them:

```bash
uv run python scripts/uplevel-r94-mutation/battery.py
```

Expected output ends with all 16 RED and `quiet: none`, exit 0. `git status` should look
unchanged afterwards; if the run prints `RESTORE-FAILED` it exits 8 and leaves a file
mutated, so check `git diff` before trusting anything else.

## What each mutant pins

| mutant | defect it plants                                  | pin that must bite                         |
| ------ | ------------------------------------------------- | ------------------------------------------ |
| M1     | `.env` word handed straight to the y/n prompt     | a saved `true` opens the LAN on Enter      |
| M2     | `saved_or` ignores the saved value                | Foscam base path / AI models path reset    |
| M3     | `saved_port` ignores the saved port               | a re-run re-offers the first-run port      |
| M4     | both interactive modes drop the saved port        | same, in quick mode and guided mode        |
| M5     | both expose prompts stop offering the saved state | a re-run defaults a running install to off |
| M6     | the new flag's handler never runs                 | `--convert-monitoring-key` does nothing    |
| M7     | "already scoped" exits 1                          | running the flag twice reports failure     |
| M8     | a refusal exits 0                                 | a no-op refusal looks like success         |
| M9     | the rewritten line loses its terminator           | conversion joins two lines (found first)   |
| M10    | a scope-less object reads as already converted    | a fail-closed entry is never reported      |
| M11    | plain + object ambiguity is not refused           | the flag edits an ambiguous file           |
| M12    | two `API_KEYS` lines are not refused              | a byte-preserving rewrite of an ambiguity  |
| M13    | re-emission uses spaced separators                | the value drifts from setup.py's own shape |
| M14    | the quote pair is dropped entirely                | the line stops sourcing                    |
| M15    | `_value_of` takes the FIRST match, not the last   | a stale key gets the scope                 |
| M16    | "keep no quote as found" (the pre-fix policy)     | a pre-R60 line comes out unquoted          |

Four of these earned their place by finding something rather than confirming it. **M13
and M15 were QUIET on the first run** (13/15 caught at the time) — that is how the two
missing pins were found. **M9** plants a defect that was genuinely in this code as first
written here: the rewritten line dropped its own terminator, which joins two `.env`
lines. **M16** is the reverse direction — written after the fix to model the policy
before it ("keep the line's quote as found"), which is the defect worth pinning hardest
because the affected population is exactly the one this ruling targets: a pre-R60 file,
where `setup.py` wrote `API_KEYS` unquoted and a converted line would then come out
unquoted and stop sourcing.

## `sourcing_shapes.py` — the measurement behind the quote rule

This package claims the single quote, not the compact separators, is what makes a
converted `API_KEYS` line survive being sourced. That is a claim about bash, so it is
measured rather than asserted:

```bash
uv run python scripts/uplevel-r94-mutation/sourcing_shapes.py
```

| shape            | rc  | the value that arrives           |
| ---------------- | --- | -------------------------------- |
| unquoted-compact | 0   | mangled — JSON readers reject it |
| unquoted-spaced  | 127 | bash tries to _execute_ `{key::` |
| quoted-compact   | 0   | parses, 2 entries                |
| quoted-spaced    | 0   | parses, 2 entries                |

The two quoted rows parse, so compactness is a consistency choice (match
`merge_api_keys`, which writes `separators=(",", ":")`) and the quote is the
correctness one. The dangerous row is `unquoted-compact`: it exits 0 and hands the
operator a value that is silently not JSON. The probe exits 0 when exactly two rows fail
to parse, which is the split the table shows.
