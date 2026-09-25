# 10 — Audit: VSS Feature Inventory and Gap Analysis

> **Provenance.** Independent read-only audit by a research subagent ("Auditor C") on
> 2026-09-23, against VSS `1e94133b4` (`origin/develop`; 78 commits after the `cdad5cc0e`
> baseline that docs 00-07 cite). Scope: user-facing VSS features vs this product; ranked import list; our differentiators. Evidence markers follow [`AGENTS.md`](AGENTS.md).
> Corrections it raises against docs 00-07 are consolidated in
> [`11-errata-2026-09-23.md`](11-errata-2026-09-23.md). The design it fed is
> [`2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md).
> Line citations resolve at `1e94133b4`; VSS moves fast, so re-verify before relying on one.

**Question:** what features do we gain by incorporating VSS technology into this platform, and which can we import?

**Versions audited:**

- VSS `origin/develop` = `1e94133b4` (2026-09-23, VSS 3.3.0 docs).
- Our repo: `feat/vss-gaming-gpu-profile` @ `4eab98e5`.

**Scope:** the unit of analysis is the user-visible feature. Contract-level detail (APIs, env vars, schemas, bus, BYOM) belongs to Auditor B (`09-audit-integration-surfaces.md`, cited as **B§n**). This report cross-checks against B in §10.

**Method:**

- Four read-only sub-agent slices, plus direct reading and verification by the author:
  - A: VLM, summarization, audio, alerts
  - B: search, agent, MCP, UI
  - C: perception, analytics, VIOS, profiles
  - D: our product
- About 70 load-bearing citations were re-read personally (Appendix A).
- External read-only queries are listed in Appendix B.

## Conventions

**Path prefixes:**

- `v:` means a path in the VSS worktree.
- `o:` means a path in our repo.
- `docs/vss-integration/` is cited as `vi/NN`.

**Evidence tags:**

| Tag     | Meaning                                |
| ------- | -------------------------------------- |
| **[V]** | Read in-session, with `path:line`      |
| **[C]** | Computed; formula shown                |
| **[E]** | External; command or URL in Appendix B |
| **[?]** | Open                                   |
| **[A]** | Inferred, not verified                 |

**GPU budgets** use VSS's 0.85 rule (`v:skills/vss-build-vision-ai/references/sizing.md:56-58` **[V]**):

| Card  | Budget  |
| ----- | ------- |
| 32 GB | 27.2 GB |
| 24 GB | 20.4 GB |
| 16 GB | 13.6 GB |
| 12 GB | 10.2 GB |

Shorthand used below: "24✓" means the feature fits a 24 GB card's 20.4 GB budget.

---

## 1. The answer on one page

**What VSS adds is a pixel-grounded second opinion. It does not add a better pipeline.**

- Our pipeline turns pixels into text (YOLO26, enrichment, Florence-2 on ambiguous crops) and lets a text-only LLM grade risk.
- VSS's highest-value capability for a home product is **a VLM that looks at the actual evidence and returns confirmed/rejected with reasoning**. VSS markets this "to reduce false positives" (`v:README.md:46`; `v:docs/agent-workflow-alert-verification.mdx:31` **[V]**).
- That capability is exactly the home-security problem.
- Everything else VSS offers is either:
  - a UX layer on top of that VLM (Q&A, reports, natural-language rules, semantic search); or
  - datacenter/industrial machinery we should not import: Kafka/Elasticsearch/Logstash, VIOS recording, DeepStream multi-stream, 3D, SOP, smart city, warehouse.

**The three facts that shape every recommendation:**

1. **VSS is video- and stream-first.**
   - Only three VSS surfaces accept still images:
     - RT-VLM (`media_type: "image"`, JPEG/PNG; `v:docs/real-time-vlm.mdx:125-140` **[V]**);
     - the Alert Bridge on-demand route (`v:skills/operations/vss-manage-alerts/references/on-demand-verification.md:12-22` **[V]**);
     - RT-Embed (JPEG/PNG padded to 8 frames, **[V]** via slice B `v:docs/real-time-embedding.mdx:19,43-44`).
   - Nothing else does:
     - RT-CV, VIOS, behavior analytics and search ingest have no still path (§2.1).
     - LVS is `MediaType.VIDEO` only (`v:services/video-summarization/src/vss_api_models.py:120-123` **[V]**).
     - FTP appears nowhere in VSS (0 grep hits, slice C **[V]**).
2. **On one 24 GB card, every VLM feature displaces our current LLM.**
   - Our Nemotron-3-Nano-30B-A3B Q4_K_M is budgeted at 21,700 MB (`o:backend/services/model_zoo.py:36` **[V]**).
   - With YOLO26 that is 22.35 GB against a 20.4 GB budget **[C]**: 21.7 + 0.65 > 20.4.
   - Today's production is **two GPUs**: the LLM on GPU 0 (A5500) and AI services on GPU 1 (A400) (`o:docker-compose.prod.yml:139,153,159,322-323,351` **[V]**).
   - So a single-card VSS tier needs either:
     - a one-VL-model topology; or
     - a VLM plus a ~4B text LLM; or
     - duty-cycled model swapping (§2.2).
3. **VSS's VLM-verification _service_ has no lean variant. Its VLM _engine_ does.**
   - As of 3.3.0, Alert Bridge is Kafka-only and Elasticsearch-backed (`v:docs/release-notes.mdx:32-42` **[V]**; compose `depends_on` both, `v:deploy/docker/services/alert/compose.yml:105-110` **[V]**).
   - RT-VLM runs with no bus at all (`MESSAGE_BUS` empty; `v:docs/real-time-vlm.mdx:1490` **[V]**; B§1c).
   - Import the **pattern and the engine**, not the alert service.

**Top imports**, ranked by (value × feasibility) ÷ infrastructure cost (§7):

| Rank | Import                                         | Score |
| ---- | ---------------------------------------------- | ----- |
| 1    | VLM verification gate on candidate events      | 20    |
| 2    | VLM scene and clip descriptions                | 16    |
| 3    | Natural-language per-camera alert rules        | 16    |
| 4    | Incident report generation                     | 12    |
| 5    | MCP tool surface over our events               | 10    |
| 6    | Lean natural-language search with a VLM critic | 8     |
| 7    | Chat / Q&A over events                         | 4.5   |
| 8    | Open-vocabulary prompt detection               | 4.5   |

Items 1-3 share one VLM engine.

**Traps** (§8): VSS search as shipped, real-time VLM alerts, live-stream summarization, VIOS recording, the LVS service, behavior analytics on stills, Omni audio on any consumer card, and the 3D, SOP and smart-city verticals.

---

## 2. Load-bearing facts

### 2.1 Input modality: what accepts what

| VSS surface                               | Stills (FTP JPEG)                                      | Uploaded clip                 | RTSP                                      | Evidence                                                                                                        |
| ----------------------------------------- | ------------------------------------------------------ | ----------------------------- | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| RT-VLM captions / Q&A                     | **Yes** (JPEG/PNG, `media_type:image`)                 | Yes (H.264/H.265/AV1/VP8/VP9) | Yes                                       | `v:docs/real-time-vlm.mdx:125-140` **[V]**                                                                      |
| RT-VLM reading our FTP directory directly | `file://` only if `FILE_URL_ALLOWED_DIRS` is set       | same                          | —                                         | `v:docs/real-time-vlm.mdx:992-996` **[V]**                                                                      |
| Alert Bridge on-demand verification       | **Yes** (`media_type` `image` or `video`, ≤5 media)    | Yes                           | —                                         | `v:.../on-demand-verification.md:12-22` **[V]**; `v:services/alert/config.yaml:300` **[V]**                     |
| Alert verification (2d_cv) stock path     | No (clip resolved from VIOS by sensor and time)        | via VIOS                      | Yes                                       | `v:docs/release-notes.mdx:46-48` **[V]**                                                                        |
| Real-time VLM alerts (2d_vlm)             | No                                                     | No                            | **Required** (`live_stream_url` required) | `v:docs/agent-workflow-rt-alert.mdx:154` **[V]**                                                                |
| LVS summarization                         | **No** (`MediaType.VIDEO` only)                        | Yes                           | Live needs Kafka                          | `v:services/video-summarization/src/vss_api_models.py:120-123` **[V]**; `v:.../via_server.py:1031-1036` **[V]** |
| RT-CV detection and tracking              | No (0 still-path hits)                                 | Yes (file/URL video)          | Yes                                       | `v:docs/object-detection-tracking.mdx:96-100` **[V]**; slice C grep **[V]**                                     |
| Behavior analytics                        | No (needs continuous tracks; gap > 0.5 s closes a run) | Only if tracked               | Yes                                       | `v:docs/behavior-analytics.mdx:270-281` **[V]**                                                                 |
| Search ingest                             | No (upload is `video/mp4`, `video/x-matroska` only)    | Yes                           | Yes                                       | slice B `v:services/agent/.../video_search_ingest.py:57-59` **[V]**                                             |
| VIOS recording and upload                 | No (H.264/H.265 only)                                  | Yes                           | Yes                                       | `v:docs/vios-microservices.mdx:595` **[V]**                                                                     |

**Our side:**

- Ingest is the FTP drop folder: `.jpg/.jpeg/.png` and `.mp4/.mkv/.avi/.mov` (`o:backend/services/file_watcher.py:68-71` **[V]**).
- An RTSP `StreamManager` exists (`o:backend/services/stream_manager.py:1-19` **[V]**), and so does an `IngestionMode.RTSP/ONVIF` enum (`o:backend/models/enums.py:100-102` **[V]**).
- But the manager has **no runtime importer** beyond the package re-export (`o:backend/services/__init__.py:341` **[V]**, grep).
- go2rtc serves viewing only (B§10 item 17). The owner's framing holds in practice: no RTSP feed reaches the AI pipeline.

### 2.2 Consumer-GPU arithmetic (VSS rule: blob × 1.3 ≤ 0.85 × VRAM)

The blob sizes below are HF safetensors totals **[E]**. `+Y` means adding YOLO26 at 0.65 GB (`o:backend/services/model_zoo.py:37` **[V]**).

| Candidate                                               | Gate                           |     Blob GB |               ×1.3 **[C]** |    +Y | 32  |  24   | 16  | 12  |
| ------------------------------------------------------- | ------------------------------ | ----------: | -------------------------: | ----: | :-: | :---: | :-: | :-: |
| Nemotron-Nano-12B-v2-VL-NVFP4-QAD                       | ungated                        |       10.60 |                      13.78 | 14.43 |  ✓  |   ✓   |  ✗  |  ✗  |
| Cosmos3-Edge                                            | ungated                        |        9.13 |                      11.87 | 12.52 |  ✓  |   ✓   |  ✓  |  ✗  |
| Qwen3-VL-8B-Instruct-FP8                                | ungated                        |       10.59 |                      13.77 | 14.42 |  ✓  |   ✓   |  ✗  |  ✗  |
| Qwen3-VL-4B-Instruct (BF16)                             | ungated                        |        8.88 |                      11.54 | 12.19 |  ✓  |   ✓   |  ✓  |  ✗  |
| Qwen3-VL-4B-FP8 (per B§1e)                              | ungated                        |        6.02 |                       7.83 |  8.48 |  ✓  |   ✓   |  ✓  |  ✓  |
| Nemotron-12B-VL GGUF Q4_K_M + mmproj (community, per B) | ungated                        |        9.19 |                      11.95 | 12.60 |  ✓  |   ✓   |  ✓  |  ✗  |
| Cosmos-Reason2-2B                                       | `gated:"auto"` (click-through) |        4.88 |                       6.34 |  6.99 |  ✓  |   ✓   |  ✓  |  ✓  |
| Nemotron-3-Nano-Omni-30B-A3B NVFP4 (audio)              | ungated                        |       22.41 |                      29.13 | 29.78 |  ✗  |   ✗   |  ✗  |  ✗  |
| Nemotron-3-Nano-Omni-30B-A3B FP8 (audio)                | ungated                        |       35.19 |                      45.75 |     — |  ✗  |   ✗   |  ✗  |  ✗  |
| RT-Embed "reserve about 10 GB" (planning reserve)       | Cosmos-Embed1 ungated          | 2.39 / 4.79 |               10 (reserve) | 10.65 |  ✓  |   ✓   |  ✓  |  ✗  |
| **Our LLM today:** Nemotron-3-Nano-30B-A3B Q4_K_M       | —                              |           — | 21.7 (`o:model_zoo.py:36`) | 22.35 |  ✓  | **✗** |  ✗  |  ✗  |

Notes on the rows:

- RT-Embed reserve: `v:sizing.md:290-291` **[V]**.
- Cosmos-Embed1 blobs: 448p is 2.39 GB, anomaly-detection is 4.79 GB **[E]**.

**Combinations [C]:**

- Any VLM + Y + our 30B LLM is 28.7-36.1 GB. That is ✗ on 24 GB and ✗ on 32 GB, except Cosmos-Reason2-2B at 28.69, which is also ✗ on 32 GB.
- VLM + Y + a 4B text LLM, using NVIDIA-Nemotron-3-Nano-4B-FP8 (blob 5.27 **[E]** × 1.3 = 6.85):
  - Cosmos3-Edge: 19.37 (24✓)
  - 12B-VL NVFP4: 21.28 (24✗)
  - Qwen3-VL-4B-FP8: 15.33 (24✓, 16✗)
- VLM + Y + RT-Embed (10): 12B-VL = 24.43 (24✗, 32✓). This is why VSS-native search plus a VLM does not fit a 24 GB card.

**Kernel caveats for the A5500 (sm_86):**

- VSS contradicts itself about NVFP4:
  - "requires FP4-capable (Blackwell-class) hardware" (`v:skills/vss-build-vision-ai/references/services/rt-vlm.md:56-58` **[V]**);
  - "On NVIDIA Jetson Orin NX (16 GB), only the Cosmos3 Nano Reasoner (modelopt-nvfp4) variant is supported" (`v:docs/real-time-vlm.mdx:92` **[V]**). Orin is an Ampere-generation GPU.
- `modelopt-fp8` is "not supported on NVIDIA A100" (`:93` **[V]**), so FP8 on sm_86 is doubtful **[A]**.
- BF16 or GGUF paths avoid the question.

**Residency:**

- RT-VLM reserves memory at vLLM engine init; changing it requires a restart (`v:docs/real-time-vlm.mdx:1535-1536` **[V]**).
- A blank utilization value is read as a **dedicated 0.7** (`v:sizing.md:183-186` **[V]**), which is 16.8 GB on 24 GB **[C]**.
- No VSS model service has an unload path (B§1f).
- llama.cpp has `--sleep-idle-seconds` and a router `--models-max`/unload **[E]** (llama.cpp `tools/server/README.md`; scratchpad copy lines 227-229, 244; B headline 3).

### 2.3 Infrastructure gravity by feature family

Developer-profile comparison (`v:docs/vss-agent/VSS-Agent-Profiles.mdx:162-173` **[V]**; columns: base | lvs | search | alerts):

| Feature (VSS row)                         | base  | lvs | search |   alerts   |
| ----------------------------------------- | :---: | :-: | :----: | :--------: |
| Video Analysis (VLM), Report Generation   |   ✓   |  ✓  |   ✓    |     ✓      |
| Live Stream Captioning                    |   ✗   |  ✓  |   ✗    | ✓ (2d_vlm) |
| Semantic Search                           |   ✗   |  ✗  |   ✓    |     ✗      |
| Alert Verification / Real-Time VLM Alerts |   ✗   |  ✗  |   ✗    |     ✓      |
| **Elasticsearch Required**                | **✗** |  ✓  |   ✓    |     ✓      |
| **Kafka Required**                        | **✗** |  ✓  |   ✓    |     ✓      |

- Only `base` (VLM Q&A plus reports) is free of ES and Kafka.
- The stock alerts profile is about 25 services (`v:skills/vss-build-vision-ai/references/profiles/alerts.md:19`, per B§5c).
- JVM heap alone is about 8 GB **[C]**: Kafka 6 + Logstash 1 + ES 1 (`v:deploy/docker/services/infra/compose.yml:181,292,119`, B§7 **[V]**).
- The one lean VSS profile is the warehouse `COMPOSE_PROFILES_WH_REDIS_2D_MINIMAL` ("no ELK…") (`v:deploy/docker/industry-profiles/warehouse-operations/overrides.env:294-296` **[V]**). It is warehouse perception only.
- **ES retention defaults are hours, not days:**
  - every `mdx-*` ILM policy is 4 hours (`v:docs/elk.mdx:217-232` **[V]**);
  - search embeddings expire at 48 h (`v:docs/agent-workflow-search.mdx:727-730` **[V]**);
  - ours is 30 days (`o:backend/core/config.py:959-963` **[V]**).

### 2.4 Gating

| Artifact                                                                                                                                                                                                                                 | Access                                                                                                                 | Evidence                                                                                                                                             |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| All 17 first-party `build` images on `ghcr.io/nvidia-ai-blueprints/vss/*`: agent, UI, alert-ms, VA-API, behavior-analytics, video-summarization, rt-vlm, rt-embed, rt-cv, 4× VIOS, configurator, rt-config-adaptor, bev-fusion, sdr-mw-l | **Anonymous**, `develop-*` tags only in the first 200 listed                                                           | **[E]** tag list with anonymous token; default registry `v:deploy/docker/containers.env:55` **[V]**; "pre-release … AS IS" `v:README.md:105` **[V]** |
| Mirror images: reid-embed, video-analytics-ui, auto-calibration(-ui), calibration                                                                                                                                                        | **NGC 401 anonymous**; `nvstaging` likely internal-only                                                                | **[E]**; `v:containers.env:130-175` **[V]**                                                                                                          |
| Default VLM `ngc:nim/nvidia/cosmos3-nano-reasoner:bf16-final`; `nvcr.io/nim/nvidia/cosmos3-nano-reasoner`                                                                                                                                | **NGC-entitled** (401)                                                                                                 | `v:docs/real-time-vlm.mdx:74,89` **[V]**; **[E]**                                                                                                    |
| LLM NIM `nemotron-3.5-lightning-30b-a3b`                                                                                                                                                                                                 | Tag list anonymous (200), but runtime NGC key plus "NVIDIA AI Enterprise developer licence required to local host NIM" | **[E]**; `v:README.md:99` **[V]**; B§4d                                                                                                              |
| RT-CV detector weights (TAO: trafficcamnet, mask_grounding_dino, reidentificationnet)                                                                                                                                                    | NGC CLI download; anonymous access **[?]**                                                                             | slice C `v:deploy/docker/services/rtvi/rtvi-cv/download-models.sh:125` **[V]**                                                                       |
| HF models: Cosmos-Embed1 (all variants), Nemotron-12B-VL-NVFP4, Omni-30B FP8/NVFP4, Cosmos3-Edge, Nemotron-3-Nano-4B-FP8, Qwen3-VL                                                                                                       | `gated: false`                                                                                                         | **[E]**                                                                                                                                              |
| HF Cosmos-Reason2-2B / 8B                                                                                                                                                                                                                | `gated: "auto"` (click-through, token needed)                                                                          | **[E]**                                                                                                                                              |
| HF Cosmos3-Nano-Reasoner / Super                                                                                                                                                                                                         | 401 (not public)                                                                                                       | **[E]**                                                                                                                                              |

**VSS docs overstate gating.** They call Nemotron Omni "gated" (`v:docs/prerequisites.mdx:293` **[V]**) and Cosmos-Embed1 "gated" (slice B, `v:docs/real-time-embedding.mdx:290`). HF says `gated:false` for both **[E]**.

---

## 3. VSS feature inventory

Each row gives:

- **(a)** what the user gets;
- **(b)** components and infrastructure;
- **(c)** documented GPU minimum → consumer fit (§2.2);
- **(d)** stills/clips vs stream;
- **(e)** maturity;
- **(f)** gating (§2.4).

Items marked **[V]** were read in-session; "sA/sB/sC" marks which slice read the citation; unmarked **[V]** items were read or re-read by the author (Appendix A).

### 3.0 Summary table

Citations for every cell are in the per-feature entries (3A-3E) below. Key:

- ✓/✗: supported / not supported.
- "–": not applicable.
- "Fit 24" means the feature fits a 24 GB card beside YOLO26, per the §2.2 arithmetic **[C]**.

| ID     | Feature                                     |    Stills    |    Clips     |    Needs RTSP     | Kafka / ES needed               | Fit 24 (beside detector)           | Maturity                                | Gating                                                 |
| ------ | ------------------------------------------- | :----------: | :----------: | :---------------: | ------------------------------- | ---------------------------------- | --------------------------------------- | ------------------------------------------------------ |
| F1     | VLM captions / visual Q&A (RT-VLM)          |      ✓       |      ✓       |         –         | none (bus optional)             | ✓ only if the 30B LLM is displaced | shipped                                 | anon image; NGC default model; HF-ungated alternatives |
| F2     | Live RTSP captioning                        |      ✗       |      ✗       |         ✓         | bus optional                    | as F1, continuous load             | shipped                                 | as F1                                                  |
| F3     | Prompt-triggered VLM incidents              |      ✓       |      ✓       |         –         | Kafka for incidents             | as F1                              | shipped (substring trigger)             | as F1                                                  |
| F4     | Constrained output (choice / json_schema)   |      ✓       |      ✓       |         –         | none                            | –                                  | code-only                               | –                                                      |
| F5     | Reasoning traces                            |      ✓       |      ✓       |         –         | none                            | –                                  | shipped                                 | –                                                      |
| F6     | EVS / EVS++ token pruning                   |      ✗       |      ✓       |         –         | none                            | lowers compute                     | shipped, opt-in                         | –                                                      |
| F7     | Alert verification (2d_cv)                  |      ✗       |   via VIOS   |       stock       | **Kafka + ES**                  | ✗ as shipped (2 GPUs)              | GA 3.2                                  | anon images; NGC VLM                                   |
| F8     | On-demand image/clip verification           |      ✓       |      ✓       |         –         | **Kafka + ES**                  | VLM only                           | shipped                                 | as F7                                                  |
| F9     | Contextualize / classify / per-type prompts |  ✓ (via F8)  |      ✓       |         –         | **Kafka + ES**                  | VLM only                           | shipped                                 | as F7                                                  |
| F10    | Real-time VLM alert rules (2d_vlm)          |      ✗       |      ✗       |         ✓         | **Kafka + ES** + VIOS           | ✗ (H100 ×2)                        | shipped                                 | as F7                                                  |
| F11    | Incident consolidation                      |      –       |      –       |         ✓         | ES                              | –                                  | new, API-only                           | –                                                      |
| F12    | Webhook → Slack/OpenClaw relay              |      –       |      –       |         –         | Kafka                           | –                                  | skill, Early Access                     | anon                                                   |
| F13    | LVS file summarization                      |      ✗       |      ✓       |         –         | ES (+Kafka in stock)            | ✗ with default LLM (≈45 GB INT4)   | shipped                                 | anon image                                             |
| F14    | Live-stream summarization                   |      ✗       |      ✗       |         ✓         | **Kafka + ES**                  | ✗                                  | Early Access                            | –                                                      |
| F15    | LVS Q&A over assets                         |      ✗       |      ✓       |         –         | graph DB, self-operated         | –                                  | shipped, heavy                          | –                                                      |
| F16    | Omni audio understanding                    |      ✗       |  ✓ (audio)   |         –         | none                            | **✗ on any consumer card**         | sanity-tested only                      | HF ungated                                             |
| F17    | Natural-language video search               |      ✗       |      ✓       |         –         | **Kafka + ES**                  | ✗ with VLM critic (24.4 GB)        | **alpha**                               | anon; HF-ungated embed model                           |
| F18    | Search by image                             |      ✗       |      ✓       |         –         | **Kafka + ES**                  | ✗                                  | alpha                                   | mixed                                                  |
| F19    | Critic (VLM re-verifies results)            |      –       |      ✓       |         –         | via search                      | VLM                                | on by default                           | NGC default VLM                                        |
| F20    | VLM tag / BM25 search                       |      ✗       |      ✗       |         ✓         | **Kafka + ES**                  | –                                  | design draft                            | –                                                      |
| F21    | Chat / visual Q&A (base agent)              | API ✓ / UI ✗ |      ✓       |         –         | **none**                        | ✓ with our LLM (default LLM ✗)     | shipped                                 | anon agent; NGC LLM NIM                                |
| F22    | Report generation (Markdown/PDF)            |      –       |      ✓       |         –         | none (Mode A) / ES (Mode B)     | as F21                             | shipped (in-memory)                     | as F21                                                 |
| F23    | Human-in-the-loop prompts                   |      –       |      –       |         –         | none                            | –                                  | shipped                                 | –                                                      |
| F24    | Incident / analytics chat                   |      –       |      –       |         –         | ES                              | –                                  | shipped (verticals)                     | –                                                      |
| F25    | Video Analytics MCP                         |      –       |      –       |         –         | ES                              | no GPU                             | shipped, **no auth**                    | anon                                                   |
| F26    | Unified memory / introspection              |      –       |      –       |         –         | ES (skill); in-memory (library) | –                                  | Early Access                            | –                                                      |
| F27    | Skills / harnesses / CLI                    |      –       |      –       |         –         | –                               | –                                  | Early Access (dev tooling)              | anon                                                   |
| F28    | Reference UI                                |      ✗       |      ✓       |         ✓         | ES for Dashboard tab            | –                                  | shipped                                 | anon                                                   |
| F29    | RT-CV detection + tracking                  |      ✗       |      ✓       |         –         | Kafka default (optional)        | VRAM likely ✓; compute [?]         | shipped                                 | anon image; NGC TAO weights [?]                        |
| F30    | Open-vocabulary GDINO                       |      ✗       |      ✓       |         –         | as F29                          | heaviest compute                   | shipped                                 | NGC TAO weights                                        |
| F31    | Object embeddings / re-ID                   |      ✗       |      ✓       |         –         | as F29                          | inside RT-CV                       | shipped                                 | NGC                                                    |
| F32    | Behavior analytics                          |      ✗       | tracked only |         –         | Kafka/Redis/MQTT input          | CPU                                | shipped                                 | anon                                                   |
| F33    | Occupancy / counting                        |      ✗       |      –       |         ✓         | ES                              | CPU                                | shipped                                 | anon                                                   |
| F34    | Anomaly (traffic; fall-risk)                |      ✗       |      –       |         ✓         | broker                          | CPU                                | traffic shipped; fall-risk experimental | –                                                      |
| F35    | Multi-camera 3D (MV3DT)                     |      ✗       |      ✗       | ✓ (30 FPS synced) | Kafka + MQTT                    | <2 GB                              | new in 3.2                              | NGC mirror                                             |
| F36    | Calibration                                 | ✓ (toolkit)  |      ✓       |         –         | –                               | CPU                                | legacy / warehouse                      | NGC (401)                                              |
| F37    | VIOS record / replay / ONVIF                |      ✗       |      ✓       |         –         | Postgres + Redis (own)          | NVDEC                              | shipped                                 | anon                                                   |
| F38    | Kibana dashboards                           |      –       |      –       |         –         | ELK                             | CPU                                | shipped                                 | public                                                 |
| F39    | Configurators                               |      –       |      –       |         –         | –                               | –                                  | shipped                                 | anon                                                   |
| F40    | SOP compliance                              |      ✗       |      ✓       |         –         | ELK + Kafka + VIOS              | VLM slot                           | skill delta                             | –                                                      |
| F41-43 | Smart city / warehouse / public safety      |      ✗       |      –       |         ✓         | full stack                      | multi-GPU                          | 2 in-repo; public safety NGC-only       | public safety via NGC                                  |
| F44    | Observability                               |      –       |      –       |         –         | –                               | –                                  | shipped                                 | public                                                 |
| F45    | Hardware / edge profiles                    |      –       |      –       |         –         | –                               | no GeForce row                     | `OTHER` experimental                    | –                                                      |

### 3A. VLM understanding and alerting

#### F1. Dense captions and visual Q&A on files and stills (RT-VLM standalone)

**(a) What the user gets:**

- Prompt-driven captions per chunk with timestamps, via `chunk_duration` (`v:docs/real-time-vlm.mdx:452-489` **[V]**).
- OpenAI-style chat on a file, image URL or data URL, plus multi-turn text chat (sA `:858-970`; `v:docs/release-notes.mdx:288`).

**(b) Components and infrastructure:**

- The RT-VLM container only. `MESSAGE_BUS` empty disables output (`:1490` **[V]**).
- The standalone compose `depends_on` kafka and redis, so it needs an override (sA `v:services/rtvi/rt-vlm/docker/compose.yaml:189-191`).
- It starts a CUDA MPS daemon and needs `runtime: nvidia` (B§1c).

**(c) GPU:**

- No consumer row. The smallest documented dedicated card is the RTX PRO 4500 at 0.80 (`v:sizing.md:171` **[V]**).
- The default CR3 Nano BF16 footprint "not revalidated" (`:82-84` **[V]**).
- Ungated VLMs fit 24✓/16✓ solo (§2.2), but **not beside our 30B LLM**.

**(d) Input:** **stills yes** (`:125-140` **[V]**); clips yes.

**(e) Maturity:**

- Shipped and documented.
- Validated GPUs exclude consumer cards (sA `:218-228`).
- The `OTHER` hardware profile is "experimental" (sC `v:docs/prerequisites.mdx:21`).

**(f) Gating:** image anonymous; default model NGC; HF-ungated alternatives exist.

#### F2. Live RTSP captioning (SSE/Kafka)

- **(a)** Continuous per-chunk captions; shared RTSP decode (`v:docs/real-time-vlm.mdx:23-30` **[V]**).
- **(b)** RT-VLM plus VIOS or another stream source.
- **(c)** "Continuous VLM inference needs more headroom" (`v:sizing.md:108` **[V]**). Same footprint as F1, but always busy.
- **(d)** **RTSP required.**
- **(e)** Shipped.
- **(f)** As F1.

#### F3. Prompt-triggered VLM incidents (yes/no prompt + `alert_category`)

- **(a)** A per-chunk yes/no prompt emits an Incident.
- **(b)** Incidents go to Kafka (sA `:1098-1101`).
- **(c)** As F1.
- **(d)** Files or streams.
- **(e)** Shipped, but the trigger is a **substring match on "yes"/"true"** (`:1204-1207` **[V]**). A known issue is that spurious `mdx-vlm-incidents-1970-01-01` records appear (`v:docs/release-notes.mdx:123` **[V]**).
- **(f)** As F1.

#### F4. Constrained output (`choice`, `json_schema`, `json_object`)

- **(a)** A guaranteed-parseable verdict or JSON.
- **(b)** RT-VLM integrated mode only; not openai-compat (B§1).
- **(c)** None.
- **(d)** Any input.
- **(e)** **Code-only**: `ResponseType` (`v:services/rtvi/rt-vlm/src/api_models/captions.py:100-106` **[V]**). It is absent from the `.mdx` docs (sA grep).
- **(f)** —

#### F5. Reasoning traces (`enable_reasoning`)

- **(a)** A `reasoning_description` for each chunk and incident.
- **(b)** RT-VLM.
- **(c)** None.
- **(d)** Any input.
- **(e)** Shipped (sA `v:docs/release-notes.mdx:279-283`).
- **(f)** —

#### F6. EVS / EVS++ visual-token pruning

- **(a)** About 47% fewer tokens: 26.7 s → 14.2 s per 30 s chunk on Nemotron 12B VL (`v:services/rtvi/rt-vlm/README.md:795-800` **[V]**).
- **(b)** RT-VLM (`v:docs/real-time-vlm.mdx:1468-1472` **[V]**).
- **(c)** Reduces compute.
- **(d)** **Video only.** No value for stills **[A]**.
- **(e)** Shipped and opt-in. EVS++ is Qwen3-VL-architecture only (sA `:1758-1763`).
- **(f)** —

#### F7. Alert verification (`2d_cv`): CV + rules candidate → VLM verdict

**(a) What the user gets:**

- The detector plus behavior rules raise candidates.
- The VLM reviews the clip "to reduce false positives" (`v:docs/agent-workflow-alert-verification.mdx:8,31` **[V]**).
- The verdict is confirmed/rejected/unverified plus a reasoning trace (sA `v:docs/alert-verification-service.mdx:30`; `v:docs/index.mdx:39` **[V]**).

**(b) Components and infrastructure:**

- RT-CV (GDINO), behavior analytics, Alert Bridge, RT-VLM, VIOS, **Kafka + ES** (`v:release-notes.mdx:32-42` **[V]**).
- About 25 services (B§5c).

**(c) GPU:**

- H100: **2 GPUs shared** (`v:docs/prerequisites.mdx:339` **[V]**).
- RTX PRO 4500: **2 GPUs** with a remote LLM (`:379` **[V]**).
- The benchmark used one GPU for CV and one for the VLM (`v:docs/performance-alert-verification.mdx:110-113` **[V]**).
- On a consumer card it fits only as a pattern (see F8).

**(d) Input:** stock clips come from VIOS (`v:release-notes.mdx:46-48` **[V]**).

**(e) Maturity:**

- Shipped in the 3.2 GA (`:151-158` **[V]**).
- Known issues: a valid "rejected" can be stored as `verification-failed`, and clips can be only a few seconds long (sA `:987,997`).

**(f) Gating:** anonymous images; NGC default VLM.

#### F8. On-demand verification of image or clip URLs

- **(a)** `POST /api/v1/verification/ondemand` with `category` and `media_urls` (`media_type` image or video), returning **202 async** (`v:.../on-demand-verification.md:12-33` **[V]**). At most 5 media per request (`v:services/alert/config.yaml:300` **[V]**).
- **(b)** Alert Bridge, which still needs **Kafka + ES** (`v:deploy/docker/services/alert/compose.yml:105-110` **[V]**). The result goes to ES, not to the HTTP response (B "Looks reusable").
- **(c)** The VLM only.
- **(d)** **Stills yes.**
- **(e)** Shipped (`v:release-notes.mdx:176-177` **[V]**).
- **(f)** As F7.

#### F9. Contextualization, N-way classification, enrichment, runtime per-alert-type prompts, custom parser

- **(a)** Verification can return yes/no, extra context, or a class (`v:release-notes.mdx:153-157` **[V]**). Prompts and VLM parameters per alert type can be changed at runtime through `PUT /api/v1/verification/config/{alert_type}` (`:39-42` **[V]**).
- **(b)** Alert Bridge + ES.
- **(c)** VLM.
- **(d)** Stills via F8.
- **(e)** Shipped.
- **(f)** As F7.

#### F10. Real-time VLM alert rules on streams (`2d_vlm`), plus "always-on" auto-attach and rule replay

- **(a)** A natural-language condition is evaluated on every chunk of a stream. "Always-on" means rules from a file are auto-attached to each newly added stream (`v:docs/alert-verification-service.mdx:76` **[V]**; `v:release-notes.mdx:161,170-173` **[V]**).
- **(b)** Alert Bridge, RT-VLM, VIOS, Kafka, Logstash, ES.
- **(c)** H100: 2 shared GPUs, **no remote-VLM option** (`v:prerequisites.mdx:340` **[V]**).
- **(d)** **RTSP required** (`v:docs/agent-workflow-rt-alert.mdx:154` **[V]**).
- **(e)** Shipped. Known issue: "Generated text is empty" (sA `:934`).
- **(f)** As F7.

#### F11. Incident consolidation

- **(a)** Consecutive confirmed chunks are grouped into one event when read (`v:docs/alert-verification-service.mdx:74` **[V]**).
- **(b)** ES.
- **(c)** —
- **(d)** Realtime path only.
- **(e)** New (API-only).
- **(f)** —

#### F12. Alert notification relay (webhook → Slack/OpenClaw)

- **(a)** A POST on each VLM-verified incident.
- **(b)** A **Kafka consumer**. Off by default. "No retry / no queue / no dead-letter" (`v:services/alert/config.yaml:362-372` **[V]**). A skill relay fans out to Slack (sB `alert-notify.md:3,27-35`).
- **(c)** —
- **(d)** —
- **(e)** Skill-grade (Early Access).
- **(f)** Anonymous.

### 3B. Summarization and audio

#### F13. File video summarization (LVS)

**(a) What the user gets:**

- Timestamped structured events plus a summary (`v:docs/long-video-summarization.mdx:8-14` **[V]**).
- Highlights driven by `scenario`/`events`/`objects` (sA `:317-320`).
- LLM merging of events that span chunks (sA `:858-890`).
- One report across several videos (`v:release-notes.mdx:113` **[V]**).

**(b) Components and infrastructure:**

- LVS + RT-VLM + an LLM.
- The ES default store; "Only Elasticsearch is provisioned" (`:914-918` **[V]**).
- Stock profile: Kafka on (B§7, `dev-profile-lvs/.env:124`).

**(c) GPU:**

- The default LLM (Lightning 30B) is about 78 GB BF16 / 45 GB INT4 (`v:sizing.md:75-76` **[V]**).
- The smallest local option is L40S with a remote LLM (sA `prerequisites.mdx:385-386`).
- Consumer: remote LLM or our llama.cpp **[A]**.

**(d) Input:**

- **No stills** (`vss_api_models.py:120-123` **[V]**). Clips yes.
- It processes **one request at a time** and returns 503 otherwise (`:1170-1172` **[V]**).

**(e) Maturity:** shipped. Invalid VLM JSON drops events (sA `:1180-1210`).

**(f) Gating:** anonymous image.

#### F14. Live-stream summarization and stream reports

- **(a)** Windowed summaries of a running stream.
- **(b)** **Kafka mandatory**; the endpoint returns 400 otherwise (`v:services/video-summarization/src/via_server.py:1031-1036` **[V]**). Also ES.
- **(c)** As F13.
- **(d)** **RTSP.**
- **(e)** **Early Access** (`v:release-notes.mdx:114` **[V]**). The caption prompt is overwritten by the latest session (`:121` **[V]**).
- **(f)** —

#### F15. Q&A over summarized assets

- **(a)** `/v1/chat/completions` against summarized media (sA `:133-134`).
- **(b)** The QA store defaults to a graph DB; Neo4j/Milvus/Arango are "deploy and operate yourself" (`:914-925` **[V]**).
- **(c)** LLM.
- **(d)** Clips.
- **(e)** Shipped but heavy.
- **(f)** —

#### F16. Audio understanding (Omni)

- **(a)** Native video and audio in a single model, with an `audio_transcript` per chunk (`v:docs/real-time-vlm.mdx:1687-1721` **[V]**). It would catch glass break, alarms and barking **[A]**.
- **(b)** RT-VLM with `VLM_TRUST_REMOTE_CODE` and `VLM_MODEL_SUPPORTS_AUDIO` (`:95` **[V]**). In the base profile only as a **remote** Omni (`v:release-notes.mdx:99` **[V]**).
- **(c)** **Fits no consumer card**: NVFP4 29.13 > 27.2 **[C]** (§2.2).
- **(d)** Clips with audio. Whether Foscam clips carry audio is **[?]**.
- **(e)** "Integration testing and sanity coverage" only (`v:docs/long-video-summarization.mdx:24` **[V]**).
- **(f)** HF ungated **[E]**.

### 3C. Search, agent, reports, MCP and UI

#### F17. Natural-language video search: embed, attribute and fusion

**(a) What the user gets:**

- Free-text search that returns timestamped clips.
- An LLM decomposes the query; filters apply (sB `v:docs/agent-workflow-search.mdx:6-27,59-64`).
- Follow-up questions (`v:release-notes.mdx:142` **[V]**).

**(b) Components and infrastructure:**

- RT-Embed, RT-CV (SigLIP2), behavior analytics, VIOS, VA-API, **ELK + Kafka** (sB `:32-42`; `VSS-Agent-Profiles.mdx:172-173` **[V]**).
- RT-Embed indexing needs Kafka (sB `rt-embed.md:12-15`).

**(c) GPU:**

- Stock layout is **2 GPUs** (`v:sizing.md:110` **[V]**).
- H100: 2 shared or 4 dedicated (`v:prerequisites.mdx:341` **[V]**).
- RT-Embed reserve (10) + VLM critic (13.8) + Y = 24.4, so 24✗ (§2.2).

**(d) Input:** **no stills ingest** (§2.1).

**(e) Maturity:**

- **"(alpha)"** (`v:docs/agent-workflows.mdx:17` **[V]**).
- "Negative-intent queries can match positive-intent results… single-word queries such as `person` can return no results" (`v:release-notes.mdx:150` **[V]**).
- Embeddings expire after 48 h (`v:agent-workflow-search.mdx:727-730` **[V]**).

**(f) Gating:** images anonymous. The default embed model is HF-ungated `Cosmos-Embed1-448p-anomaly-detection` (`v:deploy/docker/developer-profiles/dev-profile-search/.env:122` **[V]**).

#### F18. Search by image (query by bounding box)

- **(a)** Pick a box on a paused frame and find similar objects (`v:release-notes.mdx:141` **[V]**).
- **(b)** RT-CV + behavior-analytics index + ES + Kafka (sB).
- **(c)** RT-CV.
- **(d)** Video only.
- **(e)** Alpha (part of search).
- **(f)** Mixed.

#### F19. Critic agent

- **(a)** A VLM re-checks top results against the criteria extracted from the query, marking each confirmed or rejected with per-criterion ✓/✗ (`v:release-notes.mdx:144` **[V]**). The critic core is labelled "EXPERIMENTAL" (B§4g).
- **(b)** RT-VLM + the search agent.
- **(c)** VLM.
- **(d)** Clips.
- **(e)** On by default. Auto-disabled on some 2-GPU Brev hosts (sB `:636-641`).
- **(f)** NGC default VLM.

#### F20. VLM tagging → BM25 tag search

- **(a)** Keyword search over VLM tags.
- **(b)** Kafka → Logstash → ES.
- **(c)** VLM.
- **(d)** Streams.
- **(e)** **Design "Draft for review"** (sB `v:docs/designs/vlm-tagging-search.md:20-21`).
- **(f)** —

#### F21. Chat and visual Q&A over uploaded video (base agent)

- **(a)** Upload a clip, ask questions and follow-ups, and get snapshots and clips back. Conversation history defaults to 10 turns. An "Insights" reasoning panel is shown (sB `VSS-Agent-Profiles.mdx:40-52`; `VSS-Agent-Configuration.mdx:292`; `v:docs/vss-ui.mdx:60-62`).
- **(b)** VIOS, RT-VLM and an LLM. **No ES or Kafka** (`v:VSS-Agent-Profiles.mdx:172-173` **[V]**). The default path now uses an external harness (NemoClaw/OpenClaw) instead of the in-stack agent (sB `v:docs/quickstart.mdx:40-50`).
- **(c)** H100: 1 shared GPU (`v:prerequisites.mdx:337` **[V]**). The default LLM is about 45 GB even at INT4 (`v:sizing.md:76` **[V]**), so a consumer build needs our llama.cpp **[A]** (B§4g).
- **(d)** UI upload is MP4/MKV (sB `v:docs/vss-ui.mdx:91`). The API accepts stills via F1.
- **(e)** Shipped and documented. Known issues include recursion loops and bad URLs (sB `VSS-Agent-Overview.mdx:132-142`).
- **(f)** Anonymous agent image; NGC LLM NIM.

#### F22. Report generation

- **(a)** Markdown **and PDF** reports.
- **(b)** Timestamped observations auto-inject snapshots, and custom templates are supported (sB `v:docs/vss-agent/vss-agent-report-generation.mdx:129,246-258,272`). One report can cover several videos (`v:release-notes.mdx:113` **[V]**). Skill modes are A (clip VLM), B (incident range) and C (SOP) (sB). A RAG-grounded variant also exists.
- **(c)** Components by mode: Mode A needs VLM + LLM + VIOS; Mode B needs VA-MCP + ES.
- **(d)** Clips.
- **(e)** Shipped. Reports are **in-memory by default and lost on restart** (`v:release-notes.mdx:136` **[V]**).
- **(f)** As F21.

#### F23. Human-in-the-loop prompts

- **(a)** The agent asks for scenario, events and objects before summarizing.
- **(b)** Agent.
- **(c)** —
- **(d)** —
- **(e)** Shipped. Structured HITL is on by default for vss-agent (commit `6e4796506`, git log **[V]**).
- **(f)** —

#### F24. Incident and analytics chat (multi-report agent)

- **(a)** Questions such as "List incidents at Camera_01 last hour" or "How many people…", with charts (sB `VSS-Agent-Overview.mdx:54-116`).
- **(b)** VA-MCP + **ES**.
- **(c)** LLM.
- **(d)** Stored incidents.
- **(e)** Shipped for the warehouse and smart-city profiles.
- **(f)** —

#### F25. Video Analytics MCP server

- **(a)** Seven tools: `get_incident(s)`, `get_sensor_ids`, `get_places`, `get_fov_histogram`, `get_average_speeds`, `analyze` (sB `v:docs/video-analytics-mcp.mdx:21-31`).
- **(b)** **ES** (sB).
- **(c)** None.
- **(d)** —
- **(e)** Shipped. **"MCP servers and various tools lack authentication"** (sB `v:docs/Known-Limitations.mdx:14`).
- **(f)** Anonymous.

#### F26. Unified memory and introspection

- **(a)** The agent answers from the cheapest grounded source first: hot context → notes → memory → introspection → a fresh VLM run (sB `v:skills/operations/vss-ask-video/SKILL.md:77-116`).
- **(b)** The library defaults to `InMemoryStore` (`v:libs/vss/core/src/vss_core/memory/service.py:266` **[V]**), but the skill requires ES (sB `:61`).
- **(c)** —
- **(d)** —
- **(e)** New in September 2026; Early Access **[A]**.
- **(f)** —

#### F27. Agent Skills, harnesses, Orchestrator MCP and `vss` CLI

- **(a)** Deploy and operate VSS in natural language from Claude Code, Codex or NemoClaw (`v:docs/index.mdx:55-65` **[V]**).
- **(b)** None.
- **(c)** —
- **(d)** —
- **(e)** **Early Access** (`v:release-notes.mdx:90,102` **[V]**).
- **(f)** Anonymous tooling.

This is a developer and operator surface, not an end-user feature.

#### F28. Reference UI (Next.js)

**(a) Views:**

- chat sidebar
- Alerts (View and Manage)
- Dashboard (Kibana, so it needs ES)
- Search
- Video Management (MP4/MKV + RTSP)
- an undocumented Map iframe
- the "Alert Verification" rule tab: **"Coming soon (currently disabled)"** (`v:docs/vss-ui.mdx:360-363` **[V]**)

Sources: sB `v:docs/vss-ui.mdx:19-135,440-448,777`; `Home.tsx:307`.

**(b)** The agent-UI image.

**(c)** —

**(d)** Video-centric. There is no still gallery or event timeline **[A]**.

**(e) Maturity:**

- Shipped.
- The "263 files changed" is mostly one commit, `e6723df18`, which relicensed the UI to **Apache-2.0** (git log **[V]**; sB).
- Real functional churn is small: chat history, snapshot artifacts, HITL.

**(f)** Anonymous.

### 3D. Perception and analytics

#### F29. RT-CV detection and tracking (RT-DETR, NvDCF)

- **(a)** Per-stream boxes and track IDs.
- **(b)** DeepStream image, 18 GB compressed / 48 GB on disk (sC `v:docs/performance-rt-cv.mdx:116-121`). Kafka by default; optional standalone (sC).
- **(c)** "No model-memory fraction" (`v:sizing.md:96` **[V]**).
  - L40S: 15 RT-DETR streams at 87% (`v:docs/performance-rt-cv.mdx:57` **[V]**).
  - Spark: 5 at 95.5% (`:66` **[V]**).
  - The only measured perception VRAM is Sparse4D at 4 streams, under 2 GB (`v:sizing.md:282-285` **[V]**).
  - Plausible on a 24 GB card at event rate **[A]**.
- **(d)** **Clips and RTSP; no stills** (§2.1).
- **(e)** Shipped and benchmarked.
- **(f)** Anonymous image; weights from NGC TAO **[?]**.

#### F30. Open-vocabulary detection (Grounding DINO text prompts)

- **(a)** Zero-shot prompts with per-prompt thresholds, e.g. `"person wearing helmet"`, `"Car . Person . ;0.4"` (`v:docs/object-detection-tracking.mdx:668-686` **[V]**).
- **(b)** RT-CV (Triton).
- **(c)** The heaviest detector family: 3 streams on L40S (`v:performance-rt-cv.mdx:59` **[V]**).
- **(d)** Clips only.
- **(e)** Shipped (alerts profile).
- **(f)** NGC TAO weights.

#### F31. Per-object embeddings and re-ID in perception

- **(a)** SigLIP2 / RADIO-CLIP embeddings. "Smart embedding" skips objects already known to the tracker. CRP clustering in behavior analytics (sC `v:docs/object-detection-tracking.mdx:189-207,408-430`; `v:docs/behavior-analytics.mdx:833-857`).
- **(b)** RT-CV (search profile).
- **(c)** Inside RT-CV.
- **(d)** Clips.
- **(e)** Shipped. There is **no 2D multi-camera (MTMC) producer** (sC grep).
- **(f)** NGC.

#### F32. Behavior analytics

- **(a)** Tripwire IN/OUT and ROI entry/exit; proximity, restricted, confined and FOV-count incidents; speed, direction and trajectory (`v:docs/index.mdx:38` **[V]**; sC `v:docs/behavior-analytics.mdx:861-887,1025-1034,1120-1161`).
- **(b)** A CPU service fed by Kafka, Redis Streams or MQTT (sC `:12`). It consumes RT-CV output.
- **(c)** CPU only.
- **(d)** **Continuous tracks required**:
  - defaults are a 1 s threshold and a 0.5 s gap window (`:270-281` **[V]**);
  - tripwires need 5 points on each side of the crossing (`:1075` **[V]**).
- **(e)** Shipped and extensively documented.
- **(f)** Anonymous.

#### F33. Occupancy, counting and flow metrics (VA-API)

- **(a)** Tripwire counts, FOV/ROI occupancy histograms, flow rate, and clusters (sC `v:docs/video-analytics-api-server.mdx:291,375-411`). **There is no explicit loiter or dwell rule** (sC grep).
- **(b)** Node + **ES**.
- **(c)** CPU.
- **(d)** Streams.
- **(e)** Shipped.
- **(f)** Anonymous.

#### F34. Anomaly detection

- **(a)** Smart-city traffic anomalies: speed, stop, wrong-way, collision.
- **(b)** Also fall-risk and lack-of-movement, wired only into undocumented `composite`/`rpm` apps and needing pose actions that no shipped profile emits (sC `v:docs/behavior-analytics.mdx:333-343`; `anomaly_action_detection.py:104-108`).
- **(c)** CPU.
- **(d)** Streams.
- **(e)** Traffic: shipped. Fall-risk: experimental.
- **(f)** —

#### F35. Multi-camera 3D perception (Sparse4D, MV3DT)

- **(a)** Bird's-eye-view 3D tracks with global IDs (`v:release-notes.mdx:100` **[V]**).
- **(b)** RT-CV + BEV fusion + Kafka + MQTT + calibration.
- **(c)** Under 2 GB at 4 streams.
- **(d)** Needs "time-synchronized, 30 FPS" footage (sC `v:docs/mv3dt-standalone-deployment.mdx:26`).
- **(e)** New in 3.2.
- **(f)** `reid-embed` comes from an NGC mirror.

#### F36. Calibration (legacy toolkit, auto-calibration)

- **(a)** ROI and tripwire drawing. There is an "Image Calibration" mode for stills. Auto-calibration derives camera pose (sC `v:docs/legacy-calibration.mdx:6-15,93`; `v:docs/auto-calibration.mdx:6-12`; `v:release-notes.mdx:101` **[V]**).
- **(b)** Toolkit + VA-API.
- **(c)** CPU; VGGT **[?]**.
- **(d)** The toolkit works on a reference image.
- **(e)** The toolkit is "Legacy"; auto-calibration is warehouse-only.
- **(f)** **NGC mirror (401)** **[E]**.

### 3E. Video I/O, dashboards, deployment and verticals

#### F37. VIOS video I/O

- **(a)** ONVIF discovery, RTSP add, recording with aging, WebRTC/DASH replay, snapshots, upload, video wall, Milestone adaptor (sC `v:docs/vios-microservices.mdx:14-30,338-354`).
  - Default limits: `max_devices_supported` 16 (`:588` **[V]**); aging at 95% disk (`:593` **[V]**); `always_recording` FALSE (`:599` **[V]**).
- **(b)** 4 VIOS images + Postgres + Redis + SDR + ingress.
- **(c)** NVDEC/NVENC; VRAM **[?]**.
- **(d)** **RTSP or H.264/H.265 upload; no stills** (`:595` **[V]**). Foscam is not on the tested-camera list (sC `:156-184`).
- **(e)** Shipped.
- **(f)** Anonymous.

#### F38. Kibana dashboards and ELK

- **(a)** The "Dashboard" tab.
- **(b)** ES + Logstash + Kibana.
- **(c)** CPU, about 8 GB of heap with Kafka.
- **(d)** —
- **(e)** Shipped. ILM retention is **4 h** (`v:docs/elk.mdx:217-232` **[V]**).
- **(f)** Public.

#### F39. Configurators (VSS, DeepStream, RT config adaptor)

- **(a)** GPU-type-driven config rewrites. Known GPUs: H100, GB300, L40S, RTX PRO 6000/4500, Thor, Spark (sC `v:docs/vss-configurator.mdx:38`).
- **(b)** CPU.
- **(c)** —
- **(d)** —
- **(e)** Shipped; warehouse-centric.
- **(f)** Anonymous.

#### F40. SOP compliance (DS-SOP)

- **(a)** Step detection plus a compliance report (`v:skills/vss-build-vision-ai/references/services/sop.md:12-22` **[V]**).
- **(b)** ELK + Kafka + VIOS.
- **(c)** VLM slot.
- **(d)** Streams or files.
- **(e)** Skill-composed delta.
- **(f)** —

#### F41-F43. Smart-city, warehouse and public-safety verticals

- **(a)**

  - Smart city: traffic analytics and collision verification.
  - Warehouse: forklift and near-miss detection.
  - Public safety: tailgating + VLM verification.

  Sources: `v:docs/index.mdx:82-83` **[V]**; sC `v:docs/publicsafety-docs/Introduction.mdx:11-26`.

- **(b)** Full alerts stack, plus 3D for warehouse.
- **(c)** Multi-GPU (sC).
- **(d)** Streams.
- **(e)** Two profiles are in-repo. Public safety is NGC-distributed and missing from nav (sC).
- **(f)** Public safety is NGC.

#### F44. Observability

- **(a)** Grafana, Prometheus, DCGM, cAdvisor; OTel + Jaeger for alerts, off by default (sC `v:docs/observability.mdx:6,42-46`).
- **(b)** Standard.
- **(c)** —
- **(d)** —
- **(e)** Shipped.
- **(f)** Public.

#### F45. Hardware and edge profiles

**(a) What the user gets:**

- `hw-*.env` for H100, GB300, L40S, RTX PRO 6000/4500, Spark, Thor, `OTHER`.
- A new Jetson Orin NX/AGX Orin OS row (`v:README.md:126-137` **[V]**).
- Still **no GeForce row** (`v:sizing.md:60-69` **[V]**).

**(b)** —

**(c)** The smallest discrete card is the RTX PRO 4500, alerts only, 2 GPUs (`v:prerequisites.mdx:370-380` **[V]**).

**(d)** —

**(e)** `OTHER` is "experimental" (sC).

**(f)** —

---

## 4. Our product: feature inventory

Wiring status comes from the non-test importer and caller greps in slice D. I re-verified the key "not wired" claims (Appendix A):

- **WIRED**: route + page + runtime producer.
- **API/UI-ONLY**: page and CRUD routes exist, but there is no runtime producer or consumer.

| ID  | Feature                                                                                                                                                                               | What the user gets                                                                                                                         | Status                                                                                                                     | Evidence                                                                                                                  |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| O1  | FTP drop-folder ingest                                                                                                                                                                | Foscam JPEGs and short clips analysed automatically                                                                                        | WIRED                                                                                                                      | `o:backend/services/file_watcher.py:68-71` **[V]**; base `/export/foscam` `o:backend/core/config.py:929-931` (sD)         |
| O2  | Clip frame sampling                                                                                                                                                                   | Uploaded clips sampled every 4 s, ≤20 frames                                                                                               | WIRED                                                                                                                      | sD `o:backend/services/pipeline_workers.py:656,674`; `config.py:2217-2221,2567-2571`                                      |
| O3  | Live view                                                                                                                                                                             | go2rtc RTSP→WebRTC preview in camera settings. The dashboard grid shows the latest snapshot                                                | WIRED (view only)                                                                                                          | `o:docs/ui/dashboard.md:176-180` **[V]**; B§10.17                                                                         |
| O4  | RTSP analysis ingest                                                                                                                                                                  | `StreamManager` + `IngestionMode.RTSP/ONVIF`                                                                                               | **Built, not wired**                                                                                                       | `o:backend/services/stream_manager.py:1-19` **[V]**; importer grep **[V]**                                                |
| O5  | YOLO26 detection with per-class thresholds                                                                                                                                            | Person/vehicle/animal boxes                                                                                                                | WIRED                                                                                                                      | sD `o:config.py:1788-1817`                                                                                                |
| O6  | Enrichment model zoo (~23 models): plates, faces, OCR, SigLIP2/OSNet re-ID, pose, depth, violence, weather, clothing, vehicle type, **pet classifier**, threat, age/gender, low-light | Rich per-detection attributes                                                                                                              | WIRED, in-process **load-use-unload**                                                                                      | `o:backend/services/model_zoo.py:10-33,565-580` **[V]**                                                                   |
| O7  | Florence-2 cascade                                                                                                                                                                    | Captions only for ambiguous (<0.7) detections                                                                                              | WIRED                                                                                                                      | `o:backend/services/enrichment_pipeline.py:2502-2512` **[V]**                                                             |
| O8  | Threat fast path                                                                                                                                                                      | Weapons bypass the 90 s batch                                                                                                              | WIRED; may fail with `session=None` **[A]**                                                                                | `o:backend/services/batch_aggregator.py:1338-1346` **[V]**                                                                |
| O9  | Scene change / tamper (SSIM)                                                                                                                                                          | Tamper context fed into the prompt                                                                                                         | WIRED                                                                                                                      | sD `enrichment_pipeline.py:2715-2723`                                                                                     |
| O10 | Activity and scene baselines                                                                                                                                                          | Unusual-for-this-hour context                                                                                                              | WIRED                                                                                                                      | sD `o:backend/services/detector_client.py:1360`; `enrichment_pipeline.py:3598-3616`                                       |
| O11 | Trajectory / dwell (clips)                                                                                                                                                            | Movement context in the prompt                                                                                                             | WIRED                                                                                                                      | sD `o:backend/services/nemotron_analyzer.py:2020-2042`                                                                    |
| O12 | **Risk scoring**                                                                                                                                                                      | 90 s window / 30 s idle → Nemotron (llama.cpp) → 0-100 score + summary + reasoning; LOW/MED/HIGH/CRIT bands                                | WIRED                                                                                                                      | `o:config.py:966-975,2394-2412` **[V]**; sD `o:backend/models/event.py:58-70`                                             |
| O13 | LLM reasoning explorer and live analysis stream                                                                                                                                       | See the LLM's thinking                                                                                                                     | WIRED                                                                                                                      | sD `o:backend/api/routes/llm_reasoning.py:1-8`; `events.py:2538`                                                          |
| O14 | Hourly and daily narrative summaries                                                                                                                                                  | Digest of events                                                                                                                           | WIRED (60 min job)                                                                                                         | sD `o:backend/main.py:920-931`                                                                                            |
| O15 | Prompt management                                                                                                                                                                     | Versions, playground, A/B, import/export, self-audit, auto-tuner                                                                           | WIRED                                                                                                                      | sD `o:backend/api/routes/prompt_management.py:1-7`; `docs/ui/ai-audit.md:125-168`                                         |
| O16 | Dashboard                                                                                                                                                                             | Stats, risk sparkline, camera grid, activity feed, summary cards                                                                           | WIRED                                                                                                                      | `o:frontend/src/App.tsx:259` **[V]**; sD `docs/ui/dashboard.md:77-99`                                                     |
| O17 | Event timeline and detail                                                                                                                                                             | Infinite scroll, clusters, bulk actions; modal with boxes, reasoning, enrichment; review, notes, snooze, trash; "clips" = stills slideshow | WIRED                                                                                                                      | `o:App.tsx:260` **[V]**; sD `docs/ui/timeline.md:28-300`; `clip_generator.py:1-6`                                         |
| O18 | **Search**                                                                                                                                                                            | PostgreSQL full-text over summary/reasoning/objects/cameras; phrases, booleans, filters, saved searches                                    | WIRED; **keyword only**                                                                                                    | `o:backend/services/search.py:1-10` **[V]**; `o:backend/api/routes/events.py:1030` **[V]**                                |
| O19 | Re-ID entities                                                                                                                                                                        | Cross-camera entities with trusted/suspicious/unknown labels                                                                               | WIRED                                                                                                                      | sD `o:backend/api/routes/entities.py:4`; `enrichment_pipeline.py:5825`                                                    |
| O20 | **Household members and vehicles**                                                                                                                                                    | Known people and cars suppress or contextualize risk                                                                                       | WIRED                                                                                                                      | `o:enrichment_pipeline.py:5903-5910` **[V]**; sD `nemotron_analyzer.py:659-664`                                           |
| O21 | Face recognition page                                                                                                                                                                 | Enrol, known persons, auto-enrol queue                                                                                                     | UI+API; **pipeline matching not wired**                                                                                    | `o:backend/services/face_detector.py:343` records "unknown" **[V]**; `match_face` has only route and self callers **[V]** |
| O22 | Plate reads page                                                                                                                                                                      | ALPR history                                                                                                                               | API/UI-ONLY rows                                                                                                           | sD `o:backend/services/alpr_service.py:156,206`                                                                           |
| O23 | Camera zones                                                                                                                                                                          | Polygons typed entry/driveway/sidewalk/yard, fed into the prompt                                                                           | WIRED                                                                                                                      | sD `o:docs/ui/zones.md:38-48`; `context_enricher.py:27-33`                                                                |
| O24 | Analytics zones                                                                                                                                                                       | Tripwire, dwell, loiter UI                                                                                                                 | **API/UI-ONLY**                                                                                                            | sD `o:backend/api/routes/analytics_zones.py:1-8`                                                                          |
| O25 | Alert rules engine                                                                                                                                                                    | Risk/object/camera/time/zone rules, cooldown                                                                                               | **Not evaluated at runtime** (`evaluate_event` has no caller)                                                              | grep **[V]**; the Alerts page lists HIGH/CRITICAL events (sD `docs/ui/alerts.md:13`)                                      |
| O26 | Outbound webhooks                                                                                                                                                                     | HMAC, retries, Jinja templates on event create and acknowledge                                                                             | WIRED                                                                                                                      | sD `o:backend/services/webhook_service.py:1-12`; `nemotron_analyzer.py:4540-4543`                                         |
| O27 | Inbound webhooks                                                                                                                                                                      | IFTTT/Zapier/n8n arm/disarm                                                                                                                | API; effect **[A]**                                                                                                        | sD `o:backend/api/routes/inbound_webhooks.py:1-9`                                                                         |
| O28 | Email / push / browser / PWA                                                                                                                                                          | —                                                                                                                                          | Email: test endpoint only (`deliver_alert` has no caller **[V]**). Push: stub. Browser: while open. PWA: yes               | sD `o:backend/services/notification.py:4,112,544-556`                                                                     |
| O29 | MQTT / Home Assistant discovery                                                                                                                                                       | Config page                                                                                                                                | **Not wired** (no importer **[V]**)                                                                                        | sD `o:backend/api/routes/mqtt_config.py:1-13`                                                                             |
| O30 | Reports, exports, backup                                                                                                                                                              | CSV/XLSX/JSON/ZIP export; backup/restore                                                                                                   | Exports WIRED; **scheduled reports stub**                                                                                  | `o:backend/api/routes/scheduled_reports.py:419-420` **[V]**                                                               |
| O31 | Analytics pages                                                                                                                                                                       | Grafana embed, trends, baselines                                                                                                           | Mixed; heatmaps, tracks and scene-changes pages have **no writer**                                                         | sD `o:docs/ui/analytics.md:55-88`; `heatmap_service.py:142`                                                               |
| O32 | System and AI ops                                                                                                                                                                     | AI services, model zoo status, detector switching, GPU assignment, GPU metrics, Pyroscope, tracing, logs, audit, jobs, DLQ                 | WIRED                                                                                                                      | `o:App.tsx:258-305` **[V]**                                                                                               |
| O33 | Resilience                                                                                                                                                                            | Degradation modes, inference semaphore, OOM handler, back-pressure                                                                         | WIRED                                                                                                                      | `o:backend/services/degradation_manager.py:68-74` **[V]**; sD `ai/gpu_oom_handler.py:357`                                 |
| O34 | Auth and exposure                                                                                                                                                                     | First-run setup guard + login; loopback binding                                                                                            | WIRED                                                                                                                      | `o:AGENTS.md` (auth model) **[V]**                                                                                        |
| O35 | Retention                                                                                                                                                                             | 30 days + daily cleanup + trash                                                                                                            | WIRED                                                                                                                      | `o:config.py:959-963` **[V]**                                                                                             |
| O36 | **False-positive feedback**                                                                                                                                                           | Mark accurate/false_positive/missed/severity_wrong                                                                                         | **Stored, never consumed** (`FeedbackProcessor` has no importer **[V]**). "Feedback Learning" in settings docs is inactive | `o:backend/models/event_feedback.py:114` **[V]**; `o:docs/ui/settings.md:317` **[V]**                                     |

**Absent from our product** (plain grep, sD **[V]**):

- audio understanding;
- chat / Q&A over events;
- natural-language or semantic search;
- an MCP or agent tool server;
- live-stream analysis;
- recording / DVR.

---

## 5. Gap matrix

Classes:

- **NEW**: we lack it.
- **UPGRADE**: we have a weaker version.
- **PARITY**
- **N/A**: residential mismatch, or not a user feature.

| VSS                                                      | Class                   | Our counterpart                                                       | What improves, or why not                                                                                                            |
| -------------------------------------------------------- | ----------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| F1 VLM captions / Q&A                                    | **UPGRADE**             | O7 Florence-2 crop captions; O12 text-only LLM                        | Whole-scene, pixel-grounded description of stills and clips; answers ad-hoc questions. The LLM stops reasoning from secondhand text. |
| F2 Live RTSP captioning                                  | NEW (needs RTSP)        | — (O4 dormant)                                                        | Requires wiring O4 and a continuous VLM. Defer.                                                                                      |
| F3 Prompt-triggered incidents                            | **NEW**                 | O25 rules (structured, unwired)                                       | User-authored natural-language conditions. Import the idea (R3), not the substring trigger.                                          |
| F4 Constrained output                                    | N/A (plumbing)          | O12 JSON parse (B§9: our `nvext.guided_json` is a no-op on llama.cpp) | Enabler for R1 and R3; see B's #1                                                                                                    |
| F5 Reasoning traces                                      | PARITY                  | O12/O13                                                               | —                                                                                                                                    |
| F6 EVS pruning                                           | N/A                     | —                                                                     | Video-only speedup. Stills gain nothing.                                                                                             |
| F7 Alert verification                                    | **UPGRADE**             | O12 (risk graded from text)                                           | **VSS verifies, we grade** (B§5g). A pixel-grounded confirm/reject gate is the missing FP-suppression step.                          |
| F8 On-demand image verification                          | **NEW**                 | —                                                                     | The exact shape for FTP stills. The service is Kafka+ES-fenced, so import the pattern.                                               |
| F9 Contextualization / classification / per-type prompts | **UPGRADE**             | O15 (per-model prompts)                                               | Per-alert-type prompts editable at runtime; N-way classification ("delivery / visitor / intruder")                                   |
| F10 Real-time VLM rules on streams                       | NEW (needs RTSP)        | O25                                                                   | Stream-only. Adapted as R3.                                                                                                          |
| F11 Incident consolidation                               | PARITY                  | O12 batching                                                          | Ours groups at write time and is stronger for stills                                                                                 |
| F12 Webhook→Slack relay                                  | PARITY (ours stronger)  | O26                                                                   | Ours has HMAC and retries; VSS is fire-and-forget with no retry. **Neither ships working email or push.**                            |
| F13 LVS file summarization                               | **UPGRADE** (concept)   | O14 digests over event text                                           | Summaries grounded in pixels, with timestamps. But LVS is video-only and ES-default, so do it via F1 chunking.                       |
| F14 Live-stream summarization                            | NEW (trap)              | —                                                                     | Kafka mandatory; RTSP; Early Access                                                                                                  |
| F15 LVS Q&A graph                                        | NEW (trap)              | —                                                                     | Graph DB you operate yourself                                                                                                        |
| F16 Omni audio                                           | **NEW**                 | — (no audio anywhere)                                                 | High value (glass break, alarm), but **fits no consumer card**                                                                       |
| F17 Natural-language / semantic search                   | **UPGRADE**             | O18 keyword FTS                                                       | "Someone carrying a box near the garage" instead of keywords                                                                         |
| F18 Search by image                                      | **UPGRADE**             | O19 re-ID entities                                                    | Ad-hoc query-by-example on a selected box                                                                                            |
| F19 Critic                                               | **NEW**                 | —                                                                     | VLM re-verifies search results, the same FP discipline applied to search                                                             |
| F20 Tag search                                           | PARITY                  | O18 (FTS over LLM text)                                               | VSS's version is a draft                                                                                                             |
| F21 Chat / Q&A over video                                | **NEW**                 | —                                                                     | "Was anyone at the back door last night?"                                                                                            |
| F22 Report generation                                    | **UPGRADE**             | O30 exports; scheduled-reports stub                                   | Narrative incident report with snapshots, as PDF, for insurers or police                                                             |
| F23 HITL                                                 | NEW (with F21)          | —                                                                     | —                                                                                                                                    |
| F24 Incident chat                                        | NEW (merges into R7)    | —                                                                     | The VSS version is ES-bound                                                                                                          |
| F25 VA-MCP                                               | **NEW**                 | —                                                                     | Tool surface for Claude Desktop, HA or agents. Reimplement over Postgres, with auth.                                                 |
| F26 Memory / introspection                               | NEW (with F21)          | —                                                                     | The `InMemoryStore` seam is usable                                                                                                   |
| F27 Skills / harness / CLI                               | N/A (developer tooling) | —                                                                     | Relevant to the upstream contribution, not to users                                                                                  |
| F28 Reference UI                                         | PARITY / N/A            | O16-O17                                                               | Ours is home-centric. Borrow patterns only: chat sidebar, "VLM-verified" toggle, bbox playback.                                      |
| F29 RT-CV                                                | PARITY                  | O5 YOLO26                                                             | Tracking would be an upgrade only for clips; no stills                                                                               |
| F30 GDINO open-vocabulary                                | **UPGRADE**             | O6 YOLO-World in the zoo, used only by unwired package tracking       | Prompt-defined detectors ("package on porch"). Cheaper route: wire YOLO-World or use R3.                                             |
| F31 Object embeddings / re-ID                            | PARITY                  | O6/O19 SigLIP2 + OSNet                                                | "Smart embedding" skip is an efficiency idea                                                                                         |
| F32 Behavior analytics                                   | UPGRADE (clips only)    | O24 (unwired), O23                                                    | Declarative tripwire/ROI semantics, but needs continuous tracks. **Impossible on stills** at defaults.                               |
| F33 Occupancy / flow                                     | N/A                     | —                                                                     | Retail and warehouse metrics                                                                                                         |
| F34 Anomaly (traffic / fall-risk)                        | N/A                     | O10 baselines                                                         | Traffic is not residential. Fall-risk is experimental and needs pose actions.                                                        |
| F35 3D / MV3DT                                           | N/A                     | —                                                                     | Needs synchronized 30 FPS calibrated cameras                                                                                         |
| F36 Calibration                                          | PARITY / N/A            | O23 zone editor                                                       | —                                                                                                                                    |
| F37 VIOS recording / replay                              | NEW (needs RTSP)        | O3 preview                                                            | DVR-style replay. Only after an RTSP ingest decision.                                                                                |
| F38 Kibana                                               | PARITY                  | O31 Grafana                                                           | ES 4 h ILM vs our 30 days                                                                                                            |
| F39 Configurators                                        | N/A                     | —                                                                     | Deploy-time                                                                                                                          |
| F40 SOP                                                  | N/A                     | —                                                                     | Industrial                                                                                                                           |
| F41-F43 Verticals                                        | N/A                     | —                                                                     | Public safety's "person in view → VLM verify" is F7's pattern                                                                        |
| F44 Observability                                        | PARITY (ours broader)   | Tempo/Loki/Pyroscope                                                  | —                                                                                                                                    |
| F45 Hardware profiles                                    | N/A as a feature        | —                                                                     | This is the slot a consumer tier fills                                                                                               |

---

## 6. Our differentiators VSS lacks

These are what a consumer tier brings that VSS does not.

1. **Still-image FTP ingest.**
   - Ours: `o:file_watcher.py:68-71` **[V]**.
   - VSS: FTP appears nowhere (sC grep). Stills enter only through RT-VLM, the on-demand route and RT-Embed (§2.1).
   - Many consumer cameras upload JPEGs on motion. VSS cannot use them without our front end.
2. **Event-triggered compute instead of always-on residency.**
   - Ours: 90 s / 30 s batching (`o:config.py:966-975` **[V]**) and in-process load-use-unload of zoo models (`o:model_zoo.py:565-580` **[V]**).
   - VSS: every model service is always-on with no unload (B headline 3); vLLM reserves at init (`v:docs/real-time-vlm.mdx:1535-1536` **[V]**).
   - **Caveat:** the "LRU eviction" in our framing is **not the production path** (§9.2).
3. **A graded 0-100 risk score with severity bands and narrative reasoning.**
   - Ours: `o:config.py:2394-2412` **[V]**.
   - VSS: produces binary verdicts only. "risk score" has 0 grep hits in VSS **[V]**, and `AlertSeverity` is dead code (B "Looks reusable").
4. **A residential identity layer.**
   - Household people and vehicles feed "known person" context (`o:enrichment_pipeline.py:5903-5910` **[V]**).
   - Face and plate UIs exist, though matching is partially wired.
   - VSS has LPR and face recognition **only as schema fields** (`v:docs/NvSchema.mdx:246,562` **[V]**). It has no model or service for either.
5. **False-positive-specific enrichment:**

   - a pet classifier "for false positive reduction" (`o:model_zoo.py:27` **[V]**);
   - the prompt rule "High-confidence cat/dog (>85%) = likely false positive" (`o:backend/services/prompts.py:1017-1018` **[V]**);
   - weather and low-light models (`o:model_zoo.py:21,33` **[V]**);
   - scene-change and tamper detection;
   - activity baselines;
   - a Florence cascade for ambiguous detections only (`o:enrichment_pipeline.py:2502-2512` **[V]**).

   VSS has no user false-positive feedback loop either (grep, §3). Ours exists but is unconsumed (O36).

6. **A non-vLLM LLM engine.**
   - llama.cpp GGUF (`o:docker-compose.prod.yml:158` **[V]**), with sleep-on-idle and router unload available **[E]**.
   - VSS's LLM NIM has a ≥32 GB INT4 floor (B§4e), so it cannot run on 24 GB.
7. **Single-GPU resilience:** degradation modes (`o:degradation_manager.py:68-74` **[V]**), OOM handler, inference semaphore, back-pressure. VSS has nothing equivalent **[A]** (no hits in slices A-C).
8. **Prompt engineering tooling:** A/B tests, playground, self-audit and auto-tuner (O15). VSS offers only runtime `PUT` of per-type prompts (`v:release-notes.mdx:39-42` **[V]**).
9. **Home retention and security posture.**
   - Retention: 30 days vs VSS's 4 h ES ILM (`v:docs/elk.mdx:217-232` **[V]**).
   - Security: loopback binding + setup guard vs VSS's "trusted, isolated network" assumption (`v:docs/index.mdx:8-13` **[V]**) and unauthenticated MCP (sB `Known-Limitations.mdx:14`).
10. **A residential integration surface.** Outbound webhooks with HMAC and retries (O26), inbound IFTTT/Zapier, and a PWA. VSS has **no email, push, MQTT-out or Home Assistant** integration (sB grep **[V]**). Ours are partly unwired too (O28, O29).
11. **Home UX:** event timeline, entities, household, trash, and a risk-first dashboard. VSS's UI is video- and stream-centric, with no still or event timeline **[A]**.

---

## 7. Ranked import list

**Scoring [C]:** Score = V × F ÷ I.

| Axis                                                              | 1                              | 5                                     |
| ----------------------------------------------------------------- | ------------------------------ | ------------------------------------- |
| **V** (home-security user value; FP suppression weighted highest) | low                            | high                                  |
| **F** (feasible on one consumer GPU with our stills/clips ingest) | needs RTSP or does not fit     | fits 24 GB with the 30B LLM displaced |
| **I** (new infrastructure)                                        | none / one stateless container | Kafka + ES + VIOS or graph DB         |

| Rank | Import (user-visible)                                                                              | From                  |  V  |  F  |  I  |  Score |
| ---- | -------------------------------------------------------------------------------------------------- | --------------------- | :-: | :-: | :-: | -----: |
| 1    | **VLM verification gate** on candidate events: confirmed/rejected + reasoning                      | F7, F8, F9, F4, F5    |  5  |  4  |  1  | **20** |
| 2    | **VLM scene and clip descriptions** for every surfaced event                                       | F1, F5 (F13 concept)  |  4  |  4  |  1  | **16** |
| 3    | **Natural-language per-camera alert rules** ("person at side gate after dark") evaluated per event | F3, F10 (adapted), F9 |  4  |  4  |  1  | **16** |
| 4    | **Incident reports** (narrative + snapshots, Markdown/PDF, templates)                              | F22                   |  3  |  4  |  1  | **12** |
| 5    | **MCP tool surface** over our events (VA-MCP shape, with auth)                                     | F25, F24              |  2  |  5  |  1  | **10** |
| 6    | **Lean natural-language / semantic event search** + VLM critic re-rank                             | F17, F19              |  4  |  4  |  2  |  **8** |
| 7    | **Chat / Q&A over events and clips** (tools + HITL + memory ladder)                                | F21, F23, F26         |  3  |  3  |  2  |    4.5 |
| 8    | **Open-vocabulary prompt detection**                                                               | F30                   |  3  |  3  |  2  |    4.5 |
| 9    | Audio understanding (Omni)                                                                         | F16                   |  4  |  1  |  1  |      4 |
| 10   | Behavior-analytics rules on uploaded clips                                                         | F32                   |  3  |  2  |  2  |      3 |
| 11   | LVS service as shipped                                                                             | F13                   |  3  |  2  |  3  |      2 |
| 12   | Real-time VLM alerts on RTSP                                                                       | F10                   |  4  |  1  |  4  |      1 |
| 13   | VSS search stack as shipped                                                                        | F17, F18              |  4  |  1  |  5  |    0.8 |
| 14   | LVS Q&A graph                                                                                      | F15                   |  2  |  2  |  5  |    0.8 |
| 15   | VIOS recording / replay                                                                            | F37                   |  3  |  1  |  4  |   0.75 |
| 16   | Live-stream summarization                                                                          | F14                   |  2  |  1  |  4  |    0.5 |
| —    | 3D, SOP, smart city, warehouse, occupancy, configurators, Kibana                                   | F33-F43               |  —  |  —  |  —  |    N/A |

**Prerequisite (not a VSS feature):** fix our own structured output before building any of this.

- B§9 found that our analyzer sends NIM-only `nvext.guided_json` to llama.cpp.
- Unparseable output fails open to score 50 → `medium`.
- A verifier that fails open is worse than none.

### Top items in detail

#### #1 VLM verification gate (score 20)

**Why:** this is the product. VSS built it for exactly this purpose ("to reduce false positives", `v:docs/agent-workflow-alert-verification.mdx:31` **[V]**).

**User experience:**

- An event only notifies after a VLM looks at the evidence stills and says "confirmed".
- The event shows the verdict and a one-line reason.
- "Rejected" events stay visible but silent.

**Minimal VSS pieces:**

- The verdict contract: confirmed/rejected/unverified + reasoning.
- The per-alert-type prompt config (`alert_type_config.json`; runtime `PUT`, `v:release-notes.mdx:39-42` **[V]**).
- A constrained `choice`/`json_schema` verdict (`v:captions.py:100-106` **[V]**) instead of the yes/true substring trigger (`v:docs/real-time-vlm.mdx:1204-1207` **[V]**).
- Optionally the `vss-rt-vlm` image with `media_type:image`, `file://` + `FILE_URL_ALLOWED_DIRS` on the FTP directory (`:992-996` **[V]**), and `MESSAGE_BUS` empty (`:1490` **[V]**).

**Not needed:** Alert Bridge (Kafka + ES mandatory at 3.3), RT-CV, behavior analytics, VIOS, ES, Kafka.

**Lean variant exists: yes.**

- Either RT-VLM standalone (always-on; defaults to 0.7 = 16.8 GB on 24 GB **[C]**),
- or the same pattern on llama.cpp multimodal (B's #2), which keeps sleep/unload **[E]**.
- The Alerts microservice itself has **no** lean variant.

**Where it plugs in:** after O12 batching and before notification, only for events above a risk threshold. This keeps VLM calls event-rate, not frame-rate. Our risk score stays; the VLM gates it (B§5g).

**GPU on one 24 GB card:** needs one of:

- (i) a one-VL-model topology, where the VLM also emits the risk JSON: Cosmos3-Edge + Y = 12.52;
- (ii) a VLM + 4B text LLM: Cosmos3-Edge + Y + 4B-FP8 = 19.37 ✓;
- (iii) llama.cpp router swapping 30B ↔ VLM, with the latency cost **[?]**.

**Maturity risk:** RT-VLM validated GPUs exclude consumer cards. NVFP4 on sm_86 is **[?]** (§2.2).

#### #2 VLM scene and clip descriptions (score 16; shares #1's engine, so marginal I ≈ 0)

**User experience:** the event detail reads like a person described the frame ("a delivery driver in a brown uniform leaves a box on the porch and walks back to a van"), instead of a list of enrichment badges.

**What it upgrades:** O7 (Florence-2 on crops) and O12's text-only grounding.

**VSS pieces:** RT-VLM captioning (`v:docs/real-time-vlm.mdx:452-489` **[V]**) with `chunk_duration` for clips; reasoning traces (F5).

**Not needed:** the LVS service. It is video-only and ES-default (§3 F13), and processes one request at a time. Use RT-VLM chunking plus our llama.cpp for clip roll-ups.

**Lean variant:** yes.

**Frontend blast radius:** RT-VLM emits prose, not the enrichment child-object model (vi/06 §1.7). Add descriptions alongside the badges; do not replace them.

#### #3 Natural-language per-camera alert rules (score 16)

**User experience:** the user types "alert me if someone is at the side gate after dark" or "tell me when a package is left at the door". Each surfaced event on that camera is checked by the VLM against the rule.

**Why:**

- VSS's real-time alerts are the most user-friendly feature VSS has, but they are RTSP-only and continuous (`v:agent-workflow-rt-alert.mdx:154` **[V]**; H100 ×2, `v:prerequisites.mdx:340` **[V]**).
- Evaluating the same rule on **event stills** gets most of the value at event rate.
- It also gives O25, our unwired rules engine, a runtime path.

**VSS pieces:**

- The rule shape (`alert_type`, `prompt`) (`:154-156` **[V]**).
- Runtime per-type prompts (F9).
- "Always-on" auto-attach semantics, which here means the rule applies to every camera, including new ones (`v:alert-verification-service.mdx:76` **[V]**).
- N-way classification (`v:release-notes.mdx:153-157` **[V]**).

**Not needed:** RTSP, VIOS, Kafka.

**Lean variant:** yes. It runs in the same VLM call as #1, as a multi-question constrained prompt **[A]**.

#### #4 Incident reports (score 12)

**User experience:** a one-click incident report (timeline, snapshots, narrative, verdicts) exported as PDF for an insurer, police or HOA. This fills our scheduled-reports stub (`o:scheduled_reports.py:419-420` **[V]**).

**VSS pieces:**

- The report template flow and snapshot injection by timestamp (sB `vss-agent-report-generation.mdx:129,246-258,272`).
- Mode B's "incident range" framing.

**Not needed:** the vss-agent runtime (NAT + VIOS) and VA-MCP over ES.

**Lean variant:** yes. Use our llama.cpp, Postgres events and stills. Persist reports; VSS keeps them in memory (`v:release-notes.mdx:136` **[V]**).

#### #5 MCP tool surface (score 10)

**User experience:** power users ask Claude Desktop, or wire Home Assistant or agents, to "list HIGH events at the front door this week".

**VSS pieces:** the VA-MCP tool vocabulary: `get_incident(s)`, `get_sensor_ids`, `get_places`, `analyze` (sB `v:docs/video-analytics-mcp.mdx:21-31`).

**Not needed:** the VA-MCP server itself (ES-bound).

**Lean variant:** reimplement it over Postgres and **add auth**; VSS's has none (sB `Known-Limitations.mdx:14`).

**Note:** this is the substrate for #7. B estimates 300-600 LoC (B§4g) **[A]**.

#### #6 Lean natural-language search + critic (score 8)

**User experience:** "someone carrying a box near the garage last Tuesday" returns events, re-verified by the VLM so obvious mismatches are dropped.

**VSS pieces:**

- The query decomposition into text, time, sources and attributes (sB `agent-workflow-search.mdx:25`).
- The critic's per-criterion confirm/reject (`v:release-notes.mdx:144` **[V]**; B§4g).

**Not needed:** RT-Embed (a 10 GB planning reserve; Kafka required for indexing), ES kNN, RT-CV, VIOS.

**Lean variant:**

- Search over #2's VLM descriptions with our existing Postgres FTS.
- Optionally embed with the SigLIP2 already in our zoo (O6). pgvector is **not** in our Postgres image (`o:docker-compose.prod.yml:55` **[V]**, `postgres:16-alpine`), so either use a flat scan at home scale (vi/07) or add the extension.
- Re-rank with the #1 VLM.
- I = 2 because of the schema and index work.

#### #7 Chat / Q&A over events and clips (score 4.5)

**User experience:** "was anyone at the back door last night?", answered with event links, snapshots and optional visual follow-ups.

**VSS pieces:**

- The agent tool pattern.
- The memory ladder (hot context → structured memory → introspection → fresh VLM run; sB `vss-ask-video/SKILL.md:77-116`), using `InMemoryStore` (`v:memory/service.py:266` **[V]**).
- HITL.

**Not needed:** the VSS default LLM (45 GB INT4, `v:sizing.md:76` **[V]**), ES tools and VST.

**Lean variant:** yes. #5's MCP tools + our llama.cpp with tool calling (Q4 reliability **[?]**, B open question 5).

**F = 3:** tool-calling quality and VRAM contention with #1.

#### #8 Open-vocabulary prompt detection (score 4.5)

**User experience:** detectors defined in words, such as "package", "ladder against the house" or "open garage door".

**VSS pieces:** the prompt-with-threshold syntax (`v:object-detection-tracking.mdx:668-686` **[V]**).

**Not needed:** RT-CV. It is video-only, an 18 GB image, and uses NGC TAO weights.

**Lean variant:** wire YOLO-World, which is already in our zoo (`o:model_zoo.py:17` **[V]**) but only used by unwired package tracking. Or fold into #3.

---

## 8. Attractive but wrong for us (traps)

| Feature                                           | Why it attracts                                           | What it drags in or requires                                                                                                                                |
| ------------------------------------------------- | --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| VSS search as shipped (F17/F18)                   | The headline "search your video in natural language"      | ES + Kafka + Logstash + RT-Embed + RT-CV + VIOS. **2 GPUs** stock. Alpha quality. 48 h embedding life. Stills never indexed.                                |
| Real-time VLM alerts (F10)                        | The most natural UX in VSS                                | **RTSP required**, continuous VLM, H100×2, Kafka + ES                                                                                                       |
| Alert Bridge as a drop-in verifier (F7/F8)        | It is literally "VLM verifies alerts", with an image mode | Kafka-only + ES-mandatory since 3.3.0 (`v:release-notes.mdx:32-42` **[V]**). Verdicts go to ES, not the HTTP reply. **Adopt the pattern, not the service.** |
| LVS service (F13)                                 | "Summarize hours of video"                                | Video-only `MediaType`, ES default, one request at a time, heavy LLM. Our clips are short, so F1 chunking covers them.                                      |
| Live-stream summarization (F14)                   | Rolling "what happened this hour"                         | Kafka hard-required (400 otherwise), RTSP, Early Access                                                                                                     |
| LVS Q&A (F15)                                     | Q&A over summaries                                        | Graph DB you deploy and operate yourself                                                                                                                    |
| Omni audio (F16)                                  | Glass break, alarms, dogs: a real home signal we lack     | NVFP4 29.1 GB > 27.2, so **no consumer card**. Remote-only in VSS's base profile. Watch for a smaller Omni.                                                 |
| Behavior analytics (F32)                          | Tripwires, loitering, restricted zones                    | Continuous tracks (0.5 s gap window). Impossible on FTP stills at defaults. Needs RT-CV.                                                                    |
| VIOS (F37)                                        | DVR, recording, replay, ONVIF                             | RTSP ingest decision first (O4 is dormant). Postgres + Redis + SDR + ingress. Foscam untested.                                                              |
| Kibana dashboards (F38)                           | Free dashboards                                           | ELK + 4 h ILM. We already have Grafana.                                                                                                                     |
| RT-Embed (inside F17)                             | Cosmos-Embed1 ungated and anomaly-tuned                   | A 10 GB planning reserve; Kafka for indexing; video-chunk embeddings in a different space from our CLIP (B "Looks reusable")                                |
| 3D / MV3DT, SOP, smart city, warehouse, occupancy | Impressive demos                                          | Synchronized 30 FPS calibrated cameras, industrial semantics. Residential mismatch.                                                                         |

---

## 9. Contradictions

### 9.1 With `docs/vss-integration/` at `1e94133b4`

1. **"Two vLLM engines cannot share one GPU at all" is wrong as a general statement.** Claimed in vi/04:98-110, vi/05:253-261 and vi/07:456-458.
   - The quote moved to `v:deploy/docker/scripts/dev-profile.sh:1206-1216` **[V]**, inside the _Search-on-edge_ block measured on AGX Thor.
   - VSS ships a one-GPU shared LLM + RT-VLM at `0.40 + 0.40` (`v:sizing.md:98-100,106,109` **[V]**; base and lvs "Shared GPU = 1" at `v:prerequisites.mdx:337-338` **[V]**) and GB300 at 0.3 + 0.2 (`v:sizing.md:136-142` **[V]**).
   - VSS also disagrees with itself on the mechanism: `dev-profile.sh:1211-1213` vs `sizing.md:141-142` **[V]**.
   - The consumer blocker is capacity (a ≥32 GB LLM NIM floor, the 0.7 default reservation), not topology. Agrees with B.
2. **RT-Embed "fixed 10 GB, no knob"** (vi/03, vi/04:83).
   - It is "Reserve about 10 GB", a planning reserve (`v:sizing.md:290-291` **[V]**).
   - Precision knob: `COSMOS_EMBED1_TRT_PRECISION` int8/fp8 (`v:docs/real-time-embedding.mdx:351` **[V]**). The batch size auto-drops on small cards (B§3e).
   - Weights are 2.39 GB **[E]**. "No 4-bit" still holds.
3. **RT-CV "≈3.0 GB (1.7-4.5)" and "95-96% SM at 2-3 streams"** (vi/03:247-249, vi/04:82,114, vi/05:334).
   - 1.7 GB is an illustrative render box in a skill template (`v:skills/deployment/vss-deploy-detection-tracking-2d/references/next-steps.md:217-218` **[V]**).
   - 95% is DGX Spark data (`v:docs/performance-rt-cv.mdx:66-67` **[V]**); L40S runs 15 streams at 87% (`:57` **[V]**).
   - Treat both as **[?]**.
4. **RTX PRO 4500 "one row"** (vi/04:115-116). It now has two rows (`v:prerequisites.mdx:370-380` **[V]**), both needing 2 GPUs with a remote LLM, and the card is restricted to alerts (commit `979ab595a` **[V]**).
5. **"Always-on" alert route** (vi/05:276-277, marked [A]). It means rules auto-attach to newly added streams (`v:release-notes.mdx:161,170-172` **[V]**; `v:alert-verification-service.mdx:76` **[V]**), not model residency. The residency point still stands, on different evidence (`v:docs/real-time-vlm.mdx:1535-1536` **[V]**; B§1f).
6. **"Redis Streams already first-class"** (vi/03:278, vi/07:382-383).
   - False for Alerts since 3.3.0 (`v:release-notes.mdx:32-36` **[V]**).
   - Still true for RT-VLM and behavior analytics as producers or consumers, but no Redis consumer exists end to end (B§6).
7. **"Swapping the bus does not remove ES"** (vi/07:385-387). True for alerts, lvs and search, but the warehouse Redis `*_MINIMAL` variant has no ELK (`v:.../warehouse-operations/overrides.env:294-296` **[V]**).
8. **Cosmos3 Edge "zero VSS coverage"** (vi/04:139-140). It now has engine tests and two doc-table rows (`v:docs/real-time-vlm.mdx:1464,1486` **[V]**; commit `a8f3549c8` **[V]**). It is still absent from the supported-models table and from sizing.
9. **"CR1 unsupported in VSS 3.3 (`:18`)"** (vi/04:133). The line is gone, and CR1 7B fp8 is listed (`v:docs/real-time-vlm.mdx:85` **[V]**).
10. **The README NVFP4 recipe still fails** (`v:services/rtvi/rt-vlm/README.md:804-810` **[V]**; `model_path_policy.py:41-55` **[V]**). vi/04's fix variable `RTVI_VLM_MODEL_PATH_ALLOWLIST` works only through the dev-profile compose (`v:deploy/docker/services/rtvi/rtvi-vlm/rtvi-vlm-docker-compose.yml:77` **[V]**). The standalone compose reads `RTVI_MODEL_PATH_ALLOWLIST` (`v:services/rtvi/rt-vlm/docker/compose.yaml:43` **[V]**).
11. **vi/07's "Vector ANN not needed"** remains true for LVS (`LVS_EMB_ENABLE=false`, `v:docs/long-video-summarization.mdx:922-925` **[V]**). Search, however, makes ES kNN load-bearing (sB `dev-profile-search/.env:60`).
12. **vi/05's "industry profiles: warehouse-operations and others."** Exactly two exist in-repo (smartcities, warehouse-operations). Public safety is NGC-distributed (sC).
13. **vi/06 §4 "RT-VLM accepts image mode"** is confirmed (`v:docs/real-time-vlm.mdx:125-126` **[V]**). The plan to demand `response_format: json_schema` works only in integrated mode (B contradiction 9).
14. **Line drift** (no change in substance):
    - hallucination warning `:93→:91`
    - Omni flags `:97→:95`
    - EVS numbers `README.md:838-843→:795-800`
    - our Redis pin `docker-compose.prod.yml:562→:570`

### 9.2 With the owner's framing and our own docs

1. **"LRU model eviction" as a production differentiator does not hold.**
   - The production AI gateway runs Triton with `--model-control-mode=none`, which loads everything at start (`o:ai/gateway/entrypoint.sh:126-131` **[V]**).
   - The LRU manager lives in the standalone enrichment server, which is not a prod compose service (sD `ai/AGENTS.md`).
   - The real duty cycle is backend load-use-unload (`o:model_zoo.py:565-580` **[V]**) plus batching.
   - B also lists "our model_zoo LRU" as a contribution, so this correction applies there too.
2. **"Proven on one A5500" is not today's topology.**
   - Production is two GPUs: LLM on GPU 0 (A5500), AI services on GPU 1 (A400) (`o:docker-compose.prod.yml:139,153,159,322-323,351` **[V]**).
   - The 30B Q4 LLM alone (21.7 GB) exceeds the 24 GB card's 0.85 budget **[C]**.
3. **"No RTSP ingest service"** is true in effect, false in letter. go2rtc runs for viewing, and an RTSP `StreamManager` exists but is dormant (O4). This agrees with B's contradiction 17.
4. **Several documented features are not wired:**

   - alert-rule evaluation (O25)
   - email and push (O28)
   - MQTT and Home Assistant (O29)
   - feedback learning (O36; `o:docs/ui/settings.md:317` claims it)
   - scheduled reports (O30)
   - heatmaps and analytics zones (O24, O31)

   Imports #1 and #3 give the rules engine and the feedback path a reason to be wired. VLM verdicts are natural training signal for O36 **[A]**.

### 9.3 VSS internal inconsistencies worth knowing

- **NVFP4 hardware:** "requires Blackwell-class" (`v:rt-vlm.md:56-58` **[V]**) vs "Orin NX: NVFP4-only" (`v:real-time-vlm.mdx:92` **[V]**).
- **Alerts and Redis:**
  - The Alerts skill says it "requires Redis" (sA `alerts.md:24`), but the release notes say no Redis (`v:release-notes.mdx:32` **[V]**).
  - The service docs call ES "optional" (sA `alert-verification-service.mdx:106`), but compose makes ES a hard dependency (`v:deploy/docker/services/alert/compose.yml:105-110` **[V]**).
- **LVS input:** the form help says "image / video" (`via_server.py:390`), but `MediaType` is VIDEO only (`v:vss_api_models.py:120-123` **[V]**).

---

## 10. Cross-check with Auditor B (`09-audit-integration-surfaces.md`)

**Agreement on every infrastructure claim this report depends on:**

- RT-VLM (and RT-Embed) run with zero Kafka and zero ES (B headline 4, §6).
- Alert Bridge requires Kafka + ES (B§5c).
- Every VSS read path needs ES.
- No VSS model service has an unload path (B headline 3).
- The two-vLLM claim is withdrawn (B headline 5).
- The RT-CV 3.0 GB / 95% and RT-Embed 10 GB figures are template or planning numbers (B§2e, §3e).
- LVS is video-only (B§7).
- The Alerts microservice no longer uses Redis.

**Where this report differs, or adds:**

1. **LRU.** B lists "our `model_zoo` LRU" as something we bring. Prod does not run it (§9.2.1). The accurate claim is event-triggered batching plus in-process load-use-unload, plus llama.cpp sleep/unload **[E]**.
2. **Unit of value.** B ranks constrained decoding for our risk JSON as its #1 technology. I treat it as the **prerequisite** for my #1, not as a user feature. We do not disagree.
3. **Engine choice for #1.** B prefers llama.cpp multimodal (mtmd) over the RT-VLM container for duty-cycling reasons. I keep both as lean variants:
   - RT-VLM is the upstream-legible choice, but it is always-on and reserves 0.7 by default.
   - llama.cpp keeps our sleep/unload differentiator.
   - The choice is **[?]** until the boring-frames test (vi/06 §4) compares them.
4. **Stills in LVS.** Slice A initially read `via_server.py:390` as image support. B's `MediaType` finding is correct and adopted here.
5. **RTSP.** B's correction 17 is adopted. This report adds that `StreamManager` has no runtime importer (O4), which lowers the cost of stream features without making them "free".

---

## 11. Open questions

1. Does NVFP4 (or FP8) compute on the A5500's sm_86 in RT-VLM's pinned vLLM? VSS contradicts itself (§9.3). BF16/GGUF avoid the question **[?]**.
2. **Salience**, the only test that matters. On the 50-boring-frames + 5-incidents set, which VLM gives the best confirm/reject accuracy? Candidates: Cosmos3-Edge, Qwen3-VL-4B/8B, Nemotron-12B-VL. Does a constrained `choice` beat free text **[?]**?
3. Single-card topology for #1-#3:

   - (i) one VL model also producing the risk JSON;
   - (ii) VLM + 4B text LLM;
   - (iii) llama.cpp router swapping.

   What is (iii)'s swap latency per event **[?]**?

4. Can RT-VLM start beside a resident llama.cpp? The vLLM free-memory accounting is disputed in-tree (§9.1.1) **[?]**.
5. Do Foscam clips carry audio, and would a sub-20 GB Omni ever ship **[?]**?
6. Do the RT-CV TAO weights and the `nvstaging` mirrors download anonymously **[?]** (mirrors: 401 **[E]**)?
7. Is there a release (non-`develop`) tag line on ghcr, or are releases NGC-only? `README.md:105` says official releases are on NGC **[?]**.
8. Redistribution: Apache-2.0 source vs the Evaluation license on images vs "AI Enterprise to self-host NIM" (`v:README.md:99` **[V]**). This is a legal question **[?]**.
9. The biometric data model (vi/03 Q7). It becomes more pressing if VLM descriptions start naming people **[?]**.
10. Should the O36 feedback loop consume VLM verdicts, or only human feedback? It is a product decision, and it changes what "calibration" means **[?]**.

---

## Appendix A: citations re-read personally (spot-verification of slice work)

**VSS:**

- `README.md:5-11,40-49,99,105,126-137`
- `docs/index.mdx:5-13,20-43,55-65,82-83`
- `docs/release-notes.mdx:8-66,74-80,84-150,151-176`
- `docs/real-time-vlm.mdx:10-30,60-100,120-142,990-996,1200-1210,1455-1490,1530-1537`
- `docs/prerequisites.mdx:293,304,307,333-345,368-390`
- `docs/agent-workflow-alert-verification.mdx:6-12,29-32`
- `docs/performance-alert-verification.mdx:30-40,108-114`
- `docs/long-video-summarization.mdx:8-26,43-60,910-926,1168-1173`
- `docs/agent-workflow-search.mdx:725-731`
- `docs/agent-workflows.mdx:10-22`
- `docs/vss-ui.mdx:360-364`
- `docs/vss-agent/VSS-Agent-Profiles.mdx:158-176`
- `docs/vss-agent/configure-vlm.mdx:195-215`
- `docs/behavior-analytics.mdx:270-281,1075`
- `docs/elk.mdx:215-232`
- `docs/object-detection-tracking.mdx:96-100,668-686`
- `docs/vios-microservices.mdx:586-600`
- `docs/performance-rt-cv.mdx:52-70`
- `docs/agent-workflow-rt-alert.mdx:150-156`
- `docs/alert-verification-service.mdx:74-77`
- `skills/README.md:1-60`
- `skills/vss-build-vision-ai/references/credentials.md:1-142`
- `skills/vss-build-vision-ai/references/services/sop.md:1-80`
- `skills/vss-build-vision-ai/references/services/rt-vlm.md:50-62`
- `skills/vss-build-vision-ai/references/sizing.md:39,56-92,95-112,136-146,165-196,280-322`
- `skills/operations/vss-manage-alerts/references/on-demand-verification.md:1-45`
- `skills/deployment/vss-deploy-detection-tracking-2d/references/next-steps.md:210-220`
- `services/alert/config.yaml:296-302,360-373`
- `deploy/docker/services/alert/compose.yml:100-112`
- `deploy/docker/scripts/dev-profile.sh:1190-1225`
- `deploy/docker/industry-profiles/warehouse-operations/overrides.env:294-297`
- `deploy/docker/containers.env` (registry lines)
- `deploy/docker/container-inventory.json`
- `services/rtvi/rt-vlm/src/api_models/captions.py:98-107`
- `services/rtvi/rt-vlm/README.md:795-812`
- `services/rtvi/rt-vlm/src/vlm_pipeline/model_path_policy.py:41-56`
- `services/rtvi/rt-vlm/docker/compose.yaml:42-43`
- `deploy/docker/services/rtvi/rtvi-vlm/rtvi-vlm-docker-compose.yml:77`
- `services/rtvi/rt-vlm/tests/model/vllm_compatible/test_input_error_handling.py:370-390`
- `services/video-summarization/src/via_server.py:1029-1036`
- `services/video-summarization/src/vss_api_models.py:118-124`
- `libs/vss/core/src/vss_core/memory/service.py:264-268`
- `store.py:165-170`
- git log since 2026-09-12

**Ours:**

- `ai/gateway/entrypoint.sh:120-134`
- `docker-compose.prod.yml:55,136-160,318-352 (GPU lines),570`
- `backend/services/model_zoo.py:8-42,560-582`
- `backend/services/file_watcher.py:68-72`
- `backend/core/config.py:958-976,2393-2413`
- `backend/services/enrichment_pipeline.py:2502-2512,5903-5910`
- `backend/services/batch_aggregator.py:1338-1346`
- `backend/api/routes/scheduled_reports.py:416-421`
- `backend/services/prompts.py:1016-1019`
- `backend/services/degradation_manager.py:66-75`
- `backend/models/event_feedback.py:110-116`
- `docs/ui/settings.md:315-318`
- `backend/api/routes/events.py:1028-1032`
- `backend/services/search.py:1-10`
- `frontend/src/App.tsx:230-305`
- `backend/services/stream_manager.py:1-30`
- `backend/models/enums.py:98-103`
- `docs/ui/dashboard.md:176-181`
- Non-importer greps: `evaluate_event`, `create_alerts_for_event`, `mqtt_publisher`, `ha_discovery`, `FeedbackProcessor`, `match_face`, `record_face_detection`, `deliver_alert`, `StreamManager`, YOLO-World callers

## Appendix B: external read-only queries (**[E]**)

- **GHCR anonymous pull check:**
  - `curl -s "https://ghcr.io/token?scope=repository:nvidia-ai-blueprints/vss/<img>:pull"` then `GET /v2/nvidia-ai-blueprints/vss/<img>/tags/list?n=200`.
  - Every image returned 200 tags except reid-embed, vss-video-analytics-ui and vss-auto-calibration, which returned NAME_UNKNOWN.
- **NGC:**
  - `curl -s "https://nvcr.io/proxy_auth?scope=repository:<path>:pull"` then `GET /v2/<path>/tags/list`.
  - 401: `nvidia/vss-core/calibration`, `nvidia/vss-core/vss-rt-vlm`, `nvstaging/vss-core/{reid-embed,vss-video-analytics-ui}`, `nim/nvidia/cosmos3-nano-reasoner`.
  - 200: `nim/nvidia/nemotron-3.5-lightning-30b-a3b`, `nvidia/vllm`.
- **HuggingFace:** `curl -s "https://huggingface.co/api/models/<repo>?blobs=true"`, reading `.gated` and the sum of `*.safetensors` sizes.

  | Repo                                       | gated  |    GB |
  | ------------------------------------------ | ------ | ----: |
  | Cosmos-Embed1-448p                         | false  |  2.39 |
  | Cosmos-Embed1-448p-anomaly-detection       | false  |  4.79 |
  | Cosmos-Reason2-2B                          | "auto" |  4.88 |
  | Cosmos-Reason2-8B                          | "auto" | 17.53 |
  | Nemotron-3-Nano-Omni-30B-A3B-Reasoning-FP8 | false  | 35.19 |
  | …-NVFP4                                    | false  | 22.41 |
  | NVIDIA-Nemotron-Nano-12B-v2-VL-NVFP4-QAD   | false  | 10.60 |
  | NVIDIA-Nemotron-3-Nano-4B-FP8              | false  |  5.27 |
  | Cosmos3-Edge                               | false  |  9.13 |
  | Qwen3-VL-8B-Instruct                       | false  | 17.53 |
  | Qwen3-VL-8B-Instruct-FP8                   | false  | 10.59 |
  | Qwen3-VL-4B-Instruct                       | false  |  8.88 |

  Cosmos3-Nano-Reasoner and Cosmos3-Super-Reasoner returned 401.

- **llama.cpp server README:** sleep-idle, router `--models-dir`/`--models-max`, and experimental multimodal. Scratchpad copy `llamacpp-server-README.md:14,178,227-229,244,337-339`; upstream `https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md`. The version in our image is **[?]**.

---

## Addendum (2026-09-23): NemoClaw, missed by all three auditors

Verified in-session after the three audits, against VSS `1e94133b4`. It is added here because
NemoClaw is VSS's **default agent harness** (commit `0445f3239`, "docs: default agent harness to
NemoClaw and OpenClaw"), and 151 files mention it.

### What it is **[V]**

- An "open-source reference stack for running always-on AI agents more safely inside NVIDIA
  OpenShell sandboxes" (`docs/nemoclaw.mdx:6`). It onboards a harness, **OpenClaw or Hermes**,
  that gives a chat UI for _operating_ VSS through natural language ("deploy the alerts profile",
  "show me the vss-alert-bridge logs").
- The harness runs on VSS's skills, workspace bootstrap docs and a policy preset, plus a host-side
  **VSS Orchestrator MCP** server on port `9988` with nine `vss_orchestrator__*` tools: compose
  generation, compose operations, container inspection and logs (`docs/nemoclaw.mdx:44`).
- The notebook route is Early Access (`docs/nemoclaw.mdx:22`).
- The agent model is a **separate surface** from the VSS stack's LLM/VLM
  (`docs/nemoclaw-configuration.mdx:114-118`).

### Model providers **[V]**

| Setting                    | Value                                                                                                                                  | Citation                                                                                           |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `NEMOCLAW_PROVIDER`        | `custom` (any OpenAI-compatible base URL), the NemoClaw-managed `install-vllm` / `ollama` / `nim-local`, or `build` (build.nvidia.com) | `docs/nemoclaw-configuration.mdx:51`                                                               |
| `COMPATIBLE_API_KEY`       | Bearer token for `custom`; `EMPTY` for a self-hosted endpoint that ignores auth                                                        | `:54`; "cloud or local OpenAI-compatible endpoint" at `docs/nemoclaw-deploy-vss-and-skills.mdx:44` |
| `NEMOCLAW_MODEL` default   | `aws/anthropic/bedrock-claude-opus-5`, a frontier model, on an NVIDIA-internal endpoint                                                | `:52-53`                                                                                           |
| `NEMOCLAW_TOOL_DISCLOSURE` | Defaults to `direct` for Nemotron 3.5 Lightning, the tuned local option                                                                | `:63`                                                                                              |
| Skill-eval runtimes        | `("claude-code", "codex", "nemoclaw")`, so VSS's harness can score a model _as NemoClaw's agent model_                                 | `.github/skill-eval/model_config.py:12`                                                            |

### Can our single VLM also be NemoClaw's model?

**Mechanically, yes, through the llama.cpp engine only.**

- NemoClaw's `custom` provider accepts our `ai-vlm` endpoint. All three VLM candidates ship chat
  templates with tool calling **[E]**:
  - `nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-BF16` `chat_template.jinja` (tools plus `enable_thinking`)
  - `Qwen/Qwen3-VL-8B-Instruct` and `Qwen/Qwen3-VL-4B-Instruct` `chat_template.json`
- **RT-VLM cannot.** Its request models are `extra="forbid"`, so a request carrying
  `tools`/`tool_choice` returns 422 ([`09`](09-audit-integration-surfaces.md) §1b) **[V]**.

**Caveats:**

1. **Capability gap [A].** VSS defaults to a frontier model and tunes only down to Lightning
   30B-A3B. A 4-12B VLM driving a multi-step tool-calling agent is a large step down. It is
   measurable with VSS's own skill-eval `nemoclaw` runtime.
2. **Contention [A].** Agent sessions carry large contexts on the server that must return per-event
   verdicts within the design's 30 s p95.
3. **Reachability [V].** The sandboxed agent must reach the endpoint. This repo binds services to
   `127.0.0.1` as its primary security boundary (root `AGENTS.md`).
4. **Parsing [?].** Whether llama.cpp's tool-call parser handles the Nemotron-VL template at our
   pinned `b7972` is unverified.

**Disposition:** postponed. See [`12-postponed-roadmap.md`](12-postponed-roadmap.md). To keep the
option open, the design adds "tool calling through llama.cpp works" and long-context cost to the
VLM bake-off criteria.
