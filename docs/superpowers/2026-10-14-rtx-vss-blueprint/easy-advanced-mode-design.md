# Consumer NVIDIA VSS Blueprint: Easy Mode vs. Advanced Mode & RTX Gaming GPU Design Input

> **Date:** 2026-10-14 · **Home:** `docs/superpowers/2026-10-14-rtx-vss-blueprint/` (`UR-87` / `OD-33`) · **Authority:** Input to Phase 4 feature design sessions (`UR-77`, `UR-79`), not plan text (`#6854` comment `6174228588`, **Ruling 182**).

---

## 1. Product Positioning Decision in Force (Ruling 182)

Per **Owner Ruling 182** (`#6854` comment `6174228588`, 2026-10-14):

- **Positioning:** The product is a consumer NVIDIA VSS-style blueprint for desktop RTX gaming GPUs
  (RTX 30-series, 40-series, 50-series; 12 GB to 32 GB VRAM): visual search, identity recognition,
  and VLM reasoning, run locally, free, with full data control.
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
    **`complete, P3`** if `O2.5`'s witness fails them; otherwise they verify as usual (`F-177`,
    `F-179`–`F-183` remain `retire` per `R2a row 36`; `F-182` remains not ruled).

The sections below record the owner's design intent as **input to each feature's Phase 4 design
session (`UR-77`, `UR-79`)**.

---

## 2. Design Input for the Easy / Advanced Mode Switch

| Surface                | `Easy Mode` ("Home Monitor" — Default)                                                                                                                                                                                                      | `Advanced Mode` ("NVIDIA AI Blueprint")                                                                                                                                                                                                                                                                                        |
| :--------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Header Bar**         | • System protection status (`Protected` / `Armed` / `Degraded`)<br>• Unread alert badge<br>• `Easy \| Advanced` mode switch                                                                                                                 | Adds:<br>• **Live RTX Telemetry Pill** (`F-006`): `GPU % · °C · FPS`<br>• **Gaming Mode (Yield VLM VRAM)** quick control (`F-128`)                                                                                                                                                                                             |
| **Left Sidebar**       | 1. **Dashboard** (`/`)<br>2. **Timeline & Search** (`/timeline`)<br>3. **Alerts & Rules** (`/alerts`, `/settings/rules`)<br>4. **Household** (`/household`, `/face-recognition`, `/plate-reads`, `/zones`)<br>5. **Settings** (`/settings`) | Adds:<br>6. **AI Workbench** (`/ai-audit`, `/settings/prompts`)<br>7. **GPU & Model Zoo** (`/ai`, `/settings/ai-models`, `/settings/gpu`)<br>8. **Entity & Re-ID Explorer** (`/entities`, `/reid`, `/heatmaps`, `/scene-changes`)<br>9. **Operations & Monitoring** (`/operations`, `/monitoring`)                             |
| **Event Detail Modal** | • Video clip / keyframe carousel<br>• Plain-English summary & **Who / Where / When** badges<br>• Household actions (_"Enroll Face"_, _"Mark Reviewed"_, _"Snooze"_, _"Delete"_)                                                             | Adds the **"AI X-Ray" Tab** (`F-063`):<br>• Keyframes with grounded `[0–1000]` `bbox_2d` overlays (`ISS-065`)<br>• Specialist match outputs (`faces`, `plates`, `person_reid`)<br>• Rendered VLM prompt (`events.llm_prompt`), `events.reasoning`, and `event_verifications` (`verdict`, `criteria`, `latency_ms`, `model_id`) |

---

## 3. Design Input for the Rescued Advanced Mode Features (Phase 4 Sessions)

### 3.1 `F-063` — Event "AI X-Ray" Tab (`P2`)

- **Current gap (`ISS-031`, `ISS-065`):** `LLMReasoningExplorer.tsx` queries
  `GET /api/llm-reasoning/events/{event_id}`, which reads the empty legacy `llm_interactions` table
  (404 on every VLM event).
- **Phase 4 design intent (Ruling 182):** Read the live VLM columns that already populate on every
  event (`events.llm_prompt`, `events.reasoning`, and `event_verifications` — `verdict`,
  `scene_description`, `criteria`, `key_frame_detection_ids`, `engine`, `model_id`, `latency_ms`),
  and display the full key-frame stills with bounding-box overlays rather than 64px crops
  (`ISS-065`).

### 3.2 `F-128` — "Gaming Mode": Yield `ai-vlm` VRAM (`P3`)

- **Problem for desktop RTX gaming GPU users:** When a user launches a PC game while `ai-vlm` holds
  ~8.5–9.5 GiB of VRAM resident, the game contends for VRAM.
- **Phase 4 design intent (Ruling 182):**
  - Re-purpose `F-128` (`Load / Unload` on `/settings/ai-models`) so activating **Gaming Mode**
    pauses `AnalysisQueueWorker` (leaving closed detection batches safely queued in Redis
    `analysis:stream` while lightweight `YOLO26` keeps running) and frees `ai-vlm`'s VRAM.
  - Exiting Gaming Mode wakes `ai-vlm` (`VlmClient.wake()`) and drains the queued `analysis:stream`
    batches.
  - Because `ai-vlm` (`llama-server`) has no sleep/unload path today, the container/slot unload-and-wake
    mechanism is new Phase 4 design work.

### 3.3 `F-127`, `F-105`, `F-130` — RTX VRAM Budget Card & Model Latency Charts (`P3`)

- **`F-127` (`/settings/ai-models` Model Management VRAM card):** Show real-time VRAM usage and
  per-component allocation across `ai-gateway` (`yolo26`, `reid`), specialists, and `ai-vlm`.
- **`F-105` (`/ai`) & `F-130` (`/settings/ai-models`) Model Latency Charts:** Feed latency history
  from live VLM verification latencies (`event_verifications.latency_ms`) and gateway metrics.

### 3.4 `F-176`, `F-178` — RTX Hardware Profile Picker (`/settings/gpu`, `P3` if `O2.5` fails them)

- Display detected NVIDIA GPU hardware (`F-176`) and let the user preview/select hardware profiles
  (12 GB Compact, 16 GB Balanced, 24 GB+ High-Precision) without invoking the retired Podman-socket
  container recreation routes (`F-177`, `F-179`–`F-183`).
