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
