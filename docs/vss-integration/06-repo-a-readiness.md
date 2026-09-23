# Repo A Readiness: What Must Be Fixed Before Any Swap

> **Errata (2026-09-23):** E5, E7, E25, E26 in [`11-errata-2026-09-23.md`](11-errata-2026-09-23.md) correct claims in this document. The original text is kept as the record; read those entries before relying on it. Current design: [`2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md).

Findings from a 14-agent assessment on 2026-09-18, **independently re-verified** where marked
**[V]**. This document is about _this repository_, not VSS.

Claims carry an extra marker here: **[A]** = agent-reported, plausible, **not independently
verified**. Do not act on an **[A]** without checking it.

> **Retirement note — 2026-09-21 [V].** All four §1 blockers were measured CLOSED on `main`
> (verified against `origin/main`; the landing commits are named per section below). The
> instrument-class findings — a coverage merge whose glob could never match, frontend shards
> running without `--coverage`, an anti-rot argument that omitted the tier it was supposed to
> police — were real, landed in CI, and are fixed and re-verified at each cited shape. Sections
> 1.1–1.4 are kept as the measurement of record, annotated with the fix. The open program items
> are §1.5 (WP4.4's done-when drift and un-cashed deletion records), §1.6 (the in-process seam
> import), and §1.7 (the frontend blast radius). This doc stays as the assessment of record; the
> blocker list is retired.

## The headline

The test-platform program delivered real, durable value — and it is shipping a lying signal on
`main` of exactly the kind it was chartered to eliminate.

> **Status 2026-09-21 [V]:** this sentence was accurate when written and is now **stale.** The
> lying signal was the four §1 defects — each one a gate that could never see what it claimed to
> enforce. They were closed by `#6559` (backend + frontend coverage instruments, 2026-09-19),
> `#6560` (`ai/` collection, 2026-09-19), `#6562` (dead modules deleted, 2026-09-19), `#6566`
> (mutation-history bootstrap, 2026-09-19) and `#6589` (WP2.3 frontend floors made blocking,
> 2026-09-20), all re-verified on `main` 2026-09-21. The paragraph after the quote in §1.1 —
> _"the 85% floor is enforced by zero CI gates"_ — no longer holds: the floor now has a real
> merged measurement behind it and a strict drop-diff gate in front of it.

## 1. Verified gaps

> **All four blockers below were verified CLOSED on `main` 2026-09-21 [V].** Each section keeps
> its original finding as the measurement of record, with the fix commit and the re-verified
> shape annotated.

### 1.1 Backend coverage is computed nowhere in CI **[V]** — **CLOSED 2026-09-19 (#6559), re-verified 2026-09-21 [V]**

_Original finding:_ Unit shards emit `--cov-report=xml:coverage-unit-shard-N.xml` and upload only
that XML. The merge job at `.github/workflows/ci.yml:436` tested:

```bash
if compgen -G ".coverage.*" > /dev/null 2>&1; then
    uv run coverage combine --data-file=.coverage
    ...
    echo "merged=true" >> "$GITHUB_OUTPUT"      # :455
else
    touch .coverage                              # :459
```

A file named `coverage-unit-shard-N.xml` **cannot** match a glob requiring a literal leading dot.
Every run takes the `touch .coverage` branch. The file's own comment at `:443` states _"merged=true
is set exclusively on this path"_ — and that path never executes.

_Consequence as written:_ "the 85% floor in `pyproject.toml` is enforced by zero CI gates," and
WP0.9's coverage-diff gate honestly logged a skip, then reported "All test coverage checks
passed." That was the lying signal the headline named. It is no longer the state of the repo.

_Fix, re-verified at `origin/main` [V]:_ shards set `COVERAGE_FILE: coverage-unit-shard-N-pyX.Y.dat`
(`ci.yml:422`) and upload the `.dat` (`:498`); the merge job now tests
`compgen -G "coverage-reports/*.dat"` and combines real data files (`ci.yml:561`). The
merged path publishes `coverage-baseline.json` from real merged data (line-split json added by
WP2.2), and `check-test-coverage-gate.py` enforces a strict `current < base` **fail** on that
baseline. One honest annotation to the original consequence: per ruling A7.1, `fail_under = 85`
is the diff gate's relative baseline, not an absolute floor — the executed absolute backend floor
is 80% on combined unit+integration (`validate.sh --fail-under=80`, mirrored in
`nightly-full-gate.yml`). The floor now lives where a real measurement can fail it.

### 1.2 Frontend shards run without coverage at all **[V]** — **CLOSED (#6559 measured; #6589/WP2.3 enforcing), re-verified 2026-09-21 [V]**

_Original finding:_ `ci.yml` invoked `npx vitest run --shard=N/8` with **no `--coverage` flag**.
Nothing was produced, so the merge merged nothing and the 83/77/81/84 thresholds had no enforcer.

Measured actuals reported as 79.97 / 74.60 / 78.44 / 80.93 — **below every threshold** **[A]**.

_Fix, re-verified at `origin/main` [V]:_ the merge-tier shards now run
`--coverage --coverage.reporter=json --coverage.reportsDirectory=coverage/shard-N` with thresholds
zeroed per-shard (`ci.yml:1798-1801` — the "do NOT add `--coverage`" note that used to sit here
was itself corrected: per-shard thresholds would fail on partial data, so enforcement was moved,
not removed). A stdlib-only Node merger (`frontend/scripts/merge-shard-coverage.mjs`, with its own
`node --test` suite run in-job) combines the shard reports, and since WP2.3 it **enforces** the
floors — at their MEASURED values 80 / 74.6 / 78.4 / 80.9, replacing the aspirational
83/77/81/84 that never held — when every shard passed (`ci.yml:1974-1994`). Partial data gets a
warning, never a coverage-costume verdict; the shard summary job still reddens that case with the
true reason. The original **[A]** measured numbers are now the floors themselves, which is the
honest version of the same fact.

### 1.3 The `ai/` tier is dark **[V]** — **CLOSED 2026-09-19 (#6560), re-verified 2026-09-21 [V]**

_Original finding:_ the anti-rot gate was invoked as `check-test-collection.py backend frontend` —
**`ai` was not an argument.** `387 tests collected, 19 errors`, including
`ModuleNotFoundError: No module named 'ai.yolo26'`. Several errors were real packaging defects
(sibling `model.py` files across model dirs, missing `__init__.py`). Agent-reported total defined:
1,697 test functions **[A]**, i.e. most never ran.

_Fix, re-verified at `origin/main` [V]:_ `ci.yml:108` invokes
`check-test-collection.py backend frontend ai`. The packaging defects were real and Phase 6
(WP6.1–6.5, #6560) repaired them — the flat-module slot hygiene in `ai/conftest.py` is the
landed shape. The section's warning — _"you cannot claim a swap preserved behavior in the tier
being swapped, when that tier's tests never executed"_ — stands as the reason this fix mattered;
it no longer describes `main`.

### 1.4 Two dead modules were just granted protection **[V]** — **CLOSED 2026-09-19 (#6562), re-verified 2026-09-21 [V]**

_Original finding:_

| Module                    | Evidence                                                                                                                                              |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `job_state_service.py`    | `grep -rn job_state_service backend/ --include=*.py \| grep -v /tests/` → **nothing**                                                                 |
| `scene_change_service.py` | Only importer is the `backend/services/__init__.py:318` re-export. The live path is `scene_change_detector`, imported at `enrichment_pipeline.py:141` |

WP4.4 had produced surviving-mutant records for both — converting ~577 lines of unreferenced
production code into **protected** dead code under the "no deletion without a surviving mutant
record" rule.

_Fix, re-verified at `origin/main` [V]:_ both files were deleted in `eada4ba9` (#6562) —
`git ls-tree origin/main` returns neither. The protection problem resolved by removal of the
protected thing, which is what the reachability filter in §3 was written to make routine.

### 1.5 WP4.4 is moving away from its own done-when **[V]** — **PARTIALLY CLOSED 2026-09-19 (#6566); the deletion-record half remains open**

_Original finding:_

```
git diff --numstat main...origin/feat/wp44-closeout -- backend/tests
  +3596 / -3   net +3593 lines
```

Plan line 560: _"**Done when:** test line count and wall clock are down, with coverage and mutation
score not down."_

Also: `.github/mutation-history.json` **does not exist on main** **[V]** — the artifact the tier
re-run is meant to append to has never been created.

_Closed by `ebf5106b` (#6566, 2026-09-19) [V]:_ the history artifact now exists on `main` and
carries the first honest baseline (54.0% on the then-narrowed scope; the full-tree program is
re-baselining now and its close-out supersedes the number, not the mechanism).

_Still open [V]:_ the done-when drift. The close-out PR (#6556) was **closed unmerged**
2026-09-19T14:28Z and its branch (`feat/wp44-closeout`) never landed — 25 of its 26
survivor dossiers are absent from `main` (only `container_discovery` arrived, via #6555).
The triage corpus itself — the TEST-GAP/EQUIVALENT/LOW-VALUE classification records under
`.wp25-feed/` — **is** on `main` (added by #6552, #6555; relocated to `archive/wp25-feed/` by
`#6637` on 2026-09-21), so the licensed deletion candidates
are landable; nobody has spent the day §3 recommended for it. This is now a scheduled-work
item (WP4.4 survivor-triage dispatch on the fresh full-tree census), not a discovery.

### 1.6 No contract at the backend↔AI seam **[A]** — **PARTIALLY CLOSED (#6562); the import-the-server half remains open**

An adversarial pass corrected an earlier overstatement: `test_detector_client.py` _does_ pin the
real server keys (74 tests pass, clamping branch exercised). The accurate defect is structural —
**zero tests import `ai.*`**, so if a server renames a key tomorrow, both halves stay green
independently.

_Partial fix [V]:_ #6562 landed the 38-op generated contract with golden payload snapshots and a
CI drift gate (`backend/tests/contracts/ai_providers/golden/`). But the runtime half of the
original defect survives: the registry test documents the dependency-direction problem in its own
docstring and imports only `backend.ai_contract` — a rename inside `ai/yolo26/model.py`'s pydantic
models is still caught by regeneration drift in CI, not by an import-bound test that would go red
on its own. The seam fixture that **imports the server's models** remains the highest-value
missing artifact for a pipeline swap.

### 1.7 The frontend was never classified **[A]** — **OPEN**

345,148 non-test LOC, ≥62,435 in pipeline-shaped components (`events` 15,354, `zones` 12,623,
`face-recognition` 7,081, `ai` 6,629). The coupling is **not** `risk_score` — it is the enrichment
child-object model: pose keypoints, demographics, re-ID galleries, plate reads. RT-VLM emits prose
plus a severity; there is no skeleton to render. **Blast radius plausibly exceeds the backend's and
is unmeasured.**

## 2. The durability split

**Survives a swap — keep investing:** all of Phases 0-3; `container_orchestrator.py` (589 lines,
zero AI tokens, takes discovery as a constructor dependency); `go2rtc_client.py`;
`event_service.py`; `media.py` (its `clip_generator` is ffmpeg video clips — a name false-positive
on CLIP); the auth/audit/persistence/jobs/export/websocket families; and the single-GPU resilience
layer (`degradation_manager.py`, `gpu_monitor`, `circuit_breaker`, `retry_handler`).

**Perishable:** the prompt stack; all 22 in-backend `*_loader.py` torch loaders plus
`model_zoo.py`; the six httpx AI clients; `prompt_auto_tuner.py` (only callers are
`nemotron_analyzer.py:2516` and `nemotron_streaming.py:228`); the six enrichment child tables.

**Caveat, applied honestly.** The perishability discount has been applied asymmetrically. The swap
is unfunded, unapproved, legally fenced at the productization end, and hardware-blocked — the only
GPU here is an aarch64 GB300; the target is x86 GeForce. If P(swap completes as scoped this year)
is ~0.5, "perishable" means "expected life of quarters," which is a **discount, not a veto.**

## 2a. The in-process AI tier is OUT of HTTP-conformance scope — declared, with what that leaves unguarded (WP9.2)

**The declaration, in those words: the in-process AI tier is out of scope of
the HTTP-level AI conformance program (`WP8.*`), and the VSS swap question
for this tier is a SEPARATE work package, not part of the provider-swap
contract.** This is the WP9.2 scope call from
`docs/superpowers/plans/2026-09-19-swap-readiness-72h.md`; the RULING "does
the VSS swap cover the in-process tier?" stays PARKED for the owner — this
section does not decide it, it bounds what the current suites can see so the
ruling is made against a measured surface, not a guess.

**Counted module list, re-verified at HEAD `a140d244` 2026-09-20 [V]**
(commands in-line; census first taken at `a8c25c5e`, numbers unchanged):

- `find backend -name "*_loader.py" -not -path "*/tests/*"` → **22** modules.
  Of those, grepping for `import torch|transformers|ultralytics` (either
  form) → **21** pull a heavyweight framework into the BACKEND process; the
  one non-importer is `backend/services/fast_alpr_loader.py`.
- Eager/lazy split matters for what "invisible" means: `stgcn_loader.py` and
  `zero_dce_loader.py` import at MODULE level (the framework loads at
  backend import time); the other 19 defer the framework import into
  functions — invisible until warmed, then equally unguarded at runtime.
- Four more in-process detectors import their own models directly:
  `backend/services/face_detector.py` (375 lines), `plate_detector.py`
  (322), `ocr_service.py` (416), `scene_ocr_service.py` (889).
- The DI wrappers ride on top: `backend/services/ai_services.py:36-350`
  (first wrapper class `FaceDetectorService` at :36; the plan's span cited
  `ai_services.py:36-350` — verified, and it lives in `services/`, not
  `api/dependencies/` as an earlier cite implied).
- `model_zoo.py` (930 lines) is the shared weight-resolver underneath [V:
  file present, counted above].

**What remains unguarded, concretely.** Every WP8.\* suite and the WP9.1
parity checker speak HTTP or read deployed-surface ASTs
(`scripts/check-ai-provider-parity.py` walks gateway adapters, native
`model.py` files and the six httpx callers): a provider swapped IN or OUT
through them changes a socket answer. The tier above has NO socket — a VSS
swap could replace the weights, the preprocessing, or the whole loader
implementation and every one of those suites would stay green while
`is_minor` flipped on every child. There is no fake, no contract snapshot,
and no golden divergence covering a function called as
`await loader.run(frame)` inside the backend process. That is the accepted
cost of this scope call, stated so nobody discovers the second project
mid-swap: **the swap is two known projects** — (1) the HTTP provider tier,
contracted and faked, and (2) the in-process tier, which needs its own
declaration, its own inventory (the counts above are its starting census),
and eventually its own suite BEFORE any VSS decision consumes it.

**Recommendation to the parked ruling (not the ruling itself):** when the
owner answers "does the VSS swap cover the in-process tier?", treat 21+4+DI
as the priced surface; do not let "provider conformance is green" be read
as "the AI pipeline is swappable" — this section exists to make that
misreading impossible.

## 3. Recommendation on WP4.4's 2-3 day request — **SUPERSEDED 2026-09-21 [V]**

The recommendation's vehicle is gone: **PR #6556 was closed unmerged on 2026-09-19**, so "merge
#6556 after adjudicating the skip" is void — and re-verification 2026-09-21 [V] found its
substance did **not** fully re-land:

- The triage corpus **is** on `main`: `.wp25-feed/` (queue index, classification records,
  triage evidence — 2 872 paths) arrived via #6552/#6555 on 2026-09-18/19; #6637 moved it to
  `archive/wp25-feed/` on 2026-09-21. Its own handoff
  records the split as TEST-GAP ~67 / EQUIVALENT ~22 / LOW-VALUE ~10 (the 62/23/15 above was
  the earlier wave's figure) with ~220 drafted items UNVERIFIED.
- What did **not** land: #6556's census perf fix (probes `-n 0` + module sharding, 3.5-4.5 h →
  ~25 min/module) and 25 of its 26 survivor dossiers — `.wp44-fanout.py` on `main` (since #6637
  at `archive/.wp44-fanout.py`, formerly `scripts/.wp44-fanout.py`) is the pre-perf version; only
  `container_discovery`'s dossier arrived (#6555). The branch
  `feat/wp44-closeout` still exists remotely and carries them; the next WP4.4 day should
  re-land the runner change, not re-derive it.
- _"Do not re-baseline the ratchet to clear the red"_ — kept; this became standing ruling R-1
  (floors at the MEASURED value; enforcement lands in one commit).
- The **"spend it deleting, not writing"** day remains unfunded: zero of the licensed
  EQUIVALENT/LOW-VALUE records has been cashed as of 2026-09-21 [V] (§1.5; commit-body grep for
  EQUIVALENT/LOW-VALUE licensing since 2026-09-18 finds only the close-out doc itself). The
  hard exclusions below still price that work.

**Hard exclusions (unchanged):** no census on `container_discovery` (~30% of the file is a
hardcoded AI port table — lift it into config instead, which retires the debt _and_ converts a
REWRITTEN module to SURVIVES), any `*_loader` module, the six httpx AI clients, or
`prompts`/`prompt_service`/`llm_reasoning`/`nemotron_streaming`/`enrichment_pipeline`/`pipeline_workers`/`scene_ocr_service`.

## 4. The reframed experiment

The single-run falsification in [`04-fp4-and-deployment.md`](04-fp4-and-deployment.md) §6 is still
the right _technical_ check, but it cannot carry the product decision. **A red result is
informative; a green result is nearly uninformative and maximally motivating.** Do not let a green
license Step 1.

Do this instead, in order:

1. **Hour 1 — talk to the VSS team.** Highest information per hour in the entire plan. Three
   questions: (a) is Cosmos3 Nano dense ~8B or the Qwen3VLMoe 30B-A3B variant — every VRAM number
   roughly triples if it is the MoE; (b) do the x86 NIM manifests carry a GeForce allow-list;
   (c) what do the deliberately-empty `RTX4090_TESTS` tables encode — a decision, or a gap?
   Also: if the endgame is collaboration, first contact should not be "I already built a fork."
2. **Hour 1 — send the consumer-GPU procurement request.** Longest lead time in the plan, five
   minutes of effort, gates every Step-3 claim.
3. **Day 1-2 — a salience demo, labelled a demo, not a falsification.** Two inputs nobody proposed:
   - **A still JPEG.** This repo's actual ingest is **FTP stills** — `camera.py:126` and `:170`
     default to `IngestionMode.FTP` **[V]**, and there is no RTSP service in
     `docker-compose.prod.yml` **[V]**. RT-VLM accepts `image` mode.
   - **Fifty boring frames** — the cat, the shadow, rain on the lens — plus five real incidents.
     Home security is a false-positive suppression problem; VSS is a description problem. Demand
     this repo's Event JSON via `response_format: json_schema`. Note `risk_level` is lowercase here
     and uppercase in VSS's `AlertSeverity` — near-identical, not character-identical **[A]**.

## 5. Honest uncertainties — verify, do not infer **[A]**

- **VSS is a GTC-cadence blueprint, not a platform.** Four top-level restructurings in 15 months;
  `services/rtvi` went 9 files → 290 between v3.1.0 and v3.2.0; `docs/release-notes.mdx` states
  2.x/3.0/3.1 images are **removed from NGC on 2026-09-30**. No API-stability or deprecation policy
  exists in the repo. Budget version pinning, mirroring images into your own registry, and a
  per-release re-integration tax.
- **Licensing.** Source is Apache-2.0, but the _microservices_ ship under an **Evaluation** license;
  `README.md:99` requires AI Enterprise to self-host NIM; SLA §8.9 bars publishing benchmark data.
  The Product-Specific Terms that decide redistribution are **not in the repo.** Legal question.
- **Biometrics.** This repo stores 512-dim ArcFace templates and ALPR plate text with **no retention
  clock** (`retention_days` covers events/detections only), no consent record, no erasure path.
  Defensible on a 127.0.0.1 single-user box; BIPA/CUBI/GDPR territory as a shipped consumer product
  where the subjects are non-consenting visitors. **This is a product-shape decision that must
  precede building.**

## Bottom line

The four §1 blockers are closed and re-verified (2026-09-21, commits per section) — the
instrument fixes this document asked for have landed. What the freed budget should now go to,
in order:

1. **§1.6's import-bound seam fixture** — the one test artifact that most directly protects a
   pipeline swap, and the only §1 item whose core defect still exists.
2. **§1.5's deletion-record cashing** — the corpus is on `main` (quarantined at
   `archive/wp25-feed/` by #6637); one day with the
   mode inverted per §3, still unspent.
3. **§1.7's frontend classification** — the blast radius that plausibly exceeds the backend's is
   still unmeasured.

Make the VSS team call before the fork decision, not after.

## Related

- [`05-hardware-profiles.md`](05-hardware-profiles.md) — the tiering strategy
- [`03-open-questions.md`](03-open-questions.md) — the open register
- [`docs/plans/2026-09-12-context-map-doc-updates.md`](../plans/2026-09-12-context-map-doc-updates.md) — the program ledger
