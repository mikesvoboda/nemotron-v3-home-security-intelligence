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


def test_real_is_not_built_yet_and_says_so_with_its_own_exit_code() -> None:
    """Exit 2 means the preflight refused; --real before it exists is 4."""
    assert fc.main(["--real"]) == fc.EXIT_UNAVAILABLE == 4


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

    def up(self: Any) -> None:
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
