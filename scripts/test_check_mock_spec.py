"""Tests for scripts/check-mock-spec.py (WP4.2).

The gate: an unspecced-but-convertible mock-patch site is a licensed
exception, not a default. Measurement lives HERE (the classifier is reused
from autospec-sweep.py, so the gate can never disagree with the sweep about
what "convertible" means); enforcement rides the WP1.3 ratchet via the
census's `unspecced_patch` category -- so these tests cover both faces:

  * the measurer: what counts as a site, and the drift-resistant id shape
    (file::scope::kN -- line numbers drift the moment anyone inserts a
    import; the WP4.1 gate-collateral commits proved file:line registry ids
    rot under batch edits, so the ratchet's new category must not repeat it)
  * the staged fast-path: the pre-commit hook sees the ADDED lines only --
    the tree legitimately carries hundreds of licensed sites, so a whole-file scan
    would block every commit touching one
  * the done-when, end to end: adding an unspecced patch() to a tree whose
    baseline+registry were minted WITHOUT it fails ratchet-check naming the
    new id (the WP1.3 machinery, not a parallel mechanism).

Run: uv run pytest scripts/test_check_mock_spec.py -q  (wired into ci.yml's
collection-sanity gate-tests step alongside the other scripts/test_*.py).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE = REPO_ROOT / "scripts" / "check-mock-spec.py"
RATCHET = REPO_ROOT / "scripts" / "ratchet-check.py"


def gate(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )


def scan(root: Path) -> list[dict]:
    r = gate("--locations", "--root", str(root))
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def tree(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
    return tmp_path


# ---------------------------------------------------------------- measurer


def test_convertible_unspecced_site_is_reported(tmp_path):
    root = tree(
        tmp_path,
        {
            "backend/tests/unit/test_a.py": (
                "from unittest import mock\n"
                "def test_x():\n"
                "    with mock.patch('backend.core.config.get_settings') as s:\n"
                "        assert s\n"
            )
        },
    )
    locs = scan(root)
    assert [it["id"] for it in locs] == ["backend/tests/unit/test_a.py::test_x::k1"]


def test_speced_and_refused_forms_are_not_sites(tmp_path):
    """Only autospec-sweep's `convertible` set is a site: an autospec'd
    (or spec/spec_set'd) call is compliant; new=/new_callable=/patch.dict/
    bare-name/f-string targets are `na` the sweep itself refuses to touch --
    licensing them here would double-register what the sweep adjudicates."""
    root = tree(
        tmp_path,
        {
            "backend/tests/unit/test_a.py": (
                "from unittest import mock\n"
                "from unittest.mock import AsyncMock\n"
                "def test_x():\n"
                "    with mock.patch('a.b.c', autospec=True):\n"
                "        pass\n"
                "    with mock.patch('a.b.d', spec=int):\n"
                "        pass\n"
                "    with mock.patch('a.b.e', new=object()):\n"
                "        pass\n"
                "    with mock.patch('a.b.f', new_callable=AsyncMock):\n"
                "        pass\n"
                "    with mock.patch.dict('a.b.g', {}):\n"
                "        pass\n"
                "    with mock.patch('bare_name'):\n"
                "        pass\n"
                "    t = 'a.b.h'\n"
                "    with mock.patch(t):\n"
                "        pass\n"
            )
        },
    )
    assert scan(root) == []


def test_ids_are_drift_resistant_and_unique(tmp_path):
    """Inserting an import line above the site must not re-mint its id (the
    registry pairs by id; line-keyed ids rot under ordinary edits), while
    two sites in one scope get distinct ordinals in line order."""
    src = (
        "from unittest import mock\n"
        "def test_x():\n"
        "    mock.patch('a.b.c')\n"
        "    mock.patch('a.b.d')\n"
        "class TestY:\n"
        "    def test_z(self):\n"
        "        mock.patch('a.b.e')\n"
    )
    root = tree(tmp_path, {"backend/tests/unit/test_a.py": src})
    before = [it["id"] for it in scan(root)]
    assert before == [
        "backend/tests/unit/test_a.py::test_x::k1",
        "backend/tests/unit/test_a.py::test_x::k2",
        "backend/tests/unit/test_a.py::TestY.test_z::k1",
    ]
    shifted = "\n".join(["# a comment inserted above", *src.splitlines()])
    (root / "backend/tests/unit/test_a.py").write_text(shifted + "\n")
    assert [it["id"] for it in scan(root)] == before


def test_module_level_site_id(tmp_path):
    root = tree(
        tmp_path,
        {"backend/tests/unit/test_a.py": ("from unittest import mock\nmock.patch('a.b.c')\n")},
    )
    assert [it["id"] for it in scan(root)] == ["backend/tests/unit/test_a.py::k1"]


def test_count_matches_locations(tmp_path):
    root = tree(
        tmp_path,
        {
            "backend/tests/unit/test_a.py": (
                "from unittest import mock\ndef t():\n    mock.patch('a.b.c')\n"
                "    mock.patch('a.b.d', autospec=True)\n"
            )
        },
    )
    r = gate("--count", "--root", str(root))
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "1"


# ------------------------------------------------------- R-5 arity (WP2.4c)
#
# `autospec=True` on a callable that takes NO arguments buys essentially
# nothing: there is no signature to get wrong, so the drift class Phase 4
# exists to kill cannot re-enter through it. R-5 retires those sites from
# the count — which LOWERS the baseline, honestly. The retirement is earned
# per site by a resolver, so the gate needs three properties:
#   * arity is measured from the TARGET's def, followed through the test
#     module's imports (patch-at-use-site: `from backend.api.routes.system
#     import get_settings` patches backend.api.routes.system.get_settings,
#     whose def lives in backend/core/config.py);
#   * anything the resolver cannot prove is KEPT (unresolved, varargs,
#     required params, third-party targets) — the count may only fall on
#     evidence, never on a guess;
#   * the decision rides the census/ratchet category count, not a parallel
#     mechanism.


def test_zero_arity_site_is_retired_from_the_count(tmp_path):
    """A patch of a 0-parameter, no-varargs function is not counted: there
    is no signature for autospec to pin, so the suppression buys nothing."""
    root = tree(
        tmp_path,
        {
            "backend/core/db.py": "def init_redis():\n    return None\n",
            "backend/tests/unit/test_a.py": (
                "from unittest import mock\n"
                "from backend.core.db import init_redis\n"
                "def test_x():\n"
                "    with mock.patch('backend.core.db.init_redis') as m:\n"
                "        assert m\n"
            ),
        },
    )
    assert scan(root) == []
    r = gate("--count", "--root", str(root))
    assert r.stdout.strip() == "0"


def test_zero_arity_resolved_through_the_import_at_the_use_site(tmp_path):
    """patch() targets the attribute ON THE IMPORTED MODULE, but the def may
    live elsewhere; following the import is what makes the verdict provable."""
    root = tree(
        tmp_path,
        {
            "backend/core/config.py": "def get_settings():\n    return 1\n",
            "backend/api/routes/system.py": (
                "from backend.core.config import get_settings\n\nsettings = get_settings\n"
            ),
            "backend/tests/unit/test_a.py": (
                "from unittest import mock\n"
                "def test_x():\n"
                "    with mock.patch('backend.api.routes.system.get_settings') as s:\n"
                "        assert s\n"
            ),
        },
    )
    assert scan(root) == []


def test_sites_with_required_params_are_kept(tmp_path):
    """The pair-side: arity ≥ 1 is exactly where autospec has teeth, so the
    site stays licensed."""
    root = tree(
        tmp_path,
        {
            "backend/core/db.py": "def connect(dsn, timeout=5):\n    return None\n",
            "backend/tests/unit/test_a.py": (
                "from unittest import mock\n"
                "def test_x():\n"
                "    with mock.patch('backend.core.db.connect') as m:\n"
                "        assert m\n"
            ),
        },
    )
    assert [it["id"] for it in scan(root)] == ["backend/tests/unit/test_a.py::test_x::k1"]


def test_unresolved_targets_are_kept(tmp_path):
    """A count may only fall on evidence. A target the resolver cannot
    resolve — a module absent from the tree, a name it cannot follow — is
    kept, never assumed harmless."""
    root = tree(
        tmp_path,
        {
            "backend/tests/unit/test_a.py": (
                "from unittest import mock\ndef t():\n    mock.patch('a.b.c')\n"
            )
        },
    )
    assert [it["id"] for it in scan(root)] == ["backend/tests/unit/test_a.py::t::k1"]


def test_varargs_and_class_targets_are_kept(tmp_path):
    """`def f(*a)` accepts anything — autospec buys nothing but the
    retirement claim is about callables with a provably empty signature;
    likewise a patched CLASS whose __init__ takes args."""
    root = tree(
        tmp_path,
        {
            "backend/core/db.py": (
                "def wide(*args, **kwargs):\n    return None\n\n\n"
                "class Pool:\n    def __init__(self, dsn):\n        self.dsn = dsn\n"
            ),
            "backend/tests/unit/test_a.py": (
                "from unittest import mock\n"
                "def test_x():\n"
                "    mock.patch('backend.core.db.wide')\n"
                "    mock.patch('backend.core.db.Pool')\n"
            ),
        },
    )
    assert len(scan(root)) == 2


# ------------------------------------------------------------- staged mode

GIT = ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false"]
BASE = (
    "from unittest import mock\n"
    "def test_x():\n"
    "    mock.patch('a.b.c')\n"  # licensed pre-existing site, line 3
)


def git_repo(tmp_path: Path) -> Path:
    root = tree(tmp_path, {"backend/tests/unit/test_a.py": BASE})
    for c in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "base"]):
        subprocess.run([*GIT, *c], cwd=root, check=True, capture_output=True)
    return root


def test_staged_flags_only_added_sites(tmp_path):
    """Editing a file that ALREADY carries a licensed site must not block
    the commit; a NEW unspecced site in the same file must."""
    root = git_repo(tmp_path)
    ok = BASE + "def test_y():\n    mock.patch('a.b.d', autospec=True)\n"
    (root / "backend/tests/unit/test_a.py").write_text(ok)
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True, capture_output=True)
    r = gate("--staged", "--root", str(root), "backend/tests/unit/test_a.py", cwd=root)
    assert r.returncode == 0, f"licensed site blocked a clean commit:\n{r.stderr}"

    bad = BASE + "def test_y():\n    mock.patch('a.b.d')\n"
    (root / "backend/tests/unit/test_a.py").write_text(bad)
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True, capture_output=True)
    r = gate("--staged", "--root", str(root), "backend/tests/unit/test_a.py", cwd=root)
    assert r.returncode == 1
    assert "backend/tests/unit/test_a.py::test_y::k1" in r.stderr
    assert "test_x::k1" not in r.stderr  # the licensed line is not re-flagged


def test_staged_new_file_counts_whole_file(tmp_path):
    root = git_repo(tmp_path)
    (root / "backend/tests/unit/test_b.py").write_text(
        "from unittest import mock\ndef t():\n    mock.patch('a.b.x')\n"
    )
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True, capture_output=True)
    r = gate("--staged", "--root", str(root), "backend/tests/unit/test_b.py", cwd=root)
    assert r.returncode == 1
    assert "test_b.py::t::k1" in r.stderr


def test_staged_mode_works_in_a_linked_worktree(tmp_path):
    """A linked worktree's ``.git`` is a pointer FILE, not a directory — a
    staging path of ``root/.git/...`` raises NotADirectoryError and crashes
    the hook (it did, on the fix/registry-drift-check worktree commit). The
    crash was indistinguishable from a real gate failure (both rc 1), so a
    worktree commit could never land. The gate must use a real temp dir."""
    main = git_repo(tmp_path)
    wt = tmp_path / "wt"
    subprocess.run(
        [*GIT, "worktree", "add", "-q", "--detach", str(wt)],
        cwd=main,
        check=True,
        capture_output=True,
    )
    assert wt.joinpath(".git").is_file()  # the pointer-file premise
    (wt / "backend/tests/unit/test_c.py").write_text(
        "from unittest import mock\ndef t():\n    mock.patch('a.b.x')\n"
    )
    subprocess.run([*GIT, "add", "-A"], cwd=wt, check=True, capture_output=True)
    r = gate("--staged", "--root", str(wt), "backend/tests/unit/test_c.py", cwd=wt)
    assert r.returncode == 1, r.stderr
    assert "UNSPECCED MOCK" in r.stderr, f"gate crashed instead of flagging:\n{r.stderr}"
    assert "NotADirectoryError" not in r.stderr


# ------------------------------------------------- the ratchet done-when


def test_ratchet_fails_on_sneaked_unspecced_site(tmp_path):
    """THE PLAN's done-when, through the WP1.3 machinery: mint baseline +
    registry on a clean tree, then add an unspecced patch() -> the ratchet
    exits 1 naming the category and the new id (UNREGISTERED + RATCHET)."""
    import yaml

    root = tree(
        tmp_path,
        {
            "scripts/collection-sanity-allowlist.txt": "",
            ".github/flake-allowlist.yml": "flakes: []\n",
            "frontend/vite.config.ts": (
                "export default defineConfig({test: {exclude: [...configDefaults.exclude]}})\n"
            ),
            "scripts/validate.sh": "#!/usr/bin/env bash\npytest backend/tests/unit\n",
            "pyproject.toml": '[tool.coverage.run]\nomit = ["backend/tests/*"]\n',
            "backend/tests/unit/test_a.py": (
                "from unittest import mock\n"
                "def test_ok():\n"
                "    mock.patch('a.b.c', autospec=True)\n"
            ),
        },
    )
    r = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "suppression-census.py"),
            "--root",
            str(root),
            "--locations",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    loc = json.loads(r.stdout)
    assert "unspecced_patch" in loc
    assert loc["unspecced_patch"] == []
    baseline = {cat: len(items) for cat, items in loc.items()}
    registry = {
        cat: [
            {
                "id": it["id"],
                "kind": "environment",
                "owner": "tester",
                "tracking": None,
                "expires": None,
                "reason": it["reason"] or None,
            }
            for it in items
        ]
        for cat, items in loc.items()
    }
    (root / ".github").mkdir(exist_ok=True)
    (root / ".github/suppression-baseline.json").write_text(json.dumps(baseline, indent=2))
    (root / ".github/suppression-registry.yml").write_text(yaml.dump(registry, sort_keys=False))

    green = subprocess.run(
        [sys.executable, str(RATCHET), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert green.returncode == 0, green.stderr

    (root / "backend/tests/unit/test_a.py").write_text(
        "from unittest import mock\n"
        "def test_ok():\n"
        "    mock.patch('a.b.c', autospec=True)\n"
        "def test_sneaked():\n"
        "    mock.patch('a.b.evil')\n"
    )
    red = subprocess.run(
        [sys.executable, str(RATCHET), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert red.returncode == 1
    assert "unspecced_patch" in red.stderr
    assert "test_a.py::test_sneaked::k1" in red.stderr


# --------------------------------------------------------- real-tree seed


@pytest.mark.timeout(180)  # two real-tree AST scans (~30s); tier default is 5s
def test_real_tree_category_is_seeded_and_green():
    """The census, the seeded baseline and the gate must agree on the residual
    count (322 at WP4.2's seed, 233 after WP2.4c R-5 fall), or every CI run
    fails at the ratchet."""
    r = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "suppression-census.py")],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    counts = json.loads(r.stdout)
    baseline = json.loads((REPO_ROOT / ".github/suppression-baseline.json").read_text())
    assert counts["unspecced_patch"] == baseline["unspecced_patch"], (
        "census/seed drift -- counts may only fall via --update, a rise is a "
        "hand-adjudicated registry commit"
    )
    gate_rc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check-mock-spec.py"), "--count"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    assert int(gate_rc.stdout) == counts["unspecced_patch"]
