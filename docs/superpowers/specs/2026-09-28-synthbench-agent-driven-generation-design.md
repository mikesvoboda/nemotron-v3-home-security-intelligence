# Synthbench Agent-Driven Generation — Design

**Status:** approved by the owner (2026-09-28), section by section. The written spec awaits owner
review.
**Date:** 2026-09-28
**Branch:** `docs/synthbench-agent-driven-generation`
**Parent spec:** [`2026-09-27-synthetic-benchmark-generation-design.md`](2026-09-27-synthetic-benchmark-generation-design.md)
(rev 3 folds this design in: D9, §3.4, §3.6, §7.3).

Evidence tags, as in the parent spec: **[V]** verified on the host by probe or source read;
**[A]** assumption the implementation plan must confirm first.

## Goal

The owner wants to run Tier B generation together with an agent that runs on the flagship model
(`claude-flagship` = Qwen3.8-Flash-Next, which can see images). This design defines the
tooling and documents that let that agent drive the process:

- write prompts;
- render images;
- look at every image it renders to catch FLUX going off the rails;
- report back.

It must also keep the flagship, which is the agent's own model, serving throughout.

Out of scope: Tier A (sites, cast, compositor, clips), the verifier and audit page (P4), and the
benchmark run (P5). They follow the parent spec unchanged.

## Decisions (owner, 2026-09-28)

| #   | Decision                                                                                                                                                                                                               |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| G1  | **A flagship agent drives Tier B generation from a Docker Sandbox.** The owner works with it and reviews its reports.                                                                                                  |
| G2  | **The renderer is a long-lived host service.** ComfyUI holds FLUX.2 [dev] resident beside the flagship. The agent never touches docker, podman, the GPU or the weights, so it cannot stop the model it runs on.        |
| G3  | **Approach B: library in the sandbox, direct ComfyUI.** The agent runs `synthbench` commands from its repo clone; they call ComfyUI's HTTP API. The owner chose this over a host-side generation service (Rejected).   |
| G4  | **The sampler owns the facts; the agent owns the wording.** The seeded sampler fixes every fact that becomes ground truth. The agent writes the prompt text from those facts, and the text is frozen before rendering. |
| G5  | **The agent looks at every image and may reroll only for mechanical failures** (§4). Acceptance stays with the parent spec's independent verifier and the owner's audit (parent §4).                                   |
| G6  | **Rendering yields to the flagship.** It pauses between images while vLLM reports requests waiting.                                                                                                                    |
| G7  | **Render at 1280×720.** The camera stage produces the 1920×1080 Foscam still.                                                                                                                                          |
| G8  | **`synthbench camera`**, not `degrade`: the stage applies a camera model (format, optics, sensor, overlay, JPEG), and resizing is one part of it.                                                                      |
| G9  | **The corpus is its own ZFS dataset, append-only**, snapshotted every 6 h. Pruning keeps the newest 5 and holds any snapshot that is the last copy of removed or changed media (§6).                                   |
| G10 | **The flagship makes room.** Its KV pin went from 70 to 55 GiB (stack MR !7, applied 2026-09-28). Its util gate drops so it can boot beside a resident renderer (§5.3).                                                |
| G11 | **GPU windows stay owner-only.** They remain for clips and large overnight batches; the agent's documents do not describe them.                                                                                        |

## Measurements this design rests on

All on maui (GB300), 2026-09-28, unless noted.

| Fact                                                                          | Value                                                                                                                                                                   | Tag |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --- |
| Flagship after the KV change                                                  | 2,200,824 tokens (8.40× at 262,144); 183.3 GiB at boot, 186.6 GiB after traffic; ~63 GiB free                                                                           | [V] |
| Flagship KV use, 14 days at 70 GiB                                            | p50 4.3%, p99 60.4%, max 99.9% (one burst, 2026-09-24/25); footprint flat under load (Prometheus)                                                                       | [V] |
| FLUX.2 [dev] beside the flagship                                              | fully resident (`full load: True`); peak 56.2 GiB over the flagship; 50.1 GiB resident between jobs; 7.0 GiB min free (`--reserve-vram 4`)                              | [V] |
| Render time vs size, flagship at its normal load (median 11 running requests) | 1920×1088: 23.3 s; **1280×720: 8.2-8.5 s**; 960×544: 4.7 s (3 images each)                                                                                              | [V] |
| Flagship decode while FLUX renders                                            | 164 → 68 tok/s (−59%); 197 tok/s beside an idle but loaded renderer                                                                                                     | [V] |
| Plate legibility                                                              | `8KXR-417` readable at all three sizes (visual check, 1 image each)                                                                                                     | [V] |
| FLUX draws a fake timestamp bar                                               | at 1280×720 and 960×544 when prompted as security-camera footage                                                                                                        | [V] |
| Real Foscam stills                                                            | 1920×1080 on all 5 cameras (header read, 541 files); median JPEG 120-260 KiB                                                                                            | [V] |
| ZFS delegation on `primary/export/synthbench`                                 | `msvoboda`: snapshot, diff, destroy, mount; child dataset `…/corpus` exists; snapshot, diff, destroy tested                                                             | [V] |
| systemd user lingering                                                        | `Linger=yes`                                                                                                                                                            | [V] |
| A sandbox reaches host loopback ports                                         | `http://host.docker.internal:8188` answered from a fresh sandbox; `127.0.0.1:8188` did not (P3 probe, 2026-09-28, `docs/benchmarks/synthbench/p3-probes.md`)            | [V] |
| The sandbox agent's image reads reach Qwen vision                             | through LiteLLM's `/v1/messages` translation: a known word read back exactly (P3 probe, 2026-09-28, `docs/benchmarks/synthbench/p3-probes.md`)                          | [V] |
| Sandbox mounts under `/export`                                                | fail at `sbx create` (`policybind` cannot stat `/mnt/host/export/…`); the dataset now mounts at `/synthbench`, with `/synthbench` a host symlink (P3 probe, 2026-09-28) | [V] |

## §1 Architecture

**Host (maui).** The owner and host tooling own everything here; the agent owns none of it.

| Piece                                     | Role                                                                                                                                                                                                                               |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `synthbench-guard` (systemd user unit)    | Always on. Every 5 s writes `/synthbench/status/flagship.json` (`time`, `healthy`, `running`, `waiting`). After 3 failed flagship health checks in a row it stops the renderer. It never stops or starts the flagship.             |
| `synthbench-renderer` (systemd user unit) | Requires the guard. Starts ComfyUI (`127.0.0.1:8188`, `--reserve-vram 4`) only when the flagship is healthy and its util gate is ≤ 0.76 (§5.3), then renders one warm-up image so FLUX.2 is resident before the agent's first job. |
| `synthbench-snapshot.timer`               | Every 6 h: snapshot the corpus dataset, then prune by the rule in §6.                                                                                                                                                              |
| Corpus dataset                            | `primary/export/synthbench/corpus` at `/synthbench/corpus`.                                                                                                                                                                        |

**Sandbox.** The agent runs on `claude-flagship`. `agent-dgx` creates the sandbox with:

- its workspace: a clone of this repo on a working branch, where it runs `uv run synthbench …`;
- `--mount /synthbench/corpus:rw`: the images it writes and views;
- `--mount /synthbench/status:ro`: the flagship status file;
- a route to `host.docker.internal:8188`, and nothing else new.

The flagship guard is the only thing that can stop the renderer automatically, and only the owner
or the stack's `swap.sh` restarts the flagship.

## §2 Corpus layout and the append-only rule

The parent layout (§2.6) under `/synthbench/corpus/<version>/` gains a batch directory.
Tier B v0 is version `tierb-v0`.

```
<version>/events/B/<id>/spec.json          # facts (sampler) + frozen prompt (§3)
<version>/events/B/<id>/provenance.json    # every attempt: seed, prompt hash, model hashes, timings, sha256 of each output, triage verdict
<version>/events/B/<id>/renders/a<k>-s<seed>.png   # raw 1280x720 render, attempt k
<version>/events/B/<id>/stills/a<k>-s<seed>.jpg    # camera output, 1920x1080
<version>/batches/<batch>/batch.json       # event ids, sampler seed and filter
<version>/batches/<batch>/prompts.jsonl    # the agent's prompts, one row per event
<version>/batches/<batch>/triage.jsonl     # the agent's verdicts
<version>/batches/<batch>/report.md, sheet.html
<version>/index.jsonl                      # one row per event state change; the latest row wins
```

**Append-only.** No command deletes, moves or overwrites an image or a clip. A reroll writes a new
attempt file and leaves the old one. The only files that change in place are JSON and JSONL
files: prompts frozen into `spec.json`, attempts added to `provenance.json`, and rows appended to
the logs. `provenance.json` records the sha256 of every output, so `synthbench check` detects a
modified or missing image as well (§3).

## §3 The agent's batch loop

| Step | Command                                                         | What it does                                                                                                                                                                                                                                                                                                      |
| ---- | --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | `synthbench sample --batch <b> --n <n> [--only <scenario ids>]` | Writes `n` specs with the facts only (taxonomy cell, camera, conditions, subjects, props, label) and `batch.json`. Same seed, same specs.                                                                                                                                                                         |
| 2    | the agent writes `prompts.jsonl`                                | One row per event: the scene in the agent's words, built from that event's facts.                                                                                                                                                                                                                                 |
| 3    | `synthbench check --batch <b>`                                  | Validates every prompt and lists each failure with its rule; the agent fixes those rows and runs it again. When all pass, it freezes each prompt into `spec.json` as `prompt` plus the fixed `camera_suffix` (§3.1). A frozen prompt never changes; a different prompt is a new event.                            |
| 4    | `synthbench render --batch <b>`                                 | Renders every event whose current attempt has no image, at 1280×720, through ComfyUI. Yields to the flagship (§5.2). Resumes where it stopped.                                                                                                                                                                    |
| 5    | `synthbench camera --batch <b>`                                 | Turns each new render into a 1920×1080 Foscam still (§7).                                                                                                                                                                                                                                                         |
| 6    | the agent looks, writes `triage.jsonl`                          | Opens every still. One row per event: `ok`, or `reroll` plus one reason from §4.                                                                                                                                                                                                                                  |
| 7    | `synthbench triage --batch <b>`                                 | Validates verdicts, enforces the limits (§4), records them in `provenance.json`, and schedules the next attempt for each allowed reroll. Attempt `k` of an event always uses the seed derived from the event id and `k`, so a rerun renders the same images. The agent then runs steps 4-7 again for the rerolls. |
| 8    | `synthbench report --batch <b>`                                 | Writes `report.md` (counts, rerolls by reason, failed events, timings, snapshot holds from `status/snapshots.json`) and `sheet.html` (a contact sheet for the owner).                                                                                                                                             |

Every command exits 0 when done, 1 on an error, and **2 when the agent must stop and ask the
owner**: the renderer is unreachable, the status file is stale, or the batch passed its reroll
limit. The owner runs the same `synthbench check --batch <b>` on the host to confirm a batch
before relying on it. There is no separate intake audit.

**Pilots.** Before the first batch in a new taxonomy area, the agent runs a 10-event pilot to
tune its wording, then full batches of 50.

### §3.1 Prompt rules (`synthbench check`)

1. **Every required fact is mentioned.** Each subject and prop in the spec has a term list in the
   taxonomy YAML. The prompt must contain one term from each list, matched order-insensitively
   by token, as the P1 judge matched prop terms.
2. **Content rules (parent §3.8).** No term from a committed blocklist: graphic injury terms, and
   references to real or famous people. Tier B people are anonymous (parent §1.1), so the handoff
   tells the agent to describe people generically. A blocklist cannot catch every name; the
   owner's audit is the backstop.
3. **Length.** At most the text encoder's configured maximum (1,200 characters; P3 plan ruling
   P3-R4); the plan pins the number from the FLUX.2 workflow.
4. **No overlay text.** The agent does not write camera styling. `check` appends a fixed
   `camera_suffix` that describes the camera look and ends "no on-screen text, no timestamp, no
   watermark". This follows from the measured fake timestamp bar: the camera stage adds the
   real overlay.

## §4 Triage: what "off the rails" means

The agent may reroll an event only for one of these reasons:

| Reason                | Meaning                                                                    |
| --------------------- | -------------------------------------------------------------------------- |
| `blank`               | black, white, flat or noise image                                          |
| `refusal_card`        | a safety or error card instead of a scene                                  |
| `wrong_scene`         | not the spec's kind of place (indoors for a driveway, a street for a pool) |
| `no_person`           | the spec has people and the image has none                                 |
| `broken_anatomy`      | merged or duplicated bodies, grossly broken limbs                          |
| `not_security_camera` | the image does not read as a fixed security camera's view                  |
| `text_overlay`        | a timestamp, watermark or caption drawn into the image                     |

"I cannot make out the knife" is **not** a reason. Whether a prop is visible is a fact for the
independent verifier and the owner. The pipeline under test also uses a Qwen vision model, so
rerolling until Qwen sees the prop would bias the corpus toward images Qwen finds easy.

**Limits.**

- One triage reroll per event. A second triage failure marks the event `failed` in `index.jsonl`,
  and the report lists it; nothing is deleted.
- Triage and the verifier share parent §4.2's cap of 3 seeds per event. Triage spends at most
  one of them.
- If a batch's triage rerolls exceed 10% of its events, `synthbench triage` schedules no further
  rerolls and exits 2.

## §5 GPU sharing and flagship safety

### §5.1 Guard and renderer

The guard (§1) is independent of the renderer, so the status file stays fresh whether or not the
renderer runs. When the guard stops the renderer, a render in flight fails and is recorded like
any failed job; `synthbench render` resumes it later.

The guard acts on the renderer container, not on a model, so it covers anything ComfyUI loads,
including MiniMax-H3 turbo for P6's clips. FLUX.2 (56.2 GiB peak) and H3-turbo (47.4 GiB, P1)
do not fit together beside the flagship, so ComfyUI swaps between them, and mixed work runs
stage-major: stills, then clips. H3 has not run beside the flagship. P6 probes it first, as
FLUX.2 was probed on 2026-09-28, before relying on it. One clip holds the GPU for a minute or
more, so yield is coarser for clips.

### §5.2 Yield

Before each image, `synthbench render` reads `status/flagship.json`. It waits, polling every 5 s,
while `waiting > 0` or `healthy` is false. If the file is older than 30 s, the guard is down and
the command exits 2 instead of rendering blind. Yield handles a _saturated_ flagship. The measured
cost of an in-flight render (flagship decode −59%) is accepted.

### §5.3 The flagship's util gate

vLLM refuses to start unless `util × 249.81 GiB` is free (the profile's measured PyTorch-visible
total). At 0.84 that is 209.8 GiB. With the renderer resident only about 193.6-199.7 GiB is free
(249.81 minus 56.2 GiB at peak, or minus 50.1 GiB between jobs). So a flagship crash would loop
until the guard stops the renderer.

**Set util to 0.76** (189.9 GiB). That passes with the renderer at peak by 3.7 GiB, and stays
3.3 GiB above the flagship's steady 186.6 GiB, so a boot that passes the gate has room to load.
0.77 was considered and passes at peak by only 1.2 GiB. The change goes through the stack's usual
path (branch, MR, `swap.sh`, a real request afterwards). The renderer unit checks the live value
and refuses to start above 0.76.

## §6 Snapshots and the prune rule

`synthbench corpus snapshot` runs from the timer:

1. Take `primary/export/synthbench/corpus@synthbench-<UTC time>`.
2. While more than 5 `synthbench-` snapshots exist, look at the **oldest** only. Run
   `zfs diff <oldest> <next>` and ignore directory entries: adding or removing a file marks its
   directory `M`.
   - **A removed file, or a modified image or clip** (`.png`, `.jpg`, `.mp4`) → the oldest
     snapshot holds the only copy. **Hold:** stop pruning, and write `status/snapshots.json` with
     the snapshot name, the count and the first 20 paths. A run with no hold rewrites it as
     empty.
   - **Only JSON or JSONL files modified** → expected churn: destroy the oldest and repeat.
3. Never skip past a held snapshot. Only the oldest is ever destroyed, so no deletion can slip
   through a gap.

The owner resolves a hold in one of two ways:

- copy the files back from `/synthbench/corpus/.zfs/snapshot/<name>/`; or
- accept the loss and `zfs destroy` the snapshot.

Snapshots accumulate beyond 5 until then. The append-only rule keeps them cheap.

**Known gap.** A file created and deleted within the same 6 h is in no snapshot. ComfyUI's own
copy in `/synthbench/comfy-out` is the fallback for renders.

## §7 Render size and the camera stage

Render at **1280×720**. It is exact 16:9 and a 1.5× scale to the camera's 1920×1080, and it was
2.8× faster than 1920×1088 at the flagship's normal load. `synthbench camera` then applies:

- a Lanczos resize to 1920×1080;
- per-camera-type lens distortion;
- sensor noise;
- IR-night grayscale and bloom when the spec's condition is IR night;
- the timestamp overlay, in the Foscam style with the spec's scene time;
- JPEG at Foscam-like quality.

`synthbench camera calibrate` runs on the host, by the owner: it reads the real footage, which no
sandbox mounts. Until it fits these to that footage (parent D13), the stage uses
default parameters committed with it. Calibration is a follow-up plan (owner ruling 2026-09-28,
P3-R3). Each still records which parameter set produced it.

**960×544 is rejected for now.** It was 5× faster, and its plate was readable in one image. It is
revisited only if the pilots show faces and small props surviving at 1280×720 with margin to
spare.

**Render size is part of the corpus version's identity.** The same seed composes a different image
at a different size, so `corpus.json` records the render size.

## §8 Documents

| Document                               | Reader             | Holds                                                                                                                                                                                                                                                                                                                                                                                                           |
| -------------------------------------- | ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/synthbench/agent-handoff.md`     | the flagship agent | "Start here if you are the agent driving synthbench generation." Modeled on `docs/superpowers/plans/2026-09-28-a5500-operator-handoff.md`. Covers what the run is, what the agent can and cannot do, the loop (§3), the triage reasons and limits (§4), what a report must say, a **stop-and-ask list** (every exit 2, any `check` failure on sampler output, any content-rule doubt) and what is out of scope. |
| `docs/synthbench/command-reference.md` | the agent          | Each command's inputs, outputs, files written and exit codes. A unit test compares it with the argparse definitions so the two cannot drift.                                                                                                                                                                                                                                                                    |
| `docs/synthbench/operator-runbook.md`  | the owner          | Start and stop the renderer; read the guard; resolve a snapshot hold; the `agent-dgx` command that creates the agent's sandbox with its two mounts; review a batch report.                                                                                                                                                                                                                                      |
| `docs/synthbench/AGENTS.md`            | any agent          | Directory guide, per repo convention.                                                                                                                                                                                                                                                                                                                                                                           |

## §9 Build scope, testing and acceptance

**Built before handoff** (test-first, task-reviewed, as in P1), in two plans:

1. **P2: contract and sampler** (parent §7.3, no GPU). Pydantic `spec`, `truth` and `provenance`
   models, a Tier B v0 taxonomy slice with per-fact term lists, the seeded sampler, and
   `synthbench sample`.
2. **P3: agent-driven Tier B generation.**

   - The agent's commands (`check`, `render`, `camera`, `triage`, `report`) under one
     `synthbench` entry point.
   - The host units (guard, renderer, snapshot timer) and `synthbench corpus snapshot`.
   - The stack changes: util 0.76, and an explicit sandbox route to port 8188.
   - The four documents.

   Its first tasks confirm the two **[A]** assumptions:

   - a fresh sandbox reaches `host.docker.internal:8188`;
   - an image read by the sandbox agent reaches Qwen's vision input through LiteLLM.

   If either fails, the plan stops for an owner decision.

**Unit tests** (no GPU, no network):

- sampler determinism and quota coverage;
- every `check` rule, including the suffix;
- yield, including the stale-status exit;
- rerolls never touching an existing file;
- triage limits and the shared seed cap;
- sha256 integrity in `check`;
- the prune rule, against recorded `zfs diff` output with directory `M` lines;
- the camera stage's output size and format;
- the command reference matching argparse.

**Acceptance: a live handoff dry run.** A flagship agent in a fresh sandbox, given only
`docs/synthbench/agent-handoff.md`, completes a 10-event pilot and then a 50-event batch. It
passes when:

- the report arrives;
- the owner's host `synthbench check` passes on the batch;
- the flagship stays healthy throughout;
- the owner does nothing but read the report and answer stop-and-ask questions.

## §10 Risks

| #   | Risk                                                                                                                  | Mitigation                                                                                                   |
| --- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| R1  | Image reads may not reach Qwen's vision input through LiteLLM **[A]**                                                 | The first P3 task verifies it with a known image; the owner decides if it fails.                             |
| R2  | The sandbox route to 8188 relies on host-loopback reachability, which closing the LiteLLM bypass could remove **[A]** | An explicit, named route in the stack, verified from a fresh sandbox.                                        |
| R3  | The agent stalls mid-batch (observed on this model)                                                                   | Every command resumes; `report` shows progress so far; the owner nudges it.                                  |
| R4  | The agent edits its library to skip a rule (approach B)                                                               | The owner's host `check` re-validates rules and sha256s; its code changes are diffs on its branch.           |
| R5  | Triage biases the corpus toward what Qwen sees                                                                        | Enumerated mechanical reasons only, one reroll per event, a 10% batch cap, every attempt kept and logged.    |
| R6  | Renders slow every flagship user by about 59%                                                                         | Accepted cost. Yield prevents stacking on a saturated flagship; the owner can stop the renderer at any time. |
| R7  | ComfyUI has no authentication, and every sandbox can reach the route                                                  | Accepted on this single-user host. Only mounted paths are writable by the container.                         |
| R8  | Faces and small props at 1280×720 are measured on 3 images only                                                       | Pilots, then the P4 verifier and the owner's audit. 960×544 stays rejected until measured.                   |
| R9  | Unresolved snapshot holds accumulate                                                                                  | Every batch report shows current holds.                                                                      |

## Rejected

- **A: a host-side generation service in front of ComfyUI.** Every rule would be enforced where
  the agent cannot change it, but it was the most to build and operate. The owner chose B; R4's
  host-side `check` is the backstop.
- **C: a file drop and a host runner.** No network API, but a clumsy loop of status files and
  rerolls for an agent that stalls.
- **Full accept/reject by the agent's vision.** The best-looking corpus, but biased toward Qwen and
  unmeasurable. The flagship's judgments agreed with the owner's at chance (κ 0.06, P1).
- **View-and-report only.** No bias, but broken prompts would be caught late.
- **Always render / scheduled hours.** Always rendering stacks renders onto a saturated flagship.
  Scheduled hours protect daytime work but waste off-peak time the yield rule already uses.
- **Blind rotation of 5 snapshots.** It destroys the last copy of anything deleted more than
  about 30 h earlier.
- **Pruning on a snapshot's `used` value.** Data deleted after several snapshots is shared among
  them, so each shows `used ≈ 0` while together they hold the only copy.
- **Rendering at 1920×1088.** The real stills are 1920×1080 but heavily compressed, and the camera
  stage discards the detail. It is 2.8× slower.
- **Naming the stage `degrade`** (it also scales up) or **`capture`** (it collides with P0's
  capture time).
- **util 0.77.** It passes the gate with the renderer at peak by only 1.2 GiB.
