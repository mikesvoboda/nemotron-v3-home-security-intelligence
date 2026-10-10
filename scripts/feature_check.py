#!/usr/bin/env python3
"""The feature-check harness (O2.2): golden paths against a test deployment.

Run it through ``scripts/feature-check.sh``. ``--fake`` brings up the CI stack
(``docker-compose.ci.yml``) with the fake-AI overlay
(``docker-compose.fake-ai.yml``) as a **test deployment**, seeds its camera
directory, runs the harness smoke check and the golden paths, collects
artifacts and tears down. Usage and the golden-path contract are in
``docs/developer/testing.md``, "Feature check".

A test deployment touches nothing else on the machine (``docs/uplevel/30-ops.md``
§O2.2). Every run:

* gets its own compose project (``hsi-check-<run-id>``), run directory and
  generated env file; compose never reads the checkout's ``.env`` or the
  caller's shell (:func:`compose_command`, :func:`compose_environment`);
* is rendered, transformed (:func:`as_test_deployment`) and rendered again, and
  the second rendering is both what the preflight checks and what ``up``
  starts: every published port moves to an engine-assigned port on
  127.0.0.1, the camera directory is ``<run>/cameras``, and the backend's
  orchestrator is off;
* passes the **preflight** (:func:`preflight`) against a snapshot of the
  machine (:class:`Snapshot`) before anything starts;
* passes the **in-run check** (:func:`in_run_check`) once it is up;
* is torn down with ``compose -p <project> down -v`` and nothing else, then
  passes the **postflight** (:func:`postflight`): every container and volume
  from the snapshot still exists, and every container that was running still
  is, with the same start time.

Exit codes: 0 green; 1 a check of the run failed; 2 the preflight refused and
nothing started; 3 the postflight found a pre-existing container or volume
changed (report it on the urgent path; the harness restores nothing).

Standard library only, so it runs in CI, in the operator sandbox and on a host
without the project's virtualenv.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CI_STACK = REPO_ROOT / "docker-compose.ci.yml"
FAKE_OVERLAY = REPO_ROOT / "docker-compose.fake-ai.yml"
SCENARIO_DIR = REPO_ROOT / "backend" / "ai_contract" / "fake" / "scenario_fixtures"
BACKEND_GOLDEN = REPO_ROOT / "backend" / "tests" / "golden"
PLAYWRIGHT_CONFIG = REPO_ROOT / "frontend" / "playwright.config.ts"

# The services the golden paths need: the CI stack and the two fakes.
FAKE_SERVICES = ("postgres", "redis", "backend", "frontend", "ai-vlm", "ai-gateway")
CAMERA_TARGET = "/cameras"
PROJECT_LABEL = "com.docker.compose.project"

# The harness smoke check: one scenario image in, one event out. Its scenario
# has image bytes of its own: the backend deduplicates images by content for
# 300 s across cameras, so a golden path dropping any other scenario image
# right after the smoke check still gets its event.
SMOKE_SCENARIO = "harness-smoke"

# GET /api/system/services with no orchestrator on app.state
# (backend/api/routes/services.py, get_orchestrator).
ORCHESTRATOR_ABSENT = "Container orchestrator not available"

# What compose may see of the caller's environment: how to reach the engine,
# nothing that changes what it renders (IMAGE_TAG, FOSCAM_BASE_PATH,
# COMPOSE_FILE, COMPOSE_PROJECT_NAME ... all come from the run's env file).
ENGINE_ENVIRONMENT = (
    "PATH",
    "HOME",
    "DOCKER_HOST",
    "DOCKER_CONFIG",
    "DOCKER_CONTEXT",
    "DOCKER_CERT_PATH",
    "DOCKER_TLS_VERIFY",
    "XDG_RUNTIME_DIR",
    "CONTAINER_HOST",
    "CONTAINER_CONNECTION",
)

# Names a container resolves to the machine it runs on.
HOST_ALIASES = frozenset(
    {"host.docker.internal", "host.containers.internal", "gateway.docker.internal", "host-gateway"}
)

# Service keys that hand a container the host itself.
HOST_LEVEL_ACCESS = {
    "network_mode": ("host", "the host's network, where the live stack listens"),
    "pid": ("host", "the host's processes"),
    "privileged": (True, "every host device and capability"),
}

_ENGINE_SOCKET = re.compile(
    r"(?:^|/)(?:docker|podman|containerd|crio|cri-dockerd|buildkitd)\.sock$"
)
# A directory that holds an engine socket: /run, /var/run, /run/user/<uid>,
# and the engines' own directories under them.
_ENGINE_SOCKET_DIR = re.compile(
    r"^/(?:var/)?run(?:/user(?:/\d+)?)?(?:/(?:docker|podman|containerd|crio|buildkit))?$"
)


class HarnessError(RuntimeError):
    """The harness cannot go on; the message says why."""


def is_engine_socket(path: str | None) -> bool:
    """True for a container-engine socket or a directory that holds one."""
    if not path:
        return False
    normal = os.path.normpath(path)
    return (
        normal in ("/", "/var")
        or _ENGINE_SOCKET.search(normal) is not None
        or _ENGINE_SOCKET_DIR.match(normal) is not None
    )


def _inside(path: str, root: str) -> bool:
    candidate = PurePosixPath(os.path.normpath(path))
    base = PurePosixPath(os.path.normpath(root))
    return candidate == base or base in candidate.parents


def _overlaps(a: str, b: str) -> bool:
    return _inside(a, b) or _inside(b, a)


# ---------------------------------------------------------------------------
# Snapshots of the machine
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Mount:
    kind: str
    source: str
    target: str
    writable: bool


@dataclass(frozen=True)
class Container:
    id: str
    name: str
    status: str
    started_at: str
    project: str | None
    mounts: tuple[Mount, ...] = ()
    host_ports: tuple[int, ...] = ()

    @property
    def running(self) -> bool:
        return self.status == "running"

    @classmethod
    def from_inspect(cls, raw: Mapping[str, Any]) -> Container:
        """One entry of ``docker inspect`` / ``podman inspect``."""
        state = raw.get("State") or {}
        labels = (raw.get("Config") or {}).get("Labels") or {}
        mounts = tuple(
            Mount(
                kind=str(m.get("Type") or ""),
                source=str(m.get("Source") or ""),
                target=str(m.get("Destination") or ""),
                writable=bool(m.get("RW")),
            )
            for m in raw.get("Mounts") or []
        )
        ports: set[int] = set()
        for bindings in ((raw.get("NetworkSettings") or {}).get("Ports") or {}).values():
            for binding in bindings or []:
                host_port = str(binding.get("HostPort") or "")
                if host_port.isdigit():
                    ports.add(int(host_port))
        return cls(
            id=str(raw.get("Id") or ""),
            name=str(raw.get("Name") or "").lstrip("/"),
            status=str(state.get("Status") or "").lower(),
            started_at=str(state.get("StartedAt") or ""),
            project=labels.get(PROJECT_LABEL),
            mounts=mounts,
            host_ports=tuple(sorted(ports)),
        )


@dataclass(frozen=True)
class Snapshot:
    """The containers (running and stopped) and volumes on the machine."""

    containers: tuple[Container, ...]
    volumes: frozenset[str]

    @classmethod
    def from_engine(cls, inspect: Iterable[Mapping[str, Any]], volumes: Iterable[str]) -> Snapshot:
        return cls(
            containers=tuple(Container.from_inspect(raw) for raw in inspect),
            volumes=frozenset(volumes),
        )

    @property
    def names(self) -> frozenset[str]:
        return frozenset(c.name for c in self.containers)

    @property
    def projects(self) -> frozenset[str]:
        return frozenset(c.project for c in self.containers if c.project)

    @property
    def host_ports(self) -> frozenset[int]:
        return frozenset(p for c in self.containers for p in c.host_ports)

    @property
    def running_bind_sources(self) -> frozenset[str]:
        """Host paths that running containers bind-mount (a live stack's data)."""
        return frozenset(
            m.source
            for c in self.containers
            if c.running
            for m in c.mounts
            if m.kind == "bind" and m.source
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "containers": [
                {
                    "id": c.id,
                    "name": c.name,
                    "status": c.status,
                    "started_at": c.started_at,
                    "project": c.project,
                    "mounts": [
                        {
                            "kind": m.kind,
                            "source": m.source,
                            "target": m.target,
                            "writable": m.writable,
                        }
                        for m in c.mounts
                    ],
                    "host_ports": list(c.host_ports),
                }
                for c in self.containers
            ],
            "volumes": sorted(self.volumes),
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Snapshot:
        return cls(
            containers=tuple(
                Container(
                    id=c["id"],
                    name=c["name"],
                    status=c["status"],
                    started_at=c["started_at"],
                    project=c["project"],
                    mounts=tuple(Mount(**m) for m in c["mounts"]),
                    host_ports=tuple(c["host_ports"]),
                )
                for c in data["containers"]
            ),
            volumes=frozenset(data["volumes"]),
        )


# ---------------------------------------------------------------------------
# The test deployment
# ---------------------------------------------------------------------------


def as_test_deployment(base: Mapping[str, Any], *, project: str, run_dir: Path) -> dict[str, Any]:
    """Turn the rendered CI + fake stack into this run's test deployment.

    Keeps only :data:`FAKE_SERVICES`; moves every published port to an
    engine-assigned host port on 127.0.0.1; names networks and volumes after
    the run's project; points the backend's camera directory at
    ``<run_dir>/cameras`` and turns its orchestrator off. Everything else
    (a fixed ``container_name``, a bind mount) is left for the preflight to
    judge, so nothing is silently dropped.
    """
    services = base.get("services") or {}
    missing = [name for name in FAKE_SERVICES if name not in services]
    if missing:
        raise HarnessError(f"the rendered stack lacks {', '.join(missing)}")

    deployment: dict[str, Any] = {"name": project}
    for key, value in base.items():
        if key not in ("name", "services") and not key.startswith("x-"):
            deployment[key] = copy.deepcopy(value)
    for section in ("networks", "volumes"):
        for key, entry in (deployment.get(section) or {}).items():
            if isinstance(entry, dict) and not entry.get("external"):
                entry["name"] = f"{project}_{key}"

    deployment["services"] = {}
    for name in FAKE_SERVICES:
        service = copy.deepcopy(services[name])
        for dependency in service.get("depends_on") or {}:
            if dependency not in FAKE_SERVICES:
                raise HarnessError(f"{name} depends on {dependency}, which a test deployment omits")
        ports = [
            {
                "mode": "ingress",
                "host_ip": "127.0.0.1",
                "target": int(port["target"]),
                "protocol": port.get("protocol") or "tcp",
            }
            for port in service.get("ports") or []
        ]
        if ports:
            service["ports"] = ports
        deployment["services"][name] = service

    backend = deployment["services"]["backend"]
    environment = backend.setdefault("environment", {})
    environment["ORCHESTRATOR_ENABLED"] = "false"
    environment["FOSCAM_BASE_PATH"] = CAMERA_TARGET
    backend["tmpfs"] = [
        entry for entry in backend.get("tmpfs") or [] if entry.split(":", 1)[0] != CAMERA_TARGET
    ]
    backend.setdefault("volumes", []).append(
        {
            "type": "bind",
            "source": str(run_dir / "cameras"),
            "target": CAMERA_TARGET,
            "bind": {"create_host_path": False},
        }
    )
    return deployment


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------


def _published_ports(value: Any) -> list[int]:
    """``published`` as compose renders it: "", "8000", 8000 or "8000-8002"."""
    text = str(value or "").strip()
    if not text:
        return []
    low, _, high = text.partition("-")
    if not low.isdigit() or (high and not high.isdigit()):
        return []
    return list(range(int(low), int(high or low) + 1))


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, Sequence):
        return [s for v in value for s in _strings(v)]
    return [str(value)]


def _extra_hosts(service: Mapping[str, Any]) -> list[tuple[str, str]]:
    entries = service.get("extra_hosts") or []
    if isinstance(entries, Mapping):
        return [(str(k), str(v)) for k, v in entries.items()]
    pairs = []
    for entry in entries:
        alias, sep, target = str(entry).partition("=")
        if not sep:
            alias, _, target = str(entry).partition(":")
        pairs.append((alias, target))
    return pairs


def _host_references(text: str, hosts: Iterable[str]) -> list[tuple[str, int | None]]:
    found = []
    for host in sorted(hosts):
        pattern = rf"(?<![\w.-]){re.escape(host)}(?::(\d+))?(?![\w.-])"
        for match in re.finditer(pattern, text):
            port = match.group(1)
            found.append((host, int(port) if port else None))
    return found


def preflight(
    rendered: Mapping[str, Any],
    *,
    project: str,
    run_dir: Path,
    snapshot: Snapshot,
    host_addresses: frozenset[str] = frozenset(),
    allowed_host_ports: frozenset[int] = frozenset(),
) -> list[str]:
    """Every reason the rendered run must not start; empty means go.

    Refuses a writable bind mount outside ``run_dir``, any engine socket, the
    host's network, processes or devices, a configured host address on any
    port but ``allowed_host_ports`` (the ports ``agent-gpu run`` printed; none
    on ``--fake``), a backend whose orchestrator is not off, and any overlap
    with the snapshot: the project, a container name, a host port, a volume,
    or a writable host path a running container also mounts.
    """
    problems: list[str] = []
    run_root = str(run_dir)
    live_names = snapshot.names
    live_ports = snapshot.host_ports
    live_binds = snapshot.running_bind_sources
    volumes = rendered.get("volumes") or {}

    if project in snapshot.projects:
        owners = sorted(c.name for c in snapshot.containers if c.project == project)
        problems.append(
            f"project {project} already has containers on this machine: {', '.join(owners)}"
        )

    services = rendered.get("services") or {}
    for name in sorted(services):
        service = services[name] or {}

        fixed = service.get("container_name")
        if fixed:
            clash = " (already on this machine)" if fixed in live_names else ""
            problems.append(f"{name}: carries the fixed container_name {fixed}{clash}")
        for derived in (f"{project}-{name}-1", f"{project}_{name}_1"):
            if derived in live_names:
                problems.append(f"{name}: container {derived} already exists on this machine")

        for key, (value, what) in HOST_LEVEL_ACCESS.items():
            if service.get(key) == value:
                problems.append(f"{name}: {key}: {value} gives the run {what}")

        for port in service.get("ports") or []:
            if str(port.get("host_ip") or "") in ("", "0.0.0.0", "::"):  # noqa: S104
                problems.append(
                    f"{name}: publishes container port {port.get('target')} on all "
                    "interfaces; a test deployment binds 127.0.0.1"
                )
            for host_port in _published_ports(port.get("published")):
                if host_port in live_ports:
                    problems.append(
                        f"{name}: host port {host_port} is already published on this machine"
                    )

        for mount in service.get("volumes") or []:
            kind = mount.get("type")
            source = str(mount.get("source") or "")
            writable = not mount.get("read_only")
            if kind == "bind":
                if is_engine_socket(source):
                    problems.append(f"{name}: mounts an engine socket ({source})")
                elif writable and not _inside(source, run_root):
                    problems.append(
                        f"{name}: writable bind mount {source} is outside the run "
                        f"directory {run_root}"
                    )
                elif writable:
                    clashes = sorted(live for live in live_binds if _overlaps(source, live))
                    if clashes:
                        problems.append(
                            f"{name}: writable bind mount {source} overlaps "
                            f"{', '.join(clashes)}, which a running container mounts"
                        )
            elif kind == "volume" and source:
                declared = volumes.get(source) or {}
                if declared.get("external"):
                    problems.append(f"{name}: volume {source} is external, shared beyond this run")
                    continue
                volume_name = declared.get("name") or f"{project}_{source}"
                if volume_name in snapshot.volumes:
                    problems.append(f"{name}: volume {volume_name} already exists on this machine")

        hosts = set(HOST_ALIASES) | set(host_addresses)
        for alias, target in _extra_hosts(service):
            if target in HOST_ALIASES or target in host_addresses:
                hosts.add(alias)
                if not allowed_host_ports:
                    problems.append(f"{name}: extra_hosts maps {alias} to the host ({target})")
        environment = service.get("environment") or {}
        where_text = [(f"{key}", value) for key, value in environment.items() if value]
        where_text += [("command", s) for s in _strings(service.get("command"))]
        where_text += [("entrypoint", s) for s in _strings(service.get("entrypoint"))]
        for where, text in where_text:
            for host, port in _host_references(str(text), hosts):
                if port is None:
                    problems.append(
                        f"{name}: {where} points at the host ({host}) with no explicit port"
                    )
                elif port not in allowed_host_ports:
                    problems.append(f"{name}: {where} points at the host ({host}:{port})")

        if name == "backend":
            value = environment.get("ORCHESTRATOR_ENABLED")
            if str(value).lower() != "false":
                shown = "unset" if value is None else repr(value)
                problems.append(f"backend: ORCHESTRATOR_ENABLED must be false, found {shown}")

    return problems


# ---------------------------------------------------------------------------
# In-run check and postflight
# ---------------------------------------------------------------------------


def in_run_check(
    containers: Iterable[Mapping[str, Any]],
    *,
    orchestrator_enabled: bool | None,
    services: tuple[int, Any] | None,
) -> list[str]:
    """Every reason the running test deployment is not isolated.

    ``containers`` is ``inspect`` of the run project's containers;
    ``orchestrator_enabled`` is the backend's own setting, read inside its
    container (None if it could not be read); ``services`` is the status and
    JSON body of ``GET /api/system/services``, read after the first admin
    registered (the setup guard answers 503 before that, for every route).
    """
    problems = []
    for raw in containers:
        container = Container.from_inspect(raw)
        for mount in container.mounts:
            if is_engine_socket(mount.source) or _ENGINE_SOCKET.search(mount.target):
                problems.append(
                    f"{container.name}: holds an engine socket ({mount.source} -> {mount.target})"
                )
    if orchestrator_enabled is None:
        problems.append("backend: the orchestrator's setting could not be read")
    elif orchestrator_enabled:
        problems.append("backend: the orchestrator reports enabled")
    if services is None:
        problems.append("backend: /api/system/services could not be read")
    else:
        status, body = services
        detail = body.get("detail") if isinstance(body, Mapping) else None
        if status != 503 or detail != ORCHESTRATOR_ABSENT:
            problems.append(
                f"backend: /api/system/services answered {status} {json.dumps(body)}; "
                f"expected 503 {ORCHESTRATOR_ABSENT!r}"
            )
    return problems


def postflight(before: Snapshot, after: Snapshot, *, project: str) -> list[str]:
    """Every pre-existing container or volume the run changed, and anything
    of the run's own that teardown left behind."""
    problems = []
    now_by_id = {c.id: c for c in after.containers}
    for container in before.containers:
        now = now_by_id.get(container.id)
        if now is None:
            problems.append(
                f"{container.name}: missing after the run (container {container.id[:12]})"
            )
        elif container.running and not now.running:
            problems.append(
                f"{container.name}: was running before the run and is no longer running "
                f"({now.status})"
            )
        elif container.running and now.started_at != container.started_at:
            problems.append(
                f"{container.name}: restarted during the run (started {container.started_at}, "
                f"now {now.started_at})"
            )
    for volume in sorted(before.volumes - after.volumes):
        problems.append(f"volume {volume}: missing after the run")
    for container in after.containers:
        if container.project == project:
            problems.append(f"{container.name}: the run's container is still here after teardown")
    for volume in sorted(after.volumes - before.volumes):
        if volume.startswith(f"{project}_"):
            problems.append(f"volume {volume}: the run's volume is still here after teardown")
    return problems


# ---------------------------------------------------------------------------
# Compose invocation
# ---------------------------------------------------------------------------


def compose_command(
    *, engine: str, project: str, env_file: Path, files: Sequence[Path]
) -> list[str]:
    """``<engine> compose`` for this run: its env file, its project, its files."""
    command = [engine, "compose", "--env-file", str(env_file), "-p", project]
    for path in files:
        command += ["-f", str(path)]
    return command


def compose_environment(caller: Mapping[str, str]) -> dict[str, str]:
    """The part of the caller's environment compose may see."""
    return {key: caller[key] for key in ENGINE_ENVIRONMENT if key in caller}


# ---------------------------------------------------------------------------
# A run
# ---------------------------------------------------------------------------


def _log(message: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
    print(f"feature-check {stamp} {message}", flush=True)


class Run:
    """One test deployment: its project, directory, engine and artifacts."""

    def __init__(self, *, engine: str, root: Path, image_tag: str, mode: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        self.project = f"hsi-check-{stamp}-{secrets.token_hex(3)}"
        self.engine = engine
        self.mode = mode
        self.image_tag = image_tag
        self.dir = (root / self.project).resolve()
        self.cameras = self.dir / "cameras"
        self.artifacts = self.dir / "artifacts"
        self.env_file = self.dir / "env"
        self.compose_file = self.dir / "compose.json"
        self.summary: dict[str, Any] = {
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": mode,
            "project": self.project,
            "run_dir": str(self.dir),
            "engine": engine,
            "image_tag": image_tag,
            "results": {},
        }
        self.started = False

    # -- processes -----------------------------------------------------------

    def _run(
        self,
        command: Sequence[str],
        *,
        check: bool = True,
        timeout: float | None = 300,
        env: Mapping[str, str] | None = None,
        cwd: Path = REPO_ROOT,
        echo: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        if echo:
            _log("$ " + shlex.join(command))
        result = subprocess.run(
            list(command),
            cwd=cwd,
            env=dict(env) if env is not None else compose_environment(os.environ),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if check and result.returncode != 0:
            raise HarnessError(
                f"{' '.join(command[:4])} ... exited {result.returncode}: "
                f"{(result.stderr or result.stdout).strip()[-2000:]}"
            )
        return result

    def compose(
        self, files: Sequence[Path], *args: str, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        command = compose_command(
            engine=self.engine, project=self.project, env_file=self.env_file, files=files
        )
        return self._run([*command, *args], **kwargs)

    def deployment(self, *args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return self.compose([self.compose_file], *args, **kwargs)

    # -- the machine ---------------------------------------------------------

    def snapshot(self) -> Snapshot:
        ids = self._run([self.engine, "ps", "-a", "-q", "--no-trunc"], echo=False).stdout.split()
        inspect: list[dict[str, Any]] = []
        if ids:
            # A container removed between ps and inspect makes inspect exit 1
            # with the rest still printed; the snapshot keeps what exists.
            out = self._run([self.engine, "inspect", *ids], check=False, echo=False).stdout
            inspect = json.loads(out or "[]")
        volumes = self._run([self.engine, "volume", "ls", "-q"], echo=False).stdout.split()
        return Snapshot.from_engine(inspect, volumes)

    def host_addresses(self) -> frozenset[str]:
        """This machine's own addresses, as a container could configure them."""
        found: set[str] = set()
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None):
                found.add(str(info[4][0]))
        except OSError:
            pass
        result = self._run(
            [self.engine, "network", "inspect", "bridge", "podman"], check=False, echo=False
        )
        try:
            networks = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            networks = []
        for network in networks:
            for config in (network.get("IPAM") or {}).get("Config") or []:
                if config.get("Gateway"):
                    found.add(config["Gateway"])
            for subnet in network.get("subnets") or []:
                if subnet.get("gateway"):
                    found.add(subnet["gateway"])
        return frozenset(a for a in found if not a.startswith("127.") and a != "::1")

    # -- phases --------------------------------------------------------------

    def prepare(self) -> Snapshot:
        """The run directory, its env file and watched folder, and the snapshot."""
        for path in (self.dir, self.cameras, self.artifacts):
            path.mkdir(parents=True, exist_ok=path != self.dir)
        self.env_file.write_text(f"IMAGE_TAG={self.image_tag}\n", encoding="utf-8")
        # One camera folder per scenario, so a golden path drops a scenario's
        # image into the camera of the same name.
        for scenario in _scenarios():
            (self.cameras / scenario["name"]).mkdir()
        _log(f"run {self.project} in {self.dir}")
        before = self.snapshot()
        self._write("snapshot-before.json", before.to_json())
        _log(
            f"snapshot: {len(before.containers)} containers "
            f"({sum(c.running for c in before.containers)} running), {len(before.volumes)} volumes"
        )
        return before

    def render(self, before: Snapshot) -> None:
        base = json.loads(
            self.compose([CI_STACK, FAKE_OVERLAY], "config", "--format", "json").stdout
        )
        deployment = as_test_deployment(base, project=self.project, run_dir=self.dir)
        self.compose_file.write_text(json.dumps(deployment, indent=2) + "\n", encoding="utf-8")
        rendered = json.loads(self.deployment("config", "--format", "json").stdout)
        self._write("rendered.json", rendered)
        problems = preflight(
            rendered,
            project=self.project,
            run_dir=self.dir,
            snapshot=before,
            host_addresses=self.host_addresses(),
        )
        self.summary["results"]["preflight"] = problems or "ok"
        if problems:
            raise Refused(problems)
        _log("preflight: ok")
        self.summary["images"] = {
            name: service.get("image") for name, service in rendered["services"].items()
        }

    def up(self) -> None:
        self.started = True
        self.deployment("up", "-d", "--wait", "--wait-timeout", "900", timeout=1500)
        self.api = self._address("backend", 8000)
        self.ui = self._address("frontend", 8080)
        _log(f"up: api {self.api}, ui {self.ui}")
        self.summary["urls"] = {"api": self.api, "ui": self.ui}
        props = _http("GET", self._address("ai-vlm", 8098) + "/props")
        if props[0] == 200 and isinstance(props[1], Mapping):
            self.summary["build_info"] = props[1].get("build_info")
            self.summary["model_path"] = props[1].get("model_path")

    def _address(self, service: str, port: int) -> str:
        out = self.deployment("port", service, str(port), echo=False).stdout.strip()
        host, _, published = out.rpartition(":")
        if not published.isdigit():
            raise HarnessError(f"{service}:{port} is not published ({out!r})")
        return f"http://{host or '127.0.0.1'}:{published}"

    def register_admin(self) -> None:
        self.admin = {
            "username": "feature-check",
            "email": "feature-check@example.com",
            "password": f"Fc{secrets.token_hex(8)}9a",
        }
        status, body = _http("POST", self.api + "/api/auth/register", self.admin)
        if status != 201:
            raise HarnessError(f"registering the first admin answered {status}: {body}")
        admin_file = self.dir / "admin.json"
        admin_file.write_text(json.dumps(self.admin) + "\n", encoding="utf-8")
        admin_file.chmod(0o600)
        _log("first admin registered (setup guard lifted)")

    def seed_cameras(self) -> None:
        """Register a camera for each scenario folder of the watched folder."""
        self.camera_ids: dict[str, str] = {}
        for scenario in _scenarios():
            name = scenario["name"]
            status, body = _http(
                "POST",
                self.api + "/api/cameras",
                {"name": name, "folder_path": f"{CAMERA_TARGET}/{name}"},
            )
            if status != 201 or not isinstance(body, Mapping):
                raise HarnessError(f"seeding camera {name} answered {status}: {body}")
            self.camera_ids[name] = str(body["id"])
        self._write("cameras.json", self.camera_ids)
        _log(f"seeded {len(self.camera_ids)} cameras: {', '.join(self.camera_ids.values())}")

    def check_isolation(self) -> list[str]:
        ids = self._run(
            [
                self.engine,
                "ps",
                "-a",
                "-q",
                "--no-trunc",
                "--filter",
                f"label={PROJECT_LABEL}={self.project}",
            ],
            echo=False,
        ).stdout.split()
        inspect = (
            json.loads(self._run([self.engine, "inspect", *ids], echo=False).stdout) if ids else []
        )
        setting = self.deployment(
            "exec",
            "-T",
            "backend",
            "python",
            "-c",
            "from backend.core.config import get_settings; "
            "print(get_settings().orchestrator.enabled)",
            check=False,
        )
        lines = setting.stdout.strip().splitlines()
        enabled = {"True": True, "False": False}.get(lines[-1] if lines else "")
        services = _http("GET", self.api + "/api/system/services")
        problems = in_run_check(
            inspect,
            orchestrator_enabled=enabled,
            services=services if services[0] else None,
        )
        self.summary["results"]["in_run"] = problems or "ok"
        _log("in-run check: " + ("ok" if not problems else f"{len(problems)} problem(s)"))
        return problems

    def smoke(self) -> list[str]:
        """One fixture image in, one event out with the scenario's verdict."""
        scenario = _scenario(SMOKE_SCENARIO)
        camera = self.camera_ids[SMOKE_SCENARIO]
        image = drop(SCENARIO_DIR / scenario["image"], SMOKE_SCENARIO, self.cameras)
        _log(f"smoke: dropped {image.relative_to(self.dir)}; waiting for its event")
        expected = scenario["verdict"]
        deadline = time.monotonic() + 300
        events: list[Any] = []
        while time.monotonic() < deadline:
            status, body = _http("GET", self.api + f"/api/events?camera_id={camera}")
            events = body.get("items", []) if status == 200 and isinstance(body, Mapping) else []
            if events and (events[0].get("verification") or {}).get("verdict"):
                break
            time.sleep(5)
        self._write("smoke-events.json", events)
        problems = []
        if len(events) != 1:
            problems.append(f"smoke: expected one event on {camera}, found {len(events)}")
        else:
            event = events[0]
            verdict = (event.get("verification") or {}).get("verdict")
            if verdict != expected["verdict"]:
                problems.append(
                    f"smoke: verdict {verdict!r}, scenario says {expected['verdict']!r}"
                )
            if event.get("risk_score") != expected["risk_score"]:
                problems.append(
                    f"smoke: risk_score {event.get('risk_score')!r}, "
                    f"scenario says {expected['risk_score']!r}"
                )
            if not problems:
                _log(
                    f"smoke: ok, event {event.get('id')} verdict {verdict} "
                    f"risk_score {event.get('risk_score')}"
                )
        self.summary["results"]["smoke"] = problems or "ok"
        return problems

    def golden(self) -> list[str]:
        env = {
            **os.environ,
            "FEATURE_CHECK_MODE": self.mode,
            "FEATURE_CHECK_RUN_DIR": str(self.dir),
            "FEATURE_CHECK_API_URL": self.api,
            "FEATURE_CHECK_UI_URL": self.ui,
            "FEATURE_CHECK_CAMERA_ROOT": str(self.cameras),
            "FEATURE_CHECK_CAMERAS": str(self.artifacts / "cameras.json"),
            "FEATURE_CHECK_SCENARIOS": str(SCENARIO_DIR / "scenarios.json"),
            "FEATURE_CHECK_ADMIN_USERNAME": self.admin["username"],
            "FEATURE_CHECK_ADMIN_PASSWORD": self.admin["password"],
        }
        problems = []
        results: dict[str, Any] = {}
        if sorted(BACKEND_GOLDEN.glob("**/test_*.py")):
            junit = self.artifacts / "golden-backend.xml"
            result = self._run(
                [
                    "uv",
                    "run",
                    "pytest",
                    str(BACKEND_GOLDEN.relative_to(REPO_ROOT)),
                    f"--junitxml={junit}",
                ],
                check=False,
                timeout=1800,
                env=env,
            )
            (self.artifacts / "golden-backend.log").write_text(
                result.stdout + result.stderr, encoding="utf-8"
            )
            results["backend"] = "ok" if result.returncode == 0 else f"exit {result.returncode}"
            if result.returncode != 0:
                problems.append(f"golden: backend/tests/golden exited {result.returncode}")
        else:
            results["backend"] = "no specs yet"
        if PLAYWRIGHT_CONFIG.exists() and re.search(
            r"name:\s*['\"]golden['\"]", PLAYWRIGHT_CONFIG.read_text(encoding="utf-8")
        ):
            report = self.artifacts / "golden-playwright"
            result = self._run(
                ["npx", "playwright", "test", "--project=golden", f"--output={report}"],
                check=False,
                timeout=1800,
                env=env,
                cwd=REPO_ROOT / "frontend",
            )
            (self.artifacts / "golden-playwright.log").write_text(
                result.stdout + result.stderr, encoding="utf-8"
            )
            results["playwright"] = "ok" if result.returncode == 0 else f"exit {result.returncode}"
            if result.returncode != 0:
                problems.append(f"golden: the golden Playwright project exited {result.returncode}")
        else:
            results["playwright"] = "no golden project yet"
        _log(f"golden paths: {results}")
        self.summary["results"]["golden"] = results
        return problems

    def collect(self) -> None:
        logs = self.deployment("logs", "--no-color", "--timestamps", check=False, echo=False)
        (self.artifacts / "compose.log").write_text(logs.stdout + logs.stderr, encoding="utf-8")
        ps = self.deployment("ps", "-a", "--format", "json", check=False, echo=False)
        (self.artifacts / "ps.json").write_text(ps.stdout, encoding="utf-8")

    def teardown(self, before: Snapshot) -> list[str]:
        self.deployment("down", "-v", check=False, timeout=600)
        after = self.snapshot()
        self._write("snapshot-after.json", after.to_json())
        problems = postflight(before, after, project=self.project)
        self.summary["results"]["postflight"] = problems or "ok"
        _log(
            "postflight: "
            + (
                "ok, every pre-existing container and volume untouched"
                if not problems
                else "CHANGED"
            )
        )
        return problems

    def _write(self, name: str, data: Any) -> None:
        (self.artifacts / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


class Refused(HarnessError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("preflight refused the run")
        self.problems = problems


def _http(method: str, url: str, payload: Any = None, timeout: float = 15) -> tuple[int, Any]:
    """(status, JSON body or text); status 0 when nothing answered.

    Only the run's own published ports, which all bind 127.0.0.1.
    """
    if urllib.parse.urlsplit(url).hostname != "127.0.0.1":
        raise HarnessError(f"the harness talks only to its own 127.0.0.1 ports, not {url}")
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(  # noqa: S310 (127.0.0.1, checked above)
        url, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        # nosemgrep: ssrf-requests - only the run's own 127.0.0.1 ports, checked above
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
    except (urllib.error.URLError, OSError) as error:
        return 0, str(error)
    try:
        return status, json.loads(raw or b"null")
    except json.JSONDecodeError:
        return status, raw.decode(errors="replace")


def _scenarios() -> list[dict[str, Any]]:
    book = json.loads((SCENARIO_DIR / "scenarios.json").read_text(encoding="utf-8"))
    return list(book["scenarios"])


def _scenario(name: str) -> dict[str, Any]:
    for scenario in _scenarios():
        if scenario["name"] == name:
            return scenario
    raise HarnessError(f"no scenario named {name} in {SCENARIO_DIR / 'scenarios.json'}")


def drop(image: Path, camera: str, camera_root: Path) -> Path:
    """Copy an image into a camera folder of the run, as an upload would land.

    The backend's file watcher picks it up on create and waits for its size
    to settle. It deduplicates by content for 300 s, so dropping the same
    bytes twice inside five minutes yields one event.
    """
    if not camera_root.is_dir():
        raise HarnessError(f"camera root {camera_root} does not exist")
    folder = camera_root / camera
    folder.mkdir(exist_ok=True)
    target = folder / image.name
    shutil.copyfile(image, target)
    return target


def run_fake(args: argparse.Namespace) -> int:
    run = Run(engine=args.engine, root=args.root, image_tag=args.image_tag, mode="fake")
    before = run.prepare()
    status = 0
    try:
        run.render(before)
        run.up()
        run.register_admin()
        run.seed_cameras()
        problems = run.check_isolation()
        problems += run.smoke()
        if not problems:
            problems += run.golden()
        if problems:
            for problem in problems:
                _log(f"FAIL {problem}")
            status = 1
    except Refused as refused:
        for problem in refused.problems:
            _log(f"REFUSED {problem}")
        status = 2
    except (HarnessError, subprocess.TimeoutExpired) as error:
        _log(f"FAIL {error}")
        status = 1
    finally:
        if run.started:
            run.collect()
            if run.teardown(before):
                for problem in run.summary["results"]["postflight"]:
                    _log(f"URGENT {problem}")
                status = 3
        run.summary["exit"] = status
        run._write("summary.json", run.summary)
        _log(f"summary: {run.artifacts / 'summary.json'} (exit {status})")
    return status


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="feature-check.sh", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--fake", action="store_true", help="the CI stack with the fake AI (O2.1)")
    modes.add_argument("--real", action="store_true", help="real models through agent-gpu")
    parser.add_argument(
        "--image-tag",
        default=os.environ.get("FEATURE_CHECK_IMAGE_TAG", "latest"),
        help="backend/frontend image tag (default: $FEATURE_CHECK_IMAGE_TAG or latest)",
    )
    parser.add_argument(
        "--engine",
        default=os.environ.get("FEATURE_CHECK_ENGINE", "docker"),
        choices=("docker", "podman"),
        help="container engine (default: $FEATURE_CHECK_ENGINE or docker)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(os.environ.get("FEATURE_CHECK_ROOT", Path("/tmp") / "hsi-feature-check")),  # noqa: S108
        help="where run directories go (default: $FEATURE_CHECK_ROOT or /tmp/hsi-feature-check)",
    )
    drop_parser = sub.add_parser("drop", help="drop an image into a camera folder of a run")
    drop_parser.add_argument("image", type=Path)
    drop_parser.add_argument("camera")
    args = parser.parse_args(argv)

    if args.command == "drop":
        root = os.environ.get("FEATURE_CHECK_CAMERA_ROOT")
        if not root:
            parser.error(
                "drop needs FEATURE_CHECK_CAMERA_ROOT (set by the harness for golden specs)"
            )
        print(drop(args.image, args.camera, Path(root)))
        return 0
    if args.real:
        _log(
            "--real is not built yet: it waits on the owner's answers to the real-tier "
            "questions on PR #6961 (the detector, the smoke check, the host)"
        )
        return 2
    if not args.fake:
        parser.error("choose --fake or --real")
    return run_fake(args)


if __name__ == "__main__":
    sys.exit(main())
