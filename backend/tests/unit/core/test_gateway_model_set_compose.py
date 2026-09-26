"""Compose wiring for the rev-6 residency selector (Phase 1.4).

The pruning machinery lives in ai/gateway/residency.py (unit-pinned there);
these tests pin only the plumbing that lets an operator SELECT a set on a
real deployment:

1. ``.env.example`` declares GATEWAY_MODEL_SET (root env-first rule: the
   example file is the contract before the compose file reads it).
2. docker-compose.prod.yml passes it into the ai-gateway container with an
   interpolation default — compose `environment:` lists do NOT pass through
   undeclared host variables, so without this entry the variable could only
   reach the container by editing the compose file.

Owner ruling (ledger 1.4, review item 2) executed by Task 5 (1.5): the
GATEWAY_MODEL_SET default in this file and in .env.example flipped to
``vlm`` in the SAME slice that made PIPELINE_MODE default to vlm, and
``test_pipeline_mode_default_agrees_with_the_residency_default`` pins
that the two defaults AGREE — a deployment must never boot the vlm
analyzer against a full-mode gateway (or vice versa). ``full`` is
deleted with R8, when the legacy pipeline goes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load((REPO / "docker-compose.prod.yml").read_text())


@pytest.fixture(scope="module")
def gateway_env(compose: dict) -> dict[str, str]:
    env = compose["services"]["ai-gateway"]["environment"]
    if isinstance(env, list):  # prod compose uses the - KEY=value list style
        out: dict[str, str] = {}
        for item in env:
            key, _, value = item.partition("=")
            out[key] = value
        return out
    return dict(env)


class TestEnvExample:
    def test_gateway_model_set_declared(self) -> None:
        text = (REPO / ".env.example").read_text()
        assert "GATEWAY_MODEL_SET" in text, (
            "env-first rule: the selector must be declared in .env.example "
            "before compose interpolation relies on it"
        )

    def test_declared_value_is_vlm(self) -> None:
        """1.5's flip (owner ruling, ledger 1.4 review item 2): the shipped
        default is now `vlm`, because PIPELINE_MODE's shipped default is
        `vlm` and the vlm path calls nothing else. `full` remains parseable
        for the legacy pipeline until R8 deletes it."""
        text = (REPO / ".env.example").read_text()
        line = next(ln for ln in text.splitlines() if ln.strip().startswith("GATEWAY_MODEL_SET"))
        assert line.split("=", 1)[1].strip() == "vlm"


class TestComposePassesItThrough:
    def test_gateway_env_interpolates_the_selector(self, gateway_env: dict) -> None:
        assert gateway_env.get("GATEWAY_MODEL_SET") == "${GATEWAY_MODEL_SET:-vlm}", (
            "compose must pass the selector with an in-file default; an "
            "undeclared host var never reaches the container"
        )

    def test_pipeline_mode_default_agrees_with_the_residency_default(
        self, compose: dict, gateway_env: dict
    ) -> None:
        """THE 1.5 obligation from the owner ruling on 1.4 (ledger review
        item 2): the two mode defaults must AGREE. A backend built against
        the vlm analyzer while the gateway pruned to `full` (or the reverse)
        is a deployment that boots half-switched, so the pair is pinned as
        one fact, in one test, from the same parse."""
        backend_env = compose["services"]["backend"]["environment"]
        assert "PIPELINE_MODE=${PIPELINE_MODE:-vlm}" in backend_env
        assert gateway_env["GATEWAY_MODEL_SET"].endswith(":-vlm}")
        # And the example file agrees with both in-file defaults:
        text = (REPO / ".env.example").read_text()
        declared = {
            ln.split("=", 1)[0].strip(): ln.split("=", 1)[1].strip()
            for ln in text.splitlines()
            if ln.strip().startswith(("PIPELINE_MODE", "GATEWAY_MODEL_SET"))
        }
        assert declared == {"PIPELINE_MODE": "vlm", "GATEWAY_MODEL_SET": "vlm"}

    def test_threat_opt_in_passes_too(self, gateway_env: dict) -> None:
        assert gateway_env.get("GATEWAY_ENABLE_THREAT") == "${GATEWAY_ENABLE_THREAT:-false}"

    def test_existing_gateway_env_untouched(self, gateway_env: dict) -> None:
        """The residency lines joined, they did not replace: the ports and
        CUDA wiring 1.2/earlier pinned still stand."""
        assert gateway_env["GATEWAY_PORT"] == "8090"
        assert "CUDA_VISIBLE_DEVICES" in gateway_env
