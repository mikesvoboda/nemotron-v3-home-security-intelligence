# A5500 bring-up checklist (step 0.2) - dated copy with [V] repo-side amendments from the P0.2 prep review

Dated 2026-09-25. Source: spec §'A5500 bring-up checklist (step 0.2)' (docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md). Repo-side prep via `scripts/a5500_precheck.py` (F9/F6: execution is owner-run on real media; this document claims no execution).

Ordering guard: lifted 2026-09-25 by ledger F9 (no pre-switch traffic exists); re-arms the day the home stack serves live events.

## - [ ] GPU assignment

Set every `GPU_*` variable to `0` (.env.example documents "SINGLE-GPU: Set all to 0"). Remove the A400 from device passthrough.

- repo verdict: `gpu_assignment`: **FAIL** - SINGLE-GPU requires all GPU\_\*=0; non-zero: GPU_YOLO26=1, GPU_CLIP=1, GPU_ENRICHMENT=1, GPU_ENRICHMENT_LIGHT=1, GPU_AI_SERVICES=1
- repo verdict: `device_passthrough`: **WARN** - nvidia.com/gpu=all (CDI passthrough of ALL devices) in docker-compose.ghcr.yml, docker-compose.prod.yml - confirm the retired A400 is out of the CDI/handler set; CUDA placement then rides CUDA*VISIBLE_DEVICES=${GPU*\*}
- [V 2026-09-25] .env.example:503 documents 'SINGLE-GPU: Set all to 0'; shipped defaults are dual-GPU: GPU_YOLO26/CLIP/ENRICHMENT/ENRICHMENT_LIGHT=1 (:516-519) and GPU_AI_SERVICES=1 (:899) - set all to 0 on the A5500 box
- [V 2026-09-25] amend: compose carries NO per-device A400 entry to remove. docker-compose.prod.yml:139 uses nvidia.com/gpu=${GPU_LLM:-0}; :303 and :1262 pass nvidia.com/gpu=all (rootless-podman CDI design comment at :300,:320). A400 removal is therefore CDI-handler / physical, not a compose edit - confirm the retired card is out of the CDI set

## - [ ] CUDA architecture

`CUDA_ARCHITECTURES=86`. Check it BEFORE building `ai-llm`.

- repo verdict: `cuda_arch`: **FAIL** - CUDA_ARCHITECTURES='89', expected 86 (A5500 = Ampere sm_86). .env.example ships 89; setup.py's auto-detect only rewrites it when setup.py runs against the GPU - CHECK BEFORE BUILDING ai-llm
- [V 2026-09-25] .env.example:512 ships CUDA_ARCHITECTURES=89; docker-compose.prod.yml:136 threads ${CUDA_ARCHITECTURES:-} into the ai-llm build; setup.py:490 writes the auto-detected value only when setup.py runs - check-before-build stands

## - [ ] Placeholder LLM

Point `LLM_MODEL_PATH` at `NVIDIA-Nemotron-3-Nano-4B` Q4_K_M (official GGUF, 2.64 GiB; arch `nemotron_h`, registered by llama.cpp b7972). Adjust the `ai-llm` volume mount (it targets the 30B dir). Budget ~5.5 GiB including the 262K-token KV. The 30B GGUF STAYS on disk - it is the replay control.

- repo verdict: `llm_model`: **FAIL** - LLM_MODEL_PATH='/models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf': spec 0.2 wants the Nemotron-3-Nano-4B placeholder GGUF at Q4_K_M (architecture nemotron_h, registered by llama.cpp b7972); the 30B stays on disk as the replay control, it is NOT the serving placeholder
- repo verdict: `ai_llm_mount`: **FAIL** - ai-llm volume mount targets the 30B dir - adjust it too (spec 0.2): docker-compose.prod.yml: - ${AI_MODELS_PATH:-/export/ai_models}/nemotron/nemotron-3-nano-30b-a3b-q4km:/models:ro
- repo verdict: `model_env_passthrough`: **WARN** - MODEL_PATH hardcoded (LLM_MODEL_PATH cannot reach it) - editing .env alone will NOT switch the served model here: docker-compose.ghcr.yml: - MODEL_PATH=/models/Nemotron-3-Nano-30B-A3B-Q2_K_L.gguf
- repo verdict: `ctx_budget`: **INFO** - CTX_SIZE=262144 PARALLEL=8 GPU_LAYERS=auto - Nano-4B Q4_K_M ~2.64 GiB + 262K-token KV; spec budget ~5.5 GiB [C]
- [V 2026-09-25] .env.example:404 ships LLM_MODEL_PATH=/models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf; docker-compose.prod.yml ai-llm volume mounts .../nemotron/nemotron-3-nano-30b-a3b-q4km:/models:ro (spec's 'targets the 30B dir' confirmed) and MODEL_PATH=${LLM_MODEL_PATH:-...30B...} - both the .env value AND the mount dir change for the Nano-4B
- [V 2026-09-25] amend: docker-compose.ghcr.yml:165/:172 hardcode the models mount AND MODEL_PATH=.../Nemotron-3-Nano-30B-A3B-Q2_K_L.gguf - on the ghcr image path a .env switch does not reach the model; edit the compose (or run prod compose) on the A5500 box

## - [ ] Test-environment traps

- A `TMPDIR` in `.env` that differs from pytest's `tmp_path` false-reddens four `write_runtime_env` tests; CI sets no `TMPDIR`.
- Stale `__pycache__` directories for deleted modules false-redden deletion guards.
- repo verdict: `tmpdir_trap`: **WARN** - TMPDIR=/ephemeral/podman-tmp in the env file: \_runtime_env_path() gates against tempfile.gettempdir(), so an env TMPDIR unlike pytest's tmp_path false-reddens the four write_runtime_env tests (test_system.py x2, test_system_routes.py x2); CI sets no TMPDIR - unset it for test runs
- repo verdict: `pycache_stale`: **WARN** - 1 stale .pyc file(s) whose module source is gone - these false-redden deletion guards: backend/tests/integration/**pycache**/t_sparse_probe_tmp.cpython-314-pytest-9.1.1.pyc
- [V 2026-09-25] TMPDIR=/ephemeral/podman-tmp at .env.example:58; backend/api/routes/system.py:2508-2530 \_runtime_env_path() gates on tempfile.gettempdir() -> the four write_runtime_env tests (unit/api/routes/test_system.py:576,:598; unit/routes/test_system_routes.py:106,:2301) false-redden when env TMPDIR differs from pytest tmp_path. CI sets no TMPDIR
- [V 2026-09-25] pycache trap: scripts/a5500_precheck.py scan_stale_pycache() lists .pyc files whose source module is deleted (run it before trusting any deletion-guard run)

## - [ ] Health

Run `/platform-healthcheck`, and complete the root `AGENTS.md` infrastructure verification checklist.

- repo verdict: `health`: **MANUAL** - owner-run on the A5500: /platform-healthcheck + root AGENTS.md infrastructure verification checklist (compose config -q, services Up+healthy, Prometheus targets, API health). Sandbox precheck can never close this row
- [O] owner-run on the A5500: /platform-healthcheck + root AGENTS.md Infrastructure Verification checklist; ledger row carries the machine
