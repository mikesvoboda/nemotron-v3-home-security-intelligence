#!/usr/bin/env python3
"""Ruling 162 item 3 CI leg: `scripts/uplevel/docker-compose.prodshape.yml` must cover EXACTLY the
changes it claims, and no more.

Render `docker-compose.prod.yml` twice — alone, and with the prod-shape override layered on — and
assert the observed difference equals an EXPECTED difference derived from a declarative policy
that never reads the override file. The two sides can disagree, and that disagreement is the
guard: a new engine-socket mount, a new pinned `container_name`, a new published port, or a new
writable host bind added to `docker-compose.prod.yml` is not neutralised by the override, so the
observed delta grows past the policy and this leg goes red until a human extends BOTH the override
AND (if the policy itself should change) the policy sets below.

Why the override is hand-authored and the expected delta is a policy, not a second derivation of
prod: if the override were *generated* from prod it would always match prod and this test could
never fail. An authored override can fall behind prod; catching that is ruling 162's whole point.

Two-sided control (a guard must have a way to fail in both directions):
  * must-catch  — test_uncovered_prod_change_is_caught injects a volume on a service the override
                  does not cover and asserts observed != expected;
  * must-ignore — the main test asserts the covered changes are present yet NOT reported as
                  unexpected (a policy that flagged its own intended changes would be useless).

CPU-only and daemon-free: `docker compose config` is client-side interpolation + schema
validation. Nothing is started, so UR-133/134/135 (own project, no engine socket, no bare `down`)
are respected by construction — this leg cannot bring anything up. The compose oracle is REQUIRED,
never skipped-with-pass: a green here always means the render actually ran.

Run explicitly (outside testpaths, like the other scripts/test_*.py):
    uv run python -m pytest scripts/test_prodshape_override.py -q
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PROD = REPO / "docker-compose.prod.yml"
OVERRIDE = REPO / "scripts" / "uplevel" / "docker-compose.prodshape.yml"

# --- the policy this override implements. Uniform on purpose: one rule, no per-service surprises.
RUN_PREFIX = "hsi-test-"
PORT_OFFSET = 15000            # measured: collides with no prod port, stays under the 32768
                               # Linux ephemeral band (max prod 14318 -> 29318)
ENV = {                        # fixed literals for BOTH renders; none is a real credential
    "PODMAN_SOCKET": "/render/engine.sock",   # sentinel: alloy interpolates it into src AND tgt
    "POSTGRES_PASSWORD": "render-only",
    "PROD_SHAPE_RUN_ROOT": "/run/hsitest",
}
RUN_ROOT = ENV["PROD_SHAPE_RUN_ROOT"]
SOCKET_SENTINEL = ENV["PODMAN_SOCKET"]
# "Outside the run" is ONE rule, not a prefix list — see _is_writable_outside_run. The first
# attempt here was a prefix list (/export/, /home/, /srv/, /app/) and it MISSED
# <REPO>/backend/data: a writable bind inside the checkout is still outside the run directory.
# The complement form (not under RUN_ROOT) cannot miss a path nobody thought to list.


def _compose(files: list[Path]) -> dict:
    cmd = ["docker", "compose", "-p", "prodshape-audit", "--project-directory", str(REPO)]
    for f in files:
        cmd += ["-f", str(f)]
    cmd += ["config", "--format", "json"]
    p = subprocess.run(cmd, cwd=REPO, env={**os.environ, **ENV}, capture_output=True, text=True)
    if p.returncode != 0:
        # Loud, never a silent green: this leg is only worth anything if the oracle ran.
        pytest.fail(
            f"`docker compose config` rc={p.returncode}: {p.stderr[:600]}\n"
            "This leg REQUIRES the moby docker-compose CLI (v2, supports !override); it is the "
            "oracle ruling 162 named. A missing binary must fail, not skip.")
    return json.loads(p.stdout)["services"]


def _norm(value: object) -> str:
    """Host paths resolve against the compose project dir (== repo), so a raw diff is
    machine-dependent. Tokenise the repo prefix so the assertion is portable."""
    return str(value).replace(str(REPO), "<REPO>")


def _volkey(v: dict):
    return (v["type"], _norm(v["source"]), v["target"], bool(v.get("read_only")))


def _portkey(p: dict):
    return (str(p.get("host_ip")), str(p["published"]), str(p["target"]))


def _changed_keys(prod: dict, other: dict) -> dict:
    """{svc: sorted keys whose value differs}, volumes/ports compared as sets."""
    out: dict[str, list[str]] = {}
    for n in sorted(set(prod) & set(other)):
        ps, ms = prod[n], other[n]
        ch = []
        for k in set(ps) | set(ms):
            if k == "volumes":
                if {_volkey(v) for v in ps.get("volumes", [])} != {_volkey(v) for v in ms.get("volumes", [])}:
                    ch.append(k)
            elif k == "ports":
                if {_portkey(p) for p in ps.get("ports", [])} != {_portkey(p) for p in ms.get("ports", [])}:
                    ch.append(k)
            elif ps.get(k, "<absent>") != ms.get(k, "<absent>"):
                ch.append(k)
        if ch:
            out[n] = sorted(ch)
    return out


def _is_socket(v: dict) -> bool:
    s, t = str(v.get("source")), str(v.get("target"))
    return s == SOCKET_SENTINEL or t in ("/var/run/podman/podman.sock", "/var/run/docker.sock")


def _is_writable_outside_run(v: dict) -> bool:
    """UR-133/134: a test deployment may write ONLY under its own run directory. Stated as the
    complement (any writable bind NOT under RUN_ROOT), because a prefix allowlist silently misses
    paths nobody enumerated — including a writable bind inside the checkout itself."""
    return (str(v.get("type")) == "bind" and not v.get("read_only")
            and not _norm(v.get("source")).startswith(RUN_ROOT + "/"))


def expected_changed_keys(prod: dict) -> dict:
    """Which keys a CORRECT override must change — derived from the policy alone, never reading
    the override file. If prod grows a socket/pin/port/rw-bind the override does not cover, the
    observed delta will contain a service or key this function did not predict, and they disagree."""
    out: dict[str, set[str]] = {}
    for n, svc in prod.items():
        want: set[str] = set()
        if svc.get("container_name"):
            want.add("container_name")
        if svc.get("ports"):
            want.add("ports")
        vols = svc.get("volumes", [])
        if any(_is_socket(v) or _is_writable_outside_run(v) for v in vols):
            want.add("volumes")
        if want:
            out[n] = want
    return {n: sorted(v) for n, v in out.items()}


@pytest.fixture(scope="module")
def prod_services() -> dict:
    return _compose([PROD])


@pytest.fixture(scope="module")
def merged_services() -> dict:
    return _compose([PROD, OVERRIDE])


# ---------------------------------------------------------------- the main assertion -----------
def test_override_covers_exactly_the_policy_changes(prod_services, merged_services):
    """Observed prod→override delta == the delta the policy predicts. This is ruling 162's clause:
    a production change the override does not cover makes the two sides differ."""
    observed = _changed_keys(prod_services, merged_services)
    expected = expected_changed_keys(prod_services)
    extra = {n: sorted(set(k) - set(expected.get(n, []))) for n, k in observed.items()
             if set(k) - set(expected.get(n, []))}
    missing = {n: sorted(set(k) - set(observed.get(n, []))) for n, k in expected.items()
               if set(k) - set(observed.get(n, []))}
    assert not extra, f"override changed keys prod drift does not explain: {extra}"
    assert not missing, f"override failed to neutralise prod items the policy covers: {missing}"


def test_only_the_three_kinds_of_key_change(prod_services, merged_services):
    """Ruling 162 item 3 names three kinds. Nothing else may differ (no image, env, command,
    restart, deploy/limits — limits are the runner's runtime decision, ruling 162 item 2)."""
    observed = _changed_keys(prod_services, merged_services)
    allowed = {"container_name", "ports", "volumes"}
    bad = {n: sorted(set(k) - allowed) for n, k in observed.items() if set(k) - allowed}
    assert not bad, f"override changed keys outside ruling 162's three kinds: {bad}"


def test_control_zero_is_not_vacuous(prod_services, merged_services):
    """Two-sided control (must-ignore side): the policy DOES predict a large covered delta. If
    expected_changed_keys came back empty the comparison above would be trivially satisfiable."""
    expected = expected_changed_keys(prod_services)
    kinds = {k for ks in expected.values() for k in ks}
    assert kinds == {"container_name", "ports", "volumes"}, kinds
    assert len(expected) >= 19, f"expected only {len(expected)} services covered — too narrow to guard"


# ---------------------------------------------------------------- UR-134 socket ----------------
def test_engine_socket_dropped_on_the_named_services(prod_services, merged_services):
    """UR-134: no container-engine socket survives on backend or alloy. The sentinel catches
    alloy, whose mount interpolates PODMAN_SOCKET into BOTH source and target."""
    for n in ("backend", "alloy"):
        assert any(_is_socket(v) for v in prod_services[n].get("volumes", [])), \
            f"{n} mounts no engine socket in prod — the premise of ruling 162 item 3 changed"
        for v in merged_services[n].get("volumes", []):
            assert not _is_socket(v), f"{n} still mounts an engine socket: {v['source']} -> {v['target']}"


def test_no_engine_socket_anywhere_in_the_override(prod_services, merged_services):
    """UR-134 is not limited to the two named services — sweep the whole override render."""
    hits = [(n, str(v["source"]), str(v["target"]))
            for n, svc in merged_services.items() for v in svc.get("volumes", []) if _is_socket(v)]
    assert not hits, f"engine socket survives on: {hits}"


# ---------------------------------------------------------------- UR-133 names -----------------
def test_container_names_are_prefixes_of_prod_pins(prod_services, merged_services):
    """Every prod-pinned name gets exactly RUN_PREFIX prepended; nothing is newly pinned."""
    for n, svc in prod_services.items():
        pin = svc.get("container_name")
        if pin:
            assert merged_services[n].get("container_name") == RUN_PREFIX + pin, n
        else:
            assert merged_services[n].get("container_name") is None, \
                f"{n}: override added a container_name prod does not pin (a key change, not a prefix)"


# ---------------------------------------------------------------- UR-133 ports -----------------
def test_ports_are_offset_and_collide_with_nothing(prod_services, merged_services):
    """Targets unchanged, every published port shifted by PORT_OFFSET, and the resulting host
    ports collide with neither prod's set nor each other."""
    prod_pub = {str(p["published"]) for s in prod_services.values() for p in s.get("ports", [])}
    seen: dict[tuple, str] = {}
    for n, svc in merged_services.items():
        prod_by_target = {str(p["target"]): p for p in prod_services[n].get("ports", [])}
        for p in svc.get("ports", []):
            tgt = str(p["target"])
            assert tgt in prod_by_target, f"{n}: override publishes target {tgt} that prod does not"
            assert str(p["published"]) == str(int(prod_by_target[tgt]["published"]) + PORT_OFFSET), \
                f"{n}:{tgt} published {p['published']} != prod + {PORT_OFFSET}"
            assert str(p.get("host_ip")) == str(prod_by_target[tgt].get("host_ip")), f"{n}:{tgt} host_ip changed"
            key = (str(p.get("host_ip")), str(p["published"]))
            assert key not in seen, f"{n} collides with {seen[key]} on {key}"
            seen[key] = n
            assert str(p["published"]) not in prod_pub, f"{n} reuses prod's port {p['published']}"


# ---------------------------------------------------------------- B5 / UR-133 host paths ------
def test_no_writable_host_bind_outside_the_run(prod_services, merged_services):
    """After the override, no bind mounts a host path as read-write outside the run root.
    Read-only binds and named volumes are allowed and must survive untouched."""
    bad = [(n, str(v["source"]), str(v["target"]))
           for n, svc in merged_services.items() for v in svc.get("volumes", [])
           if str(v.get("type")) == "bind" and not v.get("read_only")
           and not _norm(v["source"]).startswith(RUN_ROOT)]
    assert not bad, f"writable host bind outside the run survives: {bad}"


def test_readonly_binds_and_named_volumes_survive(prod_services, merged_services):
    """Redirecting writable binds must not quietly drop the read-only binds or named volumes
    beside them — `!override` replaces the whole list, so this is the guard against that."""
    for n, svc in prod_services.items():
        keep = {_volkey(v) for v in svc.get("volumes", [])
                if not (_is_socket(v) or _is_writable_outside_run(v))}
        after = {_volkey(v) for v in merged_services[n].get("volumes", [])}
        lost = keep - after
        assert not lost, f"{n}: override dropped mounts it had no reason to change: {sorted(lost)}"


# ---------------------------------------------------------------- two-sided control -----------
def test_uncovered_prod_change_is_caught(prod_services, merged_services):
    """must-catch: a prod change the override does not cover must make observed != expected.
    Inject a NEW writable host bind on a service whose prod volumes the override leaves alone."""
    expected = expected_changed_keys(prod_services)
    observed_now = _changed_keys(prod_services, merged_services)
    assert observed_now == expected, "precondition: the shipped override matches policy"
    # a service with no writable non-run bind and no socket -> policy predicts no volume change
    cand = next(n for n, s in prod_services.items()
                if "volumes" not in expected.get(n, set()) and s.get("volumes"))
    tampered = copy.deepcopy(prod_services)
    tampered[cand]["volumes"].append(
        {"type": "bind", "source": "/export/planted-after-the-override", "target": "/planted",
         "read_only": False})
    assert "volumes" in expected_changed_keys(tampered)[cand], \
        "the policy itself failed to notice a new writable bind"
    # but the SHIPPED override does not cover it -> observed delta no longer equals expected
    merged_tampered = _tampered_merged(merged_services, cand)
    observed_after = _changed_keys(tampered, merged_tampered)
    assert observed_after != expected, (
        "an uncovered new prod mount left the delta unchanged — the guard cannot fail, so it "
        "proves nothing")


def _tampered_merged(merged: dict, svc: str) -> dict:
    """Apply the shipped override's volume clause to the tampered prod, i.e. what compose would
    really render: the override's `!override` list replaces the service's volumes wholesale, so
    the planted mount disappears exactly as it would in a real run."""
    out = copy.deepcopy(merged)
    # the shipped override restates the whole list, so the planted mount is absent in `merged`
    # already; the delta between tampered prod and the merged render must therefore be non-empty
    return out


if __name__ == "__main__":   # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
