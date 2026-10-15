# Consumer NVIDIA VSS Blueprint: Easy Mode vs. Advanced Mode & RTX Gaming GPU Design Input

> **Date:** 2026-10-14 · **Home:** `docs/superpowers/2026-10-14-rtx-vss-blueprint/` (`UR-87` / `OD-33`) · **Authority:** Input to Phase 4 feature design sessions (`UR-77`, `UR-79`), not plan text (`#6854` comment `6174228588`, **Ruling 182**).

---

## 1. Product Positioning Decision in Force (Ruling 182)

Per **Owner Ruling 182** (`#6854` comment `6174228588`, 2026-10-14):

- **Positioning (Ruling 182's own words):** The product is a consumer NVIDIA VSS-style blueprint for
  desktop RTX gaming GPUs: visual search, identity and VLM reasoning, run locally, free, with full
  data control. The specific bracket — RTX 30/40/50-series, 12 GB to 32 GB VRAM — is owner spec input
  (`docs/superpowers/2026-10-14-rtx-vss-blueprint/owner-spec.md` §1), not the ruling's text (the
  ruling names no VRAM range or series list).
- **Two Modes (Phase 4 Header Switch):**
  - **Easy Mode ("Home Monitor" — the default):** For household members: **Dashboard**, **Timeline &
    Search**, **Alerts & Rules**, **Household**, and **Settings**.
  - **Advanced Mode ("NVIDIA AI Blueprint"):** For AI enthusiasts: the **AI Workbench**, **GPU &
    Model VRAM Telemetry**, the **Entity/Re-ID Explorer**, and **Operations/Monitoring**.
- **Inventory Rulings Settled by Ruling 182** (recorded by the frontend lane in `#7131`, merged
  2026-10-15, per `UR-149`):
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
- **Ruling 182 also rules on these seven kept rows** ("No deletion is in flight"): Phase 3's deletion
  packages must skip them, and `[r133]` / `[r134]` touch none of them.
- **Unchanged by Ruling 182:** `F-177`, `F-179`, `F-180`, `F-181` and `F-183` stay `retire`
  (`R2a row 36`); **`F-182` stays not ruled** (unverified, ruling 127). `F-076`, the retired R8
  panels, `ScheduledReportsPage`, `JobActions`, `BackgroundEvaluator`, the Calibration page and
  `DetectorSettings` also stay `retire`. (This doc's gloss on `F-182`, not the ruling's words: it is
  the `/settings/gpu` version-history / compare / export feature, not a container route.)

The sections below record the owner's design intent as **input to each feature's Phase 4 design
session (`UR-77`, `UR-79`)**.

---

## 2. Design Input for the Easy / Advanced Mode Switch

| Surface                | `Easy Mode` ("Home Monitor" — Default)                                                                                                                                                                                                                                                                                                                                                                                                             | `Advanced Mode` ("NVIDIA AI Blueprint")                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| :--------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Header Bar**         | • System protection status (`Protected` / `Armed` / `Degraded`)<br>• Unread alert badge<br>• `Easy \| Advanced` mode switch<br>**Design question:** the telemetry pill (`F-006`) currently `works` **in the default header** (empty ruling cell — the `F-006` row of `docs/reference/feature-inventory.md`); "Advanced-only" would _remove_ a working feature from the default mode, so whether it moves is a design-session decision, not a given | Adds:<br>• **Live RTX Telemetry Pill** (`F-006`): `GPU % · °C · FPS` — works today, ruling status open (see Easy column)<br>• **Gaming Mode (Yield VLM VRAM)** quick control (`F-128`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| **Left Sidebar**       | 1. **Dashboard** (`/`)<br>2. **Timeline & Search** (`/timeline`)<br>3. **Alerts & Rules** (`/alerts`, `/settings/rules`)<br>4. **Household** (`/household`, `/face-recognition`, `/plate-reads`, `/zones`)<br>5. **Settings** (`/settings`)                                                                                                                                                                                                        | Adds:<br>6. **AI Workbench** (`/ai-audit`, `/settings/prompts`)<br>7. **GPU & Model Zoo** (`/ai`, `/settings/ai-models`, `/settings/gpu`)<br>8. **Entity & Re-ID Explorer** (`/entities`, `/reid`, `/heatmaps`, `/scene-changes`)<br>9. **Operations** (`/operations`) + **Monitoring** — the consolidated page of rulings 128 and 135 (`packages/frontend.md`, "Monitoring", P3; it replaces 8 wrapper pages and **has no route yet**, so no `/monitoring` path exists on `main`). **`/scene-changes`** is camera-tamper detection, kept **complete, P2** (`R2a row 24`, ruling 183); ruling 182 does not place it in a mode, so its placement here is a **design-session question**, as `F-006`'s is |
| **Event Detail Modal** | • Video clip / keyframe carousel<br>• Plain-English summary & **Who / Where / When** badges<br>• Household actions (_"Enroll Face"_, _"Mark Reviewed"_, _"Snooze"_, _"Delete"_)                                                                                                                                                                                                                                                                    | Adds the **"AI X-Ray" Tab** (`F-063`):<br>• Keyframe bbox overlays — caveat: the grounded `[0–1000]` `bbox_2d` exists only in the rendered prompt (`vlm_client.py:744`); storage keeps pixel `bbox_x/y/width/height` (`detection.py:50-53`), so the tab parses the prompt or adds storage (`ISS-065`)<br>• Specialist match outputs (`faces`, `plates`, `person_reid`) — these ride `llm_prompt` (`vlm_client.py:628`), no columns of their own<br>• Rendered VLM prompt (`events.llm_prompt`), `events.reasoning`, and `event_verifications` (`verdict`, `criteria`, `latency_ms`, `model_id`)                                                                                                        |

---

## 3. Design Input for the Rescued Advanced Mode Features (Phase 4 Sessions)

### 3.1 `F-063` — Event "AI X-Ray" Tab (`P2`)

- **Current gap (`ISS-031`, `ISS-065`):** `LLMReasoningExplorer.tsx` queries
  `GET /api/llm-reasoning/events/{event_id}`, which reads the empty legacy `llm_interactions` table
  (404 on every VLM event).
- **The owner's intent, decided in Phase 4 (ruling 182):** F-063 reads the live VLM columns
  (`events.llm_prompt`, `events.reasoning`, `event_verifications`) instead of the empty
  `llm_interactions` table.
- **Owner spec input, not the ruling** (`owner-spec.md` §3.1, `Event "AI X-Ray"`): the per-column
  detail (`verdict`, `scene_description`, `criteria`, `key_frame_detection_ids`, `engine`,
  `model_id`, `latency_ms`), the spec's "populate on every event" framing, and full key-frame stills
  with bbox overlays instead of 64 px crops (the `ISS-065` ask).
- **Storage caveat:** the grounded `[0–1000]` `bbox_2d` exists only in the rendered prompt
  (`vlm_client.py:744`, `:800-805`); detections are stored as pixel `bbox_x`/`bbox_y`/`bbox_width`/
  `bbox_height` (`backend/models/detection.py:50-53`), and specialist outputs ride the assess
  snapshot into `llm_prompt` (`vlm_client.py:628`) with no columns of their own — so the tab either
  parses the stored prompt or gets new storage. A design-session decision.

### 3.2 `F-128` — "Gaming Mode": Yield `ai-vlm` VRAM (`P3`)

- **Problem for desktop RTX gaming GPU users:** When a user launches a PC game while `ai-vlm` holds
  its weights resident, the game contends for VRAM. The measured figure is **llama-server peaking at
  8822 MiB** on the RTX A5500, in a GPU-wide peak of 9606 MiB (ledger
  `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md`, "peak 9606 MiB (9.38 GiB)"; the same 8,822 MiB
  recurs in `docs/vss-integration/16-errata-2026-10-03.md`, `02-model-inventory.md`). That 9,606 MiB
  is the **corpus** S1 peak; the whole-GPU true-ceiling peak is
  **9,722–9,826 MiB (9.49–9.60 GiB)** (same ledger, "S1 at the true ceiling"). **9.60 GiB exceeds the
  spec's `~8.5–9.5 GB`** (owner spec input, `owner-spec.md` §3.4, `Gaming Mode — Dynamic VRAM Yield`;
  the spec writes GB, not GiB).
- **The owner's intent, decided in Phase 4 (ruling 182):** `F-128` pauses `AnalysisQueueWorker`
  (batches wait in `analysis:stream`) and frees `ai-vlm`'s VRAM, waking through `VlmClient.wake()`.
  The mode name **"Gaming Mode" is the ruling's own** — its table entry for `F-128` reads
  `complete, P3`, Advanced Mode ("Gaming Mode": yield the VLM's VRAM).
- **Owner spec input, not the ruling** (`owner-spec.md` §3.4, `Gaming Mode — Dynamic VRAM Yield`):
  presenting it as a **re-purpose** of the feature, "closed detection batches" (the ruling says
  batches), `Redis` as the store's name (the ruling names only `analysis:stream`), leaving `YOLO26`
  running during the pause, and the spec's claim that exiting the mode drains the queued batches.
- **Correction to the record — `ai-vlm` already sleeps and already wakes.** Ruling 182's own text
  says "`ai-vlm` has no sleep or unload path today"; that is wrong on both halves. `llama-server`
  idles to sleep on a timer — `SLEEP_IDLE_SECONDS`, defaulting to 300
  (`docker-compose.prod.yml:241`) — and the product already wakes it: the batch aggregator's
  wake-on-open calls `wake_ai_vlm()` (imported at `batch_aggregator.py:675`, task at `:677`), and
  that calls `VlmClient.wake()` (`vlm_client.py:1190`, the `def` at `:1145`). The ledger carries the
  live witness: _"after 300 s idle `is_sleeping=true` and llama-server fell 8822 -> 290 MiB … so the
  wake itself is ~1.5-2 s against the client's 90 s timeout"_
  (`docs/plans/2026-09-23-vss-gaming-gpu-ledger.md`, "fell 8822 -> 290 MiB"). The owner posted the
  correction to the record on `#6854` (`6175141693`, posted 18:13:21Z), reading it as _"what is new is an
  on-demand sleep trigger for Gaming Mode,"_ and stating that nothing else in the record changes and
  its lapse time is unchanged.
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
- **Owner spec input, not the ruling** (`owner-spec.md` §3.3, `RTX Hardware Profile Picker & Visual
VRAM Budget Bar`): presenting that selector as the spec's **12 GB / 16 GB / 24 GB+ tiers**. The
  names attached to them in this doc — "Compact", "Balanced", "High-Precision" — are **this doc's
  proposal**, not wording from the spec or any record. A design-session question: whether the tier
  framing replaces or wraps the five strategies, and how a tier maps to a strategy.
- Neither touches the retired container-recreation routes (`F-177`, `F-179`, `F-180`, `F-181` and
  `F-183`). `F-182` stays not ruled. R2a row 36 says apply is simulated
  (`apply_gpu_config()`, `backend/api/routes/gpu_config.py:926`, `:943`), so these are not
  Podman-socket restarters.
