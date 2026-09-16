"""Route-mount completeness (WP1.5).

/api/backup was implemented, unit-tested, and NEVER MOUNTED — a production
404 no test caught (fixed at backend/main.py:1462; the unit tests passed
because they exercised the router object, not the app). Nothing else prevents
the identical defect for the next router, so this test is the prevention:

  every module-level `X = APIRouter(...)` assignment in backend/api/routes/
  must appear in an `app.include_router(<module>.X)` call in backend/main.py,
  or be listed in ALLOWLIST below with a reason.

Attribution is AST-based, not introspective: an APIRouter *instance* reports
__module__ == "fastapi.routing", so runtime inspection cannot tell a
locally-defined router from a cross-module re-export. The assignment site can.

Done-when (verified while writing this): commenting out any one
include_router line makes this suite fail, naming that router — with the
single honest exception of the redirect routers below, which mount via their
canonical names.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTES_DIR = REPO_ROOT / "backend" / "api" / "routes"
MAIN = REPO_ROOT / "backend" / "main.py"

# Legitimate exceptions — each carries its WHY; adding to this list is a
# deliberate, reviewable act, the failure mode this file exists to police.
# None are needed today: all 65 module-level routers are mounted. If one
# lands here in a future diff, read the reason before believing it.
ALLOWLIST: dict[str, str] = {}


def _module_level_routers() -> set[str]:
    """{f"{module}.{attr}"} for every top-level NAME = APIRouter(...) assign."""
    routers: set[str] = set()
    for path in sorted(ROUTES_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        for node in ast.parse(path.read_text()).body:  # .body = top level only
            if not isinstance(node, ast.Assign):
                continue
            value = node.value
            if not (isinstance(value, ast.Call) and _dotted(value.func).endswith("APIRouter")):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    routers.add(f"{path.stem}.{target.id}")
    return routers


def _dotted(node: ast.expr) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _mounted_routers() -> set[str]:
    """{f"{module}.{attr}"} for every app.include_router(<module>.<attr>) call.

    main.py imports route modules bare (`from backend.api.routes import
    alerts`), so the first attribute segment IS the module name. A mount with
    a non-attribute argument cannot be attributed — it must not pass silently.
    """
    mounted: set[str] = set()
    for node in ast.walk(ast.parse(MAIN.read_text())):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "include_router"
            and node.args
        ):
            arg = node.args[0]
            if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name):
                mounted.add(f"{arg.value.id}.{arg.attr}")
            else:  # dynamic/computed mount — unattributable, loud not silent
                pytest.fail(
                    f"main.py mounts a router this test cannot attribute: "
                    f"{ast.dump(arg)[:120]} — rewrite it as <module>.<router> or "
                    "extend this test deliberately"
                )
    return mounted


def test_every_defined_router_is_mounted():
    """THE test: a defined-but-unmounted router is the /api/backup 404."""
    defined = _module_level_routers()
    mounted = _mounted_routers()
    orphans = sorted(defined - mounted - set(ALLOWLIST))
    assert not orphans, (
        "router(s) defined in backend/api/routes/ but never include_router'd "
        f"in backend/main.py: {orphans} — mount them (an unmounted router is "
        "a production 404 that unit tests CANNOT see) or justify each in "
        "ALLOWLIST with a reason"
    )


def test_allowlist_entries_are_still_defined():
    """A zombie allowlist entry launders a future rename into 'excepted'."""
    defined = _module_level_routers()
    zombies = sorted(set(ALLOWLIST) - defined)
    assert not zombies, f"ALLOWLIST entries no longer defined anywhere: {zombies}"


def test_mount_count_matches_main_py_source():
    """The AST walk and the source must agree on how many mounts exist —
    guards the test's own machinery against an ast-walk blind spot (e.g. a
    mount inside a comprehension the walk's shape check would skip)."""
    source_count = MAIN.read_text().count(".include_router(")
    assert len(_mounted_routers()) == source_count, (
        f"main.py has {source_count} include_router call sites but this test "
        f"attributed {len(_mounted_routers())} — the test's parser missed one, "
        "fix the parser (an unattributed mount is an unpoliced router)"
    )


def test_the_test_bites():
    """Done-when, mechanically: commenting out an include_router line makes
    the check fail naming it. Synthesized here (main.py is never touched);
    verified by hand during WP1.5 against the real file."""
    defined = _module_level_routers()
    mounted = _mounted_routers()
    assert mounted >= defined - set(ALLOWLIST)  # sane baseline holds
    victim = "backup.router"  # THE historical defect object
    assert victim in defined and victim in mounted
    unmounted = sorted(defined - (mounted - {victim}))
    assert unmounted == [victim], (
        "removing a mount from the mounted set must leave exactly that router "
        f"orphaned; got {unmounted} — the test would NOT bite"
    )
