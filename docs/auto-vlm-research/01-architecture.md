# 01. Architecture

> Design proposal; nothing is built. Paths and numbers cited as evidence are as of `origin/main` `9cb9e60b0` (2026-10-23). Back to the [index](README.md).

## 1. What autovlm borrows from autocuda, and what it changes

autocuda's search machinery transfers unchanged in concept. Its measurement and coordination layers assume CUDA, so autovlm replaces them.

| Concept                | autocuda                                                                     | autovlm                                                                                                 |
| ---------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Unit of work           | A brief: one idea, a parent commit, a kind (macro, micro, combine, simplify) | Same                                                                                                    |
| Where a trial lives    | A commit on `autocuda/optimize/<tag>/brief-<K>` in its own worktree          | A commit on `autovlm/<tag>/brief-<K>` in its own worktree                                               |
| What a trial changes   | Arbitrary CUDA source in the editable files                                  | Mostly a declarative **recipe**; code only in plugins behind fixed interfaces (§3.1)                    |
| Who runs the benchmark | The worker, on a locked local GPU                                            | A host-side **executor**, on endpoints it schedules (§3.4)                                              |
| Who sees the answers   | The worker; validation is a separate correctness check                       | Nobody but the **scorer**, which holds labels behind its own uid (§3.6)                                 |
| Ranking                | Direction-aware geomean speedup against the reference                        | Paired scenario-cluster test per GPU tier; see [`02-evaluation.md`](02-evaluation.md)                   |
| Noise                  | Coefficient of variation over reruns                                         | A null-perturbation envelope; reruns are identical under greedy decoding                                |
| Profiling              | `nsys` and `ncu`                                                             | Error analysis on the train split: misses by scenario group, rationales, verdict logprobs               |
| Worker launch          | In-process sub-agents spawned by the manager                                 | Separate sandboxed sessions launched through `agent-dgx` and steered through herdr (§5)                 |
| Reward-hacking review  | A report skill that reads diffs                                              | Mechanical checks on every trial plus an auditor each epoch ([`02-evaluation.md`](02-evaluation.md) §7) |

## 2. Topology

```
 host (GB300) ────────────────────────────────────────────────────────────────────┐
 │                                                                                │
 │  manager: Claude Code session on the host                                      │
 │    │ launches workers ─────────► agent-dgx run … -- <brief>                    │
 │    │ continues / pokes workers ─► herdr agent prompt <id> <text>               │
 │    │ reads ──────────────────────► ledger, findings register, autovlm status   │
 │                                                                                │
 │  sbx sandboxes (one per worker)                                                │
 │  │ Qwen worker: brief → worktree → edit recipe/plugin → autovlm trial submit │ │
 │  │   sees: its worktree, train-split inputs and per-item feedback             │ │
 │  └───────────────┬───────────────────────────────────────────────────────────┘ │
 │                  │ HTTP through the sbx proxy, per-session token               │
 │                  ▼                                                             │
 │  executor (host daemon) ── builds the trial commit, runs replays in fenced      │
 │    │                         agent-gpu containers, owns the endpoint pool       │
 │    │                         and the content-addressed cache                    │
 │    │ raw per-item outputs (no labels)                                           │
 │    ▼                                                                            │
 │  scorer (own uid, Unix socket) ── labels, splits, query ledger                  │
 │    └─ holdout: answers only the owner's `confirm`                               │
 │                                                                                │
 │  trainer lane (queued GPU jobs) ──► model registry (sha256-pinned artifacts)   │
 └────────────────────────────────────────────────────────────────────────────────┘
          front candidates ──► Brev tier confirmation (16 / 24 / 32 GB cards)
                           ──► OD-26 holdout confirmation ──► owner ruling ──► product PR
```

## 3. The units

Each unit has one job, a stated interface, and stated dependencies.

### 3.1 Recipe

**Job:** describe one complete detection stack, so that a trial is a diff of a small file. **Interface:** a YAML document validated against a versioned schema. **Depends on:** the model registry (artifacts are named by sha256) and the plugin interfaces.

A sketch of the shape, not a schema:

```yaml
recipe: 1
corpus_inputs: realistic # never "oracle"; see 02-evaluation.md §3
perception:
  detector: { model: yolo26, conf: 0.35 }
  specialists: [faces, reid, plates] # each one a registered plugin
  open_vocab: { model: yoloe-26, vocabulary: threat-objects-v1 }
state:
  tracker: { kind: bytetrack, frames: burst }
  rules: [dwell, trajectory-grammar] # deterministic plugins
vlm_input:
  frames: { mode: burst, count: 4, layout: separate } # or mosaic
  crops: { around: persons, max: 2, size: 448 }
  overlays: [set-of-mark] # or track-trail
vlm:
  model: sha256:… # registry artifact, quant included
  build: llama.cpp@b7972 # build is part of the identity (ISS-087)
  server: { ctx: 16384, vision_tokens: 1280, kv: q8_0 }
  prompt: templates/assess-v3.j2
  thinking: off
adapter: null # or a registered LoRA artifact
decision:
  head: vlm-score # or a fusion model artifact; see 04-system-1-research.md
```

A trial that only changes `decision` re-scores cached upstream outputs on a CPU in seconds. A trial that changes `vlm.prompt` replays the VLM stage on cached perception. A trial that changes `perception` reruns everything downstream of it.

### 3.2 Search manifest

**Job:** say what a worker may change. **Interface:** an allow-list of recipe keys, plugin directories and template directories. Everything else in the worktree is read-only to the trial: a trial whose diff touches a path outside the manifest fails before it runs. The scorer, the export, the splits and the synthbench taxonomy are never in a worktree at all.

### 3.3 Blinded inputs

**Job:** give the stack what a camera would give it, and nothing that encodes the answer. **Interface:** per item, the frames, the scene timestamp and an opaque item id. **Excludes:** labels, scenario names, generation prompts and the declared subjects and props.

Evidence for the last exclusion: the synthbench VSS export writes each still beside an `expected_labels.json` that carries the label, the scenario facts and the declared subjects and props as an ideal detector's `detections` at confidence 1.0 (`synthbench/export/vss.py`, `labels_document` and `declared_detections`). Anything that can read that directory can read the answers, so autovlm builds its inputs from the corpus through a separate blinding step.

### 3.4 Executor

**Job:** turn a submitted trial into raw per-item outputs, reproducibly. **Interface:** a token-gated HTTP API on one host loopback port, reached from sandboxes through the sbx proxy: `submit(commit) → trial id`, `status(trial id)`, `result(trial id)`. Long operations are polled, never streamed, so a proxy idle timeout cannot cut a long replay; the `agent-gpu` runner uses the same rule. **Depends on:** `agent-gpu` for fenced containers and VRAM admission, the cache, the scorer.

For each trial the executor:

1. Checks the diff against the search manifest and runs the mechanical checks that need no labels ([`02-evaluation.md`](02-evaluation.md) §7).
2. Builds the trial commit in a fenced `agent-gpu` container. Agent-written plugin code runs only there, never on the host.
3. Leases an endpoint for the recipe's `(model, build, server settings)` key, starting one if needed, inside the global VRAM budget. Trials that share a key share an endpoint.
4. Runs each stage whose cache entry is missing, writes raw outputs and resource readings, and hands the outputs to the scorer.

One executor for the whole run makes VRAM a scheduling problem it solves, instead of a race between workers that each start their own servers.

### 3.5 Cache

**Job:** never compute the same stage output twice. **Interface:** content-addressed entries keyed by `(stage, stage-config hash, input sha256, build identity)`. Greedy decoding makes VLM outputs a pure function of that key; the sweep's controls matched on 450 of 450 items. The cache is the reason C1 trials exist ([`03-idea-catalogue.md`](03-idea-catalogue.md)).

### 3.6 Scorer

**Job:** join outputs to labels and answer only what each split tier allows. **Interface:** a Unix socket, not a TCP port, so nothing inside a sandbox can reach it (the sbx proxy carries TCP only, and every host loopback TCP port is reachable from every sandbox under the default allow-all policy). **Runs as** its own user, owning the label files with mode 600. A sandbox escape lands as the owner's uid, so labels owned by a separate user stay unreadable even then; the host-side manager cannot read them either.

| Tier    | Answer                                              | Who may ask                     |
| ------- | --------------------------------------------------- | ------------------------------- |
| train   | Per-item outcome, model rationale, verdict logprobs | Workers, through the executor   |
| select  | Aggregates and scenario-cluster intervals only      | Workers and manager             |
| holdout | One OD-26 confirmation per candidate                | The owner's `confirm` verb only |

Every select query is written to a query ledger, so the manager can see how often a select set has been reused ([`02-evaluation.md`](02-evaluation.md) §2).

The Claude manager runs on the host as the owner's user, so the scorer cannot tell the owner from the manager by uid. `confirm` therefore accepts only root, reached through `sudo` with the owner's password; if the owner's `sudo` does not prompt, holdout confirmation moves to a host no agent runs on.

### 3.7 Ledger

**Job:** hold the run's state, so that no agent needs to remember it. **Interface:** append-only rows, written through the `autovlm` CLI, which owns locking and validation. Row kinds follow autocuda's: `baseline`, `brief`, `brief_start`, `brief_continue`, `trial`, `brief_stop`, `retroactive`, plus `epoch` and `front_change`. The manager rebuilds its view from `autovlm status` after compaction or takeover, never from its own context.

### 3.8 Findings register

**Job:** carry what the project has learned across briefs, epochs and runs, so agents do not re-buy known results. **Interface:** rows the manager writes and the auditor can retract.

| Field      | Content                                                                               |
| ---------- | ------------------------------------------------------------------------------------- |
| claim      | A mechanism, in one sentence ("placing the verdict before the reasoning lowers S3")   |
| effect     | Size and scenario-cluster interval                                                    |
| conditions | Corpus version, build, model and quant, input mode, decision head                     |
| evidence   | Trial ids, or a document for seeded rows                                              |
| status     | `supported`, `refuted`, `inconclusive`, or `stale` once its conditions no longer hold |

Rows hold mechanisms and aggregates, never item ids or scenario names; a mechanical check rejects a row that names taxonomy vocabulary. Without that rule the register would carry knowledge of the select set from one epoch into the next. Workers do not query the register; the manager quotes the relevant rows into each brief. The register starts seeded from the sweep, docs 20, 22 and 23 of `docs/vss-integration/`, and the ISS-086 ceiling study ([`03-idea-catalogue.md`](03-idea-catalogue.md) §9).

### 3.9 Manager

**Job:** steer the search. It writes briefs with a parent and a kind, keeps the in-flight briefs diverse, reads the Pareto front, starts epochs, requests fresh scenario batches and Brev confirmations, and maintains the findings register. **Runs as** a Claude Code session on the host, because it needs `agent-dgx`, herdr and the ledger, none of which a sandbox can reach. **Waits** on `autovlm wait`, one blocking command that returns on the next ledger event, never on a polling shell.

### 3.10 Worker

**Job:** build and measure one brief. **Runs as** a flagship-Qwen Claude Code session in its own sbx sandbox, launched with its brief. **Uses** a small CLI that does the deterministic work: `autovlm brief show`, `autovlm trial submit`, `autovlm trial wait`, `autovlm trial show` (train-split detail only), `autovlm log`. Each verb is idempotent and keeps its state on disk, so a worker that stalls mid-brief is re-poked and resumes; nothing is lost but time. Workers follow autocuda's worker rules: stay on brief, build the idea rather than argue about it, commit what was measured, and report measurements, not verdicts.

### 3.11 Trainer lane

**Job:** run trials that take hours: LoRA training, distillation, system-1 model training. **Interface:** a queue the manager writes to; each job produces a sha256-pinned artifact in the model registry, which recipes then reference. Training reads only the train split and public datasets.

### 3.12 Auditor

**Job:** catch gaming that mechanical checks miss. **Runs as** a Claude session at the end of each epoch over every trial that changed a front. It reads diffs and recipes, and can reclassify a trial after the fact, which removes it from the front and taints its descendants (autocuda's `retroactive-failure` rule). Details in [`02-evaluation.md`](02-evaluation.md) §7.

## 4. The `autovlm` CLI, sketched

| Verb                             | Who              | Does                                                              |
| -------------------------------- | ---------------- | ----------------------------------------------------------------- |
| `init`                           | manager          | Creates a run: tag, config, schema snapshot, baseline trial       |
| `brief new` / `brief continue`   | manager          | Records a brief or a continuation in the ledger                   |
| `brief show`                     | worker           | Prints the brief, its parent recipe and the quoted findings       |
| `trial submit` / `wait` / `show` | worker           | Submits a commit to the executor, waits, reads train-split detail |
| `log`                            | worker, manager  | Appends lifecycle rows (`brief_start`, `brief_stop`, …)           |
| `status`                         | manager          | Pareto front per tier, open briefs, progress, select-query budget |
| `wait`                           | manager          | Blocks until the next ledger event                                |
| `findings add` / `retract`       | manager, auditor | Maintains the findings register                                   |
| `eval <recipe>`                  | human            | One-shot evaluation outside any run (phase P1)                    |
| `confirm <trial>`                | owner            | The single holdout confirmation for a candidate                   |

## 5. Communication

The design is hub-and-spoke. The manager is the only party that talks to workers, and workers talk to nobody. Peer messaging would let workers herd toward a neighbour's latest result (keeping briefs diverse is the manager's job), let one stalled worker block another, and move decisions into chat that no ledger records.

| Direction           | Message                                 | Carrier                                                     |
| ------------------- | --------------------------------------- | ----------------------------------------------------------- |
| manager → worker    | a new brief                             | `agent-dgx run … -- <brief prompt>` at launch               |
| manager → worker    | a continuation, or a poke after a stall | `brief_continue` row, then `herdr agent prompt <id> <text>` |
| worker → manager    | a trial finished, a brief returned      | ledger rows; `autovlm wait` wakes the manager               |
| trainer → manager   | an artifact is registered               | registry row and a ledger event                             |
| auditor → manager   | a trial is reclassified                 | `retroactive` ledger row                                    |
| workers ↔ endpoints | GPU and endpoint leases                 | the executor's scheduler; no messages at all                |

Workers may read other briefs' committed recipes and return messages from the same run, as autocuda allows, but nothing requires it.

## 6. Network: no ports between agents

Sandboxes run as microVMs with their own network stacks and cannot reach one another. Their egress goes through the sbx proxy, which by default reaches every TCP port on the host's loopback; the flagship's ports are closed by a port-wide deny rule. (Evidence: the stack repo's `docs/operations/agent-dgx-sessions.md`, network sections, at stack commit `de5dd71`.)

autovlm therefore needs exactly one network path, worker sandbox → executor, and it is token-gated in the same way as the `agent-gpu` runner's API. The design closes the other paths a worker might otherwise use:

- **Endpoints:** workers never call a llama-server. The executor owns the endpoint pool, and a per-sandbox sbx rule denies the pool's ports to worker sandboxes. (The `agent-gpu` design lists cross-sandbox pool-port reachability as an accepted risk; autovlm closes it for its own sandboxes.)
- **Scorer:** a Unix socket only.
- **Files:** worker sandboxes mount their own worktree and the train split's blinded inputs, nothing more. Select and holdout frames are mounted only into the executor's containers, so no agent can look at a select image and label it by eye. The run's control traffic does not use shared files, because sbx shares host directories over virtiofs with aggressive caching: a guest has been measured still seeing host-side renames and deletions until its caches were dropped. A protocol whose correctness depended on that freshness would fail intermittently.

## 7. Failure handling

| Failure                                    | Behaviour                                                                                                                                                      |
| ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A worker stalls or ends its turn mid-brief | The ledger shows the brief open and herdr shows the session idle; after a quiet period the manager, or the stall watch, pokes it. Trial verbs resume from disk |
| A worker session dies                      | The manager relaunches the same brief; `brief_start` already exists, so the worker restarts its loop without a second start (autocuda's restart mode)          |
| An endpoint dies mid-replay                | The executor retries the missing items on a new endpoint; items still unanswered are recorded as unmeasured, never as non-events of a valid run                |
| The executor restarts                      | Its queue is on disk; completed stages are in the cache, so the trial resumes where it stopped                                                                 |
| The scorer is unavailable                  | Fail closed: the trial waits; nothing is ranked without a score                                                                                                |
| A trial breaks a mechanical check          | Logged as a failure with the check's reason, not as a measurement; it cannot enter a front                                                                     |
| Two writers race on the ledger             | The CLI serialises writes under a lock; rows are append-only                                                                                                   |

The prompt programme lost a server mid-arm when its container reached its time limit, leaving 11 tail refusals that were artefacts of the dead server (doc 23 §3). The executor checks an endpoint's remaining lifetime before it starts a long replay.

## 8. Testing the harness itself

- **A known-answer corpus.** A small synthetic corpus with a fake VLM whose outputs are fixed functions of the input, so that every metric, interval and front change has a precomputed expected value.
- **Planted gaming recipes.** A recipe that keys on a scenario word, one that calls everything uncertain, and one that returns a constant score. Each mechanical check must reject its planted recipe.
- **Isolation tests.** From inside a worker sandbox: the scorer socket, the label files, the endpoint ports and the holdout must all be unreachable.
- **Determinism.** Replaying a cached trial must reproduce its scores bit for bit.
- **Stall drills.** Kill a worker mid-trial and confirm that the relaunched worker resumes without double-counting.

## 9. Where the code would live

A proposal, to be settled after the uplevel campaign: a top-level `autovlm/` package with its own `AGENTS.md`, beside `synthbench/`. It drives synthbench and the backend through their command-line and Python interfaces rather than importing their internals, so synthbench's rule that only its `score/` and `run/` packages import `backend` stays intact. The launcher changes live in the stack repo ([`05-stack-integration.md`](05-stack-integration.md)).
