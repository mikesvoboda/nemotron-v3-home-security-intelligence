"""Unit tests for scripts/a5500_precheck.py (P0.2 A5500 bring-up, repo-side prep).

ABOUTME: The bring-up checklist's claims are machine-checked, not vibes: the
precheck reads an env file + compose files + the repo tree and returns one
verdict per checklist item. Tests build ONLY synthetic fixture files (D10 -
nothing real, nothing off-box) and pin: green synthetic input exits clean;
the shipped .env.example reads with the known not-ready-for-A5500 FAILs
(that IS the [V] prep-review verdict, pinned against the real tree).

AMENDED 2026-09-27 (1.7, spec rev 5): the A5500 brings up the SHIPPED vlm
mode, not the legacy LLM path - PIPELINE_MODE=vlm ships as the default
(.env.example:211) and the vlm path calls nothing else, so the two
legacy-LLM model/mount checks became ai-vlm checks (VLM_MODEL_PATH +
VLM_MMPROJ_PATH, the /vlm volume mount, the VLM ctx budget), plus a
legacy_llm check that answers the checklist's "no legacy LLM deployed" item
and a vlm_image check that says plainly whether the ghcr image path can run
the shipped mode at all.
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
# Synthetic fixtures - single-GPU-ready config (the acceptance input), in the
# SHIPPED vlm mode: PIPELINE_MODE=vlm, Qwen3-VL-8B pair, /vlm mount.
# ---------------------------------------------------------------------------

GREEN_ENV = """\
# synthetic single-GPU A5500 .env (no TMPDIR trap), shipped vlm mode
PIPELINE_MODE=vlm
GATEWAY_MODEL_SET=vlm
CUDA_ARCHITECTURES=86
GPU_LLM=0
GPU_FLORENCE=0
GPU_YOLO26=0
GPU_CLIP=0
GPU_ENRICHMENT=0
GPU_ENRICHMENT_LIGHT=0
GPU_AI_SERVICES=0
VLM_MODEL_PATH=/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf
VLM_MMPROJ_PATH=/models/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf
VLM_CTX_SIZE=32768
VLM_PARALLEL=2
VLM_GPU_LAYERS=auto
"""

GREEN_COMPOSE = """\
services:
  ai-vlm:
    build:
      args:
        CUDA_ARCHITECTURES: ${CUDA_ARCHITECTURES:-}
    profiles:
      - vlm
    devices:
      - nvidia.com/gpu=${GPU_LLM:-0}
    volumes:
      - ${AI_MODELS_PATH:-/export/ai_models}/vlm:/models:ro
    environment:
      - MODEL_PATH=${VLM_MODEL_PATH:-/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf}
      - MMPROJ_PATH=${VLM_MMPROJ_PATH:-/models/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf}
      - CTX_SIZE=${VLM_CTX_SIZE:-32768}
      - PARALLEL=${VLM_PARALLEL:-2}
"""

# A compose that also carries the legacy serving service (prod.yml's shape:
# ai-llm with NO profile, so it starts whether or not the vlm profile is on).
LEGACY_COMPOSE = (
    GREEN_COMPOSE
    + """\
  ai-llm:
    devices:
      - nvidia.com/gpu=${GPU_LLM:-0}
    volumes:
      - ${AI_MODELS_PATH:-/export/ai_models}/nemotron/nemotron-3-nano-30b-a3b-q4km:/models:ro
    environment:
      - MODEL_PATH=${LLM_MODEL_PATH:-/models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf}
"""
)


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
        c = _by_id(checks)["gpu_assignment"]
        assert c.verdict == PASS
        assert "GPU_" in c.detail

    def test_nonzero_vars_named_in_detail(self, tmp_path: Path) -> None:
        env = _write(
            tmp_path,
            "dual.env",
            GREEN_ENV.replace("GPU_YOLO26=0", "GPU_YOLO26=1").replace("GPU_CLIP=0", "GPU_CLIP=2"),
        )
        checks = run_precheck(
            env_path=env,
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["gpu_assignment"]
        assert c.verdict == FAIL
        assert "GPU_YOLO26=1" in c.detail
        assert "GPU_CLIP=2" in c.detail

    def test_missing_required_var_named(self, tmp_path: Path) -> None:
        env = _write(tmp_path, "thin.env", "CUDA_ARCHITECTURES=86\nGPU_LLM=0\n")
        checks = run_precheck(
            env_path=env,
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["gpu_assignment"]
        assert c.verdict == FAIL
        for var in REQUIRED_GPU_VARS:
            if var != "GPU_LLM":
                assert var in c.detail


# ---------------------------------------------------------------------------
# cuda_arch (checklist item 2: 86, checked BEFORE the build)
# ---------------------------------------------------------------------------


class TestCudaArch:
    def test_86_passes_and_naming_89_fails(self, tmp_path: Path) -> None:
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["cuda_arch"].verdict == PASS
        env89 = _write(
            tmp_path, "89.env", GREEN_ENV.replace("CUDA_ARCHITECTURES=86", "CUDA_ARCHITECTURES=89")
        )
        checks = run_precheck(
            env_path=env89,
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["cuda_arch"]
        assert c.verdict == FAIL
        assert "89" in c.detail
        # 1.7: the build that consumes this value in the shipped mode is ai-vlm
        assert "ai-vlm" in c.detail

    def test_empty_means_build_for_all_archs_warn(self, tmp_path: Path) -> None:
        env = _write(
            tmp_path, "empty.env", GREEN_ENV.replace("CUDA_ARCHITECTURES=86", "CUDA_ARCHITECTURES=")
        )
        checks = run_precheck(
            env_path=env,
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["cuda_arch"].verdict == WARN


# ---------------------------------------------------------------------------
# vlm_model / vlm_mount / vlm passthrough / vlm budget (checklist item 3,
# converted from the legacy placeholder-LLM pair by 1.7)
# ---------------------------------------------------------------------------


class TestVlmModel:
    def test_qwen3vl_pair_passes(self, tmp_path: Path) -> None:
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["vlm_model"].verdict == PASS

    def test_wrong_quant_fails_naming_current_value(self, tmp_path: Path) -> None:
        env = _write(
            tmp_path,
            "q8.env",
            GREEN_ENV.replace(
                "VLM_MODEL_PATH=/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf",
                "VLM_MODEL_PATH=/models/Qwen3VL-8B-Instruct-Q8_0.gguf",
            ),
        )
        checks = run_precheck(
            env_path=env,
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["vlm_model"]
        assert c.verdict == FAIL
        assert "Q8_0" in c.detail  # current value surfaced, per the pair's shape

    def test_missing_mmproj_fails_because_vision_needs_it(self, tmp_path: Path) -> None:
        # A projector-less serve loads text-only and silently degrades every
        # vlm_assess - the check refuses rather than calling it ready.
        env = _write(
            tmp_path,
            "nommp.env",
            "\n".join(
                line for line in GREEN_ENV.splitlines() if not line.startswith("VLM_MMPROJ_PATH")
            ),
        )
        checks = run_precheck(
            env_path=env,
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["vlm_model"]
        assert c.verdict == FAIL
        assert "MMPROJ" in c.detail

    def test_legacy_llm_path_is_not_the_serving_model(self, tmp_path: Path) -> None:
        # The pre-swap env (Nano-30B LLM_MODEL_PATH, no VLM_* at all) must read
        # FAIL on the vlm check - that is the conversion, stated as a pin.
        env = _write(
            tmp_path,
            "legacy.env",
            GREEN_ENV.replace(
                "VLM_MODEL_PATH=/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf\n"
                "VLM_MMPROJ_PATH=/models/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf",
                "LLM_MODEL_PATH=/models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf",
            ),
        )
        checks = run_precheck(
            env_path=env,
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["vlm_model"]
        assert c.verdict == FAIL
        assert "Qwen3VL" in c.detail  # what it wants, named


class TestVlmMount:
    def test_vlm_dir_mount_passes(self, tmp_path: Path) -> None:
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["ai_vlm_mount"]
        assert c.verdict == PASS
        assert "/vlm:/models" in c.detail

    def test_legacy_30b_mount_on_ai_vlm_fails(self, tmp_path: Path) -> None:
        bad = GREEN_COMPOSE.replace(
            "${AI_MODELS_PATH:-/export/ai_models}/vlm:/models:ro",
            "${AI_MODELS_PATH:-/export/ai_models}/nemotron/nemotron-3-nano-30b-a3b-q4km:/models:ro",
        )
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "bad.yml", bad)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["ai_vlm_mount"]
        assert c.verdict == FAIL
        assert "30b" in c.detail.lower()

    def test_ai_llms_own_30b_mount_does_not_false_redden_the_vlm_check(
        self, tmp_path: Path
    ) -> None:
        # Block-scoped: the legacy service legitimately mounts the 30B dir.
        # A flat line scan would fail the vlm mount on the legacy service's
        # own volumes - that is the false red this pin exists to prevent.
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "prod.yml", LEGACY_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["ai_vlm_mount"].verdict == PASS

    def test_no_ai_vlm_service_is_a_warn_naming_the_file(self, tmp_path: Path) -> None:
        # ghcr.yml's shape: no ai-vlm service at all. Not a FAIL (prod compose
        # is the vlm path), but it must be said, not silently PASSed.
        legacy_only = """\
services:
  ai-llm:
    volumes:
      - ${AI_MODELS_PATH:-/export/ai_models}/nemotron/x:/models:ro
"""
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "ghcr.yml", legacy_only)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["ai_vlm_mount"]
        assert c.verdict == WARN
        assert "ghcr.yml" in c.detail

    def test_zoo_and_cache_mounts_are_not_read_as_the_model_mount(self, tmp_path: Path) -> None:
        # gateway/backend mount ai_models at /models/zoo, /models/cache etc.
        # Only a mount whose TARGET is exactly /models is the weights mount.
        extra = GREEN_COMPOSE.replace(
            "      - ${AI_MODELS_PATH:-/export/ai_models}/vlm:/models:ro",
            "      - ${AI_MODELS_PATH:-/export/ai_models}/vlm:/models:ro\n"
            "      - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo:/models/model-zoo:ro",
        )
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "both.yml", extra)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["ai_vlm_mount"]
        assert c.verdict == PASS
        assert c.detail.count("/models") == 1


class TestVlmPassthrough:
    def test_env_derived_model_paths_pass(self, tmp_path: Path) -> None:
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["vlm_model_env_passthrough"].verdict == PASS

    def test_hardcoded_model_path_warns(self, tmp_path: Path) -> None:
        hard = GREEN_COMPOSE.replace(
            "- MODEL_PATH=${VLM_MODEL_PATH:-/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf}",
            "- MODEL_PATH=/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf",
        )
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "hard.yml", hard)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["vlm_model_env_passthrough"]
        assert c.verdict == WARN
        assert "MODEL_PATH" in c.detail
        assert ".env switch" in c.detail  # the actionable half

    def test_hardcoded_mmproj_warns_too(self, tmp_path: Path) -> None:
        hard = GREEN_COMPOSE.replace(
            "- MMPROJ_PATH=${VLM_MMPROJ_PATH:-/models/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf}",
            "- MMPROJ_PATH=/models/mmproj-other.gguf",
        )
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "hard.yml", hard)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["vlm_model_env_passthrough"]
        assert c.verdict == WARN
        assert "MMPROJ_PATH" in c.detail


class TestVlmCtxBudget:
    def test_info_line_reports_per_slot_budget(self, tmp_path: Path) -> None:
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["vlm_ctx_budget"]
        assert c.verdict == INFO
        assert "16384" in c.detail  # 32768 / 2, the per-slot number spec §2 sizes

    def test_slot_below_the_worst_case_need_warns(self, tmp_path: Path) -> None:
        # 8192/2 = 4096 < the ~12.2K a worst-case vlm_assess needs: the
        # verdict truncates silently. This is the check's tooth.
        env = _write(
            tmp_path,
            "small.env",
            GREEN_ENV.replace("VLM_CTX_SIZE=32768", "VLM_CTX_SIZE=8192"),
        )
        checks = run_precheck(
            env_path=env,
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["vlm_ctx_budget"]
        assert c.verdict == WARN
        assert "4096" in c.detail

    def test_full_gpu_offload_layers_warn(self, tmp_path: Path) -> None:
        env = _write(
            tmp_path,
            "full.env",
            GREEN_ENV.replace("VLM_GPU_LAYERS=auto", "VLM_GPU_LAYERS=999"),
        )
        checks = run_precheck(
            env_path=env,
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["vlm_ctx_budget"].verdict == WARN


# ---------------------------------------------------------------------------
# legacy_llm / vlm_image (1.7: the checklist's "no legacy LLM deployed" item,
# machine-checked instead of asserted)
# ---------------------------------------------------------------------------


class TestLegacyLlmNotDeployed:
    def test_profile_gated_ai_llm_warns_not_fails(self, tmp_path: Path) -> None:
        gated = LEGACY_COMPOSE.replace(
            "  ai-llm:\n",
            "  ai-llm:\n    profiles:\n      - llm\n",
        )
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "gated.yml", gated)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["legacy_llm"]
        assert c.verdict == WARN
        assert "llm" in c.detail

    def test_unprofiled_ai_llm_warns_that_it_starts_alongside_ai_vlm(self, tmp_path: Path) -> None:
        # prod.yml's shipped shape: ai-llm has NO profiles block, so a
        # `--profile vlm` up brings BOTH serving services on one GPU.
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "prod.yml", LEGACY_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["legacy_llm"]
        assert c.verdict == WARN
        assert "profile" in c.detail.lower()
        assert "ai-llm" in c.detail

    def test_no_ai_llm_service_passes(self, tmp_path: Path) -> None:
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["legacy_llm"].verdict == PASS


class TestVlmImageAvailable:
    def test_ai_vlm_buildable_from_compose_passes(self, tmp_path: Path) -> None:
        # GREEN_COMPOSE has profiles but no build block - add one: the shape
        # where the vlm service is built from source on the box.
        built = GREEN_COMPOSE.replace(
            "    build:\n      args:\n        CUDA_ARCHITECTURES: ${CUDA_ARCHITECTURES:-}\n",
            "    build:\n      context: ./ai/vlm\n      args:\n"
            "        CUDA_ARCHITECTURES: ${CUDA_ARCHITECTURES:-}\n",
        )
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "built.yml", built)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["vlm_image"].verdict == PASS

    def test_image_only_vlm_service_warns_arch_must_match_build(self, tmp_path: Path) -> None:
        img = GREEN_COMPOSE.replace(
            "    build:\n      args:\n        CUDA_ARCHITECTURES: ${CUDA_ARCHITECTURES:-}\n",
            "    image: ghcr.io/org/ai-vlm:latest\n",
        )
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "img.yml", img)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["vlm_image"]
        assert c.verdict == WARN
        assert "86" in c.detail

    def test_no_ai_vlm_anywhere_warns_the_ghcr_path_cannot_serve(self, tmp_path: Path) -> None:
        legacy_only = """\
services:
  ai-llm:
    image: ghcr.io/org/ai-llm:latest
"""
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "ghcr.yml", legacy_only)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["vlm_image"]
        assert c.verdict == WARN
        assert "ghcr.yml" in c.detail


# ---------------------------------------------------------------------------
# device_passthrough (checklist item 1b: A400 removed / CDI all-passthrough)
# ---------------------------------------------------------------------------


class TestDevicePassthrough:
    def test_literal_gpu_all_warns(self, tmp_path: Path) -> None:
        compose = GREEN_COMPOSE.replace(
            "      - nvidia.com/gpu=${GPU_LLM:-0}",
            "      - nvidia.com/gpu=all",
        )
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "all.yml", compose)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["device_passthrough"]
        assert c.verdict == WARN
        assert "A400" in c.detail

    def test_hardwired_nonzero_device_fails(self, tmp_path: Path) -> None:
        compose = GREEN_COMPOSE.replace(
            "      - nvidia.com/gpu=${GPU_LLM:-0}", "      - nvidia.com/gpu=1"
        )
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "hard.yml", compose)],
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
# test-environment traps (TMPDIR, stale __pycache__)
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
        assert "test_system.py" in c.detail

    def test_no_tmpdir_passes(self, tmp_path: Path) -> None:
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        assert _by_id(checks)["tmpdir_trap"].verdict == PASS


class TestStalePycache:
    def test_orphan_pyc_detected_live_pyc_not_flagged(self, tmp_path: Path) -> None:
        pkg = tmp_path / "backend" / "services"
        (pkg / "__pycache__").mkdir(parents=True)
        (pkg / "live.py").write_text("x = 1\n")
        (pkg / "__pycache__" / "live.cpython-314.pyc").write_bytes(b"\x00")
        (pkg / "__pycache__" / "ghost.cpython-314.pyc").write_bytes(b"\x00")
        assert scan_stale_pycache(tmp_path) == [
            "backend/services/__pycache__/ghost.cpython-314.pyc"
        ]

    def test_clean_tree_returns_empty(self, tmp_path: Path) -> None:
        assert scan_stale_pycache(tmp_path) == []

    def test_check_lists_stale_names(self, tmp_path: Path) -> None:
        pkg = tmp_path / "backend"
        (pkg / "__pycache__").mkdir(parents=True)
        (pkg / "__pycache__" / "gone.cpython-314.pyc").write_bytes(b"\x00")
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["pycache_stale"]
        assert c.verdict == WARN
        assert "gone.cpython-314.pyc" in c.detail


# ---------------------------------------------------------------------------
# health (checklist item 5: never sandbox-closable)
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
            "vlm_model",
            "ai_vlm_mount",
            "vlm_model_env_passthrough",
            "vlm_ctx_budget",
            "legacy_llm",
            "vlm_image",
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
        md = render_checklist(checks, date_str="2026-09-27")
        assert "2026-09-27" in md
        # spec §"A5500 bring-up checklist" items, copied (paraphrase anchors):
        for anchor in (
            "GPU assignment",
            "CUDA architecture",
            "Serving VLM",
            "No legacy LLM",
            "Test-environment traps",
            "Health",
        ):
            assert anchor in md
        # [V] amendments present for every reviewed claim
        assert md.count("[V") >= 5
        # verdicts rendered
        assert "vlm_model" in md and "MANUAL" in md

    def test_render_states_the_smoke_before_traffic_requirement(self, tmp_path: Path) -> None:
        # spec :482-500 / 1.7: the Qwen3-VL-8B smoke serve + enforcement probe
        # must run BEFORE any event reaches it. That ordering is the handout's
        # point, so the render must carry it, not just the model name.
        from scripts.a5500_precheck import render_checklist

        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        md = render_checklist(checks, date_str="2026-09-27")
        assert "enforcement" in md.lower()
        assert "before" in md.lower()

    def test_render_names_the_vlm_verdicts_not_the_legacy_pair(self, tmp_path: Path) -> None:
        from scripts.a5500_precheck import render_checklist

        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        md = render_checklist(checks, date_str="2026-09-27")
        assert "vlm_model" in md
        assert "ai_vlm_mount" in md
        # the retired pair's ids are gone from the render (conversion, not
        # accretion: an A5500 reader must not find a Nano-4B instruction)
        assert "llm_model`" not in md
        assert "ai_llm_mount" not in md


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
    def test_example_ships_the_known_not_ready_fails(self, real_checks) -> None:
        by_id = _by_id(real_checks)
        # .env.example ships dual-GPU defaults (:580-583,:962) and CUDA 89
        # (:576) -> each must read FAIL for the A5500.
        assert by_id["gpu_assignment"].verdict == FAIL
        assert by_id["cuda_arch"].verdict == FAIL

    def test_example_ships_the_serving_vlm_ready(self, real_checks) -> None:
        by_id = _by_id(real_checks)
        # The VLM model pair ships correct (the .env.example VLM_MODEL_PATH /
        # VLM_MMPROJ_PATH defaults; cited by name because the line anchors in
        # this file's comments drift a slice or two after any .env edit) and
        # prod.yml mounts
        # the /vlm dir with env-derived paths: the shipped
        # mode's weights are NOT part of what's missing on the A5500.
        assert by_id["vlm_model"].verdict == PASS
        assert by_id["ai_vlm_mount"].verdict == PASS
        assert by_id["vlm_model_env_passthrough"].verdict == PASS

    def test_ghcr_image_path_cannot_serve_the_vlm_mode(self, real_checks) -> None:
        by_id = _by_id(real_checks)
        # 1.7's finding, pinned: docker-compose.ghcr.yml has NO ai-vlm service
        # (it never gained one), so the ghcr image path cannot serve vlm mode.
        assert by_id["vlm_image"].verdict == WARN
        assert "ghcr" in by_id["vlm_image"].detail

    def test_legacy_ai_llm_is_unprofiled_in_prod_compose(self, real_checks) -> None:
        by_id = _by_id(real_checks)
        c = by_id["legacy_llm"]
        assert c.verdict == WARN
        assert "ai-llm" in c.detail

    def test_example_tmpdir_trap_read(self, real_checks) -> None:
        assert _by_id(real_checks)["tmpdir_trap"].verdict == WARN

    def test_prod_compose_cdi_all_warns_not_fails(self, real_checks) -> None:
        # nvidia.com/gpu=all on the gateway is CDI by design (prod compose :303)
        assert _by_id(real_checks)["device_passthrough"].verdict == WARN

    def test_health_manual_on_real_tree(self, real_checks) -> None:
        assert _by_id(real_checks)["health"].verdict == MANUAL
