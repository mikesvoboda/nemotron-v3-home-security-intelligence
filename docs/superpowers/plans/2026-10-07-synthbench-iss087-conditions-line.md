# ISS-087 reporting half: conditions line + identical-item count — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Name the llama.cpp build and the server settings in every score report's conditions line, and report an identical-item count for every scored model pair — the reporting half of ISS-087's acceptance.

**Architecture:** Three small extensions to the existing replay → `run.json` → score → report flow: (1) an operator-declared `--server-settings` string recorded verbatim in `run.json`; (2) the conditions table gains Build and Server settings columns; (3) `comparison()` gains a per-pair `identical: {k, n}` (same bar-level outcome AND same risk score per item) and the report names it per pair. Frozen-record rule (B6) is respected by bumping `score_version` rather than pretending shapes never change.

**Tech Stack:** Python 3.12, pytest, uv. Repo: `/agents/agent-vss8/workspace`, branch `iss087-conditions-line` (off `vlm-pipeline` @ `96669bd2`).

**Spec:** The design doc is the ISS-087 register entry itself — `docs/vss-integration/17-action-plan.md`, block `#### ISS-087` (~:3791). Its **Acceptance** bullets are the binding requirements. The owner approved this half's design 2026-10-06/07 in session: operator-declared server settings (not observed), build + identical-count reporting now, control-replay execution deferred (owner-paced, event-driven at the next build bump).

## Global Constraints

- No changes to `synthbench/score/scoring.py`'s split reconciliation or any ISS-016 mechanism; `comparison()`'s existing keys keep their exact meaning.
- `metrics.json` may gain keys only with the `score_version` bump this plan names; no existing key changes meaning or value.
- Old `run.json` files (no new keys) must keep scoring and rendering, showing `unrecorded`/`—` — the same discipline as `_conditions.shown` and `_thinking`.
- Gates per task: `uv run --no-sync pytest backend/tests/unit/synthbench/ backend/tests/unit/evaluation/ -q` (baseline at plan time: **1271 passed, 1 skipped**), `python3 scripts/check-vss-docs-currency.py` → `ok` rc 0. Never `--no-verify`; commit trailer `Co-Authored-By: Claude Code <noreply@anthropic.com>`.
- Docs: docs 00–15 and 18–21 frozen; `17-action-plan.md` edits follow this branch's dated-note convention; `docs/synthbench/command-reference.md` is kept in lockstep with the CLI by `test_command_reference.py` (it reads `--help` output — a new option REQUIRES a reference edit in the same commit).
- Never run a real replay/export/GPU command; unit fixtures only.

## Review Focus

- **Old `run.json`, new report** — a replay record without `server_settings` (and vLLM's empty `build`) renders `unrecorded`/`—`, never crashes and never invents. Task 1 + Task 2 own the tests.
- **Empty vs declared server settings** — operator passes nothing → `unrecorded`; passes `""` → also `unrecorded` (an empty declaration says nothing); any non-empty string → verbatim, never reformatted. Task 1.
- **Identical means outcome AND score** — two items both `hit` but 70 vs 80 are NOT identical (ISS-087's own disagreement measure counts (verdict, risk_score) pairs); refusals (`risk_score` None) are identical only when both refused. Task 2.
- **Re-export/re-score of frozen pre-split records** — the per-pair key appears in `comparison` lists for unrecorded scores too (top-level `set(metrics)` is unchanged, so B6's pinned shape survives); the bump to `score_version` 4 is how a reader tells. Task 2 + Task 3.
- **CLI ↔ reference drift** — the new `--server-settings` option must appear in the reference's replay section in the same commit as the argparse change. Task 1.

---

### Task 1: `--server-settings` recorded in run.json, rendered in the conditions line

**Files:**

- Modify: `synthbench/commands/replay.py` (argparse + pass-through), `synthbench/run/replay.py` (`conditions()` signature and record), `synthbench/score/report.py` (`_conditions`)
- Test: `backend/tests/unit/synthbench/test_replay.py`, `backend/tests/unit/synthbench/test_score.py`

**Interfaces:**

- Consumes: `replay.execute(...)`'s existing path that calls `conditions(model, export)` at replay.py:355.
- Produces: `run.json` gains key `server_settings` — the operator's string, or `None` when not declared; `_conditions` renders a per-model row now containing build and server settings; report fixture helpers for a record WITH and WITHOUT the key.

- [ ] **Step 1: Write the failing tests.**
      In `test_replay.py`: the existing execute-with-fakes harness — call `execute` with the new arg `"cache flags: CACHE_RAM=0, CACHE_IDLE_SLOTS=0"` and assert the written `run.json["server_settings"]` is that exact string; and with the arg omitted, assert the key exists and is `None`.
      In `test_score.py`: extend the conditions-table test (find the test that renders `_conditions`/the conditions section): a replay record carrying `"server_settings": "prompt cache off (LLAMA_ARG_CACHE_RAM=0)"` and `"build": "b11376-a55e952b8"` shows BOTH strings in the rendered markdown conditions rows; a record missing BOTH keys renders `unrecorded` for server settings and `—` for build (mirror `_thinking`'s handling), and scoring still exits OK.

**Step 2: Run to verify they fail** — `uv run --no-sync pytest backend/tests/unit/synthbench/test_replay.py backend/tests/unit/synthbench/test_score.py -q`; expected: TypeError on the new kwarg / missing strings in rendered output.

- [ ] **Step 3: Implement.**
      `commands/replay.py`: `parser.add_argument("--server-settings", default=None, help=…)` (help names the ISS-087 why: llama.cpp build/cache flags change answers; declare what the endpoint was started with). Thread through to `run()` → `execute(..., server_settings: str | None = None)` → `conditions(model, export, server_settings)`; store `"server_settings": server_settings or None` in the record (an empty string records as `None` — Review Focus).
      `score/report.py` `_conditions`: add `"Build"` and `"Server settings"` to the header and `shown(r.get("build"), str)`-style cells (build `""`/missing → `—`; server settings missing → `unrecorded`). Keep column order Model first; put the two new columns last so existing columns keep positions.

- [ ] **Step 4: Reference lockstep.** `docs/synthbench/command-reference.md` replay section: document `--server-settings` (what it records, that replay cannot observe a server it did not start, `unrecorded` when omitted) and add server settings to the printed-conditions sentence if one exists. Run `uv run --no-sync pytest backend/tests/unit/synthbench/test_command_reference.py -v` → 2 passed.

- [ ] **Step 5: Run to verify pass + gates** — named files, then both gate suites + currency.

- [ ] **Step 6: Commit** — `feat(synthbench): replay records server settings; conditions line names build (ISS-087)`.

---

### Task 2: identical-item count per pair (and score_version 4)

**Files:**

- Modify: `synthbench/score/metrics.py` (`comparison()`), `synthbench/score/scoring.py` (SCORE_VERSION constant only)
- Test: `backend/tests/unit/synthbench/test_score.py`

**Interfaces:**

- Consumes: `comparison()`'s existing per-pair `by_a`/`by_b` outcome maps and its `common` item list.
- Produces: each pair dict gains `"identical": {"k": <int>, "n": <len(common)>}`; `metrics["identity"]["score_version"]` becomes `4`; report renders the count per pair (Task 3 renders; Task 2 asserts metrics only).

- [ ] **Step 1: Write the failing tests** — extend `test_the_comparison_is_paired_with_mcnemar_and_a_cluster_ci`'s fixture: two rows on a shared item with same outcome but different `risk_score` → that item counts in `n` but NOT in `k`; same outcome AND same score → counts in `k`; both refused → counts in `k`; one refused one scored → counts in `n` only. New small test: `set(metrics["comparison"][0])` contains `"identical"` for an UNARMED (manifestless) score. Bumping the version is the ISS-016-sanctioned mechanism for a legitimate additive change ("the version bump is real, so a reader can tell"): update `test_a_pre_split_export_scores_as_unrecorded`'s `score_version == 3` assertion to `== 4` and NOTHING ELSE in that test — its `set(metrics)`/model-block shape assertions must stay exactly as written (a pair gains a key; no top-level or model-block key moves). `grep -rn "score_version" backend/tests/` and update every pinned `3` the same way, nowhere else.

- [ ] **Step 2: Run to verify they fail** — expected: `KeyError: 'identical'` / version `3 != 4`.

- [ ] **Step 3: Implement** — inside the pair loop, `identical = sum(1 for i in common if by_a[i] == by_b[i] and rows-by-id risk_score equal)`; compute score equality from the row maps you already build (`{row["item_id"]: row.get("risk_score") ...}`), not by re-reading stores. Add the key to the pair dict with a one-line comment naming ISS-087 (this is the build-bump re-qualification measure). Bump `SCORE_VERSION` 3→4 at scoring.py — read its docstring/comment first; if any comment names the old value, update it.

- [ ] **Step 4: Run to verify pass + gates.**

- [ ] **Step 5: Commit** — `feat(synthbench): score pairs report identical-item counts (ISS-087)`.

---

### Task 3: render the count, close the register

**Files:**

- Modify: `synthbench/score/report.py` (comparison section), `docs/vss-integration/17-action-plan.md`, `docs/vss-integration/README.md`, `docs/synthbench/command-reference.md`

**Interfaces:**

- Consumes: Task 2's `pair["identical"]` (old metrics.json files may lack it — render must use `.get` and degrade to nothing, never `—`-noise on old frozen reports).
- Produces: markdown comparison sections state `identical k of n items` per pair; ISS-087's status and dependent counts recomputed by the gate; README Next-five updated.

- [ ] **Step 1: Write the failing test** — split-fixture report markdown contains `identical 1 of 3` (or the fixture's true numbers — compute from the fixture, do not force); a hand-built results dict WITHOUT `identical` renders the pair exactly as today (no `—`, no KeyError) — that's the old-frozen-report path.

- [ ] **Step 2: Verify fail → Step 3: Implement** — one column or trailing phrase in the existing comparison rendering (whichever the current `_table` shape makes cleanest; do not restructure the section). Old records degrade silently.

- [ ] **Step 4: Register flip (ISS-087 acceptance #1 and #2-report-half only — the issue stays OPEN).** Add a dated Update bullet inside ISS-087: the conditions line names build + server settings, and score pairs report identical counts, on `vlm-pipeline` (not main yet); acceptance #1 met on this branch for score reports; the control-replay-at-bump half and the ledger-rows claim stay open — status `open` unchanged, Dashboard UNCHANGED (no status flip → no recount; the currency script must still exit 0 untouched by arithmetic). README Next-five: mark the reporting half done. Intake: one dated entry (what shipped, the realized measure `identical {k,n}` semantics). Verify with `python3 scripts/check-vss-docs-currency.py` → ok.

- [ ] **Step 5: Gates + commit** — `feat(synthbench): report states identical counts; ISS-087 reporting half lands (ISS-087)`.

---

## After the plan

- Acceptance #3 (sweep controls in Intake log): verify the sweep's committed report (ISS-097) already records the three controls; if it does, note it in ISS-087's Update; if not, one dated Intake entry sourced to the committed report — no new measurement.
- NOT in this plan (owner-paced, by design): actually running the control replay at the next llama.cpp bump (needs `agent-gpu` + owner go-ahead); ledger-row conditions text (the register's rows are prose the owner authors — the Update note demonstrates the pattern).
