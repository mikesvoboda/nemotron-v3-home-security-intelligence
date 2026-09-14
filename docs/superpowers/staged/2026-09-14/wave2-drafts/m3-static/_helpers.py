"""Shared read-only AST helpers for M3 static drafts. Reads files only; never imports them."""
import ast, os, sys, json

REPO = "/agents/agent-nemo2/workspace"

def fixtures_in(path):
    """Return list of (name, deco_lineno, def_lineno, scope, is_autouse, cls)."""
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src, filename=path)
    out = []

    def visit(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in child.decorator_list:
                    d = dec
                    if isinstance(d, ast.Call):
                        d = d.func
                    name_ok = False
                    if isinstance(d, ast.Attribute) and d.attr == "fixture":
                        name_ok = True
                    elif isinstance(d, ast.Name) and d.id == "fixture":
                        name_ok = True
                    if not name_ok:
                        continue
                    fname = child.name
                    deco_line = dec.lineno
                    scope = "function"
                    autouse = False
                    for kw in (getattr(dec, "keywords", []) if isinstance(dec, ast.Call) else []):
                        if kw.arg == "scope" and isinstance(kw.value, ast.Constant):
                            scope = kw.value.value
                        if kw.arg == "autouse" and isinstance(kw.value, ast.Constant):
                            autouse = bool(kw.value.value)
                    out.append({"name": prefix + fname, "deco_line": deco_line,
                                "def_line": child.lineno, "end_line": child.end_lineno,
                                "scope": scope, "autouse": autouse})
                visit(child, prefix + child.name + ".")
            elif isinstance(child, ast.ClassDef):
                visit(child, prefix + child.name + ".")

    visit(tree)
    return out


def fixture_arg_names(path):
    """Return list of (test_name_or_fixture, line, [fixture params])."""
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src, filename=path)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            if node.name.startswith("test_") or any(
                (isinstance(d, ast.Attribute) and d.attr == "fixture") or
                (isinstance(d, ast.Name) and d.id == "fixture") or
                (isinstance(d, ast.Call) and isinstance(
                    (d.func if isinstance(d.func, ast.Attribute) else d.func), ast.Name)
                 and getattr(d.func, "attr", getattr(d.func, "id", "")) in ("fixture",))
                for d in node.decorator_list
            ):
                out.append((node.name, node.lineno, args))
    return out
