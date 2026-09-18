#!/usr/bin/env python3
"""WP4.3 DECIDE inventory: per-module assertion density (static AST, no pytest).
For each candidate production module under backend/services|api/routes:
  loc, mutants-proxy ops (crude: AST nodes mutmut rewrites), tests that import it,
  assert-statement count across those test files, asserts per production kloc."""
import ast, sys, json
from pathlib import Path
root = Path("/agents/agent-nemo2/workspace")
sys.path.insert(0, str(root))

# which production modules
prods = sorted((root/"backend/services").rglob("*.py")) + sorted((root/"backend/api/routes").rglob("*.py"))
# which test files, with their asserts + import text
tests = sorted((root/"backend/tests").rglob("test_*.py"))
tdata = []
for tp in tests:
    try: src = tp.read_text()
    except OSError: continue
    try: tree = ast.parse(src)
    except SyntaxError: continue
    na = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Assert))
    # pytest-style: assertions inside test funcs; also count pytest.raises
    nr = sum(1 for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", "")) == "raises")
    imports = {l.strip() for l in src.splitlines() if "import" in l}
    tdata.append((tp, src, na + nr))

def refs(module_name):
    hits = 0; asserts = 0
    needle_d = f"backend.{('services' if '/services/' in '' else '')}"  # unused
    for tp, src, na in tdata:
        # module referenced by import line mentioning the bare module name,
        # or by patch()-target strings
        if any(("." + module_name + " " in i or "." + module_name + "." in i or "." + module_name + "," in i
                or i.rstrip().endswith("." + module_name) or f'"{module_name}' in i or f"'{module_name}" in i
                or f".{module_name}." in i or f".{module_name})" in i or f".{module_name}" in i)
               for i in src.splitlines() if "import" in i or "patch" in i):
            hits += 1; asserts += na
    return hits, asserts

def opcount(p):
    try: tree = ast.parse(p.read_text())
    except (SyntaxError, OSError): return -1
    # crude mutmut-operator proxy: comparison ops, boolean ops, constants, unary not, arithmetic
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.Compare, ast.BoolOp, ast.UnaryOp)): n += 1
        elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float, str, bool)) and not isinstance(node.value, type(None)): n += 1
    return n

rows = []
for p in prods:
    if p.name == "__init__.py": continue
    loc = len(p.read_text().splitlines())
    hits, asserts = refs(p.stem)
    rows.append({"module": p.relative_to(root).as_posix(), "loc": loc, "ops": opcount(p),
                 "testfiles": hits, "asserts": asserts,
                 "asserts_per_kloc": round(asserts*1000/loc) if loc else 0})
rows.sort(key=lambda r: -r["ops"])
print(json.dumps(rows, indent=1))
