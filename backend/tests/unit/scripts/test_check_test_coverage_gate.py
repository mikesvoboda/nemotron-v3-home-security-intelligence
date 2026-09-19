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
