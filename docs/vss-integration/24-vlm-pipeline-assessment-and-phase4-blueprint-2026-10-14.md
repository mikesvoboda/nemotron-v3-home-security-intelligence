# 24 — VLM Pipeline Assessment, Open Questions, and Candidate Remedies (2026-10-14)

> **Status — 2026-10-14 [?]. A DRAFT PROPOSAL, pending owner review.** Nothing here is a plan of
> record or an active work order. Per Uplevel rule `UR-11`
> ([`docs/uplevel/history/ruling-map.md`](../uplevel/history/ruling-map.md) and
> [`docs/uplevel/README.md`](../uplevel/README.md), "Considered and rejected"), Phase 4 seams are
> designed only when reached, after Phase 3 deletions remove ~38K lines of non-shipping code. This
> document synthesizes the pre-Uplevel VLM commit history, records the open pipeline gaps against
> [`17-action-plan.md`](17-action-plan.md), and frames candidate remedies as **questions for the
> owner (`[?]`)** when `OD-2`, `OD-5`, and the Phase 4 design sessions (`UR-77`, `UR-79`) are
> reached. Verified against `main` at `6afa930b0` **[V]**. Epistemic markers follow
> [`AGENTS.md`](AGENTS.md).

---

## 1. Executive Summary: Five Pre-Uplevel Waves and the S3 Ceiling

Between `2026-09-27` (`4bfd6fa4`, Phase 1 VLM bring-up) and `2026-10-07` (`d6ba78d5`, the Uplevel
programme baseline), five waves of commits established the shipped `ai-vlm` path:

1. **Wave 1 — VLM Bring-Up, Slot Fitting & `Qwen3-VL-8B` Default (Sept 27–28):** `VlmAnalyzer`
   (`backend/services/vlm_analyzer.py`), `VlmClient` (`backend/services/vlm_client.py`), and
   `vlm_specialists` (`backend/services/vlm_specialists.py`) stood up the end-to-end `vlm_assess`
   path (`4bfd6fa4`), promoted `Qwen3-VL-8B-Instruct-Q4_K_M` as the serving default (`54141d9c`),
   switched prompt bounding boxes to `Qwen3-VL`'s native `0–1000` `[x1, y1, x2, y2]` grounding
   convention (`5b929a52`), and matched prompt fitting to the 16,384-token served slot with
   `LLAMA_ARG_IMAGE_MAX_TOKENS=1280` and `VlmContextOverflowError` (`a2d8c710`) **[V]**.
2. **Wave 2 — R8 Legacy LLM & Enrichment Retirement (Sept 29 – Oct 2):** Deleted
   `nemotron_analyzer.py` and the `ai/{florence,clip,enrichment,enrichment-light,nemotron}` trees
   (`602379e2`, `3b73b9b6`, `e40d69f5`), narrowing the specialist stage to three database-backed
   identity lookups (`faces`, `plates`, `person_reid`) guarded by four-state face classification
   (`classify_face_outcome`) and model-ID vector-space checks (`compare_person_vectors`) **[V]**.
3. **Wave 3 — Greedy Decoding, Token Budget & `OD-29` Operating Point (Oct 3–5):** Set
   `_ASSESS_TEMPERATURE = 0.0` (`9f4e65cd`, achieving 450/450 run-to-run replay reproducibility on
   `tierb-v0` **[A]**), raised `_ASSESS_MAX_TOKENS` to `2048` (`26b900bc`, with the timeout ladder
   subsequently repaired in Uplevel `B1.1` `#6868` via `VlmSlowReplyError` **[V]**), and shipped the
   `OD-29` operating point (`c0191f4d`: Arm B severity rubric + per-camera default
   `risk_threshold = 60`) **[V]**.
4. **Wave 4 — End-to-End Notification Decision Persistence (Oct 3–6):** Wired
   `NotificationFilterService.decide_notification` into `VlmAnalyzer` post-commit (`ab3bd002`),
   persisted `event_notify_decisions` (`db83f1f8`), and exposed `notify` on REST and WebSocket
   (`1a2c83d1`, closing `ISS-001` and `ISS-018`) **[V]**.
5. **Wave 5 — Statistical Rigor & Multi-Frame Temporal Context (Oct 6–7):** Added scenario-cluster
   bootstrap intervals and exact McNemar paired tests (`d8b461a8`, `ISS-043`), froze the `tierb-v0`
   dev/holdout split (`dc4607c2`, `ISS-016`), attached multi-frame batches oldest-first with
   capture-time labels (`acd6d6d6`, `ISS-033`), and spread spare key-frame slots across temporally
   distant stills of dwelling `(camera, class)` pairs (`a71cc785`, `ISS-005`), with replay parity
   enforced in `vlm_replay.py` (`B1.2`, `#6924`) **[V]**.

### The Unresolved Core Bottleneck

Despite the 12-model sweep (`08d0bf21`, `ISS-097`) and the 4-stage, 10-arm controlled prompt
programme (`26b900bc`, `60022dd0`, `c0191f4d`; banked in
[`22`](22-prompt-research-and-probes-2026-10-04.md) and
[`23`](23-prompt-programme-stages-1-4-2026-10-05.md)), the shipped `OD-29` operating point (Arm B
rubric + per-camera alert floor `60`) scores on the 450 `tierb-v0` stills:

- **S2 (benign false-alarm rate, bar $\le 5\%$):** `9/209 = 4.3%` `[2.3–8.0]` (clears bar on fresh
  installs; `c0191f4d`, `23 §5`) **[A]**
- **S3 (incident hit rate, bar $\ge 90\%$):** `104/241 = 43.2%` `[37.1–49.5]` (46.8 percentage
  points below the `F14` 90% bar; the 191.5 GB flagship reached `58.9%` in `p5a-2026-09-30.md`)
  **[A]**

Section 2 presents candidate architectural options (`[?]`) for the owner when `OD-2` and Phase 4's
`BB.6` design session are reached, and Section 3 catalogs the seven concrete pipeline gaps in the
current codebase alongside their existing register entries (`17-action-plan.md`).

---

## 2. Candidate Architectural Options for Owner Consideration (`[?]`)

### 2.1 Candidate Option A (For `OD-2` / `ISS-008` and Phase 4 `BB.6`): Structured Threat Observables $\rightarrow$ Deterministic Policy Scoring **[?]**

#### Diagnosis from `doc 22` and `doc 23`

In `VlmClient._render_prompt` (`backend/services/vlm_client.py`), the prompt asks `ai-vlm` to output
`verdict` (`confirmed | uncertain | rejected`) and `risk_score` (`0..100`) directly in one JSON
object (`VlmVerdict` in `backend/services/vlm_verdict.py`) **[V]**.

The measurements in [`22`](22-prompt-research-and-probes-2026-10-04.md) and
[`23`](23-prompt-programme-stages-1-4-2026-10-05.md) identified three properties of direct `0–100`
verbalized scoring on 8B VLMs:

- **Band-number clustering and pair ties:** In Probe 4 (`22 §2`), 20 of 37 rows emitted the exact
  integer `30`, causing argmax to tie on 31–36% of incident×benign pairs (`22 §2`, `22 §3` anchoring
  literature **[E]**).
- **Grammar digit saturation:** Token-probability expected value (`EV_C` over logprobs) tied argmax
  (`median |EV - argmax| ≈ 0.1`) because constrained JSON decoding saturates the digit probability
  distribution (`22 §2`).
- **Latent discrimination exceeds single-threshold hits:** In Stage 2 (`23 §1`), all four
  reasoning-bearing arms improved AUROC against plain-benign stills by `+0.20` to `+0.245` (CI lower
  bound $> 0$), showing that `Qwen3-VL-8B` distinguishes suspicious from benign scenes more
  reliably than its raw `0–100` integer threshold crossings reflect. Meanwhile, Stage 4 (`23 §2.1`)
  showed that placing `verdict` before `reasoning` is harmful (`vb`: `dS3 -17.0`), while placing
  `verdict` last causes truncation on evidence-rich scenes (`verify` arm: 97 truncated rows at
  2,048 tokens), confirming that `verdict` early followed by `reasoning` is the safest field order.

#### Candidate Design Question for the Owner (`OD-2` Remedy / `BB.6` Scope) **[?]**

`23 §3` noted _"severity grading in the rule engine, not in the VLM's 0-100"_ as a future input-pipeline
direction, while `docs/uplevel/packages/backend.md` defines `BB.6` as:

> _"The VLM seam — build → call → judge: one prompt fit and one key-frame selection per batch, the
> prompt as a versioned template whose hash is stored on `EventVerification`, the analyzer built
> once. Unless a VLM feature reaches it first."_

**Question for the owner when `OD-2` / `BB.6` is reached `[?]`:** Should `OD-2`'s remedy (or a
separate Phase 4 feature package after `BB.6`) decouple **visual scene classification** from
**numerical risk grading** by having `VlmVerdict` emit structured categorical observables (for
example `actor_role`, `observed_behavior`, `entry_or_tamper_evidence`, `location_context`) and
computing `risk_score` (`0..100`) deterministically in a Python policy layer over those observables
plus `specialist_outputs`, `zone_crossing`, and time-of-day?

- **Hypothesis to test on the `tierb-v0` dev split (`ISS-016`) `[?]`:** An 8B VLM that fails to emit
  `risk_score >= 60` on calm-looking `peering` or `testing_door_handle` scenes (`22 §2` Probe 3) may
  still classify `observed_behavior` accurately when asked a categorical question rather than a
  0–100 numerical calibration question, and a deterministic policy table can be tuned on CPU without
  re-running GPU inference.

---

### 2.2 Candidate Option B: Early Preview Verdict vs. 30–90s Batch Close (`ISS-021`, `OD-7`) **[?]**

#### Current State **[V]**

In the shipped pipeline (`docs/architecture/ai-pipeline-current-state.md §1`), detections accumulate
in `BatchAggregator` (`backend/services/batch_aggregator.py`, `add_detection`) until the batch
closes on `batch_window_seconds` (`90s` default) or `batch_idle_timeout_seconds` (`30s` default) in
`backend/core/config.py`.

For immediate weapon threats, `OD-7` was **ruled in `R2a` (ruling 89)** **[O]**:

- Build the weapons fast path gated (pin the Hugging Face revision of
  `Subh775/Threat-Detection-YOLOv8n`, read the checkpoint's class names to fix the gateway's labels,
  measure false positives on home-camera images, and settle the licence before enabling
  `GATEWAY_ENABLE_THREAT` and the backend `/enrich-lt/threat-detect` caller; delete the smoke/fire
  stub).
- Separately, Uplevel ruling 168 (`#7088`) adds an explicit `fast_path_enabled` boolean flag for the
  existing `BatchAggregator` fast-path hook.

#### Question for the Owner (Post-Phase 4 / Roadmap) **[?]**

Even when `OD-7`'s weapons fast path is built, non-weapon person events (an unfamiliar person
approaching a front door or driveway) wait 30–90 seconds for the batch window to close before
`VlmAnalyzer` runs.

**Question `[?]`:** Beyond `OD-7`'s weapons fast path, do we want to explore a **two-stage VLM batch
lifecycle** (where a person detection in an entry zone triggers an early T+3s preview assessment
using the first 2–3 frames, followed by a full 4-frame update when the 30s/90s batch closes), or is
the 30s idle / 90s window with `OD-7`'s weapons fast path sufficient for go-live?

---

### 2.3 Candidate Option C: Set-of-Mark (SoM) Visual Prompting Experiment **[?]**

#### Current State **[V]**

`VlmClient._render_prompt` (`backend/services/vlm_client.py`) passes detection boxes as normalized
`[x1, y1, x2, y2]` (`0..1000`) integer arrays in text (`_grounded_boxes`), while `_image_parts`
embeds the unannotated camera JPEG.

#### Candidate Experiment Question `[?]`

On multi-detection or low-light scenes, would drawing a thin, high-contrast bounding box with a
compact `#det_id` tag onto an in-memory copy of each selected key frame before base64 encoding in
`VlmClient._image_parts` improve grounding and `S3` recall compared to text-only `0..1000`
coordinates? (Can be tested as a single transport-shim arm on the `tierb-v0` dev split under
`ISS-016` / `ISS-043`).

---

## 3. Seven Concrete Gaps in the Shipped Pipeline (Mapped to `17-action-plan.md`)

Independent of `OD-2`'s scoring question, seven concrete gaps in the current codebase affect input
coverage, specialist execution, spatial context, alerting, and health checks.

### Gap 1: Video Uploads (`.mp4` / `.mkv`) Fail VLM Assessment (`ISS-002`, `ISS-003`, `ISS-004`, `OD-5`)

- **Current behavior **[V]**:**
  - `FileWatcher` (`backend/services/file_watcher.py`) and
    `DetectionQueueWorker._process_video_detection` (`backend/services/pipeline_workers.py:628`)
    accept video files. `DetectorClient.detect_objects` extracts temporary JPEG frames for YOLO26
    and stores the `.mp4` container path as `Detection.file_path`, while `pipeline_workers.py:746`
    unlinks the extracted JPEGs in its `finally` block.
  - When the batch reaches `VlmClient._image_parts` (`backend/services/vlm_client.py`),
    `suffix not in IMAGE_MIME_TYPES` raises `VlmImageError("key frame ... is a video/mp4 container,
not a still the vlm path can embed")`.
  - In a mixed batch containing both `.jpg` stills and `.mp4` clips, `select_key_frames`
    (`backend/services/key_frame_selector.py`) does not filter by media type: if an `.mp4` row has
    the highest confidence, it is selected into `image_paths` and causes the entire batch's VLM
    verdict to fail (`ISS-004`).
- **Status & Open Question (`OD-5` / `ISS-003`) `[?]`:**
  - `ISS-004` (filtering `select_key_frames` candidates so an `.mp4` row never sinks a mixed batch
    that has valid stills) is `agent-now` bug work.
  - How video batches themselves reach `vlm_assess` (`ISS-002`, `ISS-003` — e.g. retaining extracted
    keyframe JPEGs from `_process_video_detection` vs. a video-native VLM route after a llama.cpp
    re-pin) is gated on **`OD-5`**, which remains **open** pending the funded multi-frame clip
    experiment (`17-action-plan.md §4`, `OD-5`).

### Gap 2: Specialists Ship Off by Default on Sub-24 GB / Non-`setup.py` Installs and Are Unmeasured in Replay (`ISS-023`, `ISS-024`, `ISS-025`)

- **Current behavior **[V]**:**
  - `osnet_loader.get_reid_handle()` (`backend/services/osnet_loader.py`) and
    `face_recognizer_loader.get_face_leg_handles()` (`backend/services/face_recognizer_loader.py`)
    are membership reads that never trigger an on-demand load; they rely on the startup preload
    sweep in `backend/main.py`, gated on `settings.backend_model_preload`.
  - `BACKEND_MODEL_PRELOAD` defaults to `false` in `.env.example`, `docker-compose.prod.yml`, and
    `backend/core/config.py`. `setup.py:599` auto-enables `BACKEND_MODEL_PRELOAD=true` only when
    detected GPU VRAM is $\ge 24\text{ GB}$ (`docs/architecture/ai-pipeline-current-state.md §2.3`).
    On sub-24 GB cards (12 GB / 16 GB GeForce tiers) or installs that do not run `setup.py` on a
    24 GB+ host, `faces` and `person_reid` return `"unavailable: specialist did not run"` on every
    event, even though both run on CPU (`UR-85`: `REID_BACKEND=local`, while `O2.4` diagnoses
    TensorRT parity on GB300 under `[r157]`).
  - Furthermore, `vlm_replay.py` reads stored `specialist_outputs` without running specialists, and
    the 450-item `tierb-v0` export carries empty `specialist_outputs` (`ISS-024`). As
    [`23 §2.3`](23-prompt-programme-stages-1-4-2026-10-05.md) showed, `resident_arrival` false
    positives (`0/10` prompt-addressable) cannot be distinguished by prompt wording alone without
    specialist identity output.
- **Candidate Remedy (`ISS-023`, `ISS-024`, `ISS-025` — `agent-now`):**
  - Enable safe lazy-loading (or default CPU preload) for the lightweight CPU specialist legs, ship
    `fast-alpr` in the backend image (`ISS-023`), and populate `specialist_outputs` in the
    evaluation store (`ISS-024`).

### Gap 3: `Detection.track_id` Has No Writer, Making `zone_crossing` Always `False` (`ISS-035`)

- **Current behavior **[V]**:**
  - `VlmAnalyzer.analyze_batch` passes `zones` and `zone_crossing` into `build_assess_context`
    (`backend/services/vlm_analyzer.py:124`), computing `zone_crossing` via
    `detect_zone_crossing(detections, zone_names_by_detection_id)` (`vlm_analyzer.py:171`, called at
    `:624`).
  - `detect_zone_crossing` requires a `track_id` seen in two different zones. Because
    `Detection.track_id` has no production writer (`ISS-035`), `zone_crossing` is always `False`,
    and `VlmClient._render_prompt` prints `(crossing: False)` as a fact in every prompt.
- **Candidate Remedy (`ISS-035`):**
  - Avoid asserting `(crossing: False)` when `track_id` is absent on all rows in the batch (render
    `crossing: unknown` or omit the suffix until a track writer exists).

### Gap 4: `AlertRuleEngine` and Outbound Delivery Channels Are Unwired (`ISS-019`, `ISS-020`, `ISS-047`, `ISS-091`)

- **Current behavior **[V]**:**
  - `VlmAnalyzer._notify_decision` persists `event_notify_decisions` and broadcasts `notify`, but
    nothing in `VlmAnalyzer` calls `AlertRuleEngine.evaluate_event`, `create_alerts_for_event`
    (`backend/services/alert_engine.py`), or outbound notification/webhook delivery.
- **Scheduled Remedy (Uplevel Phase 4 `B4.*` P1, Rulings 89 & 139):**
  - Already ruled **complete (P1)** in `R2a` (`F-216`, `F-217`, `OD-1` option (c) reopened).

### Gap 5: Text-Only `ai-vlm` (`MMPROJ_PATH` Missing) and Probe Image Sensitivities (`ISS-071`)

- **Current behavior **[V]**:**
  - `ai/vlm/Dockerfile` passes `--mmproj` conditionally (`if [ -n "${MMPROJ_PATH}" ]`). Without it,
    `llama-server` starts in text-only mode and returns `HTTP 200` on `/health`
    (`docs/architecture/ai-pipeline-current-state.md §2.1`).
  - In `VlmClient._probe_enforcement(self, image_parts)` (`backend/services/vlm_client.py:364`,
    called at `:934`), the probe sends `image_parts` and verifies that `response_format.json_schema`
    echoes `probe_const`, but runs lazily on the first `assess` call rather than at startup, and
    `VLM_REQUIRED_BUILD` is unset by default (`ISS-071`).
- **Candidate Remedy (`ISS-071` — `agent-now`):**
  - Fail fast in `ai/vlm/Dockerfile` if `MMPROJ_PATH` is unset or missing on disk, and run an
    image-bearing readiness check at startup.

### Gap 6: Prompt-Fit Truncation Ranks Rows by Raw Confidence Only (`ISS-006`)

- **Current behavior **[V]**:**
  - When a batch exceeds the 16,384-token slot budget, `VlmClient._fitted_prompt`
    (`backend/services/vlm_client.py`) sorts detection rows solely by descending `confidence` and
    drops the tail, which can drop the detection row associated with an attached key frame
    (`request.frame_detection_ids`) or a lower-confidence person/threat row (`ISS-006`).
- **Candidate Remedy (`ISS-006` — `agent-now`):**
  - Pin detection rows referenced by `request.frame_detection_ids` (and at least one row per class)
    before truncating remaining rows by confidence.

### Gap 7: Unresolved Relative `image_paths` in `_frame_sizes` (`ISS-070`)

- **Current behavior **[V]**:**
  - `VlmClient._image_parts` resolves relative paths against `Path(self._settings.foscam_base_path)`,
    whereas `_frame_sizes` (`backend/services/vlm_client.py`) opens `Path(raw)` directly via
    `Image.open`, silently falling back to pixel `[x, y, w, h]` coordinates when given a relative
    path (`ISS-070`).
- **Candidate Remedy (`ISS-070` — `agent-now`):**
  - Share a single path-resolution helper between `_image_parts` and `_frame_sizes`.

---

## 4. Questions for the Owner at Phase 4 Design Entry (`[?]`)

When Uplevel Phase 3 completes and the Phase 4 design sessions (`UR-77`, `UR-79`) open, the
following questions from §§2–3 can be settled with the owner:

1. **Scope of `BB.6` (`docs/uplevel/packages/backend.md:195`) `[?]`:** Should the `agent-now` VLM
   plumbing fixes (`ISS-004`, `ISS-006`, `ISS-070`, `ISS-071`, `ISS-035`'s `crossing` label) fold
   into `BB.6`'s design session, or be queued as separate `agent-now` bug packages?
2. **`OD-2` Remedy (`ISS-008`, §2.1) `[?]`:** Should we run a pre-registered experiment on the
   `tierb-v0` dev split (`ISS-016`) testing **Path A (Structured Threat Observables $\rightarrow$
   Deterministic Python Policy Scoring)** to address the 43.2% S3 ceiling?
3. **`OD-5` Video Path (`ISS-002`, `ISS-003`, §3 Gap 1) `[?]`:** Once the funded multi-frame clip
   experiment concludes, should `.mp4` camera uploads retain extracted keyframe JPEGs in
   `_process_video_detection` for `vlm_assess`, or target a video-native VLM route?
4. **Specialist Lazy-Load & Eval Context (`ISS-023`, `ISS-024`, `ISS-025`, §3 Gap 2) `[?]`:** Should
   CPU specialists (`SCRFD`/`ArcFace`, `OSNet-AIN`, `FastALPR`) lazy-load on first batch when
   `BACKEND_MODEL_PRELOAD=false` so 12 GB / 16 GB RTX tiers get face, plate, and re-ID context by
   default?

For the companion product and UI design input for **Ruling 182** (`Easy Mode` vs. `Advanced Mode`
for desktop RTX gaming GPUs), see
[`docs/superpowers/2026-10-14-rtx-vss-blueprint/easy-advanced-mode-design.md`](../superpowers/2026-10-14-rtx-vss-blueprint/easy-advanced-mode-design.md).
