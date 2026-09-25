# 08 — Audit: VSS Profile Anatomy, GPU Placement, Arch Support, CI

> **Provenance.** Independent read-only audit by a research subagent ("Auditor A") on
> 2026-09-23, against VSS `1e94133b4` (`origin/develop`; 78 commits after the `cdad5cc0e`
> baseline that docs 00-07 cite). Scope: profile anatomy, dev-profile.sh placement, GPU/CPU architecture support, image availability, CI, contribution. Evidence markers follow [`AGENTS.md`](AGENTS.md).
> Corrections it raises against docs 00-07 are consolidated in
> [`11-errata-2026-09-23.md`](11-errata-2026-09-23.md). The design it fed is
> [`2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md).
> Line citations resolve at `1e94133b4`; VSS moves fast, so re-verify before relying on one.

**Audited:** `NVIDIA-AI-Blueprints/video-search-and-summarization` `origin/develop` = `1e94133b4`
(2026-09-23), in the detached worktree `.../scratchpad/vss-head`. Prior research audited
`cdad5cc0e` (2026-09-19). All `path:line` citations below are at `1e94133b4` unless marked
otherwise. Our-repo citations are prefixed `ours:`.

**Scope:** profile anatomy, GPU placement, hardware and arch support, CI, and contribution
process. Component APIs belong to Auditor B and are touched only where a question needs them.

**Evidence markers:** **[V]** verified with a `path:line` read in-session · **[C]** computed,
with formula shown · **[E]** external, with the command or URL · **[?]** open · **[A]** inferred,
not verified · **[O]** stakeholder statement (inherited from prior docs; not re-verifiable here).

---

## 0. Top findings (one screen)

1. **"Two vLLM engines cannot share one GPU" is not a VSS-wide rule.** It is a _comment_ inside
   the DGX-Spark/AGX-Thor **search** block (`deploy/docker/scripts/dev-profile.sh:1211-1216`,
   moved from `:1161-1165`). VSS ships and measures vLLM-LLM + vLLM-RT-VLM on one GPU on H100,
   RTX PRO 6000, OTHER and GB300 (`services/nim/nemotron-3.5-lightning-30b-a3b/hw-OTHER-shared.env:4-6`,
   `skills/vss-build-vision-ai/references/sizing.md:98-100,112-142`). The only enforced
   same-GPU prohibition is **L40S** (`dev-profile.sh:1376-1387`). The file also contradicts
   itself about vLLM memory semantics (`:611-613` versus `:1212-1214`). **[V]**
2. **The 32 GB RTX PRO 4500 is not a single-card tier.** Since `cdad5cc0e`, `dev-profile.sh`
   enforces alerts-only, `--use-remote-llm`, **at least 2 GPUs**, and driver ≥ 595.58.03
   (`:1037-1051`, `:1161-1179`). The smallest VRAM that VSS validates is therefore 2×32 GB with
   the LLM remote, or 1×48 GB L40S with at least one model remote (`docs/prerequisites.mdx:370-395`). **[V]**
3. **dev-profile.sh never measures memory.** Its only `nvidia-smi` queries are name, index and
   driver (`:86,88,97,131,159,1172`). Placement is table-driven by `HARDWARE_PROFILE`, so a
   co-resident llama.cpp is invisible at deploy time. vLLM's startup reservation check sees it
   at runtime, and so does the RT-VLM live-stream guard (`services/rtvi/rt-vlm/src/server/rtvi_stream_handler.py:1556-1582`). **[V]**
4. **Remote OpenAI-compatible LLM is first-class.** Use `--use-remote-llm` +
   `LLM_ENDPOINT_URL` + `--llm-model-type openai`. That yields `LLM_NAME_SLUG=none` and the
   compose key `llm_remote_none` (no container). The agent then calls `${LLM_BASE_URL}/v1`
   (`dev-profile.sh:887-891,1287-1288,1826-1838,1889-1897`;
   `developer-profiles/dev-profile-alerts/vss-agent/configs/config.yml:211-214`). **[V]**
5. **Single-GPU alerts/search on a discrete card is blocked by the profile `.env` files, not by
   memory.** Alerts reserves GPU 0 (`dev-profile-alerts/.env:39`) and search pins two GPUs
   (`dev-profile-search/.env:48-50`). Only GB300 and the edge boards are exempt
   (`dev-profile.sh:1392`). **GB300 is the only existing single-discrete-GPU template.**
   Its code paths are the blueprint for a consumer tier. **[V]**
6. **Arch:** every GPU image is CUDA 13.x. The RT-VLM, RT-CV and RT-Embed bases carry
   `CUDA_ARCH_LIST=7.5 8.0 8.6 9.0 10.0 12.0`: sm_86 native, sm_120 native, **no 8.9**
   (sm_89 runs sm_86 SASS). RT-CV and RT-Embed build TensorRT engines **at runtime** on the
   target GPU. Nothing in the tree deny-lists GeForce. An unknown GPU maps to `OTHER`
   (`dev-profile.sh:136-149`), which bypasses the name check (`:1135-1138`). **[E]/[V]**
7. **RTX 4090 CI:** the tables are still empty (`.github/skill-eval/run_leg.py:62-63`), but
   history matters. PR #1339 populated them on 2026-07-20, including base/LVS/alerts
   deploy-profile tests on 24 GB, and #1406 emptied them on 2026-07-24. NVIDIA operates
   **three 1×GeForce RTX 4090 self-hosted runners**. The open PR #1466 describes them, and a
   HEAD test calls the pool "dead weight until a spec-level `gpu_type` route is wired"
   (`.github/skill-eval/tests/test_run_leg.py:1932-1940`). **[V]/[E]**
8. **All managed VSS images are anonymous on GHCR** with amd64+arm64 (and `-sbsa` arm64 tags).
   Gated: the `cosmos3-reasoner` NIM, `nvstaging/*` images, `nvidia/vss-core/*` release images,
   and runtime NGC model downloads. Notably, **dev-profile.sh hard-requires `NGC_CLI_API_KEY`
   even for an all-remote deployment** (`:973-976`) and always runs `docker login nvcr.io`
   (`:2207-2216`). **[E]/[V]**

---

## 1. Profile anatomy

### 1.1 The kinds of "profile" in VSS

| #   | Kind                                                                                                                                                                  | Where                                                                                                                                                                                   | What selects it                                                                                                                                                         | Enforced by                                                                                                                                                                        |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P1  | **Developer profile** (`base`, `lvs`, `alerts`, `search`)                                                                                                             | `deploy/docker/developer-profiles/dev-profile-<name>/`                                                                                                                                  | `dev-profile.sh -p <name>` (`:979`); direct Compose `--env-file`; skill "Foundation"                                                                                    | `check_folder_structure.py:33-42` (dir name), `_valid_profiles` (`dev-profile.sh:979`), include list `developer-profiles/compose.yml:16-33`                                        |
| P2  | **Industry profile** (`warehouse-operations`, `smartcities`)                                                                                                          | `deploy/docker/industry-profiles/<name>/`                                                                                                                                               | `scripts/blueprint-deploy.sh` (`-d/-m/-p/-H`)                                                                                                                           | Only warehouse is included in the root graph (`industry-profiles/compose.yml:16-17`). The skill supports only warehouse (`skills/vss-build-vision-ai/SKILL.md:29,81`)              |
| P3  | **Hardware profile** (`HARDWARE_PROFILE` ∈ H100, GB300, L40S, RTXPRO4500BW, RTXPRO6000BW, DGX-SPARK, IGX-THOR, AGX-THOR, OTHER; `RTXPRO6000BW-SE` for warehouse only) | `services/nim/<model>/hw-<HW>.env` + `hw-<HW>-shared.env`; case tables in scripts                                                                                                       | `-H` flag or `HARDWARE_PROFILE=` in `overrides.env` (`dev-profile-alerts/overrides.env:26`)                                                                             | `_valid_hardware_profiles` (`dev-profile.sh:1031`), orchestrator key set (`services/agent/.../orchestrator/docker_compose_util.py:739-740`), Compose `env_file` path interpolation |
| P4  | **Compose service profile keys** (`COMPOSE_PROFILES`)                                                                                                                 | `profiles: [...]` on every service; 98 distinct keys **[C: grep count]**                                                                                                                | `COMPOSE_PROFILES=` in `overrides.env` (e.g. `dev-profile-base/overrides.env:199`); LLM key is templated `llm_${LLM_MODE}_${LLM_NAME_SLUG}`                             | Compose itself; dev-profile.sh rewrites the value for alerts real-time (`:1816`), edge search (`:2074-2086`) and base (`:2091-2099`)                                               |
| P5  | **Foundation** (skill concept)                                                                                                                                        | `skills/vss-build-vision-ai/references/composition.md:14-24`                                                                                                                            | The Build-Vision-AI skill picks the closest developer profile and writes a **Delta** to `_builds/<name>/{override.env,compose.yml,patches/}` (`composition.md:170-240`) | Skill validators (`scripts/validate_resolved_yml.py`). **No GPU checks** (grep: no device or GPU logic)                                                                            |
| P6  | **Helm profiles**                                                                                                                                                     | `deploy/helm/developer-profiles/dev-profile-<name>/` (Chart.yaml, values.yaml, `values-<variant>.yaml`, templates/, configs/) and `deploy/helm/industry-profiles/warehouse-operations/` | `helm install -f values.yaml -f values-<variant>.yaml`; GPU tuning via `nims.gpuType` → `deploy/helm/services/nims/values.yaml:43,50-134` (`gpuProfiles.<HW>`)          | `.github/workflows/helm-sync.yml` (LLM-agent parity gate, see §5)                                                                                                                  |

Correction to prior docs: the "Foundations: alerts, search, warehouse, public safety, smart
city" list in `05-hardware-profiles.md` is inaccurate. The Foundations are exactly `base`,
`alerts`, `lvs` and `search` (`composition.md:20-24`). Warehouse is an industry profile and
is not composable (`composition.md:26-31`). "Public safety" is a behavior-analytics app
(`docs/behavior-analytics.mdx:2612`), not a profile. **[V]**

### 1.2 Directory layout and file contents

**P1 developer profile** (e.g. `dev-profile-alerts`, 22 files; `base` 8; `lvs` 11; `search` 20) **[V]**:

```
dev-profile-<name>/
├── compose.yml          # profile-only services that `extends:` shared services (alerts: dev-profile-alerts/compose.yml:16-72)
├── .env                 # stable defaults: BP_PROFILE, RESERVED_DEVICE_IDS, FIXED_SHARED_DEVICE_IDS,
│                        #   RT_CV_DEVICE_ID/RT_EMBED_DEVICE_ID, broker type, UI flags (dev-profile-alerts/.env:36-100)
├── overrides.env        # mutable template: HARDWARE_PROFILE, *_DEVICE_ID, LLM_/VLM_ MODE/NAME/SLUG/BASE_URL/MODEL_TYPE,
│                        #   RTVI_* sizing, host paths, ports, creds, COMPOSE_PROFILES (dev-profile-alerts/overrides.env:13-252)
├── generated.env        # written by dev-profile.sh (gitignored: .gitignore:17)
├── user-overrides.env   # gitignored overlay for direct Compose (deploy/docker/README.md:24-25,41-49)
├── vss-agent/configs/   # agent graph (llms: nim_llm / openai_llm: dev-profile-alerts/vss-agent/configs/config.yml:202-214)
├── deepstream/, models-download.json, vios/, vlm-as-verifier/, kibana-dashboard/, Dockerfiles/  (per profile)
```

**P3 hardware profile**, per model directory under `deploy/docker/services/nim/` **[V]**:

| Model dir                                | hw files present                                                                                                         | What they contain                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `nemotron-3.5-lightning-30b-a3b/`        | AGX-THOR, DGX-SPARK, GB300, H100, IGX-THOR, OTHER, RTXPRO6000BW (each ± `-shared`); L40S and RTXPRO4500BW dedicated only | `NIM_KVCACHE_PERCENT`, `NIM_GPU_MEM_FRACTION` (0.3), `NIM_MAX_MODEL_LEN=65536`, `MAX_JOBS`, `NIM_PASSTHROUGH_ARGS` (parsers, `--max-num-seqs 8`), and **the same** pinned `NIM_MODEL_PROFILE=2ef85c…` INT4 profile everywhere (`hw-OTHER-shared.env:7-24`). The comment says the INT4 profile has "`min_vram_per_device_gb: 32.0` and no GPU allow-list" (`hw-AGX-THOR.env:21-25`). `hw-RTXPRO4500BW.env` is now **unreachable**, because RTXPRO4500BW requires a remote LLM (`dev-profile.sh:1046-1049`) |
| `nvidia-nemotron-nano-9b-v2-fp8/`        | AGX-THOR, DGX-SPARK, IGX-THOR, OTHER (± `-shared`). **No H100/L40S/RTXPRO/GB300 files**                                  | Raw vLLM. Compose honors exactly `NIM_GPU_MEM_FRACTION` (→ `--gpu-memory-utilization`, default 0.85 dedicated, 0.40 shared), `NIM_MAX_MODEL_LEN` and `NIM_MAX_NUM_SEQS` (`compose.yml:43-59,111-127`). Every file except `hw-OTHER-shared.env` is comment-only                                                                                                                                                                                                                                            |
| `cosmos3-reasoner/` (standalone VLM NIM) | DGX-SPARK, H100, OTHER, RTXPRO6000BW (± `-shared`); L40S dedicated                                                       | `NIM_GPU_MEMORY_UTILIZATION`, `NIM_MAX_MODEL_LEN`, `NIM_MAX_NUM_SEQS`, a pinned BF16 `NIM_MODEL_PROFILE`                                                                                                                                                                                                                                                                                                                                                                                                  |
| `nim.env`, `fallback-override.env`       | —                                                                                                                        | Shared ports (`nim.env:5-8`); `fallback-override.env` is license-only (the default `LLM_ENV_FILE`)                                                                                                                                                                                                                                                                                                                                                                                                        |

The `-shared` variant is selected by **compose service**, not by the script. Each model has
two services: `<model>` with profile `llm_local_<slug>` reads `hw-${HARDWARE_PROFILE}.env`, and
`<model>-shared-gpu` with profile `llm_local_shared_<slug>` reads
`hw-${HARDWARE_PROFILE}-shared.env`, binds `SHARED_LLM_VLM_DEVICE_ID:-LLM_DEVICE_ID`, and
`depends_on` the VLM services becoming healthy (`required:false`). That dependency makes the
VLM reserve memory first (`nemotron-3.5-lightning-30b-a3b/compose.yml:17-106`). **[V]**

### 1.3 How the layers compose

- **Compose include tree:** `deploy/docker/compose.yml:16-19` → `services/compose.yml`
  (agent, alert, infra, nim, rtvi, vios …) + `developer-profiles/compose.yml:16-33` (the four
  profiles, each with extra `env_file`s) + `industry-profiles/compose.yml:16-17`
  (warehouse only). **[V]**
- **Interpolation precedence:** `--env-file containers.env` → `dev-profile-<p>/.env` →
  `generated.env` (later wins) (`dev-profile.sh:2199-2204,2224-2233`;
  `deploy/docker/README.md:15-35`). **The process environment beats every `--env-file`**
  (`dev-profile.sh:1655-1658`). That is the escape hatch for overriding any value
  dev-profile.sh writes. **[V]**
- **Container env:** each service's `env_file:` (for example `hw-*.env`, `LLM_ENV_FILE`)
  sets container env, not Compose interpolation (`nvidia-nemotron-nano-9b-v2-fp8/compose.yml:35-42`). **[V]**
- Env files of _inactive_ services (e.g. `cosmos3-reasoner/hw-GB300.env`, which does not exist)
  are not required, because GB300 deploys without them. **[A]** (strong: GB300 is a shipped
  profile, and `dev-profile.sh:2197-2205` runs `compose config --images` even on dry-run)

### 1.4 Front-ends that consume profiles (and what each enforces)

| Front-end                                             | Hardware validation                                                                                                                      | Where                                                                                                 |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `dev-profile.sh` (developer profiles)                 | Full (§1.5)                                                                                                                              | `deploy/docker/scripts/dev-profile.sh`                                                                |
| Direct Compose + `user-overrides.env`                 | **None**                                                                                                                                 | `deploy/docker/README.md:37-55`                                                                       |
| Build-Vision-AI skill (`_builds/<name>/resolved.yml`) | Prose rules in `sizing.md`. `validate_resolved_yml.py` has no GPU checks. **Bypasses dev-profile.sh** (`references/deployment.md:38-88`) | skill                                                                                                 |
| Orchestrator MCP / NemoClaw                           | Rejects any `HARDWARE_PROFILE` not a key of `hardware_profiles`                                                                          | `deploy/docker/scripts/vss_orchestrator_mcp_config.yml:88-~140`; `docker_compose_util.py:278,739-740` |
| `blueprint-deploy.sh` (industry)                      | Per-HW RT-VLM sizing cases; GB300 name check                                                                                             | `blueprint-deploy.sh:317-335,616-685`                                                                 |
| Helm                                                  | `nims.gpuType` lookup; whole-GPU `nvidia.com/gpu: 1` requests                                                                            | `deploy/helm/services/nims/values.yaml:43,50-134,152-156`                                             |

### 1.5 `dev-profile.sh` end to end (2381 lines)

**Entry:** `validate_args` → `process_args` → `print_args` → for `up`: **`state_down` then
`state_up`** (`:2371-2381`). **Every `up` first runs `state_down`**, which does
`docker compose -p <proj> down -v`, deletes all `generated.env` files, removes dangling
volumes, and `sudo rm -rf` the data dir (`:2243-2369`, especially `:2356-2366`). This is
destructive for a home appliance. **[V]**

**Inputs.** Flags come from `getopt` (`:793`, `:834`): `-p -H -i -e -m -d -h --llm --vlm
--llm-device-id --vlm-device-id --use-remote-llm --use-remote-vlm --llm-model-type
--vlm-model-type --llm-env-file --vlm-env-file --use-sbsa-images`.
`--prebake-vios-packages` is documented (`:743-745`) and handled (`:882-886`) but **missing
from the getopt spec**, so it is rejected as invalid usage.
[V + E: `getopt -q -o p:H:i:e:m:dh --long <same list> -- up --prebake-vios-packages` → exit 1].
Environment inputs:

| Env                                     | Use                                                                    | Line                         |
| --------------------------------------- | ---------------------------------------------------------------------- | ---------------------------- |
| `NGC_CLI_API_KEY`                       | **Required for `up`**, even when all models are remote                 | `:32,973-976`                |
| `NVIDIA_API_KEY`, `OPENAI_API_KEY`      | Copied to generated.env                                                | `:34-35,1898-1900,1947-1949` |
| `LLM_ENDPOINT_URL` / `VLM_ENDPOINT_URL` | Remote endpoints (read only with `--use-remote-*`, or by edge search)  | `:887-896,1233,1239`         |
| `VLM_CUSTOM_WEIGHTS`                    | Local VLM weights dir                                                  | `:1338,1536-1547`            |
| `SKIP_HARDWARE_CHECK=true`              | Skips the nvidia-smi name/count/driver probe                           | `:1138`                      |
| `NIM_MODEL_SIZE`                        | nano/super for the standalone Cosmos NIM                               | `:1924-1926`                 |
| `BREV_*`, `PROXY_PORT`                  | Brev secure links; `BREV_ENV_ID` also gates the search GPU-count check | `:1768-1802,1527`            |
| `VSS_VIOS_PREBAKE_PACKAGES`             | Prebake VIOS                                                           | `:40`                        |
| `INSTALL_PROPRIETARY_CODECS`            | Codecs                                                                 | `:1756`                      |
| `RTVI_VLLM_GPU_MEMORY_UTILIZATION`      | Honored **only for Thor**                                              | `:2035`                      |
| `VSS_CONTAINER_TAG`, `VSS_RT_*_TAG`     | SBSA tag derivation                                                    | `:2172-2181`                 |
| host IP default                         | `ip route get 1.1.1.1` (empty on a host with no default route **[A]**) | `:28`                        |

**Hardware detection** (`:79-180`). `get_detected_hardware_profile` maps the nvidia-smi
product name with case-insensitive globs: `*h100*`, `*gb300*|*b300*`, `*l40s*`,
`*rtx*pro*4500*blackwell*`, `*rtx*pro*6000*blackwell*`, `*gb10*`→DGX-SPARK, `*thor*`→THOR,
and anything else → `OTHER` (`:136-149`). `get_canonical_hardware_profile` aliases
AGX-THOR|IGX-THOR→THOR (`:165-171`). This alias mechanism is reusable for a VRAM-class tier
covering several SKUs. The name check runs unless the profile is `OTHER` or
`SKIP_HARDWARE_CHECK=true`. It probes GPU 0 by default, or the selected GB300 device
(`:1134-1160`), and accepts a match on **any** GPU (`host_has_detected_hardware_profile`,
`:154-161`). **[V]**

**Placement and "budget" computation.** There is none in the arithmetic sense. The script
reads no memory figures. It derives:

- **Modes** (`:1277-1324`):
  - `LLM_MODE` = `remote` when `--use-remote-llm` is passed and the URL is set. Otherwise
    `local_shared` when the LLM device is in `RESERVED_DEVICE_IDS` or `FIXED_SHARED_DEVICE_IDS`,
    or equals the local VLM device. Otherwise `local`.
  - `VLM_MODE` is derived symmetrically.
  - GB300 forces both local models to `local_shared`.
- **RT-VLM fraction** from a static case table, `get_rtvi_vllm_gpu_memory_utilization`
  (`:591-633`):
  - alerts: GB300 0.2, DGX-SPARK 0.35.
  - local_shared: GB300 0.2, DGX-SPARK 0.35, H100/RTXPRO6000BW 0.4, L40S/RTXPRO4500BW 0.8,
    **anything else 0.7**.
  - Otherwise: L40S/4500 0.8, else 0.7.
  - Thor is set separately (`:2031-2037`).
- **Max model length:** `get_rtvi_vlm_max_model_len`, RTXPRO4500BW=18000 (`:635-641`).
- **Device IDs:** edge collapses everything to device 0 (`:1859-1873`). GB300 writes a
  full single-GPU closure: `SHARED_LLM_VLM_DEVICE_ID`, `FIXED_SHARED_DEVICE_IDS`,
  `RT_CV_DEVICE_ID`, `RT_EMBED_DEVICE_ID` and `RT_VLM_DEVICE_ID` (`:1882-1888,2027-2029`),
  plus `RTVI_VLLM_ATTENTION_BACKEND=TRITON_ATTN` (`:2003-2005`).
- **LLM sizing** is delegated entirely to `hw-<HW>[-shared].env` by filename
  (`:1471-1477,1846-1858`).

**What it writes and launches** (`state_up`, `:1676-2241`):

1. Copies `overrides.env` to `generated.env`.
2. Appends `services/vios/compose-defaults.env` keys that are not already set.
3. Runs `set_env_var` for roughly 40 keys: paths, host IP, `HARDWARE_PROFILE`, `MODE`,
   `LLM_*`, `VLM_*`, `RTVI_*`, device IDs, SBSA tags, and the alerts UI and Kafka toggles.
4. Creates the data dirs with `chmod 777`.
5. **Writes `/etc/sysctl.d/99-vss.conf` via sudo, disabling IPv6 host-wide** (`:644-660,2157-2161`).
6. Runs `docker compose config --images`, then `docker login nvcr.io`, then
   `docker compose up --detach --pull always --force-recreate --build` (`:2196-2238`).

It is Docker-CLI specific (`docker login`, `docker compose`). **[V]**

**Every error site** (83 `[ERROR]` lines; grouped). All are `[V]`:

| Lines                    | Condition                                                                                                 |
| ------------------------ | --------------------------------------------------------------------------------------------------------- |
| 795, 811, 816            | bad getopt / missing or invalid desired-state                                                             |
| 961-962                  | any option other than `-d` with `down`                                                                    |
| 970, 974, 982, 991, 1004 | missing `-p`; missing `NGC_CLI_API_KEY`; invalid profile; profile `.env` or `overrides.env` missing       |
| 1033                     | `HARDWARE_PROFILE` not in the hard-coded list `:1031`                                                     |
| 1043, 1047               | RTXPRO4500BW used with a profile other than alerts, or without `--use-remote-llm`                         |
| 1097, 1113, 1116, 1129   | GB300: conflicting device IDs; no GB300; >1 GB300 with no selector; search with a non-Lightning local LLM |
| 1151, 1154, 1157         | no GPU; selected device not GB300; requested profile matches no installed GPU                             |
| 1166, 1175               | RTXPRO4500BW: <2 GPUs; driver < 595.58.03 (`version_is_at_least` `:105-112`)                              |
| 1187-1199                | edge boards: wrong profile, search on IGX-THOR, device-ID flags                                           |
| 1223-1241                | edge search: local LLM/VLM requested; endpoint URLs missing                                               |
| 1250-1262                | Thor base/alerts: VLM flags not accepted                                                                  |
| 1328, 1332               | `--use-remote-*` without a URL                                                                            |
| 1346-1360                | alerts `--mode` missing or invalid; `--mode` on other profiles                                            |
| 1368, 1372               | invalid derived modes                                                                                     |
| **1380, 1384**           | **L40S: LLM cannot be `local_shared`; LLM and VLM cannot share a GPU**                                    |
| **1402, 1408**           | **device ID is in `RESERVED_DEVICE_IDS`** (skipped for GB300 and edge, `:1392`)                           |
| 1419, 1426               | env files missing                                                                                         |
| 1436-1451                | remote-LLM flag conflicts; bad `--llm-model-type`                                                         |
| 1461-1475                | unknown or removed `--llm`; **no `hw-<HW>[-shared].env` for the chosen LLM**                              |
| 1481, 1491-1517          | VLM flag conflicts; bad `--vlm`                                                                           |
| 1531                     | search on single-GPU Brev without a remote VLM                                                            |
| 1540, 1543               | custom weights path not absolute, or missing                                                              |
| 1687, 1693               | `.env`/`overrides.env` missing (state_up)                                                                 |
| 1783-1790                | Brev secure-link resolution                                                                               |
| 1833, 1915               | remote `/v1/models` unusable. Auto-select requires **exactly one** model (`:349-388`)                     |
| 1853-1855                | LLM tuning file missing (second check)                                                                    |
| 2048                     | `--vlm` not mappable to an integrated RT-VLM checkpoint                                                   |
| 2235                     | `docker compose up` failed                                                                                |

`run_required_step` (`:662-673`) and `require_downloaded_model_file` (`:675-683`) are defined
but never called. **[V]** (grep shows only the definitions)

### 1.6 Registry of everywhere a hardware tier must be registered

A grep for `RTXPRO4500BW|RTX PRO 4500` hits **39 files**. That enumerates the surface a new
tier inherits. **[V]** (`git grep -c` at HEAD). The GB300 introduction (`dcc709dcc`, #1762,
38 files) and the RTXPRO4500BW restriction (`979ab595a`, 13 files; `8e1c8ccdc`) are the best
worked examples. **[V]**

### 1.7 CHECKLIST: add a consumer hardware tier

"MUST" = the tier fails or is rejected without it. "SHOULD" = a CI or reviewer expectation.
"IF" = only when that capability is claimed.

**A. `deploy/docker/scripts/dev-profile.sh`** **[V]** for all line refs

| #   | Touch point                                                                                                                                                                                                            | Line                                       | Needed                                                                              |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------- |
| A1  | Add the token to `_valid_hardware_profiles` and the error text                                                                                                                                                         | 1031, 1033                                 | MUST                                                                                |
| A2  | Add a detection glob in `get_detected_hardware_profile`, e.g. `*geforce*rtx*5090*) echo "RTX5090"`. For a VRAM class, alias it in `get_canonical_hardware_profile` like THOR                                           | 136-149, 165-171, 173-180                  | MUST (otherwise `-H <tier>` fails `:1156-1158` on real hardware)                    |
| A3  | Update the usage text                                                                                                                                                                                                  | 708-725                                    | SHOULD                                                                              |
| A4  | Add a policy block (allowed profiles, required `--use-remote-llm`) by copying the RTXPRO4500BW case                                                                                                                    | 1037-1051                                  | MUST if restricted                                                                  |
| A5  | Add hardware prerequisites: GPU count, driver floor, and **VRAM floor** (new; no VRAM check exists anywhere today)                                                                                                     | 1161-1179                                  | SHOULD                                                                              |
| A6  | Add the tier to the `RESERVED_DEVICE_IDS` exemption (today only GB300 and edge)                                                                                                                                        | 1392                                       | **MUST for single-GPU alerts**                                                      |
| A7  | Add a single-GPU placement closure (copy the GB300 branches). Covers `LLM_MODE`/`VLM_MODE` forcing, `SHARED_LLM_VLM_DEVICE_ID`, `FIXED_SHARED_DEVICE_IDS`, `RT_CV_DEVICE_ID`, `RT_EMBED_DEVICE_ID`, `RT_VLM_DEVICE_ID` | 1068-1132, 1319-1324, 1882-1888, 2025-2029 | MUST for single-GPU alerts/search                                                   |
| A8  | Add RT-VLM fraction entries, dedicated and shared                                                                                                                                                                      | 591-633                                    | MUST (OTHER falls to 0.7 even when shared, `:624`, which overcommits beside an LLM) |
| A9  | Add an RT-VLM max model length                                                                                                                                                                                         | 635-641                                    | SHOULD                                                                              |
| A10 | Pin the RT-VLM checkpoint, e.g. Cosmos3 FP8 on sm_89/120, like the RTXPRO4500BW pin                                                                                                                                    | 2038-2041                                  | IF the default BF16 does not fit                                                    |
| A11 | Add an attention backend override, like GB300's `TRITON_ATTN`                                                                                                                                                          | 2003-2005                                  | IF sm_120 kernels are missing **[?]**                                               |
| A12 | Exclude from SBSA suffix logic (amd64 GeForce), or include for arm64                                                                                                                                                   | 2163-2182                                  | check                                                                               |

**B. Model sizing files** `deploy/docker/services/nim/<slug>/` **[V]**

| #   | File                                                                      | Needed                                                                                                                            |
| --- | ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| B1  | `nvidia-nemotron-nano-9b-v2-fp8/hw-<TIER>.env` and `hw-<TIER>-shared.env` | IF a local VSS-managed LLM is offered. With a remote llama.cpp LLM, **not needed** (`LLM_NAME_SLUG=none`, `:1838`)                |
| B2  | `nemotron-3.5-lightning-30b-a3b/hw-<TIER>*.env`                           | **Do not add.** The INT4 profile needs ≥ 32 GB/device (`hw-AGX-THOR.env:21-25`) and uses 46,150 MiB on L40S (`hw-L40S.env:10-14`) |
| B3  | `cosmos3-reasoner/hw-<TIER>*.env`                                         | IF search, which uses the standalone NIM slug (`dev-profile.sh:215`)                                                              |

**C. Profile env files** **[V]**

| #   | File:line                                                                                                                                                                                        | Needed                 |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------- |
| C1  | The "Valid:" `HARDWARE_PROFILE` comment in each `overrides.env` (`dev-profile-alerts/overrides.env:25`; `warehouse-operations/overrides.env:58`)                                                 | SHOULD (docs)          |
| C2  | `RESERVED_DEVICE_IDS` / `FIXED_SHARED_DEVICE_IDS` / `RT_*_DEVICE_ID` in `dev-profile-alerts/.env:39-42` and `dev-profile-search/.env:48-50`. Leave them alone and override in the script (A6/A7) | Do not edit; use A6/A7 |

**D. Other deploy front-ends** **[V]**

| #   | File:line                                                                                                                                                                                               | Needed                                                                          |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| D1  | `deploy/docker/scripts/vss_orchestrator_mcp_config.yml:88-~140` `hardware_profiles.<TIER>` (the keys **are** the allow-list, `docker_compose_util.py:739-740`)                                          | MUST for the NemoClaw/orchestrator path                                         |
| D2  | `deploy/docker/scripts/blueprint-deploy.sh:317-335` sizing cases                                                                                                                                        | IF industry profiles                                                            |
| D3  | `industry-profiles/warehouse-operations/blueprint-configurator/blueprint_config.yml:735-858` section; `deploy/helm/industry-profiles/warehouse-operations/scripts/compute_stream_cap.py:38-63` name map | IF warehouse. An unknown name silently gets no stream cap (`sizing.md:258-271`) |
| D4  | `deploy/docker/scripts/*.ipynb` hardware pickers (`deploy_vss_launchable.ipynb` has 9 hits)                                                                                                             | SHOULD                                                                          |

**E. Helm parity** (the helm-sync gate is blocking, §5) **[V]**

| #   | File:line                                                                                               | Needed                                                |
| --- | ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| E1  | `deploy/helm/services/nims/values.yaml:41` comment and a `gpuProfiles.<TIER>` block at `:50-134`        | MUST to pass helm-sync if docker NIM env files change |
| E2  | Optional `deploy/helm/services/nims/override-values-<TIER>.yaml`, following `override-values-L40S.yaml` | SHOULD                                                |
| E3  | `deploy/helm/developer-profiles/dev-profile-lvs/README.md:97,324` supported-values tables               | SHOULD                                                |
| E4  | `deploy/helm/services/rtvi/charts/rtvi-vlm/values.yaml:217` (`VLLM_GPU_MEMORY_UTILIZATION`)             | IF helm-deployable                                    |

**F. Tests** **[V]**

| #   | File                                                                                                                                                                                             | Needed                                                          |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| F1  | `deploy/docker/test-scripts/test-dev-profile.sh`: mock `nvidia-smi` directories and `EXPECTED_ERROR` assertions. Pattern at `:461-532`; helper at `:195-202`; generated.env checks at `:809-822` | MUST (reviewer expectation; the RTXPRO4500 PRs all added tests) |
| F2  | `services/agent/packages/vss_agents/tests/unit_test/orchestrator/test_docker_compose_util.py:1964-1968`, which **regex-parses dev-profile.sh literals**                                          | MUST if A10 changes. Runs in the CI `test` job                  |
| F3  | `deploy/docker/test-scripts/compose-images.golden`, regenerated with `python3 .github/scripts/compose_image_golden.py --update`                                                                  | MUST if any compose `image:` is added                           |

**G. Docs** **[V]**

| #   | File:line                                                                                           | Needed                                          |
| --- | --------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| G1  | `docs/prerequisites.mdx:10-19` validated list; `:36-41` driver list; a new `<Tab>` in `:328-434`    | MUST                                            |
| G2  | `docs/real-time-vlm.mdx:1511-1531` RT-VLM utilization table (new since `cdad5cc0e`); `:88-95` notes | MUST                                            |
| G3  | `docs/faq.mdx:266-280`-style per-GPU FAQ                                                            | SHOULD                                          |
| G4  | `docs/vss-configurator.mdx:38,114,167,289,1139`                                                     | IF warehouse                                    |
| G5  | `docs/performance*.mdx`                                                                             | IF benchmarked (see the SLA note in prior docs) |

**H. Skills** (CODEOWNERS: `@NVIDIA-AI-Blueprints/VSS-Skill-Developers`) **[V]**

| #   | File:line                                                                                                                                                   | Needed             |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| H1  | `skills/vss-build-vision-ai/references/sizing.md:60-69` **GPU table**, `:163-171` RT-VLM placement table, `:186-194` constraint prose; `:297-303` if search | MUST               |
| H2  | `skills/vss-build-vision-ai/SKILL.md:82` routing row, like RTXPRO4500BW                                                                                     | MUST if restricted |
| H3  | `references/profiles/{alerts,base,lvs,search}.md:9-10` hardware bullets                                                                                     | SHOULD             |
| H4  | `references/prerequisites.md:365-375` driver table                                                                                                          | MUST               |
| H5  | `references/services/llm-nim.md:16-17,37`                                                                                                                   | IF B1              |
| H6  | `skills/vss-build-vision-ai/evals/evals.json` (GB300 added entries at `:73,85,95`)                                                                          | SHOULD             |

**I. Skill-eval** (CI hardware) **[V]**

| #   | File:line                                                                                                                     | Needed                   |
| --- | ----------------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| I1  | `.github/skill-eval/adapters/vss-build-vision-ai/generate.py:65-94` `PLATFORMS` dict, plus the same dict in other adapters    | IF evals run on the tier |
| I2  | Spec `platforms` in `skills/*/eval/*.json` (e.g. `vdr_1_quickstart_vision_agent.json` → `{"RTXPRO6000BW": {"gpu_count": 1}}`) | IF evals                 |
| I3  | `.github/skill-eval/run_leg.py:551-570` `_registered_gpu_hint`; `:58-63` RTX4090 tables / `BREV_RTX4090_POOL`                 | IF using the 4090 pool   |

**Not required:** `check_folder_structure.py` constrains only the top level of
`developer-profiles/` (`:33-42`), so a hardware tier adds no directory there. A new
**developer profile** (`dev-profile-<name>/`) is a much larger surface:

- `check_folder_structure.py:37-41`
- `dev-profile.sh:979,982,2247`
- `developer-profiles/compose.yml:16-33`
- `composition.md:20-24`
- a helm chart under `deploy/helm/developer-profiles/`
- `.github/helm-sync/AGENTS.md` layout **[V]**

### 1.8 Naming the conventions would force

- Tokens are **uppercase SKU strings derived from the nvidia-smi product name**, not tiers:
  `H100`, `L40S`, `GB300`, `RTXPRO4500BW`, `RTXPRO6000BW`, `RTXPRO6000BW-SE`, plus the
  platform names `DGX-SPARK`, `IGX-THOR`, `AGX-THOR` and the catch-all `OTHER`
  (`dev-profile.sh:1031`; `blueprint_config.yml:735-858`). "BW" disambiguates Blackwell from
  RTX 6000 Ada. **[V]**
- By that convention a GeForce tier would be **`RTX5090`, `RTX4090`, `RTX3090`** →
  `hw-RTX5090.env`. VSS's own configurator test already uses `HARDWARE_PROFILE=RTX5090` as
  its example of an unrecognized profile (`services/configurators/vss-configurator/tests/test_profile_config_manager.py:386-391`).
  Skill-eval spells the GPU `"GEFORCE RTX 4090"` (`run_leg.py:561`). **[V]**
- `hw-GEFORCE-*` is **not** what the conventions suggest, and **no code enforces any naming
  pattern**. Membership in `_valid_hardware_profiles` and orchestrator keys is the only gate.
  A VRAM-class token (e.g. `GEFORCE-24GB`) is mechanically possible via the THOR-style
  canonical alias (`:165-171`) and would avoid a file explosion across SKUs. It would break
  the SKU-per-token convention and needs maintainer buy-in. **[A]**

---

## 2. Single-GPU placement

### 2.1 Mechanisms today **[V]**

- **Mode derivation:** see §1.5 (`dev-profile.sh:1277-1324`).
- **`-shared` selection:** Compose service per mode (§1.2).
- **Start ordering:** the shared LLM waits for `rtvi-vlm` / `cosmos3-reasoner-shared-gpu` /
  `rtvi-embed` to be healthy (`nemotron-3.5-lightning-30b-a3b/compose.yml:92-104`;
  `nvidia-nemotron-nano-9b-v2-fp8/compose.yml:163-175`).
- **Knobs by serving path** (`sizing.md:86-100`):

| Path             | Knob                                                                                                            | Where read                                                 |
| ---------------- | --------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| LLM NIM          | `NIM_GPU_MEM_FRACTION` + `NIM_KVCACHE_PERCENT`, `NIM_MAX_MODEL_LEN`, `--max-num-seqs` in `NIM_PASSTHROUGH_ARGS` | hw env → NIM container                                     |
| Raw-vLLM Nano 9B | `NIM_GPU_MEM_FRACTION`, `NIM_MAX_MODEL_LEN`, `NIM_MAX_NUM_SEQS`                                                 | `nvidia-nemotron-nano-9b-v2-fp8/compose.yml:51-55,119-123` |
| Cosmos3 NIM      | `NIM_GPU_MEMORY_UTILIZATION` (`VLM_NIM_KVCACHE_PERCENT` maps to it)                                             | `cosmos3-reasoner/hw-*.env`                                |
| RT-VLM           | `RTVI_VLLM_GPU_MEMORY_UTILIZATION`                                                                              | §2.6                                                       |

- **Budget rule:** shared fractions must fit the budget, and discrete cards stay ≤ 0.85
  (`sizing.md:51-58,98-100`). The GB300 note: "vLLM reserves `fraction × total` without
  subtracting co-residents" (`sizing.md:141-142`).

### 2.2 The "two vLLM engines" claim, re-verified

- **Location moved:** `dev-profile.sh:1161-1165` at `cdad5cc0e` is now **`:1211-1216`**. It is
  a comment inside the _edge search_ block (`:1206-1244`), measured on AGX Thor with 122.82 GiB
  unified memory. **[V]**
- **Enforced logic for that block:** on DGX-SPARK/AGX-THOR with `-p search`, a local `--llm`
  or `--vlm` is an error (`:1222-1229`), and both models are forced remote (`:1232-1243`).
  **[V]**
- **The 48 GB hard error is a different rule:** L40S only (`:1376-1387`). The reason given is
  capacity (INT4 Lightning at 46,150 MiB of 49,140, `hw-L40S.env:10-14`), not engine count.
  **[V]**
- **Counter-evidence (contradicts `04`/`05`):**
  - Stock base/LVS put LLM and RT-VLM on GPU 0 in `local_shared`
    (`dev-profile-base/overrides.env:30-40`).
  - `hw-OTHER-shared.env:4-6` records a measured co-residence: "RTX PRO 6000 co-resident with
    a live CR3 nano: 0.3 → 29970 MiB for the LLM and 21.9 GB still free".
  - GB300 runs LLM 0.3 + RT-VLM 0.2 on one GPU (`sizing.md:119-142`).
  - The engines do share a GPU. The binding constraint is Σ fractions × total ≤ free at each
    engine's start. **[V]**
- **Internal inconsistency:** `:611-613` says vLLM "claims gpu_memory_utilization × total
  … refuses to start unless free ≥ that reservation (it does not subtract co-resident
  processes)". `:1212-1214` says each engine "sizes itself as (fraction × total) − (memory
  held by every other process)". Both describe the same engine and are mutually exclusive.
  The shared layouts only work under the first reading. **[V]/[A]**

### 2.3 Can the LLM slot be an external OpenAI-compatible endpoint? **Yes.** **[V]**

- **Flags:** `--use-remote-llm` with `LLM_ENDPOINT_URL` (`:696,746,887-891`). Optionally
  `--llm <model-id>`, or the endpoint's `/v1/models` must list **exactly one** model
  (`:349-388,1826-1836`). Use `--llm-model-type openai` (`:1448-1453,1892-1897`).
- **What gets written:** `LLM_MODE=remote`, `LLM_NAME_SLUG=none`, and `LLM_BASE_URL`
  (`:1825,1838,1889-1891`). The compose key becomes `llm_remote_none`, which matches no service
  (`dev-profile-base/overrides.env:199`).
- **Agent side:** `openai_llm: {_type: openai, base_url: ${LLM_BASE_URL}/v1}`
  (`dev-profile-alerts/vss-agent/configs/config.yml:211-214`).
- **Skill path:** the skill's edge guide explicitly allows "your own OpenAI-compatible server",
  with no trailing `/v1` in the base URL (`skills/vss-build-vision-ai/references/edge.md:38-40`).
- **Caveats:**
  - **Reachability:** `vss-agent` has no `extra_hosts` mapping (`deploy/docker/services/agent/compose.yml`,
    grep). Only `rtvi-vlm` maps `host.docker.internal` (`rtvi-vlm-docker-compose.yml:197-198`).
    A llama.cpp bound to `127.0.0.1` (our loopback rule, `ours:AGENTS.md` "Network Ports") is
    **not reachable** from the agent container. It must bind a host IP that containers can
    reach. **[A]**
  - Tool calling, reasoning parsing and `max_tokens` semantics are Auditor B's territory.

### 2.4 Would a llama.cpp server on the same GPU pass dev-profile.sh? **Yes, the script cannot see it.** **[V]**

- No memory or process accounting exists (only name, index and driver queries:
  `:86,88,97,131,159,1172`).
- `OTHER` bypasses the name check (`:1135-1138`).
- The RTXPRO4500BW path would still reject a single card (count ≥ 2, `:1163-1168`).
- **Profile blockers that do bind on one discrete GPU:**
  - **alerts:** `RESERVED_DEVICE_IDS='0'` (`dev-profile-alerts/.env:39`). A local VLM on
    device 0 errors (`:1400-1411`), unless the hardware is GB300 or edge (`:1392`).
  - **search:** `FIXED_SHARED_DEVICE_IDS='0,1'` and `RT_EMBED_DEVICE_ID='1'`
    (`dev-profile-search/.env:48-50`). Device 1 does not exist, so it fails at Compose start.
  - **base:** passes (`RESERVED_DEVICE_IDS=''`, `dev-profile-base/.env:44`).
  - **lvs:** passes, but requires ES + Kafka + Logstash.
- **Runtime accounting does see llama.cpp:**
  - vLLM's startup reservation check (per `:611-613`) **[A on exact vLLM 0.17 semantics]**.
  - RT-VLM's live-stream admission guard uses device-wide `cudaMemGetInfo` with a
    1,024 MiB headroom (`rtvi_stream_handler.py:64,742-747,1556-1582`; compose
    `rtvi-vlm-docker-compose.yml:116-118`).
  - The RT-VLM start script reads `memory.free` to pick decoder reuse and `memory.total` to
    pick defaults (`services/rtvi/rt-vlm/start_rtvi_vlm.sh:90-138`).

### 2.5 Could RT-VLM (vLLM) plus an external llama.cpp LLM co-reside on one 24 GB card?

**Per the profile logic: base profile yes, alerts and search no** (without code changes; see
§2.4). What dev-profile.sh would set for `-p base -H OTHER --use-remote-llm` **[V]**:

- `VLM_MODE=local` (the LLM is remote, so it is not shared) (`:1303-1317`).
- `RTVI_VLLM_GPU_MEMORY_UTILIZATION=0.7` (`:631`).
- `RTVI_VLM_MODEL_PATH=…cosmos3-nano-reasoner:bf16-final` (`dev-profile-base/overrides.env:191`).
- `VLM_MAX_MODEL_LEN` defaults to 32768 (`rtvi-vlm-docker-compose.yml:57`).
- `VLM_BATCH_SIZE` auto-selects 3 when total memory ≤ 46,000 MiB (`start_rtvi_vlm.sh:127-138, :328`),
  which becomes vLLM `max_num_seqs` (`vllm_compatible_model.py:1505`).

Arithmetic for a 24 GB card (nvidia-smi reports ≈ 24,564 MiB on the 4090 and A5500 **[A]**):

- **[C]** RT-VLM reservation at 0.7 = 0.7 × 24,564 ≈ **17,195 MiB (16.8 GiB)**. vLLM starts
  only if free ≥ 17,195 MiB, so llama.cpp + CUDA contexts + display must stay under
  ≈ 7.2 GiB.
- **[C]** The 32 GB RTX PRO 4500 runs this same default BF16 checkpoint at
  0.8 × 32 GB = **25.6 GB** with `max_model_len=18000` (`dev-profile.sh:630,638`). That is
  above any 24 GB card's total, so the **BF16 default is not a 24 GB option beside anything
  else**. **[A]** (the reservation is not the weights footprint; the Cosmos3 Nano parameter
  count is not in-repo and its HF repo returns 401 **[E]**, see §4)
- **[E]** Our current LLM file,
  `Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf`, is **24,574,373,664 bytes**
  (`curl https://huggingface.co/api/models/unsloth/Nemotron-3-Nano-30B-A3B-GGUF/tree/main`).
  It is larger than a 24 GB card by itself. `ours:docker-compose.prod.yml:158,161,165,167`
  use `GPU_LAYERS=auto`, `CTX_SIZE=262144` and `PARALLEL=8`, which implies partial CPU
  offload or MoE offload (`:177`). **Co-residence on 24 GB needs a smaller LLM or offload.**
  **[C]/[A]**
- **Precision caveat:** "`Cosmos3 Nano Reasoner (modelopt-fp8)` is not supported on NVIDIA A100
  GPUs" (`docs/real-time-vlm.mdx:92`). A100 is sm_80 with no FP8 tensor cores, so treat FP8 as
  **unsupported on sm_86** (A5500, 3090) **[A]** and hardware-supported on sm_89/sm_120.
  "hallucinations may occur with modelopt-fp8 and modelopt-nvfp4" (`:91`). **[V]**
- **Verdict:** a 4090-class card can plausibly host RT-VLM (FP8, util ≈ 0.45–0.55,
  `max_model_len` ≤ 18k) plus a small llama.cpp LLM (≈ 9B at Q4, fixed context) **[A]**.
  The A5500 (sm_86) is limited to BF16 or emulated paths, which leaves too little room. **[?]**
  until measured.

### 2.6 Knobs that shrink RT-VLM's footprint

| Profile env (compose)                                                                                                | Container env                                                    | Read at                                                                                                   | Default            | Effect / status                                                                                                                                                                |
| -------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `RTVI_VLLM_GPU_MEMORY_UTILIZATION`                                                                                   | `VLLM_GPU_MEMORY_UTILIZATION` (`rtvi-vlm-docker-compose.yml:51`) | `vllm_compatible_model.py:1460-1473`; `start_rtvi_vlm.sh:119-124` sets 0.7 when unset and ≤ 50 GB         | 0.7                | Total reservation. dev-profile.sh overwrites it from its table (`:2002`); override by exporting it in the shell (`:1655-1658`) **[V]**                                         |
| `RTVI_VLM_MAX_MODEL_LEN`                                                                                             | `VLM_MAX_MODEL_LEN` (`:57`)                                      | `vllm_compatible_model.py:1502`; `rtvi_vlm_server.py:660`                                                 | 32768              | Caps KV per sequence **[V]**                                                                                                                                                   |
| `RTVI_VLM_BATCH_SIZE`                                                                                                | `VLM_BATCH_SIZE` (`:47`)                                         | `start_rtvi_vlm.sh:127-138, :328` → `--vlm-batch-size` → `max_num_seqs` (`vllm_compatible_model.py:1505`) | auto: 3 / 16 / 128 | The real `max_num_seqs` knob **[V]**                                                                                                                                           |
| `RTVI_VLLM_MAX_NUM_SEQS`                                                                                             | `VLLM_MAX_NUM_SEQS` (`:55`, default 256)                         | **only** an alias entry (`vllm_compatible_model.py:79`); never passed to engine args                      | 256                | **Dead knob** **[V]**                                                                                                                                                          |
| `RTVI_VLLM_MAX_NUM_BATCHED_TOKENS`                                                                                   | (`:56`)                                                          | `vllm_compatible_model.py:1475-1485`                                                                      | 5120               | Activation peak **[V]**                                                                                                                                                        |
| `RTVI_VLLM_MM_PROCESSOR_CACHE_GB` / `RTVI_VLLM_DISABLE_MM_PREPROCESSOR_CACHE`                                        | (`:60,71`)                                                       | `_apply_mm_processor_cache_engine_args`                                                                   | 0 / true           | Keep at 0 **[V]**                                                                                                                                                              |
| `RTVI_VLM_MODEL_PATH` (+ `RTVI_VLM_MODEL_TO_USE`)                                                                    | `MODEL_PATH` (`:74-75`)                                          | pipeline                                                                                                  | CR3 Nano BF16      | FP8/NVFP4 variants (`skills/.../services/rt-vlm.md:39-41`) **[V]**                                                                                                             |
| `VLM_VIDEO_PRUNING_RATE` (EVS)                                                                                       | (`:123`)                                                         | Nemotron VL/Omni only (`vllm_compatible_model.py:1692`)                                                   | unset              | Fewer tokens (`services/rtvi/rt-vlm/README.md:779-800`) **[V]**                                                                                                                |
| `RTVI_VLM_INPUT_WIDTH/HEIGHT`, `RTVI_VLM_DEFAULT_NUM_FRAMES_…`                                                       | (`:48-49,82`)                                                    | pipeline                                                                                                  | —                  | Fewer visual tokens **[V]**                                                                                                                                                    |
| `RTVI_VLLM_KV_CACHE_MEMORY_BYTES`, `RTVI_VLLM_KV_CACHE_DTYPE`, `RTVI_VLLM_ENFORCE_EAGER`, `RTVI_VLLM_CUDAGRAPH_MODE` | **not in the compose `environment:`** (grep counts 0)            | `vllm_compatible_model.py:1509-1521` (kv bytes), `:374-389` (kv dtype), `:1605-1610` (eager)              | unset              | **Most useful for co-residence: a fixed KV size independent of utilization.** Needs a compose patch to expose **[V]**. vLLM 0.17 support is gated by a signature check **[A]** |
| `RTVI_LIVE_STREAM_GPU_MEMORY_HEADROOM_MB`                                                                            | (`:118`)                                                         | `rtvi_stream_handler.py:742-747`                                                                          | 1024               | Admission watermark **[V]**                                                                                                                                                    |

---

## 3. GPU architecture support

### 3.1 Per image

Image-config values come from registry config blobs, fetched anonymously **[E]**. No layers
were pulled. Reproduce with:

```bash
TOK=$(curl -s "https://ghcr.io/token?scope=repository:$REPO:pull&service=ghcr.io" | jq -r .token)  # nvcr.io: https://nvcr.io/proxy_auth?scope=repository:$REPO:pull
ACC='Accept: application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'
DIG=$(curl -s -H "$ACC" -H "Authorization: Bearer $TOK" https://$REG/v2/$REPO/manifests/$TAG | jq -r '.manifests[]|select(.platform.architecture=="amd64")|.digest')
CFG=$(curl -s -H "$ACC" -H "Authorization: Bearer $TOK" https://$REG/v2/$REPO/manifests/$DIG | jq -r .config.digest)
curl -sL -H "Authorization: Bearer $TOK" https://$REG/v2/$REPO/blobs/$CFG | jq -r '.config.Env[]' | grep -E 'ARCH|CUDA_VERSION|TRT_VERSION|VLLM_VERSION'
```

The compressed sizes quoted are the sums of the per-arch manifest's `.layers[].size`.

| Image (as referenced)                                                                    | Base / pins                                                                                                                                                              | CUDA · TRT · framework (image config)                  | Arch list                                                                                                                                                                                                     | Engines                                                                                                                                                                    | sm_86                                                                                                                                                                   | sm_89                                                                        | sm_120                                                            |
| ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `ghcr.io/nvidia-ai-blueprints/vss/vss-rt-vlm:develop-latest` (amd64, 11.3 GB compressed) | `FROM nvcr.io/nvidia/vllm:26.03-py3` (`services/rtvi/rt-vlm/docker/Dockerfile:12,62`); vLLM **0.17.1+a03ca76a** asserted at `:381`; DeepStream 9.1 x86 tarball `:95-101` | CUDA 13.2.0.046 · TRT 10.16.0.72 · vLLM 0.17.1 **[E]** | Base `CUDA_ARCH_LIST=7.5 8.0 8.6 9.0 10.0 12.0` **[E]**. `TORCH_CUDA_ARCH_LIST` is overridden to `7.5 8.0 8.6 8.7 9.0 10.0 11.0 12.0+PTX` (`Dockerfile:73`) but governs only JIT/extensions; vLLM is prebuilt | vLLM kernels are prebuilt                                                                                                                                                  | native **[E]**                                                                                                                                                          | runs sm_86 SASS; **no 8.9-specific kernels** (e.g. CUTLASS FP8 sm89) **[A]** | native SASS; FP4 needs sm_120a kernels, whose presence is **[?]** |
| same, arm64 (Jetson/igpu default since `5e0949f1e`)                                      | `ARM_PLATFORM=igpu` (`Dockerfile:15,65`)                                                                                                                                 | CUDA 13.2 · TRT 10.16                                  | `8.0 8.6 9.0 10.0 11.0 12.0` **[E]**                                                                                                                                                                          | —                                                                                                                                                                          | —                                                                                                                                                                       | —                                                                            | —                                                                 |
| `…/vss-rt-vlm:develop-latest-sbsa` (arm64; GB300/Spark)                                  | SBSA DeepStream `Dockerfile:9,29-36`                                                                                                                                     | CUDA 13.2 · TRT 10.16                                  | as arm64 **[E]**                                                                                                                                                                                              | —                                                                                                                                                                          | GB300 = sm_103 runs sm_100 SASS. dev-profile forces `TRITON_ATTN` on GB300 (`dev-profile.sh:2003-2005`), a sign that arch-specific attention kernels are absent **[A]** |                                                                              |                                                                   |
| `…/vss-rt-cv:develop-latest` (17.8 GB)                                                   | `nvcr.io/nvidia/deepstream:rtvi_ds9.1.1-triton-dev135` (`services/rtvi/rt-cv/docker/Dockerfile:54`); `CUDA_VER=13.2` (`:110`)                                            | CUDA 13.2 · TRT 10.16 **[E]**                          | `7.5 8.0 8.6 9.0 10.0 12.0` **[E]**                                                                                                                                                                           | **Built at runtime** with `trtexec … --fp16` from ONNX on the target GPU and cached in `$VSS_APPS_DIR/engines` (`deploy/docker/services/rtvi/rtvi-cv/ds-start.sh:520-540`) | yes **[A]**                                                                                                                                                             | yes **[A]**                                                                  | yes, if TRT 10.16 supports it **[A]**                             |
| `…/vss-rt-embed:develop-latest` (12.2 GB)                                                | amd64 `nvcr.io/nvidia/tritonserver:26.03-py3` + `pytorch:26.03-py3` (`services/rtvi/rt-embed/docker/Dockerfile:19-26`)                                                   | CUDA 13.2 · TRT 10.16                                  | `TORCH_CUDA_ARCH_LIST=7.5 … 12.0+PTX` (`Dockerfile:185`)                                                                                                                                                      | TRT engines **built at runtime, named by GPU name** (`src/models/custom/samples/cosmos-embed1/create_triton_model_repo.py:232-261`)                                        | yes **[A]**                                                                                                                                                             | yes **[A]**                                                                  | yes **[A]**                                                       |
| RT-CV-3D                                                                                 | Uses the `vss-rt-cv` image (`rtvi-cv-mv3dt/compose.yaml:54`); BEV-fusion and config-init are CPU-only Python/distroless (`measurement-fusion.Dockerfile:26,73`)          | —                                                      | —                                                                                                                                                                                                             | Capability-based NVENC probe, not a name list (`stage-configs.sh:137-160`)                                                                                                 |                                                                                                                                                                         |                                                                              |                                                                   |
| `nvcr.io/nim/nvidia/nemotron-3.5-lightning-30b-a3b:2.0.9-variant` (10.0 GB)              | NIM                                                                                                                                                                      | CUDA 13.0.2 **[E]**                                    | `7.5 8.0 8.6 8.9 9.0 10.0 12.0` **[E]**                                                                                                                                                                       | INT4 profile, **≥ 32 GB/device** (`hw-AGX-THOR.env:21-25`)                                                                                                                 | VRAM-excluded below 32 GB                                                                                                                                               | same                                                                         | 32 GB 5090 is borderline: GB vs GiB interpretation is **[?]**     |
| `nvcr.io/nim/nvidia/cosmos3-reasoner:1.7`                                                | NIM                                                                                                                                                                      | **401 anonymous** **[E]**; not inspectable             |                                                                                                                                                                                                               |                                                                                                                                                                            | **[?]**                                                                                                                                                                 | **[?]**                                                                      | **[?]**                                                           |
| `nvcr.io/nvidia/vllm:26.07-py3` (Nano 9B FP8 service, 10.2 GB)                           | raw vLLM (`nvidia-nemotron-nano-9b-v2-fp8/compose.yml:34,102`)                                                                                                           | CUDA 13.3.1 · TRT 11.1 · **vLLM 0.24.0** **[E]**       | `7.5 8.0 8.6 9.0 10.0 12.0` **[E]**                                                                                                                                                                           | —                                                                                                                                                                          | FP8 via weight-only fallback **[A]**                                                                                                                                    | native FP8 via cuBLASLt **[A]**                                              | native **[A]**                                                    |

- **Driver:** VSS requires **595.58.03** on x86 (`docs/prerequisites.mdx:37`), and
  dev-profile.sh enforces it only for RTXPRO4500BW (`:1170-1177`). CUDA 13.x needs an
  R580+ driver **[E, general]**. Whether a 595-branch **GeForce** Linux driver exists is
  **[?]**. The Lightning NIM's `NVIDIA_REQUIRE_CUDA=cuda>=13.0 brand=…` brand clauses are
  forward-compat alternatives, not a GeForce block **[E]/[A]**.
- **Ampere floor stated by NVIDIA support:** issue #1556 (closed) says "VSS deployment
  requires the Ampère architecture or newer … deploy the Qwen3 LLM/VLM using vLLM and then
  deploy VSS via the remote API" **[E: `gh issue view 1556 --repo NVIDIA-AI-Blueprints/video-search-and-summarization`]**.
  #1563 documents LVS running on a 48 GB RTX 8000 via `-H OTHER` and a remote Qwen3 vLLM
  **[E]**.

### 3.2 Allow-lists, deny-lists and detection (grep `4090|5090|GeForce|RTX|compute_cap|nvidia-smi --query`)

- **No GeForce deny-list anywhere.** Outside `.github/`, "GeForce" appears only in comments
  and examples (`services/*/request_profiler.py:56`, `cuviddec.h:1037`,
  `skills/deployment/vss-deploy-detection-tracking-2d/scripts/check_container_gpu.sh:61` shows
  an "RTX 3050" example). **[V]**
- Name-based gates:
  - `dev-profile.sh:136-161,1134-1180`: unknown names become OTHER, which bypasses the check.
  - `blueprint-deploy.sh:669-680`: GB300 only.
  - `compute_stream_cap.py:38-63`: warehouse caps.
  - Orchestrator key allow-list (`docker_compose_util.py:739-740`).
  - Skill-eval `_registered_gpu_hint` fails closed for unknown prefixes (`run_leg.py:551-570`).
  - **[V]**
- **No compute-capability checks** anywhere in `services/`, `deploy/` or the skill scripts
  (grep `compute_cap|get_device_capability` → none). **[V]**

### 3.3 RTX4090 skill-eval pools at HEAD

- The tables are still empty: `RTX4090_ALL_TESTS: frozenset[str] = frozenset()` and
  `RTX4090_TESTS … = {}` (`.github/skill-eval/run_leg.py:62-63`, prefix `:58`). The comment
  says routing is "opt-in at the spec level via gpu_type" (`:59-61`). **[V]**
- **No spec declares a GeForce `gpu_type`** (grep of `skills/` and `adapters/` → none).
  Registered 4090 nodes are "never discovered" (`tests/test_run_leg.py:1932-1965`). Only a
  _managed_ 4090 instance could be selected, and only by a spec that asks for it
  (`:1969-2002`). **[V]**
- **History (not "declared intent"):**
  - #1339 (merged 2026-07-20) populated both tables with base/LVS/alerts_vlm/alerts_cv
    `vss-deploy-profile` tests, ask-video, summarize, query-analytics, 2D detection,
    embedding, VIOS, calibration and dense-captioning.
  - #1406 (merged 2026-07-24) cleared them because routing "silently overrode the
    spec-declared platform".
  - `git show 2eb3c95ca -- .github/skill-eval/run_leg.py`. **[V]/[E]**
- **Stale docs:** `.github/skill-eval/AGENTS.md:510-516` and `README.md:79` still describe a
  populated "resource-proven matrix". **[V]**
- **Fleet:** open PR #1466 lists "3 runners: 1x NVIDIA GeForce RTX 4090; canonical aliases
  `vss-eval`, `gpu-rtx4090`, `gpus-1` … all seven are online and idle"
  **[E: `gh pr view 1466 --repo …`]**. PR #1818 reports "three pre-existing RTX 4090
  capability-table failures" on develop in August **[E]**.

---

## 4. Image availability and CPU architecture

Command, per image **[E]**: take the same anonymous token as §3.1, then
`curl -s -o /dev/null -w '%{http_code}' -H "$ACC" -H "Authorization: Bearer $TOK" https://$REG/v2/$REPO/manifests/$TAG`.
On 200, read `.manifests[].platform`. Tags were listed via `GET /v2/$REPO/tags/list?n=1000`.

| Image                                                                                                                                                                                                                                                                                                                                                                       | Anonymous?                                                                    | Platforms                                                                                                                           |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `ghcr.io/nvidia-ai-blueprints/vss/{vss-rt-vlm, vss-rt-cv, vss-rt-embed, vss-video-summarization, vss-agent, vss-agent-ui, vss-alert-ms, vss-behavior-analytics, vss-configurator, vss-rt-config-adaptor, vss-rt-cv-mv3dt-bev-fusion, vss-rt-cv-mv3dt-config-init, vss-video-analytics-api, vss-vios-{ingress,nvstreamer,sensor,streamprocessing}, sdr-mw-l}:develop-latest` | **200**                                                                       | linux/amd64 + linux/arm64 (arm64 = Jetson/igpu for RTVI)                                                                            |
| same RTVI + video-summarization `:develop-latest-sbsa`                                                                                                                                                                                                                                                                                                                      | **200**                                                                       | linux/arm64 only                                                                                                                    |
| `ghcr.io/…/vss-rt-vlm:{3.3.0,latest,release-3.3.0}`                                                                                                                                                                                                                                                                                                                         | **404**                                                                       | GHCR carries only `develop-*`, `nightly-*` and `tree-*` tags (tag list of 1,000). Release images are NGC-only (`README.md:103-105`) |
| `nvcr.io/nvidia/vllm:26.03-py3`, `:26.07-py3`; `nvidia/pytorch:26.03-py3`; `nvidia/deepstream:{9.1-triton-multiarch, rtvi_ds9.1.1-triton-dev135}`                                                                                                                                                                                                                           | **200**                                                                       | amd64 + arm64                                                                                                                       |
| `nvcr.io/nim/nvidia/nemotron-3.5-lightning-30b-a3b:2.0.9-variant`                                                                                                                                                                                                                                                                                                           | **200** (manifest and config blob). Weights still need NGC at runtime **[A]** | amd64 + arm64                                                                                                                       |
| `nvcr.io/nim/nvidia/cosmos3-reasoner:1.7`                                                                                                                                                                                                                                                                                                                                   | **401**                                                                       | —                                                                                                                                   |
| `nvcr.io/nvstaging/vss-core/{vss-agent, reid-embed, vss-auto-calibration*, vss-video-analytics-ui}`; `nvcr.io/nvidia/vss-core/vss-rt-vlm:3.3.0`                                                                                                                                                                                                                             | **401**                                                                       | —                                                                                                                                   |
| `ghcr.io/ggml-org/llama.cpp:{server-cuda, server-cuda13}` (our LLM)                                                                                                                                                                                                                                                                                                         | **200**                                                                       | amd64 + arm64                                                                                                                       |

- **Docs agree:** "Managed VSS images on ghcr.io are public and require no registry login"
  (`docs/prerequisites.mdx:247,304`). **[V]**
- **Inventory:** `deploy/docker/container-inventory.json` declares amd64+arm64 for the managed
  set and arm64-only for the `-sbsa` variants. Mirrored-only images are amd64-only (auto-calibration,
  calibration, video-analytics-ui). **[V]**
- **Build matrix:** `build-dev-images.yml` builds on GitHub-hosted runners with QEMU or
  native-arch runners (`:195,221,302-321`). There is **no GPU in image CI**. **[V]**
- **HF weights:** `nvidia/NVIDIA-Nemotron-Nano-9B-v2-FP8` is `gated:false`, with 10,285,094,008
  bytes of safetensors. `nvidia/Cosmos3-Nano-Reasoner` returns null/401.
  `nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-NVFP4-QAD` is `gated:false`.
  **[E: `curl https://huggingface.co/api/models/<repo>`]**
- **Download weight for a consumer:** RT-VLM 11.3 + RT-CV 17.8 + RT-Embed 12.2 GB compressed.
  **[E]**

---

## 5. Testing and CI for profiles

| Check                                                                            | Trigger / runner                                                                                                                          | Covers profiles?                                                                                                         | Blocking?                                                                         |
| -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| `ci.yml` (all jobs)                                                              | push to `pull-request/<N>` mirror, created by copy-pr-bot (`ci.yml:16-23`; `.github/copy-pr-bot.yaml:1-60` vetter list)                   | —                                                                                                                        | per-job                                                                           |
| `folder-structure`                                                               | `ci.yml:1314` → `check_folder_structure.py`                                                                                               | `developer-profiles/` top level only                                                                                     | yes                                                                               |
| `compose-golden`                                                                 | `ci.yml:1419-1461`                                                                                                                        | Resolved default image refs vs `compose-images.golden`                                                                   | yes                                                                               |
| `test` (pytest)                                                                  | `ci.yml:416-518`, `services/agent`                                                                                                        | Orchestrator tests parse dev-profile.sh (`test_docker_compose_util.py:1964-1968`)                                        | yes                                                                               |
| `rtvi-vllm-compatible-test`                                                      | `ci.yml:888-962`                                                                                                                          | RT-VLM / RT-Embed unit tests, including SBSA decoder platform selection (`5e0949f1e`)                                    | yes                                                                               |
| `lint` yamllint                                                                  | `ci.yml:327-337`                                                                                                                          | **only `.github/**`and`services/**`YAML;`deploy/` is not linted**                                                        | yes                                                                               |
| `copyright-headers`                                                              | `ci.yml:1198-1221`                                                                                                                        | `.py/.ts/.js` only (`check_copyright_headers.py:24`)                                                                     | yes                                                                               |
| `dco`                                                                            | `ci.yml:1223-1313`                                                                                                                        | every PR commit                                                                                                          | yes                                                                               |
| **`test-dev-profile.sh`**                                                        | **not invoked by any workflow** (grep)                                                                                                    | 192 cases, all dry-run with mocked `nvidia-smi`                                                                          | **not in GitHub CI** **[V]**. Possibly in the private downstream pipeline **[?]** |
| **`docker compose config` on profiles**                                          | **no workflow runs it** (grep)                                                                                                            | —                                                                                                                        | **[V]** absent                                                                    |
| `trigger-downstream-pipeline`                                                    | `ci.yml:1547-1630`, `[self-hosted, downstream-pipeline]`, private GitLab (`/api/v4`), up to 4 h                                           | unknown (private)                                                                                                        | gates on success **[A]**                                                          |
| `osrb-scan.yml` (the renamed `license-diff.yml`, `.github/osrb/MIGRATION.md:99`) | mirror push                                                                                                                               | Compose files count as dependency files (`osrb_scan.py:557-566`). A new third-party image creates review rows            | **fails** on review or uncovered rows (`osrb-scan.yml:211-253`)                   |
| `helm-sync.yml`                                                                  | `[self-hosted, vss-brev-runner]`, Claude agent SDK                                                                                        | Any `deploy/docker` change without matching helm gets `BLOCKED: helm drift`, exit 1 (`.github/helm-sync/AGENTS.md:1-40`) | **yes**                                                                           |
| `skills-review.yml` / `vss-playbook-compliance.yml` / `skills-signatures.yml`    | skills changes; LLM review on self-hosted runners                                                                                         | skill references                                                                                                         | review / comment                                                                  |
| `skills-eval.yml`                                                                | `[self-hosted, vss-skill-eval-runner]`, Brev pools (L40S, H100, RTX PRO 6000, Spark; 4090 dormant) (`.github/skill-eval/README.md:25-35`) | end-to-end skill deploys on real GPUs                                                                                    | per spec                                                                          |
| `tracking-ref-check.yml`                                                         | `pull_request_target`                                                                                                                     | wants a `VIA-<n>` JIRA or NVBugs ref; **non-blocking** (`check_tracking_ref.py:4-12`)                                    | no                                                                                |

- **A contributed profile would have to pass:** the ci.yml jobs above (notably folder-structure,
  compose-golden, pytest, dco), OSRB (if a new image is added), helm-sync parity, and skills
  review for skill edits. Evals run only if a spec targets the tier. In practice, reviewers also
  expect `test-dev-profile.sh` additions: every RTXPRO4500BW and GB300 change added them
  (`979ab595a`, `8e1c8ccdc`, `dcc709dcc`). **[V]**
- **Hardware in the loop:** it all runs on NVIDIA-internal self-hosted runners. That includes
  Brev pools and the 4090 runners, which are dormant pending #1466 and a spec-level route.
  **An external contributor cannot target them**, and even an `@nvidia.com` author needs a
  spec with a GeForce `gpu_type` and pool wiring. **Expect to supply your own evidence:**
  measured `nvidia-smi` logs, readiness, and workload traces. **[V]/[A]**

---

## 6. Contribution and governance

- **License / DCO / CLA:**
  - Apache-2.0 inbound=outbound (`CONTRIBUTING.md:21-27`).
  - **DCO sign-off is mandatory** (`:49-114`) and enforced by the `dco` job (`ci.yml:1223`).
  - **No CLA** is mentioned (grep).
  - New features are **design-first**: "Post about your intended feature, and we shall discuss
    the design" (`CONTRIBUTING.md:11-15`).
  - Branch naming `<type>/<name>` (`:201-213`).
  - PR template checklist (`.github/PULL_REQUEST_TEMPLATE.md`).
  - **[V]**
- **CODEOWNERS:**
  - The default `*` → `@NVIDIA-AI-Blueprints/VSS-developers`. This **covers `deploy/`**, which
    has no dedicated owner.
  - `/skills/` → `@…/VSS-Skill-Developers`.
  - `/.github/` → `@…/vss-maintainers`.
  - Dockerfiles, lockfiles and manifests → `@…/VSS_OSRB_Approvers` (`.github/CODEOWNERS:9,16,24,31-81`).
  - **[V]**
- **CI gating for outsiders:** CI runs only on `pull-request/<N>` mirrors that copy-pr-bot
  creates after a vetter approves (`copy-pr-bot.yaml:1-60`, 56 vetters). **[V]** The
  `/ok to test` mechanics are **[A]**.
- **Release cadence:**
  - Tags `v3.2.0` (2026-06-17) and `v3.2.1` (2026-07-15).
  - `release_metadata.yaml` says `3.3.0`, which is not yet tagged.
  - `dev-YY.MM.N` tags roughly every 1–2 weeks, plus daily `nightly-*`
    (`git tag --sort=creatordate`).
  - **[V]**
- **API stability / deprecation policy:** **none found** (grep for deprecation policy,
  stability, semver and backward-compat in docs → no policy). Deprecation is ad hoc:
  per-release "Upgrading from 3.2.x" notes (`docs/release-notes.mdx:55-66`;
  `docs/long-video-summarization.mdx:82`), a removed skill (`vss-deploy-profile` →
  `vss-build-vision-ai`, `release-notes.mdx:12-26`), and the NGC notice below. **[V]**
  Confirms the prior docs.
- **NGC removal notice:** "Older affected 2.x, 3.0, and 3.1 container images are deprecated …
  will be removed from NGC on September 30, 2026" (`docs/release-notes.mdx:80`, under 3.2.1).
  **[V]**
- **Upstream issues and PRs on consumer/GeForce** (`gh search issues|prs --repo …`, queries:
  4090, 5090, GeForce, consumer, llama.cpp, 24GB, 3090, sm_120, sm_89) **[E]**:
  - No issue or PR proposes consumer or GeForce support.
  - GeForce appears only in skill-eval PRs (#1339, #1406, #1466, #1818).
  - Community demand exists in #1556 ("hardcoded hardware architecture"; support's answer was
    Ampere+ and the remote-vLLM workaround), #1563 (RTX 8000 via OTHER), #1091 (offline
    without an NGC key), #42 and #59 (single GPU).
  - The PM "not on the roadmap" statement stays **[O]**. Nothing public contradicts it, and
    the dormant 4090 runners do not imply roadmap.
- **Useful templates:**
  - PR #682 "RTX 4500 support via dev-profiles script" touched only 4 profile `.env` files,
    `dev-profile.sh` and `test-dev-profile.sh` (`gh pr view 682`).
  - PR #437 "Allow OTHER hw profile for all GPUs".
  - PR #1187 "Add NIM GPU tuning for OTHER hardware profile".
  - **[E]**

---

## 7. Changes since `cdad5cc0e` that matter for a consumer tier

| Commit                                                                | Change                                                                                                                                                                                                                                                                                                                                                         | Why it matters                                                                                                                                                  |
| --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `979ab595a` / `8e1c8ccdc` / `1cbb06de2` / `5f03baab0` (2026-09-21/22) | RTXPRO4500BW is now alerts-only, `--use-remote-llm` required, **≥ 2 GPUs**, driver ≥ 595.58.03 (`dev-profile.sh:1037-1051,1161-1179`); tests use `EXPECTED_ERROR`                                                                                                                                                                                              | The 32 GB tier is no longer a single-card precedent. It is the template for **restriction + prerequisite** checks, including `version_is_at_least` (`:105-112`) |
| `21f686e37` (#2321)                                                   | GB300 single-GPU closure added to `sizing.md:112-161` and a Search row (`:302`)                                                                                                                                                                                                                                                                                | The **only single-GPU discrete template**, in both script and skill                                                                                             |
| `05bec708b` (#2052); `a76afbe73` (#2259)                              | RT-VLM utilization table added (`docs/real-time-vlm.mdx:1511-1531`, #2052); "does not support cosmos-reason1 in VSS 3.3" removed and CR1 back in the table (`:85`, #2259); "ghcr public" statement (`docs/prerequisites.mdx:247`, #2259)                                                                                                                       | New doc touch point                                                                                                                                             |
| `5e0949f1e`                                                           | RT-VLM `ARM_PLATFORM` default flipped to `igpu`; SBSA only via `-sbsa`                                                                                                                                                                                                                                                                                         | arm64 (GB300) must use `-sbsa` tags, which dev-profile derives (`:2163-2182`)                                                                                   |
| rt-embed `Dockerfile`                                                 | SEI-aware `nvunixfd` for the RT-CV → RT-Embed frame IPC                                                                                                                                                                                                                                                                                                        | RT-Embed/RT-CV coupling on a shared GPU                                                                                                                         |
| `8d9f55a6e`, `a76afbe73`                                              | README and helm READMEs aligned to the existing host prerequisites. Those prerequisites were **unchanged since `cdad5cc0e`**: driver 595.58.03 on x86, Docker `< 29.5.0`, min system 18 cores / 128 GB RAM / 1 TB (`docs/prerequisites.mdx:36-43,175-184`). The "1 or 2 recommended GPUs" line became "one to four GPUs depending on the profile" (`:180-183`) | The documented host floor is far above a consumer PC. It is not new, but a consumer tier must restate it                                                        |
| `.github/skill-eval` (15 files)                                       | model-route split; RTX4090 tests hardened                                                                                                                                                                                                                                                                                                                      | 4090 still unrouted                                                                                                                                             |
| `a7f8b1f5f`, `4abf68ecd`                                              | skill container-tag override                                                                                                                                                                                                                                                                                                                                   | Skill build path                                                                                                                                                |
| rt-vlm README trimmed (−168 lines)                                    | EVS / 12B-VL recipe moved (§8)                                                                                                                                                                                                                                                                                                                                 | Citations                                                                                                                                                       |

---

## 8. Stale or moved citations in `docs/vss-integration`

| Doc        | Cited                                                                   | Status at `1e94133b4`                                                                                                                                                                                                                                                             |
| ---------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 04, 05, 07 | `deploy/docker/scripts/dev-profile.sh:1161-1165`                        | **Moved → `:1211-1216`**, and it is a comment in the edge-search block, not a general hard error (§2.2)                                                                                                                                                                           |
| 04         | `.github/skill-eval/run_leg.py:58-61`                                   | Tables at **`:62-63`** (prefix `:58`, comment `:59-61`)                                                                                                                                                                                                                           |
| 04         | `docs/prerequisites.mdx:282-295`                                        | **Moved → `:370-381`**. It had **two** rows (verification and real-time), each needing **2 GPUs**, at `cdad5cc0e` too; "exactly one row" was inaccurate                                                                                                                           |
| 04         | `services/rtvi/rt-vlm/docker/Dockerfile:67` (`TORCH_CUDA_ARCH_LIST`)    | **→ `:73`**                                                                                                                                                                                                                                                                       |
| 04         | `Dockerfile:380` (vLLM pin)                                             | **→ `:381`**                                                                                                                                                                                                                                                                      |
| 04         | `vllm_compatible_model.py:632` (+ `:638,1692,1784,2486,3738,3831,3862`) | `:632,638,1692` OK; others moved **→ `:1799,2506,3759/3765,3852,3883`**                                                                                                                                                                                                           |
| 04         | rt-vlm `README.md:838-843` (EVS numbers)                                | **→ `:797-800`**                                                                                                                                                                                                                                                                  |
| 04         | rt-vlm `README.md:845-852` (12B-VL recipe)                              | **→ `:802-810`**                                                                                                                                                                                                                                                                  |
| 04         | `src/vlm_pipeline/model_path_policy.py:41-55`                           | OK (`:41-55`, raise at `:52`)                                                                                                                                                                                                                                                     |
| 04         | `docs/real-time-vlm.mdx:18` (CR1 unsupported in 3.3)                    | **Gone**; CR1 listed at `:85`                                                                                                                                                                                                                                                     |
| 04         | `docs/real-time-vlm.mdx:77,81`                                          | **→ `:75,79`**                                                                                                                                                                                                                                                                    |
| 04         | `docs/real-time-vlm.mdx:93` (hallucination note)                        | **→ `:91`**                                                                                                                                                                                                                                                                       |
| 02         | `docs/real-time-vlm.mdx:1529`                                           | **→ `:1596`**                                                                                                                                                                                                                                                                     |
| 02         | `docs/real-time-vlm.mdx:82`, `:83`, `:85`                               | **→ `:80`, `:81`, `:83`**                                                                                                                                                                                                                                                         |
| 02         | `docs/real-time-vlm.mdx:1622` / `:1650` / `:97`                         | **→ `:1689` / `:1721` / `:95`**                                                                                                                                                                                                                                                   |
| 04         | "5 lines across 2 files" for `nemotron-nano-12b`                        | Now **3 lines** across the same 2 files                                                                                                                                                                                                                                           |
| 02         | `deploy/helm/developer-profiles/dev-profile-base/values-base.yaml:23`   | OK                                                                                                                                                                                                                                                                                |
| 05, 06     | `README.md:99`                                                          | OK                                                                                                                                                                                                                                                                                |
| 07         | `.github/scripts/check_folder_structure.py:33-42`                       | OK                                                                                                                                                                                                                                                                                |
| 07         | `dev-profile-lvs/.env:124`                                              | OK                                                                                                                                                                                                                                                                                |
| 07         | `infra/compose.yml:181,292,119`                                         | OK                                                                                                                                                                                                                                                                                |
| 07         | `redis.conf:1407`                                                       | OK                                                                                                                                                                                                                                                                                |
| 07         | `rt-vlm/src/api_models/config.py:46-50`                                 | OK                                                                                                                                                                                                                                                                                |
| 07         | `via_stream_handler.py:505,1861`                                        | OK                                                                                                                                                                                                                                                                                |
| 07         | `via_server.py:1031,1108`                                               | OK (messages at `:1033,1110`)                                                                                                                                                                                                                                                     |
| 07         | `services/video-summarization/docker/Dockerfile:67,72`                  | OK                                                                                                                                                                                                                                                                                |
| 07         | `test_event_bridge_factory.py:16-27`                                    | OK                                                                                                                                                                                                                                                                                |
| 07         | `mdx-lvs-logstash.conf:1-18`                                            | OK                                                                                                                                                                                                                                                                                |
| 07         | "`license-diff.yaml` hard-fails dependency changes"                     | **Renamed:** `.github/workflows/license-diff.yml` → `osrb-scan.yml` (`.github/osrb/MIGRATION.md:99`). It fails on OSRB review or uncovered rows (`osrb-scan.yml:211-253`)                                                                                                         |
| 07         | "existing docker-less `unit-tests` job"                                 | **No job named `unit-tests`** in VSS workflows at either commit (grep). The closest is `test` "Test (pytest)" (`ci.yml:416`). Probably a CAR-repo job **[?]**                                                                                                                     |
| 05         | "Foundations: alerts, search, warehouse, public safety, smart city"     | **Inaccurate**; see §1.1                                                                                                                                                                                                                                                          |
| 05         | "RT-CV … 95-96% SM at 2-3 streams"                                      | These are **DGX Spark** max-stream measurements (95.5% at 5 streams, 95.0% at 3; `docs/performance-rt-cv.mdx:66-67`). On L40S, GDINO is 3 streams at 84.6% (`:59`). "~3.0 GB" has **no in-repo source** **[?]**                                                                   |
| 04         | "RT-Embed is a fixed 10 GB … no knob"                                   | **Partly wrong.** "Reserve about 10 GB" is a Search starting value (`sizing.md:290-291`). Knobs exist (`sizing.md:95,318-319`; `rt-embed.md:25`). "Fixed footprint" means non-elastic (`rt-embed.md:57`). The engine build needs about 6 GiB on Thor (`dev-profile.sh:1215-1216`) |

---

## 9. What a new consumer profile would minimally consist of

The minimal viable shape is a **hardware tier on the existing `base` Foundation**, with a remote
(same-box) llama.cpp LLM. It is the only profile with no reserved GPU, no Kafka and no ES
(`dev-profile-base/overrides.env:199`; `.env:44`). The example uses `RTX4090`; repeat per SKU,
or use one VRAM-class alias (§1.8).

```
deploy/docker/scripts/dev-profile.sh
  ├─ _valid_hardware_profiles + msg (:1031,:1033)        # accept RTX4090
  ├─ get_detected_hardware_profile (:136-149)            # "*geforce*rtx*4090*" → RTX4090
  ├─ policy case (:1037-1051)                            # base[/alerts] only; require --use-remote-llm
  ├─ prereq case (:1161-1179)                            # 1 GPU ok; driver floor; NEW VRAM floor
  ├─ RESERVED_DEVICE_IDS exemption (:1392)               # only if alerts is in scope
  ├─ single-GPU closure (GB300 pattern :1319-1324,:1882-1888,:2025-2029)  # alerts/search only
  ├─ get_rtvi_vllm_gpu_memory_utilization (:591-633)     # e.g. 0.45–0.55, not OTHER's 0.7
  ├─ get_rtvi_vlm_max_model_len (:635-641)               # e.g. ≤18000
  └─ checkpoint pin (:2038-2041)                         # CR3 Nano FP8 on sm_89/120 (sm_86: [?])
deploy/docker/services/rtvi/rtvi-vlm/rtvi-vlm-docker-compose.yml
  └─ expose RTVI_VLLM_KV_CACHE_MEMORY_BYTES / _KV_CACHE_DTYPE / _ENFORCE_EAGER   # deterministic co-residence
deploy/docker/scripts/vss_orchestrator_mcp_config.yml (:88-)  # hardware_profiles.RTX4090 (allow-list)
deploy/docker/test-scripts/test-dev-profile.sh           # mock nvidia-smi "NVIDIA GeForce RTX 4090", positive + EXPECTED_ERROR cases
deploy/helm/services/nims/values.yaml (:41,:50-134)      # gpuProfiles.RTX4090 (helm-sync parity; may be {})
docs/prerequisites.mdx (:10-19,:36-41, new <Tab>)        # validated list, driver, GPU-count table
docs/real-time-vlm.mdx (:1511-1531)                      # RT-VLM utilization row
skills/vss-build-vision-ai/references/sizing.md (:60-69,:163-171,:186-194)  # GPU row, RT-VLM row, constraints
skills/vss-build-vision-ai/SKILL.md (:82)                # routing row if restricted
skills/vss-build-vision-ai/references/prerequisites.md (:365-375)  # driver row
skills/vss-build-vision-ai/references/profiles/base.md (:10)       # hardware bullet
[optional] services/nim/nvidia-nemotron-nano-9b-v2-fp8/hw-RTX4090[-shared].env  # only if offering a VSS-managed local LLM
[optional] .github/skill-eval/adapters/*/generate.py PLATFORMS + skills/*/eval/*.json platforms  # to use the dormant 4090 runners
[not needed] check_folder_structure.py, containers.env, container-inventory.json, compose-images.golden (unless an image is added)
[out of band] llama.cpp server: bind a container-reachable host IP (not 127.0.0.1); LLM_ENDPOINT_URL without /v1; single model in /v1/models or pass --llm
```

**Two alternatives with different surfaces:**

- A **new developer profile** (`dev-profile-home/`) brings a large surface (§1.7 end).
- A **downstream skill Delta build** (`_builds/<name>/override.env` + `patches/<key>.yml` that
  adds a llama.cpp service) needs **zero upstream changes**, bypasses dev-profile.sh, and still
  resolves through the same Compose graph (`composition.md:170-240`;
  `references/deployment.md:38-88`). **[V]**

---

## 10. Open questions

1. Does the NGC vLLM 26.03 build (base `CUDA_ARCH_LIST … 12.0`, not `12.0a`) include sm_120a
   NVFP4/FP8 block-scaled kernels? The same question applies to sm_89 CUTLASS FP8. This needs a
   runtime log on real hardware. **[?]**
2. Does sm_120 need `RTVI_VLLM_ATTENTION_BACKEND=TRITON_ATTN` as GB300 does? **[?]**
3. What is the Cosmos3 Nano Reasoner parameter count and blob size? The HF repo returns 401 and
   the NGC `cosmos3-reasoner` NIM returns 401. **[?]**
4. Is Cosmos3 FP8 truly unusable on sm_86? The docs speak only to A100. **[?]**
5. Does the private downstream GitLab pipeline run `test-dev-profile.sh` or any GPU profile
   bring-up? **[?]**
6. Which checks are _required_ by branch protection? This is not visible from the tree. **[?]**
7. Is there a 595-branch GeForce Linux driver? Does the Lightning NIM's
   `min_vram_per_device_gb: 32.0` admit a 5090 (32,607 MiB)? **[?]**
8. Is the vLLM 0.17 `kv_cache_memory_bytes` accepted? (The code checks the signature at
   `vllm_compatible_model.py:1509-1521`.) **[?]**
9. How does our llama.cpp config (24.57 GB Q4_K_M, 262k context, `GPU_LAYERS=auto`) actually
   place on the 24 GB A5500 today? This is the baseline for any co-residence math. **[?]**
