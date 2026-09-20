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
    # WP1.3 tpa_slow_list: the fixture carries its OWN audit script — the
    # patterns ARE the suppression, so the channel walks the rooted tree, not
    # the versioned script (unlike unspecced_patch's versioned-measurer).
    "scripts/audit-test-durations.py": (
        "SLOW_TEST_PATTERNS = [\n"
        '    r"test_alpha.*slow_one",  # measured 12.0s spike x4/17 runs\n'
        '    r"test_beta::test_slow_two",\n'
        "]\n"
        "OTHER_LIST = [r'test_gamma']  # must not count — wrong name\n"
    ),
    "backend/tests/unit/test_a.py": (
        "import pytest\n"
        "from pytest import mark\n"
        "SKIP_X = 'x'  # module-constant reason indirection — the real "
        "MQTT_PUMP_REASON/EXPORTDEFER_REASON shape; locations must resolve it\n"
        "@pytest.mark.skip(reason=SKIP_X)\n"
        "def test_one():\n    pytest.skip('nope')\n"
        "@pytest.mark.skipif(True, reason='y')\n"
        "def test_two():\n    pass\n"
        "@mark.skip(reason='bare-idiom spelling must count')\n"
        "def test_three():\n    pass\n"
        "@pytest.mark.skip(reason='stacked a')\n"
        "@pytest.mark.skip(reason='stacked b')\n"
        "def test_stacked():\n    pass\n"
        "class TestOne:\n"
        "    @pytest.mark.skip(reason='cls one site')\n"
        "    def test_shared(self):\n        pass\n"
        "class TestTwo:\n"
        "    @pytest.mark.skip(reason='cls two site')\n"
        "    def test_shared(self):\n        pass\n"
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
    "pytest_skip": 6,  # called + bare-idiom + stacked pair + two same-named methods
    "pytest_skipif": 1,
    "pytest_xfail": 1,
    "pytest_skip_imperative": 2,
    "frontend_skip": 2,
    "frontend_only": 1,
    "frontend_todo": 1,
    "excluded_test_trees": 3,  # load/benchmarks/e2e, deduped
    "coverage_omit": 2,  # main.py + wildcards are plumbing, not suppressions
    "unspecced_patch": 0,  # WP4.2: the fixture carries no convertible patch()s
    "tpa_slow_list": 2,  # WP1.3: the fixture's own audit script, 2 patterns
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
        # stacked pair (the real defect shape: test_system_models.py attaches
        # BOTH "Moved to…" and "Flaky…" to one def — 7 sites). The count pass
        # counts both decorators; ids suffix from #2 so both are addressable.
        {"id": "backend/tests/unit/test_a.py::test_stacked", "reason": "stacked a"},
        {"id": "backend/tests/unit/test_a.py::test_stacked#2", "reason": "stacked b"},
        # class-qualified: two classes each carry test_shared — the bare method
        # name collides (the real defect: test_system_models.py ships 7 such
        # pairs, its registry entries overwrote each other) and pytest itself
        # identifies them by Class.method.
        {
            "id": "backend/tests/unit/test_a.py::TestOne::test_shared",
            "reason": "cls one site",
        },
        {
            "id": "backend/tests/unit/test_a.py::TestTwo::test_shared",
            "reason": "cls two site",
        },
    ],
    "pytest_skipif": [{"id": "backend/tests/unit/test_a.py::test_two", "reason": "y"}],
    "pytest_xfail": [{"id": "backend/tests/unit/test_b.py::test_four", "reason": ""}],
    "pytest_skip_imperative": [
        {"id": "backend/tests/unit/test_a.py:6", "reason": "nope"},
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
    "tpa_slow_list": [
        {
            "id": "test_alpha.*slow_one",
            "reason": "measured 12.0s spike x4/17 runs",
        },
        {"id": "test_beta::test_slow_two", "reason": "no reason comment"},
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
    assert got["pytest_skip"] == EXPECTED["pytest_skip"] - 1
    assert got["pytest_skipif"] == EXPECTED["pytest_skipif"]


@pytest.mark.timeout(180)  # real-tree AST census ~14s; tier default timeout is 5s
def test_real_tree_matches_spec_baselines():
    """The spec's escape-hatch table: 4/0/16/32/63/4/94/54 + 4 trees + 5 modules.

    collection_allowlist 6→4 (2026-09-16): 97153cbb deleted the schemathesis
    stub and fe646612 renamed test_utils.py — real remediation, so the two
    allowlist lines vanished for the right reason; the count fell, it was not
    raised (the ratchet's one-directional rule is about the tree, and this
    test is the tree's mirror).
    pytest_skipif 63→62→56 (2026-09-16): the EXPORTDEFER fix deleted the
    module-wide skipif on TestExportDownload; the MQTTPUMP fix deleted the six
    delivery skips in test_mqtt_integration.py — suppressions REMOVED by the
    defects' repairs (the direction the ratchet exists to protect).
    pytest_skip_imperative 94→93 (2026-09-16): R-T9-MVSOURCE's retirement
    deleted test_materialized_views_migration.py, whose inline site left with
    the file. (The file's pytestmark-form skipif was never census-visible —
    the counter reads decorator AST; module-mark suppression is a known blind
    spot, noted not widened.)
    A drift here means either the tree gained a hatch (ratchet territory) or
    the spec baseline went stale — WP1.1's MEASURE step adjudicates which.
    """
    got = run_census(REPO_ROOT)
    expected = {
        "collection_allowlist": 4,
        "flake_allowlist": 0,
        "frontend_quarantine": 16,
        "pytest_skip": 32,
        "pytest_skipif": 56,
        "pytest_xfail": 4,
        "pytest_skip_imperative": 93,
        "frontend_skip": 54,
        "excluded_test_trees": 4,
        "coverage_omit": 5,
        # WP1.3: 150 uncounted patterns (P's figure, reproduced exactly) pruned
        # to the 7 MEASURED breaches over 18 main junit datasets; the channel
        # is counted from here on and the ratchet's one-way rule owns it.
        "tpa_slow_list": 7,
    }
    stale = {k: (got.get(k), v) for k, v in expected.items() if got.get(k) != v}
    assert not stale, "census vs spec baseline drift: " + ", ".join(
        f"{k} census={g} spec={e}" for k, (g, e) in stale.items()
    )
