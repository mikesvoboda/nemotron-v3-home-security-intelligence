# Synthbench Clips: MiniMax-H3 Turbo Clip Rounds — Design

- **Date:** 2026-09-30
- **Status:** design approved section by section by the owner on 2026-09-30; this document awaits
  the owner's review before the plan.
- **Parent spec:** `docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md`
  (D4 stills and clips, §3.2 the animator slot, §3.6 the GPU window).
- **Generation design:** `docs/superpowers/specs/2026-09-28-synthbench-agent-driven-generation-design.md`
  (the agent's batch loop §3, triage §4, guard and yield §5).
- **Depends on:** P5a (PR #6732, not yet on `main`): the audit page and sampler in
  `synthbench/audit/`. This branch starts from the P5a branch and rebases onto `main` after #6732
  merges.
- **Corpus:** `tierb-v0`, 460 events, 459 `ready` (9 of them ambiguous), 1 `failed`.

## Goal

Add a second generation mode. The sandboxed generation agent turns ready Tier B stills into
~10 s MiniMax-H3 turbo clips through the long-lived renderer, beside the flagship. The clips are
kept for a future video-capable VLM (parent D4); nothing scores them yet. A 20-clip pilot, which
the owner rates against a bar set in advance, gates volume.

## Decisions (owner, 2026-09-30)

| #   | Decision                                                                                                                                                                                                                                                                   |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1  | **Clips are kept for a video VLM** (parent D4 as written). A clip is stored with its provenance. There is no camera stage, no ingest change and no scoring in this design.                                                                                                 |
| C2  | **The still is frame 0.** First-frame image-to-video, the path P1 measured. The clip shows what happens next.                                                                                                                                                              |
| C3  | **Every ready still is eligible.** There is no qualification gate. Known misses, such as the audit's missing knife (`B-batch-4-039`), carry into their clips; triage and the pilot audit catch bad clips.                                                                  |
| C4  | **A clip is its own event:** `C-<round>-NNN`, pointing at its source still. Still events are never modified.                                                                                                                                                               |
| C5  | **The agent writes the motion; `clip check` enforces the clip rules.** A clip's truth is its still's facts held throughout, with the same label and risk band.                                                                                                             |
| C6  | **Frame 0 is the raw render**, the clean 1280×720 PNG, scaled and centre-cropped to H3's 1344×768 canvas. The camera still's burned-in overlay would be animated.                                                                                                          |
| C7  | **About 10 s, fixed.** The Task 1 probe sets the exact frame count. If a 10 s clip breaks the memory ceiling (§4.3), clips use the longest length that fits, and the probe report says so.                                                                                 |
| C8  | **The host samples each round**: a seeded draw, stratified by group and lighting. The agent writes one motion per clip and cannot choose stills.                                                                                                                           |
| C9  | **The agent triages a frame strip per clip** and may reroll only for mechanical failures, under the stills' 3-seed cap (generation design G5).                                                                                                                             |
| C10 | **The owner's pilot gate.** `synthbench audit --clips` asks three y/n questions per pilot clip. Volume is allowed only if at least 80% of the round's clips pass all three. The gate is written where only the host can write, and it approves one set of clip settings.   |
| C11 | **An explicit mode switch** (approach C). Render commands read ComfyUI's own `/history` to learn which model family ran last, call `/free` when it differs, and warm H3 up once.                                                                                           |
| C12 | **The agent's shipped skill documents the clip loop** (owner request, 2026-09-30). `.claude/skills/synthbench-generation/` gains the clip loop, its levers, the motion and triage rules and the gate (§6). It ships in the same change as the commands, never before them. |

**Derived:** clips render beside the flagship. The agent drives the round, and it runs on the
flagship, so the owner's GPU window (parent §3.6), which stops the flagship, cannot host it. This
amends the parent spec's Rev 3 line "The window above stays for the owner: clips and large
overnight batches": agent-driven clip rounds run beside the flagship, and the window stays for
large owner-run batches and for Tier A (P6).

## Measurements this design rests on

| Fact                             | Value                                                                                                                                                                                                                                              |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Corpus (2026-09-30)              | 460 events: 459 `ready`, 1 `failed`. Ready by group: threat 196, hard_negative 145, benign 64, suspicious 45, ambiguous 9                                                                                                                          |
| GPU (2026-09-30)                 | Flagship `VLLM::EngineCore` 191,548 MiB; 64,188 MiB free with the renderer stopped                                                                                                                                                                 |
| FLUX.2 [dev] beside the flagship | 56.2 GiB peak, 50.1 GiB resident between jobs (generation design, 2026-09-28)                                                                                                                                                                      |
| H3 turbo (P1)                    | 1344×768, 124 frames at 24 fps (~5.2 s) with audio: 67.7 s per clip, 47.4 GiB net peak, frame drift 0.372. Measured in P1's GPU window, **not** beside the flagship; clips unrated                                                                 |
| The renderer's memory ceiling    | The flagship's util gate (0.76 × 249.81 GiB = 189.9 GiB) must stay passable, so a renderer at peak may use at most **~59.9 GiB**                                                                                                                   |
| H3 weights                       | Five files (`minimax_h3_fl2va_pruned_int8_convrot`, the NVFP4 text encoder, video and audio VAEs, the 4-step 768p turbo LoRA), pinned in `generate/manifests/p1-slate.json` at `Comfy-Org/MiniMax-H3@4cc1d817`, linked in `/export/models/comfyui` |
| ComfyUI                          | v0.37.0 lists the `MiniMaxH3*` nodes (`object_info.v0.37.0.json`). `ComfyClient` already has `free()` (`POST /free`) and `upload_image()` (`POST /upload/image`)                                                                                   |
| The graph                        | `graphs.minimax_h3_turbo_i2v(prompt, image=, seed=, width=, height=, frames=)`: 4 steps, LoRA 1.0, sigma shift 6/3, euler, `BasicGuider`, 24 fps, audio decoded                                                                                    |
| The agent's sandbox              | Mounts `/synthbench/corpus:rw` and `/synthbench/status:ro` (operator runbook). It sees images through the flagship's vision input, not video                                                                                                       |

## §1 Flow

1. **Sample.** `synthbench clip sample --round <r> --n <n>` draws ready stills and writes one clip
   spec per clip (§3.1).
2. **Motion.** The agent writes `rounds/<r>/motions.jsonl`: one motion per clip.
3. **Check.** `synthbench clip check --round <r>` validates the motions and freezes them (§3.2).
4. **Render.** `synthbench clip render --round <r>` switches the renderer to H3 and renders every
   clip, with a frame strip per clip (§4).
5. **Triage.** The agent opens every strip and writes `triage.jsonl`;
   `synthbench clip triage --round <r>` records it and schedules rerolls (§3.3). Steps 4-5 repeat
   for rerolls.
6. **Report.** `synthbench clip report --round <r>` writes `report.md` and `sheet.html`.
7. **Pilot gate.** For the pilot round, the owner runs `synthbench audit --clips --round <r>` on
   the host. Its result, `status/clip-gate.json`, allows or refuses volume rounds (§5).

## §2 Data model

### §2.1 Layout

Clips live in the corpus version whose stills they animate:

```
/synthbench/corpus/<v>/
  rounds/<r>/round.json          RoundRecord
  rounds/<r>/motions.jsonl       the agent's motions: {"event_id", "prompt"}
  rounds/<r>/triage.jsonl        the agent's verdicts: {"event_id", "k", "verdict", "reason"?}
  rounds/<r>/report.md, sheet.html
  clip-index.jsonl               the clips' own index
  events/C/C-<r>-NNN/
    spec.json                    ClipSpec
    provenance.json              ClipProvenance
    clips/a<k>-s<seed>.mp4       the clip: 1344×768, 24 fps, H3's audio track kept
    strips/a<k>-s<seed>.jpg      ~6 evenly spaced frames in one image, for triage
```

`CorpusStore.event_dir` already shards by the id's first letter, so `C-` events land in
`events/C/`. The store gains `round_dir`, `round_file`, `clip_index_file`, `append_clip_index` and
`latest_clip_index`, beside their still counterparts.

**Clips have their own index and round records.** Five consumers read `index.jsonl` and filter on
`status == "ready"`: `export vss`, the audit sampler, the still sampler's `prior_counts`, `check`
and `report`. A shared index would feed clip events to all of them. A regression test pins that
none of them sees a clip.

### §2.2 `ClipSpec` (`spec.json`)

| Field                                                           | Meaning                                                                                                                                  |
| --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `schema_version`                                                | 1                                                                                                                                        |
| `event_id`                                                      | `C-<round>-NNN`. "C" marks the kind; it is not a tier                                                                                    |
| `tier`                                                          | `"B"`: the tier of the source still                                                                                                      |
| `corpus_version`, `round`                                       | slugs, as for stills                                                                                                                     |
| `source`                                                        | `event_id`, `k` (the source's ready attempt) and `render_sha256`: frame 0 is pinned to those bytes                                       |
| `cell`, `scene_time`, `label`, `risk_band`, `subjects`, `props` | copied from the source spec. `clip check` verifies they still equal it, so a clip carries its truth itself                               |
| `prompt`, `clip_suffix`                                         | the agent's motion and the fixed suffix, frozen together once, like `prompt` and `camera_suffix`. A different motion is a new clip event |

`clip_suffix` is a constant in `synthbench/clips/rules.py`: a static-camera instruction, such as
"Fixed security camera; the camera does not move; one continuous shot." Its sha256 is part of
the clip settings (§5.2).

### §2.3 `RoundRecord` (`round.json`)

`name`, `version`, `seed`, `n`, `pilot` (bool), `allocation` (clips per group and lighting as
drawn), `settings` (§5.2: `frames`, `fps`, `size`, `weights`, `clip_suffix_sha256`), `event_ids`,
`source_event_ids`, `created`. Like `batch.json`, it holds everything needed to re-derive the
round's specs; `clip check` re-derives them and exits 2 on drift.

### §2.4 `ClipProvenance` (`provenance.json`)

`attempts[]`, each with:

- `k` and `seed`: attempt `k`'s seed derives from the event id and `k`, as for stills;
- `prompt_sha256`;
- `input_sha256`: the sha256 of the exact cropped PNG uploaded to ComfyUI;
- `clip` and `strip`: output files with their sha256;
- `render_seconds` and `render_failures[]`, with the stills' failure kinds (`job`, `unreachable`);
- `triage`: the verdict and reason.

The clip index uses the stills' statuses: `sampled` → `prompted` → `rendered`, then `ready`,
`rerolled` or `failed`.

## §3 The agent's clip loop

The commands form a group, `synthbench clip <step>`. The still commands are unchanged. Exit codes
are the CLI's: 0 done, 1 error, 2 stop and ask the owner.

### §3.1 `clip sample --round <r> --n <n>`

- **Eligible stills:** every `ready` still event that no clip event names as its source,
  ambiguous included (C3).
- **Allocation:** `n` splits as evenly as possible across the scenario groups that still have
  eligible stills, with the remainder going to the groups with the most eligible stills, capped
  by what each group has. Within a group, the audit sampler's `allocate` spreads the count across
  lighting values. The pilot's 20 is therefore 4 per group.
- **Seed:** from the round name, as a batch name seeds a batch; `--seed` overrides it. The same
  seed gives the same clips.
- **Pilot rule** (C10): the round's settings are compared with `status/clip-gate.json`.
  - No gate for these settings, and no unrated pilot round with them: the round is a pilot, and
    `--n` may be at most 20.
  - A pilot round with these settings is waiting for the owner's audit: exit 2.
  - The gate for these settings failed: exit 2.
  - The gate for these settings passed: any `--n` from 1 to 500.

### §3.2 `clip check --round <r>`

It re-derives every spec from `round.json`, then validates each motion with the existing prompt
rules (the blocklist, the length limit, no clock times) and these clip rules:

1. **The source still is unchanged:** it is still `ready`, its ready attempt is still `k`, and its
   render still matches `render_sha256`.
2. **The facts equal the source spec's facts.**
3. **The motion keeps the cast:** it names every declared subject and prop, with the same term
   matching the still rules use (`rules.mentions` against the taxonomy's `terms`).
4. **The camera stays put:** no camera-movement or editing words. The list includes pan, zoom,
   tilt, dolly, tracking shot, "cut to", "meanwhile" and "later", and lives beside the blocklist.

As `check` does for stills, it lists every failure with its rule, and freezes `prompt` +
`clip_suffix` into each spec once everything passes. The owner runs the same command on the host
to confirm a round.

### §3.3 Triage: `clip triage --round <r>`

The agent opens every strip and writes one row per clip: `ok`, or `reroll` plus one reason:

| Reason               | The strip shows                                                   |
| -------------------- | ----------------------------------------------------------------- |
| `camera_moved`       | the viewpoint pans, zooms or shakes                               |
| `subject_lost`       | a declared subject leaves the frame or dissolves                  |
| `subject_duplicated` | a person or animal appears twice, or a new one appears            |
| `prop_lost`          | a declared prop disappears or changes into something else         |
| `morphing`           | bodies, faces or objects melt, merge or change shape unphysically |
| `scene_cut`          | the scene changes to a different place or shot                    |

These are mechanical failures only; taste is not a reason (G5). `clip triage` enforces the
3-seed cap, and a clip that used its 3 seeds without an `ok` becomes `failed`.

### §3.4 `clip report --round <r>`

`report.md` lists counts by status, rerolls by reason, seconds per clip, mode switches with their
load time, and failed clips. `sheet.html` plays each ready clip beside its source still and its
motion.

## §4 The renderer, memory and the mode switch

### §4.1 Which model is resident

Before its first job, each render command, `render` for stills and `clip render`, reads the most
recent entry of ComfyUI's `GET /history?max_items=1`. Its graph's loader nodes name the model
family that ran last: FLUX.2 or H3.

- **The family differs from the job's:** the command calls `ComfyClient.free()`. `clip render`
  then renders one short warm-up clip from the committed smoke image, so H3's load time is paid
  once and logged.
- **The same family, or an empty history:** no switch is needed. After a renderer restart the
  history is empty, and the unit's FLUX warm-up becomes the first entry.

No mode file is kept. The agent cannot write `status/`, and a file in the corpus would be wrong
after every renderer restart; ComfyUI's history comes from the process that holds the models.

### §4.2 The input image

`clip render` scales the source render (1280×720) to 768 pixels high (1365×768), centre-crops it
to 1344×768, writes it as PNG and uploads it with `upload_image`. The crop is deterministic, and
its sha256 is recorded as the attempt's `input_sha256`.

### §4.3 Memory safety

After the switch and before the first clip, `clip render` reads ComfyUI's `/system_stats`. It exits
2 if the device's free VRAM is less than `H3_PEAK_GIB + 4` (the probe's measured peak for the
round's frame count, plus `--reserve-vram 4`). The flagship's util gate stays where it is checked
today, in the renderer unit's precheck.

The ceiling: at its peak, the renderer may use at most ~59.9 GiB, so that the flagship's
util-0.76 boot gate (189.9 GiB) still passes (generation design §5.3). The Task 1 probe measures
H3's 10 s peak against it (C7).

### §4.4 Rendering and yield

`graphs.minimax_h3_turbo_i2v` builds each job at 1344×768 with the round's frame count. Its
positive prompt is `prompt + " " + clip_suffix`, and its seed is the attempt's. The command:

- waits for the flagship between clips, using the existing `wait_for_flagship` (§5.2 of the
  generation design);
- gives each clip a wait timeout set from the probe's timing;
- downloads the mp4, then builds the strip with PyAV: about 6 frames evenly spaced from first to
  last, tiled into one JPEG;
- resumes where it stopped, as `render` does.

One 10 s clip likely holds the GPU for 2-4 minutes, so yield is coarse and risk R6 (renders slow
flagship users) lasts longer per job. The report shows seconds per clip.

## §5 The owner's pilot audit and the gate

### §5.1 `synthbench audit --clips --round <r>`

This is an owner command that runs on the host. It reuses the P5a audit app: the loopback-only
page on 127.0.0.1 and the same-origin check that answers a cross-site request with 403.

- **It reads** the round's clip events, **read-only from the corpus**. There is no export for
  clips.
- **Each page** plays the clip in a `<video>` beside its source still and its motion, with three
  y/n questions:
  1. **Faithful:** does the clip keep the still's scene, people and props throughout?
  2. **Plausible:** is the motion physically plausible, with no morphing, melting or teleporting?
  3. **In character:** does the action fit the scenario and its label? Benign stays benign; a
     threat stays a threat.
- **Answers** are appended to `/synthbench/audits/<v>/clip-audit.jsonl`, keyed by round and clip.
  The owner rates every clip in a pilot round; nothing is sampled.
- **A failed clip event** (3 seeds, no `ok`) is shown as failed and counts as not passing.

### §5.2 The gate file

When every clip in the round is answered, the command writes `/synthbench/status/clip-gate.json`:

```json
{
  "round": "clips-pilot-1",
  "n": 20,
  "passed_all": 17,
  "rate": 0.85,
  "bar": 0.8,
  "passed": true,
  "settings": {
    "frames": 241,
    "fps": 24,
    "size": [1344, 768],
    "weights": "<sha256 over the minimax-h3-turbo manifest rows>",
    "clip_suffix_sha256": "<sha256>"
  },
  "time": "2026-10-01T12:00:00+00:00"
}
```

- **The denominator is the round's `n`**, so rerolls cannot hide H3's failure rate.
- **The gate approves one set of settings.** `clip sample` compares a new round's settings with
  it (§3.1). A change of frame count, size, weights or suffix is a different generator and needs
  a new pilot.
- **The agent can read the gate but not write it:** its sandbox mounts `status/` read-only.
- **The command also prints** the pass rate with its 95% Wilson interval, as the P5a report
  printed the stills' truth error. At n=20 the interval is wide: 17/20 is about 64-95%. The pilot
  is a go/no-go gate, not a measurement of H3's quality.

## §6 The agent's skill and docs (C12)

The generation agent loads `.claude/skills/synthbench-generation/` every session. The clip loop is
documented there in the same change that adds the commands, never before: a skill that names
commands the agent's workspace lacks sends it to run commands that fail, and this agent acts on
its own open offers.

**`SKILL.md`:**

- **Description:** the triggers gain clip rounds, animating stills, MiniMax-H3, clip triage and
  the clip gate.
- **A new "Clip rounds" section:**
  - the loop in the order of §1, with each command;
  - the gate: a pilot of at most 20 comes first; exit 2 from `clip sample` means wait for the
    owner, never work around it;
  - the levers: the round name seeds the draw, `--n` sets the size, and nothing chooses stills;
  - writing a motion: continue the event from frame 0; keep every declared subject and prop in
    frame; add no people; the camera never moves; the action stays in character for the
    scenario and label;
  - the triage reasons of §3.3, mechanical only.
- **"Common mistakes" gains rows for:**
  - sampling a volume round before the gate passes;
  - camera or editing words in a motion;
  - rerolling for taste;
  - asking for a specific still to be animated;
  - describing clips as scored.

**`reference.md`** gains the §2.1 layout rows, the `ClipSpec` fields, the clip statuses and
`status/clip-gate.json`.

**Also updated:**

- `docs/synthbench/agent-handoff.md`: the clip loop, motion rules, triage reasons and limits;
- `docs/synthbench/command-reference.md`: the `clip` group and `audit --clips`, checked by its test;
- `docs/synthbench/operator-runbook.md`: syncing the code and the skill into the agent's sandbox,
  running the pilot audit, reading the gate, and what to do after a failed gate;
- `synthbench/AGENTS.md`: the new modules;
- the parent spec's Rev 3 line and the generation design's §5.1, per the derived decision above.

**Verifying the skill** (the `writing-skills` method):

1. **Baseline.** A subagent with the current skill and the new command reference is given
   scenarios: run a clip pilot; the pilot looks good and the owner is away, so start a 200-clip
   round; write motions for three given specs; triage three given strips. Its failures are
   recorded.
2. **With the updated skill,** the same scenarios must run the loop in order, stop at the gate
   with exit 2 and wait, keep motions within the rules, and give only mechanical reroll reasons.

## §7 Code layout

| Path                                      | What                                                                               |
| ----------------------------------------- | ---------------------------------------------------------------------------------- |
| `synthbench/contract/clip.py`             | `ClipSpec`, `ClipSource`, `RoundRecord`, `ClipSettings`, `ClipProvenance`, reasons |
| `synthbench/contract/store.py`            | round paths and the clip index                                                     |
| `synthbench/clips/sample.py`              | eligibility, allocation, the pilot rule                                            |
| `synthbench/clips/rules.py`               | `clip_suffix`, the camera-word list, the clip rules                                |
| `synthbench/clips/render.py`              | the mode switch, the crop, the memory check, the strip                             |
| `synthbench/clips/gate.py`                | reading, writing and matching `clip-gate.json`                                     |
| `synthbench/commands/clip.py`             | the `clip` command group: `sample`, `check`, `render`, `triage`, `report`          |
| `synthbench/audit/` + `commands/audit.py` | the `--clips` mode: its page, questions, answer log and gate writing               |
| `synthbench/generate/render.py`           | the stills' `render` gains the same history check (§4.1)                           |

None of this imports `backend` (the import rule).

## §8 Testing and acceptance

### §8.1 Unit tests

These live in `backend/tests/unit/synthbench/` and run with no GPU and no network, against a fake
ComfyUI.

- **`ClipSpec`:** the id scheme, the source pin, the facts' equality, and freezing the prompt and
  suffix together.
- **Stills unaffected:** `export vss`, the audit sampler, the still sampler's quotas, `check` and
  `report` ignore clip events.
- **`clip sample`:**
  - the same seed gives the same clips;
  - the split across groups and lighting;
  - stills that already have a clip are skipped;
  - each branch of the pilot rule, including exit 2 on a missing, failed or mismatched gate.
- **`clip check`:** one failing case per rule, plus drift from `round.json`.
- **`clip render`:**
  - `/free` is called only when the last family in `/history` differs;
  - the warm-up runs once;
  - it exits 2 on the memory check;
  - the crop is deterministic and `input_sha256` matches;
  - it resumes and yields;
  - the strip is built from a tiny synthetic mp4.
- **Stills' `render`:** frees after an H3 history entry.
- **`clip triage`:** the reasons and the 3-seed cap.
- **`audit --clips`:**
  - the same-origin check;
  - answers are appended;
  - the gate file appears only once every clip is answered;
  - a failed clip counts in the denominator;
  - the settings are recorded;
  - the Wilson interval.
- **Existing tests:** the command reference matches argparse, and only `run/` and `score/`
  import `backend`.

### §8.2 Task 1: the live probe (GB300, beside the flagship)

It runs before any code relies on H3. Its evidence goes to
`docs/benchmarks/synthbench/clips-probes.md`.

1. The five H3 files resolve through the symlink farm and match their pinned sha256.
2. **`/free` returns memory:** with FLUX resident after the warm-up, nvidia-smi shows about
   50 GiB released.
3. **A 10 s clip** from a real render crop, at the nearest frame count H3 accepts (about 241):
   - its peak memory, sampled throughout, against the 59.9 GiB ceiling;
   - seconds per clip, and H3's load time;
   - a 124-frame clip as the reference.
4. **Quality at 10 s:** the owner looks at 2-3 clips, to judge whether the 4-step LoRA holds up
   at that length.
5. `/history?max_items=1` has the shape §4.1 reads, before and after `/free`.
6. The flagship stays healthy throughout, and the guard journal stays empty.

### §8.3 Acceptance: the pilot

- The owner syncs the code and the skill into the agent's sandbox.
- The agent runs `clips-pilot-1` (n=20) through the loop without owner edits.
- `report.md` and `sheet.html` exist, and the owner's host `clip check --round clips-pilot-1`
  passes.
- The mode switches appear in the report at the points §4.1 predicts.
- The flagship stays healthy, with no guard stops.
- The owner's audit is complete, and `clip-gate.json` is written.

A failed gate does not fail acceptance. Acceptance tests the tooling; the gate is H3's result.
The record goes to `docs/benchmarks/synthbench/clips-acceptance.md`.

## Risks

| Risk                                                                                        | Mitigation                                                                                          |
| ------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| H3's 10 s peak exceeds the 59.9 GiB ceiling                                                 | C7: clips use the longest length under it, and the probe report says so                             |
| `/free` does not return the memory to the GPU                                               | Fall back to a renderer restart between modes (approach B), which the owner runs                    |
| The 4-step LoRA degrades at 10 s                                                            | The probe's owner look, then the pilot's bar                                                        |
| Flagship users slow down for minutes per clip (R6)                                          | Yield between clips; the report shows seconds per clip; the owner can stop the renderer at any time |
| Clips inherit their stills' errors (C3)                                                     | Triage and the pilot audit catch them; they are accepted by the owner's decision                    |
| A 6-frame strip misses short morphing                                                       | The owner's pilot audit watches the whole clip                                                      |
| H3's licence excludes the US, EU, UK and KR, and bars using outputs to improve other models | The owner's P1 decision, with the terms known; the clips are used for evaluation only               |

## Out of scope

- A camera stage for clips.
- Scoring clips with a video VLM.
- Tier A clips (P6).
- Several motions per still.
- Last-frame and reference-image (Ref2V) modes.
- The audit design for volume rounds.
- Audio as truth: H3's audio track is kept but asserts nothing.

## Rejected

| Option                                                          | Why                                                                            |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Clips sampled into still bursts, scored by the product VLM      | The owner kept clips for a video VLM (C1)                                      |
| Clips uploaded through the platform's video path                | Needs P5b's live instance; the product ingests FTP stills by default           |
| Look first, choose the clips' role later                        | C1 was chosen; the pilot gate still makes the first round a look               |
| The last frame, first-and-last frames, or reference only        | Each needs an unverified extra frame or keeps no verified frame (C2)           |
| Qualification by the flagship's verdict, the agent or the owner | The owner chose every ready still (C3)                                         |
| The clip added to the still's event                             | It rewrites ready, already-scored events (C4)                                  |
| Actions declared in the taxonomy, or host templates             | Taxonomy work first, touching open P2 review items (C5)                        |
| The camera still as frame 0, or its overlay masked              | H3 animates the overlay, or it needs another model pass (C6)                   |
| ~5 s, or a length the agent chooses                             | The owner chose ~10 s fixed (C7)                                               |
| The agent picks stills, or swaps within a stratum               | Coverage would depend on the agent's choices (C8)                              |
| An implicit swap, or the mode as a unit setting                 | An uncontrolled swap beside the flagship; the agent cannot touch systemd (C11) |
