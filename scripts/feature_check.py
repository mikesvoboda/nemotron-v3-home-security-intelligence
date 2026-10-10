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

``--real`` (owner ruling 66) is the same test deployment with the real VLM in
place of the fake one, served on the GB300 through ``agent-gpu``
(:class:`AgentGpu`; ``docs/uplevel/operator.md``, "The agent-gpu path"); the
fake detector stays. It checks the weights against the production pin before
serving, lets the backend reach the host only on the port ``agent-gpu run``
printed, and removes the VLM after the run, also after a failure.

Exit codes: 0 green; 1 a check of the run failed, or teardown left the run's
own containers or volumes (or, on ``--real``, its VLM); 2 the preflight
refused and the test deployment never started; 3 the postflight found a
pre-existing container or volume changed (report it on the urgent path; the
harness restores nothing); 4 the mode cannot run here (``--real`` without
``agent-gpu``).

Standard library only, so it runs in CI, in the operator sandbox and on a host
without the project's virtualenv.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import html
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
PROJECT_PREFIX = "hsi-check-"

EXIT_OK = 0
EXIT_FAILED = 1  # a check of the run failed
EXIT_REFUSED = 2  # the preflight refused; the test deployment never started
EXIT_CHANGED = 3  # the postflight found a pre-existing container or volume changed
EXIT_UNAVAILABLE = 4  # the mode cannot run here (--real without agent-gpu)

# The harness smoke check: one scenario image in, one event out. Its scenario
# has image bytes of its own: the backend deduplicates images by content for
# 300 s across cameras, so a golden path dropping any other scenario image
# right after the smoke check still gets its event.
SMOKE_SCENARIO = "harness-smoke"

# --real (owner ruling 66, #6854): the real VLM, served on the GB300 through
# agent-gpu (docs/uplevel/operator.md, "The agent-gpu path"), with the fake
# detector kept. Its test deployment is --fake's without the fake ai-vlm.
REAL_SERVICES = tuple(name for name in FAKE_SERVICES if name != "ai-vlm")
PROD_STACK = REPO_ROOT / "docker-compose.prod.yml"
VLM_DOCKERFILE = REPO_ROOT / "ai" / "vlm" / "Dockerfile"
# The production pin and its sha256 (operator.md step 1). The library also
# holds a Q8_0 build of the model itself; it is not the pin.
VLM_LIBRARY_DIR = "qwen3vl-8b-instruct-q4km"
VLM_MODEL = "Qwen3VL-8B-Instruct-Q4_K_M.gguf"
VLM_MMPROJ = "mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf"
VLM_WEIGHTS = {
    VLM_MODEL: "67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2",  # pragma: allowlist secret
    VLM_MMPROJ: "c6ba85508d82f42590e6eb77d5340369ab6fecf107a7561d809523d8aa5f3bfd",  # pragma: allowlist secret
}
# operator.md steps 2-3: the GB300's CUDA architecture, the VLM's container
# port, its VRAM declaration (it measured 9,056 MiB actual) and its lease.
VLM_CUDA_ARCHITECTURES = "103"
VLM_PORT = 8098
VLM_VRAM_GIB = 14
VLM_TTL = 12
# The runner publishes a container port on the host from this pool and prints
# `port <container port> -> http://host.docker.internal:<host port>`.
AGENT_GPU_PORTS = range(18100, 18200)
# The verdicts a model gives: the event verification schema's enum
# (backend/api/schemas/event_verification.py) less verification_failed.
MODEL_VERDICTS = frozenset({"confirmed", "rejected", "uncertain"})

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

# The preflight fails closed: a test deployment may use only the keys it has a
# rule for. These are the keys the CI stack and the fake-AI overlay render
# (plus container_name and extra_hosts, which have refusal rules of their
# own); anything else (volumes_from, devices, cap_add, ipc, userns_mode,
# cgroup, secrets ...) is refused until a rule for it is written here.
SERVICE_KEYS = frozenset(
    {
        "build",
        "cap_drop",
        "command",
        "container_name",
        "depends_on",
        "deploy",
        "entrypoint",
        "environment",
        "extra_hosts",
        "healthcheck",
        "image",
        "networks",
        "ports",
        "pull_policy",
        "read_only",
        "security_opt",
        "sysctls",
        "tmpfs",
        "user",
        "volumes",
    }
) | frozenset(HOST_LEVEL_ACCESS)
TOP_LEVEL_KEYS = frozenset({"name", "services", "networks", "volumes"})
BUILD_KEYS = frozenset({"context", "dockerfile", "args", "target"})
SECURITY_OPTS = frozenset({"no-new-privileges:true", "no-new-privileges"})

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


def _normal(path: str) -> str:
    """normpath, with a doubled leading slash collapsed too (POSIX keeps it,
    and compose renders ``//run`` as written)."""
    return os.path.normpath(re.sub(r"/{2,}", "/", path))


def is_engine_socket(path: str | None) -> bool:
    """True for a container-engine socket or a directory that holds one."""
    if not path:
        return False
    normal = _normal(path)
    return (
        normal in ("/", "/var")
        or _ENGINE_SOCKET.search(normal) is not None
        or _ENGINE_SOCKET_DIR.match(normal) is not None
    )


def _inside(path: str, root: str) -> bool:
    candidate = PurePosixPath(_normal(path))
    base = PurePosixPath(_normal(root))
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

    @property
    def running_binds(self) -> frozenset[tuple[str, bool]]:
        """(host path, writable) for every bind a running container holds."""
        return frozenset(
            (m.source, m.writable)
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


def snapshot_brief(snapshot: Snapshot) -> dict[str, list[str]]:
    """The preflight snapshot as the summary prints it: each container's name,
    state and start time, and each volume (the full one is in artifacts/)."""
    return {
        "containers": [f"{c.name} {c.status} {c.started_at}" for c in snapshot.containers],
        "volumes": sorted(snapshot.volumes),
    }


# ---------------------------------------------------------------------------
# The test deployment
# ---------------------------------------------------------------------------


def as_test_deployment(
    base: Mapping[str, Any], *, project: str, run_dir: Path, vlm_url: str | None = None
) -> dict[str, Any]:
    """Turn the rendered CI + fake stack into this run's test deployment.

    Keeps only :data:`FAKE_SERVICES`; moves every published port to an
    engine-assigned host port on 127.0.0.1; names networks and volumes after
    the run's project; points the backend's camera directory at
    ``<run_dir>/cameras`` and turns its orchestrator off. Everything else
    (a fixed ``container_name``, a bind mount) is left for the preflight to
    judge, so nothing is silently dropped.

    With ``vlm_url`` (``--real``) the fake ai-vlm stays out and the backend
    calls the VLM ``agent-gpu run`` serves there; the fake detector stays.
    No ``extra_hosts`` entry is added: host.docker.internal resolves in the
    sandbox's Docker on its own, and ``host-gateway`` would name the sandbox,
    not the host the runner publishes on.
    """
    keep = FAKE_SERVICES if vlm_url is None else REAL_SERVICES
    services = base.get("services") or {}
    missing = [name for name in keep if name not in services]
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
    for name in keep:
        service = copy.deepcopy(services[name])
        depends_on = service.get("depends_on")
        if vlm_url is not None and isinstance(depends_on, dict):
            depends_on.pop("ai-vlm", None)
        for dependency in depends_on or {}:
            if dependency not in keep:
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
    if vlm_url is not None:
        environment["AI_VLM_URL"] = vlm_url
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


def _live_clashes(source: str, live_binds: Iterable[tuple[str, bool]]) -> list[str]:
    """Live bind paths a run's writable ``source`` would share.

    The run's path containing a live bind means the run could write into it.
    The run's path inside a live bind shares it when that bind is writable,
    or when it is a read-only view narrower than the whole filesystem: a
    live container reading a directory (a watched camera folder) may ingest
    what the run writes there. A read-only bind of ``/`` (node-exporter's
    ``/:/host:ro``) only reads, and would otherwise refuse every run.
    """
    clashes = set()
    for live, live_writable in live_binds:
        if _inside(live, source) or (
            _inside(source, live) and (live_writable or _normal(live) != "/")
        ):
            clashes.add(live)
    return sorted(clashes)


def _service_setting_problems(name: str, service: Mapping[str, Any], services: Any) -> list[str]:
    """What fails the allowlist: unknown keys, and values of known keys that
    reach beyond the run (another container's network, an unconfined profile,
    a build that runs with the host's network)."""
    problems = []
    for key in sorted(service):
        if key not in SERVICE_KEYS:
            problems.append(
                f"{name}: {key} is a setting the preflight has no rule for; "
                "a test deployment refuses it"
            )
    mode = service.get("network_mode")
    if mode not in (None, "host", "none", "bridge", "default") and not (
        str(mode).startswith("service:") and str(mode).split(":", 1)[1] in services
    ):
        problems.append(f"{name}: network_mode: {mode} joins a network the run does not own")
    pid = service.get("pid")
    if pid not in (None, "host"):
        problems.append(f"{name}: pid: {pid} shares another container's processes")
    for entry in service.get("security_opt") or []:
        if str(entry) not in SECURITY_OPTS:
            problems.append(f"{name}: security_opt {entry} is not one the preflight allows")
    build = service.get("build")
    if isinstance(build, Mapping):
        for key in sorted(set(build) - BUILD_KEYS):
            problems.append(f"{name}: build.{key} is a build setting the preflight has no rule for")
    return problems


def _top_level_problems(rendered: Mapping[str, Any], project: str) -> list[str]:
    problems = []
    for key in sorted(rendered):
        if key not in TOP_LEVEL_KEYS and not key.startswith("x-"):
            problems.append(f"{key}: a top-level section the preflight has no rule for")
    for key, network in sorted((rendered.get("networks") or {}).items()):
        network = network or {}
        own = f"{project}_{key}"
        if network.get("external"):
            problems.append(f"network {key}: external, shared beyond this run")
        elif network.get("name", own) != own:
            problems.append(f"network {key}: named {network.get('name')}, not the run's own {own}")
        elif network.get("driver") not in (None, "bridge"):
            problems.append(
                f"network {key}: driver {network.get('driver')}; a test deployment uses bridge"
            )
    for key, volume in sorted((rendered.get("volumes") or {}).items()):
        volume = volume or {}
        if volume.get("external"):
            continue  # refused where a service mounts it
        if volume.get("driver_opts"):
            problems.append(
                f"volume {key}: driver_opts can make a named volume a host bind; "
                "a test deployment refuses them"
            )
        elif volume.get("driver") not in (None, "local"):
            problems.append(
                f"volume {key}: driver {volume.get('driver')}; a test deployment uses local"
            )
    return problems


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

    Fails closed: any service key, build key, top-level section, network or
    volume option without a rule here is refused. Refuses a writable bind
    mount outside ``run_dir``, any engine socket, the host's network,
    processes or devices, a network or namespace the run does not own, a
    configured host address on any port but ``allowed_host_ports`` (the ports
    ``agent-gpu run`` printed; none on ``--fake``), a backend whose
    orchestrator is not off, and any overlap with the snapshot: the project,
    a container name, a host port, a volume, or a host path a running
    container also mounts (:func:`_live_clashes`).
    """
    problems: list[str] = _top_level_problems(rendered, project)
    run_root = str(run_dir)
    live_names = snapshot.names
    live_ports = snapshot.host_ports
    live_binds = snapshot.running_binds
    volumes = rendered.get("volumes") or {}

    if project in snapshot.projects:
        owners = sorted(c.name for c in snapshot.containers if c.project == project)
        problems.append(
            f"project {project} already has containers on this machine: {', '.join(owners)}"
        )

    services = rendered.get("services") or {}
    for name in sorted(services):
        service = services[name] or {}
        problems += _service_setting_problems(name, service, services)

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
                    clashes = _live_clashes(source, live_binds)
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


def _test_deployment_name(name: str | None) -> bool:
    return bool(name) and str(name).startswith(PROJECT_PREFIX)


def postflight(before: Snapshot, after: Snapshot, *, project: str) -> list[str]:
    """Every pre-existing container or volume the run changed (exit 3).

    Another test deployment's containers and volumes (another run on the same
    machine) come and go on their own; they are not live, so they are not
    held to the snapshot.
    """
    problems = []
    now_by_id = {c.id: c for c in after.containers}
    for container in before.containers:
        if _test_deployment_name(container.project):
            continue
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
        if not _test_deployment_name(volume):
            problems.append(f"volume {volume}: missing after the run")
    return problems


def leftovers(before: Snapshot, after: Snapshot, *, project: str) -> list[str]:
    """What of the run's own teardown left behind (a failed run, exit 1)."""
    problems = [
        f"{container.name}: the run's container is still here after teardown"
        for container in after.containers
        if container.project == project
    ]
    problems += [
        f"volume {volume}: the run's volume is still here after teardown"
        for volume in sorted(after.volumes - before.volumes)
        if volume.startswith(f"{project}_")
    ]
    return problems


_TESTCASE = re.compile(r"<testcase\b([^>]*?)(?:/>|>(.*?)</testcase>)", re.DOTALL)
_ATTRIBUTE = re.compile(r'([\w:-]+)="([^"]*)"')
_CDATA = re.compile(r"<!\[CDATA\[.*?\]\]>", re.DOTALL)


def junit_results(path: Path) -> dict[str, str]:
    """Each spec of a golden suite's JUnit report: passed, failed or skipped.

    The report is this run's own. It is read with patterns, not an XML
    parser, so no DTD or entity in it is ever processed; a spec's printed
    output (CDATA) is not mistaken for its outcome. No report, no specs.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    results = {}
    for match in _TESTCASE.finditer(text):
        attributes = {key: html.unescape(value) for key, value in _ATTRIBUTE.findall(match[1])}
        body = _CDATA.sub("", match[2] or "")
        name = f"{attributes.get('classname', '')}::{attributes.get('name', '')}"
        if re.search(r"<(?:failure|error)\b", body):
            results[name] = "failed"
        elif re.search(r"<skipped\b", body):
            results[name] = "skipped"
        else:
            results[name] = "passed"
    return results


def smoke_problems(
    events: Sequence[Mapping[str, Any]],
    *,
    camera: str,
    scenario: Mapping[str, Any] | None = None,
    served_model: str | None = None,
) -> list[str]:
    """The harness smoke check's judgement of the events on its camera.

    On ``--fake``, one event with the ``scenario``'s verdict and risk score.
    On ``--real`` the verdict is the model's own, not the scenario's (Q2 on
    #6961), so: one event whose verification names ``served_model`` (the stem
    of /props' model_path, as the backend records it) with a verdict the
    model gave (:data:`MODEL_VERDICTS`).
    """
    if len(events) != 1:
        return [f"smoke: expected one event on {camera}, found {len(events)}"]
    event = events[0]
    verification = event.get("verification") or {}
    verdict = verification.get("verdict")
    problems = []
    if scenario is not None:
        expected = scenario["verdict"]
        if verdict != expected["verdict"]:
            problems.append(f"smoke: verdict {verdict!r}, scenario says {expected['verdict']!r}")
        if event.get("risk_score") != expected["risk_score"]:
            problems.append(
                f"smoke: risk_score {event.get('risk_score')!r}, "
                f"scenario says {expected['risk_score']!r}"
            )
    if served_model is not None:
        if verdict not in MODEL_VERDICTS:
            problems.append(
                f"smoke: verdict {verdict!r}; a model's verdict is one of "
                f"{', '.join(sorted(MODEL_VERDICTS))}"
            )
        model = verification.get("model_id")
        if model != served_model:
            problems.append(
                f"smoke: the verdict names model {model!r}, not the served {served_model!r}"
            )
    return problems


# ---------------------------------------------------------------------------
# The real tier: the VLM through agent-gpu
# ---------------------------------------------------------------------------


def real_unavailable(environ: Mapping[str, str]) -> str | None:
    """Why ``--real`` cannot run here, or None. It serves models only through
    ``agent-gpu`` (owner ruling 66); there is no host-GPU mode."""
    if shutil.which("agent-gpu", path=environ.get("PATH")) is None:
        return (
            "--real serves the VLM only through agent-gpu (owner ruling 66), and "
            "agent-gpu is not on PATH here. It runs in the uplevel-operator sandbox: "
            'docs/uplevel/operator.md, "The agent-gpu path".'
        )
    if not environ.get("AGENT_GPU_LIBRARY"):
        return (
            "--real reads the VLM's weights from $AGENT_GPU_LIBRARY, the shared model "
            "library, which is not set here (agent-dgx --gpu sets it)."
        )
    return None


def weight_digests(directory: Path) -> dict[str, str]:
    """sha256 of each ``*.gguf`` in ``directory``, as ``sha256sum *.gguf``."""
    digests = {}
    for path in sorted(directory.glob("*.gguf")):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        digests[path.name] = digest.hexdigest()
    return digests


def weight_problems(found: Mapping[str, str]) -> list[str]:
    """operator.md step 1: stop unless the files are exactly the pin."""
    problems = []
    for name, digest in VLM_WEIGHTS.items():
        if name not in found:
            problems.append(f"weights: {name} is missing from the library's {VLM_LIBRARY_DIR}/")
        elif found[name] != digest:
            problems.append(f"weights: {name} has sha256 {found[name]}; the pin is {digest}")
    for name in sorted(set(found) - set(VLM_WEIGHTS)):
        problems.append(f"weights: {VLM_LIBRARY_DIR}/ also holds {name}, which is not the pin")
    return problems


_DEFAULTED = re.compile(r"\$\{(\w+)(:?-)([^}]*)\}")


def vlm_run_environment(prod: Sequence[str] | Mapping[str, Any]) -> list[str]:
    """``--env`` for ``agent-gpu run`` (operator.md step 3): the library's pin,
    then each other ai-vlm variable of docker-compose.prod.yml verbatim, at its
    default, since the run's env file sets none of them. ``prod`` is that
    environment as written (``config --no-interpolate``)."""
    if isinstance(prod, Mapping):
        entries = [key if value is None else f"{key}={value}" for key, value in prod.items()]
    else:
        entries = [str(entry) for entry in prod]
    library = f"/library/{VLM_LIBRARY_DIR}"
    environment = [f"MODEL_PATH={library}/{VLM_MODEL}", f"MMPROJ_PATH={library}/{VLM_MMPROJ}"]
    for entry in entries:
        key, sep, value = entry.partition("=")
        if key in ("MODEL_PATH", "MMPROJ_PATH"):
            continue
        resolved = _DEFAULTED.sub(lambda match: match.group(3), value)
        if not sep or "$" in resolved:
            raise HarnessError(
                f"ai-vlm's {entry} has no default in {PROD_STACK.name}, and the run sets "
                "no VLM variable"
            )
        environment.append(f"{key}={resolved}")
    return environment


def dockerfile_bases(text: str) -> list[str]:
    """The images a Dockerfile's FROM lines pull, in order, less the stages it
    builds itself: ``agent-gpu build`` never pulls (operator.md step 2)."""
    bases: list[str] = []
    stages: set[str] = set()
    for match in re.finditer(r"(?im)^\s*FROM\s+(?:--\S+\s+)*(\S+)(?:\s+AS\s+(\S+))?", text):
        image, stage = match.group(1), match.group(2)
        if "$" in image:
            raise HarnessError(f"FROM {image} names its base through a build argument")
        if image.lower() not in stages and image not in bases:
            bases.append(image)
        if stage:
            stages.add(stage.lower())
    return bases


def agent_gpu_url(output: str, container_port: int = VLM_PORT) -> tuple[str, int]:
    """The URL ``agent-gpu run`` printed for ``container_port``, and its port.

    The runner publishes from :data:`AGENT_GPU_PORTS` on the host's loopback,
    reached as host.docker.internal. Anything else could be the live stack's
    API, database or engine, so the run refuses it.
    """
    match = re.search(rf"(?m)^\s*port {container_port} -> (\S+)\s*$", output)
    if match is None:
        raise HarnessError(
            f"agent-gpu run printed no 'port {container_port} -> <url>' line: "
            f"{output.strip()[-500:]!r}"
        )
    url = match.group(1)
    parts = urllib.parse.urlsplit(url)
    try:
        port = parts.port
    except ValueError:
        port = None
    if (
        parts.scheme != "http"
        or parts.hostname != "host.docker.internal"
        or port is None
        or port not in AGENT_GPU_PORTS
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
    ):
        raise HarnessError(
            f"agent-gpu run printed {url}; a run reaches only "
            f"http://host.docker.internal:<{AGENT_GPU_PORTS.start}-{AGENT_GPU_PORTS.stop - 1}>"
        )
    return f"http://host.docker.internal:{port}", port


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
        self.project = f"{PROJECT_PREFIX}{stamp}-{secrets.token_hex(3)}"
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
        commit = self._run(["git", "rev-parse", "HEAD"], check=False, echo=False, env=os.environ)
        self.summary["commit"] = commit.stdout.strip() or None
        before = self.snapshot()
        self._write("snapshot-before.json", before.to_json())
        self.summary["snapshot_before"] = snapshot_brief(before)
        _log(
            f"snapshot: {len(before.containers)} containers "
            f"({sum(c.running for c in before.containers)} running), {len(before.volumes)} volumes"
        )
        return before

    def render(self, before: Snapshot, vlm: AgentGpu | None = None) -> None:
        base = json.loads(
            self.compose([CI_STACK, FAKE_OVERLAY], "config", "--format", "json").stdout
        )
        deployment = as_test_deployment(
            base, project=self.project, run_dir=self.dir, vlm_url=vlm.url if vlm else None
        )
        self.compose_file.write_text(json.dumps(deployment, indent=2) + "\n", encoding="utf-8")
        rendered = json.loads(self.deployment("config", "--format", "json").stdout)
        self._write("rendered.json", rendered)
        problems = preflight(
            rendered,
            project=self.project,
            run_dir=self.dir,
            snapshot=before,
            host_addresses=self.host_addresses(),
            # On --real, the one port agent-gpu run printed; none on --fake.
            allowed_host_ports=frozenset({vlm.host_port}) if vlm and vlm.host_port else frozenset(),
        )
        self.summary["results"]["preflight"] = problems or "ok"
        if problems:
            raise Refused(problems)
        _log("preflight: ok")
        self.summary["images"] = {
            name: service.get("image") for name, service in rendered["services"].items()
        }

    def up(self, vlm: AgentGpu | None = None) -> None:
        self.started = True
        try:
            self.deployment("up", "-d", "--wait", "--wait-timeout", "900", timeout=1500)
        except HarnessError:
            # The backend's health check calls the VLM, so on --real an
            # unreachable VLM fails `up --wait` first; name that reason if so.
            if vlm is not None:
                self.check_vlm_reach(str(vlm.url))
            raise
        self.api = self._address("backend", 8000)
        self.ui = self._address("frontend", 8080)
        _log(f"up: api {self.api}, ui {self.ui}")
        self.summary["urls"] = {"api": self.api, "ui": self.ui}
        if vlm is not None:
            self.check_vlm_reach(str(vlm.url))
            return
        props = _http("GET", self._address("ai-vlm", 8098) + "/props")
        if props[0] == 200 and isinstance(props[1], Mapping):
            self.summary["build_info"] = props[1].get("build_info")
            self.summary["model_path"] = props[1].get("model_path")

    def check_vlm_reach(self, url: str) -> None:
        """The backend reaches the VLM agent-gpu serves (operator.md step 4);
        without this, an unreachable VLM shows only as a missing verdict."""
        probe = self.deployment(
            "exec",
            "-T",
            "backend",
            "python",
            "-c",
            "import sys, urllib.request; "
            "print(urllib.request.urlopen(sys.argv[1] + '/health', timeout=10).status)",
            url,
            check=False,
        )
        if probe.stdout.strip().splitlines()[-1:] != ["200"]:
            raise HarnessError(
                f"the backend cannot reach the VLM at {url}: "
                f"{(probe.stderr or probe.stdout).strip()[-1000:]}"
            )
        _log(f"the backend reaches the VLM at {url}")

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

    def smoke(self, vlm: AgentGpu | None = None) -> list[str]:
        """One fixture image in, one event out (:func:`smoke_problems`)."""
        scenario = _scenario(SMOKE_SCENARIO)
        camera = self.camera_ids[SMOKE_SCENARIO]
        image = drop(SCENARIO_DIR / scenario["image"], SMOKE_SCENARIO, self.cameras)
        _log(f"smoke: dropped {image.relative_to(self.dir)}; waiting for its event")
        deadline = time.monotonic() + (300 if vlm is None else 600)
        events: list[Any] = []
        while time.monotonic() < deadline:
            status, body = _http("GET", self.api + f"/api/events?camera_id={camera}")
            events = body.get("items", []) if status == 200 and isinstance(body, Mapping) else []
            if events and (events[0].get("verification") or {}).get("verdict"):
                break
            time.sleep(5)
        self._write("smoke-events.json", events)
        problems = smoke_problems(
            events,
            camera=camera,
            scenario=scenario if vlm is None else None,
            served_model=vlm.served_model if vlm else None,
        )
        if not problems:
            event = events[0]
            verification = event.get("verification") or {}
            _log(
                f"smoke: ok, event {event.get('id')} verdict {verification.get('verdict')} "
                f"risk_score {event.get('risk_score')} model {verification.get('model_id')}"
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
            results["backend_specs"] = junit_results(junit)
            if result.returncode != 0:
                problems.append(f"golden: backend/tests/golden exited {result.returncode}")
        else:
            results["backend"] = "no specs yet"
        if PLAYWRIGHT_CONFIG.exists() and re.search(
            r"name:\s*['\"]golden['\"]", PLAYWRIGHT_CONFIG.read_text(encoding="utf-8")
        ):
            report = self.artifacts / "golden-playwright"
            junit = self.artifacts / "golden-playwright.xml"
            result = self._run(
                [
                    "npx",
                    "playwright",
                    "test",
                    "--project=golden",
                    f"--output={report}",
                    "--reporter=list,junit",
                ],
                check=False,
                timeout=1800,
                env={**env, "PLAYWRIGHT_JUNIT_OUTPUT_FILE": str(junit)},
                cwd=REPO_ROOT / "frontend",
            )
            (self.artifacts / "golden-playwright.log").write_text(
                result.stdout + result.stderr, encoding="utf-8"
            )
            results["playwright"] = "ok" if result.returncode == 0 else f"exit {result.returncode}"
            results["playwright_specs"] = junit_results(junit)
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

    def teardown(self, before: Snapshot) -> tuple[list[str], list[str]]:
        """``down -v`` for this project only; then (postflight, leftovers)."""
        self.deployment("down", "-v", check=False, timeout=600)
        after = self.snapshot()
        self._write("snapshot-after.json", after.to_json())
        changed = postflight(before, after, project=self.project)
        left = leftovers(before, after, project=self.project)
        self.summary["results"]["postflight"] = changed or "ok"
        self.summary["results"]["teardown"] = left or "ok"
        _log(
            "postflight: "
            + (
                "ok, every pre-existing container and volume untouched"
                if not changed
                else "CHANGED"
            )
        )
        return changed, left

    def _write(self, name: str, data: Any) -> None:
        (self.artifacts / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


class Refused(HarnessError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("preflight refused the run")
        self.problems = problems


class AgentGpu:
    """The real VLM of a ``--real`` run, served on the GB300 through
    ``agent-gpu`` (operator.md, "The agent-gpu path", steps 1-3 and 6): the
    weights checked against the pin, the image built once per state of
    ``ai/vlm/``, the container under the run's own name, and its removal."""

    vlm_image: str | None = None

    def __init__(self, run: Run) -> None:
        self.run = run
        self.name = f"{run.project}-vlm"
        self.started = False
        self.url: str | None = None
        self.host_port: int | None = None
        self.served_model: str | None = None

    def _cli(
        self, *args: str, check: bool = True, timeout: float | None = 300
    ) -> subprocess.CompletedProcess[str]:
        # The caller's whole environment: agent-gpu reaches its runner with it.
        return self.run._run(["agent-gpu", *args], check=check, timeout=timeout, env=os.environ)

    def _record(self, name: str, text: str) -> str:
        (self.run.artifacts / name).write_text(text, encoding="utf-8")
        return text

    def vlm_tree(self) -> str:
        """``ai/vlm/``'s tree hash, which tags its image; uncommitted changes
        there would build an image the tag does not name."""
        git = ["git", "-C", str(REPO_ROOT)]
        dirty = self.run._run([*git, "status", "--porcelain", "--", "ai/vlm"], env=os.environ)
        if dirty.stdout.strip():
            raise HarnessError(f"ai/vlm/ has uncommitted changes:\n{dirty.stdout.strip()}")
        return self.run._run(
            [*git, "rev-parse", "--short", "HEAD:ai/vlm"], env=os.environ
        ).stdout.strip()

    def prod_environment(self) -> Sequence[str] | Mapping[str, Any]:
        """ai-vlm's environment as docker-compose.prod.yml writes it (rendered
        without interpolation, never started)."""
        rendered = json.loads(
            self.run.compose(
                [PROD_STACK], "config", "--no-interpolate", "--format", "json", echo=False
            ).stdout
        )
        return rendered["services"]["ai-vlm"].get("environment") or []

    def prepare(self) -> None:
        """Steps 1-2: the weights against the pin, the budget, the image."""
        library = Path(os.environ["AGENT_GPU_LIBRARY"]) / VLM_LIBRARY_DIR
        _log(f"weights: sha256 of {library}/*.gguf")
        found = weight_digests(library)
        self.run.summary["weights"] = [f"{digest}  {name}" for name, digest in found.items()]
        problems = weight_problems(found)
        if problems:
            raise Refused(problems)
        _log("weights: the production pin")
        status = self._cli("status").stdout
        self.run.summary["agent_gpu"] = {
            "status_before": self._record("agent-gpu-status-before.txt", status)
        }
        tree = self.vlm_tree()
        self.vlm_image = f"ai-vlm:{tree}"
        images = self._cli("images", check=False).stdout
        if any("ai-vlm" in line and tree in line for line in images.splitlines()):
            _log(f"image: {self.vlm_image} is built for this state of ai/vlm/")
        else:
            for base in dockerfile_bases(VLM_DOCKERFILE.read_text(encoding="utf-8")):
                self._cli("pull", base, timeout=3600)
            self._cli(
                "build",
                "--context",
                "workspace:ai/vlm",
                "--tag",
                self.vlm_image,
                "--build-arg",
                f"CUDA_ARCHITECTURES={VLM_CUDA_ARCHITECTURES}",
                timeout=4 * 3600,
            )
        self.run.summary["vlm_image"] = self.vlm_image
        self.run.summary["vram"] = {"declared_gib": VLM_VRAM_GIB}

    def start(self) -> None:
        """Step 3: serve the pin from the library; read the URL run prints."""
        args = [
            "run",
            "--name",
            self.name,
            "--image",
            str(self.vlm_image),
            "--vram",
            str(VLM_VRAM_GIB),
            "--port",
            str(VLM_PORT),
            "--ttl",
            str(VLM_TTL),
            "--mount",
            "library:/library",
        ]
        for entry in vlm_run_environment(self.prod_environment()):
            args += ["--env", entry]
        self.started = True  # from here on, the run removes it whatever happens
        result = self._cli(*args, check=False, timeout=900)
        output = self._record("agent-gpu-run.txt", result.stdout + result.stderr)
        if result.returncode != 0:
            raise HarnessError(
                f"agent-gpu run exited {result.returncode} (admission is the runner's; "
                f"agent-gpu-status-before.txt has the budget): {output.strip()[-1000:]}"
            )
        self.url, self.host_port = agent_gpu_url(output)
        _log(f"vlm: {self.name} serves at {self.url}")

    def wait_ready(self, timeout: float = 900) -> None:
        """Step 3: /health answers 200, and /props' model_path is the pin."""
        url = str(self.url)
        deadline = time.monotonic() + timeout
        while True:
            status, _ = _http("GET", f"{url}/health", timeout=10, origin=url)
            if status == 200 or time.monotonic() >= deadline:
                break
            time.sleep(5)
        if status != 200:
            raise HarnessError(f"the VLM at {url} did not answer /health with 200 ({status})")
        status, props = _http("GET", f"{url}/props", timeout=10, origin=url)
        props = props if status == 200 and isinstance(props, Mapping) else {}
        model_path = str(props.get("model_path") or "")
        self.run.summary["build_info"] = props.get("build_info")
        self.run.summary["model_path"] = model_path
        expected = f"/library/{VLM_LIBRARY_DIR}/{VLM_MODEL}"
        if model_path != expected:
            raise HarnessError(
                f"the VLM serves {model_path or 'no model_path'}; the pin is {expected}"
            )
        self.served_model = PurePosixPath(model_path).stem
        serving = self._cli("ps", check=False).stdout
        vram = self.run.summary.setdefault("vram", {"declared_gib": VLM_VRAM_GIB})
        vram["serving"] = self._record("agent-gpu-ps-serving.txt", serving)
        _log(f"vlm: ready, build {props.get('build_info')}, model {model_path}")

    def teardown(self) -> list[str]:
        """Step 6: stop and remove the VLM; ``agent-gpu ps`` must then list
        none of the run's containers."""
        end = self._cli("ps", check=False).stdout
        vram = self.run.summary.setdefault("vram", {"declared_gib": VLM_VRAM_GIB})
        vram["at_end"] = self._record("agent-gpu-ps-end.txt", end)
        self._cli("stop", self.name, check=False, timeout=600)
        self._cli("rm", self.name, check=False, timeout=600)
        after = self._cli("ps", check=False)
        listing = self._record("agent-gpu-ps-after.txt", after.stdout + after.stderr)
        self.run.summary.setdefault("agent_gpu", {})["ps_after"] = listing
        problems = []
        if after.returncode != 0:
            problems.append(
                f"agent-gpu ps exited {after.returncode}, so whether {self.name} is gone is unknown"
            )
        elif re.search(rf"(?<![\w.-]){re.escape(self.name)}(?![\w.-])", after.stdout):
            problems.append(
                f"agent-gpu ps still lists {self.name}; remove it with agent-gpu rm {self.name}"
            )
        self.run.summary["results"]["agent_gpu"] = problems or "ok"
        _log(
            "agent-gpu: "
            + ("ok, agent-gpu ps lists none of this run's containers" if not problems else "LEFT")
        )
        return problems


# No proxies: urllib honours HTTP_PROXY, and a NO_PROXY without 127.0.0.1
# would send the harness's calls to a proxy instead of the run's own ports.
_LOOPBACK = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _http(
    method: str,
    url: str,
    payload: Any = None,
    timeout: float = 15,
    *,
    origin: str | None = None,
) -> tuple[int, Any]:
    """(status, JSON body or text); status 0 when nothing answered.

    Only the run's own published ports, which all bind 127.0.0.1, and on
    ``--real`` the one ``origin`` that ``agent-gpu run`` printed. That one is
    the host's loopback, which a sandbox reaches through its proxy, so the
    caller's proxy settings apply to it.
    """
    parts = urllib.parse.urlsplit(url)
    if origin is not None and f"{parts.scheme}://{parts.netloc}" == origin:
        opener = urllib.request.build_opener()
    elif parts.hostname == "127.0.0.1":
        opener = _LOOPBACK
    else:
        also = f" and {origin}" if origin else ""
        raise HarnessError(f"the harness talks only to its own 127.0.0.1 ports{also}, not {url}")
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(  # noqa: S310 (127.0.0.1 or the VLM, checked above)
        url, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with opener.open(request, timeout=timeout) as response:
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


def run_check(args: argparse.Namespace, *, mode: str) -> int:
    run = Run(engine=args.engine, root=args.root, image_tag=args.image_tag, mode=mode)
    before = run.prepare()
    vlm = AgentGpu(run) if mode == "real" else None
    status = EXIT_OK
    try:
        if vlm is not None:
            vlm.prepare()
            vlm.start()
            vlm.wait_ready()
        run.render(before, vlm)
        run.up(vlm)
        run.register_admin()
        run.seed_cameras()
        problems = run.check_isolation()
        problems += run.smoke(vlm)
        if not problems:
            problems += run.golden()
        if problems:
            for problem in problems:
                _log(f"FAIL {problem}")
            status = EXIT_FAILED
    except Refused as refused:
        for problem in refused.problems:
            _log(f"REFUSED {problem}")
        status = EXIT_REFUSED
    except Exception as error:  # noqa: BLE001 - whatever broke, teardown and the summary follow
        _log(f"FAIL {type(error).__name__}: {error}")
        status = EXIT_FAILED
    finally:
        if run.started:
            status = max(status, _finish(run, before))
        if vlm is not None and vlm.started:
            status = max(status, _finish_vlm(vlm))
        run.summary["exit"] = status
        run._write("summary.json", run.summary)
        # Printed whole, for the operator to paste (operator.md, "Posting results").
        print(json.dumps(run.summary, indent=2), flush=True)
        _log(f"summary: {run.artifacts / 'summary.json'} (exit {status})")
    return status


def _finish(run: Run, before: Snapshot) -> int:
    """Collect, tear down and run the postflight; nothing here may stop the
    teardown, and a postflight that cannot run counts as a change."""
    try:
        run.collect()
    except Exception as error:  # noqa: BLE001 - artifacts are best effort; teardown is not
        _log(f"collecting artifacts failed ({type(error).__name__}: {error}); tearing down")
    try:
        changed, left = run.teardown(before)
    except Exception as error:  # noqa: BLE001
        _log(f"URGENT teardown or postflight did not complete ({type(error).__name__}: {error})")
        return EXIT_CHANGED
    for problem in changed:
        _log(f"URGENT {problem}")
    for problem in left:
        _log(f"FAIL {problem}")
    if changed:
        return EXIT_CHANGED
    return EXIT_FAILED if left else EXIT_OK


def _finish_vlm(vlm: AgentGpu) -> int:
    """Remove the run's VLM after the test deployment is down, also after a
    failure (operator.md step 6)."""
    try:
        left = vlm.teardown()
    except Exception as error:  # noqa: BLE001 - say so, and leave the rm to the operator
        problem = f"removing {vlm.name} did not complete ({type(error).__name__}: {error})"
        _log(f"FAIL {problem}; agent-gpu rm {vlm.name}")
        vlm.run.summary["results"]["agent_gpu"] = [problem]
        return EXIT_FAILED
    for problem in left:
        _log(f"FAIL {problem}")
    return EXIT_FAILED if left else EXIT_OK


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
        unavailable = real_unavailable(os.environ)
        if unavailable:
            _log(unavailable)
            return EXIT_UNAVAILABLE
        return run_check(args, mode="real")
    if not args.fake:
        parser.error("choose --fake or --real")
    return run_check(args, mode="fake")


if __name__ == "__main__":
    sys.exit(main())
