"""The CI notification sinks' overlay and image ([r308a]).

``docker-compose.sinks.yml`` layers a mail sink, a webhook sink and a Web
Push service fake onto the CI stack; ``docker/ci-sinks/Dockerfile`` builds the
one stdlib-only image all three run. These pins hold what the package's box
rests on:

* the overlay is never a default (UR-18): compose loads it only when named
  with ``-f``, and no compose file or env template names it;
* one image runs three services, named and ported for their channel; the
  webhook sink carries the "on this network" marking as a compose label
  (``uplevel.r308a/sink: on-this-network``), fail-closed with the harness's
  render-time check (pinned in ``test_feature_check.py``);
* the image is stdlib-only — the sink installs nothing — so its supply-chain
  surface is the base image alone;
* the backend's sink env is spelled in the overlay, in-network by service DNS
  name; the SMTP shape (``SMTP_USE_TLS=false``) matches the sink's plain
  (no-STARTTLS) surface, which ``test_ci_sink_server.py`` pins;
* the sinks stay out of the fake-AI venue machinery: the prod-shape transform
  injects only the fake-AI bodies (``fake_service_bodies`` filters by name),
  so a sink body never reaches a prod render.

The harness's keep-list and golden-env pins live in ``test_feature_check.py``;
the sink server's wire contract in ``test_ci_sink_server.py``.
"""

from __future__ import annotations

import ast
import base64
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
OVERLAY = REPO_ROOT / "docker-compose.sinks.yml"
CI_STACK = REPO_ROOT / "docker-compose.ci.yml"
PROD = REPO_ROOT / "docker-compose.prod.yml"
DOCKERFILE = REPO_ROOT / "docker/ci-sinks/Dockerfile"
SINK_SERVER = REPO_ROOT / "docker/ci-sinks/sink.py"
SINKS = ("mail-sink", "webhook-sink", "push-sink")

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


class TestTheOverlayIsNeverADefault:
    def test_compose_loads_it_only_when_named(self) -> None:
        defaults = [name for name in _DEFAULT_COMPOSE_NAMES if (REPO_ROOT / name).exists()]

        assert OVERLAY.name not in _DEFAULT_COMPOSE_NAMES
        assert defaults == [], f"compose would load {defaults} with no -f"

    def test_no_compose_file_or_env_template_pulls_it_in(self) -> None:
        """Neither a compose `include:` nor a COMPOSE_FILE default names it.

        Comment lines are stripped before the search: the rule is about
        wiring, and a compose file's own usage example names this overlay in
        prose (this file's header spells the `-f` chain; fake-ai.yml is named
        in our header too). A raw-text pin reds on prose and stops testing
        its rule — the twin pin in test_fake_ai_overlay.py learned this with
        this overlay's arrival.
        """
        sources = [
            *REPO_ROOT.glob("docker-compose*.yml"),
            *REPO_ROOT.glob("config/docker-compose*.yml"),
            REPO_ROOT / ".env.example",
            *REPO_ROOT.glob("env-templates/*"),
        ]
        naming = [
            str(p.relative_to(REPO_ROOT))
            for p in sources
            if p != OVERLAY
            and p.is_file()
            and OVERLAY.name
            in "\n".join(
                line
                for line in p.read_text(encoding="utf-8").splitlines()
                if not line.lstrip().startswith("#")
            )
        ]

        assert naming == []


class TestOneImageThreeSinks:
    def test_all_three_build_the_one_image(self, overlay: dict) -> None:
        builds = {
            name: (
                overlay["services"][name]["build"]["dockerfile"],
                overlay["services"][name]["image"],
            )
            for name in SINKS
        }

        assert set(builds.values()) == {
            ("docker/ci-sinks/Dockerfile", "hsi-ci-sinks:${IMAGE_TAG:-latest}")
        }

    def test_the_webhook_sink_carries_the_on_this_network_label(self, overlay: dict) -> None:
        """The box's marking, spelled where the sink is spelled.

        The harness refuses to render a ``webhook-sink`` without this exact
        label (the fail-closed pair in ``test_feature_check.py``); the label is
        also how B4.2's per-channel local-network flag finds its CI referent.
        """
        assert overlay["services"]["webhook-sink"]["labels"]["uplevel.r308a/sink"] == (
            "on-this-network"
        )

    def test_the_other_sinks_carry_no_marking(self, overlay: dict) -> None:
        """The marking names the webhook channel's allowance only — a marking
        on the mail or push sink would advertise a permission nothing uses."""
        for name in ("mail-sink", "push-sink"):
            labels = overlay["services"][name].get("labels") or {}
            assert "uplevel.r308a/sink" not in labels, (name, labels)

    def test_the_sinks_keep_the_ci_stacks_hardening(self, overlay: dict) -> None:
        for name in SINKS:
            service = overlay["services"][name]
            assert service["cap_drop"] == ["ALL"], name
            assert "no-new-privileges:true" in service["security_opt"], name
            assert service["read_only"] is True, name

    def test_the_sinks_join_only_ci_net(self, overlay: dict) -> None:
        ci_networks = set(yaml.safe_load(CI_STACK.read_text(encoding="utf-8"))["networks"])
        prod_networks = set(yaml.safe_load(PROD.read_text(encoding="utf-8")).get("networks") or {})

        for name in SINKS:
            joined = set(overlay["services"][name]["networks"])
            assert joined <= ci_networks, name
            assert not joined & prod_networks, name

    def test_the_sinks_publish_only_to_loopback(self, overlay: dict) -> None:
        for name in SINKS:
            for port in overlay["services"][name].get("ports") or []:
                assert port.startswith("127.0.0.1:"), (name, port)

    def test_the_sinks_declare_healthchecks(self, overlay: dict) -> None:
        for name in SINKS:
            healthcheck = overlay["services"][name]["healthcheck"]
            assert healthcheck["test"][0] == "CMD-SHELL", name
            assert "/health" in healthcheck["test"][1], name


class TestTheBackendEnv:
    def test_the_backend_env_names_the_sinks(self, overlay: dict) -> None:
        """The backend's sink env is spelled in the overlay, in-network.

        The golden env re-derives host-side addresses from the published
        ports; this side is the in-network contract the backend container
        dials, and the pair is held together by shared strings the
        ``test_feature_check.py`` pins read off the same names.
        """
        backend = _env(overlay["services"]["backend"])
        assert backend["FEATURE_CHECK_SINKS_MODE"] == "on-this-network"
        assert backend["SMTP_HOST"] == "mail-sink"
        assert backend["SMTP_PORT"] == "8025"
        # The sink advertises no STARTTLS (pinned in test_ci_sink_server.py):
        # a TLS-on backend would die in starttls() against it, loudly, which
        # is the honest shape — so the overlay must say false explicitly.
        assert backend["SMTP_USE_TLS"] == "false"
        assert backend["SMTP_FROM_ADDRESS"] == "alerts@nemotron.test"
        # list[str] field: the env form is JSON, what pydantic-settings parses.
        assert backend["DEFAULT_EMAIL_RECIPIENTS"] == '["sinks@nemotron.test"]'
        assert backend["FEATURE_CHECK_SINK_WEBHOOK_HOST"] == "webhook-sink:8091"
        assert backend["FEATURE_CHECK_SINK_PUSH_HOST"] == "push-sink:8092"

    def test_the_golden_env_exports_both_in_network_hosts(self) -> None:
        """Both in-network hosts reach the golden env, read off the render.

        The webhook leg (r308a) dials ``FEATURE_CHECK_SINK_WEBHOOK_HOST``; the
        push leg (B4.3) registers a subscription aimed at
        ``FEATURE_CHECK_SINK_PUSH_HOST``. Both exports read the rendered
        compose.json in ``feature_check.py`` (``_sink_env_host``) — the same
        document compose consumes — so a rename here and the leg's env move
        together or the harness refuses loudly.
        """
        harness = (REPO_ROOT / "scripts" / "feature_check.py").read_text(encoding="utf-8")
        assert '_sink_env_host("FEATURE_CHECK_SINK_WEBHOOK_HOST")' in harness
        assert '_sink_env_host("FEATURE_CHECK_SINK_PUSH_HOST")' in harness
        assert 'env["FEATURE_CHECK_SINK_PUSH_HOST"] = self._sink_push_host()' in harness

    def test_the_backend_env_names_a_fixed_test_vapid_pair(self, overlay: dict) -> None:
        """The Web Push VAPID env opens the adapter's fail-closed gate (B4.3).

        The adapter returns ``webpush_not_configured`` when
        ``settings.vapid_private_key`` is None (``webpush.py``), so without
        these keys every send would fail closed in the fake stack and B4.3's
        golden leg would have nothing to prove. Production generates a
        per-install pair at setup (``setup_lib/credentials.py`` writes
        ``VAPID_PRIVATE_KEY``/``VAPID_PUBLIC_KEY`` to ``.env``); the overlay
        carries a fixed TEST-ONLY pair — the same doctrine ``ci_test_password``
        holds for Postgres. The pin is structural, not byte-precise: the value
        must load as a PKCS8 private key whose derived public key equals the
        committed one (a mistyped half-pair is the failure mode that would
        otherwise surface only as a 4xx from the push fake).
        """
        backend = _env(overlay["services"]["backend"])
        private_b64 = backend["VAPID_PRIVATE_KEY"]
        public_b64 = backend["VAPID_PUBLIC_KEY"]

        from cryptography.hazmat.primitives import serialization

        key = serialization.load_der_private_key(
            base64.urlsafe_b64decode(private_b64 + "=" * (-len(private_b64) % 4)),
            password=None,
        )
        derived = base64.urlsafe_b64encode(
            key.public_key().public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint,
            )
        ).rstrip(b"=")
        assert derived == public_b64.encode()

    def test_the_backend_starts_after_the_sinks_are_healthy(self, overlay: dict) -> None:
        depends = overlay["services"]["backend"]["depends_on"]

        for name in SINKS:
            assert depends[name] == {"condition": "service_healthy"}
            assert overlay["services"][name]["healthcheck"]["test"][0] == "CMD-SHELL"

    def test_the_smtp_port_matches_the_config_default_range(self, overlay: dict) -> None:
        """smtp_port is Field(ge=1, le=65535); the sink serves 8025.

        Pinned against the Settings field the env sets, so a renumber here and
        a re-pin there cannot drift: if the sink moves, this and the
        config-side range move in one PR or not at all.
        """
        config = (REPO_ROOT / "backend/core/config.py").read_text(encoding="utf-8")
        port_field = re.search(
            r"smtp_port: int = Field\(\s*default=(\d+),\s*ge=(\d+),\s*le=(\d+)", config
        )
        assert port_field is not None, "the smtp_port Field moved; re-pin this"
        # The pin is the range: the sink's 8025 must be a port the Settings
        # field accepts (and the field's default of 587 must stay far from
        # it, so a TLS-on default would visibly fail against this sink).
        assert int(port_field.group(2)) <= 8025 <= int(port_field.group(3))
        assert port_field.group(1) != "8025", "the default must not silently become the sink port"


class TestTheImage:
    def test_it_installs_nothing(self) -> None:
        """The sink is stdlib-only Python; nothing reaches pip.

        Pinned as the absence of every pip install line (comment lines
        stripped — this file's own comments say "pip install", which is prose,
        not an install). A dependency that appears would need its own pin
        discipline (the uv.lock closure the fake-AI image carries), which is
        not this image's story.
        """
        text = DOCKERFILE.read_text(encoding="utf-8")
        code_lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
        pip_lines = [line for line in code_lines if "pip" in line and "install" in line]
        assert pip_lines == [], pip_lines

    def test_it_runs_the_checkouts_sink_server(self) -> None:
        text = DOCKERFILE.read_text(encoding="utf-8")

        assert re.search(r"^COPY docker/ci-sinks/sink\.py", text, re.MULTILINE), text
        assert re.search(r"^ENTRYPOINT", text, re.MULTILINE), text

    def test_the_sink_server_is_stdlib_only(self) -> None:
        """The imports the server makes are stdlib imports, measured by AST.

        Pinned as the import set, not as a vague "no third-party" — a new
        import names itself here.
        """
        tree = ast.parse(SINK_SERVER.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add((node.module or "").split(".")[0])
        assert imported <= set(sys.stdlib_module_names), imported - set(sys.stdlib_module_names)

    def test_the_sink_server_writes_only_under_its_data_dir(self) -> None:
        """``read_only: true`` — the server may write only under /data.

        Pinned on the source: every filesystem write the server performs goes
        under the ``SINK_DATA_DIR`` env the overlay sets (a tmpfs), so a new
        write target outside it names itself here.
        """
        text = SINK_SERVER.read_text(encoding="utf-8")
        assert "SINK_DATA_DIR" in text, "the server lost its only-writable-root contract"
