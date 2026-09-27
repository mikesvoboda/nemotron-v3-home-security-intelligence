# A5500 bring-up checklist (vlm mode, plan 1.7) - dated copy with [V] repo-side amendments from the prep review

Dated 2026-09-27. Source: spec §'A5500 bring-up checklist (step 0.2)' (docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md) as amended by plan 1.7 to the shipped vlm mode (spec rev 5 / F10: the legacy LLM path is unsupported - the checklist's placeholder-LLM rows became serving-VLM rows). Repo-side prep via `scripts/a5500_precheck.py` (F9/F6: execution is owner-run on real media; this document claims no execution).

Ordering guard: lifted 2026-09-25 by ledger F9 (no pre-switch traffic exists); re-arms the day the home stack serves live events.

## - [ ] GPU assignment

Set every `GPU_*` variable to `0` (.env.example documents "SINGLE-GPU: Set all to 0"). Remove the A400 from device passthrough.

- repo verdict: `gpu_assignment`: **FAIL** - SINGLE-GPU requires all GPU\_\*=0; non-zero: GPU_YOLO26=1, GPU_CLIP=1, GPU_ENRICHMENT=1, GPU_ENRICHMENT_LIGHT=1, GPU_AI_SERVICES=1
- repo verdict: `device_passthrough`: **WARN** - nvidia.com/gpu=all (CDI passthrough of ALL devices) in docker-compose.ghcr.yml, docker-compose.prod.yml - confirm the retired A400 is out of the CDI/handler set; CUDA placement then rides CUDA*VISIBLE_DEVICES=${GPU*\*}
- [V 2026-09-27] .env.example:567 documents 'SINGLE-GPU: Set all to 0'; shipped defaults are dual-GPU: GPU_YOLO26/CLIP/ENRICHMENT/ENRICHMENT_LIGHT=1 (:580-583) and GPU_AI_SERVICES=1 (:962) - set all to 0 on the A5500 box (GPU_LLM/GPU_FLORENCE already ship 0, :578-579)
- [V 2026-09-25, anchors re-checked 2026-09-27] amend: compose carries NO per-device A400 entry to remove. docker-compose.prod.yml ai-vlm uses nvidia.com/gpu=${GPU_LLM:-0} (:244); :415 and :1392 pass nvidia.com/gpu=all (rootless-podman CDI design comment at :442). A400 removal is therefore CDI-handler / physical, not a compose edit - confirm the retired card is out of the CDI set

## - [ ] CUDA architecture

`CUDA_ARCHITECTURES=86`. Check it BEFORE building `ai-vlm` (the shipped mode's build; the retired mode's `ai-llm` build takes the same value).

- repo verdict: `cuda_arch`: **FAIL** - CUDA_ARCHITECTURES='89', expected 86 (A5500 = Ampere sm_86). .env.example ships 89; setup.py's auto-detect only rewrites it when setup.py runs against the GPU - CHECK BEFORE BUILDING ai-vlm (the shipped mode's build consumes this value; prod compose :240)
- [V 2026-09-27] .env.example:576 ships CUDA_ARCHITECTURES=89; docker-compose.prod.yml:240 threads ${CUDA_ARCHITECTURES:-} into the ai-vlm build (the :136 ai-llm line serves the retired mode); ai/vlm/Dockerfile:64 treats it as a build-arg - check-before-build stands

## - [ ] Serving VLM

The A5500 brings up the SHIPPED vlm mode (1.7, spec rev 5): `VLM_MODEL_PATH` at the `Qwen3-VL-4B-Instruct` Q4*K_M GGUF AND `VLM_MMPROJ_PATH` at its mmproj projector (two files - a projector-less serve loads text-only and silently degrades every vlm_assess). `ai-vlm`'s `/models` mount must target the `vlm` weights dir, and `MODEL_PATH`/`MMPROJ_PATH` must stay derived from the `VLM*\*`vars so a`.env`switch reaches the container. Per-slot context =`VLM_CTX_SIZE`/`VLM_PARALLEL` must cover a worst-case vlm_assess (~12.2K tokens; the shipped 32768/2 = 16384 does). MANDATORY ordering: smoke-serve Qwen3-VL-4B and run the P0.3 enforcement probe (a refusal check against the serving path) BEFORE any event reaches it - never attach live traffic to an unprobed server.

- repo verdict: `vlm_model`: **PASS** - VLM pair: /models/Qwen3VL-4B-Instruct-Q4_K_M.gguf + /models/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf
- repo verdict: `ai_vlm_mount`: **PASS** - ai-vlm weights mount: docker-compose.prod.yml: - ${AI_MODELS_PATH:-/export/ai_models}/vlm:/models:ro
- repo verdict: `vlm_model_env_passthrough`: **PASS** - MODEL_PATH/MMPROJ_PATH derive from VLM_MODEL_PATH/VLM_MMPROJ_PATH in every ai-vlm definition
- repo verdict: `vlm_ctx_budget`: **INFO** - per-slot 16384 tokens (CTX=32768/PARALLEL=2) covers the ~12200 worst case; VLM_GPU_LAYERS=auto
- repo verdict: `vlm_image`: **WARN** - no ai-vlm service in docker-compose.ghcr.yml - the ghcr image path cannot serve the shipped vlm mode; run docker-compose.prod.yml with --profile vlm on the A5500 box
- [V 2026-09-27] the shipped mode is the VLM path: PIPELINE_MODE=vlm and GATEWAY_MODEL_SET=vlm are the .env.example defaults (:211,:221) and the residency comment records that the mode 'calls nothing else' (:218); ai-vlm is profile-gated profiles:[vlm] (docker-compose.prod.yml:221,:227-228) - bring-up runs the VLM, not the Nano-4B placeholder plan
- [V 2026-09-27] the pair ships correct: VLM*MODEL_PATH at Qwen3VL-4B-Instruct-Q4_K_M + VLM_MMPROJ_PATH at the Q8_0 mmproj (.env.example:462-463); prod compose mounts ${AI_MODELS_PATH:-/export/ai_models}/vlm:/models:ro (:253) and derives MODEL_PATH/MMPROJ_PATH from the VLM*\* vars (:265-266) - the weights are NOT what the A5500 lacks
- [V 2026-09-27] amend (ghcr-hardcode fact, kept from the P0.2 review and still true in kind): docker-compose.ghcr.yml has NO ai-vlm service at all - the ghcr image path cannot serve the shipped mode. Run docker-compose.prod.yml with --profile vlm on the A5500 box (that compose file also hardcodes its legacy ai-llm's MODEL_PATH=...Q2_K_L.gguf at :172, unchanged)

## - [ ] No legacy LLM

No legacy LLM serving path is deployed on the A5500 (spec :482-500 / F10): the `ai-llm` service stays in the tree - its tests keep passing, nothing is deleted - but it must NOT start alongside `ai-vlm`. Keep it out of the up set.

- repo verdict: `legacy_llm`: **WARN** - ai-llm has NO profiles: block in docker-compose.ghcr.yml, docker-compose.prod.yml - a --profile vlm up starts the retired serving path ALONGSIDE ai-vlm (one A5500 GPU cannot serve both); profile-gate it or keep it out of the up set (F10 keeps the service, not its deployment)
- [V 2026-09-27] prod compose's ai-llm has NO profiles: block (:120 - the P0.2-era anchor :139 is its devices line), so `podman compose --profile vlm up` starts the retired 30B serving path ALONGSIDE ai-vlm; one A5500 cannot serve both. F10 keeps the service (its tests keep passing, nothing gets deleted) - keep it out of the up set: run only the vlm profile and do not start ai-llm

## - [ ] Test-environment traps

- A `TMPDIR` in `.env` that differs from pytest's `tmp_path` false-reddens four `write_runtime_env` tests; CI sets no `TMPDIR`.
- Stale `__pycache__` directories for deleted modules false-redden deletion guards.
- repo verdict: `tmpdir_trap`: **WARN** - TMPDIR=/ephemeral/podman-tmp in the env file: \_runtime_env_path() gates against tempfile.gettempdir(), so an env TMPDIR unlike pytest's tmp_path false-reddens the four write_runtime_env tests (test_system.py x2, test_system_routes.py x2); CI sets no TMPDIR - unset it for test runs
- repo verdict: `pycache_stale`: **WARN** - 12 stale .pyc file(s) whose module source is gone - these false-redden deletion guards: ai/enrichment/models/**pycache**/action_recognizer.cpython-314.pyc, ai/gateway/adapters/**pycache**/lifecycle.cpython-314.pyc, ai/gateway/tests/**pycache**/test_adapters_lifecycle.cpython-314-pytest-9.1.1.pyc, backend/services/**pycache**/action_recognition_service.cpython-314.pyc, backend/services/**pycache**/xclip_loader.cpython-314.pyc, backend/tests/integration/**pycache**/t_sparse_probe_tmp.cpython-314-pytest-9.1.1.pyc, backend/tests/integration/**pycache**/test_action_events.cpython-314-pytest-9.1.1.pyc, backend/tests/integration/**pycache**/test_action_recognition_service.cpython-314-pytest-9.1.1.pyc, backend/tests/integration/**pycache**/test_zz_probe_settings.cpython-314-pytest-9.1.1.pyc, backend/tests/unit/services/**pycache**/test_action_recognition_service.cpython-314-pytest-9.1.1.pyc (+2 more)
- [V 2026-09-25, anchors re-checked 2026-09-27] TMPDIR=/ephemeral/podman-tmp at .env.example:57; backend/api/routes/system.py:2508 \_runtime_env_path() gates on tempfile.gettempdir() -> the four write_runtime_env tests (unit/api/routes/test_system.py:576,:598; unit/routes/test_system_routes.py:106 and its sibling) false-redden when env TMPDIR differs from pytest tmp_path. CI sets no TMPDIR
- [V 2026-09-25] pycache trap: scripts/a5500_precheck.py scan_stale_pycache() lists .pyc files whose source module is deleted (run it before trusting any deletion-guard run)

## - [ ] Health

Run `/platform-healthcheck`, and complete the root `AGENTS.md` infrastructure verification checklist.

- repo verdict: `health`: **MANUAL** - owner-run on the A5500: /platform-healthcheck + root AGENTS.md infrastructure verification checklist (compose config -q, services Up+healthy, Prometheus targets, API health). Sandbox precheck can never close this row
- [O] owner-run on the A5500: /platform-healthcheck + root AGENTS.md Infrastructure Verification checklist; ledger row carries the machine
