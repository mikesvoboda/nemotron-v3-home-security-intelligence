#!/usr/bin/env python3
"""Can a mock-patch target be PROVEN a 0-arity callable? (WP2.4c, ruling R-5)

`autospec=True` protects a call against SIGNATURE drift. A callable with a
provably empty signature — zero declared params of any kind, no *args/**kwargs
— has nothing to drift: the suppression buys essentially nothing, so R-5
retires those `unspecced_patch` sites from the count (this LOWERS the ratchet
baseline; it never raises it).

The proof is static and deliberately conservative — `is_zero_arity()` returns
True ONLY on a def read from this tree:

  * the target string's longest module prefix is indexed from the repo root;
  * `class.attr` follows to the method; a CLASS target is NOT retired even
    with a 0-arg __init__ (autospec on a class also specs its attribute
    surface — that is a real suppression);
  * a decorated def is NOT retired (the wrapper may change the signature);
  * a name the resolver cannot follow — a module-level import alias is
    followed at most along module paths, and anything else (third-party,
    dynamic, module-level assignment) is UNRESOLVED, which means KEEP.

A count may only fall on evidence, never on a guess: every non-proof keeps
the site licensed.
"""

from __future__ import annotations

import ast
from pathlib import Path

# Only first-party trees get indexed; a target whose root is anything else
# (stdlib/third party `redis...`) is unresolved -> kept (importing it to ask
# `inspect` would execute arbitrary module code inside the gate).
INDEX_TOP = ("backend", "ai", "scripts")


def _params_are_all_absent(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    a = fn.args
    total = len(a.posonlyargs) + len(a.args) + len(a.kwonlyargs)
    return total == 0 and a.vararg is None and a.kwarg is None


def _funcs(node: ast.ClassDef | ast.Module):
    return [n for n in node.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]


class ArityResolver:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.mods: dict[str, Path] = {}
        for p in root.rglob("*.py"):
            try:
                parts = p.relative_to(root).parts
            except ValueError:
                continue
            if not parts or parts[0] not in INDEX_TOP:
                continue
            if parts[-1] == "__init__.py":
                self.mods[".".join(parts[:-1])] = p
            else:
                self.mods[".".join([*parts[:-1], parts[-1][: -len(".py")]])] = p
        self._tree: dict[Path, ast.Module | None] = {}
        self._imports: dict[Path, dict[str, str]] = {}

    def _ast(self, path: Path) -> ast.Module | None:
        if path not in self._tree:
            try:
                self._tree[path] = ast.parse(path.read_text())
            except (SyntaxError, OSError, UnicodeDecodeError):
                self._tree[path] = None
        return self._tree[path]

    def _module_imports(self, path: Path) -> dict[str, str]:
        """Module-level `import x[.y] [as a]` / `from m import n [as a]`."""
        if path not in self._imports:
            out: dict[str, str] = {}
            tree = self._ast(path)
            if tree is not None:
                for node in tree.body:
                    if isinstance(node, ast.Import):
                        for al in node.names:
                            out[al.asname or al.name.split(".")[0]] = al.name
                    elif isinstance(node, ast.ImportFrom):
                        if node.level:
                            continue  # relative — unfollowed, resolves to KEEP
                        for al in node.names:
                            out[al.asname or al.name] = f"{node.module or ''}.{al.name}".strip(".")
            self._imports[path] = out
        return self._imports[path]

    def _resolve_in(self, mod_path: Path, names: list[str], depth: int):
        """-> True/False (proven zero / proven nonzero), or None (unknown)."""
        if depth > 8:
            return None
        tree = self._ast(mod_path)
        if tree is None:
            return None
        i = 0
        scope: ast.Module | ast.ClassDef = tree
        while i < len(names):
            name = names[i]
            body = scope.body
            cand = next(
                (
                    n
                    for n in body
                    if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
                    and n.name == name
                ),
                None,
            )
            if cand is None:
                if scope is tree:
                    # a module-level import alias (patch-at-use-site): the
                    # name lives in another module — follow it, but only
                    # along first-party module paths.
                    dotted = self._module_imports(mod_path).get(name)
                    if dotted is None:
                        return None
                    parts = dotted.split(".")
                    for k in range(len(parts), 0, -1):
                        nxt = self.mods.get(".".join(parts[:k]))
                        if nxt is not None:
                            return self._resolve_in(nxt, parts[k:] + names[i + 1 :], depth + 1)
                    return None  # third-party alias -> unresolved -> KEEP
                return None
            if isinstance(cand, ast.FunctionDef | ast.AsyncFunctionDef):
                if i != len(names) - 1:
                    return None  # attribute of a call result: not visible
                if cand.decorator_list:
                    return None  # a wrapper may change the signature -> KEEP
                return _params_are_all_absent(cand)
            # ClassDef: classes are NEVER retired (attribute-surface spec),
            # but a method lookup may still land on a provable plain def.
            if i == len(names) - 1:
                return False
            meth = next((f for f in _funcs(cand) if f.name == names[i + 1]), None)
            if meth is None:
                return None
            if meth.decorator_list:
                return None
            # a method has at least `self` -> nonzero by construction unless
            # something pathological; still measured, not assumed:
            return _params_are_all_absent(meth)
        return None

    def is_zero_arity(self, target: str, imports: dict[str, str] | None = None) -> bool:
        """True only on a read-from-source proof. Anything else -> False
        (= keep the site licensed). `imports` extends the alias map at the
        ORIGIN site (test module) before module-prefix matching."""
        parts = target.split(".")
        if imports:
            head = imports.get(parts[0], parts[0])
            parts = head.split(".") + parts[1:]
        for i in range(len(parts), 0, -1):
            mp = self.mods.get(".".join(parts[:i]))
            if mp is not None:
                return self._resolve_in(mp, parts[i:], 0) is True
        return False


def module_imports_of(path: Path) -> dict[str, str]:
    """The import alias map for the ORIGIN (test) file — used to turn
    `patch.object(main, "init_redis")` into `backend.main.init_redis`."""
    out: dict[str, str] = {}
    try:
        tree = ast.parse(path.read_text())
    except (SyntaxError, OSError, UnicodeDecodeError):
        return out
    for node in tree.body:
        if isinstance(node, ast.Import):
            for al in node.names:
                out[al.asname or al.name.split(".")[0]] = al.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            for al in node.names:
                out[al.asname or al.name] = f"{node.module or ''}.{al.name}".strip(".")
    return out
