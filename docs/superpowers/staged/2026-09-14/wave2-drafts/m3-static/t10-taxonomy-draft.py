#!/usr/bin/env python3
"""M3 Task 10 taxonomy draft — READ-ONLY static classifier for backend/tests/integration.

Pure stdlib AST + filename rules. Reads NOTHING but files. NEVER runs pytest.

Emits (stdout, markdown-ready):
  A. inventory census of integration/ files (top-level flat vs existing subdirs)
  B. filename-mapable moves into EXISTING subdirs (audit 5.4's 71-class rule)
  C. never-touch-DB candidates via transitive fixture-dependency resolution
     (audit 5.1's 19.8% regeneration, at FILE granularity)
  D. the uncategorized remainder map (DECISION-NEEDED: owner category map)

Transitive rule: a file is "db-shaped" if ANY of its test functions
  - takes a param naming a known DB/HTTP-boundary fixture, OR
  - takes a param naming a fixture that (transitively, via the conftest
    dependency graph rooted at this file's directory) reaches such a fixture,
  - or the file itself references get_session/init_db/TestClient/httpx/
    app_client/AsyncClient etc. in module code (I/O in test bodies without
    fixture params).
"""
import ast
import os
import re
import sys
from collections import defaultdict

REPO = "/agents/agent-nemo2/workspace"
INT = os.path.join(REPO, "backend/tests/integration")

# ---------------------------------------------------------------- fixture graph
DB_FIXTURES = {
    "integration_db", "integration_env", "client", "test_db", "isolated_db",
    "session", "db_session", "worker_database", "template_database", "test_db_url",
    "worker_db_url", "async_client", "authenticated_client", "authenticated_async_client",
    "admin_client", "client_factory", "db_ready", "redis_client",
}
IO_PAT = re.compile(
    r"\b(get_session|AsyncSession|TestClient|AsyncClient|httpx\.|app_client|"
    r"client\.(get|post|put|delete|patch)\(|init_db|create_all|"
    r"AsyncSessionLocal|session\.execute|session\.add|session\.commit|session\.flush)\b")

def fixture_defs_in(path):
    """name -> set(param names) for a conftest/module."""
    try:
        tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    except (SyntaxError, OSError):
        return {}
    out = {}

    def is_fix(n):
        for d in n.decorator_list:
            t = d.func if isinstance(d, ast.Call) else d
            if (isinstance(t, ast.Attribute) and t.attr == "fixture") or \
               (isinstance(t, ast.Name) and t.id == "fixture"):
                return True
        return False

    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and is_fix(n):
            out[n.name] = [a.arg for a in n.args.args if a.arg not in ("self", "request", "event_loop", "config")]
    return out

def conftest_chain(rel_dir):
    """conftest files from ROOT tests dir down to rel_dir (nearest last)."""
    parts = []
    root = os.path.join(REPO, "backend/tests")
    cur = rel_dir
    chain = []
    dirs = []
    while True:
        d = os.path.relpath(cur, root) if cur != root else "."
        dirs.append((d, os.path.join(cur, "conftest.py")))
        if cur == root:
            break
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    for d, p in reversed(dirs):
        if os.path.exists(p):
            chain.append((d, fixture_defs_in(p)))
    return chain

def resolve_fixture(name, chain, local):
    """nearest-wins lookup; returns list of param deps or None if unknown."""
    if name in local:
        return local[name]
    for _d, defs in reversed(chain):
        if name in defs:
            return defs[name]
    return None

def file_profile(path):
    rel_dir = os.path.dirname(path)
    chain = conftest_chain(rel_dir)
    try:
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src, filename=path)
    except (SyntaxError, OSError) as e:
        return {"error": str(e)}
    local = fixture_defs_in(path)
    n_tests = 0
    db_tests = 0
    seen_io = bool(IO_PAT.search(re.sub(r'"""[\s\S]*?"""|"[^"\n]*"|\'[^\'\n]*\'', "", src)))
    memo = {}

    def reaches_db(name, stack):
        if name in DB_FIXTURES:
            return True
        if name in memo:
            return memo[name]
        if name in stack:
            return False
        params = resolve_fixture(name, chain, local)
        if params is None:
            return False
        memo[name] = False  # guard
        r = any(reaches_db(p, stack | {name}) for p in params)
        memo[name] = r
        return r

    def top_tests(tree):
        out = []
        for n in ast.iter_child_nodes(tree):
            if isinstance(n, ast.FunctionDef) or isinstance(n, ast.AsyncFunctionDef):
                if n.name.startswith("test_"):
                    out.append(n)
            elif isinstance(n, ast.ClassDef):
                for m in ast.iter_child_nodes(n):
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith("test_"):
                        out.append(m)
        return out

    for f in top_tests(tree):
        n_tests += 1
        if any(reaches_db(a.arg, frozenset()) for a in f.args.args):
            db_tests += 1
    return {"n_tests": n_tests, "db_tests": db_tests, "io_in_code": seen_io}

# ---------------------------------------------------------------- filename map
EXISTING = [d for d in os.listdir(INT) if os.path.isdir(os.path.join(INT, d)) and d != "__pycache__"]

def map_filename(name):
    stem = name[:-3]
    if re.search(r"_api\.py$", name) or re.match(r"test_[a-z0-9_]*_api\.py$", name):
        return "api"
    if "service" in stem:
        return "services"
    if re.search(r"websocket|broadcast", stem):
        return "websocket"
    if re.search(r"database|^test_db_|_db_|db_", stem):
        return "database"
    if "model" in stem and "models" not in stem:
        return "models"
    return None

def main():
    all_files = []
    for dp, dn, fs in os.walk(INT):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for fn in fs:
            if fn.startswith("test_") and fn.endswith(".py"):
                all_files.append(os.path.join(dp, fn))
    top = [p for p in all_files if os.path.dirname(p) == INT]
    sub = [p for p in all_files if os.path.dirname(p) != INT]
    print("## A. inventory")
    print("total test files under integration/: %d" % len(all_files))
    print("top-level flat: %d   in existing subdirs: %d" % (len(top), len(sub)))
    print("existing subdirs: %s" % ", ".join(sorted(EXISTING)))

    print("\n## B. filename-mapable (top-level -> existing subdir)")
    mapped = {}
    unmapped = []
    for p in sorted(top):
        d = map_filename(os.path.basename(p))
        if d:
            mapped.setdefault(d, []).append(os.path.basename(p))
        else:
            unmapped.append(p)
    for d in sorted(mapped):
        print("- -> %s/ (%d): %s" % (d, len(mapped[d]), ", ".join(mapped[d])))
    print("mapped total: %d   unmapped remainder: %d" %
          (sum(len(v) for v in mapped.values()), len(unmapped)))

    print("\n## C. never-touch-DB candidates (file-level, transitive fixture closure)")
    never = []
    for p in sorted(all_files):
        prof = file_profile(p)
        if prof.get("error"):
            print("  [PARSE-ERROR] %s" % os.path.relpath(p, INT))
            continue
        if prof["n_tests"] and prof["db_tests"] == 0 and not prof["io_in_code"]:
            never.append((os.path.relpath(p, INT), prof["n_tests"]))
    print("files with zero DB/HTTP-boundary reachability: %d (of %d scanned)" % (len(never), len(all_files)))
    for rel, n in never:
        print("  - %s  (%d tests)" % (rel, n))

    print("\n## D. uncategorized remainder (DECISION-NEEDED owner map)")
    # heuristic proposal buckets, flagged as proposals only
    BUCKETS = [
        ("alerts/dedup", r"alert|dedup|notification"),
        ("cache", r"cache|redis_streams|invalidat"),
        ("backup/dr", r"backup|restore|disaster|failover|recovery|replica"),
        ("auth", r"auth|admin|api_key|permission|rbac"),
        ("dlq/queue", r"dlq|dead.?letter|queue|stream"),
        ("analytics/metrics", r"analytic|metric|latency|performance|collector|throughput"),
        ("audit", r"audit"),
        ("baseline", r"baseline"),
        ("system/infra", r"system|health|config|setup|startup|lifespan|process|worker|supervisor"),
        ("video/media", r"video|media|stream_rtsp|snapshot|frame|camera_feed"),
        ("events", r"event|search|export|replay"),
        ("models/entities", r"camera|detection|zone|household|face|person|vehicle|pet"),
        ("messaging/mqtt", r"mqtt|pubsub|notify"),
    ]
    proposal = defaultdict(list)
    for p in unmapped:
        b = os.path.basename(p)
        stem = b[:-3]
        for label, pat in BUCKETS:
            if re.search(pat, stem):
                proposal[label].append(b)
                break
        else:
            proposal["UNPROPOSED (needs owner naming)"].append(b)
    for label in sorted(proposal):
        print("- %s (%d): %s" % (label, len(proposal[label]), ", ".join(sorted(proposal[label]))))
    print("\nremainder total: %d" % len(unmapped))

if __name__ == "__main__":
    main()
