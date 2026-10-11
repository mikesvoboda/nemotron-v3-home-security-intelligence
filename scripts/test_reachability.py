#!/usr/bin/env python3
"""Tests for scripts/reachability.py (O2.3 / plan 01 §M1).

Run explicitly; outside testpaths (like every scripts/test_*.py gate suite):

    uv run python -m pytest scripts/test_reachability.py -q

The walker decides which modules SHIP, and the whole programme (M2 scoring,
R-surface deletions) reads that verdict, so the tests pin the MODEL, not just
the arithmetic — the four discriminations §M1 names:

  * name-level re-exports: a package __init__ that re-exports two names, only
    one of which anyone asks for, ships ONE sub. A package-level walk ships
    both — this is the 00 §4.1 defect (services/__init__.py imports 56 subs,
    re-exports 274 names, "hides the dead modules from a package-level scan").
  * TYPE_CHECKING imports do NOT ship (erased at runtime; counting them would
    call dead modules live exactly like the package-level sin);
  * function-level imports DO ship (they execute whenever the function runs);
  * string/dynamic imports ship only through the entry_points.toml allowlist
    (an un-allowlisted literal is reported unresolved, never silently shipped
    and never silently dropped).

Plus the machinery pins: tests are never candidates (they leave with their
modules), keep-list entries ship by declaration and report as hits, and the
real-tree Done-when: redis_json / scenario_classifier / managed_service /
orphan_cleanup_service NOT shipping, vlm_analyzer and backend/evaluation
shipping. managed_service is the sharpest of the six: its ONLY non-test
importer is services/__init__.py's re-export line, so it is simultaneously
"imported" (package-level walk: alive) and dead (name-level walk: ships
nothing). A walker that gets the model wrong cannot pass both halves.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "reachability.py"
ENTRY_TOML = REPO_ROOT / "scripts" / "reachability" / "entry_points.toml"
KEEP_TOML = REPO_ROOT / "scripts" / "reachability" / "keep.toml"


def _load():
    spec = importlib.util.spec_from_file_location("reachability", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


reach = _load()


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


# ---------------------------------------------------------------- fixtures --


@pytest.fixture
def fixture_root(tmp_path: Path) -> Path:
    """A mini repo exercising all four discriminations at once.

    Tree (all under pkg/, declared the only candidate dir):

      pkg/main.py          entry; asks for keep_name from pkg, imports
                           func_needs via a function body, __import__()'s the
                           dyn module by string (allowlist decides), and does
                           a TYPE_CHECKING-only import of tc_only.
      pkg/__init__.py      re-exports keep_name from live_sub and
                           unused_name from dead_sub.
      pkg/live_sub.py      defines keep_name.
      pkg/dead_sub.py      defines unused_name — nobody asks the package for
                           it, so a name-level walk must leave it out.
      pkg/func_mod.py      reached only from a function body.
      pkg/dyn_mod.py       reached only via importlib.import_module("pkg.dyn_mod").
      pkg/tc_only.py       reached only under if TYPE_CHECKING:.
      pkg/test_helper.py   a test file — never a candidate even if imported.
      pkg/tests/__init__.py, pkg/tests/test_real.py  a tests dir — same.
    """
    r = tmp_path
    _write(
        r,
        "pkg/main.py",
        '"""entry"""\nfrom pkg import keep_name\n\n\ndef go():\n    from pkg.func_mod import helper\n    return helper\n\n\ndef load():\n    import importlib\n    return importlib.import_module("pkg.dyn_mod")\n',
    )
    _write(
        r,
        "pkg/__init__.py",
        "from pkg.live_sub import keep_name\nfrom pkg.dead_sub import unused_name\n",
    )
    _write(r, "pkg/live_sub.py", "keep_name = 'keep'\n")
    _write(r, "pkg/dead_sub.py", "unused_name = 'unused'\n")
    _write(r, "pkg/func_mod.py", "def helper():\n    return 1\n")
    _write(r, "pkg/dyn_mod.py", "VALUE = 42\n")
    # TYPE_CHECKING arm: both the bare-name and typing.-qualified forms.
    _write(
        r,
        "pkg/maybe_tc.py",
        "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    from pkg.tc_only import thing\nelse:\n    thing = None\n",
    )
    _write(r, "pkg/tc_only.py", "thing = 1\n")
    # main.py imports maybe_tc normally; maybe_tc's TYPE_CHECKING arm must
    # not carry tc_only into the shipping set.
    r.joinpath("pkg/main.py").write_text(
        r.joinpath("pkg/main.py").read_text() + "\nfrom pkg.maybe_tc import thing\n"
    )
    _write(r, "pkg/test_helper.py", "HELPER = 1\n")
    _write(r, "pkg/tests/__init__.py", "")
    _write(r, "pkg/tests/test_real.py", "from pkg.test_helper import HELPER\n")
    return r


def _analyze(root: Path, *, allow: tuple[str, ...] = (), keep: tuple[str, ...] = ()):
    return reach.analyze(
        root,
        entries=["pkg/main.py"],
        candidate_dirs=["pkg"],
        keep=list(keep),
        dynamic_allow=list(allow),
    )


def _analyze_tree(root: Path, *, entry: str = "app/main.py", candidate: str = "app"):
    """Same walk over a caller-shaped tree (the ancestor tests use app/)."""
    return reach.analyze(
        root,
        entries=[entry],
        candidate_dirs=[candidate],
        keep=[],
        dynamic_allow=[],
    )


def test_reexport_selectivity_ships_only_the_asked_for_sub(fixture_root):
    """THE 00 §4.1 pin: one requested name out of two re-exports."""
    out = _analyze(fixture_root)
    assert "pkg/live_sub.py" in set(out["shipping"])
    mods_dead = {m["module"] for m in out["not_shipping"]}
    assert "pkg/dead_sub.py" in mods_dead, "package-level walk leaked dead_sub in"


def test_function_level_imports_ship(fixture_root):
    out = _analyze(fixture_root)
    assert "pkg/func_mod.py" in set(out["shipping"])


def test_type_checking_imports_do_not_ship(fixture_root):
    out = _analyze(fixture_root)
    shipping = set(out["shipping"])
    assert "pkg/maybe_tc.py" in shipping  # imported unconditionally
    mods_dead = {m["module"] for m in out["not_shipping"]}
    assert "pkg/tc_only.py" in mods_dead, "TYPE_CHECKING-only import shipped"


def test_string_import_requires_allowlist(fixture_root):
    bare = _analyze(fixture_root)
    mods_dead = {m["module"] for m in bare["not_shipping"]}
    assert "pkg/dyn_mod.py" in mods_dead
    assert bare["unresolved"], "un-allowlisted dynamic import must be reported"

    allowed = _analyze(fixture_root, allow=["pkg.dyn_mod"])
    assert "pkg/dyn_mod.py" in set(allowed["shipping"])
    assert not any("dyn_mod" in u["target"] for u in allowed["unresolved"])


def test_ancestor_packages_of_shipping_modules_ship(tmp_path):
    """O2.3b (ruling 73): importing a module RUNS its parent packages, so a
    parent __init__ can never be listed non-shipping while a module inside it
    ships. Here NOTHING asks `pkg` or `pkg.deep` for a name — the entry dives
    straight to `pkg.deep.mod` — so pre-fix both __init__s were candidates
    reported dead. (fixture_root's pkg/__init__ is demanded BY NAME, so it
    ships through the selective channel and does not exercise this rule.)
    """
    _write(tmp_path, "app/main.py", "import app.deep.mod\n")
    _write(tmp_path, "app/__init__.py", "CONST = 1\n")
    _write(tmp_path, "app/deep/__init__.py", "import app.deep.sibling\n")
    _write(tmp_path, "app/deep/mod.py", "VALUE = 2\n")
    _write(tmp_path, "app/deep/sibling.py", "SIDE = 3\n")
    out = _analyze_tree(tmp_path)
    shipping = set(out["shipping"])
    assert "app/__init__.py" in shipping
    assert "app/deep/__init__.py" in shipping
    # The ancestor ships AS A FILE; its unasked module-level line is still
    # §M1-unshipped — the identical shape to managed_service, which stays
    # dead while the live services/__init__ imports it. The deletion wave
    # (B3.2) removes the line with the module, never the module alone.
    mods_dead = {m["module"] for m in out["not_shipping"]}
    assert "app/deep/sibling.py" in mods_dead


def test_ancestor_ships_whole_but_name_demand_stays_selective(tmp_path):
    """The ruling-73 contrast in ONE tree. `import app.deep.mod` runs
    app/deep/__init__.py outright — the caller holds the namespace, the §M1
    whole-module rule — so EVERY module-level line of that __init__ runs and
    both its imports ship. `from app.shallow import only_this` asks a package
    for ONE name, so §M1 selectivity still holds: only the line binding that
    name ships, the unasked one does not. A fix that collapses into the
    package-level walk (re-lighting managed_service) fails the second arm;
    a fix that only leaf-adds the __init__ file fails the first."""
    _write(
        tmp_path,
        "app/main.py",
        "import app.deep.mod\n\nfrom app.shallow import only_this\n",
    )
    _write(
        tmp_path,
        "app/deep/__init__.py",
        "from app.deep.helper import thing\nfrom app.deep.unrun import other\n",
    )
    _write(tmp_path, "app/deep/mod.py", "VALUE = 1\n")
    _write(tmp_path, "app/deep/helper.py", "thing = 2\n")
    _write(tmp_path, "app/deep/unrun.py", "other = 3\n")
    _write(
        tmp_path,
        "app/shallow/__init__.py",
        "from app.shallow.right import only_this\nfrom app.shallow.wrong import unused\n",
    )
    _write(tmp_path, "app/shallow/right.py", "only_this = 4\n")
    _write(tmp_path, "app/shallow/wrong.py", "unused = 5\n")
    out = _analyze_tree(tmp_path)
    shipping = set(out["shipping"])
    mods_dead = {m["module"] for m in out["not_shipping"]}
    assert "app/deep/__init__.py" in shipping, "ancestor runs; it must ship as a file"
    # …but WHICH of its lines ship is still per-name: the caller asked
    # app.deep for `mod`, not for helper/unrun (same machinery that keeps
    # managed_service dead under the live services/__init__).
    assert "app/deep/helper.py" in mods_dead
    assert "app/deep/unrun.py" in mods_dead
    assert "app/shallow/__init__.py" in shipping, "demanded by name; it executes"
    assert "app/shallow/right.py" in shipping, "the name the caller asked for"
    assert "app/shallow/wrong.py" in mods_dead, (
        "name-level selectivity (§M1) must not collapse into a package-level walk"
    )


def test_tests_are_never_candidates(fixture_root):
    out = _analyze(fixture_root)
    everywhere = set(out["shipping"]) | {m["module"] for m in out["not_shipping"]}
    assert not any(p.startswith("pkg/tests/") or "test_" in p for p in everywhere), (
        "a test module appeared in the candidate census"
    )


def test_keep_list_ships_by_declaration_and_reports_hits(tmp_path):
    _write(tmp_path, "pkg/main.py", "from pkg.app import app\n")
    _write(tmp_path, "pkg/app.py", "app = object()\n")
    _write(tmp_path, "pkg/fake_provider/__init__.py", "")
    _write(tmp_path, "pkg/fake_provider/engine.py", "class Fake:\n    pass\n")
    out = _analyze(tmp_path, keep=["pkg/fake_provider"])
    shipping = set(out["shipping"])
    assert "pkg/fake_provider/engine.py" in shipping, "keep dir must ship its modules"
    assert any("fake_provider" in h for h in out["keep_hits"])
    # a keep entry matching nothing is NOT a hit (a stale keep must be visible)
    out2 = _analyze(tmp_path, keep=["pkg/nothing_here"])
    assert out2["keep_hits"] == []


def test_keep_ships_a_kept_module_s_own_import_edges(tmp_path):
    """A keep line says a module RUNS, so what it imports ships too.

    The block used to stop at ``live.add(rel)``, shipping keep'd modules as
    islands: their imports stayed on the non-shipping list — the OVER-DEAD
    direction, the dangerous one for M2 scoring and B3.2's deletion list.
    """
    _write(tmp_path, "pkg/main.py", "x = 1\n")
    _write(tmp_path, "pkg/fake/__init__.py", "")  # empty: not a candidate
    _write(tmp_path, "pkg/fake/app.py", "from pkg.real.svc import Svc\n")
    _write(tmp_path, "pkg/real/svc.py", "Svc = object()\n")
    _write(tmp_path, "pkg/real/unused.py", "N = 1\n")
    out = _analyze(tmp_path, keep=["pkg/fake"])
    shipping = set(out["shipping"])
    assert "pkg/fake/app.py" in shipping
    assert "pkg/real/svc.py" in shipping, "keep shipped a module but not its import edge"
    # and the sweep must stay selective — keep is not a whole-tree mark
    assert "pkg/real/unused.py" in {m["module"] for m in out["not_shipping"]}


def test_keep_edges_keep_name_level_selectivity(tmp_path):
    """§M1's rule is not an entry-point-only rule: a keep'd file that asks a
    package for ONE of two re-exported names ships one sub, not both."""
    _write(tmp_path, "pkg/main.py", "x = 1\n")
    _write(
        tmp_path,
        "pkg/__init__.py",
        "from pkg.live_sub import keep_name\nfrom pkg.dead_sub import unused_name\n",
    )
    _write(tmp_path, "pkg/live_sub.py", "keep_name = 'keep'\n")
    _write(tmp_path, "pkg/dead_sub.py", "unused_name = 'unused'\n")
    _write(tmp_path, "pkg/fake/app.py", "from pkg import keep_name\n")
    # keep vocabulary is a module stem, not a file path (keep.toml:
    # "backend/ai_contract/fake", no .py) — the matcher appends the suffixes.
    out = _analyze(tmp_path, keep=["pkg/fake/app"])
    assert "pkg/live_sub.py" in set(out["shipping"])
    assert "pkg/dead_sub.py" in {m["module"] for m in out["not_shipping"]}, (
        "keep replayed the package __init__ whole instead of by name"
    )


def test_keep_ships_edges_reaching_out_of_the_kept_dir(tmp_path):
    """A NON-EMPTY kept __init__ is itself a running module: what it imports
    outside its own directory ships too (the real keep entry's
    fake/__init__.py re-exports from app.py the same way)."""
    _write(tmp_path, "pkg/main.py", "x = 1\n")
    _write(tmp_path, "pkg/fake/__init__.py", "from pkg.outside.helper import h\n")
    _write(tmp_path, "pkg/fake/inner.py", "I = 1\n")
    _write(tmp_path, "pkg/outside/helper.py", "def h():\n    return 1\n")
    _write(tmp_path, "pkg/outside/sibling.py", "S = 1\n")
    out = _analyze(tmp_path, keep=["pkg/fake"])
    assert "pkg/outside/helper.py" in set(out["shipping"])
    assert "pkg/outside/sibling.py" in {m["module"] for m in out["not_shipping"]}


def test_line_counts_are_real(tmp_path):
    _write(tmp_path, "pkg/main.py", "x = 1\n")
    body = "\n".join(f"n{i} = {i}" for i in range(37))
    _write(tmp_path, "pkg/dead_body.py", body + "\n")
    out = _analyze(tmp_path)
    row = {m["module"]: m["lines"] for m in out["not_shipping"]}["pkg/dead_body.py"]
    assert row == 37


def test_entry_point_is_itself_a_candidate_and_ships(tmp_path):
    _write(tmp_path, "pkg/main.py", "from pkg.dep import d\n")
    _write(tmp_path, "pkg/dep.py", "d = 1\n")
    out = _analyze(tmp_path)
    assert set(out["shipping"]) == {"pkg/main.py", "pkg/dep.py"}


def test_entry_list_is_what_ci_and_hooks_actually_name():
    """The declared roots must be exactly the NON-TEST scripts named by
    .github/workflows/*.yml or .pre-commit-config.yaml, plus the app roots.

    A stale entries list rots silently in the other direction from a dead
    path: keep it a superset and a deleted script becomes entry_missing
    (visible); allow it to shrink and a NEW gate script's whole import cone
    is misclassified dead (invisible). This re-runs the grep the entries
    header describes, so adding a workflow-invoked script without declaring
    it goes red here. App roots are the §M1 named set, pinned literally.
    """
    named: set[str] = set()
    src = ""
    for wf in (REPO_ROOT / ".github" / "workflows").glob("*.yml"):
        src += wf.read_text(encoding="utf-8")
    src += (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    for m in re.finditer(r"scripts/[A-Za-z0-9_./-]+\.py", src):
        p = m.group(0)
        if Path(p).name.startswith("test_"):
            continue
        named.add(p)
    app_roots = {
        "backend/main.py",
        "ai/gateway/main.py",
        "synthbench/__main__.py",
        "synthbench/cli.py",
    }
    entries, _allow = reach.load_entry_points(ENTRY_TOML)
    declared = set(entries)
    assert app_roots <= declared
    missing = named - declared
    assert not missing, f"CI/hook-named scripts not declared as entries: {sorted(missing)}"
    # every declared script-entry must exist (a deleted script leaves the
    # list with the workflow line that named it — this catches the residue)
    for e in declared:
        assert (REPO_ROOT / e).is_file(), f"declared entry point missing on disk: {e}"


# The four real-tree tests below share the module-scoped real_out walk. A
# first consumer's setup pays the full-tree parse (~1.7s dev, measured; the
# shared anti-rot runner ran it over the 5s pin before the O(n²) call-scan
# fix — job 114166488241, 4 errors at setup). -p randomly makes WHICH
# consumer pays it vary per run, so every consumer carries the mark; the
# 120s is the test_coverage_floors.py precedent value for "mints a real
# artifact, needs headroom", against pyproject global timeout=5.
@pytest.mark.timeout(120)
def test_keep_entries_all_match_a_real_module(real_out):
    """A keep entry matching nothing ships nothing (by design) — but a keep
    list of typos is how a dead keep rots. Real tree: every entry must hit.
    Shares the module-scoped real_out walk: a second full-tree parse here
    would stack two ~2.5s items and lean on the suite's 5s timeout pin."""
    keep = reach.load_keep(KEEP_TOML)
    assert set(real_out["keep_hits"]) == set(keep), (
        f"stale keep entries: {sorted(set(keep) - set(real_out['keep_hits']))}"
    )


# ------------------------------------------------------------- real tree --


@pytest.fixture(scope="module")
def real_out() -> dict:
    entries, allow = reach.load_entry_points(ENTRY_TOML)
    keep = reach.load_keep(KEEP_TOML)
    return reach.analyze(
        REPO_ROOT,
        entries=entries,
        candidate_dirs=["backend", "ai", "synthbench"],
        keep=keep,
        dynamic_allow=allow,
    )


def _matches(shipping_paths: set[str], fragment: str) -> list[str]:
    # fragments are given as module names ("redis_json") or paths
    # ("backend/evaluation"); match file paths by segment/name so the Done-when
    # does not depend on where exactly the module sits.
    frag = fragment.removesuffix(".py")
    hits = []
    for p in shipping_paths:
        stem = p.removesuffix(".py")
        # bare module name ("redis_json": any file whose final segment is it,
        # including __init__ of a module dir) or path prefix ("backend/evaluation")
        if (
            stem == frag
            or stem.endswith("/" + frag)
            or stem.endswith("/" + frag + "/__init__")
            or stem.startswith(frag + "/")
        ):
            hits.append(p)
    return hits


@pytest.mark.timeout(120)  # shares the real_out walk
def test_done_when_not_shipping_modules_are_reported_dead(real_out):
    mods_dead = {m["module"] for m in real_out["not_shipping"]}
    for name in (
        "redis_json",
        "scenario_classifier",
        "managed_service",
        "orphan_cleanup_service",
    ):
        hits = _matches(mods_dead, name)
        assert hits, f"{name} must be reported NOT shipping (found in neither list)"


@pytest.mark.timeout(120)  # shares the real_out walk
def test_done_when_shipping_modules_are_reported_live(real_out):
    shipping = set(real_out["shipping"])
    for name in ("vlm_analyzer", "backend/evaluation"):
        assert _matches(shipping, name), f"{name} must be reported shipping"


@pytest.mark.timeout(120)  # shares the real_out walk
def test_keep_edges_ship_in_the_real_tree(real_out):
    """The same invariant on today's keep.toml, whose one entry is
    backend/ai_contract/fake. fake/app.py:48-49 imports operations and
    provider at module level, so both must ship — before the fix they were
    the list's headline casualties (operations 150, provider 263,
    providers 199, ai_contract/__init__ 45 = 657 lines reported dead next to
    a keep'd module that imports three of them)."""
    shipping = set(real_out["shipping"])
    dead = {m["module"] for m in real_out["not_shipping"]}
    for rel in (
        "backend/ai_contract/operations.py",
        "backend/ai_contract/provider.py",
    ):
        assert rel in shipping, f"{rel} is imported by keep'd fake/app.py"
        assert rel not in dead
    # name-level selectivity still holds on the real tree: providers.py is
    # reached only through ai_contract/__init__, which fake/app.py's edges
    # ask for no names from.
    assert "backend/ai_contract/providers.py" in dead


@pytest.mark.timeout(120)  # shares the real_out walk
def test_output_shape_and_json_round_trip(real_out):
    assert {"shipping", "not_shipping", "keep_hits", "unresolved"} <= set(real_out)
    assert all(isinstance(m["lines"], int) and m["lines"] > 0 for m in real_out["not_shipping"])
    # the tool's contract output must serialize unchanged (CI captures --json)
    assert json.loads(json.dumps(real_out)) == real_out
