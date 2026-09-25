#!/usr/bin/env python3
"""P0.2 A5500 bring-up: repo-side PREP checker (owner rulings F9/F6).

Machine-checks every claim the design spec's "A5500 bring-up checklist (step
0.2)" makes about THIS tree, and renders the dated, [V]-amended checklist the
owner executes on the A5500 box. This script never touches a GPU, never runs
detection and never claims health - execution is owner-run on real media.

Checklist items covered (spec §A5500 bring-up):
  1. GPU assignment      every GPU_* variable = 0 (SINGLE-GPU note)
     device passthrough  no hardwired nonzero device; CDI ``gpu=all`` = WARN
  2. CUDA architecture   CUDA_ARCHITECTURES=86, checked BEFORE ai-llm build
  3. Placeholder LLM     LLM_MODEL_PATH -> Nemotron-3-Nano-4B Q4_K_M, and the
                         ai-llm volume mount must target the Nano-4B dir, not
                         the 30B dir (MODEL_PATH passthrough audited too)
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

# Placeholder LLM per spec D5/0.2: NVIDIA-Nemotron-3-Nano-4B, official GGUF,
# Q4_K_M, ~2.64 GiB, arch nemotron_h on llama.cpp b7972.
NANO4B_RE = "nano-4b"
Q4KM_RE = "q4_k_m"
CTX_BUDGET_NOTE = (
    "Nano-4B Q4_K_M ~2.64 GiB + 262K-token KV; spec budget ~5.5 GiB [C]"
)
# GPU_LAYERS=999 (full offload) at 262K ctx is the >26 GB config (.env.example
# ~:360 comment), which busts the single-GPU Nano-4B budget.
FULL_OFFLOAD_LAYERS = "999"


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
        "setup.py runs against the GPU - CHECK BEFORE BUILDING ai-llm",
    )


def _check_llm_model(env: dict[str, str]) -> Check:
    path = env.get("LLM_MODEL_PATH", "")
    lowered = path.lower()
    if NANO4B_RE in lowered and Q4KM_RE in lowered and lowered.endswith(".gguf"):
        return Check("llm_model", PASS, f"LLM_MODEL_PATH={path}")
    return Check(
        "llm_model",
        FAIL,
        f"LLM_MODEL_PATH={path!r}: spec 0.2 wants the Nemotron-3-Nano-4B "
        "placeholder GGUF at Q4_K_M (architecture nemotron_h, registered by "
        "llama.cpp b7972); the 30B stays on disk as the replay control, it is "
        "NOT the serving placeholder",
    )


def _check_mount(compose_paths: list[Path]) -> Check:
    hits_30b: list[str] = []
    hits_nano4b: list[str] = []
    for path in compose_paths:
        for line in _read(path).splitlines():
            s = line.strip()
            if not (s.startswith("- ") and "ai_models" in s and ":/models" in s):
                continue
            lowered = s.lower()
            if "30b" in lowered:
                hits_30b.append(f"{path.name}: {s}")
            elif NANO4B_RE in lowered:
                hits_nano4b.append(f"{path.name}: {s}")
    if hits_30b:
        return Check(
            "ai_llm_mount",
            FAIL,
            "ai-llm volume mount targets the 30B dir - adjust it too "
            "(spec 0.2): " + "; ".join(hits_30b),
        )
    if hits_nano4b:
        return Check("ai_llm_mount", PASS, "mount targets a Nano-4B dir: " + "; ".join(hits_nano4b))
    return Check(
        "ai_llm_mount",
        WARN,
        "no ai_models:/models mount matched 30b/nano-4b naming - inspect the "
        "ai-llm volumes block by eye",
    )


def _check_passthrough(compose_paths: list[Path]) -> Check:
    hardcoded: list[str] = []
    for path in compose_paths:
        for line in _read(path).splitlines():
            s = line.strip()
            if s.startswith("- MODEL_PATH=") or s.startswith("MODEL_PATH="):
                if "${LLM_MODEL_PATH" not in s:
                    hardcoded.append(f"{path.name}: {s}")
    if hardcoded:
        return Check(
            "model_env_passthrough",
            WARN,
            "MODEL_PATH hardcoded (LLM_MODEL_PATH cannot reach it) - editing "
            ".env alone will NOT switch the served model here: "
            + "; ".join(hardcoded),
        )
    return Check(
        "model_env_passthrough", PASS, "MODEL_PATH derives from LLM_MODEL_PATH in every compose"
    )


def _check_budget(env: dict[str, str]) -> Check:
    layers = env.get("GPU_LAYERS", "auto")
    ctx = env.get("CTX_SIZE", "")
    if layers == FULL_OFFLOAD_LAYERS:
        return Check(
            "ctx_budget",
            WARN,
            f"GPU_LAYERS=999 (all layers on GPU) at CTX_SIZE={ctx or '?'} is the "
            ">26 GB config for the 30B - busts the Nano-4B ~5.5 GiB single-GPU "
            "budget; auto/48 is the A5500 shape",
        )
    return Check(
        "ctx_budget",
        INFO,
        f"CTX_SIZE={ctx or '?'} PARALLEL={env.get('PARALLEL', '?')} "
        f"GPU_LAYERS={layers} - {CTX_BUDGET_NOTE}",
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
        _check_llm_model(env),
        _check_mount(compose_paths),
        _check_passthrough(compose_paths),
        _check_budget(env),
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
        "[V 2026-09-25] .env.example:503 documents 'SINGLE-GPU: Set all to 0'; "
        "shipped defaults are dual-GPU: GPU_YOLO26/CLIP/ENRICHMENT/"
        "ENRICHMENT_LIGHT=1 (:516-519) and GPU_AI_SERVICES=1 (:899) - set all "
        "to 0 on the A5500 box",
    ],
    "Device passthrough": [
        "[V 2026-09-25] amend: compose carries NO per-device A400 entry to "
        "remove. docker-compose.prod.yml:139 uses nvidia.com/gpu=${GPU_LLM:-0}; "
        ":303 and :1262 pass nvidia.com/gpu=all (rootless-podman CDI design "
        "comment at :300,:320). A400 removal is therefore CDI-handler / "
        "physical, not a compose edit - confirm the retired card is out of "
        "the CDI set",
    ],
    "CUDA architecture": [
        "[V 2026-09-25] .env.example:512 ships CUDA_ARCHITECTURES=89; "
        "docker-compose.prod.yml:136 threads ${CUDA_ARCHITECTURES:-} into the "
        "ai-llm build; setup.py:490 writes the auto-detected value only when "
        "setup.py runs - check-before-build stands",
    ],
    "Placeholder LLM": [
        "[V 2026-09-25] .env.example:404 ships "
        "LLM_MODEL_PATH=/models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf; "
        "docker-compose.prod.yml ai-llm volume mounts "
        ".../nemotron/nemotron-3-nano-30b-a3b-q4km:/models:ro (spec's "
        "'targets the 30B dir' confirmed) and MODEL_PATH="
        "${LLM_MODEL_PATH:-...30B...} - both the .env value AND the mount dir "
        "change for the Nano-4B",
        "[V 2026-09-25] amend: docker-compose.ghcr.yml:165/:172 hardcode the "
        "models mount AND MODEL_PATH=.../Nemotron-3-Nano-30B-A3B-Q2_K_L.gguf - "
        "on the ghcr image path a .env switch does not reach the model; edit "
        "the compose (or run prod compose) on the A5500 box",
    ],
    "Test-environment traps": [
        "[V 2026-09-25] TMPDIR=/ephemeral/podman-tmp at .env.example:58; "
        "backend/api/routes/system.py:2508-2530 _runtime_env_path() gates on "
        "tempfile.gettempdir() -> the four write_runtime_env tests "
        "(unit/api/routes/test_system.py:576,:598; unit/routes/"
        "test_system_routes.py:106,:2301) false-redden when env TMPDIR "
        "differs from pytest tmp_path. CI sets no TMPDIR",
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
    "A5500 bring-up checklist (step 0.2) - dated copy with [V] repo-side "
    "amendments from the P0.2 prep review"
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
        f"Dated {date_str}. Source: spec §'A5500 bring-up checklist (step 0.2)' "
        f"(docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md). "
        f"Repo-side prep via `scripts/a5500_precheck.py` (F9/F6: execution is "
        f"owner-run on real media; this document claims no execution).",
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
        "`CUDA_ARCHITECTURES=86`. Check it BEFORE building `ai-llm`.",
        f"- repo verdict: {v('cuda_arch')}",
    ]
    lines += [f"- {a}" for a in AMENDMENTS["CUDA architecture"]]
    lines += [
        "",
        "## - [ ] Placeholder LLM",
        "Point `LLM_MODEL_PATH` at `NVIDIA-Nemotron-3-Nano-4B` Q4_K_M "
        "(official GGUF, 2.64 GiB; arch `nemotron_h`, registered by llama.cpp "
        "b7972). Adjust the `ai-llm` volume mount (it targets the 30B dir). "
        "Budget ~5.5 GiB including the 262K-token KV. The 30B GGUF STAYS on "
        "disk - it is the replay control.",
        f"- repo verdict: {v('llm_model')}",
        f"- repo verdict: {v('ai_llm_mount')}",
        f"- repo verdict: {v('model_env_passthrough')}",
        f"- repo verdict: {v('ctx_budget')}",
    ]
    lines += [f"- {a}" for a in AMENDMENTS["Placeholder LLM"]]
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
