"""[r162] The engine socket follows the orchestrator setting.

Done-when (`docs/uplevel/packages/ops.md:450-452`, ruling 162 `6156947315`), rendered contract:

  1. a production config rendered with the orchestrator OFF mounts NO engine socket;
  2. one with it ON mounts it as before;
  3. `O2.5`'s override drift test still passes (that clause is owned by
     `test_prodshape_override.py`; this file must not break it, and does not re-run it here).

Plus the package's scope box: "the `:?` interpolation no longer demands a value when nothing uses
it" — so a render with the orchestrator OFF and `PODMAN_SOCKET` UNSET must SUCCEED, not die on the
hard-interpolation the way `docker-compose.prod.yml:473`/`:1584` do today.

These are RENDER assertions on purpose. The mechanism is an open owner-tier design question
(Compose has no conditional volume item: an interpolated entry that expands to nothing is
`invalid empty volume spec`, and `${VAR:+…}` treats the string "false" as truthy — both measured on
the repo's CLI v5.5.1). So this file reads the `docker compose config` output and says nothing about
whether the fix is an `include:` fragment, a second service, or anything else. Whichever mechanism
makes all four pins green wins; the test does not pre-select it.

The DEFAULT direction is not cosmetic. `backend/core/config.py:134-138` is `enabled: bool =
Field(True, …)`, so an unset `ORCHESTRATOR_ENABLED` means the orchestrator is ON. A render that
dropped the socket on the unset flag would silently strip it from the live host on the next redeploy
that forgot to write the variable. `test_the_unset_flag_keeps_the_socket` pins that direction.

Run explicitly (scripts/test_*.py sits outside pyproject testpaths, like every gate suite here):
    uv run python -m pytest scripts/test_orchestrator_engine_socket.py -q
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PROD = REPO / "docker-compose.prod.yml"

# Fixed literal, NOT a real path: it only has to be recognisable as the engine socket after the
# render. Same sentinel the O2.5 drift test uses, so both files agree on what "the socket" is.
SOCKET_SENTINEL = "/render/engine.sock"
# alloy interpolates PODMAN_SOCKET into BOTH source and target, so a target-only check would miss
# it — the exact blind spot scripts/feature_check.py:573-580 documents. Catch source OR target.
ENGINE_SOCKET_TARGETS = frozenset(
    {"/var/run/podman/podman.sock", "/var/run/docker.sock", "/run/docker.sock"}
)
NAMED = ("backend", "alloy")  # the two services ruling 162 names


def _interpolated_names() -> frozenset[str]:
    """Every name the prod file interpolates, read out of the file itself — not a hand-list, so a
    newly interpolated variable is scrubbed the moment it lands (the drift test's rule)."""
    text = PROD.read_text(encoding="utf-8")
    found = set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)", text))
    found |= set(re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", text))
    return frozenset(found)


INTERPOLATED = _interpolated_names()


def _clean_env(**extra: str | None) -> dict[str, str]:
    """Host env minus everything prod interpolates, plus the fixed render values. `None` in `extra`
    means 'ensure this one is also absent' (for the PODMAN_SOCKET-unset case)."""
    env = {k: v for k, v in os.environ.items() if k not in INTERPOLATED}
    env["POSTGRES_PASSWORD"] = "render-only"  # pragma: allowlist secret
    for key, value in extra.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return env


def _render(**extra: str | None) -> tuple[int, str, dict]:
    cmd = ["docker", "compose", "-p", "r162-audit", "--project-directory", str(REPO),
           "-f", str(PROD), "config", "--format", "json"]
    p = subprocess.run(cmd, cwd=REPO, env=_clean_env(**extra), capture_output=True, text=True)
    if p.returncode != 0:
        return p.returncode, p.stderr.strip(), {}
    # A 0 rc that is not JSON raises here — a loud failure, never a silent green.
    return 0, "", json.loads(p.stdout)["services"]


def _is_socket(v: dict) -> bool:
    s, t = str(v.get("source")), str(v.get("target"))
    return s == SOCKET_SENTINEL or t in ENGINE_SOCKET_TARGETS


def _socket_mounts(services: dict) -> dict[str, list[str]]:
    return {
        n: [f"{v.get('source')}->{v.get('target')}"
            for v in (services.get(n, {}).get("volumes") or []) if _is_socket(v)]
        for n in NAMED
    }


# Every render leg needs the moby docker-compose CLI. A missing binary FAILS — a skipped socket
# guard reads as a green package (test_prodshape_override.py:123-132 doctrine).
def _require_cli() -> None:
    probe = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
    if probe.returncode != 0:
        pytest.fail("`docker compose` is unavailable; this socket guard REQUIRES the moby CLI "
                    "(it is the oracle ruling 162 named). A missing binary must fail, not skip.")


# ------------------------------------------------------------------ Done-when clause 1 ----------
def test_orchestrator_off_mounts_no_engine_socket():
    """Clause 1: with the orchestrator OFF (and the socket value still supplied, to isolate the
    mount condition from the `:?` demand), neither backend nor alloy mounts an engine socket."""
    _require_cli()
    rc, err, services = _render(PODMAN_SOCKET=SOCKET_SENTINEL, ORCHESTRATOR_ENABLED="false")
    assert rc == 0, f"orchestrator-off render failed rc={rc}: {err[:400]}"
    hits = _socket_mounts(services)
    assert not any(hits.values()), f"engine socket survives with the orchestrator OFF: {hits}"


# ------------------------------------------------------------------ Done-when clause 2 ----------
def test_orchestrator_on_mounts_the_socket_as_before():
    """Clause 2: with the orchestrator ON, backend mounts it into the container path and alloy
    mounts it at the host path — the behaviour `docker-compose.prod.yml:473`/`:1584` have today."""
    _require_cli()
    rc, err, services = _render(PODMAN_SOCKET=SOCKET_SENTINEL, ORCHESTRATOR_ENABLED="true")
    assert rc == 0, f"orchestrator-on render failed rc={rc}: {err[:400]}"
    hits = _socket_mounts(services)
    for n in NAMED:
        assert hits[n], f"{n} lost its engine socket with the orchestrator ON: {hits}"


# ------------------------------------------------------------------ safe-default pin ----------
def test_the_unset_flag_keeps_the_socket():
    """The orchestrator's OWN default is ON (`backend/core/config.py:134-138`), so a render that
    does not set ORCHESTRATOR_ENABLED must keep mounting the socket. Getting this backwards would
    silently strip it from the live host on the next redeploy that omitted the variable."""
    _require_cli()
    rc, err, services = _render(PODMAN_SOCKET=SOCKET_SENTINEL, ORCHESTRATOR_ENABLED=None)
    assert rc == 0, f"unset-flag render failed rc={rc}: {err[:400]}"
    hits = _socket_mounts(services)
    for n in NAMED:
        assert hits[n], f"{n} lost its engine socket on an UNSET flag (default must be ON): {hits}"


# ------------------------------------------------------------------ scope box: the `:?` ----------
def test_orchestrator_off_needs_no_socket_value():
    """Package scope box: "the `:?` interpolation no longer demands a value when nothing uses it."
    Today `docker-compose.prod.yml:473` uses `${PODMAN_SOCKET:?…}`, so an unset value fails the
    WHOLE render even with the orchestrator off and nothing wanting the socket — measured rc=1,
    `error while interpolating services.backend.volumes`. After the fix this render must succeed."""
    _require_cli()
    rc, err, _services = _render(PODMAN_SOCKET=None, ORCHESTRATOR_ENABLED="false")
    assert rc == 0, (
        "orchestrator-off render still demands PODMAN_SOCKET (the `:?` survives): "
        f"rc={rc}: {err[:400]}"
    )
