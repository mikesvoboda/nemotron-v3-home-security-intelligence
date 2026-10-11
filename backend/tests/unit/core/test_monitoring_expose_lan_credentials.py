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

Two findings from ops-b's ``security-auditor`` pass on #6930 fixed in-commit
(each with its own pin below): the boot render made the RELATIVE ``rule_files``
entries resolve against ``/tmp``, blinding all Prometheus alerting in silence
(finding 1, HIGH — absolute paths restore it, plus a docker-gated boot arm that
counts loaded rule files end to end); and the tmpfs renders rested the machine
key world-readable at the shell's default mode (finding 2, MEDIUM — the boot
scripts now ``chmod 0600``). Finding 2's structural half — ``API_KEYS`` is one
flat list, so the monitoring key holds the same privilege as an operator key —
is recorded as an owner DECIDE in the PR, not fixed here.

Sibling precedents: test_frontend_expose_lan_bind.py (O1.6 derivation +
compose-render idioms), test_nginx_credential_forwarding.py (brace parser for
the entrypoint-rendered config).
"""

# ruff: noqa: S108  — the /tmp paths below are asserted compose mounts, not
# scratch files this test writes (the S104 analog: test_frontend_expose_lan_bind.py:1).
from __future__ import annotations

import importlib
import json
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
    region = setup_src[setup_src.index("FRONTEND_BIND_ADDRESS=") - 2000 :][
        :6000
    ]  # 6 KB covers the whole derived-mode block (the O1.11 merge comment grew it past 4 KB)
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
    R60 (ruling 60): API_KEYS is the single-quoted compact JSON list with the
    generated entry SCOPED — ``'[{"key":...,"scope":"monitoring"}]'`` — the
    form pydantic parses AND the form bash can source. The key itself is
    hsi_+token_urlsafe, whose alphabet is JSON- and shell-safe."""
    import setup

    base = {"monitoring_api_key": "hsi_TESTKEY123"}  # pragma: allowlist secret
    exposed = setup.generate_env_content({**base, "expose_lan": True})
    unexposed = setup.generate_env_content({**base, "expose_lan": False})
    for content in (exposed, unexposed):
        assert "MONITORING_API_KEY=hsi_TESTKEY123" in content
        assert """API_KEYS='[{"key":"hsi_TESTKEY123","scope":"monitoring"}]'""" in content, (
            "the key mirrors into API_KEYS, scoped and single-quoted, in BOTH modes"
        )
    assert "GRAFANA_ANONYMOUS_ENABLED=false" in exposed
    assert "GRAFANA_AUTH_PROXY_ENABLED=true" in exposed
    assert "ALERT_SINK_URL=http://frontend:8081/api/webhooks/alerts" in exposed
    assert "GRAFANA_ANONYMOUS_ENABLED=true" in unexposed
    assert "GRAFANA_AUTH_PROXY_ENABLED=false" in unexposed
    assert "ALERT_SINK_URL=http://backend:8000/api/webhooks/alerts" in unexposed


def test_generated_env_api_keys_line_sources_in_bash(tmp_path: Path) -> None:
    """The R60 emission hazard, pinned at the shell (amendment 5, measured).

    Two scripts ``source`` the generated .env under ``set -e``
    (quick-rebuild.sh:73, verify-observability.sh:19) and compose:636
    interpolates the value. Measured pre-fix: the spaced two-key line
    json.dumps defaults to ALREADY aborts those scripts with exit 127, and
    unquoted compact JSON with objects brace-EXPANDS — ``[{key:a,...},b]``
    lands as ``[[{key:a,...},b]]``, mangled with a silent exit 0. The
    generation path here is the real one (object entry + a second operator
    key, the worst case), sourced with ``set -e`` active, and the echoed
    value must be BYTE-IDENTICAL to what the file says — not just exit 0.
    """
    import subprocess

    import setup

    content = setup.generate_env_content(
        {
            "monitoring_api_key": "hsi_TESTKEY123",  # pragma: allowlist secret
            "existing_api_keys": '["operator-key-a"]',
        }
    )
    env_file = tmp_path / ".env"
    env_file.write_text(content, encoding="utf-8")
    line = next(ln for ln in content.splitlines() if ln.startswith("API_KEYS="))

    probe = subprocess.run(  # noqa: S603 — argv is a literal list; bash is the interpreter  # real
        ["bash", "-c", f'set -e\nsource "{env_file}"\nprintf %s "$API_KEYS"'],  # noqa: S607 — bash from PATH on purpose; argv is literal
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode == 0, f"sourcing the .env aborted: {probe.stderr}"
    assert probe.stdout == line.removeprefix("API_KEYS=").strip("'"), (
        "bash mangled the value on source (brace expansion / word splitting)"
    )


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


@pytest.mark.parametrize("service", ["prometheus", "json-exporter", "alertmanager"])
def test_shell_render_services_override_their_entrypoint(
    compose_services: dict, service: str
) -> None:
    """compose APPENDS ``command:`` to the image's ENTRYPOINT binary — and for
    these three images the entrypoint IS the binary. Measured 2026-10-09
    against the pinned tags with the exact argv compose delivers
    (``docker run <image> /bin/sh -ec 'echo reached'``):
    ``prometheus: error: unexpected /bin/sh`` / ``alertmanager: error:
    unexpected /bin/sh, try --help`` / ``json_exporter: error: path
    'config.yml' does not exist``. A boot render written as command: [/bin/sh,
    -ec, …] with no entrypoint: override therefore crash-loops the monitoring
    stack in BOTH modes — the renders are EXPOSE_LAN-gated, the broken argv is
    not. The fix shape, also measured (``--entrypoint /bin/sh`` + the script):
    all three images reach the shell and ``exec`` the binary cleanly.

    Scope: this pins the three render services, NOT every shell command in the
    file — foscam-init (alpine: entrypoint unset, the command runs AS argv[0])
    and redis (its docker-entrypoint.sh wrapper consumes the args) start
    shells legitimately. A global 'shell command ⇒ entrypoint' rule would be
    the wrong invariant; the right one is 'the image whose entrypoint is the
    binary needs the override', and that list is exactly these three images.'
    """
    svc = compose_services[service]
    command = svc.get("command") or []
    assert svc.get("entrypoint") == ["/bin/sh", "-ec"], (
        f"{service}: compose appends command: to the entrypoint, and for this "
        "image the entrypoint IS the binary — without the override the container "
        "runs e.g. /bin/prometheus /bin/sh -ec … and crash-loops in both modes"
    )
    assert isinstance(command, list) and command, f"{service}: render command missing"
    assert not str(command[0]).endswith("/sh"), (
        f"{service}: entrypoint already carries /bin/sh -ec; a command that "
        "REPEATS the interpreter executes the string /bin/sh against empty "
        "stdin and exits — the script must be the whole argv tail"
    )
    joined = " ".join(str(part) for part in command)
    assert ("__HSI_MONITORING_API_KEY__" in joined) or ("__HSI_ALERT_SINK__" in joined), (
        f"{service}: the boot render must still be present in command:"
    )
    assert joined.lstrip().startswith('sed "') or "case " in joined, (
        f"{service}: command must open with the render (sed or the mode case), "
        "not with an interpreter it no longer needs"
    )


def _scratch_entrypoint(tmp_path: Path, env: dict[str, str], boots: int = 1) -> str:
    """Run the real entrypoint ``boots`` times against a fresh nginx.conf.

    Hermetic by rewrite, not by mock: the ``NGINX_CONF`` constant and every
    ``/tmp/`` path in the script are redirected into ``tmp_path`` so parallel
    xdist workers (``--dist=worksteal`` splits a file across workers) cannot
    collide on the shared ``/tmp/hsi-*.conf`` scratch files. ``exec "$@"`` at
    the script's end gets ``true``, so the render is what runs.
    """
    import os
    import subprocess

    script = _text(ENTRYPOINT).replace("/tmp/", f"{tmp_path}/")
    script = script.replace(
        'NGINX_CONF="/etc/nginx/conf.d/default.conf"', f'NGINX_CONF="{tmp_path}/default.conf"'
    )
    ep = tmp_path / "entrypoint.sh"
    ep.write_text(script)
    (tmp_path / "default.conf").write_text(_text(REPO_ROOT / "frontend" / "nginx.conf"))
    run_env = {**os.environ, **env}
    for _ in range(boots):
        result = subprocess.run(  # noqa: S603 — argv is a literal list, sh is the interpreter  # real
            ["sh", str(ep), "true"],  # noqa: S607 — sh from PATH on purpose; argv is literal
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=run_env,
        )
        assert result.returncode == 0, f"entrypoint boot failed: {result.stderr[:400]}"
    return (tmp_path / "default.conf").read_text()


def test_exposed_boot_is_idempotent_across_container_restarts(tmp_path: Path) -> None:
    """``$NGINX_CONF`` lives on the container's WRITABLE layer (compose's own
    comment at docker-compose.prod.yml:915 keeps ``frontend`` off ``read_only``
    precisely because this entrypoint ``sed -i``s the file), so the appended
    machine listener PERSISTS across ``docker restart`` and a naive
    ``cat >>`` adds another copy every boot. Measured before the fix: two boots
    → two ``listen 8081`` blocks, and real ``nginx -t`` on that file is VALID
    with ``[warn] conflicting server name "localhost" on 0.0.0.0:8081,
    ignored`` — a silent failure where the FIRST block (holding a stale key, if
    one is ever rotated) owns the route. The include/anchor splices are immune
    (their placeholders are consumed on the first render), so the guard belongs
    on the appended block: strip-then-append."""
    rendered = _scratch_entrypoint(
        tmp_path,
        {"EXPOSE_LAN": "true", "MONITORING_API_KEY": "hsi_TESTKEY123"},  # pragma: allowlist secret
        boots=3,
    )
    assert rendered.count("listen 8081;") == 1, (
        "three exposed boots of one container layer must leave ONE machine "
        "listener — a second copy wins the route with a stale key"
    )
    assert rendered.count("location = /api/webhooks/alerts") == 1
    assert "__HSI_" not in rendered, "no un-rendered placeholder may survive a boot"


def test_one_vocabulary_survives_whitespace_in_env(tmp_path: Path) -> None:
    """``setup_lib.core._expose_lan_is_truthy`` STRIPS (its docstring cites the
    ``" true"`` case) and pydantic is what arms the gate; the boot renderers
    lowercase but must strip too, or ``EXPOSE_LAN=" true"`` arms the gate with
    the renders OFF — scrape 401, alerts to a never-rendered sink, /grafana/
    locked. Fail-closed, but it contradicts the entrypoint's own "can never
    disagree" comment, and a padded value is exactly what a hand-edited .env
    with ``EXPOSE_LAN= true`` produces."""
    padded = " true"
    assert _setup_fn("_expose_lan_is_truthy")(padded) is True, (
        "setup_lib is the reference reader — this test is only meaningful "
        "because it treats ' true' as exposed"
    )
    rendered = _scratch_entrypoint(
        tmp_path,
        {"EXPOSE_LAN": padded, "MONITORING_API_KEY": "hsi_TESTKEY123"},  # pragma: allowlist secret
    )
    assert "listen 8081;" in rendered, (
        'EXPOSE_LAN=" true" arms the gate (pydantic) and the bind '
        "(setup_lib strips) — the render must agree, not split"
    )


def test_json_exporter_gate_strips_whitespace_too(tmp_path: Path) -> None:
    """The fourth reader of the same vocabulary is the json-exporter's boot
    command, which lowercases through ``tr`` — it must strip as well, or a
    padded ``EXPOSE_LAN`` renders its headers OFF (probes 401) while pydantic
    has the gate ON. Runs the ACTUAL command string out of compose, with only
    its two file paths rewritten into ``tmp_path`` and the final ``exec``
    neutralised, so the case arms are what is being tested."""
    import os
    import subprocess

    svc = yaml.load(_text(COMPOSE_FILE), Loader=_ComposeLoader)["services"]["json-exporter"]  # noqa: S506  # nosemgrep: unsafe-yaml-load
    parts = list(svc["command"])
    if parts and str(parts[0]).endswith("/sh"):
        parts = parts[
            2:
        ]  # old shape: [/bin/sh, -ec, <script>] — the fix moves the interpreter to entrypoint:
    script = " ".join(parts)
    stub = tmp_path / "config.yml"
    stub.write_text(f"modules:\n  hsi-health:\n    headers:\n      X-API-Key: {KEY_PLACEHOLDER}\n")
    out = tmp_path / "rendered.yml"
    script = script.replace("/etc/json-exporter/config.yml", str(stub)).replace(
        "/tmp/json-exporter-config.yml", str(out)
    )
    script = script.replace("exec /bin/json_exporter", "exec true")
    # compose's $$-escape exists precisely so the expansion survives to the
    # CONTAINER's shell (compose would otherwise interpolate at config time);
    # running the command through sh directly must replay that unescape, or
    # sh reads $$ as its own PID and the case never matches.
    script = script.replace("$${", "${")
    result = subprocess.run(  # noqa: S603 — argv is a literal list; the script is this repo's compose text  # real
        ["sh", "-ec", script],  # noqa: S607 — sh from PATH on purpose; argv is literal
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={
            **os.environ,
            "EXPOSE_LAN": " true",
            "MONITORING_API_KEY": "hsi_TESTKEY123",  # pragma: allowlist secret
        },
    )
    assert result.returncode == 0, f"render command failed: {result.stderr[:300]}"
    rendered_yml = out.read_text()
    # Positive assertion, not "placeholder absent": the unexposed arm DELETES the
    # headers lines, so absence alone is also true when the branch was wrong.
    assert (
        "hsi_TESTKEY123" in rendered_yml and KEY_PLACEHOLDER not in rendered_yml
    ), (  # pragma: allowlist secret
        'padded " true" must render the exposed branch (key substituted) — '
        "rendering unexposed while pydantic arms the gate 401s every probe"
    )


@pytest.mark.parametrize("service", ["prometheus", "json-exporter", "alertmanager"])
def test_tmpfs_config_renders_are_owner_read_write_only(
    compose_services: dict, service: str, tmp_path: Path
) -> None:
    """Ops-b security pass on #6930 (finding 2, MEDIUM): the boot renders put a
    live API key onto tmpfs with the SHELL DEFAULT file mode — sed creates (and
    preserves) modes, so under the usual umask 022 the render rests 0644,
    group/world readable, for the container's whole life. Mitigation: ``chmod
    0600`` the render before ``exec``. Runs the ACTUAL compose command (the
    test_json_exporter_gate_strips_whitespace_too idiom: paths rewritten into
    tmp_path, ``exec`` neutralised, ``$${`` replayed) with the output file
    PRE-SET to 0644 — the finding's real-world mode — so a passing run can
    only come from the script itself
    tightening the mode. json-exporter runs both case arms — a chmod on the
    exposed arm alone would leave today's default render unprotected."""
    import os
    import stat
    import subprocess

    svc = compose_services[service]
    src_container = str(svc["volumes"][0]).split(":")[1]  # the config mount target
    script_src = " ".join(str(part) for part in (svc.get("command") or []))
    m = re.search(r">\s*(/tmp/\S+)", script_src)
    assert m, f"{service}: no /tmp render target found in command:"
    out_container = m.group(1)

    stub = tmp_path / "stub.yml"
    stub.write_text(
        f"marker: {SINK_PLACEHOLDER if service == 'alertmanager' else KEY_PLACEHOLDER}\n"
    )
    envs = (
        [("exposed", "true"), ("default", "false")]
        if service == "json-exporter"
        else [("default", "false")]
    )
    for label, expose in envs:
        out = tmp_path / f"rendered-{label}.yml"
        out.write_text("stale\n")
        # The trap's mode is the finding's real-world mode: under the usual
        # umask 022 the sed render rests 0644. sed keeps an existing target's
        # mode, so a render that starts group-readable can only pass the
        # <= 0600 assertion below if the script itself tightens it.
        os.chmod(out, 0o644)
        script = (
            script_src.replace("$${", "${")
            .replace(src_container, str(stub))
            .replace(out_container, str(out))
        )
        script = re.sub(r"exec /bin/\w+", "exec true", script)
        result = subprocess.run(  # noqa: S603 — argv literal; script is repo compose text  # real
            ["sh", "-ec", script],  # noqa: S607 — sh from PATH on purpose
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env={
                **os.environ,
                "EXPOSE_LAN": expose,
                "MONITORING_API_KEY": "hsi_TESTKEY123",  # pragma: allowlist secret
                "ALERT_SINK_URL": DEFAULT_SINK,
            },
        )
        assert result.returncode == 0, f"{service} ({label}) render failed: {result.stderr[:300]}"
        rendered = out.read_text()
        assert "stale" not in rendered, f"{service} ({label}): render did not overwrite its target"
        mode = stat.S_IMODE(out.stat().st_mode)
        assert mode <= 0o600, (
            f"{service} ({label}): tmpfs config render is mode {mode:04o} — it holds "
            "the machine key; sed keeps the umask default, so the boot script must "
            "chmod 0600 before exec"
        )


def test_setup_merges_operator_api_keys_instead_of_replacing() -> None:
    """setup.py at origin/main wrote no API_KEYS at all (measured:
    ``git show origin/main:setup.py | grep -c API_KEYS`` → 0), so O1.11's
    ``API_KEYS=json.dumps([monitoring_key])`` line silently REPLACES whatever
    keys an operator added by hand the next time setup.py runs — the file's own
    reuse-first doctrine for MONITORING_API_KEY and its "preserve existing
    passwords when re-running" rule say merge, not clobber."""
    merge = _setup_fn("merge_api_keys")
    merged = json.loads(
        merge('["operator-key-a", "operator-key-b"]', "hsi_NEW")
    )  # pragma: allowlist secret
    assert merged == ["hsi_NEW", "operator-key-a", "operator-key-b"], (
        "the generated key leads, operator keys survive in order"
    )
    assert json.loads(merge("", "hsi_NEW")) == ["hsi_NEW"]  # pragma: allowlist secret
    assert json.loads(merge("[]", "")) == [], "no key, no list entry"
    again = json.loads(merge(merge("", "hsi_NEW"), "hsi_NEW"))  # pragma: allowlist secret
    assert again == ["hsi_NEW"], (
        "re-running setup.py must not duplicate the key"
    )  # pragma: allowlist secret
    # A hand-corrupted value must not take setup.py down: keep the new key,
    # drop the unparseable list, stay a valid JSON array for pydantic.
    assert json.loads(merge("not-json", "hsi_NEW")) == ["hsi_NEW"]  # pragma: allowlist secret


def test_setup_merge_is_object_aware_under_r60() -> None:
    """R60 (ruling 60), the second-run privilege bug the design panel caught.

    The ``str(item)`` round-trip above is a silent privilege bug once objects
    exist: json.loads hands back a dict, str(dict) writes single-quoted Python
    repr, and a re-run re-emits the monitoring key as an UNSCOPED plain string
    plus a junk entry whose SHA-256 hashes as a valid unscoped key. Measured
    pre-fix: ``merge('[{"key":"hsi_NEW","scope":"monitoring"}]', "hsi_NEW")``
    → '["hsi_NEW", "{\'key\': \'hsi_NEW\', \'scope\': \'monitoring\'}"]'.

    Identity is the KEY VALUE across BOTH forms, which is what lets a pre-R60
    .env (plain-string mirror) be UPGRADED to the scoped object instead of
    duplicated — a surviving plain entry would leave the value unscoped at the
    gate (R60 precedence: a plain entry for a value means that value is
    unscoped), so R60 would un-fix itself one re-run after it shipped.
    """
    merge = _setup_fn("merge_api_keys")

    # The panel's repro, post-fix, and byte-stable on the run after it.
    once = merge('[{"key":"hsi_NEW","scope":"monitoring"}]', "hsi_NEW", "monitoring")
    assert json.loads(once) == [{"key": "hsi_NEW", "scope": "monitoring"}]
    assert merge(once, "hsi_NEW", "monitoring") == once, "byte-stable re-run"

    # Pre-R60 .env: the mirror is a PLAIN string. New setup.py upgrades it.
    upgraded = json.loads(
        merge('["hsi_NEW","operator-a","operator-b"]', "hsi_NEW", "monitoring")
    )  # pragma: allowlist secret
    assert upgraded == [{"key": "hsi_NEW", "scope": "monitoring"}, "operator-a", "operator-b"], (
        "no surviving plain duplicate — that duplicate would be the un-fix"
    )

    # setup.py's own reader keeps the surrounding quotes (raw read-back), so
    # the quoted line must round-trip through the next merge unchanged.
    quoted = """'[{"key":"hsi_NEW","scope":"monitoring"}]'"""
    assert json.loads(merge(quoted, "hsi_NEW", "monitoring")) == [
        {"key": "hsi_NEW", "scope": "monitoring"}
    ]

    # An existing object keeps the scope setup.py did NOT generate, verbatim —
    # including a name the backend will fail closed (preserve-existing). Two
    # distinct malformations, two outcomes, measured at the code:
    #   {"key": "bad"} (usable key, no scope) SURVIVES as-is — setup.py never
    #     deletes a key it didn't mint; the absent scope is the backend's
    #     fail-closed-with-warning arm, not setup.py's business;
    #   {"key": ""} (no usable key) is DROPPED — it can never match a digest.
    kept = json.loads(
        merge(
            '[{"key":"op","scope":"operator"},{"key":"bad"},{"key":"","scope":"monitoring"}]',
            "hsi_NEW",
            "monitoring",
        )
    )  # pragma: allowlist secret
    assert kept == [
        {"key": "hsi_NEW", "scope": "monitoring"},
        {"key": "op", "scope": "operator"},
        {"key": "bad"},
    ]

    # Compact separators (no ", " / ": " padding) so a sourcing shell neither
    # word-splits nor brace-expands the line; the generated entry leads.
    assert ", " not in merge('["a","b"]', "hsi_NEW", "monitoring")  # pragma: allowlist secret
    assert json.loads(merge("", "hsi_NEW", "monitoring")) == [
        {"key": "hsi_NEW", "scope": "monitoring"}
    ]  # pragma: allowlist secret


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


def test_prometheus_rule_files_are_absolute_under_the_tmp_boot(
    compose_services: dict,
) -> None:
    """Prometheus resolves ``rule_files`` relative to the DIRECTORY OF THE
    CONFIG FILE, and the O1.11 boot renders that config to /tmp — so relative
    entries look for rules in /tmp and load NOTHING. Ops-b's security pass on
    #6930 (finding 1, HIGH) measured the shipped shape on the pinned image
    with the repo's real files: groups=0 alerting=0 total=0, zero ERROR/WARN
    log lines, ``/-/ready`` green — total alerting blindness in silence. The
    same image with the config in place at /etc/prometheus (pre-O1.11 shape)
    loaded 34/121/168. Absolute entries restore it under the /tmp boot
    (measured 34/121/168). The boot render itself stays (tmpfs, read_only
    rootfs); this pins that its rule anchor is the mount, not the render dir."""
    cfg = yaml.safe_load(_text(PROM_CONFIG))
    rule_files = cfg["rule_files"]
    assert rule_files, "rule_files must stay populated"
    for entry in rule_files:
        assert entry.startswith("/etc/prometheus/"), (
            f"rule_files entry {entry!r} is relative: Prometheus resolves it "
            "against the config FILE'S directory, and the boot renders the "
            "config to /tmp — relative entries load 0 groups silently"
        )
    mounted = {
        str(v).split(":")[1]
        for v in (compose_services["prometheus"].get("volumes") or [])
        if str(v).count(":") >= 1
    }
    for entry in rule_files:
        assert entry in mounted, (
            f"{entry} is absolute but never mounted into the container — "
            "a rule_files entry that points at nothing is silently ignored "
            "(same blindness class, docs/operator/prometheus-alerting.md)"
        )
    command = " ".join(compose_services["prometheus"].get("command") or [])
    assert "/tmp/prometheus.yml" in command, (
        "the /tmp render is WHY the entries must be absolute; if the boot "
        "ever stops rendering to /tmp, revisit the rule anchor in the same "
        "change rather than silently stranding absolute paths"
    )


@pytest.mark.timeout(120)  # conftest honors an explicit timeout marker over the 5s tier
def test_prometheus_boot_loads_every_committed_rule_file(compose_services: dict) -> None:
    """Finding 1's class end to end: run the REAL compose boot command against
    the REAL pinned image with the compose service's own volume mounts, and
    require every committed rule file to contribute at least one loaded group
    (per-group ``file`` attribution from /api/v1/rules — attribution, not
    rule counts, so the pin survives legitimate rule churn). Pre-fix
    measurement on this head: 0 of 7 files loaded, silently. Skips — never
    fails — without a docker daemon or the pinned image present; the CI
    standing guard for the class is the static absolute-entry pin above."""
    import socket
    import subprocess
    import time
    import urllib.request
    import uuid

    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("no docker daemon available for the boot arm")

    def run_docker(*argv: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 — argv literal; docker from PATH  # real
            [docker, *argv],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    svc = compose_services["prometheus"]
    image = svc["image"]
    if run_docker("image", "inspect", image).returncode != 0:
        pytest.skip(f"{image} not pulled locally — the boot arm is opt-in by pull")

    volumes: list[str] = []
    for v in svc.get("volumes") or []:
        src, _, rest = str(v).partition(":")
        if not src.startswith("."):
            continue  # named volume (prometheus_data:/prometheus) — container-side
        volumes += ["-v", f"{(REPO_ROOT / src[2:]).resolve()}:{rest.partition(':')[0]}:ro"]
    script = " ".join(str(part) for part in (svc.get("command") or [])).replace("$${", "${")

    with socket.socket() as probe:  # ephemeral port — xdist workers run this concurrently
        probe.bind(("127.0.0.1", 0))
        host_port = probe.getsockname()[1]
    name = f"o111-bootpin-{uuid.uuid4().hex[:8]}"
    started = run_docker(
        "run",
        "-d",
        "--rm",
        "--name",
        name,
        "-p",
        f"127.0.0.1:{host_port}:9090",
        "-e",
        "MONITORING_API_KEY=hsi_TESTKEY123",  # pragma: allowlist secret
        *volumes,
        "--entrypoint",
        "/bin/sh",
        image,
        "-ec",
        script,
    )
    assert started.returncode == 0, f"docker run failed: {started.stderr[:300]}"
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + 25.0
        ready = False
        while time.monotonic() < deadline:
            try:
                ready = (
                    opener.open(f"http://127.0.0.1:{host_port}/-/ready", timeout=2).status == 200
                )
            except OSError:
                time.sleep(0.5)
            else:
                break
        assert ready, f"prometheus never became ready:\n{run_docker('logs', name).stdout[-800:]}"
        with opener.open(f"http://127.0.0.1:{host_port}/api/v1/rules", timeout=5) as resp:
            payload = json.load(resp)
    finally:
        run_docker("stop", name)

    loaded = {str(g.get("file", "")) for g in payload["data"]["groups"]}
    expected = {Path(entry).name for entry in yaml.safe_load(_text(PROM_CONFIG))["rule_files"]}
    missing = {n for n in expected if not any(f.endswith("/" + n) for f in loaded)}
    assert not missing, (
        f"{len(missing)} of {len(expected)} rule files loaded NO groups under the "
        f"real /tmp boot: {sorted(missing)} — alerting is blind and the boot "
        "logs stay clean (finding 1); entries must be absolute /etc/prometheus paths"
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
    region = setup_src[setup_src.index("FRONTEND_BIND_ADDRESS=") - 2000 :][:6000]
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
