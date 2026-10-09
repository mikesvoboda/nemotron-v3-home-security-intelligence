"""O1.11: monitoring behind the gate (UR-33) — the machine callers get a credential.

With ``EXPOSE_LAN=true`` the B1.5 gate refuses every request that carries no
credential (``backend/api/middleware/auth.py``); its own comment names this
package: *"O1.11 gives Prometheus, Alertmanager and Grafana a credential."*
This file pins the delivered shape, each fact read from the pinned containers
before it was asserted (probe evidence in PR #6930's ready-mark):

- one machine key (``MONITORING_API_KEY``, a ``settings.api_keys`` member via
  the ``API_KEYS`` env — the form B1.5's ``X-API-Key`` header takes);
- Prometheus sends it as a header on ``/api/metrics`` scrapes (Prometheus
  expands nothing — probe: it sent ``$MON_KEY`` literally — so the committed
  config carries a render placeholder and the service renders it at boot);
- Alertmanager cannot send ``X-API-Key`` at all (no version supports it —
  probes v0.27.0/v0.28.x/v0.29.0/v0.34.1 all reject ``http_headers``), so its
  webhook rides an unpublished frontend machine listener that injects the key;
- Grafana's Backend-API datasource carries it via core-level
  ``httpHeaderName1``/``secureJsonData`` — Grafana expands ``$VAR`` natively
  (probe: the backend echo received ``X-API-Key: grafana-LITVAL``);
- exposed ``/grafana/`` dies with anonymous Admin and lives behind the app
  session (``auth_request`` to ``/api/auth/me`` + auth-proxy), the spec's
  recorded DECIDE; the default render stays byte-identical to today's.

Sibling precedents: test_frontend_expose_lan_bind.py (O1.6 derivation +
compose-render idioms), test_nginx_credential_forwarding.py (brace parser for
the entrypoint-rendered config).
"""

# ruff: noqa: S108  — the /tmp paths below are asserted compose mounts, not
# scratch files this test writes (the S104 analog: test_frontend_expose_lan_bind.py:1).
from __future__ import annotations

import importlib
import re
import shutil
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_FILE = REPO_ROOT / "docker-compose.prod.yml"
# Committed render-env stubs for the compose file's two ${VAR:?} hard-required
# vars (the test_frontend_expose_lan_bind.py fixture — `compose config` needs
# them to interpolate the whole file).
RENDER_ENV_FIXTURE = REPO_ROOT / "backend/tests/fixtures/compose-render.env"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
PROM_CONFIG = REPO_ROOT / "monitoring" / "prometheus.yml"
ALERTMANAGER_CONFIG = REPO_ROOT / "monitoring" / "alertmanager.yml"
DATASOURCES = (
    REPO_ROOT / "monitoring" / "grafana" / "provisioning" / "datasources" / "prometheus.yml"
)
ENTRYPOINT = REPO_ROOT / "frontend" / "docker-entrypoint.sh"
SETUP_PY = REPO_ROOT / "setup.py"

# The render placeholders the boot renderers substitute. Deliberately inert in
# every config language here (a YAML scalar; no regex/significance), so an
# un-rendered config fails LOUD (401/404) rather than silently working.
KEY_PLACEHOLDER = "__HSI_MONITORING_API_KEY__"
SINK_PLACEHOLDER = "__HSI_ALERT_SINK__"
DEFAULT_SINK = "http://backend:8000/api/webhooks/alerts"

MACHINE_DEFAULT_MODE_ENV: dict[str, str] = {}


class _ComposeLoader(yaml.SafeLoader):
    """safe_load that also reads compose's merge tags (!override, !reset)."""


def _construct_compose_tag(loader: yaml.SafeLoader, _suffix: str, node: yaml.Node) -> object:
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_scalar(node)  # type: ignore[arg-type]


_ComposeLoader.add_multi_constructor("!", _construct_compose_tag)


def _text(path: Path) -> str:
    assert path.exists(), f"missing {path}"
    return path.read_text()


def _setup_fn(name: str):
    """Fetch a setup_lib.core function, FAILING (not skipping) when absent.

    The O1.6 sibling imports its derive inside the test; the same shape here,
    but an unimplemented O1.11 derivation must read as a red test, never a
    skip or a collection error.
    """
    try:
        core = importlib.import_module("setup_lib.core")
    except ImportError as exc:  # pragma: no cover — repo root is on sys.path
        pytest.fail(f"setup_lib.core unimportable: {exc}")
    fn = getattr(core, name, None)
    if fn is None:
        pytest.fail(f"setup_lib.core.{name} missing — O1.11 derivation not implemented")
    return fn


# ---------------------------------------------------------------------------
# The derivations: one flag, one vocabulary (same truthy set the bind derive
# and pydantic use), fail-safe toward the DEFAULT (un-exposed) mode.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "anonymous", "auth_proxy"),
    [
        ("", "true", "false"),  # unset: today's behavior
        ("false", "true", "false"),
        ("no", "true", "false"),
        ("banana", "true", "false"),  # fail-safe, like the bind derive
        ("true", "false", "true"),
        ("TRUE", "false", "true"),  # pydantic is case-insensitive
        ("yes", "false", "true"),
        ("on", "false", "true"),
        ("1", "false", "true"),
    ],
)
def test_grafana_mode_derivations(value: str, anonymous: str, auth_proxy: str) -> None:
    """EXPOSE_LAN flips anonymous Admin off and auth-proxy on — never both ways."""
    assert _setup_fn("derive_grafana_anonymous_enabled")(value) == anonymous
    assert _setup_fn("derive_grafana_auth_proxy_enabled")(value) == auth_proxy


# ---------------------------------------------------------------------------
# .env + setup.py: the key is generated, written to the env file, never
# committed. It exists in BOTH modes so flipping EXPOSE_LAN later never
# strands a stack on an empty key (the gate simply doesn't check it until
# exposed) — and it revives machine callers on /api/webhooks/alerts today.
# ---------------------------------------------------------------------------


def test_setup_writes_monitoring_key_into_generated_env() -> None:
    setup_src = _text(SETUP_PY)
    region = setup_src[setup_src.index("FRONTEND_BIND_ADDRESS=") - 2000 :][:4000]
    assert "MONITORING_API_KEY=" in region, (
        "setup.py's generated .env must carry MONITORING_API_KEY= beside the "
        "O1.6 EXPOSE_LAN/FRONTEND_BIND_ADDRESS block"
    )
    assert "API_KEYS=" in region, (
        "the same .env must mirror it into API_KEYS (JSON list) — the backend "
        "container reads neither file unless compose passes them (see compose tests)"
    )
    assert "derive_grafana_anonymous_enabled(" in setup_src
    assert "derive_grafana_auth_proxy_enabled(" in setup_src


def test_generated_env_carries_key_and_derived_mode_lines() -> None:
    """End-to-end through the real generator (the region test above only
    proves the literals exist; this proves what setup.py WRITES, both modes).
    API_KEYS is json.dumps([key]) — the form pydantic parses; the key itself
    is hsi_+token_urlsafe, whose alphabet is JSON- and shell-safe."""
    import setup

    base = {"monitoring_api_key": "hsi_TESTKEY123"}  # pragma: allowlist secret
    exposed = setup.generate_env_content({**base, "expose_lan": True})
    unexposed = setup.generate_env_content({**base, "expose_lan": False})
    for content in (exposed, unexposed):
        assert "MONITORING_API_KEY=hsi_TESTKEY123" in content
        assert 'API_KEYS=["hsi_TESTKEY123"]' in content, (
            "the key mirrors into API_KEYS in BOTH modes"
        )
    assert "GRAFANA_ANONYMOUS_ENABLED=false" in exposed
    assert "GRAFANA_AUTH_PROXY_ENABLED=true" in exposed
    assert "ALERT_SINK_URL=http://frontend:8081/api/webhooks/alerts" in exposed
    assert "GRAFANA_ANONYMOUS_ENABLED=true" in unexposed
    assert "GRAFANA_AUTH_PROXY_ENABLED=false" in unexposed
    assert "ALERT_SINK_URL=http://backend:8000/api/webhooks/alerts" in unexposed


def test_env_documents_the_machine_key() -> None:
    example = _text(ENV_EXAMPLE)
    assert "MONITORING_API_KEY" in example, (
        ".env.example must document the key: setup.py-generated, lives only "
        "in .env, never committed (spec: 'read from the env file and never committed')"
    )


# ---------------------------------------------------------------------------
# docker-compose.prod.yml: the plumbing. Every default keeps today's behavior
# (fail-safe :- defaults at BOTH ends, the O1.6 doctrine); the exposed mode
# arrives purely through values setup.py writes.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def compose_text() -> str:
    return _text(COMPOSE_FILE)


@pytest.fixture(scope="module")
def compose_services() -> dict:
    # _ComposeLoader IS a SafeLoader: it only adds plain-node reads of compose's
    # !override/!reset tags — the loader from test_frontend_expose_lan_bind.py.
    text = _text(COMPOSE_FILE)
    return yaml.load(text, Loader=_ComposeLoader)["services"]  # noqa: S506  # nosemgrep: unsafe-yaml-load


def _env_lines(service: dict) -> list[str]:
    env = service.get("environment") or []
    if isinstance(env, dict):
        return [f"{k}={v}" for k, v in env.items()]
    return list(env)


def test_backend_env_receives_the_api_keys(compose_text: str, compose_services: dict) -> None:
    """Settings.api_keys is read from the process env; today NO container gets it.

    (compose at HEAD carries zero API_KEY lines and the backend has no
    env_file:/env_file:.env mount — the env-gated machine path B1.5 built is
    unreachable in-container today. O1.11 wires it; fail-safe ``[]`` default.)
    """
    lines = _env_lines(compose_services["backend"])
    assert "API_KEYS=${API_KEYS:-[]}" in lines


def test_prometheus_sends_the_key_and_renders_it(compose_services: dict) -> None:
    """Prometheus expands NOTHING in its config (probe: sent ``$MON_KEY``
    literally over the wire), so the key reaches the scrape through a boot
    render of the committed placeholder into the service's writable tmpfs."""
    prom = compose_services["prometheus"]
    lines = _env_lines(prom)
    assert "MONITORING_API_KEY=${MONITORING_API_KEY:-}" in lines
    command = " ".join(prom.get("command") or [])
    assert KEY_PLACEHOLDER in command, "prometheus must render the committed placeholder at boot"
    assert "/tmp/prometheus.yml" in command, "render into tmpfs — the root filesystem is read_only"
    assert "--config.file=/tmp/prometheus.yml" in command
    assert "/tmp" in (prom.get("tmpfs") or []), (
        "prometheus needs a writable /tmp (read_only rootfs)"
    )


def test_alertmanager_routes_its_webhook_through_the_frontend(compose_services: dict) -> None:
    """No Alertmanager version can attach X-API-Key (probe: http_headers
    rejected by amtool 0.27.0→0.34.1; only basic_auth/bearer exist). The
    credential therefore joins at the frontend's unpublished machine
    listener; AM's sink becomes a render placeholder whose DEFAULT is today's
    direct backend URL — the default render stays what runs today."""
    am = compose_services["alertmanager"]
    lines = _env_lines(am)
    assert any(line.startswith("ALERT_SINK_URL=") for line in lines)
    sink_line = next(line for line in lines if line.startswith("ALERT_SINK_URL="))
    assert sink_line == f"ALERT_SINK_URL=${{ALERT_SINK_URL:-{DEFAULT_SINK}}}", (
        "the sink default must keep today's direct backend URL (default mode unchanged)"
    )
    command = " ".join(am.get("command") or [])
    assert SINK_PLACEHOLDER in command, "alertmanager must render the committed sink placeholder"
    assert "--config.file=/tmp/alertmanager.yml" in command
    assert "/tmp" in str(am.get("tmpfs") or ""), (
        "alertmanager needs a writable /tmp (read_only rootfs)"
    )


def test_grafana_gets_the_key_and_the_mode_flips(compose_services: dict) -> None:
    """Grafana expands $VAR natively (probe) — no render needed for the
    datasource leg. Anonymous Admin must become setup-derivable so exposure
    kills it while the unset default renders exactly today's ``true``."""
    graf = compose_services["grafana"]
    lines = _env_lines(graf)
    assert "MONITORING_API_KEY=${MONITORING_API_KEY:-}" in lines
    # Nested default (the precedence test below pins why): the OUTER key keeps
    # its own name so a legacy hand-set false is never resurrected, while
    # setup.py's derived GRAFANA_ANONYMOUS_ENABLED channel still wins when set.
    assert (
        "GF_AUTH_ANONYMOUS_ENABLED=${GF_AUTH_ANONYMOUS_ENABLED:-${GRAFANA_ANONYMOUS_ENABLED:-true}}"
        in lines
    ), (
        "anonymous Admin becomes derivable; the :-true default keeps today's "
        "behavior and the self-referencing outer key keeps the LEGACY false"
    )
    assert "GF_AUTH_PROXY_ENABLED=${GRAFANA_AUTH_PROXY_ENABLED:-false}" in lines
    assert "GF_AUTH_PROXY_HEADER_NAME=X-Auth-User" in lines
    assert "GF_AUTH_PROXY_AUTO_SIGN_UP=${GRAFANA_AUTH_PROXY_AUTO_SIGN_UP:-false}" in lines
    # The exposed-mode identity is a Viewer, never an Admin: either the role is
    # pinned here, or it is pinned in the entrypoint's rendered auth-proxy pair.
    joined = "\n".join(lines) + _text(ENTRYPOINT)
    assert re.search(r"GF_AUTH_PROXY_ORG_ROLE\s*=\s*Viewer", joined) or re.search(
        r"GF_AUTH_PROXY_AUTO_SIGN_UP_ORG_ROLE\s*=\s*Viewer", joined
    ), "auth-proxy auto-sign-up must land on Viewer, not Admin"


# ---------------------------------------------------------------------------
# The committed configs: placeholders and the datasource header.
# ---------------------------------------------------------------------------


def test_prometheus_backend_job_carries_the_header_placeholder() -> None:
    """The scrape leg's header, in the only schema Prometheus 3.1 accepts
    (probe: map/seq/value forms all fail to unmarshal; Header is {values:[...]}).
    A non-loopback target list keeps today's semantics: backend:8000."""
    text = _text(PROM_CONFIG)
    job = text[text.index("hsi-backend-metrics") :]
    job = job[: job.index("- job_name", 10)] if "- job_name" in job[10:] else job
    assert "http_headers" in job
    assert "X-API-Key" in job
    assert KEY_PLACEHOLDER in job, (
        f"the committed config carries {KEY_PLACEHOLDER}; the boot render "
        "substitutes the env key (Prometheus expands nothing itself)"
    )


def test_alertmanager_config_sinks_to_the_placeholder() -> None:
    """Every webhook sink renders; the default-mode render is byte-equivalent
    to today's direct backend URLs."""
    text = _text(ALERTMANAGER_CONFIG)
    assert DEFAULT_SINK not in text, (
        "literal backend sinks bypass the machine listener that injects the key"
    )
    assert SINK_PLACEHOLDER in text


def test_backend_api_datasource_carries_the_key_via_grafana_core() -> None:
    text = _text(DATASOURCES)
    # Anchor on the datasource ENTRY (not the bare name — the file header
    # note added by O1.11 mentions it too).
    ds = text[text.index("- name: Backend-API") :]
    ds = ds[: ds.index("\n  #") :] if "\n  #" in ds[10:] else ds
    assert "httpHeaderName1" in ds and "X-API-Key" in ds
    assert "secureJsonData" in ds
    assert "$MONITORING_API_KEY" in ds, (
        "Grafana expands $VAR in provisioning and sends core-level headers on "
        "datasource-proxy requests (probe: backend echo received grafana-LITVAL)"
    )


# ---------------------------------------------------------------------------
# The render precedence the composed line must keep (upgrade safety): the
# anonymous-Admin line GAINS a derived channel without losing the hand-set
# one, so a user who already set GF_AUTH_ANONYMOUS_ENABLED=false in .env is
# never silently handed anonymous Admin back by a setup.py run. The nested
# ${OUTER:-${INNER:-true}} grammar renders under compose v5.5.1 (probed) —
# asserted against the real binary when one exists, and against a two-level
# emulator otherwise (skip-free, the test_frontend_expose_lan_bind.py
# strategy; a one-level emulator would disagree with the binary on exactly
# this line, so the recursion is pinned by a pin-test below).
# ---------------------------------------------------------------------------

_RENDER_OWNED_VARS = frozenset(
    {
        "EXPOSE_LAN",
        "MONITORING_API_KEY",
        "API_KEYS",
        "ALERT_SINK_URL",
        "GF_AUTH_ANONYMOUS_ENABLED",
        "GRAFANA_ANONYMOUS_ENABLED",
        "GRAFANA_AUTH_PROXY_ENABLED",
        "GRAFANA_AUTH_PROXY_AUTO_SIGN_UP",
        "PODMAN_SOCKET",
    }
)

# One ${VAR:-default}, whose default may itself be ${…} (the nested form).
_NESTED_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-((?:[^{}]|\$\{[^{}]*\})*))?\}")
# NOTE the trailing \}: without it the scanner stops one brace early on the
# nested form (the inner default owns the first }), leaving a stray "}" —
# exactly what the pin-test's first assert caught.


def _interpolate(value: str, env: dict[str, str]) -> str:
    """${VAR:-default} grammar, two levels deep (what compose does here).

    Like the O1.6 sibling's one-level emulator, but the nested default is the
    point of the line under test; compose treats an EMPTY value like an unset
    one for :- defaults (probed against docker compose config v5.5.1).
    """

    def sub(m: re.Match[str]) -> str:
        current = env.get(m.group(1), "")
        if current == "" and m.group(2) is not None:
            return _interpolate(m.group(2), env)
        return current

    return _NESTED_VAR_RE.sub(sub, value)


def test_nested_interpolator_agrees_with_compose() -> None:
    """Pin the emulator on the exact cases the precedence test leans on.

    (Mirror of the sibling's test_binding_helpers_are_pinned: when the real
    binary is absent, the emulator is the test — so its nested semantics are
    asserted here, not assumed.)
    """
    line = "${GF_AUTH_ANONYMOUS_ENABLED:-${GRAFANA_ANONYMOUS_ENABLED:-true}}"
    assert _interpolate(line, {}) == "true"
    assert _interpolate(line, {"GF_AUTH_ANONYMOUS_ENABLED": "false"}) == "false"
    assert _interpolate(line, {"GRAFANA_ANONYMOUS_ENABLED": "false"}) == "false"
    # NOTE (pre-implementation test correction, measured against the real
    # compose v5.5.1 binary, this repo): ${A:-${B:-c}} consults the INNER
    # default only when A is unset/empty — an explicitly hand-set legacy
    # value WINS over the derived channel. An earlier revision of this line
    # asserted the derived channel wins, which the binary contradicts. The
    # security-relevant direction is the one that holds: a legacy "false"
    # can never be flipped back ON by an upgrade (see the line above this
    # block); the conflict case is an explicit opt-out, and the mode-gated
    # nginx auth_request fronts /grafana/ independently of this flag.
    assert (
        _interpolate(
            line, {"GF_AUTH_ANONYMOUS_ENABLED": "true", "GRAFANA_ANONYMOUS_ENABLED": "false"}
        )
        == "true"
    )
    # EMPTY counts as unset (compose's :- grammar), including for the inner default
    assert (
        _interpolate(line, {"GF_AUTH_ANONYMOUS_ENABLED": "", "GRAFANA_ANONYMOUS_ENABLED": ""})
        == "true"
    )


def _compose_argv() -> list[str] | None:
    """First runnable compose invocation (test_frontend_expose_lan_bind.py::_compose_argv)."""
    if shutil.which("podman"):
        return ["podman", "compose"]
    if shutil.which("docker"):
        return ["docker", "compose"]
    for binary in ("podman-compose", "docker-compose"):
        if shutil.which(binary):
            return [binary]
    return None


def _render_env_lines(service: str, env_overrides: dict[str, str]) -> list[str]:
    """One service's rendered environment under an overlay: real compose when
    a binary exists, the two-level emulator otherwise. Skip-free both ways."""
    env: dict[str, str] = {}
    with RENDER_ENV_FIXTURE.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env.setdefault(k, v)
    env.update({k: v for k, v in env_overrides.items() if v is not None})
    env.update({k: "" for k, v in env_overrides.items() if v is None})

    argv = _compose_argv()
    if argv is not None:
        import json as _json
        import os
        import subprocess

        proc_env = {k: v for k, v in os.environ.items() if k not in _RENDER_OWNED_VARS}
        proc_env.update(env)
        result = subprocess.run(  # noqa: S603 — argv is a literal list  # real
            [
                *argv,
                "--env-file",
                str(RENDER_ENV_FIXTURE),
                "-f",
                str(COMPOSE_FILE),
                "config",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=proc_env,
        )
        assert result.returncode == 0, f"compose config failed: {result.stderr[:400]}"
        rendered = _json.loads(result.stdout)
        svc_env = rendered["services"][service].get("environment") or {}
        if isinstance(svc_env, list):  # older schema: ["K=V", …]
            return list(svc_env)
        return [f"{k}={v}" for k, v in svc_env.items()]

    text = _text(COMPOSE_FILE)
    doc = yaml.load(text, Loader=_ComposeLoader)  # noqa: S506  # nosemgrep: unsafe-yaml-load
    return [_interpolate(line, env) for line in _env_lines(doc["services"][service])]


def _grafana_env(env_overrides: dict[str, str]) -> dict[str, str]:
    lines = _render_env_lines("grafana", env_overrides)
    return {ln.split("=", 1)[0]: ln.split("=", 1)[1] for ln in lines if "=" in ln}


def test_anonymous_admin_render_respects_legacy_and_derived_channels() -> None:
    """The composed line: unset → true (today); legacy hand-set false → false
    (never resurrected by the new channel); derived false → false (exposure
    kills anonymous Admin). The security direction only ever goes one way."""
    assert _grafana_env({}).get("GF_AUTH_ANONYMOUS_ENABLED") == "true"
    assert (
        _grafana_env({"GF_AUTH_ANONYMOUS_ENABLED": "false"}).get("GF_AUTH_ANONYMOUS_ENABLED")
        == "false"
    )
    assert (
        _grafana_env({"GRAFANA_ANONYMOUS_ENABLED": "false"}).get("GF_AUTH_ANONYMOUS_ENABLED")
        == "false"
    )


def test_derived_channels_render_end_to_end() -> None:
    """setup.py's exposed-mode values reach Grafana through compose: anonymous
    off, auth-proxy on, sign-up landing on Viewer."""
    env = _grafana_env(
        {
            "GRAFANA_ANONYMOUS_ENABLED": "false",
            "GRAFANA_AUTH_PROXY_ENABLED": "true",
            "GRAFANA_AUTH_PROXY_AUTO_SIGN_UP": "true",
        }
    )
    assert env.get("GF_AUTH_ANONYMOUS_ENABLED") == "false"
    assert env.get("GF_AUTH_PROXY_ENABLED") == "true"
    assert env.get("GF_AUTH_PROXY_AUTO_SIGN_UP") == "true"
    assert (
        env.get("GF_AUTH_PROXY_ORG_ROLE") == "Viewer"
        or env.get("GF_AUTH_PROXY_AUTO_SIGN_UP_ORG_ROLE") == "Viewer"
    )


# ---------------------------------------------------------------------------
# json-exporter: the fourth machine caller, admitted after an ack-time
# oversight — the hsi-telemetry/stats/gpu jobs target endpoints the gate
# COVERS (/api/system/telemetry|stats|gpu are NOT in OPEN_PATHS), so the
# probes 401 when exposed unless the exporter carries the key. Probe fact
# (v0.6.0, wire-verified against an echo target): modules.<name>.headers
# SCALAR map sends X-API-Key; a list value fails to unmarshal; a top-level/
# global headers: key is silently ignored; the binary expands no env vars,
# so its config renders too.
# ---------------------------------------------------------------------------

JSON_EXPORTER_CONFIG = REPO_ROOT / "monitoring" / "json-exporter-config.yml"


def test_json_exporter_renders_the_key_for_the_gated_modules(compose_services: dict) -> None:
    jx = compose_services["json-exporter"]
    lines = _env_lines(jx)
    assert "MONITORING_API_KEY=${MONITORING_API_KEY:-}" in lines
    assert "EXPOSE_LAN=${EXPOSE_LAN:-false}" in lines, (
        "the key renders ONLY when exposed — default-mode probes go out exactly as they do today"
    )
    command = " ".join(jx.get("command") or [])
    assert KEY_PLACEHOLDER in command, "json_exporter expands nothing (probe) — boot-render it"
    assert "--config.file=/tmp/json-exporter-config.yml" in command
    assert "/tmp" in str(jx.get("tmpfs") or ""), "needs writable /tmp if rootfs is read_only"

    text = _text(JSON_EXPORTER_CONFIG)
    for module in ("telemetry", "stats", "gpu"):
        block = text[text.index(f"  {module}:") :]
        block = block[: block.index("\n  #") :] if "\n  #" in block[10:] else block
        assert "headers" in block and "X-API-Key" in block and KEY_PLACEHOLDER in block, (
            f"module {module!r} probes a gated endpoint — it must render the key"
        )


def test_json_exporter_health_module_stays_headerless() -> None:
    """/api/system/health is in OPEN_PATHS — its probes need no credential,
    and a header on a module whose target list an operator can extend (the
    exporter is published on loopback 7979 for ad-hoc probes) is a needless
    credential-forwarding surface. Keep the open-probe module clean."""
    text = _text(JSON_EXPORTER_CONFIG)
    health = text[text.index("  health:") :]
    health = health[: health.index("\n  #") :] if "\n  #" in health[10:] else health
    health = health[: health.index("\n  telemetry") :] if "\n  telemetry" in health[10:] else health
    assert "X-API-Key" not in health


# ---------------------------------------------------------------------------
# setup.py also derives the alert sink (exposed: through the frontend machine
# listener that injects the header AM cannot send; unexposed: today's direct
# backend URL).
# ---------------------------------------------------------------------------


def test_setup_writes_the_alert_sink_beside_the_mode_block() -> None:
    setup_src = _text(SETUP_PY)
    region = setup_src[setup_src.index("FRONTEND_BIND_ADDRESS=") - 2000 :][:4000]
    assert "ALERT_SINK_URL=" in region, (
        "the sink join point is derived from EXPOSE_LAN like the bind address"
    )


# ---------------------------------------------------------------------------
# frontend/docker-entrypoint.sh: the browser-facing half, rendered ONLY when
# exposed. Default render keeps today's /grafana/ block intact; the exposed
# render adds auth_request -> /api/auth/me + auth-proxy (the recorded DECIDE:
# one login for /grafana/ and the three embedded dashboards) and the machine
# listener that no published port reaches.
# ---------------------------------------------------------------------------


def _location_blocks(text: str) -> list[tuple[str, str]]:
    """(location_path, block_body) for every nginx location block.

    Same brace-matching scanner as test_nginx_credential_forwarding.py.
    """
    blocks: list[tuple[str, str]] = []
    for match in re.finditer(r"location\s+(\^[~~]|~\*|~|=)?\s*(\S+)\s*\{", text):
        depth = 1
        pos = match.end()
        start = pos
        while pos < len(text) and depth > 0:
            if text[pos] == "{":
                depth += 1
            elif text[pos] == "}":
                depth -= 1
            pos += 1
        blocks.append((match.group(2), text[start : pos - 1]))
    return blocks


def test_entrypoint_keeps_todays_grafana_block_for_the_default_render() -> None:
    """EXPOSE_LAN unset must keep serving /grafana/ exactly as today (spec
    checklist 4): the unconditional block stays; the gated one is ADDITIVE."""
    text = _text(ENTRYPOINT)
    grafana_blocks = [b for path, b in _location_blocks(text) if path == "/grafana/"]
    assert grafana_blocks, "the default /grafana/ proxy must stay for the default render"
    assert all("auth_request" not in b for b in grafana_blocks), (
        "auth_request belongs to the exposed-only render — the DEFAULT render "
        "must not gain backend round-trips it never had (default unchanged)"
    )


def test_entrypoint_renders_the_exposed_grafana_auth_and_machine_listener() -> None:
    text = _text(ENTRYPOINT)
    assert "auth_request" in text and "/api/auth/me" in text, (
        "exposed render: /grafana/ behind the app session (200 serves, 401 "
        "refuses — the spec's refusal clause via nginx error_page)"
    )
    assert "X-Auth-User" in text and "hsi-viewer" in text, (
        "auth-proxy identity: a fixed provisioned Viewer, so the three embedded "
        "dashboards keep working after the ONE login (spec DECIDE)"
    )
    assert "listen 8081" in text, (
        "machine listener: published ONLY to the compose network (no host port — "
        "a published injector would hand the LAN a fake-alert sink)"
    )
    assert "location = /api/webhooks/alerts" in text, (
        "Alertmanager's sink route, header injected at the proxy (no AM version "
        "can send X-API-Key itself — probes 0.27→0.34)"
    )
    assert KEY_PLACEHOLDER in text, "the injector renders the key from the container env"


def test_entrypoint_gates_the_render_on_the_one_vocabulary() -> None:
    """The render branch keys on the same truthy words pydantic/B1.5 use, so
    EXPOSE_LAN=yes can never arm the gate but not the render (O1.6 lesson)."""
    text = _text(ENTRYPOINT)
    for word in ("true", "yes", "y", "on", "1"):
        assert re.search(rf"\b{word}\b", text), f"truthy vocabulary missing {word!r}"
    lower = text.lower()
    assert "expose_lan" in lower, "the render branch must key on EXPOSE_LAN"
