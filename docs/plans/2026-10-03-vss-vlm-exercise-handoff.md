# VSS VLM exercise — sandbox-recreate handoff (2026-10-03)

> **Purpose.** A scratch handoff, written in sandbox `agent-vss5` immediately before its owner
> recreates the sandbox with the synthbench mounts. It records what was MEASURED in that sandbox on
> 2026-10-03, so the next session starts from measurements instead of re-deriving them. This is not
> the ledger and claims no ledger row; where it quotes the ledger it names the row.
> Evidence markers follow `docs/vss-integration/AGENTS.md` ([V] read in-session, etc.).

## The goal this session was given

Make progress on the design in `docs/vss-integration/` — stand up the VLM pipeline and start
exercising it against the synthbench corpus (`/synthbench/corpus`: pictures and videos), after a
week of retiring the previous AI pipeline architecture. [O]

## Ground truth measured 2026-10-03 [V]

- **The VLM path is shipped and wired, not greenfield.** `docker-compose.prod.yml:484` carries
  `PIPELINE_MODE=${PIPELINE_MODE:-vlm}`; the `ai-vlm` llama.cpp service is at `:134` with
  `MODEL_PATH=/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf` (`:179`), its mmproj (`:180`),
  `CTX_SIZE=${VLM_CTX_SIZE:-32768}` (`:205`) and `PARALLEL=${VLM_PARALLEL:-2}` (`:206`);
  the backend dials `AI_VLM_URL=${AI_VLM_URL:-http://ai-vlm:8098}` (`:552`).
- **`vlm_assess` is live** in `backend/ai_contract/{operations,providers}.py` and
  `backend/services/vlm_{client,analyzer,specialists,verdict}.py`; evaluation harness:
  `backend/evaluation/vlm_replay.py` + `assess_input.py`.
- **`python -m synthbench` runs in the sandbox**: `doctor export audit replay score` all exist;
  `export/vss.py` feeds the eval-store layout, `run/replay.py` replays a served VLM through the
  shipped `VlmClient`, `score/` computes S2/S3. S3's bar is `S3_MIN_PCT = 90.0` at
  `backend/evaluation/s_metrics.py:33` — consistent with ledger item 107's note that a corpus run
  is what answers S2/S3.
- **Ledger through 2026-10-01 (rows 62–74): all agent-owned main-green work is claimed; what
  remains is owner-gated.** For THIS goal the load-bearing open items are M1 (the notification
  link is unwired) and S3 (failing its bar in every measured arm) — closing those needs scored
  corpus runs, i.e. exactly this exercise.
- **Network from the sandbox**: `huggingface.co` → 200, `github.com` → 200. ComfyUI renderer
  reachable at `http://host.docker.internal:8188` (doctor said `ok renderer`).
  `http://host.docker.internal:8098/props` → connection refused — **no ai-vlm on the host's
  localhost:8098 at read time**.

## Why the exercise could not start in that sandbox

`uv run python -m synthbench doctor` printed three FAILs and exited per its own rule: [V]

```text
FAIL opencv: the sandbox image lacks OpenCV's libraries: the owner runs sbx exec <sandbox> sudo apt-get install -y libxcb1 libgl1 libglib2.0-0
FAIL corpus mount: mount /synthbench/corpus read-write into the sandbox (never a path under /export)
FAIL guard status: mount /synthbench/status read-only into the sandbox
ok   renderer: http://host.docker.internal:8188
ok   no corpus version yet: the first sample creates it and pins the taxonomy
```

- **The corpus is simply not present inside the sandbox** — a full-filesystem media scan found no
  media files under `/synthbench` or anywhere else. The pictures/videos exist on the host ZFS
  dataset `primary/export/synthbench/corpus`; the sandbox needs them mounted. This is the blocker
  the recreate fixes.
- **No GPU in that sandbox** (no `/dev/nvidia*`, no `nvidia-smi`) and **no model weights**
  (`/export/ai_models` absent, no HF cache). llama.cpp serving the shipped 8B Q4_K_M GGUF + Q8_0
  mmproj is not possible there (≈5.1 GiB + ≈0.7 GiB, plus KV for a 32K/2 context).
- Disk was ~19 GB free on `/`; `uv sync` and the synthbench CLI work normally.
- `docs/plans/2026-09-27-vss-phase2-bakeoff-report.md:268` documents the podman pattern for serving
  a candidate GGUF with a models mount.

## Mount spec for the recreated sandbox

Derived from `synthbench/contract/store.py:94-98` (`$SYNTHBENCH_ROOT/corpus`),
`synthbench/status.py:51-53` (`$SYNTHBENCH_ROOT/status`), and the doctor FAIL strings above
(`synthbench/commands/doctor.py:37-45`). The default `SYNTHBENCH_ROOT` is `/synthbench`
(`synthbench/contract/store.py:28`), so:

1. `/synthbench/corpus` — host ZFS `primary/export/synthbench/corpus` — **read-write**
   (append-only by convention; commands write `prompts.jsonl`/`triage.jsonl` and event files).
2. `/synthbench/status` — host directory holding `flagship.json` + `snapshots.json` — **read-only**.
   `doctor` requires the guard status file to exist, parse, and be fresh; if the host guard is
   down, `synthbench-guard.service` must be enabled (`doctor.py:40-42`).
3. `SYNTHBENCH_PODMAN_ROOT` (default `/export/models/containers`) — only if generation
   (`render`) is intended from the new sandbox. Never the default podman store.
4. GPU (only if serving the VLM inside the sandbox is intended):
   `podman run --device nvidia.com/gpu=all` is the documented pattern
   (`docs/operator/gpu-setup.md:265`, `scripts/bootstrap-gb300.sh:531-551`).
5. After create: `sbx exec <sandbox> sudo apt-get install -y libxcb1 libgl1 libglib2.0-0`
   (the doctor's own one-liner fix for OpenCV).
6. Network: huggingface.co returned 200 without an approval prompt; if the new sandbox's policy
   differs, ask before assuming — do not assume `sbx policy allow` applies.

## Suggested next steps for the fresh session, in order

1. Run `uv run python -m synthbench doctor` first; all-ok = mounts landed.
2. Inventory the corpus: what versions/events exist, stills vs clips, and whether a VSS-shaped
   export already exists (`synthbench export`, `export/vss.py`). In the old sandbox the eval
   store in-tree had never been replayed against ("0 events in store; replayed 0") — expect real
   data to live only on the mounted corpus. [V at that tree; re-check at the new one]
3. Confirm a served VLM is reachable — either an ai-vlm/llama.cpp on the host published to the
   sandbox, or a model served inside a GPU-mounted sandbox. `replay` refuses to run against an
   endpoint it cannot identify (`synthbench/run/replay.py` checks endpoint, renderer, and model
   identity). If no GPU arm is available yet, `backend/ai_contract/fake/app.py` serves the
   contract ops without a GPU — useful for an end-to-end plumbing smoke of
   export → replay → score before any real arm.
4. **[CORRECTED 2026-10-03, post-recreate — this step originally said S3 needed owner-audit
   labels and would score 0-of-0. That was WRONG for this corpus.]** Generated items need no
   audit to be scored: `import_generated_items` (`backend/evaluation/label_import.py:449`,
   docstring) says "Labels are BORN: category comes from the set's placement … expected score
   from the set's declared risk band", and P5a design A2 (`docs/superpowers/specs/
   2026-09-29-synthbench-p5a-vlm-replay-design.md:27`) scores "the sampler's declared facts,
   labelled unverified, with an audit of 60 stills that measures the truth's error rate". So
   `export vss → replay → score` yields S2/S3 on declared truth; `synthbench audit` only adds
   the error bar. The feedback-label rule I had read (`label_import.py:195-265`, "no label …
   stays excluded") belongs to the OTHER importer (production-event feedback), not this one.
   S3 only counts items whose floor is above `low` meaningfully (`s_metrics.py:106`
   `excluding_zero_floor`); ambiguous events are not exported at all (`export/vss.py:20-23`).
5. `replay` an arm over an export, then `score` it — the output that answers S2 and S3
   (S3_MIN_PCT = 90.0), which is the evidence M1/M2 closure has been waiting on.
6. For M1's real end-to-end exercise (the notification link the ledger calls unwired), ask the
   owner which link is intentionally unwired before assuming either direction.

## Traps worth carrying

Each was checked by direct read at this tree (2026-10-03); anything that failed that check is
listed as dropped, per the house rule that a carried number is a claim.

- **Two replay harnesses with different metrics.** The S2/S3 path is
  `synthbench run replay` + `synthbench score` — `synthbench/score/metrics.py:3` states S2/S3
  come ONLY from `backend/evaluation/s_metrics.py` (`S3_MIN_PCT = 90.0` at `:33`, `s3_recall`
  at `:106`). The older `backend/evaluation/vlm_replay.py` serves the bake-off/S-spike lineage
  (and `scripts/vlm_probes/s3_salience_stock.py` is spike S-3's probe, not the S bar). Running
  one and quoting the bar from the other is the cheapest way to produce a false measurement.
- **Residency vs S1's wording.** The shipped `vlm` gateway set is `(yolo26, reid)` (+ `threat`
  only when `GATEWAY_ENABLE_THREAT`) — ledger row 1.4 (the `105–125` block, `c271d5e7`) [V] —
  while spec S1 (spec `:83`) says "with the detector, the specialists and the VLM resident."
  Before a bring-up claims S1, settle which residency set it is measured on.
- **The S2/S3 bars ARE set — the spec rows are just not back-edited.** Ledger item 19 / F14
  (`docs/plans/2026-09-23-vss-gaming-gpu-ledger.md:221`, owner ruling 2026-09-25 [O], commit
  `f620ba49`): `S2_MAX` = 5%, `S3_MIN` = 90%. Code agrees (`backend/evaluation/s_metrics.py:32-33`,
  `S2_MAX_PCT = 5.0`, `S3_MIN_PCT = 90.0`). The spec's S2/S3 table rows still read `[?]`
  (`docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md:84-85`) — that is spec drift,
  not an open bar. **[CORRECTED 2026-10-03: this bullet originally said S2_MAX was still `[?]` and
  that the README's "ruling at :221" cite was dead. Both were wrong: :221 IS the F14 ruling.]**

**Dropped as unverified in this tree** (came from the docs-map verifier and failed re-check
here): a stale claim at `backend/services/README.md:261` (no such file exists); "S2 = 85% rev 7
vs F3 = 80%" (no such numbers at the cited places; the bar is 5% per F14); the run id
`run-20260927T222836Z` (absent from the repo tree and git grep — if it exists it lives on the
host's off-repo eval store, not in git). If the fresh session needs that run's numbers, read
them from the host eval store.

## Session artifacts (transient — may not survive the recreate)

- A `docs/vss-integration` context-map workflow (runId `wf_2d056dcd-6ed`, 10 readers + verifier +
  critic + synthesizer) was in flight at recreate time. Script copy: `/tmp/vss-docs-context-map.js`
  (transient too). If lost, it is re-authorable from the directory layout; resume via
  `Workflow({scriptPath, resumeFromRunId})` only if the session directory still exists.
- This repo's discipline applies: append-only for the ledger, owner merges (a standing delegation
  exists — ledger row 70 records the grant), STOP-AND-ASK on exit 2 and on anything touching
  secrets, `models.yml`, deploy targets, or workflow triggers.

## Addendum — state after the recreate (2026-10-03, ~09:10 ET) [V unless marked]

- **Mounts landed; `doctor` is all ok** (`doctor: ready for every command`) after
  `sudo apt-get install -y libxcb1 libgl1 libglib2.0-0`. `/synthbench/corpus` is `rw`,
  `/synthbench/status` is `ro` (`/proc/mounts`, virtiofs). Host is aarch64 (GB300, sm_103).
  `/synthbench` itself is root-owned and holds only `corpus` and `status` — there is no
  `/synthbench/exports`, `runs` or `audits` yet; see "Open problem" below.
- **Corpus `tierb-v0`** (taxonomy sha256 `fb8de9c6176d`, 1280x720 renders): 460 events drawn
  (pilot-1 10, batch-1 50, batch-2/3/4/5 100 each), 459 ready, 1 failed; `index.jsonl` labels:
  incident 241 ready, benign 209 ready (+1 failed), ambiguous 9. 956 jpg stills, 481 mp4 clips
  (clip events are `C-clips-1-*`, `source` = the still's `B-` event; `rounds/clips-1`). 2.6 GB.
  Benign scenarios flashlight_neighbor / hooded_jogger / landscaper_machete / power_tools_at_night
  / winter_face_covering are already at 29 each (hard negatives); most incident scenarios 9-19.
- **GPU path is `agent-gpu`, not a device.** `agent-gpu status` ok (cap 40,960 MiB, floor 4,096).
  Weights already in `$AGENT_GPU_DIR/models/vlm/` (`/agents/agent-vss5/gpu/models/vlm/`),
  sha256-matched to vss1's by the owner; sizes equal the compose pin (5,027,784,800 /
  752,289,728). Base images pulled (`docker.io/nvidia/cuda:13.3.1-{devel,runtime}-ubuntu22.04`),
  then `agent-gpu build --context workspace:ai/vlm --tag ai-vlm:sm103 --build-arg
  CUDA_ARCHITECTURES=103` -> `localhost/agent-vss5/ai-vlm:sm103` (3.59 GB), llama.cpp b7972.
- **Serving recipe that worked:** `agent-gpu run --name vlm --image ai-vlm:sm103 --vram 14
  --port 8098 --mount models:/models --user 0` + the compose `ai-vlm` env verbatim, with
  `MODEL_PATH=/models/vlm/<gguf>` (the mount is the `models` ROOT, so keep the `vlm/` segment).
  **`--user 0` was required:** as the image's `llama` user (uid 1000) llama-server got
  `Permission denied` on the 0640+ACL GGUFs (rootless uid mapping). Endpoint is
  **`http://host.docker.internal:18100`** (container 8098 is remapped by the runner — NOT 8098).
  Measured: `/health` 200; `/props` model_alias `Qwen3VL-8B`, n_ctx 16384 x 2 slots, vision true,
  build b7972; 37/37 layers offloaded; model 4,455 MiB + KV 2,448 MiB (q8_0) + compute buffers;
  **runner-reported actual VRAM 9,056 MiB vs 14,336 declared**. First GB300 reading of this exact
  config; it is NOT an S1 claim (S1 is reserved to 24 GB-class hardware, F13).
- **Open problem — where do `export`/`replay`/`score` write?** They write under
  `$SYNTHBENCH_ROOT/{exports,runs,audits}` and `SYNTHBENCH_ROOT` also locates the corpus
  (`store.py:94-98`), but only `corpus` and `status` are mounted. Check `--out`/env options
  before improvising; do not symlink-farm around the mount design without the owner's say.
- **`export vss` done** (read-only on the corpus): `--out $AGENT_GPU_DIR/out/exports/tierb-v0/vss` ->
  450 sets written (normal 209, suspicious 45, threats 196); not exported: ambiguous 9, failed 1.
  Stills are real 1920x1080 JPEGs (median ~300 KB; `du` under-reports on this fs). Spot check:
  firearm_visible / incident / band [85,100] / detections person+handgun.
- **`replay` STOPPED at exit 2 (stop-and-ask), not worked around.** Command:
  `uv run python -m synthbench replay --model qwen3-vl-8b --url http://host.docker.internal:18100
  --export $AGENT_GPU_DIR/out/exports/tierb-v0/vss --limit 1`. Message, verbatim: "the renderer is
  running, or its state cannot be read: stop synthbench-renderer first (replay needs its GPU
  memory). Stop and ask the owner." Cause, both true: ComfyUI answers on 8188 (renderer running),
  and `synthbench/run/replay.py:111-125` reads `systemctl --user is-active synthbench-renderer`,
  but `systemctl` is not installed in the sandbox, so the state is unreadable and counts as
  running. Nothing was written. Separately, `replay`/`score` write to `$SYNTHBENCH_ROOT/{eval,runs}`
  (`commands/replay.py:59-67`) and `/synthbench` is root-owned with only corpus+status mounted.
  **Owner decisions needed:** (1) is replay allowed while the renderer runs, given the VLM is
  now a fenced `agent-gpu` container with its own VRAM budget (9,056 MiB actual) rather than
  sharing the renderer's memory; (2) where `eval/` and `runs/` should live (a writable mount, or
  `SYNTHBENCH_ROOT` pointed at a dir that also exposes the corpus).
- **Smoke (NOT S2/S3):** one plain chat request with a threats still to the served model:
  2.4 s, 1,245 prompt tokens, 61 completion tokens; it described a man on a porch holding a
  handgun, matching the declared firearm. Runner VRAM unchanged at 9,056 MiB.

## Addendum 2 — the first full replay (2026-10-03) [V unless marked]

**Correction first:** there was already a committed P5a baseline on this corpus
(`docs/benchmarks/synthbench/p5a-2026-09-30.md`, scored at `ca73f1ef`): Qwen3-VL-8B S3 36.5%
[30.7-42.8] (n=241) against the 90% bar, S2 6.7% [4.0-10.9] (n=209) against 5%, flagship S3 58.9% /
S2 8.6%; the 60-still owner audit is DONE (scene/people/conditions error 0.0% [0.0-6.0]). Earlier
text in this file implied S2/S3 were unmeasured; they were not. Today's run is a RE-RUN.

- **Run:** replay `20261003T131219Z-qwen3-vl-8b`, score `20261003T133003Z`, both under
  `$AGENT_GPU_DIR/out/sbroot/runs/`. 450 items, 0 refusals, verdicts confirmed 440 / rejected 4 /
  uncertain 6. **S2 19/209 = 9.1% [5.9-13.8]; S3 87/241 = 36.1% [30.3-42.3]** (zero floors are
  `low`, so "all" = "excluding zero-floor"). Risk band: 63.1% of incident scores below the declared
  band (mean 53.1 points below), 0.0% above.
- **Identity with the baseline:** export labels sha256 `3a9b16e3…c847d` is byte-identical to the
  committed report's; weights sha256 `67d1659b…` (owner-verified against vss1); build
  `b7972-e06088da0`; conditions identical (shipped prompt, max_tokens 1024, 25 s timeout, enforcement
  probe on). All 13 core files are unchanged since `ca73f1ef` (`git diff --numstat ca73f1ef HEAD --`
  vlm_client, vlm_verdict, vlm_analyzer, vlm_specialists, key_frame_selector, vlm_replay, s_metrics,
  levels, assess_input, label_import, ai/vlm/Dockerfile, synthbench/run/replay.py,
  synthbench/export/vss.py): every one unchanged. The only commits to those trees since are the R8 S3
  Florence-provider retirement (`3b73b9b6`, `7253cd94`).
- **S3 reproduces** (88/241 -> 87/241). Per scenario the counts churn by 1-2 items in both directions
  (firearm_visible 18->17, forced_entry 16->18, fire_or_smoke 10->11, knife_visible 10->9).
- **S2 does not:** 14/209 -> 19/209, and ALL of the +5 sits in the three hard-negative scenarios
  (hooded_jogger 8->9, power_tools_at_night 5->8, flashlight_neighbor 1->2, n=29 each); every plain
  benign scenario is 0 false alarms in both runs. The F14 label flips MARGINAL -> FAIL between runs
  (today's interval [5.9-13.8] lies wholly above 5%). With code ruled out, this is run-to-run
  variation at the medium threshold, **S2 measurement noise is the same size as S2's gap to its bar**
  — that is itself a finding. A repeat run to size the noise was started (see Addendum 3 if present).
- **Not run through `synthbench replay`:** that command refuses from this sandbox (renderer check
  unreadable, no `systemctl`); the owner directed running the same shipped harness without that one
  check. The driver (kept in the session scratchpad, not the repo) is `execute()` minus
  `renderer_stopped`, and writes `renderer_check: SKIPPED …` into each `run.json`. Settings needed
  `ENVIRONMENT=development` plus a placeholder `DATABASE_URL` (production validators otherwise reject
  an unconfigured process); no VlmClient setting depends on it.
- **Audit slice reads 0/60:** the real audit log is on the host (`/synthbench/audits` not mounted);
  `score` tolerates a missing log (`audit/page.py:40-48`). Use the committed report for audit numbers.
- **Warning seen on every request:** `Service 'ai-vlm' not registered`
  (`backend/services/degradation_manager.py:502`) — the replay process has no service registry; benign
  here, but it is the same path production uses for degradation tracking (candidate issue).

## Addendum 3 — the repeat run, and what it says about measurement noise (2026-10-03) [V unless marked]

- **Second full replay** `20261003T133050Z-qwen3-vl-8b`, score `20261003T134742Z`: 450 items, **1 refusal**
  (`VlmTruncatedError`, `B-batch-4-012`, stop='length' at max_tokens 1024 — reported as UNMEASURED at
  this budget, not as a verdict), **S2 18/209 = 8.6% [5.5-13.2]; S3 84/241 = 34.9% [29.1-41.1]**.
- **Three readings of the same 450 sets, same weights/build/conditions** (committed 2026-09-30,
  today run 1, today run 2): S2 false alarms 14 / 19 / 18 of 209 (mean 17.0 = 8.1%, sd 2.6);
  S3 hits 88 / 87 / 84 of 241 (mean 86.3 = 35.8%, sd 2.1) [C, n=3 — a rough band, not a CI]. Both
  metrics fail their F14 bars (5% / 90%) in every reading; S2's interval straddles 5% only in the
  baseline.
- **Item-level agreement between today's two runs (same server, same session): only 278/450 items
  (62%) returned an identical verdict and score**; 164/450 (36%) changed score, 123 by >= 10 points
  (max 95), 52 changed risk level. The benign false-alarm SETS overlap poorly: 13 items are false
  alarms in both runs, 6 only in run 1, 5 only in run 2 (Jaccard 0.54); the incident hit sets overlap
  better (76 in both, 11 / 8 in one only; Jaccard 0.80).
- **Cause (read, not inferred):** the shipped assess request samples at `"temperature": 0.1` with no
  seed (`backend/services/vlm_client.py:796`, introduced in `4bfd6fa4`, 2026-09-27); `temperature 0`
  is used only for the §6 transport retry (`:805-807`), and there is no seed, self-consistency or
  repeated-sampling code anywhere in `vlm_client.py`, `vlm_analyzer.py` or `vlm_verdict.py`. So the
  run-to-run variation is a property of production behaviour, not just of the benchmark, and a
  single replay is one draw. The committed baseline's 14 -> today's 18-19 on S2 is within what this
  noise allows; it does not by itself indicate a regression (code is unchanged since the baseline,
  Addendum 2).
- **Consequences for the action plan** (candidate issues): (1) S2/S3 verdicts must be reported as a
  mean over repeated runs with the run-to-run spread, or measured at a fixed seed / temperature 0,
  with the choice recorded in the conditions line; (2) the same sampling noise makes a live
  verdict for one event non-reproducible — an alert/no-alert decision near the medium threshold can
  flip on a re-run; consider temperature 0 + seed for the assess call, or majority/mean of k samples
  as a cheap S2 lever (it costs latency, S4); (3) the truncation refusal rate (1/450 here) should be
  tracked at the 1,024-token budget.

## Addendum 4 — temperature 0 is deterministic and does not move accuracy (2026-10-03) [V]

EXPERIMENT (not the shipped path): the same 450 sets, same server, same shipped `VlmClient`, with the
request body's `temperature` rewritten to 0 by a transport shim in a scratch driver (the repo is
untouched; each `run.json` carries `sampling_override: EXPERIMENT: temperature forced to 0.0 ...`).

- Two temperature-0 replays, `20261003T134900Z-qwen3-vl-8b-T0` and `20261003T141303Z-qwen3-vl-8b-T0`:
  **identical (verdict, risk_score) on 450/450 items**, both **S2 18/209 = 8.6%, S3 88/241 = 36.5%,
  0 refusals** (compare temperature 0.1: 278/450 identical across two runs; S2 19 and 18, S3 87 and 84).
- The temperature-0 figures sit on the temperature-0.1 means (S2 17.0 = 8.1%, S3 86.3 = 35.8%), so the
  sampling temperature adds NOISE, not a systematic shift. It is not why S3 is 36%.
- Consequence: a single replay at temperature 0 is a reproducible measurement and a valid basis for
  paired A/B comparisons; at 0.1 it is one draw. Recommend the replay driver (and, subject to the
  owner, the shipped assess call) use temperature 0 with the choice stated in the conditions line.
- Later research in this session (HF-tiers workflow, `size-vs-accuracy`) reports that S3 is limited by
  more than calibration: emitted scores are polarized (68% in {0,5,10}), AUROC incident-vs-benign about
  0.70, and 64/241 incidents are stranger/intent scenes (8B hits 2/64) that a single still may not
  separate from their benign twins, capping S3 near 73% on single stills for any model [C, agent
  analysis of the eval store; not yet independently re-derived here]. Treat as a hypothesis to test
  with the free experiments (rubric prompt; logprob score; prompt-by-size 2x2), not a settled fact.

## Addendum 5 — decisions, and where the research now lives (2026-10-03) [O/V]

**Owner decisions [O] (answered in-session):**
1. Run the free S3 experiments on the GB300 now: a severity-rubric prompt arm and a logprob-score
   arm, both at temperature 0 (scratch-driver shims only; no repo change for the experiments).
2. Decide whether S3 >= 90% is attainable from a single still AFTER those experiments (keep the
   bar as is until then).
3. Move the shipped assess call from temperature 0.1 to 0 as a small code change on this branch
   (`backend/services/vlm_client.py`, with a test).
4. Keep running replays with the renderer-stopped check bypassed under the `agent-gpu` fence, and
   label every such run (`renderer_check: SKIPPED ...` in `run.json`).
5. The action-plan register stays in the repo only (no GitHub/Linear filing); everything is
   committed to the current branch; no push unless asked.

**Where the 2026-10-03 research is written down (all uncommitted until the audit finishes):**
- `docs/vss-integration/15` to `18` - progress since the design, errata (E29 onward), the issue
  register, the world-class target (written by the drafting workflow; audited before commit).
- `docs/vss-integration/19-nvidia-accuracy-benchmarking.md` - how NVIDIA's VSS team measures accuracy
  (checkpoint dump, unaudited).
- `docs/vss-integration/20-model-tiers-benchmark-and-training.md` - HuggingFace model picks per GPU
  tier, benchmarks/Harbor/LoRA, and the size-versus-accuracy analysis (checkpoint dump, unaudited).
- This file - the measured replay results (Addenda 1-4).

## Addendum 6 — the temperature-0 change is committed (2026-10-03) [V]

Commit `9f4e65cd` on `docs/synthbench-h3-notes-crossing`: `backend/services/vlm_client.py` now sends
`"temperature": _ASSESS_TEMPERATURE` (`0.0`) on the assess call (it was `0.1`, unseeded). The §6 transport
retry stays explicit at 0 and is now a plain re-send. Tests: `test_assess_samples_greedily` (new; pins
the constant, the wire value and no sampler knobs) and `test_transport_error_retries_once_at_temperature_zero`
(now asserts the first attempt is also 0). Red-first: both fail with the constant at 0.1 (2 failed), pass
at 0.0; `test_vlm_client.py` 70 passed; with `test_vlm_analyzer.py`, `test_vlm_verdict.py` and
`backend/tests/contracts/ai_providers` 474 passed; ruff check + format clean. Authored with a one-shot
`-c user.name/user.email` (the sandbox has no git identity; nothing was written to any git config).

**Follow-ups owed in the docs once the drafting workflow's audit finishes:** the draft register
(`17-action-plan.md`) entry for the unseeded temperature (session intake, ISS-078) should read
"fixed in `9f4e65cd`", with its acceptance condition ("reproducible at a stated temperature") met by the
450/450 temperature-0 replays; and doc 15's description of the shipped assess call should say greedy.
`backend/evaluation/harness.py:554` (the retired Nemotron text-LLM harness) still carries 0.1 and is
unrelated to the VLM path. The replay experiments from here on run at temperature 0 by default, which is
now also what the shipped client does, so the transport shim is no longer needed for that.

## Addendum 7 — the Nemotron prompt-evaluation harness is removed (2026-10-03) [V]

Owner direction: the VLM path is the only supported infrastructure; no backward compatibility is kept.
Commit `d8482861` deletes the retired harness (`backend/evaluation/{harness,prompt_evaluator,
prompt_eval_dataset,combined_dataset,ab_experiment_runner,metrics,reports}.py`, six unit tests,
`backend/tests/integration/test_nemotron_prompts.py`, `.github/workflows/prompt-evaluation.yml`, two
`prompt-evaluation-results.md` pages) and everything that pointed at it: 43 files, 137 insertions, 7,770
deletions. `backend.evaluation` now holds only the VLM-path modules (`assess_input`, `control_freeze`,
`eval_store`, `label_import`, `levels`, `s_metrics`, `vlm_replay`) and exports nothing. Verified: ruff clean;
5,930 tests pass; `pytest backend/tests --collect-only` collects 32,799 tests with no import errors;
`gen-ai-contract.py --check`, `suppression-registry-gen.py --check` and `check-vss-docs-currency.py` pass; a
repo-wide search finds no remaining reference outside the historical records. Docs 17/18 (drafts) still
describe the harness as present in places; they predate this commit and need a pass when their audit
finishes (register entries about harness CI and the 0.1 site in `harness.py` are now resolved by deletion).

**Neighbors measured but NOT touched (owner decision):**
- `tools/nemo_data_designer/`: 10 files, 5,842 lines. Importers outside `tools/`: two integration tests
  (`test_multimodal_pipeline.py`, `test_enrichment_edge_cases.py`) and the `synthetic_scenarios` /
  `scenario_by_type` fixtures in `backend/tests/conftest.py`. The `nemo` extra (`data-designer`, `pandas`,
  `pyarrow`, `numpy`) exists for it; nothing at runtime or in the VLM path imports pandas or data-designer.
  The committed `data/synthetic` label sets that `eval_store.load_synthetic_items` reads would stay. Per the
  ledger (main-green evidence row on Dependabot), `data-designer-engine` caps `cryptography` and is why the
  Dependabot uv job fails - removing the extra may clear that (needs `uv lock`; not verified here).
- Prompt-management feature (Nemotron prompt templates, versions, A/B config): `backend/services/
  prompt_service.py` 1,115 lines, `backend/config/prompt_ab_config.py` 182, `backend/api/routes/
  prompt_management.py` 629, `backend/models/prompt_version.py` 97 (+ DB migration), and frontend
  components (`PromptPlayground`, `PromptABTest`, `PromptVersionHistory`). Whether the VLM prompt is
  managed through it is not established; it has a DB and UI surface, so verify before deleting.
- Four backend sites still POST to a text-LLM `/completion` (`summary_generator.py`,
  `constrained_decoding.py`, `prompt_service.py`, `pipeline_quality_audit_service.py`) and the contract still
  registers `llm_completion`, `llm_chat_completion`, `llm_slots`; the text LLM they talk to is not deployed.

## Addendum 8 — rubric-prompt and logprob experiments (2026-10-03) [V unless marked]

Owner-approved free experiments (Addendum 5). Same 450 sets, same server and weights, greedy decoding
(the client has sampled at temperature 0 since `9f4e65cd`), renderer-check bypassed and labeled. Both arms
also requested token logprobs through a transport shim (`replay_exp.py`, `analyze_exp.py` and the raw
logprob files are kept at `$AGENT_GPU_DIR/out/experiments/2026-10-03-rubric-logprob/`; the repo client is
untouched). Run ids: arm A `20261003T154038Z-qwen3-vl-8b-armA-shipped`, arm B
`20261003T161804Z-qwen3-vl-8b-armB-rubric`. **Development arms, NOT a holdout:** the rubric was written once
before looking at results and not iterated, but it was written knowing the corpus, so any adoption needs the
frozen dev/holdout split the register already asks for.

**Arm B changes exactly one phrase** of the shipped prompt (`backend/services/vlm_client.py`,
`_render_prompt`): "how threatening it is (risk_score 0-100)." is replaced by a rubric that defines
risk_score as the potential for harm if the scene is as it appears (not whether aggression is visible),
gives the product's own bands (0-29 low, 30-59 medium, 60-84 high with observable examples, 85-100
critical), says a calm person can still be high risk, and says not to raise it for ordinary visitors,
residents, workers or animals. The full text is stored in each arm-B `run.json` under `experiment.rubric_text`.

| | S2 (benign >= medium) | S3 (incidents at floor) | AUROC incident vs benign | recall at 5% false alarms | refusals |
|---|---|---|---|---|---|
| A shipped prompt | 18/209 = 8.6% | 88/241 = 36.5% | 0.703 | 42.3% | 0 |
| B rubric | 34/209 = 16.3% | 105/241 = 43.6% | 0.778 | 53.5% | 0 |

- **Arm A reproduces the earlier temperature-0 runs exactly (88/241, 18/209)**, so requesting logprobs does
  not change the result. It also independently reproduces the research agent's figures: AUROC 0.703 and
  42.3% at 5% FPR, and S3 by scene type of 2/64 stranger-or-intent, 18/82 context-risk, 68/95 object-cued
  [C; groups: stranger/intent = package_theft, loitering, peering_into_windows, trying_car_doors,
  casing_with_phone, tailgating (64); object-cued = firearm_visible, knife_visible, fire_or_smoke,
  masked_intruder_night, forced_entry (95); context-risk = the other 82 incidents].
- **The rubric improves the ranking, not just the threshold:** AUROC +0.075 and recall at a fixed 5%
  false-alarm budget +11.2 points (a single-cut frontier: 42.3% -> 53.5% at S2 <= 5%; 44.8% -> 54.8% at
  S2 <= 8.6%). At the shipped medium threshold it trades 17 more hits for 16 more false alarms.
- **Where it helps and where it costs:** hits by scene type move 2->3/64 stranger-or-intent, 18->32/82
  context-risk, 68->70/95 object-cued. New false alarms are all in hard negatives: flashlight_neighbor
  2->9, landscaper_machete 0->4, power_tools_at_night 4->9, hooded_jogger 10->11 (n=29 each); plain benign
  scenes stay at 1-2 of 64. Net: the gain is almost entirely in context-risk scenes and is partly paid for
  by hard-negative false alarms, so it fails S2 more badly (16.3% vs the 5% bar) while still failing S3.
- **Logprobs hold no hidden ranking headroom** [C, approximation]: a soft score from the first-digit logprob
  distribution has AUROC 0.717 (arm A) and 0.771 (arm B) against 0.703 / 0.778 for the integer score, and no
  gain in recall at 5% FPR. The experiment's decision rule (>= 0.85 means headroom, <= 0.72 means none) puts
  arm A at none. Caveat: only the first digit's alternatives are used; second-digit conditionals were not
  enumerated.
- **What this says about the S3 question the owner deferred:** a prompt-only change moves S3 by about 7 points
  and does not touch the stranger/intent scenes (2 -> 3 of 64), which is consistent with the hypothesis that
  roughly a quarter of incidents are not resolvable from a single still. Even with context-risk and
  object-cued scenes perfect, S3 caps at 177/241 = 73% unless stranger/intent scenes become recoverable
  [C]. Remaining untested levers: model size (the prompt-by-size 2x2 needs the 32B weights, owner-side
  download), higher image-token cap, multi-frame input for the stranger/intent scenes, and a corpus change.

## Addendum 9 — commits, the build finding, and the model sweep (2026-10-03) [V unless marked]

**Commits on this branch (all local until the PR):** `9f4e65cd` assess call greedy (temperature 0);
`d8482861` retired Nemotron prompt-evaluation harness removed; `efa1b586` NeMo Data Designer tooling and the
`nemo` extra removed (and the census baseline `pytest_skip_imperative` 99 -> 86, which `d8482861` had left
red because its verification skipped the repo-root `scripts/` tests); `f0ff083e` `cryptography` 49.0.0 ->
50.0.2 (owner-approved) with the stale ignores removed, `pip-audit` clean; `ab3bd002` M1: the analyzer makes
the notify decision and broadcasts it as `data.notify` (the decision exists; nothing acts on it yet, so M1 is
NOT closed). Then the docs refresh (15-20, banners, index) and ledger row 76 (written as row 75; renumbered at the merge with main, which had appended its own row 75).

**Build sensitivity (found by the sweep's control arm).** llama.cpp `b7972` and the new `b11376` disagree on
the same model, weights and prompt at greedy decoding: control `b11376` S2 21/209, S3 94/241, AUROC 0.677,
2 refusals (both `VlmTruncatedError` at 1,024) against `b7972` S2 18/209, S3 88/241, AUROC 0.703, 0
refusals; only 250/450 items identical (verdict, score), 143 differ by >= 10 points. Cause (build vs the two
cache-protection flags `LLAMA_ARG_CACHE_RAM=0`, `LLAMA_ARG_CACHE_IDLE_SLOTS=0`) is not yet attributed [?].
Consequence: every measured number is a claim about a build; every cross-model comparison must share one
build; register ISS-087.

**The model sweep** (owner decision: evaluate every discovered tier pick on tierb-v0). Orchestrator and
per-arm driver: `$AGENT_GPU_DIR/out/experiments/model-sweep/{sweep.py,replay_arm.py,recipes.json,rubric.txt}`
(session artifacts, not in the repo). One arm at a time because the models mount has ~42 GB free against
~187 GB of weights: download -> sha256 verify -> serve (`ai-vlm:sm103-b11376`, shipped prompt, temperature 0,
one 180 s read timeout for every arm, `LLAMA_ARG_REASONING=off` plus `enable_thinking: false` for the Qwen3.5/
3.6/3.8 and Gemma arms) -> replay 450 -> score -> delete. Results append to `results.jsonl` and `summary.md`;
`sweep.log` is the narrative; the sweep resumes where it stopped. Order: control (done), repeat control
(determinism on `b11376`), default-cache control, then Qwen3-VL-8B Q8_0, Qwen3.5-4B Q8_0, Qwen3.5-9B Q4_K_M and
Q6_K, Gemma-4-12B QAT, Qwen3-VL-32B Q4_K_M, Gemma-4-26B-A4B QAT, Qwen3.8-27B UD-Q4_K_M and UD-Q6_K,
Qwen3-VL-30B-A3B Q8_0, Qwen3.6-35B-A3B UD-Q6_K, and last Qwen3.8-27B IQ2_S (open kernel bug on one quant mix).
At the time of writing the sweep was RUNNING; none of its arm results are claimed here. Known confounders to
state with the results: mmproj precision differs by arm (Q8_0 / F16 / BF16), the Gemma arms use a smaller image
token cap (1,120), and thinking is forced off for the hybrid-thinking families.
