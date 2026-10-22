#!/usr/bin/env python3
"""Tests for scripts/uplevel/inventory_witness.py ([r218], ruling 218): one per rule.

Run explicitly; outside testpaths (like every scripts/test_*.py gate suite):

    uv run python -m pytest scripts/test_inventory_witness.py -q

Each test builds a tiny inventory, a Feature check ``summary.json``, a known-disagreement list and
a golden spec tree in ``tmp_path`` and calls the CLI's ``main``, so the exit code and the printed
line are what is pinned. Nothing here judges this checkout's inventory against a real run (that is
the CI step's job, which has the run); the real files are read only to check the witness parses
the real inventory's rows as ``scripts/check-inventory-summary-arith.py`` counts them, that the
checked-in known list reads, and that the CI step is wired where ruling 218 puts it.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


witness = _load("inventory_witness", REPO_ROOT / "scripts" / "uplevel" / "inventory_witness.py")

HEADER = (
    "| id | surface | action | API calls | backend | status | evidence | modules | real tier"
    " | ruling | priority |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
)
FAKE_SPEC = "frontend/tests/golden/area/thing.spec.ts"
SEEDED_SPEC = "frontend/tests/golden/area/thing.seeded.spec.ts"
JUNIT_FAKE = "../golden/area/thing.spec.ts"
JUNIT_SEEDED = "../golden/area/thing.seeded.spec.ts"
# The spec tree the home jobs are read from. By default one spec whose titles name no row, so
# every row's home falls back to its evidence; a home test passes its own titles.
NO_TITLES = {FAKE_SPEC: "test.describe('a placeholder golden path @critical', () => {});\n"}
PUSH = "F-033: a pushed summary refreshes the cards — WITNESSED on the app’s own /ws/events socket"


def inventory(*rows: tuple[str, str, str]) -> str:
    """rows: (id, status, evidence). One §3-shaped table, `\\|` escapes included."""
    lines = [
        f"| {rid} | Surface `/x` | does a \\| thing | `GET /api/x` | `h` at `backend/x.py:1` | {status}"
        f" | {evidence} | `frontend/src/x.ts` | — |  |  |"
        for rid, status, evidence in rows
    ]
    return (
        "# Feature Inventory\n\n### 3.1 Area\n\n<!-- prettier-ignore -->\n"
        + HEADER
        + "\n".join(lines)
        + "\n"
    )


def summary(mode: str = "fake", playwright=None, backend=None, **extra) -> dict:
    golden: dict = {
        "playwright": "ok",
        "playwright_specs": playwright if playwright is not None else {},
    }
    if backend is not None:
        golden["backend_specs"] = backend
    return {
        "mode": mode,
        "project": "hsi-check-1",
        "commit": "fixture-head-commit",
        "results": {"golden": golden},
        **extra,
    }


def spec_tree(root: Path, specs: dict[str, str]) -> Path:
    for rel, text in specs.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def make(tmp_path: Path):
    """Write the inputs and run the CLI; return its exit code. Each call gets fresh run roots."""
    calls = iter(range(1000))

    def run(inv: str, *summaries: dict, known: str = "", specs=None, as_root: bool = False) -> int:
        call = next(calls)
        inv_path = tmp_path / "inventory.md"
        inv_path.write_text(inv, encoding="utf-8")
        known_path = tmp_path / "known.toml"
        known_path.write_text(known, encoding="utf-8")
        tree = spec_tree(tmp_path / "tree", NO_TITLES if specs is None else specs)
        args = ["--inventory", str(inv_path), "--known", str(known_path), "--specs-root", str(tree)]
        for n, data in enumerate(summaries):
            root = tmp_path / f"call{call}-root{n}"
            path = root / "hsi-check-1" / "artifacts" / "summary.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(data), encoding="utf-8")
            args += ["--run-root", str(root)] if as_root else ["--summary", str(path)]
        return witness.main(args)

    return run


def out(capsys) -> str:
    captured = capsys.readouterr()
    return captured.out + captured.err


EV_FAKE = f"Green golden path `{FAKE_SPEC}`."
EV_SEEDED = f"Green golden path `{SEEDED_SPEC}`."


# -- mapping -------------------------------------------------------------------------------------


def test_the_innermost_title_segment_naming_ids_wins() -> None:
    title = "golden path: embeds (F-164..F-167, F-169) @critical › F-165 /gpu-metrics binds"
    assert witness.leg_rows(title, backend=False) == ("F-165",)


def test_a_test_title_naming_no_id_inherits_its_describes_ids() -> None:
    title = "DO-2 notifications (F-238) › the guard survives the drive"
    assert witness.leg_rows(title, backend=False) == ("F-238",)


def test_a_to_range_names_every_id_between_its_ends() -> None:
    # notify-access/access.spec.ts's guard leg, which inherits its describe's range.
    title = "DO-2 access control golden path (F-240 to F-243) › the guard survives the access drive"
    assert witness.leg_rows(title, backend=False) == ("F-240", "F-241", "F-242", "F-243")


def test_a_dotted_range_names_every_id_between_its_ends() -> None:
    title = "golden path: operations grafana embed pages (F-164..F-167, F-169, F-174) @critical › renders"
    assert witness.leg_rows(title, backend=False) == (
        "F-164",
        "F-165",
        "F-166",
        "F-167",
        "F-169",
        "F-174",
    )


def test_package_names_like_fe_4_are_not_row_ids() -> None:
    assert witness.leg_rows("FE-4 cameras (DO-3) › lists them", backend=False) == ()


def test_a_pytest_leg_carries_its_id_as_an_f_word_in_its_name() -> None:
    assert witness.leg_rows("test_f190_feature_toggle_save_roundtrip", backend=True) == ("F-190",)
    assert witness.leg_rows("test_empty_patch_does_not_clobber", backend=True) == ()
    assert witness.leg_rows("test_x", backend=True, classes=["TestThing_f250"]) == ("F-250",)
    assert witness.leg_rows("test_buff100_size", backend=True) == ()


def test_specs_resolve_to_repo_paths() -> None:
    assert witness._spec_path("../golden/shell/nav.spec.ts", False) == (
        "frontend/tests/golden/shell/nav.spec.ts",
        [],
    )
    assert witness._spec_path("backend.tests.golden.external.test_backup", True) == (
        "backend/tests/golden/external/test_backup.py",
        [],
    )
    assert witness._spec_path("backend.tests.golden.external.test_backup.TestF100", True) == (
        "backend/tests/golden/external/test_backup.py",
        ["TestF100"],
    )


# -- awaiting real tier / works ------------------------------------------------------------------


@pytest.mark.parametrize("status", ["awaiting real tier", "works"])
def test_a_claim_whose_legs_all_passed_agrees(make, capsys, status: str) -> None:
    legs = {
        f"{JUNIT_FAKE}::F-001 thing › opens": "passed",
        f"{JUNIT_FAKE}::F-001 thing › saves": "passed",
    }
    assert make(inventory(("F-001", status, EV_FAKE)), summary(playwright=legs)) == 0
    assert "1 claims witnessed, 0 failing" in out(capsys)


@pytest.mark.parametrize("outcome", ["failed", "skipped"])
@pytest.mark.parametrize("status", ["awaiting real tier", "works"])
def test_a_claim_with_a_failed_or_skipped_leg_fails(
    make, capsys, status: str, outcome: str
) -> None:
    legs = {
        f"{JUNIT_FAKE}::F-001 thing › opens": "passed",
        f"{JUNIT_FAKE}::F-001 thing › saves": outcome,
    }
    assert make(inventory(("F-001", status, EV_FAKE)), summary(playwright=legs)) == 1
    text = out(capsys)
    assert f"FAIL: F-001 ({status}): {outcome} {FAKE_SPEC} :: F-001 thing › saves" in text
    assert "opens" not in text.split("FAIL:")[1].splitlines()[0], (
        "only the leg that did not pass is named"
    )


def test_a_fixme_leg_reads_as_skipped_and_fails_the_claim(make) -> None:
    # Playwright's junit writes <skipped/> for test.fixme; feature_check.junit_results records "skipped".
    legs = {
        f"{JUNIT_FAKE}::F-001 thing › opens": "passed",
        f"{JUNIT_FAKE}::F-001 thing › is broken today": "skipped",
    }
    assert make(inventory(("F-001", "awaiting real tier", EV_FAKE)), summary(playwright=legs)) == 1


def test_a_claim_no_leg_names_fails_in_its_home_job(make, capsys) -> None:
    legs = {f"{JUNIT_FAKE}::F-002 other › opens": "passed"}
    inv = inventory(
        ("F-001", "awaiting real tier", EV_FAKE), ("F-002", "awaiting real tier", EV_FAKE)
    )
    assert make(inv, summary(playwright=legs)) == 1
    assert (
        "FAIL: F-001 (awaiting real tier): no leg in this run names it -- the fake job is its home"
        in out(capsys)
    )


def test_a_claim_whose_evidence_names_no_golden_spec_is_the_fake_jobs(make, capsys) -> None:
    legs = {f"{JUNIT_FAKE}::F-002 other › opens": "passed"}
    inv = inventory(
        ("F-001", "works", "Real tier 2026-10-01; cites `backend/x.py:1`."),
        ("F-002", "works", EV_FAKE),
    )
    assert make(inv, summary(playwright=legs)) == 1
    assert "FAIL: F-001 (works): no leg in this run names it" in out(capsys)


# -- unverified ----------------------------------------------------------------------------------


def test_an_unverified_row_whose_legs_all_passed_is_ready_to_flip_with_its_cell_text(
    make, capsys
) -> None:
    legs = {
        f"{JUNIT_FAKE}::F-003 panel (F-003) › renders the list": "passed",
        f"{JUNIT_FAKE}::F-003 panel › saves": "passed",
    }
    assert (
        make(
            inventory(("F-003", "unverified", "Writer `backend/x.py:1`.")), summary(playwright=legs)
        )
        == 0
    )
    text = out(capsys)
    assert (
        "READY to flip: F-003 (unverified -> awaiting real tier): 2 leg(s), each passed in this job."
        in text
    )
    cell = text.split("evidence text: ")[1].splitlines()[0]
    assert f"`{FAKE_SPEC}`" in cell and "`renders the list`" in cell and "`saves`" in cell
    assert "Feature check (fake AI)" in cell and "ruling 148" in cell
    assert "hsi-check-1" not in cell and "fixture-h" not in cell, (
        "no run id in the cell (ruling 218)"
    )
    assert len(cell) <= witness.PASTE_LIMIT


def test_the_cell_text_counts_the_legs_it_cannot_fit() -> None:
    legs = [
        witness.Leg(FAKE_SPEC, f"F-003 › leg {n:02d} " + "x" * 60, "passed", ("F-003",))
        for n in range(12)
    ]
    cell = witness.paste_text(legs, "fake")
    assert len(cell) <= witness.PASTE_LIMIT
    shown = cell.count("`leg ")
    assert 0 < shown < 12 and f"; +{12 - shown} more." in cell


@pytest.mark.parametrize("outcome", ["failed", "skipped"])
def test_an_unverified_row_with_a_leg_not_passed_is_reported_not_failed(
    make, capsys, outcome: str
) -> None:
    legs = {
        f"{JUNIT_FAKE}::F-003 panel › renders": "passed",
        f"{JUNIT_FAKE}::F-003 panel › saves": outcome,
    }
    assert make(inventory(("F-003", "unverified", "Writer.")), summary(playwright=legs)) == 0
    text = out(capsys)
    assert "READY" not in text
    assert f"info: F-003 (unverified): 2 leg(s) mapped (1 passed, 1 {outcome}); not judged" in text


def test_an_unverified_row_no_leg_names_is_silent(make, capsys) -> None:
    legs = {f"{JUNIT_FAKE}::F-001 thing › opens": "passed"}
    inv = inventory(("F-001", "awaiting real tier", EV_FAKE), ("F-003", "unverified", EV_FAKE))
    assert make(inv, summary(playwright=legs)) == 0
    assert "F-003" not in out(capsys)


# -- half-built / leftover -----------------------------------------------------------------------


@pytest.mark.parametrize("status", ["half-built", "leftover"])
def test_half_built_and_leftover_rows_are_never_failed(make, capsys, status: str) -> None:
    legs = {
        f"{JUNIT_FAKE}::F-004 thing › broken": "failed",
        f"{JUNIT_FAKE}::F-004 thing › fixme": "skipped",
    }
    assert make(inventory(("F-004", status, EV_FAKE)), summary(playwright=legs)) == 0
    assert f"info: F-004 ({status}): 2 leg(s) mapped (1 failed, 1 skipped); not judged" in out(
        capsys
    )


# -- the two jobs: home from the spec titles -----------------------------------------------------


def test_title_homes_reads_test_and_describe_titles_only(tmp_path: Path) -> None:
    tree = spec_tree(
        tmp_path,
        {
            FAKE_SPEC: (
                "// test('F-901 a commented-out test', () => {});\n"
                " * test.describe('F-902 inside a doc comment', () => {});\n"
                "test.describe('golden path (F-010 to F-012) @critical', () => {\n"
                "  test.skip(!harness.ready, 'F-903 a skip reason, not a title');\n"
                "  test(\n    'F-013: a title on its own line',\n    async () => {\n"
                "      await test.step('F-904 a step', async () => {});\n    });\n"
                "  test.fixme('F-014 fixme still declares a test', async () => {});\n});\n"
            ),
            SEEDED_SPEC: "test.describe('seeded golden path (F-012, F-020) @critical', () => {});\n",
            "backend/tests/golden/external/test_backup.py": "def test_f100_reports_file():\n    pass\n",
        },
    )
    homes = witness.title_homes(tree)
    assert homes == {
        "F-010": {"fake"},
        "F-011": {"fake"},
        "F-012": {"fake", "seeded"},
        "F-013": {"fake"},
        "F-014": {"fake"},
        "F-020": {"seeded"},
        "F-100": {"fake"},
    }


def test_a_passing_evidence_mention_of_a_seeded_spec_cannot_move_a_titled_rows_home(
    make, capsys
) -> None:
    # The reviewer's case: prose cites a seeded spec, but only a fake-job spec's title names the row.
    evidence = (
        f"Green golden path `{FAKE_SPEC}`; unlike `{SEEDED_SPEC}`, which drives a seeded breaker."
    )
    specs = {
        FAKE_SPEC: "test.describe('thing (F-007) @critical', () => {});\n",
        SEEDED_SPEC: "test('seeded other', () => {});\n",
    }
    seeded = summary("fake-seeded", playwright={f"{JUNIT_SEEDED}::seeded other": "passed"})
    assert make(inventory(("F-007", "awaiting real tier", evidence)), seeded, specs=specs) == 0
    assert "not judged here (no leg in this run; the other job is their home): F-007" in out(capsys)


def test_a_row_named_only_in_seeded_titles_is_the_seeded_jobs(make, capsys) -> None:
    specs = {
        FAKE_SPEC: "test('fake other', () => {});\n",
        SEEDED_SPEC: "test.describe('seeded (F-005) @critical', () => {});\n",
    }
    inv = inventory(("F-005", "awaiting real tier", "Green golden path, see the PR."))
    fake = summary("fake", playwright={f"{JUNIT_FAKE}::fake other": "passed"})
    assert make(inv, fake, specs=specs) == 0, (
        "the fake AI job never fails a row it was not meant to run"
    )
    assert "not judged here (no leg in this run; the other job is their home): F-005" in out(capsys)
    seeded = summary(
        "fake-seeded", playwright={f"{JUNIT_SEEDED}::seeded @critical › flips": "passed"}
    )
    assert make(inv, seeded, specs=specs) == 1
    assert (
        "FAIL: F-005 (awaiting real tier): no leg in this run names it -- the seeded job is its home"
        in out(capsys)
    )


def test_the_seeded_job_judges_its_own_legs(make, capsys) -> None:
    specs = {SEEDED_SPEC: "test.describe('seeded (F-005) @critical', () => {});\n"}
    ok = summary(
        "fake-seeded", playwright={f"{JUNIT_SEEDED}::seeded (F-005) @critical › flips": "passed"}
    )
    assert make(inventory(("F-005", "awaiting real tier", EV_SEEDED)), ok, specs=specs) == 0
    assert (
        "Feature check (seeded): 1 legs read, 1 rows named, 1 claims witnessed, 0 failing"
        in out(capsys)
    )


def test_a_row_named_in_both_jobs_titles_needs_legs_in_each(make, capsys) -> None:
    specs = {
        FAKE_SPEC: "test.describe('reset (F-006) @critical', () => {});\n",
        SEEDED_SPEC: "test.describe('seeded reset (F-006) @critical', () => {});\n",
    }
    inv = inventory(("F-006", "awaiting real tier", EV_FAKE))
    fake = summary("fake", playwright={f"{JUNIT_FAKE}::reset (F-006) › clicks": "passed"})
    seeded = summary("fake-seeded", playwright={f"{JUNIT_SEEDED}::seeded other › flips": "passed"})
    assert make(inv, fake, seeded, specs=specs) == 1
    fake_part, seeded_part = out(capsys).split("Feature check (seeded), run")
    assert "FAIL" not in fake_part
    assert (
        "FAIL: F-006 (awaiting real tier): no leg in this run names it -- the seeded job is its home"
        in seeded_part
    )


def test_a_row_no_title_names_takes_its_home_from_its_evidence(make, capsys) -> None:
    inv = inventory(
        ("F-008", "awaiting real tier", EV_SEEDED), ("F-009", "awaiting real tier", EV_FAKE)
    )
    fake = summary("fake", playwright={f"{JUNIT_FAKE}::untitled › opens": "passed"})
    seeded = summary("fake-seeded", playwright={f"{JUNIT_SEEDED}::untitled › flips": "passed"})
    assert make(inv, fake, seeded) == 1
    fake_part, seeded_part = out(capsys).split("Feature check (seeded), run")
    assert "FAIL: F-009" in fake_part and "FAIL: F-008" not in fake_part
    assert "FAIL: F-008" in seeded_part and "FAIL: F-009" not in seeded_part


def test_a_failed_leg_fails_the_row_in_the_job_that_ran_it_only(make, capsys) -> None:
    specs = {
        FAKE_SPEC: "test.describe('reset (F-006) @critical', () => {});\n",
        SEEDED_SPEC: "test.describe('seeded (F-006) @critical', () => {});\n",
    }
    inv = inventory(("F-006", "awaiting real tier", EV_FAKE))
    fake = summary("fake", playwright={f"{JUNIT_FAKE}::reset (F-006) › clicks": "passed"})
    seeded = summary(
        "fake-seeded", playwright={f"{JUNIT_SEEDED}::seeded (F-006) › flips": "failed"}
    )
    assert make(inv, fake, seeded, specs=specs) == 1
    fake_part, seeded_part = out(capsys).split("Feature check (seeded), run")
    assert "FAIL" not in fake_part
    assert f"FAIL: F-006 (awaiting real tier): failed {SEEDED_SPEC}" in seeded_part


def test_a_spec_tree_with_no_golden_spec_is_a_read_error(make, capsys) -> None:
    legs = {f"{JUNIT_FAKE}::F-001 thing › opens": "passed"}
    assert make(inventory(("F-001", "works", EV_FAKE)), summary(playwright=legs), specs={}) == 2
    assert "no golden spec to read the rows' home jobs from" in out(capsys)


# -- known disagreements: they excuse legs, not rows ---------------------------------------------

KNOWN_F033 = f'[[known]]\nrow = "F-033"\njobs = ["fake"]\nlegs = ["{PUSH}"]\nwhy = "the push leg self-skips; owner rules"\n'
F033_LEGS = (
    "F-033: each card mirrors GET /api/summaries/latest",
    "F-033: the content region is a PAIR keyed on the API",
    "F-033: after a user reload both cards RE-DERIVE",
    PUSH,
)


def f033_run(*outcomes: str) -> dict:
    return summary(
        playwright={
            f"{JUNIT_FAKE}::summary cards @critical › {t}": o
            for t, o in zip(F033_LEGS, outcomes, strict=False)
        }
    )


def test_a_known_leg_that_skips_is_reported_not_failed(make, capsys) -> None:
    inv = inventory(("F-033", "awaiting real tier", EV_FAKE))
    assert make(inv, f033_run("passed", "passed", "passed", "skipped"), known=KNOWN_F033) == 0
    text = out(capsys)
    assert (
        f"KNOWN: F-033 (awaiting real tier): skipped {FAKE_SPEC} :: summary cards @critical › {PUSH}"
        in text
    )
    assert "known: the push leg self-skips; owner rules" in text


def test_a_known_entry_does_not_excuse_the_rows_other_legs(make, capsys) -> None:
    # The reviewer's reproduction: every F-033 leg skipped still reads FAIL, despite the entry.
    inv = inventory(("F-033", "awaiting real tier", EV_FAKE))
    assert make(inv, f033_run("skipped", "skipped", "skipped", "skipped"), known=KNOWN_F033) == 1
    text = out(capsys)
    fail = next(line for line in text.splitlines() if line.startswith("FAIL: F-033"))
    assert fail.count("skipped ") == 3 and PUSH not in fail, (
        "the three unlisted legs fail; the listed one is excused"
    )


def test_a_known_entry_does_not_excuse_a_row_with_no_legs(make, capsys) -> None:
    legs = {f"{JUNIT_FAKE}::other › opens": "passed"}
    assert (
        make(
            inventory(("F-033", "awaiting real tier", EV_FAKE)),
            summary(playwright=legs),
            known=KNOWN_F033,
        )
        == 1
    )
    text = out(capsys)
    assert "FAIL: F-033 (awaiting real tier): no leg in this run names it" in text
    assert f"lists `{PUSH}`, which this run did not map to F-033" in text


def test_a_known_entry_whose_listed_legs_all_pass_is_stale(make, capsys) -> None:
    inv = inventory(("F-033", "awaiting real tier", EV_FAKE))
    assert make(inv, f033_run("passed", "passed", "passed", "passed"), known=KNOWN_F033) == 1
    assert (
        f"F-033's known entry (inventory_witness_known.toml, fake job) lists `{PUSH}`, which passed"
        in out(capsys)
    )


def test_a_known_entry_whose_row_was_demoted_is_stale(make, capsys) -> None:
    inv = inventory(("F-033", "half-built", EV_FAKE))
    assert make(inv, f033_run("passed", "passed", "passed", "skipped"), known=KNOWN_F033) == 1
    assert "is stale: the row is half-built now, so remove the entry" in out(capsys)


def test_a_known_entry_for_the_other_job_does_not_excuse_this_one(make, capsys) -> None:
    known = KNOWN_F033.replace('["fake"]', '["seeded"]')
    inv = inventory(("F-033", "awaiting real tier", EV_FAKE))
    assert make(inv, f033_run("passed", "passed", "passed", "skipped"), known=known) == 1
    assert "FAIL: F-033 (awaiting real tier): skipped" in out(capsys)


@pytest.mark.parametrize(
    ("known", "reason"),
    [
        (
            '[[known]]\nrow = "F-999"\njobs = ["fake"]\nlegs = ["x"]\nwhy = "x"\n',
            "'F-999' is not an inventory row",
        ),
        (
            '[[known]]\nrow = "F-001"\njobs = ["real"]\nlegs = ["x"]\nwhy = "x"\n',
            "jobs ['real'] must be",
        ),
        (
            '[[known]]\nrow = "F-001"\njobs = ["fake"]\nwhy = "x"\n',
            "legs None must be a non-empty list",
        ),
        (
            '[[known]]\nrow = "F-001"\njobs = ["fake"]\nlegs = []\nwhy = "x"\n',
            "legs [] must be a non-empty list",
        ),
        (
            '[[known]]\nrow = "F-001"\njobs = ["fake"]\nlegs = ["x"]\nwhy = " "\n',
            "F-001 says no why",
        ),
        (
            '[[known]]\nrow = "F-001"\njobs = ["fake", "fake"]\nlegs = ["x"]\nwhy = "x"\n',
            "listed twice",
        ),
        ("[[known]\n", "known list:"),
        ('[[knwon]]\nrow = "F-001"\n', "expected only [[known]] tables"),
        ("known = 3\n", "expected only [[known]] tables"),
    ],
)
def test_a_bad_known_list_is_a_read_error(make, capsys, known: str, reason: str) -> None:
    legs = {f"{JUNIT_FAKE}::F-001 thing › opens": "passed"}
    assert make(inventory(("F-001", "works", EV_FAKE)), summary(playwright=legs), known=known) == 2
    text = out(capsys)
    assert "READ ERROR (fail closed)" in text and reason in text


# -- specs naming no row, unknown ids ------------------------------------------------------------


def test_golden_specs_naming_no_row_are_listed(make, capsys) -> None:
    legs = {
        f"{JUNIT_FAKE}::F-001 thing › opens": "passed",
        "../golden/guard-contract.spec.ts::golden guard contract @smoke › page.route throws": "passed",
        "../golden/guard-contract.spec.ts::golden guard contract @smoke › context.route throws": "passed",
    }
    backend = {"backend.tests.golden.external.test_metrics::test_scrape_parses": "passed"}
    assert (
        make(inventory(("F-001", "works", EV_FAKE)), summary(playwright=legs, backend=backend)) == 0
    )
    text = out(capsys)
    assert "names no row: frontend/tests/golden/guard-contract.spec.ts (2 leg(s))" in text
    assert "names no row: backend/tests/golden/external/test_metrics.py (1 leg(s))" in text
    assert f"names no row: {FAKE_SPEC}" not in text
    assert "2 specs name no row" in text


def test_a_leg_naming_a_row_the_inventory_lacks_fails(make, capsys) -> None:
    legs = {
        f"{JUNIT_FAKE}::F-001 thing › opens": "passed",
        f"{JUNIT_FAKE}::F-777 typo › opens": "passed",
    }
    assert make(inventory(("F-001", "works", EV_FAKE)), summary(playwright=legs)) == 1
    assert "FAIL: F-777 is not an inventory row, yet a leg names it" in out(capsys)


def test_backend_legs_witness_their_rows(make, capsys) -> None:
    legs = {f"{JUNIT_FAKE}::other › opens": "passed"}
    backend = {
        "backend.tests.golden.external.test_backup::test_f100_reports_file": "passed",
        "backend.tests.golden.external.test_backup::test_f100_delete": "skipped",
    }
    inv = inventory(
        (
            "F-100",
            "awaiting real tier",
            "Green golden path `backend/tests/golden/external/test_backup.py`.",
        )
    )
    assert make(inv, summary(playwright=legs, backend=backend)) == 1
    assert (
        "FAIL: F-100 (awaiting real tier): skipped backend/tests/golden/external/test_backup.py :: test_f100_delete"
        in out(capsys)
    )


# -- read errors (fail closed) -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (summary("real"), "mode 'real' is not a CI fake-tier run"),
        (summary("real-prod-shape"), "real-tier confirmation is the operator's (ruling 148)"),
        ({"mode": "fake", "results": {"smoke": "ok"}}, "no results.golden"),
        (
            {"mode": "fake", "results": {"golden": {"playwright": "image unavailable"}}},
            "has no playwright_specs",
        ),
        (summary(playwright={f"{JUNIT_FAKE}::F-001 x": "flaky"}), "has outcome 'flaky'"),
        (summary(playwright={f"{JUNIT_FAKE} F-001 x": "passed"}), "is not '<spec>::<title>'"),
        (summary(playwright={}), "the golden Playwright project executed no test"),
        (
            summary(playwright={f"{JUNIT_FAKE}::F-001 x": "passed"}, backend=["not", "a", "map"]),
            "backend_specs is not a mapping",
        ),
    ],
)
def test_a_summary_that_cannot_witness_is_a_read_error(
    make, capsys, data: dict, reason: str
) -> None:
    assert make(inventory(("F-001", "works", EV_FAKE)), data) == 2
    text = out(capsys)
    assert "READ ERROR (fail closed)" in text and reason in text


def test_an_empty_playwright_report_is_a_read_error_even_with_backend_legs(make, capsys) -> None:
    # An "image unavailable" fake run: no Playwright test ran, the backend pytest leg did.
    data = summary(
        playwright={},
        backend={"backend.tests.golden.external.test_backup::test_f100_reports_file": "passed"},
    )
    data["results"]["golden"]["playwright"] = "image unavailable"
    inv = inventory(("F-001", "works", EV_FAKE), ("F-100", "awaiting real tier", EV_FAKE))
    assert make(inv, data) == 2
    text = out(capsys)
    assert (
        "the golden Playwright project executed no test (playwright: 'image unavailable')" in text
    )
    assert "no leg in this run names it" not in text


def _files(tmp_path: Path) -> list[str]:
    inv = tmp_path / "inv.md"
    inv.write_text(inventory(("F-001", "works", EV_FAKE)), encoding="utf-8")
    known = tmp_path / "k.toml"
    known.write_text("", encoding="utf-8")
    tree = spec_tree(tmp_path / "tree", NO_TITLES)
    return ["--inventory", str(inv), "--known", str(known), "--specs-root", str(tree)]


def test_an_unreadable_summary_is_a_read_error(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "summary.json"
    bad.write_text("{not json", encoding="utf-8")
    assert witness.main(["--summary", str(bad), *_files(tmp_path)]) == 2
    assert "cannot read the run summary" in out(capsys)
    assert witness.main(["--summary", str(tmp_path / "absent.json"), *_files(tmp_path)]) == 2


def test_the_run_root_must_hold_exactly_one_summary(tmp_path: Path, capsys) -> None:
    root = tmp_path / "root"
    root.mkdir()
    args = ["--run-root", str(root), *_files(tmp_path)]
    assert witness.main(args) == 2
    assert "found 0 (the harness wrote no summary)" in out(capsys)
    for name in ("a", "b"):
        path = root / name / "artifacts" / "summary.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(summary(playwright={f"{JUNIT_FAKE}::F-001 x": "passed"})), encoding="utf-8"
        )
    assert witness.main(args) == 2
    assert "found 2" in out(capsys)


def test_the_run_root_form_reads_the_one_run(make, capsys) -> None:
    legs = {f"{JUNIT_FAKE}::F-001 thing › opens": "passed"}
    assert make(inventory(("F-001", "works", EV_FAKE)), summary(playwright=legs), as_root=True) == 0
    assert "inventory witness -- Feature check (fake AI), run hsi-check-1 at fixture-h" in out(
        capsys
    )


@pytest.mark.parametrize(
    ("inv", "reason"),
    [
        (inventory(("F-001", "done", EV_FAKE)), "status 'done' is not one of"),
        (
            inventory(("F-001", "works", EV_FAKE), ("F-001", "works", EV_FAKE)),
            "F-001 is declared twice",
        ),
        ("# Feature Inventory\n\nno tables here\n", "the inventory has no F-NNN rows"),
        (
            inventory(("F-001", "works", EV_FAKE)).replace("| F-001 |", "| X-001 |"),
            "is not an F-NNN row",
        ),
    ],
)
def test_an_inventory_that_cannot_be_read_is_a_read_error(
    make, capsys, inv: str, reason: str
) -> None:
    legs = {f"{JUNIT_FAKE}::F-001 thing › opens": "passed"}
    assert make(inv, summary(playwright=legs)) == 2
    text = out(capsys)
    assert "READ ERROR (fail closed)" in text and reason in text


def test_a_missing_inventory_or_known_list_is_a_read_error(tmp_path: Path, capsys) -> None:
    run = tmp_path / "summary.json"
    run.write_text(
        json.dumps(summary(playwright={f"{JUNIT_FAKE}::F-001 x": "passed"})), encoding="utf-8"
    )
    args = _files(tmp_path)
    no_inventory = [*args[:1], str(tmp_path / "no.md"), *args[2:]]
    assert witness.main(["--summary", str(run), *no_inventory]) == 2
    assert "cannot read the inventory" in out(capsys)
    no_known = [*args[:3], str(tmp_path / "no.toml"), *args[4:]]
    assert witness.main(["--summary", str(run), *no_known]) == 2
    assert "cannot read the known-disagreement list" in out(capsys)


# -- the real files ------------------------------------------------------------------------------


def test_the_witness_reads_the_rows_the_summary_checker_counts() -> None:
    arith = _load(
        "check_inventory_summary_arith_for_witness",
        REPO_ROOT / "scripts" / "check-inventory-summary-arith.py",
    )
    text = (REPO_ROOT / "docs" / "reference" / "feature-inventory.md").read_text(encoding="utf-8")
    _, census = arith.check(text)
    rows = witness.read_inventory(text)
    assert len(rows) == census["rows"]
    assert {r.status for r in rows.values()} <= set(witness.STATUSES)


def test_the_checked_in_known_list_reads() -> None:
    text = (REPO_ROOT / "docs" / "reference" / "feature-inventory.md").read_text(encoding="utf-8")
    known = witness.read_known(
        witness.KNOWN.read_text(encoding="utf-8"), witness.read_inventory(text)
    )
    assert all(entry.legs and entry.why for entry in known.values())


@pytest.mark.parametrize("known", ["", '# only comments\n#   [[known]]\n#   row = "F-001"\n'])
def test_a_known_list_with_no_entries_is_valid(make, capsys, known: str) -> None:
    # Ruling 219 emptied the checked-in list: an empty or comment-only file reads as no entries.
    assert witness.read_known(known, {"F-001": witness.Row("F-001", "works", EV_FAKE)}) == {}
    legs = {f"{JUNIT_FAKE}::F-001 thing › opens": "passed"}
    assert make(inventory(("F-001", "works", EV_FAKE)), summary(playwright=legs), known=known) == 0
    assert "0 failing, 0 known" in out(capsys)


def test_the_seeded_job_runs_the_witness_after_the_harness_ran() -> None:
    """The seeded job keeps the single-job shape: harness, then the witness over its own run.

    [r264] split the fake side into shards + fan-in (its own test below); the seeded
    golden project stays one job on one stack (the package's Unchanged clause), and
    so does its witness step — pinned exactly as it was.
    """
    yaml = pytest.importorskip("yaml")
    ci = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    steps = ci["jobs"]["feature-check-seeded"]["steps"]
    runs = [str(step.get("run", "")) for step in steps]
    at_harness = next(
        i for i, run in enumerate(runs) if "scripts/feature-check.sh --fake --seeded" in run
    )
    at_witness = next(
        i for i, run in enumerate(runs) if "python3 -m scripts.uplevel.inventory_witness" in run
    )
    assert at_witness == at_harness + 1, "the witness runs right after the golden project"
    assert steps[at_harness]["id"] == "harness"
    step = steps[at_witness]
    # Red or green harness: run, so a red golden leg still names its rows. Harness never ran
    # (an image build failed first): do not add a second "found 0" red.
    assert step["if"] == "${{ !cancelled() && steps.harness.outcome != 'skipped' }}"
    assert step["env"]["FEATURE_CHECK_ROOT"] == steps[at_harness]["env"]["FEATURE_CHECK_ROOT"]
    assert '--run-root "$FEATURE_CHECK_ROOT"' in step["run"]


def test_the_fan_in_runs_the_witness_once_over_the_merged_union() -> None:
    """[r264] The fake side's witness moved to the fan-in, which runs it ONCE over the
    merged union — a row judged on the union exactly as the single job judged it (the
    Build box). The shards must NOT run it: the witness judges one summary; four
    per-shard judgments would judge each row on a partial leg set and fail rows whose
    legs a sibling shard ran.
    """
    yaml = pytest.importorskip("yaml")
    ci = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    # the fan-in: the merge writes the merged summary, the witness reads it over --run-root.
    # Merge and witness share ONE step (the invocation sits inside the merge step's
    # run body), so the witness's run body IS the merge step's run body.
    fan = ci["jobs"]["feature-check-fan-in"]["steps"]
    runs = [str(step.get("run", "")) for step in fan]
    at_witness = next(
        i for i, run in enumerate(runs) if "python3 -m scripts.uplevel.inventory_witness" in run
    )
    witness = fan[at_witness]
    assert '--run-root "$FEATURE_CHECK_ROOT"' in witness["run"], (
        "the witness reads the merged run root"
    )
    merge_step = witness
    assert "summary.json" in merge_step["run"], "the witness step also writes the merged summary"
    # the merged summary is fake-mode: the witness refuses any other tier
    assert '"mode": "fake"' in merge_step["run"] or "'mode': 'fake'" in merge_step["run"]
    # the shards: NO witness anywhere in their steps
    shards = ci["jobs"]["feature-check-shards"]
    shard_runs = "\n".join(str(s.get("run", "")) for s in shards["steps"] if s.get("run"))
    assert "inventory_witness" not in shard_runs, "a shard must not judge a partial leg set"
    assert shards["name"] == "Feature check (fake AI)", "the shard matrix carries the tier's name"
