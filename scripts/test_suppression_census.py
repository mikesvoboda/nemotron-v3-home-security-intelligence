#!/usr/bin/env python3
"""Tests for scripts/suppression-census.py (WP1.1).

Run explicitly; outside testpaths:

    uv run python -m pytest scripts/test_suppression_census.py -q

The census is the ratchet's measuring stick (WP1.3 gates on these numbers), so
each category is pinned against a synthetic fixture tree with KNOWN counts —
including the edge shapes the spec's raw grep numbers papered over: glob-tree
excludes are not quarantines; decorator spellings (@pytest.mark.skip vs
@mark.skip, bare vs called) all count; plumbing omits don't.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CENSUS = REPO_ROOT / "scripts" / "suppression-census.py"

FIXTURE = {
    # scripts/collection-sanity-allowlist.txt: 2 real, 2 comment/blank
    "scripts/collection-sanity-allowlist.txt": "# header\n\npath/a.py  # TRACK-1\npath/b.py  # TRACK-2\n# trailing comment\n",
    ".github/flake-allowlist.yml": "flakes:\n  - id: t_one\n    tracking: NEM-1\n    expires: 2099-01-01\n",
    "frontend/vite.config.ts": (
        # optimizeDeps-style decoy exclude array (no spread) must not count
        "export default defineConfig({optimizeDeps: {exclude: ['some-pkg']}, test: {\n"
        "  exclude: [\n    ...configDefaults.exclude,\n"
        "    'tests/e2e/**',\n    'tests/contract/**',\n"
        "    'src/a.test.tsx',\n    'src/b.test.tsx',\n    'src/c.test.ts',\n  ],\n}})\n"
    ),
    # Playwright tree: a different runner — its .skip/.only must NOT count
    # (the vitest count is the spec's 54/0/0; e2e suppression is the
    # excluded-trees category's job).
    "frontend/tests/e2e/specs/decoy.spec.ts": "test.skip('e2e hidden', async () => {});\ntest.only('e2e solo', async () => {});\n",
    "scripts/validate.sh": (
        "#!/usr/bin/env bash\n"
        "pytest backend/tests/unit --ignore=backend/tests/load/ "
        "--ignore=backend/tests/benchmarks/ --ignore=backend/tests/e2e/ "
        "--ignore=backend/tests/load/  # dup on purpose\n"
    ),
    "pyproject.toml": (
        "[tool.coverage.run]\n"
        'omit = [\n    "backend/tests/*",\n    "*/__pycache__/*",\n'
        '    "backend/main.py",\n    "backend/api/routes/one.py",\n'
        '    "backend/services/two.py",\n]\n'
    ),
    "backend/tests/unit/test_a.py": (
        "import pytest\n"
        "from pytest import mark\n"
        "@pytest.mark.skip(reason='x')\n"
        "def test_one():\n    pytest.skip('nope')\n"
        "@pytest.mark.skipif(True, reason='y')\n"
        "def test_two():\n    pass\n"
        "@mark.skip(reason='bare-idiom spelling must count')\n"
        "def test_three():\n    pass\n"
    ),
    "backend/tests/unit/test_b.py": (
        "import pytest\n@pytest.mark.xfail(strict=True)\ndef test_four():\n    pytest.skip()\n"
    ),
    "frontend/src/a.test.tsx": "it('x', () => {});\nit.skip('y', () => {});\ndescribe.skip('z', () => {});\n",
    "frontend/src/b.test.ts": "it.only('solo', () => {}); it.todo('later');\n",
    # Identifier noise pins the word-boundary rule: `.onlyErrorsProps`
    # (spread shorthand) and `draft.todos[0]` (property access) matched as
    # .only/.todo on real main test files when the locations regex lacked
    # \b — locations then contradicted the count pass (2/3 vs 0/0).
    "frontend/src/c.test.tsx": (
        "const onlyErrorsProps = { ...p };\nrender(<X {...onlyErrorsProps} />);\n"
        "const todo = draft.todos.find((t) => t.id === id);\n"
        "expect(newState.todos[0].done).toBe(true);\n"
    ),
}

EXPECTED = {
    "collection_allowlist": 2,
    "flake_allowlist": 1,
    "frontend_quarantine": 3,  # glob-tree entries excluded from the count
    "pytest_skip": 2,  # called + bare-idiom spellings
    "pytest_skipif": 1,
    "pytest_xfail": 1,
    "pytest_skip_imperative": 2,
    "frontend_skip": 2,
    "frontend_only": 1,
    "frontend_todo": 1,
    "excluded_test_trees": 3,  # load/benchmarks/e2e, deduped
    "coverage_omit": 2,  # main.py + wildcards are plumbing, not suppressions
}


def build_fixture(tmp_path: Path) -> Path:
    for rel, content in FIXTURE.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
    return tmp_path


def run_census(root: Path) -> dict[str, int]:
    r = subprocess.run(
        [sys.executable, str(CENSUS), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, f"census failed: {r.stderr[-400:]}"
    return json.loads(r.stdout)


def test_fixture_counts(tmp_path):
    root = build_fixture(tmp_path)
    got = run_census(root)
    assert got == EXPECTED, "\n".join(
        f"{k}: got {got.get(k)} want {v}" for k, v in EXPECTED.items() if got.get(k) != v
    )


def test_expect_flag_bites(tmp_path):
    """The CI-stability seam: a stale expectation exits 1 naming the category."""
    root = build_fixture(tmp_path)
    r = subprocess.run(
        [
            sys.executable,
            str(CENSUS),
            "--root",
            str(root),
            "--expect",
            json.dumps({"pytest_skip": 99}),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1
    assert "pytest_skip" in r.stderr


def run_locations(root: Path) -> dict[str, list[dict]]:
    r = subprocess.run(
        [sys.executable, str(CENSUS), "--root", str(root), "--locations"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, f"census --locations failed: {r.stderr[-400:]}"
    return json.loads(r.stdout)


EXPECTED_LOCATIONS = {
    # WP1.2 needs the census to be an INVENTORY, not just a tally — a registry
    # entry must key on a location, and its reason text drives the
    # environment-probe vs TODO classification. These ids pin the identity
    # rules: decorators key file::name (line-number-drift-proof), imperative
    # skips and frontend modifiers file:lineno (no stable enclosing name to
    # key on), reasons are extracted where the syntax carries one.
    "pytest_skip": [
        {"id": "backend/tests/unit/test_a.py::test_one", "reason": "x"},
        {
            "id": "backend/tests/unit/test_a.py::test_three",
            "reason": "bare-idiom spelling must count",
        },
    ],
    "pytest_skipif": [{"id": "backend/tests/unit/test_a.py::test_two", "reason": "y"}],
    "pytest_xfail": [{"id": "backend/tests/unit/test_b.py::test_four", "reason": ""}],
    "pytest_skip_imperative": [
        {"id": "backend/tests/unit/test_a.py:5", "reason": "nope"},
        {"id": "backend/tests/unit/test_b.py:4", "reason": ""},
    ],
    "collection_allowlist": [
        {"id": "path/a.py", "reason": "TRACK-1"},
        {"id": "path/b.py", "reason": "TRACK-2"},
    ],
    "flake_allowlist": [{"id": "t_one", "reason": ""}],
    "frontend_quarantine": [
        {"id": "src/a.test.tsx", "reason": ""},
        {"id": "src/b.test.tsx", "reason": ""},
        {"id": "src/c.test.ts", "reason": ""},
    ],
    # frontend suppression ids key on the test title (two .skip sites on the
    # SAME line must not collide); title-less call sites fall back to line:col
    "frontend_skip": [
        {"id": "frontend/src/a.test.tsx::y", "reason": ""},
        {"id": "frontend/src/a.test.tsx::z", "reason": ""},
    ],
    "frontend_only": [{"id": "frontend/src/b.test.ts::solo", "reason": ""}],
    "frontend_todo": [{"id": "frontend/src/b.test.ts::later", "reason": ""}],
    "excluded_test_trees": [
        {"id": "benchmarks", "reason": ""},
        {"id": "e2e", "reason": ""},
        {"id": "load", "reason": ""},
    ],
    "coverage_omit": [
        {"id": "backend/api/routes/one.py", "reason": ""},
        {"id": "backend/services/two.py", "reason": ""},
    ],
}


def test_locations_inventory(tmp_path):
    """WP1.2 seam: every counted suppression, locatable and classifiable."""
    root = build_fixture(tmp_path)
    got = run_locations(root)
    for cat, want in EXPECTED_LOCATIONS.items():
        assert got.get(cat) == want, f"{cat}: got {got.get(cat)!r} want {want!r}"
    assert sum(len(v) for v in got.values()) == sum(EXPECTED.values())


def test_counts_only_move_with_the_suppression(tmp_path):
    """Removing a suppression lowers exactly one category (ratchet monotonicity)."""
    root = build_fixture(tmp_path)
    (root / "backend/tests/unit/test_a.py").write_text(
        FIXTURE["backend/tests/unit/test_a.py"].replace(
            "@mark.skip(reason='bare-idiom spelling must count')\n", ""
        )
    )
    got = run_census(root)
    assert got["pytest_skip"] == 1 and got["pytest_skipif"] == EXPECTED["pytest_skipif"]


@pytest.mark.timeout(180)  # real-tree AST census ~14s; tier default timeout is 5s
def test_real_tree_matches_spec_baselines():
    """The spec's escape-hatch table: 6/0/16/32/63/4/94/54 + 4 trees + 5 modules.

    A drift here means either the tree gained a hatch (ratchet territory) or
    the spec baseline went stale — WP1.1's MEASURE step adjudicates which.
    """
    got = run_census(REPO_ROOT)
    expected = {
        "collection_allowlist": 6,
        "flake_allowlist": 0,
        "frontend_quarantine": 16,
        "pytest_skip": 32,
        "pytest_skipif": 63,
        "pytest_xfail": 4,
        "pytest_skip_imperative": 94,
        "frontend_skip": 54,
        "excluded_test_trees": 4,
        "coverage_omit": 5,
    }
    stale = {k: (got.get(k), v) for k, v in expected.items() if got.get(k) != v}
    assert not stale, "census vs spec baseline drift: " + ", ".join(
        f"{k} census={g} spec={e}" for k, (g, e) in stale.items()
    )
