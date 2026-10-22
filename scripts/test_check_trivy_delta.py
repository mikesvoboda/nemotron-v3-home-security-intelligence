#!/usr/bin/env python3
"""Tests for scripts/check-trivy-delta.py (the [r294] Trivy gate).

The gate extends ruling 291's design to Trivy's two vulnerability scans, so
the failure modes below ARE the gate's teeth — the same doctrine as
scripts/test_check_pip_audit_exemptions.py and its npm twin, run explicitly
outside testpaths:

    uv run python -m pytest scripts/test_check_trivy_delta.py -q

Ruling 294's named cases, on recorded Trivy JSON (no trivy run):
  - a finding in both base and head passes the gate (one case built from
    run 39528289094's `certifi` finding);
  - a head-only finding fails;
  - removing a .trivyignore entry whose finding remains fails;
  - an added entry with a past or missing review date fails;
  - a scan error on either side fails;
  - the full mode gives today's results.
Plus the workflow pins: trivy.yml's gate legs route through this checker,
and ci.yml's security-trivy call selects the gate mode (UR-122).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
CHECKER = REPO / "check-trivy-delta.py"
COMMITTED_IGNORE = REPO.parent / ".trivyignore"
TRIVY_WORKFLOW = REPO.parent / ".github" / "workflows" / "trivy.yml"
CI_WORKFLOW = REPO.parent / ".github" / "workflows" / "ci.yml"

FUTURE = "2099-01-01"
PAST = "2020-01-01"

# Run 39528289094's real finding (the certifi red-`main` raise 6306177116),
# in the exact shape trivy --format json emits for it.
CERTIFI_ID = "GHSA-6q48-6c7w-9gw2"
CERTIFI_PKG = "certifi"
FIXTURE_ID = "CVE-2099-000001"
FIXTURE_PKG = "fixturelib"


def trivy_doc(vulns: list[dict], target: str = "requirements.txt") -> str:
    """vulns: [{id, pkg, severity, status}] -> trivy --format json shape."""
    return json.dumps(
        {
            "SchemaVersion": 2,
            "Results": [
                {
                    "Target": target,
                    "Class": "lang-pkgs",
                    "Type": "pip",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": v["id"],
                            "PkgName": v["pkg"],
                            "InstalledVersion": "1.0.0",
                            "FixedVersion": "2.0.0",
                            "Status": v.get("status", "fixed"),
                            "Severity": v.get("severity", "CRITICAL"),
                        }
                        for v in vulns
                    ],
                }
            ],
        }
    )


def entry_block(vid: str, review: str | None = FUTURE) -> str:
    """A .trivyignore entry: its REVIEW BY comment + the bare id line."""
    if review is None:
        return f"# {vid} - some accepted risk\n{vid}\n"
    return f"# {vid} - some accepted risk (REVIEW BY: {review})\n{vid}\n"


class Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path

    def run(
        self,
        report: str,
        ignore: str,
        base_report: str | None = None,
        base_ignore: str | None = None,
    ):
        head_doc = self.tmp / "head.json"
        head_doc.write_text(report)
        head_ig = self.tmp / "head.trivyignore"
        head_ig.write_text(ignore)
        argv = [
            sys.executable,
            str(CHECKER),
            "--report",
            str(head_doc),
            "--ignore",
            str(head_ig),
            "--warn-days",
            "14",
        ]
        if base_report is not None:
            assert base_ignore is not None
            base_doc = self.tmp / "base.json"
            base_doc.write_text(base_report)
            base_ig = self.tmp / "base.trivyignore"
            base_ig.write_text(base_ignore)
            argv += ["--base-report", str(base_doc), "--base-ignore", str(base_ig)]
        return subprocess.run(  # noqa: PLW1510 - the whole point is checking rc
            argv,
            capture_output=True,
            text=True,
        )


CERTIFI_FINDING = [{"id": CERTIFI_ID, "pkg": CERTIFI_PKG}]
CERTIFI_IGNORE = entry_block(CERTIFI_ID)

# --- ruling 294's named cases ------------------------------------------------


def test_finding_in_both_base_and_head_passes_the_gate(tmp_path: Path) -> None:
    """The certifi case: the advisory's data changed, not the code. The same
    finding on both sides (built from run 39528289094's) is the base's
    pre-existing state and the gate passes."""
    h = Harness(tmp_path)
    r = h.run(
        trivy_doc(CERTIFI_FINDING),
        CERTIFI_IGNORE,
        base_report=trivy_doc(CERTIFI_FINDING),
        base_ignore=CERTIFI_IGNORE,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "none added by the change" in r.stdout


def test_head_only_finding_fails_the_gate(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(
        trivy_doc(CERTIFI_FINDING + [{"id": FIXTURE_ID, "pkg": FIXTURE_PKG}]),
        CERTIFI_IGNORE,
        base_report=trivy_doc(CERTIFI_FINDING),
        base_ignore=CERTIFI_IGNORE,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert FIXTURE_ID in r.stderr
    assert "UNEXEMPTED" in r.stderr
    # The shared finding is NOT listed as added.
    assert CERTIFI_ID not in r.stderr


def test_head_only_finding_on_the_same_advisory_but_new_package_fails(
    tmp_path: Path,
) -> None:
    """Keyed by (vulnerability id, package): an advisory already exempted on
    one package does not cover a NEW package the change adds."""
    h = Harness(tmp_path)
    r = h.run(
        trivy_doc(CERTIFI_FINDING + [{"id": CERTIFI_ID, "pkg": "certifi-copy"}]),
        CERTIFI_IGNORE,
        base_report=trivy_doc(CERTIFI_FINDING),
        base_ignore=CERTIFI_IGNORE,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "certifi-copy" in r.stderr


def test_removing_an_entry_whose_finding_remains_fails(tmp_path: Path) -> None:
    """The base's scan filtered the finding through its entry; the head's
    scan no longer has the entry, so the finding appears at the head only -
    removal counts as adding the finding. (In the recorded-JSON model the
    head report must therefore CARRY the finding: the workflow's gate legs
    apply each side's OWN ignore snapshot, exactly so a removal is visible;
    the checker treats a present finding as unexempted.)"""
    h = Harness(tmp_path)
    # The head scan ran WITHOUT the ignore file (the gate leg's shape), so
    # its report carries the raw finding; the base scan ran WITH its entry.
    r = h.run(
        trivy_doc(CERTIFI_FINDING),
        "",  # entry removed at the head
        base_report=trivy_doc([]),
        base_ignore=CERTIFI_IGNORE,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert CERTIFI_ID in r.stderr


def test_added_entry_with_a_past_review_date_fails(tmp_path: Path) -> None:
    """An entry this change adds must pass today's rules (the expiry
    checker's). A past REVIEW BY on an added entry reds even though trivy's
    own filter suppressed the finding under it."""
    h = Harness(tmp_path)
    r = h.run(
        trivy_doc(CERTIFI_FINDING),
        CERTIFI_IGNORE + entry_block(FIXTURE_ID, review=PAST),
        base_report=trivy_doc(CERTIFI_FINDING),
        base_ignore=CERTIFI_IGNORE,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert FIXTURE_ID in r.stderr
    assert "has PASSED" in r.stderr


def test_added_entry_with_a_missing_review_date_fails(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(
        trivy_doc(CERTIFI_FINDING),
        CERTIFI_IGNORE + entry_block(FIXTURE_ID, review=None),
        base_report=trivy_doc(CERTIFI_FINDING),
        base_ignore=CERTIFI_IGNORE,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "missing reviewBy" in r.stderr


def test_preexisting_past_entry_on_both_sides_passes_the_gate(tmp_path: Path) -> None:
    """Package case 5 parity: the base's pre-existing expired entry stands on
    both sides, so the delta sees no addition. (Full mode still reds it on
    its own trigger - test_full_mode_reds_on_expired_entry.)"""
    h = Harness(tmp_path)
    expired = entry_block(CERTIFI_ID, review=PAST)
    r = h.run(
        trivy_doc(CERTIFI_FINDING),
        expired,
        base_report=trivy_doc(CERTIFI_FINDING),
        base_ignore=expired,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_scan_error_at_the_base_fails_closed(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(
        trivy_doc(CERTIFI_FINDING),
        CERTIFI_IGNORE,
        base_report="not json at all {",
        base_ignore=CERTIFI_IGNORE,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "UNADJUDICABLE" in r.stderr


def test_scan_error_at_the_head_fails_closed(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(
        "not json at all {",
        CERTIFI_IGNORE,
        base_report=trivy_doc(CERTIFI_FINDING),
        base_ignore=CERTIFI_IGNORE,
    )
    assert r.returncode == 1, r.stdout + r.stderr


def test_missing_base_ignore_file_fails_closed(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    argv = [
        sys.executable,
        str(CHECKER),
        "--report",
        str(h.tmp / "head.json"),
        "--ignore",
        str(h.tmp / "head.trivyignore"),
        "--base-report",
        str(h.tmp / "base.json"),
        "--base-ignore",
        str(h.tmp / "absent.trivyignore"),
    ]
    (h.tmp / "head.json").write_text(trivy_doc(CERTIFI_FINDING))
    (h.tmp / "head.trivyignore").write_text(CERTIFI_IGNORE)
    (h.tmp / "base.json").write_text(trivy_doc(CERTIFI_FINDING))
    r = subprocess.run(argv, capture_output=True, text=True)
    assert r.returncode == 1, r.stdout + r.stderr


def test_base_report_without_base_ignore_is_a_usage_error(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    argv = [
        sys.executable,
        str(CHECKER),
        "--report",
        str(h.tmp / "head.json"),
        "--ignore",
        str(h.tmp / "head.trivyignore"),
        "--base-report",
        str(h.tmp / "base.json"),
    ]
    (h.tmp / "head.json").write_text(trivy_doc([]))
    (h.tmp / "head.trivyignore").write_text("")
    (h.tmp / "base.json").write_text(trivy_doc([]))
    r = subprocess.run(argv, capture_output=True, text=True)
    assert r.returncode == 1, r.stdout + r.stderr


# --- the full mode gives today's results -------------------------------------


def test_full_mode_clean_report_is_green(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(trivy_doc([]), CERTIFI_IGNORE)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "trivy scan OK" in r.stdout


def test_full_mode_reds_on_an_unexempted_finding(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(trivy_doc(CERTIFI_FINDING), "")
    assert r.returncode == 1, r.stdout + r.stderr
    assert CERTIFI_ID in r.stderr


def test_full_mode_reds_on_finding_despite_a_listing(tmp_path: Path) -> None:
    """A finding present in the report is unexempted even when an entry names
    it: the allowlist's application belongs to trivy (the gate legs apply
    each side's OWN ignore snapshot so removals are visible), so an
    ignore-file match never suppresses a finding the checker can see. The
    committed file's own entries carry their findings only in the raw scans'
    output, which this checker never consumes."""
    h = Harness(tmp_path)
    r = h.run(trivy_doc(CERTIFI_FINDING), CERTIFI_IGNORE)
    assert r.returncode == 1, r.stdout + r.stderr
    assert CERTIFI_ID in r.stderr


def test_full_mode_reds_on_expired_entry(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(trivy_doc([]), entry_block(CERTIFI_ID, review=PAST))
    assert r.returncode == 1, r.stdout + r.stderr


def test_full_mode_reds_on_missing_review_date(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(trivy_doc([]), entry_block(CERTIFI_ID, review=None))
    assert r.returncode == 1, r.stdout + r.stderr


def test_full_mode_warns_on_near_expiry(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(trivy_doc([]), "")
    assert r.returncode == 0, r.stdout + r.stderr


def test_full_mode_silence_when_gate_mode(tmp_path: Path) -> None:
    """In gate mode the head side stays quiet (its shared-violation chatter
    is not allowed to fail the delta) - the OK line is the delta's, not the
    head side's."""
    h = Harness(tmp_path)
    r = h.run(
        trivy_doc(CERTIFI_FINDING),
        CERTIFI_IGNORE,
        base_report=trivy_doc(CERTIFI_FINDING),
        base_ignore=CERTIFI_IGNORE,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "trivy scan OK" not in r.stdout
    assert "trivy delta OK" in r.stdout


# --- pins on the committed pair (ignore file + workflow) ---------------------


def test_committed_ignore_file_entries_all_carry_review_dates(tmp_path: Path) -> None:
    """The committed allowlist must pass today's own rules - the gate reads
    it on every PR. Adjudicated through the checker itself: an empty report
    isolates the ignore file, and a green full mode certifies it."""
    h = Harness(tmp_path)
    r = h.run(trivy_doc([]), COMMITTED_IGNORE.read_text())
    assert r.returncode == 0, r.stdout + r.stderr
    assert "active ignore entries" in r.stdout


def test_workflow_gate_legs_route_through_the_checker() -> None:
    """Both gate legs in trivy.yml must consult the checker (fail closed),
    and ci.yml's call must select the gate mode (UR-122)."""
    wf = TRIVY_WORKFLOW.read_text()
    assert "check-trivy-delta.py" in wf
    assert "trivy-mode: gate" in wf or "trivy-mode: gate" in CI_WORKFLOW.read_text()
    ci = CI_WORKFLOW.read_text()
    assert "trivy-mode: gate" in ci

# --- the review round (UR-89 + UR-95 findings, red-first) ---------------------


def secret_doc(rule: str = "aws-access-key-id", target: str = "backend/config.py") -> str:
    """A CRITICAL secret finding in trivy's --format json shape (the gate
    legs scan `vuln,secret`, so Secrets rows land in the same reports)."""
    return json.dumps(
        {
            "SchemaVersion": 2,
            "Results": [
                {
                    "Target": target,
                    "Class": "secret",
                    "Secrets": [
                        {
                            "RuleID": rule,
                            "Category": "AWS",
                            "Severity": "CRITICAL",
                            "Match": "AKIA…:21",
                            "StartLine": 3,
                        }
                    ],
                }
            ],
        }
    )


def test_a_critical_secret_the_change_adds_fails_the_gate(tmp_path: Path) -> None:
    """UR-89 blocking-3: the gate legs scan `vuln,secret`, so the checker
    adjudicates secrets too - a CRITICAL secret unexempted at the head only
    reds the delta (keyed RuleID + match location, secrets carry no
    package)."""
    h = Harness(tmp_path)
    r = h.run(
        secret_doc(),
        CERTIFI_IGNORE,
        base_report=trivy_doc(CERTIFI_FINDING),
        base_ignore=CERTIFI_IGNORE,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "aws-access-key-id" in r.stderr
    assert "UNEXEMPTED" in r.stderr


def test_a_secret_on_both_sides_passes_the_gate(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(
        secret_doc(),
        CERTIFI_IGNORE,
        base_report=secret_doc(),
        base_ignore=CERTIFI_IGNORE,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "none added by the change" in r.stdout


def test_full_mode_reds_on_an_unexempted_secret(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(secret_doc(), "")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "aws-access-key-id" in r.stderr


def test_added_entry_with_an_exp_field_fails(tmp_path: Path) -> None:
    """UR-95 HIGH: trivy's own ignorefile parser honors a first-field id with
    an `exp:` suffix field as a suppression with a far-future expiry. The
    earlier bare-id regex skipped such lines entirely, leaving the
    suppression ungoverned. Every non-comment line's first field is now an
    entry id and must pass today's rules."""
    h = Harness(tmp_path)
    r = h.run(
        trivy_doc(CERTIFI_FINDING),
        CERTIFI_IGNORE + f"{FIXTURE_ID} exp:{FUTURE}\n",
        base_report=trivy_doc(CERTIFI_FINDING),
        base_ignore=CERTIFI_IGNORE,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert FIXTURE_ID in r.stderr
    assert "missing reviewBy" in r.stderr


def test_added_indented_entry_fails(tmp_path: Path) -> None:
    """Leading whitespace does not hide an entry: trivy trims, so the gate
    adjudicates the trimmed line."""
    h = Harness(tmp_path)
    r = h.run(
        trivy_doc(CERTIFI_FINDING),
        CERTIFI_IGNORE + f"  {FIXTURE_ID}\n",
        base_report=trivy_doc(CERTIFI_FINDING),
        base_ignore=CERTIFI_IGNORE,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "missing reviewBy" in r.stderr


def test_added_entry_with_a_trailing_comment_fails(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    r = h.run(
        trivy_doc(CERTIFI_FINDING),
        CERTIFI_IGNORE + f"{FIXTURE_ID} # accepted by hand\n",
        base_report=trivy_doc(CERTIFI_FINDING),
        base_ignore=CERTIFI_IGNORE,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "missing reviewBy" in r.stderr


def test_added_unrecognized_id_shape_fails(tmp_path: Path) -> None:
    """An id this checker does not recognize (a future trivy id family) is
    still a suppressor trivy would honor - an unknown-shape suppressor reds
    rather than slips."""
    h = Harness(tmp_path)
    r = h.run(
        trivy_doc(CERTIFI_FINDING),
        CERTIFI_IGNORE + "NOTAREALID-9999\n",
        base_report=trivy_doc(CERTIFI_FINDING),
        base_ignore=CERTIFI_IGNORE,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "unrecognized entry id shape" in r.stderr


def test_avd_misconfig_entries_parse_and_preexisting_shape_passes(tmp_path: Path) -> None:
    """The committed allowlist carries one AVD-DS misconfig id; the parser
    must count it an entry (and its REVIEW BY a date) so an edit to it
    adjudicates entry-level, and a pre-existing AVD entry on both sides
    stays green."""
    h = Harness(tmp_path)
    block = "# AVD-DS-0002 - accepted misconfig (REVIEW BY: 2099-01-01)\nAVD-DS-0002\n"
    r = h.run(
        trivy_doc(CERTIFI_FINDING),
        CERTIFI_IGNORE + block,
        base_report=trivy_doc(CERTIFI_FINDING),
        base_ignore=CERTIFI_IGNORE,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "1 finding(s) shared" in r.stdout


def test_workflow_pins_the_review_round_fixes() -> None:
    """UR-89 + UR-95 review-round pins: the skip polarity reds no blocking
    scan in gate mode; the push trigger carries the full scans to main;
    both adjudicators fail closed on a committed trivy config file; the
    fs skip pathspec covers the gateway's live manifest."""
    wf = TRIVY_WORKFLOW.read_text()
    # Blocking-scan step polarity: in gate+skip the blocking scan must NOT run.
    assert "steps.mode.outputs.mode != 'gate' || steps.mode.outputs.skip_scan != 'true'" in wf
    # The full scans ride a push trigger (box 2: "on every push to main").
    on_block = wf.split("workflow_call:")[0]
    assert "push:" in on_block and "branches: [main]" in on_block
    # Both adjudicators fail closed on a trivy config file the change commits.
    assert wf.count("if [ -f trivy.yaml ] || [ -f .trivyignore.yaml ]; then") == 2
    # The gateway's live manifest is in the fs skip pathspec (its deps move
    # must scan).
    assert "ai/gateway/requirements.txt" in wf
    # The checker counts secret findings (the gate legs scan vuln,secret).
    checker = CHECKER.read_text()
    assert 'r.get("Secrets")' in checker
