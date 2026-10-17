Owner spec, 2026-10-14: input to the Phase 4 design sessions (ruling 182, UR-182). The ruling sets scope, not design.

# Consumer NVIDIA VSS Blueprint: Easy Mode vs. Advanced Mode & RTX Gaming GPU Architecture

> **Date:** 2026-10-14 · **Author:** Owner + Design Partner · **Status:** Design Spec (`OD-33` / `UR-87` home: `docs/superpowers/specs/`) · **Feeds:** Uplevel Phase 3 (`B3.1`/`F3.1` rescue adjustments) and Phase 4 (`B4.*` / `F4.*` / `BB.6`).

---

## 1. Product Thesis: Why This Platform Exists

Closed consumer camera ecosystems (Ring, SimpliSafe, Nest, Arlo) already offer simple cloud-based
motion notifications in exchange for monthly subscriptions and uploading private home footage to
third-party servers. Meanwhile, NVIDIA's **Video Search and Summarization (VSS) Blueprint**
demonstrates what modern multimodal AI can do—natural-language visual search, temporal event
summarization, and multi-stage specialist + VLM reasoning—but targets enterprise data-center GPUs
and heavy cluster infrastructure (Milvus, Kafka, Neo4j, multi-engine vLLM).

**Home Security Intelligence** bridges that gap:

1. **Target Hardware:** The tens of millions of **NVIDIA GeForce RTX gaming GPUs** (RTX 30-series,
   40-series, 50-series; 12 GB to 32 GB VRAM) already deployed in desktop PCs and home workstations
   sitting idle 20+ hours a day.
2. **Value Proposition:** Run an enterprise-grade NVIDIA VSS visual search, identity recognition,
   and multimodal reasoning pipeline **for free**, on hardware you already own, with **100% local
   data sovereignty** (`$0` cloud fees, zero footage leaving your LAN).
3. **Dual Persona ("Appliance by Default, AI Workbench on Demand"):**
   - A household member checking why the front-porch chime went off wants a clean, zero-jargon
     security app (**Easy Mode**).
   - The RTX GPU owner who deployed the stack wants to see their TensorRT + `llama.cpp` pipeline
     in action, inspect exact VLM prompts and keyframe bounding boxes, experiment with prompts and
     models on real events, and yield VRAM when launching a game (**Advanced Mode**).

---

## 2. The Two-Mode UI Architecture (`Easy Mode` vs. `Advanced Mode`)

A single, persistent mode switch in the top `Header` (`frontend/src/components/layout/Header.tsx`,
stored in `security-dashboard-settings` / Zustand):

- **`Easy Mode` ("Home Monitor" — Default):** Clean, high-signal home security interface for daily
  household use.
- **`Advanced Mode` ("NVIDIA AI Blueprint"):** Unlocks the AI X-Ray, GPU VRAM & TensorRT telemetry,
  Interactive Prompt & Replay Lab, and deep observability.

### 2.1 Navigation & Chrome by Mode

| Surface                | `Easy Mode` (Default — 5 Top-Level Items)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | `Advanced Mode` (Adds AI Blueprint Surfaces)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| :--------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Header Bar**         | • System protection status (`Protected` / `Armed` / `Degraded`)<br>• Unread alert badge<br>• `Easy \| Advanced` mode toggle                                                                                                                                                                                                                                                                                                                                                                                                                         | Adds:<br>• **Live RTX Telemetry Pill** (`F-006`): `GPU % · °C · VRAM Used/Total · VLM tok/s`<br>• **1-Click "Gaming Mode (Yield VRAM)" Toggle** (`F-128`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| **Left Sidebar**       | 1. **Dashboard** (`/`) — Live cameras, daily AI digest (`F-034`), recent activity<br>2. **Timeline & Search** (`/timeline`) — Visual search (`F-043`), event filters, clips<br>3. **Alerts & Rules** (`/alerts`, `/settings/rules`) — Rule hits (`F-216`/`F-217`), Home/Away/Night arming (`UR-12`)<br>4. **Household** (`/household`, `/face-recognition`, `/plate-reads`, `/zones`) — Consolidated tabs for Known Persons & Faces, Vehicles & Plates, and Camera Zones<br>5. **Settings** (`/settings`) — Cameras, Notifications, Storage, Access | Adds:<br>6. **AI Workbench** (`/ai-audit`, `/settings/prompts`) — Prompt Playground & GPU A/B Replay Lab (`F-109`–`F-113`, `F-120`–`F-124`), Batch Quality Audit (`F-106`, `F-108`)<br>7. **GPU & Model Zoo** (`/ai`, `/settings/ai-models`, `/settings/gpu`) — RTX VRAM Budget Bar (`F-127`), Hardware Profile Picker (`F-176`, `F-178`), Model Zoo status & latency (`F-104`, `F-105`, `F-125`–`F-130`)<br>8. **Entity & Re-ID Explorer** (`/entities`, `/reid`, `/heatmaps`, `/scene-changes`) — Cross-camera OSNet-AIN cosine search (`F-081`–`F-086`)<br>9. **Operations & Monitoring** (`/operations`, `/monitoring`) — Circuit breakers, pipeline queues, and the consolidated Grafana/Pyroscope/Tempo picker (ruling 128) |
| **Event Detail Modal** | • Video clip / keyframe carousel<br>• Plain-English summary & explainable **Who / Where / When / Behavior** badges<br>• **1-Click Teach Actions:** _"Enroll Face as Known Person"_ (`F-063`/`F-275`), _"Mark Reviewed"_, _"Snooze"_ (`F-050`), _"Delete"_ (`F-087`)                                                                                                                                                                                                                                                                                 | Adds the **"AI X-Ray" Tab** (`F-063`, `LLMReasoningExplorer.tsx`):<br>• Stage-by-stage GPU waterfall (`YOLO26 ms` $\rightarrow$ `Specialists ms` $\rightarrow$ `ai-vlm ms & tok/s`)<br>• Keyframes with grounded `[0–1000]` `bbox_2d` overlays (`ISS-065`)<br>• Specialist match vectors (ArcFace / OSNet / FastALPR)<br>• Exact rendered prompt (`events.llm_prompt`) & structured JSON verdict criteria (`event_verifications.criteria`)                                                                                                                                                                                                                                                                                        |

---

## 3. Five Signature Capabilities for RTX Gaming GPU Owners

### 3.1 Event "AI X-Ray" (`F-063`, `ISS-031`, `ISS-065`)

In `R2a` (row 31), `F-063` (`Event detail › AI Analysis tab / LLMReasoningExplorer`) was slated for
retirement because the legacy `llm_interactions` table stopped receiving writes when Nemotron was
deleted in R8 S2b.

- **Re-aimed design:** Keep `F-063` (visible in **Advanced Mode**) and back `GET /api/llm-reasoning/events/{event_id}`
  (or read directly from `GET /api/events/{event_id}`) using the live VLM columns that **already
  populate on every event**:
  - `events.llm_prompt` (exact prompt text sent to `ai-vlm`, including chronological frame labels
    and `0–1000` grounded bounding boxes),
  - `events.reasoning` and `events.summary`,
  - `event_verifications` (`verdict`, `scene_description`, `criteria` pass/fail array,
    `key_frame_detection_ids`, `engine`, `model_id`, `latency_ms`),
  - `detections` linked via `key_frame_detection_ids` (rendered as full key-frame stills with
    bounding-box overlays rather than 64px crops, closing `ISS-065`).
- This gives enthusiasts an instant X-ray into how `YOLO26` + `SCRFD/OSNet/FastALPR` + `Qwen3-VL-8B`
  collaborated on that specific event.

### 3.2 Interactive "Replay on My GPU" Lab (`F-109`–`F-113`, `F-120`–`F-124`)

`R2a` (row 27) already ruled the Prompt Playground and Prompt Management surfaces **complete (P3)**
with the cuatro retired-model tabs removed.

- **Blueprint enhancement:** Connect the Playground's **"Test / A/B Test"** action (`F-110`,
  `F-122`) to `backend/evaluation/vlm_replay.py` so a user can:
  1. Pick 1–5 real events from their timeline (e.g., a false alarm or a missed prowler),
  2. Edit the VLM rubric or system prompt in the browser,
  3. Click **"Run Replay on GPU"**,
  4. See a side-by-side diff of **Stored Verdict vs. Replayed Verdict** (verdict, observable tags,
     risk score, `latency_ms`, and reasoning diff) before clicking **"Promote to Active Prompt"**.

### 3.3 RTX Hardware Profile Picker & Visual VRAM Budget Bar (`F-127`, `F-105`, `F-130`, `F-176`, `F-178`)

Gamers know their GPU model and VRAM capacity intimately. On `/settings/ai-models` and
`/settings/gpu`:

- **Visual VRAM Budget Bar (`F-127`):** Displays real-time GPU memory allocation broken down by
  component:
  - `Triton (YOLO26 + Re-ID)`: `~0.6 GB`
  - `In-Process Specialists (SCRFD + ArcFace + FastALPR)`: `~0.4 GB`
  - `ai-vlm (Qwen3-VL-8B Q4_K_M + mmproj Q8_0 + 2x16K q8_0 KV)`: `~8.5 GB`
  - `Other / Desktop / Game Processes`: `X.X GB`
  - `Free Headroom`: `Y.Y GB`
- **RTX Tier Presets (`F-176`, `F-178`):** Auto-detects the installed NVIDIA card (`nvidia-smi` via
  `GPUMonitor`) and recommends the matching verified profile from `docs/vss-integration/history/20-model-tiers-benchmark-and-training.md`:
  - **12 GB Tier (RTX 3060 / 4070 / 4070 Super):** `PARALLEL=1`, `CTX_SIZE=16384`, `q8_0` KV (~8.2 GiB peak).
  - **16 GB Tier (RTX 4070 Ti Super / 4080 / 5070 Ti / 5080):** `PARALLEL=2`, `CTX_SIZE=32768`, `q8_0` KV (~9.5 GiB peak).
  - **24 GB+ Tier (RTX 3090 / 4090 / 5090 / A5500):** `PARALLEL=2–4`, high-res vision token cap, or optional larger VLM / Blackwell NVFP4 checkpoint.
  - _(Note: Retires the unsafe Podman-socket container recreation routes `F-177`, `F-179`–`F-183` per `D11`/`R2a row 36`, replacing them with safe runtime config / `.env` profile export)._

### 3.4 "Gaming Mode" — Dynamic VRAM Yield (`F-128`)

The #1 friction point for running AI 24/7 on a gaming PC is VRAM contention when launching a game.

- **Re-aim `F-128` (`Load / Unload model` on `/settings/ai-models` and a 1-click Header toggle in
  Advanced Mode) as "Gaming Mode (Yield VLM VRAM)":**
  - When **Gaming Mode** is activated (manually via 1-click toggle, or automatically when
    `GPUMonitor` detects non-HSI GPU utilization $> 60\%$ or free VRAM $< 3\text{ GB}$):
    - The backend pauses `AnalysisQueueWorker` (leaving closed batches safely persisted in Redis
      `analysis:stream`—zero dropped detections!).
    - `ai-vlm` releases its VRAM (or stops/sleeps the VLM slot), freeing **~8.5–9.5 GB of VRAM**
      for the user's game while lightweight `YOLO26` (`~400 MB`) continues detecting camera uploads
      in real time.
  - When **Gaming Mode** turns off (game exits or user clicks **Resume AI Verdict Engine**):
    - `ai-vlm` wakes (`VlmClient.wake()`) and drains the queued Redis batches in seconds.

### 3.5 Visual Entity Search & Daily Video Digest (The Core VSS Promise)

- **Cross-Camera Visual Search (`F-065`–`F-067`, `F-081`–`F-086`, `R2a row 19`):** Clicking any
  detected person or vehicle crop in an event opens **"Find Similar Appearances"**, querying
  OSNet-AIN / ArcFace embeddings across the 30-day retention window.
- **"Catch Me Up" AI Digest (`F-034`, `SummaryCards`):** Summarizes activity across cameras into
  a scannable narrative with direct deep-links (`/timeline?event=<id>`, `ruling 167`) to the
  underlying events.

---

## 4. Impact on Uplevel Phase 3 (`B3.1` / `F3.1`) Rulings

To align Phase 3 deletions with this product direction, the following rows in
`docs/reference/feature-inventory.md` are **rescued from `retire`** (everything else ruled `retire`
in `R2a`—such as `F-076` Cloud Cost Calculator, retired Florence/CLIP/X-CLIP/ViTPose panels,
`ScheduledReportsPage`, unmounted `JobActions`, and `BackgroundEvaluator`—still deletes as planned):

| Inventory Row(s)                                                                                   | Previous `R2a` Ruling    | Updated Ruling for Phase 3 / Phase 4                                                                                                                                                                                                                                                             | Priority |
| :------------------------------------------------------------------------------------------------- | :----------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------- |
| **`F-063`** (`Event detail › AI Analysis tab / LLMReasoningExplorer`)                              | `retire (R2a row 31)`    | **complete (Advanced Mode)** — re-wire `LLMReasoningExplorer` to render `events.llm_prompt`, `events.reasoning`, `event_verifications` (`verdict`, `criteria`, `latency_ms`, `model_id`), and full keyframe bbox overlays (`ISS-031`, `ISS-065`); drop empty `llm_interactions` table if unused. | `P2`     |
| **`F-127`, `F-105`, `F-130`** (`VRAM usage card, categorized model list, Model Zoo latency chart`) | `retire (R2a row 29)`    | **complete (Advanced Mode)** — render the RTX VRAM Budget Bar (`F-127`) and model latency history (`F-105`, `F-130`) fed by `event_verifications.latency_ms`, Triton `/metrics`, and `GPUMonitor`.                                                                                               | `P3`     |
| **`F-128`** (`AI Models settings › Load / Unload model buttons`)                                   | `retire (R2a row 29)`    | **complete (Advanced Mode)** — re-purpose as **"Gaming Mode / Yield VLM VRAM"** (pauses `AnalysisQueueWorker` onto Redis `analysis:stream` and sleeps/wakes `ai-vlm`).                                                                                                                           | `P3`     |
| **`F-176`, `F-178`** (`GPU settings › Detected GPUs, Strategy/Profile selector & preview`)         | `not ruled` (ruling 127) | **complete (Advanced Mode)** — RTX Hardware Profile Picker (12 GB / 16 GB / 24 GB+ presets with VRAM fit preview); `F-177`, `F-179`–`F-183` (Podman-socket container restarters) remain **`retire`**.                                                                                            | `P3`     |
