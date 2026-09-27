# Phase 2 — Evaluation and the bake-off (VSS gaming-GPU workstream)

> **For agentic workers:** execute task-by-task, checkbox syntax; every step closes on an executed command + result in the ledger, never on written code. Milestone review is the built-in code review. Ledger rows for this phase are 2.x in `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md`.

**Status: ACTIVE — drafted 2026-09-27, started while M1's hardware half waits on the owner (allowed by F13: "Phase 2 may run before M1 closes"; ledger row 1.x item 8).**

**Goal:** land spec §"Phase 2: Evaluation and bake-off" — **2.1 the replay harness** (`backend/evaluation/vlm_replay.py`, replays **stored** `specialist_outputs`, never re-runs specialists), **2.2 the bake-off runs and the report** (per candidate: S1–S5 + the `uncertain` rate, the tool-calling probe, long-context KV cost, license/gating), and the repo-side half of **2.3**. 2.3's Brev hardware matrix is **owner-run [O]** — Brev spend is a stop-and-ask.

**Spec/authority:** `docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md` rev 6 — §"Bake-off" (:280-291, the per-candidate report and the four candidates), S2/S3 (:74-75), the llama.cpp pin (:157-158, "Nemotron-12B-VL needs a newer pin … merged 2026-02-14 or later, so the bake-off includes that bump"), D2/D12 (:55, :65 — the GB300 **is** the bake-off machine), the machine table (:374 — "Phase 2 replay and bake-off runs, on synthetic and copied real items"), Phase 2 (:444-455), R3 (tool-calling stays open until the probe runs), and the risk table (:582, :590 — the bake-off answers the four-images question; fixed bars get reported verdicts beside them, not silent re-pins). Owner rulings F11–F14 and ledger items 19/20/22/24/26 are the environment-of-record.

---

## 0. What this plan was drafted against — measured here, 2026-09-27

Six numbers decided the shape of this plan. All read from the live store and the live broker, not from a doc.

1. **The frozen store is gen-1: 421 items, and none of them can carry the specialist prompt.** `items` = 421 (`synthetic` 408 + `stock` 13), `runs` 0, `results` 0. **0 of 421** snapshots contain the key `specialist_outputs` at all — the frozen `snapshot` keys are exactly `[camera_id, detections, household, timestamp, zone_crossing, zones]`, the pre-rev-6 shape. The store's own guard refuses to fix that in place: `put_item` raises `item … is frozen; replaying over it changes content` when a re-put's fingerprint differs (`eval_store.py:117-124`). **A replay that ran today would send every item with an empty specialist block, i.e. measure a system 1.3b did not ship.** So 2.1 cannot run against gen-1; task 2.0 makes gen-2.
2. **The repo's corpus has moved past the store, and the delta is known.** `git ls-files | grep -c expected_labels.json` → **413**, of which **5** declare `specialist_context` (1.3b's verdict-changing sets, ledger row 1.3b: "Corpus 408→413 (benign 134→136)"). The store froze at G0.4 (2026-09-24), before 1.3b existed. The renderer that would fill the field already ships and is corpus-side-correct: `_render_specialist_outputs` (`eval_store.py:346-401`) runs the **shipped** `classify_face_outcome` + `face_text`/`plate_text`/`reid_text`, off the same config knobs the live stage uses.
3. **Only 13 items are runnable by a VLM today, and they are the wrong 13 to carry S3.** Media-bearing: 13 (all `stock:`), and all 13 media paths resolve on disk right now (0 missing). Labels: benign 139 (134 synthetic + 5 stock), incident 282 (274 synthetic + 8 stock). **The 8 stock incident items are exactly the "8 low-expecting incidents"** — their `expected_risk_score` is 0, and 0 is the _only_ score at that floor. Consequences, both honest: **S3 on the media-bearing set is vacuous** (every score clears a floor of 0), and **S2's denominator today is 5 items**, which is why F14's "report n + a 95 % Wilson interval" is a hard part of the report, not a decoration. The 408 label-only synthetic items still have no images (ledger item 19) — **S2/S3 verdicts stay blocked on the owner's synthetic media; nothing in Phase 2 unblocks that.**
4. **No expected-severity exists on a stored item.** `EvalItem`/`AssessInput` carry `expected_risk_score` (the band midpoint) and nothing else; the severity floors (`_SEVERITY_FLOORS`, `label_import.py:96`) live only on the import dataclass. So "at or above their expected minimum level" (spec :75) must be _derived_ — see decision D-P2-2.
5. **Score→level is already fixed and agrees with F14's floors.** `frontend/src/utils/risk.ts:80-85`: low ≤ 29, medium 30–59, high 60–84, critical ≥ 85 — identical to `{"low":0,"medium":30,"high":60,"critical":85}`. `VlmVerdict` deliberately carries **no** level field (`vlm_verdict.py:11`), so the harness derives levels from the score using one shared helper, never its own table (D-P2-3).
6. **Two candidates are on the box, two are not, and the blocker is named.** `$AGENT_GPU_DIR/models/vlm/`: Qwen3VL-4B-Instruct-Q4_K_M **2380 MB** + mmproj-Q8_0 429 MB (M1's smoke model), NVIDIA-Nemotron-Nano-12B-v2-VL-Q4_K_M **7150 MB** + BF16 mmproj 1602 MB. Images: `ai-vlm:sm103`, `:sm103-v12`, and **`sm11090`-family `ai-vlm:sm11090`/`sm103-b11090`** — the llama.cpp bump the spec requires for Nemotron-12B-VL, already proven by spike S-5 ("pin-bump empirically confirmed at b11090"). **Absent: Qwen3-VL-8B and Cosmos-Reason2-8B**, and the download path is blocked (HF API 200, `cas-bridge.xethub.hf.co` → **403**). Broker at draft time: `ok`, fence true, `free_mib` 49062, `cap_mib` 40960, `containers: []`.
7. **The tool-calling probe does not exist.** `scripts/vlm_probes/` = `enforcement.py`, `s1_nvext.py`, `s2_multimodal_schema.py`, `s3_salience_stock.py`; nothing in `vlm_client.py`, `ai_contract/`, `ai/vlm/` or the probes mentions `tool_calls`/`tools`. Spec :288 makes it a per-candidate line and R3 stays open until it runs. It is a 2.2 task, built like `enforcement.py`: **a 2xx proves nothing.**
8. **Nothing to rebuild — everything to reuse.** `EvalStore` already owns the run/result ledger (`start_run(engine, model)`, `put_result`, `replay(run_id)` ordered by `item_id`, `UNIQUE(run_id,item_id)`, FK-on), and its D10 guards are exactly the ones 2.0 needs (`_REAL_MEDIA_PREFIXES`, plus a refuse-any-path-inside-the-repo check). `metrics.py` has risk-deviation/Jaccard/key-point/aggregate — but **no FP rate, no recall-at-level, no uncertain rate, no Wilson helper**, and its whole shape is the legacy Nemotron harness's. So 2.1 writes through `EvalStore` and computes S#s in a new module; it does **not** reuse `harness.py` (that file POSTs to a live Nemotron text endpoint — legacy per F10).

---

## Global constraints (binding on every task)

- **Evidence closes a step, not code.** Every box below names the command that closes it. An unrunnable step is **BLOCKED** with its blocker, never an unobserved pass.
- **GPU only through `agent-gpu`,** never around it; `--vram` declared honestly (declare the real working set, not 2); `agent-gpu rm` when done; never touch the rootful `dgx-inference` containers. Broker cap is **40960 MiB** — a candidate that cannot fit under it is BLOCKED, not squeezed.
- **F13:** S1 and S4 come **only** from 24 GB-class hardware. The GB300 may report them only as indicative, labelled as such. Every run is pinned to a commit SHA.
- **D10 privacy:** synthetic items and aggregate metrics only. Real-camera imagery, labels and snapshots never enter git; weights stay under `$AGENT_GPU_DIR/models`; the eval store lives off-repo (`$AGENT_GPU_DIR/out/eval-store/`) and gets wiped at Brev teardown. A report row is a count and a rate, never a per-item dump.
- **The store's freeze is a feature.** gen-1 is never mutated, patched or deleted. New corpus = a new generation directory. `runs`/`results` are append-only rows.
- **Replay never re-runs specialists** (rev 6, pinned for the analyzer since `3a8e2184`; the harness inherits the same rule). Stored `specialist_outputs` are the GIVENS.
- **Legacy is unsupported (F10):** no control replay, no legacy comparison column, nothing measured against it. Rev 5 already dropped the offline 30B control.
- **Tiers:** `uv run pytest backend/tests/unit/ -n auto` (the `test_deploy_phases::test_skips_when_skip_build` systemctl env-fail is the sanctioned single failure, same identity since 1.1); contracts `-n0 --timeout=30`, never xfail/skip in `ai_providers` (AST-enforced); integration only with live PG :5433 + Redis :6380 **and** a same-session up-check; `scripts/gen-ai-contract.py --check` after any ai_contract change; `cd frontend && npm run typecheck` after a TS regen.
- **Commit gate:** `SKIP=hadolint uv tool run pre-commit run --files <changed>` from the repo root (never `--all-files`) until zero churn, then the message check DIRECT: `uv tool run conventional-pre-commit <types> /tmp/msg.txt`. Push each committed task to `github` unprompted (standing permission, ledger open-issue 11).
- **Stop-and-ask, never self-resolve:** the M2 VLM pick, go-live 3.1, any D#/S# change, **any Brev spend**, dgx-inference, R10, postponed-roadmap items, PR merges.

---

## Decisions this plan needs, with a recommended default

Raised here so the owner can rule in one pass; each has a default that keeps the work moving, and none changes a D# or S#.

- **D-P2-1 — gen-2 is a new generation, not an edit.** `$AGENT_GPU_DIR/out/eval-store/gen-2/eval.sqlite`, built by the shipped loaders from the 413 committed label sets + the 13 stock media items. gen-1 stays on disk, byte-identical, as the record of what G0.4 froze. _(Default taken; this is the only non-mutating option.)_ **The gen-2 totals are not an estimate — the shipped loader already ran over the repo corpus (`ENVIRONMENT=test DATABASE_URL=… uv run python`, `load_synthetic_items("data/synthetic")`): 413 synthetic items, benign 136 / incident 277, exactly 5 carrying a rendered block (the 1.3b sets, e.g. `faces: "known person Dad (78% match)"`, with `person_reid`/`plates` honestly `unavailable: specialist did not run`), 0 with media.** With the 13 stock: **426 items, benign 141 / incident 285, 13 media-bearing, 5 with specialist context.**
- **D-P2-2 — S3's "expected minimum level" is derived from `expected_risk_score` through the shipped banding, and reported with the stock items called out.** Floor(level(expected*risk_score)) is the item's expected minimum. An item at 0 floors at `low`, so it can never fail S3 — which is honest arithmetic, not a bug, **and is exactly why the 13 stock items cannot carry S3 today**. Reported per F14: n + 95 % Wilson, and S3 **with** (n=282) and **without** (n=274) the 8. *(Default taken; the alternative — inventing expected severities for stock scenarios — is a labeling change to a fixed bar's denominator, so it stays an owner call.)\_
- **D-P2-3 — one score→level helper, imported, never re-spelled.** Add `backend/evaluation/levels.py` mirroring `RISK_THRESHOLDS` (`risk.ts:80-85`) and pin it against the TS table so the harness's S2 and the UI's gauge can never disagree. _(Default taken.)_
- **D-P2-4 — Cosmos-Reason2-8B is a BLOCKED candidate, not a dropped one.** Its weights and our vLLM build are both absent and the CDN returns 403. It stays in the report as BLOCKED with the probe output, per "unrunnable = BLOCKED". Qwen3-VL-8B likewise. _(Default taken; if the owner can place either weights directory under `$AGENT_GPU_DIR/models/vlm/`, the run needs no new code.)_
- **D-P2-5 — 2.3's Brev matrix is owner-run [O].** The sandbox prepares the checklist and the exact commands; it does not spend money.

---

## Sequencing (binding)

1. **2.0 before 2.1's live evidence.** A harness over gen-1 measures a corpus that cannot carry the shipped prompt (finding 1). gen-2 first.
2. **2.1 before 2.2.** The bake-off is "the same replay per candidate" (spec :283) — the replay is the thing being run.
3. **The tool-calling probe lands inside 2.2, per candidate**, and R3 stays open until it has run for each candidate that claims tool support.
4. **S2/S3 verdicts are gated on the owner's synthetic media (item 19).** Phase 2 ships the harness, the runs, the numbers-on-13-items and the BLOCKED lines; it does not fabricate a verdict on 408 imageless items.
5. **The M2 pick is the owner's (D5).** This phase produces the report; it never picks.

---

## Task 2.0 — eval-store generation 2: a corpus that can carry the shipped prompt

**Closes on:** the build command + the counts it prints + a `runs`/`results` = 0 check + gen-1 unchanged (its sha256 before and after).

- [ ] **2.0.1 `backend/evaluation/eval_store.py`: a generation-aware builder, red-first.** `build_gen2(store_dir)` (or a `--generation` flag on the existing entry point) that runs `load_synthetic_items(corpus_dir)` over the **413 committed** label sets and `load_stock_items(media_root)` over the 13 media items, `put_item`s all of them, and **prints a build report**: items total, per-namespace, per-label, media-bearing count, and **the count of items whose snapshot carries a non-empty `specialist_outputs`** (expected: 5 — 1.3b's sets — and the build FAILS LOUD if it is 0, because a gen-2 with no specialist block is gen-1's bug rebuilt).
- [ ] **2.0.2 The pin that gen-1 cannot be reached.** A test that gen-2's build path never opens a path containing `gen-1`/the frozen default, and one that a re-put of a changed item still raises `frozen`. (The freeze guard is the thing being preserved, so it is pinned at the new call site, not inherited silently.)
- [ ] **2.0.3 Build it and read it back.** The store must answer: 426 items, 13 media-bearing, benign 141 / incident 285, 5 items with a rendered specialist block, `runs` 0. Report the numbers it prints — do not restate this sentence.
- [ ] **2.0.4 Ledger row 2.0** with the exact command, the printed report, gen-1's sha256 before/after, and the commit. **No imagery, no per-item data (D10).**

## Task 2.1 — the replay harness, `backend/evaluation/vlm_replay.py`

Replays **stored** items through the shipped `VlmClient`, writes through `EvalStore`, and computes the S#s. It never re-runs a specialist and never imports `harness.py` (legacy, F10).

**Closes on:** `uv run pytest backend/tests/unit/evaluation/test_vlm_replay.py -q` green, plus one end-to-end replay of the 13 media-bearing items against a served `ai-vlm` through `agent-gpu` with the container `rm`-ed after.

- [ ] **2.1.1 `backend/evaluation/levels.py` + its cross-language pin (D-P2-3).** `score_to_level(score) -> low|medium|high|critical` using 29/59/84, plus a test that parses `RISK_THRESHOLDS` out of `frontend/src/utils/risk.ts` and asserts the same three numbers — the same "three twins, byte-identical" doctrine the provenance columns learned, with the DDL-render lesson (assert the literal, not the attribute).
- [ ] **2.1.2 `s_metrics.py` (or the metrics module's new section): the four S# primitives, pure functions.**
  - `wilson_interval(k, n, confidence=0.95)` → `(lo, hi)`, then
  - `false_positive_rate(results, labels)` → rate at `score ≥ 30` on labeled-benign, **plus n and that interval** (F14). No Wilson helper exists anywhere in the repo, so it is written here — **not** `scipy.stats.binomtest(...).proportion_ci`: scipy 1.18.1 resolves in this venv but is **transitive, not a declared dependency** (verified: absent from `pyproject.toml`, present in `uv tree`), and a fixed bar's report must not rest on a package that disappears with someone else's bump. `ab_experiment_runner.py:39` already imports scipy directly, which is that latent break waiting; noting it here is not fixing it — a declared-dependency change is its own call.
  - `recall_at_expected(results, items)` → share of labeled incidents with `score ≥ floor(expected level)`, returned **both** with and without the zero-floor items, each with n + Wilson (F14 / D-P2-2).
  - `uncertain_rate(results)`, `verdict_mix(results)`, and `s5_unparseable_count(results)` — every failure is `verification_failed` with a **NULL** score, never a default (S5 is the shipped ladder; the harness's own contribution is that it must not paper a NULL into a number when it aggregates).
  - Pins: an empty set is `n=0`, not a crash and not 0 %; a `verification_failed` row counts as a **refusal**, not a benign call; Wilson endpoints bracket a known case against a hand-computed value.
- [ ] **2.1.3 The replay itself.** For each item: read the stored `EvalItem`, build `VlmAssessContext` from `snapshot` (including the stored `specialist_outputs` verbatim), call the shipped `VlmClient.assess`, and `put_result(run_id, item_id, verdict=…, risk_score=…, raw_response=…)` where **`risk_score` is NULL for every non-scored verdict** (the S5 shape, at the row level). `start_run(engine="vlm_replay", model=<candidate id + quant + engine pin>)` — the model string is what makes two runs comparable, so pin it from the served model name and the image tag.
  - Pins (fakes, no GPU): a stored `specialist_outputs` block reaches the request **byte-identically**; a `verification_failed` verdict stores NULL and is not counted as low risk; a duplicate `(run_id, item_id)` is refused, not silently overwritten; the harness never imports anything that re-runs a specialist (an AST or module-identity pin, the shape `test_no_seam_constructs_nemotron_directly` already uses).
- [ ] **2.1.4 `--candidate` / `--limit` / `--store` CLI.** A run must be reproducible from one command line printed in the report, and it must refuse to run against gen-1 (finding 1) with a message naming why.
- [ ] **2.1.5 Report writer.** `save_report`/`generate_json_report` are shaped for the legacy harness's DataFrame; write a small vlm-shaped writer beside them rather than bending them. The report is: run id, engine, candidate, commit SHA, corpus generation + counts, then **aggregate only** — S2 (rate, n, Wilson), S3 both ways (n, Wilson), verdict mix, `uncertain` rate, S5 count, wall-clock per item distribution (median/p95, **labelled GB300-indicative per F13**). No per-item rows in git.
- [ ] **2.1.6 Live smoke on the GB300.** `agent-gpu run --image ai-vlm:sm103-v12 --vram 14 --port 8098 --mount models:/models` (Qwen3-VL-4B, the M1 smoke build), replay the **13 media-bearing** items, `agent-gpu rm` after, broker back to `containers: []`. This is the harness's end-to-end proof; S2's n on it is 5 and the report says so.
- [ ] **2.1.7 Tier gate + commit + push.** Unit `-n auto`, contracts, `gen-ai-contract.py --check` (expect "current": the replay consumes the contract, it does not change it), and the ledger row 2.1.

## Task 2.2 — the bake-off: the same replay per candidate, and the report

**Closes on:** one ledger row per candidate carrying command, commit SHA, and the aggregate numbers — or the word **BLOCKED** with the probe output that produced it.

- [ ] **2.2.1 Tool-calling probe — `scripts/vlm_probes/tool_calls.py`.** Built like `enforcement.py`: request a completion that **must** produce a `tool_calls` entry (a named function with a required argument), and check the parsed response, not the status code. Report per endpoint: `SUPPORTED` / `IGNORED` / `ERROR`, plus whether a required-argument schema is honoured. This is the line that keeps **R3** open or closes it, per candidate.
- [ ] **2.2.2 Candidate A — Qwen3-VL-4B-Instruct Q4_K_M** (present: 2380 MB + 429 MB mmproj), image `ai-vlm:sm103-v12`, `--vram` declared honestly for the real working set. Full replay of gen-2's media-bearing items + the tool probe + a long-context KV reading from the served engine's own log.
- [ ] **2.2.3 Candidate B — Nemotron-Nano-12B-v2-VL Q4_K_M** (present: 7150 MB + 1602 MB BF16 mmproj), **image `ai-vlm:sm103-b11090`** — the llama.cpp bump spec :157-158 requires for this model (spike S-5 confirmed b11090 empirically). Same measurements. If it cannot fit under the 40960 MiB cap with its mmproj, that is a BLOCKED row with the numbers, and it goes to the owner as a VRAM squeeze (stop-and-ask), not a lowered declaration.
- [ ] **2.2.4 Candidates C and D — Qwen3-VL-8B, Cosmos-Reason2-8B.** Absent weights; `cas-bridge.xethub.hf.co` → 403. Each is a **BLOCKED** row with the failed fetch, the size it would need, and the one thing that would unblock it (D-P2-4). Cosmos additionally needs our own vLLM (BF16, quality reference only, spec :281-282).
- [ ] **2.2.5 The bake-off report.** Per candidate, exactly the spec's four lines (:286-289): S1–S5 + `uncertain` rate; the tool-calling probe; long-context KV cost; license and gating. S1/S4 **only** as GB300-indicative (F13) — the real fit/latency numbers are 2.3's. S2/S3 as measured, each with n and Wilson, and the standing BLOCKED note for the 408 imageless items (item 19). Bars printed as F14's 5 % / 90 % **beside** the verdict mix, never against a silently-reset bar (:590).
- [ ] **2.2.6 What the report explicitly does not do:** pick the model (D5, M2 is the owner's), claim S1/S4 from the GB300, or restate S-3's `uncertain`-hedging question as answered — 1.3b deferred it to these runs, and the verdict-mix line is where it gets its first measurement.
- [ ] **2.2.7 Ledger rows 2.2.x, commit, push.**

## Task 2.3 — hardware matrix: the repo-side half only (the rest is owner-run [O])

- [ ] **2.3.1 `docs/superpowers/plans/2026-09-27-brev-hardware-matrix-checklist.md`**, shaped like the A5500 handout: per tier (A10G 24 GB sm_86, L4 24 GB sm_89, RTX PRO 4500 32 GB sm_120 [A], T4 16 GB) — the `nvidia-smi --query-gpu=compute_cap` confirmation the spec requires **before** trusting a tier's number, the serve command with the honest VRAM figure, the replay command pinned to a commit, and what to read for S1 and S4.
- [ ] **2.3.2 The NVFP4 question, stated as a reading task:** on the RTX PRO 4500, run the NVFP4-QAD checkpoint in vLLM and read the **resolved quantization method from the startup log** (04 §6) — that settles whether NVFP4 computes natively on consumer Blackwell (03 Q1). Nothing here asserts an answer.
- [ ] **2.3.3 BLOCKED honestly:** Brev spend is a stop-and-ask; no VM is started, no S1/S4 number is claimed, and 2.3's ledger row says owner-run.

---

## What Phase 2 does **not** claim

- It does not close M1. M1's assertions (2) and (3) are owner-run hardware on the A5500 (`2026-09-27-a5500-vlm-bringup-checklist.md`), and that run is also where S1 and S4 come from.
- It does not produce an S2/S3 **verdict** on the full corpus. 408 items have no images (item 19); the harness runs and the numbers come back with n = 5 and n = 274/282 until the owner's synthetic media exists.
- It does not resolve the six owner decisions the M1 draft lists (alerts unverified bucket, residency policy, the video→frame extractor, synthetic media, the 8 low incidents' relabel, the M2 pick), and it does not touch the legacy path (F10) or any postponed-roadmap item.

### Reproduce the six drafting facts

```bash
# 1 + 4 + the label split (read-only)
python3 -c "import sqlite3,json,collections,os;db=sqlite3.connect('file:$AGENT_GPU_DIR/out/eval-store/eval.sqlite?mode=ro',uri=True);\
rows=db.execute('SELECT item_id,payload FROM items').fetchall();\
print(len(rows),collections.Counter(json.loads(p)['expected_label'] for _,p in rows));\
print('media',sum(1 for _,p in rows if json.loads(p)['media_paths']));\
print('specialist_outputs',sum(1 for _,p in rows if json.loads(p)['snapshot'].get('specialist_outputs')))"
# 2
git ls-files | grep -c expected_labels.json          # 413
git grep -l specialist_context -- '*expected_labels.json' | wc -l   # 5
# 3 + 6
ls "$AGENT_GPU_DIR/models/vlm/"                       # candidates present / absent
agent-gpu status                                      # fence, free_mib, cap_mib, containers
# 5
grep -n "LOW_MAX\|MEDIUM_MAX\|HIGH_MAX" frontend/src/utils/risk.ts
# 7
ls scripts/vlm_probes/
```
