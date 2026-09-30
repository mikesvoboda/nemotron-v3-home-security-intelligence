"""The generation agent's sandbox, from the owner's side (runbook, "Create the agent's sandbox").

    uv run python -m synthbench.host.agent up   [--ref REF] [--discard-notes] [--no-renderer]
    uv run python -m synthbench.host.agent down [--ref REF] [--discard-notes]

both with --dry-run. The owner runs it from a checkout of this repository, inside a herdr pane.

`up` checks everything before it changes anything: it runs in herdr, the renderer is stopped,
and the host checkout has no uncommitted changes. It then retires the old agent (as `down`),
puts the host checkout on REF's exact commit, syncs it and reinstalls the units, and creates
the agent from the host checkout itself, so the agent's clone is the host's commit by
construction; the new manifest's source commit is checked all the same. It prepares the sandbox
with `sbx exec`, starts the renderer, and ends with `doctor` inside the sandbox.

`down` copies the old workspace's docs/synthbench/ to ~/synthbench-gen-backups/<UTC time>/, and
refuses to retire the agent while it holds notes that REF lacks: a file the agent changed from
the commit it was created from, whose content REF does not already have. It never runs git in
the agent's workspace; it hashes the files there as git would.

Exit codes: 0 done; 2 refused, or a step failed, with what to do next.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from synthbench.host.units import GUARD, RENDERER

SESSION = "synthbench-gen"
SANDBOX = f"agent-{SESSION}"
WORKSPACE = Path("/agents") / SANDBOX / "workspace"
HOST_CHECKOUT = Path("/synthbench/host-checkout")
BACKUPS = Path.home() / "synthbench-gen-backups"
NOTES = "docs/synthbench"
MOUNTS = ("/synthbench/corpus:rw", "/synthbench/status:ro")
APT_LIBS = ("libxcb1", "libgl1", "libglib2.0-0")  # OpenCV's; the sandbox image lacks them
HANDOFF = "Read docs/synthbench/agent-handoff.md and follow it."
EXIT_REFUSED = 2
_STOPPED = ("inactive", "failed")

Runner = Callable[..., subprocess.CompletedProcess[str]]


class Refused(RuntimeError):
    """Exit 2: a check refused, or a step failed. The message says what to do next."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Host:
    repo: Path  # the owner's checkout, which names the commit
    host_checkout: Path = HOST_CHECKOUT
    workspace: Path = WORKSPACE
    backups: Path = BACKUPS
    run: Runner = subprocess.run
    env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    which: Callable[[str], str | None] = shutil.which
    now: Callable[[], datetime] = _utc_now
    dry_run: bool = False


def blob_id(data: bytes) -> str:
    """The id git gives a file's content (`git hash-object`)."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


def _say(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _read(host: Host, argv: Sequence[str | Path], *, check: bool = True) -> str:
    try:
        done = host.run(
            [str(a) for a in argv], capture_output=True, text=True, timeout=120, check=check
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
        raise Refused(f"could not read `{shlex.join(map(str, argv))}`: {error}") from error
    return str(done.stdout).strip()


def _do(
    host: Host,
    what: str,
    argv: Sequence[str | Path],
    *,
    cwd: Path | None = None,
    timeout: int = 600,
) -> None:
    """One step that changes something: printed under --dry-run, run otherwise."""
    command = shlex.join(map(str, argv)) + (f"   (in {cwd})" if cwd else "")
    if host.dry_run:
        _say(f"would {what}: {command}")
        return
    _say(f"== {what}: {command}")
    try:
        host.run([str(a) for a in argv], cwd=cwd, check=True, timeout=timeout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
        raise Refused(f"{what} failed ({error}). Fix it and run `up` again.") from error


def _in_sandbox(host: Host, what: str, command: str, *, timeout: int = 600) -> None:
    script = f"cd {host.workspace} && {command}"
    _do(host, what, ["sbx", "exec", SANDBOX, "bash", "-lc", script], timeout=timeout)


def _session(host: Host) -> dict[str, Any] | None:
    """agent-dgx's view of the session, or None when it has neither a manifest nor a sandbox."""
    found: dict[str, Any] = json.loads(_read(host, ["agent-dgx", "inspect", SESSION, "--json"]))
    if found.get("manifest") is None and found.get("sandbox") is None:
        return None
    return found


def _source_head(session: Mapping[str, Any]) -> str | None:
    manifest = session.get("manifest") or {}
    head = (manifest.get("source_repository") or {}).get("head")
    return str(head) if head else None


def _tree(host: Host, commit: str) -> dict[str, str]:
    """Path -> blob id for every file under NOTES at the commit."""
    listing = _read(host, ["git", "-C", host.repo, "ls-tree", "-r", commit, "--", NOTES])
    tree: dict[str, str] = {}
    for line in listing.splitlines():
        meta, _, path = line.partition("\t")
        tree[path] = meta.split()[2]
    return tree


def _notes_at_risk(host: Host, base: str | None, target: str) -> list[str]:
    """Files under the old workspace's NOTES the new agent would not get."""
    root = host.workspace / NOTES
    if not root.is_dir():
        return []
    started = _tree(host, base) if base else {}
    kept = _tree(host, target)
    at_risk = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(host.workspace).as_posix()
        now = blob_id(path.read_bytes())
        changed = base is None or started.get(rel) != now
        if changed and kept.get(rel) != now:
            at_risk.append(rel)
    return at_risk


def _resolve(host: Host, ref: str) -> str:
    return _read(host, ["git", "-C", host.repo, "rev-parse", "--verify", f"{ref}^{{commit}}"])


def down(host: Host, *, ref: str, discard_notes: bool) -> None:
    """Retire the old agent, once its notes are safe."""
    target = _resolve(host, ref)
    session = _session(host)
    if session is None:
        _say(f"no {SESSION} session: nothing to retire")
        return
    at_risk = _notes_at_risk(host, _source_head(session), target)
    if host.dry_run:
        where = "would be copied"
        _say(f"would copy the old workspace's {NOTES}/ to {host.backups}/<UTC time>/")
    else:
        copy = host.backups / host.now().strftime("%Y%m%dT%H%M%SZ") / NOTES
        if (host.workspace / NOTES).is_dir():
            try:
                shutil.copytree(host.workspace / NOTES, copy)
            except OSError as error:
                raise Refused(
                    f"could not copy the old workspace's {NOTES}/ to {copy} ({error}); "
                    "the agent was not retired."
                ) from error
        where = f"copied to {copy}"
        _say(f"the old workspace's {NOTES}/ is {where}")
    if at_risk and not discard_notes:
        raise Refused(
            f"the old agent holds notes that {target[:8]} lacks: {', '.join(at_risk)} "
            f"({where}). Commit them to your checkout and run this again, or pass "
            "--discard-notes."
        )
    if session.get("sandbox") is not None:
        _do(host, "stop the old agent", ["agent-dgx", "stop", SESSION])
    _do(host, "remove the old agent's session", ["agent-dgx", "session", "rm", SESSION, "--force"])


def _preflight(host: Host, target: str) -> None:
    if not host.env.get("HERDR_PANE_ID") or host.which("herdr") is None:
        raise Refused(
            "run this inside a herdr pane: `agent-dgx run --split` opens the agent in a new "
            "pane beside it, and this command carries on."
        )
    state = _read(host, ["systemctl", "--user", "is-active", RENDERER], check=False)
    if state not in _STOPPED:
        raise Refused(
            f"the renderer is {state}. Stop it first (`systemctl --user stop {RENDERER}`): "
            "this changes the code it runs, and starts it again at the end."
        )
    dirty = _read(
        host, ["git", "-C", host.host_checkout, "status", "--porcelain", "--untracked-files=no"]
    )
    if dirty:
        raise Refused(
            f"the host checkout {host.host_checkout} has uncommitted changes, and agent-dgx "
            f"would copy them into the agent's clone:\n{dirty}"
        )
    _read(host, ["git", "-C", host.host_checkout, "cat-file", "-e", f"{target}^{{commit}}"])


def up(host: Host, *, ref: str, discard_notes: bool, renderer: bool) -> None:
    """Recreate the agent at REF's commit, ready for the owner's request."""
    target = _resolve(host, ref)
    subject = _read(host, ["git", "-C", host.repo, "log", "-1", "--format=%s", target])
    _say(f"the agent's commit: {target[:8]} {subject}")
    _preflight(host, target)
    down(host, ref=target, discard_notes=discard_notes)

    checkout = host.host_checkout
    _do(
        host,
        f"put the host checkout on {target[:8]}",
        ["git", "-C", checkout, "checkout", "--detach", target],
    )
    _do(host, "sync the host checkout", ["uv", "sync", "--frozen"], cwd=checkout, timeout=1800)
    python = checkout / ".venv" / "bin" / "python"
    _do(
        host,
        "install the host units",
        [python, "-m", "synthbench.host.units", "install"],
        cwd=checkout,
    )
    _do(host, "restart the guard", ["systemctl", "--user", "restart", GUARD])

    mounts = [arg for mount in MOUNTS for arg in ("--mount", mount)]
    create = ["agent-dgx", "run", SESSION, "--agent", "claude", "--endpoint", "dgx", *mounts]
    _do(
        host,
        "create the agent in a new herdr pane",
        [*create, "--split"],
        cwd=checkout,
        timeout=900,
    )
    if not host.dry_run:
        session = _session(host)
        head = _source_head(session) if session else None
        if head != target:
            raise Refused(
                f"the new agent was cloned from {str(head)[:8]}, not {target[:8]}. Retire it "
                "(`down --discard-notes`) and run `up` again."
            )

    _do(
        host,
        "install OpenCV's libraries in the sandbox",
        ["sbx", "exec", SANDBOX, "sudo", "apt-get", "install", "-y", *APT_LIBS],
    )
    _in_sandbox(host, "sync the agent's dependencies", "uv sync --frozen", timeout=1800)
    _in_sandbox(host, "check the commands import", 'uv run python -c "import synthbench.cli, av"')
    if renderer:
        _do(
            host,
            "start the renderer (about a minute: the FLUX.2 warm-up)",
            ["systemctl", "--user", "start", RENDERER],
            timeout=1500,
        )
        _in_sandbox(host, "run doctor in the sandbox", "uv run python -m synthbench doctor")
    else:
        _say(f"not started: the renderer. `doctor` needs it; run it once you start {RENDERER}.")
    _say(f"ready. In the agent's pane, say: {HANDOFF} <your request>")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m synthbench.host.agent",
        description="Retire or recreate the synthbench generation agent's sandbox.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    parsers = {
        "up": commands.add_parser("up", help="retire the old agent, then create a ready one"),
        "down": commands.add_parser("down", help="retire the agent, once its notes are safe"),
    }
    for sub in parsers.values():
        sub.add_argument("--ref", default="HEAD", help="the agent's commit (default: HEAD)")
        sub.add_argument(
            "--discard-notes",
            action="store_true",
            help="retire even when the old agent holds notes REF lacks",
        )
        sub.add_argument(
            "--dry-run",
            action="store_true",
            help="run the checks and print the steps; change nothing",
        )
    parsers["up"].add_argument(
        "--no-renderer", action="store_true", help="leave the renderer stopped, and skip doctor"
    )
    args = parser.parse_args(argv)
    try:
        repo = Path(_read(Host(repo=Path.cwd()), ["git", "rev-parse", "--show-toplevel"]))
        host = Host(repo=repo, dry_run=args.dry_run)
        if args.command == "up":
            up(host, ref=args.ref, discard_notes=args.discard_notes, renderer=not args.no_renderer)
        else:
            down(host, ref=args.ref, discard_notes=args.discard_notes)
    except Refused as error:
        sys.stderr.write(f"synthbench agent: {error}\n")
        return EXIT_REFUSED
    return 0


if __name__ == "__main__":
    sys.exit(main())
