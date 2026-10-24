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
    # Playwright tree: a different runner — its .skip/.only must NOT count in
    # the VITEST categories (those are 54/0/0 in the real tree). Two arms now:
    # e2e/benchmarks/chaos/load are `excluded_test_trees` by deferral, while
    # frontend/tests/golden is inventoried per-site ([r173] ruling 173), which
    # is why it has its own fixture file below and this decoy must stay out of
    # it — same runner, different governance.
    "frontend/tests/e2e/specs/decoy.spec.ts": "test.skip('e2e hidden', async () => {});\ntest.only('e2e solo', async () => {});\n",
    # [r173]: the golden tree. One file carrying every shape the scanner has to
    # sort: two registration forms that COUNT, three non-suppressions that must
    # not, and prose that reads like a suppression.
    "frontend/tests/golden/alpha/golden.spec.ts": (
        "import { test, expect } from '../../fixtures';\n"
        "test.describe('F-001 the panel', () => {\n"
        "  test('runs and proves the row', async ({ page }) => {});\n"
        # commented-out leg: `// test.skip(` is prose, not a call
        "  // test.skip('a leg disabled in a comment', async () => {});\n"
        # JSDoc history: mid-line mention behind ` * `
        "  /**\n   * History: test.fixme('mentioned in jsdoc', fn) was restored.\n   */\n"
        "  test.fixme('F-001 the video leg — UNPROVEN on this tier', async ({ page }) => {});\n"
        "  test.skip('F-001 the ordering leg', async ({ page }) => {});\n"
        # conditional guard: runs whenever the condition is false
        "  test.skip(!harness.ready, 'no live stack on this tier');\n"
        "  test('runtime guard inside the body', async ({ page }) => {\n"
        "    await test.info().skip(true, 'host feature absent');\n"
        "  });\n"
        # chained fluent registration: same call, two lines
        "  test\n"
        "    .fixme('F-001 the chained leg', async ({ page }) => {});\n"
        "});\n"
    ),
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
    # [r173] ruling 173: the golden tree, registration-form only. 2 fixme
    # (plain + chained-fluent spelling) and 1 skip; the conditional guard, the
    # test.info().skip runtime guard, the commented-out leg and the JSDoc
    # mention are all deliberately NOT counted here.
    "golden_fixme": 2,
    "golden_skip": 1,
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
    # [r173]: ids key on the leg TITLE (drift-proof, like the frontend arm) and
    # reason carries that title — registry-gen's classify() reads reason, and a
    # golden title is the whole adjudication ("UNPROVEN on this tier").
    "golden_fixme": [
        {
            "id": "frontend/tests/golden/alpha/golden.spec.ts::F-001 the video leg — UNPROVEN on this tier",
            "reason": "F-001 the video leg — UNPROVEN on this tier",
        },
        {
            "id": "frontend/tests/golden/alpha/golden.spec.ts::F-001 the chained leg",
            "reason": "F-001 the chained leg",
        },
    ],
    "golden_skip": [
        {
            "id": "frontend/tests/golden/alpha/golden.spec.ts::F-001 the ordering leg",
            "reason": "F-001 the ordering leg",
        },
    ],
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


# ---------------------------------------------------------------------------
# [r173] ruling 173: the golden Playwright arm. The discriminator is
# Playwright's own grammar — a STRING first argument means the leg is DECLARED
# and never runs (a suppression); anything else means a condition, and the leg
# runs whenever that condition is false (a guard, suppressing nothing). The
# shapes below are why the rule is mechanical rather than a judgment call.
# ---------------------------------------------------------------------------

GOLDEN_SHAPES = [
    # (source, counted-as-suppressions, why)
    ("test.fixme('a title', async () => {});\n", 1, "string first arg = registration"),
    ("test.skip('a title', async () => {});\n", 1, "same, skip form"),
    ("test.skip();\n", 1, "bare call is unconditional"),
    ("await test.fixme('t', async () => {});\n", 1, "awaited is still a registration"),
    ("test.fixme(\n  'multiline args',\n  async () => {},\n);\n", 1, "args split over lines"),
    ("test.fixme(`backtick title`, async () => {});\n", 1, "template-literal title"),
    ("test.fixme('escaped \\' quote', async () => {});\n", 1, "escaped quote in title"),
    ("test\n  .skip('chained fluent', async () => {});\n", 1, "chain rooted at test"),
    ("test.skip(!harness.ready, 'no stack');\n", 0, "condition first = guard, runs when false"),
    ("test.skip(a ? b : c, 'why');\n", 0, "ternary first = guard"),
    (
        "test('t', async () => { test.info().skip(c, 'why'); });\n",
        0,
        "runtime guard, not a registration",
    ),
    ("test\n  .info()\n  .skip(true, 'runtime');\n", 0, "chained runtime guard: root is .info()"),
    # The dangerous neighbour of the line above: same chain, but a STRING first
    # arg, which is the shape a walk-back that treats .info() as an ordinary
    # step miscounts as a registration (it reads the chain root back to `test`).
    # Kept at 0 by the .info() terminator, NOT by the guard rule, so this row
    # reddens if that terminator is ever dropped.
    (
        "test\n  .info()\n  .skip('looks like a leg', 'runtime');\n",
        0,
        "runtime .info() chain never a registration",
    ),
    ("fixtures\n  .skip('not a test', fn);\n", 0, "chain rooted at a receiver"),
    (
        "const t = pick();\nt\n  .skip('unknown root', fn);\n",
        0,
        "unresolvable root reads as not-ours",
    ),
    ("// test.skip('disabled in a comment', fn);\n", 0, "commented-out leg is prose"),
    (" * history: test.fixme('x', fn) was restored\n", 0, "jsdoc mention is prose"),
    ("// test.describe.skip('was disabled', () => {});\n", 0, "commented suite form stays prose"),
    ("test.describe.only('x', () => {});\n", 0, ".only is not a suppression"),
]

# Forms the census REFUSES to count. A describe-block skip hides N legs behind
# one call site and a second call on an attributed line hides one leg; either
# one read as "nothing to see" would be the exact failure this arm exists to
# close, so both exit non-zero naming the file.
GOLDEN_REFUSALS = [
    ("test.describe.skip('block', () => {});\n", "suite-level"),
    ("test.describe\n  .fixme('block', () => {});\n", "chained suite-level"),
    ("test.describe.only\n  .skip('block', () => {});\n", "chained suite-level .only"),
    ("if (x) test.skip('mid-line', fn);\n", "mid-line"),
    ("test.skip('one', fn); test.fixme('two', fn);\n", "two per line"),
]


@pytest.mark.parametrize(
    "src,want,why",
    GOLDEN_SHAPES,
    ids=[f"{i:02d}-{w[:38]}" for i, (_, _, w) in enumerate(GOLDEN_SHAPES)],
)
def test_golden_scans_registration_not_guards(tmp_path, src, want, why):
    """Registration vs guard: the count follows Playwright's grammar, not intent."""
    root = build_fixture(tmp_path)
    # Isolate the shape under test: drop the fixture tree's own golden file so a
    # change to one row of the table cannot silently move another's count.
    (root / "frontend/tests/golden/alpha/golden.spec.ts").unlink()
    spec = root / "frontend/tests/golden/shapes/shape.spec.ts"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(src)
    got = run_census(root)
    found = got["golden_skip"] + got["golden_fixme"]
    assert found == want, f"{why}: {src!r} counted {found}, want {want}"


@pytest.mark.parametrize("src,label", GOLDEN_REFUSALS, ids=[w for _, w in GOLDEN_REFUSALS])
def test_golden_refuses_to_silently_undercount(tmp_path, src, label):
    """The dangerous direction is covered by failing loud, not by parsing deeper.

    A golden suppression the scanner cannot attribute must END THE BUILD. If it
    were merely skipped the census would report a smaller number and the ratchet
    would green-light the very suppression it exists to catch — so this is the
    test that makes "extend _golden_sites" the only way forward.
    """
    root = build_fixture(tmp_path)
    (root / "frontend/tests/golden/alpha/golden.spec.ts").unlink()
    spec = root / "frontend/tests/golden/shapes/shape.spec.ts"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(src)
    r = subprocess.run(
        [sys.executable, str(CENSUS), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode != 0, f"{label}: census exited 0 and reported {r.stdout.strip()[-200:]}"
    assert "shape.spec.ts" in r.stderr, (
        f"{label}: failure does not name the file: {r.stderr[-300:]}"
    )


def test_golden_scans_by_test_file_convention_not_one_suffix(tmp_path):
    """The tree-wide net, which no real-tree assertion can prove: today's
    inventory has ZERO golden `*.test.ts` files (measured 2026-10-17: `*.spec.ts`
    and the widened pattern select the same 106 files), so only a fixture can
    show that a differently-named Playwright file is still governed. A `_golden_
    playwright_sites` glob that narrows back to `*.spec.ts` reddens here — which
    is the exact regression ruling 173 exists to close."""
    root = build_fixture(tmp_path)
    spec = root / "frontend/tests/golden/alpha/renamed.test.ts"
    spec.write_text("test.fixme('F-009 named .test.ts, still governed', async () => {});\n")
    got = run_census(root)
    assert got["golden_fixme"] == EXPECTED["golden_fixme"] + 1, got
    ids = [r["id"] for r in run_locations(root)["golden_fixme"]]
    assert any(r.endswith("renamed.test.ts::F-009 named .test.ts, still governed") for r in ids), (
        ids
    )
    # and the count is INDEPENDENT of the suffix: drop the file, back to baseline
    spec.unlink()
    assert run_census(root)["golden_fixme"] == EXPECTED["golden_fixme"]


def test_golden_arm_is_inventory_not_just_a_tally(tmp_path):
    """A golden site must carry an id AND a reason — ruling-gen reads both."""
    root = build_fixture(tmp_path)
    got = run_locations(root)
    for cat in ("golden_skip", "golden_fixme"):
        for row in got[cat]:
            assert row["id"].startswith("frontend/tests/golden/"), row
            assert "::" in row["id"], f"title-keyed id expected: {row}"
            assert row["reason"], f"reason drives classification: {row}"
    # The e2e decoy must not leak into the golden arm (or vice versa): same
    # runner, opposite governance.
    assert not any(
        "e2e" in row["id"] for cat in ("golden_skip", "golden_fixme") for row in got[cat]
    )


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
# (30 sit on CLASSES); frontend_quarantine's 16 ids held ~662 vitest cases
# until F3.3 (#7325, 2026-10-22) emptied the quarantine list — the pins below
# record that history and enforce the emptied tree.
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
    # [r173]: a golden registration-form leg IS one declared test that never
    # runs, so ids and cases agree 1:1 — there is no suite-level form to expand
    # (the scanner refuses those outright). A 1:1 here is measured, not assumed.
    "golden_fixme": {"ids": 2, "cases": 2},
    "golden_skip": {"ids": 1, "cases": 1},
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
    # 600..720 (P's band) → ==0 (2026-10-22, F3.3 #7325): the quarantine list
    # is empty — the ids P measured behind are repaired or deleted — so the
    # band collapses with its category; 0 is the only honest reading now.
    assert got["frontend_quarantine"]["cases"] == 0, (
        f"quarantine emptied but cases report {got['frontend_quarantine']}"
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
    # P: 255 ids -> 1,136 cases (4.45x) on the tree P censused; the run after
    # that measured 255 -> 1,112 (4.36x). The INVARIANT: id counts understate
    # suppressed surface by multiples — a report that only shows ids hides it.
    # 4x→1.9x (2026-10-22, F3.3 #7325): the 13 quarantine ids carried ~627 of
    # the cases (main measures 239→1072, 4.49x); F3.3 empties them, so the
    # total expansion ratio drops to what the remaining categories measure
    # (226→445, 1.97x). The invariant is now "cases ≥ ids" exactly — expansion
    # can only add — plus the skipif floor below; the multiple was the
    # quarantine's, and pinning it here would re-require the suppression the
    # package just removed.
    assert cases >= ids, f"test-level ids {ids} -> cases {cases} (expansion lost a site)"


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
    pytest_skip_imperative 94→96 (2026-09-25): batch-25 battery
    test_nemotron_analyzer_batch25_dead-10-2.py:1170/1178 — the kill-evidence
    coverage test skips when the campaign runner's red-check logs
    (/tmp/wp-batch25/redcheck_dead102{b,c}.log, off-repo artifacts written
    only at red-check time) are absent. Adjudicated environment via
    HOST_JUSTIFIED + regenerated registry (commit b80d00b4); a data-chain skip,
    not a repo-file guard.
    pytest_skip_imperative 96→99 (2026-09-27): the re-ID swap's real-.pth
    proof, test_osnet_loader.py:1360/1387/1398 — the loader's B2 acceptance
    test skips per env: pinned weights absent (AGENT_GPU_DIR unset), torch
    absent, torchreid's tensorboard chain unimportable. Adjudicated (two
    environment, one todo weights-gate) via regenerated registry + baseline
    raised the same commit — the increase path exercised exactly as designed;
    every CI env takes all three skips, every GPU box runs the real thing.
    pytest_skip_imperative 99→101 (2026-09-28): this PR's TestComposeSELinuxLabels
    block, test_docker_compose_security.py:348/358 — the camera-root precheck
    skips when git is unavailable or the tree isn't a git checkout. Adjudicated
    environment via HOST_JUSTIFIED + registry/baseline raised the same commit
    (ea79a858); the mirror here lagged one commit, which is exactly the drift
    this test exists to catch — caught on this PR, not on main.
    pytest_skip_imperative 101→99 (2026-09-29, R8 S2): two imperative skips
    died with backend/tests/unit/services/
    test_nemotron_analyzer_batch25_dead-10-2.py (the red-check battery retired
    with the analyzer tier — owner ruling: no backwards compatibility). The
    11 SURVIVING imperative sites in conftest.py / test_gpu_pipeline.py did
    NOT change kind; they line-SHIFTED with the same commit's deletions, so
    their HOST_JUSTIFIED keys and registry rows were re-armed at the new
    census ids (doctrine: the written verdict rides the move; a canary
    re-arms, it does not relax). Baseline lowered the same commit via the
    sanctioned ratchet-check --update path; the mirror follows in this diff.
    unspecced_patch 142→88 (2026-09-29, R8 S2): the fall is the deletion —
    54 unspecced mock.patch sites lived in files R8 S2 removed with the
    legacy LLM tier (test_nemotron_analyzer*, test_llm_analysis_pipeline,
    test_prompt_replay, chaos/nemotron, the gpu-pipeline LLM legs,
    smoke_fire_loader). Nothing re-specced: an unspecced patch whose FILE is
    gone is not a converted suppression, it is gone. Baseline lowered the
    same commit; the registry rows died with their sites (ratchet: entries
    must not outlive what they license).
    pytest_skip_imperative 99→86 (2026-10-03): the retired Nemotron
    prompt-evaluation harness's integration test took 10 skip sites with it
    (d8482861, 99→89) and the NeMo Data Designer fixtures and tests took 3 more
    (89→86). Baseline lowered in the commit that removed the last of them; the
    registry rows died with their sites. d8482861 itself left this guard red:
    its verification ran backend/tests/unit/scripts, not the repo-root scripts/
    tests.
    pytest_skipif 56→57 (2026-10-06): the campaign-#46 mutant-home timing-row
    skip, test_notify_reachability_guard.py test_the_scan_is_fast_enough_... —
    the skipif predicate is `"mutants" in Path(__file__).resolve().parts`, so
    every CI env (a clean checkout has no mutants ancestor) RUNS the test; only
    mutmut's stats/clean-gate pass skips it. Classified todo by the generator
    (the guard names the tree layout, not host state — environment is earned,
    WP2.4b), registry row + baseline raised the same commit.
    pytest_skip_imperative 86→87 (2026-10-08, O1.3/UR-18 PR #6862): the Done-when
    render test test_compose_render_lists_ai_vlm.py:67 — skips when no compose binary
    (podman/docker) resolves on the machine. Adjudicated environment via HOST_JUSTIFIED
    (the which-probe lives inside the argv helper, invisible to the site-line probe)
    + registry row + baseline raised the same commit — the increase path, third
    precedent. The PR's own verification missed it the same way d8482861 did: it ran
    backend/tests/unit, not the repo-root scripts/ gate.
    pytest_skipif 57→58 (2026-10-08): O0.1's follow-up #6864 — the roster
    cross-check in test_uplevel_launch.py reads docs/uplevel/roles/lane.md,
    outside mutmut's also_copy, so it skips (never aborts) when the docs tree is
    absent. Same layout-guard shape as the #46 row above: every CI checkout HAS
    docs/ and RUNS the test; only the mutant home skips. Classified todo by the
    generator; registry row + baseline raised the same commit (the same recipe).
    pytest_skipif 58→59 (2026-10-08): O1.10 #6867 — the operator-line cross-check in
    test_uplevel_launch.py reads docs/uplevel/roles/operator.md, outside mutmut's also_copy,
    so it skips (never aborts) when the docs tree is absent. Same layout-guard shape as
    the #46 row above: every CI checkout HAS docs/ and RUNS the test; only the mutant
    home skips. Classified todo by the generator; registry row + baseline raised the
    same commit (the same recipe as #6864, whose guard this learned the gate from).
    pytest_skip_imperative 87→89 (2026-10-10, O1.11/UR-33 PR #6930): the prometheus boot
    pin's two docker-availability arms in test_monitoring_expose_lan_credentials.py:680
    and :694 — skip when docker resolves to nothing (the shutil.which sits two lines
    above the guard, invisible to the site-line probe) or the image is absent from the
    host daemon's store. Adjudicated environment via HOST_JUSTIFIED + regenerated
    registry row + baseline raised (4ae36510f, re-minted c185366f7) — the increase path,
    fourth precedent. The PR's own verification missed it the same way d8482861 did: it
    ran the census/ratchet/mint trio, not the repo-root scripts/ mirror test.
    golden_fixme 0→2 and golden_skip 0→0 (2026-10-17, [r173] ruling 173, PR #7236):
    the increase path of a DIFFERENT shape — the tree did not move, the measuring
    stick grew an arm. frontend/tests/golden sat in neither census branch:
    _frontend_test_files() is Vitest-only (frontend/src) and golden is not an
    excluded tree, so its suppression was invisible to the ratchet outright. Two
    registration-form legs are what the new scan finds, both in
    timeline/download-media.spec.ts (:748 VIDEO, :1055 two-detection ordering),
    both named F-296 by 8d419a0de under ruling 222 — the cite minted into their
    registry rows as tracking: R-222-F296. The 64 conditional `test.skip(cond,
    why)` sites in the same tree are NOT counted, and the exclusion is by
    GRAMMAR, corroborated (not proved) by run 3903516734's golden junit: 245
    tests / 0 failures / 4 skips, where the 4 are the 2 F-296 fixme rows plus
    F-295 and F-034, both runtime test.info().skip sites. Read the witness
    precisely -- it does NOT say guards never skip a leg. F-295 was taken by a
    DATA guard (.skip(frameIdx === -1, ...) at summary-cards.spec.ts:708; the
    harness guard at :654 is ruled out by elimination, three F-033 legs behind
    it PASSED). The split is that a registration can never run on any stack
    while a guard runs whenever its condition is false; a guard CAN take a leg
    when its data is absent, and that residual risk is stated on the PR rather
    than denied here.
    `todo` and not `environment`: ratchet-check:133 forces tracking null on
    environment, which is exactly how a golden skip stays unreviewed, and these
    are falsifiable claims about a feature rather than host state.
    A drift here means either the tree gained a hatch (ratchet territory) or
    the spec baseline went stale — WP1.1's MEASURE step adjudicates which.
    pytest_skip_imperative 93→94 (2026-10-21, [r285] PR #7318): the
    outbound-webhook retry-commit tests, test_outbound_webhook_retry_commit.
    py:41 — the tests run the shipped get_db against real Postgres and skip
    where TEST_DATABASE_URL/DATABASE_URL are unset (the test_db_isolation.
    py:66 env-behind-local-alias shape). Adjudicated environment via
    HOST_JUSTIFIED (b904d853f) — registry + baseline raised inside the PR,
    the mirror raised THIS commit after the PR's first-round local gates
    missed it; Collection Sanity caught the drift exactly as designed.
    golden_fixme 2→0 (2026-10-24, [r323b] PR #7418): the first fall of this
    category, and the fall the [r173] entry above anticipated — ruling 323
    item 6 supplied what both F-296 test.fixme legs were waiting on (the
    fake tier's video detection via its own watched camera, and a bulk
    event whose junction order and default detected_at ordering disagree),
    so both legs became RUNNING tests and the supply-witness leg re-aimed
    from absence+500 to presence+guard. The ratchet's two R-222-F296
    registry rows died with their sites (STALE named both); the baseline
    fell via the sanctioned ratchet-check --update path; and the fall
    exposed a generator gap — golden_fixme was not in ALWAYS_PRESENT, so
    the regenerated registry dropped the category key entirely and the
    ratchet read that as `REGISTRY: category golden_fixme absent` ("a
    category may not hide"). suppression-registry-gen.py gains the key in
    the same commit; this mirror moves with it. Decrease path.
    """
    got = run_census(REPO_ROOT)
    expected = {
        # 4→2 (2026-10-21, F3.2 #7246): the deletion cut removed the two retired
        # collection ids with their files (SystemHealthIndicator,
        # ZoneTimelineScrubber); the same drop is in this commit's
        # .github/suppression-baseline.json.
        # 2→1 (2026-10-22, F3.3 #7325): F3.3 deleted TimeGroupedEvents.simple
        # .test.tsx and the allowlist line with it; test_helpers.py is the one
        # row left.
        "collection_allowlist": 1,
        "flake_allowlist": 0,
        # 16→13 (2026-10-21, roll 10 of #7246): the F3.2 cut removed three
        # quarantine ids with their files; measured on the merged tree by
        # suppression-census.py. The 16→13 movement happened on this PR's side
        # (main never had the cut), so main's mirror kept the stale 16.
        # 13→0 (2026-10-22, F3.3 #7325): the package emptied vite.config.ts's
        # exclusion list — 12 files repaired and green, one deleted — so the
        # census measures no quarantine site anywhere; the registry drops its
        # 13 rows with the sites and keeps the category key (ALWAYS_PRESENT).
        "frontend_quarantine": 0,
        # 32→25 (2026-10-16, ruling 220): the seven redundant "Flaky … app
        # initialization timing" skips in test_system_models.py expired on 10-15 and
        # were removed with their `#2` registry rows; each test stays skipped by its
        # "Moved to test_model_management.py" decorator (`retired`, BB.1 deletes them).
        "pytest_skip": 22,
        "pytest_skipif": 58,
        "pytest_xfail": 4,
        # 89→93 (2026-10-11, BE-1 / ruling 87, PR #6979): the four harness-contract
        # skips of the first backend golden tree — conftest.py:61/70 (the
        # FEATURE_CHECK_* env is absent: the guard is `if missing:` over
        # _missing_env(), an env read two functions up that the site-line probe
        # can't see through — the test_db_isolation.py:66 shape), conftest.py:131
        # (login answered non-200, probe-caught via `status_code`), and
        # test_webhook_deliveries.py:132 (no events rows on the live stack —
        # Alert.event_id is a non-nullable FK, so this is the data-chain shape of
        # test_risk_score_validation.py:199). All four adjudicated environment via
        # HOST_JUSTIFIED + regenerated registry + baseline raised (12aab2728 raised
        # the baseline; THIS commit moves the mirror — the mirror lagged one commit
        # inside the same PR, the ea79a858 pattern, not one found on main).
        # The adjudication, not just the count, is the point: `todo` would have
        # minted these a 2026-12-31 expiry that WP1.4 fires naming the owner, on
        # skips that exist because collection must never crash without a live
        # stack — a contract that can never be "fixed", so their deadline must be
        # null. Increase path, fifth precedent.
        # 93→94 (2026-10-21, [r285] / PR #7318): test_outbound_webhook_retry_
        # commit.py:41 — the retry-commit tests run the shipped get_db against
        # real Postgres and skip where TEST_DATABASE_URL/DATABASE_URL are unset
        # (the test_db_isolation.py:66 env-behind-local-alias shape). The
        # baseline file was raised in f7cadeed9 but THIS mirror was missed there
        # and the miss surfaced only here, at this round's Collection Sanity
        # (run 39531798246 job 119015088702: census=94 spec=93) — the mirror is
        # a third gate beyond the ratchet and the gen --check, and the first
        # round's local gate runs didn't include the spec suite. Adjudicated
        # environment via HOST_JUSTIFIED (b904d853f added the key; the gen then
        # mints kind: environment, expires: null, justification carried).
        # Increase path, sixth precedent.
        # 94→93 (2026-10-21, B3.2 #7319): test_benchmark_vram.py deleted with
        # backend/scripts/benchmark_vram.py (-1 imperative skip at :208).
        # 93→95 (2026-10-22, [r308a] PR #7340): the sink smoke spec's two
        # imperative skips — test_notification_sinks.py:73 (the sink env
        # gate; the comprehension over os.environ reads sits behind a local
        # alias `missing`, the conftest.py:61/:70 local-alias shape) and
        # :171 (no events rows on the live stack; an alert needs a real
        # events.id, the test_webhook_deliveries.py:154 data-chain shape).
        # Both adjudicated environment via HOST_JUSTIFIED (b904d853f's
        # channel); registry entries + baseline raised in this same commit.
        # Increase path, seventh precedent.
        # 95→92 (2026-10-24, [r306b] PR #7416): test_osnet_loader.py's three
        # CPU torchreid/weights skips (:1360/:1387/:1398) removed with the
        # backend's CPU OSNet path.
        "pytest_skip_imperative": 92,
        # 51→49 (2026-10-21, roll 10 of #7246) then main's r285 +3 sites landed
        # inside files the F3.2 cut had already deleted (useMonitoringTargets,
        # ReidHistoryPanel tests): the merged tree MEASURES 49, so main's 52
        # does not survive this merge — the three skip sites rode deleted files.
        "frontend_skip": 49,
        "excluded_test_trees": 4,
        "coverage_omit": 5,
        # WP1.3: 150 uncounted patterns (P's figure, reproduced exactly) pruned
        # to the 7 MEASURED breaches over 18 main junit datasets; the channel
        # is counted from here on and the ratchet's one-way rule owns it.
        # 7→8 (2026-09-23): license-plate household-matching test admitted with
        # measured corpus breaches (4.18s x2 #6667 head, 4.297s main junit;
        # 1.20s solo → -n8 contention), registry entry same commit.
        # 8→9 (2026-10-06): r8-s2b full-tree import sweep admitted with measured
        # corpus breaches (4.40s PR #6826 head run 37560500061, 4.116s main
        # junit 37541671553 = the WP1.3 baseline denial; 5.28s solo — O(all
        # tracked test files), grows with the suite), registry entry same commit.
        # 9→10 (2026-10-11): TestLiveWiring child-session probe admitted with
        # measured CI breaches (6.05s run 38177621922, 5.56s run 38179109729 —
        # two heads of #7003; 6.92s local): it boots a real child pytest session
        # and the ~6s interpreter+plugin boot is the mechanism, not noise. The
        # file is absent at main, so no corpus entry existed to pre-admit it.
        # 10→11 (2026-10-13): compose-render CLI-boot test admitted with
        # measured CI breaches (4.93s + isolated re-run 8.12s on PR #7083 head
        # 961ddc956, job 115516785427) while the same file measured 0.447s in
        # main's own junit (run 38478749542, so absent from both WARN lists):
        # it spawns a real compose binary and the CLI boot IS the assertion, so
        # it cannot be fake-clocked. RETRACTED: the claim that the main-vs-head
        # spread IS which compose invocation _compose_argv() resolves was my
        # inference written as a measurement. That probe reads host binaries via
        # shutil.which, and its value reaches two renderings: the exit-nonzero
        # message (test_compose_render_lists_ai_vlm.py:90) and the TimeoutExpired
        # text of the timeout=100 call (:86), whose str CPython builds from the
        # argv list. Nothing catches that exception, so a timeout ERRORS rather
        # than passes, and a passing run prints neither — which is why a passing
        # run cannot show which branch it took, and main's 0.447s run passed.
        # Both compose binaries are on the image's Included Software list
        # (Podman 4.9.3, Docker Compose 2.38.2), which is exactly why the
        # manifest cannot settle the branch; shutil.which consults runtime PATH,
        # and the suite skips outright when the binaries are absent (:66-67).
        # Two machines disagreed, which is why the entry records a reproducible
        # breach rather than a stable duration. Both rows are named by id, not counted: the
        # offset this note used to give ("the -n8-contention row two above") was
        # itself wrong by one — two above is
        # test_r8_s2b_nemotron_deletion.* (idx 8, LIVE:
        # TestNoTestFileStillImportsASymbolS2bDeleted::
        # test_no_test_module_imports_a_name_that_no_longer_exists) and the -n8
        # row test_enrichment_pipeline_household_matching.* is THREE above (idx
        # 7). Its offset and its label disagreed with each other; only the
        # label happened to name an actually-orphaned row (its def went away in
        # 602379e29 with enrichment_pipeline.py, licensing zero tests), which is
        # why the miscount stayed invisible. That is the reason to name ids.
        # 8->9 (2026-10-18): B3.3's settings-orphan ratchet, two tests sharing
        # one module fixture, admitted with measured CI breaches on PR #7244
        # head feab2a0a2 (job 117605357915: 51.42s and 48.37s against the 4.0s
        # unit threshold). The cost is the assertion — the fixture re-runs the
        # whole-tree census script (61.5s measured solo) rather than trusting a
        # committed count — so it cannot be fake-clocked away, and the pattern
        # is one regex covering both ids, so the CENSUS (+1) and the tests it
        # exempts (+2) differ deliberately.
        "tpa_slow_list": 6,
        # [r173] ruling 173 — the new arm, measured (see the docstring's
        # 0→2 entry). Asserted here as well as in the baseline file so a golden
        # test.fixme added later trips this mirror AND the ratchet.
        # 2→0 (2026-10-24, [r323b] PR #7418): ruling 323 supplied what both
        # fixme legs needed — the fake tier's video detection and the
        # two-orderings-disagree event — and the legs became RUNNING tests;
        # the registry rows died with their sites (the ratchet's STALE
        # listing named both), the baseline fell via the sanctioned
        # ratchet-check --update path, and suppression-registry-gen.py grew
        # golden_fixme in ALWAYS_PRESENT so an emptied category keeps its
        # registry key ("a category may not hide" — the ratchet reads it).
        "golden_fixme": 0,
        "golden_skip": 0,
    }
    stale = {k: (got.get(k), v) for k, v in expected.items() if got.get(k) != v}
    assert not stale, "census vs spec baseline drift: " + ", ".join(
        f"{k} census={g} spec={e}" for k, (g, e) in stale.items()
    )
