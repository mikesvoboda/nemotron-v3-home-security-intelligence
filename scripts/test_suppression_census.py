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
    # WP2.4: the environment LAUNDERING channel — registry-gen defaults every
    # imperative skip to kind=environment (exempt from tracking+expiry), and
    # most guard git-tracked repo files, not host capabilities. The census
    # must hand the ratchet the GUARD SOURCE so classification can be
    # mechanical: same file, one host-shaped skip, one repo-shaped skip.
    "backend/tests/unit/test_guard.py": (
        "import os\nimport shutil\n\nimport pytest\n"
        "def test_host_tool():\n"
        "    if not shutil.which('ffmpeg'):\n        pytest.skip('ffmpeg missing')\n"
        "def test_repo_file():\n"
        "    p = os.path.join('configs', 'nginx.conf')\n"
        "    if not os.path.exists(p):\n        pytest.skip('no nginx.conf')\n"
    ),
    # WP2.4: id counts flatter — a CLASS-level mark hides every test inside
    # (30 of the real tree's 56 skipif ids sit on classes) and parametrize
    # multiplies what one id suppresses. The --cases pass resolves each id to
    # the real test cases behind it; these shapes pin the rule.
    "backend/tests/unit/test_c.py": (
        "import pytest\n"
        "@pytest.mark.skip(reason='class skip hides three')\n"
        "class TestHidden:\n"
        "    def test_alpha(self):\n        pass\n"
        "    def test_beta(self):\n        pass\n"
        '    @pytest.mark.parametrize("v", [1, 2, 3])\n'
        "    def test_gamma(self, v):\n        pass\n"
        "@pytest.mark.skipif(True, reason='param four')\n"
        '@pytest.mark.parametrize("x", [1, 2])\n'
        "@pytest.mark.parametrize('y', ['a', 'b'])\n"
        "def test_multi(x, y):\n    pass\n"
        '@pytest.mark.parametrize("z", [1, 2, 3])\n'
        "def test_imp_param(z):\n    pytest.skip('inside params')\n"
    ),
    "frontend/src/a.test.tsx": "it('x', () => {});\nit.skip('y', () => {});\ndescribe.skip('z', () => {});\n",
    "frontend/src/b.test.ts": "it.only('solo', () => {}); it.todo('later');\n",
    # WP2.4: the quarantined files must EXIST for the --cases pass to count
    # their hidden test cases (the real 16 quarantine ids hold 662 cases —
    # the bias the id-only report papered over).
    "frontend/src/b.test.tsx": (
        "it('one', () => {});\nit('two', () => {});\n"
        "describe('g', () => { it('three', () => {}); });\n"
    ),
    "frontend/src/c.test.ts": "test('solo', () => {});\n",
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
    # 6→7 (WP2.4): test_c.py's class-level skip — the shape 30 of the real
    # tree's 56 skipif ids use, and the reason ids flatter.
    "pytest_skip": 7,
    "pytest_skipif": 2,  # test_two + test_multi (parametrized, 1 id)
    "pytest_xfail": 1,
    "pytest_skip_imperative": 5,  # +2 (WP2.4b guard-probe fixture)
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
        # WP2.4: the CLASS itself is the suppressed site — one id, but three
        # test cases hide under it (the real tree's dominant skipif shape).
        {"id": "backend/tests/unit/test_c.py::TestHidden", "reason": "class skip hides three"},
    ],
    "pytest_skipif": [
        {"id": "backend/tests/unit/test_a.py::test_two", "reason": "y"},
        {"id": "backend/tests/unit/test_c.py::test_multi", "reason": "param four"},
    ],
    "pytest_xfail": [{"id": "backend/tests/unit/test_b.py::test_four", "reason": ""}],
    # WP2.4b: every imperative entry carries its GUARD SOURCE (the enclosing
    # if-test / except-handler the skip sits behind) and the census's own
    # host-probe verdict — the laundering channel closes only when the
    # classifier can see what the skip actually guards. Guard "" with
    # host_probe False is the shape registry-gen must stop defaulting to
    # kind=environment.
    "pytest_skip_imperative": [
        {
            "id": "backend/tests/unit/test_a.py:6",
            "reason": "nope",
            "guard": "",
            "host_probe": False,
        },
        {
            "id": "backend/tests/unit/test_b.py:4",
            "reason": "",
            "guard": "",
            "host_probe": False,
        },
        {
            "id": "backend/tests/unit/test_c.py:18",
            "reason": "inside params",
            "guard": "",
            "host_probe": False,
        },
        {
            "id": "backend/tests/unit/test_guard.py:7",
            "reason": "ffmpeg missing",
            "guard": "not shutil.which('ffmpeg')",
            "host_probe": True,
        },
        {
            "id": "backend/tests/unit/test_guard.py:11",
            "reason": "no nginx.conf",
            "guard": "not os.path.exists(p)",
            "host_probe": False,
        },
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


# ---------------------------------------------------------------------------
# WP2.4: the census must report WHAT A SUPPRESSION SUPPRESSES, not just how
# many ids mint it. Measured bias P pinned: 255 test-level ids resolve to
# 1,136 real test cases (4.45x); pytest_skipif 56 ids -> 193 functions
# (30 sit on CLASSES); frontend_quarantine's 16 ids hold ~662 vitest cases.
# At id level environment looked like 66.9% of backend skips; at test level
# 39.2%. The `--cases` mode reports {category: {ids, cases}}; config
# categories (not test-level) carry cases=null rather than pretending 1:1.
# ---------------------------------------------------------------------------

EXPECTED_CASES = {
    # ids from EXPECTED above; cases per the real expansion rules:
    # class-level mark -> 1 (the id) + every test_* inside, parametrized;
    # stacked parametrize -> product; imperative skip -> enclosing fn's params;
    # describe.skip -> nested live cases (min 1 for an empty block);
    # quarantine file -> its live it/test sites (.skip/.todo sites don't run).
    # 10 = test_one/three/stacked/TestOne::shared/TestTwo::shared (1 each —
    # stacked pair is ONE case, deduped) + TestHidden (1+1+3 inner, parametrized)
    "pytest_skip": {"ids": 7, "cases": 10},
    "pytest_skipif": {"ids": 2, "cases": 5},  # test_two 1 + test_multi 2x2
    "pytest_xfail": {"ids": 1, "cases": 1},
    "pytest_skip_imperative": {"ids": 5, "cases": 7},  # 1+1+3 + 2 guard sites
    "frontend_skip": {"ids": 2, "cases": 2},  # it.skip 1 + empty describe.skip min-1
    "frontend_only": {"ids": 1, "cases": 1},
    "frontend_todo": {"ids": 1, "cases": 1},
    "frontend_quarantine": {"ids": 3, "cases": 5},  # live sites: a=1 b=3 c=1
    # non-test-level channels: an id IS the whole suppression; null beats a
    # fake 1:1 (a report that silently equals ids re-mints the old bias).
    "collection_allowlist": {"ids": 2, "cases": None},
    "flake_allowlist": {"ids": 1, "cases": None},
    "excluded_test_trees": {"ids": 3, "cases": None},
    "coverage_omit": {"ids": 2, "cases": None},
    "unspecced_patch": {"ids": 0, "cases": None},
    "tpa_slow_list": {"ids": 2, "cases": None},
}


def run_cases(root: Path) -> dict:
    r = subprocess.run(
        [sys.executable, str(CENSUS), "--root", str(root), "--cases"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, f"census --cases failed: {r.stderr[-400:]}"
    return json.loads(r.stdout)


def test_cases_report_expands_ids_to_real_test_cases(tmp_path):
    """WP2.4 done-when part 1: test-case counts alongside id counts."""
    got = run_cases(build_fixture(tmp_path))
    assert got == EXPECTED_CASES, "\n".join(
        f"{k}: got {got.get(k)!r} want {v!r}" for k, v in EXPECTED_CASES.items()
    )


def test_cases_ids_match_the_count_pass(tmp_path):
    """The cases pass must never re-define what counts — same ids, richer report."""
    root = build_fixture(tmp_path)
    counts = run_census(root)
    cases = run_cases(root)
    assert {k: v["ids"] for k, v in cases.items()} == counts


@pytest.mark.timeout(300)  # real-tree AST census ~15s
def test_real_tree_cases_report_reproduces_p_measured_bias():
    """The bias P measured (1136 cases / 4.45x / quarantine ~662) must show
    up in the committed report — a report that disagreed with the finding
    would bury it again. Bands (not exact pins): P's figures came from a
    specific old tree; the INVARIANTS are what WP2.4 is about, so pin
    generously and let the ledger carry the run's exact numbers."""
    got = run_cases(REPO_ROOT)
    # categories with no legitimate id->case coalescing must satisfy
    # cases >= ids exactly (expansion can only add): the shapes where a
    # site is guaranteed distinct.
    for cat in ("pytest_skipif", "pytest_xfail", "frontend_skip", "frontend_quarantine"):
        assert got[cat]["cases"] >= got[cat]["ids"], (
            f"{cat}: cases below ids — expansion lost a site"
        )
    # pytest_skip/pytest_skip_imperative legitimately DEDUPE: test_system_models.py
    # stacks TWO skip marks on one def (7 pairs -> 7 ids, 7 cases) and gpu files
    # carry consecutive skips inside one function. Cases are DISTINCT tests,
    # so the honest floor there is generous; the total ratio carries the truth.
    for cat in ("pytest_skip", "pytest_skip_imperative"):
        assert got[cat]["cases"] >= got[cat]["ids"] * 0.5, f"{cat}: {got[cat]}"
    assert got["pytest_skipif"]["cases"] >= 180, (
        f"P measured 56 ids -> 193 functions (class-hiding + params); got {got['pytest_skipif']}"
    )
    assert 600 <= got["frontend_quarantine"]["cases"] <= 720, (
        f"P measured ~662 cases behind 16 quarantine ids; got {got['frontend_quarantine']}"
    )
    test_level = (
        "pytest_skip",
        "pytest_skipif",
        "pytest_xfail",
        "pytest_skip_imperative",
        "frontend_skip",
        "frontend_only",
        "frontend_todo",
        "frontend_quarantine",
    )
    ids = sum(got[c]["ids"] for c in test_level)
    cases = sum(got[c]["cases"] for c in test_level)
    # P: 255 ids -> 1,136 cases (4.45x) on the tree P censused; this run
    # measures 255 -> 1,112 (4.36x). The INVARIANT: id counts understate
    # suppressed surface by multiples — a report that only shows ids hides it.
    assert cases >= ids * 4, f"test-level ids {ids} -> cases {cases} (P measured 4.45x)"


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
    pytest_skip_imperative 93→94 (2026-09-24): test_eval_store.py:295 — the
    G0.4 stock-corpus loader test skips when the GPU-mount media (owner-staged
    off-repo data, ledger F6/F5) isn't on the machine. Adjudicated
    environment via HOST_JUSTIFIED + registry the same commit; the ratchet's
    increase path exercised exactly as designed.
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
        "pytest_skip_imperative": 94,
        "frontend_skip": 54,
        "excluded_test_trees": 4,
        "coverage_omit": 5,
        # WP1.3: 150 uncounted patterns (P's figure, reproduced exactly) pruned
        # to the 7 MEASURED breaches over 18 main junit datasets; the channel
        # is counted from here on and the ratchet's one-way rule owns it.
        # 7→8 (2026-09-23): license-plate household-matching test admitted with
        # measured corpus breaches (4.18s ×2 #6667 head, 4.297s main junit;
        # 1.20s solo → -n8 contention), registry entry same commit.
        "tpa_slow_list": 8,
    }
    stale = {k: (got.get(k), v) for k, v in expected.items() if got.get(k) != v}
    assert not stale, "census vs spec baseline drift: " + ", ".join(
        f"{k} census={g} spec={e}" for k, (g, e) in stale.items()
    )
