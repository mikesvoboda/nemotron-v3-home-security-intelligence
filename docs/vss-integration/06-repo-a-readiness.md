# Repo A Readiness: What Must Be Fixed Before Any Swap

Findings from a 14-agent assessment on 2026-09-18, **independently re-verified** where marked
**[V]**. This document is about _this repository_, not VSS.

Claims carry an extra marker here: **[A]** = agent-reported, plausible, **not independently
verified**. Do not act on an **[A]** without checking it.

## The headline

The test-platform program delivered real, durable value — and it is shipping a lying signal on
`main` of exactly the kind it was chartered to eliminate.

## 1. Verified gaps

### 1.1 Backend coverage is computed nowhere in CI **[V]**

Unit shards emit `--cov-report=xml:coverage-unit-shard-N.xml` and upload only that XML. The merge
job at `.github/workflows/ci.yml:436` tests:

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

**Consequence: the 85% floor in `pyproject.toml` is enforced by zero CI gates.** WP0.9's
coverage-diff gate honestly logs a skip and then reports "All test coverage checks passed."

**Fix:** have shards emit and upload binary `.coverage.shard-N` data files instead of XML.
Estimated **hours**.

### 1.2 Frontend shards run without coverage at all **[V]**

`ci.yml:1411` and `:1444` invoke `npx vitest run --shard=${{ matrix.shard }}/8` with **no
`--coverage` flag**. Nothing is produced, so the merge merges nothing and the 83/77/81/84
thresholds have no enforcer.

Measured actuals reported as 79.97 / 74.60 / 78.44 / 80.93 — **below every threshold** **[A]**.

### 1.3 The `ai/` tier is dark **[V]**

The anti-rot gate is invoked as `check-test-collection.py backend frontend` (`ci.yml:93`) —
**`ai` is not an argument.** Reality:

```
387 tests collected, 19 errors in 3.08s
ERROR ai/yolo26/tests - ModuleNotFoundError: No module named 'ai.yolo26'; 'ai' is not a package
```

Several errors are real packaging defects (sibling `model.py` files across model dirs, missing
`__init__.py`). Agent-reported total defined: 1,697 test functions **[A]**, i.e. most never run.

**You cannot claim a swap preserved behavior in the tier being swapped, when that tier's tests
never executed.** This is the single highest-value repair for the VSS plan.

### 1.4 Two dead modules were just granted protection **[V]**

| Module                    | Evidence                                                                                                                                              |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `job_state_service.py`    | `grep -rn job_state_service backend/ --include=*.py \| grep -v /tests/` → **nothing**                                                                 |
| `scene_change_service.py` | Only importer is the `backend/services/__init__.py:318` re-export. The live path is `scene_change_detector`, imported at `enrichment_pipeline.py:141` |

WP4.4 produced surviving-mutant records for both. Under its own _"no deletion without a surviving
mutant record"_ rule, that converts ~577 lines of unreferenced production code into **protected**
dead code. Strip those records or delete the modules before merging.

### 1.5 WP4.4 is moving away from its own done-when **[V]**

```
git diff --numstat main...origin/feat/wp44-closeout -- backend/tests
  +3596 / -3   net +3593 lines
```

Plan line 560: _"**Done when:** test line count and wall clock are down, with coverage and mutation
score not down."_

Also: `.github/mutation-history.json` **does not exist on main** **[V]** — the artifact the tier
re-run is meant to append to has never been created.

### 1.6 No contract at the backend↔AI seam **[A]**

An adversarial pass corrected an earlier overstatement: `test_detector_client.py` _does_ pin the
real server keys (74 tests pass, clamping branch exercised). The accurate defect is structural —
**zero tests import `ai.*`**, so if a server renames a key tomorrow, both halves stay green
independently.

**Fix:** generate one golden-payload fixture from `ai/yolo26/model.py`'s pydantic models and import
it from both sides. This is the single test artifact that most directly protects a pipeline swap.

### 1.7 The frontend was never classified **[A]**

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

## 3. Recommendation on WP4.4's 2-3 day request

**Merge PR #6556**, after adjudicating its one blocking suppression. Ten of its fourteen product
test files land on modules that survive any swap; it carries the census perf fix (3.5-4.5 h → ~25
min per module); and the `.wp25-feed/` triage corpus (122 modules classified TEST-GAP 62% /
EQUIVALENT 23% / LOW-VALUE 15%) exists **only** on that branch.

> **Do not re-baseline the ratchet to clear the red.** That trades Phase 1's integrity for Phase
> 4's slice. Register the skip with an owner and expiry.

**Decline further kill-test writing selected by survivor count.** At 14 modules/week, 2-3 days
buys 4-6 of 122 remaining modules — and the queue is ordered by kills-per-hour, which is the
inverse of protection-per-hour.

**Grant ~1 day with the mode inverted: spend it _deleting_, not writing.** The corpus holds 6,722
already-licensed EQUIVALENT/LOW-VALUE deletion records and **not one has been cashed** **[A]**.
Mutation evidence is the only deletion license this repo has. Precede it with a two-column filter —
reachability (any non-test importer?) and swap bucket — published as the ruling. That turns the
next go/no-go from judgment into arithmetic.

**Hard exclusions:** no census on `container_discovery` (~30% of the file is a hardcoded AI port
table — lift it into config instead, which retires the debt _and_ converts a REWRITTEN module to
SURVIVES), any `*_loader` module, the six httpx AI clients, or
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

Merge #6556 after adjudicating the skip. Spend the freed budget on the coverage repair (§1.1-1.2,
hours), `ai/` collection (§1.3), and the seam fixture (§1.6). Grant WP4.4 one day to _cash_
deletion records rather than mint more. Make the VSS team call before the fork decision, not after.

## Related

- [`05-hardware-profiles.md`](05-hardware-profiles.md) — the tiering strategy
- [`03-open-questions.md`](03-open-questions.md) — the open register
- [`docs/plans/2026-09-12-context-map-doc-updates.md`](../plans/2026-09-12-context-map-doc-updates.md) — the program ledger
