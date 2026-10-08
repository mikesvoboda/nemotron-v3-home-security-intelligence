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

AMENDED 2026-09-29 (R8 S2b): the ai-llm service was deleted from every compose
file, so the legacy_llm row now PASSes when read against the REAL tree (the
gate stays for a re-added, ungated ai-llm - pinned on synthetic compose text in
TestLegacyLlmNotDeployed). The LEGACY_COMPOSE fixture is synthetic from here on.
"""

from __future__ import annotations

import ast
import inspect
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
    read_selinux_enforcing,
    read_selinux_label,
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

# A compose that also carries the legacy serving service. SYNTHETIC since R8
# S2b deleted ai-llm from every compose file; the shape it reproduces is
# prod.yml's PRE-delete one (ai-llm with NO profile, so it started whether or
# not the vlm profile was on), which is exactly the regression the legacy_llm
# gate still has teeth for.
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


# The four serving-weight digests the handout has to print, so a cold box can
# verify what it fetched (the mmproj pair included: an F16 projector instead of
# the Q8_0 loads fine and matches no hash, which is the loudest silent failure
# available on this run). These are public model hashes, not credentials -
# detect-secrets flags a bare sha256 as a Hex High Entropy String, the same false
# positive models.yml:204 carries, so the same mitigation applies. It lives at
# module level because the pragma must sit on the secret's OWN line: inside an
# indented assert, ruff-format wraps a 64-char hex and orphans the pragma, and
# detect-secrets then rejects it (verified against the real hook).
SERVING_WEIGHT_SHA256S = {
    "67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2",  # pragma: allowlist secret
    "c6ba85508d82f42590e6eb77d5340369ab6fecf107a7561d809523d8aa5f3bfd",  # pragma: allowlist secret
    "66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a",  # pragma: allowlist secret
    "30ba2c7dd3127a4561b6cba9d13d0f711c91bdb38742e2f56d73c8cb596bd06d",  # pragma: allowlist secret
}


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
        # A legacy-only stack: no ai-vlm service at all. Not a FAIL (prod
        # compose is the vlm path), but it must be said, not silently PASSed.
        legacy_only = """\
services:
  ai-llm:
    volumes:
      - ${AI_MODELS_PATH:-/export/ai_models}/nemotron/x:/models:ro
"""
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "legacy.yml", legacy_only)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["ai_vlm_mount"]
        assert c.verdict == WARN
        assert "legacy.yml" in c.detail

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
        # The gate's live teeth, on synthetic text: the shape is prod.yml's
        # PRE-S2b one (ai-llm with NO profiles block, so a `--profile vlm` up
        # brought BOTH serving services on one GPU). The service is gone from the
        # tree, but if it comes back ungated the single A5500 cannot serve both,
        # so the WARN still has to fire - which is why the check was not deleted
        # along with the service.
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

    def test_no_ai_vlm_anywhere_warns_a_prebuilt_stack_cannot_serve(self, tmp_path: Path) -> None:
        legacy_only = """\
services:
  ai-llm:
    image: ghcr.io/org/ai-llm:latest
"""
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "legacy.yml", legacy_only)],
            repo_root=tmp_path,
        )
        c = _by_id(checks)["vlm_image"]
        assert c.verdict == WARN
        assert "legacy.yml" in c.detail


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
# selinux_camera_root (A5500 box, 2026-09-28): SELinux enforcing + a usr_t
# camera root + a /cameras mount without :z = the backend can READ uploads but
# its inotify WATCH is denied (`avc: denied { watch watch_reads }`), and the
# file watcher went silently blind. The host readers are injected so these
# pins never depend on the CI host's SELinux state.
# ---------------------------------------------------------------------------

USR_T = "system_u:object_r:usr_t:s0"
CONTAINER_FILE_T = "system_u:object_r:container_file_t:s0"

# prod.yml's shape: the backend mounts the camera root, and so does
# foscam-init (whose bare mount is not the watcher's business).
BACKEND_CAMERA_MOUNT = "      - ${FOSCAM_BASE_PATH:-/export/foscam}:/cameras\n"
CAMERA_COMPOSE = (
    GREEN_COMPOSE
    + "  backend:\n"
    + "    volumes:\n"
    + "      - ./backend/data:/app/data:z,U\n"
    + BACKEND_CAMERA_MOUNT
    + "  foscam-init:\n"
    + "    volumes:\n"
    + "      - ${FOSCAM_BASE_PATH:-/export/foscam}:/cameras\n"
)


def _camera_compose_with(opts: str) -> str:
    """CAMERA_COMPOSE with the BACKEND's /cameras mount given ``opts``."""
    out = CAMERA_COMPOSE.replace(
        BACKEND_CAMERA_MOUNT, BACKEND_CAMERA_MOUNT.replace(":/cameras\n", f":/cameras{opts}\n"), 1
    )
    assert out != CAMERA_COMPOSE
    return out


class TestSelinuxCameraRoot:
    @staticmethod
    def _check(
        tmp_path: Path,
        *,
        enforcing: bool | None,
        label: str | None,
        compose: dict[str, str] | None = None,
        env: str = GREEN_ENV,
        labels_asked: list[str] | None = None,
    ) -> Check:
        def fake_label(path: str) -> str | None:
            if labels_asked is not None:
                labels_asked.append(path)
            return label

        compose = compose or {"prod.yml": CAMERA_COMPOSE}
        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", env),
            compose_paths=[_write(tmp_path, name, text) for name, text in compose.items()],
            repo_root=tmp_path,
            selinux_enforcing=lambda: enforcing,
            selinux_label=fake_label,
        )
        return _by_id(checks)["selinux_camera_root"]

    def test_enforcing_usr_t_and_no_relabel_warns_with_the_fix(self, tmp_path: Path) -> None:
        c = self._check(tmp_path, enforcing=True, label=USR_T)
        assert c.verdict == WARN
        assert "/export/foscam" in c.detail  # FOSCAM_BASE_PATH default
        assert "usr_t" in c.detail
        assert ":z" in c.detail
        assert "container_file_t" in c.detail
        assert "avc: denied { watch }" in c.detail
        assert "prod.yml" in c.detail

    def test_selinux_not_enforcing_passes_with_the_reason(self, tmp_path: Path) -> None:
        c = self._check(tmp_path, enforcing=False, label=USR_T)
        assert c.verdict == PASS
        assert "not enforcing" in c.detail

    def test_no_selinux_on_the_host_passes_with_the_reason(self, tmp_path: Path) -> None:
        c = self._check(tmp_path, enforcing=None, label=None)
        assert c.verdict == PASS
        assert "not present" in c.detail

    def test_camera_root_already_container_file_t_passes(self, tmp_path: Path) -> None:
        c = self._check(tmp_path, enforcing=True, label=CONTAINER_FILE_T)
        assert c.verdict == PASS
        assert "container_file_t" in c.detail

    @pytest.mark.parametrize("opts", [":z", ":Z", ":ro,z"])
    def test_a_relabelling_backend_mount_passes(self, tmp_path: Path, opts: str) -> None:
        # foscam-init's bare mount stays bare: only the backend's counts.
        c = self._check(
            tmp_path, enforcing=True, label=USR_T, compose={"prod.yml": _camera_compose_with(opts)}
        )
        assert c.verdict == PASS
        assert ":z" in c.detail

    def test_a_compose_file_without_the_relabel_is_named(self, tmp_path: Path) -> None:
        # prod.yml relabels, ghcr.yml mounts :ro bare: the ghcr path is the
        # one that goes blind, and the WARN must say which file.
        c = self._check(
            tmp_path,
            enforcing=True,
            label=USR_T,
            compose={
                "prod.yml": _camera_compose_with(":z"),
                "ghcr.yml": _camera_compose_with(":ro"),
            },
        )
        assert c.verdict == WARN
        assert "ghcr.yml" in c.detail
        assert "prod.yml: " not in c.detail

    def test_the_camera_root_comes_from_the_env_file(self, tmp_path: Path) -> None:
        asked: list[str] = []
        c = self._check(
            tmp_path,
            enforcing=True,
            label=USR_T,
            env=GREEN_ENV + "FOSCAM_BASE_PATH=/srv/cams\n",
            labels_asked=asked,
        )
        assert asked == ["/srv/cams"]
        assert "/srv/cams" in c.detail

    def test_an_unreadable_label_under_enforcing_still_warns(self, tmp_path: Path) -> None:
        # Camera root not created on this box yet, or no xattr: nothing proves
        # it is watchable, and the mount will not relabel it.
        c = self._check(tmp_path, enforcing=True, label=None)
        assert c.verdict == WARN


class TestSelinuxHostReaders:
    def test_enforce_file_values(self, tmp_path: Path) -> None:
        assert read_selinux_enforcing(_write(tmp_path, "on", "1\n")) is True
        assert read_selinux_enforcing(_write(tmp_path, "off", "0\n")) is False
        assert read_selinux_enforcing(tmp_path / "absent") is None

    def test_label_of_a_missing_path_is_none_not_a_crash(self, tmp_path: Path) -> None:
        assert read_selinux_label(str(tmp_path / "absent")) is None

    def test_label_of_a_real_dir_is_a_string_or_none(self, tmp_path: Path) -> None:
        # CI hosts may or may not carry SELinux xattrs; either answer is fine,
        # an exception is not.
        label = read_selinux_label(str(tmp_path))
        assert label is None or (isinstance(label, str) and "\x00" not in label)


class TestSharedSelinuxCheck:
    """setup.py deploy's preflight and this row are ONE check
    (setup_lib/selinux_check.py), so they cannot drift apart."""

    SHARED = PROJECT_ROOT / "setup_lib" / "selinux_check.py"

    @pytest.mark.parametrize("reader", [read_selinux_enforcing, read_selinux_label])
    def test_the_host_readers_are_the_shared_modules(self, reader) -> None:
        assert Path(inspect.getfile(reader)).resolve() == self.SHARED

    def test_the_precheck_stays_stdlib_only(self) -> None:
        # It runs on a cold box with no venv: the shared module is loaded by
        # path, never via the setup_lib package (whose __init__ pulls the
        # whole setup toolchain).
        tree = ast.parse((PROJECT_ROOT / "scripts" / "a5500_precheck.py").read_text())
        imported = {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        } | {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert imported <= set(sys.stdlib_module_names) | {"__future__"}, imported


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
            "selinux_camera_root",
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
        assert "selinux_camera_root" in md
        # the retired pair's ids are gone from the render (conversion, not
        # accretion: an A5500 reader must not find a Nano-4B instruction)
        assert "llm_model`" not in md
        assert "ai_llm_mount" not in md


# ---------------------------------------------------------------------------
# The handout is the A5500 run's ONLY interface to the repo, so it must carry
# what the run is FOR. A 2026-09-28 readiness audit found it asked for two "S1
# peaks" while never printing S1's bar, never mentioned S4 at all (the bar the
# spec reserves to THIS box, spec :86/:388), mandated the enforcement probe as a
# one-shot "refusal check" (bake-off finding ①: a lone ENFORCED pass produced a
# false positive once), printed no build command for an image that has no
# registry ref, and prescribed an up that hard-waits on the retired 30B. Each
# pin below is one of those findings, asserted on the RENDER because the
# render is what the operator reads - and every one of them was RED before the
# rows were added. The failure mode is not an ugly document: a run that
# satisfied every row the handout had would still leave a spec-reserved bar
# unmeasured and would have taken a CPU-offloaded serve as a passing S1.
# ---------------------------------------------------------------------------


class TestHandoutIsExecutableOnAColdBox:
    @staticmethod
    def _render(tmp_path: Path) -> str:
        from scripts.a5500_precheck import render_checklist

        checks = run_precheck(
            env_path=_write(tmp_path, "green.env", GREEN_ENV),
            compose_paths=[_write(tmp_path, "green.yml", GREEN_COMPOSE)],
            repo_root=tmp_path,
        )
        return render_checklist(checks, date_str="2026-09-27")

    def test_s1_is_asked_with_its_bar_and_a_sampler(self, tmp_path: Path) -> None:
        # S1 is "peak VRAM <= 20.4 GiB (0.85 x 24 GB) with detector +
        # specialists + VLM resident, no CPU offload" (spec :83). A bare "take
        # its S1 peak" cannot be judged, sampled, or ledgered.
        md = self._render(tmp_path)
        assert "20.4 GiB" in md, "S1's bar is absent: an operator cannot pass or fail it"
        assert "nvidia-smi --query-gpu=memory.used" in md, "no sampler given"
        assert "offload" in md.lower(), "S1's no-CPU-offload condition is not stated"
        # VLM_GPU_LAYERS defaults to auto (= offload when over budget), so the
        # trap has to be named or an offloaded serve reads as a pass.
        assert "VLM_GPU_LAYERS" in md

    def test_s4_is_asked_for_on_the_box_the_spec_reserves_it_to(self, tmp_path: Path) -> None:
        # The audit's sharpest finding: zero occurrences of "S4"/"p95" anywhere
        # in the handout or its generator, against spec :86 and the §8 machine
        # split that assigns S4 to this card.
        md = self._render(tmp_path)
        assert "S4" in md
        assert "30" in md and "p95" in md.lower()
        assert "cold start" in md.lower(), "S4 counts cold starts; a warm-only run is not S4"

    def test_the_probe_is_named_invoked_and_repeated_not_one_shot(self, tmp_path: Path) -> None:
        # P0.3 is a nonce-const grammar check whose own docstring warns that a
        # "wall of refusals" must not be read as the verdict; and bake-off
        # finding ① is a false ENFORCED from a single pass. So: name the script,
        # give its real invocation, require repeats.
        md = self._render(tmp_path)
        assert "scripts/vlm_probes/enforcement.py" in md
        assert "--expect-build" in md
        assert "3" in md and ("N>=3" in md or "three" in md.lower())
        assert "refusal check" not in md, "the probe is a grammar check, not a refusal count"

    def test_it_prints_a_build_command_because_there_is_nothing_to_pull(
        self, tmp_path: Path
    ) -> None:
        # ai-vlm has no `image:` key, no ghcr presence, no VLM_IMAGE var - the
        # A5500 must build. The handout already printed "--build-arg
        # CUDA_ARCHITECTURES=86" inside the vlm_image VERDICT detail, which is
        # why this pin is written to need an actual invocation and the
        # nothing-to-pull fact: the flag alone was green before any fix and
        # proves nothing (a pin that passes on the unfixed tree is the finding,
        # not the reassurance).
        md = self._render(tmp_path)
        assert "podman build" in md or "build ai-vlm" in md, "no actual build invocation"
        assert "no `image:` key" in md or "nothing to pull" in md.lower()

    def test_the_up_set_is_executable_without_the_retired_30b(self, tmp_path: Path) -> None:
        # backend depends_on ai-llm: service_healthy (prod:708-717) and ai-llm
        # is unprofiled (:120), so "keep ai-llm out of the up set" was prose
        # with no implementation. The repo's own proven answer is --no-deps
        # (scripts/bootstrap-gb300.sh:276).
        md = self._render(tmp_path)
        assert "--no-deps" in md, "no executable up shape: a plain up waits on the 30B"

    def test_weights_are_treated_as_absent_on_a_cold_box(self, tmp_path: Path) -> None:
        # Both pairs, byte counts, hashes, the target dir, and finding F's
        # chmod 644. The 4B pair had no sha256 anywhere in the repo before
        # 2026-09-28 even though this run is REQUIRED to serve it. All FOUR
        # digests are required, not just the two weights: the handout that omits
        # an mmproj hash is the one that lets an F16 projector through.
        md = self._render(tmp_path)
        # Guard the pin itself: a membership test over an emptied set passes
        # vacuously, which is the green-on-a-broken-tree failure this repo has
        # now caught in its own test code twice.
        assert len(SERVING_WEIGHT_SHA256S) == 4
        missing = {h for h in SERVING_WEIGHT_SHA256S if h not in md}
        assert not missing, f"handout omits {len(missing)} of 4 weight digests"
        assert "chmod 644" in md
        assert "NOT what the A5500 lacks" not in md, (
            "the GB300-share claim is false on a cold box and was corrected, not carried forward"
        )

    def test_the_end_to_end_chain_that_makes_m1_assertion_2_mean_something(
        self, tmp_path: Path
    ) -> None:
        # plan :181: synthetic still -> detector-closed batch -> vlm verdict ->
        # event + verification row -> badge -> notification decision. Nothing in
        # the old handout asked for any link of it, so every row could pass
        # while M1's own exit test went unproven.
        md = self._render(tmp_path)
        for link in ("synthetic", "verdict", "verification row", "notification"):
            assert link in md.lower(), f"M1's proof chain is missing the {link!r} link"

    def test_the_first_verdict_is_explained_as_the_pre_fix_state(self, tmp_path: Path) -> None:
        # A cold operator's first run prints "2 FAIL(s) - not ready" and exit 1.
        # Those two FAILs ARE the pre-fix state steps 1-2 exist to clear; said
        # nowhere, they read as the repo being broken rather than the box.
        md = self._render(tmp_path)
        assert "pre-fix" in md.lower() or "expected before" in md.lower()

    def test_the_probes_are_run_with_the_venv_not_bare_python(self, tmp_path: Path) -> None:
        # enforcement.py/tool_calls.py import httpx; the precheck is stdlib-only.
        # Saying "run the probe" with a bare `python3` yields ModuleNotFoundError
        # on a fresh clone and looks like the endpoint being broken.
        md = self._render(tmp_path)
        assert "uv run" in md


# ---------------------------------------------------------------------------
# Real-tree [V] prep-review pin: the shipped example is NOT A5500-ready, and
# the precheck says exactly which items, with today's line anchors.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_checks() -> list[Check]:
    return run_precheck(
        env_path=PROJECT_ROOT / ".env.example",
        compose_paths=[PROJECT_ROOT / "docker-compose.prod.yml"],
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

    def test_the_shipped_stack_builds_the_vlm_from_source(self, real_checks) -> None:
        by_id = _by_id(real_checks)
        # 1.7 pinned the mirror fact: the retired ghcr compose had NO ai-vlm
        # service, so its prebuilt-image path could not serve vlm mode. O1.2
        # (UR-17) deleted that file, and the surviving fact is the PASS half:
        # the one supported stack builds ai-vlm from source, so the A5500's
        # CUDA_ARCHITECTURES=86 arg bites at build time.
        assert by_id["vlm_image"].verdict == PASS
        assert "docker-compose.prod.yml" in by_id["vlm_image"].detail

    def test_legacy_ai_llm_is_gone_from_the_shipped_compose(self, real_checks) -> None:
        # [V 2026-09-27] row's successor: the spec :482-500 item was "no legacy
        # LLM deployed", and pre-R8 the honest answer was WARN (prod.yml carried
        # an unprofiled ai-llm). R8 S2b deleted ai-llm from every compose file, so
        # the real tree now proves the stronger fact: the check PASSes by absence.
        # The WARN teeth for a re-added ai-llm stay pinned against synthetic
        # compose text in TestLegacyLlmNotDeployed - the gate is unchanged, only
        # the tree it is read against moved.
        by_id = _by_id(real_checks)
        c = by_id["legacy_llm"]
        assert c.verdict == PASS
        assert "no ai-llm service" in c.detail

    def test_example_tmpdir_trap_read(self, real_checks) -> None:
        assert _by_id(real_checks)["tmpdir_trap"].verdict == WARN

    def test_prod_compose_cdi_all_warns_not_fails(self, real_checks) -> None:
        # nvidia.com/gpu=all on the gateway is CDI by design (prod compose :303)
        assert _by_id(real_checks)["device_passthrough"].verdict == WARN

    def test_health_manual_on_real_tree(self, real_checks) -> None:
        assert _by_id(real_checks)["health"].verdict == MANUAL

    def test_on_an_enforcing_usr_t_host_every_backend_camera_mount_relabels(self) -> None:
        # prod.yml's backend mount carries :z (f88797b4c); the ghcr compose
        # carry of this same ruling (:ro,z, owner ruling 2026-09-28: all
        # compose) retired with the file itself in O1.2. Host state injected,
        # tree real.
        checks = run_precheck(
            env_path=PROJECT_ROOT / ".env.example",
            compose_paths=[PROJECT_ROOT / "docker-compose.prod.yml"],
            repo_root=PROJECT_ROOT,
            selinux_enforcing=lambda: True,
            selinux_label=lambda _path: "system_u:object_r:usr_t:s0",
        )
        c = _by_id(checks)["selinux_camera_root"]
        assert c.verdict == PASS
        assert "docker-compose.prod.yml: " in c.detail
