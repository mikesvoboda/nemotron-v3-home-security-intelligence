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

The interpolation default is ``full``, same as the module's own default:
this slice changes nobody's footprint. Owner ruling (ledger 1.4, review
item 2): Task 5 (1.5) switches the GATEWAY_MODEL_SET default in THIS file
and in .env.example to ``vlm`` in the SAME slice that makes PIPELINE_MODE
default to vlm, and adds a test that the two defaults agree — a deployment
must never boot the vlm analyzer against a full-mode gateway (or vice
versa). ``full`` is deleted with R8, when the legacy pipeline goes.
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

    def test_declared_value_is_full(self) -> None:
        """The example ships the behavior-preserving default; vlm is an
        explicit A5500-era selection (1.7 handout)."""
        text = (REPO / ".env.example").read_text()
        line = next(ln for ln in text.splitlines() if ln.strip().startswith("GATEWAY_MODEL_SET"))
        assert line.split("=", 1)[1].strip() == "full"


class TestComposePassesItThrough:
    def test_gateway_env_interpolates_the_selector(self, gateway_env: dict) -> None:
        assert gateway_env.get("GATEWAY_MODEL_SET") == "${GATEWAY_MODEL_SET:-full}", (
            "compose must pass the selector with an in-file default; an "
            "undeclared host var never reaches the container"
        )

    def test_threat_opt_in_passes_too(self, gateway_env: dict) -> None:
        assert gateway_env.get("GATEWAY_ENABLE_THREAT") == "${GATEWAY_ENABLE_THREAT:-false}"

    def test_existing_gateway_env_untouched(self, gateway_env: dict) -> None:
        """The residency lines joined, they did not replace: the ports and
        CUDA wiring 1.2/earlier pinned still stand."""
        assert gateway_env["GATEWAY_PORT"] == "8090"
        assert "CUDA_VISIBLE_DEVICES" in gateway_env
