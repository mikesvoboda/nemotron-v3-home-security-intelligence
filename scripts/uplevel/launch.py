#!/usr/bin/env python3
"""The uplevel sandbox launcher (O0.1, UR-26 and UR-28): create a phase's agent
sandboxes from a manifest, and retire one without losing work.

    scripts/uplevel/launch.py up --phase <n> [--dry-run]
    scripts/uplevel/launch.py retire <session> [--dry-run]

A host-side tool: the owner runs it, from a clean host checkout of main, inside a herdr
pane; no agent does (docs/uplevel/rules.md, "Agents, sandboxes and models"). It drives
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

The command vocabulary is what the repo already shows (history/packages-done.md §O0.1):
`agent-dgx run [--agent --endpoint --mount] --split`, `agent-dgx inspect --json`, `agent-dgx stop`,
`agent-dgx session rm --force`, and `sbx exec <sandbox> bash -lc <script>` - from
synthbench/host/agent.py and docs/synthbench/operator-runbook.md. agent-dgx reads an
unknown word as a new session's name, so every call names its subcommand, and nothing here
runs `agent-dgx help` or `agent-dgx ls`.

MEASURE, open (history/packages-done.md §O0.1): whether `sbx exec` still reaches the sandbox
once the agent's session has ended. This order does not depend on the answer: the inspection and the
export run while the sandbox is still up, and `agent-dgx stop` comes after them. An
inspection that fails still refuses, and the owner's `retire` run on a throwaway session
posts the measurement. The supervisor's budget kill does not depend on the answer either: the
`timeout` wrapper runs *inside* the sandbox, so the tick dies at the budget even if `sbx exec`
later stops reaching it; the host's own timeout stays only as the backstop for a fire whose
`sandbox` never answers at all. The supervisor's dgx-file probe answers through the same
channel and its failure arms pass through for the same reason: the fire's own handlers are
what record the unreachable sandbox (`status=refused` for a failed connection,
`killed=yes status=timeout` for a read that overruns the probe's 120s cap), so the gap is
logged rather than refused away before any log line exists.

Exit codes: 0 done; 2 refused, or a step failed, with what to do next.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXIT_REFUSED = 2
MANIFEST = Path(__file__).resolve().parent / "sandboxes.toml"

MARKER = "@@UPLEVEL_RETIRE@@"
SECTION_NAMES = ("dirty", "stash", "branch", "head", "refs", "remote", "origin")
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
    gpu: bool = False

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
        in (rules.md, "Agents, sandboxes and models")."""
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
        # No blanket "fix it and run this again". The owner's first real retire (the PR's
        # Evidence record) got through every step and failed at the last: `agent-dgx
        # session rm` printed "Sandbox 'agent-uplevel-scratch' removed", then failed its
        # workspace cleanup ("cannot unmount '/agents/agent-uplevel-scratch': pool or
        # dataset is busy", from agent-dgx's own agent-ws destroy, exit 1). The owner's
        # `inspect --json` after shows what that leaves: "sandbox":null beside a manifest
        # still there - removed halfway. A re-run of this command cannot finish that (it
        # refuses on manifest-but-no-sandbox, whose own text names the manual `session rm`
        # that completes it), so the message says what is already safe and where the half-
        # done state is visible, instead of sending the owner to a no-op.
        raise Refused(
            f"{what} failed ({error}). Every step before it succeeded, and this command "
            "exports and verifies the work before it stops or removes anything, so "
            "nothing earlier needs redoing: fix the cause and run this again - unless the "
            "failed step was the session's removal. If `agent-dgx inspect <name> --json` "
            'then shows `"sandbox": null` beside a manifest that is still there, the '
            "session is removed halfway (the sandbox is gone; its workspace cleanup is "
            "not), and running this again refuses with the manual step that finishes it."
        ) from error


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
    """The inspection, run inside the sandbox in the clone (history/packages-done.md §O0.1)."""
    script = f"cd {session.workspace} && " + _inspection_script(session.name)
    return ["sbx", "exec", session.sandbox, "bash", "-lc", script]


# ------------------------------------------------------------------ manifest


def load_manifest(path: Path) -> dict[int, list[Session]]:
    """sandboxes.toml -> phase number -> its sessions, in file order."""
    return _phases_of(_load_toml(path), path)


def _phases_of(data: Mapping[str, Any], path: Path) -> dict[int, list[Session]]:
    """Interpret an already-parsed manifest. `up` parses once and passes the result down:
    reading a hand-edited file three times means three snapshots of it, and a coordinator
    edit landing mid-run would have `up` check the phase list against one content and
    resolve the run arguments from another."""
    # The file is hand-edited by other people ("the coordinator adds rows as the plan
    # changes"), and the launcher's whole contract is a refusal that names the next
    # step. A bare KeyError traceback would be the wrong answer to a missing `model`.
    phases: dict[int, list[Session]] = {}
    for position, entry in enumerate(data.get("phase", []), start=1):
        number = _phase_number(entry, path, position)
        sessions = [
            _session_row(s, path, f"phase {number} in {path}") for s in entry.get("session", [])
        ]
        if not sessions:
            raise Refused(f"phase {number} in {path} declares no session")
        phases.setdefault(number, []).extend(sessions)
    # A hand-edited roster can name one session twice, and the merge above folds both
    # shapes into one list: two rows in one [[phase]] block, or two blocks with the same
    # number. `up` cannot honour that - it reads every name's state before any change (the
    # gpu grant check can only know a create is coming once it knows who is missing), so
    # both rows read missing and both create: two sandboxes, and for a gpu row two grants
    # where UR-30 allows one. Refuse as the required-key refusals do. A name may reappear
    # in a *later* phase - each boundary creates its own members - so this is per phase.
    for number, rows in phases.items():
        seen: set[str] = set()
        for session in rows:
            if session.name in seen:
                raise Refused(
                    f"phase {number} in {path} lists {session.name} twice. A name appears "
                    f"once per phase. Remove the repeat from {path}; the same name may "
                    "reappear in a later phase."
                )
            seen.add(session.name)
    return phases


def _phase_number(entry: Mapping[str, Any], path: Path, position: int) -> int:
    where = f"[[phase]] #{position} in {path}"
    value = _required(entry, "number", path, where)
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise Refused(f"{where} has `number = {value!r}`, not a whole number") from error


def _session_row(row: Mapping[str, Any], path: Path, where: str) -> Session:
    label = f"{where} session {row.get('name', '?')}"
    # `gpu` is optional, so _required never sees it - and a truthy typo (`gpu = 1`,
    # `gpu = "yes"`) must not silently hand a sandbox the GPU UR-30 rationed to one
    # holder. Refuse the row, naming the key, as the required keys' refusals do.
    gpu = row.get("gpu", False)
    if gpu is not True and gpu is not False:
        raise Refused(
            f"{label} has `gpu = {gpu!r}`. In {path} the flag is a plain TOML boolean: "
            "`gpu = true` grants the GPU, and saying nothing withholds it."
        )
    mounts = tuple(str(m) for m in row.get("mount", ()))
    if gpu:
        # history/packages-done.md §O1.10, as the operator row's comment says: agent-dgx
        # --gpu mounts /srv/agent-models itself and refuses any mount at or under it. A row that
        # collides with the library dies inside agent-dgx at create time; refusing the row
        # here is the launcher's own check, not a guess about agent-dgx's behaviour.
        for mount in mounts:
            # Normalize, don't just trim: the rule is about the path the mount lands on,
            # so an equivalent spelling (/srv//agent-models, /srv/agent-models/./) names
            # the same library and must refuse too (backend review note 7b on #6867).
            source = os.path.normpath(mount.partition(":")[0])
            if source == "/srv/agent-models" or source.startswith("/srv/agent-models/"):
                raise Refused(
                    f"{label} has `gpu = true` and mounts {mount}, at or under "
                    "/srv/agent-models, which `agent-dgx --gpu` mounts itself and "
                    "refuses any mount at or under (history/packages-done.md §O1.10). "
                    f"Remove that mount from {path}."
                )
    return Session(
        name=str(_required(row, "name", path, label)),
        model=str(_required(row, "model", path, label)),
        kickoff=" ".join(str(_required(row, "kickoff", path, label)).split()),
        mounts=mounts,
        gpu=gpu,
    )


def _required(row: Mapping[str, Any], key: str, path: Path, where: str) -> Any:
    """One manifest key that must be there, or a refusal naming the row and the key."""
    if key not in row:
        raise Refused(
            f"{where} has no `{key}`. Fix {path}: every session names `name`, `model` and "
            "`kickoff`, and every phase names `number`."
        )
    return row[key]


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise Refused(f"could not read the manifest {path}: {error}") from error


def run_args_for(data: Mapping[str, Any], manifest_path: Path, session: Session) -> list[str]:
    """The `agent-dgx run` arguments that select the session's model.

    Only two argument sets are known to exist: the fast model's, which the repo already
    shows, and whatever the owner posts for the strongest one on the O0.1 PR. The launcher
    never invents a flag (history/packages-done.md §O0.1). `data` is the parsed file from the
    same read `up` used for its phase list, so one run sees one content; `manifest_path` is named
    only in the refusal, which has to say which file to edit.
    """
    models = {str(k): str(v) for k, v in data.get("models", {}).items()}
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


def _sandbox_state(session: Mapping[str, Any]) -> str:
    """The sandbox's own reported status, for a line that must not claim it runs.

    The owner's inspect on #6855 shows a session whose agent's pane was closed reading
    `"status": "stopped"` with its sandbox record still present - the ordinary state after
    an agent finishes, not a stop or a removal. `up` used to print "already runs" for every
    non-absent session, which is false of that one; this echoes the status string as
    inspect gives it (or "unknown" if it has none) so the summary states what was read.
    """
    sandbox = session.get("sandbox")
    if isinstance(sandbox, Mapping):
        return str(sandbox.get("status") or "unknown")
    return "unknown"


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
    # the commit check below is not enough on its own: a feature branch cut from, or merged
    # with, main can match origin/main's sha, and `agent-dgx run` copies the checkout - so
    # the agent would start on that branch. "clean checkout of main" names the branch too.
    # Checked before the fetch: a wrong branch should refuse without a network round trip.
    branch = _read(host, ["git", "-C", host.checkout, "rev-parse", "--abbrev-ref", "HEAD"])
    if branch != "main":
        where = "at a detached HEAD" if branch == "HEAD" else f"on branch {branch}"
        raise Refused(
            f"the host checkout is {where}, not on main. Every agent starts from a clean "
            "checkout of main (rules.md, UR-28): `git checkout main`, then run this again."
        )
    # The fetch is what makes the origin/main check worth running at all, and it moves only a
    # remote-tracking ref - never the worktree, never a branch. A failed fetch is refused, not
    # swallowed: against a stale ref the check below can pass while main has moved on, and a
    # sandbox cloned from the wrong commit is worse to undo than a refused command.
    fetch = ["git", "-C", host.checkout, "fetch", "origin", "main"]
    _say(f"== check origin/main is current: {shlex.join(map(str, fetch))}")
    _read(host, fetch)
    origin_main = _read(host, ["git", "-C", host.checkout, "rev-parse", "origin/main"])
    head = _read(host, ["git", "-C", host.checkout, "rev-parse", "HEAD"])
    if head != origin_main:
        raise Refused(
            f"the host checkout is at {head[:8]}, not origin/main ({origin_main[:8]}). "
            "Every agent starts from a clean checkout of main (rules.md, UR-28): "
            "`git pull --ff-only origin main`, then run this again."
        )
    return origin_main


def up(host: Host, *, phase: int) -> None:
    """Create the phase's missing sessions from the host checkout; print each kickoff."""
    _check_owner_checkout(host)
    # One read of the file for the whole command. _phases_of interprets every row, so a
    # typo refuses before anything else happens and the "phase is not declared" check
    # below sees a well-formed set - and the [models] table resolved a few lines down is
    # from this same content, not a second read that a concurrent edit could change.
    data = _load_toml(host.manifest)
    phases = _phases_of(data, host.manifest)
    if phase not in phases:
        raise Refused(
            f"phase {phase} is not in {host.manifest}. The coordinator declares later "
            "phases there; the launcher creates what is declared."
        )
    sessions = phases[phase]

    target = _preflight(host)
    # every session's model arguments resolve before anything is created: all checks, then
    # all changes - so a phase naming the strongest model refuses whole.
    arguments = {s.name: run_args_for(data, host.manifest, s) for s in sessions}
    # the phase's inspect results, gathered before any change (they are reads): the
    # gpu check below must refuse a whole phase the way the model check does, and it
    # can only know a --gpu create is actually coming once it knows who is missing.
    present = {s.name: _session(host, s.name) for s in sessions}
    grant = [s.name for s in sessions if s.gpu and present[s.name] is None]
    if grant and not host.env.get("AGENT_GPU_RUNNER_URL"):
        raise Refused(
            f"{', '.join(grant)} would be created with `--gpu`, but this shell has no "
            "AGENT_GPU_RUNNER_URL: that is how agent-gpu's runner - the only thing "
            "`--gpu`'s model library mounts from - reaches the launching shell "
            "(history/packages-done.md §O1.10). Run this from the shell that has it, or start "
            f"{grant[0]} by hand (UR-30: one GPU holder). No session in this phase was "
            "created."
        )
    _say(f"the agents' commit: {target[:8]} (origin/main), from {host.checkout}")

    created: list[Session] = []
    for session in sessions:
        found = present[session.name]
        if found is None:
            run = ["agent-dgx", "run", session.name, *arguments[session.name]]
            run += [arg for mount in session.mounts for arg in ("--mount", mount)]
            # after the model arguments, before --split: the order the owner's hand-start
            # line shows (history/packages-done.md §O1.10). No --mount is added for
            # /srv/agent-models - agent-dgx --gpu mounts the library itself and refuses any
            # mount at or under it.
            if session.gpu:
                run.append("--gpu")
            _do(host, f"create {session.name}", [*run, "--split"], cwd=host.checkout, timeout=900)
            created.append(session)
        elif found.get("sandbox") is None:
            # Half-removal is real, not hypothetical: both of the owner's real retires on
            # #6855 ended with agent-dgx's `session rm` deleting the sandbox and then
            # failing its own workspace cleanup, which leaves exactly this inspect state -
            # a manifest with "sandbox": null. Falling through would print "already runs
            # at <sha>: nothing to do" for a name with nothing running behind it, and the
            # phase would go out with a member silently missing. Neither guess is the
            # launcher's to make (re-running agent-dgx's own run line is agent-dgx's
            # fail-closed territory); refuse, naming the verb that finishes the removal.
            raise Refused(
                f"{session.name} has a manifest but no sandbox: its removal finished "
                "halfway (the sandbox is gone; agent-dgx's workspace cleanup after it "
                "did not complete). Nothing runs under this name, so this run creates "
                f"nothing for it: finish the removal with `agent-dgx session rm "
                f"{session.name} --force`, then run this again."
            )
        elif _source_head(found) != target:
            _say(
                f"{session.name} already exists, cloned from {str(_source_head(found))[:8]}, "
                f"not {target[:8]}: left as it is. When its work is safe, retire it "
                f"(`retire {session.name}`) and run this again for a fresh clone."
            )
        else:
            # Not "already runs". The owner's `inspect uplevel-scratch2 --json` on #6855
            # shows the state a session is left in when its agent's pane is simply closed:
            # a manifest and a sandbox record beside each other, the sandbox reading
            # "status": "stopped" - and nobody ran `agent-dgx stop`. `up` filed that under
            # "already runs", which is true of nothing, and this is the ordinary case, not
            # the corner (an agent finishing its turn leaves every session stopped), so the
            # line reports what inspect actually says and asserts nothing about whether
            # anything is running. The status value is echoed, not matched on: "stopped" is
            # the only one ever read here, so inventing a vocabulary to branch over - and
            # refusing on it - would break the normal bring-up.
            _say(
                f"{session.name} already exists at {target[:8]}, sandbox "
                f"{_sandbox_state(found)}: nothing to do"
            )

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
        # the owner's Phase-2 dry-run on #6855 caught this: every line above a dry run
        # says "would", but this summary said "created" for sessions a dry run never
        # created - the one line a skimming reader trusts, stating a false past.
        verb = "would create" if host.dry_run else "created"
        _say(f"{verb} {len(created)}: {', '.join(s.name for s in created)}")


# -------------------------------------------------------------------- retire


def _inspection_script(name: str) -> str:
    """One script, run inside the sandbox, printing seven sections. Each `say` line ends with
    MARKER <name> <exit code>, so a read that failed is a refusal, not an empty answer; a
    failed section also carries the first line of its stderr, so the refusal shows its cause
    instead of leaving one guess (a syntax error here once read as the MEASURE item).

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

    The `origin` section answers "pushed to WHAT?" - `ls-remote` asks the remote the agent's
    own .git/config names, and the agent writes that config. `assess_inspection` compares
    the answer with the host checkout's, so a redirected origin cannot pass as pushed.
    """
    own = (f"{EXPORT_DIR}/{name}.bundle", f"{EXPORT_DIR}/worktree.tar.gz")
    # The helper sticks to bash builtins and one /tmp file: a missing coreutil (mktemp,
    # head) would fail every section at once, and every section failing is the whole
    # feature refusing - the same total-failure shape as the quoting bug above.
    lines = [
        'say() { name=$1; shift; err=/tmp/uplevel-retire-$$.$name; out="$("$@" 2>"$err")"; '
        "code=$?; printf '%s\\n' \"$out\"; "
        'if [ "$code" -ne 0 ]; then first=""; { read -r first || :; } <"$err" 2>/dev/null || :; '
        'printf \'stderr: %s\\n\' "$first"; fi; rm -f "$err"; '
        f'printf \'{MARKER} %s %s\\n\' "$name" "$code"; }}'
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
        ("origin", *GIT, "remote", "get-url", "origin"),
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


def assess_inspection(
    sections: Mapping[str, tuple[str, int]],
    *,
    session: str,
    expected_origin: str | None = None,
) -> list[str]:
    """Every reason this sandbox still holds work. Empty means safe to retire.

    `expected_origin` is the host checkout's own origin URL: `retire` always passes it, so
    "pushed" is only believed when the sandbox and the host agree on what `origin` is.
    None exists for tests of this function alone - the launcher never skips the check.
    """
    missing = [name for name in SECTION_NAMES if name not in sections]
    failed = [name for name in SECTION_NAMES if sections.get(name, ("", 1))[1] != 0]
    if missing or failed:
        # each failed section carries the first line of its stderr, when the script got
        # far enough to record one: the cause belongs in the refusal, not in a guess
        causes = [
            line
            for name in dict.fromkeys(missing + failed)
            for line in sections.get(name, ("", 0))[0].splitlines()
            if line.startswith("stderr:")
        ]
        return [
            f"the inspection failed (no clean answer from: "
            f"{', '.join(dict.fromkeys(missing + failed))}). "
            + "".join(f"\n- {cause}" for cause in causes)
            + " The likely cause, if none is shown, is the open MEASURE in "
            "history/packages-done.md §O0.1 - whether `sbx exec` still reaches the sandbox "
            "once the agent's session has ended. Retirement is the owner's manual call for "
            f"{session}: read the workspace's files and run git in it only through `sbx exec`, "
            "export a bundle and a tree archive by hand, then remove the session."
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

    # `remote` asked the origin the AGENT's .git/config names - and the agent writes that
    # config. Work pushed to a local path or a sibling sandbox would answer "all pushed"
    # while GitHub never saw it, so the URL itself must match the host's before any of it
    # counts (rules.md, "Agents, sandboxes and models": GitHub is the only channel between
    # sandboxes).
    origin, _ = sections["origin"]
    if expected_origin is not None and origin.strip() != expected_origin:
        risks.append(
            f"its `origin` is {origin.strip()!r}, not the host checkout's {expected_origin!r}: "
            f"every `pushed` answer above was read from that remote, so none of it can be "
            f"trusted. Point {session}'s origin at the real one and push, or retire by hand."
        )

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


def _origin_url(host: Host) -> str:
    """The host checkout's own `origin` URL - the answer `pushed` should mean. Read from
    the host's checkout, which the launcher already reads git in (unlike an agent's)."""
    return _read(host, ["git", "-C", host.checkout, "remote", "get-url", "origin"])


def _check_owner_checkout(host: Host) -> None:
    """The checkout the run resolves from the shell's cwd must be the owner's, not a
    session's clone (the owner's own retire on #6855 ran from
    /agents/agent-uplevel-scratch/workspace and surfaced this).

    Under the trust model this checkout is the reference the command believes it can
    trust: `retire` compares the session's `origin` against *this* one (finding #5 - the
    session's own `.git/config` is the thing under suspicion, so comparing it to itself
    proves nothing), verifies the bundle by running the host's git *in* it, and `up`
    checks it is clean main before copying it into every clone. Silently run from a
    session's clone, all three become self-reports of the agent's own repo - and the
    bundle verify runs host git inside the very workspace the operator runbook forbids
    (its .git/config, core.fsmonitor included, is the agent's to write). Nothing here can
    tell a session's clone from any other checkout but by where it lives: agent-dgx's
    layout puts every session's clone under agents_root, so that is the check.
    """
    checkout = host.checkout.resolve()
    root = host.agents_root.resolve()
    if checkout == root or root in checkout.parents:
        raise Refused(
            f"this run's checkout is {checkout}, inside the sessions' root {root} - a "
            "session's own clone. Run the launcher from your own checkout of this "
            "repository instead: retire reads the trusted `origin` URL from here and "
            "verifies the exported bundle in it, and up copies it into every clone - all "
            "of which must be a checkout the sessions cannot write. cd there and run "
            "this again."
        )


def retire(host: Host, name: str) -> None:
    """Retire one session, once its work is exported to the host and verified there."""
    _check_owner_checkout(host)
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

    # The inspection only reads, so --dry-run runs it too (its help: "run the checks and
    # print the steps"). A dry run that skipped it would print a clean plan ending in
    # `session rm --force` for a workspace the real run refuses - the hedge it replaces
    # said so in parentheses, which is not the same as the refusal.
    argv = _inspect_argv(session)
    _say(f"== inspect {name}'s workspace inside the sandbox: {shlex.join(argv)}")
    try:
        done = host.run(argv, capture_output=True, text=True, timeout=600, check=False)
    except (subprocess.TimeoutExpired, OSError) as error:
        raise Refused(
            f"the inspection of {name} failed ({error}). Retirement is the owner's manual call."
        ) from error
    risks = assess_inspection(
        parse_inspection(str(done.stdout)), session=name, expected_origin=_origin_url(host)
    )
    if risks:
        raise Refused(f"{name} still holds work, so it was not retired:\n- " + "\n- ".join(risks))

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
            # what the rule forbids is running the host's git there (rules.md, UR-170)
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


# ----------------------------------------------------------------- supervise
#
# [r247]. The coordinator's tick is already a fresh, unnamed subagent whose only memory is
# the read-through cursor in its heartbeat (UR-173), so the in-pane `/loop` dispatcher adds
# nothing but a process that can die or hang - on 2026-10-16 it did, and the coordinator
# posted nothing from 03:47Z to 13:30Z. The supervisor replaces that process from the host:
# each timer fire is one tick, run headless inside the sandbox.

COORDINATOR = "uplevel-coordinator"
SUPERVISE_DIR = Path("supervise")
TICK_BUDGET = 60 * 60  # a tick that has run 60 minutes is killed ([r247], box 2)
# The pane's own launch flags, inside the sandbox (ruling 259): agent-dgx starts the
# coordinator's claude with bypass permissions, this settings file and this MCP config,
# and a bare headless `claude -p` drops all three. The fire mirrors the pane; it reads
# these two files in the sandbox and copies no setting into the repo. The files live in
# the sandbox's HOME, not the workspace: agent-dgx keeps them at
# `$HOME/.claude/agent-dgx/` (measured: `/home/agent/.claude/agent-dgx/` in a running
# session, and `workspace/.claude/agent-dgx/` does not exist), so the paths stay
# unexpanded here and the sandbox's own shell resolves `$HOME` on both wires (owner
# answer on #6854, 2026-10-18T23:31Z).
DGX_SETTINGS = "$HOME/.claude/agent-dgx/claude-settings.json"
DGX_MCP = "$HOME/.claude/agent-dgx/mcp.json"
KICKOFF_DOC = Path(__file__).resolve().parents[2] / "docs" / "uplevel" / "roles" / "coordinator.md"


def tick_prompt(doc: Path = KICKOFF_DOC) -> str:
    """The tick prompt, word for word as the `/loop` line in `coordinator.md` quotes it.

    Read out of the document rather than restated here, because box 1's whole claim is that
    the supervisor fires *that* string and not a paraphrase: the `/loop 30m ...` line names
    it in double quotes, and that quotation is the definition. A test pins the two together,
    so amending the prompt in one place cannot silently leave the other firing the old text.
    """
    text = doc.read_text(encoding="utf-8")
    quoted = re.search(r'/loop \d+m Dispatch one fresh[^\n]*?"(.+?)"', text)
    if quoted is None:
        raise Refused(
            f"{doc} no longer quotes the tick prompt on its `/loop` line, so the supervisor "
            "has nothing to fire. Restore the quoted prompt, or update tick_prompt() with it."
        )
    return quoted.group(1)


@contextmanager
def _tick_lock(path: Path) -> Iterator[bool]:
    """Hold the tick lock, or yield False at once if another fire holds it.

    The kernel drops a flock when its holder dies, so a supervisor killed mid-tick never
    leaves a marker that blocks the next fire (the idiom and its reason:
    synthbench/generate/window.py's `_window_lock`).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)


def _log_line(path: Path, line: str) -> None:
    """Append one line to the fire log, flushing so a killed run still leaves its start."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()


def _clock() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sbx_probe(host: Host, sandbox: str) -> None:
    """The two agent-dgx files the fire's flags point at must exist in the sandbox.

    Probed by the sandbox's own shell, one round-trip, at their absolute paths under the
    sandbox's HOME (`$HOME/.claude/agent-dgx/`): anything missing is refused before a
    tick runs, so a fire never guesses whether the files exist (ruling 259, item 2 - it
    refuses rather than guesses, as `up` and `retire` do; the `$HOME` expansion is the
    sandbox shell's, the same expansion the fire's flags get). A sandbox that cannot
    answer is not this check's subject: the fire hits the same wall one command later
    and its own handlers record the gap (`status=refused` for a failed connection,
    `killed=yes status=timeout` for a read that overruns the 120s cap).
    """
    argv = [
        "sbx",
        "exec",
        sandbox,
        "bash",
        "-lc",
        f'for f in {DGX_SETTINGS} {DGX_MCP}; do [ -f "$f" ] || echo "missing:$f"; done',
    ]
    try:
        done = host.run(argv, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        # A sandbox that cannot answer is not this check's subject: the fire hits the
        # same wall one command later and its own handler records the gap - `status=refused`
        # for an OSError, `killed=yes status=timeout` for an overrunning read. Refusing
        # here too would skip both log lines.
        return
    missing = [
        line.removeprefix("missing:")
        for line in done.stdout.splitlines()
        if line.startswith("missing:")
    ]
    if missing:
        quoted = ", ".join(m for m in missing)
        raise Refused(
            f"{sandbox} is missing the agent-dgx file(s) the fire mirrors the pane with "
            f"({quoted}). The pane was started with "
            "them; restore them inside the sandbox "
            "(agent-dgx recreated the session without them?) and run this again."
        )


def coordinator_session(host: Host) -> Session:
    """The coordinator's row from the manifest, which the fire runs inside.

    Read from the manifest rather than assumed: the row is what proves the session is
    declared and running before anything fires. Its `[models]` entry is `agent-dgx run`
    vocabulary - how the owner STARTS the pane - and is deliberately not on the fire's
    `claude` line (the fire carries the prompt and the pane's own three launch flags,
    per ruling 259; see `supervise`).
    """
    data = _load_toml(host.manifest)
    for sessions in _phases_of(data, host.manifest).values():
        for session in sessions:
            if session.name == COORDINATOR:
                return session
    raise Refused(
        f"{host.manifest} declares no {COORDINATOR} session, so there is no session to "
        "fire inside. Restore its row (scripts/uplevel/sandboxes.toml, Phase 0/1)."
    )


def supervise(host: Host, name: str, *, budget: int = TICK_BUDGET) -> None:
    """One timer fire: run the coordinator's tick once, inside its sandbox.

    A fire is a no-op that says so when the session is not running (exit 2, naming the
    command that starts it), when another fire holds the lock, and when the run itself was
    launched from a session's clone (as `up` and `retire` refuse; a fire from there would
    create `supervise/` in an agent-writable checkout). Otherwise it runs the tick prompt
    as a headless `claude -p` through `sbx exec` under `timeout <budget>` (the kill lives
    inside the sandbox; the host budget stays as the backstop), and appends one line
    carrying start, end, status, killed and the tick's own summary. A fire that cannot
    reach the sandbox is logged too - `status=refused` - so the log records the gap an
    absent line would hide.
    """
    if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
        raise Refused(
            f"--budget must be a positive integer (seconds before a running tick is "
            f"killed), not {budget!r}. Nothing was fired."
        )
    _check_owner_checkout(host)
    if name != COORDINATOR:
        raise Refused(
            f"supervise runs the coordinator's ticks only, and {name} is not {COORDINATOR}. "
            "Lanes, heavy agents and the operator keep their panes; whether the supervisor "
            "extends to them is the owner's decision after 48 hours ([r247], box 7)."
        )
    found = _session(host, name)
    if found is None or found.get("sandbox") is None:
        raise Refused(
            f"{name} is not running: there is no sandbox to fire a tick inside. Start it "
            f"with `agent-dgx run {name} --agent claude --split`, then run this again."
        )

    session = coordinator_session(host)
    prompt = tick_prompt()
    directory = host.checkout / SUPERVISE_DIR
    log = directory / f"{name}.log"
    # The fire mirrors the pane (ruling 259, #7248 Q1 answered with (a)): agent-dgx does
    # not start the pane on defaults - it runs `claude --dangerously-skip-permissions
    # --settings <dgx settings> --mcp-config <dgx mcp>` - and a bare headless `claude -p`
    # drops all three: without bypass permissions a headless tick cannot approve its own
    # tool calls, so it could not post, merge or update branches. The flags point at the
    # agent-dgx files inside the sandbox, the same files the pane was launched with; the
    # manifest row's arguments stay off the wire (`[models]` is `agent-dgx run`
    # vocabulary, not `claude` flags - measured: unknown option, rc 1 - and a
    # shell-injection seam had the row ever changed). The probe refuses rather than
    # guesses: a missing file is checked by the sandbox itself, not by a host-side guess
    # about its filesystem.
    _sbx_probe(host, session.sandbox)
    script = (
        f"timeout {budget} claude -p {shlex.quote(prompt)} "
        f"--dangerously-skip-permissions "
        f"--settings {DGX_SETTINGS} --mcp-config={DGX_MCP}"
    )
    argv = ["sbx", "exec", session.sandbox, "bash", "-lc", f"cd {session.workspace} && {script}"]

    if host.dry_run:
        _say(f"would fire {name}'s tick: {shlex.join(argv)}")
        _say(f"would append one line to {log} (start, end, status, killed, summary)")
        return

    with _tick_lock(directory / f"{name}.lock") as held:
        if not held:
            _log_line(log, f"{_clock()} {name} skipped: a tick is still running")
            _say(f"{name} is already running a tick: this fire is skipped")
            return

        started = _clock()
        _say(f"== fire {name}'s tick: {shlex.join(argv)}")
        killed = False
        status = "ok"
        summary = ""
        try:
            done = host.run(argv, capture_output=True, text=True, timeout=budget, check=False)
            # the tick's partial stdout is the summary even on a kill: what the tick was
            # printing when the budget caught it is the one diagnostic the log can carry
            summary = " ".join(str(done.stdout or "").split())[:300]
            if done.returncode == 124:
                # `timeout` killed the tick at the budget inside the sandbox
                killed, status = True, "timeout"
            else:
                status = "ok" if done.returncode == 0 else f"exit {done.returncode}"
        except subprocess.TimeoutExpired:
            # the host backstop: the sandbox itself stopped answering (the wrapper would
            # have killed claude in-sandbox at the same budget had it been reached)
            killed, status = True, "timeout"
        except OSError as error:
            ended = _clock()
            note = " ".join(str(error).split())[:300]
            _log_line(
                log,
                f"{started} {name} start={started} end={ended} status=refused "
                f"killed=no summary={shlex.quote(note)}",
            )
            raise Refused(
                f"could not fire {name}'s tick ({error}). Whether `sbx exec` still reaches "
                "the sandbox is this module header's open MEASURE; the session was left as "
                "it was."
            ) from error
        ended = _clock()
        _log_line(
            log,
            f"{started} {name} start={started} end={ended} status={status} "
            f"killed={'yes' if killed else 'no'} summary={shlex.quote(summary) if summary else '(none)'}",
        )
        _say(f"fired {name}: status={status} killed={'yes' if killed else 'no'}")


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
    sup_p = commands.add_parser(
        "supervise", help="one timer fire: run the coordinator's tick once, inside its sandbox"
    )
    sup_p.add_argument("name", help="the session to fire for ([r247]: uplevel-coordinator only)")
    sup_p.add_argument(
        "--budget",
        type=int,
        default=TICK_BUDGET,
        help=f"seconds before a running tick is killed (default {TICK_BUDGET})",
    )
    for sub in (up_p, retire_p, sup_p):
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
        elif args.command == "supervise":
            supervise(host, args.name, budget=args.budget)
        else:
            retire(host, args.name)
    except Refused as error:
        sys.stderr.write(f"uplevel launch: {error}\n")
        return EXIT_REFUSED
    return 0


if __name__ == "__main__":
    sys.exit(main())
