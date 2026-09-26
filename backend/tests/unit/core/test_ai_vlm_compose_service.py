"""Compose/env/Dockerfile shape tests for the `ai-vlm` service (Phase 1.2).

Spec §2 row 1 (`docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md`):
the ai-vlm compose service behind profile `vlm`, llama-server + GGUF + mmproj,
--jinja/--sleep-idle-seconds/--alias, 2 slots, context sized for 4 images +
~6K text + output, host port `AI_VLM_PORT` (8098) added to .env.example FIRST
(root AGENTS.md env-first rule), no hard backend depends_on (a profiled
service would break the default `up` - ledger the degradation instead).

These are STRUCTURE tests on the three artifacts (compose YAML, .env.example,
ai/vlm/Dockerfile text): the live-behavior half of 1.2's evidence is the
GB300 serve check via agent-gpu, recorded in the ledger row, not here.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE = REPO_ROOT / "docker-compose.prod.yml"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
DOCKERFILE = REPO_ROOT / "ai" / "vlm" / "Dockerfile"


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def vlm_service(compose: dict) -> dict:
    services = compose.get("services", {})
    assert "ai-vlm" in services, "ai-vlm service missing from docker-compose.prod.yml"
    return services["ai-vlm"]


@pytest.fixture(scope="module")
def vlm_env(vlm_service: dict) -> dict[str, str]:
    """environment: list-form KEY=VALUE entries as a map."""
    raw = vlm_service.get("environment", [])
    assert isinstance(raw, list), "ai-vlm environment should stay list-form (house style)"
    return dict(item.split("=", 1) for item in raw)


class TestEnvFirst:
    """The root rule (AGENTS.md:150): the port variable lands in .env.example
    before compose references it. Asserted as CONTENT of the ports block."""

    def test_ai_vlm_port_declared(self) -> None:
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        assert re.search(r"^AI_VLM_PORT=8098$", text, re.M), (
            "AI_VLM_PORT=8098 must be declared in .env.example"
        )

    def test_ai_vlm_port_sits_in_the_ai_ports_block(self) -> None:
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        block = text[text.index("# AI SERVICE PORTS") :]
        assert "AI_VLM_PORT=8098" in block.split("# AI Gateway")[0], (
            "AI_VLM_PORT belongs in the AI SERVICE PORTS legacy-ports list"
        )

    def test_model_path_vars_declared(self) -> None:
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        assert re.search(r"^VLM_MODEL_PATH=", text, re.M)
        assert re.search(r"^VLM_MMPROJ_PATH=", text, re.M)


class TestComposeServiceShape:
    def test_profiled_vlm(self, vlm_service: dict) -> None:
        assert vlm_service.get("profiles") == ["vlm"], (
            "ai-vlm must hide behind profile vlm so the default `up` never starts it"
        )

    def test_no_depends_on(self, vlm_service: dict) -> None:
        # a profiled service named in backend's depends_on breaks the default
        # `up` (plan 1.2); degradation is 1.3's wiring, not a compose edge.
        assert "depends_on" not in vlm_service

    def test_backend_does_not_depend_on_it(self, compose: dict) -> None:
        backend = compose["services"]["backend"]
        deps = backend.get("depends_on", {})
        names = deps if isinstance(deps, (list, dict)) else {}
        assert "ai-vlm" not in names

    def test_loopback_port_env_interpolated(self, vlm_service: dict) -> None:
        assert vlm_service["ports"] == ["127.0.0.1:${AI_VLM_PORT:-8098}:8098"], (
            "loopback-only bind (AGENTS.md port rule), env-interpolated host port"
        )

    def test_container_port_is_8098(self, vlm_env: dict) -> None:
        assert vlm_env["PORT"] == "8098", (
            "container port fixed at 8098 so the internal URL (ai-vlm:8098) "
            "never depends on the host-side variable"
        )

    def test_model_paths_are_env_indented(self, vlm_env: dict) -> None:
        # prod.yml:158 style: ${VAR:-default}, never a hardcoded literal
        assert vlm_env["MODEL_PATH"].startswith("${VLM_MODEL_PATH:-/models")
        assert vlm_env["MMPROJ_PATH"].startswith("${VLM_MMPROJ_PATH:-/models")
        assert vlm_env["MODEL_PATH"].endswith(".gguf}")
        assert vlm_env["MMPROJ_PATH"].endswith(".gguf}")

    def test_weights_never_baked(self, vlm_service: dict) -> None:
        ro = [v for v in vlm_service["volumes"] if v.endswith(":ro")]
        assert any("/models:ro" in v for v in ro), "model root mounts READ-ONLY"
        assert not any(
            line.startswith("COPY") and ".gguf" in line
            for line in DOCKERFILE.read_text(encoding="utf-8").splitlines()
        )

    def test_two_slots_and_context_budget(self, vlm_env: dict) -> None:
        ctx = int(vlm_env["CTX_SIZE"].split(":-")[1].rstrip("}"))
        par = int(vlm_env["PARALLEL"].split(":-")[1].rstrip("}"))
        assert par == 2, "spec §2: 2 slots"
        # per-slot budget >= 4 images (Qwen3-VL <= ~1280 image tokens each)
        # + 6K text + ~1K output = ~12.2K tokens (spec §2 sizing rule)
        assert ctx // par >= 12_288, f"{ctx}/{par} under-provisions a slot"

    def test_sleep_idle_and_alias_reach_the_container(self, vlm_env: dict) -> None:
        # §2 flags; the Dockerfile CMD turns these into --sleep-idle-seconds
        # / --alias conditionally (same guarded-env pattern as MMPROJ_PATH)
        assert vlm_env["SLEEP_IDLE_SECONDS"].startswith("${VLM_SLEEP_IDLE_SECONDS:-")
        assert "MODEL_ALIAS" in vlm_env

    def test_build_is_the_shared_multiarch_dockerfile(self, vlm_service: dict) -> None:
        build = vlm_service["build"]
        assert build["context"] == "./ai/vlm"
        assert build["args"]["CUDA_ARCHITECTURES"] == "${CUDA_ARCHITECTURES:-}"

    def test_gpu_device_interpolation_matches_ai_llm_convention(self, vlm_service: dict) -> None:
        # vlm mode REPLACES the legacy LLM on the GPU (spec VRAM table);
        # same host var, and the stop-ai-llm-first note lives with the service
        assert vlm_service["devices"] == ["nvidia.com/gpu=${GPU_LLM:-0}"]

    def test_healthcheck_targets_8098(self, vlm_service: dict) -> None:
        test = vlm_service["healthcheck"]["test"]
        assert any("http://localhost:8098/health" in part for part in test)


class TestDockerfileFlagWiring:
    """§2 flags that are llama-server args (--sleep-idle-seconds, --alias)
    must be wired through the runtime CMD as guarded env - the file already
    carries --jinja; the pattern must match the existing MMPROJ guard."""

    @pytest.fixture(scope="class")
    def dockerfile(self) -> str:
        return DOCKERFILE.read_text(encoding="utf-8")

    def test_jinja_present(self, dockerfile: str) -> None:
        assert "--jinja" in dockerfile

    def test_sleep_idle_guarded(self, dockerfile: str) -> None:
        assert "SLEEP_IDLE_SECONDS" in dockerfile
        assert "--sleep-idle-seconds" in dockerfile
        # empty env must NOT pass the flag (sleep disabled by default):
        assert re.search(r"SLEEP_IDLE_SECONDS.*!= *\"\"", dockerfile) or re.search(
            r"\[ -n .*SLEEP_IDLE_SECONDS", dockerfile
        )

    def test_alias_guarded(self, dockerfile: str) -> None:
        assert "MODEL_ALIAS" in dockerfile
        assert "--alias" in dockerfile

    def test_arch_stays_build_arg(self, dockerfile: str) -> None:
        assert re.search(r"^ARG CUDA_ARCHITECTURES=", dockerfile, re.M)
        assert "sm_86" in dockerfile or "86" in dockerfile, (
            "1.2 scope call: ONE Dockerfile serves sm_103 aarch64 AND sm_86 "
            "x86 via --build-arg; the file must say so where the ARG lives"
        )


class TestSecurityHardeningParity:
    """ai-vlm joins the hardened set the existing security/resource tests
    sweep (their AI_SERVICES lists carry the rest). Asserted here directly
    so this file is self-contained, too."""

    HARDENED: ClassVar = ("cap_drop", "security_opt", "tmpfs")

    def test_hardening_present(self, vlm_service: dict) -> None:
        for key in self.HARDENED:
            assert key in vlm_service, f"ai-vlm missing {key}"
        assert "no-new-privileges:true" in vlm_service["security_opt"]
        assert "ALL" in vlm_service["cap_drop"]

    def test_no_privileged(self, vlm_service: dict) -> None:
        assert not vlm_service.get("privileged", False)

    def test_resource_limits_present(self, vlm_service: dict) -> None:
        limits = vlm_service["deploy"]["resources"]["limits"]
        assert "cpus" in limits and "memory" in limits
