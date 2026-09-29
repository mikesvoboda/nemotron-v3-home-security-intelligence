"""`doctor`: check that this machine can run a batch, read-only (owner request, 2026-09-28).

Six checks, in order: OpenCV imports; the corpus mount exists and is writable; the guard's
status file exists, parses and is fresh; the fresh status says the flagship is healthy; the
renderer answers; any existing corpus version was sampled from the committed taxonomy. Every
check runs, so one run names every gap. Each prints one line, `ok   <what>` or
`FAIL <what>: <fix>`, where the fix is one sentence the agent can pass to the owner; an
unhealthy or busy flagship prints a `WAIT` line instead, which does not change the exit code.

Nothing here writes to the corpus, except one temporary probe file the corpus mount check
creates and removes at once, named like the store's own temporary files so the prune rule and
`check` already ignore it.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from synthbench.commands.common import EXIT_OK, AskOwner, CorpusError, Parser, read, taxonomy
from synthbench.contract.corpus import CorpusManifest
from synthbench.contract.store import CorpusStore
from synthbench.generate.render import RendererUnreachable, comfy_url
from synthbench.status import (
    FlagshipStatus,
    FlagshipUnknown,
    flagship_file,
    fresh_flagship,
    status_dir,
)
from synthbench.taxonomy.model import taxonomy_sha256

_OPENCV_FIX = (
    "the sandbox image lacks OpenCV's libraries: the owner runs sbx exec <sandbox> sudo "
    "apt-get install -y libxcb1 libgl1 libglib2.0-0"
)
_CORPUS_MOUNT_FIX = (
    "mount /synthbench/corpus read-write into the sandbox (never a path under /export)"
)
_GUARD_DIR_FIX = "mount /synthbench/status read-only into the sandbox"
_GUARD_DOWN_FIX = (
    "the guard is not running: the owner runs systemctl --user enable --now "
    "synthbench-guard.service"
)
_WAIT_LINE = "WAIT flagship unhealthy or busy: render waits for it"
_RENDERER_FIX = (
    "the renderer is not running: the owner starts synthbench-renderer.service "
    '(docs/synthbench/operator-runbook.md, "The renderer")'
)
_NO_CORPUS_VERSION = "ok   no corpus version yet: the first sample creates it and pins the taxonomy"


def _import_cv2() -> None:
    import cv2  # noqa: F401  # only whether this succeeds matters here


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Deps:
    """What doctor reaches outside the corpus; tests pass fakes."""

    get: Callable[..., httpx.Response] = httpx.get
    now: Callable[[], datetime] = _utc_now
    import_cv2: Callable[[], None] = _import_cv2


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "doctor",
        help="check that this machine can run a batch (read-only)",
        allow_abbrev=False,
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    del args  # no options
    return execute(env, Deps())


def execute(env: Mapping[str, str], deps: Deps) -> int:
    tax = taxonomy()
    store = CorpusStore.from_env(tax.version, env)
    problems = 0

    ok, line = _opencv(deps)
    sys.stdout.write(line + "\n")
    problems += 0 if ok else 1

    ok, line = _corpus_mount(store)
    sys.stdout.write(line + "\n")
    problems += 0 if ok else 1

    status, line = _guard_status(env, deps)
    sys.stdout.write(line + "\n")
    if status is None:
        problems += 1
    else:
        sys.stdout.write(_flagship_health(status) + "\n")

    ok, line = _renderer(env, deps)
    sys.stdout.write(line + "\n")
    problems += 0 if ok else 1

    ok, line = _corpus_version(store)
    sys.stdout.write(line + "\n")
    problems += 0 if ok else 1

    if problems:
        raise AskOwner(f"doctor: {problems} problem(s); tell the owner the FAIL lines and wait")
    sys.stdout.write("doctor: ready for every command\n")
    return EXIT_OK


def _opencv(deps: Deps) -> tuple[bool, str]:
    try:
        deps.import_cv2()
    except ImportError:
        return False, f"FAIL opencv: {_OPENCV_FIX}"
    return True, "ok   opencv"


def _corpus_mount(store: CorpusStore) -> tuple[bool, str]:
    if not store.root.is_dir():
        return False, f"FAIL corpus mount: {_CORPUS_MOUNT_FIX}"
    probe = store.root / f".doctor.{uuid.uuid4().hex}.tmp"
    try:
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False, f"FAIL corpus mount: {_CORPUS_MOUNT_FIX}"
    return True, "ok   corpus mount"


def _guard_status(env: Mapping[str, str], deps: Deps) -> tuple[FlagshipStatus | None, str]:
    if not status_dir(env).is_dir():
        return None, f"FAIL guard status: {_GUARD_DIR_FIX}"
    try:
        status = fresh_flagship(flagship_file(env), deps.now())
    except FlagshipUnknown:
        return None, f"FAIL guard status: {_GUARD_DOWN_FIX}"
    return status, "ok   guard status"


def _flagship_health(status: FlagshipStatus) -> str:
    if status.healthy and not status.waiting:
        return "ok   flagship health"
    return _WAIT_LINE


def _renderer(env: Mapping[str, str], deps: Deps) -> tuple[bool, str]:
    try:
        url = comfy_url(env, deps.get)
    except RendererUnreachable:
        return False, f"FAIL renderer: {_RENDERER_FIX}"
    return True, f"ok   renderer: {url}"


def _corpus_version(store: CorpusStore) -> tuple[bool, str]:
    if not store.manifest_file.exists():
        return True, _NO_CORPUS_VERSION
    try:
        manifest = read(store, store.manifest_file, CorpusManifest)
    except CorpusError as error:
        return False, f"FAIL corpus version: {error}"
    if manifest.taxonomy_sha256 != taxonomy_sha256():
        return False, (
            f"FAIL corpus version {store.version} was sampled from another taxonomy: ask the "
            "owner (a new corpus version)"
        )
    return True, f"ok   corpus version {store.version} matches the committed taxonomy"
