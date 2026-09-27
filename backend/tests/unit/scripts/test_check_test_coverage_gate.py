"""Tests for scripts/check-test-coverage-gate.py (WP6-branch, CI flake parity).

The gate's inline full-unit collection run (the no-seam branch of
check_coverage_diff) was the ONLY full-tier pytest invocation in CI without
the repo's rerun convention, so pytest-timeout flakes on -n 8 CI load failed
the required Test Coverage Gate with no real regression (three occurrences on
#6560's stack, each time a DIFFERENT test, all green locally and in the shard
jobs which carry --reruns 2 --reruns-delay 5, ci.yml:675,797).

These tests inspect the script's AST, not its behavior: the collection
subprocess is CI-only glue, and what we are pinning is the argv it builds.
"""

import ast
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "check-test-coverage-gate.py"


def _inline_collection_argv() -> list[str]:
    """argv elements of the subprocess.run([...pytest...]) call inside
    check_coverage_diff - the inline full-unit collection."""
    tree = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    func = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "check_coverage_diff"
    )
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
            and node.args
            and isinstance(node.args[0], ast.List)
        ):
            argv = [
                elt.value
                for elt in node.args[0].elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            ]
            if "pytest" in argv:
                return argv
    raise AssertionError("no subprocess.run([...pytest...]) call in check_coverage_diff")


def test_inline_collection_carries_rerun_parity() -> None:
    """The gate's inline collection matches the shard jobs' rerun convention.

    Extraction is not enforcement (--cov-fail-under=0 already documents
    that): a flake-retry here moves no floor and gates nothing weaker - it
    only stops a 5-second signal-timeout on an unrelated test from reddening
    the required gate.
    """
    argv = _inline_collection_argv()
    assert "--reruns" in argv, (
        "inline collection must carry --reruns like the shard jobs "
        "(ci.yml:675,797): three gate reds on #6560 were pytest-timeout "
        "flakes in THIS subprocess, each a different test"
    )
    assert "--reruns-delay" in argv, "with --reruns-delay, matching the shard convention exactly"
    # the flags must come as separate argv tokens AND carry values
    assert argv[argv.index("--reruns") + 1] == "2"
    assert argv[argv.index("--reruns-delay") + 1] == "5"


def test_inline_collection_still_extraction_only() -> None:
    """Parity fix must not silently turn collection into enforcement."""
    argv = _inline_collection_argv()
    assert "--cov-fail-under=0" in argv, (
        "collection EXISTS to extract the seam number; enforcement belongs "
        "to the shard jobs' floors, not here"
    )


def _load_gate(root: Path):
    """Load the gate script as if it LIVED at `root/scripts/`.

    `find_test_file` computes `project_root` from the module's own `__file__`,
    so the honest way to test it against a fixture tree is to place the real
    script in a tmp tree and import that copy - the code under test is
    byte-identical and nothing about path resolution is faked. (Monkeypatching
    the module's `Path` would have redirected `Path(source_file)` but not
    `Path(__file__)`, so the tree it probed would have been the real repo and
    the test would pass or fail for reasons unrelated to the finder.)
    """
    import importlib.util

    script_dir = root / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)
    copy = script_dir / "check-test-coverage-gate.py"
    copy.write_text(_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("covgate_copy", copy)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestFindTestFileFrontend:
    """`find_test_file` resolved a frontend source to ONE candidate name -
    `<stem>.test` + the source's own suffix - so a `.ts` hook whose suite
    lives at `<stem>.test.tsx` read as "Tests: None found" and the required
    Test Coverage Gate failed the PR for OBEYING it.

    That is not a hypothetical: `frontend/src/hooks/useTopEventsQuery.ts` has
    its suite at `useTopEventsQuery.test.tsx` (a JSX `<QueryClientProvider>`
    wrapper at :47 makes `.ts` genuinely invalid, so the extension is not a
    mistake to "fix" by renaming), and `d1e279fd`'s stack of frontend fixes
    made the hook a substantial change, which is what surfaced it. The
    directory uses BOTH extensions today (see `useAlerts.test.tsx` beside
    `useAlertsQuery.test.ts`), so the finder - not the corpus - is wrong.

    Behavior tests, unlike the AST pins above, because the thing that broke
    is a runtime path-existence decision the AST cannot express.
    """

    def test_ts_source_with_only_a_tsx_suite_resolves(self, tmp_path) -> None:
        gate = _load_gate(tmp_path)
        hooks = tmp_path / "frontend" / "src" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "useThing.ts").write_text("export const useThing = () => null\n")
        (hooks / "useThing.test.tsx").write_text("import {x} from './useThing'\n")
        found = gate.find_test_file("frontend/src/hooks/useThing.ts")
        assert found == "frontend/src/hooks/useThing.test.tsx", (
            "a .ts source with a .tsx suite IS tested; None here is the "
            "false-missing that reddened Test Coverage Gate on #6681"
        )

    def test_tsx_source_with_only_a_ts_suite_resolves(self, tmp_path) -> None:
        """The mirror case, so the fix is a rule and not one file's patch."""
        gate = _load_gate(tmp_path)
        comps = tmp_path / "frontend" / "src" / "components"
        comps.mkdir(parents=True)
        (comps / "Thing.tsx").write_text("export const Thing = () => null\n")
        (comps / "Thing.test.ts").write_text("import {Thing} from './Thing'\n")
        assert gate.find_test_file("frontend/src/components/Thing.tsx") == (
            "frontend/src/components/Thing.test.ts"
        )

    def test_no_suite_at_all_still_returns_none(self, tmp_path) -> None:
        """The gate must keep catching a genuinely untested file - a finder
        that always finds something is a neutered gate, the same vacuous-green
        class this repo refuses everywhere else."""
        gate = _load_gate(tmp_path)
        hooks = tmp_path / "frontend" / "src" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "Untested.ts").write_text("export const x = 1\n")
        assert gate.find_test_file("frontend/src/hooks/Untested.ts") is None

    def test_the_shipped_hook_that_reddened_the_gate_resolves(self) -> None:
        """The real file, against the real tree - the pin that fails if either
        the finder regresses or the corpus renames the suite back to a
        non-matching extension."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("covgate", _SCRIPT)
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        assert gate.find_test_file("frontend/src/hooks/useTopEventsQuery.ts") == (
            "frontend/src/hooks/useTopEventsQuery.test.tsx"
        )
