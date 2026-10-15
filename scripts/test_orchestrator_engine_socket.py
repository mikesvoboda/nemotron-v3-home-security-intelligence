"""[r162] The engine socket follows the orchestrator setting.

Done-when (`docs/uplevel/packages/ops.md:450-451` — the file is 451 lines, ruling 162 `6156947315`),
as narrowed by owner ruling 186 `6181436641` (2026-10-15T00:20Z, option b — gate backend only),
rendered contract:

  1. a production config rendered with the orchestrator OFF mounts NO engine socket **in
     `backend`** — and `alloy` KEEPS its unconditional mount (ruling 186 item 2), because Alloy
     uses the socket for monitoring, not orchestration (`monitoring/alloy/config.alloy:19`,
     `:52`, `:161`);
  2. one with it ON mounts it in both, as before;
  3. `O2.5`'s override drift test still passes (that clause is owned by
     `test_prodshape_override.py`; this file must not break it, and does not re-run it here).

The package's scope box said "the `:?` interpolation no longer demands a value when nothing uses
it"; ruling 186 item 2 STRUCK that clause — with alloy's mount unconditional, alloy's
`${PODMAN_SOCKET:?…}` (`docker-compose.prod.yml:1584`) still demands the value on every render,
which #7114's owner letter showed is accidental protection worth keeping (a prod stack with an
invalid Alloy config cannot boot at all today). `test_alloy_always_demands_the_socket_value`
pins that protection against a future relaxation.

These are RENDER assertions on purpose (Compose has no conditional volume item: an interpolated
entry that expands to nothing is `invalid empty volume spec`, and `${VAR:+…}` treats the string
"false" as truthy — both measured on the repo's CLI v5.5.1). The file reads the
`docker compose config` output, so it pins the CONTRACT, not one file's spelling of it: the shipped
mechanism (owner ruling 186 item 3, ops-a's call — `ac84fd7d9`) is the top-level `include:` whose
interpolated PATH names one of two fragments, and the pins here would hold unchanged if a future
commit re-expressed that mechanism differently, which is the point.

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
    """Clause 1 as ruled (ruling 186 items 1-2): with the orchestrator OFF (and the socket value
    still supplied, to isolate the mount condition from the `:?` demand), `backend` mounts no
    engine socket. `alloy` KEEPS its mount — its use of the socket is monitoring, not
    orchestration, so a flag-gated alloy would boot "running" with no container logs or profiling.
    Both halves are asserted: a fix that dropped alloy's mount too would pass a `not any()` check
    while breaking monitoring, so this pin cannot be satisfied by over-gating."""
    _require_cli()
    rc, err, services = _render(PODMAN_SOCKET=SOCKET_SENTINEL, ORCHESTRATOR_ENABLED="false")
    assert rc == 0, f"orchestrator-off render failed rc={rc}: {err[:400]}"
    hits = _socket_mounts(services)
    assert not hits["backend"], f"backend keeps the engine socket with the orchestrator OFF: {hits}"
    assert hits["alloy"], f"alloy LOST its monitoring socket (ruling 186 keeps it unconditional): {hits}"


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


# ------------------------------------------------------------------ loud-failure: the values gap ----------
# pydantic 2.13.5's lenient bool coercion, re-measured at this head: it accepts every
# case-insensitive spelling of true/false/yes/no/on/off/t/f/y/n plus `1` and `0` — 82 spellings, of
# which 80 name no fragment. The list below is those 80 collapsed to their distinct SHAPES (the
# case-permutations of one family all fail the same way, on the same line of code), and every entry
# was measured as accepted by pydantic and rejected by compose at this head. Silent acceptance of a
# non-canonical spelling is the bad outcome: `1` resolves to no file, and a mechanism that swallowed
# that would boot the orchestrator ON with no socket (or OFF holding one) — a shape nobody wrote
# down. The control for these legs is `test_orchestrator_on_mounts_the_socket_as_before`: same CLI,
# same `_render()`, same env scrub, rc=0. If prod.yml were broken wholesale, that leg goes red
# first, so rc!=0 here cannot be an unrelated failure — and the assertion pins WHICH fragment the
# renderer looked for, which a generic breakage cannot satisfy.
NON_CANONICAL_BOOL_SPELLINGS = (
    "1", "0",                                   # digits
    "t", "T", "f", "F", "y", "Y", "n", "N",     # single letters
    "yes", "Yes", "YES",                        # yes-family
    "no", "No", "NO",                           # no-family
    "on", "On", "ON",                           # on-family
    "off", "Off", "OFF",                        # off-family
    "True", "TRUE",                             # true-family, non-canonical case
    "False", "FALSE",                           # false-family, non-canonical case
)


@pytest.mark.parametrize("spelling", NON_CANONICAL_BOOL_SPELLINGS)
def test_a_non_canonical_flag_spelling_fails_the_render_loudly(spelling: str):
    """The values gap #7114's mechanism note names, pinned. `ORCHESTRATOR_ENABLED` reaches compose
    as a literal string, and the condition lives in a FILENAME, so a spelling pydantic accepts but
    no fragment carries has no file to include: the render must fail, and name the fragment it
    looked for. Failing loudly is the designed behaviour (see the two fragment headers) — this pin
    is what keeps it loud."""
    _require_cli()
    rc, err, _services = _render(PODMAN_SOCKET=SOCKET_SENTINEL, ORCHESTRATOR_ENABLED=spelling)
    assert rc != 0, (
        f"ORCHESTRATOR_ENABLED={spelling!r} RENDERED (rc=0). pydantic accepts this spelling, but "
        f"docker-compose.engine-{spelling}.yml does not exist, so a render that succeeded mounted "
        f"a socket on a condition no fragment expresses — the silent-wrong-shape outcome."
    )
    expected = f"docker-compose.engine-{spelling}.yml"
    assert expected in err and "no such file" in err, (
        f"ORCHESTRATOR_ENABLED={spelling!r} failed rc={rc} but not on the missing fragment "
        f"(expected {expected!r} + 'no such file' in the error): {err[:400]}"
    )


# ------------------------------------------------------------------ kept protection: the `:?` ----------
def test_alloy_always_demands_the_socket_value():
    """The struck scope box, pinned in its ruled shape (ruling 186 item 2): alloy's mount stays
    unconditional and its `${PODMAN_SOCKET:?…}` stays, so a render with the orchestrator OFF and
    `PODMAN_SOCKET` UNSET must still FAIL. #7114's owner letter showed this is worth keeping:
    alloy reads env("PODMAN_SOCKET") for container discovery, log scraping and profiling targets,
    so an unset path with a surviving mount means a monitoring stack that looks healthy while
    starved — the `:?` is what makes that state unrenderable today. The error must name ALLOY's
    interpolation (not backend's): backend's `:?` goes away with the fix; alloy's must survive,
    and an error only naming backend would mean alloy's got relaxed too."""
    _require_cli()
    rc, err, _services = _render(PODMAN_SOCKET=None, ORCHESTRATOR_ENABLED="false")
    assert rc != 0, (
        "orchestrator-off render SUCCEEDED with PODMAN_SOCKET unset — the `:?` demand was "
        "relaxed, which ruling 186 item 2 forbids while alloy's mount stays unconditional"
    )
    assert re.search(r"services\.alloy\.volumes", err), (
        f"the failing interpolation is not alloy's (expected services.alloy.volumes in the "
        f"demand): rc={rc}: {err[:400]}"
    )
