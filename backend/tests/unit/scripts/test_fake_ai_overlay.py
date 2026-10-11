"""The fake AI stack's overlay and image (O2.1).

``docker-compose.fake-ai.yml`` layers the deterministic fake VLM and fake
detector onto the CI stack; ``docker/fake-ai/Dockerfile`` builds the image both
run. These pins hold what the package's text and its two DECIDEs rest on:

* the overlay is never a default (UR-18): compose loads it only when it is
  named with ``-f``;
* one image runs as two services named and numbered like prod's, so stopping
  ``ai-vlm`` takes the verdict engine down alone, and the backend's AI
  environment is prod's;
* the backend's build pin and the build the fake reports are one value, the
  llama.cpp build ``ai/vlm/Dockerfile`` serves, so the startup gate's build
  check runs instead of being skipped;
* the image pins ``jsonschema`` to ``uv.lock`` and does not wait for a database.

The stack itself (boot, startup gates, a dropped image scored) is shown with
commands and output on the PR; the in-process halves are pinned in
``backend/tests/contracts/ai_providers/test_fake_ai_stack.py``.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
OVERLAY = REPO_ROOT / "docker-compose.fake-ai.yml"
CI_STACK = REPO_ROOT / "docker-compose.ci.yml"
PROD = REPO_ROOT / "docker-compose.prod.yml"
DOCKERFILE = REPO_ROOT / "docker/fake-ai/Dockerfile"
FAKES = ("ai-vlm", "ai-gateway")

# The file names `docker compose` loads with no -f (compose-spec: compose.yaml
# and its .yml / docker-compose.* spellings, each with its .override twin).
_DEFAULT_COMPOSE_NAMES = tuple(
    f"{stem}{override}.{ext}"
    for stem in ("compose", "docker-compose")
    for override in ("", ".override")
    for ext in ("yaml", "yml")
)


@pytest.fixture(scope="module")
def overlay() -> dict:
    return yaml.safe_load(OVERLAY.read_text(encoding="utf-8"))


def _env(service: dict) -> dict[str, str]:
    out = {}
    for entry in service.get("environment") or []:
        key, _, value = str(entry).partition("=")
        out[key] = value
    return out


def _port(service: dict) -> str:
    command = service["command"]
    return command[command.index("--port") + 1]


class TestTheOverlayIsNeverADefault:
    def test_compose_loads_it_only_when_named(self) -> None:
        defaults = [name for name in _DEFAULT_COMPOSE_NAMES if (REPO_ROOT / name).exists()]

        assert OVERLAY.name not in _DEFAULT_COMPOSE_NAMES
        assert defaults == [], f"compose would load {defaults} with no -f"

    def test_no_compose_file_or_env_template_pulls_it_in(self) -> None:
        """Neither a compose `include:` nor a COMPOSE_FILE default names it."""
        sources = [
            *REPO_ROOT.glob("docker-compose*.yml"),
            *REPO_ROOT.glob("config/docker-compose*.yml"),
            REPO_ROOT / ".env.example",
            *REPO_ROOT.glob("env-templates/*"),
        ]
        naming = [
            str(p.relative_to(REPO_ROOT))
            for p in sources
            if p != OVERLAY and p.is_file() and OVERLAY.name in p.read_text(encoding="utf-8")
        ]

        assert naming == []

    def test_it_joins_only_the_ci_stacks_network(self, overlay: dict) -> None:
        """Layered on another base (prod names the same two services, as GPU
        services) the undeclared network makes compose refuse to render."""
        ci_networks = set(yaml.safe_load(CI_STACK.read_text(encoding="utf-8"))["networks"])
        prod_networks = set(yaml.safe_load(PROD.read_text(encoding="utf-8")).get("networks") or {})

        for name in FAKES:
            joined = set(overlay["services"][name]["networks"])
            assert joined <= ci_networks, name
            assert not joined & prod_networks, name


class TestOneImageTwoServices:
    def test_both_fakes_build_the_one_image(self, overlay: dict) -> None:
        builds = {
            name: (
                overlay["services"][name]["build"]["dockerfile"],
                overlay["services"][name]["image"],
            )
            for name in FAKES
        }

        assert set(builds.values()) == {
            ("docker/fake-ai/Dockerfile", "hsi-fake-ai:${IMAGE_TAG:-latest}")
        }

    def test_names_and_ports_mirror_prod(self, overlay: dict) -> None:
        """The backend dials the fakes at prod's own URLs."""
        backend = _env(overlay["services"]["backend"])
        prod_backend = _env(yaml.safe_load(PROD.read_text(encoding="utf-8"))["services"]["backend"])

        assert _port(overlay["services"]["ai-vlm"]) == "8098"
        assert _port(overlay["services"]["ai-gateway"]) == "8090"
        assert backend["AI_VLM_URL"] == "http://ai-vlm:8098"
        assert prod_backend["AI_VLM_URL"] == "${AI_VLM_URL:-http://ai-vlm:8098}"
        for key in ("USE_AI_GATEWAY", "AI_GATEWAY_URL", "YOLO26_URL", "ENRICHMENT_LIGHT_URL"):
            assert backend[key] == prod_backend[key], key

    def test_the_backend_starts_after_both_fakes_are_healthy(self, overlay: dict) -> None:
        depends = overlay["services"]["backend"]["depends_on"]

        for name in FAKES:
            assert depends[name] == {"condition": "service_healthy"}
            assert overlay["services"][name]["healthcheck"]["test"][0] == "CMD"

    def test_the_fakes_keep_the_ci_stacks_hardening(self, overlay: dict) -> None:
        for name in FAKES:
            service = overlay["services"][name]
            assert service["cap_drop"] == ["ALL"], name
            assert "no-new-privileges:true" in service["security_opt"], name
            assert service["read_only"] is True, name


class TestTheBuildPinIsOneValue:
    def test_the_backend_pin_and_the_fakes_build_share_one_default(self, overlay: dict) -> None:
        llama_ref = re.search(
            r"^ARG LLAMA_CPP_REF=(\S+)$",
            (REPO_ROOT / "ai/vlm/Dockerfile").read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        assert llama_ref is not None
        pin = f"${{VLM_REQUIRED_BUILD:-{llama_ref.group(1)}}}"

        assert _env(overlay["services"]["backend"])["VLM_REQUIRED_BUILD"] == pin
        assert _env(overlay["services"]["backend"])["VLM_ENFORCEMENT_PROBE_ENABLED"] == "true"
        for name in FAKES:
            assert _env(overlay["services"][name])["FAKE_VLM_BUILD_INFO"] == f"{pin}-fake-ai"


class TestTheImage:
    def test_jsonschema_is_pinned_to_the_lock(self) -> None:
        """The fake validates every reply; only uv.lock's test group installs
        jsonschema, so the image installs the locked closure itself."""
        locked = {
            p["name"]: p["version"]
            for p in tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))["package"]
        }
        pins = dict(
            re.findall(r"\b([a-z][a-z0-9-]*)==(\S+)", DOCKERFILE.read_text(encoding="utf-8"))
        )

        assert "jsonschema" in pins
        assert pins == {name: locked[name] for name in pins}

    def test_it_does_not_wait_for_a_database(self) -> None:
        """The backend image's entrypoint waits for Postgres; the fake has none."""
        text = DOCKERFILE.read_text(encoding="utf-8")

        assert re.search(r"^ENTRYPOINT \[\]$", text, re.MULTILINE)
        assert "backend.ai_contract.fake.app:create_served_app" in text

    def test_it_runs_the_checkouts_fake(self) -> None:
        assert re.search(
            r"^COPY .*backend/ /app/backend/$", DOCKERFILE.read_text(encoding="utf-8"), re.MULTILINE
        )
