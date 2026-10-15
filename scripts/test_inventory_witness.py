#!/usr/bin/env python3
"""Tests for scripts/uplevel/inventory_witness.py ([r218], ruling 218): one per rule.

Run explicitly; outside testpaths (like every scripts/test_*.py gate suite):

    uv run python -m pytest scripts/test_inventory_witness.py -q

Each test builds a tiny inventory, a Feature check ``summary.json`` and a known-disagreement list
in ``tmp_path`` and calls the CLI's ``main``, so the exit code and the printed line are what is
pinned. Nothing here judges this checkout's inventory against a real run (that is the CI step's
job, which has the run); one test only checks the witness reads the real inventory's rows the
way ``scripts/check-inventory-summary-arith.py`` counts them, so the two parsers cannot drift.
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


def inventory(*rows: tuple[str, str, str]) -> str:
    """rows: (id, status, evidence). One §3-shaped table, `\\|` escapes included."""
    lines = [
        f"| {rid} | Surface `/x` | does a \\| thing | `GET /api/x` | `h` at `backend/x.py:1` | {status}"
        f" | {evidence} | `frontend/src/x.ts` | — |  |  |"
        for rid, status, evidence in rows
    ]
    return "# Feature Inventory\n\n### 3.1 Area\n\n<!-- prettier-ignore -->\n" + HEADER + "\n".join(lines) + "\n"


def summary(mode: str = "fake", playwright=None, backend=None, **extra) -> dict:
    golden: dict = {"playwright": "ok", "playwright_specs": playwright if playwright is not None else {}}
    if backend is not None:
        golden["backend_specs"] = backend
    return {"mode": mode, "project": "hsi-check-1", "commit": "fixture-head-commit", "results": {"golden": golden}, **extra}


@pytest.fixture
def make(tmp_path: Path):
    """Write the three inputs; return a runner giving (exit code, stdout+stderr)."""

    def run(inv: str, *summaries: dict, known: str = "", as_root: bool = False):
        inv_path = tmp_path / "inventory.md"
        inv_path.write_text(inv, encoding="utf-8")
        known_path = tmp_path / "known.toml"
        known_path.write_text(known, encoding="utf-8")
        args = ["--inventory", str(inv_path), "--known", str(known_path)]
        for n, data in enumerate(summaries):
            path = tmp_path / f"root{n}" / "hsi-check-1" / "artifacts" / "summary.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(data), encoding="utf-8")
            args += ["--run-root", str(tmp_path / f"root{n}")] if as_root else ["--summary", str(path)]
        return witness.main(args)

    return run


def out(capsys) -> str:
    captured = capsys.readouterr()
    return captured.out + captured.err


EV_FAKE = f"Green golden path `{FAKE_SPEC}`."
EV_SEEDED = f"Green golden path `{SEEDED_SPEC}`."
EV_BOTH = f"Green golden paths `{FAKE_SPEC}` and `{SEEDED_SPEC}`."


# -- mapping -------------------------------------------------------------------------------------


def test_the_innermost_title_segment_naming_ids_wins() -> None:
    title = "golden path: embeds (F-164..F-167, F-169) @critical › F-165 /gpu-metrics binds"
    assert witness.leg_rows(title, backend=False) == ("F-165",)


def test_a_test_title_naming_no_id_inherits_its_describes_ids() -> None:
    title = "DO-2 access (F-240 to F-243) › the guard survives the access drive"
    assert witness.leg_rows(title, backend=False) == ("F-240", "F-243")


def test_a_range_names_its_two_ends_only() -> None:
    assert witness.leg_rows("embeds (F-164..F-167) @critical › renders", backend=False) == ("F-164", "F-167")


def test_package_names_like_fe_4_are_not_row_ids() -> None:
    assert witness.leg_rows("FE-4 cameras (DO-3) › lists them", backend=False) == ()


def test_a_pytest_leg_carries_its_id_as_an_f_word_in_its_name() -> None:
    assert witness.leg_rows("test_f190_feature_toggle_save_roundtrip", backend=True) == ("F-190",)
    assert witness.leg_rows("test_empty_patch_does_not_clobber", backend=True) == ()
    assert witness.leg_rows("test_x", backend=True, classes=["TestThing_f250"]) == ("F-250",)
    assert witness.leg_rows("test_buff100_size", backend=True) == ()


def test_specs_resolve_to_repo_paths() -> None:
    assert witness._spec_path("../golden/shell/nav.spec.ts", False) == ("frontend/tests/golden/shell/nav.spec.ts", [])
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
    legs = {f"{JUNIT_FAKE}::F-001 thing › opens": "passed", f"{JUNIT_FAKE}::F-001 thing › saves": "passed"}
    assert make(inventory(("F-001", status, EV_FAKE)), summary(playwright=legs)) == 0
    assert "1 claims witnessed, 0 failing" in out(capsys)


@pytest.mark.parametrize("outcome", ["failed", "skipped"])
@pytest.mark.parametrize("status", ["awaiting real tier", "works"])
def test_a_claim_with_a_failed_or_skipped_leg_fails(make, capsys, status: str, outcome: str) -> None:
    legs = {f"{JUNIT_FAKE}::F-001 thing › opens": "passed", f"{JUNIT_FAKE}::F-001 thing › saves": outcome}
    assert make(inventory(("F-001", status, EV_FAKE)), summary(playwright=legs)) == 1
    text = out(capsys)
    assert f"FAIL: F-001 ({status}): {outcome} {FAKE_SPEC} :: F-001 thing › saves" in text
    assert "opens" not in text.split("FAIL:")[1].splitlines()[0], "only the leg that did not pass is named"


def test_a_fixme_leg_reads_as_skipped_and_fails_the_claim(make, capsys) -> None:
    # Playwright's junit writes <skipped/> for test.fixme; feature_check.junit_results records "skipped".
    legs = {f"{JUNIT_FAKE}::F-001 thing › opens": "passed", f"{JUNIT_FAKE}::F-001 thing › is broken today": "skipped"}
    assert make(inventory(("F-001", "awaiting real tier", EV_FAKE)), summary(playwright=legs)) == 1


def test_a_claim_no_leg_names_fails_in_its_home_job(make, capsys) -> None:
    legs = {f"{JUNIT_FAKE}::F-002 other › opens": "passed"}
    inv = inventory(("F-001", "awaiting real tier", EV_FAKE), ("F-002", "awaiting real tier", EV_FAKE))
    assert make(inv, summary(playwright=legs)) == 1
    assert "FAIL: F-001 (awaiting real tier): no leg in this run names it" in out(capsys)


def test_a_claim_whose_evidence_names_no_golden_spec_is_the_fake_jobs(make, capsys) -> None:
    legs = {f"{JUNIT_FAKE}::F-002 other › opens": "passed"}
    inv = inventory(("F-001", "works", "Real tier 2026-10-01; cites `backend/x.py:1`."), ("F-002", "works", EV_FAKE))
    assert make(inv, summary(playwright=legs)) == 1
    assert "FAIL: F-001 (works): no leg in this run names it" in out(capsys)


# -- unverified ----------------------------------------------------------------------------------


def test_an_unverified_row_whose_legs_all_passed_is_ready_to_flip_with_its_cell_text(make, capsys) -> None:
    legs = {f"{JUNIT_FAKE}::F-003 panel (F-003) › renders the list": "passed", f"{JUNIT_FAKE}::F-003 panel › saves": "passed"}
    assert make(inventory(("F-003", "unverified", "Writer `backend/x.py:1`.")), summary(playwright=legs)) == 0
    text = out(capsys)
    assert "READY to flip: F-003 (unverified -> awaiting real tier): 2 leg(s), each passed in this job." in text
    cell = text.split("evidence text: ")[1].splitlines()[0]
    assert f"`{FAKE_SPEC}`" in cell and "`renders the list`" in cell and "`saves`" in cell
    assert "Feature check (fake AI)" in cell and "ruling 148" in cell
    assert "hsi-check-1" not in cell and "fixture-h" not in cell, "no run id in the cell (ruling 218)"
    assert len(cell) <= witness.PASTE_LIMIT


def test_the_cell_text_counts_the_legs_it_cannot_fit() -> None:
    legs = [witness.Leg(FAKE_SPEC, f"F-003 › leg {n:02d} " + "x" * 60, "passed", ("F-003",)) for n in range(12)]
    cell = witness.paste_text(legs, "fake")
    assert len(cell) <= witness.PASTE_LIMIT
    shown = cell.count("`leg ")
    assert 0 < shown < 12 and f"; +{12 - shown} more." in cell


@pytest.mark.parametrize("outcome", ["failed", "skipped"])
def test_an_unverified_row_with_a_leg_not_passed_is_reported_not_failed(make, capsys, outcome: str) -> None:
    legs = {f"{JUNIT_FAKE}::F-003 panel › renders": "passed", f"{JUNIT_FAKE}::F-003 panel › saves": outcome}
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
    legs = {f"{JUNIT_FAKE}::F-004 thing › broken": "failed", f"{JUNIT_FAKE}::F-004 thing › fixme": "skipped"}
    assert make(inventory(("F-004", status, EV_FAKE)), summary(playwright=legs)) == 0
    assert f"info: F-004 ({status}): 2 leg(s) mapped (1 failed, 1 skipped); not judged" in out(capsys)


# -- the two jobs --------------------------------------------------------------------------------


def test_a_row_whose_legs_live_only_in_the_seeded_job_is_not_failed_by_the_fake_job(make, capsys) -> None:
    legs = {f"{JUNIT_FAKE}::F-001 thing › opens": "passed"}
    inv = inventory(("F-001", "works", EV_FAKE), ("F-005", "awaiting real tier", EV_SEEDED))
    assert make(inv, summary("fake", playwright=legs)) == 0
    assert "not judged here (no leg in this run; the other job is their home): F-005" in out(capsys)


def test_the_seeded_job_judges_its_own_legs(make, capsys) -> None:
    inv = inventory(("F-005", "awaiting real tier", EV_SEEDED))
    ok = summary("fake-seeded", playwright={f"{JUNIT_SEEDED}::seeded (F-005) @critical › flips": "passed"})
    assert make(inv, ok) == 0
    assert "Feature check (seeded): 1 legs read, 1 rows named, 1 claims witnessed, 0 failing" in out(capsys)


def test_the_seeded_job_fails_its_home_row_when_no_leg_names_it(make, capsys) -> None:
    inv = inventory(("F-001", "works", EV_FAKE), ("F-005", "awaiting real tier", EV_SEEDED))
    run = summary("fake-seeded", playwright={f"{JUNIT_SEEDED}::seeded @critical › flips": "passed"})
    assert make(inv, run) == 1
    text = out(capsys)
    assert "FAIL: F-005 (awaiting real tier): no leg in this run names it" in text
    assert "FAIL: F-001" not in text, "a row whose home is the fake AI job is not the seeded job's to fail"


def test_a_row_whose_evidence_names_both_jobs_specs_needs_legs_in_each(make, capsys) -> None:
    inv = inventory(("F-006", "awaiting real tier", EV_BOTH))
    fake = summary("fake", playwright={f"{JUNIT_FAKE}::reset (F-006) › clicks": "passed"})
    seeded = summary("fake-seeded", playwright={f"{JUNIT_SEEDED}::seeded › flips": "passed"})
    assert make(inv, fake, seeded) == 1
    text = out(capsys)
    seeded_part = text.split("Feature check (seeded), run")[1]
    assert "FAIL: F-006" in seeded_part and "FAIL: F-006" not in text.split("Feature check (seeded), run")[0]


def test_a_failed_leg_fails_the_row_in_the_job_that_ran_it_only(make, capsys) -> None:
    inv = inventory(("F-006", "awaiting real tier", EV_BOTH))
    fake = summary("fake", playwright={f"{JUNIT_FAKE}::reset (F-006) › clicks": "passed"})
    seeded = summary("fake-seeded", playwright={f"{JUNIT_SEEDED}::seeded (F-006) › flips": "failed"})
    assert make(inv, fake, seeded) == 1
    fake_part, seeded_part = out(capsys).split("Feature check (seeded), run")
    assert "FAIL" not in fake_part
    assert f"FAIL: F-006 (awaiting real tier): failed {SEEDED_SPEC}" in seeded_part


# -- known disagreements -------------------------------------------------------------------------

KNOWN_F001 = '[[known]]\nrow = "F-001"\njobs = ["fake"]\nwhy = "the push leg self-skips; owner rules"\n'


def test_a_known_disagreement_is_reported_not_failed(make, capsys) -> None:
    legs = {f"{JUNIT_FAKE}::F-001 thing › opens": "passed", f"{JUNIT_FAKE}::F-001 thing › push": "skipped"}
    assert make(inventory(("F-001", "awaiting real tier", EV_FAKE)), summary(playwright=legs), known=KNOWN_F001) == 0
    text = out(capsys)
    assert "KNOWN: F-001 (awaiting real tier): skipped" in text
    assert "known: the push leg self-skips; owner rules" in text


def test_a_known_entry_whose_row_now_agrees_fails_until_removed(make, capsys) -> None:
    legs = {f"{JUNIT_FAKE}::F-001 thing › opens": "passed", f"{JUNIT_FAKE}::F-001 thing › push": "passed"}
    assert make(inventory(("F-001", "awaiting real tier", EV_FAKE)), summary(playwright=legs), known=KNOWN_F001) == 1
    assert "F-001 is on the known-disagreement list for the fake job but agrees with this run" in out(capsys)


def test_a_known_entry_whose_row_was_demoted_is_stale_too(make, capsys) -> None:
    legs = {f"{JUNIT_FAKE}::F-001 thing › push": "skipped"}
    assert make(inventory(("F-001", "half-built", EV_FAKE)), summary(playwright=legs), known=KNOWN_F001) == 1
    assert "agrees with this run: remove its entry" in out(capsys)


def test_a_known_entry_for_the_other_job_does_not_excuse_this_one(make, capsys) -> None:
    known = KNOWN_F001.replace('["fake"]', '["seeded"]')
    legs = {f"{JUNIT_FAKE}::F-001 thing › push": "skipped"}
    assert make(inventory(("F-001", "awaiting real tier", EV_FAKE)), summary(playwright=legs), known=known) == 1
    assert "FAIL: F-001 (awaiting real tier): skipped" in out(capsys)


@pytest.mark.parametrize(
    ("known", "reason"),
    [
        ('[[known]]\nrow = "F-999"\njobs = ["fake"]\nwhy = "x"\n', "'F-999' is not an inventory row"),
        ('[[known]]\nrow = "F-001"\njobs = ["real"]\nwhy = "x"\n', "jobs ['real'] must be"),
        ('[[known]]\nrow = "F-001"\njobs = ["fake"]\nwhy = " "\n', "F-001 says no why"),
        ('[[known]]\nrow = "F-001"\njobs = ["fake", "fake"]\nwhy = "x"\n', "listed twice"),
        ("[[known]\n", "known list:"),
        ('[[knwon]]\nrow = "F-001"\n', "expected only [[known]] tables"),
        ('known = 3\n', "expected only [[known]] tables"),
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
    assert make(inventory(("F-001", "works", EV_FAKE)), summary(playwright=legs, backend=backend)) == 0
    text = out(capsys)
    assert "names no row: frontend/tests/golden/guard-contract.spec.ts (2 leg(s))" in text
    assert "names no row: backend/tests/golden/external/test_metrics.py (1 leg(s))" in text
    assert f"names no row: {FAKE_SPEC}" not in text
    assert "2 specs name no row" in text


def test_a_leg_naming_a_row_the_inventory_lacks_fails(make, capsys) -> None:
    legs = {f"{JUNIT_FAKE}::F-001 thing › opens": "passed", f"{JUNIT_FAKE}::F-777 typo › opens": "passed"}
    assert make(inventory(("F-001", "works", EV_FAKE)), summary(playwright=legs)) == 1
    assert "FAIL: F-777 is not an inventory row, yet a leg names it" in out(capsys)


def test_backend_legs_witness_their_rows(make, capsys) -> None:
    backend = {
        "backend.tests.golden.external.test_backup::test_f100_reports_file": "passed",
        "backend.tests.golden.external.test_backup::test_f100_delete": "skipped",
    }
    inv = inventory(("F-100", "awaiting real tier", "Green golden path `backend/tests/golden/external/test_backup.py`."))
    assert make(inv, summary(playwright={}, backend=backend)) == 1
    assert "FAIL: F-100 (awaiting real tier): skipped backend/tests/golden/external/test_backup.py :: test_f100_delete" in out(capsys)


# -- read errors (fail closed) -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (summary("real"), "mode 'real' is not a CI fake-tier run"),
        (summary("real-prod-shape"), "real-tier confirmation is the operator's (ruling 148)"),
        ({"mode": "fake", "results": {"smoke": "ok"}}, "no results.golden"),
        ({"mode": "fake", "results": {"golden": {"playwright": "image unavailable"}}}, "has no playwright_specs"),
        (summary(playwright={f"{JUNIT_FAKE}::F-001 x": "flaky"}), "has outcome 'flaky'"),
        (summary(playwright={f"{JUNIT_FAKE} F-001 x": "passed"}), "is not '<spec>::<title>'"),
        (summary(playwright={}), "the run executed no golden leg"),
        (summary(playwright={f"{JUNIT_FAKE}::F-001 x": "passed"}, backend=["not", "a", "map"]), "backend_specs is not a mapping"),
    ],
)
def test_a_summary_that_cannot_witness_is_a_read_error(make, capsys, data: dict, reason: str) -> None:
    assert make(inventory(("F-001", "works", EV_FAKE)), data) == 2
    text = out(capsys)
    assert "READ ERROR (fail closed)" in text and reason in text


def test_an_unreadable_summary_is_a_read_error(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "summary.json"
    bad.write_text("{not json", encoding="utf-8")
    inv = tmp_path / "inv.md"
    inv.write_text(inventory(("F-001", "works", EV_FAKE)), encoding="utf-8")
    known = tmp_path / "k.toml"
    known.write_text("", encoding="utf-8")
    assert witness.main(["--summary", str(bad), "--inventory", str(inv), "--known", str(known)]) == 2
    assert "cannot read the run summary" in out(capsys)
    assert witness.main(["--summary", str(tmp_path / "absent.json"), "--inventory", str(inv), "--known", str(known)]) == 2


def test_the_run_root_must_hold_exactly_one_summary(tmp_path: Path, capsys) -> None:
    inv = tmp_path / "inv.md"
    inv.write_text(inventory(("F-001", "works", EV_FAKE)), encoding="utf-8")
    known = tmp_path / "k.toml"
    known.write_text("", encoding="utf-8")
    root = tmp_path / "root"
    root.mkdir()
    args = ["--run-root", str(root), "--inventory", str(inv), "--known", str(known)]
    assert witness.main(args) == 2
    assert "found 0 (the harness wrote no summary)" in out(capsys)
    for name in ("a", "b"):
        path = root / name / "artifacts" / "summary.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(summary(playwright={f"{JUNIT_FAKE}::F-001 x": "passed"})), encoding="utf-8")
    assert witness.main(args) == 2
    assert "found 2" in out(capsys)


def test_the_run_root_form_reads_the_one_run(make, capsys) -> None:
    legs = {f"{JUNIT_FAKE}::F-001 thing › opens": "passed"}
    assert make(inventory(("F-001", "works", EV_FAKE)), summary(playwright=legs), as_root=True) == 0
    assert "inventory witness -- Feature check (fake AI), run hsi-check-1 at fixture-h" in out(capsys)


@pytest.mark.parametrize(
    ("inv", "reason"),
    [
        (inventory(("F-001", "done", EV_FAKE)), "status 'done' is not one of"),
        (inventory(("F-001", "works", EV_FAKE), ("F-001", "works", EV_FAKE)), "F-001 is declared twice"),
        ("# Feature Inventory\n\nno tables here\n", "the inventory has no F-NNN rows"),
        (inventory(("F-001", "works", EV_FAKE)).replace("| F-001 |", "| X-001 |"), "is not an F-NNN row"),
    ],
)
def test_an_inventory_that_cannot_be_read_is_a_read_error(make, capsys, inv: str, reason: str) -> None:
    legs = {f"{JUNIT_FAKE}::F-001 thing › opens": "passed"}
    assert make(inv, summary(playwright=legs)) == 2
    text = out(capsys)
    assert "READ ERROR (fail closed)" in text and reason in text


def test_a_missing_inventory_or_known_list_is_a_read_error(tmp_path: Path, capsys) -> None:
    run = tmp_path / "summary.json"
    run.write_text(json.dumps(summary(playwright={f"{JUNIT_FAKE}::F-001 x": "passed"})), encoding="utf-8")
    inv = tmp_path / "inv.md"
    inv.write_text(inventory(("F-001", "works", EV_FAKE)), encoding="utf-8")
    assert witness.main(["--summary", str(run), "--inventory", str(tmp_path / "no.md"), "--known", str(inv)]) == 2
    assert "cannot read the inventory" in out(capsys)
    assert witness.main(["--summary", str(run), "--inventory", str(inv), "--known", str(tmp_path / "no.toml")]) == 2
    assert "cannot read the known-disagreement list" in out(capsys)


# -- the real files ------------------------------------------------------------------------------


def test_the_witness_reads_the_rows_the_summary_checker_counts() -> None:
    arith = _load("check_inventory_summary_arith_for_witness", REPO_ROOT / "scripts" / "check-inventory-summary-arith.py")
    text = (REPO_ROOT / "docs" / "reference" / "feature-inventory.md").read_text(encoding="utf-8")
    _, census = arith.check(text)
    rows = witness.read_inventory(text)
    assert len(rows) == census["rows"]
    assert {r.status for r in rows.values()} <= set(witness.STATUSES)


def test_the_checked_in_known_list_reads() -> None:
    text = (REPO_ROOT / "docs" / "reference" / "feature-inventory.md").read_text(encoding="utf-8")
    known = witness.read_known(witness.KNOWN.read_text(encoding="utf-8"), witness.read_inventory(text))
    assert all(why for why in known.values())


def test_both_feature_check_jobs_run_the_witness_after_the_harness() -> None:
    yaml = pytest.importorskip("yaml")
    ci = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    for job_id, harness in (("feature-check", "--fake --image-tag"), ("feature-check-seeded", "--fake --seeded")):
        steps = ci["jobs"][job_id]["steps"]
        runs = [str(step.get("run", "")) for step in steps]
        at_harness = next(i for i, run in enumerate(runs) if f"scripts/feature-check.sh {harness}" in run)
        at_witness = next(i for i, run in enumerate(runs) if "python3 -m scripts.uplevel.inventory_witness" in run)
        assert at_witness == at_harness + 1, f"{job_id}: the witness runs right after the golden project"
        step = steps[at_witness]
        assert step["if"] == "${{ !cancelled() }}", f"{job_id}: a red golden leg still names its rows"
        assert step["env"]["FEATURE_CHECK_ROOT"] == steps[at_harness]["env"]["FEATURE_CHECK_ROOT"]
        assert '--run-root "$FEATURE_CHECK_ROOT"' in step["run"]
