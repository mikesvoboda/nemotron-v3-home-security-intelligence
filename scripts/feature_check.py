#!/usr/bin/env python3
"""The feature-check harness (O2.2): golden paths against a test deployment.

Run it through ``scripts/feature-check.sh``. ``--fake`` brings up the CI stack
(``docker-compose.ci.yml``) with the fake-AI overlay
(``docker-compose.fake-ai.yml``) as a **test deployment**, seeds its camera
directory, runs the harness smoke check and the golden paths, collects
artifacts and tears down. Usage and the golden-path contract are in
``docs/developer/testing.md``, "Feature check".

A test deployment touches nothing else on the machine (``docs/uplevel/packages/ops.md``
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
(:class:`AgentGpu`; ``docs/uplevel/roles/operator.md``, "The agent-gpu path"); the
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
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
# [O2.5 venue fixes, ruling 287] The stdlib relay both halves of the two-hop
# VLM relay run: the sidecar runs it from the vendored copy in the run dir,
# the host half reuses its pipe() and constants in-process. feature-check.sh
# execs this file under bare python3 with the repo root on no path, so the
# module is loaded by file path (importlib), the same containment the yaml
# import uses -- no sys.path edit, nothing else becomes importable.
_vlm_relay_spec = spec_from_file_location(
    "vlm_relay", REPO_ROOT / "scripts" / "uplevel" / "vlm_relay.py"
)
if _vlm_relay_spec is None or _vlm_relay_spec.loader is None:  # pragma: no cover - the file ships
    raise ImportError("scripts/uplevel/vlm_relay.py is missing from the checkout")
vlm_relay = module_from_spec(_vlm_relay_spec)
_vlm_relay_spec.loader.exec_module(vlm_relay)

CI_STACK = REPO_ROOT / "docker-compose.ci.yml"
FAKE_OVERLAY = REPO_ROOT / "docker-compose.fake-ai.yml"
# [r308a] The notification-sink overlay: the mail sink, the webhook sink and
# the Web Push service fake, rendered with the CI stack above (never alone —
# its services join ci-net, which only the CI stack defines).
SINKS_OVERLAY = REPO_ROOT / "docker-compose.sinks.yml"
# The webhook sink's marking, spelled once: the compose label carries it, the
# fail-closed check below enforces it, and the golden env records it
# (FEATURE_CHECK_SINKS_MODE).
SINKS_MODE = "on-this-network"
SCENARIO_DIR = REPO_ROOT / "backend" / "ai_contract" / "fake" / "scenario_fixtures"
SCRIPTS_DIR = REPO_ROOT / "scripts"
BACKEND_GOLDEN = REPO_ROOT / "backend" / "tests" / "golden"
FRONTEND = REPO_ROOT / "frontend"
FRONTEND_MODULES = FRONTEND / "node_modules"
PLAYWRIGHT_CONFIG = FRONTEND / "playwright.config.ts"
# [r282] The checked-in golden shard manifest (regen script:
# scripts/golden_shard_manifest.py; union/balance pinned by
# backend/tests/unit/scripts/test_golden_shard_manifest.py). The sharded
# fake tier reads it host-side and hands each shard its own spec files as
# FEATURE_CHECK_GOLDEN_FILES -- replacing Playwright's count-based --shard
# split, which measured 337/262/494/457 s across the shards (a 231 s spread
# a count split cannot close on a corpus this top-heavy).
GOLDEN_SHARDS_MANIFEST = FRONTEND / "golden-shards.json"
# The lock ruling 143 names as the golden image's version source.
PACKAGE_LOCK = FRONTEND / "package-lock.json"

# The services the golden paths need: the CI stack, the two fakes, and —
# since [r308a] — the three notification sinks (the mail sink, the webhook
# sink, the Web Push service fake), which the golden env reads back through.
# The sink overlay (docker-compose.sinks.yml) is rendered with the stack in
# :meth:`Run.render` and carries the on-this-network marking on the webhook
# sink, fail-closed in :func:`as_test_deployment`.
FAKE_SERVICES = (
    "postgres",
    "redis",
    "backend",
    "frontend",
    "ai-vlm",
    "ai-gateway",
    "mail-sink",
    "webhook-sink",
    "push-sink",
)
CAMERA_TARGET = "/cameras"
PROJECT_LABEL = "com.docker.compose.project"
PROJECT_PREFIX = "hsi-check-"
# Top-level sections whose entries compose names after the PROJECT, not the file. Measured on
# v5.5.1 by rendering under -p proja and rebooting the baked document under -p projb: all four
# keep `proja_<key>` after the rebind, so a boot file carrying them points at another run's
# objects (UR-133 isolation inverted into a cross-run `down -v` delete). prod declares only
# networks/volumes today, but the same file documents enabling Docker secrets
# (docker-compose.prod.yml:68-75, :1692-1720), and one constant keeps the naming site and the
# stripping site from disagreeing about the list.
PROJECT_NAME_SECTIONS = ("networks", "volumes", "configs", "secrets")

EXIT_OK = 0
EXIT_FAILED = 1  # a check of the run failed
EXIT_REFUSED = 2  # the preflight refused; the test deployment never started
EXIT_CHANGED = 3  # the postflight found a pre-existing container or volume changed
EXIT_UNAVAILABLE = 4  # the mode cannot run here (--real without agent-gpu)

# The golden Playwright leg's deadline, ruling 189. Measured, not guessed: the slowest of the
# last 10 GREEN `Feature check (fake AI)` runs on main took 1739 s from the leg's `$ docker run
# … --project=golden` line to its `golden paths:` summary (job 116184218975 at c1b804a82; the
# other nine 1492-1713 s). 1739 x 1.5 = 2608.5, rounded up to a minute = 2640. Across these 10
# legs the old 1800 kept only 61-308 s of margin (the ruling's earlier window said 66-306), and
# #7114 died at test #199 twice with exit 124. The OTHER three 1800 s timeouts are untouched and
# are not this leg: the backend golden pytest leg, the frontend `npm ci`, and the Playwright image
# pull (at ruling 189: 2169/2207/2261). This raises only the Playwright golden leg's ceiling.
# test_feature_check.py pins this value as a literal; moving it reds that pin on purpose.
GOLDEN_LEG_TIMEOUT_S = 2640

# The harness smoke check: one scenario image in, one event out. Its scenario
# has image bytes of its own: the backend deduplicates images by content for
# 300 s across cameras, so a golden path dropping any other scenario image
# right after the smoke check still gets its event.
SMOKE_SCENARIO = "harness-smoke"

# --real (owner ruling 66, #6854): the real VLM, served on the GB300 through
# agent-gpu (docs/uplevel/roles/operator.md, "The agent-gpu path"), with the fake
# detector kept. Its test deployment is --fake's without the fake ai-vlm.
REAL_SERVICES = tuple(name for name in FAKE_SERVICES if name != "ai-vlm")
PROD_STACK = REPO_ROOT / "docker-compose.prod.yml"
# The authored override the O2.5 spike posted and scripts/test_prodshape_override.py
# pins: the UR-133/134 transform (remapped ports, dropped engine-socket mounts,
# prefixed container names) applied as an extra `-f` so no production file and no
# CI leg is edited.
PROD_SHAPE_OVERRIDE = REPO_ROOT / "scripts" / "uplevel" / "docker-compose.prodshape.yml"
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
# Its container-name policy, from the broker's own refusal on the first
# --real run (#6961): at most 32 characters.
AGENT_GPU_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
VLM_NAME_PREFIX = "hsi-vlm-"
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
        "labels",
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
# [r308a] Labels a test deployment may carry: the marking namespace the CI
# notification sinks use. A label is inert inside the render, but compose
# stamps it onto the container, where `docker inspect` reads it — so anything
# outside this namespace (an automation hook, an external orchestrator's
# selector) is refused until a rule for it is written here.
LABEL_PREFIXES = ("uplevel.",)

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
    base: Mapping[str, Any],
    *,
    project: str,
    run_dir: Path,
    vlm_url: str | None = None,
    seeded: bool = False,
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
    for section in PROJECT_NAME_SECTIONS:
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
        # [r308a] The webhook sink's "on this network" marking is fail-closed:
        # a render whose webhook-sink lost the label refuses the run instead of
        # standing up an unmarked sink the golden env would still name as the
        # marked one. The label is what B4.2's per-channel flag reads; the
        # golden env carries the same string (``FEATURE_CHECK_SINKS_MODE``).
        if name == "webhook-sink":
            labels = service.get("labels") or {}
            if labels.get("uplevel.r308a/sink") != SINKS_MODE:
                raise HarnessError(
                    f"webhook-sink lacks the on-this-network marking: "
                    f"labels['uplevel.r308a/sink'] is {labels.get('uplevel.r308a/sink')!r}, "
                    f"not {SINKS_MODE!r}"
                )
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
    if seeded:
        environment["DEBUG"] = "true"
        environment["REQUEST_RECORDING_ENABLED"] = "true"
        environment["REQUEST_RECORDING_SAMPLE_RATE"] = "0.0"
        environment["HSI_FAULT_SEED"] = "1"
        if not any(entry.split(":", 1)[0].rstrip("/") == "/app/data" for entry in backend["tmpfs"]):
            backend["tmpfs"].append("/app/data:size=20m,mode=1777,uid=1000,gid=1000")
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
# Production shape (O2.5, ruling 162 item 2) — the resource-limits decision.
#
# The prod stack asks for `deploy.resources.limits` on 19 of its 21 services —
# every service that has a `deploy:` block has them — and a rootless engine
# cannot start a container that asks for a limit where no cgroup controller is
# delegated to the caller (the O2.5 spike's differential control). Unlike the CI
# path, the prod-shape run does NOT go through `as_test_deployment`/`preflight`.
# Measured, not assumed: the fail-closed key allowlist refuses the plain prod
# render with 46 problems (19 of them `restart`, which has no CI rule; plus
# `pid: host` on alloy and node-exporter, `devices`, `labels`, `cap_add`,
# `ulimits`, `userns_mode`, and three `security_opt: label=disable`), and the
# prod+override render still has 39. Widening that gate to fit would widen what a
# CI run may ask for, and `pid: host` is something the prod shape genuinely needs
# to observe the host, so it is not a refusal that can be made to go away. The
# authored override (scripts/uplevel/docker-compose.prodshape.yml, pinned by
# scripts/test_prodshape_override.py) is the UR-133/134 transform instead; limits
# are the one thing it deliberately leaves to run time, decided from the machine
# the operator runs on and recorded in the run summary.
# ---------------------------------------------------------------------------

# Ruling 162 item 2 names these strings verbatim; the run record carries them
# unchanged so the operator's paste and a reader's grep agree.
LIMITS_APPLIED = "limits: applied"
LIMITS_STRIPPED = "limits: not applied (no cgroup delegation)"
# prod.yml's limits are only ever `cpus:` and `memory:` (measured), i.e. the
# `cpu` and `memory` cgroup controllers. `cpuset` alone cannot run a `cpus:`
# limit, so the decision needs exactly these two delegated.
LIMIT_CGROUPS = frozenset({"cpu", "memory"})

# The pre-build is the longest step the prod-shape run takes: six services, from
# cold caches on a first run, one of them (`ai-gateway`) FROM a NVIDIA Triton
# server base. The precedent next door is `AgentGpu.prepare`, which allows 4 h
# for a single CUDA image; six images get one call at 6 h. Generous on purpose —
# a timer that fires mid-build costs the operator an hour and a rebuild, and a
# genuinely hung build is still reported, because `_run` answers a stall with
# exit 124 and the partial stream rather than raising.
PREBUILD_TIMEOUT_SECONDS = 6 * 3600


def read_subtree_control(
    *, proc_dir: Path = Path("/proc"), sys_dir: Path = Path("/sys/fs/cgroup")
) -> str:
    """The delegated-controller list for the cgroup a new container here inherits.

    The path comes from the caller's own `/proc/self/cgroup` — not a fixed
    location — because inside a sandbox the harness's cgroup is a slice, and the
    O2.5 spike measured that slice (it read `/sys/fs/cgroup$(cut -d: -f3
    /proc/self/cgroup)/cgroup.subtree_control` and found it EMPTY, which is why
    the spike needed `deploy: !reset null` on 18 services).

    Fail-closed by construction: anything unreadable returns "" — a malformed
    line, an absent file, a cgroup-v1 host with no `0::` line. "" makes
    :func:`decide_resource_limits` STRIP limits, and a container started without
    a limit it was promised can fail to start, while one started with no limit
    simply runs. The dangerous direction would be to guess "delegated".
    """
    try:
        lines = (proc_dir / "self" / "cgroup").read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    path = ""
    for line in lines:
        parts = line.split(":")
        if len(parts) == 3 and parts[0] == "0":  # cgroup v2: `0::<path>`
            path = parts[2]
            break
    if not path:
        return ""
    try:
        return (sys_dir / path.lstrip("/") / "cgroup.subtree_control").read_text(encoding="utf-8")
    except OSError:
        return ""


def cgroup_limits_usable(subtree_control: str) -> bool:
    """Can this machine enforce resource limits? True when the controllers a
    `deploy.resources.limits` needs are all delegated to us, read from the
    cgroup's `cgroup.subtree_control` contents (one space-separated list).

    Split on whitespace, not substring: `cpu` is a prefix of `cpuset`, so a
    substring test would call limits usable on a `cpuset`-only cgroup."""
    delegated = {token for token in subtree_control.split() if token}
    return LIMIT_CGROUPS.issubset(delegated)


# The engine sockets a container can drive the host with, wherever they are
# mounted. Measured against the prod render: prod mounts the caller's
# PODMAN_SOCKET twice -- on `backend` (into /var/run/podman/podman.sock) and on
# `alloy`, which interpolates the same variable into BOTH source and target, so a
# check that read only the target field would miss alloy outright.
ENGINE_SOCKET_TARGETS = frozenset(
    {"/var/run/docker.sock", "/var/run/podman/podman.sock", "/run/docker.sock"}
)


def engine_socket_mounts(
    rendered: Mapping[str, Any], *, socket_path: str
) -> list[tuple[str, str, str]]:
    """Every `(service, source, target)` in a rendered deployment that mounts an
    engine socket (UR-134), given the socket path this caller uses.

    This is the RUN-TIME twin of `scripts/test_prodshape_override.py`, and the two
    are not redundant. That test proves the committed override clears the mounts
    prod has in the checkout CI saw; a run happens against whatever checkout the
    operator brought, so a socket `docker-compose.prod.yml` grew since the override
    was authored is exactly what the static gate cannot see and this check can. The
    predicate reads source and target only -- never the mount's mode -- because a
    read-only socket is not a weaker capability: opening the socket is the whole
    attack, and `read_only: true` on the bind does not stop a container from
    connecting through it.
    """
    hits: list[tuple[str, str, str]] = []
    for name, service in (rendered.get("services") or {}).items():
        for mount in service.get("volumes") or []:
            if not isinstance(mount, Mapping):
                continue
            source = str(mount.get("source") or "")
            target = str(mount.get("target") or "")
            if (socket_path and source == socket_path) or target in ENGINE_SOCKET_TARGETS:
                hits.append((name, source, target))
    return hits


def strip_resource_limits(rendered: dict[str, Any]) -> int:
    """Drop each service's ``deploy.resources.limits`` in place and return how
    many services changed. Reservations are kept — the spike showed a LIMIT
    (``--memory``/``--cpus``) is what a rootless engine refuses, never a bare
    reservation — and a service with no ``deploy`` is not given one. The return
    count lets the caller prove the strip did something: an all-zero return is
    the difference between "no limits to strip" and "the strip is broken"."""
    changed = 0
    for service in (rendered.get("services") or {}).values():
        resources = (service.get("deploy") or {}).get("resources") or {}
        if "limits" in resources:
            del resources["limits"]
            changed += 1
    return changed


def boot_render(rendered: Mapping[str, Any]) -> dict[str, Any]:
    """The copy of a render that goes on disk for ``up`` to boot, with every baked
    object name removed so the ``-p`` at boot decides them.

    Measured on compose v5.5.1: ``config --format json`` writes the project name into
    the render three times over -- the top-level ``name``, and a ``name`` on every
    network and every volume (``security-net`` becomes ``<project>_security-net``).
    Feeding that render back under a DIFFERENT ``-p`` overrides the top-level name and
    nothing else: the nested names still point at the first project. So a run booted
    from such a file mounts -- and ``down -v`` DELETES -- another run's volumes, which
    is UR-133's own-project isolation turned into a cross-run delete. A render with
    those names stripped makes compose re-derive each object from the live ``-p``, so
    two runs produce two disjoint object sets. The copy keeps the caller's render
    intact: the artifact an operator reads should say what compose produced.
    """
    boot = copy.deepcopy(dict(rendered))
    boot.pop("name", None)
    for section in PROJECT_NAME_SECTIONS:
        for entry in (boot.get(section) or {}).values():
            if isinstance(entry, dict):
                entry.pop("name", None)
    return boot


def build_images(rendered: Mapping[str, Any], *, project: str) -> dict[str, str]:
    """The image each ``build:`` service will be looked for under when ``up`` runs.

    The prod stack carries six ``build:`` services, five of which declare no
    ``image:`` at all (grafana declares its own), so ``up --wait`` starts BUILDING
    during the boot. Measured on compose
    v5.5.1 (``config --images``, and a ``up --dry-run`` with the images absent): a
    service that declares ``image:`` is looked up under THAT name -- grafana's is
    hard-coded in ``docker-compose.prod.yml`` to
    ``nemotron-v3-home-security-intelligence-grafana:latest``, host-local by
    construction, so ``up`` tries to PULL it and the registry answers ``denied``
    (the first prod-shape run, operator record 6166020894) -- and a service with
    ``build:`` and no ``image:`` resolves to ``<project>-<service>:latest``, which
    is why the project name has to come from the same run that boots.

    Derived here, from the boot document ``up`` boots, so a pre-build and ``up``
    cannot disagree: an image built under any other tag is simply absent in
    compose's eyes, it builds during the boot after all, and the wall the
    pre-build exists to route around comes back with an extra step in front of
    it. A service that boots from a registry image is NOT included -- pulling it
    is the tier's business, and building it would replace what the tier
    witnesses with a locally-built stand-in.
    """
    images: dict[str, str] = {}
    for name, service in (rendered.get("services") or {}).items():
        if not isinstance(service, Mapping) or not service.get("build"):
            continue
        declared = service.get("image")
        images[name] = str(declared) if declared else f"{project}-{name}:latest"
    return images


def decide_resource_limits(rendered: dict[str, Any], subtree_control: str) -> str:
    """Decide, act and record in one step, so the three cannot disagree.

    When the machine delegates the controllers prod's limits need, the render
    keeps them and the run record says ``limits: applied``; otherwise they are
    stripped here (they would only make a rootless container fail to start) and
    the record says ruling 162 item 2's exact string. Returning the label the
    caller writes verbatim is deliberate: a caller that decided in one place and
    recorded in another is where an "applied" label lands on a stripped render."""
    if cgroup_limits_usable(subtree_control):
        return LIMITS_APPLIED
    strip_resource_limits(rendered)
    return LIMITS_STRIPPED


def prod_shape_env(*, run_dir: Path, image_tag: str, caller: Mapping[str, str]) -> str:
    """The env file for a prod-shape render, generated and never inherited.

    O2.2's rule -- compose reads this file and nothing else (:func:`compose_command`
    passes ``--env-file``, which suppresses the ``.env`` beside the compose file) --
    applies unchanged to the prod shape, so a run must not quietly pick up the host's
    real credentials. What the render needs was measured, not assumed: a drop-one
    matrix over ``prod.yml`` + the prod-shape override found four REQUIRED variables
    (each missing one exits 1 and names itself), against 154 references that
    carry a ``:-`` default. The fourth is ``HSI_TEST_NAME_PREFIX``, added with the
    per-run container names below; "three" was true until then and the matrix re-run
    is what caught it.

    Three of these are values a *test* deployment should not inherit from the host:
    ``POSTGRES_PASSWORD`` is generated per run (a fixed literal would pass a test and
    still be a shared secret), and the socket path is taken from the caller because it
    is a path, not a secret -- but a missing one is refused here rather than passed on,
    because compose only *warns* and interpolates a blank, which is the same failure
    mode the override already refuses for ``PROD_SHAPE_RUN_ROOT``.

    ``HSI_TEST_NAME_PREFIX`` exists because UR-133's project isolation has one hole a
    compose project cannot close: a pinned ``container_name`` is global to the engine,
    not namespaced by ``-p`` (measured on v5.5.1 -- booting the same pin under a second
    project dies with ``Conflict. The container name ... is already in use``). ``prod.yml``
    spells seven names and a profile-less render shows six of them (``dcgm-exporter`` sits
    behind the ``gpu-rootful`` profile), so the override prefixes each with THIS run's token;
    a constant prefix
    would leave two concurrent runs unable to come up. It is hex plus a separator because
    compose rejects other spellings, and the override reads it as ``${…:?…}`` so a run
    that somehow lacks it refuses to render instead of interpolating blank and rejoining
    the colliding set.
    """
    socket = caller.get("PODMAN_SOCKET")
    if not socket:
        raise HarnessError(
            "PODMAN_SOCKET is not set in the caller's environment. The prod stack mounts it "
            "into backend and alloy, and an empty value interpolates to a blank string with "
            "only a warning, so the render would ask the engine for a mount of '/'."
        )
    # [O2.5 venue fixes] The maui venue carries three of its own parameters in the
    # login shell (VENUE-PROFILE.md / maui-item2.env): GPU_AI_SERVICES (the CDI
    # runtime also accepts an explicit GPU list), AI_MODELS_PATH (the venue's model
    # tree, prod's /export/ai_models default retained) and ADMIN_ENABLED (the admin
    # surface the venue's run registers its first admin through). They reach the
    # render only through THIS file, and the list is closed on purpose: the caller's
    # shell stays untrusted the way O2.2 wrote it -- POSTGRES_PASSWORD is a host
    # secret, DEBUG flips the boot -- so anything outside the three names is dropped,
    # never copied. A multi-line value is refused rather than written: the file is
    # one KEY=value per line, and a newline would smuggle the following lines in as
    # new keys, the same silent-interpolation failure the file's own ${X:?} guards
    # exist for.
    venue = {
        key: caller[key]
        for key in ("GPU_AI_SERVICES", "AI_MODELS_PATH", "ADMIN_ENABLED")
        if key in caller
    }
    if any("\n" in value or "\r" in value for value in venue.values()):
        raise HarnessError("prod-shape venue parameters must be single-line values")
    return "".join(
        f"{key}={value}\n"
        for key, value in (
            ("IMAGE_TAG", image_tag),
            ("PODMAN_SOCKET", socket),
            ("POSTGRES_PASSWORD", secrets.token_hex(16)),
            ("PROD_SHAPE_RUN_ROOT", str(run_dir)),
            ("HSI_TEST_NAME_PREFIX", f"{secrets.token_hex(4)}-"),
            *venue.items(),
        )
    )


def as_prod_shape_deployment(
    rendered: Mapping[str, Any],
    *,
    vlm_url: str | None,
    fake_gateway: Mapping[str, Any] | None = None,
    fake_vlm: Mapping[str, Any] | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    """The run-time transforms the authored override cannot carry.

    The prod-shape path does NOT go through :func:`as_test_deployment` (measured:
    ``render()`` dispatches to ``render_prod_shape()`` before that function is ever
    called), so the two things the CI tier gets from it were missing here. Both were
    found by the UR-89 review and re-measured in the composed boot document.

    * ``ORCHESTRATOR_ENABLED=false`` (UR-134's first clause). The boot document's
      ``backend`` has ``env_file: None`` and its only ``ORCHESTRATOR_*`` key is
      ``DOCKER_HOST``, so an absent flag resolves to ``backend/core/config.py``'s
      ``enabled: Field(True)``; ``check_isolation`` runs on EVERY mode and asserts
      ``GET /api/system/services`` answers ``503``, so the first real run died there.
    * on ``--real``, the backend calls the VLM ``agent-gpu`` serves and the in-stack
      ``ai-vlm`` stays out -- package ``O2.5`` Step 1 words this ("pointed at
      ``agent-gpu``'s ``ai-vlm`` instead of CDI"). Left alone, the boot file keeps
      ``AI_VLM_URL=http://ai-vlm:8098`` and an ``ai-vlm`` whose top-level ``devices``
      ask the engine for ``nvidia.com/gpu=0``: a second GPU consumer racing agent-gpu's
      own container, and not the deployment the 12 real-tier rows witness.

    Ruling 256 (record 6250363327) split O2.5 by venue and binds two more shapes on
    these transforms. Its reason names the mechanism: agent-gpu gives the GPU to one
    container it starts on the host, never to the containers of a compose stack inside
    a sandbox -- the operator's attempt 2 (record 6195692210) died at
    ``unresolvable CDI devices nvidia.com/gpu=all`` with exactly one device-declaring
    service left in its boot document. The ruling:

    * SANDBOX RUN (``--real --prod-shape``, item 1): the stack keeps no GPU consumer
      except the VLM. The caller passes ``fake_gateway`` (the fake ``ai-gateway`` body
      the CI+fake render produces -- ruling 207's CI-tier fake) and this function
      replaces prod's gateway wholesale with it: the prod body's CDI
      ``nvidia.com/gpu=all`` and its deploy GPU reservation never boot, and the
      backend's gateway URLs keep working because the fake answers the same port and
      routes. ``backend``'s own deploy GPU reservation is stripped (the backend sees a
      GPU through NVML in its own container -- the maui run witnesses that; a sandbox
      boot that died asking for a GPU the venue never had would be indistinguishable
      from a harness bug). A ``dcgm-exporter`` that somehow reaches the transform is
      dropped (it sits behind prod's ``gpu-rootful`` profile, so a profile-less render
      never carries it -- the drop is belt, the naming is the ruling's clause).
    * MAUI RUN (``--prod-shape`` without ``--real``, item 2): the caller passes
      ``fake_vlm`` instead -- the fake VLM replaces the in-stack one, whose CDI line is
      "the one GPU line neither run boots" (the ruling's own words), while production's
      CDI for ``ai-gateway``, ``dcgm-exporter`` and ``backend`` is kept UNTOUCHED -- that
      stack booting with every device resolved is what the maui run witnesses. Passing
      the sandbox venue's ``fake_gateway`` here is refused: a caller asking for one
      venue's transform on the other venue would silently witness the wrong deployment.
    * the record names every removed or stripped device, on both venues. The
      deployment carries ``_device_changes`` so the caller can lift it into the run
      summary verbatim -- a silent swap would describe a deployment the venue never
      booted, which is the failure mode the operator's attempt-2 record shows.

    These are NOT put in the authored override for two reasons. It is a frozen,
    hand-authored artifact whose changes ruling 162 item 3 caps at three kinds
    (socket, pinned name, port/path) -- ``test_only_the_three_kinds_of_key_change``
    enforces exactly that, and a fourth kind would need a ruling to add. And a VLM URL
    is per-run, so static YAML cannot express it at all. Same split as the CI tier:
    the file carries the shape, the runner carries the run.
    """
    if fake_gateway is not None and fake_vlm is not None:
        raise HarnessError(
            "fake_gateway and fake_vlm cannot combine: the sandbox run swaps the gateway "
            "(--real --prod-shape), the maui run swaps the VLM (--prod-shape without --real), "
            "and one run witnesses exactly one of the two venues"
        )
    if fake_gateway is not None and vlm_url is None:
        raise HarnessError(
            "fake_gateway without vlm_url is the sandbox venue's transform on no venue: "
            "--real --prod-shape carries both the agent-gpu VLM and the fake gateway "
            "(ruling 256 item 1)"
        )
    if fake_vlm is not None and vlm_url is not None:
        raise HarnessError(
            "fake_vlm and vlm_url combine two venues' shapes: the maui run (ruling 256 "
            "item 2) has no agent-gpu, so it has no URL to pass"
        )
    deployment = copy.deepcopy(dict(rendered))
    services = deployment.get("services") or {}
    backend = services.get("backend")
    if backend is None:
        raise HarnessError("the prod-shape render has no backend service")
    # [O2.5 venue fixes] Opt-in (PROD_SHAPE_HEALTHCHECK_BUSYBOX): the maui venue's
    # older engine API reports an empty health status for services without checks,
    # so `up --wait` cannot hold the boot on the two exporters and the render
    # cannot just delete "disable" -- the authored override cannot add a healthcheck
    # (ruling 162 item 3's three kinds), so the runner gives the transform a real
    # probe. The tool crosses the bind, so the gate is a security one: a fixed,
    # read-only target, and the probe is wget --spider against the service's own
    # loopback metrics port -- no host path reachable, no command text the venue's
    # env can bend. An unusable tool is refused at render time, not discovered by
    # a boot that never turns healthy with the cause three layers away.
    if probe := os.environ.get("PROD_SHAPE_HEALTHCHECK_BUSYBOX"):
        executable = Path(probe).resolve()
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise HarnessError(f"health-check busybox is not executable: {executable}")
        for name, port in (("redis-exporter", 9121), ("json-exporter", 7979)):
            service = services.get(name)
            if service is None:
                raise HarnessError(
                    f"the prod-shape render has no {name}; the health-check probe "
                    f"cannot hold the boot on a service that is not there"
                )
            service.setdefault("volumes", []).append(
                {
                    "type": "bind",
                    "source": str(executable),
                    "target": "/busybox",
                    "read_only": True,
                }
            )
            service["healthcheck"] = {
                "test": [
                    "CMD",
                    "/busybox",
                    "wget",
                    "-q",
                    "--spider",
                    "-T",
                    "4",
                    f"http://localhost:{port}/metrics",
                ],
                "interval": "10s",
                "timeout": "5s",
                "retries": 3,
                "start_period": "10s",
            }
    device_changes: list[str] = []
    environment = backend.setdefault("environment", {})
    environment["ORCHESTRATOR_ENABLED"] = "false"

    # [O2.5 venue fixes, ruling 287] The three opt-in venue knobs below share one
    # gate and one shape: each is refused where the venue it belongs to cannot
    # exist, and each edits the boot document this run records. The gate is the
    # venue split itself (ruling 256): fake_gateway means the SANDBOX run -- the
    # real gateway was spliced out -- while its absence is the maui run that
    # keeps prod's real gateway verbatim. A knob that only touches the real
    # gateway therefore refuses on the sandbox venue, where it would edit
    # nothing and silently witness the wrong deployment.
    if userns := os.environ.get("PROD_SHAPE_INIT_USERNS"):
        # Ruling 287's venue requirement is "keep-id for foscam-init": the maui
        # probe (f4f447) measured the default initializer's bind owned by host
        # UID 100999 with the run's writer DENIED, and keep-id keeping the
        # caller's UID 1000 with the write succeeding -- the initializer must
        # chown inside ITS caller's namespace, not a subordinate one. foscam-init
        # ONLY: the whole point is one service's ownership of one writable bind,
        # and prod's other services run fine under the default mapping.
        if userns != "keep-id":
            raise HarnessError(
                f"PROD_SHAPE_INIT_USERNS must be keep-id (the venue requirement names it), "
                f"got {userns!r}"
            )
        init = services.get("foscam-init")
        if init is None:
            raise HarnessError(
                "the prod-shape render has no foscam-init; PROD_SHAPE_INIT_USERNS has "
                "nothing to apply to"
            )
        init["userns_mode"] = userns
    if base := os.environ.get("PROD_SHAPE_TRITON_IMAGE"):
        # The real gateway's base, overridden via --build-arg (ruling 287: Triton
        # 26.09 arm64 by digest, because 26.01's CUDA code fails on the GB300).
        # Sandbox venue refused: its gateway is the spliced fake, whose build is
        # the fake Dockerfile -- a build-arg for a build that never runs would
        # witness a deployment the venue never booted.
        if fake_gateway is not None:
            raise HarnessError(
                "PROD_SHAPE_TRITON_IMAGE requires the real-gateway maui venue: the sandbox "
                "run replaces the real gateway with the fake, and there is no build to "
                "carry the argument"
            )
        gateway = services.get("ai-gateway")
        if gateway is None or not isinstance(gateway.get("build"), dict):
            raise HarnessError(
                "the prod-shape render has no ai-gateway build; PROD_SHAPE_TRITON_IMAGE "
                "has nothing to carry the argument"
            )
        gateway["build"].setdefault("args", {})["TRITON_IMAGE"] = base
    if fake_gateway is None and (gpu := os.environ.get("GPU_AI_SERVICES")):
        # Ruling 287 item 2's last row: Podman's compatibility API may ignore the
        # deploy DeviceRequests prod carries, so the venue's explicit GPU choice
        # ALSO reaches the backend as NVIDIA_VISIBLE_DEVICES -- the env the NVIDIA
        # runtime honours on its own. The maui run's backend keeps prod's deploy
        # reservation untouched: this pin rides beside it, it does not replace
        # prod's wiring. The sandbox venue keeps no GPU wiring at all (its
        # backend's reservation is stripped by the transform above), so the knob
        # is maui-only like the two above.
        backend.setdefault("environment", {})["NVIDIA_VISIBLE_DEVICES"] = gpu

    def _consume_devices(service: Mapping[str, Any]) -> list[str]:
        """Every device-shaped stanza on one service, for the record's naming duty."""
        found = [str(device) for device in service.get("devices") or []]
        reservations = ((service.get("deploy") or {}).get("resources") or {}).get(
            "reservations"
        ) or {}
        found.extend(str(device) for device in reservations.get("devices") or [])
        return found

    def _splice(name: str, fake_body: Mapping[str, Any], replaced: Mapping[str, Any]) -> None:
        """Replace one prod service with a fake body, keeping the PROD render's network
        membership and host publishes.

        The fake bodies are the CI+fake render's bodies verbatim: they join ``ci-net``
        (defined only by the CI stack) and publish the CI band's host ports
        (``127.0.0.1:8090``/``8098``). Spliced into the prod render unedited, the boot
        document is REFUSED -- compose answers ``refers to undefined network ci-net``
        (the same measured refusal the solo fake render dies at, on BOTH venues) -- and
        were the network somehow defined, the publishes would be bind-fatal beside
        production on maui, where the LIVE stack holds ``127.0.0.1:8090`` (ai-gateway)
        and ``127.0.0.1:8098`` (ai-vlm). So the swap restores the replaced prod body's
        ``networks`` and ``ports`` onto the fake body: the fake joins the prod network
        the service it replaces was on (the backend reaches it by service name either
        way), and publishes on the prod-shape band the authored override set (23090/
        23098 via the override's +15000). The prod render's network membership stays the
        prod render's (``security-net``): the transform keeps it.
        """
        services[name] = copy.deepcopy(dict(fake_body))
        if "networks" in replaced:
            services[name]["networks"] = copy.deepcopy(replaced["networks"])
        else:
            services[name].pop("networks", None)
        if "ports" in replaced:
            services[name]["ports"] = copy.deepcopy(replaced["ports"])
        else:
            services[name].pop("ports", None)

    if fake_gateway is not None:
        prod_gateway = services.get("ai-gateway")
        if prod_gateway is None:
            raise HarnessError(
                "the prod-shape render has no ai-gateway; the sandbox run's swap "
                "(ruling 256 item 1) has nothing to replace"
            )
        removed = _consume_devices(prod_gateway)
        _splice("ai-gateway", fake_gateway, prod_gateway)
        device_changes.append(
            f"ai-gateway: replaced with the fake gateway (ruling 207's CI-tier fake); "
            f"removed devices {removed or 'none'}"
        )
        for key, value in (
            ("AI_GATEWAY_URL", "http://ai-gateway:8090"),
            ("YOLO26_URL", "http://ai-gateway:8090/yolo26"),
            ("ENRICHMENT_LIGHT_URL", "http://ai-gateway:8090/enrich-lt"),
        ):
            if key in environment:
                environment[key] = value
    else:
        # The maui run keeps production's CDI for ai-gateway, dcgm-exporter and backend
        # (ruling 256 item 2): the stack booting with every device resolved is what it
        # witnesses. A profile-less render cannot carry dcgm-exporter (the gpu-rootful
        # profile hides it), so the keeping is implicit -- and the device strip below is
        # what must NOT run.
        pass
    if fake_vlm is not None:
        prod_vlm = services.get("ai-vlm")
        if prod_vlm is None:
            raise HarnessError(
                "the prod-shape render has no ai-vlm; the maui run's swap (ruling 256 "
                "item 2) has nothing to replace"
            )
        removed = _consume_devices(prod_vlm)
        _splice("ai-vlm", fake_vlm, prod_vlm)
        device_changes.append(
            f"ai-vlm: replaced with the fake VLM; removed devices {removed or 'none'}"
        )
    if vlm_url is not None:
        environment["AI_VLM_URL"] = vlm_url
        prod_vlm = services.get("ai-vlm")
        if prod_vlm is not None:
            removed = _consume_devices(prod_vlm)
            services.pop("ai-vlm", None)
            device_changes.append(
                f"ai-vlm: removed (served by agent-gpu outside this render); "
                f"removed devices {removed or 'none'}"
            )
    # [O2.5 venue fixes, ruling 287] The two-hop VLM relay's in-stack half.
    # On a rootless engine a container cannot dial the loopback port the
    # agent-gpu lease published, so the backend dials this sidecar instead of
    # the lease URL, and the sidecar hands each connection over a run-dir Unix
    # socket to the host half (run.up()'s armed thread). Render-time refusal
    # beside the TRITON_IMAGE gate above: the knob belongs to the real-gateway
    # venue only, and a knob with nothing to apply to would silently witness
    # the wrong deployment.
    if os.environ.get("PROD_SHAPE_VLM_RELAY") == "1":
        if vlm_url is None or run_dir is None:
            raise HarnessError(
                "PROD_SHAPE_VLM_RELAY requires the real-gateway venue (--real --prod-shape "
                "with the agent-gpu VLM): the maui run has no agent-gpu lease to relay to, "
                "and the sidecar's bind source is the run dir"
            )
        # The backend's own image, from the same derivation `build_images`
        # records and the prebuild and `up --no-build` use: `compose config`
        # bakes no image for a build-only service, and an `up` against a
        # nameless service pulls first -- the pull-denied shape the prebuild
        # exists to prevent. The run dir's NAME IS the run's project
        # (Run.__init__: dir = root / project), so the project reaches the
        # transform through the parameter it already carries. A render whose
        # backend boots a declared image instead (drift, not the prod stack's
        # shape) is refused by name: a sidecar booting something else than the
        # backend would silently witness the wrong deployment.
        derived = build_images(rendered, project=run_dir.name)
        backend_image = derived.get("backend")
        if backend_image is None:
            raise HarnessError(
                "PROD_SHAPE_VLM_RELAY needs the backend's derived image name, and the "
                "prod-shape render's backend declares no build: it boots "
                f"{backend.get('image')!r} -- drift from the prod stack, not a shape to "
                "relay against"
            )
        services[VlmRelay.SERVICE] = {
            # The backend's own image (the derived name `build_images` and the
            # prebuild already use): `compose config` bakes no image for a
            # build-only service, and an `up` against a nameless service pulls
            # first -- the pull-denied shape the prebuild exists to prevent.
            "image": backend_image,
            "entrypoint": [
                "python3",
                "/relay/vlm_relay.py",
                "tcp2unix",
                f"0.0.0.0:{VlmRelay.PORT}",
                "/relay/relay.sock",
            ],
            "networks": {"security-net": None},
            "volumes": [
                {
                    "type": "bind",
                    "source": str(run_dir / "relay"),
                    "target": "/relay",
                    "read_only": True,
                }
            ],
            # Lesson 4 applied literally: the backend image's ENTRYPOINT
            # (entrypoint.sh) would eat the relay argv.
            # The healthcheck dials the mounted socket only -- it proves the
            # mount and the permission path; the tcp2unix process does the
            # per-connection dialing. Connect-only: no HTTP is spoken through
            # the socket, so the check cannot hang on a half-open VLM.
            "healthcheck": {
                "test": [
                    "CMD",
                    "python3",
                    "-c",
                    "import socket; s=socket.socket(socket.AF_UNIX); "
                    "s.connect('/relay/relay.sock'); s.close()",
                ],
                "interval": "10s",
                "timeout": "5s",
                "retries": 3,
                "start_period": "10s",
            },
            "depends_on": {},
        }
        device_changes.append(
            f"{VlmRelay.SERVICE}: added (the relay sidecar; no published ports, security-net only)"
        )
        depends = backend.setdefault("depends_on", {})
        depends[VlmRelay.SERVICE] = {"condition": "service_healthy"}
        device_changes.append(f"backend: depends_on {VlmRelay.SERVICE} (service_healthy) added")
        environment["AI_VLM_URL"] = VlmRelay.RELAY_URL
        device_changes.append(f"backend: AI_VLM_URL set to {VlmRelay.RELAY_URL} (the relay form)")
    for name in list(services):
        service = services[name]
        deploy = service.get("deploy")
        if name == "backend" and fake_gateway is not None and isinstance(deploy, dict):
            # Sandbox venue only (ruling 256 item 1). The maui run KEEPS this reservation
            # -- the backend seeing a GPU through NVML in its own container is exactly what
            # the maui run witnesses (F-176, F-178, F-182).
            resources = deploy.get("resources") or {}
            reservations = resources.get("reservations") or {}
            if reservations.get("devices"):
                stripped = [str(device) for device in reservations["devices"]]
                reservations.pop("devices", None)
                if not reservations:
                    resources.pop("reservations", None)
                device_changes.append(
                    f"backend: deploy GPU reservation stripped (the sandbox venue keeps no "
                    f"GPU consumer except the VLM, ruling 256 item 1); removed {stripped}"
                )
        if name == "dcgm-exporter" and fake_gateway is not None:
            removed = _consume_devices(service)
            services.pop(name, None)
            device_changes.append(
                f"{name}: dropped (ruling 256 item 1: the sandbox run keeps no GPU "
                f"consumer except the VLM); removed devices {removed or 'none'}"
            )
            continue
        depends_on = service.get("depends_on")
        if isinstance(depends_on, dict) and "ai-vlm" not in services:
            # the omission this transform performs deliberately (mirrors
            # as_test_deployment:449); anything else still missing is drift, not design.
            depends_on.pop("ai-vlm", None)
        for dependency in depends_on or {}:
            if dependency not in services:
                raise HarnessError(
                    f"{name} depends on {dependency}, which this prod-shape render omits"
                )
    deployment["_device_changes"] = device_changes
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
    labels = service.get("labels")
    if isinstance(labels, Mapping):
        for key in sorted(labels):
            if not str(key).startswith(LABEL_PREFIXES):
                problems.append(
                    f"{name}: label {key} is outside the marking namespace the "
                    "preflight allows (uplevel.*); a rule for it belongs here first"
                )
    return problems


def _top_level_problems(rendered: Mapping[str, Any], project: str) -> list[str]:
    problems = []
    for key in sorted(rendered):
        if key not in TOP_LEVEL_KEYS and not key.startswith("x-"):
            problems.append(f"{key}: a top-level section the preflight has no rule for")
    for key, raw_network in sorted((rendered.get("networks") or {}).items()):
        network = raw_network or {}
        own = f"{project}_{key}"
        if network.get("external"):
            problems.append(f"network {key}: external, shared beyond this run")
        elif network.get("name", own) != own:
            problems.append(f"network {key}: named {network.get('name')}, not the run's own {own}")
        elif network.get("driver") not in (None, "bridge"):
            problems.append(
                f"network {key}: driver {network.get('driver')}; a test deployment uses bridge"
            )
    for key, raw_volume in sorted((rendered.get("volumes") or {}).items()):
        volume = raw_volume or {}
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
                # Refused in both modes: an alias carries every built-in URL
                # that uses the name (the backend's alloy, prometheus, go2rtc
                # defaults are not in its environment) to the host.
                hosts.add(alias)
                problems.append(f"{name}: extra_hosts maps {alias} to the host ({target})")
        environment = service.get("environment") or {}
        where_text = [(f"{key}", value) for key, value in environment.items() if value]
        where_text += [("command", s) for s in _strings(service.get("command"))]
        where_text += [("entrypoint", s) for s in _strings(service.get("entrypoint"))]
        healthcheck = service.get("healthcheck") or {}
        where_text += [("healthcheck", s) for s in _strings(healthcheck.get("test"))]
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
    prod_shape_socket: str | None = None,
) -> list[str]:
    """Every reason the running test deployment is not isolated.

    ``containers`` is ``inspect`` of the run project's containers;
    ``orchestrator_enabled`` is the backend's own setting, read inside its
    container (None if it could not be read); ``services`` is the status and
    JSON body of ``GET /api/system/services``, read after the first admin
    registered (the setup guard answers 503 before that, for every route).

    ``prod_shape_socket`` switches the mount rule to the prod shape's own
    policy (ruling 287 item 12) -- the SAME :func:`engine_socket_mounts` the
    render's UR-134 re-check runs, given the caller's socket path, plus a
    writable-host-root rule of its own. The default None keeps the CI tier's
    per-mount check byte-for-byte, including its root-directory ban: prod's
    node-exporter binds ``/:/host:ro`` (docker-compose.prod.yml:1450) and the
    render deliberately accepts it, so a run would die in-run on the very boot
    its render approved if the CI rule leaked in here. The policy is stricter
    on one axis, not looser on both: a socket whose source is the caller's
    socket is refused as before (a read-only socket bind is not a weaker
    capability -- opening the socket is the whole attack), and a bind of ``/``
    or ``/var`` that is WRITABLE is named, which the read-only observer's
    acceptance never excused.
    """
    problems = []
    for raw in containers:
        container = Container.from_inspect(raw)
        if prod_shape_socket is not None:
            # One synthetic rendered doc per container: engine_socket_mounts reads
            # (service name, mounts), and the container IS the running service.
            sockets = engine_socket_mounts(
                {
                    "services": {
                        container.name: {
                            "volumes": [
                                {"source": mount.source, "target": mount.target}
                                for mount in container.mounts
                            ]
                        }
                    }
                },
                socket_path=prod_shape_socket,
            )
            hits = [(source, target) for _, source, target in sockets]
            # A read-only observer must never become a writable host-root bind:
            # the render-time rule refuses it in the boot document, so the
            # running deployment must not carry one either.
            hits += [
                (mount.source, mount.target)
                for mount in container.mounts
                if mount.writable and mount.source in {"/", "/var"}
            ]
        else:
            hits = [
                (mount.source, mount.target)
                for mount in container.mounts
                if is_engine_socket(mount.source) or _ENGINE_SOCKET.search(mount.target)
            ]
        problems += [
            f"{container.name}: holds an engine socket ({source} -> {target})"
            for source, target in hits
        ]
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


def golden_execution_problems(leg: str, specs: Mapping[str, str]) -> list[str]:
    """Ruling 114: a golden project that executed nothing is a Feature Check problem.

    A leg's exit code is not evidence that it ran. The shape that hides is the
    one that exits 0: a suite where every spec skipped — measured here, pytest
    returns 0 for that, and 5 only when it COLLECTED nothing (which the leg's own
    exit-code check already reddens). A report with no entries at all is the same
    evidential hole: the runner finished, and the report the leg records proves
    nothing either way. Both used to account as ``{"backend": "ok",
    "backend_specs": {}}`` — the most expensive kind of green, because the section
    the operator posts looks accounted for. An ABSENT golden project is a different
    state and stays accounted as such by the leg itself ("no specs yet"), never as
    a problem. Only ALL-skipped is a problem: specs that skip when their own
    precondition is absent are honest, and a run with one executed spec is green.
    """
    if not specs:
        return [
            f"golden: the {leg} golden project executed no tests — its junit report"
            " listed no spec at all (the project never started, or wrote no results)"
        ]
    if set(specs.values()) == {"skipped"}:
        return [
            f"golden: the {leg} golden project executed no tests — all"
            f" {len(specs)} of its specs were skipped"
        ]
    return []


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
            'docs/uplevel/roles/operator.md, "The agent-gpu path".'
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
    environment as written (``prod_environment``'s raw YAML read)."""
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


def host_alias_resolves(name: str = "host.docker.internal") -> bool:
    """Whether THIS process can resolve a host alias at all — a DNS question.

    The two container runtimes this repo runs on add that name precisely because
    a container is not on the machine it runs on, so it resolves exactly when
    dialing it can work: the operator sandbox answers it with the proxy's address
    (measured here: 169.254.1.1) and forwards it to the host, and a plain host
    login has no entry (the owner's maui run, record 6193951294, got
    ``curl: (6) Could not resolve host``). A container marker would be the wrong
    probe — ``/.dockerenv`` is absent under rootless Podman, which is maui's
    route — and ``$SANDBOX_NAME`` is a runtime convention, not a fact about
    reachability.
    """
    try:
        socket.getaddrinfo(name, None)
    except OSError:
        return False
    return True


def _require_pool_url(url: str, port: int, *, dialed: str) -> str:
    """Re-check an already-validated VLM URL before dialing it, and return it.

    Shared by both forms so the loopback one cannot be a wider door: same
    scheme, same port inside :data:`AGENT_GPU_PORTS`, no path, query or
    fragment. Only the HOST may differ, and only between the alias and the
    loopback of the machine that published the port.
    """
    parts = urllib.parse.urlsplit(url)
    try:
        url_port = parts.port
    except ValueError:
        url_port = None
    if (
        parts.scheme != "http"
        or parts.hostname not in ("host.docker.internal", "127.0.0.1")
        or url_port != port
        or port not in AGENT_GPU_PORTS
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
    ):
        raise HarnessError(
            f"{dialed} {url}; a run reaches only port {port} of "
            f"http://host.docker.internal:<{AGENT_GPU_PORTS.start}-{AGENT_GPU_PORTS.stop - 1}>"
        )
    return f"http://{parts.hostname}:{url_port}"


def agent_gpu_url(output: str, container_port: int = VLM_PORT) -> tuple[str, int]:
    """The URL ``agent-gpu run`` printed for ``container_port``, and its port.

    The runner publishes from :data:`AGENT_GPU_PORTS` on the host's loopback,
    reached as host.docker.internal. Anything else could be the live stack's
    API, database or engine, so the run refuses it.

    This is the address the run's CONTAINERS use: it goes to the backend as
    ``AI_VLM_URL`` and to ``check_vlm_reach``, which dials it from inside that
    container, where loopback would be the container's own. The harness's own
    dial is :func:`vlm_dial_url`.
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


def vlm_dial_url(
    url: str,
    port: int,
    *,
    alias_resolves: Callable[[str], bool] | None = None,
) -> str:
    """The form of ``url`` the HARNESS can dial from this machine.

    ``agent-gpu run`` prints the alias form even from a host login, where it has
    no DNS entry (the owner's maui run read ``/health`` at
    ``http://127.0.0.1:18100/health`` — the same pool port — while the alias gave
    ``curl: (6)``, and the run then sat out its 900 s readiness deadline). So the
    alias is used when it resolves, and loopback at the same pool port when it
    does not; this process ran ``agent-gpu run`` itself, so when the alias is
    dead it is because it is on the machine that published the port. The port and
    the rest of the shape are re-checked by :func:`_require_pool_url`, which
    refuses anything ``agent_gpu_url`` would refuse.

    ``alias_resolves`` is the probe, injectable so a test pins both arms without
    depending on the machine it runs on. It is looked up at CALL time, not bound
    as a default, so a caller that swaps ``host_alias_resolves`` on this module
    changes what a real run does.
    """
    _require_pool_url(url, port, dialed="a run dials only")
    probe = alias_resolves if alias_resolves is not None else host_alias_resolves
    if probe("host.docker.internal"):
        return f"http://host.docker.internal:{port}"
    return f"http://127.0.0.1:{port}"


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


# Ruling 143: the golden Playwright leg runs inside Playwright's own image, so
# the browser and its system libraries arrive with the runner instead of being
# downloaded onto the host. The tag's VERSION never appears here — it comes from
# frontend/package-lock.json (see playwright_image) — this is only the
# repository and the Ubuntu release Playwright publishes images for.
PLAYWRIGHT_IMAGE_REPOSITORY = "mcr.microsoft.com/playwright"
PLAYWRIGHT_IMAGE_VARIANT = "noble"
# The lock key whose version becomes the image tag: the package the golden specs
# import, and the one `npm ci` installs from the same file.
PLAYWRIGHT_LOCK_KEY = "@playwright/test"
# The registry whose reachability ruling 116's firewall clause now governs. A
# literal, not a parse of the ref, because the clause has to name a host at the
# point where nothing else has run yet: when the pull fails there is no
# engine-side fact to consult, only this string and the child's own tail. The
# image's layer blobs live on a different host, so a block one hop past the
# registry names itself in that tail — which is why the tail is kept.
PLAYWRIGHT_IMAGE_REGISTRY = "mcr.microsoft.com"
# The variables the containerized golden leg needs: exactly the ones the golden
# specs read through process.env (grep of frontend/tests/golden/** for
# FEATURE_CHECK_ returns API_URL, UI_URL, CAMERA_ROOT, CAMERAS, SCENARIOS,
# ADMIN_USERNAME, ADMIN_PASSWORD — no MODE, no RUN_DIR) plus the junit path
# golden() reads back. Names go to the engine; values never do.
#
# `CI` is here for a different reason than the eight FEATURE_CHECK_* names:
# playwright.config.ts branches on it (`forbidOnly: !!process.env.CI` :73,
# `retries: process.env.CI ? 2 : 0` :79). The host leg always had it — GitHub
# sets CI=true in every job — so omitting it here would ship the containerized
# leg with the .only guard OFF and retries 0: one stray test.only in any spec
# would run 1 of 126 and report green (the junit then holds 1 testcase, which
# the vacuity guard reads as a pass), and no spec could ever HAVE a failed
# attempt, blinding the flaky census. Name-only, same as the password: the
# engine reads the value from the harness's own env, so the container sees
# exactly what the host leg saw. Locally CI is unset and both legs match.
GOLDEN_CONTAINER_ENVIRONMENT = (
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
)
# [r282] The manifest shard's selected spec files, space-separated,
# frontend-relative. NOT in the whitelist above: the whitelist forwards names
# every leg has always had, and r282's unsharded legs (the real tier, the maui
# prod-shape run, the local operator) must keep today's argv byte for byte --
# so the selection's name is forwarded only when a selection exists, through
# golden_container_command's extra_environment, and playwright.config.ts
# treats an unset/empty FEATURE_CHECK_GOLDEN_FILES as "no selection".
R282_GOLDEN_FILES_ENV = "FEATURE_CHECK_GOLDEN_FILES"


def playwright_image(lock_path: Path) -> str:
    """The Playwright image ref for the version this repo's lock resolves.

    Ruling 143: "where `<version>` comes from `frontend/package-lock.json`,
    never hard-coded." The ref is `v<version>-<variant>` and the version is read
    from the lock's own `packages["node_modules/@playwright/test"].version` — the
    same entry `npm ci` installs, so the container's browser and the repo's
    runner cannot disagree. A missing key RAISES instead of defaulting: a
    defaulting version is a hard-coded version with extra steps, and the
    Done-when for this package is a test that this function follows the lock.

    Every way the version source can fail becomes THIS error type, including a
    lock that is absent or is not JSON. `golden()` catches `HarnessError` around
    this call precisely so the failure is accounted in summary.json, and it
    commits its results only on the way out — a raw `OSError`/`JSONDecodeError`
    would fly past that handler to the harness's catch-all and erase every golden
    step already recorded, which is ruling 116's finding about a raised timeout.
    """
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as unreadable:
        raise HarnessError(
            f"{lock_path} cannot be read ({type(unreadable).__name__}: {unreadable}), "
            f"so the golden image tag cannot be derived from it"
        ) from unreadable
    packages = lock.get("packages") if isinstance(lock, dict) else None
    entry = (packages or {}).get(f"node_modules/{PLAYWRIGHT_LOCK_KEY}") or {}
    version = entry.get("version") if isinstance(entry, dict) else None
    if not isinstance(version, str) or not version:
        raise HarnessError(
            f"{lock_path} has no packages['node_modules/{PLAYWRIGHT_LOCK_KEY}'].version, "
            f"so the golden image tag cannot be derived from it"
        )
    return f"{PLAYWRIGHT_IMAGE_REPOSITORY}:v{version}-{PLAYWRIGHT_IMAGE_VARIANT}"


def golden_container_command(
    *,
    engine: str,
    image: str,
    inner: str,
    read_only_mounts: Sequence[Path] = (),
    mounts: Sequence[Path] = (),
    extra_environment: Sequence[str] = (),
) -> list[str]:
    """The `<engine> run` argv that runs `inner` inside the golden image.

    Ruling 143's three requirements, one flag each: ``--network host`` is how the
    container reaches the harness's stack on an engine-assigned port; every mount
    is bound at its OWN absolute path, so a path recorded on the host names the
    same file inside; and the engine is ``self.engine``, so ``--engine podman``
    gets a podman invocation.

    Two choices are load-bearing rather than stylistic:

    * ``-e NAME`` with no ``=VALUE``. ``_run`` logs every argv it runs
      (``shlex.join``) to the harness's own stdout, which on CI is the Actions
      step log, so ``-e FEATURE_CHECK_ADMIN_PASSWORD=…`` would write the run's
      admin password into that log. (The uploaded artifact
      ``golden-playwright.log`` is only the Playwright child's output, so it
      never carries an argv line — the step log is the exposure.) The name-only
      form makes the engine read the value from ITS OWN environment, which is
      the ``env=`` this command runs with.
    * ``ro`` on the source tree. The leg has no reason to write into it — both
      ``--output`` and the junit file live in the run dir — and a read-only bind
      turns "the container wrote in the tree" from a quiet possibility into a
      loud failure.

    ``extra_environment`` [r282] carries names forwarded ONLY when this run's
    shape produced them (today: ``FEATURE_CHECK_GOLDEN_FILES``, the manifest
    shard's selected files). A name that is always forwarded would put
    ``-e FEATURE_CHECK_GOLDEN_FILES`` on every leg's argv, unsharded legs
    included — and then the unsharded leg's argv is no longer today's argv,
    which the r282 pins refuse: the option's existence must not change a leg
    that does not use it, exactly as the shard flag never did.

    ``z`` (shared SELinux relabel) goes on the binds only under podman, matching
    docker-compose.prod.yml's ``:z`` camera and data mounts: on an SELinux host a
    podman bind without a relabel context reads Permission denied. Docker has no
    relabel to do and rejects the option.
    """
    command = [engine, "run", "--rm", "--network", "host", "-w", str(FRONTEND)]
    suffix = ",z" if engine == "podman" else ""
    for path in read_only_mounts:
        command += ["-v", f"{path}:{path}:ro{suffix}"]
    for path in mounts:
        command += ["-v", f"{path}:{path}{suffix}"]
    for name in GOLDEN_CONTAINER_ENVIRONMENT:
        command += ["-e", name]
    for name in extra_environment:
        command += ["-e", name]
    return [*command, image, "sh", "-c", inner]


# ---------------------------------------------------------------------------
# A run
# ---------------------------------------------------------------------------

# How a step that hit its deadline is reported: the conventional "the timer
# expired" exit code, and this word in the stderr. One producer and one reader,
# both here, because the test fixture has to build the SAME value _run does --
# a fixture that re-spelled this wording could drift while every consumer's pin
# stayed green.
_TIMEOUT_RC = 124
_TIMEOUT_NOTE = "timed out"


def _as_text(value: str | bytes | None) -> str:
    """A subprocess stream as text: TimeoutExpired hands back raw BYTES even
    when run() was called with text=True (measured on 3.14.4), and the harness
    only ever captures text."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def _stalled_result(stalled: subprocess.TimeoutExpired) -> subprocess.CompletedProcess[str]:
    """What a step that never finished reports, in place of the raise.

    subprocess.run raises TimeoutExpired whatever check says (measured on
    3.14.4), and by then it has killed the child but kept the buffered output --
    e.stdout carries the bytes the child flushed before the deadline (measured:
    a print before a hang arrives as b'...'), while e.stderr is None unless the
    child wrote to stderr. A download stalled at 80% therefore still says which
    build was in flight, so the stream is kept and DECODED: the exception hands
    back raw bytes even when run() was called with text=True (measured), so a
    str-only guard would throw away exactly what is worth keeping here.
    """
    partial_out = _as_text(stalled.stdout)
    partial_err = _as_text(stalled.stderr)
    note = f"{_TIMEOUT_NOTE} after {stalled.timeout} seconds"
    return subprocess.CompletedProcess(
        list(stalled.cmd),
        _TIMEOUT_RC,
        partial_out,
        note + (f"\n{partial_err}" if partial_err else ""),
    )


def _stalled(result: subprocess.CompletedProcess[str]) -> bool:
    """Was this result a step that hit its deadline?

    An exit 124 whose own stderr says "timed out" counts even when it came from
    the child's internal timer rather than ours -- both readings are "this step
    ran out of time", which is exactly the distinction the account names.
    """
    return result.returncode == _TIMEOUT_RC and _TIMEOUT_NOTE in (result.stderr or "")


def _exit_word(result: subprocess.CompletedProcess[str]) -> str:
    """What a failed step's account names as its outcome: the literal word for a
    step that ran out of time, otherwise the number. A stall and a refusal must
    not read alike in summary.json -- the stall is the firewall's realistic
    failure (a proxy that accepts the connection then streams nothing) and the
    refusal is the one an allow fixes, so ruling 116's "name the host" step has
    to stay tellable from "the operator should allow a host"."""
    return _TIMEOUT_NOTE if _stalled(result) else str(result.returncode)


# What the two engines `main()` offers actually print for "that name is not in the engine",
# measured in this sandbox against docker 27.x and podman 5.7.0. Lowercased, because the
# comparison below lowercases the stream.
_ABSENCE_MARKERS = ("no such image:", "image not known")


def _image_absent(result: subprocess.CompletedProcess[str]) -> bool:
    """Did the engine POSITIVELY say this image name is not in it?

    The companion to :func:`_stalled`, one level down. A stall was already fenced
    because rc=124 is nonzero and nonzero inspect used to mean "never existed"; the
    same false reading survives through a second door, measured here: a DOWN daemon
    answers `image inspect` with the exit code it uses for absence -- rc=1 for
    docker, rc=125 for podman, and the SAME code for both answers on each engine.
    So the exit code cannot carry this distinction at all, and only the daemon's own
    words can: docker says "No such image:", podman says "image not known".

    Absence therefore has to be identified, not inferred. Everything this returns
    False for -- a refusal, an argument error, empty stderr, an unrecognised engine
    message -- is unknown state, which is the loud direction: the caller records the
    name and does not remove it. A marker list is deliberately short and anchored to
    the two engines the harness can be pointed at; widening it to "any stderr" would
    put the false-spotless report back.
    """
    if result.returncode == 0:
        return False  # rc=0 is present, whatever the stream says
    stderr = (result.stderr or "").lower()
    return any(marker in stderr for marker in _ABSENCE_MARKERS)


def _log(message: str) -> None:
    stamp = datetime.now(UTC).strftime("%H:%M:%SZ")
    print(f"feature-check {stamp} {message}", flush=True)


class VlmRelay:
    """The host-namespace half of the two-hop VLM relay (O2.5 item 1, ruling 287).

    On a rootless engine, a container on the stack network cannot dial the
    loopback port the agent-gpu lease published (the relay's leg 1: the netns
    boundary), so the run relays in two hops of one stdlib script
    (:mod:`scripts.uplevel.vlm_relay`):

    * ``tcp2unix`` runs as the ``agent-gpu-relay`` compose service the prod-shape
      transform adds (inside the stack's own network): accepts TCP on the relay
      port, hands each connection over a run-dir Unix socket.
    * ``unix2tcp`` — this class, a thread in the harness's own process — accepts
      on that socket and dials ``127.0.0.1:<pool port>``. The VLM keeps
      publishing loopback only; the socket never touches a network.

    The vendored script is copied into the run dir at arm time, so the sidecar's
    bind source and the teardown marker are the same path, and the socket dies
    with the run dir. Nothing here survives the run: the caller joins and
    unlinks in its teardown ``finally``.
    """

    PORT = 8098  # the relay port inside the stack network (ai-vlm's own port)
    SERVICE = "agent-gpu-relay"
    RELAY_URL = f"http://{SERVICE}:{PORT}"
    SOCKET_NAME = "relay.sock"

    def __init__(self, run: Run) -> None:
        self.run = run
        self.socket = run.dir / "relay" / self.SOCKET_NAME
        self.started = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._listener: socket.socket | None = None
        # Dial accounting for the boot-failure chain: "the backend cannot reach
        # the VLM" must be able to name the broken hop (transform-recorded
        # fields are the render's; this is the arm's own state).
        self.dials = 0
        self.last_error: str | None = None

    def arm(self) -> None:
        """Vendor the script, bind the socket, and start serving in a thread.

        Raises HarnessError naming itself when anything fails: a failed arm is a
        named failure, never a silent one -- the sidecar's healthcheck would
        otherwise turn an unexplainable `up --wait` timeout into the cause. A
        post-bind failure unlinks the bound socket first: a half that failed to
        arm leaves no artifact its join path would not have reaped.
        """
        self.run.summary["vlm_container_url"] = self.RELAY_URL
        listener: socket.socket | None = None
        try:
            relay_dir = self.run.dir / "relay"
            relay_dir.mkdir(parents=True, exist_ok=True)
            script = relay_dir / "vlm_relay.py"
            script.write_text(
                (REPO_ROOT / "scripts" / "uplevel" / "vlm_relay.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            self.socket.parent.chmod(0o755)
            if self.socket.exists():
                self.socket.unlink()
            listener = socket.socket(socket.AF_UNIX)
            listener.bind(str(self.socket))
            self.socket.chmod(0o666)
            # A container dialing across a uid map needs write permission on
            # the socket inode itself (measured: the default 0755 answers
            # EACCES to another uid).
            listener.listen(vlm_relay.BACKLOG)
        except OSError as error:
            if listener is not None:
                # The bind happened: drop the socket file so a failed arm
                # leaves the run dir as it found it (the join path would never
                # run for this half -- run.relay is not yet assigned).
                try:
                    listener.close()
                except OSError:
                    pass
                try:
                    self.socket.unlink(missing_ok=True)
                except OSError as unlink_error:
                    _log(f"FAIL the VLM relay socket could not be unlinked: {unlink_error}")
            raise HarnessError(f"the VLM relay host half could not arm: {error}") from error
        self._listener = listener
        self.started = True
        self._thread = threading.Thread(target=self._serve, args=(listener,), daemon=True)
        self._thread.start()
        self.run.summary["results"]["vlm_relay"] = "ok"
        _log(
            f"vlm relay: host half armed at {self.socket}, "
            f"dialing {self.run.vlm_dial_host}:{self.run.vlm_dial_port}"
        )

    def _serve(self, listener: socket.socket) -> None:
        """Accept until stopped; each connection is handed to the VLM."""
        listener.settimeout(0.5)
        while not self._stop.is_set():
            try:
                conn, _ = listener.accept()
            except TimeoutError:
                continue
            except OSError as error:
                self.last_error = f"accept: {error}"
                break
            try:
                up = socket.create_connection(
                    (self.run.vlm_dial_host, self.run.vlm_dial_port), timeout=10
                )
                # connect-bounded, stream-unbounded: create_connection's
                # timeout persists on the returned socket for its lifetime
                # (measured), so the relayed stream would otherwise cap every
                # read gap at 10s -- a slow inference killed mid-stream.
                up.settimeout(None)
            except OSError as error:
                self.dials += 1
                self.last_error = f"dial 127.0.0.1:{self.run.vlm_dial_port}: {error}"
                conn.close()
                continue
            self.dials += 1
            threading.Thread(target=vlm_relay.pipe, args=(conn, up), daemon=True).start()
            threading.Thread(target=vlm_relay.pipe, args=(up, conn), daemon=True).start()
        try:
            listener.close()
        except OSError:
            pass

    def join(self) -> None:
        """Stop the half, join its thread, and unlink the socket. Idempotent,
        never raises: it runs in the teardown finally, after every other
        cleanup already ran."""
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=30)
        self._thread = None
        self._listener = None
        try:
            self.socket.unlink(missing_ok=True)
        except OSError as error:
            _log(f"FAIL the VLM relay socket could not be unlinked: {error}")
        if self.started:
            self.run.summary["results"]["vlm_relay"] = (
                "stopped" if self.last_error is None else f"stopped; last error: {self.last_error}"
            )


class Run:
    """One test deployment: its project, directory, engine and artifacts."""

    def __init__(
        self,
        *,
        engine: str,
        root: Path,
        image_tag: str,
        mode: str,
        prod_shape: bool = False,
        seeded: bool = False,
        shard: tuple[int, int] | None = None,
        golden_specs: tuple[str, ...] | None = None,
        pytest_k: str | None = None,
        playwright_grep: str | None = None,
    ) -> None:
        stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        self.project = f"{PROJECT_PREFIX}{stamp}-{secrets.token_hex(3)}"
        self.engine = engine
        self.mode = mode
        self.prod_shape = prod_shape
        self.seeded = seeded
        # [r264] The golden leg's shard, as (i, N) with 1 <= i <= N. None is the
        # unsharded run -- every existing caller and pin passes no shard, and
        # None must leave every byte of the leg's argv and record unchanged.
        self.shard = shard
        # [r287] The named-spec limit for the prod-shape Playwright leg, as the
        # repo paths the option validated. None is the unlimited leg -- every
        # existing caller and pin passes no specs, and None must leave every
        # byte of the leg's argv and record unchanged.
        self.golden_specs = golden_specs
        # Phase 4 real-tier witness selectors (UR-140, pointer 6340852534):
        # None is the unlimited run -- absent from summary when unset.
        self.pytest_k = pytest_k
        self.playwright_grep = playwright_grep
        # [O2.5 venue fixes, ruling 287] The two-hop VLM relay's host half, set
        # only on the venue that needs it: run.up() arms it when the relay knob
        # is on and a real VLM serves. None leaves every render and record
        # byte-identical to today's.
        self.relay: VlmRelay | None = None
        # The lease's loopback form the relay's host half dials, recorded at arm
        # time (up() has both halves' facts then: the pool port from vlm.start()).
        self.vlm_dial_host = "127.0.0.1"
        self.vlm_dial_port: int | None = None
        # A run record that does not say WHICH compose shape was rendered cannot
        # witness ruling 127's 12 real-tier rows, which is the whole point of the
        # O2.5 run. The tier strings for --fake/--real are unchanged -- only the
        # prod shape and the ruling-127/187 seeded CI project get distinct ones --
        # so nothing that greps today shifts.
        if prod_shape:
            self.shape = f"{mode}-prod-shape"
        elif seeded:
            self.shape = f"{mode}-seeded"
        else:
            self.shape = mode
        self.image_tag = image_tag
        self.dir = (root / self.project).resolve()
        self.cameras = self.dir / "cameras"
        self.artifacts = self.dir / "artifacts"
        self.env_file = self.dir / "env"
        self.compose_file = self.dir / "compose.json"
        self.summary: dict[str, Any] = {
            "date": datetime.now(UTC).isoformat(timespec="seconds"),
            "mode": self.shape,
            "project": self.project,
            "run_dir": str(self.dir),
            "engine": engine,
            "image_tag": image_tag,
            "results": {},
        }
        if shard is not None:
            # [r264] A sharded run's record names its shard, so a merged
            # inventory judgment (and the MEASURE table) can say what each run
            # was. Absent when unset, so today's records byte-match today's.
            self.summary["shard"] = f"{shard[0]}/{shard[1]}"
        if golden_specs is not None:
            # [r287] A limited run's record names the specs it witnesses, in the
            # option's own order -- same discipline as the shard above: absent
            # when unset, so today's records byte-match today's.
            self.summary["golden_specs"] = list(golden_specs)
        if pytest_k is not None:
            self.summary["pytest_k"] = pytest_k
        if playwright_grep is not None:
            self.summary["playwright_grep"] = playwright_grep
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
        try:
            result = subprocess.run(
                list(command),
                cwd=cwd,
                env=dict(env) if env is not None else compose_environment(os.environ),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as stalled:
            # A stall is an outcome a caller that said check=False has to be
            # able to read, and raising here is strictly worse than returning:
            # the raise flies past golden() to the harness's catch-all, which
            # discards golden()'s results dict (it is only committed on the way
            # out) and skips every step after the stall — so a stalled fetch
            # (ruling 116's browser download, now ruling 143's image pull) would
            # also erase ruling 102's npm_ci entry. A caller who
            # asked check=True wants the exception; a caller who said
            # check=False gets _stalled_result, which says WHAT happened in the
            # stderr instead of just a number.
            if check:
                raise
            _log(f"! {_TIMEOUT_NOTE} after {stalled.timeout} s")
            result = _stalled_result(stalled)
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
        # This machine's name, and what the host aliases resolve to here (a
        # literal such as Docker Desktop's 192.168.65.254 is the host too).
        for name in (socket.gethostname(), *sorted(HOST_ALIASES)):
            try:
                for info in socket.getaddrinfo(name, None):
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
        return self.take_snapshot()

    def take_snapshot(self) -> Snapshot:
        """The machine before the test deployment: what the preflight judges
        and the postflight compares with."""
        before = self.snapshot()
        self._write("snapshot-before.json", before.to_json())
        self.summary["snapshot_before"] = snapshot_brief(before)
        _log(
            f"snapshot: {len(before.containers)} containers "
            f"({sum(c.running for c in before.containers)} running), {len(before.volumes)} volumes"
        )
        return before

    def render(self, before: Snapshot, vlm: AgentGpu | None = None) -> None:
        if self.prod_shape:
            self.render_prod_shape(vlm)
            return
        base = json.loads(
            self.compose(
                [CI_STACK, FAKE_OVERLAY, SINKS_OVERLAY], "config", "--format", "json"
            ).stdout
        )
        deployment = as_test_deployment(
            base,
            project=self.project,
            run_dir=self.dir,
            vlm_url=vlm.url if vlm else None,
            seeded=self.seeded,
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

    def render_prod_shape(self, vlm: AgentGpu | None = None) -> None:
        """The O2.5 production-shape render: `docker-compose.prod.yml` + the
        authored override, decided and checked here, at run time.

        This path deliberately does NOT go through `as_test_deployment` and
        :func:`preflight` (measured: the fail-closed key allowlist refuses the
        prod render with 46 problems, 19 of them `restart`, plus `pid: host` on
        alloy and node-exporter, which the prod shape genuinely needs to observe
        the host). The authored override is the UR-133/134 transform the spike
        posted, pinned by `scripts/test_prodshape_override.py`; two things can
        only be decided now, and are decided here:

        * the env file — generated by :func:`prod_shape_env`, never the checkout's
          `.env` or the caller's shell (O2.2's rule, unchanged for the prod shape);
        * resource limits — ruling 162 item 2, read from THIS machine's cgroup.

        and one thing the static gate cannot see is re-checked: the engine socket
        on the render `up` will boot from. That is the whole reason a run-time
        twin of the static test exists — a socket `docker-compose.prod.yml` grew
        since the override was authored is invisible to CI and fatal here, because
        opening that socket IS driving the host's engine.
        """
        # [O2.5 venue fixes, ruling 287 item 4] The optional Triton cache seed is a
        # per-run COPY into the run dir, never a host bind: the override binds
        # ${PROD_SHAPE_RUN_ROOT}/triton-cache, so what the gateway boots from is
        # THIS copy -- one run's plan build cannot poison the next run's cache,
        # and the host seed is never written. Copying first (before the env file)
        # means a mistyped seed refuses the run before the engine is asked for
        # anything.
        if seed := os.environ.get("PROD_SHAPE_TRITON_CACHE_SEED"):
            source = Path(seed).resolve()
            if not source.is_dir():
                raise HarnessError(f"Triton cache seed is not a directory: {source}")
            shutil.copytree(source, self.dir / "triton-cache", dirs_exist_ok=True)
        try:
            self.env_file.write_text(
                prod_shape_env(run_dir=self.dir, image_tag=self.image_tag, caller=dict(os.environ)),
                encoding="utf-8",
            )
        except HarnessError as missing:
            # Same exit as a preflight refusal: the deployment never started, and
            # the reason is named ("PODMAN_SOCKET is not set ...").
            raise Refused([str(missing)]) from missing
        rendered = json.loads(
            self.compose([PROD_STACK, PROD_SHAPE_OVERRIDE], "config", "--format", "json").stdout
        )
        sockets = engine_socket_mounts(rendered, socket_path=os.environ.get("PODMAN_SOCKET", ""))
        problems = [
            f"{name} mounts the engine socket {source} -> {target} in the render this run "
            f"would boot; the prod-shape override is expected to drop it "
            f"(scripts/uplevel/docker-compose.prodshape.yml)"
            for (name, source, target) in sockets
        ]
        self.summary["results"]["engine_socket"] = problems or "ok"
        if problems:
            for problem in problems:
                _log(f"REFUSED {problem}")
            # Deliberately before writing the artifact: `up` boots from what is on
            # disk, so a refused render must leave nothing to boot.
            raise Refused(problems)
        # Ruling 256 split O2.5 by venue, and the fake bodies come from the same place the
        # CI tier gets its whole stack: the CI+fake render. The fake service CANNOT be
        # spelled here statically -- its image is hsi-fake-ai and it must be BUILT first
        # (docker/fake-ai/Dockerfile FROMs this run's backend image, so the fake and the
        # backend it answers share one dependency set), and the runner decides per venue
        # which of the two fakes it carries. prod's own build: sections are left exactly as
        # prod spells them: the pre-build builds them under the project tag, and the maui
        # run's gateway is the REAL one, built from prod's own Dockerfile.
        fake_bodies = self.fake_service_bodies()
        fake_gateway = fake_bodies.get("ai-gateway") if vlm else None
        fake_vlm = fake_bodies.get("ai-vlm") if vlm is None else None
        rendered = as_prod_shape_deployment(
            rendered,
            vlm_url=vlm.url if vlm else None,
            fake_gateway=fake_gateway,
            fake_vlm=fake_vlm,
            run_dir=self.dir,
        )
        device_changes = rendered.pop("_device_changes", [])
        if device_changes:
            # The record names every removed or stripped device (ruling 256): a reader of
            # the summary must be able to see the venue's shape without diffing renders.
            self.summary["results"]["device_changes"] = device_changes
            _log(f"prod-shape device changes: {'; '.join(device_changes)}")
        # Ruling 162 item 2's limits decision runs on the render AFTER the transform: the
        # spliced fake bodies carry the CI tier's deploy.resources.limits (0.5 CPU / 512M),
        # and a decision taken before the splice would strip prod's limits and then let the
        # splice re-introduce ones a rootless container refuses -- exactly the failure the
        # strip exists to remove. The artifact below is written after this too, so
        # prod-rendered.json is the shape the run BOOTS (post-splice, post-limits), not the
        # pre-splice render the transform then edited out of band.
        self.summary["limits"] = decide_resource_limits(rendered, read_subtree_control())
        _log(self.summary["limits"])
        self._write("prod-rendered.json", rendered)
        # The CI tier's render() writes self.compose_file and EVERY later lifecycle call
        # boots it -- `up`, `_address` (`compose port`), `collect` (`logs`/`ps`) and
        # `teardown` (`down -v`) all go through deployment(). Without this line a
        # --real --prod-shape run came up on the two YAML files and then failed at its
        # first deployment() call with no such file, teardown included, leaving the run's
        # containers up: the exact hole UR-135 (teardown with `down -v` and nothing else)
        # exists to close. Same file, same path as the CI tier, so there is one boot path.
        self.compose_file.write_text(
            json.dumps(boot_render(rendered), indent=2) + "\n", encoding="utf-8"
        )
        _log(f"prod-shape render: {len(rendered.get('services') or {})} services")
        self.summary["images"] = {
            name: service.get("image") for name, service in (rendered.get("services") or {}).items()
        }
        self.prebuild_images()
        # [O2.5 venue fixes, ruling 287 item 4] The opt-in Triton export: ONNX
        # (yolo26, CPU; reid) then the reid TensorRT plan on the serving GPU --
        # maui's real-gateway venue only, because the sandbox venue's gateway is
        # the fake and there is no Triton, no exporter and no model repository in
        # it to witness. ONNX comes FIRST in the one script because
        # ai/gateway/export/export_reid.py's B2.2 provenance rule refuses to
        # compile a plan from an ONNX no record vouches for -- the other order
        # can only fail on the venue.
        if os.environ.get("PROD_SHAPE_EXPORT_TRITON") == "1":
            if fake_gateway is not None:
                raise HarnessError(
                    "PROD_SHAPE_EXPORT_TRITON requires the real-gateway maui venue: the "
                    "sandbox run replaces the real gateway (its fake carries no Triton "
                    "server, exporter or model repository)"
                )
            # This one-off creates project resources too: any failure must reach
            # the same down -v and postflight as a failed stack boot, so `started`
            # is armed BEFORE the first `compose run` -- the same gate `up()` sets.
            self.started = True
            # TensorRT 11 uses the graph's own types and dropped --fp16 (diagnostic
            # db7dbe): fp16 stays the shipped default and fp32 is the venue's
            # opt-in (attempt a7c96f: FP32 plan build 83.9s, native reid embedding
            # [1,512]). Validated here, not in the script, so a bad value never
            # reaches the venue's shell as generated text.
            precision = os.environ.get("PROD_SHAPE_REID_PRECISION", "fp16")
            if precision not in {"fp16", "fp32"}:
                raise HarnessError(
                    f"PROD_SHAPE_REID_PRECISION must be fp16 or fp32, got {precision!r}"
                )
            script = f"""
set -euo pipefail
mkdir -p /models/cache/yolo26/1 /models/cache/reid/1
python3 /app/gateway/export/export_yolo26.py --model-path /models/zoo/yolo26/yolo26m.pt --output-path /models/cache/yolo26/1/model.onnx --device cpu
python3 /app/gateway/export/export_reid.py --model-path /models/zoo/osnet-ain-x1-0/osnet_ain_x1_0_msmt17.pth --output-path /models/cache/reid/1/model.onnx
python3 /app/gateway/export/export_reid.py --model-path /models/zoo/osnet-ain-x1-0/osnet_ain_x1_0_msmt17.pth --output-path /models/cache/reid/1/model.plan --precision {precision}
"""
            exported = self.deployment(
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "--entrypoint",
                "/bin/bash",
                "ai-gateway",
                "-c",
                script,
                timeout=1800,
                check=False,
            )
            # The export's own stream is the artifact: the venue reads what the
            # exporter said, not just that it failed.
            (self.artifacts / "triton-export.txt").write_text(
                (exported.stdout or "") + "\n" + (exported.stderr or ""), encoding="utf-8"
            )
            if exported.returncode != 0:
                raise HarnessError(
                    f"Triton export failed ({exported.returncode}); see triton-export.txt"
                )
            _log(f"Triton export ok ({precision} reid plan); see triton-export.txt")

    def fake_service_bodies(self) -> dict[str, dict[str, Any]]:
        """The fake AI services the CI tier renders, by name, for the prod-shape transforms.

        The fake overlay cannot render alone (measured: its services join ``ci-net``,
        which only ``docker-compose.ci.yml`` defines, so a solo render is refused by
        compose rather than silently mixing with the prod stack) -- rendering CI+fake
        here yields exactly two bodies worth taking, the ones ruling 256's two venues
        swap in: ``ai-vlm`` and ``ai-gateway``. The bodies carry the fake's own image
        (``hsi-fake-ai``), command, environment, healthcheck and deploy limits, and
        nothing device-shaped. The prod render's network membership stays the prod
        render's (``security-net``): the transform keeps it.
        """
        rendered = json.loads(
            self.compose([CI_STACK, FAKE_OVERLAY], "config", "--format", "json").stdout
        )
        services = rendered.get("services") or {}
        bodies = {
            name: copy.deepcopy(service)
            for name, service in services.items()
            if name in ("ai-vlm", "ai-gateway")
        }
        # [O2.5 venue fixes] Never reuse or overwrite a shared fake: on the venue the
        # fake is BUILT (docker/fake-ai/Dockerfile FROMs this run's backend), and the
        # overlay's `hsi-fake-ai:${IMAGE_TAG:-latest}` is a host-GLOBAL name whose
        # `latest` could carry another checkout's fake code, on top of whatever base
        # built it. So the prod-shape run renames the fake to the tag `build_images`
        # derives for it (``<project>-<service>:latest``, exactly what `up --no-build`
        # looks for) and pins its base to the backend image THIS run's pre-build
        # builds first. The CI tier keeps the shared name on purpose: one checkout,
        # one job, one engine -- a shared tag there is not a lie.
        if self.prod_shape:
            for name, body in bodies.items():
                if "build" not in body:
                    continue
                body["image"] = f"{self.project}-{name}:latest"
                body["build"].setdefault("args", {})["BACKEND_IMAGE"] = (
                    f"{self.project}-backend:latest"
                )
        return bodies

    def prebuild_images(self) -> None:
        """Build the stack's `build:` images BEFORE `up`, so `up` builds nothing.

        The prod stack ships six services with `build:` in the boot document and
        five of them declare no `image:` at all (grafana declares both), so
        `up --wait` starts building during the boot — and on the
        first prod-shape run that is exactly where it died (operator record
        6166020894): grafana's host-local name answered `denied` to a PULL (an
        absent `image:` on a build service is pulled before it is built,
        measured), and the five image-less services went to a builder that
        bootstraps a `buildx_buildkit_default` CONTAINER, which needs both a
        startable container and cgroup delegation this class of machine does not
        have. Doing it here instead means a failure names itself here, in front
        of a boot that would otherwise report it as "backend is not running".

        Two measured properties shape the call:

        * ``DOCKER_BUILDKIT=0`` is honoured by ``compose build`` (measured, both
          branches) and makes the daemon's own builder answer — no builder
          container, so neither the cgroup wall nor the init-binary wall applies;
          ``DOCKER_HOST`` and friends are carried from the caller so the build
          talks to the engine `up` will boot, not a different one;
        * a name the engine already has is NOT rebuilt. That is `up`'s own
          lookup (`image inspect`, measured over the compat API: 0 present, 1
          absent), and it matters because grafana's name is host-local and NOT
          namespaced by the compose project — an image that is there IS the image
          production would boot, so rebuilding it would make the tier witness
          something production does not run, and cost hours doing it.

        The images come from :func:`build_images`, applied to the boot document
        `up` boots, so this cannot drift from the names `up` will look for. It
        matters that `up` passes ``--no-build``: a service whose manifest says
        ``pull_policy: build`` (docker-compose.fake-ai.yml:34) makes a plain
        ``up`` rebuild its image through BuildKit even when this method has just
        built it — and BuildKit's ``RUN`` steps need the cgroup delegation this
        venue's rootless engine cannot grant, which is the wall this method
        exists to dodge.
        """
        boot = json.loads(self.compose_file.read_text(encoding="utf-8"))
        wanted = build_images(boot, project=self.project)
        to_build: list[str] = []
        present: list[str] = []
        for name, image in sorted(wanted.items()):
            lookup = self._run([self.engine, "image", "inspect", image], check=False, echo=False)
            if lookup.returncode == 0:
                present.append(name)
                _log(f"prebuild: {name} -> {image} is already in the engine")
            else:
                to_build.append(name)
        # `built` is filled from the build's EXIT, never from what was about to be
        # attempted: a run that died building must not leave a summary asserting it
        # built. `to_build` carries the intent, `exit` the verdict.
        self.summary["prebuild"] = {"built": [], "present": present, "to_build": to_build}
        if not to_build:
            _log(f"prebuild: nothing to build ({len(present)} already present)")
            return
        _log(f"prebuild: {', '.join(to_build)}")
        # check=False on purpose: a stalled build comes back as a readable result
        # rather than a TimeoutExpired flying past this method, and either way the
        # message below names the services and quotes what the engine said.
        # [O2.5 venue fixes] Under prod_shape the buildables go up in TWO passes:
        # the fake services FROM the backend image (`docker/fake-ai/Dockerfile`'s
        # BACKEND_IMAGE arg), so the backend and grafana must exist before the
        # fakes build, and one builder pass per group keeps the failure message
        # readable -- a fake FROM an absent backend image reads as a mystery, not
        # as "the backend build died". The base pass is also `--no-cache` under
        # prod_shape: the venue witnesses THIS checkout's build, and a cached
        # layer from a previous checkout's backend is exactly what the fake's
        # `COPY backend/` exists to displace -- a cache hit would boot code the
        # run never checked. CI keeps one pass and no flag: its runs build once
        # per job from a clean checkout, and the fake tier stays as it is.
        fake = [
            name
            for name in to_build
            if str(boot["services"].get(name, {}).get("build", {}).get("dockerfile", "")).endswith(
                "docker/fake-ai/Dockerfile"
            )
        ]
        groups = (
            ([name for name in to_build if name not in fake], fake)
            if self.prod_shape
            else (to_build,)
        )
        outputs = []
        built: list[str] = []
        for group in groups:
            if not group:
                continue
            result = self.deployment(
                "build",
                *group,
                *(["--no-cache"] if self.prod_shape else []),
                timeout=PREBUILD_TIMEOUT_SECONDS,
                check=False,
                env={**compose_environment(os.environ), "DOCKER_BUILDKIT": "0"},
            )
            outputs.append(result)
            if result.returncode == 0:
                built.extend(group)
            else:
                break
        result.stdout = "\n".join(item.stdout or "" for item in outputs)
        result.stderr = "\n".join(item.stderr or "" for item in outputs)
        # The build's own stream is the artifact: it is what the operator's first
        # run did not have, and a build that later goes wrong is read from here.
        (self.artifacts / "prebuild.txt").write_text(
            f"to build: {to_build}\nalready present: {present}\nexit: {result.returncode}\n\n"
            f"--- stdout ---\n{result.stdout or ''}\n--- stderr ---\n{result.stderr or ''}\n",
            encoding="utf-8",
        )
        self.summary["prebuild"]["exit"] = result.returncode
        if result.returncode != 0:
            tail = " ".join((result.stderr or result.stdout or "").split())[-1200:]
            raise HarnessError(
                f"the pre-build of {', '.join(to_build)} exited {result.returncode} "
                f"(asked for the engine's own builder via DOCKER_BUILDKIT=0) — "
                f"compose said: {tail}"
            )
        # `built` is filled from each pass's EXIT, never from intent: a run that
        # died in the base pass must not claim the fakes it never started.
        self.summary["prebuild"]["built"] = built

    def up(self, vlm: AgentGpu | None = None) -> None:
        self.started = True
        # [O2.5 venue fixes, ruling 287] The relay's host half arms HERE, the
        # first arm point the teardown gate already covers: `started` just
        # flipped, and every later failure path is `_finish`'s. Earlier
        # placement would leak -- a render refusal, a wait_ready failure or a
        # prebuild failure leaves an armed half the `started` gate never joins
        # (the pre-start leak shape `_cleanup_images` sits outside that gate
        # for). Inside up() the pool port is already known (`vlm.start()` parsed
        # it; `wait_ready` confirmed it) and the socket is armed before the
        # sidecar's healthcheck can first run inside `up --wait`.
        if os.environ.get("PROD_SHAPE_VLM_RELAY") == "1" and vlm is not None and vlm.host_port:
            self.vlm_dial_port = vlm.host_port
            relay = VlmRelay(self)
            relay.arm()
            self.relay = relay
        # --no-build (ruling 274 as amended, record IC_kwDOQs9zJM8AAAABdusUHA): the
        # flag rides along exactly when `prebuild_images()` ran in this run — the
        # prod-shape modes. A `build:` service whose manifest sets
        # `pull_policy: build` (docker-compose.fake-ai.yml:34) is rebuilt by a plain
        # `up` through BuildKit even when the prebuild has just built it, and
        # BuildKit's RUN steps need the cgroup delegation the sandbox venue's
        # rootless engine cannot grant (attempt 4, operator report 6280195057).
        # Fake mode never ran a prebuild, so its `up` stays plain: CI's fake-AI
        # runs build `hsi-fake-ai` themselves at `up`, and `--no-build` there
        # strands them with `No such image` (measured on #7298).
        build_flag = ["--no-build"] if self.prod_shape else []
        try:
            self.deployment(
                "up", "-d", *build_flag, "--wait", "--wait-timeout", "900", timeout=1500
            )
        except HarnessError as boot:
            # The backend's health check calls the VLM, so on --real an
            # unreachable VLM fails `up --wait` first; name that reason if so.
            # But when the reach check ALSO fails it cannot say whether the VLM is
            # down or the stack never came up — and on the first prod-shape run
            # (operator, 2026-10-14, #7037) it said "the backend cannot reach the
            # VLM … or is not running" while the VLM was serving fine and compose
            # had died building five image-less services. The compose tail is
            # therefore carried into the message and chained: a reader has to be
            # able to tell a boot failure from a reachability one.
            if vlm is None:
                raise
            tail = " ".join(str(boot).split())[-400:]
            # The reach probe dials the path the BACKEND itself uses -- the
            # relay form when the knob is on, the alias form as today
            # otherwise -- so a failure is reported on the wire that failed,
            # and the relay host half's own dial accounting names the broken
            # hop when the sidecar pair is implicated.
            if self.relay is not None:
                hop = f" (the relay host half dialed {self.vlm_dial_host}:{self.vlm_dial_port} {self.relay.dials}x, last error: {self.relay.last_error})"
            else:
                hop = ""
            try:
                self.check_vlm_reach(str(self.vlm_container_url(vlm)))
            except HarnessError as reach:
                raise HarnessError(
                    f"{reach}{hop}; and `up` itself failed, so the stack may simply never "
                    f"have come up — compose said: {tail}"
                ) from boot
            raise HarnessError(
                f"`up` failed while the VLM is reachable; compose said: {tail}"
            ) from boot
        self.api = self._address("backend", 8000)
        self.ui = self._address("frontend", 8080)
        _log(f"up: api {self.api}, ui {self.ui}")
        self.summary["urls"] = {"api": self.api, "ui": self.ui}
        if vlm is not None:
            self.check_vlm_reach(str(self.vlm_container_url(vlm)))
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
                f"the backend cannot reach the VLM at {url}, or is not running: "
                f"{(probe.stderr or probe.stdout).strip()[-1000:]}"
            )
        _log(f"the backend reaches the VLM at {url}")

    def vlm_container_url(self, vlm: AgentGpu) -> str:
        """The VLM URL the run's containers dial: the relay form when the relay
        is armed (what the backend actually got as AI_VLM_URL), the alias form
        otherwise. One source for both the transform and the reach probe, so
        they cannot disagree."""
        if self.relay is not None:
            return VlmRelay.RELAY_URL
        return str(vlm.url)

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

    def seed_debug_fixtures(self) -> None:
        """Plant the ruling-127/187/192/215 CI fixtures for --seeded runs:
        1. Two deterministic GET recordings via X-Debug-Record: true (F-154..F-156);
        2. An unreferenced file under /app/data/thumbnails (F-186);
        3. Fill the 20 MiB /app/data volume (parent of VIDEO_THUMBNAILS_DIR) past 90%
           for GET /api/system/storage (F-012, ruling 192 item 2);
        4. One KnownPerson and one FaceEmbedding row with a fixed 512-dim float32
           vector and test-only model_id (F-278, ruling 215 item 1);
        5. Verification that HSI_FAULT_SEED=1 opened a circuit breaker (F-138) and
           a burst of Redis misses trips the hit-ratio threshold (F-171).
        """
        for path in ("/api/system/config", "/api/system/health/ready"):
            status, body = _http(
                "GET",
                self.api + path,
                headers={"X-Debug-Record": "true"},
            )
            if status != 200:
                raise HarnessError(f"seeding recorded request {path} answered {status}: {body}")
        rec_status, rec_body = _http("GET", self.api + "/api/debug/recordings")
        if (
            rec_status != 200
            or not isinstance(rec_body, Mapping)
            or int(rec_body.get("total") or 0) < 2
        ):
            raise HarnessError(
                f"expected >= 2 seeded recordings from GET /api/debug/recordings, "
                f"got {rec_status}: {rec_body}"
            )

        planted = self.deployment(
            "exec",
            "-T",
            "backend",
            "python",
            "-c",
            "import os, time; from pathlib import Path; "
            "p = Path('/app/data/thumbnails/seeded-orphan.jpg'); "
            "p.parent.mkdir(parents=True, exist_ok=True); "
            "p.write_bytes(b'seeded-orphan-fixture'); "
            "old = time.time() - 48 * 3600; "
            "os.utime(p, (old, old)); "
            "print(p.stat().st_size)",
        )
        if not planted.stdout.strip().splitlines()[-1:]:
            raise HarnessError("planting seeded-orphan.jpg produced no size output")
        orphan_status, orphan_body = _http(
            "POST", self.api + "/api/system/cleanup/orphaned-files?dry_run=true"
        )
        if (
            orphan_status != 200
            or not isinstance(orphan_body, Mapping)
            or int(orphan_body.get("orphaned_count") or 0) < 1
        ):
            raise HarnessError(
                f"expected >= 1 orphaned file after planting fixture, "
                f"got {orphan_status}: {orphan_body}"
            )

        filled = self.deployment(
            "exec",
            "-T",
            "backend",
            "python",
            "-c",
            "import shutil; from pathlib import Path; "
            "data = Path('/app/data'); "
            "usage = shutil.disk_usage(data); "
            "fill = max(0, int(usage.total * 0.93) - usage.used); "
            "(data / '.seeded-disk-fill').write_bytes(b'\\x00' * fill); "
            "after = shutil.disk_usage(data); "
            "print(round(after.used / after.total * 100, 2))",
        )
        if not filled.stdout.strip().splitlines()[-1:]:
            raise HarnessError("filling /app/data past 90% produced no output")
        storage_status, storage_body = _http("GET", self.api + "/api/system/storage")
        if (
            storage_status != 200
            or not isinstance(storage_body, Mapping)
            or float(storage_body.get("disk_usage_percent") or 0) < 90.0
        ):
            raise HarnessError(
                f"expected disk_usage_percent >= 90.0 from GET /api/system/storage, "
                f"got {storage_status}: {storage_body}"
            )

        seeded_face = self.deployment(
            "exec",
            "-T",
            "backend",
            "python",
            "-c",
            "import asyncio, struct\n"
            "from backend.core.database import close_db, get_session, init_db\n"
            "from backend.models.face_identity import FaceEmbedding, KnownPerson\n"
            "async def _seed():\n"
            "  await init_db()\n"
            "  try:\n"
            "    async with get_session() as s:\n"
            "      p = KnownPerson(name='Seeded Known Person', is_household_member=True, notes='Seeded by feature_check.py for F-278')\n"
            "      s.add(p)\n"
            "      await s.flush()\n"
            "      e = FaceEmbedding(person_id=p.id, embedding=struct.pack('<512f', 1.0, *([0.0] * 511)), model_id='test-only-seeded-vector', quality_score=0.95)\n"
            "      s.add(e)\n"
            "      await s.commit()\n"
            "      print(f'{p.id}:{e.id}')\n"
            "  finally:\n"
            "    await close_db()\n"
            "asyncio.run(_seed())",
        )
        if not seeded_face.stdout.strip().splitlines()[-1:]:
            raise HarnessError("seeding known person and face embedding produced no output")
        kp_status, kp_body = _http("GET", self.api + "/api/known-persons")
        kp_items = kp_body.get("items") if isinstance(kp_body, Mapping) else None
        if (
            kp_status != 200
            or not isinstance(kp_items, list)
            or not any(
                isinstance(item, Mapping) and int(item.get("embedding_count") or 0) >= 1
                for item in kp_items
            )
        ):
            raise HarnessError(
                f"expected >= 1 seeded known person with embedding_count >= 1 from "
                f"GET /api/known-persons, got {kp_status}: {kp_body}"
            )

        cb_status, cb_body = _http("GET", self.api + "/api/system/circuit-breakers")
        if (
            cb_status != 200
            or not isinstance(cb_body, Mapping)
            or int(cb_body.get("open_count") or 0) < 1
        ):
            raise HarnessError(
                f"expected >= 1 open circuit breaker from HSI_FAULT_SEED=1, "
                f"got {cb_status}: {cb_body}"
            )

        for _ in range(4):
            ps_status, ps_body = _http("GET", self.api + "/api/debug/pipeline-state")
            if ps_status != 200:
                raise HarnessError(
                    f"seeding Redis misses via GET /api/debug/pipeline-state "
                    f"answered {ps_status}: {ps_body}"
                )

        self.summary["results"]["seeded"] = "ok"
        _log(
            "seeded debug fixtures: 2 recordings, 1 orphan file, >90% disk fill, "
            "1 known person + face embedding, open redis breaker"
        )

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
            # The prod shape's mount rule is its render's (ruling 287 item 12):
            # the same engine_socket_mounts the UR-134 re-check ran, keyed on the
            # caller's socket. None on every other shape keeps the CI rule.
            prod_shape_socket=os.environ.get("PODMAN_SOCKET", "") or None
            if self.prod_shape
            else None,
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

    def _gpu_history_fixture(self, ids: list[str], *, restore: bool) -> None:
        """Temporary historical snapshots only; never write active GPU config."""
        script = f"""
import asyncio, json
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from backend.core.config import get_settings
ids = {ids!r}
restore = {restore!r}
async def main():
    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.begin() as connection:
            if restore:
                for row_id in ids:
                    await connection.execute(text("DELETE FROM gpu_configuration_versions WHERE id=CAST(:id AS uuid)"), {{"id": row_id}})
                remaining = await connection.scalar(text("SELECT count(*) FROM gpu_configuration_versions WHERE id IN (CAST(:a AS uuid), CAST(:b AS uuid))"), {{"a": ids[0], "b": ids[1]}})
                assert remaining == 0, remaining
                print("F182_FIXTURE restored; remaining=0")
            else:
                maximum = await connection.scalar(text("SELECT coalesce(max(version_number), 0) FROM gpu_configuration_versions"))
                for index, (strategy, gpu_index, description) in enumerate([
                    ("vram_based", 0, "o25-f182-source-provisional"),
                    ("balanced", None, "o25-f182-target-provisional"),
                ]):
                    assignments = json.dumps([{{"service": "ai-vlm", "gpu_index": gpu_index}}])
                    await connection.execute(text("INSERT INTO gpu_configuration_versions (id, version_number, strategy, assignments, description, created_by) VALUES (CAST(:id AS uuid), :version, :strategy, CAST(:assignments AS jsonb), :description, 'feature-check-provisional')"), {{"id": ids[index], "version": maximum + index + 1, "strategy": strategy, "assignments": assignments, "description": description}})
                print("F182_FIXTURE seeded=2; provisional=true")
    finally:
        await engine.dispose()
asyncio.run(main())
"""  # noqa: S608 - SQL values stay bound; interpolation only emits Python literals.
        result = self.deployment(
            "exec", "-T", "backend", "python", "-c", script, check=False, timeout=60
        )
        action = "restore" if restore else "seed"
        (self.artifacts / f"gpu-history-{action}.txt").write_text(
            (result.stdout or "") + (result.stderr or ""), encoding="utf-8"
        )
        self.summary["results"].setdefault("gpu_history_fixture", {"provisional": True})[action] = (
            "ok" if result.returncode == 0 else f"exit {result.returncode}"
        )
        if result.returncode != 0:
            raise HarnessError(f"GPU history fixture {action} failed; see gpu-history-{action}.txt")
        _log(f"GPU history fixture {action}: ok (F-182 provisional)")

    def golden(self) -> list[str]:
        # Item 14's native-scenario capture ([r287b]) is NOT in this correction:
        # its knob stays inert here, so a run can never substitute the authored
        # book until the package that owns the capture lands.
        if os.environ.get("PROD_SHAPE_GPU_HISTORY_FIXTURE") != "1":
            return self._golden()
        if not self.prod_shape:
            raise HarnessError("GPU history fixture is only for --prod-shape")
        ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        self._write("gpu-history-fixture.json", {"ids": ids, "provisional": True})
        try:
            self._gpu_history_fixture(ids, restore=False)
            return self._golden()
        finally:
            # Delete exactly our UUIDs, even if seeding or a golden leg fails.
            self._gpu_history_fixture(ids, restore=True)

    def _sink_env_host(self, env_key: str) -> str:
        """One sink's in-network address, as the backend's env spells it.

        The single spelling lives in the overlay (``docker-compose.sinks.yml``
        sets ``FEATURE_CHECK_SINK_*_HOST`` on the backend), and the run's
        rendered ``compose.json`` is the document compose itself consumes — so
        the golden env reads the value OFF that file rather than carrying a
        second copy a renumber could desync. run_check renders before golden
        (feature_check.py:3967 → :3976), so in production the file is always
        there; a run that reaches golden without a rendered stack has no
        backend to have an env, and the sink block has no business exporting
        a dial target for one — raise the same way ``_address`` does for an
        unpublished port.
        """
        if not self.compose_file.exists():
            raise HarnessError(
                f"no rendered compose.json for the golden env: {env_key} "
                "must come off the rendered backend env (run_check renders before golden)"
            )
        boot = json.loads(self.compose_file.read_text(encoding="utf-8"))
        raw = (boot.get("services", {}).get("backend", {}) or {}).get("environment") or []
        entries = raw if isinstance(raw, list) else [f"{k}={v}" for k, v in raw.items()]
        for entry in entries:
            key, _, value = str(entry).partition("=")
            if key == env_key:
                return value
        raise HarnessError(
            f"the rendered backend env carries no {env_key}; "
            "docker-compose.sinks.yml lost the sink env (a golden leg dials it)"
        )

    def _sink_webhook_host(self) -> str:
        return self._sink_env_host("FEATURE_CHECK_SINK_WEBHOOK_HOST")

    def _sink_push_host(self) -> str:
        return self._sink_env_host("FEATURE_CHECK_SINK_PUSH_HOST")

    def _golden(self) -> list[str]:
        env = {
            **os.environ,
            "FEATURE_CHECK_MODE": self.mode,
            "FEATURE_CHECK_PROD_SHAPE": "1" if self.prod_shape else "0",
            "FEATURE_CHECK_RUN_DIR": str(self.dir),
            "FEATURE_CHECK_API_URL": self.api,
            "FEATURE_CHECK_UI_URL": self.ui,
            "FEATURE_CHECK_CAMERA_ROOT": str(self.cameras),
            "FEATURE_CHECK_CAMERAS": str(self.artifacts / "cameras.json"),
            "FEATURE_CHECK_SCENARIOS": str(SCENARIO_DIR / "scenarios.json"),
            "FEATURE_CHECK_ADMIN_USERNAME": self.admin["username"],
            "FEATURE_CHECK_ADMIN_PASSWORD": self.admin["password"],
        }
        # [r308a] The notification sinks' golden env: the host-side loopback URL
        # of each sink's read-back surface (resolved the way the backend's own
        # address is, `compose port`), plus the marking the run stands up. The
        # webhook's and push's in-network addresses are NOT exported as URLs —
        # the golden env carries them as FEATURE_CHECK_SINK_*_HOST, the SAME
        # spelling the backend container's env holds (read off the rendered
        # compose.json the run booted, so the leg sees the address the backend
        # actually dials and no second copy of the overlay's value can drift).
        # From inside the backend container the host-side loopback URL points
        # at the backend, not the sink, which is why the two sides need
        # different spellings.
        #
        # B4.2 (4n-alerting.md's real-tier line): the gate is prod-shape, not
        # fake-mode. The sinks are golden-path services, not AI fakes — render()
        # composes the sinks overlay for EVERY non-prod-shape mode, so --real
        # boots them too (test_feature_check.py's real-deployment pin), and a
        # gate here that withheld the env on --real made the sink-receipt leg
        # skip on exactly the tier the design's "runs a real verdict through to
        # the webhook sink" clause names.
        if not self.prod_shape:
            env["FEATURE_CHECK_SINKS_MODE"] = SINKS_MODE
            env["FEATURE_CHECK_SINK_SMTP_URL"] = self._address("mail-sink", 8025)
            env["FEATURE_CHECK_SINK_MAIL_HTTP_URL"] = self._address("mail-sink", 8026)
            env["FEATURE_CHECK_SINK_WEBHOOK_URL"] = self._address("webhook-sink", 8091)
            env["FEATURE_CHECK_SINK_PUSH_URL"] = self._address("push-sink", 8092)
            env["FEATURE_CHECK_SINK_WEBHOOK_HOST"] = self._sink_webhook_host()
            # B4.3: the push leg registers a subscription aimed at the address
            # the BACKEND will dial (the sink's in-network name), so it reads
            # the same document the webhook host above comes off.
            env["FEATURE_CHECK_SINK_PUSH_HOST"] = self._sink_push_host()
        problems = []
        results: dict[str, Any] = {}
        project_name = "golden-seeded" if self.seeded else "golden"
        # [r264] Sharded CI runs the backend golden tests ONCE, in shard 1 (the
        # package's Build box). A shard i>1 records the skip instead of running
        # it, the same record shape the seeded branch below writes, so the
        # merged summary the fan-in builds carries one backend leg set while
        # every shard's record still says what IT ran. The skip branch makes no
        # report, so it calls neither junit_results nor golden_execution_problems
        # -- nothing to judge: the leg's verdict lives in shard 1's summary,
        # whose own in-run call already covered the execution-problems check.
        runs_backend = (self.shard is None or self.shard[0] == 1) and (
            self.playwright_grep is None or self.pytest_k is not None
        )
        if not self.seeded and runs_backend and sorted(BACKEND_GOLDEN.glob("**/test_*.py")):
            junit = self.artifacts / "golden-backend.xml"
            pytest_argv = [
                "uv",
                "run",
                "pytest",
                str(BACKEND_GOLDEN.relative_to(REPO_ROOT)),
                f"--junitxml={junit}",
            ]
            if self.pytest_k is not None:
                pytest_argv.extend(["-k", self.pytest_k])
                results["pytest_k"] = self.pytest_k
            result = self._run(
                pytest_argv,
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
            # Ruling 114: the exit code above says the runner finished, not that a
            # spec ran. Judged on the report this run wrote, never on a previous one.
            problems += golden_execution_problems("backend", results["backend_specs"])
        elif self.seeded:
            results["backend"] = "skipped on seeded"
        elif self.playwright_grep is not None and self.pytest_k is None:
            results["backend"] = "skipped on playwright-grep"
        elif not runs_backend:
            i, total = self.shard  # type: ignore[misc]
            results["backend"] = f"skipped on shard {i}/{total}"
        else:
            results["backend"] = "no specs yet"
        runs_playwright = self.pytest_k is None or self.playwright_grep is not None
        if not runs_playwright:
            results["playwright"] = "skipped on pytest-k"
        elif PLAYWRIGHT_CONFIG.exists() and re.search(
            rf"name:\s*['\"]{re.escape(project_name)}['\"]",
            PLAYWRIGHT_CONFIG.read_text(encoding="utf-8"),
        ):
            report = self.artifacts / "golden-playwright"
            junit = self.artifacts / "golden-playwright.xml"
            # Ruling 102: an operator's tree has no frontend/node_modules -- the
            # harness runs no build, and the repo keeps no committed install. The
            # documented --real leg then exited 1 at ERR_MODULE_NOT_FOUND before a
            # spec could run (the owner's O2.2 operator run). An
            # existing install is NEVER touched: `npm ci` deletes node_modules on
            # entry, so it runs only where there is nothing to delete. The install
            # stays INSIDE the golden-project guard, so a tree without one (every
            # --fake run until a golden project exists) still pays nothing. No
            # `env=` on purpose: compose_environment carries PATH/HOME and nothing
            # else, which keeps FEATURE_CHECK_ADMIN_PASSWORD out of a child that
            # does not need it. Timeout 1800s, not the 300s default -- a cold
            # install of this lock (1176 resolved packages) is minutes on a
            # cold cache. The result is accounted, not raised: an operator who
            # cannot reach the registry sees a named step in summary.json.
            if not FRONTEND_MODULES.is_dir():
                install = self._run(
                    ["npm", "ci"],
                    check=False,
                    timeout=1800,
                    cwd=FRONTEND,
                )
                results["npm_ci"] = (
                    "ok" if install.returncode == 0 else f"exit {_exit_word(install)}"
                )
                if install.returncode != 0:
                    problems.append(
                        f"golden: npm ci in frontend/ exited {install.returncode}: "
                        f"{(install.stderr or install.stdout).strip()[-400:]}"
                    )
            # Ruling 143 replaces ruling 116's browser install. The leg used to
            # run `npx playwright test` on the HOST, which meant the host needed
            # Chromium: npm ci brings the runner but not the browser, so the
            # operator's --real run failed every spec in about 3 ms on
            # "browserType.launch: Executable doesn't exist at
            # ~/.cache/ms-playwright/chromium_headless_shell-1243/…" and a
            # multi-minute `npx playwright install chromium` was bolted on to fix
            # it. Now the leg runs inside Playwright's own image, which carries
            # the browser AND the system libraries it links, so there is nothing
            # to install and no exit-127 to recover from. The image tag's version
            # comes from frontend/package-lock.json (playwright_image), never a
            # literal here.
            #
            # Ruling 116's firewall clause survives, moved onto the thing that now
            # has to be fetched: "if the registry is blocked, the failure names the
            # host, and the harness does not work around it." So the pull is its
            # own accounted step -- a problem naming the registry and the child's
            # own tail -- rather than an error buried inside the test run's output.
            #
            # The pull is attempted only when the tag is absent locally, which is
            # what `run` would do anyway. That ordering matters for the blocked
            # case: a host that already has the image and cannot reach the registry
            # stays green (correct -- a versioned tag is content, and a present
            # copy of it IS the right browser), while a host with neither gets one
            # named failure instead of two.
            try:
                image = playwright_image(PACKAGE_LOCK)
            except HarnessError as lock_problem:
                # Accounted, not raised: a raise flies past golden() to the
                # harness's catch-all, which discards the results dict and every
                # step after this one. The leg is genuinely red -- there is no
                # image to run -- so it reads red here and says why.
                results["playwright"] = "no image tag"
                problems.append(f"golden: {lock_problem}")
                problems += golden_execution_problems("playwright", {})
                self.summary["results"]["golden"] = results
                return problems
            results["playwright_image"] = image
            have = self._run([self.engine, "image", "inspect", image], check=False, echo=False)
            available = have.returncode == 0
            if available:
                results["playwright_image_pull"] = "present"
            else:
                pull = self._run([self.engine, "pull", image], check=False, timeout=1800)
                available = pull.returncode == 0
                results["playwright_image_pull"] = (
                    "pulled" if available else f"exit {_exit_word(pull)}"
                )
                if not available:
                    problems.append(
                        f"golden: {self.engine} pull of {image} exited {pull.returncode} "
                        f"(registry: {PLAYWRIGHT_IMAGE_REGISTRY} — the host to allow; the "
                        f"harness does not work around a block): "
                        f"{(pull.stderr or pull.stdout).strip()[-400:]}"
                    )
            if not available:
                # The leg cannot run and no image means no specs: that is exactly
                # the evidential hole ruling 114 exists for, so it is reported as
                # one rather than left as a silent gap. The named pull failure
                # above already carries the host; this says the leg did not run.
                results["playwright"] = "image unavailable"
                results["playwright_specs"] = {}
                problems += golden_execution_problems("playwright", {})
                self.summary["results"]["golden"] = results
                return problems
            # The leg, in the image. Same argv as before -- --project=golden,
            # --output=<run dir>, --reporter=list,junit -- because ruling 143's
            # first Done-when is that the fake-tier golden passes "with the same
            # counts"; only the wrapper changed. Both mounts are at their own
            # absolute paths so `report` and `junit` name the same file on both
            # sides, and the run dir is mounted rw because that is where the leg
            # writes (junit, --output traces, .last-run.json under outputDir).
            # ``--no-install`` because a bare ``npx`` fetches. Measured on this
            # image with the mount stripped of node_modules: ``npx playwright
            # --version`` printed "npm warn exec The following package was not
            # found and will be installed: playwright@1.64.0" and exited 0, on a
            # 1.63.0 image whose browser builds are 1.63.0's. So a tree whose
            # ``npm ci`` above failed does not fail loudly -- it runs a runner
            # the repo does not lock, against browsers it does not match, and the
            # report reads as a golden pass that witnesses nothing (UR-128). On a
            # host where npm registry is blocked the same fetch instead fails
            # inside the leg's output, where ruling 116's firewall clause cannot
            # name it, while the npm_ci step already said "exit 243". With the
            # flag the refusal is immediate and legible: "npx canceled due to
            # missing packages and no YES option" (measured, exit 1), which is
            # ruling 116's own reason for asking the lock-resolved runner, now
            # enforced at the place ruling 143 moved the leg to. With a real
            # install the flag is inert -- same tree, mounted :ro, it printed
            # "Version 1.63.0".
            inner_parts = [
                "npx",
                "--no-install",
                "playwright",
                "test",
                f"--project={project_name}",
                shlex.quote(f"--output={report}"),
                "--reporter=list,junit",
            ]
            # [r282] A manifest-sharded run selects its files HERE, host-side,
            # and hands them to the leg as FEATURE_CHECK_GOLDEN_FILES; the
            # count-based --shard append below is skipped when a selection was
            # made. The route is OPT-IN through $FEATURE_CHECK_SHARD_MANIFEST:
            # [r264]'s --shard keeps its count-based meaning byte for byte for
            # every existing caller (its pins pin that argv), and the workflow
            # flips the manifest route on per job -- so a head without this
            # opt-in behaves exactly as before, and flipping it on is the
            # workflow's decision, visible in its diff. Reading the manifest in
            # the harness (not in the config) keeps the split a fact the run
            # record can witness: the selection is recorded in results.golden,
            # where the fan-in and the pins can judge it, instead of being
            # re-derived inside the image. Under the opt-in the manifest is
            # REQUIRED (fail closed: a silent fall-back to the count split
            # would run the whole suite on every cell).
            golden_files_env: str | None = None
            if self.shard is not None and os.environ.get("FEATURE_CHECK_SHARD_MANIFEST"):
                if not GOLDEN_SHARDS_MANIFEST.is_file():
                    raise HarnessError(
                        f"--shard {self.shard[0]}/{self.shard[1]} with "
                        "$FEATURE_CHECK_SHARD_MANIFEST needs "
                        f"{GOLDEN_SHARDS_MANIFEST} and it is not on this tree -- "
                        "the manifest is checked in; its absence is a broken "
                        "checkout, not a shape to fall back from"
                    )
                manifest = json.loads(GOLDEN_SHARDS_MANIFEST.read_text(encoding="utf-8"))
                shard_count = manifest.get("shard_count")
                if not isinstance(shard_count, int) or shard_count < 1:
                    raise HarnessError(
                        f"{GOLDEN_SHARDS_MANIFEST} carries shard_count {shard_count!r}, "
                        "not a positive integer -- the manifest is checked in; run "
                        "scripts/golden_shard_manifest.py to regenerate it"
                    )
                if self.shard[0] > shard_count:
                    raise HarnessError(
                        f"--shard {self.shard[0]}/{self.shard[1]} is outside "
                        f"{GOLDEN_SHARDS_MANIFEST} (shard_count {shard_count}) -- "
                        "the workflow's matrix and the manifest disagree; the run "
                        "refuses rather than witness a partial suite as a full one"
                    )
                index = self.shard[0] - 1
                if index >= len(manifest["shards"]):
                    raise HarnessError(
                        f"{GOLDEN_SHARDS_MANIFEST} declares shard_count {shard_count} "
                        f"but holds {len(manifest['shards'])} shard lists -- regenerate "
                        "it with scripts/golden_shard_manifest.py"
                    )
                selected = manifest["shards"][index]
                golden_files_env = " ".join(selected)
                results["shard_manifest"] = str(GOLDEN_SHARDS_MANIFEST.relative_to(FRONTEND.parent))
                results["shard_files"] = list(selected)
            # No opt-in set: self.shard falls through untouched to the
            # count-based --shard append below -- [r264]'s contract, byte for
            # byte, for every caller that has not asked for the manifest.
            if self.shard is not None:
                # [r264] Playwright's own shard selector: shard i of N. The
                # worker count stays 1 and the project stays serial inside the
                # shard -- the parallelism the package buys is across shards,
                # each on its own stack, never within one. [r282] When the
                # manifest selected this shard's files, this append is skipped:
                # composing both would let Playwright re-split the manifest's
                # own selection (a second, silent partition).
                if golden_files_env is None:
                    i, total = self.shard
                    inner_parts.append(f"--shard={i}/{total}")
            if self.golden_specs is not None:
                # [r287] The named-spec limit: the specs as Playwright
                # positionals -- the runner's own file filter -- so the leg's
                # junit carries only them and golden_execution_problems keeps
                # judging what actually ran. Quoted like --output, into the
                # same shell string; spelled the way main() validated them
                # (repo paths under frontend/tests/golden), which from the
                # leg's `-w frontend` cwd is the same file.
                for spec in self.golden_specs:
                    inner_parts.append(shlex.quote(spec))
            if self.playwright_grep is not None:
                inner_parts.extend(["--grep", shlex.quote(self.playwright_grep)])
                results["playwright_grep"] = self.playwright_grep
            inner = " ".join(inner_parts)
            result = self._run(
                golden_container_command(
                    engine=self.engine,
                    image=image,
                    inner=inner,
                    # Three read-only binds, not one. A path this leg EXPORTS but
                    # does not MOUNT is not an error inside the container — it is
                    # an absent file, and the golden specs read their readiness
                    # with `if (!existsSync(bookPath)) return { ready: false }`,
                    # so an unmounted input silently SKIPS at collection in a leg
                    # that exits 0. Measured on CI: this branch shipped 115
                    # passed / 11 skipped where main's host leg read 118 / 8, and
                    # the three newly-skipped specs are the three that read the
                    # scenario book. SCENARIO_DIR is what they read; SCRIPTS_DIR
                    # is what dashboard-drop's helper execs
                    # (`repoRoot/scripts/feature-check.sh`, harness.ts:179), whose
                    # last line execs its sibling feature_check.py — hence the
                    # directory, not the single file. Both are :ro because both
                    # are inputs; the leg's writes stay in the run dir below.
                    read_only_mounts=[FRONTEND, SCENARIO_DIR, SCRIPTS_DIR],
                    mounts=[self.dir],
                    # [r282] The selection's name rides the argv only when a
                    # selection exists: an unsharded (or count-sharded) leg
                    # keeps today's argv exactly, and the whitelist above
                    # forwards only the names every leg has always had.
                    extra_environment=([R282_GOLDEN_FILES_ENV] if golden_files_env else []),
                ),
                check=False,
                timeout=GOLDEN_LEG_TIMEOUT_S,
                env={
                    **env,
                    "PLAYWRIGHT_JUNIT_OUTPUT_FILE": str(junit),
                    # [r282] The manifest selection, as env -- the config's
                    # testIgnore function ignores every spec file not in this
                    # list. Absent when there is no selection (unsharded or
                    # count-sharded), matching the argv above: no key, no
                    # name, no lie about a selection that did not happen.
                    **({R282_GOLDEN_FILES_ENV: golden_files_env} if golden_files_env else {}),
                },
            )
            (self.artifacts / "golden-playwright.log").write_text(
                result.stdout + result.stderr, encoding="utf-8"
            )
            results["playwright"] = "ok" if result.returncode == 0 else f"exit {result.returncode}"
            results["playwright_specs"] = junit_results(junit)
            if result.returncode != 0:
                problems.append(f"golden: the golden Playwright project exited {result.returncode}")
            problems += golden_execution_problems("playwright", results["playwright_specs"])
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

    def cleanup_images(self) -> int:
        """Remove the images THIS prod-shape run built, and only these.

        A prod-shape run names every image-less ``build:`` service
        ``<project>-<service>:latest`` (:func:`build_images`), and ``self.project``
        carries a per-run random token (:meth:`Run.__init__`), so those tags differ
        on every run and a re-run can never reuse a prior build. Nothing in the
        existing lifecycle removes them: ``down -v`` tears down containers and
        volumes only (UR-135 pins ``teardown`` to exactly that one compose call),
        and the postflight ``Snapshot`` tracks containers and volumes — it has no
        image axis, so the leak is not even reported. Removal therefore lives here,
        on the bare-engine surface (``image rm``), not inside ``teardown``.

        The names come from the same :func:`build_images` derivation ``up`` and the
        pre-build use, so a name is neither removed that compose did not build
        under nor missed by a second list drifting. Only names carrying THIS run's
        project prefix are touched: a service that declares its own ``image:``
        (grafana, host-local and shared with production) is not prefixed, so it is
        left exactly as skip-if-present leaves it.

        This runs whether or not the boot started. A pre-build that dies after
        building some layers leaves those layers behind with ``started`` still
        False, and the ``if run.started`` gate that guards ``teardown`` would skip
        an image cleanup placed behind it — which is why the caller calls this
        outside that gate.
        """
        if not self.prod_shape or not self.compose_file.exists():
            return EXIT_OK
        boot = json.loads(self.compose_file.read_text(encoding="utf-8"))
        prefix = f"{self.project}-"
        candidates = sorted(
            image
            for image in build_images(boot, project=self.project).values()
            if image.startswith(prefix)
        )
        removed: list[str] = []
        leaked: list[str] = []
        stalled: list[str] = []
        for image in candidates:
            present = self._run([self.engine, "image", "inspect", image], check=False, echo=False)
            if _stalled(present):
                # BEFORE the nonzero check, because a stall IS nonzero: `_run` turns
                # its own deadline into rc=124, so without this fence a dead or
                # wedged engine answers every name with "not present" and the run
                # reports a spotless cleanup it never performed. Unknown is not
                # absent, and `image rm` on an unknown name is a second guess on
                # top of the first one — so the name is only recorded, never removed.
                stalled.append(image)
                _log(f"FAIL prod-shape image state unknown, the engine timed out: {image}")
                continue
            if present.returncode != 0:
                # Not every nonzero answer means "not in the engine": a DOWN daemon answers
                # with the exit code absence uses on that same engine (rc=1 docker, rc=125
                # podman -- measured), so trusting the rc alone lets a run whose engine never
                # answered report itself spotless. Absence is claimed only when the daemon
                # said so in words; everything else is unknown, recorded, and NOT removed.
                #
                # The `continue` is OUTSIDE the inner test on purpose, so no nonzero answer
                # can reach `image rm` on either reading -- the battery found that nesting it
                # inside the unknown branch makes the two `continue`s redundant next to each
                # other, which is a mutation an editor could introduce by accident.
                if not _image_absent(present):
                    stalled.append(image)
                    said = "\n".join(
                        f"  | {line}" for line in (present.stderr or "").splitlines()[:3]
                    )
                    _log(
                        f"FAIL prod-shape image state unknown: {image} "
                        f"(exit {_exit_word(present)})" + (f"\n{said}" if said else "")
                    )
                continue  # absent (the engine said so) or unknown -- neither is removed here
            gone = self._run([self.engine, "image", "rm", image], check=False, echo=False)
            if gone.returncode == 0:
                removed.append(image)
            else:
                # Includes a stalled `image rm`: rc=124 is nonzero, and "might still
                # be there" is the correct reading of a removal we could not confirm.
                leaked.append(image)
        self.summary["images_removed"] = removed
        # The leak gets its own key, not just a log line: `run_check` prints the
        # summary whole for the operator to paste, and every other failure surface
        # (`results.postflight`, `results.teardown`, `results.engine_socket`) reaches
        # it. Names left in the engine would otherwise be visible only in the log.
        self.summary["images_leaked"] = leaked
        # Its own key rather than folded into `images_leaked`, because the two need
        # different repairs: a leak is an image to delete, a stall is an engine to
        # fix. Pasted into the same list, an operator would chase images that may
        # not exist while the wedged engine that answered 124 goes unmentioned.
        self.summary["images_stalled"] = stalled
        for image in leaked:
            _log(f"FAIL prod-shape image still in the engine, not removed: {image}")
        return EXIT_FAILED if (leaked or stalled) else EXIT_OK

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
        # The run's id under a prefix of its own: the project alone is 31
        # characters, so `<project>-vlm` broke the runner's name policy.
        self.name = VLM_NAME_PREFIX + run.project.removeprefix(PROJECT_PREFIX)
        run.summary["vlm_name"] = self.name
        self.started = False
        self.url: str | None = None
        self.dial_url: str | None = None
        self.host_port: int | None = None
        self.served_model: str | None = None

    def _cli(
        self, *args: str, check: bool = True, timeout: float | None = 300
    ) -> subprocess.CompletedProcess[str]:
        # The caller's whole environment: agent-gpu reaches its runner with it.
        return self.run._run(["agent-gpu", *args], check=check, timeout=timeout, env=os.environ)

    def _record(self, name: str, text: str) -> str:
        try:
            (self.run.artifacts / name).write_text(text, encoding="utf-8")
        except OSError as error:
            _log(f"recording {name} failed ({error}); the summary keeps it")
        return text

    def _try(self, *args: str, timeout: float = 300) -> subprocess.CompletedProcess[str] | None:
        """An agent-gpu call that must not stop the teardown; None if it did
        not complete."""
        try:
            return self._cli(*args, check=False, timeout=timeout)
        except Exception as error:
            _log(f"agent-gpu {args[0]} did not complete ({type(error).__name__}: {error})")
            return None

    def _reading(self, label: str) -> dict[str, str]:
        """``agent-gpu ps`` and ``status``, the runner's own view of the VLM
        and its VRAM, into the summary and artifacts/."""
        reading = {}
        for verb in ("ps", "status"):
            result = self._try(verb)
            text = result.stdout if result is not None else f"agent-gpu {verb} did not complete"
            reading[verb] = self._record(f"agent-gpu-{verb}-{label}.txt", text)
        self.run.summary.setdefault("vram", {"declared_gib": VLM_VRAM_GIB})[label] = reading
        return reading

    def vlm_tree(self) -> str:
        """``ai/vlm/``'s tree hash, which tags its image; uncommitted changes
        there would build an image the tag does not name."""
        git = ["git", "-C", str(REPO_ROOT)]
        dirty = self.run._run([*git, "status", "--porcelain", "--", "ai/vlm"], env=os.environ)
        if dirty.stdout.strip():
            raise Refused(
                [
                    "ai/vlm/ has uncommitted changes, which its image tag would not name: "
                    + "; ".join(dirty.stdout.strip().splitlines())
                ]
            )
        return self.run._run(
            [*git, "rev-parse", "--short", "HEAD:ai/vlm"], env=os.environ
        ).stdout.strip()

    def prod_environment(self) -> Sequence[str] | Mapping[str, Any]:
        """ai-vlm's environment as docker-compose.prod.yml writes it, raw
        (never interpolated, never started): the `${VAR:-default}` tokens
        `vlm_run_environment` needs, verbatim.

        Read from the file with ``yaml.safe_load``, NOT from
        ``compose config --no-interpolate``. [r162] (owner ruling 186) made the
        top-level ``include:`` path itself interpolated
        (``docker-compose.engine-${ORCHESTRATOR_ENABLED:-true}.yml``), and
        ``--no-interpolate`` does not expand an include path — it tries to open
        the literal ``engine-${…}.yml`` and exits 1, which would crash the
        real-tier VLM start (``start`` → this method → ``json.loads``). Measured:
        this YAML read yields the byte-identical 17-entry list on the current
        prod.yml, and it is the same read the unit test at
        ``backend/tests/unit/scripts/test_feature_check.py`` uses, so runtime and
        test now consult one source. Nothing about ai-vlm's ``environment`` is
        produced by compose that this read misses.

        The ``import yaml`` is deliberately function-local: feature-check.sh
        execs this file under bare ``python3``, and the golden Playwright
        container's python3 has no pyyaml — a module-level import made every
        subcommand (``drop`` included) die at import time there. Here is the
        only reader; only ``start`` pays for it.
        """
        try:
            import yaml
        except ModuleNotFoundError as error:
            raise HarnessError(
                "this path reads docker-compose.prod.yml with pyyaml, which bare "
                "python3 does not carry (pyyaml is a dev-only dependency, "
                "pyproject.toml). Run the harness under a python that has it: "
                "`uv run scripts/feature_check.py …`, or `export "
                "PATH=<checkout>/.venv/bin:$PATH` first. The wrapper's bare "
                "python3 stays import-clean on purpose."
            ) from error

        raw = yaml.safe_load(PROD_STACK.read_text(encoding="utf-8"))
        return (raw.get("services") or {}).get("ai-vlm", {}).get("environment") or []

    def prepare(self) -> None:
        """Steps 1-2: the weights against the pin, the budget, the image."""
        if not AGENT_GPU_NAME.fullmatch(self.name):
            raise Refused(
                [
                    f"the VLM's name {self.name} breaks agent-gpu's name policy "
                    f"({AGENT_GPU_NAME.pattern})"
                ]
            )
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
        # `ai-vlm:<tree>` or `ai-vlm  <tree>`, under any registry prefix.
        if re.search(rf"(?<![\w.-])ai-vlm(?::|[ \t]+){re.escape(tree)}(?![\w.-])", images):
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
        self.dial_url = vlm_dial_url(self.url, self.host_port)
        self.run.summary["vlm_dial_url"] = self.dial_url
        _log(f"vlm: {self.name} serves at {self.url} (this run dials {self.dial_url})")

    def wait_ready(self, timeout: float = 900) -> None:
        """Step 3: /health answers 200, and /props' model_path is the pin.

        Dialed at ``dial_url``, and with no ``origin`` when that is the loopback
        form: ``_http``'s ``origin`` branch builds an opener that HONOURS
        ``HTTP_PROXY`` — correct for the alias, which a sandbox reaches through
        its proxy — while a loopback URL must go direct, which is what its
        ``127.0.0.1`` branch (a proxy-free opener) already does. A host login
        with a proxy set for internet access must not have its VLM probe sent
        through it.
        """
        url = str(self.dial_url if self.dial_url is not None else self.url)
        loopback = urllib.parse.urlsplit(url).hostname == "127.0.0.1"
        origin = None if loopback else url
        deadline = time.monotonic() + timeout
        while True:
            status, _ = _http("GET", f"{url}/health", timeout=10, origin=origin)
            if status == 200 or time.monotonic() >= deadline:
                break
            time.sleep(5)
        if status != 200:
            raise HarnessError(f"the VLM at {url} did not answer /health with 200 ({status})")
        status, props = _http("GET", f"{url}/props", timeout=10, origin=origin)
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
        # The teardown proves the VLM gone by its name's absence from ps,
        # which proves nothing unless ps lists it by that name now.
        if self.name not in self._reading("serving")["ps"]:
            raise HarnessError(
                f"agent-gpu ps does not list {self.name} while it serves, so the "
                "teardown could not prove it gone; see agent-gpu-ps-serving.txt"
            )
        _log(f"vlm: ready, build {props.get('build_info')}, model {model_path}")

    def teardown(self) -> list[str]:
        """Step 6: stop and remove the VLM; ``agent-gpu ps`` must then list
        none of the run's containers. No step here can skip the removal."""
        self._reading("at_end")
        self._try("stop", self.name, timeout=600)
        self._try("rm", self.name, timeout=600)
        after = self._try("ps")
        listing = "" if after is None else after.stdout + after.stderr
        self.run.summary.setdefault("agent_gpu", {})["ps_after"] = self._record(
            "agent-gpu-ps-after.txt", listing
        )
        problems = []
        if after is None or after.returncode != 0:
            problems.append(
                f"agent-gpu ps did not answer, so whether {self.name} is gone is unknown; "
                f"agent-gpu rm {self.name}"
            )
        elif self.name in after.stdout:
            # Any listing that contains the name, however the runner decorates it.
            problems.append(
                f"agent-gpu ps still lists {self.name}; remove it with agent-gpu rm {self.name}"
            )
        self.run.summary["results"]["agent_gpu"] = problems or "ok"
        _log(
            "agent-gpu: "
            + ("ok, agent-gpu ps lists none of this run's containers" if not problems else "LEFT")
        )
        return problems


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect could lead past the allowlist; the harness follows none."""

    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


# No proxies: urllib honours HTTP_PROXY, and a NO_PROXY without 127.0.0.1
# would send the harness's calls to a proxy instead of the run's own ports.
_LOOPBACK = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)


def _http(
    method: str,
    url: str,
    payload: Any = None,
    timeout: float = 15,
    *,
    origin: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> tuple[int, Any]:
    """(status, JSON body or text); status 0 when nothing answered.

    Only the run's own published ports, which all bind 127.0.0.1, and on
    ``--real`` the one ``origin`` that ``agent-gpu run`` printed. That one is
    the host's loopback, which a sandbox reaches through its proxy, so the
    caller's proxy settings apply to it.
    """
    parts = urllib.parse.urlsplit(url)
    if origin is not None and f"{parts.scheme}://{parts.netloc}" == origin:
        opener = urllib.request.build_opener(_NoRedirect)
    elif parts.hostname == "127.0.0.1":
        opener = _LOOPBACK
    else:
        also = f" and {origin}" if origin else ""
        raise HarnessError(f"the harness talks only to its own 127.0.0.1 ports{also}, not {url}")
    data = json.dumps(payload).encode() if payload is not None else None
    req_headers = {"Content-Type": "application/json", **(dict(headers) if headers else {})}
    request = urllib.request.Request(  # noqa: S310 (127.0.0.1 or the VLM, checked above)
        url, data=data, method=method, headers=req_headers
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


class Interrupted(Exception):
    """A signal asked the run to stop; teardown and the summary still follow."""

    def __init__(self, signum: int) -> None:
        self.signal = signal.Signals(signum).name
        super().__init__(f"interrupted by {self.signal}")


# What a caller sends to stop a run: an operator's timed-out tool call, a
# closed terminal. Python's default for both ends the process with no
# `finally`, which would leave the test deployment and the VLM up.
STOP_SIGNALS = (signal.SIGTERM, signal.SIGHUP)


def _interrupt(signum: int, _frame: Any) -> None:
    raise Interrupted(signum)


def run_check(args: argparse.Namespace, *, mode: str) -> int:
    seeded = bool(getattr(args, "seeded", False))
    run = Run(
        engine=args.engine,
        root=args.root,
        image_tag=args.image_tag,
        mode=mode,
        prod_shape=args.prod_shape,
        seeded=seeded,
        shard=getattr(args, "shard", None),
        golden_specs=getattr(args, "golden_spec", None),
        pytest_k=getattr(args, "pytest_k", None),
        playwright_grep=getattr(args, "playwright_grep", None),
    )
    before = run.prepare()
    vlm = AgentGpu(run) if mode == "real" else None
    status = EXIT_OK
    # A signal the caller ignores stays ignored (nohup's SIGHUP).
    handlers = {
        signum: signal.signal(signum, _interrupt)
        for signum in STOP_SIGNALS
        if signal.getsignal(signum) is not signal.SIG_IGN
    }
    handlers[signal.SIGINT] = signal.getsignal(signal.SIGINT)
    try:
        if vlm is not None:
            vlm.prepare()
            vlm.start()
            vlm.wait_ready()
            # The first run builds the image for hours: judge the machine as
            # it is when the test deployment starts.
            before = run.take_snapshot()
        run.render(before, vlm)
        run.up(vlm)
        run.register_admin()
        run.seed_cameras()
        if getattr(run, "seeded", False):
            run.seed_debug_fixtures()
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
    except (Interrupted, KeyboardInterrupt) as stop:
        name = stop.signal if isinstance(stop, Interrupted) else "SIGINT"
        _log(f"FAIL interrupted by {name}; tearing down")
        run.summary["interrupted"] = name
        status = EXIT_FAILED
    except Exception as error:
        _log(f"FAIL {type(error).__name__}: {error}")
        status = EXIT_FAILED
    finally:
        # Teardown runs to its end: a second signal is ignored until it has
        # (SIGKILL is not), and the commands it starts inherit that.
        for signum in handlers:
            signal.signal(signum, signal.SIG_IGN)
        try:
            if run.started:
                status = max(status, _finish(run, before))
            # Image cleanup deliberately OUTSIDE the `run.started` gate, like the
            # VLM's own `started` gate above: a prod-shape run that dies in the
            # pre-build never sets `started` (that flips inside `up`), yet a partial
            # build has already left images in the engine. Gating this on
            # `run.started` would skip exactly the failure path that leaks.
            status = max(status, _cleanup_images(run))
            if vlm is not None and vlm.started:
                status = max(status, _finish_vlm(vlm))
            run.summary["exit"] = status
            run._write("summary.json", run.summary)
            # Printed whole, for the operator to paste (operator.md, "Posting results").
            print(json.dumps(run.summary, indent=2), flush=True)
            _log(f"summary: {run.artifacts / 'summary.json'} (exit {status})")
        finally:
            for signum, handler in handlers.items():
                signal.signal(signum, handler)
    return status


def _finish(run: Run, before: Snapshot) -> int:
    """Collect, tear down and run the postflight; nothing here may stop the
    teardown, and a postflight that cannot run counts as a change."""
    try:
        run.collect()
    except Exception as error:
        _log(f"collecting artifacts failed ({type(error).__name__}: {error}); tearing down")
    try:
        changed, left = run.teardown(before)
    except Exception as error:
        _log(f"URGENT teardown or postflight did not complete ({type(error).__name__}: {error})")
        changed, left = [], []
        status = EXIT_CHANGED
    else:
        for problem in changed:
            _log(f"URGENT {problem}")
        for problem in left:
            _log(f"FAIL {problem}")
        status = EXIT_CHANGED if changed else (EXIT_FAILED if left else EXIT_OK)
    # [O2.5 venue fixes, ruling 287] The relay host half is joined AFTER the
    # deployment is down -- its thread is only needed while the sidecar
    # accepts -- and it runs on every path that reached `up()` (`started`), so
    # no armed half survives the run. `join` never raises: it is the last
    # cleanup and it reports its own problem into the summary.
    if run.relay is not None:
        run.relay.join()
        run.relay = None
    return status


def _cleanup_images(run: Run) -> int:
    """Remove a prod-shape run's images after the deployment is gone, also after a
    failure. A cleanup that cannot run is reported, not swallowed: the images are
    the whole point (they are per-run and no later run reuses them)."""
    try:
        return run.cleanup_images()
    except Exception as error:
        _log(f"URGENT prod-shape image cleanup did not complete ({type(error).__name__}: {error})")
        return EXIT_FAILED


def _finish_vlm(vlm: AgentGpu) -> int:
    """Remove the run's VLM after the test deployment is down, also after a
    failure (operator.md step 6)."""
    try:
        left = vlm.teardown()
    except Exception as error:
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
        "--prod-shape",
        action="store_true",
        help="bring up the PRODUCTION compose shape (O2.5, ruling 144/162): "
        "docker-compose.prod.yml + the prod-shape override on Podman, instead of the CI "
        "stack. With --real it is the sandbox run; without --real it is the maui run with "
        "the fake VLM (ruling 256's venue split). Refused with --fake or --seeded.",
    )
    parser.add_argument(
        "--seeded",
        action="store_true",
        help="with --fake or --real (ruling 235), boot the ruling-127/187 seeded stack "
        "(DEBUG=true, "
        "request recorder enabled, breaker/threshold fault seed, orphan file fixture) "
        "and run the golden-seeded Playwright project.",
    )
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
    parser.add_argument(
        "--shard",
        type=str,
        default=os.environ.get("FEATURE_CHECK_SHARD", ""),
        help="[r264] run only shard I of N of the golden Playwright project, as `--shard I/N` "
        "(default: $FEATURE_CHECK_SHARD or unset -- the whole suite, unsharded). CI-only: "
        "every shard boots its own stack under its own compose project; the real tier and "
        "the maui run keep the whole suite on one stack (ruling 264 item 5).",
    )
    parser.add_argument(
        "--golden-spec",
        action="append",
        dest="golden_spec",
        default=[],
        help="[r287] run only these golden Playwright specs (repeatable), as paths under "
        "frontend/tests/golden (e.g. `tests/golden/dashboard/gpu-stats.spec.ts`). "
        "Prod-shape-only: the limit exists so the maui run can witness named specs "
        "(F-176/F-178/F-182); on any other shape it refuses at parse time.",
    )
    parser.add_argument(
        "--pytest-k",
        type=str,
        default=None,
        help="run only backend golden pytest specs matching this -k expression (--real only). "
        "When given without --playwright-grep, skips the Playwright leg.",
    )
    parser.add_argument(
        "--playwright-grep",
        type=str,
        default=None,
        help="run only Playwright golden specs matching this --grep pattern (--real only). "
        "When given without --pytest-k, skips the backend leg.",
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
    if args.seeded and args.prod_shape:
        # Ruling 235 keeps this refusal explicit rather than inheriting it from the old
        # `--seeded needs --fake` line, which is what actually blocked this combination
        # before. The prod shape renders docker-compose.prod.yml; the seeded shape sets
        # DEBUG=true and mounts the request recorder, and production never runs either.
        parser.error("--seeded cannot combine with --prod-shape (production never runs DEBUG=true)")
    if args.seeded and not (args.fake or args.real):
        # Ruling 235: the seeded stack is a BOOT SHAPE, not a third mode. Nothing in it
        # depends on the fake VLM -- the boot overrides (see as_test_deployment), the planted
        # fixtures and the golden-seeded Playwright project all key off `seeded` alone -- so
        # `--real --seeded` is the route the ~11 seeded-only inventory rows take to **works**.
        # What stays refused is `--seeded --prod-shape`, ruled above: production never runs
        # DEBUG=true. `--fake --seeded` is byte-for-byte the command the CI leg runs.
        parser.error("--seeded needs --fake or --real (it is a boot shape, not a mode)")

    if args.fake and args.prod_shape:
        # "The CI stack in the shape of prod" has no referent: --fake renders
        # docker-compose.ci.yml and the prod shape renders docker-compose.prod.yml,
        # and no run can claim both. Refused at parse time, before any engine call,
        # so a reader of a run record can never believe prod was exercised when the
        # CI stack ran. (Ruling 256 keeps THIS refusal; it lifts only the
        # needs---real one, for the maui run's bare --prod-shape below.)
        parser.error("--fake is the CI stack: it cannot also take --prod-shape")
    if not (args.fake or args.real or args.prod_shape):
        # The old generic refusal (`choose --fake or --real`) was deleted in the
        # ruling-256 venue split so the maui run's bare `--prod-shape` could fall
        # through to the fake tier; the deletion went further than the widening
        # needed and a bare invocation now silently boots the CI fake tier
        # (ruling 262's defect, found by the owner's audit). Restored, narrowed to
        # the shape it must keep open: a bare call with no mode and no shape has no
        # referent, while `--prod-shape` alone stays the maui run's form.
        parser.error("choose --fake or --real (or --prod-shape for the maui run)")
    # [r264] The shard flag is the CI fake tier's own option (it exists to split
    # that tier's golden leg across stacks). A real-tier or prod-shape run that
    # took a shard would witness the real tier on a partial suite while its run
    # record said `shard` -- exactly the silent-coverage-hole shape ruling 114
    # exists for -- so it refuses at parse time, like every other shape
    # mismatch above. `args.shard` is normalized here, once: a tuple when a
    # shard was named, None when not (the empty-string env default must not
    # reach Run -- its summary key check is `is not None`).
    if args.shard:
        match = re.fullmatch(r"(\d+)/(\d+)", args.shard.strip())
        if not match:
            parser.error(
                f"--shard takes `I/N` with 1 <= I <= N (e.g. `--shard 2/3`), got {args.shard!r}"
            )
        shard_i, shard_n = int(match[1]), int(match[2])
        if not (1 <= shard_i <= shard_n):
            parser.error(
                f"--shard takes `I/N` with 1 <= I <= N (e.g. `--shard 2/3`), got {args.shard!r}"
            )
        args.shard = (shard_i, shard_n)
    else:
        args.shard = None
    if args.shard and (args.real or args.prod_shape):
        parser.error(
            "--shard is the CI fake tier's option (--fake only): the real tier and the "
            "prod-shape run keep the whole suite on one stack (ruling 264 item 5)"
        )
    # [r287] `--golden-spec` is the prod-shape leg's own option, the mirror of
    # the shard clause above: the named-spec limit exists so the maui run can
    # witness its named specs (F-176/F-178/F-182) without failing the rest of
    # the suite it did not ask to run. On any other shape a partial golden leg
    # is the silent-coverage-hole shape ruling 114 exists for, so it refuses at
    # parse time, like every other shape mismatch. The values are normalized
    # once, here: a tuple when specs were named, None when not (the list
    # default must not reach Run -- its summary-key check is `is not None`).
    if args.golden_spec:
        if not args.prod_shape:
            parser.error(
                "--golden-spec is the prod-shape run's option (--prod-shape only): the "
                "fake and real tiers keep the whole golden suite (ruling 287)"
            )
        normalized = []
        for spec in args.golden_spec:
            if not spec or spec != spec.strip():
                parser.error(f"--golden-spec takes a repo path, got {spec!r}")
            candidate = Path(spec)
            if candidate.is_absolute() or ".." in candidate.parts:
                parser.error(f"--golden-spec takes a repo path under tests/golden, got {spec!r}")
            # The option names SPECS: a file under tests/golden whose name ends
            # .spec.ts. The prefix half is load-bearing — a name check alone
            # would pass tests/e2e/*.spec.ts, and a suffix check alone would
            # pass tests/golden/harness.ts (and Path.suffix is '.ts' anyway,
            # not '.spec.ts'), and neither can be collected by the
            # --project=golden leg, so an accepted either would write a run
            # record naming files the leg could not run.
            if candidate.parts[:2] != ("tests", "golden") or not candidate.name.endswith(
                ".spec.ts"
            ):
                parser.error(
                    f"--golden-spec takes a path to a spec under tests/golden, got {spec!r}"
                )
            # The leg's own cwd is FRONTEND (golden_container_command's -w), so
            # the spelling the runner will resolve is frontend-relative, and
            # that is the spelling this check validates.
            if not (FRONTEND / candidate).is_file():
                parser.error(f"--golden-spec names a file the repo does not carry: {spec!r}")
            normalized.append(spec)
        args.golden_spec = tuple(normalized)
    else:
        args.golden_spec = None

    if args.pytest_k is not None:
        if not args.real or args.prod_shape or args.seeded:
            parser.error(
                "--pytest-k is the real-tier witness selector (--real only, without "
                "--prod-shape or --seeded)"
            )
        if not args.pytest_k.strip():
            parser.error("--pytest-k takes a non-empty pytest -k expression")
        args.pytest_k = args.pytest_k.strip()
    # [O2.5 venue fixes, ruling 287] The relay knob is the real-gateway venue's
    # opt-in, so it refuses at parse time on every other shape -- --fake, and
    # plain --real without --prod-shape (the CI-tier real run, whose stack
    # reaches agent-gpu's alias directly). On --prod-shape without --real (the
    # maui run) the render-time gate in the transform names the same venue:
    # render() dispatches away before the transform on those other shapes, so a
    # knob that is dormant there would silently witness the wrong deployment --
    # the same shape mismatch the shard and golden-spec gates refuse above.
    if os.environ.get("PROD_SHAPE_VLM_RELAY") == "1" and not (args.real and args.prod_shape):
        parser.error(
            "PROD_SHAPE_VLM_RELAY requires --real --prod-shape (the real-gateway venue): "
            "the two-hop relay needs the agent-gpu lease to relay to"
        )
    if args.playwright_grep is not None:
        if not args.real or args.prod_shape:
            parser.error(
                "--playwright-grep is the real-tier witness selector (--real only, "
                "without --prod-shape)"
            )
        if not args.playwright_grep.strip():
            parser.error("--playwright-grep takes a non-empty Playwright --grep pattern")
        args.playwright_grep = args.playwright_grep.strip()

    if args.real:
        unavailable = real_unavailable(os.environ)
        if unavailable:
            _log(unavailable)
            return EXIT_UNAVAILABLE
        return run_check(args, mode="real")
    # Ruling 256 item 2: the venue split gives the prod shape a second caller, the maui
    # run -- `feature_check.py --prod-shape` with the fake VLM, from a host login. The
    # mode handed down is "fake" (the fake VLM serves the engine wire the CI tier's fake
    # serves, and the run record's shape string is "fake-prod-shape"); with no AgentGpu
    # on that path, render_prod_shape() splices the fake VLM in place of ai-vlm's body
    # and keeps production CDI for ai-gateway/dcgm-exporter/backend -- the maui venue
    # keeps its GPU consumers, per ruling 256 item 2. Plain --fake is the CI tier,
    # unchanged.
    return run_check(args, mode="fake")


if __name__ == "__main__":
    sys.exit(main())
