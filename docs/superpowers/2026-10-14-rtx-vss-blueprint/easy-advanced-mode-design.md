# Consumer NVIDIA VSS Blueprint: Easy Mode vs. Advanced Mode & RTX Gaming GPU Design Input

> **Date:** 2026-10-14 · **Home:** `docs/superpowers/2026-10-14-rtx-vss-blueprint/` (`UR-87` / `OD-33`) · **Authority:** Input to Phase 4 feature design sessions (`UR-77`, `UR-79`), not plan text (`#6854` comment `6174228588`, **Ruling 182**).

---

## 1. Product Positioning Decision in Force (Ruling 182)

Per **Owner Ruling 182** (`#6854` comment `6174228588`, 2026-10-14):

- **Positioning (Ruling 182's own words):** The product is a consumer NVIDIA VSS-style blueprint for
  desktop RTX gaming GPUs: visual search, identity and VLM reasoning, run locally, free, with full
  data control. The specific bracket — RTX 30/40/50-series, 12 GB to 32 GB VRAM — is the owner's §2
  design-session spec input, not the ruling's text (the ruling names no VRAM range or series list).
- **Two Modes (Phase 4 Header Switch):**
  - **Easy Mode ("Home Monitor" — the default):** For household members: **Dashboard**, **Timeline &
    Search**, **Alerts & Rules**, **Household**, and **Settings**.
  - **Advanced Mode ("NVIDIA AI Blueprint"):** For AI enthusiasts: the **AI Workbench**, **GPU &
    Model VRAM Telemetry**, the **Entity/Re-ID Explorer**, and **Operations/Monitoring**.
- **Inventory Rulings Settled by Ruling 182** (recorded by the frontend lane in its next `R2b`
  record PR per `UR-149`):
  - **`F-063` (`Event detail › AI Analysis tab`):** `retire (R2a row 31)` $\rightarrow$
    **`complete, P2`, Advanced Mode ("Event AI X-Ray")**
  - **`F-105` (`/ai` Model Zoo latency chart):** `retire (R2a row 29)` $\rightarrow$
    **`complete, P3`, Advanced Mode**
  - **`F-127` (`/settings/ai-models` Model Management VRAM card):** `retire (R2a row 29)` $\rightarrow$
    **`complete, P3`, Advanced Mode**
  - **`F-128` (`/settings/ai-models` Load / Unload buttons):** `retire (R2a row 29)` $\rightarrow$
    **`complete, P3`, Advanced Mode ("Gaming Mode": yield the VLM's VRAM)**
  - **`F-130` (`/settings/ai-models` Model Zoo latency chart):** `retire (R2a row 29)` $\rightarrow$
    **`complete, P3`, Advanced Mode**
  - **`F-176` (`/settings/gpu` Detected GPUs) & `F-178` (`Strategy selector and preview`):**
    **`complete, P3`** if `O2.5`'s witness fails them; otherwise they verify as usual.
- **Unchanged by Ruling 182** (the ruling's own words): `F-177`, `F-179`, `F-180`, `F-181` and
  `F-183` stay `retire` (`R2a row 36`); **`F-182` stays not ruled** (unverified, ruling 127) — it is
  the `/settings/gpu` version-history / compare / export feature, not a container route. `F-076`, the
  retired R8 panels, `ScheduledReportsPage`, `JobActions`, `BackgroundEvaluator`, the Calibration
  page and `DetectorSettings` also stay `retire`. **Ruling 182 adds:** Phase 3's deletion packages
  must skip these rows, and `[r133]` / `[r134]` touch none of them.

The sections below record the owner's design intent as **input to each feature's Phase 4 design
session (`UR-77`, `UR-79`)**.

---

## 2. Design Input for the Easy / Advanced Mode Switch

| Surface                | `Easy Mode` ("Home Monitor" — Default)                                                                                                                                                                                                                                                                                                                                                                                              | `Advanced Mode` ("NVIDIA AI Blueprint")                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| :--------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Header Bar**         | • System protection status (`Protected` / `Armed` / `Degraded`)<br>• Unread alert badge<br>• `Easy \| Advanced` mode switch<br>**Design question:** the telemetry pill (`F-006`) currently `works` **in the default header** (empty ruling cell — `docs/reference/feature-inventory.md:127`); "Advanced-only" would _remove_ a working feature from the default mode, so whether it moves is a design-session decision, not a given | Adds:<br>• **Live RTX Telemetry Pill** (`F-006`): `GPU % · °C · FPS` — works today, ruling status open (see Easy column)<br>• **Gaming Mode (Yield VLM VRAM)** quick control (`F-128`)                                                                                                                                                                                                                                                                                                                                                                                                          |
| **Left Sidebar**       | 1. **Dashboard** (`/`)<br>2. **Timeline & Search** (`/timeline`)<br>3. **Alerts & Rules** (`/alerts`, `/settings/rules`)<br>4. **Household** (`/household`, `/face-recognition`, `/plate-reads`, `/zones`)<br>5. **Settings** (`/settings`)                                                                                                                                                                                         | Adds:<br>6. **AI Workbench** (`/ai-audit`, `/settings/prompts`)<br>7. **GPU & Model Zoo** (`/ai`, `/settings/ai-models`, `/settings/gpu`)<br>8. **Entity & Re-ID Explorer** (`/entities`, `/reid`, `/heatmaps`, `/scene-changes`)<br>9. **Operations** (`/operations`) + **Monitoring** — ruling 128's consolidated page (`packages/frontend.md:179`, P3; it replaces 8 wrapper pages and **has no route yet**, so no `/monitoring` path exists on `main`)                                                                                                                                      |
| **Event Detail Modal** | • Video clip / keyframe carousel<br>• Plain-English summary & **Who / Where / When** badges<br>• Household actions (_"Enroll Face"_, _"Mark Reviewed"_, _"Snooze"_, _"Delete"_)                                                                                                                                                                                                                                                     | Adds the **"AI X-Ray" Tab** (`F-063`):<br>• Keyframe bbox overlays — caveat: the grounded `[0–1000]` `bbox_2d` exists only in the rendered prompt (`vlm_client.py:744`); storage keeps pixel `bbox_x/y/width/height` (`detection.py:50-53`), so the tab parses the prompt or adds storage (`ISS-065`)<br>• Specialist match outputs (`faces`, `plates`, `person_reid`) — these ride `llm_prompt` (`vlm_client.py:628`), no columns of their own<br>• Rendered VLM prompt (`events.llm_prompt`), `events.reasoning`, and `event_verifications` (`verdict`, `criteria`, `latency_ms`, `model_id`) |

---

## 3. Design Input for the Rescued Advanced Mode Features (Phase 4 Sessions)

### 3.1 `F-063` — Event "AI X-Ray" Tab (`P2`)

- **Current gap (`ISS-031`, `ISS-065`):** `LLMReasoningExplorer.tsx` queries
  `GET /api/llm-reasoning/events/{event_id}`, which reads the empty legacy `llm_interactions` table
  (404 on every VLM event).
- **What Ruling 182 rules:** F-063 reads the live VLM columns (`events.llm_prompt`,
  `events.reasoning`, `event_verifications`) instead of the empty `llm_interactions` table.
- **Owner §2 spec input, not the ruling:** the per-column detail (`verdict`, `scene_description`,
  `criteria`, `key_frame_detection_ids`, `engine`, `model_id`, `latency_ms`), the "populates on
  every event" framing, and full key-frame stills with bbox overlays instead of 64 px crops (the
  `ISS-065` ask).
- **Storage caveat:** the grounded `[0–1000]` `bbox_2d` exists only in the rendered prompt
  (`vlm_client.py:744`, `:800-805`); detections are stored as pixel `bbox_x`/`bbox_y`/`bbox_width`/
  `bbox_height` (`backend/models/detection.py:50-53`), and specialist outputs ride the assess
  snapshot into `llm_prompt` (`vlm_client.py:628`) with no columns of their own — so the tab either
  parses the stored prompt or gets new storage. A design-session decision.

### 3.2 `F-128` — "Gaming Mode": Yield `ai-vlm` VRAM (`P3`)

- **Problem for desktop RTX gaming GPU users:** When a user launches a PC game while `ai-vlm` holds
  its weights resident, the game contends for VRAM. The measured figure is **llama-server peaking at
  8822 MiB** on the RTX A5500, in a GPU-wide peak of 9606 MiB (ledger
  `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md:381`; the same 8,822 MiB recurs at
  `docs/vss-integration/16-errata-2026-10-03.md:745`) — the "~8.5–9.5 GiB" range is the owner's §2
  spec input.
- **What Ruling 182 rules:** re-purpose `F-128` so **Gaming Mode** pauses `AnalysisQueueWorker`
  (closed detection batches wait in Redis `analysis:stream`) and frees `ai-vlm`'s VRAM, waking
  through `VlmClient.wake()`.
- **Owner §2 spec input, not the ruling:** the mode name "Gaming Mode", leaving `YOLO26` running
  during the pause, and "drains the queued batches" on exit.
- **Correction to the record — `ai-vlm` already sleeps and already wakes.** Ruling 182's own text
  says "`ai-vlm` has no sleep or unload path today"; that is wrong on both halves. `llama-server`
  idles to sleep on a timer — `SLEEP_IDLE_SECONDS`, defaulting to 300
  (`docker-compose.prod.yml:241`) — and the product already wakes it: `VlmClient.wake()`
  (`vlm_client.py:1145`) and `wake_ai_vlm()` (`:1180`) are called from the batch aggregator's §6
  wake-on-open (`batch_aggregator.py:671-676`). The ledger carries the live witness: _"after 300 s
  idle `is_sleeping=true` and llama-server fell 8822 → 290 MiB … the wake itself is ~1.5-2 s against
  the client's 90 s timeout"_ (`…/2026-09-23-vss-gaming-gpu-ledger.md:382`). A correction to the
  ruling is owed on `#6854`.
- **What is actually new:** an **on-demand** yield. Nothing in `backend/` or `ai/vlm/` can ask the
  engine to sleep today — only its idle timer can — so Gaming Mode needs either an explicit sleep
  call or a slot unload, plus the pause/resume of the analysis worker.

### 3.3 `F-127`, `F-105`, `F-130` — RTX VRAM Budget Card & Model Latency Charts (`P3`)

- **`F-127` (`/settings/ai-models` Model Management VRAM card):** Show real-time VRAM usage and
  per-component allocation across `ai-gateway` (`yolo26`, `reid`), specialists, and `ai-vlm`.
- **`F-105` (`/ai`) & `F-130` (`/settings/ai-models`) Model Latency Charts:** Feed latency history
  from live VLM verification latencies (`event_verifications.latency_ms`) and gateway metrics.

### 3.4 `F-176`, `F-178` — GPU Settings (`/settings/gpu`, `P3` if `O2.5` fails them)

- `F-176` displays detected NVIDIA GPU hardware. **`F-178` is a multi-GPU assignment-strategy
  selector**, not a VRAM-tier profile picker: `GpuAssignmentStrategy` offers `MANUAL`,
  `VRAM_BASED`, `LATENCY_OPTIMIZED`, `ISOLATION_FIRST` and `BALANCED`
  (`backend/api/schemas/gpu_config.py:15-30`), which distribute models across GPUs.
- **Owner §2 spec input, not the ruling:** presenting that selector as named hardware tiers
  ("12 GB Compact / 16 GB Balanced / 24 GB+ High-Precision"). A design-session question: whether the
  tier framing replaces or wraps the five strategies, and how a tier maps to a strategy.
- Neither touches the retired Podman-socket container recreation routes (`F-177`, `F-179`–`F-183`).
