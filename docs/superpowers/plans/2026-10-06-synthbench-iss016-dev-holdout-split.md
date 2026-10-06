# Synthbench ISS-016: the tierb-v0 dev/holdout split — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix a hash-drawn, scenario-level dev/holdout split of `tierb-v0` (6 of 19 incident
scenarios to holdout, all benign in dev), recorded in the export, the eval store and the report, so
prompt tuning can only see dev and a tuned model's holdout number stays an honest generalization
check.

**Architecture:** The split is a derived fact keyed on scenario, never on item: `export vss` writes
a create-once `splits.json` manifest whose roster a published hash order recomputes; `replay`
copies it into a new `splits` table in the eval store; `score` reads one authoritative roster,
computes every model's headline per arm, prints labelled dev/holdout tables, and keeps holdout
stills out of the failure gallery. A pre-split export scores with today's exact shapes — the split
is optional end to end.

**Tech Stack:** Python 3.14 (`uv run`), stdlib only in the pieces that compute the draw (no new
dependencies anywhere), `backend/evaluation` (`EvalStore`, `s_metrics`, `cluster_stats`), the repo's
pre-commit gate.

**Spec:** `docs/superpowers/specs/2026-10-06-synthbench-iss016-dev-holdout-split-design.md` (read
it with this plan; it is the authority — decisions B1–B8, the realized draw, and §7's test table
live there).

## Global Constraints

- Tests live in `backend/tests/unit/synthbench/` and `backend/tests/unit/evaluation/` (CI runs only
  `backend/tests/unit/`). No GPU, network or podman in tests; pytest-timeout 5 s; the suite runs
  under xdist.
- Only `synthbench/score/` and `synthbench/run/` may import `backend`
  (`test_import_rule.py` parses every import); `synthbench/export/vss.py` imports nothing from
  `backend` and a test pins `CATEGORY_LABEL` equal to the importer's `_CATEGORY_LABELS`.
- Exit codes: 0 done, 1 request needs fixing (`RequestError`), 2 stop and ask the owner
  (`AskOwner`, `CorpusError`, `ExportConflict`, `ImportRefused`, `ScoreRefused`). Never catch
  broader.
- Exports and stores are create-once/frozen: a different bytes/roster raises, an identical re-write
  is a no-op. The corpus itself is read-only.
- The split is keyed on `str(facts["cell"]["scenario"])` only — no new per-item fields, no store
  item fingerprint changes.
- With `splits.json` absent, every existing **metric** key and value is unchanged (spec §4's shape
  rule); the permitted deltas are `score_version: 3`, `identity.split == {"source": "unrecorded"}`,
  per-row `"split": "unrecorded"`, and the report's `unrecorded` Split row.
- Line length 100; ruff, ruff-format, mypy and prettier through the pre-commit gate (semgrep is
  repaired in this sandbox and runs; never use `--no-verify`). Conventional commit messages ending
  with `Co-Authored-By: Claude Code <noreply@anthropic.com>`.
- After every commit that touches `docs/vss-integration/`, `python3
scripts/check-vss-docs-currency.py` must print ok.

## Review Focus

The failure modes no single task's happy-path tests will catch, each pinned by a named test in the
task that owns the code:

- **A silently changed roster.** Someone edits `SPLIT_SEEDS` or the digest recipe and the holdout
  becomes the flattering six. Pinned by Task 1's literal-seed assertion, fixed-digest pin, and
  pinned six-name roster, and by Task 3's no-op re-put refusing different bytes.
- **A pre-split export drifting.** The optional path quietly becoming "split of everything" would
  re-write history under frozen records. Pinned by Task 6's today-shape test (no `dev` key, no
  `split_comparison`, unchanged S2/S3 values) and Task 4's no-manifest replay test.
- **A holdout still reaching the gallery.** `report.html` is the tuning surface; one leaked scenario
  voids the split. Pinned by Task 7's no-holdout-event test and its fail-loud test on a row missing
  the `split` field.
- **Store/export roster disagreement scoring anyway.** Two truths would mean the arm labels are a
  coincidence. Pinned by Task 4's `ImportRefused` test and Task 5's `ScoreRefused` test.
- **The empty holdout S2 leg rendering as a passed bar.** n=0 must never read as 0%. Pinned by
  Task 6's `holdout["s2_cell"]["n"] == 0` / `rate is None` test and Task 7's `insufficient (n=0)`
  render test.

---

### Task 1: The draw and the manifest, pure

**Files:**

- Modify: `synthbench/export/vss.py` (append after `read_sets`)
- Test: `backend/tests/unit/synthbench/test_export_vss.py` (new class at the end)

**Interfaces:**

- Consumes: nothing outside this task.
- Produces (Task 2, 3, 4, 6 read these names; spec §2's block is the authority):

  - `SPLIT_FILE = "splits.json"`, `SPLIT_SEEDS: dict[str, str]`, `SPLIT_HOLDOUT_K = 6`
  - `scenario_rank(corpus_version: str, seed: str, scenario: str) -> str` (lowercase hex digest)
  - `draw_split(corpus_version: str, incident_scenarios: Sequence[str], *, seed: str = ...,
k: int = ...) -> dict[str, Any]` → `{"seed", "k", "scenarios": [{"scenario", "rank_sha256",
"arm"}]}` sorted by rank, arms `holdout`/`dev`; defaults from `SPLIT_SEEDS` /
    `SPLIT_HOLDOUT_K`; raises `KeyError` for a corpus version absent from `SPLIT_SEEDS`
  - `split_manifest_document(corpus_version: str, scenario_arm: Mapping[str, str], *, ...) ->
dict[str, Any]` → the §2 manifest (`corpus_version, seed, holdout_k, unit, arms, draw, items`)
  - canonical bytes: the existing `_json_bytes` (no new bytes helper);
    `split_sha256(document: dict) -> str` = sha256 hex of those bytes
  - `write_split(export_dir: Path, document: dict) -> bool` (create-once like `write_set`, raises
    `ExportConflict` on different bytes), `read_split(export_dir: Path) -> dict | None`

- [ ] **Step 1: Write the failing tests** — a `TestSplitDraw` class pinning: the realized draw
      (`draw_split("tierb-v0", ALL_19)` returns the spec's six, in the spec's order, `k=6`, counts
      64/177/209 via a scenario→count table asserted as data); the seed string asserted literally
      (`SPLIT_SEEDS["tierb-v0"] == "vss-iss016-s3-holdout-2026-10-06"`); a fixed-digest pin
      (`scenario_rank("tierb-v0", SPLIT_SEEDS["tierb-v0"], "knife_visible").startswith("2aad74ed")` —
      computed 2026-10-06, transcribed here so a recipe change fails); roster invariant to input order;
      changing the seed changes the roster; `max(0, min(k, n-1))` edges (1 scenario → k=0; 2 scenarios
      → k=1; 0 scenarios → k=0, empty draw); benign names passed in are a caller error the draw never
      sees (the function's docstring states it; the population edge is Task 2's);
      `split_manifest_document` with the full 31-scenario arm table produces arms covering all 31,
      benign always `dev`, and `items` counts, and its bytes are stable under dict construction order;
      `write_split` create-once: True first, False on identical bytes, `ExportConflict` on different
      content; `read_split` `None` on a directory without the file.

- [ ] **Step 2: Run to verify they fail** — `uv run pytest backend/tests/unit/synthbench/test_export_vss.py -k Split -v`; expected: `AttributeError`/`ImportError` on `vss.draw_split`.

- [ ] **Step 3: Implement** in `synthbench/export/vss.py`. The digest is
      `hashlib.sha256(f"{corpus_version}|{seed}|{scenario}".encode()).hexdigest()`; ranking key
      `(digest, name)`; `SPLIT_HOLDOUT_K = 6`; manifest per spec §2 (the `arms` lists sort by name;
      `draw` carries all incident scenarios with their digests and arms; `items` counts come from the
      caller's per-scenario item counts, which `split_manifest_document` takes as `scenario_arm` plus
      an `items_by_scenario: Mapping[str, Mapping[str, int]]` of `{"benign": n, "incident": m}` (the
      exact keyword may be tuned at implementation; the counts' presence in the manifest is what the
      tests pin) — the export command holds those, the pure module must not glob).

- [ ] **Step 4: Run to verify they pass** — same command; then the whole file:
      `uv run pytest backend/tests/unit/synthbench/test_export_vss.py -v`.

- [ ] **Step 5: Commit** — `feat(synthbench): the hash-drawn split and its manifest document (ISS-016)`
      over `synthbench/export/vss.py backend/tests/unit/synthbench/test_export_vss.py`.

### Task 2: `export vss` writes the manifest

**Files:**

- Modify: `synthbench/commands/export.py` (after the set loop in `run_vss`)
- Test: `backend/tests/unit/synthbench/test_export_vss.py` (extend `TestSplitDraw`)

**Interfaces:**

- Consumes: Task 1's `split_manifest_document`, `split_sha256`, `write_split`, `read_split`,
  `SPLIT_FILE`, `SPLIT_SEEDS`; `spec.cell.scenario`, `spec.cell.group`, `spec.label` from the loop
  already in `run_vss` (`vss.CATEGORY_LABEL[category] == spec.label` is asserted a few lines above).
- Produces: an export directory that either holds `splits.json` (canonical `_json_bytes` of the
  manifest) or prints `no split registered for <version>` and holds none.

- [ ] **Step 1: Write the failing tests** — on `_ready_batch(tmp_path, MIXED, 8)`, whose asserted
      category coverage means the export population holds exactly 2 incident scenarios (`knife_visible`
      threat, `loitering` suspicious) so the k-edge fires: first export writes `_out(root)/splits.json`
      whose parsed `arms.holdout` is exactly `["knife_visible"]` (its digest `2aad…` ranks before
      `loitering`'s `a911…` — pin it; if the recipe changes, this test failing is correct) and whose
      stdout line reports the roster, the counts and the manifest sha256; the **existing**
      `test_a_second_export_changes_nothing` stays green as written (the manifest lives inside
      `_tree(_out(...))`, so it proves byte-identical re-export — do not edit it); a pre-placed
      hand-written `splits.json` whose bytes differ raises to `cli.EXIT_ASK` naming `differs` (the
      fixture and assertion shape of `test_a_set_that_differs_from_the_corpus_exits_2`); a corpus whose
      version has no registered seed prints the unregistered line and writes no manifest.

- [ ] **Step 2: Run to verify they fail** — expected: no `splits.json` exists.

- [ ] **Step 3: Implement** in `run_vss`: while looping the ready non-ambiguous events, collect
      `scenario -> {"benign": x, "incident": y}` counters from `spec.cell.scenario` and `spec.label`.
      After the loop, when `tax.version in vss.SPLIT_SEEDS`: a scenario contributing both labels is an
      `AskOwner` (the split's premise — label purity — broke; the existing per-event label check shows
      the style); the draw population is the scenarios with ≥1 incident item, sorted; benign scenarios
      join the arm table as `dev`; call `split_manifest_document` + `write_split`, and translate
      `vss.ExportConflict` into `AskOwner` exactly as the `write_set` call in the loop does. Otherwise
      print the unregistered line. Keep the existing summary line's format and append one line.

- [ ] **Step 4: Run to verify they pass** — full file green; also
      `uv run pytest backend/tests/unit/synthbench/test_import_rule.py -v`.

- [ ] **Step 5: Commit** — `feat(synthbench): export vss records the split manifest (ISS-016)`.

### Task 3: The store's `splits` table

**Files:**

- Modify: `backend/evaluation/eval_store.py`
- Test: `backend/tests/unit/evaluation/test_eval_store.py`

**Interfaces:**

- Consumes: nothing from Tasks 1–2 (table is split-format-agnostic by design).
- Produces: table `splits(corpus_version, scenario, arm, seed, manifest_sha256, PRIMARY
KEY(corpus_version, scenario))` with `CHECK (arm IN ('dev','holdout'))`, added to the existing
  `executescript`; `EvalStore.put_split(corpus_version: str, rows: Sequence[Mapping[str, Any]], *,
seed: str, manifest_sha256: str) -> None` (rows: `{"scenario", "arm"}`; idempotent per row;
  raises `ValueError` when a stored row's `arm`, `seed` or `manifest_sha256` differs, or when
  `manifest_sha256` differs from the one already recorded for that corpus version);
  `EvalStore.get_split(corpus_version: str) -> list[dict[str, Any]] | None` (rows sorted by
  scenario, or `None` when the version has none).

- [ ] **Step 1: Write the failing tests** — put/get round-trip sorted by scenario; re-put identical
      rows is a no-op (no row growth, no error); same scenario different arm raises and the message
      names the scenario; a different `manifest_sha256` on re-put raises; `get_split` `None` before any
      put; `arm: "maybe"` raises (CHECK constraint surfaces as `ValueError` — wrap the sqlite
      `IntegrityError` into `ValueError` with the row shown, matching `put_item`'s style).

- [ ] **Step 2: Run to verify they fail** — `uv run pytest backend/tests/unit/evaluation/test_eval_store.py -k split -v`; expected `AttributeError`.

- [ ] **Step 3: Implement** — the DDL goes inside the existing `executescript` block (old stores
      gain it on open via `CREATE TABLE IF NOT EXISTS`; no migration code); keep methods adjacent to
      `put_item`/`get_item` and their commit discipline.

- [ ] **Step 4: Run to verify they pass** — whole file green (the schema change must not disturb
      any existing store test).

- [ ] **Step 5: Commit** — `feat(eval-store): a splits table pinned by manifest sha256 (ISS-016)`.

### Task 4: Replay imports and records the split

**Files:**

- Modify: `synthbench/run/replay.py` (`_import` / `execute`'s record dict)
- Test: `backend/tests/unit/synthbench/test_replay.py`

**Interfaces:**

- Consumes: Task 1's `read_split`, `split_sha256`; Task 3's `put_split`, `get_split`.
- Produces: after a replay, the store holds one `splits` row per exported scenario when the export
  carried a manifest; `run.json` gains `"split_sha256": str | None` and `"split_holdout":
list[str]` (empty when unrecorded). Task 6 reads these two keys from `run.json` — `_REPLAY_KEYS`
  must gain both or the score identity cannot see them.

- [ ] **Step 1: Write the failing tests** — extend the existing splitless replay fixture by writing
      a `splits.json` (via Task 1's `write_split` on a two-scenario-incident document): store ends with
      4 scenario rows, holdout scenario armed `holdout`, benign `dev`; `run.json.split_sha256` equals
      `split_sha256(read_split(export))` and `run.json.split_holdout == ["knife_visible"]`; a replay
      against a store whose recorded roster says `knife_visible` is `dev` raises `ImportRefused` whose
      message names the manifest sha256 it found and the one the export carries; a manifestless export
      keeps both new `run.json` keys at `None`/`[]` and records nothing (today's shape preserved).

- [ ] **Step 2: Run to verify they fail** — expected: no `split_sha256` key.

- [ ] **Step 3: Implement** — call `put_split` in `execute` right after the `_import` step (not
      inside `import_generated_items`: `label_import` stays untouched, and the store commits
      per-record, so a crashed run re-records idempotently on rerun); translate `ValueError` from
      `put_split` into `ImportRefused` naming both digests; add the two record keys and both to
      `_REPLAY_KEYS` in `synthbench/score/scoring.py` (this file edit is one line here so the score
      side of replay stays green; Task 6 consumes them).

- [ ] **Step 4: Run to verify they pass** — `uv run pytest backend/tests/unit/synthbench/test_replay.py backend/tests/unit/synthbench/test_score.py -v`
      (score's fixture run.json lacks the keys → `_REPLAY_KEYS` membership must tolerate absence the
      way the other optional conditions keys already do; check how `test_score.py` builds run.json and
      follow it).

- [ ] **Step 5: Commit** — `feat(synthbench): replay imports the split and records its digest (ISS-016)`.

### Task 5: Score loads one roster; arms onto results; version 3

**Files:**

- Modify: `synthbench/score/scoring.py`
- Test: `backend/tests/unit/synthbench/test_score.py`

**Interfaces:**

- Consumes: Task 3's `get_split`; Task 4's run.json keys; Task 1's `read_split`, `split_sha256`.
- Produces: `load_split(store, export, replay_records) -> tuple[dict[str, Any] | None, dict[str, Any]]`
  → `(scenario_arm | None, identity_dict)`; identity is `{"source": "splits.json", "sha256", "seed",
"holdout_k", "holdout": [names], "items": {...}}` or `{"source": "unrecorded"}`; raises
  `ScoreRefused` when store and export disagree. `execute()` puts it at `identity["split"]`, sets
  `SCORE_VERSION = 3`, and threads `scenario_arm` into `result_rows` (Task 7's `markdown`/`html`
  consume `identity["split"]`). Each `results.jsonl` row gains `"split": "dev"|"holdout"|
"unrecorded"`.

- [ ] **Step 1: Write the failing tests** — (a) a fixture export+store pair carrying a split scores
      with `identity["split"]["sha256"]` set and rows' `split` values matching the scenario→arm table
      (reuse the existing score fixture, extended as Task 4's test extended replay's); (b) the same
      fixture with the store roster edited to disagree raises `ScoreRefused` naming both digests;
      (c) today's manifestless fixture gives `identity["split"] == {"source": "unrecorded"}`, every row
      `"unrecorded"`, and `score_version == 3`; (d) `metrics.json` identity on the split fixture carries
      `holdout == ["knife_visible"]` and `items.holdout.incident == <fixture count>`.

- [ ] **Step 2: Run to verify they fail** — expected: `KeyError: 'split'`.

- [ ] **Step 3: Implement** — `load_split` cross-checks store rows vs `read_split` bytes digest
      before trusting either; unrecorded means BOTH sources empty (store rows without a file, or a file
      the store never recorded, are a `ScoreRefused`, not a silent fallback); `result_rows` gains a
      keyword `scenario_arm: Mapping[str, str] | None` and computes the row value from the item's
      scenario (never from `identity` — the rows are written before the report needs nothing, and the
      helper must stay pure for Task 7's gallery test to call it directly).

- [ ] **Step 4: Run to verify they pass** — `uv run pytest backend/tests/unit/synthbench/test_score.py -v`.

- [ ] **Step 5: Commit** — `feat(synthbench): score carries one split truth from store and export (ISS-016)`.

### Task 6: Per-arm metrics

**Files:**

- Modify: `synthbench/score/metrics.py` (`score_models` gains the keyword; the call site
  `synthbench/score/scoring.py:202` passes it)
- Test: `backend/tests/unit/synthbench/test_score.py`

**Interfaces:**

- Consumes: `Item.facts["cell"]["scenario"]`; Task 5's `scenario_arm` table, reaching
  `score_models` through a new keyword-only parameter
  `score_models(replays, items, answers, sampled, *, scenario_arm: Mapping[str, str] | None = None)`
  — the same table Task 5 handed to `result_rows` from one `load_split` call in `execute()`.
- Produces: with an arm table, `score_models` returns model blocks
  `{replay_id, excluded, all, audited, dev, holdout, slices, scenario_slice_dev}` and a top-level
  `split_comparison: {"dev": [...], "holdout": [...]}`; without one, exactly today's shape (spec
  §4's shape rule — this is what keeps frozen records byte-comparable; `scenario_slice_dev` exists
  only when armed).

- [ ] **Step 1: Write the failing tests** — split fixture: `models[m]["holdout"]["s2_cell"]["n"]
== 0`, `holdout["s2_cell"]["rate"] is None` and `holdout["s2"]["fp_rate"] is None` (the two
      objects, the `cell()` wrapper and `s2_false_positive_rate`'s own dict, both empty-leg),
      `holdout["s2_cell"]["insufficient"] is True`;
      `dev.n + holdout.n == all.n` for every model; `dev + holdout` item counts equal the manifest's;
      `split_comparison` present with two lists each holding one pair entry; `audited` unchanged by the
      split (same value as an armless run of the same rows). The B6 today-shape test from Task 5(c)
      stays green and additionally asserts `"dev" not in block` and `"split_comparison" not in metrics`.

- [ ] **Step 2: Run to verify they fail** — expected `KeyError: 'holdout'`.

- [ ] **Step 3: Implement** — partition `kept` by arm before `headline()`; run the existing
      `comparison()` per side feeding already-partitioned `(model, rows)` pairs (signature unchanged);
      `slices` stays on `kept` (Task 7 adds the dev scenario slice from the same partition — expose it
      by returning `dev_rows` in no public structure: compute the dev scenario slice inside
      `score_models` as `slices(dev_rows, items)["scenario"]` under key `scenario_slice_dev`, only
      when armed).

- [ ] **Step 4: Run to verify they pass** — `uv run pytest backend/tests/unit/synthbench/test_score.py -v` plus the ISS-043 comparison tests still green.

- [ ] **Step 5: Commit** — `feat(synthbench): per-arm headlines and comparisons (ISS-016)`.

### Task 7: The report and the dev-only gallery

**Files:**

- Modify: `synthbench/score/report.py`
- Test: `backend/tests/unit/synthbench/test_score.py`

**Interfaces:**

- Consumes: Task 5's `identity["split"]` and per-row `split`; Task 6's per-model `dev`/`holdout`
  blocks, per-model `scenario_slice_dev`, and top-level `split_comparison`.
- Produces: `markdown()` sections per spec §5 (Split identity row; `## What this split can and
cannot say`; `## Headline: dev split (tuning may see this)`; `## Headline: holdout split (tuning
never saw this)`; `### Scenario slice, dev only`; per-split Comparison with the rule applied to
  dev only); `html()` signature unchanged in argument list (it already receives `identity`) but it
  filters gallery rows: keep `row["split"] in ("dev", "unrecorded")`, raise `ValueError` when a row
  has no `split` key at all.

- [ ] **Step 1: Write the failing tests** — the split-fixture `report.md` contains the Split row
      (`holdout 1 scenarios`), the can/cannot-say heading, both labelled headlines, the holdout S2 cell
      rendering `insufficient (n=0)` with its design footnote, and the dev scenario slice; contains no
      holdout event id; the manifestless fixture's report contains
      `unrecorded — this export predates ISS-016` and none of the new sections; `report.html` contains
      neither the holdout event id nor its still path; a hand-built results list with a row lacking
      `split` raises `ValueError` from `html()`; a row with `"split": "unrecorded"` renders (gallery
      unchanged for old shape).

- [ ] **Step 2: Run to verify they fail** — expected: missing section strings.

- [ ] **Step 3: Implement** — reuse `_headline(models, "dev")` / `_headline(models, "holdout")`
      verbatim (that is the point: same columns, different label); the comparison section loops
      `(("dev", ...), ("holdout", ...))` from `split_comparison` when present, keeping today's single
      table when not; the gallery filter lives in `html()` before `_card` (one `raise ValueError`
      naming the row's `item_id`, then the two-way keep — spec §5 records that this is report.py's
      first raise and why).

- [ ] **Step 4: Run to verify they pass** — `uv run pytest backend/tests/unit/synthbench/test_score.py -v`;
      then the FULL suite `uv run pytest -q` and `python3 scripts/check-vss-docs-currency.py`.

- [ ] **Step 5: Commit** — `feat(synthbench): labelled dev/holdout reporting, dev-only gallery (ISS-016)`.

### Task 8: Register, references, and the real draw

**Files:**

- Modify: `docs/vss-integration/17-action-plan.md`, `docs/vss-integration/README.md`,
  `docs/synthbench/command-reference.md`
- Test: existing `test_command_reference.py` (argparse ↔ reference; new output text is not an
  option, so no change is expected — run it to confirm).

**Interfaces:**

- Consumes: the shipped mechanism from Tasks 1–7.
- Produces: the register state after ISS-016 closes; the real manifest on the owner's next export.

- [ ] **Step 1: Command reference** — document the manifest behavior under `export vss` (the file
      it writes, the unregistered-corpus line, exit 2 on a conflicting manifest). Run
      `uv run pytest backend/tests/unit/synthbench/test_command_reference.py -v`.

- [ ] **Step 2: The register flip** — ISS-016 status `open` → `done`, closure note (branch, spec +
      plan paths, the realized roster, what the split does NOT do: not tuning, not OD-15 label work);
      update the derived Dashboard counts (status `done` +1, P1 open −1, severity total open −1,
      `agent-now` open −1, `risk` kind open −1, the Evaluation-area open column −1) and the
      counts-as-of line; README Next-five and the pin line. This is the same mechanical flip the
      ISS-043 closure performed — copy its Intake-entry discipline: one dated Intake entry (realized
      roster + one-sentence scope), no renumbering, docs 00–15 untouched.

- [ ] **Step 3: Gate** — `python3 scripts/check-vss-docs-currency.py` → `ok`; prettier via
      pre-commit on the two docs.

- [ ] **Step 4: Commit** — `docs(vss): ISS-016 done — the tierb-v0 split ships on vlm-pipeline`.

- [ ] **Step 5: The real manifest (owner-paced, NOT a code step)** — `synthbench export vss` writes
      `$SYNTHBENCH_ROOT/exports/tierb-v0/vss/splits.json` on its next run against the real corpus; the
      owner's export host has the corpus. The printed roster must equal the spec's six; if it does not,
      STOP — the export population changed (a new batch with new scenarios) and the split design's
      premise needs the owner, not a code fix. No GPU needed; the manifest lands before any replay.

---

## After the plan

Frozen-record note: P5a's and the sweep's committed records are not re-scored (spec Out of scope);
nothing in this plan opens or rewrites them.
