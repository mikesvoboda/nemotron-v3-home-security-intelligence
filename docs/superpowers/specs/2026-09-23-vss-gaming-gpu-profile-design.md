# VSS Gaming-GPU Profile — Design

**Status:** approved design (§1-§8 approved section by section by the owner, 2026-09-23), ready for implementation planning
**Date:** 2026-09-23
**Branch:** `feat/vss-gaming-gpu-profile`
**Revision:** rev 2 (2026-09-23). Amended after a Codex adversarial review, owner-approved:
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

| #   | Decision                                                                                                                                                                                                                                                                                                            |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | **Downstream-first.** The work lands in this repo, behind the `backend/ai_contract` seam, shaped so it can go upstream later (R9).                                                                                                                                                                                  |
| D2  | **Test box:** the amd64 RTX A5500, 24 GB, sm_86, **single GPU**. The A400 is retired. The implementation agent runs **on that box**. Ampere has no FP8 or FP4 tensor cores, so this box proves fit and salience, not native NVFP4 speed.                                                                            |
| D3  | **Per-event architecture: detector + one VLM.** The detector gates every upload and supplies geometry. One VLM describes, verifies and scores candidates from the evidence stills in **one constrained call**. Florence-2 and most enrichment retire. The face, re-ID and plate specialists stay, loaded on demand. |
| D4  | **Engine: contract-first.** llama.cpp (GGUF + mmproj) ships first. RT-VLM, VSS's engine, follows behind the same contract in a **gated** phase; its A5500 fit, or its failure, is recorded as upstream evidence. The VSS Delta build is produced in that phase.                                                     |
| D5  | **Model slots are pluggable.** The owner picks the VLM after the bake-off (M2). The reasoning LLM is deferred to the owner (R10). `NVIDIA-Nemotron-3-Nano-4B` Q4_K_M is the **interim placeholder**, used only by the legacy path until cutover.                                                                    |
| D6  | **Ingest is FTP stills only.** Live streaming is R1.                                                                                                                                                                                                                                                                |
| D7  | **Evaluation is replay, not live shadow,** over **self-contained eval items** that production retention cannot touch. The legacy and VLM modes do not fit on one card together. The control is the verdict recorded by the dual-GPU 30B pipeline, or an offline 30B replay where none was recorded.                 |
| D8  | **Success criteria S1-S6** (below) gate the cutover.                                                                                                                                                                                                                                                                |
| D9  | **Out of scope:** everything in [`12`](../../vss-integration/12-postponed-roadmap.md).                                                                                                                                                                                                                              |
| D10 | **Real-camera data stays on the box,** in an eval store outside the repo. Only synthetic items and aggregate metrics enter git.                                                                                                                                                                                     |
| D11 | **Failure delivery is null-safe end to end.** A `verification_failed` event has a NULL score and level, and it still reaches the dashboard and the detector-only notification. It does **not** require acknowledgment; acknowledgment stays reserved for scored risk ≥ 80.                                          |

## Success criteria

Measured on the A5500.

| #   | Criterion       | Bar                                                                                                                                                         |
| --- | --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S1  | Fit             | Peak VRAM ≤ **20.4 GiB** (0.85 × 24 GB) with the detector, on-demand specialists and the VLM resident; no CPU offload of the VLM                            |
| S2  | False positives | On labeled-benign items, the VLM path's rate at `risk_level ≥ medium` is **≤ 50% of the control's**                                                         |
| S3  | No new misses   | Recall on labeled incidents (real + synthetic) **≥ the control's**                                                                                          |
| S4  | Latency         | p95 per-batch verdict ≤ **30 s**, including cold starts                                                                                                     |
| S5  | Robustness      | **0** unparseable verdicts. Every failure surfaces as `verification_failed`, never as a default score, and reaches the dashboard and the notification path. |
| S6  | Contract        | The conformance suite is green including `vlm_assess`, and the FakeProvider covers it                                                                       |

## §2 Architecture

A backend setting, `PIPELINE_MODE=legacy|vlm`, selects the per-event path. `legacy` stays the
default until cutover.

```
FTP still/clip → file_watcher → YOLO26 gate (Triton) ── nothing detected → no event (unchanged)
                                      │ detections
                           batch_aggregator (90 s / 30 s idle, unchanged)
                                      │ batch closes
          ┌───────────────────────────┴──────────────────────────────┐
  legacy: enrichment + Florence → text → LLM            vlm: key_frame_selector (≤4 stills)
          (control; Nano-4B placeholder)                     → face / re-ID / plate specialists, on demand
                                                             → vlm_assess(images + text context,
                                                                          json_schema-constrained)
          └───────────────────────────┬──────────────────────────────┘
                              Event (+ verification) → WebSocket / UI
```

**Units.** Each has one job.

| Unit                                     | Job                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `ai-vlm` compose service (profile `vlm`) | `llama-server` + GGUF + `--mmproj`; `/v1/chat/completions` with `json_schema`; `--jinja --sleep-idle-seconds --alias`; 2 slots; context sized for 4 images + ~6K text + output. Reachable on the internal compose network. Its host port is a new `AI_VLM_PORT` variable (default `8098`, unused today), added to `.env.example` first per the root port rule.                                                                                                                                                                                         |
| `backend/services/key_frame_selector.py` | Picks 1-4 stills per batch: the best detection per camera/class plus the most recent. A pure function. **Ingest-agnostic:** it takes image references from any source, which is the seam for R1.                                                                                                                                                                                                                                                                                                                                                       |
| `backend/services/vlm_client.py`         | The contract-registered client for `vlm_assess`, including the enforcement probe (§3)                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `backend/services/vlm_analyzer.py`       | Builds an **`AssessInput` snapshot** (key-frame candidates, detections, camera, zones, household: today's prompt context minus Florence) and assembles the prompt from it as a **pure function**. Production builds the snapshot from the database; replay loads it from the eval store; both share one code path. Calls `vlm_assess`, applies the invariants (§6), and maps the verdict to an Event. A **sibling** of `nemotron_analyzer.py`, not an edit to it. The legacy path stays byte-identical to the code that produced the control verdicts. |
| Triton gateway                           | Moves from `--model-control-mode=none` (`ai/gateway/entrypoint.sh:131`) to **explicit**, with per-mode load sets. `vlm` mode loads YOLO26 plus on-demand specialists only. This is the residency control E4 found missing.                                                                                                                                                                                                                                                                                                                             |

**VRAM** [C/A; S1 measures it]:

| Mode     | Resident                                                                                                                            | ≈ GiB  |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------ |
| `legacy` | Gateway with all models resident (~8-9) + Nano-4B (5.5)                                                                             | ~14    |
| `vlm`    | YOLO26 + Triton overhead (~1) + on-demand specialists (~1-2) + `ai-vlm` (e.g. 12B-VL Q4 7.5 + mmproj 1.7 + KV and image buffers ~2) | ~13-14 |

The two modes never co-reside, which is why evaluation is replay (D7).

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

- Add `ProviderId.LLAMACPP_VLM` and `ProviderId.RTVI_VLM`
  (`backend/ai_contract/provider.py:22-35`). Each registers with `required={"vlm_assess"}`, the
  subset pattern `llamacpp-serve` uses.
- The FakeProvider returns a deterministic verdict keyed on an image hash.
- The parity checker gets a `DECLARED` entry, as the `llm_*` ops have.

**Engine 1: llama.cpp (ships first).**

- **Wire:** `POST /v1/chat/completions` with up to 4 base64 `image_url` parts and a `json_schema`
  response format.
- **Enforcement probe:** it proves enforcement by requesting a schema with a required constant field
  and checking the output. **A 2xx alone proves nothing.**
- **llama.cpp pin:** `b7972` (`ai/nemotron/Dockerfile`) runs Qwen3-VL. Nemotron-12B-VL needs a newer
  pin with its multimodal support, merged 2026-02-14 or later, so the bake-off includes that bump.

**Engine 2: RT-VLM (gated Phase 4; not required for cutover).**

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

## §5 Evaluation and cutover

**Eval items.** Every evaluation input is a self-contained **eval item** with its own id, stored in
the eval store. Nothing in it depends on production rows, which retention deletes. An item holds:

- the key-frame candidate images, **copied** into the eval store;
- the `AssessInput` snapshot (§2): detections, camera, zones, household context;
- the label: benign, or incident with an expected minimum severity;
- the control verdict and where it came from;
- `source_event_id`, for provenance only (no foreign key).

| Item kind               | Source                                                                         | Label                                                                                                                                          | Control                                                                                                                                                            |
| ----------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Historical, pre-switch  | Events from before the switch (step 0.1)                                       | The owner's feedback (`EventFeedback`): `false_positive` → benign; `missed_threat`, or `accurate` on high → incident, with `expected_severity` | **Recorded** by the dual-GPU 30B pipeline, copied at freeze time                                                                                                   |
| Historical, post-switch | Events labeled after the switch                                                | Same                                                                                                                                           | The legacy pipeline **replayed offline with the production 30B**. The Nano-4B placeholder produced these events, so their recorded verdict is not a valid control. |
| Synthetic incidents     | `scripts/synthetic` (17 scenarios: normal, suspicious, threats, environmental) | The scenario spec                                                                                                                              | Offline 30B replay, as above                                                                                                                                       |

Offline 30B replay tolerates partial CPU offload, so the baseline stays production quality. Keep
the 30B GGUF on disk after step 0.2.

**Size:** at least **100 benign and 20 incidents**. At 50 benign, one frame moves the rate by 2
points, which is too coarse for S2.

**Eval store** (on the box, outside the repo, per D10): the copied images plus one SQLite file with
`eval_items`, `eval_runs` and `eval_results`.

- It is independent of production retention.
- It is **portable**: copying the directory lets the same set validate other hardware later (R11).
- **Labeling window.** Labels come from `EventFeedback` on live events, so the owner must label an
  event before retention deletes it, within 30 days. Step 0.5 imports labels into eval items by
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
3. computes S1-S5 against the labels and the control;
4. reports **per-item disagreements**, which are the tuning signal.

**Metric definitions:**

- **S2:** benign items at `risk_level ≥ medium`, divided by all benign items.
- **S3:** incidents at or above their expected minimum level, divided by all incidents.
- `uncertain` items count at their scored level.

**Bake-off.** Run the same replay per candidate: Qwen3-VL-4B, Qwen3-VL-8B, and Nemotron-12B-VL after
the llama.cpp bump. Cosmos3-Edge-4B follows in Phase 4 through RT-VLM. Report per candidate:

- S1-S5 and the `uncertain` rate;
- the **tool-calling probe** through llama.cpp, which keeps R3 open;
- long-context KV cost;
- license and gating.

**The owner picks.**

**Cutover:**

1. **Gate:** the owner's pick passes S1-S6 on replay, and the owner signs off.
2. **Flip:** set `PIPELINE_MODE=vlm` and enable the compose profile `vlm`. `ai-llm`, Florence and the
   heavy enrichment stop; `ai-vlm` starts.
3. **Observe for 14 days**, with the owner giving feedback in the normal UI. **Rollback triggers:**
   - any `missed_threat` that a legacy replay of the same event would have caught;
   - a false-positive feedback rate clearly above the replay estimate.
4. **Roll back** by flipping the flag. Legacy services stay deployable until R8.
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

**Phase 0: Foundations** (independent of VSS)

- **0.1 Freeze the control first.** Record the switch timestamp, then build eval items (§5) from
  pre-switch events: copied images, `AssessInput` snapshots and the recorded 30B verdicts. After
  0.2, new events come from the Nano-4B, so their recorded verdicts no longer count as control.
- **0.2 Single-GPU bring-up.** See the checklist below.
- **0.25 Null-safety audit.** Step 0.3 is the first time production events can have a NULL score,
  so before it lands, make every live-path consumer null-safe:

  - `WebSocketEventData` (`backend/api/schemas/websocket.py:252-253`);
  - `requires_ack` (`backend/services/event_broadcaster.py:327`);
  - `notification_filter` (`:66`);
  - the frontend's score rendering.

  Audit the remaining backend comparison and arithmetic sites (61 at `4eab98e5`, found with
  `grep -rnE 'risk_score\s*(>=|<=|>|<)'` and similar), and give each live-path consumer a
  NULL-score test.

- **0.3 Constrained verdict on the legacy path.** Send llama.cpp `json_schema` instead of `nvext`,
  add the enforcement probe, and apply the §6 semantics: never a default score.
- **0.4 `event_verifications`** plus the `verification` API/WebSocket field.
- **0.5 Labels.** The owner labels to ≥100 benign / ≥20 incidents through the feedback UI, within
  each event's 30-day retention window. Import the labels into eval items; labeled post-switch
  events become items with an offline 30B control. Generate the synthetic incidents.

**M0:** the A5500 is healthy on one GPU, the eval store is frozen, and S5 holds on the legacy path.

**Phase 1: The VLM path** (llama.cpp)

- 1.1 Contract: `VlmVerdict`, `VLM_OPS`, goldens, FakeProvider, conformance.
- 1.2 The `ai-vlm` service and the `vlm` compose profile.
- 1.3 `key_frame_selector`, `vlm_client` with the probe, `vlm_analyzer`, invariants, failure ladder,
  degradation wiring, wake-on-open.
- 1.4 Residency control: Triton explicit mode with per-mode load sets, plus llama.cpp idle sleep.
- 1.5 The `PIPELINE_MODE` flag.
- 1.6 The frontend changes.

**M1:** `vlm` mode runs end to end on the A5500 with Qwen3-VL-4B as the smoke model, and every CI
tier is green.

**Phase 2: Evaluation and bake-off**

- 2.1 The replay harness, plus the offline 30B control replay for synthetic items.
- 2.2 The bake-off runs and report.

**M2:** the owner picks the VLM.

**Phase 3: Cutover**

- 3.1 The S1-S6 gate on the pick → sign-off → flip → 14-day observation.
- 3.2 Regression replay on every model or prompt change.

**M3:** the cutover holds for 14 days, or it is rolled back with the findings recorded.

**Phase 4: The RT-VLM provider** (gated: starts after M2, not required for M3)

- 4.1 The adapter, the KV-bytes compose patch, conformance.
- 4.2 The A5500 fit attempt, with the outcome recorded in `docs/vss-integration/` as upstream evidence.
- 4.3 The **VSS skill Delta build**: `_builds/hsi-consumer-24gb/override.env` + compose patches. It needs zero
  upstream changes ([`08`](../../vss-integration/08-audit-profile-anatomy.md) §9). It configures the
  base profile's RT-VLM for 24 GB, with our llama.cpp as its remote LLM.

**M4:** RT-VLM conformance is green, the fit record is committed, and the Delta build exists.

### A5500 bring-up checklist (step 0.2)

- [ ] **GPU assignment.** Set every `GPU_*` variable to `0` (`.env.example` documents "SINGLE-GPU:
      Set all to 0"). Remove the A400 from device passthrough.
- [ ] **CUDA architecture.** `CUDA_ARCHITECTURES=86`. `.env.example` ships `89`, and `setup.py`
      auto-detect normally overwrites it. Check it before building `ai-llm`.
- [ ] **Placeholder LLM.** Point `LLM_MODEL_PATH` at `NVIDIA-Nemotron-3-Nano-4B` Q4_K_M (official
      GGUF, 2.64 GiB; architecture `nemotron_h`, which llama.cpp `b7972` registers). The `ai-llm`
      volume mount targets the 30B directory, so adjust it too. Budget ~5.5 GiB including the
      262K-token KV.
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

| Candidate                 | License                   | Notes                                                                                                                                                                 |
| ------------------------- | ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Qwen3-VL-4B / 8B-Instruct | Apache-2.0                | Tool-calling template; runs on llama.cpp `b7972`                                                                                                                      |
| Nemotron-Nano-12B-v2-VL   | NVIDIA Open Model License | Community GGUF Q4_K_M ≈ 7.5 GB + mmproj 1.69 GB [E]; tool calling plus a thinking toggle; needs the llama.cpp bump. The NVFP4-QAD checkpoint serves the RT-VLM phase. |
| Cosmos3-Edge-4B           | —                         | RT-VLM phase only                                                                                                                                                     |

## Risks and open questions

| Risk / question                                                                                                                             | Settled by                                                                                                                      |
| ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Does `b7972` silently ignore `nvext` (E5)?                                                                                                  | The first request of step 0.3                                                                                                   |
| Does llama.cpp enforce `json_schema` on _multimodal_ chat requests at the chosen pin?                                                       | The enforcement probe, phase 1.3                                                                                                |
| Four images per batch on sm_86: does S4 hold, and how many image tokens do tiling VLMs spend?                                               | The bake-off                                                                                                                    |
| RT-VLM on sm_86: VSS treats FP8 as unsupported on Ampere [A]; the NVFP4 weight-only path is unknown; the BF16 12B blob (26 GB) does not fit | Phase 4 records the outcome, whichever it is                                                                                    |
| Labels arrive after retention deleted the event                                                                                             | Label within the 30-day window (step 0.5); labeled post-switch events and synthetic items add items with an offline 30B control |
| Too few feedback labels for ≥100/≥20                                                                                                        | Step 0.5 budgets owner labeling time; synthetic incidents cover the incident side                                               |
| Replay drifts from live behaviour (key-frame choice, batching)                                                                              | The 14-day observation window and the rollback triggers                                                                         |
