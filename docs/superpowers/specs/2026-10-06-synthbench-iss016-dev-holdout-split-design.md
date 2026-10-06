# Synthbench ISS-016: the tierb-v0 dev/holdout split — Design

- **Date:** 2026-10-06
- **Status:** design approved in chat by the owner on 2026-10-06 (the split shape by one ruling, the
  rest section by section); this document awaits the owner's review before the plan.
- **Register:** `docs/vss-integration/17-action-plan.md` ISS-016 (P1, risk, agent-now). Branch
  `vlm-pipeline`, inside the measurement-validity slice the owner authorized on 2026-10-06;
  ISS-043 (scenario-cluster statistics, the paired test, the sampling conditions line) closed the
  same day and is a precondition of this design, not a part of it.
- **Parent specs:** `docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md`
  (§2 export, §5 score and report — this design extends both) and
  `docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md`.
- **Owner rulings this design executes (2026-10-06, in-session):** the measurement-validity slice
  is authorized; the split is **"hash-drawn 6 of 19 incident scenarios"**, with all benign items
  staying in dev.

## Goal

Before any prompt or specialist tuning touches `tierb-v0`, fix a split of the corpus into a dev set
that tuning may see and a holdout that tuning never sees, so that a tuned model's S3 number stays
an estimate of future performance instead of a measurement of how well the prompt memorized the
evaluation set. ISS-016 states the risk: F14's next lever _is_ prompt tuning ("if no candidate
reaches 90%, the lever is prompts and specialist context"), and a per-scenario failure gallery
makes overfitting easy.

The deliverable is the mechanism — a drawn, hash-pinned split, recorded in the export, the eval
store and the report — plus the reporting that labels which number came from which side. It is
deliberately not the tuning itself.

## What the corpus decides (measured 2026-10-06, not assumed)

| Fact                                                                  | Value                                                                    |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Corpus events / scenarios (`/synthbench/corpus/tierb-v0`, 919 events) | 32 scenarios                                                             |
| Scenarios holding more than one label                                 | **none — every scenario is label-pure**                                  |
| Scenarios that reach the export                                       | 31 (the 32nd, `costume_weapon`, is wholly `ambiguous` and never exports) |
| Exported items (ready, non-ambiguous)                                 | 450: **241 incident**, **209 benign**                                    |
| Scenario split by arm                                                 | 12 benign-only (209 items), 19 incident-only (241)                       |
| Incident scenarios by group                                           | 13 threat, 6 suspicious                                                  |
| Items per scenario (exported)                                         | 8–29, median 9; five scenarios carry 29                                  |
| Measured S3 (shipped Qwen3-VL-8B Q4_K_M, P5a)                         | 36.5% [30.7–42.8] — the F14 bar is 90%                                   |
| Measured S2                                                           | 6.7% [4.0–10.9] — the F14 bar is ≤5%                                     |
| Suspicious-scene recall (the weak leg)                                | 2.2% (P5a), 13.3% (flagship)                                             |
| Hard-negative scenarios where S2's false alarms live                  | `hooded_jogger` 27.6%, `power_tools_at_night` 17.2%                      |

Three consequences drive every choice below:

1. **Label purity means "stratify by scenario" is only possible within an arm.** A scenario
   contributes either only benign items or only incident items, so no scenario-level split can hold
   both bars at once. ISS-016's acceptance text anticipated this ("consider a split on S3 only, or
   on scenario rather than item"); the corpus says those two hedges are the same move.
2. **The correlation unit is the scenario** (ISS-043: a framing or rendering artifact misread once
   tends to be misread on _every_ still of that scenario; the sweep's scenario-cluster CIs are wide
   enough that no model arm separates from the shipped one). A holdout that shares scenarios with
   dev would be tested on artifacts dev already saw — which is precisely the leakage the holdout is
   for. So the holdout holds **whole scenarios**, and no scenario appears on both sides.
3. **A benign holdout cannot measure S2.** ISS-016 computed it: ~63 benign items gives a Wilson
   upper bound near 5.7% at 0/63 against a 5% bar. And routing hard-negative scenarios to holdout
   would strip dev of the scenarios where false alarms actually occur, so tuning could not see its
   own S2 lever at all. S2 is therefore measured on the full 209-item benign arm, in dev, by design.

## Decisions

| #   | Decision                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| B1  | **S3-only split, scenario-level.** The split partitions the 19 incident scenarios. All 209 benign items stay in dev: S2 keeps its full arm, and dev keeps every hard-negative scenario. The holdout measures one thing — whether prompt/specialist tuning generalized to scenario types it never saw — and the report says so.                                                                                                                                                                                     |
| B2  | **Six of nineteen incident scenarios go to holdout** (owner ruling, 2026-10-06). Six is ~31% of the incident scenarios and lands near the 30% ISS-016 proposed, without pretending a 19-scenario universe supports a precise fraction.                                                                                                                                                                                                                                                                             |
| B3  | **The draw is a published hash order, not a human choice or a drawn RNG sample** (owner ruling). Rank the 19 incident scenario names by `sha256("<corpus_version>\|<seed>\|<scenario>")` (hex digest, ties broken by name) and take the first six. The seed is the pre-registered string `vss-iss016-s3-holdout-2026-10-06`. Anyone holding three published strings recomputes the roster; nobody, including the owner, can pick a flattering holdout, and no RNG version or stream position can shift the answer. |
| B4  | **No stratification.** The draw is unstratified by group. The realized draw landed 3 threat / 3 suspicious against a 13/6 scenario mix — flattering is luck, not design; a stratified draw would add a second sampling stage and a second place to get wrong, and with two strata the "randomness" is mostly nominal anyway. The report prints the holdout's mix so a reader can discount it.                                                                                                                      |
| B5  | **The split is keyed on scenario, never on item.** Scenario is already on every exported label (`synthbench.cell.scenario`), already the key ISS-043 clusters on, and already the key the slices break on. Membership is derived, so the item payloads and their store fingerprints never change: existing frozen stores keep their meaning, and no item's identity is edited to carry a split.                                                                                                                    |
| B6  | **The split is optional end to end.** An export without a split manifest scores exactly as it does today and reports `split: unrecorded`. Every frozen record (P5a, the 2026-10-03 sweep) stays reproducible and re-readable. The split arrives with the next export of `tierb-v0`.                                                                                                                                                                                                                                |
| B7  | **The holdout's stills and failures never enter the tuning surface.** `report.md` prints holdout aggregates; `report.html`, the failure gallery, and therefore the per-scenario failure detail a tuner reads, carry **dev items only**. This is the enforcement half of "tuning uses dev only": the gallery is what tuning actually looks at.                                                                                                                                                                      |
| B8  | **A store/export split disagreement stops the run** (`ScoreRefused`, exit 2, the "move the eval store aside" guidance) rather than re-labelling silently. Same disposition as the existing stale-fingerprint check.                                                                                                                                                                                                                                                                                                |

## The realized draw (2026-10-06, recomputable)

Ranking all 19 incident scenarios by `sha256("tierb-v0|vss-iss016-s3-holdout-2026-10-06|<scenario>")`,
the first six:

| #   | Scenario               | items | group      |
| --- | ---------------------- | ----- | ---------- |
| 1   | `tailgating`           | 9     | suspicious |
| 2   | `blunt_weapon`         | 9     | threat     |
| 3   | `car_break_in`         | 9     | threat     |
| 4   | `casing_with_phone`    | 9     | suspicious |
| 5   | `knife_visible`        | 19    | threat     |
| 6   | `peering_into_windows` | 9     | suspicious |

**Holdout: 64 incident items (27% of 241), 0 benign. Dev: 386 items — 209 benign, 177 incident.**
Holdout arm composition 3 threat / 3 suspicious, beside the corpus incident mix of 13 threat / 6
suspicious scenarios. Dev keeps 13 incident scenarios (10 threat, 3 suspicious) and all 12 benign
scenarios.

Two properties of the realized draw are recorded because they bound what the holdout can say:

- **n=64 is a leak detector, not a precise estimate.** An S3 reading on 64 items carries a
  scenario-cluster interval several times wider than the same count of independent items would, so
  a holdout number of, say, 30% [18–45] is a check that dev's tuning did not collapse generalization,
  not a competing measurement of the 90% bar.
- **The holdout is suspicious-heavy relative to the arm** (3 of 6 scenarios, and suspicious scenes
  are where recall is worst: 2.2% shipped). The holdout's S3 level will therefore read _below_ dev's
  for any prompt that has not fixed the weak leg. This is expected and is stated in the report; it
  is the price of B4's no-stratification, and it is why the holdout's verdict is paired with the
  dev-vs-holdout gap, never read as an absolute bar attempt.

## §1 Flow

Unchanged shape; the split is a new fact recorded at export and read at score.

```
corpus ──export vss──▶ export/<v>/vss/{<category>/<set>/…, splits.json}
                          │                      │
                     replay (imports sets)   record split: sha256 + roster
                          ▼                            │
                    eval store (items + splits table)  │
                          ▼                            ▼
                        score ──▶ metrics.json (all/dev/holdout) ─▶ report.md (labelled)
                                                            └────▶ report.html (dev only)
```

## §2 Export: the split manifest

`synthbench/export/vss.py` gains the pure pieces (module rule holds: it imports nothing from
`backend`):

```python
SPLIT_FILE = "splits.json"
SPLIT_SEEDS = {"tierb-v0": "vss-iss016-s3-holdout-2026-10-06"}  # pre-registered; changing the
                                                                 # value changes the roster
SPLIT_HOLDOUT_K = 6

def scenario_rank(corpus_version: str, seed: str, scenario: str) -> str: ...
def draw_split(corpus_version: str, incident_scenarios: Sequence[str],
               *, seed: str = ..., k: int = ...) -> dict[str, Any]: ...
def split_manifest_document(corpus_version: str, scenario_arm: Mapping[str, str], ...) -> dict: ...
def split_sha256(document: dict) -> str: ...   # sha256 of the canonical bytes
def write_split(export_dir: Path, document: dict) -> bool: ...  # create-once, like write_set
def read_split(export_dir: Path) -> dict | None: ...            # None: pre-split export
```

`draw_split` takes the incident scenario names **from the export population**, not from a hardcoded
list: the scenarios that actually appear in the sets being exported, sorted. Benign scenarios never
enter the draw. Ranking is `sha256(f"{corpus_version}|{seed}|{scenario}")` over UTF-8, compared as
lowercase hex, ties by name; the first `k` are `holdout`, the rest `dev`.

`splits.json` — written at the export root, canonical `json.dumps(..., indent=2, sort_keys=True)`,
the same canonicalization `set_files` uses:

```json
{
  "corpus_version": "tierb-v0",
  "seed": "vss-iss016-s3-holdout-2026-10-06",
  "holdout_k": 6,
  "unit": "scenario",
  "arms": {"dev": [...13 incident + 12 benign scenario names...], "holdout": [...6...]},
  "draw": [{"scenario": "tailgating", "rank_sha256": "…", "arm": "holdout"}, …all 19…],
  "items": {"dev": {"benign": 209, "incident": 177}, "holdout": {"benign": 0, "incident": 64}}
}
```

`arms` lists every scenario in the export, benign ones under `dev` with their arm assigned by rule
(B1), so a reader never has to re-derive which scenarios exist. `draw` carries all 19 ranked
incident scenarios with their digests: the manifest is its own audit trail, and the roster can be
checked without the seed.

`export vss` writes it after the sets, create-once like every other artifact: an existing
`splits.json` with identical bytes is left alone, a different one raises `ExportConflict` → exit 2,
"ask the owner". The command prints the roster, the item counts and the manifest sha256.

Two edges, stated so no caller has to guess:

- **A corpus version with no pre-registered seed exports without a manifest.** `SPLIT_SEEDS` carries
  exactly `tierb-v0`; the next corpus version gets its own pre-registered string, added by the
  owner, before its split exists. Reusing `tierb-v0`'s seed for a new corpus would correlate two
  rosters for no reason, so there is no fallback seed. The command prints `no split registered for
<version>` and exits 0 — B6's optionality is the same code path.
- **`k` never empties dev, and never goes negative.** The draw size is
  `max(0, min(k, n_incident - 1))`: `tierb-v0` draws its full six; a 1- or 2-scenario incident arm
  draws zero, records `holdout_k: 0` beside the draw's full ranked list, and keeps dev non-empty (a
  split with no dev incidents measures nothing). This only fires on test fixtures and a
  hypothetically stunted corpus.

## §3 The eval store: a `splits` table

`backend/evaluation/eval_store.py` gains one table, additive to the existing three:

```sql
CREATE TABLE IF NOT EXISTS splits(
    corpus_version TEXT NOT NULL,
    scenario       TEXT NOT NULL,
    arm            TEXT NOT NULL CHECK (arm IN ('dev','holdout')),
    seed           TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    PRIMARY KEY (corpus_version, scenario)
);
```

- `EvalStore.put_split(corpus_version, rows, *, seed, manifest_sha256)` — idempotent re-put of
  identical rows is a no-op; a scenario already stored under a different arm, or a store whose
  recorded `manifest_sha256` differs from the one being written, raises `ValueError`. Same shape as
  the frozen-item rule: a store's split is born once and is not edited in place.
- `EvalStore.get_split(corpus_version) -> list[dict] | None`.
- `backend/evaluation/label_import.py` and `synthbench/run/replay.py`: replay's import step reads
  `<export>/splits.json` if present and records it, in the same transaction as the item import,
  refusing (its existing `_ImportRefused` path → exit 2) when the store already holds a different
  roster for that corpus version.

`replay`'s `run.json` gains `split_sha256` and the holdout roster (the six names), so a replay
states the split it measured under beside the labels digest it already states. Items and their
fingerprints are untouched — B5.

## §4 Score: three readings, one truth per number

`synthbench/score/scoring.py`:

- `SCORE_VERSION` 2 → **3**. Each model's block gains `dev` and `holdout` siblings of `all`, and
  `identity.split` appears. Metrics written by older code are distinguishable by this field, which
  is its only purpose, exactly as with the ISS-043 bump.
- Identity gains `"split": {"source": "splits.json", "sha256": …, "seed": …, "holdout_k": 6,
"holdout": [names], "items": {…}}`, read from the store when the store has it and cross-checked
  against the export file; disagreement → `ScoreRefused` (B8). An export with no manifest gets
  `"split": {"source": "unrecorded"}`, and the score proceeds.
- `metrics.score_models` splits `kept` (already audit-filtered) by `str(item.facts["cell"]["scenario"])`
  through the existing `_by_scenario` grouping and calls `headline()` per side:
  `{"all": …, "audited": …, "dev": …, "holdout": …, "slices": …}`. The audited subset is unchanged
  and un-split — it answers "is the declared truth right", not "did tuning leak".
- `comparison()` runs per split, returning `{"all": [...], "dev": [...], "holdout": [...]}`, each
  list in the current shape. Dev is where the OD-26 selection rule is applied; holdout is not a
  selection gate and the report says the rule is not applied there.

Because the holdout holds no benign items, its S2 leg runs over an empty population. The existing
conventions already make that honest, and this design uses them rather than adding a special case:
`s_metrics`' denominator is 0 → rate `None`, `wilson_interval(0, 0)` is the full-width `(0.0, 1.0)`
("no data is NOT a 0% rate"), `cell()` flags `insufficient`, and `cluster_bootstrap` returns
`point_pct: None` with `ci_pct: [0, 100]`. The renderer prints `—` for those, with the reason.

## §5 Report: label every number, hide nothing, show no holdout stills

`synthbench/score/report.py`:

- **Run identity** gains a `Split` row: `splits.json sha256 …; seed …; holdout 6 scenarios / 64
incident items; dev 386 (209 benign)`, or `unrecorded — this export predates ISS-016`.
- A new section directly after Run identity, **`## What this split can and cannot say`**, printed
  only when a split is recorded: the two bound-setting properties from _The realized draw_ (n=64 is
  a leak detector; the holdout is suspicious-heavy by the draw's luck), the note that S2 is measured
  on dev by design, and one line stating the tuning rule — holdout stills and failures are excluded
  from the gallery, so a prompt tuned on this run's dev material has not seen them.
- Headline tables: `## Headline: every scored item` keeps its current shape; then
  `## Headline: dev split (tuning may see this)` and `## Headline: holdout split (tuning never saw this)`,
  both rendered by the existing `_headline` helper so dev and holdout columns are literally the same
  columns as the all-items table. Where a holdout cell has no denominator (S2), the cell prints
  `—` and the section footnote states `no benign items in the holdout: S2 is measured on dev, which
holds all 209 benign items by design (ISS-016 B1)`.
- **Comparison** is printed per split: dev first, labelled as where the OD-26 rule decides; holdout
  second, labelled as the generalization check with the rule not applied. The closing
  spans-zero note (ISS-043) is unchanged and applies to both.
- **Slices.** The existing all-items slice block is unchanged, so today's numbers keep their meaning
  and stay comparable with the frozen records. One addition: a **`### Scenario slice, dev only`**
  table computed on dev rows, placed under the dev headline. It exists because the scenario slice is
  exactly what a tuner reads to pick which scenarios to fix — it is the per-scenario failure detail
  B7 keeps off the tuning surface, in table form. The other slice dimensions (lighting, weather,
  property, camera, zone, artifacts, group) stay all-items: they are aggregates the report already
  prints, they are shared across the arms rather than the unit of the split, and suppressing them
  would cost comparability for no leakage protection.
- `html()` gains the split as an argument and filters rows to dev **twice**: by scenario arm, and
  by a `split` field it refuses to render without (a row carrying `split: unrecorded` renders,
  because that gallery predates the split; a row that simply lacks the field raises). A holdout
  still reaching the gallery is a defect, not a cosmetic slip, so the check is written to fail
  loudly rather than to filter quietly.
- `results.jsonl` gains `"split": "dev" | "holdout" | "unrecorded"` per row — the file is the tuning
  input downstream tools read, so the arm belongs in the row, not only in the header.

## §6 Code layout

| File                                 | Change                                                                                                                                 |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| `synthbench/export/vss.py`           | `SPLIT_FILE`, `SPLIT_SEEDS`, `draw_split`, manifest document, canonical bytes, `write_split`, `read_split` (pure; no `backend` import) |
| `synthbench/commands/export.py`      | write the manifest after the sets; print roster, counts, sha256; `ExportConflict` on a different manifest                              |
| `backend/evaluation/eval_store.py`   | `splits` table, `put_split`, `get_split`                                                                                               |
| `backend/evaluation/label_import.py` | unchanged (the importer's item rows are untouched); the split is recorded by the caller                                                |
| `synthbench/run/replay.py`           | import step records the split; `run.json` gains `split_sha256` + roster                                                                |
| `synthbench/score/scoring.py`        | `SCORE_VERSION = 3`; identity `split`; export/store cross-check; arm rows onto results                                                 |
| `synthbench/score/metrics.py`        | `score_models` per-side headlines; `comparison` per split                                                                              |
| `synthbench/score/report.py`         | Split identity row; the can/cannot-say section; dev + holdout headline and comparison tables; gallery filter                           |

## §7 Testing and acceptance

TDD: each test written and watched to fail first.

| Test                                               | Pins                                                                                                                                                                                            |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `draw_split` on the 19 exported incident scenarios | recomputes exactly the six names above, in the recorded order, and the 64/177/209 counts. The seed string is asserted literally, so a silent edit fails here.                                   |
| `draw_split` determinism                           | same inputs → same bytes; changing the seed string changes the roster; the roster is invariant to input order                                                                                   |
| benign scenarios never drawn                       | a corpus of only benign scenarios yields `holdout: []` and an empty-population holdout, not a crash                                                                                             |
| the two §2 edges                                   | a corpus version absent from `SPLIT_SEEDS` exports with no manifest and that line on stdout; a 1-incident-scenario arm draws `holdout_k: 0`, a 2-scenario arm draws 1 — both keep dev non-empty |
| `splits.json` canonical bytes                      | stable under dict insertion order; `write_split` is create-once and raises `ExportConflict` on different content                                                                                |
| store `put_split`                                  | identical re-put is a no-op; a changed arm for one scenario raises; a different `manifest_sha256` raises                                                                                        |
| replay with a split-carrying export                | store holds 31 scenario rows; `run.json` carries `split_sha256` and the roster                                                                                                                  |
| replay against a store holding a different roster  | exit 2 `_ImportRefused`, message names the store and the fix                                                                                                                                    |
| `score` on a pre-split export (no `splits.json`)   | byte-for-byte the metrics and report of today, `split.source == "unrecorded"` (snapshot-pinned)                                                                                                 |
| `score` with a split                               | model block has `all`/`dev`/`holdout`; `holdout` S2 is the empty-population shape; dev+holdout item counts sum to `all`                                                                         |
| `score` where store and export disagree            | `ScoreRefused`, exit 2                                                                                                                                                                          |
| `report.md`                                        | prints the Split row, the can/cannot-say section, the labelled dev and holdout tables, and the `—` with its reason for holdout S2                                                               |
| `report.html`                                      | contains no holdout event id or still path; a dev row missing its `split` field raises; an `unrecorded` row still renders                                                                       |
| `results.jsonl`                                    | every row carries `split`; counts per arm match the manifest                                                                                                                                    |
| frozen P5a and sweep records re-read               | the existing snapshot tests stay green unchanged                                                                                                                                                |

Acceptance against ISS-016's acceptance text: _"fixed, hash-pinned split stratified by scenario,
recorded in the eval store"_ — drawn by published hash order, keyed and stratified within the
incident arm, recorded in the export, the store and the report. _"chosen with the power limits in
mind"_ — S2's benign arm stays intact in dev; the holdout is scenario-level so its power limit is
stated in the report rather than assumed away. _"Tuning uses dev only"_ — enforced by the gallery
and `results.jsonl`, not by a comment. _"the holdout is replayed k times per candidate, not once,
with the spread reported"_ — settled by the register's 2026-10-03 update: the assess call is greedy
(ISS-078 `done`) and the conditions line records the sampling choice (ISS-043), so one replay plus
the determinism the conditions line makes inspectable; `noise_floor()` in
`backend/evaluation/cluster_stats.py` is what reports a spread when reruns do exist. _"`report.md`
labels dev and holdout numbers"_ — §5.

## Register bookkeeping on closure

ISS-016 → `done` with a closure note naming the draw and this file. ISS-008 is unblocked (ISS-016
was its prerequisite). ISS-086's rubric arm gains a note: its prompt tuning runs on dev, or reports
itself as exploratory. ISS-045's conditions/sampling terms are already met. Derived Dashboard
counts (status, P1 open, severity total, actor, kind, area) and the README pins move with the flip;
`scripts/check-vss-docs-currency.py` must print ok.

This split does **not** constrain the OD-15 pre-screen: reading all 450 stills for label correctness
is not tuning, and corrected labels apply to both arms. What must never touch the holdout are
prompt, threshold and specialist-context changes derived from reading it.

## Risks

- **Scenario-type generalization is a hard test.** The holdout asks dev-tuned prompts to work on
  scenario types never seen. A prompt that only sharpens existing scenarios will look bad on the
  holdout while genuinely improving the product. The report frames this as a gap to interpret, not a
  verdict to obey — the bars stay the bars, and they are read on dev plus the full 450.
- **n=64 is small, and clustered.** Stated in the report wherever a holdout number prints.
- **The draw is suspicious-heavy by luck.** Stated, with the consequence (holdout reads low) named.
- **Six is a small universe of candidate holdouts.** B3's published hash order removes selection bias
  but not the fact that 19 scenarios is few. The honest fix is more scenarios, which is ISS-074/082
  territory, not this design's.
- **A split recorded in three places can drift.** The export file is authoritative, the store copy is
  checked against it at both import and score, and any disagreement stops with exit 2.
- **A tuner can still defeat the holdout** by reading the holdout aggregates in `report.md` and
  iterating against them. Aggregates are published deliberately — hiding them would make the
  generalization check unauditable. The line drawn is per-item detail and imagery, which is what
  actually overfits.

## Out of scope

Prompt and specialist tuning itself (ISS-086, ISS-024, ISS-053); the regression set as a third arm;
corpus growth (more scenarios, more lighting per scenario — the real power fix); re-scoring the
frozen P5a and sweep records under the split; anything about the OD-15 audit's label corrections.

## Rejected

- **A 30% item-level split within every scenario** (the plain reading of ISS-016's text). Dev would
  retain 70% of every scenario, so the artifacts ISS-043 showed cluster would be visible to tuning;
  the holdout would measure partial memorization, not generalization.
- **A benign holdout to check S2 too.** ~63 benign items cannot resolve a 5% bar (Wilson upper
  ≈5.7% at 0/63), and moving hard-negative scenarios to holdout blinds dev to the S2 lever entirely.
- **Stratified-by-group or owner-visible draws.** A second sampling stage for a nominal gain in
  19-scenario universe; the unstratified hash draw landed balanced anyway, and B4 records that as
  luck to be read, not design to be trusted.
- **Per-item split assignment** (a `split` field on each item, or a second export). Items and their
  store fingerprints stay untouched; scenario is the unit that carries both the correlation and the
  label purity, so item-level bookkeeping adds drift risk with no measurement gain.
- **A hardcoded holdout roster in the code.** It would read faster but could not be re-derived, and
  the whole point of B3 is that the roster is a consequence of three published strings.
- **Re-splitting per candidate** (a rotating cross-validation). Every rotation makes each
  candidate's holdout number comparable to nobody else's; a frozen roster is what makes releases
  comparable.
