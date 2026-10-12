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


def test_the_browser_steps_see_the_browsers_path_and_nothing_else() -> None:
    """R116's env rule, pinned directly: the browser probe and install get
    compose's engine view PLUS the variables the golden TEST leg would otherwise
    disagree with (a moved cache changes where the runner launches), and still
    never the run env's credential or the run's own paths. An exact dict, so a
    future key added to either list is a decision made here — which is why
    XDG_CACHE_HOME appears in both the list and this dict: it moves the same
    root and is read at launch, so leaving it out is the divergence one variable
    away from the one already fixed."""
    caller = {
        "PATH": "/usr/bin",
        "HOME": "/home/agent",
        "DOCKER_HOST": "unix:///run/docker.sock",
        "PLAYWRIGHT_BROWSERS_PATH": "/mnt/big/ms-playwright",
        "XDG_CACHE_HOME": "/mnt/big",
        "FEATURE_CHECK_ADMIN_PASSWORD": "hunter2",  # pragma: allowlist secret
        "FEATURE_CHECK_API_URL": "http://api.invalid",
        "IMAGE_TAG": "leaked",
    }
    assert fc.browser_environment(caller) == {
        "PATH": "/usr/bin",
        "HOME": "/home/agent",
        "DOCKER_HOST": "unix:///run/docker.sock",
        "PLAYWRIGHT_BROWSERS_PATH": "/mnt/big/ms-playwright",
        "XDG_CACHE_HOME": "/mnt/big",
    }
    # Absent in the caller, absent from the child: the default root then holds,
    # and the dry-run plan says so — nothing is invented here.
    assert fc.browser_environment({"PATH": "/usr/bin", "HOME": "/home/agent"}) == {
        "PATH": "/usr/bin",
        "HOME": "/home/agent",
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


# --- flaky-blindness (ruling 116 posture: the harness names the state it cannot see) ------------
#
# `junit_results` is the instrument lanes quote for "what did CI call this spec?" It is not a
# record of what happened: Playwright collapses retries before a row exists, and the reporter
# emits no marker at all for one real trajectory. These three tests are red-first pins written
# against reports taken from CI's own `feature-check` artifacts, not from invented XML.


WS_STATUS = "../golden/shell/ws-status.spec.ts"
WS_F007 = "golden path: WebSocket status and disconnect banner @critical \u203a F-007"


def _junit(tmp_path: Path, body: str, suite_attrs: str = "", root_attrs: str = "") -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "golden.xml"
    path.write_text(
        f'<?xml version="1.0"?><testsuites{root_attrs}><testsuite name="golden"{suite_attrs}>'
        f"{body}</testsuite></testsuites>",
        encoding="utf-8",
    )
    return path


def test_a_spec_that_struck_then_runtime_skipped_is_flaky(tmp_path: Path) -> None:
    """Owner ruling 126: a failed attempt followed by a self-skip is **flaky**.

    Observed live, same spec, in CI artifacts `11721450798` and `11718785897`: the partition
    guard in `ws-status.spec.ts` skips at runtime when the host never tears the socket down
    (ruling 86), and the vendored reporter only emits `<skipped>` for an `outcome()` of
    `"skipped"` \u2014 which a fail-then-skip trajectory is not. The skip therefore lands in
    `<properties>`. Owner ruling 126 (`#6854` `6116438330`) names this fixture explicitly:
    "any spec with a failed attempt is recorded as `flaky`, whatever its final outcome" \u2014
    so the property-without-element trajectory that my first cut called `skipped` is
    `flaky` under the owner's semantics: the property is the reporter's own trace that an
    attempt failed, and hiding that behind `skipped` still buries the strike.
    """
    junit = _junit(
        tmp_path,
        f'<testcase classname="{WS_STATUS}" name="{WS_F007}" time="81.64">'
        "<properties>"
        '<property name="skip" value="setOffline(true) never surfaced on the established '
        'loopback WebSockets within 15 s; ruling 86: the leg is unexecutable here, not failed"/>'
        "</properties>"
        "<system-out>the struck attempt was collapsed by the reporter</system-out>"
        "</testcase>",
    )
    assert fc.junit_results(junit) == {f"{WS_STATUS}::{WS_F007}": "flaky"}


def test_a_spec_that_struck_then_passed_is_flaky_not_passed(tmp_path: Path) -> None:
    """Ruling 126's second named fixture: fail-then-PASS maps to `flaky` too.

    FE-2's F-040 row is the production shape (#7014 `6116330046`, run `38189450762`): one
    row, no outcome element, a retained screenshot naming the failed first attempt. Before
    ruling 126 this map filed it `passed`; the owner's rule \u2014 passed ONLY if the final
    attempt passed and was not skipped, any failed attempt \u21d2 flaky \u2014 reads the retained
    artifact as what it is: proof an attempt went red. This is the shape the coordinator's
    dispatch assumed "junit can't see"; the artifact channel sees it, measured 6/6 real
    reports against the console.
    """
    junit = _junit(
        tmp_path,
        f'<testcase classname="{WS_STATUS}" name="{WS_F007}"><system-out>'
        "[[ATTACHMENT|golden-playwright/ws-status-f007-golden/test-failed-1.png]]"
        "</system-out></testcase>",
    )
    assert fc.junit_results(junit) == {f"{WS_STATUS}::{WS_F007}": "flaky"}


def test_a_true_skip_stays_skipped_under_the_flaky_rule(tmp_path: Path) -> None:
    """The retarget's boundary witness: NO failed attempt \u21d2 no `flaky`.

    A true whole-spec skip carries the `<skipped>` element AND the skip property (measured
    census \u2014 it is the property WITHOUT the element that marks a collapsed failed attempt).
    Ruling 126 promotes rows that had a failed attempt; a leg that never struck and never
    ran is `skipped`, which is exactly the outcome the owner's first clause distinguishes
    ("passed only if \u2026 not skipped"). Without this pin, a retarget could swallow every
    skip into flaky and still pass the two fixtures above.
    """
    junit = _junit(
        tmp_path,
        f'<testcase classname="{WS_STATUS}" name="{WS_F007}"><properties>'
        '<property name="skip" value="skipped by config"/></properties><skipped/>'
        "</testcase>",
    )
    assert fc.junit_results(junit) == {f"{WS_STATUS}::{WS_F007}": "skipped"}
    # The element-present skip that ALSO retains a failed-attempt artifact is
    # flaky, not skipped: ruling 126's "any failed attempt" clause outranks the
    # final outcome, which is what "whatever its final outcome" is for. Today's
    # reporter collapses this trajectory into the property-only row above, so
    # this half is a decision made in advance, like the worst-wins fold.
    struck_then_skipped = _junit(
        tmp_path.parent / "struck-then-skipped",
        f'<testcase classname="{WS_STATUS}" name="{WS_F007}"><properties>'
        '<property name="skip" value="skipped by config"/></properties><skipped/>'
        "<system-out><![CDATA["
        "[[ATTACHMENT|golden-playwright/ws-status-f007-golden/test-failed-1.png]]"
        "]]></system-out></testcase>",
    )
    assert fc.junit_results(struck_then_skipped) == {f"{WS_STATUS}::{WS_F007}": "flaky"}


def test_a_leg_that_failed_every_attempt_stays_failed_not_flaky(tmp_path: Path) -> None:
    """`failed` is not consumed by `flaky`: a red final attempt still reads `failed`.

    Ruling 126's literal tail \u2014 "any failed attempt \u21d2 flaky, whatever
    its outcome" \u2014 could also be read to relabel a leg that failed EVERY
    attempt (rate-limit's 3-strike legs in the real reports). This pin holds
    the reading consistent with the ruling's own "Why"
    (the defect is a struck leg recorded as *passed*): a leg whose final attempt went red
    keeps the verdict the gate and every lane already key on, and the extra strikes it
    carried stay countable in `junit_strikes`. The edge is flagged to the owner; if they
    meant the literal reading, this fixture flips and nothing else moves.
    """
    junit = _junit(
        tmp_path,
        f'<testcase classname="{WS_STATUS}" name="{WS_F007}">'
        "<system-out><![CDATA["
        "[[ATTACHMENT|golden-playwright/rate-limit-f007-golden/test-failed-1.png]]\n"
        "[[ATTACHMENT|golden-playwright/rate-limit-f007-golden-retry1/test-failed-1.png]]\n"
        "]]></system-out>"
        '<failure message="attempt 2 red too"/>'
        "</testcase>",
    )
    assert fc.junit_results(junit) == {f"{WS_STATUS}::{WS_F007}": "failed"}, (
        "a red final attempt must not be relabelled flaky"
    )
    assert fc.junit_strikes(junit) == {f"{WS_STATUS}::{WS_F007}": 2}


def test_repeat_rows_fold_flaky_over_a_later_clean_pass(tmp_path: Path) -> None:
    """With `flaky` in the codomain the worst-wins rank must order it correctly.

    A struck row and a later clean row for one spec fold to `flaky`, not `passed` \u2014 the
    rank table, not document order, decides.
    """
    junit = _junit(
        tmp_path,
        _struck_row(WS_STATUS, WS_F007, (("f007-golden", FAILED_ATTEMPT),))
        + f'<testcase classname="{WS_STATUS}" name="{WS_F007}"/>',
    )
    assert fc.junit_results(junit) == {f"{WS_STATUS}::{WS_F007}": "flaky"}


def test_repeated_rows_for_one_spec_never_yield_a_milder_verdict_than_the_worst(
    tmp_path: Path,
) -> None:
    """If a reporter ever emits one row per attempt, the map must not keep the last one.

    **Latent, not observed:** both CI reports inspected hold one row per spec (71 rows / 71
    names; 101 / 101), so today nothing reaches this branch \u2014 the current code passes it by
    accident only in the orderings where the last row is also the worst. The fragility is in the
    code, not in today's input: `results[name] = ...` is a per-row assignment whose tie-break is
    document order, and a reporter bump that starts emitting `<testcase>` per attempt would turn
    it into silent flaky-green. Pinned so the day the rows appear, the verdict is a decision.
    """
    junit = _junit(
        tmp_path,
        f'<testcase classname="{WS_STATUS}" name="{WS_F007}"><failure message="attempt 1"/></testcase>'
        f'<testcase classname="{WS_STATUS}" name="{WS_F007}"></testcase>',
    )
    assert fc.junit_results(junit) == {f"{WS_STATUS}::{WS_F007}": "failed"}, (
        "last-wins dropped the failure"
    )
    retry_dir = tmp_path / "retry2"
    retry_dir.mkdir()
    junit2 = _junit(
        retry_dir,
        f'<testcase classname="{WS_STATUS}" name="{WS_F007}"></testcase>'
        f'<testcase classname="{WS_STATUS}" name="{WS_F007}"><failure message="attempt 2"/></testcase>',
    )
    assert fc.junit_results(junit2) == {f"{WS_STATUS}::{WS_F007}": "failed"}


def test_the_spec_map_never_disagrees_with_the_report_sown_totals(tmp_path: Path) -> None:
    """A map whose tally drifts from the report's own counts means the parser missed rows.

    This is a **drift alarm, not a flakiness detector**, and it is deliberately labelled so: the
    suite attributes are final-outcome, so they *agree* even on the reports that carry the
    fail-then-skip mislabel above. What it does catch is the silent failure mode that a regex
    parser has and an XML parser does not \u2014 a row shape it cannot read is dropped without an
    error, and a smaller-but-plausible total is the only symptom.
    """
    junit = _junit(
        tmp_path,
        f'<testcase classname="{WS_STATUS}" name="one"/>'
        f'<testcase classname="{WS_STATUS}" name="two"><failure message="boom"/></testcase>'
        f'<testcase classname="{WS_STATUS}" name="three"><skipped/></testcase>',
        suite_attrs=' tests="3" failures="1" skipped="1" errors="0"',
    )
    verdicts = fc.junit_results(junit)
    totals = fc.junit_totals(junit)
    assert totals == {"tests": 3, "failed": 1, "skipped": 1}
    assert {k: sum(1 for v in verdicts.values() if v == k) for k in ("failed", "skipped")} == {
        "failed": totals["failed"],
        "skipped": totals["skipped"],
    }
    assert len(verdicts) == totals["tests"]


def test_the_drift_alarm_fires_only_when_rows_or_failures_cannot_be_reconciled(
    tmp_path: Path,
) -> None:
    """A positive witness that the alarm CAN fire, on each of its two checks.

    Pinned as a pair with the clean-report test below so the alarm is proven to
    have teeth and to have limits — an alarm that silently returned ``[]`` for
    every input would pass the "green reports stay green" pin vacuously.
    """
    dropped = _junit(
        tmp_path,
        f'<testcase classname="{WS_STATUS}" name="one"/>',
        suite_attrs=' tests="3" failures="0" skipped="0"',
    )
    _one_problem(
        fc.junit_drift_problems("golden", dropped), "declares 3 tests", "only 1", "dropped"
    )

    miscounted = _junit(
        tmp_path.parent / "miscounted",
        f'<testcase classname="{WS_STATUS}" name="one"/>'
        f'<testcase classname="{WS_STATUS}" name="two"/>',
        suite_attrs=' tests="2" failures="1" skipped="0"',
    )
    _one_problem(
        fc.junit_drift_problems("golden", miscounted), "declares 1 failures", "0 rows carry"
    )


def test_the_drift_alarm_stays_silent_on_the_shapes_the_parser_handles_well(
    tmp_path: Path,
) -> None:
    """Two reports that a naive reconciliation would cry wolf on; both are clean.

    These are the traps the alarm's two checks are written to avoid:

    - **the worst-wins fold.** Repeat rows for one spec collapse to fewer
      verdicts than the report holds rows; the row check must count raw
      ``<testcase>`` rows, not ``len(results)``, or the day a reporter emits
      per-attempt rows the alarm would red a report it parsed correctly.
    - **a spec that prints its own verdict.** A passing spec's ``<system-out>``
      may contain the literal text ``<failure``; counting failure markers over
      the raw document (instead of per row body, CDATA stripped, exactly as
      ``junit_results`` does) would read that printed string as a failure.
    """
    folded = _junit(
        tmp_path,
        f'<testcase classname="{WS_STATUS}" name="{WS_F007}"><failure message="attempt 1"/></testcase>'
        f'<testcase classname="{WS_STATUS}" name="{WS_F007}"></testcase>',
        suite_attrs=' tests="2" failures="1" skipped="0"',
    )
    assert len(fc.junit_results(folded)) == 1, "the two rows must fold to one verdict"
    assert fc.junit_drift_problems("golden", folded) == []

    printing = _junit(
        tmp_path.parent / "printing",
        f'<testcase classname="{WS_STATUS}" name="one"><system-out>'
        f"<![CDATA[a spec that prints the string <failure in its own output]]></system-out>"
        f"</testcase>",
        suite_attrs=' tests="1" failures="0" skipped="0"',
    )
    assert fc.junit_results(printing) == {f"{WS_STATUS}::one": "passed"}
    assert fc.junit_drift_problems("golden", printing) == []


# The reporter prints each retained artifact as ``[[ATTACHMENT|<path>]]`` inside
# the row's ``<system-out>`` CDATA (measured verbatim in CI artifact
# 11721450798). The golden project's config retains a screenshot + video +
# error-context for every FAILED attempt and a trace for the first retry, so the
# failure-bearing dirs are the countable record of strikes. These spell exactly
# that shape; nothing here is invented.
FAILED_ATTEMPT = ("test-failed-1.png", "video.webm", "error-context.md")
RETRY_TRACE_ONLY = ("trace.zip",)


def _struck_row(
    classname: str, name: str, attempts: tuple[tuple[str, tuple[str, ...]], ...]
) -> str:
    """One ``<testcase>`` whose ``<system-out>`` lists ``attempts``' artifacts.

    ``attempts`` is ``(artifact-directory, file-names)`` per retained folder, in
    the reporter's own path layout ``golden-playwright/<dir>/<file>``.
    """
    refs = "".join(
        f"[[ATTACHMENT|golden-playwright/{directory}/{artifact}]]\n"
        for directory, artifacts in attempts
        for artifact in artifacts
    )
    return (
        f'<testcase classname="{classname}" name="{name}"><system-out><![CDATA[\n'
        f"{refs}]]></system-out></testcase>"
    )


def test_a_struck_then_recovered_spec_is_flaky_and_counted_as_struck(
    tmp_path: Path,
) -> None:
    """Ruling 126's shape in one row: verdict `flaky`, strike count 1.

    The row the console would show as one ``✘`` then a green retry. Under the owner's
    semantics the verdict itself is now ``flaky`` (the retained screenshot proves the red
    attempt), and the strike stays countable in its own map — the two views answer
    different questions: 126 says WHICH SPECS were struck, ``junit_strikes`` says HOW
    OFTEN. Two clauses ride on the count being exactly 1, not 2: the ``-retry1`` directory
    is named ONLY a ``trace.zip`` (``trace: 'on-first-retry'`` marks a retry, not a second
    failure), so a naive one-artifact-per-directory count would over-read two strikes.
    """
    junit = _junit(
        tmp_path,
        _struck_row(
            WS_STATUS,
            WS_F007,
            (
                ("ws-status-ws-status-f007-golden", FAILED_ATTEMPT),
                ("ws-status-ws-status-f007-golden-retry1", RETRY_TRACE_ONLY),
            ),
        ),
    )
    assert fc.junit_results(junit) == {f"{WS_STATUS}::{WS_F007}": "flaky"}, (
        "ruling 126: a retained failed-attempt artifact makes the spec flaky, not passed"
    )
    assert fc.junit_strikes(junit) == {f"{WS_STATUS}::{WS_F007}": 1}, (
        "a trace-only retry directory is not a second strike"
    )


def test_the_strike_count_tracks_the_number_of_failure_bearing_attempts(tmp_path: Path) -> None:
    """A three-attempt leg counts three, matching the console's three ✘ lines.

    The rate-limit leg in the real reports strikes three times before recovering;
    each strike retains its own screenshot, so the count is the failed-attempt
    count row for row. Measured against the console 6/6 real reports; pinned here
    on a synthesized three-failure row.
    """
    junit = _junit(
        tmp_path,
        _struck_row(
            WS_STATUS,
            WS_F007,
            tuple(
                (f"rate-limit-f007-golden{'' if i == 0 else f'-retry{i}'}", FAILED_ATTEMPT)
                for i in range(3)
            ),
        ),
    )
    assert fc.junit_strikes(junit) == {f"{WS_STATUS}::{WS_F007}": 3}


def test_a_retry_dir_holding_only_a_trace_is_not_counted_as_a_strike(tmp_path: Path) -> None:
    """A spec retried by policy that never failed twice adds nothing.

    ``trace: 'on-first-retry'`` writes a trace whenever an attempt is retried,
    including the one that then passed. If the count keyed on any directory, a
    single legitimate retry would inflate a clean spec to one strike. This is the
    negative witness paired with the two positive counts above.
    """
    junit = _junit(
        tmp_path,
        _struck_row(
            WS_STATUS,
            WS_F007,
            (("ws-status-f007-golden-retry1", RETRY_TRACE_ONLY),),
        ),
    )
    assert fc.junit_strikes(junit) == {}


def test_a_clean_spec_carries_no_strikes(tmp_path: Path) -> None:
    """The empty case: a passed spec that never struck names no artifacts."""
    junit = _junit(tmp_path, f'<testcase classname="{WS_STATUS}" name="{WS_F007}"/>')
    assert fc.junit_strikes(junit) == {}


def test_the_strikes_are_reported_as_summary_data_not_a_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``golden()`` records strikes but does not fail on them.

    This is the load-bearing choice, not a detail. r116's posture is that
    flaky-green is *handled where it is recoverable*, and the strikes are now
    recoverable from the report itself — but turning them into a gate would make
    a spec that struck-then-recovered redden CI, which is a policy change the
    coordinator has not ruled on (and would reset a queued PR's position for a
    new class of red). So the strike map is written to ``summary`` as evidence a
    lane can quote, while ``golden()`` still returns ``[]``. The positive half
    (the map is populated) and the negative half (the return stays empty) are
    both asserted, or the wiring could be a gate in disguise.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    leg = tmp_path / "struck"
    leg.mkdir()
    run = _golden_only_run(leg, monkeypatch, True, calls)
    xml = (
        '<testsuites><testsuite name="golden" tests="1" failures="0" skipped="0">'
        + _struck_row(
            WS_STATUS,
            WS_F007,
            (("ws-status-f007-golden", FAILED_ATTEMPT),),
        )
        + "</testsuite></testsuites>"
    )
    (run.artifacts / "golden-playwright.xml").write_text(xml, encoding="utf-8")
    problems = run.golden()
    assert problems == [], "a strike must not become a gate consequence"
    strikes = run.summary["results"]["golden"]["playwright_strikes"]
    assert strikes == {f"{WS_STATUS}::{WS_F007}": 1}, (
        "the strike map must actually reach the summary, not be dead code"
    )


def test_the_golden_step_reports_junit_drift_as_a_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The alarm is wired into ``golden()``'s ``problems`` channel, not dead code.

    The same Playwright leg, twice: a report the parser cannot reconcile makes
    ``golden()`` name it, a consistent one leaves the step green. Without the
    positive half the wiring could be missing and only the unit-level alarm
    tests would pass.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    legs = {"drifting": tmp_path / "drifting", "consistent": tmp_path / "consistent"}

    def golden_with(xml: str, leg: str) -> list[str]:
        # A fresh tmp_path per leg: fc.Run creates its artifact dir, and the
        # harness's own state (config text, module dirs) is per-run.
        legs[leg].mkdir()
        run = _golden_only_run(legs[leg], monkeypatch, True, calls)
        (run.artifacts / "golden-playwright.xml").write_text(xml, encoding="utf-8")
        return run.golden()

    drifting = golden_with(
        '<testsuites><testsuite name="golden" tests="2" failures="0" skipped="0">'
        f'<testcase classname="{WS_STATUS}" name="one"/></testsuite></testsuites>',
        "drifting",
    )
    _one_problem(drifting, "Playwright", "declares 2 tests", "dropped")

    calls.clear()
    consistent = golden_with(
        '<testsuites><testsuite name="golden" tests="1" failures="0" skipped="0">'
        f'<testcase classname="{WS_STATUS}" name="one"/></testsuite></testsuites>',
        "consistent",
    )
    assert consistent == []


BROWSER_INSTALL = ["npx", "playwright", "install", "chromium"]


def _seed_runner_cli(modules: Path) -> None:
    """Make a fake node_modules hold a LOCK-RESOLVED playwright CLI, which is
    the fact the r116 browser block gates on: `npx playwright` only resolves to
    the build the lock wants (v1243) when the locked package is importable. A
    bare node_modules without it would send npx to the LATEST package — a
    different build (v1248, measured) — so the CLI, not the directory, is the
    right gate. Real `npm ci` leaves this file; so does the fake."""
    (modules / ".bin").mkdir(parents=True, exist_ok=True)
    (modules / ".bin" / "playwright").write_text("#!/bin/sh\n", encoding="utf-8")


# Playwright 1.63.0's real `install --dry-run chromium` output on this sandbox
# (linux/arm64), paths rewritten to tmp_path. The golden-project spec set boots
# devices['Desktop Chrome'], which launches the HEADLESS SHELL, so the
# chromium_headless_shell line is the one whose absence killed the operator's
# run; all three builds are checked.
DRY_RUN_PLAN = """Chrome for Testing 153.0.8010.12 (playwright chromium v1243)
  Install location:    {cache}/chromium-1243
  Download url:        https://cdn.playwright.dev/builds/cft/153.0.8010.12/linux-arm64/chrome-linux-arm64.zip

FFmpeg (playwright ffmpeg v1011)
  Install location:    {cache}/ffmpeg-1011
  Download url:        https://cdn.playwright.dev/dbazure/download/playwright/builds/ffmpeg/1011/ffmpeg-linux-arm64.zip
  Download fallback 1: https://playwright.download.prss.microsoft.com/dbazure/download/playwright/builds/ffmpeg/1011/ffmpeg-linux-arm64.zip
  Download fallback 2: https://cdn.playwright.dev/builds/ffmpeg/1011/ffmpeg-linux-arm64.zip

Chrome Headless Shell 153.0.8010.12 (playwright chromium-headless-shell v1243)
  Install location:    {cache}/chromium_headless_shell-1243
  Download url:        https://cdn.playwright.dev/builds/cft/153.0.8010.12/linux-arm64/chrome-headless-shell-linux-arm64.zip
"""


def _golden_only_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    node_modules: bool,
    calls: list[tuple[list[str], dict[str, Any]]],
    install_rc: int = 0,
    browsers: bool = False,
    browser_rc: int = 0,
    probe_rc: int = 0,
    browsers_path: Path | None = None,
    xdg_cache: Path | None = None,
    default_cache_complete: bool = False,
    partial_builds: tuple[str, ...] = (),
    install_hangs: bool = False,
    probe_hangs: bool = False,
    probe_stdout: str | None = None,
) -> Any:
    """A Run whose golden() reaches the Playwright branch with every filesystem
    fact pointed at tmp_path, and whose _run is recorded, not executed.

    The branch is guarded by the TEXT of ``frontend/playwright.config.ts`` (a
    regex for ``name: 'golden'``), so the fixture spells that text; the real
    repo's tree is never consulted, so the result cannot depend on whether
    this machine happens to have a frontend install.

    R116 pieces: the fake answers the browser probe (``install --dry-run``)
    with the 1.63.0 plan text — three build lines whose Install-location paths
    live under tmp_path, so browser PRESENCE is a filesystem fact this fixture
    controls (``browsers=True`` creates the directories). ``browser_rc`` drives
    the real install's exit; ``probe_rc`` an unreadable probe.
    """
    run = _run(tmp_path, mode="fake")
    run.api, run.ui = "http://api.invalid", "http://ui.invalid"
    # The password's VALUE is never what the pins read — they only check that
    # the npm call carries no env at all — so this stays a deliberate dummy.
    run.admin = {"username": "u", "password": "hunter2"}  # pragma: allowlist secret
    config = tmp_path / "playwright.config.ts"
    config.write_text("{ name: 'golden', testDir: './tests/golden' }\n", encoding="utf-8")
    modules = tmp_path / "frontend" / "node_modules"
    if node_modules:
        _seed_runner_cli(modules)
    default_cache = tmp_path / "ms-playwright"
    # The real CLI's resolution order, measured: PLAYWRIGHT_BROWSERS_PATH wins
    # outright; otherwise the root is XDG_CACHE_HOME/ms-playwright (with only
    # XDG_CACHE_HOME set, every "Install location:" line moves under it; with
    # both set the Playwright variable wins in the plan AND in
    # chromium.executablePath()). The fixture mirrors that order, so a probe that
    # forwards the wrong variable is caught by the plan text rather than by a
    # guess about where browsers live.
    cache = browsers_path or (xdg_cache / "ms-playwright" if xdg_cache else default_cache)

    # A completed Playwright build is a directory carrying INSTALLATION_COMPLETE,
    # which the CLI writes LAST, after extracting (measured in the pinned
    # 1.63.0 bundle: oopDownloadBrowserMain removes the dir, extractZip, chmod,
    # then writeFile(marker)). So a build seeded WITHOUT that marker is what an
    # interrupted download actually leaves behind — a directory the runner
    # cannot launch. The marker is seeded here because the fixture must be able
    # to tell those two filesystem states apart.
    def seed(root: Path, build: str, *, complete: bool = True) -> None:
        (root / build).mkdir(parents=True, exist_ok=True)
        if complete:
            (root / build / "INSTALLATION_COMPLETE").write_text("", encoding="utf-8")

    if browsers:
        for build in ("chromium-1243", "ffmpeg-1011", "chromium_headless_shell-1243"):
            seed(cache, build, complete=build not in partial_builds)
    else:
        # The shape this sandbox's real cache had: ffmpeg survived, the two
        # chromium builds never arrived. Absence is per-build, not all-or-nothing.
        seed(cache, "ffmpeg-1011")
    if default_cache_complete:
        # The misleading state: the DEFAULT root holds a full set while the root
        # the runner will actually use does not.
        for build in ("chromium-1243", "ffmpeg-1011", "chromium_headless_shell-1243"):
            seed(default_cache, build)
    if browsers_path is not None:
        # A caller who moved the browser cache (an operator whose root
        # filesystem is full — this box measured 176 MB free) sets the variable
        # the real CLI reads, and the dry-run plan follows it. Measured on the
        # repo's own 1.63.0 CLI: with the var set, every "Install location:"
        # line moves under it; unset, it prints ~/.cache/ms-playwright.
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(browsers_path))
    if xdg_cache is not None:
        # The other variable that moves the same root, also read at launch time.
        monkeypatch.setenv("XDG_CACHE_HOME", str(xdg_cache))
    monkeypatch.setattr(fc, "PLAYWRIGHT_CONFIG", config)
    monkeypatch.setattr(fc, "FRONTEND", tmp_path / "frontend")
    monkeypatch.setattr(fc, "FRONTEND_MODULES", modules)
    monkeypatch.setattr(fc, "BACKEND_GOLDEN", tmp_path / "no-backend-golden")

    def fake(self: Any, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((list(command), kwargs))
        # A stalled step: the real subprocess.run raises TimeoutExpired on a
        # timeout whatever check says (measured on 3.14.4 — child killed, the
        # child's flushed stdout kept, stderr None), and check=False only skips
        # the raise for a NONZERO EXIT. fc._run now converts that raise for
        # check=False callers, so the faithful fake raises first and converts
        # exactly the way the real helper does — through fc._stalled_result, so
        # if that producer's shape changes these tests change with it instead
        # of staying green on a hand-typed copy.
        deadline = {"probe": probe_hangs, "install": install_hangs}
        if command[:4] == ["npx", "playwright", "install", "--dry-run"]:
            which, default = "probe", 300
        elif command == BROWSER_INSTALL:
            which, default = "install", 1800
        else:
            which, default = "", 0
        if deadline.get(which, False):
            try:
                raise subprocess.TimeoutExpired(command, kwargs.get("timeout", default))
            except subprocess.TimeoutExpired as stalled:
                if kwargs.get("check", True):
                    raise
                return fc._stalled_result(stalled)
        if command[:4] == ["npx", "playwright", "install", "--dry-run"]:
            # Faithful to the measured CLI: the plan names the locations the
            # CHILD'S environment says browsers live at. So a probe that loses
            # PLAYWRIGHT_BROWSERS_PATH on the way to the child prints the
            # default root while the test run below (which gets the caller's
            # whole environment) will look elsewhere.
            child_env = kwargs.get("env") or {}
            # Resolved the way the real CLI resolves it (the precedence comment
            # above), from the CHILD's env only — so a variable the harness fails
            # to forward shows up as the plan pointing somewhere else.
            if child_env.get("PLAYWRIGHT_BROWSERS_PATH"):
                root = child_env["PLAYWRIGHT_BROWSERS_PATH"]
            elif child_env.get("XDG_CACHE_HOME"):
                root = str(Path(child_env["XDG_CACHE_HOME"]) / "ms-playwright")
            else:
                root = str(default_cache)
            text = DRY_RUN_PLAN if probe_stdout is None else probe_stdout
            return subprocess.CompletedProcess(command, probe_rc, text.format(cache=root), "")
        if command == BROWSER_INSTALL:
            return subprocess.CompletedProcess(command, browser_rc, "", "")
        rc = install_rc if command[:2] == ["npm", "ci"] else 0
        if command[:2] == ["npm", "ci"] and rc == 0:
            # A successful npm ci really does leave the locked playwright CLI
            # behind; the r116 gate reads that filesystem fact, so the fake has
            # to leave it too.
            _seed_runner_cli(modules)
        # Ruling 114 makes a golden leg that executed nothing a problem, so a
        # fixture that claims "the golden step was healthy" has to WRITE a spec.
        # Without this the pins below would each carry a vacuity problem the
        # npm ci question never meant to assert about.
        report = kwargs.get("env", {}).get("PLAYWRIGHT_JUNIT_OUTPUT_FILE")
        if report:
            Path(report).write_text(_RAN_JUNIT, encoding="utf-8")
        return subprocess.CompletedProcess(command, rc, "", "")

    monkeypatch.setattr(fc.Run, "_run", fake)
    return run


@pytest.mark.parametrize("node_modules", [False, True])
def test_the_golden_step_installs_frontend_deps_only_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, node_modules: bool
) -> None:
    """Ruling 102: the operator's documented ``--real`` run died at
    ERR_MODULE_NOT_FOUND because nothing ever installed frontend/node_modules
    on their tree (the harness builds no images for it; the CI feature-check
    job's ``npm ci`` step is not this process). golden() now installs when
    absent — and an existing install is LEFT ALONE, because ``npm ci`` deletes
    node_modules on entry and would blow away an operator's (or a CI
    runner's) working install, its Playwright browsers included."""
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, node_modules, calls)
    problems = run.golden()
    commands = [command for command, _ in calls]
    assert problems == []
    assert commands[-1][:4] == ["npx", "playwright", "test", "--project=golden"]
    installs = [c for c in commands if c[:2] == ["npm", "ci"]]
    if node_modules:
        assert installs == [], "an existing install must never be re-run over"
        assert "npm_ci" not in run.summary["results"]["golden"]
    else:
        assert installs == [["npm", "ci"]]
        assert commands[0] == ["npm", "ci"], "the install must come BEFORE npx"
        install_kwargs = calls[0][1]
        assert install_kwargs["cwd"] == tmp_path / "frontend"
        assert install_kwargs["timeout"] == 1800, "the 300 s default cannot survive a cold install"
        assert "env" not in install_kwargs, "npm must not see the run env (admin password)"
        # Positive witness that the recorder captures env= when it IS passed:
        # without this, the line above would pass even if no call ever had one.
        assert "env" in calls[-1][1], "npx keeps its run env — the recorder sees env="
        assert run.summary["results"]["golden"]["npm_ci"] == "ok"


# ---------------------------------------------------------------------------
# Ruling 114: a golden run that executes nothing is a Feature Check problem
# ---------------------------------------------------------------------------

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

    def fake(self: Any, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if junit_text is not None:
            report = kwargs.get("env", {}).get("PLAYWRIGHT_JUNIT_OUTPUT_FILE") or next(
                arg.split("=", 1)[1] for arg in command if arg.startswith("--junitxml=")
            )
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


def test_a_failed_frontend_install_is_a_named_step_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The operator posts summary.json verbatim (O2.2). An unreachable registry
    must therefore NAME its step in the summary and problems — with check=False
    the run continues, so the npx exit that follows is context, not a crash,
    and the harness still reaches collect/teardown."""
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, False, calls, install_rc=243)
    problems = run.golden()
    assert [c[:2] for c, _ in calls] == [["npm", "ci"], ["npx", "playwright"]]
    assert run.summary["results"]["golden"]["npm_ci"] == "exit 243"
    assert any("npm ci in frontend/ exited 243" in p for p in problems)


@pytest.mark.parametrize("browsers", [False, True])
def test_the_golden_step_installs_chromium_only_when_the_plan_is_unmet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, browsers: bool
) -> None:
    """Ruling 116: ``npm ci`` brings the RUNNER, not Chromium, so the operator's
    ``--real`` re-run died in ~3 ms on every spec —
    ``browserType.launch: Executable doesn't exist at
    ~/.cache/ms-playwright/chromium_headless_shell-1243/…`` — a failure the
    merged testing.md itself predicts. golden() now installs when absent and
    leaves a working install ALONE.

    The absent test is the filesystem, not a directory guess: the probe's own
    ``Install location:`` lines name the builds the LOCK-resolved runner wants
    (v1243 at the pinned 1.63.0), so a Playwright bump cannot rot a hardcoded
    build number here, and a custom PLAYWRIGHT_BROWSERS_PATH is honoured for
    free — the probe prints the paths it would use.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls, browsers=browsers)
    problems = run.golden()
    commands = [command for command, _ in calls]
    assert problems == []
    assert commands[-1][:4] == ["npx", "playwright", "test", "--project=golden"]
    probes = [c for c in commands if c[:4] == ["npx", "playwright", "install", "--dry-run"]]
    installs = [c for c in commands if c == BROWSER_INSTALL]
    if browsers:
        assert installs == [], "an installed browser set must never be re-installed over"
        assert run.summary["results"]["golden"]["playwright_browsers"] == "present"
    else:
        assert installs == [BROWSER_INSTALL]
        assert probes[0] in commands[:2], "the probe must come BEFORE the install"
        assert commands.index(BROWSER_INSTALL) < len(commands) - 1, "…and before the test run"
        assert (
            run.summary["results"]["golden"]["playwright_browsers"]
            == "installed chromium v1243 chromium-headless-shell v1243"
        ), "the version the operator's error named, per build"
    # The probe runs either way: it is how absence is decided.
    assert len(probes) == 1
    probe_kwargs = calls[commands.index(probes[0])][1]
    assert probe_kwargs["cwd"] == tmp_path / "frontend"
    # Ruling 102's discipline, restated after r116: these steps carry an env, but
    # it is browser_environment(os.environ) — the engine's PATH/HOME plus the
    # browser-cache location — NOT golden()'s run env. The password is the fact
    # that must stay out, so that is what is pinned by name.
    assert "FEATURE_CHECK_ADMIN_PASSWORD" not in probe_kwargs.get("env", {})
    # Positive witness that the absence above is not vacuous: the recorder sees
    # the credential on the leg that is GIVEN the run env (the test npx, which
    # needs it to log in), so its absence from the browser steps is a choice.
    assert calls[-1][1]["env"]["FEATURE_CHECK_ADMIN_PASSWORD"] == run.admin["password"]
    install_seen = [kw for cmd, kw in calls if cmd == BROWSER_INSTALL]
    if install_seen:
        assert "FEATURE_CHECK_ADMIN_PASSWORD" not in install_seen[0].get("env", {})
        assert install_seen[0]["cwd"] == tmp_path / "frontend"
        assert install_seen[0]["timeout"] == 1800, "a cold browser download is minutes"


def test_a_browsers_absent_tree_installs_after_the_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Order matters twice over: ``npx playwright`` with no node_modules fetches
    the LATEST package, whose plan names a DIFFERENT build than the lock's (the
    operator's tree wants v1243; latest wanted v1248 — measured 2026-10-11),
    and a failed ``npm ci`` means the locked CLI does not exist at all. So the
    probe and the install ride behind ``npm ci``, and neither runs when it
    fails — the named npm_ci step already says why."""
    calls: list[tuple[list[str], dict[str, Any]]] = []
    tree = tmp_path / "cold"
    tree.mkdir()
    run = _golden_only_run(tree, monkeypatch, False, calls)
    run.golden()
    commands = [command for command, _ in calls]
    assert commands[0] == ["npm", "ci"]
    assert commands[1][:4] == ["npx", "playwright", "install", "--dry-run"]
    assert commands[2] == BROWSER_INSTALL
    assert commands[3][:4] == ["npx", "playwright", "test", "--project=golden"]

    failed: list[tuple[list[str], dict[str, Any]]] = []
    broken = tmp_path / "npm-failed"
    broken.mkdir()
    run2 = _golden_only_run(broken, monkeypatch, False, failed, install_rc=243)
    problems = run2.golden()
    assert [c[:2] for c, _ in failed] == [["npm", "ci"], ["npx", "playwright"]]
    assert "playwright_browsers" not in run2.summary["results"]["golden"]
    assert any("npm ci in frontend/ exited 243" in p for p in problems)


def test_a_failed_browser_install_is_a_named_step_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruling 116's firewall: "If the operator sandbox cannot reach Playwright's
    download host, the PR names the host and the owner allows it. The harness
    does not work around a block." So a failed install is ACCOUNTED — a named
    step in summary.json plus the download host the owner has to allow — and
    the run continues to the test npx, which will produce Playwright's own
    browser-missing message. Not a crash, not a silent skip."""
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls, browsers=False, browser_rc=1)
    problems = run.golden()
    assert [c[:3] for c, _ in calls] == [
        ["npx", "playwright", "install"],
        ["npx", "playwright", "install"],
        ["npx", "playwright", "test"],
    ]
    assert run.summary["results"]["golden"]["playwright_browsers"] == "exit 1"
    named = [p for p in problems if "exited 1" in p and "playwright install chromium" in p]
    assert len(named) == 1, problems
    assert "cdn.playwright.dev" in named[0], "the firewall clause needs the host to allow"
    assert "playwright.download.prss.microsoft.com" in named[0], "and the fallback host too"


def test_an_unreadable_probe_installs_nothing_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The probe is the only thing that knows which builds the lock wants. If it
    cannot answer, guessing means a speculative multi-minute download on the
    operator's box; skipping is honest and cheap, and the test run still names
    the real problem in its own output."""
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls, browsers=False, probe_rc=1)
    problems = run.golden()
    assert [c[:3] for c, _ in calls] == [
        ["npx", "playwright", "install"],
        ["npx", "playwright", "test"],
    ]
    assert run.summary["results"]["golden"]["playwright_browsers"] == "probe exit 1"
    assert problems == [], "an unreadable probe is not itself a golden failure"


def test_a_moved_browser_cache_is_judged_where_the_runner_will_look(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The test leg gets the caller's WHOLE environment, so a caller who moved
    Playwright's cache with ``PLAYWRIGHT_BROWSERS_PATH`` — an operator whose root
    filesystem is full is exactly who runs this on the GPU box — launches from
    there. Absence must therefore be judged AT THAT PATH, which means the
    variable has to reach these two children as well.

    Both directions are pinned because they fail differently. A probe that loses
    the variable reads the DEFAULT root: with a complete moved cache it wastes
    minutes downloading builds the runner will never use; with a misleadingly
    complete DEFAULT cache it reports ``present`` and installs nothing,
    reproducing ruling 116's own bug silently.
    """
    moved = tmp_path / "complete" / "moved"
    moved.mkdir(parents=True)
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(
        tmp_path / "complete", monkeypatch, True, calls, browsers=True, browsers_path=moved
    )
    run.golden()
    assert run.summary["results"]["golden"]["playwright_browsers"] == "present", (
        "the root the runner launches from is complete, so nothing is missing"
    )
    assert BROWSER_INSTALL not in [c for c, _ in calls], "…and nothing may be downloaded"

    misleading = tmp_path / "misleading"
    misleading.mkdir()
    moved2 = misleading / "moved"
    later: list[tuple[list[str], dict[str, Any]]] = []
    run2 = _golden_only_run(
        misleading,
        monkeypatch,
        True,
        later,
        browsers=False,
        browsers_path=moved2,
        default_cache_complete=True,
    )
    run2.golden()
    installs = [kw for cmd, kw in later if cmd == BROWSER_INSTALL]
    assert len(installs) == 1, (
        "the moved root lacks both chromium builds; the default root's "
        "completeness is not the runner's answer"
    )
    assert installs[0]["env"].get("PLAYWRIGHT_BROWSERS_PATH") == str(moved2), (
        "the install must land where the test run will look"
    )


def test_an_xdg_cache_home_is_judged_where_the_runner_will_look(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """XDG_CACHE_HOME moves the SAME root PLAYWRIGHT_BROWSERS_PATH moves, and it
    is read at launch time too — so a probe that loses it reproduces the moved-
    cache divergence one variable away from the one already fixed.

    Measured on the repo's pinned 1.63.0 CLI: with only XDG_CACHE_HOME set, every
    ``Install location:`` line lands under ``$XDG_CACHE_HOME/ms-playwright``; with
    both set, PLAYWRIGHT_BROWSERS_PATH wins in the plan AND in
    ``chromium.executablePath()``. That agreement is why forwarding both is safe:
    the probe's oracle is the CLI's own answer, not a hand-written path guess.
    """
    moved = tmp_path / "xdg" / "ms-playwright"
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(
        tmp_path, monkeypatch, True, calls, browsers=True, xdg_cache=tmp_path / "xdg"
    )
    run.golden()
    assert run.summary["results"]["golden"]["playwright_browsers"] == "present", (
        "the launch root under XDG_CACHE_HOME is complete, so nothing is missing"
    )
    assert BROWSER_INSTALL not in [c for c, _ in calls], (
        "a probe that lost XDG_CACHE_HOME would read the default root and spend "
        "minutes downloading builds this run will never launch"
    )
    probes = [kw for cmd, kw in calls if cmd[:4] == ["npx", "playwright", "install", "--dry-run"]]
    assert probes[0]["env"].get("XDG_CACHE_HOME") == str(tmp_path / "xdg"), (
        "the variable has to reach the child that prints the plan — the probe's "
        "env is the compose whitelist, so a root variable must be added to it by name"
    )


def test_a_probe_that_prints_no_plan_is_accounted_and_installs_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rc-0-but-unparseable-plan branch, pinned (it was reachable but untested).

    A CLI that exits 0 and prints nothing usable is not the same as a plan that
    says everything is present: with no build lines there is no answer to "which
    builds does the LOCKED runner want", so the harness must not download a
    guess (an install of the wrong build is minutes of bytes and still leaves the
    runner unable to launch). It accounts ``probe empty`` and lets the test leg
    name the real launch failure in its own output.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls, browsers=False, probe_stdout="")
    problems = run.golden()
    assert problems == [], "an unreadable plan is not itself a golden failure"
    assert run.summary["results"]["golden"]["playwright_browsers"] == "probe empty"
    assert BROWSER_INSTALL not in [c for c, _ in calls]
    assert calls[-1][0][:4] == ["npx", "playwright", "test", "--project=golden"]


def test_a_partial_download_is_not_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A build directory without INSTALLATION_COMPLETE is a half-finished download.

    Measured in the pinned 1.63.0 bundle: the CLI's own "already downloaded"
    predicate is ``<dir>/INSTALLATION_COMPLETE`` (browserFetcher's early return),
    and the downloader removes the directory, extracts, chmods, and writes that
    marker LAST — so a killed download leaves a populated directory the runner
    cannot launch. Judging presence by ``is_dir()`` therefore reports
    ``present`` and installs nothing, which is ruling 116's bug preserved inside
    its own fix. The marker is not Playwright-version folklore either: the only
    build this sandbox's real cache has (ffmpeg-1011) carries one.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(
        tmp_path,
        monkeypatch,
        True,
        calls,
        browsers=True,
        partial_builds=("chromium_headless_shell-1243",),
    )
    problems = run.golden()
    assert problems == []
    assert (
        run.summary["results"]["golden"]["playwright_browsers"]
        == "installed chromium-headless-shell v1243"
    ), "the sibling complete builds must not be re-downloaded"
    assert BROWSER_INSTALL in [c for c, _ in calls]


# ---------------------------------------------------------------------------
# A stalled browser step is accounted and the run continues (ruling 116)
# ---------------------------------------------------------------------------


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
    """A download stalled at 80% still says WHICH build was in flight.

    Pinned at the pure-function level because the fact that matters is a shape:
    TimeoutExpired hands back raw BYTES even when run() was called with
    text=True (measured on 3.14.4 — e.stdout is b'...', e.stderr is None). The
    first draft of _stalled_result guarded with isinstance(v, str) as a
    defensive nicety and silently threw that stream away; the assertion below is
    the trap it fell into, so it is pinned alongside the behaviour.
    """
    exception = subprocess.TimeoutExpired(
        ["npx", "playwright", "install", "chromium"], 1800, output=b"downloading chromium 80%\n"
    )
    assert isinstance(exception.stdout, bytes), "the shape that made a str-only guard lossy"
    result = fc._stalled_result(exception)
    assert result.returncode == 124
    assert result.stdout == "downloading chromium 80%\n", "decoded, not dropped"
    assert result.stderr.startswith("timed out after 1800"), "the cause leads the text"


def test_a_stalled_browser_probe_installs_nothing_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dry-run that never returns is accounted, not raised (ruling 116).

    ``check=False`` does not cover this: subprocess.run raises TimeoutExpired
    on a timeout whatever check says (measured on 3.14.4 — stdout None, child
    killed). Raised here, golden() aborts before its return, and because it
    commits its results dict only on the way out, the WHOLE golden section —
    ruling 102's ``npm_ci`` entry included — vanishes from summary.json, the
    test npx never runs, and the harness's top-level handler reports one line
    naming neither the Playwright step nor the browser.
    """
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, True, calls, browsers=False, probe_hangs=True)
    problems = run.golden()
    assert problems == [], "an unreadable probe is not itself a golden failure"
    assert run.summary["results"]["golden"]["playwright_browsers"] == "probe exit timed out", (
        "the shipped template is 'probe exit <outcome>' (see the 'probe exit 1' pin), so "
        "the stall fills that slot with a word instead of a number — named, and "
        "distinguishable from a refusal, which is what ruling 116's firewall needs to tell apart"
    )
    assert BROWSER_INSTALL not in [c for c, _ in calls], (
        "a plan that never came back cannot say which builds are wanted, so a "
        "speculative download is exactly what must not start"
    )
    # Positive witness for the absence assertion above: the SAME absent-browsers
    # tree with a responsive probe does install, so "not in calls" above is the
    # stall's doing and not an artefact of how the recorder collects commands.
    later: list[tuple[list[str], dict[str, Any]]] = []
    _golden_only_run(
        tmp_path / "witness", monkeypatch, True, later, browsers=False, probe_hangs=False
    ).golden()
    assert BROWSER_INSTALL in [c for c, _ in later]
    # golden() continued to the test leg, so Playwright's own browser-missing
    # message still reaches the log (ruling 116: "... and continues").
    assert calls[-1][0][:4] == ["npx", "playwright", "test", "--project=golden"]


def test_a_stalled_browser_install_is_accounted_and_the_run_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A download that hangs (accepted connection, no bytes) is a named problem.

    The firewall clause's realistic failure is not a refused connect — that
    exits nonzero and is already accounted — but a proxy that accepts and then
    streams nothing, which stalls until the deadline. The step must stay
    ACCOUNTED (a named problem, a ``playwright_browsers`` value) and golden()
    must still reach the test npx, because ruling 116's sentence is "installs
    it once, logs the installed version, and CONTINUES".
    """
    # node_modules=False is the fresh-clone shape this box actually had: npm ci
    # runs (and succeeds) first, so ruling 102's entry is IN the dict before the
    # download stalls. That is what makes the npm_ci assertion below mean what it
    # says — with node_modules seeded, npm ci is skipped and the key never exists.
    calls: list[tuple[list[str], dict[str, Any]]] = []
    run = _golden_only_run(tmp_path, monkeypatch, False, calls, browsers=False, install_hangs=True)
    problems = run.golden()
    golden_results = run.summary["results"]["golden"]
    assert golden_results["playwright_browsers"] == "exit timed out"
    assert golden_results["npm_ci"] == "ok", "earlier steps keep their accounting"
    assert len(problems) == 1 and "timed out" in problems[0]
    assert "cdn.playwright.dev" in problems[0], "the firewall clause still names hosts"
    install = [kw for cmd, kw in calls if cmd == BROWSER_INSTALL]
    assert len(install) == 1, "the install was attempted, then hit its deadline"
    assert install[0]["timeout"] == 1800, "the deadline stays the parent's, unchanged"
    assert calls[-1][0][:4] == ["npx", "playwright", "test", "--project=golden"]


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
