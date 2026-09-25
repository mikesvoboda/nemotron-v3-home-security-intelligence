"""Unit tests for scripts/a5500_precheck.py (P0.2 A5500 bring-up, repo-side prep).

ABOUTME: The bring-up checklist's claims are machine-checked, not vibes: the
precheck reads an env file + compose files + the repo tree and returns one
verdict per checklist item. Tests build ONLY synthetic fixture files (D10 -
nothing real, nothing off-box) and pin: green synthetic input exits clean;
the shipped .env.example reads with the three known not-ready-for-A5500
FAILs (that IS the [V] prep-review verdict, pinned against the real tree).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add project root to path for imports - must be before script imports
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.a5500_precheck import (  # noqa: E402
    FAIL,
    INFO,
    MANUAL,
    PASS,
    REQUIRED_GPU_VARS,
    WARN,
    Check,
    parse_env,
    run_precheck,
    scan_stale_pycache,
)

# ---------------------------------------------------------------------------
# Synthetic fixtures - single-GPU-ready config (the acceptance input)
# ---------------------------------------------------------------------------

GREEN_ENV = """\
# synthetic single-GPU A5500 .env (no TMPDIR trap)
CUDA_ARCHITECTURES=86
GPU_LLM=0
GPU_FLORENCE=0
GPU_YOLO26=0
GPU_CLIP=0
GPU_ENRICHMENT=0
GPU_ENRICHMENT_LIGHT=0
GPU_AI_SERVICES=0
LLM_MODEL_PATH=/models/NVIDIA-Nemotron-3-Nano-4B-Instruct-Q4_K_M.gguf
CTX_SIZE=262144
PARALLEL=8
GPU_LAYERS=auto
"""

GREEN_COMPOSE = """\
services:
  ai-llm:
    build:
      args:
        CUDA_ARCHITECTURES: ${CUDA_ARCHITECTURES:-}
    devices:
      - nvidia.com/gpu=${GPU_LLM:-0}
    volumes:
      - ${AI_MODELS_PATH:-/export/ai_models}/nemotron/nemotron-3-nano-4b-q4km:/models:ro
    environment:
      - MODEL_PATH=${LLM_MODEL_PATH:-/models/NVIDIA-Nemotron-3-Nano-4B-Instruct-Q4_K_M.gguf}
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _by_id(checks: list[Check]) -> dict[str, Check]:
    return {c.check_id: c for c in checks}


# ---------------------------------------------------------------------------
# parse_env
# ---------------------------------------------------------------------------


class TestParseEnv:
    def test_comments_and_blanks_ignored_last_wins(self) -> None:
        env = parse_env("# c\nA=1\n\n  # indented comment\nA=2\nB=x=y\n")
        assert env == {"A": "2", "B": "x=y"}

    def test_export_prefix_tolerated(self) -> None:
        assert parse_env("export GPU_LLM=0\n")["GPU_LLM"] == "0"


# ---------------------------------------------------------------------------
# gpu_assignment (checklist item 1: every GPU_* = 0)
# ---------------------------------------------------------------------------


class TestGpuAssignment:
    def test_all_zero_passes(self, tmp_path: Path) -> None:
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["gpu_assignment"].verdict == PASS

    def test_nonzero_vars_named_in_detail(self, tmp_path: Path) -> None:
        env = _write(
            tmp_path,
            "dual.env",
            GREEN_ENV.replace("GPU_YOLO26=0", "GPU_YOLO26=1").replace(
                "GPU_AI_SERVICES=0", "GPU_AI_SERVICES=1"
            ),
        )
        checks = run_precheck(
            env_path=env,
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["gpu_assignment"]
        assert c.verdict == FAIL
        assert "GPU_YOLO26" in c.detail and "GPU_AI_SERVICES" in c.detail

    def test_missing_required_var_named(self, tmp_path: Path) -> None:
        env = _write(tmp_path, "thin.env", "CUDA_ARCHITECTURES=86\nGPU_LLM=0\n")
        checks = run_precheck(
            env_path=env,
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["gpu_assignment"]
        assert c.verdict == FAIL
        assert "GPU_CLIP" in c.detail
        for var in REQUIRED_GPU_VARS:
            assert var in (
                "GPU_LLM",
                "GPU_FLORENCE",
                "GPU_YOLO26",
                "GPU_CLIP",
                "GPU_ENRICHMENT",
                "GPU_ENRICHMENT_LIGHT",
                "GPU_AI_SERVICES",
            )


# ---------------------------------------------------------------------------
# cuda_arch (checklist item 2: CUDA_ARCHITECTURES=86, check BEFORE build)
# ---------------------------------------------------------------------------


class TestCudaArch:
    def test_86_passes_and_naming_89_fails(self, tmp_path: Path) -> None:
        checks89 = run_precheck(
            env_path=_write(
                tmp_path,
                "e89.env",
                GREEN_ENV.replace("CUDA_ARCHITECTURES=86", "CUDA_ARCHITECTURES=89"),
            ),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks89)["cuda_arch"]
        assert c.verdict == FAIL
        assert "89" in c.detail and "86" in c.detail
        checks86 = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks86)["cuda_arch"].verdict == PASS

    def test_empty_means_build_for_all_archs_warn(self, tmp_path: Path) -> None:
        # setup.py semantics: empty = build for all common architectures -
        # correct-but-slow, so WARN not FAIL.
        env = _write(
            tmp_path,
            "emptyarch.env",
            GREEN_ENV.replace("CUDA_ARCHITECTURES=86", "CUDA_ARCHITECTURES="),
        )
        checks = run_precheck(
            env_path=env,
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["cuda_arch"].verdict == WARN


# ---------------------------------------------------------------------------
# llm_model + ai_llm_mount (checklist item 3: Nano-4B Q4_K_M placeholder;
# the ai-llm volume mount targets the 30B dir - adjust it too)
# ---------------------------------------------------------------------------


class TestLlmModel:
    def test_30b_path_fails_naming_current_value(self, tmp_path: Path) -> None:
        env = _write(
            tmp_path,
            "30b.env",
            GREEN_ENV.replace(
                "LLM_MODEL_PATH=/models/NVIDIA-Nemotron-3-Nano-4B-Instruct-Q4_K_M.gguf",
                "LLM_MODEL_PATH=/models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf",
            ),
        )
        checks = run_precheck(
            env_path=env,
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["llm_model"]
        assert c.verdict == FAIL
        assert "Nano-30B" in c.detail  # current value surfaced

    def test_nano4b_wrong_quant_fails(self, tmp_path: Path) -> None:
        env = _write(
            tmp_path,
            "q8.env",
            GREEN_ENV.replace("Q4_K_M.gguf", "Q8_0.gguf"),
        )
        checks = run_precheck(
            env_path=env,
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["llm_model"].verdict == FAIL

    def test_mount_on_30b_dir_fails_nano4b_mount_passes(self, tmp_path: Path) -> None:
        prod30 = GREEN_COMPOSE.replace(
            "nemotron/nemotron-3-nano-4b-q4km:/models:ro",
            "nemotron/nemotron-3-nano-30b-a3b-q4km:/models:ro",
        )
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "prod30.yml", prod30)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["ai_llm_mount"]
        assert c.verdict == FAIL
        assert "30b" in c.detail.lower()
        checks_ok = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks_ok)["ai_llm_mount"].verdict == PASS

    def test_hardcoded_model_path_warns(self, tmp_path: Path) -> None:
        # ghcr compose pins MODEL_PATH literally - LLM_MODEL_PATH cannot reach it
        ghcr = GREEN_COMPOSE.replace(
            "- MODEL_PATH=${LLM_MODEL_PATH:-/models/NVIDIA-Nemotron-3-Nano-4B-Instruct-Q4_K_M.gguf}",
            "- MODEL_PATH=/models/Nemotron-3-Nano-30B-A3B-Q2_K_L.gguf",
        )
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "ghcr.yml", ghcr)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["model_env_passthrough"]
        assert c.verdict == WARN
        assert "MODEL_PATH" in c.detail


# ---------------------------------------------------------------------------
# device_passthrough (checklist item 1b: A400 removed / CDI all-passthrough)
# ---------------------------------------------------------------------------


class TestDevicePassthrough:
    def test_literal_gpu_all_warns(self, tmp_path: Path) -> None:
        compose = GREEN_COMPOSE.replace("- nvidia.com/gpu=${GPU_LLM:-0}", "- nvidia.com/gpu=all")
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "w.yml", compose)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["device_passthrough"]
        assert c.verdict == WARN
        assert "all" in c.detail

    def test_hardwired_nonzero_device_fails(self, tmp_path: Path) -> None:
        compose = GREEN_COMPOSE.replace("- nvidia.com/gpu=${GPU_LLM:-0}", "- nvidia.com/gpu=1")
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "w.yml", compose)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["device_passthrough"].verdict == FAIL

    def test_env_var_device_ref_passes(self, tmp_path: Path) -> None:
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["device_passthrough"].verdict == PASS


# ---------------------------------------------------------------------------
# tmpdir_trap (checklist item 4a: .env TMPDIR false-reddens write_runtime_env)
# ---------------------------------------------------------------------------


class TestTmpdirTrap:
    def test_tmpdir_set_warns_naming_the_four_tests(self, tmp_path: Path) -> None:
        env = _write(tmp_path, "trap.env", GREEN_ENV + "TMPDIR=/ephemeral/podman-tmp\n")
        checks = run_precheck(
            env_path=env,
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["tmpdir_trap"]
        assert c.verdict == WARN
        assert "write_runtime_env" in c.detail

    def test_no_tmpdir_passes(self, tmp_path: Path) -> None:
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["tmpdir_trap"].verdict == PASS


# ---------------------------------------------------------------------------
# pycache_stale (checklist item 4b: stale __pycache__ for DELETED modules)
# ---------------------------------------------------------------------------


class TestStalePycache:
    def test_orphan_pyc_detected_live_pyc_not_flagged(self, tmp_path: Path) -> None:
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "alive.py").write_text("x = 1\n", encoding="utf-8")
        cache = pkg / "__pycache__"
        cache.mkdir()
        (cache / "alive.cpython-314.pyc").write_bytes(b"\x00")  # source exists -> fine
        (cache / "deleted_module.cpython-314.pyc").write_bytes(b"\x00")  # no source -> stale
        stale = scan_stale_pycache(tmp_path)
        assert stale == ["pkg/__pycache__/deleted_module.cpython-314.pyc"]

    def test_clean_tree_returns_empty(self, tmp_path: Path) -> None:
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "alive.py").write_text("x = 1\n", encoding="utf-8")
        cache = pkg / "__pycache__"
        cache.mkdir()
        (cache / "alive.cpython-314.pyc").write_bytes(b"\x00")
        assert scan_stale_pycache(tmp_path) == []

    def test_check_lists_stale_names(self, tmp_path: Path) -> None:
        cache = tmp_path / "scripts" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "gone.cpython-314.pyc").write_bytes(b"\x00")
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["pycache_stale"]
        assert c.verdict == WARN
        assert "gone.cpython-314.pyc" in c.detail


# ---------------------------------------------------------------------------
# ctx_budget (spec sizing: Nano-4B ~2.64 GiB + 262K-token KV, ~5.5 GiB [C])
# ---------------------------------------------------------------------------


class TestCtxBudget:
    def test_info_line_reports_the_sizing_inputs(self, tmp_path: Path) -> None:
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["ctx_budget"]
        assert c.verdict == INFO
        assert "262144" in c.detail

    def test_full_offload_above_budget_warns(self, tmp_path: Path) -> None:
        # GPU_LAYERS=999 (all layers) at 262K ctx is the >26GB config - not the
        # ~5.5 GiB Nano-4B single-GPU budget.
        env = _write(
            tmp_path, "offload.env", GREEN_ENV.replace("GPU_LAYERS=auto", "GPU_LAYERS=999")
        )
        checks = run_precheck(
            env_path=env,
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["ctx_budget"].verdict == WARN


# ---------------------------------------------------------------------------
# health (checklist item 5: owner-run, never auto-pass)
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_is_manual_even_on_green_input(self, tmp_path: Path) -> None:
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["health"].verdict == MANUAL

    def test_green_synthetic_input_has_no_fails(self, tmp_path: Path) -> None:
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert [c.check_id for c in checks if c.verdict == FAIL] == []
        ids = [c.check_id for c in checks]
        assert ids == [
            "gpu_assignment",
            "device_passthrough",
            "cuda_arch",
            "llm_model",
            "ai_llm_mount",
            "model_env_passthrough",
            "ctx_budget",
            "tmpdir_trap",
            "pycache_stale",
            "health",
        ]


# ---------------------------------------------------------------------------
# Dated copied checklist render (plan Task 6 box 2: [V]-amended spec §0.2)
# ---------------------------------------------------------------------------


class TestChecklistRender:
    def test_render_is_dated_copies_spec_items_and_carries_verdicts(self, tmp_path: Path) -> None:
        from scripts.a5500_precheck import render_checklist

        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        md = render_checklist(checks, date_str="2026-09-25")
        assert "2026-09-25" in md
        # spec §"A5500 bring-up checklist" items, copied (paraphrase anchors):
        for anchor in (
            "GPU assignment",
            "CUDA architecture",
            "Placeholder LLM",
            "Test-environment traps",
            "Health",
        ):
            assert anchor in md
        # [V] amendments present for every reviewed claim
        assert md.count("[V") >= 5
        # verdicts rendered
        assert "gpu_assignment" in md and "MANUAL" in md

    def test_render_flags_amended_ghcr_passthrough_claim(self, tmp_path: Path) -> None:
        from scripts.a5500_precheck import render_checklist

        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        md = render_checklist(checks, date_str="2026-09-25")
        # the spec says "adjust the mount too" - [V] amendment records the
        # ghcr compose additionally hardcodes MODEL_PATH
        assert "ghcr" in md.lower()


# ---------------------------------------------------------------------------
# Real-tree [V] prep-review pin: the shipped example is NOT A5500-ready, and
# the precheck says exactly which items, with today's line anchors.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_checks() -> list[Check]:
    return run_precheck(
        env_path=PROJECT_ROOT / ".env.example",
        compose_paths=[
            PROJECT_ROOT / "docker-compose.prod.yml",
            PROJECT_ROOT / "docker-compose.ghcr.yml",
        ],
        repo_root=PROJECT_ROOT,
    )


class TestRealTreePrepReview:
    def test_example_ships_the_three_known_not_ready_fails(self, real_checks) -> None:
        by_id = _by_id(real_checks)
        # .env.example ships dual-GPU defaults (:516-519,:899), CUDA 89 (:512),
        # 30B model path (:404) and the 30B dir mount -> each must read FAIL.
        assert by_id["gpu_assignment"].verdict == FAIL
        assert by_id["cuda_arch"].verdict == FAIL
        assert by_id["llm_model"].verdict == FAIL
        assert by_id["ai_llm_mount"].verdict == FAIL

    def test_example_tmpdir_trap_read(self, real_checks) -> None:
        assert _by_id(real_checks)["tmpdir_trap"].verdict == WARN

    def test_prod_compose_cdi_all_warns_not_fails(self, real_checks) -> None:
        # nvidia.com/gpu=all on the gateway is CDI by design (prod compose :303)
        assert _by_id(real_checks)["device_passthrough"].verdict == WARN

    def test_health_manual_on_real_tree(self, real_checks) -> None:
        assert _by_id(real_checks)["health"].verdict == MANUAL
