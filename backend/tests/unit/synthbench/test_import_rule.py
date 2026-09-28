"""Spec §7.1: only synthbench/score and synthbench/run may import backend."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def _imported_modules(path: Path) -> Iterator[str]:
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module


def test_generate_never_imports_backend() -> None:
    paths = sorted((REPO_ROOT / "synthbench" / "generate").rglob("*.py"))
    # an empty walk (a moved package, a wrong REPO_ROOT) would pass vacuously
    assert REPO_ROOT / "synthbench" / "generate" / "window.py" in paths
    offenders = [
        f"{path.relative_to(REPO_ROOT)}: {module}"
        for path in paths
        for module in _imported_modules(path)
        if module == "backend" or module.startswith("backend.")
    ]
    assert offenders == []


def test_only_score_and_run_may_import_backend() -> None:
    """Spec §7.1: across all of synthbench, only score/ and run/ may import backend."""
    root = REPO_ROOT / "synthbench"
    allowed = (root / "score", root / "run")
    paths = sorted(p for p in root.rglob("*.py") if not any(p.is_relative_to(a) for a in allowed))
    # an empty walk would pass vacuously; these files come from the contract/sampler plan
    assert root / "cli.py" in paths
    assert root / "contract" / "spec.py" in paths
    assert root / "taxonomy" / "sampler.py" in paths
    offenders = [
        f"{path.relative_to(REPO_ROOT)}: {module}"
        for path in paths
        for module in _imported_modules(path)
        if module == "backend" or module.startswith("backend.")
    ]
    assert offenders == []
