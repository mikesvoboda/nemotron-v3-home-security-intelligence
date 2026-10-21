#!/usr/bin/env python3
"""[r294] Trivy vulnerability-scan delta checker (the gate's adjudicator).

Ruling 294 extends ruling 291's design to Trivy's two vulnerability scans
(`Filesystem Vulnerability Scan` and `Scan Backend Image` in
.github/workflows/trivy.yml): in the gate they fail a change only on a
finding it adds. This checker adjudicates that delta on the two sides'
RECORDED Trivy JSON reports - the workflow scans head and base in one job,
against the same Trivy database, each side's scan applying THAT side's
.trivyignore, and this checker compares what survives.

The .trivyignore file stays the one allowlist, with the same consequence
chain ruling 291 gave the audit registries:

  - A finding suppressed by an entry does not reach the report, so it is
    "exempted" by construction. Removing an entry whose finding remains
    makes the finding appear at the head and not at the base - the delta
    sees the addition (the "removal counts as adding the finding" rule,
    enforced by trivy's own ignorefile application, not re-parsed here).
  - An entry a change ADDS or EDITS must pass today's rules (a REVIEW BY
    present, well-formed, and not past - scripts/check-trivyignore-expiry.sh's
    rules). The checker parses both sides' ignore files for the entry keys
    and text-diffs their violation strings, exactly the pip checker's
    violated_entries doctrine: a violation on both sides is the base's
    pre-existing state and stays green in gate mode; a violation only at the
    head reds.
  - A scan error on either side fails closed: an unparsable report, a report
    from a failed scan, or a missing/unreadable ignore file leaves the
    delta's "was it already there?" question unanswerable, and an
    unanswerable delta never reads as clean.

Exit codes: 0 clean (gate: nothing added), 1 violations (or unadjudicable),
2 advisory-only (expiry warnings, full mode).

CLI:
  Full mode (default): --report HEAD.json --ignore .trivyignore
      Adjudicates the one report with today's rules: reds on any
      CRITICAL/HIGH finding present after trivy's own ignorefile filter,
      and on ignore-file violations. This is the recorded-JSON stand-in for
      the raw scans (the workflow's full scans keep running trivy itself
      with exit-code: 1, unchanged).
  Gate mode: also --base-report BASE.json --base-ignore BASE.trivyignore
      Fails only on a finding the change ADDS (keyed vulnerability id and
      package) or an ignore-file violation the change adds or edits.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

# Same threshold the two scans gate on today (severity: 'CRITICAL,HIGH').
SEVERITIES = ("CRITICAL", "HIGH")

# An entry line: a bare vulnerability id (CVE-… / GHSA-…) at column 0, as
# .trivyignore carries them. The preceding comment block's REVIEW BY date
# (scripts/check-trivyignore-expiry.sh's own regex) supplies the review date.
ENTRY_RE = re.compile(r"^(CVE-[0-9]+-[0-9]+|GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4})\s*$")
REVIEW_RE = re.compile(
    r"^#\s*(CVE-[0-9]+-[0-9]+|GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4})\s*-.*"
    r"\(REVIEW\ BY:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\)"
)


@dataclass
class IgnoreFile:
    """One .trivyignore parsed into entries + today's-rule violations.

    `violations` are the delta keys (one text string per entry), mirroring
    the pip checker's violated_entries: the entry id is every message's
    prefix, so set-difference on the strings is entry-keyed AND carries the
    wording. A file that cannot be read at all is `unadjudicable` - the
    allowlist question cannot be answered for that side.
    """

    entries: list[tuple[str, str | None]] = field(default_factory=list)
    violations: set[str] = field(default_factory=set)
    unadjudicable: bool = False
    warns: list[str] = field(default_factory=list)


def parse_ignore(path: Path, warn_days: int) -> IgnoreFile:
    """Parse one .trivyignore: entries + their rule state.

    The comment line `# <ID> - description (REVIEW BY: YYYY-MM-DD)`
    governing an entry line (comments between it and the entry may exist -
    the committed file stacks correction notes there, and the expiry checker
    keys the last matching REVIEW BY comment before the entry) supplies the
    date. An entry with no REVIEW BY comment, a malformed one, or a past one
    is a violation with today's wording.
    """
    out = IgnoreFile()
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return IgnoreFile(unadjudicable=True)
    today = date.today()
    # Last REVIEW BY comment seen, keyed by the id it names: the expiry
    # checker's "current_cve/current_review_date" pair, generalized so a
    # comment naming id X followed by entry X adjudicates even across
    # interleaved comments for other ids.
    pending: dict[str, str] = {}
    for line in lines:
        m = REVIEW_RE.match(line)
        if m:
            pending[m.group(1)] = m.group(2)
            continue
        m = ENTRY_RE.match(line)
        if not m:
            continue
        vid = m.group(1)
        rb = pending.get(vid)
        out.entries.append((vid, rb))
        if rb is None:
            out.violations.add(f"{vid}: missing reviewBy (REVIEW BY) date")
        else:
            try:
                review = datetime.strptime(rb, "%Y-%m-%d").date()
            except ValueError:
                out.violations.add(f"{vid}: malformed reviewBy {rb!r} (want YYYY-MM-DD)")
            else:
                if review < today:
                    out.violations.add(
                        f"{vid}: REVIEW BY {rb} has PASSED - re-review, fix, or remove"
                    )
                elif review <= today + timedelta(days=warn_days):
                    out.warns.append(f"{vid}: REVIEW BY {rb} expires within {warn_days}d")
    return out


def findings(report: Path) -> tuple[set[tuple[str, str]], bool]:
    """The report's CRITICAL/HIGH findings, keyed (vulnerability id, package).

    The JSON is what trivy wrote AFTER applying that side's ignore file, so
    a finding present here is unexempted on this side by construction. A
    report that does not parse (a trivy crash yields no report at all; the
    gate steps exit 0 and let this checker adjudicate) is unadjudicable.
    """
    try:
        doc = json.loads(report.read_text())
    except (OSError, json.JSONDecodeError):
        return set(), True
    if not isinstance(doc, dict) or not isinstance(doc.get("Results"), list):
        return set(), True
    out: set[tuple[str, str]] = set()
    for r in doc["Results"]:
        if not isinstance(r, dict):
            return set(), True
        for v in r.get("Vulnerabilities") or []:
            if not isinstance(v, dict):
                return set(), True
            vid, pkg, sev = v.get("VulnerabilityID"), v.get("PkgName"), v.get("Severity")
            if not vid or not pkg or not sev:
                return set(), True
            if sev in SEVERITIES:
                out.add((vid, pkg))
    return out, False


@dataclass
class Verdict:
    """One side's adjudication, reusable by both modes."""

    unexempted: set[tuple[str, str]]
    violations: set[str]
    unadjudicable: bool
    rc: int
    warns: int


def adjudicate(report: Path, ignore: Path, warn_days: int, full_report: bool) -> Verdict:
    """Adjudicate ONE side: its recorded report + its ignore snapshot."""
    ig = parse_ignore(ignore, warn_days)
    if ig.unadjudicable:
        print(
            f"MISSING/unreadable {ignore}: the gate fails closed without the "
            "allowlist snapshot.",
            file=sys.stderr,
        )
        return Verdict(set(), set(), True, 1, 0)
    found, unadjudicable = findings(report)
    if unadjudicable:
        print(
            f"UNADJUDICABLE report {report}: missing, unparsable, or not a Trivy "
            "vulnerability report - the gate fails closed.",
            file=sys.stderr,
        )
        return Verdict(set(), set(), True, 1, 0)

    errors: list[str] = []
    errors.extend(sorted(ig.violations))
    for vid, pkg in sorted(found):
        errors.append(f"{vid} on {pkg} is UNEXEMPTED ({', '.join(SEVERITIES)})")
    if full_report:
        for w in ig.warns:
            print(f"WARN: {w}")
        if errors:
            print(f"{len(errors)} Trivy violation(s):", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
        else:
            print(
                f"trivy scan OK: {len(found)} unexempted {', '.join(SEVERITIES)} "
                f"finding(s), {len(ig.entries)} active ignore entries, "
                f"no expiry within {warn_days}d"
            )
    rc = 1 if errors else (2 if ig.warns else 0)
    return Verdict(found, ig.violations, False, rc, len(ig.warns))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True, help="Trivy --format json report (head tree)")
    ap.add_argument("--ignore", required=True, help=".trivyignore snapshot of the head tree")
    ap.add_argument("--warn-days", type=int, default=14)
    ap.add_argument(
        "--base-report",
        default=None,
        help="[r294] gate mode: Trivy report of the PR's base tree. Given, the "
        "checker fails only on a finding the change ADDS - unexempted at the "
        "head and not unexempted at the base, keyed by vulnerability id and "
        "package.",
    )
    ap.add_argument("--base-ignore", default=None, help=".trivyignore snapshot of the base tree")
    args = ap.parse_args()
    if args.base_report and not args.base_ignore:
        print(
            "--base-report without --base-ignore: the delta adjudicates BOTH "
            "sides, so the base needs its own allowlist snapshot",
            file=sys.stderr,
        )
        return 1

    # Full mode is the ONLY side, so it always reports; in gate mode the
    # head side stays quiet (its shared-violation chatter is not allowed to
    # fail the delta) and the base side reports only when it fails closed.
    if not args.base_report:
        head = adjudicate(Path(args.report), Path(args.ignore), args.warn_days, full_report=True)
        return head.rc

    # Gate mode. The base side's violations are NOT the change's fault: a
    # pre-existing expired REVIEW BY or a pre-existing unexempted finding
    # prints and passes. The one base-side condition that still fails closed
    # is UNADJUDICABLE - an unparsable base report or a missing base ignore
    # file makes the delta's "was it already there?" question unanswerable.
    head = adjudicate(Path(args.report), Path(args.ignore), args.warn_days, full_report=False)
    base = adjudicate(
        Path(args.base_report), Path(args.base_ignore), args.warn_days, full_report=False
    )
    if base.unadjudicable:
        print(
            "BASE SIDE of the delta is UNADJUDICABLE (report unparsable or "
            "ignore file missing) - the gate fails closed:",
            file=sys.stderr,
        )
        return 1
    if head.unadjudicable:
        # The head's own diagnostics already printed inside its adjudicate().
        return 1

    # Entry-level rule violations (past/missing/malformed REVIEW BY), keyed
    # by ENTRY: a violation reddens the delta only when the change ADDED or
    # EDITED that entry - the violation exists at the head and not at the
    # base. The same violation standing on both sides is the base's
    # pre-existing state and stays green in gate mode (full mode still reds
    # it on its own trigger).
    entry_added = head.violations - base.violations
    if entry_added:
        print(
            f"{len(entry_added)} .trivyignore violation(s) on entries this "
            "change adds or edits (violation not present at the base):",
            file=sys.stderr,
        )
        for v in sorted(entry_added):
            print(f"  - {v}", file=sys.stderr)
        return 1

    # Findings keyed (vulnerability id, package): red only on a finding
    # unexempted at the head that is not an unexempted finding at the base.
    # Removing an entry whose finding remains shows up here by itself: the
    # head's scan no longer filters it, the base's did, so the pair appears
    # in the head set only.
    added = head.unexempted - base.unexempted
    if added:
        print(
            f"{len(added)} Trivy finding(s) this change ADDS "
            f"(unexempted at the head, not unexempted at the base):",
            file=sys.stderr,
        )
        for vid, pkg in sorted(added):
            print(f"  - {vid} on {pkg} is UNEXEMPTED", file=sys.stderr)
        return 1
    # Verdict hygiene, mirroring the pip checker: shared pre-existing
    # warnings do not fail the delta, but they print in the OK line so the
    # log never says "OK" beside a red exit code.
    warn_note = f", {head.warns} shared expiry warning(s)" if head.warns else ""
    print(
        f"trivy delta OK: {len(head.unexempted)} finding(s) shared with the "
        f"base, none added by the change{warn_note}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
