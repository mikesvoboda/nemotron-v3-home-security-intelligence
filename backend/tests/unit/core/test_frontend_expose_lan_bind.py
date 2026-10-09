# ruff: noqa: S104
"""O1.6: the frontend's published ports bind loopback unless EXPOSE_LAN=true.

The chain under test, end to end:

    EXPOSE_LAN (user answer / .env)
      -> setup.py derives FRONTEND_BIND_ADDRESS (127.0.0.1 default, 0.0.0.0 on true)
      -> docker-compose.prod.yml frontend ports reference ${FRONTEND_BIND_ADDRESS:-127.0.0.1}
      -> the published socket's bind address

Compose has no conditionals, so the DECIDE the package asks for is the derivation
above: the fail-safe default lives in BOTH ends (the derive maps anything but
pydantic's own case-insensitive truthy set — true/t/yes/y/on/1, the SAME words
that arm the auth gate — to loopback; compose's own ``:-127.0.0.1`` covers a
hand-edited .env that carries EXPOSE_LAN=true without FRONTEND_BIND_ADDRESS at
all — the render with that shape is pinned below).

Every test here is skip-free: the render test uses the real compose binary when
one is installed and, when none is (whether a given CI runner carries one is
not asserted from the repo — both branches run green either way), an
in-test interpolation emulator pinned by its own unit asserts, so the Done-when
clause ("that test runs in CI and passes") holds in both directions. The
environment-skip precedent (test_compose_render_lists_ai_vlm.py) is deliberately
NOT copied.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_FILE = REPO_ROOT / "docker-compose.prod.yml"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
# The committed render-env precedent: stubs for the two ${VAR:?} hard-required
# vars so `compose config` can interpolate the whole file.
RENDER_ENV_FIXTURE = REPO_ROOT / "backend/tests/fixtures/compose-render.env"


# A compose-native test file needs the safe loader (see
# test_docker_compose_security.py:301 for why); prod.yml carries no custom tags,
# but keep the tolerant shape so a tagged import elsewhere can't bite.
class _ComposeLoader(yaml.SafeLoader):
    """safe_load that also reads compose's merge tags (!override, !reset)."""


def _construct_compose_tag(loader: yaml.SafeLoader, _suffix: str, node: yaml.Node) -> object:
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_scalar(node)  # type: ignore[arg-type]


_ComposeLoader.add_multi_constructor("!", _construct_compose_tag)


def _frontend_port_entries() -> list[str]:
    """The frontend service's raw ports strings from the shipped compose file."""
    # _ComposeLoader IS a SafeLoader: it only adds plain-node reads of compose's
    # own tags, no Python object construction.
    text = COMPOSE_FILE.read_text(encoding="utf-8")
    doc = yaml.load(text, Loader=_ComposeLoader)  # noqa: S506  # nosemgrep: unsafe-yaml-load
    return list(doc["services"]["frontend"]["ports"])


# ---------------------------------------------------------------------------
# 1. The compose shape: variable-ised bind address, fail-safe default, no
#    hardcoded 0.0.0.0 left on the frontend.
# ---------------------------------------------------------------------------


def test_frontend_ports_use_the_bind_address_variable():
    entries = _frontend_port_entries()
    assert len(entries) == 2, f"expected the 8444/8080 pair, got {entries}"
    # NB: not entry.split(":")[0] — the :- default carries a colon INSIDE the
    # host part, so a naive split cuts the interpolation in half (my first
    # draft did exactly that and reddened on a correct compose file).
    for entry in entries:
        assert entry.startswith("${FRONTEND_BIND_ADDRESS:-127.0.0.1}:"), (
            f"frontend entry {entry!r} does not derive its bind from "
            "FRONTEND_BIND_ADDRESS with the loopback fail-safe default"
        )
        target = entry.rsplit(":", 1)[1]
        assert target in ("8443", "8080"), f"unexpected container target in {entry!r}"


def test_frontend_ports_have_no_hardcoded_wildcard_bind():
    for entry in _frontend_port_entries():
        assert not entry.startswith("0.0.0.0:"), (
            f"frontend entry {entry!r} hardcodes the wildcard bind — the "
            "0.0.0.0 default must come only from EXPOSE_LAN=true via setup.py"
        )


def test_env_example_declares_the_two_vars():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assigns = dict(re.findall(r"^([A-Z0-9_]+)=(.*)$", text, re.MULTILINE))
    assert assigns.get("EXPOSE_LAN") == "false", (
        ".env.example must carry EXPOSE_LAN=false (the package's clause)"
    )
    assert assigns.get("FRONTEND_BIND_ADDRESS") == "127.0.0.1", (
        ".env.example must carry FRONTEND_BIND_ADDRESS=127.0.0.1 so the "
        "documented default and compose's :- default cannot disagree"
    )


# ---------------------------------------------------------------------------
# 2. The derivation + the .env writer.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", "127.0.0.1"),  # unset / bare Enter
        ("false", "127.0.0.1"),
        ("False", "127.0.0.1"),
        ("FALSE", "127.0.0.1"),
        ("true", "0.0.0.0"),
        ("True", "0.0.0.0"),
        ("TRUE", "0.0.0.0"),
        ("1", "0.0.0.0"),
        # One flag, one vocabulary (O1.6 review follow-up): the truthy set is
        # the SAME case-insensitive set pydantic parses for Settings.expose_lan
        # (true/1/yes/y/on — probed against TypeAdapter(bool) on pydantic 2.13),
        # so EXPOSE_LAN=yes can never arm the auth gate while leaving the bind
        # loopback. Case variants of every member open; typos stay shut.
        ("trUe", "0.0.0.0"),
        ("t", "0.0.0.0"),
        ("T", "0.0.0.0"),
        ("YES", "0.0.0.0"),
        ("y", "0.0.0.0"),
        ("on", "0.0.0.0"),
        # fail-safe: anything unrecognised binds loopback, never wild.
        ("0", "127.0.0.1"),
        ("no", "127.0.0.1"),
        ("off", "127.0.0.1"),
        ("garbage", "127.0.0.1"),
    ],
)
def test_derive_frontend_bind_address(raw: str, expected: str) -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from setup_lib.core import derive_frontend_bind_address

    assert derive_frontend_bind_address(raw) == expected


def test_generate_env_content_writes_both_vars() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import setup

    default_env = setup.generate_env_content({})
    assert "EXPOSE_LAN=false" in default_env
    assert "FRONTEND_BIND_ADDRESS=127.0.0.1" in default_env

    lan_env = setup.generate_env_content({"expose_lan": True})
    assert "EXPOSE_LAN=true" in lan_env
    assert "FRONTEND_BIND_ADDRESS=0.0.0.0" in lan_env


# ---------------------------------------------------------------------------
# 3. The prompt flow: EXPOSE_LAN reaches the config dict in every mode.
# ---------------------------------------------------------------------------


def _answer_prompt_containing(prompt_map: dict[str, str]):
    """A fake input() wired by prompt-substring; anything else gets default.

    prompt_with_default renders ``{prompt} [{default}]: `` — matching on the
    substring keeps this honest about the real prompt text: if the prompt is
    renamed the mapping stops matching and the default path is exercised, not
    a bypass.
    """

    def fake_input(prompt: str = "") -> str:
        for needle, answer in prompt_map.items():
            if needle.lower() in prompt.lower():
                return answer
        return ""

    return fake_input


def test_defaults_mode_never_exposes_the_lan(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--defaults``/``--yes`` bootstrap through here — defaults must be loopback."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import setup

    def no_input(prompt: str = "") -> str:  # pragma: no cover - must not fire
        raise AssertionError("defaults mode must not prompt")

    monkeypatch.setattr("builtins.input", no_input)
    config = setup.run_defaults_mode()
    assert config["expose_lan"] is False


def test_quick_mode_prompt_flips_expose_lan(monkeypatch: pytest.MonkeyPatch) -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import setup

    monkeypatch.setattr("builtins.input", _answer_prompt_containing({"expose the UI": "y"}))
    config = setup.run_quick_mode()
    assert config["expose_lan"] is True


def test_quick_mode_default_keeps_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import setup

    monkeypatch.setattr("builtins.input", _answer_prompt_containing({}))
    config = setup.run_quick_mode()
    assert config["expose_lan"] is False


def test_guided_mode_prompt_flips_expose_lan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guided mode carries the same EXPOSE_LAN step as quick mode (setup.py
    ~:841); the header's "every mode" claim must hold for it, not just quick."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import setup

    monkeypatch.setattr("builtins.input", _answer_prompt_containing({"Expose the UI": "y"}))
    config = setup.run_guided_mode()
    assert config["expose_lan"] is True


def test_guided_mode_default_keeps_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import setup

    monkeypatch.setattr("builtins.input", _answer_prompt_containing({}))
    config = setup.run_guided_mode()
    assert config["expose_lan"] is False


# ---------------------------------------------------------------------------
# 4. The render: bindings with EXPOSE_LAN unset and set.
# ---------------------------------------------------------------------------

_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _interpolate(value: str, env: dict[str, str]) -> str:
    """${VAR:-default} grammar, one level (what compose does for these lines).

    compose treats an EMPTY value like an unset one for :- defaults (probed
    against docker compose config: TB= renders host_ip=127.0.0.1), so the
    emulator must not return "" — that is pinned in test_binding_helpers_are_pinned.
    """

    def sub(m: re.Match[str]) -> str:
        current = env.get(m.group(1), "")
        if current == "" and m.group(2) is not None:
            return m.group(2)
        return current

    return _VAR_RE.sub(sub, value)


def _split_binding(entry: str) -> tuple[str, str, str]:
    """Compose short vs qualified syntax -> (host_ip, published, target).

    The short form's semantics are pinned by an empirical daemon probe (docker
    29.8.1: `4317/tcp -> 0.0.0.0:32915` and `[::]:32915`): an unqualified
    publish means all interfaces. That is why a bind variable defaulting to
    127.0.0.1 must appear in the long form, never the short.
    """
    parts = entry.split(":")
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    return "0.0.0.0", "", parts[0]


def test_binding_helpers_are_pinned() -> None:
    assert _interpolate("${FRONTEND_BIND_ADDRESS:-127.0.0.1}", {}) == "127.0.0.1"
    assert (
        _interpolate("${FRONTEND_BIND_ADDRESS:-127.0.0.1}", {"FRONTEND_BIND_ADDRESS": "0.0.0.0"})
        == "0.0.0.0"
    )
    # compose's :- grammar treats an EMPTY value like an unset one (verified
    # against `docker compose config` behaviour); an emulator that returned ""
    # here would disagree with the binary on exactly the fail-safe case.
    assert (
        _interpolate("${FRONTEND_BIND_ADDRESS:-127.0.0.1}", {"FRONTEND_BIND_ADDRESS": ""})
        == "127.0.0.1"
    )
    assert _split_binding("127.0.0.1:8444:8443") == ("127.0.0.1", "8444", "8443")
    assert _split_binding("4317") == ("0.0.0.0", "", "4317")


def _compose_argv() -> list[str] | None:
    """The first compose invocation this machine can run (repo precedent:
    test_compose_render_lists_ai_vlm.py::_compose_argv). `docker compose` and
    `podman compose` are SUBCOMMANDS — which("compose") is None everywhere, so
    an all(which(part) …) over the pair can never fire (the O1.6 review caught
    exactly that dead branch here). None means: emulator path."""
    if shutil.which("podman"):
        return ["podman", "compose"]
    if shutil.which("docker"):
        return ["docker", "compose"]
    for binary in ("podman-compose", "docker-compose"):
        if shutil.which(binary):
            return [binary]
    return None


# Env vars the render tests own: a developer or CI runner export must never
# move what the "default env" render asserts.
_RENDER_OVERLAY_VARS = frozenset(
    {
        "EXPOSE_LAN",
        "FRONTEND_BIND_ADDRESS",
        "FRONTEND_HTTPS_PORT",
        "FRONTEND_HTTP_PORT",
        "PODMAN_SOCKET",
    }
)


def _render_frontend_bindings(env_overrides: dict[str, str]) -> list[tuple[str, str, str]]:
    """Render the frontend's published bindings with an env overlay.

    Real `compose config --format json` when a compose binary exists; the
    in-test emulator otherwise (skip-free by design — see module docstring).
    """
    env = {"EXPOSE_LAN": "false"}  # .env.example defaults section
    compose_file = COMPOSE_FILE
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
        # Strip the vars the render tests own BEFORE overlaying, so a developer
        # or CI-runner export (FRONTEND_HTTPS_PORT=9999 in the shell) can't move
        # what the "default env" assertions pin. os.environ keeps HOME/PATH and
        # the DOCKER_/PODMAN_ wiring the binary needs.
        proc_env = {k: v for k, v in os.environ.items() if k not in _RENDER_OVERLAY_VARS}
        proc_env.update(env)
        with RENDER_ENV_FIXTURE.open(encoding="utf-8") as fh:
            result = subprocess.run(  # noqa: S603 - argv is a literal list, never a shell string  # real
                [
                    *argv,
                    "--env-file",
                    str(RENDER_ENV_FIXTURE),
                    "-f",
                    str(compose_file),
                    "config",
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=100,
                check=False,
                env=proc_env,
            )
        assert result.returncode == 0, f"compose config failed: {result.stderr[:400]}"
        rendered = json.loads(result.stdout)
        return [
            _split_binding(
                f"{p.get('host_ip') or '0.0.0.0'}:{p.get('published') or ''}:{p['target']}"
            )
            for p in rendered["services"]["frontend"].get("ports", [])
        ]

    text = compose_file.read_text(encoding="utf-8")
    doc = yaml.load(text, Loader=_ComposeLoader)  # noqa: S506  # nosemgrep: unsafe-yaml-load
    return [
        _split_binding(_interpolate(entry, env)) for entry in doc["services"]["frontend"]["ports"]
    ]


@pytest.mark.timeout(120)
def test_render_unset_binds_loopback() -> None:
    bindings = _render_frontend_bindings(
        {"EXPOSE_LAN": "false", "FRONTEND_BIND_ADDRESS": "127.0.0.1"}
    )
    assert bindings == [
        ("127.0.0.1", "8444", "8443"),
        ("127.0.0.1", "8080", "8080"),
    ], "EXPOSE_LAN unset must publish the frontend on loopback only"


@pytest.mark.timeout(120)
def test_render_expose_lan_set_binds_wildcard() -> None:
    bindings = _render_frontend_bindings({"EXPOSE_LAN": "true", "FRONTEND_BIND_ADDRESS": "0.0.0.0"})
    assert bindings == [
        ("0.0.0.0", "8444", "8443"),
        ("0.0.0.0", "8080", "8080"),
    ], "EXPOSE_LAN=true must publish the frontend on all interfaces"


@pytest.mark.timeout(120)
def test_render_lan_flag_without_bind_var_stays_closed() -> None:
    """A hand-edited .env with EXPOSE_LAN=true but no FRONTEND_BIND_ADDRESS
    (setup.py never re-run) must still bind loopback — compose's own :- default
    is the second fail-safe layer."""
    bindings = _render_frontend_bindings({"EXPOSE_LAN": "true", "FRONTEND_BIND_ADDRESS": None})
    assert bindings == [
        ("127.0.0.1", "8444", "8443"),
        ("127.0.0.1", "8080", "8080"),
    ]


@pytest.mark.timeout(120)
def test_render_ignores_the_runners_own_bind_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real-binary branch must not inherit a developer/CI runner's exports.

    A runner with FRONTEND_BIND_ADDRESS set in its shell used to change what the
    "default env" render asserted, because the subprocess env was
    {**os.environ, **env}. The render now strips the frontend/exposure vars it
    controls before overlaying the fixture, so a hostile-looking export is
    inert. (The emulator branch was always isolated — it never reads os.environ.)
    """
    # The vars the call sites pass explicitly would be overwritten anyway; the
    # leak class is the ones they DON'T pass — FRONTEND_HTTPS_PORT exported at
    # 9999 moves the rendered host port and reddens the "default env" pins.
    monkeypatch.setenv("FRONTEND_BIND_ADDRESS", "8.8.8.8")
    monkeypatch.setenv("FRONTEND_HTTPS_PORT", "9999")
    monkeypatch.setenv("FRONTEND_HTTP_PORT", "9998")
    monkeypatch.setenv("EXPOSE_LAN", "true")
    bindings = _render_frontend_bindings(
        {"EXPOSE_LAN": "false", "FRONTEND_BIND_ADDRESS": "127.0.0.1"}
    )
    assert bindings == [
        ("127.0.0.1", "8444", "8443"),
        ("127.0.0.1", "8080", "8080"),
    ], "a runner export must not move the rendered bind or ports"


@pytest.mark.timeout(120)
def test_compose_branch_selects_a_real_invocation() -> None:
    """The candidate loop is the repo-precedent shape: `docker compose` and
    `podman compose` are SUBCOMMANDS, so which("compose") is never what to ask
    for. On any box that has docker or podman installed the real branch must
    actually fire (it silently never did while the loop asked for a binary
    named "compose"); on a bare box the loop returns None and the emulator
    carries the Done-when clause. Either way the selector must agree with
    shutil.which on the real commands — that agreement is the pin."""
    argv = _compose_argv()  # same module — call it, don't self-import (PLW0406)
    if argv is None:
        assert shutil.which("podman") is None
        assert shutil.which("docker") is None
        assert shutil.which("podman-compose") is None
        assert shutil.which("docker-compose") is None
        return
    head = argv[0]
    assert shutil.which(head) is not None, f"selected {argv!r} but {head} is not on PATH"
    assert head in ("podman", "docker", "podman-compose", "docker-compose")
    if len(argv) == 2:  # subcommand form: the second word is never a PATH lookup
        assert argv[1] == "compose"


# ---------------------------------------------------------------------------
# 5. Living docs must not keep the pre-O1.6 claims (contract rule 4 / UR-9).
# ---------------------------------------------------------------------------


def test_root_agents_md_dropped_the_pre_o16_claims() -> None:
    text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "except the frontend nginx (intentionally `0.0.0.0`" not in text, (
        "AGENTS.md still claims the frontend is intentionally 0.0.0.0 — after "
        "O1.6 that is only the EXPOSE_LAN=true mode"
    )
    assert "(until then nginx publishes" not in text, (
        "AGENTS.md still defers the binding to a future O1.6 that has landed"
    )
    assert "both bound to 0.0.0.0" not in text, (
        "the Frontend Port Note must state the conditional bind, not 0.0.0.0 flat"
    )


def test_the_integration_auth_model_docstring_is_landed_too() -> None:
    """The review's third code site: a TEST docstring that narrates the shipped
    auth model reads like product documentation to whoever greps for it, so the
    sweep covers it. Read as text, not imported — the integration suite drags in
    DB/app fixtures the unit tier must not load."""
    text = (REPO_ROOT / "backend/tests/integration/test_api_protection.py").read_text(
        encoding="utf-8"
    )
    assert "(after O1.6)" not in text, (
        "the auth-model narrative in the integration suite still says O1.6 is upcoming"
    )


def test_backend_api_agents_md_dropped_the_forward_reference() -> None:
    text = (REPO_ROOT / "backend/api/AGENTS.md").read_text(encoding="utf-8")
    assert "after `O1.6` the 127.0.0.1 binding is the boundary" not in text, (
        "backend/api/AGENTS.md still says O1.6 is upcoming"
    )


@pytest.mark.parametrize(
    "doc",
    [
        "docs/_includes/auth-model.md",
        "docs/operator/admin/security.md",
        "backend/api/middleware/README.md",
        "docs/architecture/security/README.md",
        "docs/architecture/dataflows/api-request-flow.md",
    ],
)
def test_exposure_docs_dropped_the_forward_reference(doc: str) -> None:
    # The living register (docs/vss-integration/17-action-plan.md) QUOTES the
    # old AGENTS.md wording inside a dated [V] discovery entry — that record
    # stays as written until ISS-029 closes with F1.3. The parametrized files
    # are live docs; the family assertion is the UR-9 sweep as a regression
    # gate: any live doc that later calls O1.6 future fails here, not on a
    # future grep. (docs/uplevel/50-coordination.md sequences O1.6 *after*
    # B1.5 — package order, not the bind — so it is deliberately out of scope.)
    text = (REPO_ROOT / doc).read_text(encoding="utf-8")
    assert "(until then nginx publishes on `0.0.0.0`)" not in text, (
        f"{doc} still defers the loopback bind to a future O1.6 that has landed"
    )
    assert "after `O1.6`" not in text, f"{doc} still says O1.6 is upcoming"


@pytest.mark.parametrize(
    "doc",
    [
        "docs/architecture/overview.md",
        "docs/architecture/system-overview/deployment-topology.md",
        "docs/getting-started/first-run.md",
        "docs/architecture/security/network-security.md",
    ],
)
def test_port_and_topology_docs_state_the_landed_bind(doc: str) -> None:
    """Second sweep pass (O1.6 review, blocker): the forward-reference family
    is bigger than the auth-model pages the first pass swept. These four state
    the frontend's bind as current fact in a PORT or TOPOLOGY table — the
    places an operator reads when deciding whether the box is reachable. A
    blanket ban on the string 0.0.0.0 is deliberately NOT asserted here: the
    conditional form (`EXPOSE_LAN=true` flips it) is correct and lives in
    network-security.md and env-reference.md. These pins are per-site."""
    text = (REPO_ROOT / doc).read_text(encoding="utf-8")
    assert "except the frontend" not in text, (
        f"{doc} still carves the frontend out of the loopback rule as current fact"
    )
    assert "(all interfaces) rather than loopback" not in text, (
        f"{doc} still says the frontend binds all interfaces by design"
    )
    assert "after O1.6" not in text, f"{doc} still says O1.6 is upcoming"
    assert "after `O1.6`" not in text, f"{doc} still says O1.6 is upcoming"


# The inverse-claim FAMILY, stated as claims rather than phrases. Round 1 pinned
# the deferral phrase ("after `O1.6`"), round 2 pinned one literal paraphrase
# ("except the frontend"), and each round's own grep missed the next wording —
# because the claim ("the frontend is the one port published wild") can be
# written any number of ways. So this gate matches the CLAIM shape across the
# whole port-doc family: anything that carves the frontend out of the loopback
# rule, or calls it the exception that is bound/published `0.0.0.0`, or says a
# host port is open to the network, fails here regardless of phrasing. Prose is
# whitespace-normalized first so a claim wrapped across lines still matches.
#
# The pattern is scoped to the port-doc family deliberately (round-1's live
# `Settings` gate is the same idea in product code: it catches the string
# whoever writes it, wherever). New port docs join the list; the pattern is
# what makes a missing flip loud instead of quiet.
_INVERSE_BIND_CLAIMS: tuple[tuple[str, str], ...] = (
    ("carves the frontend out of the loopback rule", r"except[^.]{0,80}frontend"),
    (
        "calls the frontend the exception bound to the wildcard",
        r"exception[^.]{0,40}(?:bound|binds?|publishes?)[^.]{0,12}0\.0\.0\.0",
    ),
    (
        "says a host port is open to the network",
        r"only[^.]{0,60}host port[^.]{0,40}open to the network",
    ),
    (
        "lists a frontend row as published on the wildcard for users",
        r"published [`\"]?0\.0\.0\.0[`\"]? — user access",
    ),
)

_PORT_DOC_FAMILY: tuple[str, ...] = (
    "README.md",
    "docs/operator/README.md",
    "docs/operator/deployment/README.md",
    "docs/operator/admin/security.md",
    "docs/architecture/security/network-security.md",
    "docs/getting-started/first-run.md",
    "docs/architecture/overview.md",
    "docs/architecture/system-overview/deployment-topology.md",
    # Sixth paraphrase the claim pattern caught that no phrase sweep had:
    # "Every mapping above except the two frontend ports is published on
    # 127.0.0.1 only" in a port-mapping table.
    "docs/diagrams/README.md",
)


@pytest.mark.parametrize("doc", _PORT_DOC_FAMILY)
def test_port_doc_family_states_the_landed_bind_by_claim(doc: str) -> None:
    """Claim-level sweep gate (O1.6 review round 2, the structural fix).

    O1.6 made the frontend's published ports loopback-by-default, so every
    sentence anywhere an operator reads reachability that still describes the
    OLD wildcard default is now false advice — including the firewall recipes,
    which would have an operator fence a port that is already shut. Phrase
    bans cannot catch that (three rounds proved it); this bans the claims.
    Conditional prose about ``EXPOSE_LAN=true`` staying wildcard is correct and
    does not match: the claims below are all the *default-state* shape.
    """
    text = (REPO_ROOT / doc).read_text(encoding="utf-8")
    normalized = re.sub(r"\s+", " ", text)
    for description, pattern in _INVERSE_BIND_CLAIMS:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match is not None:
            raise AssertionError(
                f"{doc} still {description} — O1.6 landed the loopback default, "
                f"so this is false operator advice. Matched: {match.group(0)!r}"
            )


def test_shipped_field_descriptions_do_not_defer_o16() -> None:
    """UR-9 in PRODUCT code, where no doc-pin reaches.

    A pydantic Field description is not a comment: FastAPI renders it into the
    OpenAPI schema, so "after O1.6 the frontend then binds to 127.0.0.1" was an
    endpoint-visible claim that the landed change had not happened. The gate
    reads the descriptions off the live model.
    """
    from backend.core.config import Settings

    for name in ("expose_lan", "admin_enabled"):
        description = Settings.model_fields[name].description or ""
        assert "after O1.6" not in description, (
            f"Settings.{name} description still defers the bind to a future O1.6 "
            "(this string ships in the OpenAPI schema)"
        )
        assert "until O1.6" not in description, f"Settings.{name} still says O1.6 is upcoming"
