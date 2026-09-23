# 12 — Postponed Roadmap

Items the VSS gaming-GPU effort **deliberately postponed** on 2026-09-23, so a future agent
neither re-discovers them nor mistakes their absence for an oversight. The current effort is the
design in
[`2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md):
detector plus one VLM, FTP stills, a single A5500, with milestones M0-M4.

Each item records why it waits, the **trigger** that reopens it, and where its evidence lives.
When an item is picked up, move it into its own spec and mark it here with the date and a link.

## Index

| #   | Item                                                                        | Trigger to reopen                                                                     | Evidence                                                                                     |
| --- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| R1  | Live-stream ingest with our own motion/object detection                     | Cutover (M3) holds 14 days                                                            | §R1, [`10`](10-audit-feature-inventory.md) §2.1, [`09`](09-audit-integration-surfaces.md) §2 |
| R2  | Wire the MQTT / Home Assistant / Frigate chain                              | R1 picks Frigate, or HA integration is wanted                                         | E26 in [`11`](11-errata-2026-09-23.md)                                                       |
| R3  | NemoClaw agent running on the VLM                                           | The VLM pick (M2) passes the tool-calling probe                                       | [`10`](10-audit-feature-inventory.md) addendum                                               |
| R4  | Agent features: NL Q&A/chat, MCP tools, NL search, incident reports         | Cutover holds                                                                         | [`10`](10-audit-feature-inventory.md) §7, [`09`](09-audit-integration-surfaces.md) §4g       |
| R5  | Per-camera plain-language rules on stills                                   | Cutover holds                                                                         | [`10`](10-audit-feature-inventory.md) §7 item 3, E26                                         |
| R6  | Text-prompt detection with YOLO-World                                       | Any time after M1                                                                     | [`10`](10-audit-feature-inventory.md) §7 item 8                                              |
| R7  | Audio understanding                                                         | An audio-capable model under ~20 GB exists                                            | [`10`](10-audit-feature-inventory.md) §3B                                                    |
| R8  | Delete retired enrichment code, tables and panels                           | Cutover holds 14 days                                                                 | Design §4, [`06`](06-repo-a-readiness.md) §2, §2a                                            |
| R9  | Upstream contributions to VSS                                               | M4 evidence exists and the VSS team has been asked which "not on the roadmap" applies | §R9, [`08`](08-audit-profile-anatomy.md) §1.7, §9                                            |
| R10 | Final model choices: reasoning LLM and VLM                                  | The owner selects (the VLM at M2)                                                     | §R10                                                                                         |
| R11 | Validating the tiers beyond 24 GB (halo 32 GB, volume 12-16 GB, entry 8 GB) | Hardware is available (procurement)                                                   | [`05`](05-hardware-profiles.md), E1-E3                                                       |
| R12 | Licensing and redistribution                                                | Before any consumer distribution                                                      | [`03`](03-open-questions.md), [`09`](09-audit-integration-surfaces.md) open Q8               |
| R13 | The biometric data model (retention, consent, erasure)                      | Before any consumer distribution                                                      | [`03`](03-open-questions.md) Q7, [`06`](06-repo-a-readiness.md) §5                           |
| R14 | The version-pinning tax (image mirroring, re-integration cadence)           | Before depending on VSS images in production                                          | [`03`](03-open-questions.md) Q8                                                              |

The test-platform items open in [`06`](06-repo-a-readiness.md) (§1.5 deletion cashing, the §1.6
import-bound seam fixture, the §1.7 frontend classification) belong to that program and stay
tracked there.

## R1. Live-stream ingest

**Goal (owner, 2026-09-23):** the platform streams every camera in real time and runs its own
motion and object detection instead of relying on camera FTP uploads.

**Why it waits:** the design fixes ingest to FTP stills to keep the first cutover bounded. The VLM
path is ingest-agnostic (`key_frame_selector` takes image references from any source), so a
stream front-end plugs in above the detector without changing it.

**Candidate front-ends:**

| Option                             | What it brings                                                                                                                                                                                                           | Cost / risk                                                                                                                         |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Frigate over MQTT**              | A mature open-source NVR built for consumer GPUs: decode, motion gating, detection, recordings. `backend/services/frigate_integration.py` (336 lines) already maps `frigate/{camera}/events` onto our `Detection` model. | Unwired, with no broker in compose (E26). Adds mosquitto plus a Frigate container.                                                  |
| **VSS RT-CV + behavior analytics** | DeepStream detection with NvDCF tracking, plus tripwires, loitering and proximity. This option **reopens VSS reuse** the stills path ruled out.                                                                          | A 17.8 GB image, saturates GPU compute at a few streams, Kafka-oriented, no YOLO BYOM ([`09`](09-audit-integration-surfaces.md) §2) |
| **Our own**                        | go2rtc (already running for live view) + motion gating + YOLO26 on sampled frames, building on the dormant `stream_manager` and `IngestionMode.RTSP` (E25)                                                               | The most custom code                                                                                                                |

**Constraint to carry forward:** continuous decode and detection spend GPU all the time, which
works against the duty cycling the design builds. Budget NVDEC and SM headroom alongside the VLM on
the same card. RT-VLM's live-stream alert mode fires on the substring "yes" and records no
rejections, so it is unusable as shipped for false-positive suppression
([`09`](09-audit-integration-surfaces.md) §5).

## R2. The MQTT / Home Assistant / Frigate chain

The chain is built but never started. `mqtt_client.py` (828 lines), `mqtt_publisher.py`,
`ha_discovery.py` and `frigate_integration.py` have no non-test caller, and compose runs no broker.
Wiring it means adding a broker service (port variable in `.env.example` first, per the root
`AGENTS.md` port rule), starting the chain in the application lifespan, and covering it with
integration tests.

## R3. NemoClaw on the VLM

NemoClaw's `custom` provider accepts our llama.cpp `ai-vlm` endpoint, and the candidate VLMs ship
tool-calling templates. RT-VLM cannot serve this role because it rejects `tools`. Full findings are
in the [`10`](10-audit-feature-inventory.md) addendum. To pick it up, solve four things:

1. **Capability:** score the chosen VLM with VSS's skill-eval `nemoclaw` runtime against the
   frontier default.
2. **Contention:** partition llama.cpp slots, or prioritize, so agent sessions leave the per-event
   30 s p95 intact.
3. **Reachability:** design how an OpenShell sandbox reaches the endpoint while loopback binding
   stays the security boundary.
4. **Parsing:** confirm llama.cpp parses the chosen model's tool calls.

The design prepares for this by making "tool calling through llama.cpp works" a bake-off criterion.

## R4. Agent features

These are natural-language Q&A and chat over events, an MCP tool server over the events API (with
auth, which VSS's lacks), natural-language search with a VLM re-check of results, and narrative
incident reports. [`09`](09-audit-integration-surfaces.md) §4 shows the VSS agent (NAT 1.8)
satisfies its LLM contract against llama.cpp **through configuration**: `--alias`,
`llm_reasoning: false`, and an `LLM_NAME` matching the model family. Estimated effort is 300-600
LoC for the MCP server plus ~150 lines of YAML **[A]**. Two small enablers are deferred from the
design: adding `scene_description` to the events full-text search trigger, and using VLM verdicts
as feedback-learning signal.

## R5. Per-camera plain-language rules

An example rule: "person at the side gate after dark". It runs through the same `vlm_assess` engine
on event stills. It also gives the stored-but-never-evaluated alert rules (E26) a real evaluator.

## R6. YOLO-World

YOLO-World is in the model set but unused. Wiring it gives open-vocabulary, text-prompted detection
at the gate, without adopting VSS's detection service.

## R7. Audio

Glass break, alarms and raised voices are valuable signals. The smallest VSS audio path (Omni
30B-A3B) needs ~29 GB and fits no consumer card. First confirm whether Foscam clips carry audio.

## R8. Post-cutover deletion

**What goes:** retire Florence-2, the heavy enrichment models, the in-process loaders the VLM path
no longer calls, the pose/demographics/clothing child tables, and their frontend panels (the
design's empty states become deletions).

**What stays:** the face, re-ID and plate specialists.

**What changes elsewhere:**

- This resolves [`06`](06-repo-a-readiness.md) §2a's parked in-process-tier question by
  retirement, not by swapping.
- Before deleting, clear stale `__pycache__` directories. A stale `backend/api/helpers/__pycache__`
  false-reddened a deletion guard on 2026-09-23.

## R9. Upstream contributions to VSS

Ordered so that the earliest contributions ask the least of VSS reviewers:

1. **Defect reports with patches:**
   - The README NVFP4 recipe fails at boot because of the allowlist variable name (E13).
   - The RT-VLM live-alert substring trigger ([`09`](09-audit-integration-surfaces.md) §5).
   - `dev-profile.sh` requires `NGC_CLI_API_KEY` even for all-remote deployments
     ([`08`](08-audit-profile-anatomy.md) §0).
2. **Expose RT-VLM's fixed-KV knobs in compose:** `RTVI_VLLM_KV_CACHE_MEMORY_BYTES`, the KV dtype,
   and eager mode ([`08`](08-audit-profile-anatomy.md) §2.6).
3. **Wire sleep and unload in RT-VLM.** VSS model services have no unload path.
4. **A consumer hardware tier on the `base` Foundation:**

   - naming `RTX4090` / `RTX5090`, or a VRAM-class alias;
   - roughly 39 files per the checklist in [`08`](08-audit-profile-anatomy.md) §1.7;
   - helm parity enforced in CI;
   - the three dormant RTX 4090 runners as CI hardware (E17).

   The design's Delta build (M4) is the downstream prototype.

Before item 4, ask the VSS team which kind of "not on the roadmap" applies (no headcount, judged
against, or not considered); [`05`](05-hardware-profiles.md) explains why the answer changes the
first move.

## R10. Final model choices

**Reasoning LLM (owner).** The owner reports that **Nemotron 3.5 Lightning replaced the Nano line**.
`NVIDIA-Nemotron-3-Nano-4B` is only the interim placeholder. Facts about Lightning, gathered
2026-09-23:

| Property                       | Value                                                                             | Marker                     |
| ------------------------------ | --------------------------------------------------------------------------------- | -------------------------- |
| Available sizes                | Only 30B-A3B                                                                      | [E]                        |
| Official formats               | BF16, and NVFP4 at 20.08 GiB                                                      | [E]                        |
| ggml-org GGUF                  | Q4_0, 17.60 GiB; architecture `nemotron_h_moe`, which llama.cpp `b7972` registers | [E]                        |
| Block layout                   | 23 Mamba + 23 MoE + 6 attention blocks                                            | [E]                        |
| KV cost                        | 3.19 KiB/token                                                                    | [C]                        |
| Routed-expert share of weights | ~93%                                                                              | [C]                        |
| With full expert offload       | ~2.7 GiB on GPU, ~16.4 GiB in system RAM                                          | [C]; throughput unmeasured |

Under the design, the per-event path uses **no separate text LLM**. A text LLM returns only for
the R4 features, and the chosen VLM may serve them too.

**VLM.** The candidates are Nemotron-Nano-12B-v2-VL, Qwen3-VL-4B/8B and Cosmos3-Edge-4B. The
design's bake-off produces the evidence; the owner picks at M2.

## R11. Tiers beyond 24 GB

| Tier                               | Open questions                                                                                                                              |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **Halo (32 GB, RTX 5090, sm_120)** | Does NVFP4 compute natively rather than dequantizing ([`03`](03-open-questions.md) Q1)? Does the Lightning NIM's ≥32 GB floor admit a 5090? |
| **Volume (12-16 GB)**              | Does a 4B VLM plus the detector fit and meet S2-S4?                                                                                         |
| **Entry (8 GB)**                   | Detection plus remote reasoning.                                                                                                            |

All three need hardware beyond the A5500. The procurement request has the longest lead time of
any item here.

## R12-R14. Distribution prerequisites

These must be settled before any consumer distribution. None of them blocks the design.

- **R12, licensing:** model licenses (the Nemotron Open Model License, the NVIDIA Open Model
  License, Apache-2.0 Qwen); VSS microservices ship under an Evaluation license; SLA §8.9 bars
  publishing benchmarks; image redistribution. These are legal questions.
- **R13, biometrics:** ArcFace templates and plate text have no retention clock, consent record
  or erasure path. This is a product-shape decision.
- **R14, version pinning:** VSS restructures often and removes old NGC images on a schedule. Mirror
  the images you depend on, and budget for re-integration at each release.
