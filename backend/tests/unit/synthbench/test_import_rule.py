"""Spec §7.1: nothing under synthbench/generate imports backend."""

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
