#!/usr/bin/env python3
"""P0.2 A5500 bring-up: repo-side PREP checker (owner rulings F9/F6).

Machine-checks every claim the design spec's "A5500 bring-up checklist (step
0.2)" makes about THIS tree, and renders the dated, [V]-amended checklist the
owner executes on the A5500 box. This script never touches a GPU, never runs
detection and never claims health - execution is owner-run on real media.

Checklist items covered (spec §A5500 bring-up, amended 2026-09-27 by 1.7 to
the SHIPPED vlm mode - PIPELINE_MODE=vlm is the default and that path calls
nothing but ai-vlm, so the legacy placeholder-LLM rows became serving-VLM
rows rather than accreting alongside them):
  1. GPU assignment      every GPU_* variable = 0 (SINGLE-GPU note)
     device passthrough  no hardwired nonzero device; CDI ``gpu=all`` = WARN
  2. CUDA architecture   CUDA_ARCHITECTURES=86, checked BEFORE the ai-vlm
                         build (the compose threads it into that build arg)
  3. Serving VLM         VLM_MODEL_PATH -> Qwen3-VL-8B Q4_K_M AND its mmproj
                         (a projector-less serve is text-only and degrades
                         silently); ai-vlm's /models mount -> the vlm dir, not
                         a legacy LLM dir; MODEL_PATH/MMPROJ_PATH stay
                         env-derived; the per-slot ctx covers a worst-case
                         vlm_assess
     No legacy LLM       is ai-llm profile-gated, or does it start next to
                         ai-vlm on the one GPU? (F10 keeps the service; the
                         checklist forbids deploying it)
     vlm image           can the scanned compose files build/serve ai-vlm at
                         all, or is that path image-only / absent?
  4. Test traps          TMPDIR in .env (false-reddens the four
                         write_runtime_env tests); stale __pycache__ dirs
                         for deleted modules (false-reddens deletion guards)
  5. Health              owner-run: /platform-healthcheck + root AGENTS.md
                         infrastructure checklist. ALWAYS manual.

Verdicts: PASS / WARN / FAIL / INFO / MANUAL. Exit code: 1 if any FAIL,
else 0 (MANUAL/WARN never fail the run - they are the human's row).

Usage:
  uv run python scripts/a5500_precheck.py                       # real tree
  uv run python scripts/a5500_precheck.py --env-file .env --check-only
  uv run python scripts/a5500_precheck.py --env-file f --compose a.yml \\
      --out /tmp/checklist.md                                    # dated handout
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
INFO = "INFO"
MANUAL = "MANUAL"

# Every GPU_* variable .env.example documents as REQUIRED (compose fails to
# start if any is missing), plus the gateway's GPU_AI_SERVICES.
REQUIRED_GPU_VARS = (
    "GPU_LLM",
    "GPU_FLORENCE",
    "GPU_YOLO26",
    "GPU_CLIP",
    "GPU_ENRICHMENT",
    "GPU_ENRICHMENT_LIGHT",
    "GPU_AI_SERVICES",
)

# The shipped serving pair (spec D5 as amended by rev 5 / 1.7, and rev 7 moved
# the identity): Qwen3-VL-8B-Instruct main GGUF at Q4_K_M + its mmproj
# projector - two files, one identity. The legacy Nano-4B placeholder plan is
# retired with the mode. The 4B pair remains the handout's MEASURED FALLBACK
# row (rev 7's flip condition 1), which the regexes below already admit: they
# match arch + quant, not size, deliberately - widening them is not how the
# pick moves.
QWEN3VL_RE = "qwen3vl"
VLM_MAIN_QUANT_RE = "q4_k_m"
# Spec §2 sizing: per-slot context = VLM_CTX_SIZE / VLM_PARALLEL must cover
# the worst-case vlm_assess (4 images x <=1280 tokens + ~6K prompt + ~1K
# verdict ~= 12.2K). 32768/2 = 16384 clears it; a smaller slot truncates the
# verdict input with no log line.
WORST_CASE_SLOT_TOKENS = 12_200
# VLM_GPU_LAYERS=999 (full offload) is the big-model config; the A5500 shape
# is auto (llama.cpp --fit picks layers by free VRAM).
FULL_OFFLOAD_LAYERS = "999"

# Shortest host path wins so a ``${VAR:-/export/ai_models}`` default - whose
# own ``:-`` contains a colon - does not split the mount at the wrong place.
MOUNT_RE = re.compile(r"^(?P<host>.*?):(?P<target>/[^:]*)(?::(?P<mode>ro|rw))?$")


@dataclass(frozen=True)
class Check:
    check_id: str
    verdict: str  # PASS | WARN | FAIL | INFO | MANUAL
    detail: str


def parse_env(text: str) -> dict[str, str]:
    """Parse a .env-style file: last assignment wins, comments/blanks skipped."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].strip()
        k, v = stripped.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def scan_stale_pycache(repo_root: Path) -> list[str]:
    """Return __pycache__ .pyc entries whose source module no longer exists.

    The spec's trap: a stale .pyc for a DELETED module false-reddens deletion
    guards. A .pyc named ``<mod>.cpython-XY.pyc`` is stale when no
    ``<mod>.py`` sits beside the __pycache__ directory.
    """
    stale: list[str] = []
    caches: list[Path] = []
    for dirpath, dirnames, _files in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".venv", ".git")]
        if Path(dirpath).name == "__pycache__":
            caches.append(Path(dirpath))
            dirnames[:] = []  # do not descend into a cache dir
    for cache in sorted(caches):
        for pyc in sorted(cache.glob("*.pyc")):
            module = pyc.name.split(".")[0]
            if not (cache.parent / f"{module}.py").exists():
                stale.append(str(pyc.relative_to(repo_root)))
    return stale


def _check_gpu_assignment(env: dict[str, str]) -> Check:
    nonzero = [v for v in REQUIRED_GPU_VARS if env.get(v, "0") not in ("", "0")]
    missing = [v for v in REQUIRED_GPU_VARS if v not in env]
    if nonzero:
        return Check(
            "gpu_assignment",
            FAIL,
            "SINGLE-GPU requires all GPU_*=0; non-zero: " + ", ".join(
                f"{v}={env[v]}" for v in nonzero
            )
            + (f"; missing (compose-required): {', '.join(missing)}" if missing else ""),
        )
    if missing:
        return Check(
            "gpu_assignment",
            FAIL,
            "compose-required GPU vars missing (compose fails to start): "
            + ", ".join(missing),
        )
    return Check("gpu_assignment", PASS, "all GPU_* variables are 0")


def _check_devices(compose_paths: list[Path]) -> Check:
    """Device passthrough: hardwired nonzero GPU = FAIL; 'gpu=all' = WARN.

    'nvidia.com/gpu=all' is rootless-podman CDI (all devices visible, CUDA
    pins via CUDA_VISIBLE_DEVICES=${GPU_*}); with every GPU_*=0 that is the
    single-GPU behavior, but the owner should confirm the A400 is physically
    out of the passthrough set. A hardwired literal device id is the A400-era
    mistake the checklist retires.
    """
    hardwired: list[str] = []
    alls: list[str] = []
    for path in compose_paths:
        text = _read(path)
        for line in text.splitlines():
            s = line.strip()
            if not s.startswith("- nvidia.com/gpu="):
                continue
            ref = s.split("=", 1)[1]
            if ref == "all":
                alls.append(path.name)
            elif "$" not in ref and ref != "0":
                hardwired.append(f"{path.name}: {s}")
    if hardwired:
        return Check(
            "device_passthrough", FAIL, "hardwired non-zero GPU device(s): " + "; ".join(hardwired)
        )
    if alls:
        return Check(
            "device_passthrough",
            WARN,
            "nvidia.com/gpu=all (CDI passthrough of ALL devices) in "
            + ", ".join(sorted(set(alls)))
            + " - confirm the retired A400 is out of the CDI/handler set; "
            "CUDA placement then rides CUDA_VISIBLE_DEVICES=${GPU_*}",
        )
    return Check("device_passthrough", PASS, "device refs are env-parameterized or 0")


def _check_cuda_arch(env: dict[str, str]) -> Check:
    val = env.get("CUDA_ARCHITECTURES", "")
    if val == "86":
        return Check("cuda_arch", PASS, "CUDA_ARCHITECTURES=86 (A5500 sm_86)")
    if val == "":
        return Check(
            "cuda_arch",
            WARN,
            "CUDA_ARCHITECTURES empty = build for ALL common architectures "
            "(setup.py semantics) - correct but ~6x slower build; set 86",
        )
    return Check(
        "cuda_arch",
        FAIL,
        f"CUDA_ARCHITECTURES={val!r}, expected 86 (A5500 = Ampere sm_86). "
        ".env.example ships 89; setup.py's auto-detect only rewrites it when "
        "setup.py runs against the GPU - CHECK BEFORE BUILDING ai-vlm (the "
        "shipped mode's build consumes this value; prod compose :240)",
    )


def _per_file_service_lines(
    compose_paths: list[Path], service: str
) -> dict[str, list[str]]:
    """{compose file: raw lines of ``service``'s block}; absent = not defined."""
    out: dict[str, list[str]] = {}
    for path in compose_paths:
        lines = _read(path).splitlines()
        block: list[str] = []
        in_block = False
        for line in lines:
            # a service key is exactly two spaces + name + colon
            if line.startswith("  ") and not line.startswith("   ") and line.rstrip().endswith(":"):
                name = line.strip().rstrip(":")
                in_block = name == service and line.startswith("  ")
                if in_block:
                    block = []
                    out[path.name] = block
                continue
            if in_block:
                if line and not line.startswith("    "):
                    in_block = False  # dedent back to a sibling/top-level key
                else:
                    block.append(line)
    return out


def _profile_names(block_lines: list[str]) -> list[str]:
    names: list[str] = []
    in_profiles = False
    profiles_indent = 0
    for line in block_lines:
        stripped = line.strip()
        if stripped == "profiles:":
            in_profiles = True
            profiles_indent = len(line) - len(line.lstrip())
            continue
        if in_profiles:
            indent = len(line) - len(line.lstrip())
            if stripped.startswith("- ") and indent > profiles_indent:
                names.append(stripped[2:].strip())
            elif stripped:
                in_profiles = False
    return names


def _check_vlm_model(env: dict[str, str]) -> Check:
    """The shipped serving pair: Qwen3-VL-8B-Instruct main GGUF + mmproj.

    A projector-less llama.cpp serve loads TEXT-ONLY and every vlm_assess
    silently degrades - so the pair is checked as a pair, and a legacy
    LLM_MODEL_PATH is not an answer (the vlm path calls nothing else, per
    .env.example's GATEWAY_MODEL_SET comment).
    """
    main = env.get("VLM_MODEL_PATH", "")
    mmproj = env.get("VLM_MMPROJ_PATH", "")
    want = (
        "the shipped mode serves the Qwen3VL-8B (Qwen3-VL-8B-Instruct) pair: "
        "VLM_MODEL_PATH at Q4_K_M + VLM_MMPROJ_PATH at its mmproj "
        "(the .env.example VLM_MODEL_PATH/VLM_MMPROJ_PATH defaults; cited by "
        "name, not line - a line anchor here went stale within one slice; "
        "legacy LLM_MODEL_PATH is not it)"
    )
    if not main:
        return Check("vlm_model", FAIL, f"VLM_MODEL_PATH unset - {want}")
    lowered = main.lower()
    if QWEN3VL_RE not in lowered or VLM_MAIN_QUANT_RE not in lowered or not lowered.endswith(".gguf"):
        return Check("vlm_model", FAIL, f"VLM_MODEL_PATH={main!r} - expected: {want}")
    if not mmproj:
        return Check(
            "vlm_model",
            FAIL,
            f"VLM_MMPROJ_PATH unset while VLM_MODEL_PATH={main!r}: a "
            "projector-less serve loads text-only and silently degrades "
            "every vlm_assess - the vision pair ships as two files - " + want,
        )
    if QWEN3VL_RE not in mmproj.lower() or not mmproj.lower().endswith(".gguf"):
        return Check(
            "vlm_model",
            FAIL,
            f"VLM_MMPROJ_PATH={mmproj!r} does not name a Qwen3VL GGUF beside "
            f"VLM_MODEL_PATH={main!r} - the projector must match the main "
            "file's identity (they are exported together)",
        )
    return Check("vlm_model", PASS, f"VLM pair: {main} + {mmproj}")


def _check_ai_vlm_mount(compose_paths: list[Path]) -> Check:
    """ai-vlm's weights mount: source dir must be the vlm dir, target /models.

    Only a mount whose TARGET is exactly /models is the weights mount - the
    gateway/backend mount ai_models at /models/zoo, /models/model-zoo,
    /models/cache, which are other services' business.
    """
    fail_hits: list[str] = []
    pass_hits: list[str] = []
    other: list[str] = []
    absent: list[str] = []
    merged = _per_file_service_lines(compose_paths, "ai-vlm")
    for path in compose_paths:
        fname = path.name
        lines = merged.get(fname)
        if lines is None:
            absent.append(fname)
            continue
        for line in lines:
            s = line.strip()
            if not (s.startswith("- ") and ":/models" in s):
                continue
            m = MOUNT_RE.match(s[2:])
            if m is None or m.group("target") != "/models":
                continue  # target is /models/something: a zoo/cache mount
            host = m.group("host")
            if "/vlm" in host.lower():
                pass_hits.append(f"{fname}: {s}")
            elif any(tok in host.lower() for tok in ("30b", "nano-4b", "nemotron")):
                fail_hits.append(f"{fname}: {s}")
            else:
                other.append(f"{fname}: {s}")
    if fail_hits:
        return Check(
            "ai_vlm_mount",
            FAIL,
            "ai-vlm weights mount targets a legacy LLM dir - the vlm path "
            "needs the vlm dir (spec 1.7): " + "; ".join(fail_hits),
        )
    if pass_hits:
        return Check("ai_vlm_mount", PASS, "ai-vlm weights mount: " + "; ".join(pass_hits))
    if other:
        return Check(
            "ai_vlm_mount",
            WARN,
            "ai-vlm mounts /models from a dir that names nothing recognizable"
            " - confirm it holds the Qwen3VL pair: " + "; ".join(other),
        )
    if absent:
        return Check(
            "ai_vlm_mount",
            WARN,
            "no ai-vlm service defined in "
            + ", ".join(sorted(set(absent)))
            + " - that compose cannot serve the shipped vlm mode (prod "
            "compose is the vlm path; the ghcr image path never gained one)",
        )
    return Check("ai_vlm_mount", WARN, "ai-vlm has no weights mount at /models - inspect by eye")


def _check_vlm_env_passthrough(compose_paths: list[Path]) -> Check:
    """MODEL_PATH/MMPROJ_PATH inside ai-vlm must derive from the VLM_* vars.

    Only ai-vlm's own env lines count (block scope): ai-llm derives its
    MODEL_PATH from LLM_MODEL_PATH and that is the retired path's business.
    """
    hardcoded: list[str] = []
    for fname, lines in _merge_service_lines(compose_paths, "ai-vlm").items():
        for line in lines:
            s = line.strip()
            if s.startswith("- MODEL_PATH=") or s.startswith("MODEL_PATH="):
                if "${VLM_MODEL_PATH" not in s:
                    hardcoded.append(f"{fname}: {s}")
            elif s.startswith("- MMPROJ_PATH=") or s.startswith("MMPROJ_PATH="):
                if "${VLM_MMPROJ_PATH" not in s:
                    hardcoded.append(f"{fname}: {s}")
    if hardcoded:
        return Check(
            "vlm_model_env_passthrough",
            WARN,
            "MODEL_PATH/MMPROJ_PATH hardcoded - no .env switch reaches them "
            "(editing .env alone will NOT change the served model here): "
            + "; ".join(hardcoded),
        )
    return Check(
        "vlm_model_env_passthrough",
        PASS,
        "MODEL_PATH/MMPROJ_PATH derive from VLM_MODEL_PATH/VLM_MMPROJ_PATH "
        "in every ai-vlm definition",
    )


def _merge_service_lines(compose_paths: list[Path], service: str) -> dict[str, list[str]]:
    merged = _per_file_service_lines(compose_paths, service)
    return {k: v for k, v in merged.items() if v is not None}


def _check_vlm_ctx_budget(env: dict[str, str]) -> Check:
    """Per-slot context must cover the worst-case vlm_assess (spec §2).

    The backend divides CTX_SIZE by PARALLEL itself, so the number that
    matters is the slot, not the pool: 4 images x <=1280 tokens + ~6K
    prompt + ~1K verdict ~= 12.2K. A smaller slot truncates the verdict
    input silently - the failure has no log line.
    """
    layers = env.get("VLM_GPU_LAYERS", "auto")
    ctx_raw = env.get("VLM_CTX_SIZE", "32768")
    par_raw = env.get("VLM_PARALLEL", "2")
    try:
        slot = int(ctx_raw) // max(int(par_raw), 1)
    except ValueError:
        return Check(
            "vlm_ctx_budget", WARN, f"VLM_CTX_SIZE={ctx_raw!r}/VLM_PARALLEL={par_raw!r} not integers"
        )
    if layers == FULL_OFFLOAD_LAYERS:
        return Check(
            "vlm_ctx_budget",
            WARN,
            f"VLM_GPU_LAYERS=999 (all layers on GPU) at VLM_CTX_SIZE={ctx_raw} - "
            "auto lets llama.cpp --fit decide by free VRAM; the A5500 shape is auto",
        )
    if slot < WORST_CASE_SLOT_TOKENS:
        return Check(
            "vlm_ctx_budget",
            WARN,
            f"per-slot context {slot} tokens (VLM_CTX_SIZE={ctx_raw}/"
            f"PARALLEL={par_raw}) < the ~{WORST_CASE_SLOT_TOKENS} a worst-case "
            "vlm_assess needs (4 images x <=1280 + ~6K prompt + ~1K verdict) "
            "- the verdict input truncates with no log line",
        )
    return Check(
        "vlm_ctx_budget",
        INFO,
        f"per-slot {slot} tokens (CTX={ctx_raw}/PARALLEL={par_raw}) covers the "
        f"~{WORST_CASE_SLOT_TOKENS} worst case; VLM_GPU_LAYERS={layers}",
    )


def _check_legacy_llm(compose_paths: list[Path]) -> Check:
    """"no legacy LLM deployed" (spec :482-500, rev 5 / F10), machine-checked.

    F10 says build empty states, not deletions - ai-llm STAYS in the compose
    (its tests keep passing), so the honest check is whether a `--profile vlm`
    up would START it. Unprofiled = it starts on every up, alongside ai-vlm,
    asking for VRAM a single A5500 cannot give twice.
    """
    unprofiled: list[str] = []
    gated: list[str] = []
    for fname, lines in _merge_service_lines(compose_paths, "ai-llm").items():
        names = _profile_names(lines)
        if names:
            gated.append(f"{fname}: profiles={names}")
        else:
            unprofiled.append(fname)
    if unprofiled:
        return Check(
            "legacy_llm",
            WARN,
            "ai-llm has NO profiles: block in "
            + ", ".join(sorted(set(unprofiled)))
            + " - a --profile vlm up starts the retired serving path ALONGSIDE "
            "ai-vlm (one A5500 GPU cannot serve both); profile-gate it or "
            "keep it out of the up set (F10 keeps the service, not its "
            "deployment)",
        )
    if gated:
        return Check(
            "legacy_llm",
            WARN,
            "ai-llm is profile-gated (" + "; ".join(gated) + ") - it only "
            "runs if that profile is explicitly named; leave it off",
        )
    return Check("legacy_llm", PASS, "no ai-llm service in the scanned compose files")


def _check_vlm_image(compose_paths: list[Path]) -> Check:
    """Can the scanned compose files actually BUILD/SERVE the vlm service?

    The A5500 build line (--build-arg CUDA_ARCHITECTURES=86) only means
    something through a build: block; an image: ref says nothing about the
    arch it carries, and a compose with no ai-vlm at all (ghcr.yml's shipped
    shape) cannot serve the mode at all.
    """
    buildable: list[str] = []
    image_only: list[str] = []
    absent: list[str] = []
    for path in compose_paths:
        fname = path.name
        lines = _per_file_service_lines([path], "ai-vlm").get(fname)
        if lines is None:
            absent.append(fname)
            continue
        stripped = [l.strip() for l in lines]
        if any(s == "build:" for s in stripped):
            buildable.append(fname)
        elif any(s.startswith("image:") for s in stripped):
            image_only.append(fname)
        else:
            image_only.append(fname)  # neither build nor image: treat as not buildable here
    if absent:
        return Check(
            "vlm_image",
            WARN,
            "no ai-vlm service in "
            + ", ".join(sorted(set(absent)))
            + " - the ghcr image path cannot serve the shipped vlm mode; run "
            "docker-compose.prod.yml with --profile vlm on the A5500 box",
        )
    if image_only:
        return Check(
            "vlm_image",
            WARN,
            "ai-vlm ships as an image ref in "
            + ", ".join(sorted(set(image_only)))
            + " - CUDA_ARCHITECTURES=86 must match how THAT image was built; "
            "the check-before-build only bites on a build: block",
        )
    return Check(
        "vlm_image",
        PASS,
        "ai-vlm builds from source in "
        + ", ".join(sorted(set(buildable)))
        + " - build with --build-arg CUDA_ARCHITECTURES=86 (A5500 sm_86)",
    )


def _check_tmpdir(env: dict[str, str]) -> Check:
    if "TMPDIR" in env:
        return Check(
            "tmpdir_trap",
            WARN,
            f"TMPDIR={env['TMPDIR']} in the env file: _runtime_env_path() gates "
            "against tempfile.gettempdir(), so an env TMPDIR unlike pytest's "
            "tmp_path false-reddens the four write_runtime_env tests "
            "(test_system.py x2, test_system_routes.py x2); CI sets no TMPDIR - "
            "unset it for test runs",
        )
    return Check("tmpdir_trap", PASS, "no TMPDIR in the env file (matches CI)")


def _check_pycache(repo_root: Path) -> Check:
    stale = scan_stale_pycache(repo_root)
    if stale:
        shown = ", ".join(stale[:10]) + (f" (+{len(stale) - 10} more)" if len(stale) > 10 else "")
        return Check(
            "pycache_stale",
            WARN,
            f"{len(stale)} stale .pyc file(s) whose module source is gone - "
            "these false-redden deletion guards: " + shown,
        )
    return Check("pycache_stale", PASS, "no stale __pycache__ entries for deleted modules")


def _check_health() -> Check:
    return Check(
        "health",
        MANUAL,
        "owner-run on the A5500: /platform-healthcheck + root AGENTS.md "
        "infrastructure verification checklist (compose config -q, services "
        "Up+healthy, Prometheus targets, API health). Sandbox precheck can "
        "never close this row",
    )


def run_precheck(env_path: Path, compose_paths: list[Path], repo_root: Path) -> list[Check]:
    """Every checklist verdict for one (env file, compose files, tree) triple."""
    env = parse_env(_read(env_path)) if env_path.exists() else {}
    checks = [
        _check_gpu_assignment(env),
        _check_devices(compose_paths),
        _check_cuda_arch(env),
        _check_vlm_model(env),
        _check_ai_vlm_mount(compose_paths),
        _check_vlm_env_passthrough(compose_paths),
        _check_vlm_ctx_budget(env),
        _check_legacy_llm(compose_paths),
        _check_vlm_image(compose_paths),
        _check_tmpdir(env),
        _check_pycache(repo_root),
        _check_health(),
    ]
    return checks


# The [V]-amended checklist: spec items copied, repo claims carrying today's
# verdict + the line anchor the claim was re-verified against (plan Task 6
# box 1: "the spec's anchors drift; re-verify each line-number claim first").
AMENDMENTS: dict[str, list[str]] = {
    "GPU assignment": [
        "[V 2026-09-27] .env.example:567 documents 'SINGLE-GPU: Set all to 0'; "
        "shipped defaults are dual-GPU: GPU_YOLO26/CLIP/ENRICHMENT/"
        "ENRICHMENT_LIGHT=1 (:580-583) and GPU_AI_SERVICES=1 (:962) - set all "
        "to 0 on the A5500 box (GPU_LLM/GPU_FLORENCE already ship 0, :578-579)",
    ],
    "Device passthrough": [
        "[V 2026-09-25, anchors re-checked 2026-09-27] amend: compose carries "
        "NO per-device A400 entry to remove. docker-compose.prod.yml ai-vlm "
        "uses nvidia.com/gpu=${GPU_LLM:-0} (:244); :415 and :1392 pass "
        "nvidia.com/gpu=all (rootless-podman CDI design comment at :442). "
        "A400 removal is therefore CDI-handler / physical, not a compose "
        "edit - confirm the retired card is out of the CDI set",
    ],
    "CUDA architecture": [
        "[V 2026-09-27] .env.example:576 ships CUDA_ARCHITECTURES=89; "
        "docker-compose.prod.yml:240 threads ${CUDA_ARCHITECTURES:-} into the "
        "ai-vlm build (the :136 ai-llm line serves the retired mode); "
        "ai/vlm/Dockerfile:64 treats it as a build-arg - check-before-build "
        "stands",
    ],
    "Serving VLM": [
        "[V 2026-09-27] the shipped mode is the VLM path: PIPELINE_MODE=vlm "
        "and GATEWAY_MODEL_SET=vlm are the .env.example defaults (:211,:221) "
        "and the residency comment records that the mode 'calls nothing "
        "else' (:218); ai-vlm is profile-gated profiles:[vlm] on the ai-vlm "
        "service (the anchor here read :221,:227-228 and was already stale - "
        "cite the service name, not the line) - bring-up runs the VLM, not "
        "the Nano-4B placeholder plan",
        "[V 2026-09-28] amend (owner ruling, spec rev 7, ledger item 35): the "
        "shipped pair is now Qwen3VL-8B-Instruct-Q4_K_M + VLM_MMPROJ_PATH at "
        "its Q8_0 mmproj (the .env.example VLM_MODEL_PATH/VLM_MMPROJ_PATH "
        "defaults; cited by name, not line); prod compose mounts "
        "${AI_MODELS_PATH:-/export/ai_models}/vlm:/models:ro (:253) and "
        "derives MODEL_PATH/MMPROJ_PATH from the VLM_* vars (:265-266) - the "
        "weights are NOT what the A5500 lacks, and both 8B files are on the "
        "share readable (mode 644) with sha256s pinned in ledger item 35",
        "[V 2026-09-28] ORDER OF THIS RUN (rev 7's 8B-primary ruling): serve "
        "the 8B pair first and take its S1 peak, then re-run the SAME command "
        "with VLM_MODEL_PATH/VLM_MMPROJ_PATH pointed at the 4B pair and take "
        "its S1 peak. Two readings, not one, because the 4B is the pick's "
        "named FALLBACK (flip condition 1: 8B fails S1 on 24 GB => fall to "
        "4B) and an abort must land on a model that already has a number on "
        "this box. The measured footprints to expect, quoted from the bake-off "
        "report and nothing else: 8B `vram_actual_mib 11216` (9376 projected), "
        "4B `7285 MiB projected (fit log)` - and the 4B has NO broker-actual "
        "in that report, which is precisely why both readings are taken here "
        "rather than trusting a projection. KV is 4608 MiB for BOTH at CTX "
        "32768 / PARALLEL 2 (identical 36-layer geometry - the 8B buys no KV "
        "relief), so that cost does not move with the fallback.",
        "[V 2026-09-28] record two timings this run that the repo has NEVER "
        "measured and this handout no longer guesses at: (a) the 8B pair's "
        "cold LOAD time against the healthcheck start_period of 120s "
        "(docker-compose.prod.yml, which mirrors ai/vlm/Dockerfile:133 - if "
        "the pair needs more, both numbers move together or the server is "
        "torn down for being slow when it is only early); (b) a WAKE time "
        "from sleep against the client's AI_VLM_WAKE_TIMEOUT_SECONDS=90.0 - "
        "the 8B pair is 2.0x the 4B's bytes to copy back from CPU RAM "
        "(5,027,784,800+752,289,728 vs 2,497,281,664+453,974,304), and M1's "
        "assertions 2/3 are exactly the wake-through-sleep check.",
        "[V 2026-09-28] the two KV figures in this repo DISAGREE and the "
        "disagreement is unresolved: compose's older prose implied ~73KB per "
        "token per slot (~2.4 GB for 2x16K slots) while the bake-off report "
        "recorded 4608 MiB (~144KB/token) for the same 32768/2 pool - about "
        "2x. Neither is a measurement of THIS container. Copy llama-server's "
        "own startup KV line into the run notes; it is the authority and it "
        "costs nothing to capture.",
        "[V 2026-09-27] amend (ghcr-hardcode fact, kept from the P0.2 review "
        "and still true in kind): docker-compose.ghcr.yml has NO ai-vlm "
        "service at all - the ghcr image path cannot serve the shipped mode. "
        "Run docker-compose.prod.yml with --profile vlm on the A5500 box "
        "(that compose file also hardcodes its legacy ai-llm's "
        "MODEL_PATH=...Q2_K_L.gguf at :172, unchanged)",
    ],
    "No legacy LLM": [
        "[V 2026-09-27] prod compose's ai-llm has NO profiles: block (:120 - "
        "the P0.2-era anchor :139 is its devices line), so `podman compose "
        "--profile vlm up` starts the retired 30B serving path ALONGSIDE "
        "ai-vlm; one A5500 cannot serve both. F10 keeps the service (its "
        "tests keep passing, nothing gets deleted) - keep it out of the up "
        "set: run only the vlm profile and do not start ai-llm",
    ],
    "Test-environment traps": [
        "[V 2026-09-25, anchors re-checked 2026-09-27] TMPDIR="
        "/ephemeral/podman-tmp at .env.example:57; backend/api/routes/"
        "system.py:2508 _runtime_env_path() gates on tempfile.gettempdir() "
        "-> the four write_runtime_env tests (unit/api/routes/"
        "test_system.py:576,:598; unit/routes/test_system_routes.py:106 and "
        "its sibling) false-redden when env TMPDIR differs from pytest "
        "tmp_path. CI sets no TMPDIR",
        "[V 2026-09-25] pycache trap: scripts/a5500_precheck.py "
        "scan_stale_pycache() lists .pyc files whose source module is deleted "
        "(run it before trusting any deletion-guard run)",
    ],
    "Health": [
        "[O] owner-run on the A5500: /platform-healthcheck + root AGENTS.md "
        "Infrastructure Verification checklist; ledger row carries the machine",
    ],
}

CHECKLIST_HEADLINE = (
    "A5500 bring-up checklist (vlm mode, plan 1.7) - dated copy with [V] "
    "repo-side amendments from the prep review"
)


def render_checklist(checks: list[Check], date_str: str) -> str:
    """The handout: spec §0.2 items copied + [V] amendments + machine verdicts."""
    by_id = {c.check_id: c for c in checks}

    def v(cid: str) -> str:
        c = by_id[cid]
        return f"`{cid}`: **{c.verdict}** - {c.detail}"

    lines = [
        f"# {CHECKLIST_HEADLINE}",
        "",
        f"Dated {date_str}. Source: spec §'A5500 bring-up checklist (step "
        f"0.2)' (docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-"
        f"design.md) as amended by plan 1.7 to the shipped vlm mode (spec "
        f"rev 5 / F10: the legacy LLM path is unsupported - the checklist's "
        f"placeholder-LLM rows became serving-VLM rows). Repo-side prep via "
        f"`scripts/a5500_precheck.py` (F9/F6: execution is owner-run on real "
        f"media; this document claims no execution).",
        "",
        "Ordering guard: lifted 2026-09-25 by ledger F9 (no pre-switch traffic "
        "exists); re-arms the day the home stack serves live events.",
        "",
        "## - [ ] GPU assignment",
        "Set every `GPU_*` variable to `0` (.env.example documents "
        "\"SINGLE-GPU: Set all to 0\"). Remove the A400 from device passthrough.",
        f"- repo verdict: {v('gpu_assignment')}",
        f"- repo verdict: {v('device_passthrough')}",
    ]
    for a in AMENDMENTS["GPU assignment"]:
        lines.append(f"- {a}")
    for a in AMENDMENTS["Device passthrough"]:
        lines.append(f"- {a}")
    lines += [
        "",
        "## - [ ] CUDA architecture",
        "`CUDA_ARCHITECTURES=86`. Check it BEFORE building `ai-vlm` (the "
        "shipped mode's build; the retired mode's `ai-llm` build takes the "
        "same value).",
        f"- repo verdict: {v('cuda_arch')}",
    ]
    lines += [f"- {a}" for a in AMENDMENTS["CUDA architecture"]]
    lines += [
        "",
        "## - [ ] Serving VLM",
        "The A5500 brings up the SHIPPED vlm mode (1.7, spec rev 5; the model "
        "identity is rev 7's owner pick, ledger item 35): "
        "`VLM_MODEL_PATH` at the `Qwen3-VL-8B-Instruct` Q4_K_M GGUF AND "
        "`VLM_MMPROJ_PATH` at its mmproj projector (two files - a "
        "projector-less serve loads text-only and silently degrades every "
        "vlm_assess). `ai-vlm`'s `/models` mount must target the `vlm` "
        "weights dir, and `MODEL_PATH`/`MMPROJ_PATH` must stay derived from "
        "the `VLM_*` vars so a `.env` switch reaches the container. Per-slot "
        "context = `VLM_CTX_SIZE`/`VLM_PARALLEL` must cover a worst-case "
        "vlm_assess (~12.2K tokens; the shipped 32768/2 = 16384 does). "
        "MANDATORY ordering: smoke-serve Qwen3-VL-8B and run the P0.3 "
        "enforcement probe (a refusal check against the serving path) "
        "BEFORE any event reaches it - never attach live traffic to an "
        "unprobed server. Then take the same reading on the 4B pair: it is "
        "the pick's named fallback, so a fit failure must not cost a re-run.",
        f"- repo verdict: {v('vlm_model')}",
        f"- repo verdict: {v('ai_vlm_mount')}",
        f"- repo verdict: {v('vlm_model_env_passthrough')}",
        f"- repo verdict: {v('vlm_ctx_budget')}",
        f"- repo verdict: {v('vlm_image')}",
    ]
    lines += [f"- {a}" for a in AMENDMENTS["Serving VLM"]]
    lines += [
        "",
        "## - [ ] No legacy LLM",
        "No legacy LLM serving path is deployed on the A5500 (spec :482-500 "
        "/ F10): the `ai-llm` service stays in the tree - its tests keep "
        "passing, nothing is deleted - but it must NOT start alongside "
        "`ai-vlm`. Keep it out of the up set.",
        f"- repo verdict: {v('legacy_llm')}",
    ]
    lines += [f"- {a}" for a in AMENDMENTS["No legacy LLM"]]
    lines += [
        "",
        "## - [ ] Test-environment traps",
        "  - A `TMPDIR` in `.env` that differs from pytest's `tmp_path` "
        "false-reddens four `write_runtime_env` tests; CI sets no `TMPDIR`.",
        "  - Stale `__pycache__` directories for deleted modules false-redden "
        "deletion guards.",
        f"- repo verdict: {v('tmpdir_trap')}",
        f"- repo verdict: {v('pycache_stale')}",
    ]
    lines += [f"- {a}" for a in AMENDMENTS["Test-environment traps"]]
    lines += [
        "",
        "## - [ ] Health",
        "Run `/platform-healthcheck`, and complete the root `AGENTS.md` "
        "infrastructure verification checklist.",
        f"- repo verdict: {v('health')}",
    ]
    lines += [f"- {a}" for a in AMENDMENTS["Health"]]
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--env-file", default=str(REPO_ROOT / ".env.example"), help="env file to check"
    )
    ap.add_argument(
        "--compose",
        action="append",
        default=None,
        help="compose file to check (repeatable; default: prod + ghcr)",
    )
    ap.add_argument("--repo-root", default=str(REPO_ROOT))
    ap.add_argument("--out", default=None, help="write the dated checklist here")
    ap.add_argument(
        "--date", default=None, help="override the checklist date (YYYY-MM-DD)"
    )
    ap.add_argument(
        "--check-only", action="store_true", help="verdicts only, no checklist render"
    )
    args = ap.parse_args(argv)

    compose = (
        [Path(p) for p in args.compose]
        if args.compose
        else [
            REPO_ROOT / "docker-compose.prod.yml",
            REPO_ROOT / "docker-compose.ghcr.yml",
        ]
    )
    checks = run_precheck(Path(args.env_file), compose, Path(args.repo_root))
    for c in checks:
        print(f"{c.verdict:6} {c.check_id:22} {c.detail}")
    fails = [c for c in checks if c.verdict == FAIL]

    if not args.check_only:
        date_str = args.date or date.today().isoformat()
        md = render_checklist(checks, date_str=date_str)
        if args.out:
            Path(args.out).write_text(md, encoding="utf-8")
            print(f"\nchecklist written: {args.out}")
        else:
            print("\n" + md)

    if fails:
        print(f"\n{len(fails)} FAIL(s) - not ready for A5500 bring-up as configured")
        return 1
    print("\nno FAILs - WARN/MANUAL rows are the owner's")
    return 0


if __name__ == "__main__":
    sys.exit(main())
