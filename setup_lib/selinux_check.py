"""Can the backend (container_t) inotify-WATCH the camera root under SELinux?

A5500 box, 2026-09-28: SELinux enforcing, /export/foscam labelled usr_t,
mounted without :z - container_t may READ it (uploads were listable) but the
watch was denied (`avc: denied { watch watch_reads }`), and the file watcher,
which watchdog never told, went blind while logging success. Only
container_file_t (or a :z/:Z mount, which relabels the source to it) lets the
file watcher watch.

One check, two callers: ``setup.py deploy`` runs it as a preflight, and
``scripts/a5500_precheck.py`` renders it as its ``selinux_camera_root`` row.

STDLIB ONLY and self-contained: the precheck loads this file BY PATH, so it
runs without the venv and never executes ``setup_lib/__init__.py``. Keep it
that way (pinned by test_selinux_check.py::TestImportLight).
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import NamedTuple

PASS = "PASS"  # noqa: S105 - a verdict, not a password
WARN = "WARN"

SELINUX_ENFORCE_FILE = Path("/sys/fs/selinux/enforce")
CONTAINER_FILE_T = "container_file_t"
DEFAULT_CAMERA_ROOT = "/export/foscam"
# ``<host>:/cameras[:opts]`` - the target must be exactly /cameras.
CAMERA_MOUNT_RE = re.compile(r":/cameras(?::(?P<opts>[A-Za-z,]+))?$")


class CameraRootVerdict(NamedTuple):
    verdict: str  # PASS | WARN
    detail: str


def camera_root(env: Mapping[str, str]) -> str:
    """The host camera root compose mounts: FOSCAM_BASE_PATH, else its default."""
    return env.get("FOSCAM_BASE_PATH", "").strip("'\"") or DEFAULT_CAMERA_ROOT


def read_selinux_enforcing(enforce_file: Path = SELINUX_ENFORCE_FILE) -> bool | None:
    """True = enforcing, False = permissive, None = no SELinux on this host."""
    try:
        return enforce_file.read_text(encoding="utf-8").strip() == "1"
    except OSError:
        return None


def read_selinux_label(path: str) -> str | None:
    """The path's SELinux context (``user:role:type:level``), or None if unreadable."""
    try:
        raw = os.getxattr(path, "security.selinux")
    except OSError, AttributeError:  # missing path / no xattr / no os.getxattr (macOS)
        return None
    return raw.rstrip(b"\x00").decode("utf-8", errors="replace")


def _service_block(text: str, service: str) -> list[str]:
    """Raw lines of ``service``'s block (a service key is two spaces + name + colon)."""
    block: list[str] = []
    in_block = False
    for line in text.splitlines():
        if line.startswith("  ") and not line.startswith("   ") and line.rstrip().endswith(":"):
            in_block = line.strip().rstrip(":") == service
            continue
        if in_block:
            if line and not line.startswith("    "):
                in_block = False  # dedent back to a sibling/top-level key
            else:
                block.append(line)
    return block


def service_camera_mounts(
    compose_paths: Sequence[Path], service: str = "backend"
) -> dict[str, list[str]]:
    """{compose file name: ``service``'s raw ``/cameras`` mounts in it}.

    Every file gets a key (an empty list = no such mount there), so a verdict
    can name the files it read. Block-scoped to ``service``: foscam-init
    mounts the same root, but it never watches anything. A line scan, not a
    YAML parse - this module stays stdlib-only.
    """
    out: dict[str, list[str]] = {}
    for path in compose_paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        mounts = out.setdefault(path.name, [])
        for line in _service_block(text, service):
            s = line.strip()
            if not s.startswith("- "):
                continue
            mount = s[2:].strip().strip("'\"")
            if CAMERA_MOUNT_RE.search(mount):
                mounts.append(mount)
    return out


def check_camera_root(
    root: str,
    camera_mounts: Mapping[str, Sequence[str]],
    *,
    selinux_enforcing: Callable[[], bool | None] = read_selinux_enforcing,
    selinux_label: Callable[[str], str | None] = read_selinux_label,
) -> CameraRootVerdict:
    """PASS/WARN for one camera root and the backend's /cameras mounts.

    ``camera_mounts`` is ``{compose file name: backend /cameras mount strings}``
    (see ``service_camera_mounts``). The two readers are the only HOST state
    read; they are injectable so tests never depend on the machine. Never
    changes anything: the fix is printed, not applied.
    """
    enforcing = selinux_enforcing()
    if enforcing is None:
        return CameraRootVerdict(
            PASS,
            "SELinux not present on this host (no /sys/fs/selinux/enforce) - no "
            "label can deny the file watcher's inotify watch",
        )
    if not enforcing:
        return CameraRootVerdict(
            PASS,
            "SELinux is not enforcing (enforce=0) - a denied watch is only "
            "logged, so the file watcher can watch the camera root",
        )
    label = selinux_label(root)
    label_type = label.split(":")[2] if label and label.count(":") >= 3 else label
    if label_type == CONTAINER_FILE_T:
        return CameraRootVerdict(
            PASS,
            f"camera root {root} is labeled {CONTAINER_FILE_T} - the backend "
            "(container_t) may inotify-watch it",
        )
    relabelled: list[str] = []
    bare: list[str] = []
    for fname, mounts in camera_mounts.items():
        for mount in mounts:
            m = CAMERA_MOUNT_RE.search(mount)
            opts = set(((m.group("opts") if m else None) or "").split(","))
            (relabelled if opts & {"z", "Z"} else bare).append(f"{fname}: {mount}")
    if relabelled and not bare:
        return CameraRootVerdict(
            PASS,
            "the backend /cameras mount carries :z/:Z ("
            + "; ".join(relabelled)
            + f") - podman relabels {root} to {CONTAINER_FILE_T} when the "
            "backend starts",
        )
    where = (
        "; ".join(bare)
        if bare
        else "no backend /cameras mount found in " + ", ".join(camera_mounts)
    )
    return CameraRootVerdict(
        WARN,
        f"SELinux is enforcing and camera root {root} is labeled "
        f"{label or 'UNREADABLE (missing, or no security.selinux xattr)'}, not "
        f"{CONTAINER_FILE_T}, and the backend /cameras mount does not relabel it "
        f"({where}): the backend (container_t) can READ uploads but its inotify "
        "WATCH is denied (host audit log: `avc: denied { watch }` on /cameras), so "
        "the file watcher falls back to polling. Fix: add :z to that mount "
        "(docker-compose.prod.yml carries it), or relabel the root once: sudo "
        f"semanage fcontext -a -t {CONTAINER_FILE_T} '{root}(/.*)?' && sudo "
        f"restorecon -R {root}",
    )
