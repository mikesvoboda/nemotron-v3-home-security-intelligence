# VSS Gaming-GPU Profile — Design

**Status:** approved design (§1-§8 approved section by section by the owner, 2026-09-23), ready for implementation planning
**Date:** 2026-09-23
**Branch:** `feat/vss-gaming-gpu-profile`
**Revision:** rev 5 (2026-09-25, owner ruling, ledger F10): **the legacy path is no longer
supported.** No production system is running (F9), so nothing needs to be kept alive or rolled back
to. There is no control: S2 and S3 become fixed bars. The Nano-4B placeholder, the control freeze,
the legacy A5500 bring-up and the offline 30B replay are removed. Phase 3 "Cutover" becomes
"Go-live", and its fallback is the detector-only rule (§6), not a legacy rollback. The 0.3 code
already written is kept. The legacy code stays in the repo, unsupported, until R8 deletes it
(D2, D5, D7, D8, S2, S3, §2, §5, §8). Rev 4 (2026-09-23): the GB300's Cosmos container is stopped,
leaving ~47.9 GiB for our models (D12, Phase G0, checklist). Rev 3 (2026-09-23): three test environments (D2, D10, D12, §8), an engine-agnostic
OpenAI-compatible VLM provider (§3), and a Brev hardware matrix (step 2.3). Rev 2 (2026-09-23). Amended after a Codex adversarial review, owner-approved:
null-safe failure delivery (D11, §4, §6, step 0.25) and self-contained eval items replacing the
event-FK replay (D7, §4, §5, §7).
**Companion documents:** [`docs/vss-integration/`](../../vss-integration/AGENTS.md) holds the research
this design rests on. The key files:

- [`08`](../../vss-integration/08-audit-profile-anatomy.md), [`09`](../../vss-integration/09-audit-integration-surfaces.md), [`10`](../../vss-integration/10-audit-feature-inventory.md): the audits of VSS `1e94133b4`
- [`11`](../../vss-integration/11-errata-2026-09-23.md): errata to docs 00-07, cited here as **E#**
- [`12`](../../vss-integration/12-postponed-roadmap.md): what this design deliberately postpones, cited as **R#**

## Problem

**Home security is a false-positive-suppression problem.** Today every per-event judgment passes
through text: the detector finds objects, enrichment models and Florence-2 turn crops into words,
and an LLM scores the words. The LLM never sees pixels. So it scores "person, 0.62, 02:14, front
porch" without seeing that the person is a shadow.

It is worse than that. The "structured" risk output is probably unenforced, and unparseable output
fails open to **score 50 → `medium`**, which is the empty-porch failure (E5).

VSS, NVIDIA's Video Search and Summarization blueprint, attacks false positives with a different
shape: a **detector triggers a candidate, and a vision-language model returns a constrained
confirm/reject verdict** ([`09`](../../vss-integration/09-audit-integration-surfaces.md) §5). VSS
does not run on consumer GPUs. Its smallest validated configuration is 2×32 GB (E2), and consumer
GPUs are not on its roadmap (the VSS PM, 2026-09-19).

This design brings the verification shape to **one 24 GB card**. The owner's RTX A5500 (Ampere,
sm_86) stands in for the consumer tier, and the result is packaged so it can later become a VSS
consumer tier.

## Decisions (locked by owner, 2026-09-23)

| #   | Decision                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | **Downstream-first.** The work lands in this repo, behind the `backend/ai_contract` seam, shaped so it can go upstream later (R9).                                                                                                                                                                                                                                                                                                                                            |
| D2  | **Three test environments** (§8). **The GB300** (this repo's development box) is the development loop and runs the salience bake-off. **The amd64 RTX A5500** (24 GB, sm_86, **single GPU**; the A400 is retired) runs the real-data steps and the production go-live. **Brev VMs** supply the per-tier hardware matrix. An agent runs wherever a step's environment is. Ampere has no FP8 or FP4 tensor cores, so the A5500 proves fit and salience, not native NVFP4 speed. |
| D3  | **Per-event architecture: detector + one VLM.** The detector gates every upload and supplies geometry. One VLM describes, verifies and scores candidates from the evidence stills in **one constrained call**. Florence-2 and most enrichment retire. The face, re-ID and plate specialists stay, loaded on demand.                                                                                                                                                           |
| D4  | **Engine: contract-first.** llama.cpp (GGUF + mmproj) ships first. RT-VLM, VSS's engine, follows behind the same contract in a **gated** phase; its A5500 fit, or its failure, is recorded as upstream evidence. The VSS Delta build is produced in that phase.                                                                                                                                                                                                               |
| D5  | **Model slots are pluggable.** The owner picks the VLM after the bake-off (M2). The reasoning LLM is deferred to the owner (R10). **Rev 5:** there is no placeholder LLM, because the legacy path is not deployed.                                                                                                                                                                                                                                                            |
| D6  | **Ingest is FTP stills only.** Live streaming is R1.                                                                                                                                                                                                                                                                                                                                                                                                                          |
| D7  | **Evaluation is replay, not live shadow,** over **self-contained eval items** that production retention cannot touch. **Rev 5: there is no control.** S2 and S3 are fixed bars on labeled items; nothing is compared against the legacy path.                                                                                                                                                                                                                                 |
| D8  | **Success criteria S1-S6** (below) gate the go-live.                                                                                                                                                                                                                                                                                                                                                                                                                          |
| D9  | **Out of scope:** everything in [`12`](../../vss-integration/12-postponed-roadmap.md).                                                                                                                                                                                                                                                                                                                                                                                        |
| D10 | **Real-camera data stays out of git.** It may live on the owner's machines (A5500, GB300) and on Brev VMs used for evaluation. Transfer it over SSH, and wipe the eval store from a Brev VM at teardown. Only synthetic items and aggregate metrics enter git.                                                                                                                                                                                                                |
| D11 | **Failure delivery is null-safe end to end.** A `verification_failed` event has a NULL score and level, and it still reaches the dashboard and the detector-only notification. It does **not** require acknowledgment; acknowledgment stays reserved for scored risk ≥ 80.                                                                                                                                                                                                    |
| D12 | **Development runs on the GB300 with our own engines.** The owner stopped the co-resident Cosmos vLLM container on 2026-09-23. Beside the flagship vLLM engine (~202 GiB), which **must stay resident**, that leaves **~47.9 GiB** for our models: every VLM candidate, the Triton detector and specialists, and RT-VLM for functional tests. Our llama.cpp `ai-vlm` is the development VLM. Cosmos-Reason2-8B stays a bake-off candidate, served on demand by our own vLLM.  |

## Success criteria

Measured on the A5500.

| #   | Criterion       | Bar                                                                                                                                                                                                                    |
| --- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S1  | Fit             | Peak VRAM ≤ **20.4 GiB** (0.85 × 24 GB) with the detector, on-demand specialists and the VLM resident; no CPU offload of the VLM. Measured on 24 GB-class hardware (the A5500, or a Brev A10G or L4), not on the GB300 |
| S2  | False positives | On labeled-benign items, the rate at `risk_level ≥ medium` is **≤ `S2_MAX` %**. Rev 5: a fixed bar. The owner sets `S2_MAX` before the bake-off report (step 2.2) [?]                                                  |
| S3  | Recall          | On labeled incidents, the share at or above their expected minimum level is **≥ `S3_MIN` %**. Rev 5: a fixed bar. The owner sets `S3_MIN` before step 2.2 [?]                                                          |
| S4  | Latency         | p95 per-batch verdict ≤ **30 s**, including cold starts, measured on 24 GB-class hardware                                                                                                                              |
| S5  | Robustness      | **0** unparseable verdicts. Every failure surfaces as `verification_failed`, never as a default score, and reaches the dashboard and the notification path.                                                            |
| S6  | Contract        | The conformance suite is green including `vlm_assess`, and the FakeProvider covers it                                                                                                                                  |

## §2 Architecture

A backend setting, `PIPELINE_MODE=legacy|vlm`, selects the per-event path. **Rev 5:** `vlm` is the
default and the only supported mode. `legacy` stays selectable only because its code stays in the
repo until R8 deletes it. It is not deployed, not measured, and not a rollback target.

```
FTP still/clip → file_watcher → YOLO26 gate (Triton) ── nothing detected → no event (unchanged)
                                      │ detections
                           batch_aggregator (90 s / 30 s idle, unchanged)
                                      │ batch closes
          ┌───────────────────────────┴──────────────────────────────┐
  legacy: enrichment + Florence → text → LLM            vlm: key_frame_selector (≤4 stills)
          (unsupported since rev 5; code kept until R8)      → face / re-ID / plate specialists, on demand
                                                             → vlm_assess(images + text context,
                                                                          json_schema-constrained)
          └───────────────────────────┬──────────────────────────────┘
                              Event (+ verification) → WebSocket / UI
```

**Units.** Each has one job.

| Unit                                     | Job                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ai-vlm` compose service (profile `vlm`) | `llama-server` + GGUF + `--mmproj`; `/v1/chat/completions` with `json_schema`; `--jinja --sleep-idle-seconds --alias`; 2 slots; context sized for 4 images + ~6K text + output. Reachable on the internal compose network. Its host port is a new `AI_VLM_PORT` variable (default `8098`, unused today), added to `.env.example` first per the root port rule.                                                                                                                                                                          |
| `backend/services/key_frame_selector.py` | Picks 1-4 stills per batch: the best detection per camera/class plus the most recent. A pure function. **Ingest-agnostic:** it takes image references from any source, which is the seam for R1.                                                                                                                                                                                                                                                                                                                                        |
| `backend/services/vlm_client.py`         | The contract-registered client for `vlm_assess`, including the enforcement probe (§3)                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `backend/services/vlm_analyzer.py`       | Builds an **`AssessInput` snapshot** (key-frame candidates, detections, camera, zones, household: today's prompt context minus Florence) and assembles the prompt from it as a **pure function**. Production builds the snapshot from the database; replay loads it from the eval store; both share one code path. Calls `vlm_assess`, applies the invariants (§6), and maps the verdict to an Event. A **sibling** of `nemotron_analyzer.py`, not an edit to it. The legacy analyzer stays in the repo, unsupported, until R8 (rev 5). |
| Triton gateway                           | Moves from `--model-control-mode=none` (`ai/gateway/entrypoint.sh:131`) to **explicit**, with the `vlm` load set: YOLO26 plus on-demand specialists only (rev 5: no legacy load set). This is the residency control E4 found missing.                                                                                                                                                                                                                                                                                                   |

**VRAM** [C/A; S1 measures it]:

| Mode  | Resident                                                                                                                            | ≈ GiB  |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------- | ------ |
| `vlm` | YOLO26 + Triton overhead (~1) + on-demand specialists (~1-2) + `ai-vlm` (e.g. 12B-VL Q4 7.5 + mmproj 1.7 + KV and image buffers ~2) | ~13-14 |

Evaluation is replay (D7) because eval items must outlive production retention and re-run on every
model or prompt change. (Rev 5 removed the `legacy` row: that mode is not deployed.)

## §3 Contract and engines

**One capability op: `vlm_assess`.** It is declared in `scripts/gen-ai-contract.py` as a new
`VLM_OPS` entry, following the precedent `LLM_OPS` sets for llama.cpp, an external surface.

| Side     | Shape                                                                                                                                                                                                                                                                                |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Request  | 1-4 image references (paths under the FTP root; each provider chooses a data URI or `file://`) + a structured text context: camera, zones, time, household, detections, specialist outputs                                                                                           |
| Response | **`VlmVerdict`**, a Pydantic model and the single source of truth. Fields: `verdict ∈ {confirmed, rejected, uncertain}`, `risk_score` (int 0-100), `summary`, `reasoning`, `description` (whole scene), `criteria[] = {name, passed, evidence}`, plus provenance (engine, model id). |
| Derived  | `risk_level` comes from `risk_score` through the existing `SeverityService`. The model never emits a level.                                                                                                                                                                          |

**Generated, never hand-written:** the constrained-decoding JSON schema, the golden payload and the
shape snapshot all derive from `VlmVerdict`. This is the repo's drift doctrine applied to the new
seam. The `nvext` defect (E5) is what happens when the constraint the client sends and the shape the
parser expects are maintained separately.

**Slots:**

- Add `ProviderId.OPENAI_VLM` and `ProviderId.RTVI_VLM` (`backend/ai_contract/provider.py:22-35`).
  Each registers with `required={"vlm_assess"}`, the subset pattern `llamacpp-serve` uses.
- **`OPENAI_VLM` is engine-agnostic.** It speaks standard OpenAI chat completions with
  `response_format: json_schema`, which llama.cpp (production) and vLLM (for example an on-demand
  Cosmos-Reason2-8B) both accept, and its provenance records the actual engine. RT-VLM gets its
  own slot because its adapter differs (Engine 2).
- The FakeProvider returns a deterministic verdict keyed on an image hash.
- The parity checker gets a `DECLARED` entry, as the `llm_*` ops have.

**Engine 1: llama.cpp (ships first).**

- **Wire:** `POST /v1/chat/completions` with up to 4 base64 `image_url` parts and a `json_schema`
  response format.
- **Enforcement probe:** it proves enforcement by requesting a schema with a required constant field
  and checking the output. **A 2xx alone proves nothing.** It runs once per endpoint.
- **The same client reaches any OpenAI-compatible vLLM server,** such as an on-demand
  Cosmos-Reason2-8B (D12).
- **llama.cpp pin:** `b7972` (`ai/nemotron/Dockerfile`) runs Qwen3-VL. Nemotron-12B-VL needs a newer
  pin with its multimodal support, merged 2026-02-14 or later, so the bake-off includes that bump.

**Engine 2: RT-VLM (gated Phase 4; not required for go-live).**

- **Image and mode:** the anonymous ghcr image (amd64), in integrated `vllm-compatible` mode, with an
  empty message bus.
- **Wire:** `POST /v1/chat/completions` with a `json_schema` response format, enforced fail-closed by
  xgrammar. This works in **integrated mode only**; openai-compat mode drops it silently.
- **Adapter differences:**
  - It uses only the **first image** per request, so the adapter tiles the key frames into one
    composite.
  - `model` must equal the advertised id.
  - Set `RTVI_ADD_TIMESTAMP_TO_VLM_PROMPT=false`, or stills get a "sampled from a video" preamble.
  - Send `enable_reasoning:false`.
  - Use `file://` with `FILE_URL_ALLOWED_DIRS=${FOSCAM_BASE_PATH}` (read-only mount), so no bytes are copied.
- **Memory:** a compose patch exposes `RTVI_VLLM_KV_CACHE_MEMORY_BYTES`; utilization ~0.45-0.55.
- **It cannot serve tool calls** (`extra="forbid"`), so llama.cpp stays the agent-capable engine (R3).
- **Sources:** [`09`](../../vss-integration/09-audit-integration-surfaces.md) §1 and [`08`](../../vss-integration/08-audit-profile-anatomy.md) §2.5-2.6.

## §4 Data model and frontend

**A new table, `event_verifications`.** It needs no change to `events`, because the schema is
flattened into `create_all` (Alembic was removed in #4465; `backend/core/database.py:407`), and
`create_all` creates new tables on an existing database but never alters existing ones. Columns:

- `event_id` (FK)
- `verdict ∈ {confirmed, rejected, uncertain, verification_failed}`
- `scene_description`, `criteria` (JSONB), `key_frame_detection_ids` (JSONB)
- `engine`, `model_id`, `latency_ms`, `created_at`

**Production only.** Replay results live in the eval store (§5), not here. Retention hard-deletes old
events and, one step earlier, their detections (`backend/services/cleanup_service.py:294`), so
nothing the evaluation needs may depend on production rows.

**Mapping a verdict to an Event** (vlm mode). Existing columns keep their meaning:

| Target                                    | Source                                                                                                                                                                                                                                      |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `events.risk_score`                       | `verdict.risk_score`, after the §6 invariants                                                                                                                                                                                               |
| `events.risk_level`                       | `SeverityService(risk_score)`                                                                                                                                                                                                               |
| `events.summary`, `events.reasoning`      | The verdict's fields. They are already in the full-text search trigger.                                                                                                                                                                     |
| `events.llm_prompt`, `llm_interactions.*` | The text prompt (images **referenced by path**), the raw response and the validation result                                                                                                                                                 |
| `event_verifications`                     | One row per vlm-mode event                                                                                                                                                                                                                  |
| Notifications                             | The per-camera `risk_threshold` on `risk_score` (`backend/services/notification_filter.py:66`), plus the §6 rules. `verification_failed` branches to the detector-only rule **before** that comparison, which raises on a NULL score today. |

**API and UI:**

- The Event API response and the WebSocket event payload gain a `verification` object, present on
  every vlm-mode event so consumers branch on the verdict.
- **`WebSocketEventData.risk_score` and `risk_level` become optional.** Today
  `backend/api/schemas/websocket.py:252-253` require them, so a `verification_failed` event would be
  rejected before broadcast. The REST schema already allows a NULL score. The frontend's generated
  API types regenerate.
- An **"unverified" badge** renders wherever a score would, for NULL-score events.
- **Event detail** shows a verdict badge, the scene description, a criteria checklist, and "frames
  the VLM reviewed" (existing thumbnails, from `key_frame_detection_ids`).
- **Event list** gains a verdict filter. **Rejected events stay listed but de-emphasized**, so what
  was suppressed stays auditable.
- **Retired-enrichment panels** (pose skeleton, clothing, demographics) show a "not analyzed in VLM
  mode" empty state.
- Face, plate and re-ID views are unchanged. Legacy events have no verification row.

**Deferred:** deleting retired tables and panels (R8), and adding `scene_description` to the search
trigger (R4).

## §5 Evaluation and go-live

**Eval items.** Every evaluation input is a self-contained **eval item** with its own id, stored in
the eval store. Nothing in it depends on production rows, which retention deletes. An item holds:

- the key-frame candidate images, **copied** into the eval store;
- the `AssessInput` snapshot (§2): detections, camera, zones, household context;
- the label: benign, or incident with an expected minimum severity;
- `source_event_id`, for provenance only (no foreign key).

Rev 5 removed the control verdict: S2 and S3 are fixed bars, so an item needs only its label.

| Item kind                 | Source                                                                                                      | Label                                                                                                                                          |
| ------------------------- | ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Synthetic scenarios       | `scripts/synthetic` (17 scenarios: normal, suspicious, threats, environmental)                              | The scenario spec                                                                                                                              |
| Owner-generated media     | Synthetic video from the owner (F9 ruling 2); frames are sampled into stills, because ingest is stills (D6) | Born labeled: the generator knows each clip's label                                                                                            |
| Stock imagery             | License-clean frames (`scripts/synthetic_media.py`)                                                         | The scenario it was fetched for                                                                                                                |
| Real events, post-go-live | Events labeled after go-live (Phase 3)                                                                      | The owner's feedback (`EventFeedback`): `false_positive` → benign; `missed_threat`, or `accurate` on high → incident, with `expected_severity` |

**Size:** at least **100 benign and 20 incidents**. At 50 benign, one frame moves the rate by 2
points, which is too coarse for S2.

**Eval store** (on the box, outside the repo, per D10): the copied images plus one SQLite file with
`eval_items`, `eval_runs` and `eval_results`.

- It is independent of production retention.
- It is **portable**: copying the directory lets the same set validate other hardware later (R11).
- **Labeling window.** Synthetic and stock items are labeled when they are made. After go-live,
  labels also come from `EventFeedback` on live events, so the owner must label an event before
  retention deletes it, within 30 days. Step 0.5's import turns those labels into eval items by
  `source_event_id`. Unlabeled items are excluded from S2 and S3.
- The cleanup service keeps original images by default (`delete_images=False`,
  `backend/services/cleanup_service.py:124`), but freezing copies them anyway.
- Real-camera images, labels and snapshots stay in the eval store (D10).

**Replay harness** (`backend/evaluation/vlm_replay.py`). It sits next to the text-prompt harness in
`backend/evaluation/` and reuses its report plumbing. The existing 100-event
`data/benchmark/evaluation-set` is text-only and does not apply. For each item it:

1. loads the item's `AssessInput` snapshot and runs `key_frame_selector` → `vlm_assess` against a
   live `ai-vlm`, reading nothing from the production database;
2. writes `eval_results(item_id, run_id, …)` to the eval store;
3. computes S1-S5 against the labels and the fixed bars;
4. reports **per-item disagreements**, which are the tuning signal.

**Metric definitions:**

- **S2:** benign items at `risk_level ≥ medium`, divided by all benign items.
- **S3:** incidents at or above their expected minimum level, divided by all incidents.
- `uncertain` items count at their scored level. A model that answers `uncertain` with a low score
  on everything passes S2 and fails S3; the G0 salience smoke test (S-3) saw exactly that pattern,
  so report the verdict mix beside the bars.

**Bake-off.** Run the same replay per candidate: Qwen3-VL-4B, Qwen3-VL-8B, Nemotron-12B-VL (after
the llama.cpp bump), and Cosmos-Reason2-8B. Cosmos-Reason2-8B runs on demand in our own vLLM (BF16), as a quality reference only; a consumer tier would need a quantized build. Cosmos3-Edge-4B
follows in Phase 4 through RT-VLM.

Salience depends on the model build (weights, quantization, engine), not on the GPU. So run each
candidate in the build it would ship in; any environment then gives the same S2/S3. Fit and latency
come from the hardware matrix (step 2.3). Report per candidate:

- S1-S5 and the `uncertain` rate;
- the **tool-calling probe** through llama.cpp, which keeps R3 open;
- long-context KV cost;
- license and gating.

**The owner picks.**

**Go-live** (rev 5; there is no legacy system to cut over from):

1. **Gate:** the owner's pick passes S1-S6 on replay, and the owner signs off.
2. **Deploy:** run with `PIPELINE_MODE=vlm` and the compose profile `vlm` on the A5500. `ai-llm`,
   Florence and the heavy enrichment are not deployed.
3. **Observe for 14 days**, with the owner giving feedback in the normal UI. **Stop triggers:**
   - any `missed_threat` feedback on an event the VLM rejected or scored below its expected level;
   - a false-positive feedback rate clearly above the replay estimate.
4. **On a trigger,** roll back to the last model or prompt build that passed the gate, if one
   exists. Otherwise take `ai-vlm` offline: every batch then takes §6 step 3, so the detector-only
   rule keeps notifying and the owner is never blind. The triggering events become eval items, and
   the gate re-runs before the next deploy.
5. **Regression:** the labeled replay re-runs on every model or prompt change, months later if need
   be, because eval items outlive production retention.

## §6 Error handling and safety

**Verdict semantics.** `verdict` answers _is the detected candidate real and correctly identified?_
`risk_score` answers _how threatening is it?_ They are independent: the mail carrier is `confirmed`
and low risk. Only `rejected` constrains the score.

**Server-side invariants.** The model is never trusted.

| Rule                                                                                         | Enforcement                                                                                                                      |
| -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `rejected` ⇒ score ≤ `SeverityService` `low_max` (from settings)                             | Clamp and log                                                                                                                    |
| `rejected` ⇒ never notifies, even where a camera's `risk_threshold` sits inside the low band | `notification_filter` skips `verdict=rejected` explicitly                                                                        |
| 1-4 key frames; non-empty description; ≥1 criterion with evidence                            | Constrained decoding plus post-validation                                                                                        |
| The VLM never originates an event or a structured entity                                     | It runs only on batches the detector closed. Faces, plates and re-ID come only from specialists; VLM text writes no entity rows. |

**Failure ladder, per batch:**

1. **Transport error or timeout:** retry once at temperature 0, within S4's budget.
2. **Schema or invariant failure after the retry:** `verdict = verification_failed`.
3. **A `verification_failed` event** is created with `risk_score` and `risk_level` NULL and an
   "unverified" badge. Notification uses a **detector-only rule**: notify when a security-relevant
   class (person, vehicle) was detected at or above `detection_confidence_threshold` (`backend/core/config.py:1788`).
   The owner is never left blind, and nothing is silently scored (S5). `notification_filter`
   evaluates this rule **before** any threshold comparison. The event does **not** require
   acknowledgment: `requires_ack` becomes null-safe and keeps acknowledgment for scored risk ≥ 80
   (`backend/services/event_broadcaster.py:327` reads `data.get("risk_score", 0)`, whose default
   applies only when the key is absent).
4. **Repeated failures** open the circuit breaker on `vlm_client`. `degradation_manager` marks
   `ai-vlm` unhealthy, and the system reports `DegradationMode.DEGRADED`
   (`backend/services/degradation_manager.py:68-74`). Every batch takes step 3 until recovery,
   surfaced through the health endpoint and a Prometheus alert.

**`uncertain`** keeps the model's score and gets a "needs review" badge. It notifies through the
normal threshold.

**Cold starts.** `ai-vlm` sleeps when idle. The batch aggregator sends a **wake request when a batch
opens**, so the model loads during the 30-90 s window. The wake request is a minimal real request,
`/v1/chat/completions` with `max_tokens: 1`, because health probes may not wake a sleeping server;
verify this at M1. Triton specialist loads use the same
wake-on-open.

**Out-of-memory or load failure** takes step 4.

**Privacy.** Inference is local. Stored rows reference images by path and never embed them.

## §7 Testing

The repo is TDD. The existing gates stay in force: unit floor 84, integration 37, the frontend
floors, the conformance tier's no-xfail/skip rule, the contract drift gate (`gen-ai-contract.py
--check`), and the parity golden baseline.

| Layer                                  | Tests                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Unit                                   | `key_frame_selector` Hypothesis properties. `VlmVerdict` invariants, table-driven, including a camera threshold inside the low band. The failure ladder through FakeProvider fault injection (timeout, schema-invalid, 5xx) → circuit → DEGRADED. **The enforcement probe: a server that accepts but ignores the schema must read as "not enforced"**, a regression test for the E5 bug class. Wake-on-open sends exactly one wake. `notification_filter`, `requires_ack` and every other live-path `risk_score` consumer get a NULL-score fixture.                                                  |
| Contract / conformance                 | `vlm_assess` generated from `VLM_OPS`/`VlmVerdict`; golden payload and snapshot; FakeProvider coverage; the new `ProviderId`s register with `required={"vlm_assess"}`; the "backend never imports `ai.*`" rule still holds. Via `httpx.ASGITransport`.                                                                                                                                                                                                                                                                                                                                               |
| Integration                            | `create_all` adds `event_verifications` to a **pre-populated** database without touching existing rows. API and WebSocket carry `verification`; legacy events omit it. The replay harness end to end on a synthetic fixture set gives deterministic metrics. **Replay after retention:** freeze items, run the retention cleanup, then replay; the inputs are identical and the run succeeds. **Null-score delivery end to end:** a `verification_failed` event (NULL score) goes database → WebSocket → "unverified" badge in the UI → detector-only notification, with no acknowledgment required. |
| Frontend                               | Vitest + MSW: verdict badge, criteria, reviewed frames, verdict filter, empty states, legacy rendering unchanged                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| Hardware (A5500; scripted, outside CI) | S1 (sampled `nvidia-smi` during replay); S4 p95 including cold starts; the enforcement probe against the real `llama-server`; the tool-calling probe; later the RT-VLM fit. Aggregate reports are committed.                                                                                                                                                                                                                                                                                                                                                                                         |

## §8 Phasing and milestones

**Where each step runs** (D2):

| Environment         | Steps                                                                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| GB300 (development) | Phase G0; all of Phase 0; all of Phase 1 except 1.7; Phase 2 replay and bake-off runs, on synthetic and copied real items |
| A5500 (production)  | The `vlm`-mode bring-up (1.7); S1 and S4 on its 24 GB; Phase 3 go-live                                                    |
| Brev VMs            | The hardware matrix (step 2.3); RT-VLM fit per architecture (step 4.2)                                                    |

**Phase G0: GB300 development environment** (can start immediately; see the checklist below)

- G0.1 **Backend dev environment:** the uv venv (arm64; the unit tier already collects on 64 KiB
  pages), test Postgres and Redis on rootless podman, and a free API port. The flagship vLLM holds `127.0.0.1:8000`.
- G0.2 **Build llama.cpp for aarch64 and sm_103** (`CUDA_ARCHITECTURES=103`, per
  `env-templates/gb300.env.template`). Serve the development VLM from `ai-vlm`: Qwen3-VL-4B or 8B now,
  and Nemotron-12B-VL after the pin bump. Run the enforcement probe against it.
- G0.3 **Optional: the vlm-mode GPU stack locally.** Run the Triton gateway (arm64 `sbsa` image) with
  YOLO26 and the specialists in explicit load mode, beside `ai-vlm`. Summing our processes' memory in
  `nvidia-smi` gives an **S1 estimate** before any 24 GB hardware is involved. The S1 gate itself
  stays on the A5500 or a Brev A10G/L4.
- G0.4 **Synthetic eval items** from `scripts/synthetic`, so replay works before any real item is
  frozen.

The full live pipeline on the GB300 (FTP → YOLO26 on Triton → batch → VLM) needs the arm64 port's
milestones 1 and 2 (`docs/superpowers/specs/2026-09-12-arm64-gb300-milestone1-design.md`). It is not
on this design's critical path.

**Phase 0: Foundations** (independent of VSS)

- **0.1 Freeze the control: removed in rev 5.** There is no control and no pre-switch traffic
  (F9, F10). The freeze tool already written stays in the repo, unused.
- **0.2 Legacy single-GPU bring-up: removed in rev 5.** The A5500's first bring-up is in `vlm` mode
  (step 1.7).
- **0.25 Null-safety audit.** The VLM path's `verification_failed` events carry a NULL score (D11),
  and so do 0.3's. Before either can reach production, make every live-path consumer null-safe:

  - `WebSocketEventData` (`backend/api/schemas/websocket.py:252-253`);
  - `requires_ack` (`backend/services/event_broadcaster.py:327`);
  - `notification_filter` (`:66`);
  - the frontend's score rendering.

  Audit the remaining backend comparison and arithmetic sites (61 at `4eab98e5`, found with
  `grep -rnE 'risk_score\s*(>=|<=|>|<)'` and similar), and give each live-path consumer a
  NULL-score test.

- **0.3 Constrained verdict on the legacy path.** Send llama.cpp `json_schema` instead of `nvext`,
  add the enforcement probe, and apply the §6 semantics: never a default score. **Rev 5:** the code
  is written and kept, because it removes E5's fail-open from code that stays in the repo until R8.
  No further legacy work follows from it: no home-endpoint probe, and no legacy S5 gate.
- **0.4 `event_verifications`** plus the `verification` API/WebSocket field.
- **0.5 Labels.** The eval store reaches ≥100 benign / ≥20 incidents from born-labeled items
  (synthetic scenarios, owner-generated media, stock imagery; §5). The `EventFeedback` import
  path ships now and is used after go-live.

**M0 (rev 5):** Phase 0's code is merged with every CI tier green, and the eval store meets the
size bar.

**Phase 1: The VLM path** (llama.cpp)

- 1.1 Contract: `VlmVerdict`, `VLM_OPS`, goldens, FakeProvider, conformance.
- 1.2 The `ai-vlm` service and the `vlm` compose profile.
- 1.3 `key_frame_selector`, `vlm_client` with the probe, `vlm_analyzer`, invariants, failure ladder,
  degradation wiring, wake-on-open.
- 1.4 Residency control: Triton explicit mode with the `vlm` load set, plus llama.cpp idle sleep.
- 1.5 The `PIPELINE_MODE` flag, defaulting to `vlm` (§2).
- 1.6 The frontend changes.
- 1.7 **The A5500 bring-up in `vlm` mode** (checklist below). It replaces the removed step 0.2.

**M1:** `vlm` mode runs end to end on the A5500 with Qwen3-VL-4B as the smoke model, and every CI
tier is green.

**Phase 2: Evaluation and bake-off**

- 2.1 The replay harness. (Rev 5 dropped the offline 30B control replay.)
- 2.2 The bake-off runs and report. The owner sets the S2 and S3 bars (`S2_MAX`, `S3_MIN`)
  before the report.
- 2.3 **Hardware matrix on Brev.** This is evidence, not a go-live gate.
  - Run the leading candidates on A10G (24 GB, sm_86), L4 (24 GB, sm_89), RTX PRO 4500 (32 GB,
    sm_120 [A]) and T4 (16 GB), and record S1 and S4 for each tier.
  - On the RTX PRO 4500, run the NVFP4-QAD checkpoint in vLLM and read the resolved quantization
    method from the startup log ([`04`](../../vss-integration/04-fp4-and-deployment.md) §6). That
    settles whether NVFP4 computes natively on consumer Blackwell (03 Q1).
  - Confirm each VM's architecture with `nvidia-smi --query-gpu=compute_cap` before trusting a
    result.

**M2:** the owner picks the VLM.

**Phase 3: Go-live** (rev 5; formerly "Cutover")

- 3.1 The S1-S6 gate on the pick → sign-off → deploy → 14-day observation (§5).
- 3.2 Regression replay on every model or prompt change.

**M3:** the go-live holds for 14 days, or the stop triggers fire and the findings are recorded
(§5 step 4).

**Phase 4: The RT-VLM provider** (gated: starts after M2, not required for M3)

- 4.1 The adapter, the KV-bytes compose patch, conformance.
- 4.2 The RT-VLM fit attempt on the A5500 and on Brev's A10G, L4 and RTX PRO 4500, with each
  outcome recorded in `docs/vss-integration/` as upstream evidence.
- 4.3 The **VSS skill Delta build**: `_builds/hsi-consumer-24gb/override.env` + compose patches. It needs zero
  upstream changes ([`08`](../../vss-integration/08-audit-profile-anatomy.md) §9). It configures the
  base profile's RT-VLM for 24 GB, with our llama.cpp as its remote LLM.

**M4:** RT-VLM conformance is green, the fit record is committed, and the Delta build exists.

### GB300 development checklist (Phase G0)

- [ ] **Two container daemons.** Our stack runs on rootless podman. The co-resident `dgx-inference`
      stack runs on rootful docker and holds ports (the flagship vLLM on `127.0.0.1:8000`, LiteLLM on `:4000`). Debug ours with `podman`.
- [ ] **GPU headroom and the flagship.** Since the Cosmos container was stopped (2026-09-23), the
      flagship vLLM holds ~202 GiB and **~47.9 GiB is free** for our models. The flagship **must stay
      resident**: - Keep our total a few GiB under the free memory. vLLM needs its full reservation free when it
      restarts [A], so leave that margin, or stop our GPU services before restarting the flagship. - Check `nvidia-smi` before loading any model.
- [ ] **Cosmos may come back.** The stopped container has `restart=no`, but `docker compose up` on the
      `dgx-inference` stack (`~/gitlab/dgx-station-inference-stack/stack/`) restarts it and takes
      ~39 GiB back. Making the stop permanent (a compose profile, plus removing its LiteLLM route) is
      a change in that repository and is the owner's call.
- [ ] **Architecture.** aarch64 with 64 KiB pages. There is no host CUDA toolkit, so build CUDA code
      in containers. llama.cpp uses `CUDA_ARCHITECTURES=103`.
- [ ] **Env template.** Start from `env-templates/gb300.env.template`.
- [ ] **Codex reviews.** `/codex:*` sandboxing needs `bwrap` user namespaces. This host loads Ubuntu's
      `bwrap-userns-restrict` AppArmor profile for that (added 2026-09-23). If a Codex review comes
      back empty, run `codex sandbox -- true` first.

### A5500 bring-up checklist (step 1.7, `vlm` mode)

Rev 5 moved this from step 0.2. The A5500 comes up directly in `vlm` mode, with no legacy LLM.

- [ ] **GPU assignment.** Set every `GPU_*` variable to `0` (`.env.example` documents "SINGLE-GPU:
      Set all to 0"). Remove the A400 from device passthrough.
- [ ] **CUDA architecture.** `CUDA_ARCHITECTURES=86`. `.env.example` ships `89`, and `setup.py`
      auto-detect normally overwrites it. Check it before building `ai-vlm`.
- [ ] **No legacy LLM.** `ai-llm`, Florence and the heavy enrichment are not deployed. The
      `scripts/a5500_precheck.py` checks for the placeholder LLM (`llm_model`, `ai_llm_mount`) are
      obsolete; replace them with an `ai-vlm` model/mount check.
- [ ] **VLM.** `ai-vlm` serves the smoke model (Qwen3-VL-4B) with `CUDA_ARCHITECTURES=86`. Run the
      enforcement probe against it before any event reaches it.
- [ ] **Test-environment traps:**
  - A `TMPDIR` in `.env` that differs from pytest's `tmp_path` false-reddens four
    `write_runtime_env` tests; CI sets no `TMPDIR`.
  - Stale `__pycache__` directories for deleted modules false-redden deletion guards.
- [ ] **Health.** Run `/platform-healthcheck`, and complete the root `AGENTS.md` infrastructure
      verification checklist.

## Implementation facts

These are facts an agent on another machine cannot recover from the conversation that produced this
design.

**E5 sites** (`backend/services/nemotron_analyzer.py`):

| Site                             | Lines        |
| -------------------------------- | ------------ |
| `guided_json` settings           | `:382-385`   |
| The probe                        | `:462-483`   |
| The `nvext` payload              | `:593`       |
| `/completion` payload            | `:1033-1049` |
| Default score 50                 | `:4392`      |
| Event defaults `50` / `"medium"` | `:2884-2885` |

**Invariants this design changes.** Existing code relies on both.

- _A score always exists._ It held only because of the 50/medium fail-open (E5). The live path
  assumes it at the sites listed in step 0.25.
- _Production rows persist._ Retention hard-deletes old events and their detections
  (`backend/services/cleanup_service.py:294` and the step before it), which is why eval items are
  self-contained.

**Schema.** `create_all` only (`backend/core/database.py:407`). A precedent for hand-written SQL
exists (`docs/api/migrations/NEM-5051-*.sql`), but this design needs none.

**Reused pieces:**

| Piece             | Where                                                                          |
| ----------------- | ------------------------------------------------------------------------------ |
| Notifications     | `notification_filter.py:66`                                                    |
| Severity bands    | `backend/services/severity.py` (`low_max` etc. from settings)                  |
| Degradation modes | `degradation_manager.py:68-74`                                                 |
| Circuit breaker   | `circuit_breaker.py`                                                           |
| Audit trail       | `LLMInteraction`                                                               |
| Labels            | `EventFeedback` (`backend/models/event_feedback.py`)                           |
| Event image paths | `Detection.file_path` / `thumbnail_path` (`backend/models/detection.py:49,60`) |
| Ingest extensions | `file_watcher.py:70`                                                           |

**The contract generator** declares external surfaces as data (`LLM_OPS` in
`scripts/gen-ai-contract.py`). Regenerate with `uv run python scripts/gen-ai-contract.py`; CI checks
with `--check`.

**VSS.** Clone `NVIDIA-AI-Blueprints/video-search-and-summarization`. The audits cite `1e94133b4`.
VSS moves fast, so re-verify any line before relying on it.

**VLM candidates** (all ungated; confirm sizes from the GGUF blobs):

| Candidate                 | License                      | Notes                                                                                                                                                                 |
| ------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Qwen3-VL-4B / 8B-Instruct | Apache-2.0                   | Tool-calling template; runs on llama.cpp `b7972`                                                                                                                      |
| Nemotron-Nano-12B-v2-VL   | NVIDIA Open Model License    | Community GGUF Q4_K_M ≈ 7.5 GB + mmproj 1.69 GB [E]; tool calling plus a thinking toggle; needs the llama.cpp bump. The NVFP4-QAD checkpoint serves the RT-VLM phase. |
| Cosmos-Reason2-8B         | Check license and gating [?] | Served on demand by our own vLLM on the GB300 (BF16). A quality reference; a consumer build would need quantization.                                                  |
| Cosmos3-Edge-4B           | —                            | RT-VLM phase only                                                                                                                                                     |

## Risks and open questions

| Risk / question                                                                                                                             | Settled by                                                                                                             |
| ------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Does `b7972` silently ignore `nvext` (E5)?                                                                                                  | The first request of step 0.3                                                                                          |
| Does llama.cpp enforce `json_schema` on _multimodal_ chat requests at the chosen pin?                                                       | The enforcement probe, phase 1.3                                                                                       |
| Four images per batch on sm_86: does S4 hold, and how many image tokens do tiling VLMs spend?                                               | The bake-off                                                                                                           |
| RT-VLM on sm_86: VSS treats FP8 as unsupported on Ampere [A]; the NVFP4 weight-only path is unknown; the BF16 12B blob (26 GB) does not fit | Phase 4 records the outcome, whichever it is                                                                           |
| Labels arrive after retention deleted the event                                                                                             | Only after go-live: label within the 30-day window. Synthetic and stock items are born labeled (§5)                    |
| `docker compose up` on the `dgx-inference` stack restarts Cosmos (~39 GiB) while our models are loaded                                      | Check `nvidia-smi` before loading; make the stop permanent in the stack repo (owner's call)                            |
| The GB300's shared GPU (100% busy) skews timing and has no 24 GB cap                                                                        | Measure S1 and S4 only on 24 GB-class hardware (the A5500, Brev A10G/L4)                                               |
| A Brev VM's GPU differs from its label                                                                                                      | Check `nvidia-smi --query-gpu=compute_cap` before each run                                                             |
| Real-camera items left on a Brev VM                                                                                                         | Wipe the eval store at teardown (D10)                                                                                  |
| Too few labeled items for ≥100/≥20                                                                                                          | Born-labeled synthetic generation covers both sides (step 0.5)                                                         |
| Fixed bars set without a baseline are too loose or too strict                                                                               | Report the verdict mix and per-item disagreements beside the bars; the owner can reset them before the gate (step 2.2) |
| Replay drifts from live behaviour (key-frame choice, batching)                                                                              | The 14-day observation window and the stop triggers                                                                    |
