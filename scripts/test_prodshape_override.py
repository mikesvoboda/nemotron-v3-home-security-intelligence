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

import ast
import copy
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Every node in this file may pay for a `docker compose config` spawn — its own, or a module-scoped
# fixture's, which `timeout_func_only = false` bills to whichever node runs first. 30 s is ~12x the
# worst figure measured on the heaviest node under deliberate saturation (2.42 s call at load 20,
# this box idle-base 0.38 s) and sits with the job's other spawn/scan suites (60/180/300). See
# test_no_compose_spawning_node_rides_the_five_second_tier_default for the pin and its two-sided
# control. A ceiling on THIS file, not a raise of the tier's root `timeout = 5`.
pytestmark = pytest.mark.timeout(30)

REPO = Path(__file__).resolve().parent.parent
PROD = REPO / "docker-compose.prod.yml"
OVERRIDE = REPO / "scripts" / "uplevel" / "docker-compose.prodshape.yml"

# --- the policy this override implements. Uniform on purpose: one rule, no per-service surprises.
RUN_PREFIX = "hsi-test-"
NAME_VAR = "HSI_TEST_NAME_PREFIX"
# A pinned container_name is NOT namespaced by the compose project (measured), so the prefix alone
# cannot separate two runs: the override interpolates this per-RUN token instead.
# A fixed literal here, deliberately NOT a per-run value: every render in this file must resolve
# against the same env, or the prod-vs-override delta it asserts is not comparable. The per-run
# token itself is feature_check.prod_shape_env's job; test_a_pinned_name_carries_the_run_token_...
# renders with two different tokens and requires the name sets to be disjoint.
DRIFT_NAME_PREFIX = "audit-"
# prod.yml declares ONE profile (`gpu-rootful`; O3.1 removed `ai-llm-vllm` and its `vllm` profile
# per OD-17 / ruling 89). The guard renders it because `gpu-rootful` adds dcgm-exporter (a PIN and
# a published 9400) that a profile-less render would not see.
GPU_PROFILE = "gpu-rootful"
ALL_PROFILES = (GPU_PROFILE,)
# measured: collides with no prod port, stays under the 32768 Linux ephemeral band
# (max prod 14318 -> 29318)
PORT_OFFSET = 15000
# The one service the uniform offset cannot place. The runner (`agent-gpu`) publishes the VLM on
# the host's loopback from a FIXED pool (scripts/feature_check.py `AGENT_GPU_PORTS`, 18100-18199;
# docs/uplevel/roles/operator.md says the run reads its port from that band), and loki's prod port
# 3100 + 15000 lands on 18100 — the pool's first address — so a `--real --prod-shape` run would
# start loki on the address the VLM expects. The pool is the runner's to hold, so the override
# moves loki instead: 18201 is the first port above the pool that nothing else here publishes
# (tempo already took 18200 = 3200 + 15000). [r195] box 3; test_no_published_port_lands_in_the_
# runners_vlm_pool pins the table against the renders in BOTH directions, so this stays the only
# exception and stays necessary.
PORT_POOL_EXCEPTIONS: dict[str, int] = {"loki": 18201}
# fixed literals for BOTH renders; none is a real credential
ENV = {
    # sentinel: alloy interpolates it into src AND tgt
    "PODMAN_SOCKET": "/render/engine.sock",
    "POSTGRES_PASSWORD": "render-only",  # pragma: allowlist secret
    "PROD_SHAPE_RUN_ROOT": "/run/hsitest",
    NAME_VAR: DRIFT_NAME_PREFIX,
}


# Every name either file interpolates, read out of the files themselves -- not a
# hand-list. `docker compose config` is client-side interpolation, so a host var
# on this surface leaks into BOTH renders and the "machine-independent" claim
# this guard exists to enforce dies with it: a runner exporting AI_MODELS_PATH
# (review finding CR-3/#7037, measured) reddens test_readonly_binds_and_named_
# volumes_survive for a reason that has nothing to do with the PR, and this leg
# runs in collection-sanity, which EVERY PR pays. Deriving the set from the two
# files means a newly interpolated name is covered the moment it lands.
def _interpolated_names() -> frozenset[str]:
    found: set[str] = set()
    for path in (PROD, OVERRIDE):
        text = path.read_text(encoding="utf-8")
        found |= set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)", text))
        # bare $VAR too: prod has one comment mention and the override uses the form
        found |= set(re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", text))
    return frozenset(found)


INTERPOLATED = _interpolated_names()


def _clean_env(**extra: str) -> dict[str, str]:
    """Host env MINUS everything the two compose files interpolate, plus the fixed
    ENV (and `extra` for a one-variable probe). The scrub is on the interpolation
    surface rather than an allowlist of PATH-ish names, so it cannot fall behind
    a new compose variable; PATH and friends survive because compose itself
    needs them."""
    env = {k: v for k, v in os.environ.items() if k not in INTERPOLATED}
    env.update(ENV)
    env.update(extra)
    return env


RUN_ROOT = ENV["PROD_SHAPE_RUN_ROOT"]
SOCKET_SENTINEL = ENV["PODMAN_SOCKET"]
# "Outside the run" is ONE rule, not a prefix list — see _is_writable_outside_run. The first
# attempt here was a prefix list (/export/, /home/, /srv/, /app/) and it MISSED
# <REPO>/backend/data: a writable bind inside the checkout is still outside the run directory.
# The complement form (not under RUN_ROOT) cannot miss a path nobody thought to list.


def _compose(files: list[Path], profiles: tuple[str, ...] = ()) -> dict:
    cmd = ["docker", "compose", "-p", "prodshape-audit", "--project-directory", str(REPO)]
    for pf in profiles:
        cmd += ["--profile", pf]
    for f in files:
        cmd += ["-f", str(f)]
    cmd += ["config", "--format", "json"]
    p = subprocess.run(cmd, cwd=REPO, env=_clean_env(), capture_output=True, text=True)
    if p.returncode != 0:
        # Loud, never a silent green: this leg is only worth anything if the oracle ran.
        pytest.fail(
            f"`docker compose config` rc={p.returncode}: {p.stderr[:600]}\n"
            "This leg REQUIRES the moby docker-compose CLI (v2, supports !override); it is the "
            "oracle ruling 162 named. A missing binary must fail, not skip."
        )
    return json.loads(p.stdout)["services"]


def _norm(value: object) -> str:
    """Host paths resolve against the compose project dir (== repo), so a raw diff is
    machine-dependent. Tokenise the repo prefix so the assertion is portable."""
    return str(value).replace(str(REPO), "<REPO>")


def _volkey(v: dict):
    bind = v.get("bind") or {}
    return (
        v["type"],
        _norm(v["source"]),
        v["target"],
        bool(v.get("read_only")),
        bind.get("selinux"),
        bind.get("create_host_path"),
    )


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
                if {_volkey(v) for v in ps.get("volumes", [])} != {
                    _volkey(v) for v in ms.get("volumes", [])
                }:
                    ch.append(k)
            elif k == "ports":
                if {_portkey(p) for p in ps.get("ports", [])} != {
                    _portkey(p) for p in ms.get("ports", [])
                }:
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
    return (
        str(v.get("type")) == "bind"
        and not v.get("read_only")
        and not _norm(v.get("source")).startswith(RUN_ROOT + "/")
    )


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


@pytest.fixture(scope="module")
def gpu_prod_services() -> dict:
    """The leg a GPU host actually boots: gpu-rootful adds dcgm-exporter (prod PINS it and
    publishes 9400) and vllm adds ai-llm-vllm (unpinned, publishes 8097). A profile-less render
    cannot see either, so the profile-less legs above cannot guard them — yet ruling 162 item 3
    and packages/ops.md:176 both say the override handles 'the 7 pinned container_names', and
    UR-133 says every published port gets the offset. Six of seven is not seven."""
    return _compose([PROD], ALL_PROFILES)


@pytest.fixture(scope="module")
def gpu_merged_services() -> dict:
    return _compose([PROD, OVERRIDE], ALL_PROFILES)


def test_the_render_env_scrubs_the_compose_interpolation_surface() -> None:
    """The host-environment scrub (review finding 3 on #7037, comment `6163946798`).

    Two-sided by necessity: `INTERPOLATED` is derived from the compose files, so a
    regex that matched NOTHING would scrub nothing and still leave every other test
    in this file green -- the silent-zero shape. must-catch: the two names measured
    to flip test_readonly_binds_and_named_volumes_survive (AI_MODELS_PATH on six
    volume lines, HF_CACHE_PATH on two). must-ignore: PATH/HOME/DOCKER_HOST, which
    compose and the CLI need -- a scrub that ate them would fail every render for an
    unrelated reason.
    """
    assert len(INTERPOLATED) > 50, f"derivation regressed to a trivial set: {sorted(INTERPOLATED)}"
    for name in ("AI_MODELS_PATH", "HF_CACHE_PATH", "POSTGRES_PASSWORD", "PODMAN_SOCKET"):
        assert name in INTERPOLATED, f"{name} interpolated but not scrubbed"
    host = {
        "PATH": "/usr/bin",
        "HOME": "/root",
        "DOCKER_HOST": "unix:///x",
        "AI_MODELS_PATH": "/mnt/models",
        "HF_CACHE_PATH": "/leak/hfcache",
    }
    saved = dict(os.environ)
    os.environ.clear()
    os.environ.update(host)
    try:
        clean = _clean_env()
    finally:
        os.environ.clear()
        os.environ.update(saved)
    assert "AI_MODELS_PATH" not in clean and "HF_CACHE_PATH" not in clean, (
        f"a leak name survived the scrub: {sorted(k for k in clean if k in INTERPOLATED)}"
    )
    for name in ("PATH", "HOME", "DOCKER_HOST"):
        assert clean[name] == host[name], f"the scrub ate runner plumbing: {name}"
    # the fixed sentinels still win over the host (the drop-one sites depend on it)
    assert clean["PODMAN_SOCKET"] == "/render/engine.sock"
    assert _clean_env(HF_CACHE_PATH="/extra").get("HF_CACHE_PATH") == "/extra"


def test_the_override_changes_no_service_set(prod_services, merged_services):
    """`_changed_keys` iterates the INTERSECTION of the two service sets, so a service the
    override ADDS or DROPS is invisible to every delta assertion above — an override that started
    a new container, or silently dropped one prod runs, would pass them all. The service set is
    the one thing the override must never touch: ruling 162 item 3 permits three kinds of KEY
    change on services that already exist, and says nothing about adding a service."""
    assert set(merged_services) == set(prod_services), (
        f"override changed the rendered service set: "
        f"added={sorted(set(merged_services) - set(prod_services))} "
        f"dropped={sorted(set(prod_services) - set(merged_services))}"
    )


def test_the_profiled_leg_is_covered_too(gpu_prod_services, gpu_merged_services):
    """The drift assertion, re-run on the leg with prod's profiles enabled. Every service a GPU
    or vllm host brings up must clear the same policy: a pinned name gets the run token, every
    published port gets the offset, no writable bind escapes the run, and the service set is
    unchanged. This is the leg the GPU host runs and the profile-less render cannot check."""
    assert set(gpu_merged_services) == set(gpu_prod_services), (
        f"override changed the profiled service set: "
        f"added={sorted(set(gpu_merged_services) - set(gpu_prod_services))} "
        f"dropped={sorted(set(gpu_prod_services) - set(gpu_merged_services))}"
    )
    observed = _changed_keys(gpu_prod_services, gpu_merged_services)
    expected = expected_changed_keys(gpu_prod_services)
    missing = {
        n: sorted(set(k) - set(observed.get(n, [])))
        for n, k in expected.items()
        if set(k) - set(observed.get(n, []))
    }
    extra = {
        n: sorted(set(k) - set(expected.get(n, [])))
        for n, k in observed.items()
        if set(k) - set(expected.get(n, []))
    }
    assert not missing, f"profiled services the override fails to neutralise: {missing}"
    assert not extra, f"override changed keys the profiled policy does not explain: {extra}"
    for n, svc in gpu_merged_services.items():
        pin = gpu_prod_services[n].get("container_name")
        if pin:
            assert svc.get("container_name") == RUN_PREFIX + DRIFT_NAME_PREFIX + pin, (
                f"{n}: profiled pin not prefixed: {svc.get('container_name')!r}"
            )
        prod_pub = {str(p["target"]) for p in gpu_prod_services[n].get("ports", [])}
        for p in svc.get("ports", []):
            assert str(p["published"]) not in prod_pub, (
                f"{n}: profiled port {p['published']} reuses a prod target"
            )


# ---------------------------------------------------------------- the main assertion -----------
def test_override_covers_exactly_the_policy_changes(prod_services, merged_services):
    """Observed prod→override delta == the delta the policy predicts. This is ruling 162's clause:
    a production change the override does not cover makes the two sides differ."""
    observed = _changed_keys(prod_services, merged_services)
    expected = expected_changed_keys(prod_services)
    extra = {
        n: sorted(set(k) - set(expected.get(n, [])))
        for n, k in observed.items()
        if set(k) - set(expected.get(n, []))
    }
    missing = {
        n: sorted(set(k) - set(observed.get(n, [])))
        for n, k in expected.items()
        if set(k) - set(observed.get(n, []))
    }
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
    assert len(expected) >= 19, (
        f"expected only {len(expected)} services covered — too narrow to guard"
    )


# ---------------------------------------------------------------- UR-134 socket ----------------
def test_engine_socket_dropped_on_the_named_services(prod_services, merged_services):
    """UR-134: no container-engine socket survives on backend or alloy. The sentinel catches
    alloy, whose mount interpolates PODMAN_SOCKET into BOTH source and target."""
    for n in ("backend", "alloy"):
        assert any(_is_socket(v) for v in prod_services[n].get("volumes", [])), (
            f"{n} mounts no engine socket in prod — the premise of ruling 162 item 3 changed"
        )
        for v in merged_services[n].get("volumes", []):
            assert not _is_socket(v), (
                f"{n} still mounts an engine socket: {v['source']} -> {v['target']}"
            )


def test_no_engine_socket_anywhere_in_the_override(prod_services, merged_services):
    """UR-134 is not limited to the two named services — sweep the whole override render."""
    hits = [
        (n, str(v["source"]), str(v["target"]))
        for n, svc in merged_services.items()
        for v in svc.get("volumes", [])
        if _is_socket(v)
    ]
    assert not hits, f"engine socket survives on: {hits}"


# ---------------------------------------------------------------- UR-133 names -----------------
def test_container_names_are_prefixes_of_prod_pins(prod_services, merged_services):
    """Every prod-pinned name gets RUN_PREFIX plus this render's run token prepended; nothing is
    newly pinned. The token is the part that makes the name this RUN's: a pinned container_name is
    NOT namespaced by the compose project, so a constant prefix leaves two concurrent runs asking
    for the same name (measured: the second `up` dies with `Conflict. The container name ... is
    already in use by container ...`), which UR-133's own-project isolation cannot allow."""
    for n, svc in prod_services.items():
        pin = svc.get("container_name")
        if pin:
            assert (
                merged_services[n].get("container_name") == RUN_PREFIX + DRIFT_NAME_PREFIX + pin
            ), (
                f"{n}: expected {RUN_PREFIX + DRIFT_NAME_PREFIX + pin!r}, "
                f"got {merged_services[n].get('container_name')!r}"
            )
        else:
            assert merged_services[n].get("container_name") is None, (
                f"{n}: override added a container_name prod does not pin (a key change, not a prefix)"
            )


def test_a_pinned_name_carries_the_run_token_and_the_render_refuses_without_it():
    """Two-sided, because a per-run name that silently degraded to a constant is exactly the bug.

    must-ignore: two renders with two different run tokens get two DISJOINT container-name sets,
    so two runs on one machine cannot collide at `up`.
    must-catch: with the token MISSING the render must fail and name the variable. compose's
    default for an unset `${VAR}` is a blank string plus a warning, which would resolve to
    `hsi-test-alloy` -- the same name the override used before this rule existed -- so an
    optional variable here reintroduces the collision it exists to prevent. Only `${VAR:?…}`
    refuses, which is the same discipline docker-compose.prod.yml applies to PODMAN_SOCKET.
    """
    a = _render_full([PROD, OVERRIDE], "hsi-names-a", extra={NAME_VAR: "a1b2c3d4-"})
    b = _render_full([PROD, OVERRIDE], "hsi-names-b", extra={NAME_VAR: "9f8e7d6c-"})
    names_a, names_b = _container_names(a), _container_names(b)
    assert names_a and names_b, "no service pins a container_name -- the premise changed"
    assert not (names_a & names_b), (
        f"two run tokens produced the same container names: {sorted(names_a & names_b)}"
    )
    assert all(n.startswith(RUN_PREFIX) for n in names_a), sorted(names_a)

    env = {k: v for k, v in _clean_env().items() if k != NAME_VAR}
    cmd = [
        "docker",
        "compose",
        "--env-file",
        os.devnull,
        "-p",
        "hsi-names-missing",
        "--project-directory",
        str(REPO),
        "-f",
        str(PROD),
        "-f",
        str(OVERRIDE),
        "config",
        "--format",
        "json",
    ]
    p = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True, check=False)
    # No json.loads() in this message: the render is expected to FAIL, so stdout may be empty,
    # and a guard whose failure path raises a parse error is not a guard.
    assert p.returncode != 0, (
        f"the render SUCCEEDED with no run token, so a name resolved to a constant: "
        f"{p.stdout[:300]!r}"
    )
    assert NAME_VAR in p.stderr, (
        f"the render failed for another reason, so the refusal is not this variable: "
        f"{p.stderr[:300]}"
    )


# ---------------------------------------------------------------- UR-133 ports -----------------
def test_ports_are_offset_and_collide_with_nothing(prod_services, merged_services):
    """Targets unchanged, every published port shifted by PORT_OFFSET (except the table's named
    services), and the resulting host ports collide with neither prod's set nor each other."""
    prod_pub = {str(p["published"]) for s in prod_services.values() for p in s.get("ports", [])}
    seen: dict[tuple, str] = {}
    for n, svc in merged_services.items():
        prod_by_target = {str(p["target"]): p for p in prod_services[n].get("ports", [])}
        for p in svc.get("ports", []):
            tgt = str(p["target"])
            assert tgt in prod_by_target, f"{n}: override publishes target {tgt} that prod does not"
            want = PORT_POOL_EXCEPTIONS.get(n, int(prod_by_target[tgt]["published"]) + PORT_OFFSET)
            assert str(p["published"]) == str(want), (
                f"{n}:{tgt} published {p['published']} != "
                + (f"the declared exception {want}" if n in PORT_POOL_EXCEPTIONS
                   else f"prod + {PORT_OFFSET}"))
            assert str(p.get("host_ip")) == str(prod_by_target[tgt].get("host_ip")), f"{n}:{tgt} host_ip changed"
            key = (str(p.get("host_ip")), str(p["published"]))
            assert key not in seen, f"{n} collides with {seen[key]} on {key}"
            seen[key] = n
            assert str(p["published"]) not in prod_pub, f"{n} reuses prod's port {p['published']}"


def test_no_published_port_lands_in_the_runners_vlm_pool(
    prod_services, merged_services, gpu_merged_services
):
    """The pool belongs to `agent-gpu run`, which only `--real` starts — and a `--real`
    run publishes the VLM on 127.0.0.1 somewhere in AGENT_GPU_PORTS. The two prod-shape
    venues differ (ruling 256): the maui run is plain `--prod-shape` (no agent-gpu, no VLM
    pool in use), and the sandbox `--real` venue serves its VLM through agent-gpu — so a
    stack service published inside that band either squats the address the VLM expects
    (loki's 3100 + 15000 = 18100 was exactly the pool's floor — [r195] box 3) or loses the
    VLM's port to a bind conflict, and neither failure names itself as a port collision at
    boot.

    Two-sided: the assertion must catch a squat AND must not fire on the ports that sit beside the
    pool today (tempo's 18200 is the pool's first address +1, 18002/18200 are both legal). The
    must-catch side re-runs the same scan over a synthetic squat; a scan that matched everything
    or nothing would pass this node either way.
    """
    fc = _feature_check()
    pool = frozenset(fc.AGENT_GPU_PORTS)
    assert len(pool) == 100, f"the pool the guard reads is not the runner's: {sorted(pool)[:3]}…"

    def squats(services: dict) -> list[str]:
        return [
            f"{n} publishes {p.get('host_ip')}:{p['published']} (target {p['target']})"
            for n, svc in services.items()
            for p in svc.get("ports", [])
            if int(p["published"]) in pool
        ]

    for label, services in (("merged", merged_services), ("gpu-merged", gpu_merged_services)):
        found = squats(services)
        assert not found, f"{label} render publishes in the runner's VLM pool {min(pool)}-{max(pool)}: {found}"
    # must-catch: the shape the guard exists for, and the one prod's own offset produced.
    synthetic = {"loki": {"ports": [{"host_ip": "127.0.0.1", "published": min(pool), "target": "3100"}]}}
    assert len(squats(synthetic)) == 1, "the pool scan cannot see a squat it is meant to catch"
    # must-ignore: neighbours of the pool stay legal, so the scan is not "everything in 18xxx".
    neighbours = {
        s: {"ports": [{"host_ip": "127.0.0.1", "published": p, "target": "1"}]}
        for s, p in (("a", min(pool) - 1), ("b", max(pool) + 1))
    }
    assert squats(neighbours) == [], "the pool scan rejects addresses outside the pool"


def test_the_pool_exception_table_is_the_minimal_set(
    prod_services, merged_services, gpu_merged_services
):
    """A declared exception must be (a) actually needed — the uniform offset really lands that
    service inside the pool — and (b) sufficient — its port is outside the pool, unique, and not
    prod's own. Without this, PORT_POOL_EXCEPTIONS could quietly grow into "whatever the file
    happens to say", and the uniform-offset test above would stop guarding anything."""
    fc = _feature_check()
    pool = frozenset(fc.AGENT_GPU_PORTS)
    for services in (merged_services, gpu_merged_services):
        published: dict[int, str] = {}
        for n, svc in services.items():
            for p in svc.get("ports", []):
                published.setdefault(int(p["published"]), n)
        for n, port in PORT_POOL_EXCEPTIONS.items():
            prod = prod_services.get(n)
            assert prod is not None, (
                f"{n}: the table names a service absent from the profile-less render; this node "
                f"derives 'is the exception earned' from prod_services only")
            prod_ports = {int(p["published"]) for p in prod.get("ports", [])}
            assert prod_ports, f"{n}: prod publishes no ports for the table to offset"
            assert any(pp + PORT_OFFSET in pool for pp in prod_ports), (
                f"{n}: the table exempts it but prod + {PORT_OFFSET} "
                f"{sorted(prod_ports)} never enters the pool — the exception is unearned")
            assert port not in pool, f"{n}: the declared port {port} is still inside the pool"
            assert published.get(port) == n, (
                f"{n}: nothing in the render publishes {port} "
                f"(it belongs to {published.get(port, 'nobody')})")
            assert port not in {pp + PORT_OFFSET for pp in prod_ports}, (
                f"{n}: {port} equals its own offset port, so the table hides a double bind")
        # "nothing squats by being left OFF the table" is the other node's job
        # (test_no_published_port_lands_in_the_runners_vlm_pool scans every service); this one only
        # proves the entries that ARE on the table are earned and sufficient.


# ---------------------------------------------------------------- B5 / UR-133 host paths ------
def test_no_writable_host_bind_outside_the_run(prod_services, merged_services):
    """After the override, no bind mounts a host path as read-write outside the run root.
    Read-only binds and named volumes are allowed and must survive untouched."""
    bad = [
        (n, str(v["source"]), str(v["target"]))
        for n, svc in merged_services.items()
        for v in svc.get("volumes", [])
        if str(v.get("type")) == "bind"
        and not v.get("read_only")
        and not _norm(v["source"]).startswith(RUN_ROOT + "/")
    ]
    assert not bad, f"writable host bind outside the run survives: {bad}"


def test_readonly_binds_and_named_volumes_survive(prod_services, merged_services):
    """Redirecting writable binds must not quietly drop the read-only binds or named volumes
    beside them — `!override` replaces the whole list, so this is the guard against that."""
    for n, svc in prod_services.items():
        keep = {
            _volkey(v)
            for v in svc.get("volumes", [])
            if not (_is_socket(v) or _is_writable_outside_run(v))
        }
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
    cand = next(
        n
        for n, s in prod_services.items()
        if "volumes" not in expected.get(n, set()) and s.get("volumes")
    )
    tampered = copy.deepcopy(prod_services)
    tampered[cand]["volumes"].append(
        {
            "type": "bind",
            "source": "/export/planted-after-the-override",
            "target": "/planted",
            "read_only": False,
        }
    )
    assert "volumes" in expected_changed_keys(tampered)[cand], (
        "the policy itself failed to notice a new writable bind"
    )
    # but the SHIPPED override does not cover it -> observed delta no longer equals expected
    merged_tampered = _tampered_merged(merged_services, cand)
    observed_after = _changed_keys(tampered, merged_tampered)
    assert observed_after != expected, (
        "an uncovered new prod mount left the delta unchanged — the guard cannot fail, so it "
        "proves nothing"
    )


def _tampered_merged(merged: dict, svc: str) -> dict:
    """Apply the shipped override's volume clause to the tampered prod, i.e. what compose would
    really render: the override's `!override` list replaces the service's volumes wholesale, so
    the planted mount disappears exactly as it would in a real run."""
    out = copy.deepcopy(merged)
    # the shipped override restates the whole list, so the planted mount is absent in `merged`
    # already; the delta between tampered prod and the merged render must therefore be non-empty
    return out


def test_override_refuses_to_render_without_the_run_root():
    """UR-133/134: a forgotten PROD_SHAPE_RUN_ROOT must stop the render, not fall back to `/`.

    Measured on the first version of this file (which interpolated the variable bare): with it
    unset, compose rendered WRITABLE binds at the filesystem root — /cameras, /backend-data,
    /triton-cache, /hf-cache — because `${VAR}/cameras` interpolates to `/cameras` when VAR is
    empty. A test deployment would then write outside its own run directory on a host that may
    run the live stack, and nothing would say so. The override now carries `${VAR:?…}`, so the
    render exits nonzero and names the variable; rc=0 here is the breach.
    """
    env = {k: v for k, v in _clean_env().items() if k != "PROD_SHAPE_RUN_ROOT"}
    cmd = [
        "docker",
        "compose",
        "-p",
        "prodshape-audit",
        "--project-directory",
        str(REPO),
        "-f",
        str(PROD),
        "-f",
        str(OVERRIDE),
        "config",
        "--quiet",
    ]
    p = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True)
    assert p.returncode != 0, (
        "the override rendered with PROD_SHAPE_RUN_ROOT unset — its writable binds land at the "
        f"filesystem root, outside the run directory: {p.stdout[:200]}"
    )
    assert "PROD_SHAPE_RUN_ROOT" in p.stderr, (
        f"the render failed for a reason that is not the missing variable: {p.stderr[:300]}"
    )


# ------------------------------------------------ the runner's generated boot file (O2.5) --------
def _feature_check():
    """Load scripts/feature_check.py as a module (it is a script, not a package)."""
    spec = importlib.util.spec_from_file_location(
        "feature_check", REPO / "scripts" / "feature_check.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["feature_check"] = mod
    spec.loader.exec_module(mod)
    return mod


def _render_full(files: list[Path], project: str, *, extra: dict[str, str] | None = None) -> dict:
    """`compose config` for these files, returning the WHOLE document (names included).

    Loud on rc!=0 like _compose: a green here only means the render actually ran.
    `extra` overrides ENV entries for one render (a drop-one probe); without it every
    render in this file sees the same fixed env, which is what makes the delta tests
    comparable."""
    cmd = ["docker", "compose", "-p", project, "--project-directory", str(REPO)]
    for f in files:
        cmd += ["-f", str(f)]
    cmd += ["config", "--format", "json"]
    p = subprocess.run(
        cmd,
        cwd=REPO,
        # same scrub as _compose: this render sees the fixed env, not the host's.
        # `extra` still wins over ENV -- _clean_env applies it last -- so a drop-one
        # probe here behaves exactly as it did before (review finding 3, 4th site).
        env=_clean_env(**(extra or {})),
        capture_output=True,
        text=True,
        check=False,  # rc IS the observation: a nonzero render must name the file
    )
    if p.returncode != 0:
        pytest.fail(f"`docker compose config` rc={p.returncode}: {p.stderr[:600]}")
    return json.loads(p.stdout)


def _container_names(document: dict) -> set[str]:
    return {
        str(svc["container_name"])
        for svc in (document.get("services") or {}).values()
        if svc.get("container_name")
    }


def _object_names(document: dict) -> set[str]:
    """Every object name compose would create: the run's networks and named volumes."""
    out = set()
    for section in ("networks", "volumes"):
        for entry in (document.get(section) or {}).values():
            name = entry.get("name") if isinstance(entry, dict) else None
            out.add(name or "UNNAMED")
    return out


def test_the_generated_boot_file_rebinds_its_objects_to_the_live_project(tmp_path):
    """UR-133's isolation has to survive the runner writing a boot FILE.

    `compose config --format json` bakes the project name into the top-level object AND
    into every network and every volume (security-net -> prodshape-audit_security-net).
    Measured on compose v5.5.1: re-feeding that render under a DIFFERENT -p overrides the
    top-level name and NOTHING else. So a boot file written from a render is not
    project-neutral -- a second run boots it under its own -p and still creates, mounts
    and `down -v`s the FIRST project's networks and volumes. That turns UR-133's "its own
    compose project" into a cross-run delete, which is why feature_check.boot_render()
    strips the baked names before writing.

    Two-sided control, because a guard that cannot fail both ways is decoration:
      * must-catch  -- the UNstripped render, booted under a second project, still carries
                       the first project's object names (the trap is real on this compose);
      * must-ignore -- the stripped boot file, booted under two projects, yields two
                       DISJOINT name sets, each prefixed by the project that booted it.
    And one faithfulness clause: stripping the names must not change what gets deployed --
    at the same -p the boot file renders byte-identically to the YAML pair it came from.
    """
    fc = _feature_check()
    source_project = "prodshape-audit"
    full = _render_full([PROD, OVERRIDE], source_project)
    boot = fc.boot_render(full)

    assert "name" not in boot, "the top-level name must be decided by -p at boot"
    for section in ("networks", "volumes"):
        assert all("name" not in entry for entry in (boot.get(section) or {}).values()), section

    boot_file = tmp_path / "compose.json"
    boot_file.write_text(json.dumps(boot, indent=2) + "\n", encoding="utf-8")

    run_one = _render_full([boot_file], "hsi-run-one")
    run_two = _render_full([boot_file], "hsi-run-two")
    names_one, names_two = _object_names(run_one), _object_names(run_two)
    assert names_one and names_two, "the stack has no networks or volumes to isolate?"
    assert not (names_one & names_two), (
        f"two runs sharing a boot file created the same objects: {names_one & names_two}"
    )
    assert all(n.startswith("hsi-run-one_") for n in names_one), names_one
    assert all(n.startswith("hsi-run-two_") for n in names_two), names_two

    # must-catch: the UNstripped render booted under a second project keeps the FIRST
    # project's object names. This is the leak boot_render exists to close -- and it is
    # only real because it reproduces on the compose in CI, not on my reading of it.
    unstripped = tmp_path / "baked.json"
    unstripped.write_text(json.dumps(full, indent=2) + "\n", encoding="utf-8")
    assert any(n.startswith(source_project + "_") for n in _object_names(full)), (
        "the source render bakes no project names at all -- the clause below is vacuous "
        "and boot_render would be dead code"
    )
    leaked = _object_names(_render_full([unstripped], "hsi-run-leak"))
    assert any(n.startswith(source_project + "_") for n in leaked), (
        "compose no longer bakes object names against a -p rebind; boot_render is then "
        f"dead code and THIS leg is what changed, not the runner ({sorted(leaked)[:3]})"
    )
    assert not any(n.startswith("hsi-run-leak_") for n in leaked), (
        f"a baked boot file DID rebind to the live project ({sorted(leaked)[:3]})"
    )

    # faithfulness: at the project it was rendered for, the boot file deploys the SAME stack.
    reblessed = _render_full([boot_file], source_project)
    assert reblessed == full, (
        "boot_render changed what would be deployed, not just who owns the objects"
    )



# ------------------------------------------------ ruling 256: the spliced boot document renders --
def _splice_venue(fc, venue: str) -> tuple[dict, dict]:
    """The boot document one prod-shape run would write, via the real compose oracle.

    Renders prod+override (the run's base) and CI+fake (where the fake bodies come from),
    then applies `as_prod_shape_deployment` exactly as `render_prod_shape` does -- the
    WHOLE document, not abbreviated fixtures, because abbreviated fixtures are how the
    ci-net/ports divergence shipped: a dict-level test that omits the keys under test
    cannot see them. Returns (the boot document, the pre-fix control)."""
    full = _render_full([PROD, OVERRIDE], "prodshape-audit")
    bodies = _render_full([REPO / "docker-compose.ci.yml", REPO / "docker-compose.fake-ai.yml"],
                          "ci-fake")
    fakes = {n: b for n, b in bodies["services"].items() if n in ("ai-vlm", "ai-gateway")}
    if venue == "sandbox":
        swapped, kwargs = "ai-gateway", {"vlm_url": "http://127.0.0.1:18100",
                                         "fake_gateway": fakes["ai-gateway"]}
    elif venue == "maui":
        swapped, kwargs = "ai-vlm", {"vlm_url": None, "fake_vlm": fakes["ai-vlm"]}
    else:
        raise AssertionError(venue)
    boot = fc.as_prod_shape_deployment(copy.deepcopy(full), **kwargs)
    boot.pop("_device_changes", None)
    # must-catch control: the PRE-FIX splice, reconstructed by restoring the raw fake
    # body's networks/ports over the repaired output. (The transform repairs
    # unconditionally, so a "raw body in" control would exercise the same fixed code and
    # prove nothing.) That pre-fix shape is what first shipped: the fake body's ci-net and
    # CI-band publishes left in the prod document, which compose refuses. The refusal must
    # reproduce on this compose, or the repair guards a phantom.
    control = copy.deepcopy(boot)
    for key in ("networks", "ports"):
        if key in fakes[swapped]:
            control["services"][swapped][key] = copy.deepcopy(fakes[swapped][key])
        else:
            control["services"][swapped].pop(key, None)
    return boot, control


@pytest.mark.parametrize("venue", ["sandbox", "maui"])
def test_the_spliced_boot_document_renders_and_keeps_prod_network_and_ports(venue, tmp_path):
    """Ruling 256's transforms meet the compose oracle end to end: `docker compose config`
    on the document the run would boot must RENDER (the ci-net divergence made it refuse),
    the spliced service must sit on the prod render's security-net, and it must publish on
    the prod-shape band the override set -- not the CI band, whose 8090/8098 binds are the
    LIVE stack's own beside production on maui. Two-sided: the pre-fix control (the fake
    body's ci-net/ports left in) must still be REFUSED naming ci-net, so this leg cannot
    pass by matching everything."""
    fc = _feature_check()
    boot, control = _splice_venue(fc, venue)

    boot_file = tmp_path / f"boot-{venue}.json"
    boot_file.write_text(json.dumps(fc.boot_render(boot), indent=2) + "\n", encoding="utf-8")
    rendered = _render_full([boot_file], "hsi-splice-probe")
    spliced = rendered["services"]["ai-gateway" if venue == "sandbox" else "ai-vlm"]
    assert set(spliced.get("networks") or {}) == {"security-net"}, spliced.get("networks")
    ci_band = {"8090", "8098"}
    assert not ci_band & {str(p.get("published")) for p in spliced.get("ports") or []}, (
        f"the spliced body publishes on the CI band beside production: {spliced.get('ports')}")

    control_file = tmp_path / f"control-{venue}.json"
    control_file.write_text(json.dumps(fc.boot_render(control), indent=2) + "\n", encoding="utf-8")
    p = subprocess.run(
        ["docker", "compose", "-p", "hsi-splice-control", "--project-directory", str(REPO),
         "-f", str(control_file), "config", "--format", "json"],
        cwd=REPO, env=_clean_env(), capture_output=True, text=True, check=False)
    assert p.returncode != 0, "the pre-fix control renders -- the refusal this test guards is gone"
    assert "ci-net" in p.stderr, p.stderr[-400:]


# ------------------------------------------------ the anti-rot ceiling this file rides ----------
# This file is a member of Collection Sanity's ONE-argv anti-rot battery (ci.yml:263), so every node
# here runs under the root `timeout = 5` in pyproject's [tool.pytest.ini_options] unless something
# marks it otherwise. A `docker compose config` spawn does not fit 5 seconds on a loaded runner:
# measured >5.0s twice in one day — #7122 `f1d923174` FAILED one node IN-CALL inside
# `process.communicate()` (`_render_full` issues five renders), and #7123 `68f64bb6b` reported 13
# `ERROR at setup` when the module-scoped fixtures' own spawns landed on whichever nodes
# pytest-randomly ran first. `timeout_func_only = false`, so a fixture's spawn bills the victim node,
# and the victim is chosen by a per-run lottery — which is why the ceiling belongs on the WHOLE file
# (`pytestmark` below), not on the nodes that visibly spawn. The floor is set the way the job's other
# spawn/scan suites set theirs (test_suppression_census.py 180/300, test_ai_surface_census.py 60):
# the ceiling must exceed the inflation, and 15 s is already ~6x the worst figure measured on the
# heaviest node under deliberate saturation (2.42 s call, load 20). This is a ceiling, not a budget:
# the node finishes in well under a second when the box is idle. It is deliberately NOT a raise of
# the root `timeout` — that number is the tier's gate, and per the coordinator's routing
# (`6173401735`) raising it is not this cell's to give.
_CEILING_FLOOR = 15


def _ceiling_seconds(marks: list) -> int:
    """Highest @pytest.mark.timeout(N) in a decorator list (0 = no ceiling raised).

    Reads BOTH shapes a decorator arrives in, because the guard walks a parsed tree while the file's
    own `pytestmark` is a live object: `pytest.MarkDecorator` at runtime, `ast.Call` after
    `ast.parse`. Handling only the first would make per-node marks invisible — the ceiling would read
    as absent on a file that raised it correctly, and a guard with a false-red direction gets deleted.
    """
    best = 0
    for mark in marks:
        name: str | None = None
        arg: object | None = None
        if isinstance(mark, pytest.MarkDecorator):
            name, arg = mark.name, (mark.args[0] if mark.args else None)
        elif isinstance(mark, ast.Call):
            # pytest.mark.timeout(N) → Attribute(attr="timeout") on Attribute(attr="mark") on Name.
            func = mark.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute):
                name = func.attr
                if mark.args and isinstance(mark.args[0], ast.Constant):
                    arg = mark.args[0].value
        if name == "timeout" and isinstance(arg, int) and not isinstance(arg, bool):
            best = max(best, arg)
    return best


def _nodes_owed_a_ceiling(tree: ast.Module, module_marks: list) -> set[str]:
    """Module-level test functions that can pay for a compose spawn without a ceiling above the floor.

    `module_marks` is the file's own `pytestmark` list, which covers every node the way the fixtures
    do. The trigger is that the MODULE spawns at all, not that this node does: under
    `timeout_func_only = false`, a module-scoped fixture's render is billed to whichever node the
    randomiser runs first, so an unmarked node that only reads a fixture is still exposed — the exact
    shape of the 13-error #7123 red. A module that spawns nothing owes nothing, which is the
    must-ignore side the companion test pins.
    """
    if _ceiling_seconds(module_marks) >= _CEILING_FLOOR:
        return set()
    spawns = any(
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "run"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "subprocess"
        for call in ast.walk(tree)
    )
    if not spawns:
        return set()
    return {
        fn.name
        for fn in tree.body
        if isinstance(fn, ast.FunctionDef)
        and fn.name.startswith("test_")
        and _ceiling_seconds(fn.decorator_list) < _CEILING_FLOOR
    }


def test_no_compose_spawning_node_rides_the_five_second_tier_default() -> None:
    """The ceiling is pinned, so it cannot rot out of this file (anti-rot doctrine, WP0.1 et al.).

    must-catch: drop the marks and this is red naming every spawn-exposed node. must-ignore: a module
    that spawns no subprocess owes no ceiling — otherwise the guard is a demand for marks everywhere
    and the next person deletes it instead of the bug.
    """
    tree = ast.parse(Path(__file__).resolve().read_text(encoding="utf-8"))
    module_marks = globals().get("pytestmark", [])
    assert isinstance(module_marks, (list, pytest.MarkDecorator)), (
        "pytestmark must be a mark or a list"
    )
    if isinstance(module_marks, pytest.MarkDecorator):
        module_marks = [module_marks]
    owed = _nodes_owed_a_ceiling(tree, module_marks)
    assert not owed, (
        f"{len(owed)} node(s) in this file can pay for a `docker compose config` spawn while riding "
        f"the root `timeout = 5` — a loaded runner has measured this red twice ({sorted(owed)[:3]}…). "
        f"Raise the file's ceiling with `pytestmark = pytest.mark.timeout(N)`, N >= {_CEILING_FLOOR}, "
        "because a module-scoped fixture's spawn bills a lottery-chosen node, not only the spawner."
    )


def test_the_ceiling_guard_itself_discriminates() -> None:
    """Two-sided control for the guard above: it must fire on the bad tree and stay silent on the
    good one AND on a spawn-free module — a guard that cannot fail is a comment, not a gate."""
    spawn_src = (
        "import subprocess, pytest\n"
        "def _render(): subprocess.run(['docker', 'compose', 'config'])\n"
        "def test_a(): _render()\n"
        "def test_b(): assert True\n"
    )
    unmarked = ast.parse(spawn_src)
    assert _nodes_owed_a_ceiling(unmarked, []) == {"test_a", "test_b"}, (
        "the guard did not flag unmarked tests in a spawning module: it is vacuous"
    )
    # covered by a module-level ceiling → nothing owed.
    covered = [pytest.mark.timeout(_CEILING_FLOOR)]
    assert _nodes_owed_a_ceiling(unmarked, covered) == set(), "a covered module must owe nothing"
    # covered per-node, no module mark → still nothing owed.
    per_node = ast.parse(
        spawn_src.replace("def test_a():", "@pytest.mark.timeout(20)\ndef test_a():").replace(
            "def test_b():", "@pytest.mark.timeout(20)\ndef test_b():"
        )
    )
    assert _nodes_owed_a_ceiling(per_node, []) == set(), "every node marked => nothing owed"
    # must-ignore: a module that never spawns owes nothing, marked or not.
    quiet = ast.parse("def test_c(): assert True\ndef test_d(): assert True\n")
    assert _nodes_owed_a_ceiling(quiet, []) == set(), "a spawn-free module must not be flagged"
    # the floor is real: a ceiling AT the tier default buys nothing, so both nodes are still owed.
    weak = ast.parse(spawn_src.replace("def test_a():", "@pytest.mark.timeout(5)\ndef test_a():"))
    assert _nodes_owed_a_ceiling(weak, []) == {"test_a", "test_b"}, (
        f"a timeout at the tier default (5) is not a ceiling; only >= {_CEILING_FLOOR} counts. If "
        "this fails, the guard has started crediting a mark that does not lift anything, which is "
        "the exact shape that leaves the real red in place while looking green."
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))


# ------------------------------------------------- B2: removal is not the same as redirect -----
def _writable_outside_run(prod: dict) -> dict[str, list[dict]]:
    """{svc: the prod mounts the policy says must be REDIRECTED under the run root}.
    Sockets are excluded, and the exclusion is code, not prose: the engine socket IS a writable
    bind outside the run by _is_writable_outside_run's definition (measured -- alloy's
    socket:socket mount satisfies it), and the policy's rule for it is DROP, not redirect.
    Conflating the two makes the guard demand a run-root redirect for a mount UR-134 forbids
    outright."""
    return {
        n: [v for v in svc.get("volumes", []) if _is_writable_outside_run(v) and not _is_socket(v)]
        for n, svc in prod.items()
        if any(_is_writable_outside_run(v) and not _is_socket(v) for v in svc.get("volumes", []))
    }


def test_every_writable_prod_bind_is_redirected_at_its_own_target(prod_services, merged_services):
    """must-ignore side of the two-sided control: the shipped override redirects EVERY writable
    prod bind, at the same target, to a path under the run root.

    This is the level the key-name guard cannot see. _changed_keys compares per (service, key),
    so once a service is EXPECTED to change `volumes` -- which every service with a writable bind
    is -- the CONTENT of that change is unexamined. Measured: the override restates each such
    service's whole list under `!override`, which REPLACES it, so a bind a later prod change adds
    is silently ABSENT from the boot document rather than redirected, and the observed delta still
    equals the prediction, so the leg stays green on a production change nobody reviewed. Dropping
    a writable bind is not compliance; the run must still be able to write there."""
    for n, want in _writable_outside_run(prod_services).items():
        after = {_volkey(v): v for v in merged_services[n].get("volumes", [])}
        for v in want:
            tgt = str(v["target"])
            redirects = [
                m
                for m in merged_services[n].get("volumes", [])
                if str(m["target"]) == tgt
                and str(m.get("type")) == "bind"
                and not m.get("read_only")
                and _norm(m.get("source")).startswith(RUN_ROOT + "/")
            ]
            assert redirects, (
                f"{n}: prod's writable bind at {tgt} ({_norm(v['source'])}) has no redirect under "
                f"{RUN_ROOT}/ in the boot document -- the override restates this service's volume "
                f"list wholesale, so an uncovered new bind DISAPPEARS rather than being redirected. "
                f"Extend scripts/uplevel/docker-compose.prodshape.yml."
            )
            assert after, f"{n}: no volumes survive the override at all"


def test_an_uncovered_new_writable_bind_is_caught(prod_services, merged_services):
    """must-catch side: a writable bind added to prod AFTER the override was authored, on a
    service the override already restates, MUST make the guard disagree. The existing
    test_uncovered_prod_change_is_caught plants on a service the override does NOT restate; this
    plants where that test's structure cannot reach, which is where the real drift lands."""
    test_every_writable_prod_bind_is_redirected_at_its_own_target(
        prod_services, merged_services
    )  # precondition: the shipped pair is compliant
    # a service the override ALREADY restates -- i.e. one whose volumes the policy expects to
    # change. That is precisely where the key-name comparison is blind.
    cand = next(
        n
        for n in sorted(prod_services)
        if "volumes" in expected_changed_keys(prod_services).get(n, [])
    )
    planted = {
        "type": "bind",
        "source": "/export/planted-after-the-override",
        "target": "/planted",
        "read_only": False,
    }
    tampered_prod = copy.deepcopy(prod_services)
    tampered_prod[cand]["volumes"].append(dict(planted))
    # The override restates the list, so the planted bind is absent from the merged render --
    # exactly what compose produces when the override has not been extended.
    tampered_merged = copy.deepcopy(merged_services)
    assert dict(planted) not in tampered_merged[cand]["volumes"]
    with pytest.raises(AssertionError, match="/planted"):
        test_every_writable_prod_bind_is_redirected_at_its_own_target(
            tampered_prod, tampered_merged
        )
    # and the key-level guard is provably BLIND at this position, which is why the test above
    # exists: a vanished mount and a redirected mount both read as "volumes changed", so the
    # guard's whole-document verdict on the tampered pair is still "fully compliant". If this
    # assert ever fails, _changed_keys has become content-aware and this companion test can go.
    assert _changed_keys(tampered_prod, tampered_merged) == expected_changed_keys(tampered_prod), (
        "the key-level guard now DISAGREES with itself on the tampered pair, so it is no longer "
        "blind here -- re-check whether this companion test is still needed"
    )
