"""Uplevel O0.1: scripts/uplevel/launch.py, the sandbox launcher (UR-26, UR-28).

The owner creates agent sandboxes with `agent-dgx` (docs/uplevel/50-coordination.md,
"Where agents run"), which gives each session its own clone of the host checkout. This
launcher drives `agent-dgx` from scripts/uplevel/sandboxes.toml so a phase boundary is one
command, and retires sandboxes without losing work. It follows synthbench/host/agent.py,
which already drives agent-dgx from the host: every command goes through a Host seam,
--dry-run prints each step instead of running it, all checks run before any change, and a
refusal exits 2 naming the next step. The tests run against a fake host, as
backend/tests/unit/synthbench/test_host_agent.py does.

The command vocabulary is fixed by what the repo already shows (30-ops.md §O0.1:
synthbench/host/agent.py and docs/synthbench/operator-runbook.md): `agent-dgx run <name>
[--agent --endpoint --mount] --split`, `agent-dgx inspect <name> --json`, `agent-dgx stop
<name>`, `agent-dgx session rm <name> --force`, and `sbx exec <sandbox> bash -lc <script>`.
`agent-dgx` reads an unknown word as a new session's name, so every call names its
subcommand and nothing runs `agent-dgx help` or `agent-dgx ls` (operator-runbook.md).

The retirement tests pin the safety rules: git runs inside the sandbox through `sbx exec`,
never on the host against the workspace - its .git/config is the agent's to write, and
settings such as core.fsmonitor run commands (operator-runbook.md) - and the export (a
bundle plus a working-tree archive, streamed out through the same seam) is verified on the
host before anything is stopped or removed.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

# the identity these throwaway repos commit under (as test_vss_next_id.py does)
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}

REPO_ROOT = Path(__file__).resolve().parents[4]
_spec = importlib.util.spec_from_file_location(
    "uplevel_launch", REPO_ROOT / "scripts" / "uplevel" / "launch.py"
)
launch = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
# registered before exec: the module's @dataclass resolves its string annotations through
# sys.modules[cls.__module__], which is absent for a module loaded by path alone
sys.modules[_spec.name] = launch
_spec.loader.exec_module(launch)

MAIN_SHA = "a" * 40
BASE_SHA = "b" * 40
WIP_SHA = "c" * 40
SCRATCH = "uplevel-scratch"
SCRATCH_SANDBOX = "agent-uplevel-scratch"
BUNDLE_BYTES = b"fake bundle bytes"
TREE_BYTES = b"fake tree tar.gz bytes"

CO = "uplevel-coordinator"
OPS_A = "uplevel-ops-a"
OPS_B = "uplevel-ops-b"
BACKEND = "uplevel-backend"
FRONTEND = "uplevel-frontend"
DOCS = "uplevel-docs"
HEAVY = "uplevel-heavy"
OPERATOR = "uplevel-operator"

RUNNING = {"head": MAIN_SHA, "sandbox": "running"}
# the state the owner's inspect showed for a session whose agent's pane was closed: the
# sandbox record remains, reading "status": "stopped"
STOPPED = {"head": MAIN_SHA, "sandbox": "stopped"}
NO_SANDBOX = {"head": MAIN_SHA, "sandbox": None}
PUSHED = {"main": MAIN_SHA, "agent-branch": MAIN_SHA}

# what both the host checkout and a well-behaved agent's clone call `origin`
ORIGIN_URL = "https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence"


def remote_heads(mapping: dict[str, str]) -> str:
    """What `git ls-remote --heads origin` prints: one line per pushed branch."""
    return "".join(f"{sha}\trefs/heads/{name}\n" for name, sha in mapping.items())


def sections_body(**over: tuple[str, int]) -> str:
    """A fixture inspection output: every section, each overridden with (text, code)."""
    defaults: dict[str, tuple[str, int]] = {
        "dirty": ("", 0),
        "stash": ("", 0),
        "branch": ("main", 0),
        "head": (MAIN_SHA, 0),
        "refs": (f"{MAIN_SHA} refs/heads/main\n", 0),
        "remote": (remote_heads({"main": MAIN_SHA}), 0),
        "origin": (ORIGIN_URL, 0),
    }
    defaults.update(over)
    return "".join(
        f"{defaults[name][0]}\n{launch.MARKER} {name} {defaults[name][1]}\n"
        for name in launch.SECTION_NAMES
    )


class FakeHost:
    """Answers the read-only commands; records every call; fails the step named in `fail`.

    `sessions` maps a session name to its state before the run (a dict with `head` =
    manifest.source_repository.head and `sandbox` = "running" or None; an absent name has
    neither manifest nor sandbox). Once `agent-dgx run <name>` is seen, inspect reports the
    session created at `new_head`. The retirement inspection script is answered from the
    `ws` fixture, so the refusal tests are tests on fixture outputs.
    """

    def __init__(
        self,
        *,
        sessions: dict[str, dict[str, Any]] | None = None,
        checkout_head: str = MAIN_SHA,
        checkout_branch: str = "main",
        checkout_dirty: str = "",
        ws: dict[str, Any] | None = None,
        new_head: str = MAIN_SHA,
        fail: str | None = None,
        agents_root: Path | None = None,
        origin_url: str = ORIGIN_URL,
        checkout: Path | None = None,
    ) -> None:
        self.checkout = checkout
        self.sessions = sessions or {}
        self.checkout_head = checkout_head
        self.checkout_branch = checkout_branch
        self.checkout_dirty = checkout_dirty
        self.origin_url = origin_url
        self.ws = ws if ws is not None else {}
        self.new_head = new_head
        self.fail = fail
        self.agents_root = agents_root
        self.calls: list[tuple[list[str], Path | None]] = []

    def _stage(self, script: str, filename: str, data: bytes) -> tuple[int, str, str]:
        """An export step: write what the sandbox would leave in its own clone."""
        if self.agents_root is not None:
            sandbox = script.split("cd /agents/", 1)[1].split("/workspace", 1)[0]
            staged = self.agents_root / sandbox / "workspace" / launch.EXPORT_DIR
            staged.mkdir(parents=True, exist_ok=True)
            (staged / filename).write_bytes(data)
        return 0, "", ""

    def __call__(self, argv: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        argv = [str(a) for a in argv]
        self.calls.append((argv, kwargs.get("cwd")))
        joined = " ".join(argv)
        if self.fail and self.fail in joined:
            if kwargs.get("check"):
                raise subprocess.CalledProcessError(1, argv)
            return subprocess.CompletedProcess(argv, 1, "", "step failed")
        return subprocess.CompletedProcess(argv, *self._answer(argv, joined))

    def _answer(self, argv: list[str], joined: str) -> tuple[int, str, str]:
        # One table of commands in the order the launcher issues them, so the fake stays
        # a lookup; a `sbx exec` script answers through its own branch below.
        answer: tuple[int, str, str] | None = None
        if argv[:2] == ["agent-dgx", "inspect"]:
            answer = (0, json.dumps(self._inspect(argv[2])), "")
        elif argv[:2] == ["sbx", "exec"]:
            answer = self._sandbox(argv)
        elif "status" in argv and "--porcelain" in argv:
            answer = (0, (self.checkout_dirty + "\n") if self.checkout_dirty else "", "")
        elif "rev-parse" in argv and "--show-toplevel" in argv:
            # main() asks the checkout where its root is before it builds the real Host;
            # an empty answer here would become Path("") and point at the test runner's cwd
            answer = (0, str(self.checkout or (Path.cwd() / "checkout")) + "\n", "")
        elif "rev-parse" in argv and "origin/main" in joined:
            answer = (0, MAIN_SHA + "\n", "")
        elif "rev-parse" in argv and "--abbrev-ref" in argv:
            # before the HEAD case below: this read also names HEAD
            answer = (0, self.checkout_branch + "\n", "")
        elif "rev-parse" in argv and "HEAD" in joined:
            answer = (0, self.checkout_head + "\n", "")
        elif "get-url" in argv:
            answer = (0, self.origin_url + "\n", "")
        elif "bundle" in argv and "verify" in argv:
            answer = (0, "the bundle requires this ref\n", "")
        elif argv[:2] == ["tar", "-tzf"]:
            answer = (0, "worktree.tar.gz listing\n", "")
        return answer or (0, "", "")

    def _sandbox(self, argv: list[str]) -> tuple[int, str, str]:
        script = argv[-1]
        if launch.MARKER in script:
            return self._inspection(script)
        # The export steps really do write into the session's own clone, because the
        # launcher reads them back off the host's mount afterwards (synthbench's `down`
        # copies workspace files the same way).
        if "bundle create" in script:
            return self._stage(script, f"{argv[2].removeprefix('agent-')}.bundle", BUNDLE_BYTES)
        if "tar" in script:
            return self._stage(script, "worktree.tar.gz", TREE_BYTES)
        return (0, "", "")

    def _inspect(self, name: str) -> dict[str, Any]:
        if self.ran("agent-dgx", "run", name):
            return {
                "id": name,
                "manifest": {"source_repository": {"head": self.new_head}, "status": "prepared"},
                "sandbox": {"status": "running"},
            }
        state = self.sessions.get(name)
        if state is None:
            return {"id": name, "manifest": None, "sandbox": None}
        sandbox = None if state.get("sandbox") is None else {"status": state["sandbox"]}
        return {
            "id": name,
            "manifest": {"source_repository": {"head": state["head"]}, "status": "prepared"},
            "sandbox": sandbox,
        }

    def _inspection(self, script: str) -> tuple[int, str, str]:
        """Answer the retirement inspection script from the `ws` fixture."""
        refs = self.ws.get("refs")
        texts: dict[str, str] = {
            "dirty": self.ws.get("dirty", ""),
            "stash": self.ws.get("stash", ""),
            "branch": self.ws.get("branch", "main"),
            "head": self.ws.get("head", MAIN_SHA),
            "refs": "".join(f"{sha} refs/heads/{name}\n" for name, sha in (refs or {}).items()),
            "remote": self.ws.get("remote", remote_heads({"main": MAIN_SHA})),
            "origin": self.ws.get("origin", ORIGIN_URL),
        }
        codes: dict[str, int] = self.ws.get("codes", {})
        body, failed = "", 0
        for name in launch.SECTION_NAMES:
            if f"say {name} " not in script:
                continue
            code = codes.get(name, 0)
            failed = failed or code
            body += f"{texts[name]}\n{launch.MARKER} {name} {code}\n"
        return failed, body, ""

    def ran(self, *prefix: str) -> bool:
        return any(argv[: len(prefix)] == list(prefix) for argv, _ in self.calls)

    def changes(self) -> list[list[str]]:
        """Every call that changes something: not a read, not a check."""
        return [argv for argv, _ in self.calls if not self._is_read(argv)]

    @staticmethod
    def _is_read(argv: list[str]) -> bool:
        # Each test asserts against this list: `changes()` is everything left over. The
        # retirement inspection script only reads, while the export scripts write, so
        # only the MARKER-bearing `sbx exec` counts as a read.
        checks = (
            argv[:2] == ["agent-dgx", "inspect"],
            "rev-parse" in argv,
            # reading the host checkout's own remote URL changes nothing
            "remote" in argv and "get-url" in argv,
            # a fetch moves only a remote-tracking ref: never the worktree or a branch
            argv[:2] == ["git", "-C"] and "fetch" in argv,
            "status" in argv and "--porcelain" in argv,
            "bundle" in argv and "verify" in argv,
            argv[:2] == ["tar", "-tzf"],
            argv[:2] == ["sbx", "exec"] and launch.MARKER in " ".join(argv),
        )
        return any(checks)


def host(
    tmp_path: Path,
    fake: FakeHost,
    *,
    dry_run: bool = False,
    herdr: bool = True,
    gpu_runner: bool = True,
    manifest: Path | None = None,
    host_class: Any = launch.Host,
) -> launch.Host:
    # `host_class` defaults to the real dataclass, but a test that patches launch.Host (to
    # drive main(), which builds its own) passes the class captured *before* the patch -
    # otherwise this helper calls the patch and the patch calls this helper.
    # the host's view of each session's clone (the real /agents is root-owned and absent
    # in a test run); the fake writes the export there, as the sandbox really would
    if fake.agents_root is None:
        fake.agents_root = tmp_path / "agents"
    env: dict[str, str] = {}
    if herdr:
        env["HERDR_PANE_ID"] = "w1:p1"
    if gpu_runner:
        # the shell's handle on `agent-gpu`'s runner (30-ops.md §O1.10 names the
        # variable; 50-coordination.md, "Where agents run", is where the runner
        # itself is described); O1.10 makes the launcher require it before it hands
        # any sandbox `--gpu`
        env["AGENT_GPU_RUNNER_URL"] = "http://127.0.0.1:8100"
    return host_class(
        checkout=tmp_path / "checkout",
        manifest=manifest or REPO_ROOT / "scripts" / "uplevel" / "sandboxes.toml",
        exports=tmp_path / "exports",
        agents_root=fake.agents_root,
        run=fake,
        env=env,
        which=lambda name: f"/usr/bin/{name}",
        dry_run=dry_run,
    )


# --------------------------------------------------------------- the manifest


def test_manifest_declares_the_roster() -> None:
    """sandboxes.toml declares each phase's sessions as 50-coordination.md's roster does.
    Later phases are the coordinator's to add; the launcher reads what is declared."""
    phases = launch.load_manifest(REPO_ROOT / "scripts" / "uplevel" / "sandboxes.toml")
    assert sorted(phases) == [0, 1]
    assert [s.name for s in phases[0]] == [CO, OPS_B]
    assert {s.name for s in phases[1]} == {
        CO,
        OPS_A,
        OPS_B,
        BACKEND,
        FRONTEND,
        DOCS,
        HEAVY,
        OPERATOR,
    }


def test_sandbox_and_workspace_names_follow_agent_dgx() -> None:
    """The sandbox is `agent-<name>`; its clone is /agents/agent-<name>/workspace."""
    session = launch.Session(name=OPS_B, model="fast", kickoff="k")
    assert session.sandbox == "agent-uplevel-ops-b"
    assert session.workspace == "/agents/agent-uplevel-ops-b/workspace"


def test_split_lane_kickoff_carries_the_cell_sentence() -> None:
    """50-coordination.md "Split lanes": a split lane's kickoff line carries one more
    sentence, so an agent never claims a package outside its cell."""
    phases = launch.load_manifest(REPO_ROOT / "scripts" / "uplevel" / "sandboxes.toml")
    lines = {s.name: s.kickoff for s in phases[1]}
    for name, cell in ((OPS_A, "A"), (OPS_B, "B")):
        assert lines[name].startswith("Follow the kickoff prompt in docs/uplevel/30-ops.md.")
        assert f"You are cell {cell} of the ops lane" in lines[name]
    assert lines[CO].startswith("Follow the kickoff prompt in docs/uplevel/50-coordination.md.")
    assert "cell" not in lines[BACKEND]


def test_operator_is_the_only_gpu_session_in_every_phase() -> None:
    """UR-30: exactly one GPU holder. agent-gpu's runner admits the GPU sandbox and
    `agent-dgx --gpu` owns /srv/agent-models; a second gpu row somewhere later is the
    bug this pins, so the rule runs over every declared phase, not just the one that
    has the operator today."""
    phases = launch.load_manifest(REPO_ROOT / "scripts" / "uplevel" / "sandboxes.toml")
    for number, sessions in phases.items():
        gpu = {s.name for s in sessions if s.gpu}
        assert gpu == (set() if number == 0 else {OPERATOR}), f"phase {number}"


def test_the_operator_row_declares_no_mount() -> None:
    """The launcher adds no --mount for the model library: agent-dgx --gpu mounts
    /srv/agent-models itself and refuses any mount at or under it, so a mount on this
    row would hand the owner an agent-dgx-level failure at create time."""
    phases = launch.load_manifest(REPO_ROOT / "scripts" / "uplevel" / "sandboxes.toml")
    operator = next(s for s in phases[1] if s.name == OPERATOR)
    assert operator.mounts == ()


def test_operator_kickoff_names_the_prompt_section_not_a_position() -> None:
    """30-ops.md §O1.10 wrote this line positionally ("at the end of the file"). #6864's
    ruling applies unchanged - `up` prints the line verbatim, so it names its section,
    never a position - and operator.md has one kickoff prompt in its own file, which the
    cross-check below pins. Ruling 13 (2026-10-08) routes the plan-text correction into
    this PR: the 30-ops.md line now names the section too, same wording as this row."""
    phases = launch.load_manifest(REPO_ROOT / "scripts" / "uplevel" / "sandboxes.toml")
    line = {s.name: s.kickoff for s in phases[1]}[OPERATOR]
    assert line.startswith("Follow the kickoff prompt in docs/uplevel/operator.md.")
    assert "Kickoff prompt" in line
    assert "end of" not in line


@pytest.mark.skipif(
    # operator.md is a docs/ path, outside mutmut's also_copy: in the mutant home the
    # read would raise and abort the -x stats gather (the also_copy abort family).
    # Skip, never abort - the doctrine test_check_vss_docs_currency.py:508 states and
    # test_notify_reachability_guard.py's mutant-home skipif argues at length.
    not (REPO_ROOT / "docs" / "uplevel" / "operator.md").exists(),
    reason="docs/ tree absent (mutmut's mutant home): nothing to cross-check the line against",
)
def test_operator_md_holds_the_section_the_line_names() -> None:
    """the section the operator line names exists - the drift a positional pointer hid
    for the heavy sandbox (#6864): rename it, and the printed line points at nothing."""
    doc = (REPO_ROOT / "docs" / "uplevel" / "operator.md").read_text(encoding="utf-8")
    assert "## Kickoff prompt" in doc


def test_the_mutant_home_shape_skips_the_docs_read_and_keeps_the_rest_alive(
    tmp_path: Path,
) -> None:
    """The guarded skip above is only honest if the mutant home really still runs the
    rest. mutmut copies backend/ and scripts/ but never docs/, so in that home the
    cross-check must SKIP (aborting the -x stats gather is the registered abort family)
    while every string/flag assert stays live and killable. This builds that shape - this
    very file, the launcher, the manifest, and no docs/ - and runs the file's operator
    and gpu tests inside it. Contract rule 3: the harness lives here, in the repo, not
    in someone's /tmp. No recursion: the inner -k names no part of this test's name, so
    the copy never re-runs it - and the test carries no suppression marker, so the
    census has nothing to count."""
    sim = tmp_path / "home"
    scripts = sim / "scripts" / "uplevel"
    tests = sim / "backend" / "tests" / "unit" / "scripts"
    scripts.mkdir(parents=True)
    tests.mkdir(parents=True)
    (scripts / "launch.py").write_text(
        (REPO_ROOT / "scripts" / "uplevel" / "launch.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (scripts / "sandboxes.toml").write_text(
        (REPO_ROOT / "scripts" / "uplevel" / "sandboxes.toml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    copied = tests / "test_uplevel_launch.py"
    # nosemgrep: path-traversal-open - this test file's own path, not user input
    copied.write_text(Path(__file__).read_text(encoding="utf-8"), encoding="utf-8")

    done = subprocess.run(  # real: runs this file's copy inside a docs-less tree  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            str(copied),
            "-q",
            "-o",
            "addopts=",
            "-p",
            "no:randomly",
            "-k",
            "operator or gpu",
        ],
        cwd=sim,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,  # a nonzero inner run IS the evidence: the assert prints its output
    )
    out = done.stdout + done.stderr
    assert done.returncode == 0, out
    assert "1 skipped" in out, out  # the guarded cross-check, skipping not aborting
    assert "failed" not in out and " error" not in out, out
    summary = next(line for line in out.splitlines() if " passed" in line)
    passed = int(summary.partition(" passed")[0].rsplit(maxsplit=1)[-1])
    assert passed >= 8, f"the string/flag asserts must stay live in the mutant home: {out}"


def test_a_non_boolean_gpu_flag_refuses_naming_the_row(tmp_path: Path) -> None:
    """`gpu` is optional, so a typo on it is not caught by the required-key refusals -
    and silently truthy ("gpu = 1") would hand a sandbox the GPU by accident, the one
    resource UR-30 rationed to one holder."""
    manifest = tmp_path / "m.toml"
    manifest.write_text(
        "[[phase]]\nnumber = 0\n"
        f'[[phase.session]]\nname = "{OPERATOR}"\nmodel = "fast"\nkickoff = "k"\ngpu = 1\n',
        encoding="utf-8",
    )
    # pinned to the naming, not the word `gpu`: the refusal's promise is that it names
    # which row is wrong, and `match="gpu"` passes on a message that names nothing (the
    # literal `gpu = 1` is in it either way).
    with pytest.raises(launch.Refused, match=f"session {OPERATOR}") as caught:
        launch.load_manifest(manifest)
    assert str(manifest) in str(caught.value)


def test_a_gpu_row_mounting_the_model_library_refuses(tmp_path: Path) -> None:
    """30-ops.md §O1.10 states agent-dgx's rule: --gpu mounts /srv/agent-models itself
    and refuses any mount at or under it. A hand-written row that collides with the
    library fails at create time inside agent-dgx; the launcher's doctrine is to refuse
    first, naming the row."""
    manifest = tmp_path / "m.toml"
    manifest.write_text(
        "[[phase]]\nnumber = 0\n"
        f'[[phase.session]]\nname = "{OPERATOR}"\nmodel = "fast"\nkickoff = "k"\n'
        'gpu = true\nmount = ["/srv/agent-models:ro"]\n',
        encoding="utf-8",
    )
    with pytest.raises(launch.Refused, match="agent-models"):
        launch.load_manifest(manifest)


def test_a_gpu_row_may_mount_elsewhere(tmp_path: Path) -> None:
    """The rule is about the library path, not mounts in general: a mount outside
    /srv/agent-models is unaffected by what --gpu brings, and refusing it would be the
    launcher inventing a rule the plan does not state."""
    manifest = tmp_path / "m.toml"
    manifest.write_text(
        "[[phase]]\nnumber = 0\n"
        f'[[phase.session]]\nname = "{OPERATOR}"\nmodel = "fast"\nkickoff = "k"\n'
        'gpu = true\nmount = ["/stack/shared:ro"]\n',
        encoding="utf-8",
    )
    fake = FakeHost()
    launch.up(host(tmp_path, fake, manifest=manifest), phase=0)
    run = next(argv for argv, _ in fake.calls if argv[:3] == ["agent-dgx", "run", OPERATOR])
    assert run == [
        "agent-dgx",
        "run",
        OPERATOR,
        "--agent",
        "claude",
        "--endpoint",
        "dgx",
        "--mount",
        "/stack/shared:ro",
        "--gpu",
        "--split",
    ]


def test_a_phase_repeating_a_session_name_refuses(tmp_path: Path) -> None:
    """Two rows for one name is a hand-edit the launcher cannot honour. `up` gathers each
    name's state once before any change (the gpu grant must be knowable up front), so two
    same-name rows would both read "missing" and both create - two sandboxes, and two
    `--gpu` grants where UR-30 allows one. `main` re-inspected per row and so printed
    "already exists" for the second only by accident - it was never the rule. The answer
    is this launcher's own idiom for a hand-edit typo: refuse, naming the phase and the
    repeated name, before any change."""
    manifest = tmp_path / "m.toml"
    manifest.write_text(
        "[[phase]]\nnumber = 1\n"
        '[[phase.session]]\nname = "dup"\nmodel = "fast"\nkickoff = "k"\n'
        "[[phase]]\nnumber = 1\n"
        '[[phase.session]]\nname = "dup"\nmodel = "fast"\nkickoff = "k"\n',
        encoding="utf-8",
    )
    with pytest.raises(launch.Refused, match="phase 1"):
        launch.load_manifest(manifest)


def test_the_repeated_name_is_the_one_named(tmp_path: Path) -> None:
    """The refusal names which session is duplicated, not just the phase - a coordinator
    editing a long roster needs the row, not a line to go look for."""
    manifest = tmp_path / "m.toml"
    manifest.write_text(
        "[[phase]]\nnumber = 2\n"
        '[[phase.session]]\nname = "uplevel-backend"\nmodel = "fast"\nkickoff = "k"\n'
        '[[phase.session]]\nname = "uplevel-backend"\nmodel = "fast"\nkickoff = "k"\n',
        encoding="utf-8",
    )
    with pytest.raises(launch.Refused, match="uplevel-backend"):
        launch.load_manifest(manifest)


def test_the_same_name_may_reappear_in_different_phases(tmp_path: Path) -> None:
    """A name is only unique within a phase: the roster reuses uplevel-coordinator and
    uplevel-ops-b across phases 0 and 1 (the launcher creates each phase's members at its
    own boundary). A uniqueness check that spanned phases would refuse the real roster."""
    manifest = tmp_path / "m.toml"
    manifest.write_text(
        "[[phase]]\nnumber = 0\n"
        '[[phase.session]]\nname = "shared"\nmodel = "fast"\nkickoff = "k"\n'
        "[[phase]]\nnumber = 1\n"
        '[[phase.session]]\nname = "shared"\nmodel = "fast"\nkickoff = "k"\n',
        encoding="utf-8",
    )
    phases = launch.load_manifest(manifest)
    assert [s.name for s in phases[0]] == ["shared"]
    assert [s.name for s in phases[1]] == ["shared"]


def test_heavy_kickoff_names_the_heavy_prompt_instead_of_a_position() -> None:
    """50-coordination.md holds TWO prompts and ends with the coordinator's, so a heavy line
    pointing at "the prompt at the end of that file" hands uplevel-heavy the coordinator's job
    - route work, write no product code - the opposite of the UR-24 package it is started for.
    `up` prints the line verbatim, so it has to name the section it means."""
    phases = launch.load_manifest(REPO_ROOT / "scripts" / "uplevel" / "sandboxes.toml")
    line = {s.name: s.kickoff for s in phases[1]}[HEAVY]
    assert "The heavy sandbox's kickoff prompt" in line
    assert "end of that file" not in line


@pytest.mark.skipif(
    # the roster is a docs/ path and docs/uplevel/ sits outside mutmut's also_copy (its
    # comment: docs/ as a whole is never copied): in the mutant home this read would raise
    # and abort the -x stats gather - the also_copy abort family, pyproject.toml. Skip,
    # never abort, as test_check_vss_docs_currency.py and test_mutation_hold_banner.py do.
    not (REPO_ROOT / "docs" / "uplevel" / "50-coordination.md").exists(),
    reason="docs/ tree absent (mutmut's mutant home): nothing to cross-check the line against",
)
def test_the_roster_holds_both_prompts_the_heavy_line_points_between() -> None:
    """the sections the heavy line names all exist, and there are TWO kickoff prompts in the
    file - which is exactly why the line has to name its section instead of a position."""
    roster = (REPO_ROOT / "docs" / "uplevel" / "50-coordination.md").read_text(encoding="utf-8")
    assert "### The roster" in roster
    assert "**The heavy sandbox's kickoff prompt:**" in roster
    assert "## Coordinator kickoff prompt" in roster


def test_an_unnamed_model_refuses_and_names_the_owners_next_step(tmp_path: Path) -> None:
    """The strongest model's run arguments are the owner's to post (PR #6855). The launcher
    refuses naming that, and never invents a flag (30-ops.md §O0.1, first item)."""
    manifest = tmp_path / "m.toml"
    manifest.write_text(
        "[[phase]]\nnumber = 9\n"
        f'[[phase.session]]\nname = "{HEAVY}"\nmodel = "strongest"\nkickoff = "k"\n',
        encoding="utf-8",
    )
    # one read, passed down - the shape up() uses, so [models] and the phase rows the
    # launcher acts on always come from the same content.
    data = launch._load_toml(manifest)
    phases = launch._phases_of(data, manifest)
    with pytest.raises(launch.Refused, match="owner"):
        launch.run_args_for(data, manifest, phases[9][0])


def test_manifest_models_override_the_builtin_fast(tmp_path: Path) -> None:
    """[models] holds the owner's arguments once posted; the builtin fast is the pair the
    repo already shows (synthbench/host/agent.py, operator-runbook.md)."""
    manifest = tmp_path / "m.toml"
    manifest.write_text(
        '[models]\nfast = "--agent claude --endpoint dgx --fast-profile x"\n'
        "[[phase]]\nnumber = 0\n"
        f'[[phase.session]]\nname = "{CO}"\nmodel = "fast"\nkickoff = "k"\n',
        encoding="utf-8",
    )
    data = launch._load_toml(manifest)
    phases = launch._phases_of(data, manifest)
    assert launch.run_args_for(data, manifest, phases[0][0]) == [
        "--agent",
        "claude",
        "--endpoint",
        "dgx",
        "--fast-profile",
        "x",
    ]


@pytest.mark.parametrize(
    ("row", "missing"),
    [
        # the coordinator hand-edits this file ("the coordinator adds rows as the plan
        # changes"), so a row with a key missing is the expected failure, not a bug.
        ('[[phase]]\nnumber = 0\n[[phase.session]]\nname = "s"\nkickoff = "k"\n', "model"),
        ('[[phase]]\nnumber = 0\n[[phase.session]]\nname = "s"\nmodel = "fast"\n', "kickoff"),
        ('[[phase]]\n[[phase.session]]\nname = "s"\nmodel = "fast"\nkickoff = "k"\n', "number"),
    ],
)
def test_a_malformed_manifest_refuses_naming_the_missing_key(
    tmp_path: Path, row: str, missing: str
) -> None:
    """Every other manifest failure raises Refused; a bare KeyError traceback would be
    exit 1 and name nothing (synthbench/host/agent.py: exit 2 naming the next step)."""
    manifest = tmp_path / "m.toml"
    manifest.write_text(row, encoding="utf-8")
    with pytest.raises(launch.Refused, match=f"has no `{missing}`"):
        launch.load_manifest(manifest)


def test_a_phase_number_that_is_not_a_number_refuses(tmp_path: Path) -> None:
    manifest = tmp_path / "m.toml"
    manifest.write_text(
        '[[phase]]\nnumber = "one"\n'
        f'[[phase.session]]\nname = "{CO}"\nmodel = "fast"\nkickoff = "k"\n',
        encoding="utf-8",
    )
    with pytest.raises(launch.Refused, match="whole number"):
        launch.load_manifest(manifest)


# ---------------------------------------------------------------------- up


def test_up_outside_herdr_refuses_before_anything(tmp_path: Path) -> None:
    """`agent-dgx run --split` opens the agent in a new herdr pane beside the launcher's,
    so the launcher has to be running in one (as synthbench's `up` checks)."""
    fake = FakeHost()
    with pytest.raises(launch.Refused, match="herdr"):
        launch.up(host(tmp_path, fake, herdr=False), phase=0)
    assert fake.calls == []


def test_up_refuses_a_dirty_host_checkout(tmp_path: Path) -> None:
    """agent-dgx copies uncommitted changes into the clone (50-coordination.md)."""
    fake = FakeHost(checkout_dirty=" M setup.py")
    with pytest.raises(launch.Refused, match="uncommitted"):
        launch.up(host(tmp_path, fake), phase=0)
    assert not fake.changes()


def test_up_refuses_a_stale_host_checkout(tmp_path: Path) -> None:
    """Every agent starts from a clean host checkout of main (50-coordination.md)."""
    fake = FakeHost(checkout_head=BASE_SHA)
    with pytest.raises(launch.Refused, match=BASE_SHA[:8]):
        launch.up(host(tmp_path, fake), phase=0)
    assert not fake.changes()


def test_up_refuses_when_the_fetch_fails(tmp_path: Path) -> None:
    """The at-origin/main check is worthless against a stale ref, so a failed fetch is a
    refusal, not a shrug (`check=False` once meant the launcher could create sandboxes at
    a commit main had moved past). A fetch moves only a remote-tracking ref."""
    fake = FakeHost(fail="fetch")
    with pytest.raises(launch.Refused, match="fetch"):
        launch.up(host(tmp_path, fake), phase=0)
    assert not fake.changes()
    assert not fake.ran("agent-dgx", "run")


@pytest.mark.parametrize(
    ("branch", "wording"),
    [
        # the exact hazard: same commit as origin/main, wrong branch. The sha check alone
        # would pass; agent-dgx copies the checkout, so the agent would start on the branch.
        ("uplevel/B1.4-x", r"on branch uplevel/B1\.4-x, not on main"),
        ("HEAD", r"at a detached HEAD, not on main"),
    ],
)
def test_up_refuses_a_host_checkout_on_another_branch(
    tmp_path: Path, branch: str, wording: str
) -> None:
    """Every agent starts from a clean host checkout of *main* (50-coordination.md) - the
    branch is part of the rule, not only its commit."""
    fake = FakeHost(checkout_branch=branch, checkout_head=MAIN_SHA)
    with pytest.raises(launch.Refused, match=wording):
        launch.up(host(tmp_path, fake), phase=0)
    assert not fake.changes()


def test_up_refuses_the_whole_phase_when_a_model_is_unresolvable(tmp_path: Path) -> None:
    """Every check runs before any change: a phase with one session whose model has no
    [models] entry refuses the whole run - the fast sessions in that phase are not created
    either - naming the owner's next step. Its own manifest, so the rule holds whatever
    the real roster's [models] holds (since #6855 the owner has posted `strongest`)."""
    manifest = tmp_path / "m.toml"
    manifest.write_text(
        '[models]\nfast = "--agent claude --endpoint dgx"\n'
        "[[phase]]\nnumber = 0\n"
        f'[[phase.session]]\nname = "{CO}"\nmodel = "fast"\nkickoff = "k"\n'
        f'[[phase.session]]\nname = "{HEAVY}"\nmodel = "strongest"\nkickoff = "k"\n',
        encoding="utf-8",
    )
    fake = FakeHost()
    with pytest.raises(launch.Refused, match="owner"):
        launch.up(host(tmp_path, fake, manifest=manifest), phase=0)
    assert not fake.changes()
    assert not fake.ran("agent-dgx", "run")


def test_the_rosters_strongest_row_is_the_owners_ruling() -> None:
    """The owner's ruling on #6855, pinned: no --endpoint (Claude Code's own upstream -
    the Anthropic API, not DGX-served), no --model (Claude Code's default model). This
    assertion is the tripwire if either is ever restated."""
    phases = launch.load_manifest(REPO_ROOT / "scripts" / "uplevel" / "sandboxes.toml")
    heavy = next(s for s in phases[1] if s.name == HEAVY)
    data = launch._load_toml(REPO_ROOT / "scripts" / "uplevel" / "sandboxes.toml")
    assert launch.run_args_for(
        data, REPO_ROOT / "scripts" / "uplevel" / "sandboxes.toml", heavy
    ) == ["--agent", "claude"]


def test_up_creates_each_missing_session_from_the_checkout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeHost(sessions={CO: RUNNING})
    h = host(tmp_path, fake)
    launch.up(h, phase=0)

    runs = [(argv, cwd) for argv, cwd in fake.calls if argv[:3] == ["agent-dgx", "run", OPS_B]]
    assert runs == [
        (
            ["agent-dgx", "run", OPS_B, "--agent", "claude", "--endpoint", "dgx", "--split"],
            h.checkout,
        )
    ]
    assert not fake.ran("agent-dgx", "run", CO)  # already there, at the right commit
    out = capsys.readouterr().out
    # the kickoff line prints for what it created, not for what was already running
    assert out.count("Follow the kickoff prompt") == 1


def test_up_passes_a_declared_mount_to_agent_dgx(tmp_path: Path) -> None:
    """50-coordination.md gives the backend sandbox Docker "for the fake stack"; if a
    session needs a host path agent-dgx mounts it with --mount (shown at
    synthbench/host/agent.py:248). The launcher passes each declared mount through, in
    order, before --split. sandboxes.toml declares none today - no shown flag takes a
    network profile or a secret, so nothing invents one."""
    manifest = tmp_path / "m.toml"
    manifest.write_text(
        "[[phase]]\nnumber = 0\n"
        f'[[phase.session]]\nname = "{BACKEND}"\nmodel = "fast"\nkickoff = "k"\n'
        'mount = ["/stack/shared:ro", "/stack/secrets:ro"]\n',
        encoding="utf-8",
    )
    fake = FakeHost()
    h = host(tmp_path, fake, manifest=manifest)
    launch.up(h, phase=0)

    run = next(argv for argv, _ in fake.calls if argv[:3] == ["agent-dgx", "run", BACKEND])
    assert run == [
        "agent-dgx",
        "run",
        BACKEND,
        "--agent",
        "claude",
        "--endpoint",
        "dgx",
        "--mount",
        "/stack/shared:ro",
        "--mount",
        "/stack/secrets:ro",
        "--split",
    ]


def test_up_adds_gpu_to_the_operator_and_no_other_session(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The Done-when, run the way the owner runs it: `up --phase 1 --dry-run` against the
    real roster. `--gpu` goes after the model arguments and before --split - the order
    30-ops.md's hand-start line shows the owner use - and it appears on exactly one line.
    --dry-run because the flag must be visible in what the command would run, and a dry
    run changes nothing on a machine that may have real sessions up."""
    fake = FakeHost()
    launch.up(host(tmp_path, fake, dry_run=True), phase=1)
    out = capsys.readouterr().out

    lines = [line for line in out.splitlines() if "agent-dgx run" in line]
    # derive the expected count from the manifest, not a literal: the roster grows when
    # the coordinator opens uplevel-heavy-2 (sandboxes.toml announces it), and a hardcoded
    # 8 would then fail here *and* in test_manifest_declares_the_roster for one edit.
    expected = launch.load_manifest(REPO_ROOT / "scripts" / "uplevel" / "sandboxes.toml")[1]
    assert len(lines) == len(expected), out  # every session's line present, nothing filtered
    operator = next(line for line in lines if OPERATOR in line)
    assert operator.split().index("--gpu") == operator.split().index("--split") - 1
    assert operator.endswith(f"--split   (in {tmp_path / 'checkout'})")
    assert "--mount" not in operator
    # The owner's ruled form, whole, not just the flag's position: "the flag is exactly
    # `--gpu`, and the operator's line keeps `--split`" (#6854, 2026-10-08, from the
    # stack repo's docs/operations/agent-gpu-runner.md, checked live). Position asserts
    # alone would pass on a line that had grown an extra flag, so pin the whole prefix.
    # the dry-run line prints "would create <name>: <command>  (in <cwd>)"
    command = operator.split(": ", 1)[1]
    tokens = command.split()
    assert " ".join(tokens[: tokens.index("--split") + 1]) == (
        "agent-dgx run uplevel-operator --agent claude --endpoint dgx --gpu --split"
    ), operator
    assert sum("--gpu" in line for line in lines) == 1, lines


def test_up_refuses_a_gpu_phase_without_the_gpu_runner(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--gpu` reaches a sandbox through agent-gpu's runner; without AGENT_GPU_RUNNER_URL
    in the launching shell there is no runner to reach, so the flag would be a promise
    nothing honours. The check joins the others ahead of every change: the seven fast
    sessions in the phase are not created either. The refusal names the variable, which
    is the next thing the owner types."""
    fake = FakeHost()
    with pytest.raises(launch.Refused, match="AGENT_GPU_RUNNER_URL") as caught:
        launch.up(host(tmp_path, fake, gpu_runner=False), phase=1)
    assert not fake.changes()
    assert not fake.ran("agent-dgx", "run")
    assert "uplevel-operator" in str(caught.value)
    assert "created" not in capsys.readouterr().out


def test_a_gpu_session_already_up_needs_no_runner(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The check belongs to a create, not to the command: the owner hand-started
    uplevel-operator for Phase 1 (UR-30), so from Phase 1's boundary on `up` normally
    finds it already there - nothing to grant - and a shell without the runner still
    reports the roster instead of refusing. Distinguishing the two is the same rule as
    the commit check's "for what this run creates"."""
    started = dict.fromkeys((CO, OPS_A, OPS_B, BACKEND, FRONTEND, DOCS, HEAVY, OPERATOR), RUNNING)
    fake = FakeHost(sessions=started)
    launch.up(host(tmp_path, fake, gpu_runner=False), phase=1)  # no refusal
    assert not fake.changes()
    assert "AGENT_GPU_RUNNER_URL" not in capsys.readouterr().out


def test_up_passes_gpu_for_a_declared_session(tmp_path: Path) -> None:
    """The rule as a rule, not as this roster's shape: a session declaring gpu = true
    gets --gpu; the clause is about what a declaration does, and a future phase's row is
    exactly as much its subject as the operator's."""
    manifest = tmp_path / "m.toml"
    manifest.write_text(
        "[[phase]]\nnumber = 0\n"
        f'[[phase.session]]\nname = "{OPERATOR}"\nmodel = "fast"\nkickoff = "k"\ngpu = true\n',
        encoding="utf-8",
    )
    fake = FakeHost()
    launch.up(host(tmp_path, fake, manifest=manifest), phase=0)
    run = next(argv for argv, _ in fake.calls if argv[:3] == ["agent-dgx", "run", OPERATOR])
    assert run == [
        "agent-dgx",
        "run",
        OPERATOR,
        "--agent",
        "claude",
        "--endpoint",
        "dgx",
        "--gpu",
        "--split",
    ]


def test_a_missing_runner_still_refuses_a_dry_run(tmp_path: Path) -> None:
    """--dry-run prints the plan; a plan ending in a flag nothing honours is not a plan.
    The same reason retire's dry run really runs its inspection: the checks are not
    skipped for the preview, so the preview cannot promise what the run refuses."""
    manifest = tmp_path / "m.toml"
    manifest.write_text(
        "[[phase]]\nnumber = 0\n"
        f'[[phase.session]]\nname = "{OPERATOR}"\nmodel = "fast"\nkickoff = "k"\ngpu = true\n',
        encoding="utf-8",
    )
    fake = FakeHost()
    with pytest.raises(launch.Refused, match="AGENT_GPU_RUNNER_URL"):
        launch.up(host(tmp_path, fake, manifest=manifest, gpu_runner=False, dry_run=True), phase=0)
    assert fake.changes() == []


def test_up_is_idempotent(tmp_path: Path) -> None:
    """Re-running creates only what is missing."""
    fake = FakeHost(sessions={CO: RUNNING, OPS_B: RUNNING})
    launch.up(host(tmp_path, fake), phase=0)
    launch.up(host(tmp_path, fake), phase=0)
    assert not fake.ran("agent-dgx", "run")
    assert not fake.changes()


def test_up_refuses_a_session_cloned_from_the_wrong_commit(tmp_path: Path) -> None:
    """agent-dgx clones whatever the checkout held, so the new manifest's source commit is
    checked all the same (as synthbench's `up` does). It refuses naming the owner's next
    step; it does not remove what it just created - that is `retire`'s job."""
    fake = FakeHost(sessions={CO: RUNNING}, new_head=BASE_SHA)
    with pytest.raises(launch.Refused, match=BASE_SHA[:8]):
        launch.up(host(tmp_path, fake), phase=0)
    assert not fake.ran("agent-dgx", "stop")
    assert not fake.ran("agent-dgx", "session", "rm")


def test_up_leaves_an_existing_session_at_an_older_commit_alone(tmp_path: Path) -> None:
    """The commit check is for what `up` creates (30-ops.md §O0.1): an agent keeps its
    session while main moves on. `up` neither recreates it nor removes it - retirement
    goes through `retire`, which checks for work first."""
    fake = FakeHost(sessions={CO: {"head": BASE_SHA, "sandbox": "running"}})
    launch.up(host(tmp_path, fake), phase=0)
    assert not fake.ran("agent-dgx", "run", CO)
    assert not fake.ran("agent-dgx", "stop")
    assert not fake.ran("agent-dgx", "session", "rm")


def test_up_refuses_a_half_removed_session(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A manifest with `"sandbox": null` is what the owner's two real retires left behind
    on #6855: agent-dgx's `session rm` deleted the sandbox, then its own workspace cleanup
    failed, every time. Before this check `up` filed that state under "already runs at
    <sha>: nothing to do" - true of no running thing - and a phase would ship with a
    member silently missing. Refuse, and name the verb that finishes the removal. NO_SANDBOX
    carries the target sha, so the old fall-through would have printed the lie's exact
    words; both assertions below pin the new path."""
    fake = FakeHost(sessions={CO: NO_SANDBOX})
    with pytest.raises(launch.Refused, match=f"agent-dgx session rm {CO} --force"):
        launch.up(host(tmp_path, fake), phase=0)
    assert "nothing to do" not in capsys.readouterr().out
    assert not fake.ran("agent-dgx", "run")
    assert not fake.changes()


def test_up_reports_a_stopped_session_as_stopped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The owner's `inspect uplevel-scratch2 --json` on #6855: manifest and sandbox record
    side by side, `"status": "stopped"`, no `agent-dgx stop` ever run - closing the
    agent's pane leaves every session in this state, so it is the normal one an `up` meets
    on a re-run. `up` called it "already runs", which is true of nothing running. It now
    echoes the status inspect reported, and the old claim is pinned gone."""
    fake = FakeHost(sessions={CO: STOPPED, OPS_B: RUNNING})
    launch.up(host(tmp_path, fake), phase=0)
    out = capsys.readouterr().out
    assert f"{CO} already exists at {MAIN_SHA[:8]}, sandbox stopped: nothing to do" in out
    assert "already runs" not in out
    assert not fake.ran("agent-dgx", "run")
    assert not fake.changes()


def test_up_dry_run_only_reads(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeHost()
    launch.up(host(tmp_path, fake, dry_run=True), phase=0)
    assert fake.changes() == []
    out = capsys.readouterr().out
    assert f"agent-dgx run {CO} --agent claude --endpoint dgx --split" in out
    # the owner's Phase-2 dry-run on #6855 showed the summary line claiming "created 2"
    # for sessions nothing created - the only past-tense line in a "would"-tense run
    assert "created" not in out


def test_up_reports_what_it_created_in_the_past_tense(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other tense: a real run's summary says `created`, naming the sessions, so the
    owner can see at a glance what the command added."""
    fake = FakeHost(sessions={CO: RUNNING})
    launch.up(host(tmp_path, fake), phase=0)
    assert "created 1: uplevel-ops-b" in capsys.readouterr().out


# ------------------------------------------------------------------- retire


def _clean_ws(**over: Any) -> dict[str, Any]:
    ws: dict[str, Any] = {"refs": {"main": MAIN_SHA}, "remote": remote_heads(PUSHED)}
    ws.update(over)
    return ws


@pytest.mark.parametrize(
    ("ws", "says"),
    [
        (_clean_ws(dirty=" M backend/main.py"), "changed"),
        (_clean_ws(dirty="?? scripts/new-thing.py"), "untracked"),
        (_clean_ws(stash="stash@{0}: WIP on main"), "stash"),
        (_clean_ws(refs={"main": MAIN_SHA, "wip": WIP_SHA}), "not pushed"),
        (_clean_ws(refs={"main": BASE_SHA}), "not pushed"),  # origin moved on without it
        (_clean_ws(branch="HEAD", head=WIP_SHA), "detached"),
    ],
)
def test_retire_refuses_and_changes_nothing(tmp_path: Path, ws: dict, says: str) -> None:
    fake = FakeHost(sessions={SCRATCH: RUNNING}, ws=ws)
    with pytest.raises(launch.Refused, match=says):
        launch.retire(host(tmp_path, fake), SCRATCH)
    assert not fake.ran("agent-dgx", "stop")
    assert not fake.ran("agent-dgx", "session", "rm")
    assert not (tmp_path / "exports").exists()


def test_a_failed_inspection_refuses_and_names_the_open_measurement(tmp_path: Path) -> None:
    """MEASURE (30-ops.md §O0.1): whether `sbx exec` still reaches the sandbox once the
    agent's session has ended. The step order never depends on the answer - inspect and
    export happen while the sandbox is still up - but an inspection that fails is still a
    refusal, and retirement is then the owner's manual call."""
    for failed in ("dirty", "remote"):
        fake = FakeHost(sessions={SCRATCH: RUNNING}, ws=_clean_ws(codes={failed: 128}))
        with pytest.raises(launch.Refused, match="inspection failed"):
            launch.retire(host(tmp_path, fake), SCRATCH)
        assert not fake.ran("agent-dgx", "stop")
        assert not (tmp_path / "exports").exists()


def test_retire_refuses_when_the_sandbox_is_already_gone(tmp_path: Path) -> None:
    """With no sandbox there is nothing to inspect, so there is no way to prove the work is
    safe. Refuse, and say whose call retirement is now. This is the state the owner's
    `inspect --json` showed after the first real retire's failed `session rm` - manifest
    present, `"sandbox": null`, a session removed halfway - so the refusal also names the
    one verb that finishes the job, which is why the failed-step message points here."""
    fake = FakeHost(sessions={SCRATCH: NO_SANDBOX})
    with pytest.raises(launch.Refused, match=f"agent-dgx session rm {SCRATCH} --force") as caught:
        launch.retire(host(tmp_path, fake), SCRATCH)
    assert "owner's manual call" in str(caught.value)
    assert not fake.ran("agent-dgx", "session", "rm")


def test_clean_retire_exports_verifies_then_removes(tmp_path: Path) -> None:
    fake = FakeHost(sessions={SCRATCH: RUNNING}, ws=_clean_ws())
    h = host(tmp_path, fake)
    launch.retire(h, SCRATCH)

    execs = [" ".join(argv) for argv, _ in fake.calls if argv[:2] == ["sbx", "exec"]]
    assert len(execs) == 3
    inspect_exec, bundle_exec, tree_exec = execs
    assert inspect_exec.startswith(f"sbx exec {SCRATCH_SANDBOX} bash -lc")
    assert f"cd /agents/{SCRATCH_SANDBOX}/workspace" in inspect_exec
    # git runs inside the sandbox with -c core.fsmonitor=false, never on the host against
    # the workspace (operator-runbook.md: its .git/config is the agent's to write)
    assert "git -c core.fsmonitor=false status --porcelain --untracked-files=all" in inspect_exec
    assert "git -c core.fsmonitor=false stash list" in inspect_exec
    assert "git -c core.fsmonitor=false for-each-ref" in inspect_exec
    assert "git -c core.fsmonitor=false ls-remote --heads origin" in inspect_exec
    assert "bundle create" in bundle_exec and "--all" in bundle_exec
    assert "tar" in tree_exec and "--exclude" in tree_exec  # the working tree, without .git

    # the export lands on the host under the session's own directory, is verified there,
    # and only then is anything stopped or removed
    dest = tmp_path / "exports" / SCRATCH
    assert sorted(p.name for p in dest.iterdir()) == [f"{SCRATCH}.bundle", "worktree.tar.gz"]
    assert (dest / f"{SCRATCH}.bundle").read_bytes() == BUNDLE_BYTES
    assert (dest / "worktree.tar.gz").read_bytes() == TREE_BYTES

    order = [" ".join(argv) for argv in fake.changes()]
    assert order == [
        bundle_exec,
        tree_exec,
        f"agent-dgx stop {SCRATCH}",
        f"agent-dgx session rm {SCRATCH} --force",
    ]


def test_the_export_is_verified_from_the_owners_checkout(tmp_path: Path) -> None:
    """`git bundle verify` from the owner's checkout; the archive listed (30-ops.md §O0.1)."""
    fake = FakeHost(sessions={SCRATCH: RUNNING}, ws=_clean_ws())
    h = host(tmp_path, fake)
    launch.retire(h, SCRATCH)
    verify = [(argv, cwd) for argv, cwd in fake.calls if "bundle" in argv and "verify" in argv]
    listing = [(argv, cwd) for argv, cwd in fake.calls if argv[:2] == ["tar", "-tzf"]]
    assert len(verify) == 1 and len(listing) == 1
    assert verify[0][1] == h.checkout and listing[0][1] == h.checkout
    bundle_path = verify[0][0][-1]
    assert bundle_path.endswith(f"{SCRATCH}.bundle")
    assert Path(bundle_path).is_file()


def test_a_bundle_that_does_not_verify_stops_before_removal(tmp_path: Path) -> None:
    fake = FakeHost(sessions={SCRATCH: RUNNING}, ws=_clean_ws(), fail="bundle verify")
    with pytest.raises(launch.Refused, match="verify"):
        launch.retire(host(tmp_path, fake), SCRATCH)
    assert not fake.ran("agent-dgx", "stop")
    assert not fake.ran("agent-dgx", "session", "rm")


def test_a_failed_removal_does_not_advice_a_rerun(tmp_path: Path) -> None:
    """The owner's first real retire on #6855 reached the last step and failed there: the
    export, copy, verify and stop all ran, then `agent-dgx session rm` returned 1 after
    printing that it removed the sandbox ("cannot unmount '/agents/agent-uplevel-scratch':
    pool or dataset is busy"). `inspect --json` after the failure shows the state that
    leaves behind - `"sandbox": null` with the manifest still present - so a blanket "fix
    it and run this again" sends the owner to a command that refuses on exactly that
    half-done state. The refusal names what is already safe and what the state looks like,
    and the stop really did run before it."""
    fake = FakeHost(sessions={SCRATCH: RUNNING}, ws=_clean_ws(), fail="session rm")
    with pytest.raises(launch.Refused, match="removed halfway") as caught:
        launch.retire(host(tmp_path, fake), SCRATCH)
    assert fake.ran("agent-dgx", "stop")  # everything up to the removal did happen
    assert "verifies the work" in str(caught.value)


def test_retire_dry_run_only_reads(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeHost(sessions={SCRATCH: RUNNING}, ws=_clean_ws())
    launch.retire(host(tmp_path, fake, dry_run=True), SCRATCH)
    assert fake.changes() == []
    assert not (tmp_path / "exports").exists()
    out = capsys.readouterr().out
    assert f"agent-dgx session rm {SCRATCH} --force" in out
    # its help is "run the checks and print the steps", so the inspection really runs
    assert fake.ran("sbx", "exec")


def test_retire_dry_run_refuses_a_workspace_the_real_run_would_refuse(
    tmp_path: Path,
) -> None:
    """A dry run that skipped the inspection printed a clean plan ending in
    `session rm --force` for a session the real run refuses - hedged in parentheses,
    which is not a refusal. The inspection only reads, so --dry-run runs it."""
    fake = FakeHost(sessions={SCRATCH: RUNNING}, ws=_clean_ws(dirty=" M backend/main.py"))
    with pytest.raises(launch.Refused, match="changed files"):
        launch.retire(host(tmp_path, fake, dry_run=True), SCRATCH)
    assert fake.changes() == []


def test_retire_without_a_session_changes_nothing(tmp_path: Path) -> None:
    fake = FakeHost()
    launch.retire(host(tmp_path, fake), SCRATCH)
    assert fake.changes() == []


@pytest.mark.parametrize("command", ["up", "retire"])
def test_running_from_a_sessions_clone_refuses(tmp_path: Path, command: str) -> None:
    """The owner's first real retire on #6855 ran with the cwd inside the session's own
    clone (/agents/agent-uplevel-scratch/workspace) - which turns the run's trusted
    reference into the suspect's own repo: retire reads the expected `origin` from this
    checkout (#5), verifies the bundle with host git *in* it (the operator runbook's
    forbidden access - core.fsmonitor is the agent's to set), and up would copy it into
    every clone. Refused before anything, naming where to run instead. The launcher
    can't tell a session's clone from any checkout by content - only by where it lives,
    under the sessions' root."""
    fake = FakeHost()
    in_clone = host(tmp_path, fake)
    in_clone = replace(in_clone, checkout=in_clone.agents_root / SCRATCH_SANDBOX / "workspace")
    (in_clone.checkout).mkdir(parents=True)
    with pytest.raises(launch.Refused, match="session's own clone"):
        if command == "up":
            launch.up(in_clone, phase=0)
        else:
            launch.retire(in_clone, SCRATCH)
    assert fake.calls == []  # refused before even the read-only commands


def test_up_reads_the_manifest_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One run acts on one content: up() used to parse the file for the phase list, again
    for the phase's rows, and once per session for [models] - a coordinator edit landing
    mid-run could have the checks read one version and the creates act on another. The
    parse result now flows down, so exactly one read happens for a whole phase."""
    reads = 0
    real = launch._load_toml

    def counting(path: Path) -> dict[str, Any]:
        nonlocal reads
        reads += 1
        return real(path)

    monkeypatch.setattr(launch, "_load_toml", counting)
    # a manifest of this test's own, so the counts hold whatever the coordinator puts in
    # the real roster later (a real phase-1 run would refuse anyway: `strongest` is unset)
    manifest = tmp_path / "m.toml"
    manifest.write_text(
        '[models]\nfast = "--agent claude --endpoint dgx"\n'
        + "[[phase]]\nnumber = 0\n"
        + "".join(
            f'[[phase.session]]\nname = "s{n}"\nmodel = "fast"\nkickoff = "k"\n' for n in range(3)
        ),
        encoding="utf-8",
    )
    fake = FakeHost()
    launch.up(host(tmp_path, fake, manifest=manifest), phase=0)
    assert reads == 1
    assert sum(1 for argv in fake.changes() if argv[:3] == ["agent-dgx", "run", "s2"]) == 1


def test_main_turns_a_refusal_into_exit_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Everything asserts `Refused` is raised; `main()` is what turns that into exit 2
    (30-ops.md §O0.1's contract, and the exit code the owner's shell sees). Patching the
    class `main()` looks up is what keeps this off the machine: `main()` builds its own
    Host from the cwd, so without this the test would run real git and real agent-dgx,
    and its result would depend on which of those happen to be installed here. The patch
    forwards the arguments it is given - a lambda that dropped `dry_run` would answer a
    different command than the one sent and could pass for the wrong reason."""
    fake = FakeHost(sessions={SCRATCH: RUNNING}, ws=_clean_ws(dirty=" M backend/main.py"))
    monkeypatch.setattr(
        launch,
        "Host",
        lambda **kwargs: host(tmp_path, fake, dry_run=bool(kwargs.get("dry_run"))),
    )
    assert launch.main(["retire", SCRATCH, "--dry-run"]) == 2
    assert "changed files" in capsys.readouterr().err  # the refusal the owner reads
    assert fake.changes() == []
    # the success path exits 0, so 2 means "refused" and not "ran"
    idle = FakeHost()
    monkeypatch.setattr(
        launch, "Host", lambda **kwargs: host(tmp_path, idle, dry_run=bool(kwargs.get("dry_run")))
    )
    assert launch.main(["retire", SCRATCH]) == 0


# ------------------------------------------- the command vocabulary


def test_every_agent_dgx_call_names_its_subcommand(tmp_path: Path) -> None:
    """An unknown word starts a real session (operator-runbook.md), so the launcher always
    names its subcommand and nothing here is `agent-dgx help` or `agent-dgx ls`."""
    fake = FakeHost()
    launch.up(host(tmp_path, fake), phase=0)  # creates both Phase 0 sessions
    launch.retire(host(tmp_path, fake), SCRATCH)  # no such session: a no-op
    checked = 0
    for argv, _ in fake.calls:
        if argv[:1] != ["agent-dgx"]:
            continue
        assert argv[1] in {"run", "inspect", "stop", "session"}, argv
        if argv[1] == "session":
            assert argv[2] == "rm", argv
        checked += 1
    assert fake.ran("agent-dgx", "run", CO) and fake.ran("agent-dgx", "inspect", CO)
    assert checked > 0


# --------------------------- the inspection script, run for real


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(  # real: drives a throwaway git repo  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        env=GIT_ENV,
    )
    return done.stdout


def _scratch_repo(tmp_path: Path) -> Path:
    """A throwaway workspace with a real `origin`, shaped like an agent's clone: one
    commit on `main`, pushed. Built with real git, as test_vss_next_id.py does."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", str(origin))
    work = tmp_path / "workspace"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "main.py").write_text("print('hi')\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "base")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-q", "-u", "origin", "main")
    return work


def _redirect_origin(work: Path) -> str:
    """Point the clone's `origin` at a second bare repo and push there - what an agent
    rewriting its own .git/config does: every branch is "pushed", and the teams remote is
    one this clone no longer mentions. Returns the new URL, which the host's checkout
    will not have."""
    elsewhere = work.parent / "not-the-teams-repo.git"
    _git(work.parent, "init", "-q", "--bare", str(elsewhere))
    _git(work, "push", "-q", str(elsewhere), "main")
    _git(work, "remote", "set-url", "origin", str(elsewhere))
    return str(elsewhere)


def _remote_url(repo: Path) -> str:
    """What `git remote get-url origin` answers in `repo` - the section's real text."""
    return _git(repo, "remote", "get-url", "origin").strip()


def _run_inspection(workspace: Path) -> dict[str, tuple[str, int]]:
    """Run the launcher's real inspection script, as `sbx exec` would, and parse it.

    `sbx exec <sandbox> bash -lc <script>` makes the whole inspection one *string*, so
    every argument's shell quoting is load-bearing: unquoted, the space and parentheses
    in `--format=%(objectname) %(refname)` split the word and bash stops on `(`. A
    substring check on the script cannot see that - only running it can. The workspace
    path is rewritten because the sandbox's fixed path cannot exist inside a test.
    """
    session = launch.Session(name=SCRATCH, model="", kickoff="")
    script = launch._inspect_argv(session)[-1].replace(session.workspace, str(workspace))
    done = subprocess.run(  # real: runs the inspection script itself  # noqa: S603
        ["bash", "-lc", script],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        env=GIT_ENV,
    )
    assert not done.stderr, f"the script is not valid bash: {done.stderr}"
    return launch.parse_inspection(done.stdout)


def test_the_inspection_script_runs_and_passes_a_pushed_workspace(tmp_path: Path) -> None:
    workspace = _scratch_repo(tmp_path)
    sections = _run_inspection(workspace)
    assert set(sections) == set(launch.SECTION_NAMES), "every section must answer"
    assert all(code == 0 for _, code in sections.values()), sections
    assert (
        launch.assess_inspection(sections, session=SCRATCH, expected_origin=_remote_url(workspace))
        == []
    )


def test_a_redirected_origin_refuses_even_with_everything_pushed(tmp_path: Path) -> None:
    """`remote` asks the origin the agent's own .git/config names, and the agent writes
    that config. Push everything to a second repo, repoint origin at it, and every
    `pushed` answer is true of a remote the team never sees - the one assurance retire
    must never give falsely (50-coordination.md: GitHub is the only channel)."""
    workspace = _scratch_repo(tmp_path)
    elsewhere = _redirect_origin(workspace)
    sections = _run_inspection(workspace)
    assert sections["origin"] == (elsewhere, 0), "the seventh section names the real remote"
    # against the URL the clone itself reports, nothing looks wrong - that is the trap
    assert launch.assess_inspection(sections, session=SCRATCH, expected_origin=elsewhere) == []
    risks = launch.assess_inspection(
        sections, session=SCRATCH, expected_origin=str(tmp_path / "origin.git")
    )
    assert any("origin" in r and "not the host checkout's" in r for r in risks), risks
    assert not any("not pushed" in r for r in risks), "the refs really are pushed, there"


def test_the_inspection_script_spots_an_unpushed_branch_for_real(tmp_path: Path) -> None:
    """The Done-when's throwaway case: work on a branch that origin has never seen."""
    workspace = _scratch_repo(tmp_path)
    _git(workspace, "checkout", "-q", "-b", "wip")
    (workspace / "wip.py").write_text("work\n", encoding="utf-8")
    _git(workspace, "add", "-A")
    _git(workspace, "commit", "-q", "-m", "unpushed work")

    risks = launch.assess_inspection(
        _run_inspection(workspace), session=SCRATCH, expected_origin=_remote_url(workspace)
    )
    assert any("wip" in r and "not pushed" in r for r in risks), risks


def test_the_inspection_script_spots_changed_and_untracked_files_for_real(
    tmp_path: Path,
) -> None:
    workspace = _scratch_repo(tmp_path)
    (workspace / "main.py").write_text("print('changed')\n", encoding="utf-8")
    (workspace / "loose.py").write_text("new\n", encoding="utf-8")

    risks = launch.assess_inspection(
        _run_inspection(workspace), session=SCRATCH, expected_origin=_remote_url(workspace)
    )
    assert any("changed" in r and "main.py" in r for r in risks), risks
    assert any("untracked" in r and "loose.py" in r for r in risks), risks


def test_a_failed_retire_does_not_poison_its_own_retry(tmp_path: Path) -> None:
    """`retire` exports into .uplevel-retire/ inside the workspace it inspects, so when
    anything after the export fails (a copy, a verify) that litter is still there on the
    retry. It is the launcher's, not the agent's work: excluding it keeps the retry's
    refusal about the real question instead of a bogus "untracked files" one.

    Excluded by file name, not by directory. `retire` also excludes the whole directory
    from the worktree archive, so a directory-wide blind spot here would let a file in
    that directory be neither reported nor exported - lost, which is the one thing retire
    is not allowed to do. So only the launcher's own two artifacts are ignored."""
    workspace = _scratch_repo(tmp_path)
    staged = workspace / launch.EXPORT_DIR
    staged.mkdir()
    (staged / f"{SCRATCH}.bundle").write_bytes(BUNDLE_BYTES)
    (staged / "worktree.tar.gz").write_bytes(TREE_BYTES)

    assert (
        launch.assess_inspection(
            _run_inspection(workspace), session=SCRATCH, expected_origin=_remote_url(workspace)
        )
        == []
    )

    (staged / "agent-notes.md").write_text("work the agent wrote here\n", encoding="utf-8")
    (workspace / "real-work.py").write_text("still here\n", encoding="utf-8")
    risks = launch.assess_inspection(
        _run_inspection(workspace), session=SCRATCH, expected_origin=_remote_url(workspace)
    )
    assert any("real-work.py" in r for r in risks), "the exclusion must not hide real work"
    assert any("agent-notes.md" in r for r in risks), "nor a file left inside the export dir"
    assert not any(f"{SCRATCH}.bundle" in r or "worktree.tar.gz" in r for r in risks), risks


# --------------------------------------- refusal logic on fixture outputs


def test_assess_reports_changed_files() -> None:
    sections = launch.parse_inspection(sections_body(dirty=(" M backend/main.py\n", 0)))
    assert any("changed" in r for r in launch.assess_inspection(sections, session=SCRATCH))


def test_assess_reports_untracked_files() -> None:
    sections = launch.parse_inspection(sections_body(dirty=("?? scripts/new-thing.py\n", 0)))
    assert any("untracked" in r for r in launch.assess_inspection(sections, session=SCRATCH))


def test_assess_refuses_a_failed_section() -> None:
    risks = launch.assess_inspection(
        launch.parse_inspection(sections_body(dirty=("", 128))), session=SCRATCH
    )
    assert any("inspection failed" in r for r in risks)
    # a section failing for the same reason twice is reported once, not "dirty, dirty"
    assert risks[0].count("dirty") == 1, risks


def test_a_failed_section_carries_its_stderr_for_real(tmp_path: Path) -> None:
    """`2>/dev/null` once turned a bash syntax error into a refusal that blamed the open
    MEASURE: the section failed, its cause vanished. A failing section now carries the
    first line of its stderr into the body, so the refusal can show why it refused."""
    workspace = _scratch_repo(tmp_path)
    session = launch.Session(name=SCRATCH, model="", kickoff="")
    script = launch._inspect_argv(session)[-1].replace(session.workspace, str(workspace))
    # fail one command at runtime (an unknown flag: parses fine, writes git's error to
    # stderr, exits 129) - exactly the shape of a real section failure
    broken = script.replace(
        "git -c core.fsmonitor=false stash list",
        "git -c core.fsmonitor=false stash --no-such-flag list",
    )
    assert broken != script, "the fixture must really alter the script"
    done = subprocess.run(  # real: the altered script, run on purpose  # noqa: S603
        ["bash", "-lc", broken],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        env=GIT_ENV,
    )
    sections = launch.parse_inspection(done.stdout)
    assert sections["stash"][1] != 0, "the broken section must fail"
    assert "stderr:" in sections["stash"][0], "and its cause must survive into the body"
    risks = launch.assess_inspection(sections, session=SCRATCH)
    assert any("inspection failed" in r for r in risks)


def test_assess_passes_a_clean_and_pushed_workspace() -> None:
    sections = launch.parse_inspection(
        sections_body(
            refs=(f"{MAIN_SHA} refs/heads/main\n", 0),
            remote=(remote_heads({"main": MAIN_SHA, "agent-branch": MAIN_SHA}), 0),
        )
    )
    assert launch.assess_inspection(sections, session=SCRATCH) == []
