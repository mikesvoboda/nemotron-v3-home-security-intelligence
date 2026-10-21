"""The feature-check harness's isolation logic (O2.2).

``scripts/feature-check.sh`` brings up a *test deployment* — the CI stack
plus the fake-AI overlay under its own compose project — and must touch
nothing else on the machine. Isolation rests on three checks, pinned here
against fixture snapshots and fixture rendered configs (``data/feature_check/``):

* the **preflight** refuses to start when the run's rendered configuration
  could write outside its own directory, reach a container engine, or
  overlap anything already on the machine (project, container name, host
  port, volume, a running stack's bind-mounted host path);
* the **in-run check** fails the run when a container of the test
  deployment holds an engine socket or the backend's orchestrator is on;
* the **postflight** fails loudly when a container or volume that existed
  before the run is gone, or a container that was running has stopped or
  restarted (a new start time).

The harness end to end (boot, smoke check, teardown) runs in the
``feature-check`` CI job and is shown with commands and output on the PR.
"""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import os
import re
import secrets
import signal
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "feature_check.py"
DATA = Path(__file__).resolve().parent / "data" / "feature_check"

PROJECT = "hsi-check-fixture"
RUN_DIR = Path("/runs/hsi-check-fixture")


def _load_script() -> Any:
    spec = importlib.util.spec_from_file_location("feature_check", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["feature_check"] = module
    spec.loader.exec_module(module)
    return module


fc = _load_script()


def _read(name: str) -> dict[str, Any]:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@pytest.fixture
def base() -> dict[str, Any]:
    """The CI stack plus the fake-AI overlay, as compose renders it."""
    return _read("rendered-ci-fake.json")["rendered"]


@pytest.fixture
def deployment(base: dict[str, Any]) -> dict[str, Any]:
    """The test deployment the harness makes of ``base``."""
    return fc.as_test_deployment(base, project=PROJECT, run_dir=RUN_DIR)


@pytest.fixture
def live() -> Any:
    raw = _read("live-machine.json")
    return fc.Snapshot.from_engine(raw["containers"], raw["volumes"])


@pytest.fixture
def run_containers() -> list[dict[str, Any]]:
    return _read("run-containers.json")["containers"]


def _preflight(rendered: dict[str, Any], snapshot: Any, **kwargs: Any) -> list[str]:
    return fc.preflight(rendered, project=PROJECT, run_dir=RUN_DIR, snapshot=snapshot, **kwargs)


def _one_problem(problems: list[str], *needles: str) -> None:
    """Exactly one problem, and it names every needle."""
    assert len(problems) == 1, problems
    for needle in needles:
        assert needle in problems[0], problems


# ---------------------------------------------------------------------------
# The test deployment
# ---------------------------------------------------------------------------


def test_the_test_deployment_passes_the_preflight_on_a_live_machine(
    deployment: dict[str, Any], live: Any
) -> None:
    assert _preflight(deployment, live) == []


def test_the_untransformed_ci_stack_is_refused_on_a_live_machine(
    base: dict[str, Any], live: Any
) -> None:
    """The CI files publish the live stack's ports (5432, 8000, 8098, 8090)
    on fixed numbers, and the backend's orchestrator is on by default."""
    problems = "\n".join(_preflight(base, live))
    for port in ("5432", "8000", "8098", "8090"):
        assert f"host port {port}" in problems
    assert "ORCHESTRATOR_ENABLED" in problems


def test_the_test_deployment_publishes_no_fixed_host_port(deployment: dict[str, Any]) -> None:
    ports = [
        port for service in deployment["services"].values() for port in service.get("ports", [])
    ]
    assert ports, "the backend and frontend must stay reachable from the host"
    for port in ports:
        assert port["host_ip"] == "127.0.0.1"
        assert not port.get("published"), port


def test_the_test_deployment_seeds_cameras_from_its_own_directory(
    deployment: dict[str, Any],
) -> None:
    backend = deployment["services"]["backend"]
    assert "/cameras" not in backend.get("tmpfs", [])
    (camera_mount,) = [v for v in backend["volumes"] if v["target"] == "/cameras"]
    assert camera_mount["type"] == "bind"
    assert Path(camera_mount["source"]) == RUN_DIR / "cameras"
    assert backend["environment"]["FOSCAM_BASE_PATH"] == "/cameras"


def test_the_test_deployment_turns_the_orchestrator_off(deployment: dict[str, Any]) -> None:
    assert deployment["services"]["backend"]["environment"]["ORCHESTRATOR_ENABLED"] == "false"


def test_the_test_deployment_keeps_only_the_golden_path_services(
    base: dict[str, Any],
) -> None:
    extra = copy.deepcopy(base)
    extra["services"]["grafana"] = {"image": "grafana/grafana", "networks": {"ci-net": None}}
    deployment = fc.as_test_deployment(extra, project=PROJECT, run_dir=RUN_DIR)
    assert sorted(deployment["services"]) == sorted(fc.FAKE_SERVICES)
    assert deployment["name"] == PROJECT


def test_the_test_deployment_refuses_a_missing_service(base: dict[str, Any]) -> None:
    del base["services"]["ai-vlm"]
    with pytest.raises(fc.HarnessError, match="ai-vlm"):
        fc.as_test_deployment(base, project=PROJECT, run_dir=RUN_DIR)


# ---------------------------------------------------------------------------
# Preflight: each overlap or reach refuses the run
# ---------------------------------------------------------------------------


def test_an_overlapping_host_port_refuses(deployment: dict[str, Any], live: Any) -> None:
    deployment["services"]["frontend"]["ports"][0]["published"] = "8000"
    _one_problem(_preflight(deployment, live), "frontend", "host port 8000")


def test_a_fixed_container_name_refuses(deployment: dict[str, Any], live: Any) -> None:
    deployment["services"]["frontend"]["container_name"] = "hsi-go2rtc"
    problems = "\n".join(_preflight(deployment, live))
    assert "frontend" in problems
    assert "container_name" in problems


def test_an_overlapping_container_name_refuses(deployment: dict[str, Any]) -> None:
    raw = _read("live-machine.json")
    stray = copy.deepcopy(raw["containers"][-1])
    stray["Name"] = f"/{PROJECT}-backend-1"
    snapshot = fc.Snapshot.from_engine([*raw["containers"], stray], raw["volumes"])
    _one_problem(_preflight(deployment, snapshot), f"{PROJECT}-backend-1")


def test_an_overlapping_project_refuses(deployment: dict[str, Any]) -> None:
    raw = _read("live-machine.json")
    stray = copy.deepcopy(raw["containers"][-1])
    stray["Name"] = "/left-over"
    stray["Config"]["Labels"] = {"com.docker.compose.project": PROJECT}
    snapshot = fc.Snapshot.from_engine([*raw["containers"], stray], raw["volumes"])
    _one_problem(_preflight(deployment, snapshot), f"project {PROJECT}")


def test_an_overlapping_volume_refuses(deployment: dict[str, Any], live: Any) -> None:
    live_volume = "nemotron-v3-home-security-intelligence_postgres_data"
    deployment["volumes"] = {"pgdata": {"name": live_volume}}
    deployment["services"]["postgres"]["volumes"] = [
        {"type": "volume", "source": "pgdata", "target": "/var/lib/postgresql/data"}
    ]
    _one_problem(_preflight(deployment, live), "postgres", live_volume)


def test_an_external_volume_refuses(deployment: dict[str, Any], live: Any) -> None:
    deployment["volumes"] = {"shared": {"name": "shared", "external": True}}
    deployment["services"]["redis"]["volumes"] = [
        {"type": "volume", "source": "shared", "target": "/data"}
    ]
    _one_problem(_preflight(deployment, live), "redis", "external")


def test_an_overlapping_camera_path_refuses(base: dict[str, Any], live: Any) -> None:
    """A run directory under the live camera directory: the run's camera
    bind is inside its own directory, yet the live backend watches it."""
    run_dir = Path("/export/foscam/hsi-check-fixture")
    deployment = fc.as_test_deployment(base, project=PROJECT, run_dir=run_dir)
    problems = fc.preflight(deployment, project=PROJECT, run_dir=run_dir, snapshot=live)
    _one_problem(problems, "backend", "/export/foscam")


def test_a_live_read_only_view_of_the_whole_filesystem_does_not_refuse(
    deployment: dict[str, Any], live: Any
) -> None:
    """node-exporter mounts / read-only (docker-compose.prod.yml), so every
    path on the host is inside one of its binds; reading is not sharing."""
    assert "/" in live.running_bind_sources
    assert _preflight(deployment, live) == []


def test_a_run_inside_a_live_read_only_bind_refuses(deployment: dict[str, Any]) -> None:
    """A live container that reads a narrower directory may ingest what the
    run writes there (a camera folder watched read-only, say)."""
    raw = _read("live-machine.json")
    reader = copy.deepcopy(raw["containers"][0])
    reader["Id"] = "0" * 60 + "0042"
    reader["Name"] = "/live-reader"
    reader["Mounts"] = [{"Type": "bind", "Source": "/runs", "Destination": "/in", "RW": False}]
    reader["NetworkSettings"] = {"Ports": {}}
    snapshot = fc.Snapshot.from_engine([*raw["containers"], reader], raw["volumes"])
    _one_problem(_preflight(deployment, snapshot), "backend", "/runs")


def test_a_run_that_contains_a_live_bind_refuses(base: dict[str, Any], live: Any) -> None:
    """A run directory above a live bind: the run could write into it."""
    run_dir = Path("/export")
    deployment = fc.as_test_deployment(base, project=PROJECT, run_dir=run_dir)
    deployment["services"]["backend"]["volumes"].append(
        {"type": "bind", "source": "/export", "target": "/scratch"}
    )
    problems = fc.preflight(deployment, project=PROJECT, run_dir=run_dir, snapshot=live)
    _one_problem(problems, "backend", "/export/foscam")


def test_a_writable_bind_mount_outside_the_run_dir_refuses(
    deployment: dict[str, Any], live: Any
) -> None:
    deployment["services"]["backend"]["volumes"].append(
        {"type": "bind", "source": "/srv/hsi/backend/data", "target": "/app/data"}
    )
    _one_problem(_preflight(deployment, live), "backend", "/srv/hsi/backend/data")


def test_a_read_only_bind_mount_outside_the_run_dir_is_allowed(
    deployment: dict[str, Any], live: Any
) -> None:
    """Model weights mount read-only; reading shares nothing writable."""
    deployment["services"]["ai-vlm"]["volumes"] = [
        {
            "type": "bind",
            "source": "/export/ai_models/vlm",
            "target": "/models",
            "read_only": True,
        }
    ]
    assert _preflight(deployment, live) == []


@pytest.mark.parametrize(
    "source",
    [
        "/run/user/1000/podman/podman.sock",
        "/var/run/docker.sock",
        "/run/containerd/containerd.sock",
        "/var/run",
        # compose renders a doubled leading slash as written; POSIX keeps it.
        "//run",
        "//var/run",
    ],
)
def test_a_mounted_engine_socket_refuses(
    deployment: dict[str, Any], live: Any, source: str
) -> None:
    """Read-only too: a read-only socket still drives the engine API."""
    deployment["services"]["backend"]["volumes"].append(
        {"type": "bind", "source": source, "target": "/var/run/engine", "read_only": True}
    )
    _one_problem(_preflight(deployment, live), "backend", "engine socket", source)


@pytest.mark.parametrize("value", [None, "true", "1"])
def test_the_orchestrator_must_be_off(
    deployment: dict[str, Any], live: Any, value: str | None
) -> None:
    env = deployment["services"]["backend"]["environment"]
    if value is None:
        del env["ORCHESTRATOR_ENABLED"]
    else:
        env["ORCHESTRATOR_ENABLED"] = value
    _one_problem(_preflight(deployment, live), "backend", "ORCHESTRATOR_ENABLED")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("network_mode", "host"),
        ("privileged", True),
        ("pid", "host"),
    ],
)
def test_host_level_access_refuses(
    deployment: dict[str, Any], live: Any, key: str, value: Any
) -> None:
    deployment["services"]["redis"][key] = value
    _one_problem(_preflight(deployment, live), "redis", key)


LIVE_BACKEND = "nemotron-v3-home-security-intelligence_backend_1"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("volumes_from", [f"container:{LIVE_BACKEND}"]),
        ("network_mode", f"container:{LIVE_BACKEND}"),
        ("ipc", "host"),
        ("pid", f"container:{LIVE_BACKEND}"),
        ("userns_mode", "host"),
        ("cgroup", "host"),
        ("cap_add", ["SYS_ADMIN"]),
        ("devices", ["/dev/sda:/dev/sda"]),
        ("security_opt", ["no-new-privileges:true", "seccomp:unconfined"]),
        ("build", {"context": "/checkout", "network": "host"}),
    ],
)
def test_a_setting_the_preflight_does_not_vet_refuses(
    deployment: dict[str, Any], live: Any, key: str, value: Any
) -> None:
    """Fail closed: a key or value the preflight has no rule for is refused,
    so a setting added to a compose file later cannot slip through."""
    deployment["services"]["redis"][key] = value
    _one_problem(_preflight(deployment, live), "redis", key)


def test_a_bind_backed_named_volume_refuses(deployment: dict[str, Any], live: Any) -> None:
    """The local driver's bind options make a named volume a host bind."""
    deployment["volumes"] = {
        "cams": {
            "name": f"{PROJECT}_cams",
            "driver": "local",
            "driver_opts": {"type": "none", "o": "bind", "device": "/export/foscam"},
        }
    }
    deployment["services"]["redis"]["volumes"] = [
        {"type": "volume", "source": "cams", "target": "/data"}
    ]
    _one_problem(_preflight(deployment, live), "volume cams", "driver_opts")


@pytest.mark.parametrize(
    "network",
    [
        {"name": "nemotron-v3-home-security-intelligence_security-net", "external": True},
        {"name": "nemotron-v3-home-security-intelligence_security-net"},
        {"name": f"{PROJECT}_lan", "driver": "macvlan"},
    ],
)
def test_a_network_that_is_not_the_runs_own_refuses(
    deployment: dict[str, Any], live: Any, network: dict[str, Any]
) -> None:
    deployment["networks"]["live"] = network
    _one_problem(_preflight(deployment, live), "network live")


def test_a_top_level_section_the_preflight_does_not_vet_refuses(
    deployment: dict[str, Any], live: Any
) -> None:
    deployment["secrets"] = {"token": {"file": "/srv/hsi/.env"}}
    _one_problem(_preflight(deployment, live), "secrets")


def test_a_host_address_refuses(deployment: dict[str, Any], live: Any) -> None:
    """The way out of a sandbox is the host's loopback, where the live
    stack's API, database and engine listen (operator.md, step 4)."""
    deployment["services"]["backend"]["environment"]["AI_VLM_URL"] = (
        "http://host.docker.internal:8098"
    )
    _one_problem(_preflight(deployment, live), "backend", "host.docker.internal:8098")


def test_a_host_address_is_allowed_only_on_an_agent_gpu_port(
    deployment: dict[str, Any], live: Any
) -> None:
    env = deployment["services"]["backend"]["environment"]
    env["AI_VLM_URL"] = "http://host.docker.internal:18123"
    assert _preflight(deployment, live, allowed_host_ports=frozenset({18123})) == []
    env["DATABASE_URL"] = "postgresql+asyncpg://security:x@host.docker.internal:5432/security"
    _one_problem(
        _preflight(deployment, live, allowed_host_ports=frozenset({18123})),
        "host.docker.internal:5432",
    )


def test_a_host_ip_refuses(deployment: dict[str, Any], live: Any) -> None:
    deployment["services"]["backend"]["environment"]["REDIS_URL"] = "redis://192.168.1.20:6379"
    problems = _preflight(deployment, live, host_addresses=frozenset({"192.168.1.20"}))
    _one_problem(problems, "192.168.1.20:6379")


def test_a_host_gateway_alias_refuses(deployment: dict[str, Any], live: Any) -> None:
    deployment["services"]["backend"]["extra_hosts"] = ["live-api=host-gateway"]
    _one_problem(_preflight(deployment, live), "backend", "host-gateway")


# ---------------------------------------------------------------------------
# In-run check
# ---------------------------------------------------------------------------

# GET /api/system/services with no orchestrator on app.state
# (backend/api/routes/services.py:get_orchestrator).
NO_ORCHESTRATOR = (503, {"detail": "Container orchestrator not available"})


def test_a_clean_test_deployment_passes_the_in_run_check(
    run_containers: list[dict[str, Any]],
) -> None:
    assert (
        fc.in_run_check(run_containers, orchestrator_enabled=False, services=NO_ORCHESTRATOR) == []
    )


def test_an_in_run_container_exposing_an_engine_socket_fails(
    run_containers: list[dict[str, Any]],
) -> None:
    run_containers[4]["Mounts"].append(
        {
            "Type": "bind",
            "Source": "/run/user/1000/podman/podman.sock",
            "Destination": "/var/run/podman/podman.sock",
            "RW": False,
        }
    )
    problems = fc.in_run_check(run_containers, orchestrator_enabled=False, services=NO_ORCHESTRATOR)
    _one_problem(problems, f"{PROJECT}-backend-1", "engine socket")


@pytest.mark.parametrize("enabled", [True, None])
def test_an_orchestrator_that_is_on_or_unread_fails(
    run_containers: list[dict[str, Any]], enabled: bool | None
) -> None:
    problems = fc.in_run_check(
        run_containers, orchestrator_enabled=enabled, services=NO_ORCHESTRATOR
    )
    _one_problem(problems, "orchestrator")


@pytest.mark.parametrize(
    "services",
    [
        (200, []),
        # The setup guard answers 503 too, before the first admin registers
        # (backend/api/middleware/setup_guard.py): not proof of anything.
        (503, {"detail": "Initial setup required. Please register the first admin user."}),
        None,
    ],
)
def test_an_orchestrator_api_that_does_not_report_it_absent_fails(
    run_containers: list[dict[str, Any]], services: Any
) -> None:
    problems = fc.in_run_check(run_containers, orchestrator_enabled=False, services=services)
    _one_problem(problems, "/api/system/services")


# ---------------------------------------------------------------------------
# Postflight
# ---------------------------------------------------------------------------


def _after(mutate: Any = None, *, volumes: list[str] | None = None) -> Any:
    raw = _read("live-machine.json")
    containers = raw["containers"]
    if mutate is not None:
        containers = mutate(containers)
    return fc.Snapshot.from_engine(containers, raw["volumes"] if volumes is None else volumes)


def test_an_untouched_machine_passes_the_postflight(live: Any) -> None:
    assert fc.postflight(live, _after(), project=PROJECT) == []


def test_a_missing_live_container_fails(live: Any) -> None:
    after = _after(lambda cs: [c for c in cs if c["Name"] != "/hsi-go2rtc"])
    _one_problem(fc.postflight(live, after, project=PROJECT), "hsi-go2rtc", "missing")


def test_a_replaced_live_container_fails(live: Any) -> None:
    """Same name, new container: the live one was removed and recreated."""

    def replace(cs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cs[4]["Id"] = "0" * 64
        return cs

    _one_problem(fc.postflight(live, _after(replace), project=PROJECT), "hsi-go2rtc", "missing")


def test_a_stopped_live_container_fails(live: Any) -> None:
    def stop(cs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cs[0]["State"].update(Status="exited", Running=False)
        return cs

    _one_problem(
        fc.postflight(live, _after(stop), project=PROJECT),
        "nemotron-v3-home-security-intelligence_backend_1",
        "no longer running",
    )


def test_a_restarted_live_container_fails(live: Any) -> None:
    """A restart that already finished leaves it running, with a new start time."""

    def restart(cs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cs[2]["State"]["StartedAt"] = "2026-10-10T15:04:41.000000Z"
        return cs

    _one_problem(
        fc.postflight(live, _after(restart), project=PROJECT),
        "nemotron-v3-home-security-intelligence_ai-vlm_1",
        "restarted",
    )


def test_a_stopped_container_is_held_only_to_existing(live: Any) -> None:
    """The package asks that a running container keep running with its start
    time; a stopped one only has to still exist (it may be started and
    stopped again in the meantime)."""
    stopped = [c for c in live.containers if not c.running]
    assert [c.name for c in stopped] == ["test-orchestrator-ai-yolo26-151714443697"]

    def cycle(cs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cs[-1]["State"]["StartedAt"] = "2026-10-10T15:04:41.000000Z"
        return cs

    assert fc.postflight(live, _after(cycle), project=PROJECT) == []


def test_another_runs_teardown_is_not_a_live_change(
    run_containers: list[dict[str, Any]],
) -> None:
    """Two runs on one machine: the other run's containers and volumes come
    and go; they belong to a test deployment, not to anything live."""
    raw = _read("live-machine.json")
    other = copy.deepcopy(run_containers[0])
    other["Name"] = "/hsi-check-other-postgres-1"
    other["Config"]["Labels"]["com.docker.compose.project"] = "hsi-check-other"
    before = fc.Snapshot.from_engine(
        [*raw["containers"], other], [*raw["volumes"], "hsi-check-other_pgdata"]
    )
    after = fc.Snapshot.from_engine(raw["containers"], raw["volumes"])
    assert fc.postflight(before, after, project=PROJECT) == []


def test_a_missing_live_volume_fails(live: Any) -> None:
    raw = _read("live-machine.json")
    volumes = [v for v in raw["volumes"] if not v.endswith("_postgres_data")]
    _one_problem(
        fc.postflight(live, _after(volumes=volumes), project=PROJECT),
        "nemotron-v3-home-security-intelligence_postgres_data",
        "missing",
    )


def test_a_teardown_that_leaves_run_containers_fails_but_is_not_urgent(
    live: Any, run_containers: list[dict[str, Any]]
) -> None:
    """The run's own leftovers fail the run (exit 1); exit 3 and the urgent
    path are for something that existed before the run."""
    raw = _read("live-machine.json")
    after = fc.Snapshot.from_engine(
        [*raw["containers"], run_containers[0]], [*raw["volumes"], f"{PROJECT}_pgdata"]
    )
    assert fc.postflight(live, after, project=PROJECT) == []
    problems = fc.leftovers(live, after, project=PROJECT)
    assert len(problems) == 2, problems
    assert f"{PROJECT}-postgres-1" in problems[0]
    assert f"{PROJECT}_pgdata" in problems[1]


# ---------------------------------------------------------------------------
# Snapshots round-trip into the run's artifacts
# ---------------------------------------------------------------------------


def test_a_snapshot_round_trips_through_json(live: Any) -> None:
    assert fc.Snapshot.from_json(json.loads(json.dumps(live.to_json()))) == live


def test_a_snapshot_reads_published_ports_and_running_bind_paths(live: Any) -> None:
    assert {8000, 5432, 8098, 8090, 1984, 8554} <= live.host_ports
    assert "/export/foscam" in live.running_bind_sources
    assert "nemotron-v3-home-security-intelligence" in live.projects


# ---------------------------------------------------------------------------
# Compose never reads the checkout's .env or the caller's shell
# ---------------------------------------------------------------------------


def test_the_script_runs_on_python_3_10() -> None:
    """It runs on the operator sandbox's and the runners' own python3, not the
    project's 3.14: a formatter targeting 3.14 strips the parentheses from
    ``except (A, B):``, which no earlier Python parses."""
    import ast

    ast.parse(SCRIPT.read_text(encoding="utf-8"), feature_version=(3, 10))


def test_compose_runs_with_the_runs_env_file_and_project(tmp_path: Path) -> None:
    command = fc.compose_command(
        engine="docker",
        project=PROJECT,
        env_file=tmp_path / "env",
        files=[tmp_path / "compose.json"],
    )
    assert command[:2] == ["docker", "compose"]
    assert command[command.index("--env-file") + 1] == str(tmp_path / "env")
    assert command[command.index("-p") + 1] == PROJECT


def test_compose_sees_only_the_engine_environment() -> None:
    caller = {
        "PATH": "/usr/bin",
        "HOME": "/home/agent",
        "DOCKER_HOST": "unix:///run/docker.sock",
        "IMAGE_TAG": "leaked",
        "FOSCAM_BASE_PATH": "/export/foscam",
        "COMPOSE_FILE": "docker-compose.prod.yml",
        "COMPOSE_PROJECT_NAME": "nemotron-v3-home-security-intelligence",
    }
    env = fc.compose_environment(caller)
    assert env == {
        "PATH": "/usr/bin",
        "HOME": "/home/agent",
        "DOCKER_HOST": "unix:///run/docker.sock",
    }


# ---------------------------------------------------------------------------
# The smoke check and the drop helper
# ---------------------------------------------------------------------------


def test_the_smoke_check_has_image_bytes_of_its_own() -> None:
    """The backend deduplicates images by content for 300 s across cameras,
    so a golden path that drops another scenario's image right after the
    smoke check must still get its event."""
    book = json.loads((fc.SCENARIO_DIR / "scenarios.json").read_text(encoding="utf-8"))
    smoke = [s for s in book["scenarios"] if s["name"] == fc.SMOKE_SCENARIO]
    assert len(smoke) == 1
    smoke_bytes = (fc.SCENARIO_DIR / smoke[0]["image"]).read_bytes()
    others = [s for s in book["scenarios"] if s["name"] != fc.SMOKE_SCENARIO]
    assert others
    for scenario in others:
        assert (fc.SCENARIO_DIR / scenario["image"]).read_bytes() != smoke_bytes


def test_the_scenario_book_outcomes_survive_a_fixture_image_swap() -> None:
    """[r287 item 8] The photographs replace the drawings; the outcomes do not move.

    The swap changes WHICH bytes hash to WHICH book entry, and nothing else:
    every name, detection, verdict and reply delay is carried by
    scenarios.json, and the fake is byte-keyed (scenarios.py hashes the bytes
    it RECEIVES). These pins are the substance of the ruling-287 clause that
    lets the swap stand -- "how O2.5's rule that the fake tier stays as it is
    still holds": the tier's ANSWERS are unchanged, so every ScenarioBook
    consumer keeps its scenario. One image per scenario (uniqueness) and the
    smoke bytes distinct from every other scenario's (the dedupe pin above)
    are re-asserted over the SWAPPED files, so a swap that accidentally
    aliased two scenarios or split the smoke bytes reds here.
    """
    book = json.loads((fc.SCENARIO_DIR / "scenarios.json").read_text(encoding="utf-8"))
    scenarios = book["scenarios"]
    assert [s["name"] for s in scenarios] == [
        "person-at-door",
        "cat-on-porch",
        "car-in-driveway",
        "slow-reply",
        "harness-smoke",
    ]
    # The verdicts the tiers pin: person 82 confirmed, cat 4 rejected, car 45
    # uncertain (the DO-1 medium band), slow-reply 70 with its 40 s delay, smoke 61.
    by_name = {s["name"]: s for s in scenarios}
    assert by_name["person-at-door"]["verdict"]["risk_score"] == 82
    assert by_name["cat-on-porch"]["verdict"]["risk_score"] == 4
    assert by_name["car-in-driveway"]["verdict"]["risk_score"] == 45
    assert by_name["slow-reply"]["verdict"]["risk_score"] == 70
    assert by_name["slow-reply"]["reply_delay_seconds"] == 40
    assert by_name["harness-smoke"]["verdict"]["risk_score"] == 61
    # Routing still works: the book the fake loads at startup resolves every
    # image, hashes it, and the five digests stay distinct.
    loaded = (
        fc._load_scenario_book_for_test() if hasattr(fc, "_load_scenario_book_for_test") else None
    )
    if loaded is None:
        from backend.ai_contract.fake.scenarios import ScenarioBook

        loaded = ScenarioBook.load(fc.SCENARIO_DIR)
    assert len(loaded) == 5, len(loaded)
    digests = {s.digest for s in loaded}
    assert len(digests) == 5, "two scenarios share an image"


def test_drop_lands_the_image_in_the_camera_folder(tmp_path: Path) -> None:
    image = fc.SCENARIO_DIR / "person-at-door.jpg"
    landed = fc.drop(image, "front-door", tmp_path)
    assert landed == tmp_path / "front-door" / "person-at-door.jpg"
    assert landed.read_bytes() == image.read_bytes()


def test_drop_refuses_a_camera_root_that_does_not_exist(tmp_path: Path) -> None:
    with pytest.raises(fc.HarnessError, match="does not exist"):
        fc.drop(fc.SCENARIO_DIR / "person-at-door.jpg", "front-door", tmp_path / "missing")


@pytest.mark.parametrize(
    "url",
    ["http://10.0.0.5:8000/api/events", "http://host.docker.internal:8000/", "http://localhost:1/"],
)
def test_the_harness_talks_only_to_its_own_loopback_ports(url: str) -> None:
    with pytest.raises(fc.HarnessError, match=r"127\.0\.0\.1"):
        fc._http("GET", url)


def test_the_harness_ignores_proxy_settings_for_its_own_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """urllib honours HTTP_PROXY; a NO_PROXY without 127.0.0.1 would send the
    harness's calls to the proxy instead of the run's own published ports."""
    import http.server
    import threading

    class Answer(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: Any) -> None:
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Answer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for name in ("HTTP_PROXY", "http_proxy"):
            monkeypatch.setenv(name, "http://127.0.0.1:9")
        for name in ("NO_PROXY", "no_proxy"):
            monkeypatch.delenv(name, raising=False)
        url = f"http://127.0.0.1:{server.server_address[1]}/"
        assert fc._http("GET", url, timeout=2) == (200, {"ok": True})
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------
# Exit codes and the summary
# ---------------------------------------------------------------------------


def test_real_refuses_where_agent_gpu_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--real serves models only through agent-gpu (owner ruling 66); on a
    machine without it, the run says so with its own exit code (exit 2 means
    the preflight refused) and creates nothing."""
    monkeypatch.setenv("PATH", str(tmp_path / "no-agent-gpu"))
    monkeypatch.setenv("AGENT_GPU_LIBRARY", str(tmp_path))
    assert fc.main(["--real", "--root", str(tmp_path / "runs")]) == fc.EXIT_UNAVAILABLE == 4
    assert not (tmp_path / "runs").exists()


def test_real_refuses_without_the_model_library(
    agent_gpu: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AGENT_GPU_LIBRARY")
    assert fc.main(["--real", "--root", str(tmp_path / "runs")]) == fc.EXIT_UNAVAILABLE
    assert not (tmp_path / "runs").exists()


def test_an_unexpected_error_still_tears_down_and_records_its_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whatever breaks once the stack may be up, teardown and the postflight
    run, and summary.json records the exit the process returns."""
    calls: list[str] = []
    empty = fc.Snapshot(containers=(), volumes=frozenset())

    def prepare(self: Any) -> Any:
        for path in (self.dir, self.cameras, self.artifacts):
            path.mkdir(parents=True, exist_ok=True)
        return empty

    def up(self: Any, vlm: Any = None) -> None:
        self.started = True
        raise KeyError("id")

    def collect(self: Any) -> None:
        calls.append("collect")
        raise TimeoutError("compose logs")

    def teardown(self: Any, before: Any) -> tuple[list[str], list[str]]:
        calls.append("teardown")
        return [], []

    monkeypatch.setattr(fc.Run, "prepare", prepare)
    monkeypatch.setattr(fc.Run, "render", lambda *_: None)
    monkeypatch.setattr(fc.Run, "up", up)
    monkeypatch.setattr(fc.Run, "collect", collect)
    monkeypatch.setattr(fc.Run, "teardown", teardown)

    status = fc.main(["--fake", "--root", str(tmp_path), "--image-tag", "test"])
    assert status == 1
    assert calls == ["collect", "teardown"]
    (summary,) = tmp_path.glob("hsi-check-*/artifacts/summary.json")
    assert json.loads(summary.read_text(encoding="utf-8"))["exit"] == 1


# ---------------------------------------------------------------------------
# The real tier (owner ruling 66): the real VLM through agent-gpu, the fake
# detector kept
# ---------------------------------------------------------------------------

VLM_URL = "http://host.docker.internal:18123"
SERVED_MODEL = "Qwen3VL-8B-Instruct-Q4_K_M"

# A stand-in for the agent-gpu CLI: it logs each call as a JSON line, keeps
# the names `run` started until `rm` removes them, and lists them on `ps`. It
# refuses a name as the broker does (its policy and refusal, quoted from the
# operator's first --real run on #6961).
AGENT_GPU_STUB = """#!/usr/bin/env python3
import json, os, re, sys
log = os.environ["AGENT_GPU_STUB_LOG"]
state = log + ".running"
with open(log, "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
names = open(state).read().split() if os.path.exists(state) else []
verb = sys.argv[1]
if verb == "run":
    name = sys.argv[sys.argv.index("--name") + 1]
    if not re.fullmatch("[a-z0-9][a-z0-9-]{0,31}", name):
        print("agent-gpu: refused.policy: name: must match [a-z0-9][a-z0-9-]{0,31}", file=sys.stderr)
        sys.exit(1)
    if os.environ.get("AGENT_GPU_STUB_RUN_EXIT"):
        print("admission refused: 38 of 40 GiB declared", file=sys.stderr)
        sys.exit(int(os.environ["AGENT_GPU_STUB_RUN_EXIT"]))
    open(state, "w").write("\\n".join([*names, name]))
    print(f"{name}: admitted")
    url = os.environ.get("AGENT_GPU_STUB_RUN_URL", "http://host.docker.internal:18123")
    print(f"port 8098 -> {url}")
elif verb == "rm" and os.environ.get("AGENT_GPU_STUB_KEEP") != "1":
    open(state, "w").write("\\n".join(n for n in names if n != sys.argv[2]))
elif verb == "ps":
    print("NAME IMAGE VRAM")
    for name in names:
        if os.environ.get("AGENT_GPU_STUB_PS_ANONYMOUS"):
            print("c0ffee ai-vlm:0000000 14GiB")
        else:
            print(f"{os.environ.get('AGENT_GPU_STUB_PS_PREFIX', '')}{name} ai-vlm:0000000 14GiB")
elif verb == "status":
    print("declared 0 of 40 GiB")
elif verb == "images":
    print(os.environ.get("AGENT_GPU_STUB_IMAGES", ""))
"""


class AgentGpuStub:
    def __init__(self, bin_dir: Path, log: Path) -> None:
        self.bin_dir = bin_dir
        self.log = log

    def calls(self) -> list[list[str]]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def verbs(self) -> list[str]:
        return [call[0] for call in self.calls()]


@pytest.fixture
def agent_gpu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AgentGpuStub:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "agent-gpu"
    stub.write_text(AGENT_GPU_STUB, encoding="utf-8")
    stub.chmod(0o755)
    log = tmp_path / "agent-gpu.log"
    monkeypatch.setenv("PATH", f"{bin_dir}:{Path(sys.executable).parent}:/usr/bin:/bin")
    monkeypatch.setenv("AGENT_GPU_LIBRARY", str(tmp_path / "library"))
    monkeypatch.setenv("AGENT_GPU_STUB_LOG", str(log))
    return AgentGpuStub(bin_dir, log)


@pytest.fixture
def real_deployment(base: dict[str, Any]) -> dict[str, Any]:
    return fc.as_test_deployment(base, project=PROJECT, run_dir=RUN_DIR, vlm_url=VLM_URL)


def _run(tmp_path: Path, mode: str = "real") -> Any:
    run = fc.Run(engine="docker", root=tmp_path / "runs", image_tag="test", mode=mode)
    run.artifacts.mkdir(parents=True)
    return run


def test_the_real_tier_takes_the_vlm_from_agent_gpu_and_keeps_the_fake_detector(
    real_deployment: dict[str, Any],
) -> None:
    services = real_deployment["services"]
    assert "ai-vlm" not in services
    assert "ai-gateway" in services
    backend = services["backend"]
    assert backend["environment"]["AI_VLM_URL"] == VLM_URL
    assert "ai-vlm" not in backend["depends_on"]
    assert "ai-gateway" in backend["depends_on"]
    # host.docker.internal resolves in the sandbox's Docker on its own; a
    # host-gateway entry would name the sandbox, not the GB300's runner.
    assert "extra_hosts" not in backend


def test_the_real_test_deployment_reaches_the_host_only_on_the_agent_gpu_port(
    real_deployment: dict[str, Any], live: Any
) -> None:
    assert _preflight(real_deployment, live, allowed_host_ports=frozenset({18123})) == []
    _one_problem(
        _preflight(real_deployment, live, allowed_host_ports=frozenset({18124})),
        "backend",
        "host.docker.internal:18123",
    )


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        (
            "vlm: admitted\nport 8098 -> http://host.docker.internal:18123\n",
            ("http://host.docker.internal:18123", 18123),
        ),
        (
            "port 8098 -> http://host.docker.internal:18199/",
            ("http://host.docker.internal:18199", 18199),
        ),
    ],
)
def test_the_vlm_url_is_the_one_agent_gpu_run_prints(
    output: str, expected: tuple[str, int]
) -> None:
    assert fc.agent_gpu_url(output) == expected


@pytest.mark.parametrize(
    "output",
    [
        "vlm: admitted",
        "port 8099 -> http://host.docker.internal:18123",
        "port 8098 -> http://host.docker.internal:8000",
        "port 8098 -> http://192.168.1.20:18123",
        "port 8098 -> https://host.docker.internal:18123",
        "port 8098 -> http://host.docker.internal:18123/v1",
    ],
)
def test_a_vlm_url_outside_the_runners_pool_refuses(output: str) -> None:
    """The runner publishes from 18100-18199 on the host's loopback; any other
    address could be the live stack's API, database or engine."""
    with pytest.raises(fc.HarnessError, match="agent-gpu run"):
        fc.agent_gpu_url(output)


# ---------------------------------------------------------------------------
# [r195] box 1: the address the HARNESS dials vs the address its CONTAINERS dial
#
# The owner's maui run (record 6193951294) printed `port 8098 ->
# http://host.docker.internal:18100` from a plain host login, where that name
# does not resolve (`curl: (6) Could not resolve host`), while
# `http://127.0.0.1:18100/health` answered `{"status":"ok"}` at the same pool
# port. The run sat out its whole 900 s readiness and died at `/health ... (0)`.
# Inside the operator sandbox the same name DOES resolve - this sandbox's own
# `getaddrinfo("host.docker.internal")` answers 169.254.1.1, the proxy that
# forwards to the host - which is why today's behavior works there.
#
# So the printed URL is one address for two vantage points, and they differ:
# `AI_VLM_URL` and `check_vlm_reach` are read from INSIDE the backend
# container (loopback there is that container's own), while `wait_ready` dials
# from the harness process, which ran `agent-gpu run` itself and so sits on the
# machine that published the port. The split keeps both: the alias stays
# byte-identical for the containers, and only the harness may use loopback.
# ---------------------------------------------------------------------------

DIAL_URL = "http://host.docker.internal:18123"


@pytest.mark.parametrize(
    ("alias_resolves", "want"),
    [
        # Inside a sandbox: the name resolves to the proxy that forwards to the
        # host, so today's behavior must not change by one byte.
        (True, "http://host.docker.internal:18123"),
        # A host login: no entry for the name, and the publisher's loopback is
        # where the runner published (measured by the owner on maui).
        (False, "http://127.0.0.1:18123"),
    ],
    ids=["sandbox", "host-login"],
)
def test_the_harness_dials_the_form_this_machine_can_reach(alias_resolves: bool, want: str) -> None:
    got = fc.vlm_dial_url(DIAL_URL, 18123, alias_resolves=lambda _name: alias_resolves)
    assert got == want


@pytest.mark.parametrize(
    ("url", "port", "needle"),
    [
        ("http://host.docker.internal:8000", 8000, "8000"),
        ("http://192.168.1.20:18123", 18123, "192.168.1.20"),
        ("https://host.docker.internal:18123", 18123, "https"),
    ],
    ids=["off-pool-port", "foreign-host", "wrong-scheme"],
)
def test_the_loopback_form_refuses_what_the_printed_url_refuses(
    url: str, port: int, needle: str
) -> None:
    """Box 1's second clause: reaching the VLM on loopback must not widen what a
    run may reach. Both machines refuse - the loopback path is a different
    ADDRESS for the same pool port, never a different port or host."""
    for probe in (lambda _name: True, lambda _name: False):
        with pytest.raises(fc.HarnessError, match=re.escape(needle)):
            fc.vlm_dial_url(url, port, alias_resolves=probe)


def _nodename(*_args: Any, **_kwargs: Any) -> Any:
    raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")


def test_the_alias_probe_is_dns_and_nothing_else(monkeypatch: pytest.MonkeyPatch) -> None:
    """The signal is resolution, not a container marker: `/.dockerenv` is absent
    under rootless Podman (maui's route, box 2) and `$SANDBOX_NAME` is a runtime
    convention, while the alias exists precisely to name the machine you are NOT
    on - so it resolves exactly when dialing it can work."""
    monkeypatch.setattr(fc.socket, "getaddrinfo", _nodename)
    assert fc.host_alias_resolves("host.docker.internal") is False
    monkeypatch.setattr(
        fc.socket,
        "getaddrinfo",
        lambda *_a, **_k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.1.1", 0))],
    )
    assert fc.host_alias_resolves("host.docker.internal") is True


def test_the_run_keeps_the_alias_for_its_containers_and_takes_loopback_itself(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The two forms on one started VLM, at the source that feeds both."""
    monkeypatch.setattr(fc, "host_alias_resolves", lambda _name: False)
    monkeypatch.setattr(fc.AgentGpu, "prod_environment", lambda *_: ["PORT=8098"])
    vlm = fc.AgentGpu(_run(tmp_path))
    vlm.vlm_image = "ai-vlm:abc1234"
    vlm.start()
    # AI_VLM_URL (feature_check.py:496) and check_vlm_reach run inside the
    # backend container, where 127.0.0.1 is that container's own loopback.
    assert vlm.url == VLM_URL
    # wait_ready dials from this process, on the machine that published the port.
    assert vlm.dial_url == "http://127.0.0.1:18123"
    assert vlm.run.summary["vlm_dial_url"] == "http://127.0.0.1:18123"


def test_the_sandbox_run_dials_the_alias_it_always_dialed(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The no-change pin for the machine every run has used so far: when the
    alias resolves, the harness form IS the printed URL."""
    monkeypatch.setattr(fc, "host_alias_resolves", lambda _name: True)
    monkeypatch.setattr(fc.AgentGpu, "prod_environment", lambda *_: ["PORT=8098"])
    vlm = fc.AgentGpu(_run(tmp_path))
    vlm.vlm_image = "ai-vlm:abc1234"
    vlm.start()
    assert (vlm.url, vlm.dial_url) == (VLM_URL, VLM_URL)


def _dial_probe_sees(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    """Record what `wait_ready` dials. Each probe answers 0 (nothing answered),
    which is how the owner's maui run ended, so the readiness loop stops on its
    own and the test reads the run's own refusal."""

    seen: list[tuple[str, Any]] = []

    def fake_http(_method: str, url: str, *_args: Any, **_kwargs: Any) -> tuple[int, Any]:
        seen.append((url, _kwargs.get("origin")))
        return 0, None

    monkeypatch.setattr(fc, "_http", fake_http)
    return seen


def test_readiness_dials_the_harness_form_not_the_container_form(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`wait_ready` is the harness's own dial; a run that took the alias from
    the printed line is the run the owner watched time out on maui."""
    seen = _dial_probe_sees(monkeypatch)
    vlm = fc.AgentGpu(_run(tmp_path))
    vlm.url = VLM_URL
    vlm.host_port = 18123
    vlm.dial_url = "http://127.0.0.1:18123"
    with pytest.raises(fc.HarnessError, match=r"127\.0\.0\.1:18123 did not answer"):
        vlm.wait_ready(timeout=0)
    # origin=None sends it through _http's proxy-free 127.0.0.1 opener. The
    # alias needs the proxy (a sandbox reaches the host through it); a host
    # login with HTTP_PROXY set for internet access must NOT have its own
    # VLM probe forwarded through that proxy.
    assert seen == [("http://127.0.0.1:18123/health", None)]


def test_the_alias_readiness_dial_keeps_its_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other arm of that origin choice, so the loopback rule above is not
    simply "never pass an origin"."""
    seen = _dial_probe_sees(monkeypatch)
    vlm = fc.AgentGpu(_run(tmp_path))
    vlm.url = VLM_URL
    vlm.host_port = 18123
    vlm.dial_url = VLM_URL
    with pytest.raises(fc.HarnessError, match=r"host\.docker\.internal:18123 did not answer"):
        vlm.wait_ready(timeout=0)
    assert seen == [(f"{VLM_URL}/health", VLM_URL)]


def test_the_weight_pins_are_operator_mds() -> None:
    runbook = (REPO_ROOT / "docs" / "uplevel" / "roles" / "operator.md").read_text(encoding="utf-8")
    assert set(fc.VLM_WEIGHTS) == {fc.VLM_MODEL, fc.VLM_MMPROJ}
    for name, digest in fc.VLM_WEIGHTS.items():
        assert f"{digest}  {name}" in runbook
    assert f"$AGENT_GPU_LIBRARY/{fc.VLM_LIBRARY_DIR}" in runbook


def _library(root: Path, files: dict[str, bytes]) -> Path:
    directory = root / fc.VLM_LIBRARY_DIR
    directory.mkdir(parents=True)
    for name, content in files.items():
        (directory / name).write_bytes(content)
    return directory


def _pin(monkeypatch: pytest.MonkeyPatch, files: dict[str, bytes]) -> dict[str, str]:
    import hashlib

    pins = {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}
    monkeypatch.setattr(fc, "VLM_WEIGHTS", pins)
    return pins


PINNED = {
    "Qwen3VL-8B-Instruct-Q4_K_M.gguf": b"model",
    "mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf": b"mmproj",
}


def test_weights_that_match_the_pin_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pins = _pin(monkeypatch, PINNED)
    found = fc.weight_digests(_library(tmp_path, PINNED))
    assert found == pins
    assert fc.weight_problems(found) == []


@pytest.mark.parametrize(
    ("files", "needle"),
    [
        (
            {**PINNED, "Qwen3VL-8B-Instruct-Q4_K_M.gguf": b"another build"},
            "Qwen3VL-8B-Instruct-Q4_K_M.gguf has sha256",
        ),
        (
            {"mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf": b"mmproj"},
            "Qwen3VL-8B-Instruct-Q4_K_M.gguf is missing",
        ),
        (
            {**PINNED, "Qwen3VL-8B-Instruct-Q8_0.gguf": b"q8"},
            "Qwen3VL-8B-Instruct-Q8_0.gguf, which is not the pin",
        ),
    ],
)
def test_weights_that_are_not_the_pin_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: dict[str, bytes], needle: str
) -> None:
    """operator.md step 1: stop unless sha256sum prints exactly the pin."""
    _pin(monkeypatch, PINNED)
    _one_problem(fc.weight_problems(fc.weight_digests(_library(tmp_path, files))), needle)


def test_the_vlm_runs_with_prods_environment_and_the_librarys_weights() -> None:
    """operator.md step 3: the library's pin, then each other ai-vlm variable
    from docker-compose.prod.yml verbatim (its defaults: the run's env file
    sets none of them)."""
    yaml = pytest.importorskip("yaml")
    prod = yaml.safe_load((REPO_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"))
    raw = prod["services"]["ai-vlm"]["environment"]
    environment = fc.vlm_run_environment(raw)
    library = f"/library/{fc.VLM_LIBRARY_DIR}"
    assert environment[:2] == [
        f"MODEL_PATH={library}/Qwen3VL-8B-Instruct-Q4_K_M.gguf",
        f"MMPROJ_PATH={library}/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf",
    ]
    assert len(environment) == len(raw)
    values = dict(entry.split("=", 1) for entry in environment)
    assert values["PORT"] == str(fc.VLM_PORT) == "8098"
    assert values["CTX_SIZE"] == "32768"
    assert values["PARALLEL"] == "2"
    assert values["LLAMA_ARG_IMAGE_MAX_TOKENS"] == "1280"
    assert values["CACHE_TYPE_K"] == values["CACHE_TYPE_V"] == "q8_0"
    assert not [entry for entry in environment if "$" in entry]


@pytest.mark.parametrize("entry", ["GPU_LAYERS=${VLM_GPU_LAYERS}", "X=${Y:?set it}", "X=$Y"])
def test_a_vlm_variable_with_no_default_refuses(entry: str) -> None:
    """The run's env file sets no VLM variable, so a reference with no
    default would have the harness make up a value."""
    with pytest.raises(fc.HarnessError, match="no default"):
        fc.vlm_run_environment([entry])


def test_the_vlm_image_pulls_each_base_of_its_dockerfile() -> None:
    text = (REPO_ROOT / "ai" / "vlm" / "Dockerfile").read_text(encoding="utf-8")
    named = re.findall(r"(?im)^FROM\s+(\S+)", text)
    assert fc.dockerfile_bases(text) == named
    assert fc.dockerfile_bases(
        "FROM a:1 AS builder\nFROM builder AS test\nFROM --platform=linux/arm64 b:2\nFROM a:1\n"
    ) == ["a:1", "b:2"]
    with pytest.raises(fc.HarnessError, match="BASE"):
        fc.dockerfile_bases("ARG BASE=x\nFROM ${BASE}\n")


def _event(**overrides: Any) -> dict[str, Any]:
    verification = {
        "verdict": "confirmed",
        "engine": "llama.cpp@b7972-1a2b3c4",
        "model_id": SERVED_MODEL,
    }
    verification.update(overrides.pop("verification", {}))
    return {"id": 7, "risk_score": 61, "verification": verification, **overrides}


def test_the_fake_smoke_check_wants_the_scenarios_verdict_and_score() -> None:
    scenario = fc._scenario(fc.SMOKE_SCENARIO)
    assert fc.smoke_problems([_event()], camera="harness_smoke", scenario=scenario) == []
    _one_problem(
        fc.smoke_problems([_event(risk_score=12)], camera="harness_smoke", scenario=scenario),
        "risk_score 12",
    )


@pytest.mark.parametrize("verdict", ["confirmed", "rejected", "uncertain"])
def test_the_real_smoke_check_wants_a_verdict_from_the_served_model(verdict: str) -> None:
    """Q2 (heavy's DECIDE): the real VLM's verdict is not the scenario's, so
    the check asserts that the served model gave one."""
    event = _event(risk_score=3, verification={"verdict": verdict})
    assert fc.smoke_problems([event], camera="harness_smoke", served_model=SERVED_MODEL) == []


@pytest.mark.parametrize(
    ("verification", "needle"),
    [
        ({"verdict": "verification_failed"}, "verification_failed"),
        ({"model_id": "Qwen3VL-8B-Instruct-Q8_0"}, "Qwen3VL-8B-Instruct-Q8_0"),
        ({"model_id": "fake-ai-vlm"}, "fake-ai-vlm"),
        ({"verdict": None}, "None"),
    ],
)
def test_a_real_smoke_event_the_served_model_did_not_judge_fails(
    verification: dict[str, Any], needle: str
) -> None:
    event = _event(verification=verification)
    problems = fc.smoke_problems([event], camera="harness_smoke", served_model=SERVED_MODEL)
    _one_problem(problems, needle)


@pytest.mark.parametrize("count", [0, 2])
def test_the_smoke_check_wants_exactly_one_event(count: int) -> None:
    events = [_event(id=n) for n in range(count)]
    _one_problem(
        fc.smoke_problems(events, camera="harness_smoke", served_model=SERVED_MODEL),
        f"found {count}",
    )


def test_the_harness_reaches_no_host_port_but_the_vlms() -> None:
    for url in ("http://host.docker.internal:18124/health", "http://host.docker.internal:8000/"):
        with pytest.raises(fc.HarnessError, match=r"127\.0\.0\.1"):
            fc._http("GET", url, origin=VLM_URL)


def _serve(handler: Any) -> Any:
    import http.server
    import threading

    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _started_vlm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """A VLM the stand-in agent-gpu has started (and so lists on ps).

    The alias is pinned RESOLVING, because every caller of this helper is the
    sandbox arm: they route the probe through a stand-in proxy that answers for
    the VLM, which is how a sandbox reaches host.docker.internal. Left unpinned,
    the helper would ask this machine's DNS - true in the operator sandbox
    (169.254.1.1) and false on a CI runner, where the probe would go to a loopback
    nothing serves and those tests would red for the machine's reason, not the
    code's.
    """
    monkeypatch.setattr(fc, "host_alias_resolves", lambda _name: True)
    monkeypatch.setattr(fc.AgentGpu, "prod_environment", lambda *_: ["PORT=8098"])
    vlm = fc.AgentGpu(_run(tmp_path))
    vlm.vlm_image = "ai-vlm:abc1234"
    vlm.start()
    assert (vlm.url, vlm.host_port) == (VLM_URL, 18123)
    return vlm


def _vlm_proxy(model_path: str, seen: list[str]) -> Any:
    """A proxy that answers for the VLM, as the sandbox's proxy forwards
    host.docker.internal to the host's loopback."""
    import http.server

    class Proxy(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            seen.append(self.path)
            payload: Any = {"status": "ok"}
            if self.path.endswith("/props"):
                payload = {"build_info": "b7972-1a2b3c4", "model_path": model_path}
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: Any) -> None:
            pass

    return _serve(Proxy)


def _through(monkeypatch: pytest.MonkeyPatch, server: Any) -> None:
    for name in ("HTTP_PROXY", "http_proxy"):
        monkeypatch.setenv(name, f"http://127.0.0.1:{server.server_address[1]}")
    for name in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(name, raising=False)


def test_the_served_model_must_be_the_pin(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """operator.md step 3: wait for /health, record /props, and stop unless
    model_path names the Q4_K_M file. The sandbox reaches the runner's port
    through its proxy, so the harness does too."""
    seen: list[str] = []
    library = f"/library/{fc.VLM_LIBRARY_DIR}"
    server = _vlm_proxy(f"{library}/Qwen3VL-8B-Instruct-Q4_K_M.gguf", seen)
    try:
        _through(monkeypatch, server)
        vlm = _started_vlm(tmp_path, monkeypatch)
        vlm.wait_ready(timeout=5)
        assert seen[:1] == [f"{VLM_URL}/health"]
        assert f"{VLM_URL}/props" in seen
        assert vlm.served_model == SERVED_MODEL
        assert vlm.run.summary["build_info"] == "b7972-1a2b3c4"
        assert vlm.run.summary["model_path"] == f"{library}/Qwen3VL-8B-Instruct-Q4_K_M.gguf"
    finally:
        server.shutdown()
        server.server_close()


def test_a_served_model_that_is_not_the_pin_refuses(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = _vlm_proxy("/library/qwen3vl-8b-instruct-q8_0/Qwen3VL-8B-Instruct-Q8_0.gguf", [])
    try:
        _through(monkeypatch, server)
        vlm = _started_vlm(tmp_path, monkeypatch)
        with pytest.raises(fc.HarnessError, match="Q8_0"):
            vlm.wait_ready(timeout=5)
    finally:
        server.shutdown()
        server.server_close()


def test_the_vlm_is_built_and_served_as_operator_md_says(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pins = _pin(monkeypatch, PINNED)
    _library(tmp_path / "library", PINNED)
    monkeypatch.setattr(fc.AgentGpu, "vlm_tree", lambda *_: "abc1234")
    monkeypatch.setattr(fc.AgentGpu, "prod_environment", lambda *_: ["PORT=8098"])
    run = _run(tmp_path)
    vlm = fc.AgentGpu(run)
    vlm.prepare()
    vlm.start()

    calls = agent_gpu.calls()
    assert [call[0] for call in calls] == ["status", "images", "pull", "pull", "build", "run"]
    assert [call[1] for call in calls[2:4]] == fc.dockerfile_bases(
        (REPO_ROOT / "ai" / "vlm" / "Dockerfile").read_text(encoding="utf-8")
    )
    assert calls[4] == [
        "build",
        "--context",
        "workspace:ai/vlm",
        "--tag",
        "ai-vlm:abc1234",
        "--build-arg",
        "CUDA_ARCHITECTURES=103",
    ]
    library = f"/library/{fc.VLM_LIBRARY_DIR}"
    assert calls[5] == [
        "run",
        "--name",
        vlm.name,
        "--image",
        "ai-vlm:abc1234",
        "--vram",
        "14",
        "--port",
        "8098",
        "--ttl",
        "12",
        "--mount",
        "library:/library",
        "--env",
        f"MODEL_PATH={library}/Qwen3VL-8B-Instruct-Q4_K_M.gguf",
        "--env",
        f"MMPROJ_PATH={library}/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf",
        "--env",
        "PORT=8098",
    ]
    assert (vlm.url, vlm.host_port) == (VLM_URL, 18123)
    assert run.summary["weights"] == [f"{digest}  {name}" for name, digest in pins.items()]
    assert run.summary["vlm_image"] == "ai-vlm:abc1234"
    assert run.summary["vram"]["declared_gib"] == 14
    assert "declared 0 of 40 GiB" in run.summary["agent_gpu"]["status_before"]


@pytest.mark.parametrize(
    ("listing", "built"),
    [
        ("IMAGE TAG\nai-vlm abc1234", True),
        ("localhost/agent-uplevel-operator/ai-vlm:abc1234 5.1GB", True),
        ("ai-vlm:abc1234f 5.1GB", False),
        ("ai-vlm-old:abc1234 5.1GB", False),
        ("my-ai-vlm abc1234", False),
    ],
)
def test_the_vlm_image_is_built_once_per_state_of_ai_vlm(
    agent_gpu: AgentGpuStub,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    listing: str,
    built: bool,
) -> None:
    _pin(monkeypatch, PINNED)
    _library(tmp_path / "library", PINNED)
    monkeypatch.setattr(fc.AgentGpu, "vlm_tree", lambda *_: "abc1234")
    monkeypatch.setenv("AGENT_GPU_STUB_IMAGES", listing)
    fc.AgentGpu(_run(tmp_path)).prepare()
    expected = ["status", "images"] + ([] if built else ["pull", "pull", "build"])
    assert agent_gpu.verbs() == expected


def test_weights_that_are_not_the_pin_refuse_before_anything_is_served(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pin(monkeypatch, PINNED)
    _library(tmp_path / "library", {**PINNED, "Qwen3VL-8B-Instruct-Q4_K_M.gguf": b"q8 build"})
    monkeypatch.setattr(fc.AgentGpu, "vlm_tree", lambda *_: "abc1234")
    vlm = fc.AgentGpu(_run(tmp_path))
    with pytest.raises(fc.Refused) as refused:
        vlm.prepare()
    _one_problem(refused.value.problems, "Qwen3VL-8B-Instruct-Q4_K_M.gguf has sha256")
    assert agent_gpu.verbs() == []
    assert not vlm.started


def _green_real_run(
    monkeypatch: pytest.MonkeyPatch,
    order: list[str],
    *,
    log: Path,
    fail: str = "",
    error: type[BaseException] = RuntimeError,
    kill: int | None = None,
) -> None:
    """Every phase of a real run stubbed green but the agent-gpu calls; the
    phase named ``fail`` raises ``error``, and with ``kill`` the smoke check
    sends the process that signal. The compose teardown is logged in ``log``
    beside the stand-in's calls, so their order shows."""
    empty = fc.Snapshot(containers=(), volumes=frozenset())

    def prepare(self: Any) -> Any:
        for path in (self.dir, self.cameras, self.artifacts):
            path.mkdir(parents=True, exist_ok=True)
        return empty

    def phase(name: str, result: Any = None) -> Any:
        def call(self: Any, *args: Any, **kwargs: Any) -> Any:
            order.append(name)
            if name == "up":
                self.started = True
            if name == "teardown":
                with log.open("a", encoding="utf-8") as calls:
                    calls.write(json.dumps(["compose-down"]) + "\n")
            if name == "smoke" and kill is not None:
                os.kill(os.getpid(), kill)
            if name == fail:
                raise error(f"{name} broke")
            return result

        return call

    monkeypatch.setattr(fc.Run, "prepare", prepare)
    monkeypatch.setattr(fc.Run, "take_snapshot", phase("take_snapshot", empty), raising=False)
    monkeypatch.setattr(fc.AgentGpu, "prepare", phase("vlm.prepare"))
    monkeypatch.setattr(fc.AgentGpu, "wait_ready", phase("vlm.wait_ready"))
    monkeypatch.setattr(fc.AgentGpu, "prod_environment", lambda *_: ["PORT=8098"])
    for name, result in (
        ("render", None),
        ("up", None),
        ("register_admin", None),
        ("seed_cameras", None),
        ("check_isolation", []),
        ("smoke", []),
        ("golden", []),
        ("collect", None),
        ("teardown", ([], [])),
    ):
        monkeypatch.setattr(fc.Run, name, phase(name, result))


def test_a_green_real_run_removes_its_vlm_after_the_test_deployment(
    agent_gpu: AgentGpuStub,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    order: list[str] = []
    _green_real_run(monkeypatch, order, log=agent_gpu.log)
    monkeypatch.setattr(fc.AgentGpu, "vlm_image", "ai-vlm:abc1234", raising=False)
    status = fc.main(["--real", "--root", str(tmp_path / "runs"), "--image-tag", "test"])
    assert status == fc.EXIT_OK, capsys.readouterr().out
    assert order[-2:] == ["collect", "teardown"]
    (summary_file,) = (tmp_path / "runs").glob("hsi-check-*/artifacts/summary.json")
    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    name = summary["vlm_name"]
    assert agent_gpu.calls()[-6:] == [
        ["compose-down"],
        ["ps"],
        ["status"],
        ["stop", name],
        ["rm", name],
        ["ps"],
    ]
    assert summary["results"]["agent_gpu"] == "ok"
    assert summary["exit"] == 0
    assert summary["mode"] == "real"
    assert '"exit": 0' in capsys.readouterr().out


@pytest.mark.parametrize("seeded", [True, False], ids=["seeded", "unseeded"])
def test_a_real_run_plants_the_debug_fixtures_only_when_seeded(
    agent_gpu: AgentGpuStub,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    seeded: bool,
) -> None:
    """Ruling 235 puts the CI fixtures on the REAL tier, so the real tier has to plant them.

    ``run_check`` guards the call on ``seeded`` alone (``feature_check.py:3040``). A
    guard that also demanded ``run.mode == "fake"`` — the shape every pre-ruling
    seeded run had — keeps every fake-tier test green and leaves ``--real --seeded``
    running the seeded goldens against an UNSEEDED backend: the seeded specs then
    read fixtures that were never planted. That is the failure this pins, and it is
    the failure the operator's ruling-235 leg could not have caught on its own,
    because a leg only observes what its own seeding step left behind.

    Both arms are asserted, because a one-sided "was called" pin passes for any
    reason at all: the un-seeded arm is what says the guard is ``seeded`` and not
    simply unconditional.
    """
    order: list[str] = []
    _green_real_run(monkeypatch, order, log=agent_gpu.log)
    monkeypatch.setattr(fc.AgentGpu, "vlm_image", "ai-vlm:abc1234", raising=False)
    monkeypatch.setattr(
        fc.Run,
        "seed_debug_fixtures",
        lambda _self: order.append("seed_debug_fixtures"),
    )
    argv = ["--real"]
    if seeded:
        argv.append("--seeded")
    status = fc.main([*argv, "--root", str(tmp_path / "runs"), "--image-tag", "test"])
    assert status == fc.EXIT_OK, capsys.readouterr().out
    assert ("seed_debug_fixtures" in order) is seeded
    if seeded:
        # The fixtures are the CI's, and they are planted where the CI planted them:
        # after the cameras, before anything reads them.
        assert order.index("seed_debug_fixtures") > order.index("seed_cameras")


@pytest.mark.parametrize("fail", ["vlm.wait_ready", "render", "up", "smoke"])
def test_a_real_run_that_breaks_still_removes_its_vlm(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail: str
) -> None:
    """operator.md step 6: tear down, also after a failure."""
    order: list[str] = []
    _green_real_run(monkeypatch, order, log=agent_gpu.log, fail=fail)
    monkeypatch.setattr(fc.AgentGpu, "vlm_image", "ai-vlm:abc1234", raising=False)
    status = fc.main(["--real", "--root", str(tmp_path / "runs"), "--image-tag", "test"])
    assert status == fc.EXIT_FAILED
    assert agent_gpu.verbs()[-3:] == ["stop", "rm", "ps"]
    (summary_file,) = (tmp_path / "runs").glob("hsi-check-*/artifacts/summary.json")
    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    assert summary["results"]["agent_gpu"] == "ok"
    assert summary["exit"] == 1
    assert ("teardown" in order) == (fail not in ("vlm.wait_ready", "render"))


def test_a_vlm_that_outlives_the_run_fails_it(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """operator.md step 6: agent-gpu ps must list none of the run's containers."""
    monkeypatch.setenv("AGENT_GPU_STUB_KEEP", "1")
    order: list[str] = []
    _green_real_run(monkeypatch, order, log=agent_gpu.log)
    monkeypatch.setattr(fc.AgentGpu, "vlm_image", "ai-vlm:abc1234", raising=False)
    status = fc.main(["--real", "--root", str(tmp_path / "runs"), "--image-tag", "test"])
    assert status == fc.EXIT_FAILED
    (summary_file,) = (tmp_path / "runs").glob("hsi-check-*/artifacts/summary.json")
    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    (problem,) = summary["results"]["agent_gpu"]
    assert summary["vlm_name"] in problem


def test_a_backend_that_cannot_reach_the_vlm_says_so_when_up_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The backend's health check calls the VLM, so an unreachable VLM fails
    `up --wait` before the reach check runs; the run still names the reason."""
    import subprocess

    def deployment(self: Any, *args: str, **kwargs: Any) -> Any:
        if args[0] == "up":
            raise fc.HarnessError("docker compose ... exited 1: dependency backend failed to start")
        return subprocess.CompletedProcess(args, 1, "", "ConnectionResetError: [Errno 104]")

    monkeypatch.setattr(fc.Run, "deployment", deployment)
    vlm = fc.AgentGpu(_run(tmp_path))
    vlm.url = VLM_URL
    with pytest.raises(fc.HarnessError, match=r"cannot reach the VLM at .*Errno 104"):
        vlm.run.up(vlm)


def test_a_failed_up_with_a_reachable_vlm_keeps_its_own_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    def deployment(self: Any, *args: str, **kwargs: Any) -> Any:
        if args[0] == "up":
            raise fc.HarnessError("docker compose ... exited 1: frontend is unhealthy")
        return subprocess.CompletedProcess(args, 0, "200\n", "")

    monkeypatch.setattr(fc.Run, "deployment", deployment)
    vlm = fc.AgentGpu(_run(tmp_path))
    vlm.url = VLM_URL
    with pytest.raises(fc.HarnessError, match="frontend is unhealthy"):
        vlm.run.up(vlm)


# ---------------------------------------------------------------------------
# The summary the operator posts (packages/ops.md §O2.2: the preflight snapshot and
# each golden spec's result)
# ---------------------------------------------------------------------------


def test_the_summary_carries_the_preflight_snapshot(live: Any) -> None:
    brief = fc.snapshot_brief(live)
    assert brief["volumes"] == sorted(live.volumes)
    assert len(brief["containers"]) == len(live.containers)
    for container, line in zip(live.containers, brief["containers"], strict=True):
        state = "running" if container.running else container.status
        assert line == f"{container.name} {state} {container.started_at}"


def test_the_summary_lists_each_golden_spec(tmp_path: Path) -> None:
    junit = tmp_path / "golden.xml"
    junit.write_text(
        '<?xml version="1.0"?><testsuites><testsuite name="golden">'
        '<testcase classname="backend.tests.golden.test_events" name="test_one"/>'
        '<testcase classname="backend.tests.golden.test_events" name="test_two">'
        '<failure message="boom"/></testcase>'
        '<testcase classname="backend.tests.golden.test_events" name="test_three">'
        "<skipped/></testcase>"
        '<testcase classname="backend.tests.golden.test_events" name="test_four">'
        '<error message="setup"/></testcase>'
        '<testcase classname="golden.spec.ts" name="prints &quot;&lt;failure&gt;&quot;">'
        "<system-out><![CDATA[a passing spec that prints <failure> text]]></system-out>"
        "</testcase>"
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    spec = "backend.tests.golden.test_events::"
    assert fc.junit_results(junit) == {
        f"{spec}test_one": "passed",
        f"{spec}test_two": "failed",
        f"{spec}test_three": "skipped",
        f"{spec}test_four": "failed",
        'golden.spec.ts::prints "<failure>"': "passed",
    }


def test_a_golden_suite_with_no_report_lists_no_specs(tmp_path: Path) -> None:
    assert fc.junit_results(tmp_path / "missing.xml") == {}
    broken = tmp_path / "broken.xml"
    broken.write_text("<testsuites><testsuite", encoding="utf-8")
    assert fc.junit_results(broken) == {}


LOCK_VERSION_DEFAULT = "1.63.0"


def _write_lock(
    path: Path, version: str | None = LOCK_VERSION_DEFAULT, *, strip_version: bool = False
) -> Path:
    """A minimal ``package-lock.json`` for the fixture tree.

    Only the one key the harness reads is spelled out: the real lock's 1176
    ``packages`` entries are noise here, and a fixture that carried them would
    let a pin pass on a shape the real file does not have. ``strip_version``
    produces the lock that HAS the package but no version — the state
    ``playwright_image`` refuses rather than defaults.
    """
    entry: dict[str, Any] = {} if strip_version else {"version": version}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "name": "frontend",
                "lockfileVersion": 3,
                # Spelled as a literal, NOT f"node_modules/{fc.PLAYWRIGHT_LOCK_KEY}".
                # A fixture that builds its key from the same constant the harness
                # reads stays green when that constant is mutated — both sides move
                # together. The literal is what makes a drift in PLAYWRIGHT_LOCK_KEY
                # redden these tests, which is the drift the real lock would punish.
                "packages": {"node_modules/@playwright/test": entry},
            }
        ),
        encoding="utf-8",
    )
    return path


LOCK_REGISTRY = "mcr.microsoft.com"  # the host UR-131 says a failure must NAME
LOCK_IMAGE_V163 = f"{LOCK_REGISTRY}/playwright:v{LOCK_VERSION_DEFAULT}-noble"


def _named_registry(problem: str) -> str:
    """The host the harness's firewall clause tells the owner to allow.

    Extracted from the instruction, never substring-matched against the whole
    sentence. ``assert "mcr.microsoft.com" in problem`` cannot fail on a mutated
    ``PLAYWRIGHT_IMAGE_REGISTRY``, because the SAME sentence quotes the image
    reference — ``pull of mcr.microsoft.com/playwright:v…-noble`` — which is
    built from a SECOND constant, ``PLAYWRIGHT_IMAGE_REPOSITORY``. Measured: with
    ``PLAYWRIGHT_IMAGE_REGISTRY`` set to ``cdn.playwright.dev``, the substring
    assert still passed on the reference while the instruction named the wrong
    host. Parsing the host out of the operator instruction and comparing it to a
    literal is what makes the instruction's own value the pin's referent.
    """
    found = re.search(r"registry: (\S+) — the host to allow", problem)
    assert found, f"no operator instruction in {problem!r}"
    return found.group(1)


def _golden_only_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    node_modules: bool,
    calls: list[tuple[list[str], dict[str, Any]]],
    install_rc: int = 0,
    image_present: bool = True,
    pull_rc: int = 0,
    lock_version: str | None = LOCK_VERSION_DEFAULT,
    lock_strip_version: bool = False,
    lock_absent: bool = False,
    run_rc: int = 0,
    shard: tuple[int, int] | None = None,
    prod_shape: bool = False,
    golden_specs: tuple[str, ...] | None = None,
) -> Any:
    """A Run whose golden() reaches the Playwright branch with every filesystem
    fact pointed at tmp_path, and whose ``_run`` is recorded, not executed.

    The branch is guarded by the TEXT of ``frontend/playwright.config.ts`` (a
    regex for ``name: 'golden'``), so the fixture spells that text; the real
    repo's tree is never consulted, so the result cannot depend on whether this
    machine happens to have a frontend install.

    Ruling 143. The ruling-116 half of this fixture is gone with the step it
    modelled: the seeded ``~/.cache/ms-playwright`` whose ``INSTALLATION_COMPLETE``
    markers decided whether to download, and the fake ``install --dry-run`` that
    printed a plan of ``Install location:`` paths (see ``DRY_RUN_PLAN``, deleted
    with them). What the fixture controls now is the pair of facts the container
    leg depends on: the LOCK the image tag is read from (written here, never read
    from the repo, so a pin can bump it) and whether the engine already HAS that
    image — ``image_present`` and ``pull_rc`` are the new firewall question.
    """
    run = _run(tmp_path, mode="fake")
    if shard is not None:
        # [r264] A shard is a shape fact: it goes into the Run at construction
        # so the record written at init already names it.
        run.shard = shard
        run.summary["shard"] = f"{shard[0]}/{shard[1]}"
    if golden_specs is not None:
        # [r287] Same discipline as the shard above: the limit is a shape fact
        # set at construction, so the record written at init already names it.
        run.golden_specs = golden_specs
        run.summary["golden_specs"] = list(golden_specs)
    if prod_shape:
        run.prod_shape = True
        run.shape = f"{run.mode}-prod-shape"
    run.api, run.ui = "http://api.invalid", "http://ui.invalid"
    # The password's VALUE is never what the pins read — they only check that the
    # npm call carries no env at all, and that the container argv carries the
    # variable's NAME and not its value — so this stays a deliberate dummy.
    run.admin = {"username": "u", "password": "hunter2"}  # pragma: allowlist secret
    frontend = tmp_path / "frontend"
    config = tmp_path / "playwright.config.ts"
    config.write_text("{ name: 'golden', testDir: './tests/golden' }\n", encoding="utf-8")
    modules = frontend / "node_modules"
    if node_modules:
        modules.mkdir(parents=True)
    lock = frontend / "package-lock.json"
    if not lock_absent:
        _write_lock(lock, lock_version, strip_version=lock_strip_version)
    monkeypatch.setattr(fc, "PLAYWRIGHT_CONFIG", config)
    monkeypatch.setattr(fc, "FRONTEND", frontend)
    monkeypatch.setattr(fc, "FRONTEND_MODULES", modules)
    monkeypatch.setattr(fc, "PACKAGE_LOCK", lock)
    monkeypatch.setattr(fc, "BACKEND_GOLDEN", tmp_path / "no-backend-golden")

    def fake(self: Any, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((list(command), kwargs))
        if command[:3] == [self.engine, "image", "inspect"]:
            return subprocess.CompletedProcess(command, 0 if image_present else 1, "", "")
        if command[:2] == [self.engine, "pull"]:
            tail = "Error: pull access denied" if pull_rc else ""
            return subprocess.CompletedProcess(command, pull_rc, "", tail)
        rc = install_rc if command[:2] == ["npm", "ci"] else run_rc
        # Ruling 114 makes a golden leg that executed nothing a problem, so a
        # fixture that claims "the golden step was healthy" has to WRITE a spec.
        # Without this, the pins below would each carry a vacuity problem the
        # npm ci question never meant to assert about. It is written for the
        # CONTAINER leg only: its junit path arrives as an env value, which is
        # the seam ruling 143 kept (`-e PLAYWRIGHT_JUNIT_OUTPUT_FILE`).
        report = kwargs.get("env", {}).get("PLAYWRIGHT_JUNIT_OUTPUT_FILE")
        if report and rc == 0:
            Path(report).write_text(_RAN_JUNIT, encoding="utf-8")
        return subprocess.CompletedProcess(command, rc, "", "")

    monkeypatch.setattr(fc.Run, "_run", fake)
    return run


def _container_calls(calls: list[tuple[list[str], dict[str, Any]]]) -> list[list[str]]:
    """The ``<engine> run`` argvs golden() issued — the leg, in the image."""
    return [command for command, _ in calls if command[1:3] == ["run", "--rm"]]


def _golden_container(
    calls: list[tuple[list[str], dict[str, Any]]],
) -> tuple[list[str], dict[str, Any]]:
    """The one container call whose inner command is the golden project."""
    legs = [
        (c, k) for c, k in calls if c[1:3] == ["run", "--rm"] and "--project=golden" in " ".join(c)
    ]
    assert len(legs) == 1, [c for c, _ in legs]
    return legs[0]


# ---------------------------------------------------------------------------
# Ruling 143 Done when 1/2: the leg's wrapper, and what reaches it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("node_modules", [False, True])
def test_the_golden_step_installs_frontend_deps_only_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, node_modules: bool
) -> None:
    """Ruling 102: the operator's documented ``--real`` run died at
    ERR_MODULE_NOT_FOUND because nothing ever installed frontend/node_modules on
    their tree (the harness builds no images for it; the CI feature-check job's
    ``npm ci`` step is not this process). golden() installs when absent — and an
    existing install is LEFT ALONE, because ``npm ci`` deletes node_modules on
    entry and would blow away an operator's (or a CI runner's) working install.

    Ruling 143 keeps this step and its discipline verbatim: it still installs the
    RUNNER, which is what the container mounts, so ``--project=golden`` still
    resolves inside the image. What moved is the npx that followed it — now the
    inner command of the container argv — so the ordering assertion reads "the
    install comes before the leg" off the leg's argv.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, node_modules, calls)
    problems = run.golden()
    commands = [command for command, _ in calls]
    assert problems == []
    _golden_container(calls)
    installs = [c for c in commands if c[:2] == ["npm", "ci"]]
    if node_modules:
        assert installs == [], "an existing install must never be re-run over"
        assert "npm_ci" not in run.summary["results"]["golden"]
    else:
        assert installs == [["npm", "ci"]]
        assert commands[0] == ["npm", "ci"], "the install must come BEFORE the container leg"
        install_kwargs = calls[0][1]
        assert install_kwargs["cwd"] == tmp_path / "frontend"
        assert install_kwargs["timeout"] == 1800, "the 300 s default cannot survive a cold install"
        assert "env" not in install_kwargs, "npm must not see the run env (admin password)"
        # Positive witness that the recorder captures env= when it IS passed:
        # without this, the line above would pass even if no call ever had one.
        assert "env" in _golden_container(calls)[1], (
            "the leg keeps its env — the recorder sees env="
        )
        assert run.summary["results"]["golden"]["npm_ci"] == "ok"


def test_the_leg_runs_in_the_image_with_the_same_argv_inside(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Done when 1's shape: the golden stage runs "with the same counts as
    before", so only the wrapper may differ.

    Both sides of the wrapper are read. Outside: the engine's ``run --rm``,
    ``--network host`` (how the container reaches the stack on an
    engine-assigned port), ``frontend/`` mounted READ-ONLY at its own absolute
    path, the run dir mounted writable (where junit and ``--output`` land),
    ``-w frontend``, and the lock-derived image. Inside: the same
    ``npx playwright test --project=golden --output=… --reporter=list,junit`` the
    host leg used, so a spec count from before ruling 143 is still comparable —
    plus ``--no-install``, asserted below because it is the one addition, and it
    pins WHICH runner runs those specs rather than which specs there are.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls)
    assert run.golden() == []
    argv, kwargs = _golden_container(calls)
    assert argv[:3] == ["docker", "run", "--rm"], argv[:3]
    assert argv[argv.index("--network") + 1] == "host"
    frontend = tmp_path / "frontend"
    assert f"{frontend}:{frontend}:ro" in argv, "the source tree is read-only"
    assert f"{run.dir}:{run.dir}" in argv, "the run dir is writable, at its own path"
    assert argv[argv.index("-w") + 1] == str(frontend), "cwd is frontend/"
    # The tag the FIXTURE's lock implies, as a literal — not fc.playwright_image(...)
    # re-evaluated, which would agree with golden() no matter what golden() chose.
    assert argv[argv.index("sh") - 1] == LOCK_IMAGE_V163, "the image is the lock-derived tag"
    assert argv[argv.index("sh") :][:2] == ["sh", "-c"], "everything after is the inner command"
    inner = argv[-1]
    assert inner.startswith("npx --no-install playwright test --project=golden "), inner
    assert "--reporter=list,junit" in inner, "the same reporters, so the same counts"
    assert f"{run.artifacts / 'golden-playwright'}" in inner, "the same --output path, both sides"
    # A literal, not fc.GOLDEN_LEG_TIMEOUT_S — a re-read would agree with whatever the constant
    # says (this file's own rule above: "not fc.playwright_image(...) re-evaluated"). The value
    # is ruling 189's measurement: the slowest of the last 10 green golden legs on main was
    # 1739 s (job 116184218975 at c1b804a82), x 1.5 rounded up to a minute = 2640. A later edit
    # of the constant reds this line — that is the point — and its author brings new numbers here.
    assert kwargs["timeout"] == 2640, "a golden suite is minutes; 2640 = measured 1739 s x 1.5"


def test_the_unsharded_leg_carries_no_shard_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[r264] Without --shard the inner command is exactly today's: no `--shard=` substring.

    The union-of-legs judgment compares shard runs against the unsharded run at the
    same head, and a run record that carried a shard the argv never took would be a
    claim the leg did not make. Absence here is the pin: `--shard=` must appear in a
    sharded run's inner command and NOWHERE in an unsharded one.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls)
    run.shard = None
    assert run.golden() == []
    _inner, kwargs = _golden_container(calls)
    assert "--shard=" not in _inner, _inner
    assert kwargs["timeout"] == 2640


def test_a_sharded_leg_passes_playwrights_own_shard_selector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[r264] With shard (2,3) the inner command ends with Playwright's `--shard=2/3`.

    The flag is spelled the way Playwright documents it (`--shard=i/N`), inside the
    same container argv -- same mounts, same image, same reporters -- so a shard's
    legs are the same kinds of evidence an unsharded run's are, and the junit the
    fan-in merges is written by the same runner. The record names the shard too:
    a merged judgment must be able to say which run each leg came from. The shard
    is passed at CONSTRUCTION, like every other shape fact (mode, seeded,
    prod_shape): a record patched after init would witness nothing.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls, shard=(2, 3))
    assert run.golden() == []
    argv, _kwargs = _golden_container(calls)
    inner = argv[-1]
    assert inner.endswith(" --shard=2/3"), inner
    assert inner.startswith("npx --no-install playwright test --project=golden "), inner
    assert run.summary["results"]["golden"]["playwright"] == "ok"
    assert run.summary["shard"] == "2/3", run.summary.get("shard")


def test_a_shard_record_is_absent_on_an_unsharded_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[r264] The `shard` key exists only when a shard ran, so today's record shape holds."""
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls)
    run.shard = None
    assert run.golden() == []
    assert "shard" not in run.summary, run.summary.get("shard")


# [r287] The named-spec limit for the prod-shape Playwright leg. Refusals first
# (a partial suite outside the prod shape is a silent coverage hole, ruling 114's
# shape), then the argv pin: the inner command carries the named specs as
# Playwright positionals, the unlimited leg's argv stays byte-identical, and the
# record names what was witnessed.


def test_a_named_spec_limit_is_refused_outside_the_prod_shape(monkeypatch: Any) -> None:
    """`--golden-spec` is the prod-shape leg's option: on --fake or --real it refuses.

    Ruling 287 asks for the option "under `--prod-shape`", the mirror of the [r264]
    shard clause ("--shard is the CI fake tier's option"): a partial suite on the CI
    tier would witness the tier on a subset of its golden specs while the run record
    looked ordinary -- ruling 114's silent-coverage-hole shape. Refused at parse
    time, before any engine call, like every other shape mismatch.
    """
    booted = _fake_boot(monkeypatch)
    with pytest.raises(SystemExit):
        fc.main(["--fake", "--golden-spec", "tests/golden/dashboard/gpu-stats.spec.ts"])
    assert booted == []
    with pytest.raises(SystemExit):
        fc.main(["--real", "--golden-spec", "tests/golden/dashboard/gpu-stats.spec.ts"])
    assert booted == []


def test_a_named_spec_limit_refuses_paths_that_are_not_specs(monkeypatch: Any) -> None:
    """The option takes paths to .spec.ts files under the repo's golden tree; anything else refuses.

    Five shapes, all refused at parse time: an absolute path, a path that escapes
    the repo, a name the golden tree does not carry, a file the golden tree
    carries that is not a spec (the helpers `harness.ts`/`guard.ts` are real
    files — the is_file check alone would accept them), and a .spec.ts path
    outside the golden tree (the suffix check alone would accept it). A path
    outside `tests/golden` — or a carried non-spec file — could never be
    collected by the `--project=golden` leg, so an accepted misspelling would
    write a record naming files the leg could not run — a claim the leg did
    not make.
    """
    booted = _fake_boot(monkeypatch)
    with pytest.raises(SystemExit):
        fc.main(["--prod-shape", "--golden-spec", "/etc/passwd"])
    with pytest.raises(SystemExit):
        fc.main(["--prod-shape", "--golden-spec", "../secrets.env"])
    with pytest.raises(SystemExit):
        fc.main(["--prod-shape", "--golden-spec", "tests/golden/no-such-spec.spec.ts"])
    with pytest.raises(SystemExit):
        fc.main(["--prod-shape", "--golden-spec", "tests/golden/harness.ts"])
    with pytest.raises(SystemExit):
        fc.main(["--prod-shape", "--golden-spec", "tests/e2e/dashboard.spec.ts"])
    assert booted == []


def test_a_named_spec_limit_carries_its_specs_into_the_run(monkeypatch: Any) -> None:
    """`--prod-shape --golden-spec A --golden-spec B` reaches run_check with both, in order."""
    seen: dict[str, Any] = {}

    def fake_run_check(args: Any, *, mode: str) -> int:
        seen["specs"] = args.golden_spec
        # A throwaway Run, only to see what construction writes into the record:
        # the same pin shape the [r264] shard tests use.
        probe = fc.Run(
            engine="docker",
            root=Path("/tmp/hsi-feature-check-tests"),  # noqa: S108 - never touched
            image_tag="t",
            mode=mode,
            prod_shape=True,
            golden_specs=args.golden_spec,
        )
        seen["record"] = probe.summary
        return 0

    monkeypatch.setattr(fc, "run_check", fake_run_check)
    monkeypatch.setattr(fc, "real_unavailable", lambda _environ: None)
    argv = [
        "--prod-shape",
        "--golden-spec",
        "tests/golden/dashboard/gpu-stats.spec.ts",
        "--golden-spec",
        "tests/golden/timeline/event-detail.spec.ts",
    ]
    assert fc.main(argv) == 0
    assert seen["specs"] == (
        "tests/golden/dashboard/gpu-stats.spec.ts",
        "tests/golden/timeline/event-detail.spec.ts",
    )
    # The record is written at construction, the same place the [r264] shard
    # lands: run_check hands the parse-validated specs to Run, and the summary
    # names them from then on -- a merged judgment reads the record, not argv.
    assert seen["record"]["golden_specs"] == [
        "tests/golden/dashboard/gpu-stats.spec.ts",
        "tests/golden/timeline/event-detail.spec.ts",
    ], seen["record"]


def test_a_run_record_names_its_golden_specs_only_when_they_were_set() -> None:
    """The `golden_specs` key exists only when a limit was named (absent when unset).

    Same discipline as the shard key: today's records byte-match today's, and a
    record that named specs the run never took would be a claim it did not make.
    """
    limited = fc.Run(
        engine="docker",
        root=Path("/tmp/hsi-feature-check-tests"),  # noqa: S108 - never touched
        image_tag="t",
        mode="fake",
        golden_specs=("tests/golden/dashboard/gpu-stats.spec.ts",),
    )
    assert limited.summary["golden_specs"] == ["tests/golden/dashboard/gpu-stats.spec.ts"]
    bare = fc.Run(
        engine="docker",
        root=Path("/tmp/hsi-feature-check-tests"),  # noqa: S108 - never touched
        image_tag="t",
        mode="fake",
    )
    assert "golden_specs" not in bare.summary, bare.summary.get("golden_specs")


def test_a_named_spec_limit_limits_the_legs_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With --golden-spec the inner command names exactly the named specs.

    The specs ride the inner command as Playwright positionals -- the runner's
    own file filter -- so the leg's junit carries only them and
    golden_execution_problems keeps judging what actually ran. Paths are
    shlex-quoted like --output's, into the same shell string. Both specs are
    real files in this repo's golden tree (the parse-time validation names
    them); the timeline one is deliberately NOT named, and must not appear.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(
        tmp_path,
        monkeypatch,
        True,
        calls,
        prod_shape=True,
        golden_specs=("tests/golden/dashboard/gpu-stats.spec.ts",),
    )
    problems = run.golden()
    argv, _kwargs = _golden_container(calls)
    inner = argv[-1]
    assert "tests/golden/dashboard/gpu-stats.spec.ts" in inner, inner
    assert "tests/golden/timeline/event-detail.spec.ts" not in inner, inner
    assert problems == []


def test_the_unlimited_leg_carries_no_spec_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without --golden-spec the inner command is exactly today's: no spec positional.

    Absence pin, mirroring test_the_unsharded_leg_carries_no_shard_flag: the
    whole-suite leg must not gain a filter nobody asked for, and a record that
    named specs the argv never took would be a claim the leg did not make.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls)
    assert run.golden() == []
    _inner = _golden_container(calls)[0][-1]
    assert ".spec.ts" not in _inner, _inner
    assert "golden_specs" not in run.summary, run.summary.get("golden_specs")


def test_a_named_spec_limit_names_the_specs_in_the_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The run record says what the leg witnessed, in the option's own order.

    A merged judgment (or the operator's post) must be able to say which specs a
    limited leg ran, not just that it ran something. The limit is a shape fact
    like the [r264] shard: recorded at construction, absent when unset.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(
        tmp_path,
        monkeypatch,
        True,
        calls,
        prod_shape=True,
        golden_specs=(
            "tests/golden/dashboard/gpu-stats.spec.ts",
            "tests/golden/timeline/event-detail.spec.ts",
        ),
    )
    assert run.golden() == []
    assert run.summary["golden_specs"] == [
        "tests/golden/dashboard/gpu-stats.spec.ts",
        "tests/golden/timeline/event-detail.spec.ts",
    ], run.summary.get("golden_specs")


# [r264] Build box: the backend golden tests run once, in one shard. Shard 1 (or an
# unsharded run) keeps the pytest leg; every other shard records the skip with the
# record shape the seeded branch already writes ("skipped on ..."), and carries no
# backend_specs at all -- the fan-in's merge takes shard 1's, and a shard that ran
# no backend leg must not look like one that ran none and passed everything.
@pytest.mark.parametrize("shard", [(2, 4), (3, 4), (4, 4)])
def test_a_non_first_shard_skips_the_backend_leg_in_the_seeded_record_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shard: tuple[int, int]
) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls, shard=shard)
    run.golden()
    backend = run.summary["results"]["golden"]
    assert backend.get("backend") == f"skipped on shard {shard[0]}/{shard[1]}", backend.get(
        "backend"
    )
    assert "backend_specs" not in backend, backend.get("backend_specs")
    # no pytest invocation was recorded: every recorded argv is the Playwright leg
    assert not any(argv[0] == "uv" for argv, _ in calls), [a for a, _ in calls]
    # the recorded shard still names this run (the fan-in reads it)
    assert run.summary["shard"] == f"{shard[0]}/{shard[1]}"


def test_shard_1_still_runs_the_backend_leg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The backend golden tests run once, in ONE shard (the Build box): shard 1's."""
    run = _golden_leg(tmp_path, monkeypatch, "backend", _RAN_JUNIT)
    run.shard = (1, 4)
    run.summary["shard"] = "1/4"
    run.golden()
    backend = run.summary["results"]["golden"]
    assert backend.get("backend") == "ok", backend.get("backend")
    # The specs can only come from a report the leg's own pytest wrote, so
    # "ok" with a leg's record is the execution proof here (the fixture's
    # fake writes the report only when the leg runs).
    assert backend.get("backend_specs") == {"golden::one": "passed"}, backend.get("backend_specs")


def test_the_feature_check_job_budget_covers_the_new_cap_with_10_minutes_of_margin() -> None:
    """Ruling 189's second clause, re-measured for the [r264] sharded shape: each shard job's
    timeout-minutes leaves >= 10 minutes after boot + the golden leg + teardown on that shard's
    own clock.

    Measured on run 39202004102's four 4/4 shards (the picked shape, #7264's table): the
    slowest shard's harness clock topped at 1097 s, worst job setup (checkout through
    Playwright install, i.e. everything before the harness step) 320 s, worst teardown
    31 s. Conservative sum with the cap: 320 + 2640 + 31 = 2991 s = 49.9 min, which under
    the standing 64 min leaves 849 s >= 600. The budget is NOT raised by hand — 64 min
    stands from ruling 189 — and the pin is against the workflow file itself, so an edit
    to either side (the cap, or the budget) reds a test that says why.
    """
    yaml = pytest.importorskip("yaml")
    ci = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    job = ci["jobs"]["feature-check-shards"]
    assert job["name"] == "Feature check (fake AI)", "the job this package budgets is this job"
    minutes = job["timeout-minutes"]
    # [r264]'s re-measurement, run 39202004102's 4/4 shards, on each job's started_at/
    # completed_at clock: worst setup (to the harness step) 320 s, worst teardown 31 s.
    setup_worst_s, teardown_worst_s = 320, 31
    margin_s = minutes * 60 - (setup_worst_s + fc.GOLDEN_LEG_TIMEOUT_S + teardown_worst_s)
    assert margin_s >= 600, (
        f"ruling 189: setup + cap + teardown must leave each shard >= 10 min; "
        f"timeout-minutes: {minutes} leaves {margin_s} s"
    )


@pytest.mark.parametrize("prod_shape", [False, True])
def test_the_container_gets_environment_names_never_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prod_shape: bool
) -> None:
    """The run's admin password must not reach the logged argv.

    ``_run`` logs every command it issues (``shlex.join``) into the harness's
    stdout, and on CI that stdout IS the Actions step log — an artifact of the
    run in every practical sense, and one any operator can read. (The one file
    this job uploads as a named artifact, ``golden-playwright.log``, carries
    only the CHILD's output; the argv never reaches it. The claim used to be
    written the other way round here and in the two docs; corrected — the
    name-only rule is right for the step log, and a reader deciding what is
    safe to put in an argv needs the true carrier, not a flattering one.)
    So ``-e FEATURE_CHECK_ADMIN_PASSWORD=<value>`` would write the throwaway
    admin password into the step log. The name-only form makes the engine read
    the value from the ``env=`` this command actually runs with, which is the
    other half of this pin: the NAMES are on the argv and the VALUES are in the
    child's env, so the leg still receives its credentials. Both the engine
    view (PATH/HOME) and the run env reach the child; only the password is
    asserted by name, because that is the fact that must stay out of the log.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls)
    run.prod_shape = prod_shape
    run.golden()
    argv, kwargs = _golden_container(calls)
    password = run.admin["password"]
    assert password not in " ".join(argv), "the value is never an argv token"
    exported = [argv[i + 1] for i, token in enumerate(argv) if token == "-e"]
    # Spelled here, NOT read off fc.GOLDEN_CONTAINER_ENVIRONMENT: a pin that
    # compares the argv to the same constant that builds it is green no matter
    # what the constant drops, and a leg that loses PLAYWRIGHT_JUNIT_OUTPUT_FILE
    # writes its report somewhere the harness never reads — a golden section of
    # `{}` that still exits 0, which is ruling 114's hole reopened by a flag.
    assert set(exported) == {
        "FEATURE_CHECK_PROD_SHAPE",
        "FEATURE_CHECK_API_URL",
        "FEATURE_CHECK_UI_URL",
        "FEATURE_CHECK_CAMERA_ROOT",
        "FEATURE_CHECK_CAMERAS",
        "FEATURE_CHECK_SCENARIOS",
        "FEATURE_CHECK_ADMIN_USERNAME",
        "FEATURE_CHECK_ADMIN_PASSWORD",
        "PLAYWRIGHT_JUNIT_OUTPUT_FILE",
        "CI",
    }, "every name the spec set needs to reach the browser, and only those"
    assert not any(token.startswith("-e") and len(token) > 2 for token in argv)
    env = kwargs["env"]
    assert env["FEATURE_CHECK_PROD_SHAPE"] == ("1" if prod_shape else "0")
    assert env["FEATURE_CHECK_ADMIN_PASSWORD"] == password, "and the child still gets it"
    assert env["PLAYWRIGHT_JUNIT_OUTPUT_FILE"] == str(run.artifacts / "golden-playwright.xml")


def test_the_container_sees_ci_so_the_config_branches_as_they_did_on_the_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`CI` reaches the browser, because playwright.config.ts BRANCHES on it.

    `forbidOnly: !!process.env.CI` (config :73) and `retries: CI ? 2 : 0`
    (:79) were live on the host leg — Actions sets CI=true unconditionally, no
    workflow line needed — and the move into the container put a whitelist
    between the config and that variable. Without `-e CI` the golden leg runs
    with the .only guard OFF: one stray `test.only` executes 1 of 126, the
    junit holds 1 passed testcase, `golden_execution_problems` sees neither an
    empty nor an all-skipped set, and the leg reports green (UR-128's hole,
    measured by the self-review's scratch config: CI=true → rc 1, `env -u CI`
    → 1 passed rc 0). With retries 0 no spec can HAVE a failed attempt, so the
    flaky census reads this leg as zero flake forever (UR-129).

    Pinned as a SEPARATE test from the name-set pin above, on purpose: the
    name-set pins membership, and a drop of exactly this name out of the
    whitelist is the quiet one — the leg still runs, the specs still pass, and
    only the two guards nobody exercises change. The value assertion is the
    same shape as the password's: the name rides the argv, the value comes from
    the harness's own env, so a `CI=true` job containers-inherits `true` and a
    laptop inherits nothing — both legs match their host, which is the whole
    contract of the name-only form.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls)
    monkeypatch.setenv("CI", "true")
    run.golden()
    argv, kwargs = _golden_container(calls)
    exported = [argv[i + 1] for i, token in enumerate(argv) if token == "-e"]
    assert "CI" in exported, "the config's CI branches go dark without this name"
    assert kwargs["env"].get("CI") == "true", "name-only: the value comes from the harness env"


def _mount_sources(argv: list[str]) -> list[Path]:
    """The host paths the leg binds, from its own ``-v`` tokens."""
    return [Path(token.split(":")[0]) for token in _argv_values(argv, "-v")]


def _argv_values(argv: list[str], flag: str) -> list[str]:
    return [argv[i + 1] for i, token in enumerate(argv) if token == flag]


def test_every_path_the_container_is_told_to_read_is_inside_a_mount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path the leg EXPORTS but does not MOUNT is read as absent, silently.

    The self-review found the shape by accident: ``FEATURE_CHECK_SCENARIOS``
    names ``backend/ai_contract/fake/scenario_fixtures/scenarios.json`` and the
    leg mounted only ``frontend/`` and the run dir, so inside the image the file
    is not there — and a spec whose readiness check starts with
    ``if (!existsSync(bookPath)) return { ready: false }`` does not error. It
    SKIPS, at collection, with a reason nobody prints, in a leg that exits 0 and
    whose ``--list`` still counts it. Measured at the head this PR fixes, on the
    CI leg itself: ``playwright_specs`` read 115 passed / 11 skipped where
    main's host leg read 118 / 8, and the three newly-skipped specs are exactly
    the three that read the book (dashboard-drop, analytics, alerts). The
    container mount set is the whole diff between those two tallies.

    Pinned as the INVARIANT rather than the three paths, because the next
    exported path is the one that breaks: containment is checked for every
    ``-e`` value that looks like a filesystem path (the URL-typed names are
    skipped — ``--network host`` serves those, and they were never mounts).
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls)
    run.golden()
    argv, kwargs = _golden_container(calls)
    sources = _mount_sources(argv)
    path_typed = {
        name: value
        for name, value in kwargs["env"].items()
        if name.startswith("FEATURE_CHECK_") and value.startswith("/")
    }
    unmounted = {
        name: value
        for name, value in path_typed.items()
        if not any(value == str(src) or Path(value).is_relative_to(src) for src in sources)
    }
    assert not unmounted, f"exported but not mounted, so the leg reads it missing: {unmounted}"
    assert kwargs["env"]["FEATURE_CHECK_SCENARIOS"].startswith(str(fc.SCENARIO_DIR)), (
        "the fixture still models the book under SCENARIO_DIR (positive control: an empty "
        "unmounted set proves nothing if the env stopped naming paths)"
    )


def test_the_scenario_book_and_the_drop_shim_are_mounted_into_the_leg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The two host paths the golden specs read must be bound, at their own paths.

    Both mounts are ``:ro``: the book and the shim are inputs, and the leg's
    writes belong in the run dir. The shim is ``scripts/feature-check.sh``, which
    ``dropDo1Fixture`` (analytics-alerts/harness.ts:179) execs as
    ``repoRoot/scripts/feature-check.sh`` — with only ``backend/`` mounted that
    exec raised ``spawnSync …/scripts/feature-check.sh ENOENT``, so the fix is
    TWO mounts, not one. It is the DIRECTORY and not just the shim, because the
    shim's last line is ``exec python3 "$(dirname …)/feature_check.py"``, so the
    sibling module has to be in the container too.

    Measured, not inferred: with both mounts the three specs get past readiness
    and past the drop — the run dir came back holding
    ``cameras/car-in-driveway/car-in-driveway.jpg`` and
    ``cameras/person-at-door/person-at-door.jpg`` (``drop()`` is a
    ``shutil.copyfile`` into ``FEATURE_CHECK_CAMERA_ROOT``, which is inside the
    rw-mounted run dir, so no compose or docker client is needed, and the image
    does ship python3). The scratch arms then failed only on ``fetch failed`` /
    ``bad port``, because an arm run outside the harness has no stack; under CI,
    which does, these specs execute.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls)
    run.golden()
    argv = _golden_container(calls)[0]
    assert f"{fc.SCENARIO_DIR}:{fc.SCENARIO_DIR}:ro" in argv, "the book the specs read"
    assert f"{fc.SCRIPTS_DIR}:{fc.SCRIPTS_DIR}:ro" in argv, "the shim the specs exec"


@pytest.mark.parametrize("engine", ["docker", "podman"])
def test_the_leg_runs_on_the_engine_the_harness_runs_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, engine: str
):
    """``--engine podman`` gets a podman invocation (clause 1's last words).

    One Run object drives compose and the golden leg, so the leg reads
    ``self.engine`` — pinned on all three of its calls (inspect, pull-when-absent,
    run). The ``z`` SELinux relabel goes on the podman binds ONLY: that is
    docker-compose.prod.yml's own convention, and docker rejects the option, so a
    blanket ``z`` would break the default engine. Both sides are pinned because a
    one-sided test lets either mistake through.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls, image_present=False)
    run.engine = engine
    run.golden()
    engine_calls = [c[:2] for c, _ in calls if c[0] in ("docker", "podman")]
    assert engine_calls == [[engine, "image"], [engine, "pull"], [engine, "run"]], engine_calls
    argv, _ = _golden_container(calls)
    suffix = ",z" if engine == "podman" else ""
    frontend = tmp_path / "frontend"
    assert f"{frontend}:{frontend}:ro{suffix}" in argv
    assert f"{run.dir}:{run.dir}{suffix}" in argv


# ---------------------------------------------------------------------------
# Ruling 143 Done when 3: the image tag follows package-lock.json
# ---------------------------------------------------------------------------


def test_the_image_tag_follows_the_version_the_lock_resolves(tmp_path: Path) -> None:
    """The package's third Done-when clause in one call: "a unit test pins that
    the image tag follows ``package-lock.json``."

    "Follows" is a two-sided claim, so the pin BUMPS the lock rather than only
    reading it. A function that read the lock once and cached it, or that read
    the top-level ``version`` key (the lockfileVersion-1 shape, which no longer
    holds the Playwright version), would pass a read-only pin and fail this one.
    """
    lock = tmp_path / "package-lock.json"
    _write_lock(lock, "1.63.0")
    assert fc.playwright_image(lock) == "mcr.microsoft.com/playwright:v1.63.0-noble"
    _write_lock(lock, "1.41.2")
    assert fc.playwright_image(lock) == "mcr.microsoft.com/playwright:v1.41.2-noble", (
        "a bumped lock must move the tag: a stale tag is the locked-runner /"
        "wrong-browser mismatch ruling 116 measured, back again in image form"
    )


def test_the_image_tag_is_derived_from_the_repo_lock_not_a_literal() -> None:
    """``never hard-coded``, measured on the file the harness actually runs.

    Two assertions, because "no literal" alone is satisfiable by a function that
    hard-codes the tag somewhere else in the script. The first is the negative:
    no ``playwright:v``-shaped tag appears anywhere in ``feature_check.py``. The
    second is the positive control that makes the grep mean something — the REAL
    lock resolves a version, and the REAL function given the REAL lock returns a
    tag naming exactly that version. Without it the grep could be green because
    the literal's shape changed, not because the value is read.
    """
    source = SCRIPT.read_text(encoding="utf-8")
    assert not re.search(r"playwright:v?\d+\.\d+", source), (
        "a version literal in the harness is a second source of truth for the "
        "browser, which is the divergence ruling 143 exists to end"
    )
    resolved = json.loads(
        (REPO_ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8")
    )
    version = resolved["packages"]["node_modules/@playwright/test"]["version"]
    assert fc.playwright_image(fc.PACKAGE_LOCK) == f"{LOCK_REGISTRY}/playwright:v{version}-noble"
    # And the KEY itself, pinned directly, because no derived comparison can see
    # a drift in it: the real lock carries node_modules/playwright and
    # node_modules/playwright-core alongside, all three at 1.63.0 (measured), so
    # a key that drifted to "playwright" would still produce the same tag from
    # the same file and every equality above would hold. The sibling pins catch
    # that drift now because their fixtures spell the path as a literal; this
    # test reads the REAL lock, so it pins the constant against the literal too.
    assert fc.PLAYWRIGHT_LOCK_KEY == "@playwright/test", (
        "the lock key is a second source of truth for the browser if it drifts "
        "from the package the frontend actually depends on"
    )


@pytest.mark.parametrize(
    ("lock_strip_version", "lock_absent"),
    [(True, False), (False, True)],
    ids=["entry without a version", "no lock file at all"],
)
def test_a_lock_that_cannot_answer_refuses_rather_than_defaulting(
    tmp_path: Path, lock_strip_version: bool, lock_absent: bool
) -> None:
    """``playwright_image`` RAISES where the lock cannot answer.

    Its docstring's reason is the thing worth pinning: a defaulting version is a
    hard-coded version with extra steps, and it would run the suite in a browser
    that does not match the runner the lock resolved — ruling 116's mismatch
    class again. Both ways a lock fails to answer are pinned: the entry with no
    version, and no file at all. A CORRUPT lock (unparseable JSON) is the third
    way, and is wrapped into the same error so golden()'s one handler owns it.
    """
    lock = tmp_path / "package-lock.json"
    if not lock_absent:
        _write_lock(lock, strip_version=lock_strip_version)
    with pytest.raises(fc.HarnessError, match="image tag cannot be derived"):
        fc.playwright_image(lock)


def test_an_unparseable_lock_is_the_same_refusal(tmp_path: Path) -> None:
    """A lock that is not JSON is the third way the version source fails.

    Left raw, ``json.loads`` raises ``JSONDecodeError`` and ``read_text`` raises
    ``OSError`` — neither is a ``HarnessError``, so golden()'s single
    ``except HarnessError`` would let them fly past it to the harness's catch-all,
    which discards the results dict and every step already accounted for. One
    error type for "the tag cannot be derived" is what keeps that handler honest.
    """
    lock = tmp_path / "package-lock.json"
    lock.write_text("{ not json", encoding="utf-8")
    with pytest.raises(fc.HarnessError, match="image tag cannot be derived"):
        fc.playwright_image(lock)


# ---------------------------------------------------------------------------
# Ruling 143's firewall clause: a blocked registry is named, never worked around
# ---------------------------------------------------------------------------


def test_a_present_image_is_never_pulled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The pull is attempted only when the tag is absent locally.

    That ordering is what keeps a blocked host that HAS the image green: a
    versioned tag is content, and a present copy of it IS the right browser, so
    requiring a reachable registry there would be a workaround in the other
    direction. An absence assertion needs its positive witness, which is the pull
    pin below running the same fixture with the image absent.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls, image_present=True)
    assert run.golden() == []
    assert [c[:2] for c, _ in calls if c[1] == "pull"] == [], "no pull when inspect succeeded"
    assert run.summary["results"]["golden"]["playwright_image_pull"] == "present"
    assert run.summary["results"]["golden"]["playwright"] == "ok"


def test_a_missing_image_is_pulled_and_a_blocked_registry_names_the_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UR-131: "A blocked registry or download host is named in the failure,
    never worked around."

    So the pull is its OWN accounted step: a problem naming the registry (the
    host the owner has to allow), carrying the child's own tail, and no fallback —
    no bare ``npx`` on the host, no second tag, no ``latest``. The leg is red
    because there is genuinely no browser to run, and ruling 114's vacuity guard
    says so as well: an image that never arrived executed nothing.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls, image_present=False, pull_rc=1)
    problems = run.golden()
    pulls = [c for c, _ in calls if c[:2] == ["docker", "pull"]]
    assert pulls == [["docker", "pull", LOCK_IMAGE_V163]], (
        "exactly one pull of the tag THIS fixture's lock implies, spelled as a "
        "literal. Comparing against fc.playwright_image(fc.PACKAGE_LOCK) instead "
        "would let golden() hard-code a tag and stay green: both sides of the "
        "equality would move together. Derivation from the real lock is pinned "
        "separately, by the test that greps the harness for a version literal."
    )
    assert run.summary["results"]["golden"]["playwright_image_pull"] == "exit 1"
    named = [p for p in problems if "pull of" in p]
    assert len(named) == 1, problems
    assert _named_registry(named[0]) == LOCK_REGISTRY, (
        "UR-131 makes the failure NAME the host the owner must allow; the "
        "instruction is the only part of the sentence whose host comes from "
        "PLAYWRIGHT_IMAGE_REGISTRY, so that is the part to read"
    )
    # The host name alone is NOT the clause: `mcr.microsoft.com` is already inside
    # the image reference the sentence quotes, so a message that only says
    # "registry unreachable" would still pass a substring test on it. What makes
    # this the firewall clause is the instruction addressed to the operator.
    assert "the host to allow" in named[0]
    assert "does not work around a block" in named[0]
    # The child's OWN words, not just the harness's summary of them: an owner
    # asking IT for the allow needs to see why the pull refused (access denied,
    # TLS, name unknown) without re-running it. The fixture's fake engine prints
    # this string and nothing else produces it.
    assert "pull access denied" in named[0], "the tail of the child's own output is carried"
    assert _container_calls(calls) == [], "a leg with no image never starts"
    assert run.summary["results"]["golden"]["playwright"] == "image unavailable"
    assert any("executed no tests" in p for p in problems), "and the vacuity guard fires too"


def test_a_tag_that_cannot_be_derived_is_an_accounted_step_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """golden() commits its results only on the way out, so an exception here
    would erase the WHOLE golden section from summary.json — ruling 116's lesson,
    still load-bearing — and the operator posts that file verbatim.

    So the refused tag reads as a value plus a named problem, and the leg is red
    rather than absent. Neither a run nor a pull is issued: there is no tag to
    name, and a ``pull`` of an empty reference is not a fallback, it is noise.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls, lock_absent=True)
    problems = run.golden()
    results = run.summary["results"]["golden"]
    assert results["playwright"] == "no image tag"
    assert "playwright_image" not in results, "no tag was derived"
    assert any("image tag cannot be derived" in p for p in problems)
    assert _container_calls(calls) == []
    assert [c[:2] for c, _ in calls if c[1] == "pull"] == []
    assert any("executed no tests" in p for p in problems), "ruling 114 still guards this hole"


def test_a_failing_container_leg_is_the_legs_own_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The spec-level verdict survives the container wrapper.

    A non-zero ``docker run`` means the suite failed (or the browser failed to
    launch) INSIDE the image: the harness reports the exit it was given and keeps
    the child's output in its own log — and does NOT claim a registry problem,
    because the image was already there. Telling those two apart is what keeps
    "name the host" honest: only a failed FETCH may name a host.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls, run_rc=1)
    problems = run.golden()
    assert run.summary["results"]["golden"]["playwright"] == "exit 1"
    assert run.summary["results"]["golden"]["playwright_image_pull"] == "present"
    assert any("golden Playwright project exited 1" in p for p in problems)
    assert not any("pull of" in p for p in problems), (
        "a leg that ran and failed is not a fetch failure"
    )
    assert (run.artifacts / "golden-playwright.log").exists()


def test_a_failed_frontend_install_is_a_named_step_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The operator posts summary.json verbatim (O2.2), so an unreachable npm
    registry must NAME its step in the summary and in problems. With check=False
    the run continues — the leg that follows is context, not a crash — and the
    harness still reaches collect/teardown."""
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, False, calls, install_rc=243)
    problems = run.golden()
    # The WHOLE sequence, not its first two entries. The point of this test is
    # the docstring's claim that check=False lets the run continue, and the
    # third entry is that claim: a failed install still attempts the leg, so it
    # arrives as a named step rather than a crash. A [:2] slice keeps the order
    # and deletes the evidence. (Measured: exactly these three calls, with the
    # image already present so no pull sits between them.)
    assert [c[:2] for c, _ in calls] == [
        ["npm", "ci"],
        ["docker", "image"],
        ["docker", "run"],
    ]
    assert run.summary["results"]["golden"]["npm_ci"] == "exit 243"
    assert any("npm ci in frontend/ exited 243" in p for p in problems)


# ---------------------------------------------------------------------------
# Ruling 114: a golden run that executes nothing is a Feature Check problem


_EMPTY_JUNIT = '<?xml version="1.0"?><testsuites><testsuite name="golden"/></testsuites>'
_SKIPPED_JUNIT = (
    '<?xml version="1.0"?><testsuites><testsuite name="golden">'
    '<testcase classname="golden" name="one"><skipped/></testcase>'
    '<testcase classname="golden" name="two"><skipped/></testcase>'
    "</testsuite></testsuites>"
)
_RAN_JUNIT = (
    '<?xml version="1.0"?><testsuites><testsuite name="golden">'
    '<testcase classname="golden" name="one"/>'
    "</testsuite></testsuites>"
)


def _golden_leg(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    leg: str,
    junit_text: str | None,
) -> Any:
    """A Run whose golden() runs ONE leg to a successful exit, leaving
    ``junit_text`` as that leg's junit report (``None``: it writes none).

    Both legs judge their suite the same way, so each is exercised on its own:
    the backend leg needs a ``test_*.py`` under BACKEND_GOLDEN to enter at all,
    the Playwright leg needs the config's ``name: 'golden'`` text (see
    ``_golden_only_run`` for why that text, and not a real tree, is the trigger).
    The exit code is deliberately 0 in every case — the whole point of ruling 114
    is that a golden suite which collected nothing, or skipped everything, exits 0
    and therefore looks exactly like a golden suite that ran.
    """
    run = _run(tmp_path, mode="fake")
    run.api, run.ui = "http://api.invalid", "http://ui.invalid"
    # The password's VALUE is never what these pins read — the Playwright leg is
    # the only consumer and it is not asserted on here.
    run.admin = {"username": "u", "password": "hunter2"}  # pragma: allowlist secret
    backend_golden = tmp_path / "golden-py"
    backend_golden.mkdir()
    (backend_golden / "test_golden_events.py").write_text("def test_one():\n", encoding="utf-8")
    config = tmp_path / "playwright.config.ts"
    config.write_text("{ name: 'golden', testDir: './tests/golden' }\n", encoding="utf-8")
    modules = tmp_path / "frontend" / "node_modules"
    modules.mkdir(parents=True)  # so the Playwright leg never runs `npm ci`
    monkeypatch.setattr(
        fc, "PLAYWRIGHT_CONFIG", config if leg == "playwright" else tmp_path / "none.ts"
    )
    monkeypatch.setattr(
        fc, "BACKEND_GOLDEN", backend_golden if leg == "backend" else tmp_path / "none-py"
    )
    # golden() passes the suite as a path RELATIVE to REPO_ROOT, so the relocated
    # suite needs a REPO_ROOT that contains it. Safe to move here because _run is
    # faked: nothing else in golden() reads REPO_ROOT.
    monkeypatch.setattr(fc, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(fc, "FRONTEND", tmp_path / "frontend")
    monkeypatch.setattr(fc, "FRONTEND_MODULES", modules)
    # Ruling 143: the Playwright leg now reads the lock for its image tag before
    # it runs anything, so the fixture has to give it one. `image inspect`
    # answers "already here" so no pull is attempted and the leg runs.
    monkeypatch.setattr(
        fc, "PACKAGE_LOCK", _write_lock(tmp_path / "frontend" / "package-lock.json")
    )

    def fake(self: Any, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if command[:3] == [self.engine, "image", "inspect"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if junit_text is None:
            return subprocess.CompletedProcess(command, 0, "", "")
        # Where the report path comes from depends on the leg: the backend leg
        # passes it as a `--junitxml=` argv, the Playwright leg as an env value
        # (the container must write a path both sides can see).
        report = kwargs.get("env", {}).get("PLAYWRIGHT_JUNIT_OUTPUT_FILE")
        if report is None:
            paths = [a.split("=", 1)[1] for a in command if a.startswith("--junitxml=")]
            if not paths:
                return subprocess.CompletedProcess(command, 0, "", "")
            report = paths[0]
        Path(report).write_text(junit_text, encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(fc.Run, "_run", fake)
    return run


@pytest.mark.parametrize("leg", ["backend", "playwright"])
@pytest.mark.parametrize(
    ("junit_text", "needle"),
    [
        (_EMPTY_JUNIT, "no tests"),
        (_SKIPPED_JUNIT, "skipped"),
        (None, "no tests"),
    ],
)
def test_a_golden_project_that_executed_nothing_is_a_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, leg: str, junit_text: str | None, needle: str
) -> None:
    """Ruling 114: "When a golden project reports zero executed tests, `golden()`
    adds a problem and Feature Check goes red. That covers a project that never
    started, empty junit results, and all-skipped results."

    Before this the leg's exit code was the only verdict, and 0 is what all three
    shapes return, so a golden section of `summary.json` could read
    ``{"backend": "ok", "backend_specs": {}}`` on a run that proved nothing — the
    most expensive kind of green, because the section the operator posts looks
    accounted for.
    """
    run = _golden_leg(tmp_path, monkeypatch, leg, junit_text)
    problems = run.golden()
    _one_problem(problems, f"golden: the {leg} golden project executed", needle)


@pytest.mark.parametrize("leg", ["backend", "playwright"])
def test_a_golden_project_that_ran_a_spec_is_not_a_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, leg: str
) -> None:
    """Positive witness for the pin above: the new check must fire on vacuity, not
    on every golden run. One executed spec, exit 0, is the green this programme
    already has, and it still has to produce zero problems and an ``ok`` account.
    """
    run = _golden_leg(tmp_path, monkeypatch, leg, _RAN_JUNIT)
    assert run.golden() == []
    results = run.summary["results"]["golden"]
    assert results[leg] == "ok"
    assert list(results[f"{leg}_specs"].values()) == ["passed"]


# ---------------------------------------------------------------------------
# A stalled fetch is accounted and the run continues
# ---------------------------------------------------------------------------


def _stalled_pull_recorder(
    calls: list[tuple[list[str], dict[str, Any]]],
) -> Any:
    """A ``_run`` fake that stalls only on ``pull``, then converts the way the
    real helper does — through ``fc._stalled_result``, so if that producer's
    shape changes this test changes with it instead of staying green on a
    hand-typed copy of the shape.
    """

    def fake(self: Any, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((list(command), kwargs))
        if command[:2] == [self.engine, "pull"]:
            raise subprocess.TimeoutExpired(command, kwargs.get("timeout", 1800))
        if command[:3] == [self.engine, "image", "inspect"]:
            return subprocess.CompletedProcess(command, 1, "", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    def checked(self: Any, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        try:
            return fake(self, command, **kwargs)
        except subprocess.TimeoutExpired as expired:
            if kwargs.get("check", True):
                raise
            return fc._stalled_result(expired)

    return checked


def test_a_stalled_pull_is_a_named_problem_and_never_starts_the_leg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruling 116's firewall lesson, moved onto the step that now fetches.

    The realistic blocked-registry failure is not a refused connect — that exits
    nonzero and the pin above covers it — but a proxy that accepts and then
    streams nothing, stalling until the deadline. ``check=False`` does NOT cover a
    timeout (``subprocess.run`` raises ``TimeoutExpired`` whatever ``check``
    says), and golden() commits its results only on the way out, so a raised
    stall would erase every earlier golden entry — ruling 116's exact finding,
    which is why the ``npm_ci`` assertion below is the load-bearing one.

    The word, not the number: ``_exit_word`` prints ``timed out``, so a stall
    cannot be misread as a registry refusal. That distinction IS ruling 116's
    firewall clause — "the harness does not work around a block" only helps if
    the reader can tell a block from a stall.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, False, calls, image_present=False)
    monkeypatch.setattr(fc.Run, "_run", _stalled_pull_recorder(calls))
    problems = run.golden()
    golden_results = run.summary["results"]["golden"]
    assert golden_results["playwright_image_pull"] == "exit timed out"
    assert golden_results["npm_ci"] == "ok", "earlier steps keep their accounting"
    named = [p for p in problems if "timed out" in p]
    assert len(named) == 1, problems
    assert _named_registry(named[0]) == LOCK_REGISTRY, (
        "the firewall clause still names the host, in the instruction — not only "
        "in the image reference it quotes, which a substring test would accept "
        "from PLAYWRIGHT_IMAGE_REPOSITORY alone"
    )
    # Both of these are content the IMAGE REFERENCE cannot supply, so each one
    # fails if its clause is deleted: the instruction (the host alone is not
    # actionable — the ref already names it), and the child's own tail, which for
    # a stall is _stalled_result's note saying how long it waited.
    assert "the host to allow" in named[0]
    assert "after 1800 seconds" in named[0], "the stall's own note reaches the problem"
    assert _container_calls(calls) == [], "a pull that never returned has no image to run"
    pulls = [k for c, k in calls if c[:2] == ["docker", "pull"]]
    assert pulls and pulls[0]["timeout"] == 1800, "the deadline stays the parent's, unchanged"
    assert any("executed no tests" in p for p in problems), "ruling 114 still guards the hole"


def test_a_stalled_step_is_an_ordinary_failure_for_a_check_false_caller(
    tmp_path: Path,
) -> None:
    """_run's own conversion, against a real child that never finishes.

    Every golden() test above replaces _run with a recorder, so the deadline
    handling inside _run is reachable from here only. The child is a bare sleep
    on a short deadline on purpose: rc 124 does not depend on the child having
    started, so this asserts the conversion without racing interpreter startup
    against the deadline, and it stays far under the 1.5 s unit WARN band that
    the duration gate measures (an 1.8 s version of this pin was measured here —
    a new WARN entry of my own, in the band red 2 is about).
    """
    run = _run(tmp_path)
    stalled = run._run(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        check=False,
        timeout=0.2,
        echo=False,
    )
    assert stalled.returncode == 124, "the conventional deadline exit"
    assert stalled.stderr.startswith("timed out"), "the log names the cause, not a bare number"
    assert fc._stalled(stalled), "the reader agrees with the producer"
    assert fc._exit_word(stalled) == "timed out", "so the account says a word, not 124"
    # The other half of the contract: a caller that DID ask for a raise still
    # gets one. Without this, the conversion could silently swallow failures in
    # the compose/teardown steps that rely on check=True.
    with pytest.raises(subprocess.TimeoutExpired):
        run._run([sys.executable, "-c", "import time; time.sleep(60)"], timeout=0.2, echo=False)


def test_a_stalled_result_keeps_the_partial_stream_the_child_flushed() -> None:
    """A fetch stalled at 80% still says WHICH image was in flight.

    Pinned at the pure-function level because the fact that matters is a shape:
    TimeoutExpired hands back raw BYTES even when run() was called with
    text=True (measured on 3.14.4 — e.stdout is b'...', e.stderr is None). The
    first draft of _stalled_result guarded with isinstance(v, str) as a
    defensive nicety and silently threw that stream away; the assertion below is
    the trap it fell into, so it is pinned alongside the behaviour. The command
    and stream are illustrative — the point is the byte-vs-str shape, so it
    shows the step that can stall now (ruling 143's image pull), not the browser
    install ruling 143 removed.
    """
    exception = subprocess.TimeoutExpired(
        ["docker", "pull", "mcr.microsoft.com/playwright:v1.63.0-noble"],
        1800,
        output=b"9.2GB / 11.4GB  80%\n",
    )
    assert isinstance(exception.stdout, bytes), "the shape that made a str-only guard lossy"
    result = fc._stalled_result(exception)
    assert result.returncode == 124
    assert result.stdout == "9.2GB / 11.4GB  80%\n", "decoded, not dropped"
    assert result.stderr.startswith("timed out after 1800"), "the cause leads the text"


def _real_summary(root: Path) -> dict[str, Any]:
    (summary_file,) = root.glob("hsi-check-*/artifacts/summary.json")
    return json.loads(summary_file.read_text(encoding="utf-8"))


class _Unhandled(BaseException):
    """What a signal raises when the harness installed no handler for it."""


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGHUP])
def test_a_signal_still_tears_down_and_removes_the_vlm(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signum: int
) -> None:
    """An operator whose tool call times out sends SIGTERM. Python's default
    ends the process with no `finally`: the stack and the VLM stay up."""

    def unhandled(*_: Any) -> None:
        raise _Unhandled

    previous = signal.signal(signum, unhandled)
    try:
        order: list[str] = []
        _green_real_run(monkeypatch, order, log=agent_gpu.log, kill=signum)
        status = fc.main(["--real", "--root", str(tmp_path / "runs"), "--image-tag", "test"])
        assert signal.getsignal(signum) is unhandled, "the run restores the caller's handler"
    finally:
        signal.signal(signum, previous)
    assert status == fc.EXIT_FAILED
    assert "teardown" in order
    assert agent_gpu.verbs()[-3:] == ["stop", "rm", "ps"]
    summary = _real_summary(tmp_path / "runs")
    assert summary["exit"] == 1
    assert summary["interrupted"] == signal.Signals(signum).name


def test_ctrl_c_is_a_failed_run_that_still_tears_down(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """KeyboardInterrupt is no Exception: the summary said exit 0."""
    order: list[str] = []
    _green_real_run(monkeypatch, order, log=agent_gpu.log, fail="smoke", error=KeyboardInterrupt)
    status = fc.main(["--real", "--root", str(tmp_path / "runs"), "--image-tag", "test"])
    assert status == fc.EXIT_FAILED
    assert "teardown" in order
    assert agent_gpu.verbs()[-3:] == ["stop", "rm", "ps"]
    summary = _real_summary(tmp_path / "runs")
    assert summary["exit"] == 1
    assert summary["interrupted"] == "SIGINT"


def test_removing_the_vlm_does_not_wait_on_recording_its_vram(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    cli = fc.AgentGpu._cli

    def flaky(self: Any, *args: str, **kwargs: Any) -> Any:
        calls.append(args[0])
        if args[0] in ("ps", "status") and "stop" not in calls:
            raise subprocess.TimeoutExpired(["agent-gpu", args[0]], 300)
        return cli(self, *args, **kwargs)

    monkeypatch.setattr(fc.AgentGpu, "_cli", flaky)
    vlm = fc.AgentGpu(_run(tmp_path))
    assert vlm.teardown() == []
    assert calls == ["ps", "status", "stop", "rm", "ps"]


@pytest.mark.parametrize("real", [False, True])
@pytest.mark.parametrize(
    ("service", "test", "needle"),
    [
        (
            "frontend",
            ["CMD", "curl", "-f", "http://host.docker.internal:8000/api/health"],
            "host.docker.internal:8000",
        ),
        (
            "redis",
            ["CMD", "redis-cli", "-h", "host.docker.internal", "-p", "6379", "ping"],
            "host.docker.internal",
        ),
    ],
)
def test_a_healthcheck_that_reaches_the_host_refuses(
    base: dict[str, Any],
    live: Any,
    real: bool,
    service: str,
    test: list[str],
    needle: str,
) -> None:
    deployment = fc.as_test_deployment(
        base, project=PROJECT, run_dir=RUN_DIR, vlm_url=VLM_URL if real else None
    )
    deployment["services"][service]["healthcheck"]["test"] = test
    allowed = frozenset({18123}) if real else frozenset()
    _one_problem(_preflight(deployment, live, allowed_host_ports=allowed), service, needle)


def test_an_extra_hosts_entry_to_the_host_refuses_on_real_too(
    real_deployment: dict[str, Any], live: Any
) -> None:
    """The backend's built-in service URLs (alloy, prometheus, go2rtc) are not
    in its environment, so an alias to the host would carry them there."""
    real_deployment["services"]["redis"]["extra_hosts"] = ["alloy=host-gateway"]
    problems = _preflight(real_deployment, live, allowed_host_ports=frozenset({18123}))
    _one_problem(problems, "redis", "host-gateway")


@pytest.mark.parametrize("failure", ["refused", "outside the pool", "timed out"])
def test_a_vlm_that_fails_to_start_is_still_removed(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    order: list[str] = []
    _green_real_run(monkeypatch, order, log=agent_gpu.log)
    monkeypatch.setattr(fc.AgentGpu, "vlm_image", "ai-vlm:abc1234", raising=False)
    if failure == "refused":
        monkeypatch.setenv("AGENT_GPU_STUB_RUN_EXIT", "3")
    elif failure == "outside the pool":
        monkeypatch.setenv("AGENT_GPU_STUB_RUN_URL", "http://host.docker.internal:8000")
    else:
        cli = fc.AgentGpu._cli

        def slow(self: Any, *args: str, **kwargs: Any) -> Any:
            if args[0] == "run":
                raise subprocess.TimeoutExpired(["agent-gpu", "run"], 900)
            return cli(self, *args, **kwargs)

        monkeypatch.setattr(fc.AgentGpu, "_cli", slow)
    status = fc.main(["--real", "--root", str(tmp_path / "runs"), "--image-tag", "test"])
    assert status == fc.EXIT_FAILED
    assert "render" not in order
    name = _real_summary(tmp_path / "runs")["vlm_name"]
    calls = agent_gpu.calls()
    assert ["stop", name] in calls
    assert ["rm", name] in calls


@pytest.mark.parametrize("real", [False, True])
def test_the_preflight_allows_the_one_port_agent_gpu_printed(
    base: dict[str, Any], live: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, real: bool
) -> None:
    run = _run(tmp_path, mode="real" if real else "fake")
    vlm = fc.AgentGpu(run) if real else None
    if vlm is not None:
        vlm.url, vlm.host_port = VLM_URL, 18123
    seen: dict[str, Any] = {}

    def compose(self: Any, files: Any, *args: str, **kwargs: Any) -> Any:
        return subprocess.CompletedProcess(args, 0, json.dumps(base), "")

    def deployment(self: Any, *args: str, **kwargs: Any) -> Any:
        return subprocess.CompletedProcess(args, 0, self.compose_file.read_text(), "")

    def preflight(rendered: Any, **kwargs: Any) -> list[str]:
        seen.update(kwargs, rendered=rendered)
        return []

    monkeypatch.setattr(fc.Run, "compose", compose)
    monkeypatch.setattr(fc.Run, "deployment", deployment)
    monkeypatch.setattr(fc.Run, "host_addresses", lambda *_: frozenset())
    monkeypatch.setattr(fc, "preflight", preflight)
    run.render(live, vlm)
    assert seen["allowed_host_ports"] == (frozenset({18123}) if real else frozenset())
    backend = seen["rendered"]["services"]["backend"]["environment"]
    assert (backend.get("AI_VLM_URL") == VLM_URL) is real


def test_a_seeded_real_render_keeps_both_halves_of_the_boot(
    base: dict[str, Any], live: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruling 235's boot claim, at the seam the real tier actually renders through.

    ``Run.render`` is the only caller that passes **both** ``vlm_url`` and
    ``seeded`` (``feature_check.py:1839-1845``), so it is where the two features
    of this PR genuinely meet. Nothing else covers that conjunction: the
    deployment-level test below calls ``as_test_deployment`` directly (so it never
    runs the render), and ``test_the_preflight_allows_the_one_port_agent_gpu_printed``
    above renders *un-seeded*. A render that quietly dropped the seeded shape
    whenever a VLM was present -- ``seeded=self.seeded and vlm is None`` -- keeps
    every one of those green, and would boot an unseeded backend that the seeded
    goldens then read as if it were seeded.

    The preflight is deliberately the real one, wrapped only to capture its input:
    a render that loses the seeded ``/app/data`` tmpfs or re-adds ``ai-vlm`` to
    ``depends_on`` should be *refused* here, not merely asserted differently.
    """
    run = fc.Run(
        engine="docker", root=tmp_path / "runs", image_tag="test", mode="real", seeded=True
    )
    run.artifacts.mkdir(parents=True)
    vlm = fc.AgentGpu(run)
    vlm.url, vlm.host_port = VLM_URL, 18123
    seen: dict[str, Any] = {}
    # Bound BEFORE the swap below: `fc.preflight` is about to be this wrapper, so
    # calling it by name from inside the wrapper would recurse forever.
    real_preflight = fc.preflight

    def compose(self: Any, files: Any, *args: str, **kwargs: Any) -> Any:
        return subprocess.CompletedProcess(args, 0, json.dumps(base), "")

    def deployment(self: Any, *args: str, **kwargs: Any) -> Any:
        return subprocess.CompletedProcess(args, 0, self.compose_file.read_text(), "")

    def check(rendered: Any, **kwargs: Any) -> list[str]:
        seen.update(kwargs, rendered=rendered)
        return real_preflight(rendered, **kwargs)

    monkeypatch.setattr(fc.Run, "compose", compose)
    monkeypatch.setattr(fc.Run, "deployment", deployment)
    monkeypatch.setattr(fc.Run, "host_addresses", lambda *_: frozenset())
    monkeypatch.setattr(fc, "preflight", check)

    run.render(live, vlm)

    backend = seen["rendered"]["services"]["backend"]
    env = backend["environment"]
    # the real half: the VLM is wired in and the fake detector is gone
    assert list(seen["rendered"]["services"]) == list(fc.REAL_SERVICES)
    assert env["AI_VLM_URL"] == VLM_URL
    assert "ai-vlm" not in backend["depends_on"]
    assert seen["allowed_host_ports"] == frozenset({18123})
    # the seeded half, on top of it -- the part a render-seam regression deletes
    assert env["DEBUG"] == "true"
    assert env["REQUEST_RECORDING_ENABLED"] == "true"
    assert env["REQUEST_RECORDING_SAMPLE_RATE"] == "0.0"
    assert env["HSI_FAULT_SEED"] == "1"
    assert "/app/data:size=20m,mode=1777,uid=1000,gid=1000" in backend["tmpfs"]
    # and the render survived the REAL preflight, not a stub that always says ok
    assert run.summary["results"]["preflight"] == "ok"


@pytest.mark.parametrize(("porcelain", "refused"), [("", False), (" M ai/vlm/Dockerfile\n", True)])
def test_uncommitted_changes_under_ai_vlm_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, porcelain: str, refused: bool
) -> None:
    """The image is tagged with ai/vlm's committed tree; a dirty tree would
    build something the tag does not name. Nothing has started: exit 2."""
    commands: list[list[str]] = []

    def git(self: Any, command: list[str], **kwargs: Any) -> Any:
        commands.append(command)
        out = porcelain if "status" in command else "abc1234\n"
        return subprocess.CompletedProcess(command, 0, out, "")

    monkeypatch.setattr(fc.Run, "_run", git)
    vlm = fc.AgentGpu(_run(tmp_path))
    if refused:
        with pytest.raises(fc.Refused) as refusal:
            vlm.vlm_tree()
        _one_problem(refusal.value.problems, "ai/vlm/", "uncommitted")
    else:
        assert vlm.vlm_tree() == "abc1234"
    assert commands[0] == ["git", "-C", str(fc.REPO_ROOT), "status", "--porcelain", "--", "ai/vlm"]


@pytest.mark.parametrize(("answer", "reaches"), [("200\n", True), ("Traceback\nURLError\n", False)])
def test_the_backend_must_reach_the_vlm_once_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answer: str, reaches: bool
) -> None:
    def deployment(self: Any, *args: str, **kwargs: Any) -> Any:
        out = {"up": "", "port": "127.0.0.1:32800\n", "exec": answer}[args[0]]
        return subprocess.CompletedProcess(args, 0, out, "")

    monkeypatch.setattr(fc.Run, "deployment", deployment)
    vlm = fc.AgentGpu(_run(tmp_path))
    vlm.url = VLM_URL
    if reaches:
        vlm.run.up(vlm)
    else:
        with pytest.raises(fc.HarnessError, match="cannot reach the VLM"):
            vlm.run.up(vlm)


@pytest.mark.parametrize(
    ("environ", "argv", "engine"),
    [
        ({}, [], "docker"),
        ({"FEATURE_CHECK_ENGINE": "podman"}, [], "podman"),
        ({"FEATURE_CHECK_ENGINE": "podman"}, ["--engine", "docker"], "docker"),
    ],
)
def test_the_engine_comes_from_feature_check_engine(
    monkeypatch: pytest.MonkeyPatch, environ: dict[str, str], argv: list[str], engine: str
) -> None:
    """Ruling 66, Q3: the preflight, postflight and teardown take
    FEATURE_CHECK_ENGINE=docker|podman."""
    monkeypatch.delenv("FEATURE_CHECK_ENGINE", raising=False)
    for key, value in environ.items():
        monkeypatch.setenv(key, value)
    seen: list[str] = []
    monkeypatch.setattr(fc, "run_check", lambda args, **_: seen.append(args.engine) or 0)
    assert fc.main(["--fake", *argv]) == 0
    assert seen == [engine]


def test_a_vlm_listed_under_a_decorated_name_still_fails_the_run(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The check fails closed: any listing that contains the run's name."""
    monkeypatch.setenv("AGENT_GPU_STUB_KEEP", "1")
    monkeypatch.setenv("AGENT_GPU_STUB_PS_PREFIX", "agent-uplevel-operator-")
    monkeypatch.setattr(fc.AgentGpu, "prod_environment", lambda *_: ["PORT=8098"])
    vlm = fc.AgentGpu(_run(tmp_path))
    vlm.vlm_image = "ai-vlm:abc1234"
    vlm.start()
    _one_problem(vlm.teardown(), vlm.name)


def test_the_harness_follows_no_redirect() -> None:
    """A redirect could lead past the allowlist (to localhost, or the host)."""
    import http.server

    hits: list[str] = []

    class Target(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            hits.append(self.path)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args: Any) -> None:
            pass

    target = _serve(Target)

    class Redirect(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(302)
            self.send_header("Location", f"http://localhost:{target.server_address[1]}/")
            self.end_headers()

        def log_message(self, *args: Any) -> None:
            pass

    redirect = _serve(Redirect)
    try:
        status, _ = fc._http("GET", f"http://127.0.0.1:{redirect.server_address[1]}/", timeout=2)
        assert status == 302
        assert hits == []
    finally:
        for server in (redirect, target):
            server.shutdown()
            server.server_close()


def test_the_host_aliases_own_addresses_count_as_host_addresses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A literal host IP (Docker Desktop's 192.168.65.254) is the host too."""
    resolve = socket.getaddrinfo

    def getaddrinfo(host: str, *args: Any, **kwargs: Any) -> Any:
        if host == "host.docker.internal":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.65.254", 0))]
        if host in fc.HOST_ALIASES:
            raise socket.gaierror(host)
        return resolve(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(fc.Run, "_run", lambda *_, **__: subprocess.CompletedProcess([], 1, "", ""))
    assert "192.168.65.254" in _run(tmp_path).host_addresses()


def test_the_real_snapshot_is_taken_once_the_vlm_is_ready(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first run builds llama.cpp for hours; the preflight must judge the
    machine as it is when the test deployment starts."""
    order: list[str] = []
    _green_real_run(monkeypatch, order, log=agent_gpu.log)
    monkeypatch.setattr(fc.AgentGpu, "vlm_image", "ai-vlm:abc1234", raising=False)
    assert fc.main(["--real", "--root", str(tmp_path / "runs"), "--image-tag", "test"]) == 0
    assert order.index("vlm.wait_ready") < order.index("take_snapshot") < order.index("render")


def test_a_signal_the_caller_ignores_stays_ignored(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under nohup, SIGHUP is ignored on purpose: a closed terminal must not
    end the run, so the harness keeps an ignore it inherits."""
    previous = signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        order: list[str] = []
        _green_real_run(monkeypatch, order, log=agent_gpu.log, kill=signal.SIGHUP)
        status = fc.main(["--real", "--root", str(tmp_path / "runs"), "--image-tag", "test"])
        assert signal.getsignal(signal.SIGHUP) is signal.SIG_IGN
    finally:
        signal.signal(signal.SIGHUP, previous)
    assert status == fc.EXIT_OK
    assert "interrupted" not in _real_summary(tmp_path / "runs")
    assert "golden" in order


# ---------------------------------------------------------------------------
# agent-gpu's name policy (#6967): the first --real run on the GB300 was
# refused, `agent-gpu: refused.policy: name: must match [a-z0-9][a-z0-9-]{0,31}`
# ---------------------------------------------------------------------------


def test_the_vlm_name_fits_agent_gpus_name_policy(tmp_path: Path) -> None:
    """`<project>-vlm` was 35 characters: the project alone is 31, so the
    name is the run's id under a short prefix, not the project plus a suffix."""
    for _ in range(20):
        run = _run(tmp_path / secrets.token_hex(4))
        vlm = fc.AgentGpu(run)
        assert re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", vlm.name), vlm.name
        assert vlm.name == "hsi-vlm-" + run.project.removeprefix(fc.PROJECT_PREFIX)
        assert run.summary["vlm_name"] == vlm.name


def test_a_vlm_name_the_policy_refuses_stops_the_run_before_anything_is_served(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pin(monkeypatch, PINNED)
    _library(tmp_path / "library", PINNED)
    monkeypatch.setattr(fc.AgentGpu, "vlm_tree", lambda *_: "abc1234")
    vlm = fc.AgentGpu(_run(tmp_path))
    vlm.name = "hsi-check-20261010181711-802118-vlm"
    with pytest.raises(fc.Refused) as refused:
        vlm.prepare()
    _one_problem(refused.value.problems, vlm.name, "[a-z0-9][a-z0-9-]{0,31}")
    assert agent_gpu.verbs() == []


def test_a_policy_refused_name_ends_the_run_with_exit_2_before_the_weights(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through main: a refusal (exit 2), recorded in the summary, before the
    weights are hashed and before any agent-gpu call."""
    hashed: list[Path] = []
    monkeypatch.setattr(fc, "weight_digests", lambda directory: hashed.append(directory) or {})
    monkeypatch.setattr(fc.AgentGpu, "vlm_tree", lambda *_: "abc1234")
    monkeypatch.setattr(fc.Run, "take_snapshot", lambda *_: fc.Snapshot((), frozenset()))
    monkeypatch.setattr(fc, "VLM_NAME_PREFIX", "hsi-check-and-a-prefix-too-long-")
    status = fc.main(["--real", "--root", str(tmp_path / "runs"), "--image-tag", "test"])
    assert status == fc.EXIT_REFUSED == 2
    assert hashed == []
    assert agent_gpu.verbs() == []
    summary = _real_summary(tmp_path / "runs")
    assert summary["exit"] == 2
    assert "weights" not in summary


def test_a_vlm_that_ps_does_not_list_by_name_fails_the_run(
    agent_gpu: AgentGpuStub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The teardown proves the VLM gone by its name's absence from ps; that
    proves nothing unless ps lists it by that name while it serves."""
    monkeypatch.setenv("AGENT_GPU_STUB_PS_ANONYMOUS", "1")
    server = _vlm_proxy(f"/library/{fc.VLM_LIBRARY_DIR}/Qwen3VL-8B-Instruct-Q4_K_M.gguf", [])
    try:
        _through(monkeypatch, server)
        vlm = _started_vlm(tmp_path, monkeypatch)
        with pytest.raises(fc.HarnessError, match="does not list"):
            vlm.wait_ready(timeout=5)
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------
# O2.5 / ruling 162 item 2 — the prod-shape resource-limits decision.
#
# A rootless engine cannot start a container that asks for a resource limit
# where no cgroup controller is delegated to the caller (the O2.5 spike's
# differential control: same image, `--memory`/`--cpus` both fail with runc's
# "rootless needs no limits ... when no permission is granted for cgroups").
# So the runner decides limits at RUN time from the machine it is on, and says
# which in the run record. These pieces are CPU-only and daemon-free, so they
# are pinned here even though the boot they feed is the operator's (UR-136).
# ---------------------------------------------------------------------------

# prod.yml's limits are only ever `cpus:` and `memory:` (measured), which the
# kernel exposes as the `cpu` and `memory` controllers. `cpuset` alone is not
# enough to run a `cpus:` limit, so the predicate keys on the two that matter.
_PROD_LIMIT_RENDER = {
    "services": {
        "postgres": {"deploy": {"resources": {"limits": {"cpus": "2", "memory": "1G"}}}},
        # a reservation is a request, not a cap, and the spike's failing flag was
        # a limit (`--memory=512m`), never a bare reservation — so the strip keeps
        # reservations and preserves prod-shape fidelity for what was not shown
        # to block.
        "backend": {
            "deploy": {
                "resources": {
                    "limits": {"cpus": "8", "memory": "20G"},
                    "reservations": {"memory": "10G"},
                }
            }
        },
        "go2rtc": {"deploy": {"resources": {}}},  # a deploy with no limits
        "frontend": {},  # no deploy at all
    }
}


def test_limits_are_usable_only_where_both_controlling_cgroups_are_delegated() -> None:
    assert fc.cgroup_limits_usable("cpuset cpu io memory pids\n") is True
    assert fc.cgroup_limits_usable("cpu memory\n") is True
    # each limit kind on its own is not enough: a `cpus:` limit needs `cpu`, a
    # `memory:` limit needs `memory`, and prod declares both.
    assert fc.cgroup_limits_usable("cpuset io pids\n") is False  # cpu and memory both absent
    assert fc.cgroup_limits_usable("cpu io pids\n") is False  # memory missing
    assert fc.cgroup_limits_usable("io memory pids\n") is False  # cpu missing
    assert fc.cgroup_limits_usable("") is False
    assert fc.cgroup_limits_usable("\n") is False


def test_strip_resource_limits_removes_only_limits_and_reports_what_it_changed() -> None:
    import copy

    rendered = copy.deepcopy(_PROD_LIMIT_RENDER)
    changed = fc.strip_resource_limits(rendered)
    services = rendered["services"]
    # The count is the non-vacuity control: a strip that changed nothing would
    # return 0 and this test could not tell it apart from a working one.
    assert changed == 2, changed
    assert "limits" not in services["postgres"]["deploy"]["resources"]
    assert "limits" not in services["backend"]["deploy"]["resources"]
    # reservations survive the strip (only limits were shown to block);
    # an empty resources and a deploy-free service are left untouched, not created.
    assert services["backend"]["deploy"]["resources"] == {"reservations": {"memory": "10G"}}
    assert services["go2rtc"]["deploy"] == {"resources": {}}
    assert services["frontend"] == {}


def test_strip_resource_limits_is_idempotent_and_never_adds_a_deploy() -> None:
    import copy

    once = copy.deepcopy(_PROD_LIMIT_RENDER)
    fc.strip_resource_limits(once)
    assert fc.strip_resource_limits(once) == 0  # a second pass changes nothing
    # a service with no deploy is not given one by the strip
    once["services"]["brand-new"] = {"image": "x"}
    fc.strip_resource_limits(once)
    assert "deploy" not in once["services"]["brand-new"]


def test_the_limits_decision_records_the_exact_string_ruling_162_names() -> None:
    # ruling 162 item 2 names these verbatim; the run record must carry them, not
    # a paraphrase, because the operator pastes the record and a reader greps it.
    assert fc.LIMITS_APPLIED == "limits: applied"
    assert fc.LIMITS_STRIPPED == "limits: not applied (no cgroup delegation)"


def test_the_limits_decision_strips_only_when_cgroups_are_not_delegated() -> None:
    # The branch is where the bug hides: decide, act, and record must agree in one
    # call, or a run could strip on a machine that supports limits, or record
    # "applied" while the render still carries a limit it cannot enforce.
    import copy

    delegated = copy.deepcopy(_PROD_LIMIT_RENDER)
    label = fc.decide_resource_limits(delegated, "cpuset cpu io memory pids\n")
    assert label == fc.LIMITS_APPLIED
    # applied => the limits are still there (this is what the operator gets enforced)
    assert "limits" in delegated["services"]["postgres"]["deploy"]["resources"]

    stripped = copy.deepcopy(_PROD_LIMIT_RENDER)
    label = fc.decide_resource_limits(stripped, "cpuset io pids\n")
    assert label == fc.LIMITS_STRIPPED
    assert "limits" not in stripped["services"]["postgres"]["deploy"]["resources"]
    # a machine with neither controller nor a limit to enforce is still "not applied"
    assert fc.decide_resource_limits({"services": {}}, "") == fc.LIMITS_STRIPPED


def test_the_prod_shape_env_file_is_generated_and_carries_no_host_secret(
    tmp_path: Path,
) -> None:
    # Ruling 162 item 3 + O2.2's own rule that compose never reads the checkout's
    # .env or the caller's shell. Measured against the real render (drop-one matrix
    # on prod + the prod-shape override): exactly three variables are REQUIRED --
    # PODMAN_SOCKET, POSTGRES_PASSWORD (both `${X:?…}` in docker-compose.prod.yml)
    # and PROD_SHAPE_RUN_ROOT (the override's). Dropping any one exits 1 and names
    # that one; there are 154 `${X:-default}` references and no other bare ones.
    run_dir = tmp_path / "run-1"
    caller = {
        "PODMAN_SOCKET": "/run/user/1000/podman/podman.sock",
        "POSTGRES_PASSWORD": "hunter2",  # pragma: allowlist secret
    }

    text = fc.prod_shape_env(run_dir=run_dir, image_tag="test", caller=caller)
    values = dict(
        line.split("=", 1) for line in text.splitlines() if line and not line.startswith("#")
    )
    assert {"PODMAN_SOCKET", "POSTGRES_PASSWORD", "PROD_SHAPE_RUN_ROOT", "IMAGE_TAG"} <= set(values)
    # the run directory is where UR-133 says every writable bind must land
    assert values["PROD_SHAPE_RUN_ROOT"] == str(run_dir)
    assert values["IMAGE_TAG"] == "test"
    assert values["PODMAN_SOCKET"] == caller["PODMAN_SOCKET"], (
        "the socket path is a path, not a secret"
    )
    # the host's postgres password must NOT reach a disposable test deployment
    assert "hunter2" not in text
    assert values["POSTGRES_PASSWORD"] != caller["POSTGRES_PASSWORD"]
    # a fixed value copied from an example would pass everything above and still be
    # a shared secret across runs: two runs of the same run dir must differ
    again = fc.prod_shape_env(run_dir=run_dir, image_tag="test", caller=caller)
    second = dict(line.split("=", 1) for line in again.splitlines() if "=" in line)
    assert second["POSTGRES_PASSWORD"] != values["POSTGRES_PASSWORD"], (
        "password is per-run, not constant"
    )
    # and with no socket to name the caller gets a refusal, not a blank string
    # (compose would only warn and interpolate "/" -- the same failure mode as the
    # run root, which the override already refuses outright)
    with pytest.raises(fc.HarnessError):
        fc.prod_shape_env(run_dir=run_dir, image_tag="test", caller={})


def test_the_prod_shape_env_gives_the_run_its_own_container_name_prefix(
    tmp_path: Path,
) -> None:
    # UR-133: a run's objects are isolated by its compose project -- EXCEPT a pinned
    # `container_name`, which the project does NOT namespace. Measured on compose
    # v5.5.1: booting the same pinned name under a second -p dies with `Conflict. The
    # container name "/x" is already in use by container ...`, so a prod-shape run and
    # any other prod-shape run on the machine cannot both come up. The override
    # therefore prefixes each pinned name with a per-run token it reads from this env
    # file (as ${HSI_TEST_NAME_PREFIX:?…}, so a missing token refuses the render rather
    # than interpolating blank and silently rejoining the colliding set).
    run_dir = tmp_path / "run-1"
    caller = {"PODMAN_SOCKET": "/run/user/1000/podman/podman.sock"}

    def values_of(text: str) -> dict[str, str]:
        return {
            line.split("=", 1)[0]: line.split("=", 1)[1]
            for line in text.splitlines()
            if "=" in line
        }

    first = values_of(fc.prod_shape_env(run_dir=run_dir, image_tag="test", caller=caller))
    assert "HSI_TEST_NAME_PREFIX" in first, (
        "the override pins container names the project cannot namespace; it needs this run's "
        "token from the env file it renders with"
    )
    token = first["HSI_TEST_NAME_PREFIX"]
    # a name is `hsi-test-<token><prod-pin>`: token must end in a separator and be
    # container-name-safe, or the pinned name compose writes is one compose rejects.
    assert token.endswith("-"), token
    assert re.fullmatch(r"[0-9a-f]{6,16}-", token), (
        f"token {token!r} is not lowercase hex + separator; project names and container names "
        "both reject other spellings (measured: 'invalid project name' / name conflict errors)"
    )
    second = values_of(fc.prod_shape_env(run_dir=run_dir, image_tag="test", caller=caller))
    assert second["HSI_TEST_NAME_PREFIX"] != token, (
        "a constant token is the collision this exists to prevent, restated as a variable"
    )


_ENGINE_SOCKET = "/run/user/1000/podman/podman.sock"


def _svc(**volumes: Any) -> dict[str, Any]:
    """One service per keyword; each value is a mount spec or a list of them. A spec
    is (source, target) or (source, target, {extra fields})."""
    services = {}
    for name, spec in volumes.items():
        specs = spec if isinstance(spec, list) else [spec]
        services[name] = {"volumes": [_mount(s) for s in specs]}
    return {"services": services}


def _mount(spec: Any) -> dict[str, Any]:
    if isinstance(spec, dict):
        return {"type": "bind", **spec}
    source, target, *extra = spec
    return {"type": "bind", "source": source, "target": target, **(extra[0] if extra else {})}


def test_the_run_refuses_a_render_that_still_mounts_the_engine_socket() -> None:
    # UR-134. The static CI oracle (scripts/test_prodshape_override.py) proves the
    # committed override clears the two mounts prod has TODAY; this is the run-time
    # twin, and its reason to exist is drift: a run happens at whatever checkout the
    # operator brought, so a socket prod grew since the override was authored is not
    # covered by it and must stop the run rather than start a container that can
    # drive the host's engine.
    prod_shaped = _svc(
        backend=(_ENGINE_SOCKET, "/var/run/podman/podman.sock", {}),
        alloy=(_ENGINE_SOCKET, _ENGINE_SOCKET, {}),  # prod interpolates it into BOTH fields
    )
    hits = fc.engine_socket_mounts(prod_shaped, socket_path=_ENGINE_SOCKET)
    assert {h[0] for h in hits} == {"backend", "alloy"}, hits
    # must-ignore side. Deliberately NOT "the override's render, as a fixture I typed":
    # the override clears the socket mounts, but the authority for that is
    # test_prodshape_override.py, which renders the real file -- a hand-written
    # socket-free fixture here would assert my own guess and could not disagree with
    # anything. What this clause must show is that the predicate does not flag the
    # mounts a COMPLIANT prod-shape render really keeps: named volumes, and a writable
    # bind inside the run directory.
    compliant = {
        "services": {
            "node-exporter": {
                "volumes": [
                    {"type": "volume", "source": "tempo-data", "target": "/var/tempo"},
                    {"type": "bind", "source": "/run/hsitest/cameras", "target": "/cameras"},
                ]
            },
            "postgres": {
                "volumes": [
                    {"type": "volume", "source": "pg", "target": "/var/lib/postgresql/data"}
                ]
            },
        }
    }
    assert fc.engine_socket_mounts(compliant, socket_path=_ENGINE_SOCKET) == []
    # ...and the two predicates DISAGREE on purpose. `is_engine_socket` counts "/" and
    # "/var" as holding a socket, which is precisely why the fail-closed preflight
    # refuses the prod shape (node-exporter's `/:/host:ro` is a breach by its rules,
    # on every render). Wiring this check to it would make every prod-shape run refuse
    # itself, so the divergence is asserted, not left to a reader's judgement.
    assert fc.is_engine_socket("/"), "the preflight's rule, kept for the CI path"
    assert (
        fc.engine_socket_mounts(
            _svc(node_exporter=("/", "/host", {"read_only": True})), socket_path=_ENGINE_SOCKET
        )
        == []
    ), "the prod-shape path's rule: the engine's own socket, not the host's root"
    # a socket-shaped path that is NOT the engine's is not a breach (no blanket .sock
    # ban -- a test deployment may legitimately mount one)
    other = _svc(backend=("/run/hsitest/gpg-agent.sock", "/in/gpg.sock", {}))
    assert fc.engine_socket_mounts(other, socket_path=_ENGINE_SOCKET) == []


def test_a_read_only_engine_socket_mount_is_still_a_breach() -> None:
    # `read_only: true` on a socket is not a permission boundary: the socket IS the
    # engine's API, and opening it read-write is what the container does after the
    # mount exists. So the UR-134 check must not filter on the mount's mode -- which
    # is why the predicate below reads source/target only.
    ro = _svc(alloy=(_ENGINE_SOCKET, _ENGINE_SOCKET, {"read_only": True}))
    assert [h[0] for h in fc.engine_socket_mounts(ro, socket_path=_ENGINE_SOCKET)] == ["alloy"]
    # and a docker-targeted engine reaches the same verdict through the target field,
    # which is how a socket the caller did not name is still caught
    docker_sock = _svc(backend=("/host/elsewhere.sock", "/var/run/docker.sock", {}))
    assert [h[0] for h in fc.engine_socket_mounts(docker_sock, socket_path=_ENGINE_SOCKET)] == [
        "backend"
    ]


# ---------------------------------------------------------------------------
# O2.5 Step 2: the --prod-shape flag (package text: "feature_check.py --real
# --prod-shape (the flag's name is the package's call)"). This slice is the CLI
# seam only -- that the flag exists, is refused off --real, and that the chosen
# shape reaches run_check, which is where the prod render decision lives.
# ---------------------------------------------------------------------------


def test_prod_shape_reaches_run_check_with_the_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, bool]] = []

    def fake_run_check(args: Any, *, mode: str) -> int:
        seen.append((mode, args.prod_shape))
        return 0

    monkeypatch.setattr(fc, "real_unavailable", lambda _environ: None)
    monkeypatch.setattr(fc, "run_check", fake_run_check)
    assert fc.main(["--real", "--prod-shape"]) == 0
    assert seen == [("real", True)]


def test_prod_shape_without_real_is_a_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # "--prod-shape --fake" would mean "the CI stack, in the shape of prod" -- two
    # compose files that cannot both be the one rendered. argparse's own error
    # (SystemExit 2) is the answer, and it must be the answer BEFORE any engine call.
    called: list[Any] = []
    monkeypatch.setattr(fc, "run_check", lambda *a, **_k: called.append(a) or 0)
    with pytest.raises(SystemExit) as caught:
        fc.main(["--fake", "--prod-shape"])
    assert caught.value.code == 2
    assert called == []
    # and the default stays honest for every other invocation
    seen: list[bool] = []
    monkeypatch.setattr(fc, "run_check", lambda args, **_kw: seen.append(args.prod_shape) or 0)
    assert fc.main(["--fake"]) == 0
    assert seen == [False]


def test_prod_shape_without_real_now_reaches_run_check(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ruling 256 item 2: the maui run is `feature_check.py --prod-shape` with the fake
    # VLM, from a host login -- no --real, because nothing on maui's path runs agent-gpu
    # for it. The old gate ("--prod-shape needs --real -- it is the real tier's
    # production shape") was written when the prod shape had exactly one caller; the
    # venue split gives it a second, and the flag refusal is now the thing in the
    # maui command's way. --fake --prod-shape stays refused (the CI stack has no prod
    # shape), and --seeded --prod-shape keeps its own refusal (production never runs
    # DEBUG=true). The mode handed to run_check is "fake" -- the fake VLM serves the
    # engine wire the CI tier's fake serves, and the run's tier strings name it.
    seen: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        fc, "run_check", lambda args, *, mode: seen.append((mode, args.prod_shape)) or 0
    )
    assert fc.main(["--prod-shape"]) == 0
    assert seen == [("fake", True)]


def test_run_check_builds_the_run_with_the_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The forwarding itself: main() only holds the flag; run_check is what hands it
    # to the Run that renders. A run_check that drops it would render the CI stack
    # while the operator believes prod was exercised -- and the summary above would
    # still be self-consistent, because both would say "real". So this pins the
    # exact handoff, not the two ends.
    import argparse

    captured: dict[str, Any] = {}
    real_init = fc.Run.__init__

    def spy(self: Any, **kwargs: Any) -> None:
        captured.update(kwargs)
        real_init(self, **kwargs)

    monkeypatch.setattr(fc.Run, "__init__", spy)

    class StopHere(Exception):
        pass

    # prepare() runs BEFORE run_check's try block, so this propagates out of
    # run_check untouched -- which is exactly what we want: every Run kwarg is
    # already captured, and no engine, VLM or artifact code runs.
    def stop(*_a: Any, **_k: Any) -> None:
        raise StopHere

    monkeypatch.setattr(fc.Run, "prepare", stop)
    args = argparse.Namespace(
        engine="podman", root=tmp_path / "runs", image_tag="test", prod_shape=True
    )
    with pytest.raises(StopHere):
        fc.run_check(args, mode="real")
    assert captured.get("prod_shape") is True, "run_check must forward the flag to Run"
    assert captured.get("mode") == "real"


def test_the_shape_is_recorded_in_the_run_summary(tmp_path: Path) -> None:
    # A run record that does not say which stack was rendered cannot witness
    # ruling 127's real-tier rows -- the whole point of the O2.5 run.
    run = fc.Run(
        engine="podman", root=tmp_path / "runs", image_tag="test", mode="real", prod_shape=True
    )
    assert run.summary["mode"] == "real-prod-shape"
    # and the ordinary tiers keep the strings they already emit
    plain = fc.Run(engine="docker", root=tmp_path / "runs", image_tag="test", mode="real")
    assert plain.summary["mode"] == "real"
    fake = fc.Run(engine="docker", root=tmp_path / "runs", image_tag="test", mode="fake")
    assert fake.summary["mode"] == "fake"


# ---------------------------------------------------------------------------
# O2.5 Step 2 slice 2: the prod render itself -- the generated env file, the
# two-file compose, the limits decision recorded from THIS machine, and the
# UR-134 re-check on the render the run actually got (drift, not the static gate).
# ---------------------------------------------------------------------------


def _prod_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, socket: str | None = None) -> Any:
    if socket is None:
        monkeypatch.delenv("PODMAN_SOCKET", raising=False)
    else:
        monkeypatch.setenv("PODMAN_SOCKET", socket)
    run = fc.Run(
        engine="podman",
        root=tmp_path / "runs",
        image_tag="test",
        mode="real",
        prod_shape=True,
    )
    # what prepare() leaves behind, without prepare()'s engine calls
    run.dir.mkdir(parents=True)
    run.artifacts.mkdir(parents=True)
    run.env_file.write_text(f"IMAGE_TAG={run.image_tag}\n", encoding="utf-8")
    return run


def _fake_compose(run: Any, rendered: dict[str, Any]) -> list[Any]:
    """Record every compose(...) call; answer the render with `rendered`."""
    calls: list[Any] = []

    def compose(files: Any, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((list(files), args))
        return subprocess.CompletedProcess(["fake"], 0, stdout=json.dumps(rendered), stderr="")

    run.compose = compose  # instance attribute: shadow the bound method
    return calls


def _prod_rendered(**services: Any) -> dict[str, Any]:
    # `backend` is in every prod render (and as_prod_shape_deployment refuses a render
    # without it, exactly as as_test_deployment refuses a stack missing a kept service).
    # A caller that needs a specific backend passes one and wins.
    return {"services": {"backend": {"image": "backend:test"}, **services}}


_PG_LIMITS = {"image": "pg:1", "deploy": {"resources": {"limits": {"memory": "512M"}}}}


def test_the_prod_render_swaps_in_the_generated_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    calls = _fake_compose(run, _prod_rendered(postgres=_PG_LIMITS))

    run.render(fc.Snapshot.from_engine([], []))

    env = dict(line.split("=", 1) for line in run.env_file.read_text(encoding="utf-8").splitlines())
    # The surface is an exact set on purpose: compose reads this file and nothing else, so a key
    # silently added or dropped here changes the render. HSI_TEST_NAME_PREFIX is a deliberate
    # addition -- a pinned container_name is not namespaced by the compose project, so the
    # override needs this run's token to keep two runs off the same name.
    assert {
        "IMAGE_TAG",
        "PODMAN_SOCKET",
        "POSTGRES_PASSWORD",
        "PROD_SHAPE_RUN_ROOT",
        "HSI_TEST_NAME_PREFIX",
    } == set(env)
    assert env["PROD_SHAPE_RUN_ROOT"] == str(run.dir)
    assert env["IMAGE_TAG"] == "test"
    assert env["PODMAN_SOCKET"] == _ENGINE_SOCKET
    # the files are prod + the authored override (the UR-133/134 transform the static
    # oracle pins) -- and, since ruling 256's venue split, the CI+fake render whose two
    # fake bodies the transforms swap in. On the maui shape (no VLM passed) the runner
    # still renders CI+fake: the fake VLM body comes from there. Two named calls, ordered.
    assert [list(files) for files, _ in calls] == [
        [fc.PROD_STACK, fc.PROD_SHAPE_OVERRIDE],
        [fc.CI_STACK, fc.FAKE_OVERLAY],
    ]


def test_the_prod_shape_render_lifts_the_device_changes_into_the_run_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Ruling 256's record duty, end to end: every transform test above reads
    # `as_prod_shape_deployment(...)._device_changes` — the payload key the transform
    # returns — but no test drove a render through `Run.render_prod_shape`, so the lift
    # that actually publishes it (`rendered.pop("_device_changes")` ->
    # `summary["results"]["device_changes"]`) had no witness: a rename of the payload
    # key or the summary key passed all 291 tests while the summary carried nothing.
    # Driven with a device-carrying prod render through BOTH venues, with the
    # transforms' real inputs (the CI+fake render answers the second compose call).
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    # the fake bodies must survive the run's own deepcopy in fake_service_bodies()
    ci_render = json.dumps({"services": {"ai-vlm": _fake_vlm_body()}})

    def compose_dispatch(files: Any, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        prod = _prod_rendered(**_ruling256_doc()["services"])
        body = ci_render if fc.CI_STACK in files else json.dumps(prod)
        return subprocess.CompletedProcess(["fake"], 0, stdout=body, stderr="")

    run.compose = compose_dispatch  # type: ignore[method-assign] # both renders, by file set
    run.render(fc.Snapshot.from_engine([], []), vlm=None)  # vlm=None -> the maui venue

    recorded = run.summary["results"]["device_changes"]
    assert "ai-vlm" in json.dumps(recorded) and "nvidia.com/gpu=0" in json.dumps(recorded), (
        f"the maui venue's one device change must reach the summary's results: {recorded}"
    )
    assert "ai-gateway" not in json.dumps(recorded), "the maui venue strips nothing else"
    # and the artifact is still the post-splice, post-limits render the run boots
    landed = json.loads((run.artifacts / "prod-rendered.json").read_text(encoding="utf-8"))
    assert "devices" not in landed["services"]["ai-vlm"]


# ---------------------------------------------------------------------------
# [O2.5 venue fixes, ruling 287] item 4: the Triton cache knobs. The seed is a
# plain per-run COPY of a host cache into the run dir (the override binds
# ${PROD_SHAPE_RUN_ROOT}/triton-cache, so the copy is what `up` boots); the
# export is an opt-in one-off `compose run` against the real gateway image,
# ordered ONNX-first because export_reid.py's B2.2 provenance rule refuses to
# compile a plan from an ONNX no record vouches for.
# ---------------------------------------------------------------------------


def test_the_triton_cache_seed_is_copied_per_run_without_sharing_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The venue's per-run cache: a shared host seed is COPIED into the run dir,
    # never bound in place, so one run's plan build cannot poison the next
    # run's cache (and the seed itself is never written).
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "model.plan").write_bytes(b"seed")
    monkeypatch.setenv("PROD_SHAPE_TRITON_CACHE_SEED", str(seed))
    run = _prod_run(tmp_path / "a", monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    _fake_compose(run, _prod_rendered(postgres=_PG_LIMITS))
    run.render(fc.Snapshot.from_engine([], []))
    copied = run.dir / "triton-cache" / "model.plan"
    assert copied.read_bytes() == b"seed"
    # the copy is the run's own: writing it cannot reach back into the seed
    copied.write_bytes(b"run-specific")
    assert (seed / "model.plan").read_bytes() == b"seed"


def test_a_triton_cache_seed_that_is_not_a_directory_is_refused_by_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A mistyped path (a file, or a directory that does not exist) must refuse
    # the render with the path named, not fail later as a compose mount of
    # nothing or an empty cache the export then "fixes" silently.
    monkeypatch.setenv("PROD_SHAPE_TRITON_CACHE_SEED", str(tmp_path / "no-such-dir"))
    run = _prod_run(tmp_path / "a", monkeypatch, socket=_ENGINE_SOCKET)
    calls = _fake_compose(run, _prod_rendered(postgres=_PG_LIMITS))
    with pytest.raises(fc.HarnessError, match="no-such-dir"):
        run.render(fc.Snapshot.from_engine([], []))
    assert calls == []


@pytest.mark.parametrize("precision", [None, "fp32"])
def test_the_triton_export_fails_loudly_and_arms_teardown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, precision: str | None
) -> None:
    # PROD_SHAPE_EXPORT_TRITON=1 runs the ONNX-then-plan export as a one-off
    # `compose run` against the real gateway image, with PROD_SHAPE_REID_PRECISION
    # validated (fp16 default, fp32 the venue's opt-in -- TensorRT 11 has no
    # --fp16, diagnostic db7dbe). A failed export must (a) leave the full
    # output in triton-export.txt, (b) have set started BEFORE the one-off so
    # its compose-created resources reach the normal down -v teardown, and
    # (c) name the artifact in the error.
    run = _prod_run(tmp_path / "a", monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setenv("PROD_SHAPE_EXPORT_TRITON", "1")
    if precision is None:
        monkeypatch.delenv("PROD_SHAPE_REID_PRECISION", raising=False)
    else:
        monkeypatch.setenv("PROD_SHAPE_REID_PRECISION", precision)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    _fake_compose(run, _prod_rendered(postgres=_PG_LIMITS))
    monkeypatch.setattr(run, "prebuild_images", lambda: None)

    def failed_export(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, "export stdout", "export failure")

    monkeypatch.setattr(run, "deployment", failed_export)
    with pytest.raises(fc.HarnessError, match="Triton export failed"):
        run.render(fc.Snapshot.from_engine([], []))
    assert run.started is True, "teardown must be armed before the one-off runs"
    artifact = (run.artifacts / "triton-export.txt").read_text(encoding="utf-8")
    assert "export stdout" in artifact and "export failure" in artifact


def test_the_triton_export_argv_runs_onnx_first_then_the_plan_in_the_gateway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The one-off's shape, pinned at the argv seam: `compose run --rm --no-deps
    # -T --entrypoint /bin/bash ai-gateway`, a single bash script, and INSIDE it
    # the ONNX exports precede the reid plan compile -- export_reid.py's B2.2
    # provenance rule refuses a plan whose sibling ONNX carries no record, so
    # the other order can only fail on the venue. The precision knob reaches
    # the plan step, and the yolo26 ONNX --device is cpu (the maui venue's
    # diagnostic exported ONNX on CPU: a7c96f's plan build, not its ONNX, was
    # the GPU-bound step).
    run = _prod_run(tmp_path / "a", monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setenv("PROD_SHAPE_EXPORT_TRITON", "1")
    monkeypatch.setenv("PROD_SHAPE_REID_PRECISION", "fp32")
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    _fake_compose(run, _prod_rendered(postgres=_PG_LIMITS))
    monkeypatch.setattr(run, "prebuild_images", lambda: None)
    calls: list[tuple[Any, Any]] = []

    def record(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, "exported", "")

    monkeypatch.setattr(run, "deployment", record)
    run.render(fc.Snapshot.from_engine([], []))
    assert len(calls) == 1, calls
    (argv, kwargs) = calls[0]
    assert argv[:6] == ("run", "--rm", "--no-deps", "-T", "--entrypoint", "/bin/bash"), argv
    assert "ai-gateway" in argv
    script = argv[-1]
    # ONNX exports before the plan (the provenance rule's order), the plan
    # carrying the venue's precision choice.
    assert script.index("export_yolo26.py") < script.index("export_reid.py"), script
    assert script.index("--output-path /models/cache/reid/1/model.onnx") < script.index(
        "--output-path /models/cache/reid/1/model.plan"
    ), script
    assert "--precision fp32" in script
    assert "--device cpu" in script
    assert kwargs["timeout"] >= 1800, "an 83.9s plan build is the FAST case; the cap is not"


def test_the_triton_export_is_refused_on_the_sandbox_venue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The sandbox venue's gateway is the FAKE (a uvicorn stub with no Triton,
    # no exporter, no model repository): an export there would witness a
    # deployment that cannot happen. The refusal names the venue.
    run = _prod_run(tmp_path / "a", monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setenv("PROD_SHAPE_EXPORT_TRITON", "1")
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    ci_render = json.dumps(
        {"services": {"ai-vlm": _fake_vlm_body(), "ai-gateway": _fake_gateway_body()}}
    )

    def compose_dispatch(files: Any, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        prod = _prod_rendered(**_ruling256_doc()["services"])
        body = ci_render if fc.CI_STACK in files else json.dumps(prod)
        return subprocess.CompletedProcess(["fake"], 0, stdout=body, stderr="")

    run.compose = compose_dispatch  # type: ignore[method-assign]
    with pytest.raises(fc.HarnessError, match="real-gateway"):
        run.render(fc.Snapshot.from_engine([], []), vlm=_StubVlm())


def test_no_triton_export_runs_when_the_knob_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Default runs perform no export (ruling 287: "Defaults ... stay unchanged"):
    # the render with the knob unset never issues a compose run -- and the
    # invalid-precision refusal cannot fire either, because validation only
    # exists under the knob.
    run = _prod_run(tmp_path / "a", monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.delenv("PROD_SHAPE_EXPORT_TRITON", raising=False)
    monkeypatch.setenv("PROD_SHAPE_REID_PRECISION", "bogus")
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    _fake_compose(run, _prod_rendered(postgres=_PG_LIMITS))

    def no_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise AssertionError(f"no one-off should run without the knob: {args}")

    monkeypatch.setattr(run, "deployment", no_run)
    run.render(fc.Snapshot.from_engine([], []))  # must not raise


def test_an_invalid_reid_precision_is_refused_under_the_export_knob(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The validated knob (ruling 287 item 4): a free-form value must refuse at
    # render time, not reach the venue's shell as part of a generated script.
    run = _prod_run(tmp_path / "a", monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setenv("PROD_SHAPE_EXPORT_TRITON", "1")
    monkeypatch.setenv("PROD_SHAPE_REID_PRECISION", "int8")
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    _fake_compose(run, _prod_rendered(postgres=_PG_LIMITS))
    monkeypatch.setattr(run, "prebuild_images", lambda: None)
    with pytest.raises(fc.HarnessError, match="PROD_SHAPE_REID_PRECISION"):
        run.render(fc.Snapshot.from_engine([], []))


def test_the_prod_shape_render_lifts_the_sandbox_device_changes_into_the_run_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The other venue: with a VLM (any --real run), the sandbox transform strips the
    # gateway's CDI + deploy reservation, drops dcgm-exporter and strips the backend's
    # reservation — and the record must name all of them, not just the VLM swap.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    ci_render = json.dumps(
        {"services": {"ai-vlm": _fake_vlm_body(), "ai-gateway": _fake_gateway_body()}}
    )

    def compose_dispatch(files: Any, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        prod = _prod_rendered(**_ruling256_doc()["services"])
        body = ci_render if fc.CI_STACK in files else json.dumps(prod)
        return subprocess.CompletedProcess(["fake"], 0, stdout=body, stderr="")

    run.compose = compose_dispatch  # type: ignore[method-assign] # both renders, by file set
    # a started AgentGpu carries its URL; a bare AgentGpu(run) has url=None and the venue
    # guard refuses fake_gateway without vlm_url -- so this uses the started-shape stub.
    run.render(fc.Snapshot.from_engine([], []), vlm=_StubVlm())

    recorded = json.dumps(run.summary["results"]["device_changes"])
    for name in ("ai-gateway", "nvidia.com/gpu=all", "backend", "dcgm-exporter"):
        assert name in recorded, f"the sandbox record must name {name}: {recorded}"
    assert "ai-vlm" in recorded, "the in-stack VLM pop is named too"


def test_the_prod_render_refuses_before_the_engine_without_the_socket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # prod_shape_env refuses a missing PODMAN_SOCKET (a blank interpolates to a
    # "/" mount); here that refusal must stop the render, not reach compose.
    run = _prod_run(tmp_path, monkeypatch, socket=None)
    calls = _fake_compose(run, _prod_rendered(postgres=_PG_LIMITS))
    with pytest.raises(fc.Refused) as refused:
        run.render(fc.Snapshot.from_engine([], []))
    assert any("PODMAN_SOCKET" in p for p in refused.value.problems), refused.value.problems
    assert calls == []


def test_the_prod_render_records_and_applies_the_limits_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Ruling 162 item 2: limits stay where the machine delegates the controllers
    # and are stripped otherwise, with the verbatim string in the run record.
    # Both branches run through render_prod_shape, not just the helper, because
    # a caller that decided in one place and recorded in another is the bug the
    # helper's docstring warns about -- and because only the render writes the
    # artifact `up` will boot from.
    import copy

    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "cpuset cpu io memory pids\n")
    _fake_compose(run, copy.deepcopy(_prod_rendered(postgres=_PG_LIMITS)))
    run.render(fc.Snapshot.from_engine([], []))
    assert run.summary["limits"] == fc.LIMITS_APPLIED
    landed = json.loads((run.artifacts / "prod-rendered.json").read_text(encoding="utf-8"))
    assert "limits" in landed["services"]["postgres"]["deploy"]["resources"]

    run2 = _prod_run(tmp_path / "b", monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    _fake_compose(run2, copy.deepcopy(_prod_rendered(postgres=_PG_LIMITS)))
    run2.render(fc.Snapshot.from_engine([], []))
    assert run2.summary["limits"] == fc.LIMITS_STRIPPED
    landed2 = json.loads((run2.artifacts / "prod-rendered.json").read_text(encoding="utf-8"))
    assert "limits" not in landed2["services"]["postgres"]["deploy"]["resources"]


def test_the_prod_render_limits_decision_reaches_the_spliced_fake_bodies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The splice happens in the same render, and the fake bodies carry the CI tier's
    # deploy.resources.limits (0.5 CPU / 512M). If the limits decision runs BEFORE the
    # transform, a machine with no cgroup delegation strips the prod render's limits and
    # then the splice re-introduces ones the strip exists to remove -- a rootless
    # container refusing a limit is what the strip's docstring records. The decision must
    # see the render the run BOOTS, i.e. run after the transform.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    spliced = _prod_rendered(postgres=_PG_LIMITS, **{"ai-vlm": _fake_vlm_body()})
    _fake_compose(run, copy.deepcopy(spliced))
    run.render(fc.Snapshot.from_engine([], []))
    assert run.summary["limits"] == fc.LIMITS_STRIPPED
    landed = json.loads((run.artifacts / "prod-rendered.json").read_text(encoding="utf-8"))
    assert "limits" not in (
        landed["services"]["ai-vlm"].get("deploy", {}).get("resources") or {}
    ), "the spliced fake's CI-tier limits must be inside the strip's reach, not outside it"
    # the other direction stays green: where the machine delegates, the spliced limits stay
    run2 = _prod_run(tmp_path / "b", monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "cpuset cpu io memory pids\n")
    _fake_compose(run2, copy.deepcopy(spliced))
    run2.render(fc.Snapshot.from_engine([], []))
    landed2 = json.loads((run2.artifacts / "prod-rendered.json").read_text(encoding="utf-8"))
    assert landed2["services"]["ai-vlm"]["deploy"]["resources"]["limits"] == {
        "cpus": 0.5,
        "memory": "536870912",
    }


def test_the_prod_render_refuses_a_render_that_still_mounts_the_socket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The runtime twin of the static gate: the override DROPS the socket mounts
    # (test_prodshape_override.py proves the committed file does), but the render
    # is what `up` boots, and a socket prod grew after the override was authored
    # is invisible to the gate and visible here. A hit refuses the run naming
    # the service, before anything starts.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    mounting = _prod_rendered(
        backend={
            "image": "b:1",
            "volumes": [
                {"type": "bind", "source": _ENGINE_SOCKET, "target": "/var/run/podman/podman.sock"}
            ],
        },
        # The real shape prod mounts on `alloy`: the SAME ${PODMAN_SOCKET}
        # interpolated into BOTH fields, so the target is the caller's socket path,
        # NOT one of the canonical docker/podman targets. A check that passed no
        # socket path would see only the target and miss alloy outright -- which is
        # the exact drift this re-check exists for.
        alloy={
            "image": "a:1",
            "volumes": [{"type": "bind", "source": _ENGINE_SOCKET, "target": _ENGINE_SOCKET}],
        },
    )
    _fake_compose(run, mounting)
    with pytest.raises(fc.Refused) as refused:
        run.render(fc.Snapshot.from_engine([], []))
    assert any("backend" in p for p in refused.value.problems), refused.value.problems
    assert any("alloy" in p for p in refused.value.problems), refused.value.problems
    assert refused.value.problems == run.summary["results"]["engine_socket"], (
        "the record and the refusal are one measurement; run_check logs the second "
        "and the operator pastes the first, and a reader must be able to match them"
    )
    assert not (run.artifacts / "prod-rendered.json").exists(), (
        "a refused render must not leave the artifact up would boot from"
    )
    # the same render without the mount passes (the re-check is not a blanket ban)
    run2 = _prod_run(tmp_path / "b", monkeypatch, socket=_ENGINE_SOCKET)
    _fake_compose(run2, _prod_rendered(backend={"image": "b:1"}))
    run2.render(fc.Snapshot.from_engine([], []))
    assert (run2.artifacts / "prod-rendered.json").exists()


def test_read_subtree_control_follows_the_caller_s_own_cgroup(tmp_path: Path) -> None:
    # Which cgroup the harness's OWN containers will inherit is what /proc says,
    # not a fixed path: the probe measured /sys/fs/cgroup$(cut -d: -f3 of
    # /proc/self/cgroup)/cgroup.subtree_control. A missing file must read as ""
    # -- the fail-closed direction, because "" makes decide_resource_limits
    # STRIP limits (a container that starts without a limit cannot fail to
    # start over one it was promised).
    proc = tmp_path / "proc"
    (proc / "self").mkdir(parents=True)
    (proc / "self" / "cgroup").write_text(
        "0::/user.slice/user-1000.slice/session-2.scope\n", encoding="utf-8"
    )
    sysfs = tmp_path / "sys"
    cg = sysfs / "user.slice/user-1000.slice/session-2.scope"
    cg.mkdir(parents=True)
    (cg / "cgroup.subtree_control").write_text("cpuset cpu io memory pids\n", encoding="utf-8")
    assert fc.read_subtree_control(proc_dir=proc, sys_dir=sysfs) == "cpuset cpu io memory pids\n"
    assert fc.read_subtree_control(proc_dir=proc, sys_dir=tmp_path / "nothing") == ""
    broken = tmp_path / "broken"
    (broken / "self").mkdir(parents=True)
    (broken / "self" / "cgroup").write_text("garbage\n", encoding="utf-8")
    assert fc.read_subtree_control(proc_dir=broken, sys_dir=sysfs) == ""


def test_the_prod_render_writes_the_boot_file_the_lifecycle_boots_from(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The CI render writes self.compose_file (the deployment up/up-logs/down -v all
    # read via deployment()). render_prod_shape did NOT -- so a --real --prod-shape run
    # came up on PROD_STACK+OVERRIDE and then died at the first deployment() call:
    # _address('compose port'), collect ('logs'/'ps') and teardown ('down -v') all boot
    # compose_file, which was never written. That left the run's containers UP after a
    # red run -- the exact failure UR-135 (teardown with down -v and nothing else) exists
    # to prevent. The prod render must write the same file the CI render does.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "cpu memory\n")
    _fake_compose(run, _prod_rendered(postgres=_PG_LIMITS))
    run.render(fc.Snapshot.from_engine([], []))
    assert run.compose_file.exists(), (
        "deployment()/teardown read compose_file; a prod render that never wrote it "
        "leaves the run's containers up after teardown would run"
    )


def _recording_compose(run: Any, rendered: dict[str, Any]) -> list[Any]:
    """Like _fake_compose but keeps kwargs too: teardown's check=False is part of
    the contract (a failed `down -v` must not mask the postflight)."""
    calls: list[Any] = []

    def compose(files: Any, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((list(files), args, kwargs))
        return subprocess.CompletedProcess(["fake"], 0, stdout=json.dumps(rendered), stderr="")

    run.compose = compose
    return calls


def test_a_prod_shape_run_tears_down_with_down_v_on_its_project_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # UR-135: teardown is `compose -p <run project> ... down -v` and NOTHING else.
    # For the prod shape that only holds if the lifecycle boots the file the prod
    # render wrote -- deployment() supplies the -p and the -f; before the boot file
    # existed this call raised (no such file) mid-teardown, leaving containers up.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    # teardown()'s postflight reads a SECOND snapshot through _run -> the engine
    # binary. _recording_compose fakes the `down -v` only, so without this the
    # postflight snapshot reaches a real `podman ps` (the UR-135 assertion is on
    # `calls`, not on _run, so faking it keeps the contract pinned -- review
    # finding CR-2 on #7037). Empty stdout => empty after-snapshot => the
    # before==after case this test already asserts.
    monkeypatch.setattr(fc.Run, "_run", lambda *_, **__: subprocess.CompletedProcess([], 0, "", ""))
    calls = _recording_compose(run, _prod_rendered(postgres=_PG_LIMITS))
    run.render(fc.Snapshot.from_engine([], []))
    calls.clear()
    changed, left = run.teardown(fc.Snapshot.from_engine([], []))
    assert calls == [([run.compose_file], ("down", "-v"), {"check": False, "timeout": 600})], (
        f"UR-135 allows exactly one teardown call; got {calls}"
    )
    assert changed == [] and left == []


def test_the_prod_boot_file_bakes_no_object_names_so_the_project_decides_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Measured on compose v5.5.1: `config --format json` bakes the project name into
    # every network and volume (`name: runA_security-net`), and a later `-p runB`
    # overrides ONLY the top-level name -- the nested baked names survive and point at
    # runA. A boot file carrying them would make a second run mount, and `down -v`
    # DELETE, the first run's volumes: UR-133 isolation inverted into a cross-run
    # delete. Stripping every baked `name` makes compose re-derive each object from
    # the live -p, so the file cannot point at a run that is not booting it.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    baked = {
        "name": run.project,
        # backend included because every prod render has one (the transform refuses a
        # render without it); this test's subject is the baked object NAMES, not services.
        "services": {"backend": {"image": "backend:test"}, "postgres": {"image": "pg:1"}},
        "networks": {"security-net": {"name": f"{run.project}_security-net", "driver": "bridge"}},
        "volumes": {"postgres_data": {"name": f"{run.project}_postgres_data", "driver": "local"}},
    }
    _fake_compose(run, baked)
    run.render(fc.Snapshot.from_engine([], []))
    boot = json.loads(run.compose_file.read_text(encoding="utf-8"))
    assert "name" not in boot, "the top-level name must come from -p at boot"
    assert all("name" not in net for net in boot["networks"].values()), boot["networks"]
    assert all("name" not in vol for vol in boot["volumes"].values()), boot["volumes"]
    # the artifact an operator reads keeps the render as compose produced it
    landed = json.loads((run.artifacts / "prod-rendered.json").read_text(encoding="utf-8"))
    assert landed["volumes"]["postgres_data"]["name"] == f"{run.project}_postgres_data"


def test_the_boot_file_strips_baked_names_from_every_project_named_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The section list is not decoration: compose names `configs` and `secrets` after the
    # PROJECT exactly like networks and volumes (measured on v5.5.1 -- render under
    # `-p proja`, reboot the baked document under `-p projb`, and `configs.myconf` still
    # reads `proja_myconf`). This test failed against the two-section loop it replaced:
    # networks and volumes came back clean while configs kept the other run's name.
    # docker-compose.prod.yml declares neither today, but the same file documents enabling
    # Docker secrets (docker-compose.prod.yml:68-75, :1692-1720), and the CI drift guard
    # cannot catch this -- it compares prod to prod+override, never the boot file.
    # The four names are spelled HERE on purpose: reading fc.PROJECT_NAME_SECTIONS back
    # would make this test shrink in lockstep with the constant and stay green.
    sections = ("networks", "volumes", "configs", "secrets")
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    baked = {
        "name": run.project,
        "services": {"backend": {"image": "backend:test"}},
        "networks": {"security-net": {"name": f"{run.project}_security-net", "driver": "bridge"}},
        "volumes": {"postgres_data": {"name": f"{run.project}_postgres_data", "driver": "local"}},
        "configs": {"alerts.yml": {"name": f"{run.project}_alerts.yml", "file": "./alerts.yml"}},
        "secrets": {"pg_pass": {"name": f"{run.project}_pg_pass", "file": "./pg_pass"}},
    }
    _fake_compose(run, baked)
    run.render(fc.Snapshot.from_engine([], []))
    boot = json.loads(run.compose_file.read_text(encoding="utf-8"))
    for section in sections:
        entries = boot.get(section) or {}
        assert entries, f"{section} vanished from the boot file"
        leftover = {k: e["name"] for k, e in entries.items() if "name" in e}
        assert not leftover, f"{section} still carries another run's baked names: {leftover}"
    # behaviour checked first (it fails with the leftover names, not with a missing symbol)
    assert sections == fc.PROJECT_NAME_SECTIONS, (
        f"compose names objects in {sections}, the strip list is {fc.PROJECT_NAME_SECTIONS}"
    )


def test_the_test_tier_names_project_scoped_objects_in_every_named_section(
    base: dict[str, Any],
) -> None:
    # The other half of the same constant. as_test_deployment PREFIXES names so one run's
    # objects cannot be confused with another's; if the prefix list and the strip list ever
    # disagree, a section is named by the test tier and left baked by the prod tier. The
    # sections are spelled HERE, not read back from the constant under test.
    doc = copy.deepcopy(base)
    doc["volumes"] = {"vol": {}}
    doc["configs"] = {"conf": {}}
    doc["secrets"] = {"sec": {}}
    got = fc.as_test_deployment(doc, project=PROJECT, run_dir=RUN_DIR)
    for section in ("networks", "volumes", "configs", "secrets"):
        names = {k: e.get("name") for k, e in got[section].items()}
        assert names == {k: f"{PROJECT}_{k}" for k in names}, (
            f"{section} not prefixed by the project: {names}"
        )


# --------------------------------------------------- O2.5 Step 2: the prod-shape transforms ----
def _prod_shape_doc() -> dict[str, Any]:
    """A prod-shaped render, as compose would produce it: the backend pointing at the
    in-stack ai-vlm, that ai-vlm present with its CDI devices, no orchestrator flag."""
    return {
        "name": "hsi-check-x",
        "services": {
            "backend": {
                "image": "backend:test",
                "environment": {"AI_VLM_URL": "http://ai-vlm:8098"},
                "depends_on": {"ai-gateway": {"condition": "service_healthy"}},
            },
            "ai-vlm": {"image": "vlm:test", "devices": ["nvidia.com/gpu=0"]},
            "ai-gateway": {"image": "gw:test", "devices": ["nvidia.com/gpu=all"]},
            "postgres": {"image": "pg:1"},
        },
    }


def test_the_prod_shape_deployment_turns_the_orchestrator_off() -> None:
    # UR-134's first clause, and the blocker the fresh-context review found: the CI tier
    # gets this from as_test_deployment (:469), but the prod-shape path does NOT go through
    # that function, so nothing set it -- and check_isolation runs on EVERY mode (:2502),
    # where an absent flag resolves to backend/core/config.py's default `True` and the run
    # dies at "expected 503 'Container orchestrator not available'". Measured in the
    # composed boot doc: env_file is None and the only ORCHESTRATOR_* key is DOCKER_HOST.
    doc = _prod_shape_doc()
    out = fc.as_prod_shape_deployment(doc, vlm_url=None)
    assert out["services"]["backend"]["environment"]["ORCHESTRATOR_ENABLED"] == "false"
    # must-ignore side: the input document is not mutated (the render artifact an operator
    # reads must stay what compose produced).
    assert "ORCHESTRATOR_ENABLED" not in doc["services"]["backend"]["environment"]


def test_the_prod_shape_run_points_the_backend_at_agent_gpu_and_drops_the_in_stack_vlm() -> None:
    # The package Step 1 words it: "GPU services pointed at agent-gpu's ai-vlm INSTEAD OF
    # CDI". Without this the boot file keeps AI_VLM_URL=http://ai-vlm:8098 (measured) and an
    # in-stack ai-vlm whose top-level devices ask for nvidia.com/gpu=0 -- a second GPU
    # consumer racing agent-gpu's own container on the operator's box, and a deployment
    # that is not the one ruling 127's 12 rows are supposed to witness.
    out = fc.as_prod_shape_deployment(_prod_shape_doc(), vlm_url="http://10.0.0.5:8123")
    backend = out["services"]["backend"]
    assert backend["environment"]["AI_VLM_URL"] == "http://10.0.0.5:8123"
    assert "ai-vlm" not in out["services"], "the in-stack GPU container must not boot on --real"
    # ai-gateway is NOT a VLM and prod's backend does not depend on it (measured), so it
    # stays -- dropping it would be a wider change than the package asks for.
    assert "ai-gateway" in out["services"]


def test_the_prod_shape_run_keeps_the_in_stack_vlm_on_the_fake_tier_shape() -> None:
    # must-ignore side: no vlm_url means no agent-gpu, so the in-stack ai-vlm is the ONLY
    # VLM and must survive, URL and all. A transform that dropped it unconditionally would
    # break every run that is not pointed at agent-gpu.
    out = fc.as_prod_shape_deployment(_prod_shape_doc(), vlm_url=None)
    assert "ai-vlm" in out["services"]
    assert out["services"]["backend"]["environment"]["AI_VLM_URL"] == "http://ai-vlm:8098"


def test_the_prod_shape_transform_drops_only_the_dependency_it_omits() -> None:
    # Two directions, both needed. Deliberate omission: `--real` drops the in-stack ai-vlm,
    # so a depends_on naming it goes with it (as_test_deployment:449 does the same on the
    # CI tier). Accidental omission: a dependency on a service this render never had is
    # drift the transform must NOT paper over, because compose would refuse to start.
    doc = _prod_shape_doc()
    doc["services"]["backend"]["depends_on"]["ai-vlm"] = {"condition": "service_started"}
    out = fc.as_prod_shape_deployment(doc, vlm_url="http://10.0.0.5:8123")
    assert "ai-vlm" not in out["services"]["backend"]["depends_on"]

    doc2 = _prod_shape_doc()
    doc2["services"]["backend"]["depends_on"]["tempo"] = {"condition": "service_started"}
    with pytest.raises(fc.HarnessError, match="tempo"):
        fc.as_prod_shape_deployment(doc2, vlm_url="http://10.0.0.5:8123")


# --------------------------------------------------- ruling 256: the sandbox run keeps no GPU
# consumer except the VLM (record 6250363327, 2026-10-18). Attempt 2 (6195692210) died at
# `unresolvable CDI devices nvidia.com/gpu=all` from ai-gateway alone; the ruling splits O2.5 by
# venue instead of routing around it. The tests below name the three transforms and the record's
# duty: every removed or stripped device is NAMED in the run record, not silently absent.


def _ruling256_doc() -> dict[str, Any]:
    """The prod render's GPU-bearing half, as compose produces it (measured 2026-10-18 at
    9aa06a1f0): backend carries a deploy GPU reservation AND depends on ai-gateway healthy;
    ai-gateway carries CDI nvidia.com/gpu=all plus its own deploy reservation and the prod
    gateway env; ai-vlm carries CDI nvidia.com/gpu=0. Every service joins security-net
    (measured at the same head) — the key the splice must restore."""
    return {
        "name": "hsi-check-x",
        "services": {
            "backend": {
                "image": "backend:test",
                "networks": {"security-net": None},
                "environment": {
                    "AI_VLM_URL": "http://ai-vlm:8098",
                    "AI_GATEWAY_URL": "http://ai-gateway:8090",
                    "YOLO26_URL": "http://ai-gateway:8090/yolo26",
                    "ENRICHMENT_LIGHT_URL": "http://ai-gateway:8090/enrich-lt",
                    "USE_AI_GATEWAY": "true",
                },
                "depends_on": {"ai-gateway": {"condition": "service_healthy"}},
                "deploy": {
                    "resources": {
                        "limits": {"cpus": 2, "memory": "10737418240"},
                        "reservations": {
                            "memory": "1073741824",
                            "devices": [{"capabilities": ["gpu"], "driver": "nvidia", "count": 1}],
                        },
                    }
                },
            },
            "ai-gateway": {
                "image": "gw:test",
                "devices": [{"source": "nvidia.com/gpu=all", "target": "nvidia.com/gpu=all"}],
                "environment": {
                    "SERVICE_NAME": "ai-gateway",
                    "GATEWAY_PORT": "8090",
                    "CUDA_VISIBLE_DEVICES": "1",
                },
                "deploy": {
                    "resources": {
                        "limits": {"cpus": 8, "memory": "21474836480"},
                        "reservations": {
                            "memory": "10737418240",
                            "devices": [
                                {"capabilities": ["gpu"], "driver": "nvidia", "device_ids": ["1"]}
                            ],
                        },
                    }
                },
                "networks": {"security-net": None},
            },
            "ai-vlm": {
                "image": "vlm:test",
                "devices": [{"source": "nvidia.com/gpu=0", "target": "nvidia.com/gpu=0"}],
                "networks": {"security-net": None},
            },
            "dcgm-exporter": {
                "image": "dcgm:test",
                "devices": [{"source": "nvidia.com/gpu=all", "target": "nvidia.com/gpu=all"}],
                "networks": {"security-net": None},
            },
        },
    }


def _fake_gateway_body() -> dict[str, Any]:
    """The fake ai-gateway as the CI+fake render produces it (measured): uvicorn command,
    fake env, httpx healthcheck, hsi-fake-ai image, 0.5 CPU / 512M deploy, the CI tier's
    ci-net membership and the CI band's host publishes — and NOTHING device-shaped. The
    transform takes this body from the CI-tier render the same run makes. The shape of
    networks/ports/deploy here is load-bearing: these are the three keys the spliced body
    must NOT keep (the first two are the prod render's, the third belongs to
    decide_resource_limits), and an abbreviated fixture hides exactly the bug that
    omission caused."""
    return {
        "image": "hsi-fake-ai:latest",
        "command": [
            "uvicorn",
            "--factory",
            "backend.ai_contract.fake.app:create_served_app",
            # the fake body as the CI+fake render spells it (in-container bind)
            "--host",
            "0.0.0.0",  # noqa: S104
            "--port",
            "8090",
            "--no-server-header",
        ],
        "environment": {"FAKE_VLM_BUILD_INFO": "b7972-fake-ai"},
        "healthcheck": {
            "test": [
                "CMD",
                "python",
                "-c",
                "import httpx; r = httpx.get('http://localhost:8090/health'); "
                "exit(0 if r.status_code == 200 else 1)",
            ],
            "interval": "5s",
            "timeout": "5s",
            "retries": 20,
            "start_period": "10s",
        },
        "deploy": {"resources": {"limits": {"cpus": 0.5, "memory": "536870912"}}},
        "networks": {"ci-net": None},
        "ports": [
            {
                "mode": "ingress",
                "host_ip": "127.0.0.1",
                "target": 8090,
                "published": "8090",
                "protocol": "tcp",
            }
        ],
    }


def test_the_sandbox_run_swaps_the_real_gateway_for_the_fake_and_names_the_devices() -> None:
    # Ruling 256 item 1: on the sandbox venue the stack keeps no GPU consumer except the VLM,
    # and `ai-gateway` is the fake "as in --real's CI tier (ruling 207)". The prod gateway's
    # CDI stanza is the one this venue can NEVER resolve (attempt 2's death), so a run record
    # that stayed silent about swapping it would describe a deployment the venue never booted.
    out = fc.as_prod_shape_deployment(
        _ruling256_doc(), vlm_url="http://10.0.0.5:8123", fake_gateway=_fake_gateway_body()
    )
    gw = out["services"]["ai-gateway"]
    # the fake body, except the prod render's own networks and publishes: the swap takes the
    # fake's command/env/healthcheck/image and restores the replaced body's network
    # membership and host publishes (the splice's own repair -- a body carrying ci-net or
    # the CI band would be refused at boot, or bind-fatal beside production). This doc
    # fixture's gateway declares no ports, so the restored body drops the key outright --
    # the same absent-means-absent rule the transform implements.
    expect = copy.deepcopy(_fake_gateway_body())
    replaced = _ruling256_doc()["services"]["ai-gateway"]
    expect["networks"] = copy.deepcopy(replaced["networks"])
    if "ports" in replaced:
        expect["ports"] = copy.deepcopy(replaced["ports"])
    else:
        expect.pop("ports", None)
    assert gw == expect, "the prod gateway body must be replaced wholesale"
    assert "devices" not in gw, "the fake carries no CDI device"
    assert "nvidia" not in json.dumps(gw), "no deploy GPU reservation survives the swap"
    backend = out["services"]["backend"]
    assert backend["environment"]["AI_GATEWAY_URL"] == "http://ai-gateway:8090"
    assert backend["environment"]["YOLO26_URL"] == "http://ai-gateway:8090/yolo26"
    assert backend["environment"]["ENRICHMENT_LIGHT_URL"] == "http://ai-gateway:8090/enrich-lt"
    # the fake's own healthcheck answers `service_healthy`, so the backend's dependency holds
    assert backend["depends_on"] == {"ai-gateway": {"condition": "service_healthy"}}
    # the record names what was removed or stripped — a silent swap is the failure mode
    names = json.dumps(out["_device_changes"])
    assert "ai-gateway" in names and "nvidia.com/gpu=all" in names
    assert "deploy" in names, "the gateway's deploy GPU reservation is stripped too, named"


def test_the_sandbox_run_strips_the_backend_gpu_reservation_and_names_it() -> None:
    # Ruling 256 item 1, third clause. The backend's GPU detection (NVML in its own container,
    # backend/services/gpu_detection_service.py) is exactly what the maui run witnesses — on
    # the sandbox venue the reservation asks the engine for a GPU the venue never has, and a
    # boot that died there would be indistinguishable from a harness bug.
    out = fc.as_prod_shape_deployment(
        _ruling256_doc(), vlm_url="http://10.0.0.5:8123", fake_gateway=_fake_gateway_body()
    )
    resources = out["services"]["backend"]["deploy"]["resources"]
    assert "reservations" not in resources or "devices" not in (resources.get("reservations") or {})
    assert "backend" in json.dumps(out["_device_changes"]), "the strip is named in the record"
    assert "nvidia" in json.dumps(out["_device_changes"])


def test_the_sandbox_run_drops_dcgm_exporter_and_names_it() -> None:
    # Ruling 256 item 1, second clause. In the profile-less render dcgm-exporter is already
    # absent (the gpu-rootful profile hides it), so the ordinary path never sees it — the drop
    # is belt for a render that somehow carries it, and the naming is the ruling's own clause.
    out = fc.as_prod_shape_deployment(
        _ruling256_doc(), vlm_url="http://10.0.0.5:8123", fake_gateway=_fake_gateway_body()
    )
    assert "dcgm-exporter" not in out["services"]
    assert "dcgm-exporter" in json.dumps(out["_device_changes"])


def test_the_sandbox_run_leaves_no_gpu_consumer_but_the_vlm_untouched_services() -> None:
    # The whole clause in one node: the only GPU consumer the boot keeps is the one the ruling
    # keeps (ai-vlm, served by agent-gpu OUTSIDE this render — it is popped when vlm_url is
    # set), and every non-GPU service passes through untouched. A transform that "helpfully"
    # rebuilt unrelated services would widen what the run boots beyond the ruling's words.
    doc = _ruling256_doc()
    doc["services"]["postgres"] = {"image": "pg:1"}
    out = fc.as_prod_shape_deployment(
        doc, vlm_url="http://10.0.0.5:8123", fake_gateway=_fake_gateway_body()
    )
    assert "ai-vlm" not in out["services"]  # agent-gpu serves it; the pop is unchanged
    assert out["services"]["postgres"] == {"image": "pg:1"}
    gpu_consumers = [
        name
        for name, svc in out["services"].items()
        if "nvidia" in json.dumps(svc)
        or "gpu"
        in json.dumps(
            (svc.get("deploy") or {}).get("resources", {}).get("reservations", {})
        ).lower()
    ]
    assert gpu_consumers == [], "no GPU consumer may survive the sandbox transform"


def test_the_maui_run_keeps_production_cdi_and_refuses_the_fake_gateway() -> None:
    # Ruling 256 item 2: the maui run keeps production's CDI for ai-gateway, dcgm-exporter and
    # backend, and witnesses that the stack boots with every device resolved. So the sandbox
    # transform must NOT run there — and a caller that passed the fake gateway anyway is asking
    # for the venue's transform on the wrong venue, refused rather than silently applied.
    with pytest.raises(fc.HarnessError, match="fake_gateway"):
        fc.as_prod_shape_deployment(
            _ruling256_doc(), vlm_url=None, fake_gateway=_fake_gateway_body()
        )
    # without vlm_url the in-stack ai-vlm stays (the maui run boots the fake VLM in its place
    # — spliced by the runner, not this function's concern); CDI stanzas all survive here.
    doc = _ruling256_doc()
    out = fc.as_prod_shape_deployment(doc, vlm_url=None)
    assert out["services"]["ai-gateway"]["devices"] == doc["services"]["ai-gateway"]["devices"]
    assert (
        out["services"]["backend"]["deploy"]["resources"]["reservations"]
        == (doc["services"]["backend"]["deploy"]["resources"]["reservations"])
    )
    assert "dcgm-exporter" in out["services"]
    assert out["_device_changes"] == [], "the maui shape strips nothing"


def test_the_maui_run_drops_the_in_stack_vlm_cdi_line_and_names_it() -> None:
    # Ruling 256 item 2, last line: "ai-vlm's own CDI line is the one GPU line neither run
    # boots." The maui run boots the FAKE VLM in ai-vlm's place (item 2's command), so the
    # in-stack ai-vlm's CDI device must go with the service the swap removes — named.
    # The fake VLM REPLACES the in-stack one under the same service name: the backend's
    # prod AI_VLM_URL (http://ai-vlm:8098) keeps working, the CDI device line is gone with
    # the prod body it lived on, and the healthcheck that gates the backend's dependency is
    # the fake's. (Ruling 256 item 2: "ai-vlm's own CDI line is the one GPU line neither
    # run boots" -- booted never, but the service name stays, exactly as the CI tier does.)
    out = fc.as_prod_shape_deployment(_ruling256_doc(), vlm_url=None, fake_vlm=_fake_vlm_body())
    vlm = out["services"]["ai-vlm"]
    assert vlm["image"] == _fake_vlm_body()["image"], "the fake VLM replaces the prod body"
    assert "devices" not in vlm and "nvidia" not in json.dumps(vlm)
    assert "ai-vlm" in json.dumps(out["_device_changes"])
    assert "nvidia.com/gpu=0" in json.dumps(out["_device_changes"])
    gw = out["services"]["ai-gateway"]
    assert gw["devices"], "the maui run keeps production's gateway CDI"
    assert out["services"]["backend"]["deploy"]["resources"]["reservations"]  # and the backend's
    assert "dcgm-exporter" in out["services"]


def test_the_maui_run_points_the_backend_at_the_fake_vlm() -> None:
    # The maui command runs --prod-shape WITHOUT --real, so there is no agent-gpu URL to set —
    # the backend must call the FAKE VLM the way the CI tier does: by service name on the
    # prod network (fake-ai's own AI_VLM_URL is http://ai-vlm:8098).
    out = fc.as_prod_shape_deployment(_ruling256_doc(), vlm_url=None, fake_vlm=_fake_vlm_body())
    assert out["services"]["backend"]["environment"]["AI_VLM_URL"] == "http://ai-vlm:8098"


def _ci_net_leftovers(out: dict[str, Any]) -> list[str]:
    """Every service whose body still carries the CI tier's network or host band, measured
    after a transform. The fake bodies arrive with `ci-net` and the CI-band publishes because
    they are the CI+fake render's bodies verbatim; the wholesale swap replaces the prod body
    INCLUDING its security-net membership and 23xxx publishes, so the boot document would
    name a network the prod render never defines (compose refuses it: the measured solo-render
    failure `refers to undefined network ci-net`) and re-publish prod's OWN host ports beside
    production on maui (the live stack holds 127.0.0.1:8090/8098)."""
    return [
        name
        for name, svc in out["services"].items()
        if "ci-net" in (svc.get("networks") or {})
        or any(str(p.get("published")) in ("8090", "8098") for p in (svc.get("ports") or []))
    ]


def test_the_sandbox_run_leaves_no_ci_net_or_ci_band_in_the_boot_document() -> None:
    # The compose oracle caught what the abbreviated fixtures hid: a wholesale body swap
    # replaces the prod body's security-net membership and 23xxx publishes with the fake
    # body's ci-net and CI-band publishes. `docker compose config` on that boot document is
    # refused ("refers to undefined network ci-net" — the same measured failure the solo
    # fake render dies at), and on maui the 8090/8098 binds are the LIVE stack's own.
    # The docstring's own sentence is the contract: "The prod render's network membership
    # stays the prod render's (security-net): the transform keeps it."
    out = fc.as_prod_shape_deployment(
        _ruling256_doc(), vlm_url="http://10.0.0.5:8123", fake_gateway=_fake_gateway_body()
    )
    assert _ci_net_leftovers(out) == []
    for name in ("ai-gateway", "backend"):
        assert out["services"][name]["networks"] == {"security-net": None}, name


def test_the_maui_run_leaves_no_ci_net_or_ci_band_in_the_boot_document() -> None:
    # Same contract on the maui venue: the swapped-in fake VLM must join the prod network
    # the replaced service had, and publish nothing on the CI band (the live ai-vlm holds
    # 127.0.0.1:8098 beside production — a bind attempt on it dies before any VLM read).
    out = fc.as_prod_shape_deployment(_ruling256_doc(), vlm_url=None, fake_vlm=_fake_vlm_body())
    assert _ci_net_leftovers(out) == []
    assert out["services"]["ai-vlm"]["networks"] == {"security-net": None}


def _fake_vlm_body() -> dict[str, Any]:
    """The fake ai-vlm as the CI+fake render produces it (measured): same image as the fake
    gateway, port 8098, fake env, httpx healthcheck, ci-net membership and the CI band's
    host publish — the same three keys the gateway fixture carries, for the same reason."""
    return {
        "image": "hsi-fake-ai:latest",
        "command": [
            "uvicorn",
            "--factory",
            "backend.ai_contract.fake.app:create_served_app",
            # the fake body as the CI+fake render spells it (in-container bind)
            "--host",
            "0.0.0.0",  # noqa: S104
            "--port",
            "8098",
            "--no-server-header",
        ],
        "environment": {"FAKE_VLM_BUILD_INFO": "b7972-fake-ai"},
        "healthcheck": {
            "test": [
                "CMD",
                "python",
                "-c",
                "import httpx; r = httpx.get('http://localhost:8098/health'); "
                "exit(0 if r.status_code == 200 else 1)",
            ],
            "interval": "5s",
            "timeout": "5s",
            "retries": 20,
            "start_period": "10s",
        },
        "deploy": {"resources": {"limits": {"cpus": 0.5, "memory": "536870912"}}},
        "networks": {"ci-net": None},
        "ports": [
            {
                "mode": "ingress",
                "host_ip": "127.0.0.1",
                "target": 8098,
                "published": "8098",
                "protocol": "tcp",
            }
        ],
    }


# ---------------------------------------------------------------------------
# O2.5 / UR-140 — the operator's first prod-shape run (#7037 `6166020894`) died at
# the prod shape's BUILD path and the harness reported it as a VLM problem. The
# run's own words: "21 seconds, zero services booted — and the harness reports it
# as 'backend is not running', because `up()` swallows compose's own output into
# that reason. The VLM was fine (it was serving; I had just read `/props`)."
#
# Mechanism, in `Run.up`: `deployment("up", …)` raises a HarnessError whose
# message IS compose's tail ("… denied …", "booting buildkit", "mkdir
# /sys/fs/cgroup/docker/buildx: permission denied"), and the `except HarnessError`
# arm calls `check_vlm_reach` and lets ITS message win, discarding the one it
# caught. A reader then goes looking for a broken model server while the actual
# failure is five image-less services the engine cannot build.
#
# Each pin below has a way to fail: the first goes red if compose's tail is
# swallowed again, the second if the VLM reason is dropped in the other direction.
# ---------------------------------------------------------------------------

# A trimmed copy of the operator's `up-replay.out` (sha 6f0cd7b1…): the walls, in
# the words compose actually printed.
_COMPOSE_BUILD_FAILURE = (
    " Image nemotron-v3-home-security-intelligence-grafana:latest denied: "
    "requested access to the resource is denied\n"
    "#2 [internal] booting buildkit\n"
    "#2 starting container buildx_buildkit_default\n"
    "#2 ERROR: cgroup configuration: mkdir /sys/fs/cgroup/docker/buildx: "
    "permission denied: OCI permission denied"
)


class _StubVlm:
    url = "http://host.docker.internal:18100"


def _boot_failed_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> fc.HarnessError:
    """A run whose `up` dies the way the operator's did — compose fails, VLM
    serving — returning the error the harness raised."""

    def deployment(*args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise fc.HarnessError(f"docker compose … up … exited 1: {_COMPOSE_BUILD_FAILURE}")

    monkeypatch.setattr(fc.Run, "deployment", deployment)
    monkeypatch.setattr(fc.Run, "check_vlm_reach", lambda *_: None)
    run = fc.Run(engine="docker", root=tmp_path / "runs", image_tag="test", mode="real")
    with pytest.raises(fc.HarnessError) as raised:
        run.up(vlm=_StubVlm())
    return raised.value


def test_a_failed_up_with_a_reachable_vlm_reraises_composes_error_verbatim(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The control that says WHERE the defect is. Measured at the first attempt,
    # before any implementation: this one PASSES on main. When the VLM answers,
    # `check_vlm_reach` returns and `up`'s bare `raise` re-raises compose's own
    # HarnessError untouched — so the swallow is NOT here. It is in the other
    # branch, where the VLM check also fails (the operator's situation: nothing
    # booted, so `exec -T backend` fails too) and the reach message REPLACES the
    # compose one. Pinned because a "fix" that routed every failure through a
    # synthesized reach message would break this and read a healthy boot failure
    # as a VLM outage.
    message = str(_boot_failed_run(monkeypatch, tmp_path))
    for needle in ("buildx_buildkit_default", "permission denied", "denied"):
        assert needle in message, f"compose's reason {needle!r} was lost: {message[:400]}"
    # and a build failure must not be MISLABELED as a reachability one
    assert "cannot reach the VLM" not in message, (
        f"a build failure was reported as a VLM reachability failure: {message[:400]}"
    )


def test_a_failed_up_chains_composes_failure_under_the_raised_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = fc.Run(engine="docker", root=tmp_path / "runs", image_tag="test", mode="real")

    def deployment(*args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise fc.HarnessError(f"docker compose … up … exited 1: {_COMPOSE_BUILD_FAILURE}")

    monkeypatch.setattr(fc.Run, "deployment", deployment)
    monkeypatch.setattr(fc.Run, "check_vlm_reach", lambda *_: None)
    with pytest.raises(fc.HarnessError) as raised:
        run.up(vlm=_StubVlm())
    assert isinstance(raised.value.__cause__, fc.HarnessError), (
        "the raised error is not chained to compose's own failure"
    )


def test_a_failed_up_with_the_vlm_also_unreachable_names_both_reasons(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The arm the except clause was written for must keep working: an unreachable
    # VLM really is the likely reason, and dropping it would be the mirror image
    # of the bug above. Both reasons, neither alone.
    def unreachable(self: Any, url: str) -> None:
        raise fc.HarnessError(f"the backend cannot reach the VLM at {url}, or is not running")

    monkeypatch.setattr(fc.Run, "check_vlm_reach", unreachable)

    def deployment(*args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise fc.HarnessError(f"docker compose … up … exited 1: {_COMPOSE_BUILD_FAILURE}")

    monkeypatch.setattr(fc.Run, "deployment", deployment)
    run = fc.Run(engine="docker", root=tmp_path / "runs", image_tag="test", mode="real")
    with pytest.raises(fc.HarnessError) as raised:
        run.up(vlm=_StubVlm())
    message = str(raised.value)
    assert "cannot reach the VLM" in message, f"the VLM reason was dropped: {message[:400]}"
    assert "buildx_buildkit_default" in message, f"compose's reason was swallowed: {message[:400]}"


def test_up_boots_with_no_build_and_never_rebuilds_at_up(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ruling 274 as amended (record IC_kwDOQs9zJM8AAAABdusUHA): on the prod-shape
    modes the harness boots with `up --no-build`, so `up` never builds there.
    `docker-compose.fake-ai.yml:34` sets `pull_policy: build`, which makes a plain
    `up` rebuild `hsi-fake-ai` through BuildKit even when the prebuild has just
    built it — and that rebuild's RUN step needs the cgroup delegation this venue's
    rootless engine cannot grant (attempt 4, operator report 6280195057). The
    prebuild builds everything with DOCKER_BUILDKIT=0 precisely so `up` builds
    nothing; the flag makes that true."""

    capture: list[tuple[str, ...]] = []

    def deployment(self: Any, *args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        capture.append(args)
        if args[:2] == ("up", "-d"):
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:2] == ("port", "backend"):
            return subprocess.CompletedProcess(args, 0, "127.0.0.1:18000\n", "")
        if args[:2] == ("port", "frontend"):
            return subprocess.CompletedProcess(args, 0, "127.0.0.1:18080\n", "")
        raise AssertionError(f"unexpected deployment call: {args}")

    monkeypatch.setattr(fc.Run, "deployment", deployment)
    monkeypatch.setattr(fc.Run, "check_vlm_reach", lambda *_: None)
    run = fc.Run(
        engine="docker", root=tmp_path / "runs", image_tag="test", mode="real", prod_shape=True
    )
    run.up(vlm=_StubVlm())
    assert run.summary["urls"] == {"api": "http://127.0.0.1:18000", "ui": "http://127.0.0.1:18080"}
    # The pin itself: the boot argv carries --no-build exactly when the prebuild ran
    # (the prod-shape modes; amendment item 1). Position is free - it is a flag, not
    # an operand - so this is a membership assert, not a shape.
    up_calls = [c for c in capture if c[0] == "up"]
    assert up_calls, f"no `up` call captured: {capture}"
    for argv in up_calls:
        assert "--no-build" in argv, f"the boot argv lacks --no-build: {argv}"


def test_up_without_a_prebuild_boots_plain(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ruling 274 as amended: fake mode's `up` is unchanged. Fake mode never ran a
    prebuild (`prebuild_images` lives only on the prod-shape render), and nothing in
    CI's fake-AI runs builds `hsi-fake-ai` before `up` — so with `--no-build` on
    every run those runs failed with `No such image` and the four fake shards went
    red (measured on #7298). The flag rides along exactly when the prebuild ran."""

    capture: list[tuple[str, ...]] = []

    def deployment(self: Any, *args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        capture.append(args)
        if args[:2] == ("up", "-d"):
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:2] == ("port", "backend"):
            return subprocess.CompletedProcess(args, 0, "127.0.0.1:18000\n", "")
        if args[:2] == ("port", "frontend"):
            return subprocess.CompletedProcess(args, 0, "127.0.0.1:18080\n", "")
        if args[:2] == ("port", "ai-vlm"):
            return subprocess.CompletedProcess(args, 0, "127.0.0.1:18098\n", "")
        raise AssertionError(f"unexpected deployment call: {args}")

    monkeypatch.setattr(fc.Run, "deployment", deployment)
    run = fc.Run(engine="docker", root=tmp_path / "runs", image_tag="test", mode="fake")
    run.up(vlm=None)
    assert run.summary["urls"] == {"api": "http://127.0.0.1:18000", "ui": "http://127.0.0.1:18080"}
    up_calls = [c for c in capture if c[0] == "up"]
    assert up_calls, f"no `up` call captured: {capture}"
    for argv in up_calls:
        assert "--no-build" not in argv, f"fake mode's boot argv must not carry --no-build: {argv}"
        assert "--wait" in argv, f"the boot argv lost --wait: {argv}"


# ---------------------------------------------------------------------------
# O2.5 / UR-140 slice 2a — the names `up` builds under.
#
# The operator's run (#7037 `6166020894`) died because six prod services carry
# `build:` and no image existed locally, so `up --wait` started building during
# the boot: it PULLED grafana's host-local name first (measured: compose prints
# `Image <name> Pulling` for a build+image service whose image is absent, then
# `denied: requested access to the resource is denied`), and for the five
# services with no `image:` at all it started a buildx builder container, which
# is where the cgroup wall bit. A pre-build can only prevent that if it builds
# under the EXACT names compose will look for, so those names are derived here,
# from the same boot document `up` boots, and not from a second source.
#
# Measured on compose v5.5.1 (both branches, with a real render):
#   * a service with `image:` is looked up under that name — grafana's is
#     `nemotron-v3-home-security-intelligence-grafana:latest`, hard-coded in
#     docker-compose.prod.yml, host-local by construction: there is nowhere to
#     pull it from, so `up`'s pull is the failure;
#   * a service with `build:` and no `image:` gets `<project>-<service>:latest`.
#
# Each pin fails if the derivation drifts from what compose does: a pre-build
# under any other tag leaves the image "absent" in compose's eyes, `up` builds
# it anyway, and the wall is back with an extra step in front of it.
# ---------------------------------------------------------------------------


def test_the_derivation_names_a_build_service_with_no_image_under_the_project(
    tmp_path: Path,
) -> None:
    boot = {
        "services": {
            "backend": {"build": {"context": "/repo", "dockerfile": "backend/Dockerfile"}},
            "redis": {"image": "redis:7.4-alpine3.21"},
        }
    }
    assert fc.build_images(boot, project="hsi-check-x1") == {
        "backend": "hsi-check-x1-backend:latest"
    }


def test_the_derivation_keeps_a_declared_image_name_verbatim(tmp_path: Path) -> None:
    # grafana's real case: prod sets the name, so compose looks for THAT name and
    # a pre-build tagged anything else is invisible to it.
    boot = {
        "services": {
            "grafana": {
                "image": "nemotron-v3-home-security-intelligence-grafana:latest",
                "build": {"context": "/repo/monitoring/grafana"},
            }
        }
    }
    assert fc.build_images(boot, project="hsi-check-x1") == {
        "grafana": "nemotron-v3-home-security-intelligence-grafana:latest"
    }


def test_the_derivation_ignores_a_service_that_boots_from_a_registry_image(
    tmp_path: Path,
) -> None:
    # A pulled service is not something a pre-build should attempt: building it
    # would replace what the tier witnesses with a locally-built stand-in.
    boot = {
        "services": {
            "postgres": {"image": "postgres:17.3-alpine"},
            "tempo": {"image": "grafana/tempo:2.9.0"},
        }
    }
    assert fc.build_images(boot, project="hsi-check-x1") == {}


# ---------------------------------------------------------------------------
# O2.5 / UR-140 slice 2b — the pre-build leg.
#
# The routing sent the runner revision to this lane (#7114 `6166927526`:
# "pre-build or pre-pull the five images, or drop them from the boot set, and
# name grafana's image; it's your call as the lane that writes the runner").
# Measured here: pre-pull is impossible (five services have no registry name at
# all, and grafana's is host-local by construction) and dropping services would
# change what the tier witnesses (9 of ruling 127's 12 rows ARE Grafana embeds;
# backend depends on ai-gateway with USE_AI_GATEWAY=true). So: pre-build, before
# `up` — because building INSIDE the boot is the failure.
#
# Two walls the leg routes around, both reproduced in this sandbox:
#   * buildkit is the DEFAULT builder, and against an engine socket the CLI
#     bootstraps a `docker-container` builder — `creating container
#     buildx_buildkit_default` — needing a startable container (the operator's
#     missing catatonit) and cgroup delegation (absent there). DOCKER_BUILDKIT=0
#     is honoured by `compose build` (measured, both branches: `Sending build
#     context to Docker daemon`, then the daemon's native `STEP 1/2`).
#   * `up` PULLS a build+image service whose image is absent, so grafana's
#     host-local name answers `denied`. With the image present it prints neither
#     Pulling nor Building and goes to `Container Creating` (measured, `up
#     --dry-run`, both branches). Hence skip-if-present, using `up`'s own
#     `image inspect` lookup (measured over the compat API: 0 present, 1 absent).
#
# The fake dispatches on the compose VERB (the token after the last `-f`), never
# on a substring of the argv: pytest's tmp_path embeds the test name, so a path
# here can contain the word "build" and a substring filter would match the `-f`
# argument instead of the subcommand.
# ---------------------------------------------------------------------------


# What each SUPPORTED engine actually prints, and what it returns, when a name is not in the engine
# vs when its daemon is DOWN. Measured in this sandbox against docker 27.x and podman 5.7.0:
#     docker  absent  rc=1    "Error response from daemon: No such image: <name>"
#     docker  down    rc=1    "failed to connect to the docker API at unix:///…; check if the path…"
#     podman  absent  rc=125  "Error: <name>: image not known"
#     podman  down    rc=125  "Cannot connect to Podman. Please verify your connection…"
# Both DOWN answers share their engine's absent exit code, so the rc cannot carry the distinction
# and only the words can -- which is why the cleanup's absence test is a marker, not a code. One
# source feeds both the shared fake below (fidelity: an honest absence must carry the daemon's
# words or a tightening of the rule silently reclassifies every real absence as unknown) and the
# engine-down pins further down. `choices=("docker", "podman")` in `main()` closes the engine set.
_ABSENT_STDERR = {
    "docker": "Error response from daemon: No such image: {name}",
    "podman": "Error: {name}: image not known",
}
_DOWN_STDERR = {
    "docker": (
        "failed to connect to the docker API at unix:///run/user/1000/podman/podman.sock; "
        "check if the path is correct and if the daemon is running"
    ),
    "podman": "Cannot connect to Podman. Please verify your connection to the Linux system",
}
# The exit code each engine returns for BOTH answers above -- the reason rc is no discriminator.
_LOOKUP_RC = {"docker": 1, "podman": 125}


def _absent_stderr(engine: str, name: str) -> str:
    """What `engine` says, verbatim, when `name` is genuinely not in it."""
    return _ABSENT_STDERR[engine].format(name=name)


_PREBUILD_DOC = {
    "services": {
        # build, no image -> compose derives <project>-backend:latest
        "backend": {"build": {"context": "/repo", "dockerfile": "backend/Dockerfile"}},
        # build AND a host-local image -> that name verbatim (grafana's case)
        "grafana": {
            "image": "nemotron-v3-home-security-intelligence-grafana:latest",
            "build": {"context": "/repo/monitoring/grafana"},
        },
        # registry image, no build -> nobody's build, and must not be pulled
        "redis": {"image": "redis:7.4-alpine3.21"},
    }
}


def _last(argv: list[str], token: str) -> int:
    """Index of the LAST occurrence of `token` (a list has no rindex)."""
    return max(i for i, part in enumerate(argv) if part == token)


_GRAFANA = "nemotron-v3-home-security-intelligence-grafana:latest"


def _engine_answers(
    run: Any,
    rendered: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    *,
    present: frozenset[str] = frozenset(),
    build_rc: int = 0,
    build_tail: str = "",
    rm_rc: int = 0,
) -> list[tuple[list[str], dict[str, Any]]]:
    """Answer this run's engine at the `_run` seam and record every argv + env.

    `_run` is the one boundary every engine call crosses: the compose argv, the
    bare `image inspect`, and the env each call carries all arrive here — which
    the file's `_fake_compose` cannot show, because it drops kwargs and env is
    exactly where the builder switch lives.
    """

    class _Calls(list):
        """The argv record, plus the engine's image state as it evolved.

        `have` starts as `present` and a SUCCESSFUL build adds the namespaced tags
        it built, because that is what a build does: it leaves `<project>-
        <service>:latest` in the engine. A static `present` set could not show both
        facts the cleanup is judged on — that the build put images there, and that a
        name the engine never got must not be `image rm`'d.
        """

        have: set[str]

    calls = _Calls()
    calls.have = set(present)

    def compose_verb(command: list[str]) -> str | None:
        # The subcommand follows the LAST -f's value: the argv is
        # `<engine> compose --env-file E -p P -f F [-f F …] <verb> …`, so the
        # render may carry two files and the verb still sits at +2.
        if "compose" not in command[:2] or "-f" not in command:
            return None
        after = command[_last(command, "-f") + 2 :]
        return after[0] if after else None

    def fake(self: Any, command: list[Any], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        argv = [str(part) for part in command]
        calls.append((argv, kwargs))
        verb = compose_verb(argv)
        if argv[1:3] == ["image", "inspect"]:
            if argv[3] in calls.have:
                return subprocess.CompletedProcess(argv, 0, "", "")
            # An honest "not in the engine" carries the daemon's WORDS, not just a nonzero rc:
            # the cleanup reads absence as a positive claim (see `_ABSENT_STDERR` above), so a
            # fake that answers absence with empty stderr would make every real absence read
            # as unknown and turn the guard green by never exercising it.
            return subprocess.CompletedProcess(
                argv, _LOOKUP_RC[self.engine], "", _absent_stderr(self.engine, argv[3])
            )
        if argv[1:3] == ["image", "rm"]:
            if rm_rc == 0:
                calls.have.discard(argv[3])
            return subprocess.CompletedProcess(
                argv, rm_rc, "", "image is used by container" if rm_rc else ""
            )
        if verb == "config":
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(rendered), stderr="")

        def build_names(argv: list[str]) -> list[str]:
            # `--no-cache` rides along under prod_shape (the venue fixes' fresh-build
            # clause), after the names: the slice stops at the flag.
            return [part for part in argv[_last(argv, "-f") + 3 :] if part != "--no-cache"]

        if verb == "build":
            if build_rc == 0:
                built = build_names(argv)
                for name in built:
                    service = (rendered.get("services") or {}).get(name) or {}
                    if not service.get("image"):
                        calls.have.add(f"{run.project}-{name}:latest")
            return subprocess.CompletedProcess(argv, build_rc, "", build_tail)
        if verb == "up":
            raise AssertionError(f"`up` ran during a pre-build test: {argv}")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(fc.Run, "_run", fake)
    return calls


def _image_rms(calls: Any) -> list[str]:
    """The image names this run asked the engine to remove, in call order.

    Matched on the argv position, like every other matcher here: a bare engine
    call has no `-f`, so `_verb_calls` (compose-only by design) cannot see it.
    """
    return [argv[3] for argv, _ in calls if argv[1:3] == ["image", "rm"]]


def _is_verb(argv: list[str], verb: str) -> bool:
    """Is this a `<engine> compose … -f FILE <verb> …` invocation?

    Matched on the subcommand position, not on a substring: pytest's tmp_path
    embeds the test name, so a `-f` path here can contain the word "build".
    """
    if "compose" not in argv[:2] or "-f" not in argv:
        return False
    after = argv[_last(argv, "-f") + 2 :]
    return bool(after) and after[0] == verb


def _verb_calls(calls: Any, verb: str) -> list[list[str]]:
    """The recorded compose argvs whose subcommand is `verb`."""
    return [argv for argv, _ in calls if _is_verb(argv, verb)]


def _the_build(calls: Any) -> tuple[list[str], dict[str, Any]]:
    """The one and only `build` call, with the env it carried.

    One call is itself a pin: the buildable services go to a single
    `compose build` naming them, not one call per service, so the tier pays for
    one builder start and the failure message can name every service at once.
    """
    builds = [(argv, env) for argv, env in calls if _is_verb(argv, "build")]
    assert len(builds) == 1, [argv for argv, _ in builds]
    return builds[0]


def test_the_prod_render_prebuilds_the_build_images_before_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Nothing boots in this sandbox (podman cannot mount here at all), so the leg
    # is pinned at the seam it acts through: the argv it issues and the record it
    # leaves. The `up` guard in the fake carries the ordering.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    calls = _engine_answers(run, _PREBUILD_DOC, monkeypatch)

    run.render(fc.Snapshot.from_engine([], []))

    builds = _verb_calls(calls, "build")
    assert len(builds) == 1, builds
    argv = builds[0]
    named = [p for p in argv[_last(argv, "-f") + 3 :] if p != "--no-cache"]
    # Both build-bearing services by NAME; redis is nobody's build. --no-cache
    # rides exactly under prod-shape (asserted on the raw slice), and CI's argv
    # drops it (its own pin).
    assert sorted(named) == ["backend", "grafana"], argv
    assert "--no-cache" in argv[_last(argv, "-f") + 3 :], argv
    assert run.summary["prebuild"] == {
        "built": ["backend", "grafana"],
        "present": [],
        "to_build": ["backend", "grafana"],
        "exit": 0,
    }


def test_the_prebuild_skips_an_image_the_engine_already_has(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Not an optimisation: grafana's name is host-local and NOT namespaced by the
    # project, so an image that is present IS the image production boots.
    # Rebuilding it would make the tier witness something production does not
    # run — and spend hours doing it.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    calls = _engine_answers(run, _PREBUILD_DOC, monkeypatch, present=frozenset({_GRAFANA}))

    run.render(fc.Snapshot.from_engine([], []))

    (argv, _env) = _the_build(calls)
    assert [p for p in argv[_last(argv, "-f") + 3 :] if p != "--no-cache"] == ["backend"], argv
    assert "--no-cache" in argv[_last(argv, "-f") + 3 :], argv
    assert run.summary["prebuild"] == {
        "built": ["backend"],
        "present": ["grafana"],
        "to_build": ["backend"],
        "exit": 0,
    }
    # the lookup is per image, through the engine, not a path on disk
    inspected = {argv[3] for argv, _ in calls if argv[1:3] == ["image", "inspect"]}
    assert inspected == {_GRAFANA, f"{run.project}-backend:latest"}, inspected


def test_the_prebuild_routes_the_builder_away_from_a_builder_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The wall is the builder, not the build. By default the CLI bootstraps
    # `buildx_buildkit_default` as a CONTAINER (reproduced here: `exec:
    # "catatonit": executable file not found in $PATH`); DOCKER_BUILDKIT=0 makes
    # the daemon's own builder answer. DOCKER_HOST must survive, or the build
    # talks to a different engine than the one `up` boots.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    monkeypatch.setenv("DOCKER_HOST", "unix:///run/user/1000/podman/podman.sock")
    calls = _engine_answers(run, _PREBUILD_DOC, monkeypatch)

    run.render(fc.Snapshot.from_engine([], []))

    (_argv, kwargs) = _the_build(calls)
    env = kwargs["env"]
    assert env["DOCKER_BUILDKIT"] == "0", env
    assert env["DOCKER_HOST"] == "unix:///run/user/1000/podman/podman.sock", (
        "the build must reach the engine `up` boots, so DOCKER_HOST cannot be dropped"
    )


def test_a_failing_prebuild_names_the_services_and_never_boots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Slice 1 made a dead boot quotable; this stops the run one step EARLIER, and
    # must not become the next silent middle step: which services, the engine's
    # own words, and no `up` afterwards.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    calls = _engine_answers(
        run,
        _PREBUILD_DOC,
        monkeypatch,
        build_rc=1,
        build_tail="cgroup configuration: mkdir /sys/fs/cgroup/docker/buildx: permission denied",
    )

    with pytest.raises(fc.HarnessError) as raised:
        run.render(fc.Snapshot.from_engine([], []))
    message = str(raised.value)
    assert "backend" in message and "grafana" in message, message
    assert "buildx" in message, f"the engine's own words were dropped: {message[:300]}"
    assert _verb_calls(calls, "up") == [], "a failed pre-build must not boot the stack"
    # and the stream it died with is kept for the operator to read
    assert "buildx" in (run.artifacts / "prebuild.txt").read_text(encoding="utf-8")


def test_a_failed_prebuild_records_nothing_as_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The record is read as a claim about the engine, not about intent. Reporting
    # the images as built when the build exited nonzero is the same class of defect
    # slice 1 fixed: a run that died leaving a summary that says otherwise. `built`
    # is filled from the build's exit, so `to_build` holds the intent and `built`
    # stays empty, and the artifact says `exit: 1` in its own words.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    _engine_answers(
        run,
        _PREBUILD_DOC,
        monkeypatch,
        build_rc=1,
        build_tail="STEP 1/2: Error: building at STEP ...: /dev/fuse: Operation not permitted",
    )

    with pytest.raises(fc.HarnessError):
        run.render(fc.Snapshot.from_engine([], []))

    prebuild = run.summary["prebuild"]
    assert prebuild["built"] == [], prebuild
    assert prebuild["to_build"] == ["backend", "grafana"], prebuild
    assert prebuild["exit"] == 1, prebuild
    artifact = (run.artifacts / "prebuild.txt").read_text(encoding="utf-8")
    assert "exit: 1" in artifact, artifact[:200]


def test_a_render_with_no_build_services_builds_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The CI tier's stack has no `build:` blocks at all (measured: 0 in
    # docker-compose.ci.yml). A tier with nothing to build must not spend an
    # `image inspect` per service, and must not claim a prebuild it did not do.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    calls = _engine_answers(run, _prod_rendered(postgres=_PG_LIMITS), monkeypatch)

    run.render(fc.Snapshot.from_engine([], []))

    assert _verb_calls(calls, "build") == []
    assert [a for a, _ in calls if a[1:3] == ["image", "inspect"]] == []
    # No `exit` key at all: the record distinguishes "nothing was buildable" from
    # "a build ran and returned 0", which the CI tier's stack can never be.
    assert run.summary["prebuild"] == {"built": [], "present": [], "to_build": []}


# ---------------------------------------------------------------------------
# O2.5 follow-up: the images a prod-shape run LEAVES BEHIND.
#
# The pre-build names every image-less build service `<project>-<service>:latest`
# and `self.project` carries a per-run random token, so those tags differ on every
# run — a re-run cannot reuse a prior build, and nothing removes the old ones.
# `down -v` (UR-135, pinned above to exactly that one compose call) takes
# containers and volumes; the postflight `Snapshot` tracks containers and volumes.
# Neither has an image axis, so the leak is neither cleaned nor reported. Measured
# on the rendered boot document: 5 image-less build tags on a first real-tier run,
# 4 once --vlm-url is set (as_prod_shape_deployment:795 pops ai-vlm). The fake tier
# leaks nothing: --prod-shape is refused without --real (:2893) and both of its
# build services declare image: hsi-fake-ai, so compose never names one <project>-.
# grafana declares its own host-
# local `image:` and is NOT project-prefixed, so it is shared with production and
# must survive — the same reason skip-if-present exists.
#
# Removal therefore lives on the bare-engine surface (`image rm`), OUTSIDE the
# `run.started` gate: a run that dies in the pre-build never sets `started` (that
# flips inside `up`), yet a partial build already left images behind.
# ---------------------------------------------------------------------------


def _cleanup_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, list[tuple[list[str], dict[str, Any]]]]:
    """A rendered prod run plus its engine recorder, ready to clean up.

    The shape needs no argument: _prod_run builds with prod_shape=True, and the
    non-prod-shape case writes its own run because it also swaps the boot document.
    """
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    calls = _engine_answers(run, _PREBUILD_DOC, monkeypatch)
    run.render(fc.Snapshot.from_engine([], []))
    return run, calls


def test_a_prod_shape_run_removes_the_images_it_built_under_its_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The names come from build_images over the run's OWN boot document, so the
    # cleanup cannot drift from what `up` looked for. Only this run's prefixed tags
    # go; grafana's declared name is production's image, not this run's to delete.
    run, calls = _cleanup_run(tmp_path, monkeypatch)
    backend_image = f"{run.project}-backend:latest"
    # Seed grafana as ACTUALLY PRESENT before cleaning up. The fake's build branch
    # never adds a declared-image service's tag (faithful: compose builds grafana
    # under its own host-local name, not `<project>-grafana`), so with an empty
    # engine the grafana assert below is unsatisfiable-by-construction and a mutant
    # dropping the `startswith(prefix)` filter survives it (ops-b's UR-89 finding).
    # `prebuild_images` leaves grafana in the engine under this exact name whenever
    # it was absent, so this is the state that matters — the filter is the only
    # thing between this cleanup and production's grafana image.
    calls.have.add(_GRAFANA)

    status = run.cleanup_images()

    assert _image_rms(calls) == [backend_image], (
        "the project-namespaced build image must be removed by the exact name `up` "
        f"used, and nothing else — grafana's declared tag was present: {_image_rms(calls)}"
    )
    assert _GRAFANA not in _image_rms(calls), (
        "a declared host-local image is not this run's to remove"
    )
    assert _GRAFANA in calls.have, "grafana's image must still be in the engine after the run"
    assert status == fc.EXIT_OK, status
    assert run.summary["images_removed"] == [backend_image], run.summary
    assert run.summary["images_leaked"] == [], run.summary


def test_the_image_cleanup_asks_before_removing_and_skips_what_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `image rm` on a name the engine does not have is an error, not a no-op, so
    # the cleanup checks each name first, the way the pre-build does: an absent
    # name costs an inspect, never an rm that would report a false failure. A boot
    # document is written by hand so the names are KNOWN, and the engine holds
    # none of them — the two-sided half of the ask-before-remove pair.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    calls = _engine_answers(run, _PREBUILD_DOC, monkeypatch, present=frozenset())
    run.compose_file.write_text(json.dumps(_PREBUILD_DOC), encoding="utf-8")

    assert run.cleanup_images() == fc.EXIT_OK
    assert _image_rms(calls) == [], (
        f"an image the engine does not have must not be `image rm`'d: {_image_rms(calls)}"
    )
    inspected = {argv[3] for argv, _ in calls if argv[1:3] == ["image", "inspect"]}
    assert inspected == {f"{run.project}-backend:latest"}, inspected


def test_a_run_that_never_started_still_removes_its_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # THE reason cleanup sits outside `if run.started:`. A pre-build that dies
    # after building SOME images leaves those with `started` still False, and the
    # gate that correctly guards `teardown` would skip them. Engine state is seeded
    # to say exactly that: backend's tag exists, the render still dies (build_rc=1,
    # a build that half-finished is the operator's first-run situation).
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    partial = f"{run.project}-backend:latest"
    calls = _engine_answers(
        run,
        _PREBUILD_DOC,
        monkeypatch,
        present=frozenset({partial}),
        build_rc=1,
        build_tail="mkdir /sys/fs/cgroup: permission denied",
    )
    with pytest.raises(fc.HarnessError):
        run.render(fc.Snapshot.from_engine([], []))
    assert run.started is False, "a failed pre-build must never have set started"

    assert run.cleanup_images() == fc.EXIT_OK
    assert _image_rms(calls) == [partial], _image_rms(calls)


def test_the_image_cleanup_is_gated_on_shape_not_on_started(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The wiring is the finding: an unguarded call site is decoration if the gate
    # next to it swallows it. `run_check`'s finally must call cleanup whether or not
    # `started` flipped, and must NOT reach the engine for a tier that built nothing.
    import argparse

    calls: list[str] = []

    class StubRun:
        started = False
        prod_shape = True

        def __init__(self) -> None:
            self.artifacts = tmp_path
            self.summary: dict[str, Any] = {}

        def prepare(self) -> Any:
            # prepare() runs BEFORE run_check's try block, so it has to succeed for
            # the finally to run at all; the failure goes in render(), inside it.
            return fc.Snapshot.from_engine([], [])

        def render(self, before: Any, vlm: Any = None) -> None:
            raise fc.HarnessError("stopped on purpose")

        def cleanup_images(self) -> int:
            calls.append("cleanup")
            return fc.EXIT_OK

        def _write(self, name: str, data: Any) -> None:
            return None

    stub = StubRun()
    # run_check resolves `Run` from the module at call time (`run = Run(...)`,
    # :2727), so handing it the stub is a module-attribute patch — which monkeypatch
    # undoes exactly. Do NOT patch `Run.__new__` here: a subclass never owns that
    # slot, and monkeypatch's snapshot-then-restore leaves CPython's `__new__`
    # unwinding broken, so every LATER `fc.Run(...)` in the process raises
    # "object.__new__() takes exactly one argument". render() is where the stub
    # fails: prepare() runs before run_check's try block, so the failure has to
    # happen inside the try for the finally under test to run at all.
    monkeypatch.setattr(fc, "Run", lambda **_kw: stub)
    monkeypatch.setattr(fc, "AgentGpu", lambda *_a, **_k: None)

    args = argparse.Namespace(
        engine="podman", root=tmp_path / "runs", image_tag="test", prod_shape=True
    )
    status = fc.run_check(args, mode="real")
    assert calls == ["cleanup"], (
        "the finally must attempt image cleanup even when the run never started"
    )
    assert status != fc.EXIT_OK, "a run that died still reports its failure exit"


def test_a_non_prod_shape_run_touches_no_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Only the prod shape is in scope. The CI tier boots registry images and builds
    # nothing (docker-compose.ci.yml: 4 services, zero build blocks); the fake tier
    # DOES build two, but tags them image: hsi-fake-ai, and --prod-shape is refused
    # without --real. Either way an `image inspect` per service is pure cost and an
    # `image rm` there could delete outside the run's own namespace. The doc is hand-written, WITH
    # the build blocks a prod render would have, so a guard that looked only at the
    # document would still act here — this pins the shape guard, not the document.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    calls = _engine_answers(run, _PREBUILD_DOC, monkeypatch)
    run.prod_shape = False
    run.compose_file.write_text(json.dumps(_PREBUILD_DOC), encoding="utf-8")

    assert run.cleanup_images() == fc.EXIT_OK
    assert _image_rms(calls) == [], _image_rms(calls)
    assert [a for a, _ in calls if a[1:3] == ["image", "inspect"]] == []


def test_a_pre_render_run_removes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # No boot document means no measured names. Deriving them from a second source
    # (the stack YAML, a fixed list) is exactly the drift the names come from the
    # render to avoid; an empty hand is the honest answer.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    calls = _engine_answers(run, _PREBUILD_DOC, monkeypatch)
    assert not run.compose_file.exists()
    assert run.cleanup_images() == fc.EXIT_OK
    assert _image_rms(calls) == []
    assert [a for a, _ in calls if a[1:3] == ["image", "inspect"]] == []


def test_a_stalled_inspect_is_reported_as_unknown_and_not_as_a_clean_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # A stalled `image inspect` returns rc=124, which is nonzero, and a nonzero
    # inspect is the code's signal for "this name never existed". Without the stall
    # fence a dead engine therefore reads as a perfectly clean run: the whole point
    # of this step is that a leak must not be reported as a cleanup, and "the engine
    # never answered" is not evidence that nothing leaked. `_stalled` is the file's
    # own detector (`_exit_word` already refuses to let a stall and a refusal read
    # alike), and the name must NOT be `image rm`'d: unknown state is not absence.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    # The boot document is what makes this test measure the loop at all: without it
    # cleanup_images() returns EXIT_OK at its own "no render, no names" gate and every
    # assertion below passes without the stall branch ever running.
    run.compose_file.write_text(json.dumps(_PREBUILD_DOC), encoding="utf-8")
    backend_image = f"{run.project}-backend:latest"

    def stalled_engine(self: Any, command: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        argv = [str(part) for part in command]
        calls.append(argv)
        if argv[1:3] == ["image", "inspect"]:
            return subprocess.CompletedProcess(
                argv, fc._TIMEOUT_RC, "", f"{fc._TIMEOUT_NOTE} after 300 seconds"
            )
        return subprocess.CompletedProcess(argv, 0, "", "")

    calls: list[list[str]] = []
    monkeypatch.setattr(fc.Run, "_run", stalled_engine)

    assert run.cleanup_images() == fc.EXIT_FAILED
    assert run.summary["images_stalled"] == [backend_image], run.summary
    assert run.summary["images_removed"] == [], run.summary
    assert run.summary["images_leaked"] == [], run.summary
    assert [a for a in calls if a[1:3] == ["image", "rm"]] == [], calls
    logged = capsys.readouterr().out
    assert f"the engine timed out: {backend_image}" in logged, logged


def _refusing_engine(
    run: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    answer: str,
    rc: int | None = None,
) -> list[list[str]]:
    """Answer every `image inspect` with a refusal, and record the argvs.

    `answer` is `"down"` (the daemon's not-there words for this run's engine), `"absent"`
    (its honest no-such-image words), or a literal stderr to hand back verbatim. The
    message is resolved INSIDE the fake because fidelity needs the run's own engine, and
    a per-call lambda would either ignore arguments (ruff ARG005) or re-derive the engine
    at every call site. A refusal is not a stall: rc is never 124, so the stall fence
    doesn't see it and this exercises the other door.
    """
    exit_code = rc if rc is not None else _LOOKUP_RC[run.engine]
    calls: list[list[str]] = []

    def refusing(self: Any, command: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        argv = [str(part) for part in command]
        calls.append(argv)
        if argv[1:3] == ["image", "inspect"]:
            if answer == "down":
                stderr = _DOWN_STDERR[self.engine]
            elif answer == "absent":
                stderr = _absent_stderr(self.engine, argv[3])
            else:
                stderr = answer
            return subprocess.CompletedProcess(argv, exit_code, "", stderr)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(fc.Run, "_run", refusing)
    return calls


def test_a_down_engine_is_reported_as_unknown_and_not_as_a_clean_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The companion test fences a STALLED inspect (rc=124). This is the other door: a daemon that is
    # DOWN answers `image inspect` with the same exit code it uses for "that name is not in the
    # engine", so the bare nonzero test reads every name as never-having-existed and reports the
    # exact false-spotless run this step exists to prevent. The discriminator is the daemon's own
    # words, measured above; absence has to be POSITIVELY identified, not inferred from an rc.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    run.compose_file.write_text(json.dumps(_PREBUILD_DOC), encoding="utf-8")
    backend_image = f"{run.project}-backend:latest"
    calls = _refusing_engine(run, monkeypatch, answer="down")

    assert run.cleanup_images() == fc.EXIT_FAILED, (
        "a run whose engine never answered must not exit OK: the cleanup is unverified, not clean"
    )
    assert run.summary["images_stalled"] == [backend_image], (
        "the unknown name belongs in the list the operator acts on -- the repair is an engine "
        f"to fix, exactly as for a timeout: {run.summary}"
    )
    assert run.summary["images_removed"] == [], run.summary
    assert run.summary["images_leaked"] == [], run.summary
    # Not one `image rm`: guessing that a name is absent and removing it anyway is a second guess
    # stacked on the first, and on a daemon that is merely slow to come up it deletes a built image.
    assert [a for a in calls if a[1:3] == ["image", "rm"]] == [], calls
    logged = capsys.readouterr().out
    assert f"state unknown: {backend_image}" in logged, logged
    # The log carries the daemon's own words, because "state unknown" alone does not tell the
    # operator whether to wait for a hung engine or start a dead one.
    assert "Cannot connect" in logged or "failed to connect" in logged, logged


@pytest.mark.parametrize("engine", sorted(_ABSENT_STDERR))
def test_a_name_the_engine_positively_does_not_have_is_absent_not_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, engine: str
) -> None:
    # The must-ignore side, per engine: an honest "No such image" / "image not known" is evidence of
    # absence and must still exit OK with nothing named. Without this half the rule would be "any
    # refusal is unknown", every real cleanup of a never-built name would go red, and the next
    # person would delete the guard instead of the bug.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    run.engine = engine
    run.compose_file.write_text(json.dumps(_PREBUILD_DOC), encoding="utf-8")
    calls = _refusing_engine(run, monkeypatch, answer="absent")

    assert run.cleanup_images() == fc.EXIT_OK, run.summary
    assert run.summary["images_stalled"] == [], run.summary
    assert run.summary["images_leaked"] == [], run.summary
    assert run.summary["images_removed"] == [], run.summary
    assert [a for a in calls if a[1:3] == ["image", "rm"]] == [], calls


def test_the_absence_markers_discriminate_both_ways() -> None:
    # Two-sided control on the marker set itself, deterministic and engine-independent: each
    # supported engine's absent words must be accepted and its DOWN words refused. A marker list is
    # exactly the kind of constant that silently rots -- widen it to "any stderr" and the false
    # spotless returns; narrow it to one engine and that engine's real absences start reporting
    # unknown on every green run.
    for engine in sorted(_ABSENT_STDERR):
        absent = subprocess.CompletedProcess(
            ["x", "image", "inspect", "n"], _LOOKUP_RC[engine], "", "irrelevant"
        )
        absent.stderr = _ABSENT_STDERR[engine].format(name="proj-backend:latest")
        assert fc._image_absent(absent), f"{engine}'s measured absence marker must read absent"
        down = subprocess.CompletedProcess(
            ["x", "image", "inspect", "n"], _LOOKUP_RC[engine], "", _DOWN_STDERR[engine]
        )
        assert not fc._image_absent(down), f"{engine}'s measured DOWN text must read UNKNOWN"
    # And an rc=0 answer is not "absent" whatever its stderr, so the marker cannot turn a present
    # image into an unknown one.
    assert not fc._image_absent(
        subprocess.CompletedProcess(["x"], 0, "", _ABSENT_STDERR["docker"].format(name="n"))
    ), "rc=0 is present, full stop"


def test_the_engine_helper_holds_a_silence_is_not_an_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Empty stderr with a nonzero rc is the shape a fake writes by default and a real engine can
    # also produce (a wrapper that logged nothing). It is unknown, not absent: absence is a positive
    # claim the daemon made in words, and this pins that the guard's DEFAULT is the loud direction.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    run.compose_file.write_text(json.dumps(_PREBUILD_DOC), encoding="utf-8")
    _refusing_engine(run, monkeypatch, answer="")

    assert run.cleanup_images() == fc.EXIT_FAILED, run.summary
    assert run.summary["images_stalled"] == [f"{run.project}-backend:latest"], run.summary


def test_the_ceiling_of_unknown_covers_every_nonzero_inspect_that_is_not_marked_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The whole rule in one line: `image inspect` may be believed as "not present" ONLY when the
    # daemon said so. Every other nonzero answer -- a refusal, a bad name form, an unexpected rc --
    # is unknown. Pinning the rule as a sweep rather than as one case per message is what keeps a
    # new engine error shape from silently defaulting to "absent".
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    run.compose_file.write_text(json.dumps(_PREBUILD_DOC), encoding="utf-8")
    unmarked = [
        "docker: 'docker image inspect' requires at least 1 argument",
        "permission denied while trying to connect to the Docker daemon socket",
        "error during connect: Get http://%2Fvar%2Frun%2Fdocker.sock/v1.24/execute: dial unix",
        "",
    ]
    for stderr in unmarked:
        assert not fc._image_absent(
            subprocess.CompletedProcess(["x", "image", "inspect", "n"], 1, "", stderr)
        ), f"unmarked nonzero stderr {stderr!r} must read UNKNOWN, not absent"
    # One end-to-end instance of the sweep's conclusion, so the helper is not the only thing pinned.
    _refusing_engine(
        run, monkeypatch, answer="permission denied while trying to connect to the daemon"
    )
    assert run.cleanup_images() == fc.EXIT_FAILED, run.summary
    assert run.summary["images_stalled"], run.summary


def test_the_cleanup_removes_the_prefixed_tags_in_a_stable_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The summary is pasted to the operator and diffed between runs, and the rm
    # order is what a log reader traces, so both get `sorted` rather than document
    # order. Hand-write a boot document whose two image-less build services are in
    # NON-alphabetical order: without the sort, both lists come out reversed.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    two_builds = {
        "services": {
            "zeta": {"build": {"context": "/repo/zeta"}},
            "alpha": {"build": {"context": "/repo/alpha"}},
        }
    }
    run.compose_file.write_text(json.dumps(two_builds), encoding="utf-8")
    calls = _engine_answers(run, two_builds, monkeypatch)
    for name in ("zeta", "alpha"):
        calls.have.add(f"{run.project}-{name}:latest")

    assert run.cleanup_images() == fc.EXIT_OK
    want = [f"{run.project}-alpha:latest", f"{run.project}-zeta:latest"]
    assert run.summary["images_removed"] == want, run.summary
    assert _image_rms(calls) == want, _image_rms(calls)


def test_the_fake_engine_never_seeds_a_declared_image_services_namespaced_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The fake's build branch adds `<project>-<service>:latest` only for a service
    # with no `image:`, because that is what compose actually does. That predicate
    # is what makes the grafana pin above mean anything: seed grafana's namespaced
    # tag too and `present` would be satisfied by an image no engine ever held, and
    # the "must not be rm'd" assertion would pass while the code lost the guard.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    calls = _engine_answers(run, _PREBUILD_DOC, monkeypatch)

    run.render(fc.Snapshot.from_engine([], []))

    assert f"{run.project}-backend:latest" in calls.have, sorted(calls.have)
    assert f"{run.project}-grafana:latest" not in calls.have, sorted(calls.have)


def test_an_unremovable_image_is_reported_not_swallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # An `image rm` that fails (in use, engine gone) must raise the exit, not vanish
    # into a summary that says the run cleaned up after itself.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    calls = _engine_answers(run, _PREBUILD_DOC, monkeypatch, rm_rc=1)
    run.render(fc.Snapshot.from_engine([], []))

    assert run.cleanup_images() == fc.EXIT_FAILED
    assert run.summary["images_removed"] == [], run.summary
    assert run.summary["images_leaked"] == [f"{run.project}-backend:latest"], (
        "the operator pastes summary.json verbatim, so an image left in the engine "
        f"must be named there and not only in the log: {run.summary}"
    )
    assert _image_rms(calls) == [f"{run.project}-backend:latest"], _image_rms(calls)
    # The live log too, not only the summary: the leak is reported where the
    # operator is watching while the run is still going. Deleting the `_log` line
    # for a leaked image reddens this half.
    logged = capsys.readouterr().out
    assert (
        f"FAIL prod-shape image still in the engine, not removed: {run.project}-backend" in logged
    ), logged


class _WiredRun:
    """A run that walks `run_check`'s whole lifecycle without an engine.

    `run_check` resolves `Run` from the module at call time, so a test hands it this
    via `monkeypatch.setattr(fc, "Run", ...)` — a module-attribute patch monkeypatch
    undoes exactly (never `Run.__new__`: a subclass never owns that slot and its
    snapshot-then-restore leaves CPython's slot unwinding broken for every LATER
    `fc.Run(...)` in the process). Every lifecycle method is a no-op except the ones
    a test is watching, and `record` collects the calls in the order they happened,
    which is what pins the ORDER of teardown and image cleanup.
    """

    def __init__(
        self,
        artifacts: Path,
        *,
        record: list[str] | None = None,
        fail_in: str | None = None,
        cleanup: int | None = fc.EXIT_OK,
        cleanup_raises: Exception | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.summary: dict[str, Any] = {}
        self.started = True
        self.prod_shape = True
        self.record = record if record is not None else []
        self.fail_in = fail_in
        self.cleanup = cleanup
        self.cleanup_raises = cleanup_raises

    def prepare(self) -> Any:
        return fc.Snapshot.from_engine([], [])

    def take_snapshot(self) -> Any:
        return fc.Snapshot.from_engine([], [])

    def render(self, before: Any, vlm: Any = None) -> None:
        if self.fail_in == "render":
            raise fc.HarnessError("stopped on purpose")

    def up(self, vlm: Any = None) -> None:
        self.record.append("up")

    def register_admin(self) -> None:
        return None

    def seed_cameras(self) -> None:
        return None

    def check_isolation(self) -> list[str]:
        return []

    def smoke(self, vlm: Any = None) -> list[str]:
        return []

    def golden(self) -> list[str]:
        return []

    def collect(self) -> None:
        return None

    def teardown(self, before: Any) -> tuple[list[str], list[str]]:
        self.record.append("teardown")
        return [], []

    def cleanup_images(self) -> int:
        self.record.append("cleanup")
        if self.cleanup_raises is not None:
            raise self.cleanup_raises
        assert self.cleanup is not None
        return self.cleanup

    def _write(self, name: str, data: Any) -> None:
        return None


def _run_check_with(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, run: _WiredRun) -> int:
    """Drive the real `run_check` over a stub run, prod-shape and real-tier."""
    import argparse

    monkeypatch.setattr(fc, "Run", lambda **_kw: run)
    monkeypatch.setattr(fc, "AgentGpu", lambda *_a, **_k: None)
    args = argparse.Namespace(
        engine="podman", root=tmp_path / "runs", image_tag="test", prod_shape=True
    )
    return fc.run_check(args, mode="real")


def test_a_green_prod_shape_run_removes_its_images_after_the_teardown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Two pins the failure-path wiring test cannot make, both measured as survivors
    # (ops-b's UR-89 review, reproduced in my own shell): a cleanup gated on
    # `status != EXIT_OK` — "only clean up when something went wrong" — passes every
    # failure-path test and leaks on every SUCCESSFUL run, which is the common case
    # this PR exists for; and moving the cleanup call above `_finish` removes the
    # images while containers still hold them, which is exactly the `image rm`
    # failure the code already handles. A green run reaching EXIT_OK with the calls
    # recorded in that order reddens both.
    record: list[str] = []
    run = _WiredRun(tmp_path, record=record)

    status = _run_check_with(monkeypatch, tmp_path, run)

    assert status == fc.EXIT_OK, run.summary
    assert "up" in record, "the run must actually have reached the boot"
    assert record == [*record[: record.index("teardown")], "teardown", "cleanup"], (
        f"image cleanup must run last, after the deployment is torn down: {record}"
    )
    assert record[-1] == "cleanup", record
    assert "cleanup" in record, (
        "a SUCCESSFUL prod-shape run must remove the images it built — they are "
        f"per-run names nothing else ever deletes: {record}"
    )


def test_a_cleanup_that_crashes_is_reported_and_not_reported_as_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # `_cleanup_images`'s docstring promises a cleanup that cannot run is "reported,
    # not swallowed". Both halves of that promise were unpinned: making its `except`
    # return EXIT_OK survived all 240, and so did deleting the `except` so the crash
    # escapes the finally. The run here is GREEN, so the exit word below comes from
    # the cleanup alone — a swallowed crash (EXIT_OK) cannot pass it — and the URGENT
    # line is what the operator pastes, so it is asserted as text.
    record: list[str] = []
    run = _WiredRun(
        tmp_path, record=record, cleanup_raises=fc.HarnessError("engine socket vanished")
    )

    status = _run_check_with(monkeypatch, tmp_path, run)
    logged = capsys.readouterr().out

    assert record[-1] == "cleanup", record
    assert "URGENT prod-shape image cleanup did not complete" in logged, logged
    assert "engine socket vanished" in logged, logged
    assert status == fc.EXIT_FAILED, (
        f"a run whose image cleanup could not run must not report a clean exit: {status}"
    )


# ---------------------------------------------------------------------------
# The failure-message WINDOWS: `up()`'s compose tail ([-400:]) and the pre-build's
# ([-1200:]). A UR-89 review at 0d8b04387 showed `[:400:]` SURVIVED all 231 tests:
# every existing boot-failure fixture is shorter than the window, so head-slice and
# tail-slice carry the same bytes and no pin can tell them apart. compose actually
# prints pages (the operator's up-replay runs to ~30KB) and the REASON sits at the
# END of a build log, so the slice direction is the whole message contract: keep
# the tail. Each pin is two-sided — the reason must survive, and a head marker that
# a head-slice (or an unbouned message) would carry must not.
# ---------------------------------------------------------------------------


def _long_compose_error(reason: str) -> str:
    # HEADMARKER sits at byte 0 of the flattened message; the reason sits at the
    # end, ~3k characters apart. A window that keeps the last N chars carries the
    # reason and not the marker; one that keeps the first N, or none at all, fails
    # one half of the pair.
    padding = "HEADMARKER " + "build step line output " * 150
    return f"docker compose … up … exited 1: {padding} {reason}"


def test_a_failed_up_message_keeps_the_tail_of_a_long_compose_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    reason = "ERROR: cgroup configuration: mkdir /sys/fs/cgroup/docker/buildx: denied"

    def deployment(*args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise fc.HarnessError(_long_compose_error(reason))

    monkeypatch.setattr(fc.Run, "deployment", deployment)
    monkeypatch.setattr(fc.Run, "check_vlm_reach", lambda *_: None)
    run = fc.Run(engine="docker", root=tmp_path / "runs", image_tag="test", mode="real")
    with pytest.raises(fc.HarnessError) as raised:
        run.up(vlm=_StubVlm())
    message = str(raised.value)
    assert reason in message, (
        f"a head-slice (or no window) lost the reason at the END of compose's output: "
        f"{message[:160]}"
    )
    assert "HEADMARKER" not in message, (
        "the message is unbounded or head-sliced: the window must keep the tail only"
    )


def test_a_failed_prebuild_message_keeps_the_tail_of_long_build_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The same contract one layer earlier: `prebuild_images` quotes the build with
    # its own window, and the builder's reason is at the end of its stream.
    reason = "STEP 2/6: Error: mounting /dev/fuse: Operation not permitted"

    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    _engine_answers(
        run,
        _PREBUILD_DOC,
        monkeypatch,
        build_rc=1,
        build_tail="HEADMARKER " + "sending build context " * 200 + reason,
    )
    with pytest.raises(fc.HarnessError) as raised:
        run.render(fc.Snapshot.from_engine([], []))
    message = str(raised.value)
    assert reason in message, f"the build's reason at the end was sliced away: {message[:160]}"
    assert "HEADMARKER" not in message, "the pre-build window must keep the tail, not the head"


# ---------------------------------------------------------------------------
# Ruling 127 / 187: --seeded mode (DEBUG=true, request recorder, breaker and
# threshold fault seeds, orphan file fixture, and golden-seeded project).
# ---------------------------------------------------------------------------


def test_as_test_deployment_seeded_enables_debug_recorder_fault_seed_and_data_tmpfs(
    base: dict[str, Any],
) -> None:
    unseeded = fc.as_test_deployment(base, project=PROJECT, run_dir=RUN_DIR)
    unseeded_backend = unseeded["services"]["backend"]
    unseeded_env = unseeded_backend["environment"]
    assert unseeded_env.get("DEBUG") != "true"
    assert "REQUEST_RECORDING_ENABLED" not in unseeded_env
    assert "HSI_FAULT_SEED" not in unseeded_env
    assert not any(
        entry.split(":", 1)[0].rstrip("/") == "/app/data" for entry in unseeded_backend["tmpfs"]
    )

    seeded = fc.as_test_deployment(base, project=PROJECT, run_dir=RUN_DIR, seeded=True)
    backend = seeded["services"]["backend"]
    env = backend["environment"]
    assert env["DEBUG"] == "true"
    assert env["REQUEST_RECORDING_ENABLED"] == "true"
    assert env["REQUEST_RECORDING_SAMPLE_RATE"] == "0.0"
    assert env["HSI_FAULT_SEED"] == "1"
    assert "/app/data:size=20m,mode=1777,uid=1000,gid=1000" in backend["tmpfs"]


def test_seeded_needs_a_mode_but_no_longer_needs_fake(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruling 235 rewrote the second half of this test.

    `--seeded` alone is still refused (it is a shape, not a mode) — that half is unchanged. What
    changed is `--real --seeded`: it used to exit 2 here, and ruling 235 rules it *accepted*, so
    this parse-layer test now proves it reached the tier's own availability gate instead of the
    flag check. `!= 2` would NOT prove that — it also passes on a tier that died for a reason
    unrelated to the parse layer, so both directions are pinned and neither is left to whatever
    this host happens to have installed (the form test_real_refuses_where_agent_gpu_is_absent
    already uses). Without agent-gpu the refusal is EXIT_UNAVAILABLE and nothing is created; with
    it on PATH the run gets further and is refused for the NEXT reason, the unset
    $AGENT_GPU_LIBRARY — still never exit 2, so no host can satisfy this by accident. The
    accept-and-boot path, with run_check stubbed, is test_seeded_with_real_boots_the_real_tier.
    """
    with pytest.raises(SystemExit) as bare:
        fc.main(["--seeded"])
    assert bare.value.code == 2

    no_gpu = tmp_path / "no-agent-gpu"
    monkeypatch.setenv("PATH", str(no_gpu))
    monkeypatch.delenv("AGENT_GPU_LIBRARY", raising=False)
    root = tmp_path / "runs-no-gpu"
    assert fc.main(["--real", "--seeded", "--root", str(root)]) == fc.EXIT_UNAVAILABLE == 4
    assert not root.exists()  # accepted by the parse layer, refused before it created anything

    shim = tmp_path / "bin"
    shim.mkdir()
    (shim / "agent-gpu").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (shim / "agent-gpu").chmod(0o755)
    monkeypatch.setenv("PATH", f"{shim}:/usr/bin:/bin")
    root_with = tmp_path / "runs-with-gpu"
    assert fc.main(["--real", "--seeded", "--root", str(root_with)]) == fc.EXIT_UNAVAILABLE
    assert not root_with.exists()  # the next gate refuses, not the flag check


def test_seed_debug_fixtures_plants_recordings_orphan_and_verifies_breaker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = fc.Run(
        engine="docker", root=tmp_path / "runs", image_tag="test", mode="fake", seeded=True
    )
    run.prepare()
    run.api = "http://127.0.0.1:32772"
    run.admin = {"username": "feature-check", "password": "secret"}  # pragma: allowlist secret

    exec_calls: list[tuple[str, ...]] = []

    def fake_deployment(*args: str, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        exec_calls.append(args)
        return subprocess.CompletedProcess(list(args), 0, stdout="21\n", stderr="")

    http_calls: list[tuple[str, str, Any]] = []

    def fake_http(
        method: str, url: str, payload: Any = None, timeout: float = 15, **kwargs: Any
    ) -> tuple[int, Any]:
        http_calls.append((method, url, kwargs.get("headers")))
        if url.endswith("/api/debug/recordings"):
            return 200, {"recordings": [{"recording_id": "r1"}, {"recording_id": "r2"}], "total": 2}
        if "/api/system/cleanup/orphaned-files" in url:
            return 200, {"orphaned_count": 1, "total_size": 21}
        if url.endswith("/api/system/storage"):
            return 200, {"disk_usage_percent": 93.0}
        if url.endswith("/api/known-persons"):
            return 200, {
                "items": [{"id": 1, "name": "Seeded Known Person", "embedding_count": 1}],
                "total": 1,
            }
        if url.endswith("/api/system/circuit-breakers"):
            return 200, {"circuit_breakers": {"redis": {"state": "open"}}, "open_count": 1}
        return 200, {"ok": True}

    monkeypatch.setattr(run, "deployment", fake_deployment)
    monkeypatch.setattr(fc, "_http", fake_http)

    run.seed_debug_fixtures()

    assert run.summary["results"]["seeded"] == "ok"
    assert any(headers and headers.get("X-Debug-Record") == "true" for _, _, headers in http_calls)
    assert any("seeded-orphan.jpg" in " ".join(c) and "os.utime" in " ".join(c) for c in exec_calls)
    assert any(
        ".seeded-disk-fill" in " ".join(c) and "shutil.disk_usage" in " ".join(c)
        for c in exec_calls
    )
    assert any(
        "KnownPerson" in " ".join(c)
        and "FaceEmbedding" in " ".join(c)
        and "test-only-seeded-vector" in " ".join(c)
        and "struct.pack('<512f'" in " ".join(c)
        for c in exec_calls
    )
    for c in exec_calls:
        if "-c" in c:
            ast.parse(c[c.index("-c") + 1])
    assert any(url.endswith("/api/system/storage") for _, url, _ in http_calls)
    assert any(url.endswith("/api/known-persons") for _, url, _ in http_calls)
    assert sum(1 for _, url, _ in http_calls if url.endswith("/api/debug/pipeline-state")) == 4


def test_seed_debug_fixtures_refuses_missing_seeded_face_embedding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = fc.Run(
        engine="docker", root=tmp_path / "runs", image_tag="test", mode="fake", seeded=True
    )
    run.prepare()
    run.api = "http://127.0.0.1:32772"
    run.admin = {"username": "feature-check", "password": "secret"}  # pragma: allowlist secret

    monkeypatch.setattr(
        run,
        "deployment",
        lambda *args, **_kwargs: subprocess.CompletedProcess(
            list(args), 0, stdout="1:1\n", stderr=""
        ),
    )

    def fake_http(
        _method: str, url: str, _payload: Any = None, _timeout: float = 15, **_kwargs: Any
    ) -> tuple[int, Any]:
        if url.endswith("/api/debug/recordings"):
            return 200, {"recordings": [{"recording_id": "r1"}, {"recording_id": "r2"}], "total": 2}
        if "/api/system/cleanup/orphaned-files" in url:
            return 200, {"orphaned_count": 1, "total_size": 21}
        if url.endswith("/api/system/storage"):
            return 200, {"disk_usage_percent": 93.0}
        if url.endswith("/api/known-persons"):
            return 200, {
                "items": [{"id": 1, "name": "Seeded Known Person", "embedding_count": 0}],
                "total": 1,
            }
        if url.endswith("/api/system/circuit-breakers"):
            return 200, {"circuit_breakers": {"redis": {"state": "open"}}, "open_count": 1}
        return 200, {"ok": True}

    monkeypatch.setattr(fc, "_http", fake_http)

    with pytest.raises(fc.HarnessError, match="embedding_count >= 1"):
        run.seed_debug_fixtures()


def test_seed_debug_fixtures_refuses_under_90_percent_disk_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = fc.Run(
        engine="docker", root=tmp_path / "runs", image_tag="test", mode="fake", seeded=True
    )
    run.prepare()
    run.api = "http://127.0.0.1:32772"
    run.admin = {"username": "feature-check", "password": "secret"}  # pragma: allowlist secret

    monkeypatch.setattr(
        run,
        "deployment",
        lambda *args, **_kwargs: subprocess.CompletedProcess(
            list(args), 0, stdout="89.9\n", stderr=""
        ),
    )

    def fake_http(
        _method: str, url: str, _payload: Any = None, _timeout: float = 15, **_kwargs: Any
    ) -> tuple[int, Any]:
        if url.endswith("/api/debug/recordings"):
            return 200, {"recordings": [{"recording_id": "r1"}, {"recording_id": "r2"}], "total": 2}
        if "/api/system/cleanup/orphaned-files" in url:
            return 200, {"orphaned_count": 1, "total_size": 21}
        if url.endswith("/api/system/storage"):
            return 200, {"disk_usage_percent": 89.9}
        if url.endswith("/api/system/circuit-breakers"):
            return 200, {"circuit_breakers": {"redis": {"state": "open"}}, "open_count": 1}
        return 200, {"ok": True}

    monkeypatch.setattr(fc, "_http", fake_http)

    with pytest.raises(fc.HarnessError, match="disk_usage_percent >= 90"):
        run.seed_debug_fixtures()


@pytest.mark.parametrize("mode", ["fake", "real"], ids=["fake-tier", "real-tier"])
def test_golden_seeded_runs_golden_seeded_playwright_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """The seeded leg selects the seeded Playwright project, on BOTH tiers.

    ``golden()`` picks the project from ``seeded`` alone (``feature_check.py:2345``).
    The ``real`` arm is the one this adds: a guard that also demanded
    ``mode == "fake"`` — true of every seeded run before ruling 235 — leaves this
    test green while ``--real --seeded`` runs the UNSEEDED ``golden`` project against
    a seeded backend, silently reporting the ~11 ``*.seeded.spec.ts`` rows as never
    run. The un-seeded half of the same condition is pinned by
    ``test_the_leg_runs_in_the_image_with_the_same_argv_inside``, which asserts
    ``--project=golden`` for an un-seeded run, so the two tests together cover every
    arm rather than only the arm a fix could break.
    """
    run = fc.Run(engine="docker", root=tmp_path / "runs", image_tag="test", mode=mode, seeded=True)
    run.prepare()
    run.api = "http://127.0.0.1:32772"
    run.ui = "http://127.0.0.1:32773"
    run.admin = {"username": "feature-check", "password": "secret"}  # pragma: allowlist secret

    config = tmp_path / "playwright.config.ts"
    config.write_text(
        "projects: [{ name: 'golden' }, { name: 'golden-seeded' }]\n", encoding="utf-8"
    )
    monkeypatch.setattr(fc, "PLAYWRIGHT_CONFIG", config)
    monkeypatch.setattr(fc, "FRONTEND_MODULES", tmp_path)

    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        cmd = [str(c) for c in command]
        commands.append(cmd)
        if "playwright" in " ".join(cmd):
            junit = run.artifacts / "golden-playwright.xml"
            junit.write_text(
                '<testsuites><testsuite name="operations/debug-mode-toggle.seeded.spec.ts">'
                '<testcase classname="debug-mode-toggle.seeded.spec.ts" name="F-133"/>'
                "</testsuite></testsuites>",
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(run, "_run", fake_run)
    problems = run.golden()
    assert problems == []
    playwright_cmds = [" ".join(c) for c in commands if "--project=" in " ".join(c)]
    assert len(playwright_cmds) == 1
    assert "--project=golden-seeded" in playwright_cmds[0]
    assert "--project=golden " not in playwright_cmds[0]


# --- ruling 235: the flag matrix for --seeded ---------------------------------------------
#
# Before ruling 235 the parse layer refused `--seeded` without `--fake`, and that one line was
# doing double duty: it also blocked `--real --seeded --prod-shape`. Widening `--seeded` to the
# real tier therefore has to carry its own prod-shape refusal, and the matrix below pins all four
# edges together so the loosening cannot silently widen a third combination.
#
# Every case goes through main(), the same entry the CLI uses, because the thing under test is the
# decision made before any engine call — so the engine is replaced by a recorder and the real
# tier's agent-gpu probe is stubbed to "available". If a case ever boots anything, the assert fires.


def _fake_boot(monkeypatch: Any) -> list[tuple[str, bool, bool]]:
    """Record run_check calls instead of booting; pretend agent-gpu is on PATH."""
    booted: list[tuple[str, bool, bool]] = []

    def fake_run_check(args: Any, *, mode: str) -> int:
        booted.append((mode, bool(args.seeded), bool(args.prod_shape)))
        return 0

    monkeypatch.setattr(fc, "run_check", fake_run_check)
    monkeypatch.setattr(fc, "real_unavailable", lambda _environ: None)
    return booted


def test_seeded_with_real_boots_the_real_tier_seeded(monkeypatch: Any) -> None:
    """Ruling 235's whole point: `--real --seeded` reaches run_check, seeded, on the real tier."""
    booted = _fake_boot(monkeypatch)
    assert fc.main(["--real", "--seeded"]) == 0
    assert booted == [("real", True, False)]


def test_seeded_with_fake_is_unchanged(monkeypatch: Any) -> None:
    """The command the CI leg runs (`--fake --seeded`) behaves exactly as before."""
    booted = _fake_boot(monkeypatch)
    assert fc.main(["--fake", "--seeded"]) == 0
    assert booted == [("fake", True, False)]


def test_seeded_without_a_mode_is_still_refused(monkeypatch: Any) -> None:
    """`--seeded` is still a shape, not a mode: with neither --fake nor --real it refuses."""
    booted = _fake_boot(monkeypatch)
    with pytest.raises(SystemExit):
        fc.main(["--seeded"])
    assert booted == []


def test_seeded_with_prod_shape_is_refused_under_real(monkeypatch: Any) -> None:
    """The refusal the OLD `--seeded needs --fake` line covered by accident, now stated on its own.

    This is the case that would silently have started booting prod.yml with DEBUG=true if the
    change had only relaxed the fake requirement.
    """
    booted = _fake_boot(monkeypatch)
    with pytest.raises(SystemExit):
        fc.main(["--real", "--seeded", "--prod-shape"])
    assert booted == []


def test_a_bare_invocation_is_refused(monkeypatch: Any, capsys: Any) -> None:
    """The generic mode refusal lives again, narrowed to the shape ruling 256 kept open.

    The ruling-256 venue split deleted the old `choose --fake or --real` guard so the maui
    run's bare `--prod-shape` could fall through to the fake tier, and a bare invocation fell
    through with it — silently booting the CI fake tier (ruling 262's audit found the defect
    on this file). The restored guard refuses a call with no mode and no shape, names all
    three forms, and `--prod-shape` alone still boots the fake tier (the maui run's form,
    pinned by the next test).
    """
    booted = _fake_boot(monkeypatch)
    with pytest.raises(SystemExit):
        fc.main([])
    booted_refused = booted == []
    err = capsys.readouterr().err
    assert booted_refused, "a bare invocation must not reach run_check"
    assert "choose --fake or --real" in err, err
    assert "--prod-shape" in err, err


def test_a_bare_prod_shape_boots_the_fake_tier(monkeypatch: Any) -> None:
    """The maui run's form (`--prod-shape`, no mode flag) is the one fall-through that stays."""
    booted = _fake_boot(monkeypatch)
    assert fc.main(["--prod-shape"]) == 0
    assert booted == [("fake", False, True)]


# [r264] The golden leg's shard flag. Refusals first (a shard on the wrong tier
# is a silent coverage hole, ruling 114's shape), then the argv pin (the inner
# command carries Playwright's own `--shard=i/N`, and the unsharded run's argv
# stays byte-identical).


def test_a_shard_needs_the_fake_tier(monkeypatch: Any) -> None:
    """`--shard` is the CI fake tier's option: on --real it refuses, before any boot."""
    booted = _fake_boot(monkeypatch)
    with pytest.raises(SystemExit):
        fc.main(["--real", "--shard", "1/2"])
    assert booted == []


def test_a_shard_is_refused_with_prod_shape(monkeypatch: Any) -> None:
    """The prod shape is the real tier's shape; a shard there witnesses a partial suite."""
    booted = _fake_boot(monkeypatch)
    with pytest.raises(SystemExit):
        fc.main(["--prod-shape", "--shard", "1/2"])
    assert booted == []


@pytest.mark.parametrize("bad", ["0/2", "3/2", "5/5x", "/2", "2/", "2", "1/0", "a/b"])
def test_a_malformed_shard_is_refused(monkeypatch: Any, bad: str) -> None:
    """The flag takes exactly `I/N` with 1 <= I <= N; anything else refuses at parse time."""
    booted = _fake_boot(monkeypatch)
    with pytest.raises(SystemExit):
        fc.main(["--fake", "--shard", bad])
    assert booted == []


def test_a_sharded_fake_run_boots_with_the_shard(monkeypatch: Any) -> None:
    """`--fake --shard 2/3` boots the fake tier, and the record carries the shard."""
    seen: dict[str, Any] = {}

    def fake_run_check(args: Any, *, mode: str) -> int:
        seen["shard"] = args.shard
        return 0

    monkeypatch.setattr(fc, "run_check", fake_run_check)
    monkeypatch.setattr(fc, "real_unavailable", lambda _environ: None)
    assert fc.main(["--fake", "--shard", "2/3"]) == 0
    assert seen["shard"] == (2, 3)


def test_an_unset_shard_boots_with_none(monkeypatch: Any) -> None:
    """Without --shard the run is the unsharded run: shard is None, nothing else moves."""
    seen: dict[str, Any] = {}

    def fake_run_check(args: Any, *, mode: str) -> int:
        seen["shard"] = args.shard
        return 0

    monkeypatch.setattr(fc, "run_check", fake_run_check)
    monkeypatch.setattr(fc, "real_unavailable", lambda _environ: None)
    assert fc.main(["--fake"]) == 0
    assert seen["shard"] is None


def test_the_seeded_refusals_are_distinguishable(monkeypatch: Any, capsys: Any) -> None:
    """A refusal that cannot be told apart from another one teaches an operator nothing.

    Pinning the two messages separately also catches a guard reordered into the wrong slot: a
    reader who types `--seeded --prod-shape --real` should be told about DEBUG=true in production,
    not about choosing a mode.

    The bare-`--seeded` pin is deliberately TWO-SIDED. Its substring `--fake or --real` is also a
    substring of the restored generic refusal `choose --fake or --real`, which the bare-run guard
    prints. So deleting the seeded guard entirely
    still satisfies the positive half — the run falls through to the generic refusal and the
    substring is present. The negative half is what makes this a pin: the operator has to be told
    that the SHAPE needs a mode, not that they forgot to pick a tier.
    """
    _fake_boot(monkeypatch)
    with pytest.raises(SystemExit):
        fc.main(["--seeded", "--prod-shape", "--real"])
    err = capsys.readouterr().err
    assert "prod-shape" in err, err
    assert "DEBUG=true" in err, err

    with pytest.raises(SystemExit):
        fc.main(["--seeded"])
    err = capsys.readouterr().err
    assert "--seeded needs --fake or --real" in err, err
    assert "boot shape" in err, err
    assert "choose --fake or --real" not in err, f"fell through to the generic mode refusal: {err}"


def test_a_real_seeded_run_gets_the_seeded_shape_and_overrides(
    tmp_path: Path, base: dict[str, Any]
) -> None:
    """Ruling 235's boot-level half: on `--real` the seeded shape still applies.

    `as_test_deployment` takes `seeded` but not `mode`, so the overrides are mode-independent by
    signature — that is the structural reason a real-tier seeded boot needs no new code path. This
    pins the two user-visible consequences anyway, because a signature is easy to change later:
    the run's shape string (which lands in the run record a reviewer reads) and the DEBUG/recorder
    environment the seeded golden specs depend on.
    """
    run = fc.Run(
        engine="docker", root=tmp_path / "runs", image_tag="test", mode="real", seeded=True
    )
    assert run.shape == "real-seeded"

    seeded = fc.as_test_deployment(base, project=PROJECT, run_dir=RUN_DIR, seeded=True)
    env = seeded["services"]["backend"]["environment"]
    assert env["DEBUG"] == "true"
    assert env["HSI_FAULT_SEED"] == "1"
    assert env["REQUEST_RECORDING_ENABLED"] == "true"


def test_a_real_seeded_boot_forwards_the_flag_into_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The handoff at the top of ``run_check``, where the CLI flag becomes ``Run.seeded``.

    Every flag-matrix test above replaces ``run_check`` wholesale, so none of them ever runs this
    line. A ``seeded = False`` here would boot the real tier unseeded while every parse test stayed
    green: the run would still print ``mode``, the seeded golden project would simply collect
    nothing, and the operator's ``--real --seeded`` would report a clean run that seeded nothing.
    So pin the exact handoff, not its two ends — the same shape as
    test_run_check_builds_the_run_with_the_shape for prod_shape.
    """
    import argparse

    captured: dict[str, Any] = {}
    real_init = fc.Run.__init__

    def spy(self: Any, **kwargs: Any) -> None:
        captured.update(kwargs)
        real_init(self, **kwargs)

    monkeypatch.setattr(fc.Run, "__init__", spy)

    class StopHere(Exception):
        pass

    monkeypatch.setattr(fc.Run, "prepare", lambda *_a, **_k: (_ for _ in ()).throw(StopHere))

    args = argparse.Namespace(
        engine="podman",
        root=tmp_path / "runs",
        image_tag="test",
        prod_shape=False,
        seeded=True,
    )
    with pytest.raises(StopHere):
        fc.run_check(args, mode="real")
    assert captured.get("seeded") is True, "run_check must forward --seeded to Run"
    assert captured.get("mode") == "real"


def test_a_real_and_seeded_deployment_takes_the_vlm_url_and_the_seeded_shape_together(
    base: dict[str, Any], live: Any
) -> None:
    """The one call the real tier actually makes: ``vlm_url`` AND ``seeded`` set at once.

    ``as_test_deployment`` takes both, and the two guards sit in different parts of the function —
    ``vlm_url`` chooses the kept services and pops the in-stack ``ai-vlm`` dependency, ``seeded``
    sets the DEBUG/recorder/fault-seed environment and the ``/app/data`` tmpfs. The seeded-only
    test above never passes ``vlm_url``, and test_the_real_take... never passes ``seeded``, so
    either half alone leaves this combination untested. If the overrides were ever gated on
    ``vlm_url is None`` — a plausible-looking "seeded is a fake-tier shape" edit — the real tier
    would boot WITHOUT the recorder or the fault seeds, and the seeded goldens it then runs would
    read an unseeded backend and pass anyway.

    It also has to survive the preflight, because the seeded tmpfs is a new mount on the real
    tier's deployment.
    """
    both = fc.as_test_deployment(
        base, project=PROJECT, run_dir=RUN_DIR, vlm_url=VLM_URL, seeded=True
    )
    backend = both["services"]["backend"]
    env = backend["environment"]

    # the real half: VLM from agent-gpu, in-stack ai-vlm gone from both services and depends_on
    assert list(both["services"]) == list(fc.REAL_SERVICES)
    assert env["AI_VLM_URL"] == VLM_URL
    assert "ai-vlm" not in backend["depends_on"]

    # the seeded half, on top of it, unchanged from the fake tier
    assert env["DEBUG"] == "true"
    assert env["REQUEST_RECORDING_ENABLED"] == "true"
    assert env["REQUEST_RECORDING_SAMPLE_RATE"] == "0.0"
    assert env["HSI_FAULT_SEED"] == "1"
    assert "/app/data:size=20m,mode=1777,uid=1000,gid=1000" in backend["tmpfs"]

    # and the combination is still a deployment the in-run check accepts
    assert _preflight(both, live, allowed_host_ports=frozenset({18123})) == []


# ---------------------------------------------------------------------------
# [O2.5 venue fixes] the maui venue's own parameters reach the prod-shape env
# file, and nothing else from the caller does.
# ---------------------------------------------------------------------------


def test_prod_shape_venue_parameters_do_not_import_other_host_settings(tmp_path: Path) -> None:
    # The maui venue sets GPU_AI_SERVICES / AI_MODELS_PATH / ADMIN_ENABLED in its
    # login shell (VENUE-PROFILE.md). The generated env file is the ONLY input the
    # prod render reads (O2.2), so a venue value that never lands in it silently
    # renders as prod's own default instead -- the model zoo and admin surface of a
    # venue the run is not in. But "venue parameters" must stay a closed list: the
    # caller's shell is still untrusted (POSTGRES_PASSWORD is a host secret, DEBUG
    # flips the app's boot), so anything outside the three names is dropped.
    caller = {
        "PODMAN_SOCKET": _ENGINE_SOCKET,
        "GPU_AI_SERVICES": "0",
        "AI_MODELS_PATH": "/venue/models",
        "ADMIN_ENABLED": "true",
        "DEBUG": "true",
        "POSTGRES_PASSWORD": "host-secret",  # pragma: allowlist secret
    }
    text = fc.prod_shape_env(run_dir=tmp_path, image_tag="test", caller=caller)
    assert "GPU_AI_SERVICES=0\n" in text
    assert "AI_MODELS_PATH=/venue/models\n" in text
    assert "ADMIN_ENABLED=true\n" in text
    assert "DEBUG=" not in text, "the closed list must not widen to the whole shell"
    assert "host-secret" not in text
    # An env file is one KEY=value per line: a multi-line value would smuggle the
    # next lines in as new keys (DEBUG=true below) -- the same interpolation the
    # file's own ${X:?} refusals guard against, now from the caller's side.
    caller["AI_MODELS_PATH"] = "/venue/models\nDEBUG=true"
    with pytest.raises(fc.HarnessError, match="single-line"):
        fc.prod_shape_env(run_dir=tmp_path, image_tag="test", caller=caller)


# ---------------------------------------------------------------------------
# [O2.5 venue fixes] exporter health checks on the maui venue, opt-in.
# ---------------------------------------------------------------------------


def test_exporter_healthchecks_are_real_http_probes_with_readonly_tool_mount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The maui venue's engine reports an empty health status for services without
    # checks, so `up --wait` cannot hold the boot on the two exporters. The fix is
    # opt-in (PROD_SHAPE_HEALTHCHECK_BUSYBOX) and doubles as a security gate: the
    # only thing that crosses the bind is the venue's own busybox, mounted READ-ONLY
    # at a fixed target, and the probe it runs is wget --spider against the
    # service's own loopback metrics port. An absent or non-executable tool is
    # refused at render time, not discovered by a boot that never went healthy.
    tool = tmp_path / "busybox"
    tool.write_bytes(b"fixture")
    tool.chmod(0o755)
    monkeypatch.setenv("PROD_SHAPE_HEALTHCHECK_BUSYBOX", str(tool))
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    monkeypatch.setattr(run, "prebuild_images", lambda: None)
    doc = copy.deepcopy(_PREBUILD_DOC)
    doc["services"]["redis-exporter"] = {"healthcheck": {"disable": True}}
    doc["services"]["json-exporter"] = {}
    calls = _fake_compose(run, doc)
    run.render(fc.Snapshot.from_engine([], []))
    services = json.loads(run.compose_file.read_text())["services"]
    for name, port in (("redis-exporter", 9121), ("json-exporter", 7979)):
        svc = services[name]
        assert svc["healthcheck"]["test"] == [
            "CMD",
            "/busybox",
            "wget",
            "-q",
            "--spider",
            "-T",
            "4",
            f"http://localhost:{port}/metrics",
        ]
        assert "disable" not in svc["healthcheck"], "the probe must actually run"
        assert svc["volumes"][-1] == {
            "type": "bind",
            "source": str(tool),
            "target": "/busybox",
            "read_only": True,
        }
    # the render it bootstraps from is untouched: the authored doc stays as compose
    # answered it (the transform edits the boot document, never its inputs)
    assert doc["services"]["redis-exporter"]["healthcheck"] == {"disable": True}
    assert [list(files) for files, _ in calls] == [
        [fc.PROD_STACK, fc.PROD_SHAPE_OVERRIDE],
        [fc.CI_STACK, fc.FAKE_OVERLAY],
    ]


def test_exporter_healthcheck_refuses_an_unusable_busybox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Opt-in must be honest: a path that is not an executable file would produce a
    # healthcheck that fails every probe and a boot that never turns healthy, with
    # the cause three layers away from the setting. Refuse at render time.
    missing = tmp_path / "absent"
    not_exec = tmp_path / "tool"
    not_exec.write_bytes(b"not executable")
    run = fc.Run(
        engine="podman",
        root=tmp_path / "runs",
        image_tag="test",
        mode="real",
        prod_shape=True,
    )
    run.dir.mkdir(parents=True)
    run.artifacts.mkdir(parents=True)
    run.env_file.write_text("IMAGE_TAG=test\n", encoding="utf-8")
    for bad in (missing, not_exec):
        with monkeypatch.context() as patch:
            patch.setenv("PROD_SHAPE_HEALTHCHECK_BUSYBOX", str(bad))
            with pytest.raises(fc.HarnessError, match="busybox"):
                fc.as_prod_shape_deployment(
                    _prod_rendered(
                        **{
                            "redis-exporter": {"healthcheck": {"disable": True}},
                            "json-exporter": {},
                        }
                    ),
                    vlm_url=None,
                )


# ---------------------------------------------------------------------------
# [O2.5 venue fixes] the fake the prod-shape run builds is THIS run's fake: its
# image tags are the run's project, its base is the backend this run built, and
# its build is fresh. The CI path stays exactly as it was.
# ---------------------------------------------------------------------------


def test_prod_shape_builds_a_fresh_fake_after_its_own_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The maui venue's fake must never boot from a shared `hsi-fake-ai:latest` --
    # that name is host-global, so it can carry ANOTHER checkout's fake code (the
    # tag is `latest` for every project), and its base would be whatever backend
    # built it, not this run's. The run's own project tag and this run's backend
    # image are what `build_images` derives for a build service with no image,
    # so the fake lands where `up --no-build` looks for it -- and the pre-build
    # builds the backend BEFORE the fakes that FROM it, in one builder pass each.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    doc = copy.deepcopy(_PREBUILD_DOC)
    doc["services"]["ai-vlm"] = {
        "image": "hsi-fake-ai:${IMAGE_TAG:-latest}",
        "build": {"context": "/repo", "dockerfile": "docker/fake-ai/Dockerfile"},
    }
    # prod's REAL gateway: the maui venue keeps it (ruling 256 item 2) and builds
    # it from prod's own Dockerfile under the project tag -- it is in the FIRST
    # build group, and nothing here renames it. An image-less build service has
    # no `image` key in the boot document (compose derives the name at `up`).
    doc["services"]["ai-gateway"] = {
        "build": {"context": "/repo", "dockerfile": "ai/gateway/Dockerfile"},
    }
    calls = _engine_answers(run, doc, monkeypatch)

    run.render(fc.Snapshot.from_engine([], []))
    boot = json.loads(run.compose_file.read_text())

    # The spliced fake VLM carries the run's own tags.
    assert boot["services"]["ai-vlm"]["image"] == f"{run.project}-ai-vlm:latest"
    assert boot["services"]["ai-vlm"]["build"]["args"]["BACKEND_IMAGE"] == (
        f"{run.project}-backend:latest"
    )
    assert "image" not in boot["services"]["ai-gateway"]
    assert "args" not in boot["services"]["ai-gateway"]["build"]
    # the authored doc is untouched: the run does not edit its inputs
    assert doc["services"]["ai-vlm"]["image"] == "hsi-fake-ai:${IMAGE_TAG:-latest}"
    # the build came in two passes: backend+grafana first, then the fake,
    # with --no-cache under prod-shape only
    builds = _verb_calls(calls, "build")
    assert len(builds) == 2, builds
    first, second = (
        [p for p in argv[_last(argv, "-f") + 3 :] if p != "--no-cache"] for argv in builds
    )
    assert sorted(first) == ["ai-gateway", "backend", "grafana"], first
    assert sorted(second) == ["ai-vlm"], second
    assert all("--no-cache" in argv for argv in builds), builds
    # the prebuild record still reads as one story, in build order (alphabetical
    # within a pass: to_build is sorted)
    assert run.summary["prebuild"]["built"] == ["ai-gateway", "backend", "grafana", "ai-vlm"]


def test_ci_build_and_shared_fake_names_remain_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The fake tier stays as it is (O2.5's own clause, carried through ruling 287):
    # CI builds `hsi-fake-ai:latest` at `up`, fake mode never runs the prebuild
    # (ruling 274's amendment leaves its `up` plain), and nothing on the CI path
    # renames the fake or gets --no-cache. The shared name is CORRECT on CI --
    # one checkout, one job, one engine -- so fake_service_bodies leaves it alone.
    run = fc.Run(
        engine="podman",
        root=tmp_path / "runs",
        image_tag="test",
        mode="fake",
        prod_shape=False,
    )
    run.dir.mkdir(parents=True)
    run.artifacts.mkdir(parents=True)
    run.env_file.write_text("IMAGE_TAG=test\n", encoding="utf-8")
    rendered = {
        "services": {
            "ai-vlm": {
                "image": "hsi-fake-ai:${IMAGE_TAG:-latest}",
                "build": {"context": "/repo", "dockerfile": "docker/fake-ai/Dockerfile"},
            },
            "ai-gateway": {
                "image": "hsi-fake-ai:${IMAGE_TAG:-latest}",
                "build": {"context": "/repo", "dockerfile": "docker/fake-ai/Dockerfile"},
            },
        }
    }
    monkeypatch.setattr(
        fc.Run,
        "compose",
        # Underscore-prefixed names: the file's lambda idiom where the args are
        # deliberately unused (the answered render is closed over).
        lambda _self, _files, *_args, **_kwargs: subprocess.CompletedProcess(
            ["fake"], 0, stdout=json.dumps(rendered), stderr=""
        ),
    )

    bodies = run.fake_service_bodies()

    assert bodies["ai-vlm"]["image"] == "hsi-fake-ai:${IMAGE_TAG:-latest}"
    assert bodies["ai-gateway"]["image"] == "hsi-fake-ai:${IMAGE_TAG:-latest}"
    assert "args" not in bodies["ai-vlm"]["build"]


def test_prebuild_stops_before_the_fakes_when_the_backend_build_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A backend whose build failed cannot base the fakes; a second builder pass
    # on top of a failed first one would fail confusingly (FROM an absent image)
    # and overwrite the artifact with a stream that never mentions the cause.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setattr(fc, "read_subtree_control", lambda: "")
    doc = copy.deepcopy(_PREBUILD_DOC)
    doc["services"]["ai-vlm"] = {
        "image": "hsi-fake-ai:${IMAGE_TAG:-latest}",
        "build": {"context": "/repo", "dockerfile": "docker/fake-ai/Dockerfile"},
    }
    calls = _engine_answers(
        run, doc, monkeypatch, build_rc=1, build_tail="cgroup configuration: permission denied"
    )

    with pytest.raises(fc.HarnessError) as raised:
        run.render(fc.Snapshot.from_engine([], []))
    builds = _verb_calls(calls, "build")
    assert len(builds) == 1, builds
    assert sorted(p for p in builds[0][_last(builds[0], "-f") + 3 :] if p != "--no-cache") == [
        "backend",
        "grafana",
    ]
    assert "--no-cache" in builds[0], builds[0]
    assert "cgroup" in str(raised.value), str(raised.value)


# ---------------------------------------------------------------------------
# [O2.5 venue fixes, ruling 287] the remaining opt-in venue transforms, tested
# at the same two levels as the item-6 probes: the pure boot-document transform
# where the shape alone decides, and render_prod_shape where the venue (a VLM
# present or not) decides who may take which knob.
# ---------------------------------------------------------------------------


def _maui_ruling256() -> dict[str, Any]:
    # The maui venue's prod render, minus the fake-VLM splice: this is the shape
    # whose ai-gateway keeps production's CDI and whose foscam-init carries the
    # writable camera bind. Compose keys are HYPHENATED ("foscam-init"), and
    # _prod_rendered takes service dicts as keyword arguments, so the fixture
    # service is assigned after the doc is built -- a foscam_init kwarg would
    # spell an "foscam_init" key no transform ever reads.
    doc = _prod_rendered(**_ruling256_doc()["services"])
    doc["services"]["foscam-init"] = {"image": "init:test"}
    return doc


def test_keep_id_userns_lands_on_foscam_init_alone_and_the_default_stays_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ruling 287 item 11. The venue requirement is "keep-id for foscam-init":
    # the probe (f4f447) measured the default initializer owning its bind as host
    # UID 100999 and DENIED the run's writer, while keep-id keeps the caller's
    # own UID 1000 and the write succeeds. The knob is opt-in and validated, so
    # an operator's typo must refuse the render rather than boot an initializer
    # that silently reproduces the original denial under a different name.
    with monkeypatch.context() as patch:
        patch.setenv("PROD_SHAPE_INIT_USERNS", "keep-id")
        out = fc.as_prod_shape_deployment(_maui_ruling256(), vlm_url=None)
    assert out["services"]["foscam-init"]["userns_mode"] == "keep-id"
    # foscam-init ONLY: no other service in the whole document changes namespace.
    for name, service in out["services"].items():
        if name != "foscam-init":
            assert "userns_mode" not in service, (name, service.get("userns_mode"))
    # and with nothing set, the default render carries none: the authored
    # override's policy (three kinds of key change, ruling 162 item 3) intact.
    default = fc.as_prod_shape_deployment(_maui_ruling256(), vlm_url=None)
    assert "userns_mode" not in default["services"]["foscam-init"]


def test_a_userns_value_other_than_keep_id_is_refused_by_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # keep-id is the one value the venue requirement names. "host" would put the
    # initializer in the HOST namespace (the preflight refuses that shape for the
    # CI stack; the prod shape's in-run check must not inherit it either), and an
    # unvalidated free-form value lets a future engine spelling boot unnoticed.
    with monkeypatch.context() as patch:
        patch.setenv("PROD_SHAPE_INIT_USERNS", "host")
        with pytest.raises(fc.HarnessError, match="PROD_SHAPE_INIT_USERNS"):
            fc.as_prod_shape_deployment(_maui_ruling256(), vlm_url=None)


def test_a_missing_foscam_init_refuses_the_userns_transform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The knob names one service. A render without it must refuse at render
    # time with a message that says WHICH key was missing, not KeyError three
    # frames into the transform.
    with monkeypatch.context() as patch:
        patch.setenv("PROD_SHAPE_INIT_USERNS", "keep-id")
        with pytest.raises(fc.HarnessError, match="foscam-init"):
            fc.as_prod_shape_deployment(
                _prod_rendered(**_ruling256_doc()["services"]), vlm_url=None
            )


@pytest.mark.parametrize("failed", [False, True])
def test_provisional_gpu_history_fixture_restores_only_its_rows_on_any_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed: bool
) -> None:
    # Ruling 287 item 10's F-182 half. The fixture is PROVISIONAL: golden() only
    # seeds it under PROD_SHAPE_GPU_HISTORY_FIXTURE=1, and the restore must run
    # on ANY exit -- a golden leg that raises is exactly when a leak would hide.
    # Both legs must monkeypatch cleanly (the DB is never touched here) and the
    # two legs must see the SAME two UUIDs, so "delete exactly those" deletes
    # what was seeded, not a second pair minted after the leg.
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    monkeypatch.setenv("PROD_SHAPE_GPU_HISTORY_FIXTURE", "1")
    calls = []

    def fixture(ids: list[str], *, restore: bool) -> None:
        calls.append((ids, restore))

    def leg() -> list[str]:
        if failed:
            raise fc.HarnessError("golden failed")
        return []

    monkeypatch.setattr(run, "_gpu_history_fixture", fixture)
    monkeypatch.setattr(run, "_golden", leg)
    if failed:
        with pytest.raises(fc.HarnessError, match="golden failed"):
            run.golden()
    else:
        assert run.golden() == []
    assert len(calls) == 2
    assert calls[0][0] == calls[1][0]
    assert len(set(calls[0][0])) == 2
    assert [call[1] for call in calls] == [False, True]


def test_the_triton_base_argument_reaches_the_real_gateway_build_only_on_maui(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Ruling 287 item 7's harness half: the venue overrides the gateway base with
    # --build-arg TRITON_IMAGE=... (26.09 arm64 by digest, because 26.01's CUDA
    # code fails on the GB300). The override can only reach a BUILD, and only the
    # maui venue keeps the real gateway (ruling 256 item 2) -- the sandbox run
    # splices the fake, whose build is the fake Dockerfile. The maui real gateway
    # is an IMAGE-LESS build service (docker-compose.prod.yml spells build.context
    # + build.dockerfile, no image), which is the shape the knob reads.
    doc = _maui_ruling256()
    doc["services"]["ai-gateway"] = {
        "build": {"context": ".", "dockerfile": "ai/gateway/Dockerfile"}
    }
    with monkeypatch.context() as patch:
        patch.setenv("PROD_SHAPE_TRITON_IMAGE", "nvcr.io/nvidia/tritonserver@sha256:abc123")
        out = fc.as_prod_shape_deployment(doc, vlm_url=None)
    args = out["services"]["ai-gateway"]["build"]["args"]
    assert args["TRITON_IMAGE"] == "nvcr.io/nvidia/tritonserver@sha256:abc123"
    # nothing else gained a build.args entry (the fake splices below carry their
    # own BACKEND_IMAGE, set in fake_service_bodies, not here)
    for name, service in out["services"].items():
        if name != "ai-gateway":
            assert "args" not in (service.get("build") or {}), name


def test_a_triton_base_override_is_refused_on_the_sandbox_venue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The sandbox run replaced the real gateway with the CI fake; a build-arg for
    # a build that never runs would silently witness the wrong deployment -- the
    # exact failure shape ruling 256's refusal of cross-venue transforms exists
    # for. The refusal is at render time, by the venue's own name.
    with monkeypatch.context() as patch:
        patch.setenv("PROD_SHAPE_TRITON_IMAGE", "nvcr.io/nvidia/tritonserver@sha256:abc123")
        with pytest.raises(fc.HarnessError, match="real-gateway"):
            fc.as_prod_shape_deployment(
                _maui_ruling256(),
                vlm_url="http://10.0.0.5:8123",
                fake_gateway=_fake_gateway_body(),
            )


def test_gpu_ai_services_pins_the_backend_devices_env_only_on_maui(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ruling 287 item 2's last row: Podman's compatibility API may ignore the
    # deploy DeviceRequests prod carries, so the venue's explicit GPU choice
    # must ALSO reach the backend as NVIDIA_VISIBLE_DEVICES -- the env the
    # NVIDIA runtime itself honours. maui-only, like the base override: the
    # sandbox backend has its reservation stripped and no GPU at all.
    with monkeypatch.context() as patch:
        patch.setenv("GPU_AI_SERVICES", "0")
        out = fc.as_prod_shape_deployment(_maui_ruling256(), vlm_url=None)
    assert out["services"]["backend"]["environment"]["NVIDIA_VISIBLE_DEVICES"] == "0"
    # the deploy reservation prod spells stays: the env ADDS the explicit pin,
    # it does not replace prod's own wiring
    resources = out["services"]["backend"]["deploy"]["resources"]
    assert resources["reservations"]["devices"], "the maui reservation must survive"


def test_gpu_ai_services_absent_or_empty_leaves_the_backend_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An empty string is "unset" for this knob (the venue shell may export it
    # blank), and the sandbox venue never takes it: fake_gateway present is
    # refused for the build-arg knob but the GPU env knob must simply not fire.
    baseline = fc.as_prod_shape_deployment(_maui_ruling256(), vlm_url=None)
    with monkeypatch.context() as patch:
        patch.setenv("GPU_AI_SERVICES", "")
        out = fc.as_prod_shape_deployment(_maui_ruling256(), vlm_url=None)
    assert "NVIDIA_VISIBLE_DEVICES" not in out["services"]["backend"]["environment"]
    assert "NVIDIA_VISIBLE_DEVICES" not in baseline["services"]["backend"]["environment"]
    # and the sandbox venue: its backend keeps no GPU wiring at all
    with monkeypatch.context() as patch:
        patch.setenv("GPU_AI_SERVICES", "0")
        sandbox = fc.as_prod_shape_deployment(
            _maui_ruling256(),
            vlm_url="http://10.0.0.5:8123",
            fake_gateway=_fake_gateway_body(),
        )
    assert "NVIDIA_VISIBLE_DEVICES" not in sandbox["services"]["backend"]["environment"]
    assert "NVIDIA_VISIBLE_DEVICES" not in baseline["services"]["backend"]["environment"]


def test_ci_golden_keeps_the_authored_fake_scenario_book(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The CI leg is unchanged (ruling 287: "Defaults ... and CI's behaviour stay
    # unchanged"). With neither prod-shape knob set, golden() must reach _golden()
    # untouched: the authored scenario book stays FEATURE_CHECK_SCENARIOS's value.
    # Item 14's native-capture machinery ([r287b]) is not in this correction, so
    # there is no golden_scenarios attribute and nothing substitutes the book --
    # asserted by absence of the attribute, not by a monkeypatched forbidden call
    # (the method itself is out of scope; asserting on its absence would be
    # inventing a surface this diff does not ship).
    run = _prod_run(tmp_path, monkeypatch, socket=_ENGINE_SOCKET)
    run.prod_shape = False
    monkeypatch.delenv("PROD_SHAPE_GPU_HISTORY_FIXTURE", raising=False)
    monkeypatch.setattr(run, "_golden", lambda: ["original CI golden leg"])
    assert run.golden() == ["original CI golden leg"]
    assert not hasattr(run, "golden_scenarios")


# ---------------------------------------------------------------------------
# [O2.5 venue fixes, ruling 287] the in-run isolation check on the prod shape:
# it reuses the render's OWN socket policy (the same engine_socket_mounts the
# render's UR-134 re-check runs) instead of the CI tier's root-directory ban,
# which mistakenly flags node-exporter's read-only /:/host:ro observer bind.
# CI's check keeps its exact behavior (ruling 287 item 12).
# ---------------------------------------------------------------------------


def _inspect_of(*mounts: tuple[str, str, bool]) -> list[dict[str, Any]]:
    """One container's inspect, as the backend/MAUI stack would answer it."""
    return [
        {
            "Name": f"/{PROJECT}-backend-1",
            "Id": "fixture",
            "State": {"Status": "running", "StartedAt": "2026-01-01T00:00:00Z"},
            "Config": {"Labels": {fc.PROJECT_LABEL: PROJECT}},
            "NetworkSettings": {"Ports": {}},
            "Mounts": [
                {"Type": "bind", "Source": src, "Destination": dst, "RW": rw}
                for (src, dst, rw) in mounts
            ],
        }
    ]


def test_the_prod_shape_in_run_check_uses_the_render_socket_policy() -> None:
    # node-exporter binds /:/host read-only (docker-compose.prod.yml:1450) and
    # alloy reads /sys,/proc: the render's UR-134 re-check accepts those (they
    # name no engine socket and no socket path), so the in-run check must accept
    # the BOOTS it allowed. is_engine_socket("/" or "/var") is True by design for
    # the CI preflight -- a writable host root is the whole machine -- so the old
    # per-mount check here reddened every maui run on an observer bind.
    containers = _inspect_of(("/", "/host", False), ("/run/user/1000/netns", "/netns", False))
    assert (
        fc.in_run_check(
            containers,
            orchestrator_enabled=False,
            services=NO_ORCHESTRATOR,
            prod_shape_socket=_ENGINE_SOCKET,
        )
        == []
    )


def test_the_prod_shape_in_run_check_still_rejects_a_real_engine_socket() -> None:
    # Item 12 does NOT skip isolation checking: a socket mount whose source is
    # the caller's PODMAN_SOCKET is refused on the prod shape exactly as the
    # render refuses one in its boot document, and the conventional targets
    # (/var/run/podman/podman.sock etc.) stay refused whatever the source is.
    containers = _inspect_of((_ENGINE_SOCKET, "/var/run/podman/podman.sock", False))
    _one_problem(
        fc.in_run_check(
            containers,
            orchestrator_enabled=False,
            services=NO_ORCHESTRATOR,
            prod_shape_socket=_ENGINE_SOCKET,
        ),
        "engine socket",
    )
    containers2 = _inspect_of(("/somewhere/else.sock", "/var/run/docker.sock", False))
    _one_problem(
        fc.in_run_check(
            containers2,
            orchestrator_enabled=False,
            services=NO_ORCHESTRATOR,
            prod_shape_socket=_ENGINE_SOCKET,
        ),
        "engine socket",
    )


def test_the_prod_shape_in_run_check_rejects_a_writable_host_root() -> None:
    # The read-only observer is the deliberate shape; a WRITABLE bind of / or
    # /var is the machine itself -- the check must still name it, on the prod
    # shape as on CI.
    containers = _inspect_of(("/", "/host", True))
    _one_problem(
        fc.in_run_check(
            containers,
            orchestrator_enabled=False,
            services=NO_ORCHESTRATOR,
            prod_shape_socket=_ENGINE_SOCKET,
        ),
        "engine socket",
    )


def test_the_ci_in_run_check_keeps_its_root_ban_with_no_prod_shape_socket() -> None:
    # CI behavior retained (ruling 287 item 12): the per-mount check on
    # is_engine_socket flags / and /var on the CI tier exactly as before -- the
    # prod-shape policy is opt-in through the new parameter, never a default.
    containers = _inspect_of(("/", "/host", False))
    _one_problem(
        fc.in_run_check(containers, orchestrator_enabled=False, services=NO_ORCHESTRATOR),
        "engine socket",
    )


def test_the_prod_shape_run_wires_its_socket_into_the_in_run_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The wiring, not just the policy: check_isolation passes the caller's
    # PODMAN_SOCKET only under --prod-shape, so a CI run can never take the
    # prod-shape branch through a leaked variable.
    seen: dict[str, Any] = {}

    def fake_in_run_check(containers: Any, **kwargs: Any) -> list[str]:
        seen.update(kwargs)
        return []

    monkeypatch.setattr(fc, "in_run_check", fake_in_run_check)
    # check_isolation reads the socket from the environment, so the prod run
    # needs the variable set -- exactly what _prod_run does for its own tests.
    monkeypatch.setenv("PODMAN_SOCKET", _ENGINE_SOCKET)
    monkeypatch.setattr(
        fc.Run,
        "_run",
        lambda *_, **__: subprocess.CompletedProcess([], 0, "", ""),
    )
    monkeypatch.setattr(
        fc.Run, "deployment", lambda *_, **__: subprocess.CompletedProcess([], 0, "False\n", "")
    )
    monkeypatch.setattr(fc, "_http", lambda *_, **__: (503, {"detail": fc.ORCHESTRATOR_ABSENT}))

    prod = fc.Run(
        engine="podman", root=tmp_path / "a", image_tag="test", mode="real", prod_shape=True
    )
    # self.api is set by up(); the wiring test drives check_isolation alone.
    prod.api = "http://127.0.0.1:1"
    prod.check_isolation()
    assert seen["prod_shape_socket"] == _ENGINE_SOCKET, seen

    seen.clear()
    ci = fc.Run(engine="podman", root=tmp_path / "b", image_tag="test", mode="real")
    ci.api = "http://127.0.0.1:1"
    ci.check_isolation()
    assert seen["prod_shape_socket"] is None, seen
