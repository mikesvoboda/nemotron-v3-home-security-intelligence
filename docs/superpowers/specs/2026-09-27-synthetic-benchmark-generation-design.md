# Synthetic Benchmark Generation — Design

**Status:** approved by the owner (2026-09-27): §1-§7 section by section, then the written spec.
Ready for implementation planning.
**Date:** 2026-09-27
**Branch:** `feat/synthetic-benchmark-generation`
**Revision:** rev 1 (2026-09-27). The owner's answers to the two open questions are folded in as D13
and D14.

Evidence tags: **[V]** verified in this session by probe or source read; **[A]** assumption to
confirm during planning; **[?]** unverified external claim (most model facts come from a
2026-09-27 research report and post-date the assistant's knowledge; phase P1 re-checks them).

## Goal

Generate hundreds to thousands of synthetic home-security stills and clips, each with
machine-readable ground truth, then feed them through the **live** platform and score the
detector, every enrichment and specialist model, and the VLM: for accuracy at realistic pacing,
and for latency and accuracy under load.

The corpus must include threat content (weapons, forced entry, masked intruders, fire) because a
security system is judged on the threats it catches. Two facts make that the central constraint:

- Hosted generators sanitize threats. Gemini and Veo left out the weapon, the forced entry or the
  mask in 11 of 13 threat scenarios (`docs/developer/synthetic-data-quality.md`) [V].
- The VSS eval store holds 421 frozen items, and 408 of them have labels but no media. Until media
  exist, the Phase 2.2 bake-off cannot measure S2 or S3 (VSS ledger, F9 ruling 2) [V].

## Decisions (locked by owner, 2026-09-27)

| #   | Decision                                                                                                                                                                                                                                                                                                                          |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | **Live end to end.** Generated media land in synthetic cameras' FTP folders and the real pipeline runs. The scorer compares what every stage stored against each event's ground truth. Per-stage direct-call harnesses are out of scope.                                                                                          |
| D2  | **Ground truth = spec + independent automatic verification + human audit sample** (§4).                                                                                                                                                                                                                                           |
| D3  | **Fully synthetic scenes.** No real camera frame is used as a plate, reference or edit source. Real footage may inform degrade calibration through aggregate statistics only (D13).                                                                                                                                               |
| D4  | **Stills and clips.** Stills feed the detector and specialists (and the VLM); the clip is kept for a VLM that analyzes video directly. The benchmark scores the VLM in stills mode now and in video mode once a video-capable VLM exists.                                                                                         |
| D5  | **Accuracy and load.** One frozen, versioned corpus replays in a _paced_ mode (accuracy) and a _burst_ mode (load, and accuracy under load).                                                                                                                                                                                      |
| D6  | **Two tiers over one taxonomy** (§1): Tier A anchored sites built spec-first and compositionally; Tier B independent text-to-image at volume across a broad property taxonomy.                                                                                                                                                    |
| D7  | **Local open-weight generation only.** Hosted generators (Hailuo, Veo, Gemini) are out: their content filters remove the threats the benchmark exists to test.                                                                                                                                                                    |
| D8  | **Licenses are not a selection criterion** (standing ruling 2026-09-25). Models are picked on fit, measured in P1.                                                                                                                                                                                                                |
| D9  | **The flagship vLLM may be stopped for generation.** The `generate window` command stops it and **always** restarts it, including on failure or interrupt (§3.6).                                                                                                                                                                 |
| D10 | **Capture time comes from the Foscam filename** — a prerequisite backend PR (P0, §5.3).                                                                                                                                                                                                                                           |
| D11 | **Isolated benchmark instance, clean database per run** (§5.1). Synthetic households and events never touch any other database.                                                                                                                                                                                                   |
| D12 | **Tier B first.** The first end-to-end result comes from a ~500-still Tier B v0 before Tier A work starts (§7.3).                                                                                                                                                                                                                 |
| D13 | **Degrade calibration from real footage** (owner, Q1). Degrade parameters (noise, JPEG quantization, IR response, contrast and blur) may be fitted to aggregate statistics of the real Foscam footage on the owner's machine. No real pixel enters the corpus or git; the committed output is a parameter file of numbers (§3.4). |
| D14 | **Retire the 408 media-less VSS items** (owner, Q2) once media-backed replacements from this corpus are imported and the eval store still meets its size floor (≥ 100 benign, ≥ 20 incidents) without them (§8).                                                                                                                  |

## §1 Scope

### §1.1 Tiers

| Tier                   | Unit                                                             | Recognition claims                                                | Purpose                                                                                                          |
| ---------------------- | ---------------------------------------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **A — Anchored sites** | an event: keyframes → clip (6-10 s [A]) → ~5 Foscam-style stills | yes: known faces, known plates, same person across frames/cameras | the specialists (faces, plates, re-ID), household logic, zones, temporal behavior, the video path                |
| **B — Breadth**        | one independent still                                            | none: every person is anonymous                                   | detection, threat, vehicle type, pets, pose and the VLM verdict across many more environments than Tier A covers |

A Tier A **site** is one synthetic property: fixed cameras (an empty plate per camera, with
lighting and weather variants), zone polygons, a household (members, vehicles with plates, pets)
and a recurring cast of visitors and strangers.

### §1.2 Taxonomy (both tiers sample from it)

| Dimension  | v1 values                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Property   | suburban house, urban townhouse, rural farmhouse, lake/beach house with dock, gated estate, mobile home, duplex, apartment entrance/lobby door, apartment parking garage, mailroom/package area, small office entrance, office lot, storefront after hours, warehouse loading dock                                                                                                                                                                                                                                                                                                                                                                |
| Zone       | front porch/doorbell, driveway, garage (inside/outside), backyard, swimming pool and deck, side gate/fence line, patio/balcony, shed, street edge, indoor (kitchen, living room, hallway)                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| Camera     | doorbell fisheye, eave-mounted wide, garage-mounted, pole/lot, indoor corner                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| Conditions | day, golden hour, dusk, IR night, porch-lit night; clear, rain, snow, fog; headlight glare, lens droplets, motion blur                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| Scenario   | **benign**: residents, deliveries, landscapers, pool service, kids, pets, wildlife, neighbors, utility workers. **Hard negatives**: hooded jogger, power tools at night, winter face covering, flashlight, landscaper carrying a machete, costume. **Suspicious**: loitering, casing, peering into windows, trying car door handles, tailgating into a building. **Threats**: firearm, knife, bat or crowbar visible; forced entry; package theft; car break-in; catalytic-converter theft; masked intruder at night; fence climbing; pool trespass; vandalism and camera tampering; assault; person down; fire or smoke; child alone at the pool |

The taxonomy lives in committed YAML. The scenario list starts from the 17 existing templates in
`scripts/synthetic/scenarios/` [V] and grows from there.

### §1.3 Labels and sizes

- Every event is labeled `incident`, `benign` or `ambiguous`. **Ambiguous** events (a toy gun, a
  costume weapon) are scored in their own bucket and never enter S2 or S3.
- Hard negatives are first-class. S2 (false alarms) is measured on benign events that _look_
  alarming; without them the benchmark rewards an alarm-happy VLM.
- **v1 sizes:** Tier A ≈ 8 sites × ≈ 4 cameras, ≈ 600 events (≈ 3,000 stills plus clips); Tier B ≈
  5,000 stills. These are starting targets; the owner adjusts them per corpus version.

## §2 Contract: event spec and ground truth

### §2.1 Files per event

| File              | Written by                 | Holds                                                                                                                                                                             |
| ----------------- | -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `spec.json`       | spec sampler               | **Intent**: site or taxonomy cell, camera, conditions, scene time, subjects (cast refs or free descriptions), props, per-keyframe layout boxes, action timeline, prompt fragments |
| `truth.json`      | packager (spec + verifier) | **World facts**: what each still contains, and when things happen in the clip                                                                                                     |
| `provenance.json` | every stage                | model IDs and weight hashes, seeds, prompts, stage timings, verifier verdicts, audit status                                                                                       |

All three are pydantic models in `synthbench/contract/`, each with a `schema_version`.

### §2.2 Truth stores facts, never expected model outputs

`truth.json` says "stranger `S3`, handgun in right hand, face 38 px tall". It never says "the face
specialist returns `not_identifiable`" or "detector confidence ≥ 0.75". The existing templates
hard-code such outputs (`min_confidence`, `florence_caption.must_contain`) [V], which ties the
corpus to one pipeline configuration.

A pure function in the scorer, `expectations(truth, profile, ledger)`, turns facts into
per-stage expectations under a versioned **scoring profile**. The profile records the scoring rules'
version plus a snapshot of the thresholds the benchmark instance actually runs with (for example
`face_min_size_px`, `face_scrfd_threshold`), captured at run start. When a threshold changes,
expectations are recomputed; the corpus is not regenerated. Expectations that span events
(re-ID links) also take the run ledger as input, because they depend on what the pipeline saw
earlier in the run.

### §2.3 Example (Tier A threat event, trimmed)

```json
{
  "schema_version": 1,
  "event_id": "A-lakehouse-dock_cam2-00417",
  "tier": "A",
  "site": "lakehouse",
  "camera": "dock_cam2",
  "scene_time": "02:14",
  "conditions": ["ir_night", "fog"],
  "label": "incident",
  "risk_band": [85, 100],
  "scenario": "armed_intruder_dock",
  "cast": { "S3": { "role": "stranger", "enrolled": false } },
  "stills": [
    {
      "file": "stills/002.jpg",
      "t": 2.4,
      "objects": [
        {
          "id": "S3",
          "class": "person",
          "bbox": [0.58, 0.31, 0.72, 0.93],
          "zone": "dock",
          "face": { "visible": true, "height_px": 38 },
          "posture": "crouching"
        },
        {
          "class": "handgun",
          "held_by": "S3",
          "bbox": [0.66, 0.55, 0.69, 0.6],
          "visible": true
        }
      ],
      "fact_provenance": { "S3.bbox": "verified", "handgun": "verified" }
    }
  ],
  "timeline": [
    { "actor": "S3", "action": "climbs_onto_dock", "t": [0.0, 1.8] },
    { "actor": "S3", "action": "approaches_door_with_weapon", "t": [1.8, 6.0] }
  ]
}
```

Boxes are normalized `[x0, y0, x1, y1]`. A subject's zone is computed from its foot point against
the camera's zone polygons.

### §2.4 Fact provenance

Every fact carries one of `declared` < `verified` < `audited`. The scorer scores only
`verified` or `audited` facts (§6), so a generator miss is never counted as a pipeline miss.

### §2.5 Site files

A Tier A site directory holds `site.json`, one plate per camera per condition variant, zone
polygons per camera, reference sheets and `cast.json`. The cast file lists household members,
visitors and strangers, plus vehicles with plate strings and `registered: true|false`.
**Enrollment shots** (the images the benchmark instance enrolls) are generated separately from
event stills and never appear in events. Tier B events reference a taxonomy cell instead of a
site.

### §2.6 Corpus layout

The corpus lives outside the repo: it is fully synthetic but gigabytes in size. Git holds only
schemas, taxonomy, sampler config, workflows and the weights manifest.

```
<corpus_root>/<version>/corpus.json          # version, taxonomy hash, model hashes, counts
<corpus_root>/<version>/sites/<site>/…       # plates, zones, cast, reference and enrollment sheets
<corpus_root>/<version>/events/<tier>/<id>/  # spec/truth/provenance, keyframes/, clip.mp4, stills/
<corpus_root>/<version>/quarantine/<id>/     # events that failed verification (§4.2)
<corpus_root>/<version>/index.jsonl          # one row per event for fast selection and scoring
```

A frozen corpus version is immutable. Changes produce a new version.

### §2.7 Export to the VSS eval store

An adapter writes selected events in the layout `import_generated_items` reads:
`<category>/<set>/expected_labels.json` plus frames, with an optional contained `manifest.json`
(`backend/evaluation/label_import.py`) [V]. The VSS replay harness then gets media-backed items
from the same corpus.

## §3 Generation stack

### §3.1 Runtime

Headless **ComfyUI** in a container, driven by the `synthbench` orchestrator over its HTTP API.
Workflow templates (JSON) and a hash-pinned weights manifest are committed; weights live outside
the repo.

- **Why ComfyUI:** new models (Qwen-Image-2.1, FLUX.2, LTX-2.x) ship official ComfyUI workflows
  first [?], and its queue handles batching. The cost is testing against a fake server (§7.2).
- **Image:** arm64, an NGC PyTorch base with sm_103 support, run with `podman`. The GB300 is
  aarch64 with 64 KiB pages and no host CUDA toolkit [V], so CUDA comes from the image.
- **Fallback:** if a slot's model has no working arm64 path in ComfyUI, that slot runs through
  plain `diffusers` behind the same stage interface.

### §3.2 Stages and model slots

Phase P1 fills the pick for each slot. Nothing is pre-committed.

| Slot        | Job                                                                           | Candidates [?]                                                |
| ----------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------- |
| T2I-quality | Tier A camera plates; cast, vehicle and prop sheets; the Tier B quality slice | FLUX.2 [dev], Qwen-Image-2.1, HiDream-I1                      |
| T2I-volume  | the bulk of Tier B                                                            | Z-Image-Turbo, FLUX.2 Klein                                   |
| Compositor  | place cast and props on a plate inside the spec's boxes                       | Qwen-Image-2.1 edit, FLUX.2 [dev] edit (≤ 10 references each) |
| Text        | legible plate strings and signage                                             | Qwen-Image-2.1, Ideogram 4                                    |
| Animator    | keyframes → clip (first/last-frame and multi-keyframe guides)                 | LTX-2.x, Wan 2.x, Cosmos-Predict2.5                           |
| Degrade     | Foscam camera model                                                           | plain code (OpenCV, ffmpeg), not a model                      |

Stages hand off through files (spec → assets → keyframes → clip → stills → manifest), so a model
swap touches one stage.

### §3.3 Placement by masked inpainting

The compositor edits only inside a mask drawn from the spec's box, with the cast or prop sheet as
reference. Declared boxes are near-exact by construction; the verifier confirms them rather than
discovering them.

### §3.4 Camera degrade

Deterministic, seeded code converts a clean render into what a Foscam camera uploads:

- **Stills:** 1920×1080 JPEG [V], lens distortion per camera type, sensor noise, IR-night grayscale
  and bloom, timestamp overlay.
- **Clips:** HEVC 2560×1440 at 30 fps. Real clips run ~40 s [V]; generated clips are shorter (6-10 s
  [A]), and P6 checks how the video path treats short clips.

Stills are sampled from the clip at Foscam-like burst spacing (1-2 s).

**Calibration (D13).** `synthbench degrade calibrate` reads the real footage under
`/export/foscam` on the owner's machine and fits the degrade parameters per camera type and
condition (day, IR night) to aggregate statistics: noise level, JPEG quantization tables, IR
luminance response, contrast and sharpness. It writes a committed parameter file of numbers only;
no real pixel, crop or thumbnail leaves the calibration run. A test pins that the calibration
output holds no array larger than a parameter table.

### §3.5 Generator diversity in Tier B

Most Tier B stills come from the volume model. A ~15% slice renders the same specs with a quality
model. If pipeline accuracy differs sharply by generator, the benchmark is measuring generator
artifacts rather than the pipeline, and the report shows that split (§6.2).

### §3.6 GPU window

`synthbench generate window --stages …` owns the GPU for the duration of a generation run:

1. Take a host-wide lock and write a window-open marker.
2. Stop the flagship at container level (`docker stop dgx-inference-vllm-1`, the rootful daemon)
   [V]. Never run `docker compose up` on that stack: it would also restart the stopped Cosmos
   container.
3. Start the ComfyUI container (and, for verification, the judge VLM) on the whole GPU (~250 GiB).
4. Run the requested stages **stage-major**: every plate, then every composite, then every clip,
   then verification. Each model loads once per window and batches stay large.
5. **Always** restore: stop our containers, `docker start dgx-inference-vllm-1`, and wait until
   it reports healthy and `127.0.0.1:8000/v1/models` answers. This runs on success, failure,
   SIGINT and SIGTERM. A marker left behind by a crashed run makes the next invocation restore
   first.

Outputs are content-addressed and every stage skips finished work, so an interrupted window
resumes where it stopped. Stopping the flagship also takes down `claude-flagship` in LiteLLM and
any sandbox agent that runs on it; the window prints that warning at start.

Benchmark _runs_ (§5) do not open a window: the platform fits beside the flagship
(48.9 GiB free on 2026-09-27, flagship at 206.7 GiB) [V].

### §3.7 Bake-off (phase P1, throwaway)

About a dozen hard prompts per candidate:

- a handgun in hand, a knife, a crowbar at a door, a balaclava at IR night, a forced door, a pried
  window;
- a child alone at the pool edge, smoke from an eave;
- a legible plate `8KXR-417`;
- the same face across 5 shots and 3 lighting conditions.

Measured per candidate:

- prompt adherence (verifier plus the owner's eye);
- identity drift, as face-embedding distance from an embedder **other than** the pipeline's
  w600k_r50;
- plate OCR accuracy;
- seconds per image or clip, and peak VRAM;
- whether the model runs in ComfyUI on arm64/sm_103 at all.

The picks and their numbers are recorded in this spec's next revision. If no model renders a
threat prop convincingly, fall back to a prop reference sheet composited in, and train a LoRA
only as a last resort.

### §3.8 Content rules

- The cast is generated from scratch and never derived from photos of real people, so no real
  face is enrolled or depicted.
- Threat content is realistic and non-graphic: what a security camera sees (a weapon in hand, a
  forced door, a person down), never injury detail.

## §4 Verification and audit

### §4.1 Independent checks

No verifier model may be a model the pipeline runs or a VSS bake-off candidate. A unit test
enforces this against the pipeline's model registry and the VSS candidate list.

| Fact type                                                                                       | Check                                                                                                                                                                                 |
| ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| objects and props (person, weapon, tool, vehicle, pet, fire)                                    | open-vocabulary detector from a different family than YOLO26, YOLOE and the YOLOv8 threat model (for example Grounding DINO or OWLv2); IoU against the declared box                   |
| label-bearing semantics (holding a handgun, door forced, child alone at pool edge, face masked) | judge VLM from a different model family than every VSS bake-off VLM, asked **closed questions** on a crop ("Is the person in the red box holding a handgun? yes/no/unclear")          |
| identity                                                                                        | independent face embedder: household members match their cast sheet, and **every stranger is far from every household member** (Tier B faces too, whenever a run enrolls a household) |
| plates                                                                                          | independent OCR reads the exact spec string, or `plate_legible` becomes false                                                                                                         |
| clips                                                                                           | the same checks on sampled frames, identity drift across frames, and the subject present within each timeline window                                                                  |

### §4.2 Per-event policy

- **Label-bearing facts** (weapon present, forced entry, fire, mask, person count, household
  identity) must reach `verified`. If one is contradicted, regenerate with a new seed, up to 3
  attempts, then move the event to `quarantine/`. Quarantined events are counted in generator
  failure-rate statistics and never scored.
- **Minor facts** (posture, clothing color): if contradicted, the truth follows the image. The
  fact is corrected or dropped and the event passes.
- **Unclear** answers go to the audit queue at high priority.

### §4.3 Human audit

`synthbench audit` serves a local review page on 127.0.0.1. It shows the stills, the clip and the
truth drawn over them (boxes, identities, timeline), takes keyboard accept, reject or relabel, and
writes `audit.json`. Audited facts are promoted to `audited`.

Sampling:

- 100% of threat and ambiguous events for each new (scenario × generator) pair, until 20 pass with
  ≥ 95% agreement with the verifier;
- then a stratified 5% per scenario;
- every `unclear`.

If the owner rejects more than 5% of verifier-passed events in a pair, that pair returns to 100%
audit. The audit therefore also measures the verifier's precision.

## §5 Benchmark instance and runner

### §5.1 Benchmark instance

A separate compose project, `hsi-bench`, with its own Postgres, Redis, backend, AI services and
FTP root. It uses its own env file, `.env.bench`, with every port taken from an env var as
`AGENTS.md` requires, and binds loopback only. `synthbench instance up|reset|down` manages it.

- **Every run starts from a clean database.** The re-ID gallery, zone baselines and anomaly
  learning all accumulate state.
- **Setup goes through the platform's own APIs:** register the admin (which satisfies
  `SetupGuardMiddleware`); create each Tier A camera and its zone polygons; enroll household members
  from their enrollment shots; register vehicles and plates. Enrollment runs the pipeline's own
  embedder, so gallery vectors carry the correct `model_id`. Whether every one of these operations
  has an API today is [A]; the P5 plan verifies each and adds the smallest missing endpoint.

### §5.2 Runner

Inputs: corpus version, selection (tiers, scenarios, sample size, seed) and mode.

- **Folder layout** mirrors a real camera [V]:
  `<camera>/FoscamCamera_<id>/snap/MDAlarm_YYYYMMDD-HHMMSS.jpg` and
  `<camera>/FoscamCamera_<id>/record/MDalarm_YYYYMMDD_HHMMSS.mkv`. The first path component is the
  camera (`backend/services/file_watcher.py:566`) [V].
- **Writes** are write-then-rename, which suits the watcher's 2 s stability check
  (`file_watcher.py:404`) [V].
- **Run ledger:** event ID, camera, files, and first and last upload time.
- **Clips:** a Tier A event uploads its clip beside its stills, as a real camera does. How the
  video path's detections join the event's batch is measured in P6, and the matcher (§6.1)
  attributes both to the same corpus event.

**Paced mode (accuracy).** One corpus event produces one batch. Per camera, events are serialized
with a gap longer than the 30 s idle timeout; stills within an event keep burst spacing. Tier B
spreads its stills over a pool of neutral "breadth cameras" (for example 32 per camera type) so
5,000 stills take hours, not days. The production batching configuration is left unchanged: it is
part of the system under test.

**Burst mode (load).** N cameras at R events per minute, ramping. It measures latency from upload
to event to verdict to WebSocket, Redis queue depth, GPU use, errors, and dropped or merged events.
It also re-scores accuracy on a subset shared with a paced run.

### §5.3 Capture time (prerequisite P0)

The pipeline stamps detections and batches with wall-clock time (`datetime.now(UTC)` at
`backend/services/detector_client.py:1163` and `backend/services/batch_aggregator.py:250`) [V].
A 02:14 IR-night scene uploaded at 15:00 reaches the VLM as 15:00, which contradicts the image.

P0 derives capture time from the Foscam filename and falls back to wall clock when the name does
not parse. The parser accepts both observed patterns, `MDAlarm_YYYYMMDD-HHMMSS` and
`MDalarm_YYYYMMDD_HHMMSS`, plus the `HMDAlarm_` prefix [V]. This also fixes production: after an
outage or backlog, every image currently gets its processing time. The runner writes scene time
into filenames on the run's date. Which downstream consumers read the capture time (batch
windows, retention, UI) is settled in the P0 plan.

## §6 Scorer and report

### §6.1 Flow

1. **Match** corpus events to database events by camera and upload window from the run ledger,
   and stills to detections by file path. An extra database event is scored as `split` and a
   missing one as `dropped`; both are findings.
2. **Expect:** `expectations(truth, profile, ledger)` (§2.2). Only `verified` and `audited` facts
   are scored; the rest are recorded as `not_scored` with a reason.
3. **Compare** expected with actual per fact and write one row per comparison to
   `runs/<run_id>/results.jsonl`. Actuals come from the API where it exposes them, otherwise from
   read-only database queries; the plan lists every database-sourced field.
4. **Aggregate** into `metrics.json` and the report.

### §6.2 Metrics

Every cell carries its _n_ and a 95% interval. Cells below a minimum _n_ read "insufficient", not
a bare percentage. Every metric can be sliced by tier, scenario, property, zone, condition, camera
type and generator.

| Stage               | Metrics                                                                                                                                                         |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Detector            | per-class precision and recall at IoU 0.5; person-count accuracy                                                                                                |
| Threat              | weapon recall and precision by type × condition, with IR night as its own row                                                                                   |
| Vehicles and plates | type and color accuracy; plate exact match and character error rate; registered-vs-unknown decision accuracy                                                    |
| Faces               | four-outcome confusion (match / unknown / not_identifiable / unavailable) against expectation; **false-match rate (stranger read as household)**                |
| Re-ID               | correct same-person links across frames and cameras; false-link rate                                                                                            |
| Pets, pose, zones   | species, posture and zone-assignment accuracy                                                                                                                   |
| VLM                 | **S2 and S3 computed by the functions `backend/evaluation` uses** (one definition); risk-band error; verdict mix (the hedging rate); stills vs video input mode |
| System              | p50/p95/p99 latency per stage and end to end, throughput, dropped and split events, errors, GPU use; accuracy change from paced to burst                        |
| Benchmark health    | fact coverage per scenario (share of declared facts that reached `verified` or `audited`), quarantine rate, audit agreement, per-generator score split          |

Fact coverage matters because scoring only verified facts hides blind spots that the verifier and
the pipeline share. Low coverage in a cell means that cell is not being tested.

### §6.3 Report and comparison

`report.md` plus a local HTML report: headline numbers, per-stage tables, a scenario × condition
heatmap, a failure gallery (the worst misses with truth and predicted boxes drawn), and the run's
identity (platform git SHA, model hashes, corpus version, scoring-profile version).
`synthbench compare <run_a> <run_b>` reports deltas with intervals and is the regression tool.
Aggregate metrics for notable runs may be committed under `docs/benchmarks/synthbench/`; images
and per-fact rows stay in the run directory.

## §7 Code layout, testing, phasing

### §7.1 Layout

A new top-level package, `synthbench/`, named to avoid `tests/benchmark/`. It is added to pytest
`testpaths`, coverage `source` and mypy, because today coverage covers only `backend` and
`testpaths` omit `scripts/` and `tools/` (`pyproject.toml:543`, `:586`) [V].

```
synthbench/
  AGENTS.md
  contract/     # pydantic: spec, truth, provenance, index, scoring profile (§2)
  taxonomy/     # YAML taxonomy + seeded coverage-matrix sampler
  generate/     # ComfyUI client, stages, workflows/*.json, degrade, GPU window
  verify/       # fact checkers, per-event policy, independence guard
  audit/        # local review page (127.0.0.1)
  run/          # benchmark instance, setup through the platform API, paced and burst runner
  score/        # expectations(), matching, metrics, report, compare, eval-store export
  cli.py        # synthbench generate|verify|audit|instance|run|score|compare|export
  tests/
```

**Import rule**, enforced by a test like the existing "backend never imports `ai.*`" rule: only
`synthbench.score` and `synthbench.run` may import `backend`. `generate/` and `verify/` never do,
so the generation container carries no backend dependencies.

`scripts/synthetic/` (Gemini/Veo) stays untouched. `synthbench` supersedes it; retiring it is a
later cleanup.

### §7.2 Testing

TDD throughout. CI never needs a GPU.

- **Unit:** contract round-trips; sampler determinism (same seed, same specs) and quota coverage;
  table-driven `expectations()` (face size gate → outcome, plate legibility × registration →
  expected read); matching with split and dropped ledgers; metrics and intervals on known
  confusion matrices; degrade determinism (golden hashes); verifier policy (regenerate,
  quarantine, truth follows image); the verifier-independence guard; the capture-time parser; and
  **the GPU window always restoring the flagship**, against a fake runtime controller that raises,
  receives SIGINT and times out.
- **Integration:** a fake ComfyUI server returning canned images drives generate → verify →
  package. A committed **mini-corpus** (≈ 10 tiny synthetic events, a few KB each) drives
  instance → runner → scorer against a real benchmark instance.
- **Manual, with recorded evidence:** real generation runs (the bake-off report, corpus build
  logs).

### §7.3 Phasing

Each phase gets its own plan and PR. The implementing agent writes one phase's plan at a time.

| Phase | Deliverable                                                                                                | GPU                 |
| ----- | ---------------------------------------------------------------------------------------------------------- | ------------------- |
| P0    | Capture time from the Foscam filename (backend, TDD; §5.3)                                                 | no                  |
| P1    | Bake-off spike (throwaway): ComfyUI on arm64/sm_103; picks recorded in rev 2 of this spec                  | window              |
| P2    | Contract, taxonomy, sampler, `expectations()`                                                              | no                  |
| P3    | Generation stack and GPU window, Tier B first (text-to-image + degrade calibrated per D13)                 | window              |
| P4    | Verifier and audit page                                                                                    | window              |
| P5    | Benchmark instance, paced runner, scorer, report → first end-to-end result on a ≈ 500-still Tier B v0      | beside the flagship |
| P6    | Tier A: sites, cast, compositor, animator, enrollment, clips                                               | window              |
| P7    | Burst mode, `compare`, VSS eval-store export and retirement of the 408 items (D14), then scale to v1 sizes | mixed               |

## §8 Relationship to existing work

- **`scripts/synthetic/`**: its 17 scenario templates seed the taxonomy's scenario list, and its
  expected outputs inform the fact vocabulary. `synthbench` does not import it.
- **VSS eval store**: the export adapter (§2.7) supplies media-backed items, and they replace the
  408 media-less items (D14). Retirement runs after the import, only if the store still meets its
  size floor without them, and is recorded in the VSS ledger as an owner ruling.
- **VSS D6** ("ingest is FTP stills only"): unchanged. The benchmark carries clips so video-mode
  VLM scoring is ready when a video-capable VLM exists; it does not change the ingest decision.

## §9 Risks and open questions

### §9.1 Risks

| #   | Risk                                                                                                      | Mitigation                                                                                                                 |
| --- | --------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| R1  | Open-weight models may not render some threat props convincingly (filtered training data).                | P1 measures per prop; fall back to prop reference sheets, then a LoRA.                                                     |
| R2  | ComfyUI or its custom nodes may lack arm64/sm_103 builds.                                                 | P1 checks this first; per-slot `diffusers` fallback (§3.1).                                                                |
| R3  | Model facts from the research report are unverified [?].                                                  | P1 re-checks availability, size, gating and ComfyUI support for each candidate.                                            |
| R4  | Fully synthetic frames still differ from real Foscam footage, so scores are relative, not field accuracy. | Degrade model; the generator-diversity slice (§3.5); later comparison against owner-labeled real events after VSS go-live. |
| R5  | The verifier and the pipeline may share blind spots.                                                      | Fact-coverage reporting; `unclear` goes to audit (§4.2, §6.2).                                                             |
| R6  | A crashed window could leave the flagship down.                                                           | Always-restore handlers, the leftover-marker check, and the unit test in §7.2.                                             |
| R7  | Enrollment or registration APIs may be missing [A].                                                       | The P5 plan verifies each; add the smallest missing endpoint.                                                              |
| R8  | Generated clips are shorter than real ones (6-10 s vs ~40 s).                                             | P6 checks how the video path handles short clips; pad or chain segments if needed.                                         |
| R9  | Burst mode may merge events across the 90 s window.                                                       | Scored as `split` or merged findings; that is the load test working, not a scorer bug.                                     |

### §9.2 Open questions

None open. Q1 became D13 and Q2 became D14 (owner, 2026-09-27).
