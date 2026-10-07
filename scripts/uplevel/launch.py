#!/usr/bin/env python3
"""The uplevel sandbox launcher (O0.1, UR-26 and UR-28): create a phase's agent
sandboxes from a manifest, and retire one without losing work.

    scripts/uplevel/launch.py up --phase <n> [--dry-run]
    scripts/uplevel/launch.py retire <session> [--dry-run]

A host-side tool: the owner runs it, from a clean host checkout of main, inside a herdr
pane; no agent does (docs/uplevel/50-coordination.md, "Where agents run"). It drives
`agent-dgx`, which gives each session its own clone of the host checkout, from
scripts/uplevel/sandboxes.toml, so a phase boundary is one command.

It follows synthbench/host/agent.py, which already drives agent-dgx from the host: every
command goes through a Host seam, --dry-run prints each step instead of running it, all
checks run before any change, and a refusal exits 2 naming the next step.

`up --phase <n>` refuses unless it runs inside herdr and the host checkout is clean and at
origin/main. It creates each missing session with `agent-dgx run <name> … --split` from the
host checkout, checks that `agent-dgx inspect <name> --json` reports that commit as
manifest.source_repository.head, and prints each kickoff line. Re-running creates only what
is missing.

`retire <name>` never loses work. The owner ends the agent's session first. It inspects
inside the sandbox - git runs with `sbx exec agent-<name>` in
/agents/agent-<name>/workspace, never on the host against the workspace: its .git/config is
the agent's to write, and settings such as core.fsmonitor run commands
(docs/synthbench/operator-runbook.md) - for changed or untracked files, stashes, and refs
not pushed to origin, on every branch. It refuses if any of these exist or the inspection
fails; retirement is then the owner's manual call. Otherwise it exports first: a
`git bundle create --all` and an archive of the working tree, made inside the sandbox,
copied to a host directory (a plain read of the mount, as synthbench's `down` does) and
verified there (`git bundle verify` from the owner's checkout; the archive listed). Only
then `agent-dgx stop <name>` and `agent-dgx session rm <name> --force`.

The command vocabulary is what the repo already shows (30-ops.md §O0.1): `agent-dgx run
[--agent --endpoint --mount] --split`, `agent-dgx inspect --json`, `agent-dgx stop`,
`agent-dgx session rm --force`, and `sbx exec <sandbox> bash -lc <script>` - from
synthbench/host/agent.py and docs/synthbench/operator-runbook.md. agent-dgx reads an
unknown word as a new session's name, so every call names its subcommand, and nothing here
runs `agent-dgx help` or `agent-dgx ls`.

MEASURE, open (30-ops.md §O0.1): whether `sbx exec` still reaches the sandbox once the
agent's session has ended. This order does not depend on the answer: the inspection and the
export run while the sandbox is still up, and `agent-dgx stop` comes after them. An
inspection that fails still refuses, and the owner's `retire` run on a throwaway session
posts the measurement.

Exit codes: 0 done; 2 refused, or a step failed, with what to do next.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EXIT_REFUSED = 2
MANIFEST = Path(__file__).resolve().parent / "sandboxes.toml"

MARKER = "@@UPLEVEL_RETIRE@@"
SECTION_NAMES = ("dirty", "stash", "branch", "head", "refs", "remote")
EXPORT_DIR = ".uplevel-retire"

# git inside the sandbox. core.fsmonitor is off because the workspace's .git/config is the
# agent's to write and that setting runs commands (docs/synthbench/operator-runbook.md).
GIT = ("git", "-c", "core.fsmonitor=false")

# The fast model's arguments are the pair the repo already shows (synthbench/host/agent.py,
# docs/synthbench/operator-runbook.md). The owner's arguments for the strongest model, once
# posted on the O0.1 PR, go in [models] in sandboxes.toml; nothing invents a flag here.
DEFAULT_MODELS = {"fast": "--agent claude --endpoint dgx"}

Runner = Callable[..., subprocess.CompletedProcess[str]]


class Refused(RuntimeError):
    """Exit 2: a check refused, or a step failed. The message says what to do next."""


@dataclass(frozen=True)
class Session:
    """One agent, as sandboxes.toml declares it."""

    name: str
    model: str
    kickoff: str
    mounts: tuple[str, ...] = ()

    @property
    def sandbox(self) -> str:
        return f"agent-{self.name}"

    @property
    def workspace(self) -> str:
        return f"/agents/{self.sandbox}/workspace"


@dataclass(frozen=True)
class Host:
    """The owner's machine, behind one seam (as synthbench/host/agent.py does)."""

    checkout: Path  # the owner's checkout of this repository, at origin/main
    manifest: Path = MANIFEST
    exports: Path = field(default_factory=lambda: Path.home() / "uplevel-retirements")
    agents_root: Path = Path("/agents")  # the host sees each session's clone here
    run: Runner = subprocess.run
    env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    which: Callable[[str], str | None] = shutil.which
    dry_run: bool = False

    def clone(self, session: Session) -> Path:
        """The host's view of the session's clone: a directory to read, never to run git
        in (50-coordination.md, "Where agents run")."""
        return self.agents_root / session.sandbox / "workspace"


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
    argv: Iterable[str | Path],
    *,
    cwd: Path | None = None,
    timeout: int = 600,
) -> None:
    """One step that changes something: printed under --dry-run, run otherwise."""
    argv = list(argv)
    command = shlex.join(map(str, argv)) + (f"   (in {cwd})" if cwd else "")
    if host.dry_run:
        _say(f"would {what}: {command}")
        return
    _say(f"== {what}: {command}")
    try:
        host.run([str(a) for a in argv], cwd=cwd, check=True, timeout=timeout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
        raise Refused(f"{what} failed ({error}). Fix it and run this again.") from error


def _in_sandbox(
    host: Host, session: Session, what: str, script: str, *, timeout: int = 600
) -> None:
    """One step run inside the sandbox, in its clone (the only way git gets near it)."""
    _do(
        host,
        what,
        ["sbx", "exec", session.sandbox, "bash", "-lc", f"cd {session.workspace} && {script}"],
        timeout=timeout,
    )


def _inspect_argv(session: Session) -> list[str]:
    """The inspection, run inside the sandbox in the clone (30-ops.md §O0.1)."""
    script = f"cd {session.workspace} && " + _inspection_script(session.name)
    return ["sbx", "exec", session.sandbox, "bash", "-lc", script]


# ------------------------------------------------------------------ manifest


def load_manifest(path: Path) -> dict[int, list[Session]]:
    """sandboxes.toml -> phase number -> its sessions, in file order."""
    try:
        data = _load_toml(path)
    except Refused:
        raise
    phases: dict[int, list[Session]] = {}
    for entry in data.get("phase", []):
        number = int(entry["number"])
        sessions = [
            Session(
                name=str(s["name"]),
                model=str(s["model"]),
                kickoff=" ".join(str(s["kickoff"]).split()),
                mounts=tuple(str(m) for m in s.get("mount", ())),
            )
            for s in entry.get("session", [])
        ]
        if not sessions:
            raise Refused(f"phase {number} in {path} declares no session")
        phases.setdefault(number, []).extend(sessions)
    return phases


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise Refused(f"could not read the manifest {path}: {error}") from error


def run_args_for(manifest_path: Path, session: Session) -> list[str]:
    """The `agent-dgx run` arguments that select the session's model.

    Only two argument sets are known to exist: the fast model's, which the repo already
    shows, and whatever the owner posts for the strongest one on the O0.1 PR. The launcher
    never invents a flag (30-ops.md §O0.1).
    """
    models = {str(k): str(v) for k, v in _load_toml(manifest_path).get("models", {}).items()}
    arguments = dict(DEFAULT_MODELS)
    arguments.update(models)
    if session.model not in arguments:
        raise Refused(
            f"the run arguments for the `{session.model}` model are not in {manifest_path}. "
            f"The owner has them: post them on the O0.1 PR and add "
            f'`{session.model} = "..."` under [models]. Until then {session.name} is '
            "started by hand, as Phases 0 and 1 were (UR-28)."
        )
    return shlex.split(arguments[session.model])


# ------------------------------------------------------------------------ up


def _session(host: Host, name: str) -> dict[str, Any] | None:
    """agent-dgx's view of a session, or None when it has neither a manifest nor a sandbox."""
    found = _inspect_json(_read(host, ["agent-dgx", "inspect", name, "--json"]))
    if found.get("manifest") is None and found.get("sandbox") is None:
        return None
    return found


def _inspect_json(text: str) -> dict[str, Any]:
    try:
        found = json.loads(text)
    except ValueError as error:
        raise Refused(f"agent-dgx inspect did not print JSON: {text[:80]!r}") from error
    if not isinstance(found, dict):
        raise Refused(f"agent-dgx inspect printed {type(found).__name__}, not an object")
    return found


def _source_head(session: Mapping[str, Any]) -> str | None:
    manifest = session.get("manifest") or {}
    head = (manifest.get("source_repository") or {}).get("head")
    return str(head) if head else None


def _preflight(host: Host) -> str:
    """Every check `up` runs before it changes anything. Returns origin/main's commit."""
    if not host.env.get("HERDR_PANE_ID") or host.which("herdr") is None:
        raise Refused(
            "run this inside a herdr pane: `agent-dgx run --split` opens each agent in a "
            "new pane beside it, and this command carries on."
        )
    dirty = _read(host, ["git", "-C", host.checkout, "status", "--porcelain"])
    if dirty:
        raise Refused(
            f"the host checkout {host.checkout} has uncommitted changes, and agent-dgx "
            f"copies them into every clone:\n{dirty}"
        )
    # a fetch moves only a remote-tracking ref; nothing here touches the worktree
    _read(host, ["git", "-C", host.checkout, "fetch", "origin", "main"], check=False)
    # the commit check below is not enough on its own: a feature branch cut from, or merged
    # with, main can match origin/main's sha, and `agent-dgx run` copies the checkout - so
    # the agent would start on that branch. "clean checkout of main" names the branch too.
    branch = _read(host, ["git", "-C", host.checkout, "rev-parse", "--abbrev-ref", "HEAD"])
    if branch != "main":
        where = "at a detached HEAD" if branch == "HEAD" else f"on branch {branch}"
        raise Refused(
            f"the host checkout is {where}, not on main. Every agent starts from a clean "
            "checkout of main (50-coordination.md): `git checkout main`, then run this again."
        )
    origin_main = _read(host, ["git", "-C", host.checkout, "rev-parse", "origin/main"])
    head = _read(host, ["git", "-C", host.checkout, "rev-parse", "HEAD"])
    if head != origin_main:
        raise Refused(
            f"the host checkout is at {head[:8]}, not origin/main ({origin_main[:8]}). "
            "Every agent starts from a clean checkout of main (50-coordination.md): "
            "`git pull --ff-only origin main`, then run this again."
        )
    return origin_main


def up(host: Host, *, phase: int) -> None:
    """Create the phase's missing sessions from the host checkout; print each kickoff."""
    declared = {int(e["number"]) for e in _load_toml(host.manifest).get("phase", [])}
    if phase not in declared:
        raise Refused(
            f"phase {phase} is not in {host.manifest}. The coordinator declares later "
            "phases there; the launcher creates what is declared."
        )
    sessions = load_manifest(host.manifest)[phase]

    target = _preflight(host)
    # every session's model arguments resolve before anything is created: all checks, then
    # all changes - so a phase naming the strongest model refuses whole.
    arguments = {s.name: run_args_for(host.manifest, s) for s in sessions}
    _say(f"the agents' commit: {target[:8]} (origin/main), from {host.checkout}")

    created: list[Session] = []
    for session in sessions:
        found = _session(host, session.name)
        if found is None:
            run = ["agent-dgx", "run", session.name, *arguments[session.name]]
            run += [arg for mount in session.mounts for arg in ("--mount", mount)]
            _do(host, f"create {session.name}", [*run, "--split"], cwd=host.checkout, timeout=900)
            created.append(session)
        elif _source_head(found) != target:
            _say(
                f"{session.name} already exists, cloned from {str(_source_head(found))[:8]}, "
                f"not {target[:8]}: left as it is. When its work is safe, retire it "
                f"(`retire {session.name}`) and run this again for a fresh clone."
            )
        else:
            _say(f"{session.name} already runs at {target[:8]}: nothing to do")

    # the clone is the host's commit by construction, and checked anyway - but only after
    # a real create: under --dry-run nothing was created, so there is no manifest to read
    if host.dry_run:
        for session in created:
            _say(f"would tell {session.name}: {session.kickoff}")
    else:
        for session in created:
            found = _session(host, session.name)
            head = _source_head(found) if found else None
            if head != target:
                raise Refused(
                    f"{session.name} was cloned from {str(head)[:8]}, not {target[:8]} "
                    f"(origin/main). Retire it (`retire {session.name}`), put the checkout "
                    "on origin/main, and run `up` again."
                )
            _say(f"tell {session.name}: {session.kickoff}")

    if created:
        _say(f"created {len(created)}: {', '.join(s.name for s in created)}")


# -------------------------------------------------------------------- retire


def _inspection_script(name: str) -> str:
    """One script, run inside the sandbox, printing six sections. Each `say` line ends with
    MARKER <name> <exit code>, so a read that failed is a refusal, not an empty answer.

    The script is a string handed to `bash -lc`, so every argument goes through shlex.quote:
    `--format=%(objectname) %(refname)` carries a space and parentheses, which unquoted would
    split into two words and stop the shell with a syntax error. test_the_inspection_script_
    runs_... catches exactly that; a substring check on the script cannot.

    The dirty section ignores the two files `retire` itself writes there - a retire that
    failed after its export would otherwise refuse its own retry with a bogus "untracked
    files". Excluded by name, never by directory: anything else found in that directory is
    reported, because `retire` also excludes the whole directory from the worktree archive,
    and a file hidden by both would be lost. A refusal loses nothing - it stops before
    `agent-dgx stop` - so naming the stray file is the safe direction.
    """
    own = (f"{EXPORT_DIR}/{name}.bundle", f"{EXPORT_DIR}/worktree.tar.gz")
    lines = [
        f'say() {{ name=$1; shift; out="$("$@" 2>/dev/null)"; code=$?; '
        f'printf \'%s\\n\' "$out"; printf \'{MARKER} %s %s\\n\' "$name" "$code"; }}'
    ]
    for section, *command in (
        (
            "dirty",
            *GIT,
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            ".",
            *(f":(exclude){path}" for path in own),
        ),
        ("stash", *GIT, "stash", "list"),
        ("branch", *GIT, "rev-parse", "--abbrev-ref", "HEAD"),
        ("head", *GIT, "rev-parse", "HEAD"),
        ("refs", *GIT, "for-each-ref", "--format=%(objectname) %(refname)", "refs/heads"),
        ("remote", *GIT, "ls-remote", "--heads", "origin"),
    ):
        quoted = [shlex.quote(str(part)) for part in command]
        lines.append(" ".join(["say", section, *quoted]))
    return "\n".join(lines) + "\n"


def parse_inspection(stdout: str) -> dict[str, tuple[str, int]]:
    """The script's stdout -> section name -> (text, exit code)."""
    sections: dict[str, tuple[str, int]] = {}
    lines: list[str] = []
    for line in stdout.splitlines():
        if not line.startswith(MARKER):
            lines.append(line)
            continue
        parts = line[len(MARKER) :].split()
        name = parts[0] if parts else "?"
        code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        sections[name] = ("\n".join(lines).strip("\n"), code)
        lines = []
    return sections


def _branches(text: str) -> dict[str, str]:
    """`<sha> <ref>` lines -> {branch: sha}, counting only real branches."""
    found: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].startswith("refs/heads/"):
            found[parts[1].removeprefix("refs/heads/")] = parts[0]
    return found


def assess_inspection(sections: Mapping[str, tuple[str, int]], *, session: str) -> list[str]:
    """Every reason this sandbox still holds work. Empty means safe to retire."""
    missing = [name for name in SECTION_NAMES if name not in sections]
    failed = [name for name in SECTION_NAMES if sections.get(name, ("", 1))[1] != 0]
    if missing or failed:
        return [
            f"the inspection failed (no clean answer from: {', '.join(missing + failed)}). "
            "The likely cause is the open MEASURE in 30-ops.md §O0.1 - whether `sbx exec` "
            "still reaches the sandbox once the agent's session has ended. Retirement is "
            f"the owner's manual call for {session}: read the workspace's files and run git "
            "in it only through `sbx exec`, export a bundle and a tree archive by hand, "
            "then remove the session."
        ]

    risks: list[str] = []
    dirty, _ = sections["dirty"]
    changed = [line for line in dirty.splitlines() if line and not line.startswith("?? ")]
    untracked = [line for line in dirty.splitlines() if line.startswith("?? ")]
    if changed:
        risks.append("changed files: " + ", ".join(changed))
    if untracked:
        risks.append("untracked files: " + ", ".join(untracked))

    stash, _ = sections["stash"]
    if stash.strip():
        risks.append("stashes: " + "; ".join(stash.splitlines()))

    branch, _ = sections["branch"]
    head, _ = sections["head"]
    local = _branches(sections["refs"][0])
    pushed = _branches(sections["remote"][0])
    if branch.strip() == "HEAD":
        risks.append(
            f"HEAD is detached at {head[:8]}: that commit is on no branch, so it cannot be "
            "pushed. Have the agent move it onto a branch and push it, first."
        )
    for name, sha in sorted(local.items()):
        if name not in pushed:
            risks.append(f"branch {name} ({sha[:8]}) is not pushed to origin")
        elif pushed[name] != sha:
            risks.append(
                f"branch {name} is not pushed to origin at {sha[:8]} - origin has "
                f"{pushed[name][:8]}"
            )
    return risks


def retire(host: Host, name: str) -> None:
    """Retire one session, once its work is exported to the host and verified there."""
    session = Session(name=name, model="", kickoff="")
    found = _session(host, name)
    if found is None:
        _say(f"no {name} session: nothing to retire")
        return
    if found.get("sandbox") is None:
        raise Refused(
            f"{name} has a manifest but no sandbox: there is nothing to inspect, so its "
            "work cannot be checked. Retirement is the owner's manual call - once the "
            f"clone is safe, `agent-dgx session rm {name} --force`."
        )

    argv = _inspect_argv(session)
    if host.dry_run:
        # read-only, but its answer decides the steps below: show them as a clean plan
        _say(f"would inspect: {shlex.join(argv)}")
        _say("(dry-run: shown as if the workspace were clean and fully pushed)")
    else:
        _say(f"== inspect {name}'s workspace inside the sandbox")
        try:
            done = host.run(argv, capture_output=True, text=True, timeout=600, check=False)
        except (subprocess.TimeoutExpired, OSError) as error:
            raise Refused(
                f"the inspection of {name} failed ({error}). Retirement is the owner's manual call."
            ) from error
        risks = assess_inspection(parse_inspection(str(done.stdout)), session=name)
        if risks:
            raise Refused(
                f"{name} still holds work, so it was not retired:\n- " + "\n- ".join(risks)
            )

    dest_dir = host.exports / name
    bundle = dest_dir / f"{name}.bundle"
    tree = dest_dir / "worktree.tar.gz"
    staged = host.clone(session) / EXPORT_DIR

    _in_sandbox(
        host,
        session,
        f"bundle {name}'s refs (all of them)",
        f"mkdir -p {EXPORT_DIR} && "
        + " ".join([*GIT, "bundle", "create", f"{EXPORT_DIR}/{name}.bundle", "--all"]),
    )
    _in_sandbox(
        host,
        session,
        f"archive {name}'s working tree",
        f"mkdir -p {EXPORT_DIR} && tar --exclude .git --exclude {EXPORT_DIR} "
        f"-czf {EXPORT_DIR}/worktree.tar.gz .",
    )

    if host.dry_run:
        _say(f"would copy {staged}/ to {dest_dir} (a plain read of the host's mount)")
    else:
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            # reading the sandbox's files from the mount is what synthbench's `down` does;
            # what the rule forbids is running the host's git there (50-coordination.md)
            shutil.copy2(staged / f"{name}.bundle", bundle)
            shutil.copy2(staged / "worktree.tar.gz", tree)
        except OSError as error:
            raise Refused(
                f"could not copy {name}'s export to {dest_dir} ({error}); nothing was "
                "stopped or removed."
            ) from error

    _do(
        host,
        "verify the bundle from the owner's checkout",
        [*GIT, "bundle", "verify", bundle],
        cwd=host.checkout,
    )
    _do(host, "list the worktree archive", ["tar", "-tzf", tree], cwd=host.checkout)

    _do(host, f"stop {name}", ["agent-dgx", "stop", name])
    _do(host, f"remove {name}'s session", ["agent-dgx", "session", "rm", name, "--force"])
    _say(
        f"{name} is retired. Its work is in {dest_dir} (the bundle verified, the archive "
        "listed). When its replacement's branch is open, run `up --phase <n>`."
    )


# ----------------------------------------------------------------------- cli


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scripts/uplevel/launch.py",
        description="Create a phase's uplevel agent sandboxes; retire one without losing work.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    up_p = commands.add_parser("up", help="create the phase's missing sessions")
    up_p.add_argument("--phase", type=int, required=True, help="the phase to bring up")
    retire_p = commands.add_parser("retire", help="export a session's work, then remove it")
    retire_p.add_argument("name", help="the session, as agent-dgx names it (uplevel-ops-a)")
    for sub in (up_p, retire_p):
        sub.add_argument(
            "--dry-run",
            action="store_true",
            help="run the checks and print the steps; change nothing",
        )
    args = parser.parse_args(argv)
    dry = bool(getattr(args, "dry_run", False))
    try:
        repo = Path(
            _read(Host(checkout=Path.cwd(), dry_run=dry), ["git", "rev-parse", "--show-toplevel"])
        )
        host = Host(checkout=repo, dry_run=dry)
        if args.command == "up":
            up(host, phase=args.phase)
        else:
            retire(host, args.name)
    except Refused as error:
        sys.stderr.write(f"uplevel launch: {error}\n")
        return EXIT_REFUSED
    return 0


if __name__ == "__main__":
    sys.exit(main())
