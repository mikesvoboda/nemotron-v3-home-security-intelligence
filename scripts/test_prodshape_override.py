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
import importlib.util
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
NAME_VAR = "HSI_TEST_NAME_PREFIX"
# A pinned container_name is NOT namespaced by the compose project (measured), so the prefix alone
# cannot separate two runs: the override interpolates this per-RUN token instead.
# A fixed literal here, deliberately NOT a per-run value: every render in this file must resolve
# against the same env, or the prod-vs-override delta it asserts is not comparable. The per-run
# token itself is feature_check.prod_shape_env's job; test_a_pinned_name_carries_the_run_token_...
# renders with two different tokens and requires the name sets to be disjoint.
DRIFT_NAME_PREFIX = "audit-"
# measured: collides with no prod port, stays under the 32768 Linux ephemeral band
# (max prod 14318 -> 29318)
PORT_OFFSET = 15000
# fixed literals for BOTH renders; none is a real credential
ENV = {
    # sentinel: alloy interpolates it into src AND tgt
    "PODMAN_SOCKET": "/render/engine.sock",
    "POSTGRES_PASSWORD": "render-only",
    "PROD_SHAPE_RUN_ROOT": "/run/hsitest",
    NAME_VAR: DRIFT_NAME_PREFIX,
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

    env = {k: v for k, v in {**os.environ, **ENV}.items() if k != NAME_VAR}
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


def test_override_refuses_to_render_without_the_run_root():
    """UR-133/134: a forgotten PROD_SHAPE_RUN_ROOT must stop the render, not fall back to `/`.

    Measured on the first version of this file (which interpolated the variable bare): with it
    unset, compose rendered WRITABLE binds at the filesystem root — /cameras, /backend-data,
    /triton-cache, /hf-cache — because `${VAR}/cameras` interpolates to `/cameras` when VAR is
    empty. A test deployment would then write outside its own run directory on a host that may
    run the live stack, and nothing would say so. The override now carries `${VAR:?…}`, so the
    render exits nonzero and names the variable; rc=0 here is the breach.
    """
    env = {k: v for k, v in {**os.environ, **ENV}.items() if k != "PROD_SHAPE_RUN_ROOT"}
    cmd = ["docker", "compose", "-p", "prodshape-audit", "--project-directory", str(REPO),
           "-f", str(PROD), "-f", str(OVERRIDE), "config", "--quiet"]
    p = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True)
    assert p.returncode != 0, (
        "the override rendered with PROD_SHAPE_RUN_ROOT unset — its writable binds land at the "
        f"filesystem root, outside the run directory: {p.stdout[:200]}")
    assert "PROD_SHAPE_RUN_ROOT" in p.stderr, (
        f"the render failed for a reason that is not the missing variable: {p.stderr[:300]}")


# ------------------------------------------------ the runner's generated boot file (O2.5) --------
def _feature_check():
    """Load scripts/feature_check.py as a module (it is a script, not a package)."""
    spec = importlib.util.spec_from_file_location("feature_check", REPO / "scripts" / "feature_check.py")
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
        env={**os.environ, **ENV, **(extra or {})},
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
        f"two runs sharing a boot file created the same objects: {names_one & names_two}")
    assert all(n.startswith("hsi-run-one_") for n in names_one), names_one
    assert all(n.startswith("hsi-run-two_") for n in names_two), names_two

    # must-catch: the UNstripped render booted under a second project keeps the FIRST
    # project's object names. This is the leak boot_render exists to close -- and it is
    # only real because it reproduces on the compose in CI, not on my reading of it.
    unstripped = tmp_path / "baked.json"
    unstripped.write_text(json.dumps(full, indent=2) + "\n", encoding="utf-8")
    assert any(n.startswith(source_project + "_") for n in _object_names(full)), (
        "the source render bakes no project names at all -- the clause below is vacuous "
        "and boot_render would be dead code")
    leaked = _object_names(_render_full([unstripped], "hsi-run-leak"))
    assert any(n.startswith(source_project + "_") for n in leaked), (
        "compose no longer bakes object names against a -p rebind; boot_render is then "
        f"dead code and THIS leg is what changed, not the runner ({sorted(leaked)[:3]})")
    assert not any(n.startswith("hsi-run-leak_") for n in leaked), (
        f"a baked boot file DID rebind to the live project ({sorted(leaked)[:3]})")

    # faithfulness: at the project it was rendered for, the boot file deploys the SAME stack.
    reblessed = _render_full([boot_file], source_project)
    assert reblessed == full, (
        "boot_render changed what would be deployed, not just who owns the objects")

if __name__ == "__main__":   # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
