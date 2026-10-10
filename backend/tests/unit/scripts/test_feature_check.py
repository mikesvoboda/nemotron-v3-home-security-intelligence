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
# the names `run` started until `rm` removes them, and lists them on `ps`.
AGENT_GPU_STUB = """#!/usr/bin/env python3
import json, os, sys
log = os.environ["AGENT_GPU_STUB_LOG"]
state = log + ".running"
with open(log, "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
names = open(state).read().split() if os.path.exists(state) else []
verb = sys.argv[1]
if verb == "run":
    name = sys.argv[sys.argv.index("--name") + 1]
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
    runbook = (REPO_ROOT / "docs" / "uplevel" / "operator.md").read_text(encoding="utf-8")
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
        vlm = fc.AgentGpu(_run(tmp_path))
        vlm.url, vlm.host_port = VLM_URL, 18123
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
        vlm = fc.AgentGpu(_run(tmp_path))
        vlm.url, vlm.host_port = VLM_URL, 18123
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
        f"{run.project}-vlm",
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
    name = f"{summary['project']}-vlm"
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
    assert f"{summary['project']}-vlm" in problem


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
# The summary the operator posts (30-ops.md §O2.2: the preflight snapshot and
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


# ---------------------------------------------------------------------------
# The second self-review's findings (the --real diff), each reproduced here
# ---------------------------------------------------------------------------


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
    name = f"{_real_summary(tmp_path / 'runs')['project']}-vlm"
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
