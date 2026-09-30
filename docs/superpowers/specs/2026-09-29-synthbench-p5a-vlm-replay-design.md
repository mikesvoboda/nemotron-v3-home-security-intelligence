# Synthbench P5a: VLM Replay Scoring — Design

- **Date:** 2026-09-29
- **Status:** design approved section by section by the owner on 2026-09-29; this document awaits
  the owner's review before the plan.
- **Amended:** 2026-09-29, decisions A6 (the ideal detector) and A7 (Cosmos reasons first), the
  owner's answers to the plan's Task 1 live probe.
- **Parent spec:** `docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md`
  (§2.7 export, §4.3 audit, §5 runner, §6 scorer). This design splits the parent's P5 into P5a
  (this document) and P5b (the live `hsi-bench` instance, designed later).
- **Corpus:** `tierb-v0`, 460 events drawn (pilot-1, batch-1 to batch-5), 459 `ready`, 1 `failed`.

## Goal

Get the first scored result from the synthbench corpus. The question: how well does the product's
VLM, Qwen3-VL-8B-Instruct Q4_K_M, judge 450 synthetic Tier B stills, and how do the flagship and
Cosmos-Reason2-8B compare on the same stills?

P5a scores the VLM's verdict only, through the existing VSS replay harness. It does not run the
detector, the specialists or the live pipeline; P5b does.

## Decisions (owner, 2026-09-29)

| #   | Decision                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | **The GB300 hosts the benchmark.** It measures accuracy only: latency and memory fit on the shared GB300 do not represent the owner's deployment, and the report says so.                                                                                                                                                                                                                                                                 |
| A2  | **Declared truth plus an owner audit.** P5a scores the sampler's declared facts, labelled unverified, with an audit of 60 stills that measures the truth's error rate. This overrides parent §6.1's "only `verified` and `audited` facts are scored" for P5a; P4's verifier is not a prerequisite.                                                                                                                                        |
| A3  | **Staged P5.** P5a replays the VLM on stills (this document). P5b brings up the live pipeline on arm64 and scores every stage. P5a is a direct-call harness, which parent D1 kept out of scope; the owner chose it as the first stage.                                                                                                                                                                                                    |
| A4  | **Comparison models:** the flagship and Cosmos-Reason2-8B replay the same items. Cosmos is served with vLLM.                                                                                                                                                                                                                                                                                                                              |
| A5  | **Bring up what exists.** The product's `ai-vlm` service, its sm_103 image and its weights already exist on this host from the VSS work. P5a brings them online; it builds no new VLM service.                                                                                                                                                                                                                                            |
| A6  | **Ideal detector** (owner, after the Task 1 probe). Each exported set carries the event's declared subjects and props as detections: object type, confidence 1.0, no box. With `Detections: []` the shipped prompt made the VLM answer `uncertain`, 0 on most stills; in production the VLM runs only after the detector fires. Optimistic: a real detector misses some objects.                                                          |
| A7  | **Cosmos reasons first** (owner, after the Task 1 probe). Cosmos-Reason2-8B looped inside the verdict's first text field under the schema. For Cosmos only, the replay adds its model card's `<think>` format instruction as a system message, gives it 4096 tokens and 120 s, and vLLM serves it with `--reasoning-parser qwen3`. The product prompt is unchanged for Qwen3-VL-8B and the flagship; the flagship runs with thinking off. |

## Measurements this design rests on (2026-09-29)

| Fact                                          | Value                                                                                                                                                                                                                        |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ready events by group                         | threat 196, suspicious 45, hard_negative 145, benign 64, ambiguous 9                                                                                                                                                         |
| Exported items (ready, not ambiguous)         | 450: 241 incidents (S3's denominator), 209 benign (S2's)                                                                                                                                                                     |
| IR-night events                               | 53 threat, 53 hard negative                                                                                                                                                                                                  |
| The product VLM's weights                     | `Qwen3VL-8B-Instruct-Q4_K_M.gguf` (5.0 GB) and `mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf` (0.8 GB) in `/agents/agent-vss1/gpu/models/vlm/`, the compose default pair                                                             |
| Other VSS bake-off weights in the same folder | Qwen3VL-4B-Instruct Q4_K_M, NVIDIA-Nemotron-Nano-12B-v2-VL Q4_K_M                                                                                                                                                            |
| The `ai-vlm` image for sm_103                 | `localhost/agent-vss1/ai-vlm:sm103-v12` (llama.cpp `b7972-e06088da0`) is the product's build; `:sm103-b11090` is Nemotron-12B-VL's; both in the agent-gpu store (uid 1001), built 2026-09-25                                 |
| Cosmos-Reason2-8B                             | `/export/models/hub/models--nvidia--Cosmos-Reason2-8B` (17 GB)                                                                                                                                                               |
| The flagship                                  | `nvidia/Qwen3.8-Flash-Next-NVFP4`, served as `claude-flagship` by `vllm/vllm-openai:nightly-aarch64` on `127.0.0.1:8000`                                                                                                     |
| GPU                                           | 256.7 GB total; flagship 191.5 GB; renderer 52.1 GB while it runs, so 12 GB free then and about 64 GB free with it stopped                                                                                                   |
| The importer's timestamp                      | `import_generated_items` stamps every item `1970-01-01T00:00:00+00:00`; replay pins `camera_timezone=None`, so the prompt shows that string (midnight UTC) for every scene. P5a's export declares each scene's time (Task 2) |

## §1 Flow

1. **Export.** `synthbench export vss` writes every ready, non-ambiguous Tier B event in the layout
   the VSS eval store imports (§2).
2. **Import.** `import_generated_items` loads the export into an eval store at
   `/synthbench/eval/<version>/`. It stays the single label authority.
3. **Serve and replay.** The product's `ai-vlm` serves Qwen3-VL-8B (§3). The existing
   `backend/evaluation/vlm_replay.py` runs every item through the shipped `VlmClient`. The
   comparison models replay the same items (§3).
4. **Audit.** `synthbench audit` shows the owner 60 stills and records a verdict per fact (§4).
5. **Score.** `synthbench score` joins the replay results, the export's facts and the audit, and
   writes the report (§5).

**Stated conditions**, printed on the report's first line:

- the truth is declared by the sampler, with the audit's error bar;
- stills with an ideal detector (A6): the VLM gets each event's declared subjects and props as
  detections, and no specialist context; detection is optimistic, specialists are absent;
- accuracy only (A1);
- ambiguous events are excluded, because S2 and S3 do not count them.

## §2 Export: `synthbench export vss`

**Selection.** Every Tier B event whose latest index status is `ready`, with the still of its last
attempt. Events not exported are counted by reason in the export's summary: failed, not ready, or
ambiguous.

**Layout**, under `/synthbench/exports/<version>/vss/` (outside the append-only corpus and outside
the repo, as the eval store's residence guard requires):

```
threats/B-batch-1-003/expected_labels.json
threats/B-batch-1-003/still.jpg      a copy of the ready still
threats/B-batch-1-003/still.json     its attribution sidecar
```

**Category** from the scenario's group. The directory is the eval store's label authority
(`resolve_category_label`):

| synthbench group      | Directory     | Eval label |
| --------------------- | ------------- | ---------- |
| benign, hard_negative | `normal/`     | benign     |
| suspicious            | `suspicious/` | incident   |
| threat                | `threats/`    | incident   |
| ambiguous             | not exported  | —          |

The export checks that each event's own label equals its directory's label and exits 2 if they
ever differ: that would be a taxonomy bug.

**`expected_labels.json`:**

- `category`, and `risk` as `{"min_score": lo, "max_score": hi}` from the event's risk band: the
  keys the importer reads today (it takes the band's midpoint as the expected score).
- `timestamp`: the scene time on a fixed date in the camera timezone (`America/New_York`). Snow
  scenes use 2026-01-15, every other scene 2026-04-15, so the date never contradicts the weather.
- `detections` (A6): one row per declared subject, then per declared prop,
  `{"object_type": <class>, "confidence": 1.0}`: no box, no role or attribute. The importer
  already reads this key into the item's snapshot, so the replay prompt shows it.
- `synthbench`: the event id, corpus version, cell, label, risk band, subjects, props and the
  still's sha256. The importer ignores it; the scorer reads it.

**Attribution sidecar** (`still.json`): `license` names the FLUX.2 [dev] license and `artist`
reads "synthbench <version>, FLUX.2 [dev] (synthetic)", which the importer's attribution guard
requires.

**Idempotent.** Each set is written once, through a temporary file and a rename. A re-export skips
a set whose content is identical and exits 2 if it would differ. Import is immutable by item id.

**The one change to VSS code.** `import_generated_items` (`backend/evaluation/label_import.py`)
accepts an optional `timestamp` key: an ISO-8601 time with a UTC offset. A malformed value refuses
that set, loudly, as the importer refuses other bad sets. A file without the key keeps the epoch
sentinel, so every existing import behaves as before.

## §3 Serving and replaying the models

| Model                                   | Served by                                                                                                                                                                                                    | Client                                                                                   | GPU memory        |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- | ----------------- |
| **Qwen3-VL-8B** (the product)           | the product's `ai-vlm` compose service (`docker-compose.prod.yml`, profile `vlm`), with its shipped settings: 32k context, 2 slots, q8_0 KV cache, flash attention                                           | the shipped `VlmClient`, unchanged: build pin through `/props`, JSON enforced by grammar | ~11 GB (measured) |
| **Cosmos-Reason2-8B**                   | vLLM (`vllm/vllm-openai:nightly-aarch64`, the flagship's image) in our rootless podman store, `--gpu-memory-utilization` sized to about 20 GB, on `127.0.0.1:8099` (`replay` reads `$SYNTHBENCH_COSMOS_URL`) | the shipped `VlmClient`, probe off, per-model conditions (below)                         | ~25 GB (measured) |
| **The flagship**                        | the running flagship (`127.0.0.1:8000`)                                                                                                                                                                      | the shipped `VlmClient`, probe off, per-model conditions (below)                         | none extra        |
| Qwen3-VL-4B, Nemotron-12B-VL (optional) | `ai-vlm`, as the product model                                                                                                                                                                               | the shipped `VlmClient`                                                                  | ~5–10 GB          |

**Bringing up `ai-vlm`.**

- A new `.env.bench` holds this host's values: `AI_MODELS_PATH=/export/models/ai_models`,
  `CUDA_ARCHITECTURES=103`, `GPU_LLM=0`, the ports, and `CAMERA_TIMEZONE=America/New_York`.
  `.env.example` cannot render compose here (the A5500 checklist records why). P5b grows
  `.env.bench` into the `hsi-bench` env file.
- The weights are copied, read-only, from `/agents/agent-vss1/gpu/models/vlm/` into
  `/export/models/ai_models/vlm/`, with their sha256s recorded. P5a does not mount another agent's
  workspace.
- The image is the same Dockerfile at the llama.cpp build the VSS bake-off pinned. The plan's first
  task reads that pin from the VSS ledger and either copies the VSS agent's image into our store
  (`podman save | podman load`) or rebuilds it.
- Only `ai-vlm` starts (`up --no-deps ai-vlm`), so compose starts nothing else. (`ai-llm` left
  compose in R8 S2b, main `aaf29361`.) On this host it starts through `podman-compose`: the
  docker-compose plugin drops the CDI GPU device (Task 1's probe; the operator runbook).

**The comparison path** (`synthbench/run/`; plan ruling P5a-R2). The flagship and Cosmos go
through the shipped `VlmClient` too, with its llama.cpp-only enforcement probe (`/props`) turned
off and a transport that names the served model; vLLM serves the same JSON schema through its
structured outputs, and the shipped parser reads the answer. The probe found two models that
cannot answer inside the product's contract, so each comparison model has its own conditions,
recorded per run and printed in the report:

| Model             | Prompt                                  | Thinking           | Budget, read timeout |
| ----------------- | --------------------------------------- | ------------------ | -------------------- |
| Qwen3-VL-8B       | shipped                                 | —                  | 1024 tokens, 25 s    |
| The flagship      | shipped                                 | off                | 1024 tokens, 25 s    |
| Cosmos-Reason2-8B | shipped, plus its `<think>` format (A7) | on, parsed by vLLM | 4096 tokens, 120 s   |

**Replay.** `synthbench replay --model <name>` runs `vlm_replay.run_replay` against the eval store
(for the `ai-vlm` models) or the adapter (for the vLLM models), and writes
`/synthbench/runs/<run_id>/`. The names are `qwen3-vl-8b` (the product), `qwen3-vl-4b`,
`nemotron-12b-vl`, `cosmos-reason2-8b` and `flagship`. Before the first item it checks three things
and exits 2 on any failure:

- the endpoint answers;
- the renderer is stopped: `systemctl --user is-active synthbench-renderer` is not `active` and no
  `synthbench-comfyui` container is running;
- the served model is the one named: for `ai-vlm`, the model file stem that `/props` reports; for
  vLLM, the model id that `/v1/models` reports.

**GPU safety.**

- Replay runs only while `synthbench-renderer` is stopped. Only 12 GB is free while it runs.
- One model is served at a time, and it stays well under 50 GiB, so a flagship restart still
  passes its 0.76 util gate (agent-driven design §5.3), as with the renderer.
- The flagship model replays at concurrency 1: agents share it.

## §4 Audit: `synthbench audit`

**Sample.** 60 exported stills, drawn with a fixed seed and stratified:

| Stratum       | Stills | Why                                              |
| ------------- | ------ | ------------------------------------------------ |
| threat        | 20     | S3's main denominator; a missing weapon hurts it |
| suspicious    | 10     | the rest of S3                                   |
| hard_negative | 15     | S2's hardest cases                               |
| benign        | 15     | the rest of S2                                   |

Within each stratum the stills are allocated across its lighting values in proportion to their
counts (largest remainder), with at least one per lighting value the stratum has, so IR night and
low light are always covered.

**Questions per still** (answers `y`, `n` or `u` for unclear; about 20 s per still):

1. **Scene:** "Does this show <the scenario, in plain words>?" This is the label S2 and S3 rest on.
2. **Threat prop** (threat scenarios only): "Is the <prop> visible?"
3. **People:** "<N> person(s)?"
4. **Conditions:** "Lighting and weather as declared?"

**Serving.** A small page on `127.0.0.1`, keyboard-driven, one still at a time. Answers append to
`/synthbench/audits/<version>/audit.jsonl`; the latest answer per fact wins, so the owner can stop
and resume. The runbook gives the `ssh -L` command for a remote session.

**Use in scoring.**

- Truth error rates per question, with n and a 95% Wilson interval.
- The headline metrics twice: on every exported item (declared truth), and on the audited subset
  whose scene answer is yes.
- An event whose scene answer is no leaves S2 and S3 and is listed as a generation error, never a
  model error.
- Audited facts become `audited` in the parent spec's terms (§2.4).
- The 60 answers are the labelled set for later measuring a judge model's agreement with the
  owner, which P4 needs before trusting an automatic verifier.

## §5 Score and report: `synthbench score`

`synthbench/score/` joins the replay results per model (from the eval store), the export's
`synthbench` blocks and the audit. It computes S2 and S3 by calling
`backend/evaluation/s_metrics.py`, so the benchmark and the VSS harness share one definition.

**Metrics, per model:**

- **S2**, the false-positive rate on benign items at level medium or above (score ≥ 30);
- **S3**, recall on incidents at their expected level, in both of `s_metrics`' forms (all, and
  excluding the unfailable `low` floor);
- refusals (`verification_failed`) and the uncertain rate;
- risk-score error: inside, below or above the declared band, and the distance from it;
- the verdict mix.

Every cell carries n and a 95% Wilson interval; a cell under n = 10 reads "insufficient (n=…)".

**Slices:** scenario, group, lighting (IR night is its own row), weather, property, camera, zone,
and whether camera artifacts were drawn.

**Comparison:** per-item agreement between models on the same items, and the misses one model
makes that another catches.

**Outputs** in `/synthbench/runs/<run_id>/`: `results.jsonl` (one row per item per model),
`metrics.json`, `report.md`, and `report.html` with a failure gallery: incidents scored too low
and benign items scored too high, each with its still, its declared facts and the VLM's reasoning.

**Run identity:** the platform's git SHA, each weight file's sha256, the llama.cpp build (from
`/props`), the vLLM image digest (pinned in the runbook's start command; no endpoint reports it),
each model's conditions (prompt, thinking, budget, read timeout, enforcement probe), the eval
store, and the corpus, export, audit and scoring versions.

**Committed:** the aggregate report, without images or per-item rows, as
`docs/benchmarks/synthbench/p5a-<date>.md`.

## §6 Code layout

| Path                                 | What                                                                                        |
| ------------------------------------ | ------------------------------------------------------------------------------------------- |
| `synthbench/export/vss.py`           | the export; writes files only and imports nothing from `backend`                            |
| `synthbench/run/`                    | `replay` (wraps `vlm_replay`) and the comparison path; may import `backend` (spec §7.1)     |
| `synthbench/score/`                  | `score` and the report; may import `backend`                                                |
| `synthbench/audit/`                  | the audit sampler and its loopback page                                                     |
| `synthbench/commands/`               | `export`, `replay`, `audit`, `score`: owner commands, not in the generation agent's handoff |
| `backend/evaluation/label_import.py` | the optional `timestamp` key                                                                |
| `.env.bench`                         | this host's values for the product's compose services                                       |

## §7 Testing and acceptance

**Tests.** No GPU; every subprocess and HTTP call is faked, as in P3.

| Area       | What the tests check                                                                                                                                                          |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Export     | on a throwaway corpus: the category mapping; ambiguous excluded; a label that disagrees with its directory exits 2; a re-export changes nothing; sidecars; the timestamp rule |
| Importer   | an optional `timestamp` is accepted; a malformed one refuses the set; no key keeps the epoch sentinel                                                                         |
| Round trip | export, then `import_generated_items` into a throwaway eval store; each item's label, expected score, timestamp and media match its event                                     |
| Replay     | `vlm_replay` with an injected fake client; the comparison path against a fake vLLM, parsed by the shipped parser; the three pre-run checks                                    |
| Score      | on constructed results: S2 and S3 equal `s_metrics`' own output; slicing; audit exclusions; the "insufficient" rule                                                           |
| Audit      | the sample is deterministic and fills each stratum; the page's answer and resume handlers, through a test client                                                              |

**Acceptance.** P5a is done when:

1. every ready, non-ambiguous Tier B event is exported and imported, and every skip is listed;
2. the product model's replay covers every item, and S2, S3 and refusals are reported with n and
   intervals;
3. the owner has audited the 60 stills, and the report carries the truth error rates and the
   twice-reported headline metrics;
4. at least one comparison model has replayed the same items;
5. the aggregate report is committed and the full run is under `/synthbench/runs/`;
6. the flagship stayed healthy throughout: the renderer was stopped and the guard stopped nothing.

**Order.** After the 400-event run (done 2026-09-29):

1. a live probe: copy the weights, bring up `ai-vlm`, replay five items, and confirm three things
   the design assumes: the importer accepts the export's set shape and ids, a set with no
   detections and no specialist outputs imports, and one eval store keeps each model's results
   apart;
2. the importer's `timestamp` key;
3. the export;
4. the audit;
5. the vLLM comparison path (Cosmos and the flagship);
6. score and report;
7. the full scored run (owner).

## Risks

- **The llama.cpp build.** A different build from the VSS bake-off's pin would make P5a's numbers
  incomparable with the VSS results. The first task reads the pin from the ledger.
- **Declared-truth errors.** The generation agent reported count drift in about 3% of events
  (11/460), a forced hood in 18 of 19 hooded-jogger events, and undeclared motion blur or lit lamps
  in 6. P5a scores none of those facts except counts, and the audit measures them.
- **An ideal detector (A6).** The declared detections name every subject and prop, including
  props a real detector may miss (a handgun, a ski mask), so S3 may read higher than production's;
  without specialist context it may read lower. P5b measures the production condition. Without any
  detections (the design before A6) the VLM mostly declined to judge: Task 1's probe.
- **Structured outputs differ.** vLLM's structured outputs may constrain differently from
  llama.cpp's grammar; parse failures and refusals are reported per model.
- **The flagship is shared.** Replay adds load to the model the agents use; it runs at
  concurrency 1, in a quiet period.

## Out of scope

The detector, specialists, the live pipeline and latency (P5b); clips and the MiniMax-H3 video round;
Tier A; P4's automatic verifier; burst mode.

## Rejected

- **The live instance first** (one P5). The most faithful, but the first number would wait on the
  whole arm64 bring-up, the riskiest piece.
- **Replay only**, with no P5b. It leaves the detector and specialists unscored.
- **Cosmos converted to GGUF** and served by `ai-vlm`. The owner chose vLLM, which avoids an
  unverified conversion.
- **A new VLM serving command.** The product's `ai-vlm` service, image and weights already exist on
  this host.
