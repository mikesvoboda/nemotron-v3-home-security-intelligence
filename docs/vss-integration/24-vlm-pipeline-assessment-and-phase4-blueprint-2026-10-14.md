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
2. **Wave 2 — R8 Legacy LLM & Enrichment Retirement (Sept 29 – Oct 2):** `602379e2` deleted the
   legacy LLM tier — `backend/services/nemotron_analyzer.py` and the whole `ai/nemotron` tree — and
   `3b73b9b6` deleted the `ai/{florence,clip,enrichment,enrichment-light}` trees with their gateway
   adapters and client services. (`e40d69f5` is a separate docs/monitoring/deploy residue sweep: its
   33 deletions touch no `backend/` or `ai/` module, so it retired nothing.) This narrowed the
   specialist stage to three database-backed identity lookups (`faces`, `plates`, `person_reid`)
   guarded by four-state face classification — `match`, `unknown`, `not_identifiable` on
   `FaceOutcome`, plus `FaceUnavailable`, whose `kind` is a **class, never a score**
   (`vlm_specialists.py:135`, `:144`, `:161`) — and model-ID vector-space checks
   (`classify_face_outcome` `vlm_specialists.py:179`, `compare_person_vectors`
   `household_matcher.py:139`; both reach trunk in Wave 1 `4bfd6fa4`, authored a day or two earlier on
   the feature branches) **[V]**.
3. **Wave 3 — Greedy Decoding, Token Budget & `OD-29` Operating Point (Oct 3–5):** Set
   `_ASSESS_TEMPERATURE = 0.0` (`9f4e65cd`, achieving 450/450 run-to-run replay reproducibility on
   `tierb-v0` **[A]**), raised `_ASSESS_MAX_TOKENS` to `2048` (`26b900bc`, with the timeout ladder
   subsequently repaired in Uplevel `B1.1` `#6868` via `VlmSlowReplyError` **[V]**), and shipped the
   `OD-29` operating point (`c0191f4d`: Arm B severity rubric + per-camera default
   `risk_threshold = 60`) **[V]**.
4. **Wave 4 — End-to-End Notification Decision Persistence (Oct 3–6):** Wired
   `decide_notification` — a **module-level** function in `notification_filter.py:218`, distinct from
   the class method `NotificationFilterService.should_notify` (`:44`), which it wraps — into
   `VlmAnalyzer` and put `notify` on the WebSocket schema (`ab3bd002`); persisted the decision and
   exposed it on the REST surface (`db83f1f8`). `1a2c83d1` is docs-only: it recorded that
   `ISS-001` and `ISS-018` had landed **[V]**.
5. **Wave 5 — Statistical Rigor & Multi-Frame Temporal Context (Oct 6–7):** Added scenario-cluster
   bootstrap intervals and exact McNemar paired tests (`d8b461a8`, `ISS-043`), froze the `tierb-v0`
   dev/holdout split as a published hash draw (`54d036d5e`, with the `splits` table added by
   `dc4607c2` and `ISS-016` closed by `641bf109a` over the range `54d036d5`..`8cdbb412`), attached
   multi-frame batches oldest-first with
   capture-time labels (`acd6d6d6`, `ISS-033`), and spread spare key-frame slots across temporally
   distant stills of dwelling `(camera, class)` pairs (`a71cc785`, `ISS-005`). Replay parity in
   `vlm_replay.py` came later than this window: `B1.2` (`#6924`) merged 2026-10-09, two days **after**
   the `d6ba78d5` baseline, so it is not part of the pre-Uplevel waves this section counts **[V]**.

### The Unresolved Core Bottleneck

Despite the 15-arm sweep — 12 model arms across 10 distinct upstream repositories (12 distinct
weight files; two repos contribute two quantizations each) plus 3 controls — reported in
`6144f132f` and recorded by `08d0bf21` (`ISS-097`), and the 4-stage, 10-arm controlled prompt
programme (`26b900bc`, `60022dd0`, `c0191f4d`; banked in
[`22`](22-prompt-research-and-probes-2026-10-04.md) and
[`23`](23-prompt-programme-stages-1-4-2026-10-05.md)), the shipped `OD-29` operating point (Arm B
rubric + per-camera alert floor `60`) scores on the 450 `tierb-v0` stills:

- **S2 (benign false-alarm rate, bar $\le 5\%$):** `9/209 = 4.3%` `[2.3–8.0]` — **does not clear the
  bar**: the interval straddles 5%, and `F14` labels a straddling result _marginal_, not a pass
  (`18-world-class-target.md:131`). The figure is a **fresh-install reading** of the `OD-29` operating
  point (`c0191f4d`), and the register says so in its own words: at the shipped gate the same arm
  reads `21/209 = 10.0%` `[6.7–14.9]`, so "both `F14` bars still missed" (`17-action-plan.md §4`,
  `OD-29` update; ledger row 82). `23 §5` carries no measurement numbers and is not this source. **[V]**
- **S3 (incident hit rate, bar $\ge 90\%$):** `104/241 = 43.2%` `[37.1–49.5]` (46.8 percentage
  points below the `F14` 90% bar; the flagship — 191.5 GB resident on the 256.7 GB GB300, per
  `p5a-probes.md:4` — reached `58.9%` `[52.6–65.0]` in `p5a-2026-09-30.md:23`, which carries the
  hit rate but not the footprint figure) **[A]**

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
- **Grammar digit saturation:** Token-probability expected value (`EV_C` over logprobs) did **not**
  beat argmax — `22 §2` calls the difference a **coin-flip** (AUROC 0.6250 vs 0.6324 on `nc`,
  0.6426 vs 0.6676 on `nc_rp1`; paired-bootstrap gaps −0.007 `[−0.109, +0.089]` and −0.025
  `[−0.109, +0.055]`, P(argmax wins) 0.43/0.26), and on the native-floor rule `EV_C` is **strictly
  worse**: 7/17 hits against argmax's 12/17, buying 6 fewer false alarms at 3× n. The mechanism is
  that constrained JSON decoding saturates the digit distribution — median
  `|EV − argmax| ≈ 0.1` — so what looks like an EV edge is tie-breaking, not signal (`22 §2`).
- **Latent discrimination exceeds single-threshold hits:** In Stage 2 (`23 §1`), all four
  reasoning-bearing arms improved AUROC against plain-benign stills by `+0.20` to `+0.245` (CI lower
  bound $> 0$), showing that `Qwen3-VL-8B` distinguishes suspicious from benign scenes more
  reliably than its raw `0–100` integer threshold crossings reflect. Meanwhile `23 §2` item 1 (the
  Stage 2 arm `vb`, verdict-before-reasoning) showed that placing `verdict` before `reasoning` is
  actively harmful (`dS3 −17.0`, CI `[−30.6, −3.3]` vs arm A), while placing `verdict` last causes
  truncation on evidence-rich scenes (`verify` arm: 97 truncated rows at 2,048 tokens, against 342
  completed rows at a median 425.5 tokens). Doc 23's own conclusion, as written: **"verdict early,
  reasoning after — which is what arm (b) already does"** — the two readings point the same way;
  "safest" is this doc's word, not 23's. (`23` has no subsections, so the cite is `23 §2`, not
  `23 §2.1`.)

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
  `risk_score >= 60` on calm-looking floor-60 scenes — Probe 3 names _peering_ and _trying car doors_
  (`22 §2`, and `trying_car_doors` in the corpus tables; there is no `testing_door_handle` scenario) —
  may
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

- Ruling 89 rules `OD-7` in **two parts** (`17-action-plan.md:584`, `6854 6102602152`). **Part 1** is
  the weapons fast path, gated: pin the Hugging Face revision of `Subh775/Threat-Detection-YOLOv8n`
  and read the checkpoint's own class names (fixing the gateway's labels); **measure false positives
  on home-camera images — tools, umbrellas, garden equipment — and precision per class**, with **the
  owner setting the acceptable false-positive rate** and settling the licence; only then
  `GATEWAY_ENABLE_THREAT` on, add the backend `/enrich-lt/threat-detect` caller, and publish
  `threat_detected`; the smoke/fire stub is deleted, since no model detects smoke. **Part 2** is the
  Alerts surface: once row 1's rules engine runs, the **Alerts page lists rule hits** from the
  `alerts` table, a default "risk high or critical" rule is created on upgrade and new installs, and
  unverified (NULL-score) events appear badged (`F-077`, `F-078`). The surfaces that consume the fast
  path are already `complete, gated` at **P4** — `F-010` (header recent-threats indicator,
  `docs/reference/feature-inventory.md:131`) and `F-036` (dashboard threat banner, `:165`) — "completed against the
  weapons fast path once its gates pass".
- A separate item, **not** part of `OD-7`: Uplevel ruling 168's `fast_path_enabled` boolean flag for
  the existing `BatchAggregator` fast-path hook. It is a settings-bug fix that makes the legacy
  confidence-threshold path's "disabled" state explicit; it lives in `[r130b]` **`#7088`, which is
  still open** — the flag is **not on `main`** (0 hits for `fast_path_enabled` under `backend/` at
  `origin/main`) **[V]**.

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
    accept video files. It is **`_process_video_detection` that extracts the frames**, via
    `extract_frames_for_detection_batch` at `pipeline_workers.py:657` (defined
    `video_processor.py:632`); `DetectorClient.detect_objects` (`detector_client.py:993`) only stores
    the `.mp4` container path as `Detection.file_path` for every row of the video frame
    (`:1173-1177`, `:1283`) — the extracted JPEG path never reaches the row. `pipeline_workers.py:746`
    then unlinks the extracted frames in its `finally` block
    (`cleanup_extracted_frames`, `video_processor.py:812`).
  - When the batch reaches `VlmClient._image_parts` (`backend/services/vlm_client.py`),
    `suffix not in IMAGE_MIME_TYPES` raises `VlmImageError("key frame ... is a video/mp4 container,
not a still the vlm path can embed")`.
  - In a mixed batch containing both `.jpg` stills and `.mp4` clips, `select_key_frames`
    (`backend/services/key_frame_selector.py`) does not filter by media type. The reason it _cannot_:
    the analyzer's row dict (`vlm_analyzer.py:517-535`) never carries `media_type`, and `FrameRef`
    has no such field, so the selector is blind to it. So it is **any** `.mp4` that lands in one of
    the four `MAX_KEY_FRAMES` slots — not only the top-confidence row — that puts a clip path into
    `image_paths` and fails the whole batch's verdict: `vlm_client.py:590` raises
    `VlmImageError`, which is in `_DEGRADABLE_ERRORS`, and the batch lands
    `verification_failed` with a NULL score. The code names this as its own known gap at
    `vlm_client.py:577-582` (`ISS-004`).
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
    `backend/core/config.py`. The $\ge 24\text{ GB}$ decision is **`should_preload_models`**
    (`setup_lib/nvidia_detect.py:224`, threshold `PRELOAD_MIN_VRAM_MB = 24 * 1024` at `:221`,
    inclusive so a card reporting exactly 24576 MiB does not lose on its own spec figure), called at
    `setup.py:805`/`:1053`/`:1232`; `setup.py:599` only _writes_ the resulting line into the
    generated `.env` (`docs/architecture/ai-pipeline-current-state.md §2.3`).
    On sub-24 GB cards (12 GB / 16 GB GeForce tiers) or installs that do not run `setup.py` on a
    24 GB+ host, `faces` and `person_reid` return `"unavailable: specialist did not run"` on every
    event, even though both can run on CPU. `UR-85` is what pins re-ID there: _"Production re-ID stays
    OSNet-AIN on the CPU (`REID_BACKEND=local`) until a later ruling"_ — it says nothing about the
    face legs or about TensorRT, so the face question and the TensorRT parity work under `O2.4`
    (`[r157]`, GB300) are separate rulings, not `UR-85` coverage.
  - Furthermore, `vlm_replay.py` reads stored `specialist_outputs` without running specialists, and
    the 450-item `tierb-v0` export carries empty `specialist_outputs` (`ISS-024`). As
    [`23 §2` item 3](23-prompt-programme-stages-1-4-2026-10-05.md) measured, `resident_arrival` false
    positives are **`0/10` prompt-addressable** — the A0 audit bounds how far prompts reach at all
    (44/64 A-incidents, 68.75%) — and `23 §3` assigns that class to the detector/specialist tier as
    prompt-unreachable. Neither is fixable by prompt wording alone without specialist identity output.
    (`23` has no `§2.3`; the cite is `§2` item 3, with `§3` for the tier.)
- **Candidate questions (`ISS-023`, `ISS-024`, `ISS-025`) `[?]`:**
  - Would safe lazy-loading (or CPU preload by default) for the lightweight CPU specialist legs be the
    right shape, and should `fast-alpr` ship in the backend image (`ISS-023`)? Note the leg already
    _attempts_ an on-demand load — `load_fast_alpr` (`fast_alpr_loader.py:66`) is called per plate leg
    at `vlm_specialists.py:568` and constructs a fresh `ALPR` each time with no cache — but it can
    never succeed: `backend/Dockerfile:144` installs only `--extra face`, so the import guard raises
    first (`fast_alpr_loader.py:79`, `:86`). `ISS-023` is the packaging gap, not a missing lazy-load
    path. And should `specialist_outputs` be populated in the evaluation store (`ISS-024`)?

### Gap 3: `Detection.track_id` Has No Writer, Making `zone_crossing` Always `False` (`ISS-035`)

- **Current behavior **[V]**:**
  - `VlmAnalyzer.analyze_batch` passes `zones` and `zone_crossing` into `build_assess_context` (the
    call is at `backend/services/vlm_analyzer.py:619`; the function is defined at `:106` — `:124` is a
    docstring line, not the call), computing `zone_crossing` via
    `detect_zone_crossing(detections, zone_names_by_detection_id)` (defined `vlm_analyzer.py:171`,
    called at `:624`).
  - `detect_zone_crossing` requires a `track_id` seen in two different zones. Because
    `Detection.track_id` has no production writer (`ISS-035`), `zone_crossing` is always `False`,
    and `VlmClient._render_prompt` prints `(crossing: False)` as a fact in every prompt.
- **Candidate questions (`ISS-035`):** `[?]`
  - When `track_id` is absent on every row in the batch, should `_render_prompt` render
    `crossing: unknown` or omit the suffix, rather than asserting `(crossing: False)` as a fact?

### Gap 4: `AlertRuleEngine` and Outbound Delivery Channels Are Unwired (`ISS-019`, `ISS-020`, `ISS-047`, `ISS-091`)

- **Current behavior **[V]**:**
  - `VlmAnalyzer._notify_decision` decides and persists the row to `event_notify_decisions`
    (`backend/services/vlm_analyzer.py:876`; persist at `:928`), and a separate `_broadcast` (`:947`)
    is what attaches `notify` to the WebSocket payload (`:979`); both are called from `analyze_batch`
    at `:742` / `:754`. Nothing in `VlmAnalyzer` calls `AlertRuleEngine.evaluate_event`
    (`backend/services/alert_engine.py:166`), `create_alerts_for_event` (`:1039`), or outbound
    webhook delivery.
- **What is already ruled, precisely:**
  - Only the **rules-engine half** is ruled **complete (P1)** in `R2a` — `F-216` and `F-217`
    (`docs/reference/feature-inventory.md:409`, `:410`), whose ruling cells read "complete — re-opens
    `OD-1` option (c): call the rules engine after each verdict (`R2a` row 1)". Their `status` cells
    still read `half-built`, which is today's code state: `AlertRuleEngine` is constructed only by
    the DI factory (`backend/api/dependencies.py:918`) and by `backend/services/__init__.py`, and no
    production code calls `evaluate_event` or `create_alerts_for_event` (the module's own docstring
    and `api/routes/ai_audit.py:194`, a same-named but unrelated audit endpoint, are the only other
    mentions).
  - The outbound-webhook half is a **different row at a different tier**: `F-246`
    (`docs/reference/feature-inventory.md:447`) is `event_created` / `anomaly_detected` **complete at
    P2**, with the remaining (batch) types retired. But the issue that holds the `EVENT_CREATED` ask,
    `ISS-091`, is still `status open` (`17-action-plan.md:1076`–`:1078`), and the inventory's
    `complete` there records the owner's ruling, not shipped code.
  - **Which** `EVENT_CREATED` is missing matters, because two carry the name: the browser-facing
    WebSocket broadcast exists (`backend/services/websocket_emitter.py:455` → `broadcast_event`),
    while the `outbound_webhooks` one does not. Its emitter was
    `NemotronAnalyzer._trigger_event_created_webhook`, deleted with the file by `602379e2`; production
    now triggers only the `alert_*` types plus `entity_discovered` — the lone in-engine
    `ALERT_FIRED` trigger at `alert_engine.py:1113` sits inside the unwired engine above.
  - (`Ruling 139`, paired with 89 in earlier drafts of this section, is unrelated: it is the `R2a`
    alert-rules schedule-end-minute ruling, `docs/uplevel/history/ruling-map.md:154`. Priority tiers came from ruling 89.)

### Gap 5: Text-Only `ai-vlm` (`MMPROJ_PATH` Missing) and Probe Image Sensitivities (`ISS-071`)

- **Current behavior **[V]**:**
  - `ai/vlm/Dockerfile` passes `--mmproj` conditionally (`if [ -n "${MMPROJ_PATH}" ]`). Without it,
    `llama-server` starts in text-only mode and returns `HTTP 200` on `/health`
    (`docs/architecture/ai-pipeline-current-state.md §2.1`).
  - In `VlmClient._probe_enforcement(self, image_parts)` (`backend/services/vlm_client.py:364`,
    called at `:934`), the probe sends only the **first** image part (`*image_parts[:1]` at `:416`)
    and verifies that `response_format.json_schema` echoes `probe_const`, but runs lazily on the
    first `assess` call rather than at startup (`ISS-071`).
  - Whether the build assertion is on depends on which default you install from, and the repo ships
    four: `backend/core/config.py:1377` defaults `vlm_required_build` to `""` and
    `docker-compose.prod.yml:569` passes `${VLM_REQUIRED_BUILD:-}` (assertion skipped), but
    `.env.example:271` ships `b7972` and the fake-AI overlay defaults it the same way
    (`docker-compose.fake-ai.yml:116`) — so a fresh install from `.env.example`, which the
    `docs/vss-integration/README.md` pin line names, has the assertion **on**, and only the
    compose-without-`.env` path has it off.
- **Candidate questions (`ISS-071` — `agent-now`):** `[?]`
  - Should `ai/vlm/Dockerfile` fail fast when `MMPROJ_PATH` is unset or missing on disk, and should
    an image-bearing readiness check move to startup rather than the first `assess`?
  - Which of the four `VLM_REQUIRED_BUILD` defaults should be the shipped one, and should they be
    reconciled (`17-action-plan.md:4539` already flags `.env.example` against the compose default)?

### Gap 6: Prompt-Fit Truncation Ranks Rows by Raw Confidence Only (`ISS-006`)

- **Current behavior **[V]**:**
  - When a batch exceeds the 16,384-token slot budget, `VlmClient._fitted_prompt`
    (`backend/services/vlm_client.py:836`) orders rows on the `_rank_for_budget` total order —
    descending `confidence`, with `-id` breaking ties so survivors never depend on arrival order
    (`:827`, `reverse=True` at `:880`) — and keeps the **longest prefix that fits** a binary search
    (`:894-901`), not a fixed cut. Any dropped row can be the one attached to a key frame
    (`request.frame_detection_ids`) or a lower-confidence person/threat row (`ISS-006`).
- **Candidate questions (`ISS-006` — `agent-now`):** `[?]`
  - Should rows referenced by `request.frame_detection_ids` (and at least one row per class) be
    pinned ahead of the budget before the remaining rows drop by confidence?

### Gap 7: Unresolved Relative `image_paths` in `_frame_sizes` (`ISS-070`)

- **Current behavior **[V]**:**
  - `VlmClient._image_parts` resolves relative paths against `Path(self._settings.foscam_base_path)`,
    whereas `_frame_dims` (`backend/services/vlm_client.py:717`) opens each raw path directly via
    `Image.open` (`:724`) — it is the shared opener behind both `_frame_sizes` (`:731`) and
    `_grounded_boxes` (`:740`) — silently degrading to `None` dims, hence pixel `[x, y, w, h]`
    coordinates, when given a relative path (`ISS-070`).
- **Candidate questions (`ISS-070` — `agent-now`):** `[?]`
  - Should `_image_parts` and `_frame_dims` share one path-resolution helper, so a relative path
    resolves (or fails loudly) the same way on both sides?

---

## 4. Questions for the Owner at Phase 4 Design Entry (`[?]`)

When Uplevel Phase 3 completes and the Phase 4 design sessions (`UR-77`, `UR-79`) open, the
following questions from §§2–3 can be settled with the owner:

1. **Scope of `BB.6` (`docs/uplevel/packages/backend.md:195`) `[?]`:** Should the `agent-now` VLM
   plumbing fixes (`ISS-004`, `ISS-006`, `ISS-070`, `ISS-071`, `ISS-035`'s `crossing` label) fold
   into `BB.6`'s design session, or be queued as separate `agent-now` bug packages?
2. **`OD-2` Remedy (`ISS-008`, §2.1) `[?]`:** Should we run a pre-registered experiment on the
   `tierb-v0` dev split (`ISS-016`) testing **Candidate Option A (Structured Threat Observables
   $\rightarrow$ Deterministic Policy Scoring)** — the §2.1 name for it — to address the 43.2% S3
   ceiling?
3. **`OD-5` Video Path (`ISS-002`, `ISS-003`, §3 Gap 1) `[?]`:** Once the funded multi-frame clip
   experiment concludes, which of `OD-5`'s recorded options applies (`17-action-plan.md:582`): a
   roadmap entry or spec for a video-capable engine; keep clips as assets (unscored); retain
   extracted keyframe JPEGs in `_process_video_detection` for `vlm_assess` — noting `OD-5`'s own
   guard that frame bursts do not go through the product VLM?
4. **Specialist Context on 12/16 GB Tiers (`ISS-023`, `ISS-024`, `ISS-025`, §3 Gap 2) `[?]`:** The
   three specialists sit in two different states. Face (`SCRFD`/`ArcFace`) and re-ID (`OSNet-AIN`)
   never load on demand — `get_face_leg_handles` (`face_recognizer_loader.py:466`) and
   `get_reid_handle` (`osnet_loader.py:208`, "a membership read, NEVER a load trigger") return `None`
   unless the `models.yml` `preload: true` rows were loaded by the boot sweep, which the
   install-time `BACKEND_MODEL_PRELOAD` write (`should_preload_models`, §3 Gap 2) gates on ≥24 GB.
   FastALPR **does** attempt an on-demand load per plate leg (`load_fast_alpr`,
   `fast_alpr_loader.py:66`, called at `vlm_specialists.py:568`) but can never succeed, because the
   image installs only `--extra face` (`backend/Dockerfile:144`) — that half is the `ISS-023`
   packaging gap, not a lazy-load question. So: should the `models.yml` residency of the face/re-ID
   rows become independent of the install-time VRAM guess for the 12/16 GB tiers, and separately,
   does `ISS-023` ship as a packaging fix (`fast-alpr` into the backend image)?

For the companion product and UI design input for the **Ruling 182** BINDING NOW record (`Easy Mode`
vs. `Advanced Mode` for desktop RTX gaming GPUs; `#6854 6174228588`, not yet carried by a merged PR)
see
[`docs/superpowers/2026-10-14-rtx-vss-blueprint/easy-advanced-mode-design.md`](../superpowers/2026-10-14-rtx-vss-blueprint/easy-advanced-mode-design.md).
