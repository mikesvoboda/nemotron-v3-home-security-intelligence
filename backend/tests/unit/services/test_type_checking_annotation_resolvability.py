"""Repo-wide pin: TYPE_CHECKING-annotated modules must stay signature-safe.

Bug class (PR #6679 CI, py 3.14.2): a module that annotates callables
with TYPE_CHECKING-only types but lacks ``from __future__ import
annotations`` gets, under PEP 649 (3.14+), lazy ``__annotate__``
evaluators that resolve those bare names against module globals at
RUNTIME. Any runtime annotation consumer -- ``inspect.signature``,
``unittest.mock.create_autospec`` -- raises NameError. It reproduces
only on the CI patch level (mock on newer 3.14 falls back to
ForwardRef), so it is invisible locally unless you call
``inspect.signature`` directly.

This test enumerates every backend module with a ``if TYPE_CHECKING:``
block and no future-annotations import and pins that every public
callable's signature resolves. New offenders fail here at PR time
instead of as 16 red autospec tests in a CI shard.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]


def _has_type_checking_block(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "TYPE_CHECKING"
        for node in ast.walk(tree)
    )


def _offender_prone_modules() -> list[str]:
    """Modules with TYPE_CHECKING blocks but no PEP 563 future import."""
    mods = []
    for path in (REPO / "backend").rglob("*.py"):
        if "/tests/" in str(path) or path.name == "__init__.py":
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        if not _has_type_checking_block(tree):
            continue
        if any(
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(a.name == "annotations" for a in node.names)
            for node in ast.walk(tree)
        ):
            continue
        mods.append(str(path.relative_to(REPO))[: -len(".py")].replace("/", "."))
    return sorted(mods)


PRONE = _offender_prone_modules()


def _public_callables(module):
    for name, obj in inspect.getmembers(module):
        if name.startswith("_"):
            continue
        fn = getattr(obj, "__func__", obj)
        if inspect.isfunction(fn) or inspect.ismethod(fn):
            yield name, fn


@pytest.mark.parametrize("module_name", PRONE, ids=PRONE)
def test_public_signatures_resolve(module_name: str):
    """Every public callable must survive inspect.signature().

    Pre-fix offenders carried NameErrors like:
      analyzer_facade.get_cache_service -> CacheService is not defined
      face_detector.detect_faces        -> PILImage is not defined
    """
    module = importlib.import_module(module_name)
    broken = []
    for qual, fn in _public_callables(module):
        try:
            inspect.signature(fn)
        except Exception as exc:
            broken.append(f"{qual}: {type(exc).__name__}: {exc}")
    assert not broken, f"{module_name} has runtime-unresolvable annotations: {broken}"


def test_prone_list_shrinks_as_modules_get_the_future_import():
    """Sanity: the scan works and every listed module is genuinely prone."""
    assert PRONE, "scan found no prone modules -- convention fully adopted?"
    for dotted in PRONE:
        path = REPO / (dotted.replace(".", "/") + ".py")
        assert _has_type_checking_block(ast.parse(path.read_text())), (
            f"{dotted} listed as prone but has no TYPE_CHECKING block"
        )
