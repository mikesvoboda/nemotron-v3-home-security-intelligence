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
    """A VLM the stand-in agent-gpu has started (and so lists on ps)."""
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
    assert kwargs["timeout"] == 1800, "a golden suite is minutes, not the 300 s default"


def test_the_container_gets_environment_names_never_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
