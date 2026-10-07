# Synthbench ISS-038: the blind clip audit instrument — Design

- **Date:** 2026-10-07
- **Status:** **design not yet reviewed by the owner.** It was written beside the code under the
  standing campaign instruction to keep working the funded phases, not after a chat design the
  owner approved; nothing in this file has been agreed to. The code and its tests are on branch
  `clip-audit-instrument` for review, and the owner's read of this document is the gate on the
  next campaign step (the audit run itself, Phase 3), not on this one.
- **Register:** `docs/vss-integration/17-action-plan.md` ISS-038 (P2, risk, actor
  `owner-decision`, status `open`). It stays `open` until the owner's audit has actually run;
  shipping the instrument is not running it. Related: ISS-044/OD-15 (the audit method this
  reuses), ISS-093 (clip supply), ISS-003 and the pre-registration it gates.
- **Parent specs:** `docs/superpowers/specs/2026-09-30-synthbench-h3-clips-design.md` (what a
  clip is: C5 conditions carry through from the source still, C13 leaves the audit unowned),
  `docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` (§4 the stills audit
  this mirrors, §7.1 the import rule that places the statistics), and the campaign's
  pre-registration `docs/research/2026-10-07-clip-measurement-prereg/README.md` (freezes F2 and
  F4, which decide the shape of the draw).

## Goal

Give the clip corpus the one thing ISS-038 says it lacks: an audit that puts an error bar on the
declared truth a clip inherits, and a disclosure of who survived rendering. Until it exists,
every clip number is declared-truth with no measured label noise and no correction for the fact
that H3 fails crossing motion at elevated rates — the shape of the failure is recorded in
`docs/synthbench/h3-prompt-notes.md` (the runner crossings 0/13 ready, working-in-place 24/26).

This is the instrument, not the audit. It draws the set, serves the owner a blind page, records
the answers, and prints what the answers imply. The owner runs it in Phase 3; no clip number
exists before that.

## What the corpus decides (measured, not assumed)

| Fact                                                    | Value                                            |
| ------------------------------------------------------- | ------------------------------------------------ |
| Ready clips in `clips-1`, latest status per `event_id`  | 164 of 459 (2026-10-03 census)                   |
| Ready **incident** clips                                | **17** — entirely the time-revealed A-group      |
| The 205-clip prompted backlog                           | weapon/threat-heavy, of which 9 suspicious       |
| Measured incident yield per render attempt              | 17/59 = 29 % (prereg supply recount)             |
| Threat-group clips rendered at all                      | none                                             |
| Scenarios in the taxonomy (the blind pick list)         | 32                                               |
| Ready benign clips available to mirror against          | 144                                              |
| Crossing-motion failure recorded mid-round, 'seen once' | runner crossing 0/13, walker 4/9, in-place 24/26 |

Two of these decide the architecture. **Seventeen ready incidents** means a 60-clip stratified
incident sample is not available at the current supply, and pre-registration freeze **F4** already
ruled the better answer: the audited subset _is_ the measurement corpus, so the incident half of
the draw is a **census of ready incidents**, not a sample — every clip that could enter the
measurement gets audited, and a render window that makes more clips ready grows the draw for the
next round instead of reshuffling a half-audited one. **Zero threat clips rendered** is not this
instrument's problem to fix (that is ISS-093's supply ruling and Phase 2's render window), but it
is the reason the by-group clause of ISS-038's acceptance can only be satisfied after Phase 2 and
why the report labels its group slices by what they hold rather than assuming both.

## Decisions

| #   | Decision                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | **The page never reads a `spec.json`.** Its whole input is the write-once draw manifest, the ready attempt's `provenance.json` (for the mp4 path) and the mp4's bytes. A clip's frozen motion text names the scenario's props (`"the person works with a drill"` on a `power_tools_at_night` clip), which is the strongest leak available to an audit whose point is that the owner should name the scene cold. This is enforced by shape, not by care: `build_items` has no taxonomy parameter and a test greps the rendered page for the clip's own motion words. |
| A2  | **The scenario pick list is the whole taxonomy, 32 ids, identical for every clip.** A list that varies per clip would carry information about the clip; a fixed list carries none. The leak test therefore strips `<select>` blocks and separately pins the printed list against the sorted taxonomy ids with no per-clip `selected` attribute — a pre-selected option would be a leak the "motion words absent" grep cannot see.                                                                                                                                   |
| A3  | **Questions run motion → scene → prop → conditions → threat.** The prop question follows the scene pick and asks about the _auditor's_ pick, because after a blind pick the declared prop is not the item's truth — a mislabelled clip is exactly what the audit is for. A prop answer is bound to the scene pick standing when it was written; the binding lives only in the log's order and is reconstructed by `load_answers`.                                                                                                                                   |
| A4  | **The one declared fact shown is lighting and weather.** H3 carries them unchanged from the source still (clips design C5), so a disagreement is a clip defect rather than a label leak, and a clip that contradicts its own conditions has scene trouble anyway. They are copied onto the draw row so the page never needs the spec for them (A1 again).                                                                                                                                                                                                           |
| A5  | **Blind means v1's clause unamended** (ISS-044 v2/OD-15): the owner picks scenario and threat level from lists and sees no declared text. OD-15's machine pre-screen is _not_ implemented here — this instrument only pins its row shape (`ClipAuditFlagRow`) and accepts a flagged file through `--flagged`, so a future screen lands without touching the instrument.                                                                                                                                                                                             |
| A6  | **The draw is write-once** through `CorpusStore.write_new_bytes`, like every corpus file. An audit interrupted by a render window resumes the same set; a bigger draw is the next round's manifest, not an edit of this one. `sample` on a frozen round exits 1 and says so.                                                                                                                                                                                                                                                                                        |
| A7  | **The benign mirror is a seeded stratified draw sized to the incident count**, over `(group × intended motion)` strata using the stills audit's `allocate` (freeze F2). The motion axis is in the strata because that is where the bias lives; stratifying only on scenario and lighting would silently over-weight in-place clips.                                                                                                                                                                                                                                 |
| A8  | **The intended-motion class comes from a keyword classifier over the frozen motion text**, priority crossing > line-of-sight > in-place > other, using `h3-prompt-notes.md`'s own counted wordings. `MOTION_CLASSES` (…,"other") is disclosure vocabulary and `MOTION_CHOICES` (…,"barely-moving","unclear") is what a human is asked — the classifier's `other` is "no keyword family matched", counted out loud, never folded into a named class.                                                                                                                 |
| A9  | **Survivor rates are over decided clips only** (`ready` / `failed`); sampled, prompted, rendered-awaiting-triage and rerolled clips are `open`, excluded from the denominator and printed beside it. An open clip has survived nothing yet, so counting it either way would invent a rate. A class with nothing decided prints a note, never a 0/0.                                                                                                                                                                                                                 |
| A10 | **The statistics live in `synthbench/score/clip_audit_report.py`.** The Wilson interval is `backend/evaluation/s_metrics.py`'s and spec §7.1 lets only `score/` and `run/` import `backend`, so the command imports this module lazily and the generation-side commands never load it. `report()` is a pure function over already-read files, so the math is testable with no corpus and no socket.                                                                                                                                                                 |
| A11 | **The page is loopback-only and same-origin-checked.** `serve()` binds `127.0.0.1`; `POST /answer` additionally requires `Host` to be `127.0.0.1:<port>`/`localhost:<port>` and any sent `Origin` to be `http://` one of those. Loopback binding does not stop another page in the owner's browser from posting. Stills and clips are served by sample index, never by a path from the request.                                                                                                                                                                     |
| A12 | **The answer log is append-only and last-write-wins per (event, question)** — the stills audit's rule verbatim, so a corrected answer is a new line rather than an edit, and an interrupted audit loses nothing.                                                                                                                                                                                                                                                                                                                                                    |

## Shape

```
clip audit sample --round r [--flagged f]   -> rounds/r/audit-draw.jsonl   (write-once)
clip audit page   --round r [--port 8766]    -> reads manifest + provenance + mp4
                                             -> appends $SYNTHBENCH_ROOT/audits/<ver>/clip-r.jsonl
clip audit bias   --round r                  -> stdout only, reads everything, writes nothing
```

| File                                    | Role                                                                                   |
| --------------------------------------- | -------------------------------------------------------------------------------------- |
| `synthbench/contract/clip_audit.py`     | the three row kinds: draw, answer, pre-screen flag; `MOTION_CHOICES`, `THREAT_CHOICES` |
| `synthbench/audit/clip_sample.py`       | the classifier, the draw policy, the five questions                                    |
| `synthbench/audit/clip_page.py`         | `ClipAuditApp.handle(method, path, body, headers)` — the whole page, pure              |
| `synthbench/score/clip_audit_report.py` | `report(...)` — survivor rates, the two matrices, progress, the disclosures            |
| `synthbench/commands/clip_audit.py`     | argparse for the three steps plus the only code that touches the corpus for the page   |

`handle` is a method over an in-memory item list, tested without a socket exactly as the stills
audit page is; `serve` is its only socket.

## Testing

`backend/tests/unit/synthbench/` gains three files, 66 tests (`test_clip_audit.py` for the
contract rows and the sampler, `test_clip_audit_report.py` for the statistics,
`test_clip_audit_command.py` for the three steps end-to-end over a fixture round). Pinned
properties beyond the happy paths:

- **the leak grep** — a drawn clip's own motion words never appear in its page, with the
  `<select>` blocks stripped first and the pick list checked separately against the taxonomy.
- **prop staleness** — a prop answer written behind one scene pick is inert behind a propless
  pick and revives on return; only another prop answer moves the stamp; a never-asked prop
  leaves the four always-asked keys in charge of "answered".
- **census stability** — a clip that becomes ready after the freeze does not join a frozen draw,
  and the bias report's rates still move, because they are computed over the round, not the draw.
- **the matrices** count the owner's picks against the declaration and total answered clips only;
  an unanswered clip is absent, never a disagreement.
- `test_command_reference.py` pins the three new section headings and their option rows against
  argparse, and `test_import_rule.py` keeps the §7.1 boundary that A10 exists for.

Measured on the branch: the synthbench unit suite passes at 1131 tests; `ruff check`,
`ruff format --check` and `mypy` are clean over the changed files; prettier 3.2.4 is clean over
the touched markdown.

## Deliberately not here

- No machine pre-screen (OD-15 item 1): the owner authorizes that separately; only its row shape
  is pinned, so it lands without a redesign.
- No scripted H3 triplet renders — the owner's renderer window, and the ruled corpus is
  frame-sampled from existing mp4s, which the report discloses in its own words.
- No scoring, no export, no eval-store entry for clips. ISS-037's harness and ISS-033/ISS-005 do
  the multi-frame plumbing; this does the truth side, and no number crosses between them before
  Phase 3.
- No clip supply: 17 ready incidents is a Phase 2 question (ISS-093), and the report's honest
  wide intervals at small n are the point of printing them.
