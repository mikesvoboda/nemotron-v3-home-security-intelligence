#!/usr/bin/env python3
"""pip-audit exemption registry checker (mirror of check-npm-audit-exemptions.py).

The Python leg of .github/workflows/dependency-audit.yml used to run a bare
`pip-audit … --ignore-vuln CVE-…`. That shape fails OPEN in both directions:
the flag silences an advisory with no reason, no owner and no expiry, and a
STALE ignore (the advisory no longer fires at all) suppresses nothing while
still reading as "there is a carve-out here" - the CVE-2026-0994 entry added
in 91a841507 had a "Review date: 2026-01-23" comment that expired eight-plus
months before O1.8 measured, on 2026-10-09, that it no longer reproduces
(protobuf is at 7.36.1; pip-audit 2.10.1 reports zero findings WITHOUT the
flag). This checker replaces it and fails CLOSED, red when ANY of:

  1. a REVIEW BY (reviewBy) date has passed (or expires within --warn-days),
  2. a missing/malformed reviewBy on any entry,
  3. a pip-audit finding (vulnerability id) is NOT covered by an active
     exemption - the registry IS the allowlist, so without this file any
     finding at all is red,
  4. an exemption matches NOTHING in the current audit (stale entry - the
     failure mode the inline --ignore-vuln could never report; remove it),
  5. an exempted advisory that pip-audit reports WITH fix_versions (the
     sanctioned premise is "awaiting an upstream fix"; a released fix ends
     the exemption - take the bump),
  6. the advisory id a registry entry cites matches NEITHER the id pip-audit
     reports nor that advisory's aliases, for the package it names (id drift -
     e.g. a PYSEC/PYSEC-alias change). Either direction counts: registry-cited
     alias matching the audit's primary id, or audit-side alias matching the
     registry's id (R61 - pip-audit emits ONE primary id per advisory, so a
     CVE-keyed dismissal of a PYSEC-reported advisory is the common case).

Run it on an exported requirements file (the same export the audit job uses):

    uv export --no-hashes > requirements-audit.txt
    pip-audit -r requirements-audit.txt --desc -f json > /tmp/pa.json
    python3 scripts/check-pip-audit-exemptions.py --audit-json /tmp/pa.json \
        --registry .pip-audit-exemptions.json --warn-days 14

Exit codes: 0 clean, 1 violations, 2 --warn-days advisory only.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

DEFAULT_REGISTRY = ".pip-audit-exemptions.json"


def load_audit(path: Path) -> dict:
    """Read a pip-audit `-f json` report; '-' means stdin."""
    raw = sys.stdin.read() if str(path) == "-" else path.read_text()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(
            "pip-audit JSON report is unparsable - the gate fails closed "
            "(an unparsable audit must never read as a clean audit)",
            file=sys.stderr,
        )
        sys.exit(1)


def advisories(audit: dict) -> dict[str, dict]:
    """vuln id -> packages / versions / fix_versions across all dependencies.

    pip-audit's report is per-dependency: {"dependencies": [{"name","version",
    "vulns":[{"id","fix_versions",...}]}]}. One advisory can hit several
    dependencies (or the same dependency at several versions), so merge on the
    id and keep every (package, version) it was reported against.
    """
    out: dict[str, dict] = {}
    for dep in audit.get("dependencies") or []:
        name = dep.get("name", "?")
        version = dep.get("version", "?")
        for vuln in dep.get("vulns") or []:
            vid = vuln.get("id")
            if not vid:
                continue
            a = out.setdefault(
                vid,
                {"packages": set(), "fix_versions": [], "aliases": set()},
            )
            a["packages"].add(f"{name}=={version}")
            fixes = vuln.get("fix_versions") or []
            if fixes:
                a["fix_versions"] = fixes
            for alias in vuln.get("aliases") or []:
                a["aliases"].add(alias)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-json", default="-", help="pip-audit -f json output (- for stdin)")
    ap.add_argument("--registry", default=DEFAULT_REGISTRY)
    ap.add_argument("--warn-days", type=int, default=14)
    ap.add_argument(
        "--base-audit-json",
        default=None,
        help="[r291] gate mode: pip-audit -f json for the PR's base tree. "
        "Given, the checker fails only on a finding the change ADDS - "
        "unexempted at the head and not unexempted at the base, keyed by "
        "advisory id (with aliases) and package.",
    )
    ap.add_argument("--base-registry", default=None, help="registry snapshot of the base tree")
    args = ap.parse_args()
    if args.base_audit_json and not args.base_registry:
        print(
            "--base-audit-json without --base-registry: the delta adjudicates "
            "BOTH sides, so the base needs its own registry snapshot",
            file=sys.stderr,
        )
        return 1

    # full_report = "print today's per-violation report". In full-lockfile
    # mode that is the ONLY side, so it always reports; in gate mode the head
    # side stays quiet (its shared-violation chatter is not allowed to fail
    # the delta) and the base side reports only when it fails closed.
    head = adjudicate(
        Path(args.audit_json),
        Path(args.registry),
        args.warn_days,
        full_report=args.base_audit_json is None,
    )
    if not args.base_audit_json:
        return head.rc

    # The base side adjudicates with today's rules too, but its violations are
    # NOT the change's fault: a pre-existing expired REVIEW BY or a pre-existing
    # unexempted finding prints and passes (package case 5). The one base-side
    # condition that still fails closed is UNADJUDICABLE - an unparsable base
    # audit or a missing/malformed base registry makes the delta's "was it
    # already there?" question unanswerable, and an unanswerable delta never
    # reads as clean (package case 6, "an audit error on either side fails
    # closed").
    base = adjudicate(
        Path(args.base_audit_json), Path(args.base_registry), args.warn_days, full_report=False
    )
    if base.unadjudicable:
        print(
            "BASE SIDE of the delta is UNADJUDICABLE (audit unparsable or registry "
            "missing/malformed) - the gate fails closed:",
            file=sys.stderr,
        )
        return 1
    if head.unadjudicable:
        # The head side reports in place: the MISSING/malformed message the
        # head's adjudicate() already printed IS the violation list.
        return 1

    # Package case 4 vs 5, keyed by ENTRY (id, package): a registry violation
    # (expired/malformed/missing REVIEW BY, premise broken, mis-attributed
    # package, stale) reddens the delta only when the change ADDED or EDITED
    # that entry - i.e. the violation exists at the head and not at the base.
    # The same violation standing on both sides is the base's pre-existing
    # state and stays green in gate mode (full-lockfile mode still reds it on
    # its own trigger).
    entry_added = head.violated_entries - base.violated_entries
    if entry_added:
        print(
            f"{len(entry_added)} registry violation(s) on entries this change "
            f"adds or edits (violation not present at the base):",
            file=sys.stderr,
        )
        for v in sorted(entry_added):
            print(f"  - {v}", file=sys.stderr)
        return 1

    # Package cases 1/2/3: findings keyed (canonical advisory id, package).
    # canonical_keys() resolves a report id through its aliases to the same
    # key on both trees, so id drift (PYSEC vs CVE vs GHSA of one advisory)
    # does not invent a delta where the advisory was already there.
    canonical_base = canonical_keys(Path(args.base_audit_json), base)
    canonical_head = canonical_keys(Path(args.audit_json), head)
    added = canonical_head - canonical_base
    if added:
        print(
            f"{len(added)} pip-audit finding(s) this change ADDS "
            f"(unexempted at the head, not unexempted at the base):",
            file=sys.stderr,
        )
        for vid, pkg in sorted(added):
            print(f"  - {vid} on {pkg} is UNEXEMPTED", file=sys.stderr)
        return 1
    print(
        f"pip-audit delta OK: {len(canonical_head)} finding(s) shared with the "
        f"base, none added by the change (full-lockfile mode still audits the "
        f"lock on main on its own trigger)"
    )
    return head.rc if head.warnings else 0


@dataclass
class Verdict:
    """One tree's full adjudication, reusable by both modes.

    full_lockfile verdict (today's): exit 1 on ANY violation, 2 on warns-only.
    Gate mode reads `unexempted` (the id+package keys of findings no active
    entry covers), `violated_entries` (one key per registry entry that fails
    today's rules), and `unadjudicable` (the audit could not be parsed or the
    registry could not be loaded - the delta's "was it already there?"
    question is unanswerable, so a side in that state fails closed).
    """

    unexempted: set[tuple[str, str]]
    violated_entries: set[str]
    unadjudicable: bool
    rc: int
    warnings: int


def canonical_keys(audit_path: Path, v: Verdict) -> set[tuple[str, str]]:
    """Collapse `unexempted` to one key per REAL advisory: each reported id
    becomes (its canonical id-set's representative, package). Two trees
    reporting the same advisory under different ids (PYSEC at base, GHSA at
    head) must compare equal, so the representative is the sorted-min of the
    id + its aliases - the same advisory produces the same min on both sides
    whatever id pip-audit chose to lead with."""
    out: set[tuple[str, str]] = set()
    for vid, pkg in v.unexempted:
        group = {vid, *advisory_aliases(audit_path).get(vid, set())}
        out.add((min(sorted(group)), pkg))
    return out


def advisory_aliases(audit_path: Path) -> dict[str, set[str]]:
    """id -> {aliases} straight from the recorded audit report. Reads the file
    a second time (adjudicate already did) because the alias map is per-id and
    only the delta needs it; the full-lockfile path never calls this."""
    try:
        raw = audit_path.read_text()
        doc = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, set[str]] = {}
    for dep in doc.get("dependencies") or []:
        for vuln in dep.get("vulns") or []:
            vid = vuln.get("id")
            if vid:
                out.setdefault(vid, set()).update(vuln.get("aliases") or [])
    return out


def adjudicate(audit_path: Path, reg_path: Path, warn_days: int, full_report: bool) -> Verdict:
    """Run today's registry rules against one audit report.

    `full_report` prints today's per-violation diagnostics (the full-lockfile
    mode is always full_report; the delta's head side stays quiet - its
    shared-violation chatter is not allowed to fail the delta).
    """
    if not reg_path.is_file():
        print(
            f"MISSING {reg_path}: the gate fails closed without the registry. "
            "Any pip-audit finding is red until an entry here (with reason, "
            "owner and a REVIEW BY date) covers it.",
            file=sys.stderr,
        )
        return Verdict(set(), set(), True, 1, 0)

    reg = json.loads(reg_path.read_text())
    exceptions = reg.get("exceptions")
    if not isinstance(exceptions, list):
        print(f"{reg_path}: missing 'exceptions' array", file=sys.stderr)
        return Verdict(set(), set(), True, 1, 0)

    found = advisories(load_audit(audit_path))
    today = date.today()

    errors: list[str] = []
    warns: list[str] = []
    covered: set[str] = set()
    unexempted: set[tuple[str, str]] = set()
    violated_entries: set[str] = set()

    def entry_error(eid: str, msg: str) -> None:
        """A registry entry failing today's rules. The violation TEXT is the
        delta key: every message starts with the entry id, so set-difference
        on the strings is entry-keyed (gate mode reds a violation only when
        the change added or edited that entry - the same violation standing
        on both trees is the base's pre-existing state) AND carries the
        wording for the delta's report."""
        errors.append(msg)
        violated_entries.add(msg)

    for e in exceptions:
        eid = e.get("id", "?")
        rb = e.get("reviewBy") or e.get("review_by")
        if not rb:
            entry_error(eid, f"{eid}: missing reviewBy (REVIEW BY) date")
            continue
        try:
            review = datetime.strptime(rb, "%Y-%m-%d").date()
        except ValueError:
            entry_error(eid, f"{eid}: malformed reviewBy {rb!r} (want YYYY-MM-DD)")
            continue
        if review < today:
            entry_error(eid, f"{eid}: REVIEW BY {rb} has PASSED - re-review, fix, or remove")
        elif review <= today + timedelta(days=warn_days):
            warns.append(f"{eid}: REVIEW BY {rb} expires within {warn_days}d")

        ids = {eid, *(e.get("aliases") or [])}
        hit = next((i for i in ids if i in found), None)
        if hit is None:
            # R61: match the OTHER alias direction too. pip-audit emits one
            # primary id per advisory (aliases deduped into an "aliases"
            # array), so an audit reporting PYSEC-x with CVE-y in aliases and
            # a registry keyed by CVE-y is the SAME advisory - without this
            # second look the pair is double-red: the entry reads stale while
            # the advisory prints UNEXEMPTED. Exact-id logic, not fuzzy:
            # the package-attribution check below still adjudicates.
            hit = next((vid for vid, a in found.items() if ids & a["aliases"]), None)
        if hit is None:
            entry_error(
                eid,
                f"{eid}: registered but NO current pip-audit finding matches - "
                "stale (the advisory is fixed or no longer reachable); remove it",
            )
            continue
        covered.add(hit)

        a = found[hit]
        if a["fix_versions"]:
            entry_error(
                eid,
                f"{eid}: exemption premise broken - pip-audit reports fix_versions "
                f"{a['fix_versions']} (sanctioned premise is 'awaiting upstream "
                f"fix'); take the bump and drop this entry",
            )
        pkg = e.get("package")
        if pkg and not any(p.split("==", 1)[0].lower() == pkg.lower() for p in a["packages"]):
            entry_error(
                eid,
                f"{eid}: registered for {pkg!r}, pip-audit attributes it to {sorted(a['packages'])}",
            )

    for vid, a in found.items():
        if vid not in covered:
            errors.append(
                f"{vid}: pip-audit finding on {sorted(a['packages'])} is UNEXEMPTED "
                f"(fix_versions={a['fix_versions'] or 'none reported'})"
            )
            for p in a["packages"]:
                # The delta key: id + each package the advisory is reported
                # against. Package attribution is how the base/head compare
                # distinguishes "the advisory moved to another package" from
                # "the advisory was here all along".
                unexempted.add((vid, p.split("==", 1)[0].lower()))

    if full_report:
        for w in warns:
            print(f"WARN: {w}")
        if errors:
            print(f"{len(errors)} pip-audit exemption violation(s):", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
        else:
            print(
                f"pip-audit exemptions OK: {len(exceptions)} active, "
                f"{len(found)} advisories all covered, no expiry within {warn_days}d"
            )
    rc = 1 if errors else (2 if warns else 0)
    return Verdict(unexempted, violated_entries, False, rc, len(warns))


if __name__ == "__main__":
    sys.exit(main())
