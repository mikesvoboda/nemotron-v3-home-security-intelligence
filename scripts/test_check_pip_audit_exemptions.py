#!/usr/bin/env python3
"""Tests for scripts/check-pip-audit-exemptions.py (the Python audit gate).

The gate replaces the bare `pip-audit … --ignore-vuln CVE-…` in
dependency-audit.yml, so the failure modes below ARE the gate's teeth — the
same doctrine as scripts/test_check_npm_audit_exemptions.py (its npm twin),
run explicitly outside testpaths:

    uv run python -m pytest scripts/test_check_pip_audit_exemptions.py -q

The Done-when clause this suite exists for: "the CI audit fails on a fixture
advisory that is not on the dismissal list" — test_unexempted_fixture_advisory_is_red
is that fixture, and the committed registry's emptiness is what makes it red.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent
CHECKER = REPO / "check-pip-audit-exemptions.py"
COMMITTED_REGISTRY = REPO.parent / ".pip-audit-exemptions.json"
AUDIT_WORKFLOW = REPO.parent / ".github" / "workflows" / "dependency-audit.yml"

FUTURE = "2099-01-01"

# A fake advisory in the exact shape pip-audit -f json emits.
FIXTURE_ID = "CVE-2099-000001"
FIXTURE_PKG = "fixturelib"
FIXTURE_PIN = "1.2.3"


def audit_doc(vulns: list[dict], clean_pkgs: list[str] | None = None) -> str:
    """vulns: [{id, pkg, version, fix_versions, aliases}] -> pip-audit JSON shape."""
    deps: dict[str, dict] = {}
    for pkg in clean_pkgs or []:
        deps[pkg] = {"name": pkg, "version": "9.9.9", "vulns": []}
    for v in vulns:
        dep = deps.setdefault(
            v.get("pkg", FIXTURE_PKG),
            {
                "name": v.get("pkg", FIXTURE_PKG),
                "version": v.get("version", FIXTURE_PIN),
                "vulns": [],
            },
        )
        vuln = {"id": v["id"], "fix_versions": v.get("fix_versions", [])}
        if v.get("aliases"):
            vuln["aliases"] = v["aliases"]
        dep["vulns"].append(vuln)
    return json.dumps({"dependencies": list(deps.values())})


class Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path

    def run(self, audit_json: str, registry: dict | None, registry_exists: bool = True):
        reg = self.tmp / "registry.json"
        if registry_exists:
            reg.write_text(json.dumps(registry if registry is not None else {"exceptions": []}))
        doc = self.tmp / "pa.json"
        doc.write_text(audit_json)
        return subprocess.run(  # noqa: PLW1510 - the whole point is checking rc
            [
                sys.executable,
                str(CHECKER),
                "--audit-json",
                str(doc),
                "--registry",
                str(reg),
                "--warn-days",
                "14",
            ],
            capture_output=True,
            text=True,
        )


def entry(vid: str, pkg: str = FIXTURE_PKG, review: str = FUTURE, **extra: str) -> dict:
    return {"id": vid, "package": pkg, "severity": "high", "reviewBy": review, **extra}


FIXTURE_FINDING = [{"id": FIXTURE_ID, "pkg": FIXTURE_PKG}]


def test_clean_audit_with_empty_registry_is_green(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(audit_doc([]), {"exceptions": []})
    assert r.returncode == 0, r.stdout + r.stderr


def test_unexempted_fixture_advisory_is_red(tmp_path: Path) -> None:
    """The O1.8 Done-when: a new advisory NOT on the dismissal list fails CI."""
    h = Harness(tmp_path)
    r = h.run(audit_doc(FIXTURE_FINDING), {"exceptions": []})
    assert r.returncode == 1
    assert FIXTURE_ID in r.stderr
    assert "UNEXEMPTED" in r.stderr


def test_valid_exemption_is_green(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    reg = {"exceptions": [entry(FIXTURE_ID)]}
    r = h.run(audit_doc(FIXTURE_FINDING), reg)
    assert r.returncode == 0, r.stdout + r.stderr


def test_missing_registry_fails_closed(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(audit_doc([]), None, registry_exists=False)
    assert r.returncode == 1
    assert "MISSING" in r.stderr


def test_expired_review_by_is_red(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    reg = {"exceptions": [entry(FIXTURE_ID, review="2020-01-01")]}
    r = h.run(audit_doc(FIXTURE_FINDING), reg)
    assert r.returncode == 1
    assert "PASSED" in r.stderr


def test_missing_review_by_is_red(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    e = entry(FIXTURE_ID)
    del e["reviewBy"]
    r = Harness(tmp_path).run(audit_doc(FIXTURE_FINDING), {"exceptions": [e]})
    assert r.returncode == 1
    assert "reviewBy" in r.stderr


def test_malformed_review_by_is_red(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    reg = {"exceptions": [entry(FIXTURE_ID, review="2027-04")]}
    r = h.run(audit_doc(FIXTURE_FINDING), reg)
    assert r.returncode == 1
    assert "malformed" in r.stderr


def test_stale_exemption_is_red(tmp_path: Path) -> None:
    """The CVE-2026-0994 class: advisory no longer fires, carve-out must not linger."""
    h = Harness(tmp_path)
    reg = {"exceptions": [entry(FIXTURE_ID)]}
    r = h.run(audit_doc([]), reg)  # clean audit, dead entry
    assert r.returncode == 1
    assert "stale" in r.stderr


def test_fix_versions_appearing_invalidates_exemption(tmp_path: Path) -> None:
    """Premise is 'awaiting upstream fix'; a released fix ends the exemption."""
    h = Harness(tmp_path)
    reg = {"exceptions": [entry(FIXTURE_ID)]}
    doc = audit_doc([{**FIXTURE_FINDING[0], "fix_versions": ["1.2.4"]}])
    r = h.run(doc, reg)
    assert r.returncode == 1
    assert "fix_versions" in r.stderr


def test_package_attribution_mismatch_is_red(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    reg = {"exceptions": [entry(FIXTURE_ID, pkg="otherlib")]}
    r = h.run(audit_doc(FIXTURE_FINDING), reg)
    assert r.returncode == 1
    assert "attributes" in r.stderr


def test_alias_id_matches(tmp_path: Path) -> None:
    """Registry may cite the CVE while pip-audit reports the GHSA id (or vice versa)."""
    h = Harness(tmp_path)
    finding = [{"id": "GHSA-7gcm-g887-7qv7", "pkg": "protobuf", "version": "4.25.1"}]
    e = entry("CVE-2026-0994", pkg="protobuf")
    e["aliases"] = ["GHSA-7gcm-g887-7qv7"]
    r = h.run(audit_doc(finding), {"exceptions": [e]})
    assert r.returncode == 0, r.stdout + r.stderr


def test_audit_side_alias_matches_fixture_advisory(tmp_path: Path) -> None:
    """R61 Done-when half 1: a fixture advisory dismissed under its ALIAS passes.

    The mirror direction of test_alias_id_matches: pip-audit 2.10.1 emits ONE
    primary id per advisory (its service interface dedups and sorts aliases),
    so a registry keyed by the CVE - exactly the $schema_note's own example,
    CVE-2026-0994, alias of PYSEC-2026-1805 - must still cover an advisory the
    audit reports under the other id with ours in the advisory's aliases
    array. Before R61 this pair was deterministically DOUBLE-red: the entry
    got the misleading "stale - remove me" diagnostic while the same advisory
    also printed UNEXEMPTED. The registry here carries no aliases field on
    purpose: the match must come from the AUDIT side's aliases.
    """
    h = Harness(tmp_path)
    finding = [
        {
            "id": "PYSEC-2026-1805",
            "pkg": "protobuf",
            "version": "4.25.1",
            "aliases": ["CVE-2026-0994"],
        }
    ]
    r = h.run(audit_doc(finding), {"exceptions": [entry("CVE-2026-0994", pkg="protobuf")]})
    assert r.returncode == 0, r.stdout + r.stderr


def test_fixture_advisory_dismissed_under_neither_id_is_red(tmp_path: Path) -> None:
    """R61 Done-when half 2: dismissed under neither id still fails.

    Guards the fix from overshooting: matching on the audit side's aliases is
    widened exact-id logic, not fuzzy package logic. FIXTURE_ID shares nothing
    with the reported advisory's primary id or aliases (its package name even
    matches) - the entry must read stale AND the advisory UNEXEMPTED."""
    h = Harness(tmp_path)
    finding = [
        {
            "id": "GHSA-2222-3333-4444",
            "pkg": FIXTURE_PKG,
            "aliases": ["CVE-2099-000002"],
        }
    ]
    r = h.run(audit_doc(finding), {"exceptions": [entry(FIXTURE_ID)]})
    assert r.returncode == 1
    assert "stale" in r.stderr
    assert "UNEXEMPTED" in r.stderr


def test_warn_on_expiry_soon_is_exit_two(tmp_path: Path) -> None:
    from datetime import date, timedelta

    soon = (date.today() + timedelta(days=7)).isoformat()
    h = Harness(tmp_path)
    reg = {"exceptions": [entry(FIXTURE_ID, review=soon)]}
    r = h.run(audit_doc(FIXTURE_FINDING), reg)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "WARN" in r.stdout


def test_unparsable_audit_json_is_red(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run("not json at all {{{", {"exceptions": []})
    assert r.returncode == 1
    assert "unparsable" in r.stderr


# --- pins on the committed pair (registry + workflow) -------------------------


def test_committed_registry_currently_carries_no_exceptions() -> None:
    """O1.8 measured the last inline ignore (CVE-2026-0994) into staleness:
    protobuf is at 7.36.1 and pip-audit 2.10.1 reports zero findings on the
    committed lock WITHOUT any ignore flag. The registry opens empty; any new
    entry must arrive with reason + owner + reviewBy, and the stale-check
    above guarantees it cannot outlive its advisory."""
    reg = json.loads(COMMITTED_REGISTRY.read_text())
    assert reg["exceptions"] == []


def test_workflow_python_leg_routes_through_the_checker() -> None:
    """The gate step must consult the registry (fail CLOSED) and must never
    regress to a bare --ignore-vuln (fail OPEN). Pinned because the whole
    point of O1.8 is that the inline flag went stale silently - a text pin
    keeps it from creeping back (same doctrine as test_workflow_paths)."""
    wf = AUDIT_WORKFLOW.read_text()
    leg = wf.split("python-audit:", 1)[1].split("npm-audit:", 1)[0]
    # Comments are how the leg explains WHY the flag is gone ("O1.8 removed
    # the inline ignore..."); the pin guards the executed command, so strip
    # comment lines before checking. Same line-wise shape the run: blocks use.
    executable = "\n".join(ln for ln in leg.splitlines() if not ln.strip().startswith("#"))
    assert "check-pip-audit-exemptions.py" in leg
    assert ".pip-audit-exemptions.json" in leg
    assert "--ignore-vuln" not in executable


# --- [r291] gate mode: fail a change only on a finding it adds ----------------
#
# --base-audit-json turns the checker into a DELTA: the same registry/audit
# adjudication runs on both trees and only a finding unexempted at the head
# that is not an unexempted finding at the base reddens. Everything below is
# the package block's seven named cases, on recorded JSON (no pip-audit run).


def run_delta(h: Harness, base_audit: str, head_audit: str, base_reg: dict, head_reg: dict):
    """Feed two recorded audits + two registries through --base-audit-json.

    The harness's single-audit runner takes one registry path; the delta
    needs a second file, so the second registry lands beside it and the
    checker gets both paths explicitly.
    """
    base_doc = h.tmp / "base-pa.json"
    head_doc = h.tmp / "head-pa.json"
    base_doc.write_text(base_audit)
    head_doc.write_text(head_audit)
    base_reg_path = h.tmp / "base-registry.json"
    head_reg_path = h.tmp / "head-registry.json"
    base_reg_path.write_text(json.dumps(base_reg if base_reg is not None else {"exceptions": []}))
    head_reg_path.write_text(json.dumps(head_reg if head_reg is not None else {"exceptions": []}))
    return subprocess.run(  # noqa: PLW1510 - the whole point is checking rc
        [
            sys.executable,
            str(CHECKER),
            "--audit-json",
            str(head_doc),
            "--base-audit-json",
            str(base_doc),
            "--registry",
            str(head_reg_path),
            "--base-registry",
            str(base_reg_path),
            "--warn-days",
            "14",
        ],
        capture_output=True,
        text=True,
    )


def test_gate_finding_shared_by_base_and_head_passes(tmp_path: Path) -> None:
    """Package case 1: the advisory fires on BOTH trees, unexempted on both -
    the change did not add it, the gate is green (full-lockfile mode would
    still be red; that is the other mode's job)."""
    h = Harness(tmp_path)
    r = run_delta(
        h,
        audit_doc(FIXTURE_FINDING),
        audit_doc(FIXTURE_FINDING),
        {"exceptions": []},
        {"exceptions": []},
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_gate_head_adds_vulnerable_package_fails(tmp_path: Path) -> None:
    """Package case 2: the head's audit reports a finding the base's does not -
    the change added it, the gate is red naming the advisory and the package."""
    h = Harness(tmp_path)
    r = run_delta(
        h,
        audit_doc([]),
        audit_doc(FIXTURE_FINDING),
        {"exceptions": []},
        {"exceptions": []},
    )
    assert r.returncode == 1
    assert FIXTURE_ID in r.stderr
    assert "UNEXEMPTED" in r.stderr


def test_gate_removed_exemption_with_surviving_finding_fails(tmp_path: Path) -> None:
    """Package case 3: base carries a valid exemption for a finding that
    survives to the head, and the head's registry drops the entry. Removing
    the exemption counts as ADDING that finding - keyed by id+package, the
    finding is unexempted at head and not unexempted at base."""
    h = Harness(tmp_path)
    r = run_delta(
        h,
        audit_doc(FIXTURE_FINDING),
        audit_doc(FIXTURE_FINDING),
        {"exceptions": [entry(FIXTURE_ID)]},
        {"exceptions": []},
    )
    assert r.returncode == 1
    assert FIXTURE_ID in r.stderr
    assert "UNEXEMPTED" in r.stderr


def test_gate_added_exemption_past_review_by_fails(tmp_path: Path) -> None:
    """Package case 4: the head's registry ADDS an entry whose REVIEW BY has
    passed - an entry the change adds or edits must pass today's registry
    rules, so the delta is red on the registry violation itself (an audit
    error either side fails closed)."""
    h = Harness(tmp_path)
    r = run_delta(
        h,
        audit_doc([]),
        audit_doc(FIXTURE_FINDING),
        {"exceptions": []},
        {"exceptions": [entry(FIXTURE_ID, review="2020-01-01")]},
    )
    assert r.returncode == 1
    assert "PASSED" in r.stderr


def test_gate_base_expired_review_by_untouched_passes_gate_fails_full_lockfile(
    tmp_path: Path,
) -> None:
    """Package case 5: the base's registry has an entry past its REVIEW BY the
    change does not touch. The gate is green (the change did not add the
    violation; the same pair adjudicated in full-lockfile mode - no
    --base-audit-json - must stay red, which is today's behavior pinned by
    test_expired_review_by_is_red)."""
    h = Harness(tmp_path)
    r = run_delta(
        h,
        audit_doc(FIXTURE_FINDING),
        audit_doc(FIXTURE_FINDING),
        {"exceptions": [entry(FIXTURE_ID, review="2020-01-01")]},
        {"exceptions": [entry(FIXTURE_ID, review="2020-01-01")]},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    # The full-lockfile leg of the same pair is NOT green: run today's
    # checker on the head tree alone.
    single = h.run(
        audit_doc(FIXTURE_FINDING), {"exceptions": [entry(FIXTURE_ID, review="2020-01-01")]}
    )
    assert single.returncode == 1
    assert "PASSED" in single.stderr


def test_gate_audit_error_on_either_side_fails(tmp_path: Path) -> None:
    """Package case 6: an unparsable audit - base or head - fails closed. A
    delta that cannot adjudicate a side must never read as clean."""
    h = Harness(tmp_path)
    r = run_delta(
        h,
        "not json at all {{{",
        audit_doc([]),
        {"exceptions": []},
        {"exceptions": []},
    )
    assert r.returncode == 1
    assert "unparsable" in r.stderr
    r = run_delta(
        h,
        audit_doc([]),
        "not json at all {{{",
        {"exceptions": []},
        {"exceptions": []},
    )
    assert r.returncode == 1
    assert "unparsable" in r.stderr


def test_gate_exemption_added_at_head_covers_new_finding(tmp_path: Path) -> None:
    """The flip side of case 3: the head adds BOTH the finding and a valid
    exemption for it (reason + owner + REVIEW BY). The registry entry is
    today's allowlist; the delta is green - the finding the change adds is
    exempted, exactly as full-lockfile mode treats it today."""
    h = Harness(tmp_path)
    r = run_delta(
        h,
        audit_doc([]),
        audit_doc(FIXTURE_FINDING),
        {"exceptions": []},
        {"exceptions": [entry(FIXTURE_ID)]},
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_gate_alias_keyed_finding_shared_across_trees_passes(tmp_path: Path) -> None:
    """The delta key is (id-with-aliases, package): base reports PYSEC-x with
    CVE-y among aliases, head reports the same advisory under its GHSA - one
    finding added before the base, not a new one at the head."""
    h = Harness(tmp_path)
    base = [{"id": "PYSEC-2099-0001", "pkg": FIXTURE_PKG, "aliases": [FIXTURE_ID]}]
    head = [{"id": "GHSA-9999-8888-7777", "pkg": FIXTURE_PKG, "aliases": [FIXTURE_ID]}]
    r = run_delta(h, audit_doc(base), audit_doc(head), {"exceptions": []}, {"exceptions": []})
    assert r.returncode == 0, r.stdout + r.stderr


def run_gate_without_head_registry(h: Harness):
    """Delta invocation with the head's registry path pointing at nothing."""
    base_doc = h.tmp / "base-pa.json"
    head_doc = h.tmp / "head-pa.json"
    base_doc.write_text(audit_doc([]))
    head_doc.write_text(audit_doc([]))
    base_reg_path = h.tmp / "base-registry.json"
    base_reg_path.write_text(json.dumps({"exceptions": []}))
    return subprocess.run(  # noqa: PLW1510 - the whole point is checking rc
        [
            sys.executable,
            str(CHECKER),
            "--audit-json",
            str(head_doc),
            "--base-audit-json",
            str(base_doc),
            "--registry",
            str(h.tmp / "no-such-registry.json"),
            "--base-registry",
            str(base_reg_path),
            "--warn-days",
            "14",
        ],
        capture_output=True,
        text=True,
    )


def test_gate_missing_head_registry_is_red(tmp_path: Path) -> None:
    """A head tree whose registry file vanished fails closed, delta or not."""
    r = run_gate_without_head_registry(Harness(tmp_path))
    assert r.returncode == 1
    assert "MISSING" in r.stderr


def test_gate_resurrected_advisory_behind_dead_entry_fails(tmp_path: Path) -> None:
    """r291 security pass: the base's audit does NOT report the advisory, the
    head's does, and both registries carry an entry for it whose REVIEW BY
    has passed. The PR touches no registry file - the finding resurrects the
    dead entry by making its advisory live again. Strict coverage: a
    violating entry does not cover the head's finding, so the delta is red,
    not '0 finding(s) shared ... none added'."""
    h = Harness(tmp_path)
    dead = {"exceptions": [entry(FIXTURE_ID, review="2020-01-01")]}
    r = run_delta(h, audit_doc([]), audit_doc(FIXTURE_FINDING), dead, dead)
    assert r.returncode == 1
    assert FIXTURE_ID in r.stderr
    assert "UNEXEMPTED" in r.stderr


def test_gate_sibling_advisory_sharing_an_id_is_red(tmp_path: Path) -> None:
    """r291 security pass, key collapse: one CVE id carrying two advisories
    (each its own GHSA with the shared CVE in aliases). The head reports
    BOTH, the base one - min() gives both the same canonical key, so a bare
    set-difference read them as 'shared'. The key counts advisories per
    canonical key: head count 2 > base count 1 is an addition."""
    base = [{"id": "CVE-2026-0001", "pkg": FIXTURE_PKG}]
    head = [
        {"id": "CVE-2026-0001", "pkg": FIXTURE_PKG},
        {"id": "GHSA-zzzz-zzzz-zzzz", "pkg": FIXTURE_PKG, "aliases": ["CVE-2026-0001"]},
    ]
    h = Harness(tmp_path)
    r = run_delta(h, audit_doc(base), audit_doc(head), {"exceptions": []}, {"exceptions": []})
    assert r.returncode == 1
    assert "UNEXEMPTED" in r.stderr


def test_gate_shared_warn_keeps_delta_green_with_warning_note(tmp_path: Path) -> None:
    """r291 security pass, verdict hygiene: a pre-existing entry expiring
    within warn-days on BOTH trees (finding shared too) must not fail the
    delta - and the OK line carries the warning count, so the log never
    reads 'delta OK' beside a nonzero exit code."""
    soon = (date.today() + timedelta(days=5)).isoformat()
    h = Harness(tmp_path)
    r = run_delta(
        h,
        audit_doc(FIXTURE_FINDING),
        audit_doc(FIXTURE_FINDING),
        {"exceptions": [entry(FIXTURE_ID, review=soon)]},
        {"exceptions": [entry(FIXTURE_ID, review=soon)]},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "shared expiry warning(s)" in r.stdout
