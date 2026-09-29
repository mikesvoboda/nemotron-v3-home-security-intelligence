"""R8 S1: nothing in the shipped code may branch on pipeline_mode == "legacy".

ABOUTME: The deletion guard for the legacy pipeline's branch sites. Owner ruling 2026-09-29:
"we should hard raise" -- so config now rejects PIPELINE_MODE=legacy at boot
(test_config_pipeline_mode_hard_raise.py). Rejecting it is only half the work: thirteen branch
sites stayed behind, unreachable-but-present, which is the "confuse future agents" failure the
owner named as the motive for R8. This gate is what makes their absence structural.

Why an AST scan and not a grep. Two hazards the naive instrument has, both real here:
  - backend/core/config.py's RAISE TEXT contains the word legacy. A bare grep for "legacy" over
    backend/ can never be empty, so a gate written that way is unsatisfiable and gets skipped.
  - backend/api/schemas/enrichment_data.py has dict keys literally spelled "legacy" in a JSON
    field-name migration (old `"vehicle"` -> `"vehicle_classifications"`). Those are data, not a
    mode branch, and deleting them would corrupt stored-event readers. The scope doc counted
    them among the branch sites; matching on ast.Compare instead of on text excludes them.

So the rule is structural: no comparison against the string "legacy" anywhere in shipped
backend code. A comparison is what selecting the pipeline means; a key, a comment, a docstring
or an error message is not.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "backend"


def shipped_python() -> list[Path]:
    """backend/**.py, tests and caches excluded."""
    return [
        path
        for path in BACKEND.rglob("*.py")
        if "tests" not in path.parts and "__pycache__" not in path.parts
    ]


def legacy_comparisons(path: Path) -> list[int]:
    """1-indexed lines where this file compares something against the string "legacy"."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            if any(isinstance(o, ast.Constant) and o.value == "legacy" for o in operands):
                hits.append(node.lineno)
    return hits


def test_shipped_code_is_importable_by_the_scanner() -> None:
    """Guards the guard: if the scan matches nothing, the slice passes for the wrong reason."""
    files = shipped_python()
    assert len(files) > 500, f"scanner found only {len(files)} files under {BACKEND} — path moved"


def test_the_scanner_recognises_a_mode_branch() -> None:
    """A positive control. A scanner that never fires and a clean tree look identical."""
    sample = "if settings.pipeline_mode == 'legacy':\n    x = 1\n"
    tree = ast.parse(sample)
    found = [
        n.lineno
        for n in ast.walk(tree)
        if isinstance(n, ast.Compare)
        and any(
            isinstance(o, ast.Constant) and o.value == "legacy" for o in [n.left, *n.comparators]
        )
    ]
    assert found == [1]


def test_no_shipped_file_compares_against_legacy() -> None:
    offenders: list[str] = []
    for path in shipped_python():
        for line in legacy_comparisons(path):
            offenders.append(f"{path.relative_to(REPO_ROOT)}:{line}")
    assert not offenders, (
        f"{len(offenders)} legacy branch site(s) remain — R8 S1 deletes them:\n  "
        + "\n  ".join(offenders)
    )
